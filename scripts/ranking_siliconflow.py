#!/usr/bin/env python3
"""Ranking local de SiliconFlow para Núcleo IA.

Extrae dinámicamente los modelos del endpoint v1/models de SiliconFlow
y filtra estrictamente los de pago (aquellos que comienzan con "Pro/").
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

from ranking_common import calcular_puntaje_comun, clave_orden_modelo, cumple_minimos
from secret_utils import get_siliconflow_api_key, load_local_env, _norm_env_suffix

RAIZ = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
STATE_DIR = os.path.join(RAIZ, "state")
SALIDA = os.path.join(STATE_DIR, "ranking_siliconflow.json")


def obtener_cuentas_siliconflow() -> list[dict]:
    """Carga claves distintas para rotar las pruebas entre cuentas."""
    root = Path(RAIZ)
    load_local_env(root)
    try:
        data = json.loads((root / "cuentas.json").read_text(encoding="utf-8"))
    except Exception:
        data = {}
    cuentas = data.get("proveedores", {}).get("siliconflow", {}).get("cuentas", [])
    resultado = []
    vistas = set()
    for idx, cuenta in enumerate(cuentas, 1):
        account_id = str(cuenta.get("id", f"siliconflow_{idx}"))
        candidatos = [
            cuenta.get("api_key"),
            os.getenv(f"SILICONFLOW_API_KEY_{_norm_env_suffix(account_id)}"),
            os.getenv(f"SILICONFLOW_API_KEY_{idx}"),
            os.getenv("SILICONFLOW_API_KEY") if idx == 1 else None,
        ]
        clave = next((str(x).strip() for x in candidatos if x and not str(x).startswith("TU_")), None)
        if clave and clave not in vistas:
            resultado.append({"id": account_id, "api_key": clave})
            vistas.add(clave)
    if not resultado:
        clave = get_siliconflow_api_key(root)
        if clave:
            resultado.append({"id": "siliconflow_default", "api_key": clave})
    return resultado

def obtener_catalogo_gratis() -> list[dict]:
    api_key = get_siliconflow_api_key(Path(RAIZ))
    if not api_key:
        print("[!] No se encontró API Key para SiliconFlow. No se pueden actualizar los modelos.")
        return []

    url = "https://api.siliconflow.com/v1/models"
    req = urllib.request.Request(url, headers={
        "Authorization": f"Bearer {api_key}",
        "Accept": "application/json"
    })
    
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
    except Exception as e:
        print(f"[!] Error contactando API de SiliconFlow: {e}")
        return []
    
    modelos = data.get("data", [])
    catalogo_gratis = []
    
    for m in modelos:
        m_id = m.get("id", "")
        # Filtro estricto: modelos de pago empiezan por 'Pro/' o 'vendor/'
        # Si el modelo tiene un nombre estándar asume que es free open source, 
        # pero por seguridad ignoramos los sospechosos.
        if m_id.startswith("Pro/") or m_id.startswith("vendor/") or m_id.startswith("Premium/"):
            continue
            
        # Determinar contexto aproximado y capacidades base basado en nombre (heurística simple para open source)
        contexto = 32000
        herramientas = False
        if "Qwen2.5" in m_id or "Llama-3" in m_id:
            contexto = 128000
            if "Instruct" in m_id:
                herramientas = True
                
        catalogo_gratis.append({
            "model": m_id,
            "contexto": contexto,
            "max_completion_tokens": 4096,
            "parametros_b": 0,
            "capacidades": {"herramientas": herramientas, "vision": "vl" in m_id.lower() or "vision" in m_id.lower()}
        })
        
    return catalogo_gratis


def prober_modelo(modelo: str, api_key: str | None) -> tuple[bool, str, str]:
    if not api_key:
        return False, "sin_clave", ""
    payload = json.dumps({
        "model": modelo,
        "messages": [{"role": "user", "content": "Responde únicamente: OK"}],
        "max_tokens": 8,
    }).encode("utf-8")
    req = urllib.request.Request(
        "https://api.siliconflow.com/v1/chat/completions", data=payload, method="POST",
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
    cuentas = obtener_cuentas_siliconflow()
    api_key = cuentas[0]["api_key"] if cuentas else None
    modelos_permitidos = obtener_catalogo_gratis()
    
    ranking = []
    cuentas_sin_saldo = set()
    for indice, fila in enumerate(modelos_permitidos):
        model = fila.get("model", "")
        cuenta = cuentas[indice % len(cuentas)] if cuentas else {"id": "sin_cuenta", "api_key": None}
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
        if len(cuentas) > 0 and len(cuentas_sin_saldo) == len(cuentas):
            probe_ok, probe_estado, probe_preview = False, "no_probado_saldo_agotado", ""
        else:
            probe_ok, probe_estado, probe_preview = prober_modelo(model, cuenta["api_key"])
            if probe_estado == "http_402":
                cuentas_sin_saldo.add(cuenta["id"])
        apto = cumple_minimos(caps_norm, probe_ok)

        entrada = {
            "id": model,
            "modelo": model,
            "modelo_base": model,
            "nombre": model,
            "proveedor": "siliconflow",
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
            "cuenta_prueba": cuenta["id"],
            "desglose": " + ".join(desglose) if desglose else "",
            "fuente": "siliconflow_api",
        }
        ranking.append(entrada)

    ranking.sort(key=clave_orden_modelo, reverse=True)
    for i, r in enumerate(ranking):
        r["posicion"] = i + 1

    resultado = {
        "generado": datetime.now().isoformat(),
        "service": "siliconflow",
        "total_modelos": len(ranking),
        "total_aptos_finales": sum(1 for r in ranking if r.get("apto_agente")),
        "ranking": ranking,
        "ranking_final": [r for r in ranking if r.get("apto_agente")],
        "ranking_rechazados_probe": [r for r in ranking if not r.get("apto_agente")],
        "cuentas_prueba": [c["id"] for c in cuentas],
        "politica_pruebas": "una_prueba_por_modelo_rotando_cuentas; se detiene si todas devuelven HTTP 402",
        "ficha_comun": {
            "filtro": ["herramientas", "reasoning", "probe_ok"],
        },
    }

    os.makedirs(STATE_DIR, exist_ok=True)
    with open(SALIDA, "w", encoding="utf-8") as f:
        json.dump(resultado, f, indent=2, ensure_ascii=False)

    print("═" * 80)
    print("  RANKING DE SILICONFLOW — Núcleo IA (Solo Gratuitos)")
    print("═" * 80)
    for r in ranking:
        print(f"  #{r['posicion']:>2} {r['puntaje']:>3} pts  {r['modelo']}")
    print(f"\nGuardado en: {SALIDA}")
    return resultado


if __name__ == "__main__":
    generar_ranking()
