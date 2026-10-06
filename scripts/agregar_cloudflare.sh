#!/bin/bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
read -rp "Cloudflare account_id [account]: " ACCOUNT_ID
ACCOUNT_ID=${ACCOUNT_ID:-account}
read -rsp "API token Cloudflare ($ACCOUNT_ID): " API_KEY
printf '\n'
[ -z "${API_KEY:-}" ] && { echo "[ERROR] Falta el token"; exit 1; }
python3 "$ROOT/scripts/gestor_cuentas.py" cloudflare "$ACCOUNT_ID" "$API_KEY"
echo "✅ Guardado Cloudflare: $ACCOUNT_ID"
