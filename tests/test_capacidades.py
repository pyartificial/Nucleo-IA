import unittest

from proxy.capacidades import candidato_permitido, capacidad_video_para_body, proveedor_con_adaptador
from scripts.catalogo_capacidades import canonica, orden_guardado


class CapacidadesTests(unittest.TestCase):
    def test_catalogo_descubierto_no_implica_adaptador_upstream(self):
        self.assertTrue(proveedor_con_adaptador('image_generation', 'cloudflare'))
        self.assertTrue(proveedor_con_adaptador('video_generation_text', 'zhipu'))
        self.assertFalse(proveedor_con_adaptador('image_generation', 'agnes'))
        self.assertFalse(proveedor_con_adaptador('video_generation_image', 'tokenrouter'))

    def test_video_desde_texto_e_imagen_tienen_rutas_distintas(self):
        self.assertEqual(capacidad_video_para_body({'prompt': 'un bosque'}), 'video_generation_text')
        self.assertEqual(capacidad_video_para_body({'prompt': 'animar', 'image_url': 'data:image/png;base64,AA'}),
                         'video_generation_image')

    def test_cuenta_paga_requiere_tres_permisos(self):
        cuenta = {'habilitado': True, 'uso_pago': True,
                  'capacidades_habilitadas': ['video_generation_image']}
        self.assertTrue(candidato_permitido(cuenta, 'video_generation_image', pago=True))
        self.assertFalse(candidato_permitido(cuenta, 'video_generation_text', pago=True))
        cuenta['uso_pago'] = False
        self.assertFalse(candidato_permitido(cuenta, 'video_generation_image', pago=True))

    def test_nombres_antiguos_siguen_leyendo_el_orden_guardado(self):
        self.assertEqual(canonica('video'), 'video_generation_text')
        self.assertEqual(orden_guardado({'capacidad:video': ['p::m']}, 'video_generation_text'), ['p::m'])


if __name__ == '__main__':
    unittest.main()
