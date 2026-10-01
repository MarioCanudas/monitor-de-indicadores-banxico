# AGENTS.md

## Propósito del proyecto

`monitor-de-indicadores-banxico` es un monitor backend para consultar, limpiar, almacenar y analizar indicadores económicos publicados por Banxico. Su objetivo es convertir datos crudos del SIE en información confiable, trazable y lista para ser consultada por un frontend o distribuida como reporte.

El proyecto busca evitar que cada consumidor tenga que conectarse directamente a Banxico o repetir la lógica de transformación y cálculo. El backend concentra esa responsabilidad y expone resultados consistentes mediante una API HTTP.

## Motivos

- Automatizar la descarga periódica de indicadores de Banxico.
- Mantener un histórico consultable de observaciones por serie y fecha.
- Evitar duplicados cuando una misma ventana de datos se procesa más de una vez.
- Centralizar el cálculo de KPIs, variaciones y estadísticas descriptivas.
- Detectar cambios relevantes mediante reglas de alerta claras y reproducibles.
- Generar análisis y reportes a partir de cifras previamente calculadas y verificables.
- Mantener separado al frontend de Banxico, MongoDB y los servicios de análisis.

## Objetivos funcionales

1. Consultar una o varias series del SIE de Banxico para un rango de fechas.
2. Convertir las respuestas de Banxico a documentos estructurados y utilizables.
3. Descartar valores inválidos o sin dato, como `N/E`, sin interrumpir todo el proceso.
4. Calcular, cuando corresponda, año, mes y variación porcentual contra la observación anterior.
5. Guardar las observaciones en MongoDB con un identificador determinista por serie y fecha.
6. Calcular agregaciones directamente en MongoDB cuando el cálculo pertenezca a la capa de datos.
7. Obtener estadísticas descriptivas con pandas para análisis por serie, año y mes.
8. Construir snapshots con series, KPIs y alertas embebidos para facilitar su lectura y publicación.
9. Generar texto explicativo usando únicamente los números presentes en el snapshot.
10. Crear reportes por correo de forma segura, con modo de vista previa antes de realizar un envío real.
11. Exponer los datos y operaciones principales mediante endpoints de FastAPI.

## Flujo esperado del backend

```text
Banxico SIE
    ↓
Descarga del histórico
    ↓
Limpieza y normalización
    ↓
MongoDB: observaciones
    ↓
KPIs y agregaciones
    ↓
Estadística descriptiva
    ↓
Snapshot con alertas
    ↓
Análisis redactado y validado
    ↓
MongoDB: snapshots
    ↓
API FastAPI y reportes
```

## Principios de implementación

### Datos y limpieza

- Tratar las fechas y valores recibidos desde Banxico como datos externos no confiables hasta validarlos.
- Convertir fechas de texto a tipos de fecha y valores numéricos a `float` cuando sea posible.
- Ignorar o registrar observaciones sin valor numérico sin detener innecesariamente toda la ingesta.
- Conservar una estructura consistente para que las consultas y estadísticas sean predecibles.

### MongoDB

- Usar MongoDB como el único sistema de persistencia del proyecto.
- Mantener una colección de observaciones históricas y una colección de snapshots calculados.
- Usar identificadores deterministas, por ejemplo `serie|fecha`, para que la ingesta sea idempotente.
- Preferir `insert_many` con manejo de duplicados para la ingesta y `upsert` para actualizar snapshots.
- Calcular en MongoDB los KPIs que puedan expresarse como agregaciones, evitando trasladar grandes volúmenes a Python sin necesidad.
- Crear índices adecuados para las consultas por serie, fecha y snapshot.

### Análisis y alertas

- Calcular primero las cifras y después generar el texto explicativo.
- El análisis redactado no debe inventar cifras ni sustituir los valores calculados.
- Validar el resultado del análisis contra el snapshot; si no es válido, usar una plantilla fija.
- Mantener las reglas de alerta explícitas, configurables y fáciles de probar.

### API y reportes

- El frontend debe comunicarse únicamente con la API, nunca directamente con Banxico o MongoDB.
- Mantener separados los endpoints de consulta, snapshots y envío de reportes.
- Usar `dry_run` por defecto para generar una vista previa del correo sin enviarlo.
- Restringir los envíos reales a las direcciones configuradas en `EMAIL_TO`.
- No exponer credenciales, cadenas de conexión ni datos sensibles en respuestas o logs.

## Criterios de calidad

- Las operaciones de ingesta deben poder repetirse sin duplicar observaciones.
- Las respuestas de la API deben ser consistentes aunque no haya datos para una serie o periodo.
- Los cálculos críticos deben contar con pruebas para datos normales, valores faltantes, duplicados y cambios abruptos.
- Los errores externos, como fallos de Banxico, MongoDB o correo, deben registrarse con contexto y comunicarse sin ocultar la causa.
- Antes de integrar cambios, ejecutar las pruebas del proyecto y comprobar que las dependencias estén sincronizadas con `uv sync`.

## Alcance y restricción explícita

La persistencia y publicación de resultados se realizan exclusivamente con MongoDB. Mantener una sola fuente de verdad para las observaciones y los snapshots, salvo que el alcance del proyecto cambie de forma explícita.
