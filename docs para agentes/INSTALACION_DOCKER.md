# Despliegue con Docker Compose

Este despliegue ejecuta el proxy en un contenedor sin privilegios, guarda datos y estado en volúmenes persistentes y exige autenticación. El puerto del host queda enlazado a `127.0.0.1` por defecto.

## Preparar credenciales

Copiá `.env.example` a `.env`, restringí sus permisos y definí dos secretos distintos:

```sh
cp .env.example .env
chmod 600 .env
openssl rand -hex 32
```

Usá una salida para `NUCLEO_API_KEY` y otra para `NUCLEO_ADMIN_KEY` dentro de `.env`. No subas ese archivo al repositorio. Compose lo usa para interpolar las variables y las pasa al contenedor; la aplicación no recibe el `.env` montado.

## Iniciar

Desde la raíz del proyecto:

```sh
docker compose up -d --build
docker compose ps
```

La API queda en `http://127.0.0.1:8080/v1`. Usá `NUCLEO_API_KEY` como clave del cliente. Centro de control y administración requieren `NUCLEO_ADMIN_KEY`; el contenedor trabaja en modo Profesional.

Los datos de cuentas y configuración persisten en `nucleo-data`; el estado, sesiones y almacenes locales persisten en `nucleo-state`. `docker compose down` conserva ambos volúmenes. No uses `docker compose down -v` salvo que quieras borrar todos los datos persistentes.

## Acceso remoto

No publiques directamente el puerto del contenedor en una interfaz de red. Para acceso desde la empresa, colocá un proxy inverso con HTTPS y autenticación de red delante del puerto local, limita el firewall al proxy y agrega únicamente los orígenes necesarios en `CORS_ALLOW_ORIGINS`. Si cambiás `NUCLEO_PUBLISHED_PORT`, el enlace sigue limitado a loopback.

## Cuentas y catálogos de arranque

Agregá proveedores desde “Mis servicios” o usá `NUCLEO_STARTUP_CONFIG_PATH`. Para el segundo caso, crea un archivo local de configuración y un override de Compose que lo monte como solo lectura en `/run/secrets/nucleo-startup.json`, y define esa ruta dentro del servicio. El archivo puede contener API keys en texto claro: restringí sus permisos en el host y no lo incluyas en la imagen. El aprovisionamiento declarativo puede crear el primer administrador; la contraseña se referencia desde una variable de entorno y no se guarda en el JSON.

Las rutas a Ollama en `127.0.0.1` se refieren al propio contenedor. Para usar Ollama instalado en el host, configura un endpoint compatible accesible desde Docker, restringe su red y evita enviar credenciales si es un runtime local sin autenticación.

La imagen usa el health endpoint local `/healthz`; el healthcheck no requiere enviar una clave API. El contenedor corre como UID `10001`, elimina todas las capabilities Linux, activa `no-new-privileges` y monta la raíz de archivos como solo lectura.
