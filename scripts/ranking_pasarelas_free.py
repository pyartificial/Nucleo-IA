#!/usr/bin/env python3
"""Descubre catálogos OpenAI-compatible y admite solo rutas free verificables.

Los rankings se guardan por proveedor. El catálogo conserva también capacidades
secundarias aunque Núcleo IA todavía no tenga un adaptador de tarea para ellas.
"""
from __future__ import annotations

import json
import math
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ranking_common import calcular_puntaje_comun, clave_orden_modelo, cumple_minimos, extraer_parametros
from secret_utils import _norm_env_suffix, _parse_env_file, _is_placeholder_secret

ROOT = Path(__file__).resolve().parent.parent
CONFIG = {
    "agnes": ("AGNES_API_KEY", "https://apihub.agnes-ai.com/v1", "pricing"),
    "aion": ("AION_API_KEY", "https://api.aionlabs.ai/v1", "pricing"),
    "airforce": ("AIRFORCE_API_KEY", "https://api.airforce/v1", "pricing"),
    "anyapi": ("ANYAPI_API_KEY", "https://api.anyapi.ai/v1", "pricing"),
    "bazaarlink": ("BAZAARLINK_API_KEY", "https://api.bazaarlink.ai/v1", "pricing"),
    "dreamprompting": ("DREAMPROMPTING_API_KEY", "https://dreamprompting.com/api/v1", "pricing"),
    "huggingface": ("HF_TOKEN", "https://router.huggingface.co/v1", "pricing"),
    "orcarouter": ("ORCAROUTER_API_KEY", "https://api.orcarouter.ai/v1", "orcarouter"),
    "requesty": ("REQUESTY_API_KEY", "https://router.requesty.ai/v1", "pricing"),
    "routeway": ("ROUTEWAY_API_KEY", "https://api.routeway.ai/v1", "pricing"),
    "sealion": ("SEALION_API_KEY", "https://api.sea-lion.ai/v1", "pricing"),
    "unorouter": ("UNOROUTER_API_KEY", "https://api.unorouter.com/v1", "pricing"),
    "ollama_cloud_api": ("OLLAMA_API_KEY", "https://ollama.com/v1", "pricing"),
    "mistral": ("MISTRAL_API_KEY", "https://api.mistral.ai/v1", "pricing"),
}


def _keys(provider: str) -> list[tuple[str, str]]:
    env_name, _, _ = CONFIG[provider]
    env = dict(os.environ)
    for filename in (".env", "granja.env"):
        env.update(_parse_env_file(ROOT / filename))
    try:
        raw = json.loads((ROOT / "cuentas.json").read_text(encoding="utf-8"))
        accounts = raw.get("proveedores", {}).get(provider, {}).get("cuentas", [])
    except (OSError, ValueError, AttributeError):
        accounts = []
    result: list[tuple[str, str]] = []
    for idx, account in enumerate(accounts, 1):
        if account.get("habilitado") is False:
            continue
        aid = _norm_env_suffix(account.get("id", ""))
        for name in (f"{env_name}_{aid}", f"{env_name}_{idx}"):
            key = env.get(name)
            if not _is_placeholder_secret(key) and key:
                key = key.strip()
                if all(key != old for _, old in result):
                    result.append((str(account.get("id", f"cuenta_{idx}")), key))
                break
    global_key = env.get(env_name)
    if not _is_placeholder_secret(global_key) and global_key:
        global_key = global_key.strip()
        if all(global_key != old for _, old in result):
            result.append(("clave_global", global_key))
    return result


def _catalog_url(provider: str, base: str) -> str:
    path = "/models"
    if provider == "airforce":
        return base + path + "?channels=1"
    if provider == "bazaarlink":
        return base + path + "?output_modalities=all"
    return base + path


def _get_json(url: str, key: str) -> tuple[int, dict]:
    req = urllib.request.Request(url, headers={
        "Authorization": f"Bearer {key}", "Accept": "application/json",
        "User-Agent": "NucleoIA-Ranking/1.0",
    })
    try:
        with urllib.request.urlopen(req, timeout=25) as response:
            data = json.loads(response.read().decode("utf-8"))
            return response.status, data if isinstance(data, dict) else {}
    except urllib.error.HTTPError as exc:
        return exc.code, {}
    except (urllib.error.URLError, TimeoutError, OSError, ValueError):
        return 0, {}


