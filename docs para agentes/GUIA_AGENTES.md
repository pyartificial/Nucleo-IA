# Guía de integración para agentes

Esta guía describe la copia exportable actual. El servidor debe estar iniciado y accesible. Usa `http://127.0.0.1:8080` como origen y `/v1` para rutas compatibles con OpenAI. Desde Docker, `127.0.0.1` apunta al contenedor: usa la dirección del anfitrión configurada para esa red.

## Descubrimiento, en orden

1. `GET /healthz`: proceso activo.
2. `GET /readyz`: preparación general.
3. `GET /v1/capabilities`: proveedores disponibles por capacidad; consulta aquí antes de imágenes, audio, video o embeddings.
4. `GET /v1/models`: IDs de modelos/rutas publicados. El catálogo y cuotas cambian; prefiere `model="auto"` salvo que haya una razón para fijar el modelo.
5. `POST /v1/chat/completions`: chat estándar. Los perfiles lógicos incluyen `auto`, `cheap`, `reasoning`, `tools` y `vision` cuando el ranking tiene candidatos.

Configura API keys en Núcleo IA, nunca en prompts, código del agente o peticiones. En modo personal local, los iniciadores pueden usar la sesión local; si la autenticación está habilitada, usa la clave que configuró el administrador. No imprimas cabeceras de autorización ni contenido sensible en logs.

## Capacidades implementadas en esta copia

| Función | Ruta | Entrada | Proveedor/adaptador implementado |
|---|---|---|---|
| Chat y herramientas | `POST /v1/chat/completions` | JSON OpenAI chat | Catálogo activo; consulta `/v1/models` |
| Visión | Chat con `image_url` o `/v1/analizar-imagen` | URL accesible o data URL base64 | Cualquier modelo visual clasificado y habilitado |
| Transcripción | `POST /v1/audio/transcriptions` | multipart `file`, `model` | Groq Whisper |
| Texto a voz | `POST /v1/audio/speech` o `/v1/crear-voz` | JSON con `input`/`texto` | Edge TTS, SiliconFlow, Groq, Speechify; ElevenLabs con permiso de capacidad |
| Crear imagen | `POST /v1/images/generations` o `/v1/crear-imagen` | JSON `prompt` | SiliconFlow, Zhipu y Cloudflare Workers AI |
| Crear video | `POST /v1/videos/generations` o `/v1/crear-video` | JSON `prompt` | Plan Zhipu/SiliconFlow; depende de permisos, cuota y compatibilidad del modelo |
| Embeddings | `POST /v1/embeddings` o `/v1/buscar-significado` | JSON `input` | Cohere, SiliconFlow |
| Música | `POST /v1/music/generations` | JSON `prompt` | Solo simulador `mock_music`; no genera audio real |

El registro de un proveedor no demuestra que cada adaptador esté terminado. Usa `/v1/capabilities` como descubrimiento inicial y una llamada pequeña como validación final. Speechify y ElevenLabs están disponibles por selección explícita de proveedor para TTS; ElevenLabs además requiere que la cuenta tenga `speech_generation` habilitado.

## Contrato de peticiones y respuestas

TTS e imagen pueden devolver bytes o JSON del proveedor: inspecciona `Content-Type`; no fuerces `response.json()` para `audio/mpeg` o `image/*`. Transcripción recibe `multipart/form-data` y devuelve JSON. Video puede devolver una tarea; conserva su ID. El límite de subida local para audio es 25 MiB por defecto, ajustable con `GROQ_MAX_UPLOAD_BYTES`.

Ejemplo de chat:

```bash
curl -fS http://127.0.0.1:8080/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{"model":"auto","messages":[{"role":"user","content":"Responde solo: funciona"}]}'
```

Ejemplo de transcripción:

```bash
curl -fS http://127.0.0.1:8080/v1/audio/transcriptions \
  -F 'file=@grabacion.mp3' -F 'model=whisper-large-v3'
```

Ejemplo de voz, guardando la respuesta binaria:

```bash
curl -fS http://127.0.0.1:8080/v1/audio/speech \
  -H 'Content-Type: application/json' \
  -d '{"provider":"edge_tts","input":"Hola.","voice":"es-AR-ElenaNeural"}' \
  --output voz.mp3
```

## Privacidad y reintentos

No hagas reintentos automáticos ciegos para generación de audio, imagen o video: el proveedor puede haber terminado aunque el cliente pierda la respuesta. Para una respuesta ambigua, detén el reintento y comprueba el proveedor si ofrece consulta por ID. No envíes contenido privado a otro proveedor por failover salvo que la política de datos lo permita. Edge TTS tampoco es local: necesita Internet y envía texto al servicio de voz externo.

## Errores frecuentes

- `422`: falta un campo o el cuerpo tiene formato incorrecto.
- `413`: archivo mayor al máximo local.
- `503`: no hay cuenta utilizable o falta una dependencia/capacidad.
- `402` o `429`: el proveedor exige saldo o aplicó un límite.
- `401` o `403`: credencial, permiso o política de envío.
- `502`: problema al contactar o recibir respuesta del proveedor.

Una cuenta registrada o una capacidad marcada `enabled` no garantiza cuota, disponibilidad externa ni acceso a cada modelo. Confirma con una petición pequeña y conserva el código HTTP sin revelar secretos.

## Fichas específicas

- [Texto a voz](agentes/tts.md)
- [Creación de imágenes](agentes/imagenes.md)
- [Creación de videos](agentes/videos.md)
- [Análisis visual](agentes/vision.md)
- [Transcripción de audio](agentes/transcripcion.md)
- [Embeddings y búsqueda semántica](agentes/embeddings.md)

El ranking cambia con el tiempo. El usuario puede actualizarlo desde Centro de control; los agentes deben preferir `auto` y consultar `/v1/models` cuando necesiten un ID fijo.
