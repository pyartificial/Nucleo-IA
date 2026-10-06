#!/usr/bin/env python3
"""
agregar_ollama.py — Asistente Multiplataforma para Vincular Cuentas Ollama Cloud.
Funciona de forma nativa en Windows y Linux.
"""
import os
import sys
import re
import json
import base64
import socket
import shutil
import subprocess
import urllib.request
import urllib.error
import webbrowser
from pathlib import Path

if hasattr(sys.stdout, 'reconfigure'):
    try: sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception: pass
if hasattr(sys.stderr, 'reconfigure'):
    try: sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception: pass

ROOT = Path(__file__).resolve().parent.parent
CUENTAS_FILE = ROOT / "cuentas.json"
GRANJA_ENV = ROOT / "granja.env"


def copy_clipboard(text: str):
    if not text:
        return
    if sys.platform.startswith("win"):
        try:
            subprocess.run(["powershell", "-NoProfile", "-Command", "Set-Clipboard", "-Value", f"'{text}'"], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return
        except Exception:
            pass
        try:
            proc = subprocess.Popen(["clip"], stdin=subprocess.PIPE, shell=True)
            proc.communicate(text.encode("utf-8"))
            return
        except Exception:
            pass
    else:
        for cmd in ["wl-copy", "xclip -selection clipboard", "xsel --clipboard"]:
            if shutil.which(cmd.split()[0]):
                try:
                    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, shell=True)
                    proc.communicate(text.encode("utf-8"))
                    return
                except Exception:
                    pass


def get_next_instance_info() -> tuple[str, int]:
    cuentas = []
    if CUENTAS_FILE.exists():
        try:
            data = json.loads(CUENTAS_FILE.read_text(encoding="utf-8"))
            cuentas = data.get("proveedores", {}).get("ollama", {}).get("cuentas", [])
        except Exception:
            pass

    max_num = 0
    max_port = 11433
    for c in cuentas:
        cid = str(c.get("id", ""))
        m = re.search(r"\d+", cid)
        if m:
            num = int(m.group())
            if num > max_num:
                max_num = num
        port = c.get("puerto")
        if isinstance(port, int) and port > max_port:
            max_port = port

    next_num = max_num + 1
    next_id = f"acc{next_num}"
    next_port = max_port + 1 if max_port >= 11434 else 11434
    return next_id, next_port


def generate_ssh_key(key_path: Path, email: str) -> bool:
    key_path.parent.mkdir(parents=True, exist_ok=True)
    if key_path.exists():
        return True

    # Buscar ssh-keygen en el sistema
    ssh_keygen = shutil.which("ssh-keygen")
    if not ssh_keygen and sys.platform.startswith("win"):
        win_ssh = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32" / "OpenSSH" / "ssh-keygen.exe"
        if win_ssh.exists():
            ssh_keygen = str(win_ssh)

    if ssh_keygen:
        cmd = [ssh_keygen, "-t", "ed25519", "-N", "", "-f", str(key_path), "-C", email]
        res = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return res.returncode == 0

    return False


def start_ollama_instance(inst_dir: Path, port: int) -> bool:
    ollama_bin = shutil.which("ollama")
    if not ollama_bin:
        return False

    # No crear dos servidores para la misma cuenta si ya está escuchando.
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=.25):
            return True
    except OSError:
        pass

    env = os.environ.copy()
    env["HOME"] = str(inst_dir)
    env["USERPROFILE"] = str(inst_dir)
    env["OLLAMA_HOST"] = f"127.0.0.1:{port}"
    env["OLLAMA_CONTEXT_LENGTH"] = "131072"
    env["OLLAMA_KEEP_ALIVE"] = "-1"

    logs_dir = inst_dir / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    log_file = logs_dir / "ollama.log"

    creationflags = 0
    if sys.platform.startswith("win"):
        creationflags = subprocess.CREATE_NEW_PROCESS_GROUP | 0x08000000  # CREATE_NO_WINDOW

    options = {"creationflags": creationflags} if sys.platform.startswith("win") else {"start_new_session": True}
    with open(log_file, "a", encoding="utf-8") as out:
        process = subprocess.Popen([ollama_bin, "serve"], env=env, stdin=subprocess.DEVNULL,
                                   stdout=out, stderr=out, **options)
    # Guardamos el PID para que el panel pueda identificar esta instancia sin
    # confundirla con otro Ollama que el usuario tenga abierto.
    (logs_dir / "ollama.pid").write_text(str(process.pid), encoding="utf-8")
    return True
    return True


