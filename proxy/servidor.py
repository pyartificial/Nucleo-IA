"""
Servidor proxy multi-proveedor para Núcleo IA.
Recibe peticiones de OpenClaw / Hermes Agent y las despacha
priorizando el Ranking Global Unificado (Ollama, Cloudflare Workers AI, NVIDIA NIM, OpenRouter).
"""
import json
import os
import sys
import time
import threading
import hmac
import importlib.util
from typing import Any
from contextlib import asynccontextmanager

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
if hasattr(sys.stderr, "reconfigure"):
    try:
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

RAIZ = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if RAIZ not in sys.path:
    sys.path.insert(0, RAIZ)

from proxy.configuracion import cargar_configuracion, recargar_configuracion

cargar_configuracion()

import httpx
import tempfile
import shutil
from fastapi import FastAPI, Request, HTTPException, UploadFile, File, Form, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse, Response

from proxy import normalizador_stream, registrador, rotador_cuentas, limitador_tasa, gestor_modelos, seguridad, politicas
from proxy.esquemas import EntradaInvalida, validar_chat
from proxy.proveedores.fabrica import crear_proveedor
from scripts.catalogo_capacidades import CAPACIDADES, canonica, claves_compatibles, orden_guardado
from scripts.catalogo_servicios import SERVICIOS_OPCIONALES
from scripts.secret_utils import _parse_env_file
from proxy.capacidades import candidato_permitido, capacidad_video_para_body, proveedor_con_adaptador

PROVEEDORES_OPCIONALES = {x["id"] for x in SERVICIOS_OPCIONALES} | {"deepseek", "grok", "minimax", "alibaba", "cerebras", "mistral"}

_http_client: httpx.AsyncClient | None = None
_speechify_rotation_lock = threading.Lock()
_speechify_rotation_index = 0


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _http_client
    seguridad.validate_deployment()
    runtime_path = os.path.join(RAIZ, "state", "proxy_runtime.json")
    os.makedirs(os.path.dirname(runtime_path), exist_ok=True)
    _guardar_json_seguro(runtime_path, {
        "pid": os.getpid(), "root": RAIZ,
        "started_at": time.time(),
    })
    _http_client = httpx.AsyncClient(
        timeout=httpx.Timeout(120.0, connect=10.0),
        limits=httpx.Limits(max_keepalive_connections=30, max_connections=150),
    )
    try:
        yield
    finally:
        if _http_client is not None:
            await _http_client.aclose()
            _http_client = None
        try:
            runtime = _cargar_json_seguro(runtime_path, {})
            if runtime.get("pid") == os.getpid():
                os.remove(runtime_path)
        except OSError:
            pass


def get_http_client() -> httpx.AsyncClient:
    if _http_client is not None:
        return _http_client
    return httpx.AsyncClient(timeout=120.0)


app = FastAPI(title="Núcleo IA — Proxy Multi-Proveedor Unificado", lifespan=lifespan)


@app.get("/healthz")
def healthz():
    return {"status": "ok"}


@app.get("/readyz")
def readyz():
    cuentas = rotador_cuentas.contar_activas_por_tipo()
    total = sum(int(v.get("activas", 0)) for v in cuentas.values())
    return {"status": "ready" if total > 0 else "degraded", "active_accounts": total}


@app.middleware("http")
async def autenticacion_opcional(request: Request, call_next):
    """Protección local opcional; desactivada por defecto para uso personal."""
    from proxy.servicios_locales import RUTA_RECARGA, autorizar_recarga, recargar
    if request.url.path not in {"/healthz", "/readyz", "/status", "/rankings", RUTA_RECARGA}:
        pausa = _cargar_json_seguro(os.path.join(RAIZ, "state", "proxy_pausa.json"), {})
        if pausa.get("pausado"):
            return JSONResponse(status_code=503, content={"error": {"message": "Núcleo IA está pausado desde el Centro de control.", "type": "temporarily_unavailable"}})
    if request.url.path == RUTA_RECARGA:
        cliente = request.client.host if request.client else ''
        if request.method != 'POST' or not autorizar_recarga(cliente, request.headers.get('X-Nucleo-Local', ''), RAIZ):
            return JSONResponse(status_code=403, content={'mensaje': 'Acción reservada al asistente local.'})
        try:
            return JSONResponse(content=recargar(RAIZ))
        except (OSError, ValueError, TypeError):
            return JSONResponse(status_code=400, content={'mensaje': 'No se pudieron recargar las cuentas.'})
    if not seguridad.host_allowed(request.headers.get("host", "")):
        return JSONResponse(status_code=400, content={"error": {"message": "Host no permitido", "type": "authentication_error"}})
    if not seguridad.origin_allowed(request.headers.get("origin", "")):
        return JSONResponse(status_code=403, content={"error": {"message": "Origen web no permitido", "type": "authentication_error"}})
    max_body = int(os.getenv("MAX_REQUEST_BODY_BYTES", str(16 * 1024 * 1024)))
    content_length = request.headers.get("content-length", "")
    if content_length.isdigit() and int(content_length) > max_body:
        return JSONResponse(status_code=413, content={"error": {"message": "Solicitud demasiado grande", "type": "invalid_request_error"}})
    if seguridad.enabled("AUTH_ENABLED") and request.url.path not in seguridad.PUBLIC_PATHS:
        expected = seguridad.expected_key(request.url.path)
        supplied = request.headers.get("authorization", "")
        supplied = supplied[7:].strip() if supplied.lower().startswith("bearer ") else supplied.strip()
        if not expected or not hmac.compare_digest(supplied, expected):
            return JSONResponse(status_code=401, content={"error": {"message": "API key inválida", "type": "authentication_error"}})
    return await call_next(request)

_cors_origins = sorted(seguridad.allowed_origins())
_cors_credentials = os.getenv("CORS_ALLOW_CREDENTIALS", "false").strip().lower() in {"1", "true", "yes", "on"}
if "*" in _cors_origins:
    _cors_credentials = False
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=_cors_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(HTTPException)
async def custom_http_exception_handler(request: Request, exc: HTTPException):
    detail = exc.detail
    if isinstance(detail, dict):
        msg = detail.get("message") or detail.get("error") or str(detail)
        code = detail.get("code") or str(exc.status_code)
    else:
        msg = str(detail)
        code = str(exc.status_code)
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "message": msg,
                "type": "invalid_request_error" if exc.status_code < 500 else "api_error",
                "param": None,
                "code": code,
            }
        },
    )


RAIZ = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
UI_DEMO_PATH = os.path.join(RAIZ, "ui", "demo.html")
rotador_cuentas.cargar_cuentas()
registrador.cargar_contadores()


def _desactivar_openrouter_sin_clave() -> None:
    cuentas_ruta = os.path.join(RAIZ, "cuentas.json")
    if not os.path.exists(cuentas_ruta):
        return
    try:
        with open(cuentas_ruta, "r", encoding="utf-8") as f:
            datos = json.load(f)
    except Exception:
        return

    openrouter_cuentas = datos.get("proveedores", {}).get("openrouter", {}).get("cuentas", [])
    if not openrouter_cuentas:
        return

    for cuenta in openrouter_cuentas:
        try:
            proveedor = crear_proveedor(cuenta, "openrouter")
        except Exception:
            continue
        if not getattr(proveedor, "tiene_credencial_valida", lambda: False)():
            rotador_cuentas.bloquear_cuenta(cuenta.get("id", ""), razon="openrouter_key_invalida")


def _desactivar_cloudflare_sin_clave() -> None:
    cuentas_ruta = os.path.join(RAIZ, "cuentas.json")
    if not os.path.exists(cuentas_ruta):
        return
    try:
        with open(cuentas_ruta, "r", encoding="utf-8") as f:
            datos = json.load(f)
    except Exception:
        return

    cloudflare_cuentas = datos.get("proveedores", {}).get("cloudflare", {}).get("cuentas", [])
    if not cloudflare_cuentas:
        return

    for cuenta in cloudflare_cuentas:
        try:
            proveedor = crear_proveedor(cuenta, "cloudflare")
        except Exception:
            continue
        if not getattr(proveedor, "tiene_credencial_valida", lambda: False)():
            rotador_cuentas.bloquear_cuenta(cuenta.get("id", ""), razon="cloudflare_key_invalida")


def _desactivar_google_sin_clave() -> None:
    cuentas_ruta = os.path.join(RAIZ, "cuentas.json")
    if not os.path.exists(cuentas_ruta):
        return
    try:
        with open(cuentas_ruta, "r", encoding="utf-8") as f:
            datos = json.load(f)
    except Exception:
        return

    google_cuentas = datos.get("proveedores", {}).get("google", {}).get("cuentas", [])
    if not google_cuentas:
        return

    for cuenta in google_cuentas:
        try:
            proveedor = crear_proveedor(cuenta, "google")
        except Exception:
            continue
        if not getattr(proveedor, "tiene_credencial_valida", lambda: False)():
            rotador_cuentas.bloquear_cuenta(cuenta.get("id", ""), razon="google_key_invalida")


def _desactivar_cohere_sin_clave() -> None:
    cuentas_ruta = os.path.join(RAIZ, "cuentas.json")
    if not os.path.exists(cuentas_ruta):
        return
    try:
        with open(cuentas_ruta, "r", encoding="utf-8") as f:
            datos = json.load(f)
    except Exception:
        return

    cohere_cuentas = datos.get("proveedores", {}).get("cohere", {}).get("cuentas", [])
    if not cohere_cuentas:
        return

    for cuenta in cohere_cuentas:
        try:
            proveedor = crear_proveedor(cuenta, "cohere")
        except Exception:
            continue
        if not getattr(proveedor, "tiene_credencial_valida", lambda: False)():
            rotador_cuentas.bloquear_cuenta(cuenta.get("id", ""), razon="cohere_key_invalida")


def _desactivar_siliconflow_sin_clave() -> None:
    cuentas_ruta = os.path.join(RAIZ, "cuentas.json")
    if not os.path.exists(cuentas_ruta):
        return
    try:
        with open(cuentas_ruta, "r", encoding="utf-8") as f:
            datos = json.load(f)
    except Exception:
        return

    sf_cuentas = datos.get("proveedores", {}).get("siliconflow", {}).get("cuentas", [])
    if not sf_cuentas:
        return

    for cuenta in sf_cuentas:
        try:
            proveedor = crear_proveedor(cuenta, "siliconflow")
        except Exception:
            continue
        if not getattr(proveedor, "tiene_credencial_valida", lambda: False)():
            rotador_cuentas.bloquear_cuenta(cuenta.get("id", ""), razon="siliconflow_key_invalida")


def _desactivar_zhipu_sin_clave() -> None:
    cuentas_ruta = os.path.join(RAIZ, "cuentas.json")
    if not os.path.exists(cuentas_ruta):
        return
    try:
        with open(cuentas_ruta, "r", encoding="utf-8") as f:
            datos = json.load(f)
    except Exception:
        return

    zh_cuentas = datos.get("proveedores", {}).get("zhipu", {}).get("cuentas", [])
    if not zh_cuentas:
        return

    for cuenta in zh_cuentas:
        try:
            proveedor = crear_proveedor(cuenta, "zhipu")
        except Exception:
            continue
        if not getattr(proveedor, "tiene_credencial_valida", lambda: False)():
            rotador_cuentas.bloquear_cuenta(cuenta.get("id", ""), razon="zhipu_key_invalida")


def _desactivar_groq_sin_clave() -> None:
    cuentas_ruta = os.path.join(RAIZ, "cuentas.json")
    if not os.path.exists(cuentas_ruta):
        return
    try:
        with open(cuentas_ruta, "r", encoding="utf-8") as f:
            datos = json.load(f)
    except Exception:
        return

    groq_cuentas = datos.get("proveedores", {}).get("groq", {}).get("cuentas", [])
    if not groq_cuentas:
        return

    for cuenta in groq_cuentas:
        try:
            proveedor = crear_proveedor(cuenta, "groq")
        except Exception:
            continue
        if not getattr(proveedor, "tiene_credencial_valida", lambda: False)():
            rotador_cuentas.bloquear_cuenta(cuenta.get("id", ""), razon="groq_key_invalida")


def _desactivar_tokenrouter_sin_clave() -> None:
    cuentas_ruta = os.path.join(RAIZ, "cuentas.json")
    if not os.path.exists(cuentas_ruta):
        return
    try:
        with open(cuentas_ruta, "r", encoding="utf-8") as f:
            datos = json.load(f)
    except Exception:
        return

    tr_cuentas = datos.get("proveedores", {}).get("tokenrouter", {}).get("cuentas", [])
    if not tr_cuentas:
        return

    for cuenta in tr_cuentas:
        try:
            proveedor = crear_proveedor(cuenta, "tokenrouter")
        except Exception:
            continue
        if not getattr(proveedor, "tiene_credencial_valida", lambda: False)():
            rotador_cuentas.bloquear_cuenta(cuenta.get("id", ""), razon="tokenrouter_key_invalida")


def _desactivar_xkiro_sin_clave() -> None:
    cuentas_ruta = os.path.join(RAIZ, "cuentas.json")
    if not os.path.exists(cuentas_ruta):
        return
    try:
        with open(cuentas_ruta, "r", encoding="utf-8") as f:
            datos = json.load(f)
    except Exception:
        return
    for cuenta in datos.get("proveedores", {}).get("xkiro", {}).get("cuentas", []):
        try:
            proveedor = crear_proveedor(cuenta, "xkiro")
        except Exception:
            continue
        if not getattr(proveedor, "tiene_credencial_valida", lambda: False)():
            rotador_cuentas.bloquear_cuenta(cuenta.get("id", ""), razon="xkiro_key_invalida")


def _desactivar_tokenharbor_sin_clave() -> None:
    cuentas_ruta = os.path.join(RAIZ, "cuentas.json")
    if not os.path.exists(cuentas_ruta):
        return
    try:
        with open(cuentas_ruta, "r", encoding="utf-8") as f:
            datos = json.load(f)
    except Exception:
        return
    for cuenta in datos.get("proveedores", {}).get("tokenharbor", {}).get("cuentas", []):
        try:
            proveedor = crear_proveedor(cuenta, "tokenharbor")
        except Exception:
            continue
        if not getattr(proveedor, "tiene_credencial_valida", lambda: False)():
            rotador_cuentas.bloquear_cuenta(cuenta.get("id", ""), razon="tokenharbor_key_invalida")

def _desactivar_apinex_sin_clave() -> None:
    cuentas_ruta = os.path.join(RAIZ, "cuentas.json")
    if not os.path.exists(cuentas_ruta): return
    try:
        with open(cuentas_ruta, "r", encoding="utf-8") as f: datos = json.load(f)
    except Exception: return
    for cuenta in datos.get("proveedores", {}).get("apinex", {}).get("cuentas", []):
        try: proveedor = crear_proveedor(cuenta, "apinex")
        except Exception: continue
        if not proveedor.tiene_credencial_valida():
            rotador_cuentas.bloquear_cuenta(cuenta.get("id", ""), razon="apinex_key_invalida")


