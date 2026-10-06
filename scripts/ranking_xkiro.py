#!/usr/bin/env python3
"""Ranking vivo de xKiro para Núcleo IA.

Acepta como gratuitos únicamente los modelos que el catálogo oficial marca con
``access_tier=free`` y precio cero. Cada ruta se prueba con la cuenta local;
los modelos agénticos además deben devolver una tool call exacta.
"""
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ranking_common import (
    calcular_puntaje_comun,
    clave_orden_modelo,
    extraer_parametros,
)
from ranking_pasarelas_free import _capabilities as _descubrir_capacidades
from secret_utils import get_xkiro_accounts, get_xkiro_api_key

RAIZ = Path(__file__).resolve().parent.parent
STATE_DIR = RAIZ / "state"
SALIDA = STATE_DIR / "ranking_xkiro.json"
CATALOGO_CACHE = STATE_DIR / "catalogo_xkiro.json"

BASE_URL = "https://api.xkiro.com/v1"
URL_MODELOS = f"{BASE_URL}/models"
URL_CHAT = f"{BASE_URL}/chat/completions"
URL_USAGE = f"{BASE_URL}/usage"
USER_AGENT = "Nucleo-IA-Ranking/1.0"


def _request_json(
    url: str,
    *,
    api_key: str | None = None,
    payload: dict[str, Any] | None = None,
    timeout: int = 45,
) -> tuple[int, dict[str, Any], dict[str, str]]:
    headers = {"Accept": "application/json", "User-Agent": USER_AGENT}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    data = None
    method = "GET"
    if payload is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(payload).encode("utf-8")
        method = "POST"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            body = json.loads(response.read().decode("utf-8", "replace"))
            return response.status, body, {k.lower(): v for k, v in response.headers.items()}
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", "replace")
        try:
            body = json.loads(raw)
        except Exception:
            body = {"error": {"message": raw[:240]}}
        return exc.code, body, {k.lower(): v for k, v in exc.headers.items()}
    except Exception as exc:
        return 0, {"error": {"type": type(exc).__name__, "message": str(exc)[:240]}}, {}


def _error_state(status: int, body: dict[str, Any]) -> tuple[str, str]:
    error = body.get("error") if isinstance(body, dict) else {}
    if not isinstance(error, dict):
        error = {"message": str(error)}
    code = str(error.get("code") or error.get("type") or "").strip()
    message = str(error.get("message") or "").strip().replace("\n", " ")
    if status == 0:
        label = code or "error_conexion"
    elif status == 429:
        label = "cuota_free_o_rate_limit"
    elif status == 403:
        label = "cuenta_sin_permiso"
    elif status == 402:
        label = "saldo_insuficiente"
    elif status == 401:
        label = "clave_invalida"
    else:
        label = f"http_{status}"
    return label, f"{code}: {message}".strip(": ")[:240]


