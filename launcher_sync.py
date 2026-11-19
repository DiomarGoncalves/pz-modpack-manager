#!/usr/bin/env python3
"""PZ Modpack Launcher - motor (sem tela). Deixa Zomboid/mods igual a um modpack em .zip (Google Drive
ou link direto), baixando SO os arquivos que mudaram (le o indice do zip por partes, com HTTP Range).

Um modpack ativo por vez: ao ativar, a pasta mods fica SO com ele (tudo o que nao e dele e APAGADO, inclusive
os mods do pack anterior). O botao Desativar guarda os mods do pack em Zomboid/PZLauncher/estacionados/ para
jogar na Steam; ativar de novo traz de volta sem baixar. Veja PLANO_LAUNCHER.md."""
import json
import os
import re
import shutil
import struct
import tempfile
import time
import urllib.error
import urllib.request
import zlib

import modpack as MP  # pastas da Steam/Zomboid (Windows, Linux, Flatpak)

UA = "Mozilla/5.0 (PZ Modpack Launcher)"
GAP = 1 << 20          # junta trechos com ate 1 MB de distancia num pedido so
MAX_CHUNK = 64 << 20   # no maximo 64 MB por pedido


# Links ------------------------------------------------------------------------------------------
def link_direto(link):
    """Google Drive (qualquer formato de link) -> download direto; outros links ficam como estao."""
    link = (link or "").strip()
    m = re.search(r"drive\.google\.com/file/d/([\w-]+)", link) or re.search(r"[?&]id=([\w-]+)", link)
    if m and "google" in link:
        return "https://drive.usercontent.google.com/download?id=%s&export=download&confirm=t" % m.group(1)
    if "dropbox.com" in link:
        return re.sub(r"[?&]dl=0", "", link) + ("&" if "?" in link else "?") + "dl=1"
    return link


# Fontes: algo de onde se le um pedaco (inicio, tamanho) ---------------------------------------------
class ArquivoSource:
    def __init__(self, caminho):
        self.caminho = caminho
        self.tamanho = os.path.getsize(caminho)
        self.nome = os.path.basename(caminho)
        self.versao = "%d-%d" % (self.tamanho, int(os.path.getmtime(caminho)))

    def ler(self, inicio, n):
        with open(self.caminho, "rb") as f:
            f.seek(inicio)
            return f.read(n)


class SemRange(Exception):
    pass


class HttpSource:
    """Arquivo na internet lido por partes (Range). Levanta SemRange se o servidor nao aceitar."""

    def __init__(self, link, timeout=60):
        self.url = link_direto(link)
        self.timeout = timeout
        req = urllib.request.Request(self.url, headers={"User-Agent": UA, "Range": "bytes=0-0"})
        try:
            r = urllib.request.urlopen(req, timeout=timeout)
        except urllib.error.HTTPError as e:
            raise IOError(explica_http(e.code)) from e
        with r:
            if r.status != 206:
                raise SemRange("o servidor nao manda o arquivo por partes")
            m = re.search(r"/(\d+)$", r.headers.get("Content-Range", ""))
            if not m:
                raise SemRange("sem Content-Range")
            self.tamanho = int(m.group(1))
            disp = r.headers.get("Content-Disposition", "")
            n = re.search(r'filename="?([^";]+)', disp)
            self.nome = n.group(1) if n else os.path.basename(self.url.split("?")[0]) or "modpack.zip"
            self.versao = "%d|%s" % (self.tamanho, r.headers.get("Last-Modified") or r.headers.get("ETag") or "")

    def ler(self, inicio, n):
        req = urllib.request.Request(self.url, headers={"User-Agent": UA, "Range": "bytes=%d-%d" % (inicio, inicio + n - 1)})
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as r:
                if r.status != 206:
                    raise SemRange("o servidor ignorou o pedido por partes")
                return r.read()
        except urllib.error.HTTPError as e:
            raise IOError(explica_http(e.code)) from e


def explica_http(code):
    if code == 429:
        return "O servidor do link pediu para esperar (muitos pedidos). Tente de novo em alguns minutos."
    if code in (403, 404):
        return ("Link sem acesso ou apagado (HTTP %d). No Google Drive: compartilhar > 'Qualquer pessoa com o link'. "
                "Se for 403 num arquivo grande, o Drive pode ter limitado os downloads de hoje." % code)
    return "Erro HTTP %d ao baixar." % code


