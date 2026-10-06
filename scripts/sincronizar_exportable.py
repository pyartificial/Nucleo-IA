#!/usr/bin/env python3
"""
sincronizar_exportable.py — Sincroniza y Sanitiza la Copia Exportable de Núcleo IA.
Copia código, scripts y documentación hacia una carpeta pública elegida,
garantizando que ninguna clave secreta, correo privado, token ni log temporal sea exportado.
"""
import os
import sys
import shutil
import json
import re
import argparse
import subprocess
import tempfile
from pathlib import Path

if hasattr(sys.stdout, 'reconfigure'):
    try: sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception: pass
if hasattr(sys.stderr, 'reconfigure'):
    try: sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception: pass

ROOT = Path(__file__).resolve().parent.parent
EXP_DIR_DEFAULT = ROOT.parent / "NUCLEO_IA_FINAL_PUBLICO"
EXPORT_MARKER = ".nucleo-ia-exportable"

EXCLUDED_SCRIPTS = {
    "test_acc7_models.py",
    "test_cuentas_ollama.py",
    "test_estabilidad.py",
    "ejecutar_pruebas.py",
    "mock_servidor_ollama.py",
    "probar_minimax.py",
    "probar_modelos_gratis.py",
    "exportar_inventario_capacidades.py",
    "instalar_hermes.sh",
}

EXCLUDED_EXTENSIONS = {
    ".pyc", ".log", ".tmp", ".aux", ".out", ".zip", ".tar", ".gz"
}

EXCLUDED_DIRS = {
    "__pycache__", "venv", ".venv", ".git", "build-latex", "ollama_instances", "dist", "NO_COMPARTIR_CREDENCIALES"
}

