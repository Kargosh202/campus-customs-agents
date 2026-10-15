import { agentTitle, money } from '../format'
import type { RunInfo, TicketPlan } from '../types'
import StatusPill from './StatusPill'

interface Props {
  plan: TicketPlan | null
  cashSummary: string | null
  run: RunInfo | null
}

export default function BossDecision({ plan, cashSummary, run }: Props) {
  if (!run || run.status === 'running') return null
  if (run.status === 'error') {
    return (
      <div className="panel">
        <div className="panel-head">
          <h2>Boss's decision</h2>
        </div>
        <p className="error-text">The run failed: {run.error}</p>
      </div>
    )
  }
  if (!plan) return null

  return (
    <div className="panel decision">
      <div className="panel-head">
        <h2>Boss's decision</h2>
        <StatusPill status={plan.recommended_status} />
      </div>
      <p className="decision-text">{plan.decision}</p>

      {plan.actions.length > 0 && (
        <>
          <h3>Actions</h3>
          <ol className="action-list">
            {plan.actions.map((a, i) => (
              <li key={i}>
                <span className="action-kind">{a.kind.replace(/_/g, ' ')}</span>
                {a.description}
                <div className="action-meta">
                  {a.amount != null && <span>{money(a.amount)}</span>}
                  {a.payee && <span>to {a.payee}</span>}
                  {a.payment_request_id != null && <span>request #{a.payment_request_id}</span>}
                  {a.requires_human_approval && <span className="tag-approval">needs human approval</span>}
                  {a.blocked_by && <span className="tag-blocked">blocked: {a.blocked_by}</span>}
                </div>
              </li>
            ))}
          </ol>
        </>
      )}

      <div className="decision-cols">
        <div>
          <h3>Why</h3>
          <p>{plan.reasoning}</p>
        </div>
        {cashSummary && (
          <div>
            <h3>Cash</h3>
            <p>{cashSummary}</p>
          </div>
        )}
      </div>

      {plan.unknowns.length > 0 && (
        <>
          <h3>Couldn't verify</h3>
          <ul className="plain-list">
            {plan.unknowns.map((u, i) => (
              <li key={i}>{u}</li>
            ))}
          </ul>
        </>
      )}

      <p className="muted small">Worked by {plan.assigned_agents.map(agentTitle).join(', ') || 'the Boss alone'}.</p>
    </div>
  )
}
