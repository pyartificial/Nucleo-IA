import unittest
import tempfile
from unittest.mock import patch
from pathlib import Path

from scripts import ranking_pasarelas_free as free_ranking
from scripts import ranking_cloudflare


class FreeEvidenceTests(unittest.TestCase):
    def test_account_credits_alone_do_not_make_models_free(self):
        free, evidence = free_ranking._free(
            {"id": "vendor/model", "account_free_credits": 10}, "requesty", "pricing"
        )
        self.assertFalse(free)
        self.assertIn("sin evidencia", evidence)

    def test_both_input_and_output_prices_must_be_zero(self):
        self.assertTrue(free_ranking._free(
            {"id": "vendor/free-model", "pricing": {"input": "0", "output": "0"}},
            "anyapi", "pricing",
        )[0])
        self.assertFalse(free_ranking._free(
            {"id": "vendor/model", "pricing": {"input": "0", "output": "0.1"}},
            "anyapi", "pricing",
        )[0])

    def test_explicit_free_flags_and_ids_are_recognized(self):
        self.assertTrue(free_ranking._free({"id": "m", "is_free": True}, "huggingface", "pricing")[0])
        self.assertTrue(free_ranking._free({"id": "vendor/model:free"}, "routeway", "pricing")[0])
        self.assertTrue(free_ranking._free({"id": "orcarouter/free"}, "orcarouter", "orcarouter")[0])

    def test_openai_compatible_catalog_without_capability_flags_is_chat_candidate(self):
        self.assertTrue(free_ranking._es_chat({"id": "vendor/chat-model"}, "vendor/chat-model", {}))
        self.assertFalse(free_ranking._es_chat({"id": "vendor/embed-large"}, "vendor/embed-large", {}))
        self.assertFalse(free_ranking._es_chat({"id": "vendor/model", "supports_chat": False}, "vendor/model", {}))

    def test_secondary_catalog_recognizes_the_full_internal_capability_taxonomy(self):
        cases = [
            ({"input_modalities": ["image"]}, "vision_image"),
            ({"task": "image_to_text"}, "vision_image"),
            ({"input_modalities": ["video"]}, "vision_video"),
            ({"task": "video_captioning"}, "vision_video"),
            ({"input_modalities": ["audio"], "task": "automatic_speech_recognition"}, "transcription_audio"),
            ({"api_formats": ["transcription-realtime"]}, "transcription_realtime"),
            ({"output_modalities": ["speech"]}, "speech_generation"),
            ({"task": "speech_to_speech"}, "speech_to_speech"),
            ({"task": "voice_cloning"}, "voice_cloning"),
            ({"task": "voice_design"}, "voice_design"),
            ({"task": "audio_isolation"}, "audio_isolation"),
            ({"task": "sound_effect_generation"}, "sound_effects"),
            ({"task": "video_dubbing"}, "dubbing"),
            ({"task": "forced_alignment"}, "forced_alignment"),
            ({"task": "text_to_image"}, "image_generation"),
            ({"output_task": "image_editing"}, "image_editing"),
            ({"output_task": "text_to_video"}, "video_generation_text"),
            ({"input_modalities": ["image"], "output_task": "image_to_video"}, "video_generation_image"),
            ({"task": "video_editing"}, "video_editing"),
            ({"task": "lip_sync"}, "lip_sync"),
            ({"task": "text_embedding"}, "embeddings"),
            ({"task": "document_parsing"}, "parse_documents"),
            ({"task": "reranking"}, "reranking"),
            ({"task": "music_generation"}, "music_generation"),
            ({"task": "music_inpainting"}, "music_editing"),
            ({"task": "voice_agent"}, "voice_agents"),
        ]
        for model, expected in cases:
            with self.subTest(capability=expected):
                self.assertIn(expected, free_ranking._capabilities(model)[1])

    def test_audio_output_alone_is_not_mislabelled_as_speech(self):
        _, discovered, _ = free_ranking._capabilities({
            "output_modalities": ["audio"], "task": "music_generation",
        })
        self.assertIn("music_generation", discovered)
        self.assertNotIn("speech_generation", discovered)

    def test_huggingface_routes_keep_route_specific_pricing(self):
        rows = free_ranking._provider_rows({
            "id": "org/model",
            "providers": [
                {"provider": "provider-free", "status": "live", "pricing": {"input": 0, "output": 0}},
                {"provider": "provider-paid", "status": "live", "pricing": {"input": 1, "output": 2}},
                {"provider": "provider-down", "status": "paused", "pricing": {"input": 0, "output": 0}},
            ],
        }, "huggingface")
        self.assertEqual([model for _, model in rows], ["org/model:provider-free", "org/model:provider-paid"])
        self.assertTrue(free_ranking._free(rows[0][0], "huggingface", "pricing")[0])
        self.assertFalse(free_ranking._free(rows[1][0], "huggingface", "pricing")[0])

    def test_cloudflare_reachability_is_not_free_price_evidence(self):
        model = {"name": "@cf/vendor/model", "task": {"name": "Text Generation"}, "properties": []}
        with patch.object(ranking_cloudflare, "probar_respuesta_real", return_value={"ok": True, "estado": "ok", "preview": "OK"}):
            row = ranking_cloudflare.analizar_modelo_api(model, {"account_id": "test", "api_token": "secret", "cuenta_id": "test-account"})
        self.assertTrue(row["probe_ok"])
        self.assertFalse(row["gratis"])
        self.assertIn("sin_precio_cero", row["gratis_evidencia"])

    def test_full_probe_promotes_only_verified_account_to_agent_ranking(self):
        model = {
            "id": "vendor/model-free", "is_free": True, "supports_chat": True,
            "supports_tools": True, "supports_reasoning": True,
            "input_modalities": ["text", "image"], "context_length": 65536,
        }
        with tempfile.TemporaryDirectory() as tmp:
            with (
                patch.object(free_ranking, "ROOT", Path(tmp)),
                patch.object(free_ranking, "_keys", return_value=[("account-1", "test-only-secret")]),
                patch.object(free_ranking, "_get_json", return_value=(200, {"data": [model]})),
                patch.object(free_ranking, "_probe", return_value=True),
                patch.object(free_ranking, "_probe_tools", return_value=(True, "ok_tool_call_exacta")),
                patch.object(free_ranking, "_probe_reasoning", return_value=True),
            ):
                result = free_ranking.generar("agnes")
            self.assertEqual(result["total_aptos_finales"], 1)
            self.assertEqual(result["ranking_final"][0]["cuentas_compatibles"], ["account-1"])
            self.assertTrue(result["ranking_final"][0]["apto_agente"])
            self.assertTrue(result["rankings_capacidades"]["vision_image"][0]["implementado"])


if __name__ == "__main__":
    unittest.main()
