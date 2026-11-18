#!/usr/bin/env python3
"""PZ Modpack Manager - gerenciador de modpacks de servidor do Project Zomboid.
https://github.com/DiomarGoncalves/pz-modpack-manager  (licenca MIT)

Cada modpack (um por servidor) tem a sua lista em packs/<nome>/modpack.json (na pasta de dados do
programa) e a sua pasta de publicacao em <pasta Zomboid>/Workshop/<pasta do modpack>.

REGRA PRINCIPAL: o que ja esta no pacote fica CONGELADO. "montar" so copia os mods novos
(ou os que voce mandar atualizar) da pasta de downloads da Workshop; os outros ficam como
estao, mesmo que a Steam tenha baixado versao nova.

Linha de comando (a janela e o modpack_gui.py):
    python3 modpack.py packs                                  # lista os modpacks
    python3 modpack.py pastas                                 # pastas achadas nesta maquina
    python3 modpack.py novo "Nome" [--ini servidor.ini] [--branch 42.21]
    python3 modpack.py [--pack nome] status
    python3 modpack.py [--pack nome] adicionar <id ou link> [--mods ID1,ID2]
    python3 modpack.py [--pack nome] remover <id>
    python3 modpack.py [--pack nome] separar <id> "motivo"    # fica fora do pacote
    python3 modpack.py [--pack nome] juntar <id>              # volta para dentro do pacote
    python3 modpack.py [--pack nome] montar [--atualizar ID,ID | --atualizar tudo] [--simular]
    python3 modpack.py [--pack nome] linhas
    python3 modpack.py [--pack nome] baixados                 # todos os mods baixados no PC
    python3 modpack.py [--pack nome] novidades                # mods do pacote com versao nova
    python3 modpack.py [--pack nome] ini <servidor.ini> [saida]  # devolve <nome>_pronto.ini
    python3 modpack.py baixar ID,ID                          # download automatico (SteamCMD, sem login)
    python3 modpack.py procurar "texto" [--pagina 2] [--ordem trend] [--todas-versoes]  # busca na Workshop
  Sem Steam (servidor ligado com -nosteam):
    python3 modpack.py [--pack nome] exportar-nosteam [saida.zip]  # zip com mods/ para servidor e jogadores
    python3 modpack.py [--pack nome] ini-nosteam <servidor.ini> [saida]  # Mods= certo, WorkshopItems= vazio
    python3 modpack.py instalar-nosteam <zip> [--zomboid PASTA]  # jogador: instala em Zomboid/mods
    python3 modpack.py desinstalar-nosteam [pack] [--zomboid PASTA]  # sem pack: lista os instalados
"""
import argparse
import glob
import json
import os
import re
import shutil
import sys
import time
import unicodedata
import urllib.error
import urllib.request

VERSAO = "1.1.0"
AQUI = os.path.dirname(os.path.abspath(__file__))
# Arquivos que vem junto com o programa (no executavel ficam na pasta temporaria do PyInstaller).
RECURSOS = getattr(sys, "_MEIPASS", AQUI)


def pasta_de_dados():
    """Onde ficam as listas dos modpacks e as pastas escolhidas.
    - rodando o .py: ao lado do codigo (como sempre);
    - executavel portatil (.exe / AppImage / binario): pasta "ModpackServidor_dados" AO LADO do
      executavel, para levar tudo junto num pendrive; se ali nao der para gravar, usa a pasta do usuario."""
    if not getattr(sys, "frozen", False):
        return AQUI
    exe = os.environ.get("APPIMAGE") or sys.executable  # AppImage: o arquivo .AppImage, nao o ponto de montagem
    candidatos = [os.path.join(os.path.dirname(os.path.abspath(exe)), "ModpackServidor_dados")]
    if os.name == "nt":
        candidatos.append(os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "ModpackServidor"))
    else:
        candidatos.append(os.path.join(os.environ.get("XDG_DATA_HOME", os.path.expanduser("~/.local/share")), "ModpackServidor"))
    for d in candidatos:
        try:
            os.makedirs(d, exist_ok=True)
            teste = os.path.join(d, ".teste_escrita")
            open(teste, "w").close()
            os.remove(teste)
            return d
        except OSError:
            continue
    return candidatos[-1]


DADOS = pasta_de_dados()
PACKS = os.path.join(DADOS, "packs")
LOCAL = os.path.join(DADOS, "config_local.json")  # pastas desta maquina (escolhidas na mao)
APP_PZ = "108600"


# Pastas (Windows, Linux nativo, Linux com Steam em Flatpak, macOS) ---------------------

def _existentes(lista):
    out = []
    for p in lista:
        p = os.path.realpath(os.path.expanduser(os.path.expandvars(p)))
        if os.path.isdir(p) and p not in out:
            out.append(p)
    return out


def raizes_steam():
    c = []
    if os.name == "nt":
        try:
            import winreg
            k = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam")
            c.append(winreg.QueryValueEx(k, "SteamPath")[0])
        except OSError:
            pass
        c += [r"C:\Program Files (x86)\Steam", r"C:\Program Files\Steam"]
    elif sys.platform == "darwin":
        c.append("~/Library/Application Support/Steam")
    else:
        c += ["~/.var/app/com.valvesoftware.Steam/.local/share/Steam",  # Steam em Flatpak
              "~/.local/share/Steam", "~/.steam/steam", "~/.steam/root",
              "~/snap/steam/common/.local/share/Steam"]
    return _existentes(c)


def bibliotecas(raiz):
    """A raiz da Steam + as outras bibliotecas (outros discos) do libraryfolders.vdf."""
    libs = [raiz]
    vdf = os.path.join(raiz, "steamapps", "libraryfolders.vdf")
    if os.path.exists(vdf):
        for p in re.findall(r'"path"\s*"([^"]+)"', open(vdf, encoding="utf-8", errors="ignore").read()):
            libs.append(p.replace("\\\\", "\\"))
    return _existentes(libs)


