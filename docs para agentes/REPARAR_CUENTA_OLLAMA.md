# Reparar una cuenta de Ollama

Cuando una cuenta de Ollama se desconecta, no hay que volver a cargar todas las cuentas.

## Windows

Abrir con doble clic:

```text
reparar_ollama.bat
```

El asistente muestra el número de cuenta, correo, puerto, carpeta y estado. Elegí únicamente la cuenta que falla.

## Linux

Abrir:

```text
reparar_ollama.sh
```

También se puede ejecutar desde una terminal con:

```bash
bash reparar_ollama.sh
```

## Qué hace la reparación

1. Reutiliza el mismo ID, por ejemplo `acc7`.
2. Reutiliza el mismo puerto.
3. Reutiliza la misma carpeta `ollama_instances/acc7`.
4. Conserva la clave local existente.
5. Abre el enlace oficial de autorización de Ollama.
6. Comprueba la autorización.
7. Limpia el bloqueo local solo si la cuenta vuelve a responder.

No borra carpetas, no regenera claves existentes y no crea una cuenta nueva.

El estado completo también se puede consultar en:

```text
http://127.0.0.1:8080/status
```

La salida incluye `id`, `email`, `puerto`, `ollama_home`, `estado` y `last_error`.
