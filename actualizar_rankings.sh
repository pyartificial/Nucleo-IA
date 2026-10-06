#!/usr/bin/env bash
set -uo pipefail

if [[ ! -t 0 && -z "${IN_TERMINAL:-}" ]]; then
  export IN_TERMINAL=1
  for terminal in konsole gnome-terminal xfce4-terminal x-terminal-emulator mate-terminal kitty alacritty xterm; do
    if command -v "$terminal" >/dev/null 2>&1; then
      case "$terminal" in
        konsole|alacritty|kitty|xterm)
          exec "$terminal" -e bash -c 'script="$1"; shift; bash "$script" "$@"; rc=$?; echo; read -r -p "Presione Enter para cerrar..." _; exit "$rc"' _ "$0" "$@" ;;
        *)
          exec "$terminal" -- bash -c 'script="$1"; shift; bash "$script" "$@"; rc=$?; echo; read -r -p "Presione Enter para cerrar..." _; exit "$rc"' _ "$0" "$@" ;;
      esac
    fi
  done
fi

SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$SCRIPT_DIR"
PYTHON_BIN="${PYTHON_BIN:-python3}"
LOG_DIR="$(mktemp -d "${TMPDIR:-/tmp}/nucleo-rankings.XXXXXX")"
FAILED=0
trap 'rm -rf "$LOG_DIR"' EXIT
cd "$ROOT_DIR"

hora() { date '+%H:%M:%S'; }

resumen() {
  local etiqueta="$1" archivo="$2"
  [[ -f "$archivo" ]] || { echo "[$(hora)] Sin ranking: $archivo"; return; }
  "$PYTHON_BIN" - "$etiqueta" "$archivo" <<'PY'
import json, sys
etiqueta, ruta = sys.argv[1:]
try:
    d = json.load(open(ruta, encoding="utf-8"))
except Exception as e:
    print(f"  Resumen no disponible: {e}"); raise SystemExit
def n(*keys):
    for k in keys:
        if d.get(k) is not None: return d[k]
    return 0
final = d.get("ranking_final") or d.get("ranking_aptos") or d.get("ranking") or []
rech = d.get("ranking_rechazados_probe") or []
print(f"  Ranking final {etiqueta}: {len(final)} modelos")
print(f"  Descubiertos: {n('total_modelos')} | Respondieron: {n('total_modelos_respondieron','total_modelos_gratis')} | Aptos: {n('total_aptos_finales')} | Rechazados: {len(rech)}")
for i, x in enumerate(final[:5], 1):
    print(f"    #{i} {x.get('id') or x.get('modelo_id') or x.get('modelo') or '?'} [{x.get('probe_estado','ok')}]")
if rech:
    print("  Errores/rechazos:")
    for x in rech[:8]:
        mid = x.get('id') or x.get('modelo_id') or x.get('modelo') or '?'
        print(f"    - {mid}: {x.get('probe_estado') or x.get('error') or 'rechazado'} — {x.get('probe_preview','')}")
PY
}

ejecutar() {
  local etiqueta="$1" archivo="$2"; shift 2
  local log="$LOG_DIR/${etiqueta//[^A-Za-z0-9_-]/_}.log" inicio fin codigo
  inicio="$(date +%s)"
  echo; echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  echo "[$(hora)] INICIO: $etiqueta"; echo "[$(hora)] Comando: $*"
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  "$@" 2>&1 | tee "$log"
  codigo=${PIPESTATUS[0]}; fin="$(date +%s)"
  if [[ "$codigo" -eq 0 ]]; then
    echo "[$(hora)] OK: $etiqueta ($((fin-inicio))s)"
  else
    FAILED=$((FAILED + 1)); echo "[$(hora)] ERROR: $etiqueta código $codigo ($((fin-inicio))s)"
    echo "  Últimas líneas:"; tail -n 12 "$log" | sed 's/^/    /'
  fi
  resumen "$etiqueta" "$archivo"
}

echo "======================================================================"
echo "  ACTUALIZACIÓN COMPLETA DE RANKINGS — Núcleo IA"
echo "  Inicio: $(date '+%Y-%m-%d %H:%M:%S')"
echo "  Los errores se muestran y no detienen los demás proveedores."
echo "======================================================================"

ejecutar ollama_cloud state/ranking_ollama.json "$PYTHON_BIN" scripts/ollama_cloud_monitor.py --no-set-active-model --no-update-rankings
ejecutar nvidia state/ranking_nvidia.json "$PYTHON_BIN" scripts/ranking_nvidia.py
ejecutar openrouter state/ranking_openrouter.json "$PYTHON_BIN" scripts/ranking_openrouter.py
ejecutar cloudflare state/ranking_cloudflare.json "$PYTHON_BIN" scripts/ranking_cloudflare.py
ejecutar cohere state/ranking_cohere.json "$PYTHON_BIN" scripts/ranking_cohere.py
ejecutar google state/ranking_google.json "$PYTHON_BIN" scripts/ranking_google.py
ejecutar siliconflow state/ranking_siliconflow.json "$PYTHON_BIN" scripts/ranking_siliconflow.py
ejecutar zhipu_zai state/ranking_zhipu.json "$PYTHON_BIN" scripts/ranking_zhipu.py
ejecutar groq state/ranking_groq.json "$PYTHON_BIN" scripts/ranking_groq.py
ejecutar tokenrouter state/ranking_tokenrouter.json "$PYTHON_BIN" scripts/ranking_tokenrouter.py
ejecutar xkiro state/ranking_xkiro.json "$PYTHON_BIN" scripts/ranking_xkiro.py
ejecutar tokenharbor state/ranking_tokenharbor.json "$PYTHON_BIN" scripts/ranking_tokenharbor.py
ejecutar ollama_local state/ranking_ollama.json "$PYTHON_BIN" scripts/generar_ranking.py
ejecutar ranking_global state/ranking_global.json "$PYTHON_BIN" scripts/ranking_global.py

echo; echo "======================================================================"
echo "  FIN: $(date '+%Y-%m-%d %H:%M:%S')"
if [[ "$FAILED" -eq 0 ]]; then echo "  Resultado: todos los procesos terminaron correctamente."; else echo "  Resultado: $FAILED proceso(s) terminaron con error; el resto sí se ejecutó."; fi
echo "======================================================================"
RESULTADO=0; [[ "$FAILED" -eq 0 ]] || RESULTADO=1
if [[ -n "${IN_TERMINAL:-}" ]]; then echo; read -r -p "Presione Enter para cerrar esta ventana..." _; fi
exit "$RESULTADO"
