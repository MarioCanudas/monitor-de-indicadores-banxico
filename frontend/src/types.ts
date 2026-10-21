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
  fecha_inicial: string
  valor_final: number
  fecha_final: string
  cambio_absoluto: number
  var_periodo_pct: number | null
  var_ultimo_dia_pct: number
  min: number
  fecha_min: string
  max: number
  fecha_max: string
  rango: number
  promedio: number
  mediana: number
  desviacion_estandar: number
  volatilidad_diaria_pct: number
  dias_alza: number
  dias_baja: number
  dias_sin_cambio: number
  mayor_subida_pct: number
  fecha_mayor_subida: string | null
  mayor_caida_pct: number
  fecha_mayor_caida: string | null
  tendencia: 'ascendente' | 'descendente' | 'estable'
  observaciones_validas: number
  dias_habiles_esperados: number
  cobertura_pct: number
  distancia_promedio_pct: number
  cambio_puntos_porcentuales: number | null
  cambio_puntos_base: number | null
  ultimo_valor: number
  ultima_fecha: string
  var_pct: number
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

export interface StatisticsValues {
  count: number | null
  mean: number | null
  std: number | null
  min: number | null
  '25%': number | null
  '50%': number | null
  '75%': number | null
  max: number | null
}

export interface GroupedStatistics {
  grupo: string
  estadisticas: StatisticsValues
  total_observaciones: number
}

export interface StatisticsResponse {
  serie: SeriesMetadata
  periodo: { desde: string; hasta: string }
  total_observaciones: number
  estadisticas: StatisticsValues
  agrupacion: 'year' | 'month' | 'year_month' | null
  grupos: GroupedStatistics[]
}

export interface Kpi {
  serie_id: string
  valor_inicial: number
  fecha_inicial: string
  valor_final: number
  fecha_final: string
  cambio_absoluto: number
  var_periodo_pct: number | null
  var_ultimo_dia_pct: number
  min: number
  fecha_min: string
  max: number
  fecha_max: string
  rango: number
  promedio: number
  mediana: number
  desviacion_estandar: number
  volatilidad_diaria_pct: number
  dias_alza: number
  dias_baja: number
  dias_sin_cambio: number
  mayor_subida_pct: number
  mayor_caida_pct: number
  tendencia: 'ascendente' | 'descendente' | 'estable'
  observaciones_validas: number
  dias_habiles_esperados: number
  cobertura_pct: number
  distancia_promedio_pct: number
  cambio_puntos_porcentuales: number | null
  cambio_puntos_base: number | null
}

export interface IngestionSeriesResult {
  serie_id: string
  nuevos: number
  duplicados: number
  consultada: boolean
  desde?: string | null
  hasta?: string | null
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