import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import ranking_xkiro as ranker


class XkiroRankingTests(unittest.TestCase):
    def test_secondary_vision_capability_is_cataloged_without_fabricating_adapter(self):
        catalog = [{
            "id": "vision-free", "access_tier": "free",
            "pricing": {"input": 0, "output": 0},
            "capabilities": {"vision": True},
        }]
        capabilities = ranker._catalogo_capacidades(catalog)
        row = capabilities["vision_image"][0]
        self.assertTrue(row["gratis"])
        self.assertFalse(row["probe_ok"])
        self.assertFalse(row["implementado"])

    def test_account_loader_returns_all_distinct_configured_accounts(self):
        rows = [
            {"id": "xkiro_1", "api_key": "test-key-1"},
            {"id": "xkiro_2", "api_key": "test-key-2"},
            {"id": "xkiro_3", "api_key": "test-key-1"},
        ]
        with patch.object(ranker, "get_xkiro_accounts", return_value=rows):
            self.assertEqual(ranker._cuentas_xkiro(), [
                ("xkiro_1", "test-key-1"), ("xkiro_2", "test-key-2"),
            ])

    def test_agent_requires_exact_tool_and_reasoning_probes(self):
        tool_response = {"choices": [{"message": {"tool_calls": [{
            "function": {"name": "sumar_numeros", "arguments": '{"a":17,"b":25}'},
        }]}}]}
        reasoning_response = {"choices": [{"message": {"content": "INES"}}]}
        with patch.object(ranker, "_request_json", side_effect=[
            (200, {"choices": [{"message": {"content": "OK"}}]}, {}),
            (200, tool_response, {}),
            (200, reasoning_response, {}),
        ]) as request:
            result = ranker.probar_modelo({
                "id": "agent-model", "capabilities": {"tools": True, "reasoning": True},
            }, "test-key")
        self.assertTrue(result["probe_ok"])
        self.assertTrue(result["tool_probe_ok"])
        self.assertTrue(result["reasoning_probe_ok"])
        self.assertEqual(request.call_count, 3)

    def test_uses_account_that_passes_and_keeps_it_compatible(self):
        accounts = [("xkiro_1", "test-key-1"), ("xkiro_2", "test-key-2")]
        quota = {"ok": True, "free_tokens": {"remaining": 20}}
        model = {
            "id": "free-agent", "access_tier": "free",
            "pricing": {"input": 0, "output": 0},
            "capabilities": {"tools": True, "reasoning": True},
        }
        results = [
            {"probe_ok": False, "probe_estado": "cuenta_no_elegible", "tool_probe_ok": False, "reasoning_probe_ok": False},
            {"probe_ok": True, "probe_estado": "ok", "tool_probe_ok": True, "reasoning_probe_ok": True},
        ]
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "ranking.json"
            with (
                patch.object(ranker, "_cuentas_xkiro", return_value=accounts),
                patch.object(ranker, "obtener_catalogo", return_value=([model], "test_catalog")),
                patch.object(ranker, "obtener_cuota", return_value=quota),
                patch.object(ranker, "probar_modelo", side_effect=results) as probe,
                patch.object(ranker, "STATE_DIR", Path(tmp)),
                patch.object(ranker, "SALIDA", out),
                redirect_stdout(io.StringIO()),
            ):
                result = ranker.generar_ranking()
        self.assertEqual(probe.call_count, 2)
        self.assertEqual(result["ranking"][0]["cuenta_id"], "xkiro_2")
        self.assertEqual(result["ranking"][0]["cuentas_compatibles"], ["xkiro_2"])
        self.assertEqual(result["ranking_final"][0]["cuentas_probe_ok"], ["xkiro_2"])


if __name__ == "__main__":
    unittest.main()
