#!/usr/bin/env python3
"""Crea un acceso nativo a Mis servicios para el usuario que ejecuta el instalador."""
from pathlib import Path
import os
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def desktop_text(root, centro=False):
    def quote(value):
        value = str(value).replace('\\', '\\\\').replace('"', '\\"').replace('`', '\\`').replace('$', '\\$').replace('%', '%%')
        return '"' + value + '"'
    nombre = 'Centro de control — Núcleo IA' if centro else 'Mis servicios — Núcleo IA'
    comentario = 'Administrá servicios, cuentas y seguridad' if centro else 'Conectá tus cuentas paso a paso'
    lanzador = 'centro_control.sh' if centro else 'mis_servicios.sh'
    return ('[Desktop Entry]\nType=Application\nName=' + nombre + '\n'
            'Comment=' + comentario + '\n'
            'Exec=bash ' + quote(Path(root) / lanzador) + '\n'
            'Icon=preferences-system\nTerminal=false\nCategories=Utility;\nStartupNotify=false\n')


def main():
    if sys.platform == 'win32':
        env = os.environ.copy()
        env['NUCLEO_SERVICIOS_TARGET'] = str(ROOT / 'mis_servicios.vbs')
        # El acceso queda en el escritorio real, incluso si Windows lo redirigió a OneDrive.
        script = "$s=New-Object -ComObject WScript.Shell; $p=Join-Path ([Environment]::GetFolderPath('Desktop')) 'Mis servicios - Nucleo IA.lnk'; $l=$s.CreateShortcut($p); $l.TargetPath=$env:NUCLEO_SERVICIOS_TARGET; $l.WorkingDirectory=Split-Path $env:NUCLEO_SERVICIOS_TARGET; $l.Save()"
        subprocess.run(['powershell', '-NoProfile', '-Command', script], env=env, check=True)
        env['NUCLEO_CENTRO_TARGET'] = str(ROOT / 'centro_control.vbs')
        script_centro = "$s=New-Object -ComObject WScript.Shell; $p=Join-Path ([Environment]::GetFolderPath('Desktop')) 'Centro de control - Nucleo IA.lnk'; $l=$s.CreateShortcut($p); $l.TargetPath=$env:NUCLEO_CENTRO_TARGET; $l.WorkingDirectory=Split-Path $env:NUCLEO_CENTRO_TARGET; $l.Save()"
        subprocess.run(['powershell', '-NoProfile', '-Command', script_centro], env=env, check=True)
    else:
        local = ROOT / 'mis_servicios.desktop'
        local.write_text(desktop_text(ROOT), encoding='utf-8')
        local.chmod(0o755)
        centro_local = ROOT / 'centro_control.desktop'
        centro_local.write_text(desktop_text(ROOT, centro=True), encoding='utf-8')
        centro_local.chmod(0o755)
        if '--solo-carpeta' not in sys.argv:
            target = Path(os.environ.get('XDG_DATA_HOME', str(Path.home() / '.local/share'))) / 'applications' / 'nucleo-ia-servicios.desktop'
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(desktop_text(ROOT), encoding='utf-8')
            target.chmod(0o755)
            centro_target = target.with_name('nucleo-ia-centro-control.desktop')
            centro_target.write_text(desktop_text(ROOT, centro=True), encoding='utf-8')
            centro_target.chmod(0o755)
    print('Accesos a Mis servicios y Centro de control preparados.')


if __name__ == '__main__':
    main()
