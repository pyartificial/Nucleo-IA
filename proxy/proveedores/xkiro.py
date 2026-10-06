"""Proveedor xKiro — gateway OpenAI-compatible con catálogo multi-modelo."""
from __future__ import annotations

import os
import re
from pathlib import Path

from proxy.proveedores.base import ProveedorBase

URL_BASE_XKIRO = "https://api.xkiro.com/v1/chat/completions"
ROOT = Path(__file__).resolve().parents[2]


def _parse_env_file(path: Path) -> dict[str, str]:
    data: dict[str, str] = {}
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return data
    for raw in lines:
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        if line.startswith("export "):
            line = line[7:].lstrip()
        key, value = line.split("=", 1)
        data[key.strip()] = value.strip().strip('"').strip("'")
    return data


def _load_local_env() -> None:
    for filename in (".env", "granja.env"):
        for key, value in _parse_env_file(ROOT / filename).items():
            os.environ.setdefault(key, value)


def _env_suffix(text: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "_", str(text).upper()).strip("_")


def _valid_key(value: object) -> bool:
    text = str(value or "").strip()
    return text.startswith("sk-xt-") and len(text) >= 32 and "..." not in text


def _resolve_api_key(cuenta: dict) -> str:
    _load_local_env()
    account_id = str(cuenta.get("id", "")).strip()
    candidates = [
        cuenta.get("api_key"),
        os.getenv(f"XKIRO_API_KEY_{_env_suffix(account_id)}") if account_id else None,
        os.getenv("XKIRO_API_KEY"),
    ]
    for candidate in candidates:
        if _valid_key(candidate):
            return str(candidate).strip()
    return ""


class ProveedorXKiro(ProveedorBase):
    """Conecta Núcleo IA con Chat Completions de xKiro."""

    def __init__(self, cuenta):
        super().__init__(cuenta)
        self.api_key = _resolve_api_key(cuenta)
        self.url_base = (cuenta.get("url_base") or URL_BASE_XKIRO).rstrip("/")

    def construir_url(self):
        if self.url_base.endswith("/v1"):
            return f"{self.url_base}/chat/completions"
        return self.url_base

    def construir_headers(self):
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "User-Agent": "Nucleo-IA/1.0",
        }

    def tiene_credencial_valida(self):
        return bool(self.api_key)

    def identificar(self):
        key_corta = self.api_key[-6:] if len(self.api_key) > 6 else "***"
        return f"xkiro:{self.id_cuenta}(***{key_corta})"
