#!/bin/bash
set -euo pipefail

# Auto-detectar si se ejecutó por doble clic (sin terminal TTY) y abrir ventana de terminal
if [ ! -t 0 ] && [ -z "${IN_TERMINAL:-}" ]; then
  export IN_TERMINAL=1
  for term in konsole gnome-terminal xfce4-terminal x-terminal-emulator mate-terminal kitty alacritty xterm; do
    if command -v "$term" >/dev/null 2>&1; then
      case "$term" in
        konsole)
          exec "$term" -e bash "$0" "$@"
          ;;
        gnome-terminal|mate-terminal)
          exec "$term" -- bash "$0" "$@"
          ;;
        *)
          exec "$term" -e bash "$0" "$@"
          ;;
      esac
    fi
  done
fi

ROOT="$(cd "$(dirname "$0")" && pwd)"
LOG_DIR="$ROOT/state"
VENV_PY="$ROOT/venv/bin/python"
ENV_LOADED=0
set -a
if [ -f "$ROOT/granja.env" ]; then
  source "$ROOT/granja.env"
  ENV_LOADED=1
fi
if [ -f "$ROOT/.env" ]; then
  source "$ROOT/.env"
  ENV_LOADED=1
fi
set +a

if [ "$ENV_LOADED" -eq 0 ]; then
  echo "[ERROR] No existe .env ni granja.env"
  exit 1
fi

: "${PROXY_PORT:=8080}"
mkdir -p "$LOG_DIR"

if [ -x "$VENV_PY" ]; then
  PYTHON_BIN="$VENV_PY"
else
  PYTHON_BIN="$(command -v python3)"
fi

if [ -z "${PYTHON_BIN:-}" ] || [ ! -x "$PYTHON_BIN" ]; then
  echo "[ERROR] No encuentro python3 ni el venv de la granja"
  exit 1
fi

cd "$ROOT"

if pgrep -f "proxy.servidor" >/dev/null 2>&1; then
  echo "[OK] Proxy ya estaba corriendo"
else
  echo "[1/1] Iniciando Proxy FastAPI..."
  PYTHONPATH="$ROOT" nohup "$PYTHON_BIN" -m proxy.servidor > "$LOG_DIR/proxy.log" 2>&1 &
  sleep 2
fi

URL_DEMO="http://127.0.0.1:$PROXY_PORT/demo"
URL_API="http://127.0.0.1:$PROXY_PORT/api/demo/chat"

if command -v xdg-open >/dev/null 2>&1; then
  xdg-open "$URL_DEMO" >/dev/null 2>&1 || true
elif command -v sensible-browser >/dev/null 2>&1; then
  sensible-browser "$URL_DEMO" >/dev/null 2>&1 || true
fi

echo ""
echo "Demo lista en: $URL_DEMO"
echo "API demo:      $URL_API"
echo "Log:           $LOG_DIR/proxy.log"
