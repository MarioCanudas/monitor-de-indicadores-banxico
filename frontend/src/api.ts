import type {
  IngestionLog,
  IngestionResponse,
  Kpi,
  Observation,
  ObservationPage,
  ReportResponse,
  SeriesMetadata,
  Snapshot,
  StatisticsResponse,
} from './types'

// En desarrollo se usa el proxy de Vite (/api). En producción se puede
// apuntar directo al backend con VITE_API_URL, que ahora permite CORS.
const API_ROOT = ((import.meta.env.VITE_API_URL as string | undefined) ?? '/api').replace(/\/$/, '')
export const API_DOCS_URL = (import.meta.env.VITE_API_DOCS_URL as string | undefined)
  ?? (API_ROOT.startsWith('http') ? `${API_ROOT.replace(/\/api$/, '')}/docs` : 'http://localhost:8000/docs')

type ApiSeries = Omit<SeriesMetadata, 'id'> & { _id: string }
type ApiObservation = Omit<Observation, 'id'> & { _id: string }
type ApiObservationPage = Omit<ObservationPage, 'items'> & { items: ApiObservation[] }
type ApiSnapshot = Omit<Snapshot, 'id'> & { _id: string }
type ApiStatistics = Omit<StatisticsResponse, 'serie'> & { serie: ApiSeries }
type ApiKpi = { serie: ApiSeries; periodo: { desde: string; hasta: string }; kpi: Kpi | null }

export class ApiError extends Error {
  constructor(message: string, readonly status: number) {
    super(message)
    this.name = 'ApiError'
  }
}

function normalizeId<T extends { _id: string }>(item: T): Omit<T, '_id'> & { id: string } {
  const { _id, ...rest } = item
  return { ...rest, id: _id }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_ROOT}${path}`, {
    ...init,
    headers: {
      Accept: 'application/json',
      ...(init?.body ? { 'Content-Type': 'application/json' } : {}),
      ...init?.headers,
    },
  })

  if (!response.ok) {
    const body = await response.json().catch(() => null) as { detail?: string } | null
    throw new ApiError(body?.detail ?? `Error de API (${response.status})`, response.status)
  }

  return response.json() as Promise<T>
}

function queryString(values: Record<string, string | number | undefined>) {
  const query = new URLSearchParams()
  Object.entries(values).forEach(([key, value]) => {
    if (value !== undefined && value !== '') query.set(key, String(value))
  })
  return query.toString()
}

export const api = {
  health: () => request<{ status: string }>('/health'),
  series: async () => (await request<ApiSeries[]>('/series')).map(normalizeId),
  observations: async (seriesId: string, start: string, end: string) => {
    const page = await request<ApiObservationPage>(`/observaciones?${queryString({ series_id: seriesId, start_date: start, end_date: end, limit: 1000 })}`)
    return { ...page, items: page.items.map(normalizeId) }
  },
  statistics: async (seriesId: string, start: string, end: string, grouping: string) => {
    const data = await request<ApiStatistics>(
      `/estadisticas/${seriesId}?${queryString({ start_date: start, end_date: end, agrupacion: grouping })}`,
    )
    return { ...data, serie: normalizeId(data.serie) }
  },
  kpis: async (seriesId: string, start: string, end: string) => {
    const data = await request<ApiKpi>(
      `/kpis/${seriesId}?${queryString({ start_date: start, end_date: end })}`,
    )
    return { ...data, serie: normalizeId(data.serie) }
  },
  snapshots: async (limit = 20) => {
    const page = await request<{ items: ApiSnapshot[] }>(`/snapshots?limit=${limit}`)
    return { ...page, items: page.items.map(normalizeId) }
  },
  history: (limit = 20) => request<{ items: IngestionLog[] }>(`/ingestas/historial?limit=${limit}`),
  ingest: (start: string, end: string) =>
    request<IngestionResponse>(`/ingestas?${queryString({ start_date: start, end_date: end })}`, { method: 'POST' }),
  createSnapshot: (start: string, end: string) =>
    request<ApiSnapshot>(`/snapshots?${queryString({ start_date: start, end_date: end })}`, { method: 'POST' }).then(normalizeId),
  dailyTask: (start: string, end: string) =>
    request<ApiSnapshot>(`/tareas/diaria?${queryString({ start_date: start, end_date: end })}`, { method: 'POST' }).then(normalizeId),
  previewReport: (email: string, start: string, end: string) =>
    request<ReportResponse>('/reportes/preview', {
      method: 'POST',
      body: JSON.stringify({ destinatario: email, start_date: start, end_date: end }),
    }),
  sendReport: (email: string, start: string, end: string) =>
    request<ReportResponse>('/reportes/enviar', {
      method: 'POST',
      body: JSON.stringify({ destinatario: email, start_date: start, end_date: end, dry_run: false }),
    }),
}

export { request }