"""
Clase base abstracta para proveedores backend de IA.
Proveedores = Ollama, OpenRouter (los que ejecutan los modelos).
Clientes = OpenClaw, Hermes Agent (los que consumen la API del proxy).
"""
from abc import ABC, abstractmethod


class ProveedorBase(ABC):
    """Interfaz comun para proveedores backend."""

    def __init__(self, cuenta):
        self.cuenta = cuenta
        self.id_cuenta = cuenta["id"]

    @abstractmethod
    def construir_url(self):
        """Retorna la URL del endpoint de chat completions."""
        pass

    @abstractmethod
    def construir_headers(self):
        """Retorna los headers necesarios para la peticion."""
        pass

    def preparar_body(self, body, modelo):
        """Prepara el cuerpo de la peticion."""
        body_copia = dict(body)
        body_copia["model"] = modelo
        return body_copia

    def identificar(self):
        """Retorna cadena legible que identifica este proveedor + cuenta."""
        return f"{self.id_cuenta}"
