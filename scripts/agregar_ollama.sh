#!/bin/bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"

if [ $# -gt 0 ]; then
  python3 "$ROOT/scripts/ollama_account_sync.py" "$@"
  exit 0
fi

# Intentar copiar al portapapeles si hay herramienta instalada
copy_to_clipboard() {
  local text="$1"
  if command -v wl-copy >/dev/null 2>&1; then
    echo -n "$text" | wl-copy 2>/dev/null || true
  elif command -v xclip >/dev/null 2>&1; then
    echo -n "$text" | xclip -selection clipboard 2>/dev/null || true
  elif command -v xsel >/dev/null 2>&1; then
    echo -n "$text" | xsel --clipboard 2>/dev/null || true
  fi
}

# Abrir el navegador en EXACTAMENTE 1 SOLA ventana respetando la opción del usuario
open_browser_mode() {
  local url="$1"
  local mode="$2" # "normal", "private", "none"

  if [ "$mode" = "none" ] || ([ -z "${DISPLAY:-}" ] && [ -z "${WAYLAND_DISPLAY:-}" ]); then
    return 0
  fi

  if [ "$mode" = "private" ]; then
    for b in firefox opera google-chrome chromium brave vivaldi; do
      if command -v "$b" >/dev/null 2>&1; then
        case "$b" in
          firefox|opera|vivaldi)
            "$b" --private-window "$url" >/dev/null 2>&1 & disown
            return 0
            ;;
          google-chrome|chromium|brave)
            "$b" --incognito "$url" >/dev/null 2>&1 & disown
            return 0
            ;;
        esac
      fi
    done
  fi

  # Modo Normal (Perfil habitual con gestor de contraseñas)
  if command -v python3 >/dev/null 2>&1; then
    python3 -m webbrowser "$url" >/dev/null 2>&1 || true
  elif command -v xdg-open >/dev/null 2>&1; then
    xdg-open "$url" >/dev/null 2>&1 || true
  fi
}

cat <<'EOF'

═══════════════════════════════════════════════════════════════════════════
  🌾 LA GRANJA DE IA — Asistente de Cuentas Ollama Cloud
═══════════════════════════════════════════════════════════════════════════
  Este asistente te guiará para vincular tus cuentas de Ollama Cloud.
  No necesitás copiar ni pegar claves manualmente.
  El sistema generará el enlace directo de vinculación.
═══════════════════════════════════════════════════════════════════════════
EOF

