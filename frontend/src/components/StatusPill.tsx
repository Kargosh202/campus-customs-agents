import { STATUS_LABEL } from '../format'
import type { TicketStatus } from '../types'

export default function StatusPill({ status }: { status: TicketStatus }) {
  return <span className={`pill pill-${status}`}>{STATUS_LABEL[status] ?? status}</span>
}
