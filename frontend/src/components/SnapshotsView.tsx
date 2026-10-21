import { useEffect, useMemo, useState } from 'react'
import {
  Bar,
  BarChart,
  Cell,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import {
  AlertTriangle,
  ArrowRight,
  Check,
  CircleHelp,
  FileText,
  Layers,
  LoaderCircle,
  RefreshCw,
  Sparkles,
} from 'lucide-react'
import { number, seriesName, shortDate, shortDateTime, signedPercent } from '../format'
import type { SeriesMetadata, Snapshot } from '../types'

export default function SnapshotsView({
  series,
  snapshots,
  selectedId,
  busy,
  onCreateSnapshot,
  onRefresh,
  onOpenReport,
}: {
  series: SeriesMetadata[]
  snapshots: Snapshot[]
  selectedId: string
  busy: string
  onCreateSnapshot: () => void
  onRefresh: () => void
  onOpenReport: (start: string, end: string) => void
}) {
  const [selectedSnapshotId, setSelectedSnapshotId] = useState('')

  useEffect(() => {
    if (!snapshots.length) {
      setSelectedSnapshotId('')
      return
    }
    setSelectedSnapshotId((current) => (
      snapshots.some((item) => item.id === current) ? current : snapshots[0].id
    ))
  }, [snapshots])

  const snapshot = snapshots.find((item) => item.id === selectedSnapshotId) ?? snapshots[0]
  const selectedMetric = snapshot?.series.find((item) => item.serie_id === selectedId)
  const chartData = useMemo(
    () => (snapshot?.series ?? []).map((item) => ({
      serie: seriesName(series, item.serie_id),
      variacion: item.var_periodo_pct ?? 0,
    })),
    [snapshot, series],
  )

  return (
    <div className="stack">
      <section className="panel snapshot-toolbar">
        <div className="stats-toolbar-copy">
          <div className="section-kicker">SNAPSHOTS CALCULADOS</div>
          <h2>KPIs, alertas y análisis del periodo</h2>
          <p>
            Cada snapshot se calcula con un aggregation pipeline en MongoDB y se
            guarda con un identificador determinista por periodo.
          </p>
        </div>
        <div className="snapshot-toolbar-actions">
          <button className="button button-secondary compact-button" onClick={onRefresh} disabled={Boolean(busy)}>
            <RefreshCw size={15} /> Actualizar
          </button>
          <button className="button button-primary compact-button" onClick={onCreateSnapshot} disabled={Boolean(busy)}>
            {busy === 'snapshot' ? <LoaderCircle className="spin" size={15} /> : <Layers size={15} />}
            Calcular snapshot
          </button>
        </div>
      </section>

      {!snapshots.length ? (
        <section className="panel empty-state">
          <div>
            <Layers size={26} />
            <p>No hay snapshots guardados. Calcula uno para ver KPIs, alertas y análisis.</p>
          </div>
        </section>
      ) : (
        <section className="snapshot-layout">
          <aside className="panel snapshot-list-panel">
            <div className="panel-heading table-heading">
              <div>
                <div className="section-kicker">HISTÓRICO</div>
                <h2>Periodos</h2>
              </div>
              <span className="count-pill">{snapshots.length}</span>
            </div>
            <div className="snapshot-list">
              {snapshots.map((item) => (
                <button
                  key={item.id}
                  className={`snapshot-item ${item.id === snapshot?.id ? 'snapshot-item-active' : ''}`}
                  onClick={() => setSelectedSnapshotId(item.id)}
                >
                  <span className={`snapshot-dot ${item.estado === 'con_alertas' ? 'snapshot-dot-warning' : ''}`} />
                  <span>
                    <strong>{shortDate(item.desde)} — {shortDate(item.hasta)}</strong>
                    <small>{item.series.length} series · {item.alertas.length} alertas</small>
                  </span>
                  <span className={`state-tag ${item.estado === 'con_alertas' ? 'state-warning' : ''}`}>
                    <span />{item.estado === 'con_alertas' ? 'Alertas' : 'OK'}
                  </span>
                </button>
              ))}
            </div>
          </aside>

          {snapshot && (
            <div className="snapshot-detail">
              <section className="panel snapshot-head-panel">
                <div className="snapshot-head">
                  <div>
                    <div className="section-kicker">SNAPSHOT SELECCIONADO</div>
                    <h2>{shortDate(snapshot.desde)} — {shortDate(snapshot.hasta)}</h2>
                    <p>Creado {shortDateTime(snapshot.creado_en)} · {snapshot.id}</p>
                  </div>
                  <div className="snapshot-head-actions">
                    <span className={`state-tag ${snapshot.estado === 'con_alertas' ? 'state-warning' : ''}`}>
                      <span />{snapshot.estado === 'con_alertas' ? 'Con alertas' : 'Estable'}
                    </span>
                    <button className="button button-secondary compact-button" onClick={() => onOpenReport(snapshot.desde, snapshot.hasta)}>
                      <FileText size={15} /> Preparar reporte
                    </button>
                  </div>
                </div>

                <div className="stat-grid snapshot-stat-grid">
                  <article className="stat-card">
                    <span>ÚLTIMO VALOR</span>
                    <strong>{selectedMetric ? number(selectedMetric.ultimo_valor, 4) : '—'}<small>{series.find((item) => item.id === selectedId)?.unidad}</small></strong>
                  </article>
                  <article className="stat-card">
                    <span>VARIACIÓN DEL PERIODO</span>
                    <strong className={(selectedMetric?.var_periodo_pct ?? 0) < 0 ? 'negative' : 'positive'}>
                      {selectedMetric ? signedPercent(selectedMetric.var_periodo_pct) : '—'}
                    </strong>
                  </article>
                  <article className="stat-card">
                    <span>VOLATILIDAD DIARIA</span>
                    <strong>{selectedMetric ? `${number(selectedMetric.volatilidad_diaria_pct)}%` : '—'}</strong>
                  </article>
                  <article className="stat-card">
                    <span>COBERTURA</span>
                    <strong>{selectedMetric ? `${number(selectedMetric.cobertura_pct)}%` : '—'}<small>días hábiles</small></strong>
                  </article>
                </div>
              </section>

              <section className="snapshot-two-columns">
                <article className="panel snapshot-chart-panel">
                  <div className="panel-heading">
                    <div>
                      <div className="section-kicker">COMPARATIVO</div>
                      <h2>Variación por indicador</h2>
                    </div>
                    <div className="chart-legend"><span className="legend-line" />% del periodo</div>
                  </div>
                  <div className="chart-wrap snapshot-chart-wrap">
                    <ResponsiveContainer width="100%" height="100%">
                      <BarChart data={chartData} layout="vertical" margin={{ top: 8, right: 20, left: 4, bottom: 0 }}>
                        <CartesianGrid stroke="#e8ebe5" horizontal={false} />
                        <XAxis type="number" tickLine={false} axisLine={false} tick={{ fill: '#899087', fontSize: 10 }} tickFormatter={(value: number) => `${number(value, 1)}%`} />
                        <YAxis type="category" dataKey="serie" width={135} tickLine={false} axisLine={false} tick={{ fill: '#687168', fontSize: 10 }} />
                        <Tooltip
                          contentStyle={{ border: '1px solid #e6e8e2', borderRadius: 6, fontSize: 12 }}
                          formatter={(value: number) => [signedPercent(value), 'Variación']}
                        />
                        <Bar dataKey="variacion" radius={[0, 3, 3, 0]} maxBarSize={22}>
                          {chartData.map((item) => (
                            <Cell key={item.serie} fill={item.variacion < 0 ? '#c15448' : '#167456'} />
                          ))}
                        </Bar>
                      </BarChart>
                    </ResponsiveContainer>
                  </div>
                </article>

                <article className="panel snapshot-alerts-panel">
                  <div className="panel-heading table-heading">
                    <div>
                      <div className="section-kicker">SEÑALES</div>
                      <h2>Alertas del snapshot</h2>
                    </div>
                    <span className="count-pill">{snapshot.alertas.length}</span>
                  </div>
                  {snapshot.alertas.length ? (
                    <div className="alert-list">
                      {snapshot.alertas.map((alert, index) => (
                        <div className="alert-row" key={`${alert.serie_id}-${index}`}>
                          <span className={`alert-marker severity-${alert.severidad}`}><AlertTriangle size={14} /></span>
                          <div>
                            <strong>{seriesName(series, alert.serie_id)}</strong>
                            <p>{alert.mensaje}</p>
                          </div>
                          <span className={`alert-change ${alert.var_pct < 0 ? 'negative' : 'positive'}`}>
                            {signedPercent(alert.var_pct)}
                          </span>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div className="no-alerts">
                      <span className="all-clear-icon"><Check size={16} /></span>
                      <span>Sin alertas: ninguna serie superó los umbrales configurados.</span>
                    </div>
                  )}
                </article>
              </section>

              <section className="panel full-table-panel snapshot-table-panel">
                <div className="panel-heading table-heading">
                  <div>
                    <div className="section-kicker">DETALLE DE KPIs</div>
                    <h2>Series del snapshot</h2>
                  </div>
                  <span className="count-pill">{snapshot.series.length} series</span>
                </div>
                <div className="table-scroll">
                  <table>
                    <thead>
                      <tr>
                        <th>INDICADOR</th>
                        <th>ÚLTIMO VALOR</th>
                        <th>VAR. PERIODO</th>
                        <th>MÍN / MÁX</th>
                        <th>PROMEDIO</th>
                        <th>TENDENCIA</th>
                        <th>COBERTURA</th>
                      </tr>
                    </thead>
                    <tbody>
                      {snapshot.series.map((item) => (
                        <tr key={item.serie_id} className={item.serie_id === selectedId ? 'row-highlight' : ''}>
                          <td><strong className="table-strong">{seriesName(series, item.serie_id)}</strong><code>{item.serie_id}</code></td>
                          <td className="value-cell">{number(item.ultimo_valor, 4)}</td>
                          <td className={Number(item.var_periodo_pct) < 0 ? 'negative mono-cell' : 'positive mono-cell'}>{signedPercent(item.var_periodo_pct)}</td>
                          <td className="mono-cell">{number(item.min, 4)} / {number(item.max, 4)}</td>
                          <td className="mono-cell">{number(item.promedio, 4)}</td>
                          <td><span className={`trend-chip trend-${item.tendencia}`}>{item.tendencia}</span></td>
                          <td className="mono-cell">{number(item.cobertura_pct)}%</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </section>

              <section className="panel snapshot-analysis-panel">
                <div className="panel-heading">
                  <div>
                    <div className="section-kicker">ANÁLISIS REDACTADO</div>
                    <h2>Resumen ejecutivo</h2>
                  </div>
                  <span className="stat-icon"><Sparkles size={16} /></span>
                </div>
                {snapshot.analisis ? (
                  <>
                    <p className="analysis-summary">{snapshot.analisis.resumen}</p>
                    {snapshot.analisis.puntos_clave.length > 0 && (
                      <div className="analysis-block">
                        <span>PUNTOS CLAVE</span>
                        <ul>{snapshot.analisis.puntos_clave.map((point) => <li key={point}>{point}</li>)}</ul>
                      </div>
                    )}
                    {snapshot.analisis.limitaciones.length > 0 && (
                      <div className="analysis-block">
                        <span>LIMITACIONES</span>
                        <ul>{snapshot.analisis.limitaciones.map((point) => <li key={point}>{point}</li>)}</ul>
                      </div>
                    )}
                  </>
                ) : (
                  <p className="analysis-summary muted-summary">Este snapshot no tiene análisis redactado.</p>
                )}
                <button className="panel-link" onClick={() => onOpenReport(snapshot.desde, snapshot.hasta)}>
                  Preparar reporte de este periodo <ArrowRight size={15} />
                </button>
              </section>
            </div>
          )}
        </section>
      )}

      {!snapshots.length && (
        <div className="inline-error"><CircleHelp size={16} /> Genera un snapshot para habilitar el detalle y el reporte.</div>
      )}
    </div>
  )
}
