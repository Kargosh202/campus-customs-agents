import { useState } from 'react'
import { agentTitle, KIND_LABEL, money } from '../format'
import type { Cash, PaymentRequest } from '../types'

interface Props {
  payments: PaymentRequest[]
  cash: Cash | null
  selectedId: number | null
  person: string
  onApprove: (request: PaymentRequest) => Promise<void>
  onReject: (request: PaymentRequest, note: string) => Promise<void>
}

function detailLine(p: PaymentRequest): string {
  if (p.kind === 'invoice') return `Invoice #${p.ref_id}`
  if (p.kind === 'rent') return `Lease #${p.ref_id}`
  return `${p.qty} × ${p.sku} size ${p.size}`
}

function ApprovalCard({ p, cash, highlighted, person, onApprove, onReject }: {
  p: PaymentRequest
  cash: Cash | null
  highlighted: boolean
  person: string
  onApprove: Props['onApprove']
  onReject: Props['onReject']
}) {
  const [mode, setMode] = useState<'idle' | 'confirm' | 'reject'>('idle')
  const [note, setNote] = useState('')
  const [busy, setBusy] = useState(false)
  const after = cash ? cash.balance - p.amount : null
  const overdraw = after !== null && after < 0
  const named = person.trim().length > 0

  async function run(action: () => Promise<void>) {
    setBusy(true)
    await action()
    setBusy(false)
    setMode('idle')
  }

  return (
    <li className={`approval ${highlighted ? 'is-highlighted' : ''}`}>
      <div className="approval-top">
        <span className="approval-kind">{KIND_LABEL[p.kind] ?? p.kind}</span>
        <span className="approval-amount">{money(p.amount)}</span>
      </div>
      <div className="approval-payee">{p.payee}</div>
      <div className="approval-meta">
        {detailLine(p)} · ticket #{p.ticket_id ?? '—'} · request #{p.id}
      </div>
      <p className="approval-reason">{p.reason}</p>
      <div className="approval-meta">Requested by {agentTitle(p.requested_by)}</div>
      {after !== null && (
        <div className={`approval-after ${overdraw ? 'neg' : ''}`}>
          {overdraw ? `Not enough cash: ${money(-after)} short. Approval will be refused.` : `Checking after approval: ${money(after)}`}
        </div>
      )}

      {mode === 'idle' && (
        <div className="approval-buttons">
          <button type="button" className="btn btn-approve" disabled={!named || busy} onClick={() => setMode('confirm')}>
            Approve
          </button>
          <button type="button" className="btn btn-ghost" disabled={!named || busy} onClick={() => setMode('reject')}>
            Reject
          </button>
        </div>
      )}
      {mode === 'confirm' && (
        <div className="approval-confirm">
          <p>
            Pay <b>{money(p.amount)}</b> to <b>{p.payee}</b> from checking, approved by <b>{person.trim()}</b>?
          </p>
          <div className="approval-buttons">
            <button type="button" className="btn btn-approve" disabled={busy} onClick={() => run(() => onApprove(p))}>
              {busy ? 'Paying…' : 'Confirm payment'}
            </button>
            <button type="button" className="btn btn-ghost" disabled={busy} onClick={() => setMode('idle')}>
              Cancel
            </button>
          </div>
        </div>
      )}
      {mode === 'reject' && (
        <div className="approval-confirm">
          <label className="field">
            <span>Reason (optional)</span>
            <input type="text" value={note} onChange={(e) => setNote(e.target.value)} maxLength={500} />
          </label>
          <div className="approval-buttons">
            <button type="button" className="btn btn-reject" disabled={busy} onClick={() => run(() => onReject(p, note))}>
              {busy ? 'Rejecting…' : 'Confirm reject'}
            </button>
            <button type="button" className="btn btn-ghost" disabled={busy} onClick={() => setMode('idle')}>
              Cancel
            </button>
          </div>
        </div>
      )}
    </li>
  )
}

export default function ApprovalQueue({ payments, cash, selectedId, person, onApprove, onReject }: Props) {
  return (
    <div className="panel">
      <div className="panel-head">
        <h2>Needs your approval</h2>
        <span className="count-badge">{payments.length}</span>
      </div>
      {!person.trim() && payments.length > 0 && <p className="hint hint-box">Enter your name at the top to approve or reject.</p>}
      {payments.length === 0 ? (
        <p className="empty">Nothing waiting. Payments and purchase orders the agents queue appear here; no cash moves until a person approves.</p>
      ) : (
        <ul className="approval-list">
          {payments.map((p) => (
            <ApprovalCard
              key={p.id}
              p={p}
              cash={cash}
              highlighted={p.ticket_id === selectedId}
              person={person}
              onApprove={onApprove}
              onReject={onReject}
            />
          ))}
        </ul>
      )}
    </div>
  )
}
