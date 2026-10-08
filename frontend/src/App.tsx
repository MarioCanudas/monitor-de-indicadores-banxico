import { useEffect, useMemo, useState } from 'react'
import {
  Activity,
  AlertTriangle,
  ArrowDownRight,
  ArrowRight,
  ArrowUpRight,
  BarChart3,
  CalendarDays,
  Check,
  ChevronDown,
  CircleHelp,
  Clock3,
  Database,
  Download,
  ExternalLink,
  FileText,
  Gauge,
  LoaderCircle,
  Mail,
  Menu,
  RefreshCw,
  Search,
  Server,
  SlidersHorizontal,
  X,
} from 'lucide-react'
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { api } from './api'
import type { IngestionLog, Observation, ReportResponse, SeriesMetadata, Snapshot } from './types'

type View = 'resumen' | 'series' | 'observaciones' | 'ejecuciones'
type Notice = { kind: 'success' | 'error'; text: string }

const viewOptions: { id: View; label: string; icon: typeof Gauge }[] = [
  { id: 'resumen', label: 'Resumen', icon: Gauge },
  { id: 'series', label: 'Series', icon: Activity },
  { id: 'observaciones', label: 'Observaciones', icon: Database },
  { id: 'ejecuciones', label: 'Ejecuciones', icon: Clock3 },
]

const today = () => new Date().toISOString().slice(0, 10)
const daysAgo = (days: number) => {
  const date = new Date()
  date.setDate(date.getDate() - days)
  return date.toISOString().slice(0, 10)
}

function shortDate(value: string | null | undefined) {
  if (!value) return 'Sin fecha'
  return new Intl.DateTimeFormat('es-MX', { day: '2-digit', month: 'short', year: 'numeric' }).format(new Date(value))
}

function number(value: number | null | undefined, digits = 2) {
  if (value == null || !Number.isFinite(value)) return '—'
  return new Intl.NumberFormat('es-MX', { maximumFractionDigits: digits, minimumFractionDigits: digits }).format(value)
}

function seriesName(series: SeriesMetadata[] | undefined, id: string) {
  return series?.find((item) => item.id === id)?.titulo ?? id
}

function ErrorState({ message }: { message: string }) {
  return <div className="inline-error"><CircleHelp size={16} /> <span>{message}</span></div>
}

