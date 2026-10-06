#!/usr/bin/env python3
"""Ranking local de Cloudflare Workers AI para Núcleo IA."""
from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from datetime import datetime
from typing import Any

from ranking_common import calcular_puntaje_comun, cumple_minimos, clave_orden_modelo, extraer_parametros
from ranking_quality import probar_herramienta_openai
from secret_utils import get_cloudflare_accounts, get_cloudflare_credentials, load_local_env

RAIZ = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
STATE_DIR = os.path.join(RAIZ, "state")
RANKING_SALIDA = os.path.join(STATE_DIR, "ranking_cloudflare.json")
CATALOGO_CACHE = os.path.join(STATE_DIR, "ranking_cloudflare_catalog_cache.json")
URL_INDEX = "https://developers.cloudflare.com/workers-ai/models/index.md"
URL_CHAT = "https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/v1/chat/completions"
URL_MODELOS_API = "https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/models/search"
CATALOGO_TTL_SEC = int(os.getenv("CLOUDFLARE_CATALOG_TTL_SEC", "86400"))
TEST_PROMPT = "ping"
TEST_TEMPERATURE = 1
# Los modelos de reasoning pueden consumir 12 tokens antes de producir texto.
# Este valor solo afecta el probe del ranking, no los timeouts del núcleo.
TEST_MAX_TOKENS = 128
TEST_TIMEOUT = 60

MODEL_PAGE_RE = re.compile(r"https://developers\.cloudflare\.com/workers-ai/models/([^/\s]+)/")
MODEL_ID_RE = re.compile(r"`(@cf/[^`]+)`")
TITLE_RE = re.compile(r"^#\s+([^\n]+)", re.M)
TASK_RE = re.compile(
    r"^([A-Za-z][A-Za-z0-9\-+ ]{2,60})\s*•",
    re.M,
)
CONTEXT_RE = re.compile(r"Context Window.*?([0-9][0-9,]*)\s*tokens", re.S)
DESCRIPTION_RE = re.compile(r"^#\s+[^\n]+\n\n[^\n]+\n\n(.+?)(?:\n\n\*|\n\n##|\Z)", re.S)


def recortar_texto(texto: str, limite: int = 180) -> str:
    texto = (texto or "").strip().replace("\n", " ")
    if len(texto) <= limite:
        return texto
    return texto[: limite - 1].rstrip() + "…"


