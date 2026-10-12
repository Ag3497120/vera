"""LOOM-f: the L2 API driver (docs/LINE3_LOOM_DESIGN.md 7.1 L2, 7.2, 7.3, 9.3).  A manual tool-use loop in which the model's ONLY path to
anything is a tool call on the loom.

WHAT THE DRIVER FORWARDS.  Its `tools` are the loom tools (the 19 after `begin`; the harness has begun the run) plus `done` and nothing else.
Every `tool_use` block of an assistant turn is executed in block order against `LoomServer.call` (one ledger row each) with the driver's own
`run_id` (a `run_id` the model passes is overwritten: it cannot reach another run), and all results go back in ONE user message.  Every `text`
block of every assistant turn is DROPPED from the output path: its sha256 and length become one `free_text_dropped` row, and the text is
never scored, shown or returned by this module.  The assistant turn is kept in the API history exactly as the API produced it (L-LOOM-16:
the API requires it), but nothing the model wrote as text is ever sent anywhere else.  The driver passes on nothing but tool calls.

THE RUN CLOSES, THE TURN STOPS (L-LOOM-62).  Tool calls of one assistant turn run in block order; as soon as one of them closes the run (a successful
`emit` / `abstain`) the remaining blocks of that turn are NOT executed (no row, no state; counted in `calls_skipped_after_close`) and the episode ends
`closed`.  The alternative (run them, refuse each as `run_closed`, and keep those refusals out of the model's refusal count) was not chosen: a stopped
turn leaves a ledger that ends at the close, and no `run_closed` refusal from the driver's own batching can be mistaken for the model's.

THE EPISODE ENDS on a successful `emit` / `abstain` (the run is closed), on `done` (if the run is still open the harness row `abandoned`
`done_without_close` is appended), on `max_turns` (`abandoned` `max_turns`), after `NO_TOOL_LIMIT` consecutive turns without a tool call
(`abandoned` `no_tool_call`, the text of those turns dropped), or on an API error (`abandoned` `api_error`; the error text is returned to the
harness and never enters the ledger).

`tool_choice` (design 7.3).  Models that accept it get `{"type": "any"}`: every turn is a tool call and `done` ends the episode.  Models that
reject forced tool use with a 400 (EXACTLY the ids in `FORCED_REJECTED`, L-LOOM-63) get `{"type": "auto"}` with `strict: true` on every
tool.  THE GUARANTEE DOES NOT DEPEND ON THIS: the driver forwards only tool calls, `tool_choice` only removes wasted turns.

CONTROL (`control=True`, design 9.3 / 10.1): the one place where free text is the answer.  The tools are the read-only lookups only (no
state-changing op, no emit, no done), `tool_choice` is `auto`, the text blocks of a turn that also carries tool calls are dropped like any
other, and the text of the final tool-less turn is returned as `control_text` (the harness stores it as `free_text_control`).

This module imports no SDK and no network module (the confined package imports none; test_loom_enforce reads the imports).  The real client is
made by the harness (`experiments/line3/loom/harness.py: make_anthropic_client`, `anthropic` imported there, not here).  `ReplayClient` is the
fake client of the tests: it replays a recorded script of turns and checks what the driver sends.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from types import SimpleNamespace
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

# L-LOOM-127 (LOOM-batch): prose 60 -> 160.  With the prose lookup cap at 100, 60 turns would end a run before its lookups did (the first
# measurement's I2-025 record_only ended at exactly 60).  A turn may carry several calls; the caps, not this, are what bounds a run.
MAX_TURNS = {"prose": 160, "code": 200}
NO_TOOL_LIMIT = 3
MAX_TOKENS = 4096
REMINDER = ("Your last turn had no tool call. Text is discarded. Continue only by calling a tool: build the structure and call emit, "
            "call abstain, or call done when you are finished.")
CONTROL_REMINDER = "Answer in one line, or answer 不明."

# EXACT model ids that reject forced tool use (`tool_choice` any / tool) with a 400 (docs/LINE3_LOOM_DESIGN.md 7.3; the Claude API reference): Claude Opus 5.5,
# Claude Sonnet 5.5, Claude Fable 5.1 and (same API surface, Project Glasswing only) Claude Mythos 5.1.  NOT `claude-fable-5` / `claude-mythos-5` / `claude-opus-5`
# and not any prefix or substring: the id must equal one of these (the API ids carry no date suffix).
FORCED_REJECTED = ("claude-opus-5-5", "claude-sonnet-5-5", "claude-fable-5-1", "claude-mythos-5-1")

DONE_TOOL = {"name": "done",
             "description": "Call when you have finished: after emit or abstain succeeded, or when you give up. Ends the episode. Takes no arguments.",
             "input_schema": {"type": "object", "properties": {}, "additionalProperties": False}}

CONTROL_TOOLS = ("lookup", "read_sentence")


def forced_choice_accepted(model: str) -> bool:
    return (model or "").strip().lower() not in FORCED_REJECTED


def tool_choice_for(model: str) -> Tuple[dict, bool]:
    """(tool_choice, strict) by model family: `any` where it is accepted, else `auto` + strict tools."""
    if forced_choice_accepted(model):
        return {"type": "any"}, False
    return {"type": "auto"}, True


def api_tools(mcp_tools: Iterable[Any], strict: bool = False, control: bool = False) -> List[dict]:
    """The `tools` array of the Messages API from the FastMCP tool objects (`name`, `description`, `inputSchema`) of the SAME server object the
    loom runs on, so the model sees exactly the schemas of the MCP door, minus `begin` (the harness began the run) and minus `run_id` (the
    driver supplies it).  Plus `done`, except for a control (only the read-only lookups)."""
    out: List[dict] = []
    for t in mcp_tools:
        if t.name == "begin" or (control and t.name not in CONTROL_TOOLS):
            continue
        schema = json.loads(json.dumps(t.inputSchema))
        schema.get("properties", {}).pop("run_id", None)
        if "required" in schema:
            schema["required"] = [k for k in schema["required"] if k != "run_id"]
            if not schema["required"]:
                del schema["required"]
        schema["additionalProperties"] = False
        d = {"name": t.name, "description": t.description, "input_schema": schema}
        if strict:
            d["strict"] = True
        out.append(d)
    if not control:
        d = json.loads(json.dumps(DONE_TOOL))
        if strict:
            d["strict"] = True
        out.append(d)
    return out


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _get(b: Any, k: str, default: Any = None) -> Any:
    return b.get(k, default) if isinstance(b, dict) else getattr(b, k, default)


@dataclass
class DriverResult:
    ended: str = "?"                                  # closed | done | max_turns | no_tool_call | api_error | control_answer
    turns: int = 0
    tool_calls: int = 0
    text_blocks_dropped: int = 0
    thinking_dropped: Dict[str, Any] = field(default_factory=lambda: {"n": 0, "chars": 0, "sha256": []})   # thinking blocks: hash + length only, never a ledger row
    calls_skipped_after_close: int = 0
    tool_less_turns: int = 0
    response_models: List[str] = field(default_factory=list)
    stop_reasons: List[str] = field(default_factory=list)
    control_text: Optional[str] = None
    error: Optional[str] = None
    tool_choice: Optional[dict] = None
    usage: Dict[str, int] = field(default_factory=lambda: {"calls": 0, "input_tokens": 0, "output_tokens": 0,
                                                            "cache_read_input_tokens": 0, "cache_creation_input_tokens": 0})   # what the API reports; testimony

    def to_obj(self) -> dict:
        return {k: getattr(self, k) for k in ("ended", "turns", "tool_calls", "text_blocks_dropped", "thinking_dropped", "calls_skipped_after_close",
                                              "tool_less_turns", "response_models",
                                              "stop_reasons", "error", "tool_choice", "usage")} | {"control_text_chars": None if self.control_text is None else len(self.control_text)}


def first_message(begin_result: dict) -> str:
    """The first user turn: the `begin` result (task text, mode, caps, rules) as JSON.  No gold is anywhere in it."""
    return ("The run has been begun for you; the run id is supplied by the system, never pass it. This is the result of begin:\n"
            + json.dumps({k: begin_result[k] for k in ("task", "rules") if k in begin_result}, ensure_ascii=False, sort_keys=True))


def run_episode(client: Any, server: Any, run_id: str, model: str, system: str, user_message: str, tools: Sequence[dict], *,
                tool_choice: Optional[dict] = None, max_turns: int = MAX_TURNS["prose"], max_tokens: int = MAX_TOKENS, control: bool = False,
                extra: Optional[dict] = None) -> DriverResult:
    """Drive one episode.  `client.messages.create(**kwargs)` returns an object (or dict) with `content` (blocks of type text / tool_use / ...),
    `stop_reason`, `model`.  `server` is a LoomServer: `call`, `harness`, `closed`."""
    res = DriverResult()
    choice = tool_choice if tool_choice is not None else ({"type": "auto"} if control else {"type": "any"})
    if control:
        choice = {"type": "auto"}
    res.tool_choice = choice
    messages: List[dict] = [{"role": "user", "content": user_message}]
    allowed = {t["name"] for t in tools}

    def drop(text: str) -> None:
        res.text_blocks_dropped += 1
        server.harness(run_id, "free_text_dropped", {"sha256": _sha(text), "chars": len(text)})

    def drop_thinking(b: Any) -> None:
        body = _get(b, "thinking") if _get(b, "type") == "thinking" else _get(b, "data")
        body = body if isinstance(body, str) else ""
        td = res.thinking_dropped
        td["n"] += 1
        td["chars"] += len(body)
        td["sha256"].append(_sha(body))

    def abandon(reason: str) -> None:
        if server.closed(run_id) is None:
            server.harness(run_id, "abandoned", {"reason": reason})

    for _ in range(max_turns):
        kw = dict(model=model, max_tokens=max_tokens, system=system, tools=list(tools), tool_choice=choice, messages=list(messages))
        if extra:
            kw.update(extra)
        try:
            resp = client.messages.create(**kw)
        except Exception as e:                                                # noqa: BLE001  the driver must always leave a closed ledger
            res.ended, res.error = "api_error", "%s: %s" % (type(e).__name__, str(e)[:300])
            abandon("api_error")
            return res
        res.turns += 1
        res.usage["calls"] += 1
        us = _get(resp, "usage")
        for k in ("input_tokens", "output_tokens", "cache_read_input_tokens", "cache_creation_input_tokens"):
            v = _get(us, k) if us is not None else None
            if isinstance(v, int) and not isinstance(v, bool):
                res.usage[k] += v
        content = list(_get(resp, "content", []) or [])
        res.stop_reasons.append(str(_get(resp, "stop_reason", "")))
        rm = _get(resp, "model")
        if rm and rm not in res.response_models:
            res.response_models.append(rm)
        uses = [b for b in content if _get(b, "type") == "tool_use"]
        texts = [_get(b, "text", "") or "" for b in content if _get(b, "type") == "text"]
        for b in content:
            if _get(b, "type") in ("thinking", "redacted_thinking"):                 # counted apart from the text blocks; the assistant turn is kept as the API sent it
                drop_thinking(b)
        if not (control and not uses):                                           # a control's final answer is its output; every other text is dropped
            for tx in texts:
                drop(tx)
        messages.append({"role": "assistant", "content": content})             # the API's own blocks, unchanged (L-LOOM-16)
        if control and not uses:
            res.ended, res.control_text = "control_answer", "\n".join(texts)
            return res
        if not uses:
            res.tool_less_turns += 1
            if res.tool_less_turns >= NO_TOOL_LIMIT:
                res.ended = "no_tool_call"
                abandon("no_tool_call")
                return res
            messages.append({"role": "user", "content": CONTROL_REMINDER if control else REMINDER})
            continue
        res.tool_less_turns = 0
        results: List[dict] = []
        finished = False
        for k, tu in enumerate(uses):
            if k and server.closed(run_id) is not None:                           # the run closed earlier in this turn: stop (L-LOOM-62)
                res.calls_skipped_after_close += len(uses) - k
                break
            name = _get(tu, "name")
            inp = _get(tu, "input")
            if name == "done" and not control:
                res.tool_calls += 1
                results.append({"type": "tool_result", "tool_use_id": _get(tu, "id"), "content": json.dumps({"ok": True})})
                was_closed = server.closed(run_id) is not None
                abandon("done_without_close")
                res.ended = "closed" if was_closed else "done"
                finished = True
                break
            args = dict(inp) if isinstance(inp, dict) else {}
            args["run_id"] = run_id                                              # the model cannot address another run
            if name in allowed:
                out = server.call(name, args)
            else:                                                                # not offered to the model: refused, no row, no state
                out = {"ok": False, "refusal": "unknown_tool", "detail": {"tool": name if isinstance(name, str) else None}}
            res.tool_calls += 1
            results.append({"type": "tool_result", "tool_use_id": _get(tu, "id"), "content": json.dumps(out, ensure_ascii=False, sort_keys=True)})
        if finished:
            return res
        messages.append({"role": "user", "content": results})
        if server.closed(run_id) is not None:
            res.ended = "closed"
            return res
    res.ended = "max_turns"
    abandon("max_turns")
    return res


# ------------------------------------------------------------------------------------------------------------
# the fake client of the tests
# ------------------------------------------------------------------------------------------------------------
class ReplayClient:
    """`client.messages.create(**kw)` that replays a recorded script.  A script is a list of turns; a turn is a list of blocks:
    ("text", str), ("thinking", str), ("redacted_thinking", str) or ("tool", name, input_dict).  It records every request in `.calls`, refuses (AssertionError) a request that offers a tool
    outside `allowed_tools` or ends with the script exhausted, and returns the blocks as objects with `type`, `text`, `id`, `name`, `input`
    like the SDK's.  `stop_reason` is `tool_use` if the turn has a tool call, else `end_turn`."""

    def __init__(self, script: Sequence[Sequence[tuple]], allowed_tools: Optional[Iterable[str]] = None, model: str = "fake-model") -> None:
        self.script = [list(t) for t in script]
        self.allowed = None if allowed_tools is None else set(allowed_tools)
        self.model = model
        self.calls: List[dict] = []
        self.messages = SimpleNamespace(create=self._create)
        self._n = 0

    def _create(self, **kw: Any) -> Any:
        self.calls.append(json.loads(json.dumps({k: v for k, v in kw.items() if k != "messages"}, default=str)))
        self.calls[-1]["n_messages"] = len(kw["messages"])
        if self.allowed is not None:
            offered = {t["name"] for t in kw["tools"]}
            assert offered <= self.allowed, "the driver offered tools outside the loom: %s" % sorted(offered - self.allowed)
        assert self._n < len(self.script), "the recorded script is exhausted"
        turn = self.script[self._n]
        self._n += 1
        blocks = []
        for b in turn:
            if b[0] == "text":
                blocks.append(SimpleNamespace(type="text", text=b[1]))
            elif b[0] == "thinking":
                blocks.append(SimpleNamespace(type="thinking", thinking=b[1], signature="sig"))
            elif b[0] == "redacted_thinking":
                blocks.append(SimpleNamespace(type="redacted_thinking", data=b[1]))
            elif b[0] == "tool":
                blocks.append(SimpleNamespace(type="tool_use", id="toolu_%d_%d" % (self._n, len(blocks)), name=b[1], input=dict(b[2])))
            else:
                blocks.append(SimpleNamespace(type=b[0]))
        stop = "tool_use" if any(b.type == "tool_use" for b in blocks) else "end_turn"
        return SimpleNamespace(content=blocks, stop_reason=stop, model=self.model)
