#!/bin/bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"

ACC_ID="${1:-xkiro_1}"
echo "ID de cuenta xKiro [$ACC_ID]: "
read -r USER_ID
if [ -n "$USER_ID" ]; then
    ACC_ID="$USER_ID"
fi

echo "API key xKiro (sk-xt-...): "
read -rs API_KEY
echo
if [[ "$API_KEY" != sk-xt-* ]]; then
    echo "[ERROR] La API key de xKiro debe comenzar con sk-xt-"
    exit 1
fi

if [ -x "$ROOT/venv/bin/python" ]; then
    "$ROOT/venv/bin/python" "$ROOT/scripts/gestor_cuentas.py" xkiro "$ACC_ID" "$API_KEY"
else
    python3 "$ROOT/scripts/gestor_cuentas.py" xkiro "$ACC_ID" "$API_KEY"
fi

echo "[OK] Guardado xKiro: $ACC_ID"
