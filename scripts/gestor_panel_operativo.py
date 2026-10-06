"""Estado operativo y controles locales del Centro de control."""
from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

from scripts.servicios_backend import peticion_json, escribir_json
from scripts.gestor_rankings_panel import GestorRankings
from scripts.catalogo_capacidades import CAPACIDADES


class ErrorOperacion(ValueError):
    pass


class GestorPanelOperativo:
    CAPACIDADES_BASE = {
        "general": "General", "herramientas": "Herramientas", "razonamiento": "Razonamiento",
    }
    CAPACIDADES = {**CAPACIDADES_BASE, **CAPACIDADES}

    def __init__(self, root: Path, servicios, rankings: GestorRankings):
        self.root = Path(root)
        self.servicios = servicios
        self.rankings = rankings
        self.runtime = self.root / "state" / "proxy_runtime.json"
        self.pause_path = self.root / "state" / "proxy_pausa.json"

    @staticmethod
    def _read(path, default):
        try:
            data = json.loads(Path(path).read_text(encoding="utf-8"))
            return data if isinstance(data, type(default)) else default
        except (OSError, ValueError, TypeError):
            return default

    def _config(self):
        return self.servicios.config()

    def _proxy_json(self, path, timeout=1.2):
        config = self._config()
        port = int(config.get("PROXY_PORT", 8080))
        key = config.get("NUCLEO_ADMIN_KEY", "") if path == "/status" else config.get("NUCLEO_API_KEY", "")
        code, data = peticion_json(f"http://127.0.0.1:{port}{path}", key=key, timeout=timeout)
        return code, data

    def _pid_propio(self):
        runtime = self._read(self.runtime, {})
        try: pid = int(runtime.get("pid", 0))
        except (TypeError, ValueError): return None
        if runtime.get("root") != str(self.root) or pid <= 0 or pid == os.getpid(): return None
        if sys.platform.startswith("win"):
            return pid
        try:
            if Path(f"/proc/{pid}/cwd").resolve() != self.root: return None
            if b"proxy.servidor" not in Path(f"/proc/{pid}/cmdline").read_bytes(): return None
            os.kill(pid, 0)
            return pid
        except (OSError, ValueError):
            return None

    def _pausado(self):
        return bool(self._read(self.pause_path, {}).get("pausado"))

    def _filas_capacidad(self, data, capability):
        if capability == "general": rows = data["general"]
        elif capability == "herramientas": rows = [x for x in data["general"] if "Herramientas" in x["capacidades"]]
        elif capability == "razonamiento": rows = [x for x in data["general"] if "Razonamiento" in x["capacidades"]]
        else: rows = data["capacidades"].get(capability, [])
        return rows

    def estado(self):
        config = self._config(); port = int(config.get("PROXY_PORT", 8080))
        runtime = self._read(self.runtime, {})
        pid_propio = self._pid_propio()
        pertenece_a_esta_copia = bool(pid_propio) and runtime.get("root") == str(self.root.resolve())
        health_code, health = self._proxy_json("/healthz") if pertenece_a_esta_copia else (0, {})
        online = pertenece_a_esta_copia and health_code == 200 and health.get("status") == "ok"
        status = {}
        if online:
            code, status = self._proxy_json("/status", timeout=2)
            if code != 200: status = {}
        rank = self.rankings.resumen()
        route_health = self._read(self.root / "state" / "route_health.json", {}).get("candidatos", {})
        top = {}
        for cap in self.CAPACIDADES:
            rows = []
            for row in self._filas_capacidad(rank, cap):
                health_row = route_health.get(f"{row['proveedor']}:{row['modelo']}", {})
                # Los rankings incluidos en una copia exportable son datos de catálogo.
                # El Resumen solo presenta rutas con cuentas y actividad observada
                # dentro del estado local de esta instalación.
                try:
                    observado = float(health_row.get("last_ok", 0) or 0) > 0 or float(health_row.get("last_fail", 0) or 0) > 0
                except (TypeError, ValueError):
                    observado = False
                if not row.get("cuentas") or not observado:
                    continue
                copy = {k: row[k] for k in ("clave", "nombre", "modelo", "proveedor", "estado")}
                copy.update(cuentas=len(row.get("cuentas", [])), capacidades=row.get("capacidades", []),
                            ultimo_ok=health_row.get("last_ok", 0), ultimo_fallo=health_row.get("last_fail", 0),
                            latencia_ms=health_row.get("last_latency_ms", 0), error=health_row.get("last_error", ""),
                            enfriamiento_hasta=health_row.get("cooldown_until", 0))
                rows.append(copy)
                if len(rows) >= 3:
                    break
            top[cap] = rows
        cuentas_data = self._read(self.root / "cuentas.json", {})
        account_labels = {}
        model_provider = {x["modelo"]: x["proveedor"] for x in rank["general"]}
        for provider, cfg in cuentas_data.get("proveedores", {}).items():
            for account in cfg.get("cuentas", []):
                aid = str(account.get("id", ""))
                account_labels[aid] = {"nombre": str(account.get("email") or account.get("nombre") or aid), "proveedor": provider}
        counters = self._read(self.root / "state" / "contadores_uso.json", {})
        recent = []
        for item in reversed(counters.get("historial", [])[-100:]):
            account = account_labels.get(str(item.get("cuenta", "")), {})
            model = str(item.get("modelo", ""))
            account_id = str(item.get("cuenta", ""))
            if model.lower().startswith(("modelo_test", "test_")) or account_id.lower().startswith(("acc_test", "test_")):
                continue
            recent.append({"tipo": "correcto", "fecha": item.get("ts"), "modelo": model,
                           "proveedor": account.get("proveedor") or model_provider.get(model, ""),
                           "cuenta": account.get("nombre") or str(item.get("cuenta", "")), "tokens": item.get("tokens", 0)})
            if len(recent) >= 10:
                break
        last = recent[0] if recent else None
        active_by_type = status.get("activas_por_tipo", {})
        active_accounts = sum(int(x.get("activas", 0)) for x in active_by_type.values()) if active_by_type else 0
        total_accounts = sum(len(x.get("cuentas", [])) for x in cuentas_data.get("proveedores", {}).values())
        optional = []
        try:
            for service in self.servicios.lista_opcionales().get("servicios", []):
                accounts = service.get("cuentas", [])
                optional.append({
                    "id": service.get("id"),
                    "nombre": service.get("nombre", service.get("id", "")),
                    "habilitado": bool(service.get("habilitado")),
                    "cuentas": len(accounts),
                    "cuentas_habilitadas": sum(1 for account in accounts if account.get("habilitado")),
                    "capacidades": service.get("capacidades", []),
                })
        except (AttributeError, TypeError):
            optional = []
        mode = rank["preferencias"].get("rotacion", {})
        return {
            "proxy": {"estado": "pausado" if online and self._pausado() else "funcionando" if online else "detenido",
                      "online": online, "pausado": self._pausado(), "port": port, "pid": runtime.get("pid") if online else None,
                      "inicio": runtime.get("started_at"), "proceso_propio": bool(self._pid_propio())},
            "cuentas": {"activas": active_accounts, "total": total_accounts, "por_servicio": active_by_type},
            "rotacion": mode, "top": top, "nombres_capacidades": self.CAPACIDADES,
            "proveedores_opcionales": optional,
            "ultimo": last, "actividad": recent, "uso": status.get("resumen_uso", {}),
        }

    def detener(self):
        pid = self._pid_propio()
        if not pid:
            if self._proxy_json("/healthz")[0] == 200:
                raise ErrorOperacion("El proxy responde, pero no pertenece al proceso registrado por esta copia. No se detuvo.")
            return {"mensaje": "Núcleo IA ya estaba detenido."}
        try:
            if sys.platform.startswith("win"):
                subprocess.run(["taskkill", "/PID", str(pid)], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            else:
                os.kill(pid, signal.SIGTERM)
            for _ in range(30):
                if self._proxy_json("/healthz", timeout=.2)[0] != 200: break
                time.sleep(.1)
            self.runtime.unlink(missing_ok=True)
            self.pause_path.unlink(missing_ok=True)
            return {"mensaje": "Núcleo IA se detuvo correctamente."}
        except OSError as exc:
            raise ErrorOperacion("No se pudo detener el proceso de esta copia.") from exc

    def pausar(self, value):
        escribir_json(self.pause_path, {"pausado": bool(value), "actualizado": datetime.now().isoformat(timespec="seconds")})
        return {"mensaje": "Las nuevas solicitudes quedaron pausadas." if value else "Núcleo IA volvió a aceptar solicitudes."}
