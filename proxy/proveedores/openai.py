"""Proveedor OpenAI para la API estándar mediante clave API.

OAuth no se mezcla aquí: este adaptador solo acepta una clave API almacenada
por el gestor de cuentas.
"""
from __future__ import annotations

import os

from proxy.proveedores.base import ProveedorBase

URL_BASE_OPENAI = "https://api.openai.com/v1/chat/completions"


def _sufijo(value: str) -> str:
    return ''.join(ch if ch.isalnum() else '_' for ch in str(value).upper()).strip('_')


def _resolve_api_key(cuenta) -> str:
    account_id = str(cuenta.get('id', ''))
    values = [
        cuenta.get('api_key'),
        os.getenv(f'OPENAI_API_KEY_{_sufijo(account_id)}'),
        os.getenv('OPENAI_API_KEY'),
    ]
    return next((str(x).strip() for x in values if str(x or '').strip()), '')


class ProveedorOpenAI(ProveedorBase):
    def __init__(self, cuenta):
        super().__init__(cuenta)
        self.api_key = _resolve_api_key(cuenta)
        self.url_base = cuenta.get('url_base', URL_BASE_OPENAI)

    def construir_url(self):
        return self.url_base

    def construir_headers(self):
        return {'Content-Type': 'application/json', 'Authorization': f'Bearer {self.api_key}'}

    def tiene_credencial_valida(self):
        return bool(self.api_key)

    def identificar(self):
        corto = self.api_key[-6:] if len(self.api_key) > 6 else '***'
        return f'openai:{self.id_cuenta}(***{corto})'
