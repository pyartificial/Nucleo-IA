#!/bin/bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ENV_FILE=""
for candidato in "$ROOT/.env" "$ROOT/granja.env"; do
  if [ -f "$candidato" ]; then
    ENV_FILE="$candidato"
    break
  fi
done

if [ -z "$ENV_FILE" ]; then
  echo "[ERROR] No existe .env ni granja.env"
  exit 1
fi

source "$ENV_FILE"
CUENTAS_JSON="$ROOT/cuentas.json"
MODEL="${1:-$ACTIVE_MODEL}"
echo "🏥 Healthcheck — $MODEL"

while IFS='|' read -r cid port email; do
    [ -z "$cid" ] && continue
    payload="{\"model\":\"$MODEL\",\"messages\":[{\"role\":\"user\",\"content\":\"ping\"}],\"max_tokens\":1,\"stream\":false}"
    code=$(curl -sS -o /dev/null -w "%{http_code}" -m "$CURL_TIMEOUT" \
        -H "Content-Type: application/json" -d "$payload" \
        "http://127.0.0.1:$port/v1/chat/completions" 2>/dev/null || echo "000")

    case "$code" in
        200) echo "  ✅ $cid | ${email:-correo no registrado} (:$port) → OK" ;;
        429) echo "  🔴 $cid | ${email:-correo no registrado} (:$port) → CUOTA AGOTADA" ;;
        403) echo "  🔴 $cid | ${email:-correo no registrado} (:$port) → SUSCRIPCIÓN" ;;
        *)   echo "  ⚠️  $cid | ${email:-correo no registrado} (:$port) → HTTP $code" ;;
    esac
done < <(python3 - "$CUENTAS_JSON" <<'PY'
import json, sys
from pathlib import Path
try:
    data = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
except Exception:
    raise SystemExit(0)
for c in data.get("proveedores", {}).get("ollama", {}).get("cuentas", []):
    if c.get("id") and isinstance(c.get("puerto"), int):
        print(f"{c['id']}|{c['puerto']}|{c.get('email', '')}")
PY
)
