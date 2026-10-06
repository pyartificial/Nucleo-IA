#!/usr/bin/env python3
"""Ranking vivo de Cohere y sus capacidades especializadas.

El catálogo se obtiene de la API. En modo trial, todas las llamadas son
gratuitas pero limitadas; en cualquier otro modo se excluyen para no arriesgar
costos. Los modelos que no son LLM se guardan en rankings secundarios.
"""
from __future__ import annotations
import base64, io, json, os, struct, urllib.error, urllib.parse, urllib.request, wave, zlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from ranking_common import calcular_puntaje_comun, clave_orden_modelo, cumple_minimos
from secret_utils import get_cohere_api_key, load_local_env

ROOT = Path(__file__).resolve().parent.parent
STATE = ROOT / "state"
OUT = STATE / "ranking_cohere.json"
CATALOG = STATE / "ranking_cohere_catalogo.json"
CAPS_OUT = STATE / "ranking_cohere_capacidades.json"
API = "https://api.cohere.com"
TIMEOUT = int(os.getenv("COHERE_RANKING_TIMEOUT", "60"))

def now(): return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
def read_json(path, default):
    try: return json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception: return default
def save_json(path, data):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
def short(value, n=180):
    text = " ".join(str(value or "").split())
    return text if len(text) <= n else text[:n-1] + "…"

def request_json(path, key, payload=None, method="GET"):
    data = None if payload is None else json.dumps(payload).encode()
    req = urllib.request.Request(API + path, data=data, method=method, headers={
        "Authorization": "Bearer " + key, "Content-Type": "application/json", "X-Client-Name": "NucleoIA-ranking"})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as response:
        result = json.loads(response.read().decode("utf-8", errors="replace"))
    return result if isinstance(result, dict) else {}

def discover(key):
    result, token = [], ""
    while True:
        query = "?page_size=1000" + ("&page_token=" + urllib.parse.quote(token) if token else "")
        data = request_json("/v1/models" + query, key)
        page = data.get("models") or []
        result.extend(x for x in page if isinstance(x, dict) and x.get("name"))
        token = str(data.get("next_page_token") or "")
        if not token or not page: break
    if not result: raise RuntimeError("el catálogo de Cohere no devolvió modelos")
    return result

def text_from_chat(data):
    blocks = (data.get("message") or {}).get("content") or []
    out = []
    for block in blocks:
        if not isinstance(block, dict): continue
        for field in ("text", "thinking", "summary"):
            value = block.get(field)
            if isinstance(value, str): out.append(value)
            elif isinstance(value, list): out.extend(str(x.get("text", "")) for x in value if isinstance(x, dict))
    return " ".join(x for x in out if x).strip()

def error_state(exc): return "http_" + str(exc.code) if isinstance(exc, urllib.error.HTTPError) else type(exc).__name__

def probe_chat(model, key, tools=False):
    body = {"model": model, "messages": [{"role": "user", "content": "Responde únicamente OK."}], "max_tokens": 128}
    if tools:
        body["tools"] = [{"type": "function", "function": {"name": "ranking_ping", "description": "Devuelve un valor de prueba.", "parameters": {"type": "object", "properties": {"value": {"type": "integer"}}, "required": ["value"]}}}]
        # Cohere admite la elección automática; ``tool_choice`` como objeto
        # no es válido en v2 y algunos modelos tampoco aceptan REQUIRED.
        body["messages"][0]["content"] = "Llama obligatoriamente a ranking_ping con value 7 y no escribas texto."
    try:
        data = request_json("/v2/chat", key, body, "POST")
        calls = (data.get("message") or {}).get("tool_calls") or []
        text = text_from_chat(data)
        return {"ok": bool(text or calls), "estado": "ok_tool" if calls else ("ok" if text else "respuesta_vacia"), "preview": short(text), "tool_ok": bool(calls)}
    except Exception as exc: return {"ok": False, "estado": error_state(exc), "preview": "", "tool_ok": False}

def png_uri():
    def chunk(kind, payload):
        return struct.pack(">I", len(payload)) + kind + payload + struct.pack(">I", zlib.crc32(kind + payload) & 0xffffffff)
    pixels = b"\x00\xff\xff\xff\xff\xff\xff\xff\xff" * 2
    raw = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", 2, 2, 8, 6, 0, 0, 0)) + chunk(b"IDAT", zlib.compress(pixels)) + chunk(b"IEND", b"")
    return "data:image/png;base64," + base64.b64encode(raw).decode()

