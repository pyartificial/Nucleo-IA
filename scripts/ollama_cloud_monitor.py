#!/usr/bin/env python3
"""Monitoreo de Ollama Cloud para Núcleo IA.

Qué hace:
- descubre candidatos cloud desde ollama.com/library
- suma candidatos conocidos desde ollama-farm-kit/catalog.json
- verifica cada candidato con `ollama show` en las cuentas de `cuentas.json`
- extrae contexto, parámetros y capacidades del propio `ollama show`
- escribe state/catalogo_modelos.json para el ranking
- opcionalmente actualiza ranking_modelos.json, ranking_global.json y ACTIVE_MODEL

No usa paquetes externos.
"""
from __future__ import annotations

import argparse
import csv
import html
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import atexit
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from threading import Lock


RAIZ = Path(__file__).resolve().parent.parent
STATE_DIR = RAIZ / "state"
CUENTAS_RUTA = RAIZ / "cuentas.json"
CATALOGO_PORTATIL = RAIZ / "ollama-farm-kit" / "catalog.json"
CLOUD_SOURCES = RAIZ / "scripts" / "cloud_sources.json"
GRANJA_ENV = RAIZ / "granja.env"

CATALOGO_URL = "https://ollama.com/library"
SEARCH_URL = "https://r.jina.ai/https://ollama.com/search?c=cloud&c=tools&c=thinking&o=newest"
LIBRARY_URL = "https://r.jina.ai/https://ollama.com/library/{slug}"
USER_AGENT = "ollama-cloud-monitor/2.0"

CATALOGO_SALIDA = STATE_DIR / "catalogo_modelos.json"
ESTADO_SALIDA = STATE_DIR / "ollama_cloud_estado.json"
CSV_SALIDA = STATE_DIR / "ollama_cloud_reporte.csv"
MEJOR_SALIDA = STATE_DIR / "mejor_modelo_ollama.json"

# El monitor solo conserva y cierra las instancias que él mismo inició. Si la
# granja ya estaba activa, nunca toca su proceso.
_MONITOR_PROCESSES: dict[str, subprocess.Popen[Any]] = {}
_MONITOR_LOCKS: dict[str, Lock] = {}

CAPS_DEFAULT = {
    "herramientas": False,
    "razonamiento": False,
    "vision": False,
    "audio": False,
    "contexto": 0,
    "parametros_b": 0.0,
}

# Heurísticas de respaldo cuando el modelo no expone todo en `ollama show`.
CAPACIDADES_CONOCIDAS = {
    "glm-5.2": {"herramientas": True, "razonamiento": True, "vision": False, "audio": False, "contexto": 131072, "parametros_b": 31.0},
    "glm:4.6": {"herramientas": True, "razonamiento": True, "vision": False, "audio": False, "contexto": 131072, "parametros_b": 9.0},
    "glm:5.1": {"herramientas": True, "razonamiento": True, "vision": False, "audio": False, "contexto": 131072, "parametros_b": 31.0},
    "glm:5.2": {"herramientas": True, "razonamiento": True, "vision": False, "audio": False, "contexto": 131072, "parametros_b": 31.0},
    "gpt-oss": {"herramientas": True, "razonamiento": True, "vision": False, "audio": False, "contexto": 131072, "parametros_b": 120.0},
    "kimi-k2.7-code": {"herramientas": True, "razonamiento": True, "vision": True, "audio": False, "contexto": 262144, "parametros_b": 1042.0},
    "kimi-k2.5": {"herramientas": True, "razonamiento": True, "vision": True, "audio": False, "contexto": 262144, "parametros_b": 1042.0},
    "kimi-k2.6": {"herramientas": True, "razonamiento": True, "vision": True, "audio": False, "contexto": 262144, "parametros_b": 1042.0},
    "qwen3": {"herramientas": True, "razonamiento": True, "vision": False, "audio": False, "contexto": 131072, "parametros_b": 7.0},
    "qwen3.5": {"herramientas": True, "razonamiento": True, "vision": True, "audio": False, "contexto": 131072, "parametros_b": 32.0},
    "qwen3.6": {"herramientas": True, "razonamiento": True, "vision": True, "audio": False, "contexto": 131072, "parametros_b": 32.0},
    "deepseek-v3": {"herramientas": True, "razonamiento": True, "vision": False, "audio": False, "contexto": 131072, "parametros_b": 671.0},
    "deepseek-v4": {"herramientas": True, "razonamiento": True, "vision": False, "audio": False, "contexto": 1048576, "parametros_b": 284.0},
    "deepseek-r1": {"herramientas": False, "razonamiento": True, "vision": False, "audio": False, "contexto": 131072, "parametros_b": 671.0},
    "gemma4": {"herramientas": True, "razonamiento": True, "vision": True, "audio": False, "contexto": 131072, "parametros_b": 27.0},
    "mistral-large-3": {"herramientas": True, "razonamiento": True, "vision": True, "audio": False, "contexto": 131072, "parametros_b": 76.0},
    "minimax-m3": {"herramientas": True, "razonamiento": True, "vision": True, "audio": True, "contexto": 524288, "parametros_b": 120.0},
    "minimax-m2.7": {"herramientas": True, "razonamiento": True, "vision": False, "audio": False, "contexto": 131072, "parametros_b": 120.0},
    "minimax-m2.5": {"herramientas": True, "razonamiento": True, "vision": False, "audio": False, "contexto": 131072, "parametros_b": 120.0},
    "gemini-3-flash-preview": {"herramientas": True, "razonamiento": True, "vision": True, "audio": False, "contexto": 131072, "parametros_b": 0.0},
    "nemotron-3-nano": {"herramientas": True, "razonamiento": True, "vision": False, "audio": False, "contexto": 131072, "parametros_b": 4.0},
    "nemotron-3": {"herramientas": True, "razonamiento": True, "vision": True, "audio": True, "contexto": 131072, "parametros_b": 120.0},
    "nemotron-3-ultra": {"herramientas": True, "razonamiento": True, "vision": False, "audio": False, "contexto": 131072, "parametros_b": 120.0},
    "nemotron-3-super": {"herramientas": True, "razonamiento": True, "vision": False, "audio": False, "contexto": 131072, "parametros_b": 120.0},
}


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def http_text(url: str, timeout: float | None) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    # No hay un límite global para descubrir el catálogo. Cada solicitud sí
    # tiene un límite y reintentos para que una sola página caída no congele
    # todo el proceso indefinidamente.
    request_timeout = 30.0 if timeout is None else timeout
    last_error: Exception | None = None
    for attempt in range(3):
        try:
            with urllib.request.urlopen(request, timeout=request_timeout) as response:
                return response.read().decode("utf-8", errors="replace")
        except Exception as exc:
            last_error = exc
            if attempt < 2:
                time.sleep(1.0 + attempt)
    assert last_error is not None
    raise last_error


