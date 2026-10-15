"""Campus Customs operations API: what the React dashboard calls.

Every shop fact comes from the MCP server (mcp_server/server.py on data/campus_customs_new.db);
this file never opens the database. Agent runs happen in the background, and the dashboard polls
/api/events to watch them. Runs are kept in memory and reloaded from output/team_runs/ on restart.

Run from HW 5/backend (with the HW 5 .venv active, or as ../.venv/bin/uvicorn):
    uvicorn main:app --reload --port 8000
The dashboard calls it at http://localhost:8000.

Routes
    GET  /                                this list of routes
    GET  /api/health                      model, shop date, whether a run is going
    GET  /api/tickets                     all tickets, each open or resolved
    GET  /api/tickets/{id}                one ticket with its drafts and payment requests
    POST /api/tickets/{id}/run            start the agent team on one ticket (202, returns run_id)
    POST /api/tickets/{id}/resolve        a person marks the ticket resolved (refused while payments are pending)
    GET  /api/runs, /api/runs/{run_id}    run status and the Boss's final plan
    GET  /api/events?since=&run_id=       recent agent events: who said what, which tools they used
    GET  /api/payments?status=pending     payment and purchase-order requests
    POST /api/payments/{id}/approve       a person approved it: pay it (refuses negative balances)
    POST /api/payments/{id}/reject        a person rejected it
    GET  /api/cash                        current checking balance
"""

from __future__ import annotations

import asyncio
import json
from collections import deque
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any, Literal
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from agents.config import MCP_TOOLSET, MODEL_NAME, REASONING_EFFORT
from agents.team import RUNS_DIR, run_board, save_run
from models import AGENT_ROSTER, AgentEvent, ApproveRequest, BoardPlan, RejectRequest, ResolveRequest, RunInfo

MAX_EVENTS = 5000  # events kept in memory for the activity feed


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


async def mcp(tool: str, **args: Any) -> dict[str, Any]:
    """Call an MCP tool and return its result."""
    return await MCP_TOOLSET.direct_call_tool(tool, args)


def tool_error(result: dict[str, Any], status: int = 400) -> None:
    if isinstance(result, dict) and "error" in result:
        raise HTTPException(status_code=status, detail=result)


# --- Run and event state (in memory, for the life of the server) -------------

runs: dict[str, RunInfo] = {}
events: deque[AgentEvent] = deque(maxlen=MAX_EVENTS)
next_seq = 1
run_lock = asyncio.Lock()  # one team run at a time: runs share one cash balance
BOOT_ID = uuid4().hex[:8]  # changes on every restart, so the dashboard knows to reload its feed


def describe(event: dict[str, Any]) -> str:
    kind = event["type"]
    if kind == "agent_started":
        return f"Started: {event.get('task', '')}"
    if kind == "delegated":
        return f"Asked {event['to']}: {event.get('task', '')}"
    if kind == "delegation_returned":
        return f"{event['to']} replied: {event.get('summary', '')}"
    if kind == "tool_called":
        return f"Called {event['tool']}"
    if kind == "tool_result":
        return f"{event['tool']} returned"
    if kind == "agent_finished":
        output = event.get("output") or {}
        if "plans" in output:  # the Boss's BoardPlan
            return " ".join(p.get("decision", "") for p in output["plans"]) or "Finished."
        return output.get("summary", "Finished.")
    if kind == "agent_error":
        return f"Error: {event.get('error', '')}"
    return kind


def record(run_id: str, ticket_id: int, event: dict[str, Any]) -> None:
    global next_seq
    events.append(
        AgentEvent(
            seq=next_seq,
            run_id=run_id,
            ticket_id=ticket_id,
            at=event.get("at", now()),
            type=event["type"],
            agent=event["agent"],
            chain=event.get("chain", []),
            message=describe(event),
            tool=event.get("tool"),
            args=event.get("args"),
            result=event.get("result"),
            to=event.get("to"),
            detail=event.get("output") if event["type"] == "agent_finished" else None,
        )
    )
    next_seq += 1
    runs[run_id].event_count += 1


