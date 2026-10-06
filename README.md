# Núcleo IA

**Una API local para conectar aplicaciones con distintos proveedores de inteligencia artificial y modelos de Ollama.** Núcleo IA centraliza las conexiones, las cuentas y la selección de modelos en una dirección compatible con clientes que usan el formato de API de OpenAI.

> “Compatible con OpenAI” describe el formato de comunicación; no significa que tus solicitudes vayan a OpenAI. El proveedor que las recibe depende de las cuentas y del modelo que configures.

Núcleo IA está pensado para ejecutarse en tu propia computadora, en Windows, Linux o WSL. Puede combinar servicios en la nube con modelos locales de Ollama. La disponibilidad de cada capacidad depende del servicio, del modelo, de tu cuenta y de los límites vigentes del proveedor.

## Funciones principales

- Un punto de conexión local para aplicaciones compatibles: `http://127.0.0.1:8080/v1`.
- Administración de cuentas y servicios desde las pantallas **Mis servicios** y **Centro de control**.
- Selección y rotación entre cuentas y modelos configurados, con alternativas cuando una ruta no está disponible.
- Catálogos y rankings que podés actualizar desde tu propia instalación.
- Rutas por finalidad, como `auto`, `cheap`, `reasoning`, `tools` y `vision`, según las capacidades verificadas en los modelos disponibles.
- Integraciones de chat y, según el proveedor configurado, visión, texto a voz, transcripción, generación de imágenes, video y embeddings.
- Opciones para ejecutar modelos localmente con Ollama.

No todos los proveedores ofrecen todas las funciones. La generación de música es una simulación. Consultá `/v1/capabilities` en tu instalación para conocer las capacidades anunciadas allí y probá cada integración antes de depender de ella.

## Servicios incluidos en esta copia

La pantalla **Mis servicios** separa conexiones generales y opcionales para que sea más fácil encontrarlas. **Servicios generales** incluye Ollama, Groq, OpenRouter, NVIDIA NIM, Google Gemini, Cloudflare Workers AI, Cohere, SiliconFlow, Zhipu/Z.AI, TokenRouter, xKiro, Token Harbor, APInex, ElevenLabs (por capacidad), Agnes AI, Aion Labs, BazaarLink, Hugging Face Inference Providers, Mistral AI, Requesty, SEA-LION y UnoRouter.

**Proveedores opcionales** incluye Speechify (solo texto a voz), Airforce API, AnyAPI.ai, DreamPrompting, OrcaRouter, Routeway, Ollama Cloud · API key, Cerebras, OpenAI, Anthropic, DeepSeek, Grok/xAI, MiniMax, Alibaba/Qwen y proveedores especializados de música (Treblo · música, Stable Audio · música, Mubert · música, Soundraw · música y Beatoven · música).

Un proveedor opcional con dos o más cuentas habilitadas aparece junto a los servicios generales, excepto GitHub. La ubicación organiza las tarjetas: no promete que sus modelos sean gratuitos. Cada proveedor define precios, cuotas y permisos por separado. Revisa el costo de la ruta/modelo concreto y `/v1/capabilities` antes de enviar una solicitud.

## Instalación rápida

### Windows

1. Descargá este repositorio y extraé sus archivos en una carpeta normal, por ejemplo `Documentos\\Nucleo-IA`.
2. Ejecutá `instalar_nucleo_ia.bat` y seguí las indicaciones que aparezcan.
3. Abrí **Mis servicios** con `mis_servicios.vbs` y agregá al menos una cuenta o servicio local.
4. Iniciá el programa con `iniciar_todo.bat`.
5. Abrí <http://127.0.0.1:8080/healthz>. Si ves una respuesta de estado correcto, el servidor está funcionando.

### Linux o WSL

1. Descargá este repositorio y extraé sus archivos.
2. Abrí una terminal en la carpeta del proyecto y ejecutá `bash instalar_nucleo_ia.sh`.
3. Ejecutá `bash mis_servicios.sh` y agregá al menos una cuenta o servicio local.
4. Iniciá el programa con `bash iniciar_todo.sh`.
5. Comprobá el estado en <http://127.0.0.1:8080/healthz>.

La instalación prepara `.env` a partir de `.env.example`. Las claves de los proveedores se agregan en la configuración local y nunca deben publicarse.

## Conectar una aplicación

En la configuración de una aplicación compatible con una API de chat tipo OpenAI, usá estos valores iniciales:

| Campo | Valor |
| --- | --- |
| Dirección base | `http://127.0.0.1:8080/v1` |
| Modelo | Consultá `http://127.0.0.1:8080/v1/models` después de configurar cuentas y actualizar los rankings |
| Clave | La clave local que indique tu configuración, si activaste autenticación |

El servidor escucha en la propia computadora de manera predeterminada. El acceso desde otras computadoras requiere configuración de red y autenticación; no expongas el servicio directamente a Internet.

## Documentación

- [Manual completo para usuarios](informacion/MANUAL_USUARIO.pdf): guía detallada, paso a paso.
- [Manual para principiantes](docs%20para%20agentes/MANUAL_PRINCIPIANTE.md).
- [Conectar cuentas y servicios](docs%20para%20agentes/MIS_SERVICIOS.md).
- [Modelos, pasarelas y ranking gratuito](docs%20para%20agentes/PASARELAS_Y_RANKING_GRATUITO.md).
- [Capacidades y rankings](docs%20para%20agentes/RANKING_AUTOMATICO.md).
- [Manual avanzado](docs%20para%20agentes/MANUAL_AVANZADO.md).
- [Integración para agentes](docs%20para%20agentes/GUIA_AGENTES.md).
- [Instalación con Docker](docs%20para%20agentes/INSTALACION_DOCKER.md).

## Privacidad y seguridad

Las claves API son privadas. Guardalas solo en la configuración local; no las incluyas en mensajes, capturas, registros, incidencias ni commits. No publiques `.env`, `granja.env`, `cuentas.json`, sesiones, registros o contenido de `state/`. Este paquete de publicación incluye `.env.example`, que es una plantilla sin las claves de tus cuentas.

Cada proveedor puede aplicar cargos, límites y condiciones propios. Revisá esos términos antes de usar un servicio. Las solicitudes salen hacia el proveedor correspondiente cuando usás una integración en la nube.

Para reportar un problema de seguridad de forma privada, escribí a [pyartificial@gmail.com](mailto:pyartificial@gmail.com). No incluyas claves ni contraseñas en el mensaje. Más información en [SECURITY.md](SECURITY.md).

## Licencia

Núcleo IA se distribuye bajo **GNU Affero General Public License v3 o posterior (AGPL-3.0-or-later)**. Leé el archivo [LICENSE](LICENSE).

## Autor y contacto

Creado y mantenido por **Cristian Quiroga**, Malargüe, Mendoza, Argentina.

- Correo: [pyartificial@gmail.com](mailto:pyartificial@gmail.com)

Al informar un problema, indicá tu sistema operativo y los pasos para reproducirlo. Quitá de antemano claves, contraseñas, correos privados y otros datos personales.