def abrir_fonte(link):
    """Fonte para um link (Drive/direto) ou caminho de arquivo .zip local."""
    if os.path.isfile(link):
        return ArquivoSource(link)
    return HttpSource(link)


# Indice do zip (central directory) ---------------------------------------------------------------
def ler_indice(fonte):
    """{nome: {crc, csize, usize, metodo, off}} so dos arquivos (pastas ficam de fora)."""
    n = min(fonte.tamanho, 65536 + 22)
    fim = fonte.ler(fonte.tamanho - n, n)
    i = fim.rfind(b"PK\x05\x06")
    if i < 0:
        raise IOError("Isso nao parece um .zip (sem o fim do arquivo).")
    total, cd_size, cd_off = struct.unpack("<HII", fim[i + 10:i + 20])
    if cd_off == 0xFFFFFFFF or total == 0xFFFF:  # zip64
        j = fim.rfind(b"PK\x06\x07")
        if j < 0:
            raise IOError("zip64 sem localizador")
        (eocd64_off,) = struct.unpack("<Q", fim[j + 8:j + 16])
        e64 = fonte.ler(eocd64_off, 56)
        total, cd_size, cd_off = struct.unpack("<QQQ", e64[32:56])
    cd = fonte.ler(cd_off, cd_size)
    out, p = {}, 0
    while p + 46 <= len(cd) and cd[p:p + 4] == b"PK\x01\x02":
        flag, metodo = struct.unpack("<HH", cd[p + 8:p + 12])
        crc, cs, us = struct.unpack("<III", cd[p + 16:p + 28])
        nl, el, cl = struct.unpack("<HHH", cd[p + 28:p + 34])
        (off,) = struct.unpack("<I", cd[p + 42:p + 46])
        raw = cd[p + 46:p + 46 + nl]
        nome = raw.decode("utf-8" if flag & 0x800 else "cp437", "replace").replace("\\", "/")
        extra = cd[p + 46 + nl:p + 46 + nl + el]
        q = 0
        while q + 4 <= len(extra):  # zip64: tamanhos/posicao de 64 bits no extra 0x0001
            hid, hl = struct.unpack("<HH", extra[q:q + 4])
            if hid == 1:
                vals, r = [], q + 4
                for campo in (us, cs, off):
                    if campo == 0xFFFFFFFF:
                        (v,) = struct.unpack("<Q", extra[r:r + 8])
                        vals.append(v)
                        r += 8
                    else:
                        vals.append(campo)
                us, cs, off = vals
            q += 4 + hl
        p += 46 + nl + el + cl
        if not nome.endswith("/") and seguro(nome):
            out[nome] = {"crc": crc, "csize": cs, "usize": us, "metodo": metodo, "off": off}
    return out


def seguro(nome):
    partes = [x for x in nome.split("/") if x]
    return bool(partes) and not nome.startswith("/") and ".." not in partes and ":" not in partes[0]


def raiz_dos_mods(indice):
    """Prefixo onde ficam as pastas dos mods dentro do zip ("" ou "mods/" ou "Zomboid/mods/").
    Arquivos soltos na raiz (LEIA-ME, manifesto do 'Exportar zip nosteam') nao contam."""
    for pre in ("mods/", "Zomboid/mods/"):
        dentro = [n for n in indice if n.startswith(pre)]
        if dentro and all(n.startswith(pre) or "/" not in n for n in indice):
            return pre
    return ""


def arquivos_do_pack(indice):
    """{nome no zip: caminho relativo em mods/} so do que fica dentro de uma pasta de mod."""
    pre = raiz_dos_mods(indice)
    out = {}
    for n in indice:
        if n.startswith(pre):
            rel = n[len(pre):]
            if "/" in rel:  # arquivo solto na raiz do pack nao e mod
                out[n] = rel
    return out


# Estado local --------------------------------------------------------------------------------------
def pasta_zomboid():
    return MP.pasta_zomboid_jogador()


def pasta_launcher(zomboid):
    d = os.path.join(zomboid, "PZLauncher")
    os.makedirs(d, exist_ok=True)
    return d


def ler_json(caminho, padrao):
    try:
        return json.load(open(caminho, encoding="utf-8"))
    except (OSError, ValueError):
        return padrao


def gravar_json(caminho, dados):
    tmp = caminho + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(dados, f, indent=1, ensure_ascii=False)
    os.replace(tmp, caminho)