def tokens_from_library_size(value: str, unit: str) -> int:
    try:
        num = float(value)
    except ValueError:
        return 0
    unit = unit.upper()
    if unit == "K":
        return int(round(num * 1024))
    if unit == "M":
        return int(round(num * 1024 * 1024))
    if unit == "B":
        return int(round(num))
    if unit == "T":
        return int(round(num * 1024 * 1024 * 1024))
    return int(round(num))


def params_b_from_library_size(value: str, unit: str) -> float:
    try:
        num = float(value)
    except ValueError:
        return 0.0
    unit = unit.upper()
    if unit == "T":
        return round(num * 1000.0, 3)
    if unit == "B":
        return round(num, 3)
    if unit == "M":
        return round(num / 1000.0, 3)
    if unit == "K":
        return round(num / 1_000_000.0, 3)
    return round(num, 3)


def detectar_precio_ollama(page: str) -> tuple[bool, str]:
    """Regla deliberadamente binaria: cualquier precio publicado implica no gratis.

    Devuelve (es_gratuito, evidencia). La evidencia se conserva para poder auditar
    por qué un modelo entró o quedó fuera del catálogo.
    """
    text = html.unescape(page)
    # Precios de entrada/salida expresados por token o por millón de tokens.
    price_patterns = (
        r">\s*\$\s*\d+(?:[.,]\d+)?\s*<",
        r"cost\s*/\s*1\s*m\s*tokens?\s*\n\s*\$\s*\d+(?:[.,]\d+)?",
        r"cost\s*(?:per|por)\s*1\s*m\s*tokens?\s*[:\n]\s*\$?\s*\d+(?:[.,]\d+)?",
        r"(?:\$|USD\s*)\s*\d+(?:[.,]\d+)?\s*(?:/\s*(?:1\s*)?m(?:illion)?\s*)?tokens?",
        r"\d+(?:[.,]\d+)?\s*(?:cents?|centavos?)\s*(?:/\s*)?(?:1\s*)?m(?:illion)?\s*tokens?",
        r"(?:input|output|prompt|completion|inference)\s*(?:price|pricing|cost)\b[^\n]{0,100}(?:\$|usd|token)",
        r"(?:price|pricing|cost)\b[^\n]{0,100}(?:\$|usd)\s*\d",
    )
    for pattern in price_patterns:
        match = re.search(pattern, text, flags=re.I)
        if match:
            return False, re.sub(r"\s+", " ", match.group(0)).strip()[:240]
    return True, "sin precio publicado"


def load_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return default
    except (OSError, json.JSONDecodeError):
        return default


def save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def load_accounts() -> list[dict[str, Any]]:
    data = load_json(CUENTAS_RUTA, {})
    return data.get("proveedores", {}).get("ollama", {}).get("cuentas", [])


def _ollama_url(account: dict[str, Any], path: str) -> str:
    return f'http://127.0.0.1:{int(account["puerto"])}{path}'


def _ollama_alive(account: dict[str, Any], timeout: float = 1.5) -> bool:
    try:
        request = urllib.request.Request(_ollama_url(account, "/api/version"))
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status == 200
    except Exception:
        return False


