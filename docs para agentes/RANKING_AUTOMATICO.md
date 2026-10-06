# Ranking automático de Núcleo IA

## Qué comando se ejecuta

El punto de entrada único es:

```bash
venv/bin/python -B scripts/ranking_global.py
```

No es necesario ejecutar manualmente un ranking por proveedor. El ranking general:

1. actualiza el catálogo de Ollama;
2. ejecuta los rankings de todos los proveedores;
3. acepta solamente archivos regenerados en esa ejecución;
4. comprueba generación real y compatibilidad con herramientas;
5. actualiza la evidencia pública de Artificial Analysis y LMArena;
6. calcula y guarda el ranking general.

Si falla una fuente, su archivo anterior no se presenta como actualizado. Si falla el catálogo de Ollama, tampoco se reconstruye Ollama con información vieja.

Consulta también [Pasarelas y modelos gratuitos](PASARELAS_Y_RANKING_GRATUITO.md) para las reglas de catálogo, precios, pruebas, cuentas y capacidades secundarias.

## Admisión y orden

Son decisiones diferentes:

- Un modelo entra al ranking principal cuando responde y cumple las capacidades mínimas de herramientas y razonamiento.
- Su posición depende de evidencia externa, herramientas reales, trabajo agéntico, instrucciones, contexto útil y multimodalidad.
- Una prueba de calidad baja modifica la posición, pero no elimina un modelo que cumplió los mínimos.
- Un timeout en la prueba de herramientas se considera inconcluso y no se trata como incapacidad.

## Configuración sencilla

El archivo `ranking_config.json` permite modificar el comportamiento sin tocar Python.

```json
{
  "contexto_objetivo": 150000,
  "contexto_excluye": false,
  "pesos": {
    "inteligencia_aa": 24,
    "preferencia_lmarena": 6,
    "herramientas": 25,
    "trabajo_agentico_lmarena": 10,
    "trabajo_agentico_aa": 5,
    "instrucciones": 15,
    "contexto_util": 10,
    "multimodal": 5
  }
}
```

- `contexto_objetivo`: cantidad de tokens considerada suficiente.
- `contexto_excluye: false`: un contexto menor resta puntuación, pero el modelo permanece.
- `contexto_excluye: true`: los modelos por debajo del objetivo pasan al ranking secundario.
- `pesos`: importancia relativa de cada área. El programa los normaliza automáticamente a 100.

La latencia y la cantidad de parámetros no alteran el puntaje principal.

## Evidencia de Artificial Analysis

El programa descarga el listado público mediante Jina y guarda una copia validada en `state/ranking_aa_public_cache.json`.

- Rechaza respuestas con menos de 50 fichas.
- Rechaza una reducción anómala superior al 35 % respecto del caché anterior.
- Elimina fichas repetidas.
- Solo relaciona identidades exactas o alias explícitos.
- Una coincidencia aproximada se conserva únicamente como diagnóstico.
- Si la red falla, reutiliza el último caché válido.
- Si no existe caché, aplica valores neutrales y reduce la cobertura de evidencia.

## Evidencia de LMArena

El programa consulta el dataset público `lmarena-ai/leaderboard-dataset` y guarda `state/ranking_lmarena_public_cache.json`.

- `text_style_control/latest` aporta preferencia conversacional con control de estilo.
- `agent/latest` aporta desempeño observado en sesiones agénticas.
- Se usa el límite inferior del intervalo de confianza para ordenar conservadoramente.
- Las puntuaciones se convierten a percentiles dentro de cada fuente; no se mezclan escalas crudas.
- Solo se unen nombres canónicos exactos. Una similitud textual no transfiere resultados.
- Si la red falla, se reutiliza el último caché completo; sin caché se usa 50 neutral y baja la cobertura.

## Cómo leer el resultado

El archivo principal es `state/ranking_global.json`. Cada modelo contiene:

- `puntaje`: valor final entre 0 y 100;
- `puntaje_origen`: puntaje anterior del proveedor, conservado para diagnóstico;
- `componentes_calidad`: resultados separados por área;
- `cobertura_evidencia`: porcentaje del puntaje respaldado con información disponible;
- `confianza`: indicador derivado de la cobertura;
- `evidencia_aa`: ficha externa, índice original y seguridad de la identidad;
- `evidencia_lmarena`: puntuaciones, límites de confianza, cantidad de votos o sesiones y fecha;
- `evidencia_local`: resultado de la prueba real de herramientas;
- `modelo_id`: ruta exacta que utilizará el núcleo;
- `proveedor`: servicio al que pertenece esa ruta.

Las rutas nunca se fusionan. Dos servicios que ofrecen el mismo modelo conservan entradas independientes para mantener la rotación y el failover.

## Alcance actual

La llamada básica de herramientas ya se prueba en Ollama, NVIDIA, OpenRouter, Groq, TokenRouter, xKiro, Token Harbor y Google. Las respuestas se validan por nombre de función y argumentos exactos, sin utilizar otro LLM como juez.

## Token Harbor: rutas gratuitas por cuenta

`scripts/ranking_tokenharbor.py` consulta el catálogo autenticado actual y solo
considera IDs que terminan exactamente en `:free`. Nunca prueba la ruta base
paga. Cada candidata debe responder con la cuenta configurada y superar pruebas
independientes de conversación, llamada de herramienta y razonamiento. Las que
responden pero fallan un mínimo agéntico quedan en el ranking secundario; las
retiradas, vencidas, sin consentimiento, sin elegibilidad o sin cuota quedan en
`ranking_rechazados_probe` y no entran al ranking global.

