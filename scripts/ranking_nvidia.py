#!/usr/bin/env python3
"""Ranking local de NVIDIA NIM para Núcleo IA.

Usa catálogo vivo + probe real + ficha oficial vía Jina para afinar solo
los modelos que ya responden.
"""
from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime

from ranking_common import calcular_puntaje_comun, cumple_minimos, clave_orden_modelo, extraer_parametros
from ranking_quality import probar_herramienta_openai
from secret_utils import get_nvidia_api_key, load_local_env

RAIZ = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
STATE_DIR = os.path.join(RAIZ, "state")
RANKING_SALIDA = os.path.join(STATE_DIR, "ranking_nvidia.json")
CACHE_PRUEBAS = os.path.join(STATE_DIR, "ranking_nvidia_probe_cache.json")
CACHE_JINA = os.path.join(STATE_DIR, "ranking_nvidia_jina_cache.json")
JINA_CACHE_VERSION = 2
CUENTAS_RUTA = os.path.join(RAIZ, "cuentas.json")

URL_MODELOS = "https://integrate.api.nvidia.com/v1/models"
URL_CHAT = "https://integrate.api.nvidia.com/v1/chat/completions"
JINA_BASE = "https://r.jina.ai/https://build.nvidia.com/"
TEST_PROMPT = "ping"
TEST_TEMPERATURE = 1
TEST_MAX_TOKENS = 12
TEST_TIMEOUT = 60

MODELOS_ACTIVOS = {
    "meta/llama-3.1-8b-instruct",
    "meta/llama-3.1-70b-instruct",
    "meta/llama-3.1-405b-instruct",
    "meta/llama-3.2-1b-instruct",
    "meta/llama-3.2-3b-instruct",
    "meta/llama-3.3-70b-instruct",
    "nvidia/nemotron-mini-4b-instruct",
    "nvidia/nemotron-3-super-120b-a12b",
    "nvidia/nemotron-3-ultra-550b-a55b",
    "google/gemma-2-2b-it",
    "google/gemma-3-4b-it",
    "google/gemma-3-12b-it",
    "deepseek-ai/deepseek-v4-flash",
    "deepseek-ai/deepseek-v4-pro",
    "deepseek-ai/deepseek-coder-6.7b-instruct",
    "qwen/qwen3.5-122b-a10b",
    "qwen/qwen3.5-397b-a17b",
    "qwen/qwen3-next-80b-a3b-instruct",
}


def obtener_api_key() -> str | None:
    load_local_env()
    return get_nvidia_api_key()


