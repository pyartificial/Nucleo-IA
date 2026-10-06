#!/bin/bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
read -rp "ID de cuenta Cohere [cohere_1]: " ACCOUNT_ID
ACCOUNT_ID=${ACCOUNT_ID:-cohere_1}
read -rsp "API key Cohere / Command ($ACCOUNT_ID): " API_KEY
printf '\n'
[ -z "${API_KEY:-}" ] && { echo "[ERROR] Falta la API key"; exit 1; }
python3 "$ROOT/scripts/gestor_cuentas.py" cohere "$ACCOUNT_ID" "$API_KEY"
echo "✅ Guardado Cohere: $ACCOUNT_ID"
