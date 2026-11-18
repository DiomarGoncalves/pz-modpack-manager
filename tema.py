"""Tema visual da janela (ttk "clam" estilizado; sem instalar nada a mais).
Dois modos: escuro (padrao, cara de Project Zomboid) e claro."""
import sys
import tkinter as tk
from tkinter import font as tkfont
from tkinter import ttk

PALETAS = {
    "escuro": {
        "fundo": "#1d2023", "cartao": "#25292e", "campo": "#2e3339", "borda": "#3b4249",
        "texto": "#e7e9eb", "sutil": "#98a2ab", "destaque": "#c0392b", "destaque2": "#d84a3b",
        "selecao": "#a8322a", "sel_texto": "#ffffff", "zebra": "#2a2f35",
        "ok": "#6cc679", "aviso": "#e8a83e", "erro": "#ff6b6b", "info": "#74aee0",
        "separado": "#a9a3d6", "apagado": "#6c757d",
        "banner_aviso": "#463717", "banner_aviso_t": "#ffd27a",
        "banner_ok": "#1e3624", "banner_ok_t": "#93dca0",
        "dica": "#30363d", "dica_t": "#e7e9eb",
        "lateral": "#16181b", "lateral_ativo": "#2a2f35", "botao": "#343a41",
    },
    "claro": {
        "fundo": "#f2f3f5", "cartao": "#ffffff", "campo": "#ffffff", "borda": "#cdd2d8",
        "texto": "#1f2328", "sutil": "#5d6874", "destaque": "#b03027", "destaque2": "#c73b31",
        "selecao": "#b03027", "sel_texto": "#ffffff", "zebra": "#f6f7f9",
        "ok": "#2e7d32", "aviso": "#a86200", "erro": "#b00020", "info": "#1f5fa8",
        "separado": "#55557a", "apagado": "#9a9a9a",
        "banner_aviso": "#fff3cd", "banner_aviso_t": "#6e4b00",
        "banner_ok": "#e5f4e8", "banner_ok_t": "#1d6630",
        "dica": "#ffffe6", "dica_t": "#222222",
        "lateral": "#e4e7eb", "lateral_ativo": "#ffffff", "botao": "#e6e9ed",
    },
}

ATUAL = dict(PALETAS["escuro"])
ICONES = {"ok": "✔", "aviso": "⚠", "erro": "✖", "separado": "◇", "baixado": "↓"}


def cor(nome):
    return ATUAL[nome]


def _fontes():
    padrao = tkfont.nametofont("TkDefaultFont")
    if sys.platform.startswith("win"):
        padrao.configure(family="Segoe UI", size=10)
    else:
        padrao.configure(size=10)
    for nome in ("TkTextFont", "TkMenuFont"):
        tkfont.nametofont(nome).configure(family=padrao.actual("family"), size=10)
    tkfont.nametofont("TkHeadingFont").configure(family=padrao.actual("family"), size=10, weight="bold")
    fixa = tkfont.nametofont("TkFixedFont")
    fixa.configure(size=9)
    return padrao


