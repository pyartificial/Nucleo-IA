"""Política de acceso HTTP común para el proxy de Núcleo IA."""
from __future__ import annotations

import os
from urllib.parse import urlsplit


TRUE_VALUES = {"1", "true", "yes", "on", "si", "sí"}
LOOPBACK_HOSTS = {"127.0.0.1", "::1", "localhost"}
PUBLIC_PATHS = {"/healthz", "/readyz"}
ADMIN_PATHS = {"/status", "/rankings"}


def professional_profile() -> bool:
    """Acepta nombres antiguos, pero el nombre público es Profesional."""
    return os.getenv("PERFIL_USO", "personal").strip().lower() in {
        "profesional", "empresa", "organizacion", "organización"
    }


def enabled(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    return default if raw is None else raw.strip().lower() in TRUE_VALUES


def configured_host() -> str:
    return os.getenv("PROXY_HOST", "127.0.0.1").strip() or "127.0.0.1"


def is_loopback_host(host: str) -> bool:
    return host.strip("[]").lower() in LOOPBACK_HOSTS


def allowed_origins() -> set[str]:
    raw = os.getenv("CORS_ALLOW_ORIGINS", "").strip()
    explicit = {x.strip().rstrip("/") for x in raw.split(",") if x.strip() and x.strip() != "*"}
    port = int(os.getenv("PROXY_PORT", "8080"))
    return explicit | {f"http://127.0.0.1:{port}", f"http://localhost:{port}"}


def origin_allowed(origin: str) -> bool:
    if not origin:
        return True  # Clientes de API nativos no envían Origin.
    try:
        parsed = urlsplit(origin)
    except ValueError:
        return False
    normalized = f"{parsed.scheme}://{parsed.netloc}".rstrip("/")
    return parsed.scheme in {"http", "https"} and normalized in allowed_origins()


def host_allowed(host_header: str) -> bool:
    """Acepta únicamente el nombre configurado y los alias locales explícitos."""
    if not host_header:
        return False
    host = host_header.strip().lower()
    if host.startswith("[") and "]" in host:
        host = host[1:host.index("]")]
    else:
        host = host.split(":", 1)[0]
    configured = configured_host().strip("[]").lower()
    allowed = {configured}
    if is_loopback_host(configured):
        allowed |= LOOPBACK_HOSTS
    allowed |= {
        value.strip().strip("[]").lower()
        for value in os.getenv("ALLOWED_HOSTS", "").split(",")
        if value.strip()
    }
    return host in allowed


def validate_deployment() -> None:
    """Impide publicar el proxy por red sin una clave de acceso."""
    professional = professional_profile()
    if is_loopback_host(configured_host()) and not professional:
        return
    if not enabled("AUTH_ENABLED") or not os.getenv("NUCLEO_API_KEY", "").strip():
        raise RuntimeError(
            "Para compartir Núcleo IA por red activa AUTH_ENABLED y configura NUCLEO_API_KEY."
        )
    if professional and not os.getenv("NUCLEO_ADMIN_KEY", "").strip():
        raise RuntimeError("El modo Profesional requiere NUCLEO_ADMIN_KEY para proteger la administración.")


def expected_key(path: str) -> str:
    if professional_profile() and path in ADMIN_PATHS:
        return os.getenv("NUCLEO_ADMIN_KEY", "")
    return os.getenv("NUCLEO_API_KEY", "")