def probe_special(model, endpoint, key):
    try:
        if endpoint in ("embed", "embed_image"):
            if endpoint == "embed_image":
                # Cohere publica los modelos de imagen como alias; el endpoint
                # usa el nombre base y recibe la imagen en el cuerpo.
                base = model[:-6] if model.endswith("-image") else model
                payload = {"model": base, "images": [png_uri()], "input_type": "image", "embedding_types": ["float"]}
            else:
                payload = {"model": model, "texts": ["Nucleo IA"], "input_type": "search_query", "embedding_types": ["float"]}
            d = request_json("/v2/embed", key, payload, "POST")
            emb = (d.get("embeddings") or {}).get("float") or []
            return {"ok": bool(emb), "estado": "ok" if emb else "respuesta_vacia", "detalle": "dimensiones=" + str(len(emb[0])) if emb and isinstance(emb[0], list) else ""}
        if endpoint == "rerank":
            d = request_json("/v2/rerank", key, {"model": model, "query": "capital de Francia", "documents": ["París es la capital de Francia.", "Roma está en Italia."], "top_n": 1}, "POST")
            return {"ok": bool(d.get("results")), "estado": "ok" if d.get("results") else "respuesta_vacia", "detalle": "ranking_validado"}
        if endpoint == "parse":
            d = request_json("/v2/parse", key, {"model": model, "document": {"type": "image_url", "image_url": png_uri()}, "output_format": "markdown"}, "POST")
            return {"ok": bool(d.get("pages")), "estado": "ok" if d.get("pages") else "respuesta_vacia", "detalle": "paginas=" + str(len(d.get("pages") or []))}
        if endpoint == "transcriptions":
            stream = io.BytesIO(); wav = wave.open(stream, "wb"); wav.setnchannels(1); wav.setsampwidth(2); wav.setframerate(8000); wav.writeframes(struct.pack("<h", 0) * 8000); wav.close()
            boundary = "----NucleoIAProbe"; audio = stream.getvalue()
            body = b"".join([f"--{boundary}\r\nContent-Disposition: form-data; name=\"model\"\r\n\r\n{model}\r\n".encode(), f"--{boundary}\r\nContent-Disposition: form-data; name=\"language\"\r\n\r\nes\r\n".encode(), f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"probe.wav\"\r\nContent-Type: audio/wav\r\n\r\n".encode(), audio, f"\r\n--{boundary}--\r\n".encode()])
            req = urllib.request.Request(API + "/v2/audio/transcriptions", data=body, method="POST", headers={"Authorization": "Bearer " + key, "Content-Type": "multipart/form-data; boundary=" + boundary})
            with urllib.request.urlopen(req, timeout=TIMEOUT) as response: d = json.loads(response.read().decode("utf-8", errors="replace"))
            return {"ok": isinstance(d, dict) and "text" in d, "estado": "ok" if "text" in d else "respuesta_vacia", "detalle": "audio_aceptado"}
    except Exception as exc: return {"ok": False, "estado": error_state(exc), "detalle": ""}
    return {"ok": False, "estado": "endpoint_no_soportado", "detalle": ""}

def caps_for(model):
    fs = {str(x).lower() for x in (model.get("features") or [])}; eps = {str(x).lower() for x in (model.get("endpoints") or [])}; name = str(model.get("name", "")).lower()
    return {"herramientas": "tools" in fs or "strict_tools" in fs, "reasoning": "reasoning" in fs or ("chat" in eps and not any(x in name for x in ("translate", "vision"))), "vision": "vision" in fs or "vision" in name, "audio": "transcriptions" in eps}

def secondary_type(model):
    eps = {str(x).lower() for x in (model.get("endpoints") or [])}; name = str(model.get("name", "")).lower()
    if "embed_image" in eps: return "embeddings_imagen"
    if "embed" in eps: return "embeddings"
    if "rerank" in eps: return "reranking"
    if "transcriptions" in eps: return "transcripcion_audio"
    if "parse" in eps: return "parse_documentos"
    if "translate" in name: return "traduccion"
    if "vision" in name: return "vision"
    return ""

