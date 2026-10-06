#!/usr/bin/env python3
"""Helpers for local config/secrets in Núcleo IA."""
from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent


def _parse_env_file(path: Path) -> dict[str, str]:
    data: dict[str, str] = {}
    try:
        text = path.read_text(encoding='utf-8')
    except (FileNotFoundError, OSError):
        return data
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        if line.startswith('export '):
            line = line[7:].lstrip()
        key, value = line.split('=', 1)
        key = key.strip()
        value = value.strip()
        if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
            value = value[1:-1]
        data[key] = value
    return data


def load_local_env(root: Path | None = None) -> None:
    root = root or ROOT
    for filename in ('.env', 'granja.env'):
        env_path = root / filename
        for key, value in _parse_env_file(env_path).items():
            os.environ.setdefault(key, value)


def _read_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except Exception:
        return {}


def _norm_env_suffix(text: str) -> str:
    return re.sub(r'[^A-Za-z0-9]+', '_', str(text).upper()).strip('_')


def _is_placeholder_secret(value: Any) -> bool:
    if not value:
        return True
    text = str(value).strip()
    if not text:
        return True
    if text.startswith('TU_'):
        return True
    if text.startswith('<') and text.endswith('>'):
        return True
    if '...' in text:
        return True
    return False


def get_nvidia_api_key(root: Path | None = None) -> str | None:
    root = root or ROOT
    load_local_env(root)
    cuentas = _read_json(root / 'cuentas.json').get('proveedores', {}).get('nvidia', {}).get('cuentas', [])
    for idx, acc in enumerate(cuentas, 1):
        if not isinstance(acc, dict):
            continue
        account_id = str(acc.get('id', '')).strip()
        candidatos = [
            acc.get('api_key'),
            os.getenv(f'NVIDIA_API_KEY_{_norm_env_suffix(account_id)}') if account_id else None,
            os.getenv(f'NVIDIA_KEY_{_norm_env_suffix(account_id)}') if account_id else None,
            os.getenv(f'NVIDIA_API_KEY_{idx}'),
            os.getenv(f'NVIDIA_KEY_{idx}'),
            os.getenv('NVIDIA_API_KEY'),
            os.getenv('NVIDIA_KEY'),
        ]
        for key in candidatos:
            if not _is_placeholder_secret(key):
                return str(key)
    return None


def get_openrouter_accounts(root: Path | None = None) -> list[dict[str, Any]]:
    root = root or ROOT
    load_local_env(root)
    cuentas = _read_json(root / 'cuentas.json').get('proveedores', {}).get('openrouter', {}).get('cuentas', [])
    salida: list[dict[str, Any]] = []
    for idx, acc in enumerate(cuentas, 1):
        if not isinstance(acc, dict):
            continue
        item = dict(acc)
        account_id = str(item.get('id', '')).strip()
        candidatos = [
            item.get('api_key'),
            os.getenv(f'OPENROUTER_API_KEY_{_norm_env_suffix(account_id)}') if account_id else None,
            os.getenv(f'OPENROUTER_API_KEY_{idx}'),
            os.getenv('OPENROUTER_API_KEY'),
        ]
        for key in candidatos:
            if not _is_placeholder_secret(key):
                item['api_key'] = str(key)
                break
        salida.append(item)
    return salida


def get_openrouter_api_key(root: Path | None = None) -> str | None:
    accounts = get_openrouter_accounts(root)
    for acc in accounts:
        key = acc.get('api_key')
        if not _is_placeholder_secret(key):
            return str(key)
    return None


