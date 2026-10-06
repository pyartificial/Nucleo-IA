"""Reglas finales que ningún fallback puede eludir."""
from __future__ import annotations

import os
from urllib.parse import urlsplit


CLOUD = {"groq", "tokenrouter", "xkiro", "tokenharbor", "cloudflare", "nvidia", "openrouter", "google", "cohere", "siliconflow", "zhipu"}


class EnvioNoPermitido(ValueError):
    pass


def _true(name: str) -> bool:
    return os.getenv(name, "false").strip().lower() in {"1", "true", "yes", "on", "si", "sí"}


def validar_envio(proveedor: str, modelo: str, url: str) -> None:
    if os.getenv("PROCESAMIENTO_PERMITIDO", "local_y_cloud").strip() == "solo_local" and proveedor in CLOUD:
        raise EnvioNoPermitido("La configuración permite únicamente procesamiento local.")
    if _true("SOLO_MODELOS_GRATUITOS"):
        gratuito_explicito = proveedor == "ollama" and not str(modelo).lower().endswith(":cloud")
        gratuito_explicito = gratuito_explicito or str(modelo).lower().endswith(":free")
        if not gratuito_explicito:
            raise EnvioNoPermitido("El modelo no tiene una marca gratuita verificable.")
    parsed = urlsplit(url)
    if proveedor == "ollama":
        if parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}:
            if not _true("PERMITIR_OLLAMA_REMOTO"):
                raise EnvioNoPermitido("Ollama remoto necesita habilitación explícita.")
    elif parsed.scheme != "https":
        raise EnvioNoPermitido("Los proveedores cloud requieren HTTPS.")

