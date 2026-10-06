"""Adaptador para TokenRouter (https://www.tokenrouter.com).

Utiliza la API compatible con OpenAI para enrutar consultas de chat a modelos
a través del endpoint de TokenRouter.
"""
from __future__ import annotations

import os
from typing import Any, Dict
from .base import ProveedorBase


class ProveedorTokenRouter(ProveedorBase):
    """Adaptador de proveedor para TokenRouter."""

    BASE_URL = "https://api.tokenrouter.com/v1"

    def construir_url(self, endpoint: str = "chat/completions") -> str:
        """Construye la URL completa del endpoint."""
        url_base = (self.cuenta.get("url_base") or "").rstrip("/")
        if not url_base:
            url_base = self.BASE_URL
        endpoint = endpoint.lstrip("/")
        return f"{url_base}/{endpoint}"

    def construir_headers(self) -> Dict[str, str]:
        """Construye los headers con la API Key y metadatos."""
        api_key = self._resolver_api_key()
        headers: Dict[str, str] = {
            "Content-Type": "application/json",
            "User-Agent": "NucleoIA/1.0",
            "X-Title": "Nucleo IA",
        }
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        return headers

    def preparar_body(self, body: Dict[str, Any], modelo: str) -> Dict[str, Any]:
        """Ajusta el body de la petición para TokenRouter."""
        nuevo_body = dict(body)
        nuevo_body["model"] = modelo
        return nuevo_body

    def identificar(self) -> str:
        """Identificador legible de la cuenta."""
        return f"TokenRouter ({self.cuenta.get('id', 'sin-id')})"

    def _resolver_api_key(self) -> str:
        """Resuelve la API Key desde la cuenta o variables de entorno."""
        clave = self.cuenta.get("api_key", "")
        if clave and not clave.startswith("${"):
            return clave

        ref = self.cuenta.get("api_key", "")
        if ref.startswith("${") and ref.endswith("}"):
            var_name = ref[2:-1]
            val = os.getenv(var_name, "")
            if val:
                return val

        cuenta_id = self.cuenta.get("id", "")
        if cuenta_id:
            val = os.getenv(f"TOKENROUTER_API_KEY_{cuenta_id.upper()}", "")
            if val:
                return val

        return os.getenv("TOKENROUTER_API_KEY", "")
