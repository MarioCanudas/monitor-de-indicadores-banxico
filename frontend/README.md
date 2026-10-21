# Frontend del monitor Banxico

Interfaz React, Vite y TypeScript para consultar el backend del monitor. El frontend no conecta directamente con Banxico ni con MongoDB.

## Desarrollo local

1. Inicia la API desde la raíz del proyecto:

   ```bash
   uv run uvicorn backend.main:app --reload
   ```

2. Desde esta carpeta, instala dependencias e inicia Vite:

   ```bash
   npm install
   npm run dev
   ```

Vite envía las solicitudes de `/api/*` al backend en `http://localhost:8000`. Para usar otra dirección, copia `.env.example` como `.env.local` y modifica `BANXICO_API_URL`.

## Producción

El build se genera con `npm run build`. El servidor que publique `dist/` debe enrutar `/api/*` al backend y quitar el prefijo `/api`, o bien definir `VITE_API_URL` con la URL completa del backend para llamarlo directamente:

```env
VITE_API_URL=https://api.example.com
# Opcional, si la documentación vive en otra ruta:
VITE_API_DOCS_URL=https://api.example.com/docs
```

En ese caso el backend debe incluir el dominio del frontend en `CORS_ORIGINS`; de lo contrario el navegador bloqueará las peticiones. El proxy de Vite solo aplica al servidor de desarrollo.

## Pantallas

- **Resumen:** KPIs del indicador, gráfica histórica, alertas y acceso rápido al reporte.
- **Series:** catálogo de indicadores configurados.
- **Estadísticas:** estadística descriptiva y agrupaciones por año, mes o año-mes.
- **Snapshots:** KPIs, alertas y análisis guardados por periodo.
- **Observaciones:** histórico persistido, búsqueda y exportación CSV.
- **Ejecuciones:** historial de ingestas y resultado por serie.
- **Reportes:** vista previa, confirmación y envío por correo.

## Reportes por correo

En el panel, registra el correo destinatario; se conserva en el almacenamiento local de ese navegador. Genera la vista previa del periodo y confirma el envío con la casilla antes de pulsar **Enviar correo**. El envío real requiere `GMAIL_USER` y `GMAIL_KEY` configurados en el backend.

El backend actual valida el formato del correo, pero no aplica una lista permitida de destinatarios. No expongas la API a usuarios no confiables sin agregar esa autorización en el backend.