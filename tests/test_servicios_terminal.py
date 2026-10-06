import contextlib
import io
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch, MagicMock
from scripts import servicios_terminal as terminal

ROOT = Path(__file__).resolve().parents[1]


class DeteccionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='nucleo con espacios ')
        self.root = Path(self.tmp.name)
        for name in ('mis_servicios.sh', 'agregar_cuentas.sh'):
            shutil.copy2(ROOT / name, self.root / name)
        py = self.root / 'venv/bin/python'
        py.parent.mkdir(parents=True)
        py.write_text('#!/bin/sh\nprintf "%s\\n" "$@"\n')
        py.chmod(0o755)

    def tearDown(self):
        self.tmp.cleanup()

    def lanzar(self, flags=(), variables=None):
        env = {k:v for k,v in os.environ.items() if k not in ('DISPLAY','WAYLAND_DISPLAY')}
        env.update(variables or {})
        return subprocess.run(['bash',str(self.root/'agregar_cuentas.sh'),*flags],env=env,text=True,capture_output=True,check=True).stdout

    def test_sin_escritorio_y_ssh(self):
        self.assertIn('servicios_terminal.py',self.lanzar())
        self.assertIn('servicios_terminal.py',self.lanzar(variables={'SSH_CONNECTION':'prueba'}))

    def test_x11_y_wayland(self):
        for variables in ({'DISPLAY':':0'},{'WAYLAND_DISPLAY':'wayland-0'}):
            self.assertIn('/scripts/mis_servicios.py',self.lanzar(variables=variables))

    def test_modo_forzado(self):
        self.assertIn('servicios_terminal.py',self.lanzar(['--terminal'],{'DISPLAY':':0'}))
        self.assertIn('/scripts/mis_servicios.py',self.lanzar(['--gui']))

    def test_argumentos_servidor_no_caen_en_menu(self):
        for flags in (['--no-browser'],['--serve'],['--port','19000'],['--help']):
            output=self.lanzar(flags)
            self.assertIn('/scripts/mis_servicios.py',output)
            self.assertIn(flags[0],output)


class MenuTests(unittest.TestCase):
    def ejecutar(self, inputs, gestor=None):
        with patch.object(terminal.sys.stdin,'isatty',return_value=True), patch('builtins.input',side_effect=inputs), patch.object(terminal,'GestorServicios',return_value=gestor or MagicMock()), contextlib.redirect_stdout(io.StringIO()) as out:
            rc=terminal.main()
        return rc,out.getvalue()

    def test_salir_y_menu_completo(self):
        code,out=self.ejecutar(['0'])
        self.assertEqual(code,0)
        for s in terminal.SERVICIOS:
            self.assertIn(s['nombre'],out)

    def test_sin_terminal_no_espera_entrada(self):
        with patch.object(terminal.sys.stdin,'isatty',return_value=False), contextlib.redirect_stdout(io.StringIO()) as out:
            self.assertEqual(terminal.main(),2)
        self.assertIn('ssh -t',out.getvalue())

    def test_ollama_no_abre_navegador(self):
        gestor = MagicMock()
        gestor.emails_conocidos.return_value = []
        with patch('scripts.agregar_ollama.main') as ollama:
            self.ejecutar(['1','0'], gestor)
        ollama.assert_called_once_with(abrir_navegador=False, email_inicial='')

    def test_clave_oculta_y_sin_exposicion_en_salida(self):
        g=MagicMock()
        g.conectar.return_value={'guardada':True,'mensaje':'Acceso comprobado'}
        with patch.object(terminal.getpass,'getpass',return_value='clave-ficticia') as secret:
            code,out=self.ejecutar(['2','correo@ejemplo.com','Mi cuenta','0'],g)
        self.assertEqual(code,0)
        secret.assert_called_once()
        self.assertNotIn('clave-ficticia',out)
        self.assertEqual(g.conectar.call_args.args[0]['proveedor'],'groq')

    def test_guardar_pendiente_solo_con_eleccion(self):
        g=MagicMock()
        g.conectar.return_value=dict(guardada=False,estado='sin_conexion',mensaje='Sin conexión',verificada=False)
        g.guardar.return_value={'guardada':True}
        with patch.object(terminal.getpass,'getpass',return_value='clave-ficticia'):
            self.ejecutar(['2','correo@ejemplo.com','','s','0'],g)
        self.assertNotIn('guardada',g.guardar.call_args.kwargs['check'])
        g.guardar.assert_called_once()

    def test_cancelar_clave_no_guarda(self):
        g=MagicMock()
        with patch.object(terminal.getpass,'getpass',return_value=''):
            self.ejecutar(['2','','0','0'],g)
        g.conectar.assert_not_called()


if __name__ == '__main__':
    unittest.main()
