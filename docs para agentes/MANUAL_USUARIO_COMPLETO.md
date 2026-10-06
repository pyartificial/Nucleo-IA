# Manual completo de Núcleo IA

Este manual está escrito para una persona que usa una computadora pero no necesariamente conoce programación, servidores o inteligencia artificial. Podés leerlo desde el principio o buscar en el índice la tarea que necesitás. Cada palabra técnica se explica la primera vez que aparece y también vuelve a aparecer en el glosario.

Núcleo IA funciona como un centro de conexiones. Recibe una petición de una aplicación, elige una cuenta y un modelo disponibles, envía el trabajo y devuelve el resultado. La aplicación puede ser un agente, una interfaz de chat, un programa propio o la demostración incluida. La persona usuaria no tiene que cambiar de proveedor cada vez que una cuenta alcanza su límite: Núcleo IA intenta continuar con otra opción válida.

> Consejo para la primera vez: instalá el programa, conectá un solo servicio, probá una pregunta breve y recién después agregá más cuentas. No es necesario configurar todo para empezar.

## Índice completo

Este índice permite ir directamente a cualquier capítulo. Los enlaces llevan a la sección correspondiente de este mismo manual.

1. [1. Qué es Núcleo IA y para qué sirve](#1-qué-es-núcleo-ia-y-para-qué-sirve)
2. [2. Conceptos básicos antes de instalar](#2-conceptos-básicos-antes-de-instalar)
3. [3. Preparar la computadora](#3-preparar-la-computadora)
4. [4. Instalación en Windows](#4-instalación-en-windows)
5. [5. Instalación en Linux y WSL](#5-instalación-en-linux-y-wsl)
6. [6. Iniciar, detener y comprobar el funcionamiento](#6-iniciar-detener-y-comprobar-el-funcionamiento)
7. [7. Pantalla Mis servicios](#7-pantalla-mis-servicios)
8. [8. Pozo de correos y varias cuentas](#8-pozo-de-correos-y-varias-cuentas)
9. [9. Servicios generales compatibles](#9-servicios-generales-compatibles)
10. [10. Conectar un agente o una aplicación](#10-conectar-un-agente-o-una-aplicación)
11. [11. Cómo elige Núcleo IA una respuesta](#11-cómo-elige-núcleo-ia-una-respuesta)
12. [12. Capacidades multimedia: diferencias importantes](#12-capacidades-multimedia-diferencias-importantes)
13. [13. Analizar imágenes con visión](#13-analizar-imágenes-con-visión)
14. [14. Crear imágenes](#14-crear-imágenes)
15. [15. Edge TTS incluido: voz sin API key](#15-edge-tts-incluido-voz-sin-api-key)
16. [16. Otras opciones de texto a voz](#16-otras-opciones-de-texto-a-voz)
17. [17. Transcribir audio](#17-transcribir-audio)
18. [18. Crear videos](#18-crear-videos)
19. [19. Embeddings y búsqueda por significado](#19-embeddings-y-búsqueda-por-significado)
20. [20. Configuración explicada campo por campo](#20-configuración-explicada-campo-por-campo)
21. [21. Respaldo, restauración y traslado](#21-respaldo-restauración-y-traslado)
22. [22. Uso compartido en una organización](#22-uso-compartido-en-una-organización)
23. [23. Seguridad y privacidad](#23-seguridad-y-privacidad)
24. [24. Diagnóstico de problemas](#24-diagnóstico-de-problemas)
25. [25. Comandos y archivos de uso cotidiano](#25-comandos-y-archivos-de-uso-cotidiano)
26. [26. Recorridos completos de ejemplo](#26-recorridos-completos-de-ejemplo)
27. [27. Glosario explicado](#27-glosario-explicado)
28. [28. Lista final de comprobación](#28-lista-final-de-comprobación)
29. [29. Preguntas frecuentes](#29-preguntas-frecuentes)
30. [30. Autor y contacto](#30-autor-y-contacto)
31. [31. Licencia](#31-licencia)

# 1. Qué es Núcleo IA y para qué sirve

## 1.1 La idea principal

Los servicios de inteligencia artificial ofrecen modelos. Un modelo es el sistema que recibe instrucciones y produce una respuesta. Algunos modelos escriben texto, otros entienden imágenes, otros crean audio, imágenes o videos. Cada servicio tiene su propia cuenta, su propia clave y sus propios límites.

Núcleo IA se coloca entre la aplicación que usás y esos servicios. La aplicación envía todo a una única dirección local: `http://127.0.0.1:8080/v1`. Núcleo IA revisa qué servicio está disponible, qué modelo conviene y qué cuenta todavía puede responder. Después entrega el resultado con un formato compatible con muchas aplicaciones que aceptan una API de tipo OpenAI.

“Compatible con OpenAI” describe el formato de comunicación. No significa que necesites una cuenta de OpenAI ni que las respuestas sean procesadas por OpenAI. El proveedor real puede ser Groq, Google, Ollama, Cloudflare u otro de los servicios conectados.

## 1.2 Qué problemas intenta resolver

- Evita configurar por separado cada servicio dentro de cada agente.
- Puede pasar a otra cuenta cuando aparece un límite temporal.
- Permite elegir una finalidad, como conversación general, razonamiento, herramientas o visión.
- Centraliza la comprobación de cuentas y modelos.
- Conserva estadísticas de funcionamiento para elegir opciones saludables.
- Expone funciones de texto, visión, generación de imágenes, voz, transcripción, video y búsqueda semántica.
- Permite combinar procesamiento local con servicios en Internet.

## 1.3 Qué no hace por sí solo

Núcleo IA no es una ventana de chat completa ni un agente autónomo. Es el motor de conexión que usa otra aplicación. Tampoco crea cuentas automáticamente ni evita las condiciones de cada proveedor. Si un servicio exige registro, verificación, saldo o una cuota activa, esas reglas siguen existiendo.

Una clave guardada no garantiza que todos los modelos sean gratuitos. Un proveedor puede cambiar su catálogo o sus límites. Por eso Núcleo IA comprueba el acceso, registra errores y permite restringir modelos no confirmados como gratuitos.

## 1.4 Uso personal y uso compartido

En una computadora personal, la configuración recomendada escucha solamente en la propia máquina. Esto mantiene el uso sencillo: la aplicación y Núcleo IA están en la misma PC.

Cuando varias personas comparten una instalación se usa el modo Profesional. Ese modo separa la clave de consumo de la clave administrativa. Las cuentas siguen identificadas por sus correos para que el responsable pueda saber cuál debe reparar. No se anonimizan ni se mezclan de manera que impida reconocerlas.

# 2. Conceptos básicos antes de instalar

## 2.1 Carpeta, archivo y extensión

Una carpeta contiene archivos. En Windows, algunos nombres terminan en `.bat`, `.vbs` o `.exe`; son iniciadores que se abren con doble clic. En Linux los iniciadores suelen terminar en `.sh` y se ejecutan desde una terminal. No cambies esos nombres porque otros componentes los buscan exactamente así.

Si descargaste un archivo ZIP, primero extraelo. No ejecutes Núcleo IA dentro del ZIP: en esa situación Windows muestra los archivos, pero los programas no pueden guardar correctamente la configuración.

## 2.2 Terminal

La terminal es una ventana donde se escriben instrucciones. En Windows puede llamarse Símbolo del sistema, CMD, PowerShell o Terminal. En Linux suele llamarse Terminal. No necesitás memorizar comandos: este manual muestra los necesarios completos.

Cuando una instrucción dice “abrí una terminal dentro de la carpeta”, en Windows podés abrir la carpeta, hacer clic en la barra donde aparece la ubicación, escribir `cmd` y presionar Enter. En Linux, normalmente se puede hacer clic derecho dentro de la carpeta y elegir “Abrir en una terminal”.

## 2.3 Cuenta, correo, contraseña y API key

Una cuenta pertenece a un servicio externo. El correo sirve para reconocer qué cuenta estás usando. La contraseña y los códigos de verificación se escriben únicamente en la página oficial del servicio.

Una API key es una clave larga creada por el proveedor para que un programa pueda usar la cuenta. No es necesariamente tu contraseña. Cuando Mis servicios te pide una API key, copiá la clave completa desde el panel oficial y pegala en el campo indicado. No la envíes por chat, correo o capturas de pantalla.

## 2.4 Servicio, proveedor y modelo

En este manual, servicio y proveedor se refieren a la empresa o plataforma que ofrece acceso a modelos. Groq, Google y Cloudflare son ejemplos de proveedores. Un modelo es la inteligencia artificial específica que ejecuta el trabajo. Un proveedor puede ofrecer varios modelos.

## 2.5 Local y cloud

Local significa que el procesamiento ocurre en tu propia computadora. Cloud o nube significa que la información se envía por Internet al proveedor elegido. Ollama puede trabajar localmente y también ofrece cuentas cloud. No confundas Ollama local con Ollama Cloud: usan el mismo ecosistema, pero los datos y los recursos se procesan en lugares diferentes.

# 3. Preparar la computadora

## 3.1 Requisitos generales

Necesitás espacio para la carpeta, Python y sus dependencias. Para servicios cloud necesitás Internet. Para modelos locales, la memoria y la capacidad de la computadora determinan qué modelos pueden funcionar con comodidad.

Guardá la carpeta en un lugar estable, por ejemplo Documentos. Evitá moverla después de crear accesos directos o configurar inicio automático. No la pongas dentro de una carpeta que se sincronice públicamente.

## 3.2 Antes de modificar una instalación existente

Si ya usabas Núcleo IA, hacé un respaldo personal antes de reemplazar archivos. El respaldo conserva cuentas, correos y configuración. Una copia pública exportable no reemplaza al respaldo personal porque se crea sin credenciales.

## 3.3 Antivirus y avisos del sistema

Los iniciadores ejecutan Python y pueden abrir una ventana local en el navegador. Algunos sistemas preguntan si permitís la ejecución. Revisá que el archivo esté dentro de la carpeta de Núcleo IA que descargaste. No desactives el antivirus para instalar. Si un archivo fue bloqueado, revisá el nombre y la ubicación antes de autorizarlo.

# 4. Instalación en Windows

## 4.1 Instalación paso a paso

1. Extraé completamente la carpeta descargada.
2. Abrí la carpeta extraída.
3. Hacé doble clic en `instalar_nucleo_ia.bat`.
4. Esperá mientras se comprueba Python, se crea el entorno y se instalan dependencias.
5. No cierres la ventana mientras muestra tareas en progreso.
6. Cuando aparezca el mensaje de finalización, cerrá la ventana si no se cierra sola.
7. Hacé doble clic en `iniciar_todo.bat` para la primera prueba.
8. Dejá esa ventana abierta mientras usás Núcleo IA.

El entorno virtual llamado `venv` guarda las bibliotecas de Python que necesita el programa. No hace falta abrirlo ni modificarlo.

## 4.2 Confirmar que inició

Abrí el navegador y escribí `http://127.0.0.1:8080/healthz`. Si aparece una respuesta indicando que está saludable, el servidor está funcionando. Después abrí `http://127.0.0.1:8080/readyz`; esta segunda dirección indica si la configuración está lista o si funciona de manera degradada.

Si el navegador dice que no puede conectarse, revisá que la ventana de `iniciar_todo.bat` siga abierta. Si se cerró, abrila de nuevo y leé el último mensaje visible.

## 4.3 Inicio en segundo plano

Después de comprobar que todo funciona, podés iniciar sin una ventana de consola usando `iniciar_segundo_plano.vbs`. Este archivo ejecuta el servidor oculto. Los mensajes de inicio quedan registrados para poder revisarlos si algo falla.

Para iniciar sin mostrar una consola usa `iniciar_segundo_plano.vbs`, después de completar la instalación.

## 4.4 Inicio automático con Windows

Ejecutá `instalar_inicio_automatico.bat` una sola vez. A partir del próximo inicio de sesión, Windows intentará iniciar Núcleo IA para ese usuario. No lo instala como servicio general del equipo y normalmente no requiere permisos de administrador.

Para quitar el inicio automático, ejecutá `desinstalar_inicio_automatico.bat`. Esto solo elimina el arranque automático; no borra el programa, las cuentas ni la configuración.

## 4.5 Detener Núcleo IA

Ejecutá `detener_todo.bat`. Esperá el mensaje de finalización antes de apagar la computadora o reemplazar archivos. Cerrar una ventana puede detener la versión visible, pero el iniciador de segundo plano puede seguir ejecutándose; por eso es mejor usar el archivo de detención.

# 5. Instalación en Linux y WSL

## 5.1 Diferencia entre Linux y WSL

Linux es un sistema operativo. WSL permite usar un entorno Linux dentro de Windows. Los pasos son parecidos, pero en WSL el navegador normalmente se abre del lado de Windows.

## 5.2 Instalación paso a paso

1. Extraé la carpeta.
2. Abrí una terminal dentro de esa carpeta.
3. Ejecutá `bash instalar_nucleo_ia.sh`.
4. Esperá a que se instalen las dependencias.
5. Ejecutá `bash iniciar_todo.sh`.
6. Abrí `http://127.0.0.1:8080/healthz` en el navegador.

Si el instalador informa que falta un paquete del sistema, copiá el mensaje completo. Algunas distribuciones usan nombres diferentes para Python, el entorno virtual o las herramientas de red.

## 5.3 Inicio automático en un escritorio Linux

Ejecutá `bash instalar_inicio_automatico.sh`. Esto crea un inicio automático para tu usuario. Para quitarlo, ejecutá `bash desinstalar_inicio_automatico.sh`.

## 5.4 Detener el sistema

Ejecutá `bash detener_todo.sh`. No borres archivos de estado mientras el servidor está funcionando.

## 5.5 Servidor Linux sin escritorio

Si la computadora no tiene entorno gráfico, `bash agregar_cuentas.sh` abre un menú en la terminal. Elegí el servicio, abrí el enlace oficial desde otra computadora y pegá la clave cuando se solicite. La entrada de la clave se oculta. Para forzar este modo usá `bash agregar_cuentas.sh --terminal`.

Con Ollama Cloud se muestra un enlace y un código de autorización. Abrí el enlace desde una computadora con navegador, completá la autorización y luego regresá a la terminal. Con OpenRouter, el modo terminal usa una clave manual porque una redirección al localhost del servidor no llegaría a tu navegador remoto.

# 6. Iniciar, detener y comprobar el funcionamiento

## 6.1 Tres comprobaciones diferentes

`/healthz` responde si el proceso está vivo. No asegura que exista una cuenta usable.

`/readyz` informa si el sistema está listo o degradado. Degradado significa que el servidor funciona, pero alguna parte de la configuración no está disponible.

`/status` muestra información operativa: cuentas, estados, intentos y disponibilidad. En modo Profesional, esta información requiere la clave administrativa.

## 6.2 La dirección local

`127.0.0.1` significa “esta misma computadora”. El puerto predeterminado es `8080`. La parte `/v1` identifica la interfaz compatible que usan los agentes.

Si cambiás el puerto, también tenés que cambiarlo en cada aplicación conectada. Si una aplicación se ejecuta dentro de Docker, su `127.0.0.1` corresponde al contenedor y no a la computadora anfitriona.

## 6.3 Una prueba sencilla

Con el servidor iniciado, abrí la demostración incluida o configurá una aplicación con:

```
Dirección base: http://127.0.0.1:8080/v1
Clave: local
Modelo: auto
```

Escribí una pregunta breve, por ejemplo: “Respondé únicamente con la palabra FUNCIONA”. Una respuesta correcta demuestra que el cliente llega a Núcleo IA y que al menos una cuenta puede procesar texto.

# 7. Pantalla Mis servicios

## 7.1 Para qué sirve

Mis servicios es el asistente que conecta cuentas y claves. En Windows se abre con `mis_servicios.vbs`, `mis_servicios.bat` o el acceso directo creado por el instalador. En Linux se abre con el acceso del menú o `mis_servicios.sh`.

El catálogo inicial de la pantalla tiene 22 fichas bajo **Servicios generales** y otras 19 bajo **Proveedores opcionales**. Speechify aparece entre las opcionales porque solo ofrece una conexión dedicada de texto a voz (TTS). Si un proveedor opcional tiene dos o más cuentas habilitadas, su tarjeta se muestra en Servicios generales, excepto GitHub. Es solo una regla para encontrar la tarjeta: no activa las cuentas ni garantiza precio cero, acceso a todos los modelos o implementación de toda función anunciada. No necesitás conectarlas todas. Comprobá `http://127.0.0.1:8080/v1/capabilities` y hacé una prueba pequeña antes de depender de una función. ElevenLabs tiene voz con autorización por capacidad.


> Guía detallada para agregar estas pasarelas y actualizar sus modelos: [Pasarelas y modelos gratuitos](PASARELAS_Y_RANKING_GRATUITO.md). La guía explica paso a paso cómo crear una cuenta, cargar una clave, probarla y distinguir una cuota gratuita de un modelo con precio cero.

## 7.2 Primera conexión

1. Elegí un servicio.
2. Pulsá “Tengo cuenta” si ya estás registrado o “Crear cuenta” si todavía no lo estás.
3. Se abre la página oficial en otra pestaña.
4. Iniciá sesión allí. Si el navegador tenía otra cuenta abierta, cerrá esa sesión primero.
5. Creá o copiá la API key cuando corresponda.
6. Volvé a Mis servicios.
7. Escribí el correo que identifica la cuenta.
8. Pegá la clave completa.
9. Pulsá “Comprobar y guardar”.
10. Al regresar a la pantalla principal, pulsá “Aplicar conexiones”.

La contraseña y los códigos de verificación se escriben en la página oficial, nunca en Núcleo IA.

## 7.3 Estados de una cuenta

“Acceso comprobado” significa que el servicio aceptó la autenticación durante la prueba. No significa que todos los modelos tengan cuota.

“Pendiente” significa que la clave se guardó, pero la comprobación no pudo completarse. Puede deberse a una interrupción temporal, a un límite o a que la prueba disponible no permite confirmar toda la cuenta.

“Rechazada” significa que el proveedor no aceptó la clave. Las claves rechazadas no se guardan como válidas.

“Espera” o “límite” significa que la cuenta alcanzó una cuota temporal. Núcleo IA evita insistir continuamente y puede probar otra cuenta.

## 7.4 Aplicar conexiones

Guardar una cuenta modifica la configuración local. “Aplicar conexiones” pide al servidor que vuelva a cargarla. Los bloqueos por saldo o cuota no desaparecen por aplicar nuevamente: se mantienen hasta que el proveedor permita usar la cuenta.



## 7.5 Pasarelas y modelos gratuitos

Esta guía explica cómo añadir las pasarelas compatibles con la API de chat de OpenAI, actualizar sus modelos y entender qué entra en el ranking automático. Está escrita para distinguir tres cosas que suelen confundirse: tener una clave, ver un modelo en un catálogo y poder usarlo gratis.

## 7.5.1 Antes de empezar

Necesitás una conexión a Internet para hablar con proveedores en la nube. Cada proveedor debe darte su propia clave API. La clave es privada: se guarda localmente en `.env` y no se debe enviar por correo, capturas, GitHub o mensajes de soporte.

No todas las cuentas permiten todos los modelos. Un saldo inicial, un crédito promocional, una cuota diaria o un plan gratis de la cuenta **no** significa que cada modelo cueste cero. Revisá las condiciones del servicio antes de activar una cuenta.

## 7.5.2 Pasarelas incluidas

Estas integraciones se administran desde **Mis servicios** y el Centro de control. Agnes AI, Aion Labs, BazaarLink, Hugging Face, Mistral AI, Requesty, SEA-LION y UnoRouter aparecen junto a los servicios generales, no en “Proveedores opcionales”. Esa ubicación solo ayuda a encontrar servicios con API disponible; no quiere decir que cada modelo sea gratis ni que todos tengan el mismo tipo de crédito. No hace falta configurar todas las cuentas.

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
| Ollama Cloud por API key | Catálogo de Ollama Cloud | Es distinto de vincular una instancia con inicio de sesión. Una clave o plan no prueba que cada modelo sea gratis. |
| Mistral AI | Catálogo de modelos y precios | Los modelos pagos no se clasifican como gratis por tener saldo o una prueba de cuenta. |
| TokenRouter | Catálogo mixto con rutas pagas y gratuitas | Solo se prueban rutas que el catálogo marque gratis o cuyos dos precios sean cero; si falla el catálogo, los modelos recordados no se prueban. |

El catálogo del Centro de control indica cómo crear una clave y la dirección oficial correspondiente. Las páginas y condiciones de cada proveedor pueden cambiar; verificá sus precios en su sitio antes de usar modelos.

## 7.5.3 Agregar una cuenta, paso a paso

1. Abrí **Mis servicios** desde el Centro de control.
2. Elegí el proveedor que querés conectar.
3. En otra pestaña, abrí el enlace oficial para crear una clave que muestra su tarjeta. Iniciá sesión en ese proveedor y creá la clave.
4. Copiá la clave API completa. No copies espacios antes o después.
5. Volvé a Núcleo IA, elegí **Agregar cuenta** y pegá la clave en el campo de ese proveedor. Si la interfaz solicita una etiqueta, poné un nombre que te ayude a reconocerla, por ejemplo `cuenta personal`.
6. Guardá la cuenta y revisá el resultado de conexión. Una clave guardada puede aparecer pendiente hasta que ejecutes una comprobación.
7. Si la cuenta no se puede comprobar, revisá que la clave pertenezca al proveedor correcto, que no tenga espacios extra y que la cuenta tenga acceso a la API. No pegues la clave en el mensaje de error.
8. Repetí estos pasos únicamente para las cuentas que quieras usar.

Las claves se asocian a variables locales como `AGNES_API_KEY`, `AION_API_KEY` o `HF_TOKEN`; el programa las administra por cuenta. No edites estas variables manualmente mientras el Centro de control está escribiendo configuración.

## 7.5.4 Actualizar catálogos y rankings

1. Abrí el **Centro de control**.
2. Entrá en **Rankings**.
3. Para una cuenta concreta, elegí **Por servicio**, seleccioná el proveedor y ejecutá **Volver a probar este servicio**.
4. Para hacer la actualización normal completa, elegí **General** y ejecutá la actualización general. Esto consulta proveedores configurados y consolida sus resultados; cada servicio puede tardar o fallar de forma independiente.
5. Esperá a que el proceso termine y leé el resultado de cada etapa. Si aparece un error de clave, cuota o acceso, ese modelo no se debe tratar como verificado.
6. Consultá el ranking general y `/v1/models`. La ruta automática usa los modelos agénticos verificados, no cualquier nombre que aparezca en una página de catálogo.

Las comprobaciones hacen solicitudes a los proveedores usando tus claves. Pueden consumir cuota o saldo según las reglas del servicio; las rutas marcadas como gratis tienen controles para evitar confundir fallbacks pagos con gratuitos, pero revisá siempre los avisos del proveedor. No ejecutes el ranking si no aceptás que se envíen solicitudes de prueba desde tu cuenta.

## 7.5.5 Qué significa cada resultado

- **Encontrado en catálogo**: el proveedor anunció ese identificador o capacidad. No confirma que tu cuenta pueda usarlo.
- **Conexión comprobada**: la cuenta obtuvo una respuesta de chat. No confirma gratuidad.
- **Gratis**: hay evidencia específica de costo cero para el modelo/ruta, según el catálogo o una política explícita documentada en el código.
- **Herramientas comprobadas**: el modelo devolvió la llamada y los argumentos exactos de una función de prueba.
- **Razonamiento comprobado**: respondió correctamente una pregunta determinista de prueba.
- **Apto para agentes**: pasó la prueba de chat y los mínimos de herramientas y razonamiento; si se usa la ruta general gratuita, además tiene que ser gratis y la cuenta debe haberse comprobado.
- **Capacidad secundaria descubierta**: los metadatos del proveedor sugieren una tarea como visión, TTS, transcripción, imagen, video, embeddings, reranking o documentos. Esto es un hallazgo de catálogo, no significa que la operación esté conectada en Núcleo IA.
- **Adaptador implementado y probado**: existe una ruta real de Núcleo IA para esa tarea y se probó con una cuenta/modelo compatible. Revisá `/v1/capabilities`.

El puntaje común ordena modelos que ya pasaron los mínimos. No transforma en gratis un modelo, no concede acceso a la cuenta y no sustituye las condiciones del proveedor.

## 7.5.6 Reglas particulares de las pruebas

- Los gateways con modelos gratis y pagos se filtran por modelo/ruta. Las pruebas no deben lanzar una solicitud a una ruta paga solo porque una cuenta tenga créditos gratis.
- BazaarLink recibe una indicación para no hacer fallback desde gratuito hacia pago.
- DreamPrompting recibe una indicación para no reemplazar el modelo pedido por otro.
- Hugging Face se separa por proveedor de inferencia; dos rutas del mismo modelo pueden tener precios o capacidades distintas.
- OrcaRouter puede ofrecer un alias dinámico `orcarouter/free`; la prueba acepta el modelo que devuelva ese alias dinámico.
- Si el catálogo no da precio/capacidad suficiente, el programa conserva la incertidumbre y no inventa una etiqueta gratis.
- Los modelos secundarios se guardan por separado para no presentarlos como modelos de chat ni como capacidades ya servidas.

## 7.5.7 Privacidad y errores

No publiques `.env`, `granja.env`, `cuentas.json`, las claves ni archivos de ranking de tu instalación. Al pedir ayuda, compartí el nombre del proveedor y el texto del error después de quitar claves, correos, identificadores privados y respuestas con datos sensibles.

Un error `401` o `403` suele indicar clave incorrecta o falta de permiso; `402`, falta de crédito; `429`, límite o cuota; un error de red puede ser temporal. La respuesta final la determina el proveedor. Corregí el problema desde su panel oficial y volvé a probar la cuenta.

# 8. Pozo de correos y varias cuentas

## 8.1 Qué es el pozo de correos

El pozo es una lista común de correos que usás para reconocer tus cuentas. Un mismo correo puede utilizarse en diferentes proveedores. Por ejemplo, podés usarlo en Groq, Google y Ollama.

“Vinculado aquí” significa que ese correo ya identifica una cuenta del servicio que estás mirando. “Sin vincular aquí” significa que el correo está en el pozo, pero todavía puede asignarse a ese servicio.

## 8.2 Por qué se conserva el correo

El correo permite saber exactamente qué cuenta falló. Esto es especialmente importante con varias cuentas de Ollama Cloud: cada una conserva correo, identificador, puerto e instancia. Si una autorización vence, podés reautorizar solo esa cuenta sin adivinar y sin volver a cargar todas.

## 8.3 Agregar varias cuentas

Entrá en el servicio, elegí “Agregar otra cuenta” y verificá que la página oficial esté abierta con el correo correcto. Dos claves creadas desde la misma cuenta no equivalen necesariamente a dos cuotas independientes.

## 8.4 Reparar una cuenta de Ollama

Abrí Ollama dentro de Mis servicios, buscá el correo que muestra el fallo y elegí “Volver a autorizar esta cuenta”. El sistema conserva su identidad y su puerto. No elimines las demás instancias.

Un límite de cuota no siempre requiere reautorización. Si la cuenta sigue autorizada y solo está limitada, esperá el tiempo indicado o dejá que Núcleo IA elija otra opción.

# 9. Servicios generales compatibles

## 9.1 Ollama local y Ollama Cloud

Ollama local ejecuta modelos en tu computadora. Necesita que Ollama esté instalado, abierto y tenga al menos un modelo descargado. No necesita API key para el uso local normal. La velocidad depende del procesador, la memoria y, si existe, la placa gráfica.

Ollama Cloud usa una cuenta autorizada. En Mis servicios escribís el correo, preparás la conexión y seguís la autorización de dispositivo. La cuenta queda asociada a una instancia identificable. Puede ofrecer modelos distintos de los que descargaste localmente.

Elegí Ollama local cuando no querés enviar el contenido a Internet y tu equipo puede ejecutar el modelo. Elegí Ollama Cloud cuando preferís usar recursos remotos y aceptás las condiciones del servicio.

## Cómo conectarlo

Para Ollama local, instalá y abrí Ollama antes de entrar en Mis servicios y comprobá que tenga al menos un modelo descargado. La comprobación no descarga modelos. Para Ollama Cloud, elegí “Vincular Ollama Cloud”, escribí el correo exacto, abrí la autorización y aceptá “Authorize Device”. Volvé a Mis servicios, completá la comprobación y pulsá “Aplicar conexiones”. Si usás varias cuentas, cada una conserva su correo, identificador, puerto e instancia. Si una falla, elegí “Volver a autorizar esta cuenta” para reparar solo esa cuenta.

## 9.2 Groq

Groq ofrece respuestas rápidas y también integra transcripción con Whisper y generación de voz con PlayAI TTS cuando la cuenta y la cuota lo permiten.

Creá una cuenta en el panel de Groq, verificá el correo, generá una API key y pegala en Mis servicios. Una clave válida para chat no garantiza que todos los modelos de audio estén disponibles en tu región o plan.

Groq es necesario para la transcripción integrada de MP3, WAV u OGG. Para texto a voz no es obligatorio porque Edge TTS funciona sin clave.

## Cómo conectarlo

Desde la tarjeta de Groq, creá la cuenta o iniciá sesión y confirmá el correo. Entrá en API Keys, generá una clave y copiala completa. En Mis servicios escribí el correo asociado, pegá la clave y pulsá “Comprobar y guardar”. Aplicá las conexiones y probá primero un chat breve. Para transcripción adjuntá un audio corto; para PlayAI TTS indicá `provider=groq`. Que el chat funcione no garantiza que el modelo de audio tenga cuota.

## 9.3 Google Gemini

Google ofrece modelos Gemini y otros modelos publicados en AI Studio. Se necesita una API key creada desde la cuenta correcta. Si usás varios correos de Google, mirá el avatar y comprobá cuál está activo antes de crear la clave.

Google puede aportar conversación, razonamiento y visión cuando el catálogo y la cuenta incluyen un modelo compatible. Tener una clave de Google no activa automáticamente generación de imágenes o video dentro de Núcleo IA; cada capacidad necesita una adaptación específica.

## Cómo conectarlo

Elegí Google, abrí AI Studio y verificá el avatar para confirmar el correo activo. Generá una API key con esa cuenta, copiala y regresá al asistente. Pegá la clave, escribí el mismo correo, guardá y aplicá. Probá `auto` para texto y `vision` para imágenes. Si un modelo concreto falla aunque la clave sea válida, actualizá el ranking porque el catálogo puede haber cambiado.

## 9.4 OpenRouter

OpenRouter reúne modelos de diferentes orígenes detrás de una sola cuenta. Mis servicios puede conectarlo mediante el navegador o mediante una clave manual. La autorización del navegador regresa a la misma computadora y vence si no se completa a tiempo.

OpenRouter tiene modelos gratuitos, pagos y modelos con condiciones diferentes. Núcleo IA filtra las rutas según la configuración, pero conviene revisar el nombre completo y las condiciones de cada modelo.

## Cómo conectarlo

Usá “Conectar desde el navegador”, aceptá la autorización y permití el regreso a la computadora local. Es temporal y de un solo uso. También podés crear una API key manual y pegarla. Revisá saldo y límites. Si `SOLO_MODELOS_GRATUITOS=true`, las rutas sin evidencia suficiente quedan fuera.

## 9.5 NVIDIA NIM

NVIDIA ofrece modelos alojados y optimizados. Para usarlo se crea una API key en NVIDIA Build. Algunas altas pueden pedir verificación telefónica. Una cuenta y un número de teléfono no deben darse por disponibles para crear cantidades ilimitadas de cuentas.

NVIDIA puede aportar texto, razonamiento, herramientas o visión según los modelos que la cuenta tenga disponibles.

## Cómo conectarlo

Abrí NVIDIA Build con el correo correcto, completá la verificación, generá una API key y copiala. En Mis servicios pegala junto con el correo, comprobá, guardá y aplicá. Probá texto antes de visión o herramientas. Algunas cuentas piden un número de teléfono; una verificación no garantiza una cantidad ilimitada de cuentas.

## 9.6 Cloudflare Workers AI

Cloudflare necesita dos datos: Account ID y un token con permiso para Workers AI. El Account ID identifica la cuenta; el token autoriza la operación. Si falta cualquiera de los dos, la conexión no funciona.

Cloudflare puede participar en chat y visión con modelos compatibles. La creación de imágenes está adaptada mediante un modelo Flux de Workers AI. La cuenta necesita cuota activa para esa operación.

## Cómo conectarlo

En la tarjeta de Cloudflare completá dos campos: Account ID y token. El Account ID aparece en los detalles de la cuenta y no es el nombre del sitio. El token debe tener permiso para Workers AI. Guardá y aplicá. Para imágenes indicá `provider=cloudflare`. Si aparece un error de cuota, revisá la cuenta antes de crear otro token.

## 9.7 Cohere

Cohere ofrece modelos de texto, clasificación, razonamiento y herramientas según su catálogo. Creá una API key en su panel y comprobala desde Mis servicios.

La presencia de modelos especializados no significa que todas las capacidades multimedia estén conectadas. Núcleo IA los usa en las rutas para las que fueron probados.

## Cómo conectarlo

Iniciá sesión en Cohere, abrí la sección de claves y generá una API key. Copiala antes de cerrar la pantalla. En Mis servicios elegí Cohere, escribí el correo, pegá la clave, comprobá, guardá y aplicá. Si fallan herramientas, revisá que el modelo publicado figure como apto; la clave puede seguir siendo válida.

## 9.8 SiliconFlow

La integración usa la plataforma internacional de SiliconFlow. Una cuenta del sitio no es suficiente: hay que crear una API key dentro del panel, completar las verificaciones que pida el servicio y copiar la clave completa.

SiliconFlow está integrado para conversación, generación de imágenes con FLUX, voz con CosyVoice y embeddings con BGE-M3. Esas funciones requieren una clave válida y cuota. Edge TTS permite generar voz sin SiliconFlow.

Si una clave parece correcta pero se rechaza, comprobá que pertenezca a la plataforma internacional, que no esté incompleta, revocada o sin saldo y que tenga permiso para el modelo elegido.

## Cómo conectarlo

Abrí `cloud.siliconflow.com`, completá las verificaciones, entrá en Account o API Keys, creá una clave y copiala completa. En Mis servicios pegala, escribí el correo y esperá “Acceso comprobado”. Probá por separado texto, FLUX, CosyVoice y BGE-M3 porque sus cuotas pueden ser diferentes. Si solo querés voz sin clave, usá Edge TTS.

## 9.9 Zhipu o Z.AI

Zhipu ofrece modelos de texto y capacidades como CogView para imágenes y CogVideoX para video. La integración utiliza la API general; una suscripción de otro producto o plan de programación no necesariamente sirve para esta API.

La creación de video usa `CogVideoX-Flash` como opción predeterminada. Se necesita una API key con cuota disponible. El servicio puede responder con un identificador de tarea antes de que el video esté terminado.

## Cómo conectarlo

Abrí el panel general de Z.AI, generá una API key para la API general y copiala. En Mis servicios escribí el correo, pegá la clave, comprobá y aplicá. Usá `provider=zhipu` para imagen y `/v1/crear-video` para video. Si recibís un identificador de tarea, guardalo: significa que el proveedor está procesando el trabajo.

## 9.10 TokenRouter

TokenRouter funciona como una pasarela compatible con el formato OpenAI. Se usa una API key de su servicio. El catálogo contiene rutas gratuitas y pagas. Núcleo IA consulta las cuentas de TokenRouter configuradas, filtra primero las rutas que tienen evidencia explícita de precio cero y prueba cada ruta solamente con las cuentas que la anuncian como gratuita. No prueba rutas pagas ni supone que un crédito de cuenta vuelva gratis a un modelo. Si no puede consultar el catálogo, no envía pruebas a identificadores guardados de una ejecución anterior. Para entrar en **Auto**, una ruta gratuita debe responder al chat y superar las pruebas de herramientas y razonamiento con la cuenta que luego se usará para atenderla.

## Cómo conectarlo

Entrá en `tokenrouter.com`, generá la clave de ese servicio y copiala. En Mis servicios seleccioná TokenRouter, escribí el correo, pegá la clave y aplicá. En el Centro de control abrí **Rankings → Por servicio → TokenRouter** y volvé a probarlo. El resultado muestra las rutas gratuitas que el catálogo actual anuncia y que respondieron a las comprobaciones. Para incorporarlas al orden común, actualizá **Rankings → General**. Una clave de otra plataforma con nombre parecido no sirve.

## 9.11 xKiro

xKiro también ofrece una interfaz compatible. Núcleo IA considera como gratuitas solamente las rutas cuya condición gratuita pudo comprobarse mediante catálogo, cuota y prueba real. Si el proveedor cambia una condición, el modelo puede dejar de participar hasta una nueva comprobación.

## Cómo conectarlo

Creá una clave en xKiro, registrá el correo en Mis servicios y aplicá las conexiones. Actualizá el ranking: Núcleo IA debe comprobar el catálogo, la cuota y una prueba real. Una ruta no se considera gratuita solo por llevar una etiqueta `free`.

Si agregaste más de una cuenta xKiro, el ranking las consulta una por una y guarda cuál cuenta respondió a cada modelo. Una cuota agotada no debe hacer que el ranking presente esa cuenta como utilizable. Para que una ruta aparezca en **Auto**, además del chat debe aprobar una prueba exacta de herramientas y una pregunta de razonamiento. Si el catálogo menciona visión, audio u otra capacidad secundaria, eso solo indica que el proveedor la anuncia; no quiere decir que Núcleo IA ya pueda realizar esa operación con ese modelo.

## 9.12 Token Harbor

Token Harbor se integra con rutas marcadas como gratuitas. Algunas rutas pueden conservar prompts y respuestas según las condiciones del servicio. Leé el aviso de Mis servicios antes de conectarlo y no envíes contenido confidencial si esas condiciones no son apropiadas para tu caso.

## Cómo conectarlo

Leé primero el aviso de retención de contenido. Si aceptás las condiciones, generá una API key, pegala en Mis servicios, comprobá y aplicá. Núcleo IA limita la integración a rutas `:free` comprobadas; el servicio puede aparecer conectado y no participar si ninguna ruta supera la comprobación.

Si guardaste varias cuentas Token Harbor, Núcleo IA revisa el catálogo de cada una y solo prueba los modelos que esa misma cuenta anuncia como gratuitos, con las dos tarifas en cero. El modelo se vincula con la cuenta que realmente pasó las pruebas; tener varias cuentas no vuelve gratuita una ruta paga. La ruta debe superar chat, herramientas y razonamiento para entrar en **Auto**. Las capacidades secundarias que el catálogo anuncie se muestran como información y necesitan una integración específica para estar disponibles en uso real.

## 9.13 APInex

APInex es una pasarela compatible con el formato OpenAI que reúne rutas de distintos proveedores. Núcleo IA la trata como un servicio independiente: una ruta de APInex tiene su propia salud, modelo, cuota y posición en el ranking. El nombre del modelo no alcanza para saber qué proveedor responderá detrás; por eso conviene actualizar su ranking después de conectarlo.

**Precaución por IP:** APInex suele limitar o vigilar el uso de varias cuentas desde una misma dirección IP. Una sola cuenta por IP es la configuración más segura. Si tenés varias cuentas legítimas y APInex permite usarlas, podés configurarlas y rotarlas bajo tu responsabilidad; hacelo con moderación porque puede provocar bloqueos, limitar los tokens gratuitos o hacer que las cuentas dejen de responder.

APInex puede aportar conversación y, según el catálogo activo, razonamiento, herramientas o visión. No se habilitan automáticamente imágenes, voz, transcripción o video solo porque una ruta de APInex los anuncie: esas capacidades requieren una adaptación comprobada en Núcleo IA.

**Cómo decide Núcleo IA si una ruta es gratuita:** no alcanza con que el nombre empiece con `free/`. El catálogo autenticado de APInex debe declarar `is_free` o `free`, o informar precio cero tanto para entrada como para salida. Si el catálogo no trae esa evidencia, Núcleo IA no envía pruebas a esa ruta ni la incorpora como gratuita. Cuando sí hay evidencia, las pruebas de chat, herramientas y razonamiento envían solicitudes reales y pueden consumir la cuota gratuita disponible.

### Cómo conectarlo

1. Entrá en el panel oficial de APInex e iniciá sesión con el correo que querés conservar como identificador.
2. Creá una API key para la API compatible y copiá el valor completo una sola vez.
3. En **Mis servicios**, elegí APInex, escribí el correo de esa cuenta y pegá la clave.
4. Pulsá **Comprobar y guardar** y después **Aplicar conexiones**.
5. Abrí **Rankings**, elegí **Por servicio → APInex** y pulsá **Volver a probar este servicio**.

Si la clave se acepta pero el ranking queda vacío, el catálogo puede no estar disponible para esa cuenta o sus rutas pueden no responder. No copies una clave de otro agregador con un nombre parecido.

### GitHub Models: servicio retirado

GitHub Models ya no ofrece su catálogo ni su API de inferencia desde el **30 de julio de 2026**. Por eso Núcleo IA no lo agrega como proveedor de modelos y no usa tokens personales de GitHub como claves de inferencia. GitHub Copilot es un producto distinto y no equivale a una API compatible para esta aplicación. Podés conservar un token de GitHub para las tareas propias de GitHub, pero no lo cargues como una cuenta de modelos. [Aviso oficial de GitHub](https://docs.github.com/en/github-models).

## 9.14 Agnes AI

Agnes AI es una pasarela compatible con OpenAI. Núcleo IA consulta el catálogo de la cuenta y distingue rutas gratuitas de rutas pagas. La lista de modelos puede cambiar con el tiempo.

### Cómo conectarlo

1. En **Mis servicios**, elegí **Agnes AI** y abrí el enlace del panel que muestra la tarjeta.
2. Iniciá sesión o creá tu cuenta en el sitio oficial. En la sección de claves API, generá una clave nueva.
3. Copiá la clave completa y volvé a Núcleo IA. Escribí el correo de esa cuenta, pegá la clave y elegí **Comprobar y guardar**.
4. Elegí **Aplicar conexiones**. Después abrí **Rankings → Por servicio → Agnes AI** y ejecutá **Volver a probar este servicio**.
5. Revisá el precio publicado de cada ruta. No supongas que una ruta es gratis si no aparece como gratis en el catálogo; las pruebas usan la API de tu cuenta y pueden consumir sus límites.

## 9.15 Aion Labs

Aion Labs ofrece una API compatible con OpenAI. Un crédito inicial o promocional permite probar el servicio, pero no vuelve gratuito a cada modelo. El catálogo y el precio se revisan modelo por modelo.

### Cómo conectarlo

1. En **Mis servicios**, elegí **Aion Labs** y abrí su panel oficial.
2. Iniciá sesión o registrate. Desde el panel creá una API key.
3. Copiala, volvé a Núcleo IA, indicá el correo de la cuenta y pegá la clave en el formulario de Aion Labs.
4. Elegí **Comprobar y guardar** y luego **Aplicar conexiones**.
5. En **Rankings → Por servicio → Aion Labs**, volvé a probar el servicio y revisá la tarifa de cada modelo antes de solicitarlo. Un saldo promocional puede agotarse.

## 9.16 BazaarLink

BazaarLink es una pasarela con rutas gratuitas y pagas. Núcleo IA solicita que la prueba no cambie automáticamente una ruta gratuita por una paga si se agota la cuota gratuita.

### Cómo conectarlo

1. En **Mis servicios**, elegí **BazaarLink** y abrí su página oficial.
2. Iniciá sesión o creá la cuenta y generá una API key desde el panel.
3. Copiá la clave completa. Volvé a Núcleo IA, agregá la cuenta de BazaarLink y pegá la clave.
4. Elegí **Comprobar y guardar**, después **Aplicar conexiones**.
5. Abrí **Rankings → Por servicio → BazaarLink** y ejecutá una nueva prueba. Comprueba que la ruta esté marcada gratuita en el catálogo actual; la cuota y disponibilidad pueden cambiar.

## 9.17 Hugging Face Inference Providers

Hugging Face enruta modelos a diferentes proveedores de inferencia. El mismo modelo puede tener rutas con precio, disponibilidad o capacidades distintas. El crédito mensual de una cuenta no significa que todas las rutas cuesten cero.

### Cómo conectarlo

1. Iniciá sesión en Hugging Face y abrí **Settings → Access Tokens**.
2. Creá un token con permiso de uso de Inference Providers. Copialo cuando aparezca.
3. En Núcleo IA, elegí **Hugging Face Inference Providers**, pegá el token, indicá el correo de la cuenta y elegí **Comprobar y guardar**.
4. Elegí **Aplicar conexiones** y luego **Rankings → Por servicio → Hugging Face** para actualizar sus modelos.
5. Revisá el proveedor de inferencia y los dos precios de la ruta concreta. No confundas el crédito de la cuenta con una tarifa cero.

## 9.18 Mistral AI

Mistral AI ofrece sus modelos mediante una API compatible con OpenAI. La clave de API se crea en Mistral AI Studio; una cuenta del chat de Mistral no reemplaza esa clave. Los precios y modelos disponibles dependen de la cuenta y pueden cambiar.

### Cómo conectarlo

1. En **Mis servicios**, elegí **Mistral AI** y abrí Mistral AI Studio.
2. Iniciá sesión o registrate. Abrí la sección **API Keys** y creá una clave.
3. Copiá la clave y volvé a Núcleo IA. Pegala en el formulario de Mistral AI e indicá el correo correspondiente.
4. Elegí **Comprobar y guardar** y después **Aplicar conexiones**.
5. Actualizá **Rankings → Por servicio → Mistral AI**. Antes de usar un modelo, mirá sus precios y la cuota disponible de tu cuenta.

## 9.19 Requesty

Requesty es un enrutador compatible con OpenAI. El plan puede incluir una cantidad de solicitudes sin cargo, pero eso no convierte en gratuitos todos los modelos disponibles. Núcleo IA revisa las señales de precio del modelo.

### Cómo conectarlo

1. En **Mis servicios**, elegí **Requesty** y abrí el sitio o la documentación oficial.
2. Iniciá sesión o registrate y genera una API key desde tu cuenta.
3. Copiala completa. Regresá a Núcleo IA, elegí **Agregar cuenta**, indicá el correo y pegá la clave.
4. Elegí **Comprobar y guardar** y **Aplicar conexiones**.
5. Desde **Rankings → Por servicio → Requesty**, probá las rutas publicadas. Revisa tanto el precio del modelo como los límites diarios del plan.

## 9.20 SEA-LION API

SEA-LION ofrece una API compatible con OpenAI y puede proporcionar una clave de prueba. Que la cuenta tenga solicitudes de prueba no demuestra que todos sus modelos tengan precio cero.

### Cómo conectarlo

1. En **Mis servicios**, elegí **SEA-LION API** y abrí SEA-LION Playground.
2. Iniciá sesión, creá una **Trial API Key** (clave de prueba) y copiala.
3. Volvé a Núcleo IA, agregá la cuenta SEA-LION, indicá el correo y pegá la clave.
4. Elegí **Comprobar y guardar**, luego **Aplicar conexiones**.
5. En **Rankings → Por servicio → SEA-LION**, vuelve a probar. Revisa el costo publicado y los límites de la cuenta antes de utilizar modelos.

## 9.21 UnoRouter

UnoRouter es un enrutador compatible con OpenAI. Su catálogo puede publicar variantes gratuitas para modelos concretos; esa condición se verifica por ruta y puede cambiar.

### Cómo conectarlo

1. En **Mis servicios**, elegí **UnoRouter** y abrí su sitio oficial.
2. Iniciá sesión o creá la cuenta. En el panel generá una API key.
3. Copiá la clave completa y regresá a Núcleo IA. Agregá la cuenta UnoRouter, indicá el correo y pegá la clave.
4. Elegí **Comprobar y guardar** y después **Aplicar conexiones**.
5. Ejecutá **Rankings → Por servicio → UnoRouter** para consultar el catálogo reciente. Solo tratá una variante como gratuita si el catálogo actual la identifica así o informa precios cero.

## 9.22 Cuántos servicios conviene conectar

Para comenzar alcanza uno. Los servicios generales pueden aparecer junto a los proveedores especializados, pero algunos tienen precios o créditos distintos. Conectar varios mejora la posibilidad de continuar cuando una cuota se agota, pero también aumenta la cantidad de cuentas que debés cuidar. Agregá un servicio cuando entiendas para qué lo necesitás.

## 9.23 Proveedores y capacidades opcionales

La sección **Proveedores opcionales** reúne conexiones que no están en la lista principal de servicios: Speechify (solo texto a voz), Airforce API, AnyAPI.ai, DreamPrompting, OrcaRouter, Routeway, Ollama Cloud · API key, Cerebras, OpenAI, Anthropic, DeepSeek, Grok/xAI, MiniMax y Alibaba/Qwen. También muestra proveedores especiales de música como Treblo · música, Stable Audio · música, Mubert · música, Soundraw · música y Beatoven · música. Algunas de estas opciones pueden no tener una cuenta gratuita o no contar todavía con todas sus funciones adaptadas en Núcleo IA.

1. Abrí **Mis servicios** y localizá **Proveedores opcionales**. Elegí el nombre exacto: Speechify, Airforce API, AnyAPI.ai, DreamPrompting, OrcaRouter, Routeway, Ollama Cloud · API key, Cerebras, OpenAI, Anthropic, DeepSeek, Grok/xAI, MiniMax, Alibaba/Qwen, Treblo · música, Stable Audio · música, Mubert · música, Soundraw · música o Beatoven · música.
2. Abrí **Necesito ayuda** en la tarjeta elegida y revisá sus pasos y enlaces oficiales. Creá una clave en el panel del servicio; no reutilices una clave de otra plataforma ni escribas tu contraseña de cuenta en Núcleo IA.
3. Volvé a la tarjeta, indicá el correo si te lo pide y pegá la API key en el campo indicado. Elegí **Comprobar y guardar**. Si la comprobación falla, revisá el mensaje y la página oficial antes de decidir si guardás la cuenta pendiente.
4. En la tarjeta, si aparece **Activar proveedor**, pulsalo. Algunos proveedores también muestran interruptores para habilitar una cuenta o una capacidad; activá solo lo que quieras usar. Los proveedores opcionales empiezan desactivados. Esta acción no confirma que haya cuota gratuita ni habilita automáticamente todas las capacidades.
5. Elegí **Aplicar conexiones**. Para proveedores de chat, actualizá su vista individual en **Rankings → Por servicio** y revisá el costo de cada modelo.
6. Para proveedores de música, abrí `/v1/capabilities`: el catálogo puede mostrar opciones cuya función real todavía no está conectada. En esta versión la ruta de música es un simulador y no devuelve audio real.

Speechify solo ofrece texto a voz: no lo uses como modelo de chat ni esperes que aparezca en el ranking general. Para generar voz, la cuenta debe tener permiso y cuota; en la solicitud se indica un `voice_id`. Consultá el apartado **16.1, Speechify como proveedor de voz**, para ver los pasos y el ejemplo completos.

Una opción marcada como opcional no es necesaria para comenzar. La etiqueta tampoco significa que todo lo que ofrece sea pago; consulta el precio y las funciones concretas en la página del servicio y en la salida de `/v1/capabilities`.

# 10. Conectar un agente o una aplicación

## 10.1 Los tres datos básicos

Buscá en la aplicación una opción llamada “OpenAI compatible”, “Custom OpenAI”, “Custom endpoint” o “Proveedor personalizado”. Completá:

```
Base URL: http://127.0.0.1:8080/v1
API key: local
Model: auto
```

La palabra `local` funciona como valor de compatibilidad cuando la autenticación está desactivada. Si activaste autenticación, usá la clave definida como `NUCLEO_API_KEY`.

## 10.2 Qué modelo elegir

`auto` es la opción recomendada para empezar. No es un modelo único: es una ruta lógica que elige una opción disponible.

`cheap` prioriza modelos ligeros o de menor costo.

`reasoning` busca modelos adecuados para problemas que requieren varios pasos.

`tools` busca modelos probados para llamar herramientas o funciones.

`vision` busca modelos capaces de recibir imágenes.

## 10.3 Prueba inicial

Guardá la configuración, comenzá una conversación nueva y pedí una respuesta corta. Si funciona, recién después probá herramientas, imágenes o conversaciones largas. Esto permite distinguir un problema de conexión de un problema específico de capacidad.

## 10.4 Herramientas y agentes

Una herramienta es una acción que la aplicación pone a disposición del modelo, por ejemplo leer un archivo, consultar una base o ejecutar una función. Núcleo IA transporta la definición de las herramientas y elige un modelo compatible, pero la aplicación decide si ejecuta la acción y qué permisos concede.

Elegir `tools` no instala herramientas ni da acceso automático a la computadora. Solo selecciona modelos que demostraron comprender ese formato.

## 10.5 Conversaciones largas

Una conversación ocupa contexto. El contexto incluye instrucciones, mensajes anteriores, resultados de herramientas y documentos adjuntos. Cuando se vuelve muy grande, el proveedor puede rechazarla o recortar contenido. Creá una conversación nueva cuando el tema haya cambiado o cuando la aplicación empiece a perder detalles importantes.

# 11. Cómo elige Núcleo IA una respuesta

## 11.1 Ranking

El ranking ordena modelos mediante pruebas de disponibilidad, velocidad, calidad, uso de herramientas, seguimiento de instrucciones, contexto y capacidades multimodales. No afirma que un modelo sea el mejor para todas las personas. Es una guía operativa para elegir entre opciones que realmente responden.

## 11.2 Rotación y failover

Rotación significa repartir solicitudes entre opciones. Failover significa pasar a otra cuenta o proveedor cuando aparece un fallo. Núcleo IA registra errores temporales y evita repetir de inmediato una opción limitada.

Un error 429 suele representar demasiadas solicitudes o cuota temporal. Un error 402 suele indicar falta de crédito. Un error 403 puede indicar permisos, política o modelo no autorizado. Los errores de red y algunos errores 5xx se consideran transitorios.

## 11.3 Servicios principales y secundarios

Un servicio o modelo principal aprobó las pruebas necesarias para la ruta. Uno secundario puede responder texto, pero no alcanzó todos los mínimos para desplazar automáticamente a una opción principal en herramientas, razonamiento o visión.

Secundario no significa inútil. Sirve como respaldo y puede elegirse de forma explícita si conocés su identificador. Para volver a la selección automática, elegí `auto`.

## 11.4 Actualizar el ranking

En Windows ejecutá `actualizar_rankings.bat`. En Linux ejecutá `bash actualizar_rankings.sh`. También podés usar `python granja.py rank`.

La actualización consulta catálogos y realiza pruebas que pueden consumir cuota. No es necesario ejecutarla después de cada conversación. Conviene hacerlo después de agregar servicios, cuando cambian muchos modelos o cuando el ranking contiene opciones que ya no responden.

Una copia exportable nueva puede traer catálogos de referencia para que el programa tenga datos base. En **Ranking general** no se muestran como resultados de esta computadora: conectá tus cuentas y ejecutá un escaneo completo con **Actualizar todos**, `actualizar_rankings.bat` / `actualizar_rankings.sh` o `python granja.py rank`. El ranking aparecerá cuando se hayan actualizado correctamente los proveedores que tienen cuentas en esta instalación.

En una actualización general, las capacidades especiales también se refrescan solo desde proveedores que terminaron bien en esa ejecución. Si uno falla, no se presenta su catálogo anterior como si acabara de descubrirse. Una consolidación de diagnóstico sin actualizar puede seguir mostrando la última información guardada.

## 11.5 Centro de control y pestaña Rankings

El **Centro de control** reúne el estado del servidor, las cuentas utilizables, las capacidades detectadas y los rankings. Se abre con `centro_control.bat`, `centro_control.vbs`, `centro_control.sh` o el acceso gráfico que instala Núcleo IA. Dentro del Centro de control, la pestaña **Rankings** permite cambiar el orden sin editar archivos.

El Resumen muestra modelos con actividad observada en esta instalación. Los rankings precargados sirven como catálogo y no se presentan como modelos disponibles hasta que una cuenta local haya intentado usarlos. El panel también confirma que el proxy pertenece a esta carpeta antes de mostrar su estado; así no mezcla la actividad de otra copia que use el mismo puerto.

La pantalla tiene tres vistas:

- **General:** modelos principales que usan los agentes cuando elegís `auto`, `tools`, `reasoning` o una ruta equivalente.
- **Por servicio:** una subpestaña para cada proveedor. Sirve para revisar qué modelos de una plataforma están realmente disponibles.
- **Capacidades especiales:** voz, imágenes, video, visión, transcripción, embeddings y otros modelos secundarios. El orden de esta vista se usa cuando una aplicación pide explícitamente esa capacidad.

El catálogo global reúne también las capacidades secundarias anunciadas en los catálogos de Cloudflare, Mistral y las pasarelas compatibles. Una tarjeta puede decir que la capacidad fue detectada por el catálogo sin que eso pruebe el adaptador, el acceso de tu cuenta o que sea gratis; mirá sus indicadores de prueba antes de enviar trabajo real.

La capacidad **Texto a voz** también puede mostrar Speechify como proveedor dedicado, con el modelo **simba-3.2**, cuando la cuenta Speechify está verificada y habilitada para síntesis. No es un modelo de chat. La disponibilidad de la voz y la cuota se comprueban al generar el audio.

Algunas etiquetas se parecen pero no significan lo mismo: salida de audio no necesariamente significa que el modelo convierta texto a voz; comprender una imagen no es crearla; y una modalidad anunciada no garantiza que tu cuenta tenga permiso. El catálogo separa las tareas anunciadas para que puedas reconocerlas sin confundirlas con funciones disponibles.

Para crear imágenes, el programa solo intenta servicios con adaptador local: SiliconFlow, Zhipu y Cloudflare. Para crear video, usa SiliconFlow o Zhipu. Si otro proveedor anuncia generación de imágenes o video, Núcleo IA lo puede mostrar como descubrimiento de catálogo, pero no lo intenta hasta incorporar y comprobar su adaptador. Así una ruta no aparece como utilizable solo porque el modelo figure en el catálogo del proveedor.

Cada bloque de modelo muestra el puesto, el nombre, el proveedor, tamaño aproximado, contexto, estado, capacidades, última prueba y una lista de cuentas compatibles. **Automática: N cuentas disponibles** significa que Núcleo IA puede probar esas cuentas según la rotación. Si elegís un correo en **Cuenta preferida**, esa cuenta se intenta primero para ese modelo; las demás siguen disponibles como respaldo.

Para mover un modelo, mantené presionado el símbolo de arrastre y llevá el bloque hacia arriba o abajo. También podés usar **Subir** y **Bajar**. Después pulsá **Guardar cambios**. Mover un modelo no cambia su capacidad ni crea una cuenta: solo cambia el orden en que se lo intenta.

## 11.6 Qué significa el indicador de actividad

Cuando pulsás **Volver a probar este servicio** o **Actualizar todos**, aparece un panel de actividad encima del ranking. El ranking anterior sigue visible mientras se realizan las pruebas; esto evita que una comprobación parcial deje al agente sin una ruta conocida.

El panel informa:

1. **Estado:** trabajando, comprobación terminada, comprobación con errores o detenida.
2. **Servicio actual:** el proveedor que se está consultando en ese momento.
3. **Modelo actual:** aparece cuando el comprobador informa qué modelo está probando.
4. **Etapa:** por ejemplo, preparación, catálogo, prueba de respuestas o finalización.
5. **Avance:** en una actualización total muestra cuántos servicios terminaron y cuántos faltan.
6. **Último evento:** el último mensaje recibido del comprobador, útil para saber que sigue trabajando aunque tarde.
7. **Tiempo:** cuánto lleva abierta la comprobación.
8. **Detalle:** una lista desplegable con cada servicio y su resultado.

**Actualizar todos** y **Actualizar ranking general** ejecutan la misma revisión integral: el ranking global consulta cada proveedor una sola vez y arma el ranking con los resultados válidos de esa ejecución. La lista de avance muestra qué proveedores ya terminaron. Puede tardar bastante más que una prueba individual y algunas cuentas pueden consumir cuota. No cierres el navegador durante la comprobación: podés cambiar de pestaña, pero el servidor debe seguir iniciado.

Si necesitás detenerla, pulsá **Detener pruebas**. La solicitud de detención termina el proceso activo y conserva el ranking anterior. Si no se reciben avances durante aproximadamente un minuto y medio, el indicador muestra **Sin avances recientes**; después de dos minutos el sistema marca la prueba como detenida para evitar que quede bloqueada indefinidamente. Una prueba lenta no significa necesariamente que el proveedor esté caído: revisá el último evento y el servicio actual antes de volver a iniciarla.

Si una actualización integral termina parcialmente, el panel marca cada proveedor que falló y esos datos viejos no se incorporan como si fueran una comprobación nueva. Los proveedores que sí terminaron correctamente pueden actualizar el ranking general. Podés corregir la cuenta desde **Mis servicios** y volver a revisar solo ese proveedor. Si elegís **Restaurar automático**, se quita únicamente el orden manual de la vista seleccionada; no se borran cuentas ni rankings guardados.

## 11.7 Cómo elegir la rotación general

La rotación se configura solo en la vista **General**. **Usar siempre el mejor puesto disponible** comienza en el puesto 1 y prueba sus cuentas antes de bajar. **Alternar las cuentas del mejor puesto** mantiene el modelo principal y distribuye sus cuentas. **Alternar puestos y cuentas** distribuye solicitudes entre puestos consecutivos; el campo **Cuántos puestos participan al alternar** acepta `0` para incluir todos. La rotación general no modifica el ranking secundario ni las subpestañas de capacidades especiales.

La casilla **Conservar mi orden al actualizar** conserva tus movimientos si la prueba termina correctamente. Si la desactivás, el resultado automático reemplaza el orden manual de esa vista. El sistema guarda las pruebas y sus resultados aunque el orden elegido sea manual.

# 12. Capacidades multimedia: diferencias importantes

Visión analiza una imagen existente. Generación de imágenes crea una nueva. Transcripción convierte audio en texto. TTS convierte texto en audio. Video crea una secuencia visual. Embeddings transforma texto en números para encontrar significados parecidos.

Estas capacidades son independientes. Un modelo que ve imágenes no necesariamente puede crearlas. Un proveedor que transcribe audio no necesariamente genera una voz. Antes de depender de una función, abrí `http://127.0.0.1:8080/v1/capabilities`.

## 12.1 Qué está implementado en esta copia

| Función | Integración presente | Resultado |
|---|---|---|
| Chat con texto | Proveedores y modelos publicados en `/v1/models` | Respuesta de chat |
| Analizar imagen | Modelos de chat clasificados para visión | Texto que describe o responde sobre la imagen |
| Crear imagen | SiliconFlow, Zhipu y Cloudflare Workers AI | Imagen o JSON del proveedor |
| Texto a voz | Edge TTS, SiliconFlow, Groq, Speechify y ElevenLabs | Audio binario |
| Transcribir audio | Groq Whisper | Texto en JSON |
| Crear video | Plan Zhipu y SiliconFlow | URL o tarea, según proveedor |
| Embeddings | Cohere y SiliconFlow | Vectores numéricos |
| Música | Solo simulador `mock_music` | Datos de prueba, sin archivo musical |

La generación de imágenes tiene adaptadores para SiliconFlow, Zhipu y Cloudflare Workers AI. Cloudflare usa el endpoint de inferencia de la cuenta y admite el modelo base `@cf/black-forest-labs/flux-1-schnell`; los demás modelos quedan sujetos a habilitación explícita de modelos de imagen no gratuitos. Speechify y ElevenLabs tienen rutas TTS; ElevenLabs exige que la cuenta tenga `speech_generation` habilitado. Una entrada del catálogo, una clave válida o `enabled=true` no aseguran que el proveedor tenga cuota ni acceso al modelo. La prueba real y el estado del proveedor son la última comprobación.

## 12.2 Alias en español

Los alias facilitan la llamada sin memorizar nombres técnicos:

| Alias | Qué hace | Requisito principal |
|---|---|---|
| `/v1/analizar-imagen` | Describe o responde sobre una imagen | Un modelo visual disponible |
| `/v1/crear-imagen` | Crea una imagen desde texto | SiliconFlow o Zhipu con acceso y cuota |
| `/v1/crear-voz` | Convierte texto en audio | Edge TTS sin clave, o un proveedor de voz |
| `/v1/transcribir-audio` | Convierte una grabación en texto | Groq con Whisper disponible |
| `/v1/crear-video` | Solicita un video desde texto | Plan Zhipu/SiliconFlow; requiere acceso y cuota |
| `/v1/buscar-significado` | Crea embeddings | Cohere o SiliconFlow con acceso disponible |

Los alias usan las mismas políticas, límites y cuentas que las rutas técnicas.

# 13. Analizar imágenes con visión

## 13.1 Qué puede hacer

Puede describir una fotografía, leer elementos visibles, comparar objetos o responder una pregunta sobre la imagen. La precisión depende del modelo, la calidad de la imagen y la claridad de la pregunta.

## 13.2 Qué necesita

Necesita una cuenta con un modelo visual apto. Según los modelos disponibles, puede provenir de Google, Groq, Ollama, Cloudflare, NVIDIA, OpenRouter, Cohere, SiliconFlow, Zhipu, TokenRouter, xKiro o Token Harbor.

## 13.3 Uso mediante el alias

```
POST http://127.0.0.1:8080/v1/analizar-imagen
```

```json
{
  "imagen": "https://sitio.example/foto.jpg",
  "pregunta": "Describí los objetos principales y su posición"
}
```

La imagen puede ser una dirección accesible o datos Base64 con formato `data:image/...;base64,...`. Base64 permite incluir la imagen dentro de la petición, pero aumenta el tamaño.

## 13.4 Privacidad

Si el modelo es cloud, la imagen se envía al proveedor. Para evitarlo, configurá procesamiento local y un modelo visual local. No asumas que elegir la ruta `vision` vuelve local el procesamiento.

# 14. Crear imágenes

## 14.1 Proveedores integrados

SiliconFlow usa FLUX.1-schnell como opción base, Zhipu puede usar CogView-3-Flash y Cloudflare Workers AI puede usar `@cf/black-forest-labs/flux-1-schnell`. Cada opción necesita credenciales, permisos y cuota; confirmá disponibilidad en `/v1/capabilities` y revisá el costo en tu cuenta.

## 14.2 Escribir una buena descripción

Incluí sujeto, entorno, iluminación, encuadre y estilo. “Un perro” deja casi todo a decisión del modelo. “Un perro negro sentado junto a una ventana, luz suave de mañana, ilustración de libro infantil” produce una intención más clara.

## 14.3 Ejemplo

```json
{
  "descripcion": "Una biblioteca comunitaria luminosa, personas leyendo y trabajando juntas, ilustración detallada",
  "provider": "siliconflow",
  "model": "auto"
}
```

Enviá ese JSON a `/v1/crear-imagen`. La respuesta puede contener una URL temporal o la imagen codificada. Guardá el resultado si querés conservarlo.

## 14.4 Evitar duplicados

Una generación puede completarse aunque la conexión se corte antes de mostrarla. No repitas automáticamente la misma petición muchas veces porque podés consumir cuota y obtener duplicados.

## 14.5 Modelos no confirmados como gratuitos

Permanecen bloqueados por defecto. Solo se habilitan con `NUCLEO_HABILITAR_MODELOS_IMAGEN_NO_GRATUITOS=true` cuando entendés la cuota y aceptás un posible costo.

# 15. Edge TTS incluido: voz sin API key

## 15.1 Qué es

Edge TTS convierte texto escrito en audio hablado. Núcleo IA lo incluye como la forma más sencilla de probar voz. No requiere crear una cuenta, copiar una API key ni tener saldo. Sí necesita conexión a Internet durante la generación porque utiliza el servicio de voz de Microsoft Edge.

## 15.2 Cómo usarlo

Enviá una petición a `/v1/crear-voz` y especificá `edge_tts`:

```json
{
  "provider": "edge_tts",
  "texto": "Este audio fue creado desde Núcleo IA.",
  "voice": "es-AR-ElenaNeural"
}
```

La respuesta es un MP3. La aplicación que realiza la petición debe guardarlo con un nombre terminado en `.mp3`. Si usás una herramienta de terminal, indicá un archivo de salida. Si usás un agente, pedile que conserve el contenido recibido como archivo de audio.

Es importante escribir `"provider":"edge_tts"`. Si se omite el proveedor, la configuración actual puede intentar usar SiliconFlow, que sí necesita clave.

## 15.3 Idiomas y voces

El nombre empieza con un código de idioma y región. `es-AR` es español de Argentina, `es-MX` español de México, `es-ES` español de España, `en-US` inglés de Estados Unidos y `pt-BR` portugués de Brasil.

| Voz | Idioma y región | Uso |
|---|---|---|
| `es-AR-ElenaNeural` | Español de Argentina | Voz predeterminada recomendada |
| `es-MX-DaliaNeural` | Español de México | Lectura con variante mexicana |
| `es-ES-ElviraNeural` | Español de España | Lectura con variante europea |
| `en-US-JennyNeural` | Inglés de Estados Unidos | Texto en inglés |
| `pt-BR-FranciscaNeural` | Portugués de Brasil | Texto en portugués |
| `fr-FR-DeniseNeural` | Francés de Francia | Texto en francés |
| `it-IT-ElsaNeural` | Italiano | Texto en italiano |

El catálogo puede cambiar. Si una voz deja de existir, elegí otra del mismo idioma. Escribí el texto en el idioma de la voz para obtener una pronunciación natural.

## 15.4 Velocidad, tono y volumen

`rate` cambia la velocidad. `-10%` habla más despacio y `+10%` más rápido.

`pitch` cambia el tono. Un valor positivo lo sube y uno negativo lo baja.

`volume` modifica el volumen relativo.

```json
{
  "provider": "edge_tts",
  "texto": "Esta frase se leerá un poco más despacio.",
  "voice": "es-AR-ElenaNeural",
  "rate": "-10%",
  "pitch": "+0Hz",
  "volume": "+0%"
}
```

## 15.5 Textos largos

Para un capítulo largo, dividí el texto en fragmentos razonables y generá un MP3 por fragmento. Esto facilita saber qué parte falló y evita repetir todo. Nombrá los archivos en orden, por ejemplo `capitulo_01.mp3`, `capitulo_02.mp3` y `capitulo_03.mp3`.

## 15.6 Errores habituales

Si aparece que Edge TTS no está instalado, ejecutá nuevamente el instalador de Núcleo IA. Si aparece un error de conexión, verificá Internet. Si una voz falla, probá la voz predeterminada. Edge TTS no usa el pozo de API keys porque no necesita una.

# 16. Otras opciones de texto a voz

SiliconFlow puede usar CosyVoice2 y Groq puede usar PlayAI TTS. Estas opciones requieren una API key válida, un modelo habilitado y cuota. Pueden ofrecer voces o comportamientos diferentes de Edge TTS.

Para SiliconFlow enviá `provider: "siliconflow"`. Para Groq enviá `provider: "groq"`. El modelo `auto` selecciona el modelo base permitido para ese proveedor.

Los modelos de voz fuera de la lista base permanecen bloqueados salvo que actives `NUCLEO_HABILITAR_MODELOS_VOZ_NO_GRATUITOS=true`.

Speechify también está integrado como proveedor dedicado. Agregá y comprobá una cuenta en **Mis servicios**; después envía `provider: "speechify"`, el texto en `input` y un `voice_id` habilitado en tu espacio de trabajo. El modelo predeterminado es `simba-3.2`; el formato predeterminado es `mp3`.

```json
{"provider":"speechify","input":"Hola, este es un audio de prueba.","voice_id":"ID_DE_TU_VOZ","model":"simba-3.2","audio_format":"mp3"}
```

## 16.1 Speechify como proveedor de voz

Speechify está integrado como proveedor dedicado de texto a voz. Agregá y comprobá una cuenta en **Mis servicios**. Al llamar `/v1/audio/speech`, envía `provider: "speechify"`, el texto en `input` y un `voice_id` habilitado en tu espacio de trabajo. El modelo predeterminado es `simba-3.2` y el formato predeterminado es `mp3`; el acceso y el precio dependen de tu plan.

```json
{"provider":"speechify","input":"Hola, este es un audio de prueba.","voice_id":"ID_DE_TU_VOZ","model":"simba-3.2","audio_format":"mp3"}
```

ElevenLabs se puede seleccionar con `provider: "elevenlabs"`, siempre que la cuenta tenga `speech_generation` habilitado y se envíe un `voice_id` o se haya guardado `ELEVENLABS_VOICE_ID`.

```json
{"provider":"elevenlabs","input":"Hola.","voice_id":"ID_DE_TU_VOZ","model":"eleven_multilingual_v2","output_format":"mp3_44100_128","voice_settings":{"stability":0.5,"similarity_boost":0.75}}
```

La API key se guarda en la configuración de Núcleo IA, no en el JSON de petición. Opciones avanzadas como `voice_settings`, `language_code`, `pronunciation_dictionary_locators`, `seed` y `optimize_streaming_latency` se reenvían cuando el proveedor las admite. Confirma el precio y cuota del plan antes de usarlo a escala.


# 17. Transcribir audio

Transcribir significa convertir lo hablado en texto. Es la operación inversa a TTS.

La ruta sencilla es `/v1/transcribir-audio`. Se adjunta un archivo MP3, WAV u OGG. La integración usa Groq y Whisper, por lo que necesitás una clave de Groq con cuota disponible.

El archivo se procesa temporalmente. Una grabación con ruido, voces superpuestas o volumen muy bajo puede producir errores. Si el archivo es grande, dividilo antes. El límite predeterminado protege la cuota y el servidor.

El resultado es texto. Después podés pedir a un modelo que lo resuma, lo corrija o lo convierta nuevamente en audio.

# 18. Crear videos

La ruta `/v1/crear-video` recibe una descripción. El plan de esta versión contempla Zhipu (`CogVideoX-Flash`) y SiliconFlow (`stabilityai/stable-video-diffusion`). Necesita una cuenta con modelo permitido, acceso y cuota de video.

```json
{
  "descripcion": "Una cámara avanza lentamente por un bosque húmedo al amanecer",
  "model": "auto"
}
```

La generación puede ser asíncrona. Eso significa que el proveedor acepta el trabajo y devuelve un identificador antes de terminar el MP4. Conservá el identificador o la URL de la respuesta. No repitas la creación solo porque todavía no llegó el archivo final.

Los modelos de video no confirmados como gratuitos permanecen desactivados. Para permitirlos existe `NUCLEO_HABILITAR_MODELOS_VIDEO_NO_GRATUITOS=true`. Activarlo puede generar consumo pago.

# 19. Embeddings y búsqueda por significado

Un embedding es una lista de números que representa características del significado de un texto. No se muestra como respuesta de chat. Una aplicación guarda esos números y los compara para encontrar textos parecidos.

La ruta `/v1/buscar-significado` puede enrutar a Cohere o SiliconFlow, por ejemplo con `BAAI/bge-m3`. Necesita una cuenta con permiso y cuota para embeddings.

```json
{
  "texto": "economía participativa y cooperativas",
  "model": "auto"
}
```

Usá el mismo modelo para todos los documentos que quieras comparar. Si cambiás el modelo o la dimensión, los vectores anteriores pueden dejar de ser comparables.

# 20. Configuración explicada campo por campo

La configuración principal se guarda en `.env`. Para una persona principiante, lo más seguro es cambiarla mediante los asistentes. Si necesitás editarla, detené Núcleo IA, hacé una copia privada y modificá una sola opción por vez.

## 20.1 Red y puerto

`PROXY_HOST=127.0.0.1` limita el servidor a la misma computadora. Es la opción recomendada para uso personal.

`PROXY_PORT=8080` define el puerto. Cambialo solo si otro programa ya usa 8080. Después actualizá la dirección en cada agente.

`ALLOWED_HOSTS` limita qué nombres de host acepta el servidor. En una red compartida debe contener los nombres reales utilizados.

`CORS_ALLOW_ORIGINS` define qué páginas web pueden llamar al servidor desde un navegador. No uses `*` en una instalación compartida con credenciales.

`CORS_ALLOW_CREDENTIALS` decide si el navegador puede enviar credenciales en solicitudes entre orígenes. Mantenelo desactivado salvo que sepas que la interfaz lo necesita.

## 20.2 Autenticación

`AUTH_ENABLED=false` simplifica el uso local. Si el servidor escucha en otra interfaz o lo usan varias personas, cambialo a `true`.

`NUCLEO_API_KEY` es la clave de consumo. Los agentes la usan para chat y capacidades.

`NUCLEO_ADMIN_KEY` es la clave administrativa del modo Profesional. Debe ser diferente de la clave de consumo y no se entrega a usuarios comunes.

## 20.3 Perfil y privacidad

`PERFIL_USO=personal` corresponde a una computadora y una persona. El nombre visible “organización” se guarda internamente como `empresa` por compatibilidad con versiones anteriores.

`PROCESAMIENTO_PERMITIDO=local_y_cloud` permite ambos tipos. `solo_local` impide enviar solicitudes a proveedores cloud. Esta regla puede reducir mucho la cantidad de modelos disponibles.

`PERMITIR_OLLAMA_REMOTO=false` evita usar un Ollama de otra computadora. Activarlo requiere una red confiable y una configuración explícita.

## 20.4 Selección de servicios y modelos

`SERVICIOS_ACTIVOS` es una lista separada por comas. Solo esos proveedores participan. Una credencial guardada para un servicio inactivo permanece guardada, pero no se usa.

`ACTIVE_MODEL=auto` define la ruta predeterminada.

`ROTACION_TOP_N=3` considera las primeras tres opciones del ranking. `0` permite recorrer todas. Un número grande aumenta la cantidad de alternativas, pero también puede hacer más largo un fallo completo.

`MODO_ROTACION` puede priorizar modelos, cuentas, proveedores, velocidad o cascada. Para empezar, conservá el valor instalado.

`SOLO_MODELOS_GRATUITOS=false` permite opciones según las políticas normales. Si lo cambiás a `true`, Núcleo IA exige una marca gratuita verificable antes de enviar. Esto puede dejar rutas sin candidatos si el proveedor no publica suficiente información.

## 20.5 Límites y tiempos

`MAX_REQUESTS_POR_CUENTA_HORA` limita cuántas peticiones se reservan por cuenta durante una hora.

`MAX_REQUESTS_POR_CUENTA_SEMANA` agrega un límite semanal local.

`MAX_REQUESTS_GLOBAL_MINUTO` protege al servidor de una ráfaga total.

Estos límites locales no sustituyen los límites del proveedor. Un proveedor puede aplicar una cuota menor.

`TIMEOUT_CLOUD` define cuánto se espera una operación cloud. Imágenes, audio y video pueden necesitar más tiempo que una respuesta breve de texto.

`MAX_REQUEST_BODY_BYTES` limita el tamaño total de la petición. Una imagen Base64 o un audio grande puede superar este valor.

## 20.6 Modelos multimedia no gratuitos

`NUCLEO_HABILITAR_MODELOS_IMAGEN_NO_GRATUITOS`, `NUCLEO_HABILITAR_MODELOS_VOZ_NO_GRATUITOS` y `NUCLEO_HABILITAR_MODELOS_VIDEO_NO_GRATUITOS` vienen en `false`. Cambialos solamente si conocés la cuota del proveedor y aceptás el posible costo.

## 20.7 Ultra fallback

El ultra fallback es una opción de emergencia desactivada. Puede apuntar a una cuenta y un modelo pequeño específico cuando las rutas normales no funcionan. No lo actives hasta haber probado el modelo y entender su límite de contexto y calidad.

## 20.8 Configuración de instancias Ollama

`INSTANCIAS` indica cuántas instancias administradas existen. Normalmente lo actualizan los asistentes. Cambiarlo a mano sin crear o retirar las instancias correspondientes puede dejar puertos huérfanos.

`PUERTO_BASE=11434` es el primer puerto usado por Ollama. Las cuentas adicionales usan puertos separados. No cambies el puerto base si otras aplicaciones ya se conectan a la instalación actual.

`OLLAMA_BASE_DIR` es la carpeta donde se guardan las instancias administradas. Puede ocupar mucho espacio. No la muevas mientras Ollama está funcionando y no la incluyas en una copia pública.

`CONTEXT_LENGTH` establece una longitud de contexto solicitada para modelos compatibles. Un valor muy alto consume más memoria y no obliga a un modelo a aceptar más contexto del que soporta.

## 20.9 Pruebas, conexiones y compatibilidad

`CURL_TIMEOUT` limita cuánto esperan algunos scripts de comprobación. Un valor demasiado bajo puede marcar como fallida una conexión lenta; uno demasiado alto hace que una comprobación caída tarde en terminar.

`MAX_TOKENS_TEST` limita la cantidad de salida usada en pruebas de disponibilidad. Se mantiene pequeña para no gastar cuota innecesariamente. No mide la calidad de una respuesta larga.

`OPENCLAW_PUERTO_DEFAULT` conserva el puerto esperado por integraciones con OpenClaw. No afecta el puerto principal de Núcleo IA.

`granja.env` existe por compatibilidad con instalaciones anteriores. La configuración principal es `.env` y las variables definidas directamente en el sistema tienen prioridad. Evitá definir el mismo valor de maneras diferentes porque puede resultar confuso saber cuál se está usando.

# 21. Respaldo, restauración y traslado

## 21.1 Respaldo personal

El respaldo personal contiene configuración, cuentas y correos. Es privado. Elegí una carpeta vacía y ejecutá:

```
python granja.py backup RUTA_DE_CARPETA_VACIA
```

Guardá esa carpeta en un medio seguro. No la publiques ni la envíes junto con una copia distribuible.

## 21.2 Restaurar en otra computadora

Instalá primero Núcleo IA en la computadora nueva. Después ejecutá:

```
python granja.py restore RUTA_DEL_RESPALDO
```

Reiniciá el servidor. Las claves y los correos vuelven a aparecer. Las autorizaciones externas que hayan vencido deben repararse una por una. En Ollama, usá el correo para elegir la cuenta exacta.

## 21.3 Trasladar cuentas desde el Centro de control

Esta opción agrega cuentas desde otra instalación sin reemplazar las cuentas que ya tenés en esta computadora.

1. En la computadora que ya tiene las claves, abrí **Centro de control** y entrá en la pestaña **Trasladar cuentas**.
2. Elegí **Crear y descargar paquete**. Se descargará `nucleo-ia-cuentas.zip`.
3. Pasá ese archivo a la otra computadora usando una memoria USB privada u otro medio seguro.
4. Instalá Núcleo IA en la computadora nueva y abrí **Centro de control → Trasladar cuentas**.
5. Seleccioná el archivo ZIP y elegí **Agregar estas cuentas**.
6. Cuando termine, reiniciá Núcleo IA si el panel lo indica y comprobá las conexiones en **Servicios y cuentas**.

El paquete contiene claves API sin cifrar. No lo envíes por correo o chat, no lo subas a una carpeta compartida y eliminá las copias temporales después del traslado. Si una cuenta con el mismo identificador ya existe, se conserva la de destino; si una variable de clave ya tiene valor, también se conserva. Las autorizaciones que dependan de sesiones externas pueden requerir una nueva conexión.

## 21.4 Actualizar una instalación

1. Detené Núcleo IA.
2. Creá un respaldo personal.
3. Conservá el respaldo fuera de la carpeta que vas a reemplazar.
4. Aplicá la actualización sobre la instalación según el paquete recibido.
5. Ejecutá nuevamente el instalador para actualizar dependencias.
6. Iniciá y revisá `/healthz`, `/readyz` y Mis servicios.
7. Restaurá solamente si la configuración no fue conservada.

## 21.5 Las tres carpetas y sus diferencias

En una instalación de desarrollo pueden existir tres carpetas separadas:

- **nucleo ia:** carpeta de trabajo. Puede contener cuentas, claves, estados, registros y herramientas internas. Es privada.
- **nucleo ia EXPORTABLE:** copia para compartir con otra persona. Se genera sanitizada, comienza sin cuentas y conserva los archivos necesarios para instalar y usar el programa.
- **nucleo ia GITHUB:** copia pública preparada para subir a GitHub. No contiene claves, correos, estados privados, registros ni herramientas internas de pruebas.

No copies manualmente la carpeta privada sobre una exportable. Usá el sincronizador para regenerarla y el validador para comprobarla:

```
python scripts/sincronizar_exportable.py --destino "RUTA_DE_LA_COPIA"
python scripts/validar_exportable.py "RUTA_DE_LA_COPIA"
```

Los informes de auditoría, inventarios locales, matrices de cuotas y pruebas de desarrollo no forman parte de las copias públicas. Los manuales, la licencia, la política de seguridad, las pruebas públicas y los lanzadores sí se conservan porque ayudan a instalar, comprender y verificar el programa.

# 22. Uso compartido en una organización

## 22.1 Cuándo usarlo

Usá modo Profesional si varias personas o equipos consumen el mismo servidor o necesitás controles reforzados de acceso.

## 22.2 Separación de permisos

La clave de consumo permite usar modelos y capacidades. La clave administrativa permite revisar estado, rankings y cuentas. El responsable conserva los correos para identificar y reparar cuentas; los consumidores no necesitan verlos.

## 22.3 Exposición de red

No publiques el puerto 8080 directamente en Internet. Usá autenticación, firewall y HTTPS mediante un proxy inverso administrado por una persona con experiencia. Limitá CORS y hosts a las direcciones reales.

## 22.4 Políticas de datos

Definí si se permite cloud, qué proveedores pueden recibir contenido y si solo se aceptan modelos gratuitos. Informá a las personas usuarias qué datos salen de la red y qué proveedores pueden conservarlos.

## 22.5 Volver al modo personal

Cambiá el perfil a personal y reiniciá. Las cuentas y correos permanecen; cambia la separación de permisos. Revisá también host, autenticación, CORS y firewall.

# 23. Seguridad y privacidad

## 23.1 Archivos privados

No compartas `.env`, `granja.env`, `cuentas.json`, los registros de `state` ni las carpetas de instancias Ollama. Pueden revelar claves, correos, rutas o información operativa.

## 23.2 Contraseñas

Núcleo IA no necesita la contraseña de tus proveedores. Si una pantalla que no pertenece al sitio oficial te la pide, detenete y revisá la dirección.

## 23.3 Contenido enviado a cloud

Cuando se elige un proveedor cloud, el prompt, las imágenes, el audio o los documentos necesarios se envían a ese proveedor. La política `solo_local` bloquea esos envíos, pero requiere modelos locales capaces de realizar la tarea.

## 23.4 Registros

Los registros ayudan a diagnosticar errores. Antes de compartir un registro con otra persona, revisá si contiene correos, nombres de modelos, rutas locales o fragmentos de errores del proveedor. Compartí solo la parte necesaria.

# 24. Diagnóstico de problemas

## 24.1 Orden recomendado

1. Comprobá `/healthz`.
2. Comprobá `/readyz`.
3. Abrí `/status`.
4. Revisá `/v1/capabilities` si falla una función multimedia.
5. Probá un mensaje breve con `model=auto`.
6. Identificá el código de error.
7. Revisá la cuenta y el correo afectados.

## 24.2 Códigos frecuentes

| Código | Significado habitual | Qué hacer |
|---|---|---|
| 400 | La petición está mal formada | Revisar nombres de campos y JSON |
| 401 | Clave del cliente incorrecta | Revisar `NUCLEO_API_KEY` y la aplicación |
| 402 | Crédito o cuota agotada | Esperar, recargar o usar otra cuenta |
| 403 | Permiso, política o modelo bloqueado | Revisar proveedor, gratuidad y configuración |
| 404 | Ruta o modelo inexistente | Comprobar `/v1` y la lista de modelos |
| 413 | Archivo o petición demasiado grande | Reducir o dividir el contenido |
| 422 | Falta un campo requerido | Leer el detalle y completar el campo |
| 429 | Demasiadas solicitudes | Esperar; permitir que actúe el failover |
| 500-503 | Fallo interno o servicio no disponible | Revisar estado, cuentas y registros |

## 24.3 El navegador no abre Mis servicios

Ejecutá nuevamente el iniciador. Si muestra una dirección local, copiala al navegador. Comprobá que Python esté instalado. En un servidor sin escritorio, usá el modo terminal.

## 24.4 Una clave no funciona

Comprobá que la copiaste completa, que pertenece a la cuenta correcta, que está activa, que usaste la plataforma correcta y que el servicio permite el modelo. Crear una cuenta no garantiza cuota gratuita.

## 24.5 El puerto está ocupado

Otro programa puede usar 8080. Detené instancias anteriores con el iniciador de detención. Si necesitás otro puerto, cambialo en la configuración y también en todos los clientes.

## 24.6 La respuesta tarda mucho

Núcleo IA puede estar probando varias cuentas después de errores temporales. Las imágenes, el audio y el video también tardan más que el texto. Revisá `/status` antes de cancelar y repetir muchas veces.

## 24.7 Un agente no muestra modelos

Abrí `/v1/models` en el navegador. Si allí aparecen modelos, revisá que la dirección del agente termine en `/v1`. Si la aplicación no descubre modelos automáticamente, agregá `auto`, `tools`, `reasoning`, `cheap` y `vision` manualmente.

## 24.8 Docker no llega al servidor

Dentro de un contenedor, `127.0.0.1` apunta al contenedor. En Docker Desktop suele usarse `host.docker.internal`. En Linux puede requerir una regla de host gateway o una dirección de red. Si exponés Núcleo IA fuera de localhost, activá autenticación y restringí el firewall.

# 25. Comandos y archivos de uso cotidiano

## 25.1 Gestor universal

| Comando | Qué hace |
|---|---|
| `python granja.py install` | Instala el entorno y las dependencias |
| `python granja.py start` | Inicia el servidor |
| `python granja.py stop` | Detiene el servidor |
| `python granja.py restart` | Reinicia el servidor |
| `python granja.py status` | Muestra el estado operativo |
| `python granja.py models` | Lista modelos publicados |
| `python granja.py rank` | Actualiza el ranking |
| `python granja.py test` | Ejecuta pruebas internas |
| `python granja.py config` | Abre la configuración guiada |
| `python granja.py add-key` | Agrega una clave de proveedor |
| `python granja.py add-ollama` | Vincula una cuenta Ollama |
| `python granja.py adjust-ranking` | Ajusta el orden manualmente |
| `python granja.py sync-exportable` | Crea la copia pública sin credenciales |

## 25.2 Iniciadores de Windows

`instalar_nucleo_ia.bat` instala. `iniciar_todo.bat` inicia con ventana. `iniciar_segundo_plano.vbs` inicia oculto. `detener_todo.bat` detiene. `agregar_cuentas.bat` abre Mis servicios. `actualizar_rankings.bat` actualiza modelos. `reparar_ollama.bat` reautoriza una cuenta concreta. `probar_demo.bat` abre la demostración.

## 25.3 Iniciadores de Linux

`instalar_nucleo_ia.sh` instala. `iniciar_todo.sh` inicia. `detener_todo.sh` detiene. `agregar_cuentas.sh` abre el asistente gráfico o de terminal. `actualizar_rankings.sh` actualiza modelos. `reparar_ollama.sh` reautoriza una cuenta concreta. `probar_demo.sh` abre la demostración.

## 25.4 Otros iniciadores que podés encontrar

`configura_nucleoia.bat` y `configura_nucleoia.sh` abren la configuración guiada de servicios y rotación.

`ajustar_ranking_manual.bat` y `ajustar_ranking_manual.sh` permiten mover modelos en el orden. Un ajuste manual expresa una preferencia; no vuelve saludable a un modelo que está caído.

`instalar_inicio_automatico.bat` y `instalar_inicio_automatico.sh` agregan el arranque al inicio de sesión. Los archivos que comienzan con `desinstalar_` quitan únicamente ese arranque.


Los archivos dentro de la carpeta `scripts` son componentes internos o alternativas avanzadas. Usá primero los iniciadores de la carpeta principal o `granja.py`, porque preparan el contexto correcto y muestran mensajes más claros.

# 26. Recorridos completos de ejemplo

## 26.1 Primera instalación personal

Extraé la carpeta, ejecutá el instalador, iniciá el servidor, comprobá `/healthz`, abrí Mis servicios, conectá una cuenta, aplicá las conexiones y configurá tu agente con la dirección local, clave `local` y modelo `auto`. Probá una frase corta. Después creá un respaldo personal.

## 26.2 Crear un audio sin ninguna API key

Instalá e iniciá Núcleo IA. Enviá texto a `/v1/crear-voz` con `provider=edge_tts` y `voice=es-AR-ElenaNeural`. Guardá la respuesta como MP3. No hace falta abrir Mis servicios ni agregar una clave para esta capacidad.

## 26.3 Recuperar una cuenta Ollama

Abrí Mis servicios, entrá en Ollama, buscá el correo que aparece con error y elegí “Volver a autorizar esta cuenta”. Completá la autorización oficial y aplicá conexiones. No borres otras cuentas ni cambies sus puertos.

## 26.4 Preparar una instalación compartida

Probá primero en modo Personal. Creá un respaldo. Cambiá al modo Profesional, definí las direcciones y sitios autorizados, configurá HTTPS y firewall para acceso por red, y documentá qué proveedores reciben datos. El asistente activa la autenticación y genera claves distintas de consumo y administración.

# 27. Glosario explicado

API: reglas y direcciones que permiten que dos programas se comuniquen.

API key: clave creada por un proveedor para autorizar a un programa. Debe mantenerse privada.

Base URL: dirección principal que una aplicación usa para encontrar la API.

Cloud: procesamiento en computadoras del proveedor a través de Internet.

Contexto: conjunto de instrucciones, mensajes y datos que el modelo recibe en una petición.

Cooldown o espera: período durante el cual una cuenta no se vuelve a probar después de un límite.

Embedding: lista de números que representa el significado de un texto.

Failover: cambio automático a otra opción después de un fallo.

JSON: formato de texto con campos y valores usado para enviar peticiones.

Local: procesamiento que ocurre en la propia computadora o servicio accesible localmente.

Modelo: sistema de inteligencia artificial que ejecuta una tarea.

Multimodal: capacidad de trabajar con más de un tipo de información, como texto e imágenes.

Proveedor: servicio que ofrece acceso a modelos.

Proxy: intermediario que recibe una petición, elige un destino y devuelve la respuesta.

Ranking: orden calculado para elegir modelos según evidencia y estado.

Streaming: forma de recibir una respuesta por partes mientras se genera.

Token: unidad pequeña en la que un modelo divide el texto. No coincide exactamente con una palabra.

TTS: “text to speech” o texto a voz; convierte texto escrito en audio hablado.

Visión: capacidad de interpretar imágenes enviadas al modelo.

# 28. Lista final de comprobación

- La carpeta está extraída y guardada en una ubicación estable.
- El instalador terminó sin errores.
- `/healthz` responde.
- `/readyz` no muestra un bloqueo desconocido.
- Mis servicios muestra al menos una cuenta válida para las funciones cloud que querés usar.
- El agente usa `http://127.0.0.1:8080/v1`.
- El primer modelo elegido es `auto`.
- Edge TTS se llama explícitamente con `provider=edge_tts`.
- Sabés qué capacidades envían información a Internet.
- Tenés un respaldo personal privado.
- No compartís la carpeta privada ni las claves.

Con estas comprobaciones, una instalación personal queda preparada para conversar, usar agentes y probar las capacidades adicionales disponibles en sus cuentas.

# 29. Preguntas frecuentes

## 29.1 ¿Tengo que conectar todos los servicios?

No. Para empezar alcanza una cuenta que pueda responder texto. Los otros servicios agregan alternativas o capacidades. Conectá otro cuando tengas un motivo concreto: más continuidad, visión, transcripción, imágenes, embeddings, voz o video. La lista exacta depende de las conexiones y adaptadores disponibles en esta versión.

## 29.2 ¿Núcleo IA es gratis?

El programa puede utilizarse según su licencia, pero cada proveedor mantiene sus propias condiciones. Algunos ofrecen cuotas gratuitas, otros piden saldo y otros mezclan modelos gratuitos y pagos. Edge TTS no necesita API key ni saldo, aunque usa Internet. Los modelos locales consumen recursos de tu computadora en lugar de una cuota cloud.

## 29.3 ¿Por qué una clave aparece comprobada pero una petición falla?

La comprobación confirma que la autenticación funcionó en ese momento. Una petición concreta también depende del modelo, la región, la cuota, el tamaño del contenido y los permisos del plan. Revisá el código de error y probá una tarea de texto breve para separar un problema general de uno específico del modelo.

## 29.4 ¿Puedo usar varias cuentas del mismo proveedor?

Sí, cuando la integración lo admite. Identificá cada una con su correo real. No supongas que dos claves creadas desde la misma cuenta ofrecen dos cuotas diferentes. Respetá siempre las reglas del proveedor.

## 29.5 ¿Por qué se guardan los correos de Ollama?

Porque permiten reconocer cuál autorización corresponde a cada instancia. Si una falla, podés reautorizar esa cuenta exacta sin borrar, adivinar ni volver a cargar las demás. El correo es información privada y no se incluye en la copia pública.

## 29.6 ¿Una copia exportable mostrará mis cuentas en otra PC?

No. La copia exportable se limpia precisamente para compartir el programa sin tus credenciales. En otra PC mostrará la misma capacidad para agregar cuentas, pero comenzará vacía. Para trasladar tus propias cuentas de forma privada usá respaldo y restauración.

## 29.7 ¿Puedo usar Núcleo IA sin Internet?

Sí, si tenés Ollama local con modelos descargados y configurás procesamiento local. Los servicios cloud, la autorización de cuentas y Edge TTS necesitan Internet. Una función local también puede necesitar Internet durante la instalación inicial de dependencias o modelos.

## 29.8 ¿Qué ocurre si se corta Internet durante una petición?

El proveedor cloud puede no recibir la solicitud o puede haberla completado sin que llegue la respuesta. Para texto se puede reintentar con prudencia. Para imágenes y video, evitá reintentos automáticos inmediatos porque podrías duplicar una generación que consume cuota.

## 29.9 ¿Puedo elegir siempre un modelo específico?

Sí, escribiendo su identificador cuando el cliente lo permite. Al hacerlo renunciás a parte de la selección automática. Si ese modelo se cae o desaparece, puede no existir una alternativa equivalente. `auto` es más resistente para uso general.

## 29.10 ¿Por qué tools no ejecuta acciones por sí solo?

`tools` selecciona modelos capaces de solicitar funciones. La aplicación que actúa como agente define las funciones, decide permisos y ejecuta la acción. Núcleo IA no debe conceder acceso a archivos o programas que el cliente nunca autorizó.

## 29.11 ¿Vision crea imágenes?

No. Visión recibe una imagen existente y la interpreta. Para crear una nueva se usa `/v1/crear-imagen`. Son tareas y cuotas diferentes.

## 29.12 ¿Transcripción y TTS son lo mismo?

No. Transcripción recibe una grabación y devuelve texto. TTS recibe texto y devuelve una grabación. Groq Whisper se usa para transcribir; Edge TTS, CosyVoice o PlayAI TTS pueden generar voz.

## 29.13 ¿Puedo escuchar un texto sin configurar ningún servicio?

Sí. Usá `/v1/crear-voz` con `provider=edge_tts`. La dependencia debe estar instalada y la computadora necesita Internet, pero no hace falta una API key.

## 29.14 ¿Dónde se guardan los audios e imágenes?

La API devuelve el resultado a la aplicación que hizo la petición. Esa aplicación decide el nombre y la carpeta. Si usás una terminal, indicá un archivo de salida. Si usás un agente, pedile que lo guarde y verificá la ruta que informa.

## 29.15 ¿Cómo sé si una función está disponible ahora?

Abrí `/v1/capabilities`. Esa respuesta muestra las capacidades detectadas y sus proveedores. Después realizá una prueba pequeña: una capacidad declarada puede encontrar igualmente un límite temporal al usar la cuenta real.

## 29.16 ¿Es peligroso cambiar `.env`?

No si hacés un respaldo, detenés el servidor y modificás un campo conocido. El riesgo aparece al borrar claves, duplicar opciones contradictorias o exponer el servidor en red sin autenticación. Usá los asistentes cuando exista una opción equivalente.

## 29.17 ¿Qué debo guardar antes de pedir ayuda?

Anotá qué estabas intentando, la hora aproximada, la ruta o capacidad, el código de error y el correo de la cuenta afectada. No copies la API key. Esa información permite investigar sin entregar secretos.

## 29.18 ¿Cómo sé si un ranking está trabajando o se trabó?

La pestaña Rankings muestra un panel de actividad mientras la prueba está abierta. Mirá el servicio actual, la etapa, el tiempo y el último evento. Si el mensaje dice **Sin avances recientes**, esperá a que termine el margen de seguridad; luego el sistema la marca como detenida y permite volver a intentarlo. Usá **Detener pruebas** si ya no querés esperar. El ranking anterior queda disponible durante todo el proceso.

## 29.19 ¿Actualizar todos borra mi orden manual?

No si está marcada **Conservar mi orden al actualizar**. La prueba actualiza catálogos y resultados, pero tu orden queda guardado cuando termina correctamente. Si desmarcás esa opción, el resultado automático reemplaza el orden de la vista que se actualizó. **Restaurar automático** también afecta solo la vista elegida.

## 29.20 ¿Por qué una capacidad aparece pero no todos los proveedores pueden usarla?

La capacidad se muestra por proveedor y modelo, no solo por el nombre del servicio. Ver imágenes, crear imágenes, transcribir audio, crear voz y crear video son operaciones distintas. Cada una requiere un adaptador, un modelo compatible, una cuenta autorizada y cuota disponible. Abrí `/v1/capabilities` y revisá la tarjeta o alias que querés usar antes de enviar contenido real.

# 30. Autor y contacto

Núcleo IA fue creado y es mantenido por **Cristian Quiroga**, desde **Malargüe, Mendoza, Argentina**.

Para consultas, comentarios o para informar un problema, escribí a [pyartificial@gmail.com](mailto:pyartificial@gmail.com). Si informás un error, contá qué estabas haciendo y copiá el mensaje que apareció. **No envíes claves API, contraseñas ni códigos de acceso.**

También podés encontrar estos datos dentro del programa, en **Centro de control → Acerca de**.

# 31. Licencia

Núcleo IA se distribuye bajo la licencia **GNU Affero General Public License, versión 3 o posterior (AGPL-3.0-or-later)**. La licencia permite usar el programa, estudiarlo, modificarlo y compartirlo respetando sus condiciones.

Si redistribuís una copia modificada, conservá el aviso de copyright y entregá el texto de la licencia. Si ofrecés el programa modificado como un servicio accesible por red, la AGPL también exige ofrecer a quienes lo usan el código fuente correspondiente a esa versión modificada.

La licencia del programa no reemplaza las condiciones de los proveedores conectados. Cada cuenta, API key, modelo, cuota y servicio externo se rige además por sus propios términos. No redistribuyas credenciales, cuentas personales ni contenido de terceros junto con el programa.