def check_auth(port: int, email: str) -> str:
    url = f"http://127.0.0.1:{port}/api/me"
    req = urllib.request.Request(url, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=8) as resp:
            if resp.status == 200:
                data = json.loads(resp.read().decode("utf-8"))
                actual_email = data.get("email", "").strip().lower()
                if actual_email and actual_email != email.lower().strip():
                    return f"MISMATCH:{actual_email}"
                return "OK"
    except urllib.error.HTTPError as e:
        if e.code != 401:
            return "OK"
        return f"HTTP_{e.code}"
    except Exception as e:
        return f"ERR:{e}"
    return "PENDING"


def main(abrir_navegador=True, email_inicial=''):
    print("=" * 70)
    print("  🌾 NÚCLEO IA — Asistente de Cuentas Ollama Cloud (Multiplataforma)")
    print("=" * 70)
    print("  Este asistente te permite vincular cuentas de Ollama Cloud.")
    print("  Genera el enlace directo de vinculación oficial y lo abre en tu navegador.")
    print("=" * 70)

    while True:
        acc_id, port = get_next_instance_info()
        rel_home = f"ollama_instances/{acc_id}"
        abs_home = ROOT / rel_home

        print(f"\n  [+] Próxima instancia disponible: {acc_id} (Puerto: {port})")
        sugerencia = str(email_inicial or '').strip()
        prompt = f"  📧 Email de la cuenta Ollama Cloud [{sugerencia or '0=cancelar'}]: "
        email = input(prompt).strip() or sugerencia
        email_inicial = ''
        if not email or email == "0":
            print("  Operación finalizada.")
            break

        key_path = abs_home / ".ollama" / "id_ed25519"
        generate_ssh_key(key_path, email)

        pub_file = abs_home / ".ollama" / "id_ed25519.pub"
        connect_url = "https://ollama.com/settings/keys"
        pub_text = ""

        if pub_file.exists():
            pub_text = pub_file.read_text(encoding="utf-8").strip()
            parts = pub_text.split()
            if len(parts) >= 2:
                raw_key = f"{parts[0]} {parts[1]}"
                b64_key = base64.b64encode(raw_key.encode("utf-8")).decode("utf-8").rstrip("=")
                host = socket.gethostname()
                connect_url = f"https://ollama.com/connect?name={host}&key={b64_key}"

        if abrir_navegador:
            copy_clipboard(pub_text or connect_url)

        # Iniciar instancia Ollama si es posible
        start_ollama_instance(abs_home, port)

        # Sincronizar en cuentas.json y granja.env
        sync_script = ROOT / "scripts" / "ollama_account_sync.py"
        if sync_script.exists():
            subprocess.run([sys.executable, str(sync_script), "--id", acc_id, "--puerto", str(port), "--home", rel_home, "--email", email])

        print("\n" + "=" * 70)
        print(f"  ✅ INSTANCIA PREPARADA: {acc_id} (Puerto local: {port})")
        print(f"  📧 Cuenta: {email}")
        print("=" * 70)
        print(f"\n  🔗 ENLACE DE VINCULACIÓN OFICIAL:")
        print(f"     👉 {connect_url}")
        if abrir_navegador:
            print("     (Clave copiada automáticamente al portapapeles)")
        else:
            print("     Copiá este enlace y abrilo en el navegador de otra computadora.")

        abrir = '1'
        if abrir_navegador:
            print("\n  ¿Deseas abrir el enlace en tu navegador?")
            print("    [ ENTER ] -> Abrir en navegador predeterminado")
            print("    [   1   ] -> No abrir (abriré el enlace manualmente)")
            abrir = input("    Opción [ENTER]: ").strip()
        if abrir != "1":
            try:
                webbrowser.open(connect_url)
            except Exception:
                pass

        print("\n  Asegúrate de tocar 'Authorize Device' en la web de Ollama.")
        input("  Presiona [ENTER] cuando hayas autorizado el dispositivo en el navegador...")

        res = check_auth(port, email)
        if res == "OK":
            print(f"\n  🎉 ¡Éxito! Instancia {acc_id} vinculada y verificada correctamente.")
        elif res.startswith("MISMATCH:"):
            real_email = res.split(":", 1)[1]
            print(f"\n  ℹ️ Autorizada con la cuenta: {real_email}. Sincronizando...")
            subprocess.run([sys.executable, str(sync_script), "--id", acc_id, "--puerto", str(port), "--home", rel_home, "--email", real_email])
            print(f"  🎉 ¡Éxito! Instancia {acc_id} guardada con {real_email}.")
        else:
            print(f"\n  ℹ️ Instancia registrada ({res}). Se verificará automáticamente al iniciar la granja.")

        otra = input("\n¿Deseas vincular otra cuenta de Ollama Cloud? (s/N): ").strip().lower()
        if otra not in ("s", "si", "y", "yes"):
            break


if __name__ == "__main__":
    main()
