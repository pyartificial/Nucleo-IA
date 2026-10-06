#!/usr/bin/env python3
"""Ranking local de Z.AI (internamente llamado Zhipu) para Núcleo IA.

La API actual publica ``glm-4.5-flash`` como modelo de acceso gratuito.
``glm-4-flash`` fue retirado y ya no debe anunciarse como ruta disponible.
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

from ranking_common import calcular_puntaje_comun, clave_orden_modelo, cumple_minimos
from ranking_quality import probar_herramienta_openai
from secret_utils import get_zhipu_api_key

RAIZ = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
STATE_DIR = os.path.join(RAIZ, "state")
SALIDA = os.path.join(STATE_DIR, "ranking_zhipu.json")

URL_CHAT = "https://api.z.ai/api/paas/v4/chat/completions"
URL_PRECIOS = "https://r.jina.ai/https://docs.z.ai/guides/overview/pricing"

# Datos de capacidad conocidos. La condición de gratuidad NO sale de esta
# tabla: se vuelve a leer de la tabla oficial de precios en cada ejecución.
FICHAS_CONOCIDAS = {
    "glm-4.7-flash": {
        "contexto": 200000, "max_completion_tokens": 128000, "parametros_b": 0.0,
        "capacidades": {"herramientas": True, "reasoning": True, "vision": False},
    },
    "glm-4.5-flash": {
        "contexto": 128000, "max_completion_tokens": 8192, "parametros_b": 32.0,
        "capacidades": {"herramientas": True, "reasoning": True, "vision": False},
    },
    "glm-4.6v-flash": {
        "contexto": 128000, "max_completion_tokens": 8192, "parametros_b": 0.0,
        "capacidades": {"herramientas": True, "reasoning": True, "vision": True},
    },
}

def descubrir_modelos_gratuitos() -> tuple[list[dict], str]:
    """Lee la tabla oficial y acepta solo filas cuyo precio completo es Free."""
    req = urllib.request.Request(URL_PRECIOS, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            texto = resp.read().decode("utf-8", errors="replace")
        nombres: list[str] = []
        for linea in texto.splitlines():
            if not linea.lstrip().startswith("|"):
                continue
            celdas = [c.strip() for c in linea.strip().strip("|").split("|")]
            if len(celdas) < 3 or not celdas[0].upper().startswith("GLM-"):
                continue
            precios = celdas[1:]
            # "Limited-time Free" no significa modelo gratuito: hay precio de
            # entrada/salida. Solo se admite Free puro en todas las columnas.
            if precios and all(p.lower() == "free" for p in precios):
                nombres.append(celdas[0].lower())
        if nombres:
            return [crear_ficha(n) for n in dict.fromkeys(nombres)], "pricing_oficial"
    except Exception as exc:
        print(f"  [!] No pude actualizar precios oficiales: {type(exc).__name__}")
    # Fallo cerrado: si no se puede comprobar el precio actual, no se prueba
    # una lista histórica que mañana podría consumir crédito de pago.
    return [], "precios_no_disponibles"


def crear_ficha(modelo: str) -> dict:
    conocida = FICHAS_CONOCIDAS.get(modelo, {})
    vision = "v-flash" in modelo
    return {
        "model": modelo,
        "contexto": int(conocida.get("contexto", 0)),
        "max_completion_tokens": int(conocida.get("max_completion_tokens", 0)),
        "parametros_b": float(conocida.get("parametros_b", 0.0)),
        "capacidades": conocida.get("capacidades", {
            "herramientas": True, "reasoning": True, "vision": vision,
        }),
    }


def prober_modelo(modelo: str, api_key: str | None) -> tuple[bool, str, str]:
    if not api_key:
        return False, "sin_clave", ""
    payload = json.dumps({
        "model": modelo,
        "messages": [{"role": "user", "content": "Responde únicamente OK, sin explicación."}],
        "max_tokens": 512,
    }).encode("utf-8")
    req = urllib.request.Request(
        URL_CHAT, data=payload, method="POST",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read().decode("utf-8", errors="replace"))
        opciones = data.get("choices") or []
        texto = str(opciones[0].get("message", {}).get("content", "") if opciones else "").strip()
        return bool(texto), "ok" if texto else "respuesta_vacia", texto[:180]
    except urllib.error.HTTPError as exc:
        return False, f"http_{exc.code}", ""
    except Exception as exc:
        return False, type(exc).__name__, ""

def generar_ranking() -> dict:
    api_key = get_zhipu_api_key(Path(RAIZ))
    modelos_permitidos, fuente_catalogo = descubrir_modelos_gratuitos()
    ranking = []
    for fila in modelos_permitidos:
        model = fila.get("model", "")
        caps = fila.get("capacidades", {}) or {}
        contexto = int(fila.get("contexto", 0) or 0)
        max_completion_tokens = int(fila.get("max_completion_tokens", 0) or 0)
        parametros_b = float(fila.get("parametros_b", 0.0) or 0.0)

        puntaje, desglose, caps_norm = calcular_puntaje_comun(
            caps,
            contexto=contexto,
            max_completion_tokens=max_completion_tokens,
            parametros_b=parametros_b,
        )
        probe_ok, probe_estado, probe_preview = prober_modelo(model, api_key)
        tool_probe_ok = False
        tool_probe_estado = "no_ejecutada"
        if probe_ok and caps_norm.get("herramientas"):
            tool_probe_ok, tool_probe_estado = probar_herramienta_openai(
                URL_CHAT, api_key or "", model,
            )
        apto = cumple_minimos(caps_norm, probe_ok)

        entrada = {
            "id": model,
            "modelo": model,
            "modelo_base": model,
            "nombre": model,
            "proveedor": "zhipu",
            "puntaje": puntaje,
            "apto_agente": apto,
            "parametros_b": parametros_b,
            "contexto": contexto,
            "max_completion_tokens": max_completion_tokens,
            "capacidades": caps,
            "capacidades_norm": caps_norm,
            "gratis": True,
            "probe_ok": probe_ok,
            "probe_estado": probe_estado,
            "probe_preview": probe_preview,
            "tool_probe_ok": tool_probe_ok,
            "tool_probe_estado": tool_probe_estado,
            "desglose": " + ".join(desglose) if desglose else "",
            "fuente": fuente_catalogo,
        }
        ranking.append(entrada)

    ranking.sort(key=clave_orden_modelo, reverse=True)
    for i, r in enumerate(ranking):
        r["posicion"] = i + 1

    resultado = {
        "generado": datetime.now().isoformat(),
        "service": "zhipu",
        "total_modelos": len(ranking),
        "total_aptos_finales": sum(1 for r in ranking if r.get("apto_agente")),
        "fuente_catalogo": fuente_catalogo,
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

    print("═" * 80)
    print("  RANKING DE ZHIPU AI — Núcleo IA (Solo Gratuitos)")
    print("═" * 80)
    for r in ranking:
        print(f"  #{r['posicion']:>2} {r['puntaje']:>3} pts  {r['modelo']}")
    print(f"\nGuardado en: {SALIDA}")
    return resultado


if __name__ == "__main__":
    generar_ranking()
