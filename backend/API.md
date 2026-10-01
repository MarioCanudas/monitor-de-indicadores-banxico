# API de indicadores Banxico

La aplicación se inicia desde la raíz del proyecto con:

```bash
uv run uvicorn backend.main:app --reload
```

La documentación interactiva queda disponible en `/docs` y `/redoc`. Las rutas que acceden a datos requieren `MONGODB_URI`; la ruta de ingesta requiere además `BANXICO_API`. Ambas variables se pueden definir en `.env`.

## `GET /health`

Comprueba que el proceso está levantado. No consulta MongoDB ni Banxico, por lo que sirve para health checks y para probar la instalación sin credenciales.

Respuesta `200`:

```json
{"status": "ok"}
```

## `GET /series`

Devuelve el catálogo estático de series del paquete `mercados`. Cada elemento incluye el identificador Banxico, título, unidad, frecuencia, paquetes y estado. No requiere credenciales.

## `GET /series/{series_id}`

Devuelve los metadatos de una serie concreta, por ejemplo `/series/SF43718`. Responde `404` si el identificador no pertenece al catálogo configurado.

## `GET /observaciones`

Consulta las observaciones almacenadas en `banxico_monitor.observaciones`, ordenadas de la más reciente a la más antigua. Parámetros opcionales: `series_id` filtra por serie y `limit` limita los resultados entre `1` y `1000` (predeterminado `100`). Responde `503` si MongoDB no está configurado o no está disponible.

## `POST /ingestas`

Consulta cada serie configurada en el SIE de Banxico de forma incremental. Para cada serie busca en `observaciones` su fecha más reciente y solicita a Banxico únicamente desde el día siguiente hasta `end_date`. Si la serie ya tiene datos hasta esa fecha, no realiza ninguna petición a Banxico para ella. Después transforma fechas y valores, calcula `var_pct` respecto a la observación previa e inserta únicamente los documentos faltantes. El `_id` con formato `serie_id|AAAA-MM-DD` mantiene la ingesta idempotente.

Parámetros query opcionales: `start_date` y `end_date` en formato `AAAA-MM-DD`, ambos inclusivos. El inicio predeterminado es `2024-01-01` y el fin predeterminado es la fecha actual. La respuesta `201` contiene `run_id`, totales, duración y resumen por serie. Cada resumen indica `consultada: false` y `motivo: "sin datos nuevos"` cuando no hubo que consultar Banxico. Responde `422` con un rango inválido, `502` si Banxico falla y `503` si falta una credencial o MongoDB no está disponible.

## Prueba rápida

```bash
uv run python -c "from fastapi.testclient import TestClient; from backend.main import app; c=TestClient(app); print(c.get('/health').json()); print(c.get('/series/SF43718').status_code)"
```