#!/usr/bin/env bash
set -euo pipefail
SERVICIOS_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# Los argumentos de servidor conservan el modo web para uso avanzado.
SERVICIOS_MODO=auto
case "${1:-}" in
  --terminal) SERVICIOS_MODO=terminal; shift ;;
  --gui) SERVICIOS_MODO=gui; shift ;;
  --serve|--no-browser|--port|--panel|--help|-h) SERVICIOS_MODO=gui ;;
esac
if [ "$SERVICIOS_MODO" = auto ]; then
  if [ -n "${DISPLAY:-}" ] || [ -n "${WAYLAND_DISPLAY:-}" ]; then
    SERVICIOS_MODO=gui
  else
    SERVICIOS_MODO=terminal
  fi
fi
SERVICIOS_SCRIPT=mis_servicios.py
if [ "$SERVICIOS_MODO" = terminal ]; then
  SERVICIOS_SCRIPT=servicios_terminal.py
fi
if [ -x "$SERVICIOS_DIR/venv/bin/python" ]; then
  if [ "$SERVICIOS_MODO" = gui ]; then
    exec "$SERVICIOS_DIR/venv/bin/python" "$SERVICIOS_DIR/scripts/$SERVICIOS_SCRIPT" --serve "$@"
  fi
  exec "$SERVICIOS_DIR/venv/bin/python" "$SERVICIOS_DIR/scripts/$SERVICIOS_SCRIPT" "$@"
elif command -v python3 >/dev/null 2>&1; then
  if [ "$SERVICIOS_MODO" = gui ]; then
    exec python3 "$SERVICIOS_DIR/scripts/$SERVICIOS_SCRIPT" --serve "$@"
  fi
  exec python3 "$SERVICIOS_DIR/scripts/$SERVICIOS_SCRIPT" "$@"
else
  MENSAJE='Falta Python 3. Abrí instalar_nucleo_ia.sh en esta carpeta y después volvé a Mis servicios.'
  if [ "$SERVICIOS_MODO" = gui ] && command -v zenity >/dev/null 2>&1; then
    zenity --error --title='Mis servicios — Núcleo IA' --text="$MENSAJE"
  elif [ "$SERVICIOS_MODO" = gui ] && command -v kdialog >/dev/null 2>&1; then
    kdialog --error "$MENSAJE"
  else
    printf '%s\n' "$MENSAJE"
  fi
  exit 1
fi
