#!/usr/bin/env python3
"""Menú de cuentas para servidores sin escritorio. No abre un navegador local."""
from pathlib import Path
import getpass
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from scripts.catalogo_servicios import SERVICIOS
from scripts.servicios_backend import GestorServicios, ErrorUsuario


def main():
    if not sys.stdin.isatty():
        print('Para cargar cuentas, abrí una terminal interactiva y ejecutá bash agregar_cuentas.sh. Si usás SSH, conectate con ssh -t.')
        return 2
    gestor = GestorServicios(ROOT)
    try:
        while True:
            print('\nMIS SERVICIOS — MODO TERMINAL\n')
            print('Los enlaces se pueden abrir en el navegador de otra computadora.')
            for i, servicio in enumerate(SERVICIOS, 1):
                alcance = ' [SOLO TTS]' if servicio.get('solo_tts') else ''
                print(f"  {i:2}) {servicio['nombre']}{alcance}")
            print('   0) Salir')
            opcion = input('\nElegí un servicio: ').strip()
            if opcion == '0':
                return 0
            if not opcion.isdigit() or not 1 <= int(opcion) <= len(SERVICIOS):
                print('Elegí uno de los números de la lista.')
                continue
            servicio = SERVICIOS[int(opcion) - 1]
            try:
                if servicio['id'] == 'ollama':
                    from scripts.agregar_ollama import main as agregar_ollama
                    conocidos = gestor.emails_conocidos()
                    if conocidos:
                        print('\nPozo de correos (se pueden reutilizar entre servicios):')
                        for n, correo in enumerate(conocidos, 1):
                            print(f'  {n}) {correo}')
                        eleccion = input('Elegí un número o escribí otro correo [Enter=escribir luego]: ').strip()
                        email_inicial = conocidos[int(eleccion) - 1] if eleccion.isdigit() and 1 <= int(eleccion) <= len(conocidos) else eleccion
                    else:
                        email_inicial = ''
                    agregar_ollama(abrir_navegador=False, email_inicial=email_inicial)
                    continue
                print(f"\nAbrí esta página en tu otra computadora:\n{servicio['claves']}\n")
                print('Cuentas ya registradas de este servicio:')
                existentes = gestor.lista()['servicios'][int(opcion) - 1]['cuentas']
                if existentes:
                    for cuenta in existentes:
                        print(f"  - {cuenta.get('nombre')}: {cuenta.get('email') or 'correo no registrado'}")
                else:
                    print('  - ninguna todavía')
                for paso in servicio['pasos']:
                    print('• ' + paso)
                if servicio.get('nota'):
                    print(servicio['nota'])
                print('Revisá el plan y los precios antes de conectar. La clave no es tu contraseña.')
                email = input('\nCorreo asociado a esta cuenta: ').strip()
                nombre = input('Nombre para reconocer esta cuenta (opcional): ').strip()
                cf_id = input('Account ID de Cloudflare: ').strip() if servicio['id'] == 'cloudflare' else ''
                voice_id = input('ID de voz de ElevenLabs (opcional): ').strip() if servicio['id'] == 'elevenlabs' else ''
                clave = getpass.getpass('Pegá la clave (no se muestra; Enter para cancelar): ').strip()
                if not clave:
                    continue
                body = dict(proveedor=servicio['id'], nombre=nombre, email=email, cf_id=cf_id, voice_id=voice_id, clave=clave)
                print('Comprobando acceso…')
                resultado = gestor.conectar(body)
                print(resultado['mensaje'])
                if not resultado['guardada'] and resultado['estado'] not in {'clave_rechazada', 'sin_permiso'}:
                    if input('¿Guardar como pendiente? [s/N]: ').strip().lower() in {'s', 'si', 'sí'}:
                        check = {k: resultado[k] for k in ('estado', 'mensaje', 'verificada')}
                        resultado = gestor.guardar(servicio['id'], clave, nombre, cf_id, check=check, email=email, voice_id=voice_id)
                if resultado.get('guardada'):
                    print('Cuenta guardada. Iniciá o reiniciá Núcleo IA para cargar la nueva configuración.')
                del clave, body
            except ErrorUsuario as exc:
                print(str(exc))
            except OSError:
                print('No se pudo completar la operación. Revisá permisos y espacio en la carpeta.')
    except (EOFError, KeyboardInterrupt):
        print('\nOperación cancelada.')
        return 0


if __name__ == '__main__':
    raise SystemExit(main())
