#!/usr/bin/env python3
"""
Explorador de modelos OpenRouter para Núcleo IA.
Funciones:
  - Listar todos los modelos disponibles con precios y capacidades
  - Detectar modelos gratuitos
  - Descubrir modelos nuevos comparando con catalogo anterior
  - Verificar creditos/saldo de cada API key
  - Generar mapeo automatico de modelos Ollama -> OpenRouter
"""
import json
import os
import sys
import urllib.request
from datetime import datetime

from secret_utils import get_openrouter_accounts, load_local_env

RAIZ = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
STATE_DIR = os.path.join(RAIZ, "state")
CATALOGO_OR = os.path.join(STATE_DIR, "catalogo_openrouter.json")
CUENTAS_RUTA = os.path.join(RAIZ, "cuentas.json")

URL_MODELOS = "https://openrouter.ai/api/v1/models"
URL_AUTH_KEY = "https://openrouter.ai/api/v1/auth/key"


# ── Obtener modelos ──────────────────────────────────────

def obtener_modelos():
    """Consulta la API publica de modelos de OpenRouter (no requiere auth)."""
    req = urllib.request.Request(URL_MODELOS, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            datos = json.loads(resp.read().decode())
        return datos.get("data", [])
    except Exception as e:
        print(f"  [!] Error obteniendo modelos: {e}")
        return []


def clasificar_modelos(modelos):
    """Clasifica modelos por precio y capacidades."""
    gratis = []
    pagos = []

    for m in modelos:
        precio_prompt = m.get("pricing", {}).get("prompt", "1")
        precio_completion = m.get("pricing", {}).get("completion", "1")
        es_gratis = precio_prompt == "0" and precio_completion == "0"

        params = m.get("supported_parameters", [])
        entrada = {
            "id": m.get("id", "?"),
            "nombre": m.get("name", "?"),
            "contexto": m.get("context_length", 0),
            "max_tokens": m.get("top_provider", {}).get("max_completion_tokens", 0),
            "precio_prompt": precio_prompt,
            "precio_completion": precio_completion,
            "gratis": es_gratis,
            "herramientas": "tools" in params,
            "vision": "image" in m.get("architecture", {}).get("modality", ""),
            "modalidad": m.get("architecture", {}).get("modality", "text->text"),
        }

        if es_gratis:
            gratis.append(entrada)
        else:
            pagos.append(entrada)

    return gratis, pagos


# ── Verificar creditos por API key ───────────────────────

def verificar_creditos_key(api_key):
    """Consulta saldo y limites de una API key de OpenRouter."""
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    req = urllib.request.Request(URL_AUTH_KEY, headers=headers, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            datos = json.loads(resp.read().decode())
        info = datos.get("data", datos)
        return {
            "valida": True,
            "label": info.get("label", "sin nombre"),
            "credito_usado": info.get("usage", 0),
            "limite": info.get("limit", None),
            "limite_restante": info.get("limit_remaining", None),
            "es_free_tier": info.get("is_free_tier", None),
            "tasa_limite_intervalo": info.get("rate_limit", {}).get("interval", "?"),
            "tasa_limite_requests": info.get("rate_limit", {}).get("requests", "?"),
        }
    except urllib.error.HTTPError as e:
        code = e.code
        return {"valida": False, "error": f"HTTP {code}"}
    except Exception as e:
        return {"valida": False, "error": str(e)}


# ── Detectar modelos nuevos ──────────────────────────────

def detectar_nuevos(modelos_actuales):
    """Compara con catalogo anterior y detecta modelos nuevos."""
    if not os.path.exists(CATALOGO_OR):
        return [], []  # Primera ejecucion

    try:
        with open(CATALOGO_OR, "r", encoding="utf-8") as f:
            anterior = json.load(f)
    except Exception:
        return [], []

    ids_anteriores = set(m.get("id", "") for m in anterior.get("modelos", []))
    ids_actuales = set(m.get("id", "") for m in modelos_actuales)

    nuevos = [m for m in modelos_actuales if m.get("id", "") not in ids_anteriores]
    eliminados = ids_anteriores - ids_actuales

    return nuevos, list(eliminados)


# ── Comando principal ────────────────────────────────────

def explorar():
    """Ejecuta exploracion completa de OpenRouter."""
    os.makedirs(STATE_DIR, exist_ok=True)

    # Cargar cuentas OpenRouter
    load_local_env()
    cuentas_or = get_openrouter_accounts()

    print("=" * 65)
    print("  EXPLORADOR OPENROUTER - Núcleo IA")
    print("=" * 65)

    # 1. Obtener modelos
    print("\n[1] Consultando modelos disponibles...")
    modelos = obtener_modelos()
    if not modelos:
        print("  No se pudieron obtener modelos. Abortando.")
        return

    gratis, pagos = clasificar_modelos(modelos)
    print(f"  Total: {len(modelos)} modelos ({len(gratis)} gratis, {len(pagos)} pagos)")

    # 2. Detectar nuevos
    nuevos, eliminados = detectar_nuevos(modelos)
    if nuevos:
        print(f"\n[2] MODELOS NUEVOS ({len(nuevos)}):")
        for m in nuevos:
            precio = m.get("pricing", {})
            es_free = precio.get("prompt", "1") == "0"
            tag = "[GRATIS]" if es_free else f"[${precio.get('prompt','?')}/tok]"
            print(f"  + {m.get('id','?'):50s} {tag}")
    else:
        print("\n[2] Sin modelos nuevos desde la ultima exploracion.")

    if eliminados:
        print(f"\n  Modelos eliminados ({len(eliminados)}):")
        for eid in eliminados[:10]:
            print(f"  - {eid}")

    # 3. Modelos gratis con herramientas (los mas utiles)
    gratis_tools = [m for m in gratis if m["herramientas"]]
    print(f"\n[3] MODELOS GRATIS CON HERRAMIENTAS ({len(gratis_tools)}):")
    print(f"  {'ID':50s} {'CTX':>8}  {'MAX_TOK':>8}  VISION")
    print(f"  {'-'*50} {'-'*8}  {'-'*8}  {'-'*6}")
    for m in sorted(gratis_tools, key=lambda x: x["contexto"], reverse=True):
        vis = "si" if m["vision"] else "no"
        mt = m["max_tokens"] or 0
        print(f"  {m['id']:50s} {m['contexto']:>8}  {mt:>8}  {vis}")

    # 4. Todos los modelos gratis
    print(f"\n[4] TODOS LOS MODELOS GRATIS ({len(gratis)}):")
    for m in sorted(gratis, key=lambda x: x["contexto"], reverse=True):
        tools = "[T]" if m["herramientas"] else "   "
        vis = "[V]" if m["vision"] else "   "
        print(f"  {m['id']:50s} ctx={m['contexto']:>8} {tools} {vis}")

    # 5. Verificar creditos de cada cuenta
    if cuentas_or:
        print(f"\n[5] CREDITOS POR CUENTA ({len(cuentas_or)} keys):")
        print(f"  {'ID':20s} {'ESTADO':10s} {'USADO':>10}  {'LIMITE':>10}  {'RESTANTE':>10}  RATE")
        print(f"  {'-'*20} {'-'*10} {'-'*10}  {'-'*10}  {'-'*10}  {'-'*15}")
        for c in cuentas_or:
            cid = c["id"]
            if not c.get('api_key'):
                print(f"  {cid:20s} [SKIP]     sin api_key en entorno")
                continue
            info = verificar_creditos_key(c["api_key"])
            if info["valida"]:
                usado = info.get("credito_usado", 0)
                limite = info.get("limite")
                restante = info.get("limite_restante")
                rate_req = info.get("tasa_limite_requests", "?")
                rate_int = info.get("tasa_limite_intervalo", "?")

                limite_str = f"${limite:.4f}" if limite else "sin lim"
                restante_str = f"${restante:.4f}" if restante else "N/A"
                usado_str = f"${usado:.4f}" if isinstance(usado, (int, float)) else str(usado)

                estado = "[OK]" if (restante is None or restante > 0) else "[AGOTADA]"
                print(f"  {cid:20s} {estado:10s} {usado_str:>10}  {limite_str:>10}  {restante_str:>10}  {rate_req}/{rate_int}")
            else:
                print(f"  {cid:20s} [ERROR]    {info.get('error','?')}")
    else:
        print("\n[5] No hay cuentas OpenRouter configuradas.")

    # 6. Guardar catalogo
    catalogo_datos = {
        "generado": datetime.now().isoformat(),
        "total": len(modelos),
        "gratis": len(gratis),
        "pagos": len(pagos),
        "gratis_con_tools": len(gratis_tools),
        "modelos": [clasificar_modelo_simple(m) for m in modelos],
        "modelos_gratis": gratis,
    }
    with open(CATALOGO_OR, "w", encoding="utf-8") as f:
        json.dump(catalogo_datos, f, indent=2, ensure_ascii=False)

    print(f"\nCatalogo guardado en: {CATALOGO_OR}")
    print(f"{'=' * 65}")


def clasificar_modelo_simple(m):
    """Crea entrada simplificada para el catalogo."""
    precio = m.get("pricing", {})
    params = m.get("supported_parameters", [])
    return {
        "id": m.get("id", "?"),
        "nombre": m.get("name", "?"),
        "contexto": m.get("context_length", 0),
        "precio_prompt": precio.get("prompt", "?"),
        "precio_completion": precio.get("completion", "?"),
        "gratis": precio.get("prompt", "1") == "0" and precio.get("completion", "1") == "0",
        "herramientas": "tools" in params,
        "vision": "image" in m.get("architecture", {}).get("modality", ""),
    }


if __name__ == "__main__":
    explorar()
