"""
Proveedor Zhipu AI (BigModel) — API cloud con autenticación Bearer.
Endpoint OpenAI-compatible.
"""
from __future__ import annotations

import os
from pathlib import Path

from proxy.proveedores.base import ProveedorBase

URL_BASE_ZHIPU = "https://api.z.ai/api/paas/v4/chat/completions"
ROOT = Path(__file__).resolve().parents[2]


def _parse_env_file(path: Path) -> dict[str, str]:
    data: dict[str, str] = {}
    try:
        text = path.read_text(encoding='utf-8')
    except Exception:
        return data
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        if line.startswith('export '):
            line = line[7:].lstrip()
        key, value = line.split('=', 1)
        data[key.strip()] = value.strip().strip('"').strip("'")
    return data


def _looks_like_secret(value: object) -> bool:
    if not value:
        return False
    text = str(value).strip()
    return bool(text and not text.startswith('TU_') and not (text.startswith('<') and text.endswith('>')) and '...' not in text)


def _load_local_env() -> None:
    for filename in ('.env', 'granja.env'):
        for key, value in _parse_env_file(ROOT / filename).items():
            os.environ.setdefault(key, value)


def _env_suffix(text: str) -> str:
    return ''.join(ch if ch.isalnum() else '_' for ch in str(text).upper()).strip('_')


def _resolve_api_key(cuenta) -> str:
    _load_local_env()
    account_id = str(cuenta.get('id', '')).strip()
    candidatos = [
        cuenta.get('api_key'),
        os.getenv(f'ZHIPU_API_KEY_{_env_suffix(account_id)}') if account_id else None,
        os.getenv('ZHIPU_API_KEY'),
    ]
    for key in candidatos:
        if _looks_like_secret(key):
            return str(key)
    return ''


class ProveedorZhipu(ProveedorBase):
    """Conecta con Zhipu AI usando el endpoint OpenAI-compatible."""

    def __init__(self, cuenta):
        super().__init__(cuenta)
        self.api_key = _resolve_api_key(cuenta)
        self.nombre_app = cuenta.get('nombre_app', 'LaGranjaDeIA')

    def construir_url(self):
        return URL_BASE_ZHIPU

    def construir_headers(self):
        return {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {self.api_key}',
        }

    def tiene_credencial_valida(self):
        return bool(self.api_key)

    def identificar(self):
        key_corta = self.api_key[-6:] if len(self.api_key) > 6 else '***'
        return f'zhipu:{self.id_cuenta}(***{key_corta})'
