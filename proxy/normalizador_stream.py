import json


def resetear_contadores():
    pass


def normalizar_linea_sse(linea_raw):
    linea = linea_raw.strip()
    if not linea:
        return None

    if linea.startswith("data: "):
        contenido = linea[6:]
        if contenido == "[DONE]":
            return None
        try:
            datos = json.loads(contenido)
            datos = _normalizar_chunk(datos)
            return f"data: {json.dumps(datos, ensure_ascii=False)}"
        except json.JSONDecodeError:
            return linea

    try:
        datos = json.loads(linea)
        datos = _normalizar_chunk(datos)
        return f"data: {json.dumps(datos, ensure_ascii=False)}"
    except json.JSONDecodeError:
        pass

    return None


def _normalizar_chunk(datos):
    if not isinstance(datos, dict) or "choices" not in datos:
        return datos

    for choice in datos.get("choices", []):
        if not isinstance(choice, dict):
            continue
        delta = choice.get("delta", {})
        if isinstance(delta, dict):
            tool_calls = delta.get("tool_calls", [])
            if isinstance(tool_calls, list):
                for i, tc in enumerate(tool_calls):
                    if isinstance(tc, dict):
                        tc.setdefault("index", i)

        if delta == {} and choice.get("finish_reason") is None:
            choice["delta"] = {"content": ""}

    return datos


def inyectar_finish(modelo="unknown"):
    chunk_final = {
        "id": "granja-final",
        "object": "chat.completion.chunk",
        "model": modelo,
        "choices": [{
            "index": 0,
            "delta": {},
            "finish_reason": "stop",
        }]
    }
    return f"data: {json.dumps(chunk_final)}\n\ndata: [DONE]\n\n"


def normalizar_respuesta_completa(body_json):
    if not isinstance(body_json, dict) or "choices" not in body_json:
        return body_json

    for choice in body_json.get("choices", []):
        if not isinstance(choice, dict):
            continue
        if "finish_reason" not in choice or choice["finish_reason"] is None:
            choice["finish_reason"] = "stop"

        msg = choice.get("message", {})
        if isinstance(msg, dict):
            tool_calls = msg.get("tool_calls", [])
            if isinstance(tool_calls, list):
                for i, tc in enumerate(tool_calls):
                    if isinstance(tc, dict):
                        tc.setdefault("index", i)

    return body_json
