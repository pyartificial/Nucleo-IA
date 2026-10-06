"""Pruebas con datos ficticios: no usan cuentas, claves ni servicios reales."""
import base64
import hashlib
import http.client
import json
import os
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch
from urllib.parse import urlsplit, parse_qs

from scripts import servicios_backend as backend
from scripts.mis_servicios import Servidor
from scripts.catalogo_servicios import SERVICIOS
from proxy.servicios_locales import autorizar_recarga

CLAVE = 'clave-ficticia-para-pruebas'
def clave_para(p):
    return {'openrouter': 'sk-or-v1-' + 'prueba_' * 8, 'xkiro': 'sk-xt-' + 'prueba_' * 6, 'tokenharbor': 'thk_' + 'prueba_' * 6}.get(p, CLAVE)


class CuentasTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / '.env').write_text('PROXY_PORT=9999\nSERVICIOS_ACTIVOS=ollama\n', encoding='utf-8')
        (self.root / 'cuentas.json').write_text('{"proveedores": {"ollama": {"cuentas": [{"id": "acc1", "puerto": 11434}]}}, "extra": "conservar"}', encoding='utf-8')
        self.g = backend.GestorServicios(self.root)

    def tearDown(self):
        self.tmp.cleanup()

    def test_los_once_proveedores_guardan_sin_filtrar_secretos(self):
        for p in backend.VARIABLES:
            key = clave_para(p)
            r = self.g.guardar(p, key, 'Mi cuenta', 'a' * 32 if p == 'cloudflare' else '', email=f'{p}@ejemplo.com')
            self.assertTrue(r['guardada'])
            self.assertEqual(self.g.clave_guardada(p, self.g.buscar(p, r['id'])), key)
        self.assertGreaterEqual(len(self.g.lista()['servicios']), 14)
        self.assertNotIn(CLAVE, json.dumps(self.g.lista()))
        self.assertNotIn(CLAVE, (self.root / 'cuentas.json').read_text())
        self.assertEqual(self.g.cuentas()['extra'], 'conservar')
        self.assertEqual(self.g.config()['PROXY_PORT'], '9999')
        self.assertEqual(set(self.g.config()['SERVICIOS_ACTIVOS'].split(',')),
                         {s['id'] for s in SERVICIOS if not s.get('solo_tts') and not s.get('solo_capacidades')})
        if os.name != 'nt':
            self.assertEqual((self.root / '.env').stat().st_mode & 0o777, 0o600)

    def test_reemplazo_no_duplica_y_nuevas_cuentas_no_colisionan(self):
        first = self.g.guardar('groq', CLAVE, email='primera@ejemplo.com')
        second = self.g.guardar('groq', CLAVE + '2', email='segunda@ejemplo.com')
        self.assertNotEqual(first['id'], second['id'])
        self.g.guardar('groq', CLAVE + '3', account_id=first['id'], email='primera@ejemplo.com')
        rows = self.g.cuentas()['proveedores']['groq']['cuentas']
        self.assertEqual(len(rows), 2)
        self.assertEqual(self.g.clave_guardada('groq', rows[0]), CLAVE + '3')
        self.assertEqual(self.g.clave_guardada('groq', rows[1]), CLAVE + '2')

    def test_emails_conocidos_y_pozo_en_lista(self):
        self.g.guardar('groq', CLAVE, email='pozo1@ejemplo.com')
        self.g.guardar('nvidia', CLAVE, email='pozo2@ejemplo.com')
        self.assertIn('pozo1@ejemplo.com', self.g.emails_conocidos())
        self.assertIn('pozo2@ejemplo.com', self.g.emails_conocidos())
        lista = self.g.lista()
        self.assertIn('emails_conocidos', lista)
        self.assertIn('pozo1@ejemplo.com', lista['emails_conocidos'])

    def test_agregar_email_pozo_independiente(self):
        res = self.g.agregar_email_pozo('nuevo_pozo@ejemplo.com')
        self.assertTrue(res['agregado'])
        self.assertIn('nuevo_pozo@ejemplo.com', self.g.emails_conocidos())
        self.assertIn('nuevo_pozo@ejemplo.com', self.g.lista()['emails_conocidos'])

    def test_opcional_activa_proveedor_y_cuenta_sin_inventar_capacidades(self):
        data = self.g.cuentas()
        data.setdefault('proveedores', {})['minimax'] = {'cuentas': [
            {'id': 'mm1', 'nombre': 'MiniMax pruebas', 'habilitado': False,
             'uso_pago': False, 'capacidades_habilitadas': []}]}
        backend.escribir_json(self.root / 'cuentas.json', data)
        self.g.configurar_opcional({'proveedor': 'minimax', 'habilitado': True})
        self.g.configurar_opcional({'proveedor': 'minimax', 'id': 'mm1', 'habilitado': True,
                                    'uso_pago': True, 'primaria': True})
        service = next(x for x in self.g.lista_opcionales()['servicios'] if x['id'] == 'minimax')
        self.assertTrue(service['habilitado'])
        self.assertTrue(service['cuentas'][0]['habilitado'])
        self.assertTrue(service['cuentas'][0]['uso_pago'])
        self.assertEqual(service['cuentas'][0]['capacidades_habilitadas'], [])

    def test_speechify_opcional_se_lista_y_se_puede_activar(self):
        self.assertNotIn('speechify', {x['id'] for x in self.g.lista()['servicios']})
        service = next(x for x in self.g.lista_opcionales()['servicios'] if x['id'] == 'speechify')
        self.assertFalse(service['habilitado'])
        self.g.configurar_opcional({'proveedor': 'speechify', 'habilitado': True})
        service = next(x for x in self.g.lista_opcionales()['servicios'] if x['id'] == 'speechify')
        self.assertTrue(service['habilitado'])

    def test_opcional_rechaza_capacidad_ajena(self):
        data = self.g.cuentas()
        data.setdefault('proveedores', {})['deepseek'] = {'cuentas': [{'id': 'ds1'}]}
        backend.escribir_json(self.root / 'cuentas.json', data)
        with self.assertRaises(backend.ErrorUsuario):
            self.g.configurar_opcional({'proveedor': 'deepseek', 'id': 'ds1',
                                        'capacidad': 'music_generation',
                                        'capacidad_habilitada': True})

    def test_elevenlabs_usa_una_cuenta_con_capacidades_separadas(self):
        data = self.g.cuentas()
        data.setdefault('proveedores', {})['elevenlabs'] = {'cuentas': [
            {'id': 'el1', 'nombre': 'Eleven compartida', 'habilitado': True,
             'capacidades_habilitadas': []}]}
        backend.escribir_json(self.root / 'cuentas.json', data)
        self.g.configurar_opcional({'proveedor': 'elevenlabs', 'id': 'el1',
                                    'capacidad': 'speech_generation',
                                    'capacidad_habilitada': True})
        service = next(x for x in self.g.lista()['servicios'] if x['id'] == 'elevenlabs')
        self.assertEqual(len(service['cuentas']), 1)
        self.assertEqual(service['cuentas'][0]['capacidades_habilitadas'], ['speech_generation'])
        self.assertIn('speech_to_speech', service['capacidades_ids'])
        self.assertIn('music_generation', service['capacidades_ids'])
        self.assertIn('video_generation_image', service['capacidades_ids'])
        with self.assertRaises(backend.ErrorUsuario):
            self.g.configurar_opcional({'proveedor': 'elevenlabs', 'id': 'el1',
                                        'capacidad': 'sound_effects',
                                        'capacidad_habilitada': True})

    def test_correo_se_reutiliza_entre_proveedores_incluido_ollama(self):
        self.g.guardar('groq', CLAVE, email='compartido@ejemplo.com')
        data = self.g.cuentas()
        data['proveedores']['ollama']['cuentas'][0]['email'] = 'compartido@ejemplo.com'
        backend.escribir_json(self.root / 'cuentas.json', data)
        self.assertEqual(
            sum(m == 'compartido@ejemplo.com' for m in self.g.emails_conocidos()),
            1,
        )
        self.assertEqual(
            self.g.buscar('ollama', 'acc1')['email'],
            'compartido@ejemplo.com',
        )

    def test_reautorizar_ollama_conserva_id_puerto_instancia_y_correo(self):
        data = self.g.cuentas()
        row = data['proveedores']['ollama']['cuentas'][0]
        row.update(email='ollama@ejemplo.com', ollama_home='ollama_instances/acc1')
        backend.escribir_json(self.root / 'cuentas.json', data)

        def fake_key(path, email):
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text('PRIVATEA', encoding='utf-8')
            path.with_suffix('.pub').write_text('ssh-ed25519 PUBLICA', encoding='utf-8')
            return True

        with patch('shutil.which', return_value='/usr/bin/ollama'), \
             patch('scripts.agregar_ollama.generate_ssh_key', side_effect=fake_key), \
             patch('scripts.agregar_ollama.start_ollama_instance', return_value=True), \
             patch.object(backend, 'peticion_json', return_value=(200, {})):
            result = self.g.ollama_preparar('ollama@ejemplo.com', 'acc1')

        self.assertTrue(result['reautorizar'])
        pending = backend.leer_json(self.root / 'state' / 'servicios_ollama_pendiente.json')
        self.assertEqual(
            {k: pending[k] for k in ('id', 'puerto', 'ollama_home', 'email')},
            {'id': 'acc1', 'puerto': 11434,
             'ollama_home': 'ollama_instances/acc1',
             'email': 'ollama@ejemplo.com'},
        )

        with patch.object(backend, 'peticion_json', return_value=(200, {'email': 'ollama@ejemplo.com'})):
            final = self.g.ollama_finalizar()
        self.assertEqual(final['id'], 'acc1')
        self.assertEqual(len(self.g.cuentas()['proveedores']['ollama']['cuentas']), 1)

    def test_reautorizar_ollama_rechaza_otro_correo(self):
        data = self.g.cuentas()
        data['proveedores']['ollama']['cuentas'][0]['email'] = 'correcto@ejemplo.com'
        backend.escribir_json(self.root / 'cuentas.json', data)
        with self.assertRaises(backend.ErrorUsuario):
            self.g.ollama_preparar('otro@ejemplo.com', 'acc1')

    def test_reautorizar_reemplaza_un_alta_pendiente_anterior(self):
        data = self.g.cuentas()
        data['proveedores']['ollama']['cuentas'][0].update(
            email='cuenta@ejemplo.com', ollama_home='ollama_instances/acc1')
        backend.escribir_json(self.root / 'cuentas.json', data)
        backend.escribir_json(self.root / 'state' / 'servicios_ollama_pendiente.json', {
            'id': 'acc17', 'email': 'anterior@ejemplo.com', 'puerto': 11446,
            'ollama_home': 'ollama_instances/acc17'})

        def fake_key(path, email):
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text('PRIVATEA', encoding='utf-8')
            path.with_suffix('.pub').write_text('ssh-ed25519 PUBLICA', encoding='utf-8')
            return True

        with patch('shutil.which', return_value='/usr/bin/ollama'), \
             patch('scripts.agregar_ollama.generate_ssh_key', side_effect=fake_key), \
             patch.object(backend, 'peticion_json', return_value=(200, {})):
            result = self.g.ollama_preparar('cuenta@ejemplo.com', 'acc1')

        self.assertTrue(result['reautorizar'])
        self.assertEqual(result['id'], 'acc1')
        pending = backend.leer_json(self.root / 'state' / 'servicios_ollama_pendiente.json')
        self.assertEqual(pending['id'], 'acc1')
        self.assertEqual(pending['puerto'], 11434)


    def test_editar_cuenta_sin_clave_conserva_secreto(self):
        original = self.g.guardar('groq', CLAVE, nombre='Original', email='antes@ejemplo.com')
        # Editar solo el correo y nombre pasando clave vacía
        actualizada = self.g.guardar('groq', clave='', nombre='Nuevo Nombre', account_id=original['id'], email='despues@ejemplo.com')
        self.assertTrue(actualizada['guardada'])
        cuenta = self.g.buscar('groq', original['id'])
        self.assertEqual(cuenta['nombre'], 'Nuevo Nombre')
        self.assertEqual(cuenta['email'], 'despues@ejemplo.com')
        # La clave en .env sigue intacta
        self.assertEqual(self.g.clave_guardada('groq', cuenta), CLAVE)

    def test_evita_correos_duplicados_en_mismo_proveedor(self):
        self.g.guardar('groq', CLAVE, email='repetido@ejemplo.com')
        # Intentar registrar otra cuenta en groq con el mismo correo debe fallar
        with self.assertRaises(backend.ErrorUsuario):
            self.g.guardar('groq', CLAVE + '2', email='repetido@ejemplo.com')
        # Pero en otro proveedor sí se permite
        otra = self.g.guardar('nvidia', CLAVE, email='repetido@ejemplo.com')
        self.assertTrue(otra['guardada'])

    def test_no_inyeccion_env_ni_cuentas_arbitrarias(self):
        for key in ['abc\nOTRA=123456', 'clave$(peligro)', 'clave con espacios', 'clave"comillas']:
            with self.assertRaises(backend.ErrorUsuario):
                self.g.guardar('groq', key, email='cuenta@ejemplo.com')
        with self.assertRaises(backend.ErrorUsuario):
            self.g.guardar('cloudflare', CLAVE, cf_id='../otra-cuenta', email='cuenta@ejemplo.com')
        with self.assertRaises(backend.ErrorUsuario):
            self.g.guardar('groq', CLAVE, account_id='inexistente', email='cuenta@ejemplo.com')
        self.assertNotIn(CLAVE, (self.root / '.env').read_text())

    def test_cuentas_corruptas_no_se_sobrescriben(self):
        (self.root / 'cuentas.json').write_text('INVALIDO')
        old = (self.root / '.env').read_text()
        with self.assertRaises(backend.ErrorUsuario):
            self.g.guardar('groq', CLAVE, email='cuenta@ejemplo.com')
        self.assertEqual((self.root / '.env').read_text(), old)
        self.assertEqual((self.root / 'cuentas.json').read_text(), 'INVALIDO')

    def test_fallo_escritura_cuentas_restaura_env(self):
        old = (self.root / '.env').read_text()
        with patch.object(backend, 'escribir_json', side_effect=OSError('disk full')):
            with self.assertRaises(OSError):
                self.g.guardar('groq', CLAVE, email='cuenta@ejemplo.com')
        self.assertEqual((self.root / '.env').read_text(), old)

    def test_clave_invalida_no_guarda_ni_con_opcion_pendiente(self):
        with patch.object(backend, 'peticion_json', return_value=(401, {})):
            res = self.g.conectar(dict(proveedor='groq', clave=CLAVE, email='cuenta@ejemplo.com', guardar_pendiente=True))
        self.assertFalse(res['guardada'])
        self.assertNotIn(CLAVE, (self.root / '.env').read_text())

    def test_pendiente_requiere_eleccion_explicita(self):
        with patch.object(backend, 'peticion_json', return_value=(0, {})):
            self.assertFalse(self.g.conectar(dict(proveedor='groq', clave=CLAVE, email='cuenta@ejemplo.com'))['guardada'])
            result = self.g.conectar(dict(proveedor='groq', clave=CLAVE, email='cuenta@ejemplo.com', guardar_pendiente=True))
        self.assertTrue(result['guardada'])
        self.assertFalse(result['verificada'])

    def test_catalogo_publico_no_valida_clave(self):
        with patch.object(backend, 'peticion_json', return_value=(200, {'data': []})):
            self.assertFalse(backend.comprobar_clave('nvidia', CLAVE)['verificada'])

    def test_catalogo_protegido_verifica_sin_inferencia(self):
        for p in ['groq','nvidia','google','zhipu','tokenrouter','xkiro','tokenharbor','cloudflare']:
            with patch.object(backend, 'peticion_json', side_effect=[(200, {'data': []}), (401, {})]) as req:
                self.assertTrue(backend.comprobar_clave(p, CLAVE, 'a'*32)['verificada'], p)
                self.assertNotIn('chat/completions', req.call_args_list[0].args[0])

    def test_errores_claros(self):
        for code, estado in [(0,'sin_conexion'),(401,'clave_rechazada'),(403,'sin_permiso'),(402,'sin_saldo'),(429,'limite'),(503,'no_disponible'),(404,'sin_verificar')]:
            with patch.object(backend, 'peticion_json', return_value=(code, {})):
                self.assertEqual(backend.comprobar_clave('groq', CLAVE)['estado'], estado)

    def test_cohere_necesita_valid_true(self):
        with patch.object(backend, 'peticion_json', return_value=(200, {'valid': False})):
            self.assertFalse(backend.comprobar_clave('cohere', CLAVE)['verificada'])
        with patch.object(backend, 'peticion_json', return_value=(200, {'valid': True})):
            self.assertTrue(backend.comprobar_clave('cohere', CLAVE)['verificada'])

    def test_ollama_no_confunde_error_o_cuenta_distinta_con_exito(self):
        for status, data in [(500, {}),(403, {}),(200, {}),(200, {'email': 'otra@ejemplo.com'})]:
            with patch.object(backend, 'peticion_json', return_value=(status, data)):
                self.assertFalse(self.g.comprobar_ollama(11434, 'cuenta@ejemplo.com')['verificada'])
        with patch.object(backend, 'peticion_json', return_value=(200, {'email':'cuenta@ejemplo.com'})):
            self.assertTrue(self.g.comprobar_ollama(11434, 'cuenta@ejemplo.com')['verificada'])

    def test_ollama_local_sin_modelos(self):
        with patch.object(backend, 'peticion_json', return_value=(200, {'models': []})):
            self.assertEqual(self.g.comprobar_ollama(11434, local=True)['estado'], 'sin_modelos')

    def test_oauth_pkce_estado_un_solo_uso(self):
        init = self.g.oauth_iniciar('http://127.0.0.1:19000', 'openrouter@ejemplo.com')
        query = parse_qs(urlsplit(init['url']).query)
        state = query['callback_url'][0].rsplit('/', 1)[1]
        verifier = self.g.oauth[state]['verifier']
        expected = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip('=')
        self.assertEqual(query['code_challenge'][0], expected)
        self.assertEqual(query['code_challenge_method'], ['S256'])
        with patch.object(backend, 'peticion_json', side_effect=[(200, {'key':clave_para('openrouter')}), (200, {'data': {'limit': 0}})]) as req:
            result = self.g.oauth_completar(state, 'code-ficticio')
        self.assertTrue(result['guardada'])
        self.assertNotIn(CLAVE, json.dumps(result))
        self.assertEqual(req.call_args_list[0].kwargs['payload']['code_verifier'], verifier)
        with self.assertRaises(backend.ErrorUsuario):
            self.g.oauth_completar(state, 'code-ficticio')

    def test_oauth_vencido_no_hace_intercambio(self):
        self.g.oauth['vencido'] = dict(created=0, verifier='test')
        with patch.object(backend, 'peticion_json') as req:
            with self.assertRaises(backend.ErrorUsuario):
                self.g.oauth_completar('vencido', 'test')
            req.assert_not_called()

    def test_cloudflare_account_id_limpieza_y_extraccion_url(self):
        cid = '0123456789abcdef0123456789abcdef'
        self.assertEqual(backend.limpiar_cf_id(cid), cid)
        self.assertEqual(backend.limpiar_cf_id(f'https://dash.cloudflare.com/{cid}/workers-and-pages'), cid)
        self.assertEqual(backend.limpiar_cf_id(f'  "{cid.upper()}"  '), cid)
        with patch.object(backend, 'peticion_json', side_effect=[(200, {'result': []}), (401, {})]):
            res = self.g.conectar(dict(
                proveedor='cloudflare',
                clave=CLAVE,
                cf_id=f'https://dash.cloudflare.com/{cid}/workers-and-pages',
                email='cf@ejemplo.com'
            ))
            self.assertTrue(res['guardada'])
        env = (self.root / '.env').read_text()
        self.assertIn(f'CLOUDFLARE_ACCOUNT_ID={cid}', env)
        cuentas = json.loads((self.root / 'cuentas.json').read_text())
        cf_cuentas = cuentas['proveedores']['cloudflare']['cuentas']
        self.assertEqual(cf_cuentas[0]['account_id'], cid)
        self.assertEqual(cf_cuentas[0]['email'], 'cf@ejemplo.com')


class HttpTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.server = Servidor(('127.0.0.1', 0), Path(self.tmp.name))
        self.server.publicar()
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        self.tmp.cleanup()

    def request(self, path, method='GET', body=None, **headers):
        conn = http.client.HTTPConnection('127.0.0.1', self.server.server_port)
        conn.request(method, path, body=body, headers=headers)
        r = conn.getresponse()
        result = r.status, r.read(), dict(r.getheaders())
        conn.close()
        return result

    def test_sin_sesion_no_hay_metadata_ni_archivos_privados(self):
        self.assertEqual(self.request('/api/servicios')[0], 401)
        for path in ['/.env', '/cuentas.json', '/state/mis_servicios_runtime.json', '/../.env']:
            self.assertEqual(self.request(path)[0], 404)

    def test_host_y_origen_ajenos_rechazados(self):
        self.assertEqual(self.request('/', Host='sitio-ajeno.invalid')[0], 403)
        headers = {'X-Nucleo-Session':self.server.token,'Content-Type':'application/json','Origin':'https://sitio-ajeno.invalid'}
        self.assertEqual(self.request('/api/conectar','POST','{}',**headers)[0],403)
        del headers['Origin']
        self.assertEqual(self.request('/api/conectar','POST','{}',**headers)[0],403)

    def test_html_csp_y_lista(self):
        status, body, headers = self.request('/')
        self.assertEqual(status,200)
        self.assertIn('frame-ancestors',headers['Content-Security-Policy'])
        self.assertNotIn(self.server.token.encode(), body)
        status, body, _ = self.request('/api/servicios', **{'X-Nucleo-Session':self.server.token})
        self.assertEqual(status, 200)
        self.assertGreaterEqual(len(json.loads(body)['servicios']),14)

    def test_guardar_via_http_sin_secretos_en_respuesta(self):
        payload=json.dumps(dict(proveedor='groq',clave=CLAVE,email='groq@ejemplo.com'))
        headers={'Origin':self.server.origen,'X-Nucleo-Session':self.server.token,'Content-Type':'application/json'}
        with patch.object(backend,'peticion_json',side_effect=[(200,{'data':[]}),(401,{})]):
            status, body, _ = self.request('/api/conectar','POST',payload,**headers)
        self.assertEqual(status,200)
        self.assertTrue(json.loads(body)['guardada'])
        self.assertNotIn(CLAVE.encode(),body)

    def test_recarga_solo_loopback_y_token_de_esta_copia(self):
        self.assertTrue(autorizar_recarga('127.0.0.1',self.server.token,self.tmp.name))
        self.assertFalse(autorizar_recarga('192.168.1.1',self.server.token,self.tmp.name))
        self.assertFalse(autorizar_recarga('127.0.0.1','incorrecto',self.tmp.name))

    def test_oauth_invalido_no_redirige_ni_entrega_sesion(self):
        status, body, headers=self.request('/oauth/callback/inventado?code=falso')
        self.assertEqual(status,400)
        self.assertNotIn('Location',headers)
        self.assertNotIn(self.server.token.encode(),body)


if __name__ == '__main__':
    unittest.main()
