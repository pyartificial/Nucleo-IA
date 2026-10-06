#!/usr/bin/env bash
# ==============================================================================
#  instalar_inicio_automatico.sh — Configurar Inicio Automático en Linux
#  Crea una entrada en ~/.config/autostart para iniciar el proxy al iniciar sesión.
# ==============================================================================
set -euo pipefail

DIR_RAIZ="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AUTOSTART_DIR="$HOME/.config/autostart"
DESKTOP_FILE="$AUTOSTART_DIR/nucleo_ia.desktop"

echo "==================================================="
echo "  CONFIGURAR INICIO AUTOMÁTICO — Núcleo IA (Linux)"
echo "==================================================="
echo ""

mkdir -p "$AUTOSTART_DIR"

cat > "$DESKTOP_FILE" << EOF2
[Desktop Entry]
Type=Application
Name=Núcleo IA
Comment=Servidor Proxy Multi-Proveedor Unificado para Modelos de IA
Exec=bash "$DIR_RAIZ/iniciar_todo.sh"
Path=$DIR_RAIZ
Terminal=false
Hidden=false
X-GNOME-Autostart-enabled=true
Categories=Utility;Development;
EOF2

chmod +x "$DESKTOP_FILE"

echo "  [OK] Creado archivo de inicio automático en:"
echo "       $DESKTOP_FILE"
echo ""
echo "==================================================="
echo "  🎉 Núcleo IA se iniciará automáticamente en"
echo "     segundo plano cada vez que inicies sesión."
echo "==================================================="
echo ""
