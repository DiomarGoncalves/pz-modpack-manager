#!/usr/bin/env python3
"""Janela do gerenciador de modpacks de servidor (usa o modpack.py; sem IA).
Funciona no Linux (Steam normal ou Flatpak), no Windows e no macOS.

    Linux:   python3 modpack_gui.py
    Windows: dois cliques em "Abrir modpack (Windows).bat" (precisa do Python instalado)

1. Escolha o modpack no topo (ou crie um com "Novo modpack...", importando o .ini do servidor).
2. Cole o ID ou o link do mod e clique Adicionar (se nao estiver baixado, o programa abre
   a pagina na Steam, espera voce se inscrever e baixar, e adiciona sozinho).
3. Montar pacote -> publique no jogo (Workshop > Criar e atualizar itens > <pasta do modpack>).
4. Gerar .ini do servidor -> escolha o .ini atual; sai o <nome>_pronto.ini para subir.
"""
import os
import subprocess
import sys
import threading
import time
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import modpack as MP  # noqa: E402
import tema  # noqa: E402

ESPERA_MS = 3000          # de quanto em quanto tempo confere se a Steam baixou
ESPERA_MAX = 200          # ~10 minutos
ULTIMO = os.path.join(MP.PACKS, ".ultimo")


# Dicas (passar o mouse por cima) ---------------------------------------------------------

DICAS = {
    # topo
    "Novo modpack...": "Cria um modpack para outro servidor. Você dá o nome, a versão do jogo (branch) e, se quiser, "
                       "importa a lista de mods direto do .ini daquele servidor.",
    "Configurar...": "Muda o nome do modpack, o título que aparece na Workshop e a versão (branch) do jogo.",
    "Excluir...": "Apaga só a lista deste modpack no programa. A pasta de publicação e o item já publicado na Steam continuam.",
    "Importar...": "Traz um modpack de outra pasta ou de outro PC: escolha o modpack.json dele (fica em packs/<nome>/). "
                   "Use para levar um modpack de um PC para outro.",
    "Pastas...": "Mostra (e deixa trocar) onde o programa acha os mods baixados pela Steam e a pasta Zomboid "
                 "onde o pacote é montado. Normalmente ele acha sozinho.",
    "Adicionar": "Coloca no modpack o mod do ID/link digitado ao lado. Se ele tiver dependências, elas entram junto. "
                 "Se não estiver baixado, abre a página na Steam e espera baixar.",
    "Abrir na Steam": "Abre a página do mod na Steam (para ver detalhes ou se inscrever e baixar).",
    # aba do modpack
    "Remover selecionado": "Tira o(s) mod(s) selecionado(s) da lista e do Mods=. Depois monte o pacote de novo.",
    "Separar / juntar": "Separado = o mod fica FORA do pacote e o servidor baixa ele da Workshop original. "
                        "Clique de novo para colocar de volta dentro do pacote.",
    "Baixar os que faltam": "Baixa os mods da lista que ainda não estão no PC: automático (SteamCMD, sem conta) "
                            "ou abrindo as páginas na Steam para você se inscrever.",
    "Baixar de novo (versão nova)": "Baixa de novo pela SteamCMD os mods selecionados, pegando a versão mais nova da "
                                    "Workshop (os baixados no automático não se atualizam sozinhos).",
    "Montar pacote": "Monta a pasta do pacote para publicar. Só copia os mods novos; os que já estavam ficam "
                     "congelados na versão de antes. Confere as regras da Workshop antes. Depois publique no jogo.",
    "ATUALIZAR MODS (versão nova)": "Pega a versão nova SÓ dos mods que a Steam já atualizou e monta o pacote. "
                                    "Teste no seu jogo antes, publique e reinicie o servidor.",
    "Atualizar selecionado": "Pega a versão que a Steam tem baixada agora apenas do(s) mod(s) selecionado(s) e monta o pacote.",
    "Atualizar TODOS e montar": "Pega a versão atual de TODOS os mods e monta o pacote. Use só depois de testar.",
    "Gerar .ini do servidor...": "Escolha o .ini atual do servidor: sai uma cópia com o MESMO nome na pasta 'pronto', "
                                 "com o Mods= e o WorkshopItems= certos para este modpack, já conferida.",
    "Ver publicação na Steam": "Confere se o pacote aparece na Steam para quem está de fora (não privado, não 0 B) "
                               "e se o que está publicado é o mesmo pacote montado aqui.",
    "Conferir .ini do servidor...": "Confere um .ini de servidor contra este modpack: Mods= vazio, mods faltando, "
                                    "pacote ausente, itens repetidos e ordem das dependências.",
    "Conferir log (servidor ou jogo)...": "Lê o console.txt do jogo ou o log do servidor e diz quantos mods carregaram, "
                                          "quais falharam, erros da Workshop e quais mods deram erro de Lua.",
    "Abrir pasta do pacote": "Abre a pasta onde o pacote fica montado (a que o jogo publica na Workshop).",
    "Recarregar lista": "Lê de novo a lista e a situação de cada mod (use depois de baixar ou mudar algo).",
    # aba do PC
    "ADICIONAR AO MODPACK": "Coloca no modpack os mods selecionados nesta lista (com as dependências). "
                            "Dá para selecionar vários com Ctrl/Shift ou dar dois cliques em um.",
    "Recarregar lista do PC": "Lê de novo todos os mods baixados pela Steam neste PC.",
    "Só mods da B42": "Esconde os mods que só funcionam na Build 41.",
    "Só os que não estão no modpack": "Mostra só os mods baixados que ainda não estão neste modpack.",
    # aba procurar na Steam
    "Procurar": "Procura mods do Project Zomboid na Workshop da Steam (sem login). Sem texto, mostra os mais inscritos. "
                "Também aceita o número ou o link de um mod.",
    "Só Build 42": "Mostra só os mods marcados como Build 42 na Steam (os que funcionam na versão do servidor).",
    "ADICIONAR SELECIONADOS": "Coloca no modpack os mods selecionados (com as dependências). Os que ainda não estão "
                              "baixados abrem na Steam: clique em Inscrever-se e o programa espera baixar e adiciona sozinho.",
    "◀ Página anterior": "Volta para a página anterior de resultados.",
    "Próxima página ▶": "Mostra os próximos 30 resultados.",
    # aba sem Steam
    "Exportar zip nosteam...": "DONO DO SERVIDOR: gera um .zip com TODOS os mods do modpack (os do pacote montado e os "
                               "separados) dentro de mods/. Serve para o servidor -nosteam e para mandar aos jogadores.",
    "Gerar .ini nosteam...": "DONO DO SERVIDOR: escolha o .ini atual do servidor. Sai uma cópia na pasta 'pronto_nosteam' "
                             "com o Mods= certo e o WorkshopItems= vazio (sem Steam não existe Workshop).",
    "Instalar .zip do modpack...": "JOGADOR: escolha o .zip que o dono do servidor mandou. O programa apaga a versão "
                                   "velha desse modpack e coloca os mods em Zomboid/mods. Seus outros mods não são tocados.",
    "Desinstalar selecionado": "Apaga de Zomboid/mods só as pastas que o programa instalou para o modpack selecionado "
                               "(use antes de voltar a jogar em servidor da Steam com os mesmos mods).",
    "Abrir pasta mods": "Abre a pasta Zomboid/mods deste PC, onde ficam os mods do modo sem Steam.",
    "Trocar pasta Zomboid...": "Escolha a pasta Zomboid do jogo neste PC (a que tem Saves/ e mods/). "
                               "Normalmente o programa acha sozinho.",
    # janelas
    "Escolher...": "Escolher a pasta na mão.",
    "Salvar": "Guarda as pastas escolhidas para esta máquina.",
    "Achar sozinho": "Volta a deixar o programa achar as pastas sozinho (Windows, Linux, Flatpak, macOS).",
}


def situacao_simples(sit):
    """Situacao do mod em portugues simples: (cor, texto curto, explicacao com o que fazer)."""
    if sit.startswith("separado"):
        return ("separado", "◇ Fora do pacote",
                "Este mod fica FORA do pacote: o servidor baixa ele direto da Workshop original. "
                "Para colocar dentro do pacote: botão direito > Separar / juntar.")
    if "APAGADA" in sit:
        return ("erro", "✖ Pasta apagada",
                "A cópia congelada deste mod sumiu da pasta do pacote. Use o botão do passo ② para recuperar.")
    if "NAO BAIXADO" in sit:
        return ("erro", "✖ Falta baixar",
                "Este mod está na lista mas não está baixado neste PC. Passo ① > 'Baixar os que faltam'.")
    if "VERSAO NOVA" in sit:
        return ("aviso", "⬆ Versão nova",
                "O autor atualizou este mod. O pacote continua com a versão antiga (congelada) até você mandar "
                "atualizar: botão direito > Atualizar este, ou passo ② > Atualizar e montar.")
    if "a toa" in sit:
        return ("aviso", "○ Nenhum mod ligado",
                "Este item está na lista, mas nenhum dos mods dele está ligado no servidor (fora do Mods=), "
                "então ele não faz nada agora. Acontece com itens que têm vários mods ou variantes. "
                "Botão direito > 'Escolher quais mods ligar...' para usar, ou 'Remover do modpack'.")
    if sit.startswith("novo") or "falta montar" in sit:
        return ("aviso", "➕ Novo (falta montar)",
                "Mod novo na lista. Ele entra no pacote quando você clicar em 'Montar pacote' (passo ②).")
    return ("ok", "✔ No pacote",
            "Este mod está dentro do pacote, na versão congelada. Os jogadores recebem exatamente esta versão.")


class EntradaDica(ttk.Entry):
    """Campo com um texto de exemplo apagado enquanto esta vazio (placeholder)."""

    def __init__(self, master, dica, **kw):
        self.var = tk.StringVar()
        super().__init__(master, textvariable=self.var, **kw)
        self.dica, self.vazio = dica, False
        self.bind("<FocusIn>", self._entrar, add="+")
        self.bind("<FocusOut>", self._sair, add="+")
        self._sair()

    def _sair(self, _e=None):
        if not self.var.get():
            self.vazio = True  # antes do set: quem observa a variavel ja ve "vazio"
            self.configure(style="Dica.TEntry")
            self.var.set(self.dica)

    def _entrar(self, _e=None):
        if self.vazio:
            self.vazio = False
            self.configure(style="TEntry")
            self.var.set("")

    def valor(self):
        return "" if self.vazio else self.var.get()

    def definir(self, texto):
        self._entrar()
        self.var.set(texto)
        if not texto and self.focus_get() is not self:
            self._sair()

    def limpar(self):
        self.definir("")


class Dica:
    """Caixinha de explicação que aparece quando o mouse para em cima de um widget."""

    def __init__(self, widget, texto, espera=500):
        self.widget, self.texto, self.espera = widget, texto, espera
        self.janela = self.agendado = None
        widget.bind("<Enter>", self._agendar, add="+")
        widget.bind("<Leave>", self._esconder, add="+")
        widget.bind("<ButtonPress>", self._esconder, add="+")

    def _agendar(self, _e=None):
        self._esconder()
        self.agendado = self.widget.after(self.espera, self._mostrar)

    def _mostrar(self):
        if self.janela or not self.widget.winfo_exists():
            return
        x = self.widget.winfo_rootx() + 12
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 6
        self.janela = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry("+%d+%d" % (x, y))
        tk.Label(tw, text=self.texto, justify="left", wraplength=360, background=tema.cor("dica"),
                 foreground=tema.cor("dica_t"), relief="solid", borderwidth=1, padx=10, pady=6,
                 highlightthickness=0).pack()

    def _esconder(self, _e=None):
        if self.agendado:
            self.widget.after_cancel(self.agendado)
            self.agendado = None
        if self.janela:
            self.janela.destroy()
            self.janela = None


