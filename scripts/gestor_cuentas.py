#!/usr/bin/env python3
"""Helper común para altas de cuentas/secretos en Núcleo IA."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ENV_FILE = ROOT / '.env'
CUENTAS_FILE = ROOT / 'cuentas.json'


def norm_id(text: str) -> str:
    return re.sub(r'[^A-Za-z0-9]+', '_', str(text).upper()).strip('_')


def load_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except Exception:
        return {}


def save_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')


def upsert_env(name: str, value: str) -> None:
    lines = ENV_FILE.read_text(encoding='utf-8').splitlines() if ENV_FILE.exists() else []
    out: list[str] = []
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
    ENV_FILE.write_text('\n'.join(out) + '\n', encoding='utf-8')


def upsert_servicio_activo(provider: str) -> None:
    granja_env = ROOT / 'granja.env'
    if not granja_env.exists():
        return
    lines = granja_env.read_text(encoding='utf-8').splitlines()
    out = []
    for line in lines:
        if line.lstrip().startswith('SERVICIOS_ACTIVOS='):
            parts = line.split('=', 1)
            servicios = [x.strip() for x in parts[1].split(',') if x.strip()]
            if provider not in servicios:
                servicios.append(provider)
            line = f"SERVICIOS_ACTIVOS={','.join(servicios)}"
        out.append(line)
    granja_env.write_text('\n'.join(out) + '\n', encoding='utf-8')

def upsert_account(provider: str, account_id: str, data: dict) -> None:
    # Nunca persistir secretos en cuentas.json. Los proveedores los resuelven
    # desde las variables por cuenta escritas previamente en .env.
    sensitive = {'api_key', 'token', 'auth_token', 'secret', 'secret_key', 'api_secret', 'password'}
    safe_data = {k: v for k, v in data.items() if k.lower() not in sensitive}
    root = load_json(CUENTAS_FILE)
    prov = root.setdefault('proveedores', {})
    orden = root.setdefault('orden_failover', [])
    if provider not in orden:
        orden.append(provider)
    section = prov.setdefault(provider, {})
    cuentas = section.setdefault('cuentas', [])
    for item in cuentas:
        if isinstance(item, dict) and str(item.get('id')) == account_id:
            for key in list(item):
                if key.lower() in sensitive:
                    item.pop(key, None)
            item.update(safe_data)
            break
    else:
        entry = {'id': account_id}
        entry.update(safe_data)
        cuentas.append(entry)
    save_json(CUENTAS_FILE, root)
    upsert_servicio_activo(provider)


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print('usage: gestor_cuentas.py <provider> <account_id> <api_key> [--email <email>]', file=sys.stderr)
        return 2

    email = ''
    filtered_argv = [argv[0], argv[1]]
    i = 2
    while i < len(argv):
        if argv[i] == '--email' and i + 1 < len(argv):
            email = argv[i + 1].strip()
            i += 2
        elif argv[i].startswith('--email='):
            email = argv[i].split('=', 1)[1].strip()
            i += 1
        else:
            filtered_argv.append(argv[i])
            i += 1
    argv = filtered_argv

    provider = argv[1]
    extra = {'email': email} if email else {}

    if provider == 'google':
        account_id, api_key = argv[2], argv[3]
        suf = norm_id(account_id)
        upsert_env(f'GOOGLE_API_KEY_{suf}', api_key)
        upsert_env(f'GEMINI_API_KEY_{suf}', api_key)
        upsert_env('GOOGLE_API_KEY', api_key)
        upsert_env('GEMINI_API_KEY', api_key)
        upsert_account('google', account_id, {'api_key': api_key, 'nombre_app': 'LaGranjaDeIA', **extra})
        return 0

    if provider == 'cohere':
        account_id, api_key = argv[2], argv[3]
        suf = norm_id(account_id)
        upsert_env(f'COHERE_API_KEY_{suf}', api_key)
        upsert_env('COHERE_API_KEY', api_key)
        upsert_account('cohere', account_id, {'api_key': api_key, 'nombre_app': 'LaGranjaDeIA', **extra})
        return 0

    if provider == 'openrouter':
        account_id, api_key = argv[2], argv[3]
        url_app = argv[4] if len(argv) > 4 else ''
        suf = norm_id(account_id)
        upsert_env(f'OPENROUTER_API_KEY_{suf}', api_key)
        upsert_env('OPENROUTER_API_KEY', api_key)
        upsert_account('openrouter', account_id, {'api_key': api_key, 'url_app': url_app, 'nombre_app': 'LaGranjaDeIA', **extra})
        return 0

    if provider == 'nvidia':
        account_id, api_key = argv[2], argv[3]
        suf = norm_id(account_id)
        upsert_env(f'NVIDIA_API_KEY_{suf}', api_key)
        upsert_env(f'NVIDIA_KEY_{suf}', api_key)
        upsert_env('NVIDIA_API_KEY', api_key)
        upsert_env('NVIDIA_KEY', api_key)
        upsert_account('nvidia', account_id, {'api_key': api_key, 'nombre_app': 'LaGranjaDeIA', **extra})
        return 0

    if provider == 'cloudflare':
        account_id, api_key = argv[2], argv[3]
        suf = norm_id(account_id)
        upsert_env(f'CLOUDFLARE_ACCOUNT_ID_{suf}', account_id)
        upsert_env(f'CLOUDFLARE_API_TOKEN_{suf}', api_key)
        upsert_env('CLOUDFLARE_ACCOUNT_ID', account_id)
        upsert_env('CLOUDFLARE_API_TOKEN', api_key)
        upsert_account('cloudflare', account_id, {'account_id': account_id, 'api_key': api_key, 'nombre_app': 'LaGranjaDeIA', **extra})
        return 0

    if provider == 'siliconflow':
        account_id, api_key = argv[2], argv[3]
        suf = norm_id(account_id)
        upsert_env(f'SILICONFLOW_API_KEY_{suf}', api_key)
        upsert_env('SILICONFLOW_API_KEY', api_key)
        upsert_account('siliconflow', account_id, {'nombre_app': 'LaGranjaDeIA', **extra})
        return 0

    if provider == 'zhipu':
        account_id, api_key = argv[2], argv[3]
        suf = norm_id(account_id)
        upsert_env(f'ZHIPU_API_KEY_{suf}', api_key)
        upsert_env('ZHIPU_API_KEY', api_key)
        upsert_account('zhipu', account_id, {'nombre_app': 'LaGranjaDeIA', **extra})
        return 0

    if provider == 'groq':
        account_id, api_key = argv[2], argv[3]
        suf = norm_id(account_id)
        upsert_env(f'GROQ_API_KEY_{suf}', api_key)
        upsert_env('GROQ_API_KEY', api_key)
        upsert_account('groq', account_id, {'api_key': api_key, 'nombre_app': 'LaGranjaDeIA', **extra})
        return 0

    if provider == 'tokenrouter':
        account_id, api_key = argv[2], argv[3]
        suf = norm_id(account_id)
        upsert_env(f'TOKENROUTER_API_KEY_{suf}', api_key)
        upsert_env('TOKENROUTER_API_KEY', api_key)
        upsert_account('tokenrouter', account_id, {'api_key': api_key, 'nombre_app': 'LaGranjaDeIA', **extra})
        return 0

    if provider == 'xkiro':
        account_id, api_key = argv[2], argv[3]
        suf = norm_id(account_id)
        upsert_env(f'XKIRO_API_KEY_{suf}', api_key)
        upsert_env('XKIRO_API_KEY', api_key)
        upsert_account('xkiro', account_id, {
            'url_base': 'https://api.xkiro.com/v1/chat/completions',
            'nombre_app': 'NucleoIA',
            **extra
        })
        return 0

    if provider == 'tokenharbor':
        account_id, api_key = argv[2], argv[3]
        if not api_key.startswith('thk_'):
            print('clave Token Harbor inválida: se esperaba prefijo thk_', file=sys.stderr)
            return 2
        suf = norm_id(account_id)
        upsert_env(f'TOKENHARBOR_API_KEY_{suf}', api_key)
        upsert_env('TOKENHARBOR_API_KEY', api_key)
        upsert_account('tokenharbor', account_id, {
            'url_base': 'https://tokenharbor.ai/v1/chat/completions',
            'nombre_app': 'NucleoIA',
            'solo_free': True,
            **extra
        })
        return 0

    print(f'provider desconocido: {provider}', file=sys.stderr)
    return 2


if __name__ == '__main__':
    raise SystemExit(main(sys.argv))
