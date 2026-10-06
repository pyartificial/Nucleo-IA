# Manual para empezar

Núcleo IA es un servidor local compatible con la API de OpenAI. Conecta tu aplicación a `http://127.0.0.1:8080/v1` y el proxy elegirá una cuenta disponible. El catálogo inicial tiene 22 fichas en **Servicios generales** y 19 en **Proveedores opcionales**, entre ellas Speechify, que ofrece una conexión dedicada solo a texto a voz (TTS). Si un proveedor opcional tiene dos o más cuentas habilitadas, su tarjeta aparece en Servicios generales, excepto GitHub. Estos grupos ordenan la pantalla: no garantizan que cada modelo sea gratis o que cada capacidad esté implementada. Cada servicio conserva sus modelos y su ranking; el ranking general reúne candidatos válidos.

## Índice

1. Qué vas a hacer
2. Instalación mínima
3. Probar un agente
4. Pozo de correos y Ollama
5. Respaldo y traslado
6. Modo Profesional
7. Si falla
8. Palabras importantes explicadas

## Qué vas a hacer

Núcleo IA organiza la comunicación entre tu agente y los servicios de inteligencia artificial. Un proveedor ofrece modelos; una cuenta es tu autorización en ese servicio; un agente es una aplicación que conversa, razona y puede usar herramientas. No necesitás saber programación para empezar.

## Instalación mínima

- Windows: ejecuta `instalar_nucleo_ia.bat` y después `iniciar_todo.bat` para la primera comprobación.
- Linux/WSL: ejecuta `bash instalar_nucleo_ia.sh` y después `bash iniciar_todo.sh`.

Copiá `.env.example` a `.env` y abrí **Mis servicios** para vincular cuentas. En modo personal, el panel local funciona sin pedir otra contraseña. El cliente usa `http://127.0.0.1:8080/v1` con el modelo `auto`.

## Probar un agente

1. Instalá e iniciá Núcleo IA.
2. Abrí **Mis servicios** y vinculá una cuenta.
3. En tu agente buscá **OpenAI compatible**, **Custom API** o **Proveedor personalizado**.
4. Dirección base: `http://127.0.0.1:8080/v1`. Clave: `local`. Modelo: `auto`.
5. Probá con: “explicame qué podés hacer”.

Para agentes que usan herramientas elegí `tools`. Una herramienta es una acción solicitada por el agente, como leer un archivo o llamar una función; la aplicación decide si la permite.

## Capacidades multimedia: qué hace cada una

La opción `vision` solo permite **recibir una imagen y describirla o analizarla** dentro de un chat. No genera imágenes.

| Capacidad | Acción | Ruta | Proveedor configurado |
|---|---|---|---|
| Visión | Analizar una imagen enviada en un mensaje | `/v1/chat/completions` | Ollama, Cloudflare, NVIDIA, OpenRouter, Google, Groq, Cohere, SiliconFlow, Zhipu, TokenRouter, xKiro y Token Harbor, cuando tengan un modelo visual apto |
| Generación de imágenes | Crear una imagen a partir de texto | `/v1/images/generations` | SiliconFlow, Zhipu y Cloudflare (si hay acceso y cuota) |
| Texto a voz (TTS) | Convertir texto en audio hablado | `/v1/audio/speech` | Edge TTS, SiliconFlow, Groq, Speechify y ElevenLabs (con autorización) |
| Transcripción | Convertir MP3, WAV u OGG en texto | `/v1/audio/transcriptions` | Groq, Whisper |
| Embeddings | Convertir texto en vectores para búsqueda semántica | `/v1/embeddings` | SiliconFlow y Cohere (según modelo y acceso) |
| Generación de video | Solicitar un video corto desde un prompt | `/v1/videos/generations` | Zhipu AI y SiliconFlow, según cuenta y cuota |

Para saber cuáles están disponibles en tu instalación, abrí `http://127.0.0.1:8080/v1/capabilities`. Cada función depende de su proveedor, de una cuenta válida y, a veces, de un permiso habilitado por separado. Tener visión no habilita automáticamente imágenes, voz o video. Las rutas de audio, imágenes y video pueden tardar más y consumir una cuota distinta del chat. Una etiqueta de servicio gratuito no significa que todos sus modelos sean gratis: revisá el precio de la ruta antes de usarla.

## Pozo de correos y Ollama

Mis servicios mantiene un pozo común de correos. Podés agregar correos antes de vincular un proveedor y reutilizarlos en Groq, Google, Ollama u otros servicios. En Ollama cada cuenta queda identificada por su correo. Si una falla, elegí **Volver a autorizar esta cuenta**: se conserva su ID, puerto e instancia y no se recargan las demás.

## Respaldo y traslado

La copia exportable pública no contiene tus credenciales. Para trasladar tus datos personales usá:

