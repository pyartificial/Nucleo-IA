#!/usr/bin/env python3
"""Ranking global unificado para Núcleo IA.

Lee los rankings de todos los proveedores configurados, conserva rutas
separadas entre servicios y ordena todo con la misma base de puntaje.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime

from ranking_common import agrupar_por_modelo_base
from ranking_quality import (
    AA_RELEASES_URL,
    LMARENA_DATASET_URL,
    PESOS_CALIDAD as PESOS_DEFAULT,
    aplicar_calidad,
    cargar_evidencia,
    cargar_evidencia_lmarena,
    normalizar_nombre,
)

RAIZ = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.append(os.path.dirname(__file__))
STATE_DIR = os.path.join(RAIZ, "state")
RANKING_OLLAMA_CANDIDATOS = [
    os.path.join(STATE_DIR, "ranking_ollama.json"),
    os.path.join(STATE_DIR, "ranking_modelos.json"),
]
RANKING_OPENROUTER = os.path.join(STATE_DIR, "ranking_openrouter.json")
RANKING_NVIDIA = os.path.join(STATE_DIR, "ranking_nvidia.json")
RANKING_CLOUDFLARE = os.path.join(STATE_DIR, "ranking_cloudflare.json")
RANKING_COHERE = os.path.join(STATE_DIR, "ranking_cohere.json")
RANKING_COHERE_CAPACIDADES = os.path.join(STATE_DIR, "ranking_cohere_capacidades.json")
RANKING_GOOGLE = os.path.join(STATE_DIR, "ranking_google.json")
RANKING_SILICONFLOW = os.path.join(STATE_DIR, "ranking_siliconflow.json")
RANKING_ZHIPU = os.path.join(STATE_DIR, "ranking_zhipu.json")
RANKING_GROQ = os.path.join(STATE_DIR, "ranking_groq.json")
RANKING_CEREBRAS = os.path.join(STATE_DIR, "ranking_cerebras.json")
RANKING_MISTRAL = os.path.join(STATE_DIR, "ranking_mistral.json")
RANKING_DEEPSEEK = os.path.join(STATE_DIR, "ranking_deepseek.json")
RANKING_GROK = os.path.join(STATE_DIR, "ranking_grok.json")
RANKING_MINIMAX = os.path.join(STATE_DIR, "ranking_minimax.json")
RANKING_ALIBABA = os.path.join(STATE_DIR, "ranking_alibaba.json")
PASARELAS_FREE = {
    "agnes", "aion", "airforce", "anyapi", "bazaarlink", "dreamprompting",
    "huggingface", "orcarouter", "requesty", "routeway", "sealion", "unorouter",
    "ollama_cloud_api",
}
RANKING_TOKENROUTER = os.path.join(STATE_DIR, "ranking_tokenrouter.json")
RANKING_XKIRO = os.path.join(STATE_DIR, "ranking_xkiro.json")
RANKING_TOKENHARBOR = os.path.join(STATE_DIR, "ranking_tokenharbor.json")
RANKING_APINEX = os.path.join(STATE_DIR, "ranking_apinex.json")
RANKING_GLOBAL = os.path.join(STATE_DIR, "ranking_global.json")
RANKING_SECUNDARIO = os.path.join(STATE_DIR, "ranking_secundario.json")
ROUTE_RANKINGS_DIR = os.path.join(STATE_DIR, "route_rankings")
REFRESH_STATUS = os.path.join(STATE_DIR, "ranking_global_refresh_status.json")
AA_CACHE = os.path.join(STATE_DIR, "ranking_aa_public_cache.json")
LMARENA_CACHE = os.path.join(STATE_DIR, "ranking_lmarena_public_cache.json")
CONFIG_RANKING = os.path.join(RAIZ, "ranking_config.json")

def cargar_configuracion() -> tuple[int, dict[str, float], bool]:
    config = {}
    try:
        with open(CONFIG_RANKING, "r", encoding="utf-8") as archivo:
            config = json.load(archivo)
    except FileNotFoundError:
        pass
    except Exception as exc:
        print(f"  [!] Configuración de ranking inválida; uso valores seguros: {exc}")
    contexto = int(os.environ.get("RANKING_CONTEXT_TARGET", config.get("contexto_objetivo", 150000)))
    pesos = dict(PESOS_DEFAULT)
    for clave, valor in (config.get("pesos") or {}).items():
        if clave in pesos and isinstance(valor, (int, float)) and valor >= 0:
            pesos[clave] = float(valor)
    total = sum(pesos.values())
    if total <= 0:
        pesos = dict(PESOS_DEFAULT)
        total = sum(pesos.values())
    pesos_norm = {clave: 100.0 * valor / total for clave, valor in pesos.items()}
    return contexto, pesos_norm, bool(config.get("contexto_excluye", False))


# El contexto es una señal saturada, no una causa de exclusión.
CONTEXTO_OBJETIVO, PESOS_CALIDAD, CONTEXTO_EXCLUYE = cargar_configuracion()

REFRESH_STEPS = [
    ("ollama_catalogo", ["scripts/ollama_cloud_monitor.py", "--no-set-active-model", "--no-update-rankings"], None),
    ("nvidia", ["scripts/ranking_nvidia.py"], RANKING_NVIDIA),
    ("openrouter", ["scripts/ranking_openrouter.py"], RANKING_OPENROUTER),
    ("cloudflare", ["scripts/ranking_cloudflare.py"], RANKING_CLOUDFLARE),
    ("cohere", ["scripts/ranking_cohere.py"], RANKING_COHERE),
    ("google", ["scripts/ranking_google.py"], RANKING_GOOGLE),
    ("siliconflow", ["scripts/ranking_siliconflow.py"], RANKING_SILICONFLOW),
    ("zhipu", ["scripts/ranking_zhipu.py"], RANKING_ZHIPU),
    ("groq", ["scripts/ranking_groq.py"], RANKING_GROQ),
    ("cerebras", ["scripts/ranking_openai_compatible.py", "cerebras"], RANKING_CEREBRAS),
    ("mistral", ["scripts/ranking_pasarelas_free.py", "mistral"], RANKING_MISTRAL),
    ("deepseek", ["scripts/ranking_openai_compatible.py", "deepseek"], RANKING_DEEPSEEK),
    ("grok", ["scripts/ranking_openai_compatible.py", "grok"], RANKING_GROK),
    ("minimax", ["scripts/ranking_openai_compatible.py", "minimax"], RANKING_MINIMAX),
    ("alibaba", ["scripts/ranking_openai_compatible.py", "alibaba"], RANKING_ALIBABA),
    *[(p, ["scripts/ranking_pasarelas_free.py", p], os.path.join(STATE_DIR, f"ranking_{p}.json")) for p in sorted(PASARELAS_FREE)],
    ("tokenrouter", ["scripts/ranking_tokenrouter.py"], RANKING_TOKENROUTER),
    ("xkiro", ["scripts/ranking_xkiro.py"], RANKING_XKIRO),
    ("tokenharbor", ["scripts/ranking_tokenharbor.py"], RANKING_TOKENHARBOR),
    ("apinex", ["scripts/ranking_apinex.py"], RANKING_APINEX),
    ("ollama", ["scripts/generar_ranking.py"], RANKING_OLLAMA_CANDIDATOS[0]),
]


def refrescar_fuentes() -> tuple[set[str], list[dict]]:
    """Actualiza cada proveedor y acepta solo archivos escritos en esta ejecución."""
    validas: set[str] = set()
    informe: list[dict] = []
    estado_pasos: dict[str, bool] = {}
    for nombre, argumentos, salida in REFRESH_STEPS:
        if nombre == "ollama" and not estado_pasos.get("ollama_catalogo", False):
            informe.append({
                "proveedor": nombre,
                "ok": False,
                "codigo": "dependencia",
                "detalle": "omitido porque falló ollama_catalogo; no se reutiliza el catálogo anterior",
            })
            estado_pasos[nombre] = False
            print("  [FALLO] ollama: catálogo de esta ejecución no disponible", flush=True)
            continue
        inicio = time.time()
        try:
            env = os.environ.copy()
            env["RANKING_FORCE_PROBE"] = "1"
            print(f"  [....] {nombre}", flush=True)
            proc = subprocess.run(
                [sys.executable, *argumentos], cwd=RAIZ,
                capture_output=True, text=True, timeout=900, env=env,
            )
            archivo_nuevo = salida is None or (
                os.path.exists(salida) and os.path.getmtime(salida) >= inicio - 1.0
            )
            ok = proc.returncode == 0 and archivo_nuevo
            detalle = (proc.stderr or proc.stdout or "").strip().splitlines()
            informe.append({
                "proveedor": nombre, "ok": ok, "codigo": proc.returncode,
                "detalle": detalle[-1][:240] if detalle else "",
            })
            if ok and salida:
                validas.add(os.path.basename(salida))
            estado_pasos[nombre] = ok
            print(f"  [{'OK' if ok else 'FALLO'}] {nombre}", flush=True)
        except subprocess.TimeoutExpired:
            informe.append({"proveedor": nombre, "ok": False, "codigo": "timeout", "detalle": "superó 900 segundos"})
            estado_pasos[nombre] = False
            print(f"  [FALLO] {nombre}: timeout")
        except Exception as exc:
            informe.append({"proveedor": nombre, "ok": False, "codigo": "error", "detalle": str(exc)[:240]})
            estado_pasos[nombre] = False
            print(f"  [FALLO] {nombre}: {exc}")
    return validas, informe

def canonizar_modelo(modelo: str) -> str:
    return normalizar_nombre(modelo)


def cargar_json(ruta: str) -> dict:
    if os.path.exists(ruta):
        try:
            with open(ruta, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"  [!] Error cargando {os.path.basename(ruta)}: {e}")
    return {}


def primera_existente(rutas: list[str]) -> str | None:
    for ruta in rutas:
        if os.path.exists(ruta):
            return ruta
    return None


def normalizar_entrada(entrada: dict, proveedor: str, fuente: str) -> dict:
    modelo_base = (
        entrada.get("modelo_base")
        or entrada.get("id")
        or entrada.get("modelo")
        or entrada.get("nombre")
        or "desconocido"
    )
    modelo_id = entrada.get("id") or entrada.get("modelo") or modelo_base
    modelo_canonico = canonizar_modelo(modelo_base)
    capacidades = entrada.get("capacidades") or {}
    caps_norm = entrada.get("capacidades_norm") or {
        "herramientas": bool(capacidades.get("herramientas") or capacidades.get("tools")),
        "reasoning": bool(capacidades.get("reasoning") or capacidades.get("pensamiento") or capacidades.get("razonamiento")),
        "vision": bool(capacidades.get("vision")),
        "audio": bool(capacidades.get("audio")),
    }
    probe_ok = bool(entrada.get("probe_ok", False))
    apto_agente = bool(entrada.get("apto_agente", False)) or (probe_ok and caps_norm.get("herramientas") and caps_norm.get("reasoning"))
    return {
        "modelo_base": modelo_canonico,
        "modelo_original": modelo_base,
        "modelo_id": modelo_id,
        "id": modelo_id,
        "nombre": entrada.get("nombre") or entrada.get("modelo") or modelo_id,
        "proveedor": proveedor,
        "fuente_ranking": fuente,
        "puntaje": int(entrada.get("puntaje", 0) or 0),
        "parametros_b": float(entrada.get("parametros_b", 0.0) or 0.0),
        "contexto": int(entrada.get("contexto", 0) or 0),
        "max_completion_tokens": int(entrada.get("max_completion_tokens", 0) or 0),
        "gratis": bool(entrada.get("gratis", False)),
        "gratis_evidencia": entrada.get("gratis_evidencia", ""),
        "access_tier": entrada.get("access_tier"),
        "pricing": entrada.get("pricing") or {},
        "capacidades_secundarias": entrada.get("capacidades_secundarias", []),
        "modalidades": entrada.get("modalidades", []),
        "adaptador_secundario_implementado": bool(entrada.get("adaptador_secundario_implementado", False)),
        "probe_ok": probe_ok,
        "probe_estado": entrada.get("probe_estado", ""),
        "probe_preview": entrada.get("probe_preview", ""),
        "tool_probe_ok": entrada.get("tool_probe_ok"),
        "tool_probe_estado": entrada.get("tool_probe_estado", ""),
        "reasoning_probe_ok": entrada.get("reasoning_probe_ok"),
        "cuenta_id": entrada.get("cuenta_id"),
        "cuentas_compatibles": entrada.get("cuentas_probe_ok") or entrada.get("cuentas_compatibles", []),
        "instruction_score": entrada.get("instruction_score"),
        "capacidades": capacidades,
        "capacidades_norm": caps_norm,
        "desglose": entrada.get("desglose", ""),
        "apto_agente": apto_agente,
    }


def cargar_entradas(fuentes_validas: set[str] | None = None) -> list[dict]:
    acumulado: list[dict] = []

    ruta_ollama = primera_existente(RANKING_OLLAMA_CANDIDATOS)
    if ruta_ollama:
        datos = cargar_json(ruta_ollama)
        for entrada in datos.get("ranking", []):
            acumulado.append(normalizar_entrada(entrada, "ollama", os.path.basename(ruta_ollama)))

    datos_or = cargar_json(RANKING_OPENROUTER)
    for entrada in datos_or.get("ranking", []) or datos_or.get("ranking_aptos", []):
        if entrada.get("probe_ok"):
            acumulado.append(normalizar_entrada(entrada, "openrouter", os.path.basename(RANKING_OPENROUTER)))

    datos_nv = cargar_json(RANKING_NVIDIA)
    for entrada in datos_nv.get("ranking", []) or datos_nv.get("ranking_final", []):
        if entrada.get("probe_ok"):
            acumulado.append(normalizar_entrada(entrada, "nvidia", os.path.basename(RANKING_NVIDIA)))

    datos_cf = cargar_json(RANKING_CLOUDFLARE)
    for entrada in datos_cf.get("ranking", []) or datos_cf.get("ranking_final", []):
        # Reachable on a plan's free allocation is not proof that each model
        # has a zero price. Only explicitly free models enter automatic routes.
        if entrada.get("probe_ok") and entrada.get("gratis") is True:
            acumulado.append(normalizar_entrada(entrada, "cloudflare", os.path.basename(RANKING_CLOUDFLARE)))

    datos_co = cargar_json(RANKING_COHERE)
    for entrada in datos_co.get("ranking", []) or datos_co.get("ranking_final", []):
        # Cohere distingue explícitamente Trial (gratuito limitado) de
        # Production (facturado). El ranking personal nunca incorpora rutas
        # que no estén marcadas como gratuitas por su proveedor.
        if entrada.get("probe_ok") and entrada.get("gratis", False):
            acumulado.append(normalizar_entrada(entrada, "cohere", os.path.basename(RANKING_COHERE)))

    datos_google = cargar_json(RANKING_GOOGLE)
    for entrada in datos_google.get("ranking", []) or datos_google.get("ranking_final", []):
        if entrada.get("probe_ok"):
            acumulado.append(normalizar_entrada(entrada, "google", os.path.basename(RANKING_GOOGLE)))

    datos_siliconflow = cargar_json(RANKING_SILICONFLOW)
    for entrada in datos_siliconflow.get("ranking", []) or datos_siliconflow.get("ranking_final", []):
        if entrada.get("probe_ok"):
            acumulado.append(normalizar_entrada(entrada, "siliconflow", os.path.basename(RANKING_SILICONFLOW)))

    datos_zhipu = cargar_json(RANKING_ZHIPU)
    for entrada in datos_zhipu.get("ranking", []) or datos_zhipu.get("ranking_final", []):
        if entrada.get("probe_ok"):
            acumulado.append(normalizar_entrada(entrada, "zhipu", os.path.basename(RANKING_ZHIPU)))

    datos_groq = cargar_json(RANKING_GROQ)
    for entrada in datos_groq.get("ranking", []) or datos_groq.get("ranking_final", []):
        if entrada.get("probe_ok"):
            acumulado.append(normalizar_entrada(entrada, "groq", os.path.basename(RANKING_GROQ)))

    for proveedor, ruta in (("cerebras", RANKING_CEREBRAS), ("mistral", RANKING_MISTRAL), ("deepseek", RANKING_DEEPSEEK), ("grok", RANKING_GROK), ("minimax", RANKING_MINIMAX), ("alibaba", RANKING_ALIBABA)):
        datos = cargar_json(ruta)
        for entrada in datos.get("ranking", []):
            if entrada.get("probe_ok"):
                acumulado.append(normalizar_entrada(entrada, proveedor, os.path.basename(ruta)))

    datos_tokenrouter = cargar_json(RANKING_TOKENROUTER)
    for entrada in datos_tokenrouter.get("ranking", []) or datos_tokenrouter.get("ranking_final", []):
        if entrada.get("probe_ok"):
            acumulado.append(normalizar_entrada(entrada, "tokenrouter", os.path.basename(RANKING_TOKENROUTER)))

    datos_xkiro = cargar_json(RANKING_XKIRO)
    for entrada in datos_xkiro.get("ranking", []):
        # xKiro es un gateway con catálogo mixto. Solo entran rutas marcadas
        # free, precio cero y comprobadas con la cuenta local.
        if entrada.get("probe_ok") and entrada.get("gratis", False):
            acumulado.append(normalizar_entrada(entrada, "xkiro", os.path.basename(RANKING_XKIRO)))

    datos_tokenharbor = cargar_json(RANKING_TOKENHARBOR)
    for entrada in datos_tokenharbor.get("ranking", []):
        # Solo IDs :free vistos en el catálogo autenticado de esta ejecución
        # y comprobados realmente con la cuenta local.
        if (
            entrada.get("probe_ok")
            and entrada.get("gratis") is True
            and str(entrada.get("id", "")).lower().endswith(":free")
        ):
            acumulado.append(normalizar_entrada(
                entrada, "tokenharbor", os.path.basename(RANKING_TOKENHARBOR)
            ))

    datos_apinex = cargar_json(RANKING_APINEX)
    for entrada in datos_apinex.get("ranking", []):
        if entrada.get("probe_ok"):
            acumulado.append(normalizar_entrada(entrada, "apinex", os.path.basename(RANKING_APINEX)))

    # Los nuevos gateways tienen catálogos mixtos. Solo las rutas declaradas
    # gratuitas, comprobadas en vivo y disponibles en esta actualización
    # pueden entrar al ranking utilizable por auto.
    for proveedor in PASARELAS_FREE:
        ruta = os.path.join(STATE_DIR, f"ranking_{proveedor}.json")
        datos = cargar_json(ruta)
        for entrada in datos.get("ranking", []):
            if entrada.get("gratis") is True and entrada.get("probe_ok") is True:
                acumulado.append(normalizar_entrada(entrada, proveedor, os.path.basename(ruta)))

    if fuentes_validas is not None:
        acumulado = [e for e in acumulado if e.get("fuente_ranking") in fuentes_validas]
    return acumulado


def generar_ranking_global(refrescar: bool = True) -> dict:
    print("=" * 80)
    print("  RANKING GLOBAL UNIFICADO — Núcleo IA")
    print("=" * 80)

    informe_actualizacion: list[dict] = []
    fuentes_validas: set[str] | None = None
    if refrescar:
        print("\nActualizando proveedores desde el ranking general...")
        fuentes_validas, informe_actualizacion = refrescar_fuentes()
        os.makedirs(STATE_DIR, exist_ok=True)
        with open(REFRESH_STATUS, "w", encoding="utf-8") as archivo:
            json.dump(
                {"generado": datetime.now().isoformat(), "proveedores": informe_actualizacion},
                archivo,
                indent=2,
                ensure_ascii=False,
            )
    else:
        # Una consolidación de diagnóstico no debe borrar el informe de la
        # última actualización integral.
        previo = cargar_json(RANKING_GLOBAL)
        estado_previo = cargar_json(REFRESH_STATUS)
        informe_actualizacion = (
            estado_previo.get("proveedores", [])
            or previo.get("actualizacion_proveedores", [])
        )

    entradas = cargar_entradas(fuentes_validas)
    if not entradas:
        print("[!] No hay rankings locales para consolidar.")
        raise SystemExit(1)

    def cumple_contexto(entrada: dict) -> bool:
        return not CONTEXTO_EXCLUYE or int(entrada.get("contexto", 0) or 0) >= CONTEXTO_OBJETIVO

    entradas_aptas = [e for e in entradas if e.get("apto_agente") and cumple_contexto(e)]
    entradas_secundarias = [e for e in entradas if not e.get("apto_agente") or not cumple_contexto(e)]

    print("\nActualizando evidencia independiente de calidad...")
    filas_aa, estado_aa = cargar_evidencia(AA_CACHE)
    fuentes_lmarena, estado_lmarena = cargar_evidencia_lmarena(LMARENA_CACHE)
    aplicar_calidad(
        entradas_aptas, filas_aa, CONTEXTO_OBJETIVO, PESOS_CALIDAD, fuentes_lmarena
    )
    aplicar_calidad(
        entradas_secundarias, filas_aa, CONTEXTO_OBJETIVO, PESOS_CALIDAD, fuentes_lmarena
    )
    etiqueta_aa = (
        "OK" if estado_aa["actualizada"]
        else "CACHE" if estado_aa["cache"]
        else "SIN DATOS"
    )
    print(f"  [{etiqueta_aa}] Artificial Analysis: {estado_aa['detalle']}")
    etiqueta_lmarena = (
        "OK" if estado_lmarena["actualizada"]
        else "CACHE" if estado_lmarena["cache"]
        else "SIN DATOS"
    )
    print(f"  [{etiqueta_lmarena}] LMArena: {estado_lmarena['detalle']}")

    ranking_plano = sorted(
        entradas_aptas,
        key=lambda x: (
            -float(x.get("puntaje", 0)),
            -float(x.get("componentes_calidad", {}).get("herramientas", 0)),
            -float(x.get("componentes_calidad", {}).get("trabajo_agentico_lmarena", 0)),
            -float(x.get("componentes_calidad", {}).get("trabajo_agentico_aa", 0)),
            -float(x.get("cobertura_evidencia", 0)),
            str(x.get("modelo_base", "")),
            str(x.get("proveedor", "")),
        ),
    )
    for i, entrada in enumerate(ranking_plano):
        entrada["posicion"] = i + 1

    ranking_secundario = sorted(
        entradas_secundarias,
        key=lambda x: (
            -float(x.get("puntaje", 0)),
            -float(x.get("cobertura_evidencia", 0)),
            str(x.get("modelo_base", "")),
        ),
    )
    for i, entrada in enumerate(ranking_secundario):
        entrada["posicion"] = i + 1

    grupos = agrupar_por_modelo_base(ranking_plano)
    capacidades_secundarias = {}
    cohere_caps = {}
    if fuentes_validas is None or os.path.basename(RANKING_COHERE) in fuentes_validas:
        cohere_caps = cargar_json(RANKING_COHERE_CAPACIDADES).get("rankings", {})
    if cohere_caps:
        capacidades_secundarias["cohere"] = cohere_caps
    # Las capacidades secundarias viven también en fuentes con ranker propio
    # (Cloudflare) o con adaptador de pasarela pero política específica (Mistral).
    for proveedor in PASARELAS_FREE | {
        "tokenrouter", "xkiro", "tokenharbor", "cloudflare", "mistral"
    }:
        ruta_caps = os.path.join(STATE_DIR, f"ranking_{proveedor}.json")
        if fuentes_validas is not None and os.path.basename(ruta_caps) not in fuentes_validas:
            continue
        datos_caps = cargar_json(ruta_caps).get("rankings_capacidades", {})
        if datos_caps:
            capacidades_secundarias[proveedor] = datos_caps

    resultado = {
        "generado": datetime.now().isoformat(),
        "total_modelos": len(ranking_plano),
        "total_secundarios": len(ranking_secundario),
        "total_grupos": len(grupos),
        "ranking": ranking_plano,
        "ranking_plano": ranking_plano,
        "ranking_secundario": ranking_secundario,
        "rankings_capacidades": capacidades_secundarias,
        "grupos": grupos,
        "actualizacion_proveedores": informe_actualizacion,
        "actualizacion_evidencia": {
            "artificial_analysis": estado_aa,
            "lmarena": estado_lmarena,
        },
        "ficha_comun": {
            "filtro": ["herramientas", "reasoning", "probe_ok"],
            "peso": PESOS_CALIDAD,
            "contexto_objetivo": CONTEXTO_OBJETIVO,
            "contexto_excluye": CONTEXTO_EXCLUYE,
            "parametros_afectan_puntaje": False,
            "latencia_afecta_puntaje": False,
            "fuentes_externas": [AA_RELEASES_URL, LMARENA_DATASET_URL],
            "nota": "Los mínimos deciden admisión; la evidencia ordena. Los datos ausentes reducen cobertura, no eliminan rutas.",
        },
    }

    os.makedirs(STATE_DIR, exist_ok=True)
    with open(RANKING_GLOBAL, "w", encoding="utf-8") as f:
        json.dump(resultado, f, indent=2, ensure_ascii=False)

    with open(RANKING_SECUNDARIO, "w", encoding="utf-8") as f:
        json.dump({"generado": datetime.now().isoformat(), "total": len(ranking_secundario), "ranking": ranking_secundario}, f, indent=2, ensure_ascii=False)

    # Solo una actualización real y exitosa de todos los proveedores que tienen
    # cuentas locales convierte el catálogo exportable en ranking de esta PC.
    marker = os.path.join(STATE_DIR, "rankings_precargados.json")
    if refrescar and os.path.isfile(marker):
        try:
            with open(os.path.join(RAIZ, "cuentas.json"), encoding="utf-8") as archivo:
                cuentas = json.load(archivo).get("proveedores", {})
            configurados = {
                proveedor for proveedor, datos in cuentas.items()
                if isinstance(datos, dict) and isinstance(datos.get("cuentas", []), list) and datos.get("cuentas")
            }
            salidas = {
                proveedor: os.path.basename(salida)
                for proveedor, _, salida in REFRESH_STEPS if salida
            }
            requeridos = {salidas[x] for x in configurados if x in salidas}
            if requeridos and requeridos.issubset(fuentes_validas or set()):
                os.remove(marker)
        except (OSError, ValueError, TypeError, AttributeError):
            pass

    # Los perfiles cheap/reasoning/tools/vision se cachean en el proxy. Un
    # ranking recién calculado debe invalidarlos para que promociones,
    # descartes y modelos retirados tengan efecto en la siguiente petición.
    if os.path.isdir(ROUTE_RANKINGS_DIR):
        for nombre in os.listdir(ROUTE_RANKINGS_DIR):
            if nombre.startswith("ranking_") and nombre.endswith(".json"):
                try:
                    os.remove(os.path.join(ROUTE_RANKINGS_DIR, nombre))
                except OSError as exc:
                    print(f"  [!] No se pudo invalidar caché de ruta {nombre}: {exc}")

    print(f"\n[+] Ranking global consolidado: {len(ranking_plano)} modelos agénticos aptos | {len(ranking_secundario)} modelos secundarios/refuerzo")
    print("\n  TOP MODELOS AGÉNTICOS (RANKING PRINCIPAL):")
    print(f"  {'POS':>3}  {'PTS':>6}  {'COB':>5}  {'PROVEEDOR':10s}  {'MODELO BASE'}")
    print(f"  {'---':>3}  {'---':>6}  {'---':>5}  {'':->10}  {'':->50}")
    for m in ranking_plano[:12]:
        print(f"  {m['posicion']:>3}  {m['puntaje']:>6.2f}  {m['cobertura_evidencia']:>5.1f}  {m['proveedor']:10s}  {m['modelo_base']}")

    print(f"\nGuardado en: {RANKING_GLOBAL} y {RANKING_SECUNDARIO}")
    return resultado



if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Actualiza y consolida el ranking global de Núcleo IA.")
    parser.add_argument("--no-refresh", action="store_true", help="Consolida archivos existentes sin refrescar proveedores.")
    args = parser.parse_args()
    generar_ranking_global(refrescar=not args.no_refresh)
