#!/bin/sh
# Instala o Pomodoro Pet no menu de aplicativos do usuario (Linux/XDG).
#
#   ./desktop/install.sh [argumentos do app]   ex.: ./desktop/install.sh --scale 3
#   ./desktop/install.sh --uninstall
#
# Nada e instalado fora do seu diretorio pessoal e nenhum privilegio e
# necessario: tudo vai para $XDG_DATA_HOME (ou ~/.local/share).

set -eu

HERE=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
APPDIR=$(dirname -- "$HERE")
NAME=pomodoro-pet
DATA=${XDG_DATA_HOME:-$HOME/.local/share}
APPS=$DATA/applications
ICONS=$DATA/icons/hicolor
DESKTOP=$APPS/$NAME.desktop

refresh() {
    [ -x "$(command -v update-desktop-database 2>/dev/null)" ] \
        && update-desktop-database "$APPS" 2>/dev/null || true
    [ -x "$(command -v gtk-update-icon-cache 2>/dev/null)" ] \
        && gtk-update-icon-cache -qtf "$ICONS" 2>/dev/null || true
    [ -x "$(command -v kbuildsycoca6 2>/dev/null)" ] \
        && kbuildsycoca6 --noincremental >/dev/null 2>&1 || true
}

if [ "${1:-}" = "--uninstall" ]; then
    rm -f "$DESKTOP"
    for dir in "$ICONS"/*/apps; do
        rm -f "$dir/$NAME.png"
    done
    refresh
    echo "Removido: $DESKTOP e os icones."
    exit 0
fi

# Python: o venv do projeto, se existir; senao o do sistema.
if [ -x "$APPDIR/.venv/bin/python" ]; then
    PYTHON=$APPDIR/.venv/bin/python
else
    PYTHON=$(command -v python3 || command -v python)
fi
[ -n "$PYTHON" ] || { echo "python nao encontrado" >&2; exit 1; }

# Terminal para a acao "ver focos por dia" (--stats escreve no stdout).
TERMINAL=
for candidate in konsole gnome-terminal xfce4-terminal alacritty kitty xterm; do
    if command -v "$candidate" >/dev/null 2>&1; then
        case $candidate in
            konsole)        TERMINAL="konsole --hold -e" ;;
            gnome-terminal) TERMINAL="gnome-terminal --" ;;
            xterm)          TERMINAL="xterm -hold -e" ;;
            *)              TERMINAL="$candidate -e" ;;
        esac
        break
    fi
done

echo "app:     $APPDIR"
echo "python:  $PYTHON"
echo "args:    ${*:-(nenhum)}"

"$PYTHON" "$HERE/make_icons.py" "$HERE/icons" >/dev/null

mkdir -p "$APPS"
for size_dir in "$HERE"/icons/*/; do
    size=$(basename -- "$size_dir")
    mkdir -p "$ICONS/$size/apps"
    cp -- "$size_dir/$NAME.png" "$ICONS/$size/apps/$NAME.png"
done

# Substitui os marcadores do template. Sem terminal disponivel, a acao de
# estatisticas e removida em vez de virar um lancador quebrado.
sed -e "s|@PYTHON@|$PYTHON|g" \
    -e "s|@APPDIR@|$APPDIR|g" \
    -e "s|@ARGS@|$*|g" \
    -e "s|@TERMINAL@|$TERMINAL|g" \
    "$HERE/$NAME.desktop.in" > "$DESKTOP.tmp"

if [ -z "$TERMINAL" ]; then
    sed -e '/^Actions=/d' -e '/^\[Desktop Action Stats\]/,$d' \
        "$DESKTOP.tmp" > "$DESKTOP.tmp2"
    mv -- "$DESKTOP.tmp2" "$DESKTOP.tmp"
fi

mv -- "$DESKTOP.tmp" "$DESKTOP"
chmod 644 "$DESKTOP"
refresh

echo
echo "Instalado: $DESKTOP"
echo "Procure por \"Pomodoro Pet\" no menu. Para fixar na barra de tarefas,"
echo "clique com o botao direito no item do menu e escolha fixar no painel."
if command -v desktop-file-validate >/dev/null 2>&1; then
    desktop-file-validate "$DESKTOP" && echo "Arquivo .desktop valido."
fi