def _desactivar_compatible_sin_clave() -> None:
    """Bloquea solo cuentas opcionales sin credencial disponible."""
    try:
        with open(os.path.join(RAIZ, "cuentas.json"), "r", encoding="utf-8") as f:
            proveedores = json.load(f).get("proveedores", {})
    except (OSError, ValueError, TypeError):
        return
    for tipo in ("cerebras", "mistral", "deepseek", "grok", "minimax", "alibaba"):
        for cuenta in proveedores.get(tipo, {}).get("cuentas", []):
            try:
                adapter = crear_proveedor(cuenta, tipo)
                if not adapter.tiene_credencial_valida():
                    rotador_cuentas.bloquear_cuenta(cuenta.get("id", ""), razon=f"{tipo}_key_invalida")
            except Exception:
                continue


_desactivar_openrouter_sin_clave()
_desactivar_cloudflare_sin_clave()
_desactivar_google_sin_clave()
_desactivar_cohere_sin_clave()
_desactivar_siliconflow_sin_clave()
_desactivar_zhipu_sin_clave()
_desactivar_groq_sin_clave()
_desactivar_tokenrouter_sin_clave()
_desactivar_xkiro_sin_clave()
_desactivar_tokenharbor_sin_clave()
_desactivar_apinex_sin_clave()
_desactivar_compatible_sin_clave()

PESO_PROVEEDOR = {
    "ollama": 1.0,
    "groq": 1.0,
    "cerebras": 1.0,
    "mistral": 1.0,
    "deepseek": 1.0,
    "grok": 1.0,
    "minimax": 1.0,
    "alibaba": 1.0,
    "tokenrouter": 1.0,
    "cloudflare": 0.9,
    "openrouter": 1.0,
    "nvidia": 0.3,
    "google": 0.7,
    "cohere": 0.8,
    "siliconflow": 0.8,
    "zhipu": 0.8,
    "xkiro": 0.8,
    "tokenharbor": 0.8,
    "apinex": 0.8,
}

_provider_turn = None  # proveedor usado en auto
_health_lock = threading.RLock()
_health_state = {"generado": None, "candidatos": {}}

ROUTE_RANKINGS_DIR = os.path.join(RAIZ, "state", "route_rankings")
ROUTE_HEALTH_RUTA = os.path.join(RAIZ, "state", "route_health.json")
ROUTE_RANKING_TTL_SEC = int(os.getenv("ROUTE_RANKING_TTL_SEC", "1800"))
ROUTE_RANKING_TOP_N = int(os.getenv("ROUTE_RANKING_TOP_N", "6"))


_last_hot_reload_check = 0.0
_mtime_env = 0.0
_mtime_cuentas = 0.0


def _verificar_hot_reload() -> None:
    global _last_hot_reload_check, _mtime_env, _mtime_cuentas
    now = time.time()
    if now - _last_hot_reload_check < 5.0:
        return
    _last_hot_reload_check = now

    changed = False
    env_path = os.path.join(RAIZ, ".env")
    cuentas_path = os.path.join(RAIZ, "cuentas.json")

    if os.path.exists(env_path):
        try:
            mt = os.stat(env_path).st_mtime
            if _mtime_env > 0 and mt != _mtime_env:
                changed = True
            _mtime_env = mt
        except Exception:
            pass

    if os.path.exists(cuentas_path):
        try:
            mt = os.stat(cuentas_path).st_mtime
            if _mtime_cuentas > 0 and mt != _mtime_cuentas:
                changed = True
            _mtime_cuentas = mt
        except Exception:
            pass

    if changed:
        print("[proxy] Detectado cambio en .env o cuentas.json. Recargando...")
        try:
            recargar_configuracion()
            rotador_cuentas.cargar_cuentas()
            _desactivar_openrouter_sin_clave()
            _desactivar_cloudflare_sin_clave()
            _desactivar_google_sin_clave()
            _desactivar_cohere_sin_clave()
            _desactivar_siliconflow_sin_clave()
            _desactivar_zhipu_sin_clave()
            _desactivar_groq_sin_clave()
            _desactivar_tokenrouter_sin_clave()
            _desactivar_xkiro_sin_clave()
            _desactivar_tokenharbor_sin_clave()
            _desactivar_compatible_sin_clave()
            _purgar_cache_rutas()
        except Exception as exc:
            print(f"[proxy] Error al recargar configuración: {exc}")


async def _intentar_ultra_fallback(body: dict[str, Any], solicita_stream: bool):
    enabled = os.getenv("ULTRA_FALLBACK_HABILITADO", "false").strip().lower() == "true"
    if not enabled:
        return None

    target_account_id = os.getenv("ULTRA_FALLBACK_CUENTA", "acc1").strip()
    target_model = os.getenv("ULTRA_FALLBACK_MODELO", "qwen2.5-coder:3b").strip()

    cuentas_ollama = rotador_cuentas._cuentas_por_tipo.get("ollama", [])
    cuenta = None
    for c in cuentas_ollama:
        if c.get("id") == target_account_id:
            cuenta = c
            break

    if not cuenta and cuentas_ollama:
        cuenta = cuentas_ollama[0]

    if not cuenta:
        return None

    print(f"[proxy] 🚨 Ejecutando Ultra-Fallback de supervivencia: cuenta={cuenta.get('id')} modelo={target_model}")
    try:
        status_code, content = await forward_request(body, solicita_stream, "ollama", cuenta, target_model, perfil="ultra_fallback")
        if status_code == 200:
            return content
    except Exception as exc:
        print(f"[proxy] Error en Ultra-Fallback: {exc}")

    return None


def _servicios_activos():
    raw = os.getenv("SERVICIOS_ACTIVOS", "").strip()
    todos = {"ollama", "groq", "tokenrouter", "xkiro", "tokenharbor", "apinex", "cloudflare", "nvidia", "openrouter", "google", "cohere", "siliconflow", "zhipu"}
    if not raw:
        return todos
    seleccionados = {x.strip() for x in raw.split(",") if x.strip()}
    # Las capacidades secundarias (por ejemplo ElevenLabs, solo TTS) no
    # pueden entrar en la rotación de proveedores de chat aunque alguien las
    # escriba manualmente en SERVICIOS_ACTIVOS.
    return (seleccionados & todos) or todos


def _top_rotacion():
    raw = os.getenv("ROTACION_TOP_N", "3").strip()
    try:
        with open(os.path.join(RAIZ, "state", "preferencias_ranking.json"), "r", encoding="utf-8") as f:
            raw = str(json.load(f).get("rotacion", {}).get("top_n", raw))
    except (OSError, ValueError, TypeError):
        pass
    try:
        valor = int(raw)
    except Exception:
        valor = 3
    return max(0, valor)



def _cargar_json_seguro(ruta: str, default: dict[str, Any]) -> dict[str, Any]:
    try:
        with open(ruta, "r", encoding="utf-8") as f:
            datos = json.load(f)
        return datos if isinstance(datos, dict) else dict(default)
    except Exception:
        return dict(default)


def _guardar_json_seguro(ruta: str, datos: dict[str, Any]) -> None:
    dir_path = os.path.dirname(ruta)
    os.makedirs(dir_path, exist_ok=True)
    tmp_path = os.path.join(dir_path, f"{os.path.basename(ruta)}.tmp.{os.getpid()}")
    try:
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(datos, f, indent=2, ensure_ascii=False)
        os.replace(tmp_path, ruta)
    except Exception:
        if os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except Exception:
                pass


def _salud_clave(tipo_proveedor: str, modelo_final: str) -> str:
    return f"{tipo_proveedor}:{modelo_final}"


def _cargar_estado_salud() -> dict[str, Any]:
    global _health_state
    _health_state = _cargar_json_seguro(ROUTE_HEALTH_RUTA, {"generado": None, "candidatos": {}})
    _health_state.setdefault("generado", None)
    _health_state.setdefault("candidatos", {})
    return _health_state


def _guardar_estado_salud() -> None:
    _guardar_json_seguro(ROUTE_HEALTH_RUTA, _health_state)


def _salud_entrada(tipo_proveedor: str, modelo_final: str) -> dict[str, Any]:
    clave = _salud_clave(tipo_proveedor, modelo_final)
    with _health_lock:
        entrada = _health_state.setdefault("candidatos", {}).setdefault(clave, {})
        entrada.setdefault("provider", tipo_proveedor)
        entrada.setdefault("model", modelo_final)
        entrada.setdefault("ok_count", 0)
        entrada.setdefault("fail_count", 0)
        entrada.setdefault("ok_streak", 0)
        entrada.setdefault("fail_streak", 0)
        entrada.setdefault("last_ok", 0.0)
        entrada.setdefault("last_fail", 0.0)
        entrada.setdefault("last_latency_ms", 0)
        entrada.setdefault("cooldown_until", 0.0)
        entrada.setdefault("last_error", "")
        entrada.setdefault("last_route", "")
        return entrada


def _purgar_cache_rutas() -> None:
    if os.path.exists(ROUTE_RANKINGS_DIR):
        try:
            for fn in os.listdir(ROUTE_RANKINGS_DIR):
                if fn.startswith("ranking_") and fn.endswith(".json"):
                    try:
                        os.remove(os.path.join(ROUTE_RANKINGS_DIR, fn))
                    except Exception:
                        pass
        except Exception:
            pass


def _salud_registrar(tipo_proveedor: str, modelo_final: str, ok: bool, ruta: str | None = None, latency_ms: int | None = None, status_code: int | None = None, reason: str | None = None) -> None:
    now = time.time()
    with _health_lock:
        entrada = _salud_entrada(tipo_proveedor, modelo_final)
        entrada["provider"] = tipo_proveedor
        entrada["model"] = modelo_final
        entrada["last_route"] = ruta or entrada.get("last_route", "")
        if ok:
            entrada["ok_count"] = int(entrada.get("ok_count", 0)) + 1
            entrada["ok_streak"] = int(entrada.get("ok_streak", 0)) + 1
            entrada["fail_streak"] = 0
            entrada["last_ok"] = now
            entrada["last_error"] = ""
            entrada["cooldown_until"] = 0.0
            if latency_ms is not None:
                entrada["last_latency_ms"] = int(latency_ms)
        else:
            entrada["fail_count"] = int(entrada.get("fail_count", 0)) + 1
            entrada["fail_streak"] = int(entrada.get("fail_streak", 0)) + 1
            entrada["ok_streak"] = 0
            entrada["last_fail"] = now
            if latency_ms is not None:
                entrada["last_latency_ms"] = int(latency_ms)
            entrada["last_error"] = (reason or "")[:240]
            if status_code in (401, 403, 402):
                entrada["cooldown_until"] = now + 3600
            elif status_code in (429, 503):
                entrada["cooldown_until"] = now + 180
            elif status_code in (500, 502, 504):
                entrada["cooldown_until"] = now + 60
            else:
                entrada["cooldown_until"] = now + 90

            if int(entrada.get("fail_streak", 0)) >= 3:
                _purgar_cache_rutas()

        _health_state["generado"] = now
        _guardar_estado_salud()


def _salud_score(tipo_proveedor: str, modelo_final: str) -> float:
    with _health_lock:
        entrada = _salud_entrada(tipo_proveedor, modelo_final)
        now = time.time()
        cooldown = float(entrada.get("cooldown_until", 0.0) or 0.0)
        if cooldown and cooldown > now:
            return -1e9

        score = 0.0
        ok_count = int(entrada.get("ok_count", 0) or 0)
        fail_count = int(entrada.get("fail_count", 0) or 0)
        ok_streak = int(entrada.get("ok_streak", 0) or 0)
        fail_streak = int(entrada.get("fail_streak", 0) or 0)
        last_ok = float(entrada.get("last_ok", 0.0) or 0.0)
        last_fail = float(entrada.get("last_fail", 0.0) or 0.0)
        latency_ms = int(entrada.get("last_latency_ms", 0) or 0)

        if ok_count:
            score += min(ok_count * 2.0, 20.0)
        if fail_count:
            score -= min(fail_count * 1.5, 12.0)
        if ok_streak:
            score += min(ok_streak * 4.0, 16.0)
        if fail_streak:
            score -= min(fail_streak * 12.0, 60.0)
        if last_ok:
            age_min = max(0.0, (now - last_ok) / 60.0)
            score += max(0.0, 12.0 - min(age_min, 12.0))
        if last_fail:
            age_min = max(0.0, (now - last_fail) / 60.0)
            score -= max(0.0, 10.0 - min(age_min, 10.0))
        if latency_ms:
            score += max(0.0, 18.0 - min(latency_ms / 100.0, 18.0))
        return score


def _ruta_cache_path(perfil: str) -> str:
    safe = perfil.replace("/", "_").strip().lower()
    return os.path.join(ROUTE_RANKINGS_DIR, f"ranking_{safe}.json")


