#!/bin/bash
set -euo pipefail

# Auto-detectar si se ejecutó por doble clic (sin terminal TTY) y abrir ventana de terminal
if [ ! -t 0 ] && [ -z "${IN_TERMINAL:-}" ]; then
  export IN_TERMINAL=1
  for term in konsole gnome-terminal xfce4-terminal x-terminal-emulator mate-terminal kitty alacritty xterm; do
    if command -v "$term" >/dev/null 2>&1; then
      case "$term" in
        konsole) exec "$term" -e bash -c "\"$0\" \"$@\"; echo ''; read -p 'Presione Enter para salir...'" ;;
        gnome-terminal|mate-terminal) exec "$term" -- bash -c "\"$0\" \"$@\"; echo ''; read -p 'Presione Enter para salir...'" ;;
        *) exec "$term" -e bash -c "\"$0\" \"$@\"; echo ''; read -p 'Presione Enter para salir...'" ;;
      esac
    fi
  done
fi

ROOT="$(cd "$(dirname "$0")" && pwd)"
ENV_FILE="$ROOT/.env"
LEGACY_ENV="$ROOT/granja.env"

if [ ! -f "$ENV_FILE" ] && [ -f "$LEGACY_ENV" ]; then
  cp "$LEGACY_ENV" "$ENV_FILE"
fi

if [ ! -f "$ENV_FILE" ]; then
  echo "[ERROR] No existe .env ni granja.env"
  exit 1
fi

set_var() {
  python3 - "$ENV_FILE" "$1" "$2" <<'PY'
from pathlib import Path
import sys
path = Path(sys.argv[1])
name = sys.argv[2]
value = sys.argv[3]
lines = path.read_text(encoding='utf-8').splitlines() if path.exists() else []
out = []
replaced = False
for line in lines:
    if line.lstrip().startswith(f'{name}='):
        out.append(f'{name}={value}')
        replaced = True
    else:
        out.append(line)
if not replaced:
    if out and out[-1].strip():
        out.append('')
    out.append(f'{name}={value}')
path.write_text('\n'.join(out) + '\n', encoding='utf-8')
PY
}

get_var() {
  python3 - "$ENV_FILE" "$1" <<'PY'
from pathlib import Path
import sys
path = Path(sys.argv[1])
name = sys.argv[2]
val = ''
if path.exists():
    for raw in path.read_text(encoding='utf-8').splitlines():
        line = raw.strip()
        if line.startswith(name + '='):
            val = line.split('=', 1)[1].strip()
            break
print(val)
PY
}

current_services="$(get_var SERVICIOS_ACTIVOS)"
current_top="$(get_var ROTACION_TOP_N)"
current_modo="$(get_var MODO_ROTACION)"

current_services=${current_services:-ollama,groq,tokenrouter,xkiro,tokenharbor,cloudflare,nvidia,openrouter,google,cohere,zhipu}
current_top=${current_top:-3}
current_modo=${current_modo:-modelos}

echo "════════════════════════════════════════════════════════"
echo "  CONFIGURACIÓN — Núcleo IA"
echo "════════════════════════════════════════════════════════"
echo "  Esta herramienta te permite configurar cómo funciona"
echo "  el balanceo y la rotación de tus cuentas de IA."
echo "════════════════════════════════════════════════════════"
echo ""
echo "Servicios activos actuales: ${current_services}"
echo "Top de rotación actual:     ${current_top}"
echo "Modo de rotación actual:    ${current_modo}"
echo ""
echo "¿Qué querés configurar?"
echo "  1) Servicios activos"
echo "     (Elegir qué proveedores de IA encender o apagar)"
echo "  2) Top de rotación (ROTACION_TOP_N)"
echo "     (Cuántos modelos distintos usar en la rotación)"
echo "  3) Modo de rotación (MODO_ROTACION)"
echo "     (La estrategia: por modelo, por proveedor, más rápido, etc.)"
echo "  4) Configuración completa (Paso a paso)"
echo "  5) Salir"
echo "════════════════════════════════════════════════════════"
read -rp "  Opción [4]: " choice
choice=${choice:-4}

