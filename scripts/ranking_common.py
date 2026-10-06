#!/usr/bin/env python3
"""Utilidades comunes para rankings de Núcleo IA.

Objetivo: que Ollama, NVIDIA y OpenRouter usen la misma ficha base y la misma
fórmula de puntaje, sin borrar rutas duplicadas entre servicios.
"""

from __future__ import annotations

import re
from collections import defaultdict
from typing import Any, Dict, Iterable, List, Tuple

PTS_VISION = 10
PTS_CTX_128K = 15
PTS_CTX_256K_BONUS = 5
PTS_CTX_1M_BONUS = 5
PTS_MAXTOK_128K = 5
PTS_MAXTOK_32K = 3
PTS_MAXTOK_8K = 1
PTS_PARAM_MUY_ALTO = 30  # >= 100B
PTS_PARAM_ALTO = 20      # >= 40B
PTS_PARAM_MEDIO = 12     # >= 14B
PTS_PARAM_BAJO = 5       # >= 7B
PTS_PARAM_MINIMO = 2     # < 7B


def normalizar_capacidades(capacidades: Dict[str, Any] | None) -> Dict[str, bool]:
    caps = capacidades or {}
    return {
        "herramientas": bool(caps.get("herramientas") or caps.get("tools")),
        "reasoning": bool(caps.get("reasoning") or caps.get("pensamiento") or caps.get("razonamiento")),
        "vision": bool(caps.get("vision")),
        "audio": bool(caps.get("audio")),
    }


# Base de conocimiento de arquitecturas y parámetros conocidos (en Miles de Millones / Billions)
PARAMETROS_POR_FAMILIA = {
    "kimi-k3": 2812.0,
    "kimi-k2.7": 1042.0,
    "kimi-k2.6": 1042.0,
    "kimi-k2.5": 1042.0,
    "glm-5.2": 756.0,
    "glm-5.1": 756.0,
    "glm-5": 756.0,
    "glm-4-flash": 9.0,
    "glm-4.5-flash": 32.0,
    "glm-4": 9.0,
    "minimax-m3": 456.0,
    "minimax-m2.7": 229.0,
    "minimax-m2.5": 229.0,
    "minimax-01": 456.0,
    "deepseek-v3": 671.0,
    "deepseek-r1": 671.0,
    "deepseek-v4": 284.0,
    "nemotron-3-ultra": 550.0,
    "nemotron-ultra": 550.0,
    "nemotron-3-super": 120.0,
    "nemotron-super": 120.0,
    "nemotron-mini": 4.0,
    "gpt-oss-120b": 120.0,
    "gpt-oss-20b": 20.0,
    "compound-mini": 20.0,
    "compound": 70.0,
    "gemini-3-flash": 40.0,
    "gemini-2.5-flash": 40.0,
    "gemini-3.5-flash-lite": 14.0,
    "gemini-3.1-flash-lite": 14.0,
    "gemini-flash-lite": 14.0,
    "gemini-pro": 100.0,
    "gemini-robotics": 14.0,
    "command-a-reasoning": 111.0,
    "command-a": 111.0,
    "command-a-plus": 25.0,
    "command-a-vision": 25.0,
    "command-r7b": 7.0,
    "phi-2": 2.7,
    "phi-3-mini": 3.8,
    "phi-3-medium": 14.0,
    "phi-4": 14.0,
    "granite-4.0-h-micro": 3.0,
    "granite-micro": 3.0,
    "granite": 8.0,
    "allam-2-7b": 7.0,
    "allam": 7.0,
}


def extraer_parametros(texto: str) -> float:
    texto = (texto or "").strip().lower()
    if not texto:
        return 0.0

    # 1. Búsqueda exacta en catálogo de arquitecturas conocidas
    for patron, params in PARAMETROS_POR_FAMILIA.items():
        if patron in texto:
            return float(params)

    # 2. Regex MoE (ej: 8x7b -> 47, 8x22b -> 141)
    match_moe = re.search(r"(\d+)\s*x\s*(\d+(?:\.\d+)?)\s*[bB]", texto)
    if match_moe:
        try:
            num_exp = float(match_moe.group(1))
            size_exp = float(match_moe.group(2))
            return float(num_exp * size_exp * 0.8)  # Estimación de peso total MoE
        except ValueError:
            pass

    # 3. Regex estándar de parámetros (ej: 70b, 120b, 32b, 8b, 4b)
    match = re.search(r"(?:^|[^\w])(\d+(?:\.\d+)?)\s*[bB](?:[^\w]|$)", texto)
    if match:
        try:
            return float(match.group(1))
        except ValueError:
            pass

    # 4. Regex con prefijos de arquitectura (ej: a55b -> 550b, a12b -> 120b)
    match_a = re.search(r"a(\d+)[bB]", texto)
    if match_a:
        try:
            val = float(match_a.group(1))
            return val * 10.0 if val < 100.0 else val
        except ValueError:
            pass

    # 5. Inferencia heurística por sufijos semánticos
    if "ultra" in texto or "super" in texto:
        return 120.0
    if "large" in texto or "plus" in texto or "pro" in texto:
        return 70.0
    if "flash" in texto or "medium" in texto:
        return 32.0
    if "mini" in texto or "small" in texto or "lite" in texto:
        return 14.0
    if "nano" in texto or "micro" in texto or "pico" in texto:
        return 3.0

    return 0.0


