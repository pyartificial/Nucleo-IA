#!/bin/bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"

ACC_ID="${1:-zhipu_1}"
echo "ID de cuenta Zhipu AI [$ACC_ID]: "
read -r USER_ID
if [ -n "$USER_ID" ]; then
    ACC_ID="$USER_ID"
fi

echo "API key Zhipu AI: "
read -rs API_KEY
if [ -z "$API_KEY" ]; then
    echo "[ERROR] Falta la API key"
    exit 1
fi

if [ -f "$ROOT/venv/bin/python" ]; then
    "$ROOT/venv/bin/python" "$ROOT/scripts/gestor_cuentas.py" zhipu "$ACC_ID" "$API_KEY"
else
    python3 "$ROOT/scripts/gestor_cuentas.py" zhipu "$ACC_ID" "$API_KEY"
fi

echo "[OK] Guardado Zhipu AI: $ACC_ID"
