import json
import tempfile
import unittest
from pathlib import Path

from scripts.gestor_perfiles import ErrorPerfil, GestorPerfiles


class GestorPerfilesTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / ".env").write_text(
            "PROXY_PORT=8080\nPERFIL_USO=personal\nAUTH_ENABLED=false\nCORS_ALLOW_ORIGINS=*\n",
            encoding="utf-8",
        )
        self.gestor = GestorPerfiles(self.root)

    def tearDown(self):
        self.tmp.cleanup()

    def test_profesional_genera_claves_y_elimina_comodin(self):
        estado = self.gestor.aplicar("profesional")
        env = (self.root / ".env").read_text(encoding="utf-8")
        self.assertEqual(estado["perfil"], "profesional")
        self.assertTrue(estado["protegido"])
        self.assertIn("AUTH_ENABLED=true", env)
        self.assertIn("CORS_ALLOW_ORIGINS=\n", env)
        self.assertIn("NUCLEO_API_KEY=", env)
        self.assertIn("NUCLEO_ADMIN_KEY=", env)
        self.assertEqual(len(list((self.root / "state" / "config_backups").glob("*.bak"))), 1)

    def test_profesional_en_red_exige_hosts_y_rechaza_comodin(self):
        with self.assertRaises(ErrorPerfil):
            self.gestor.aplicar("profesional", acceso_red=True)
        with self.assertRaises(ErrorPerfil):
            self.gestor.aplicar("profesional", acceso_red=True, hosts_permitidos="*")

    def test_personal_vuelve_a_loopback_sin_borrar_claves(self):
        self.gestor.aplicar("profesional")
        self.gestor.aplicar("personal")
        estado = self.gestor.estado()
        env = (self.root / ".env").read_text(encoding="utf-8")
        self.assertEqual(estado["perfil"], "personal")
        self.assertEqual(estado["host"], "127.0.0.1")
        self.assertFalse(estado["autenticacion"])
        self.assertIn("NUCLEO_API_KEY=", env)
        eventos = [json.loads(x) for x in (self.root / "state" / "auditoria_panel.jsonl").read_text().splitlines()]
        self.assertEqual([e["perfil"] for e in eventos], ["profesional", "personal"])


if __name__ == "__main__":
    unittest.main()