def ensure_ollama_instance(account: dict[str, Any]) -> tuple[bool, str]:
    """Asegura un servidor local para la cuenta sin interferir con la granja."""
    account_id = str(account.get("id", account.get("puerto", "?")))
    lock = _MONITOR_LOCKS.setdefault(account_id, Lock())
    with lock:
        if _ollama_alive(account):
            return True, "ya_activa"
        if account_id in _MONITOR_PROCESSES and _ollama_alive(account, timeout=2.0):
            return True, "iniciada_por_monitor"

        home = Path(str(account.get("ollama_home", "")))
        if not home.is_absolute():
            home = RAIZ / home
        (home / "logs").mkdir(parents=True, exist_ok=True)
        env = os.environ.copy()
        env["HOME"] = str(home)
        env["USERPROFILE"] = str(home)
        env["OLLAMA_HOST"] = f'127.0.0.1:{int(account["puerto"])}'
        env.setdefault("OLLAMA_CONTEXT_LENGTH", "131072")
        env.setdefault("OLLAMA_KEEP_ALIVE", "-1")
        log_path = home / "logs" / "ollama_cloud_monitor.log"
        handle = log_path.open("a", encoding="utf-8")
        try:
            proc = subprocess.Popen(["ollama", "serve"], env=env, stdout=handle, stderr=handle)
        except Exception as exc:
            handle.close()
            return False, f"inicio_{type(exc).__name__}: {exc}"
        _MONITOR_PROCESSES[account_id] = proc
        deadline = time.monotonic() + 12.0
        while time.monotonic() < deadline:
            if _ollama_alive(account, timeout=1.0):
                return True, "iniciada_por_monitor"
            if proc.poll() is not None:
                break
            time.sleep(0.25)
        return False, "servidor_no_disponible"


def _stop_monitor_processes() -> None:
    for proc in _MONITOR_PROCESSES.values():
        if proc.poll() is None:
            proc.terminate()
    for proc in _MONITOR_PROCESSES.values():
        try:
            proc.wait(timeout=3)
        except Exception:
            if proc.poll() is None:
                proc.kill()


atexit.register(_stop_monitor_processes)


def load_portable_candidates() -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}

    for source_path in (CATALOGO_PORTATIL, CLOUD_SOURCES):
        data = load_json(source_path, {"models": []})
        for item in data.get("models", []):
            if isinstance(item, str):
                name = item
                meta = {"name": name}
            else:
                name = item.get("name")
                meta = item
            if name:
                result[name] = meta

    return result



def discover_search_slugs(timeout: float) -> list[str]:
    text = html.unescape(http_text(SEARCH_URL, timeout))
    slugs: list[str] = []
    seen: set[str] = set()
    # Jina puede devolver enlaces absolutos, Markdown o rutas relativas.
    for match in re.finditer(r"(?:https?://ollama\.com)?/library/([A-Za-z0-9._:-]+)", text):
        slug = match.group(1).strip()
        if not slug or slug in seen:
            continue
        seen.add(slug)
        slugs.append(slug)
    return slugs


def parse_library_page(page: str, slug: str, search_rank: int | None = None) -> dict[str, Any]:
    text = html.unescape(page)
    title_match = re.search(r"^Title:\s*(.+)$", text, flags=re.M)
    desc_match = re.search(r"^##\s+(.+)$", text, flags=re.M)
    tags_match = re.search(r"^\s*(vision|tools|thinking|audio|cloud)(?:\s+(?:vision|tools|thinking|audio|cloud))*\s*$", text, flags=re.M)
    context_match = re.search(r"^Context\s*\n\n([0-9.]+)\s*([KMBT])\s*tokens", text, flags=re.M)
    size_match = re.search(r"^Size\s*\n\n([0-9.]+)\s*([KMBT])\s*parameters", text, flags=re.M)
    downloads_match = re.search(r"^([0-9.,]+[KM]?)\s+Downloads\s+Updated\s+(.+?)$", text, flags=re.M)

    tags_line = tags_match.group(0).strip() if tags_match else ""
    tags = {tok.strip().lower() for tok in tags_line.split() if tok.strip()}

    caps = {
        "herramientas": "tools" in tags,
        "razonamiento": "thinking" in tags,
        "vision": "vision" in tags,
        "audio": "audio" in tags,
        "contexto": 0,
        "parametros_b": 0.0,
    }
    gratis, evidencia_precio = detectar_precio_ollama(text)

    if context_match:
        caps["contexto"] = tokens_from_library_size(context_match.group(1), context_match.group(2))
    if size_match:
        caps["parametros_b"] = params_b_from_library_size(size_match.group(1), size_match.group(2))

    nombre = f"{slug}:cloud" if not slug.endswith(":cloud") else slug
    return {
        "nombre": nombre,
        "slug": slug,
        "titulo": title_match.group(1).strip() if title_match else slug,
        "descripcion": desc_match.group(1).strip() if desc_match else "",
        "tags": sorted(tags),
        "uso": "high" if "high" in text.lower() else "",
        "contexto": caps["contexto"],
        "parametros_b": caps["parametros_b"],
        "capacidades": caps,
        "search_rank": search_rank or 0,
        "downloads": downloads_match.group(1).strip() if downloads_match else "",
        "updated": downloads_match.group(2).strip() if downloads_match else "",
        "source": "ollama_search_library",
        "gratis": gratis,
        "precio_estado": "sin_precio" if gratis else "precio_detectado",
        "precio_evidencia": evidencia_precio,
        "url_fuente": f"https://ollama.com/library/{slug}",
    }


