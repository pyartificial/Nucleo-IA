"""Operaciones del asistente, independientes de Windows/Linux y de la interfaz."""
from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import secrets
import socket
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from scripts.catalogo_servicios import SERVICIOS, SERVICIOS_OPCIONALES, POR_ID
from scripts.gestor_cuentas import norm_id
from scripts.secret_utils import _parse_env_file, _is_placeholder_secret

VARIABLES = {
    'openai': ['OPENAI_API_KEY'], 'anthropic': ['ANTHROPIC_API_KEY'], 'minimax': ['MINIMAX_API_KEY'],
    'alibaba': ['DASHSCOPE_API_KEY'], 'deepseek': ['DEEPSEEK_API_KEY'], 'grok': ['XAI_API_KEY'],
    'treblo': ['TREBLO_API_KEY'], 'stable_audio': ['STABLE_AUDIO_API_KEY'], 'mubert': ['MUBERT_API_KEY'],
    'soundraw': ['SOUNDRAW_API_KEY'], 'beatoven': ['BEATOVEN_API_KEY'],
    'groq': ['GROQ_API_KEY'], 'openrouter': ['OPENROUTER_API_KEY'],
    'nvidia': ['NVIDIA_API_KEY', 'NVIDIA_KEY'], 'google': ['GOOGLE_API_KEY', 'GEMINI_API_KEY'],
    'cloudflare': ['CLOUDFLARE_API_TOKEN'], 'cohere': ['COHERE_API_KEY'],
    'siliconflow': ['SILICONFLOW_API_KEY'], 'zhipu': ['ZHIPU_API_KEY'],
    'tokenrouter': ['TOKENROUTER_API_KEY'], 'xkiro': ['XKIRO_API_KEY'], 'tokenharbor': ['TOKENHARBOR_API_KEY'], 'apinex': ['APINEX_API_KEY'],
    'elevenlabs': ['ELEVENLABS_API_KEY'],
    'speechify': ['SPEECHIFY_API_KEY'],
    'cerebras': ['CEREBRAS_API_KEY'], 'mistral': ['MISTRAL_API_KEY'],
    'agnes': ['AGNES_API_KEY'], 'aion': ['AION_API_KEY'], 'airforce': ['AIRFORCE_API_KEY'],
    'anyapi': ['ANYAPI_API_KEY'], 'bazaarlink': ['BAZAARLINK_API_KEY'],
    'dreamprompting': ['DREAMPROMPTING_API_KEY'], 'huggingface': ['HF_TOKEN'],
    'orcarouter': ['ORCAROUTER_API_KEY'], 'requesty': ['REQUESTY_API_KEY'],
    'routeway': ['ROUTEWAY_API_KEY'], 'sealion': ['SEALION_API_KEY'],
    'unorouter': ['UNOROUTER_API_KEY'], 'ollama_cloud_api': ['OLLAMA_API_KEY'],
}
ENDPOINTS = {
    'groq': 'https://api.groq.com/openai/v1/models',
    'openrouter': 'https://openrouter.ai/api/v1/key',
    'nvidia': 'https://integrate.api.nvidia.com/v1/models',
    'google': 'https://generativelanguage.googleapis.com/v1beta/models?pageSize=1',
    'cohere': 'https://api.cohere.com/v1/check-api-key',
    'siliconflow': 'https://api.siliconflow.com/v1/user/info',
    'zhipu': 'https://api.z.ai/api/paas/v4/models',
    'tokenrouter': 'https://api.tokenrouter.com/v1/models',
    'xkiro': 'https://api.xkiro.com/v1/models',
    'tokenharbor': 'https://tokenharbor.ai/v1/models', 'apinex': 'https://api.apinex.bond/v1/models',
    'elevenlabs': 'https://api.elevenlabs.io/v1/user',
    'speechify': 'https://api.speechify.ai/v1/workspaces/current/entitlements',
    'cerebras': 'https://api.cerebras.ai/v1/models',
    'mistral': 'https://api.mistral.ai/v1/models',
    'minimax': 'https://api.minimax.io/v1/models',
    'deepseek': 'https://api.deepseek.com/models', 'grok': 'https://api.x.ai/v1/models',
    'alibaba': 'https://dashscope-intl.aliyuncs.com/compatible-mode/v1/models',
    'agnes': 'https://apihub.agnes-ai.com/v1/models',
    'aion': 'https://api.aionlabs.ai/v1/models',
    'airforce': 'https://api.airforce/v1/models?channels=1',
    'anyapi': 'https://api.anyapi.ai/v1/models',
    'bazaarlink': 'https://api.bazaarlink.ai/v1/models?output_modalities=all',
    'dreamprompting': 'https://dreamprompting.com/api/v1/models',
    'huggingface': 'https://router.huggingface.co/v1/models',
    'orcarouter': 'https://api.orcarouter.ai/v1/models',
    'requesty': 'https://router.requesty.ai/v1/models',
    'routeway': 'https://api.routeway.ai/v1/models',
    'sealion': 'https://api.sea-lion.ai/v1/models',
    'unorouter': 'https://api.unorouter.com/v1/models',
    'ollama_cloud_api': 'https://ollama.com/v1/models',
}
OPENAI_COMPATIBLE = {
    'agnes', 'aion', 'airforce', 'anyapi', 'bazaarlink', 'dreamprompting',
    'huggingface', 'orcarouter', 'requesty', 'routeway', 'sealion',
    'unorouter', 'ollama_cloud_api',
}


