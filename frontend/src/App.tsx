import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { api, ApiError } from './api'
import ActivityFeed from './components/ActivityFeed'
import AgentBoard from './components/AgentBoard'
import ApprovalQueue from './components/ApprovalQueue'
import BossDecision from './components/BossDecision'
import CustomerDrafts from './components/CustomerDrafts'
import Header from './components/Header'
import TicketList from './components/TicketList'
import TicketPanel from './components/TicketPanel'
import type { AgentEvent, Cash, Health, PaymentRequest, RunInfo, Ticket, TicketDetail } from './types'

const FAST_POLL_MS = 1500 // while the team is working
const SLOW_POLL_MS = 8000 // otherwise

export type Notice = { kind: 'ok' | 'error'; text: string }

function useStoredName(): [string, (name: string) => void] {
  const [name, setName] = useState(() => localStorage.getItem('cc-desk-name') ?? '')
  const save = useCallback((value: string) => {
    setName(value)
    localStorage.setItem('cc-desk-name', value)
  }, [])
  return [name, save]
}

export default function App() {
  const [tickets, setTickets] = useState<Ticket[]>([])
  const [selectedId, setSelectedId] = useState<number | null>(null)
  const [detail, setDetail] = useState<TicketDetail | null>(null)
  const [payments, setPayments] = useState<PaymentRequest[]>([])
  const [cash, setCash] = useState<Cash | null>(null)
  const [health, setHealth] = useState<Health | null>(null)
  const [runs, setRuns] = useState<RunInfo[]>([])
  const [plans, setPlans] = useState<Record<string, RunInfo>>({})
  const [events, setEvents] = useState<AgentEvent[]>([])
  const [connectionError, setConnectionError] = useState<string | null>(null)
  const [notice, setNotice] = useState<Notice | null>(null)
  const [person, setPerson] = useStoredName()
  const lastSeq = useRef(0)
  const bootId = useRef<string | null>(null)
  const selectedRef = useRef<number | null>(null)
  selectedRef.current = selectedId

  const runInProgress = runs.some((r) => r.status === 'running') || Boolean(health?.run_in_progress)

  const refresh = useCallback(async () => {
    try {
      let newEvents = await api.events(lastSeq.current)
      if (bootId.current !== newEvents.boot_id) {
        // The backend restarted: its event numbers start over, so reload the whole feed.
        bootId.current = newEvents.boot_id
        lastSeq.current = 0
        setEvents([])
        newEvents = await api.events(0)
      }
      const [ticketList, paymentList, cashNow, healthNow, runList] = await Promise.all([
        api.tickets(),
        api.payments('pending'),
        api.cash(),
        api.health(),
        api.runs(),
      ])
      setTickets(ticketList.tickets)
      setPayments(paymentList.requests)
      setCash(cashNow)
      setHealth(healthNow)
      setRuns(runList)
      if (newEvents.events.length) {
        lastSeq.current = newEvents.last_seq
        setEvents((prev) => [...prev, ...newEvents.events])
      }
      setSelectedId((current) => current ?? ticketList.tickets.find((t) => t.is_open)?.id ?? ticketList.tickets[0]?.id ?? null)
      const selected = selectedRef.current
      if (selected !== null) setDetail(await api.ticket(selected))
      setConnectionError(null)
    } catch (err) {
      setConnectionError(err instanceof Error ? err.message : String(err))
    }
  }, [])

  // Poll the backend: fast while the team is working, slow otherwise.
  useEffect(() => {
    let stopped = false
    let timer: number | undefined
    const tick = async () => {
      await refresh()
      if (!stopped) timer = window.setTimeout(tick, runInProgress ? FAST_POLL_MS : SLOW_POLL_MS)
    }
    tick()
    return () => {
      stopped = true
      window.clearTimeout(timer)
    }
  }, [refresh, runInProgress])

  // When a run ends, refresh once more right away to pick up its last events and results.
  const wasRunning = useRef(false)
  useEffect(() => {
    if (wasRunning.current && !runInProgress) refresh()
    wasRunning.current = runInProgress
  }, [runInProgress, refresh])

  // Load the selected ticket's details as soon as it's picked.
  useEffect(() => {
    if (selectedId === null) return
    let current = true
    api.ticket(selectedId).then((d) => current && setDetail(d)).catch(() => {})
    return () => {
      current = false
    }
  }, [selectedId])

  const ticketRuns = useMemo(() => runs.filter((r) => r.ticket_id === selectedId), [runs, selectedId])
  const latestRun = ticketRuns[0] ?? null

  // Fetch the Boss's final plan once a run finishes.
  useEffect(() => {
    for (const run of runs) {
      if (run.status !== 'running' && !plans[run.run_id]) {
        api.run(run.run_id).then((full) => setPlans((p) => ({ ...p, [full.run_id]: full }))).catch(() => {})
      }
    }
  }, [runs, plans])

  const runEvents = useMemo(
    () => (latestRun ? events.filter((e) => e.run_id === latestRun.run_id) : []),
    [events, latestRun],
  )
  const latestPlan = latestRun ? plans[latestRun.run_id]?.plan ?? null : null
  const ticketPlan = latestPlan?.plans.find((p) => p.ticket_id === selectedId) ?? latestPlan?.plans[0] ?? null
  const selectedTicket = detail?.ticket.id === selectedId ? detail.ticket : tickets.find((t) => t.id === selectedId) ?? null

  async function act(action: () => Promise<string>) {
    try {
      setNotice({ kind: 'ok', text: await action() })
    } catch (err) {
      setNotice({ kind: 'error', text: err instanceof ApiError || err instanceof Error ? err.message : String(err) })
    }
    await refresh()
  }

  const startRun = (id: number) =>
    act(async () => {
      const run = await api.runTicket(id)
      setRuns((prev) => [run, ...prev])
      return `The agent team started on ticket ${id}.`
    })

  const resolve = (id: number) =>
    act(async () => {
      await api.resolveTicket(id, person.trim())
      return `Ticket ${id} marked resolved by ${person.trim()}.`
    })

  const approve = (request: PaymentRequest) =>
    act(async () => {
      const result = await api.approve(request.id, person.trim())
      return `Paid ${request.payee} for request #${request.id}. Checking is now $${result.balance_after.toFixed(2)}.`
    })

  const reject = (request: PaymentRequest, note: string) =>
    act(async () => {
      await api.reject(request.id, person.trim(), note)
      return `Request #${request.id} rejected. No cash moved.`
    })

  return (
    <div className="app">
      <Header health={health} cash={cash} payments={payments} person={person} onPersonChange={setPerson} runInProgress={runInProgress} />

      {connectionError && (
        <div className="banner banner-error" role="alert">
          {connectionError}
        </div>
      )}
      {notice && (
        <div className={`banner banner-${notice.kind}`} role="status">
          <span>{notice.text}</span>
          <button type="button" className="banner-close" onClick={() => setNotice(null)} aria-label="Dismiss">
            ×
          </button>
        </div>
      )}

      <main className="layout">
        <aside className="col col-tickets">
          <TicketList tickets={tickets} selectedId={selectedId} runs={runs} onSelect={setSelectedId} />
        </aside>

        <section className="col col-main">
          {selectedTicket ? (
            <>
              <TicketPanel
                ticket={selectedTicket}
                detail={detail?.ticket.id === selectedId ? detail : null}
                latestRun={latestRun}
                runInProgress={runInProgress}
                person={person}
                onRun={() => startRun(selectedTicket.id)}
                onResolve={() => resolve(selectedTicket.id)}
              />
              <AgentBoard events={runEvents} run={latestRun} plan={ticketPlan} />
              <BossDecision plan={ticketPlan} cashSummary={latestPlan?.cash_summary ?? null} run={latestRun} />
              <ActivityFeed events={runEvents} running={latestRun?.status === 'running'} />
            </>
          ) : (
            <div className="panel empty">Loading tickets…</div>
          )}
        </section>

        <aside className="col col-side">
          <ApprovalQueue payments={payments} cash={cash} selectedId={selectedId} person={person} onApprove={approve} onReject={reject} />
          <CustomerDrafts drafts={detail?.ticket.id === selectedId ? detail.customer_drafts : []} />
        </aside>
      </main>
    </div>
  )
}