def _list_items(data: dict) -> list[dict]:
    for field in ("data", "models", "results"):
        value = data.get(field)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
    return []


def _zero(value) -> bool:
    try:
        number = float(str(value).strip())
        return math.isfinite(number) and number == 0
    except (TypeError, ValueError):
        return False


def _as_int(*values) -> int:
    for value in values:
        if value is None or value == "":
            continue
        try:
            return max(0, int(float(value)))
        except (TypeError, ValueError, OverflowError):
            continue
    return 0


def _price_proves_zero(item: dict) -> bool:
    """A true free signal needs both input and output prices (unless is_free)."""
    for container_name in ("pricing", "price", "cost"):
        pricing = item.get(container_name)
        if not isinstance(pricing, dict):
            continue
        input_value = next((pricing[k] for k in ("input", "prompt", "input_price", "inputPrice", "input_cost") if k in pricing), None)
        output_value = next((pricing[k] for k in ("output", "completion", "output_price", "outputPrice", "output_cost") if k in pricing), None)
        if input_value is not None and output_value is not None and _zero(input_value) and _zero(output_value):
            return True
    input_value = next((item[k] for k in ("pricepermilliontokens", "input_price", "inputPrice") if k in item), None)
    output_value = next((item[k] for k in ("output_pricepermilliontokens", "output_price", "outputPrice") if k in item), None)
    return input_value is not None and output_value is not None and _zero(input_value) and _zero(output_value)


def _free(item: dict, provider: str, policy: str) -> tuple[bool, str]:
    mid = str(item.get("id") or item.get("name") or "").strip()
    if provider == "orcarouter" and mid.casefold() == "orcarouter/free":
        return True, "alias orcarouter/free declarado gratuito por OrcaRouter"
    tier = str(item.get("tier") or item.get("access_tier") or item.get("pricing_tier") or "").casefold()
    if item.get("is_free") is True or item.get("free") is True or tier == "free":
        return True, "catálogo del proveedor declara el modelo gratuito"
    if _price_proves_zero(item):
        return True, "precio de entrada y salida igual a cero en catálogo"
    if re.search(r"(?i)(?:[:/-]free|\(free\))$", mid):
        return True, "ID de variante gratuita publicado por el proveedor"
    return False, "sin evidencia explícita de costo cero"


def _provider_rows(item: dict, provider: str) -> list[tuple[dict, str]]:
    """Hugging Face publishes prices and capabilities separately per route."""
    routes = item.get("providers")
    if provider != "huggingface" or not isinstance(routes, list) or not routes:
        return [(item, str(item.get("id") or item.get("name") or ""))]
    rows = []
    base_id = str(item.get("id") or "")
    for route in routes:
        if not isinstance(route, dict) or str(route.get("status", "live")).casefold() != "live":
            continue
        route_id = str(route.get("provider") or "").strip()
        if not route_id:
            continue
        merged = dict(item)
        merged.update(route)
        merged["id"] = f"{base_id}:{route_id}"
        rows.append((merged, merged["id"]))
    return rows


def _es_chat(item: dict, model_id: str, caps: dict) -> bool:
    if item.get("supports_chat") is False:
        return False
    task = str(item.get("task") or item.get("pipeline_tag") or "").casefold().replace("-", "_")
    if task in {"embeddings", "feature_extraction", "text_embedding", "rerank", "reranking", "text_to_speech", "text_to_audio", "automatic_speech_recognition", "speech_to_text", "image_generation", "text_to_image", "text_to_video", "video_generation", "moderation"}:
        return False
    if item.get("supports_chat") is True:
        return True
    # Several OpenAI-compatible /models endpoints expose only an ID and omit
    # task/capability metadata. Keep plausible candidates for a real chat probe;
    # explicit non-chat tasks and recognizable non-chat IDs remain excluded.
    if any(marker in model_id.casefold() for marker in ("embed", "whisper", "tts", "moderation", "rerank", "text-to-image", "text-to-video", "stable-diffusion")):
        return False
    input_mod, _ = _modalities(item)
    if input_mod and not ({"text", "image", "audio", "video", "document"} & input_mod):
        return False
    _, output_mod = _modalities(item)
    if output_mod and not ({"text"} & output_mod) and not input_mod:
        return False
    return True


