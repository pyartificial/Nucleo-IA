#!/usr/bin/env python3
"""Ranking local de Groq para Núcleo IA.

Extrae dinámicamente o usa catálogo de modelos del endpoint v1/models de Groq,
analiza sus capacidades (herramientas, razonamiento, visión), ejecuta sondeo
y calcula puntajes estandarizados.
"""
from __future__ import annotations

import json
import os
import urllib.request
import urllib.error
from datetime import datetime
from pathlib import Path

from ranking_common import calcular_puntaje_comun, clave_orden_modelo, cumple_minimos
from ranking_quality import probar_herramienta_openai
from secret_utils import get_groq_api_key

RAIZ = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
STATE_DIR = os.path.join(RAIZ, "state")
SALIDA = os.path.join(STATE_DIR, "ranking_groq.json")

# Catálogo base conocido de Groq con metadatos técnicos
CATALOGO_GROQ_BASE = {
    "openai/gpt-oss-120b": {
        "contexto": 131072,
        "max_completion_tokens": 32768,
        "parametros_b": 120.0,
        "capacidades": {"herramientas": True, "reasoning": True, "vision": False},
    },
    "openai/gpt-oss-20b": {
        "contexto": 131072,
        "max_completion_tokens": 32768,
        "parametros_b": 20.0,
        "capacidades": {"herramientas": True, "reasoning": True, "vision": False},
    },
    "qwen/qwen3.6-27b": {
        "contexto": 131072,
        "max_completion_tokens": 32768,
        "parametros_b": 27.0,
        "capacidades": {"herramientas": True, "reasoning": True, "vision": False},
    },
    "groq/compound": {
        "contexto": 131072,
        "max_completion_tokens": 32768,
        "parametros_b": 70.0,
        "capacidades": {"herramientas": True, "reasoning": True, "vision": False},
    },
    "groq/compound-mini": {
        "contexto": 131072,
        "max_completion_tokens": 32768,
        "parametros_b": 20.0,
        "capacidades": {"herramientas": True, "reasoning": True, "vision": False},
    },
    "llama-3.3-70b-versatile": {
        "contexto": 128000,
        "max_completion_tokens": 32768,
        "parametros_b": 70.0,
        "capacidades": {"herramientas": True, "reasoning": True, "vision": False},
    },
    "llama-3.1-70b-versatile": {
        "contexto": 128000,
        "max_completion_tokens": 8192,
        "parametros_b": 70.0,
        "capacidades": {"herramientas": True, "reasoning": True, "vision": False},
    },
    "llama-3.1-8b-instant": {
        "contexto": 128000,
        "max_completion_tokens": 8192,
        "parametros_b": 8.0,
        "capacidades": {"herramientas": True, "reasoning": False, "vision": False},
    },
    "deepseek-r1-distill-llama-70b": {
        "contexto": 128000,
        "max_completion_tokens": 32768,
        "parametros_b": 70.0,
        "capacidades": {"herramientas": False, "reasoning": True, "vision": False},
    },
    "deepseek-r1-distill-qwen-32b": {
        "contexto": 128000,
        "max_completion_tokens": 32768,
        "parametros_b": 32.0,
        "capacidades": {"herramientas": False, "reasoning": True, "vision": False},
    },
    "qwen-2.5-32b": {
        "contexto": 128000,
        "max_completion_tokens": 32768,
        "parametros_b": 32.0,
        "capacidades": {"herramientas": True, "reasoning": True, "vision": False},
    },
    "qwen-2.5-coder-32b": {
        "contexto": 128000,
        "max_completion_tokens": 32768,
        "parametros_b": 32.0,
        "capacidades": {"herramientas": True, "reasoning": True, "vision": False},
    },
    "llama-3.2-90b-vision-preview": {
        "contexto": 128000,
        "max_completion_tokens": 8192,
        "parametros_b": 90.0,
        "capacidades": {"herramientas": True, "reasoning": True, "vision": True},
    },
    "llama-3.2-11b-vision-preview": {
        "contexto": 128000,
        "max_completion_tokens": 8192,
        "parametros_b": 11.0,
        "capacidades": {"herramientas": True, "reasoning": False, "vision": True},
    },
    "llama-3.2-3b-preview": {
        "contexto": 128000,
        "max_completion_tokens": 8192,
        "parametros_b": 3.0,
        "capacidades": {"herramientas": True, "reasoning": False, "vision": False},
    },
    "llama-3.2-1b-preview": {
        "contexto": 128000,
        "max_completion_tokens": 8192,
        "parametros_b": 1.0,
        "capacidades": {"herramientas": True, "reasoning": False, "vision": False},
    },
    "mixtral-8x7b-32768": {
        "contexto": 32768,
        "max_completion_tokens": 32768,
        "parametros_b": 47.0,
        "capacidades": {"herramientas": True, "reasoning": False, "vision": False},
    },
    "allam-2-7b": {
        "contexto": 4096,
        "max_completion_tokens": 4096,
        "parametros_b": 7.0,
        "capacidades": {"herramientas": False, "reasoning": False, "vision": False},
    },
    "gemma2-9b-it": {
        "contexto": 8192,
        "max_completion_tokens": 8192,
        "parametros_b": 9.0,
        "capacidades": {"herramientas": False, "reasoning": False, "vision": False},
    },
}


