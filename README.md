# monitor-de-indicadores-banxico

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

La documentación interactiva queda disponible en `/docs`. Las consultas de observaciones aceptan filtros por serie, fechas y paginación; las estadísticas aceptan agrupaciones por año, mes y año-mes; el historial de ejecuciones está disponible en `GET /ingestas/historial`.

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
