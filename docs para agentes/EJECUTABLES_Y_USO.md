# Ejecutables y forma de uso

Esta es la referencia de los iniciadores incluidos con Núcleo IA. En Windows se ejecutan con doble clic; en Linux se usa `bash nombre.sh`. Los archivos dentro de `scripts/` son opciones avanzadas y normalmente se accede a ellos mediante `granja.py` o los iniciadores de la raíz.

## Flujo recomendado en Windows

1. `instalar_nucleo_ia.bat`: instala Python si hace falta, crea `venv` e instala dependencias. Se ejecuta una vez.
2. `agregar_cuentas.bat`: abre el asistente para registrar claves y cuentas. Se repite cuando se agrega un proveedor.
3. `iniciar_todo.bat`: inicia Núcleo IA mostrando la consola. Es la opción recomendada para la primera prueba.
4. `iniciar_segundo_plano.vbs`: inicia Núcleo IA oculto, sin consola. Requiere que el instalador haya creado `venv`.
5. `instalar_inicio_automatico.bat`: registra el VBS anterior en el inicio de sesión del usuario actual. No requiere permisos de administrador.

## Iniciadores de la raíz

| Archivo | Para qué sirve | Cómo se usa |
|---|---|---|
| `instalar_nucleo_ia.bat` | Instalación completa en Windows. | Doble clic; aceptar la instalación de Python y dependencias si se solicita. |
| `instalar_nucleo_ia.sh` | Instalación completa en Linux/WSL. | `bash instalar_nucleo_ia.sh` |
| `iniciar_todo.bat` | Inicio visible en Windows, útil para diagnóstico. | Doble clic; dejar la ventana abierta. |
| `iniciar_todo.sh` | Inicio desacoplado en Linux/WSL. | `bash iniciar_todo.sh` |
| `iniciar_segundo_plano.vbs` | Inicio oculto recomendado en Windows. | Doble clic después de instalar. Registra eventos en `state/inicio_windows.log`. |
| `detener_todo.bat` | Detiene el proxy en Windows. | Doble clic. |
| `detener_todo.sh` | Detiene el proxy en Linux/WSL. | `bash detener_todo.sh` |
| `instalar_inicio_automatico.bat` | Inicia el servidor automáticamente al iniciar sesión en Windows. | Ejecutar una vez después de la instalación. |
| `desinstalar_inicio_automatico.bat` | Elimina el inicio automático de Windows. | Doble clic. No desinstala Núcleo IA. |
| `instalar_inicio_automatico.sh` | Crea el autostart del usuario en Linux gráfico. | `bash instalar_inicio_automatico.sh` |
| `desinstalar_inicio_automatico.sh` | Elimina el autostart de Linux. | `bash desinstalar_inicio_automatico.sh` |
| `agregar_cuentas.bat` | Asistente general de cuentas en Windows. | Doble clic y elegir proveedor. |
| `agregar_cuentas.sh` | Asistente general de cuentas en Linux/WSL. | `bash agregar_cuentas.sh` |
| `centro_control.vbs` | Abre el Centro de control en Windows sin mostrar una consola. | Doble clic después de instalar. |
| `centro_control.bat` | Abre el Centro de control en Windows y permite ver errores de inicio. | Doble clic para diagnóstico. |
| `centro_control.sh` | Abre el Centro de control general en Linux/WSL. | `bash centro_control.sh` |
| `centro_control.desktop` | Acceso gráfico Linux al Centro de control, generado al ejecutar el instalador. | Abrir desde la carpeta del proyecto o desde el menú de aplicaciones. |
| `configura_nucleoia.bat` | Configura proveedores y rotación en Windows. | Doble clic. |
| `configura_nucleoia.sh` | Configura proveedores y rotación en Linux. | `bash configura_nucleoia.sh` |
| `actualizar_rankings.bat` | Descubre, prueba y ordena modelos. | Doble clic; requiere Internet y puede tardar. |
| `actualizar_rankings.sh` | Equivalente Linux del actualizador. | `bash actualizar_rankings.sh` |
| `actualizar_rankings.desktop` | Acceso gráfico local de Linux al actualizador. | Abrir desde el escritorio del equipo donde fue creado; no se exporta porque su ruta es local. |
| `ajustar_ranking_manual.bat` | Cambia manualmente el orden global. | Doble clic y elegir posiciones. |
| `ajustar_ranking_manual.sh` | Editor manual en Linux. | `bash ajustar_ranking_manual.sh` |
| `ajustar_ranking_manual.desktop` | Acceso gráfico Linux al editor. | Doble clic desde un escritorio compatible. |
| `probar_demo.bat` | Abre la interfaz web de demostración. | Iniciar primero el servidor y luego hacer doble clic. |
| `probar_demo.sh` | Inicia/abre la demostración en Linux. | `bash probar_demo.sh` |
| `reparar_ollama.bat` | Revincula una cuenta Ollama concreta sin borrar las demás. | Doble clic y seleccionar la cuenta. |
| `reparar_ollama.sh` | Equivalente Linux de reparación de Ollama. | `bash reparar_ollama.sh` |

