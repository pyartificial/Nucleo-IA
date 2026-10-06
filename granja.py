#!/usr/bin/env python3
"""
🌾 Núcleo IA / La Granja de IA — Gestor Unificado Multiplataforma (Windows / Linux / macOS)

Uso:
  python granja.py install          → Instala entorno venv y dependencias
  python granja.py start            → Inicia el servidor proxy central
  python granja.py stop             → Detiene el proxy y procesos asociados
  python granja.py restart          → Reinicia el proxy
  python granja.py status           → Consulta el estado del proxy y de los proveedores
  python granja.py models           → Consulta la lista de modelos OpenAI (/v1/models)
  python granja.py rank             → Recalcula y consolida todos los rankings
  python granja.py test             → Ejecuta la suite de pruebas de estabilidad
  python granja.py config           → Asistente interactivo de configuración
  python granja.py add-key          → Asistente para agregar API Keys (OpenRouter, NVIDIA, etc.)
  python granja.py services         → Abre Mis servicios en el navegador (Windows y Linux)
  python granja.py add-ollama       → Asistente para vincular cuentas de Ollama Cloud
  python granja.py adjust-ranking   → Editor visual interactivo de posiciones en el ranking
  python granja.py sync-exportable  → Sincroniza y sanitiza la versión exportable para compartir
  python granja.py backup CARPETA   → Respalda cuentas, correos y configuración personal
  python granja.py restore CARPETA  → Restaura un respaldo personal validado
"""
import os
import sys
import json
import shutil
import subprocess
import urllib.request
import urllib.error
from pathlib import Path

if hasattr(sys.stdout, 'reconfigure'):
    try: sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception: pass
if hasattr(sys.stderr, 'reconfigure'):
    try: sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception: pass

ROOT = Path(__file__).resolve().parent
IS_WIN = sys.platform.startswith("win")
VENV_DIR = ROOT / "venv"


def _read_config_value(name: str) -> str:
    value = ""
    for env_path in (ROOT / "granja.env", ROOT / ".env"):
        if not env_path.exists():
            continue
        for line in env_path.read_text(encoding="utf-8", errors="ignore").splitlines():
            raw = line.strip()
            if raw.startswith(name + "="):
                value = raw.split("=", 1)[1].strip().strip('"').strip("'")
    return value


def get_python_bin() -> str:
    if IS_WIN:
        candidate = VENV_DIR / "Scripts" / "python.exe"
    else:
        candidate = VENV_DIR / "bin" / "python"

    if candidate.exists():
        try:
            res = subprocess.run([str(candidate), "--version"], capture_output=True, check=False)
            if res.returncode == 0:
                return str(candidate)
        except Exception:
            pass

    if sys.executable:
        return sys.executable

    py = shutil.which("python3") or shutil.which("python")
    return py or "python"


def log_info(msg: str):
    print(f" [INFO] {msg}")


def log_ok(msg: str):
    print(f" [  OK] {msg}")


def log_err(msg: str):
    print(f" [FAIL] {msg}")


def cmd_install():
    log_info(f"Sistema operativo detectado: {sys.platform}")
    if not VENV_DIR.exists():
        log_info("Creando entorno virtual Python (venv)...")
        subprocess.check_call([sys.executable, "-m", "venv", str(VENV_DIR)])
        log_ok(f"Entorno virtual creado en: {VENV_DIR}")

    py_bin = get_python_bin()
    log_info("Instalando dependencias desde requirements.txt...")
    subprocess.check_call([py_bin, "-m", "pip", "install", "--upgrade", "pip", "-q"])
    requirements = ROOT / "requirements.txt"
    if not requirements.exists():
        raise FileNotFoundError(f"No se encontró {requirements}")
    subprocess.check_call([py_bin, "-m", "pip", "install", "-r", str(requirements), "-q"])

    # Crear carpetas requeridas
    (ROOT / "state" / "route_rankings").mkdir(parents=True, exist_ok=True)
    (ROOT / "ollama_instances").mkdir(parents=True, exist_ok=True)

    # Crear .env si no existe
    env_file = ROOT / ".env"
    if not env_file.exists() and (ROOT / ".env.example").exists():
        shutil.copy2(ROOT / ".env.example", env_file)
        log_ok("Creado archivo .env inicial desde .env.example")

    log_ok("Instalación completada exitosamente.")