```bash
python granja.py backup CARPETA_VACIA
python granja.py restore CARPETA_DEL_RESPALDO
```

El respaldo conserva cuentas, correos y configuración, pero no copia sesiones temporales ni procesos en ejecución. Después de restaurar, reiniciá Núcleo IA y reautorizá solo la cuenta cuyo permiso haya vencido.

También podés pasar cuentas a otra computadora desde **Centro de control → Trasladar cuentas**. En la computadora que ya tiene las cuentas, creá el paquete. Pasalo en privado a la otra computadora, abrí la misma pestaña allí, seleccioná el paquete y tocá **Agregar estas cuentas**. Esta opción suma las cuentas nuevas; conserva las que ya existen en la computadora de destino. El paquete contiene claves API sin cifrar: no lo compartas por correo o chat y borrá las copias al terminar.

## Modo Profesional

Cuando varias personas comparten una instalación, el asistente permite elegir **modo Profesional**. Usa una clave para consumo y otra para administración. Los consumidores pueden usar el proxy sin ver correos ni credenciales; la persona administradora puede revisar el estado y reparar una cuenta concreta. Los valores antiguos del perfil siguen aceptándose por compatibilidad.

## Segundo plano e inicio con Windows

- `iniciar_segundo_plano.vbs`: inicia el servidor oculto después de instalarlo.
- `instalar_inicio_automatico.bat`: registra ese iniciador para el usuario actual. Se ejecutará al iniciar sesión, sin ventana de consola.
- `desinstalar_inicio_automatico.bat`: quita solamente el arranque automático.

Para comprobarlo, espera unos segundos y abre `http://127.0.0.1:8080/status`. Los errores de arranque se guardan en `state/inicio_windows.log`.

## Centro de control y progreso de rankings

Abrí `centro_control.bat` (Windows) o `bash centro_control.sh` (Linux). Entrá en **Rankings** para ver tres vistas: **General**, **Por servicio** y **Capacidades especiales**. En cada bloque podés ver el modelo, el proveedor, sus capacidades, la última prueba y cuántas cuentas pueden responder. **Automática: N cuentas disponibles** deja que Núcleo IA elija las cuentas; **Cuenta preferida** intenta primero el correo que selecciones y conserva las otras cuentas como respaldo.

Para ordenar modelos, arrastrá el bloque con el símbolo de movimiento o usá **Subir** y **Bajar**. Pulsá **Guardar cambios** cuando termines. La rotación de cuentas y modelos se configura únicamente en **General**: prioridad estricta, alternar cuentas o alternar puestos. Si elegís alternar puestos, `0` significa todos los puestos.

Al pulsar **Volver a probar este servicio** aparece un panel que indica qué está haciendo la prueba: servicio, modelo, etapa, tiempo, último avance y errores. **Actualizar todos** revisa los servicios uno por uno y luego recalcula el ranking general. El ranking anterior queda disponible mientras se trabaja. Si no hay avances, aparece **Sin avances recientes**; podés usar **Detener pruebas** y volver a intentarlo.

## Si falla

Consulta `state/proxy.log` o ejecutá `python granja.py status`. Conservá `state/`: contiene disponibilidad y latencias aprendidas. Para revisar la instalación: `/healthz` comprueba que responde, `/readyz` indica si está lista y `/v1/capabilities` muestra las funciones multimedia disponibles.

Si activaste acceso remoto, configurá `AUTH_ENABLED=true`, `NUCLEO_API_KEY`, `CORS_ALLOW_ORIGINS` y `ALLOWED_HOSTS`. Para uso exclusivamente local no hace falta cambiar esa configuración.

## Palabras importantes explicadas

**API:** reglas y direcciones para que dos programas se comuniquen; es el mostrador al que el agente envía preguntas.

**Compatible con OpenAI:** usa un formato conocido por muchas aplicaciones. No significa que tengas que usar una cuenta de OpenAI.

**Proxy:** intermediario que recibe una solicitud, elige un proveedor y devuelve la respuesta.

**Modelo:** sistema de IA que genera la respuesta. `auto` elige una opción disponible; `cheap` prioriza opciones livianas; `reasoning` razonamiento; `tools` herramientas; `vision` imágenes.

**Token:** unidad pequeña de texto que procesa el modelo. Una conversación larga consume más tokens.

**Ranking:** orden de modelos basado en pruebas y señales de calidad. Sirve como orientación y puede cambiar.

**Failover:** cambio automático a otra cuenta o proveedor cuando el actual falla.

**Streaming:** recibir la respuesta mientras se escribe.

**Multimodal:** trabajar con texto y también imágenes, audio o video.

**Local y cloud:** local procesa en tu computadora; cloud envía datos a un servicio externo. `solo_local` bloquea ese envío.