def aplicar(raiz, modo="escuro"):
    """Aplica o tema em toda a janela. Pode ser chamado de novo para trocar de modo."""
    ATUAL.clear()
    ATUAL.update(PALETAS.get(modo, PALETAS["escuro"]))
    p = ATUAL
    padrao = _fontes()
    negrito = (padrao.actual("family"), 10, "bold")
    pequeno_negrito = (padrao.actual("family"), 9, "bold")
    alt_linha = padrao.metrics("linespace") + 10

    s = ttk.Style(raiz)
    s.theme_use("clam")
    s.configure(".", background=p["fundo"], foreground=p["texto"], fieldbackground=p["campo"],
                bordercolor=p["borda"], lightcolor=p["fundo"], darkcolor=p["fundo"], troughcolor=p["fundo"],
                focuscolor=p["destaque"], selectbackground=p["selecao"], selectforeground=p["sel_texto"],
                insertcolor=p["texto"], font=padrao)
    s.map(".", foreground=[("disabled", p["apagado"])])

    # Botoes
    s.configure("TButton", background=p["botao"], foreground=p["texto"], bordercolor=p["borda"],
                lightcolor=p["botao"], darkcolor=p["botao"], padding=(12, 5), relief="flat", focusthickness=0)
    s.map("TButton", background=[("disabled", p["fundo"]), ("pressed", p["borda"]), ("active", p["borda"])],
          bordercolor=[("focus", p["destaque"])], foreground=[("disabled", p["apagado"])])
    s.configure("Accent.TButton", background=p["destaque"], foreground="#ffffff", bordercolor=p["destaque"],
                lightcolor=p["destaque"], darkcolor=p["destaque"], font=negrito)
    s.map("Accent.TButton", background=[("disabled", p["borda"]), ("pressed", p["selecao"]), ("active", p["destaque2"])],
          bordercolor=[("active", p["destaque2"])], foreground=[("disabled", p["sutil"])])

    # Campos
    s.configure("TEntry", fieldbackground=p["campo"], foreground=p["texto"], bordercolor=p["borda"],
                lightcolor=p["campo"], darkcolor=p["campo"], padding=(6, 5), insertcolor=p["texto"])
    s.map("TEntry", bordercolor=[("focus", p["destaque"])], lightcolor=[("focus", p["destaque"])])
    s.configure("TCombobox", fieldbackground=p["campo"], background=p["campo"], foreground=p["texto"],
                arrowcolor=p["texto"], bordercolor=p["borda"], lightcolor=p["campo"], darkcolor=p["campo"],
                padding=(6, 4), arrowsize=14)
    s.map("TCombobox", fieldbackground=[("readonly", p["campo"])], foreground=[("readonly", p["texto"])],
          selectbackground=[("readonly", p["campo"])], selectforeground=[("readonly", p["texto"])],
          bordercolor=[("focus", p["destaque"])], background=[("active", p["borda"])])
    raiz.option_add("*TCombobox*Listbox.background", p["campo"])
    raiz.option_add("*TCombobox*Listbox.foreground", p["texto"])
    raiz.option_add("*TCombobox*Listbox.selectBackground", p["selecao"])
    raiz.option_add("*TCombobox*Listbox.selectForeground", p["sel_texto"])
    s.configure("TCheckbutton", background=p["fundo"], foreground=p["texto"], indicatorbackground=p["campo"],
                indicatorforeground=p["sel_texto"], indicatormargin=(0, 0, 6, 0))
    s.map("TCheckbutton", indicatorbackground=[("selected", p["destaque"])],
          background=[("active", p["fundo"])])

    # Abas
    s.configure("TNotebook", background=p["fundo"], borderwidth=0, tabmargins=(0, 4, 0, 0))
    s.configure("TNotebook.Tab", background=p["fundo"], foreground=p["sutil"], padding=(16, 7),
                borderwidth=0, lightcolor=p["fundo"], bordercolor=p["fundo"])
    s.map("TNotebook.Tab", background=[("selected", p["cartao"]), ("active", p["campo"])],
          foreground=[("selected", p["texto"]), ("active", p["texto"])],
          lightcolor=[("selected", p["destaque"])], expand=[("selected", (0, 2, 0, 0))])

    # Tabelas
    s.configure("Treeview", background=p["cartao"], fieldbackground=p["cartao"], foreground=p["texto"],
                rowheight=alt_linha, borderwidth=0, bordercolor=p["borda"])
    s.map("Treeview", background=[("selected", p["selecao"])], foreground=[("selected", p["sel_texto"])])
    s.configure("Treeview.Heading", background=p["campo"], foreground=p["sutil"], relief="flat",
                padding=(6, 6), font=pequeno_negrito, bordercolor=p["borda"], lightcolor=p["campo"], darkcolor=p["campo"])
    s.map("Treeview.Heading", background=[("active", p["borda"])], foreground=[("active", p["texto"])])

    # Barras de rolagem, progresso, molduras
    for o in ("Vertical", "Horizontal"):
        s.configure("%s.TScrollbar" % o, background=p["campo"], troughcolor=p["fundo"], bordercolor=p["fundo"],
                    arrowcolor=p["sutil"], lightcolor=p["campo"], darkcolor=p["campo"], gripcount=0, arrowsize=12)
        s.map("%s.TScrollbar" % o, background=[("active", p["borda"])])
    s.configure("Horizontal.TProgressbar", background=p["destaque"], troughcolor=p["campo"], bordercolor=p["campo"],
                lightcolor=p["destaque"], darkcolor=p["destaque"], thickness=10)
    s.configure("TLabelframe", background=p["fundo"], bordercolor=p["borda"], lightcolor=p["fundo"], darkcolor=p["fundo"])
    s.configure("TLabelframe.Label", background=p["fundo"], foreground=p["texto"], font=negrito)
    s.configure("TPanedwindow", background=p["fundo"])
    s.configure("Sash", sashthickness=6, gripcount=0, background=p["fundo"], lightcolor=p["fundo"], bordercolor=p["fundo"])

    # Textos
    s.configure("TLabel", background=p["fundo"], foreground=p["texto"])
    s.configure("Sutil.TLabel", foreground=p["sutil"])
    s.configure("Titulo.TLabel", font=negrito)
    s.configure("Marca.TLabel", font=(padrao.actual("family"), 12, "bold"), foreground=p["destaque2"])
    s.configure("Secao.TLabel", foreground=p["sutil"], font=pequeno_negrito, padding=(2, 4, 0, 0))
    s.configure("BannerAviso.TLabel", background=p["banner_aviso"], foreground=p["banner_aviso_t"], padding=(10, 6))
    s.configure("BannerOk.TLabel", background=p["banner_ok"], foreground=p["banner_ok_t"], padding=(10, 6))
    s.configure("Cartao.TFrame", background=p["cartao"], relief="flat")
    grande = (padrao.actual("family"), 17, "bold")
    s.configure("Pagina.TLabel", font=grande)
    s.configure("Subtitulo.TLabel", foreground=p["sutil"])

    # Menu lateral
    s.configure("Lateral.TFrame", background=p["lateral"])
    s.configure("Lateral.TLabel", background=p["lateral"], foreground=p["texto"])
    s.configure("LateralSecao.TLabel", background=p["lateral"], foreground=p["sutil"], font=pequeno_negrito)
    s.configure("LateralMarca.TLabel", background=p["lateral"], foreground=p["destaque2"],
                font=(padrao.actual("family"), 13, "bold"))
    s.configure("Nav.TButton", background=p["lateral"], foreground=p["sutil"], anchor="w", padding=(14, 9),
                bordercolor=p["lateral"], lightcolor=p["lateral"], darkcolor=p["lateral"], relief="flat")
    s.map("Nav.TButton", background=[("active", p["lateral_ativo"])], foreground=[("active", p["texto"])],
          bordercolor=[("focus", p["lateral"])])
    s.configure("NavAtivo.TButton", background=p["lateral_ativo"], foreground=p["texto"], anchor="w",
                padding=(14, 9), bordercolor=p["destaque"], lightcolor=p["lateral_ativo"],
                darkcolor=p["lateral_ativo"], relief="flat", font=negrito)
    s.map("NavAtivo.TButton", background=[("active", p["lateral_ativo"])], bordercolor=[("focus", p["destaque"])])
    s.configure("Pequeno.TButton", padding=(8, 4))

    # Cartoes do passo a passo
    s.configure("CartaoTitulo.TLabel", background=p["cartao"], foreground=p["texto"], font=negrito)
    s.configure("CartaoTexto.TLabel", background=p["cartao"], foreground=p["sutil"])
    for nome in ("ok", "aviso", "erro"):
        s.configure("Cartao%s.TLabel" % nome.capitalize(), background=p["cartao"], foreground=p[nome])
    s.configure("Numero.TLabel", background=p["cartao"], foreground=p["destaque2"],
                font=(padrao.actual("family"), 15, "bold"))

    # Campo com texto de exemplo, menus
    s.configure("Dica.TEntry", foreground=p["sutil"])
    s.configure("TMenubutton", background=p["botao"], foreground=p["texto"], bordercolor=p["borda"],
                lightcolor=p["botao"], darkcolor=p["botao"], arrowcolor=p["texto"], padding=(12, 5), relief="flat")
    s.map("TMenubutton", background=[("active", p["borda"]), ("pressed", p["borda"])])
    for chave, valor in (("*Menu.background", p["campo"]), ("*Menu.foreground", p["texto"]),
                         ("*Menu.activeBackground", p["selecao"]), ("*Menu.activeForeground", p["sel_texto"]),
                         ("*Menu.relief", "flat"), ("*Menu.borderWidth", 1), ("*Menu.activeBorderWidth", 0),
                         ("*Menu.disabledForeground", p["apagado"])):
        raiz.option_add(chave, valor)

    # Notebook sem abas (as paginas sao trocadas pelo menu lateral)
    s.layout("Paginas.TNotebook.Tab", [])
    s.configure("Paginas.TNotebook", background=p["fundo"], borderwidth=0, padding=0, tabmargins=0,
                bordercolor=p["fundo"], lightcolor=p["fundo"], darkcolor=p["fundo"])

    # Widgets tk (dialogos de arquivo no Linux, janelas extras)
    raiz.configure(background=p["fundo"])
    for chave, valor in (("*Toplevel.background", p["fundo"]), ("*Background", p["fundo"]),
                         ("*Foreground", p["texto"]), ("*selectBackground", p["selecao"]),
                         ("*selectForeground", p["sel_texto"]), ("*Entry.Background", p["campo"]),
                         ("*Listbox.Background", p["cartao"]), ("*insertBackground", p["texto"]),
                         ("*highlightBackground", p["fundo"]), ("*highlightColor", p["destaque"]),
                         ("*activeBackground", p["borda"]), ("*activeForeground", p["texto"]),
                         ("*troughColor", p["fundo"])):
        raiz.option_add(chave, valor)