def discover_cloud_candidates(timeout: float, workers: int) -> dict[str, dict[str, Any]]:
    slugs = discover_search_slugs(timeout)
    if not slugs:
        raise RuntimeError("No se detectaron modelos en ollama search cloud newest.")
    print(f"Catálogo dinámico: {len(slugs)} fichas encontradas; verificando precio y etiquetas…", flush=True)

    result: dict[str, dict[str, Any]] = {}
    with ThreadPoolExecutor(max_workers=max(1, workers)) as executor:
        futures = {
            executor.submit(http_text, LIBRARY_URL.format(slug=urllib.parse.quote(slug, safe='/._-')), timeout): (slug, idx + 1)
            for idx, slug in enumerate(slugs)
        }
        for future in as_completed(futures):
            slug, rank = futures[future]
            try:
                page = future.result()
                meta = parse_library_page(page, slug, search_rank=rank)
                # La página visual puede contener precios que Jina omite.
                direct_page = http_text(f"https://ollama.com/library/{urllib.parse.quote(slug, safe='/._-')}", timeout)
                direct_free, direct_evidence = detectar_precio_ollama(direct_page)
                if not direct_free:
                    meta["gratis"] = False
                    meta["precio_estado"] = "precio_detectado_html"
                    meta["precio_evidencia"] = direct_evidence
                # Solo se consideran utilizables los modelos sin precio publicado.
                if meta.get("gratis"):
                    # Algunas familias no aceptan `:cloud` genérico y publican
                    # una etiqueta concreta, por ejemplo `:30b-cloud`.
                    tags_found = sorted(set(re.findall(rf"{re.escape(slug)}:([A-Za-z0-9._-]*cloud)\b", page, flags=re.I)))
                    # No inventar slug:cloud cuando la ficha solo publica
                    # variantes concretas (por ejemplo gpt-oss:20b-cloud).
                    if "cloud" in {t.casefold() for t in tags_found} or not tags_found:
                        result[meta["nombre"]] = meta
                    for tag in tags_found:
                        tagged_name = f"{slug}:{tag}"
                        tagged_meta = dict(meta)
                        tagged_meta["nombre"] = tagged_name
                        tagged_meta["tag_cloud"] = tag
                        result[tagged_name] = tagged_meta
            except Exception:
                # Sin página no hay evidencia suficiente para afirmar que es gratis.
                continue
    print(f"Catálogo dinámico: {len(result)} modelos gratuitos candidatos.", flush=True)
    return result


def discover_families(catalog_html: str) -> list[str]:
    families: set[str] = set()
    for block in re.findall(r"<li\\b.*?</li>", catalog_html, flags=re.I | re.S):
        if not re.search(r">\\s*cloud\\s*<", block, flags=re.I):
            continue
        match = re.search(r'href="/library/([^"?#]+)"', block, flags=re.I)
        if match:
            families.add(urllib.parse.unquote(match.group(1)))
    return sorted(families, key=str.casefold)


def discover_tags_for_family(family: str, timeout: float) -> list[str]:
    url = f"{CATALOGO_URL}/{urllib.parse.quote(family, safe='/._-')}"
    page = html.unescape(http_text(url, timeout))
    escaped = re.escape(family)
    tags = {
        f"{family}:{tag}"
        for tag in re.findall(
            rf"(?:/library/)?{escaped}:([A-Za-z0-9._-]*cloud)\\b",
            page,
            flags=re.I,
        )
    }
    if not tags:
        tags.add(f"{family}:cloud")
    return sorted(tags, key=str.casefold)


def discover_cloud_models(timeout: float, workers: int) -> tuple[list[str], list[str]]:
    try:
        candidates = discover_cloud_candidates(timeout, workers)
        return sorted(candidates.keys(), key=str.casefold), []
    except Exception as search_exc:
        catalog_html = http_text(CATALOG_URL, timeout)
        families = discover_families(catalog_html)
        if not families:
            raise RuntimeError("No se detectaron modelos en search ni en el catálogo de Ollama Cloud.") from search_exc

        models: set[str] = set()
        errors: list[str] = [f"search: {search_exc}"]
        with ThreadPoolExecutor(max_workers=max(1, workers)) as executor:
            futures = {executor.submit(discover_tags_for_family, family, timeout): family for family in families}
            for future in as_completed(futures):
                family = futures[future]
                try:
                    models.update(future.result())
                except Exception as exc:
                    models.add(f"{family}:cloud")
                    errors.append(f"{family}: {exc}")

        return sorted(models, key=str.casefold), errors


