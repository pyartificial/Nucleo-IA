"""Adaptador nativo de Anthropic Messages API para solicitudes no streaming."""
from __future__ import annotations
import os
from proxy.proveedores.base import ProveedorBase

class ProveedorAnthropic(ProveedorBase):
    def __init__(self, cuenta):
        super().__init__(cuenta)
        suf = ''.join(c if c.isalnum() else '_' for c in self.id_cuenta.upper()).strip('_')
        self.api_key = str(cuenta.get('api_key') or os.getenv(f'ANTHROPIC_API_KEY_{suf}') or os.getenv('ANTHROPIC_API_KEY') or '').strip()
        self.url = cuenta.get('url_base', 'https://api.anthropic.com/v1/messages')

    def construir_url(self): return self.url
    def construir_headers(self):
        return {'content-type': 'application/json', 'x-api-key': self.api_key, 'anthropic-version': '2023-06-01'}
    def preparar_body(self, body, modelo):
        messages = body.get('messages', [])
        system = body.get('system')
        converted = []
        for item in messages:
            if item.get('role') == 'system':
                system = item.get('content', '')
            elif item.get('role') in ('user', 'assistant'):
                converted.append({'role': item['role'], 'content': item.get('content', '')})
        result = {'model': modelo, 'max_tokens': int(body.get('max_tokens', 1024)), 'messages': converted}
        if system: result['system'] = system
        if body.get('temperature') is not None: result['temperature'] = body['temperature']
        return result
    def normalizar_respuesta(self, data):
        text = ''.join(x.get('text', '') for x in data.get('content', []) if isinstance(x, dict) and x.get('type') == 'text')
        return {'id': data.get('id', 'anthropic-response'), 'object': 'chat.completion', 'model': data.get('model'),
                'choices': [{'index': 0, 'message': {'role': 'assistant', 'content': text}, 'finish_reason': data.get('stop_reason', 'stop')}],
                'usage': {'input_tokens': data.get('usage', {}).get('input_tokens', 0), 'output_tokens': data.get('usage', {}).get('output_tokens', 0)}}
    def tiene_credencial_valida(self): return bool(self.api_key)
    def identificar(self): return f'anthropic:{self.id_cuenta}(***{self.api_key[-6:] if len(self.api_key)>6 else "***"})'