def get_cloudflare_accounts(root: Path | None = None) -> list[dict[str, str]]:
    root = root or ROOT
    load_local_env(root)
    cuentas = _read_json(root / 'cuentas.json').get('proveedores', {}).get('cloudflare', {}).get('cuentas', [])
    result: list[dict[str, str]] = []
    global_account_id = str(os.getenv('CLOUDFLARE_ACCOUNT_ID') or os.getenv('CLOUDFLARE_ACCOUNT') or '').strip()
    global_token = os.getenv('CLOUDFLARE_API_TOKEN') or os.getenv('CLOUDFLARE_AUTH_TOKEN')
    for idx, acc in enumerate(cuentas, 1):
        if not isinstance(acc, dict):
            continue
        account_id = str(acc.get('account_id') or acc.get('id') or '').strip()
        account_ref = str(acc.get('id') or '').strip()
        candidatos_token = [
            acc.get('api_key'),
            os.getenv(f'CLOUDFLARE_API_TOKEN_{_norm_env_suffix(account_ref)}') if account_ref else None,
            os.getenv(f'CLOUDFLARE_AUTH_TOKEN_{_norm_env_suffix(account_ref)}') if account_ref else None,
            os.getenv(f'CLOUDFLARE_API_TOKEN_{_norm_env_suffix(account_id)}') if account_id else None,
            os.getenv(f'CLOUDFLARE_AUTH_TOKEN_{_norm_env_suffix(account_id)}') if account_id else None,
            os.getenv(f'CLOUDFLARE_API_TOKEN_{idx}'),
            os.getenv(f'CLOUDFLARE_AUTH_TOKEN_{idx}'),
        ]
        if global_token and (len(cuentas) == 1 or (global_account_id and global_account_id == account_id)):
            candidatos_token.append(global_token)
        token = next((str(k) for k in candidatos_token if not _is_placeholder_secret(k)), None)
        if account_id and token:
            if not any(item['api_token'] == token and item['account_id'] == account_id for item in result):
                result.append({'account_id': account_id, 'api_token': token, 'cuenta_id': account_ref or f'cloudflare_{idx}'})
    account_id = global_account_id
    api_token = global_token
    if account_id and api_token and not _is_placeholder_secret(account_id) and not _is_placeholder_secret(api_token):
        if not any(item['api_token'] == str(api_token) and item['account_id'] == str(account_id) for item in result):
            result.append({'account_id': str(account_id), 'api_token': str(api_token), 'cuenta_id': 'cloudflare_env'})
    return result


def get_cloudflare_credentials(root: Path | None = None) -> dict[str, str] | None:
    accounts = get_cloudflare_accounts(root)
    return accounts[0] if accounts else None


def get_google_api_key(root: Path | None = None) -> str | None:
    root = root or ROOT
    load_local_env(root)
    for key in (
        os.getenv('GOOGLE_API_KEY'),
        os.getenv('GEMINI_API_KEY'),
    ):
        if not _is_placeholder_secret(key):
            return str(key)
    cuentas = _read_json(root / 'cuentas.json').get('proveedores', {}).get('google', {}).get('cuentas', [])
    for idx, acc in enumerate(cuentas, 1):
        if not isinstance(acc, dict):
            continue
        account_id = str(acc.get('id', '')).strip()
        candidatos = [
            acc.get('api_key'),
            os.getenv(f'GOOGLE_API_KEY_{_norm_env_suffix(account_id)}') if account_id else None,
            os.getenv(f'GEMINI_API_KEY_{_norm_env_suffix(account_id)}') if account_id else None,
            os.getenv(f'GOOGLE_API_KEY_{idx}'),
            os.getenv(f'GEMINI_API_KEY_{idx}'),
        ]
        for key in candidatos:
            if not _is_placeholder_secret(key):
                return str(key)
    return None


def get_cohere_api_key(root: Path | None = None) -> str | None:
    root = root or ROOT
    load_local_env(root)
    for key in (
        os.getenv('COHERE_API_KEY'),
    ):
        if not _is_placeholder_secret(key):
            return str(key)
    cuentas = _read_json(root / 'cuentas.json').get('proveedores', {}).get('cohere', {}).get('cuentas', [])
    for idx, acc in enumerate(cuentas, 1):
        if not isinstance(acc, dict):
            continue
        account_id = str(acc.get('id', '')).strip()
        candidatos = [
            acc.get('api_key'),
            os.getenv(f'COHERE_API_KEY_{_norm_env_suffix(account_id)}') if account_id else None,
            os.getenv(f'COHERE_API_KEY_{idx}'),
        ]
        for key in candidatos:
            if not _is_placeholder_secret(key):
                return str(key)
    return None

