#!/usr/bin/env python3
"""
ajustar_ranking_manual.py — Edición Directa del Ranking Global (Multiplataforma)
Soporta mover modelos, reordenar, intercambiar, eliminar y sincronizar con la copia exportable.
"""
import os
import sys
import json
from pathlib import Path

if hasattr(sys.stdout, 'reconfigure'):
    try: sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception: pass
if hasattr(sys.stderr, 'reconfigure'):
    try: sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception: pass

ROOT = Path(__file__).resolve().parent.parent
FILE_RANKING = ROOT / 'state' / 'ranking_global.json'
RANKING_PRELOAD_MARKER = ROOT / 'state' / 'rankings_precargados.json'

# Detectar dinámicamente la carpeta exportable
CANDIDATE_EXPORTABLES = [
    ROOT.parent / 'NUCLEO_IA_FINAL_PUBLICO' / 'state' / 'ranking_global.json',
]


def find_exportable_ranking_path() -> Path | None:
    for cand in CANDIDATE_EXPORTABLES:
        if cand.parent.parent.exists():
            cand.parent.mkdir(parents=True, exist_ok=True)
            return cand
    return None


def sincronizar():
    if not FILE_RANKING.exists():
        return
    exp_path = find_exportable_ranking_path()
    if exp_path:
        try:
            exp_path.write_text(FILE_RANKING.read_text(encoding='utf-8'), encoding='utf-8')
            print(f"  [OK] Sincronizado ranking con versión exportable: {exp_path}")
        except Exception as e:
            print(f"  [WARN] No se pudo sincronizar con exportable: {e}")


def cargar_datos() -> dict:
    if not FILE_RANKING.exists():
        return {"generado": "", "ranking": []}
    try:
        return json.loads(FILE_RANKING.read_text(encoding='utf-8'))
    except Exception as e:
        print(f"  [ERROR] Error leyendo {FILE_RANKING}: {e}")
        return {"generado": "", "ranking": []}


def guardar_datos(datos: dict):
    FILE_RANKING.parent.mkdir(parents=True, exist_ok=True)
    FILE_RANKING.write_text(json.dumps(datos, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    sincronizar()


def mostrar_ranking():
    datos = cargar_datos()
    ranking = datos.get('ranking', [])
    print('\n' + '=' * 72)
    print('   RANKING GLOBAL ACTIVO (state/ranking_global.json)')
    print('=' * 72)
    print(f"  {'Nº':>3}  {'PTS':>4}  {'PROVEEDOR':12s}  {'MODELO ID':42s}")
    print('  ' + '-' * 3 + '  ' + '-' * 4 + '  ' + '-' * 12 + '  ' + '-' * 42)
    for i, m in enumerate(ranking, 1):
        mid = m.get('modelo_id') or m.get('id') or m.get('modelo_base') or 'desconocido'
        pts = m.get('puntaje', 0)
        prov = m.get('proveedor', '?')
        print(f"  {i:>3}) {pts:>4}  {prov:12s}  {mid:42s}")
    print('=' * 72 + '\n')


def mover_modelo():
    datos = cargar_datos()
    ranking = datos.get('ranking', [])
    if not ranking:
        print("  [!] El ranking está vacío.")
        return

    mostrar_ranking()
    try:
        orig = input(f"  Ingresa el número del modelo a mover (1-{len(ranking)}) [0=cancelar]: ").strip()
        if orig in ('', '0'):
            return
        idx_orig = int(orig) - 1
        if not (0 <= idx_orig < len(ranking)):
            print("  [ERROR] Número de origen inválido.")
            return

        dest = input(f"  Ingresa la nueva posición deseada (1-{len(ranking)}) [0=cancelar]: ").strip()
        if dest in ('', '0'):
            return
        idx_dest = max(0, min(int(dest) - 1, len(ranking) - 1))

        item = ranking.pop(idx_orig)
        ranking.insert(idx_dest, item)

        for i, m in enumerate(ranking, 1):
            m['posicion'] = i

        datos['ranking'] = ranking
        guardar_datos(datos)
        print(f"  [OK] Modelo '{item.get('modelo_id')}' movido a la posición #{idx_dest + 1} exitosamente.")
    except ValueError:
        print("  [ERROR] Entrada inválida.")


def intercambiar_modelos():
    datos = cargar_datos()
    ranking = datos.get('ranking', [])
    if len(ranking) < 2:
        print("  [!] Se necesitan al menos 2 modelos para intercambiar.")
        return

    mostrar_ranking()
    try:
        p1 = input("  Primer número de posición [0=cancelar]: ").strip()
        if p1 in ('', '0'): return
        p2 = input("  Segundo número de posición [0=cancelar]: ").strip()
        if p2 in ('', '0'): return

        i1, i2 = int(p1) - 1, int(p2) - 1
        if not (0 <= i1 < len(ranking) and 0 <= i2 < len(ranking)):
            print("  [ERROR] Posiciones fuera de rango.")
            return

        ranking[i1], ranking[i2] = ranking[i2], ranking[i1]
        for i, m in enumerate(ranking, 1):
            m['posicion'] = i

        datos['ranking'] = ranking
        guardar_datos(datos)
        print(f"  [OK] Intercambiadas posiciones #{p1} y #{p2}.")
    except ValueError:
        print("  [ERROR] Entrada inválida.")


def eliminar_modelo():
    datos = cargar_datos()
    ranking = datos.get('ranking', [])
    if not ranking:
        print("  [!] El ranking está vacío.")
        return

    mostrar_ranking()
    try:
        pos = input(f"  Número del modelo a eliminar (1-{len(ranking)}) [0=cancelar]: ").strip()
        if pos in ('', '0'): return
        idx = int(pos) - 1
        if not (0 <= idx < len(ranking)):
            print("  [ERROR] Posición inválida.")
            return

        eliminado = ranking.pop(idx)
        for i, m in enumerate(ranking, 1):
            m['posicion'] = i

        datos['ranking'] = ranking
        guardar_datos(datos)
        print(f"  [OK] Eliminado '{eliminado.get('modelo_id')}' del ranking.")
    except ValueError:
        print("  [ERROR] Entrada inválida.")


def menu_principal():
    while True:
        print('\n' + '=' * 60)
        print('  🎛️  AJUSTAR RANKING MANUAL — Núcleo IA')
        print('=' * 60)
        print('  1) Ver ranking actual')
        print('  2) Mover modelo a otra posición')
        print('  3) Intercambiar dos modelos')
        print('  4) Eliminar un modelo del ranking')
        print('  5) Forzar sincronización con copia exportable')
        print('  0) Salir')
        print('=' * 60)

        opc = input('  Opción [1]: ').strip() or '1'
        if opc == '0':
            print('  Listo.')
            break
        elif opc == '1':
            mostrar_ranking()
        elif opc == '2':
            mover_modelo()
        elif opc == '3':
            intercambiar_modelos()
        elif opc == '4':
            eliminar_modelo()
        elif opc == '5':
            sincronizar()
        else:
            print('  Opción no reconocida.')


if __name__ == '__main__':
    if RANKING_PRELOAD_MARKER.is_file():
        print('El ranking disponible todavía es un catálogo inicial, no un resultado local.')
        print('Conectá cuentas y completá una actualización de rankings antes de ordenarlo.')
        raise SystemExit(1)
    menu_principal()
