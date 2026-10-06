import os
import threading
import time
from proxy.registrador import obtener_uso_cuenta, obtener_uso_global_minuto

MAX_POR_CUENTA_HORA = int(os.getenv("MAX_REQUESTS_POR_CUENTA_HORA", 15))
MAX_POR_CUENTA_SEMANA = int(os.getenv("MAX_REQUESTS_POR_CUENTA_SEMANA", 200))
MAX_GLOBAL_MINUTO = int(os.getenv("MAX_REQUESTS_GLOBAL_MINUTO", 90))
_lock = threading.Lock()
_reservas_global: list[float] = []
_reservas_cuenta: dict[str, list[float]] = {}


class ResultadoLimite:
    def __init__(self, permitido, razon=None, espera_seg=0):
        self.permitido = permitido
        self.razon = razon
        self.espera_seg = espera_seg

    def __bool__(self):
        return self.permitido


def verificar(cuenta_id):
    # Global
    uso_min = obtener_uso_global_minuto()
    if uso_min >= MAX_GLOBAL_MINUTO:
        return ResultadoLimite(False, f"global_minuto ({uso_min}/{MAX_GLOBAL_MINUTO})", 30)

    # Cuenta hora
    uso = obtener_uso_cuenta(cuenta_id)
    if uso["hora"] >= MAX_POR_CUENTA_HORA:
        return ResultadoLimite(False, f"cuenta_hora ({uso['hora']}/{MAX_POR_CUENTA_HORA})", 600)

    # Cuenta semana
    if uso["semana"] >= MAX_POR_CUENTA_SEMANA:
        return ResultadoLimite(False, f"cuenta_semana ({uso['semana']}/{MAX_POR_CUENTA_SEMANA})", 3600)

    return ResultadoLimite(True)


def reservar(cuenta_id):
    """Comprueba y reserva el intento de forma atómica para evitar ráfagas paralelas."""
    now = time.time()
    with _lock:
        _reservas_global[:] = [ts for ts in _reservas_global if now - ts < 60]
        cuenta = _reservas_cuenta.setdefault(cuenta_id, [])
        cuenta[:] = [ts for ts in cuenta if now - ts < 7 * 24 * 3600]
        minuto = len(_reservas_global)
        hora = sum(now - ts < 3600 for ts in cuenta)
        semana = len(cuenta)
        uso = obtener_uso_cuenta(cuenta_id)
        uso_global = obtener_uso_global_minuto()
        total_minuto = max(minuto, uso_global)
        total_hora = max(hora, int(uso.get("hora", 0)))
        total_semana = max(semana, int(uso.get("semana", 0)))
        if total_minuto >= MAX_GLOBAL_MINUTO:
            return ResultadoLimite(False, f"global_minuto ({total_minuto}/{MAX_GLOBAL_MINUTO})", 60)
        if total_hora >= MAX_POR_CUENTA_HORA:
            return ResultadoLimite(False, f"cuenta_hora ({total_hora}/{MAX_POR_CUENTA_HORA})", 3600)
        if total_semana >= MAX_POR_CUENTA_SEMANA:
            return ResultadoLimite(False, f"cuenta_semana ({total_semana}/{MAX_POR_CUENTA_SEMANA})", 3600)
        _reservas_global.append(now)
        cuenta.append(now)
        return ResultadoLimite(True)
