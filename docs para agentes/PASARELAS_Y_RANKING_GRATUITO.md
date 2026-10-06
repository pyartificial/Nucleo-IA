# Guía de pasarelas y modelos gratuitos

Esta guía explica cómo añadir las pasarelas compatibles con la API de chat de OpenAI, actualizar sus modelos y entender qué entra en el ranking automático. Está escrita para distinguir tres cosas que suelen confundirse: tener una clave, ver un modelo en un catálogo y poder usarlo gratis.

## 1. Antes de empezar

Necesitás una conexión a Internet para hablar con proveedores en la nube. Cada proveedor debe darte su propia clave API. La clave es privada: se guarda localmente en `.env` y no se debe enviar por correo, capturas, GitHub o mensajes de soporte.

No todas las cuentas permiten todos los modelos. Un saldo inicial, un crédito promocional, una cuota diaria o un plan gratis de la cuenta **no** significa que cada modelo cueste cero. Revisá las condiciones del servicio antes de activar una cuenta.

## 2. Pasarelas incluidas

Estas integraciones se administran desde **Mis servicios** y el Centro de control. Agnes AI, Aion Labs, BazaarLink, Hugging Face Inference Providers, Mistral AI, Requesty, SEA-LION y UnoRouter están agrupados bajo **Servicios generales** en esta copia; Airforce, AnyAPI, DreamPrompting, OrcaRouter, Routeway y Ollama Cloud por API key están en **Proveedores opcionales**. La agrupación solo ordena la interfaz. No afirma que todos los modelos sean gratis ni que el servicio ofrezca la misma cuota a todas las cuentas.

| Servicio | Qué consulta Núcleo IA | Precaución sobre gratuidad |
|---|---|---|
| Agnes AI | Catálogo `/v1/models` y prueba de chat | Se acepta solo el costo cero publicado para el modelo o una variante `:free`. |
| Aion Labs | Catálogo y precio declarado | Los créditos promocionales de una cuenta no vuelven gratis a todos sus modelos. |
| Airforce API | Catálogo de canales y precios (`channels=1`) | Solo variantes con evidencia por modelo y probadas con la cuenta. |
| AnyAPI.ai | Catálogo y metadatos de precio | Un nivel o cuota gratuita de la cuenta no basta. |
| BazaarLink | Catálogo, modalidades y rutas gratuitas | Se desactiva el fallback gratuito a pago en las pruebas; si la cuota gratis falla, no se debe asumir que la solicitud pasa a un servicio pago. |
| DreamPrompting | Catálogo y prueba de ruta | Las pruebas piden no sustituir el modelo; la cuota compartida puede limitar el servicio. |
| Hugging Face Inference Providers | Catálogo del Hub, ruta/proveedor, tareas y precios | El crédito de la cuenta no basta. Debe existir una ruta concreta marcada gratis o con ambos precios en cero. |
| OrcaRouter | Catálogo y alias `orcarouter/free` | El alias publicado como gratis puede estar sujeto a límites y disponibilidad. |
| Requesty | Catálogo, precio y prueba | Los créditos del plan no convierten automáticamente en gratis los modelos con precio. |
| Routeway | Catálogo y variantes de precio cero | Se comprueba la variante exacta, incluida `:free` cuando el catálogo la publica. |
| SEA-LION | Catálogo y ruta compatible | Una clave de prueba o límite de solicitudes no demuestra precio cero por modelo. |
| UnoRouter | Catálogo/precios del servicio | Se requiere señal gratuita explícita o ambos precios en cero. |
| Ollama Cloud · API key | Catálogo de Ollama Cloud | Es distinto de vincular una instancia con inicio de sesión. Una clave o plan no prueba que cada modelo sea gratis. |
| Mistral AI | Catálogo de modelos y precios | Los modelos pagos no se clasifican como gratis por tener saldo o una prueba de cuenta. |

El catálogo del Centro de control indica cómo crear una clave y la dirección oficial correspondiente. Las páginas y condiciones de cada proveedor pueden cambiar; verificá sus precios en su sitio antes de usar modelos.

## 3. Agregar una cuenta, paso a paso

