import tempfile
import unittest
import json
import io
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import ranking_tokenrouter as ranker
import ranking_global


class TokenRouterFreeCatalogTests(unittest.TestCase):
    def test_secondary_capabilities_are_normalized_from_api_formats(self):
        _, capabilities, modalities = ranker._metadatos_capacidades({
            "id": "media-model",
            "api_formats": [
                "image-generation", "video-generation", "embeddings",
                "text-to-speech", "transcription", "reranking",
                "lip-sync", "voice-cloning", "sound-effects", "music-generation",
                "transcription-realtime", "speech-to-speech", "voice-design",
                "audio-isolation", "dubbing", "forced-alignment", "video-editing",
                "music-editing", "voice-agents", "document-parsing",
            ],
        })
        self.assertEqual(set(capabilities), {
            "image_generation", "video_generation_text", "embeddings",
            "speech_generation", "transcription_audio", "reranking",
            "lip_sync", "voice_cloning", "sound_effects", "music_generation",
            "transcription_realtime", "speech_to_speech", "voice_design",
            "audio_isolation", "dubbing", "forced_alignment", "video_editing",
            "music_editing", "voice_agents", "parse_documents",
        })
        self.assertTrue({"image", "video", "audio"}.issubset(set(modalities)))

    def test_non_chat_api_formats_are_not_chat_probe_candidates(self):
        self.assertFalse(ranker._candidato_chat(
            {"id": "image-gen", "api_formats": ["image-generation"]}, "image-gen"
        ))
        self.assertTrue(ranker._candidato_chat(
            {"id": "chat-model", "api_formats": ["openai"]}, "chat-model"
        ))

    def test_secondary_catalog_flows_into_global_ranking(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = Path(tmp) / "state"
            state.mkdir()
            capabilities = {"image_generation": [{"id": "image-model", "gratis": False}]}
            cloudflare_capabilities = {"transcription_audio": [{"id": "whisper", "probe_ok": False}]}
            mistral_capabilities = {"vision_image": [{"id": "pixtral", "probe_ok": False}]}
            (state / "ranking_tokenrouter.json").write_text(json.dumps({
                "ranking": [], "rankings_capacidades": capabilities,
            }))
            (state / "ranking_cloudflare.json").write_text(json.dumps({
                "ranking": [], "rankings_capacidades": cloudflare_capabilities,
            }))
            (state / "ranking_mistral.json").write_text(json.dumps({
                "ranking": [], "rankings_capacidades": mistral_capabilities,
            }))
            output = state / "ranking_global.json"
            secondary = state / "ranking_secundario.json"
            with (
                patch.object(ranking_global, "STATE_DIR", str(state)),
                patch.object(ranking_global, "RANKING_GLOBAL", str(output)),
                patch.object(ranking_global, "RANKING_SECUNDARIO", str(secondary)),
                patch.object(ranking_global, "REFRESH_STATUS", str(state / "refresh.json")),
                patch.object(ranking_global, "ROUTE_RANKINGS_DIR", str(state / "route_rankings")),
                patch.object(ranking_global, "RANKING_COHERE_CAPACIDADES", str(state / "cohere_caps.json")),
                patch.object(ranking_global, "cargar_evidencia", return_value=({}, {"actualizada": False, "cache": False, "detalle": "offline test"})),
                patch.object(ranking_global, "cargar_evidencia_lmarena", return_value=([], {"actualizada": False, "cache": False, "detalle": "offline test"})),
                patch.object(ranking_global, "cargar_entradas", return_value=[{
                    "id": "offline-placeholder", "modelo_base": "offline-placeholder",
                    "probe_ok": False, "apto_agente": False, "puntaje": 0,
                    "contexto": 0, "capacidades_norm": {"herramientas": False, "reasoning": False},
                }]),
                patch.object(ranking_global, "aplicar_calidad"),
                redirect_stdout(io.StringIO()),
            ):
                result = ranking_global.generar_ranking_global(refrescar=False)
        self.assertEqual(result["rankings_capacidades"]["tokenrouter"], capabilities)
        self.assertEqual(result["rankings_capacidades"]["cloudflare"], cloudflare_capabilities)
        self.assertEqual(result["rankings_capacidades"]["mistral"], mistral_capabilities)

    def test_failed_sources_do_not_republish_stale_secondary_catalogs(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = Path(tmp) / "state"
            state.mkdir()
            for provider in ("tokenrouter", "cloudflare", "mistral"):
                (state / f"ranking_{provider}.json").write_text(json.dumps({
                    "rankings_capacidades": {"vision_image": [{"id": "stale-model"}]},
                }))
            cohere_file = state / "cohere_caps.json"
            cohere_file.write_text(json.dumps({"rankings": {"embeddings": [{"id": "stale-embed"}]}}))
            output = state / "ranking_global.json"
            secondary = state / "ranking_secundario.json"
            placeholder = [{
                "id": "offline-placeholder", "modelo_base": "offline-placeholder",
                "probe_ok": False, "apto_agente": False, "puntaje": 0,
                "contexto": 0, "capacidades_norm": {"herramientas": False, "reasoning": False},
            }]
            with (
                patch.object(ranking_global, "STATE_DIR", str(state)),
                patch.object(ranking_global, "RANKING_GLOBAL", str(output)),
                patch.object(ranking_global, "RANKING_SECUNDARIO", str(secondary)),
                patch.object(ranking_global, "REFRESH_STATUS", str(state / "refresh.json")),
                patch.object(ranking_global, "ROUTE_RANKINGS_DIR", str(state / "route_rankings")),
                patch.object(ranking_global, "RANKING_COHERE_CAPACIDADES", str(cohere_file)),
                patch.object(ranking_global, "refrescar_fuentes", return_value=(set(), [])),
                patch.object(ranking_global, "cargar_evidencia", return_value=({}, {"actualizada": False, "cache": False, "detalle": "offline test"})),
                patch.object(ranking_global, "cargar_evidencia_lmarena", return_value=([], {"actualizada": False, "cache": False, "detalle": "offline test"})),
                patch.object(ranking_global, "cargar_entradas", return_value=placeholder),
                patch.object(ranking_global, "aplicar_calidad"),
                redirect_stdout(io.StringIO()),
            ):
                result = ranking_global.generar_ranking_global(refrescar=True)
        self.assertEqual(result["rankings_capacidades"], {})

    def test_only_explicit_free_catalog_models_are_candidates(self):
        catalog = {
            "org/free-model:free": {"id": "org/free-model:free"},
            "org/free-by-price": {
                "id": "org/free-by-price",
                "pricing": {"input": "0", "output": "0"},
            },
            "org/paid-model": {
                "id": "org/paid-model",
                "pricing": {"input": "0.1", "output": "0.2"},
            },
            "org/unknown-price": {"id": "org/unknown-price"},
        }
        candidates = ranker._modelos_gratuitos(catalog)
        self.assertEqual(set(candidates), {"org/free-model:free", "org/free-by-price"})

    def test_paid_routes_never_receive_chat_probes(self):
        catalog = {
            "org/free-agent-reasoning:free": {
                "id": "org/free-agent-reasoning:free",
                "pricing": {"input": 0, "output": 0},
            },
            "org/paid-agent": {
                "id": "org/paid-agent",
                "pricing": {"input": 0.1, "output": 0.2},
            },
        }
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "ranking.json"
            probe = patch.object(ranker, "prober_modelo", return_value=(True, "ok"))
            with (
                patch.object(ranker, "get_tokenrouter_api_key", return_value="local-test-key"),
                patch.object(ranker, "get_tokenrouter_accounts", return_value=[{"id": "local-test-account", "api_key": "local-test-key"}]),
                patch.object(ranker, "obtener_modelos_remotos", return_value=catalog),
                patch.object(ranker, "probar_herramienta_openai", return_value=(True, "ok")) as tools_probe,
                patch.object(ranker, "_probar_razonamiento", return_value=(True, "ok")),
                patch.object(ranker, "SALIDA", str(output)),
                patch.object(ranker, "STATE_DIR", tmp),
                probe as text_probe,
            ):
                result = ranker.generar_ranking()

        self.assertEqual(text_probe.call_count, 1)
        self.assertEqual(text_probe.call_args.args[0], "org/free-agent-reasoning:free")
        self.assertEqual(tools_probe.call_count, 1)
        self.assertEqual(result["total_modelos_catalogo"], 2)
        self.assertEqual(result["total_modelos_omitidos_por_precio"], 1)
        self.assertEqual(len(result["ranking"]), 1)
        self.assertTrue(result["ranking"][0]["gratis"])
        self.assertTrue(result["ranking"][0]["apto_agente"])

    def test_stale_static_free_ids_are_not_probed_when_catalog_is_unavailable(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "ranking.json"
            with (
                patch.object(ranker, "get_tokenrouter_api_key", return_value="local-test-key"),
                patch.object(ranker, "get_tokenrouter_accounts", return_value=[{"id": "local-test-account", "api_key": "local-test-key"}]),
                patch.object(ranker, "obtener_modelos_remotos", return_value={}),
                patch.object(ranker, "prober_modelo") as text_probe,
                patch.object(ranker, "SALIDA", str(output)),
                patch.object(ranker, "STATE_DIR", tmp),
            ):
                result = ranker.generar_ranking()
        text_probe.assert_not_called()
        self.assertEqual(result["total_modelos"], 0)

    def test_uses_a_free_account_that_actually_passes_the_probe(self):
        catalog = {
            "org/free-agent-reasoning:free": {
                "id": "org/free-agent-reasoning:free",
                "pricing": {"input": 0, "output": 0},
            },
        }
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "ranking.json"
            with (
                patch.object(ranker, "get_tokenrouter_api_key", return_value="local-test-key-1"),
                patch.object(ranker, "get_tokenrouter_accounts", return_value=[
                    {"id": "test-account-1", "api_key": "local-test-key-1"},
                    {"id": "test-account-2", "api_key": "local-test-key-2"},
                ]),
                patch.object(ranker, "obtener_modelos_remotos", side_effect=[catalog, catalog]),
                patch.object(ranker, "prober_modelo", side_effect=[(False, "sin_acceso"), (True, "ok")]) as text_probe,
                patch.object(ranker, "probar_herramienta_openai", return_value=(True, "ok")),
                patch.object(ranker, "_probar_razonamiento", return_value=(True, "ok")),
                patch.object(ranker, "SALIDA", str(output)),
                patch.object(ranker, "STATE_DIR", tmp),
            ):
                result = ranker.generar_ranking()
        self.assertEqual(text_probe.call_count, 2)
        self.assertEqual(result["ranking"][0]["cuenta_id"], "test-account-2")
        self.assertEqual(result["ranking"][0]["cuentas_compatibles"], ["test-account-2"])


if __name__ == "__main__":
    unittest.main()
