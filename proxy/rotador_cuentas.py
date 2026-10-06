"""
Rotador de cuentas multi-proveedor para Núcleo IA.
Soporta Ollama, Cloudflare Workers AI, OpenRouter, NVIDIA NIM, Cohere y Google Gemini.
"""
import json
import os
import threading
from datetime import datetime, timedelta

from proxy.registrador import obtener_uso_cuenta
from scripts.catalogo_servicios import SERVICIOS_OPCIONALES

RAIZ = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
CUENTAS_RUTA = os.path.join(RAIZ, "cuentas.json")
ESTADO_RUTA = os.path.join(RAIZ, "state", "estado_cuentas.json")
PREFERENCIAS_RANKING = os.path.join(RAIZ, "state", "preferencias_ranking.json")

_lock = threading.Lock()
_indice_por_tipo = {}
_cuentas_por_tipo = {}
_estados = {}
_orden_failover = ["ollama", "groq", "cerebras", "mistral", "deepseek", "grok", "minimax", "alibaba", "tokenrouter", "xkiro", "tokenharbor", "apinex", "cloudflare", "nvidia", "openrouter", "cohere", "google", "zhipu"]
_mapeo_modelos = {}
_servicios_activos = set(_orden_failover)
_cuentas_compatibles_por_modelo = {}

ESTADOS_FINALES = {"sin_credito", "restringida"}

PROVEEDORES_OPCIONALES = {x["id"] for x in SERVICIOS_OPCIONALES} | {"deepseek", "grok", "minimax", "alibaba", "cerebras", "mistral"}
SERVICIOS_DISPONIBLES = {"ollama", "groq", "cerebras", "mistral", "deepseek", "grok", "minimax", "alibaba", "tokenrouter", "xkiro", "tokenharbor", "apinex", "cloudflare", "nvidia", "openrouter", "cohere", "google", "siliconflow", "zhipu", "elevenlabs", "speechify"} | PROVEEDORES_OPCIONALES


def cargar_cuentas():
    """Carga la configuración de cuentas agrupadas por proveedor."""
    global _orden_failover, _mapeo_modelos, _servicios_activos, _cuentas_compatibles_por_modelo
    if not os.path.exists(CUENTAS_RUTA):
        return

    with open(CUENTAS_RUTA, "r", encoding="utf-8") as f:
        datos = json.load(f)

    _orden_failover = datos.get("orden_failover", ["ollama", "groq", "cerebras", "mistral", "deepseek", "grok", "minimax", "alibaba", "tokenrouter", "xkiro", "tokenharbor", "cloudflare", "nvidia", "openrouter", "cohere", "google", "zhipu"])
    _mapeo_modelos = datos.get("mapeo_modelos", {})
    _cuentas_compatibles_por_modelo = {}
    try:
        with open(os.path.join(RAIZ, "state", "ranking_global.json"), "r", encoding="utf-8") as f:
            ranking = json.load(f).get("ranking", [])
        for fila in ranking:
            if not isinstance(fila, dict):
                continue
            proveedor = str(fila.get("proveedor", ""))
            modelo = str(fila.get("modelo_id") or fila.get("id") or "")
            ids = fila.get("cuentas_compatibles")
            if proveedor and modelo and isinstance(ids, list):
                _cuentas_compatibles_por_modelo[(proveedor, modelo)] = {str(x) for x in ids if x}
    except (OSError, ValueError, TypeError):
        _cuentas_compatibles_por_modelo = {}
    _servicios_activos = _leer_servicios_activos(_orden_failover)
    _orden_failover = [tipo for tipo in _orden_failover if tipo in _servicios_activos]

    proveedores = datos.get("proveedores", {})
    for tipo, config in proveedores.items():
        if tipo in PROVEEDORES_OPCIONALES and config.get("habilitado") is True:
            _servicios_activos.add(tipo)
            if tipo not in _orden_failover and not config.get("solo_capacidades"):
                _orden_failover.append(tipo)
    _cuentas_por_tipo.clear()
    _indice_por_tipo.clear()

    for tipo, config in proveedores.items():
        cuentas_lista = config.get("cuentas", [])
        if tipo in PROVEEDORES_OPCIONALES:
            cuentas_lista = [c for c in cuentas_lista if c.get("habilitado", True) is True]
        _cuentas_por_tipo[tipo] = cuentas_lista
        _indice_por_tipo[tipo] = 0

    _cargar_estados()


