#!/usr/bin/env python3
"""Ranking local de OpenRouter para Núcleo IA.

Usa catálogo vivo + probe real + fórmula común compartida con Ollama y NVIDIA.
"""
from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from datetime import datetime

from ranking_common import calcular_puntaje_comun, cumple_minimos, clave_orden_modelo, extraer_parametros
from ranking_quality import probar_herramienta_openai
from secret_utils import get_openrouter_api_key, load_local_env

RAIZ = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
STATE_DIR = os.path.join(RAIZ, "state")
RANKING_SALIDA = os.path.join(STATE_DIR, "ranking_openrouter.json")
CACHE_PRUEBAS = os.path.join(STATE_DIR, "ranking_openrouter_probe_cache.json")
URL_MODELOS = "https://openrouter.ai/api/v1/models"
URL_MODELOS_JINA = "https://r.jina.ai/https://openrouter.ai/models"
URL_CHAT = "https://openrouter.ai/api/v1/chat/completions"
TEST_TEMPERATURE = 1
# Algunos modelos gratuitos consumen primero tokens de razonamiento. Incluso
# 128 tokens pueden terminar íntegramente en reasoning y dejar content vacío,
# aunque el modelo y la clave funcionen correctamente.
TEST_MAX_TOKENS = 512
TEST_PROMPT = "Responde únicamente OK, sin explicación ni razonamiento visible."
TEST_TIMEOUT = 60


def obtener_api_key_openrouter() -> str | None:
    load_local_env()
    return get_openrouter_api_key()


