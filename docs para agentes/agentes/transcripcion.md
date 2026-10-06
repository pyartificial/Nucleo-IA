# Transcripción de audio

Convierte una grabación en texto. Endpoint sencillo: `POST /v1/transcribir-audio` como formulario multipart, campo `file` y opcional `model=whisper-large-v3`.

El proveedor integrado es Groq (Whisper) y requiere API key con permiso/cuota de transcripción. La ruta recibe `multipart/form-data`, no JSON. El límite máximo predeterminado es 25 MiB (`GROQ_MAX_UPLOAD_BYTES` puede ajustarlo). El código conserva el nombre y tipo MIME del archivo al reenviarlo; usa formatos aceptados por Groq (por ejemplo MP3, WAV, M4A, OGG, FLAC o WEBM) y respeta el límite del proveedor.

```bash
curl -fS http://127.0.0.1:8080/v1/audio/transcriptions \
  -F 'file=@grabacion.mp3' \
  -F 'model=whisper-large-v3' \
  -F 'response_format=json'
```

La respuesta es JSON con el texto. Un `413` indica que el archivo supera el límite local; `503`, que no hay cuenta de Groq utilizable; `429`, cuota/límite; `401/403`, clave o permiso. El archivo se guarda temporalmente durante la operación y se elimina después. No incluyas credenciales en el formulario y evita reintentos ciegos de archivos grandes.
