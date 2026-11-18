#!/usr/bin/env python3
"""PZ Modpack Launcher - tela. Cole o link do modpack (Google Drive ou direto); o launcher deixa a pasta
Zomboid/mods igual a ele, baixando so o que mudou, e confere atualizacoes sozinho."""
import json
import os
import sys
import threading
import time
import tkinter as tk
import urllib.request
from tkinter import filedialog, messagebox, simpledialog, ttk

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import launcher_sync as L  # noqa: E402
import modpack as MP  # noqa: E402
import tema  # noqa: E402

VERSAO = "1.0.0"
REPO = "DiomarGoncalves/pz-modpack-manager"
INTERVALO_MIN = 30


def abrir(alvo):
    try:
        if os.name == "nt":
            os.startfile(alvo)  # noqa: S606
        else:
            import subprocess
            subprocess.Popen(["open" if sys.platform == "darwin" else "xdg-open", alvo])
    except OSError as e:
        messagebox.showerror("Launcher", str(e))


def quando(ts):
    return time.strftime("%d/%m %H:%M", time.localtime(ts)) if ts else "-"


def nova_versao_launcher():
    """Tag da ultima Release no GitHub, se for mais nova que esta (ou None)."""
    try:
        req = urllib.request.Request("https://api.github.com/repos/%s/releases/latest" % REPO,
                                     headers={"User-Agent": "PZ-Launcher"})
        tag = json.load(urllib.request.urlopen(req, timeout=10)).get("tag_name", "")
    except Exception:
        return None
    def num(v):
        return tuple(int(x) for x in v.lstrip("vV").split(".") if x.isdigit())
    return tag if tag and num(tag) > num(VERSAO) else None