def cargar_cache_pruebas() -> dict:
    if not os.path.exists(CACHE_PRUEBAS):
        return {}
    try:
        with open(CACHE_PRUEBAS, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def guardar_cache_pruebas(cache: dict) -> None:
    os.makedirs(STATE_DIR, exist_ok=True)
    with open(CACHE_PRUEBAS, "w", encoding="utf-8") as f:
        json.dump(cache, f, indent=2, ensure_ascii=False)


def recortar_texto(texto: str, limite: int = 160) -> str:
    texto = (texto or "").strip().replace("\n", " ")
    if len(texto) <= limite:
        return texto
    return texto[: limite - 1].rstrip() + "…"


def es_modelo_gratis(m: dict) -> bool:
    pricing = m.get("pricing", {}) or {}
    modelo_id = str(m.get("id", "") or "")
    return modelo_id.endswith(":free") or (
        str(pricing.get("prompt", "1")) == "0" and str(pricing.get("completion", "1")) == "0"
    )


def obtener_ids_free_desde_jina() -> set[str]:
    req = urllib.request.Request(URL_MODELOS_JINA, method="GET")
    req.add_header("User-Agent", "Mozilla/5.0")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            texto = resp.read().decode("utf-8", errors="replace")
    except Exception as e:
        print(f"  [!] No pude leer Jina para filtrar free: {e}")
        return set()

    ids = set(re.findall(r"https?://openrouter\.ai/([A-Za-z0-9_.\-]+/[A-Za-z0-9_.\-:]+:free)", texto))
    if not ids:
        ids = set(re.findall(r"\b([A-Za-z0-9_.\-]+/[A-Za-z0-9_.\-:]+:free)\b", texto))
    return ids


def filtrar_modelos_free(modelos: list[dict]) -> tuple[list[dict], dict]:
    ids_jina = obtener_ids_free_desde_jina()
    if ids_jina:
        filtrados = [m for m in modelos if str(m.get("id", "") or "") in ids_jina]
        meta = {"fuente": "jina+api", "ids_jina": len(ids_jina), "filtrados": len(filtrados)}
        return filtrados, meta

    filtrados = [m for m in modelos if es_modelo_gratis(m)]
    meta = {"fuente": "api", "ids_jina": 0, "filtrados": len(filtrados)}
    return filtrados, meta


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
    req.add_header("HTTP-Referer", "https://openclaw.local")
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


def obtener_modelos() -> list:
    req = urllib.request.Request(URL_MODELOS, method="GET")
    req.add_header("User-Agent", "Mozilla/5.0")
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            datos = json.loads(resp.read().decode())
        return datos.get("data", [])
    except Exception as e:
        print(f"  [!] Error obteniendo modelos: {e}")
        return []


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
    params = m.get("supported_parameters", []) or []
    pricing = m.get("pricing", {}) or {}
    arch = m.get("architecture", {}) or {}
    top = m.get("top_provider", {}) or {}

    tiene_tools = "tools" in params
    tiene_reason = "include_reasoning" in params or "reasoning" in params
    tiene_vision = "image" in arch.get("modality", "")
    es_gratis = pricing.get("prompt", "1") == "0" and pricing.get("completion", "1") == "0"

    ctx = int(m.get("context_length", 0) or 0)
    max_tokens = extraer_max_tokens(m)
    params_b = extraer_parametros(f"{m.get('id', '')} {m.get('name', '')} {m.get('description', '') or ''}")

    caps = {
        "herramientas": tiene_tools,
        "pensamiento": tiene_reason,
        "vision": tiene_vision,
        "audio": False,
    }
    puntaje, desglose, caps_norm = calcular_puntaje_comun(caps, contexto=ctx, max_completion_tokens=max_tokens, parametros_b=params_b)
    apto_agente = bool(caps_norm.get("herramientas") and caps_norm.get("reasoning"))

    return {
        "id": m.get("id", "?"),
        "modelo": m.get("id", "?"),
        "modelo_base": m.get("id", "?"),
        "nombre": m.get("name", "?"),
        "puntaje": puntaje,
        "apto_agente": apto_agente,
        "parametros_b": params_b,
        "capacidades": caps,
        "capacidades_norm": caps_norm,
        "contexto": ctx,
        "max_completion_tokens": max_tokens,
        "gratis": es_gratis,
        "precio_prompt": pricing.get("prompt", "?"),
        "precio_completion": pricing.get("completion", "?"),
        "desglose": " + ".join(desglose) if desglose else "",
    }


def generar_ranking() -> dict:
    print("=" * 90)
    print("  RANKING DE MODELOS OPENROUTER — Núcleo IA")
    print("=" * 90)

    modelos = obtener_modelos()
    if not modelos:
        print("[!] No se pudieron obtener modelos.")
        raise SystemExit(1)

    modelos, meta_free = filtrar_modelos_free(modelos)
    if not modelos:
        print("[!] No quedaron modelos free para rankear.")
        raise SystemExit(1)
    print(f"[FREE FILTER] fuente={meta_free['fuente']}  ids_jina={meta_free['ids_jina']}  modelos={meta_free['filtrados']}")

    analizados = [analizar_modelo(m) for m in modelos]
    aptos_teoricos = [a for a in analizados if a["apto_agente"]]
    no_aptos = [a for a in analizados if not a["apto_agente"]]
    aptos_teoricos.sort(key=clave_orden_modelo, reverse=True)
    no_aptos.sort(key=clave_orden_modelo, reverse=True)

    cache_pruebas = cargar_cache_pruebas()
    api_key = obtener_api_key_openrouter()
    if not api_key:
        print("[!] No encuentro API key de OpenRouter en cuentas.json; no puedo probar chat real.")
        raise SystemExit(1)

    print(f"\n[APTOS TEORICOS] Tools + Reasoning ({len(aptos_teoricos)} modelos)")
    print("  Se prueban contra chat real para filtrar el ranking final")

    for a in aptos_teoricos:
        mid = a["id"]
        cached = cache_pruebas.get(mid)
        if cached and cached.get("estado") == "ok" and os.getenv("RANKING_FORCE_PROBE") != "1":
            probe = cached
        else:
            probe = probar_respuesta_real(mid, api_key)
            cache_pruebas[mid] = {
                "modelo": mid,
                "estado": probe["estado"],
                "ok": probe["ok"],
                "preview": probe["preview"],
                "probado_en": datetime.now().isoformat(),
            }
        a["probe_ok"] = probe["ok"]
        a["probe_estado"] = probe["estado"]
        a["probe_preview"] = probe["preview"]
        a["tool_probe_ok"] = None
        a["tool_probe_estado"] = "no_ejecutada"
        if a["probe_ok"] and a.get("capacidades_norm", {}).get("herramientas"):
            a["tool_probe_ok"], a["tool_probe_estado"] = probar_herramienta_openai(
                URL_CHAT,
                api_key,
                mid,
                headers_extra={
                    "HTTP-Referer": "https://openclaw.local",
                    "X-Title": "LaGranjaDeIA",
                },
                timeout=30,
            )
        a["apto_agente"] = cumple_minimos(a.get("capacidades_norm", {}), a.get("probe_ok", False))

    guardar_cache_pruebas(cache_pruebas)

    aptos_finales = [a for a in aptos_teoricos if a.get("apto_agente")]
    rechazados_probe = [a for a in aptos_teoricos if not a.get("apto_agente")]
    for i, a in enumerate(aptos_finales):
        a["posicion"] = i + 1

    aptos_gratis = [a for a in aptos_finales if a["gratis"]]
    aptos_pagos = [a for a in aptos_finales if not a["gratis"]]

    print(f"[APTOS FINALES] Tools + Reasoning + Chat real ({len(aptos_finales)} modelos)")
    print()

    print(f"  --- GRATIS ({len(aptos_gratis)}) ---")
    print(f"  {'#':>3}  {'PTS':>3}  {'MODELO':50s}  {'SIZE':>6}  {'CTX':>8}  {'MAX_TOK':>8}  VIS  PROBE  DESGLOSE")
    print(f"  {'---':>3}  {'---':>3}  {'':->50}  {'':->6}  {'':->8}  {'':->8}  ---  {'':->5}  {'':->25}")
    for a in aptos_gratis:
        vis = "SI" if a["capacidades"]["vision"] else "--"
        size_str = f"{a['parametros_b']:.1f}B" if a["parametros_b"] > 0 else "n/a"
        print(f"  {a['posicion']:>3}  {a['puntaje']:>3}  {a['id']:50s}  {size_str:>6}  {a['contexto']:>8}  {a['max_completion_tokens']:>8}  {vis:3s}  OK   {a['desglose']}")

    print(f"\n  --- PAGOS (top 20 de {len(aptos_pagos)}) ---")
    print(f"  {'#':>3}  {'PTS':>3}  {'MODELO':50s}  {'SIZE':>6}  {'CTX':>8}  {'$/prompt':>10}  VIS  PROBE")
    print(f"  {'---':>3}  {'---':>3}  {'':->50}  {'':->6}  {'':->8}  {'':->10}  ---  {'':->5}")
    for a in aptos_pagos[:20]:
        vis = "SI" if a["capacidades"]["vision"] else "--"
        size_str = f"{a['parametros_b']:.1f}B" if a["parametros_b"] > 0 else "n/a"
        print(f"  {a['posicion']:>3}  {a['puntaje']:>3}  {a['id']:50s}  {size_str:>6}  {a['contexto']:>8}  {a['precio_prompt']:>10}  {vis:3s}  OK")

    if rechazados_probe:
        print(f"\n[RECHAZADOS POR PROBE] {len(rechazados_probe)} modelos teoricamente aptos que no respondieron bien")
        for a in rechazados_probe[:20]:
            print(f"  - {a['id']:50s}  estado={a['probe_estado']:8s}  preview={a['probe_preview']}")

    print(f"\n[NO APTOS] Falta tools o reasoning ({len(no_aptos)} modelos)")
    print(f"  Solo tools: {sum(1 for a in no_aptos if a['capacidades']['herramientas'] and not a['capacidades']['pensamiento'])}")
    print(f"  Solo reasoning: {sum(1 for a in no_aptos if a['capacidades']['pensamiento'] and not a['capacidades']['herramientas'])}")
    print(f"  Ninguno: {sum(1 for a in no_aptos if not a['capacidades']['herramientas'] and not a['capacidades']['pensamiento'])}")

    resultado = {
        "generado": datetime.now().isoformat(),
        "solo_free": True,
        "free_filter": meta_free,
        "total_modelos": len(analizados),
        "total_aptos_teoricos": len(aptos_teoricos),
        "total_aptos_finales": len(aptos_finales),
        "total_aptos_gratis": len(aptos_gratis),
        "ranking_aptos_teoricos": aptos_teoricos,
        "ranking_aptos": aptos_finales,
        "ranking": aptos_finales,
        "ranking_final": aptos_finales,
        "ranking_rechazados_probe": rechazados_probe,
        "no_aptos_resumen": {
            "total": len(no_aptos),
            "solo_tools": sum(1 for a in no_aptos if a["capacidades"]["herramientas"] and not a["capacidades"]["pensamiento"]),
            "solo_pensamiento": sum(1 for a in no_aptos if a["capacidades"]["pensamiento"] and not a["capacidades"]["herramientas"]),
            "ninguno": sum(1 for a in no_aptos if not a["capacidades"]["herramientas"] and not a["capacidades"]["pensamiento"]),
        },
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

    print(f"\n{'=' * 90}")
    print(f"  RESUMEN")
    print(f"{'=' * 90}")
    print(f"  Total modelos OpenRouter:       {len(analizados)}")
    print(f"  Aptos teoricos (T+R):           {len(aptos_teoricos)}")
    print(f"  Aptos finales (T+R+probe):      {len(aptos_finales)}")
    print(f"    - Gratis:                     {len(aptos_gratis)}")
    print(f"    - Pagos:                      {len(aptos_pagos)}")
    print(f"  Rechazados por probe:           {len(rechazados_probe)}")
    print(f"  No aptos:                       {len(no_aptos)}")
    print(f"\n  Top 3 gratis para agentes:")
    for a in aptos_gratis[:3]:
        print(f"    {a['posicion']:>2}. {a['id']:45s} ({a['puntaje']} pts)")
    print(f"\n  Ranking guardado en: {RANKING_SALIDA}")
    print(f"{'=' * 90}")
    return resultado


if __name__ == "__main__":
    generar_ranking()