def _inferir_metadatos(model_id: str, remote_info: dict | None = None) -> dict:
    mid_low = model_id.lower()
    if model_id in CATALOGO_GROQ_BASE:
        res = dict(CATALOGO_GROQ_BASE[model_id])
        if remote_info and remote_info.get("context_window"):
            res["contexto"] = int(remote_info["context_window"])
        return res

    # Inferencia heurística
    ctx = int((remote_info or {}).get("context_window", 0))
    if ctx <= 0:
        ctx = 131072 if ("llama-3" in mid_low or "qwen" in mid_low or "deepseek" in mid_low or "gpt" in mid_low or "compound" in mid_low) else 32768
    max_tokens = 32768 if ctx >= 128000 else 8192
    params_b = 0.0

    if "120b" in mid_low:
        params_b = 120.0
    elif "90b" in mid_low:
        params_b = 90.0
    elif "70b" in mid_low:
        params_b = 70.0
    elif "32b" in mid_low:
        params_b = 32.0
    elif "27b" in mid_low:
        params_b = 27.0
    elif "20b" in mid_low:
        params_b = 20.0
    elif "11b" in mid_low:
        params_b = 11.0
    elif "8b" in mid_low or "9b" in mid_low or "7b" in mid_low:
        params_b = 8.0
    elif "3b" in mid_low:
        params_b = 3.0
    elif "1b" in mid_low:
        params_b = 1.0

    is_reasoning = "r1" in mid_low or "reason" in mid_low or "think" in mid_low or "compound" in mid_low or "gpt" in mid_low or "qwen3" in mid_low or params_b >= 70.0
    is_tools = "distill" not in mid_low and "whisper" not in mid_low and "guard" not in mid_low and "orpheus" not in mid_low
    is_vision = "vision" in mid_low or "vl" in mid_low

    return {
        "contexto": ctx,
        "max_completion_tokens": max_tokens,
        "parametros_b": params_b,
        "capacidades": {
            "herramientas": is_tools,
            "reasoning": is_reasoning,
            "vision": is_vision,
        }
    }


def obtener_modelos_remotos(api_key: str) -> dict[str, dict]:
    url = "https://api.groq.com/openai/v1/models"
    req = urllib.request.Request(url, headers={
        "Authorization": f"Bearer {api_key}",
        "Accept": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    })
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
            modelos_raw = data.get("data", [])
            salida = {}
            for m in modelos_raw:
                mid = m.get("id", "")
                if not mid or m.get("active") is False:
                    continue
                if mid.startswith("whisper") or "guard" in mid.lower() or "orpheus" in mid.lower():
                    continue
                salida[mid] = m
            return salida
    except Exception as e:
        print(f"  [!] Error consultando API de Groq: {e}")
        return {}


def prober_modelo(model_id: str, api_key: str) -> tuple[bool, str]:
    url = "https://api.groq.com/openai/v1/chat/completions"
    payload = json.dumps({
        "model": model_id,
        "messages": [{"role": "user", "content": "ping"}],
        "max_tokens": 1,
    }).encode("utf-8")

    req = urllib.request.Request(
        url,
        data=payload,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        },
        method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=8) as resp:
            if resp.status == 200:
                return True, "ok"
            return False, f"status_{resp.status}"
    except urllib.error.HTTPError as e:
        return False, f"http_{e.code}"
    except Exception as e:
        return False, str(e)[:30]