def cmd_start():
    py_bin = get_python_bin()
    if not (VENV_DIR / ("Scripts" if IS_WIN else "bin") / ("python.exe" if IS_WIN else "python")).exists():
        log_info("Entorno venv no encontrado. Ejecutando instalación inicial...")
        cmd_install()
        py_bin = get_python_bin()

    port = 8080
    host = "127.0.0.1"
    for env_path in [ROOT / ".env", ROOT / "granja.env"]:
        if env_path.exists():
            for line in env_path.read_text(encoding="utf-8", errors="ignore").splitlines():
                if line.startswith("PROXY_PORT="):
                    try: port = int(line.split("=", 1)[1].strip().strip('"').strip("'"))
                    except Exception: pass
                elif line.startswith("PROXY_HOST="):
                    host = line.split("=", 1)[1].strip().strip('"').strip("'")

    log_info(f"Arrancando Núcleo IA en http://{host}:{port}...")

    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT)
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"

    try:
        subprocess.run([py_bin, "-m", "proxy.servidor"], cwd=str(ROOT), env=env)
    except KeyboardInterrupt:
        print("\n[INFO] Servidor detenido por el usuario.")


def cmd_stop():
    py_bin = get_python_bin()
    stop_script = ROOT / "scripts" / "detener_granja.py"
    if stop_script.exists():
        subprocess.run([py_bin, str(stop_script)], cwd=str(ROOT))
    else:
        log_err("No se encontró scripts/detener_granja.py")


def cmd_status():
    port = 8080
    for env_path in [ROOT / ".env", ROOT / "granja.env"]:
        if env_path.exists():
            for line in env_path.read_text(encoding="utf-8", errors="ignore").splitlines():
                if line.startswith("PROXY_PORT="):
                    try: port = int(line.split("=", 1)[1].strip().strip('"').strip("'"))
                    except Exception: pass

    url = f"http://127.0.0.1:{port}/status"
    try:
        headers = {"User-Agent": "granja-cli"}
        admin_key = _read_config_value("NUCLEO_ADMIN_KEY") or _read_config_value("NUCLEO_API_KEY")
        if admin_key:
            headers["Authorization"] = "Bearer " + admin_key
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode())
            print(json.dumps(data, indent=2, ensure_ascii=False))
            log_ok("Servidor responde correctamente.")
    except Exception as e:
        log_err(f"No se pudo conectar a {url}: {e}")


def cmd_models():
    port = 8080
    for env_path in [ROOT / ".env", ROOT / "granja.env"]:
        if env_path.exists():
            for line in env_path.read_text(encoding="utf-8", errors="ignore").splitlines():
                if line.startswith("PROXY_PORT="):
                    try: port = int(line.split("=", 1)[1].strip().strip('"').strip("'"))
                    except Exception: pass

    url = f"http://127.0.0.1:{port}/v1/models"
    try:
        headers = {"User-Agent": "granja-cli"}
        api_key = _read_config_value("NUCLEO_API_KEY")
        if api_key:
            headers["Authorization"] = "Bearer " + api_key
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode())
            models = data.get("data", [])
            log_ok(f"Total modelos expuestos: {len(models)}")
            for m in models:
                mid = m.get("id")
                owner = m.get("owned_by", "unknown")
                print(f"  • {mid:45s} (proveedor: {owner})")
    except Exception as e:
        log_err(f"No se pudo consultar {url}: {e}")


def cmd_rank():
    py_bin = get_python_bin()
    log_info("Actualizando proveedores y recalculando el ranking global...")
    script = ROOT / "scripts" / "ranking_global.py"
    if not script.exists():
        log_err(f"No se encontró {script}")
        return
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT)
    env["PYTHONIOENCODING"] = "utf-8"
    proc = subprocess.run([py_bin, str(script)], cwd=str(ROOT), env=env)
    if proc.returncode == 0:
        log_ok("Rankings recalculados y consolidados exitosamente.")
    else:
        log_err(f"La actualización terminó con código {proc.returncode}.")


def cmd_test():
    py_bin = get_python_bin()
    log_info("Ejecutando las pruebas locales de Núcleo IA...")
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT)
    resultado = subprocess.run(
        [py_bin, "-m", "unittest", "discover", "-s", "tests", "-v"],
        cwd=str(ROOT), env=env,
    )
    return resultado.returncode