while true; do
  NEXT_INFO=$(python3 - "$ROOT/cuentas.json" <<'PY'
import json, sys, re
from pathlib import Path

cuentas_file = Path(sys.argv[1])
cuentas = []
if cuentas_file.exists():
    try:
        data = json.loads(cuentas_file.read_text(encoding='utf-8'))
        cuentas = data.get('proveedores', {}).get('ollama', {}).get('cuentas', [])
    except Exception:
        pass

max_num = 0
max_port = 11433

for c in cuentas:
    cid = str(c.get('id', ''))
    m = re.search(r'\d+', cid)
    if m:
        num = int(m.group())
        if num > max_num:
            max_num = num
    port = c.get('puerto')
    if isinstance(port, int) and port > max_port:
        max_port = port

next_num = max_num + 1
next_id = f"acc{next_num}"
next_port = max_port + 1 if max_port >= 11434 else 11434
print(f"{next_id}:{next_port}")
PY
  )

  SUGGESTED_ID=$(echo "$NEXT_INFO" | cut -d':' -f1)
  SUGGESTED_PORT=$(echo "$NEXT_INFO" | cut -d':' -f2)
  INST_HOME="$ROOT/ollama_instances/$SUGGESTED_ID"

  echo ""
  read -rp "📧 Ingresá el Email de tu cuenta Ollama Cloud: " EMAIL
  if [ -z "${EMAIL:-}" ]; then
    echo "[WARN] El Email es requerido para identificar la cuenta."
    continue
  fi

  # Preguntar preferencia de navegador
  echo ""
  echo "  🌐 ¿Cómo querés abrir el navegador para autorizar la cuenta?"
  echo "    [ ENTER ] -> Navegador Normal (Perfil habitual con gestor de contraseñas)"
  echo "    [   1   ] -> Navegador en Modo Incógnito / Privado (por seguridad)"
  echo "    [   2   ] -> No abrir navegador automáticamente (copiaré la URL manualmente)"
  echo ""
  read -rp "  Elegí el modo de navegador [ENTER]: " MODO_NAV
  MODO_NAV=${MODO_NAV:-0}

  BROWSER_MODE="normal"
  case "$MODO_NAV" in
    1) BROWSER_MODE="private" ;;
    2) BROWSER_MODE="none" ;;
    *) BROWSER_MODE="normal" ;;
  esac

  # Crear estructura de carpetas
  mkdir -p "$INST_HOME/.ollama" "$INST_HOME/logs"

  # Generar clave SSH aislada si no existe
  KEY_PATH="$INST_HOME/.ollama/id_ed25519"
  if [ ! -f "$KEY_PATH" ]; then
    ssh-keygen -t ed25519 -N "" -f "$KEY_PATH" -C "$EMAIL" >/dev/null 2>&1
  fi

  # Registrar en la configuración del proxy
  python3 "$ROOT/scripts/ollama_account_sync.py" --id "$SUGGESTED_ID" --puerto "$SUGGESTED_PORT" --home "$INST_HOME" --email "$EMAIL"

  # Iniciar servidor Ollama local para esta instancia si no está activo
  if ! ss -ltn "sport = :$SUGGESTED_PORT" 2>/dev/null | grep -q ":$SUGGESTED_PORT"; then
    HOME="$INST_HOME" \
    OLLAMA_HOST="127.0.0.1:$SUGGESTED_PORT" \
    OLLAMA_CONTEXT_LENGTH="131072" \
    OLLAMA_KEEP_ALIVE="-1" \
    nohup ollama serve </dev/null > "$INST_HOME/logs/ollama.log" 2>&1 & disown
    sleep 1.5
  fi

  # Construir el URL de vinculación directamente sin invocar la herramienta externa de Ollama
  CONNECT_URL=$(python3 - "${KEY_PATH}.pub" <<'PY'
import sys, base64, socket, re
from pathlib import Path

pub_file = Path(sys.argv[1])
if pub_file.exists():
    pub_text = pub_file.read_text(encoding='utf-8').strip()
    parts = pub_text.split()
    if len(parts) >= 2:
        raw_key = f"{parts[0]} {parts[1]}"
        b64_key = base64.b64encode(raw_key.encode('utf-8')).decode('utf-8').rstrip('=')
        host = socket.gethostname()
        print(f"https://ollama.com/connect?name={host}&key={b64_key}")
        sys.exit(0)

print("https://ollama.com/settings/keys")
PY
  )

  PUB_KEY=""
  if [ -f "${KEY_PATH}.pub" ]; then
    PUB_KEY=$(cat "${KEY_PATH}.pub")
  fi

  copy_to_clipboard "$PUB_KEY"
  open_browser_mode "$CONNECT_URL" "$BROWSER_MODE"

  echo ""
  echo "═══════════════════════════════════════════════════════════════════════════"
  echo "  ✅ INSTANCIA ASIGNADA: $SUGGESTED_ID (Puerto local: $SUGGESTED_PORT)"
  echo "  📧 Cuenta esperada: $EMAIL"
  echo "═══════════════════════════════════════════════════════════════════════════"
  echo ""
  echo "  📌 VINCULACIÓN EN 1 SOLO CLIC:"
  echo ""
  echo "  1. Abrí esta URL oficial de vinculación:"
  echo "     👉 $CONNECT_URL"
  if [ "$BROWSER_MODE" != "none" ] && ([ -n "${DISPLAY:-}" ] || [ -n "${WAYLAND_DISPLAY:-}" ]); then
    echo "     (Se abrió 1 ventana automáticamente en tu navegador [$BROWSER_MODE])"
  fi
  echo ""
  echo "  2. En la web, asegurate de estar logueado con $EMAIL"
  echo "     y tocá el botón \"Authorize Device\" (Autorizar Dispositivo)."
  echo "═══════════════════════════════════════════════════════════════════════════"

  # Bucle interactivo de verificación
  while true; do
    echo ""
    echo "  Opciones disponibles:"
    echo "    [ ENTER ]  -> Verificar vinculación con Ollama Cloud ahora"
    echo "    [   1   ]  -> Re-abrir solo en Navegador Normal (perfil con contraseñas)"
    echo "    [   2   ]  -> Re-abrir solo en Modo Incógnito / Privado"
    echo "    [   3   ]  -> Guardar y continuar (verificar más tarde)"
    echo ""
    read -rp "  Elegí una opción [ENTER]: " ACCION
    ACCION=${ACCION:-verificar}

    case "$ACCION" in
      1)
        open_browser_mode "$CONNECT_URL" "normal"
        echo "  [INFO] Re-abriendo en Navegador Normal..."
        continue
        ;;
      2)
        open_browser_mode "$CONNECT_URL" "private"
        echo "  [INFO] Re-abriendo en Modo Incógnito / Privado..."
        continue
        ;;
      3)
        echo "  [INFO] Cuenta guardada. Se verificará automáticamente al iniciar la granja."
        break
        ;;
      *)
        echo ""
        echo "  ⏳ Verificando autorización en puerto $SUGGESTED_PORT..."
        CHECK_RES=$(python3 - "$SUGGESTED_PORT" "$EMAIL" <<'PY'
import sys, urllib.request, json

port = sys.argv[1]
expected_email = sys.argv[2].strip().lower()

url = f"http://127.0.0.1:{port}/api/me"
req = urllib.request.Request(url, headers={"Content-Type": "application/json"}, method="POST")
try:
    with urllib.request.urlopen(req, timeout=12) as resp:
        if resp.status == 200:
            data = json.loads(resp.read().decode('utf-8'))
            actual_email = data.get("email", "").strip().lower()
            if actual_email and actual_email != expected_email:
                print(f"MISMATCH:{actual_email}")
            else:
                print("OK")
            sys.exit(0)
except urllib.error.HTTPError as e:
    if e.code != 401:
        print("OK")
        sys.exit(0)
    else:
        print(f"HTTP {e.code}")
        sys.exit(0)
except Exception as e:
    print(f"ERR: {e}")
PY
        )

        if [ "$CHECK_RES" = "OK" ]; then
          echo ""
          echo "  🎉 ¡ÉXITO! La cuenta $EMAIL en la instancia $SUGGESTED_ID se vinculó y autorizó correctamente."
          break
        elif [[ "$CHECK_RES" == MISMATCH:* ]]; then
          ACTUAL_EMAIL="${CHECK_RES#MISMATCH:}"
          echo ""
          echo "  ⚠️  ¡ALERTA DE SEGURIDAD Y CUENTA!"
          echo "  ─────────────────────────────────────────────────────────────────────────"
          echo "  Ingresaste en la consola:  $EMAIL"
          echo "  Pero en la web autorizaste: $ACTUAL_EMAIL (sesión abierta en tu navegador)."
          echo "  ─────────────────────────────────────────────────────────────────────────"
          echo "  [INFO] Sincronizando la cuenta a $ACTUAL_EMAIL en la configuración..."
          python3 "$ROOT/scripts/ollama_account_sync.py" --id "$SUGGESTED_ID" --puerto "$SUGGESTED_PORT" --home "$INST_HOME" --email "$ACTUAL_EMAIL"
          echo ""
          echo "  🎉 ¡ÉXITO! Instancia $SUGGESTED_ID guardada y vinculada a la cuenta real: $ACTUAL_EMAIL"
          break
        else
          echo ""
          echo "  ⚠️ Todavía no pudimos verificar la autorización (Respuesta: $CHECK_RES)."
          echo "     Asegurate de haber tocado el botón 'Authorize Device' en $CONNECT_URL"
          continue
        fi
        ;;
    esac
  done

  echo ""
  read -rp "¿Querés agregar otra cuenta de Ollama Cloud? [s/N]: " ANOTHER
  case "$ANOTHER" in
    [sS]|[sS][íÍ]|[yY][eE][sS])
      continue
      ;;
    *)
      break
      ;;
  esac
done