def local():
    try:
        return json.load(open(LOCAL, encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def salvar_local(dados):
    with open(LOCAL, "w", encoding="utf-8") as f:
        json.dump(dados, f, indent=1, ensure_ascii=False)


def detectar_workshop():
    """Pasta workshop/content/108600 (downloads dos mods do PZ)."""
    for raiz in raizes_steam():
        for lib in bibliotecas(raiz):
            d = os.path.join(lib, "steamapps", "workshop", "content", APP_PZ)
            if os.path.isdir(d):
                return d
    return None


def detectar_zomboid(workshop=None):
    """Pasta Zomboid do usuario (onde fica Workshop/ para publicar)."""
    c = []
    if workshop and ".var/app/com.valvesoftware.Steam" in workshop.replace("\\", "/"):
        c.append("~/.var/app/com.valvesoftware.Steam/Zomboid")  # Flatpak: o jogo grava aqui
    if os.name == "nt":
        c.append(os.path.join(os.environ.get("USERPROFILE", "~"), "Zomboid"))
    c += ["~/Zomboid", "~/.var/app/com.valvesoftware.Steam/Zomboid"]
    e = _existentes(c)
    return e[0] if e else None


def definir_pastas():
    """Preenche WORKSHOP, ACF e PUBLICAR (escolha manual em config_local.json vence)."""
    global WORKSHOP, ACF, PUBLICAR
    loc = local()
    WORKSHOP = loc.get("workshop") or detectar_workshop() or ""
    zomboid = loc.get("zomboid") or detectar_zomboid(WORKSHOP) or os.path.expanduser("~/Zomboid")
    ACF = os.path.join(os.path.dirname(os.path.dirname(WORKSHOP)), "appworkshop_%s.acf" % APP_PZ) if WORKSHOP else ""
    PUBLICAR = os.path.join(zomboid, "Workshop")
    return WORKSHOP, PUBLICAR


def pastas_ok():
    """Lista de problemas com as pastas (vazia = tudo certo)."""
    out = []
    if not pastas_downloads():
        out.append("Nao achei a pasta de downloads da Workshop do PZ (steamapps/workshop/content/108600). "
                   "Use 'Pastas...' ou baixe um mod pelo download automatico.")
    if not os.path.isdir(os.path.dirname(PUBLICAR)):
        out.append("Nao achei a pasta Zomboid do usuario (%s). Abra o jogo uma vez ou use 'Pastas...'." % os.path.dirname(PUBLICAR))
    return out


definir_pastas()


# Download automatico (SteamCMD oficial da Valve, login anonimo) ---------------------------

URLS_STEAMCMD = {
    "nt": "https://steamcdn-a.akamaihd.net/client/installer/steamcmd.zip",
    "linux": "https://steamcdn-a.akamaihd.net/client/installer/steamcmd_linux.tar.gz",
    "darwin": "https://steamcdn-a.akamaihd.net/client/installer/steamcmd_osx.tar.gz",
}


def pasta_steamcmd():
    """Onde a SteamCMD fica. Portatil: junto dos dados; pelo codigo: na pasta do usuario (fora do git)."""
    escolhida = local().get("steamcmd")
    if escolhida:
        return escolhida
    if getattr(sys, "frozen", False):
        return os.path.join(DADOS, "steamcmd")
    if os.name == "nt":
        base = os.environ.get("APPDATA", os.path.expanduser("~"))
    else:
        base = os.environ.get("XDG_DATA_HOME", os.path.expanduser("~/.local/share"))
    return os.path.join(base, "ModpackServidor", "steamcmd")


def steamcmd_exe():
    return os.path.join(pasta_steamcmd(), "steamcmd.exe" if os.name == "nt" else "steamcmd.sh")


def workshop_steamcmd():
    """Pasta de downloads da SteamCMD. Ela grava em <HOME>/Steam/steamapps (no Linux o HOME e o nosso)
    ou ao lado do executavel (Windows); a pasta que a propria SteamCMD informou ao baixar vence."""
    base = pasta_steamcmd()
    candidatos = [local().get("workshop_steamcmd"),
                  os.path.join(base, "home", "Steam", "steamapps", "workshop", "content", APP_PZ),
                  os.path.join(base, "steamapps", "workshop", "content", APP_PZ)]
    for c in candidatos:
        if c and os.path.isdir(c):
            return c
    return candidatos[1] if os.name != "nt" else candidatos[2]


def instalar_steamcmd(timeout=120):
    """Baixa e extrai a SteamCMD oficial. Devolve (ok, mensagens)."""
    import tarfile
    import tempfile
    import zipfile
    chave = "nt" if os.name == "nt" else ("darwin" if sys.platform == "darwin" else "linux")
    destino_dir = pasta_steamcmd()
    os.makedirs(destino_dir, exist_ok=True)
    fd, temp = tempfile.mkstemp(suffix=".zip" if chave == "nt" else ".tar.gz")
    os.close(fd)
    try:
        req = urllib.request.Request(URLS_STEAMCMD[chave], headers={"User-Agent": "Mozilla/5.0 (ModpackServidor)"})
        with urllib.request.urlopen(req, timeout=timeout) as r, open(temp, "wb") as f:
            shutil.copyfileobj(r, f)
        raiz = os.path.realpath(destino_dir)

        def dentro(nome):
            alvo = os.path.realpath(os.path.join(destino_dir, nome))
            return alvo == raiz or alvo.startswith(raiz + os.sep)
        if chave == "nt":
            with zipfile.ZipFile(temp) as z:
                if not all(dentro(n) for n in z.namelist()):
                    return False, ["Arquivo da SteamCMD com caminho estranho: nao extrai."]
                z.extractall(destino_dir)
        else:
            with tarfile.open(temp) as t:
                membros = t.getmembers()
                if not all(dentro(m.name) and (m.isfile() or m.isdir()) for m in membros):
                    return False, ["Arquivo da SteamCMD com caminho estranho: nao extrai."]
                t.extractall(destino_dir, members=membros)
            for x in ("steamcmd.sh", os.path.join("linux32", "steamcmd"), "steamcmd"):
                f = os.path.join(destino_dir, x)
                if os.path.isfile(f):
                    os.chmod(f, 0o755)
    except Exception as e:
        return False, ["Nao consegui baixar a SteamCMD da Valve: %s" % e]
    finally:
        if os.path.exists(temp):
            os.remove(temp)
    return True, ["SteamCMD instalada em %s." % destino_dir]


LINHAS_STEAMCMD = re.compile(r"Success|ERROR|FAILED|Failed|Downloading item|Logging in|Waiting for|Update|Timeout|No subscription")


def baixar_automatico(itens, aviso=None, tentativas=2):
    """Baixa itens da Workshop pela SteamCMD com login anonimo (sem conta e sem inscricao).
    aviso(linha) recebe as linhas importantes da saida. Devolve (baixados, falhas {item: motivo}, mensagens)."""
    import subprocess
    itens = [i for i in dict.fromkeys(itens) if i]
    msgs = []
    if not itens:
        return [], {}, ["Nada para baixar."]
    if not os.path.isfile(steamcmd_exe()):
        if aviso:
            aviso("Instalando a SteamCMD (so na primeira vez)...")
        ok, m = instalar_steamcmd()
        msgs += m
        if not ok:
            return [], {i: "SteamCMD nao instalada" for i in itens}, msgs
    env = dict(os.environ)
    if os.name != "nt":
        env["HOME"] = os.path.join(pasta_steamcmd(), "home")  # nao mexe na ~/.steam da pessoa
        os.makedirs(env["HOME"], exist_ok=True)
    extra = {"creationflags": 0x08000000} if os.name == "nt" else {}  # Windows: sem janela preta
    baixados, falhas, faltam = [], {}, list(itens)
    for _ in range(tentativas):
        cmd = [steamcmd_exe(), "+login", "anonymous"]
        for i in faltam:
            cmd += ["+workshop_download_item", APP_PZ, i]
        cmd.append("+quit")
        try:
            p = subprocess.Popen(cmd, cwd=pasta_steamcmd(), env=env, stdout=subprocess.PIPE,
                                 stderr=subprocess.STDOUT, text=True, errors="ignore", **extra)
        except OSError as e:
            dica = ""
            if os.name != "nt":
                dica = (" No Linux a SteamCMD precisa das bibliotecas de 32 bits: sudo apt install lib32gcc-s1 "
                        "(Ubuntu/Debian/Mint) ou sudo dnf install glibc.i686 libstdc++.i686 (Fedora).")
            return baixados, {i: "nao rodou: %s" % e for i in faltam}, msgs + ["Nao consegui rodar a SteamCMD: %s.%s" % (e, dica)]
        saida = []
        for linha in p.stdout:
            linha = re.sub(r"\x1b\[[0-9;]*m|\[0m", "", linha)  # tira as cores do terminal
            saida.append(linha)
            if aviso and LINHAS_STEAMCMD.search(linha):
                aviso(linha.strip())
            m = re.search(r'Success\. Downloaded item (\d+)(?: to "([^"]+)")?', linha)
            if m:
                baixados.append(m.group(1))
                falhas.pop(m.group(1), None)
                if m.group(2):  # guarda onde a SteamCMD realmente grava
                    pasta = os.path.dirname(m.group(2))
                    loc = local()
                    if loc.get("workshop_steamcmd") != pasta:
                        loc["workshop_steamcmd"] = pasta
                        salvar_local(loc)
            m = re.search(r"ERROR! Download item (\d+) failed \(([^)]*)\)", linha)
            if m:
                falhas[m.group(1)] = m.group(2)
        p.wait()
        if p.returncode == 127 or any("cannot open shared object" in l or "No such file or directory" in l for l in saida[:20]):
            msgs.append("A SteamCMD nao abriu. No Linux ela precisa das bibliotecas de 32 bits: "
                        "sudo apt install lib32gcc-s1 (Ubuntu/Debian/Mint) ou sudo dnf install glibc.i686 libstdc++.i686 (Fedora).")
        for i in itens:
            if i not in baixados:
                falhas.setdefault(i, "sem resposta da SteamCMD")
        # tenta de novo so os que deram tempo esgotado (item grande); "Failure"/"Access Denied" nao adianta
        faltam = [i for i in itens if i not in baixados and ("Timeout" in falhas[i] or "sem resposta" in falhas[i])]
        if not faltam:
            break
    if baixados:
        msgs.append("Baixado automatico: %s." % ", ".join(baixados))
    if falhas:
        msgs.append("Nao baixou: %s." % ", ".join("%s (%s)" % kv for kv in falhas.items()))
    return baixados, falhas, msgs


PROIBIDOS = (".exe", ".dll", ".bat", ".app", ".dylib", ".sh", ".so", ".zip")  # regra do uploader do jogo


# Leitura dos mods baixados -------------------------------------------------------------

def item_id(texto):
    """Aceita o numero ou o link da Workshop."""
    m = re.search(r"id=(\d+)", texto or "") or re.search(r"(\d{6,})", texto or "")
    return m.group(1) if m else None


def ler_info(path):
    t = open(path, encoding="utf-8", errors="ignore").read()

    def campo(k):
        m = re.search(r"^\s*%s\s*=\s*(.+?)\s*$" % k, t, re.M)
        return m.group(1).strip() if m else None
    req = []
    for m in re.finditer(r"^\s*require\s*=\s*(.+?)\s*$", t, re.M):
        req += [r.strip().lstrip("\\").strip() for r in re.split(r"[,;]", m.group(1)) if r.strip()]
    return {"id": campo("id"), "name": campo("name"), "require": req}


def info_pasta(md):
    """ids, dependencias (B42) e nome de uma pasta de mod."""
    infos = glob.glob(os.path.join(glob.escape(md), "**", "mod.info"), recursive=True)
    b42 = [p for p in infos if os.path.basename(os.path.dirname(p)).startswith("42")]
    raiz = [p for p in infos if os.path.dirname(p) == md]
    usar = [ler_info(p) for p in (b42 or raiz or infos)]
    todos = [ler_info(p) for p in infos]
    ids = sorted({d["id"] for d in usar + todos if d["id"]})
    req = sorted({r for d in usar for r in d["require"]})
    nome = next((d["name"] for d in usar + todos if d["name"]), os.path.basename(md))
    return {"ids": ids, "req": req, "nome": nome, "tem_info": bool(infos)}


def pastas_downloads():
    """Pastas workshop/content/108600 com mods baixados: a da Steam e a da SteamCMD (download automatico)."""
    out = []
    for d in (WORKSHOP, workshop_steamcmd()):
        if d and os.path.isdir(d) and os.path.realpath(d) not in [os.path.realpath(x) for x in out]:
            out.append(d)
    return out


def itens_baixados():
    """ids dos itens baixados (Steam + SteamCMD), sem repetir."""
    out = []
    for d in pastas_downloads():
        for item in os.listdir(d):
            if item.isdigit() and item not in out:
                out.append(item)
    return out


_CACHE_ACF = {}


def _versoes_de(content):
    """timeupdated de cada item no appworkshop_108600.acf ao lado dessa pasta de downloads."""
    acf = os.path.join(os.path.dirname(os.path.dirname(content)), "appworkshop_%s.acf" % APP_PZ)
    try:
        mt = os.path.getmtime(acf)
    except OSError:
        return {}
    if _CACHE_ACF.get(acf, (None,))[0] != mt:
        t = open(acf, encoding="utf-8", errors="ignore").read()
        out = {}
        for m in re.finditer(r'"(\d+)"\s*\{[^{}]*?"timeupdated"\s*"(\d+)"', t):
            out.setdefault(m.group(1), m.group(2))
        _CACHE_ACF[acf] = (mt, out)
    return _CACHE_ACF[acf][1]


def pasta_do_item(item):
    """Pasta <downloads>/<item>/mods mais nova entre Steam e SteamCMD (ou None)."""
    achados = [d for d in pastas_downloads() if os.path.isdir(os.path.join(d, item, "mods"))]
    if not achados:
        return None
    # copia pela metade (Steam apagando ou baixando: sem nenhum mod.info) perde para a completa
    achados.sort(key=lambda d: (_tem_mod_info(os.path.join(d, item, "mods")), int(_versoes_de(d).get(item) or 0)),
                 reverse=True)
    return os.path.join(achados[0], item, "mods")


def _tem_mod_info(pasta):
    for _, _, arquivos in os.walk(pasta):
        if "mod.info" in arquivos:
            return True
    return False


def steam_pastas(item):
    """Pastas de mod do item baixado (Steam ou SteamCMD), ou None se nao esta baixado."""
    base = pasta_do_item(item)
    if not base:
        return None
    out = []
    for md in sorted(glob.glob(os.path.join(glob.escape(base), "*"))):
        if os.path.isdir(md):
            d = info_pasta(md)
            d.update({"item": item, "origem": md, "folder": os.path.basename(md)})
            out.append(d)
    return out


def versoes():
    """timeupdated de cada item baixado (appworkshop_108600.acf da Steam e da SteamCMD; vale o mais novo)."""
    out = {}
    for d in pastas_downloads():
        for item, v in _versoes_de(d).items():
            if int(v) > int(out.get(item) or 0):
                out[item] = v
    return out


# Modpacks ----------------------------------------------------------------------------

def slug(nome):
    s = unicodedata.normalize("NFKD", nome).encode("ascii", "ignore").decode()
    s = re.sub(r"[^A-Za-z0-9]+", "_", s).strip("_")
    return s or "modpack"


def listar_packs():
    """[(slug, titulo)] em ordem alfabetica."""
    out = []
    for f in sorted(glob.glob(os.path.join(PACKS, "*", "modpack.json"))):
        try:
            cfg = json.load(open(f, encoding="utf-8"))
            out.append((os.path.basename(os.path.dirname(f)), cfg.get("titulo", "?")))
        except (OSError, ValueError):
            pass
    return out


def carregar(nome=None):
    """Carrega um modpack pelo slug (ou o unico/primeiro existente)."""
    packs = listar_packs()
    if not packs:
        raise SystemExit("Nenhum modpack ainda: crie um com 'novo'.")
    if nome is None:
        nome = packs[0][0]
    d = os.path.join(PACKS, nome)
    f = os.path.join(d, "modpack.json")
    if not os.path.exists(f):
        raise SystemExit("Modpack '%s' nao existe. Existentes: %s" % (nome, ", ".join(p for p, _ in packs)))
    cfg = json.load(open(f, encoding="utf-8"))
    cfg["_dir"] = d
    cfg.setdefault("separados", {})
    cfg.setdefault("congelado", {})
    return cfg


def salvar(cfg):
    dados = {k: v for k, v in cfg.items() if not k.startswith("_")}
    with open(os.path.join(cfg["_dir"], "modpack.json"), "w", encoding="utf-8") as f:
        json.dump(dados, f, indent=1, ensure_ascii=False)
        f.write("\n")


def ler_ini_listas(caminho):
    txt = open(caminho, encoding="utf-8", errors="ignore").read()
    mm = re.search(r"^Mods=(.*)$", txt, re.M)
    mi = re.search(r"^WorkshopItems=(.*)$", txt, re.M)
    if not mm or not mi:
        return None, None
    mods = [m.strip() for m in mm.group(1).split(";") if m.strip()]
    itens = [i.strip() for i in mi.group(1).split(";") if i.strip()]
    return mods, itens


def ids_publicados():
    """ids da Workshop dos nossos proprios modpacks (para nao importar um pacote dentro de outro)."""
    out = set()
    for s, _ in listar_packs():
        p = pacote_id(carregar(s))
        if p:
            out.add(p)
    return out


def expandir_pacotes(itens):
    """Troca cada modpack NOSSO (id publicado) pelos itens originais dele, na mesma posicao, sem repetir.
    Devolve (itens, [(nome do pack, id, quantos itens)])."""
    packs = {}
    for s_, _ in listar_packs():
        try:
            c = carregar(s_)
        except Exception:
            continue
        pub = pacote_id(c)
        if pub:
            packs[pub] = c
    out, abertos = [], []
    for i in itens:
        if i in packs:
            c = packs[i]
            for x in c["itens"]:
                if x not in out:
                    out.append(x)
            abertos.append((c.get("nome") or c.get("titulo"), i, len(c["itens"])))
        elif i not in out:
            out.append(i)
    return out, abertos


def novo(nome, ini=None, branch="42.21"):
    """Cria um modpack. Com o .ini do servidor, ja importa Mods= e WorkshopItems=."""
    s = slug(nome)
    d = os.path.join(PACKS, s)
    if os.path.exists(os.path.join(d, "modpack.json")):
        return False, ["Ja existe um modpack com esse nome (%s)." % s], None
    mods, itens, msgs = [], [], []
    if ini:
        mods, itens = ler_ini_listas(ini)
        if mods is None:
            return False, ["Esse arquivo nao tem as linhas Mods= e WorkshopItems= (e o .ini do servidor?)."], None
        itens, abertos = expandir_pacotes(itens)
        for nome_pack, pub, n in abertos:
            msgs.append("O modpack '%s' (%s) estava no .ini: entraram os %d itens originais dele." % (nome_pack, pub, n))
    os.makedirs(d, exist_ok=True)
    cfg = {"nome": nome, "titulo": "%s - Modpack do servidor (B%s)" % (nome, branch), "branch": branch,
           "pasta": "Modpack_" + s, "mods": mods, "itens": itens, "separados": {}, "congelado": {}, "_dir": d}
    salvar(cfg)
    faltam = [i for i in itens if steam_pastas(i) is None]
    msgs.append("Modpack '%s' criado com %d mods de %d itens." % (nome, len(mods), len(itens)))
    if faltam:
        msgs.append("%d itens ainda nao estao baixados: inscreva-se neles na Steam antes de montar." % len(faltam))
    return True, msgs, s


def importar(caminho_json):
    """Traz um modpack de outra pasta/PC (o modpack.json dele; os arquivos ao lado vem junto)."""
    if not os.path.isfile(caminho_json) or os.path.basename(caminho_json) != "modpack.json":
        return False, ["Escolha o arquivo modpack.json do modpack (fica em packs/<nome>/)."], None
    try:
        cfg = json.load(open(caminho_json, encoding="utf-8"))
    except (OSError, ValueError) as e:
        return False, ["Arquivo invalido: %s" % e], None
    if "mods" not in cfg or "itens" not in cfg:
        return False, ["Esse arquivo nao e de um modpack deste programa."], None
    s = slug(os.path.basename(os.path.dirname(caminho_json)) or cfg.get("nome", "modpack"))
    d = os.path.join(PACKS, s)
    if os.path.abspath(os.path.dirname(caminho_json)) == os.path.abspath(d):
        return False, ["Esse modpack ja esta aqui."], s
    if os.path.exists(os.path.join(d, "modpack.json")):
        return False, ["Ja existe um modpack chamado '%s' aqui. Exclua ou renomeie antes." % s], None
    shutil.copytree(os.path.dirname(caminho_json), d, dirs_exist_ok=True)
    return True, ["Modpack '%s' importado (%d mods). Se a pasta do pacote nao existir neste PC, use 'Montar pacote'." % (
        cfg.get("nome", s), len(cfg["mods"]))], s


def configurar(cfg, nome=None, titulo=None, branch=None):
    if nome:
        cfg["nome"] = nome
    if titulo:
        cfg["titulo"] = titulo
    if branch:
        cfg["branch"] = branch
    salvar(cfg)
    return True, ["Modpack configurado."]


def excluir(cfg):
    """Apaga so a lista do modpack (a pasta de publicacao na Workshop fica)."""
    shutil.rmtree(cfg["_dir"])
    return True, ["Lista do modpack apagada. A pasta de publicacao continua em %s." % destino(cfg)]


def destino(cfg):
    return os.path.join(PUBLICAR, cfg["pasta"])


def pack_mods(cfg):
    return os.path.join(destino(cfg), "Contents", "mods")


def pacote_id(cfg):
    """Id do pacote na Workshop. Vem do workshop.txt (o jogo grava ao publicar) e fica guardado tambem no
    modpack.json, para nao se perder se a pasta do pacote for apagada (senao o jogo criaria um item NOVO)."""
    wt = os.path.join(destino(cfg), "workshop.txt")
    achado = None
    if os.path.exists(wt):
        m = re.search(r"^id=(\d+)", open(wt, encoding="utf-8").read(), re.M)
        achado = m.group(1) if m else None
    if achado and cfg.get("id_publicado") != achado:
        cfg["id_publicado"] = achado
        if cfg.get("_dir"):
            salvar(cfg)
    return achado or cfg.get("id_publicado")


def pastas_congeladas_faltando(cfg):
    """Pastas que o modpack.json diz que estao no pacote, mas sumiram da pasta (pasta do pacote apagada)."""
    return [p for p in cfg.get("congelado", {}) if not os.path.isdir(os.path.join(pack_mods(cfg), p))]


def restaurar_do_publicado(cfg):
    """Recria a pasta do pacote (com as versoes congeladas) a partir do pacote PUBLICADO que a Steam baixou.
    Devolve (ok, mensagens)."""
    pub = pacote_id(cfg)
    if not pub:
        return False, ["Este modpack nao tem id publicado: nao ha de onde restaurar."]
    origem = pasta_do_item(pub)
    if not origem:
        return False, ["O pacote publicado (%s) ainda nao esta baixado neste PC. Inscreva-se nele na Steam "
                       "(ou baixe no automatico), espere terminar e tente de novo." % pub]
    pmods = pack_mods(cfg)
    os.makedirs(pmods, exist_ok=True)
    publicadas = sorted(d for d in os.listdir(origem) if os.path.isdir(os.path.join(origem, d)))
    restauradas, sobras = [], []
    for nome in publicadas:
        if nome not in cfg["congelado"]:
            sobras.append(nome)
            continue
        dst = os.path.join(pmods, nome)
        if not os.path.isdir(dst):
            copiar(os.path.join(origem, nome), dst)
            restauradas.append(nome)
    faltam = pastas_congeladas_faltando(cfg)
    nomes = {n: {"item": d["item"], "nome": d["nome"], "ids": d["ids"]} for n, d in cfg["congelado"].items()}
    escrever_workshop_txt(cfg, nomes)
    prev = os.path.join(destino(cfg), "preview.png")
    if not os.path.exists(prev):
        preview(prev, cfg.get("nome", "Modpack"), cfg["branch"])
    msgs = ["Restauradas %d pastas do pacote publicado (%s) em %s." % (len(restauradas), pub, pmods),
            "workshop.txt recriado com o id %s (publicar de novo ATUALIZA o mesmo item)." % pub]
    if faltam:
        msgs.append("ATENCAO: %d pastas da ultima montagem nao estao no publicado (a ultima montagem nao foi "
                    "publicada?): %s. Elas entram de novo no proximo 'Montar pacote', com a versao baixada agora."
                    % (len(faltam), ", ".join(faltam[:10])))
        for n in faltam:
            cfg["congelado"].pop(n, None)
        salvar(cfg)
    if sobras:
        msgs.append("O publicado tem %d pastas que nao estao na lista (ignoradas): %s" % (len(sobras), ", ".join(sobras[:10])))
    return True, msgs


def nome_do_item(cfg, item):
    for d in cfg["congelado"].values():
        if d["item"] == item:
            return d["nome"]
    sp = steam_pastas(item)
    if sp:
        return sp[0]["nome"]
    return "(nao baixado)"


# Dependencias -------------------------------------------------------------------------

def indice_baixados():
    """id do mod -> [itens baixados que tem esse mod]."""
    idx = {}
    nossos = ids_publicados()  # um modpack publicado tem todos os mods dentro: nunca e "fonte" de dependencia
    for item in itens_baixados():
        if item in nossos:
            continue
        for p in steam_pastas(item) or []:
            for i in p["ids"]:
                idx.setdefault(i, []).append(item)
    return idx


CACHE_REQ = os.path.join(DADOS, "cache_dependencias.json")
_cache_req = None


def _cache_requeridos():
    global _cache_req
    if _cache_req is None:
        try:
            _cache_req = json.load(open(CACHE_REQ, encoding="utf-8"))
        except (OSError, ValueError):
            _cache_req = {}
    return _cache_req


def requeridos_na_steam(item, timeout=8, tentativas=3):
    """Itens que a pagina do mod na Steam lista em "Itens necessarios".
    Devolve a lista, ou None se nao conseguiu consultar (sem internet, ou a Steam limitando: 429).
    Guarda a resposta por 1 dia (evita o bloqueio de "muitas consultas")."""
    cache = _cache_requeridos()
    c = cache.get(item)
    if c and time.time() - c.get("quando", 0) < 86400:
        return list(c["itens"])
    url = "https://steamcommunity.com/sharedfiles/filedetails/?id=%s" % item
    t = None
    for n in range(tentativas):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            t = urllib.request.urlopen(req, timeout=timeout).read().decode("utf-8", "ignore")
            break
        except urllib.error.HTTPError as e:
            if e.code == 429 and n < tentativas - 1:
                time.sleep(3 * (n + 1))  # a Steam pede para esperar: tenta de novo
                continue
            return None
        except Exception:
            return None
    if t is None:
        return None
    itens = _ler_requeridos(t, item)
    cache[item] = {"itens": itens, "quando": int(time.time())}
    try:
        with open(CACHE_REQ, "w", encoding="utf-8") as f:
            json.dump(cache, f)
    except OSError:
        pass
    return itens


def _ler_requeridos(t, item):
    m = re.search(r'id="RequiredItems"(.*?)</div>\s*</div>\s*</div>', t, re.S) or \
        re.search(r'class="requiredItemsContainer"(.*?)</div>\s*</div>', t, re.S)
    if not m:
        return []
    return [i for i in dict.fromkeys(re.findall(r"filedetails/\?id=(\d+)", m.group(1))) if i != item]


def pedidos_de(item, mods):
    """O que os mods escolhidos do item exigem (require= da B42)."""
    req = []
    for p in steam_pastas(item) or []:
        if set(p["ids"]) & set(mods):
            req += [r for r in p["req"] if r not in req]
    return req


def colocar_antes(cfg, mod, antes_de):
    """Poe "mod" no Mods= antes de "antes_de" (dependencia carrega primeiro)."""
    if mod in cfg["mods"]:
        return False
    i = cfg["mods"].index(antes_de) if antes_de in cfg["mods"] else len(cfg["mods"])
    cfg["mods"].insert(i, mod)
    return True


def resolver_dependencias(cfg, item, mods, idx=None):
    """Adiciona (recursivo) os mods exigidos pelos "mods" do item. Devolve (mensagens,
    ids que nao achei em nenhum mod baixado)."""
    idx = idx if idx is not None else indice_baixados()
    msgs, faltando = [], []
    fila = [(item, m) for m in mods]
    vistos = set()
    while fila:
        it, mod = fila.pop(0)
        if (it, mod) in vistos:
            continue
        vistos.add((it, mod))
        for r in pedidos_de(it, [mod]):
            fornecedores = sorted(idx.get(r, []), key=lambda x: (x not in cfg["itens"], x))
            if not fornecedores:
                if r not in cfg["mods"] and r not in faltando:
                    faltando.append(r)
                continue
            prov = fornecedores[0]
            if prov not in cfg["itens"]:
                # entra antes do item que precisa dele
                pos = cfg["itens"].index(it) if it in cfg["itens"] else len(cfg["itens"])
                cfg["itens"].insert(pos, prov)
                msgs.append("Dependencia: item %s (%s) adicionado, porque %s precisa dele." % (prov, nome_do_item(cfg, prov), mod))
            if colocar_antes(cfg, r, mod):
                msgs.append("Dependencia: mod '%s' colocado no Mods= antes de '%s'." % (r, mod))
            fila.append((prov, r))
    return msgs, faltando


def ordenar_por_dependencias(cfg):
    """Garante que cada dependencia venha ANTES de quem precisa dela no Mods= (mexe o minimo:
    move a dependencia para logo antes do primeiro mod que a exige). Devolve mensagens."""
    exige = {}
    pm = pack_mods(cfg)
    fontes = [os.path.join(pm, p) for p in cfg["congelado"] if os.path.isdir(os.path.join(pm, p))]
    for item in cfg["itens"]:
        if item in cfg["separados"]:
            fontes += [p["origem"] for p in steam_pastas(item) or []]
    for f in fontes:
        inf = info_pasta(f)
        for i in inf["ids"]:
            exige.setdefault(i, set()).update(inf["req"])
    msgs = []
    for _ in range(len(cfg["mods"]) * 2):  # limite contra dependencia circular
        mudou = False
        pos = {m: n for n, m in enumerate(cfg["mods"])}
        for m in list(cfg["mods"]):
            for r in sorted(exige.get(m, ())):
                if r in pos and pos[r] > pos[m]:
                    cfg["mods"].remove(r)
                    cfg["mods"].insert(cfg["mods"].index(m), r)
                    msgs.append("Ordem corrigida: '%s' agora vem antes de '%s' (dependencia)." % (r, m))
                    mudou = True
                    break
            if mudou:
                break
        if not mudou:
            break
    return msgs


# Operacoes ---------------------------------------------------------------------------

def adicionar(cfg, texto, mods=None):
    """Devolve (ok, mensagens, opcoes). opcoes = lista de (id, nome) quando o item tem
    mais de um mod e "mods" nao foi informado (escolha e chame de novo)."""
    item = item_id(texto)
    if not item:
        return False, ["Nao entendi o id/link: %s" % texto], None
    sp = steam_pastas(item)
    if sp is None:
        return False, ["O item %s ainda nao esta baixado. Inscreva-se nele na Steam, espere baixar e tente de novo." % item], None
    disponiveis = [(i, p["nome"]) for p in sp for i in p["ids"]]
    if not disponiveis:
        return False, ["O item %s nao tem nenhum mod (mod.info) dentro." % item], None
    if mods is None and item in cfg["itens"]:  # ja na lista: reaproveita os mods ja escolhidos
        mods = [i for i, _ in disponiveis if i in cfg["mods"]] or None
    if mods is None:
        if len(disponiveis) > 1:
            return False, ["O item %s tem %d mods; escolha quais ativar." % (item, len(disponiveis))], disponiveis
        mods = [disponiveis[0][0]]
    validos = {i for i, _ in disponiveis}
    for m in mods:
        if m not in validos:
            return False, ["O mod %s nao existe no item %s." % (m, item)], disponiveis
    msgs = []
    if item not in cfg["itens"]:
        cfg["itens"].append(item)
    for m in mods:
        if m not in cfg["mods"]:
            cfg["mods"].append(m)
            msgs.append("Mod %s adicionado ao Mods=." % m)
    cfg["_pendentes"] = []
    antes = set(cfg["itens"])
    dm, faltando = resolver_dependencias(cfg, item, mods)
    msgs += dm
    if faltando:
        # consulta a pagina do mod E das dependencias achadas no caminho (A precisa de B, que precisa de C:
        # o C pode estar so na pagina do B)
        cadeia = [item] + [i for i in cfg["itens"] if i not in antes]
        baixar, falhou = [], False
        for c in cadeia:
            req = requeridos_na_steam(c)
            if req is None:
                falhou = True
                continue
            for i in req:
                if i not in baixar and i not in cadeia and steam_pastas(i) is None:
                    baixar.append(i)
        if falhou and not baixar:
            msgs.append("ATENCAO: nao consegui consultar a pagina na Steam (sem internet ou a Steam pedindo para "
                        "esperar). Tente adicionar de novo daqui a alguns minutos, ou adicione a dependencia pelo ID.")
        cfg["_pendentes"] = baixar
        msgs.append("ATENCAO: faltam as dependencias %s, que nao estao baixadas no PC." % ", ".join(faltando))
        if baixar:
            msgs.append("A pagina do mod na Steam pede estes itens: %s. Inscreva-se neles; quando baixarem, "
                        "adicione o mod de novo que as dependencias entram sozinhas." % ", ".join(baixar))
    salvar(cfg)
    msgs.append("Item %s (%s) na lista. Agora monte o pacote." % (item, sp[0]["nome"]))
    return True, msgs, None


def remover(cfg, texto):
    item = item_id(texto)
    if item not in cfg["itens"]:
        return False, ["O item %s nao esta na lista." % item]
    ids = set()
    for d in cfg["congelado"].values():
        if d["item"] == item:
            ids.update(d["ids"])
    for p in steam_pastas(item) or []:
        ids.update(p["ids"])
    ids.update(cfg.get("ids_separados", {}).get(item, []))
    outros = set()
    for d in cfg["congelado"].values():
        if d["item"] != item:
            outros.update(d["ids"])
    cfg["itens"].remove(item)
    cfg["separados"].pop(item, None)
    tirados = [m for m in cfg["mods"] if m in ids and m not in outros]
    cfg["mods"] = [m for m in cfg["mods"] if m not in tirados]
    salvar(cfg)
    return True, ["Item %s removido da lista; mods tirados do Mods=: %s. Monte o pacote para aplicar." % (item, ", ".join(tirados) or "nenhum")]


def separar(cfg, texto, motivo):
    item = item_id(texto)
    if item not in cfg["itens"]:
        return False, ["O item %s nao esta na lista." % item]
    cfg["separados"][item] = motivo or "fora do pacote"
    salvar(cfg)
    return True, ["Item %s fica fora do pacote (vem da Workshop original). Monte o pacote para aplicar." % item]


def juntar(cfg, texto):
    item = item_id(texto)
    if cfg["separados"].pop(item, None) is None:
        return False, ["O item %s nao estava separado." % item]
    salvar(cfg)
    return True, ["Item %s volta para dentro do pacote. Monte o pacote para aplicar." % item]


def status(cfg):
    """Linhas (item, nome, mods ativos, situacao) na ordem da lista."""
    ver = versoes()
    out = []
    pmods = pack_mods(cfg)
    aviso_apagada = ("PASTA DO PACOTE APAGADA: use 'Restaurar do publicado'" if pacote_id(cfg)
                     else "PASTA DO PACOTE APAGADA: monte de novo ('Atualizar TODOS e montar')")
    for item in cfg["itens"]:
        congel_todos = [(p, d) for p, d in cfg["congelado"].items() if d["item"] == item]
        congel = [d for p, d in congel_todos if os.path.isdir(os.path.join(pmods, p))]
        apagado = bool(congel_todos) and not congel
        sp = steam_pastas(item)
        ids = sorted({i for d in congel for i in d["ids"]} | {i for p in sp or [] for i in p["ids"]}
                     | set(cfg.get("ids_separados", {}).get(item, [])))
        ativos = [m for m in cfg["mods"] if m in ids]
        if item in cfg["separados"]:
            sit = "separado: " + cfg["separados"][item]
            if sp is None:
                sit += " (NAO BAIXADO)"
        elif apagado:
            sit = aviso_apagada
        elif not ativos and (congel or sp is not None):
            sit = "nenhum mod dele no Mods= (baixado a toa)"
        elif congel:
            v = congel[0].get("versao")
            if sp is not None and v and ver.get(item) and ver[item] != v:
                sit = "no pacote - TEM VERSAO NOVA baixada (use atualizar)"
            else:
                sit = "no pacote (congelado)"
        elif sp is None:
            sit = "NAO BAIXADO: inscreva-se na Steam"
        else:
            sit = "novo: entra no proximo 'montar'"
        out.append((item, nome_do_item(cfg, item), ", ".join(ativos), sit))
    return out


def eh_b42(pastas):
    """O item tem versao para a B42 (pasta 42*/common com mod.info)?"""
    for p in pastas:
        for sub in os.listdir(p["origem"]):
            sp = os.path.join(p["origem"], sub)
            if os.path.isdir(sp) and (sub == "common" or re.fullmatch(r"42(\.\d+)*", sub)) \
                    and os.path.exists(os.path.join(sp, "mod.info")):
                return True
    return False


def baixados():
    """Todos os itens do PZ baixados pela Steam nesta maquina:
    [{item, nome, ids, b42, versao}] em ordem de nome."""
    ver = versoes()
    out = []
    nossos = ids_publicados()
    for item in itens_baixados():
        if item in nossos:
            continue  # os nossos modpacks publicados nao aparecem como "mod baixado"
        sp = steam_pastas(item)
        if not sp:
            continue
        out.append({"item": item, "nome": sp[0]["nome"], "ids": sorted({i for p in sp for i in p["ids"]}),
                    "b42": eh_b42(sp), "versao": ver.get(item)})
    out.sort(key=lambda d: d["nome"].lower())
    return out


def situacao_no_pack(cfg, item):
    if item not in cfg["itens"]:
        return ""
    if item in cfg["separados"]:
        return "separado"
    if any(d["item"] == item for d in cfg["congelado"].values()):
        return "no modpack"
    return "na lista (falta montar)"


def com_versao_nova(cfg):
    """Itens do pacote que a Steam ja baixou numa versao mais nova que a congelada."""
    ver = versoes()
    out = []
    for item in cfg["itens"]:
        if item in cfg["separados"]:
            continue
        congel = [d for d in cfg["congelado"].values() if d["item"] == item]
        if congel and congel[0].get("versao") and ver.get(item) and ver[item] != congel[0]["versao"] \
                and steam_pastas(item) is not None:
            out.append(item)
    return out


def faltando(cfg):
    """Itens da lista que nao estao baixados nem congelados (precisam de inscricao)."""
    congelados = {d["item"] for d in cfg["congelado"].values()}
    return [i for i in cfg["itens"] if steam_pastas(i) is None and i not in congelados]


def copiar(src, dst):
    for raiz, _, arquivos in os.walk(src):
        alvo = os.path.join(dst, os.path.relpath(raiz, src))
        os.makedirs(alvo, exist_ok=True)
        for a in arquivos:
            s, d = os.path.join(raiz, a), os.path.join(alvo, a)
            try:
                os.link(s, d)  # mesmo disco: sem espaco extra, e a Steam nao mexe nesta copia
            except OSError:
                shutil.copy2(s, d)


def preview(path, nome, branch):
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:  # sem Pillow (comum no Windows): usa a imagem padrao que vem junto
        shutil.copy2(os.path.join(RECURSOS, "preview_padrao.png"), path)
        return
    img = Image.new("RGB", (256, 256), (24, 28, 24))
    d = ImageDraw.Draw(img)
    d.rectangle([8, 8, 247, 247], outline=(150, 30, 30), width=4)
    try:
        f1, f2 = ImageFont.truetype("DejaVuSans-Bold.ttf", 34), ImageFont.truetype("DejaVuSans.ttf", 20)
    except OSError:
        f1 = f2 = ImageFont.load_default()
    titulo = nome if len(nome) <= 12 else nome[:11] + "."
    d.text((128, 92), titulo, fill=(230, 230, 220), font=f1, anchor="mm")
    d.text((128, 140), "Modpack do servidor", fill=(200, 200, 190), font=f2, anchor="mm")
    d.text((128, 172), "Build %s" % branch, fill=(170, 60, 60), font=f2, anchor="mm")
    img.save(path, "PNG", optimize=True)


def montar(cfg, atualizar=(), simular=False):
    """Monta o pacote. atualizar: ids de itens para pegar a versao baixada agora, ou "tudo".
    Devolve (ok, mensagens)."""
    msgs, problemas = [], list(pastas_ok())
    if problemas:
        return False, ["PROBLEMA: " + p for p in problemas]
    ver = versoes()
    tudo = atualizar == "tudo"
    atualizar = set() if tudo else set(atualizar or ())
    ordem = {it: n for n, it in enumerate(cfg["itens"])}
    pmods = pack_mods(cfg)
    apagadas = pastas_congeladas_faltando(cfg)
    if apagadas and not tudo and not simular:
        return False, ["PROBLEMA: %d pastas do pacote foram apagadas (%s...). Montar agora trocaria as versoes "
                       "congeladas pelas baixadas hoje. Use 'Restaurar do publicado' primeiro (ou 'Atualizar TODOS "
                       "e montar', se quiser mesmo as versoes novas)." % (len(apagadas), ", ".join(apagadas[:5]))]

    # 1) Candidatos: pastas congeladas (do proprio pacote) ou baixadas (Steam).
    cands, ids_separados = [], set()
    for item in cfg["itens"]:
        if item in cfg["separados"]:
            sp = steam_pastas(item)
            if sp is not None:  # guarda os ids para quando o original nao estiver baixado
                cfg.setdefault("ids_separados", {})[item] = sorted({i for p in sp for i in p["ids"]})
            ids_separados.update(cfg.get("ids_separados", {}).get(item, []))
            continue
        congel = [(pasta, d) for pasta, d in cfg["congelado"].items()
                  if d["item"] == item and os.path.isdir(os.path.join(pmods, pasta))]
        quer_novo = tudo or item in atualizar or not congel
        sp = steam_pastas(item) if quer_novo else None
        if quer_novo and sp is not None:
            for p in sp:
                p.update({"congelado": False, "versao": ver.get(item)})
                cands.append(p)
            if congel:
                msgs.append("Atualizando %s com a versao baixada agora." % congel[0][1]["nome"])
        elif congel:
            if quer_novo:
                msgs.append("Item %s nao esta baixado: mantida a versao congelada." % item)
            for pasta, d in congel:
                c = info_pasta(os.path.join(pmods, pasta))
                c.update({"item": item, "origem": os.path.join(pmods, pasta), "folder": pasta,
                          "congelado": True, "versao": d.get("versao"), "nome": d["nome"]})
                cands.append(c)
        else:
            problemas.append("Item %s nao esta baixado e ainda nao esta no pacote: inscreva-se nele na Steam." % item)

    # 2) Ids necessarios: Mods= + dependencias da B42 (recursivo).
    por_id = {}
    for c in cands:
        for i in c["ids"]:
            por_id.setdefault(i, []).append(c)
    preciso, fila = set(cfg["mods"]), list(cfg["mods"])
    while fila:
        quem = fila.pop()
        for c in por_id.get(quem, []):
            for r in c["req"]:
                if r not in cfg["mods"] and r in por_id:  # dependencia fora do Mods=: entra antes de quem pede
                    colocar_antes(cfg, r, quem)
                    msgs.append("Dependencia '%s' (exigida por '%s') colocada no Mods=." % (r, quem))
                if r not in preciso:
                    preciso.add(r)
                    fila.append(r)

    # 3) Uma pasta por id (a do item que vem primeiro na lista).
    escolhidas, cobertos = [], set(ids_separados)
    for i in sorted(preciso, key=lambda i: min((ordem[c["item"]] for c in por_id.get(i, [])), default=1e9)):
        if i in cobertos or i not in por_id:
            continue
        c = sorted(por_id[i], key=lambda c: ordem[c["item"]])[0]
        if c not in escolhidas:
            escolhidas.append(c)
        cobertos.update(c["ids"])
    for i in sorted(preciso - cobertos):
        problemas.append("O mod '%s' esta no Mods= (ou e exigido) mas nao vem de nenhum item da lista." % i)

    # 4) Nome da pasta no pacote (congeladas mantem o nome; repetidos ganham o id do item).
    nomes = {}
    for c in [c for c in escolhidas if c["congelado"]] + [c for c in escolhidas if not c["congelado"]]:
        nome = c["folder"]
        if nome in nomes:
            nome = "%s (%s)" % (nome, c["item"])
        nomes[nome] = c

    # 5) Regras do uploader do jogo.
    tamanho = 0
    for nome, c in nomes.items():
        if not c["tem_info"]:
            problemas.append("Sem mod.info: %s" % c["origem"])
        for raiz, _, arquivos in os.walk(c["origem"]):
            for x in arquivos:
                tamanho += os.path.getsize(os.path.join(raiz, x))
                if x.lower().endswith(PROIBIDOS) and x != "pyramid.zip":
                    problemas.append("Arquivo proibido pelo uploader: %s" % os.path.join(raiz, x))
    if not nomes:
        problemas.append("Nenhum mod para colocar no pacote.")

    novos = [n for n, c in nomes.items() if not c["congelado"]]
    sair = [p for p in (os.listdir(pmods) if os.path.isdir(pmods) else []) if p not in nomes]
    msgs.append("%d mods no pacote (%.2f GB): %d novos/atualizados, %d congelados, %d saem." %
                (len(nomes), tamanho / 1e9, len(novos), len(nomes) - len(novos), len(sair)))
    if problemas:
        return False, msgs + ["PROBLEMA: " + p for p in problemas]
    if simular:
        return True, msgs + ["(simulacao: nada foi alterado)"]

    # 6) Aplica.
    os.makedirs(pmods, exist_ok=True)
    for p in sair:
        shutil.rmtree(os.path.join(pmods, p))
    for nome in novos:
        dst = os.path.join(pmods, nome)
        if os.path.isdir(dst):
            shutil.rmtree(dst)
        copiar(nomes[nome]["origem"], dst)
    cfg["congelado"] = {nome: {"item": c["item"], "ids": c["ids"], "nome": c["nome"], "versao": c.get("versao")}
                        for nome, c in nomes.items()}
    cfg["montado"] = {"quando": int(time.time()), "bytes": tamanho, "mods": len(nomes)}
    msgs += ordenar_por_dependencias(cfg)
    salvar(cfg)
    prev = os.path.join(destino(cfg), "preview.png")
    if not os.path.exists(prev):
        preview(prev, cfg.get("nome", "Modpack"), cfg["branch"])
    escrever_workshop_txt(cfg, nomes)
    with open(os.path.join(cfg["_dir"], "conteudo_do_pacote.txt"), "w", encoding="utf-8") as f:
        f.write("# pasta no pacote | item original | ids | versao congelada (timeupdated)\n")
        for nome, c in nomes.items():
            f.write("%s | %s | %s | %s\n" % (nome, c["item"], ",".join(c["ids"]), c.get("versao") or "?"))
    linhas(cfg)
    msgs.append("Pacote montado em %s" % destino(cfg))
    msgs.append("Agora publique no jogo: Workshop > Criar e atualizar itens > %s." % cfg["pasta"])
    if not pacote_id(cfg):
        msgs.append("(1a publicacao: depois de publicar, gere o .ini; o WorkshopItems= ja sai com o id.)")
    return True, msgs


LIMITE_STEAM = 8000  # bytes (UTF-8) da descricao na Steam; passou disso = result=8 (InvalidParam)


def bytes_extras_do_jogo(cfg):
    """O jogo (SteamWorkshopItem.getSubmitDescription) acrescenta a descricao:
    "Workshop ID: <id>" e uma linha "Mod ID: <id>" por mod.info (e "Map Folder:" por mapa).
    Conta por cima (cada mod.info das pastas de versao/common), para nunca passar do limite."""
    total = len("\n\nWorkshop ID: 0000000000".encode("utf-8"))
    pm = pack_mods(cfg)
    if not os.path.isdir(pm):
        return total
    for mod in os.listdir(pm):
        md = os.path.join(pm, mod)
        if not os.path.isdir(md):
            continue
        for sub in os.listdir(md):
            info = os.path.join(md, sub, "mod.info")
            if os.path.exists(info):
                i = ler_info(info)["id"] or ""
                total += len(("\nMod ID: " + i).encode("utf-8"))
            maps = os.path.join(md, sub, "media", "maps")
            if os.path.isdir(maps):
                for m in os.listdir(maps):
                    total += len(("\nMap Folder: " + m).encode("utf-8"))
    return total


def descricao(cfg, nomes, orcamento):
    """Descricao que cabe no orcamento (bytes). Tenta do mais completo ao mais curto."""
    topo = [
        "[h1]Modpack do servidor %s[/h1]" % cfg.get("nome", ""),
        "Pacote NAO LISTADO, so para os jogadores do servidor, com as versoes dos mods congeladas para o "
        "Project Zomboid [b]Build %s[/b] (Steam > Propriedades > Betas > %s)." % (cfg["branch"], cfg["branch"]),
        "Nao inscreva os mods originais junto com este pacote: os IDs sao os mesmos e o jogo pode carregar a versao errada.",
        "",
        "[h2]Creditos - todos os mods pertencem aos seus autores[/h2]",
    ]
    fim = "Se voce e autor de algum destes mods e quer que ele saia do pacote, fale com a gente que removemos."
    itens, vistos = [], set()
    for c in nomes.values():
        if c["item"] not in vistos:
            vistos.add(c["item"])
            itens.append((c["item"], c["nome"]))
    url = "https://steamcommunity.com/sharedfiles/filedetails/?id=%s"
    tentativas = [
        topo + ["Apoie os autores na pagina original de cada mod:", "[list]"]
        + ["[*][url=%s]%s[/url]" % (url % i, n) for i, n in itens] + ["[/list]", fim],
        topo + ["Mods originais (nome e ID na Workshop):", "[list]"]
        + ["[*]%s (%s)" % (n, i) for i, n in itens] + ["[/list]", fim],
        topo + ["Mods originais: " + "; ".join("%s (%s)" % (n[:30], i) for i, n in itens), fim],
        topo + ["IDs dos mods originais na Workshop: " + ", ".join(i for i, _ in itens), fim],
    ]
    for t in tentativas:
        if len("\n".join(t).encode("utf-8")) <= orcamento:
            return t
    return topo[:3]


def escrever_workshop_txt(cfg, nomes):
    wt = os.path.join(destino(cfg), "workshop.txt")
    pub = pacote_id(cfg)
    orcamento = LIMITE_STEAM - bytes_extras_do_jogo(cfg) - 200  # folga
    desc = descricao(cfg, nomes, orcamento)
    linhas_wt = ["version=1"] + (["id=" + pub] if pub else []) + ["title=" + cfg["titulo"][:128]]
    linhas_wt += ["description=" + d for d in desc] + ["tags=Build 42;Multiplayer", "visibility=unlisted"]
    with open(wt, "w", encoding="utf-8") as f:
        f.write("\n".join(linhas_wt) + "\n")
    return len("\n".join(desc).encode("utf-8")), orcamento


def linhas(cfg):
    """Mods= e WorkshopItems= para o servidor (pacote + itens separados). Grava servidor_linhas.txt."""
    pub = pacote_id(cfg) or "<ID_DO_PACOTE>"
    itens = [pub] + [i for i in cfg["itens"] if i in cfg["separados"]]
    mods_l = "Mods=" + ";".join(cfg["mods"])
    items_l = "WorkshopItems=" + ";".join(itens)
    with open(os.path.join(cfg["_dir"], "servidor_linhas.txt"), "w", encoding="utf-8") as f:
        f.write(mods_l + "\n\n" + items_l + "\n")
    return mods_l, items_l


def gerar_ini(cfg, entrada, saida=None):
    """Copia o .ini do servidor trocando so Mods= e WorkshopItems=. Por padrao grava com o
    MESMO nome numa pasta "pronto" ao lado do original (nao precisa renomear para subir).
    Confere o resultado antes de terminar. Devolve (ok, mensagens)."""
    if not os.path.isfile(entrada):
        return False, ["Arquivo nao encontrado: %s" % entrada]
    texto = open(entrada, encoding="utf-8", errors="ignore").read()
    if not re.search(r"^Mods=", texto, re.M) or not re.search(r"^WorkshopItems=", texto, re.M):
        return False, ["Esse arquivo nao tem as linhas Mods= e WorkshopItems= (e o .ini do servidor?)."]
    if not cfg["mods"]:
        return False, ["O modpack nao tem nenhum mod na lista: adicione mods antes de gerar o .ini."]
    if not pacote_id(cfg):
        return False, ["O pacote ainda nao foi publicado (sem id da Workshop). Monte, publique no jogo e gere o .ini depois."]
    ordem = ordenar_por_dependencias(cfg)
    if ordem:
        salvar(cfg)
    mods_l, items_l = linhas(cfg)
    texto = re.sub(r"^Mods=.*$", lambda m: mods_l, texto, count=1, flags=re.M)
    texto = re.sub(r"^WorkshopItems=.*$", lambda m: items_l, texto, count=1, flags=re.M)
    if not saida:
        pasta = os.path.join(os.path.dirname(os.path.abspath(entrada)), "pronto")
        os.makedirs(pasta, exist_ok=True)
        saida = os.path.join(pasta, os.path.basename(entrada))
    if os.path.abspath(saida) == os.path.abspath(entrada):
        return False, ["Escolha outro lugar para o .ini pronto (nao sobrescrevo o original)."]
    with open(saida, "w", encoding="utf-8") as f:
        f.write(texto)
    cfg["ini_servidor"] = os.path.abspath(entrada)  # da proxima vez o .ini e atualizado sozinho
    cfg["ini_pronto"] = os.path.abspath(saida)
    salvar(cfg)
    msgs = ordem + ["Ini pronto: %s" % saida,
            "Suba ESSE arquivo (mesmo nome) em Zomboid/Server/ no lugar do atual, com o servidor DESLIGADO, e ligue de novo."]
    nome = os.path.splitext(os.path.basename(saida))[0]
    msgs.append("O nome do arquivo (%s) tem que ser igual ao -servername do servidor." % nome)
    problemas = [m for nivel, m in conferir_ini(cfg, saida) if nivel == "ERRO"]
    if problemas:
        return False, msgs + ["PROBLEMA no .ini gerado: " + p for p in problemas]
    return True, msgs + ["Conferido: Mods= com %d mods e WorkshopItems= certo." % len(cfg["mods"])]


# Procurar na Workshop (sem login e sem chave de API) -----------------------------------

BROWSE = "https://steamcommunity.com/workshop/browse/"
API_DETALHES = "https://api.steampowered.com/ISteamRemoteStorage/GetPublishedFileDetails/v1/"
ORDENS_BUSCA = [("Relevância", "textsearch"), ("Mais inscritos", "totaluniquesubscribers"),
                ("Em alta na semana", "trend"), ("Mais recentes", "mostrecent"),
                ("Atualizados há pouco", "lastupdated")]


def _baixar_texto(url, dados=None, timeout=20):
    req = urllib.request.Request(url, data=dados, headers={"User-Agent": "Mozilla/5.0 (ModpackServidor)",
                                                           "Accept-Language": "en"})
    return urllib.request.urlopen(req, timeout=timeout).read().decode("utf-8", "ignore")


def sem_bbcode(texto, limite=600):
    t = re.sub(r"\[/?[a-zA-Z0-9*]+(=[^\]]*)?\]", "", texto or "")
    t = re.sub(r"\s*\n\s*\n+", "\n", t).strip()
    return t if len(t) <= limite else t[:limite].rsplit(" ", 1)[0] + "..."


def detalhes_steam(ids, timeout=20):
    """{item: {...}} dos itens publicos do PZ (GetPublishedFileDetails, sem chave)."""
    import urllib.parse
    out = {}
    for n in range(0, len(ids), 100):
        lote = ids[n:n + 100]
        dados = {"itemcount": len(lote)}
        for k, x in enumerate(lote):
            dados["publishedfileids[%d]" % k] = x
        resp = json.loads(_baixar_texto(API_DETALHES, urllib.parse.urlencode(dados).encode(), timeout))
        for d in resp.get("response", {}).get("publishedfiledetails", []):
            if d.get("result") != 1 or str(d.get("consumer_app_id")) != APP_PZ:
                continue
            tags = [t.get("tag", "") for t in d.get("tags", [])]
            out[d["publishedfileid"]] = {
                "item": d["publishedfileid"], "titulo": d.get("title") or "?",
                "tamanho": int(d.get("file_size") or 0), "atualizado": int(d.get("time_updated") or 0),
                "inscritos": int(d.get("subscriptions") or 0), "tags": tags,
                "b42": "Build 42" in tags, "b41": "Build 41" in tags,
                "descricao": sem_bbcode(d.get("description")), "autor": "",
            }
    return out


def buscar_workshop(texto="", ordem="textsearch", pagina=1, so_b42=True):
    """Procura mods do PZ na Workshop. Devolve (resultados, total_paginas, total).
    Numero ou link de mod: devolve so ele. Sem internet: levanta OSError."""
    import html as H
    import urllib.parse
    texto = (texto or "").strip()
    if texto and (texto.isdigit() or "filedetails" in texto):
        it = item_id(texto)
        d = detalhes_steam([it]) if it else {}
        return list(d.values()), 1, len(d)
    if not texto and ordem == "textsearch":
        ordem = "totaluniquesubscribers"  # sem texto, "relevancia" nao existe: mostra os mais inscritos
    params = [("appid", APP_PZ), ("section", "readytouseitems"), ("numperpage", "30"), ("p", str(pagina)),
              ("browsesort", ordem), ("actualsort", ordem)]
    if texto:
        params.append(("searchtext", texto))
    if ordem == "trend":
        params.append(("days", "7"))  # em alta nos ultimos 7 dias
    if so_b42:
        params.append(("requiredtags[]", "Build 42"))
    pagina_html = _baixar_texto(BROWSE + "?" + urllib.parse.urlencode(params))
    ids = list(dict.fromkeys(re.findall(r'\\"publishedfileid\\":\\"(\d+)\\"', pagina_html)))
    if not ids:  # formato antigo da pagina
        ids = list(dict.fromkeys(re.findall(r'data-publishedfileid="(\d+)"', pagina_html)))
    m = re.search(r'\\"total_pages\\":(\d+)', pagina_html)
    total_pag = int(m.group(1)) if m else (pagina + 1 if len(ids) >= 30 else pagina)
    m = re.search(r'\\"total_count\\":(\d+)', pagina_html)
    total = int(m.group(1)) if m else len(ids)
    autores = {}
    for m in re.finditer(r'filedetails/\?id=(\d+)"[^>]*>[^<]+</a>', pagina_html):
        a = re.search(r'myworkshopfiles/\?appid=\d+"[^>]*>(?:By )?([^<]+)</a>', pagina_html[m.end():m.end() + 800])
        if a:
            autores.setdefault(m.group(1), H.unescape(a.group(1)).strip())
    det = detalhes_steam(ids) if ids else {}
    res = []
    for i in ids:
        if i in det:
            det[i]["autor"] = autores.get(i, "")
            res.append(det[i])
    return res, total_pag, total


# Sem Steam (-nosteam) -------------------------------------------------------------------
# Num servidor iniciado com -nosteam a Workshop nao existe: o servidor e cada jogador precisam
# ter os mesmos arquivos em <pasta Zomboid>/mods/. O Mods= continua dizendo o que liga.
# O .zip exportado tem a pasta mods/ na raiz: extrair dentro da pasta Zomboid ja deixa no lugar.

MANIFESTO_NOSTEAM = "modpack_nosteam.json"
REGISTRO_NOSTEAM = "ModpackServidor_nosteam"  # <Zomboid>/<isto>/<pack>.json: o que foi instalado
JA_COMPRIMIDOS = (".png", ".jpg", ".jpeg", ".ogg", ".mp3", ".bank", ".zip", ".pack", ".gz", ".7z")


def pasta_zomboid_jogador():
    """Pasta Zomboid deste PC (onde o jogo le mods/). A escolhida em 'Pastas...' vence."""
    loc = local()
    z = loc.get("zomboid_nosteam") or loc.get("zomboid") or detectar_zomboid(WORKSHOP)
    if z:
        return z
    base = os.environ.get("USERPROFILE") if os.name == "nt" else None
    return os.path.join(base or os.path.expanduser("~"), "Zomboid")


def pastas_de_desenvolvimento(ids, ignorar=None):
    """Pastas de mod em <Zomboid>/Workshop/*/Contents/mods/ que tem algum desses ids (mods nossos
    que nao estao baixados pela Steam neste PC)."""
    out = []
    for md in sorted(glob.glob(os.path.join(glob.escape(PUBLICAR), "*", "Contents", "mods", "*"))):
        if not os.path.isdir(md) or (ignorar and os.path.abspath(md).startswith(os.path.abspath(ignorar) + os.sep)):
            continue
        d = info_pasta(md)
        if set(d["ids"]) & set(ids):
            d.update({"origem": md, "folder": os.path.basename(md)})
            out.append(d)
    return out


def pastas_nosteam(cfg):
    """O que vai no .zip: as pastas do pacote montado + as dos itens separados.
    Devolve (lista de {nome, origem, item, ids, req}, problemas, avisos)."""
    problemas, avisos, out = [], [], []
    pmods = pack_mods(cfg)
    dentro = [i for i in cfg["itens"] if i not in cfg["separados"]]
    if dentro and (not cfg.get("congelado") or not os.path.isdir(pmods)):
        return [], ["O pacote ainda nao foi montado: clique em 'Montar pacote' antes."], []
    usados = set()
    for pasta, d in cfg.get("congelado", {}).items():
        origem = os.path.join(pmods, pasta)
        if not os.path.isdir(origem):
            problemas.append("A pasta '%s' sumiu do pacote: monte de novo." % pasta)
            continue
        inf = info_pasta(origem)
        out.append({"nome": pasta, "origem": origem, "item": d["item"], "ids": inf["ids"], "req": inf["req"]})
        usados.add(pasta)
    ligados = set(cfg["mods"])
    for item in [i for i in cfg["itens"] if i in cfg["separados"]]:
        sp, de = steam_pastas(item), "Steam"
        if sp is None:
            ids = cfg.get("ids_separados", {}).get(item, [])
            sp, de = pastas_de_desenvolvimento(ids, destino(cfg)), "desenvolvimento"
            if sp:
                avisos.append("'%s' nao esta baixado pela Steam: usei a pasta de desenvolvimento %s. "
                              "Confira se e a MESMA versao publicada (senao da kick por checksum)."
                              % (nome_do_item(cfg, item), sp[0]["origem"]))
        if not sp:
            problemas.append("Item separado %s nao esta baixado neste PC: inscreva-se nele na Steam." % item)
            continue
        for p in sp:
            if not set(p["ids"]) & ligados:
                continue  # variante que o servidor nao liga
            nome = p["folder"] if p["folder"] not in usados else "%s (%s)" % (p["folder"], item)
            usados.add(nome)
            out.append({"nome": nome, "origem": p["origem"], "item": item, "ids": p["ids"], "req": p["req"]})
    tem = {i for p in out for i in p["ids"]}
    for m in cfg["mods"]:
        if m not in tem:
            problemas.append("O mod '%s' do Mods= nao vem de nenhuma pasta do .zip." % m)
    for p in out:
        for r in p["req"]:
            if r not in tem:
                problemas.append("'%s' precisa de '%s', que nao vem no .zip." % (p["nome"], r))
    return out, problemas, avisos


def leia_me_nosteam(cfg, branch):
    return """MODPACK %(t)s - JOGAR SEM STEAM (-nosteam)

Versao do jogo: %(b)s (tem que ser a mesma do servidor).

INSTALAR (jogador)
  Jeito facil: abra o programa ModpackServidor > pagina "Sem Steam (nosteam)" > "Instalar .zip do modpack...".
  Na mao: extraia este .zip DENTRO da pasta Zomboid do seu usuario (a pasta mods/ do zip
  vai parar em Zomboid/mods/). A pasta Zomboid fica em:
    Windows: C:\\Users\\<voce>\\Zomboid
    Linux:   ~/Zomboid   (Steam em Flatpak: ~/.var/app/com.valvesoftware.Steam/Zomboid)

ABRIR O JOGO SEM STEAM
  Versao da Steam: Biblioteca > Project Zomboid > Propriedades > Opcoes de inicializacao: -nosteam
  Depois Entrar no jogo > Entrar no servidor > IP e porta do servidor, usuario e senha.
  Nao precisa ativar os mods no menu: o servidor diz quais ligam.

ATUALIZAR
  Quando o dono mandar um .zip novo, instale de novo (o programa apaga a versao velha antes).

VOLTAR A JOGAR COM STEAM
  Tire o -nosteam das opcoes de inicializacao. Se for jogar em servidor da Steam com estes
  mesmos mods, use "Desinstalar" no programa (ou apague as pastas de Zomboid/mods) para nao
  ficar com duas versoes do mesmo mod.
""" % {"t": cfg.get("titulo") or cfg.get("nome") or "do servidor", "b": branch}


def exportar_nosteam(cfg, saida=None, progresso=None):
    """Gera o .zip com mods/<pasta>/... + manifesto + leia-me. progresso(feito, total) em bytes.
    Devolve (ok, mensagens)."""
    pastas, problemas, avisos = pastas_nosteam(cfg)
    if problemas:
        return False, ["PROBLEMA: " + p for p in problemas]
    if not pastas:
        return False, ["PROBLEMA: nenhum mod para exportar."]
    if not saida:
        saida = os.path.join(cfg["_dir"], "%s_nosteam.zip" % cfg["pasta"])
    arquivos, total = [], 0
    for p in pastas:
        for raiz, _, nomes in os.walk(p["origem"]):
            for a in nomes:
                s = os.path.join(raiz, a)
                rel = os.path.relpath(s, p["origem"]).replace(os.sep, "/")
                tam = os.path.getsize(s)
                arquivos.append((s, "mods/%s/%s" % (p["nome"], rel), tam))
                total += tam
    import zipfile
    temp = saida + ".parcial"
    feito = 0
    manifesto = {"pack": os.path.basename(cfg["_dir"]), "titulo": cfg.get("titulo"), "branch": cfg["branch"],
                 "mods": cfg["mods"], "pastas": [p["nome"] for p in pastas], "gerado": int(time.time())}
    try:
        with zipfile.ZipFile(temp, "w", allowZip64=True) as z:
            z.writestr(MANIFESTO_NOSTEAM, json.dumps(manifesto, indent=1, ensure_ascii=False))
            z.writestr("LEIA-ME_nosteam.txt", leia_me_nosteam(cfg, cfg["branch"]))
            for s, arc, tam in arquivos:
                tipo = zipfile.ZIP_STORED if arc.lower().endswith(JA_COMPRIMIDOS) else zipfile.ZIP_DEFLATED
                z.write(s, arc, compress_type=tipo, compresslevel=6 if tipo == zipfile.ZIP_DEFLATED else None)
                feito += tam
                if progresso:
                    progresso(feito, total)
        os.replace(temp, saida)
    except OSError as e:
        if os.path.exists(temp):
            os.remove(temp)
        return False, ["PROBLEMA ao gravar o .zip: %s" % e]
    return True, avisos + [
        "Zip sem Steam pronto: %s (%d mods, %.2f GB de arquivos, zip com %.2f GB)."
        % (saida, len(pastas), total / 1e9, os.path.getsize(saida) / 1e9),
        "SERVIDOR: extraia este zip dentro da pasta Zomboid do servidor (a que tem Server/ e Saves/), "
        "use o .ini de 'Gerar .ini nosteam' e ligue o servidor com -nosteam.",
        "JOGADORES: mande o zip (Drive/MEGA); eles instalam pela pagina 'Sem Steam' do programa ou extraem na pasta Zomboid.",
    ]


def _membros_seguros(z):
    """Nomes do zip que caem dentro de mods/ (recusa caminho absoluto ou com '..')."""
    out = []
    for info in z.infolist():
        n = info.filename.replace("\\", "/")
        partes = [p for p in n.split("/") if p]
        if n.startswith("/") or ".." in partes or (partes and ":" in partes[0]):
            raise ValueError("caminho perigoso no zip: %s" % info.filename)
        if len(partes) >= 2 and partes[0] == "mods":
            out.append((info, partes))
    return out


def instalar_nosteam(zip_path, zomboid=None, progresso=None):
    """Instala o zip do modpack em <Zomboid>/mods (apaga antes a versao instalada do mesmo pack).
    Devolve (ok, mensagens)."""
    import zipfile
    zomboid = zomboid or pasta_zomboid_jogador()
    mods_dir = os.path.join(zomboid, "mods")
    try:
        z = zipfile.ZipFile(zip_path)
    except (OSError, zipfile.BadZipFile) as e:
        return False, ["Nao consegui abrir o zip: %s" % e]
    with z:
        try:
            man = json.loads(z.read(MANIFESTO_NOSTEAM).decode("utf-8"))
        except (KeyError, ValueError):
            return False, ["Esse zip nao foi gerado pelo programa (falta o %s)." % MANIFESTO_NOSTEAM]
        try:
            membros = _membros_seguros(z)
        except ValueError as e:
            return False, ["Zip recusado: %s" % e]
        pastas = sorted({p[1] for _, p in membros})
        reg_dir = os.path.join(zomboid, REGISTRO_NOSTEAM)
        reg = os.path.join(reg_dir, "%s.json" % slug(man.get("pack") or "modpack"))
        antigas = []
        if os.path.exists(reg):
            try:
                antigas = json.load(open(reg, encoding="utf-8")).get("pastas", [])
            except (OSError, ValueError):
                pass
        os.makedirs(mods_dir, exist_ok=True)
        substituidas = [p for p in pastas if os.path.isdir(os.path.join(mods_dir, p)) and p not in antigas]
        for p in set(antigas) | set(pastas):
            alvo = os.path.join(mods_dir, p)
            if os.path.isdir(alvo):
                shutil.rmtree(alvo)
        total = sum(i.file_size for i, _ in membros) or 1
        feito = 0
        for info, partes in membros:
            destino_arq = os.path.join(mods_dir, *partes[1:])
            if info.is_dir():
                os.makedirs(destino_arq, exist_ok=True)
                continue
            os.makedirs(os.path.dirname(destino_arq), exist_ok=True)
            with z.open(info) as src, open(destino_arq, "wb") as dst:
                shutil.copyfileobj(src, dst, 1 << 20)
            feito += info.file_size
            if progresso:
                progresso(feito, total)
    os.makedirs(reg_dir, exist_ok=True)
    man["pastas"] = pastas
    man["instalado"] = int(time.time())
    with open(reg, "w", encoding="utf-8") as f:
        json.dump(man, f, indent=1, ensure_ascii=False)
    msgs = ["Instalado: %d mods em %s." % (len(pastas), mods_dir)]
    if substituidas:
        msgs.append("Substitui %d pastas que ja existiam em mods/ com o mesmo nome: %s"
                    % (len(substituidas), ", ".join(substituidas[:10])))
    msgs += ["Versao do jogo do modpack: %s (a sua tem que ser a mesma)." % man.get("branch", "?"),
             "Abra o jogo com -nosteam (Steam: Propriedades > Opcoes de inicializacao) e entre pelo IP do servidor."]
    return True, msgs


def instalados_nosteam(zomboid=None):
    """[(pack, titulo, branch, n_pastas, quando)] instalados nesta pasta Zomboid."""
    zomboid = zomboid or pasta_zomboid_jogador()
    out = []
    for f in sorted(glob.glob(os.path.join(glob.escape(os.path.join(zomboid, REGISTRO_NOSTEAM)), "*.json"))):
        try:
            d = json.load(open(f, encoding="utf-8"))
        except (OSError, ValueError):
            continue
        out.append((os.path.splitext(os.path.basename(f))[0], d.get("titulo") or "?", d.get("branch") or "?",
                    len(d.get("pastas", [])), d.get("instalado")))
    return out


def desinstalar_nosteam(pack, zomboid=None):
    """Apaga de <Zomboid>/mods as pastas que o programa instalou para esse pack."""
    zomboid = zomboid or pasta_zomboid_jogador()
    reg = os.path.join(zomboid, REGISTRO_NOSTEAM, "%s.json" % pack)
    try:
        pastas = json.load(open(reg, encoding="utf-8")).get("pastas", [])
    except (OSError, ValueError):
        return False, ["Nada instalado com o nome '%s' em %s." % (pack, zomboid)]
    apagadas = 0
    for p in pastas:
        alvo = os.path.join(zomboid, "mods", p)
        if p and os.path.isdir(alvo):
            shutil.rmtree(alvo)
            apagadas += 1
    os.remove(reg)
    return True, ["Desinstalado '%s': %d pastas apagadas de %s." % (pack, apagadas, os.path.join(zomboid, "mods"))]


def gerar_ini_nosteam(cfg, entrada, saida=None):
    """Copia o .ini do servidor para o modo -nosteam: Mods= do modpack e WorkshopItems= vazio.
    Grava com o MESMO nome em 'pronto_nosteam/'. Devolve (ok, mensagens)."""
    if not os.path.isfile(entrada):
        return False, ["Arquivo nao encontrado: %s" % entrada]
    texto = open(entrada, encoding="utf-8", errors="ignore").read()
    if not re.search(r"^Mods=", texto, re.M) or not re.search(r"^WorkshopItems=", texto, re.M):
        return False, ["Esse arquivo nao tem as linhas Mods= e WorkshopItems= (e o .ini do servidor?)."]
    if not cfg["mods"]:
        return False, ["O modpack nao tem nenhum mod na lista."]
    _, problemas, avisos = pastas_nosteam(cfg)
    if problemas:
        return False, ["PROBLEMA: " + p for p in problemas]
    ordem = ordenar_por_dependencias(cfg)
    if ordem:
        salvar(cfg)
    texto = re.sub(r"^Mods=.*$", lambda m: "Mods=" + ";".join(cfg["mods"]), texto, count=1, flags=re.M)
    texto = re.sub(r"^WorkshopItems=.*$", "WorkshopItems=", texto, count=1, flags=re.M)
    if not saida:
        pasta = os.path.join(os.path.dirname(os.path.abspath(entrada)), "pronto_nosteam")
        os.makedirs(pasta, exist_ok=True)
        saida = os.path.join(pasta, os.path.basename(entrada))
    if os.path.abspath(saida) == os.path.abspath(entrada):
        return False, ["Escolha outro lugar para o .ini pronto (nao sobrescrevo o original)."]
    with open(saida, "w", encoding="utf-8") as f:
        f.write(texto)
    return True, ordem + avisos + [
        "Ini sem Steam pronto: %s (Mods= com %d mods, WorkshopItems= vazio)." % (saida, len(cfg["mods"])),
        "1) Com o servidor DESLIGADO, suba esse arquivo (mesmo nome) em Zomboid/Server/.",
        "2) Extraia o zip de 'Exportar zip nosteam' dentro da pasta Zomboid do servidor (fica Zomboid/mods/...).",
        "3) No painel, acrescente -nosteam no fim do comando de inicializacao (aba Startup) e ligue.",
        "Quem entra precisa abrir o jogo com -nosteam e ter o mesmo zip instalado; jogador no modo Steam nao entra.",
        "Faca isso num servidor separado (ou com backup): as contas do modo Steam e do -nosteam nao sao as mesmas.",
    ]


def criar_ini_novo(cfg, nome_servidor):
    """Cria um .ini de servidor do zero, so com o essencial (Mods= e WorkshopItems=); o servidor completa o
    resto com os valores padrao quando liga. Fica em packs/<pack>/servidor/<nome>.ini e a copia certa sai em
    packs/<pack>/servidor/pronto/<nome>.ini (o nome tem que ser o -servername do servidor)."""
    nome = re.sub(r"[^A-Za-z0-9_-]+", "", nome_servidor or "") or "servertest"
    pasta = os.path.join(cfg["_dir"], "servidor")
    os.makedirs(pasta, exist_ok=True)
    base = os.path.join(pasta, nome + ".ini")
    if not os.path.exists(base):
        with open(base, "w", encoding="utf-8") as f:
            f.write("# Criado pelo PZ Modpack Manager: so o essencial. O servidor completa as outras opcoes\n"
                    "# com os valores padrao na primeira vez que ligar.\n"
                    "Mods=\nWorkshopItems=\n")
    return gerar_ini(cfg, base)


def situacao_ini(cfg):
    """(estado, mensagem) do .ini gerado: "nenhum", "sumiu", "ok" ou "desatualizado"."""
    pronto = cfg.get("ini_pronto")
    if not pronto:
        return "nenhum", "Ainda não gerado."
    if not os.path.isfile(pronto):
        return "sumiu", "O .ini gerado não existe mais (%s)." % pronto
    mods, itens = ler_ini_listas(pronto)
    if mods is None:
        return "sumiu", "O arquivo %s não parece um .ini de servidor." % pronto
    faltam = [m for m in cfg["mods"] if m not in mods]
    sobram = [m for m in mods if m not in cfg["mods"]]
    pub = pacote_id(cfg)
    if faltam or sobram or (pub and pub not in itens) or mods != cfg["mods"]:
        partes = []
        if faltam:
            partes.append("faltam %d mod(s)" % len(faltam))
        if sobram:
            partes.append("sobram %d mod(s)" % len(sobram))
        if not partes:
            partes.append("ordem ou WorkshopItems diferentes")
        return "desatualizado", ", ".join(partes)
    return "ok", "%d mods, igual ao modpack" % len(mods)


def atualizar_ini(cfg):
    """Gera o .ini de novo a partir do .ini do servidor escolhido da ultima vez. (ok, mensagens)"""
    orig = cfg.get("ini_servidor")
    if not orig or not os.path.isfile(orig):
        return False, ["Escolha o .ini do servidor (o app guarda para as próximas vezes)."]
    return gerar_ini(cfg, orig, cfg.get("ini_pronto"))


# Conferencias ------------------------------------------------------------------------

RESULTADOS_STEAM = {
    "2": "falha generica da Steam (tente de novo)",
    "8": "parametro invalido: descricao/titulo/tags/imagem recusados (descricao passou de 8000 bytes?)",
    "9": "item nao encontrado (id errado ou apagado)",
    "15": "acesso negado: item privado, so-amigos ou que nunca terminou de enviar (0 B na pagina)",
    "16": "tempo esgotado (internet/Steam fora do ar)",
    "25": "limite excedido na Steam",
}


def conferir_ini(cfg, caminho):
    """[(nivel, mensagem)] com nivel ERRO/AVISO/OK sobre o .ini do servidor x este modpack."""
    out = []
    mods, itens = ler_ini_listas(caminho)
    if mods is None:
        return [("ERRO", "O arquivo nao tem as linhas Mods= e WorkshopItems=.")]
    pub = pacote_id(cfg)
    nosteam = not itens
    if not mods:
        out.append(("ERRO", "Mods= esta VAZIO: o servidor baixa o pacote mas nao liga nenhum mod. Use 'Gerar .ini'."))
    if nosteam:
        out.append(("AVISO", "WorkshopItems= vazio: so serve para servidor ligado com -nosteam e com os mods em "
                             "Zomboid/mods (zip de 'Exportar zip nosteam'). Em servidor da Steam, use 'Gerar .ini'."))
    elif pub and pub not in itens:
        out.append(("ERRO", "WorkshopItems= nao tem o pacote (%s)." % pub))
    esperados = list(cfg["mods"])
    faltam = [m for m in esperados if m not in mods]
    sobram = [m for m in mods if m not in esperados]
    if mods and faltam:
        out.append(("ERRO", "%d mods do modpack faltam no Mods=: %s" % (len(faltam), ", ".join(faltam[:15]))))
    if sobram:
        out.append(("AVISO", "%d mods no Mods= nao estao no modpack (precisam vir de outro item): %s" % (len(sobram), ", ".join(sobram[:15]))))
    dentro = {d["item"] for d in cfg["congelado"].values()}
    dup = [i for i in itens if i in dentro]
    if dup:
        out.append(("AVISO", "WorkshopItems= tem itens originais que ja estao DENTRO do pacote (mods repetidos): %s" % ", ".join(dup)))
    separados = [i for i in cfg["itens"] if i in cfg["separados"]]
    falta_sep = [i for i in separados if i not in itens] if not nosteam else []
    if falta_sep:
        out.append(("ERRO", "Itens separados (fora do pacote) faltando no WorkshopItems=: %s" % ", ".join(falta_sep)))
    # ordem das dependencias
    pos = {m: n for n, m in enumerate(mods)}
    for c in cfg["congelado"]:
        pasta = os.path.join(pack_mods(cfg), c)
        if not os.path.isdir(pasta):
            continue
        inf = info_pasta(pasta)
        for i in inf["ids"]:
            for r in inf["req"]:
                if i in pos and r in pos and pos[r] > pos[i]:
                    out.append(("AVISO", "Ordem: '%s' precisa de '%s', mas ele vem DEPOIS no Mods=." % (i, r)))
    if not any(n == "ERRO" for n, _ in out):
        out.append(("OK", "Ini confere com o modpack: %d mods, WorkshopItems= %s." % (len(mods), ";".join(itens) or "vazio (modo -nosteam)")))
    return out


def _mod_da_linha(linha, pastas):
    m = re.search(r"/mods/([^/]+)/", linha.replace("\\", "/"))
    if m:
        return m.group(1)
    for nome in pastas:
        if nome in linha:
            return nome
    return None


def conferir_log(cfg, caminho):
    """Le um log (console.txt do jogo ou DebugLog-server.txt / console do painel) e confere
    a ultima conexao/inicio: mods carregados x esperados, erros da Workshop e erros por mod."""
    out = []
    linhas_log = open(caminho, encoding="utf-8", errors="ignore").read().splitlines()
    # So a ultima sessao: a partir do ultimo inicio de servidor ou conexao.
    inicio = None
    for n, l in enumerate(linhas_log):
        if 'server name is "' in l or "ConnectToServerState: Start" in l:
            inicio = n
    if inicio is None:
        return [("AVISO", "Esse log nao tem nenhuma conexao a servidor nem inicio de servidor (so o menu do jogo). "
                          "Entre no servidor, saia do jogo e confira de novo.")]
    sessao = linhas_log[inicio:]
    nome = re.search(r'server name is "([^"]+)"', "\n".join(sessao))
    if nome:
        out.append(("OK", "Log do servidor '%s'." % nome.group(1)))
    carregados = []
    for l in sessao:
        m = re.match(r"^(?:\[[^\]]*\]\s*)?LOG\s*:\s*Mod\s.*?> loading (.+?)\.?\s*$", l)
        if m:
            carregados.append(m.group(1).strip())
    # O DebugLog-server.txt nao registra "loading <mod>"; o sinal confiavel de mod AUSENTE e o
    # jogo descartando itens dele ao carregar o mundo ("cannot create item ... modID = X").
    descartados = {}
    for l in sessao:
        m = re.search(r'cannot create item:.*?modID = "([^"]+)"', l)
        if m:
            descartados[m.group(1)] = descartados.get(m.group(1), 0) + 1
    tem_registro_de_mods = any(re.search(r"LOG\s*:\s*Mod\s", l) for l in sessao)
    for l in sessao:
        m = re.search(r"onItemNotDownloaded itemID=(\d+) result=(\d+)", l)
        if m:
            out.append(("ERRO", "Workshop nao baixou o item %s: result=%s = %s" % (
                m.group(1), m.group(2), RESULTADOS_STEAM.get(m.group(2), "codigo da Steam %s" % m.group(2)))))
    pub = pacote_id(cfg)
    if pub and any(("Ready ID=%s" % pub) in l or ("onItemDownloaded itemID=%s" % pub) in l for l in sessao):
        out.append(("OK", "O pacote %s foi baixado." % pub))
    esperados = cfg["mods"]
    if not any("Workshop" in l for l in sessao):
        out.append(("AVISO", "Nenhuma atividade da Workshop nesta sessao: o .ini lido pode estar sem WorkshopItems= "
                              "(ou o servidor criou um .ini novo e vazio por causa do nome do arquivo)."))
    if descartados:
        tot = sum(descartados.values())
        out.append(("ERRO", "O jogo DESCARTOU %d itens de mods que nao estao carregados (somem do save ao salvar!): %s. "
                            "Pare o servidor e confira o Mods=/WorkshopItems= do .ini." % (
                                tot, ", ".join("%s (%d)" % t for t in sorted(descartados.items(), key=lambda x: -x[1])[:8]))))
    if not carregados and not tem_registro_de_mods:
        out.append(("AVISO", "Este tipo de log nao registra quais mods carregaram (o DebugLog-server.txt nao tem). "
                             "Para a lista completa, use o console do painel ou o console.txt do jogo."))
    elif not carregados:
        out.append(("ERRO", "Nenhum mod carregado nesta sessao. Se o pacote baixou, o Mods= do servidor esta vazio "
                            "ou com nomes errados: use 'Gerar .ini'."))
    else:
        faltam = [m for m in esperados if m not in carregados]
        out.append(("OK" if not faltam else "ERRO", "%d de %d mods do modpack carregados." % (
            len([m for m in esperados if m in carregados]), len(esperados))))
        if faltam:
            out.append(("ERRO", "Nao carregaram: %s" % ", ".join(faltam[:20])))
    # Erros de verdade (o jogo escreve "Lua((MOD:Nome))" no erro de Lua de mod). Ruido conhecido
    # do jogo fica de fora: pasta AnimSets/actiongroups ausente e osso de animacao nao achado.
    ruido = ("visitFileFailed", "NoSuchFileException", "Could not find bone index", "UnixException",
             "Sanitizing container name", "AngelCodeFont", "missing UiConfigScript")
    por_mod, msgs_erro, total = {}, {}, 0
    for n, l in enumerate(sessao):
        if not (l.startswith("ERROR") or "Exception thrown" in l):
            continue
        if any(r in l for r in ruido) or "dumping Lua stack trace" in l or l.rstrip().endswith("> ----"):
            continue
        prox = " ".join(sessao[n:n + 3])
        if any(r in prox for r in ruido):
            continue
        total += 1
        m = re.search(r"Lua\(\(MOD:(.+?)\)\)\.", l) or re.search(r"MOD: ?([^|\n]+)", prox)
        if m:
            por_mod[m.group(1).strip()] = por_mod.get(m.group(1).strip(), 0) + 1
        ex = re.search(r"(\w+(?:Exception|Error)): (.{0,120})", prox)
        chave = (ex.group(1) + ": " + re.sub(r"\d+", "#", ex.group(2))) if ex else re.sub(r"\d+", "#", l.split(">", 1)[-1].strip()[:120])
        msgs_erro[chave] = msgs_erro.get(chave, 0) + 1
    if por_mod:
        out.append(("AVISO", "Mods com erro de Lua: " + ", ".join("%s (%d)" % t for t in sorted(por_mod.items(), key=lambda x: -x[1]))))
    for chave, qt in sorted(msgs_erro.items(), key=lambda x: -x[1])[:8]:
        out.append(("AVISO", "%dx %s" % (qt, chave)))
    dup = [k for k in msgs_erro if "duplicate object" in k]
    if dup:
        out.append(("ERRO", "Ha registro DUPLICADO: dois mods (ou duas versoes do mesmo mod) definem a mesma coisa. "
                            "Deixe so um deles no Mods=."))
    out.append(("OK" if total == 0 else "AVISO", "%d erros relevantes na sessao (sem contar o ruido normal do jogo)." % total))
    return out


def status_publicacao(cfg, timeout=15):
    """Pagina do pacote na Steam vista como visitante: (visivel, tamanho_bytes, mensagens)."""
    pub = pacote_id(cfg)
    if not pub:
        return False, None, [("ERRO", "Pacote ainda nao publicado (sem id).")]
    url = "https://steamcommunity.com/sharedfiles/filedetails/?id=%s" % pub
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        t = urllib.request.urlopen(req, timeout=timeout).read().decode("utf-8", "ignore")
    except urllib.error.HTTPError as e:
        if e.code == 429:
            return False, None, [("AVISO", "A Steam pediu para esperar (muitas consultas seguidas). "
                                           "Tente de novo daqui a alguns minutos.")]
        return False, None, [("AVISO", "Nao consegui abrir a Steam: %s" % e)]
    except Exception as e:
        return False, None, [("AVISO", "Nao consegui abrir a Steam: %s" % e)]
    out = []
    titulo = re.search(r'<div class="workshopItemTitle">(.*?)</div>', t)
    if not titulo:
        return False, None, [("ERRO", "O pacote %s NAO aparece para quem esta de fora: privado, so-amigos ou o envio nao "
                                      "terminou (0 B). Publique de novo no jogo e espere 'success updating item'." % pub)]
    stats = re.findall(r'<div class="detailsStatRight">(.*?)</div>', t)
    tam = None
    if stats:
        m = re.match(r"([\d.,]+)\s*(B|KB|MB|GB)", stats[0].strip())
        if m:
            tam = float(m.group(1).replace(",", "")) * {"B": 1, "KB": 1e3, "MB": 1e6, "GB": 1e9}[m.group(2)]
    out.append(("OK", "Visivel na Steam: %s (%s)." % (titulo.group(1).strip(), stats[0] if stats else "?")))
    if tam is not None and tam < 1000:
        out.append(("ERRO", "Publicado com 0 B: o envio nao terminou. Publique de novo."))
    local = (cfg.get("montado") or {}).get("bytes")
    if not local and os.path.isdir(pack_mods(cfg)):
        local = sum(os.path.getsize(os.path.join(r, f)) for r, _, fs in os.walk(pack_mods(cfg)) for f in fs)
    if tam and local:
        dif = abs(tam - local) / max(local, 1)
        if dif > 0.02:
            out.append(("AVISO", "O publicado (%.2f GB) e diferente do pacote montado (%.2f GB): falta publicar a "
                                 "ultima montagem." % (tam / 1e9, local / 1e9)))
        else:
            out.append(("OK", "O publicado bate com o pacote montado (%.2f GB)." % (local / 1e9)))
    return True, tam, out


def branch_do_jogo():
    """Branch (beta) do jogo instalado nesta maquina, pelo appmanifest da Steam."""
    if not WORKSHOP:
        return None
    steamapps = os.path.dirname(os.path.dirname(os.path.dirname(WORKSHOP)))
    for lib in [steamapps]:
        acf = os.path.join(lib, "appmanifest_%s.acf" % APP_PZ)
        if os.path.exists(acf):
            m = re.search(r'"BetaKey"\s*"([^"]*)"', open(acf, encoding="utf-8", errors="ignore").read())
            return m.group(1) if m else ""
    return None


# Linha de comando --------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(description="Gerenciador de modpacks de servidor")
    ap.add_argument("--pack", help="nome (pasta) do modpack; sem isso, o primeiro")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("packs")
    sub.add_parser("pastas")
    n = sub.add_parser("novo"); n.add_argument("nome"); n.add_argument("--ini"); n.add_argument("--branch", default="42.21")
    sub.add_parser("status")
    a = sub.add_parser("adicionar"); a.add_argument("item"); a.add_argument("--mods")
    r = sub.add_parser("remover"); r.add_argument("item")
    s = sub.add_parser("separar"); s.add_argument("item"); s.add_argument("motivo", nargs="?", default="")
    j = sub.add_parser("juntar"); j.add_argument("item")
    m = sub.add_parser("montar"); m.add_argument("--atualizar", default=""); m.add_argument("--simular", action="store_true")
    sub.add_parser("linhas")
    sub.add_parser("baixados")
    sub.add_parser("novidades")
    i = sub.add_parser("ini"); i.add_argument("entrada"); i.add_argument("saida", nargs="?")
    ci = sub.add_parser("conferir-ini"); ci.add_argument("arquivo")
    cl = sub.add_parser("conferir-log"); cl.add_argument("arquivo")
    sub.add_parser("publicacao")
    ba = sub.add_parser("baixar"); ba.add_argument("itens", help="ids separados por virgula")
    sub.add_parser("restaurar")
    bu = sub.add_parser("procurar"); bu.add_argument("texto", nargs="?", default=""); bu.add_argument("--pagina", type=int, default=1)
    bu.add_argument("--ordem", default="textsearch", choices=[o for _, o in ORDENS_BUSCA]); bu.add_argument("--todas-versoes", action="store_true")
    en = sub.add_parser("exportar-nosteam"); en.add_argument("saida", nargs="?")
    inn = sub.add_parser("ini-nosteam"); inn.add_argument("entrada"); inn.add_argument("saida", nargs="?")
    ins = sub.add_parser("instalar-nosteam"); ins.add_argument("zip"); ins.add_argument("--zomboid")
    de = sub.add_parser("desinstalar-nosteam"); de.add_argument("pack", nargs="?"); de.add_argument("--zomboid")
    args = ap.parse_args()

    if args.cmd == "packs":
        for s_, t in listar_packs():
            print("%-20s %s" % (s_, t))
        return 0
    if args.cmd == "pastas":
        print("Downloads da Workshop: %s" % (WORKSHOP or "(nao achei)"))
        print("Download automatico (SteamCMD): %s" % workshop_steamcmd())
        print("Publicar (Zomboid/Workshop): %s" % PUBLICAR)
        for p in pastas_ok():
            print("PROBLEMA: " + p)
        return 0
    if args.cmd == "novo":
        ok, msgs, _ = novo(args.nome, args.ini, args.branch)
        print("\n".join(msgs))
        return 0 if ok else 1
    if args.cmd == "baixar":
        b, f, msgs = baixar_automatico([item_id(x) for x in args.itens.split(",")], aviso=print)
        print("\n".join(msgs))
        return 0 if not f else 1
    if args.cmd == "procurar":
        res, paginas, total = buscar_workshop(args.texto, args.ordem, args.pagina, not args.todas_versoes)
        for d in res:
            print("%-11s %-45.45s %-20.20s %8d insc. %s" % (d["item"], d["titulo"], d["autor"], d["inscritos"],
                                                             "B42" if d["b42"] else "B41"))
        print("pagina %d de %d (%d resultados)" % (args.pagina, paginas, total))
        return 0
    if args.cmd == "instalar-nosteam":
        ok, msgs = instalar_nosteam(args.zip, args.zomboid)
        print("\n".join(msgs))
        return 0 if ok else 1
    if args.cmd == "desinstalar-nosteam":
        if not args.pack:
            for pk, t, b, n, _ in instalados_nosteam(args.zomboid):
                print("%-20s %-30s branch %-6s %d pastas" % (pk, t, b, n))
            return 0
        ok, msgs = desinstalar_nosteam(args.pack, args.zomboid)
        print("\n".join(msgs))
        return 0 if ok else 1
    cfg = carregar(args.pack)
    ok, msgs = True, []
    if args.cmd == "status":
        for item, nome, ativos, sit in status(cfg):
            print("%-11s %-45.45s %s" % (item, nome, sit))
        return 0
    if args.cmd == "baixados":
        for d in baixados():
            print("%-11s %-45.45s %-4s %s" % (d["item"], d["nome"], "B42" if d["b42"] else "B41", situacao_no_pack(cfg, d["item"])))
        return 0
    if args.cmd == "novidades":
        novos = com_versao_nova(cfg)
        print("%d mods do pacote com versao nova baixada: %s" % (len(novos), ", ".join(novos) or "-"))
        print("Para atualizar: montar --atualizar " + ",".join(novos) if novos else "")
        return 0
    if args.cmd == "adicionar":
        mods = [x.strip() for x in args.mods.split(",")] if args.mods else None
        ok, msgs, opcoes = adicionar(cfg, args.item, mods)
        if opcoes:
            msgs.append("Use --mods com um ou mais destes ids: " + ", ".join("%s (%s)" % o for o in opcoes))
    elif args.cmd == "remover":
        ok, msgs = remover(cfg, args.item)
    elif args.cmd == "separar":
        ok, msgs = separar(cfg, args.item, args.motivo)
    elif args.cmd == "juntar":
        ok, msgs = juntar(cfg, args.item)
    elif args.cmd == "montar":
        at = "tudo" if args.atualizar == "tudo" else [item_id(x) for x in args.atualizar.split(",") if x.strip()]
        ok, msgs = montar(cfg, at, args.simular)
    elif args.cmd == "ini":
        ok, msgs = gerar_ini(cfg, args.entrada, args.saida)
    elif args.cmd == "restaurar":
        ok, msgs = restaurar_do_publicado(cfg)
    elif args.cmd == "exportar-nosteam":
        ok, msgs = exportar_nosteam(cfg, args.saida)
    elif args.cmd == "ini-nosteam":
        ok, msgs = gerar_ini_nosteam(cfg, args.entrada, args.saida)
    elif args.cmd in ("conferir-ini", "conferir-log", "publicacao"):
        if args.cmd == "conferir-ini":
            res = conferir_ini(cfg, args.arquivo)
        elif args.cmd == "conferir-log":
            res = conferir_log(cfg, args.arquivo)
        else:
            res = status_publicacao(cfg)[2]
        for nivel, m in res:
            print("[%s] %s" % (nivel, m))
        return 1 if any(n == "ERRO" for n, _ in res) else 0
    if args.cmd in ("linhas", "montar") and ok:
        msgs += list(linhas(cfg))
    print("\n".join(msgs))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
