# Búsqueda semántica (embeddings)

Convierte texto en vectores numéricos para comparar significados. Endpoint: `POST /v1/buscar-significado`.

```json
{"texto":"cooperativas latinoamericanas","model":"auto"}
```

El enrutamiento soporta Cohere y SiliconFlow; el catálogo base incluye `BAAI/bge-m3` y modelos de Cohere. Requiere una cuenta con permiso/cuota de embeddings. Consulta `GET /v1/capabilities` y usa `model="auto"` para permitir que el proxy elija una ruta disponible. La respuesta sigue el formato de embeddings compatible con OpenAI y no es texto conversacional.

```bash
curl -fS http://127.0.0.1:8080/v1/embeddings \
  -H 'Content-Type: application/json' \
  -d '{"model":"auto","input":["¿Cómo instalo el servidor?","La instalación se inicia con el instalador."]}'
```

Almacena cada vector junto a su texto, proveedor, modelo y dimensión. Para comparar vectores, usa el mismo modelo y la misma dimensión en todos los documentos y consultas. Si cambias el modelo, vuelve a generar el índice; los vectores de modelos distintos no son necesariamente comparables.
