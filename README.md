# PZ Modpack Manager

Programa para donos de servidor de **Project Zomboid (Build 42)** criarem e manterem o **modpack do servidor**: um item **não listado** na Workshop com todos os mods dentro, **congelados** na versão que você testou. Quando o autor de um mod atualiza, o seu servidor não quebra e os jogadores não levam kick por versão diferente.

Funciona no **Windows** e no **Linux** (Steam normal ou Flatpak). Não precisa instalar nada.

## Baixar

Vá em **[Releases](../../releases/latest)** e baixe:

| Sistema | Arquivo | Como abrir |
|---|---|---|
| Windows | `ModpackServidor.exe` | Dois cliques. Se aparecer "O Windows protegeu o computador", clique em **Mais informações → Executar assim mesmo** (o programa não tem assinatura paga). |
| Linux | `ModpackServidor-x86_64.AppImage` | Botão direito → Propriedades → **Permitir executar como programa** (ou `chmod +x`), depois dois cliques. |

Os seus modpacks ficam na pasta **`ModpackServidor_dados`**, ao lado do programa. Para levar tudo para outro PC, é só copiar as duas coisas juntas.

## O que ele faz

- **Passo a passo na tela:** ① mods → ② montar o pacote → ③ arquivo `.ini` do servidor. Cada etapa mostra se está ok e traz o botão do que fazer agora. Clique num mod e aparece embaixo o que a situação dele significa.
- **O `.ini` se atualiza sozinho:** você escolhe o `.ini` do servidor uma vez. Depois, cada "Montar pacote" já gera o `.ini` novo (uma cópia na pasta `pronto/`, ao lado do original) e mostra onde ele está.
- **Procurar na Steam:** busca mods da Workshop por nome, com filtro Build 42, autor, inscritos e data, e adiciona com um clique.
- **Download automático:** baixa os mods sozinho pela SteamCMD oficial da Valve, com login anônimo (sem conta e sem se inscrever). Também dá para baixar do jeito normal, se inscrevendo na Steam.
- **Dependências automáticas:** se um mod precisa de outro, o outro entra junto e na ordem certa do `Mods=`.
- **Versões congeladas:** o que já está no pacote não muda quando a Steam baixa uma versão nova. Para atualizar, você escolhe quando e quais mods.
- **Gera o `.ini` do servidor:** copia o seu `.ini` trocando só o `Mods=` e o `WorkshopItems=`, e confere tudo (mod faltando, ordem de dependências, pacote ausente...).
- **Conferências:**
  - se o pacote publicado está visível e igual ao montado;
  - se o `.ini` está certo;
  - o log do servidor ou do jogo: quais mods carregaram e quais deram erro, com os códigos de erro da Steam traduzidos.
- **Servidor sem Steam (`-nosteam`):** exporta um `.zip` com todos os mods para o servidor e para os jogadores, que instalam com um clique.
- **Restaurar:** se a pasta do pacote for apagada, ele recria as versões congeladas a partir do pacote publicado.
- **Vários servidores:** um modpack para cada um.
- **Tema escuro e claro.** Passe o mouse em cima de qualquer botão para ver o que ele faz.

## Como usar

1. **＋ Novo** (menu ao lado): dê um nome, a versão do jogo (ex.: `42.21`) e, se quiser, escolha o `.ini` atual do servidor. A lista de mods vem dele.
2. Adicione mods: cole o ID ou o link, ou use **Procurar na Steam**.
3. **Montar pacote.**
4. No jogo: **Workshop > Criar e atualizar itens > (pasta do modpack) > Publicar**. Espere aparecer "success updating item".
5. Passo ③ **Escolher .ini do servidor**: o app grava uma cópia certa em `pronto/<mesmo nome>.ini` (o seu original não muda) → suba essa cópia em `Zomboid/Server/` com o servidor **desligado** → ligue. Das próximas vezes, o "Montar pacote" já atualiza esse arquivo.

Os **jogadores não fazem nada**: entram no servidor e a Steam baixa o pacote sozinha. Só precisam estar na mesma versão do jogo (Steam → Propriedades → Betas) e **não** estar inscritos nos mods originais que estão no pacote.

**Para atualizar mods depois:** quando a Steam baixar versões novas, o passo ② avisa. Teste no seu jogo, clique em **Atualizar e montar**, publique de novo e reinicie o servidor.