def parse_show_output(text: str, candidate: dict[str, Any], model_name: str) -> dict[str, Any]:
    caps = dict(CAPS_DEFAULT)
    architecture = ""
    parameters = 0
    context = 0
    in_caps = False

    for raw in text.splitlines():
        line = raw.strip()
        low = line.casefold()

        if not line:
            continue
        if low == "capabilities":
            in_caps = True
            continue

        if in_caps:
            token = low.split()[0]
            if token == "tools":
                caps["herramientas"] = True
            elif token in ("thinking", "reasoning"):
                caps["razonamiento"] = True
            elif token == "vision":
                caps["vision"] = True
            elif token == "audio":
                caps["audio"] = True
            elif token == "completion":
                pass
            else:
                in_caps = False

        m = re.match(r"architecture\s+(\S+)", low)
        if m:
            architecture = m.group(1)
            continue

        m = re.match(r"parameters\s+(\d+)", low)
        if m:
            parameters = int(m.group(1))
            continue

        m = re.match(r"context length\s+(\d+)", low)
        if m:
            context = int(m.group(1))
            continue

    if context == 0:
        context = int(candidate.get("context", 0) or 0)
    if parameters == 0:
        params_guess = float(candidate.get("params_b", candidate.get("parametros_b", 0.0)) or 0.0)
        parameters = int(params_guess * 1_000_000_000) if params_guess else 0

    candidate_caps = candidate.get("capacidades", {}) if isinstance(candidate.get("capacidades", {}), dict) else {}
    if candidate_caps:
        for key in ("herramientas", "razonamiento", "vision", "audio"):
            if not caps.get(key) and candidate_caps.get(key):
                caps[key] = True
    if context == 0 and int(candidate.get("contexto", 0) or 0):
        context = int(candidate.get("contexto", 0) or 0)
    if parameters == 0 and float(candidate.get("parametros_b", 0.0) or 0.0):
        parameters = int(float(candidate.get("parametros_b", 0.0) or 0.0) * 1_000_000_000)

    if not any(caps.values()):
        # Intentamos rescatar algo del catálogo portátil / heurísticas.
        base = model_name.replace(":cloud", "").replace("-cloud", "")
        for key, fallback in CAPACIDADES_CONOCIDAS.items():
            if base == key or base.startswith(key):
                caps.update({k: v for k, v in fallback.items() if k in caps})
                if context == 0:
                    context = int(fallback.get("contexto", 0) or 0)
                if parameters == 0:
                    parameters = int(float(fallback.get("parametros_b", 0.0)) * 1_000_000_000)
                break

    parametros_b = round(parameters / 1_000_000_000, 3) if parameters else float(candidate.get("parametros_b", 0.0) or 0.0)

    return {
        "nombre": model_name,
        "familia": architecture or model_name.split("-")[0].split(":")[0],
        "contexto": context,
        "parametros_b": parametros_b,
        "capacidades": caps,
    }


def ollama_show(account: dict[str, Any], model: str) -> tuple[bool, str]:
    ready, ready_detail = ensure_ollama_instance(account)
    if not ready:
        return False, f"infraestructura_no_disponible: {ready_detail}"
    env = os.environ.copy()
    home = Path(str(account.get("ollama_home", "")))
    if not home.is_absolute():
        home = RAIZ / home
    env["HOME"] = str(home)
    env["OLLAMA_HOST"] = f'127.0.0.1:{account["puerto"]}'

    try:
        proc = subprocess.run(
            ["ollama", "show", model],
            env=env,
            capture_output=True,
            text=True,
            timeout=25,
        )
    except Exception as exc:
        return False, f"{type(exc).__name__}: {exc}"

    if proc.returncode == 0:
        return True, proc.stdout

    err = (proc.stderr or proc.stdout or "").strip()
    return False, err or f"exit_{proc.returncode}"


def ollama_probe_response(account: dict[str, Any], model: str) -> tuple[bool, str]:
    """Prueba mínima tolerante contra la instancia autenticada de esa cuenta."""
    url = f'http://127.0.0.1:{account["puerto"]}/api/chat'
    payload = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": "Responde únicamente: OK"}],
        "stream": False,
        "think": False,
        "options": {"temperature": 0, "num_predict": 128},
    }).encode("utf-8")
    request = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            data = json.loads(response.read().decode("utf-8", errors="replace"))
        message = data.get("message") or {}
        content = str(message.get("content", "")).strip()
        thinking = str(message.get("thinking", "")).strip()
        low = content.casefold()
        if any(marker in low for marker in ("you need to be signed in", "unauthorized", "error:", "failed to")):
            return False, content[:240] or "respuesta_error"
        # Algunos modelos de razonamiento generan tokens en `thinking` antes
        # de entregar el contenido final. No tratar una respuesta vacía como
        # fallo si Ollama terminó correctamente y realmente generó tokens.
        if content:
            return True, content[:240]
        if data.get("done") is True and (thinking or data.get("eval_count", 0)):
            return True, "generacion_ok_sin_contenido_final"
        return False, "respuesta_vacia"
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        return False, f"HTTP {exc.code}: {detail[:200]}"
    except Exception as exc:
        return False, f"{type(exc).__name__}: {exc}"


