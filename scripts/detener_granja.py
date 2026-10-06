#!/usr/bin/env python3
"""
detener_granja.py — Detiene limpiamente el proxy y las instancias de Ollama (Multiplataforma).
"""
import os
import sys
import json
import subprocess
import signal
from pathlib import Path

if hasattr(sys.stdout, 'reconfigure'):
    try: sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception: pass
if hasattr(sys.stderr, 'reconfigure'):
    try: sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception: pass

ROOT = Path(__file__).resolve().parent.parent
RUNTIME = ROOT / "state" / "proxy_runtime.json"


def get_proxy_port() -> int:
    for filename in ('.env', 'granja.env'):
        path = ROOT / filename
        if path.exists():
            for line in path.read_text(encoding='utf-8', errors='ignore').splitlines():
                if line.startswith('PROXY_PORT='):
                    try:
                        return int(line.split('=', 1)[1].strip().strip('"').strip("'"))
                    except Exception:
                        pass
    return 8080


def detener_todo():
    print("=" * 60)
    print("  🛑 DETENIENDO NÚCLEO IA (Proxy y Procesos)")
    print("=" * 60)

    port = get_proxy_port()
    print(f"  [1] Deteniendo Proxy en puerto {port}...")

    try:
        runtime = json.loads(RUNTIME.read_text(encoding="utf-8"))
        pid = int(runtime.get("pid", 0))
        if runtime.get("root") != str(ROOT) or pid <= 0 or pid == os.getpid():
            raise ValueError("identidad inválida")
        if sys.platform.startswith("win"):
            subprocess.run(["taskkill", "/PID", str(pid)], check=False,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        else:
            proc_cwd = Path(f"/proc/{pid}/cwd").resolve()
            cmdline = Path(f"/proc/{pid}/cmdline").read_bytes().replace(b"\0", b" ")
            if proc_cwd != ROOT or b"proxy.servidor" not in cmdline:
                raise ValueError("el proceso no pertenece a esta copia")
            os.kill(pid, signal.SIGTERM)
        RUNTIME.unlink(missing_ok=True)
        print(f"  [OK] Terminado el proxy propio (PID {pid})")
    except FileNotFoundError:
        print("  [INFO] Esta copia no tiene un proxy registrado en ejecución.")
    except (ValueError, OSError, json.JSONDecodeError) as exc:
        print(f"  [AVISO] No se detuvo el proceso del puerto {port}: {exc}")

    print("  ✅ Se detuvieron los procesos propios que estaban registrados.\n")


if __name__ == "__main__":
    detener_todo()
