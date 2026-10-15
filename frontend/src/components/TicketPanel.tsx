import { clock, shortDate, TYPE_LABEL } from '../format'
import type { RunInfo, Ticket, TicketDetail } from '../types'
import StatusPill from './StatusPill'

interface Props {
  ticket: Ticket
  detail: TicketDetail | null
  latestRun: RunInfo | null
  runInProgress: boolean
  person: string
  onRun: () => void
  onResolve: () => void
}

export default function TicketPanel({ ticket, detail, latestRun, runInProgress, person, onRun, onResolve }: Props) {
  const resolved = ticket.status === 'resolved'
  const workingThis = latestRun?.status === 'running'
  const pending = detail?.payment_requests.filter((p) => p.status === 'pending').length ?? ticket.pending_payment_count ?? 0
  const [original, ...updates] = (ticket.notes ?? '').split('\n')

  const facts: [string, string][] = []
  if (ticket.sku) facts.push(['SKU', ticket.sku])
  if (ticket.size) facts.push(['Size', ticket.size])
  if (ticket.qty !== null) facts.push(['Quantity', String(ticket.qty)])
  if (ticket.lease_id !== null) facts.push(['Lease', `#${ticket.lease_id}`])
  if (ticket.invoice_id !== null) facts.push(['Invoice', `#${ticket.invoice_id}`])
  facts.push(['Received', `${shortDate(ticket.created_at)}, ${clock(ticket.created_at)}`])

  let runHint = 'The Boss reads the ticket and hands work to the team.'
  if (resolved) runHint = 'This ticket is resolved.'
  else if (workingThis) runHint = 'The team is working this ticket now. Watch the agents below.'
  else if (runInProgress) runHint = 'The team is busy with another ticket. One run at a time, since runs share one cash balance.'

  let resolveHint = 'Mark it resolved once nothing is left to do.'
  if (!person.trim()) resolveHint = 'Enter your name at the top to mark tickets resolved or approve payments.'
  else if (pending > 0) resolveHint = `${pending} payment request${pending > 1 ? 's' : ''} for this ticket must be approved or rejected first.`
  else if (latestRun?.status === 'done' && !resolved) resolveHint = 'The team has finished. Review the plan and drafts, then mark it resolved.'

  return (
    <div className="panel ticket-panel">
      <div className="ticket-panel-head">
        <div>
          <div className="eyebrow">
            Ticket #{ticket.id} · {TYPE_LABEL[ticket.type] ?? ticket.type}
          </div>
          <h1>{ticket.subject}</h1>
          <div className="muted">From {ticket.requester}</div>
        </div>
        <StatusPill status={ticket.status} />
      </div>

      <p className="ticket-request">“{original}”</p>

      <dl className="fact-grid">
        {facts.map(([label, value]) => (
          <div key={label}>
            <dt>{label}</dt>
            <dd>{value}</dd>
          </div>
        ))}
      </dl>

      {updates.length > 0 && (
        <div className="ticket-updates">
          <h3>Updates on the ticket</h3>
          <ul>
            {updates.map((line, i) => (
              <li key={i}>{line}</li>
            ))}
          </ul>
        </div>
      )}

      <div className="ticket-actions">
        <div className="action">
          <button type="button" className="btn btn-primary" onClick={onRun} disabled={resolved || runInProgress}>
            {workingThis ? (
              <>
                <span className="spinner" aria-hidden="true" /> Team working…
              </>
            ) : latestRun ? (
              'Run the agent team again'
            ) : (
              'Start the agent team'
            )}
          </button>
          <p className="hint">{runHint}</p>
        </div>
        <div className="action">
          <button
            type="button"
            className="btn btn-secondary"
            onClick={onResolve}
            disabled={resolved || workingThis || !person.trim() || pending > 0}
          >
            {resolved ? 'Resolved' : 'Mark resolved'}
          </button>
          <p className="hint">{resolved ? 'Nothing left to do on this ticket.' : resolveHint}</p>
        </div>
      </div>
    </div>
  )
}