def _modalities(item: dict) -> tuple[set[str], set[str]]:
    architecture = item.get("architecture") if isinstance(item.get("architecture"), dict) else {}
    input_mod = architecture.get("input_modalities", item.get("input_modalities", item.get("inputModalities", [])))
    output_mod = architecture.get("output_modalities", item.get("output_modalities", item.get("outputModalities", [])))
    if isinstance(input_mod, str): input_mod = [input_mod]
    if isinstance(output_mod, str): output_mod = [output_mod]
    return ({str(x).casefold() for x in input_mod or []}, {str(x).casefold() for x in output_mod or []})


def _capabilities(item: dict) -> tuple[dict, list[str], list[str]]:
    flags = item.get("capabilities") if isinstance(item.get("capabilities"), dict) else {}
    input_mod, output_mod = _modalities(item)
    features = item.get("features", [])
    if isinstance(features, str): features = [features]
    features = {str(x).casefold().replace("-", "_") for x in features or []}
    api_formats = item.get("api_formats") or item.get("apiFormats") or []
    if isinstance(api_formats, str): api_formats = [api_formats]
    formats = {str(x).casefold().replace("-", "_").replace(" ", "_") for x in api_formats or []}
    task_fields = (
        item.get("task"), item.get("pipeline_tag"), item.get("task_type"), item.get("type"),
        item.get("input_task"), item.get("output_task"),
    )
    task = " ".join(str(value) for value in task_fields if value).casefold().replace("-", "_").replace(" ", "_")
    signals = " ".join([task, *sorted(features), *sorted(formats), *(
        str(name).casefold().replace("-", "_") for name, value in flags.items() if value is True
    )])
    def has(*terms: str) -> bool:
        return any(term in signals for term in terms)

    # API format metadata often describes a task without listing modalities.
    if has("image_generation", "text_to_image", "image_editing"):
        output_mod.add("image")
    if has("video_generation", "text_to_video", "image_to_video", "video_editing"):
        output_mod.add("video")
    if has("text_to_speech", "speech_generation", "voice_design", "voice_cloning", "sound_effect", "music_generation", "music_editing", "dubbing", "speech_to_speech"):
        output_mod.add("audio")
    if has("transcription", "speech_to_text", "audio_to_text", "speech_recognition", "audio_isolation", "forced_alignment", "speech_to_speech"):
        input_mod.add("audio")

    vision = bool(
        item.get("supports_vision") or flags.get("vision") or {"image", "video"} & input_mod
        or has("vision_image", "image_understanding", "image_question_answering", "image_to_text", "image_captioning", "vision_video", "video_understanding", "video_question_answering", "video_to_text", "video_captioning")
    )
    tools = bool(item.get("supports_tools") or item.get("tool_calling") or flags.get("tools") or "tools" in features or "function_calling" in features)
    reasoning = bool(item.get("supports_reasoning") or item.get("reasoning") or flags.get("reasoning") or "reasoning" in features)
    caps = {"herramientas": tools, "reasoning": reasoning, "vision": vision, "audio": bool({"audio"} & (input_mod | output_mod))}
    discovered: set[str] = set()
    all_mod = input_mod | output_mod
    if "image" in input_mod or has("vision_image", "image_understanding", "image_question_answering", "image_to_text", "image_captioning"):
        discovered.add("vision_image")
    if "video" in input_mod or has("vision_video", "video_understanding", "video_question_answering", "video_to_text", "video_captioning"):
        discovered.add("vision_video")
    if "audio" in input_mod and has("audio_to_text", "transcription", "speech_recognition", "automatic_speech_recognition", "speech_to_text", "asr"):
        discovered.add("transcription_audio")
    if "audio" in input_mod and has("realtime", "real_time", "live") and has("transcription", "speech_to_text", "speech_recognition", "asr"):
        discovered.add("transcription_realtime")
    if has("speech_to_speech", "audio_to_audio", "voice_conversion"):
        discovered.add("speech_to_speech")
    if "speech" in output_mod or has("text_to_speech", "text_to_audio", "speech_generation", "voice_design", "voice_cloning"):
        discovered.add("speech_generation")
    if has("voice_cloning", "voice_clone"):
        discovered.add("voice_cloning")
    if has("voice_design", "voice_creation", "custom_voice"):
        discovered.add("voice_design")
    if has("audio_isolation", "voice_isolation", "vocal_isolation", "source_separation"):
        discovered.add("audio_isolation")
    if has("text_to_sound", "sound_effect", "sound_generation", "audio_effect"):
        discovered.add("sound_effects")
    if has("dubbing", "dub_video", "voice_dubbing"):
        discovered.add("dubbing")
    if has("forced_alignment", "forced_align", "text_alignment", "audio_alignment"):
        discovered.add("forced_alignment")
    if "image" in output_mod or has("text_to_image", "image_generation", "image_editing"):
        discovered.add("image_editing" if has("image_editing", "image_inpainting", "image_edit") else "image_generation")
    if "video" in output_mod or has("text_to_video", "image_to_video", "video_generation", "video_editing"):
        if has("video_editing", "video_edit"):
            discovered.add("video_editing")
        elif "image" in input_mod or has("image_to_video", "video_generation_image"):
            discovered.add("video_generation_image")
        else:
            discovered.add("video_generation_text")
    if "embedding" in all_mod or "embeddings" in all_mod or has("embedding", "feature_extraction"):
        discovered.add("embeddings")
    if "rerank" in all_mod or has("rerank"):
        discovered.add("reranking")
    if "document" in input_mod or has("document_question_answering", "document_qa", "document_parsing", "parse_document", "document_extraction"):
        discovered.add("parse_documents")
    if item.get("supports_documents") is True or flags.get("documents") is True:
        discovered.add("parse_documents")
    if has("music"):
        discovered.add("music_editing" if has("music_edit", "music_inpainting") else "music_generation")
    if has("lip_sync", "lipsync", "avatar_video"):
        discovered.add("lip_sync")
    if has("voice_agent", "voice_assistant", "conversational_voice"):
        discovered.add("voice_agents")
    return caps, sorted(discovered), sorted(input_mod | output_mod)