def bonus_contexto(contexto: int | float | None) -> Tuple[int, List[str]]:
    ctx = int(contexto or 0)
    puntaje = 0
    desglose: List[str] = []
    if ctx >= 131072:
        puntaje += PTS_CTX_128K
        desglose.append(f"ctx128k={PTS_CTX_128K}")
    if ctx >= 262144:
        puntaje += PTS_CTX_256K_BONUS
        desglose.append(f"ctx256k={PTS_CTX_256K_BONUS}")
    if ctx >= 1000000:
        puntaje += PTS_CTX_1M_BONUS
        desglose.append(f"ctx1M={PTS_CTX_1M_BONUS}")
    return puntaje, desglose


def bonus_max_tokens(max_completion_tokens: int | float | None) -> Tuple[int, List[str]]:
    tok = int(max_completion_tokens or 0)
    puntaje = 0
    desglose: List[str] = []
    if tok >= 131072:
        puntaje += PTS_MAXTOK_128K
        desglose.append(f"maxTok128k={PTS_MAXTOK_128K}")
    elif tok >= 32768:
        puntaje += PTS_MAXTOK_32K
        desglose.append(f"maxTok32k={PTS_MAXTOK_32K}")
    elif tok >= 8192:
        puntaje += PTS_MAXTOK_8K
        desglose.append(f"maxTok8k={PTS_MAXTOK_8K}")
    return puntaje, desglose


def bonus_parametros(parametros_b: int | float | None) -> Tuple[int, List[str]]:
    params = float(parametros_b or 0.0)
    puntaje = 0
    desglose: List[str] = []
    if params >= 100.0:
        puntaje += PTS_PARAM_MUY_ALTO
        desglose.append(f"size_100B+={PTS_PARAM_MUY_ALTO}")
    elif params >= 40.0:
        puntaje += PTS_PARAM_ALTO
        desglose.append(f"size_40B+={PTS_PARAM_ALTO}")
    elif params >= 14.0:
        puntaje += PTS_PARAM_MEDIO
        desglose.append(f"size_14B+={PTS_PARAM_MEDIO}")
    elif params >= 7.0:
        puntaje += PTS_PARAM_BAJO
        desglose.append(f"size_7B+={PTS_PARAM_BAJO}")
    elif params > 0.0:
        puntaje += PTS_PARAM_MINIMO
        desglose.append(f"size_under7B={PTS_PARAM_MINIMO}")
    return puntaje, desglose


def calcular_puntaje_comun(
    capacidades: Dict[str, Any] | None,
    contexto: int | float | None = 0,
    max_completion_tokens: int | float | None = 0,
    parametros_b: int | float | None = 0.0,
) -> Tuple[int, List[str], Dict[str, bool]]:
    caps = normalizar_capacidades(capacidades)
    puntaje = 0
    desglose: List[str] = []

    if caps["vision"]:
        puntaje += PTS_VISION
        desglose.append(f"vision={PTS_VISION}")

    p_ctx, d_ctx = bonus_contexto(contexto)
    puntaje += p_ctx
    desglose.extend(d_ctx)

    p_tok, d_tok = bonus_max_tokens(max_completion_tokens)
    puntaje += p_tok
    desglose.extend(d_tok)

    p_param, d_param = bonus_parametros(parametros_b)
    puntaje += p_param
    desglose.extend(d_param)

    return puntaje, desglose, caps


def cumple_minimos(caps_norm: Dict[str, bool], probe_ok: bool) -> bool:
    return bool(probe_ok and caps_norm.get("herramientas") and caps_norm.get("reasoning"))


def clave_orden_modelo(modelo: Dict[str, Any]) -> tuple:
    return (
        int(modelo.get("puntaje", 0)),
        float(modelo.get("parametros_b", 0.0) or 0.0),
        int(modelo.get("contexto", 0) or 0),
        int(modelo.get("max_completion_tokens", 0) or 0),
        1 if modelo.get("capacidades_norm", {}).get("reasoning") else 0,
        1 if modelo.get("capacidades_norm", {}).get("herramientas") else 0,
        str(modelo.get("modelo_base", modelo.get("id", ""))),
        str(modelo.get("proveedor", "")),
        str(modelo.get("id", modelo.get("modelo", ""))),
    )


def agrupar_por_modelo_base(entradas: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    grupos: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for entrada in entradas:
        base = entrada.get("modelo_base") or entrada.get("id") or entrada.get("modelo") or entrada.get("nombre") or "desconocido"
        grupos[base].append(entrada)

    resultado: List[Dict[str, Any]] = []
    for modelo_base, items in grupos.items():
        items_ordenados = sorted(items, key=clave_orden_modelo, reverse=True)
        mejor = items_ordenados[0] if items_ordenados else {}
        resultado.append({
            "modelo_base": modelo_base,
            "mejor_puntaje": mejor.get("puntaje", 0),
            "cantidad_rutas": len(items_ordenados),
            "rutas": items_ordenados,
        })

    resultado.sort(key=lambda g: (
        int(g.get("mejor_puntaje", 0)),
        len(g.get("rutas", [])),
        str(g.get("modelo_base", "")),
    ), reverse=True)
    return resultado
