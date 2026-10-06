"""Recarga de cuentas, autorizada únicamente por el asistente de esta copia."""
from __future__ import annotations

import hmac
import json
import os
from pathlib import Path

RUTA_RECARGA = '/internal/mis-servicios/recargar'


def autorizar_recarga(cliente, token, root):
    if cliente not in {'127.0.0.1', '::1'} or not token:
        return False
    try:
        data = json.loads((Path(root) / 'state' / 'mis_servicios_runtime.json').read_text(encoding='utf-8'))
        expected = data.get('token', '')
        return isinstance(expected, str) and len(expected) >= 32 and hmac.compare_digest(token, expected)
    except (OSError, ValueError, TypeError):
        return False


def recargar(root):
    from proxy.configuracion import _leer_env, recargar_configuracion
    from proxy import rotador_cuentas
    from scripts.servicios_backend import VARIABLES
    config = _leer_env(Path(root) / 'granja.env')
    config.update(_leer_env(Path(root) / '.env'))
    permitidas = [v for values in VARIABLES.values() for v in values] + ['CLOUDFLARE_ACCOUNT_ID']
    # Leer y validar el JSON antes de tocar la configuración en memoria.
    data = json.loads((Path(root) / 'cuentas.json').read_text(encoding='utf-8'))
    if not isinstance(data.get('proveedores', {}), dict):
        raise ValueError('Configuración de cuentas inválida')
    with rotador_cuentas._lock:
        recargar_configuracion()
        for name, value in config.items():
            if name == 'SERVICIOS_ACTIVOS' or any(name == p or name.startswith(p + '_') for p in permitidas):
                os.environ[name] = value
        rotador_cuentas.cargar_cuentas()
        # Una clave recién comprobada puede resolver un bloqueo por falta de
        # credencial. Conservar límites, saldo y bloqueos por otros motivos.
        changed = False
        for section in data.get('proveedores', {}).values():
            for account in section.get('cuentas', []):
                state = rotador_cuentas._estados.get(account.get('id'), {})
                if account.get('conexion_estado') == 'acceso_comprobado' and str(state.get('razon', '')).endswith('_key_invalida'):
                    state.update(estado='activa', bloqueado_hasta=None, razon=None)
                    changed = True
        if changed:
            rotador_cuentas._guardar_estados()
    return {'aplicado': True}
