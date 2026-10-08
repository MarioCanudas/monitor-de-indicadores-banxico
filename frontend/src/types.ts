export interface SeriesMetadata {
  id: string
  titulo: string
  unidad: string
  frecuencia: string
  paquetes: string[]
  activa: boolean
  ultima_fecha: string | null
}

export interface Observation {
  id: string
  serie_id: string
  fecha: string
  anio: number
  mes: number
  valor: number
  var_pct: number
  run_id: string
}

export interface Pagination {
  total: number
  skip: number
  limit: number
  has_more: boolean
}

export interface ObservationPage {
  items: Observation[]
  pagination: Pagination
}

export interface SeriesSnapshot {
  serie_id: string
  valor_inicial: number
  valor_final: number
  cambio_absoluto: number
  var_periodo_pct: number | null
  var_ultimo_dia_pct: number
  min: number
  max: number
  promedio: number
  mediana: number
  desviacion_estandar: number
  volatilidad_diaria_pct: number
  dias_alza: number
  dias_baja: number
  dias_sin_cambio: number
  tendencia: string
  observaciones_validas: number
  cobertura_pct: number
  ultimo_valor: number
  ultima_fecha: string
}

export interface Alert {
  tipo: string
  severidad: 'media' | 'alta'
  serie_id: string
  mensaje: string
  valor: number
  var_pct: number
}

export interface Snapshot {
  id: string
  creado_en: string
  desde: string
  hasta: string
  series: SeriesSnapshot[]
  alertas: Alert[]
  estado: 'ok' | 'con_alertas'
  analisis: {
    resumen: string
    puntos_clave: string[]
    alertas: string[]
    limitaciones: string[]
  } | null
}

export interface IngestionSeriesResult {
  serie_id: string
  nuevos: number
  duplicados: number
  consultada: boolean
  motivo?: string | null
  error?: string | null
}

export interface IngestionLog {
  run_id: string
  creado_en: string | null
  resumen: Record<string, number>
  series: IngestionSeriesResult[]
}

export interface IngestionResponse {
  run_id: string
  nuevos: number
  duplicados: number
  errores: number
  duracion_seg: number
  series: IngestionSeriesResult[]
}

export interface ReportResponse {
  destinatario: string
  dry_run: boolean
  asunto: string
  html: string
  snapshot_id: string
}