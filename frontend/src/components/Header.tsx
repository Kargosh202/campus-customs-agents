import { money, shortDate } from '../format'
import type { Cash, Health, PaymentRequest } from '../types'

interface Props {
  health: Health | null
  cash: Cash | null
  payments: PaymentRequest[]
  person: string
  onPersonChange: (name: string) => void
  runInProgress: boolean
}

export default function Header({ health, cash, payments, person, onPersonChange, runInProgress }: Props) {
  const pendingTotal = payments.reduce((sum, p) => sum + p.amount, 0)
  const afterPending = cash ? cash.balance - pendingTotal : null

  return (
    <header className="masthead">
      <div className="masthead-inner">
        <div className="brand">
          <div className="brand-mark" aria-hidden="true">CC</div>
          <div>
            <div className="brand-name">Campus Customs</div>
            <div className="brand-sub">Operations Desk</div>
          </div>
        </div>

        <dl className="masthead-facts">
          <div>
            <dt>Shop date</dt>
            <dd>{health ? shortDate(health.shop_date) : '—'}</dd>
          </div>
          <div>
            <dt>Agent team</dt>
            <dd>
              <span className={`dot ${runInProgress ? 'dot-live' : 'dot-idle'}`} aria-hidden="true" />
              {runInProgress ? 'Working' : 'Idle'}
              {health && <span className="muted"> · {health.model}</span>}
            </dd>
          </div>
        </dl>

        <div className="balance-card" aria-label="Checking balance">
          <div className="balance-label">Checking balance</div>
          <div className="balance-amount">{cash ? money(cash.balance) : '—'}</div>
          <div className="balance-meta">
            {payments.length > 0 && afterPending !== null ? (
              <>
                {payments.length} pending · {money(pendingTotal)} ·{' '}
                <span className={afterPending < 0 ? 'neg' : ''}>after all: {money(afterPending)}</span>
              </>
            ) : (
              <>As of {cash ? shortDate(cash.as_of) : '—'}</>
            )}
          </div>
        </div>

        <label className="person">
          <span>Signed in as</span>
          <input
            type="text"
            value={person}
            onChange={(e) => onPersonChange(e.target.value)}
            placeholder="Your name"
            maxLength={80}
            autoComplete="name"
          />
        </label>
      </div>
    </header>
  )
}
