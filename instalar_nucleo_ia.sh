#!/bin/bash
# ══════════════════════════════════════════════════════
# ⚡ NÚCLEO IA — Instalador Maestro
#
# Instala todo desde cero en un Linux limpio / WSL.
# Soporta: Ubuntu/Debian, Arch/Manjaro
#
# Uso:
#   bash instalar_nucleo_ia.sh
# ══════════════════════════════════════════════════════
set -euo pipefail

# Si se ejecuta desde el explorador de archivos, abrir una terminal persistente
# para que las preguntas del instalador sean visibles y no se cierre la ventana.
if [ ! -t 0 ] && [ -z "${NUCLEO_EN_TERMINAL:-}" ]; then
    export NUCLEO_EN_TERMINAL=1
    for term in gnome-terminal konsole xfce4-terminal mate-terminal xterm; do
        if command -v "$term" >/dev/null 2>&1; then
            case "$term" in
                gnome-terminal|mate-terminal) exec "$term" -- bash -c 'bash "$0"; echo; read -rp "Presiona Enter para cerrar..."' "$0" "$@" ;;
                konsole) exec "$term" --noclose -e bash -c 'bash "$0"; echo; read -rp "Presiona Enter para cerrar..."' "$0" "$@" ;;
                *) exec "$term" -e bash -c 'bash "$0"; echo; read -rp "Presiona Enter para cerrar..."' "$0" "$@" ;;
            esac
        fi
    done
    echo "Abrí una terminal y ejecutá: bash $0"
    exit 1
fi

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; BOLD='\033[1m'; NC='\033[0m'

info()  { echo -e "${CYAN}[INFO]${NC} $1"; }
ok()    { echo -e "${GREEN}[  OK]${NC} $1"; }
warn()  { echo -e "${YELLOW}[WARN]${NC} $1"; }
fail()  { echo -e "${RED}[FAIL]${NC} $1"; }

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
GRANJA_DIR="${GRANJA_DIR:-$SCRIPT_DIR}"
OLLAMA_BASE="$GRANJA_DIR/ollama_instances"
PUERTO_BASE=11434

echo ""
echo -e "${BOLD}══════════════════════════════════════════${NC}"
echo -e "${BOLD}  ⚡ NÚCLEO IA — Instalador Maestro${NC}"
echo -e "${BOLD}══════════════════════════════════════════${NC}"
echo ""

# ═══════════════════════════════════════
# PASO 1: Detectar distro
# ═══════════════════════════════════════
if [ -f /etc/os-release ]; then
    . /etc/os-release
    DISTRO="$ID"
else
    DISTRO="desconocida"
fi
info "Distro: $DISTRO"

# ═══════════════════════════════════════
# PASO 2: Dependencias del sistema
# ═══════════════════════════════════════
info "Verificando dependencias del sistema..."

FALTA=""
command -v curl    &>/dev/null || FALTA="$FALTA curl"
command -v jq      &>/dev/null || FALTA="$FALTA jq"
command -v python3 &>/dev/null || FALTA="$FALTA python3"

if [ -n "$FALTA" ]; then
    info "Faltan paquetes:$FALTA"

    if sudo -n true 2>/dev/null; then
        case "$DISTRO" in
            ubuntu|debian|linuxmint)
                sudo apt update -qq
                sudo apt install -y -qq $FALTA python3-pip python3-venv >/dev/null 2>&1
                ;;
            arch|manjaro|endeavouros)
                sudo pacman -Syu --noconfirm --quiet
                sudo pacman -S --noconfirm --needed $FALTA python python-pip python-fastapi python-httpx uvicorn >/dev/null 2>&1
                ;;
        esac
        ok "Paquetes instalados"
    else
        fail "No tengo permisos de sudo. Instalar manualmente:"
        case "$DISTRO" in
            ubuntu|debian|linuxmint)
                echo "  sudo apt install -y curl jq python3 python3-pip python3-venv python3-fastapi python3-httpx uvicorn"
                ;;
            arch|manjaro|endeavouros)
                echo "  sudo pacman -S curl jq python python-pip python-fastapi python-httpx uvicorn"
                ;;
            *)
                echo "  Instalar: curl jq python3 python3-pip python3-venv"
                ;;
        esac
        echo ""
        echo "Después volvé a ejecutar este script."
        exit 1
    fi
