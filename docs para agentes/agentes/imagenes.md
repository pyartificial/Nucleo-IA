# Creación de imágenes

Genera una imagen desde una descripción. Endpoint: `POST /v1/crear-imagen`.

```json
{"descripcion":"Un zorro leyendo bajo la lluvia, ilustración detallada","provider":"siliconflow","model":"auto"}
```

Proveedores implementados en esta copia: SiliconFlow (`black-forest-labs/FLUX.1-schnell`), Zhipu (`CogView-3-Flash`) y Cloudflare Workers AI (`@cf/black-forest-labs/flux-1-schnell`). Cloudflare usa el endpoint de inferencia de la cuenta. Los tres requieren credenciales, permiso y cuota válidos; el modo predeterminado puede restringir modelos de imagen que no estén aprobados como base gratuita. Comprueba `/v1/capabilities`, porque acceso y precios cambian por cuenta/modelo.

La respuesta puede contener una URL o datos codificados, según el proveedor; inspecciona `data` y conserva la URL o el contenido recibido. Una generación puede continuar en el proveedor aunque el cliente pierda la conexión: no repitas automáticamente una petición ambigua, para evitar consumir cuota dos veces.

Ejemplo completo:

```bash
curl -fS http://127.0.0.1:8080/v1/images/generations \
  -H 'Content-Type: application/json' \
  -d '{"model":"auto","prompt":"Un zorro leyendo bajo la lluvia, ilustración detallada","provider":"siliconflow"}'
```
