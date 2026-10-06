"""Paquete local para trasladar cuentas API entre instalaciones de Núcleo IA."""
from __future__ import annotations

import io
import json
import os
import re
import zipfile
from pathlib import Path

from scripts.secret_utils import _parse_env_file, _is_placeholder_secret
from scripts.servicios_backend import escribir_atomico, escribir_json, ErrorUsuario

MAX_ARCHIVE = 2_000_000
MAX_JSON = 1_500_000
SECRET_NAME = re.compile(r"(?:API_KEY|_TOKEN|_ACCOUNT_ID|^NVIDIA_KEY)(?:_[A-Z0-9_]+)?$")
SECRET_FIELDS = {'api_key', 'token', 'auth_token', 'secret', 'secret_key', 'api_secret', 'password'}


def crear_paquete(root: Path) -> bytes:
    cuentas_path = root / 'cuentas.json'
    try:
        cuentas = json.loads(cuentas_path.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        raise ErrorUsuario('No se pudieron leer las cuentas de esta computadora.')
    if not isinstance(cuentas, dict) or not isinstance(cuentas.get('proveedores'), dict):
        raise ErrorUsuario('El archivo de cuentas no tiene un formato válido.')
    def public_metadata(value):
        if isinstance(value, dict):
            return {k: public_metadata(v) for k, v in value.items() if str(k).lower() not in SECRET_FIELDS}
        if isinstance(value, list):
            return [public_metadata(item) for item in value]
        return value
    cuentas = public_metadata(cuentas)
    env = {}
    for filename in ('.env', 'granja.env'):
        for name, value in _parse_env_file(root / filename).items():
            if SECRET_NAME.search(name) and not _is_placeholder_secret(value):
                env[name] = value
    payload = json.dumps({'formato': 1, 'cuentas': cuentas, 'claves': env}, ensure_ascii=False).encode('utf-8')
    if len(payload) > MAX_JSON:
        raise ErrorUsuario('El paquete de cuentas es demasiado grande para trasladarlo desde el panel.')
    buff = io.BytesIO()
    with zipfile.ZipFile(buff, 'w', zipfile.ZIP_DEFLATED) as archive:
        archive.writestr('transferencia.json', payload)
    return buff.getvalue()


def _leer_paquete(raw: bytes) -> dict:
    if not raw or len(raw) > MAX_ARCHIVE:
        raise ErrorUsuario('El archivo no es válido o supera el tamaño permitido (2 MB).')
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            entries = archive.infolist()
            if len(entries) != 1 or entries[0].filename != 'transferencia.json' or entries[0].file_size > MAX_JSON:
                raise ValueError()
            payload = json.loads(archive.read(entries[0]))
    except (zipfile.BadZipFile, KeyError, ValueError, OSError, UnicodeError):
        raise ErrorUsuario('No se reconoce este paquete de cuentas de Núcleo IA.')
    if not isinstance(payload, dict) or payload.get('formato') != 1:
        raise ErrorUsuario('La versión del paquete no es compatible.')
    cuentas = payload.get('cuentas')
    claves = payload.get('claves')
    if not isinstance(cuentas, dict) or not isinstance(cuentas.get('proveedores'), dict) or not isinstance(claves, dict):
        raise ErrorUsuario('El paquete está incompleto o dañado.')
    if len(claves) > 500 or any(not isinstance(k, str) or not SECRET_NAME.search(k) or not isinstance(v, str) or len(v) > 10000 or '\n' in v or '\r' in v or '\x00' in v for k, v in claves.items()):
        raise ErrorUsuario('El paquete contiene datos de claves no válidos.')
    return payload


def sumar_paquete(root: Path, raw: bytes) -> dict:
    payload = _leer_paquete(raw)
    cuenta_path, env_path = root / 'cuentas.json', root / '.env'
    try:
        actual = json.loads(cuenta_path.read_text(encoding='utf-8')) if cuenta_path.exists() else {'proveedores': {}, 'orden_failover': [], 'mapeo_modelos': {}, 'pozo_emails': []}
        if not isinstance(actual, dict) or not isinstance(actual.get('proveedores'), dict):
            raise ValueError()
        env_text = env_path.read_text(encoding='utf-8') if env_path.exists() else ''
    except (OSError, ValueError):
        raise ErrorUsuario('No se pudieron leer las cuentas actuales; no se cambió nada.')

    cuentas_agregadas = 0
    entrantes = payload['cuentas']
    for proveedor, seccion in entrantes['proveedores'].items():
        if not isinstance(proveedor, str) or not isinstance(seccion, dict) or not isinstance(seccion.get('cuentas', []), list):
            raise ErrorUsuario('Hay una cuenta con formato inválido; no se cambió nada.')
        local = actual['proveedores'].setdefault(proveedor, {})
        locales = local.setdefault('cuentas', [])
        if not isinstance(locales, list):
            raise ErrorUsuario('Las cuentas actuales tienen un formato que no se puede combinar.')
        ids = {str(row.get('id')) for row in locales if isinstance(row, dict)}
        for row in seccion.get('cuentas', []):
            if not isinstance(row, dict) or not row.get('id'):
                continue
            if str(row['id']) not in ids:
                locales.append(row)
                ids.add(str(row['id']))
                cuentas_agregadas += 1
    orden = actual.setdefault('orden_failover', [])
    if isinstance(orden, list):
        for proveedor in entrantes.get('orden_failover', []):
            if proveedor in actual['proveedores'] and proveedor not in orden:
                orden.append(proveedor)
    for key in ('mapeo_modelos',):
        if key not in actual and isinstance(entrantes.get(key), dict):
            actual[key] = entrantes[key]
    emails = actual.setdefault('pozo_emails', [])
    if isinstance(emails, list):
        for email in entrantes.get('pozo_emails', []):
            if isinstance(email, str) and email not in emails:
                emails.append(email)

    env_actual = _parse_env_file(env_path)
    for name, value in _parse_env_file(root / 'granja.env').items():
        env_actual.setdefault(name, value)
    nuevas = {k: v for k, v in payload['claves'].items() if _is_placeholder_secret(env_actual.get(k))}
    conflictos = len(payload['claves']) - len(nuevas)
    if nuevas:
        lines = env_text.splitlines()
        present = {line.strip().removeprefix('export ').split('=', 1)[0].strip() for line in lines if '=' in line and not line.lstrip().startswith('#')}
        lines.extend(f'{k}={v}' for k, v in nuevas.items() if k not in present)
        # Para una variable existente vacía/plantilla, reemplazarla con la clave importada.
        for key, value in nuevas.items():
            for i, line in enumerate(lines):
                if line.strip().removeprefix('export ').split('=', 1)[0].strip() == key:
                    lines[i] = f'{key}={value}'
                    break
        env_text = '\n'.join(lines).rstrip() + '\n'

    # Escribir ambos archivos de forma atómica; conservar copias privadas para poder deshacer.
    backup_dir = root / 'state' / 'config_backups'
    backup_dir.mkdir(parents=True, exist_ok=True)
    if os.name != 'nt': backup_dir.chmod(0o700)
    import time
    stamp = time.strftime('%Y%m%d-%H%M%S')
    for path in (cuenta_path, env_path):
        if path.exists():
            backup = backup_dir / f'{path.name.lstrip(".")}-antes-traslado-{stamp}.bak'
            if os.name != 'nt': backup.touch(mode=0o600, exist_ok=True)
            backup.write_bytes(path.read_bytes())
            if os.name != 'nt': backup.chmod(0o600)
    escribir_json(cuenta_path, actual)
    escribir_atomico(env_path, env_text)
    if os.name != 'nt':
        cuenta_path.chmod(0o600)
        env_path.chmod(0o600)
    return {'cuentas_agregadas': cuentas_agregadas, 'claves_agregadas': len(nuevas), 'claves_ya_existentes': conflictos}
