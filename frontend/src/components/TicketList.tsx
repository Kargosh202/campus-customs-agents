import { STATUS_LABEL, TYPE_LABEL } from '../format'
import type { RunInfo, Ticket } from '../types'
import StatusPill from './StatusPill'

interface Props {
  tickets: Ticket[]
  selectedId: number | null
  runs: RunInfo[]
  onSelect: (id: number) => void
}

export default function TicketList({ tickets, selectedId, runs, onSelect }: Props) {
  const open = tickets.filter((t) => t.is_open !== false).length

  return (
    <div className="panel">
      <div className="panel-head">
        <h2>Tickets</h2>
        <span className="muted">
          {open} open · {tickets.length - open} resolved
        </span>
      </div>
      <ul className="ticket-list" role="listbox" aria-label="Tickets">
        {tickets.map((t) => {
          const working = runs.some((r) => r.ticket_id === t.id && r.status === 'running')
          return (
            <li key={t.id}>
              <button
                type="button"
                role="option"
                aria-selected={t.id === selectedId}
                className={`ticket-item ${t.id === selectedId ? 'is-selected' : ''}`}
                onClick={() => onSelect(t.id)}
              >
                <div className="ticket-item-top">
                  <span className="ticket-id">#{t.id}</span>
                  <StatusPill status={t.status} />
                </div>
                <div className="ticket-subject">{t.subject}</div>
                <div className="ticket-meta">
                  {TYPE_LABEL[t.type] ?? t.type} · {t.requester}
                </div>
                <div className="ticket-flags">
                  {t.status !== 'open' && t.status !== 'resolved' && <span className="flag">Still open</span>}
                  {working && <span className="flag flag-live">Team working…</span>}
                  {!!t.pending_payment_count && <span className="flag flag-warn">{t.pending_payment_count} awaiting approval</span>}
                  {!!t.draft_count && <span className="flag">{t.draft_count} draft{t.draft_count > 1 ? 's' : ''}</span>}
                </div>
                <span className="sr-only">Status: {STATUS_LABEL[t.status]}</span>
              </button>
            </li>
          )
        })}
      </ul>
    </div>
  )
}