def crc_arquivo(caminho):
    crc = 0
    with open(caminho, "rb") as f:
        while True:
            b = f.read(1 << 20)
            if not b:
                return crc & 0xFFFFFFFF
            crc = zlib.crc32(b, crc)


# Plano -------------------------------------------------------------------------------------------------
def planejar(indice, mods_dir, estado):
    """Compara o zip com a pasta mods. estado["arquivos"][rel] = {size, mtime, crc} (cache do CRC).
    Devolve {baixar: [nomes do zip], apagar: [rel], pastas: set(pastas do pack), bytes: total a baixar}."""
    pre = raiz_dos_mods(indice)
    cache = estado.get("arquivos", {})
    baixar, pastas, alvo = [], set(), set()
    for nome, rel in arquivos_do_pack(indice).items():
        e = indice[nome]
        pastas.add(rel.split("/")[0])
        alvo.add(rel)
        local = os.path.join(mods_dir, *rel.split("/"))
        try:
            st = os.stat(local)
        except OSError:
            baixar.append(nome)
            continue
        c = cache.get(rel)
        if st.st_size != e["usize"]:
            baixar.append(nome)
            continue
        if c and c.get("size") == st.st_size and c.get("mtime") == st.st_mtime_ns:
            crc = c.get("crc")
        else:
            crc = crc_arquivo(local)
            cache[rel] = {"size": st.st_size, "mtime": st.st_mtime_ns, "crc": crc}
        if crc != e["crc"]:
            baixar.append(nome)
    apagar = []
    for pasta in pastas:
        raiz = os.path.join(mods_dir, pasta)
        for dp, _, fs in os.walk(raiz):
            for f in fs:
                rel = os.path.relpath(os.path.join(dp, f), mods_dir).replace(os.sep, "/")
                if rel not in alvo:
                    apagar.append(rel)
    estado["arquivos"] = cache
    total = sum(indice[n]["csize"] for n in baixar)
    return {"baixar": baixar, "apagar": apagar, "pastas": pastas, "bytes": total, "prefixo": pre}


# Aplicar ------------------------------------------------------------------------------------------------
def _grupos(indice, nomes):
    """Junta arquivos vizinhos no zip em pedidos maiores (menos idas ao servidor)."""
    itens = sorted(nomes, key=lambda n: indice[n]["off"])
    grupos, atual = [], None
    for n in itens:
        e = indice[n]
        ini = e["off"]
        fim = ini + 30 + 1024 + e["csize"] + 64 * 1024  # cabecalho local + nome/extra (folga)
        if atual and ini - atual["fim"] <= GAP and fim - atual["ini"] <= MAX_CHUNK:
            atual["fim"] = max(atual["fim"], fim)
            atual["nomes"].append(n)
        else:
            atual = {"ini": ini, "fim": fim, "nomes": [n]}
            grupos.append(atual)
    return grupos


def _extrair(bloco, base, e):
    """Dados de um arquivo dentro de um bloco lido a partir de "base"."""
    p = e["off"] - base
    if bloco[p:p + 4] != b"PK\x03\x04":
        raise IOError("cabecalho local invalido")
    nl, el = struct.unpack("<HH", bloco[p + 26:p + 30])
    ini = p + 30 + nl + el
    comp = bloco[ini:ini + e["csize"]]
    if len(comp) < e["csize"]:
        return None  # bloco curto (extra local maior que a folga): pede de novo sozinho
    if e["metodo"] == 0:
        dados = comp
    elif e["metodo"] == 8:
        dados = zlib.decompressobj(-15).decompress(comp)
    else:
        raise IOError("compressao %d nao suportada" % e["metodo"])
    if zlib.crc32(dados) & 0xFFFFFFFF != e["crc"]:
        raise IOError("arquivo corrompido no download (CRC)")
    return dados