def _leer_servicios_activos(default=None):
    default = list(default or ["ollama", "groq", "tokenrouter", "xkiro", "tokenharbor", "cloudflare", "nvidia", "openrouter", "cohere", "google", "zhipu"])
    raw = os.getenv("SERVICIOS_ACTIVOS", "").strip()
    if not raw:
        return set(default)
    seleccionados = {x.strip() for x in raw.split(",") if x.strip()}
    validos = {x for x in seleccionados if x in SERVICIOS_DISPONIBLES}
    return validos or set(default)


def _servicio_habilitado(tipo):
    return tipo in _servicios_activos


def _cargar_estados():
    global _estados
    if os.path.exists(ESTADO_RUTA):
        try:
            with open(ESTADO_RUTA, "r", encoding="utf-8") as f:
                _estados = json.load(f).get("cuentas", {})
        except Exception:
            _estados = {}


def _asegurar_estado(cuenta_id):
    estado = _estados.setdefault(cuenta_id, {})
    estado.setdefault("estado", "activa")
    estado.setdefault("modelos_agotados", [])
    estado.setdefault("fallos", {})
    estado.setdefault("last_used", None)
    estado.setdefault("last_error", None)
    estado.setdefault("cooldown_hasta", None)
    return estado


def _guardar_estados():
    dir_path = os.path.dirname(ESTADO_RUTA)
    os.makedirs(dir_path, exist_ok=True)
    tmp_path = os.path.join(dir_path, f"estado_cuentas.tmp.{os.getpid()}")
    try:
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump({
                "generado": datetime.now().isoformat(),
                "cuentas": _estados
            }, f, indent=2, ensure_ascii=False)
        os.replace(tmp_path, ESTADO_RUTA)
    except Exception:
        if os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except Exception:
                pass


def _disponible(cuenta):
    cid = cuenta["id"]
    est = _asegurar_estado(cid)
    estado = est.get("estado", "activa")
    hasta = est.get("cooldown_hasta") or est.get("bloqueado_hasta")
    if hasta:
        try:
            if datetime.now() < datetime.fromisoformat(hasta):
                return False
            est["estado"] = "activa"
            est["cooldown_hasta"] = None
            est["bloqueado_hasta"] = None
        except (ValueError, TypeError):
            pass

    estado = est.get("estado", "activa")
    if estado in ESTADOS_FINALES:
        return False

    return est.get("estado", "activa") != "bloqueada"


def _rotar_tipo(tipo):
    if not _servicio_habilitado(tipo):
        return None
    cuentas_tipo = _cuentas_por_tipo.get(tipo, [])
    if not cuentas_tipo:
        return None

    total = len(cuentas_tipo)
    inicio = _indice_por_tipo.get(tipo, 0)

    for i in range(total):
        idx = (inicio + i) % total
        cuenta = cuentas_tipo[idx]
        if _disponible(cuenta):
            _indice_por_tipo[tipo] = (idx + 1) % total
            return cuenta

    return None


def _puntaje_cuenta(cuenta, modelo=None):
    if not _disponible(cuenta):
        return None

    cid = cuenta["id"]
    est = _asegurar_estado(cid)
    if modelo and modelo in est.get("modelos_agotados", []):
        return None

    uso = obtener_uso_cuenta(cid)
    ahora = datetime.now()
    score = 100.0
    score -= float(uso.get("hora", 0)) * 4.5
    score -= float(uso.get("semana", 0)) * 0.18
    score -= float(uso.get("tokens_totales", 0)) / 50000.0

    last_used = est.get("last_used")
    if last_used:
        try:
            delta_h = (ahora - datetime.fromisoformat(last_used)).total_seconds() / 3600.0
            score += min(delta_h * 1.5, 18.0)
        except (ValueError, TypeError):
            score += 4.0
    else:
        score += 10.0

    fallos = est.get("fallos", {})
    score -= float(fallos.get("429", 0)) * 18.0
    score -= float(fallos.get("403", 0)) * 28.0
    score -= float(fallos.get("402", 0)) * 40.0
    score -= float(fallos.get("otros", 0)) * 8.0

    estado = est.get("estado", "activa")
    if estado == "parcial":
        score -= 6.0
    elif estado == "bloqueada":
        score -= 100.0
    elif estado == "sin_credito":
        score -= 120.0
    elif estado == "restringida":
        score -= 90.0

    return score