def generar_ranking() -> dict:
    print("═" * 80)
    print("  RANKING DE GROQ — Núcleo IA (LPU Ultra-Fast Inference)")
    print("═" * 80)

    api_key = get_groq_api_key(Path(RAIZ))
    remotos_dict = {}

    if api_key:
        print("  [*] API Key de Groq detectada. Consultando endpoint oficial /v1/models...")
        remotos_dict = obtener_modelos_remotos(api_key)

    if not remotos_dict:
        if not api_key:
            print("  [i] Sin API Key activa. Usando catálogo estático verificado de Groq.")
        else:
            print("  [!] Falla al consultar catálogo remoto. Usando catálogo estático verificado.")
        modelos_ids = list(CATALOGO_GROQ_BASE.keys())
    else:
        modelos_ids = list(remotos_dict.keys())

    ranking = []
    for model_id in modelos_ids:
        meta = _inferir_metadatos(model_id, remotos_dict.get(model_id))
        caps = meta.get("capacidades", {})
        contexto = int(meta.get("contexto", 0) or 0)
        max_tok = int(meta.get("max_completion_tokens", 0) or 0)
        params_b = float(meta.get("parametros_b", 0.0) or 0.0)

        puntaje, desglose, caps_norm = calcular_puntaje_comun(
            caps,
            contexto=contexto,
            max_completion_tokens=max_tok,
            parametros_b=params_b,
        )

        probe_ok = False
        probe_estado = "sin_clave"
        tool_probe_ok = None
        tool_probe_estado = "no_ejecutada"
        if api_key:
            ok, est = prober_modelo(model_id, api_key)
            probe_ok = ok
            probe_estado = est
            if probe_ok and caps_norm.get("herramientas"):
                tool_probe_ok, tool_probe_estado = probar_herramienta_openai(
                    "https://api.groq.com/openai/v1/chat/completions",
                    api_key,
                    model_id,
                    timeout=20,
                )

        apto = cumple_minimos(caps_norm, probe_ok)

        entrada = {
            "id": model_id,
            "modelo": model_id,
            "modelo_base": model_id,
            "nombre": model_id,
            "proveedor": "groq",
            "puntaje": puntaje,
            "apto_agente": apto,
            "parametros_b": params_b,
            "contexto": contexto,
            "max_completion_tokens": max_tok,
            "capacidades": caps,
            "capacidades_norm": caps_norm,
            "gratis": True,
            "probe_ok": probe_ok,
            "probe_estado": probe_estado,
            "probe_preview": "ok",
            "tool_probe_ok": tool_probe_ok,
            "tool_probe_estado": tool_probe_estado,
            "desglose": " + ".join(desglose) if desglose else "",
            "fuente": "groq_api" if api_key else "groq_catalog",
        }
        ranking.append(entrada)

    ranking.sort(key=clave_orden_modelo, reverse=True)
    for i, r in enumerate(ranking):
        r["posicion"] = i + 1

    resultado = {
        "generado": datetime.now().isoformat(),
        "service": "groq",
        "total_modelos": len(ranking),
        "total_aptos_finales": sum(1 for r in ranking if r.get("apto_agente")),
        "ranking": ranking,
        "ranking_final": [r for r in ranking if r.get("apto_agente")],
        "ranking_rechazados_probe": [r for r in ranking if not r.get("apto_agente")],
        "ficha_comun": {
            "filtro": ["herramientas", "reasoning", "probe_ok"],
        },
    }

    os.makedirs(STATE_DIR, exist_ok=True)
    with open(SALIDA, "w", encoding="utf-8") as f:
        json.dump(resultado, f, indent=2, ensure_ascii=False)

    for r in ranking:
        apto_str = "[APTO]" if r.get("apto_agente") else "[SECUNDARIO]"
        print(f"  #{r['posicion']:>2} {r['puntaje']:>3} pts  {r['modelo']:35s} {apto_str} ({r['desglose']})")

    print(f"\nGuardado en: {SALIDA}")
    return resultado


if __name__ == "__main__":
    generar_ranking()