def _cargar_cache_ruta(perfil: str) -> dict[str, Any] | None:
    ruta = _ruta_cache_path(perfil)
    if not os.path.exists(ruta):
        return None
    try:
        with open(ruta, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return None
    generado = float(data.get("generado_ts", 0.0) or 0.0)
    if not generado or (time.time() - generado) > ROUTE_RANKING_TTL_SEC:
        return None
    return data if isinstance(data, dict) else None


def _guardar_cache_ruta(perfil: str, ranking: list[dict[str, Any]], origen: str = "global") -> dict[str, Any]:
    top_lim = _top_rotacion()
    data = {
        "perfil": perfil,
        "origen": origen,
        "generado": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "generado_ts": time.time(),
        "ttl_sec": ROUTE_RANKING_TTL_SEC,
        "top_n": top_lim,
        "total": len(ranking),
        "ranking": ranking[:top_lim] if top_lim > 0 else ranking,
    }
    _guardar_json_seguro(_ruta_cache_path(perfil), data)
    return data


def _filtrar_candidatos_por_perfil(body: dict[str, Any], perfil: str) -> list[dict[str, Any]]:
    ranking = gestor_modelos.cargar_ranking_global()
    servicios = _servicios_activos()
    candidatos: list[dict[str, Any]] = []

    for entrada in ranking:
        if entrada.get("proveedor") not in servicios:
            continue
        caps = entrada.get("capacidades", {})
        probe_ok = bool(entrada.get("probe_ok", True))

        if perfil == "cheap":
            if not probe_ok:
                continue
        else:
            if not entrada.get("apto_agente"):
                continue

        if perfil == "reasoning" and not caps.get("reasoning"):
            continue
        if perfil == "tools" and not (caps.get("herramientas") and caps.get("reasoning")):
            continue
        if perfil == "vision" and not caps.get("vision"):
            continue

        candidatos.append(entrada)

    return candidatos


def _ordenar_por_perfil(candidatos: list[dict[str, Any]], perfil: str) -> list[dict[str, Any]]:
    if not candidatos:
        return []

    candidatos_vivos = []
    for entrada in candidatos:
        tipo = entrada.get("proveedor", "")
        modelo = entrada.get("modelo_id") or entrada.get("id") or ""
        if _salud_score(tipo, modelo) <= -1e8:
            continue
        candidatos_vivos.append(entrada)

    base = candidatos_vivos or candidatos

    def key(entrada: dict[str, Any]):
        tipo = entrada.get("proveedor", "")
        modelo = entrada.get("modelo_id") or entrada.get("id") or ""
        salud = _salud_score(tipo, modelo)
        puntaje = float(entrada.get("puntaje", 0) or 0.0)
        params = float(entrada.get("parametros_b", 0.0) or 0.0)
        contexto = int(entrada.get("contexto", 0) or 0)
        if perfil == "cheap":
            return (-salud, params, contexto, -puntaje, str(modelo))
        return (-salud, -puntaje, -contexto, -params, str(modelo))

    return sorted(base, key=key)


def _candidatos_ruta(body: dict[str, Any], perfil: str | None) -> list[dict[str, Any]]:
    perfil = _normalizar_perfil(perfil)
    if perfil is None:
        return []

    cache = _cargar_cache_ruta(perfil)
    if cache is None:
        ranking = _filtrar_candidatos_por_perfil(body, perfil)
        ranking = _ordenar_por_perfil(ranking, perfil)
        cache = _guardar_cache_ruta(perfil, ranking, origen="rebuild")

    ranking = list(cache.get("ranking", []))
    ranking = [r for r in ranking if r.get("proveedor") in _servicios_activos()]
    ranking = _ordenar_por_perfil(ranking, perfil)
    return ranking


def _cargar_estado_salud() -> dict[str, Any]:
    return _cargar_json_seguro(ROUTE_HEALTH_RUTA, {"generado": None, "candidatos": {}})


_health_state = _cargar_estado_salud()


def _requiere_vision(body: dict[str, Any]) -> bool:
    if body.get("modalities") and "image" in body.get("modalities", []):
        return True
    for mensaje in body.get("messages", []):
        if isinstance(mensaje, dict):
            contenido = mensaje.get("content")
            if isinstance(contenido, list):
                for item in contenido:
                    if isinstance(item, dict) and item.get("type") in {"image_url", "input_image"}:
                        return True
            if isinstance(contenido, dict) and contenido.get("type") in {"image_url", "input_image"}:
                return True
    return False


def _requiere_tools(body: dict[str, Any]) -> bool:
    tools = body.get("tools") or []
    tool_choice = body.get("tool_choice")
    return bool(tools) or tool_choice not in (None, "none")


def _normalizar_perfil(valor: Any) -> str | None:
    if valor is None:
        return None
    raw = str(valor).strip().lower()
    if raw in {"", "auto", "default", "general", "balanceado", "balanced", "none"}:
        return None
    if raw in {"cheap", "barato", "low", "lowcost", "economico", "econ", "fast", "rapido", "rápido"}:
        return "cheap"
    if raw in {"reasoning", "razonamiento", "razonar", "think", "reason"}:
        return "reasoning"
    if raw in {"tools", "herramientas", "tool", "agente", "agent"}:
        return "tools"
    if raw in {"vision", "imagen", "images", "image", "visual", "multimodal"}:
        return "vision"
    return None


def _perfil_solicitado(body: dict[str, Any]) -> str | None:
    for key in ("route", "perfil", "profile", "modo", "mode"):
        if key in body:
            return _normalizar_perfil(body.get(key))
    return None


def _limpiar_body_upstream(body: dict[str, Any]) -> dict[str, Any]:
    limpio = dict(body)
    for key in ("route", "perfil", "profile", "modo", "mode"):
        limpio.pop(key, None)
    return limpio


def _texto_mensajes(body: dict[str, Any]) -> str:
    partes = []
    for mensaje in body.get("messages", []):
        if isinstance(mensaje, dict):
            contenido = mensaje.get("content")
            if isinstance(contenido, str):
                partes.append(contenido)
            elif isinstance(contenido, list):
                for item in contenido:
                    if isinstance(item, dict):
                        for clave in ("text", "content", "detail", "caption"):
                            valor = item.get(clave)
                            if isinstance(valor, str):
                                partes.append(valor)
                    elif isinstance(item, str):
                        partes.append(item)
            elif isinstance(contenido, dict):
                for clave in ("text", "content", "detail", "caption"):
                    valor = contenido.get(clave)
                    if isinstance(valor, str):
                        partes.append(valor)
            for clave in ("name", "role"):
                valor = mensaje.get(clave)
                if isinstance(valor, str):
                    partes.append(valor)
    return " ".join(partes).lower()


def _inferir_perfil_por_texto(body: dict[str, Any]) -> str | None:
    texto = _texto_mensajes(body)
    if not texto:
        return None

    if any(p in texto for p in ("imagen", "foto", "photo", "ocr", "vision", "multimodal", "captura", "screenshot")):
        return "vision"
    if any(p in texto for p in ("herramienta", "herramientas", "tool", "tools", "funcion", "function", "json", "api", "agente", "agent", "llama", "call")):
        return "tools"
    if any(p in texto for p in ("razona", "razonamiento", "reasoning", "demuestra", "analiza", "analisis", "compara", "deduce", "paso a paso", "step by step", "prove")):
        return "reasoning"
    if any(p in texto for p in ("resumen", "resum", "sintetiza", "clasifica", "simple", "corto", "rápido", "rapido", "barato", "cheap", "low cost", "borrador", "draft")):
        return "cheap"
    return None


def _orden_proveedores_candidatos(candidatos: list[dict[str, Any]]) -> list[str]:
    orden: list[str] = []
    for entrada in candidatos:
        tipo = entrada.get("proveedor")
        if tipo and tipo not in orden:
            orden.append(tipo)
    return orden


def _orden_proveedores_autobalance(candidatos: list[dict[str, Any]], ultimo: str | None = None) -> list[str]:
    orden = _orden_proveedores_candidatos(candidatos)
    if not orden:
        return []
    if ultimo in orden and len(orden) > 1:
        idx = orden.index(ultimo)
        return orden[idx + 1:] + orden[:idx + 1]
    return orden


def _costo_estimado(entrada: dict[str, Any]) -> tuple[float, float, float, str]:
    parametros = float(entrada.get("parametros_b") or 0.0)
    contexto = float(entrada.get("contexto") or 0.0)
    puntaje = float(entrada.get("puntaje") or 0.0)
    modelo = str(entrada.get("modelo_id") or entrada.get("id") or "")
    return (
        parametros if parametros > 0 else 10_000.0,
        contexto if contexto > 0 else 1_000_000_000.0,
        -puntaje,
        modelo,
    )


def _score_proveedor(tipo: str) -> float:
    conteo = rotador_cuentas.contar_activas_por_tipo().get(tipo, {"activas": 0, "total": 0})
    activas = int(conteo.get("activas", 0))
    total = int(conteo.get("total", 0))
    if total <= 0 or activas <= 0:
        return -999.0

    salud = activas / float(total)
    peso = PESO_PROVEEDOR.get(tipo, 0.6)
    return (activas * 8.0 * peso) + (salud * 20.0 * peso)


def _score_candidato(entrada: dict[str, Any], requiere_vision: bool) -> float:
    if not gestor_modelos.es_apto_agente(entrada, requiere_vision=requiere_vision):
        return -9999.0

    tipo = entrada.get("proveedor", "")
    modelo = entrada.get("modelo_id") or entrada.get("id")
    puntaje_modelo = float(entrada.get("puntaje", 0))
    score_proveedor = _score_proveedor(tipo)
    _, score_cuenta = rotador_cuentas.obtener_mejor_score_tipo(tipo, modelo=modelo)
    score_cuenta = 0.0 if score_cuenta is None else float(score_cuenta)

    # El ranking del modelo manda, pero el estado operativo puede mover la balanza.
    return (puntaje_modelo * 10.0) + score_proveedor + (score_cuenta * 0.2)


def _candidatos_agentes(body: dict[str, Any], perfil: str | None = None) -> list[dict[str, Any]]:
    perfil = _normalizar_perfil(perfil)
    requiere_vision = _requiere_vision(body) or perfil == "vision"

    if perfil is None:
        ranking = gestor_modelos.cargar_ranking_global_agente(
            requiere_vision=requiere_vision,
            servicios_activos=_servicios_activos(),
            top_n=0,
        )
        manual = False
        try:
            with open(os.path.join(RAIZ, "state", "preferencias_ranking.json"), "r", encoding="utf-8") as f:
                manual = bool(json.load(f).get("ordenes", {}).get("general"))
        except (OSError, ValueError, TypeError):
            pass
        if not manual:
            ranking.sort(key=lambda entrada: _score_candidato(entrada, requiere_vision), reverse=True)
        return ranking

    candidatos = _candidatos_ruta(body, perfil)
    if not candidatos:
        return []

    if perfil == "cheap":
        candidatos.sort(key=lambda entrada: (
            -_salud_score(entrada.get("proveedor", ""), entrada.get("modelo_id") or entrada.get("id") or ""),
            float(entrada.get("parametros_b", 0.0) or 0.0),
            int(entrada.get("contexto", 0) or 0),
            -float(entrada.get("puntaje", 0) or 0),
            str(entrada.get("modelo_id") or entrada.get("id") or ""),
        ))
    else:
        candidatos.sort(key=lambda entrada: _score_candidato(entrada, requiere_vision), reverse=True)

    return candidatos


def _resumen_perfiles() -> dict[str, Any]:
    resumen: dict[str, Any] = {}
    for perfil in ("cheap", "reasoning", "tools", "vision"):
        candidatos = _candidatos_ruta({}, perfil)
        if not candidatos:
            continue
        top = candidatos[0]
        resumen[perfil] = {
            "modelo": top.get("modelo_id") or top.get("id"),
            "proveedor": top.get("proveedor"),
            "puntaje": top.get("puntaje"),
            "contexto": top.get("contexto"),
            "parametros_b": top.get("parametros_b"),
        }
    return resumen


def _sse_event(evento: str, payload: dict[str, Any]) -> bytes:
    return f"event: {evento}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n".encode("utf-8")


def _demo_attempt(tipo_proveedor: str, cuenta: dict[str, Any], modelo_final: str) -> dict[str, Any]:
    return {
        "provider": tipo_proveedor,
        "account_id": cuenta.get("id"),
        "model": modelo_final,
    }


def _plan_demo_candidatos(body: dict[str, Any], modelo_pedido: str, perfil: str | None = None) -> list[dict[str, Any]]:
    plan: list[dict[str, Any]] = []

    if modelo_pedido in ("auto", "default", gestor_modelos.MODELO_DEFAULT):
        candidatos = _candidatos_agentes(body, perfil)
        if not candidatos and perfil is not None:
            candidatos = _candidatos_agentes(body)
        if not candidatos:
            return []

        if perfil is None:
            orden_proveedores = _orden_proveedores_autobalance(candidatos, _provider_turn)
            for tipo in orden_proveedores:
                for entrada in candidatos:
                    if entrada.get("proveedor") != tipo:
                        continue
                    modelo_final = entrada.get("modelo_id") or entrada.get("id")
                    cuenta = rotador_cuentas.obtener_cuenta_mejor(tipo, modelo=modelo_final)
                    if not cuenta:
                        continue
                    if modelo_final in rotador_cuentas.obtener_modelos_agotados(cuenta["id"]):
                        continue
                    plan.append({**_demo_attempt(tipo, cuenta, modelo_final), "cuenta": cuenta})
            return plan

        for entrada in candidatos:
            tipo = entrada.get("proveedor")
            modelo_final = entrada.get("modelo_id") or entrada.get("id")
            cuenta = rotador_cuentas.obtener_cuenta_mejor(tipo, modelo=modelo_final)
            if not cuenta:
                continue
            if modelo_final in rotador_cuentas.obtener_modelos_agotados(cuenta["id"]):
                continue
            plan.append({**_demo_attempt(tipo, cuenta, modelo_final), "cuenta": cuenta})
        return plan

    for tipo in rotador_cuentas.obtener_orden_failover():
        modelo_final = rotador_cuentas.traducir_modelo(modelo_pedido, tipo)
        cuenta = rotador_cuentas.obtener_cuenta_mejor(tipo, modelo=modelo_final)
        if not cuenta:
            continue
        if modelo_final in rotador_cuentas.obtener_modelos_agotados(cuenta["id"]):
            continue
        plan.append({**_demo_attempt(tipo, cuenta, modelo_final), "cuenta": cuenta})

    return plan


def _demo_error_final(attempts: list[dict[str, Any]], status_code: int, detail: str, started_at: float) -> dict[str, Any]:
    return {
        "ok": False,
        "latency_ms": int((time.perf_counter() - started_at) * 1000),
        "error": {
            "status": status_code,
            "detail": detail,
        },
        "attempts": attempts,
    }


async def _demo_responder_json(body: dict[str, Any], modelo_pedido: str) -> JSONResponse:
    global _provider_turn
    started_at = time.perf_counter()
    attempts: list[dict[str, Any]] = []
    perfil = _perfil_solicitado(body)
    plan = _plan_demo_candidatos(body, modelo_pedido, perfil)
    if not plan:
        return JSONResponse(_demo_error_final(attempts, 503, "Sin candidatos disponibles.", started_at), status_code=503)

    async with httpx.AsyncClient() as client:
        for candidato in plan:
            tipo_proveedor = candidato["provider"]
            cuenta = candidato["cuenta"]
            modelo_final = candidato["model"]
            cid = cuenta["id"]

            check_rate = limitador_tasa.reservar(cid)
            if not check_rate:
                attempts.append({**candidato, "status": 503, "reason": check_rate.razon})
                continue

            proveedor = crear_proveedor(cuenta, tipo_proveedor)
            url = proveedor.construir_url()
            headers = proveedor.construir_headers()
            body_preparado = proveedor.preparar_body(_limpiar_body_upstream(body), modelo_final)
            timeout = 120.0 if tipo_proveedor in ("openrouter", "nvidia", "xkiro", "tokenharbor") else 60.0

            try:
                resp = await client.post(url, json=body_preparado, headers=headers, timeout=timeout)
            except httpx.RequestError as exc:
                rotador_cuentas.registrar_fallo(cid, 500, modelo_final, razon=str(exc))
                attempts.append({**candidato, "status": 500, "reason": str(exc)[:240]})
                continue

            if resp.status_code != 200:
                detalle = resp.text[:240]
                rotador_cuentas.registrar_fallo(cid, resp.status_code, modelo_final, razon=detalle)
                if resp.status_code == 403:
                    rotador_cuentas.marcar_modelo_agotado(cid, modelo_final)
                attempts.append({**candidato, "status": resp.status_code, "reason": detalle})
                if resp.status_code in (401, 403, 402, 429, 503, 500):
                    continue
                break

            datos = resp.json()
            if tipo_proveedor == "anthropic":
                datos = proveedor.normalizar_respuesta(datos)
            datos_norm = normalizador_stream.normalizar_respuesta_completa(datos)
            usage = datos.get("usage", {})
            prompt_t = usage.get("prompt_tokens", 0)
            completion_t = usage.get("completion_tokens", 0)
            registrador.registrar_uso(cid, modelo_final, prompt_t, completion_t)
            registrador.guardar_contadores()
            rotador_cuentas.registrar_exito(cid, modelo_final)
            if modelo_pedido in ("auto", "default", gestor_modelos.MODELO_DEFAULT):
                _provider_turn = tipo_proveedor

            return JSONResponse({
                "ok": True,
                "reply": datos_norm.get("choices", [{}])[0].get("message", {}).get("content", ""),
                "model": modelo_final,
                "provider": tipo_proveedor,
                "account_id": cid,
                "latency_ms": int((time.perf_counter() - started_at) * 1000),
                "usage": usage,
                "attempts": attempts + [{**candidato, "status": 200}],
            })

    return JSONResponse(_demo_error_final(attempts, 503, "Reintentos agotados.", started_at), status_code=503)


async def _demo_responder_stream(body: dict[str, Any], modelo_pedido: str):
    global _provider_turn
    started_at = time.perf_counter()
    attempts: list[dict[str, Any]] = []
    perfil = _perfil_solicitado(body)
    plan = _plan_demo_candidatos(body, modelo_pedido, perfil)
    if not plan:
        yield _sse_event("error", _demo_error_final(attempts, 503, "Sin candidatos disponibles.", started_at))
        return

    async with httpx.AsyncClient() as client:
        for candidato in plan:
            tipo_proveedor = candidato["provider"]
            cuenta = candidato["cuenta"]
            modelo_final = candidato["model"]
            cid = cuenta["id"]

            check_rate = limitador_tasa.reservar(cid)
            if not check_rate:
                attempts.append({**candidato, "status": 503, "reason": check_rate.razon})
                continue

            proveedor = crear_proveedor(cuenta, tipo_proveedor)
            url = proveedor.construir_url()
            headers = proveedor.construir_headers()
            body_preparado = proveedor.preparar_body(_limpiar_body_upstream(body), modelo_final)
            timeout = 120.0 if tipo_proveedor in ("openrouter", "nvidia", "xkiro", "tokenharbor") else 60.0
            reply_parts: list[str] = []

            try:
                async with client.stream("POST", url, json=body_preparado, headers=headers, timeout=timeout) as resp:
                    if resp.status_code != 200:
                        cuerpo_err = await resp.aread()
                        detalle = cuerpo_err.decode(errors="ignore")[:240]
                        rotador_cuentas.registrar_fallo(cid, resp.status_code, modelo_final, razon=detalle)
                        if resp.status_code == 403:
                            rotador_cuentas.marcar_modelo_agotado(cid, modelo_final)
                        attempts.append({**candidato, "status": resp.status_code, "reason": detalle})
                        continue

                    yield _sse_event("meta", {
                        "ok": True,
                        "model": modelo_final,
                        "provider": tipo_proveedor,
                        "account_id": cid,
                    })

                    normalizador_stream.resetear_contadores()
                    async for line in resp.aiter_lines():
                        if not line:
                            continue
                        if line.strip() in {"data: [DONE]", "[DONE]"}:
                            break
                        sse_line = normalizador_stream.normalizar_linea_sse(line)
                        if not sse_line or not sse_line.startswith("data: "):
                            continue
                        chunk = sse_line[6:]
                        if chunk == "[DONE]":
                            break
                        try:
                            payload = json.loads(chunk)
                        except Exception:
                            continue
                        delta = payload.get("choices", [{}])[0].get("delta", {})
                        piece = delta.get("content")
                        if piece:
                            reply_parts.append(piece)
                        yield _sse_event("delta", payload)

                    reply_final = "".join(reply_parts)
                    yield _sse_event("done", {
                        "ok": True,
                        "reply": reply_final,
                        "model": modelo_final,
                        "provider": tipo_proveedor,
                        "account_id": cid,
                        "latency_ms": int((time.perf_counter() - started_at) * 1000),
                        "attempts": attempts + [{**candidato, "status": 200}],
                    })
                    registrador.registrar_uso(cid, modelo_final, 0, 0)
                    registrador.guardar_contadores()
                    rotador_cuentas.registrar_exito(cid, modelo_final)
                    if modelo_pedido in ("auto", "default", gestor_modelos.MODELO_DEFAULT):
                        _provider_turn = tipo_proveedor
                    return
            except httpx.RequestError as exc:
                rotador_cuentas.registrar_fallo(cid, 500, modelo_final, razon=str(exc))
                attempts.append({**candidato, "status": 500, "reason": str(exc)[:240]})
                continue

    yield _sse_event("error", _demo_error_final(attempts, 503, "Reintentos agotados.", started_at))


@app.get("/demo", response_class=HTMLResponse)
def demo():
    if os.path.exists(UI_DEMO_PATH):
        with open(UI_DEMO_PATH, "r", encoding="utf-8") as f:
            return HTMLResponse(f.read())
    return HTMLResponse("<h1>Demo no encontrada</h1>", status_code=404)


@app.post("/api/demo/chat")
async def demo_chat(request: Request):
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"ok": False, "error": {"status": 400, "detail": "JSON invalido"}}, status_code=400)

    modelo_pedido = body.get("model", "auto")
    solicita_stream = bool(body.get("stream", True))

    if solicita_stream:
        return StreamingResponse(_demo_responder_stream(body, modelo_pedido), media_type="text/event-stream")
    return await _demo_responder_json(body, modelo_pedido)