La referencia de todos los iniciadores está en `docs para agentes/EJECUTABLES_Y_USO.md`.

## Alias multimedia y claves necesarias

Los alias en español permiten llamar las funciones sin recordar las rutas técnicas. Todos usan la misma cuenta, límite, failover y políticas que las rutas estándar.

| Alias | Entrada | Proveedor y clave usable |
|---|---|---|
| `/v1/analizar-imagen` | `imagen`, `pregunta` opcional | Un modelo visual apto y su cuenta válida |
| `/v1/crear-imagen` | `descripcion` | SiliconFlow, Zhipu o Cloudflare Workers AI con acceso y cuota |
| `/v1/crear-voz` | `texto` | Edge TTS, SiliconFlow, Groq, Speechify o ElevenLabs con permisos correspondientes |
| `/v1/transcribir-audio` | MP3, WAV u OGG | Groq y API key válida |
| `/v1/crear-video` | `descripcion` | Zhipu y API key válida |
| `/v1/buscar-significado` | `texto` | SiliconFlow y API key válida |

Una clave guardada pero vencida, revocada, sin saldo o sin permiso no habilita la función. Comprobá `http://127.0.0.1:8080/v1/capabilities` antes de probar. Las rutas estándar equivalentes son `/v1/chat/completions`, `/v1/images/generations`, `/v1/audio/speech`, `/v1/audio/transcriptions`, `/v1/videos/generations` y `/v1/embeddings`.

## Uso práctico de voz, imágenes, video y audio

Estas funciones son independientes: que puedas analizar una imagen no significa que puedas crearla, y que puedas transcribir audio no significa que puedas generar voz.

### Escuchar un texto (texto a voz)

Núcleo IA ya trae **Edge TTS como opción de voz predeterminada**. No necesita API key, cuenta de proveedor ni crédito: solo una conexión a Internet para que el servicio de Microsoft convierta el texto en audio. El instalador prepara la dependencia automáticamente; si una copia antigua no la tiene, ejecutá nuevamente el instalador de Núcleo IA.

La forma más fácil de usarlo es enviar el texto al alias `/v1/crear-voz`:

```json
{"texto":"Este es mi primer audio.","provider":"edge_tts","voice":"es-AR-ElenaNeural"}
```

Si omitís `provider`, el servidor usa el proveedor configurado en la instalación; para pedir explícitamente la opción sin clave escribí `provider: "edge_tts"`. También podés usar la ruta técnica `/v1/audio/speech` con el mismo contenido.

#### Idiomas y voces

Edge TTS ofrece voces en muchos idiomas. El idioma no se elige con una palabra aparte: está incluido en el nombre de la voz. Por ejemplo:

- `es-AR-ElenaNeural`: español de Argentina (voz predeterminada).
- `es-MX-DaliaNeural`: español de México.
- `es-ES-ElviraNeural`: español de España.
- `en-US-JennyNeural`: inglés de Estados Unidos.
- `pt-BR-FranciscaNeural`: portugués de Brasil.
- `fr-FR-DeniseNeural`: francés de Francia.
- `it-IT-ElsaNeural`: italiano.

La primera parte (`es-AR`, `en-US`, etc.) indica idioma y región. La última parte identifica la voz. Si no sabés cuál elegir, dejá `es-AR-ElenaNeural`: entiende texto en español rioplatense y es la opción recomendada para empezar. El catálogo de voces puede cambiar con el tiempo; si una voz no existe, probá otra del mismo idioma.

La respuesta es un MP3. Guardalo con extensión `.mp3`. Para cambiar la forma de hablar se pueden enviar `rate` (velocidad), `pitch` (tono) y `volume` (volumen), por ejemplo `"rate":"-10%"` para hablar un poco más despacio. Si el texto es muy largo, dividilo en partes y generá un archivo por parte.

#### Otros proveedores de voz

También podés elegir `siliconflow` (CosyVoice2) o `groq` (PlayAI TTS), pero esos proveedores sí requieren una API key válida, el modelo habilitado y cuota disponible. Si no configuraste esas claves, usá Edge TTS.

ElevenLabs se puede elegir como proveedor secundario exclusivo de voz con `provider: "elevenlabs"`. Requiere `ELEVENLABS_API_KEY` y un `voice_id` de tu cuenta. No participa en chat ni en el ranking general. Admite las opciones avanzadas de su API, como `model_id`, `voice_settings`, `language_code`, `output_format`, diccionarios de pronunciación y ajustes de latencia.

### Crear una imagen

Usá `/v1/crear-imagen` con una descripción clara. SiliconFlow (`FLUX.1-schnell`), Zhipu (`CogView-3-Flash`) y Cloudflare Workers AI (`@cf/black-forest-labs/flux-1-schnell`) tienen adaptadores implementados. Cada uno requiere su propia credencial, permiso y acceso/cuota. La disponibilidad y el precio dependen de tu cuenta; consulta `/v1/capabilities`.

