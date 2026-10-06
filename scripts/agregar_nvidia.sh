#!/bin/bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
read -rp "ID de cuenta NVIDIA [nvidia_1]: " ACCOUNT_ID
ACCOUNT_ID=${ACCOUNT_ID:-nvidia_1}
read -rsp "API key NVIDIA ($ACCOUNT_ID): " API_KEY
printf '\n'
[ -z "${API_KEY:-}" ] && { echo "[ERROR] Falta la API key"; exit 1; }
python3 "$ROOT/scripts/gestor_cuentas.py" nvidia "$ACCOUNT_ID" "$API_KEY"
echo "✅ Guardado NVIDIA: $ACCOUNT_ID"
