#!/bin/bash
# ============================================
# Núcleo IA — Iniciar instancias Ollama
# ============================================
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
if [ -f "$ROOT/granja.env" ]; then
  source "$ROOT/granja.env"
fi
if [ -f "$ROOT/.env" ]; then
  source "$ROOT/.env"
fi

CUENTAS_JSON="$ROOT/cuentas.json"
if [ ! -f "$CUENTAS_JSON" ]; then
  echo "[ERROR] Falta cuentas.json"
  exit 1
fi

# La configuración real vive en cuentas.json. INSTANCIAS/PUERTO_BASE quedan
# como compatibilidad para instalaciones antiguas, pero no deben cambiar la
# relación entre cuenta, correo, carpeta y puerto.
mapfile -t CUENTAS_OLLAMA < <(python3 - "$CUENTAS_JSON" <<'PY'
import json, sys
from pathlib import Path

try:
    data = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
except Exception as exc:
    print(f"ERROR|{exc}")
    raise SystemExit(0)

for cuenta in data.get("proveedores", {}).get("ollama", {}).get("cuentas", []):
    cid = str(cuenta.get("id", "")).strip()
    port = cuenta.get("puerto")
    home = str(cuenta.get("ollama_home", "")).strip()
    email = str(cuenta.get("email", "")).strip()
    if cid and isinstance(port, int) and home:
        print("|".join((cid, str(port), home, email)))
PY
)

if [ "${#CUENTAS_OLLAMA[@]}" -eq 0 ]; then
  echo "[ERROR] No hay cuentas Ollama con id, puerto y ollama_home válidos"
  exit 1
fi

echo "═══════════════════════════════════════"
echo "  INICIANDO LA GRANJA DE IA"
echo "  Instancias: ${#CUENTAS_OLLAMA[@]}"
echo "═══════════════════════════════════════"

echo "[1] Revisando instancias existentes..."

for registro in "${CUENTAS_OLLAMA[@]}"; do
    IFS='|' read -r cid port rel_home email <<< "$registro"
    if [[ "$rel_home" = /* ]]; then
      inst_dir="$rel_home"
    else
      inst_dir="$ROOT/$rel_home"
    fi
    mkdir -p "$inst_dir/logs"

    if ss -ltn "sport = :$port" 2>/dev/null | grep -q ":$port"; then
        echo "  ⏭ $cid | ${email:-correo no registrado} → :$port ya está activa"
        continue
    fi

    HOME="$inst_dir" \
    OLLAMA_HOST="127.0.0.1:$port" \
    OLLAMA_CONTEXT_LENGTH="${CONTEXT_LENGTH:-131072}" \
    OLLAMA_KEEP_ALIVE="-1" \
    nohup ollama serve </dev/null > "$inst_dir/logs/ollama.log" 2>&1 & disown

    echo "  ✅ $cid | ${email:-correo no registrado} → :$port  (pid=$!)"
    sleep 0.5
done

echo ""
echo "🌾 Granja iniciada. ${#CUENTAS_OLLAMA[@]} instancias activas."
echo "   Usa /status para consultar la cuenta asociada a cada puerto."