@app.get("/status")
def status():
    return {
        "cuentas": rotador_cuentas.obtener_estado_general(),
        "activas_por_tipo": rotador_cuentas.contar_activas_por_tipo(),
        "orden_failover": rotador_cuentas.obtener_orden_failover(),
        "servicios_activos": sorted(_servicios_activos()),
        "rotacion_top_n": _top_rotacion(),
        "mapeo_modelos": rotador_cuentas.obtener_mapeo_modelos(),
        "perfiles_sugeridos": _resumen_perfiles(),
        "salud_rutas": {
            k: {
                "ok_count": v.get("ok_count", 0),
                "fail_count": v.get("fail_count", 0),
                "ok_streak": v.get("ok_streak", 0),
                "fail_streak": v.get("fail_streak", 0),
                "last_latency_ms": v.get("last_latency_ms", 0),
                "cooldown_until": v.get("cooldown_until", 0),
                "last_error": v.get("last_error", ""),
            }
            for k, v in _health_state.get("candidatos", {}).items()
        },
        "resumen_uso": registrador.obtener_resumen(),
    }


@app.get("/rankings")
def rankings():
    return gestor_modelos.resumen_rankings()


@app.get("/v1/models")
@app.get("/models")
def list_models():
    """
    Endpoint estándar OpenAI para validar conexión y exponer rutas virtuales.
    Solo expone las rutas automáticas (auto, cheap, reasoning, tools, vision)
    para forzar que los agentes siempre usen la rotación automática inteligente.
    """
    return {
        "object": "list",
        "data": [
            {"id": "auto", "object": "model", "created": 1700000000, "owned_by": "nucleo-ia"},
            {"id": "cheap", "object": "model", "created": 1700000000, "owned_by": "nucleo-ia"},
            {"id": "reasoning", "object": "model", "created": 1700000000, "owned_by": "nucleo-ia"},
            {"id": "tools", "object": "model", "created": 1700000000, "owned_by": "nucleo-ia"},
            {"id": "vision", "object": "model", "created": 1700000000, "owned_by": "nucleo-ia"},
        ]
    }


@app.get("/v1/models/{model_id:path}")
@app.get("/models/{model_id:path}")
def get_model_info(model_id: str):
    return {
        "id": model_id,
        "object": "model",
        "created": 1700000000,
        "owned_by": "nucleo-ia"
    }


def _elevenlabs_capacidad_permitida(capacidad: str) -> bool:
    """Respeta la autorización local de la cuenta compartida de ElevenLabs."""
    data = _cargar_json_seguro(os.path.join(RAIZ, "cuentas.json"), {})
    rows = data.get("proveedores", {}).get("elevenlabs", {}).get("cuentas", [])
    for account in rows:
        if not isinstance(account, dict) or account.get("habilitado") is False:
            continue
        enabled = account.get("capacidades_habilitadas", ["speech_generation"])
        if isinstance(enabled, list) and capacidad in enabled:
            return True
    return False


def _speechify_cuentas():
    """Lista credenciales TTS guardadas fuera del JSON, conservando orden de cuentas."""
    data = _cargar_json_seguro(os.path.join(RAIZ, "cuentas.json"), {})
    rows = data.get("proveedores", {}).get("speechify", {}).get("cuentas", [])
    env = dict(os.environ)
    env.update(_parse_env_file(os.path.join(RAIZ, ".env")))
    cuentas = []
    for row in rows:
        if not isinstance(row, dict) or row.get("habilitado") is False:
            continue
        suffix = "".join(ch if ch.isalnum() else "_" for ch in str(row.get("id", "")).upper()).strip("_")
        key = env.get(f"SPEECHIFY_API_KEY_{suffix}") or env.get("SPEECHIFY_API_KEY", "")
        if key and row.get("conexion_estado") == "acceso_comprobado":
            cuentas.append((row, key))
    if not rows and env.get("SPEECHIFY_API_KEY"):
        cuentas.append(({"id": "speechify_env", "nombre": "Speechify"}, env["SPEECHIFY_API_KEY"]))
    global _speechify_rotation_index
    if cuentas:
        with _speechify_rotation_lock:
            start = _speechify_rotation_index % len(cuentas)
            _speechify_rotation_index = (start + 1) % len(cuentas)
        cuentas = cuentas[start:] + cuentas[:start]
    return cuentas


@app.get("/v1/capabilities")
def capabilities():
    """Describe qué capacidades están configuradas sin intentar proveedores."""
    cuentas = rotador_cuentas.contar_activas_por_tipo()
    configurados = set()
    for tipo, datos in cuentas.items():
        if not datos.get("habilitado") or datos.get("activas", 0) <= 0:
            continue
        for cuenta in rotador_cuentas.obtener_todas_cuentas_tipo(tipo):
            try:
                proveedor = crear_proveedor(cuenta, tipo)
                if getattr(proveedor, "tiene_credencial_valida", lambda: True)():
                    configurados.add(tipo)
                    break
            except Exception:
                continue
    edge_disponible = importlib.util.find_spec("edge_tts") is not None
    eleven_disponible = bool(os.getenv("ELEVENLABS_API_KEY", "").strip()) and _elevenlabs_capacidad_permitida("speech_generation")
    speechify_disponible = bool(_speechify_cuentas())
    vision_models = set()
    for proveedor in configurados:
        datos_ranking = _cargar_json_seguro(os.path.join(RAIZ, "state", f"ranking_{proveedor}.json"), {})
        for fila in datos_ranking.get("ranking", []):
            if fila.get("probe_ok") is True and (fila.get("capacidades") or {}).get("vision") is True:
                vision_models.add(proveedor)
    providers_by_capability = {
        "vision_image": sorted(vision_models),
        "vision_video": [],
        "transcription_audio": [p for p in ("groq",) if p in configurados],
        "speech_generation": (["edge_tts"] if edge_disponible else []) +
                             (["elevenlabs"] if eleven_disponible else []) +
                             (["speechify"] if speechify_disponible else []) +
                             [p for p in ("siliconflow", "groq") if p in configurados],
        "voice_cloning": [],
        "sound_effects": [],
        "image_generation": [p for p in ("siliconflow", "zhipu", "cloudflare") if p in configurados],
        "image_editing": [],
        "video_generation_text": [p for p in ("zhipu", "siliconflow") if p in configurados],
        "video_generation_image": [p for p in ("zhipu", "siliconflow") if p in configurados],
        "video_editing": [],
        "lip_sync": [],
        "embeddings": [p for p in ("cohere", "siliconflow") if p in configurados],
        "parse_documents": [],
        "reranking": [p for p in ("cohere",) if p in configurados],
        "music_generation": ["mock_music"] if os.getenv("NUCLEO_MUSIC_MOCK", "") == "1" else [],
    }
    routes = {
        "vision_image": "/v1/chat/completions", "transcription_audio": "/v1/audio/transcriptions",
        "speech_generation": "/v1/audio/speech", "image_generation": "/v1/images/generations",
        "video_generation_text": "/v1/videos/generations",
        "video_generation_image": "/v1/videos/generations", "embeddings": "/v1/embeddings",
        "music_generation": "/v1/music/generations",
    }
    detailed = {key: {"label": label, "enabled": bool(providers_by_capability.get(key)),
                      "providers": providers_by_capability.get(key, []), "route": routes.get(key)}
                for key, label in CAPACIDADES.items()}
    # Catálogos de capacidades descubiertos por /models se exponen aparte de
    # las rutas realmente conectadas. Así no se presenta como utilizable una
    # tarea para la que todavía no existe adaptador upstream.
    ranking_global_data = _cargar_json_seguro(os.path.join(RAIZ, "state", "ranking_global.json"), {})
    discovered = ranking_global_data.get("rankings_capacidades", {}) if isinstance(ranking_global_data, dict) else {}
    for cap_id, details in detailed.items():
        details["catalogo_descubierto"] = {
            proveedor: rows.get(cap_id, [])
            for proveedor, rows in discovered.items()
            if isinstance(rows, dict) and rows.get(cap_id)
        }
    return {
        "object": "capabilities",
        "capabilities": detailed,
        "chat": {"enabled": bool(configurados), "providers": sorted(configurados)},
        "vision": {"enabled": bool(configurados), "providers": sorted(configurados), "route": "chat.completions"},
        "transcriptions": {"enabled": bool(providers_by_capability["transcription_audio"]), "providers": providers_by_capability["transcription_audio"], "provider": (providers_by_capability["transcription_audio"] or [None])[0]},
        "images": {"enabled": bool(providers_by_capability["image_generation"]), "providers": providers_by_capability["image_generation"], "provider": (providers_by_capability["image_generation"] or [None])[0]},
        "speech": {"enabled": bool(providers_by_capability["speech_generation"]), "providers": providers_by_capability["speech_generation"]},
        "speech_secondary_providers": (["elevenlabs"] if os.getenv("ELEVENLABS_API_KEY", "").strip() else []),
        "embeddings": {
            "enabled": bool({"cohere", "siliconflow"} & configurados),
            "providers": [p for p in ["cohere", "siliconflow"] if p in configurados],
            "provider": "cohere" if "cohere" in configurados else "siliconflow",
        },
        "video": {"enabled": bool(providers_by_capability["video_generation_text"]), "providers": providers_by_capability["video_generation_text"], "provider": (providers_by_capability["video_generation_text"] or [None])[0]},
        "multimedia_pending": {
            "enabled": False,
            "providers": ["cloudflare", "google", "xkiro", "tokenrouter", "tokenharbor"],
            "reason": "Proveedor con capacidad publicada, pero sin adaptador multimedia verificado en Núcleo IA.",
        },
    }


