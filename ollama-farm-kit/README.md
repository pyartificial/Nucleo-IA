# ollama-farm-kit (portable)

Solo para Ollama Farm (sin OpenClaw).

## Uso rápido

```bash
cd "/ruta/de/instalacion/nucleo ia/ollama-farm-kit"
chmod +x scripts/*.sh scripts/*.py
./scripts/start-farm.sh
./scripts/stop-farm.sh
./scripts/healthcheck.sh glm:4.6:cloud
./scripts/ranker.py
```

## Archivos
- `farm.env`: plantilla pública de configuración global (instancias, puertos y contexto inicial de 32768 tokens; ajustalo según los recursos de tu equipo)
- `catalog.json`: catálogo inicial de modelos
- `scripts/start-farm.sh`: inicia la granja
- `scripts/stop-farm.sh`: detiene solo las instancias que este kit inició
- `scripts/healthcheck.sh [modelo]`: test real chat por puerto
- `scripts/ranker.py`: resumen último healthcheck
- `state/`: resultados históricos

## Copiar a otra PC
Copiá la carpeta completa y reemplazá la ruta del ejemplo por la ubicación donde la instalaste. `farm.env` se puede editar para ajustar puertos e instancias. Los historiales de comprobación se generan en `state/` al ejecutar las pruebas.
