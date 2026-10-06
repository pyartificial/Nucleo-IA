#!/usr/bin/env python3
"""Ranking local de TokenRouter para Núcleo IA (Modo Filtro Estricto: Solo Modelos Free / Gratuitos).

Extrae dinámicamente o consulta el catálogo de TokenRouter (https://www.tokenrouter.com),
analiza sus capacidades, ejecuta sondeo en vivo multihilo con la API Key para detectar
exclusivamente los modelos con acceso libre/gratuito (sin requerir saldo pago),
y calcula puntajes estandarizados para integrarlos al ranking global.
"""
from __future__ import annotations

import json
import os
import urllib.request
import urllib.error
from datetime import datetime
from pathlib import Path

from ranking_common import calcular_puntaje_comun, clave_orden_modelo, cumple_minimos, extraer_parametros
from ranking_quality import probar_herramienta_openai
from ranking_pasarelas_free import (
    _capabilities as _descubrir_capacidades,
    _es_chat,
    _free as _evidencia_gratuita,
)
from secret_utils import get_tokenrouter_accounts, get_tokenrouter_api_key

RAIZ = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
STATE_DIR = os.path.join(RAIZ, "state")
SALIDA = os.path.join(STATE_DIR, "ranking_tokenrouter.json")

# Catálogo base conocido de modelos libres/gratuitos de TokenRouter
CATALOGO_TOKENROUTER_BASE = {
    "qwen/qwen3.8-max-free": {
        "contexto": 131072,
        "max_completion_tokens": 32768,
        "parametros_b": 72.0,
        "capacidades": {"herramientas": True, "reasoning": True, "vision": False},
    },
    "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free": {
        "contexto": 131072,
        "max_completion_tokens": 16384,
        "parametros_b": 30.0,
        "capacidades": {"herramientas": True, "reasoning": True, "vision": True},
    },
}


