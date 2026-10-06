import unittest
import tempfile
from pathlib import Path

from scripts import ranking_apinex


class APInexFreeEvidenceTests(unittest.TestCase):
    def test_free_prefix_without_zero_price_is_not_enough(self):
        self.assertIsNone(ranking_apinex._free_evidence({"id": "free/model"}))

    def test_requires_zero_input_and_output_prices(self):
        self.assertIsNone(ranking_apinex._free_evidence({"id": "free/model", "pricing": {"input": 0}}))
        self.assertIsNone(ranking_apinex._free_evidence({"id": "free/model", "pricing": {"input": 0, "output": 0.2}}))
        self.assertEqual(
            "catalogo:precio_entrada_y_salida_cero",
            ranking_apinex._free_evidence({"id": "paid-model", "pricing": {"input": 0, "output": 0}}),
        )

    def test_explicit_free_flag_is_accepted(self):
        self.assertEqual("catalogo:is_free", ranking_apinex._free_evidence({"is_free": True}))
        self.assertEqual("catalogo:is_free", ranking_apinex._free_evidence({"free": True}))

    def test_tool_probe_requires_exact_function_arguments(self):
        original = ranking_apinex.call
        try:
            ranking_apinex.call = lambda *args, **kwargs: (200, {"choices": [{"message": {"tool_calls": [{"function": {"name": "sumar", "arguments": "{\"a\":17,\"b\":25}"}}]}}]})
            self.assertTrue(ranking_apinex._probe_tools("free/model", "not-a-real-key"))
            ranking_apinex.call = lambda *args, **kwargs: (200, {"choices": [{"message": {"tool_calls": [{"function": {"name": "sumar", "arguments": "{\"a\":17,\"b\":24}"}}]}}]})
            self.assertFalse(ranking_apinex._probe_tools("free/model", "not-a-real-key"))
        finally:
            ranking_apinex.call = original

    def test_catalog_without_free_evidence_never_sends_generation_requests(self):
        original = (ranking_apinex._keys, ranking_apinex.call, ranking_apinex.STATE, ranking_apinex.OUT)
        calls = []
        try:
            ranking_apinex._keys = lambda: ["local-test-key"]
            def fake_call(url, key, payload=None):
                calls.append((url, payload))
                return 200, {"data": [{"id": "free/model", "pricing": {"input": 0}}]} if payload is None else (500, {})
            ranking_apinex.call = fake_call
            with tempfile.TemporaryDirectory() as directory:
                ranking_apinex.STATE = Path(directory)
                ranking_apinex.OUT = Path(directory) / "ranking.json"
                result = ranking_apinex.main()
                self.assertFalse(result["ranking"][0]["probe_ok"])
                self.assertEqual("sin_evidencia_precio_cero", result["ranking"][0]["probe_estado"])
            self.assertEqual(1, len(calls))
            self.assertIsNone(calls[0][1])
        finally:
            ranking_apinex._keys, ranking_apinex.call, ranking_apinex.STATE, ranking_apinex.OUT = original


if __name__ == "__main__":
    unittest.main()
