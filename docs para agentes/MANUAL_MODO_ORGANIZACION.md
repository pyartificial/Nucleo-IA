# Manual del modo Profesional

Esta guía explica cómo preparar una instalación compartida con controles claros. El nombre visible del modo es **Profesional**; “organización” se conserva únicamente en nombres antiguos de archivos.

## Índice

1. [Cuándo elegir Profesional](#cuándo-elegir-profesional)
2. [Preparación segura](#preparación-segura)
3. [Claves y roles](#claves-y-roles)
4. [Red y protección](#red-y-protección)
5. [Cuentas y correos](#cuentas-y-correos)
6. [Rankings y actividad](#rankings-y-actividad)
7. [Políticas de datos](#políticas-de-datos)
8. [Operación y recuperación](#operación-y-recuperación)
9. [Volver a Personal](#volver-a-personal)

## Cuándo elegir Profesional

Elegí Profesional cuando dos o más personas usan el mismo proxy, cuando un agente se ejecuta en otra computadora o cuando necesitás separar quién consume de quién administra. Para una sola persona en una PC, Personal es más sencillo y mantiene el servidor en loopback.

## Preparación segura

1. Detené Núcleo IA si ya está funcionando.
2. Creá un respaldo privado: `python granja.py backup CARPETA_VACIA`.
3. Revisá qué proveedores pueden recibir información y qué cuotas están disponibles.
4. En el asistente elegí **Profesional** o establecé `PERFIL_USO=profesional`.
5. Reiniciá y comprobá `/healthz`, `/readyz` y `/status`.

El cambio de perfil no borra correos, cuentas ni autorizaciones. Cambia las reglas de acceso al panel y al proxy.

## Claves y roles

Definí dos valores distintos:

- `NUCLEO_API_KEY`: clave de consumo para agentes y aplicaciones.
- `NUCLEO_ADMIN_KEY`: clave de administración para estado, rankings, cuentas y reparaciones.

Guardá la clave administrativa únicamente en manos de la persona responsable. No la pegues en un agente, porque un agente solo necesita consumir. Cambiá ambas claves si una persona deja de tener acceso o si sospechás que fueron expuestas.

## Red y protección

Usá `PROXY_HOST=127.0.0.1` si todo corre en la misma máquina. Para acceso por red, colocá Núcleo IA detrás de un proxy inverso con HTTPS, firewall y control de origen. Completá `ALLOWED_HOSTS` con nombres concretos y `CORS_ALLOW_ORIGINS` con los sitios reales; no uses `*` en Profesional.

No publiques el puerto 8080 directamente en Internet. Si un contenedor necesita conectarse, permití solo la red necesaria y conservá autenticación. `PERMITIR_OLLAMA_REMOTO=false` mantiene las instancias Ollama locales; activalo solo con una red protegida.

## Cuentas y correos

El responsable conserva los correos reales para saber qué cuenta falló y reparar solo esa autorización. No se anonimizan automáticamente. El pozo de correos puede reutilizarse entre proveedores dentro de la instalación autorizada.

Los consumidores no necesitan ver claves ni modificar cuentas. Si una cuenta Ollama falla, el responsable identifica el correo y pulsa **Volver a autorizar esta cuenta**. No borres todas las cuentas para solucionar una sola.

## Rankings y actividad

En **Centro de control → Rankings**, el responsable puede revisar General, Por servicio y Capacidades especiales. Cada modelo muestra sus cuentas, su estado y su última prueba. **Cuenta preferida** elige el primer correo del modelo; **Automática: N cuentas disponibles** conserva la selección automática.

**Volver a probar este servicio** comprueba un proveedor. **Actualizar todos** comprueba primero cada proveedor y después el ranking global. El panel muestra servicio, modelo, etapa, avance, último evento, tiempo y errores. Si no hay avances durante aproximadamente 90 segundos avisa; después de dos minutos detiene el proceso bloqueado. El ranking anterior permanece mientras se trabaja.

La rotación general se configura por separado: prioridad estricta, alternar cuentas o alternar puestos. En este último caso `0` incluye todos los puestos. Los rankings de capacidades especiales tienen orden propio y no modifican la rotación general.

## Políticas de datos

Definí por escrito si se permite cloud, qué proveedores pueden recibir prompts, qué capacidades multimedia están autorizadas y si solo se aceptan rutas gratuitas. `PROCESAMIENTO_PERMITIDO=solo_local` evita envíos cloud, pero no puede hacer funcionar una capacidad que no exista en un modelo local.

Token Harbor puede tener condiciones de retención propias. Informá a los usuarios antes de permitirlo. Imágenes, audios, documentos y prompts pueden salir de la red cuando se elige una ruta cloud.

## Operación y recuperación

Revisá `/healthz` para saber si vive el proceso y `/readyz` para saber si está preparado. Usá `/status` y `/rankings` con la clave administrativa. Si una prueba falla, guardá el último evento, corregí la cuenta y repetí solo ese proveedor.

Antes de actualizar el programa, detené el proxy y creá un respaldo. Validá la copia pública con `scripts/validar_exportable.py` antes de distribuirla. No restaures sesiones como si fueran autorizaciones vigentes: los proveedores pueden exigir una nueva autorización.

## Volver a Personal

1. Detené Núcleo IA.
2. Cambiá el perfil a `personal` desde el asistente o `.env`.
3. Revisá que `PROXY_HOST=127.0.0.1` y que no queden reglas de exposición remota innecesarias.
4. Reiniciá y comprobá el estado.

Las cuentas, correos y rankings se conservan. Solo se desactiva la separación reforzada de consumo y administración.

## Lista de comprobación

- Hay un respaldo privado fuera de la carpeta pública.
- Las claves de consumo y administración son diferentes.
- HTTPS, firewall, hosts y orígenes están restringidos.
- Los usuarios conocen qué datos salen a cloud.
- El responsable sabe identificar cuentas por correo.
- El panel de rankings tiene un orden y una rotación documentados.
- La exportable no contiene credenciales ni informes internos.
