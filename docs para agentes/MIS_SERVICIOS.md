# Mis servicios — Núcleo IA

Asistente visual para conectar los proveedores de Núcleo IA en Windows y Linux. El catálogo base de esta copia tiene **22 fichas generales** y **19 opcionales**, incluida Speechify, que solo sirve para texto a voz (TTS). Cuando un proveedor opcional tiene dos o más cuentas habilitadas, su tarjeta pasa a **Servicios generales** para que sea más fácil encontrarla; GitHub queda excluido. Esto solo cambia su ubicación en pantalla: no activa la cuenta ni confirma que sus modelos sean gratuitos. Cada modelo puede tener un precio distinto y las funciones especiales requieren que exista adaptador y permiso.

Los proveedores opcionales comienzan desactivados. Después de agregar una cuenta, mirá la tarjeta principal y pulsá **Activar proveedor** si querés usarlo. Si también aparecen interruptores para cuentas o capacidades, habilitá únicamente las que necesitás. Activar un proveedor no confirma gratuidad, saldo ni acceso a todos sus modelos.

## Pozo común y Ollama

Los correos conocidos forman un pozo común para todos los proveedores, incluido Ollama. «Vinculado aquí» significa que ese correo ya identifica una cuenta del servicio que estás viendo; «Sin vincular aquí» permite usarlo en ese servicio aunque ya se use en otros.

En Ollama Cloud, el correo queda asociado al ID, puerto e instancia. Si esa cuenta pierde autorización, elegí «Volver a autorizar esta cuenta»: se conserva la instancia y las demás cuentas no se modifican. Un límite de cuota se muestra como espera o reintento y no obliga a volver a cargar todas las cuentas.

## Abrir

**Windows:** doble clic en “Mis servicios — Núcleo IA” en el escritorio, después de ejecutar el instalador. También podés abrir `mis_servicios.vbs` o `mis_servicios.bat` dentro de la carpeta.

**Linux:** elegí “Mis servicios — Núcleo IA” en el menú de aplicaciones, después de ejecutar el instalador. También podés usar `mis_servicios.desktop` en la carpeta. El lanzador `mis_servicios.sh` detecta el entorno: con escritorio abre el navegador; sin escritorio muestra un menú de terminal con los servicios generales disponibles y la conexión secundaria de ElevenLabs (solo TTS).

Necesita Python 3.10 o posterior; los instaladores preparan Python y las dependencias del proxy. La pantalla del asistente usa solo la biblioteca estándar y puede abrirse antes de instalar las dependencias de Núcleo IA. Si falta Python, el lanzador indica el instalador correspondiente. Se abre el navegador predeterminado y un segundo inicio reutiliza el asistente de esa carpeta.

## Tu primera conexión

1. Elegí el servicio exacto que quieras conectar. Los servicios generales y los opcionales se configuran desde esta pantalla; no hace falta agregar todos.
2. Tocá “Tengo cuenta” o “Crear cuenta”. La página oficial se abre aparte.
3. Completá el acceso en esa página y volvé a Mis servicios.
4. Si el servicio usa una clave, copiala completa y pegala. No ingreses tu contraseña en Núcleo IA.
5. Tocá “Comprobar y guardar”.
6. Tocá “Aplicar conexiones”. Inicia el proxy o recarga las cuentas sin reiniciar una versión compatible.

La comprobación consulta la autenticación o el catálogo; no genera conversaciones. Un acceso comprobado no garantiza cuota, saldo, disponibilidad de todos los modelos ni gratuidad. Las comprobaciones también están sujetas a los límites del servicio. Si el catálogo es público, el asistente no lo toma como prueba de una clave válida: muestra “pendiente”.

Las claves rechazadas no se guardan. Si hay un problema temporal o no se puede confirmar el acceso, aparece “Guardar como pendiente”. Esa acción requiere un clic separado. Podés reintentar desde “Ver mis cuentas”.

## Casos especiales