def generar_ranking():
    load_local_env(ROOT); key = get_cohere_api_key(ROOT)
    if not key: raise SystemExit("[!] Falta COHERE_API_KEY")
    modo = os.getenv("COHERE_KEY_MODE", "trial").strip().lower(); gratis = modo == "trial"
    modelos = discover(key); save_json(CATALOG, {"generado": now(), "fuente": "api_v1_models", "total": len(modelos), "modelos": modelos})
    ranking, secundarios = [], {}
    for model in modelos:
        name = str(model["name"]); eps = {str(x).lower() for x in (model.get("endpoints") or [])}; caps = caps_for(model); ctx = int(model.get("context_length") or 0)
        points, breakdown, norm = calcular_puntaje_comun(caps, contexto=ctx, parametros_b=0)
        row = {"id": name, "modelo": name, "modelo_base": name, "nombre": name, "proveedor": "cohere", "puntaje": points, "parametros_b": 0.0, "contexto": ctx, "max_completion_tokens": 0, "capacidades": caps, "capacidades_norm": norm, "endpoints": sorted(eps), "features": model.get("features") or [], "gratis": gratis, "gratis_evidencia": "clave_trial:uso_gratuito_con_limites" if gratis else "clave_no_trial:precio_no_verificado", "is_deprecated": bool(model.get("is_deprecated")), "fuente": "api_v1_models", "desglose": " + ".join(breakdown), "probe_ok": False, "probe_estado": "pendiente"}
        if "chat" in eps and not row["is_deprecated"]:
            p = probe_chat(name, key, caps["herramientas"]); row.update({"probe_ok": p["ok"], "probe_estado": p["estado"], "probe_preview": p["preview"], "tool_probe_ok": p["tool_ok"] if caps["herramientas"] else None, "tool_probe_estado": p["estado"] if caps["herramientas"] else "no_aplica", "apto_agente": bool(gratis and cumple_minimos(norm, p["ok"]))}); ranking.append(row)
        else:
            typ = secondary_type(model)
            if typ and gratis:
                ep = "embed_image" if "embed_image" in eps else "embed" if "embed" in eps else "rerank" if "rerank" in eps else "parse" if "parse" in eps else "transcriptions" if "transcriptions" in eps else ""
                p = probe_special(name, ep, key); row.update({"probe_ok": p["ok"], "probe_estado": p["estado"], "probe_detalle": p["detalle"], "apto_agente": False}); secundarios.setdefault(typ, []).append(row)
    ranking.sort(key=clave_orden_modelo, reverse=True)
    for i, row in enumerate(ranking, 1): row["posicion"] = i
    for values in secundarios.values():
        values.sort(key=clave_orden_modelo, reverse=True)
        for i, row in enumerate(values, 1): row["posicion"] = i
    result = {"generado": now(), "service": "cohere", "modo_clave": modo, "catalogo_fuente": "api_v1_models", "total_catalogo": len(modelos), "total_modelos": len(ranking), "total_aptos_finales": sum(bool(x.get("apto_agente")) for x in ranking), "ranking": ranking, "ranking_final": [x for x in ranking if x.get("apto_agente")], "ranking_rechazados_probe": [x for x in ranking if not x.get("apto_agente")], "rankings_secundarios": secundarios, "ficha_comun": {"filtro": ["catalogo_api", "gratis_trial", "probe_ok", "herramientas", "reasoning"], "nota": "Los modelos especializados se conservan separados y no se promocionan a LLM agéntico."}}
    save_json(OUT, result); save_json(CAPS_OUT, {"generado": result["generado"], "service": "cohere", "modo_clave": modo, "rankings": secundarios})
    print("═" * 80); print("  RANKING DE COHERE — catálogo y capacidades vivas"); print("═" * 80); print(f"  Catálogo API: {len(modelos)} | Chat: {len(ranking)} | Agentes gratuitos: {result['total_aptos_finales']}")
    for row in ranking: print(f"  #{row['posicion']:>2} {row['puntaje']:>3} pts  {row['modelo']}  [{row['probe_estado']}]")
    print("  Secundarios: " + ", ".join(f"{k}={len(v)}" for k, v in sorted(secundarios.items()))); print(f"\nGuardado en: {OUT}")
    return result

if __name__ == "__main__": generar_ranking()
