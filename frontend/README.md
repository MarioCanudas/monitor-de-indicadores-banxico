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

El build se genera con `npm run build`. El servidor que publique `dist/` debe enrutar `/api/*` al backend y quitar el prefijo `/api`; la configuración de proxy incluida solo aplica al servidor de desarrollo de Vite.

## Reportes por correo

En el panel, registra el correo destinatario; se conserva en el almacenamiento local de ese navegador. Genera la vista previa del periodo y confirma el envío con la casilla antes de pulsar **Enviar correo**. El envío real requiere `GMAIL_USER` y `GMAIL_KEY` configurados en el backend.

El backend actual valida el formato del correo, pero no aplica una lista permitida de destinatarios. No expongas la API a usuarios no confiables sin agregar esa autorización en el backend.