- **Ollama Cloud:** escribí el correo, prepará la conexión, abrí la autorización, elegí “Authorize Device” y volvé a comprobar. Se registra como conectada solo después de confirmar la identidad. Una autorización con otro correo no se considera exitosa. Si falta OpenSSH, se muestra qué componente instalar. Solo hay una preparación pendiente a la vez y se conserva al cerrar la pantalla.
- **Ollama local:** debe estar abierto en el puerto local estándar y tener al menos un modelo instalado. La comprobación no descarga modelos.
- **OpenRouter:** “Conectar desde el navegador” usa OAuth con PKCE S256 y vuelve a esta computadora. La autorización vence y es de un solo uso. Si no se completa, se puede pegar una clave manualmente. Se guarda la clave obtenida por autorización aunque su comprobación posterior esté temporalmente caída, marcándola como pendiente.
- **Cloudflare:** requiere el token para Workers AI y el Account ID. La guía enlaza las instrucciones oficiales.
- **SiliconFlow:** esta integración usa la plataforma internacional `.com`.

### SiliconFlow: cómo obtener una clave que realmente funcione

SiliconFlow suele ser el recorrido más confuso. La cuenta del sitio no es la clave: necesitás crear una API key dentro del panel de la plataforma internacional.

1. Abrí `https://cloud.siliconflow.com` (la plataforma `.cn` es distinta).
2. Iniciá sesión y completá la verificación de correo o teléfono que solicite el sitio.
3. Entrá en **Account / API Keys** y elegí **Create API Key**.
4. Copiá la clave completa en ese momento; normalmente no vuelve a mostrarse.
5. En Mis servicios elegí SiliconFlow, pegá la clave y guardá.
6. Esperá el resultado **Acceso comprobado**. Si queda pendiente, la clave fue guardada pero el servicio no pudo verificarla todavía.

Una clave de otra plataforma, incompleta, revocada, sin saldo o sin permiso para el modelo produce un rechazo aunque el formato parezca correcto. SiliconFlow es necesario actualmente para crear imágenes, crear voz, embeddings y algunas rutas multimodales; si no querés usar esas funciones, podés dejarlo sin configurar.
- **Z.AI:** esta integración usa la API general, no el endpoint del Coding Plan.
- **TokenRouter:** esta integración corresponde a `tokenrouter.com`.
- **Token Harbor:** se mantienen las restricciones a rutas `:free` del proyecto. Se explica la posible retención de contenido antes de conectar.
- **APInex:** pasarela compatible con formato OpenAI. Usá una API key propia de APInex y actualizá su ranking; sus capacidades multimedia dependen de adaptadores comprobados y no se activan solo por aparecer en el catálogo. **Una sola cuenta por IP es la configuración más segura. Si tenés varias cuentas legítimas y APInex permite usarlas, podés configurarlas y rotarlas bajo tu responsabilidad, con moderación.**
- **ElevenLabs (SOLO TTS):** aparece como tarjeta separada porque solo convierte texto en audio. Pegá una API key de ElevenLabs y, si querés dejar una voz predeterminada, su `voice_id`. Esta conexión no habilita chat, imágenes, video ni ranking de modelos.

## Continuar después y ayuda

El botón “Necesito ayuda” explica los pasos y abre la guía del proveedor. Se recuerda el servicio y paso elegidos en esa pestaña; las claves no guardadas se borran al salir del formulario. Después de cerrar una pestaña puede ser necesario elegir el servicio nuevamente. La preparación pendiente de Ollama sí se conserva en la computadora.

Si cerraste el navegador, abrí otra vez el acceso. Si el navegador predeterminado no abre, se intenta mostrar una ventana con una dirección copiable; cuando el sistema no dispone de interfaz gráfica, queda disponible el mensaje del lanzador.

## Datos y alcance

- Claves solo en `.env`, sin incluirlas en respuestas, URLs del asistente, `cuentas.json` o almacenamiento del navegador.
- Metadatos de cuentas en `cuentas.json`; estados de comprobación con fecha, sin afirmar que sean un monitoreo continuo.
- El servidor del asistente escucha exclusivamente en `127.0.0.1`, requiere sesión y valida Host y Origin. No se publica ni se integra al CORS abierto del proxy.
- La recarga del proxy requiere un token local específico de esta carpeta. No cambia la configuración de autenticación, puertos ni exposición del proxy.
- El archivo privado `state/mis_servicios_runtime.json` permite reutilizar la sesión local; no debe compartirse. El exportador no lo copia.
- Al usar “Aplicar conexiones”, los bloqueos por saldo/cuota permanecen. Solo se puede levantar un bloqueo por falta de clave cuando la cuenta tiene acceso comprobado.
- No se actualizan rankings automáticamente: las pruebas de modelos podrían consumir cuota. Desde el Centro de control podés probar un servicio o usar **Actualizar todos**. El panel muestra servicio, modelo, etapa, último avance, errores y permite detener una prueba trabada.

