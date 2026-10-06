#!/bin/bash
# ============================================
# Núcleo IA — Instalador de Dependencias
# Detecta Debian/Arch automáticamente
# ============================================
set -euo pipefail

detectar_distro() {
    if [ -f /etc/os-release ]; then
        . /etc/os-release
        echo "$ID"
    elif command -v pacman &>/dev/null; then
        echo "arch"
    elif command -v apt &>/dev/null; then
        echo "debian"
    else
        echo "desconocida"
    fi
}

DISTRO=$(detectar_distro)
echo "═══════════════════════════════════════"
echo "  LA GRANJA DE IA — Instalador"
echo "  Distro detectada: $DISTRO"
echo "═══════════════════════════════════════"

case "$DISTRO" in
    debian|ubuntu|linuxmint)
        echo "[1/4] Actualizando paquetes (apt)..."
        sudo apt update
        sudo apt install -y curl python3 python3-pip python3-venv python3-fastapi python3-httpx uvicorn jq

        echo "[2/4] Instalando Ollama..."
        if ! command -v ollama &>/dev/null; then
            curl -fsSL https://ollama.com/install.sh | sh
        else
            echo "  Ollama ya instalado: $(ollama --version)"
        fi

        echo "[3/4] Creando entorno virtual Python..."
        VENV_DIR="$(cd "$(dirname "$0")/.." && pwd)/venv"
        python3 -m venv "$VENV_DIR"
        source "$VENV_DIR/bin/activate"

        echo "[4/4] Instalando dependencias Python..."
        pip install --upgrade pip
        pip install -r "$(cd "$(dirname "$0")/.." && pwd)/requirements.txt"
        ;;

    arch|manjaro|endeavouros)
        echo "[1/4] Actualizando paquetes (pacman)..."
        sudo pacman -Syu --noconfirm
        sudo pacman -S --noconfirm --needed curl python python-pip python-fastapi python-httpx uvicorn jq

        echo "[2/4] Instalando Ollama..."
        if ! command -v ollama &>/dev/null; then
            if command -v yay &>/dev/null; then
                yay -S --noconfirm ollama
            else
                echo "  yay no encontrado, usando script oficial..."
                curl -fsSL https://ollama.com/install.sh | sh
            fi
        else
            echo "  Ollama ya instalado: $(ollama --version)"
        fi

        echo "[3/4] Creando entorno virtual Python..."
        VENV_DIR="$(cd "$(dirname "$0")/.." && pwd)/venv"
        python -m venv "$VENV_DIR"
        source "$VENV_DIR/bin/activate"

        echo "[4/4] Instalando dependencias Python..."
        pip install --upgrade pip
        pip install -r "$(cd "$(dirname "$0")/.." && pwd)/requirements.txt"
        ;;

    *)
        echo "[!] Distro '$DISTRO' no soportada."
        echo "    Instalar manualmente: curl, python3, pip, jq, ollama"
        echo "    Luego: pip install -r requirements.txt"
        exit 1
        ;;
esac

echo ""
echo "✅ Instalación completada."
echo "   Entorno virtual: $VENV_DIR"
echo "   Activar con: source $VENV_DIR/bin/activate"