def aplicar_dicas(raiz):
    """Poe a dica de DICAS em todo botao/caixa de marcar dentro de "raiz" (pelo texto)."""
    for w in raiz.winfo_children():
        if isinstance(w, (ttk.Button, ttk.Checkbutton)) and not getattr(w, "_tem_dica", False):
            texto = str(w.cget("text"))
            if texto in DICAS:
                Dica(w, DICAS[texto])
                w._tem_dica = True
        aplicar_dicas(w)


# Layout responsivo ------------------------------------------------------------------------

class Fluxo(ttk.Frame):
    """Poe os widgets lado a lado e QUEBRA A LINHA quando nao cabem (como texto).
    preencher=True: um por linha, ocupando a largura toda (coluna de botoes).
    None em add() = separador (espaco extra)."""

    def __init__(self, master, espaco=4, largura_item=None, largura_secao=92, **kw):
        super().__init__(master, **kw)
        self.itens, self.espaco, self.largura_item = [], espaco, largura_item
        self.largura_secao = largura_secao
        self.preencher = False
        self._ultima = None
        self.bind("<Configure>", lambda e: self.arrumar())

    def add(self, w):
        self.itens.append(w)
        return w

    def quebra(self):
        self.itens.append(None)

    def altura_necessaria(self, largura, preencher=None):
        antes = self.preencher
        if preencher is not None:
            self.preencher = preencher
        try:
            return self._calcular(largura, aplicar=False)
        finally:
            self.preencher = antes

    def arrumar(self):
        largura = max(self.winfo_width(), 1)
        alt = self._calcular(largura, aplicar=True)
        if not self.preencher and int(self.cget("height") or 0) != alt:
            self.configure(height=alt)

    def _calcular(self, largura, aplicar):
        """Titulos de secao (w._secao): em coluna ocupam a linha toda; em linha comecam uma linha nova,
        com largura fixa, e os botoes daquela secao quebram alinhados depois do titulo."""
        e = self.espaco
        x = y = h = 0
        recuo = 0
        for w in self.itens:
            if w is None:
                if self.preencher:
                    y += e * 3
                else:
                    x += e * 4
                continue
            secao = getattr(w, "_secao", False)
            if secao and not self.preencher:
                if x > 0:
                    x, y, h = 0, y + h + e * 2, 0
                ww = min(self.largura_secao, largura)
                wh = w.winfo_reqheight()
                if aplicar:
                    w.place(x=0, y=y, width=ww, height=wh)
                recuo = x = ww + e
                h = max(h, wh)
                continue
            if self.preencher or secao:
                recuo = 0
            ww = largura if self.preencher else (self.largura_item or w.winfo_reqwidth())
            wh = w.winfo_reqheight()
            if x > recuo and x + ww > largura:
                x, y, h = recuo, y + h + e, 0
            if aplicar:
                w.place(x=x, y=y, width=min(ww, largura), height=wh)
            if self.preencher:
                y += wh + e
            else:
                x += ww + e
                h = max(h, wh)
        return y if self.preencher else y + h


def secao(fluxo, texto, cmd):
    """Item do painel de botoes: "#TITULO" = titulo de secao; "!Texto" = botao principal (destaque)."""
    if texto.startswith("#"):
        if fluxo.itens:
            fluxo.quebra()
        rotulo = ttk.Label(fluxo, text=texto[1:], style="Secao.TLabel", anchor="w")
        rotulo._secao = True
        return fluxo.add(rotulo)
    if texto.startswith("!"):
        return fluxo.add(ttk.Button(fluxo, text=texto[1:], command=cmd, style="Accent.TButton"))
    return fluxo.add(ttk.Button(fluxo, text=texto, command=cmd))


class PainelAdaptavel:
    """Tabela + painel de botoes: botoes em coluna a direita quando cabem; senao embaixo,
    em varias colunas."""

    def __init__(self, pai, tabela_frame, botoes, largura_lado=250):
        self.pai, self.tab, self.botoes, self.largura_lado = pai, tabela_frame, botoes, largura_lado
        self.modo = None
        pai.rowconfigure(0, weight=1)
        pai.columnconfigure(0, weight=1)
        pai.bind("<Configure>", lambda e: self.decidir(e.width, e.height), add="+")

    def decidir(self, largura, altura):
        cabe_lado = largura >= 860 and self.botoes.altura_necessaria(self.largura_lado, preencher=True) <= altura
        modo = "lado" if cabe_lado else "baixo"
        if modo == self.modo:
            return
        self.modo = modo
        self.tab.grid_forget()
        self.botoes.grid_forget()
        self.tab.grid(row=0, column=0, sticky="nsew")
        if modo == "lado":
            self.botoes.preencher = True
            self.botoes.configure(width=self.largura_lado)
            self.botoes.grid(row=0, column=1, sticky="ns", padx=(8, 0))
            self.pai.rowconfigure(1, weight=0)
        else:
            self.botoes.preencher = False
            self.botoes.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(6, 0))
        self.botoes.after_idle(self.botoes.arrumar)


def colunas_proporcionais(tree, pesos):
    """Larguras das colunas acompanham a largura da tabela (pesos relativos)."""
    total = float(sum(pesos.values()))

    def ajustar(e):
        largura = max(e.width - 4, 100)
        for c, p in pesos.items():
            tree.column(c, width=int(largura * p / total))
    tree.bind("<Configure>", ajustar, add="+")


