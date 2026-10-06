# Texto a voz (TTS)

TTS convierte texto escrito en audio hablado. En esta versión están implementados Edge TTS, SiliconFlow, Groq, Speechify y ElevenLabs. Speechify y ElevenLabs son rutas seleccionadas directamente; no asumas que participan en el ranking general de chat. La respuesta real es un archivo de audio binario, no JSON.

## Antes de llamar

1. Comprueba `GET http://127.0.0.1:8080/v1/capabilities` y confirma que `speech_generation.enabled` sea `true`.
2. Elige un proveedor explícito. Edge TTS requiere Internet y la dependencia instalada; SiliconFlow, Groq, Speechify y ElevenLabs requieren credencial habilitada y cuota. Para ElevenLabs, la cuenta debe permitir `speech_generation` y debe existir un `voice_id`.
3. No envíes API keys en la petición. Se configuran en Núcleo IA.
4. Para procesar texto privado, ten presente que Edge TTS también envía el texto al servicio externo de voz.

## Ejemplo recomendado: Edge TTS

`POST /v1/audio/speech` (o el alias `/v1/crear-voz`) con JSON:

```json
{"provider":"edge_tts","input":"Hola, esto es una prueba.","voice":"es-AR-ElenaNeural","rate":"+0%","pitch":"+0Hz","volume":"+0%"}
```

Guarda el cuerpo de la respuesta como `.mp3`; no intentes decodificarlo como JSON. Ejemplo con `curl`:

```bash
curl -fS http://127.0.0.1:8080/v1/audio/speech \
  -H 'Content-Type: application/json' \
  -d '{"provider":"edge_tts","input":"Hola desde Núcleo IA.","voice":"es-AR-ElenaNeural"}' \
  --output saludo.mp3
```

Voces de ejemplo: `es-AR-ElenaNeural`, `es-MX-DaliaNeural`, `es-ES-ElviraNeural`, `en-US-JennyNeural`, `pt-BR-FranciscaNeural`. El catálogo de Edge puede cambiar. `rate`, `pitch` y `volume` son opcionales.

## Proveedores con API

- SiliconFlow: `provider="siliconflow"`; modelo base `FunAudioLLM/CosyVoice2-0.5B`.
- Groq: `provider="groq"`; modelo base `playai-tts`.
- Speechify: `provider="speechify"`; requiere `input`, `voice_id`; `model` predeterminado `simba-3.2`, `audio_format` predeterminado `mp3`. Conecta la cuenta desde **Mis servicios → Proveedores opcionales** y activa el proveedor si aparece deshabilitado.
- ElevenLabs: `provider="elevenlabs"`; requiere cuenta habilitada con `speech_generation`, `ELEVENLABS_API_KEY` y `voice_id` por petición o `ELEVENLABS_VOICE_ID`. `model` predeterminado `eleven_multilingual_v2`; opciones avanzadas como `voice_settings` se reenvían al proveedor.

Ejemplo Speechify:

```json
{"provider":"speechify","input":"Hola.","voice_id":"ID_DE_VOZ","model":"simba-3.2","audio_format":"mp3"}
```

Ejemplo ElevenLabs:

```json
{"provider":"elevenlabs","input":"Hola.","voice_id":"ID_DE_TU_VOZ","model":"eleven_multilingual_v2","output_format":"mp3_44100_128","voice_settings":{"stability":0.5,"similarity_boost":0.75}}
```

Para evitar cargos inesperados, revisa el plan/cuota del proveedor. Las respuestas `401/403` indican autenticación, permiso o política; `429` indica límite; `503` suele significar que no hay una cuenta configurada y utilizable. Reintenta como máximo una vez ante un fallo transitorio; una síntesis repetida puede consumir cuota dos veces.