class ErrorUsuario(Exception):
    pass


def leer_json(path, default=None):
    try:
        data = json.loads(Path(path).read_text(encoding='utf-8'))
        if not isinstance(data, dict):
            raise ValueError()
        return data
    except FileNotFoundError:
        return {} if default is None else default
    except (ValueError, OSError):
        raise ErrorUsuario('No se pudo leer la configuración. No se sobrescribió; pedí ayuda para revisarla.')


def escribir_atomico(path, text):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix='.' + path.name + '.', dir=path.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8', newline='\n') as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def escribir_json(path, data):
    escribir_atomico(path, json.dumps(data, ensure_ascii=False, indent=2) + '\n')


def modificar_env(text, valores):
    restantes = dict(valores)
    out = []
    for linea in text.splitlines():
        nombre = linea.strip().removeprefix('export ').split('=', 1)[0].strip()
        if nombre in valores:
            if nombre in restantes:
                out.append(f'{nombre}={restantes.pop(nombre)}')
        else:
            out.append(linea)
    out.extend(f'{k}={v}' for k, v in restantes.items())
    return '\n'.join(out) + '\n'


class SinRedireccion(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None  # Una clave nunca sigue una redirección a otro destino.


def peticion_json(url, key='', metodo='GET', payload=None, google=False, timeout=12, header_name='Authorization', extra_headers=None):
    headers = {'Accept': 'application/json', 'User-Agent': 'NucleoIA-MisServicios/1'}
    if key:
        if google:
            headers['x-goog-api-key'] = key
        elif header_name == 'xi-api-key':
            headers['xi-api-key'] = key
        else:
            headers[header_name] = 'Bearer ' + key
    if extra_headers:
        headers.update({str(k): str(v) for k, v in extra_headers.items()})
    data = None if payload is None else json.dumps(payload).encode()
    if data is not None:
        headers['Content-Type'] = 'application/json'
    req = urllib.request.Request(url, data=data, headers=headers, method=metodo)
    try:
        with urllib.request.build_opener(urllib.request.ProxyHandler({}), SinRedireccion()).open(req, timeout=timeout) as r:
            body = r.read(2_000_001)
            if len(body) > 2_000_000:
                return r.status, {}
            try:
                parsed = json.loads(body)
                return r.status, parsed if isinstance(parsed, dict) else {}
            except (ValueError, UnicodeError):
                return r.status, {}
    except urllib.error.HTTPError as exc:
        return exc.code, {}  # No reenviar errores del proveedor: pueden contener secretos.
    except (OSError, urllib.error.URLError):
        return 0, {}


def resultado(estado, mensaje, verificada=False):
    return dict(estado=estado, mensaje=mensaje, verificada=verificada)


def validar_email(email, obligatorio=True):
    email = str(email or '').strip()
    if not email and not obligatorio:
        return ''
    if not re.fullmatch(r'[^\s@]{1,100}@[A-Za-z0-9._-]{1,150}\.[A-Za-z]{2,30}', email):
        raise ErrorUsuario('Escribí un correo válido para identificar esta cuenta. No uses la contraseña.')
    return email


def limpiar_cf_id(val: str) -> str:
    val = str(val or '').strip().strip('\'"')
    if not val:
        return ''
    m = re.search(r'[a-fA-F0-9]{32}', val)
    if m:
        return m.group(0).lower()
    return val


def comprobar_clave(proveedor, clave, account_id=''):
    url = ENDPOINTS.get(proveedor)
    if proveedor == 'cloudflare':
        url = f'https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/models/search?per_page=1'
    status, data = peticion_json(url, clave, 'POST' if proveedor == 'cohere' else 'GET',
                                {} if proveedor == 'cohere' else None, proveedor == 'google',
                                header_name='xi-api-key' if proveedor == 'elevenlabs' else 'Authorization',
                                extra_headers={'Speechify-Version': '2026-09-08'} if proveedor == 'speechify' else None)
    if status == 0:
        return resultado('sin_conexion', 'No pudimos contactar al servicio. Revisá Internet y volvé a intentar.')
    if status == 401:
        return resultado('clave_rechazada', 'El servicio no aceptó la clave. Copiala nuevamente desde su página oficial.')
    if status == 403:
        if isinstance(data, dict) and str(data.get('code', '')) == '1010':
            return resultado('servidor_bloqueado', 'APInex bloqueó temporalmente este origen (Cloudflare 1010). La cuenta y la clave no se marcaron como inválidas.')
        return resultado('sin_permiso', 'El servicio denegó el acceso. Revisá la clave, los permisos y la verificación de tu cuenta.')
    if status == 402:
        return resultado('sin_saldo', 'El servicio pide saldo o un plan habilitado. Revisá tu cuenta antes de continuar.')
    if status == 429:
        return resultado('limite', 'El servicio alcanzó un límite de uso. Esperá y probá nuevamente; no hace falta crear otra cuenta.')
    if status >= 500:
        return resultado('no_disponible', 'El servicio está teniendo un problema. Podés probar más tarde.')
    if status != 200 or not data or data.get('error') or data.get('success') is False:
        return resultado('sin_verificar', 'No se pudo confirmar el acceso con esta comprobación. Podés guardar la clave como pendiente.')
    if proveedor == 'cohere' and data.get('valid') is not True:
        return resultado('clave_rechazada', 'Cohere no confirmó que esta clave sea válida. Copiala nuevamente.')
    if proveedor == 'siliconflow' and data.get('code') not in (0, 20000):
        return resultado('sin_verificar', 'SiliconFlow no confirmó el acceso. Revisá que la cuenta sea de la plataforma .com.')
    if proveedor in ({'groq', 'nvidia', 'google', 'zhipu', 'tokenrouter', 'xkiro', 'tokenharbor', 'apinex', 'cloudflare', 'cerebras', 'mistral', 'deepseek', 'grok', 'alibaba', 'minimax'} | OPENAI_COMPATIBLE):
        # Algunos catálogos son públicos. Un 200 por sí solo no prueba autenticación.
        control, _ = peticion_json(url, 'nucleo-invalid-' + secrets.token_hex(12), google=proveedor == 'google')
        if control not in (400, 401, 403):
            return resultado('sin_verificar', 'La página de modelos respondió, pero no permite confirmar tu clave. Podés guardarla como pendiente.')
    if proveedor == 'openrouter' and not isinstance(data.get('data'), dict):
        return resultado('sin_verificar', 'OpenRouter no devolvió la información esperada de la clave.')
    if proveedor in ({'cerebras', 'mistral', 'deepseek', 'grok', 'minimax', 'alibaba'} | OPENAI_COMPATIBLE) and not (isinstance(data.get('data'), list) or isinstance(data.get('models'), list)):
        return resultado('sin_verificar', 'El servicio no devolvió el catálogo de modelos esperado. Podés guardar la clave como pendiente.')
    if proveedor == 'elevenlabs' and not data:
        return resultado('sin_verificar', 'ElevenLabs no devolvió los datos de la cuenta. Podés guardar la clave como pendiente.')
    if proveedor == 'speechify' and not data:
        return resultado('sin_verificar', 'Speechify no devolvió datos del espacio de trabajo. Podés guardar la cuenta como pendiente.')
    return resultado('acceso_comprobado', 'Acceso comprobado. La disponibilidad y el costo dependen del modelo y de tu cuota.', True)


class GestorServicios:
    def __init__(self, root):
        self.root = Path(root)
        self.lock = threading.RLock()
        self.oauth = {}
        self.proxy_process = None

    def config(self):
        data = _parse_env_file(self.root / 'granja.env')
        data.update(_parse_env_file(self.root / '.env'))
        return data

    def cuentas(self):
        data = leer_json(self.root / 'cuentas.json')
        if not isinstance(data.get('proveedores', {}), dict):
            raise ErrorUsuario('El archivo de cuentas necesita revisión. No se modificó.')
        return data

    def emails_conocidos(self):
        with self.lock:
            data = self.cuentas()
            prov = data.get('proveedores', {})
            encontrados = set()
            for s in prov.values():
                if isinstance(s, dict):
                    for c in s.get('cuentas', []):
                        if isinstance(c, dict) and c.get('email'):
                            mail = str(c.get('email', '')).strip()
                            if mail:
                                encontrados.add(mail)
            for mail in data.get('pozo_emails', []):
                if isinstance(mail, str) and mail.strip():
                    encontrados.add(mail.strip())
            return sorted(encontrados)

    def agregar_email_pozo(self, email):
        email = validar_email(email)
        with self.lock:
            data = self.cuentas()
            pozo = [str(m).strip() for m in data.get('pozo_emails', []) if isinstance(m, str) and m.strip()]
            if email not in pozo:
                pozo.append(email)
                data['pozo_emails'] = pozo
                escribir_json(self.root / 'cuentas.json', data)
            return dict(agregado=True, email=email, emails_conocidos=self.emails_conocidos())


    def lista(self):
        with self.lock:
            prov = self.cuentas().get('proveedores', {})
            rows = []
            for servicio in SERVICIOS:
                row = dict(servicio)
                cuentas = []
                for c in prov.get(servicio['id'], {}).get('cuentas', []):
                    if not isinstance(c, dict):
                        continue
                    account = dict(id=c.get('id'), nombre=c.get('nombre', c.get('id', 'Cuenta')),
                                   email=c.get('email', ''),
                                   voice_id=c.get('voice_id', '') if servicio['id'] == 'elevenlabs' else '',
                                   estado=c.get('conexion_estado', 'guardada'), fecha=c.get('conexion_fecha'))
                    if servicio.get('control_capacidades'):
                        account.update(habilitado=c.get('habilitado') is not False,
                                       uso_pago=bool(c.get('uso_pago', False)),
                                       primaria=bool(c.get('primaria', False)),
                                       capacidades_habilitadas=list(c.get('capacidades_habilitadas', ['speech_generation'])) if isinstance(c.get('capacidades_habilitadas', ['speech_generation']), list) else ['speech_generation'])
                    cuentas.append(account)
                row['cuentas'] = cuentas
                rows.append(row)
            pending = leer_json(self.root / 'state' / 'servicios_ollama_pendiente.json')
            return dict(servicios=rows, sistema='Windows' if sys.platform == 'win32' else 'Linux',
                        ollama_pendiente=bool(pending), emails_conocidos=self.emails_conocidos())

    def lista_opcionales(self):
        """Devuelve proveedores opcionales sin mezclarlos con el catálogo free."""
        with self.lock:
            prov = self.cuentas().get('proveedores', {})
            rows = []
            opcionales_chat = {'deepseek', 'grok', 'minimax', 'alibaba', 'cerebras'}
            catalogo_opcionales = [s for s in SERVICIOS_OPCIONALES if s['id'] not in opcionales_chat]
            catalogo_opcionales.extend(POR_ID[x] for x in sorted(opcionales_chat) if x in POR_ID)
            for servicio in catalogo_opcionales:
                row = dict(servicio)
                row['cuentas'] = [dict(id=c.get('id'), nombre=c.get('nombre', c.get('id', 'Cuenta')),
                                      email=c.get('email', ''),
                                      estado=c.get('conexion_estado', 'guardada'),
                                      fecha=c.get('conexion_fecha'),
                                      habilitado=bool(c.get('habilitado', True)),
                                      uso_pago=bool(c.get('uso_pago', False)),
                                      primaria=bool(c.get('primaria', False)),
                                      capacidades_habilitadas=list(c.get('capacidades_habilitadas', [])) if isinstance(c.get('capacidades_habilitadas', []), list) else [])
                                 for c in prov.get(servicio['id'], {}).get('cuentas', []) if isinstance(c, dict)]
                row['habilitado'] = bool(prov.get(servicio['id'], {}).get('habilitado', False))
                rows.append(row)
            return dict(servicios=rows)

    def configurar_opcional(self, body):
        proveedor = str(body.get('proveedor', '')).strip()
        controlados = {x['id'] for x in SERVICIOS if x.get('control_capacidades')}
        if proveedor not in {x['id'] for x in SERVICIOS_OPCIONALES} | {'deepseek', 'grok', 'minimax', 'alibaba', 'cerebras'} | controlados:
            raise ErrorUsuario('Proveedor opcional desconocido.')
        with self.lock:
            data = self.cuentas()
            prov = data.setdefault('proveedores', {}).setdefault(proveedor, {})
            cuentas = prov.setdefault('cuentas', [])
            account_id = str(body.get('id', '')).strip()
            if not account_id and 'habilitado' in body:
                prov['habilitado'] = body.get('habilitado') is True
            if account_id:
                cuenta = next((x for x in cuentas if x.get('id') == account_id), None)
                if not cuenta:
                    raise ErrorUsuario('La cuenta opcional no existe.')
                if 'uso_pago' in body:
                    cuenta['uso_pago'] = body.get('uso_pago') is True
                if 'primaria' in body:
                    for otra in cuentas:
                        otra['primaria'] = False
                    cuenta['primaria'] = body.get('primaria') is True
                if 'habilitado' in body:
                    cuenta['habilitado'] = body.get('habilitado') is True
                if 'capacidad' in body:
                    capacidad = str(body.get('capacidad', '')).strip()
                    permitidas = set(POR_ID[proveedor].get('capacidades_ids', []))
                    if capacidad not in permitidas:
                        raise ErrorUsuario('Esa capacidad no pertenece al proveedor.')
                    implementadas = POR_ID[proveedor].get('adaptadores_implementados')
                    if isinstance(implementadas, list) and capacidad not in implementadas:
                        raise ErrorUsuario('Esa capacidad está catalogada, pero todavía no tiene un adaptador utilizable en Núcleo IA.')
                    activas = {str(x) for x in cuenta.get('capacidades_habilitadas', []) if str(x) in permitidas}
                    if body.get('capacidad_habilitada') is True:
                        activas.add(capacidad)
                    else:
                        activas.discard(capacidad)
                    cuenta['capacidades_habilitadas'] = sorted(activas)
            escribir_json(self.root / 'cuentas.json', data)
            return self.lista_opcionales()

    def clave_guardada(self, proveedor, cuenta):
        env = self.config()
        suf = norm_id(cuenta['id'])
        index = next((i for i, c in enumerate(self.cuentas().get('proveedores', {}).get(proveedor, {}).get('cuentas', []), 1)
                      if c.get('id') == cuenta['id']), 1)
        candidatos = [f'{v}_{suf}' for v in VARIABLES[proveedor]]
        candidatos += [f'{v}_{index}' for v in VARIABLES[proveedor]] + VARIABLES[proveedor]
        for name in candidatos:
            if not _is_placeholder_secret(env.get(name)):
                return env[name]
        return ''

    def buscar(self, proveedor, account_id):
        return next((c for c in self.cuentas().get('proveedores', {}).get(proveedor, {}).get('cuentas', [])
                     if c.get('id') == account_id), None)

    def nuevo_id(self, proveedor):
        ids = {str(c.get('id')) for s in self.cuentas().get('proveedores', {}).values() for c in s.get('cuentas', [])}
        i = 1
        while f'{proveedor}_{i}' in ids:
            i += 1
        return f'{proveedor}_{i}'

    def validar(self, proveedor, clave, cf_id=''):
        if proveedor not in VARIABLES:
            raise ErrorUsuario('Elegí uno de los servicios de la lista.')
        if not isinstance(clave, str) or not re.fullmatch(r'[A-Za-z0-9._~+/=\-]{8,4096}', clave):
            raise ErrorUsuario('Pegá la clave completa, sin espacios ni comillas. No escribas tu contraseña.')
        cf_id = limpiar_cf_id(cf_id)
        if proveedor == 'cloudflare' and not re.fullmatch(r'[a-fA-F0-9]{32}', cf_id):
            raise ErrorUsuario('El identificador de Cloudflare debe tener 32 letras y números. No es tu correo.')
        if proveedor in {'xkiro', 'tokenharbor'}:
            prefijo = 'sk-xt-' if proveedor == 'xkiro' else 'thk_'
            if not clave.startswith(prefijo) or len(clave) < 32:
                raise ErrorUsuario(f'La clave de {POR_ID[proveedor]["nombre"]} debe empezar con {prefijo}. Copiala completa.')
        if proveedor == 'openrouter':
            from proxy.proveedores.openrouter import _looks_like_valid_openrouter_key
            if not _looks_like_valid_openrouter_key(clave):
                raise ErrorUsuario('Copiá la clave completa de OpenRouter; comienza con sk-or-v1 y tiene al menos 50 caracteres.')

    def guardar(self, proveedor, clave='', nombre='', cf_id='', account_id='', check=None, email='', voice_id=''):
        cf_id = limpiar_cf_id(cf_id)
        with self.lock:
            cuenta = self.buscar(proveedor, account_id) if account_id else None
            if account_id and not cuenta:
                raise ErrorUsuario('Esa cuenta ya no está en la lista. Volvé a Mis servicios.')
            if proveedor in {'deepseek', 'grok', 'minimax', 'alibaba', 'cerebras', 'mistral'} and account_id and not clave:
                cuenta['habilitado'] = True
            if account_id and not clave:
                clave_actual = self.clave_guardada(proveedor, cuenta)
                if not clave_actual:
                    raise ErrorUsuario('Falta la clave de esta cuenta. Ingresala para continuar.')
                if proveedor == 'cloudflare' and cf_id and not re.fullmatch(r'[a-fA-F0-9]{32}', cf_id):
                    raise ErrorUsuario('El identificador de Cloudflare debe tener 32 letras y números. No es tu correo.')
            else:
                self.validar(proveedor, clave, cf_id)

            email = validar_email(email, obligatorio=cuenta is None and proveedor not in {'elevenlabs', 'speechify'})
            if cuenta and not email:
                email = str(cuenta.get('email', '')).strip()
            if not email and not cuenta and proveedor not in {'elevenlabs', 'speechify'}:
                raise ErrorUsuario('Falta el correo asociado a esta cuenta.')

            cuentas_prov = self.cuentas().get('proveedores', {}).get(proveedor, {}).get('cuentas', [])
            for c in cuentas_prov:
                if isinstance(c, dict) and c.get('id') != account_id:
                    if email and str(c.get('email', '')).strip().lower() == email.lower():
                        nom = c.get('nombre') or c.get('id')
                        raise ErrorUsuario(f'El correo {email} ya está registrado en otra cuenta de {POR_ID[proveedor]["nombre"]} ({nom}). Usá un correo distinto para no repetir cuentas.')

            account_id = account_id or self.nuevo_id(proveedor)
            suf = norm_id(account_id)
            vals = {}
            if clave:
                vals = {f'{v}_{suf}': clave for v in VARIABLES[proveedor]}
                # Compatibilidad con scripts que consultan una única clave del proveedor.
                vals.update({v: clave for v in VARIABLES[proveedor]})
                if proveedor == 'cloudflare':
                    vals[f'CLOUDFLARE_ACCOUNT_ID_{suf}'] = cf_id
                    vals['CLOUDFLARE_ACCOUNT_ID'] = cf_id

            row = dict(cuenta or {}, id=account_id, nombre=str(nombre or (cuenta or {}).get('nombre') or POR_ID[proveedor]['nombre'])[:80])
            row['nombre_app'] = 'NucleoIA'
            row['email'] = email
            if proveedor in {'deepseek', 'grok', 'minimax', 'alibaba', 'cerebras', 'mistral'}:
                row.setdefault('habilitado', True)
            if proveedor == 'cloudflare':
                if cf_id:
                    row['account_id'] = cf_id
                elif cuenta and cuenta.get('account_id'):
                    row['account_id'] = cuenta.get('account_id')
            if proveedor == 'tokenharbor':
                row['solo_free'] = True
            if proveedor == 'elevenlabs':
                voz = str(voice_id or row.get('voice_id', '')).strip()
                if voz:
                    row['voice_id'] = voz[:160]
                    vals['ELEVENLABS_VOICE_ID'] = voz[:160]
                row.setdefault('habilitado', True)
                row.setdefault('uso_pago', False)
                row.setdefault('capacidades_habilitadas', ['speech_generation'])
            if proveedor == 'speechify':
                row.setdefault('habilitado', True)
                row.setdefault('capacidades_habilitadas', ['speech_generation'])

            chk = check or (dict(estado=cuenta.get('conexion_estado', 'guardada'), mensaje='Cuenta actualizada.', verificada=cuenta.get('conexion_estado') == 'acceso_comprobado') if cuenta and not clave else resultado('sin_verificar', 'Guardada como pendiente.'))
            self._persistir(proveedor, row, vals, chk)
            return dict(id=account_id, guardada=True, **chk)

    def _persistir(self, proveedor, row, vals, check):
        # Preparar todo antes de escribir; ninguna credencial va a cuentas.json.
        data = self.cuentas()
        rows = data.setdefault('proveedores', {}).setdefault(proveedor, {}).setdefault('cuentas', [])
        secret_names = {'api_key', 'token', 'auth_token', 'secret', 'password', 'key', 'secret_key', 'api_secret'}
        row = {k: v for k, v in row.items() if k.lower() not in secret_names}
        row.update(conexion_estado=check['estado'], conexion_fecha=time.strftime('%Y-%m-%d %H:%M:%S'))
        existing = next((i for i, c in enumerate(rows) if c.get('id') == row['id']), None)
        if existing is None:
            rows.append(row)
        else:
            rows[existing] = row
        orden = data.setdefault('orden_failover', [])
        # ElevenLabs es una capacidad secundaria de voz: no entra al failover ni al chat.
        opcionales_chat = {x['id'] for x in SERVICIOS_OPCIONALES} | {'deepseek', 'grok', 'minimax', 'alibaba', 'cerebras'}
        if proveedor not in opcionales_chat and proveedor not in {'elevenlabs', 'speechify'} and proveedor not in orden:
            orden.append(proveedor)
        seleccion = [x.strip() for x in self.config().get('SERVICIOS_ACTIVOS', '').split(',') if x.strip()]
        if not seleccion:
            seleccion = list(orden)
        if proveedor not in opcionales_chat and proveedor not in {'elevenlabs', 'speechify'} and proveedor not in seleccion:
            seleccion.append(proveedor)
        vals['SERVICIOS_ACTIVOS'] = ','.join(seleccion)
        envpath = self.root / '.env'
        previous = envpath.read_text(encoding='utf-8') if envpath.exists() else None
        newtext = modificar_env(previous or '', vals)
        escribir_atomico(envpath, newtext)
        try:
            escribir_json(self.root / 'cuentas.json', data)
        except OSError:
            if previous is None:
                envpath.unlink(missing_ok=True)
            else:
                escribir_atomico(envpath, previous)
            raise

    def conectar(self, body):
        proveedor = body.get('proveedor', '')
        clave = str(body.get('clave', '')).strip()
        cf_id = limpiar_cf_id(body.get('cf_id', ''))
        account_id = body.get('id', '')

        if account_id and not clave:
            cuenta = self.buscar(proveedor, account_id)
            if not cuenta:
                raise ErrorUsuario('Esa cuenta ya no está en la lista. Volvé a Mis servicios.')
            clave_existente = self.clave_guardada(proveedor, cuenta)
            if not clave_existente:
                raise ErrorUsuario('Falta la clave de esta cuenta. Ingresala para continuar.')
            email = validar_email(body.get('email') or cuenta.get('email', ''), obligatorio=not bool(cuenta) and proveedor not in {'elevenlabs', 'speechify'})
            check = comprobar_clave(proveedor, clave_existente, cf_id or cuenta.get('account_id', ''))
            if not check['verificada'] and body.get('guardar_pendiente') is not True and check['estado'] in {'clave_rechazada', 'sin_permiso'}:
                return dict(guardada=False, **check)
            return self.guardar(proveedor, clave='', nombre=body.get('nombre', ''), cf_id=cf_id, account_id=account_id, check=check, email=email, voice_id=body.get('voice_id', ''))

        self.validar(proveedor, clave, cf_id)
        email = validar_email(body.get('email', ''), obligatorio=not account_id and proveedor not in {'elevenlabs', 'speechify'})
        check = comprobar_clave(proveedor, clave, cf_id)
        if check['verificada'] or (body.get('guardar_pendiente') is True and check['estado'] not in {'clave_rechazada', 'sin_permiso'}):
            return self.guardar(proveedor, clave, body.get('nombre', ''), cf_id, account_id, check, email, body.get('voice_id', ''))
        return dict(guardada=False, **check)

    def verificar(self, proveedor, account_id):
        with self.lock:
            if proveedor not in POR_ID:
                raise ErrorUsuario('Servicio desconocido.')
            cuenta = self.buscar(proveedor, account_id)
            if not cuenta:
                raise ErrorUsuario('No encontramos esta cuenta.')
            if proveedor == 'ollama':
                inicio = self.iniciar_ollama_registradas(account_id=account_id)
                check = self.comprobar_ollama(cuenta['puerto'], cuenta.get('email', ''), cuenta.get('modo') == 'local')
                if check['estado'] == 'sin_conexion' and inicio.get('errores'):
                    check = resultado('sin_conexion',
                        'No se pudo iniciar esta instancia de Ollama. Reiniciá Núcleo IA; si continúa, revisá el registro de la cuenta.')
            else:
                clave = self.clave_guardada(proveedor, cuenta)
                if not clave:
                    return resultado('sin_clave', 'Falta la clave de esta cuenta. Usá “Actualizar clave”.')
                check = comprobar_clave(proveedor, clave, cuenta.get('account_id', ''))
            data = self.cuentas()
            target = next(c for c in data['proveedores'][proveedor]['cuentas'] if c['id'] == account_id)
            target.update(conexion_estado=check['estado'], conexion_fecha=time.strftime('%Y-%m-%d %H:%M:%S'))
            escribir_json(self.root / 'cuentas.json', data)
            return check

    def iniciar_ollama_registradas(self, account_id=None):
        """Inicia las instancias Ollama apagadas sin alterar su identidad local."""
        from scripts.agregar_ollama import start_ollama_instance
        cuentas = self.cuentas().get('proveedores', {}).get('ollama', {}).get('cuentas', [])
        seleccionadas = [c for c in cuentas if not account_id or c.get('id') == account_id]
        iniciadas = 0
        validas = []
        errores = []
        for cuenta in seleccionadas:
            port = cuenta.get('puerto')
            rel_home = str(cuenta.get('ollama_home', '')).strip()
            if not isinstance(port, int) or not 1024 <= port <= 65535 or not rel_home:
                errores.append(str(cuenta.get('id', 'cuenta desconocida')))
                continue
            home = Path(rel_home)
            if not home.is_absolute():
                home = self.root / home
            validas.append((cuenta, port))
            try:
                with socket.create_connection(('127.0.0.1', port), timeout=.2):
                    continue
            except OSError:
                pass
            if start_ollama_instance(home, port):
                iniciadas += 1
            else:
                errores.append(str(cuenta.get('id', 'cuenta desconocida')))
        if iniciadas:
            # Ollama suele responder enseguida, pero en equipos lentos necesita
            # unos segundos antes de que /api/me esté disponible.
            limite = time.time() + 8
            pendientes = list(validas)
            while pendientes and time.time() < limite:
                restantes = []
                for cuenta, port in pendientes:
                    try:
                        with socket.create_connection(('127.0.0.1', port), timeout=.2):
                            continue
                    except OSError:
                        restantes.append((cuenta, port))
                pendientes = restantes
                if pendientes:
                    time.sleep(.2)
        disponibles = 0
        for cuenta, port in validas:
            try:
                with socket.create_connection(('127.0.0.1', port), timeout=.2):
                    disponibles += 1
            except OSError:
                errores.append(str(cuenta.get('id', 'cuenta desconocida')))
        return {'total': len(seleccionadas), 'iniciadas': iniciadas, 'disponibles': disponibles,
                'errores': sorted(set(errores))}

    def oauth_iniciar(self, origin, email):
        email = validar_email(email)
        with self.lock:
            self.oauth = {k: v for k, v in self.oauth.items() if time.time() - v['created'] < 600}
            state = secrets.token_urlsafe(24)
            verifier = secrets.token_urlsafe(48)
            challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip('=')
            self.oauth[state] = dict(verifier=verifier, created=time.time(), email=email)
            url = 'https://openrouter.ai/auth?' + urllib.parse.urlencode(dict(
                callback_url=origin + '/oauth/callback/' + state, code_challenge=challenge, code_challenge_method='S256'))
            return dict(url=url, estado='esperando')

    def oauth_completar(self, state, code):
        with self.lock:
            flow = self.oauth.pop(state, None)
        if not flow or time.time() - flow['created'] > 600 or not code or len(code) > 4096:
            raise ErrorUsuario('Esta autorización venció o ya fue usada. Volvé al asistente y conectá de nuevo.')
        status, data = peticion_json('https://openrouter.ai/api/v1/auth/keys', metodo='POST', payload=dict(
            code=code, code_verifier=flow['verifier'], code_challenge_method='S256'))
        if status != 200 or not isinstance(data.get('key'), str):
            raise ErrorUsuario('No pudimos terminar la autorización. Volvé a intentar o usá la opción de pegar una clave.')
        key = data['key']
        self.validar('openrouter', key)
        check = comprobar_clave('openrouter', key)
        # La autorización produjo una clave; conservarla aunque la comprobación esté temporalmente caída.
        return self.guardar('openrouter', key, check=check, email=flow.get('email', ''))

    @staticmethod
    def comprobar_ollama(port, email='', local=False):
        if not isinstance(port, int) or not 1024 <= port <= 65535:
            raise ErrorUsuario('El puerto guardado de Ollama necesita revisión.')
        code, data = peticion_json(f'http://127.0.0.1:{port}/api/tags' if local else f'http://127.0.0.1:{port}/api/me',
                                  metodo='GET' if local else 'POST')
        if not code:
            return resultado('sin_conexion', 'Ollama no responde. Abrí Ollama y volvé a comprobar.')
        if code == 401:
            return resultado('pendiente', 'Todavía falta autorizar. Abrí el enlace de conexión y elegí “Authorize Device”.')
        if code != 200:
            return resultado('sin_verificar', 'Ollama respondió, pero no confirmó la conexión. Probá nuevamente.')
        if local:
            if not isinstance(data.get('models'), list):
                return resultado('sin_verificar', 'No se pudo leer la lista de modelos de Ollama.')
            if not data['models']:
                return resultado('sin_modelos', 'Ollama está abierto, pero aún no tiene modelos. Descargá uno desde Ollama.')
            return resultado('acceso_comprobado', 'Ollama local está disponible y tiene modelos instalados.', True)
        actual = str(data.get('email', '')).strip().lower()
        if not actual:
            return resultado('sin_verificar', 'Ollama no confirmó la cuenta autorizada. No se marcó como conectada.')
        if email and actual != email.strip().lower():
            return resultado('otra_cuenta', 'Autorizaste una cuenta diferente al correo indicado. Entrá con la cuenta correcta y repetí la autorización.')
        return resultado('acceso_comprobado', 'La cuenta de Ollama Cloud está autorizada. Su uso depende de la cuota disponible.', True)

    def ollama_preparar(self, email, account_id=''):
        from scripts.agregar_ollama import generate_ssh_key, start_ollama_instance
        import shutil
        if not isinstance(email, str) or not re.fullmatch(r'[^\s@]{1,100}@[^\s@]{1,150}\.[^\s@]{2,30}', email):
            raise ErrorUsuario('Escribí el correo con el que vas a entrar a Ollama.')
        with self.lock:
            path = self.root / 'state' / 'servicios_ollama_pendiente.json'
            pending = leer_json(path)
            cuenta_existente = self.buscar('ollama', account_id) if account_id else None
            if account_id and not cuenta_existente:
                raise ErrorUsuario('Esa cuenta de Ollama ya no está en la lista. Volvé a Mis servicios.')
            if cuenta_existente and str(cuenta_existente.get('email', '')).strip().lower() != email.lower():
                raise ErrorUsuario('El correo no coincide con la cuenta de Ollama elegida. Volvé a abrir esa cuenta para repararla.')
            # Al reparar una cuenta ya guardada, esa elección explícita tiene
            # prioridad sobre cualquier alta que haya quedado a medio hacer.
            # Solo reemplazamos el puntero pendiente: no borramos claves ni
            # carpetas de la preparación anterior.
            if cuenta_existente and (not pending or pending.get('id') != account_id):
                pending = dict(cuenta_existente)
                pending['reautorizar'] = True
                escribir_json(path, pending)
            elif pending and pending.get('email', '').lower() != email.lower():
                raise ErrorUsuario('Hay una conexión pendiente con otro correo. Terminá esa conexión antes de agregar una nueva.')
            if not shutil.which('ollama'):
                raise ErrorUsuario('No encontramos Ollama instalado. Usá “Instalar Ollama”, completá la instalación y volvé a abrir Mis servicios.')
            if not pending and cuenta_existente:
                pending = dict(cuenta_existente)
                pending['reautorizar'] = True
                escribir_json(path, pending)
            elif not pending:
                ids = {str(c.get('id')) for c in self.cuentas().get('proveedores', {}).get('ollama', {}).get('cuentas', [])}
                n = 1
                while f'acc{n}' in ids or (self.root / 'ollama_instances' / f'acc{n}').exists():
                    n += 1
                used = {c.get('puerto') for c in self.cuentas().get('proveedores', {}).get('ollama', {}).get('cuentas', [])}
                port = 11434
                while port < 65535:
                    with socket.socket() as s:
                        try:
                            if port in used:
                                raise OSError()
                            s.bind(('127.0.0.1', port))
                            break
                        except OSError:
                            port += 1
                if port >= 65535:
                    raise ErrorUsuario('No encontramos un puerto libre para Ollama.')
                pending = dict(id=f'acc{n}', puerto=port, email=email, ollama_home=f'ollama_instances/acc{n}')
                escribir_json(path, pending)
            home = self.root / pending['ollama_home']
            keypath = home / '.ollama' / 'id_ed25519'
            if not generate_ssh_key(keypath, email):
                raise ErrorUsuario('Falta la herramienta de claves OpenSSH. En Windows agregá “Cliente OpenSSH” en Funciones opcionales; en Linux instalá openssh-client.')
            pub = keypath.with_suffix('.pub').read_text(encoding='utf-8').split()
            if len(pub) < 2:
                raise ErrorUsuario('No se pudo preparar la clave pública de Ollama.')
            code, _ = peticion_json(f"http://127.0.0.1:{pending['puerto']}/api/version")
            if code == 0:
                if not start_ollama_instance(home, pending['puerto']):
                    raise ErrorUsuario('No se pudo iniciar Ollama. Abrí la aplicación y reintentá.')
            b64 = base64.b64encode(' '.join(pub[:2]).encode()).decode().rstrip('=')
            url = 'https://ollama.com/connect?' + urllib.parse.urlencode(dict(name='NucleoIA-' + pending['id'], key=b64))
            return dict(url=url, email=pending['email'], id=pending['id'],
                        reautorizar=bool(pending.get('reautorizar')), estado='pendiente')

    def ollama_finalizar(self, local=False):
        with self.lock:
            path = self.root / 'state' / 'servicios_ollama_pendiente.json'
            row = dict(id=self.nuevo_id('ollama'), puerto=11434, modo='local', nombre='Ollama local') if local else leer_json(path)
            if not row:
                raise ErrorUsuario('Primero prepará la conexión de Ollama.')
            check = self.comprobar_ollama(row['puerto'], row.get('email', ''), local)
            if check['verificada']:
                if local:
                    existing = next((c for c in self.cuentas().get('proveedores', {}).get('ollama', {}).get('cuentas', []) if c.get('puerto') == 11434), None)
                    if existing:
                        return dict(guardada=True, id=existing['id'], **check)
                self._persistir('ollama', row, {}, check)
                if not local:
                    path.unlink(missing_ok=True)
                return dict(guardada=True, id=row['id'], **check)
            return dict(guardada=False, **check)
