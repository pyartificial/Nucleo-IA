"""
Gestor de modelos multi-proveedor para Núcleo IA.
Consulta rankings de Ollama, OpenRouter, NVIDIA NIM, Cloudflare, Cohere, Google y el Ranking Global.
"""
import json
import os

RAIZ = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
RANKING_OLLAMA = os.path.join(RAIZ, "state", "ranking_modelos.json")
RANKING_OPENROUTER = os.path.join(RAIZ, "state", "ranking_openrouter.json")
RANKING_NVIDIA = os.path.join(RAIZ, "state", "ranking_nvidia.json")
RANKING_CLOUDFLARE = os.path.join(RAIZ, "state", "ranking_cloudflare.json")
RANKING_COHERE = os.path.join(RAIZ, "state", "ranking_cohere.json")
RANKING_GOOGLE = os.path.join(RAIZ, "state", "ranking_google.json")
RANKING_SILICONFLOW = os.path.join(RAIZ, "state", "ranking_siliconflow.json")
RANKING_ZHIPU = os.path.join(RAIZ, "state", "ranking_zhipu.json")
RANKING_GROQ = os.path.join(RAIZ, "state", "ranking_groq.json")
RANKING_TOKENROUTER = os.path.join(RAIZ, "state", "ranking_tokenrouter.json")
RANKING_XKIRO = os.path.join(RAIZ, "state", "ranking_xkiro.json")
RANKING_TOKENHARBOR = os.path.join(RAIZ, "state", "ranking_tokenharbor.json")
RANKING_APINEX = os.path.join(RAIZ, "state", "ranking_apinex.json")
RANKING_APINEX = os.path.join(RAIZ, "state", "ranking_apinex.json")
RANKING_GLOBAL = os.path.join(RAIZ, "state", "ranking_global.json")
PREFERENCIAS_RANKING = os.path.join(RAIZ, "state", "preferencias_ranking.json")
MODELO_DEFAULT = "kimi-k2.6:cloud"

SERVICIOS_VALIDOS = {"ollama", "cloudflare", "nvidia", "openrouter", "cohere", "google", "siliconflow", "zhipu", "groq", "cerebras", "mistral", "deepseek", "grok", "minimax", "alibaba", "tokenrouter", "xkiro", "tokenharbor", "apinex", "agnes", "aion", "airforce", "anyapi", "bazaarlink", "dreamprompting", "huggingface", "orcarouter", "requesty", "routeway", "sealion", "unorouter", "ollama_cloud_api"}


# ── Ranking Global Unificado ────────────────────────────

def cargar_ranking_global():
    """Carga el ranking maestro consolidado."""
    if not os.path.exists(RANKING_GLOBAL):
        return []
    with open(RANKING_GLOBAL, "r", encoding="utf-8") as f:
        ranking = json.load(f).get("ranking", [])
    try:
        with open(PREFERENCIAS_RANKING, "r", encoding="utf-8") as f:
            order = json.load(f).get("ordenes", {}).get("general", [])
        positions = {key: i for i, key in enumerate(order)}
        ranking = sorted(enumerate(ranking), key=lambda pair: (
            positions.get(f"{pair[1].get('proveedor','')}::{pair[1].get('modelo_id') or pair[1].get('id') or pair[1].get('modelo') or ''}", len(positions)), pair[0]))
        ranking = [row for _, row in ranking]
    except (OSError, ValueError, TypeError):
        pass
    return ranking


def _leer_servicios_activos():
    raw = os.getenv("SERVICIOS_ACTIVOS", "").strip()
    if not raw:
        return set(SERVICIOS_VALIDOS)
    seleccionados = {x.strip() for x in raw.split(",") if x.strip()}
    return seleccionados or set(SERVICIOS_VALIDOS)


def _leer_top_rotacion():
    raw = os.getenv("ROTACION_TOP_N", "3").strip()
    try:
        valor = int(raw)
    except Exception:
        valor = 3
    return max(0, valor)


def cargar_ranking_global_agente(requiere_vision=False, servicios_activos=None, top_n=None):
    """Carga el ranking global filtrado para uso por agentes."""
    servicios_activos = set(servicios_activos or _leer_servicios_activos())
    limite_top = top_n if top_n is not None else _leer_top_rotacion()
    ranking = []
    for entrada in cargar_ranking_global():
        if not entrada.get("apto_agente"):
            continue
        if entrada.get("proveedor") not in servicios_activos:
            continue
        if requiere_vision and not entrada.get("capacidades", {}).get("vision"):
            continue
        ranking.append(entrada)
        if limite_top > 0 and len(ranking) >= limite_top * 4:
            break
    return ranking


