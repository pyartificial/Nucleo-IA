#!/usr/bin/env bash
set -euo pipefail
CENTRO_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
if [ -x "$CENTRO_DIR/venv/bin/python" ]; then
    exec "$CENTRO_DIR/venv/bin/python" "$CENTRO_DIR/scripts/mis_servicios.py" --serve --panel "$@"
elif command -v python3 >/dev/null 2>&1; then
    exec python3 "$CENTRO_DIR/scripts/mis_servicios.py" --serve --panel "$@"
else
    echo 'Falta Python 3. Ejecutá instalar_nucleo_ia.sh antes de abrir el Centro de control.' >&2
    exit 1
fi
