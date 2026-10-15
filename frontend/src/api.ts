// Calls to the FastAPI backend. It runs at http://localhost:8000 (see backend/main.py).
import type {
  Cash,
  EventsResponse,
  Health,
  PaymentList,
  RunInfo,
  TicketDetail,
  TicketList,
} from './types'

export const API_BASE: string = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

export class ApiError extends Error {
  status: number
  detail: unknown

  constructor(status: number, detail: unknown) {
    super(errorText(detail) ?? `Request failed (${status})`)
    this.status = status
    this.detail = detail
  }
}

function errorText(detail: unknown): string | undefined {
  if (typeof detail === 'string') return detail
  if (detail && typeof detail === 'object') {
    const d = detail as Record<string, unknown>
    if (typeof d.error === 'string') {
      if (typeof d.short_by === 'number') return `${d.error} Short by $${d.short_by.toFixed(2)}.`
      return d.error
    }
    if (Array.isArray(detail) && detail[0]?.msg) return String(detail[0].msg)
  }
  return undefined
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response
  try {
    response = await fetch(`${API_BASE}${path}`, {
      ...init,
      headers: { 'Content-Type': 'application/json', ...init?.headers },
    })
  } catch {
    throw new ApiError(0, `Can't reach the backend at ${API_BASE}. Is uvicorn running?`)
  }
  const body = await response.json().catch(() => null)
  if (!response.ok) throw new ApiError(response.status, body?.detail ?? body)
  return body as T
}

const post = <T>(path: string, body?: unknown) =>
  request<T>(path, { method: 'POST', body: body === undefined ? undefined : JSON.stringify(body) })

export const api = {
  health: () => request<Health>('/api/health'),
  tickets: () => request<TicketList>('/api/tickets'),
  ticket: (id: number) => request<TicketDetail>(`/api/tickets/${id}`),
  runTicket: (id: number) => post<RunInfo>(`/api/tickets/${id}/run`),
  resolveTicket: (id: number, resolvedBy: string, note = '') =>
    post<unknown>(`/api/tickets/${id}/resolve`, { resolved_by: resolvedBy, note }),
  runs: () => request<RunInfo[]>('/api/runs'),
  run: (runId: string) => request<RunInfo>(`/api/runs/${runId}`),
  events: (since: number) => request<EventsResponse>(`/api/events?since=${since}&limit=1000`),
  payments: (status: 'pending' | 'paid' | 'rejected' | 'all' = 'pending') =>
    request<PaymentList>(`/api/payments?status=${status}`),
  approve: (id: number, approvedBy: string) =>
    post<{ paid: boolean; balance_after: number }>(`/api/payments/${id}/approve`, { approved_by: approvedBy }),
  reject: (id: number, rejectedBy: string, note: string) =>
    post<unknown>(`/api/payments/${id}/reject`, { rejected_by: rejectedBy, note }),
  cash: () => request<Cash>('/api/cash'),
}
