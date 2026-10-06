#!/usr/bin/env python3
"""Ranking local de Google Gemini para Núcleo IA.

Usa catálogo vivo + probe real + ficha común compartida con el resto de la granja.
"""
from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from typing import Any

from ranking_common import calcular_puntaje_comun, cumple_minimos, clave_orden_modelo, extraer_parametros
from secret_utils import get_google_api_key, load_local_env

RAIZ = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
STATE_DIR = os.path.join(RAIZ, "state")
RANKING_SALIDA = os.path.join(STATE_DIR, "ranking_google.json")
CACHE_PRUEBAS = os.path.join(STATE_DIR, "ranking_google_probe_cache.json")
URL_MODELOS = "https://generativelanguage.googleapis.com/v1beta/models"
URL_GENERATE = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"
TEST_PROMPT = "ping"
TEST_TEMPERATURE = 1
TEST_MAX_TOKENS = 12
TEST_TIMEOUT = 60

RE_GENERATION = re.compile(r"generateContent", re.I)
RE_EMBEDDING = re.compile(r"embed|embedding", re.I)
RE_REASONING = re.compile(r"reasoning|thinking|think", re.I)
RE_VISION = re.compile(r"vision|image|multimodal|vision-language", re.I)
RE_AUDIO = re.compile(r"audio|speech|tts", re.I)


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


def cargar_cache_pruebas() -> dict[str, Any]:
    cache = cargar_json(CACHE_PRUEBAS)
    entries = cache.get("entries", {}) if isinstance(cache, dict) else {}
    return entries if isinstance(entries, dict) else {}


def guardar_cache_pruebas(cache: dict[str, Any]) -> None:
    guardar_json(CACHE_PRUEBAS, {"generado": datetime.now().isoformat(), "entries": cache})


def recortar_texto(texto: str, limite: int = 180) -> str:
    texto = (texto or "").strip().replace("\n", " ")
    if len(texto) <= limite:
        return texto
    return texto[: limite - 1].rstrip() + "…"


def obtener_api_key() -> str | None:
    load_local_env()
    return get_google_api_key()


def request_json(url: str, method: str = "GET", payload: dict[str, Any] | None = None) -> dict[str, Any]:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    req.add_header("User-Agent", "Mozilla/5.0")
    with urllib.request.urlopen(req, timeout=TEST_TIMEOUT) as resp:
        return json.loads(resp.read().decode("utf-8", errors="replace"))


def obtener_modelos(api_key: str) -> list[dict[str, Any]]:
    url = f"{URL_MODELOS}?key={urllib.parse.quote(api_key, safe='')}"
    try:
        datos = request_json(url)
    except Exception as e:
        print(f"  [!] Error obteniendo modelos Google: {e}")
        return []
    modelos = datos.get("models") or datos.get("data") or []
    return modelos if isinstance(modelos, list) else []


def extraer_modelo_api(m: dict[str, Any]) -> str:
    raw = str(m.get("name") or m.get("id") or "").strip()
    if raw.startswith("models/"):
        raw = raw.split("/", 1)[1]
    return raw


def extraer_contexto(m: dict[str, Any]) -> int:
    for key in ("inputTokenLimit", "contextLength", "context_length", "context"):
        valor = m.get(key)
        if isinstance(valor, (int, float)) and valor > 0:
            return int(valor)
    return 0


def extraer_max_completion(m: dict[str, Any]) -> int:
    for key in ("outputTokenLimit", "maxOutputTokens", "max_completion_tokens", "max_tokens"):
        valor = m.get(key)
        if isinstance(valor, (int, float)) and valor > 0:
            return int(valor)
    return 0


def estimar_parametros_b(model_id: str, display_name: str, description: str) -> float:
    texto = f"{model_id} {display_name} {description}".lower()
    val = extraer_parametros(texto)
    if val > 0.0:
        return val
    if "flash-lite" in texto or "lite" in texto:
        return 14.0
    if "flash" in texto:
        return 40.0
    if "pro" in texto:
        return 100.0
    if "nano" in texto:
        return 7.0
    return 14.0


def parsear_capacidades(m: dict[str, Any]) -> dict[str, bool]:
    description = f"{m.get('description', '')} {m.get('displayName', '')}"
    model_id = extraer_modelo_api(m).lower()
    methods = {str(x) for x in (m.get("supportedGenerationMethods") or [])}
    input_mod = {str(x).lower() for x in (m.get("inputModalities") or [])}
    output_mod = {str(x).lower() for x in (m.get("outputModalities") or [])}

    text = f"{model_id} {description} {' '.join(methods)}"
    vision = bool(input_mod & {"image", "vision"}) or bool(RE_VISION.search(text))
    audio = bool(output_mod & {"audio"}) or bool(RE_AUDIO.search(text))
    reasoning = bool(RE_REASONING.search(text)) or any(tag in model_id for tag in ("gemini-2.5", "gemini-3", "gemini-3.5", "gemini-3.6"))
    tools = "generateContent" in methods and not RE_EMBEDDING.search(text)

    return {"herramientas": tools, "reasoning": reasoning, "vision": vision, "audio": audio}