def _probe(url: str, key: str, model: str, provider: str) -> bool:
    payload = {"model": model, "messages": [{"role": "user", "content": "Respondé solo: OK"}], "max_tokens": 1}
    if provider == "dreamprompting": payload["allow_fallback"] = False
    body = json.dumps(payload).encode()
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json", "Accept": "application/json", "User-Agent": "NucleoIA-Ranking/1.0"}
    if provider == "bazaarlink": headers["X-Free-Fallback"] = "false"
    req = urllib.request.Request(url + "/chat/completions", data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=25) as response:
            return response.status == 200
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError):
        return False


def _probe_tools(url: str, key: str, model: str, provider: str) -> tuple[bool, str]:
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json", "Accept": "application/json", "User-Agent": "NucleoIA-Ranking/1.0"}
    if provider == "bazaarlink": headers["X-Free-Fallback"] = "false"
    choices = ["required", "auto", {"type": "function", "function": {"name": "sumar_numeros"}}]
    estados = []
    for choice in choices:
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": "Llama a sumar_numeros con a=17 y b=25. No calcules ni respondas con texto."}],
            "tools": [{"type": "function", "function": {"name": "sumar_numeros", "description": "Suma dos enteros", "parameters": {"type": "object", "properties": {"a": {"type": "integer"}, "b": {"type": "integer"}}, "required": ["a", "b"]}}}],
            "tool_choice": choice, "temperature": 0, "max_tokens": 128, "stream": False,
        }
        if provider == "dreamprompting": payload["allow_fallback"] = False
        req = urllib.request.Request(url + "/chat/completions", data=json.dumps(payload).encode(), headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=35) as response:
                data = json.loads(response.read().decode("utf-8", "replace"))
            actual_model = str(data.get("model") or model)
            dynamic_route = (provider == "orcarouter" and model == "orcarouter/free") or (provider == "bazaarlink" and model == "auto:free")
            if actual_model != model and not dynamic_route:
                estados.append("modelo_sustituido")
                continue
            message = ((data.get("choices") or [{}])[0].get("message") or {})
            for call in message.get("tool_calls") or []:
                function = call.get("function") or {}
                if function.get("name") != "sumar_numeros": continue
                args = function.get("arguments") or {}
                if isinstance(args, str): args = json.loads(args)
                if isinstance(args, dict) and args.get("a") == 17 and args.get("b") == 25:
                    return True, "ok_tool_call_exacta"
            estados.append("sin_tool_call_exacta")
        except urllib.error.HTTPError as exc:
            estados.append(f"http_{exc.code}")
        except (urllib.error.URLError, TimeoutError, OSError, ValueError, TypeError, IndexError):
            estados.append("respuesta_invalida")
    return False, "/".join(estados)


