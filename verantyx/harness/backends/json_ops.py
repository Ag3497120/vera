"""The JSON-ops backend: for a model that has no tool calling (a small local model, a plain completion endpoint).

The model is told the tools in the system prompt and must answer with ONE JSON array of ops:

    [{"tool": "lookup", "input": {"text": "松風庵", "tier": "any"}}, {"tool": "read_sentence", "input": {"sid": 1}}]

The harness executes only VALID ops, in order: an object with exactly the keys `tool` (the name of an offered tool) and `input` (a JSON object).  Everything else is
DROPPED and RECORDED: an invalid element of the array, an array that is not an array (prose, a bare object, broken JSON), text around the array.  A dropped part becomes a
`text` block of the turn, which the driver hashes into a `free_text_dropped` row exactly like the free text of any other backend; it is never executed and never shown.
Nothing else changes: the ops go through the same loom / memory server, one ledger row each, and the user sees only a successful `emit` or a typed abstention.

The only leniency: one fenced block (```json ... ```) that is the WHOLE reply is unwrapped, and a leading <think>...</think> is taken as reasoning (hash + length only).

The transport is an OpenAI-compatible chat endpoint with NO tools in the request (`--backend json --base-url ...`), or any object with `.send_chat(system, messages, max_tokens)`.
"""
from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional, Sequence, Tuple

from verantyx.harness.backends.base import Turn, get, jdump, text_block, thinking_block, tool_block
from verantyx.harness.backends.openai_compat import OpenAICompatBackend, _usage

MAX_OPS_PER_TURN = 32
_FENCE = re.compile(r"\A```[A-Za-z0-9_-]*\s*\n(.*?)\n?```\Z", re.S)
_THINK = re.compile(r"\A\s*<think>(.*?)</think>\s*", re.S)

INSTRUCTIONS = """You cannot call tools directly. You act ONLY by replying with ONE JSON array of ops and nothing else (no prose, no markdown around it):

[{"tool": "<tool name>", "input": {<arguments of the tool>}}, ...]

The ops are executed in order. After they have run you receive their results and reply again with the next array. Anything that is not such an array, and any element that is not
exactly {"tool": ..., "input": ...} with an offered tool and an object `input`, is discarded unread (only its hash is kept). Never pass `run_id`. Reply with `[]` only if you have nothing to do.

The tools (name: description; input = JSON schema of the arguments):
"""


def catalog(tools: Sequence[dict]) -> str:
    lines = []
    for t in tools:
        schema = t.get("input_schema") or {"type": "object", "properties": {}}
        lines.append("- %s: %s\n  input: %s" % (t["name"], " ".join((t.get("description") or "").split()), json.dumps(schema, ensure_ascii=False, sort_keys=True, separators=(",", ":"))))
    return "\n".join(lines)


def parse_ops(text: str, allowed: Sequence[str]) -> Tuple[List[Tuple[str, dict]], List[str], List[str]]:
    """(valid ops [(tool, input)], dropped parts [str], reasoning [str]).  The dropped parts are the text of whatever was not a valid op, as written (or its JSON form)."""
    reasoning: List[str] = []
    s = text or ""
    m = _THINK.match(s)
    if m:
        reasoning.append(m.group(1))
        s = s[m.end():]
    s = s.strip()
    if not s:
        return [], [], reasoning
    fm = _FENCE.match(s)
    body = fm.group(1).strip() if fm else s
    try:
        arr = json.loads(body)
    except ValueError:
        return [], [s], reasoning
    if not isinstance(arr, list):
        return [], [s], reasoning
    ops: List[Tuple[str, dict]] = []
    dropped: List[str] = []
    allowed_set = set(allowed)
    for el in arr:
        if (isinstance(el, dict) and set(el) == {"tool", "input"} and isinstance(el["tool"], str) and el["tool"] in allowed_set and isinstance(el["input"], dict)
                and len(ops) < MAX_OPS_PER_TURN):
            ops.append((el["tool"], el["input"]))
        else:
            dropped.append(jdump(el))
    return ops, dropped, reasoning


