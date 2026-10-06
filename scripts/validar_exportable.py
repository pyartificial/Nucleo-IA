#!/usr/bin/env python3
"""Valida que una copia de Núcleo IA sea coherente y segura para compartir."""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import zipfile
from pathlib import Path


REQUIRED = {
    "README.md",
    "LICENSE",
    "requirements.txt",
    ".env",
    ".env.example",
    "cuentas.json",
    "ranking_config.json",
    "granja.py",
    "instalar_nucleo_ia.bat",
    "iniciar_segundo_plano.vbs",
    "instalar_inicio_automatico.bat",
    "docs para agentes/EJECUTABLES_Y_USO.md",
    "docs para agentes/CONTRATO_ALIASES_MULTIMEDIA.md",
    "docs para agentes/MANUAL_PRINCIPIANTE.md",
    "docs para agentes/MANUAL_AVANZADO.md",
    "docs para agentes/MANUAL_MODO_ORGANIZACION.md",
    "docs para agentes/MANUAL_USUARIO_COMPLETO.md",
    "docs para agentes/MIS_SERVICIOS.md",
    "docs para agentes/PASARELAS_Y_RANKING_GRATUITO.md",
    "docs para agentes/RANKING_AUTOMATICO.md",
    "docs para agentes/GUIA_AGENTES.md",
    "docs para agentes/INSTALACION_DOCKER.md",
    "docs para agentes/REPARAR_CUENTA_OLLAMA.md",
    "docs para agentes/agentes/embeddings.md",
    "docs para agentes/agentes/imagenes.md",
    "docs para agentes/agentes/transcripcion.md",
    "docs para agentes/agentes/tts.md",
    "docs para agentes/agentes/videos.md",
    "docs para agentes/agentes/vision.md",
    "informacion/README.md",
    "informacion/MANUAL_USUARIO.pdf",
    "informacion/MANUAL_HERMES_NUCLEO_IA.pdf",
    "informacion/MANUAL_OPENCODE_NUCLEO_IA.pdf",
    "informacion/MANUAL_OPENWEBUI_NUCLEO_IA.pdf",
    "informacion/MANUAL_MODO_ORGANIZACION.pdf",
}
PUBLICATION_REQUIRED = {
    "README.md", "LICENSE", ".gitignore", "SECURITY.md", "index.html",
    "CONTENIDO_PAGINA.md", "docs para agentes/MANUAL_USUARIO_COMPLETO.md",
    "docs para agentes/GUIA_AGENTES.md", "docs para agentes/CONTRATO_ALIASES_MULTIMEDIA.md",
    "docs para agentes/EJECUTABLES_Y_USO.md", "docs para agentes/INSTALACION_DOCKER.md",
    "docs para agentes/MANUAL_AVANZADO.md", "docs para agentes/MANUAL_MODO_ORGANIZACION.md",
    "docs para agentes/MANUAL_PRINCIPIANTE.md", "docs para agentes/MIS_SERVICIOS.md",
    "docs para agentes/PASARELAS_Y_RANKING_GRATUITO.md", "docs para agentes/RANKING_AUTOMATICO.md",
    "docs para agentes/REPARAR_CUENTA_OLLAMA.md", "docs para agentes/agentes/embeddings.md",
    "docs para agentes/agentes/imagenes.md", "docs para agentes/agentes/transcripcion.md",
    "docs para agentes/agentes/tts.md", "docs para agentes/agentes/videos.md",
    "docs para agentes/agentes/vision.md", "agent.md",
    ".github/ISSUE_TEMPLATE/bug_report.yml",
    ".github/ISSUE_TEMPLATE/feature_request.yml", ".github/PULL_REQUEST_TEMPLATE.md",
}
FORBIDDEN_DIRS = {
    ".git", ".agents", ".aws", ".codex", "venv", ".venv", "__pycache__", "NO_COMPARTIR_CREDENCIALES",
    "PROVISORIO_NUCLEO_IA_ANTIGUO", "nucleo ia EXPORTABLE",
}
SECRET_PATTERNS = {
    "OpenRouter": re.compile(r"\bsk-or-v1-[A-Za-z0-9_-]{16,}"),
    "Groq": re.compile(r"\bgsk_[A-Za-z0-9_-]{16,}"),
    "NVIDIA": re.compile(r"\bnvapi-[A-Za-z0-9_-]{16,}"),
    "Google": re.compile(r"\bAIza[A-Za-z0-9_-]{20,}"),
    "Hugging Face": re.compile(r"\bhf_[A-Za-z0-9]{20,}"),
}
PRIVATE_EMAIL = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I)
TEXT_SUFFIXES = {".py", ".sh", ".bat", ".vbs", ".md", ".txt", ".json", ".env", ".cs", ".html"}
CREDENTIAL_KEYS = {"api_key", "token", "auth_token", "key", "secret", "secret_key", "api_secret"}
SHARE_EXCLUDED_DIRS = {
    ".git", ".agents", ".aws", ".codex", "__pycache__", "venv", ".venv",
    "state", "ollama_instances", "logs", "PUBLICACION_GITHUB",
    "NO_COMPARTIR_CREDENCIALES", "node_modules", "dist", "build",
}
SHARE_EXCLUDED_FILES = {
    ".env", "granja.env", "cuentas.json", ".nucleo-ia-exportable",
    "Nucleo-IA-GITHUB.zip", "PREPARAR_PUBLICACION_GITHUB.md",
    "actualizar_publicacion_github.py",
}
SHARE_EXCLUDED_SUFFIXES = {
    ".pyc", ".pyo", ".log", ".tmp", ".zip", ".nia-backup", ".nia-keys",
    ".sqlite", ".db",
}
PUBLICATION_ASSETS = {
    "README.md", ".gitignore", "SECURITY.md", "index.html", "CONTENIDO_PAGINA.md",
    ".github/ISSUE_TEMPLATE/bug_report.yml",
    ".github/ISSUE_TEMPLATE/feature_request.yml",
    ".github/PULL_REQUEST_TEMPLATE.md",
}