def ollama_probe_tool(account: dict[str, Any], model: str) -> tuple[bool, str]:
    """Prueba una llamada de herramienta real sin afectar la admisión."""
    url = f'http://127.0.0.1:{account["puerto"]}/api/chat'
    payload_base = {
        "model": model,
        "messages": [{"role": "user", "content": "Llama a sumar_numeros con a=17 y b=25. No respondas con texto."}],
        "tools": [{"type": "function", "function": {
            "name": "sumar_numeros",
            "description": "Suma exactamente dos enteros.",
            "parameters": {
                "type": "object",
                "properties": {"a": {"type": "integer"}, "b": {"type": "integer"}},
                "required": ["a", "b"],
            },
        }}],
        "stream": False,
        "options": {"temperature": 0, "num_predict": 128},
    }
    estados = []
    for incluir_think in (True, False):
        body = dict(payload_base)
        if incluir_think:
            body["think"] = False
        request = urllib.request.Request(
            url,
            data=json.dumps(body).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=120) as response:
                data = json.loads(response.read().decode("utf-8", errors="replace"))
            calls = (data.get("message") or {}).get("tool_calls") or []
            for call in calls:
                function = call.get("function") or {}
                arguments = function.get("arguments") or {}
                if isinstance(arguments, str):
                    arguments = json.loads(arguments)
                if function.get("name") == "sumar_numeros" and arguments.get("a") == 17 and arguments.get("b") == 25:
                    return True, "ok"
            estados.append("sin_llamada")
        except urllib.error.HTTPError as exc:
            estados.append(f"http_{exc.code}")
        except Exception as exc:
            estados.append(type(exc).__name__)
    return False, "/".join(estados)


def candidate_pool(discovery_timeout: float | None = None, workers: int = 8) -> dict[str, dict[str, Any]]:
    # La búsqueda viva es la fuente principal, pero no exclusiva. Ollama puede
    # omitir variantes gratuitas recientes en la búsqueda filtrada; por eso se
    # une con el catálogo portátil/cacheado y todos los candidatos pasan luego
    # por la misma comprobación de precio y acceso real. No es una lista fija:
    # las fuentes web siguen agregando modelos nuevos automáticamente.
    pool: dict[str, dict[str, Any]] = {}
    try:
        search_models = discover_cloud_candidates(timeout=discovery_timeout, workers=workers)
        for name, meta in search_models.items():
            merged = dict(meta)
            merged.setdefault("name", name)
            merged.setdefault("capacidades", meta.get("capacidades", {}))
            pool[name] = merged
    except Exception as exc:
        print(f"La búsqueda filtrada falló: {type(exc).__name__}. Sumando catálogo web alternativo…", flush=True)
        try:
            web_models, _ = discover_cloud_models(timeout=discovery_timeout, workers=workers)
            for name in web_models:
                pool.setdefault(name, {"name": name})
        except Exception as fallback_exc:
            print(f"El catálogo web alternativo falló: {type(fallback_exc).__name__}.", flush=True)

    # Siempre se incorpora el catálogo portátil como segunda fuente. Si un
    # modelo ya apareció en la web, la metadata viva tiene prioridad.
    for name, portable_meta in load_portable_candidates().items():
        if name not in pool:
            pool[name] = dict(portable_meta)
        else:
            for key, value in portable_meta.items():
                pool[name].setdefault(key, value)

    # Todos los candidatos heredados deben pasar por la misma comprobación de
    # precio; así tampoco se cuela un modelo pago por estar guardado.
    for name in list(pool):
        meta = pool[name]
        if "gratis" in meta:
            continue
        slug = str(meta.get("slug") or name)
        slug = re.sub(r":(?:\d+[A-Za-z0-9.-]*-)?cloud$", "", slug)
        slug = re.sub(r":cloud$", "", slug)
        try:
            page = http_text(LIBRARY_URL.format(slug=urllib.parse.quote(slug, safe='/._-')), discovery_timeout)
            gratis, evidencia = detectar_precio_ollama(page)
            direct_page = http_text(f"https://ollama.com/library/{urllib.parse.quote(slug, safe='/._-')}", discovery_timeout)
            direct_free, direct_evidence = detectar_precio_ollama(direct_page)
            if not direct_free:
                gratis, evidencia = False, direct_evidence
            meta["gratis"] = gratis
            meta["precio_estado"] = "sin_precio" if gratis else "precio_detectado"
            meta["precio_evidencia"] = evidencia
            meta["url_fuente"] = f"https://ollama.com/library/{slug}"
            if not gratis:
                del pool[name]
        except Exception:
            # No afirmar gratuidad sin poder leer la ficha.
            del pool[name]
    return pool


