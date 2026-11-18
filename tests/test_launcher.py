"""Testes do motor do launcher (python3 tests/test_launcher.py). Zips de verdade, pasta Zomboid falsa."""
import os
import shutil
import sys
import tempfile
import zipfile

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import launcher_sync as L  # noqa: E402

BASE = tempfile.mkdtemp(prefix="pzl_test_")
Z = os.path.join(BASE, "Zomboid")
MODS = os.path.join(Z, "mods")


def zip_de(caminho, arquivos, prefixo=""):
    with zipfile.ZipFile(caminho, "w") as z:
        for nome, conteudo in arquivos.items():
            metodo = zipfile.ZIP_STORED if nome.endswith(".png") else zipfile.ZIP_DEFLATED
            z.writestr(prefixo + nome, conteudo, compress_type=metodo)
    return caminho


def ler(rel):
    return open(os.path.join(MODS, rel), "rb").read()


def ok(cond, msg):
    if not cond:
        raise AssertionError(msg)
    print("  ok  ", msg)


v1 = {"ModA/42/mod.info": b"id=A\n", "ModA/42/media/lua/a.lua": b"print('a')\n" * 500,
      "ModA/poster.png": os.urandom(5000), "ModB/42/mod.info": b"id=B\n", "ModB/42/media/b.txt": b"b" * 3000}
zA = zip_de(os.path.join(BASE, "packA.zip"), v1)
os.makedirs(os.path.join(MODS, "MeuModDev", "42"))
open(os.path.join(MODS, "MeuModDev", "42", "mod.info"), "w").write("id=dev")
open(os.path.join(MODS, "default.txt"), "w").write("lista do jogo")

print("== primeira instalacao")
A = L.adicionar_pack(Z, "Pack A", zA)
r = L.sincronizar(Z, A)
ok(r["baixados"] == 5, "baixou os 5 arquivos")
ok(ler("ModA/42/media/lua/a.lua") == v1["ModA/42/media/lua/a.lua"], "conteudo certo (deflate)")
ok(ler("ModA/poster.png") == v1["ModA/poster.png"], "conteudo certo (sem compressao)")
ok(r["backup"] == ["MeuModDev"], "mod solto foi para o backup")
ok(not os.path.exists(os.path.join(MODS, "MeuModDev")), "saiu da pasta mods")
ok(os.path.isdir(os.path.join(Z, "mods_removidos")), "existe em mods_removidos")
ok(os.path.exists(os.path.join(MODS, "default.txt")), "arquivo solto do jogo (default.txt) nao e mexido")

print("== atualizacao: muda 1, tira 1, poe 1")
v2 = dict(v1)
v2["ModA/42/media/lua/a.lua"] = b"print('a2')\n" * 500
del v2["ModB/42/media/b.txt"]
v2["ModC/42/mod.info"] = b"id=C\n"
zip_de(zA, v2)
r = L.sincronizar(Z, A)
ok(r["baixados"] == 2, "baixou so 2 (o alterado e o novo), nao os 5")
ok(r["apagados"] == 1, "apagou o que saiu do pack")
ok(not os.path.exists(os.path.join(MODS, "ModB/42/media/b.txt")), "b.txt sumiu")
ok(ler("ModA/42/media/lua/a.lua") == v2["ModA/42/media/lua/a.lua"], "a.lua atualizado")
r = L.sincronizar(Z, A)
ok(r["baixados"] == 0 and r["apagados"] == 0, "rodar de novo sem mudanca nao baixa nada")

print("== arquivo mexido no PC volta ao original")
open(os.path.join(MODS, "ModB", "42", "mod.info"), "wb").write(b"id=X\n")  # mesmo tamanho, conteudo diferente
r = L.sincronizar(Z, A)
ok(r["baixados"] == 1 and ler("ModB/42/mod.info") == b"id=B\n", "consertado pelo CRC")

print("== troca de pack: estaciona e restaura sem baixar")
zB = zip_de(os.path.join(BASE, "packB.zip"), {"mods/ModA/42/mod.info": b"id=A\n", "mods/ModZ/42/mod.info": b"id=Z\n"})
B = L.adicionar_pack(Z, "Pack B", zB)
r = L.sincronizar(Z, B)
ok(sorted(os.listdir(MODS)) == ["ModA", "ModZ", "default.txt"], "so os mods do pack B (prefixo mods/ no zip)")
ok(sorted(r["estacionados"]) == ["ModB", "ModC"], "ModB e ModC estacionados")
ok(not os.path.exists(os.path.join(MODS, "ModA", "42", "media")), "ModA ficou igual a versao do pack B")
r = L.sincronizar(Z, A)
ok(sorted(r["restaurados"]) == ["ModB", "ModC"], "voltaram do estacionamento")
ok(r["baixados"] == 2, "baixou so os 2 arquivos do ModA que o pack B tinha tirado")
ok(L.config(Z)["ativo"] == A, "pack A ativo")

print("== desativar")
d = L.desativar(Z)
ok(sorted(d) == ["ModA", "ModB", "ModC"], "tudo estacionado")
ok(sorted(os.listdir(MODS)) == ["default.txt"], "pasta mods limpa")
r = L.sincronizar(Z, A)
ok(r["baixados"] == 0, "reativar nao baixa nada")

print("== zip do 'Exportar zip nosteam' (mods/ + manifesto e LEIA-ME na raiz)")
zN = zip_de(os.path.join(BASE, "nosteam.zip"), {"mods/ModN/42/mod.info": b"id=N\n", "modpack_nosteam.json": b"{}",
                                               "LEIA-ME_nosteam.txt": b"leia"})
N = L.adicionar_pack(Z, "Pack N", zN)
r = L.sincronizar(Z, N)
ok(r["mods"] == 1 and os.path.exists(os.path.join(MODS, "ModN", "42", "mod.info")), "so o ModN, sem uma pasta 'mods' dentro de mods")
ok(not os.path.exists(os.path.join(MODS, "modpack_nosteam.json")), "manifesto nao vai para a pasta mods")

print("== links")
ok(L.link_direto("https://drive.google.com/file/d/ABC_123-x/view?usp=sharing").endswith("id=ABC_123-x&export=download&confirm=t"), "drive /file/d/")
ok("id=QQ" in L.link_direto("https://drive.google.com/open?id=QQ"), "drive open?id=")
ok(L.link_direto("https://www.dropbox.com/s/x/a.zip?dl=0").endswith("dl=1"), "dropbox")

shutil.rmtree(BASE)
print("TUDO OK")
