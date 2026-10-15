"""Model and MCP configuration shared by all five agents.

- Every agent runs on gpt-6-luna through Portkey, using PORTKEY_API_KEY from a .env file (this
  project's, or the AI Foundations root's). The model is fixed for this assignment; reasoning
  effort can be changed with REASONING_EFFORT (default high).
- MCP_TOOLSET is one stdio connection to mcp_server/server.py, shared by the whole team.
  mcp_tools(...) gives each agent only the MCP tools its role needs, and logs every call.
"""

from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from openai import AsyncOpenAI
from pydantic_ai import RunContext
from pydantic_ai.mcp import CallToolFunc, MCPToolset
from pydantic_ai.models.openai import OpenAIResponsesModel, OpenAIResponsesModelSettings
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai.toolsets import AbstractToolset

from models import TeamDeps

BACKEND_DIR = Path(__file__).resolve().parents[1]
HW_DIR = BACKEND_DIR.parent
PROMPTS_DIR = BACKEND_DIR / "prompts"
MCP_SERVER_PATH = HW_DIR / "mcp_server" / "server.py"

os.environ.setdefault("PYDANTIC_AI_NO_BANNER", "1")
for env_file in (HW_DIR / ".env", HW_DIR.parent / ".env"):  # this project's .env, then the course root .env
    load_dotenv(env_file)

MODEL_NAME = "gpt-6-luna"  # the only model used in HW 5
REASONING_EFFORT = os.getenv("REASONING_EFFORT", "high")
PORTKEY_BASE_URL = "https://api.portkey.ai/v1"


@lru_cache(maxsize=1)
def build_model() -> OpenAIResponsesModel:
    key = os.getenv("PORTKEY_API_KEY", "").strip()
    if not key:
        raise RuntimeError("PORTKEY_API_KEY is not set. Copy .env.example to .env and fill it in.")
    client = AsyncOpenAI(
        api_key=key,
        base_url=PORTKEY_BASE_URL,
        default_headers={"x-portkey-api-key": key, "x-portkey-provider": "openai"},
    )
    return OpenAIResponsesModel(MODEL_NAME, provider=OpenAIProvider(openai_client=client))


def model_settings() -> OpenAIResponsesModelSettings:
    return OpenAIResponsesModelSettings(openai_reasoning_effort=REASONING_EFFORT)


def load_prompt(agent_file: str) -> str:
    """Shared shop rules followed by the agent's own prompt."""
    rules = (PROMPTS_DIR / "shop_rules.md").read_text(encoding="utf-8")
    role = (PROMPTS_DIR / agent_file).read_text(encoding="utf-8")
    return f"{role}\n\n{rules}"


def _short(value: Any, limit: int = 600) -> str:
    text = value if isinstance(value, str) else json.dumps(value, default=str)
    return text if len(text) <= limit else text[:limit] + "…"


async def _log_tool_call(ctx: RunContext[TeamDeps], call_tool: CallToolFunc, name: str, args: dict[str, Any]):
    ctx.deps.emit("tool_called", tool=name, args=args)
    result = await call_tool(name, args)
    ctx.deps.emit("tool_result", tool=name, result=_short(result))
    return result


MCP_TOOLSET = MCPToolset(MCP_SERVER_PATH, id="campus-customs", process_tool_call=_log_tool_call)


# Only a person approving in the dashboard may call these. They are never given to an agent.
HUMAN_ONLY_TOOLS = {"pay_request", "reject_payment_request"}


def mcp_tools(*allowed: str) -> AbstractToolset[TeamDeps]:
    """The shared MCP connection, limited to the tools one role is allowed to call."""
    names = set(allowed)
    if names & HUMAN_ONLY_TOOLS:
        raise ValueError(f"Agents can't be given human-only tools: {sorted(names & HUMAN_ONLY_TOOLS)}")
    return MCP_TOOLSET.filtered(lambda ctx, tool_def: tool_def.name in names)
