#!/usr/bin/env bash
# ==============================================================================
#  ajustar_ranking_manual.sh — Edición Directa del Ranking Global por Números
#  Soporta opción 0 para cancelar/salir en todos los menús y submenús.
# ==============================================================================

if [ ! -t 0 ] || [ ! -t 1 ]; then
    for term in konsole alacritty kitty xterm gnome-terminal xfce4-terminal; do
        if command -v "$term" >/dev/null 2>&1; then
            case "$term" in
                konsole)
                    exec konsole --noclose -e "$0" "$@"
                    ;;
                alacritty)
                    exec alacritty -e "$0" "$@"
                    ;;
                kitty)
                    exec kitty --hold "$0" "$@"
                    ;;
                *)
                    exec "$term" -e "$0" "$@"
                    ;;
            esac
        fi
    done
fi

DIR_RAIZ="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR_RAIZ" || exit 1

FILE_RANKING="$DIR_RAIZ/state/ranking_global.json"

COLOR_TITULO="\033[1;34m"
COLOR_EXITO="\033[1;32m"
COLOR_ALERTA="\033[1;33m"
COLOR_RESET="\033[0m"

sincronizar() {
    if [ -f "$FILE_RANKING" ]; then
        exp_dir="$DIR_RAIZ/../NUCLEO_IA_FINAL_PUBLICO"
        if [ -d "$exp_dir/state" ]; then
            cp -f "$FILE_RANKING" "$exp_dir/state/ranking_global.json" 2>/dev/null || true
        fi
    fi
}

mostrar_ranking() {
    echo -e "\n${COLOR_TITULO}════════════════════════════════════════════════════════════════════════${COLOR_RESET}"
    echo -e "${COLOR_TITULO}   RANKING GLOBAL ACTIVO (state/ranking_global.json)${COLOR_RESET}"
    echo -e "${COLOR_TITULO}════════════════════════════════════════════════════════════════════════${COLOR_RESET}"
    python3 -c "
import json
with open('$FILE_RANKING', 'r') as f:
    datos = json.load(f)
ranking = datos.get('ranking', [])
print(f'  {\"Nº\":>3}  {\"PROVEEDOR\":12s}  {\"MODELO ID\":40s}')
print('  ' + '-'*3 + '  ' + '-'*12 + '  ' + '-'*40)
for m in ranking:
    mid = m.get('modelo_id') or m.get('id') or m.get('modelo_base')
    print(f'  {m.get(\"posicion\", 0):>3}) {m.get(\"proveedor\", \"?\"):12s}  {mid:40s}')
"
    echo -e "${COLOR_TITULO}════════════════════════════════════════════════════════════════════════${COLOR_RESET}\n"
}

mover_por_numero() {
    num_origen="$1"
    num_destino="$2"

    python3 -c "
import json, sys

archivo = '$FILE_RANKING'
with open(archivo, 'r', encoding='utf-8') as f:
    datos = json.load(f)

ranking = datos.get('ranking', [])

try:
    idx_orig = int('$num_origen') - 1
    idx_dest = int('$num_destino') - 1
except ValueError:
    print('❌ Error: Ingresá números válidos.')
    sys.exit(1)

if not (0 <= idx_orig < len(ranking)):
    print(f'❌ Número de modelo original invalido (debe ser entre 1 y {len(ranking)}).')
    sys.exit(1)

modelo_elegido = ranking.pop(idx_orig)
insert_idx = max(0, min(idx_dest, len(ranking)))
ranking.insert(insert_idx, modelo_elegido)

for i, m in enumerate(ranking):
    m['posicion'] = i + 1

datos['ranking'] = ranking
with open(archivo, 'w', encoding='utf-8') as f:
    json.dump(datos, f, indent=2, ensure_ascii=False)

print(f'✅ \"{modelo_elegido.get(\"modelo_id\")}\" movido a la posición #{insert_idx + 1}')
"
    if [ $? -eq 0 ]; then
        sincronizar
    fi
}

intercambiar_por_numero() {
    num1="$1"
    num2="$2"

    python3 -c "
import json, sys

archivo = '$FILE_RANKING'
with open(archivo, 'r', encoding='utf-8') as f:
    datos = json.load(f)

ranking = datos.get('ranking', [])

try:
    idx1 = int('$num1') - 1
    idx2 = int('$num2') - 1
except ValueError:
    print('❌ Error: Ingresá números válidos.')
    sys.exit(1)

if not (0 <= idx1 < len(ranking)) or not (0 <= idx2 < len(ranking)):
    print('❌ Número de posición fuera de rango.')
    sys.exit(1)

ranking[idx1], ranking[idx2] = ranking[idx2], ranking[idx1]

for i, m in enumerate(ranking):
    m['posicion'] = i + 1

datos['ranking'] = ranking
with open(archivo, 'w', encoding='utf-8') as f:
    json.dump(datos, f, indent=2, ensure_ascii=False)

print(f'✅ Puestos #{idx1+1} y #{idx2+1} intercambiados exitosamente.')
"
    if [ $? -eq 0 ]; then
        sincronizar
    fi
}

