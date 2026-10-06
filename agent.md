# agent.md — Backend OpenAI-Compatible (Núcleo IA)

## Objetivo del Proyecto

**Núcleo IA** es un proxy local compatible con OpenAI. Recibe peticiones en `/v1`, consulta los modelos/candidatos habilitados en esta instalación y enruta chat y las capacidades implementadas. El estado y las cuentas son locales a cada instalación.

## Catálogo de servicios de esta copia

El catálogo de interfaz (`scripts/catalogo_servicios.py`) distingue el grupo **Servicios generales** del grupo **Proveedores opcionales**. Son etiquetas de navegación: no certifican precio cero, crédito, acceso a cada modelo ni implementación de cada capacidad. Comprobar el costo de una ruta/modelo y sus límites por separado.

Servicios generales (22 fichas, incluidas conexiones especiales): Ollama, Groq, OpenRouter, NVIDIA NIM, Google Gemini, Cloudflare Workers AI, Cohere, SiliconFlow, Zhipu AI/Z.AI, TokenRouter, xKiro, Token Harbor, APInex, ElevenLabs (con capacidades por cuenta), Agnes AI, Aion Labs, BazaarLink, Hugging Face Inference Providers, Mistral AI, Requesty, SEA-LION API y UnoRouter.

Proveedores opcionales (19 fichas): Speechify (solo TTS), Airforce API, AnyAPI.ai, DreamPrompting, OrcaRouter, Routeway, Ollama Cloud · API key, Cerebras, OpenAI, Anthropic, DeepSeek, Grok/xAI, MiniMax, Alibaba/Qwen, Treblo · música, Stable Audio · música, Mubert · música, Soundraw · música y Beatoven · música. La conexión específica y las capacidades anunciadas pueden requerir plan, permiso, revisión del proveedor o un adaptador local aún no implementado.

La cifra corresponde al catálogo base; en la interfaz, cualquier proveedor opcional con dos o más cuentas habilitadas se muestra en Servicios generales, salvo GitHub. Esto no modifica el estado de habilitación ni certifica gratuidad. Al modificar el catálogo, revisar interfaz, rankings y documentación. No usar listas anteriores de 12 proveedores ni describir todos como gratuitos. Ocho pasarelas recientes —Agnes, Aion, BazaarLink, Hugging Face, Mistral, Requesty, SEA-LION y UnoRouter— están en Servicios generales. Cada proveedor conserva su ranking y la consolidación global depende de las actualizaciones válidas de esa instalación.

Para detalles de los rankers compartidos, filtros de gratuidad por modelo, pruebas y límites de cuenta, consultar [docs para agentes/PASARELAS_Y_RANKING_GRATUITO.md](docs%20para%20agentes/PASARELAS_Y_RANKING_GRATUITO.md). Para la integración de capacidades y contratos HTTP, leer [docs para agentes/GUIA_AGENTES.md](docs%20para%20agentes/GUIA_AGENTES.md), `/v1/capabilities` y las fichas bajo `docs para agentes/agentes/`.

---

## Verdades del Proyecto

- **Aislamiento de secretos**: Las claves de API se gestionan mediante las variables de entorno locales; los asistentes de esta copia mantienen los secretos en `.env`/`granja.env`. No se copian credenciales a `cuentas.json`, rankings, documentos ni registros. Revisar los flujos antes de cambiar el almacenamiento.
- **Metadata en `cuentas.json`**: Guarda exclusivamente IDs de cuenta, puertos asignados, emails y rutas de instancias.
- **Formato OpenAI-Compatible**: Cualquier cliente que soporte la API de OpenAI (vía `baseURL` y `apiKey`) puede conectarse directamente a `http://127.0.0.1:8080/v1`.
- **Rutas lógicas y auto-detección**: Soporta perfiles explícitos (`auto`, `cheap`, `reasoning`, `tools`, `vision`) y también infiere la ruta inspeccionando el contenido de la petición (imágenes, herramientas JSON, prompts de análisis).
- **Ranking global dinámico**: Mantiene un índice de rendimiento, salud y capacidades de cada modelo/proveedor que se actualiza periódicamente.

---

## Flujo de una Petición HTTP

