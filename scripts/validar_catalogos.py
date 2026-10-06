#!/usr/bin/env python3
"""Valida si las instantáneas de rankings contienen evidencia suficiente.

Una lista de modelos sin fecha y fuente sirve para diagnóstico, pero no para
habilitar automáticamente capacidades ni afirmar que una ruta es gratuita.
"""
from __future__ import annotations

import json
from pathlib import Path


RAIZ = Path(__file__).resolve().parents[1]
ESTADO = RAIZ / "state"


def validar(ruta: Path) -> tuple[bool, list[str]]:
    problemas: list[str] = []
    try:
        datos = json.loads(ruta.read_text(encoding="utf-8"))
    except Exception as exc:
        return False, [f"JSON inválido: {exc}"]
    if not isinstance(datos, dict):
        return False, ["la raíz no es un objeto"]
    if not any(datos.get(k) for k in ("fecha", "timestamp", "generado_en", "updated_at")):
        problemas.append("falta fecha de consulta")
    if not any(datos.get(k) for k in ("fuente", "source", "url", "endpoint")):
        problemas.append("falta fuente o endpoint")
    filas = datos.get("ranking") or datos.get("modelos") or datos.get("data")
    if not isinstance(filas, list):
        problemas.append("falta lista de modelos")
    return not problemas, problemas


def main() -> int:
    archivos = sorted(ESTADO.glob("ranking_*.json"))
    validos = 0
    for ruta in archivos:
        ok, problemas = validar(ruta)
        if ok:
            validos += 1
            print(f"OK       {ruta.name}")
        else:
            print(f"OBSOLETO {ruta.name}: {'; '.join(problemas)}")
    print(f"Resumen: {validos}/{len(archivos)} contienen metadatos suficientes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
