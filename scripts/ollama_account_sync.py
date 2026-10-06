#!/usr/bin/env python3
"""Sincroniza cuentas Ollama aprobadas en cuentas.json y granja.env.

Uso:
  python scripts/ollama_account_sync.py --id acc9 --puerto 11442 \
      --home /home/agente/ollama_instances/acc9 --email user@mail.com
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent.parent
CUENTAS = ROOT / "cuentas.json"
GRANJA_ENV = ROOT / "granja.env"


def load_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return default
    except (OSError, json.JSONDecodeError):
        return default


def save_json(path: Path, data: Any) -> None:
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def sync_instances_env(total: int) -> None:
    if not GRANJA_ENV.exists():
        return
    text = GRANJA_ENV.read_text(encoding="utf-8")
    if re.search(r"^INSTANCIAS=\d+$", text, flags=re.M):
        text = re.sub(r"^INSTANCIAS=\d+$", f"INSTANCIAS={total}", text, flags=re.M)
    else:
        text = f"INSTANCIAS={total}\n" + text
    GRANJA_ENV.write_text(text, encoding="utf-8")


def upsert_ollama_account(account_id: str, puerto: int, home: str, email: str | None = None) -> None:
    data = load_json(CUENTAS, {})
    proveedores = data.setdefault("proveedores", {})
    ollama = proveedores.setdefault("ollama", {})
    cuentas = ollama.setdefault("cuentas", [])

    updated = False
    for item in cuentas:
        if str(item.get("id")) == account_id:
            item["puerto"] = puerto
            item["ollama_home"] = home
            if email:
                item["email"] = email
            updated = True
            break

    if not updated:
        nueva = {"id": account_id, "puerto": puerto, "ollama_home": home}
        if email:
            nueva["email"] = email
        cuentas.append(nueva)

    cuentas.sort(key=lambda x: (int(re.search(r"\d+", str(x.get("id", "0"))).group()) if re.search(r"\d+", str(x.get("id", "0"))) else 10**9, str(x.get("id", ""))))
    save_json(CUENTAS, data)
    sync_instances_env(len(cuentas))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--id", required=True)
    parser.add_argument("--puerto", required=True, type=int)
    parser.add_argument("--home", required=True)
    parser.add_argument("--email")
    args = parser.parse_args()

    upsert_ollama_account(args.id, args.puerto, args.home, args.email)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