def cmd_config():
    py_bin = get_python_bin()
    cfg_script = ROOT / "scripts" / "configurar_granja.py"
    if cfg_script.exists():
        subprocess.run([py_bin, str(cfg_script)], cwd=str(ROOT))
    else:
        log_err("No se encontró scripts/configurar_granja.py")


def cmd_add_key():
    print("=" * 60)
    print("  🔑 AGREGAR API KEY DE PROVEEDOR")
    print("=" * 60)
    print("  1) OpenRouter")
    print("  2) NVIDIA NIM")
    print("  3) Cloudflare Workers AI")
    print("  4) Google Gemini")
    print("  5) Cohere")
    print("  6) SiliconFlow (Free Tier)")
    print("  7) Zhipu AI (BigModel)")
    print("  8) Groq (LPU Speed)")
    print("  9) TokenRouter (OpenAI-compatible Gateway)")
    print(" 10) xKiro (modelos con cuota Free)")
    print(" 11) Token Harbor (rutas :free; pueden retener contenido)")
    print("  0) Cancelar")
    print("=" * 60)

    opc = input("  Selecciona proveedor [1]: ").strip() or "1"
    gestor = ROOT / "scripts" / "gestor_cuentas.py"
    py_bin = get_python_bin()

    if opc == "1":
        acc_id = input("  ID de cuenta [openrouter_1]: ").strip() or "openrouter_1"
        key = input(f"  API Key de OpenRouter ({acc_id}): ").strip()
        if key:
            url_app = input("  URL de tu aplicación (opcional): ").strip()
            subprocess.run([py_bin, str(gestor), "openrouter", acc_id, key, url_app], cwd=str(ROOT))
            log_ok(f"Guardada clave de OpenRouter: {acc_id}")
    elif opc == "2":
        acc_id = input("  ID de cuenta [nvidia_1]: ").strip() or "nvidia_1"
        key = input(f"  API Key de NVIDIA NIM ({acc_id}): ").strip()
        if key:
            subprocess.run([py_bin, str(gestor), "nvidia", acc_id, key], cwd=str(ROOT))
            log_ok(f"Guardada clave de NVIDIA: {acc_id}")
    elif opc == "3":
        acc_id = input("  Account ID de Cloudflare: ").strip()
        token = input("  API Token de Cloudflare Workers AI: ").strip()
        if acc_id and token:
            subprocess.run([py_bin, str(gestor), "cloudflare", acc_id, token], cwd=str(ROOT))
            log_ok(f"Guardadas credenciales de Cloudflare: {acc_id}")
    elif opc == "4":
        acc_id = input("  ID de cuenta [google_1]: ").strip() or "google_1"
        key = input("  API Key de Google Gemini: ").strip()
        if key:
            subprocess.run([py_bin, str(gestor), "google", acc_id, key], cwd=str(ROOT))
            log_ok(f"Guardada clave de Google Gemini: {acc_id}")
    elif opc == "5":
        acc_id = input("  ID de cuenta [cohere_1]: ").strip() or "cohere_1"
        key = input("  API Key de Cohere: ").strip()
        if key:
            subprocess.run([py_bin, str(gestor), "cohere", acc_id, key], cwd=str(ROOT))
            log_ok(f"Guardada clave de Cohere: {acc_id}")
    elif opc == "6":
        acc_id = input("  ID de cuenta [siliconflow_1]: ").strip() or "siliconflow_1"
        key = input("  API Key de SiliconFlow: ").strip()
        if key:
            subprocess.run([py_bin, str(gestor), "siliconflow", acc_id, key], cwd=str(ROOT))
            log_ok(f"Guardada clave de SiliconFlow: {acc_id}")
    elif opc == "7":
        acc_id = input("  ID de cuenta [zhipu_1]: ").strip() or "zhipu_1"
        key = input("  API Key de Zhipu AI: ").strip()
        if key:
            subprocess.run([py_bin, str(gestor), "zhipu", acc_id, key], cwd=str(ROOT))
            log_ok(f"Guardada clave de Zhipu AI: {acc_id}")
    elif opc == "8":
        acc_id = input("  ID de cuenta [groq_1]: ").strip() or "groq_1"
        key = input("  API Key de Groq (gsk_...): ").strip()
        if key:
            subprocess.run([py_bin, str(gestor), "groq", acc_id, key], cwd=str(ROOT))
            log_ok(f"Guardada clave de Groq: {acc_id}")
    elif opc == "9":
        acc_id = input("  ID de cuenta [tokenrouter_1]: ").strip() or "tokenrouter_1"
        key = input("  API Key de TokenRouter: ").strip()
        if key:
            subprocess.run([py_bin, str(gestor), "tokenrouter", acc_id, key], cwd=str(ROOT))
            log_ok(f"Guardada clave de TokenRouter: {acc_id}")
    elif opc == "10":
        acc_id = input("  ID de cuenta [xkiro_1]: ").strip() or "xkiro_1"
        key = input("  API Key de xKiro (sk-xt-...): ").strip()
        if key:
            subprocess.run([py_bin, str(gestor), "xkiro", acc_id, key], cwd=str(ROOT))
            log_ok(f"Guardada clave de xKiro: {acc_id}")
    elif opc == "11":
        acc_id = input("  ID de cuenta [tokenharbor_1]: ").strip() or "tokenharbor_1"
        print("  Aviso: Token Harbor puede retener prompts/respuestas enviados por rutas :free.")
        key = input("  API Key de Token Harbor (thk_...): ").strip()
        if key:
            subprocess.run([py_bin, str(gestor), "tokenharbor", acc_id, key], cwd=str(ROOT))
            log_ok(f"Guardada clave de Token Harbor: {acc_id}")
    elif opc == "0":
        print("  Cancelado.")


