"""Data types shared by the Campus Customs agent team.

- AgentName / AGENT_ROSTER: the five roles and what each one does
- TeamDeps: per-run state passed to every agent (who is asking, the delegation chain, the event log)
- ProposedAction, Fact, SpecialistReport: what a specialist (Inventory, Accounting, Facilities,
  Customer Service) hands back when someone delegates work to it
- TicketPlan / BoardPlan: the Boss's final call on each ticket
- AuditToolCall / AuditEntry: one agent-loop step in output/audit_trail.json
- ApproveRequest, RejectRequest, ResolveRequest, RunInfo, AgentEvent: request and response shapes for backend/main.py
"""

from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field

AgentName = Literal["boss", "inventory", "accounting", "facilities", "customer_service"]

AGENT_ROSTER: dict[str, dict[str, str]] = {
    "boss": {
        "title": "Boss",
        "job": "Reads each ticket, decides who should work on it, and makes the final call.",
    },
    "inventory": {
        "title": "Inventory",
        "job": "Checks stock by SKU and size, spots shortfalls, and works out which vendor can restock.",
    },
    "accounting": {
        "title": "Accounting",
        "job": "Watches cash and invoices, checks margins, and prepares payments or purchase orders for human approval.",
    },
    "facilities": {
        "title": "Facilities",
        "job": "Handles the shop space: leases, rent amounts, and due dates.",
    },
    "customer_service": {
        "title": "Customer Service",
        "job": "Drafts messages for customers. Drafts stay on the board and are never sent.",
    },
}

MAX_DELEGATION_DEPTH = 3  # boss -> inventory -> accounting -> customer_service is the deepest chain


# --- Run state ---------------------------------------------------------------


@dataclass
class TeamDeps:
    """State for one agent inside a team run. Teammates get a copy via for_agent()."""

    agent: AgentName
    chain: list[AgentName]  # who handed work to whom to reach this agent, starting with the first agent
    run_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])  # one id for the whole team run
    events: list[dict[str, Any]] = field(default_factory=list)
    queue: asyncio.Queue | None = None  # live event feed for the dashboard, if one is listening

    @property
    def depth(self) -> int:
        return len(self.chain) - 1

    def for_agent(self, agent: AgentName) -> TeamDeps:
        """Deps for a teammate this agent delegates to. The run id and event log are shared across the run."""
        return TeamDeps(agent=agent, chain=[*self.chain, agent], run_id=self.run_id, events=self.events, queue=self.queue)

    def emit(self, event_type: str, **data: Any) -> None:
        event = {
            "type": event_type,
            "agent": self.agent,
            "chain": list(self.chain),
            "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            **data,
        }
        self.events.append(event)
        if self.queue is not None:
            self.queue.put_nowait(event)


# --- What agents hand back ---------------------------------------------------

ActionKind = Literal[
    "payment",  # pay an invoice or rent (always needs human approval)
    "purchase_order",  # order stock from a vendor (costs cash, so it needs human approval)
    "discount",  # sell below list price
    "customer_message",  # a drafted message that stays on the board
    "lease_update",  # change a lease record, e.g. move next_due after rent is paid
    "ticket_update",  # change a ticket's status or notes
    "inventory_update",  # change stock on hand
    "other",
]


class ProposedAction(BaseModel):
    kind: ActionKind
    description: str = Field(description="What should happen, in one or two plain sentences.")
    amount: float | None = Field(default=None, description="Dollar amount, only if it came from a tool or from arithmetic on tool values.")
    payee: str | None = Field(default=None, description="Who gets paid, for payments and purchase orders.")
    reference: str | None = Field(default=None, description="Related record, e.g. 'invoice 501', 'lease 1', 'ticket 103'.")
    requires_human_approval: bool = Field(description="True for anything that moves cash. A human must approve it before it happens.")
    blocked_by: str | None = Field(default=None, description="What must happen first, if anything (e.g. 'invoice 501 must be paid').")
    payment_request_id: int | None = Field(default=None, description="Id from request_payment, if this action was queued for human approval.")