## Validación de esta versión

Pruebas automáticas con datos ficticios para guardado de proveedores, actualización sin duplicación, preservación de configuración, recuperación ante errores de escritura, rechazo de claves, separación de secretos, comprobaciones sin inferencia, OAuth y protección de HTTP local. Se probó en navegador el recorrido de clave incorrecta, corrección, guardado y regreso a la lista.

Los archivos de arranque de Windows están preparados, pero necesitan una prueba real en Windows. Las autorizaciones reales con cada proveedor requieren completar el acceso en su página. La presencia de un enlace o una prueba simulada no equivale a haber creado una cuenta real.

## Referencias de los recorridos

- Ollama: https://docs.ollama.com/cloud
- OpenRouter: https://openrouter.ai/docs/guides/overview/auth/oauth
- Groq: https://console.groq.com/docs/quickstart
- Gemini: https://ai.google.dev/gemini-api/docs/api-key
- Cloudflare: https://developers.cloudflare.com/workers-ai/get-started/rest-api/
- NVIDIA: https://build.nvidia.com/explore
- Cohere: https://docs.cohere.com/docs/get-started-installation
- SiliconFlow: https://docs.siliconflow.com/en/userguide/quickstart
- Z.AI: https://docs.z.ai/api-reference/introduction
- TokenRouter: https://www.tokenrouter.com/docs/tokenrouter-feature-guide/
- xKiro: https://xkiro.com
- Token Harbor: https://tokenharbor.ai/docs/getting-started/quickstart
- ElevenLabs (TTS): https://elevenlabs.io/docs/api-reference/text-to-speech/convert

Las pantallas oficiales pueden cambiar. Sus enlaces, instrucciones y particularidades se mantienen en `scripts/catalogo_servicios.py`, separados del servidor y de la interfaz.

## Servidor sin interfaz gráfica / SSH

Ejecutá `bash agregar_cuentas.sh`. El mismo archivo usa el menú de terminal si no hay `DISPLAY` ni `WAYLAND_DISPLAY`; con escritorio abre el asistente visual. También funciona desde `mis_servicios.sh` o `scripts/agregar_cuentas.sh`.

- Elegí uno de los servicios que muestra el menú o ElevenLabs (marcado **SOLO TTS**). Para salir elegí `0`.
- Para las claves, abrí el enlace oficial en otra computadora y pegá la clave en la terminal del servidor. La entrada se mantiene oculta. Se comprueba antes de guardar; los problemas temporales permiten elegir guardar como pendiente.
- Para Ollama Cloud, seguí el enlace de autorización desde otra computadora y volvé a la terminal. Este modo no intenta abrir un navegador ni copiar al portapapeles del servidor. Ollama y OpenSSH deben estar instalados en el servidor.
- Para OpenRouter, el modo terminal usa una clave manual, evitando redirigir la autorización al localhost de otra computadora.
- Iniciá o reiniciá Núcleo IA después de guardar las cuentas para cargar la configuración.

Podés forzar el menú incluso con escritorio: `bash agregar_cuentas.sh --terminal`. Para forzar el asistente visual: `bash agregar_cuentas.sh --gui`. Los argumentos avanzados `--serve`, `--no-browser` y `--port` conservan el comportamiento del servidor web.

La carga de claves requiere una terminal interactiva: si una sesión SSH no la asigna, usá `ssh -t`. Sin entrada interactiva, el menú termina con una explicación, sin quedar esperando ni leer claves desde una tubería.

## Pasarelas adicionales

Las tarjetas opcionales de la interfaz se describen en `scripts/catalogo_servicios.py`. Cada clave permanece asociada al proveedor exacto y se guarda en `.env`; `cuentas.json` almacena metadatos, nunca el secreto. La guía de configuración paso a paso, requisitos por proveedor, política de gratuidad y lectura de resultados está en [PASARELAS_Y_RANKING_GRATUITO.md](PASARELAS_Y_RANKING_GRATUITO.md). Los créditos de una cuenta no convierten modelos pagados en gratuitos.