```
[ Cliente / Agente ] 
       │  POST /v1/chat/completions
       ▼
[ Proxy FastAPI (Puerto 8080) ]
       │ 1. Infiere la ruta lógica (auto, cheap, reasoning, tools, vision)
       │ 2. Consulta el Ranking Global & Salud en vivo
       │ 3. Selecciona el mejor proveedor + cuenta + modelo según score
       │ 4. Limpia los campos internos (ej. 'route') antes de enviar upstream
       ▼
[ Proveedor activo del catálogo scripts/catalogo_servicios.py, con cuenta apta para esa ruta ]
       │ Responde 200 OK (o error 429/403/402)
       ▼
[ Proxy Normaliza Stream SSE / JSON ] ──► [ Registra estadísticas y actualiza estado ]
       │
       ▼
[ Respuesta al Cliente ]
```

---

## Rutas Lógicas y Capacidades

- `auto` / `default`: Rotación inteligente sobre los mejores candidatos del ranking global.
- `cheap`: Filtra y selecciona los modelos de menor costo o más ligeros.
- `reasoning`: Selecciona modelos de pensamiento profundo (DeepSeek R1, Qwen Reasoning, Gemini, Nemotron).
- `tools`: Selecciona modelos probados para llamadas a funciones (function calling) y agentes autónomos.
- `vision`: Selecciona modelos multimodales aptos para procesar imágenes.

---

## Manejo de Fallos y Cooldowns

- **429 (Rate Limit)**: El proxy coloca la cuenta en cooldown (30 minutos) y conmuta inmediatamente al siguiente candidato o proveedor (failover).
- **403 (Forbidden / Modelo agotado)**: Marca ese modelo específico como agotado en la cuenta o pone la cuenta en estado parcial, evitando repetir el fallo.
- **402 (Sin Crédito)**: Inhabilita la cuenta por 24 horas.
- **503 (Servicio no disponible)**: Se activa si ningún proveedor upstream responde o no hay rutas saludables.

---

## Despliegue Multiplataforma (Windows y Linux)

Núcleo IA se ejecuta con sus instaladores nativos en **Windows** o **Linux** y también en **WSL 2**. En Windows no requiere bash ni WSL si se utiliza el instalador nativo. La compatibilidad OpenAI aplica a las rutas implementadas; no implica compatibilidad total con todas las extensiones de todos los clientes.

### Instalación Nativa en Windows
1. Haz doble clic en `instalar_nucleo_ia.bat`. Si no tienes Python, el instalador intentará descargarlo automáticamente.
2. Agrega tus API Keys haciendo doble clic en `agregar_cuentas.bat`.
3. Inicia el proxy haciendo doble clic en `iniciar_todo.bat`.
4. El proxy FastAPI quedará accesible en `http://127.0.0.1:8080/v1`.

*(Alternativamente, puedes usar la CLI universal en tu terminal CMD / PowerShell: `python granja.py install`, luego `python granja.py start`)*.

### Instalación en Linux / WSL 2
1. **Instalar dependencias**: `sudo apt update && sudo apt install -y curl jq python3 python3-venv`.
2. **Ejecutar instalador**: `bash instalar_nucleo_ia.sh` (prepara el entorno virtual y configuraciones).
3. **Agregar claves**: Usa `bash agregar_cuentas.sh` o edita `.env`.
4. **Vincular Ollama Cloud (Opcional)**: `bash scripts/agregar_ollama.sh`.
5. **Arrancar proxy**: `bash iniciar_todo.sh` o `python granja.py start`.

---

## CLI Universal (`granja.py`)

Núcleo IA proporciona un gestor en Python, llamado `granja.py`, con comandos para administrar la instalación:

- `python granja.py install`: Instalación maestro inicial.
- `python granja.py start`: Inicia el proxy central en `8080`.
- `python granja.py stop`: Detiene todos los procesos y libera los puertos limpiamente.
- `python granja.py status`: Muestra el estado operativo de cuentas, salud y métricas en tiempo real.
- `python granja.py models`: Lista todos los modelos virtuales disponibles en `/v1/models`.
- `python granja.py rank`: Ejecuta consultas y pruebas de ranking para los proveedores configurados y consolida el ranking global. Las solicitudes pueden consumir cuota o saldo; requerir autorización explícita antes de ejecutarlo con cuentas reales.
- `python granja.py config`: Interfaz interactiva de configuración general.
- `python granja.py add-key`: Abre la carga interactiva de credenciales. Consultar las fichas actuales en Mis servicios/`scripts/catalogo_servicios.py`; no mantener una lista parcial de proveedores aquí.
- `python granja.py add-ollama`: Asistente interactivo multiplataforma para vincular cuentas SSH de Ollama.
- `python granja.py sync-exportable`: Genera la carpeta pública predeterminada sin credenciales.
- `python scripts/sincronizar_exportable.py --destino "RUTA"`: Regenera una copia pública en una ruta explícita.