def es_apto_agente(entrada, requiere_vision=False):
    """Evalua si una entrada de ranking sirve para agentes."""
    if not entrada or not entrada.get("apto_agente"):
        return False
    if requiere_vision and not entrada.get("capacidades", {}).get("vision"):
        return False
    return True


# ── Rankings Ollama ──────────────────────────────────────

def cargar_ranking():
    """Carga ranking de modelos Ollama."""
    if not os.path.exists(RANKING_OLLAMA):
        return []
    with open(RANKING_OLLAMA, "r", encoding="utf-8") as f:
        return json.load(f).get("ranking", [])


def obtener_modelo_preferido():
    """Retorna el modelo Ollama con mayor puntaje."""
    ranking = cargar_ranking()
    return ranking[0]["modelo"] if ranking else MODELO_DEFAULT


def obtener_siguiente_modelo(modelos_agotados, requiere_herramientas=False):
    """Busca el siguiente modelo Ollama disponible en el ranking."""
    ranking = cargar_ranking()
    agotados = set(modelos_agotados)

    for entrada in ranking:
        if entrada["modelo"] in agotados:
            continue
        if requiere_herramientas and not entrada.get("capacidades", {}).get("herramientas"):
            continue
        return entrada["modelo"]

    return None


# ── Rankings OpenRouter ──────────────────────────────────

def cargar_ranking_openrouter():
    """Carga ranking de modelos OpenRouter aptos para agentes."""
    if not os.path.exists(RANKING_OPENROUTER):
        return []
    with open(RANKING_OPENROUTER, "r", encoding="utf-8") as f:
        return json.load(f).get("ranking_aptos", [])


def obtener_siguiente_openrouter(modelos_agotados, requiere_vision=False):
    """Busca el siguiente modelo OpenRouter en el ranking."""
    ranking = cargar_ranking_openrouter()
    agotados = set(modelos_agotados)

    for entrada in ranking:
        mid = entrada.get("id", "")
        if mid in agotados:
            continue
        if requiere_vision and not entrada.get("capacidades", {}).get("vision"):
            continue
        return mid

    return None


# ── Rankings NVIDIA ──────────────────────────────────────

def cargar_ranking_nvidia():
    """Carga ranking de modelos NVIDIA NIM."""
    if not os.path.exists(RANKING_NVIDIA):
        return []
    with open(RANKING_NVIDIA, "r", encoding="utf-8") as f:
        return json.load(f).get("ranking", [])


def cargar_ranking_cloudflare():
    """Carga ranking de modelos Cloudflare Workers AI."""
    if not os.path.exists(RANKING_CLOUDFLARE):
        return []
    with open(RANKING_CLOUDFLARE, "r", encoding="utf-8") as f:
        return json.load(f).get("ranking", [])


def cargar_ranking_cohere():
    """Carga ranking de modelos Cohere."""
    if not os.path.exists(RANKING_COHERE):
        return []
    with open(RANKING_COHERE, "r", encoding="utf-8") as f:
        return json.load(f).get("ranking", [])


def cargar_ranking_google():
    """Carga ranking de modelos Google Gemini."""
    if not os.path.exists(RANKING_GOOGLE):
        return []
    with open(RANKING_GOOGLE, "r", encoding="utf-8") as f:
        return json.load(f).get("ranking", [])


def cargar_ranking_siliconflow():
    """Carga ranking de modelos SiliconFlow."""
    if not os.path.exists(RANKING_SILICONFLOW):
        return []
    with open(RANKING_SILICONFLOW, "r", encoding="utf-8") as f:
        return json.load(f).get("ranking", [])


def cargar_ranking_zhipu():
    """Carga ranking de modelos Zhipu AI."""
    if not os.path.exists(RANKING_ZHIPU):
        return []
    with open(RANKING_ZHIPU, "r", encoding="utf-8") as f:
        return json.load(f).get("ranking", [])


def cargar_ranking_groq():
    """Carga ranking de modelos Groq."""
    if not os.path.exists(RANKING_GROQ):
        return []
    with open(RANKING_GROQ, "r", encoding="utf-8") as f:
        return json.load(f).get("ranking", [])