else
    ok "curl, jq, python3 ya instalados"
fi

# Verificar venv
if ! python3 -m venv --help >/dev/null 2>&1; then
    fail "python3-venv no disponible."
    case "$DISTRO" in
        ubuntu|debian*) echo "  sudo apt install python3-venv" ;;
        arch|manjaro*)  echo "  (incluido en python de pacman)" ;;
    esac
    exit 1
fi
ok "python3-venv disponible"

# ═══════════════════════════════════════
# PASO 3: Instalar Ollama (opcional)
# ═══════════════════════════════════════
if command -v ollama &>/dev/null; then
    ok "Ollama ya instalado"
else
    info "Instalando Ollama..."
    if sudo -n true 2>/dev/null; then
        curl -fsSL https://ollama.com/install.sh | sh
        ok "Ollama instalado"
    else
        warn "Ollama no instalado. Si usas proveedores cloud, puedes continuar."
    fi
fi

echo ""
echo -e "${BOLD}¿Qué servicios querés activar?${NC}"
echo "  1) Ollama       → modelos locales y Ollama Cloud"
echo "  2) Groq         → chat rápido y transcripciones"
echo "  3) TokenRouter  → agregador de modelos"
echo "  4) Cloudflare   → Workers AI"
echo "  5) NVIDIA       → NIM y modelos cloud"
echo "  6) OpenRouter   → modelos remotos/free"
echo "  7) Google       → Gemini, visión y razonamiento"
echo "  8) Cohere       → chat y reranking"
echo "  9) Zhipu        → generación de video"
echo " 10) xKiro        → gateway con cuota diaria gratuita"
echo " 11) Token Harbor → rutas :free con cuota renovable"
echo "     SiliconFlow  → implementado, pero desactivado por defecto"
echo "  Escribí números separados por coma (ej: 1,2,5,7)"
echo "  0 = todos"
read -rp "  Servicios [recomendados]: " SERVICIOS_PICK
SERVICIOS_PICK=${SERVICIOS_PICK:-1,2,3,4,5,6,7,8,9,10,11}
SERVICIOS_ACTIVOS=()
if [ "$(echo "$SERVICIOS_PICK" | tr -d '[:space:]')" = "0" ]; then
    SERVICIOS_ACTIVOS=(ollama groq tokenrouter xkiro tokenharbor cloudflare nvidia openrouter google cohere zhipu)
