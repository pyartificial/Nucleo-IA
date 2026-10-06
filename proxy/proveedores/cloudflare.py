"""
Proveedor Cloudflare Workers AI — API cloud con autenticación Bearer.
Endpoint OpenAI-compatible:
https://api.cloudflare.com/client/v4/accounts/{ACCOUNT_ID}/ai/v1/chat/completions
"""
from __future__ import annotations

import json
import os
from pathlib import Path

from proxy.proveedores.base import ProveedorBase

URL_BASE_CLOUDFLARE = "https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/v1/chat/completions"
ROOT = Path(__file__).resolve().parents[2]


def _parse_env_file(path: Path) -> dict[str, str]:
    data: dict[str, str] = {}
    try:
        text = path.read_text(encoding="utf-8")
    except Exception:
        return data
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        if line.startswith("export "):
            line = line[7:].lstrip()
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        data[key] = value
    return data


def _looks_like_secret(value: object) -> bool:
    if not value:
        return False
    text = str(value).strip()
    if not text:
        return False
    if text.startswith("TU_"):
        return False
    if text.startswith("<") and text.endswith(">"):
        return False
    if "..." in text:
        return False
    return True


def _load_local_env() -> None:
    for filename in (".env", "granja.env"):
        for key, value in _parse_env_file(ROOT / filename).items():
            os.environ.setdefault(key, value)


def _env_suffix(text: str) -> str:
    return "".join(ch if ch.isalnum() else "_" for ch in str(text).upper()).strip("_")


def _resolve_account_id(cuenta) -> str:
    _load_local_env()
    account_id = str(cuenta.get("account_id") or cuenta.get("accountId") or "").strip()
    if account_id:
        return account_id

    account_id = str(cuenta.get("id", "")).strip()
    candidatos = [
        os.getenv(f"CLOUDFLARE_ACCOUNT_ID_{_env_suffix(account_id)}") if account_id else None,
        os.getenv(f"CLOUDFLARE_ACCOUNT_{_env_suffix(account_id)}") if account_id else None,
        os.getenv("CLOUDFLARE_ACCOUNT_ID"),
        os.getenv("CLOUDFLARE_ACCOUNT"),
    ]
    for value in candidatos:
        if _looks_like_secret(value):
            return str(value)
    return ""


def _resolve_api_key(cuenta) -> str:
    _load_local_env()
    account_id = str(cuenta.get("id", "")).strip()
    candidatos = [
        cuenta.get("api_key"),
        os.getenv(f"CLOUDFLARE_API_TOKEN_{_env_suffix(account_id)}") if account_id else None,
        os.getenv(f"CLOUDFLARE_AUTH_TOKEN_{_env_suffix(account_id)}") if account_id else None,
        os.getenv(f"CLOUDFLARE_API_KEY_{_env_suffix(account_id)}") if account_id else None,
        os.getenv(f"CLOUDFLARE_API_TOKEN_{account_id}") if account_id else None,
        os.getenv(f"CLOUDFLARE_AUTH_TOKEN_{account_id}") if account_id else None,
    ]
    global_token = os.getenv("CLOUDFLARE_API_TOKEN") or os.getenv("CLOUDFLARE_AUTH_TOKEN") or os.getenv("CLOUDFLARE_API_KEY")
    global_account = str(os.getenv("CLOUDFLARE_ACCOUNT_ID") or os.getenv("CLOUDFLARE_ACCOUNT") or "").strip()
    try:
        rows = json.loads((ROOT / "cuentas.json").read_text(encoding="utf-8")).get("proveedores", {}).get("cloudflare", {}).get("cuentas", [])
    except (OSError, ValueError, TypeError):
        rows = []
    target_account = str(cuenta.get("account_id") or cuenta.get("accountId") or "").strip()
    if global_token and (len(rows) == 1 or (global_account and global_account == target_account)):
        candidatos.append(global_token)
    if account_id and account_id[-1].isdigit():
        candidatos.append(os.getenv(f"CLOUDFLARE_API_TOKEN_{account_id[-1]}"))
        candidatos.append(os.getenv(f"CLOUDFLARE_AUTH_TOKEN_{account_id[-1]}"))
        candidatos.append(os.getenv(f"CLOUDFLARE_API_KEY_{account_id[-1]}"))
    for key in candidatos:
        if _looks_like_secret(key):
            return str(key)
    return ""


class ProveedorCloudflare(ProveedorBase):
    """Conecta con Workers AI usando el endpoint OpenAI-compatible."""

    def __init__(self, cuenta):
        super().__init__(cuenta)
        self.account_id = _resolve_account_id(cuenta)
        self.api_key = _resolve_api_key(cuenta)
        self.nombre_app = cuenta.get("nombre_app", "LaGranjaDeIA")

    def construir_url(self):
        if not self.account_id:
            return URL_BASE_CLOUDFLARE.format(account_id="")
        return URL_BASE_CLOUDFLARE.format(account_id=self.account_id)

    def construir_headers(self):
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
            "X-Title": self.nombre_app,
        }
        if self.account_id:
            headers["CF-Account-ID"] = self.account_id
        return headers

    def preparar_body(self, body, modelo):
        """Workers AI acepta el formato OpenAI estándar para chat completions."""
        body_copia = dict(body)
        body_copia["model"] = modelo
        return body_copia

    def tiene_credencial_valida(self):
        return bool(self.api_key and self.account_id)

    def identificar(self):
        key_corta = self.api_key[-6:] if len(self.api_key) > 6 else "***"
        acct_corta = self.account_id[-6:] if len(self.account_id) > 6 else self.account_id or "***"
        return f"cloudflare:{self.id_cuenta}:{acct_corta}(***{key_corta})"