def cargar_ranking_tokenrouter():
    """Carga ranking de modelos TokenRouter."""
    if not os.path.exists(RANKING_TOKENROUTER):
        return []
    with open(RANKING_TOKENROUTER, "r", encoding="utf-8") as f:
        return json.load(f).get("ranking", [])


def cargar_ranking_xkiro():
    """Carga todas las rutas gratuitas comprobadas de xKiro."""
    if not os.path.exists(RANKING_XKIRO):
        return []
    with open(RANKING_XKIRO, "r", encoding="utf-8") as f:
        return json.load(f).get("ranking", [])


def cargar_ranking_tokenharbor():
    """Carga rutas :free comprobadas de Token Harbor."""
    if not os.path.exists(RANKING_TOKENHARBOR):
        return []
    with open(RANKING_TOKENHARBOR, "r", encoding="utf-8") as f:
        return json.load(f).get("ranking", [])

def cargar_ranking_apinex():
    if not os.path.exists(RANKING_APINEX): return []
    with open(RANKING_APINEX, "r", encoding="utf-8") as f: return json.load(f).get("ranking", [])


def resumen_rankings():
    """Retorna un resumen de todos los rankings."""
    r_global = cargar_ranking_global()
    r_ollama = cargar_ranking()
    r_or = cargar_ranking_openrouter()
    r_nv = cargar_ranking_nvidia()
    r_cf = cargar_ranking_cloudflare()
    r_co = cargar_ranking_cohere()
    r_go = cargar_ranking_google()
    r_sf = cargar_ranking_siliconflow()
    r_zh = cargar_ranking_zhipu()
    r_gq = cargar_ranking_groq()
    r_tr = cargar_ranking_tokenrouter()
    r_xk = cargar_ranking_xkiro()
    r_th = cargar_ranking_tokenharbor()
    r_ax = cargar_ranking_apinex()

    return {
        "global": {
            "total": len(r_global),
            "top_modelo": r_global[0]["modelo_id"] if r_global else "N/A",
            "top_proveedor": r_global[0]["proveedor"] if r_global else "N/A",
        },
        "ollama": {"total": len(r_ollama)},
        "openrouter": {"total": len(r_or)},
        "nvidia": {"total": len(r_nv)},
        "cloudflare": {"total": len(r_cf)},
        "cohere": {"total": len(r_co)},
        "google": {"total": len(r_go)},
        "siliconflow": {"total": len(r_sf)},
        "zhipu": {"total": len(r_zh)},
        "groq": {"total": len(r_gq)},
        "tokenrouter": {"total": len(r_tr)},
        "xkiro": {"total": len(r_xk)},
        "tokenharbor": {"total": len(r_th)},
        "apinex": {"total": len(r_ax)},
        "cerebras": {"total": len(cargar_ranking_proveedor("cerebras"))},
        "mistral": {"total": len(cargar_ranking_proveedor("mistral"))},
        "deepseek": {"total": len(cargar_ranking_proveedor("deepseek"))},
        "grok": {"total": len(cargar_ranking_proveedor("grok"))},
        "minimax": {"total": len(cargar_ranking_proveedor("minimax"))},
        "alibaba": {"total": len(cargar_ranking_proveedor("alibaba"))},
    }