def expected_share_files(root: Path) -> set[str]:
    """Files that the GitHub package generator is expected to mirror."""
    found: set[str] = set()
    for current, dirnames, filenames in os.walk(root, followlinks=False):
        current_path = Path(current)
        relative_dir = current_path.relative_to(root)
        dirnames[:] = [
            name for name in dirnames
            if name not in SHARE_EXCLUDED_DIRS and not (current_path / name).is_symlink()
        ]
        for filename in filenames:
            path = current_path / filename
            relative = path.relative_to(root)
            if path.is_symlink() or filename in SHARE_EXCLUDED_FILES:
                continue
            if filename in {"README.md", ".gitignore", "SECURITY.md", "index.html", "CONTENIDO_PAGINA.md"} and relative.parent == Path("."):
                continue
            if path.suffix.lower() in SHARE_EXCLUDED_SUFFIXES:
                continue
            found.add(relative.as_posix())
    return found


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("ruta", nargs="?", type=Path, default=Path(__file__).resolve().parents[1])
    return parser.parse_args()


def main() -> int:
    root = parse_args().ruta.resolve()
    errors: list[str] = []

    for rel in sorted(REQUIRED):
        if not (root / rel).is_file():
            errors.append(f"falta archivo requerido: {rel}")

    publication = root / "PUBLICACION_GITHUB"
    if not publication.is_dir():
        errors.append("falta carpeta de publicación PUBLICACION_GITHUB")
        publication_files: set[str] = set()
    else:
        publication_files = {
            path.relative_to(publication).as_posix()
            for path in publication.rglob("*") if path.is_file() and not path.is_symlink()
        }
        for rel in sorted(PUBLICATION_REQUIRED):
            if rel not in publication_files:
                errors.append(f"falta archivo requerido para publicar: PUBLICACION_GITHUB/{rel}")

        expected_files = expected_share_files(root)
        missing_from_publication = sorted(expected_files - publication_files)
        unexpected_in_publication = sorted(publication_files - expected_files - PUBLICATION_ASSETS)
        if missing_from_publication:
            errors.append("faltan archivos actuales en PUBLICACION_GITHUB: " + ", ".join(missing_from_publication[:12]))
        if unexpected_in_publication:
            errors.append("hay archivos sin fuente en PUBLICACION_GITHUB: " + ", ".join(unexpected_in_publication[:12]))
        mismatches = [
            rel for rel in sorted(expected_files & publication_files)
            if (root / rel).read_bytes() != (publication / rel).read_bytes()
        ]
        if mismatches:
            errors.append("PUBLICACION_GITHUB está desactualizada respecto de la copia: " + ", ".join(mismatches[:12]))

    public_archive = root / "Nucleo-IA-GITHUB.zip"
    share_archive = root / "Nucleo-IA-Compartir.zip"
    for path in root.rglob("*"):
        rel = path.relative_to(root)
        if path.is_dir() and path.name in FORBIDDEN_DIRS:
            # Codex monta marcadores vacíos de workspace en la raíz. No contienen
            # datos exportables; cualquier contenido o aparición anidada sí falla.
            root_marker = rel.parent == Path(".") and path.name in {".git", ".agents", ".aws", ".codex"}
            marker_empty = root_marker and not any(path.iterdir())
            if not marker_empty:
                errors.append(f"directorio prohibido: {rel}")
        if path.is_file() and path.suffix.lower() in {".log", ".pyc"}:
            errors.append(f"archivo temporal/prohibido: {rel}")
        if path.is_file() and path.suffix.lower() == ".zip" and path not in {public_archive, share_archive}:
            errors.append(f"archivo comprimido no reconocido: {rel}")

    env_file = root / ".env"
    env_example = root / ".env.example"
    if env_file.exists() and env_example.exists() and env_file.read_bytes() != env_example.read_bytes():
        errors.append(".env no coincide con la plantilla limpia .env.example")

    accounts_path = root / "cuentas.json"
    if accounts_path.exists():
        try:
            accounts = json.loads(accounts_path.read_text(encoding="utf-8"))
            if accounts.get("pozo_emails"):
                errors.append("cuentas.json contiene correos del pozo de la instalación de origen")
            stack = [accounts]
            while stack:
                value = stack.pop()
                if isinstance(value, dict):
                    for key, item in value.items():
                        if key.casefold() in CREDENTIAL_KEYS and item not in (None, "", [], {}):
                            errors.append(f"cuentas.json contiene credencial en campo {key}")
                        stack.append(item)
                elif isinstance(value, list):
                    stack.extend(value)
            for match in PRIVATE_EMAIL.findall(accounts_path.read_text(encoding="utf-8")):
                if not match.casefold().endswith("@ejemplo.com"):
                    errors.append("cuentas.json contiene un correo no anonimizado")
                    break
        except Exception as exc:
            errors.append(f"cuentas.json inválido: {exc}")

    for env_name in (".env", "granja.env"):
        env_path = root / env_name
        if not env_path.exists():
            continue
        for raw in env_path.read_text(encoding="utf-8", errors="ignore").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.removeprefix("export ").split("=", 1)
            key = key.strip().upper()
            value = value.strip().strip("\"'")
            sensitive = (
                key.endswith(("API_KEY", "API_TOKEN", "AUTH_TOKEN", "ACCESS_TOKEN", "SECRET", "PASSWORD"))
                or key in {"NUCLEO_API_KEY", "NUCLEO_ADMIN_KEY"}
            )
            if sensitive and value and not value.startswith("TU_") and "..." not in value:
                errors.append(f"{env_name} contiene un valor sensible en {key}")

    if public_archive.exists():
        try:
            with zipfile.ZipFile(public_archive) as archive:
                names = archive.namelist()
                archive_errors = []
                if len(names) != len(set(names)):
                    archive_errors.append("el ZIP contiene rutas duplicadas")
                if not names or any(not name.startswith("Nucleo-IA-GITHUB/") for name in names):
                    archive_errors.append("el ZIP debe contener solo la carpeta Nucleo-IA-GITHUB/")
                for name in names:
                    parts = Path(name).parts
                    base = Path(name).name
                    if any(part in FORBIDDEN_DIRS | {"state", "ollama_instances", "logs", "venv", ".venv"} for part in parts):
                        archive_errors.append(f"directorio privado en ZIP: {name}")
                    if base in {".env", "granja.env", "cuentas.json"}:
                        archive_errors.append(f"archivo con estado/credenciales en ZIP: {name}")
                    if name.endswith((".pyc", ".log", ".zip", ".nia-backup", ".nia-keys")):
                        archive_errors.append(f"archivo temporal en ZIP: {name}")
                    if not name.endswith("/"):
                        try:
                            content = archive.read(name)
                        except (KeyError, RuntimeError, OSError) as exc:
                            archive_errors.append(f"no se puede leer {name}: {exc}")
                            continue
                        if Path(name).suffix.lower() == ".json":
                            try:
                                json.loads(content.decode("utf-8"))
                            except (UnicodeDecodeError, ValueError) as exc:
                                archive_errors.append(f"JSON inválido en ZIP {name}: {exc}")
                        if Path(name).suffix.lower() == ".py":
                            try:
                                compile(content.decode("utf-8"), name, "exec")
                            except (UnicodeDecodeError, SyntaxError) as exc:
                                archive_errors.append(f"Python inválido en ZIP {name}: {exc}")
                        if Path(name).suffix.lower() in TEXT_SUFFIXES:
                            decoded = content.decode("utf-8", errors="ignore")
                            for provider, pattern in SECRET_PATTERNS.items():
                                if pattern.search(decoded):
                                    archive_errors.append(f"posible secreto {provider} en ZIP {name}")
                                    break
                        if base == "farm.env":
                            for raw in content.decode("utf-8", errors="ignore").splitlines():
                                line = raw.strip()
                                if not line or line.startswith("#") or "=" not in line:
                                    continue
                                key, value = line.removeprefix("export ").split("=", 1)
                                if key.strip().upper().endswith(("API_KEY", "API_TOKEN", "AUTH_TOKEN", "ACCESS_TOKEN", "SECRET", "PASSWORD")) and value.strip().strip("\"'"):
                                    archive_errors.append(f"farm.env contiene una credencial: {name}")
                                    break
                prefix = "Nucleo-IA-GITHUB/"
                zipped_files = {name[len(prefix):] for name in names if name.startswith(prefix) and not name.endswith("/")}
                if zipped_files != publication_files:
                    absent = sorted(publication_files - zipped_files)
                    extra = sorted(zipped_files - publication_files)
                    archive_errors.append(
                        f"contenido no coincide con PUBLICACION_GITHUB (faltan: {absent[:8]}; sobran: {extra[:8]})"
                    )
                for rel in sorted(zipped_files & publication_files):
                    try:
                        if archive.read(f"{prefix}{rel}") != (publication / rel).read_bytes():
                            archive_errors.append(f"contenido distinto a PUBLICACION_GITHUB: {rel}")
                    except (KeyError, RuntimeError, OSError) as exc:
                        archive_errors.append(f"no se puede comparar {rel}: {exc}")
                if archive_errors:
                    errors.extend(f"Nucleo-IA-GITHUB.zip: {issue}" for issue in archive_errors)
        except (OSError, zipfile.BadZipFile) as exc:
            errors.append(f"ZIP de GitHub ilegible: {exc}")

    if share_archive.exists():
        try:
            with zipfile.ZipFile(share_archive) as archive:
                names = archive.namelist()
                prefix = "Nucleo-IA/"
                archive_errors = []
                if len(names) != len(set(names)):
                    archive_errors.append("el ZIP contiene rutas duplicadas")
                if not names or any(not name.startswith(prefix) for name in names):
                    archive_errors.append("el ZIP debe contener solo la carpeta Nucleo-IA/")
                zipped_files = {name[len(prefix):] for name in names if name.startswith(prefix) and not name.endswith("/")}
                if zipped_files != publication_files:
                    absent = sorted(publication_files - zipped_files)
                    extra = sorted(zipped_files - publication_files)
                    archive_errors.append(f"contenido no coincide con PUBLICACION_GITHUB (faltan: {absent[:8]}; sobran: {extra[:8]})")
                for rel in sorted(zipped_files & publication_files):
                    try:
                        if archive.read(f"{prefix}{rel}") != (publication / rel).read_bytes():
                            archive_errors.append(f"contenido distinto a PUBLICACION_GITHUB: {rel}")
                    except (KeyError, RuntimeError, OSError) as exc:
                        archive_errors.append(f"no se puede comparar {rel}: {exc}")
                required_manuals = {name for name in publication_files if name.startswith("informacion/") and name.lower().endswith(".pdf")}
                if not required_manuals.issubset(zipped_files):
                    archive_errors.append("faltan manuales PDF en el ZIP para compartir")
                if archive_errors:
                    errors.extend(f"Nucleo-IA-Compartir.zip: {issue}" for issue in archive_errors)
        except (OSError, zipfile.BadZipFile) as exc:
            errors.append(f"ZIP para compartir ilegible: {exc}")

    for path in root.rglob("*.json"):
        try:
            json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            errors.append(f"JSON inválido {path.relative_to(root)}: {exc}")

    for path in root.rglob("*.py"):
        try:
            compile(path.read_text(encoding="utf-8"), str(path), "exec")
        except Exception as exc:
            errors.append(f"Python inválido {path.relative_to(root)}: {exc}")

    for path in root.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for name, pattern in SECRET_PATTERNS.items():
            if pattern.search(text):
                errors.append(f"posible secreto {name} en {path.relative_to(root)}")

    executable_doc = root / "docs para agentes" / "EJECUTABLES_Y_USO.md"
    if executable_doc.exists():
        doc_text = executable_doc.read_text(encoding="utf-8")
        for path in root.rglob("*"):
            if path.is_file() and path.suffix.lower() in {".bat", ".sh", ".vbs", ".exe", ".desktop"}:
                rel_name = path.relative_to(root).as_posix()
                if rel_name not in doc_text and path.name not in doc_text:
                    errors.append(f"ejecutable sin documentar: {rel_name}")

    ranking_doc = root / "docs para agentes" / "RANKING_AUTOMATICO.md"
    if ranking_doc.exists() and "LMArena" not in ranking_doc.read_text(encoding="utf-8"):
        errors.append("el manual de ranking no documenta LMArena")

    if errors:
        print(f"[FALLO] Copia no apta: {len(errors)} problema(s)")
        for error in errors:
            print(f"  - {error}")
        return 1
    print("[OK] Copia compartible validada: estructura, JSON, Python, manuales y secretos.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
