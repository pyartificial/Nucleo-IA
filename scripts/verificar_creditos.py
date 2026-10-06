#!/usr/bin/env python3
"""
Verificador de creditos multi-proveedor para Núcleo IA.
Sondea cuentas de Ollama y OpenRouter para detectar
429/403/402 sin gastar muchos recursos.
"""
import json
import os
import sys
import urllib.request
from datetime import datetime, timedelta

from secret_utils import get_openrouter_accounts, load_local_env

RAIZ = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
STATE_DIR = os.path.join(RAIZ, "state")
ESTADO_SALIDA = os.path.join(STATE_DIR, "estado_cuentas.json")
CUENTAS_RUTA = os.path.join(RAIZ, "cuentas.json")
MODELO_DEFAULT_OLLAMA = "kimi-k2.6:cloud"
MODELO_SONDEO_OPENROUTER = "openai/gpt-4o-mini"


def cargar_config():
    """Carga la configuracion completa."""
    with open(CUENTAS_RUTA, "r", encoding="utf-8") as f:
        return json.load(f)


def sondear_ollama(cuenta, modelo):
    """Sondea una instancia local de Ollama."""
    host = cuenta.get("host", "127.0.0.1")
    puerto = cuenta["puerto"]
    url = f"http://{host}:{puerto}/v1/chat/completions"
    headers = {"Content-Type": "application/json"}
    return _hacer_ping(url, headers, modelo)


def sondear_openrouter(cuenta):
    """Sondea una cuenta de OpenRouter."""
    url = cuenta.get("url_base", "https://openrouter.ai/api/v1/chat/completions")
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {cuenta['api_key']}",
        "X-Title": cuenta.get("nombre_app", "LaGranjaDeIA"),
    }
    return _hacer_ping(url, headers, MODELO_SONDEO_OPENROUTER)


def _hacer_ping(url, headers, modelo):
    """Realiza un ping minimo al endpoint."""
    payload = json.dumps({
        "model": modelo,
        "messages": [{"role": "user", "content": "ping"}],
        "max_tokens": 1,
        "stream": False,
    }).encode()

    req = urllib.request.Request(url, data=payload, headers=headers)

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = json.loads(resp.read().decode())
            if "choices" in body:
                return ("activa", "ok")
            return ("desconocido", "sin_choices")
    except urllib.error.HTTPError as e:
        code = e.code
        body_err = ""
        try:
            body_err = e.read().decode()
        except Exception:
            pass

        if code == 429:
            if "weekly" in body_err.lower():
                return ("bloqueada", "429_semanal")
            elif "daily" in body_err.lower():
                return ("bloqueada", "429_diario")
            return ("bloqueada", "429_sesion")
        if code == 403:
            return ("bloqueada", "403_acceso")
        if code == 402:
            return ("bloqueada", "402_sin_credito")
        if code == 401:
            return ("error", "401_api_key_invalida")
        return ("error", f"http_{code}")
    except Exception as e:
        return ("error", f"{type(e).__name__}")


def verificar():
    """Verifica todas las cuentas de todos los proveedores."""
    modelo_ollama = sys.argv[1] if len(sys.argv) > 1 else MODELO_DEFAULT_OLLAMA
    os.makedirs(STATE_DIR, exist_ok=True)
    config = cargar_config()
    proveedores = config.get("proveedores", {})
    resultados = {}

    print("=" * 60)
    print("  VERIFICACION DE CREDITOS - MULTI-PROVEEDOR")
    print("=" * 60)

    # --- OLLAMA ---
    cuentas_ollama = proveedores.get("ollama", {}).get("cuentas", [])
    if cuentas_ollama:
        print(f"\n[OLLAMA] ({len(cuentas_ollama)} cuentas)")
        print("-" * 40)
        for c in cuentas_ollama:
            etiqueta = f"{c['id']} (:{c.get('puerto', '?')})"
            print(f"  Sondeando {etiqueta}...", end=" ")
            estado, razon = sondear_ollama(c, modelo_ollama)
            icono = {"activa": "[OK]", "bloqueada": "[BLOQ]", "error": "[ERR]"}.get(estado, "[?]")
            print(f"{icono} {estado} - {razon}")
            resultados[c["id"]] = _crear_entrada(estado, razon, "ollama")

    # --- OPENROUTER ---
    cuentas_openrouter = get_openrouter_accounts()
    if cuentas_openrouter:
        print(f"\n[OPENROUTER] ({len(cuentas_openrouter)} cuentas)")
        print("-" * 40)
        for c in cuentas_openrouter:
            key = c.get("api_key")
            if not key:
                print(f"  {c['id']:20s} [SKIP] sin api_key en .env")
                continue
            key_corta = key[-6:]
            etiqueta = f"{c['id']} (***{key_corta})"
            print(f"  Sondeando {etiqueta}...", end=" ")
            estado, razon = sondear_openrouter(c)
            icono = {"activa": "[OK]", "bloqueada": "[BLOQ]", "error": "[ERR]"}.get(estado, "[?]")
            print(f"{icono} {estado} - {razon}")
            resultados[c["id"]] = _crear_entrada(estado, razon, "openrouter")

    # Guardar estado
    salida = {
        "generado": datetime.now().isoformat(),
        "modelo_ollama": modelo_ollama,
        "cuentas": resultados
    }
    with open(ESTADO_SALIDA, "w", encoding="utf-8") as f:
        json.dump(salida, f, indent=2, ensure_ascii=False)

    # Resumen
    print(f"\n{'=' * 60}")
    print("  RESUMEN")
    print(f"{'=' * 60}")
    for tipo in ["ollama", "openrouter"]:
        cuentas_tipo = proveedores.get(tipo, {}).get("cuentas", [])
        if cuentas_tipo:
            cids = [c["id"] for c in cuentas_tipo]
            activas = sum(1 for cid in cids if resultados.get(cid, {}).get("estado") == "activa")
            total = len(cids)
            print(f"  {tipo:12s} {activas}/{total} activas")

    print(f"\nEstado guardado en: {ESTADO_SALIDA}")


def _crear_entrada(estado, razon, tipo):
    """Crea una entrada de estado para una cuenta."""
    entrada = {
        "estado": estado,
        "razon": razon,
        "tipo": tipo,
        "ultimo_check": datetime.now().isoformat()
    }
    if estado == "bloqueada":
        ahora = datetime.now()
        if "semanal" in razon:
            dias = (7 - ahora.weekday()) % 7 or 7
            entrada["bloqueado_hasta"] = (ahora + timedelta(days=dias)).isoformat()
        elif "diario" in razon:
            entrada["bloqueado_hasta"] = (ahora + timedelta(hours=24)).isoformat()
        else:
            entrada["bloqueado_hasta"] = (ahora + timedelta(hours=5)).isoformat()
    return entrada


if __name__ == "__main__":
    verificar()