def to_chat_messages(system: str, messages: Sequence[dict]) -> List[dict]:
    """The driver's history as plain chat: assistant turns are the JSON arrays of their valid ops; tool results come back as one user message."""
    out: List[dict] = [{"role": "system", "content": system}]
    names: Dict[str, str] = {}
    for m in messages:
        role, content = m["role"], m["content"]
        if role == "user" and isinstance(content, str):
            out.append({"role": "user", "content": content})
        elif role == "user":
            res = []
            for b in content:
                if get(b, "type") == "tool_result":
                    c = get(b, "content")
                    try:
                        c = json.loads(c) if isinstance(c, str) else c
                    except ValueError:
                        pass
                    res.append({"tool": names.get(get(b, "tool_use_id")), "result": c})
            out.append({"role": "user", "content": "Results of your ops, in order:\n" + jdump(res) + "\nReply with the next JSON array of ops."})
        else:
            ops = []
            if not isinstance(content, str):
                for b in content:
                    if get(b, "type") == "tool_use":
                        names[get(b, "id")] = get(b, "name")
                        ops.append({"tool": get(b, "name"), "input": get(b, "input") or {}})
            out.append({"role": "assistant", "content": jdump(ops)})
    return out


class JsonOpsBackend:
    name = "json"

    def __init__(self, model: str, base_url: Optional[str] = None, transport: Any = None, *, client: Any = None, api_key_env: Optional[str] = None,
                 max_tokens_param: str = "max_tokens", temperature: Optional[float] = None) -> None:
        self.model = model
        self.base_url = base_url
        self._t = transport or OpenAICompatBackend(model, base_url, client, api_key_env=api_key_env, max_tokens_param=max_tokens_param, temperature=temperature)
        self._n = 0
        self.dropped_parts = 0
        self.last_response_model: Optional[str] = None

    def ready(self) -> None:
        if hasattr(self._t, "ready"):
            self._t.ready()

    def tool_choice(self) -> Tuple[dict, bool]:
        return {"type": "any"}, False                                  # every turn is an array of ops; there is no server-side forcing

    def _chat(self, system: str, messages: Sequence[dict], max_tokens: int, extra: Optional[dict]) -> Tuple[str, Dict[str, int], Optional[str], str]:
        if hasattr(self._t, "send_chat"):
            return self._t.send_chat(system, messages, max_tokens)
        kw = self._t.request(system, [], [], max_tokens, None, extra)
        kw["messages"] = messages
        resp = self._t.client().chat.completions.create(**kw)
        choices = get(resp, "choices") or []
        msg = get(choices[0], "message") if choices else None
        text = get(msg, "content") if msg is not None else ""
        return (text if isinstance(text, str) else ""), _usage(get(resp, "usage")), get(resp, "model"), str(get(choices[0], "finish_reason") or "") if choices else "no_choices"

    def send(self, *, system: str, messages: Sequence[dict], tools: Sequence[dict], max_tokens: int, tool_choice: Optional[dict] = None,
             extra: Optional[dict] = None) -> Turn:
        full = system + "\n\n" + INSTRUCTIONS + catalog(tools)
        text, usage, model, finish = self._chat(full, to_chat_messages(full, messages), max_tokens, extra)
        self.last_response_model = model
        ops, dropped, reasoning = parse_ops(text, [t["name"] for t in tools])
        self._n += 1
        content: List[Any] = [thinking_block(r) for r in reasoning]
        for k, (name, inp) in enumerate(ops):
            content.append(tool_block("op_%d_%d" % (self._n, k), name, inp))
        for d in dropped:
            content.append(text_block(d))
        self.dropped_parts += len(dropped)
        return Turn(content=content, usage=usage, model=model, stop_reason="tool_use" if ops else (finish or "end_turn"))

    def describe(self) -> dict:
        d = {"backend": self.name, "model": self.model, "mode": "json_ops"}
        if self.base_url:
            d["base_url"] = self.base_url
        return d
