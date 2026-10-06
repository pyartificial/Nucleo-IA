#!/usr/bin/env python3
"""Asistente local de cuentas. Solo biblioteca estándar; Windows y Linux."""
from __future__ import annotations

import argparse
import hashlib
import hmac
import html
import json
import os
from pathlib import Path
import secrets
import socket
import subprocess
import sys
import threading
import time
import urllib.parse
import urllib.request
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from scripts.servicios_backend import GestorServicios, ErrorUsuario, escribir_json, leer_json, peticion_json
from scripts.gestor_perfiles import GestorPerfiles, ErrorPerfil
from scripts.gestor_rankings_panel import GestorRankings, ErrorRanking
from scripts.gestor_panel_operativo import GestorPanelOperativo, ErrorOperacion


class Servidor(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = False

    def __init__(self, address, root=ROOT, panel=False):
        super().__init__(address, Handler)
        self.gestor = GestorServicios(root)
        self.perfiles = GestorPerfiles(root)
        self.rankings = GestorRankings(root)
        self.operacion = GestorPanelOperativo(root, self.gestor, self.rankings)
        self.panel = panel
        self.token = secrets.token_urlsafe(32)
        self.origen = f'http://127.0.0.1:{self.server_port}'
        self.instance = hashlib.sha256(str(Path(root).resolve()).encode()).hexdigest()
        self.runtime = Path(root) / 'state' / 'mis_servicios_runtime.json'
        self.proxy_lock = threading.Lock()

    def publicar(self):
        escribir_json(self.runtime, dict(port=self.server_port, token=self.token, instance=self.instance,
                                         pid=os.getpid(), catalog_version=8))

    def aplicar(self):
        from granja import get_python_bin
        with self.proxy_lock:
            config = self.gestor.config()
            ollama = self.gestor.iniciar_ollama_registradas()
            port = int(config.get('PROXY_PORT', 8080))
            if not 1024 <= port <= 65535:
                raise ErrorUsuario('El puerto de Núcleo IA necesita revisión.')
            origin = f'http://127.0.0.1:{port}'
            def reload():
                req = urllib.request.Request(origin + '/internal/mis-servicios/recargar', data=b'{}',
                    headers={'X-Nucleo-Local': self.token, 'Content-Type': 'application/json'}, method='POST')
                try:
                    with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(req, timeout=5) as r:
                        return json.loads(r.read())
                except (OSError, ValueError):
                    return None
            with socket.socket() as s:
                s.settimeout(1)
                ocupado = s.connect_ex(('127.0.0.1', port)) == 0
            if ocupado:
                res = reload()
                if res and res.get('aplicado'):
                    return dict(mensaje=self._mensaje_inicio(ollama, 'Las conexiones ya fueron cargadas por Núcleo IA.'), aplicado=True, ollama=ollama)
                return dict(mensaje='Hay un servidor anterior abierto. Cerralo con “detener_todo” y volvé a tocar “Aplicar conexiones”. Las cuentas están guardadas.', aplicado=False)
            env = os.environ.copy()
            env.update(PYTHONPATH=str(ROOT), PYTHONUTF8='1')
            opts = {'creationflags': 0x08000000 | 0x00000200} if sys.platform == 'win32' else {'start_new_session': True}
            # El proxy conserva su propia configuración; el asistente nunca cambia su alcance de red.
            logfile = self.gestor.root / 'state' / 'proxy_desde_servicios.log'
            with open(logfile, 'a', encoding='utf-8') as output:
                self.gestor.proxy_process = subprocess.Popen([get_python_bin(), '-m', 'proxy.servidor'], cwd=ROOT,
                    env=env, stdin=subprocess.DEVNULL, stdout=output, stderr=output, **opts)
            for _ in range(30):
                if self.gestor.proxy_process.poll() is not None:
                    raise ErrorUsuario('Núcleo IA no pudo iniciar. Ejecutá el instalador de tu sistema para revisar las dependencias.')
                if reload():
                    return dict(mensaje=self._mensaje_inicio(ollama, 'Núcleo IA está iniciado y cargó tus conexiones.'), aplicado=True, ollama=ollama)
                time.sleep(.3)
            return dict(mensaje='Núcleo IA todavía está iniciando. Esperá unos segundos y volvé a aplicar.', aplicado=False)

    @staticmethod
    def _mensaje_inicio(ollama, base):
        total = int(ollama.get('total', 0))
        disponibles = int(ollama.get('disponibles', 0))
        errores = ollama.get('errores', [])
        if not total:
            return base + ' No hay cuentas Ollama registradas.'
        if errores:
            return base + f' Ollama: {disponibles} de {total} instancias disponibles; revisá {", ".join(errores[:4])}.'
        return base + f' Ollama: {disponibles} de {total} instancias disponibles.'

    def recargar_proxy(self):
        """Aplica cambios de cuentas al proxy activo sin iniciar otro proceso."""
        config = self.gestor.config()
        port = int(config.get('PROXY_PORT', 8080))
        req = urllib.request.Request(
            f'http://127.0.0.1:{port}/internal/mis-servicios/recargar',
            data=b'{}',
            headers={'X-Nucleo-Local': self.token, 'Content-Type': 'application/json'},
            method='POST')
        try:
            with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(req, timeout=3) as response:
                return json.loads(response.read()).get('aplicado') is True
        except (OSError, ValueError, TypeError):
            return False


class Handler(BaseHTTPRequestHandler):
    server_version = 'NucleoIA'

    def log_message(self, *_):
        pass  # Nunca registrar URLs OAuth, cuerpos ni credenciales.

    def responder(self, code, body, tipo='application/json; charset=utf-8'):
        raw = json.dumps(body, ensure_ascii=False).encode() if isinstance(body, (dict, list)) else body.encode() if isinstance(body, str) else body
        self.send_response(code)
        self.send_header('Content-Type', tipo)
        self.send_header('Content-Length', str(len(raw)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('X-Frame-Options', 'DENY')
        self.send_header('Referrer-Policy', 'no-referrer')
        self.send_header('Content-Security-Policy', "default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
        self.end_headers()
        self.wfile.write(raw)

    def host_valido(self):
        return self.headers.get('Host') in {f'127.0.0.1:{self.server.server_port}', f'localhost:{self.server.server_port}'}

    def autenticado(self):
        return hmac.compare_digest(self.headers.get('X-Nucleo-Session', ''), self.server.token)

    def do_GET(self):
        if not self.host_valido():
            return self.responder(403, {'mensaje': 'Dirección no permitida.'})
        parsed = urllib.parse.urlsplit(self.path)
        path = parsed.path
        if path == '/health':
            return self.responder(200, dict(app='nucleo-mis-servicios', instance=self.server.instance))
        if path.startswith('/locales/') and path.endswith('.json'):
            locale = path.removeprefix('/locales/').removesuffix('.json')
            if not locale or any(ch not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-' for ch in locale):
                return self.responder(404, {'mensaje': 'Idioma no disponible.'})
            locale_file = ROOT / 'ui' / 'locales' / f'{locale}.json'
            if not locale_file.is_file():
                return self.responder(404, {'mensaje': 'Idioma no disponible.'})
            return self.responder(200, locale_file.read_bytes(), 'application/json; charset=utf-8')
        if path.startswith('/oauth/callback/'):
            try:
                code = urllib.parse.parse_qs(parsed.query).get('code', [''])[0]
                self.server.gestor.oauth_completar(path.rsplit('/', 1)[-1], code)
                self.send_response(303)
                self.send_header('Location', '/#sesion=' + self.server.token + '&conectado=openrouter')
                self.send_header('Cache-Control', 'no-store')
                self.send_header('Referrer-Policy', 'no-referrer')
                self.send_header('Content-Length', '0')
                self.end_headers()
                return
            except ErrorUsuario as exc:
                return self.responder(400, '<!doctype html><html lang="es"><meta charset="utf-8"><title>Volvé a Mis servicios</title><h1>No se completó la conexión</h1><p>' + html.escape(str(exc)) + '</p><p>Volvé a la pestaña Mis servicios o abrí su acceso directo.</p></html>', 'text/html; charset=utf-8')
            except Exception:
                return self.responder(500, {'mensaje': 'No se pudo guardar la conexión. Volvé al asistente para reintentar.'})
        if path in {'/rankings', '/rankings/'}:
            return self.responder(200, (ROOT / 'ui' / 'rankings.html').read_bytes(), 'text/html; charset=utf-8')
        if path in {'/trasladar-cuentas', '/trasladar-cuentas/'}:
            self.server.panel = True
            return self.responder(200, (ROOT / 'ui' / 'trasladar_cuentas.html').read_bytes(), 'text/html; charset=utf-8')
        if path in {'/acerca', '/acerca/'}:
            self.server.panel = True
            return self.responder(200, (ROOT / 'ui' / 'acerca.html').read_bytes(), 'text/html; charset=utf-8')
        if path == '/trasladar.js':
            return self.responder(200, (ROOT / 'ui' / 'trasladar_cuentas.js').read_bytes(), 'application/javascript; charset=utf-8')
        if path == '/api/trasladar/crear':
            if not self.autenticado():
                return self.responder(401, {'mensaje': 'La sesión cambió. Abrí nuevamente el Centro de control.'})
            try:
                from scripts.transferencia_cuentas import crear_paquete
                raw = crear_paquete(ROOT)
            except ErrorUsuario as exc:
                return self.responder(400, {'mensaje': str(exc)})
            self.send_response(200)
            self.send_header('Content-Type', 'application/zip')
            self.send_header('Content-Disposition', 'attachment; filename="nucleo-ia-cuentas.zip"')
            self.send_header('Content-Length', str(len(raw)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.end_headers()
            self.wfile.write(raw)
            return
        if path == '/rankings/app.js':
            return self.responder(200, (ROOT / 'ui' / 'rankings.js').read_bytes(), 'application/javascript; charset=utf-8')
        if path == '/rankings/style.css':
            css = b'[hidden]{display:none!important}\n' + (ROOT / 'ui' / 'rankings.css').read_bytes()
            return self.responder(200, css, 'text/css; charset=utf-8')
        if path == '/rankings/progress.css':
            return self.responder(200, (ROOT / 'ui' / 'rankings_progress.css').read_bytes(), 'text/css; charset=utf-8')
        if path == '/shell.css':
            return self.responder(200, (ROOT / 'ui' / 'shell.css').read_bytes(), 'text/css; charset=utf-8')
        if path == '/control':
            path = '/'
            self.server.panel = True
        elif path == '/mis-servicios':
            path = '/'
            self.server.panel = False
        static = ({'/': 'centro_control.html', '/app.js': 'centro_control.js', '/style.css': 'centro_control.css'}
                  if self.server.panel else
                  {'/': 'mis_servicios.html', '/app.js': 'mis_servicios.js', '/style.css': 'mis_servicios.css'})
        if path in static:
            mime = 'text/html' if path == '/' else 'application/javascript' if path.endswith('.js') else 'text/css'
            return self.responder(200, (ROOT / 'ui' / static[path]).read_bytes(), mime + '; charset=utf-8')
        if path == '/api/servicios':
            if not self.autenticado():
                return self.responder(401, {'mensaje': 'Para entrar, abrí nuevamente el acceso directo Mis servicios.'})
            try:
                return self.responder(200, self.server.gestor.lista())
            except ErrorUsuario as exc:
                return self.responder(400, {'mensaje': str(exc)})
        if path == '/api/proveedores-opcionales':
            if not self.autenticado():
                return self.responder(401, {'mensaje': 'Para entrar, abrí nuevamente el acceso directo Mis servicios.'})
            try:
                return self.responder(200, self.server.gestor.lista_opcionales())
            except ErrorUsuario as exc:
                return self.responder(400, {'mensaje': str(exc)})
        if path == '/api/perfil':
            if not self.autenticado():
                return self.responder(401, {'mensaje': 'Para entrar, abrí nuevamente el acceso directo Mis servicios.'})
            return self.responder(200, self.server.perfiles.estado())
        if path == '/api/panel/resumen':
            if not self.autenticado():
                return self.responder(401, {'mensaje': 'Para entrar, abrí nuevamente el Centro de control.'})
            try:
                from scripts.catalogo_servicios import SERVICIOS
                rankings = []
                for archivo in sorted((ROOT / 'state').glob('ranking_*.json')):
                    try:
                        datos = json.loads(archivo.read_text(encoding='utf-8'))
                        cantidad = len(datos.get('modelos', datos.get('data', []))) if isinstance(datos, dict) else 0
                        rankings.append({'nombre': archivo.stem.removeprefix('ranking_'), 'modelos': cantidad, 'fecha': time.strftime('%Y-%m-%d', time.localtime(archivo.stat().st_mtime))})
                    except (OSError, ValueError, TypeError):
                        continue
                return self.responder(200, {'perfil': self.server.perfiles.estado(), 'servicios': len(SERVICIOS), 'cuentas': sum(len(x['cuentas']) for x in self.server.gestor.lista()['servicios']), 'capacidades': sorted({c for s in SERVICIOS for c in s.get('capacidades', [])}), 'rankings': rankings})
            except (ErrorUsuario, OSError):
                return self.responder(400, {'mensaje': 'No se pudo leer el estado del panel.'})
        if path == '/api/rankings':
            if not self.autenticado():
                return self.responder(401, {'mensaje': 'Para entrar, abrí nuevamente el Centro de control.'})
            try:
                return self.responder(200, self.server.rankings.resumen())
            except (ErrorRanking, OSError):
                return self.responder(400, {'mensaje': 'No se pudieron leer los rankings guardados.'})
        if path == '/api/panel/operacion':
            if not self.autenticado():
                return self.responder(401, {'mensaje': 'Para entrar, abrí nuevamente el Centro de control.'})
            try:
                return self.responder(200, self.server.operacion.estado())
            except (ErrorOperacion, OSError):
                return self.responder(400, {'mensaje': 'No se pudo leer el estado operativo de Núcleo IA.'})
        return self.responder(404, {'mensaje': 'Página no encontrada.'})

    def do_POST(self):
        if not self.host_valido() or self.headers.get('Origin') not in {self.server.origen, f'http://localhost:{self.server.server_port}'}:
            return self.responder(403, {'mensaje': 'Esta acción debe hacerse desde Mis servicios.'})
        if not self.autenticado():
            return self.responder(401, {'mensaje': 'La sesión cambió. Abrí nuevamente Mis servicios.'})
        if self.path == '/api/trasladar/cargar':
            if self.headers.get_content_type() != 'application/zip':
                return self.responder(415, {'mensaje': 'Elegí un paquete ZIP de Núcleo IA.'})
            try:
                size = int(self.headers.get('Content-Length', '0'))
                if not 0 < size <= 2_000_000:
                    return self.responder(413, {'mensaje': 'El paquete no puede superar los 2 MB.'})
                from scripts.transferencia_cuentas import sumar_paquete
                res = sumar_paquete(ROOT, self.rfile.read(size))
                res['proxy_recargado'] = self.server.recargar_proxy()
                res['mensaje'] = ('Las cuentas se agregaron y el proxy cargó los cambios.' if res['proxy_recargado']
                                  else 'Las cuentas se agregaron. Reiniciá Núcleo IA para que tome las nuevas conexiones.')
                return self.responder(200, res)
            except ErrorUsuario as exc:
                return self.responder(400, {'mensaje': str(exc)})
            except Exception:
                return self.responder(500, {'mensaje': 'No se pudo completar la transferencia. No se informó el contenido de las claves.'})
        if self.headers.get_content_type() != 'application/json':
            return self.responder(415, {'mensaje': 'Formato no permitido.'})
        try:
            size = int(self.headers.get('Content-Length', '0'))
            if not 0 < size <= 16384:
                return self.responder(413, {'mensaje': 'El formulario es demasiado grande.'})
            body = json.loads(self.rfile.read(size))
            if not isinstance(body, dict):
                raise ValueError()
            g = self.server.gestor
            if self.path == '/api/conectar':
                res = g.conectar(body)
            elif self.path == '/api/proveedores-opcionales/configurar':
                res = g.configurar_opcional(body)
                res['proxy_recargado'] = self.server.recargar_proxy()
            elif self.path == '/api/verificar':
                res = g.verificar(body.get('proveedor', ''), body.get('id', ''))
            elif self.path == '/api/oauth/iniciar':
                res = g.oauth_iniciar(self.server.origen, str(body.get('email', '')).strip())
            elif self.path == '/api/ollama/preparar':
                res = g.ollama_preparar(body.get('email', '').strip(), str(body.get('id', '')).strip())
            elif self.path == '/api/ollama/comprobar':
                res = g.ollama_finalizar(body.get('local') is True)
            elif self.path == '/api/aplicar':
                res = self.server.aplicar()
            elif self.path == '/api/abrir_privado':
                res = self.abrir_privado(body.get('url', ''))
            elif self.path == '/api/pozo/agregar':
                res = g.agregar_email_pozo(body.get('email', ''))
            elif self.path == '/api/perfil/aplicar':
                res = self.server.perfiles.aplicar(
                    body.get('perfil', 'personal'),
                    acceso_red=body.get('acceso_red') is True,
                    hosts_permitidos=str(body.get('hosts_permitidos', '')),
                    origenes=str(body.get('origenes', '')),
                )
            elif self.path == '/api/rankings/guardar':
                res = self.server.rankings.guardar(body)
            elif self.path == '/api/rankings/restaurar':
                res = self.server.rankings.restaurar(str(body.get('alcance', '')))
            elif self.path == '/api/rankings/actualizar':
                res = self.server.rankings.actualizar(str(body.get('objetivo', '')), body.get('conservar') is not False)
            elif self.path == '/api/rankings/cancelar':
                res = self.server.rankings.cancelar()
            elif self.path == '/api/panel/iniciar':
                res = self.server.aplicar()
            elif self.path == '/api/panel/detener':
                res = self.server.operacion.detener()
            elif self.path == '/api/panel/reiniciar':
                self.server.operacion.detener()
                res = self.server.aplicar()
            elif self.path == '/api/panel/pausar':
                res = self.server.operacion.pausar(body.get('pausado') is True)
            else:
                return self.responder(404, {'mensaje': 'Acción no encontrada.'})
            return self.responder(200, res)
        except ErrorUsuario as exc:
            return self.responder(400, {'mensaje': str(exc)})
        except ErrorPerfil as exc:
            return self.responder(400, {'mensaje': str(exc)})
        except ErrorRanking as exc:
            return self.responder(400, {'mensaje': str(exc)})
        except ErrorOperacion as exc:
            return self.responder(400, {'mensaje': str(exc)})
        except (ValueError, TypeError, AttributeError):
            return self.responder(400, {'mensaje': 'Revisá los datos del formulario y volvé a intentar.'})
        except Exception:
            return self.responder(500, {'mensaje': 'No pudimos completar la operación. Revisá los permisos de la carpeta y el espacio disponible.'})

    def abrir_privado(self, url):
        import shutil
        url = str(url or '').strip()
        if not (url.startswith('https://') or url.startswith('http://')):
            raise ErrorUsuario('Dirección inválida.')
        browsers = [
            ('opera-gx', ['--private']),
            ('opera', ['--private']),
            ('firefox', ['--private-window']),
            ('google-chrome-stable', ['--incognito']),
            ('google-chrome', ['--incognito']),
            ('chromium', ['--incognito']),
            ('chromium-browser', ['--incognito']),
            ('brave-browser', ['--incognito']),
        ]
        for b_name, flags in browsers:
            path = shutil.which(b_name)
            if path:
                try:
                    subprocess.Popen([path] + flags + [url], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    return dict(abierto=True, navegador=b_name, modo='privado')
                except OSError:
                    pass
        webbrowser.open(url)
        return dict(abierto=True, navegador='default', modo='estandar')



def sesion_existente(root=ROOT, panel=False):
    path = Path(root) / 'state' / 'mis_servicios_runtime.json'
    try:
        runtime = leer_json(path)
        port = int(runtime.get('port', 0))
        if not 1024 <= port <= 65535:
            return None
        code, info = peticion_json(f'http://127.0.0.1:{port}/health', timeout=.4)
        expected = hashlib.sha256(str(Path(root).resolve()).encode()).hexdigest()
        if (code == 200 and info.get('instance') == expected and info.get('app') == 'nucleo-mis-servicios'
                and runtime.get('catalog_version', 0) >= 8):
            token = runtime.get('token', '')
            if isinstance(token, str) and len(token) >= 32:
                ruta = '/control' if panel else '/mis-servicios'
                return f'http://127.0.0.1:{port}{ruta}#sesion=' + token
    except (ErrorUsuario, ValueError, OSError):
        pass
    return None


def abrir(url):
    try:
        if webbrowser.open(url):
            return
    except Exception:
        pass
    try:
        import tkinter as tk
        root = tk.Tk()
        root.title('Mis servicios — Núcleo IA')
        tk.Label(root, text='No se abrió el navegador. Copiá esta dirección y abrila en tu navegador:', padx=20, pady=20).pack()
        campo = tk.Entry(root, width=100)
        campo.insert(0, url)
        campo.pack(padx=20, pady=10)
        campo.select_range(0, 'end')
        def copiar():
            root.clipboard_clear()
            root.clipboard_append(url)
        tk.Button(root, text='Copiar dirección', command=copiar).pack(pady=10)
        tk.Button(root, text='Reintentar', command=lambda: webbrowser.open(url)).pack(pady=10)
        root.mainloop()
    except Exception:
        print('Abrí esta dirección en el navegador de esta computadora:', url)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--serve', action='store_true')
    parser.add_argument('--no-browser', action='store_true')
    parser.add_argument('--port', type=int, default=0)
    parser.add_argument('--panel', action='store_true', help='Abrir el Centro de control general')
    args = parser.parse_args()
    existing = sesion_existente(panel=args.panel)
    if existing:
        if not args.no_browser:
            abrir(existing)
        return 0
    # En Linux el proceso que abre un acceso directo puede vivir dentro de un
    # grupo administrado por el escritorio. Si ese proceso crea un hijo y sale,
    # algunos escritorios terminan también el hijo. Mantener el servidor en el
    # mismo proceso evita dejar una pestaña abierta apuntando a un puerto muerto.
    if not args.serve and sys.platform != 'win32':
        args.serve = True
    if not args.serve:
        opts = {'creationflags': 0x08000000 | 0x00000200} if sys.platform == 'win32' else {'start_new_session': True}
        child_args = [sys.executable, str(Path(__file__).resolve()), '--serve', '--no-browser']
        if args.panel:
            child_args.append('--panel')
        child = subprocess.Popen(child_args,
                                 cwd=ROOT, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, **opts)
        for _ in range(100):
            url = sesion_existente(panel=args.panel)
            if url:
                if not args.no_browser:
                    abrir(url)
                return 0
            if child.poll() is not None:
                break
            time.sleep(.1)
        print('No se pudo abrir Mis servicios. Revisá que la carpeta permita guardar archivos.')
        return 1
    # Puerto derivado de la carpeta: dos clics compiten por el mismo socket;
    # distintas copias pueden abrirse sin compartir cuentas.
    port = args.port or (18000 + int(hashlib.sha256(str(ROOT).encode()).hexdigest()[:6], 16) % 10000)
    server = None
    for candidate in range(port, min(port + 20, 65535)):
        try:
            server = Servidor(('127.0.0.1', candidate), panel=args.panel)
            break
        except OSError:
            time.sleep(.1)
            if sesion_existente():
                return 0
    if server is None:
        return 1
    server.publicar()
    if not args.no_browser:
        threading.Thread(target=abrir, args=(server.origen + '/#sesion=' + server.token,), daemon=True).start()
    try:
        server.serve_forever()
    finally:
        server.server_close()
        try:
            if leer_json(server.runtime).get('pid') == os.getpid():
                server.runtime.unlink(missing_ok=True)
        except (OSError, ErrorUsuario):
            pass
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