@app.post("/v1/responses")
async def responses_compatibility(request: Request):
    return await chat_completions(request)


@app.api_route("/api/show", methods=["GET", "POST"])
@app.api_route("/api/tags", methods=["GET", "POST"])
@app.api_route("/v1/props", methods=["GET", "POST"])
@app.api_route("/props", methods=["GET", "POST"])
@app.api_route("/version", methods=["GET", "POST"])
def client_probing_compatibility():
    return {"status": "ok", "version": "1.0.0", "models": ["auto", "tools", "reasoning", "vision", "cheap"]}


def _cuentas_con_credencial(tipo: str, modelo: str | None = None, capacidad: str | None = None):
    """Devuelve cuentas ordenadas cuya credencial puede resolverse localmente, respetando cuenta preferida si se indica modelo."""
    resultado = []
    for cuenta in rotador_cuentas.obtener_cuentas_ordenadas(tipo, modelo=modelo):
        if capacidad and not candidato_permitido(cuenta, canonica(capacidad), pago=tipo in PROVEEDORES_OPCIONALES):
            continue
        try:
            proveedor = crear_proveedor(cuenta, tipo)
            if getattr(proveedor, "tiene_credencial_valida", lambda: True)():
                resultado.append((cuenta, proveedor))
        except Exception:
            continue
    return resultado


def _registrar_capacidad_ok(cuenta, modelo: str):
    registrador.registrar_uso(cuenta["id"], modelo, 0, 0)
    registrador.guardar_contadores()
    rotador_cuentas.registrar_exito(cuenta["id"], modelo)


def _registrar_capacidad_fallo(cuenta, modelo: str, status_code: int, detalle: str):
    rotador_cuentas.registrar_fallo(cuenta["id"], status_code, modelo, razon=detalle[:240])
    if status_code in (401, 402):
        rotador_cuentas.bloquear_cuenta(cuenta["id"], razon=f"capacidad_{status_code}")
    elif status_code in (403, 404, 410):
        rotador_cuentas.marcar_modelo_agotado(cuenta["id"], modelo)


def _es_reintentable_capacidad(status_code: int) -> bool:
    return status_code in (401, 402, 403, 404, 408, 409, 410, 429, 500, 502, 503, 504)


def _valor_salida_utilizable(valor: Any) -> bool:
    """Indica si un campo de salida contiene algo consumible por el cliente."""
    if isinstance(valor, str):
        return bool(valor.strip())
    if isinstance(valor, list):
        return any(_valor_salida_utilizable(item) for item in valor)
    if isinstance(valor, dict):
        return bool(valor)
    return False


def _mensaje_utilizable(mensaje: Any) -> bool:
    if not isinstance(mensaje, dict):
        return False
    if _valor_salida_utilizable(mensaje.get("content")):
        return True
    if _valor_salida_utilizable(mensaje.get("refusal")):
        return True
    if _valor_salida_utilizable(mensaje.get("audio")):
        return True
    if _valor_salida_utilizable(mensaje.get("tool_calls")):
        return True
    if _valor_salida_utilizable(mensaje.get("function_call")):
        return True
    return False


def _respuesta_completa_utilizable(datos: Any) -> bool:
    """Acepta texto o salidas estructuradas, pero rechaza un HTTP 200 vacío."""
    if not isinstance(datos, dict) or datos.get("error"):
        return False
    choices = datos.get("choices")
    if not isinstance(choices, list) or not choices:
        return False
    for choice in choices:
        if not isinstance(choice, dict):
            continue
        if _mensaje_utilizable(choice.get("message")):
            return True
        if _valor_salida_utilizable(choice.get("text")):
            return True
    return False


def _chunk_stream_utilizable(linea_sse: str | None) -> bool:
    """Detecta el primer delta útil antes de abrir el stream al cliente."""
    if not linea_sse or not linea_sse.startswith("data: "):
        return False
    contenido = linea_sse[6:].strip()
    if not contenido or contenido == "[DONE]":
        return False
    try:
        datos = json.loads(contenido)
    except (TypeError, json.JSONDecodeError):
        return False
    choices = datos.get("choices") if isinstance(datos, dict) else None
    if not isinstance(choices, list):
        return False
    for choice in choices:
        if not isinstance(choice, dict):
            continue
        if _mensaje_utilizable(choice.get("delta")):
            return True
        if _mensaje_utilizable(choice.get("message")):
            return True
        if _valor_salida_utilizable(choice.get("text")):
            return True
    return False



async def forward_request(request_body, stream, tipo_proveedor, cuenta, modelo_final, perfil: str | None = None):
    started_at = time.perf_counter()
    cid = cuenta["id"]
    check_rate = limitador_tasa.reservar(cid)
    if not check_rate:
        return 429, {
                "error": "rate_limited",
                "provider": tipo_proveedor,
                "account_id": cid,
                "model": modelo_final,
                "reason": check_rate.razon,
                "wait_seconds": check_rate.espera_seg,
            }

    proveedor = crear_proveedor(cuenta, tipo_proveedor)
    url = proveedor.construir_url()
    headers = proveedor.construir_headers()
    try:
        politicas.validar_envio(tipo_proveedor, modelo_final, url)
    except politicas.EnvioNoPermitido as exc:
        return 403, {"error": "policy_denied", "message": str(exc)}
    body_preparado = proveedor.preparar_body(_limpiar_body_upstream(request_body), modelo_final)

    print(f"[proxy] Despachando a {proveedor.identificar()} modelo={modelo_final}")
    timeout = 120.0 if tipo_proveedor in ("openrouter", "nvidia", "xkiro", "tokenharbor") else 60.0
    client = get_http_client()

    if stream:
        try:
            req = client.build_request(
                "POST",
                url,
                json=body_preparado,
                headers=headers,
                timeout=timeout,
            )
            r = await client.send(req, stream=True)
            if r.status_code != 200:
                cuerpo_err = await r.aread()
                await r.aclose()
                _salud_registrar(tipo_proveedor, modelo_final, False, ruta=perfil, status_code=r.status_code, reason=cuerpo_err.decode(errors="ignore")[:240])
                return r.status_code, {
                    "error": "upstream_error",
                    "provider": proveedor.identificar(),
                    "upstream_status": r.status_code,
                    "body": cuerpo_err.decode(errors="ignore")[:240],
                }

            normalizador_stream.resetear_contadores()
            lineas = r.aiter_lines()
            prefijo: list[bytes] = []
            stream_utilizable = False
            try:
                async for line in lineas:
                    if not line:
                        continue
                    sse_line = normalizador_stream.normalizar_linea_sse(line)
                    if sse_line:
                        prefijo.append((sse_line + "\n\n").encode())
                        if _chunk_stream_utilizable(sse_line):
                            stream_utilizable = True
                            break
                    if line.strip() in {"data: [DONE]", "[DONE]"}:
                        break
            except Exception as exc:
                await r.aclose()
                _salud_registrar(tipo_proveedor, modelo_final, False, ruta=perfil, status_code=502, reason=str(exc)[:240])
                return 502, {
                    "error": "invalid_upstream_stream",
                    "provider": proveedor.identificar(),
                    "message": str(exc)[:240],
                }

            if not stream_utilizable:
                await r.aclose()
                razon = "El proveedor devolvió HTTP 200 pero el stream no contenía salida utilizable."
                _salud_registrar(tipo_proveedor, modelo_final, False, ruta=perfil, status_code=502, reason=razon)
                return 502, {
                    "error": "empty_upstream_response",
                    "provider": proveedor.identificar(),
                    "upstream_status": 200,
                    "message": razon,
                }

            async def stream_generator():
                try:
                    for chunk in prefijo:
                        yield chunk
                    async for line in lineas:
                        if not line:
                            continue
                        sse_line = normalizador_stream.normalizar_linea_sse(line)
                        if sse_line:
                            yield (sse_line + "\n\n").encode()

                    yield normalizador_stream.inyectar_finish(modelo_final).encode()
                    registrador.registrar_uso(cid, modelo_final, 0, 0)
                    registrador.guardar_contadores()
                    rotador_cuentas.registrar_exito(cid, modelo_final)
                    _salud_registrar(tipo_proveedor, modelo_final, True, ruta=perfil)
                except Exception as e:
                    rotador_cuentas.registrar_fallo(cid, 500, modelo_final, razon=str(e))
                    _salud_registrar(tipo_proveedor, modelo_final, False, ruta=perfil, status_code=500, reason=str(e)[:240])
                    error_sse = {"error": {"type": "stream_error", "message": "El flujo del proveedor se interrumpió."}}
                    yield ("data: " + json.dumps(error_sse, ensure_ascii=False) + "\n\n").encode()
                finally:
                    await r.aclose()

            return 200, StreamingResponse(stream_generator(), media_type="text/event-stream")
        except Exception as exc:
            _salud_registrar(tipo_proveedor, modelo_final, False, ruta=perfil, status_code=500, reason=str(exc)[:240])
            return 500, {
                "error": "connection_error",
                "provider": proveedor.identificar(),
                "message": str(exc),
            }

    try:
        resp = await client.post(
            url,
            json=body_preparado,
            headers=headers,
            timeout=timeout,
        )
        if resp.status_code != 200:
            return resp.status_code, {
                "error": "upstream_error",
                "provider": proveedor.identificar(),
                "upstream_status": resp.status_code,
                "body": resp.text[:240],
            }

        try:
            datos = resp.json()
        except (TypeError, ValueError, json.JSONDecodeError) as exc:
            razon = f"El proveedor devolvió HTTP 200 con JSON inválido: {exc}"
            _salud_registrar(tipo_proveedor, modelo_final, False, ruta=perfil, status_code=502, reason=razon[:240])
            return 502, {
                "error": "invalid_upstream_response",
                "provider": proveedor.identificar(),
                "upstream_status": 200,
                "message": razon[:240],
            }
        datos_norm = normalizador_stream.normalizar_respuesta_completa(datos)

        if not _respuesta_completa_utilizable(datos_norm):
            razon = "El proveedor devolvió HTTP 200 pero no incluyó una salida utilizable."
            _salud_registrar(tipo_proveedor, modelo_final, False, ruta=perfil, status_code=502, reason=razon)
            return 502, {
                "error": "empty_upstream_response",
                "provider": proveedor.identificar(),
                "upstream_status": 200,
                "message": razon,
            }

        usage = datos.get("usage", {})
        prompt_t = usage.get("prompt_tokens", 0)
        completion_t = usage.get("completion_tokens", 0)

        registrador.registrar_uso(cid, modelo_final, prompt_t, completion_t)
        registrador.guardar_contadores()
        rotador_cuentas.registrar_exito(cid, modelo_final)
        _salud_registrar(tipo_proveedor, modelo_final, True, ruta=perfil, latency_ms=int((time.perf_counter() - started_at) * 1000))

        return 200, datos_norm
    except httpx.RequestError as exc:
        _salud_registrar(tipo_proveedor, modelo_final, False, ruta=perfil, status_code=500, reason=str(exc)[:240])
        return 500, {
            "error": "connection_error",
            "provider": proveedor.identificar(),
            "message": str(exc),
        }



_account_turn_by_model: dict[str, int] = {}
_model_turn = 0


def _modo_rotacion() -> str:
    raw = os.getenv("MODO_ROTACION", "modelos").strip().lower()
    try:
        with open(os.path.join(RAIZ, "state", "preferencias_ranking.json"), "r", encoding="utf-8") as f:
            ui_mode = json.load(f).get("rotacion", {}).get("modo")
        raw = {"prioridad": "cascada", "rotar_cuentas": "cuentas_primero", "rotar_top": "modelos"}.get(ui_mode, raw)
    except (OSError, ValueError, TypeError):
        pass
    if raw in {"cuentas_primero", "cuentas", "accounts_first", "exprimir_cuentas"}:
        return "cuentas_primero"
    if raw in {"proveedores", "proveedor", "providers", "intercalado"}:
        return "proveedores"
    if raw in {"velocidad", "latencia", "speed", "latency", "fastest"}:
        return "velocidad"
    if raw in {"cascada", "failover", "waterfall", "estricto"}:
        return "cascada"
    return "modelos"