def _metadatos_capacidades(item: dict) -> tuple[dict, list[str], list[str]]:
    """Normaliza formatos de tarea de TokenRouter para el catálogo secundario."""
    normalized = dict(item)
    formats = item.get("api_formats") or item.get("apiFormats") or []
    if isinstance(formats, str):
        formats = [formats]
    formats = {str(value).casefold().replace("_", "-") for value in formats}
    task_map = {
        "embeddings": ("task", "embeddings"),
        "embedding": ("task", "embeddings"),
        "reranking": ("task", "reranking"),
        "rerank": ("task", "reranking"),
        "image-generation": ("output_task", "image_generation"),
        "image-editing": ("output_task", "image_editing"),
        "video-editing": ("output_task", "video_editing"),
        "video-generation": ("output_task", "video_generation"),
        "text-to-video": ("output_task", "text_to_video"),
        "image-to-video": ("output_task", "image_to_video"),
        "text-to-speech": ("output_task", "text_to_speech"),
        "speech-generation": ("output_task", "speech_generation"),
        "speech-to-speech": ("task", "speech_to_speech"),
        "voice-cloning": ("task", "voice_cloning"),
        "voice-design": ("output_task", "voice_design"),
        "audio-isolation": ("task", "audio_isolation"),
        "transcription": ("input_task", "transcription"),
        "speech-to-text": ("input_task", "speech_to_text"),
        "audio-transcription": ("input_task", "audio_to_text"),
        "transcription-realtime": ("input_task", "realtime_transcription"),
        "real-time-transcription": ("input_task", "realtime_transcription"),
        "dubbing": ("task", "dubbing"),
        "forced-alignment": ("task", "forced_alignment"),
        "text-alignment": ("task", "forced_alignment"),
        "lip-sync": ("task", "lip_sync"),
        "sound-effects": ("task", "sound_effect"),
        "music-generation": ("task", "music_generation"),
        "music-editing": ("task", "music_editing"),
        "audio-inpainting": ("task", "music_editing"),
        "voice-agents": ("task", "voice_agents"),
        "document-parsing": ("task", "document_parsing"),
    }
    capability_map = {
        "vision-image": {"vision_image"},
        "vision-video": {"vision_video"},
        "transcription": {"transcription_audio"},
        "speech-to-text": {"transcription_audio"},
        "audio-transcription": {"transcription_audio"},
        "transcription-realtime": {"transcription_audio", "transcription_realtime"},
        "real-time-transcription": {"transcription_audio", "transcription_realtime"},
        "text-to-speech": {"speech_generation"},
        "speech-generation": {"speech_generation"},
        "speech-to-speech": {"speech_to_speech"},
        "voice-cloning": {"voice_cloning"},
        "voice-design": {"voice_design", "speech_generation"},
        "audio-isolation": {"audio_isolation"},
        "dubbing": {"dubbing"},
        "forced-alignment": {"forced_alignment"},
        "text-alignment": {"forced_alignment"},
        "image-generation": {"image_generation"},
        "image-editing": {"image_editing"},
        "video-generation": {"video_generation_text"},
        "text-to-video": {"video_generation_text"},
        "image-to-video": {"video_generation_image"},
        "video-editing": {"video_editing"},
        "embeddings": {"embeddings"},
        "embedding": {"embeddings"},
        "reranking": {"reranking"},
        "rerank": {"reranking"},
        "document-parsing": {"parse_documents"},
        "lip-sync": {"lip_sync"},
        "sound-effects": {"sound_effects"},
        "music-generation": {"music_generation"},
        "music-editing": {"music_editing"},
        "audio-inpainting": {"music_editing"},
        "voice-agents": {"voice_agents"},
    }
    def add_modality(field: str, modality: str) -> None:
        values = normalized.get(field, [])
        if isinstance(values, str):
            values = [values]
        normalized[field] = list({str(value) for value in values} | {modality})

    for api_format in formats:
        field_value = task_map.get(api_format)
        if not field_value:
            continue
        field, task = field_value
        previous_task = str(normalized.get(field, "")).strip()
        normalized[field] = f"{previous_task}_{task}" if previous_task else task
        if field == "output_task" and api_format.startswith("image-"):
            add_modality("output_modalities", "image")
        elif field == "output_task" and ("video" in api_format):
            add_modality("output_modalities", "video")
        elif field == "output_task" and any(x in api_format for x in ("speech", "audio")):
            add_modality("output_modalities", "audio")
        elif field == "input_task" and any(x in api_format for x in ("speech", "transcription", "audio")):
            add_modality("input_modalities", "audio")
    caps, capabilities, modalities = _descubrir_capacidades(normalized)
    for api_format in formats:
        capabilities.extend(capability_map.get(api_format, ()))
    return caps, sorted(set(capabilities)), modalities


def _catalogo_capacidades(modelos: dict[str, dict]) -> dict[str, list[dict]]:
    catalog: dict[str, list[dict]] = {}
    for model_id, item in modelos.items():
        _, capabilities, modalities = _metadatos_capacidades(item)
        gratis, evidence = _evidencia_gratuita(item, "tokenrouter", "pricing")
        evidence = str(item.get("_nucleo_free_evidence") or evidence)
        for capability in capabilities:
            catalog.setdefault(capability, []).append({
                "id": model_id,
                "modelo": model_id,
                "proveedor": "tokenrouter",
                "gratis": gratis,
                "gratis_evidencia": evidence,
                "probe_ok": False,
                "implementado": False,
                "estado_prueba": "solo_catalogo",
                "modalidades": modalities,
                "fuente": "catalogo_tokenrouter; capacidad secundaria descubierta, requiere verificación y adaptador de tarea",
            })
    for entries in catalog.values():
        entries.sort(key=lambda entry: (not entry["gratis"], entry["id"]))
    return catalog


