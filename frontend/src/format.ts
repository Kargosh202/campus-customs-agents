import type { AgentName, TicketStatus } from './types'

export const AGENTS: { name: AgentName; title: string; initials: string; job: string }[] = [
  { name: 'boss', title: 'Boss', initials: 'B', job: 'Reads each ticket, routes the work, makes the final call' },
  { name: 'inventory', title: 'Inventory', initials: 'I', job: 'Stock by SKU and size, shortfalls, restock vendors' },
  { name: 'accounting', title: 'Accounting', initials: 'A', job: 'Cash, invoices, margins; queues payments for approval' },
  { name: 'facilities', title: 'Facilities', initials: 'F', job: 'Leases, rent amounts, and due dates' },
  { name: 'customer_service', title: 'Customer Service', initials: 'CS', job: 'Drafts customer messages (never sent)' },
]

export const agentTitle = (name: string) => AGENTS.find((a) => a.name === name)?.title ?? name

export const money = (n: number) =>
  n.toLocaleString('en-US', { style: 'currency', currency: 'USD' })

export const STATUS_LABEL: Record<TicketStatus, string> = {
  open: 'Open',
  waiting_on_approval: 'Waiting on approval',
  blocked: 'Blocked',
  needs_info: 'Needs info',
  resolved: 'Resolved',
}

export const TYPE_LABEL: Record<string, string> = {
  customer_order: 'Customer order',
  rent_notice: 'Rent notice',
  price_override: 'Discount request',
}

export const KIND_LABEL: Record<string, string> = {
  invoice: 'Vendor invoice',
  rent: 'Rent',
  purchase_order: 'Purchase order',
}

export function clock(iso: string): string {
  const d = new Date(iso)
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit', second: '2-digit' })
}

export function shortDate(iso: string): string {
  const d = new Date(iso.length === 10 ? `${iso}T12:00:00` : iso)
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
}
