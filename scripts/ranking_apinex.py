#!/usr/bin/env python3
"""Descubre APInex y prueba solo rutas explícitamente gratuitas."""
from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ranking_common import calcular_puntaje_comun, clave_orden_modelo, extraer_parametros
from secret_utils import load_local_env

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / "state"
OUT = STATE / "ranking_apinex.json"
BASE = "https://api.apinex.bond/v1"


def _keys() -> list[str]:
    load_local_env(ROOT)
    try:
        data = json.loads((ROOT / "cuentas.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        data = {}
    keys: list[str] = []
    accounts = data.get("proveedores", {}).get("apinex", {}).get("cuentas", [])
    for index, account in enumerate(accounts, 1):
        ident = re.sub(r"[^A-Za-z0-9]+", "_", str(account.get("id", "")).upper()).strip("_")
        for name in (f"APINEX_API_KEY_{ident}", "APINEX_API_KEY" if index == 1 else ""):
            value = os.getenv(name, "").strip() if name else ""
            if value and value not in keys:
                keys.append(value)
            if value:
                break
    if not keys and os.getenv("APINEX_API_KEY", "").strip():
        keys.append(os.environ["APINEX_API_KEY"].strip())
    return keys


def call(url: str, key: str, payload: dict | None = None) -> tuple[int, dict]:
    headers = {"Authorization": f"Bearer {key}", "Accept": "application/json", "User-Agent": "Nucleo-IA-Ranking/1.0"}
    body = None
    if payload is not None:
        headers["Content-Type"] = "application/json"
        body = json.dumps(payload).encode()
    request = urllib.request.Request(url, data=body, headers=headers, method="POST" if body else "GET")
    try:
        with urllib.request.urlopen(request, timeout=45) as response:
            data = json.loads(response.read())
            return response.status, data if isinstance(data, dict) else {}
    except urllib.error.HTTPError as error:
        try:
            data = json.loads(error.read().decode("utf-8", "replace"))
            return error.code, data if isinstance(data, dict) else {}
        except (ValueError, OSError):
            return error.code, {}
    except (urllib.error.URLError, TimeoutError, OSError, ValueError):
        return 0, {}


def _text(body: dict) -> str:
    message = (body.get("choices") or [{}])[0].get("message") or {}
    value = message.get("content", "")
    return value if isinstance(value, str) else ""


def _free_evidence(model: dict) -> str | None:
    """Do not infer zero cost from an ID prefix alone."""
    if model.get("is_free") is True or model.get("free") is True:
        return "catalogo:is_free"
    pricing = model.get("pricing")
    if not isinstance(pricing, dict):
        return None
    def zero(*names: str) -> bool:
        for name in names:
            if name not in pricing:
                continue
            try:
                return float(pricing[name]) == 0
            except (TypeError, ValueError):
                return False
        return False
    if zero("input", "prompt", "input_price", "inputPrice") and zero("output", "completion", "output_price", "outputPrice"):
        return "catalogo:precio_entrada_y_salida_cero"
    return None


def _probe_tools(model_id: str, key: str) -> bool:
    payload = {
        "model": model_id,
        "messages": [{"role": "user", "content": "Llama a sumar con a=17 y b=25. No respondas con texto."}],
        "tools": [{"type": "function", "function": {"name": "sumar", "parameters": {"type": "object", "properties": {"a": {"type": "integer"}, "b": {"type": "integer"}}, "required": ["a", "b"]}}}],
        "tool_choice": "auto", "max_tokens": 80, "temperature": 0,
    }
    status, body = call(f"{BASE}/chat/completions", key, payload)
    if status != 200:
        return False
    message = (body.get("choices") or [{}])[0].get("message") or {}
    for tool_call in message.get("tool_calls") or []:
        function = tool_call.get("function") or {}
        if function.get("name") != "sumar":
            continue
        arguments = function.get("arguments") or {}
        if isinstance(arguments, str):
            try:
                arguments = json.loads(arguments)
            except ValueError:
                return False
        return isinstance(arguments, dict) and arguments.get("a") == 17 and arguments.get("b") == 25
    return False


def _probe_reasoning(model_id: str, key: str) -> bool:
    payload = {"model": model_id, "messages": [{"role": "user", "content": "Lara llegó antes que Inés, e Inés antes que Bruno. ¿Quién llegó segundo? Responde únicamente INES"}], "max_tokens": 20, "temperature": 0}
    status, body = call(f"{BASE}/chat/completions", key, payload)
    return status == 200 and _text(body).upper().strip(" .,!¡¿?") == "INES"


def main() -> dict:
    keys = _keys()
    if not keys:
        raise SystemExit("Falta APINEX_API_KEY")
    status, catalog = call(f"{BASE}/models", keys[0])
    if status != 200 or not isinstance(catalog.get("data"), list):
        raise SystemExit(f"Catálogo APInex inaccesible (HTTP {status})")

    rows = []
    for model in catalog["data"]:
        model_id = str(model.get("id", "")).strip()
        if not model_id:
            continue
        evidence = _free_evidence(model)
        if not evidence:
            rows.append({"id": model_id, "modelo": model_id, "modelo_base": model_id, "nombre": model.get("name") or model_id,
                         "proveedor": "apinex", "puntaje": 0, "parametros_b": extraer_parametros(model_id), "contexto": 0,
                         "max_completion_tokens": 0, "capacidades": {}, "capacidades_norm": {}, "probe_ok": False,
                         "probe_estado": "sin_evidencia_precio_cero", "tool_probe_ok": False, "reasoning_probe_ok": False,
                         "apto_agente": False, "gratis": False, "pricing": model.get("pricing") or {},
                         "fuente": "apinex_v1_models_autenticada"})
            continue

        # IDs free/ are corroborating data, never sufficient evidence alone.
        # These probes run only after explicit zero-cost metadata was returned.
        key = keys[0]
        status_chat, response = call(f"{BASE}/chat/completions", key, {
            "model": model_id, "messages": [{"role": "user", "content": "Responde únicamente APINEX"}],
            "max_tokens": 16, "temperature": 0,
        })
        chat_ok = status_chat == 200 and bool(_text(response).strip())
        tools_ok = _probe_tools(model_id, key) if chat_ok else False
        reasoning_ok = _probe_reasoning(model_id, key) if chat_ok else False
        caps = {"herramientas": tools_ok, "reasoning": reasoning_ok,
                "vision": bool(model.get("vision") or (model.get("capabilities") or {}).get("vision"))}
        context = int(model.get("context_length") or model.get("context_window") or 0)
        max_output = int(model.get("max_output_tokens") or model.get("max_completion_tokens") or 0)
        score, detail, normalized = calcular_puntaje_comun(caps, context, max_output, extraer_parametros(model_id))
        error = response.get("error") if isinstance(response, dict) else {}
        error_text = error.get("message", "") if isinstance(error, dict) else str(error or "")
        eligible = bool(chat_ok and tools_ok and reasoning_ok)
        rows.append({"id": model_id, "modelo": model_id, "modelo_base": model_id, "nombre": model.get("name") or model_id,
                     "proveedor": "apinex", "puntaje": score, "desglose": detail, "parametros_b": extraer_parametros(model_id),
                     "contexto": context, "max_completion_tokens": max_output, "capacidades": caps,
                     "capacidades_norm": normalized, "probe_ok": chat_ok,
                     "probe_estado": f"http_{status_chat}" if not chat_ok else "ok", "probe_preview": (_text(response) or error_text)[:240],
                     "tool_probe_ok": tools_ok, "reasoning_probe_ok": reasoning_ok, "apto_agente": eligible,
                     "gratis": True, "gratis_evidencia": evidence, "pricing": model.get("pricing") or {},
                     "fuente": "apinex_v1_models_autenticada"})

    rows.sort(key=clave_orden_modelo, reverse=True)
    for position, row in enumerate(rows, 1):
        row["posicion"] = position
    result = {"generado": datetime.now(timezone.utc).isoformat(), "service": "apinex", "total_claves_utilizadas": 1,
              "total_catalogo": len(catalog["data"]), "total_modelos": len(rows),
              "total_modelos_respondieron": sum(bool(row["probe_ok"]) for row in rows),
              "total_aptos_finales": sum(bool(row["apto_agente"]) for row in rows), "ranking": rows,
              "ranking_final": [row for row in rows if row["apto_agente"]],
              "ranking_secundario": [row for row in rows if row["probe_ok"] and not row["apto_agente"]],
              "ranking_rechazados_probe": [row for row in rows if not row["probe_ok"]],
              "ficha_comun": {"filtro": ["precio_entrada_cero", "precio_salida_cero", "probe_ok", "tool_probe_ok", "reasoning_probe_ok"],
                              "nota": "El prefijo free/ no demuestra por sí solo costo cero. Las solicitudes de prueba solo se envían cuando el catálogo autenticado declara gratuidad explícita."}}
    STATE.mkdir(exist_ok=True)
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"modelos": len(rows), "respondieron": result["total_modelos_respondieron"], "aptos": result["total_aptos_finales"]}, ensure_ascii=False))
    return result


if __name__ == "__main__":
    main()