async def _procesar_autoranking(body: dict[str, Any], solicita_stream: bool, perfil: str | None = None):
    global _provider_turn, _account_turn_by_model, _model_turn
    candidatos = _candidatos_agentes(body, perfil)
    if not candidatos:
        return None

    modo = _modo_rotacion()

    if perfil is not None:
        for entrada in candidatos:
            tipo = entrada.get("proveedor")
            modelo_final = entrada.get("modelo_id") or entrada.get("id")
            cuenta = rotador_cuentas.obtener_cuenta_mejor(tipo, modelo=modelo_final)
            if not cuenta:
                continue
            cid = cuenta["id"]
            if modelo_final in rotador_cuentas.obtener_modelos_agotados(cid):
                continue
            status_code, content = await forward_request(body, solicita_stream, tipo, cuenta, modelo_final, perfil)
            if status_code == 200:
                return content
            rotador_cuentas.registrar_fallo(cid, status_code, modelo_final, razon=str(content)[:240])
            if status_code in (401, 403, 402):
                rotador_cuentas.marcar_modelo_agotado(cid, modelo_final)
            if status_code in (429, 503, 500):
                continue
        return None

    # ── MODO E: CASCADA ESTRICTA (Priority Waterfall) ──────────────────────
    if modo == "cascada":
        for entrada in candidatos:
            tipo = entrada.get("proveedor")
            modelo_final = entrada.get("modelo_id") or entrada.get("id")
            cuentas = rotador_cuentas.obtener_todas_cuentas_tipo(tipo, modelo=modelo_final)
            for cuenta in cuentas:
                cid = cuenta["id"]
                if modelo_final in rotador_cuentas.obtener_modelos_agotados(cid):
                    continue
                status_code, content = await forward_request(body, solicita_stream, tipo, cuenta, modelo_final, perfil)
                if status_code == 200:
                    return content
                rotador_cuentas.registrar_fallo(cid, status_code, modelo_final, razon=str(content)[:240])
                if status_code in (401, 403, 402):
                    rotador_cuentas.marcar_modelo_agotado(cid, modelo_final)
        return None

    # ── MODO B: CUENTAS PRIMERO (Exhaustive Account Rotation per Model) ────
    if modo == "cuentas_primero":
        for entrada in candidatos:
            tipo = entrada.get("proveedor")
            modelo_final = entrada.get("modelo_id") or entrada.get("id")
            cuentas_disponibles = rotador_cuentas.obtener_todas_cuentas_tipo(tipo, modelo=modelo_final)
            if not cuentas_disponibles:
                continue
            
            turn_idx = _account_turn_by_model.get(modelo_final, 0)
            if turn_idx >= len(cuentas_disponibles):
                turn_idx = 0
            
            cuentas_ordenadas = cuentas_disponibles[turn_idx:] + cuentas_disponibles[:turn_idx]
            
            for cuenta in cuentas_ordenadas:
                cid = cuenta["id"]
                if modelo_final in rotador_cuentas.obtener_modelos_agotados(cid):
                    continue
                status_code, content = await forward_request(body, solicita_stream, tipo, cuenta, modelo_final, perfil)
                if status_code == 200:
                    idx_real = cuentas_disponibles.index(cuenta)
                    _account_turn_by_model[modelo_final] = (idx_real + 1) % len(cuentas_disponibles)
                    return content
                rotador_cuentas.registrar_fallo(cid, status_code, modelo_final, razon=str(content)[:240])
                if status_code in (401, 403, 402):
                    rotador_cuentas.marcar_modelo_agotado(cid, modelo_final)
                continue
        return None

    # ── MODO D: VELOCIDAD (Lowest Latency First) ──────────────────────────
    if modo == "velocidad":
        def latencia_key(e):
            tipo = e.get("proveedor", "")
            modelo = e.get("modelo_id") or e.get("id") or ""
            salud = _salud_entrada(tipo, modelo)
            lat = int(salud.get("last_latency_ms", 999999) or 999999)
            return (lat, -float(e.get("puntaje", 0) or 0))

        candidatos_velocidad = sorted(candidatos, key=latencia_key)
        for entrada in candidatos_velocidad:
            tipo = entrada.get("proveedor")
            modelo_final = entrada.get("modelo_id") or entrada.get("id")
            cuenta = rotador_cuentas.obtener_cuenta_mejor(tipo, modelo=modelo_final)
            if not cuenta:
                continue
            cid = cuenta["id"]
            if modelo_final in rotador_cuentas.obtener_modelos_agotados(cid):
                continue
            status_code, content = await forward_request(body, solicita_stream, tipo, cuenta, modelo_final, perfil)
            if status_code == 200:
                return content
            rotador_cuentas.registrar_fallo(cid, status_code, modelo_final, razon=str(content)[:240])
            if status_code in (401, 403, 402):
                rotador_cuentas.marcar_modelo_agotado(cid, modelo_final)
            continue
        return None

    # ── MODO C: PROVEEDORES (Interleaved Provider Rotation) ────────────────
    if modo == "proveedores":
        candidatos_por_prov = {}
        for e in candidatos:
            p = e.get("proveedor")
            if p and p not in candidatos_por_prov:
                candidatos_por_prov[p] = e

        cand_prov_list = list(candidatos_por_prov.values())
        orden_proveedores = _orden_proveedores_autobalance(cand_prov_list, _provider_turn)

        for prov_tipo in orden_proveedores:
            entrada = candidatos_por_prov.get(prov_tipo)
            if not entrada:
                continue
            modelo_final = entrada.get("modelo_id") or entrada.get("id")
            cuenta = rotador_cuentas.obtener_cuenta_mejor(prov_tipo, modelo=modelo_final)
            if not cuenta:
                continue
            cid = cuenta["id"]
            if modelo_final in rotador_cuentas.obtener_modelos_agotados(cid):
                continue
            status_code, content = await forward_request(body, solicita_stream, prov_tipo, cuenta, modelo_final, perfil)
            if status_code == 200:
                _provider_turn = prov_tipo
                return content
            rotador_cuentas.registrar_fallo(cid, status_code, modelo_final, razon=str(content)[:240])
            if status_code in (401, 403, 402):
                rotador_cuentas.marcar_modelo_agotado(cid, modelo_final)
            continue
        return None

    # Rotación literal entre puestos. Un cero incluye el ranking completo.
    limite = _top_rotacion()
    participantes = candidatos[:limite] if limite > 0 else candidatos
    if not participantes:
        return None
    inicio = _model_turn % len(participantes)
    ordenados = participantes[inicio:] + participantes[:inicio]
    for entrada in ordenados:
        tipo = entrada.get("proveedor")
        modelo_final = entrada.get("modelo_id") or entrada.get("id")
        cuentas = rotador_cuentas.obtener_todas_cuentas_tipo(tipo, modelo=modelo_final)
        if not cuentas:
            continue
        turno_cuenta = _account_turn_by_model.get(modelo_final, 0) % len(cuentas)
        cuentas = cuentas[turno_cuenta:] + cuentas[:turno_cuenta]
        for cuenta in cuentas:
            cid = cuenta["id"]
            if modelo_final in rotador_cuentas.obtener_modelos_agotados(cid):
                continue
            status_code, content = await forward_request(body, solicita_stream, tipo, cuenta, modelo_final, perfil)
            if status_code == 200:
                posicion = participantes.index(entrada)
                _model_turn = (posicion + 1) % len(participantes)
                _account_turn_by_model[modelo_final] = (turno_cuenta + cuentas.index(cuenta) + 1) % len(cuentas)
                _provider_turn = tipo
                return content
            rotador_cuentas.registrar_fallo(cid, status_code, modelo_final, razon=str(content)[:240])
            if status_code in (401, 403, 402):
                rotador_cuentas.marcar_modelo_agotado(cid, modelo_final)

    return None


async def _procesar_modelo_especifico(body: dict[str, Any], solicita_stream: bool, modelo_pedido: str):
    intentados: set[tuple[str, str, str]] = set()
    tokenharbor_explicito = str(modelo_pedido).lower().startswith("tokenharbor/")
    if tokenharbor_explicito and not str(modelo_pedido).lower().endswith(":free"):
        raise HTTPException(
            status_code=400,
            detail="Núcleo IA bloquea las rutas pagas de Token Harbor; usa una ruta :free del ranking.",
        )

    async def intentar_tipo(tipo: str, modelo: str):
        cuentas = rotador_cuentas.obtener_cuentas_ordenadas(tipo, modelo=modelo)
        for cuenta in cuentas:
            cid = cuenta["id"]
            clave = (tipo, cid, modelo)
            if clave in intentados:
                continue
            intentados.add(clave)
            status_code, content = await forward_request(body, solicita_stream, tipo, cuenta, modelo, None)
            if status_code == 200:
                return content
            rotador_cuentas.registrar_fallo(cid, status_code, modelo, razon=str(content)[:240])
            if status_code in (401, 402):
                continue
            if status_code == 403:
                rotador_cuentas.marcar_modelo_agotado(cid, modelo)
                continue
            # Modelo retirado/no disponible o fallo temporal: continuar con el
            # siguiente proveedor/cuenta antes de devolver un error final.
            if status_code in (404, 408, 409, 410, 429, 500, 502, 503, 504):
                continue
            raise HTTPException(status_code=status_code, detail=content)
        return None

    # 1. Si el modelo pertenece a un proveedor conocido, recorrer todas sus cuentas.
    deteccion = gestor_modelos.detectar_proveedor_de_modelo(modelo_pedido)
    if deteccion:
        tipo_det, mod_det = deteccion
        resultado = await intentar_tipo(tipo_det, mod_det)
        if resultado is not None:
            return resultado
        if tokenharbor_explicito:
            raise HTTPException(status_code=503, detail="La ruta :free solicitada de Token Harbor no está disponible.")

    # 2. Recorrer exhaustivamente todos los proveedores y sus cuentas, sin repetir.
    for tipo_proveedor in rotador_cuentas.obtener_orden_failover():
        modelo_final = rotador_cuentas.traducir_modelo(modelo_pedido, tipo_proveedor)
        resultado = await intentar_tipo(tipo_proveedor, modelo_final)
        if resultado is not None:
            return resultado

    fallback = await _intentar_ultra_fallback(body, solicita_stream)
    if fallback is not None:
        return fallback

    raise HTTPException(status_code=503, detail="Reintentos agotados.")


@app.post("/v1/chat/completions")
async def chat_completions(request: Request):
    """
    Endpoint principal compatible OpenAI.
    Prioriza modelos segun el Ranking Global Unificado si no se especifica un modelo concreto.
    """
    _verificar_hot_reload()

    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="JSON invalido")
    try:
        validar_chat(body)
    except EntradaInvalida as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    solicita_stream = body.get("stream", False)
    modelo_pedido = body.get("model", "auto")
    perfil_solicitado = _perfil_solicitado(body)
    if perfil_solicitado is None and _normalizar_perfil(modelo_pedido) is not None:
        perfil_solicitado = _normalizar_perfil(modelo_pedido)
        modelo_pedido = "auto"
    perfil_texto = None if perfil_solicitado is not None else _inferir_perfil_por_texto(body)

    if modelo_pedido in ("auto", "default", gestor_modelos.MODELO_DEFAULT):
        if perfil_solicitado is not None:
            respuesta = await _procesar_autoranking(body, solicita_stream, perfil_solicitado)
            if respuesta is not None:
                return respuesta
        if perfil_texto is not None:
            respuesta = await _procesar_autoranking(body, solicita_stream, perfil_texto)
            if respuesta is not None:
                return respuesta
        respuesta = await _procesar_autoranking(body, solicita_stream)
        if respuesta is not None:
            return respuesta

        fallback = await _intentar_ultra_fallback(body, solicita_stream)
        if fallback is not None:
            return fallback

        modelo_pedido = gestor_modelos.MODELO_DEFAULT

    return await _procesar_modelo_especifico(body, solicita_stream, modelo_pedido)



@app.post("/v1/audio/transcriptions")
async def transcribir_audio_optimizado(
    request: Request,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    model: str = Form("whisper-large-v3")
):
    """
    Endpoint dedicado a transcripciones de audio hacia Groq.
    Usa el disco duro de forma asíncrona para no saturar la RAM ni bloquear el Event Loop.
    """
    _verificar_hot_reload()

    # Groq documenta 25 MB para transcripción en el nivel gratuito. Se permite
    # ajustar el límite para cuentas/planes distintos sin cambiar el código.
    max_upload = int(os.getenv("GROQ_MAX_UPLOAD_BYTES", os.getenv("MAX_UPLOAD_BYTES", str(25 * 1024 * 1024))))
    content_length = request.headers.get("content-length")
    if content_length and content_length.isdigit() and int(content_length) > max_upload:
        raise HTTPException(status_code=413, detail="Archivo demasiado grande")

    candidatos = _cuentas_con_credencial("groq", capacidad="transcription_audio")
    if not candidatos:
        raise HTTPException(status_code=503, detail="No hay cuentas de Groq disponibles")

    fd, temp_path = tempfile.mkstemp(suffix=".tmp")
    
    def cleanup_file(path):
        if os.path.exists(path):
            try:
                os.remove(path)
            except Exception:
                pass
                
    background_tasks.add_task(cleanup_file, temp_path)

    try:
        total_upload = 0
        with os.fdopen(fd, 'wb') as f_out:
            while True:
                chunk = file.file.read(1024 * 1024)
                if not chunk:
                    break
                total_upload += len(chunk)
                if total_upload > max_upload:
                    raise HTTPException(status_code=413, detail="Archivo demasiado grande")
                f_out.write(chunk)
        ultimo_status = 503
        async with httpx.AsyncClient(timeout=120.0) as client:
            for cuenta, proveedor in candidatos:
                limite = limitador_tasa.reservar(cuenta["id"])
                if not limite:
                    ultimo_status = 429
                    continue
                try:
                    politicas.validar_envio("groq", model, "https://api.groq.com/openai/v1/audio/transcriptions")
                except politicas.EnvioNoPermitido as exc:
                    raise HTTPException(status_code=403, detail=str(exc))
                try:
                    with open(temp_path, "rb") as f_in:
                        respuesta = await client.post(
                            "https://api.groq.com/openai/v1/audio/transcriptions",
                            headers=proveedor.construir_headers(),
                            files={"file": (file.filename, f_in, file.content_type or "audio/mpeg")},
                            data={"model": model},
                        )
                except httpx.RequestError as exc:
                    ultimo_status = 502
                    _registrar_capacidad_fallo(cuenta, model, 502, str(exc))
                    continue
                if respuesta.status_code == 200:
                    _registrar_capacidad_ok(cuenta, model)
                    return respuesta.json()
                ultimo_status = respuesta.status_code
                _registrar_capacidad_fallo(cuenta, model, respuesta.status_code, respuesta.text[:240])
                if not _es_reintentable_capacidad(respuesta.status_code):
                    raise HTTPException(status_code=respuesta.status_code, detail={"error": "upstream_error", "status": respuesta.status_code})
        raise HTTPException(status_code=ultimo_status, detail="No se pudo transcribir con las cuentas disponibles")

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail={"error": "transcription_failed", "message": str(e)[:240]})
    finally:
        cleanup_file(temp_path)


def _obtener_plan_capacidad_multimedia(capacidad: str, modelo_solicitado: str | None, catalogo_default: list[tuple[str, str]]) -> list[tuple[str, str]]:
    capacidad = canonica(capacidad)
    es_auto = modelo_solicitado in ("auto", None, "")
    ranking_cap = []
    state_dir = os.path.join(RAIZ, "state")
    ranking_global_path = os.path.join(state_dir, "ranking_global.json")
    if os.path.exists(ranking_global_path):
        try:
            with open(ranking_global_path, "r", encoding="utf-8") as f:
                data_glob = json.load(f)
            for prov, caps in data_glob.get("rankings_capacidades", {}).items():
                if isinstance(caps, dict):
                    for clave_cap in claves_compatibles(capacidad):
                        for m in caps.get(clave_cap, []):
                            mid = m.get("id") or m.get("modelo")
                            if mid:
                                ranking_cap.append((str(prov), str(mid)))
        except Exception:
            pass

    if ranking_cap:
        vistos = set()
        orden_base = []
        for p, m in ranking_cap:
            if (p, m) not in vistos:
                vistos.add((p, m))
                orden_base.append((p, m))
        for p, m in catalogo_default:
            if (p, m) not in vistos:
                vistos.add((p, m))
                orden_base.append((p, m))
    else:
        orden_base = list(catalogo_default)

    pref_path = os.path.join(state_dir, "preferencias_ranking.json")
    if os.path.exists(pref_path):
        try:
            with open(pref_path, "r", encoding="utf-8") as f:
                prefs = json.load(f)
            orden_usuario = orden_guardado(prefs.get("ordenes", {}), capacidad)
            if orden_usuario:
                pos = {clave: i for i, clave in enumerate(orden_usuario)}
                orden_base.sort(key=lambda item: pos.get(f"{item[0]}::{item[1]}", 9999))
        except Exception:
            pass

    if es_auto:
        return orden_base

    plan = []
    solicitado_str = str(modelo_solicitado).strip()
    for p, m in orden_base:
        if m == solicitado_str or f"{p}::{m}" == solicitado_str:
            plan.append((p, m))
            break

    if not plan:
        if "cogview" in solicitado_str.lower() or "zhipu" in solicitado_str.lower():
            prov = "zhipu"
        elif "@cf" in solicitado_str.lower() or "cloudflare" in solicitado_str.lower():
            prov = "cloudflare"
        else:
            prov = "siliconflow"
        plan.append((prov, solicitado_str))

    for p, m in orden_base:
        if (p, m) not in plan:
            plan.append((p, m))

    return plan


