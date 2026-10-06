#!/bin/bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"

ACC_ID="${1:-groq_1}"
echo "ID de cuenta Groq [$ACC_ID]: "
read -r USER_ID
if [ -n "$USER_ID" ]; then
    ACC_ID="$USER_ID"
fi

echo "API key Groq (gsk_...): "
read -rs API_KEY
if [ -z "$API_KEY" ]; then
    echo "[ERROR] Falta la API key"
    exit 1
fi

if [ -f "$ROOT/venv/bin/python" ]; then
    "$ROOT/venv/bin/python" "$ROOT/scripts/gestor_cuentas.py" groq "$ACC_ID" "$API_KEY"
else
    python3 "$ROOT/scripts/gestor_cuentas.py" groq "$ACC_ID" "$API_KEY"
fi

echo "[OK] Guardado Groq: $ACC_ID"