def aplicar(fonte, indice, plano, mods_dir, estado, progresso=None):
    """Baixa so o necessario, apaga o que saiu e atualiza o estado. progresso(feito, total) em bytes."""
    total, feito = max(1, plano["bytes"]), 0
    pre = plano["prefixo"]
    cache = estado.setdefault("arquivos", {})
    for g in _grupos(indice, plano["baixar"]):
        tam = min(g["fim"], fonte.tamanho) - g["ini"]
        bloco = fonte.ler(g["ini"], tam)
        for n in g["nomes"]:
            e = indice[n]
            dados = _extrair(bloco, g["ini"], e)
            if dados is None:
                b2 = fonte.ler(e["off"], min(fonte.tamanho - e["off"], 30 + 65535 * 2 + e["csize"]))
                dados = _extrair(b2, e["off"], e)
            rel = n[len(pre):]
            destino = os.path.join(mods_dir, *rel.split("/"))
            os.makedirs(os.path.dirname(destino), exist_ok=True)
            tmp = destino + ".pzl-tmp"
            with open(tmp, "wb") as f:
                f.write(dados)
            os.replace(tmp, destino)
            st = os.stat(destino)
            cache[rel] = {"size": st.st_size, "mtime": st.st_mtime_ns, "crc": e["crc"]}
            feito += e["csize"]
            if progresso:
                progresso(feito, total)
    for rel in plano["apagar"]:
        try:
            os.remove(os.path.join(mods_dir, *rel.split("/")))
        except OSError:
            pass
        cache.pop(rel, None)
    # pastas que ficaram vazias dentro dos mods do pack
    for pasta in plano["pastas"]:
        raiz = os.path.normpath(os.path.join(mods_dir, pasta))
        for dp, _, _ in os.walk(raiz, topdown=False):  # de baixo para cima: a pasta-mae esvazia depois
            if os.path.normpath(dp) != raiz and os.path.isdir(dp) and not os.listdir(dp):
                try:
                    os.rmdir(dp)
                except OSError:
                    pass
    estado["pastas"] = sorted(plano["pastas"])


# Packs cadastrados, ativo e estacionar (Desativar) --------------------------------------------------------------
def config(zomboid):
    return ler_json(os.path.join(pasta_launcher(zomboid), "launcher.json"), {"packs": {}, "ativo": None})


def salvar_config(zomboid, cfg):
    gravar_json(os.path.join(pasta_launcher(zomboid), "launcher.json"), cfg)


def estado_pack(zomboid, pack):
    return ler_json(os.path.join(pasta_launcher(zomboid), "estado_%s.json" % pack), {})


def salvar_estado(zomboid, pack, est):
    gravar_json(os.path.join(pasta_launcher(zomboid), "estado_%s.json" % pack), est)


def slug(nome):
    return re.sub(r"[^A-Za-z0-9_-]+", "_", nome or "").strip("_") or "modpack"


def adicionar_pack(zomboid, nome, link):
    cfg = config(zomboid)
    s = slug(nome)
    cfg["packs"][s] = {"nome": nome, "link": link, "versao": None, "verificado": None}
    salvar_config(zomboid, cfg)
    return s


def remover_pack(zomboid, pack):
    """Tira o pack da lista. Se for o ativo, os mods dele sao apagados da pasta mods."""
    cfg = config(zomboid)
    mods = os.path.join(zomboid, "mods")
    if cfg.get("ativo") == pack:
        for p in estado_pack(zomboid, pack).get("pastas", []):
            if p and os.path.isdir(os.path.join(mods, p)):
                shutil.rmtree(os.path.join(mods, p), ignore_errors=True)
        cfg["ativo"] = None
    shutil.rmtree(os.path.join(pasta_launcher(zomboid), "estacionados", pack), ignore_errors=True)
    for f in ("estado_%s.json" % pack,):
        try:
            os.remove(os.path.join(pasta_launcher(zomboid), f))
        except OSError:
            pass
    cfg["packs"].pop(pack, None)
    salvar_config(zomboid, cfg)


def _mover(origem, destino):
    os.makedirs(os.path.dirname(destino), exist_ok=True)
    if os.path.exists(destino):
        shutil.rmtree(destino, ignore_errors=True)
    shutil.move(origem, destino)