def abrir(alvo):
    """Abre link ou pasta no programa padrao do sistema."""
    try:
        if os.name == "nt":
            os.startfile(alvo)  # noqa: S606 - Windows
        elif sys.platform == "darwin":
            subprocess.Popen(["open", alvo])
        else:
            subprocess.Popen(["xdg-open", alvo])
    except OSError as e:
        messagebox.showerror("Modpack", "Nao consegui abrir %s\n%s" % (alvo, e))


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("PZ Modpack Manager %s - Project Zomboid" % MP.VERSAO)
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        w, h = min(1180, sw - 40), min(780, sh - 70)
        self.geometry("%dx%d+%d+%d" % (w, h, max(0, (sw - w) // 2), max(0, (sh - h) // 3)))
        self.minsize(620, 420)
        self.cfg = None
        self.esperando = None  # (item, tentativas)
        self.modo_tema = MP.local().get("tema", "escuro")
        tema.aplicar(self, self.modo_tema)
        self._montar_tela()
        self._pintar()
        self._divisao_ok = False
        self.divisao.bind("<Configure>", lambda e: self._ajustar_divisao(), add="+")
        aplicar_dicas(self)
        Dica(self.combo, "Escolha qual modpack (servidor) você está editando. Cada servidor tem o seu.")
        Dica(self.entrada, "Cole aqui o número do mod na Workshop ou o link da página dele e clique em Adicionar.")
        Dica(self.busca_entry, "Filtra a lista pelo nome do mod, pelo número na Workshop ou pelo ID do mod.")
        self.protocol("WM_DELETE_WINDOW", self.fechar)
        self.recarregar_packs(self._ultimo())
        self.carregar_baixados()
        for p in MP.pastas_ok():
            self.log("ATENCAO: " + p)

    # Tela ------------------------------------------------------------------------
    def _montar_tela(self):
        self.columnconfigure(1, weight=1)
        self.rowconfigure(0, weight=1)
        self.menus = []
        self._lateral()

        principal = ttk.Frame(self, padding=(18, 14, 18, 10))
        principal.grid(row=0, column=1, sticky="nsew")
        # Paginas em cima e registro embaixo, com divisoria arrastavel
        self.divisao = ttk.PanedWindow(principal, orient="vertical")
        self.divisao.pack(fill="both", expand=True)
        self.abas = ttk.Notebook(self.divisao, style="Paginas.TNotebook")
        self.divisao.add(self.abas, weight=5)
        self.abas.bind("<<NotebookTabChanged>>", lambda e: self._marcar_nav())

        self._pagina_modpack()
        self._aba_busca()
        self._pagina_pc()
        self._aba_nosteam()
        self.paginas = [self.pag_modpack, self.pag_busca, self.pag_pc, self.aba_ns]

        # Registro (log)
        baixo = ttk.Frame(self.divisao, padding=(0, 8, 0, 0))
        self.divisao.add(baixo, weight=1)
        cab = ttk.Frame(baixo)
        cab.pack(fill="x", pady=(0, 4))
        ttk.Label(cab, text="REGISTRO", style="Secao.TLabel").pack(side="left")
        ttk.Button(cab, text="Limpar", style="Pequeno.TButton", command=self.limpar_registro).pack(side="right")
        corpo = ttk.Frame(baixo)
        corpo.pack(fill="both", expand=True)
        self.texto = tk.Text(corpo, height=5, wrap="word", state="disabled", font="TkFixedFont")
        rolagem = ttk.Scrollbar(corpo, orient="vertical", command=self.texto.yview)
        self.texto.configure(yscrollcommand=rolagem.set)
        self.texto.pack(side="left", fill="both", expand=True)
        rolagem.pack(side="left", fill="y")
        self._marcar_nav()

    def _lateral(self):
        lat = ttk.Frame(self, style="Lateral.TFrame", padding=(14, 16, 14, 14), width=236)
        lat.grid(row=0, column=0, sticky="ns")
        lat.grid_propagate(False)
        lat.pack_propagate(False)
        ttk.Label(lat, text="☣  MODPACKS PZ", style="LateralMarca.TLabel").pack(anchor="w")
        ttk.Label(lat, text="Project Zomboid  ·  v%s" % MP.VERSAO,
                  style="LateralSecao.TLabel").pack(anchor="w", pady=(0, 18))

        ttk.Label(lat, text="MODPACK (SERVIDOR)", style="LateralSecao.TLabel").pack(anchor="w", pady=(0, 4))
        self.combo = ttk.Combobox(lat, state="readonly")
        self.combo.pack(fill="x")
        self.combo.bind("<<ComboboxSelected>>", lambda e: self.trocar_pack())
        linha = ttk.Frame(lat, style="Lateral.TFrame")
        linha.pack(fill="x", pady=(6, 20))
        ttk.Button(linha, text="＋ Novo", style="Pequeno.TButton", command=self.novo_pack).pack(side="left", fill="x", expand=True)
        mais = ttk.Menubutton(linha, text="Mais", style="TMenubutton")
        m = tk.Menu(mais, tearoff=False)
        m.add_command(label="Configurar nome, título e versão...", command=self.configurar_pack)
        m.add_command(label="Importar modpack (modpack.json)...", command=self.importar_pack)
        m.add_separator()
        m.add_command(label="Excluir este modpack...", command=self.excluir_pack)
        mais["menu"] = m
        self.menus.append(m)
        mais.pack(side="left", padx=(6, 0))
        Dica(mais, "Configurar, importar ou excluir modpacks.")

        ttk.Label(lat, text="MENU", style="LateralSecao.TLabel").pack(anchor="w", pady=(0, 4))
        self.nav = []
        for i, texto in enumerate(("📦   Modpack", "🔍   Procurar na Steam", "💾   Mods no PC", "🛰   Sem Steam (nosteam)")):
            b = ttk.Button(lat, text=texto, style="Nav.TButton", command=lambda i=i: self.ir(i))
            b.pack(fill="x", pady=1)
            self.nav.append(b)

        rodape = ttk.Frame(lat, style="Lateral.TFrame")
        rodape.pack(side="bottom", fill="x")
        ttk.Button(rodape, text="⚙   Pastas do PC", style="Nav.TButton", command=self.pastas).pack(fill="x", pady=1)
        self.b_tema = ttk.Button(rodape, style="Nav.TButton", command=self.trocar_tema)
        self.b_tema.pack(fill="x", pady=1)
        Dica(self.b_tema, "Troca entre o tema escuro e o claro (fica guardado para a próxima vez).")

    def ir(self, i):
        self.abas.select(self.paginas[i])

    def _marcar_nav(self):
        if not getattr(self, "paginas", None):
            return
        atual = self.abas.index("current")
        for i, b in enumerate(self.nav):
            b.configure(style="NavAtivo.TButton" if i == atual else "Nav.TButton")

    def _cabecalho(self, pai, titulo, sub):
        """Titulo grande + explicacao curta no topo de cada pagina. Devolve (rotulo_titulo, rotulo_sub)."""
        cab = ttk.Frame(pai)
        cab.pack(fill="x", pady=(0, 12))
        t = ttk.Label(cab, text=titulo, style="Pagina.TLabel")
        t.pack(anchor="w")
        st = ttk.Label(cab, text=sub, style="Subtitulo.TLabel", justify="left")
        st.pack(fill="x", anchor="w")
        st.bind("<Configure>", lambda e: st.configure(wraplength=max(e.width - 8, 200)))
        return t, st

    def _pagina_modpack(self):
        pag = ttk.Frame(self.abas)
        self.pag_modpack = pag
        self.abas.add(pag, text="Modpack")
        self.titulo_pack, self.info_pack = self._cabecalho(pag, "Modpack", "")

        # Passo a passo
        self.passos_frame = ttk.Frame(pag)
        self.passos_frame.pack(fill="x", pady=(0, 12))
        self.passos = []
        for n, titulo in enumerate(("Mods", "Montar pacote", "Arquivo .ini do servidor"), 1):
            c = ttk.Frame(self.passos_frame, style="Cartao.TFrame", padding=(12, 10))
            topo = ttk.Frame(c, style="Cartao.TFrame")
            topo.pack(fill="x")
            ttk.Label(topo, text="①②③"[n - 1], style="Numero.TLabel").pack(side="left", padx=(0, 8))
            ttk.Label(topo, text=titulo, style="CartaoTitulo.TLabel").pack(side="left")
            st = ttk.Label(c, style="CartaoTexto.TLabel", justify="left")
            st.pack(fill="x", pady=(6, 8))
            st.bind("<Configure>", lambda e, r=st: r.configure(wraplength=max(e.width - 4, 120)))
            linha = ttk.Frame(c, style="Cartao.TFrame")
            linha.pack(fill="x")
            b = ttk.Button(linha)
            b.pack(side="left")
            b2 = ttk.Button(linha, style="Pequeno.TButton")
            self.passos.append({"frame": c, "status": st, "botao": b, "botao2": b2})
        self.passos_frame.bind("<Configure>", lambda e: self._arrumar_passos(e.width))

        # Barra da tabela: adicionar por ID | filtro | mais acoes
        barra = Fluxo(pag, espaco=6)
        barra.pack(fill="x", pady=(0, 8))
        self.entrada = barra.add(EntradaDica(barra, "Cole o ID ou o link do mod na Workshop...", width=40))
        self.entrada.bind("<Return>", lambda e: self.adicionar())
        barra.add(ttk.Button(barra, text="＋ Adicionar", command=self.adicionar, style="Accent.TButton"))
        barra.add(None)
        self.filtro_pack = barra.add(EntradaDica(barra, "🔍 Filtrar a lista...", width=26))
        self.filtro_pack.var.trace_add("write", lambda *a: self.atualizar_lista(recarregar=False))
        self.b_mais = barra.add(ttk.Menubutton(barra, text="Mais ações"))
        m = tk.Menu(self.b_mais, tearoff=False)
        for texto, cmd in (("Remover selecionado", self.remover),
                           ("Separar / juntar (fora ou dentro do pacote)", self.separar_juntar),
                           ("Abrir na Steam", self.abrir_steam_sel),
                           ("Atualizar selecionado (versão baixada agora)", self.atualizar_selecionado),
                           (None, None),
                           ("Baixar os que faltam", self.abrir_faltando),
                           ("Atualizar mods com versão nova", self.atualizar_novidades),
                           ("Atualizar TODOS e montar", self.montar_tudo),
                           (None, None),
                           ("Ver publicação na Steam", self.ver_publicacao),
                           ("Conferir .ini do servidor...", self.conferir_ini),
                           ("Conferir log (servidor ou jogo)...", self.conferir_log),
                           (None, None),
                           ("Restaurar do pacote publicado", self.restaurar_publicado),
                           ("Abrir pasta do pacote", self.abrir_pasta),
                           ("Recarregar lista", self.atualizar_lista)):
            if texto is None:
                m.add_separator()
            else:
                m.add_command(label=texto, command=cmd)
        self.b_mais["menu"] = m
        self.menus.append(m)
        Dica(self.b_mais, "Outras ações: remover, separar, atualizar, conferir .ini/log, abrir a pasta... "
                          "(dica: clique com o botão direito em cima de um mod).")

        tab = ttk.Frame(pag)
        tab.pack(fill="both", expand=True)
        cols = ("item", "nome", "mods", "situacao")
        self.tabela = ttk.Treeview(tab, columns=cols, show="headings", selectmode="extended")
        for c, t in (("item", "Item"), ("nome", "Nome"), ("mods", "Mods ativos"), ("situacao", "Situação")):
            self.tabela.heading(c, text=t)
            self.tabela.column(c, width=100, minwidth=60, anchor="w")
        colunas_proporcionais(self.tabela, {"item": 11, "nome": 33, "mods": 26, "situacao": 30})
        rol = ttk.Scrollbar(tab, orient="vertical", command=self.tabela.yview)
        self.tabela.configure(yscrollcommand=rol.set)
        self.tabela.pack(side="left", fill="both", expand=True)
        rol.pack(side="left", fill="y")
        self.tabela.bind("<Delete>", lambda e: self.remover())
        self.tabela.bind("<<TreeviewSelect>>", lambda e: self.mostrar_explicacao())
        self.explicacao = ttk.Label(pag, style="Sutil.TLabel", justify="left", padding=(2, 6, 0, 0))
        self.explicacao.pack(fill="x", side="bottom", before=tab)  # antes da tabela: nunca fica espremida
        self.explicacao.bind("<Configure>", lambda e: self.explicacao.configure(wraplength=max(e.width - 8, 200)))

        # botao direito
        ctx = tk.Menu(self.tabela, tearoff=False)
        for texto, cmd in (("Abrir na Steam", self.abrir_steam_sel),
                           ("Atualizar este (versão baixada agora)", self.atualizar_selecionado),
                           ("Escolher quais mods ligar...", self.escolher_ligados),
                           ("Separar / juntar", self.separar_juntar),
                           (None, None),
                           ("Remover do modpack", self.remover)):
            if texto is None:
                ctx.add_separator()
            else:
                ctx.add_command(label=texto, command=cmd)
        self.menus.append(ctx)
        self.tabela.bind("<Button-3>", lambda e: self._menu_linha(e, self.tabela, ctx))

    def mostrar_explicacao(self):
        sel = self.tabela.selection()
        exp = getattr(self, "_explicacoes", {})
        if len(sel) == 1 and sel[0] in exp:
            curto, explica = exp[sel[0]]
            self.explicacao.configure(text="%s:  %s" % (curto, explica))
        elif sel:
            self.explicacao.configure(text="%d mods selecionados. Botão direito para as ações." % len(sel))
        else:
            self.explicacao.configure(text="Clique num mod para ver o que a situação dele significa. "
                                           "Botão direito: ações do mod.")

    def escolher_ligados(self):
        """Abre a escolha de quais mods (variantes) de um item ficam ligados no Mods=."""
        sel = self.selecionados()
        if not sel or not self.precisa_pack():
            return
        item = sel[0]
        sp = MP.steam_pastas(item)
        if not sp:
            messagebox.showinfo("Escolher mods", "Este item não está baixado neste PC: baixe antes (passo ①).")
            return
        opcoes = [(i, p["nome"]) for p in sp for i in p["ids"]]
        escolha = self.escolher_mods(item, opcoes)
        if not escolha:
            return
        ok, msgs, _ = MP.adicionar(self.cfg, item, escolha)
        self.log(*msgs)
        self.atualizar_lista()

    def _menu_linha(self, e, tree, menu):
        linha = tree.identify_row(e.y)
        if not linha:
            return
        if linha not in tree.selection():
            tree.selection_set(linha)
        menu.tk_popup(e.x_root, e.y_root)

    def _arrumar_passos(self, largura):
        colunas = 3 if largura >= 760 else 1
        if getattr(self, "_colunas_passos", None) == colunas:
            return
        self._colunas_passos = colunas
        for i in range(3):
            self.passos_frame.columnconfigure(i, weight=1 if i < colunas else 0, uniform="passo" if i < colunas else "")
        for n, p in enumerate(self.passos):
            p["frame"].grid(row=n // colunas, column=n % colunas, sticky="nsew",
                            padx=(0 if n % colunas == 0 else 8, 0), pady=(0 if n < colunas else 8, 0))

    def _passo(self, n, texto, nivel, botao, cmd, destaque=False, botao2=None, cmd2=None):
        p = self.passos[n]
        p["status"].configure(text=texto, style={"ok": "CartaoOk.TLabel", "aviso": "CartaoAviso.TLabel",
                                                "erro": "CartaoErro.TLabel"}.get(nivel, "CartaoTexto.TLabel"))
        p["botao"].configure(text=botao, command=cmd, style="Accent.TButton" if destaque else "TButton")
        if botao2:
            p["botao2"].configure(text=botao2, command=cmd2)
            p["botao2"].pack(side="left", padx=(6, 0))
        else:
            p["botao2"].pack_forget()

    def atualizar_passos(self):
        """Situacao de cada etapa (mods -> montar -> .ini) e o botao do que fazer agora."""
        if not self.cfg:
            self._passo(0, "Crie o primeiro modpack (um para cada servidor).", "", "＋ Novo modpack", self.novo_pack, True)
            for n, txt in ((1, "Depois de escolher os mods."), (2, "Depois de montar e publicar.")):
                self._passo(n, txt, "", "—", None)
                self.passos[n]["botao"].state(["disabled"])
            return
        for p in self.passos:
            p["botao"].state(["!disabled"])
        cfg = self.cfg
        # 1) mods
        faltam = MP.faltando(cfg)
        nitens = len(cfg["itens"])
        if faltam:
            self._passo(0, "⚠ %d mod(s) da lista ainda não estão baixados neste PC." % len(faltam), "aviso",
                        "Baixar os que faltam", self.abrir_faltando, True)
        else:
            self._passo(0, "✔ %d itens na lista (%d mods ligados no servidor)." % (nitens, len(cfg["mods"])), "ok",
                        "🔍 Procurar mais mods", lambda: self.ir(1))
        # 2) montar
        # so conta o que realmente entra ao montar (item sem nenhum mod ligado nao entra)
        sem_montar = [i for i, _, _, sit in getattr(self, "_status_cache", []) if sit.startswith("novo")]
        novos = MP.com_versao_nova(cfg)
        montado = cfg.get("montado") or {}
        quando = time.strftime("%d/%m %H:%M", time.localtime(montado["quando"])) if montado.get("quando") else None
        apagadas = MP.pastas_congeladas_faltando(cfg)
        pub = MP.pacote_id(cfg)
        if apagadas and pub:
            self._passo(1, "✖ A pasta do pacote foi apagada. Dá para recuperar as mesmas versões a partir do "
                           "pacote publicado.", "erro", "Restaurar do publicado", self.restaurar_publicado, True)
        elif apagadas:
            self._passo(1, "✖ A pasta do pacote foi apagada. Monte de novo (usa as versões baixadas agora).",
                        "erro", "Montar de novo", self.montar_tudo, True)
        elif sem_montar or not montado:
            self._passo(1, ("⚠ %d mod(s) novo(s) ainda fora do pacote. Monte e depois publique no jogo."
                            % len(sem_montar)) if sem_montar else "⚠ O pacote ainda não foi montado.",
                        "aviso", "Montar pacote", self.montar, True)
        elif novos:
            self._passo(1, "⚠ %d mod(s) têm versão nova. Teste no seu jogo e atualize quando quiser." % len(novos),
                        "aviso", "Atualizar e montar", self.atualizar_novidades, True, "Como publicar?", self.como_publicar)
        else:
            self._passo(1, "✔ Montado em %s com %d mods. Se ainda não publicou essa montagem, publique no jogo."
                        % (quando, montado.get("mods", 0)), "ok", "Montar de novo", self.montar, False,
                        "Como publicar?", self.como_publicar)
        # 3) .ini
        estado, msg = MP.situacao_ini(cfg)
        pronto = cfg.get("ini_pronto") or ""
        orig_ok = bool(cfg.get("ini_servidor") and os.path.isfile(cfg["ini_servidor"]))
        if not pub:
            self._passo(2, "Primeiro monte e publique o pacote no jogo. Depois o .ini é feito aqui.", "",
                        "Como publicar?", self.como_publicar)
        elif estado == "nenhum":
            self._passo(2, "Escolha o .ini atual do servidor (baixe do painel): o app salva uma CÓPIA certa numa "
                           "pasta 'pronto' ao lado dele. Servidor novo, sem .ini? Use 'Criar .ini novo'.", "aviso",
                        "Escolher .ini do servidor...", self.gerar_ini, True, "Criar .ini novo...", self.criar_ini_novo)
        elif estado == "desatualizado":
            self._passo(2, "⚠ O .ini pronto está desatualizado (%s)." % msg, "aviso", "Atualizar .ini",
                        self.atualizar_ini if orig_ok else self.gerar_ini, True, "Usar outro .ini...", self.gerar_ini)
        elif estado == "sumiu":
            self._passo(2, "⚠ %s" % msg, "aviso", "Gerar de novo", self.atualizar_ini if orig_ok else self.gerar_ini,
                        True, "Usar outro .ini...", self.gerar_ini)
        else:
            self._passo(2, "✔ Pronto para subir no servidor (%s):\n%s" % (msg, pronto), "ok",
                        "Abrir pasta do .ini", lambda: abrir(os.path.dirname(pronto)), True,
                        "Usar outro .ini...", self.gerar_ini)

    def criar_ini_novo(self):
        if not self.precisa_pack():
            return
        padrao = MP.slug(self.cfg.get("nome") or "servertest")

        def feito(nome):
            ok, msgs = MP.criar_ini_novo(self.cfg, nome)
            self.log(*msgs)
            if ok:
                self._aviso_ini(self.cfg["ini_pronto"], "Criado com só o essencial (Mods= e WorkshopItems=). O servidor "
                                "completa as outras opções com os valores padrão na primeira vez que ligar.\n"
                                "O nome do arquivo tem que ser o -servername do servidor.\n\n")
            else:
                messagebox.showerror("Criar .ini", "\n\n".join(msgs))
            self.atualizar_lista()
        nome = simpledialog.askstring("Criar .ini novo", "Nome do servidor (o -servername; vira <nome>.ini):",
                                      initialvalue=padrao, parent=self)
        if nome:
            feito(nome)

    def atualizar_ini(self):
        if not self.precisa_pack():
            return
        ok, msgs = MP.atualizar_ini(self.cfg)
        self.log(*msgs)
        if not ok:
            return self.gerar_ini()
        self._aviso_ini(self.cfg.get("ini_pronto"))
        self.atualizar_lista()

    def _aviso_ini(self, caminho, extra=""):
        if messagebox.askyesno("Arquivo .ini pronto", extra + "O .ini certo foi salvo em:\n\n%s\n\n"
                               "Suba ESTE arquivo no painel do servidor, em Zomboid/Server/, com o servidor desligado.\n"
                               "(O seu .ini original não foi alterado.)\n\nAbrir a pasta agora?" % caminho):
            abrir(os.path.dirname(caminho))

    def restaurar_publicado(self):
        """Recria a pasta do pacote a partir do pacote publicado baixado (versoes congeladas exatas)."""
        if not self.precisa_pack():
            return
        pub = MP.pacote_id(self.cfg)
        if not pub:
            messagebox.showinfo("Restaurar", "Este modpack ainda não foi publicado: não há de onde restaurar.")
            return
        if MP.pasta_do_item(pub) is None:
            self.obter_downloads([pub], [], "Para restaurar, o pacote publicado (%s) precisa estar baixado neste PC.\n"
                                            "Depois que baixar, clique em 'Restaurar do publicado' de novo." % pub)
            return
        self.config(cursor="watch")
        self.update()
        try:
            ok, msgs = MP.restaurar_do_publicado(self.cfg)
        finally:
            self.config(cursor="")
        self.log(*msgs)
        (messagebox.showinfo if ok else messagebox.showerror)("Restaurar do publicado", "\n\n".join(msgs))
        self.atualizar_lista()

    def como_publicar(self):
        if not self.precisa_pack():
            return
        messagebox.showinfo("Como publicar", "Depois de montar, publique o pacote pelo próprio jogo:\n\n"
                                             "1. Abra o Project Zomboid (versão %s).\n"
                                             "2. Menu principal > Workshop > Criar e atualizar itens.\n"
                                             "3. Escolha '%s' e clique em Publicar/Atualizar.\n"
                                             "4. Espere aparecer 'success updating item'.\n\n"
                                             "Os jogadores não precisam fazer nada: ao entrar no servidor, a Steam "
                                             "baixa a versão nova sozinha." % (self.cfg["branch"], self.cfg["pasta"]))

    def _pagina_pc(self):
        pc = ttk.Frame(self.abas)
        self.pag_pc = pc
        self.abas.add(pc, text="Mods no PC")
        self._cabecalho(pc, "Mods no PC", "Tudo o que já está baixado neste computador (pela Steam ou pelo download "
                                          "automático). Dois cliques adiciona ao modpack.")
        moldura2 = ttk.Frame(pc, padding=(0, 0, 0, 8))
        moldura2.pack(fill="x")
        filtro = Fluxo(moldura2, espaco=8)
        filtro.pack(fill="x")
        self.filtro = filtro
        self.busca_entry = filtro.add(EntradaDica(filtro, "🔍 Procurar por nome ou ID...", width=34))
        self.busca = self.busca_entry.var
        self.busca.trace_add("write", lambda *a: self.preencher_baixados())
        self.so_b42 = tk.BooleanVar(value=True)
        filtro.add(ttk.Checkbutton(filtro, text="Só mods da B42", variable=self.so_b42, command=self.preencher_baixados))
        self.so_fora = tk.BooleanVar(value=False)
        filtro.add(ttk.Checkbutton(filtro, text="Só os que não estão no modpack", variable=self.so_fora,
                                   command=self.preencher_baixados))
        self.conta_pc = filtro.add(ttk.Label(filtro, style="Sutil.TLabel"))
        corpo = ttk.Frame(pc)
        corpo.pack(fill="both", expand=True)
        tab2 = ttk.Frame(corpo)
        cols2 = ("item", "nome", "ids", "versao", "situacao")
        self.tabela_pc = ttk.Treeview(tab2, columns=cols2, show="headings", selectmode="extended")
        for c, t in (("item", "Item"), ("nome", "Nome"), ("ids", "IDs dos mods"), ("versao", "Jogo"), ("situacao", "No modpack")):
            self.tabela_pc.heading(c, text=t)
            self.tabela_pc.column(c, width=100, minwidth=45, anchor="w")
        colunas_proporcionais(self.tabela_pc, {"item": 11, "nome": 34, "ids": 30, "versao": 6, "situacao": 19})
        barra2 = ttk.Scrollbar(tab2, orient="vertical", command=self.tabela_pc.yview)
        self.tabela_pc.configure(yscrollcommand=barra2.set)
        self.tabela_pc.pack(side="left", fill="both", expand=True)
        barra2.pack(side="left", fill="y")
        self.tabela_pc.bind("<Double-1>", lambda e: self.adicionar_do_pc())
        ctx = tk.Menu(self.tabela_pc, tearoff=False)
        ctx.add_command(label="Adicionar ao modpack", command=self.adicionar_do_pc)
        ctx.add_command(label="Abrir na Steam", command=self.abrir_steam_pc)
        ctx.add_command(label="Baixar de novo (versão nova)", command=self.baixar_de_novo_pc)
        self.menus.append(ctx)
        self.tabela_pc.bind("<Button-3>", lambda e: self._menu_linha(e, self.tabela_pc, ctx))
        lado2 = Fluxo(corpo, espaco=3, largura_item=232)
        lado2.add(ttk.Button(lado2, text="ADICIONAR AO MODPACK", command=self.adicionar_do_pc, style="Accent.TButton"))
        lado2.add(ttk.Label(lado2, text="(ou dois cliques no mod)", style="Sutil.TLabel", anchor="center"))
        lado2.quebra()
        lado2.add(ttk.Button(lado2, text="Abrir na Steam", command=self.abrir_steam_pc))
        lado2.add(ttk.Button(lado2, text="Baixar de novo (versão nova)", command=self.baixar_de_novo_pc))
        lado2.add(ttk.Button(lado2, text="Recarregar lista do PC", command=self.carregar_baixados))
        self.painel2 = PainelAdaptavel(corpo, tab2, lado2)
        self.lista_pc = []

    def _aba_busca(self):
        aba = ttk.Frame(self.abas)
        self.pag_busca = aba
        self.abas.add(aba, text="Procurar na Steam")
        self._cabecalho(aba, "Procurar na Steam", "Busque mods na Workshop do Project Zomboid e coloque no modpack. "
                                                  "Se não estiverem baixados, o programa baixa sozinho.")
        moldura = ttk.Frame(aba, padding=(0, 0, 0, 8))
        moldura.pack(fill="x")
        barra = Fluxo(moldura, espaco=6)
        barra.pack(fill="x")
        self.busca_steam = barra.add(EntradaDica(barra, "🔍 Nome do mod, ID ou link...", width=36))
        self.busca_steam.bind("<Return>", lambda e: self.procurar_steam(1))
        self.ordem_busca = barra.add(ttk.Combobox(barra, state="readonly", width=20,
                                                  values=[n for n, _ in MP.ORDENS_BUSCA]))
        self.ordem_busca.current(0)
        self.ordem_busca.bind("<<ComboboxSelected>>", lambda e: self.procurar_steam(1))
        self.busca_b42 = tk.BooleanVar(value=True)
        barra.add(ttk.Checkbutton(barra, text="Só Build 42", variable=self.busca_b42, command=lambda: self.procurar_steam(1)))
        barra.add(ttk.Button(barra, text="Procurar", command=lambda: self.procurar_steam(1), style="Accent.TButton"))
        self.status_busca = barra.add(ttk.Label(barra, style="Sutil.TLabel"))

        corpo = ttk.Frame(aba)
        corpo.pack(fill="both", expand=True)
        esq = ttk.Frame(corpo)
        tab = ttk.Frame(esq)
        tab.pack(fill="both", expand=True)
        cols = ("item", "nome", "autor", "inscritos", "atualizado", "tamanho", "versao", "situacao")
        self.tabela_busca = ttk.Treeview(tab, columns=cols, show="headings", selectmode="extended")
        for c, t in (("item", "Item"), ("nome", "Nome"), ("autor", "Autor"), ("inscritos", "Inscritos"),
                     ("atualizado", "Atualizado"), ("tamanho", "Tamanho"), ("versao", "Jogo"), ("situacao", "Situação")):
            self.tabela_busca.heading(c, text=t)
            self.tabela_busca.column(c, width=80, minwidth=40, anchor="e" if c in ("inscritos", "tamanho") else "w")
        colunas_proporcionais(self.tabela_busca, {"item": 10, "nome": 30, "autor": 13, "inscritos": 9,
                                                  "atualizado": 10, "tamanho": 8, "versao": 7, "situacao": 13})
        rol = ttk.Scrollbar(tab, orient="vertical", command=self.tabela_busca.yview)
        self.tabela_busca.configure(yscrollcommand=rol.set)
        self.tabela_busca.pack(side="left", fill="both", expand=True)
        rol.pack(side="left", fill="y")
        self.tabela_busca.bind("<Double-1>", lambda e: self.adicionar_da_busca())
        self.tabela_busca.bind("<<TreeviewSelect>>", lambda e: self.mostrar_descricao())
        self.desc_busca = ttk.Label(esq, style="Sutil.TLabel", padding=(2, 8, 0, 0), justify="left")
        self.desc_busca.pack(fill="x")
        self.desc_busca.bind("<Configure>", lambda e: self.desc_busca.configure(wraplength=max(e.width - 8, 200)))

        lado = Fluxo(corpo, espaco=3, largura_item=232)
        lado.add(ttk.Button(lado, text="ADICIONAR SELECIONADOS", command=self.adicionar_da_busca, style="Accent.TButton"))
        lado.add(ttk.Label(lado, text="(ou dois cliques no mod)", style="Sutil.TLabel", anchor="center"))
        lado.add(ttk.Button(lado, text="Abrir na Steam", command=self.abrir_steam_busca))
        lado.quebra()
        self.b_anterior = lado.add(ttk.Button(lado, text="◀ Página anterior", command=lambda: self.procurar_steam(self.pagina_busca - 1)))
        self.b_proxima = lado.add(ttk.Button(lado, text="Próxima página ▶", command=lambda: self.procurar_steam(self.pagina_busca + 1)))
        self.rotulo_pagina = lado.add(ttk.Label(lado, style="Sutil.TLabel", anchor="center"))
        self.painel_busca = PainelAdaptavel(corpo, esq, lado)
        self.resultados_busca, self.pagina_busca, self.paginas_busca = [], 1, 1
        self.buscando = False
        self._botoes_pagina()
        self.desc_busca.configure(text="Digite o nome do mod e clique em Procurar (ou só Procurar para ver os mais inscritos).")

    def _botoes_pagina(self):
        self.b_anterior.state(["!disabled"] if self.pagina_busca > 1 and not self.buscando else ["disabled"])
        self.b_proxima.state(["!disabled"] if self.pagina_busca < self.paginas_busca and not self.buscando else ["disabled"])
        self.rotulo_pagina.configure(text="Página %d de %d" % (self.pagina_busca, self.paginas_busca)
                                     if self.resultados_busca else "")

    def procurar_steam(self, pagina=1):
        if self.buscando:
            return
        pagina = max(1, pagina)
        texto = self.busca_steam.valor().strip()
        ordem = dict(MP.ORDENS_BUSCA)[self.ordem_busca.get()]
        so_b42 = self.busca_b42.get()
        self.buscando = True
        self._botoes_pagina()
        self.status_busca.configure(text="procurando na Steam...")
        res = {}

        def trabalho():
            try:
                res["ok"] = MP.buscar_workshop(texto, ordem, pagina, so_b42)
            except Exception as e:  # sem internet, Steam fora do ar, pagina mudou
                res["erro"] = e
        t = threading.Thread(target=trabalho, daemon=True)
        t.start()

        def conferir():
            if t.is_alive():
                self.after(150, conferir)
                return
            self.buscando = False
            if "erro" in res:
                self.status_busca.configure(text="a Steam não respondeu")
                self.log("Procurar na Steam: não consegui (%s). Confira a internet e tente de novo." % res["erro"])
                self._botoes_pagina()
                return
            self.resultados_busca, self.paginas_busca, total = res["ok"]
            self.pagina_busca = pagina
            self.status_busca.configure(text="%d resultado(s)" % total)
            self.preencher_busca()
            self.tabela_busca.yview_moveto(0)
            self._botoes_pagina()
            self.desc_busca.configure(text="Nada encontrado." if not self.resultados_busca else
                                      "Clique num mod para ver a descrição.")
        self.after(150, conferir)

    def situacao_busca(self, item):
        sit = MP.situacao_no_pack(self.cfg, item) if self.cfg else ""
        if sit:
            return "%s  %s" % (tema.icone("ok"), sit), "dentro"
        if MP.steam_pastas(item) is not None:
            return "%s  baixado no PC" % tema.icone("baixado"), "baixado"
        return "-", ""

    def preencher_busca(self):
        import time as _t
        sel = self.tabela_busca.selection()
        self.tabela_busca.delete(*self.tabela_busca.get_children())
        for d in self.resultados_busca:
            sit, tag = self.situacao_busca(d["item"])
            versao = "B42" if d["b42"] else ("B41" if d["b41"] else "?")
            tags = (tag,) if tag else (("b41",) if not d["b42"] else ())
            tam = d["tamanho"]
            self.tabela_busca.insert("", "end", iid=d["item"], tags=tags, values=(
                d["item"], d["titulo"], d["autor"], "{:,}".format(d["inscritos"]).replace(",", "."),
                _t.strftime("%d/%m/%Y", _t.localtime(d["atualizado"])) if d["atualizado"] else "?",
                ("%.1f MB" % (tam / 1e6)) if tam >= 1e5 else ("%d KB" % max(1, tam // 1000)), versao, sit))
        tema.zebra(self.tabela_busca)
        manter = [i for i in sel if self.tabela_busca.exists(i)]
        if manter:
            self.tabela_busca.selection_set(manter)

    def mostrar_descricao(self):
        sel = self.tabela_busca.selection()
        info = {d["item"]: d for d in self.resultados_busca}
        if len(sel) != 1 or sel[0] not in info:
            self.desc_busca.configure(text="%d mods selecionados." % len(sel) if sel else "")
            return
        d = info[sel[0]]
        desc = " · ".join(l.strip() for l in (d["descricao"] or "").splitlines() if l.strip())
        if len(desc) > 320:
            desc = desc[:320].rsplit(" ", 1)[0] + "..."
        self.desc_busca.configure(text="%s   —   tags: %s\n%s" % (d["titulo"], ", ".join(d["tags"]) or "-",
                                                                 desc or "(sem descrição)"))

    def adicionar_da_busca(self):
        if not self.precisa_pack():
            return
        sel = list(self.tabela_busca.selection())
        if not sel:
            messagebox.showinfo("Modpack", "Selecione um ou mais mods na lista.")
            return
        info = {d["item"]: d for d in self.resultados_busca}
        b41 = [i for i in sel if i in info and not info[i]["b42"]]
        if b41 and not messagebox.askyesno("Modpack", "%d dos mods escolhidos não estão marcados como Build 42 na Steam "
                                                      "e podem não funcionar.\n\nAdicionar mesmo assim?" % len(b41)):
            sel = [i for i in sel if i not in b41]
        ja = [i for i in sel if MP.situacao_no_pack(self.cfg, i)]
        for i in ja:
            self.log("Item %s (%s) já está no modpack." % (i, info.get(i, {}).get("titulo", "?")))
        sel = [i for i in sel if i not in ja]
        baixados = [i for i in sel if MP.steam_pastas(i) is not None]
        faltam = [i for i in sel if i not in baixados]
        for i in baixados:
            self.adicionar(i)
        if faltam:
            nomes = "\n".join("• %s" % info.get(i, {}).get("titulo", i) for i in faltam[:15])
            self.obter_downloads(faltam, faltam, "%d mod(s) ainda não estão baixados neste PC:\n%s" % (len(faltam), nomes))
        self.preencher_busca()

    def abrir_steam_busca(self):
        for item in self.tabela_busca.selection():
            self.abrir_steam(item)

    def _aba_nosteam(self):
        ns = ttk.Frame(self.abas)
        self.aba_ns = ns
        self.abas.add(ns, text="Sem Steam (nosteam)")
        self._cabecalho(ns, "Sem Steam (-nosteam)", (
            "Servidor ligado com -nosteam não usa a Workshop: o servidor e cada jogador precisam ter os MESMOS "
            "mods na pasta Zomboid/mods. Quem entra abre o jogo com -nosteam (Steam: Propriedades > Opções de "
            "inicialização) e conecta pelo IP. Jogador no modo Steam não entra nesse servidor, e vice-versa."))

        dono = ttk.LabelFrame(ns, text=" Dono do servidor (usa o modpack escolhido no topo) ", padding=6)
        dono.pack(fill="x", pady=(8, 0))
        f1 = Fluxo(dono, espaco=6)
        f1.pack(fill="x")
        f1.add(ttk.Button(f1, text="Exportar zip nosteam...", command=self.exportar_nosteam, style="Accent.TButton"))
        f1.add(ttk.Button(f1, text="Gerar .ini nosteam...", command=self.gerar_ini_nosteam))
        passos = ttk.Label(dono, style="Sutil.TLabel", padding=(0, 6, 0, 0), text=(
            "1) Montar pacote (página Modpack)   2) Exportar zip   3) Gerar .ini nosteam   "
            "4) No servidor: extrair o zip na pasta Zomboid, .ini em Zomboid/Server/ e -nosteam na inicialização   "
            "5) Mandar o mesmo zip para os jogadores"))
        passos.pack(fill="x")

        jog = ttk.LabelFrame(ns, text=" Jogador (não precisa de modpack escolhido) ", padding=6)
        jog.pack(fill="both", expand=True, pady=(8, 0))
        f2 = Fluxo(jog, espaco=6)
        f2.pack(fill="x")
        f2.add(ttk.Button(f2, text="Instalar .zip do modpack...", command=self.instalar_nosteam, style="Accent.TButton"))
        f2.add(ttk.Button(f2, text="Desinstalar selecionado", command=self.desinstalar_nosteam))
        f2.add(ttk.Button(f2, text="Abrir pasta mods", command=self.abrir_mods_nosteam))
        f2.add(ttk.Button(f2, text="Trocar pasta Zomboid...", command=self.trocar_zomboid_nosteam))
        self.zomboid_ns = ttk.Label(jog, style="Sutil.TLabel", padding=(0, 6))
        self.zomboid_ns.pack(fill="x")
        for rot in (passos, self.zomboid_ns):
            rot.bind("<Configure>", lambda e, r=rot: r.configure(wraplength=max(e.width - 8, 200)))
        tab = ttk.Frame(jog)
        tab.pack(fill="both", expand=True)
        cols = ("pack", "titulo", "branch", "pastas", "quando")
        self.tabela_ns = ttk.Treeview(tab, columns=cols, show="headings", selectmode="browse", height=4)
        for c, t in (("pack", "Modpack"), ("titulo", "Título"), ("branch", "Versão do jogo"),
                     ("pastas", "Mods"), ("quando", "Instalado em")):
            self.tabela_ns.heading(c, text=t)
            self.tabela_ns.column(c, width=100, minwidth=50, anchor="w")
        colunas_proporcionais(self.tabela_ns, {"pack": 18, "titulo": 34, "branch": 14, "pastas": 10, "quando": 24})
        rol = ttk.Scrollbar(tab, orient="vertical", command=self.tabela_ns.yview)
        self.tabela_ns.configure(yscrollcommand=rol.set)
        self.tabela_ns.pack(side="left", fill="both", expand=True)
        rol.pack(side="left", fill="y")

        self.progresso_txt = ttk.Label(ns, style="Sutil.TLabel")
        self.progresso_txt.pack(fill="x", pady=(6, 0))
        self.progresso = ttk.Progressbar(ns, mode="determinate", maximum=1000)
        self.progresso.pack(fill="x")
        self.trabalhando = False
        self.atualizar_nosteam()

    def atualizar_nosteam(self):
        z = MP.pasta_zomboid_jogador()
        self.zomboid_ns.configure(text="Pasta Zomboid deste PC: %s%s" % (
            z, "" if os.path.isdir(z) else "   (ainda não existe: abra o jogo uma vez ou escolha outra)"))
        self.tabela_ns.delete(*self.tabela_ns.get_children())
        import time as _t
        for pk, titulo, branch, n, quando in MP.instalados_nosteam(z):
            self.tabela_ns.insert("", "end", iid=pk, values=(
                pk, titulo, branch, n, _t.strftime("%d/%m/%Y %H:%M", _t.localtime(quando)) if quando else "?"))
        tema.zebra(self.tabela_ns)

    def _em_segundo_plano(self, titulo, trabalho, fim):
        """Roda trabalho(progresso) numa thread, mostrando a barra; depois chama fim(ok, msgs)."""
        if self.trabalhando:
            messagebox.showinfo(titulo, "Espere terminar o que já está rodando.")
            return
        self.trabalhando = True
        estado = {"feito": 0, "total": 1}

        def progresso(feito, total):
            estado["feito"], estado["total"] = feito, total or 1

        def rodar():
            try:
                estado["res"] = trabalho(progresso)
            except Exception as e:  # mostra o erro em vez de travar a barra
                estado["res"] = (False, ["PROBLEMA: %s" % e])
        t = threading.Thread(target=rodar, daemon=True)
        t.start()
        self.abas.select(self.aba_ns)

        def acompanhar():
            frac = estado["feito"] / float(estado["total"])
            self.progresso["value"] = int(frac * 1000)
            self.progresso_txt.configure(text="%s... %d%% (%.2f de %.2f GB)" % (
                titulo, frac * 100, estado["feito"] / 1e9, estado["total"] / 1e9))
            if t.is_alive():
                self.after(250, acompanhar)
                return
            self.trabalhando = False
            ok, msgs = estado["res"]
            self.progresso["value"] = 1000 if ok else 0
            self.progresso_txt.configure(text="%s: %s" % (titulo, "pronto" if ok else "deu problema (veja o registro)"))
            self.log(*msgs)
            fim(ok, msgs)
        self.after(250, acompanhar)

    def exportar_nosteam(self):
        if not self.precisa_pack():
            return
        _, problemas, _ = MP.pastas_nosteam(self.cfg)
        if problemas:
            self.log(*["PROBLEMA: " + p for p in problemas])
            messagebox.showerror("Exportar zip nosteam", "\n\n".join(problemas[:8]))
            return
        saida = filedialog.asksaveasfilename(title="Onde salvar o zip para o modo sem Steam",
                                             initialfile="%s_nosteam.zip" % self.cfg["pasta"],
                                             defaultextension=".zip", filetypes=[("Zip", "*.zip")])
        if not saida:
            return
        cfg = self.cfg

        def fim(ok, msgs):
            (messagebox.showinfo if ok else messagebox.showerror)("Exportar zip nosteam", "\n\n".join(msgs))
        self._em_segundo_plano("Exportando zip", lambda prog: MP.exportar_nosteam(cfg, saida, prog), fim)

    def gerar_ini_nosteam(self):
        if not self.precisa_pack():
            return
        entrada = filedialog.askopenfilename(title="Escolha o .ini ATUAL do servidor",
                                             filetypes=[("Ini do servidor", "*.ini"), ("Todos", "*")])
        if not entrada:
            return
        ok, msgs = MP.gerar_ini_nosteam(self.cfg, entrada)
        self.log(*msgs)
        (messagebox.showinfo if ok else messagebox.showerror)("Gerar .ini nosteam", "\n\n".join(msgs))

    def instalar_nosteam(self):
        f = filedialog.askopenfilename(title="Escolha o .zip do modpack (o que o dono do servidor mandou)",
                                       filetypes=[("Zip", "*.zip"), ("Todos", "*")])
        if not f:
            return
        z = MP.pasta_zomboid_jogador()
        if not messagebox.askyesno("Instalar", "Instalar os mods em:\n%s\n\nA versão antiga deste modpack "
                                               "(se tiver) é apagada antes. Seus outros mods ficam." % os.path.join(z, "mods")):
            return

        def fim(ok, msgs):
            self.atualizar_nosteam()
            (messagebox.showinfo if ok else messagebox.showerror)("Instalar", "\n\n".join(msgs))
        self._em_segundo_plano("Instalando", lambda prog: MP.instalar_nosteam(f, z, prog), fim)

    def desinstalar_nosteam(self):
        sel = self.tabela_ns.selection()
        if not sel:
            messagebox.showinfo("Desinstalar", "Selecione na lista o modpack instalado.")
            return
        if messagebox.askyesno("Desinstalar", "Apagar de Zomboid/mods as pastas do modpack '%s'?" % sel[0]):
            ok, msgs = MP.desinstalar_nosteam(sel[0], MP.pasta_zomboid_jogador())
            self.log(*msgs)
            self.atualizar_nosteam()

    def abrir_mods_nosteam(self):
        d = os.path.join(MP.pasta_zomboid_jogador(), "mods")
        abrir(d if os.path.isdir(d) else os.path.dirname(d))

    def trocar_zomboid_nosteam(self):
        d = filedialog.askdirectory(title="Pasta Zomboid do jogo (a que tem Saves/ e mods/)",
                                    initialdir=MP.pasta_zomboid_jogador())
        if d:
            loc = MP.local()
            loc["zomboid_nosteam"] = d
            MP.salvar_local(loc)
            self.atualizar_nosteam()

    def _pintar(self):
        """Cores que nao vem do ttk.Style (texto do registro, cores das tabelas, botao do tema)."""
        tema.texto(self.texto)
        for tree in (self.tabela, self.tabela_pc, self.tabela_busca, self.tabela_ns):
            tema.tabela(tree)
        self.b_tema.configure(text="☀   Tema claro" if self.modo_tema == "escuro" else "☾   Tema escuro")
        for m in getattr(self, "menus", []):
            tema.menu(m)
        self.atualizar_passos()

    def fechar(self):
        ocupado = [n for n, v in (("exportando/instalando o zip", getattr(self, "trabalhando", False)),
                                  ("baixando mods", getattr(self, "baixando", False))) if v]
        if ocupado and not messagebox.askyesno("Fechar", "O programa ainda está %s.\n\nFechar mesmo assim? "
                                                         "(o que estava pela metade fica incompleto)" % " e ".join(ocupado)):
            return
        self.destroy()

    def limpar_registro(self):
        self.texto.configure(state="normal")
        self.texto.delete("1.0", "end")
        self.texto.configure(state="disabled")

    def _ajustar_divisao(self):
        """Na primeira vez que a janela ganha tamanho, deixa umas 7 linhas para o registro embaixo
        (depois a pessoa arrasta a divisoria como quiser)."""
        alt = self.divisao.winfo_height()
        if self._divisao_ok or alt < 300:
            return
        self._divisao_ok = True
        self.after_idle(lambda: self.divisao.sashpos(0, alt - 130))

    def trocar_tema(self):
        self.modo_tema = "claro" if self.modo_tema == "escuro" else "escuro"
        tema.aplicar(self, self.modo_tema)
        self._pintar()
        loc = MP.local()
        loc["tema"] = self.modo_tema
        try:
            MP.salvar_local(loc)
        except OSError:
            pass

    def log(self, *linhas):
        self.texto.configure(state="normal")
        for linha in linhas:
            self.texto.insert("end", str(linha) + "\n")
        self.texto.see("end")
        self.texto.configure(state="disabled")

    # Modpacks --------------------------------------------------------------------
    def _ultimo(self):
        try:
            return open(ULTIMO, encoding="utf-8").read().strip()
        except OSError:
            return None

    def recarregar_packs(self, escolher=None):
        self.packs = MP.listar_packs()
        nomes = []
        for s_, t in self.packs:
            try:
                nomes.append(MP.carregar(s_).get("nome") or t)
            except Exception:
                nomes.append(t)
        self.combo["values"] = nomes
        if not self.packs:
            self.cfg = None
            self.combo.set("")
            self.titulo_pack.configure(text="Nenhum modpack ainda")
            self.info_pack.configure(text="Clique em '＋ Novo' no menu ao lado para criar o primeiro.")
            self.tabela.delete(*self.tabela.get_children())
            self.atualizar_passos()
            return
        slugs = [s for s, _ in self.packs]
        i = slugs.index(escolher) if escolher in slugs else 0
        self.combo.current(i)
        self.trocar_pack()

    def trocar_pack(self):
        i = self.combo.current()
        if i < 0:
            return
        s = self.packs[i][0]
        self.cfg = MP.carregar(s)
        try:
            os.makedirs(os.path.dirname(ULTIMO), exist_ok=True)
            open(ULTIMO, "w", encoding="utf-8").write(s)
        except OSError:
            pass
        self.atualizar_lista()
        b = MP.branch_do_jogo()
        if b is not None and b != self.cfg["branch"]:
            self.log("ATENCAO: seu jogo está no branch '%s' e este modpack é do '%s'. Teste no mesmo branch do servidor "
                     "(Steam > Propriedades > Betas)." % (b or "padrão", self.cfg["branch"]))

    def precisa_pack(self):
        """Chamado antes de toda acao no modpack: rele o modpack.json do disco, para nunca gravar por cima
        de uma mudanca feita fora desta janela (outra janela aberta, linha de comando, edicao na mao)."""
        if not self.cfg:
            messagebox.showinfo("Modpack", "Crie ou escolha um modpack primeiro.")
            return False
        try:
            self.cfg = MP.carregar(os.path.basename(self.cfg["_dir"]))
        except (OSError, ValueError, KeyError):
            messagebox.showerror("Modpack", "Não consegui ler o modpack do disco (apagado ou corrompido?).")
            return False
        return True

    def novo_pack(self):
        nome = simpledialog.askstring("Novo modpack", "Nome do servidor / modpack (ex.: Meu Servidor):", parent=self)
        if not nome:
            return
        branch = simpledialog.askstring("Novo modpack", "Versão (branch beta) do jogo no servidor:",
                                        initialvalue="42.21", parent=self) or "42.21"
        ini = None
        if messagebox.askyesno("Novo modpack", "Importar a lista de mods do .ini desse servidor?\n\n"
                                               "(Sim = escolher o .ini; Não = começar vazio e ir adicionando por ID)"):
            ini = filedialog.askopenfilename(title="Escolha o .ini do servidor",
                                             filetypes=[("Ini do servidor", "*.ini"), ("Todos", "*")])
            if not ini:
                return
        ok, msgs, s = MP.novo(nome, ini, branch)
        self.log(*msgs)
        if not ok:
            messagebox.showerror("Modpack", "\n".join(msgs))
            return
        self.recarregar_packs(s)
        faltam = MP.faltando(self.cfg)
        if faltam:
            self.obter_downloads(faltam, [], "%d mods desse servidor ainda não estão baixados aqui." % len(faltam))

    def importar_pack(self):
        f = filedialog.askopenfilename(title="Escolha o modpack.json do modpack (pasta packs/<nome>/)",
                                       filetypes=[("Modpack", "modpack.json"), ("Todos", "*")])
        if not f:
            return
        ok, msgs, s = MP.importar(f)
        self.log(*msgs)
        if ok:
            self.recarregar_packs(s)
        else:
            messagebox.showerror("Importar", "\n".join(msgs))

    def configurar_pack(self):
        if not self.precisa_pack():
            return
        nome = simpledialog.askstring("Configurar", "Nome do servidor / modpack:", initialvalue=self.cfg.get("nome", ""), parent=self)
        if nome is None:
            return
        titulo = simpledialog.askstring("Configurar", "Título na Workshop:", initialvalue=self.cfg["titulo"], parent=self)
        if titulo is None:
            return
        branch = simpledialog.askstring("Configurar", "Versão (branch beta) do jogo:", initialvalue=self.cfg["branch"], parent=self)
        if branch is None:
            return
        ok, msgs = MP.configurar(self.cfg, nome.strip() or None, titulo.strip() or None, branch.strip() or None)
        self.log(*msgs, "O título e a descrição novos entram no próximo 'Montar pacote'.")
        self.recarregar_packs(os.path.basename(self.cfg["_dir"]))

    def excluir_pack(self):
        if not self.precisa_pack():
            return
        if messagebox.askyesno("Excluir", "Apagar a lista do modpack '%s'?\n\nA pasta de publicação (%s) e o item "
                                          "já publicado na Steam NÃO são apagados." % (self.cfg.get("nome"), MP.destino(self.cfg))):
            ok, msgs = MP.excluir(self.cfg)
            self.log(*msgs)
            self.recarregar_packs()

    def pastas(self):
        loc = MP.local()
        win = tk.Toplevel(self)
        win.title("Pastas desta máquina")
        win.transient(self)
        campos = {}
        for chave, rotulo, atual in (
                ("workshop", "Downloads da Workshop do PZ (steamapps/workshop/content/108600):", MP.WORKSHOP),
                ("zomboid", "Pasta Zomboid do usuário (onde fica Workshop/ para publicar):", os.path.dirname(MP.PUBLICAR))):
            ttk.Label(win, text=rotulo, padding=(8, 8, 8, 0)).pack(anchor="w")
            linha = ttk.Frame(win, padding=(8, 2))
            linha.pack(fill="x")
            v = tk.StringVar(value=loc.get(chave) or atual or "")
            ttk.Entry(linha, textvariable=v, width=80).pack(side="left", fill="x", expand=True)

            def escolher(var=v):
                d = filedialog.askdirectory(parent=win, initialdir=var.get() or os.path.expanduser("~"))
                if d:
                    var.set(d)
            ttk.Button(linha, text="Escolher...", command=escolher).pack(side="left", padx=4)
            campos[chave] = v
        ttk.Label(win, text="Deixe como está para o programa achar sozinho (Windows, Linux, Flatpak, macOS).",
                  padding=8, style="Sutil.TLabel").pack(anchor="w")

        def salvar():
            dados = {k: v for k, v in MP.local().items() if k not in campos}
            for chave, v in campos.items():
                val = v.get().strip()
                auto = MP.detectar_workshop() if chave == "workshop" else MP.detectar_zomboid(MP.detectar_workshop())
                if val and os.path.realpath(val) != os.path.realpath(auto or ""):
                    dados[chave] = val
            MP.salvar_local(dados)
            MP.definir_pastas()
            self.log("Pastas: downloads = %s | publicar = %s" % (MP.WORKSHOP or "(não achei)", MP.PUBLICAR))
            for p in MP.pastas_ok():
                self.log("ATENCAO: " + p)
            win.destroy()
            self.atualizar_lista()

        def automatico():
            MP.salvar_local({k: v for k, v in MP.local().items() if k not in campos})
            MP.definir_pastas()
            self.log("Pastas automáticas: downloads = %s | publicar = %s" % (MP.WORKSHOP or "(não achei)", MP.PUBLICAR))
            win.destroy()
            self.atualizar_lista()
        b = ttk.Frame(win, padding=8)
        b.pack(fill="x")
        ttk.Button(b, text="Salvar", command=salvar).pack(side="right")
        ttk.Button(b, text="Achar sozinho", command=automatico).pack(side="right", padx=6)
        aplicar_dicas(win)

    # Lista -----------------------------------------------------------------------
    def atualizar_lista(self, recarregar=True):
        self.tabela.delete(*self.tabela.get_children())
        if not self.cfg:
            self.atualizar_passos()
            return
        if recarregar or not hasattr(self, "_status_cache"):
            self.cfg = MP.carregar(os.path.basename(self.cfg["_dir"]))
            self._status_cache = MP.status(self.cfg)
        pub = MP.pacote_id(self.cfg)
        self.titulo_pack.configure(text=self.cfg.get("nome") or self.cfg["titulo"])
        self.info_pack.configure(text="Build %s   ·   %s   ·   pasta: %s" % (
            self.cfg["branch"], ("Workshop id %s" % pub) if pub else "ainda não publicado", MP.destino(self.cfg)))
        filtro = self.filtro_pack.valor().strip().lower()
        self._explicacoes = {}
        for item, nome, ativos, sit in self._status_cache:
            if filtro and filtro not in nome.lower() and filtro not in item and filtro not in ativos.lower():
                continue
            tag, curto, explica = situacao_simples(sit)
            self._explicacoes[item] = (curto, explica)
            self.tabela.insert("", "end", iid=item, values=(item, nome, ativos or "—", curto), tags=(tag,))
        tema.zebra(self.tabela)
        self.mostrar_explicacao()
        if not recarregar:
            return
        self.atualizar_passos()
        if hasattr(self, "tabela_pc"):
            self.preencher_baixados()
        if hasattr(self, "tabela_busca"):
            self.preencher_busca()

    def selecionados(self):
        sel = list(self.tabela.selection())
        if not sel:
            messagebox.showinfo("Modpack", "Selecione um item na lista.")
        return sel

    # Acoes ------------------------------------------------------------------------
    def adicionar(self, texto=None, mods=None):
        if not self.precisa_pack():
            return
        texto = texto or self.entrada.valor().strip()
        item = MP.item_id(texto)
        if not item:
            messagebox.showwarning("Modpack", "Cole o número ou o link do mod na Workshop.")
            return
        ok, msgs, opcoes = MP.adicionar(self.cfg, texto, mods)
        if opcoes and mods is None:
            escolha = self.escolher_mods(item, opcoes)
            if escolha:
                return self.adicionar(texto, escolha)
            self.log("Adição cancelada.")
            return
        self.log(*msgs)
        if not ok and MP.steam_pastas(item) is None:
            self.obter_downloads([item], [item], "O item %s ainda não está baixado neste PC." % item)
            return
        if ok:
            self.entrada.limpar()
            pend = self.cfg.get("_pendentes") or []
            if pend:
                self.obter_downloads(pend, [item], "Esse mod precisa de %d item(ns) que não estão baixados:\n%s\n\n"
                                                   "Depois de baixar, as dependências entram sozinhas."
                                     % (len(pend), ", ".join(pend)))
        self.atualizar_lista()

    def obter_downloads(self, itens, depois, motivo):
        """Pergunta como baixar: automatico (SteamCMD) ou pela Steam (inscrever-se)."""
        r = messagebox.askyesnocancel(
            "Baixar mods", motivo + "\n\nSIM = baixar AUTOMÁTICO (o programa baixa sozinho pela SteamCMD da Valve, "
                                    "sem conta e sem se inscrever).\n\nNÃO = abrir na Steam para você clicar em "
                                    "Inscrever-se (o programa espera baixar).\n\nCANCELAR = deixa pra lá.")
        if r is None:
            return
        if r:
            self.baixar_auto(itens, depois)
        else:
            self.esperar_downloads(itens, depois)

    def baixar_auto(self, itens, depois):
        """Baixa pela SteamCMD numa thread, mostrando o andamento no registro; depois adiciona "depois".
        O que falhar pode ser baixado pela Steam (inscrever-se)."""
        import queue
        if getattr(self, "baixando", False):
            messagebox.showinfo("Baixar mods", "Já tem um download automático rodando. Espere terminar.")
            return
        self.baixando = True
        depois = list(depois) if isinstance(depois, (list, tuple)) else [depois]
        fila, res = queue.Queue(), {}
        primeira = not os.path.isfile(MP.steamcmd_exe())
        self.log("Download automático de %d item(ns): %s" % (len(itens), ", ".join(itens)),
                 "(primeira vez: instalando a SteamCMD da Valve, leva 1-2 minutos)" if primeira else "")

        def trabalho():
            try:
                res["r"] = MP.baixar_automatico(itens, aviso=fila.put)
            except Exception as e:
                res["r"] = ([], {i: str(e) for i in itens}, ["PROBLEMA no download automático: %s" % e])
        t = threading.Thread(target=trabalho, daemon=True)
        t.start()
        self.config(cursor="watch")

        def acompanhar():
            while not fila.empty():
                self.log("   " + fila.get())
            if t.is_alive():
                self.after(300, acompanhar)
                return
            self.config(cursor="")
            self.baixando = False
            baixados, falhas, msgs = res["r"]
            self.log(*msgs)
            self.carregar_baixados()
            for d in depois:
                if MP.steam_pastas(d) is not None:
                    self.adicionar(d)
            self.atualizar_lista()
            if falhas:
                if messagebox.askyesno("Baixar mods", "O download automático não conseguiu %d item(ns):\n%s\n\n"
                                                      "Abrir na Steam para você se inscrever?"
                                       % (len(falhas), "\n".join("• %s (%s)" % kv for kv in list(falhas.items())[:12]))):
                    self.esperar_downloads(list(falhas), [d for d in depois if MP.steam_pastas(d) is None])
            elif baixados and not depois:
                messagebox.showinfo("Baixar mods", "Baixados: %d item(ns)." % len(baixados))
        self.after(300, acompanhar)

    def esperar_downloads(self, itens, depois):
        """Abre os itens na Steam e espera todos baixarem; depois adiciona "depois" (um item ou
        uma lista). Se ja estava esperando outros, junta tudo na mesma espera."""
        for i, it in enumerate(itens):
            self.after(i * 1500, lambda x=it: self.abrir_steam(x))
        depois = list(depois) if isinstance(depois, (list, tuple)) else [depois]
        if self.esperando:
            antes_itens, _, antes_depois = self.esperando
            self.esperando = (list(dict.fromkeys(antes_itens + list(itens))), 0,
                              list(dict.fromkeys(antes_depois + depois)))
        else:
            self.esperando = (list(itens), 0, depois)
            self.after(ESPERA_MS, self.conferir_download)
        self.log("Esperando a Steam baixar: %s..." % ", ".join(itens))

    def conferir_download(self):
        if not self.esperando:
            return
        itens, n, depois = self.esperando
        falta = [i for i in itens if MP.steam_pastas(i) is None]
        if not falta:
            self.esperando = None
            self.log("Baixado: %s." % ", ".join(itens))
            self.carregar_baixados()
            for d in depois:
                self.adicionar(d)
            return
        if n >= ESPERA_MAX:
            self.esperando = None
            prontos = [d for d in depois if d not in falta and MP.steam_pastas(d) is not None]
            for d in prontos:
                self.adicionar(d)
            self.log("Desisti de esperar: %s. Quando baixar, clique Adicionar de novo." % ", ".join(falta))
            return
        self.esperando = (itens, n + 1, depois)
        self.after(ESPERA_MS, self.conferir_download)

    def escolher_mods(self, item, opcoes):
        """Janela com caixas de marcar para itens com mais de um mod."""
        win = tk.Toplevel(self)
        win.title("Quais mods ativar? (item %s)" % item)
        win.transient(self)
        win.grab_set()
        ttk.Label(win, text="Este item tem mais de um mod. Marque os que o servidor usa:", padding=8).pack(anchor="w")
        vars_ = []
        for i, (mid, nome) in enumerate(opcoes):
            v = tk.BooleanVar(value=(i == 0))
            ttk.Checkbutton(win, text="%s   (id: %s)" % (nome, mid), variable=v).pack(anchor="w", padx=16)
            vars_.append((mid, v))
        res = {"mods": None}

        def ok():
            res["mods"] = [m for m, v in vars_ if v.get()]
            win.destroy()
        b = ttk.Frame(win, padding=8)
        b.pack(fill="x")
        ttk.Button(b, text="OK", command=ok).pack(side="right")
        ttk.Button(b, text="Cancelar", command=win.destroy).pack(side="right", padx=6)
        self.wait_window(win)
        return res["mods"] or None

    def remover(self):
        if not self.precisa_pack():
            return
        for item in self.selecionados():
            if messagebox.askyesno("Modpack", "Tirar o item %s da lista (e os mods dele do Mods=)?" % item):
                ok, msgs = MP.remover(self.cfg, item)
                self.log(*msgs)
        self.atualizar_lista()

    def separar_juntar(self):
        if not self.precisa_pack():
            return
        for item in self.selecionados():
            if item in self.cfg["separados"]:
                ok, msgs = MP.juntar(self.cfg, item)
            else:
                ok, msgs = MP.separar(self.cfg, item, "deixado fora do pacote pelo admin")
            self.log(*msgs)
        self.atualizar_lista()

    def atualizar_selecionado(self):
        if not self.precisa_pack():
            return
        sel = self.selecionados()
        if sel:
            self._montar(sel)

    def montar(self):
        if self.precisa_pack():
            self._montar(())

    def montar_tudo(self):
        if self.precisa_pack() and messagebox.askyesno(
                "Modpack", "Pegar a versão baixada AGORA de todos os mods?\n\n"
                           "Só faça isso depois de testar as versões novas no seu jogo (branch %s)." % self.cfg["branch"]):
            self._montar("tudo")

    def _montar(self, atualizar):
        self.config(cursor="watch")
        self.update()
        try:
            ok, msgs = MP.montar(self.cfg, atualizar)
        finally:
            self.config(cursor="")
        self.log(*msgs)
        if ok:
            self.log(*MP.linhas(self.cfg))
            passo_ini = "2. Depois, gere o .ini do servidor no passo ③."
            if self.cfg.get("ini_servidor") and os.path.isfile(self.cfg["ini_servidor"]) and MP.pacote_id(self.cfg):
                ok_ini, msgs_ini = MP.atualizar_ini(self.cfg)
                self.log(*msgs_ini)
                if ok_ini:
                    passo_ini = "2. Suba no painel o .ini, que já foi atualizado:\n    %s" % self.cfg["ini_pronto"]
            messagebox.showinfo("Pacote montado", "Pacote montado (%d mods).\n\nAgora:\n"
                                                  "1. Publique no jogo: Workshop > Criar e atualizar itens > %s\n"
                                                  "    (espere 'success updating item').\n%s"
                                % (len(self.cfg["congelado"]), self.cfg["pasta"], passo_ini))
        else:
            messagebox.showerror("Modpack", "Não montei: veja os PROBLEMAS no registro embaixo.")
        self.atualizar_lista()

    def gerar_ini(self):
        if not self.precisa_pack():
            return
        antes = self.cfg.get("ini_servidor")
        entrada = filedialog.askopenfilename(title="Escolha o .ini ATUAL do servidor (baixado do painel)",
                                             initialdir=os.path.dirname(antes) if antes else os.path.expanduser("~"),
                                             filetypes=[("Ini do servidor", "*.ini"), ("Todos", "*")])
        if not entrada:
            return
        ok, msgs = MP.gerar_ini(self.cfg, entrada)
        self.log(*msgs)
        if ok:
            self._aviso_ini(self.cfg["ini_pronto"], "Mods= com %d mods e WorkshopItems= conferidos.\n\n" % len(self.cfg["mods"]))
        else:
            messagebox.showerror("Gerar .ini", "\n\n".join(msgs))
        self.atualizar_lista()

    def mostrar_resultado(self, titulo, res):
        """Janela com o resultado de uma conferencia (ERRO vermelho, AVISO laranja, OK verde)."""
        self.log("== " + titulo, *["[%s] %s" % r for r in res])
        win = tk.Toplevel(self)
        win.title(titulo)
        win.transient(self)
        win.configure(background=tema.cor("fundo"))
        t = tk.Text(win, width=110, height=min(24, 4 + 2 * len(res)), wrap="word", font="TkDefaultFont")
        tema.texto(t)
        t.pack(fill="both", expand=True, padx=10, pady=10)
        cores = {"ERRO": tema.cor("erro"), "AVISO": tema.cor("aviso"), "OK": tema.cor("ok")}
        for nivel, c in cores.items():
            t.tag_configure(nivel, foreground=c, font="TkHeadingFont")
        for nivel, m in res:
            t.insert("end", {"ERRO": "✖ ", "AVISO": "⚠ ", "OK": "✔ "}.get(nivel, "") + nivel + "  ", nivel)
            t.insert("end", m + "\n\n")
        t.configure(state="disabled")
        ttk.Button(win, text="Fechar", command=win.destroy).pack(pady=(0, 8))

    def conferir_ini(self):
        if not self.precisa_pack():
            return
        f = filedialog.askopenfilename(title="Escolha o .ini do servidor para conferir",
                                       filetypes=[("Ini do servidor", "*.ini"), ("Todos", "*")])
        if f:
            self.mostrar_resultado("Conferência do .ini: %s" % os.path.basename(f), MP.conferir_ini(self.cfg, f))

    def conferir_log(self):
        if not self.precisa_pack():
            return
        inicio = os.path.dirname(MP.PUBLICAR)
        f = filedialog.askopenfilename(title="Escolha o log (console.txt do jogo ou DebugLog-server.txt do servidor)",
                                       initialdir=inicio if os.path.isdir(inicio) else None,
                                       filetypes=[("Logs", "*.txt *.log"), ("Todos", "*")])
        if f:
            self.mostrar_resultado("Conferência do log: %s" % os.path.basename(f), MP.conferir_log(self.cfg, f))

    def ver_publicacao(self):
        if not self.precisa_pack():
            return
        self.config(cursor="watch")
        self.update()
        try:
            res = MP.status_publicacao(self.cfg)[2]
        finally:
            self.config(cursor="")
        self.mostrar_resultado("Publicação na Steam", res)

    def abrir_steam(self, item):
        # steam:// abre direto no cliente da Steam; se nao der, o navegador abre a pagina.
        abrir("steam://url/CommunityFilePage/%s" % item)

    def abrir_steam_entrada(self):
        item = MP.item_id(self.entrada.valor())
        if item:
            self.abrir_steam(item)

    def abrir_steam_sel(self):
        for item in self.selecionados():
            self.abrir_steam(item)

    def abrir_faltando(self, perguntar=True):
        if not self.precisa_pack():
            return
        faltam = MP.faltando(self.cfg)
        if not faltam:
            messagebox.showinfo("Modpack", "Todos os mods da lista já estão baixados ou no pacote.")
            return
        if perguntar:
            self.obter_downloads(faltam, [], "%d mod(s) da lista não estão baixados neste PC." % len(faltam))
            return
        for i, item in enumerate(faltam):
            self.after(i * 1500, lambda it=item: self.abrir_steam(it))  # devagar para a Steam acompanhar
        self.log("Abrindo %d páginas na Steam. Inscreva-se em cada uma; depois clique em 'Recarregar lista'." % len(faltam))

    # Mods baixados no PC ------------------------------------------------------------
    def carregar_baixados(self):
        """Le a pasta da Workshop em segundo plano (centenas de mods levam alguns segundos)."""
        self.conta_pc.configure(text="lendo os mods baixados...")
        res = {}

        def trabalho():
            res["lista"] = MP.baixados()
        t = threading.Thread(target=trabalho, daemon=True)
        t.start()

        def conferir():
            if t.is_alive():
                self.after(200, conferir)
                return
            self.lista_pc = res.get("lista", [])
            self.preencher_baixados()
        self.after(200, conferir)

    def preencher_baixados(self):
        self.tabela_pc.delete(*self.tabela_pc.get_children())
        busca = self.busca_entry.valor().strip().lower()
        mostrados = 0
        for d in self.lista_pc:
            sit = MP.situacao_no_pack(self.cfg, d["item"]) if self.cfg else ""
            if self.so_b42.get() and not d["b42"]:
                continue
            if self.so_fora.get() and sit:
                continue
            if busca and busca not in d["nome"].lower() and busca not in d["item"] and \
                    not any(busca in i.lower() for i in d["ids"]):
                continue
            tag = ("dentro",) if sit == "no modpack" else ("separado",) if sit == "separado" else \
                  ("aviso",) if sit else ("b41",) if not d["b42"] else ()
            mostra = sit or "-"
            if sit:
                mostra = "%s  %s" % (tema.icone({"dentro": "ok"}.get(tag[0], tag[0])), sit)
            self.tabela_pc.insert("", "end", iid=d["item"], tags=tag,
                                  values=(d["item"], d["nome"], ", ".join(d["ids"]), "B42" if d["b42"] else "B41", mostra))
            mostrados += 1
        tema.zebra(self.tabela_pc)
        self.conta_pc.configure(text="%d de %d mods baixados" % (mostrados, len(self.lista_pc)))

    def adicionar_do_pc(self):
        if not self.precisa_pack():
            return
        sel = list(self.tabela_pc.selection())
        if not sel:
            messagebox.showinfo("Modpack", "Selecione um ou mais mods na lista.")
            return
        info = {d["item"]: d for d in self.lista_pc}
        b41 = [i for i in sel if i in info and not info[i]["b42"]]
        if b41 and not messagebox.askyesno("Modpack", "%d dos mods escolhidos são da B41 e não funcionam na B42.\n\n"
                                                      "Adicionar mesmo assim?" % len(b41)):
            sel = [i for i in sel if i not in b41]
        feitos = 0
        for item in sel:
            if item in self.cfg["itens"] and MP.situacao_no_pack(self.cfg, item):
                self.log("Item %s já está no modpack." % item)
                continue
            antes = len(self.cfg["itens"])
            self.adicionar(item)
            if len(MP.carregar(os.path.basename(self.cfg["_dir"]))["itens"]) > antes:
                feitos += 1
        self.atualizar_lista()
        if feitos:
            self.log("%d mod(s) adicionados. Clique em 'Montar pacote' (página Modpack) e publique no jogo." % feitos)

    def baixar_de_novo_pc(self):
        sel = list(self.tabela_pc.selection())
        if not sel:
            messagebox.showinfo("Baixar", "Selecione um ou mais mods na lista.")
            return
        self.baixar_auto(sel, [])

    def abrir_steam_pc(self):
        for item in self.tabela_pc.selection():
            self.abrir_steam(item)

    def atualizar_novidades(self):
        if not self.precisa_pack():
            return
        novos = MP.com_versao_nova(self.cfg)
        if not novos:
            messagebox.showinfo("Modpack", "Nenhum mod do pacote tem versão nova baixada.\n\n"
                                           "A Steam baixa as atualizações dos mods em que você está inscrito "
                                           "(deixe a Steam aberta ou abra o jogo) e aí elas aparecem aqui.")
            return
        nomes = "\n".join("• %s (%s)" % (MP.nome_do_item(self.cfg, i), i) for i in novos[:25])
        if len(novos) > 25:
            nomes += "\n... e mais %d" % (len(novos) - 25)
        if messagebox.askyesno("Atualizar mods", "Atualizar %d mod(s) no pacote com a versão que a Steam baixou?\n\n%s\n\n"
                                                 "Dica: teste no seu jogo (branch %s) antes de publicar."
                                                 % (len(novos), nomes, self.cfg["branch"])):
            self._montar(novos)

    def abrir_pasta(self):
        if not self.precisa_pack():
            return
        d = MP.destino(self.cfg)
        abrir(d if os.path.isdir(d) else os.path.dirname(d))


if __name__ == "__main__":
    App().mainloop()
    os._exit(0)  # nao espera as consultas de rede em segundo plano (fechar fica instantaneo e sem erro)