---

## Separación de Entornos

El flujo de trabajo distingue dos entornos:
1. La carpeta privada activa contiene claves reales en `.env`, correos en `cuentas.json` y estado local. NUNCA debe compartirse.
2. La copia pública se regenera con el sincronizador, queda sanitizada y puede renombrarse o moverse. Debe aprobar `scripts/validar_exportable.py` antes de compartirse.

## Traslado de cuentas desde el Centro de control

- La pestaña **Trasladar cuentas** vive en `ui/trasladar_cuentas.html` y `ui/trasladar_cuentas.js`; la vista general enlaza a ella desde `ui/centro_control.html`.
- Las rutas locales `/api/trasladar/crear` y `/api/trasladar/cargar` se sirven en `scripts/mis_servicios.py` y requieren la sesión local `X-Nucleo-Session`.
- `scripts/transferencia_cuentas.py` genera un ZIP de formato versionado con `cuentas.json` y solo variables de credenciales del `.env`/`granja.env`. No empaquetar el resto del entorno, rankings ni sesiones temporales.
- La importación combina cuentas por proveedor e identificador, conserva valores locales de claves que ya tienen contenido y crea respaldos privados previos bajo `state/config_backups/`. Mantener validación estricta del ZIP, tamaño y estructura.
- El ZIP contiene claves sin cifrar. La interfaz debe advertirlo y recomendar transferencia privada y eliminación posterior. Nunca registrar ni imprimir claves durante creación o importación.

---

## Estado que muestra el Centro de control

- `scripts/gestor_panel_operativo.py` acepta `/healthz` y `/status` solo si `state/proxy_runtime.json` y el PID confirman que el proxy se ejecuta desde el mismo directorio raíz.
- Los `ranking_*.json` que trae una copia exportable son catálogos precargados. El Resumen muestra modelos con cuentas registradas y actividad local observada en `state/route_health.json`.
- `state/rankings_precargados.json` indica que Rankings debe ocultar esos catálogos hasta que un escaneo completo actualice correctamente los proveedores configurados. El sincronizador crea la marca; el panel y `ranking_global.py` la quitan al completar esa comprobación.
- No usar el puerto compartido como prueba suficiente de que un proxy pertenece a esta instalación: varias copias pueden configurar `8080`.

## Mantenimiento y Buenas Prácticas

1. **Nunca subir secretos a Git**: Mantener `.env`, `granja.env` y `cuentas.json` fuera del control de versiones.
2. **Refrescar rankings periódicamente**: Ejecutar `python granja.py rank` tras agregar credenciales nuevas.
3. **Exportación segura**: Después de cada cambio, regenera la copia pública y ejecuta `python scripts/validar_exportable.py "RUTA"` antes de compartirla.
4. **Validación previa**: Ante cambios internos en el core (`proxy/*.py`), ejecuta las pruebas automatizadas incluidas: `python granja.py test`.

## Instrucciones específicas de capacidades

Para integrar multimedia, consultar [docs para agentes/GUIA_AGENTES.md](docs%20para%20agentes/GUIA_AGENTES.md) y la ficha correspondiente en `docs para agentes/agentes/`: `tts.md`, `imagenes.md`, `videos.md`, `vision.md`, `transcripcion.md` o `embeddings.md`. Estas fichas describen endpoints, campos, proveedores, credenciales y reglas de reintento.


## Pasarelas adicionales y gratuidad

Para integrar o mantener Agnes, Aion, Airforce, AnyAPI, BazaarLink, DreamPrompting, Hugging Face Inference Providers, OrcaRouter, Requesty, Routeway, SEA-LION, UnoRouter, Ollama Cloud API o Mistral, seguir `docs para agentes/PASARELAS_Y_RANKING_GRATUITO.md`. El ranking exige evidencia de precio cero específica de la ruta y una prueba de chat; créditos promocionales, cuota de cuenta y acceso autenticado no sustituyen esa evidencia. BazaarLink debe conservar `X-Free-Fallback: false`; DreamPrompting debe impedir la sustitución del modelo durante probes. Las capacidades secundarias de catálogo no deben presentarse como integradas hasta que exista una ruta y prueba específica.
