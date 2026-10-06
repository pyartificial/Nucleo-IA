#!/bin/bash
set -euo pipefail

if [ ! -t 0 ] && [ -z "${IN_TERMINAL:-}" ]; then
  export IN_TERMINAL=1
  for term in konsole gnome-terminal xfce4-terminal x-terminal-emulator mate-terminal kitty alacritty xterm; do
    if command -v "$term" >/dev/null 2>&1; then
      case "$term" in
        konsole) exec "$term" -e bash "$0" "$@" ;;
        gnome-terminal|mate-terminal) exec "$term" -- bash "$0" "$@" ;;
        *) exec "$term" -e bash "$0" "$@" ;;
      esac
    fi
  done
fi

ROOT="$(cd "$(dirname "$0")" && pwd)"
if [ -x "$ROOT/venv/bin/python" ]; then
  "$ROOT/venv/bin/python" "$ROOT/scripts/reparar_ollama.py" "$@"
else
  python3 "$ROOT/scripts/reparar_ollama.py" "$@"
fi
echo
read -r -p "Presiona ENTER para cerrar..." _
