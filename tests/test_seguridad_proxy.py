"""Regresiones locales del proxy; no usan proveedores ni secretos reales."""
import os
import unittest
from unittest.mock import patch

from proxy import limitador_tasa, normalizador_stream, rotador_cuentas, seguridad
from proxy.esquemas import EntradaInvalida, validar_chat


class SeguridadTests(unittest.TestCase):
    def test_origen_local_y_cliente_sin_origin(self):
        with patch.dict(os.environ, {"PROXY_PORT": "8080", "CORS_ALLOW_ORIGINS": ""}):
            self.assertTrue(seguridad.origin_allowed(""))
            self.assertTrue(seguridad.origin_allowed("http://127.0.0.1:8080"))
            self.assertFalse(seguridad.origin_allowed("https://sitio-ajeno.invalid"))

    def test_host_local_rechaza_nombres_ajenos(self):
        with patch.dict(os.environ, {"PROXY_HOST": "127.0.0.1"}, clear=True):
            self.assertTrue(seguridad.host_allowed("localhost:8080"))
            self.assertTrue(seguridad.host_allowed("127.0.0.1:8080"))
            self.assertFalse(seguridad.host_allowed("sitio-ajeno.invalid"))

    def test_red_requiere_autenticacion(self):
        with patch.dict(os.environ, {"PROXY_HOST": "0.0.0.0", "AUTH_ENABLED": "false", "NUCLEO_API_KEY": ""}, clear=False):
            with self.assertRaises(RuntimeError):
                seguridad.validate_deployment()
        with patch.dict(os.environ, {"PROXY_HOST": "0.0.0.0", "AUTH_ENABLED": "true", "NUCLEO_API_KEY": "ficticia"}, clear=False):
            seguridad.validate_deployment()

    def test_profesional_acepta_nombre_nuevo_y_legado(self):
        for nombre in ("profesional", "empresa", "organizacion"):
            with patch.dict(os.environ, {"PERFIL_USO": nombre}, clear=True):
                self.assertTrue(seguridad.professional_profile())

    def test_profesional_exige_clave_administrativa_incluso_en_local(self):
        entorno = {"PERFIL_USO": "profesional", "PROXY_HOST": "127.0.0.1",
                   "AUTH_ENABLED": "true", "NUCLEO_API_KEY": "uso", "NUCLEO_ADMIN_KEY": ""}
        with patch.dict(os.environ, entorno, clear=True):
            with self.assertRaises(RuntimeError):
                seguridad.validate_deployment()

    def test_chat_invalido_no_llega_al_despacho(self):
        for body in ([], {}, {"model": {}, "messages": []}):
            with self.assertRaises(EntradaInvalida):
                validar_chat(body)
        self.assertEqual(validar_chat({"model": "auto", "messages": [{"role": "user", "content": "hola"}]})["model"], "auto")

    def test_stream_tiene_un_solo_final(self):
        self.assertIsNone(normalizador_stream.normalizar_linea_sse("data: [DONE]"))
        self.assertEqual(normalizador_stream.inyectar_finish("ficticio").count("[DONE]"), 1)


class LimitesYEstadosTests(unittest.TestCase):
    def setUp(self):
        limitador_tasa._reservas_global.clear()
        limitador_tasa._reservas_cuenta.clear()

    def test_reserva_atomica_impide_segundo_intento(self):
        with patch.object(limitador_tasa, "MAX_GLOBAL_MINUTO", 1), \
             patch.object(limitador_tasa, "obtener_uso_global_minuto", return_value=0), \
             patch.object(limitador_tasa, "obtener_uso_cuenta", return_value={"hora": 0, "semana": 0}):
            self.assertTrue(limitador_tasa.reservar("cuenta"))
            self.assertFalse(limitador_tasa.reservar("cuenta"))

    def test_402_vencido_se_recupera(self):
        from datetime import datetime, timedelta
        with rotador_cuentas._lock:
            rotador_cuentas._estados["ficticia"] = {
                "estado": "sin_credito",
                "cooldown_hasta": (datetime.now() - timedelta(seconds=1)).isoformat(),
            }
            self.assertTrue(rotador_cuentas._disponible({"id": "ficticia"}))


if __name__ == "__main__":
    unittest.main()
