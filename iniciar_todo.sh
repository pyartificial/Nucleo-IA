#!/bin/bash
set -euo pipefail

# Auto-detectar si se ejecutó por doble clic desde el entorno gráfico (sin terminal TTY)
if ([ -n "${DISPLAY:-}" ] || [ -n "${WAYLAND_DISPLAY:-}" ]) && [ ! -t 0 ] && [ ! -t 1 ] && [ -z "${IN_TERMINAL:-}" ]; then
  export IN_TERMINAL=1
  for term in konsole gnome-terminal xfce4-terminal x-terminal-emulator mate-terminal kitty alacritty xterm; do
    if command -v "$term" >/dev/null 2>&1; then
      case "$term" in
        konsole)
          exec "$term" --noclose -e bash -c 'bash "$0" "$@"' "$0" "$@"
          ;;
        gnome-terminal|mate-terminal)
          exec "$term" -- bash -c 'bash "$0" "$@"' "$0" "$@"
          ;;
        *)
          exec "$term" -e bash -c 'bash "$0" "$@"' "$0" "$@"
          ;;
      esac
    fi
  done
fi

ROOT="$(cd "$(dirname "$0")" && pwd)"
LOG_DIR="$ROOT/state"
VENV_PY="$ROOT/venv/bin/python"
set -a
if [ -f "$ROOT/granja.env" ]; then
  source "$ROOT/granja.env"
fi
if [ -f "$ROOT/.env" ]; then
  source "$ROOT/.env"
fi
set +a

INSTANCIAS="${INSTANCIAS:-0}"
PROXY_HOST="${PROXY_HOST:-127.0.0.1}"
PROXY_PORT="${PROXY_PORT:-8080}"
mkdir -p "$LOG_DIR"

if [ -x "$VENV_PY" ]; then
  PYTHON_BIN="$VENV_PY"
else
  PYTHON_BIN="$(command -v python3 || command -v python)"
fi

if [ -z "${PYTHON_BIN:-}" ] || [ ! -x "$PYTHON_BIN" ]; then
  echo "[ERROR] No encuentro python3 ni el venv de Núcleo IA"
  exit 1
fi

echo "══════════════════════════════════════"
echo "  INICIADOR — Núcleo IA"
echo "══════════════════════════════════════"
echo ""
echo "Proyecto: $ROOT"
echo "Python: $PYTHON_BIN"
echo "Proxy: http://$PROXY_HOST:$PROXY_PORT"
echo ""

# Arranca las instancias Ollama si están configuradas
if [ "$INSTANCIAS" -gt 0 ] 2>/dev/null && [ -f "$ROOT/scripts/iniciar_granja.sh" ]; then
  echo "[1/2] Iniciando $INSTANCIAS instancias de Ollama..."
  bash "$ROOT/scripts/iniciar_granja.sh" || true
else
  echo "[1/2] Modo Proveedores Cloud / Proxy Central (sin instancias Ollama locales)..."
fi

# No cerrar procesos por nombre o puerto: podrían pertenecer a otra copia.
if ss -ltn "sport = :$PROXY_PORT" 2>/dev/null | grep -q ":$PROXY_PORT"; then
  echo "[ERROR] El puerto $PROXY_PORT ya está ocupado. Detené esta copia con detener_todo o elegí otro puerto."
  exit 1
fi

# Arranca el proxy central desacoplado de la terminal (nohup + disown + unbuffered)
echo "[2/2] Iniciando Proxy FastAPI..."
cd "$ROOT"
PYTHONUNBUFFERED=1 PYTHONPATH="$ROOT" setsid nohup "$PYTHON_BIN" -u -m proxy.servidor </dev/null >> "$LOG_DIR/proxy.log" 2>&1 &
PID_PROXY=$!
disown $PID_PROXY 2>/dev/null || true

# Esperar hasta 5 segundos para confirmar que el proxy responda
PROXY_LISTO=false
for i in {1..10}; do
  if curl -s "http://127.0.0.1:$PROXY_PORT/status" >/dev/null 2>&1; then
    PROXY_LISTO=true
    break
  fi
  sleep 0.5
done

if [ "$PROXY_LISTO" = "true" ]; then
  echo "  ✅ Proxy levantado exitosamente en http://$PROXY_HOST:$PROXY_PORT"
  echo "  📝 Log: $LOG_DIR/proxy.log"
  echo "  🧾 PID: $PID_PROXY"
else
  echo "  ❌ Error: El proxy no respondió a tiempo. Revisá el log en $LOG_DIR/proxy.log"
  exit 1
fi
echo ""
echo "Listo. Probá con:"
echo "  curl http://127.0.0.1:$PROXY_PORT/status"
echo "  curl http://127.0.0.1:$PROXY_PORT/rankings"
echo ""
