"""Perfiles de seguridad para el Centro de control de Núcleo IA.

El nombre visible es Personal o Profesional. Los valores históricos
``empresa`` y ``organizacion`` se aceptan únicamente al leer configuraciones.
"""
from __future__ import annotations

import json
import os
import secrets
import tempfile
import time
from pathlib import Path

from scripts.secret_utils import _parse_env_file


TRUE_VALUES = {"1", "true", "yes", "on", "si", "sí"}


class ErrorPerfil(ValueError):
    pass


def normalizar_perfil(valor: str) -> str:
    valor = str(valor or "personal").strip().lower()
    if valor in {"profesional", "empresa", "organizacion", "organización"}:
        return "profesional"
    return "personal"


def _es_true(valor: str) -> bool:
    return str(valor or "").strip().lower() in TRUE_VALUES


def _escribir_atomico(path: Path, contenido: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporal = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as archivo:
            archivo.write(contenido)
            archivo.flush()
            os.fsync(archivo.fileno())
        os.replace(temporal, path)
    finally:
        if os.path.exists(temporal):
            os.unlink(temporal)


def _actualizar_env(texto: str, cambios: dict[str, str]) -> str:
    pendientes = dict(cambios)
    salida: list[str] = []
    for linea in texto.splitlines():
        nombre = linea.strip().removeprefix("export ").split("=", 1)[0].strip()
        if nombre in cambios:
            if nombre in pendientes:
                salida.append(f"{nombre}={pendientes.pop(nombre)}")
        else:
            salida.append(linea)
    if salida and salida[-1].strip():
        salida.append("")
    salida.extend(f"{nombre}={valor}" for nombre, valor in pendientes.items())
    return "\n".join(salida) + "\n"


class GestorPerfiles:
    def __init__(self, root: Path | str):
        self.root = Path(root)
        self.env_path = self.root / ".env"
        self.backup_dir = self.root / "state" / "config_backups"
        self.audit_path = self.root / "state" / "auditoria_panel.jsonl"

    def configuracion(self) -> dict[str, str]:
        datos = _parse_env_file(self.root / "granja.env")
        datos.update(_parse_env_file(self.env_path))
        return datos

    def estado(self) -> dict:
        cfg = self.configuracion()
        perfil = normalizar_perfil(cfg.get("PERFIL_USO", "personal"))
        auth = _es_true(cfg.get("AUTH_ENABLED", "false"))
        host = cfg.get("PROXY_HOST", "127.0.0.1") or "127.0.0.1"
        origenes = [x.strip() for x in cfg.get("CORS_ALLOW_ORIGINS", "").split(",") if x.strip()]
        hosts = [x.strip() for x in cfg.get("ALLOWED_HOSTS", "").split(",") if x.strip()]
        avisos: list[str] = []
        if perfil == "profesional":
            if not auth:
                avisos.append("La autenticación profesional no está activa.")
            if not cfg.get("NUCLEO_API_KEY", "").strip() or not cfg.get("NUCLEO_ADMIN_KEY", "").strip():
                avisos.append("Faltan credenciales separadas de uso y administración.")
            if "*" in origenes:
                avisos.append("El acceso web permite cualquier origen.")
            if host not in {"127.0.0.1", "::1", "localhost"} and not hosts:
                avisos.append("Falta definir qué nombres o direcciones pueden acceder por red.")
        return {
            "perfil": perfil,
            "nombre": "Profesional" if perfil == "profesional" else "Personal",
            "protegido": perfil == "profesional" and not avisos,
            "host": host,
            "puerto": int(cfg.get("PROXY_PORT", "8080") or 8080),
            "acceso_red": host not in {"127.0.0.1", "::1", "localhost"},
            "autenticacion": auth,
            "origenes": origenes,
            "hosts_permitidos": hosts,
            "avisos": avisos,
        }

    def aplicar(self, perfil: str, *, acceso_red: bool = False,
                hosts_permitidos: str = "", origenes: str = "") -> dict:
        perfil = normalizar_perfil(perfil)
        texto_anterior = self.env_path.read_text(encoding="utf-8") if self.env_path.exists() else ""
        cfg = self.configuracion()

        if perfil == "personal":
            cambios = {
                "PERFIL_USO": "personal",
                "PROXY_HOST": "127.0.0.1",
                "AUTH_ENABLED": "false",
                "CORS_ALLOW_ORIGINS": "",
                "ALLOWED_HOSTS": "",
                "CORS_ALLOW_CREDENTIALS": "false",
                "PERMITIR_OLLAMA_REMOTO": "false",
            }
        else:
            hosts = [x.strip() for x in str(hosts_permitidos).split(",") if x.strip()]
            cors = [x.strip().rstrip("/") for x in str(origenes).split(",") if x.strip()]
            if "*" in hosts or "*" in cors:
                raise ErrorPerfil("En modo Profesional no se permite usar * en sitios o direcciones autorizadas.")
            if acceso_red and not hosts:
                raise ErrorPerfil("Indicá al menos una dirección o nombre autorizado para el acceso por red.")
            if any(not (x.startswith("http://") or x.startswith("https://")) for x in cors):
                raise ErrorPerfil("Cada sitio autorizado debe comenzar con http:// o https://.")
            cambios = {
                "PERFIL_USO": "profesional",
                "PROXY_HOST": "0.0.0.0" if acceso_red else "127.0.0.1",
                "AUTH_ENABLED": "true",
                "NUCLEO_API_KEY": cfg.get("NUCLEO_API_KEY", "").strip() or secrets.token_urlsafe(32),
                "NUCLEO_ADMIN_KEY": cfg.get("NUCLEO_ADMIN_KEY", "").strip() or secrets.token_urlsafe(32),
                "CORS_ALLOW_ORIGINS": ",".join(cors),
                "ALLOWED_HOSTS": ",".join(hosts),
                "CORS_ALLOW_CREDENTIALS": "false",
                "PERMITIR_OLLAMA_REMOTO": "false",
            }

        self.backup_dir.mkdir(parents=True, exist_ok=True)
        marca = time.strftime("%Y%m%d-%H%M%S")
        backup = self.backup_dir / f"env-antes-perfil-{marca}.bak"
        _escribir_atomico(backup, texto_anterior)
        try:
            _escribir_atomico(self.env_path, _actualizar_env(texto_anterior, cambios))
            if perfil == "profesional" and os.name != "nt":
                os.chmod(self.env_path, 0o600)
        except Exception:
            _escribir_atomico(self.env_path, texto_anterior)
            raise

        self._auditar("cambio_perfil", {"perfil": perfil, "acceso_red": bool(acceso_red)})
        resultado = self.estado()
        resultado.update({
            "aplicado": True,
            "requiere_reinicio": True,
            "mensaje": f"Modo {resultado['nombre']} guardado. Reiniciá Núcleo IA para aplicar la protección.",
        })
        return resultado

    def _auditar(self, accion: str, detalle: dict) -> None:
        self.audit_path.parent.mkdir(parents=True, exist_ok=True)
        evento = {"fecha": time.strftime("%Y-%m-%d %H:%M:%S"), "accion": accion, **detalle}
        with self.audit_path.open("a", encoding="utf-8") as archivo:
            archivo.write(json.dumps(evento, ensure_ascii=False) + "\n")
            archivo.flush()
            os.fsync(archivo.fileno())
        if os.name != "nt":
            os.chmod(self.audit_path, 0o600)
