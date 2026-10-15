"""Append-only audit trail of agent-loop activity: output/audit_trail.json.

One AuditEntry (models.py) per agent-loop step, written as soon as the step finishes: the run id,
which agent, how the work reached it (the delegation chain), its task, the model's tool calls with
short arguments and results, any text, the stop reason, whether it ended the agent's run, tokens,
and any error. Entries are only ever added, never removed or rewritten.
"""

from __future__ import annotations

import json
import re
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import BaseModel
from pydantic_ai.messages import ModelRequest, ModelResponse, RetryPromptPart, TextPart, ToolCallPart, ToolReturnPart

from models import AuditEntry, AuditToolCall, TeamDeps

AUDIT_PATH = Path(__file__).resolve().parents[1] / "output" / "audit_trail.json"
MAX_TEXT = 300  # characters kept from any argument, result, or message

_lock = threading.Lock()
_EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")


def shorten(value: Any, limit: int = MAX_TEXT) -> str:
    if isinstance(value, BaseModel):
        text = value.model_dump_json()
    elif isinstance(value, (dict, list)):
        text = json.dumps(value, default=str, ensure_ascii=False)
    else:
        text = str(value)
    text = _EMAIL.sub("[email]", " ".join(text.split()))
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _short_args(args: dict[str, Any] | str | None) -> dict[str, Any] | str:
    if isinstance(args, dict):
        return {k: (shorten(v, 200) if isinstance(v, (str, dict, list)) else v) for k, v in args.items()}
    return shorten(args or "", 200)


def append(entry: AuditEntry) -> None:
    """Add one entry to the end of output/audit_trail.json, keeping every earlier entry."""
    with _lock:
        existing = json.loads(AUDIT_PATH.read_text(encoding="utf-8")) if AUDIT_PATH.exists() else []
        existing.append(entry.model_dump(mode="json"))
        AUDIT_PATH.parent.mkdir(parents=True, exist_ok=True)
        tmp = AUDIT_PATH.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(existing, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        tmp.replace(AUDIT_PATH)  # atomic swap: a crash mid-write never loses earlier entries


class StepRecorder:
    """Builds one AuditEntry per agent-loop step from the nodes of agent.iter()."""

    def __init__(self, deps: TeamDeps, task: str, model: str, reasoning_effort: str):
        self.deps, self.task, self.model, self.effort = deps, shorten(task), model, reasoning_effort
        self.step = 0
        self.pending: AuditEntry | None = None
        self.call_ids: list[str] = []  # tool_call_ids of the pending step, same order as its tool_calls

    def model_responded(self, response: ModelResponse) -> None:
        """The model answered: record its tool calls. Their results arrive with the next request."""
        self.flush()
        self.step += 1
        self.call_ids = [p.tool_call_id for p in response.parts if isinstance(p, ToolCallPart)]
        texts = [p.content for p in response.parts if isinstance(p, TextPart) and p.content.strip()]
        self.pending = AuditEntry(
            timestamp=datetime.now(timezone.utc).isoformat(timespec="seconds"),
            run_id=self.deps.run_id,
            agent=self.deps.agent,
            chain=list(self.deps.chain),
            task=self.task,
            step=self.step,
            model=response.model_name or self.model,
            reasoning_effort=self.effort,
            text=shorten(" ".join(texts)) if texts else None,
            tool_calls=[
                AuditToolCall(tool_name=p.tool_name, args=_short_args(p.args_as_dict()), result=None)
                for p in response.parts
                if isinstance(p, ToolCallPart)
            ],
            stop_reason=response.finish_reason,
            input_tokens=response.usage.input_tokens or 0,
            output_tokens=response.usage.output_tokens or 0,
        )

    def tools_returned(self, request: ModelRequest) -> None:
        """The tool results for the pending step came back: attach them and write the step."""
        if self.pending is None:
            return
        results: dict[str, str] = {}
        for part in request.parts:
            if isinstance(part, ToolReturnPart):
                results[part.tool_call_id] = shorten(part.content)
            elif isinstance(part, RetryPromptPart) and part.tool_call_id:
                results[part.tool_call_id] = "RETRY: " + shorten(part.content)
        for record, call_id in zip(self.pending.tool_calls, self.call_ids):
            record.result = results.get(call_id)
        self.flush()

    def finished(self, output: Any) -> None:
        if self.pending is not None:
            self.pending.ended_run = True
            for record in self.pending.tool_calls:
                record.result = record.result or "final output: " + shorten(output)
        self.flush()

    def failed(self, error: BaseException) -> None:
        if self.pending is None:
            self.step += 1
            self.pending = AuditEntry(
                timestamp=datetime.now(timezone.utc).isoformat(timespec="seconds"),
                run_id=self.deps.run_id,
                agent=self.deps.agent,
                chain=list(self.deps.chain),
                task=self.task,
                step=self.step,
                model=self.model,
                reasoning_effort=self.effort,
            )
        self.pending.ended_run = True
        self.pending.error = shorten(f"{type(error).__name__}: {error}")
        self.flush()

    def flush(self) -> None:
        if self.pending is not None:
            append(self.pending)
            self.pending = None