def cargar_json(ruta: str) -> dict:
    if not os.path.exists(ruta):
        return {}
    try:
        with open(ruta, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def guardar_json(ruta: str, datos: dict) -> None:
    os.makedirs(STATE_DIR, exist_ok=True)
    with open(ruta, "w", encoding="utf-8") as f:
        json.dump(datos, f, indent=2, ensure_ascii=False)


def cargar_cache_pruebas() -> dict:
    return cargar_json(CACHE_PRUEBAS)


def guardar_cache_pruebas(cache: dict) -> None:
    guardar_json(CACHE_PRUEBAS, cache)


def cargar_cache_jina() -> dict:
    cache = cargar_json(CACHE_JINA)
    if not isinstance(cache, dict):
        return {}
    if cache.get("_schema_version") != JINA_CACHE_VERSION:
        return {}
    entries = cache.get("entries", {})
    return entries if isinstance(entries, dict) else {}


def guardar_cache_jina(cache: dict) -> None:
    guardar_json(CACHE_JINA, {"_schema_version": JINA_CACHE_VERSION, "entries": cache})


def recortar_texto(texto: str, limite: int = 160) -> str:
    texto = (texto or "").strip().replace("\n", " ")
    if len(texto) <= limite:
        return texto
    return texto[: limite - 1].rstrip() + "…"


def probar_respuesta_real(modelo_id: str, api_key: str) -> dict:
    body = {
        "model": modelo_id,
        "messages": [{"role": "user", "content": TEST_PROMPT}],
        "temperature": TEST_TEMPERATURE,
        "max_tokens": TEST_MAX_TOKENS,
        "stream": False,
    }
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(URL_CHAT, data=data, method="POST")
    req.add_header("Content-Type", "application/json")
    req.add_header("Authorization", f"Bearer {api_key}")
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


def obtener_modelos(api_key: str | None = None) -> list:
    req = urllib.request.Request(URL_MODELOS, method="GET")
    req.add_header("User-Agent", "Mozilla/5.0")
    if api_key:
        req.add_header("Authorization", f"Bearer {api_key}")
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            datos = json.loads(resp.read().decode())
        return datos.get("data", [])
    except Exception as e:
        print(f"  [!] Error obteniendo modelos NVIDIA: {e}")
        return [
            {"id": "meta/llama-3.1-70b-instruct", "name": "Llama 3.1 70B Instruct"},
            {"id": "meta/llama-3.3-70b-instruct", "name": "Llama 3.3 70B Instruct"},
            {"id": "nvidia/nemotron-mini-4b-instruct", "name": "Nemotron Mini 4B"},
            {"id": "google/gemma-2-2b-it", "name": "Gemma 2 2B"},
            {"id": "deepseek-ai/deepseek-v4-flash", "name": "DeepSeek V4 Flash"},
        ]


def construir_url_jina(model_id: str) -> str:
    quoted = urllib.parse.quote(model_id, safe="/-_.:~")
    return f"{JINA_BASE}{quoted}"


def leer_jina(model_id: str) -> str:
    url = construir_url_jina(model_id)
    req = urllib.request.Request(url, method="GET")
    req.add_header("User-Agent", "Mozilla/5.0")
    with urllib.request.urlopen(req, timeout=40) as resp:
        return resp.read().decode("utf-8", errors="replace")


KW_AGENTIC = re.compile(r"\bagentic\b", re.I)
KW_REASONING = re.compile(r"\breasoning\b|\bthinking\b|\breasoner\b", re.I)
KW_TOOL = re.compile(r"tool calling|tool use|function calling|function call|tools?\b", re.I)
KW_CODING = re.compile(r"\bcoding\b|code\b|coder\b", re.I)
KW_PLANNING = re.compile(r"\bplanning\b|plan\b|long-horizon\b", re.I)
KW_MULTIMODAL = re.compile(r"\bmultimodal\b|\bvision-language\b|\btext \+ image\b|\bimage\/video understanding\b", re.I)
KW_CTX_1M = re.compile(r"1M(?:-token)?\s+context(?:\s+windows?)?|Context Length 1M|1,000,000 context|1000000 context", re.I)
KW_CTX_256K = re.compile(r"256K context|Context Length 256K|262144", re.I)
KW_CTX_128K = re.compile(r"128K context|Context Length 128K|131072", re.I)
KW_FREE = re.compile(r"Free Endpoint|Downloadable", re.I)
KW_DOWNLOAD = re.compile(r"Download Available", re.I)
KW_PARTNER = re.compile(r"Partner Endpoint", re.I)
KW_REASONING_EFFORT = re.compile(r'reasoning_effort\s*[:=]\s*"?(low|medium|high|minimal)"?', re.I)
KW_THINKING = re.compile(r'thinking\s*[:=]\s*(true|false)', re.I)
KW_MAX_TOKENS = re.compile(r'max_tokens\s*=\s*(\d+)', re.I)
KW_MAX_COMPLETION_TOKENS = re.compile(r'max_completion_tokens\s*=\s*(\d+)', re.I)
KW_API_CALLS_30D = re.compile(r'Available API calls in last 30 days\s+([\d.]+\s*[MK]?)', re.I)


def extraer_max_tokens_texto(texto: str) -> int:
    valores = []
    for patron in (KW_MAX_TOKENS, KW_MAX_COMPLETION_TOKENS):
        for m in patron.finditer(texto or ""):
            try:
                valores.append(int(m.group(1)))
            except Exception:
                pass
    return max(valores) if valores else 0


def extraer_api_calls_30d(texto: str) -> str:
    m = KW_API_CALLS_30D.search(texto or "")
    return (m.group(1).strip() if m else "")


def afinar_con_jina(modelo_id: str, caps: dict, contexto_actual: int) -> dict:
    cache = cargar_cache_jina()
    if modelo_id in cache:
        return cache[modelo_id]

    texto = ""
    error = None
    try:
        texto = leer_jina(modelo_id)
    except Exception as e:
        error = f"{type(e).__name__}: {e}"

    mejoras = []
    bonus = 0
    acceso_bonus = 0
    caps = dict(caps)
    contexto = int(contexto_actual or 0)
    max_completion_tokens = 0

    if KW_FREE.search(texto):
        acceso_bonus += 1
        mejoras.append("acceso=free_or_downloadable")
    if KW_DOWNLOAD.search(texto):
        acceso_bonus += 1
        mejoras.append("download=+1")
    if KW_PARTNER.search(texto):
        mejoras.append("partner_endpoint=detectado")

    max_completion_tokens = extraer_max_tokens_texto(texto)
    if max_completion_tokens:
        mejoras.append(f"max_tokens={max_completion_tokens}")

    api_calls_30d = extraer_api_calls_30d(texto)
    if api_calls_30d:
        mejoras.append(f"api_calls_30d={api_calls_30d}")

    if KW_THINKING.search(texto):
        mejoras.append("thinking=detectado")
    if KW_REASONING_EFFORT.search(texto):
        mejoras.append("reasoning_effort=detectado")

    if KW_AGENTIC.search(texto):
        caps["herramientas"] = True
        caps["reasoning"] = True
        bonus += 2
        mejoras.append("agentic=+2")
    if KW_REASONING.search(texto):
        caps["reasoning"] = True
        bonus += 2
        mejoras.append("reasoning=+2")
    if KW_TOOL.search(texto):
        caps["herramientas"] = True
        bonus += 2
        mejoras.append("tooling=+2")
    if KW_CODING.search(texto):
        bonus += 1
        mejoras.append("coding=+1")
    if KW_PLANNING.search(texto):
        bonus += 1
        mejoras.append("planning=+1")
    if KW_MULTIMODAL.search(texto):
        caps["vision"] = True
        bonus += 1
        mejoras.append("multimodal=+1")

    if KW_CTX_1M.search(texto):
        contexto = max(contexto, 1_000_000)
        mejoras.append("ctx1M=detected")
    elif KW_CTX_256K.search(texto):
        contexto = max(contexto, 262_144)
        mejoras.append("ctx256k=detected")
    elif KW_CTX_128K.search(texto):
        contexto = max(contexto, 131_072)
        mejoras.append("ctx128k=detected")

    data = {
        "modelo": modelo_id,
        "url": construir_url_jina(modelo_id),
        "ok": bool(texto),
        "error": error,
        "bonus": bonus,
        "acceso_bonus": acceso_bonus,
        "mejoras": mejoras,
        "contexto": contexto,
        "max_completion_tokens": max_completion_tokens,
        "api_calls_30d": api_calls_30d,
        "texto_preview": recortar_texto(texto, 700),
        "free_or_downloadable_ignoradas": bool(KW_FREE.search(texto)),
        "probado_en": datetime.now().isoformat(),
    }
    cache[modelo_id] = data
    guardar_cache_jina(cache)
    return data


def detectar_tools(model_id: str) -> bool:
    # En NVIDIA NIM suele haber tool use en el catálogo; no lo usamos como filtro duro.
    return True


def detectar_reasoning_basico(model_id: str) -> bool:
    mid = (model_id or "").lower()
    return any(k in mid for k in ("r1", "reason", "thinking", "nemotron"))


def detectar_vision_basico(model_id: str) -> bool:
    mid = (model_id or "").lower()
    return any(k in mid for k in ("vision", "vl", "maverick"))


def extraer_contexto(m: dict) -> int:
    for key in ("context_length", "context", "max_context_tokens"):
        valor = m.get(key)
        if isinstance(valor, (int, float)) and valor > 0:
            return int(valor)
    return 0


def extraer_max_tokens(m: dict) -> int:
    top = m.get("top_provider", {}) or {}
    for key in ("max_completion_tokens", "max_tokens", "output_tokens"):
        valor = top.get(key)
        if isinstance(valor, (int, float)) and valor > 0:
            return int(valor)
    for key in ("max_completion_tokens", "max_tokens"):
        valor = m.get(key)
        if isinstance(valor, (int, float)) and valor > 0:
            return int(valor)
    return 0


def analizar_modelo(m: dict) -> dict:
    mid = m.get("id", "")
    name = m.get("name", "")
    contexto = extraer_contexto(m)
    max_tokens = extraer_max_tokens(m)
    params = extraer_parametros(f"{mid} {name}")
    caps = {
        "herramientas": detectar_tools(mid),
        "reasoning": detectar_reasoning_basico(mid),
        "vision": detectar_vision_basico(mid),
        "audio": False,
    }

    puntaje, desglose, caps_norm = calcular_puntaje_comun(
        caps,
        contexto=contexto,
        max_completion_tokens=max_tokens,
        parametros_b=params,
    )
    return {
        "id": mid,
        "modelo": mid,
        "modelo_base": mid,
        "nombre": name,
        "proveedor": "nvidia",
        "puntaje": puntaje,
        "apto_agente": bool(caps_norm.get("herramientas") and caps_norm.get("reasoning")),
        "parametros_b": float(params or 0.0),
        "contexto": contexto,
        "max_completion_tokens": max_tokens,
        "capacidades": caps,
        "capacidades_norm": caps_norm,
        "gratis": True,
        "desglose": " + ".join(desglose) if desglose else "",
        "jina": None,
    }


def aplicar_jina(modelo: dict) -> dict:
    mid = modelo["id"]
    base_caps = dict(modelo.get("capacidades_norm", {}))
    meta = afinar_con_jina(mid, base_caps, modelo.get("contexto", 0))
    if not meta.get("ok"):
        modelo["jina"] = meta
        return modelo

    caps = dict(modelo.get("capacidades", {}))
    caps_norm = dict(modelo.get("capacidades_norm", {}))
    caps["herramientas"] = bool(meta["mejoras"] and any(x.startswith(("agentic", "tooling", "reasoning")) for x in meta["mejoras"])) or caps.get("herramientas", False)
    caps["vision"] = bool(caps.get("vision") or "multimodal=+1" in meta["mejoras"])

    # reasoning: si Jina lo marca explícitamente, se considera; agentic también ayuda.
    if any(x.startswith(("agentic", "reasoning")) for x in meta["mejoras"]):
        caps["reasoning"] = True
        caps_norm["reasoning"] = True
        caps_norm["herramientas"] = True

    contexto = max(int(modelo.get("contexto", 0) or 0), int(meta.get("contexto", 0) or 0))
    max_completion_tokens = max(
        int(modelo.get("max_completion_tokens", 0) or 0),
        int(meta.get("max_completion_tokens", 0) or 0),
    )
    puntaje, desglose, caps_norm = calcular_puntaje_comun(
        caps,
        contexto=contexto,
        max_completion_tokens=max_completion_tokens,
        parametros_b=modelo.get("parametros_b", 0.0),
    )

    # bono pequeño y determinístico por metadata oficial útil
    puntaje += int(meta.get("bonus", 0) or 0)
    puntaje += int(meta.get("acceso_bonus", 0) or 0)
    if meta.get("bonus", 0):
        desglose.append(f"jina_bonus={meta['bonus']}")
    if meta.get("acceso_bonus", 0):
        desglose.append(f"acceso_bonus={meta['acceso_bonus']}")
    desglose.extend(meta.get("mejoras", []))

    modelo.update({
        "puntaje": puntaje,
        "capacidades": caps,
        "capacidades_norm": caps_norm,
        "contexto": contexto,
        "max_completion_tokens": max_completion_tokens,
        "jina": meta,
        "desglose": " + ".join(desglose) if desglose else modelo.get("desglose", ""),
    })
    modelo["apto_agente"] = bool(caps_norm.get("herramientas") and caps_norm.get("reasoning"))
    return modelo


def generar_ranking() -> dict:
    print("=" * 78)
    print("  RANKING DE MODELOS NVIDIA NIM — Núcleo IA")
    print("=" * 78)

    key = obtener_api_key()
    if not key:
        print("[!] No encuentro API key de NVIDIA en cuentas.json; no puedo probar chat real.")
        raise SystemExit(1)

    modelos = obtener_modelos(key)
    modelos_filtrados = [m for m in modelos if m.get("id") in MODELOS_ACTIVOS]
    analizados = [analizar_modelo(m) for m in modelos_filtrados]
    analizados.sort(key=clave_orden_modelo, reverse=True)

    cache = cargar_cache_pruebas()
    print(f"\n[APTOS TEORICOS] {len(analizados)} modelos")
    print("  Se prueban contra chat real para filtrar el ranking final")

    for a in analizados:
        mid = a["id"]
        cached = cache.get(mid)
        if cached and cached.get("estado") == "ok" and os.getenv("RANKING_FORCE_PROBE") != "1":
            probe = cached
        else:
            probe = probar_respuesta_real(mid, key)
            cache[mid] = {
                "modelo": mid,
                "estado": probe["estado"],
                "ok": probe["ok"],
                "preview": probe["preview"],
                "probado_en": datetime.now().isoformat(),
            }
        a["probe_ok"] = probe["ok"]
        a["probe_estado"] = probe["estado"]
        a["probe_preview"] = probe["preview"]
        a["apto_agente"] = cumple_minimos(a.get("capacidades_norm", {}), a.get("probe_ok", False))

        # Solo si ya respondió bien, completamos con Jina y revalidamos.
        if a["probe_ok"]:
            a = aplicar_jina(a)
        cache[mid]["jina_aplicado"] = bool(a.get("jina", {}).get("ok")) if isinstance(a.get("jina"), dict) else False
        a["apto_agente"] = cumple_minimos(a.get("capacidades_norm", {}), a.get("probe_ok", False))
        a["tool_probe_ok"] = None
        a["tool_probe_estado"] = "no_ejecutada"
        if a["probe_ok"] and a.get("capacidades_norm", {}).get("herramientas"):
            a["tool_probe_ok"], a["tool_probe_estado"] = probar_herramienta_openai(
                URL_CHAT,
                key,
                mid,
                headers_extra={"X-Title": "LaGranjaDeIA"},
                timeout=120,
            )

    guardar_cache_pruebas(cache)

    # Reordenar ya con la puntuación afinada por Jina.
    analizados.sort(key=clave_orden_modelo, reverse=True)

    final = [a for a in analizados if a.get("apto_agente")]
    rechazados = [a for a in analizados if not a.get("apto_agente")]
    for i, a in enumerate(final):
        a["posicion"] = i + 1

    resultado = {
        "generado": datetime.now().isoformat(),
        "total_modelos": len(analizados),
        "total_aptos_finales": len(final),
        "ranking_teorico": analizados,
        "ranking": final,
        "ranking_final": final,
        "ranking_rechazados_probe": rechazados,
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
                "jina_bonus_max": 8,
                "jina_notes": "Solo afina modelos que ya pasaron probe; descargar/free endpoint se ignoran.",
            },
        },
    }

    os.makedirs(STATE_DIR, exist_ok=True)
    with open(RANKING_SALIDA, "w", encoding="utf-8") as f:
        json.dump(resultado, f, indent=2, ensure_ascii=False)

    print(f"[APTOS FINALES] {len(final)} modelos")
    for a in final[:10]:
        jina_bonus = a.get("jina", {}).get("bonus", 0) if isinstance(a.get("jina"), dict) else 0
        print(f"  #{a['posicion']:>2} {a['puntaje']:>3} pts  {a['id']:<45s}  ctx={a['contexto']:<7d}  params={a['parametros_b']:<8.1f}  probe={a['probe_estado']}  jina={jina_bonus}")
    if rechazados:
        print(f"[RECHAZADOS POR PROBE/FILTRO] {len(rechazados)}")
        for a in rechazados[:10]:
            print(f"  - {a['id']:<45s} estado={a['probe_estado']}")
    print(f"\nRanking guardado en: {RANKING_SALIDA}")
    return resultado


if __name__ == "__main__":
    generar_ranking()