async def run_ticket(run_id: str, ticket_id: int) -> None:
    """Background job: the team works one ticket while its events stream into the feed."""
    queue: asyncio.Queue = asyncio.Queue()

    async def drain() -> None:
        while True:
            record(run_id, ticket_id, await queue.get())

    drainer = asyncio.create_task(drain())
    info = runs[run_id]
    status: Literal["done", "error"] = "error"
    try:
        plan, all_events, _ = await run_board([ticket_id], queue=queue, run_id=run_id)
        info.plan, status = plan, "done"
        save_run(run_id, [ticket_id], plan, all_events)
    except Exception as exc:
        info.error = f"{type(exc).__name__}: {exc}"
    finally:
        drainer.cancel()
        while not queue.empty():
            record(run_id, ticket_id, queue.get_nowait())
        # Mark the run finished only after its last events are in the feed, so a dashboard that
        # sees "done" has already been able to fetch every event.
        info.status, info.finished_at = status, now()
        run_lock.release()


# --- App ----------------------------------------------------------------------


def load_saved_runs(limit: int = 30) -> None:
    """Put recent single-ticket runs from output/team_runs/ back on the board after a restart.
    Runs from before the last database reset (backend/reset_db.py) are skipped: they describe a board
    that no longer exists."""
    marker = RUNS_DIR.parents[1] / "data" / "last_reset.txt"
    reset_at = marker.stat().st_mtime if marker.exists() else 0
    for path in sorted(RUNS_DIR.glob("run-*.json"))[-limit:]:
        if path.stat().st_mtime < reset_at:
            continue
        try:
            saved = json.loads(path.read_text())
            ticket_ids = saved.get("ticket_ids") or []
            if len(ticket_ids) != 1 or not saved.get("events"):
                continue
            run_id, ticket_id = saved["run_id"], ticket_ids[0]
            saved_events = saved["events"]
            runs[run_id] = RunInfo(
                run_id=run_id,
                ticket_id=ticket_id,
                status="done",
                started_at=saved_events[0].get("at", now()),
                finished_at=saved_events[-1].get("at", now()),
                plan=BoardPlan.model_validate(saved["plan"]),
            )
            for event in saved_events:
                record(run_id, ticket_id, event)
        except (KeyError, ValueError, TypeError):
            continue  # skip files from older formats


@asynccontextmanager
async def lifespan(app: FastAPI):
    load_saved_runs()
    async with MCP_TOOLSET:  # one MCP server process for the life of the API
        yield