def obtener_cuenta_mejor(tipo, modelo=None):
    if not _servicio_habilitado(tipo):
        return None
    cuentas_tipo = _filtrar_cuentas_modelo(tipo, modelo, _cuentas_por_tipo.get(tipo, []))
    if not cuentas_tipo:
        return None

    if modelo:
        try:
            with open(PREFERENCIAS_RANKING, "r", encoding="utf-8") as f:
                preferred = json.load(f).get("cuentas_preferidas", {}).get(f"{tipo}::{modelo}")
            for cuenta in cuentas_tipo:
                if cuenta.get("id") == preferred and _puntaje_cuenta(cuenta, modelo=modelo) is not None:
                    return cuenta
        except (OSError, ValueError, TypeError):
            pass

    mejor = None
    mejor_score = None
    for cuenta in cuentas_tipo:
        score = _puntaje_cuenta(cuenta, modelo=modelo)
        if score is None:
            continue
        if mejor_score is None or score > mejor_score:
            mejor = cuenta
            mejor_score = score

    if mejor is not None:
        return mejor

    return _rotar_tipo(tipo)


def obtener_todas_cuentas_tipo(tipo, modelo=None):
    """Retorna todas las cuentas utilizables, ordenadas por salud y uso."""
    with _lock:
        cuentas = _obtener_cuentas_ordenadas(tipo, modelo=modelo)
        if modelo:
            try:
                with open(PREFERENCIAS_RANKING, "r", encoding="utf-8") as f:
                    preferred = json.load(f).get("cuentas_preferidas", {}).get(f"{tipo}::{modelo}")
                cuentas.sort(key=lambda cuenta: cuenta.get("id") != preferred)
            except (OSError, ValueError, TypeError):
                pass
        return cuentas


def _obtener_cuentas_ordenadas(tipo, modelo=None):
    if not _servicio_habilitado(tipo):
        return []
    puntuadas = []
    for cuenta in _filtrar_cuentas_modelo(tipo, modelo, _cuentas_por_tipo.get(tipo, [])):
        score = _puntaje_cuenta(cuenta, modelo=modelo)
        if score is not None:
            puntuadas.append((score, cuenta))
    puntuadas.sort(key=lambda item: item[0], reverse=True)
    return [cuenta for _, cuenta in puntuadas]


def _filtrar_cuentas_modelo(tipo, modelo, cuentas):
    if not modelo:
        return cuentas
    permitidas = _cuentas_compatibles_por_modelo.get((str(tipo), str(modelo)))
    if permitidas is None:
        return cuentas
    return [cuenta for cuenta in cuentas if str(cuenta.get("id", "")) in permitidas]


def obtener_cuentas_ordenadas(tipo, modelo=None):
    """Lista pública para construir planes exhaustivos sin repetir cuentas."""
    with _lock:
        return _obtener_cuentas_ordenadas(tipo, modelo=modelo)


def obtener_cuenta_disponible(tipo):
    """Obtiene la siguiente cuenta disponible para un proveedor específico."""
    with _lock:
        return obtener_cuenta_mejor(tipo)


def obtener_siguiente(tipo_preferido=None):
    with _lock:
        if tipo_preferido:
            if _servicio_habilitado(tipo_preferido):
                cuenta = obtener_cuenta_mejor(tipo_preferido)
                if cuenta:
                    return tipo_preferido, cuenta
            else:
                tipo_preferido = None

        for tipo in _orden_failover:
            if not _servicio_habilitado(tipo):
                continue
            if tipo == tipo_preferido:
                continue
            cuenta = obtener_cuenta_mejor(tipo)
            if cuenta:
                return tipo, cuenta

        return None, None


def traducir_modelo(modelo_ollama, tipo_destino):
    if tipo_destino == "ollama":
        return modelo_ollama

    if modelo_ollama in _mapeo_modelos:
        regla = _mapeo_modelos[modelo_ollama]
        if isinstance(regla, dict):
            return regla.get(tipo_destino, regla.get("default", modelo_ollama))
        return regla

    return _mapeo_modelos.get("default", modelo_ollama)


def marcar_modelo_agotado(cid, modelo):
    with _lock:
        est = _asegurar_estado(cid)
        agotados = est.get("modelos_agotados", [])
        if modelo not in agotados:
            agotados.append(modelo)
        est["modelos_agotados"] = agotados
        est["estado"] = "parcial"
        est["last_error"] = {
            "codigo": 403,
            "modelo": modelo,
            "ts": datetime.now().isoformat(),
        }
        _guardar_estados()


