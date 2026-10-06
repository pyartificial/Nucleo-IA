#!/usr/bin/env python3
"""Respalda o restaura datos personales sin sesiones temporales."""
from __future__ import annotations
import argparse
import json
import os
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ARCHIVOS = ("cuentas.json", ".env", "granja.env")


def _privado(path: Path, directory: bool = False):
    if os.name != "nt":
        path.chmod(0o700 if directory else 0o600)


def crear(destino: Path):
    destino = destino.expanduser().resolve()
    if destino.exists() and any(destino.iterdir()):
        raise RuntimeError("El destino del respaldo debe estar vacío.")
    destino.mkdir(parents=True, exist_ok=True)
    _privado(destino, True)
    copiados = []
    for nombre in ARCHIVOS:
        origen = ROOT / nombre
        if origen.is_file():
            shutil.copy2(origen, destino / nombre)
            _privado(destino / nombre)
            copiados.append(nombre)
    manifiesto = {"formato": 1, "creado": datetime.now(timezone.utc).isoformat(), "archivos": copiados}
    (destino / "respaldo.json").write_text(json.dumps(manifiesto, indent=2) + "\n", encoding="utf-8")
    _privado(destino / "respaldo.json")
    print(f"[OK] Respaldo personal creado en {destino}")


def restaurar(origen: Path):
    origen = origen.expanduser().resolve()
    manifiesto = json.loads((origen / "respaldo.json").read_text(encoding="utf-8"))
    if manifiesto.get("formato") != 1 or not isinstance(manifiesto.get("archivos"), list):
        raise RuntimeError("El respaldo no tiene un formato reconocido.")
    archivos = [n for n in manifiesto["archivos"] if n in ARCHIVOS and (origen / n).is_file()]
    if "cuentas.json" in archivos:
        cuentas = json.loads((origen / "cuentas.json").read_text(encoding="utf-8"))
        if not isinstance(cuentas.get("proveedores"), dict) or not isinstance(cuentas.get("pozo_emails", []), list):
            raise RuntimeError("El archivo de cuentas del respaldo no es válido.")
    with tempfile.TemporaryDirectory(prefix="nucleo-restauracion-") as temporal:
        anterior = Path(temporal)
        for nombre in archivos:
            if (ROOT / nombre).exists():
                shutil.copy2(ROOT / nombre, anterior / nombre)
        instalados = []
        try:
            for nombre in archivos:
                tmp = ROOT / f".{nombre.lstrip('.')}.restaurando"
                shutil.copy2(origen / nombre, tmp)
                _privado(tmp)
                os.replace(tmp, ROOT / nombre)
                instalados.append(nombre)
        except Exception:
            for nombre in instalados:
                if (anterior / nombre).exists():
                    shutil.copy2(anterior / nombre, ROOT / nombre)
            raise
    print(f"[OK] Datos personales restaurados: {', '.join(archivos)}")
    print("Reiniciá Núcleo IA. Si venció una autorización, repará solo la cuenta indicada por su correo.")


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="accion", required=True)
    sub.add_parser("crear").add_argument("destino", type=Path)
    sub.add_parser("restaurar").add_argument("origen", type=Path)
    args = parser.parse_args()
    crear(args.destino) if args.accion == "crear" else restaurar(args.origen)


if __name__ == "__main__":
    main()