def cmd_add_ollama():
    py_bin = get_python_bin()
    script = ROOT / "scripts" / "agregar_ollama.py"
    if script.exists():
        subprocess.run([py_bin, str(script)], cwd=str(ROOT))
    else:
        log_err("No se encontró scripts/agregar_ollama.py")


def cmd_services():
    script = ROOT / 'scripts' / 'mis_servicios.py'
    return subprocess.call([get_python_bin(), str(script)], cwd=str(ROOT))


def cmd_adjust_ranking():
    py_bin = get_python_bin()
    script = ROOT / "scripts" / "ajustar_ranking_manual.py"
    if script.exists():
        subprocess.run([py_bin, str(script)], cwd=str(ROOT))
    else:
        log_err("No se encontró scripts/ajustar_ranking_manual.py")


def cmd_sync_exportable():
    py_bin = get_python_bin()
    script = ROOT / "scripts" / "sincronizar_exportable.py"
    if script.exists():
        return subprocess.run([py_bin, str(script)], cwd=str(ROOT)).returncode
    else:
        log_err("No se encontró scripts/sincronizar_exportable.py")
        return 1


def cmd_personal_backup(action: str):
    if len(sys.argv) < 3:
        log_err("Indicá la carpeta del respaldo.")
        return 2
    script = ROOT / "scripts" / "respaldo_personal.py"
    return subprocess.run([get_python_bin(), str(script), action, sys.argv[2]], cwd=str(ROOT)).returncode


def print_help():
    print(__doc__)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print_help()
        sys.exit(0)

    action = sys.argv[1].lower().strip("-")
    if action in ("install", "instalar"):
        cmd_install()
    elif action in ("start", "iniciar", "run"):
        cmd_start()
    elif action in ("stop", "detener", "kill"):
        cmd_stop()
    elif action in ("restart", "reiniciar"):
        cmd_stop()
        cmd_start()
    elif action in ("status", "estado"):
        cmd_status()
    elif action in ("models", "modelos"):
        cmd_models()
    elif action in ("rank", "rankings", "actualizar"):
        cmd_rank()
    elif action in ("test", "probar", "pruebas"):
        sys.exit(cmd_test())
    elif action in ("config", "configurar"):
        cmd_config()
    elif action in ("add-key", "agregar-key", "clave"):
        cmd_add_key()
    elif action in ("services", "servicios", "mis-servicios"):
        sys.exit(cmd_services())
    elif action in ("add-ollama", "agregar-ollama", "ollama"):
        cmd_add_ollama()
    elif action in ("adjust-ranking", "ajustar-ranking", "ranking-manual"):
        cmd_adjust_ranking()
    elif action in ("sync-exportable", "exportar", "sync"):
        sys.exit(cmd_sync_exportable())
    elif action in ("backup", "respaldo", "respaldar"):
        sys.exit(cmd_personal_backup("crear"))
    elif action in ("restore", "restaurar"):
        sys.exit(cmd_personal_backup("restaurar"))
    else:
        print_help()
