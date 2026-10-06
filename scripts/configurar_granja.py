#!/usr/bin/env python3
"""
Configuracion interactiva multiplataforma para Nucleo IA.
Permite modificar servicios activos, rotacion, puertos y variables de entorno.
"""
import os
import sys
import re
import secrets
from pathlib import Path

if hasattr(sys.stdout, 'reconfigure'):
    try: sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception: pass
if hasattr(sys.stderr, 'reconfigure'):
    try: sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception: pass

ROOT = Path(__file__).resolve().parent.parent
ENV_FILE = ROOT / '.env'
LEGACY_ENV = ROOT / 'granja.env'

ALL_SERVICES = ['ollama', 'cloudflare', 'nvidia', 'openrouter', 'google', 'cohere', 'siliconflow', 'zhipu', 'groq', 'tokenrouter', 'xkiro', 'tokenharbor', 'apinex']


def get_var(name: str, default: str = '') -> str:
    for path in (ENV_FILE, LEGACY_ENV):
        if path.exists():
            for line in path.read_text(encoding='utf-8', errors='ignore').splitlines():
                raw = line.strip()
                if raw.startswith(f'{name}='):
                    val = raw.split('=', 1)[1].strip()
                    if (val.startswith('"') and val.endswith('"')) or (val.startswith("'") and val.endswith("'")):
                        val = val[1:-1]
                    return val
    return default


def set_var(name: str, value: str) -> None:
    for path in (ENV_FILE, LEGACY_ENV):
        if path.exists():
            lines = path.read_text(encoding='utf-8', errors='ignore').splitlines()
            out = []
            replaced = False
            for line in lines:
                if line.lstrip().startswith(f'{name}='):
                    out.append(f'{name}={value}')
                    replaced = True
                else:
                    out.append(line)
            if not replaced:
                if out and out[-1].strip():
                    out.append('')
                out.append(f'{name}={value}')
            path.write_text('\n'.join(out) + '\n', encoding='utf-8')


def interactive_menu():
    print('=' * 60)
    print('  CONFIGURACION - Nucleo IA (Multiplataforma)')
    print('=' * 60)

    current_services = get_var('SERVICIOS_ACTIVOS', 'ollama,groq,tokenrouter,xkiro,tokenharbor,apinex,cloudflare,nvidia,openrouter,google,cohere,zhipu')
    current_top = get_var('ROTACION_TOP_N', '3')
    current_port = get_var('PROXY_PORT', '8080')
    current_host = get_var('PROXY_HOST', '127.0.0.1')
    current_profile = get_var('PERFIL_USO', 'personal')

    print(f'  * Servicios activos:  {current_services}')
    print(f'  * Rotacion (Top N):   {current_top}')
    print(f'  * Host / Puerto:      http://{current_host}:{current_port}')
    print(f'  * Perfil de uso:      {current_profile}')
    print('=' * 60)
    print('  1) Modificar servicios activos')
    print('  2) Modificar profundidad de rotacion (ROTACION_TOP_N)')
    print('  3) Modificar puerto del proxy (PROXY_PORT)')
    print('  4) Configuracion completa guiada')
    print('  0) Salir sin cambios')
    print('=' * 60)

    choice = input('  Elige una opcion [4]: ').strip() or '4'

    if choice == '0':
        print('  Cancelado.')
        return

    if choice in ('1', '4'):
        print('\n  Servicios disponibles:')
        for i, s in enumerate(ALL_SERVICES, 1):
            activo = '[X]' if s in current_services.split(',') else '[ ]'
            print(f'    {i}) {s:12s} {activo}')
        print('\n  Ingresa los numeros o nombres separados por coma (ej: 1,2,4,5)')
        print(f'  [ENTER] para mantener: {current_services}')
        val = input(f'  Seleccion [{current_services}]: ').strip()
        if val:
            selected = []
            for item in val.split(','):
                item = item.strip().lower()
                if item.isdigit():
                    idx = int(item) - 1
                    if 0 <= idx < len(ALL_SERVICES):
                        selected.append(ALL_SERVICES[idx])
                elif item in ALL_SERVICES:
                    selected.append(item)
            if selected:
                new_services = ','.join(selected)
                set_var('SERVICIOS_ACTIVOS', new_services)
                print(f'  [OK] SERVICIOS_ACTIVOS actualizado a: {new_services}')

    if choice in ('2', '4'):
        print(f'\n  Profundidad de rotacion actual: {current_top}')
        val = input(f'  Nuevo valor de ROTACION_TOP_N [{current_top}]: ').strip()
        if val and val.isdigit():
            set_var('ROTACION_TOP_N', val)
            print(f'  [OK] ROTACION_TOP_N actualizado a: {val}')

    if choice in ('3', '4'):
        print(f'\n  Puerto actual del proxy: {current_port}')
        val = input(f'  Nuevo valor de PROXY_PORT [{current_port}]: ').strip()
        if val and val.isdigit():
            set_var('PROXY_PORT', val)
            print(f'  [OK] PROXY_PORT actualizado a: {val}')

    if choice == '4':
        print('\n  Modo: Personal conserva acceso local simple; Profesional separa consumo y administración.')
        profile = input(f'  Modo [personal/profesional] [{current_profile}]: ').strip().lower()
        if profile in {'empresa', 'organización', 'organizacion'}:
            profile = 'profesional'
        if profile in {'personal', 'profesional'}:
            set_var('PERFIL_USO', profile)
            if profile == 'profesional':
                set_var('AUTH_ENABLED', 'true')
                if not get_var('NUCLEO_API_KEY'):
                    set_var('NUCLEO_API_KEY', secrets.token_urlsafe(32))
                if not get_var('NUCLEO_ADMIN_KEY'):
                    set_var('NUCLEO_ADMIN_KEY', secrets.token_urlsafe(32))
                print('  [OK] Acceso de consumo y administración protegido con claves generadas localmente.')

    print('\n  [OK] Configuracion guardada exitosamente.')


if __name__ == '__main__':
    interactive_menu()