def _probe_reasoning(url: str, key: str, model: str, provider: str) -> bool:
    body = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": "En una carrera, Lara llegó antes que Inés; Inés antes que Bruno; Bruno antes que Mateo. ¿Quién llegó segunda? Responde únicamente: INES"}],
        "max_tokens": 24,
        "temperature": 0,
    }).encode()
    if provider == "dreamprompting":
        payload = json.loads(body)
        payload["allow_fallback"] = False
        body = json.dumps(payload).encode()
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json", "Accept": "application/json", "User-Agent": "NucleoIA-Ranking/1.0"}
    if provider == "bazaarlink": headers["X-Free-Fallback"] = "false"
    req = urllib.request.Request(url + "/chat/completions", data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            data = json.loads(response.read().decode("utf-8", "replace"))
        choices = data.get("choices") or []
        text = str(((choices[0].get("message") or {}).get("content") or "")).upper().replace("Í", "I").strip(" .,:;!¡¿?\"'") if choices else ""
        return text == "INES"
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError, ValueError, TypeError, IndexError):
        return False


def generar(provider: str) -> dict:
    env_name, base_url, policy = CONFIG[provider]
    keys = _keys(provider)
    rows: dict[str, tuple[dict, list[tuple[str, str]]]] = {}
    errores = []
    catalog_url = _catalog_url(provider, base_url)
    for account_id, key in keys:
        status, data = _get_json(catalog_url, key)
        if status != 200:
            errores.append({"cuenta": account_id, "estado": f"http_{status}" if status else "sin_conexion"})
            continue
        for original in _list_items(data):
            for item, route_model_id in _provider_rows(original, provider):
                model_id = str(route_model_id or "").strip()
                if not model_id:
                    continue
                if model_id not in rows:
                    rows[model_id] = (item, [])
                if all(existing_key != key for existing_key, _ in rows[model_id][1]):
                    rows[model_id][1].append((key, account_id))

    if provider == "orcarouter" and keys and "orcarouter/free" not in rows:
        # OrcaRouter documents this stable, free, difficulty-routed alias even
        # when a key-filtered /models response omits the virtual model.
        rows["orcarouter/free"] = ({"id": "orcarouter/free", "supports_chat": True}, [(key, account_id) for account_id, key in keys])

    ranking = []
    capability_catalog: dict[str, list[dict]] = {}
    accounts_chat_ok: set[str] = set()
    for model_id, (item, model_keys) in rows.items():
        is_free, evidence = _free(item, provider, policy)
        caps, secondary, modalities = _capabilities(item)
        has_chat = _es_chat(item, model_id, caps)
        price = item.get("pricing") if isinstance(item.get("pricing"), dict) else {}
        context = _as_int(item.get("context_length"), item.get("context_window"), item.get("context"))
        max_output = _as_int(item.get("max_completion_tokens"), item.get("max_output_tokens"), item.get("max_tokens"))
        params = extraer_parametros(model_id)
        score, breakdown, caps_norm = calcular_puntaje_comun(caps, context, max_output, params)
        selected_key = model_keys[0][0] if model_keys else ""
        selected_account = model_keys[0][1] if model_keys else ""
        probe_ok = False
        tool_probe_ok: bool | None = None
        tool_probe_estado = "no_gratis" if not is_free else ("no_chat" if not has_chat else "no_ejecutada")
        reasoning_probe_ok: bool | None = None
        if is_free and has_chat:
            for key, account_id in model_keys:
                if not _probe(base_url, key, model_id, provider):
                    continue
                probe_ok = True
                selected_key, selected_account = key, account_id
                accounts_chat_ok.add(account_id)
                tool_probe_ok, tool_probe_estado = _probe_tools(base_url, key, model_id, provider)
                reasoning_probe_ok = _probe_reasoning(base_url, key, model_id, provider)
                break
        catalog_caps = dict(caps)
        caps["herramientas"] = bool(tool_probe_ok) if tool_probe_ok is not None else False
        caps["reasoning"] = bool(reasoning_probe_ok) if reasoning_probe_ok is not None else False
        score, breakdown, caps_norm = calcular_puntaje_comun(caps, context, max_output, params)
        apto = bool(is_free and probe_ok and tool_probe_ok is True and reasoning_probe_ok is True and cumple_minimos(caps_norm, probe_ok))
        entry = {
            "id": model_id, "modelo": model_id, "modelo_base": model_id, "nombre": item.get("name") or model_id,
            "proveedor": provider, "cuenta_id": selected_account,
            "cuentas_compatibles": [selected_account] if probe_ok and selected_account else [],
            "cuentas_probe_ok": [selected_account] if apto and selected_account else [],
            "puntaje": score, "apto_agente": apto,
            "parametros_b": params, "contexto": context, "max_completion_tokens": max_output,
            "capacidades": caps, "capacidades_norm": caps_norm, "gratis": is_free,
            "capacidades_catalogo": catalog_caps,
            "gratis_evidencia": evidence, "pricing": price, "price_raw": item.get("price"),
            "probe_ok": probe_ok, "probe_estado": "ok" if probe_ok else ("no_gratis" if not is_free else "fallo_probe"),
            "tool_probe_ok": tool_probe_ok, "tool_probe_estado": tool_probe_estado,
            "reasoning_probe_ok": reasoning_probe_ok,
            "chat_capaz": has_chat,
            "capacidades_secundarias": secondary, "modalidades": modalities,
            "adaptador_secundario_implementado": False,
            "fuente": "catalogo_autenticado", "desglose": " + ".join(breakdown),
        }
        if has_chat:
            ranking.append(entry)
        for capability in secondary:
            capability_catalog.setdefault(capability, []).append({
                "id": model_id, "modelo": model_id, "proveedor": provider,
                "cuentas_compatibles": [selected_account] if probe_ok and selected_account else [],
                "gratis": is_free, "probe_ok": probe_ok,
                "implementado": capability == "vision_image" and has_chat and probe_ok,
                "estado_prueba": "chat_verificado" if has_chat and probe_ok else "solo_catalogo",
                "modalidades": modalities,
                "fuente": "metadatos_catalogo; requiere adaptador de tarea para enrutar",
            })

    ranking.sort(key=clave_orden_modelo, reverse=True)
    for i, row in enumerate(ranking, 1): row["posicion"] = i
    for rows_for_cap in capability_catalog.values():
        rows_for_cap.sort(key=lambda row: (not row["gratis"], not row["probe_ok"], row["id"]))
    result = {
        "generado": datetime.now().isoformat(), "service": provider,
        "total_modelos": len(ranking), "total_aptos_finales": sum(bool(x["apto_agente"]) for x in ranking),
        "total_gratuitos": sum(bool(x["gratis"]) for x in ranking),
        "cuentas_catalogo_ok": len(keys) - len(errores), "errores_cuentas": errores,
        "cuentas_prueba_chat_ok": len(accounts_chat_ok),
        "nota_autenticacion": "Los catálogos públicos pueden responder sin autenticar; una prueba de chat es la única confirmación de uso en este ranking.",
        "ranking": ranking, "ranking_final": [x for x in ranking if x["apto_agente"]],
        "rankings_capacidades": capability_catalog,
    }
    state = ROOT / "state"
    state.mkdir(exist_ok=True)
    (state / f"ranking_{provider}.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return result


if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] not in CONFIG:
        raise SystemExit("Proveedor requerido: " + " | ".join(CONFIG))
    data = generar(sys.argv[1])
    print(f"{data['service']}: {data['total_modelos']} modelos | {data['total_gratuitos']} gratis | {data['total_aptos_finales']} aptos para agentes")