def es_modelo_texto(m: dict[str, Any]) -> bool:
    methods = {str(x) for x in (m.get("supportedGenerationMethods") or [])}
    if "generateContent" not in methods:
        return False
    text = f"{m.get('name', '')} {m.get('displayName', '')} {m.get('description', '')}".lower()
    if RE_EMBEDDING.search(text):
        return False
    return True


def probe_model(api_key: str, model_api: str) -> dict[str, Any]:
    url = URL_GENERATE.format(model=urllib.parse.quote(model_api, safe="/-_.~"), key=urllib.parse.quote(api_key, safe=""))
    body = {
        "contents": [
            {
                "role": "user",
                "parts": [{"text": TEST_PROMPT}],
            }
        ],
        "generationConfig": {
            "temperature": TEST_TEMPERATURE,
            "maxOutputTokens": TEST_MAX_TOKENS,
        },
    }
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST")
    req.add_header("Content-Type", "application/json")
    req.add_header("User-Agent", "Mozilla/5.0")

    try:
        with urllib.request.urlopen(req, timeout=TEST_TIMEOUT) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            payload = json.loads(raw)
        candidates = payload.get("candidates") or []
        if candidates:
            content = (candidates[0].get("content") or {})
            parts = content.get("parts") or []
            texto = " ".join(str(p.get("text", "")) for p in parts if isinstance(p, dict)).strip()
            if texto:
                return {"ok": True, "estado": "ok", "preview": recortar_texto(texto)}
        return {"ok": False, "estado": "empty", "preview": ""}
    except urllib.error.HTTPError as e:
        try:
            err = e.read().decode("utf-8", errors="replace")
        except Exception:
            err = ""
        return {"ok": False, "estado": f"http{e.code}", "preview": recortar_texto(err)}
    except Exception as e:
        return {"ok": False, "estado": "err", "preview": f"{type(e).__name__}: {e}"}


def probe_herramienta(api_key: str, model_api: str) -> tuple[bool, str]:
    """Comprueba una llamada de función real mediante la API de Gemini."""
    url = URL_GENERATE.format(model=urllib.parse.quote(model_api, safe="/-_.~"), key=urllib.parse.quote(api_key, safe=""))
    body = {
        "contents": [{"role": "user", "parts": [{"text": "Llama a sumar_numeros con a=17 y b=25. No respondas con texto."}]}],
        "tools": [{"functionDeclarations": [{
            "name": "sumar_numeros",
            "description": "Suma exactamente dos enteros.",
            "parameters": {
                "type": "OBJECT",
                "properties": {"a": {"type": "INTEGER"}, "b": {"type": "INTEGER"}},
                "required": ["a", "b"],
            },
        }]}],
        "toolConfig": {"functionCallingConfig": {"mode": "ANY", "allowedFunctionNames": ["sumar_numeros"]}},
        "generationConfig": {"temperature": 0, "maxOutputTokens": 128},
    }
    req = urllib.request.Request(url, data=json.dumps(body).encode("utf-8"), method="POST")
    req.add_header("Content-Type", "application/json")
    req.add_header("User-Agent", "Nucleo-IA-Ranking/1.0")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            datos = json.loads(resp.read().decode("utf-8", errors="replace"))
        parts = (((datos.get("candidates") or [{}])[0].get("content") or {}).get("parts") or [])
        for part in parts:
            llamada = part.get("functionCall") or {}
            args = llamada.get("args") or {}
            if llamada.get("name") == "sumar_numeros" and args.get("a") == 17 and args.get("b") == 25:
                return True, "ok"
        return False, "sin_llamada_valida"
    except urllib.error.HTTPError as exc:
        return False, f"http_{exc.code}"
    except Exception as exc:
        return False, f"{type(exc).__name__}: {str(exc)[:80]}"


def analizar_modelo(m: dict[str, Any], api_key: str) -> dict[str, Any] | None:
    if not es_modelo_texto(m):
        return None

    model_api = extraer_modelo_api(m)
    display_name = str(m.get("displayName") or m.get("name") or model_api)
    description = str(m.get("description") or "")
    contexto = extraer_contexto(m)
    max_completion_tokens = extraer_max_completion(m)
    parametros_b = estimar_parametros_b(model_api, display_name, description)
    caps = parsear_capacidades(m)

    puntaje, desglose, caps_norm = calcular_puntaje_comun(
        caps,
        contexto=contexto,
        max_completion_tokens=max_completion_tokens,
        parametros_b=parametros_b,
    )

    probe = probe_model(api_key, model_api)
    apto = cumple_minimos(caps_norm, bool(probe.get("ok")))
    tool_probe_ok = None
    tool_probe_estado = "no_ejecutada"
    if probe.get("ok") and caps_norm.get("herramientas"):
        tool_probe_ok, tool_probe_estado = probe_herramienta(api_key, model_api)

    modelo_id = f"google/{model_api}"
    return {
        "id": modelo_id,
        "modelo": modelo_id,
        "modelo_base": modelo_id,
        "modelo_api": model_api,
        "nombre": display_name,
        "proveedor": "google",
        "puntaje": puntaje,
        "apto_agente": apto,
        "parametros_b": parametros_b,
        "contexto": contexto,
        "max_completion_tokens": max_completion_tokens,
        "capacidades": caps,
        "capacidades_norm": caps_norm,
        "gratis": False,
        "probe_ok": bool(probe.get("ok")),
        "probe_estado": probe.get("estado", ""),
        "probe_preview": probe.get("preview", ""),
        "tool_probe_ok": tool_probe_ok,
        "tool_probe_estado": tool_probe_estado,
        "desglose": " + ".join(desglose) if desglose else "",
        "fuente": "google_gemini_api",
        "description": description,
        "raw": {
            "name": m.get("name"),
            "displayName": m.get("displayName"),
            "supportedGenerationMethods": m.get("supportedGenerationMethods", []),
        },
    }


