# Llamadas simples de Núcleo IA

Las rutas estándar en inglés siguen disponibles para compatibilidad. Estas rutas en español son atajos: reutilizan el mismo proveedor, límite, failover y política, sin duplicar procesamiento.

| Ruta simple | Campo principal | Proveedor necesario |
|---|---|---|
| `/v1/analizar-imagen` | `imagen` y `pregunta` opcional | Ollama, Cloudflare, NVIDIA, OpenRouter, Google, Groq, Cohere, SiliconFlow, Zhipu, TokenRouter, xKiro o Token Harbor, si la cuenta tiene un modelo visual apto |
| `/v1/crear-imagen` | `descripcion` | SiliconFlow con una API key usable |
| `/v1/crear-voz` | `texto` | SiliconFlow con una API key usable |
| `/v1/transcribir-audio` | archivo MP3, WAV u OGG | Groq con una API key usable |
| `/v1/crear-video` | `descripcion` | Zhipu con una API key usable |
| `/v1/buscar-significado` | `texto` | SiliconFlow con una API key usable |

Una clave escrita pero vencida, limitada o sin permiso no habilita la función. `/v1/capabilities` muestra qué funciones detectó como disponibles. Visión analiza imágenes; no las crea. Video puede devolver una tarea del proveedor y requiere esperar el resultado según la respuesta recibida.
