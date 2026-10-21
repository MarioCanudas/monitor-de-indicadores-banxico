import type { ReactNode } from 'react'
import { CalendarDays, Check, CircleHelp, FileText, Mail, RefreshCw } from 'lucide-react'
import { shortDate } from '../format'
import type { Snapshot } from '../types'

export default function ReportsView({
  children,
  snapshots,
  startDate,
  endDate,
  selectedSeriesName,
  onUsePeriod,
  onRefresh,
}: {
  children: ReactNode
  snapshots: Snapshot[]
  startDate: string
  endDate: string
  selectedSeriesName: string
  onUsePeriod: (start: string, end: string) => void
  onRefresh: () => void
}) {
  const snapshotId = `${startDate}|${endDate}`
  const available = snapshots.find((item) => item.id === snapshotId)

  return (
    <div className="stack">
      <section className="panel reports-hero">
        <div className="report-icon"><Mail size={18} /></div>
        <div className="reports-hero-copy">
          <div className="section-kicker">DISTRIBUCIÓN SEGURA</div>
          <h2>Reportes por correo con vista previa</h2>
          <p>
            El envío real solo se realiza cuando confirmas la casilla y el backend
            tiene configurado <code>GMAIL_USER</code> y <code>GMAIL_KEY</code>. La
            vista previa nunca abre una conexión SMTP.
          </p>
        </div>
        <div className={`report-readiness ${available ? 'is-ready' : ''}`}>
          {available ? <Check size={15} /> : <CircleHelp size={15} />}
          <span>{available ? 'Snapshot listo para el periodo' : 'Falta el snapshot del periodo'}</span>
        </div>
      </section>

      <section className="reports-layout">
        <div className="reports-main">
          {children}
          <section className="panel report-guide">
            <div className="panel-heading">
              <div>
                <div className="section-kicker">FLUJO RECOMENDADO</div>
                <h2>Cómo generar un reporte</h2>
              </div>
              <FileText size={16} />
            </div>
            <ol className="report-steps">
              <li><span>01</span><p>Elige el periodo y el indicador de referencia en la barra superior.</p></li>
              <li><span>02</span><p>Guarda el correo destinatario. Se conserva solo en este navegador.</p></li>
              <li><span>03</span><p>Genera la vista previa. Si no existe snapshot, se calcula uno para el periodo.</p></li>
              <li><span>04</span><p>Revisa el HTML y confirma el envío con la casilla de verificación.</p></li>
            </ol>
            <p className="report-note">
              Periodo activo: <strong>{shortDate(startDate)} — {shortDate(endDate)}</strong>.
              Indicador de referencia: <strong>{selectedSeriesName}</strong>.
            </p>
          </section>
        </div>

        <aside className="panel reports-side">
          <div className="panel-heading table-heading">
            <div>
              <div className="section-kicker">SNAPSHOTS DISPONIBLES</div>
              <h2>Elige un periodo</h2>
            </div>
            <button className="icon-button" title="Actualizar snapshots" onClick={onRefresh}>
              <RefreshCw size={15} />
            </button>
          </div>
          {snapshots.length ? (
            <div className="report-period-list">
              {snapshots.map((item) => (
                <div key={item.id} className={`report-period ${item.id === snapshotId ? 'report-period-active' : ''}`}>
                  <div>
                    <span><CalendarDays size={13} />{shortDate(item.desde)} — {shortDate(item.hasta)}</span>
                    <small>{item.series.length} series · {item.alertas.length} alertas</small>
                  </div>
                  <button className="subtle-link" onClick={() => onUsePeriod(item.desde, item.hasta)}>
                    Usar periodo
                  </button>
                </div>
              ))}
            </div>
          ) : (
            <div className="empty-state compact-empty-state">
              No hay snapshots guardados. Genera uno desde la pantalla de Snapshots.
            </div>
          )}
        </aside>
      </section>
    </div>
  )
}
