"""
Proveedor Ollama — Instancias locales con puertos rotativos.
"""
from proxy.proveedores.base import ProveedorBase


class ProveedorOllama(ProveedorBase):
    """Conecta con instancias locales de Ollama vía HTTP."""

    def __init__(self, cuenta):
        super().__init__(cuenta)
        self.puerto = cuenta["puerto"]
        self.host = cuenta.get("host", "127.0.0.1")

    def construir_url(self):
        return f"http://{self.host}:{self.puerto}/v1/chat/completions"

    def construir_headers(self):
        return {"Content-Type": "application/json"}
