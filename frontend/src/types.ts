// Shapes returned by the FastAPI backend (backend/main.py, backend/models.py).

export type AgentName = 'boss' | 'inventory' | 'accounting' | 'facilities' | 'customer_service'

export type TicketStatus = 'open' | 'waiting_on_approval' | 'blocked' | 'needs_info' | 'resolved'

export interface Ticket {
  id: number
  type: string
  requester: string
  subject: string
  sku: string | null
  size: string | null
  qty: number | null
  lease_id: number | null
  invoice_id: number | null
  status: TicketStatus
  notes: string | null
  created_at: string
  draft_count?: number
  pending_payment_count?: number
  is_open?: boolean
}

export interface TicketList {
  ticket_count: number
  open_count: number
  resolved_count: number
  tickets: Ticket[]
}

export interface CustomerDraft {
  id: number
  ticket_id: number
  recipient: string
  message: string
  drafted_by: string
  created_at: string
  status: 'draft'
}

export interface PaymentRequest {
  id: number
  kind: 'invoice' | 'rent' | 'purchase_order'
  ref_id: number | null
  vendor_id: number | null
  sku: string | null
  size: string | null
  qty: number | null
  amount: number
  payee: string
  account: string
  ticket_id: number | null
  reason: string
  requested_by: string
  requested_at: string
  status: 'pending' | 'paid' | 'rejected'
  decided_by: string | null
  decided_at: string | null
  decision_note: string | null
  payment_id: number | null
}

export interface TicketDetail {
  ticket: Ticket
  customer_drafts: CustomerDraft[]
  payment_requests: PaymentRequest[]
}

export interface ProposedAction {
  kind: string
  description: string
  amount?: number | null
  payee?: string | null
  reference?: string | null
  requires_human_approval: boolean
  blocked_by?: string | null
  payment_request_id?: number | null
}

export interface TicketPlan {
  ticket_id: number
  decision: string
  assigned_agents: AgentName[]
  actions: ProposedAction[]
  customer_message_draft: string | null
  recommended_status: TicketStatus
  reasoning: string
  unknowns: string[]
}

export interface BoardPlan {
  plans: TicketPlan[]
  cash_summary: string
  approval_queue: ProposedAction[]
}

export interface RunInfo {
  run_id: string
  ticket_id: number
  status: 'running' | 'done' | 'error'
  started_at: string
  finished_at: string | null
  error: string | null
  event_count: number
  plan: BoardPlan | null
}

export interface AgentEvent {
  seq: number
  run_id: string
  ticket_id: number
  at: string
  type: 'agent_started' | 'delegated' | 'tool_called' | 'tool_result' | 'delegation_returned' | 'agent_finished' | 'agent_error'
  agent: AgentName
  chain: AgentName[]
  message: string
  tool: string | null
  args: Record<string, unknown> | null
  result: string | null
  to: AgentName | null
  detail: Record<string, unknown> | null
}

export interface EventsResponse {
  events: AgentEvent[]
  last_seq: number
  run_in_progress: boolean
  boot_id: string
}

export interface Cash {
  account: string
  balance: number
  as_of: string
  shop_date: string
}

export interface Health {
  ok: boolean
  model: string
  reasoning_effort: string
  shop_date: string
  run_in_progress: boolean
}

export interface PaymentList {
  count: number
  total_amount: number
  requests: PaymentRequest[]
}