class Launcher(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("PZ Modpack Launcher %s" % VERSAO)
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        w, h = min(940, sw - 40), min(600, sh - 80)
        self.geometry("%dx%d+%d+%d" % (w, h, (sw - w) // 2, (sh - h) // 3))
        self.minsize(720, 460)
        tema.aplicar(self, MP.local().get("tema", "escuro"))
        self.zomboid = L.pasta_zomboid()
        self.ocupado = False
        self.situacao = {}   # pack -> texto/cor da ultima verificacao
        self.auto = tk.BooleanVar(value=True)
        self._tela()
        self.protocol("WM_DELETE_WINDOW", self.fechar)
        self.preencher()
        self.after(800, self.verificar_tudo)
        self.after(1500, self.checar_launcher)

    # Tela -------------------------------------------------------------------------------------------
    def _tela(self):
        topo = ttk.Frame(self, padding=(16, 12, 16, 6))
        topo.pack(fill="x")
        ttk.Label(topo, text="☣  PZ MODPACK LAUNCHER", style="Marca.TLabel").pack(side="left")
        ttk.Label(topo, text="  v" + VERSAO, style="Sutil.TLabel").pack(side="left")
        ttk.Button(topo, text="Trocar pasta...", command=self.trocar_pasta).pack(side="right")
        self.lbl_pasta = ttk.Label(self, style="Sutil.TLabel", padding=(16, 0, 16, 6))
        self.lbl_pasta.pack(fill="x")
        self.banner = ttk.Label(self, style="BannerAviso.TLabel")
        corpo = ttk.Frame(self, padding=(16, 4, 16, 6))
        corpo.pack(fill="both", expand=True)
        corpo.columnconfigure(0, weight=1)
        corpo.rowconfigure(0, weight=1)
        cols = ("nome", "situacao", "mods", "tamanho", "atualizado")
        self.tabela = ttk.Treeview(corpo, columns=cols, show="headings", selectmode="browse")
        pesos = {"nome": 28, "situacao": 32, "mods": 8, "tamanho": 12, "atualizado": 20}
        for c, t in (("nome", "Modpack"), ("situacao", "Situação"), ("mods", "Mods"), ("tamanho", "Tamanho"),
                     ("atualizado", "Atualizado em")):
            self.tabela.heading(c, text=t)
            self.tabela.column(c, width=80, minwidth=50, anchor="w")

        def ajustar(e):
            total = float(sum(pesos.values()))
            for c, w in pesos.items():
                self.tabela.column(c, width=int((e.width - 4) * w / total))
        self.tabela.bind("<Configure>", ajustar, add="+")
        self.tabela.grid(row=0, column=0, sticky="nsew")
        self.tabela.bind("<Double-1>", lambda e: self.ativar())
        lado = ttk.Frame(corpo, padding=(10, 0, 0, 0))
        lado.grid(row=0, column=1, sticky="ns")
        for texto, cmd, estilo in (("＋ Adicionar modpack", self.adicionar, "Accent.TButton"),
                                   ("Ativar e atualizar", self.ativar, "Accent.TButton"),
                                   ("Verificar atualizações", self.verificar_tudo, "TButton"),
                                   ("Desativar (jogar na Steam)", self.desativar, "TButton"),
                                   ("Remover da lista", self.remover, "TButton"),
                                   ("Abrir pasta mods", lambda: abrir(os.path.join(self.zomboid, "mods")), "TButton"),
                                   ("Abrir backup", lambda: abrir(os.path.join(self.zomboid, "mods_removidos")), "TButton")):
            ttk.Button(lado, text=texto, command=cmd, style=estilo, width=26).pack(fill="x", pady=3)
        ttk.Checkbutton(lado, text="Atualizar sozinho", variable=self.auto).pack(anchor="w", pady=(12, 0))
        ttk.Label(lado, text="(confere ao abrir e a cada\n%d minutos)" % INTERVALO_MIN, style="Sutil.TLabel").pack(anchor="w")
        baixo = ttk.Frame(self, padding=(16, 0, 16, 12))
        baixo.pack(fill="x")
        self.etapa = ttk.Label(baixo, style="Sutil.TLabel")
        self.etapa.pack(fill="x")
        self.barra = ttk.Progressbar(baixo, maximum=1000)
        self.barra.pack(fill="x", pady=(4, 0))
        tema.tabela(self.tabela)

    def preencher(self):
        cfg = L.config(self.zomboid)
        self.lbl_pasta.configure(text="Pasta do jogo: %s" % os.path.join(self.zomboid, "mods"))
        sel = self.pack_sel()
        self.tabela.delete(*self.tabela.get_children())
        for pid, p in cfg["packs"].items():
            ativo = cfg.get("ativo") == pid
            sit, tag = self.situacao.get(pid, ("Ativo" if ativo else ("Instalado" if p.get("versao") else "Nunca instalado"),
                                               "dentro" if ativo else ""))
            if ativo and not sit.startswith("✔"):
                sit = "✔ " + sit
            t = p.get("tamanho") or 0
            tam = ("%.2f GB" % (t / 1e9)) if t >= 1e9 else (("%.1f MB" % (t / 1e6)) if t else "-")
            self.tabela.insert("", "end", iid=pid, tags=(tag,) if tag else (),
                               values=(p["nome"], sit, p.get("mods", "-"), tam, quando(p.get("atualizado"))))
        tema.zebra(self.tabela)
        if sel and self.tabela.exists(sel):
            self.tabela.selection_set(sel)

    def pack_sel(self):
        s = self.tabela.selection() if hasattr(self, "tabela") else ()
        return s[0] if s else None

    # Acoes ----------------------------------------------------------------------------------------------
    def adicionar(self):
        link = simpledialog.askstring("Adicionar modpack", "Cole o link do modpack (.zip no Google Drive ou link direto):",
                                      parent=self)
        if not link:
            return
        nome = simpledialog.askstring("Adicionar modpack", "Nome para este modpack (ex.: o nome do servidor):", parent=self)
        if not nome:
            return
        pid = L.adicionar_pack(self.zomboid, nome.strip(), link.strip())
        self.preencher()
        self.tabela.selection_set(pid)
        if messagebox.askyesno("Adicionar modpack", "Ativar e instalar '%s' agora?\n\nA pasta mods vai ficar igual a "
                                                    "este modpack. Mods que não fazem parte dele vão para o backup "
                                                    "(mods_removidos), não são apagados." % nome):
            self.sincronizar(pid)

    def ativar(self):
        pid = self.pack_sel()
        if not pid:
            return messagebox.showinfo("Launcher", "Selecione um modpack na lista.")
        self.sincronizar(pid)

    def desativar(self):
        if self.ocupado:
            return
        cfg = L.config(self.zomboid)
        if not cfg.get("ativo"):
            return messagebox.showinfo("Launcher", "Nenhum modpack ativo.")
        if messagebox.askyesno("Desativar", "Tirar os mods do modpack ativo da pasta mods?\n\nEles ficam guardados e "
                                            "voltam na hora quando você ativar de novo (sem baixar). Use antes de jogar "
                                            "em servidor da Steam, para não ter mod duplicado."):
            n = L.desativar(self.zomboid)
            self.situacao.clear()
            self.preencher()
            self.etapa.configure(text="Desativado: %d mod(s) guardados." % len(n))

    def remover(self):
        pid = self.pack_sel()
        if not pid or self.ocupado:
            return
        nome = L.config(self.zomboid)["packs"][pid]["nome"]
        if messagebox.askyesno("Remover", "Tirar '%s' da lista?\n\nSe ele estiver ativo, os mods dele vão para o "
                                          "backup (mods_removidos)." % nome):
            L.remover_pack(self.zomboid, pid)
            self.situacao.pop(pid, None)
            self.preencher()

    def trocar_pasta(self):
        d = filedialog.askdirectory(title="Pasta Zomboid do jogo (a que tem mods/ e Saves/)", initialdir=self.zomboid)
        if d:
            loc = MP.local()
            loc["zomboid_nosteam"] = d
            MP.salvar_local(loc)
            self.zomboid = d
            self.situacao.clear()
            self.preencher()

    # Em segundo plano --------------------------------------------------------------------------------------
    def _rodar(self, trabalho, fim):
        if self.ocupado:
            return
        self.ocupado = True
        st = {"feito": 0, "total": 1, "etapa": ""}

        def prog(f, t):
            st["feito"], st["total"] = f, max(1, t)

        def etapa(t):
            st["etapa"] = t

        def corre():
            try:
                st["res"] = ("ok", trabalho(prog, etapa))
            except Exception as e:
                st["res"] = ("erro", str(e))
        th = threading.Thread(target=corre, daemon=True)
        th.start()

        def acompanha():
            self.barra["value"] = int(st["feito"] / st["total"] * 1000)
            txt = st["etapa"]
            if st["total"] > 1:
                txt += "  %d%%  (%.1f de %.1f MB)" % (st["feito"] * 100 // st["total"], st["feito"] / 1e6, st["total"] / 1e6)
            self.etapa.configure(text=txt)
            if th.is_alive():
                self.after(200, acompanha)
                return
            self.ocupado = False
            fim(*st["res"])
        self.after(200, acompanha)

    def sincronizar(self, pid, silencioso=False):
        nome = L.config(self.zomboid)["packs"][pid]["nome"]

        def trabalho(prog, etapa):
            return L.sincronizar(self.zomboid, pid, prog, etapa)

        def fim(tipo, r):
            if tipo == "erro":
                self.situacao[pid] = ("✖ Erro: " + r, "erro")
                self.preencher()
                self.etapa.configure(text="Erro: " + r)
                if not silencioso:
                    messagebox.showerror("Launcher", r)
                return
            self.situacao[pid] = ("✔ Ativo e atualizado", "dentro")
            self.barra["value"] = 1000
            msg = "'%s' pronto: %d mods. Baixados %d arquivo(s) (%.1f MB), apagados %d." % (
                nome, r["mods"], r["baixados"], r["bytes"] / 1e6, r["apagados"])
            if r["backup"]:
                msg += " Para o backup: %s." % ", ".join(r["backup"][:8])
            self.etapa.configure(text=msg)
            self.preencher()
            if not silencioso:
                messagebox.showinfo("Launcher", msg)
        self._rodar(trabalho, fim)

    def verificar_tudo(self, automatico=False):
        """Confere todos os links (sem baixar) e, com 'Atualizar sozinho', atualiza o ativo se mudou."""
        packs = list(L.config(self.zomboid)["packs"].keys())
        if not packs:
            self.etapa.configure(text="Adicione um modpack com o link que o dono do servidor passou.")
            self._agendar()
            return

        def trabalho(prog, etapa):
            res = {}
            for i, pid in enumerate(packs):
                etapa("Verificando %d de %d..." % (i + 1, len(packs)))
                try:
                    mudou, _, _ = L.verificar(self.zomboid, pid)
                    res[pid] = mudou
                except Exception as e:
                    res[pid] = e
            return res

        def fim(tipo, res):
            ativo = L.config(self.zomboid).get("ativo")
            atualizar = None
            if tipo == "ok":
                for pid, mudou in res.items():
                    if isinstance(mudou, Exception):
                        self.situacao[pid] = ("✖ " + str(mudou), "erro")
                    elif pid == ativo and mudou:
                        self.situacao[pid] = ("⬆ Versão nova disponível", "aviso")
                        atualizar = pid
                    elif pid == ativo:
                        self.situacao[pid] = ("✔ Ativo e atualizado", "dentro")
                    else:
                        self.situacao[pid] = ("Instalado (inativo)" if not mudou else "Disponível", "")
            self.etapa.configure(text="Verificado às %s." % time.strftime("%H:%M"))
            self.preencher()
            self._agendar()
            if atualizar and self.auto.get():
                self.sincronizar(atualizar, silencioso=True)
        self._rodar(trabalho, fim)

    def _agendar(self):
        if getattr(self, "_timer", None):
            self.after_cancel(self._timer)
        self._timer = self.after(INTERVALO_MIN * 60 * 1000, lambda: self.verificar_tudo(True))

    def checar_launcher(self):
        """Pergunta ao GitHub em segundo plano; so a thread da tela mexe na tela (Tkinter nao aceita outra)."""
        res = {}
        th = threading.Thread(target=lambda: res.update(tag=nova_versao_launcher()), daemon=True)
        th.start()

        def espera():
            if th.is_alive():
                self.after(500, espera)
            elif res.get("tag"):
                self._mostrar_banner(res["tag"])
        self.after(500, espera)

    def _mostrar_banner(self, tag):
        self.banner.configure(text="⬆  Saiu o launcher %s: clique aqui para baixar." % tag, cursor="hand2")
        self.banner.bind("<Button-1>", lambda e: abrir("https://github.com/%s/releases/latest" % REPO))
        self.banner.pack(fill="x", padx=16, pady=(0, 6), after=self.lbl_pasta)

    def fechar(self):
        if self.ocupado and not messagebox.askyesno("Fechar", "Ainda está baixando. Fechar mesmo assim? "
                                                              "(continua de onde parou da próxima vez)"):
            return
        self.destroy()


if __name__ == "__main__":
    Launcher().mainloop()
    os._exit(0)
