"""Validación pequeña y estable de cuerpos OpenAI compatibles."""
from __future__ import annotations

from typing import Any


class EntradaInvalida(ValueError):
    pass


def validar_chat(body: Any) -> dict[str, Any]:
    if not isinstance(body, dict):
        raise EntradaInvalida("El cuerpo JSON debe ser un objeto.")
    model = body.get("model", "auto")
    if not isinstance(model, str) or not model.strip() or len(model) > 300:
        raise EntradaInvalida("El campo model debe ser texto válido.")
    messages = body.get("messages")
    if not isinstance(messages, list) or not messages or len(messages) > 1000:
        raise EntradaInvalida("messages debe ser una lista no vacía.")
    for message in messages:
        if not isinstance(message, dict):
            raise EntradaInvalida("Cada mensaje debe ser un objeto.")
        if message.get("role") not in {"system", "developer", "user", "assistant", "tool"}:
            raise EntradaInvalida("Cada mensaje necesita un role compatible.")
        if "content" not in message and "tool_calls" not in message:
            raise EntradaInvalida("Cada mensaje necesita content o tool_calls.")
    tools = body.get("tools", [])
    if tools is not None and (not isinstance(tools, list) or len(tools) > 128):
        raise EntradaInvalida("tools debe ser una lista de hasta 128 herramientas.")
    if "stream" in body and not isinstance(body["stream"], bool):
        raise EntradaInvalida("stream debe ser verdadero o falso.")
    return body

