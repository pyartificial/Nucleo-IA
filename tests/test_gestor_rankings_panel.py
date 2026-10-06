import json
import tempfile
import unittest
from pathlib import Path

from scripts.gestor_rankings_panel import (
    GestorRankings, ErrorRanking, _evento_proveedor_global,
    _objetivos_actualizacion, _script_actualizacion,
)


class GestorRankingsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / "state").mkdir()
        (self.root / "cuentas.json").write_text(json.dumps({"proveedores": {"groq": {"cuentas": [
            {"id": "g1", "email": "uno@example.com", "api_key": "NO-DEBE-SALIR"},
            {"id": "g2", "nombre": "Cuenta con crédito"}]}}}), encoding="utf-8")
        rows = [{"proveedor": "groq", "id": "modelo-a", "nombre": "Modelo A", "apto_agente": True, "probe_ok": True},
                {"proveedor": "groq", "id": "modelo-b", "nombre": "Modelo B", "apto_agente": True, "probe_ok": True}]
        (self.root / "state" / "ranking_global.json").write_text(json.dumps({"ranking": rows}), encoding="utf-8")
        (self.root / "state" / "ranking_groq.json").write_text(json.dumps({"ranking": rows}), encoding="utf-8")
        self.gestor = GestorRankings(self.root)

    def tearDown(self):
        self.tmp.cleanup()

    def test_resumen_no_expone_claves_y_muestra_cuentas(self):
        data = self.gestor.resumen()
        raw = json.dumps(data)
        self.assertNotIn("NO-DEBE-SALIR", raw)
        self.assertEqual(len(data["general"][0]["cuentas"]), 2)

    def test_guarda_orden_cuenta_y_rotacion_separados_del_ranking(self):
        original = (self.root / "state" / "ranking_global.json").read_text()
        result = self.gestor.guardar({"alcance": "general", "orden": ["groq::modelo-b", "groq::modelo-a"],
            "cuentas_preferidas": {"groq::modelo-b": "g2"},
            "rotacion": {"modo": "rotar_top", "top_n": 2, "conservar_al_actualizar": True}})
        self.assertEqual(result["preferencias"]["cuentas_preferidas"]["groq::modelo-b"], "g2")
        self.assertEqual((self.root / "state" / "ranking_global.json").read_text(), original)
        self.assertEqual(self.gestor.resumen()["general"][0]["modelo"], "modelo-b")

    def test_rechaza_modelo_desconocido(self):
        with self.assertRaises(ErrorRanking):
            self.gestor.guardar({"alcance": "general", "orden": ["groq::inventado"]})

    def test_actualizador_resuelve_ranker_compartido_para_pasarelas_y_mistral(self):
        for provider in ("agnes", "huggingface", "ollama_cloud_api", "mistral"):
            script, args = _script_actualizacion(self.root, provider)
            self.assertEqual(script.name, "ranking_pasarelas_free.py")
            self.assertEqual(args, [provider])
        for provider in ("deepseek", "cerebras"):
            script, args = _script_actualizacion(self.root, provider)
            self.assertEqual(script.name, "ranking_openai_compatible.py")
            self.assertEqual(args, [provider])

    def test_actualizar_todos_consolida_sin_repetir_pruebas_de_proveedores(self):
        targets = _objetivos_actualizacion("todos", GestorRankings.PROVEEDORES)
        self.assertEqual(targets, ["general"])
        script, args = _script_actualizacion(self.root, targets[0])
        self.assertEqual(script.name, "ranking_global.py")
        self.assertEqual(args, [])
        self.assertEqual(_objetivos_actualizacion("general", GestorRankings.PROVEEDORES), ["general"])
        self.assertEqual(_objetivos_actualizacion("agnes", GestorRankings.PROVEEDORES), ["agnes"])
        script, args = _script_actualizacion(self.root, "general")
        self.assertEqual(script.name, "ranking_global.py")
        self.assertEqual(args, [])

    def test_progreso_global_reconoce_proveedor_inicio_final_y_fallo(self):
        self.assertEqual(_evento_proveedor_global("[....] agnes"), ("inicio", "agnes", None))
        self.assertEqual(_evento_proveedor_global("[OK] agnes"), ("fin", "agnes", "terminado"))
        self.assertEqual(_evento_proveedor_global("[FALLO] ollama_catalogo: timeout"),
                         ("fin", "ollama_cloud_api", "error"))
        self.assertIsNone(_evento_proveedor_global("Ranking global consolidado"))

    def test_cero_significa_todos_los_puestos(self):
        result = self.gestor.guardar({"alcance": "general", "orden": ["groq::modelo-a", "groq::modelo-b"],
            "rotacion": {"modo": "rotar_top", "top_n": 0, "conservar_al_actualizar": True}})
        self.assertEqual(result["preferencias"]["rotacion"]["top_n"], 0)

    def test_capacidades_multimedia_tienen_rankings_independientes(self):
        data = self.gestor.resumen()
        esperadas = {
            "vision_image", "vision_video", "transcription_audio", "speech_generation",
            "voice_cloning", "sound_effects", "image_generation", "image_editing",
            "video_generation_text", "video_generation_image", "video_editing",
            "lip_sync", "music_generation",
        }
        self.assertTrue(esperadas.issubset(data["capacidades"]))
        self.assertNotIn("video", data["capacidades"])
        self.assertNotIn("tts", data["capacidades"])

    def test_migra_orden_antiguo_de_video_sin_perderlo(self):
        fuentes = {"proveedores": {"zhipu": {"video": True, "modelos_confirmados": {
            "video": ["CogVideoX-Flash", "cogvideox-2"]}}}}
        (self.root / "state" / "capacidades_fuentes.json").write_text(json.dumps(fuentes), encoding="utf-8")
        prefs = {"ordenes": {"capacidad:video": ["zhipu::cogvideox-2", "zhipu::CogVideoX-Flash"]}}
        (self.root / "state" / "preferencias_ranking.json").write_text(json.dumps(prefs), encoding="utf-8")
        rows = self.gestor.resumen()["capacidades"]["video_generation_text"]
        self.assertEqual([x["modelo"] for x in rows], ["cogvideox-2", "CogVideoX-Flash"])

    def test_proveedor_opcional_exige_proveedor_y_cuenta_habilitados(self):
        cuentas = {"proveedores": {"minimax": {"habilitado": False, "cuentas": [
            {"id": "mm1", "nombre": "Cuenta MiniMax", "habilitado": True}]}}}
        (self.root / "cuentas.json").write_text(json.dumps(cuentas), encoding="utf-8")
        self.assertNotIn("minimax", self.gestor._cuentas())
        cuentas["proveedores"]["minimax"]["habilitado"] = True
        cuentas["proveedores"]["minimax"]["cuentas"][0]["habilitado"] = False
        (self.root / "cuentas.json").write_text(json.dumps(cuentas), encoding="utf-8")
        self.assertEqual(self.gestor._cuentas().get("minimax"), [])
        cuentas["proveedores"]["minimax"]["cuentas"][0]["habilitado"] = True
        (self.root / "cuentas.json").write_text(json.dumps(cuentas), encoding="utf-8")
        self.assertEqual(self.gestor._cuentas()["minimax"][0]["id"], "mm1")

    def test_elevenlabs_solo_entra_en_tts_si_la_cuenta_lo_autoriza(self):
        cuentas = {"proveedores": {"elevenlabs": {"cuentas": [{
            "id": "el1", "nombre": "Eleven", "habilitado": True,
            "capacidades_habilitadas": ["sound_effects"]}]}}}
        (self.root / "cuentas.json").write_text(json.dumps(cuentas), encoding="utf-8")
        speech = self.gestor.resumen()["capacidades"]["speech_generation"]
        self.assertFalse(any(x["proveedor"] == "elevenlabs" for x in speech))
        cuentas["proveedores"]["elevenlabs"]["cuentas"][0]["capacidades_habilitadas"] = ["speech_generation"]
        (self.root / "cuentas.json").write_text(json.dumps(cuentas), encoding="utf-8")
        speech = self.gestor.resumen()["capacidades"]["speech_generation"]
        self.assertEqual(sum(x["proveedor"] == "elevenlabs" for x in speech), 5)

    def test_speechify_aparece_como_capacidad_tts_si_su_cuenta_fue_verificada(self):
        cuentas = {"proveedores": {"speechify": {"habilitado": True, "cuentas": [{
            "id": "sp1", "nombre": "Speechify", "habilitado": True,
            "conexion_estado": "guardada",
        }]}}}
        (self.root / "cuentas.json").write_text(json.dumps(cuentas), encoding="utf-8")
        speech = self.gestor.resumen()["capacidades"]["speech_generation"]
        self.assertFalse(any(x["proveedor"] == "speechify" for x in speech))
        cuentas["proveedores"]["speechify"]["cuentas"][0]["conexion_estado"] = "acceso_comprobado"
        (self.root / "cuentas.json").write_text(json.dumps(cuentas), encoding="utf-8")
        speech = self.gestor.resumen()["capacidades"]["speech_generation"]
        entry = next(x for x in speech if x["proveedor"] == "speechify")
        self.assertEqual(entry["modelo"], "simba-3.2")
        self.assertEqual([x["id"] for x in entry["cuentas"]], ["sp1"])


if __name__ == "__main__":
    unittest.main()