## Gestor multiplataforma

`granja.py` ofrece los mismos flujos desde consola: `install`, `start`, `stop`, `restart`, `status`, `models`, `rank`, `test`, `config`, `add-key`, `add-ollama`, `adjust-ranking` y `sync-exportable`.

Ejemplo: `python granja.py status` comprueba el servidor; `python granja.py rank` ejecuta una sola actualización integral del ranking.

## Scripts avanzados

Estos archivos normalmente no se abren directamente: los llaman los iniciadores de la raíz. Se conservan para diagnóstico y automatización.

| Archivo | Para qué sirve y cómo se usa |
|---|---|
| `scripts/agregar_cuentas.sh` | Menú general Linux para elegir y agregar un proveedor; `bash scripts/agregar_cuentas.sh`. |
| `scripts/agregar_cloudflare.bat` / `scripts/agregar_cloudflare.sh` | Carga Account ID y token de Cloudflare; doble clic o `bash scripts/agregar_cloudflare.sh`. |
| `scripts/agregar_cohere.bat` / `scripts/agregar_cohere.sh` | Carga una clave de Cohere; doble clic o `bash scripts/agregar_cohere.sh`. |
| `scripts/agregar_google.sh` | Carga una clave de Google en Linux; `bash scripts/agregar_google.sh`. |
| `scripts/agregar_groq.bat` / `scripts/agregar_groq.sh` | Carga una clave de Groq; doble clic o `bash scripts/agregar_groq.sh`. |
| `scripts/agregar_nvidia.sh` | Carga una clave de NVIDIA en Linux; `bash scripts/agregar_nvidia.sh`. |
| `scripts/agregar_ollama.bat` / `scripts/agregar_ollama.sh` | Vincula cuentas/modelos Ollama; doble clic o `bash scripts/agregar_ollama.sh`. |
| `scripts/agregar_openrouter.sh` | Carga una clave de OpenRouter en Linux; `bash scripts/agregar_openrouter.sh`. |
| `scripts/agregar_siliconflow.bat` / `scripts/agregar_siliconflow.sh` | Carga SiliconFlow para chat y multimedia; doble clic o `bash scripts/agregar_siliconflow.sh`. |
| `scripts/agregar_tokenrouter.bat` / `scripts/agregar_tokenrouter.sh` | Carga TokenRouter; doble clic o `bash scripts/agregar_tokenrouter.sh`. |
| `scripts/agregar_xkiro.bat` / `scripts/agregar_xkiro.sh` | Carga xKiro; doble clic o `bash scripts/agregar_xkiro.sh`. |
| `scripts/agregar_tokenharbor.bat` / `scripts/agregar_tokenharbor.sh` | Carga Token Harbor y avisa sobre la retención de las rutas free; doble clic o `bash scripts/agregar_tokenharbor.sh`. |
| `scripts/agregar_zhipu.bat` / `scripts/agregar_zhipu.sh` | Carga Zhipu/Z.AI; doble clic o `bash scripts/agregar_zhipu.sh`. |
| `scripts/agregar_key_google.bat` / `scripts/agregar_key_google.sh` | Alias heredado del asistente de Google; usar solo por compatibilidad. |
| `scripts/agregar_key_nvidia.bat` / `scripts/agregar_key_nvidia.sh` | Alias heredado del asistente de NVIDIA; usar solo por compatibilidad. |
| `scripts/agregar_key_openrouter.bat` / `scripts/agregar_key_openrouter.sh` | Alias heredado del asistente de OpenRouter; usar solo por compatibilidad. |
| `scripts/detener_granja.bat` | Detención interna en Windows; lo invoca `detener_todo.bat`. |
| `scripts/healthcheck.sh` | Prueba rápida del proxy y una consulta; `bash scripts/healthcheck.sh`. |
| `scripts/iniciar_granja.sh` | Inicia las instancias locales Ollama configuradas; uso interno del arranque Linux. |
| `scripts/login_cuentas.sh` | Vinculación avanzada de cuentas Ollama; `bash scripts/login_cuentas.sh`. |
| `scripts/instalar_dependencias.sh` | Instala dependencias del sistema en Linux; lo invoca el instalador principal. |
| `ollama-farm-kit/scripts/start-farm.sh` | Inicia únicamente la granja Ollama local; `bash ollama-farm-kit/scripts/start-farm.sh`. |
| `ollama-farm-kit/scripts/stop-farm.sh` | Detiene únicamente los procesos de la granja Ollama local; `bash ollama-farm-kit/scripts/stop-farm.sh`. |
| `ollama-farm-kit/scripts/healthcheck.sh` | Comprueba únicamente la granja Ollama; `bash ollama-farm-kit/scripts/healthcheck.sh`. |