def cargar_json(ruta: str) -> dict[str, Any]:
    if not os.path.exists(ruta):
        return {}
    try:
        with open(ruta, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def guardar_json(ruta: str, data: dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(ruta), exist_ok=True)
    with open(ruta, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def fetch_text(url: str, timeout: int = 30) -> str:
    req = urllib.request.Request(url, method="GET")
    req.add_header("User-Agent", "Mozilla/5.0")
    req.add_header("Accept", "text/markdown,text/plain;q=0.9,*/*;q=0.1")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="replace")


def obtener_credenciales() -> dict[str, str] | None:
    load_local_env()
    return get_cloudflare_credentials()


def obtener_catalogo_api(creds: dict[str, str]) -> list[dict[str, Any]]:
    """Obtiene capacidades estructuradas; evita palabras del menú de la web."""
    req = urllib.request.Request(
        URL_MODELOS_API.format(account_id=creds["account_id"]),
        headers={"Authorization": f"Bearer {creds['api_token']}", "Accept": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=TEST_TIMEOUT) as resp:
        data = json.loads(resp.read().decode("utf-8", errors="replace"))
    result = data.get("result") or []
    return result if isinstance(result, list) else []


def _propiedades_api(modelo: dict[str, Any]) -> dict[str, Any]:
    return {
        str(p.get("property_id")): p.get("value")
        for p in (modelo.get("properties") or []) if isinstance(p, dict)
    }


def _prop_bool(props: dict[str, Any], nombre: str) -> bool:
    return str(props.get(nombre, "")).strip().lower() == "true"


def analizar_modelo_api(modelo: dict[str, Any], creds: dict[str, str]) -> dict[str, Any] | None:
    task = str((modelo.get("task") or {}).get("name", ""))
    if task.lower() != "text generation":
        return None
    model_id = str(modelo.get("name") or "").strip()
    if not model_id:
        return None
    props = _propiedades_api(modelo)
    caps = {
        "herramientas": _prop_bool(props, "function_calling"),
        "reasoning": _prop_bool(props, "reasoning"),
        "vision": _prop_bool(props, "vision"),
        "audio": False,
    }
    try:
        contexto = int(float(props.get("context_window") or 0))
    except (TypeError, ValueError):
        contexto = 0
    params_b = extraer_parametros(f"{model_id} {modelo.get('description', '')}")
    puntaje, desglose, caps_norm = calcular_puntaje_comun(caps, contexto=contexto, parametros_b=params_b)
    probe = probar_respuesta_real(creds["account_id"], creds["api_token"], model_id)
    tool_ok = None
    tool_estado = "no_aplica"
    if probe.get("ok") and caps["herramientas"]:
        tool_ok, tool_estado = probar_herramienta_openai(
            URL_CHAT.format(account_id=creds["account_id"]), creds["api_token"], model_id, timeout=30,
        )
    apto = cumple_minimos(caps_norm, bool(probe.get("ok"))) and tool_ok is not False
    return {
        "id": model_id, "modelo": model_id, "modelo_base": model_id,
        "nombre": model_id, "proveedor": "cloudflare", "puntaje": puntaje,
        "apto_agente": apto, "parametros_b": params_b, "contexto": contexto,
        "max_completion_tokens": 0, "capacidades": caps,
        # A successful request proves reachability, not zero marginal price.
        # Workers AI free allocations vary by account/plan and do not make every
        # model an explicitly free model for the shared ranking.
        "capacidades_norm": caps_norm, "gratis": False,
        "gratis_evidencia": "sin_precio_cero_por_modelo; el plan/cuota de cuenta no prueba gratuidad",
        "probe_ok": bool(probe.get("ok")), "probe_estado": probe.get("estado", ""),
        "probe_preview": probe.get("preview", ""), "tool_probe_ok": tool_ok,
        "tool_probe_estado": tool_estado, "desglose": " + ".join(desglose),
        "fuente": "cloudflare_models_api", "task_type": task,
        "descripcion": recortar_texto(str(modelo.get("description") or ""), 260),
        "cuenta_id": str(creds.get("cuenta_id", "")),
    }


def capacidades_secundarias_cloudflare(modelo: dict[str, Any]) -> list[str]:
    task = str((modelo.get("task") or {}).get("name", "")).casefold()
    props = _propiedades_api(modelo)
    tags = f"{task} {modelo.get('name', '')} {modelo.get('description', '')}".casefold()
    salida = set()
    if "text generation" in task and _prop_bool(props, "vision"):
        salida.add("vision_image")
    if "embedding" in task:
        salida.add("embeddings")
    if "rerank" in task:
        salida.add("reranking")
    if any(x in task for x in ("speech recognition", "automatic speech", "transcription")):
        salida.add("transcription_audio")
    if "text to speech" in task or "text-to-speech" in task:
        salida.add("speech_generation")
    if "image to text" in task or "image classification" in task or "vision" in task:
        salida.add("vision_image")
    if "text to image" in task or "image generation" in task:
        salida.add("image_generation")
    if "text to video" in task or "video generation" in task:
        salida.add("video_generation_text")
    if "video classification" in task or "video to text" in task:
        salida.add("vision_video")
    if "document" in tags or "ocr" in task:
        salida.add("parse_documents")
    return sorted(salida)


def probar_respuesta_real(account_id: str, api_token: str, modelo_id: str) -> dict[str, Any]:
    body = {
        "model": modelo_id,
        "messages": [{"role": "user", "content": TEST_PROMPT}],
        "temperature": TEST_TEMPERATURE,
        "max_tokens": TEST_MAX_TOKENS,
        "stream": False,
    }
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(URL_CHAT.format(account_id=account_id), data=data, method="POST")
    req.add_header("Content-Type", "application/json")
    req.add_header("Authorization", f"Bearer {api_token}")
    req.add_header("X-Title", "LaGranjaDeIA")
    req.add_header("User-Agent", "Mozilla/5.0")

    try:
        with urllib.request.urlopen(req, timeout=TEST_TIMEOUT) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            payload = json.loads(raw)
        choice = (payload.get("choices") or [{}])[0]
        message = choice.get("message") or {}
        contenido = (message.get("content") or "").strip()
        if contenido:
            return {"ok": True, "estado": "ok", "preview": recortar_texto(contenido)}
        return {"ok": False, "estado": "empty", "preview": ""}
    except urllib.error.HTTPError as e:
        try:
            err = e.read().decode("utf-8", errors="replace")
        except Exception:
            err = ""
        return {"ok": False, "estado": f"http{e.code}", "preview": recortar_texto(err)}
    except Exception as e:
        return {"ok": False, "estado": "err", "preview": f"{type(e).__name__}: {e}"}


def discover_catalogo() -> dict[str, Any]:
    cache = cargar_json(CATALOGO_CACHE)
    generado_ts = float(cache.get("generado_ts", 0.0) or 0.0)
    if cache and generado_ts and (datetime.now().timestamp() - generado_ts) < CATALOGO_TTL_SEC:
        return cache

    index_text = fetch_text(URL_INDEX)
    slugs = sorted(set(MODEL_PAGE_RE.findall(index_text)))
    pages: list[dict[str, Any]] = []

    for slug in slugs:
        page_url = f"https://developers.cloudflare.com/workers-ai/models/{slug}/index.md"
        try:
            page_text = fetch_text(page_url)
        except Exception as exc:
            pages.append({
                "slug": slug,
                "url": page_url,
                "error": f"{type(exc).__name__}: {exc}",
            })
            continue
        pages.append({
            "slug": slug,
            "url": page_url,
            "text": page_text,
        })

    cache = {
        "generado": datetime.now().isoformat(),
        "generado_ts": datetime.now().timestamp(),
        "index_url": URL_INDEX,
        "total_detectado": len(slugs),
        "pages": pages,
    }
    guardar_json(CATALOGO_CACHE, cache)
    return cache


def extraer_modelo_id(texto: str, slug: str) -> str:
    m = MODEL_ID_RE.search(texto or "")
    if m:
        return m.group(1).strip()
    return f"@cf/{slug}"


def extraer_titulo(texto: str, slug: str) -> str:
    m = TITLE_RE.search(texto or "")
    if m:
        return m.group(1).strip()
    return slug.replace("-", " ").title()


def extraer_tipo(texto: str) -> str:
    m = TASK_RE.search(texto or "")
    if m:
        return m.group(1).strip()
    return ""


def extraer_descripcion(texto: str) -> str:
    m = DESCRIPTION_RE.search(texto or "")
    if m:
        return recortar_texto(m.group(1).strip(), 260)
    return ""


def parsear_capacidades(texto: str, task_type: str) -> dict[str, bool]:
    lower = (texto or "").lower()
    task = (task_type or "").lower()
    return {
        "herramientas": ("function calling" in lower) or ("tool calling" in lower) or ("tool use" in lower),
        "reasoning": ("reasoning" in lower) or ("reasoning" in task),
        "vision": ("vision" in lower) or ("multimodal" in lower) or ("image" in lower and "text generation" in task),
        "audio": ("audio" in lower) or ("speech" in lower) or ("text-to-speech" in task),
    }


def es_text_generation(task_type: str, texto: str) -> bool:
    lower = (task_type or "").lower()
    if "text generation" in lower:
        return True
    # algunos modelos vision siguen siendo chat/text generation con visión
    if "vision" in (texto or "").lower() and "text generation" in (texto or "").lower():
        return True
    return False


def analizar_modelo(page: dict[str, Any], creds: dict[str, str] | None = None) -> dict[str, Any] | None:
    texto = page.get("text", "") or ""
    if not texto:
        return None

    task_type = extraer_tipo(texto)
    if not es_text_generation(task_type, texto):
        return None

    slug = page.get("slug", "")
    model_id = extraer_modelo_id(texto, slug)
    title = extraer_titulo(texto, slug)
    descripcion = extraer_descripcion(texto)
    caps = parsear_capacidades(texto, task_type)
    contexto_match = CONTEXT_RE.search(texto)
    contexto = int((contexto_match.group(1) if contexto_match else "0").replace(",", "") or 0)
    params_b = extraer_parametros(" ".join([model_id, slug, title, descripcion]))

    puntaje, desglose, caps_norm = calcular_puntaje_comun(
        caps,
        contexto=contexto,
        max_completion_tokens=0,
        parametros_b=params_b,
    )

    probe_ok = False
    probe_estado = "sin_credenciales"
    probe_preview = ""
    if creds:
        probe = probar_respuesta_real(creds["account_id"], creds["api_token"], model_id)
        probe_ok = bool(probe.get("ok"))
        probe_estado = str(probe.get("estado", ""))
        probe_preview = str(probe.get("preview", ""))

    apto = cumple_minimos(caps_norm, probe_ok)

    return {
        "id": model_id,
        "modelo": model_id,
        "modelo_base": model_id,
        "nombre": title,
        "proveedor": "cloudflare",
        "puntaje": puntaje,
        "apto_agente": apto,
        "parametros_b": params_b,
        "contexto": contexto,
        "max_completion_tokens": 0,
        "capacidades": caps,
        "capacidades_norm": caps_norm,
        "gratis": False,
        "probe_ok": probe_ok,
        "probe_estado": probe_estado,
        "probe_preview": probe_preview,
        "desglose": " + ".join(desglose) if desglose else "",
        "fuente": "cloudflare_workers_ai_catalogo",
        "slug": slug,
        "task_type": task_type,
        "descripcion": descripcion,
        "url": page.get("url", ""),
    }


def generar_ranking() -> dict[str, Any]:
    print("=" * 90)
    print("  RANKING DE MODELOS CLOUDFLARE WORKERS AI — Núcleo IA")
    print("=" * 90)

    creds_list = get_cloudflare_accounts()
    creds = creds_list[0] if creds_list else obtener_credenciales()
    if not creds_list and creds:
        creds_list = [creds]
    if not creds:
        print("[!] No encuentro credenciales de Cloudflare; haré el escaneo completo sin probe real.")

    modelos_por_id: dict[str, tuple[dict[str, Any], dict[str, str]]] = {}
    if creds_list:
        for account in creds_list:
            try:
                for model in obtener_catalogo_api(account):
                    model_id = str(model.get("name") or "").strip()
                    if model_id:
                        modelos_por_id.setdefault(model_id, (model, account))
            except Exception:
                continue
    modelos_api = [value[0] for value in modelos_por_id.values()]
    if modelos_api:
        creds = creds_list[0]
    else:
        modelos_api = []
    if not modelos_api and creds:
        print("[!] Ninguna cuenta confirmó el catálogo; uso documentación como respaldo sin marcar claves válidas.")
    catalogo = discover_catalogo() if not modelos_api else {}
    pages = catalogo.get("pages", []) or []
    total_detectado = len(modelos_api) if modelos_api else int(catalogo.get("total_detectado", len(pages)) or len(pages))

    analizados: list[dict[str, Any]] = []
    rechazados: list[dict[str, Any]] = []
    errores: list[dict[str, Any]] = []

    fuente_items = modelos_api if modelos_api else pages
    for page in fuente_items:
        if page.get("error"):
            errores.append({"slug": page.get("slug"), "error": page.get("error")})
            continue
        model_creds = modelos_por_id.get(str(page.get("name") or ""), (None, creds))[1] if modelos_api else creds
        entrada = analizar_modelo_api(page, model_creds) if modelos_api and model_creds else analizar_modelo(page, creds=model_creds)
        if not entrada:
            continue
        analizados.append(entrada)
        if not entrada.get("apto_agente"):
            rechazados.append(entrada)

    analizados.sort(key=clave_orden_modelo, reverse=True)
    for i, entrada in enumerate(analizados):
        entrada["posicion"] = i + 1

    aptos = [a for a in analizados if a.get("apto_agente")]
    rechazados = [a for a in analizados if not a.get("apto_agente")]

    capacidades_secundarias: dict[str, list[dict[str, Any]]] = {}
    if modelos_api:
        for model, account in modelos_por_id.values():
            model_id = str(model.get("name") or "").strip()
            for capability in capacidades_secundarias_cloudflare(model):
                capacidades_secundarias.setdefault(capability, []).append({
                    "id": model_id, "modelo": model_id, "proveedor": "cloudflare",
                    "cuenta_id": str(account.get("cuenta_id", "")),
                    "gratis": False, "probe_ok": False, "implementado": capability == "vision_image",
                    "fuente": "catalogo_workers_ai; las tareas distintas de chat requieren adaptador específico",
                })

    resultado = {
        "generado": datetime.now().isoformat(),
        "catalogo": {
            "index_url": URL_MODELOS_API if modelos_api else URL_INDEX,
            "fuente": "api" if modelos_api else "documentacion",
            "total_detectado": total_detectado,
            "total_pages": len(pages),
            "errores_pages": errores,
        },
        "total_modelos": len(analizados),
        "total_aptos_finales": len(aptos),
        "ranking": analizados,
        "ranking_final": aptos,
        "ranking_rechazados_probe": rechazados,
        "rankings_capacidades": capacidades_secundarias,
        "ficha_comun": {
            "filtro": ["herramientas", "reasoning", "probe_ok"],
            "peso": {
                "vision": 10,
                "contexto_128k": 15,
                "contexto_256k": 5,
                "contexto_1m": 5,
                "max_tokens_128k": 5,
                "max_tokens_32k": 3,
                "max_tokens_8k": 1,
                "parametros_100b": 30,
                "parametros_40b": 20,
                "parametros_14b": 12,
                "parametros_7b": 5,
                "parametros_menor_7b": 2,
            },
        },
    }

    os.makedirs(STATE_DIR, exist_ok=True)
    with open(RANKING_SALIDA, "w", encoding="utf-8") as f:
        json.dump(resultado, f, indent=2, ensure_ascii=False)

    print(f"[+] Catálogo detectado: {total_detectado} páginas")
    print(f"[+] Modelos text-generation analizados: {len(analizados)}")
    print(f"[+] Aptos finales: {len(aptos)}")
    for entrada in analizados[:15]:
        print(f"  #{entrada['posicion']:>2} {entrada['puntaje']:>3} pts  {entrada['id']:<45s} probe={entrada['probe_estado']}")
    print(f"\nGuardado en: {RANKING_SALIDA}")
    return resultado


if __name__ == "__main__":
    generar_ranking()
