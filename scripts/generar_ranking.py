#!/usr/bin/env python3
"""Ranking local de Ollama para Núcleo IA.

Usa el catálogo local + resultados de probe real para generar una ficha común
comparable con NVIDIA y OpenRouter.
"""
from __future__ import annotations

import json
import os
from datetime import datetime

from ranking_common import calcular_puntaje_comun, cumple_minimos, clave_orden_modelo

RAIZ = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
STATE_DIR = os.path.join(RAIZ, "state")
CATALOGO = os.path.join(STATE_DIR, "catalogo_modelos.json")
PROBES = os.path.join(STATE_DIR, "ollama_real_test_results.json")
RANKING_SALIDA = os.path.join(STATE_DIR, "ranking_modelos.json")
RANKING_OLLAMA = os.path.join(STATE_DIR, "ranking_ollama.json")


def cargar_json(ruta: str) -> dict:
    if not os.path.exists(ruta):
        return {}
    try:
        with open(ruta, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def indexar_probes(datos: dict) -> dict:
    idx = {}
    for fila in datos.get("results", []):
        idx[fila.get("model", "")] = fila
    return idx


def generar_ranking() -> dict:
    if not os.path.exists(CATALOGO):
        print(f"[!] No existe {CATALOGO}. Ejecutar ollama_cloud_monitor.py primero.")
        raise SystemExit(1)

    catalogo = cargar_json(CATALOGO)
    probes = indexar_probes(cargar_json(PROBES))
    modelos = catalogo.get("modelos", [])
    if not modelos:
        print("[!] Catálogo vacío.")
        raise SystemExit(1)

    rankeados = []
    rechazados = []
    for m in modelos:
        nombre = m.get("nombre", "")
        caps = m.get("capacidades", {})
        contexto = m.get("contexto", 0)
        params = m.get("parametros_b", 0.0)
        if (not params or float(params) <= 0.0) and "minimax-m3" in nombre.lower():
            params = 456.0
        elif (not params or float(params) <= 0.0) and "minimax-m2.7" in nombre.lower():
            params = 229.0

        probe = probes.get(nombre, {})
        # Si el modelo tiene cuentas_disponibles y fue verificado por show, es considerado apto aunque no haya probe sintético
        probe_archivo_ok = str(probe.get("status", "")).upper() == "OK"
        probe_monitor_ok = m.get("probe_estado") == "OK_GENERACION" and bool(m.get("cuentas_disponibles"))
        probe_ok = probe_archivo_ok or probe_monitor_ok
        probe_estado = m.get("probe_estado", "OK" if probe_archivo_ok else "SIN_PROBE") if probe_monitor_ok else (probe.get("status") if probe_archivo_ok else "SIN_PROBE")
        probe_preview = probe.get("detail", "")

        # El monitor de Ollama clasifica cada ficha leyendo su página Jina.
        # Un precio publicado excluye el modelo del ranking gratuito.
        gratis = bool(m.get("gratis", True))

        puntaje, desglose, caps_norm = calcular_puntaje_comun(caps, contexto=contexto, max_completion_tokens=0, parametros_b=params)
        apto = gratis and cumple_minimos(caps_norm, probe_ok)

        entrada = {
            "id": nombre,
            "modelo": nombre,
            "modelo_base": nombre,
            "familia": m.get("familia", "?"),
            "proveedor": "ollama",
            "puntaje": puntaje,
            "apto_agente": apto,
            "parametros_b": float(params or 0.0),
            "contexto": int(contexto or 0),
            "max_completion_tokens": 0,
            "capacidades": caps,
            "capacidades_norm": caps_norm,
            "gratis": gratis,
            "precio_estado": m.get("precio_estado", "no_informado"),
            "precio_evidencia": m.get("precio_evidencia", ""),
            "url_fuente": m.get("url_fuente", ""),
            "probe_ok": probe_ok,
            "probe_estado": probe_estado,
            "probe_preview": probe_preview[:180],
            "tool_probe_ok": m.get("tool_probe_ok"),
            "tool_probe_estado": m.get("tool_probe_estado", "no_ejecutada"),
            "desglose": " + ".join(desglose) if desglose else "",
            "fuente": "ollama_cloud_monitor",
        }

        if apto:
            rankeados.append(entrada)
        else:
            rechazados.append(entrada)

    rankeados.sort(key=clave_orden_modelo, reverse=True)
    for i, r in enumerate(rankeados):
        r["posicion"] = i + 1

    resultado = {
        "generado": datetime.now().isoformat(),
        "total_modelos": len(modelos),
        "total_aptos_finales": len(rankeados),
        "ranking": rankeados,
        "ranking_final": rankeados,
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
        },
    }

    os.makedirs(STATE_DIR, exist_ok=True)
    for ruta in (RANKING_SALIDA, RANKING_OLLAMA):
        with open(ruta, "w", encoding="utf-8") as f:
            json.dump(resultado, f, indent=2, ensure_ascii=False)

    print("═" * 80)
    print("  RANKING DE MODELOS OLLAMA — Núcleo IA")
    print("═" * 80)
    print(f"[APTOS FINALES] {len(rankeados)} / {len(modelos)}")
    for r in rankeados[:10]:
        print(f"  #{r['posicion']:>2} {r['puntaje']:>3} pts  {r['modelo']:<28s}  ctx={r['contexto']:<7d}  params={r['parametros_b']:<8.1f}  probe={r['probe_estado']}")
    if rechazados:
        print(f"[RECHAZADOS] {len(rechazados)}")
        for r in rechazados[:10]:
            print(f"  - {r['modelo']:<28s} probe={r['probe_estado']}")
    print(f"\nGuardado en: {RANKING_SALIDA}")
    return resultado


if __name__ == "__main__":
    generar_ranking()