1. Abrí **Mis servicios** desde el Centro de control.
2. Elegí el proveedor que querés conectar.
3. En otra pestaña, abrí el enlace oficial para crear una clave que muestra su tarjeta. Iniciá sesión en ese proveedor y creá la clave.
4. Copiá la clave API completa. No copies espacios antes o después.
5. Volvé a Núcleo IA, elegí **Agregar cuenta** y pegá la clave en el campo de ese proveedor. Si la interfaz solicita una etiqueta, poné un nombre que te ayude a reconocerla, por ejemplo `cuenta personal`.
6. Guardá la cuenta y revisá el resultado de conexión. Una clave guardada puede aparecer pendiente hasta que ejecutes una comprobación.
7. Si la cuenta no se puede comprobar, revisá que la clave pertenezca al proveedor correcto, que no tenga espacios extra y que la cuenta tenga acceso a la API. No pegues la clave en el mensaje de error.
8. Repetí estos pasos únicamente para las cuentas que quieras usar.

Las claves se asocian a variables locales como `AGNES_API_KEY`, `AION_API_KEY` o `HF_TOKEN`; el programa las administra por cuenta. No edites estas variables manualmente mientras el Centro de control está escribiendo configuración.

## 4. Actualizar catálogos y rankings

1. Abrí el **Centro de control**.
2. Entrá en **Rankings**.
3. Para una cuenta concreta, elegí **Por servicio**, seleccioná el proveedor y ejecutá **Volver a probar este servicio**.
4. Para hacer la actualización normal completa, elegí **General** y ejecutá la actualización general. Esto consulta proveedores configurados y consolida sus resultados; cada servicio puede tardar o fallar de forma independiente. **Actualizar todos** usa el mismo flujo; cada proveedor se consulta una sola vez.
5. Esperá a que el proceso termine y leé el resultado de cada etapa. Si aparece un error de clave, cuota o acceso, ese modelo no se debe tratar como verificado.
6. Consultá el ranking general y `/v1/models`. La ruta automática usa los modelos agénticos verificados, no cualquier nombre que aparezca en una página de catálogo.

Las comprobaciones hacen solicitudes a los proveedores usando tus claves. Pueden consumir cuota o saldo según las reglas del servicio; las rutas marcadas como gratis tienen controles para evitar confundir fallbacks pagos con gratuitos, pero revisá siempre los avisos del proveedor. No ejecutes el ranking si no aceptás que se envíen solicitudes de prueba desde tu cuenta.

Las pasarelas de esta guía y Mistral usan el comprobador compartido `ranking_pasarelas_free.py`. Al actualizar una sola pestaña, Núcleo IA le pasa el proveedor elegido; **Actualizar todos** o **General** ejecuta el ranker una vez dentro de la actualización integral y consolida el ranking. Si una fuente falla, no se vuelve a presentar su ranking viejo como si acabara de verificarse. No hace falta crear un archivo `ranking_<proveedor>.py` para cada pasarela.

## 5. Qué significa cada resultado

- **Encontrado en catálogo**: el proveedor anunció ese identificador o capacidad. No confirma que tu cuenta pueda usarlo.
- **Conexión comprobada**: la cuenta obtuvo una respuesta de chat. No confirma gratuidad.
- **Gratis**: hay evidencia específica de costo cero para el modelo/ruta, según el catálogo o una política explícita documentada en el código.
- **Herramientas comprobadas**: el modelo devolvió la llamada y los argumentos exactos de una función de prueba.
- **Razonamiento comprobado**: respondió correctamente una pregunta determinista de prueba.
- **Apto para agentes**: pasó la prueba de chat y los mínimos de herramientas y razonamiento; si se usa la ruta general gratuita, además tiene que ser gratis y la cuenta debe haberse comprobado.
- **Capacidad secundaria descubierta**: los metadatos del proveedor sugieren una tarea como visión, TTS, transcripción, imagen, video, embeddings, reranking o documentos. Esto es un hallazgo de catálogo, no significa que la operación esté conectada en Núcleo IA.
- **Adaptador implementado y probado**: existe una ruta real de Núcleo IA para esa tarea y se probó con una cuenta/modelo compatible. Revisá `/v1/capabilities`.

El puntaje común ordena modelos que ya pasaron los mínimos. No transforma en gratis un modelo, no concede acceso a la cuenta y no sustituye las condiciones del proveedor.

## 6. Reglas particulares de las pruebas

