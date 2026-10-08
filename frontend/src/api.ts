import type {
  IngestionLog,
  IngestionResponse,
  Observation,
  ObservationPage,
  ReportResponse,
  SeriesMetadata,
  Snapshot,
} from './types'

const API_ROOT = '/api'
type ApiSeries = Omit<SeriesMetadata, 'id'> & { _id: string }
type ApiObservation = Omit<Observation, 'id'> & { _id: string }
type ApiObservationPage = Omit<ObservationPage, 'items'> & { items: ApiObservation[] }
type ApiSnapshot = Omit<Snapshot, 'id'> & { _id: string }

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
    throw new Error(body?.detail ?? `Error de API (${response.status})`)
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
  snapshots: async () => {
    const page = await request<{ items: ApiSnapshot[] }>('/snapshots?limit=8')
    return { ...page, items: page.items.map(normalizeId) }
  },
  history: () => request<{ items: IngestionLog[] }>('/ingestas/historial?limit=8'),
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
}

export { request }