Token Harbor renueva la cuota por ventanas personales de siete días. Sus rutas
gratuitas pueden retener prompts y respuestas, por lo que no deben recibir
secretos, repositorios privados ni datos confidenciales.

## xKiro: gratuidad y restricciones reales

El ranking de xKiro consulta el catálogo vivo y exige `access_tier=free`, precio
de entrada cero y precio de salida cero. Como el catálogo es público y no prueba
que una cuenta concreta tenga acceso, cada ruta se ejecuta con la clave local.
Los modelos con herramientas y razonamiento solo entran al ranking principal si
devuelven la función y los argumentos exactos de la prueba. Los modelos que
responden pero no cumplen esos mínimos quedan en el ranking secundario; los
`403`, `402`, `429`, errores de proveedor y respuestas inválidas quedan fuera de
ambos rankings utilizables y se conservan como diagnóstico en
`state/ranking_xkiro.json`.

La cuota gratuita es diaria y compartida por la cuenta. El actualizador registra
la cuota antes y después de las pruebas mediante `GET /v1/usage`, sin guardar
identidad del usuario ni la clave en los archivos de ranking.

El componente de seguimiento de instrucciones admite resultados deterministas futuros, pero mientras no exista una batería común repetida utiliza el valor neutral 50. Esto queda visible como menor cobertura; no se inventa una puntuación.

## Consolidar sin volver a consultar proveedores

Para diagnóstico se puede usar:

```bash
venv/bin/python -B scripts/ranking_global.py --no-refresh
```

Esta opción no es la ejecución normal: utiliza los rankings locales existentes y recalcula únicamente la evidencia y el orden global.

## Cohere: modelos gratuitos y capacidades secundarias

Cohere se actualiza consultando `GET /v1/models`; ya no depende de una lista
manual. La instalación personal usa `COHERE_KEY_MODE=trial`: una clave Trial
permite probar los modelos y endpoints sin cargo, aunque con límites de uso.
Si se cambia a `production` o a un modo desconocido, las rutas de Cohere no se
incorporan al ranking personal para evitar costos accidentales.

Además del ranking de chat/agentes, se guarda
`state/ranking_cohere_capacidades.json` con pruebas independientes para
embeddings, embeddings de imagen, reranking, transcripción de audio y Parse
de documentos. Estas familias no se mezclan con los LLM agénticos: sirven para
las funciones secundarias del núcleo y conservan su propio resultado y estado.


## Uso desde el Centro de control

El Centro de control ofrece una forma visual de ejecutar y revisar el ranking sin abrir una terminal. En **Rankings → Por servicio**, elegí un proveedor y pulsá **Volver a probar este servicio** para actualizar solo ese proveedor. En **General**, el mismo botón actualiza todos los proveedores configurados y genera el ranking global. **Actualizar todos** usa ese mismo flujo completo: `ranking_global.py` ejecuta cada ranker una sola vez y consolida únicamente las fuentes válidas de esa ejecución. No se hace una pasada previa que duplique llamadas ni cuotas.

Las pasarelas de `ranking_pasarelas_free.py`, Mistral incluido, comparten ese comprobador y reciben el identificador del proveedor elegido. El panel no busca un archivo de ranking distinto por pasarela. Los demás servicios siguen usando su comprobador dedicado; Cerebras, DeepSeek, Grok, MiniMax y Alibaba comparten `ranking_openai_compatible.py` con su identificador correspondiente.

Mientras trabaja, el panel conserva el ranking anterior y muestra el servicio actual, el modelo informado por el comprobador, la etapa, el tiempo transcurrido, el último evento y el resultado de cada etapa. Los eventos no incluyen claves API. Si una prueba no emite avances durante aproximadamente 90 segundos aparece una advertencia; a los dos minutos se detiene de manera preventiva. **Detener pruebas** termina la comprobación activa y conserva los datos anteriores.

La casilla **Conservar mi orden al actualizar** mantiene el orden manual que se movió con el mouse. Si se desmarca, un resultado automático correcto reemplaza el orden manual de la vista actual. Un error no borra el ranking anterior.

El modo de rotación está separado del ranking de capacidades. En el ranking general se puede elegir prioridad estricta, alternar cuentas o alternar puestos y cuentas. `0` en la cantidad de puestos significa todos; los rankings secundarios y de capacidades no usan esta rotación general.

## Pasarelas OpenAI-compatible adicionales

El ranker `scripts/ranking_pasarelas_free.py <proveedor>` cubre los gateways definidos en `CONFIG` y Mistral. Consulta catálogo con la clave de cada cuenta, mantiene cada ruta por proveedor y aplica el puntaje común. Solo una ruta con señal explícita de gratuidad puede pasar al conjunto gratis. Una cuenta que devuelve el catálogo no se considera por eso utilizable: cada candidata de chat requiere probe; para `auto` también debe superar la herramienta exacta y la comprobación de razonamiento. `cuentas_compatibles` conserva la cuenta que se probó para que la rotación no envíe el modelo a una cuenta no verificada.

Las capacidades secundarias se guardan aparte en `rankings_capacidades`; su presencia indica descubrimiento en metadatos, no adaptador de tarea disponible. La diferencia, los proveedores y las particularidades de las pruebas se documentan en [PASARELAS_Y_RANKING_GRATUITO.md](PASARELAS_Y_RANKING_GRATUITO.md).
