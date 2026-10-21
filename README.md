# monitor-de-indicadores-banxico

## Cómo ejecutar el proyecto

Esta sección explica cómo preparar y ejecutar el backend y el frontend desde
cero. Los comandos deben ejecutarse desde la carpeta raíz del proyecto
(`monitor-de-indicadores-banxico`).

### Requisitos previos

Instala las siguientes herramientas antes de comenzar:

- **Python 3.14 o superior** para el backend. La versión mínima está definida
  en `pyproject.toml`.
- **Node.js y npm** para el frontend. Usa Node.js 18 o superior; se recomienda
  una versión LTS reciente.
- **MongoDB** accesible mediante una URI válida. Es necesario para consultar o
  guardar observaciones, ingestas y snapshots.
- **Git**, si vas a clonar o actualizar el proyecto.
- Un **token de Banxico** para las operaciones que consultan el SIE. Las rutas
  de salud y algunas consultas que no acceden a Banxico pueden funcionar sin
  este token.

Puedes comprobar que Python, Node.js y npm están disponibles con:

```bash
python --version
node --version
npm --version
```

En algunos equipos el comando de Python es `python3` en lugar de `python`.
Cuando sea así, sustituye `python` por `python3` en los comandos de esta guía.

### 1. Obtener el proyecto y entrar a su carpeta

Si todavía no tienes una copia local:

```bash
git clone https://github.com/MarioCanudas/monitor-de-indicadores-banxico.git
cd monitor-de-indicadores-banxico
```

Si ya tienes el proyecto, únicamente entra a la carpeta raíz:

```bash
cd monitor-de-indicadores-banxico
```

### 2. Instalar las dependencias de Python

#### Opción recomendada: `uv`

`uv` crea y administra el entorno virtual a partir de `pyproject.toml` y
`uv.lock`, por lo que instala las dependencias exactas del proyecto,
incluidas las herramientas de desarrollo necesarias para la tarea que inicia
ambos servicios.

Instala `uv` siguiendo su documentación oficial y después ejecuta:

```bash
uv sync
```

Si quieres comprobar que el entorno quedó listo:

```bash
uv run python --version
uv run poe --help
```

#### Opción alternativa: `pip`

Si no tienes `uv`, crea y activa un entorno virtual para no instalar las
dependencias globalmente:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

En Windows PowerShell, activa el entorno con:

```powershell
.venv\Scripts\Activate.ps1
```

La instalación con `pip` toma las dependencias de producción y las
dependencias de desarrollo declaradas en `pyproject.toml`, entre ellas
FastAPI, Uvicorn, PyMongo, pandas, Requests, OpenAI y `poethepoet`.

### 3. Instalar las dependencias de JavaScript

Desde la raíz del proyecto, ejecuta:

```bash
npm --prefix frontend install
```

Este comando instala las dependencias del frontend dentro de
`frontend/node_modules`, entre ellas React, Vite, TypeScript, Recharts y
Lucide React. Solo es necesario repetirlo cuando cambie
`frontend/package.json` (o cuando quieras reconstruir `node_modules`).

### 4. Configurar las variables de entorno

El backend necesita un archivo `.env` en la raíz del proyecto. Como mínimo,
configura `MONGODB_URI` y `BANXICO_API` para utilizar las operaciones que
acceden a MongoDB y Banxico:

```env
MONGODB_URI=mongodb+srv://usuario:contraseña@cluster.mongodb.net/?retryWrites=true&w=majority
MONGODB_DATABASE=banxico_monitor
BANXICO_API=token_de_banxico
```

