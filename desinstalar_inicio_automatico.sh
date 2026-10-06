#!/usr/bin/env bash
# ==============================================================================
#  desinstalar_inicio_automatico.sh — Desactivar Inicio Automático en Linux
# ==============================================================================
set -euo pipefail

AUTOSTART_DIR="$HOME/.config/autostart"
DESKTOP_FILE="$AUTOSTART_DIR/nucleo_ia.desktop"

echo "==================================================="
echo "  DESACTIVAR INICIO AUTOMÁTICO — Núcleo IA (Linux)"
echo "==================================================="
echo ""

if [ -f "$DESKTOP_FILE" ]; then
    rm -f "$DESKTOP_FILE"
    echo "  [OK] Eliminada entrada de inicio automático: $DESKTOP_FILE"
else
    echo "  [INFO] No había ninguna entrada de inicio automático activa."
fi

echo ""
echo "==================================================="
echo "  [OK] Inicio automático desactivado con éxito."
echo "==================================================="
echo ""
