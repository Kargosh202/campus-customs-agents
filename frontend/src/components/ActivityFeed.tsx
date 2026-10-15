import { useEffect, useMemo, useRef, useState } from 'react'
import { AGENTS, agentTitle, clock } from '../format'
import type { AgentEvent, AgentName } from '../types'

interface Props {
  events: AgentEvent[]
  running: boolean
}

function describe(e: AgentEvent): { title: string; body: string | null } {
  const who = agentTitle(e.agent)
  switch (e.type) {
    case 'agent_started':
      return { title: `${who} started`, body: e.message.replace(/^Started: /, '') }
    case 'delegated':
      return { title: `${who} → ${agentTitle(e.to ?? '')}`, body: e.message.replace(/^Asked [^:]+: /, '') }
    case 'delegation_returned':
      return { title: `${agentTitle(e.to ?? '')} → ${who}`, body: e.message.replace(/^[^ ]+ replied: /, '') }
    case 'tool_called':
      return { title: `${who} used ${e.tool}`, body: e.args && Object.keys(e.args).length ? JSON.stringify(e.args) : null }
    case 'tool_result':
      return { title: `${e.tool} returned`, body: e.result }
    case 'agent_finished':
      return { title: `${who} finished`, body: e.message }
    case 'agent_error':
      return { title: `${who} hit an error`, body: e.message }
    default:
      return { title: e.type, body: e.message }
  }
}

export default function ActivityFeed({ events, running }: Props) {
  const [agentFilter, setAgentFilter] = useState<AgentName | 'all'>('all')
  const [showResults, setShowResults] = useState(false)
  const listRef = useRef<HTMLOListElement>(null)

  const shown = useMemo(
    () =>
      events.filter(
        (e) => (agentFilter === 'all' || e.agent === agentFilter || e.to === agentFilter) && (showResults || e.type !== 'tool_result'),
      ),
    [events, agentFilter, showResults],
  )

  // Keep the newest event in view while the team is working, unless the reader scrolled up.
  useEffect(() => {
    const list = listRef.current
    if (!list || !running) return
    const nearBottom = list.scrollHeight - list.scrollTop - list.clientHeight < 160
    if (nearBottom) list.scrollTop = list.scrollHeight
  }, [shown.length, running])

  return (
    <div className="panel">
      <div className="panel-head">
        <h2>Activity</h2>
        <span className="muted">{events.length} events</span>
      </div>

      <div className="feed-controls">
        <div className="segmented" role="group" aria-label="Filter by agent">
          <button type="button" aria-pressed={agentFilter === 'all'} onClick={() => setAgentFilter('all')}>
            All
          </button>
          {AGENTS.map((a) => (
            <button key={a.name} type="button" aria-pressed={agentFilter === a.name} onClick={() => setAgentFilter(a.name)}>
              {a.title}
            </button>
          ))}
        </div>
        <label className="toggle">
          <input type="checkbox" checked={showResults} onChange={(e) => setShowResults(e.target.checked)} />
          Show tool results
        </label>
      </div>

      {shown.length === 0 ? (
        <p className="empty">{events.length ? 'Nothing for this filter.' : 'Start the agent team to see what each agent says and which tools it uses.'}</p>
      ) : (
        <ol className="feed" ref={listRef} aria-live="polite">
          {shown.map((e) => {
            const { title, body } = describe(e)
            return (
              <li key={e.seq} className={`feed-item feed-${e.type} agent-${e.agent}`}>
                <span className="feed-dot" aria-hidden="true" />
                <div className="feed-body">
                  <div className="feed-title">
                    <span>{title}</span>
                    <time>{clock(e.at)}</time>
                  </div>
                  {e.chain.length > 1 && <div className="feed-chain">{e.chain.map(agentTitle).join(' › ')}</div>}
                  {body && <div className={e.type.startsWith('tool') ? 'feed-code' : 'feed-text'}>{body}</div>}
                </div>
              </li>
            )
          })}
        </ol>
      )}
    </div>
  )
}
