# Contributing

Gracias por ayudar.

## Antes de proponer cambios
- revisá que no haya secretos en lo que vas a subir
- no toques `state/` ni archivos generados a mano si no hace falta
- si cambiás comportamiento, actualizá la documentación
- si cambiás el ruteo o el manual, actualizá los Markdown correspondientes

## Flujo recomendado
1. creá una rama nueva
2. hacé cambios pequeños
3. probá al menos:
   - `bash -n scripts/*.sh`
   - `python3 -m py_compile proxy/*.py scripts/*.py`
4. abrí pull request con descripción clara

## Buenas prácticas
- un tema por PR
- mensajes de commit cortos y concretos
- si agregás un script nuevo, documentalo en `README.md`
- si cambiás configuración, actualizá `.env.example`

## No incluir
- claves API
- archivos de sesión
- dumps locales
- logs grandes
