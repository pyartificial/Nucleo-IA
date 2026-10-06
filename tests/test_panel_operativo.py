import json
import tempfile
import unittest
from pathlib import Path

from scripts.gestor_panel_operativo import GestorPanelOperativo
from scripts.gestor_rankings_panel import GestorRankings
from scripts.servicios_backend import GestorServicios


class PanelOperativoTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / "state").mkdir()
        (self.root / "cuentas.json").write_text(json.dumps({"proveedores": {"groq": {"cuentas": [
            {"id": "g1", "email": "persona@example.com", "api_key": "secreto"}]}}}), encoding="utf-8")
        ranking = [{"proveedor": "groq", "id": f"modelo-{n}", "nombre": f"Modelo {n}",
                    "apto_agente": True, "probe_ok": True,
                    "capacidades": {"herramientas": True, "reasoning": True}} for n in range(1, 5)]
        (self.root / "state" / "ranking_global.json").write_text(json.dumps({"ranking": ranking}), encoding="utf-8")
        route_health = {"candidatos": {f"groq:modelo-{n}": {"last_ok": 1} for n in range(1, 5)}}
        (self.root / "state" / "route_health.json").write_text(json.dumps(route_health), encoding="utf-8")
        self.panel = GestorPanelOperativo(self.root, GestorServicios(self.root), GestorRankings(self.root))
        self.panel._proxy_json = lambda *args, **kwargs: (0, {})

    def tearDown(self):
        self.tmp.cleanup()

    def test_muestra_solo_top_tres_y_no_expone_claves(self):
        data = self.panel.estado()
        self.assertEqual(len(data["top"]["general"]), 3)
        self.assertEqual(len(data["top"]["herramientas"]), 3)
        self.assertNotIn("secreto", json.dumps(data))

    def test_pausa_es_persistente_y_reversible(self):
        self.panel.pausar(True)
        self.assertTrue(self.panel._pausado())
        self.panel.pausar(False)
        self.assertFalse(self.panel._pausado())

    def test_accesos_directos_mantienen_el_servidor_en_primer_plano(self):
        project = Path(__file__).resolve().parents[1]
        self.assertIn("--serve", (project / "mis_servicios.sh").read_text(encoding="utf-8"))
        self.assertIn("--serve", (project / "centro_control.sh").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
