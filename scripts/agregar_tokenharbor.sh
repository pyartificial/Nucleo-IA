#!/usr/bin/env bash
set -euo pipefail
ROOT="$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
ACC_ID="${1:-tokenharbor_1}"
echo "Agregar cuenta Token Harbor ($ACC_ID)"
echo "Aviso: las rutas :free pueden retener prompts y respuestas según su política."
read -rsp "API key Token Harbor (thk_...): " API_KEY
echo
if [[ "$API_KEY" != thk_* ]]; then
    echo "[ERROR] La clave debe comenzar con thk_"
    exit 1
fi
PYTHON_BIN="$ROOT/venv/bin/python"
[[ -x "$PYTHON_BIN" ]] || PYTHON_BIN=python3
"$PYTHON_BIN" "$ROOT/scripts/gestor_cuentas.py" tokenharbor "$ACC_ID" "$API_KEY"
echo "[OK] Token Harbor guardado. Ejecutá actualizar_rankings para probar las rutas :free."
