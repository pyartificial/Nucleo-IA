#!/usr/bin/env python3
"""Evidencia externa, normalización y puntaje explicable del ranking global."""
from __future__ import annotations

import difflib
import json
import re
import urllib.parse
import urllib.request
import urllib.error
from datetime import datetime

AA_RELEASES_URL = "https://r.jina.ai/https://artificialanalysis.ai/models/releases"
LMARENA_DATASET_URL = "https://huggingface.co/datasets/lmarena-ai/leaderboard-dataset"
LMARENA_ROWS_URL = "https://datasets-server.huggingface.co/rows"
PESOS_CALIDAD = {
    "inteligencia_aa": 24.0,
    "preferencia_lmarena": 6.0,
    "herramientas": 25.0,
    "trabajo_agentico_lmarena": 10.0,
    "trabajo_agentico_aa": 5.0,
    "instrucciones": 15.0,
    "contexto_util": 10.0,
    "multimodal": 5.0,
}


def probar_herramienta_openai(
    url: str,
    api_key: str,
    modelo: str,
    headers_extra: dict[str, str] | None = None,
    timeout: int = 30,
) -> tuple[bool, str]:
    """Prueba determinista de function calling para APIs compatibles con OpenAI."""
    payload_base = {
        "model": modelo,
        "messages": [
            {
                "role": "user",
                "content": "Llama a sumar_numeros con a=17 y b=25. No calcules ni respondas con texto.",
            }
        ],
        "tools": [
            {
                "type": "function",
                "function": {
                    "name": "sumar_numeros",
                    "description": "Suma exactamente dos enteros.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "a": {"type": "integer"},
                            "b": {"type": "integer"},
                        },
                        "required": ["a", "b"],
                    },
                },
            }
        ],
        "temperature": 0,
        "max_tokens": 128,
        "stream": False,
    }
    cabeceras = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "User-Agent": "Nucleo-IA-Ranking/1.0",
    }
    cabeceras.update(headers_extra or {})
    intentos = [
        "required",
        "auto",
        {"type": "function", "function": {"name": "sumar_numeros"}},
    ]
    estados: list[str] = []
    for eleccion in intentos:
        payload = dict(payload_base)
        payload["tool_choice"] = eleccion
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers=cabeceras,
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as respuesta:
                datos = json.loads(respuesta.read().decode("utf-8", "replace"))
            mensaje = ((datos.get("choices") or [{}])[0].get("message") or {})
            llamadas = mensaje.get("tool_calls") or []
            for llamada in llamadas:
                funcion = llamada.get("function") or {}
                if funcion.get("name") != "sumar_numeros":
                    continue
                argumentos = funcion.get("arguments") or "{}"
                if isinstance(argumentos, str):
                    argumentos = json.loads(argumentos)
                if argumentos.get("a") == 17 and argumentos.get("b") == 25:
                    modo = "forzada" if eleccion != "auto" else "auto"
                    return True, f"ok_{modo}"
            estados.append("sin_llamada")
        except urllib.error.HTTPError as exc:
            estados.append(f"http_{exc.code}")
        except Exception as exc:
            estados.append(f"{type(exc).__name__}")
    return False, "/".join(estados)


def normalizar_nombre(texto: str) -> str:
    """Normaliza identidad para benchmarks, sin modificar el ID de la ruta."""
    valor = (texto or "").lower().replace(":", "-").replace("_", "-")
    # LMArena usa etiquetas legibles como "Qwen 3.8 27B", mientras las APIs
    # publican "qwen3.8-27b". El espacio no representa una familia distinta.
    valor = re.sub(r"^qwen\s+(?=\d)", "qwen", valor)
    # Cloudflare antepone @cf/<autor>/ al checkpoint real. Las demás rutas
    # suelen anteponer una sola vez el proveedor o autor conocido.
    valor = re.sub(r"^@cf/", "", valor)
    prefijos = r"(?:google|openai|nvidia|qwen|z-ai|zai|groq)"
    while re.match(rf"^{prefijos}/", valor):
        valor = re.sub(rf"^{prefijos}/", "", valor, count=1)
    valor = re.sub(r"(?:-cloud|-free|-api)$", "", valor)
    valor = re.sub(r"[^a-z0-9]+", "-", valor).strip("-")
    valor = re.sub(rf"^{prefijos}-", "", valor)
    alias = {
        "gemma4": "gemma-4-31b",
        "gemma4-31b": "gemma-4-31b",
        "nemotron-3-super": "nemotron-3-super-120b-a12b",
        "nemotron-3-nano-30b": "nemotron-3-nano-30b-a3b",
    }
    return alias.get(valor, valor)


