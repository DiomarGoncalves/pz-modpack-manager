# PZ Modpack Launcher — plano

Um programa separado, distribuído junto com o PZ Modpack Manager no mesmo repositório e nas mesmas Releases, para os **jogadores**:

1. A pessoa cola o link de um modpack (Google Drive ou link direto).
2. O launcher acha a pasta `Zomboid/mods` sozinho.
3. Ele deixa essa pasta **igual ao modpack**, baixando **só os arquivos que mudaram**, do jeito que o GitHub faz.

## Decisões (com o Diomar, 15/11/2026)

- **Mods na pasta que não estão no modpack:** são **apagados** (decisão de 18/11/2026; antes iam para um backup).
- **Formato:** um **programa completo e separado**, que **se atualiza sozinho**. Ele confere os modpacks ao abrir e de tempos em tempos, e também confere a versão nova do próprio launcher nas Releases do GitHub.
- **Modpacks:** **um ativo por vez**. Dá para cadastrar vários e alternar entre eles. Ao trocar, os mods do pack que sai são apagados. Só o botão **Desativar** guarda os mods em `Zomboid/PZLauncher/estacionados/<pack>/`, para jogar na Steam; eles voltam sem baixar.

## O que foi testado com o link real (`ModpackPiveteServer.zip` no Drive)

- **Link direto do Drive:** `https://drive.usercontent.google.com/download?id=<ID>&export=download&confirm=t` funciona sem login, até para arquivo grande.
- **O Drive responde 206 a pedidos com `Range`.** Dá para baixar um pedaço qualquer do arquivo.
- **Detectar mudança sem baixar nada:** pelos cabeçalhos `content-length` (1.626.490.455), `last-modified` e `content-disposition` (o nome do arquivo).
- **O zip:**
  - **17.701 arquivos**, 1,90 GB descompactado, sem zip64;
  - o **índice** (central directory) tem **2,6 MB** e fica no fim do arquivo;
  - as pastas dos mods ficam **direto na raiz** (Bandits/, Fletcher/, damnlib/...), que é o formato de `Zomboid/mods`.

## Como funciona a sincronização

1. **Ler o índice:**
   - baixar os últimos 64 KB e achar o fim do zip (EOCD, ou o EOCD64 do zip64);
   - baixar o índice, que dá cada arquivo com nome, CRC32, tamanhos, método e posição.
2. **Comparar com o PC:**
   - um arquivo de estado em `Zomboid/PZLauncher/<pack>.json` guarda o caminho, o tamanho, o mtime e o CRC de cada arquivo instalado;
   - o CRC só é recalculado quando o tamanho ou o mtime mudaram.
3. **O que fazer:**
   - **baixar:** arquivos que faltam ou com CRC diferente;
   - **apagar:** arquivos dentro das pastas do pack que não estão mais no pack;
   - **apagar:** pastas de `mods/` que não são do pack ativo.
4. **Baixar só o necessário:**
   - juntar os trechos vizinhos num pedido só (com um espaço de até 1 MB entre eles, e no máximo 64 MB por pedido);
   - em cada arquivo, pular o cabeçalho local (30 bytes, mais o nome e o extra);
   - descompactar (método 8 = deflate; 0 = sem compressão) e conferir o CRC;
   - gravar num arquivo temporário e trocar (`os.replace`).
5. **Se o servidor não aceitar `Range`** (responder 200): baixa o arquivo inteiro para uma pasta temporária e usa a mesma lógica com o arquivo local.

## Peças

- **`launcher_sync.py`:** o motor, sem tela e com testes:
  - fontes: `HttpSource` e `ArquivoSource`;
  - links: normaliza o link do Drive e aceita links diretos;
  - índice do zip, plano e aplicação;
  - estado, estacionar e backup.
- **`launcher_gui.py`:** a tela (com o `tema.py`):
  - a lista de modpacks, com nome, situação, tamanho e o ativo;
  - os botões Adicionar link, Ativar, Atualizar agora, Remover e Abrir pasta mods;
  - a barra de progresso;
  - a conferência automática ao abrir e a cada 30 minutos;
  - o aviso de versão nova do launcher.
- **Build:** um segundo executável (`PZLauncher`, `.exe` e `.AppImage`) no mesmo workflow e na mesma Release.

## Cuidados

- **`Zomboid/mods` vale também no modo Steam.** Mod local tem prioridade sobre o da Workshop, então jogar num servidor Steam com o mesmo mod em versão diferente dá kick por checksum. Por isso vai existir o botão **Desativar** (estaciona tudo).
- **O Drive limita downloads** de arquivo grande e muito baixado ("muitos downloads nas últimas 24 h"). Baixar só o que mudou ajuda bastante. O launcher deve mostrar esse erro com clareza.

## Estado (15/11/2026)

**Feito, na versão 1.0.0:**
- `launcher_sync.py`, com testes em `tests/test_launcher.py`, que passam todos;
- testado com o link real: índice em 5 segundos e o download de um mod sozinho, com o CRC conferido;
- `launcher_gui.py`, testado numa tela virtual;
- o build no workflow (`PZLauncher.exe` e `PZLauncher-x86_64.AppImage`).

**Falta:**
- testar no Windows;
- trocar o próprio launcher sozinho (por enquanto ele só avisa e abre a página da Release);
- ícone próprio.