```json
{"descripcion":"Una plaza de Mendoza al atardecer, estilo ilustración","provider":"siliconflow","model":"auto"}
```

La respuesta contiene la imagen o una referencia para descargarla. No repitas la solicitud automáticamente si no ves la imagen: una generación puede haberse completado aunque la conexión se haya cortado.

### Crear un video

Usá `/v1/crear-video` con una descripción del movimiento. Los adaptadores de esta copia contemplan Zhipu y SiliconFlow; el proveedor y modelo utilizables dependen del catálogo, el permiso de tu cuenta y la cuota. No envíes una segunda solicitud automáticamente si la primera quedó sin respuesta: el proveedor podría estar procesándola.

```json
{"descripcion":"Un cóndor vuela sobre la cordillera al amanecer","model":"auto"}
```

El servicio puede devolver una URL o un identificador de tarea. Guardá ese dato y consultá el resultado según indique el servicio; no dupliques la petición al reintentar.

### Analizar una imagen (visión)

Usá `/v1/analizar-imagen` para que un modelo describa una imagen existente. Podés enviar una URL o una imagen codificada como `data:image/...;base64,...`. Requiere al menos un proveedor con un modelo visual apto y una cuenta válida, por ejemplo Ollama, Google, Groq, Cloudflare, NVIDIA, OpenRouter, SiliconFlow, Zhipu, Cohere, TokenRouter, xKiro o Token Harbor, según su catálogo actual.

```json
{"imagen":"https://ejemplo.com/foto.jpg","pregunta":"¿Qué aparece en la foto?"}
```

### Transcribir una grabación

Usá `/v1/transcribir-audio` y adjuntá un archivo MP3, WAV u OGG. La integración configurada usa Groq y el modelo Whisper, por lo que requiere una API key de Groq con cuota. El resultado es texto que luego podés resumir o convertir en voz.

### Buscar por significado (embeddings)

Usá `/v1/buscar-significado` para convertir texto en números que representan su significado. SiliconFlow o Cohere pueden aportar modelos de embeddings según el catálogo y la cuenta; la clave debe tener acceso a esa función. Esta operación sirve para buscar documentos parecidos; no genera una respuesta ni una imagen.

```json
{"texto":"economía participativa y cooperativas","model":"auto"}
```

### Antes de empezar

Abrí `http://127.0.0.1:8080/v1/capabilities`: allí Núcleo IA muestra qué capacidades están activas y qué proveedores detectó. Una clave escrita pero vencida, revocada o sin cuota cuenta como no disponible. Las claves se cargan desde **Mis servicios** y nunca se ponen dentro del prompt ni se comparten con el agente.

## Edge TTS incluido: voz sin API key

Esta es una capacidad que Núcleo IA incorpora para probar texto a voz sin crear cuentas en servicios externos. **Edge TTS no necesita API key, registro, saldo ni configuración de proveedor.** Solo necesita conexión a Internet durante la generación.

### Cómo usarlo

Enviá `POST /v1/crear-voz` con `provider` igual a `edge_tts` y el texto en `texto`:

```json
{"provider":"edge_tts","texto":"Bienvenido a Núcleo IA.","voice":"es-AR-ElenaNeural"}
```

La respuesta es un archivo MP3. Guardalo con extensión `.mp3` y abrilo con el reproductor de música. También podés usar `/v1/audio/speech`. Si omitís `voice`, se usa `es-AR-ElenaNeural`.

### Idiomas y voces

El nombre incluye idioma y región (`es-AR` es español argentino; `en-US`, inglés estadounidense):

| Voz | Idioma |
|---|---|
| `es-AR-ElenaNeural` | Español argentino (predeterminada) |
| `es-MX-DaliaNeural` | Español mexicano |
| `es-ES-ElviraNeural` | Español de España |
| `en-US-JennyNeural` | Inglés estadounidense |
| `pt-BR-FranciscaNeural` | Portugués brasileño |
| `fr-FR-DeniseNeural` | Francés |
| `it-IT-ElsaNeural` | Italiano |

El catálogo puede cambiar. Si una voz falla, probá otra del mismo idioma. Escribí el texto en el idioma elegido para una pronunciación natural.

### Velocidad, tono y volumen

Los campos opcionales `rate`, `pitch` y `volume` modifican la lectura. Por ejemplo, `"rate":"-10%"` habla más despacio, `"pitch":"+2Hz"` sube el tono y `"volume":"-5%"` baja el volumen.

Para textos muy largos, dividilos en fragmentos y generá un MP3 por fragmento. Si aparece un error de dependencia, ejecutá nuevamente el instalador de Núcleo IA.
