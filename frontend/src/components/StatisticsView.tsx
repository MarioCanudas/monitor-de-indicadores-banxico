import { useEffect, useMemo, useState } from 'react'
import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { BarChart3, Calculator, CircleHelp, LoaderCircle, RefreshCw } from 'lucide-react'
import { api } from '../api'
import { number, shortDate } from '../format'
import type { SeriesMetadata, StatisticsResponse, StatisticsValues } from '../types'

type Grouping = 'none' | 'year' | 'month' | 'year_month'

const groupingOptions: { id: Grouping; label: string }[] = [
  { id: 'none', label: 'Todo el periodo' },
  { id: 'year', label: 'Por año' },
  { id: 'month', label: 'Por mes' },
  { id: 'year_month', label: 'Año-mes' },
]

function statistic(value: number | null | undefined, digits = 4) {
  return number(value, digits)
}

function Metric({
  label,
  value,
  suffix,
}: {
  label: string
  value: string
  suffix?: string
}) {
  return (
    <article className="stat-card">
      <span>{label}</span>
      <strong>{value}<small>{suffix}</small></strong>
    </article>
  )
}

export default function StatisticsView({
  series,
  selectedId,
  startDate,
  endDate,
  refreshKey,
}: {
  series: SeriesMetadata[]
  selectedId: string
  startDate: string
  endDate: string
  refreshKey: number
}) {
  const [grouping, setGrouping] = useState<Grouping>('year_month')
  const [data, setData] = useState<StatisticsResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [attempt, setAttempt] = useState(0)
  const selected = series.find((item) => item.id === selectedId)

  useEffect(() => {
    if (!selectedId) return
    let active = true
    setLoading(true)
    setError('')
    api.statistics(selectedId, startDate, endDate, grouping)
      .then((response) => {
        if (active) setData(response)
      })
      .catch((cause: Error) => {
        if (active) {
          setData(null)
          setError(cause.message)
        }
      })
      .finally(() => {
        if (active) setLoading(false)
      })
    return () => { active = false }
  }, [selectedId, startDate, endDate, grouping, refreshKey, attempt])

  const stats: StatisticsValues | null = data?.estadisticas ?? null
  const chartData = useMemo(
    () => (data?.grupos ?? []).map((group) => ({
      grupo: group.grupo,
      media: group.estadisticas.mean,
      observaciones: group.total_observaciones,
    })),
    [data],
  )

  return (
    <div className="stack">
      <section className="panel stats-toolbar">
        <div className="stats-toolbar-copy">
          <div className="section-kicker">ESTADÍSTICA DESCRIPTIVA</div>
          <h2>{selected?.titulo ?? 'Selecciona un indicador'}</h2>
          <p>
            Calculada desde la fuente de Banxico con la misma limpieza de la
            ingesta: fechas válidas, valores numéricos y una observación por fecha.
          </p>
        </div>
        <div className="segmented" role="group" aria-label="Agrupación de estadísticas">
          {groupingOptions.map((option) => (
            <button
              key={option.id}
              className={grouping === option.id ? 'segmented-active' : ''}
              onClick={() => setGrouping(option.id)}
            >
              {option.label}
            </button>
          ))}
        </div>
      </section>

      {error && (
        <div className="inline-error panel inline-error-panel">
          <CircleHelp size={16} />
          <span>{error}</span>
          <button className="subtle-link" onClick={() => setAttempt((value) => value + 1)}>
            <RefreshCw size={14} /> Reintentar
          </button>
        </div>
      )}

      {loading && !data && (
        <div className="panel empty-state">
          <span className="loading-inline"><LoaderCircle className="spin" size={17} /> Calculando estadísticas…</span>
        </div>
      )}

      {stats && data && (
        <>
          <section className="stat-grid" aria-label="Estadísticas del periodo">
            <Metric label="OBSERVACIONES" value={statistic(stats.count, 0)} suffix="registros" />
            <Metric label="PROMEDIO" value={statistic(stats.mean)} suffix={selected?.unidad} />
            <Metric label="MEDIANA" value={statistic(stats['50%'])} suffix={selected?.unidad} />
            <Metric label="DESV. ESTÁNDAR" value={statistic(stats.std)} suffix={selected?.unidad} />
            <Metric label="MÍNIMO" value={statistic(stats.min)} suffix={selected?.unidad} />
            <Metric label="PERCENTIL 25" value={statistic(stats['25%'])} suffix={selected?.unidad} />
            <Metric label="PERCENTIL 75" value={statistic(stats['75%'])} suffix={selected?.unidad} />
            <Metric label="MÁXIMO" value={statistic(stats.max)} suffix={selected?.unidad} />
          </section>

          <section className="stats-grid">
            <article className="panel chart-panel stats-chart-panel">
              <div className="panel-heading">
                <div>
                  <div className="section-kicker">PROMEDIO POR GRUPO</div>
                  <h2>{grouping === 'none' ? 'Sin agrupación' : 'Evolución del promedio'}</h2>
                </div>
                <div className="chart-legend"><span className="legend-line" />{selected?.unidad ?? 'Valor'}</div>
              </div>
              {chartData.length ? (
                <div className="chart-wrap">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={chartData} margin={{ top: 12, right: 10, left: 4, bottom: 0 }}>
                      <CartesianGrid stroke="#e8ebe5" vertical={false} />
                      <XAxis dataKey="grupo" tickLine={false} axisLine={false} tick={{ fill: '#899087', fontSize: 10 }} />
                      <YAxis orientation="right" tickLine={false} axisLine={false} width={62} domain={['auto', 'auto']} tick={{ fill: '#899087', fontSize: 10 }} tickFormatter={(value: number) => number(value, 2)} />
                      <Tooltip
                        contentStyle={{ border: '1px solid #e6e8e2', borderRadius: 6, boxShadow: '0 8px 24px #16291c12', fontSize: 12 }}
                        formatter={(value: number, _name, item) => [number(value, 4), `${item.payload.observaciones} observaciones`]}
                      />
                      <Bar dataKey="media" fill="#167456" radius={[3, 3, 0, 0]} maxBarSize={38} />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              ) : (
                <div className="empty-chart compact-empty">
                  <div className="empty-chart-art"><BarChart3 size={24} /></div>
                  <strong>Selecciona una agrupación</strong>
                  <span>Elige año, mes o año-mes para comparar promedios y detectar cambios por periodo.</span>
                </div>
              )}
              <div className="chart-foot">
                <span><span className="chart-dot" />Fuente: SIE · Banxico</span>
                <span>{shortDate(startDate)} — {shortDate(endDate)}</span>
              </div>
            </article>

            <article className="panel stats-summary-panel">
              <div className="panel-heading">
                <div>
                  <div className="section-kicker">LECTURA RÁPIDA</div>
                  <h2>Qué dicen los números</h2>
                </div>
                <span className="stat-icon"><Calculator size={16} /></span>
              </div>
              <div className="stats-summary-list">
                <div><span>Observaciones válidas</span><strong>{number(stats.count, 0)}</strong></div>
                <div><span>Rango (máx − mín)</span><strong>{stats.max != null && stats.min != null ? number(stats.max - stats.min, 4) : '—'}</strong></div>
                <div><span>Coeficiente de variación</span><strong>{stats.mean ? `${number((Number(stats.std) / Number(stats.mean)) * 100, 2)}%` : '—'}</strong></div>
                <div><span>Promedio vs mediana</span><strong>{stats.mean != null && stats['50%'] != null ? number(Number(stats.mean) - Number(stats['50%']), 4) : '—'}</strong></div>
                <div><span>Grupos calculados</span><strong>{number(data.grupos.length, 0)}</strong></div>
              </div>
              <p className="stats-note">
                Una desviación estándar alta indica mayor dispersión. Si el promedio
                se aleja de la mediana, la serie puede tener valores extremos.
              </p>
            </article>
          </section>

          {data.grupos.length > 0 && (
            <section className="panel full-table-panel">
              <div className="panel-heading table-heading">
                <div>
                  <div className="section-kicker">DETALLE POR GRUPO</div>
                  <h2>Estadísticas agrupadas</h2>
                </div>
                <span className="count-pill">{data.grupos.length} grupos</span>
              </div>
              <div className="table-scroll">
                <table>
                  <thead>
                    <tr>
                      <th>GRUPO</th>
                      <th>OBSERVACIONES</th>
                      <th>PROMEDIO</th>
                      <th>MEDIANA</th>
                      <th>DESV. EST.</th>
                      <th>MÍNIMO</th>
                      <th>MÁXIMO</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.grupos.map((group) => (
                      <tr key={group.grupo}>
                        <td><code>{group.grupo}</code></td>
                        <td className="mono-cell">{group.total_observaciones}</td>
                        <td className="value-cell">{statistic(group.estadisticas.mean)}</td>
                        <td className="mono-cell">{statistic(group.estadisticas['50%'])}</td>
                        <td className="mono-cell">{statistic(group.estadisticas.std)}</td>
                        <td className="mono-cell">{statistic(group.estadisticas.min)}</td>
                        <td className="mono-cell">{statistic(group.estadisticas.max)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <div className="catalog-foot">
                <span><span className="chart-dot" />Cálculo descriptivo sobre observaciones depuradas</span>
                <span>Agrupación: {groupingOptions.find((item) => item.id === grouping)?.label}</span>
              </div>
            </section>
          )}
        </>
      )}
    </div>
  )
}