@app.post("/v1/images/generations")
async def creador_imagenes(request: Request):
    """
    Endpoint para generación de imágenes. Rutea dinámicamente con ranking de preferencias y failover automático.
    """
    _verificar_hot_reload()
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="JSON invalido")
    if not isinstance(body, dict):
        raise HTTPException(status_code=422, detail="El cuerpo JSON debe ser un objeto")

    proveedor_simulado = str(body.get("provider", body.get("proveedor", ""))).strip().lower()
    if proveedor_simulado == "mock_images":
        prompt = str(body.get("prompt", "")).strip()
        if not prompt:
            raise HTTPException(status_code=422, detail="Falta prompt de imagen")
        return JSONResponse({"created": int(time.time()), "data": [], "simulated": True,
                             "provider": "mock_images", "model": body.get("model", "mock-image-v1"),
                             "prompt": prompt, "message": "Simulación sin archivo ni consumo de API"})

    proveedor_explicito = body.pop("provider", body.pop("proveedor", None))
    modelo_solicitado = body.get("model", "auto")

    catalogo_default_imagenes = [
        ("siliconflow", "black-forest-labs/FLUX.1-schnell"),
        ("zhipu", "CogView-3-Flash"),
        ("cloudflare", "@cf/black-forest-labs/flux-1-schnell"),
    ]

    plan = _obtener_plan_capacidad_multimedia("image_generation", modelo_solicitado, catalogo_default_imagenes)
    if proveedor_explicito:
        prov_filter = str(proveedor_explicito).strip().lower()
        plan = [item for item in plan if item[0] == prov_filter] + [item for item in plan if item[0] != prov_filter]
    plan = [(prov, model) for prov, model in plan
            if proveedor_con_adaptador("image_generation", prov)]

    ultimo_status = 503
    ultimo_error = "No se pudo completar la generación de imagen con las cuentas disponibles"

    async with httpx.AsyncClient(timeout=120.0) as client:
        for prov_nombre, modelo_actual in plan:
            candidatos = _cuentas_con_credencial(prov_nombre, modelo=modelo_actual, capacidad="image_generation")
            if not candidatos:
                continue

            modelos_imagen_base = {"cogview-3-flash", "black-forest-labs/flux.1-schnell", "@cf/black-forest-labs/flux-1-schnell"}
            if str(modelo_actual).lower() not in modelos_imagen_base and os.getenv("NUCLEO_HABILITAR_MODELOS_IMAGEN_NO_GRATUITOS", "false").strip().lower() not in {"1", "true", "yes", "on"}:
                continue

            url_generacion = (
                "https://open.bigmodel.cn/api/paas/v4/images/generations"
                if prov_nombre == "zhipu"
                else "https://api.siliconflow.com/v1/images/generations" if prov_nombre == "siliconflow"
                else ""
            )

            payload = dict(body)
            payload["model"] = modelo_actual

            for cuenta, proveedor in candidatos:
                limite = limitador_tasa.reservar(cuenta["id"])
                if not limite:
                    ultimo_status = 429
                    ultimo_error = f"Límite de tasa alcanzado en cuenta {cuenta.get('id')}"
                    continue
                try:
                    politicas.validar_envio(prov_nombre, modelo_actual, url_generacion or "https://api.cloudflare.com")
                except politicas.EnvioNoPermitido as exc:
                    ultimo_status = 403
                    ultimo_error = str(exc)
                    continue
                try:
                    if prov_nombre == "cloudflare":
                        cloudflare_url = f"https://api.cloudflare.com/client/v4/accounts/{proveedor.account_id}/ai/run/{modelo_actual}"
                        respuesta = await client.post(cloudflare_url, json={"prompt": payload.get("prompt", payload.get("description", ""))}, headers=proveedor.construir_headers())
                    else:
                        respuesta = await client.post(url_generacion, json=payload, headers=proveedor.construir_headers())
                except httpx.RequestError as exc:
                    ultimo_status = 502
                    ultimo_error = str(exc)
                    _registrar_capacidad_fallo(cuenta, modelo_actual, 502, str(exc))
                    continue
                if respuesta.status_code == 200:
                    _registrar_capacidad_ok(cuenta, modelo_actual)
                    if prov_nombre == "cloudflare" and respuesta.headers.get("content-type", "").startswith("image/"):
                        return Response(content=respuesta.content, media_type=respuesta.headers.get("content-type", "image/png"))
                    return respuesta.json()
                ultimo_status = respuesta.status_code
                ultimo_error = respuesta.text[:240]
                _registrar_capacidad_fallo(cuenta, modelo_actual, respuesta.status_code, respuesta.text[:240])

    raise HTTPException(status_code=ultimo_status, detail=ultimo_error)


@app.post("/v1/audio/speech")
async def creador_voz(request: Request):
    """
    Endpoint para Text-to-Speech. Rutea a SiliconFlow (compatible OpenAI).
    """
    _verificar_hot_reload()
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="JSON invalido")
    if not isinstance(body, dict):
        raise HTTPException(status_code=422, detail="El cuerpo JSON debe ser un objeto")
    proveedor_simulado = str(body.get("provider", body.get("proveedor", ""))).strip().lower()
    if proveedor_simulado == "mock_tts":
        texto = str(body.get("input", body.get("text", ""))).strip()
        if not texto:
            raise HTTPException(status_code=422, detail="Falta texto para TTS")
        return JSONResponse({"simulated": True, "provider": "mock_tts", "model": body.get("model", "mock-tts-v1"),
                             "voice": body.get("voice", "default"), "characters": len(texto),
                             "audio": None, "message": "Simulación sin audio ni consumo de API"})

    proveedor_solicitado = str(body.pop("provider", body.pop("proveedor", "siliconflow"))).strip().lower()
    if proveedor_solicitado == "edge_tts":
        try:
            import edge_tts
            texto = str(body.get("input") or body.get("texto") or "").strip()
            if not texto:
                raise HTTPException(status_code=422, detail="Falta input o texto para Edge TTS")
            voz = str(body.get("voice") or body.get("voz") or os.getenv("EDGE_TTS_VOICE", "es-AR-ElenaNeural"))
            rate = str(body.get("rate") or os.getenv("EDGE_TTS_RATE", "+0%"))
            pitch = str(body.get("pitch") or os.getenv("EDGE_TTS_PITCH", "+0Hz"))
            volume = str(body.get("volume") or os.getenv("EDGE_TTS_VOLUME", "+0%"))
            tmp = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
            tmp.close()
            try:
                await edge_tts.Communicate(texto, voice=voz, rate=rate, pitch=pitch, volume=volume).save(tmp.name)
                with open(tmp.name, "rb") as audio:
                    contenido = audio.read()
                return Response(content=contenido, media_type="audio/mpeg")
            finally:
                try: os.unlink(tmp.name)
                except OSError: pass
        except ImportError:
            raise HTTPException(status_code=503, detail="Edge TTS no está instalado; ejecutá el instalador de dependencias")
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(status_code=502, detail=f"Edge TTS no pudo generar el audio: {exc}")
    if proveedor_solicitado == "speechify":
        texto = str(body.get("input") or body.get("text") or body.get("texto") or "").strip()
        if not texto:
            raise HTTPException(status_code=422, detail="Speechify requiere input con el texto a convertir")
        candidatos = _speechify_cuentas()
        if not candidatos:
            raise HTTPException(status_code=503, detail="No hay cuentas Speechify verificadas y habilitadas")
        voz = str(body.get("voice_id") or body.get("voice") or "").strip()
        if not voz:
            raise HTTPException(status_code=422, detail="Speechify requiere voice_id (consultá GET /v1/voices en la API del proveedor)")
        payload = {"input": texto, "voice_id": voz,
                   "model": str(body.get("model") or "simba-3.2"),
                   "audio_format": str(body.get("audio_format") or body.get("response_format") or "mp3")}
        for key in ("options", "output_format"):
            if body.get(key) is not None:
                payload[key] = body[key]
        async with httpx.AsyncClient(timeout=120.0) as client:
            ultimo_status = 503
            for cuenta, api_key in candidatos:
                try:
                    respuesta = await client.post(
                        "https://api.speechify.ai/v1/audio/speech", json=payload,
                        headers={"Authorization": f"Bearer {api_key}", "Speechify-Version": "2026-09-08", "Content-Type": "application/json"})
                except httpx.RequestError:
                    ultimo_status = 502
                    continue
                if respuesta.status_code == 200:
                    try:
                        result = respuesta.json()
                        audio_b64 = result.get("audio") or result.get("audio_data")
                        if audio_b64:
                            import base64
                            audio_bytes = base64.b64decode(audio_b64, validate=True)
                            return Response(content=audio_bytes, media_type=f"audio/{payload['audio_format']}")
                    except (ValueError, TypeError):
                        pass
                    return Response(content=respuesta.content, media_type=respuesta.headers.get("content-type", "audio/mpeg"))
                ultimo_status = respuesta.status_code
                if not _es_reintentable_capacidad(respuesta.status_code):
                    raise HTTPException(status_code=respuesta.status_code, detail={"error": "speechify_error", "status": respuesta.status_code})
            raise HTTPException(status_code=ultimo_status, detail={"error": "speechify_unavailable", "message": "Ninguna cuenta Speechify pudo completar la síntesis"})
    # ElevenLabs es una capacidad secundaria exclusiva de TTS. No se agrega
    # al ranking general ni a la lista de proveedores de chat: solo se activa
    # cuando la persona configura su API key y solicita provider=elevenlabs.
    if proveedor_solicitado == "elevenlabs":
        if not _elevenlabs_capacidad_permitida("speech_generation"):
            raise HTTPException(status_code=403, detail="Texto a voz de ElevenLabs está desactivado para esta cuenta en Núcleo IA")
        api_key = os.getenv("ELEVENLABS_API_KEY", "").strip()
        if not api_key:
            raise HTTPException(status_code=503, detail="ElevenLabs requiere ELEVENLABS_API_KEY")
        texto = str(body.get("input") or body.get("texto") or body.get("text") or "").strip()
        if not texto:
            raise HTTPException(status_code=422, detail="Falta input o texto para ElevenLabs")
        voz = str(body.get("voice_id") or body.get("voice") or body.get("voz") or os.getenv("ELEVENLABS_VOICE_ID", "")).strip()
        if not voz:
            raise HTTPException(status_code=422, detail="ElevenLabs requiere voice_id o ELEVENLABS_VOICE_ID")

        payload = dict(body)
        payload.pop("input", None)
        payload.pop("texto", None)
        payload.pop("voice_id", None)
        payload.pop("voice", None)
        payload.pop("voz", None)
        payload.pop("model", None)
        payload["text"] = texto
        model_id = str(body.get("model_id") or body.get("model") or os.getenv("ELEVENLABS_MODEL_ID", "eleven_multilingual_v2"))
        if model_id.lower() == "auto":
            model_id = os.getenv("ELEVENLABS_MODEL_ID", "eleven_multilingual_v2")
        payload["model_id"] = model_id

        query = {}
        for key in ("output_format", "enable_logging", "optimize_streaming_latency"):
            if key in body and body[key] is not None:
                value = body[key]
                query[key] = str(value).lower() if isinstance(value, bool) else str(value)
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{voz}"
        headers = {"xi-api-key": api_key, "Content-Type": "application/json", "Accept": "audio/mpeg"}
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                respuesta = await client.post(url, params=query, json=payload, headers=headers)
        except httpx.RequestError as exc:
            raise HTTPException(status_code=502, detail=f"ElevenLabs no pudo ser contactado: {exc}")
        if respuesta.status_code == 200:
            media_type = respuesta.headers.get("content-type", "audio/mpeg").split(";", 1)[0]
            return StreamingResponse(iter([respuesta.content]), media_type=media_type)
        detalle = respuesta.text[:240]
        raise HTTPException(status_code=respuesta.status_code, detail={"error": "elevenlabs_error", "status": respuesta.status_code, "detail": detalle})
    if proveedor_solicitado not in {"siliconflow", "groq"}:
        raise HTTPException(status_code=400, detail="Proveedor de voz no soportado")
    candidatos = _cuentas_con_credencial(proveedor_solicitado, capacidad="speech_generation")
    if not candidatos:
        raise HTTPException(status_code=503, detail=f"No hay cuentas de {proveedor_solicitado} disponibles")

    if "model" not in body or body["model"] == "auto":
        body["model"] = "playai-tts" if proveedor_solicitado == "groq" else "FunAudioLLM/CosyVoice2-0.5B"
    modelos_voz_base = {"playai-tts", "funaudiollm/cosyvoice2-0.5b"}
    if str(body["model"]).lower() not in modelos_voz_base and os.getenv("NUCLEO_HABILITAR_MODELOS_VOZ_NO_GRATUITOS", "false").strip().lower() not in {"1", "true", "yes", "on"}:
        raise HTTPException(status_code=403, detail="Ese modelo de voz está desactivado por defecto; habilitá NUCLEO_HABILITAR_MODELOS_VOZ_NO_GRATUITOS si tu cuenta tiene cuota.")
    url_voz = "https://api.groq.com/openai/v1/audio/speech" if proveedor_solicitado == "groq" else "https://api.siliconflow.com/v1/audio/speech"

    ultimo_status = 503
    async with httpx.AsyncClient(timeout=120.0) as client:
        for cuenta, proveedor in candidatos:
            limite = limitador_tasa.reservar(cuenta["id"])
            if not limite:
                ultimo_status = 429
                continue
            try:
                politicas.validar_envio(proveedor_solicitado, body["model"], url_voz)
            except politicas.EnvioNoPermitido as exc:
                raise HTTPException(status_code=403, detail=str(exc))
            try:
                respuesta = await client.post(url_voz, json=body, headers=proveedor.construir_headers())
            except httpx.RequestError as exc:
                ultimo_status = 502
                _registrar_capacidad_fallo(cuenta, body["model"], 502, str(exc))
                continue
            if respuesta.status_code == 200:
                _registrar_capacidad_ok(cuenta, body["model"])
                return StreamingResponse(iter([respuesta.content]), media_type=respuesta.headers.get("content-type", "audio/mpeg"))
            ultimo_status = respuesta.status_code
            _registrar_capacidad_fallo(cuenta, body["model"], respuesta.status_code, respuesta.text[:240])
            if not _es_reintentable_capacidad(respuesta.status_code):
                raise HTTPException(status_code=respuesta.status_code, detail={"error": "upstream_error", "status": respuesta.status_code})
    raise HTTPException(status_code=ultimo_status, detail="No se pudo generar voz con las cuentas disponibles")


