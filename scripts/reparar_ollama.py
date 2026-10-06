#!/usr/bin/env python3
"""Repara una cuenta Ollama existente sin crear otra identidad local."""
from __future__ import annotations

import argparse
import base64
import json
import socket
import subprocess
import sys
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CUENTAS_FILE = ROOT / "cuentas.json"

sys.path.insert(0, str(ROOT))
from proxy import rotador_cuentas  # noqa: E402
from scripts.agregar_ollama import (  # noqa: E402
    check_auth,
    copy_clipboard,
    generate_ssh_key,
    start_ollama_instance,
)


def load_accounts() -> list[dict]:
    try:
        data = json.loads(CUENTAS_FILE.read_text(encoding="utf-8"))
    except Exception:
        return []
    return data.get("proveedores", {}).get("ollama", {}).get("cuentas", [])


def account_by_id(accounts: list[dict], wanted: str) -> dict | None:
    wanted = wanted.strip().lower()
    for account in accounts:
        if str(account.get("id", "")).lower() == wanted:
            return account
    return None


def show_accounts(accounts: list[dict]) -> None:
    print("\nCUENTAS OLLAMA REGISTRADAS")
    print("-" * 92)
    for index, account in enumerate(accounts, 1):
        cid = str(account.get("id", "?"))
        email = str(account.get("email", "correo no registrado"))
        port = account.get("puerto", "?")
        home = str(account.get("ollama_home", "carpeta no registrada"))
        state = next((x for x in rotador_cuentas.obtener_estado_general() if x.get("id") == cid), {})
        print(f"  {index:2d}) {cid:8s} | {email:36.36s} | puerto {port} | {state.get('estado', 'activa')}")
        print(f"      Carpeta: {home}")
    print("-" * 92)


def build_connect_url(account: dict) -> tuple[str, str]:
    rel_home = str(account.get("ollama_home", "")).strip()
    inst_dir = Path(rel_home)
    if not inst_dir.is_absolute():
        inst_dir = ROOT / inst_dir
    key_path = inst_dir / ".ollama" / "id_ed25519"
    email = str(account.get("email", "")).strip()
    generate_ssh_key(key_path, email)
    pub_file = key_path.with_suffix(".pub")
    pub_text = pub_file.read_text(encoding="utf-8").strip() if pub_file.exists() else ""
    connect_url = "https://ollama.com/settings/keys"
    parts = pub_text.split()
    if len(parts) >= 2:
        raw_key = f"{parts[0]} {parts[1]}"
        b64_key = base64.b64encode(raw_key.encode("utf-8")).decode("utf-8").rstrip("=")
        connect_url = f"https://ollama.com/connect?name={socket.gethostname()}&key={b64_key}"
    return connect_url, pub_text


def repair(account: dict) -> int:
    cid = str(account.get("id", "")).strip()
    email = str(account.get("email", "")).strip()
    port = account.get("puerto")
    rel_home = str(account.get("ollama_home", "")).strip()
    if not cid or not email or not isinstance(port, int) or not rel_home:
        print("[ERROR] La cuenta no tiene ID, correo, puerto o carpeta completos.")
        return 1

    home = Path(rel_home)
    if not home.is_absolute():
        home = ROOT / home
    print(f"\nSe reparará: {cid}")
    print(f"  Correo:  {email}")
    print(f"  Puerto:  {port}")
    print(f"  Carpeta: {home}")
    print("\nSe conservará la clave local existente y no se creará otra cuenta.")
    if input("¿Continuar? [S/n]: ").strip().lower() not in ("", "s", "si", "sí", "y", "yes"):
        print("Cancelado.")
        return 0

    connect_url, pub_text = build_connect_url(account)
    copy_clipboard(pub_text or connect_url)
    started = start_ollama_instance(home, port)
    if not started:
        print("[AVISO] No se pudo iniciar Ollama automáticamente. Continúa si ya está funcionando.")

    print("\nENLACE DE AUTORIZACIÓN")
    print(connect_url)
    print("La clave/enlace se copió al portapapeles si el sistema lo permite.")
    if input("¿Abrir el enlace en el navegador? [S/n]: ").strip().lower() not in ("n", "no"):
        try:
            webbrowser.open(connect_url)
        except Exception:
            pass
    input("Autoriza el dispositivo en Ollama y presiona ENTER para comprobarlo...")

    result = check_auth(port, email)
    if result == "OK":
        rotador_cuentas.reactivar_cuenta(cid)
        print(f"\n[OK] {cid} volvió a quedar activa para {email}.")
        return 0
    if result.startswith("MISMATCH:"):
        real_email = result.split(":", 1)[1]
        print(f"[AVISO] Ollama informa otra cuenta: {real_email}.")
        if input("¿Guardar ese correo en esta misma cuenta? [s/N]: ").strip().lower() in ("s", "si", "sí", "y", "yes"):
            sync = ROOT / "scripts" / "ollama_account_sync.py"
            subprocess.run([sys.executable, str(sync), "--id", cid, "--puerto", str(port), "--home", rel_home, "--email", real_email], check=False)
            rotador_cuentas.reactivar_cuenta(cid)
            print(f"[OK] {cid} actualizada y reactivada.")
            return 0
    print(f"[AVISO] No se pudo confirmar la autorización ({result}). La cuenta no se marcó como reparada.")
    print(f"Revisa el registro: {home / 'logs' / 'ollama.log'}")
    return 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Repara una cuenta Ollama existente")
    parser.add_argument("--id", help="ID existente, por ejemplo acc7")
    args = parser.parse_args()
    rotador_cuentas.cargar_cuentas()
    accounts = load_accounts()
    if not accounts:
        print("[ERROR] No hay cuentas Ollama registradas en cuentas.json")
        return 1
    wanted = args.id
    if not wanted:
        show_accounts(accounts)
        wanted = input("Escribe el número o ID de la cuenta a reparar [0=salir]: ").strip()
        if wanted == "0" or not wanted:
            return 0
        if wanted.isdigit() and 1 <= int(wanted) <= len(accounts):
            account = accounts[int(wanted) - 1]
        else:
            account = account_by_id(accounts, wanted)
    else:
        account = account_by_id(accounts, wanted)
    if not account:
        print("[ERROR] No encontré esa cuenta.")
        return 1
    return repair(account)


if __name__ == "__main__":
    raise SystemExit(main())
