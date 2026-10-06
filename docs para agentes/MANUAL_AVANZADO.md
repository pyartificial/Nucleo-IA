# Manual avanzado de Núcleo IA

Este manual explica las opciones que no hacen falta para la primera prueba, pero sí para administrar rankings, cuotas, multimedia, copias y una instalación compartida. Cada apartado indica qué cambia, cuándo conviene usarlo y qué puede salir mal.

## Índice

1. [Distribución segura](#distribución-segura)
2. [Configuración y perfiles](#configuración-y-perfiles)
3. [Ranking y evidencia](#ranking-y-evidencia)
4. [Centro de control y actividad](#centro-de-control-y-actividad)
5. [Rotación, cuentas y puestos](#rotación-cuentas-y-puestos)
6. [Capacidades especiales](#capacidades-especiales)
7. [Copia de trabajo, exportable y GitHub](#copia-de-trabajo-exportable-y-github)
8. [Windows en segundo plano](#windows-en-segundo-plano)
9. [Diagnóstico avanzado](#diagnóstico-avanzado)

## Distribución segura

No compartas la carpeta privada directamente. Generá una copia nueva con:

```bash
python scripts/sincronizar_exportable.py --destino "/ruta/copia compartible"
python "/ruta/copia compartible/scripts/validar_exportable.py" "/ruta/copia compartible"
```

El sincronizador copia únicamente las carpetas y archivos permitidos, genera plantillas limpias y reconstruye los rankings públicos sin `probe caches`, sesiones, registros ni datos personales. La validación revisa estructura, JSON, Python, manuales y patrones de secretos. Si la validación falla, no publiques la copia.

El respaldo personal se hace con `python granja.py backup CARPETA_VACIA`. Ese respaldo sí contiene tus cuentas y configuración: debe permanecer privado y nunca debe mezclarse con una carpeta pública.

## Configuración y perfiles

`.env` es la configuración principal; `granja.env` se mantiene por compatibilidad. Las variables del sistema tienen prioridad. Detené el servidor antes de editar y reinicialo después para asegurarte de que todos los procesos hayan leído los nuevos valores.

Para uso personal dejá `PROXY_HOST=127.0.0.1`, `AUTH_ENABLED=false`, `PERFIL_USO=personal` y `PERMITIR_OLLAMA_REMOTO=false`. Para modo Profesional, activá autenticación, usá claves separadas de consumo y administración, restringí hosts y orígenes y protegé el acceso con HTTPS cuando atraviese la red.

`PROCESAMIENTO_PERMITIDO=solo_local` bloquea envíos cloud; requiere modelos locales capaces de cada tarea. `SOLO_MODELOS_GRATUITOS=true` filtra las rutas que no tienen evidencia de gratuidad, pero no garantiza que el proveedor mantenga su cuota. `NUCLEO_HABILITAR_MODELOS_IMAGEN_NO_GRATUITOS`, `NUCLEO_HABILITAR_MODELOS_VOZ_NO_GRATUITOS` y `NUCLEO_HABILITAR_MODELOS_VIDEO_NO_GRATUITOS` permanecen en `false` salvo que conozcas el costo y el límite de tu cuenta.

## Ranking y evidencia

`python granja.py rank` ejecuta una actualización integral desde terminal. El Centro de control ofrece la misma tarea desde **Rankings**. El ranking distingue la ruta exacta (`proveedor + identificador`) de la identidad base del modelo, así que una misma familia en dos proveedores mantiene salud, cuota y failover independientes.

La admisión combina catálogo, autenticación, prueba de respuesta, contexto, instrucciones, herramientas, razonamiento y capacidades multimodales. Las señales externas son orientación; una puntuación alta no demuestra que tu cuenta tenga cuota hoy. Las rutas con evidencia insuficiente quedan fuera de una capacidad automática o se muestran como secundarias.

## Centro de control y actividad

Abrí `centro_control.bat`, `centro_control.vbs`, `bash centro_control.sh` o el acceso gráfico. **Resumen** muestra estado del servidor, cuentas utilizables, capacidades y el último modelo que respondió. **Servicios y cuentas** lleva al asistente de conexión. **Rankings** administra el orden.

En Rankings:

- **General** muestra los modelos para agentes y la configuración de rotación.
- **Por servicio** muestra una subpestaña por proveedor, con los modelos que ese proveedor publicó o respondió.
- **Capacidades especiales** separa visión, imágenes, voz, transcripción, video, embeddings y otras tareas.

Cada bloque incluye nombre, proveedor, tamaño, contexto, estado, capacidades, última prueba, cuentas compatibles y cuenta preferida. “Automática: N cuentas disponibles” significa que se probarán esas cuentas con las reglas de rotación. Elegir un correo como cuenta preferida solo cambia el primer intento de ese modelo; no elimina las demás.

**Volver a probar este servicio** ejecuta un comprobador individual. **Actualizar todos** ejecuta los comprobadores de los proveedores y luego calcula el ranking global. El panel de actividad muestra etapa, servicio, modelo, tiempo, último evento, avance por etapas y errores. El ranking anterior permanece visible mientras se trabaja.

Si pasan aproximadamente 90 segundos sin eventos, el panel avisa **Sin avances recientes**. A los dos minutos el sistema detiene de manera preventiva el trabajo que perdió su latido. El botón **Detener pruebas** termina el proceso actual. Un error conserva el ranking anterior y permite corregir la cuenta y repetir.

## Rotación, cuentas y puestos

Un puesto es una fila del ranking; un modelo puede tener varias cuentas. En **General** hay tres modos:

1. **Usar siempre el mejor puesto disponible:** empieza en el puesto 1, prueba su cuenta preferida y luego sus otras cuentas; baja al puesto siguiente cuando ninguna responde.
2. **Alternar las cuentas del mejor puesto:** mantiene el puesto 1 y reparte solicitudes entre sus cuentas disponibles.
3. **Alternar puestos y cuentas:** reparte solicitudes entre los primeros puestos y sus cuentas. `top_n=3` usa tres puestos; `top_n=0` usa todos.

La casilla **Conservar mi orden al actualizar** mantiene los movimientos manuales si la prueba termina correctamente. Desmarcarla permite que el resultado automático reemplace el orden de la vista. Los rankings de capacidades tienen su propio orden manual y no activan la rotación general.

## Capacidades especiales

Visión interpreta una imagen existente. Generación de imágenes crea una nueva. Transcripción convierte audio en texto. TTS convierte texto en audio. Video crea una secuencia. Embeddings producen vectores para búsquedas por significado. Cada operación necesita un adaptador, un modelo, una cuenta y cuota adecuados.

Edge TTS (`provider=edge_tts`) está disponible para voz y necesita Internet; SiliconFlow, Groq, Speechify y ElevenLabs ofrecen rutas TTS sujetas a credenciales y cuota. ElevenLabs requiere la capacidad `speech_generation` habilitada en la cuenta. SiliconFlow, Zhipu y Cloudflare Workers AI tienen rutas implementadas para generación de imágenes; Zhipu y SiliconFlow para video. Cohere y SiliconFlow ofrecen embeddings; Groq, transcripción Whisper. Música responde solo con un simulador sin audio. Verifica cada capacidad en `/v1/capabilities` y no infieras soporte operativo a partir del catálogo.

Antes de hacer una llamada, consultá `/v1/capabilities`. Si una función aparece deshabilitada, no la fuerces con un nombre de modelo: conectá el proveedor necesario o usá otra capacidad. Una clave válida para chat no demuestra que el mismo proveedor permita video, imagen o voz.

## Copia de trabajo, exportable y GitHub

La carpeta de trabajo puede contener `.env`, `granja.env`, `cuentas.json`, `state/`, instancias Ollama y herramientas de desarrollo. Es privada.

La carpeta `nucleo ia EXPORTABLE` se comparte con otra persona. Tiene plantillas sin claves, cuentas vacías y rankings públicos preparados. No contiene informes internos, inventarios locales, matrices de cuotas, herramientas de pruebas antiguas ni respaldos.

La carpeta `nucleo ia GITHUB` es una copia pública preparada para control de versiones. Mantiene código, manuales, licencia, seguridad, pruebas públicas y lanzadores, pero no credenciales, correos, estados privados, registros ni herramientas de desarrollo retiradas. Antes de subirla, ejecutá el validador y revisá `git status` y la lista de archivos ignorados.

No subas un respaldo personal. No fuerces `git add` sobre `.env`, `cuentas.json` o `state/`. Si una clave apareció en Git alguna vez, revocala en el proveedor y eliminá el historial correspondiente; borrar el archivo actual no revoca una clave ya publicada.

## Windows en segundo plano

`iniciar_segundo_plano.vbs` usa `venv\Scripts\pythonw.exe` e inicia el proxy sin consola. `instalar_inicio_automatico.bat` lo registra en el inicio del usuario actual bajo HKCU; no es un servicio global del equipo. `detener_todo.bat` detiene la instancia administrada.

## Diagnóstico avanzado

Comprobá en orden `/healthz`, `/readyz`, `/status`, `/v1/models` y `/v1/capabilities`. Un 401 corresponde a la clave de acceso de Núcleo IA; un 402 suele ser crédito del proveedor; 403 es permiso o política; 404 es ruta o modelo; 413 es tamaño; 429 es límite; 5xx es un fallo temporal o upstream.

Si el panel de rankings muestra una prueba vieja como ejecutándose, esperá la detección de falta de latido o reiniciá Núcleo IA. No borres manualmente el ranking anterior mientras un proceso pueda seguir escribiéndolo. Si un servicio termina con errores, repará solo la cuenta que aparece en Mis servicios y repetí la prueba individual.

Si una aplicación en Docker no llega a `127.0.0.1`, recordá que localhost pertenece al contenedor. Usá `host.docker.internal` o una dirección de host restringida, activá autenticación y aplicá firewall. No uses `PROXY_HOST=0.0.0.0` en una red sin controles.

Para un diagnóstico reproducible anotá fecha, servicio, modelo, etapa, código de respuesta y último evento. Nunca adjuntes API keys, `cuentas.json`, `.env`, sesiones ni registros completos sin revisarlos.
