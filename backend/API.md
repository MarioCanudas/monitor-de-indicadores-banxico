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

Consulta las observaciones almacenadas en `banxico_monitor.observaciones`, ordenadas de la más reciente a la más antigua. Parámetros opcionales: `series_id`, `start_date`, `end_date`, `skip` y `limit`. Las fechas son inclusivas; `limit` acepta valores entre `1` y `1000` (predeterminado `100`). La respuesta contiene `items` y `pagination` con `total`, `skip`, `limit` y `has_more`. Responde `404` si se solicita una serie inexistente, `422` si el rango no es válido y `503` si MongoDB no está configurado o no está disponible.

## `GET /estadisticas/{series_id}`

Consulta directamente a Banxico la serie indicada y calcula estadísticas descriptivas con pandas sobre las observaciones depuradas. La limpieza estandariza fechas y valores numéricos, quita separadores de miles y espacios, descarta fechas inválidas, marcadores de dato ausente, valores no numéricos o infinitos, y conserva una sola observación por fecha (la última recibida). Acepta `start_date` y `end_date` inclusivos, con los mismos valores predeterminados que `/ingestas`. La respuesta incluye metadatos de la serie, el periodo consultado, el total de observaciones válidas y las métricas `count`, `mean`, `std`, `min`, `25%`, `50%`, `75%` y `max` de `pandas.Series.describe()`. Las métricas no calculables se devuelven como `null`. El parámetro `agrupacion` acepta `none`, `year`, `month` o `year_month`; cuando se usa una agrupación, `grupos` contiene las métricas y el total de cada grupo. Responde `404` si la serie no está en el catálogo, `422` si el rango o la agrupación no son válidos, `502` si Banxico falla y `503` si falta `BANXICO_API`.

## `GET /ingestas/historial`

Consulta los registros de ingesta guardados en `banxico_monitor.ingesta_log`. Acepta `run_id`, `start_date`, `end_date`, `skip` y `limit`. Devuelve `items` con el resumen y el resultado por serie, junto con `pagination`. Los logs históricos sin `creado_en` se mantienen legibles y exponen ese campo como `null`.

## `POST /ingestas`

Consulta cada serie configurada en el SIE de Banxico de forma incremental. Para cada serie busca en `observaciones` su fecha más reciente y solicita a Banxico únicamente desde el día siguiente hasta `end_date`. Si la serie ya tiene datos hasta esa fecha, no realiza ninguna petición a Banxico para ella. Aplica la misma limpieza descrita en `/estadisticas`, ordena las observaciones cronológicamente y calcula `var_pct` usando como base el último valor previamente almacenado. Inserta únicamente los documentos faltantes. El `_id` con formato `serie_id|AAAA-MM-DD` mantiene la ingesta idempotente.

Parámetros query opcionales: `start_date` y `end_date` en formato `AAAA-MM-DD`, ambos inclusivos. El inicio predeterminado es `DEFAULT_START_DATE` o `2024-01-01`, y el fin predeterminado es la fecha actual. La respuesta `201` contiene `run_id`, totales, duración y resumen por serie. Cada resumen indica `consultada: false` y `motivo: "sin datos nuevos"` cuando no hubo que consultar Banxico. Responde `422` con un rango inválido, `502` si Banxico falla y `503` si falta una credencial o MongoDB no está disponible.

## Configuración

Además de `BANXICO_API` y `MONGODB_URI`, se pueden configurar `MONGODB_DATABASE`, `MONGODB_TIMEOUT_MS`, `DEFAULT_START_DATE` y `MAX_PAGE_SIZE`. La aplicación carga `.env` desde la raíz del proyecto y no devuelve estos valores en las respuestas.

## Prueba rápida

```bash
uv run python -c "from fastapi.testclient import TestClient; from backend.main import app; c=TestClient(app); print(c.get('/health').json()); print(c.get('/series/SF43718').status_code)"
```