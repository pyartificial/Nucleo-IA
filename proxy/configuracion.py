"""Carga única y predecible de la configuración local de Núcleo IA."""
from __future__ import annotations

import os
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
_external_names = set(os.environ)
_managed_names: set[str] = set()


def _leer_env(path: Path) -> dict[str, str]:
    valores: dict[str, str] = {}
    try:
        lineas = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return valores
    for raw in lineas:
        linea = raw.strip()
        if not linea or linea.startswith("#") or "=" not in linea:
            continue
        if linea.startswith("export "):
            linea = linea[7:].lstrip()
        nombre, valor = linea.split("=", 1)
        nombre = nombre.strip()
        valor = valor.strip().strip('"').strip("'")
        if nombre:
            valores[nombre] = os.path.expandvars(valor)
    return valores


def cargar_configuracion() -> None:
    """Carga `.env` como fuente principal y `granja.env` como legado.

    Las variables proporcionadas por el proceso siempre tienen prioridad.
    """
    combinada = _leer_env(ROOT / "granja.env")
    combinada.update(_leer_env(ROOT / ".env"))
    for nombre, valor in combinada.items():
        if nombre not in _external_names:
            os.environ[nombre] = valor
            _managed_names.add(nombre)

    # Compatibilidad temporal con el nombre usado en configuraciones antiguas.
    if "MODO_ROTACION" not in os.environ and "ROTACION_MODO" in os.environ:
        os.environ["MODO_ROTACION"] = os.environ["ROTACION_MODO"]


def recargar_configuracion() -> None:
    """Sustituye valores provenientes de archivos y elimina los que se quitaron."""
    combinada = _leer_env(ROOT / "granja.env")
    combinada.update(_leer_env(ROOT / ".env"))
    for nombre in _managed_names - set(combinada):
        os.environ.pop(nombre, None)
    for nombre, valor in combinada.items():
        if nombre not in _external_names:
            os.environ[nombre] = valor
            _managed_names.add(nombre)