def _cuentas_tokenrouter() -> list[tuple[str, str]]:
    cuentas = []
    vistos = set()
    for index, account in enumerate(get_tokenrouter_accounts(Path(RAIZ)), 1):
        key = str(account.get("api_key") or "").strip()
        if not key or key.startswith("TU_") or key in vistos:
            continue
        account_id = str(account.get("id") or f"tokenrouter_{index}")
        cuentas.append((account_id, key))
        vistos.add(key)
    if not cuentas:
        key = get_tokenrouter_api_key(Path(RAIZ))
        if key:
            cuentas.append(("clave_global", str(key).strip()))
    return cuentas


def _unir_catalogo_modelos(catalogos: list[tuple[str, str, dict[str, dict]]]) -> tuple[dict[str, dict], dict[str, list[tuple[str, str, str]]]]:
    """Combina los catálogos por modelo y conserva las cuentas que lo ofrecen gratis."""
    modelos: dict[str, dict] = {}
    gratis_por_cuenta: dict[str, list[tuple[str, str, str]]] = {}
    for account_id, key, catalog in catalogos:
        for model_id, raw in catalog.items():
            item = dict(raw)
            current = modelos.setdefault(model_id, dict(item))
            for field in ("api_formats", "apiFormats", "input_modalities", "output_modalities"):
                old_values = current.get(field, [])
                new_values = item.get(field, [])
                if isinstance(old_values, str): old_values = [old_values]
                if isinstance(new_values, str): new_values = [new_values]
                if old_values or new_values:
                    current[field] = sorted({str(value) for value in old_values + new_values})
            if isinstance(item.get("capabilities"), dict):
                merged_flags = dict(current.get("capabilities") or {})
                for flag, value in item["capabilities"].items():
                    merged_flags[flag] = bool(merged_flags.get(flag) or value)
                current["capabilities"] = merged_flags
            free, evidence = _evidencia_gratuita(item, "tokenrouter", "pricing")
            if free:
                current["is_free"] = True
                current["_nucleo_free_evidence"] = evidence
                gratis_por_cuenta.setdefault(model_id, []).append((account_id, key, evidence))
    return modelos, gratis_por_cuenta


def _candidato_chat(item: dict, model_id: str) -> bool:
    formats = item.get("api_formats") or item.get("apiFormats") or []
    if isinstance(formats, str):
        formats = [formats]
    normalized_formats = {str(value).casefold().replace("_", "-") for value in formats}
    if normalized_formats and not normalized_formats.intersection({"openai", "openai-compatible", "openai-chat", "chat-completions"}):
        return False
    caps, _, _ = _metadatos_capacidades(item)
    return _es_chat(item, model_id, caps)


def _inferir_metadatos(model_id: str, remote_info: dict | None = None) -> dict:
    mid_low = model_id.lower()
    if model_id in CATALOGO_TOKENROUTER_BASE:
        res = dict(CATALOGO_TOKENROUTER_BASE[model_id])
        if remote_info and remote_info.get("context_window"):
            res["contexto"] = int(remote_info["context_window"])
        return res

    # Extraer parámetros de arquitectura
    params_b = extraer_parametros(model_id)
    if params_b <= 0.0 and "max" in mid_low:
        params_b = 72.0

    # Inferencia heurística de contexto
    ctx = int((remote_info or {}).get("context_window", 0))
    if ctx <= 0:
        if "1m" in mid_low or "kimi" in mid_low or "gemini" in mid_low:
            ctx = 1048576
        elif "256k" in mid_low or "minimax" in mid_low or "nemotron" in mid_low:
            ctx = 262144
        elif "128k" in mid_low or "llama-3" in mid_low or "qwen" in mid_low or "deepseek" in mid_low:
            ctx = 131072
        else:
            ctx = 32768

    max_tokens = 32768 if ctx >= 128000 else 8192

    is_reasoning = "r1" in mid_low or "reason" in mid_low or "think" in mid_low or "kimi" in mid_low or "deepseek" in mid_low or "max" in mid_low or params_b >= 70.0
    is_tools = "distill" not in mid_low and "whisper" not in mid_low and "guard" not in mid_low and "embed" not in mid_low
    is_vision = "vision" in mid_low or "vl" in mid_low or "image" in mid_low or "kimi" in mid_low or "4o" in mid_low

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
    url = "https://api.tokenrouter.com/v1/models"
    req = urllib.request.Request(url, headers={
        "Authorization": f"Bearer {api_key}",
        "Accept": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    })
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
            modelos_raw = data.get("data", []) or data.get("models", [])
            salida = {}
            for m in modelos_raw:
                mid = m.get("id", "")
                if not mid or m.get("active") is False:
                    continue
                if mid.startswith("whisper") or "guard" in mid.lower() or "embed" in mid.lower():
                    continue
                salida[mid] = m
            return salida
    except Exception as e:
        print(f"  [!] Error consultando API de TokenRouter: {e}")
        return {}


