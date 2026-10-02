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

El backend carga las variables desde `.env` en la raíz del proyecto:

```env
BANXICO_API=token_de_banxico
MONGODB_URI=mongodb://...
MONGODB_DATABASE=banxico_monitor
MONGODB_TIMEOUT_MS=5000
DEFAULT_START_DATE=2024-01-01
MAX_PAGE_SIZE=1000
```

No se deben incluir valores reales en el repositorio. Para iniciar la API:

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