## Comprobación del inicio automático

Después de ejecutar `instalar_inicio_automatico.bat`, cerrar sesión y volver a entrar, esperar unos segundos y abrir `http://127.0.0.1:8080/status`. Si no responde, revisar `state/inicio_windows.log` y confirmar que existe `venv\Scripts\pythonw.exe`.

## Mis servicios: conectar cuentas sin consola

- `mis_servicios.vbs`: acceso recomendado en Windows, sin ventana de consola.
- `mis_servicios.bat`: alternativa para Windows y diagnóstico del inicio.
- `mis_servicios.sh`: lanzador Linux; abre el navegador predeterminado con escritorio y el menú de terminal en servidores sin entorno gráfico.
- `mis_servicios.desktop`: acceso gráfico Linux. El instalador lo prepara para la carpeta actual y agrega “Mis servicios — Núcleo IA” al menú de aplicaciones.
- `agregar_cuentas.bat`: abre el asistente visual en Windows. `agregar_cuentas.sh`: usa la detección de escritorio de `mis_servicios.sh`, con opción `--terminal`.
- `scripts/instalar_acceso_servicios.py`: prepara el acceso nativo del sistema. Se ejecuta desde los instaladores.
- `python granja.py services`: entrada opcional para uso desde una terminal; `add-key` y `add-ollama` conservan sus recorridos anteriores.

Si movés la carpeta, ejecutá de nuevo el instalador para actualizar el acceso del menú o del escritorio. El lanzador `.sh`, `.bat` o `.vbs` dentro de la carpeta sigue usando su ubicación actual. Algunos escritorios Linux piden marcar el archivo `.desktop` como confiable; el acceso del menú evita depender de esa opción.

El asistente abre un servidor exclusivo en `127.0.0.1`, recuerda el paso sin guardar claves en el navegador y permite comprobar las cuentas existentes. “Aplicar conexiones” inicia el proxy si está detenido o recarga las cuentas en una versión compatible. Si ya estaba ejecutándose una versión anterior, el asistente indica que hay que cerrarla con `detener_todo.sh` / `detener_todo.bat` y volver a aplicar; no termina procesos ajenos.

Guía: `docs para agentes/MIS_SERVICIOS.md`.