app = FastAPI(title="Campus Customs Operations", version="1.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    # The Vite dashboard's page origin (npm run dev serves it on :5173). The regex also allows any
    # other local port, in case Vite picks the next free one, but never another host.
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_origin_regex=r"http://(localhost|127\.0\.0\.1):\d+",
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


@app.get("/")
async def index() -> dict[str, Any]:
    """What http://localhost:8000 serves: the API's routes, for the dashboard and for a quick check."""
    return {
        "name": "Campus Customs Operations API",
        "docs": "/docs",
        "routes": [
            f"{method} {route.path}"
            for route in app.routes
            if getattr(route, "path", "").startswith("/api")
            for method in sorted(getattr(route, "methods", []) or [])
        ],
    }


@app.get("/api/health")
async def health() -> dict[str, Any]:
    desk = await mcp("get_shop_date")
    return {
        "ok": True,
        "model": MODEL_NAME,
        "reasoning_effort": REASONING_EFFORT,
        "shop_date": desk["date_today"],
        "run_in_progress": run_lock.locked(),
    }


@app.get("/api/tickets")
async def list_tickets() -> dict[str, Any]:
    """Every ticket with `is_open` (true until it's resolved)."""
    return await mcp("list_tickets")


@app.get("/api/tickets/{ticket_id}")
async def get_ticket(ticket_id: int) -> dict[str, Any]:
    result = await mcp("get_ticket", ticket_id=ticket_id)
    tool_error(result, 404)
    return result


@app.post("/api/tickets/{ticket_id}/run", status_code=202)
async def start_run(ticket_id: int) -> RunInfo:
    """Start the agent team on one ticket. Returns at once; watch /api/events for progress."""
    tool_error(await mcp("get_ticket", ticket_id=ticket_id), 404)
    if run_lock.locked():
        active = next((r for r in runs.values() if r.status == "running"), None)
        raise HTTPException(409, {"error": "The team is already working a ticket.", "run": active.model_dump() if active else None})
    await run_lock.acquire()  # released when the run finishes
    run_id = uuid4().hex[:12]
    runs[run_id] = RunInfo(run_id=run_id, ticket_id=ticket_id, status="running", started_at=now())
    asyncio.create_task(run_ticket(run_id, ticket_id))
    return runs[run_id]


@app.post("/api/tickets/{ticket_id}/resolve")
async def resolve_ticket(ticket_id: int, body: ResolveRequest) -> dict[str, Any]:
    """A person marks a ticket resolved after the team finishes. Refused (409) while one of its
    payment requests is still waiting for a human, or while the team is working it."""
    name = body.resolved_by.strip()
    if name.lower() in AGENT_ROSTER:
        raise HTTPException(400, {"error": "A ticket is marked resolved by a person, not an agent."})
    if any(r.status == "running" and r.ticket_id == ticket_id for r in runs.values()):
        raise HTTPException(409, {"error": "The team is still working this ticket."})
    note = f"Marked resolved by {name}." + (f" {body.note.strip()}" if body.note.strip() else "")
    result = await mcp("update_ticket", ticket_id=ticket_id, status="resolved", note=note, updated_by=name)
    if isinstance(result, dict) and "pending_request_ids" in result:
        raise HTTPException(409, result)
    tool_error(result)
    return result


@app.get("/api/runs")
async def list_runs() -> list[RunInfo]:
    """Runs since the server started, newest first (without plans, to keep it light)."""
    return [r.model_copy(update={"plan": None}) for r in sorted(runs.values(), key=lambda r: r.started_at, reverse=True)]


@app.get("/api/runs/{run_id}")
async def get_run(run_id: str) -> RunInfo:
    if run_id not in runs:
        raise HTTPException(404, {"error": f"Unknown run {run_id}."})
    return runs[run_id]


@app.get("/api/events")
async def list_events(
    since: int = Query(0, ge=0, description="Only events with seq greater than this"),
    run_id: str | None = None,
    ticket_id: int | None = None,
    limit: int = Query(200, ge=1, le=1000),
) -> dict[str, Any]:
    """Recent agent events, oldest first: what each agent said and which tools it used.
    Poll with ?since=<last_seq> to get only what's new."""
    matched = [
        e for e in events
        if e.seq > since and (run_id is None or e.run_id == run_id) and (ticket_id is None or e.ticket_id == ticket_id)
    ][-limit:]
    return {
        "events": matched,
        "last_seq": matched[-1].seq if matched else since,
        "run_in_progress": run_lock.locked(),
        "boot_id": BOOT_ID,
    }


@app.get("/api/payments")
async def list_payments(status: Literal["pending", "paid", "rejected", "all"] = "pending") -> dict[str, Any]:
    """Payment and purchase-order requests the agents queued for a human."""
    return await mcp("list_payment_requests", status=status)


@app.post("/api/payments/{request_id}/approve")
async def approve_payment(request_id: int, body: ApproveRequest) -> dict[str, Any]:
    """A person clicked Approve. Pays the request; refuses (409) if cash would go below zero."""
    result = await mcp("pay_request", request_id=request_id, approved_by=body.approved_by)
    if isinstance(result, dict) and "short_by" in result:
        raise HTTPException(409, result)
    tool_error(result)
    return result


@app.post("/api/payments/{request_id}/reject")
async def reject_payment(request_id: int, body: RejectRequest) -> dict[str, Any]:
    """A person clicked Reject. No cash moves."""
    result = await mcp("reject_payment_request", request_id=request_id, rejected_by=body.rejected_by, note=body.note)
    tool_error(result)
    return result


@app.get("/api/cash")
async def cash() -> dict[str, Any]:
    """Current checking balance from cash_accounts."""
    result = await mcp("get_cash_balance", account="checking")
    tool_error(result, 404)
    account = result["accounts"][0]
    return {"account": account["name"], "balance": account["balance"], "as_of": account["date"], "shop_date": result["date_today"]}
