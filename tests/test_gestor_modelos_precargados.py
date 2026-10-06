import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from proxy import gestor_modelos


class RankingsPrecargadosTests(unittest.TestCase):
    def test_catalogos_de_exportacion_no_se_publican_como_rankings_locales(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = Path(tmp) / "state"
            state.mkdir()
            (state / "rankings_precargados.json").write_text(
                json.dumps({"formato": 1, "estado": "catalogo_inicial"}),
                encoding="utf-8",
            )
            with patch.object(gestor_modelos, "RAIZ", tmp):
                cargadores = (
                    gestor_modelos.cargar_ranking_global,
                    gestor_modelos.cargar_ranking,
                    gestor_modelos.cargar_ranking_openrouter,
                    gestor_modelos.cargar_ranking_nvidia,
                    gestor_modelos.cargar_ranking_cloudflare,
                    gestor_modelos.cargar_ranking_cohere,
                    gestor_modelos.cargar_ranking_google,
                    gestor_modelos.cargar_ranking_siliconflow,
                    gestor_modelos.cargar_ranking_zhipu,
                    gestor_modelos.cargar_ranking_groq,
                    gestor_modelos.cargar_ranking_tokenrouter,
                    gestor_modelos.cargar_ranking_xkiro,
                    gestor_modelos.cargar_ranking_tokenharbor,
                    gestor_modelos.cargar_ranking_apinex,
                    lambda: gestor_modelos.cargar_ranking_proveedor("cerebras"),
                )
                for cargar in cargadores:
                    with self.subTest(cargador=getattr(cargar, "__name__", "proveedor")):
                        self.assertEqual(cargar(), [])
                resumen = gestor_modelos.resumen_rankings()
                self.assertEqual(resumen["global"]["total"], 0)
                self.assertEqual(resumen["global"]["top_modelo"], "N/A")


if __name__ == "__main__":
    unittest.main()