**Mod fora do pacote:** por padrão todo mod entra no pacote. Se quiser que algum venha da Workshop original (um mod que você mesmo atualiza sempre, por exemplo), use **Mais ações → Separar / juntar**.

## PZ Modpack Launcher (para os jogadores)

Um programa separado, o `PZLauncher.exe` ou `PZLauncher-x86_64.AppImage` nas Releases, que deixa a pasta `Zomboid/mods` **igual ao modpack do servidor**:

1. Abra, clique em **＋ Adicionar modpack** e cole o link do `.zip`. Funciona com Google Drive (qualquer link de compartilhamento), Dropbox ou link direto.
2. Clique em **Ativar e atualizar**. O launcher acha a pasta do jogo sozinho (Windows, Linux e Steam Flatpak).

**Baixa só o que mudou:** o launcher lê o índice do `.zip` por partes e compara **arquivo por arquivo** (CRC) com o que você já tem. Numa atualização do modpack, só os arquivos alterados são baixados, e não o zip inteiro.

**O que ele faz com a pasta `mods`:**
- **arquivos de mods que saíram do pack:** são apagados;
- **arquivos mexidos no PC:** voltam ao original;
- **mods soltos que não são do pack:** vão para `Zomboid/mods_removidos/<data>/` (não são apagados).

**Vários servidores:** dá para cadastrar vários modpacks, mas fica **um ativo por vez**. Ao trocar, os mods do outro ficam guardados e voltam sem baixar de novo.

**Atualiza sozinho:** confere os links ao abrir e a cada 30 minutos, e atualiza o pack ativo se mudou. Também avisa quando sai uma versão nova do próprio launcher.

**Desativar (jogar na Steam):** tira os mods do pack da pasta, para não ficar mod duplicado com a Workshop; ao ativar de novo, voltam na hora.

**Para o dono do servidor:** use **Exportar zip nosteam** (no app de modpack) ou qualquer `.zip` com as pastas dos mods na raiz. Suba no Drive como "qualquer pessoa com o link" e mande o link para o pessoal. Para atualizar, troque o arquivo **no mesmo link**: no Drive, Gerenciar versões > Enviar nova versão.

## Servidor sem Steam (`-nosteam`)

Na página **Sem Steam**:

- **Dono do servidor:**
  1. **Exportar zip nosteam**.
  2. **Gerar .ini nosteam** (`WorkshopItems=` vazio).
  3. No servidor: extraia o zip dentro da pasta `Zomboid`, suba o `.ini` e ligue com `-nosteam`.
- **Jogador:**
  1. **Instalar .zip do modpack**, o mesmo zip do servidor. O programa apaga a versão anterior e não mexe nos outros mods.
  2. Abra o jogo com `-nosteam`.

Steam e `-nosteam` não se misturam: cada modo só aceita jogadores do mesmo modo.

## Linha de comando

Tudo da janela também funciona pelo terminal:

```
python3 modpack.py --help
python3 modpack.py novo "Meu Servidor" --ini servidor.ini --branch 42.21
python3 modpack.py --pack Meu_Servidor adicionar <id ou link>
python3 modpack.py --pack Meu_Servidor montar
python3 modpack.py --pack Meu_Servidor ini servidor.ini
python3 modpack.py procurar "generator"
python3 modpack.py baixar 2972289937
```

## Rodar pelo código ou compilar

- **Rodar:** precisa de Python 3.10+ com tkinter. Use `python3 modpack_gui.py` ou, no Windows, `Abrir modpack (Windows).bat`. O Pillow é opcional e só serve para gerar a imagem de capa do pacote.
- **Compilar no Linux:** `pip install pyinstaller` e depois `bash build/build_linux.sh`. Para gerar também o AppImage, defina `APPIMAGETOOL=/caminho/appimagetool`.
- **GitHub Actions:**
  - a cada push, compila Windows e Linux e deixa os arquivos em **Actions > Artifacts**;
  - uma tag `v*` (ex.: `git tag v1.0.1 && git push --tags`) publica a **Release** com os arquivos.

## Avisos

- Os mods pertencem aos seus autores. A descrição do pacote na Workshop lista cada mod original com o link, e o pacote é **não listado**, feito só para os jogadores do servidor. Respeite o pedido de qualquer autor que não queira o mod dele em modpack.
- O programa não usa a sua conta da Steam. O download automático usa login anônimo, e a publicação é feita por você, dentro do jogo.

## Licença

[MIT](LICENSE): use, modifique e compartilhe à vontade, mantendo os créditos.
