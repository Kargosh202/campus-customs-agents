"""The Campus Customs team: the five agents and the loops that run them.

- run_agent(name, task, deps): one agent's loop (model -> MCP tools / ask_teammate -> model ...)
  until it returns its structured report. ask_teammate calls back into run_agent, so any agent
  can start another agent's loop.
- run_board(ticket_ids): the Boss works the board and returns a BoardPlan plus the event log.

Every loop step of every agent is appended to output/audit_trail.json as it finishes (audit.py).
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from pydantic_ai import Agent
from pydantic_ai.usage import UsageLimits

from agents.accounting import accounting_agent
from agents.boss import boss_agent
from agents.config import MCP_TOOLSET, MODEL_NAME, REASONING_EFFORT, build_model, model_settings
from agents.customer_service import customer_service_agent
from agents.facilities import facilities_agent
from agents.inventory import inventory_agent
from audit import StepRecorder
from models import AgentName, BoardPlan, SpecialistReport, TeamDeps

AGENTS: dict[AgentName, Agent[TeamDeps, Any]] = {
    "boss": boss_agent,
    "inventory": inventory_agent,
    "accounting": accounting_agent,
    "facilities": facilities_agent,
    "customer_service": customer_service_agent,
}

BOSS_REQUEST_LIMIT = 30  # model calls the Boss may make for one board run
TEAMMATE_REQUEST_LIMIT = 15  # model calls a teammate may make for one delegated task


async def run_loop(name: AgentName, task: str, deps: TeamDeps, output_type: type, request_limit: int) -> Any:
    """Run one agent's loop step by step, writing each step to the audit trail as it finishes."""
    recorder = StepRecorder(deps, task, MODEL_NAME, REASONING_EFFORT)
    try:
        async with AGENTS[name].iter(
            task,
            deps=deps,
            output_type=output_type,
            model=build_model(),
            model_settings=model_settings(),
            usage_limits=UsageLimits(request_limit=request_limit),
        ) as run:
            async for node in run:
                if Agent.is_call_tools_node(node):
                    recorder.model_responded(node.model_response)
                elif Agent.is_model_request_node(node):
                    recorder.tools_returned(node.request)
            output = run.result.output
    except BaseException as exc:
        recorder.failed(exc)
        raise
    recorder.finished(output)
    return output


async def run_agent(name: AgentName, task: str, deps: TeamDeps) -> SpecialistReport:
    """Run one teammate's agent loop on a delegated task. Failures come back as a report, not a crash,
    so the agent that asked can carry on."""
    deps.emit("agent_started", task=task)
    try:
        # The Boss also answers teammates with a report rather than a BoardPlan.
        report = await run_loop(name, task, deps, SpecialistReport, TEAMMATE_REQUEST_LIMIT)
    except Exception as exc:
        report = SpecialistReport(
            summary=f"{name} could not finish this task ({type(exc).__name__}).",
            unknowns=[f"{name} failed: {type(exc).__name__}: {exc}"],
        )
        deps.emit("agent_error", error=f"{type(exc).__name__}: {exc}")
    deps.emit("agent_finished", output=report.model_dump(exclude_none=True))
    return report


def _board_task(ticket_ids: list[int] | None) -> str:
    if ticket_ids:
        ids = ", ".join(str(i) for i in ticket_ids)
        return (
            f"Work ticket(s) {ids} on the board. Read them with get_ticket, route the work to teammates, "
            "record your call on each ticket with update_ticket, and return a TicketPlan for each one in "
            "your BoardPlan."
        )
    return (
        "Work every open ticket on the board. Read them with list_open_tickets, route the work to "
        "teammates, settle any conflicts over cash between tickets, record your call on each ticket with "
        "update_ticket, and return a TicketPlan for each ticket in your BoardPlan."
    )


async def run_board(
    ticket_ids: list[int] | None = None, queue: asyncio.Queue | None = None, run_id: str | None = None
) -> tuple[BoardPlan, list[dict[str, Any]], str]:
    """The Boss works the board (all open tickets, or just ticket_ids).
    Returns the plan, every event, and the run id used in the audit trail."""
    deps = TeamDeps(agent="boss", chain=["boss"], queue=queue)
    if run_id:
        deps.run_id = run_id
    task = _board_task(ticket_ids)
    deps.emit("agent_started", task=task)
    async with MCP_TOOLSET:  # one MCP server process for the whole run
        plan = await run_loop("boss", task, deps, BoardPlan, BOSS_REQUEST_LIMIT)
    deps.emit("agent_finished", output=plan.model_dump(exclude_none=True))
    return plan, deps.events, deps.run_id


RUNS_DIR = Path(__file__).resolve().parents[2] / "output" / "team_runs"


def save_run(run_id: str, ticket_ids: list[int] | None, plan: BoardPlan, events: list[dict[str, Any]]) -> Path:
    """Save one run's plan and full event log to output/team_runs/."""
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    path = RUNS_DIR / f"run-{datetime.now():%Y%m%d-%H%M%S}-{run_id}.json"
    payload = {
        "run_id": run_id,
        "model": MODEL_NAME,
        "reasoning_effort": REASONING_EFFORT,
        "ticket_ids": ticket_ids,
        "plan": plan.model_dump(),
        "events": events,
    }
    path.write_text(json.dumps(payload, indent=2, default=str))
    return path
