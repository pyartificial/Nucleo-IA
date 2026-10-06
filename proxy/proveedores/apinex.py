"""Proveedor APInex, API compatible con OpenAI."""
from __future__ import annotations
import os, re
from pathlib import Path
from proxy.proveedores.base import ProveedorBase

URL_BASE_APINEX = "https://api.apinex.bond/v1/chat/completions"
ROOT = Path(__file__).resolve().parents[2]

def _load_env():
    for name in (".env", "granja.env"):
        try:
            for line in (ROOT / name).read_text(encoding="utf-8").splitlines():
                if "=" in line and not line.lstrip().startswith("#"):
                    k, v = line.removeprefix("export ").split("=", 1)
                    os.environ.setdefault(k.strip(), v.strip().strip("\"'"))
        except OSError: pass

def _key(cuenta):
    _load_env(); ident = re.sub(r"[^A-Za-z0-9]+", "_", str(cuenta.get("id", "")).upper()).strip("_")
    for value in (cuenta.get("api_key"), os.getenv("APINEX_API_KEY_" + ident), os.getenv("APINEX_API_KEY")):
        if value and str(value).startswith("sk-") and len(str(value)) >= 20:
            return str(value).strip()
    return ""

class ProveedorAPInex(ProveedorBase):
    def __init__(self, cuenta):
        super().__init__(cuenta); self.api_key = _key(cuenta)
        self.url_base = (cuenta.get("url_base") or URL_BASE_APINEX).rstrip("/")
    def construir_url(self):
        return self.url_base + ("/chat/completions" if self.url_base.endswith("/v1") else "")
    def construir_headers(self):
        return {"Authorization": "Bearer " + self.api_key, "Content-Type": "application/json", "User-Agent": "Nucleo-IA/1.0"}
    def tiene_credencial_valida(self): return bool(self.api_key)
    def identificar(self): return f"apinex:{self.id_cuenta}(***{self.api_key[-6:]})"