def _obtener_plan_embeddings(modelo_solicitado: str | None) -> list[tuple[str, str]]:
    """
    Construye la lista ordenada de (proveedor, modelo) para embeddings basándose en:
    1. Preferencias del usuario en 'capacidad:embeddings' (state/preferencias_ranking.json).
    2. Ranking de capacidades guardado (state/ranking_global.json o state/ranking_cohere_capacidades.json).
    3. Catálogo base de soporte (Cohere, SiliconFlow y Cloudflare Workers AI).
    Si se solicita un modelo específico, dicho modelo va primero y los demás quedan como respaldo failover.
    """
    es_auto = modelo_solicitado in ("auto", None, "")

    catalogo_embeddings = [
        ("cohere", "embed-v4.0"),
        ("cohere", "embed-multilingual-v3.0"),
        ("cohere", "embed-multilingual-light-v3.0"),
        ("cohere", "embed-english-v3.0"),
        ("cohere", "embed-english-light-v3.0"),
        ("siliconflow", "BAAI/bge-m3"),
        ("siliconflow", "BAAI/bge-large-en-v1.5"),
        ("siliconflow", "BAAI/bge-large-zh-v1.5"),
    ]

    ranking_cap = []
    state_dir = os.path.join(RAIZ, "state")
    ranking_global_path = os.path.join(state_dir, "ranking_global.json")
    if os.path.exists(ranking_global_path):
        try:
            with open(ranking_global_path, "r", encoding="utf-8") as f:
                data_glob = json.load(f)
            for prov, caps in data_glob.get("rankings_capacidades", {}).items():
                if isinstance(caps, dict):
                    for m in caps.get("embeddings", []):
                        mid = m.get("id") or m.get("modelo")
                        if mid:
                            ranking_cap.append((str(prov), str(mid)))
        except Exception:
            pass

    if ranking_cap:
        vistos = set()
        orden_base = []
        for p, m in ranking_cap:
            if (p, m) not in vistos:
                vistos.add((p, m))
                orden_base.append((p, m))
        for p, m in catalogo_embeddings:
            if (p, m) not in vistos:
                vistos.add((p, m))
                orden_base.append((p, m))
    else:
        orden_base = list(catalogo_embeddings)

    pref_path = os.path.join(state_dir, "preferencias_ranking.json")
    if os.path.exists(pref_path):
        try:
            with open(pref_path, "r", encoding="utf-8") as f:
                prefs = json.load(f)
            orden_usuario = prefs.get("ordenes", {}).get("capacidad:embeddings", [])
            if orden_usuario:
                pos = {clave: i for i, clave in enumerate(orden_usuario)}
                orden_base.sort(key=lambda item: pos.get(f"{item[0]}::{item[1]}", 9999))
        except Exception:
            pass

    if es_auto:
        return orden_base

    # Si se pide un modelo específico, ponerlo al inicio
    plan = []
    solicitado_str = str(modelo_solicitado).strip()
    for p, m in orden_base:
        if m == solicitado_str or f"{p}::{m}" == solicitado_str:
            plan.append((p, m))
            break

    if not plan:
        # Si es un modelo no indexado, inferir proveedor
        if solicitado_str.startswith("embed-") or "cohere" in solicitado_str.lower():
            prov = "cohere"
        elif "bge-" in solicitado_str.lower() or "baai" in solicitado_str.lower() or "siliconflow" in solicitado_str.lower():
            prov = "siliconflow"
        else:
            prov = "cohere"
        plan.append((prov, solicitado_str))

    # Incorporar el resto de modelos ordenados como failover
    for p, m in orden_base:
        if (p, m) not in plan:
            plan.append((p, m))

    return plan


@app.post("/v1/embeddings")
async def vectorizador(request: Request):
    """
    Endpoint para Embeddings. Rutea dinámicamente con ranking de preferencias y failover automático.
    """
    _verificar_hot_reload()
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="JSON invalido")
    if not isinstance(body, dict):
        raise HTTPException(status_code=422, detail="El cuerpo JSON debe ser un objeto")

    modelo_solicitado = body.get("model", "auto")
    es_auto = modelo_solicitado in ("auto", None, "")

    endpoints_embeddings = {
        "cohere": "https://api.cohere.com/compatibility/v1/embeddings",
        "siliconflow": "https://api.siliconflow.com/v1/embeddings",
    }

    plan = _obtener_plan_embeddings(modelo_solicitado)
    ultimo_status = 503
    ultimo_error = "No se pudieron generar embeddings con las cuentas disponibles"

    async with httpx.AsyncClient(timeout=120.0) as client:
        for prov_nombre, modelo_actual in plan:
            url_target = endpoints_embeddings.get(prov_nombre)
            if not url_target:
                continue

            candidatos = _cuentas_con_credencial(prov_nombre, modelo=modelo_actual, capacidad="embeddings")
            if not candidatos:
                continue

            payload = dict(body)
            payload["model"] = modelo_actual

            for cuenta, proveedor in candidatos:
                limite = limitador_tasa.reservar(cuenta["id"])
                if not limite:
                    ultimo_status = 429
                    ultimo_error = f"Límite de tasa alcanzado en cuenta {cuenta.get('id')}"
                    continue
                try:
                    politicas.validar_envio(prov_nombre, modelo_actual, url_target)
                except politicas.EnvioNoPermitido as exc:
                    ultimo_status = 403
                    ultimo_error = str(exc)
                    continue
                try:
                    respuesta = await client.post(url_target, json=payload, headers=proveedor.construir_headers())
                except httpx.RequestError as exc:
                    ultimo_status = 502
                    ultimo_error = str(exc)
                    _registrar_capacidad_fallo(cuenta, modelo_actual, 502, str(exc))
                    continue
                if respuesta.status_code == 200:
                    _registrar_capacidad_ok(cuenta, modelo_actual)
                    return respuesta.json()
                ultimo_status = respuesta.status_code
                ultimo_error = respuesta.text[:240]
                _registrar_capacidad_fallo(cuenta, modelo_actual, respuesta.status_code, respuesta.text[:240])

    raise HTTPException(status_code=ultimo_status, detail=ultimo_error)


@app.post("/v1/music/generations")
async def creador_musica(request: Request):
    """Contrato local de música para probar routing y rankings sin gastar saldo.

    Solo responde para ``provider=mock_music`` (o ``NUCLEO_MUSIC_MOCK=1``).
    No fabrica un archivo de audio: devuelve una tarea determinista con
    metadatos, suficiente para probar activación, ranking, polling y errores
    sin convertir un proveedor real en dependencia del núcleo.
    """
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="JSON invalido")
    if not isinstance(body, dict):
        raise HTTPException(status_code=422, detail="El cuerpo JSON debe ser un objeto")
    proveedor = str(body.get("provider", body.get("proveedor", ""))).strip().lower()
    if proveedor != "mock_music" and os.getenv("NUCLEO_MUSIC_MOCK", "") != "1":
        raise HTTPException(status_code=403, detail="El simulador musical no está habilitado")
    prompt = str(body.get("prompt", "")).strip()
    if not prompt:
        raise HTTPException(status_code=422, detail="Falta prompt musical")
    duracion = max(1, min(int(body.get("duration", body.get("duracion", 30)) or 30), 600))
    tarea = f"mock-music-{abs(hash((prompt, duracion))) % 10**10:010d}"
    return JSONResponse({
        "id": tarea,
        "object": "music.task",
        "status": "completed",
        "provider": "mock_music",
        "model": str(body.get("model", "mock-music-v1")),
        "prompt": prompt,
        "duration": duracion,
        "format": str(body.get("format", "mp3")),
        "audio_url": None,
        "simulated": True,
    })


@app.post("/v1/videos/generations")
async def creador_videos(request: Request):
    """
    Endpoint para Text-to-Video. Rutea dinámicamente con ranking de preferencias y failover automático.
    """
    _verificar_hot_reload()
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="JSON invalido")
    if not isinstance(body, dict):
        raise HTTPException(status_code=422, detail="El cuerpo JSON debe ser un objeto")

    proveedor_explicito = body.pop("provider", body.pop("proveedor", None))
    modelo_solicitado = body.get("model", "auto")

    catalogo_default_video = [
        ("zhipu", "CogVideoX-Flash"),
        ("siliconflow", "stabilityai/stable-video-diffusion"),
    ]

    capacidad_video = capacidad_video_para_body(body)
    plan = _obtener_plan_capacidad_multimedia(capacidad_video, modelo_solicitado, catalogo_default_video)
    if proveedor_explicito:
        prov_filter = str(proveedor_explicito).strip().lower()
        plan = [item for item in plan if item[0] == prov_filter] + [item for item in plan if item[0] != prov_filter]
    plan = [(prov, model) for prov, model in plan
            if proveedor_con_adaptador(capacidad_video, prov)]

    ultimo_status = 503
    ultimo_error = "No se pudo iniciar el video con las cuentas disponibles"

    async with httpx.AsyncClient(timeout=120.0) as client:
        for prov_nombre, modelo_actual in plan:
            candidatos = _cuentas_con_credencial(prov_nombre, modelo=modelo_actual, capacidad=capacidad_video)
            if not candidatos:
                continue

            modelos_video_base = {"cogvideox-flash", "cogvideox-2", "cogvideox-3", "stabilityai/stable-video-diffusion"}
            if str(modelo_actual).lower() not in modelos_video_base and os.getenv("NUCLEO_HABILITAR_MODELOS_VIDEO_NO_GRATUITOS", "false").strip().lower() not in {"1", "true", "yes", "on"}:
                continue

            url_video = (
                "https://open.bigmodel.cn/api/paas/v4/videos/generations"
                if prov_nombre == "zhipu"
                else "https://api.siliconflow.com/v1/video/submit" if prov_nombre == "siliconflow"
                else ""
            )

            payload = dict(body)
            payload["model"] = modelo_actual

            for cuenta, proveedor in candidatos:
                limite = limitador_tasa.reservar(cuenta["id"])
                if not limite:
                    ultimo_status = 429
                    ultimo_error = f"Límite de tasa alcanzado en cuenta {cuenta.get('id')}"
                    continue
                try:
                    politicas.validar_envio(prov_nombre, modelo_actual, url_video)
                except politicas.EnvioNoPermitido as exc:
                    ultimo_status = 403
                    ultimo_error = str(exc)
                    continue
                try:
                    respuesta = await client.post(url_video, json=payload, headers=proveedor.construir_headers())
                except httpx.RequestError as exc:
                    ultimo_status = 502
                    ultimo_error = str(exc)
                    _registrar_capacidad_fallo(cuenta, modelo_actual, 502, str(exc))
                    continue
                if respuesta.status_code == 200:
                    _registrar_capacidad_ok(cuenta, modelo_actual)
                    return respuesta.json()
                ultimo_status = respuesta.status_code
                ultimo_error = respuesta.text[:240]
                _registrar_capacidad_fallo(cuenta, modelo_actual, respuesta.status_code, respuesta.text[:240])

    raise HTTPException(status_code=ultimo_status, detail=ultimo_error)


# Alias sencillos para agentes y aplicaciones que no quieren conocer los nombres
# OpenAI. Reutilizan exactamente los mismos límites, políticas y failover.
async def _request_json_equivalente(request: Request, body: dict) -> Request:
    raw = json.dumps(body, ensure_ascii=False).encode("utf-8")
    headers = [(k, v) for k, v in request.scope.get("headers", []) if k.lower() != b"content-length"]
    headers.append((b"content-type", b"application/json"))
    scope = dict(request.scope, headers=headers)
    enviado = False

    async def recibir():
        nonlocal enviado
        if enviado:
            return {"type": "http.request", "body": b"", "more_body": False}
        enviado = True
        return {"type": "http.request", "body": raw, "more_body": False}

    return Request(scope, receive=recibir)


@app.post("/v1/analizar-imagen")
async def alias_analizar_imagen(request: Request):
    body = await request.json()
    if not isinstance(body, dict) or not body.get("imagen"):
        raise HTTPException(status_code=422, detail="Enviá imagen y, opcionalmente, pregunta")
    pregunta = str(body.get("pregunta") or "¿Qué aparece en esta imagen?")
    imagen = str(body["imagen"])
    mensaje = {"role": "user", "content": [{"type": "text", "text": pregunta}, {"type": "image_url", "image_url": {"url": imagen}}]}
    payload = {"model": body.get("model", "vision"), "messages": [mensaje], "stream": bool(body.get("stream", False))}
    return await chat_completions(await _request_json_equivalente(request, payload))


@app.post("/v1/crear-imagen")
async def alias_crear_imagen(request: Request):
    body = await request.json()
    if not isinstance(body, dict) or not str(body.get("descripcion") or body.get("prompt") or "").strip():
        raise HTTPException(status_code=422, detail="Enviá una descripcion de la imagen")
    body["prompt"] = str(body.get("prompt") or body["descripcion"])
    body.setdefault("model", "auto")
    return await creador_imagenes(await _request_json_equivalente(request, body))


@app.post("/v1/crear-voz")
async def alias_crear_voz(request: Request):
    body = await request.json()
    if not isinstance(body, dict) or not str(body.get("texto") or body.get("input") or "").strip():
        raise HTTPException(status_code=422, detail="Enviá el texto que querés escuchar")
    body["input"] = str(body.get("input") or body["texto"])
    body.setdefault("model", "auto")
    return await creador_voz(await _request_json_equivalente(request, body))


@app.post("/v1/buscar-significado")
async def alias_buscar_significado(request: Request):
    body = await request.json()
    if not isinstance(body, dict) or not body.get("texto") and not body.get("input"):
        raise HTTPException(status_code=422, detail="Enviá el texto que querés convertir en significado")
    body["input"] = body.get("input", body["texto"])
    body.setdefault("model", "auto")
    return await vectorizador(await _request_json_equivalente(request, body))


@app.post("/v1/crear-video")
async def alias_crear_video(request: Request):
    body = await request.json()
    if not isinstance(body, dict) or not str(body.get("descripcion") or body.get("prompt") or "").strip():
        raise HTTPException(status_code=422, detail="Enviá una descripcion del video")
    body["prompt"] = str(body.get("prompt") or body["descripcion"])
    body.setdefault("model", "auto")
    return await creador_videos(await _request_json_equivalente(request, body))


@app.post("/v1/transcribir-audio")
async def alias_transcribir_audio(request: Request, background_tasks: BackgroundTasks,
                                  file: UploadFile = File(...), model: str = Form("whisper-large-v3")):
    return await transcribir_audio_optimizado(request, background_tasks, file, model)

if __name__ == "__main__":
    import uvicorn

    for env_name in (".env", "granja.env"):
        env_f = os.path.join(RAIZ, env_name)
        if os.path.exists(env_f):
            try:
                with open(env_f, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line.startswith("PROXY_PORT="):
                            os.environ.setdefault("PROXY_PORT", line.split("=", 1)[1].strip().strip('"').strip("'"))
                        elif line.startswith("PROXY_HOST="):
                            os.environ.setdefault("PROXY_HOST", line.split("=", 1)[1].strip().strip('"').strip("'"))
            except Exception:
                pass

    host = os.getenv("PROXY_HOST", "127.0.0.1")
    port = int(os.getenv("PROXY_PORT", "8080"))
    uvicorn.run(app, host=host, port=port)