class Fact(BaseModel):
    label: str = Field(description="What the number or value is, e.g. 'CC-TEE-WHITE size S on hand'.")
    value: str = Field(description="The value exactly as a tool returned it, or arithmetic on tool values.")
    source: str = Field(description="Tool or teammate it came from, e.g. 'check_stock' or 'inventory'.")


class SpecialistReport(BaseModel):
    """What Inventory, Accounting, Facilities, or Customer Service returns to whoever asked."""

    summary: str = Field(description="Two to four sentences answering the task.")
    facts: list[Fact] = Field(default_factory=list, description="Verified facts the summary relies on.")
    proposed_actions: list[ProposedAction] = Field(default_factory=list)
    draft_message: str | None = Field(default=None, description="Customer Service only: the drafted customer message.")
    unknowns: list[str] = Field(default_factory=list, description="Things that could not be checked with the available tools.")


TicketStatus = Literal["resolved", "waiting_on_approval", "blocked", "needs_info"]


class TicketPlan(BaseModel):
    """The Boss's final call on one ticket."""

    ticket_id: int
    decision: str = Field(description="The Boss's call in two to four sentences.")
    assigned_agents: list[AgentName] = Field(description="Teammates who worked on this ticket.")
    actions: list[ProposedAction] = Field(default_factory=list)
    customer_message_draft: str | None = Field(default=None, description="Draft from Customer Service, if the ticket has a customer.")
    recommended_status: TicketStatus
    reasoning: str = Field(description="Why, citing the facts teammates verified.")
    unknowns: list[str] = Field(default_factory=list)


class BoardPlan(BaseModel):
    """The Boss's final call on every ticket in one run."""

    plans: list[TicketPlan]
    cash_summary: str = Field(description="How the proposed payments fit the cash on hand, or what could not be verified.")
    approval_queue: list[ProposedAction] = Field(default_factory=list, description="Every action that needs a human, in priority order.")


# --- Audit trail -------------------------------------------------------------


class AuditToolCall(BaseModel):
    tool_name: str
    args: dict[str, Any] | str
    result: str | None = None  # shortened; None if the step ended before the tool ran


class AuditEntry(BaseModel):
    """One agent-loop step (one model response and the tool results that came back for it)."""

    timestamp: str
    run_id: str  # every agent in one team run shares this
    agent: AgentName
    chain: list[AgentName]  # how the work reached this agent, e.g. boss -> facilities -> accounting
    task: str  # what the agent was asked to do (shortened)
    step: int  # 1, 2, 3 … within this agent's loop
    model: str
    reasoning_effort: str
    text: str | None = None  # any text the model wrote alongside its tool calls
    tool_calls: list[AuditToolCall] = Field(default_factory=list)
    stop_reason: str | None = None
    ended_run: bool = False  # True on the step that produced the agent's final output
    input_tokens: int = 0
    output_tokens: int = 0
    error: str | None = None


# --- API (backend/main.py) ---------------------------------------------------

RunStatus = Literal["running", "done", "error"]


class ApproveRequest(BaseModel):
    approved_by: str = Field(min_length=1, max_length=80, description="Name of the person who clicked Approve.")


class RejectRequest(BaseModel):
    rejected_by: str = Field(min_length=1, max_length=80)
    note: str = Field(default="", max_length=500)


class ResolveRequest(BaseModel):
    resolved_by: str = Field(min_length=1, max_length=80, description="Name of the person marking it resolved.")
    note: str = Field(default="", max_length=500)


class RunInfo(BaseModel):
    run_id: str
    ticket_id: int
    status: RunStatus
    started_at: str
    finished_at: str | None = None
    error: str | None = None
    event_count: int = 0
    plan: BoardPlan | None = None


class AgentEvent(BaseModel):
    """One thing that happened in a run, shaped for the dashboard's activity feed."""

    seq: int  # increasing across the server's life; poll with ?since=<last seq>
    run_id: str
    ticket_id: int
    at: str
    type: str  # agent_started, delegated, tool_called, tool_result, delegation_returned, agent_finished, agent_error
    agent: str
    chain: list[str]
    message: str  # what the agent said or did, in one line
    tool: str | None = None
    args: dict[str, Any] | None = None
    result: str | None = None
    to: str | None = None  # delegated / delegation_returned: the teammate
    detail: dict[str, Any] | None = None  # agent_finished: the agent's full output