def get_siliconflow_api_key(root: Path | None = None) -> str | None:
    root = root or ROOT
    load_local_env(root)
    # 1. Variables de entorno globales
    for key in ['SILICONFLOW_API_KEY']:
        val = os.getenv(key)
        if val and not _is_placeholder_secret(val):
            return str(val).strip()
    # 2. cuentas.json
    cuentas = _read_json(root / 'cuentas.json')
    if 'proveedores' in cuentas and 'siliconflow' in cuentas['proveedores']:
        lista = cuentas['proveedores']['siliconflow'].get('cuentas', [])
        for c in lista:
            if isinstance(c, dict) and c.get('api_key') and not _is_placeholder_secret(c.get('api_key')):
                return str(c['api_key']).strip()
    return None

def get_zhipu_api_key(root: Path | None = None) -> str | None:
    root = root or ROOT
    load_local_env(root)
    # 1. Variables de entorno globales
    for key in ['ZHIPU_API_KEY']:
        val = os.getenv(key)
        if val and not _is_placeholder_secret(val):
            return str(val).strip()
    # 2. cuentas.json
    cuentas = _read_json(root / 'cuentas.json')
    if 'proveedores' in cuentas and 'zhipu' in cuentas['proveedores']:
        lista = cuentas['proveedores']['zhipu'].get('cuentas', [])
        for c in lista:
            if isinstance(c, dict) and c.get('api_key') and not _is_placeholder_secret(c.get('api_key')):
                return str(c['api_key']).strip()
    return None


def get_groq_accounts(root: Path | None = None) -> list[dict[str, Any]]:
    root = root or ROOT
    load_local_env(root)
    cuentas = _read_json(root / 'cuentas.json').get('proveedores', {}).get('groq', {}).get('cuentas', [])
    salida: list[dict[str, Any]] = []
    for idx, acc in enumerate(cuentas, 1):
        if not isinstance(acc, dict):
            continue
        item = dict(acc)
        account_id = str(item.get('id', '')).strip()
        candidatos = [
            item.get('api_key'),
            os.getenv(f'GROQ_API_KEY_{_norm_env_suffix(account_id)}') if account_id else None,
            os.getenv(f'GROQ_KEY_{_norm_env_suffix(account_id)}') if account_id else None,
            os.getenv(f'GROQ_API_KEY_{idx}'),
            os.getenv(f'GROQ_KEY_{idx}'),
            os.getenv('GROQ_API_KEY'),
            os.getenv('GROQ_KEY'),
        ]
        for key in candidatos:
            if not _is_placeholder_secret(key):
                item['api_key'] = str(key)
                break
        salida.append(item)
    return salida


def get_groq_api_key(root: Path | None = None) -> str | None:
    root = root or ROOT
    load_local_env(root)
    # 1. Variables de entorno globales
    for key in ['GROQ_API_KEY', 'GROQ_KEY']:
        val = os.getenv(key)
        if val and not _is_placeholder_secret(val):
            return str(val).strip()
    # 2. cuentas.json
    accounts = get_groq_accounts(root)
    for acc in accounts:
        key = acc.get('api_key')
        if not _is_placeholder_secret(key):
            return str(key).strip()
    return None


