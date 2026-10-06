#!/usr/bin/env python3
"""Asistente rápido de terminal para asociar correos a cuentas existentes en cuentas.json."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
CUENTAS_FILE = ROOT / 'cuentas.json'


def cargar_cuentas() -> dict:
    return json.loads(CUENTAS_FILE.read_text(encoding='utf-8'))


def guardar_cuentas(data: dict) -> None:
    CUENTAS_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')


def obtener_pozo(data: dict) -> list[str]:
    mails = set()
    for prov in data.get('proveedores', {}).values():
        if isinstance(prov, dict):
            for c in prov.get('cuentas', []):
                if isinstance(c, dict) and c.get('email'):
                    m = str(c.get('email', '')).strip()
                    if m:
                        mails.add(m)
    return sorted(mails)


def cuentas_sin_correo(data: dict) -> list[tuple[str, dict]]:
    sin = []
    for prov_name, prov in data.get('proveedores', {}).items():
        if isinstance(prov, dict):
            for c in prov.get('cuentas', []):
                if isinstance(c, dict) and not str(c.get('email', '')).strip():
                    sin.append((prov_name, c))
    return sin


def main() -> int:
    parser = argparse.ArgumentParser(description='Asocia correos a cuentas existentes sin correo')
    parser.add_argument('--list', action='store_true', help='Lista cuentas que no tienen correo asignado')
    parser.add_argument('--set', nargs=3, metavar=('PROVEEDOR', 'ACCOUNT_ID', 'EMAIL'), help='Asigna un correo directamente')
    args = parser.parse_args()

    data = cargar_cuentas()
    pozo = obtener_pozo(data)

    if args.list:
        sin = cuentas_sin_correo(data)
        if not sin:
            print('✅ Todas las cuentas registradas tienen correo asociado.')
            return 0
        print(f'⚠️ Hay {len(sin)} cuenta(s) sin correo asociado:')
        for prov, c in sin:
            print(f"  • [{prov}] {c.get('id')} ({c.get('nombre') or c.get('nombre_app') or 'sin nombre'})")
        return 0

    if args.set:
        prov, aid, email = args.set
        cuentas = data.get('proveedores', {}).get(prov, {}).get('cuentas', [])
        target = next((c for c in cuentas if c.get('id') == aid), None)
        if not target:
            print(f'Error: no se encontró la cuenta {aid} en {prov}', file=sys.stderr)
            return 1
        target['email'] = email.strip()
        guardar_cuentas(data)
        print(f"✅ Cuenta [{prov}] {aid} asociada a: {email.strip()}")
        return 0

    # Modo interactivo
    sin = cuentas_sin_correo(data)
    if not sin:
        print('✅ Todas las cuentas registradas tienen un correo asignado.')
        return 0

    print('=====================================================')
    print(' ASOCIADOR DE CORREOS PARA CUENTAS DE NÚCLEO IA')
    print('=====================================================')
    print(f'Se encontraron {len(sin)} cuenta(s) sin correo asociado.\n')

    if pozo:
        print('Pozo de correos conocidos detectados:')
        for idx, m in enumerate(pozo, 1):
            print(f'  [{idx:2}] {m}')
        print()
    else:
        print('(No se encontraron correos previos en el pozo)')

    modificadas = 0
    for prov, c in sin:
        cid = c.get('id')
        cnombre = c.get('nombre') or c.get('nombre_app') or cid
        print(f"\n👉 Proveedor: [{prov}]  |  Cuenta: {cid} ({cnombre})")
        resp = input('   Elegí el número del pozo, escribí un correo nuevo (o Enter para omitir): ').strip()
        if not resp:
            continue
        if resp.isdigit() and 1 <= int(resp) <= len(pozo):
            email_elegido = pozo[int(resp) - 1]
        else:
            email_elegido = resp

        if '@' not in email_elegido:
            print('   ⚠️ Correo inválido, se omitió esta cuenta.')
            continue

        c['email'] = email_elegido
        modificadas += 1
        print(f'   ✅ Asignado: {email_elegido}')

    if modificadas > 0:
        guardar_cuentas(data)
        print(f'\n🎉 Se guardaron {modificadas} asociaciones en cuentas.json.')
    else:
        print('\nNo se realizaron cambios.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
