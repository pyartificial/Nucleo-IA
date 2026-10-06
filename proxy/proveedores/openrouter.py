"""
Proveedor OpenRouter — API cloud con autenticación Bearer.
Endpoint: https://openrouter.ai/api/v1/chat/completions
"""
from __future__ import annotations

import os
from pathlib import Path

from proxy.proveedores.base import ProveedorBase

URL_BASE_OPENROUTER = "https://openrouter.ai/api/v1/chat/completions"
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
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        data[key] = value
    return data


def _looks_like_secret(value: object) -> bool:
    if not value:
        return False
    text = str(value).strip()
    if not text:
        return False
    if text.startswith('TU_'):
        return False
    if text.startswith('<') and text.endswith('>'):
        return False
    if '...' in text:
        return False
    return True


def _looks_like_valid_openrouter_key(value: object) -> bool:
    if not _looks_like_secret(value):
        return False
    text = str(value).strip()
    if not text.startswith('sk-or-v1'):
        return False
    if len(text) < 50:
        return False
    upper = text.upper()
    if 'PLACEHOLDER' in upper or upper.endswith('_KEY'):
        return False
    return True


def _load_local_env() -> None:
    for filename in ('.env', 'granja.env'):
        for key, value in _parse_env_file(ROOT / filename).items():
            os.environ.setdefault(key, value)


def _env_suffix(text: str) -> str:
    return ''.join(ch if ch.isalnum() else '_' for ch in str(text).upper()).strip('_')


def _resolve_api_key(cuenta) -> str:
    _load_local_env()
    account_id = cuenta.get('id', '')
    candidatos = [
        cuenta.get('api_key'),
        os.getenv(f'OPENROUTER_API_KEY_{_env_suffix(account_id)}'),
        os.getenv('OPENROUTER_API_KEY'),
    ]
    if account_id and account_id[-1].isdigit():
        candidatos.append(os.getenv(f'OPENROUTER_API_KEY_{account_id[-1]}'))
    for key in candidatos:
        if _looks_like_valid_openrouter_key(key):
            return str(key)
    return ''


class ProveedorOpenRouter(ProveedorBase):
    """Conecta con la API de OpenRouter usando API keys."""

    def __init__(self, cuenta):
        super().__init__(cuenta)
        self.api_key = _resolve_api_key(cuenta)
        self.url_base = cuenta.get("url_base", URL_BASE_OPENROUTER)
        self.nombre_app = cuenta.get("nombre_app", "LaGranjaDeIA")
        self.url_app = cuenta.get("url_app", "")

    def construir_url(self):
        return self.url_base

    def construir_headers(self):
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
            "X-Title": self.nombre_app,
        }
        if self.url_app:
            headers["HTTP-Referer"] = self.url_app
        return headers

    def preparar_body(self, body, modelo):
        """OpenRouter usa el formato estándar OpenAI."""
        body_copia = dict(body)
        body_copia["model"] = modelo
        return body_copia

    def tiene_credencial_valida(self):
        return bool(self.api_key)

    def identificar(self):
        key_corta = self.api_key[-6:] if len(self.api_key) > 6 else "***"
        return f"openrouter:{self.id_cuenta}(***{key_corta})"