def preparar_pasta(zomboid, pack, pastas_do_pack):
    """Antes de sincronizar o pack: traz de volta os mods dele que estavam guardados (botao Desativar) e
    APAGA da pasta mods tudo o que nao e deste pack (mods soltos e os do pack anterior).
    Devolve (restaurados, apagados)."""
    cfg = config(zomboid)
    mods = os.path.join(zomboid, "mods")
    os.makedirs(mods, exist_ok=True)
    est_dir = os.path.join(pasta_launcher(zomboid), "estacionados")
    restaurados, apagados = [], []
    meu = os.path.join(est_dir, pack)
    if os.path.isdir(meu):
        for p in os.listdir(meu):
            if not os.path.exists(os.path.join(mods, p)):
                shutil.move(os.path.join(meu, p), os.path.join(mods, p))
                restaurados.append(p)
    shutil.rmtree(est_dir, ignore_errors=True)  # o guardado de outro pack tambem sai: um modpack por vez
    for p in sorted(os.listdir(mods)):
        full = os.path.join(mods, p)
        if os.path.isdir(full) and p not in pastas_do_pack:
            shutil.rmtree(full, ignore_errors=True)
            apagados.append(p)
    anterior = cfg.get("ativo")
    if anterior and anterior != pack and anterior in cfg["packs"]:
        cfg["packs"][anterior]["versao"] = None  # os mods dele foram apagados: ativar de novo baixa
    cfg["ativo"] = pack
    salvar_config(zomboid, cfg)
    return restaurados, apagados


def desativar(zomboid):
    """Estaciona os mods do pack ativo (para jogar em servidor da Steam sem duplicidade)."""
    cfg = config(zomboid)
    pack = cfg.get("ativo")
    if not pack:
        return []
    mods = os.path.join(zomboid, "mods")
    out = []
    for p in estado_pack(zomboid, pack).get("pastas", []):
        if os.path.isdir(os.path.join(mods, p)):
            _mover(os.path.join(mods, p), os.path.join(pasta_launcher(zomboid), "estacionados", pack, p))
            out.append(p)
    cfg["ativo"] = None
    salvar_config(zomboid, cfg)
    return out


# Tudo junto ------------------------------------------------------------------------------------------------
def verificar(zomboid, pack):
    """So confere se o link mudou (sem baixar). Devolve (mudou, versao_remota, fonte)."""
    cfg = config(zomboid)
    p = cfg["packs"][pack]
    fonte = abrir_fonte(p["link"])
    p["verificado"] = int(time.time())
    p["tamanho"] = fonte.tamanho
    p["arquivo"] = fonte.nome
    salvar_config(zomboid, cfg)
    return fonte.versao != p.get("versao") or cfg.get("ativo") != pack, fonte.versao, fonte


def sincronizar(zomboid, pack, progresso=None, etapa=None):
    """Ativa o pack e deixa a pasta mods igual a ele, baixando so o que mudou. Devolve um resumo."""
    def diz(t):
        if etapa:
            etapa(t)
    cfg = config(zomboid)
    p = cfg["packs"][pack]
    diz("Lendo o indice do modpack...")
    try:
        fonte = abrir_fonte(p["link"])
    except SemRange:
        diz("Este link nao entrega por partes: baixando o arquivo inteiro...")
        fonte = _baixar_inteiro(p["link"], progresso)
    indice = ler_indice(fonte)
    pastas = {rel.split("/")[0] for rel in arquivos_do_pack(indice).values()}
    rest, apagadas = preparar_pasta(zomboid, pack, pastas)
    mods = os.path.join(zomboid, "mods")
    estado = estado_pack(zomboid, pack)
    diz("Comparando com a pasta mods...")
    plano = planejar(indice, mods, estado)
    diz("Baixando %d arquivo(s) (%.1f MB)..." % (len(plano["baixar"]), plano["bytes"] / 1e6))
    aplicar(fonte, indice, plano, mods, estado, progresso)
    salvar_estado(zomboid, pack, estado)
    cfg = config(zomboid)
    cfg["packs"][pack].update({"versao": fonte.versao, "atualizado": int(time.time()), "mods": len(pastas),
                               "tamanho": fonte.tamanho, "arquivo": fonte.nome})
    salvar_config(zomboid, cfg)
    return {"baixados": len(plano["baixar"]), "bytes": plano["bytes"], "apagados": len(plano["apagar"]),
            "mods": len(pastas), "restaurados": rest, "removidos": apagadas}


def _baixar_inteiro(link, progresso=None):
    url = link_direto(link)
    pasta = tempfile.mkdtemp(prefix="pzlauncher_")
    destino = os.path.join(pasta, "modpack.zip")
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=120) as r, open(destino, "wb") as f:
            total = int(r.headers.get("Content-Length") or 0) or 1
            feito = 0
            while True:
                b = r.read(1 << 20)
                if not b:
                    break
                f.write(b)
                feito += len(b)
                if progresso:
                    progresso(feito, total)
    except urllib.error.HTTPError as e:
        raise IOError(explica_http(e.code)) from e
    return ArquivoSource(destino)
