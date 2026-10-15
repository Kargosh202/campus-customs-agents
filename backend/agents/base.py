"""What every agent shares: the ask_teammate delegation tool and make_agent().

Full connectivity: any agent can hand a task to any other agent. Two guards keep the agent loops
from running forever: an agent can't delegate to itself or to anyone already in the chain that
handed it the work (no A -> B -> A ping-pong), and chains stop at MAX_DELEGATION_DEPTH.
"""

from __future__ import annotations

from typing import Any

from pydantic_ai import Agent, RunContext
from pydantic_ai.toolsets import AbstractToolset

from agents.config import load_prompt
from models import AGENT_ROSTER, MAX_DELEGATION_DEPTH, AgentName, TeamDeps


async def ask_teammate(ctx: RunContext[TeamDeps], teammate: AgentName, task: str) -> dict[str, Any]:
    """Hand a task to another agent on the team and get back their report.

    Args:
        teammate: Who should do it: boss, inventory, accounting, facilities, or customer_service.
        task: A self-contained task. Include every id the teammate needs (ticket, SKU, size,
            quantity, lease, invoice) and what you want back.
    """
    deps = ctx.deps
    if teammate == deps.agent:
        return {"error": "You can't delegate to yourself. Do this part with your own tools."}
    if teammate in deps.chain:
        chain = " -> ".join(deps.chain)
        return {"error": f"{teammate} is already working on this ({chain}). Finish with what you have and list gaps as unknowns."}
    if deps.depth >= MAX_DELEGATION_DEPTH:
        return {"error": f"Delegation limit reached ({MAX_DELEGATION_DEPTH} hand-offs deep). Finish with what you have and list gaps as unknowns."}

    from agents.team import run_agent  # late import: team.py imports every agent, including this module's users

    deps.emit("delegated", to=teammate, task=task)
    report = await run_agent(teammate, task, deps.for_agent(teammate))
    deps.emit("delegation_returned", to=teammate, summary=report.summary)
    return report.model_dump(exclude_none=True)


def make_agent(
    name: AgentName,
    prompt_file: str,
    output_type: type,
    toolset: AbstractToolset[TeamDeps],
) -> Agent[TeamDeps, Any]:
    agent = Agent(
        output_type=output_type,
        deps_type=TeamDeps,
        name=name,
        instructions=load_prompt(prompt_file),
        tools=[ask_teammate],
        toolsets=[toolset],
        retries=2,
    )

    @agent.instructions
    def who_am_i(ctx: RunContext[TeamDeps]) -> str:
        title = AGENT_ROSTER[name]["title"]
        if ctx.deps.depth == 0:
            return f"You are {title}. This task comes straight from the shop's run, not from a teammate."
        handed_by = AGENT_ROSTER[ctx.deps.chain[-2]]["title"]
        return (
            f"You are {title}. {handed_by} handed you this task "
            f"(chain: {' -> '.join(ctx.deps.chain)}). Answer it and hand back your report."
        )

    return agent