def scan_models(accounts: list[dict[str, Any]], workers: int, discovery_timeout: float | None = None) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    pool = candidate_pool(discovery_timeout=discovery_timeout, workers=workers)
    names = sorted(pool.keys(), key=str.casefold)
    state: dict[str, Any] = {"total_candidatos": len(names), "modelos": {}, "rechazados": []}

    def probe(name: str) -> dict[str, Any] | None:
        candidate = pool.get(name, {"name": name})
        aciertos: list[str] = []
        first_text = ""
        last_error = ""
        tool_probe_ok = None
        tool_probe_estado = "no_ejecutada"
        generation_verified = False

        for account in accounts:
            ok, out = ollama_show(account, name)
            if ok:
                # Una generación correcta valida el modelo. Para las demás
                # cuentas, `ollama show` alcanza para confirmar que la ruta está
                # disponible, evitando repetir la misma generación doce veces.
                if generation_verified:
                    aciertos.append(account["id"])
                    continue
                probe_ok, probe_out = ollama_probe_response(account, name)
                if not probe_ok:
                    last_error = f"probe_generacion: {probe_out}"
                    continue
                generation_verified = True
                aciertos.append(account["id"])
                if not first_text:
                    first_text = out
                if tool_probe_ok is None:
                    tool_probe_ok, tool_probe_estado = ollama_probe_tool(account, name)
            else:
                last_error = out

        if not aciertos:
            if last_error and len(state["rechazados"]) < 80:
                state["rechazados"].append({"modelo": name, "detalle": last_error[:240]})
            return None

        parsed = parse_show_output(first_text, candidate, name)
        for key in ("gratis", "precio_estado", "precio_evidencia", "url_fuente", "slug", "search_rank"):
            if key in candidate:
                parsed[key] = candidate[key]
        parsed["cuentas_disponibles"] = aciertos
        parsed["probe_estado"] = "OK_GENERACION"
        parsed["tool_probe_ok"] = tool_probe_ok
        parsed["tool_probe_estado"] = tool_probe_estado
        parsed["verificado"] = now_iso()
        parsed["fuente"] = "ollama_cloud_monitor"
        return parsed

    resultados: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=max(1, workers)) as executor:
        futures = {executor.submit(probe, name): name for name in names}
        for future in as_completed(futures):
            model_name = futures[future]
            try:
                result = future.result()
            except Exception as exc:
                state["rechazados"].append({"modelo": model_name, "detalle": str(exc)[:240]})
                print(f"Modelo {model_name}: error de prueba.", flush=True)
                continue
            if result:
                resultados.append(result)
                state["modelos"][result["nombre"]] = result
                print(f"Modelo {model_name}: verificado en {len(result.get('cuentas_disponibles', []))} cuentas.", flush=True)
            else:
                print(f"Modelo {model_name}: no respondió correctamente.", flush=True)

    resultados.sort(key=lambda x: x["nombre"].casefold())
    state["catalogado_at"] = now_iso()
    state["cuentas"] = [a.get("id", "?") for a in accounts]
    return resultados, state


def catalog_to_csv(path: Path, modelos: list[dict[str, Any]], state: dict[str, Any]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["modelo", "familia", "contexto", "parametros_b", "herramientas", "razonamiento", "vision", "audio", "cuentas", "verificado"],
        )
        writer.writeheader()
        for item in modelos:
            caps = item.get("capacidades", {})
            writer.writerow(
                {
                    "modelo": item.get("nombre", ""),
                    "familia": item.get("familia", ""),
                    "contexto": item.get("contexto", 0),
                    "parametros_b": item.get("parametros_b", 0.0),
                    "herramientas": int(bool(caps.get("herramientas"))),
                    "razonamiento": int(bool(caps.get("razonamiento"))),
                    "vision": int(bool(caps.get("vision"))),
                    "audio": int(bool(caps.get("audio"))),
                    "cuentas": ",".join(item.get("cuentas_disponibles", [])),
                    "verificado": item.get("verificado", ""),
                }
            )


def update_granja_env(model_name: str) -> None:
    try:
        text = GRANJA_ENV.read_text(encoding="utf-8")
    except FileNotFoundError:
        return

    if re.search(r"^ACTIVE_MODEL=.*$", text, flags=re.M):
        text = re.sub(r"^ACTIVE_MODEL=.*$", f'ACTIVE_MODEL="{model_name}"', text, flags=re.M)
    else:
        text = text.rstrip() + f'\nACTIVE_MODEL="{model_name}"\n'

    GRANJA_ENV.write_text(text, encoding="utf-8")


def run_step(title: str, script: str) -> None:
    print(f"\n[{title}] {script}")
    cmd = [sys.executable, str(RAIZ / script)] if script.endswith(".py") else ["bash", str(RAIZ / script)]
    subprocess.run(cmd, check=True)


