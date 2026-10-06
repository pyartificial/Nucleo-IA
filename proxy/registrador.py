import json
import os
import threading
from datetime import datetime, timedelta

RAIZ = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
STATE_DIR = os.path.join(RAIZ, "state")
CONTADORES_RUTA = os.path.join(STATE_DIR, "contadores_uso.json")

_lock = threading.Lock()
_contadores = {"por_cuenta": {}, "global": {"minuto_actual": 0, "ultimo_reset_minuto": None}, "historial": []}


def _ahora():
    return datetime.now()


def _init_cuenta(cid):
    ahora = _ahora()
    _contadores["por_cuenta"][cid] = {
        "hora": 0, "semana": 0, "tokens_totales": 0,
        "ultimo_reset_hora": ahora.isoformat(),
        "ultimo_reset_semana": ahora.isoformat(),
    }


def cargar_contadores():
    global _contadores
    if os.path.exists(CONTADORES_RUTA):
        try:
            with open(CONTADORES_RUTA, "r", encoding="utf-8") as f:
                _contadores = json.load(f)
        except Exception:
            pass


def guardar_contadores():
    os.makedirs(STATE_DIR, exist_ok=True)
    tmp_path = os.path.join(STATE_DIR, f"contadores_uso.tmp.{os.getpid()}")
    with _lock:
        try:
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(_contadores, f, indent=2, ensure_ascii=False)
            os.replace(tmp_path, CONTADORES_RUTA)
        except Exception:
            if os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except Exception:
                    pass


def _verificar_resets(cid):
    ahora = _ahora()
    if cid not in _contadores["por_cuenta"]:
        _init_cuenta(cid)
    datos = _contadores["por_cuenta"][cid]

    try:
        ult_h = datetime.fromisoformat(datos["ultimo_reset_hora"])
    except (ValueError, TypeError):
        ult_h = ahora - timedelta(hours=2)
    if ahora - ult_h >= timedelta(hours=1):
        datos["hora"] = 0
        datos["ultimo_reset_hora"] = ahora.isoformat()

    try:
        ult_s = datetime.fromisoformat(datos["ultimo_reset_semana"])
    except (ValueError, TypeError):
        ult_s = ahora - timedelta(days=8)
    if ahora - ult_s >= timedelta(days=7):
        datos["semana"] = 0
        datos["ultimo_reset_semana"] = ahora.isoformat()

    g = _contadores["global"]
    try:
        ult_m = datetime.fromisoformat(g["ultimo_reset_minuto"])
    except (ValueError, TypeError):
        ult_m = ahora - timedelta(minutes=2)
    if ahora - ult_m >= timedelta(minutes=1):
        g["minuto_actual"] = 0
        g["ultimo_reset_minuto"] = ahora.isoformat()


def registrar_uso(cid, modelo, tokens_prompt=0, tokens_resp=0):
    with _lock:
        _verificar_resets(cid)
        d = _contadores["por_cuenta"][cid]
        d["hora"] += 1
        d["semana"] += 1
        d["tokens_totales"] += tokens_prompt + tokens_resp
        _contadores["global"]["minuto_actual"] += 1
        _contadores["historial"].append({
            "cuenta": cid, "modelo": modelo,
            "tokens": tokens_prompt + tokens_resp,
            "ts": _ahora().isoformat(),
        })
        _contadores["historial"] = _contadores["historial"][-100:]


def obtener_uso_cuenta(cid):
    with _lock:
        _verificar_resets(cid)
        if cid not in _contadores["por_cuenta"]:
            _init_cuenta(cid)
        return dict(_contadores["por_cuenta"][cid])


def obtener_uso_global_minuto():
    with _lock:
        _verificar_resets("__noop__")
        return _contadores["global"]["minuto_actual"]


def obtener_resumen():
    with _lock:
        return {
            "global_minuto": _contadores["global"]["minuto_actual"],
            "por_cuenta": {cid: {"hora": d["hora"], "semana": d["semana"], "tokens_totales": d["tokens_totales"]} 
                           for cid, d in _contadores["por_cuenta"].items()},
            "total_peticiones_historial": len(_contadores["historial"])
        }