def registrar_exito(cid, modelo=None):
    with _lock:
        est = _asegurar_estado(cid)
        est["estado"] = "activa"
        est["last_used"] = datetime.now().isoformat()
        est["last_error"] = None
        est["cooldown_hasta"] = None
        est["bloqueado_hasta"] = None
        _guardar_estados()


def reactivar_cuenta(cid):
    """Limpia el bloqueo local después de volver a autorizar una cuenta."""
    with _lock:
        est = _asegurar_estado(cid)
        est["estado"] = "activa"
        est["cooldown_hasta"] = None
        est["bloqueado_hasta"] = None
        est["last_error"] = None
        _guardar_estados()


def registrar_fallo(cid, codigo, modelo=None, razon=None):
    with _lock:
        est = _asegurar_estado(cid)
        fallos = est.get("fallos", {})
        clave = str(codigo) if str(codigo).isdigit() else "otros"
        if clave not in {"429", "403", "402"}:
            clave = "otros"
        fallos[clave] = int(fallos.get(clave, 0)) + 1
        est["fallos"] = fallos
        est["last_error"] = {
            "codigo": codigo,
            "modelo": modelo,
            "razon": razon,
            "ts": datetime.now().isoformat(),
        }

        ahora = datetime.now()
        if str(codigo) in ("401", "401_unauthorized"):
            est["estado"] = "restringida"
            est["cooldown_hasta"] = None
        elif str(codigo) == "429":
            est["estado"] = "bloqueada"
            est["cooldown_hasta"] = (ahora + timedelta(minutes=30)).isoformat()
        elif str(codigo) == "402":
            est["estado"] = "sin_credito"
            est["cooldown_hasta"] = (ahora + timedelta(hours=24)).isoformat()
        elif str(codigo) == "403":
            est["estado"] = "parcial"
        else:
            est["estado"] = "parcial"

        if modelo and str(codigo) == "403":
            agotados = est.get("modelos_agotados", [])
            if modelo not in agotados:
                agotados.append(modelo)
            est["modelos_agotados"] = agotados

        _guardar_estados()


def bloquear_cuenta(cid, razon="429_sesion"):
    with _lock:
        ahora = datetime.now()
        hasta = ahora + timedelta(hours=5)
        est = _asegurar_estado(cid)
        est.update({
            "estado": "bloqueada",
            "razon": razon,
            "bloqueado_hasta": hasta.isoformat(),
        })
        _guardar_estados()


def obtener_modelos_agotados(cid):
    with _lock:
        return _asegurar_estado(cid).get("modelos_agotados", [])


def obtener_orden_failover():
    return list(_orden_failover)


def obtener_mapeo_modelos():
    return dict(_mapeo_modelos)


def obtener_estado_general():
    with _lock:
        resultado = []
        for tipo, cuentas_tipo in _cuentas_por_tipo.items():
            for c in cuentas_tipo:
                est = _asegurar_estado(c["id"])
                entrada = {
                    "id": c["id"],
                    "tipo": tipo,
                    "estado": est.get("estado", "activa"),
                    "modelos_agotados": est.get("modelos_agotados", []),
                    "cooldown_hasta": est.get("cooldown_hasta"),
                    "last_used": est.get("last_used"),
                }
                # Metadatos operativos seguros: permiten identificar la cuenta
                # afectada sin exponer claves ni tokens.
                for campo in ("email", "puerto", "ollama_home", "host"):
                    if campo in c:
                        entrada[campo] = c[campo]
                if est.get("last_error") is not None:
                    entrada["last_error"] = est.get("last_error")
                resultado.append(entrada)
        return resultado


def contar_activas_por_tipo():
    with _lock:
        conteo = {}
        for tipo, cuentas_tipo in _cuentas_por_tipo.items():
            habilitado = _servicio_habilitado(tipo)
            activas = sum(1 for c in cuentas_tipo if _disponible(c)) if habilitado else 0
            conteo[tipo] = {"activas": activas, "total": len(cuentas_tipo), "habilitado": habilitado}
        return conteo


def obtener_mejor_score_tipo(tipo, modelo=None):
    with _lock:
        if not _servicio_habilitado(tipo):
            return None, None
        mejor = None
        mejor_score = None
        for cuenta in _cuentas_por_tipo.get(tipo, []):
            score = _puntaje_cuenta(cuenta, modelo=modelo)
            if score is None:
                continue
            if mejor_score is None or score > mejor_score:
                mejor = cuenta
                mejor_score = score
        return mejor, mejor_score