def print_table(modelos: list[dict[str, Any]]) -> None:
    print("\nMODELO".ljust(34), "CTX".rjust(8), "PTS".rjust(6), "CUENTAS")
    print("-" * 72)
    for item in modelos:
        caps = item.get("capacidades", {})
        pts = 0
        pts += 30 if caps.get("herramientas") else 0
        pts += 25 if caps.get("razonamiento") else 0
        pts += 20 if caps.get("vision") else 0
        pts += 15 if caps.get("audio") else 0
        pts += 10 if int(item.get("contexto", 0) or 0) >= 131072 else 0
        params = float(item.get("parametros_b", 0.0) or 0.0)
        if params >= 100:
            pts += 30
        elif params >= 40:
            pts += 20
        elif params >= 14:
            pts += 12
        elif params >= 7:
            pts += 5
        elif params > 0:
            pts += 2
        print(
            str(item.get("nombre", ""))[:33].ljust(34),
            str(item.get("contexto", 0)).rjust(8),
            str(pts).rjust(6),
            ",".join(item.get("cuentas_disponibles", [])),
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Descubre y actualiza modelos Ollama Cloud para Núcleo IA.")
    parser.add_argument("--timeout", type=float, default=0.0, help="Límite del descubrimiento web; 0 espera sin límite")
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--no-update-rankings", action="store_true", help="No ejecuta ranking_modelos ni ranking_global.")
    parser.add_argument("--no-set-active-model", action="store_true", help="No actualiza ACTIVE_MODEL en granja.env.")
    parser.add_argument("--show-table", action="store_true", help="Muestra tabla resumida al final.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    accounts = load_accounts()
    if not accounts:
        print("ERROR: no hay cuentas Ollama cargadas en cuentas.json", file=sys.stderr)
        return 1

    print("═" * 68)
    print("  OLLAMA CLOUD MONITOR — Núcleo IA")
    print("═" * 68)
    print(f"Cuentas: {len(accounts)} | Host base: 127.0.0.1:{accounts[0].get('puerto', '?')}")

    discovery_timeout = None if args.timeout <= 0 else args.timeout
    discovered, state = scan_models(accounts, args.workers, discovery_timeout=discovery_timeout)
    # Un escaneo vacío es un fallo, no una actualización válida. No se debe
    # presentar el catálogo anterior como si hubiese sido probado ahora.
    if not discovered:
        state["estado"] = "fallido"
        state["error"] = "El escaneo no verificó ningún modelo; no se reemplazó el catálogo válido anterior."
        save_json(ESTADO_SALIDA, state)
        print("ERROR: el escaneo no verificó ningún modelo; no se reemplazó el catálogo anterior.", file=sys.stderr)
        return 2
    save_json(CATALOGO_SALIDA, {"total": len(discovered), "generado": now_iso(), "modelos": discovered})
    save_json(ESTADO_SALIDA, state)
    catalog_to_csv(CSV_SALIDA, discovered, state)

    print(f"\nCatálogo guardado en: {CATALOGO_SALIDA}")
    print(f"Estado guardado en:   {ESTADO_SALIDA}")
    print(f"Reporte CSV:          {CSV_SALIDA}")
    print(f"Modelos disponibles:  {len(discovered)}")

    if args.show_table:
        print_table(discovered)

    if discovered and not args.no_set_active_model:
        top = max(
            discovered,
            key=lambda m: (
                int(bool(m.get("capacidades", {}).get("herramientas"))) * 30
                + int(bool(m.get("capacidades", {}).get("razonamiento"))) * 25
                + int(bool(m.get("capacidades", {}).get("vision"))) * 20
                + int(bool(m.get("capacidades", {}).get("audio"))) * 15
                + (10 if int(m.get("contexto", 0) or 0) >= 131072 else 0)
                + (30 if float(m.get("parametros_b", 0.0) or 0.0) >= 100 else 0)
                + (20 if float(m.get("parametros_b", 0.0) or 0.0) >= 40 else 0)
                + (12 if float(m.get("parametros_b", 0.0) or 0.0) >= 14 else 0)
                + (5 if float(m.get("parametros_b", 0.0) or 0.0) >= 7 else 0)
                + (2 if float(m.get("parametros_b", 0.0) or 0.0) > 0 else 0),
                float(m.get("contexto", 0) or 0),
                float(m.get("parametros_b", 0.0) or 0.0),
            ),
        )
        update_granja_env(top.get("nombre", ""))
        save_json(MEJOR_SALIDA, {"mejor_modelo": top.get("nombre", ""), "generado": now_iso(), "detalle": top})
        print(f"Modelo activo sugerido: {top.get('nombre', '')}")
        print(f"Guardado en: {MEJOR_SALIDA}")

    if not args.no_update_rankings:
        run_step("RANK", "scripts/generar_ranking.py")
        run_step("GLOBAL", "scripts/ranking_global.py")

    print("\nListo.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