Gmail y Azure OpenAI son opcionales: solo agrega sus variables si vas a
enviar reportes o generar resúmenes con Azure OpenAI. No compartas ni
confirmes estas credenciales en Git. La lista completa de variables y sus
usos está en [Configuración del backend](#configuración-del-backend).

### 5. Levantar backend y frontend al mismo tiempo

Esta es la forma más sencilla de ejecutar todo el proyecto.

Con `uv`:

```bash
uv run poe run
```

Con `pip`, después de activar `.venv`:

```bash
poe run
```

El comando anterior abre ambos servicios en paralelo:

- **Backend (API):** <http://localhost:8000>
- **Documentación interactiva de la API:** <http://localhost:8000/docs>
- **Frontend:** <http://localhost:8080>

Mantén abierta esa terminal mientras uses la aplicación. Para detener ambos
servicios, presiona `Ctrl+C`.

### 6. Levantar cada servicio por separado

Si prefieres usar dos terminales, deja la primera ubicada en la raíz del
proyecto y ejecuta el backend.

Con `uv`:

```bash
uv run uvicorn backend.main:app --reload --port 8000
```

Con `pip` y el entorno virtual activado:

```bash
python -m uvicorn backend.main:app --reload --port 8000
```

En una segunda terminal, inicia el frontend desde cualquier ubicación con:

```bash
npm --prefix /ruta/al/proyecto/monitor-de-indicadores-banxico run dev -- --host 0.0.0.0 --port 8080
```

Si la segunda terminal también está en la raíz del proyecto, puedes usar la
forma corta:

```bash
npm --prefix frontend run dev -- --host 0.0.0.0 --port 8080
```

Cuando Vite muestre la dirección disponible, abre
<http://localhost:8080> en el navegador. Las solicitudes del frontend se
dirigen al backend en el puerto 8000.

## Guía rápida de Git y GitHub en VS Code

Esta guía describe un flujo básico para trabajar con ramas desde la terminal integrada de VS Code. Abre la terminal con **Terminal > New Terminal**.

### 1. Actualizar el proyecto antes de trabajar

```bash
git checkout main
git pull origin main
uv sync
```

- `git checkout main` cambia a la rama principal del proyecto.
- `git pull origin main` descarga los cambios del repositorio remoto (`origin`) y los integra en la rama local `main`.
- `uv sync` instala o actualiza las dependencias declaradas en `pyproject.toml` y sincroniza el entorno virtual del proyecto.

Se recomienda ejecutar `uv sync` cada vez que se haga un `pull`, porque otra persona pudo haber agregado o actualizado una dependencia en la rama remota.

### 2. Crear una rama para los cambios

```bash
git checkout -b nombre-de-la-rama
```

Este comando crea una rama nueva llamada `nombre-de-la-rama` y cambia la terminal a ella. Usa nombres descriptivos, por ejemplo:

```bash
git checkout -b feature/consulta-indicadores
```

Para cambiar a una rama que ya existe, usa:

```bash
git checkout nombre-de-la-rama
```

### 3. Revisar y preparar los cambios

Después de modificar los archivos en VS Code, revisa qué cambió:

```bash
git status
```

`git status` muestra la rama actual y los archivos modificados, nuevos o eliminados.

Para preparar todos los cambios para el commit:

```bash
git add .
```

`git add .` agrega los cambios del directorio actual al área de preparación de Git. También puedes seleccionar archivos individualmente desde la vista **Source Control** de VS Code.

### 4. Crear un commit

```bash
git commit -m "Describe brevemente el cambio"
```

`git commit` guarda una versión de los cambios que preparaste. El texto después de `-m` es el mensaje del commit; debe explicar brevemente qué se modificó.

Ejemplo:

```bash
git commit -m "Agrega consulta de indicadores"
```

### 5. Subir la rama a GitHub

La primera vez que subas una rama nueva, usa:

```bash
git push -u origin nombre-de-la-rama
```

- `git push` envía los commits locales a GitHub.
- `origin` identifica el repositorio remoto.
- `nombre-de-la-rama` indica qué rama se va a subir.
- `-u` establece la relación entre la rama local y la remota; así, en los siguientes envíos bastará con usar `git push`.

En los siguientes cambios de la misma rama:

```bash
git add .
git commit -m "Describe el nuevo cambio"
git push
```

## Configuración del backend

El backend carga las variables desde `.env` en la raíz del proyecto. La
configuración recomendada puede mantenerse con este conjunto de variables.
No incluyas valores reales en Git ni en la documentación:

```env
# MongoDB
MONGODB_USERNAME=usuario
MONGODB_PASSWORD=contraseña
MONGODB_URI=mongodb+srv://usuario:contraseña@cluster.mongodb.net/?retryWrites=true&w=majority
MONGODB_DATABASE=banxico_monitor

# Gmail
GMAIL_USER=cuenta@gmail.com
GMAIL_KEY=contraseña_de_aplicación_de_gmail

# Proveedor de resumen narrativo
LLM_PROVIDER=azure
AZURE_OPENAI_API_KEY=clave_de_azure_openai
AZURE_OPENAI_ENDPOINT=https://recurso.openai.azure.com/
AZURE_OPENAI_DEPLOYMENT=nombre_del_deployment

# Banxico
BANXICO_API=token_de_banxico
```

### Variables y valores esperados

| Variable | Requerida | Formato y uso | Valor predeterminado |
| --- | --- | --- | --- |
| `MONGODB_USERNAME` | No | Usuario de MongoDB. Actualmente el backend no la lee; puede conservarse como dato auxiliar para construir `MONGODB_URI` fuera de la aplicación. | Sin valor |
| `MONGODB_PASSWORD` | No | Contraseña de MongoDB. Actualmente el backend no la lee; debe quedar incluida o referenciada correctamente en `MONGODB_URI`. | Sin valor |
| `MONGODB_URI` | Sí para observaciones, ingestas, snapshots e historial | URI completa y válida de conexión a MongoDB, por ejemplo `mongodb://...` o `mongodb+srv://...`. | Sin valor; la operación falla si falta |
| `MONGODB_DATABASE` | No | Nombre de la base de datos donde se guardan `observaciones`, `series_catalogo`, `ingesta_log` y `snapshots`. | `banxico_monitor` |
| `GMAIL_USER` | Solo para enviar reportes | Dirección de la cuenta Gmail que autentica el SMTP. | Sin valor |
| `GMAIL_KEY` | Solo para enviar reportes | Contraseña de aplicación de Gmail, no la contraseña normal de la cuenta. Se usa con SMTP SSL en `smtp.gmail.com:465`. | Sin valor |
| `LLM_PROVIDER` | No | Proveedor elegido por el proyecto. Actualmente el backend no la lee; la integración se determina por la configuración de Azure OpenAI. | Sin valor |
| `AZURE_OPENAI_API_KEY` | Solo para usar Azure OpenAI | Clave de autenticación del recurso o proyecto de Azure OpenAI. Si falta junto con el endpoint, el snapshot usa el resumen determinista de respaldo. | Sin valor |
| `AZURE_OPENAI_ENDPOINT` | Solo para usar Azure OpenAI | URL base del recurso o proyecto de Azure OpenAI. Los endpoints de proyectos `*.services.ai.azure.com/api/projects/...` se conectan mediante la API compatible de OpenAI. | Sin valor |
| `AZURE_OPENAI_DEPLOYMENT` | No | Nombre del deployment/modelo que se envía en `model` al generar el resumen. | `gpt-4.1-mini-ejercicio-openai` |
| `BANXICO_API` | Sí para ingestas y estadísticas | Token de acceso al SIE de Banxico. Se envía en el encabezado `Bmx-Token`. | Sin valor; la operación falla si falta |
| `CORS_ORIGINS` | No | Orígenes permitidos separados por coma, por ejemplo `https://monitor.example.com,http://localhost:8080`. El navegador bloquea las peticiones si el origen no está en la lista. | `http://localhost:8080`, `http://127.0.0.1:8080`, `http://localhost:5173` y `http://127.0.0.1:5173` |
| `CORS_ORIGIN_REGEX` | No | Expresión regular opcional para orígenes dinámicos, por ejemplo `https://.*\.example\.com`. | Sin valor |

`BANXICO_API` y `MONGODB_URI` son necesarias únicamente cuando se ejecutan
rutas que acceden a esos servicios; por ejemplo, `/health` y `/series` no
requieren credenciales. Azure OpenAI es opcional: si no se configura o el
servicio falla, se genera un resumen determinista. Gmail solo se necesita
cuando `POST /reportes/enviar` recibe `dry_run=false`; la vista previa no
abre una conexión SMTP.

La conexión usa la URI completa de `MONGODB_URI`; por eso
`MONGODB_USERNAME` y `MONGODB_PASSWORD` no se combinan automáticamente con
ella. `LLM_PROVIDER` también se conserva por compatibilidad, pero no modifica
el comportamiento actual.

Para iniciar la API:

```bash
uv run uvicorn backend.main:app --reload
```

La documentación interactiva queda disponible en `/docs`. Las consultas de observaciones aceptan filtros por serie, fechas y paginación; las estadísticas aceptan agrupaciones por año, mes y año-mes; los KPIs del periodo se consultan en `GET /kpis/{series_id}` y el historial de ejecuciones en `GET /ingestas/historial`.

### CORS para el frontend

El backend registra `CORSMiddleware` y permite por defecto los orígenes de
desarrollo (`localhost:8080`, `127.0.0.1:8080`, `localhost:5173` y
`127.0.0.1:5173`). En un despliegue real agrega el dominio público a
`CORS_ORIGINS`:

```env
CORS_ORIGINS=https://monitor.example.com
```

El frontend usa `/api` con el proxy de Vite en desarrollo. Para producción,
define `VITE_API_URL` con la URL completa del backend (por ejemplo
`https://api.example.com`) y construye con `npm --prefix frontend run build`.
Con CORS configurado, el navegador puede llamar la API aunque el frontend se
sirva desde otro dominio.

### Índices y diagnóstico de consultas

La aplicación administra 18 índices declarados en `backend/indexes.py`:

- **8 básicos:** filtros y ordenamientos de un solo campo.
- **5 avanzados:** compuestos, únicos y de cobertura.
- **5 desde Python:** agregaciones, alertas y consultas del monitor.

`get_database()` los crea una sola vez por proceso. Para revisar el inventario
y comparar planes de ejecución antes/después:

```bash
uv run python -m backend.indexes --inventory
uv run python -m backend.indexes --explain
uv run python -m backend.indexes --drop --explain
```

La opción `--drop` elimina únicamente los índices administrados (nunca `_id_`)
para medir el plan sin índices. La salida muestra `totalDocsExamined`,
`totalKeysExamined` y el índice elegido por cinco consultas representativas:
última observación por serie, histórico por periodo, KPIs con `$match`/`$group`,
snapshots recientes e historial de ingestas.

### KPIs con aggregation pipeline

`POST /snapshots` y `GET /kpis/{series_id}` calculan los KPIs con un
aggregation pipeline real sobre `observaciones`: `$match` por fecha y serie,
`$sort`, `$group` para colapsar fechas y agregar por serie, y `$project` para
extremos, mediana, volatilidad, cobertura y cambios. Python solo recibe un
documento agregado por serie; no descarga el histórico completo ni calcula los
KPIs con pandas.

### Iniciar backend y frontend

Con las dependencias del frontend instaladas en `frontend/`, puedes iniciar ambos
servicios desde la raíz del proyecto con:

```bash
uv run poe run
```

El backend queda disponible en `http://localhost:8000` y el frontend en
`http://localhost:8080`. La tarea `run` ejecuta ambos procesos en paralelo.

### Flujo completo de ejemplo

```bash
git checkout main
git pull origin main
uv sync
git checkout -b feature/nueva-funcionalidad
# Realiza los cambios en VS Code
git add .
git commit -m "Agrega nueva funcionalidad"
git push -u origin feature/nueva-funcionalidad
```

Después del `push`, la rama estará disponible en GitHub para crear un Pull Request y solicitar la revisión de otros desarrolladores.

### Hacer commit y push usando los botones de VS Code

También puedes ejecutar el mismo flujo desde la vista **Source Control**:

1. Abre **Source Control** en la barra lateral.
2. Revisa los archivos modificados y pulsa **+** para preparar cada archivo, o **Stage All Changes** para prepararlos todos.
3. Escribe el mensaje del commit en el campo superior y pulsa **Commit**.
4. Pulsa **Sync Changes** o **Push** para enviar el commit a GitHub.

Para hacer `pull`, abre el menú **...** de **Source Control** y selecciona **Pull**, o usa la paleta de comandos con **Git: Pull**. Después de cada `pull`, ejecuta `uv sync` en la terminal integrada.
