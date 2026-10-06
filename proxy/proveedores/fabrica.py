"""
Fábrica de proveedores — Instancia el proveedor correcto según el tipo.
Ollama, OpenRouter, NVIDIA y Cloudflare son proveedores backend.
OpenClaw y Hermes Agent son clientes que consumen el proxy.
"""
from proxy.proveedores.cloudflare import ProveedorCloudflare
from proxy.proveedores.cohere import ProveedorCohere
from proxy.proveedores.google import ProveedorGoogle
from proxy.proveedores.ollama import ProveedorOllama
from proxy.proveedores.openrouter import ProveedorOpenRouter
from proxy.proveedores.groq import ProveedorGroq
from proxy.proveedores.nvidia import ProveedorNvidia
from proxy.proveedores.siliconflow import ProveedorSiliconFlow
from proxy.proveedores.zhipu import ProveedorZhipu
from proxy.proveedores.tokenrouter import ProveedorTokenRouter
from proxy.proveedores.xkiro import ProveedorXKiro
from proxy.proveedores.tokenharbor import ProveedorTokenHarbor
from proxy.proveedores.apinex import ProveedorAPInex
from proxy.proveedores.openai import ProveedorOpenAI
from proxy.proveedores.openai_compatible import ProveedorOpenAICompatible
from proxy.proveedores.anthropic import ProveedorAnthropic

_MAPA_PROVEEDORES = {
    "ollama": ProveedorOllama,
    "cloudflare": ProveedorCloudflare,
    "cohere": ProveedorCohere,
    "google": ProveedorGoogle,
    "openrouter": ProveedorOpenRouter,
    "nvidia": ProveedorNvidia,
    "siliconflow": ProveedorSiliconFlow,
    "zhipu": ProveedorZhipu,
    "groq": ProveedorGroq,
    "tokenrouter": ProveedorTokenRouter,
    "xkiro": ProveedorXKiro,
    "tokenharbor": ProveedorTokenHarbor,
    "apinex": ProveedorAPInex,
    "openai": ProveedorOpenAI,
    "deepseek": ProveedorOpenAICompatible,
    "grok": ProveedorOpenAICompatible,
    "minimax": ProveedorOpenAICompatible,
    "alibaba": ProveedorOpenAICompatible,
    "cerebras": ProveedorOpenAICompatible,
    "mistral": ProveedorOpenAICompatible,
    "agnes": ProveedorOpenAICompatible,
    "aion": ProveedorOpenAICompatible,
    "airforce": ProveedorOpenAICompatible,
    "anyapi": ProveedorOpenAICompatible,
    "bazaarlink": ProveedorOpenAICompatible,
    "dreamprompting": ProveedorOpenAICompatible,
    "huggingface": ProveedorOpenAICompatible,
    "orcarouter": ProveedorOpenAICompatible,
    "requesty": ProveedorOpenAICompatible,
    "routeway": ProveedorOpenAICompatible,
    "sealion": ProveedorOpenAICompatible,
    "unorouter": ProveedorOpenAICompatible,
    "ollama_cloud_api": ProveedorOpenAICompatible,
    "anthropic": ProveedorAnthropic,
}


def crear_proveedor(cuenta, tipo):
    """Crea instancia del proveedor adecuado según el tipo."""
    clase = _MAPA_PROVEEDORES.get(tipo)
    if not clase:
        raise ValueError(f"Tipo de proveedor desconocido: '{tipo}'. "
                         f"Tipos válidos: {list(_MAPA_PROVEEDORES.keys())}")
    # El contrato histórico solo recibe la cuenta; los adaptadores genéricos
    # también necesitan conocer el tipo para resolver endpoint y variable.
    if clase is ProveedorOpenAICompatible:
        cuenta = dict(cuenta, proveedor=tipo)
    return clase(cuenta)


def tipos_disponibles():
    """Retorna lista de tipos de proveedor registrados."""
    return list(_MAPA_PROVEEDORES.keys())