def generar_ranking() -> dict[str, Any]:
    print("=" * 90)
    print("  RANKING DE MODELOS GOOGLE GEMINI — Núcleo IA")
    print("=" * 90)

    api_key = obtener_api_key()
    if not api_key:
        print("[!] No encuentro GOOGLE_API_KEY ni GEMINI_API_KEY; no puedo rankear Google.")
        resultado = {
            "generado": datetime.now().isoformat(),
            "total_modelos": 0,
            "total_aptos_finales": 0,
            "ranking": [],
            "ranking_final": [],
            "ranking_rechazados_probe": [],
            "ficha_comun": {
                "filtro": ["herramientas", "reasoning", "probe_ok"],
                "nota": "Google quedó vacío porque falta la API key.",
            },
        }
        os.makedirs(STATE_DIR, exist_ok=True)
        with open(RANKING_SALIDA, "w", encoding="utf-8") as f:
            json.dump(resultado, f, indent=2, ensure_ascii=False)
        return resultado

    modelos = obtener_modelos(api_key)
    if not modelos:
        print("[!] No se pudieron obtener modelos de Google Gemini.")
        raise SystemExit(1)

    cache = cargar_cache_pruebas()
    analizados: list[dict[str, Any]] = []

    for m in modelos:
        mid = extraer_modelo_api(m)
        cached = cache.get(mid)
        if cached and cached.get("estado") == "ok" and os.getenv("RANKING_FORCE_PROBE") != "1":
            # Recalcular ranking con metadatos frescos, pero conservar probe cache si sigue válido.
            entrada = analizar_modelo(m, api_key)
            if entrada is None:
                continue
            entrada["probe_ok"] = True
            entrada["probe_estado"] = cached.get("estado", "ok")
            entrada["probe_preview"] = cached.get("preview", "")
            entrada["apto_agente"] = cumple_minimos(entrada.get("capacidades_norm", {}), True)
        else:
            entrada = analizar_modelo(m, api_key)
            if entrada is None:
                continue
            cache[mid] = {
                "modelo": mid,
                "estado": entrada.get("probe_estado", ""),
                "ok": bool(entrada.get("probe_ok")),
                "preview": entrada.get("probe_preview", ""),
                "probado_en": datetime.now().isoformat(),
            }
        analizados.append(entrada)

    guardar_cache_pruebas(cache)

    analizados.sort(key=clave_orden_modelo, reverse=True)
    for i, entrada in enumerate(analizados):
        entrada["posicion"] = i + 1

    respondieron = [a for a in analizados if a.get("probe_ok")]
    aptos = [a for a in respondieron if a.get("apto_agente")]
    rechazados = [a for a in analizados if not a.get("probe_ok")]

    for i, entrada in enumerate(respondieron):
        entrada["posicion_respondio"] = i + 1

    resultado = {
        "generado": datetime.now().isoformat(),
        "total_modelos": len(analizados),
        "total_modelos_respondieron": len(respondieron),
        "total_aptos_finales": len(aptos),
        "ranking": respondieron,
        "ranking_final": aptos,
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
            },
            "nota": "Google usa un proxy de tamaño por familia porque no publica parámetros exactos en la API.",
        },
    }

    os.makedirs(STATE_DIR, exist_ok=True)
    with open(RANKING_SALIDA, "w", encoding="utf-8") as f:
        json.dump(resultado, f, indent=2, ensure_ascii=False)

    print(f"[+] Modelos Google analizados: {len(analizados)}")
    print(f"[+] Respondieron probe: {len(respondieron)}")
    print(f"[+] Aptos finales: {len(aptos)}")
    for entrada in respondieron[:15]:
        print(f"  #{entrada['posicion_respondio']:>2} {entrada['puntaje']:>3} pts  {entrada['id']:<40s} probe={entrada['probe_estado']}")
    print(f"\nGuardado en: {RANKING_SALIDA}")
    return resultado


if __name__ == "__main__":
    generar_ranking()