else
    IFS=',' read -ra _SERVICIOS_ITEMS <<< "$SERVICIOS_PICK"
    for item in "${_SERVICIOS_ITEMS[@]}"; do
        case "$(echo "$item" | tr -d '[:space:]')" in
            1|ollama) SERVICIOS_ACTIVOS+=(ollama) ;;
            2|groq) SERVICIOS_ACTIVOS+=(groq) ;;
            3|tokenrouter) SERVICIOS_ACTIVOS+=(tokenrouter) ;;
            4|cloudflare) SERVICIOS_ACTIVOS+=(cloudflare) ;;
            5|nvidia) SERVICIOS_ACTIVOS+=(nvidia) ;;
            6|openrouter) SERVICIOS_ACTIVOS+=(openrouter) ;;
            7|google) SERVICIOS_ACTIVOS+=(google) ;;
            8|cohere) SERVICIOS_ACTIVOS+=(cohere) ;;
            9|zhipu) SERVICIOS_ACTIVOS+=(zhipu) ;;
            10|xkiro) SERVICIOS_ACTIVOS+=(xkiro) ;;
            11|tokenharbor) SERVICIOS_ACTIVOS+=(tokenharbor) ;;
        esac
    done
    if [ ${#SERVICIOS_ACTIVOS[@]} -eq 0 ]; then
        SERVICIOS_ACTIVOS=(ollama groq tokenrouter xkiro tokenharbor cloudflare nvidia openrouter google cohere zhipu)
    fi
fi
SERVICIOS_ACTIVOS_JOINED=$(IFS=,; echo "${SERVICIOS_ACTIVOS[*]}")
ok "Servicios: $SERVICIOS_ACTIVOS_JOINED"

# ═══════════════════════════════════════
# PASO 4: Crear estructura
# ═══════════════════════════════════════
info "Creando estructura en $GRANJA_DIR..."
mkdir -p "$GRANJA_DIR"/{proxy,scripts,state}

# ═══════════════════════════════════════
# PASO 5: Entorno virtual Python
# ═══════════════════════════════════════
info "Creando entorno virtual Python..."
python3 -m venv "$GRANJA_DIR/venv"
source "$GRANJA_DIR/venv/bin/activate"
pip install --upgrade pip -q
pip install -r "$SCRIPT_DIR/requirements.txt" -q
ok "venv con dependencias listas"

# ═══════════════════════════════════════
# PASO 6: Copiar código fuente
# ═══════════════════════════════════════
if [ -d "$SCRIPT_DIR/proxy" ] && [ "$SCRIPT_DIR" != "$GRANJA_DIR" ]; then
    cp -r "$SCRIPT_DIR/proxy"/* "$GRANJA_DIR/proxy/"
    ok "Módulos de proxy copiados"
fi
if [ -d "$SCRIPT_DIR/scripts" ] && [ "$SCRIPT_DIR" != "$GRANJA_DIR" ]; then
    cp -r "$SCRIPT_DIR/scripts"/* "$GRANJA_DIR/scripts/"
    chmod +x "$GRANJA_DIR/scripts"/*.sh 2>/dev/null || true
    ok "Scripts copiados"
fi

if [ -f "$SCRIPT_DIR/.env.example" ] && [ ! -f "$GRANJA_DIR/.env" ]; then
    cp "$SCRIPT_DIR/.env.example" "$GRANJA_DIR/.env"
    ok ".env inicial creado"
fi

# Persistir la selección realizada en el asistente.
python3 - "$GRANJA_DIR/.env" "$SERVICIOS_ACTIVOS_JOINED" <<'PY'
from pathlib import Path
import sys
p=Path(sys.argv[1]); value=sys.argv[2]
lines=p.read_text(encoding='utf-8').splitlines() if p.exists() else []
out=[]; done=False
for line in lines:
    if line.startswith('SERVICIOS_ACTIVOS='):
        out.append('SERVICIOS_ACTIVOS='+value); done=True
    else: out.append(line)
if not done: out.append('SERVICIOS_ACTIVOS='+value)
p.write_text('\n'.join(out)+'\n',encoding='utf-8')
PY
ok "Servicios guardados en .env"

for archivo in granja.py requirements.txt iniciar_todo.sh actualizar_rankings.sh probar_demo.sh configura_nucleoia.sh agregar_cuentas.sh mis_servicios.sh centro_control.sh; do
    if [ -f "$SCRIPT_DIR/$archivo" ] && [ "$SCRIPT_DIR" != "$GRANJA_DIR" ]; then
        cp "$SCRIPT_DIR/$archivo" "$GRANJA_DIR/$archivo"
    fi
done

if [ "$SCRIPT_DIR" != "$GRANJA_DIR" ] && [ -d "$SCRIPT_DIR/ui" ]; then
    mkdir -p "$GRANJA_DIR/ui"
    cp -r "$SCRIPT_DIR/ui/." "$GRANJA_DIR/ui/"
fi
python3 "$GRANJA_DIR/scripts/instalar_acceso_servicios.py" || warn "Podés abrir mis_servicios.sh desde la carpeta."

find "$GRANJA_DIR" -type f -name '*.sh' -exec chmod +x {} + 2>/dev/null || true

echo ""
echo -e "${BOLD}══════════════════════════════════════════${NC}"
echo -e "${BOLD}  ⚡ INSTALACIÓN DE NÚCLEO IA COMPLETADA${NC}"
echo -e "${BOLD}══════════════════════════════════════════${NC}"
echo ""
echo "  Directorio:  $GRANJA_DIR"
echo ""
echo -e "${BOLD}  PASOS SIGUIENTES:${NC}"
echo ""
echo -e "  1. ${CYAN}cd $GRANJA_DIR${NC}"
echo -e "  2. ${CYAN}bash agregar_cuentas.sh${NC} (configurar API keys)"
echo -e "  3. ${CYAN}bash iniciar_todo.sh${NC}    (arrancar el servidor)"
echo ""
