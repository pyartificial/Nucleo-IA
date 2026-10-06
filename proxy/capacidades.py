"""Contratos y política común para capacidades multimedia."""
from dataclasses import dataclass
from typing import Any

from scripts.catalogo_capacidades import CAPACIDADES

ADAPTADORES_UPSTREAM = {
    # Estos proveedores tienen rutas concretas en proxy/servidor.py.
    # El resto puede aparecer como descubrimiento de catálogo, pero no se
    # debe seleccionar como destino automático de estas operaciones.
    "image_generation": frozenset({"siliconflow", "zhipu", "cloudflare"}),
    "video_generation_text": frozenset({"siliconflow", "zhipu"}),
    "video_generation_image": frozenset({"siliconflow", "zhipu"}),
}


def proveedor_con_adaptador(capacidad: str, proveedor: str) -> bool:
    capacidad = str(capacidad)
    proveedor = str(proveedor).strip().lower()
    return proveedor in ADAPTADORES_UPSTREAM.get(capacidad, frozenset())



@dataclass(frozen=True)
class ResultadoCapacidad:
    capacidad: str
    proveedor: str
    modelo: str
    estado: str
    simulada: bool = False
    datos: dict[str, Any] | None = None


def candidato_permitido(cuenta: dict, capacidad: str, pago: bool = False) -> bool:
    """Aplica el filtro local antes de llamar a un adaptador."""
    if not cuenta or cuenta.get('habilitado') is False:
        return False
    capacidades = cuenta.get('capacidades_habilitadas')
    if isinstance(capacidades, list) and capacidad not in capacidades:
        return False
    if pago and cuenta.get('uso_pago') is not True:
        return False
    return True


def capacidad_video_para_body(body: dict) -> str:
    """Distingue texto-a-video de imagen-a-video por la entrada recibida."""
    campos_imagen = ('image', 'image_url', 'first_frame', 'first_frame_image', 'input_image')
    return 'video_generation_image' if any(body.get(key) for key in campos_imagen) else 'video_generation_text'
