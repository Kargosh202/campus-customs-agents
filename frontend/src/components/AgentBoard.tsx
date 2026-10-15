import { AGENTS, agentTitle } from '../format'
import type { AgentEvent, AgentName, RunInfo, TicketPlan } from '../types'

interface Props {
  events: AgentEvent[]
  run: RunInfo | null
  plan: TicketPlan | null
}

type State = 'idle' | 'waiting' | 'working' | 'done' | 'error' | 'not-needed'

interface AgentSummary {
  state: State
  saying: string | null
  tools: [string, number][]
  asked: AgentName[]
  reports: string[]
}

function summarize(name: AgentName, events: AgentEvent[], run: RunInfo | null, plan: TicketPlan | null): AgentSummary {
  const mine = events.filter((e) => e.agent === name)
  const started = mine.filter((e) => e.type === 'agent_started').length
  const finished = mine.filter((e) => e.type === 'agent_finished').length
  const errored = mine.some((e) => e.type === 'agent_error')

  const toolCounts = new Map<string, number>()
  for (const e of mine) if (e.type === 'tool_called' && e.tool) toolCounts.set(e.tool, (toolCounts.get(e.tool) ?? 0) + 1)

  const asked = [...new Set(mine.filter((e) => e.type === 'delegated' && e.to).map((e) => e.to as AgentName))]

  const reports = mine
    .filter((e) => e.type === 'agent_finished')
    .map((e) => (name === 'boss' && plan ? plan.decision : e.message))

  const latest = [...mine].reverse().find((e) => ['agent_finished', 'delegated', 'agent_started', 'agent_error'].includes(e.type))
  let saying: string | null = null
  if (latest?.type === 'delegated') saying = `Asking ${agentTitle(latest.to ?? '')}: ${latest.message.replace(/^Asked [^:]+: /, '')}`
  else if (latest?.type === 'agent_started') saying = `Working on: ${latest.message.replace(/^Started: /, '')}`
  else if (latest) saying = latest.message

  let state: State = 'idle'
  if (!run) state = 'idle'
  else if (errored) state = 'error'
  else if (started > finished) state = 'working'
  else if (finished > 0) state = 'done'
  else state = run.status === 'running' ? 'waiting' : 'not-needed'

  return { state, saying, tools: [...toolCounts.entries()], asked, reports }
}

const STATE_LABEL: Record<State, string> = {
  idle: 'Idle',
  waiting: 'Standing by',
  working: 'Working',
  done: 'Done',
  error: 'Error',
  'not-needed': 'Not needed',
}

function oneLine(name: AgentName, s: AgentSummary): string {
  if (s.state === 'idle') return 'No run yet for this ticket.'
  if (s.state === 'waiting' || s.state === 'not-needed') return s.state === 'waiting' ? 'Not called in yet.' : 'Not needed on this ticket.'
  const parts: string[] = []
  const toolCalls = s.tools.reduce((n, [, c]) => n + c, 0)
  if (toolCalls) parts.push(`${toolCalls} tool call${toolCalls > 1 ? 's' : ''}`)
  if (s.asked.length) parts.push(`asked ${s.asked.map(agentTitle).join(', ')}`)
  if (s.reports.length > 1) parts.push(`${s.reports.length} reports`)
  if (name === 'customer_service' && s.tools.some(([t]) => t === 'save_customer_draft')) parts.push('saved a draft')
  if (name === 'accounting' && s.tools.some(([t]) => t === 'request_payment')) parts.push('queued a payment for approval')
  if (name === 'boss' && s.tools.some(([t]) => t === 'update_ticket')) parts.push('updated the ticket')
  return parts.length ? parts.join(' · ') : 'Working…'
}

export default function AgentBoard({ events, run, plan }: Props) {
  return (
    <div className="panel">
      <div className="panel-head">
        <h2>Agent team</h2>
        <span className="muted">
          {run ? (run.status === 'running' ? 'Live' : `Last run ${run.status === 'done' ? 'finished' : 'failed'}`) : 'Not run yet'}
        </span>
      </div>
      <div className="agent-grid">
        {AGENTS.map((agent) => {
          const s = summarize(agent.name, events, run, plan)
          const report = s.reports.at(-1)
          return (
            <article key={agent.name} className={`agent-card agent-${agent.name} state-${s.state}`} aria-live="polite">
              <header className="agent-card-head">
                <span className="agent-avatar" aria-hidden="true">
                  {agent.initials}
                </span>
                <div>
                  <h3>{agent.title}</h3>
                  <div className="agent-job">{agent.job}</div>
                </div>
                <span className={`agent-state state-${s.state}`}>
                  {s.state === 'working' && <span className="spinner spinner-sm" aria-hidden="true" />}
                  {STATE_LABEL[s.state]}
                </span>
              </header>

              <div className="agent-summary">{oneLine(agent.name, s)}</div>

              {s.state === 'working' && s.saying && <p className="agent-saying">{s.saying}</p>}
              {s.state !== 'working' && report && (
                <p className="agent-saying">
                  <span className="quote-label">{agent.name === 'boss' ? 'Decision' : 'Reported'}</span>
                  {report}
                </p>
              )}

              {s.tools.length > 0 && (
                <ul className="tool-chips" aria-label={`${agent.title} tools used`}>
                  {s.tools.map(([tool, count]) => (
                    <li key={tool} className="chip">
                      {tool}
                      {count > 1 && <span className="chip-count">×{count}</span>}
                    </li>
                  ))}
                </ul>
              )}
            </article>
          )
        })}
      </div>
    </div>
  )
}
