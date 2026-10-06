import io
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import ranking_tokenharbor as ranker


class TokenHarborRankingTests(unittest.TestCase):
    def test_account_loader_keeps_all_distinct_configured_keys(self):
        rows = [
            {"id": "tokenharbor_1", "api_key": "thk_test_one"},
            {"id": "tokenharbor_2", "api_key": "thk_test_two"},
            {"id": "tokenharbor_3", "api_key": "thk_test_one"},
        ]
        with patch.object(ranker, "get_tokenharbor_accounts", return_value=rows):
            self.assertEqual(ranker._cuentas_tokenharbor(), [
                ("tokenharbor_1", "thk_test_one"),
                ("tokenharbor_2", "thk_test_two"),
            ])

    def test_paid_route_is_not_probed_and_successful_account_is_preserved(self):
        free = {
            "id": "vendor/model:free", "pricing": {"input": 0, "output": 0},
            "capabilities": {"tools": True, "reasoning": True},
        }
        paid_free_id = {
            "id": "vendor/paid:free", "pricing": {"input": 0.1, "output": 0.2},
        }
        paid_base = {
            "id": "vendor/paid", "pricing": {"input": 1, "output": 2},
        }
        catalogs = [
            [free, paid_free_id, paid_base],
            [free, paid_free_id, paid_base],
        ]
        text_results = [
            {"ok": False, "estado": "no_acceso", "detalle": "", "status": 403, "intentos": 1},
            {"ok": True, "estado": "ok", "detalle": "HARBOR", "status": 200, "intentos": 1},
        ]
        success = {"ok": True, "estado": "ok", "detalle": "", "status": 200, "intentos": 1}
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "ranking.json"
            with (
                patch.object(ranker, "_cuentas_tokenharbor", return_value=[
                    ("account_1", "thk_test_one"), ("account_2", "thk_test_two"),
                ]),
                patch.object(ranker, "obtener_catalogo", side_effect=[(catalogs[0], "test_catalog"), (catalogs[1], "test_catalog")]),
                patch.object(ranker, "_probe_texto", side_effect=text_results) as text_probe,
                patch.object(ranker, "_probe_herramientas", return_value=success),
                patch.object(ranker, "_probe_razonamiento", return_value=success),
                patch.object(ranker, "STATE_DIR", Path(tmp)),
                patch.object(ranker, "SALIDA", output),
                redirect_stdout(io.StringIO()),
            ):
                result = ranker.generar_ranking()

        self.assertEqual(text_probe.call_count, 2)
        self.assertEqual(text_probe.call_args_list[0].args, ("vendor/model:free", "thk_test_one"))
        self.assertEqual(text_probe.call_args_list[1].args, ("vendor/model:free", "thk_test_two"))
        self.assertEqual(result["total_modelos"], 1)
        self.assertEqual(result["ranking"][0]["cuenta_id"], "account_2")
        self.assertEqual(result["ranking_final"][0]["cuentas_probe_ok"], ["account_2"])
        self.assertEqual(result["ranking"][0]["id"], "vendor/model:free")

    def test_secondary_capabilities_are_catalogued_without_claiming_adapter(self):
        catalog = [{
            "id": "vision-model", "capabilities": {"vision": True},
            "pricing": {"input": 0, "output": 0},
        }]
        row = ranker._catalogo_capacidades(catalog)["vision_image"][0]
        self.assertFalse(row["probe_ok"])
        self.assertFalse(row["implementado"])


if __name__ == "__main__":
    unittest.main()