def get_tokenrouter_accounts(root: Path | None = None) -> list[dict[str, Any]]:
    root = root or ROOT
    load_local_env(root)
    cuentas = _read_json(root / 'cuentas.json').get('proveedores', {}).get('tokenrouter', {}).get('cuentas', [])
    salida: list[dict[str, Any]] = []
    for idx, acc in enumerate(cuentas, 1):
        if not isinstance(acc, dict):
            continue
        item = dict(acc)
        account_id = str(item.get('id', '')).strip()
        candidatos = [
            item.get('api_key'),
            os.getenv(f'TOKENROUTER_API_KEY_{_norm_env_suffix(account_id)}') if account_id else None,
            os.getenv(f'TOKENROUTER_KEY_{_norm_env_suffix(account_id)}') if account_id else None,
            os.getenv(f'TOKENROUTER_API_KEY_{idx}'),
            os.getenv(f'TOKENROUTER_KEY_{idx}'),
            os.getenv('TOKENROUTER_API_KEY'),
            os.getenv('TOKENROUTER_KEY'),
        ]
        for key in candidatos:
            if not _is_placeholder_secret(key):
                item['api_key'] = str(key)
                break
        salida.append(item)
    return salida


def get_tokenrouter_api_key(root: Path | None = None) -> str | None:
    root = root or ROOT
    load_local_env(root)
    # 1. Variables de entorno globales
    for key in ['TOKENROUTER_API_KEY', 'TOKENROUTER_KEY']:
        val = os.getenv(key)
        if val and not _is_placeholder_secret(val):
            return str(val).strip()
    # 2. cuentas.json
    accounts = get_tokenrouter_accounts(root)
    for acc in accounts:
        key = acc.get('api_key')
        if not _is_placeholder_secret(key):
            return str(key).strip()
    return None


def get_xkiro_accounts(root: Path | None = None) -> list[dict[str, Any]]:
    root = root or ROOT
    load_local_env(root)
    cuentas = _read_json(root / 'cuentas.json').get('proveedores', {}).get('xkiro', {}).get('cuentas', [])
    salida: list[dict[str, Any]] = []
    for idx, acc in enumerate(cuentas, 1):
        if not isinstance(acc, dict):
            continue
        item = dict(acc)
        account_id = str(item.get('id', '')).strip()
        candidatos = [
            item.get('api_key'),
            os.getenv(f'XKIRO_API_KEY_{_norm_env_suffix(account_id)}') if account_id else None,
            os.getenv(f'XKIRO_API_KEY_{idx}'),
            os.getenv('XKIRO_API_KEY'),
        ]
        for key in candidatos:
            if not _is_placeholder_secret(key):
                item['api_key'] = str(key).strip()
                break
        salida.append(item)
    return salida


def get_xkiro_api_key(root: Path | None = None) -> str | None:
    for acc in get_xkiro_accounts(root):
        key = acc.get('api_key')
        if not _is_placeholder_secret(key):
            return str(key).strip()
    return None


def get_tokenharbor_accounts(root: Path | None = None) -> list[dict[str, Any]]:
    root = root or ROOT
    load_local_env(root)
    cuentas = _read_json(root / 'cuentas.json').get('proveedores', {}).get('tokenharbor', {}).get('cuentas', [])
    salida: list[dict[str, Any]] = []
    for idx, acc in enumerate(cuentas, 1):
        if not isinstance(acc, dict):
            continue
        item = dict(acc)
        account_id = str(item.get('id', '')).strip()
        candidatos = [
            item.get('api_key'),
            os.getenv(f'TOKENHARBOR_API_KEY_{_norm_env_suffix(account_id)}') if account_id else None,
            os.getenv(f'TOKENHARBOR_API_KEY_{idx}'),
            os.getenv('TOKENHARBOR_API_KEY'),
        ]
        for key in candidatos:
            if not _is_placeholder_secret(key):
                item['api_key'] = str(key).strip()
                break
        salida.append(item)
    return salida


def get_tokenharbor_api_key(root: Path | None = None) -> str | None:
    for acc in get_tokenharbor_accounts(root):
        key = acc.get('api_key')
        if not _is_placeholder_secret(key):
            return str(key).strip()
    return None
