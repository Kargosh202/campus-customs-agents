"""Run the agent team from the command line and save the result.

From HW 5/backend:
    ../.venv/bin/python run_team.py               # every open ticket
    ../.venv/bin/python run_team.py --ticket 102  # one ticket (repeat --ticket for more)

Prints each event as it happens and saves the plan and full event log to output/team_runs/.
"""

from __future__ import annotations

import argparse
import asyncio
import json

from agents.config import MODEL_NAME, REASONING_EFFORT
from agents.team import run_board, save_run

def describe(event: dict) -> str:
    who = " > ".join(event["chain"])
    kind = event["type"]
    if kind == "agent_started":
        return f"[{who}] started: {event['task'][:160]}"
    if kind == "delegated":
        return f"[{who}] -> {event['to']}: {event['task'][:160]}"
    if kind == "delegation_returned":
        return f"[{who}] <- {event['to']}: {event['summary'][:160]}"
    if kind == "tool_called":
        return f"[{who}] tool {event['tool']}({json.dumps(event['args'])})"
    if kind == "tool_result":
        return f"[{who}] tool {event['tool']} returned {event['result'][:160]}"
    if kind == "agent_error":
        return f"[{who}] ERROR {event['error'][:200]}"
    return f"[{who}] {kind}"


async def main(ticket_ids: list[int] | None) -> None:
    print(f"Model: {MODEL_NAME} (reasoning {REASONING_EFFORT})")
    queue: asyncio.Queue = asyncio.Queue()

    async def printer() -> None:
        while True:
            print(describe(await queue.get()), flush=True)

    printer_task = asyncio.create_task(printer())
    try:
        plan, events, run_id = await run_board(ticket_ids, queue=queue)
    finally:
        await asyncio.sleep(0)
        printer_task.cancel()

    path = save_run(run_id, ticket_ids, plan, events)
    print("\n=== BoardPlan ===")
    print(plan.model_dump_json(indent=2))
    print(f"\nSaved {path}")
    print(f"Audit trail: output/audit_trail.json (run_id {run_id})")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--ticket", type=int, action="append", help="ticket id to work (default: all open)")
    asyncio.run(main(parser.parse_args().ticket))