if [[ "$choice" == "1" || "$choice" == "4" ]]; then
  echo ""
  echo "Servicios disponibles:"
  echo "  1) ollama  2) groq  3) tokenrouter  4) cloudflare  5) nvidia"
  echo "  6) openrouter  7) google  8) cohere  9) siliconflow  10) zhipu  11) xkiro  12) tokenharbor"
  echo "  Escribí números separados por coma, ej: 1,2,5,9"
  echo "  Enter = mantener: ${current_services}"
  read -rp "  Servicios [${current_services}]: " picked
  picked=${picked:-$current_services}
  selected=()
  IFS=',' read -ra parts <<< "$picked"
  for part in "${parts[@]}"; do
    case "$(echo "$part" | tr -d '[:space:]')" in
      1|ollama) selected+=(ollama) ;;
      2|groq) selected+=(groq) ;;
      3|tokenrouter) selected+=(tokenrouter) ;;
      4|cloudflare) selected+=(cloudflare) ;;
      5|nvidia) selected+=(nvidia) ;;
      6|openrouter) selected+=(openrouter) ;;
      7|google) selected+=(google) ;;
      8|cohere) selected+=(cohere) ;;
      9|siliconflow) selected+=(siliconflow) ;;
      10|zhipu) selected+=(zhipu) ;;
      11|xkiro) selected+=(xkiro) ;;
      12|tokenharbor) selected+=(tokenharbor) ;;
    esac
  done
  if [ ${#selected[@]} -eq 0 ]; then
    selected=(ollama groq tokenrouter xkiro tokenharbor cloudflare nvidia openrouter google cohere zhipu)
  fi
  services_joined=$(IFS=,; echo "${selected[*]}")
  set_var SERVICIOS_ACTIVOS "$services_joined"
  echo "  ✅ SERVICIOS_ACTIVOS=$services_joined"
fi

if [[ "$choice" == "2" || "$choice" == "4" ]]; then
  echo ""
  read -rp "Top de rotación (0 = todo el ranking) [${current_top}]: " top_n
  top_n=${top_n:-$current_top}
  if ! [[ "$top_n" =~ ^[0-9]+$ ]]; then
    echo "[WARN] Valor inválido, uso 3"
    top_n=3
  fi
  set_var ROTACION_TOP_N "$top_n"
  if [ "$top_n" -eq 0 ]; then
    echo "  ✅ ROTACION_TOP_N=0 (Usando TODO el ranking disponible)"
  else
    echo "  ✅ ROTACION_TOP_N=$top_n"
  fi
fi

if [[ "$choice" == "3" || "$choice" == "4" ]]; then
  echo ""
  echo "Elegí el MODO DE ROTACIÓN:"
  echo "  1) modelos        ➔ Round-Robin entre Top N modelos del Ranking (Default)"
  echo "  2) cuentas_primero➔ Agota todas las cuentas del Modelo #1 antes de pasar al #2"
  echo "  3) proveedores    ➔ Intercala 1 llamada a cada empresa (NVIDIA ➔ Ollama ➔ Google...)"
  echo "  4) velocidad      ➔ Elige el par (Modelo+Cuenta) con menor latencia en ms en vivo"
  echo "  5) cascada        ➔ Failover estricto: 100% al Puesto #1, solo conmuta si falla"
  read -rp "  Modo de rotación [1-5 o nombre] [${current_modo}]: " modo_in
  modo_in=${modo_in:-$current_modo}
  case "$modo_in" in
    1|modelos) modo_val="modelos" ;;
    2|cuentas_primero|cuentas) modo_val="cuentas_primero" ;;
    3|proveedores|proveedor) modo_val="proveedores" ;;
    4|velocidad|latencia) modo_val="velocidad" ;;
    5|cascada|failover) modo_val="cascada" ;;
    *) modo_val="$modo_in" ;;
  esac
  set_var MODO_ROTACION "$modo_val"
  echo "  ✅ MODO_ROTACION=$modo_val"
fi

cp "$ENV_FILE" "$LEGACY_ENV"
chmod 600 "$ENV_FILE" 2>/dev/null || true

echo ""
echo "Listo. Si querés revisar a mano:"
echo "  $ENV_FILE"
echo "  $LEGACY_ENV"
