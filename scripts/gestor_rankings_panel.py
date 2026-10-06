"""Datos y preferencias seguras del panel visual de rankings."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import time
import re
from datetime import datetime
from pathlib import Path

from scripts.catalogo_capacidades import CAPACIDADES, FUENTES, canonica, orden_guardado
from scripts.catalogo_servicios import SERVICIOS_OPCIONALES
from scripts.ranking_pasarelas_free import CONFIG as PASARELAS_FREE_CONFIG


class ErrorRanking(ValueError):
    pass


def _objetivos_actualizacion(target: str, providers) -> list[str]:
    """Una actualización global ya actualiza todos los proveedores una vez."""
    if target == "todos":
        return ["general"]
    if target == "general" or target in providers:
        return [target]
    raise ErrorRanking("Ese ranking no se puede actualizar desde aquí.")


def _script_actualizacion(root: Path, provider: str) -> tuple[Path, list[str]]:
    """Resuelve el script y sus argumentos para cada servicio del panel."""
    if provider == "general":
        return Path(root) / "scripts" / "ranking_global.py", []
    if provider in PASARELAS_FREE_CONFIG:
        return Path(root) / "scripts" / "ranking_pasarelas_free.py", [provider]
    if provider in {"cerebras", "deepseek", "grok", "minimax", "alibaba"}:
        return Path(root) / "scripts" / "ranking_openai_compatible.py", [provider]
    return Path(root) / "scripts" / f"ranking_{provider}.py", []


def _evento_proveedor_global(line: str):
    """Extrae el proveedor y el resultado de las líneas de progreso global."""
    started = re.search(r"^\[\.{4}\]\s+([a-z0-9_-]+)$", line, re.I)
    if started:
        provider = started.group(1).lower()
        return "inicio", "ollama_cloud_api" if provider == "ollama_catalogo" else provider, None
    finished = re.search(r"^\[(OK|FALLO)\]\s+([a-z0-9_-]+)(?:\s|:|$)", line, re.I)
    if finished:
        provider = finished.group(2).lower()
        return "fin", "ollama_cloud_api" if provider == "ollama_catalogo" else provider, (
            "terminado" if finished.group(1).upper() == "OK" else "error"
        )
    return None


class GestorRankings:
    PROVEEDORES = ("ollama", "groq", "openrouter", "nvidia", "google", "cloudflare", "cohere",
                   "siliconflow", "zhipu", "tokenrouter", "xkiro", "tokenharbor", "apinex",
                   "cerebras", "mistral", "deepseek", "grok", "minimax", "alibaba",
                   "agnes", "aion", "airforce", "anyapi", "bazaarlink", "dreamprompting",
                   "huggingface", "orcarouter", "requesty", "routeway", "sealion", "unorouter",
                   "ollama_cloud_api")
    CAPACIDADES = CAPACIDADES
    MODOS = {"prioridad": "cascada", "rotar_cuentas": "cuentas_primero", "rotar_top": "modelos"}

    def __init__(self, root: Path):
        self.root = Path(root)
        self.state = self.root / "state"
        self.pref_path = self.state / "preferencias_ranking.json"
        self.job_path = self.state / "ranking_panel_trabajo.json"
        self._lock = threading.Lock()
        self._active_process = None
        self._cancel_requested = False

    def _read(self, path, default):
        try:
            value = json.loads(Path(path).read_text(encoding="utf-8"))
            return value if isinstance(value, type(default)) else default
        except (OSError, ValueError, TypeError):
            return default

    def _write(self, path, value):
        path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(path.name + f".tmp.{os.getpid()}")
        tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        os.replace(tmp, path)

    @staticmethod
    def clave(modelo):
        provider = str(modelo.get("proveedor") or modelo.get("service") or "").lower()
        mid = str(modelo.get("modelo_id") or modelo.get("id") or modelo.get("modelo") or modelo.get("nombre") or "")
        return f"{provider}::{mid}"

    def preferencias(self):
        base = {"version": 1, "ordenes": {}, "cuentas_preferidas": {}, "rotacion": {
            "modo": "prioridad", "top_n": 3, "conservar_al_actualizar": True}}
        saved = self._read(self.pref_path, {})
        if isinstance(saved, dict):
            base.update(saved)
            base["ordenes"] = saved.get("ordenes", {}) if isinstance(saved.get("ordenes", {}), dict) else {}
            base["cuentas_preferidas"] = saved.get("cuentas_preferidas", {}) if isinstance(saved.get("cuentas_preferidas", {}), dict) else {}
            base["rotacion"].update(saved.get("rotacion", {}) if isinstance(saved.get("rotacion", {}), dict) else {})
        return base

    def _cuentas(self):
        data = self._read(self.root / "cuentas.json", {})
        result = {}
        opcionales = {x["id"] for x in SERVICIOS_OPCIONALES} | {"deepseek", "grok", "minimax", "alibaba", "cerebras"}
        for provider, cfg in data.get("proveedores", {}).items():
            if provider in opcionales and cfg.get("habilitado") is not True:
                continue
            rows = []
            for acc in cfg.get("cuentas", []):
                if provider in opcionales and acc.get("habilitado") is not True:
                    continue
                aid = str(acc.get("id", ""))
                if not aid: continue
                label = str(acc.get("email") or acc.get("correo") or acc.get("nombre") or aid)
                default_caps = ["speech_generation"] if provider in {"elevenlabs", "speechify"} else []
                rows.append({"id": aid, "nombre": label,
                             "habilitado": acc.get("habilitado") is not False,
                             "uso_pago": bool(acc.get("uso_pago", False)),
                             "conexion_estado": str(acc.get("conexion_estado", "guardada")),
                             "capacidades_habilitadas": list(acc.get("capacidades_habilitadas", default_caps))
                             if isinstance(acc.get("capacidades_habilitadas", default_caps), list) else default_caps})
            result[provider] = rows
        return result

    def _normalizar(self, row, cuentas):
        provider = str(row.get("proveedor") or row.get("service") or "").lower()
        mid = str(row.get("modelo_id") or row.get("id") or row.get("modelo") or row.get("nombre") or "")
        caps = row.get("capacidades_norm") or row.get("capacidades") or {}
        if not isinstance(caps, dict): caps = {}
        labels = []
        for key, label in (("herramientas", "Herramientas"), ("reasoning", "Razonamiento"), ("vision", "Visión"), ("audio", "Audio")):
            if caps.get(key): labels.append(label)
        return {
            "clave": f"{provider}::{mid}", "nombre": str(row.get("nombre") or row.get("modelo_base") or mid),
            "modelo": mid, "proveedor": provider, "puntaje": row.get("puntaje", 0),
            "tamano": row.get("parametros_b", 0), "contexto": row.get("contexto", 0),
            "estado": "Disponible" if row.get("probe_ok", True) else str(row.get("probe_estado") or "Sin respuesta"),
            "capacidades": labels, "cuentas": cuentas.get(provider, []),
            "ultima_prueba": str(row.get("probe_detalle") or row.get("ultima_prueba") or "Sin detalle"),
        }

    @staticmethod
    def _aplicar_orden(rows, order):
        positions = {key: i for i, key in enumerate(order or [])}
        return sorted(rows, key=lambda row: (positions.get(row["clave"], len(positions)), row.get("posicion_automatica", 999999)))

    def resumen(self):
        prefs = self.preferencias(); cuentas = self._cuentas()
        precargado = (self.state / "rankings_precargados.json").is_file()
        # Una copia exportable lleva rankings de referencia para el motor, pero
        # no debe presentarlos como comprobados en esta computadora.
        global_data = {} if precargado else self._read(self.state / "ranking_global.json", {})
        general = [self._normalizar(x, cuentas) for x in global_data.get("ranking", []) if x.get("apto_agente", True)]
        for i, row in enumerate(general): row["posicion_automatica"] = i + 1
        general = self._aplicar_orden(general, prefs["ordenes"].get("general", []))
        secondary_data = {} if precargado else self._read(self.state / "ranking_secundario.json", {})
        secondary = [self._normalizar(x, cuentas) for x in secondary_data.get("ranking", []) if x.get("probe_ok", True)]
        for i, row in enumerate(secondary): row["posicion_automatica"] = i + 1
        secondary = self._aplicar_orden(secondary, prefs["ordenes"].get("secundarios", []))
        services = {}
        for provider in self.PROVEEDORES:
            data = {} if precargado else self._read(self.state / ("ranking_modelos.json" if provider == "ollama" else f"ranking_{provider}.json"), {})
            source = data.get("ranking_final") or data.get("ranking_aptos") or data.get("ranking") or []
            rows = [self._normalizar(dict(x, proveedor=x.get("proveedor", provider)), cuentas) for x in source]
            for i, row in enumerate(rows): row["posicion_automatica"] = i + 1
            services[provider] = self._aplicar_orden(rows, prefs["ordenes"].get("servicio:" + provider, []))
        capabilities = {key: [] for key in self.CAPACIDADES}
        capabilities["vision_image"] = [x for x in general if "Visión" in x["capacidades"]]
        for provider, groups in global_data.get("rankings_capacidades", {}).items():
            if not isinstance(groups, dict): continue
            for cap, source in groups.items():
                canonical = canonica(cap)
                if canonical in capabilities:
                    capabilities[canonical].extend(self._normalizar(dict(x, proveedor=x.get("proveedor", provider)), cuentas) for x in source)
        # Los servicios de medios se publican en capacidades_fuentes aunque no participen del chat general.
        fuentes = {} if precargado else self._read(self.state / "capacidades_fuentes.json", {})
        for provider, info in fuentes.get("proveedores", {}).items():
            if not isinstance(info, dict): continue
            confirmed = info.get("modelos_confirmados", {}) if isinstance(info.get("modelos_confirmados", {}), dict) else {}
            for cap, source_keys in FUENTES.items():
                active_key = next((key for key in source_keys if info.get(key)), None)
                models = confirmed.get(active_key, []) if active_key else []
                # El formato antiguo solo distinguía "video". Stable Video
                # Diffusion es imagen-a-video; CogVideoX admite ambos flujos.
                if cap == "video_generation_image" and not models and info.get("video"):
                    legacy = confirmed.get("video", [])
                    models = [m for m in legacy if "cogvideo" in str(m).lower() or "stable-video" in str(m).lower()]
                if not active_key and not models:
                    continue
                for model in models:
                    capabilities[cap].append(self._normalizar({"proveedor": provider, "id": model, "nombre": model,
                        "probe_ok": True, "probe_detalle": "Registrado para esta capacidad"}, cuentas))
        capabilities["speech_generation"].insert(0, self._normalizar({"proveedor": "edge_tts", "id": "edge-tts",
            "nombre": "Edge TTS (incluido, sin clave)", "probe_ok": True, "probe_detalle": "Disponible al instalar Núcleo IA"}, cuentas))
        if not precargado and cuentas.get("speechify"):
            speechify_accounts = [a for a in cuentas["speechify"] if a.get("habilitado")
                                  and a.get("conexion_estado") == "acceso_comprobado"
                                  and "speech_generation" in a.get("capacidades_habilitadas", [])]
            if speechify_accounts:
                scoped_accounts = dict(cuentas, speechify=speechify_accounts)
                capabilities["speech_generation"].append(self._normalizar({
                    "proveedor": "speechify", "id": "simba-3.2", "nombre": "Speechify Simba 3.2",
                    "probe_ok": True,
                    "probe_detalle": "Cuenta verificada; la voz y cuota se comprueban al sintetizar"}, scoped_accounts))
        if not precargado and cuentas.get("elevenlabs"):
            eleven_speech_accounts = [a for a in cuentas["elevenlabs"] if a.get("habilitado") and
                                      "speech_generation" in a.get("capacidades_habilitadas", [])]
            if eleven_speech_accounts:
                scoped_accounts = dict(cuentas, elevenlabs=eleven_speech_accounts)
                for model, name in (("eleven_v3", "Eleven v3"),
                                    ("eleven_v3_conversational", "Eleven v3 Conversational"),
                                    ("eleven_multilingual_v2", "Eleven Multilingual v2"),
                                    ("eleven_flash_v2_5", "Eleven Flash v2.5"),
                                    ("eleven_flash_v2", "Eleven Flash v2")):
                    capabilities["speech_generation"].append(self._normalizar({"proveedor": "elevenlabs", "id": model,
                        "nombre": name, "probe_ok": True, "probe_detalle": "Usa la voz configurada en la cuenta"}, scoped_accounts))
        for cap, rows in capabilities.items():
            seen = set(); unique = []
            for i, row in enumerate(rows):
                if row["clave"] in seen: continue
                seen.add(row["clave"]); row["posicion_automatica"] = i + 1; unique.append(row)
            capabilities[cap] = self._aplicar_orden(unique, orden_guardado(prefs["ordenes"], cap))
        return {"generado": global_data.get("generado"), "precargado": precargado, "general": general, "secundarios": secondary,
                "servicios": services, "capacidades": capabilities, "nombres_capacidades": self.CAPACIDADES,
                "preferencias": prefs, "trabajo": self._trabajo()}

    def _trabajo(self):
        """Lee el progreso y marca como detenido un proceso que perdió su latido."""
        job = self._read(self.job_path, {"estado": "inactivo"})
        if not isinstance(job, dict):
            return {"estado": "inactivo"}
        if job.get("estado") == "ejecutando":
            last = float(job.get("latido_ts") or job.get("inicio_ts") or 0)
            if not last and job.get("inicio"):
                try:
                    last = datetime.fromisoformat(str(job["inicio"])).timestamp()
                except (TypeError, ValueError, OSError):
                    last = 0
            if last and time.time() - last > 120:
                self._cancel_requested = True
                if self._active_process and self._active_process.poll() is None:
                    try:
                        self._active_process.terminate()
                    except OSError:
                        pass
                job.update({"estado": "detenido", "fin": datetime.now().isoformat(timespec="seconds"),
                            "mensaje": "No hubo avances durante dos minutos. La prueba se detuvo; podés volver a intentarla."})
                self._write(self.job_path, job)
        return job

    def guardar(self, body):
        scope = str(body.get("alcance", "")); order = body.get("orden", [])
        allowed = {"general", "secundarios"} | {"servicio:" + x for x in self.PROVEEDORES} | {"capacidad:" + x for x in self.CAPACIDADES}
        if scope not in allowed or not isinstance(order, list) or len(order) > 1000 or len(set(order)) != len(order):
            raise ErrorRanking("El orden recibido no es válido.")
        valid = {x["clave"] for x in self._rows_scope(scope)}
        if any(not isinstance(x, str) or x not in valid for x in order): raise ErrorRanking("El orden contiene un modelo desconocido.")
        prefs = self.preferencias(); prefs["ordenes"][scope] = order
        account_prefs = body.get("cuentas_preferidas", {})
        all_accounts = {a["id"] for rows in self._cuentas().values() for a in rows}
        if isinstance(account_prefs, dict):
            for key, aid in account_prefs.items():
                if key in valid and (aid == "" or aid in all_accounts):
                    if aid: prefs["cuentas_preferidas"][key] = aid
                    else: prefs["cuentas_preferidas"].pop(key, None)
        # La preferencia de conservar el orden es global para todos los
        # rankings; no debe reactivarse al cambiar de pestaña o servicio.
        rotation = body.get("rotacion", {})
        if isinstance(rotation, dict) and (scope == "general" or "conservar_al_actualizar" in rotation):
            mode = rotation.get("modo", prefs["rotacion"]["modo"])
            if mode not in self.MODOS: raise ErrorRanking("La forma de rotación no es válida.")
            top_n = max(0, min(1000, int(rotation.get("top_n", 3))))
            prefs["rotacion"] = {"modo": mode, "top_n": top_n,
                                  "conservar_al_actualizar": rotation.get("conservar_al_actualizar") is not False}
        prefs["actualizado"] = datetime.now().isoformat(timespec="seconds")
        with self._lock: self._write(self.pref_path, prefs)
        return {"mensaje": "El orden y la rotación quedaron guardados.", "preferencias": prefs}

    def _rows_scope(self, scope):
        data = self.resumen()
        if scope == "general": return data["general"]
        if scope == "secundarios": return data["secundarios"]
        kind, name = scope.split(":", 1)
        return data["servicios" if kind == "servicio" else "capacidades"].get(name, [])

    def restaurar(self, scope):
        prefs = self.preferencias(); prefs["ordenes"].pop(scope, None)
        with self._lock: self._write(self.pref_path, prefs)
        return {"mensaje": "Se restauró el orden automático."}

    def actualizar(self, target, conservar=True):
        # ranking_global.py refresca cada proveedor y consolida con un filtro
        # de fuentes válidas de esta misma ejecución. Ejecutarlo proveedor por
        # proveedor antes causaría llamadas duplicadas y podría reutilizar
        # rankings antiguos tras un fallo parcial.
        targets = _objetivos_actualizacion(target, self.PROVEEDORES)
        # La casilla pertenece a la acción de actualización: conservar su estado
        # evita que la recarga del panel la vuelva a activar inmediatamente.
        prefs = self.preferencias()
        prefs.setdefault("rotacion", {})["conservar_al_actualizar"] = bool(conservar)
        with self._lock:
            self._write(self.pref_path, prefs)
        scripts = []
        for item in targets:
            script, argumentos = _script_actualizacion(self.root, item)
            if not script.exists():
                raise ErrorRanking("No está disponible el comprobador de ese servicio.")
            scripts.append((item, script, argumentos))
        status = self._trabajo()
        if status.get("estado") == "ejecutando" or (self._active_process and self._active_process.poll() is None):
            raise ErrorRanking("Ya hay una actualización en curso.")
        started = time.time()
        self._cancel_requested = False
        seguimiento_global = target in {"todos", "general"}
        servicios_seguimiento = list(self.PROVEEDORES) if seguimiento_global else [targets[0]]
        self._write(self.job_path, {"estado": "ejecutando", "objetivo": target,
            "inicio": datetime.now().isoformat(timespec="seconds"), "inicio_ts": started,
            "latido_ts": started, "etapa": "Preparando pruebas", "servicio_actual": "",
            "modelo_actual": "", "total": len(servicios_seguimiento), "completados": 0, "exitosos": 0,
            "fallos": 0, "eventos": 0, "servicios": servicios_seguimiento,
            "servicios_terminados": [], "historial": [],
            "mensaje": "La comprobación está comenzando."})

        def update(**changes):
            current = self._read(self.job_path, {})
            current.update(changes, latido_ts=time.time())
            self._write(self.job_path, current)

        def run():
            log = self.state / "ranking_panel_actualizacion.log"
            resultados = []
            estados_proveedores: dict[str, str] = {}
            try:
                with open(log, "a", encoding="utf-8") as output:
                    for index, (item, script, argumentos) in enumerate(scripts):
                        if self._cancel_requested:
                            break
                        update(etapa=f"Probando {item}", servicio_actual=item,
                               modelo_actual="", completados=index,
                               mensaje=f"Comprobando el catálogo de {item}…")
                        child_env = dict(os.environ)
                        child_env["PYTHONUNBUFFERED"] = "1"
                        command = [sys.executable, str(script), *argumentos]
                        proc = subprocess.Popen(command, cwd=self.root,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                            bufsize=1, start_new_session=True, env=child_env)
                        self._active_process = proc
                        timeout_timer = threading.Timer(1800, proc.terminate)
                        timeout_timer.daemon = True
                        timeout_timer.start()
                        eventos = 0
                        historial = []
                        for line in proc.stdout:
                            clean = re.sub(r"\s+", " ", line).strip()
                            if not clean:
                                continue
                            output.write(f"[{item}] {clean}\n"); output.flush()
                            eventos += 1
                            historial.append(clean[:240]); historial = historial[-8:]
                            model_match = re.search(r"\b(?:modelo|model|probando)\s*[:=]?\s*([^\s,;]+)", clean, re.I)
                            model = model_match.group(1)[:160] if model_match else ""
                            update(eventos=int(self._read(self.job_path, {}).get("eventos", 0)) + 1,
                                   ultimo_evento=clean[:240], historial=historial,
                                   modelo_actual=model or self._read(self.job_path, {}).get("modelo_actual", ""),
                                   mensaje=f"{item}: {clean[:180]}")
                            if seguimiento_global:
                                evento = _evento_proveedor_global(clean)
                                if evento:
                                    accion, provider, estado = evento
                                    if provider in self.PROVEEDORES:
                                        if accion == "fin" and estado:
                                            estados_proveedores[provider] = estado
                                        live_rows = [{"objetivo": name, "estado": value}
                                                     for name, value in estados_proveedores.items()]
                                        update(servicio_actual=provider,
                                               etapa=(f"Comprobando {provider}" if accion == "inicio" else f"Resultado de {provider}"),
                                               completados=len(live_rows),
                                               exitosos=sum(x["estado"] == "terminado" for x in live_rows),
                                               fallos=sum(x["estado"] == "error" for x in live_rows),
                                               servicios_terminados=live_rows,
                                               mensaje=(f"Consultando {provider}…" if accion == "inicio"
                                                        else f"{provider}: {'actualizado' if estado == 'terminado' else 'falló y se excluye de los datos nuevos'}."))
                        code = proc.wait(timeout=30)
                        timeout_timer.cancel()
                        self._active_process = None
                        ok = code == 0 and not self._cancel_requested
                        resultados.append({"objetivo": item, "estado": "terminado" if ok else "error"})
                        if ok and not conservar:
                            prefs = self.preferencias(); scope = "general" if item == "general" else "servicio:" + item
                            prefs["ordenes"].pop(scope, None); self._write(self.pref_path, prefs)
                        if seguimiento_global:
                            report_path = self.state / "ranking_global_refresh_status.json"
                            try:
                                fresh_report = report_path.stat().st_mtime >= started - 1.0
                            except OSError:
                                fresh_report = False
                            refresh_report = self._read(report_path, {}) if fresh_report else {}
                            for row in refresh_report.get("proveedores", []):
                                if not isinstance(row, dict):
                                    continue
                                provider = str(row.get("proveedor") or "").lower()
                                if provider == "ollama_catalogo":
                                    provider = "ollama_cloud_api"
                                if provider in self.PROVEEDORES:
                                    estados_proveedores[provider] = "terminado" if row.get("ok") is True else "error"
                            service_rows = [{"objetivo": name, "estado": estados_proveedores[name]}
                                            for name in servicios_seguimiento if name in estados_proveedores]
                            completed = len(service_rows)
                            provider_failures = [x["objetivo"] for x in service_rows if x["estado"] == "error"]
                            summary = (f"Actualización parcial: {len(provider_failures)} servicio(s) fallaron y se excluyeron del ranking nuevo."
                                       if provider_failures else "Ranking actualizado correctamente.")
                            update(completados=completed,
                                   exitosos=sum(x["estado"] == "terminado" for x in service_rows),
                                   fallos=len(provider_failures), servicios_terminados=service_rows,
                                   mensaje=summary)
                        else:
                            update(completados=index + 1, exitosos=sum(x["estado"] == "terminado" for x in resultados),
                                   fallos=sum(x["estado"] == "error" for x in resultados),
                                   servicios_terminados=resultados,
                                   mensaje=f"{item}: {'completado correctamente.' if ok else 'terminó con errores.'}")
                if self._cancel_requested:
                    self._write(self.job_path, {**self._read(self.job_path, {}), "estado": "cancelado",
                        "fin": datetime.now().isoformat(timespec="seconds"), "etapa": "Detenido por vos",
                        "mensaje": "La comprobación se detuvo. El ranking anterior se conserva."})
                else:
                    failed = any(x["estado"] == "error" for x in resultados)
                    if seguimiento_global:
                        failed = failed or any(value == "error" for value in estados_proveedores.values())
                    self._write(self.job_path, {**self._read(self.job_path, {}),
                        "estado": "error" if failed else "terminado", "fin": datetime.now().isoformat(timespec="seconds"),
                        "etapa": "Finalizado", "mensaje": (
                            "Actualización parcial: los servicios con error se excluyeron del ranking nuevo; revisá el último avance."
                            if failed and seguimiento_global else
                            "La prueba terminó con errores; se conservó el ranking anterior."
                            if failed else "Ranking actualizado correctamente.")})
            except Exception as exc:
                self._write(self.job_path, {**self._read(self.job_path, {}), "estado": "error",
                    "fin": datetime.now().isoformat(timespec="seconds"), "etapa": "Error",
                    "mensaje": "No se pudo completar la actualización.", "detalle": str(exc)[:240]})
            finally:
                self._active_process = None
        threading.Thread(target=run, daemon=True, name="ranking-panel").start()
        return {"mensaje": "La comprobación comenzó. Podés seguir usando el panel."}

    def cancelar(self):
        status = self._trabajo()
        if status.get("estado") != "ejecutando":
            return {"mensaje": "No hay una comprobación en curso."}
        self._cancel_requested = True
        proc = self._active_process
        if proc and proc.poll() is None:
            try:
                proc.terminate()
            except OSError:
                pass
        return {"mensaje": "Se solicitó detener la comprobación."}
