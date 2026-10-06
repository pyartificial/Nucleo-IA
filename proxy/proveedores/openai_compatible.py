"""Adaptador para proveedores con endpoint de chat compatible con OpenAI."""
from __future__ import annotations

import os
from pathlib import Path
from proxy.proveedores.base import ProveedorBase
from scripts.secret_utils import _parse_env_file, _is_placeholder_secret

CONFIG = {
    'deepseek': ('https://api.deepseek.com/chat/completions', 'DEEPSEEK_API_KEY'),
    'grok': ('https://api.x.ai/v1/chat/completions', 'XAI_API_KEY'),
    'minimax': ('https://api.minimax.io/v1/chat/completions', 'MINIMAX_API_KEY'),
    'alibaba': ('https://dashscope-intl.aliyuncs.com/compatible-mode/v1/chat/completions', 'DASHSCOPE_API_KEY'),
    'cerebras': ('https://api.cerebras.ai/v1/chat/completions', 'CEREBRAS_API_KEY'),
    'mistral': ('https://api.mistral.ai/v1/chat/completions', 'MISTRAL_API_KEY'),
    'agnes': ('https://apihub.agnes-ai.com/v1/chat/completions', 'AGNES_API_KEY'),
    'aion': ('https://api.aionlabs.ai/v1/chat/completions', 'AION_API_KEY'),
    'airforce': ('https://api.airforce/v1/chat/completions', 'AIRFORCE_API_KEY'),
    'anyapi': ('https://api.anyapi.ai/v1/chat/completions', 'ANYAPI_API_KEY'),
    'bazaarlink': ('https://api.bazaarlink.ai/v1/chat/completions', 'BAZAARLINK_API_KEY'),
    'dreamprompting': ('https://dreamprompting.com/api/v1/chat/completions', 'DREAMPROMPTING_API_KEY'),
    'huggingface': ('https://router.huggingface.co/v1/chat/completions', 'HF_TOKEN'),
    'orcarouter': ('https://api.orcarouter.ai/v1/chat/completions', 'ORCAROUTER_API_KEY'),
    'requesty': ('https://router.requesty.ai/v1/chat/completions', 'REQUESTY_API_KEY'),
    'routeway': ('https://api.routeway.ai/v1/chat/completions', 'ROUTEWAY_API_KEY'),
    'sealion': ('https://api.sea-lion.ai/v1/chat/completions', 'SEALION_API_KEY'),
    'unorouter': ('https://api.unorouter.com/v1/chat/completions', 'UNOROUTER_API_KEY'),
    'ollama_cloud_api': ('https://ollama.com/v1/chat/completions', 'OLLAMA_API_KEY'),
}


def _suffix(value):
    return ''.join(c if c.isalnum() else '_' for c in str(value).upper()).strip('_')


class ProveedorOpenAICompatible(ProveedorBase):
    def __init__(self, cuenta):
        super().__init__(cuenta)
        self.proveedor = str(cuenta.get('proveedor', cuenta.get('provider', ''))).lower()
        base, env = CONFIG.get(self.proveedor, ('', ''))
        self.env_name = env
        self.url_base = cuenta.get('url_base', base)
        self.api_key = str(cuenta.get('api_key') or self._cuenta_key(env) or '').strip()

    def _cuenta_key(self, env):
        suffix = _suffix(self.id_cuenta)
        names = (f'{env}_{suffix}',)
        for filename in ('.env', 'granja.env'):
            for name, value in _parse_env_file(Path(__file__).resolve().parents[2] / filename).items():
                if name in names and not _is_placeholder_secret(value):
                    return value
        return os.getenv(names[0], '')

    def construir_url(self):
        return self.url_base

    def construir_headers(self):
        headers = {'Content-Type': 'application/json', 'Authorization': f'Bearer {self.api_key}'}
        if self.proveedor == 'mistral':
            headers['Accept'] = 'application/json'
        if self.proveedor == 'bazaarlink':
            headers['X-Free-Fallback'] = 'false'
        return headers

    def preparar_body(self, body, modelo):
        body_copia = dict(body)
        body_copia['model'] = modelo
        return body_copia

    def tiene_credencial_valida(self):
        return bool(self.api_key and self.url_base)

    def identificar(self):
        corto = self.api_key[-6:] if len(self.api_key) > 6 else '***'
        return f'{self.proveedor}:{self.id_cuenta}(***{corto})'
