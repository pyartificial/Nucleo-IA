"""Construye un ranking verificado desde la API /models compatible con OpenAI."""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

sys.path.insert(0, os.path.dirname(__file__))
from ranking_common import calcular_puntaje_comun, clave_orden_modelo, cumple_minimos
from ranking_quality import probar_herramienta_openai
from secret_utils import _norm_env_suffix, _parse_env_file, _is_placeholder_secret

ROOT = Path(__file__).resolve().parent.parent
CONFIG = {
    "cerebras": ("CEREBRAS_API_KEY", "https://api.cerebras.ai/v1"),
    "mistral": ("MISTRAL_API_KEY", "https://api.mistral.ai/v1"),
    "deepseek": ("DEEPSEEK_API_KEY", "https://api.deepseek.com"),
    "grok": ("XAI_API_KEY", "https://api.x.ai/v1"),
    "minimax": ("MINIMAX_API_KEY", "https://api.minimax.io/v1"),
    "alibaba": ("DASHSCOPE_API_KEY", "https://dashscope-intl.aliyuncs.com/compatible-mode/v1"),
}


def _keys(provider: str) -> list[str]:
    env_name, _ = CONFIG[provider]
    env = dict(os.environ)
    for filename in (".env", "granja.env"):
        env.update(_parse_env_file(ROOT / filename))
    try:
        accounts = json.loads((ROOT / "cuentas.json").read_text(encoding="utf-8")).get("proveedores", {}).get(provider, {}).get("cuentas", [])
    except (OSError, ValueError):
        accounts = []
    keys = []
    for idx, account in enumerate(accounts, 1):
        if account.get('habilitado') is False:
            continue
        account_id = _norm_env_suffix(account.get("id", ""))
        for name in (f"{env_name}_{account_id}", f"{env_name}_{idx}"):
            key = env.get(name)
            if not _is_placeholder_secret(key) and key not in keys:
                keys.append(key.strip())
                break
    global_key = env.get(env_name)
    if not _is_placeholder_secret(global_key) and global_key not in keys:
        keys.append(env[env_name].strip())
    return keys


def _get_json(url: str, key: str) -> dict:
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {key}", "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=20) as response:
        return json.loads(response.read().decode("utf-8"))


def _probe(url: str, key: str, model: str) -> bool:
    payload = json.dumps({"model": model, "messages": [{"role": "user", "content": "ping"}], "max_tokens": 1}).encode()
    req = urllib.request.Request(url + "/chat/completions", data=payload, headers={
        "Authorization": f"Bearer {key}", "Content-Type": "application/json", "Accept": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=20) as response:
            return response.status == 200
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError):
        return False


def generar(provider: str) -> dict:
    env_name, base_url = CONFIG[provider]
    api_keys = _keys(provider)
    models = {}
    for key in api_keys:
        try:
            for item in _get_json(base_url + "/models", key).get("data", []):
                model_id = str(item.get("id", "")).strip()
                if model_id:
                    models.setdefault(model_id, key)
        except Exception as exc:
            print(f"No se pudo leer el catálogo de {provider}: {exc}", file=sys.stderr)
    ranking = []
    for model_id, key in models.items():
        low = model_id.lower()
        excluded = ("embed", "moderation", "whisper", "tts", "audio", "guard")
        if any(tag in low for tag in excluded):
            continue
        # /models does not advertise consistent capability metadata; only claim
        # text chat and never infer vision/tools/reasoning from model names.
        caps = {"herramientas": False, "reasoning": False, "vision": False}
        score, breakdown, caps_norm = calcular_puntaje_comun(caps)
        probe_ok = _probe(base_url, key, model_id)
        row = {
            "id": model_id, "modelo": model_id, "modelo_base": model_id, "nombre": model_id,
            "proveedor": provider, "puntaje": score, "apto_agente": cumple_minimos(caps_norm, probe_ok),
            "parametros_b": 0, "contexto": 0, "max_completion_tokens": 0,
            "capacidades": caps, "capacidades_norm": caps_norm, "gratis": False,
            "probe_ok": probe_ok, "probe_estado": "ok" if probe_ok else "fallo_probe",
            "tool_probe_ok": None, "tool_probe_estado": "no_ejecutada",
            "desglose": " + ".join(breakdown), "fuente": "api_models_autenticada",
        }
        if probe_ok:
            try:
                row["tool_probe_ok"], row["tool_probe_estado"] = probar_herramienta_openai(base_url + "/chat/completions", key, model_id, timeout=20)
                if row["tool_probe_ok"]:
                    row["capacidades"]["herramientas"] = True
                    row["capacidades_norm"]["herramientas"] = True
            except Exception:
                pass
        ranking.append(row)
    ranking.sort(key=clave_orden_modelo, reverse=True)
    for i, row in enumerate(ranking, 1):
        row["posicion"] = i
    result = {"generado": datetime.now().isoformat(), "service": provider,
              "total_modelos": len(ranking), "total_aptos_finales": sum(bool(x["apto_agente"]) for x in ranking),
              "ranking": ranking, "ranking_final": [x for x in ranking if x["apto_agente"]]}
    state = ROOT / "state"
    state.mkdir(exist_ok=True)
    (state / f"ranking_{provider}.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return result


if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] not in CONFIG:
        raise SystemExit("Uso: ranking_openai_compatible.py cerebras|mistral|deepseek|grok|minimax|alibaba")
    data = generar(sys.argv[1])
    print(f"{data['service']}: {data['total_modelos']} modelos descubiertos; {data['total_aptos_finales']} aptos para agentes")