- No se implementa GitHub como proveedor de modelos: GitHub Models fue retirado el 30 de julio de 2026. Un token personal de GitHub no debe confundirse con una clave de inferencia activa ni probarse contra una API de modelos. GitHub Copilot es un producto separado. Fuente oficial: [GitHub Models](https://docs.github.com/en/github-models).
- Los gateways con modelos gratis y pagos se filtran por modelo/ruta. Las pruebas no deben lanzar una solicitud a una ruta paga solo porque una cuenta tenga créditos gratis.
- BazaarLink recibe una indicación para no hacer fallback desde gratuito hacia pago.
- DreamPrompting recibe una indicación para no reemplazar el modelo pedido por otro.
- Hugging Face se separa por proveedor de inferencia; dos rutas del mismo modelo pueden tener precios o capacidades distintas.
- OrcaRouter puede ofrecer un alias dinámico `orcarouter/free`; la prueba acepta el modelo que devuelva ese alias dinámico.
- TokenRouter publica modelos gratuitos y pagos en el mismo catálogo. El ranker consulta cada cuenta configurada, filtra primero las rutas con `:free`, un indicador de gratuidad o ambos precios en cero y prueba cada ruta solo con cuentas cuyo catálogo la declara gratuita. Conserva el ID de la cuenta que pasó la prueba. La ruta entra en `auto` si además supera chat, herramientas y razonamiento. No se deduce gratuidad de los créditos de la cuenta. Los `api_formats` de tareas multimedia se normalizan a `rankings_capacidades` en el ranking global, sin afirmar que exista un adaptador de tarea si no lo hay.
- xKiro consulta sus cuentas configuradas por separado, conserva qué cuenta pasó cada modelo y descuenta las cuentas con cuota agotada del conjunto de candidatas. Las herramientas y el razonamiento tienen pruebas independientes: para aparecer en `auto`, el modelo debe contestar correctamente la prueba de razonamiento y superar la prueba exacta de llamada a herramienta. Las capacidades multimedia anunciadas por catálogo se anotan como descubrimientos secundarios, no como adaptadores funcionales.
- Token Harbor consulta el catálogo autenticado de cada cuenta. Solo prueba rutas que esa misma cuenta declara gratuitas (`:free` y precios de entrada y salida en cero); no prueba rutas pagas ni supone que la gratuidad de una cuenta cubra otros modelos. Guarda la cuenta compatible que pasó chat, herramientas y razonamiento. El catálogo secundario se refleja aparte y no prueba por sí solo una operación multimedia.
- APInex consulta su catálogo autenticado, pero el prefijo `free/` por sí solo no basta para hacer una prueba. Solo se envían pruebas de chat, herramientas y razonamiento si el propio catálogo devuelve `is_free=true`, `free=true` o precios explícitos de entrada y salida iguales a cero. Un modelo sin esa evidencia queda registrado como no confirmado y no entra en Auto. Las pruebas siguen siendo solicitudes al proveedor y pueden consumir límites del plan gratuito.
- El ranking global conserva los catálogos de capacidades de Cloudflare y Mistral junto con los de las pasarelas, TokenRouter, xKiro, Token Harbor y Cohere. “Detectado” describe lo anunciado por el catálogo; no acredita por sí solo una operación disponible, una cuenta autorizada ni gratuidad.
- En una actualización general, el ranking global solo incorpora capacidades secundarias de proveedores que terminaron correctamente esa ejecución; si un proveedor falla, no reutiliza su catálogo viejo como si fuera una detección nueva. Una consolidación de diagnóstico sin actualizar puede mostrar la última información guardada y su fecha.
- El router multimedia debe filtrar tareas generativas por adaptadores locales implementados. Hoy generación de imágenes tiene adaptadores para SiliconFlow, Zhipu y Cloudflare; generación de video para SiliconFlow y Zhipu. El resto de las rutas de imagen/video detectadas se conservan como catálogo, pero no se deben poner en ejecución hasta implementar y probar el adaptador correspondiente.
- El normalizador de pasarelas entiende las 24 categorías internas a partir de modalidades, tareas, funciones y `api_formats`; combina varias etiquetas de un mismo modelo y no toma una salida de audio genérica como prueba de TTS. El hallazgo permanece como catálogo secundario hasta verificar acceso y adaptador.
- Si el catálogo no da precio/capacidad suficiente, el programa conserva la incertidumbre y no inventa una etiqueta gratis.
- Los modelos secundarios se guardan por separado para no presentarlos como modelos de chat ni como capacidades ya servidas.

## 7. Privacidad y errores

No publiques `.env`, `granja.env`, `cuentas.json`, las claves ni archivos de ranking de tu instalación. Al pedir ayuda, compartí el nombre del proveedor y el texto del error después de quitar claves, correos, identificadores privados y respuestas con datos sensibles.

Un error `401` o `403` suele indicar clave incorrecta o falta de permiso; `402`, falta de crédito; `429`, límite o cuota; un error de red puede ser temporal. La respuesta final la determina el proveedor. Corregí el problema desde su panel oficial y volvé a probar la cuenta.