def _modelos_gratuitos(modelos: dict[str, dict]) -> dict[str, dict]:
    """Devuelve solo rutas cuyo catálogo aporta evidencia de costo cero.

    Un catálogo autenticado también devuelve modelos pagos. No se debe sondear
    chat ni inferir gratuidad a partir de que la cuenta tenga crédito.
    """
    return {
        model_id: info
        for model_id, info in modelos.items()
        if _evidencia_gratuita(info, "tokenrouter", "pricing")[0]
    }


def prober_modelo(model_id: str, api_key: str) -> tuple[bool, str]:
    url = "https://api.tokenrouter.com/v1/chat/completions"
    payload = json.dumps({
        "model": model_id,
        "messages": [{"role": "user", "content": "ping"}],
        "max_tokens": 10,
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
        with urllib.request.urlopen(req, timeout=10) as resp:
            if resp.status == 200:
                return True, "ok"
            return False, f"status_{resp.status}"
    except urllib.error.HTTPError as e:
        return False, f"http_{e.code}"
    except Exception as e:
        return False, str(e)[:30]


def _probar_razonamiento(model_id: str, api_key: str) -> tuple[bool, str]:
    """Comprueba una respuesta determinista; el nombre del modelo no basta."""
    url = "https://api.tokenrouter.com/v1/chat/completions"
    payload = json.dumps({
        "model": model_id,
        "messages": [{"role": "user", "content": (
            "En una carrera, Lara llegó antes que Inés; Inés antes que Bruno; "
            "Bruno antes que Mateo. ¿Quién llegó segundo? Responde únicamente: INES"
        )}],
        "max_tokens": 24,
        "temperature": 0,
    }).encode("utf-8")
    req = urllib.request.Request(url, data=payload, headers={
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": "Nucleo-IA-Ranking/1.0",
    }, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=25) as response:
            body = json.loads(response.read().decode("utf-8"))
        choices = body.get("choices") or []
        message = (choices[0].get("message") or {}) if choices else {}
        content = message.get("content", "")
        if isinstance(content, list):
            content = "".join(str(x.get("text", "")) for x in content if isinstance(x, dict))
        normalized = str(content).upper().replace("Í", "I").strip(" .,:;!¡¿?\"'")
        return normalized == "INES", "ok" if normalized == "INES" else "respuesta_no_exacta"
    except urllib.error.HTTPError as exc:
        return False, f"http_{exc.code}"
    except Exception as exc:
        return False, type(exc).__name__


def generar_ranking() -> dict:
    print("═" * 80)
    print("  RANKING DE TOKENROUTER — Núcleo IA (Solo Modelos Free / Gratuitos)")
    print("═" * 80)

    cuentas = _cuentas_tokenrouter()
    api_key = cuentas[0][1] if cuentas else None
    catalogos = []
    if cuentas:
        print(f"  [*] {len(cuentas)} cuenta(s) configurada(s). Consultando catálogos oficiales...")
        for account_id, key in cuentas:
            catalog = obtener_modelos_remotos(key)
            if catalog:
                catalogos.append((account_id, key, catalog))

    remotos_dict, cuentas_free = _unir_catalogo_modelos(catalogos)
    total_modelos_catalogo = len(remotos_dict)
    catalogo_remoto_disponible = bool(catalogos)
    catalogo_capacidades = _catalogo_capacidades(remotos_dict)

    if not catalogo_remoto_disponible:
        if not cuentas:
            print("  [i] Sin API Key activa. Usando catálogo estático verificado de modelos libres.")
        else:
            print("  [!] No se pudo consultar ningún catálogo remoto. Se conserva la lista estática solo como referencia.")
        modelos_ids = list(CATALOGO_TOKENROUTER_BASE.keys())
        modelos_free = {
            model_id: {"info": {"id": model_id}, "cuentas": [], "evidencia": "ID estático conocido como variante free; pendiente de catálogo actual"}
            for model_id in modelos_ids
        }
    else:
        # El catálogo incluye rutas pagas. Solo las gratuitas explícitas pueden
        # llegar a cualquier prueba que envíe una solicitud de chat.
        candidatos_free = _modelos_gratuitos(remotos_dict)
        total_modelos_omitidos_por_precio = total_modelos_catalogo - len(candidatos_free)
        modelos_free = {
            model_id: {
                "info": item,
                "cuentas": cuentas_free.get(model_id, []),
                "evidencia": str(item.get("_nucleo_free_evidence") or "evidencia_gratuita_del_catalogo"),
            }
            for model_id, item in candidatos_free.items()
            if _candidato_chat(item, model_id) and cuentas_free.get(model_id)
        }
        modelos_ids = list(modelos_free)
    if not total_modelos_catalogo and not catalogo_remoto_disponible:
        total_modelos_omitidos_por_precio = 0

    probe_resultados: dict[str, tuple[bool, str]] = {}

    if cuentas and modelos_ids and catalogo_remoto_disponible:
        print(f"  [*] Sondeando {len(modelos_ids)} modelos para verificar acceso gratuito...")
        for model_id in modelos_ids:
            resultado = (False, "sin_cuenta_free", "", "")
            for account_id, key, _ in modelos_free[model_id]["cuentas"]:
                try:
                    ok, state = prober_modelo(model_id, key)
                except Exception as exc:
                    ok, state = False, type(exc).__name__
                if ok:
                    resultado = (True, state, account_id, key)
                    break
                resultado = (False, state, "", "")
            probe_resultados[model_id] = resultado
    else:
        for mid in modelos_ids:
            estado = "catalogo_no_disponible" if cuentas else "sin_clave"
            probe_resultados[mid] = (False, estado, "", "")

    ranking = []
    rechazados = []

    for model_id in modelos_ids:
        ok, estado, cuenta_id_probe, api_key_probe = probe_resultados.get(model_id, (False, "sin_probar", "", ""))
        
        # Una respuesta correcta no demuestra gratuidad; esa condición ya se
        # exigió al filtrar el catálogo, antes de enviar solicitudes.
        if api_key and not ok:
            continue

        remote_info = modelos_free[model_id]["info"]
        meta = _inferir_metadatos(model_id, remote_info)
        _, secondary, modalities = _metadatos_capacidades(remote_info or {"id": model_id})
        caps = dict(meta.get("capacidades", {}))
        tool_probe_ok = False
        tool_probe_estado = "no_ejecutada"
        if api_key_probe and ok and caps.get("herramientas"):
            tool_probe_ok, tool_probe_estado = probar_herramienta_openai(
                "https://api.tokenrouter.com/v1/chat/completions",
                api_key_probe,
                model_id,
                timeout=25,
            )
        reasoning_probe_ok = False
        reasoning_probe_estado = "no_ejecutada"
        if api_key_probe and ok and caps.get("reasoning"):
            reasoning_probe_ok, reasoning_probe_estado = _probar_razonamiento(model_id, api_key_probe)
        # El ranking de agentes refleja pruebas observadas, no heurísticas del ID.
        caps["herramientas"] = bool(tool_probe_ok)
        caps["reasoning"] = bool(reasoning_probe_ok)
        contexto = int(meta.get("contexto", 0) or 0)
        max_tok = int(meta.get("max_completion_tokens", 0) or 0)
        params_b = float(meta.get("parametros_b", 0.0) or 0.0)

        puntaje, desglose, caps_norm = calcular_puntaje_comun(
            caps,
            contexto=contexto,
            max_completion_tokens=max_tok,
            parametros_b=params_b,
        )

        apto = cumple_minimos(caps_norm, ok)

        entrada = {
            "id": model_id,
            "modelo": model_id,
            "modelo_base": model_id,
            "nombre": model_id,
            "proveedor": "tokenrouter",
            "cuenta_id": cuenta_id_probe,
            "cuentas_compatibles": [cuenta_id_probe] if cuenta_id_probe else [],
            "cuentas_probe_ok": [cuenta_id_probe] if apto and cuenta_id_probe else [],
            "puntaje": puntaje,
            "apto_agente": apto,
            "parametros_b": params_b,
            "contexto": contexto,
            "max_completion_tokens": max_tok,
            "capacidades": caps,
            "capacidades_norm": caps_norm,
            "gratis": bool(modelos_free[model_id]["cuentas"]),
            "gratis_evidencia": modelos_free[model_id]["evidencia"],
            "probe_ok": ok,
            "probe_estado": estado,
            "probe_preview": "ok",
            "tool_probe_ok": tool_probe_ok,
            "tool_probe_estado": tool_probe_estado,
            "reasoning_probe_ok": reasoning_probe_ok,
            "reasoning_probe_estado": reasoning_probe_estado,
            "capacidades_secundarias": secondary,
            "modalidades": modalities,
            "adaptador_secundario_implementado": False,
            "desglose": " + ".join(desglose) if desglose else "",
            "fuente": "tokenrouter_api" if api_key else "tokenrouter_catalog",
        }

        for capability, catalog_rows in catalogo_capacidades.items():
            for catalog_row in catalog_rows:
                if catalog_row["id"] == model_id and ok:
                    catalog_row["probe_ok"] = True
                    catalog_row["estado_prueba"] = "chat_verificado"
                    catalog_row["implementado"] = capability == "vision_image"
        
        if apto or (not cuentas):
            ranking.append(entrada)
        else:
            rechazados.append(entrada)

    ranking.sort(key=clave_orden_modelo, reverse=True)
    for i, r in enumerate(ranking):
        r["posicion"] = i + 1

    resultado = {
        "generado": datetime.now().isoformat(),
        "service": "tokenrouter",
        "total_modelos": len(ranking),
        "total_modelos_catalogo": total_modelos_catalogo or len(modelos_ids),
        "total_modelos_omitidos_por_precio": total_modelos_omitidos_por_precio,
        "total_aptos_finales": sum(1 for r in ranking if r.get("apto_agente")),
        "ranking": ranking,
        "ranking_final": [r for r in ranking if r.get("apto_agente")],
        "ranking_rechazados_probe": rechazados,
        "rankings_capacidades": catalogo_capacidades,
        "ficha_comun": {
            "filtro": ["herramientas", "reasoning", "probe_ok", "gratis_only"],
        },
    }

    os.makedirs(STATE_DIR, exist_ok=True)
    with open(SALIDA, "w", encoding="utf-8") as f:
        json.dump(resultado, f, indent=2, ensure_ascii=False)

    if not ranking:
        print("  [!] No se encontraron modelos gratuitos activos en este momento.")
    else:
        for r in ranking:
            apto_str = "[APTO - FREE]" if r.get("apto_agente") else "[SECUNDARIO]"
            print(f"  #{r['posicion']:>2} {r['puntaje']:>3} pts  {r['modelo']:40s} {apto_str} ({r['desglose']})")

    print(f"\nGuardado en: {SALIDA}")
    return resultado


if __name__ == "__main__":
    generar_ranking()
