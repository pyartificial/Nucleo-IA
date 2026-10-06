#!/bin/bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
read -rp "ID de cuenta Google [google_1]: " ACCOUNT_ID
ACCOUNT_ID=${ACCOUNT_ID:-google_1}
read -rsp "API key Google/Gemini ($ACCOUNT_ID): " API_KEY
printf '\n'
[ -z "${API_KEY:-}" ] && { echo "[ERROR] Falta la API key"; exit 1; }
python3 "$ROOT/scripts/gestor_cuentas.py" google "$ACCOUNT_ID" "$API_KEY"
echo "✅ Guardado Google: $ACCOUNT_ID"