def menu(m):
    """Cores de um tk.Menu ja criado (para a troca de tema)."""
    p = ATUAL
    m.configure(background=p["campo"], foreground=p["texto"], activebackground=p["selecao"],
                activeforeground=p["sel_texto"], relief="flat", borderwidth=1, activeborderwidth=0,
                disabledforeground=p["apagado"])


def texto(widget):
    """Estilo do tk.Text (registro e resultados)."""
    p = ATUAL
    widget.configure(background=p["cartao"], foreground=p["texto"], insertbackground=p["texto"],
                     selectbackground=p["selecao"], selectforeground=p["sel_texto"], relief="flat",
                     highlightthickness=1, highlightbackground=p["borda"], highlightcolor=p["borda"],
                     borderwidth=0, padx=8, pady=6)


def tabela(tree):
    """Cores das situacoes e linhas alternadas."""
    p = ATUAL
    for tag, c in (("dentro", "ok"), ("aviso", "aviso"), ("erro", "erro"),
                   ("separado", "separado"), ("baixado", "info"), ("b41", "apagado")):
        tree.tag_configure(tag, foreground=p[c])
    tree.tag_configure("par", background=p["zebra"])


def zebra(tree):
    """Pinta uma linha sim, outra nao (chamar depois de preencher)."""
    for n, i in enumerate(tree.get_children()):
        tags = [t for t in tree.item(i, "tags") if t != "par"]
        if n % 2:
            tags.append("par")
        tree.item(i, tags=tags)


def icone(tag):
    return ICONES.get(tag, "•")