def sanitizar_cuentas(origen: Path, destino: Path):
    if not origen.exists():
        return
    try:
        data = json.loads(origen.read_text(encoding="utf-8"))
        proveedores_origen = data.get("proveedores", {})
        proveedores = {
            nombre: {"cuentas": []}
            for nombre in proveedores_origen
            if isinstance(nombre, str)
        }
        limpio = {
            "proveedores": proveedores,
            "orden_failover": [x for x in data.get("orden_failover", []) if x in proveedores],
            "mapeo_modelos": data.get("mapeo_modelos", {}),
            "pozo_emails": [],
        }
        destino.write_text(json.dumps(limpio, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"  [OK] Sanitizado cuentas.json -> {destino}")
    except Exception as e:
        print(f"  [ERROR] Error sanitizando cuentas.json: {e}")


def sanitizar_env(origen_example: Path, destino_env: Path):
    if origen_example.exists():
        shutil.copy2(origen_example, destino_env)
        print(f"  [OK] Generado .env limpio desde plantilla -> {destino_env}")
    else:
        destino_env.write_text(
            "# Configuración Núcleo IA (Plantilla Exportable)\n"
            "PROXY_HOST=\"127.0.0.1\"\n"
            "PROXY_PORT=8080\n"
            "SERVICIOS_ACTIVOS=ollama,groq,tokenrouter,cloudflare,nvidia,openrouter,google,cohere,zhipu\n"
            "ROTACION_TOP_N=3\n"
            "GROQ_API_KEY=\n"
            "CEREBRAS_API_KEY=\n"
            "MISTRAL_API_KEY=\n"
            "TOKENROUTER_API_KEY=\n"
            "NVIDIA_API_KEY=\n"
            "CLOUDFLARE_ACCOUNT_ID=\n"
            "CLOUDFLARE_API_TOKEN=\n"
            "OPENROUTER_API_KEY=\n"
            "GOOGLE_API_KEY=\n"
            "COHERE_API_KEY=\n"
            "SILICONFLOW_API_KEY=\n"
            "ZHIPU_API_KEY=\n",
            encoding="utf-8"
        )
        print(f"  [OK] Creado .env limpio -> {destino_env}")


def crear_granja_env_publico(destino: Path):
    """Crea una plantilla legacy sin copiar la configuración privada del clon."""
    destino.write_text(
        "# Compatibilidad legacy. La configuración principal vive en .env\n"
        "PROXY_HOST=127.0.0.1\n"
        "PROXY_PORT=8080\n"
        "INSTANCIAS=0\n"
        "MODO_ROTACION=modelos\n"
        "ROTACION_TOP_N=3\n",
        encoding="utf-8",
    )
    print(f"  [OK] Generado granja.env público -> {destino}")


def strip_bom_file(filepath: Path):
    """Elimina byte order mark (BOM) UTF-8 si está presente."""
    try:
        raw = filepath.read_bytes()
        if raw.startswith(b"\xef\xbb\xbf"):
            filepath.write_bytes(raw[3:])
    except Exception:
        pass


def copiar_arbol(src: Path, dst: Path):
    if not src.exists():
        return
    dst.mkdir(parents=True, exist_ok=True)
    for s_path in src.rglob("*"):
        rel = s_path.relative_to(src)
        if any(part in EXCLUDED_DIRS for part in rel.parts):
            continue
        if s_path.is_file():
            if s_path.suffix.lower() in EXCLUDED_EXTENSIONS:
                continue
            if s_path.name in EXCLUDED_SCRIPTS:
                continue
        d_path = dst / rel
        if s_path.is_dir():
            d_path.mkdir(parents=True, exist_ok=True)
        else:
            try:
                shutil.copy2(s_path, d_path)
                if d_path.suffix in [".py", ".sh", ".bat", ".json", ".md", ".tex", ".txt", ".env"]:
                    strip_bom_file(d_path)
                if d_path.suffix == ".sh":
                    d_path.chmod(0o755)
            except Exception:
                pass


def sanitizar_rankings_state(src_state: Path, dst_state: Path):
    """Prepara un state inicial vacío; nunca copia rankings de esta máquina."""
    dst_state.mkdir(parents=True, exist_ok=True)
    # Los rankings se generan localmente después de configurar cuentas y correr
    # los escaneos. Tampoco se copian route_rankings: son cachés con caducidad.


def parse_args():
    parser = argparse.ArgumentParser(description="Genera una copia limpia y compartible de Núcleo IA.")
    parser.add_argument(
        "--destino",
        type=Path,
        default=EXP_DIR_DEFAULT,
        help="Carpeta exacta que se regenerará. Por defecto: ../NUCLEO_IA_FINAL_PUBLICO",
    )
    parser.add_argument("--interno", action="store_true", help=argparse.SUPPRESS)
    return parser.parse_args()


def limpiar_destino(destino: Path):
    for item in destino.iterdir() if destino.exists() else ():
        if item.is_dir():
            shutil.rmtree(item)
        else:
            item.unlink()


def reemplazar_con_respaldo(destino: Path, preparado: Path):
    """Instala una copia ya validada y restaura la anterior ante cualquier error."""
    with tempfile.TemporaryDirectory(prefix="nucleo-export-backup-") as temporal:
        respaldo = Path(temporal) / "anterior"
        if destino.exists():
            shutil.copytree(destino, respaldo, dirs_exist_ok=True)
        try:
            destino.mkdir(parents=True, exist_ok=True)
            limpiar_destino(destino)
            shutil.copytree(preparado, destino, dirs_exist_ok=True)
        except Exception:
            destino.mkdir(parents=True, exist_ok=True)
            limpiar_destino(destino)
            if respaldo.exists():
                shutil.copytree(respaldo, destino, dirs_exist_ok=True)
            raise


def main():
    args = parse_args()
    exp_dir = args.destino.expanduser().resolve()
    root_resuelto = ROOT.resolve()
    destino_resuelto = exp_dir
    if root_resuelto == destino_resuelto:
        raise RuntimeError(
            "Sincronización cancelada: el origen y el destino son el mismo directorio. "
            "Ejecuta este comando únicamente desde la copia privada de desarrollo."
        )
    if root_resuelto in destino_resuelto.parents or destino_resuelto in root_resuelto.parents:
        raise RuntimeError(
            "Sincronización cancelada: origen y destino no pueden contenerse entre sí."
        )
    if str(destino_resuelto) in {"/", str(Path.home().resolve())}:
        raise RuntimeError("Sincronización cancelada: destino demasiado amplio.")
    if exp_dir.exists():
        contenido = list(exp_dir.iterdir())
        if contenido and not (exp_dir / EXPORT_MARKER).is_file():
            legacy = subprocess.run(
                [sys.executable, str(ROOT / "scripts" / "validar_exportable.py"), str(exp_dir)],
                check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
            if legacy.returncode != 0:
                raise RuntimeError(
                    "Sincronización cancelada: el destino tiene contenido y no es una exportación reconocida. "
                    "Elegí una carpeta vacía para la primera generación."
                )

    if not args.interno:
        with tempfile.TemporaryDirectory(prefix="nucleo-export-stage-") as temporal:
            preparado = Path(temporal) / "exportable"
            resultado = subprocess.run(
                [sys.executable, str(Path(__file__).resolve()), "--destino", str(preparado), "--interno"],
                check=False,
            )
            if resultado.returncode != 0:
                raise RuntimeError("La nueva exportación falló; la copia anterior quedó intacta.")
            reemplazar_con_respaldo(exp_dir, preparado)
        print(f"  [OK] Copia validada instalada con restauración de seguridad: {exp_dir}")
        return

    print("=" * 65)
    print("  📦 SINCRONIZADOR & SANITIZADOR DE COPIA EXPORTABLE")
    print(f"  Origen:  {ROOT}")
    print(f"  Destino: {exp_dir}")
    print("=" * 65)

    # 0. Limpiar completamente el directorio destino previo para evitar archivos huérfanos
    if exp_dir.exists():
        print("  [0] Limpiando residuos previos en destino...")
        limpiar_destino(exp_dir)

    exp_dir.mkdir(parents=True, exist_ok=True)
    (exp_dir / EXPORT_MARKER).write_text("Nucleo IA exportable\n", encoding="utf-8")

    # 1. Copiar carpetas principales
    for item in ["proxy", "scripts", "ui", "informacion", "ollama-farm-kit", "docs para agentes", "tests"]:
        src = ROOT / item
        dst = exp_dir / item
        if src.exists():
            copiar_arbol(src, dst)
            print(f"  [+] Sincronizada carpeta: {item}/")

    # Estos informes son material interno de auditoría y planificación. No forman
    # parte del producto que se comparte ni del repositorio público.
    for interno in (
        "AUDITORIA_EVIDENCIA_2026-09-15.json",
        "AUDITORIA_Y_PLAN_2026-09-15.md",
        "INFORME_RANKING_AUTOMATICO.md",
        "INVENTARIO_MODELOS_LOCAL_2026-09-15.md",
        "MATRIZ_CAPACIDADES_CUOTAS_2026-09-15.md",
        "PLAN_PROVEEDORES_CUENTAS_Y_MUSICA.md",
    ):
        (exp_dir / "docs para agentes" / interno).unlink(missing_ok=True)
    # Manual en PDF que corresponde a una versión previa del instalador.
    (exp_dir / "informacion" / "MANUAL_MODO_EQUIPO.pdf").unlink(missing_ok=True)
    # Herramientas de inventario y pruebas antiguas que solo generan informes
    # internos o alteran una instalación de desarrollo. No se distribuyen.
    for interno in (
        "exportar_inventario_capacidades.py",
        "test_estabilidad.py",
        "ejecutar_pruebas.py",
        "mock_servidor_ollama.py",
        "probar_minimax.py",
    ):
        (exp_dir / "scripts" / interno).unlink(missing_ok=True)

    # 2. Copiar archivos raíz de código, scripts y documentación
    archivos_raiz = [
        "granja.py",
        "requirements.txt",
        "README.md",
        "agent.md",
        "LICENSE",
        "SECURITY.md",
        "CONTRIBUTING.md",
        ".env.example",
        ".gitignore",
        "ranking_config.json",
        "iniciar_todo.sh",
        "iniciar_todo.bat",
        "detener_todo.sh",
        "detener_todo.bat",
        "instalar_nucleo_ia.sh",
        "instalar_nucleo_ia.bat",
        "configura_nucleoia.sh",
        "configura_nucleoia.bat",
        "actualizar_rankings.sh",
        "actualizar_rankings.bat",
        "agregar_cuentas.sh",
        "agregar_cuentas.bat",
        "mis_servicios.sh",
        "mis_servicios.bat",
        "mis_servicios.vbs",
        "centro_control.sh",
        "centro_control.bat",
        "centro_control.vbs",
        "ajustar_ranking_manual.sh",
        "ajustar_ranking_manual.bat",
        "ajustar_ranking_manual.desktop",
        "probar_demo.sh",
        "probar_demo.bat",
        "iniciar_segundo_plano.vbs",
        "instalar_inicio_automatico.bat",
        "desinstalar_inicio_automatico.bat",
        "instalar_inicio_automatico.sh",
        "desinstalar_inicio_automatico.sh",
        "reparar_ollama.sh",
        "reparar_ollama.bat",
    ]

    for fname in archivos_raiz:
        src_f = ROOT / fname
        dst_f = exp_dir / fname
        if src_f.exists():
            shutil.copy2(src_f, dst_f)
            if dst_f.suffix in [".py", ".sh", ".bat", ".json", ".md", ".tex", ".txt", ".env"]:
                strip_bom_file(dst_f)
            if dst_f.suffix == ".sh":
                dst_f.chmod(0o755)

    print("  [+] Copiados archivos ejecutables y scripts nativos (.bat, .sh, .py).")

    # El acceso Linux se genera para el destino: no debe apuntar a la copia privada.
    from instalar_acceso_servicios import desktop_text
    acceso = exp_dir / 'mis_servicios.desktop'
    acceso.write_text(desktop_text(exp_dir), encoding='utf-8')
    acceso.chmod(0o755)
    acceso_centro = exp_dir / 'centro_control.desktop'
    acceso_centro.write_text(desktop_text(exp_dir, centro=True), encoding='utf-8')
    acceso_centro.chmod(0o755)

    # 3. Sanitizar .env en destino (Plantilla limpia sin secretos)
    sanitizar_env(ROOT / ".env.example", exp_dir / ".env")
    if (ROOT / ".env.example").exists():
        shutil.copy2(ROOT / ".env.example", exp_dir / ".env.example")
    crear_granja_env_publico(exp_dir / "granja.env")

    # 4. Sanitizar cuentas.json en destino
    sanitizar_cuentas(ROOT / "cuentas.json", exp_dir / "cuentas.json")

    # 5. Preparar estructura de state limpia con rankings (sin probe caches ni logs)
    sanitizar_rankings_state(ROOT / "state", exp_dir / "state")
    (exp_dir / "state" / "rankings_precargados.json").write_text(
        json.dumps({"formato": 1, "estado": "catalogo_inicial"}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print("  [+] State exportado vacío; rankings y cachés se crearán en la nueva instalación.")

    # 6. Crear carpeta de instancias vacía para Ollama
    (exp_dir / "ollama_instances").mkdir(parents=True, exist_ok=True)

    # 7. Asegurar permisos de ejecución en todos los .sh
    for sh_file in exp_dir.glob("**/*.sh"):
        try:
            sh_file.chmod(0o755)
        except Exception:
            pass

    validator = exp_dir / "scripts" / "validar_exportable.py"
    validation = subprocess.run([sys.executable, str(validator), str(exp_dir)], check=False)
    if validation.returncode != 0:
        raise RuntimeError(
            "La copia fue generada pero no aprobó la validación. No debe compartirse."
        )

    print("=" * 65)
    print("  🎉 Sincronización y validación finalizadas exitosamente!")
    print(f"  La carpeta '{exp_dir.name}' fue regenerada y sanitizada.")
    print("=" * 65)


if __name__ == "__main__":
    main()
