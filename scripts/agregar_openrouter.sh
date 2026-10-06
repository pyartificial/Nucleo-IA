#!/bin/bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
read -rp "ID de cuenta OpenRouter [openrouter_1]: " ACCOUNT_ID
ACCOUNT_ID=${ACCOUNT_ID:-openrouter_1}
read -rsp "API key OpenRouter ($ACCOUNT_ID): " API_KEY
printf '\n'
[ -z "${API_KEY:-}" ] && { echo "[ERROR] Falta la API key"; exit 1; }
read -rp "URL app (opcional): " URL_APP
python3 "$ROOT/scripts/gestor_cuentas.py" openrouter "$ACCOUNT_ID" "$API_KEY" "$URL_APP"
echo "✅ Guardado OpenRouter: $ACCOUNT_ID"
