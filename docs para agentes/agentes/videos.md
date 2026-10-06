# Creación de videos

Solicita un video corto desde texto. Endpoint: `POST /v1/crear-video`.

```json
{"descripcion":"Un tren cruza un valle al amanecer","model":"auto"}
```

El endpoint planifica Zhipu (`CogVideoX-Flash`) y SiliconFlow (`stabilityai/stable-video-diffusion`). Requiere credenciales y acceso/cuota del proveedor; que la capacidad aparezca habilitada no garantiza que un modelo esté disponible para tu cuenta. Los modelos fuera de la lista base permanecen bloqueados salvo configuración explícita. La respuesta puede ser una URL o una tarea del proveedor: conserva el ID/URL y no dupliques la solicitud si se corta la conexión. El proxy de esta versión no expone una ruta de consulta de estado propia; sigue las instrucciones del proveedor para una tarea pendiente.

```bash
curl -fS http://127.0.0.1:8080/v1/videos/generations \
  -H 'Content-Type: application/json' \
  -d '{"model":"auto","prompt":"Un tren cruza un valle al amanecer","provider":"zhipu"}'
```