def obtener_catalogo() -> tuple[list[dict[str, Any]], str]:
    status, body, _ = _request_json(URL_MODELOS, timeout=30)
    if status == 200 and isinstance(body.get("data"), list):
        rows = [m for m in body["data"] if isinstance(m, dict) and m.get("id")]
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        CATALOGO_CACHE.write_text(
            json.dumps({"generado": datetime.now(timezone.utc).isoformat(), "data": rows}, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        return rows, "xkiro_api_v1_models"
    try:
        cached = json.loads(CATALOGO_CACHE.read_text(encoding="utf-8"))
        rows = [m for m in cached.get("data", []) if isinstance(m, dict) and m.get("id")]
        if rows:
            return rows, "cache_xkiro_ultimo_catalogo_valido"
    except Exception:
        pass
    raise RuntimeError(f"No se pudo obtener el catálogo de xKiro ({status})")


def obtener_cuota(api_key: str) -> dict[str, Any]:
    status, body, _ = _request_json(URL_USAGE, api_key=api_key, timeout=30)
    if status != 200:
        estado, detalle = _error_state(status, body)
        return {"ok": False, "estado": estado, "detalle": detalle}
    free = body.get("free_tokens") or {}
    return {
        "ok": True,
        "plan": body.get("plan"),
        "free_tokens": {
            "used_today": free.get("used_today"),
            "limit_per_day": free.get("limit_per_day"),
            "remaining": free.get("remaining"),
        },
    }


def _cuentas_xkiro() -> list[tuple[str, str]]:
    cuentas: list[tuple[str, str]] = []
    vistos: set[str] = set()
    for index, cuenta in enumerate(get_xkiro_accounts(RAIZ), 1):
        key = str(cuenta.get("api_key") or "").strip()
        if not key or key.startswith("TU_") or key in vistos:
            continue
        account_id = str(cuenta.get("id") or f"xkiro_{index}")
        cuentas.append((account_id, key))
        vistos.add(key)
    if not cuentas:
        key = get_xkiro_api_key(RAIZ)
        if key:
            cuentas.append(("clave_global", str(key).strip()))
    return cuentas


def _precios_cero(modelo: dict[str, Any]) -> bool:
    pricing = modelo.get("pricing") or {}
    try:
        return float(pricing.get("input", -1)) == 0.0 and float(pricing.get("output", -1)) == 0.0
    except (TypeError, ValueError):
        return False


def _catalogo_capacidades(catalogo: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    result: dict[str, list[dict[str, Any]]] = {}
    for model in catalogo:
        caps, secondary, modalities = _descubrir_capacidades(model)
        raw_caps = model.get("capabilities") if isinstance(model.get("capabilities"), dict) else {}
        if raw_caps.get("vision") and "vision_image" not in secondary:
            secondary.append("vision_image")
            modalities.append("image")
        free = model.get("access_tier") == "free" and _precios_cero(model)
        for capability in sorted(set(secondary)):
            result.setdefault(capability, []).append({
                "id": str(model.get("id") or ""),
                "modelo": str(model.get("id") or ""),
                "proveedor": "xkiro",
                "gratis": free,
                "probe_ok": False,
                "implementado": False,
                "estado_prueba": "solo_catalogo",
                "modalidades": sorted(set(modalities)),
                "fuente": "catalogo_xkiro; capacidad descubierta por metadatos, requiere prueba/adaptador",
            })
    for entries in result.values():
        entries.sort(key=lambda row: (not row["gratis"], row["id"]))
    return result


def _payload_texto(model_id: str) -> dict[str, Any]:
    return {
        "model": model_id,
        "messages": [{"role": "user", "content": "Responde únicamente: OK"}],
        "temperature": 0,
        "max_tokens": 16,
        "stream": False,
    }


def _payload_herramienta(model_id: str) -> dict[str, Any]:
    return {
        "model": model_id,
        "messages": [{
            "role": "user",
            "content": "Llama a sumar_numeros con a=17 y b=25. No calcules ni respondas con texto.",
        }],
        "tools": [{
            "type": "function",
            "function": {
                "name": "sumar_numeros",
                "description": "Suma exactamente dos enteros.",
                "parameters": {
                    "type": "object",
                    "properties": {"a": {"type": "integer"}, "b": {"type": "integer"}},
                    "required": ["a", "b"],
                },
            },
        }],
        "tool_choice": {"type": "function", "function": {"name": "sumar_numeros"}},
        "temperature": 0,
        "max_tokens": 128,
        "stream": False,
    }


def _tool_call_exacta(body: dict[str, Any]) -> bool:
    choices = body.get("choices") or []
    message = (choices[0].get("message") or {}) if choices else {}
    for call in message.get("tool_calls") or []:
        function = call.get("function") or {}
        if function.get("name") != "sumar_numeros":
            continue
        args = function.get("arguments") or {}
        try:
            if isinstance(args, str):
                args = json.loads(args)
        except Exception:
            continue
        if isinstance(args, dict) and args.get("a") == 17 and args.get("b") == 25:
            return True
    return False


def probar_modelo(modelo: dict[str, Any], api_key: str) -> dict[str, Any]:
    model_id = str(modelo["id"])
    raw_caps = modelo.get("capabilities") or {}
    status = 0
    body: dict[str, Any] = {}
    headers: dict[str, str] = {}
    for intento in range(3):
        status, body, headers = _request_json(URL_CHAT, api_key=api_key, payload=_payload_texto(model_id), timeout=100)
        if status not in {429, 500, 502, 503} or intento == 2:
            break
        if status == 429:
            try:
                retry_after = float(headers.get("retry-after", "0"))
            except ValueError:
                retry_after = 0.0
            # Una espera larga indica cuota diaria o una ventana que no debe
            # bloquear la actualización completa.
            if retry_after <= 0 or retry_after > 30:
                break
            time.sleep(retry_after)
        else:
            time.sleep(1.0 + intento)

    if status != 200:
        estado, detalle = _error_state(status, body)
        return {
            "probe_ok": False,
            "probe_estado": estado,
            "probe_preview": detalle,
            "tool_probe_ok": False if raw_caps.get("tools") else None,
            "tool_probe_estado": estado if raw_caps.get("tools") else "no_requerida",
            "reasoning_probe_ok": False if raw_caps.get("reasoning") else None,
            "reasoning_probe_estado": estado if raw_caps.get("reasoning") else "no_requerida",
        }

    choices = body.get("choices") or []
    message = (choices[0].get("message") or {}) if choices else {}
    content = str(message.get("content") or "").strip()
    if not content:
        return {
            "probe_ok": False,
            "probe_estado": "respuesta_vacia",
            "probe_preview": "",
            "tool_probe_ok": False if raw_caps.get("tools") else None,
            "tool_probe_estado": "respuesta_vacia" if raw_caps.get("tools") else "no_requerida",
            "reasoning_probe_ok": False if raw_caps.get("reasoning") else None,
            "reasoning_probe_estado": "respuesta_vacia" if raw_caps.get("reasoning") else "no_requerida",
        }

    tool_ok: bool | None = None
    tool_state = "no_requerida"
    if raw_caps.get("tools"):
        tool_status, tool_body, _ = _request_json(URL_CHAT, api_key=api_key, payload=_payload_herramienta(model_id), timeout=100)
        tool_ok = tool_status == 200 and _tool_call_exacta(tool_body)
        tool_state = "ok_forzada" if tool_ok else (f"http_{tool_status}" if tool_status != 200 else "respuesta_incorrecta")

    reasoning_ok: bool | None = None
    reasoning_state = "no_requerida"
    if raw_caps.get("reasoning"):
        reasoning_payload = {
            "model": model_id,
            "messages": [{"role": "user", "content": (
                "En una carrera, Lara llegó antes que Inés; Inés antes que Bruno; "
                "Bruno antes que Mateo. ¿Quién llegó segundo? Responde únicamente: INES"
            )}],
            "temperature": 0,
            "max_tokens": 24,
            "stream": False,
        }
        reasoning_status, reasoning_body, _ = _request_json(URL_CHAT, api_key=api_key, payload=reasoning_payload, timeout=100)
        reasoning_choices = reasoning_body.get("choices") or []
        reasoning_message = (reasoning_choices[0].get("message") or {}) if reasoning_choices else {}
        reasoning_text = str(reasoning_message.get("content") or "").upper().replace("Í", "I").strip(" .,:;!¡¿?\"'")
        reasoning_ok = reasoning_status == 200 and reasoning_text == "INES"
        reasoning_state = "ok_exacta" if reasoning_ok else (f"http_{reasoning_status}" if reasoning_status != 200 else "respuesta_incorrecta")

    return {
        "probe_ok": True,
        "probe_estado": "ok",
        "probe_preview": content[:180],
        "tool_probe_ok": tool_ok,
        "tool_probe_estado": tool_state,
        "reasoning_probe_ok": reasoning_ok,
        "reasoning_probe_estado": reasoning_state,
    }


def generar_ranking() -> dict[str, Any]:
    print("═" * 80)
    print("  RANKING DE xKIRO — Núcleo IA (catálogo free + prueba real por ruta)")
    print("═" * 80)

    cuentas = _cuentas_xkiro()
    if not cuentas:
        raise SystemExit("[!] Falta XKIRO_API_KEY; no se aceptan modelos sin prueba real.")

    catalogo, fuente = obtener_catalogo()
    rankings_capacidades = _catalogo_capacidades(catalogo)
    cuotas_antes = {account_id: obtener_cuota(key) for account_id, key in cuentas}
    cuentas_validas = [(account_id, key) for account_id, key in cuentas if cuotas_antes[account_id].get("ok")]
    if not cuentas_validas:
        estados = sorted({str(row.get("estado") or "sin_estado") for row in cuotas_antes.values()})
        raise SystemExit(f"[!] No se pudo validar ninguna cuenta xKiro: {' / '.join(estados)}")

    cuentas_con_cuota = []
    for account_id, key in cuentas_validas:
        free = cuotas_antes[account_id].get("free_tokens") or {}
        remaining = free.get("remaining")
        if remaining is not None:
            try:
                if int(remaining) <= 0:
                    continue
            except (TypeError, ValueError):
                continue
        cuentas_con_cuota.append((account_id, key))

    candidatos = [
        m for m in catalogo
        if m.get("access_tier") == "free" and _precios_cero(m)
    ]
    print(f"  Catálogo chat: {len(catalogo)} | gratuitos verificables: {len(candidatos)}")
    print(f"  Cuentas válidas: {len(cuentas_validas)} | con cuota free disponible: {len(cuentas_con_cuota)}")

    ranking: list[dict[str, Any]] = []
    for pos, modelo in enumerate(candidatos, 1):
        model_id = str(modelo["id"])
        raw_caps = modelo.get("capabilities") if isinstance(modelo.get("capabilities"), dict) else {}
        elegido_id = ""
        prueba = {
            "probe_ok": False,
            "probe_estado": "cuota_free_agotada" if cuentas_validas else "cuenta_no_verificada",
            "probe_preview": "Ninguna cuenta verificada tiene cuota free disponible para la prueba.",
            "tool_probe_ok": False if raw_caps.get("tools") else None,
            "tool_probe_estado": "cuota_free_agotada" if raw_caps.get("tools") else "no_requerida",
            "reasoning_probe_ok": False if raw_caps.get("reasoning") else None,
            "reasoning_probe_estado": "cuota_free_agotada" if raw_caps.get("reasoning") else "no_requerida",
        }
        for account_id, key in cuentas_con_cuota:
            candidate = probar_modelo(modelo, key)
            if candidate.get("probe_ok"):
                elegido_id = account_id
                prueba = candidate
                if candidate.get("tool_probe_ok") is True and candidate.get("reasoning_probe_ok") is True:
                    break
            elif not prueba.get("probe_ok"):
                prueba = candidate

        caps = {
            "herramientas": prueba.get("tool_probe_ok") is True,
            "reasoning": prueba.get("reasoning_probe_ok") is True,
            "vision": bool(raw_caps.get("vision")),
            "audio": bool(raw_caps.get("audio")),
        }
        contexto = int(modelo.get("context_length") or 0)
        max_tokens = int(modelo.get("max_output_tokens") or 0)
        parametros_b = extraer_parametros(model_id)
        puntaje, desglose, caps_norm = calcular_puntaje_comun(
            caps, contexto=contexto, max_completion_tokens=max_tokens, parametros_b=parametros_b
        )
        apto = bool(
            prueba["probe_ok"]
            and prueba.get("tool_probe_ok") is True
            and prueba.get("reasoning_probe_ok") is True
            and caps_norm.get("herramientas")
            and caps_norm.get("reasoning")
        )
        entrada = {
            "id": model_id,
            "modelo": model_id,
            "modelo_base": model_id,
            "nombre": modelo.get("display_name") or model_id,
            "proveedor": "xkiro",
            "cuenta_id": elegido_id,
            "cuentas_compatibles": [elegido_id] if prueba.get("probe_ok") and elegido_id else [],
            "cuentas_probe_ok": [elegido_id] if apto and elegido_id else [],
            "puntaje": puntaje,
            "apto_agente": apto,
            "parametros_b": parametros_b,
            "contexto": contexto,
            "max_completion_tokens": max_tokens,
            "capacidades": caps,
            "capacidades_norm": caps_norm,
            "capacidades_secundarias": _descubrir_capacidades(modelo)[1],
            "modalidades": _descubrir_capacidades(modelo)[2],
            "adaptador_secundario_implementado": bool(raw_caps.get("vision") and prueba.get("probe_ok")),
            "gratis": True,
            "gratis_evidencia": "access_tier=free+pricing_input_output=0+probe_cuenta",
            "access_tier": modelo.get("access_tier"),
            "pricing": modelo.get("pricing") or {},
            "reasoning_efforts": modelo.get("reasoning_efforts") or {},
            "owned_by": modelo.get("owned_by"),
            **prueba,
            "desglose": " + ".join(desglose) if desglose else "",
            "fuente": fuente,
        }
        if raw_caps.get("vision") and "vision_image" not in entrada["capacidades_secundarias"]:
            entrada["capacidades_secundarias"].append("vision_image")
        for capability, rows in rankings_capacidades.items():
            for row in rows:
                if row["id"] == model_id and prueba.get("probe_ok"):
                    row["probe_ok"] = True
                    row["estado_prueba"] = "chat_verificado"
                    row["implementado"] = capability == "vision_image" and bool(raw_caps.get("vision"))
        ranking.append(entrada)
        etiqueta = "APTO" if apto else "SECUNDARIO" if prueba["probe_ok"] else "RECHAZADO"
        print(f"  [{pos:>2}/{len(candidatos)}] {etiqueta:10s} {model_id} ({prueba['probe_estado']})", flush=True)

    ranking.sort(key=clave_orden_modelo, reverse=True)
    for pos, row in enumerate(ranking, 1):
        row["posicion"] = pos

    resultado = {
        "generado": datetime.now(timezone.utc).isoformat(),
        "service": "xkiro",
        "fuente_catalogo": fuente,
        "total_catalogo": len(catalogo),
        "total_modelos": len(ranking),
        "total_modelos_respondieron": sum(bool(r.get("probe_ok")) for r in ranking),
        "total_aptos_finales": sum(bool(r.get("apto_agente")) for r in ranking),
        "cuota_antes": {account_id: cuotas_antes[account_id] for account_id, _ in cuentas},
        "cuota_despues": {account_id: obtener_cuota(key) for account_id, key in cuentas_validas},
        "ranking": ranking,
        "ranking_final": [r for r in ranking if r.get("apto_agente")],
        "ranking_secundario": [r for r in ranking if r.get("probe_ok") and not r.get("apto_agente")],
        "ranking_rechazados_probe": [r for r in ranking if not r.get("probe_ok")],
        "rankings_capacidades": rankings_capacidades,
        "ficha_comun": {
            "filtro": [
                "access_tier=free",
                "pricing.input=0",
                "pricing.output=0",
                "probe_ok",
                "tool_probe_ok",
                "herramientas",
                "reasoning",
            ],
            "nota": "El catálogo público no basta: cada modelo se prueba con la cuenta configurada.",
        },
    }
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    SALIDA.write_text(json.dumps(resultado, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(
        f"\n[+] xKiro: {resultado['total_modelos_respondieron']}/{len(ranking)} respondieron; "
        f"{resultado['total_aptos_finales']} entran al ranking principal."
    )
    print(f"Guardado en: {SALIDA}")
    return resultado


if __name__ == "__main__":
    generar_ranking()