def _descargar_lmarena(config: str) -> list[dict]:
    """Descarga solo la banda `overall` del último snapshot público."""
    filas: list[dict] = []
    offset = 0
    total = None
    while total is None or offset < total:
        consulta = urllib.parse.urlencode({
            "dataset": "lmarena-ai/leaderboard-dataset",
            "config": config,
            "split": "latest",
            "offset": offset,
            "length": 100,
        })
        req = urllib.request.Request(
            f"{LMARENA_ROWS_URL}?{consulta}",
            headers={"User-Agent": "Nucleo-IA-Ranking/1.0"},
        )
        with urllib.request.urlopen(req, timeout=45) as respuesta:
            datos = json.loads(respuesta.read().decode("utf-8", "replace"))
        lote = [item.get("row", {}) for item in datos.get("rows", [])]
        total = int(datos.get("num_rows_total", len(lote)) or len(lote))
        if not lote:
            break
        overall = [fila for fila in lote if fila.get("category") == "overall"]
        filas.extend(overall)
        offset += len(lote)
        # El snapshot está agrupado por categoría: `overall` aparece primero.
        # Cortar al encontrar la categoría siguiente evita bajar ~10.000 filas.
        if filas and len(overall) < len(lote):
            break
    return filas


def cargar_evidencia_lmarena(cache_path: str) -> tuple[dict[str, list[dict]], dict]:
    """Actualiza Agent Arena y Text Arena; conserva caché ante cualquier fallo."""
    estado = {
        "fuente": LMARENA_DATASET_URL,
        "actualizada": False,
        "cache": False,
        "detalle": "",
    }
    try:
        with open(cache_path, "r", encoding="utf-8") as archivo:
            previo = json.load(archivo)
        previo_fuentes = {
            "agent": previo.get("agent", []),
            "text_style_control": previo.get("text_style_control", []),
        }
    except Exception:
        previo_fuentes = {"agent": [], "text_style_control": []}
    try:
        fuentes = {
            "agent": _descargar_lmarena("agent"),
            "text_style_control": _descargar_lmarena("text_style_control"),
        }
        if len(fuentes["agent"]) < 20 or len(fuentes["text_style_control"]) < 100:
            raise ValueError(
                "respuesta incompleta: "
                f"agent={len(fuentes['agent'])}, text={len(fuentes['text_style_control'])}"
            )
        with open(cache_path, "w", encoding="utf-8") as archivo:
            json.dump(
                {
                    "generado": datetime.now().isoformat(),
                    "fuente": LMARENA_DATASET_URL,
                    **fuentes,
                },
                archivo,
                indent=2,
                ensure_ascii=False,
            )
        estado.update({
            "actualizada": True,
            "detalle": (
                f"Agent Arena {len(fuentes['agent'])} modelos; "
                f"Text Arena {len(fuentes['text_style_control'])} modelos"
            ),
        })
        return fuentes, estado
    except Exception as exc:
        hay_cache = all(previo_fuentes.values())
        estado.update({
            "cache": hay_cache,
            "detalle": f"{type(exc).__name__}: {str(exc)[:160]}",
        })
        return previo_fuentes, estado


def parsear_lanzamientos(markdown: str) -> list[dict]:
    """Extrae el índice y los rangos visibles del listado público de AA."""
    filas: list[dict] = []
    for linea in markdown.splitlines():
        if not linea.startswith("*   [") or " Intelligence " not in linea:
            continue
        enlace = re.search(
            r"\]\(https://artificialanalysis\.ai/models/(?:releases/)?([^)/]+)\)\s*$",
            linea,
        )
        indice = re.search(r"\bIntelligence\s+(\d+)", linea)
        if not enlace or not indice:
            continue
        slug = enlace.group(1).strip().lower()
        rangos = {
            clave.lower().replace(" & ", "_").replace(" ", "_"): int(valor)
            for clave, valor in re.findall(
                r"(Engineering|Strategy & Ops|Healthcare & Medical|Finance & Accounting|Legal|Economics)\s*\(#(\d+)\)",
                linea,
            )
        }
        filas.append({
            "slug": slug,
            "clave": normalizar_nombre(slug),
            "inteligencia": int(indice.group(1)),
            "rangos": rangos,
            "url": f"https://artificialanalysis.ai/models/{slug}",
        })
    # Evita que una repetición accidental de la página pese dos veces.
    return list({fila["slug"]: fila for fila in filas}.values())


