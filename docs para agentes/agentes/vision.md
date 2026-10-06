# Análisis de imágenes (visión)

Envía una imagen a un modelo capaz de verla y pide una explicación. Endpoint: `POST /v1/analizar-imagen`.

```json
{"imagen":"data:image/png;base64,...","pregunta":"¿Qué objetos aparecen?","model":"vision"}
```

`imagen` puede ser una URL accesible para el proveedor o un `data:image/...;base64,...`. El alias transforma la imagen en un mensaje `image_url` y usa `POST /v1/chat/completions`, por lo que debe existir un modelo visual apto en el catálogo/ranking. Las URLs deben ser accesibles desde el proveedor, no solo desde el equipo del usuario. Comprueba `/v1/capabilities`; un proveedor configurado no implica que cada modelo acepte imágenes. Analizar una imagen no la genera.

```json
{"model":"vision","messages":[{"role":"user","content":[{"type":"text","text":"Describe la escena y lee el cartel."},{"type":"image_url","image_url":{"url":"https://ejemplo.test/foto.jpg"}}]}]}
```

No envíes imágenes privadas a modelos cloud sin autorización. Para uso local, verifica que Ollama tenga instalado un modelo visual compatible y que la política permita solo procesamiento local.
