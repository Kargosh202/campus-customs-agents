import { clock } from '../format'
import type { CustomerDraft } from '../types'

export default function CustomerDrafts({ drafts }: { drafts: CustomerDraft[] }) {
  const latest = drafts.at(-1)
  const earlier = drafts.slice(0, -1).reverse()

  return (
    <div className="panel">
      <div className="panel-head">
        <h2>Customer drafts</h2>
        <span className="muted">Never sent</span>
      </div>
      {!latest ? (
        <p className="empty">No draft for this ticket. Customer Service saves one here when a customer needs a reply.</p>
      ) : (
        <>
          <article className="draft">
            <div className="draft-head">
              To <b>{latest.recipient}</b>
              <span className="draft-badge">Draft</span>
            </div>
            <div className="draft-body">{latest.message}</div>
            <div className="muted small">Saved {clock(latest.created_at)} by Customer Service</div>
          </article>
          {earlier.length > 0 && (
            <details className="draft-history">
              <summary>
                {earlier.length} earlier version{earlier.length > 1 ? 's' : ''}
              </summary>
              {earlier.map((d) => (
                <div key={d.id} className="draft-body draft-old">
                  {d.message}
                </div>
              ))}
            </details>
          )}
        </>
      )}
    </div>
  )
}