def cargar_evidencia(cache_path: str) -> tuple[list[dict], dict]:
    """Actualiza la fuente; ante un fallo conserva el último caché válido."""
    estado = {
        "fuente": AA_RELEASES_URL,
        "actualizada": False,
        "cache": False,
        "detalle": "",
    }
    try:
        with open(cache_path, "r", encoding="utf-8") as archivo:
            cache_previo = json.load(archivo)
        filas_previas = cache_previo.get("modelos", [])
    except Exception:
        filas_previas = []
    try:
        req = urllib.request.Request(
            AA_RELEASES_URL,
            headers={"User-Agent": "Nucleo-IA-Ranking/1.0"},
        )
        with urllib.request.urlopen(req, timeout=45) as respuesta:
            texto = respuesta.read().decode("utf-8", "replace")
        filas = parsear_lanzamientos(texto)
        if len(filas) < 50:
            raise ValueError(f"respuesta incompleta: {len(filas)} modelos")
        if filas_previas and len(filas) < len(filas_previas) * 0.65:
            raise ValueError(
                f"caída anómala del catálogo: {len(filas_previas)} -> {len(filas)}"
            )
        with open(cache_path, "w", encoding="utf-8") as archivo:
            json.dump(
                {
                    "generado": datetime.now().isoformat(),
                    "fuente": AA_RELEASES_URL,
                    "modelos": filas,
                },
                archivo,
                indent=2,
                ensure_ascii=False,
            )
        estado.update({"actualizada": True, "detalle": f"{len(filas)} fichas públicas"})
        return filas, estado
    except Exception as exc:
        filas = filas_previas
        estado.update(
            {
                "cache": bool(filas),
                "detalle": f"{type(exc).__name__}: {str(exc)[:160]}",
            }
        )
        return filas, estado


def percentil(valor: float, universo: list[float]) -> float:
    if not universo:
        return 50.0
    menores = sum(1 for item in universo if item < valor)
    iguales = sum(1 for item in universo if item == valor)
    return round(100.0 * (menores + 0.5 * iguales) / len(universo), 3)


def buscar_ficha(entrada: dict, filas: list[dict]) -> tuple[dict | None, float]:
    objetivo = normalizar_nombre(
        str(entrada.get("modelo_base") or entrada.get("modelo_id") or "")
    )
    exactas = [f for f in filas if f.get("clave") == objetivo]
    if exactas:
        return exactas[0], 1.0
    if not objetivo or not filas:
        return None, 0.0
    similitud, ficha = max(
        (
            (
                difflib.SequenceMatcher(
                    None, objetivo, str(f.get("clave", ""))
                ).ratio(),
                f,
            )
            for f in filas
        ),
        key=lambda par: par[0],
    )
    # La similitud solo sirve para diagnóstico. Nunca transfiere benchmarks:
    # un cambio pequeño de versión puede representar un modelo distinto.
    return None, round(similitud, 3)


def buscar_ficha_lmarena(entrada: dict, filas: list[dict]) -> dict | None:
    """Une únicamente identidades exactas ya normalizadas."""
    objetivo = normalizar_nombre(
        str(entrada.get("modelo_base") or entrada.get("modelo_id") or "")
    )
    for fila in filas:
        if normalizar_nombre(str(fila.get("model_name", ""))) == objetivo:
            return fila
    return None