function App() {
  const [view, setView] = useState<View>('resumen')
  const [series, setSeries] = useState<SeriesMetadata[]>([])
  const [selectedId, setSelectedId] = useState('')
  const [observations, setObservations] = useState<Observation[]>([])
  const [snapshots, setSnapshots] = useState<Snapshot[]>([])
  const [history, setHistory] = useState<IngestionLog[]>([])
  const [apiOnline, setApiOnline] = useState<boolean | null>(null)
  const [loadError, setLoadError] = useState('')
  const [startDate, setStartDate] = useState(daysAgo(30))
  const [endDate, setEndDate] = useState(today())
  const [refreshKey, setRefreshKey] = useState(0)
  const [busy, setBusy] = useState('')
  const [notice, setNotice] = useState<Notice | null>(null)
  const [search, setSearch] = useState('')
  const [reportEmail, setReportEmail] = useState('')
  const [report, setReport] = useState<ReportResponse | null>(null)
  const [mobileNavOpen, setMobileNavOpen] = useState(false)

  useEffect(() => {
    api.health().then(() => setApiOnline(true)).catch(() => setApiOnline(false))
    api.series()
      .then((items) => {
        setSeries(items)
        setSelectedId((current) => current || items[0]?.id || '')
      })
      .catch((error: Error) => setLoadError(error.message))
  }, [])

  useEffect(() => {
    api.observations(selectedId, startDate, endDate)
      .then((page) => {
        setObservations(page.items)
        setLoadError('')
      })
      .catch((error: Error) => {
        setObservations([])
        setLoadError(error.message)
      })
  }, [selectedId, startDate, endDate, refreshKey])

  useEffect(() => {
    api.snapshots().then((response) => setSnapshots(response.items)).catch(() => setSnapshots([]))
    api.history().then((response) => setHistory(response.items)).catch(() => setHistory([]))
  }, [refreshKey])

  const selectedSeries = series.find((item) => item.id === selectedId)
  const chartData = useMemo(
    () => [...observations].sort((a, b) => a.fecha.localeCompare(b.fecha)),
    [observations],
  )
  const latest = chartData.at(-1)
  const previous = chartData.at(-2)
  const changePct = latest && previous && previous.valor !== 0
    ? ((latest.valor - previous.valor) / previous.valor) * 100
    : null
  const filteredObservations = observations.filter((item) =>
    `${item.serie_id} ${item.fecha} ${item.valor}`.toLowerCase().includes(search.toLowerCase()),
  )
  const latestSnapshot = snapshots[0]
  const totalAlerts = latestSnapshot?.alertas.length ?? 0
  const latestIngestion = history[0]

  async function runAction(action: 'ingest' | 'snapshot' | 'daily') {
    const labels = { ingest: 'ingesta', snapshot: 'snapshot', daily: 'tarea diaria' }
    setBusy(action)
    setNotice(null)
    try {
      if (action === 'ingest') {
        const result = await api.ingest(startDate, endDate)
        setNotice({ kind: 'success', text: `Ingesta lista: ${result.nuevos} nuevas observaciones, ${result.errores} errores.` })
      } else if (action === 'snapshot') {
        await api.createSnapshot(startDate, endDate)
        setNotice({ kind: 'success', text: 'Snapshot calculado y guardado.' })
      } else {
        await api.dailyTask(startDate, endDate)
        setNotice({ kind: 'success', text: 'Tarea diaria terminada: ingesta y snapshot actualizados.' })
      }
      setRefreshKey((value) => value + 1)
    } catch (error) {
      setNotice({ kind: 'error', text: error instanceof Error ? error.message : `No fue posible ejecutar la ${labels[action]}.` })
    } finally {
      setBusy('')
    }
  }

  async function createReport(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setBusy('report')
    setNotice(null)
    try {
      setReport(await api.previewReport(reportEmail, startDate, endDate))
    } catch (error) {
      setNotice({ kind: 'error', text: error instanceof Error ? error.message : 'No fue posible preparar el reporte.' })
    } finally {
      setBusy('')
    }
  }

  function exportObservations() {
    const rows = [
      ['serie_id', 'fecha', 'valor', 'var_pct'],
      ...filteredObservations.map((item) => [item.serie_id, item.fecha.slice(0, 10), item.valor, item.var_pct]),
    ]
    const csv = rows.map((row) => row.join(',')).join('\n')
    const url = URL.createObjectURL(new Blob([csv], { type: 'text/csv;charset=utf-8' }))
    const link = document.createElement('a')
    link.href = url
    link.download = `observaciones-${selectedId}-${startDate}-${endDate}.csv`
    link.click()
    URL.revokeObjectURL(url)
  }

  const activeView = viewOptions.find((item) => item.id === view)!
  const title = view === 'resumen' ? 'Monitor de mercados' : activeView.label

  return (
    <div className="app-shell">
      <aside className={`sidebar ${mobileNavOpen ? 'sidebar-open' : ''}`}>
        <a className="brand" href="#resumen" onClick={() => setView('resumen')}>
          <span className="brand-mark"><BarChart3 size={21} strokeWidth={2.3} /></span>
          <span className="brand-type">banxico<span>monitor</span></span>
        </a>
        <div className="workspace-label">ESPACIO DE TRABAJO</div>
        <nav className="primary-nav" aria-label="Navegación principal">
          {viewOptions.map(({ id, label, icon: Icon }) => (
            <button key={id} className={`nav-item ${view === id ? 'nav-active' : ''}`} onClick={() => { setView(id); setMobileNavOpen(false) }}>
              <Icon size={18} strokeWidth={1.8} />
              <span>{label}</span>
              {id === 'series' && <span className="nav-count">{series.length}</span>}
            </button>
          ))}
        </nav>
        <div className="sidebar-rule" />
        <div className="workspace-label">SISTEMA</div>
        <div className="system-status">
          <span className={`status-light ${apiOnline === true ? 'is-online' : apiOnline === false ? 'is-offline' : ''}`} />
          <span>{apiOnline === true ? 'API conectada' : apiOnline === false ? 'API sin conexión' : 'Conectando API'}</span>
          <span className="status-version">v1</span>
        </div>
        <div className="sidebar-bottom">
          <div className="source-mark"><span>BM</span><div><strong>Banco de México</strong><small>Sistema de Información Económica</small></div></div>
          <a className="docs-link" href="http://localhost:8000/docs" target="_blank" rel="noreferrer">Documentación API <ExternalLink size={13} /></a>
        </div>
      </aside>

      {mobileNavOpen && <button className="nav-scrim" aria-label="Cerrar navegación" onClick={() => setMobileNavOpen(false)} />}

      <main className="main-area">
        <header className="topbar">
          <button className="icon-button mobile-menu" aria-label="Abrir navegación" onClick={() => setMobileNavOpen(true)}><Menu size={19} /></button>
          <div className="breadcrumb"><span>Indicadores</span><span className="crumb-slash">/</span><strong>{title}</strong></div>
          <div className="topbar-right">
            <span className="live-label"><span className={`status-light ${apiOnline ? 'is-online' : ''}`} />{apiOnline ? 'En vivo' : 'Sin conexión'}</span>
            <div className="topbar-date"><CalendarDays size={15} />{new Intl.DateTimeFormat('es-MX', { dateStyle: 'medium' }).format(new Date())}</div>
          </div>
        </header>

        <div className="page-content">
          <section className="page-heading">
            <div>
              <div className="eyebrow"><span className="eyebrow-line" />DATOS ECONÓMICOS · MÉXICO</div>
              <h1>{title}<span className="heading-period">.</span></h1>
              <p className="heading-description">Tipo de cambio y tasas de referencia, en una sola vista.</p>
            </div>
            <div className="heading-actions">
              <button className="button button-secondary" onClick={() => void runAction('ingest')} disabled={Boolean(busy)}>
                {busy === 'ingest' ? <LoaderCircle className="spin" size={16} /> : <RefreshCw size={16} />}
                <span>Actualizar datos</span>
              </button>
              <button className="button button-primary" onClick={() => void runAction('daily')} disabled={Boolean(busy)}>
                {busy === 'daily' ? <LoaderCircle className="spin" size={16} /> : <Activity size={16} />}
                <span>Ejecutar tarea</span>
                <ArrowRight size={15} />
              </button>
            </div>
          </section>

          {notice && <div className={`notice notice-${notice.kind}`} role="status"><span>{notice.kind === 'success' ? <Check size={16} /> : <AlertTriangle size={16} />}{notice.text}</span><button aria-label="Cerrar aviso" onClick={() => setNotice(null)}><X size={15} /></button></div>}

          <section className="filter-bar" aria-label="Filtros del periodo">
            <div className="filter-caption"><SlidersHorizontal size={15} /><span>PERIODO DE CONSULTA</span></div>
            <label className="date-control"><span>Desde</span><input aria-label="Fecha de inicio" type="date" value={startDate} max={endDate} onChange={(event) => setStartDate(event.target.value)} /></label>
            <span className="date-separator">—</span>
            <label className="date-control"><span>Hasta</span><input aria-label="Fecha de fin" type="date" value={endDate} min={startDate} max={today()} onChange={(event) => setEndDate(event.target.value)} /></label>
            <div className="filter-spacer" />
            <div className="selected-indicator">
              <span>INDICADOR</span>
              <label>
                <select value={selectedId} onChange={(event) => setSelectedId(event.target.value)} aria-label="Seleccionar indicador">
                  {series.map((item) => <option key={item.id} value={item.id}>{item.titulo}</option>)}
                </select>
                <ChevronDown size={14} />
              </label>
            </div>
          </section>

          {view === 'resumen' && <>
            <section className="metric-grid" aria-label="Indicadores clave">
              <article className="metric-card metric-primary">
                <div className="metric-topline"><span>ÚLTIMO VALOR</span><span className="metric-icon"><Activity size={17} /></span></div>
                <div className="metric-value">{latest ? number(latest.valor, 4) : '—'}<small>{selectedSeries?.unidad}</small></div>
                <div className="metric-foot"><span className="metric-name">{selectedSeries?.titulo ?? 'Selecciona un indicador'}</span><span>{latest ? shortDate(latest.fecha) : 'Sin datos'}</span></div>
              </article>
              <article className="metric-card">
                <div className="metric-topline"><span>VARIACIÓN DIARIA</span><span className={`trend-icon ${changePct != null && changePct < 0 ? 'trend-down' : ''}`}>{changePct != null && changePct < 0 ? <ArrowDownRight size={17} /> : <ArrowUpRight size={17} />}</span></div>
                <div className={`metric-value ${changePct != null && changePct < 0 ? 'negative' : 'positive'}`}>{changePct == null ? '—' : `${changePct > 0 ? '+' : ''}${number(changePct)}%`}</div>
                <div className="metric-foot"><span className="metric-name">Respecto al dato anterior</span><span>{chartData.length} observaciones</span></div>
              </article>
              <article className="metric-card">
                <div className="metric-topline"><span>ALERTAS ACTIVAS</span><span className="alert-icon"><AlertTriangle size={16} /></span></div>
                <div className="metric-value">{totalAlerts}<small>{totalAlerts === 1 ? 'alerta' : 'alertas'}</small></div>
                <div className="metric-foot"><span className="metric-name">Snapshot más reciente</span><span>{latestSnapshot ? shortDate(latestSnapshot.hasta) : 'Sin snapshot'}</span></div>
              </article>
              <article className="metric-card">
                <div className="metric-topline"><span>ÚLTIMA INGESTA</span><span className="metric-icon"><Download size={16} /></span></div>
                <div className="metric-value metric-time">{latestIngestion?.creado_en ? shortDate(latestIngestion.creado_en) : '—'}</div>
                <div className="metric-foot"><span className="metric-name">{latestIngestion ? `${latestIngestion.resumen.nuevos ?? 0} registros nuevos` : 'Sin ejecuciones registradas'}</span><span>{latestIngestion?.creado_en ? new Intl.DateTimeFormat('es-MX', { hour: '2-digit', minute: '2-digit' }).format(new Date(latestIngestion.creado_en)) : 'MongoDB'}</span></div>
              </article>
            </section>

            <section className="content-grid">
              <article className="panel chart-panel">
                <div className="panel-heading">
                  <div><div className="section-kicker">SERIE HISTÓRICA</div><h2>{selectedSeries?.titulo ?? 'Observaciones'}</h2></div>
                  <div className="chart-legend"><span className="legend-line" />{selectedSeries?.unidad ?? 'Valor'}</div>
                </div>
                {loadError ? <ErrorState message={loadError} /> : chartData.length ? <div className="chart-wrap">
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={chartData} margin={{ top: 10, right: 10, left: 4, bottom: 0 }}>
                      <CartesianGrid stroke="#e8ebe5" vertical={false} />
                      <XAxis dataKey="fecha" tickFormatter={(value: string) => new Intl.DateTimeFormat('es-MX', { day: '2-digit', month: 'short' }).format(new Date(value))} tickLine={false} axisLine={false} tick={{ fill: '#899087', fontSize: 11 }} minTickGap={32} />
                      <YAxis orientation="right" tickLine={false} axisLine={false} width={58} tick={{ fill: '#899087', fontSize: 11 }} domain={['auto', 'auto']} tickFormatter={(value: number) => number(value, 2)} />
                      <Tooltip contentStyle={{ border: '1px solid #e6e8e2', borderRadius: 6, boxShadow: '0 8px 24px #16291c12', fontSize: 12 }} labelFormatter={(value) => shortDate(String(value))} formatter={(value) => [number(Number(value), 4), selectedSeries?.unidad ?? 'Valor']} />
                      <Line type="monotone" dataKey="valor" stroke="#167456" strokeWidth={2.5} dot={false} activeDot={{ r: 4, strokeWidth: 0, fill: '#f5bd4f' }} />
                    </LineChart>
                  </ResponsiveContainer>
                </div> : <div className="empty-chart"><div className="empty-chart-art"><Activity size={28} /></div><strong>{apiOnline === false ? 'No hay conexión con la API' : 'Aún no hay observaciones'}</strong><span>Verifica la conexión o ejecuta una ingesta para consultar el histórico.</span><button className="text-button" onClick={() => void runAction('ingest')} disabled={Boolean(busy)}>Actualizar datos <ArrowRight size={14} /></button></div>}
                <div className="chart-foot"><span><span className="chart-dot" />Fuente: Sistema de Información Económica · Banxico</span><span>{chartData.length ? `${shortDate(startDate)} — ${shortDate(endDate)}` : 'Periodo seleccionado'}</span></div>
              </article>

              <article className="panel pulse-panel">
                <div className="panel-heading pulse-heading"><div><div className="section-kicker">PULSO DEL MERCADO</div><h2>Estado del periodo</h2></div><span className={`state-tag ${latestSnapshot?.estado === 'con_alertas' ? 'state-warning' : ''}`}><span />{latestSnapshot?.estado === 'con_alertas' ? 'Con alertas' : latestSnapshot ? 'Estable' : 'Sin snapshot'}</span></div>
                {latestSnapshot?.analisis?.resumen ? <p className="pulse-summary">{latestSnapshot.analisis.resumen}</p> : <p className="pulse-summary muted-summary">Genera un snapshot para obtener un resumen ejecutivo de las series y alertas del periodo.</p>}
                <div className="pulse-divider" />
                <div className="pulse-stats">
                  <div><span>Series en catálogo</span><strong>{series.length.toString().padStart(2, '0')}<small>indicadores</small></strong></div>
                  <div><span>Observaciones del periodo</span><strong>{chartData.length.toLocaleString('es-MX')}<small>registros</small></strong></div>
                  <div><span>Cobertura de serie</span><strong>{latestSnapshot?.series.find((item) => item.serie_id === selectedId) ? `${number(latestSnapshot.series.find((item) => item.serie_id === selectedId)?.cobertura_pct)}%` : '—'}<small>del periodo</small></strong></div>
                </div>
                <button className="panel-link" onClick={() => void runAction('snapshot')} disabled={Boolean(busy)}>{busy === 'snapshot' ? 'Calculando…' : 'Calcular snapshot'}{busy === 'snapshot' ? <LoaderCircle className="spin" size={15} /> : <ArrowRight size={15} />}</button>
              </article>
            </section>

            <section className="lower-grid">
              <article className="panel table-panel">
                <div className="panel-heading table-heading"><div><div className="section-kicker">DATOS RECIENTES</div><h2>Últimas observaciones</h2></div><button className="subtle-link" onClick={() => setView('observaciones')}>Ver todas <ArrowRight size={14} /></button></div>
                <ObservationTable rows={observations.slice(0, 5)} unit={selectedSeries?.unidad ?? ''} />
              </article>
              <article className="panel alert-panel">
                <div className="panel-heading table-heading"><div><div className="section-kicker">SEÑALES DEL SISTEMA</div><h2>Alertas recientes</h2></div><span className="count-pill">{latestSnapshot?.alertas.length ?? 0}</span></div>
                {latestSnapshot?.alertas.length ? <div className="alert-list">{latestSnapshot.alertas.slice(0, 3).map((alert, index) => <div className="alert-row" key={`${alert.serie_id}-${index}`}><span className={`alert-marker severity-${alert.severidad}`}><AlertTriangle size={14} /></span><div><strong>{seriesName(series, alert.serie_id)}</strong><p>{alert.mensaje}</p></div><span className={`alert-change ${alert.var_pct < 0 ? 'negative' : 'positive'}`}>{alert.var_pct > 0 ? '+' : ''}{number(alert.var_pct)}%</span></div>)}</div> : <div className="no-alerts"><span className="all-clear-icon"><Check size={16} /></span><span>{latestSnapshot ? 'No hay alertas para este periodo.' : 'Las alertas aparecerán al generar un snapshot.'}</span></div>}
                {latestSnapshot && <div className="alert-period">Snapshot {shortDate(latestSnapshot.desde)} — {shortDate(latestSnapshot.hasta)}</div>}
              </article>
            </section>

            <section className="panel report-panel">
              <div className="report-intro"><div className="report-icon"><Mail size={18} /></div><div><div className="section-kicker">DISTRIBUCIÓN</div><h2>Vista previa del reporte</h2><p>Prepara el correo del snapshot del periodo. No se enviará desde esta vista.</p></div></div>
              <form className="report-form" onSubmit={(event) => void createReport(event)}><label htmlFor="report-email">Correo destinatario</label><div className="report-input-row"><input id="report-email" type="email" placeholder="nombre@empresa.com" value={reportEmail} onChange={(event) => setReportEmail(event.target.value)} required /><button className="button button-secondary" type="submit" disabled={Boolean(busy)}>{busy === 'report' ? <LoaderCircle className="spin" size={15} /> : <FileText size={15} />}Generar vista previa</button></div></form>
              {report && <div className="report-result"><div className="report-result-head"><div><span>ASUNTO</span><strong>{report.asunto}</strong></div><button className="icon-button" title="Cerrar vista previa" onClick={() => setReport(null)}><X size={16} /></button></div><iframe title="Vista previa del reporte" sandbox="" srcDoc={report.html} /></div>}
            </section>
          </>}

          {view === 'series' && <section className="panel full-table-panel">
            <div className="panel-heading table-heading"><div><div className="section-kicker">CATÁLOGO BANXICO</div><h2>Indicadores disponibles</h2></div><span className="count-pill">{series.length} series</span></div>
            {series.length ? <div className="table-scroll"><table><thead><tr><th>INDICADOR</th><th>ID BANXICO</th><th>FRECUENCIA</th><th>UNIDAD</th><th>ÚLTIMO DATO</th><th>ESTADO</th></tr></thead><tbody>{series.map((item, index) => {
              const summary = latestSnapshot?.series.find((row) => row.serie_id === item.id)
              return <tr key={item.id} className="clickable-row" onClick={() => { setSelectedId(item.id); setView('resumen') }}><td><span className="series-name-cell"><span className={`series-index index-${index % 4}`}>{String(index + 1).padStart(2, '0')}</span><strong>{item.titulo}</strong></span></td><td><code>{item.id}</code></td><td>{item.frecuencia}</td><td>{item.unidad}</td><td className="mono-cell">{summary ? `${number(summary.ultimo_valor, 4)} · ${shortDate(summary.ultima_fecha)}` : item.ultima_fecha ? shortDate(item.ultima_fecha) : '—'}</td><td><span className="active-pill"><span />Activa</span></td></tr>
            })}</tbody></table></div> : <div className="empty-state">{loadError || 'Conectando con el catálogo de series…'}</div>}
            <div className="catalog-foot"><span><span className="chart-dot" />Catálogo configurado para el paquete mercados</span><span>Fuente: Banco de México</span></div>
          </section>}

          {view === 'observaciones' && <section className="panel full-table-panel">
            <div className="panel-heading table-heading"><div><div className="section-kicker">HISTÓRICO ALMACENADO</div><h2>Observaciones</h2></div><button className="button button-secondary compact-button" onClick={exportObservations} disabled={!filteredObservations.length}><Download size={15} />Exportar CSV</button></div>
            <div className="table-tools"><label className="search-field"><Search size={16} /><input placeholder="Buscar en observaciones…" value={search} onChange={(event) => setSearch(event.target.value)} /><kbd>⌘ K</kbd></label><span>{filteredObservations.length} resultados · {selectedSeries?.titulo ?? selectedId}</span></div>
            {loadError ? <div className="table-error"><ErrorState message={loadError} /></div> : <ObservationTable rows={filteredObservations} unit={selectedSeries?.unidad ?? ''} expanded />}
          </section>}

          {view === 'ejecuciones' && <section className="panel full-table-panel">
            <div className="panel-heading table-heading"><div><div className="section-kicker">OPERACIÓN</div><h2>Historial de ingestas</h2></div><button className="button button-primary compact-button" onClick={() => void runAction('ingest')} disabled={Boolean(busy)}>{busy === 'ingest' ? <LoaderCircle className="spin" size={15} /> : <RefreshCw size={15} />}Ejecutar ingesta</button></div>
            {history.length ? <div className="table-scroll"><table><thead><tr><th>FECHA DE EJECUCIÓN</th><th>ID DE EJECUCIÓN</th><th>NUEVAS</th><th>DUPLICADAS</th><th>ERRORES</th><th>RESULTADO</th></tr></thead><tbody>{history.map((item) => {
              const errors = item.resumen.errores ?? item.series.filter((row) => row.error).length
              return <tr key={item.run_id}><td className="mono-cell">{shortDate(item.creado_en)}</td><td><code className="run-id">{item.run_id.slice(0, 26)}{item.run_id.length > 26 ? '…' : ''}</code></td><td className="mono-cell">{item.resumen.nuevos ?? item.series.reduce((total, row) => total + row.nuevos, 0)}</td><td className="mono-cell">{item.resumen.duplicados ?? item.series.reduce((total, row) => total + row.duplicados, 0)}</td><td className={errors ? 'negative mono-cell' : 'mono-cell'}>{errors}</td><td><span className={`result-pill ${errors ? 'result-error' : ''}`}><span />{errors ? 'Con errores' : 'Completada'}</span></td></tr>
            })}</tbody></table></div> : <div className="empty-state">{apiOnline === false ? 'No se pudo conectar con la API.' : 'No hay ejecuciones registradas todavía.'}</div>}
            <div className="catalog-foot"><span><Server size={14} /> Historial persistido en MongoDB</span><span>Últimas {history.length} ejecuciones</span></div>
          </section>}

          <footer className="page-footer"><span>Monitor de indicadores económicos</span><span>Datos publicados por Banco de México <span className="footer-dot">·</span> Actualizados bajo demanda</span></footer>
        </div>
      </main>
    </div>
  )
}

function ObservationTable({ rows, unit, expanded = false }: { rows: Observation[]; unit: string; expanded?: boolean }) {
  if (!rows.length) return <div className="empty-state">No hay observaciones para este indicador y periodo.</div>
  return <div className={`table-scroll ${expanded ? 'expanded-table' : ''}`}><table><thead><tr><th>FECHA</th><th>VALOR</th><th>VARIACIÓN</th><th>PERIODO</th>{expanded && <th>ID DE EJECUCIÓN</th>}</tr></thead><tbody>{rows.map((item) => <tr key={item.id}><td className="mono-cell">{shortDate(item.fecha)}</td><td className="value-cell">{number(item.valor, 4)}<span>{unit}</span></td><td className={item.var_pct < 0 ? 'negative mono-cell' : 'positive mono-cell'}>{item.var_pct > 0 ? '+' : ''}{number(item.var_pct)}%</td><td>{new Intl.DateTimeFormat('es-MX', { month: 'long', year: 'numeric' }).format(new Date(item.fecha))}</td>{expanded && <td><code className="run-id">{item.run_id}</code></td>}</tr>)}</tbody></table></div>
}

export default App