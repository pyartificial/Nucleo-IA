#!/usr/bin/env python3
"""Ranking vivo de las rutas gratuitas de Token Harbor para Núcleo IA.

La admisión es deliberadamente estricta:

* el ID debe venir del catálogo autenticado actual y terminar en ``:free``;
* la ruta debe responder con la cuenta configurada;
* para el ranking principal debe superar herramientas y razonamiento;
* una ruta retirada, vencida, sin consentimiento o sin cuota queda rechazada.

Nunca se prueba ni se incorpora el ID base pago de un modelo.
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

from ranking_common import calcular_puntaje_comun, clave_orden_modelo, extraer_parametros
from secret_utils import get_tokenharbor_accounts, get_tokenharbor_api_key
from ranking_pasarelas_free import _capabilities as _descubrir_capacidades

RAIZ = Path(__file__).resolve().parent.parent
STATE_DIR = RAIZ / "state"
SALIDA = STATE_DIR / "ranking_tokenharbor.json"
CATALOGO_CACHE = STATE_DIR / "catalogo_tokenharbor.json"
BASE_URL = "https://tokenharbor.ai/v1"
URL_MODELOS = f"{BASE_URL}/models"
URL_CHAT = f"{BASE_URL}/chat/completions"
USER_AGENT = "Nucleo-IA-Ranking/1.0"


def _request_json(
    url: str,
    *,
    api_key: str,
    payload: dict[str, Any] | None = None,
    timeout: int = 60,
) -> tuple[int, dict[str, Any], dict[str, str]]:
    headers = {
        "Accept": "application/json",
        "Authorization": f"Bearer {api_key}",
        "User-Agent": USER_AGENT,
    }
    data = None
    method = "GET"
    if payload is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(payload).encode("utf-8")
        method = "POST"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            raw = response.read().decode("utf-8", "replace")
            body = json.loads(raw) if raw.strip() else {}
            return response.status, body, {k.lower(): v for k, v in response.headers.items()}
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", "replace")
        try:
            body = json.loads(raw)
        except Exception:
            body = {"error": {"message": raw[:400]}}
        return exc.code, body, {k.lower(): v for k, v in exc.headers.items()}
    except Exception as exc:
        return 0, {"error": {"type": type(exc).__name__, "message": str(exc)[:400]}}, {}


def _error_state(status: int, body: dict[str, Any]) -> tuple[str, str]:
    error: Any = body.get("error") if isinstance(body, dict) else None
    if isinstance(error, str):
        code, message = "", error
    elif isinstance(error, dict):
        code = str(error.get("code") or error.get("type") or "").strip()
        message = str(error.get("message") or error.get("detail") or "").strip()
    else:
        code = str(body.get("code") or "") if isinstance(body, dict) else ""
        message = str(body.get("message") or body.get("detail") or "") if isinstance(body, dict) else ""
    combined = f"{code}: {message}".strip(": ").replace("\n", " ")[:300]
    lower = combined.lower()
    if status == 0:
        label = code or "error_conexion"
    elif status == 401:
        label = "clave_invalida"
    elif status == 402:
        label = "ruta_pago_o_saldo_insuficiente"
    elif status == 403 and any(x in lower for x in ("consent", "enable free", "free model", "opt-in")):
        label = "requiere_habilitar_modelos_free"
    elif status == 403:
        label = "cuenta_no_elegible_o_sin_permiso"
    elif status == 404:
        label = "modelo_retirado_o_no_disponible"
    elif status == 410:
        label = "modelo_temporal_finalizado"
    elif status == 429:
        label = "cuota_free_agotada_o_rate_limit"
    else:
        label = f"http_{status}"
    return label, combined or label


def obtener_catalogo(api_key: str) -> tuple[list[dict[str, Any]], str]:
    status, body, _ = _request_json(URL_MODELOS, api_key=api_key, timeout=45)
    if status != 200 or not isinstance(body.get("data"), list):
        estado, detalle = _error_state(status, body)
        raise RuntimeError(f"catálogo Token Harbor inaccesible: {estado} — {detalle}")
    rows = [m for m in body["data"] if isinstance(m, dict) and m.get("id")]
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    CATALOGO_CACHE.write_text(
        json.dumps({"generado": datetime.now(timezone.utc).isoformat(), "data": rows}, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return rows, "tokenharbor_api_v1_models_autenticada"


def _content(body: dict[str, Any]) -> str:
    choices = body.get("choices") or []
    if not choices:
        return ""
    message = choices[0].get("message") or {}
    content = message.get("content")
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        return " ".join(str(x.get("text") or "") for x in content if isinstance(x, dict)).strip()
    return ""


def _call(api_key: str, payload: dict[str, Any]) -> tuple[int, dict[str, Any], dict[str, str], int]:
    status = 0
    body: dict[str, Any] = {}
    headers: dict[str, str] = {}
    for intento in range(3):
        status, body, headers = _request_json(URL_CHAT, api_key=api_key, payload=payload, timeout=120)
        if status not in {0, 408, 429, 500, 502, 503, 504} or intento == 2:
            break
        retry = headers.get("retry-after", "")
        try:
            espera = float(retry)
        except (TypeError, ValueError):
            espera = 0.0
        if status == 429 and (espera <= 0 or espera > 20):
            break
        time.sleep(espera if espera > 0 else 1.0 + intento)
    return status, body, headers, intento + 1


def _base_payload(model_id: str) -> dict[str, Any]:
    return {"model": model_id, "temperature": 0, "stream": False}


def _probe_texto(model_id: str, api_key: str) -> dict[str, Any]:
    payload = _base_payload(model_id)
    payload.update({
        "messages": [{"role": "user", "content": "Responde únicamente con la palabra HARBOR."}],
        "max_tokens": 24,
    })
    status, body, _, intentos = _call(api_key, payload)
    if status != 200:
        estado, detalle = _error_state(status, body)
        return {"ok": False, "estado": estado, "detalle": detalle, "status": status, "intentos": intentos}
    text = _content(body)
    return {
        "ok": bool(text),
        "estado": "ok" if text else "respuesta_vacia",
        "detalle": text[:180],
        "status": status,
        "intentos": intentos,
    }


def _probe_herramientas(model_id: str, api_key: str) -> dict[str, Any]:
    payload = _base_payload(model_id)
    payload.update({
        "messages": [{"role": "user", "content": "Llama a sumar_numeros con a=17 y b=25. No respondas con texto."}],
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
        "max_tokens": 160,
    })
    status, body, _, intentos = _call(api_key, payload)
    if status != 200:
        estado, detalle = _error_state(status, body)
        return {"ok": False, "estado": estado, "detalle": detalle, "status": status, "intentos": intentos}
    choices = body.get("choices") or []
    message = (choices[0].get("message") or {}) if choices else {}
    for call in message.get("tool_calls") or []:
        function = call.get("function") or {}
        if function.get("name") != "sumar_numeros":
            continue
        args: Any = function.get("arguments") or {}
        try:
            if isinstance(args, str):
                args = json.loads(args)
        except Exception:
            continue
        if isinstance(args, dict) and args.get("a") == 17 and args.get("b") == 25:
            return {"ok": True, "estado": "ok_forzada", "detalle": "tool_call_exacta", "status": status, "intentos": intentos}
    return {
        "ok": False,
        "estado": "respuesta_sin_tool_call_exacta",
        "detalle": _content(body)[:180],
        "status": status,
        "intentos": intentos,
    }


def _probe_razonamiento(model_id: str, api_key: str) -> dict[str, Any]:
    payload = _base_payload(model_id)
    payload.update({
        "messages": [{
            "role": "user",
            "content": (
                "En una carrera, Lara llegó antes que Inés; Inés antes que Bruno; "
                "Bruno antes que Mateo. ¿Quién llegó segundo? Responde únicamente: INES"
            ),
        }],
        "max_tokens": 32,
    })
    status, body, _, intentos = _call(api_key, payload)
    if status != 200:
        estado, detalle = _error_state(status, body)
        return {"ok": False, "estado": estado, "detalle": detalle, "status": status, "intentos": intentos}
    text = _content(body).upper().replace("Í", "I")
    exacta = text.strip(" .,:;!¡¿?\"'") == "INES"
    return {
        "ok": exacta,
        "estado": "ok_exacta" if exacta else "razonamiento_respuesta_incorrecta",
        "detalle": text[:180],
        "status": status,
        "intentos": intentos,
    }


def _int_value(modelo: dict[str, Any], *keys: str) -> int:
    for key in keys:
        value = modelo.get(key)
        if isinstance(value, dict):
            value = value.get("tokens") or value.get("max")
        try:
            if value is not None:
                return int(value)
        except (TypeError, ValueError):
            continue
    return 0


def _precios_catalogo_cero(modelo: dict[str, Any]) -> bool:
    pricing = modelo.get("pricing") or {}
    input_price = pricing.get("input_usd_per_1m", pricing.get("input"))
    output_price = pricing.get("output_usd_per_1m", pricing.get("output"))
    try:
        return float(input_price) == 0.0 and float(output_price) == 0.0
    except (TypeError, ValueError):
        return False


def _cuentas_tokenharbor() -> list[tuple[str, str]]:
    accounts: list[tuple[str, str]] = []
    seen: set[str] = set()
    for index, account in enumerate(get_tokenharbor_accounts(RAIZ), 1):
        key = str(account.get("api_key") or "").strip()
        if not key.startswith("thk_") or key in seen:
            continue
        account_id = str(account.get("id") or f"tokenharbor_{index}")
        accounts.append((account_id, key))
        seen.add(key)
    if not accounts:
        key = get_tokenharbor_api_key(RAIZ)
        if key and key.startswith("thk_"):
            accounts.append(("clave_global", str(key).strip()))
    return accounts


def _catalogo_capacidades(catalogo: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    result: dict[str, list[dict[str, Any]]] = {}
    merged: dict[str, dict[str, Any]] = {}
    for model in catalogo:
        model_id = str(model.get("id") or "")
        if not model_id:
            continue
        _, secondary, modalities = _descubrir_capacidades(model)
        raw_caps = model.get("capabilities") if isinstance(model.get("capabilities"), dict) else {}
        if raw_caps.get("vision") and "vision_image" not in secondary:
            secondary.append("vision_image")
            modalities.append("image")
        free = str(model.get("id", "")).lower().endswith(":free") and _precios_catalogo_cero(model)
        row = merged.setdefault(model_id, {"capabilities": set(), "modalities": set(), "gratis": False})
        row["capabilities"].update(secondary)
        row["modalities"].update(modalities)
        row["gratis"] = row["gratis"] or free
    for model_id, data in merged.items():
        for capability in sorted(data["capabilities"]):
            result.setdefault(capability, []).append({
                "id": model_id, "modelo": model_id,
                "proveedor": "tokenharbor", "gratis": data["gratis"], "probe_ok": False,
                "implementado": False, "estado_prueba": "solo_catalogo",
                "modalidades": sorted(data["modalities"]),
                "fuente": "catalogo_tokenharbor; capacidad secundaria descubierta, requiere verificación y adaptador",
            })
    for entries in result.values():
        entries.sort(key=lambda row: (not row["gratis"], row["id"]))
    return result


def generar_ranking() -> dict[str, Any]:
    print("═" * 80)
    print("  RANKING TOKEN HARBOR — catálogo :free + pruebas reales por cuenta")
    print("═" * 80)
    cuentas = _cuentas_tokenharbor()
    if not cuentas:
        raise SystemExit("[!] Falta TOKENHARBOR_API_KEY válida; no se aceptan rutas sin prueba real.")

    catalogo_por_id: dict[str, dict[str, Any]] = {}
    all_catalog_rows: list[dict[str, Any]] = []
    fuentes: set[str] = set()
    errores_cuentas = []
    for account_id, key in cuentas:
        try:
            catalog, source = obtener_catalogo(key)
        except RuntimeError as exc:
            errores_cuentas.append({"cuenta": account_id, "estado": str(exc)[:240]})
            continue
        fuentes.add(source)
        all_catalog_rows.extend(catalog)
        for model in catalog:
            model_id = str(model.get("id") or "").strip()
            if not model_id:
                continue
            row = catalogo_por_id.setdefault(model_id, {"modelo": model, "cuentas_free": []})
            if model_id.lower().endswith(":free") and _precios_catalogo_cero(model):
                row["cuentas_free"].append((account_id, key, model))

    if not fuentes:
        raise SystemExit("[!] No se pudo consultar ningún catálogo autenticado de Token Harbor.")
    catalogo = [row["modelo"] for row in catalogo_por_id.values()]
    rutas_free_ids = {mid for mid in catalogo_por_id if mid.lower().endswith(":free")}
    candidatos = {
        mid: row for mid, row in catalogo_por_id.items() if row["cuentas_free"]
    }
    rankings_capacidades = _catalogo_capacidades(all_catalog_rows)
    fuente = "+".join(sorted(fuentes))
    print(
        f"  Cuentas: {len(cuentas)} | catálogos consultados: {len(fuentes)} | "
        f"modelos: {len(catalogo)} | rutas :free: {len(rutas_free_ids)} | "
        f":free con precio cero por cuenta: {len(candidatos)}"
    )

    ranking: list[dict[str, Any]] = []
    for pos, (model_id, model_row) in enumerate(candidatos.items(), 1):
        modelo = model_row["cuentas_free"][0][2]
        elegido_id = ""
        texto = {"ok": False, "estado": "sin_cuenta_probe_ok", "detalle": "", "status": None, "intentos": 0}
        tools = {"ok": False, "estado": "omitida_por_fallo_base", "detalle": "", "status": None, "intentos": 0}
        reasoning = {"ok": False, "estado": "omitida_por_fallo_base", "detalle": "", "status": None, "intentos": 0}
        for account_id, key, account_model in model_row["cuentas_free"]:
            account_text = _probe_texto(model_id, key)
            if not account_text["ok"]:
                texto = account_text
                continue
            account_tools = _probe_herramientas(model_id, key)
            account_reasoning = _probe_razonamiento(model_id, key)
            elegido_id = account_id
            texto, tools, reasoning = account_text, account_tools, account_reasoning
            if account_tools["ok"] and account_reasoning["ok"]:
                modelo = account_model
                break

        raw_caps = modelo.get("capabilities") if isinstance(modelo.get("capabilities"), dict) else {}
        _, secondary, modalities = _descubrir_capacidades(modelo)
        if raw_caps.get("vision") and "vision_image" not in secondary:
            secondary.append("vision_image")
            modalities.append("image")
        caps = {
            "herramientas": bool(tools["ok"]),
            "reasoning": bool(reasoning["ok"]),
            "vision": bool(raw_caps.get("vision") or modelo.get("vision")),
            "audio": bool(raw_caps.get("audio") or modelo.get("audio")),
        }
        contexto = _int_value(modelo, "context_length", "context_window", "max_context_length")
        max_tokens = _int_value(modelo, "max_output_tokens", "max_completion_tokens")
        parametros_b = extraer_parametros(model_id)
        puntaje, desglose, caps_norm = calcular_puntaje_comun(
            caps, contexto=contexto, max_completion_tokens=max_tokens, parametros_b=parametros_b
        )
        apto = bool(texto["ok"] and tools["ok"] and reasoning["ok"])
        ranking.append({
            "id": model_id,
            "modelo": model_id,
            "modelo_base": model_id.removesuffix(":free"),
            "nombre": modelo.get("label") or modelo.get("name") or modelo.get("display_name") or model_id,
            "proveedor": "tokenharbor",
            "cuenta_id": elegido_id,
            "cuentas_compatibles": [elegido_id] if texto["ok"] and elegido_id else [],
            "cuentas_probe_ok": [elegido_id] if apto and elegido_id else [],
            "puntaje": puntaje,
            "apto_agente": apto,
            "parametros_b": parametros_b,
            "contexto": contexto,
            "max_completion_tokens": max_tokens,
            "capacidades": caps,
            "capacidades_norm": caps_norm,
            "capacidades_secundarias": secondary,
            "modalidades": modalities,
            "adaptador_secundario_implementado": bool(raw_caps.get("vision") and texto["ok"]),
            "gratis": True,
            "gratis_evidencia": "id_catalogo_autenticado_termina_en_:free+pricing_input_output=0+probe_cuenta",
            "access_tier": "free",
            "pricing": {"input": 0, "output": 0},
            "list_pricing": modelo.get("pricing") or {},
            "owned_by": modelo.get("owned_by"),
            "temporal_o_limitado": bool(
                modelo.get("limited")
                or modelo.get("campaign")
                or any(
                    marker in " ".join(str(modelo.get(k, "")) for k in ("label", "name", "blurb")).lower()
                    for marker in ("limited", "campaign", "promo")
                )
            ),
            "probe_ok": bool(texto["ok"]),
            "probe_estado": texto["estado"],
            "probe_preview": texto["detalle"],
            "probe_http_status": texto["status"],
            "probe_intentos": texto["intentos"],
            "tool_probe_ok": bool(tools["ok"]),
            "tool_probe_estado": tools["estado"],
            "tool_probe_http_status": tools["status"],
            "tool_probe_intentos": tools["intentos"],
            "reasoning_probe_ok": bool(reasoning["ok"]),
            "reasoning_probe_estado": reasoning["estado"],
            "reasoning_probe_http_status": reasoning["status"],
            "reasoning_probe_intentos": reasoning["intentos"],
            "desglose": " + ".join(desglose) if desglose else "",
            "fuente": fuente,
        })
        for capability, rows in rankings_capacidades.items():
            for row in rows:
                if row["id"] == model_id and texto["ok"]:
                    row["probe_ok"] = True
                    row["estado_prueba"] = "chat_verificado"
                    row["implementado"] = capability == "vision_image" and bool(raw_caps.get("vision"))
        etiqueta = "APTO" if apto else "SECUNDARIO" if texto["ok"] else "RECHAZADO"
        estado = texto["estado"] if not texto["ok"] else f"tools={tools['estado']}, reasoning={reasoning['estado']}"
        print(f"  [{pos:>2}/{len(candidatos)}] {etiqueta:10s} {model_id} ({estado})", flush=True)

    ranking.sort(key=clave_orden_modelo, reverse=True)
    for pos, row in enumerate(ranking, 1):
        row["posicion"] = pos

    resultado = {
        "generado": datetime.now(timezone.utc).isoformat(),
        "service": "tokenharbor",
        "fuente_catalogo": fuente,
        "total_catalogo": len(catalogo),
        "cuentas_catalogo_ok": len(cuentas) - len(errores_cuentas),
        "errores_cuentas": errores_cuentas,
        "total_rutas_free_catalogo": len(rutas_free_ids),
        "rutas_free_excluidas_por_precio": sorted(rutas_free_ids - set(candidatos)),
        "total_modelos": len(ranking),
        "total_modelos_respondieron": sum(bool(r["probe_ok"]) for r in ranking),
        "total_aptos_finales": sum(bool(r["apto_agente"]) for r in ranking),
        "ranking": ranking,
        "ranking_final": [r for r in ranking if r["apto_agente"]],
        "ranking_secundario": [r for r in ranking if r["probe_ok"] and not r["apto_agente"]],
        "ranking_rechazados_probe": [r for r in ranking if not r["probe_ok"]],
        "rankings_capacidades": rankings_capacidades,
        "ficha_comun": {
            "filtro": ["id=:free", "pricing.input=0", "pricing.output=0", "catalogo_autenticado_actual", "probe_ok", "tool_probe_ok", "reasoning_probe_ok"],
            "nota": "Las rutas de pago nunca se prueban. Las temporales o no elegibles se descartan al dejar de responder.",
            "privacidad": "Las rutas free pueden retener prompts y respuestas según la política de Token Harbor.",
        },
    }
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    temporal = SALIDA.with_name(f"{SALIDA.name}.tmp.{os.getpid()}")
    try:
        temporal.write_text(json.dumps(resultado, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        os.replace(temporal, SALIDA)
    finally:
        if temporal.exists():
            temporal.unlink()
    print(
        f"\n[+] Token Harbor: {resultado['total_modelos_respondieron']}/{len(ranking)} respondieron; "
        f"{resultado['total_aptos_finales']} principales; {len(resultado['ranking_secundario'])} secundarios; "
        f"{len(resultado['ranking_rechazados_probe'])} rechazados."
    )
    print(f"Guardado en: {SALIDA}")
    return resultado


if __name__ == "__main__":
    generar_ranking()
