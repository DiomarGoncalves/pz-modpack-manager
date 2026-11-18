#!/bin/bash
# Compila para Linux: binario unico + AppImage (portateis).
#   bash build/build_linux.sh                                          (o PZ Modpack Manager)
#   NOME=PZLauncher ENTRADA=launcher_gui.py bash build/build_linux.sh  (o launcher dos jogadores)
# Precisa: python3 com tkinter, pip install pyinstaller (e pillow, opcional).
# Saida: dist/<NOME> (binario) e dist/<NOME>-x86_64.AppImage
set -e
AQUI="$(cd "$(dirname "$0")" && pwd)"
SRC="$(dirname "$AQUI")"
DIST="$SRC/dist"
TMP="${TMPDIR:-/tmp}/modpack_build_$$"
PYI="${PYINSTALLER:-pyinstaller}"
NOME="${NOME:-ModpackServidor}"
ENTRADA="${ENTRADA:-modpack_gui.py}"
TITULO="${TITULO:-PZ Modpack Manager}"
mkdir -p "$DIST" "$TMP"
cd "$SRC"
"$PYI" --noconfirm --clean --onefile --windowed --name "$NOME" \
  --add-data "$SRC/preview_padrao.png:." --hidden-import PIL._tkinter_finder \
  --distpath "$DIST" --workpath "$TMP/work" --specpath "$TMP" "$SRC/$ENTRADA"
echo "binario: $DIST/$NOME"

# AppImage (precisa do appimagetool: APPIMAGETOOL=/caminho/appimagetool)
if [ -n "$APPIMAGETOOL" ]; then
  APPDIR="$TMP/$NOME.AppDir"
  mkdir -p "$APPDIR/usr/bin"
  cp "$DIST/$NOME" "$APPDIR/usr/bin/"
  cp "$AQUI/icone.png" "$APPDIR/modpackservidor.png"
  cat > "$APPDIR/modpackservidor.desktop" <<DESK
[Desktop Entry]
Type=Application
Name=$TITULO
Comment=Monta modpacks de servidor do Project Zomboid
Exec=$NOME
Icon=modpackservidor
Categories=Utility;
Terminal=false
DESK
  cat > "$APPDIR/AppRun" <<'RUN'
#!/bin/sh
HERE="$(dirname "$(readlink -f "$0")")"
exec "$HERE/usr/bin/NOME_DO_APP" "$@"
RUN
  sed -i "s/NOME_DO_APP/$NOME/" "$APPDIR/AppRun"
  chmod +x "$APPDIR/AppRun"
  ARCH=x86_64 "$APPIMAGETOOL" --appimage-extract-and-run "$APPDIR" "$DIST/$NOME-x86_64.AppImage" >/dev/null 2>&1 \
    || ARCH=x86_64 "$APPIMAGETOOL" "$APPDIR" "$DIST/$NOME-x86_64.AppImage"
  echo "AppImage: $DIST/"$NOME"-x86_64.AppImage"
fi
rm -rf "$TMP"