def detectar_proveedor_de_modelo(modelo: str) -> tuple[str, str] | None:
    """
    Detecta el proveedor y el ID de modelo correspondiente para peticiones
    que piden un modelo especifico explicito.
    """
    if not modelo:
        return None
    m_low = modelo.strip().lower()

    # 1. Prefijos directos conocidos
    if m_low.startswith("google/") or m_low.startswith("gemini-"):
        return "google", modelo
    if m_low.startswith("@cf/") or m_low.startswith("cloudflare/") or m_low.startswith("cf/"):
        return "cloudflare", modelo
    if m_low.startswith("nvidia/"):
        return "nvidia", modelo
    if m_low.startswith("groq/"):
        return "groq", modelo.split("/", 1)[1] if "/" in modelo else modelo
    if m_low.startswith("cohere/") or m_low.startswith("command-"):
        return "cohere", modelo.split("/", 1)[1] if m_low.startswith("cohere/") else modelo
    if m_low.startswith("tokenrouter/"):
        return "tokenrouter", modelo.split("/", 1)[1]
    if m_low.startswith("xkiro/"):
        return "xkiro", modelo.split("/", 1)[1]
    if m_low.startswith("tokenharbor/"):
        route = modelo.split("/", 1)[1]
        return ("tokenharbor", route) if route.lower().endswith(":free") else None
    if m_low.startswith("apinex/"):
        return "apinex", modelo.split("/", 1)[1]
    if m_low.startswith("siliconflow/"):
        return "siliconflow", modelo.split("/", 1)[1]
    if (m_low.startswith("z.ai/") or m_low.startswith("zai/") or
            m_low.startswith("zhipu/") or m_low.startswith("glm-")):
        return "zhipu", modelo.split("/", 1)[1] if (
            m_low.startswith("zhipu/") or m_low.startswith("z.ai/") or
            m_low.startswith("zai/")) else modelo
    if m_low.startswith("openrouter/"):
        return "openrouter", modelo.split("/", 1)[1]
    if m_low.startswith("cerebras/"):
        return "cerebras", modelo.split("/", 1)[1]
    if m_low.startswith("mistral/"):
        return "mistral", modelo.split("/", 1)[1]
    if m_low.startswith("deepseek/"):
        return "deepseek", modelo.split("/", 1)[1]
    if m_low.startswith("grok/"):
        return "grok", modelo.split("/", 1)[1]
    if m_low.startswith("minimax/"):
        return "minimax", modelo.split("/", 1)[1]
    if m_low.startswith("qwen/") or m_low.startswith("alibaba/"):
        return "alibaba", modelo.split("/", 1)[1]
    if m_low.startswith("mistral-") or m_low.startswith("ministral-") or m_low.startswith("codestral-"):
        return "mistral", modelo
    if m_low.startswith("cerebras/") or m_low.startswith("llama3."):
        return "cerebras", modelo.split("/", 1)[1] if "/" in modelo else modelo
    if m_low.startswith("deepseek-"):
        return "deepseek", modelo
    if m_low.startswith("grok-"):
        return "grok", modelo
    if m_low.endswith(":cloud"):
        return "ollama", modelo

    # 2. Busqueda en ranking global consolidado
    for entrada in cargar_ranking_global():
        prov = entrada.get("proveedor")
        mid = str(entrada.get("modelo_id") or entrada.get("id") or "")
        m_base = str(entrada.get("modelo_base") or entrada.get("modelo") or "")
        if modelo.lower() in (mid.lower(), m_base.lower()):
            return prov, mid or modelo

    # Un ID :free sin prefijo puede pertenecer a distintos gateways. Primero
    # se resolvió contra el ranking vivo; solo si no existe allí conservamos
    # el fallback histórico de OpenRouter.
    if m_low.endswith(":free"):
        return "openrouter", modelo

    # 3. Busqueda en rankings especificos
    proveedores_check = [
        ("cerebras", lambda: cargar_ranking_proveedor("cerebras")),
        ("mistral", lambda: cargar_ranking_proveedor("mistral")),
        ("deepseek", lambda: cargar_ranking_proveedor("deepseek")),
        ("grok", lambda: cargar_ranking_proveedor("grok")),
        ("minimax", lambda: cargar_ranking_proveedor("minimax")),
        ("alibaba", lambda: cargar_ranking_proveedor("alibaba")),
        ("apinex", cargar_ranking_apinex),
        ("tokenharbor", cargar_ranking_tokenharbor),
        ("xkiro", cargar_ranking_xkiro),
        ("groq", cargar_ranking_groq),
        ("google", cargar_ranking_google),
        ("cohere", cargar_ranking_cohere),
        ("nvidia", cargar_ranking_nvidia),
        ("cloudflare", cargar_ranking_cloudflare),
        ("tokenrouter", cargar_ranking_tokenrouter),
        ("siliconflow", cargar_ranking_siliconflow),
        ("zhipu", cargar_ranking_zhipu),
        ("openrouter", cargar_ranking_openrouter),
        ("ollama", cargar_ranking),
    ]
    for prov, fn in proveedores_check:
        try:
            for entrada in fn():
                mid = str(entrada.get("modelo_id") or entrada.get("id") or "")
                m_base = str(entrada.get("modelo_base") or entrada.get("modelo") or "")
                if modelo.lower() in (mid.lower(), m_base.lower()):
                    return prov, mid or modelo
        except Exception:
            continue

    return None


def cargar_ranking_proveedor(proveedor):
    """Carga un ranking genérico por proveedor descubierto desde la API."""
    ruta = os.path.join(RAIZ, "state", f"ranking_{proveedor}.json")
    if not os.path.exists(ruta):
        return []
    with open(ruta, "r", encoding="utf-8") as f:
        return json.load(f).get("ranking", [])
