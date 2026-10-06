#!/bin/bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
VENV_PY="$ROOT/venv/bin/python"

if [ -x "$VENV_PY" ]; then
  PYTHON_BIN="$VENV_PY"
else
  PYTHON_BIN="$(command -v python3 || command -v python)"
fi

if [ -z "${PYTHON_BIN:-}" ] || [ ! -x "$PYTHON_BIN" ]; then
  echo "[ERROR] No se encontró Python en el sistema."
  exit 1
fi

"$PYTHON_BIN" "$ROOT/scripts/detener_granja.py"