armar_orden_por_numeros() {
    python3 -c "
import json, sys

archivo = '$FILE_RANKING'
with open(archivo, 'r', encoding='utf-8') as f:
    datos = json.load(f)

ranking = datos.get('ranking', [])
disponibles = list(ranking)
nuevo_ranking = []

print('\n--- ARMAR ORDEN PASO A PASO POR NÚMERO ---')
print('(Ingresá 0 en cualquier momento para cancelar y salir al menú principal)')

for pos in range(1, len(ranking) + 1):
    print(f'\n📌 Seleccioná qué modelo poner en el PUESTO #{pos}:')
    print('   0) ❌ Cancelar y salir al menú principal')
    for i, m in enumerate(disponibles, 1):
        mid = m.get('modelo_id') or m.get('id')
        print(f'   {i:2d}) {mid} ({m.get(\"proveedor\")})')
    
    cancelado = False
    while True:
        try:
            opc = input(f'Ingresá NÚMERO para puesto #{pos} (0 para cancelar): ').strip()
            if opc == '0':
                print('⚠️ Operación cancelada. Volviendo al menú principal...')
                cancelado = True
                break
            idx = int(opc) - 1
            if 0 <= idx < len(disponibles):
                elegido = disponibles.pop(idx)
                elegido['posicion'] = pos
                nuevo_ranking.append(elegido)
                print(f'   ➡️ Puesto #{pos} asignado a: {elegido.get(\"modelo_id\")}')
                break
            else:
                print('Número fuera de rango.')
        except ValueError:
            print('Ingresá un número entero válido.')

    if cancelado:
        sys.exit(1)

datos['ranking'] = nuevo_ranking
with open(archivo, 'w', encoding='utf-8') as f:
    json.dump(datos, f, indent=2, ensure_ascii=False)

print('\n✅ ¡Nuevo orden completo guardado exitosamente en state/ranking_global.json!')
"
    if [ $? -eq 0 ]; then
        sincronizar
    fi
}

restaurar_automatico() {
    echo -e "${COLOR_ALERTA}🔄 Recalculando el ranking automático por algoritmo...${COLOR_RESET}"
    python3 "$DIR_RAIZ/scripts/ranking_global.py" > /dev/null 2>&1
    sincronizar
    echo -e "${COLOR_EXITO}✅ Ranking restaurado al cálculo automático original.${COLOR_RESET}\n"
}

# --- Procesamiento CLI directo ---
if [ "$#" -gt 0 ]; then
    case "$1" in
        --list|-l)
            mostrar_ranking
            exit 0
            ;;
        --mover|-m)
            if [ -n "$2" ] && [ -n "$3" ]; then
                mover_por_numero "$2" "$3"
                exit 0
            fi
            ;;
        --swap|-s)
            if [ -n "$2" ] && [ -n "$3" ]; then
                intercambiar_por_numero "$2" "$3"
                exit 0
            fi
            ;;
        --reset|-r)
            restaurar_automatico
            exit 0
            ;;
        *)
            if [ -n "$1" ] && [ -n "$2" ]; then
                mover_por_numero "$1" "$2"
                exit 0
            fi
            ;;
    esac
fi

# --- Menú Interactivo Súper Cómodo ---
while true; do
    echo -e "${COLOR_TITULO}========================================================================${COLOR_RESET}"
    echo -e "${COLOR_TITULO}   AJUSTE MANUAL DE RANKING GLOBAL (Núcleo IA)${COLOR_RESET}"
    echo -e "${COLOR_TITULO}========================================================================${COLOR_RESET}"
    echo " 1) 📋 Ver Ranking Global Actual"
    echo " 2) 📌 Mover un modelo a otro puesto (Nº de modelo y Nº de puesto)"
    echo " 3) 🔀 Intercambiar 2 modelos (Nº de primer y Nº de segundo modelo)"
    echo " 4) ✍️ Armar orden completo desde cero (Paso a paso)"
    echo " 5) 🔄 Volver a calcular ranking automático por algoritmo"
    echo " 0) 🚪 Salir"
    echo -e "${COLOR_TITULO}========================================================================${COLOR_RESET}"
    read -p "Seleccioná una opción [0-5]: " opc

    case "$opc" in
        1) mostrar_ranking ;;
        2)
            mostrar_ranking
            read -p "Ingresá NÚMERO del modelo a mover (0 para cancelar): " orig_in
            if [ "$orig_in" = "0" ] || [ -z "$orig_in" ]; then echo "Operación cancelada."; continue; fi
            read -p "¿A qué NÚMERO de puesto querés moverlo? (0 para cancelar): " dest_in
            if [ "$dest_in" = "0" ] || [ -z "$dest_in" ]; then echo "Operación cancelada."; continue; fi
            mover_por_numero "$orig_in" "$dest_in"
            ;;
        3)
            mostrar_ranking
            read -p "NÚMERO del primer modelo (0 para cancelar): " n1
            if [ "$n1" = "0" ] || [ -z "$n1" ]; then echo "Operación cancelada."; continue; fi
            read -p "NÚMERO del segundo modelo (0 para cancelar): " n2
            if [ "$n2" = "0" ] || [ -z "$n2" ]; then echo "Operación cancelada."; continue; fi
            intercambiar_por_numero "$n1" "$n2"
            ;;
        4) armar_orden_por_numeros ;;
        5) restaurar_automatico ;;
        0|6) echo "¡Hasta luego!"; break ;;
        *) echo "Opción no válida." ;;
    esac
done