def aplicar_calidad(
    entradas: list[dict],
    filas: list[dict],
    contexto_objetivo: int,
    pesos: dict[str, float] | None = None,
    lmarena: dict[str, list[dict]] | None = None,
) -> None:
    """Ordena por evidencia; la falta de datos nunca elimina una ruta admitida."""
    pesos_efectivos = pesos or PESOS_CALIDAD
    universo = [float(f["inteligencia"]) for f in filas if "inteligencia" in f]
    total_publicados = max(len(filas), 1)
    fuentes_lmarena = lmarena or {}
    filas_agent = fuentes_lmarena.get("agent", [])
    filas_text = fuentes_lmarena.get("text_style_control", [])
    universo_agent = [
        float(f.get("score_ci_lower", f.get("score")))
        for f in filas_agent if f.get("score_ci_lower", f.get("score")) is not None
    ]
    universo_text = [
        float(f.get("rating_lower", f.get("rating")))
        for f in filas_text if f.get("rating_lower", f.get("rating")) is not None
    ]
    for entrada in entradas:
        ficha, certeza_alias = buscar_ficha(entrada, filas)
        ficha_agent = buscar_ficha_lmarena(entrada, filas_agent)
        ficha_text = buscar_ficha_lmarena(entrada, filas_text)
        caps = entrada.get("capacidades_norm", {}) or {}
        rango_ing = (ficha or {}).get("rangos", {}).get("engineering")
        tool_probe = entrada.get("tool_probe_ok")
        tool_estado = str(entrada.get("tool_probe_estado", "") or "")
        inconclusa = any(
            marca in tool_estado.lower()
            for marca in (
                "timeout", "timed out", "urlerror", "connection", "temporarily",
                "http_429", "http_5",
            )
        )
        if tool_probe is False and inconclusa:
            tool_probe = None
        instruction_score = entrada.get("instruction_score")
        componentes = {
            "inteligencia_aa": (
                percentil(float(ficha["inteligencia"]), universo)
                if ficha
                else 50.0
            ),
            "preferencia_lmarena": (
                percentil(
                    float(ficha_text.get("rating_lower", ficha_text.get("rating"))),
                    universo_text,
                )
                if ficha_text else 50.0
            ),
            "herramientas": 100.0 if tool_probe is True else 0.0 if tool_probe is False else 50.0,
            "trabajo_agentico_lmarena": (
                percentil(
                    float(ficha_agent.get("score_ci_lower", ficha_agent.get("score"))),
                    universo_agent,
                )
                if ficha_agent else 50.0
            ),
            "trabajo_agentico_aa": (
                max(
                    0.0,
                    100.0
                    * (1.0 - (rango_ing - 1) / max(total_publicados - 1, 1)),
                )
                if rango_ing
                else 50.0
            ),
            "instrucciones": float(instruction_score) if instruction_score is not None else 50.0,
            "contexto_util": min(
                100.0,
                100.0
                * int(entrada.get("contexto", 0) or 0)
                / max(contexto_objetivo, 1),
            ),
            "multimodal": 100.0 if caps.get("vision") else 0.0,
        }
        componentes = {k: round(v, 3) for k, v in componentes.items()}
        cobertura = pesos_efectivos.get("contexto_util", 0.0) + pesos_efectivos.get("multimodal", 0.0)
        if ficha:
            cobertura += pesos_efectivos.get("inteligencia_aa", 0.0)
        if ficha_text:
            cobertura += pesos_efectivos.get("preferencia_lmarena", 0.0)
        if ficha_agent:
            cobertura += pesos_efectivos.get("trabajo_agentico_lmarena", 0.0)
        if rango_ing:
            cobertura += pesos_efectivos.get("trabajo_agentico_aa", 0.0)
        if tool_probe is not None:
            cobertura += pesos_efectivos.get("herramientas", 0.0)
        if instruction_score is not None:
            cobertura += pesos_efectivos.get("instrucciones", 0.0)
        cobertura = round(min(100.0, cobertura), 3)
        entrada["puntaje_origen"] = entrada.get("puntaje", 0)
        entrada["puntaje"] = round(
            sum(
                componentes[clave] * pesos_efectivos[clave] / 100.0
                for clave in pesos_efectivos
            ),
            3,
        )
        entrada["componentes_calidad"] = componentes
        entrada["cobertura_evidencia"] = cobertura
        entrada["confianza"] = round(0.60 + 0.40 * cobertura / 100.0, 3)
        entrada["evidencia_aa"] = {
            "encontrada": bool(ficha),
            "certeza_alias": certeza_alias,
            "slug": ficha.get("slug") if ficha else None,
            "indice_crudo": ficha.get("inteligencia") if ficha else None,
            "url": ficha.get("url") if ficha else None,
        }
        entrada["evidencia_lmarena"] = {
            "agent": {
                "encontrada": bool(ficha_agent),
                "score": ficha_agent.get("score") if ficha_agent else None,
                "score_ci_lower": ficha_agent.get("score_ci_lower") if ficha_agent else None,
                "session_count": ficha_agent.get("session_count") if ficha_agent else None,
                "fecha": ficha_agent.get("leaderboard_publish_date") if ficha_agent else None,
            },
            "text_style_control": {
                "encontrada": bool(ficha_text),
                "rating": ficha_text.get("rating") if ficha_text else None,
                "rating_lower": ficha_text.get("rating_lower") if ficha_text else None,
                "vote_count": ficha_text.get("vote_count") if ficha_text else None,
                "fecha": ficha_text.get("leaderboard_publish_date") if ficha_text else None,
            },
            "url": LMARENA_DATASET_URL,
        }
        entrada["evidencia_local"] = {
            "tool_probe_ok": tool_probe,
            "tool_probe_estado": tool_estado or "no_ejecutada",
            "tool_probe_inconclusa": inconclusa,
            "instruction_score": instruction_score,
        }
