"""MEM-d: the L2 driver for MULTI-SESSION runs (docs/LINE3_LOOM_MEMORY_DESIGN.md 5.2; owner 2026-10-13 「記憶の計器の前の決定」).

`driver.run_episode` runs ONE conversation that ends when the run closes.  The memory meter needs the other shape: a SESSION is a conversation in which messages arrive ONE BY ONE
(chat lines, minutes, ticket comments of a project), the model acts on each and ENDS EACH TURN with the same `report` tool, and the next session is a NEW conversation: nothing of
the old one is sent again.  Whatever survives a session boundary survives through the arm's tools only (the structure; the plain log; nothing for the context-only arm).

`run_story_session(client, door, ...)`:
  - the model's ONLY path to anything is a tool call on the door (`memdoor`); the driver forwards nothing else.  Every `text` block of every assistant turn is DROPPED from the
    output path (its sha256 and length become one `free_text_dropped` harness row of the door's ledger, exactly as in `driver.run_episode`); thinking blocks are counted, never stored.
  - a TURN = one delivered message (id "<session>-<message>", 1-based; the door is told with `set_turn`, so `report` carries it and the model never types it).  The tool calls of an
    assistant turn run in block order against `door.call`; the turn ENDS at the first ok `report` (the rest of that assistant turn is NOT executed: no row, no state; the API
    still needs a tool_result for every tool_use, so each skipped call gets the synthetic result `{"ok": false, "refusal": "skipped_after_report"}`, counted in
    `calls_skipped_after_report`).  A turn with no ok report after `max_calls` tool calls, or after NO_TOOL_LIMIT consecutive tool-less assistant turns, ENDS WITHOUT a report: the
    ledger then simply has none for it (what the model noticed is what its reports say, nothing is filled in).
  - the next message reaches the model in the same user message as the previous turn's tool results (the API wants results first), as one text block.
  - an API error ends the SESSION (`abandoned api_error`); the error text is returned and never enters a ledger.
The question phase is `driver.run_episode` itself over an answer door.  This module imports no SDK and no network module (test_loom_enforce reads the imports); the real client is the
harness's (`make_anthropic_client`), the tests' is `driver.ReplayClient`.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple

from verantyx.loom import driver as drv
from verantyx.loom.driver import NO_TOOL_LIMIT, _get, _sha

MAX_CALLS_PER_TURN = 12                 # the limit of the meter v1 (mem.v2): 23 + 14 structure turns ended here with no report
MAX_CALLS_PER_TURN_V3 = 24              # MEM-fix (L-MEM-62): the limit of the mem.v3 meter, the SAME for every arm
FORCE_ATTEMPTS = 2                      # MEM-fix (L-MEM-62): how many times the forced final `report` is asked for before the turn is recorded `report_missing`
FORCE_NOTE = ("This turn has run out of tool calls (or tool-less turns). Call report(contradictions, bugs) NOW to end it: the pairs of turn ids whose statements disagree, [] if none. "
              "It is the only tool you have left for this turn.")
SKIPPED = {"ok": False, "refusal": "skipped_after_report", "detail": {"reason": "the turn ended at your report; nothing after it ran"}}
STORY_REMINDER = ("Your last turn had no tool call. Text is discarded. Continue only by calling a tool; end the turn with report(contradictions, bugs).")


@dataclass
class StoryResult:
    ended: str = "?"                                   # complete | api_error
    turns: List[dict] = field(default_factory=list)    # [{"turn", "calls", "report", "ended": report | turn_limit | no_tool_call}]
    api_calls: int = 0
    tool_calls: int = 0
    calls_skipped_after_report: int = 0
    text_blocks_dropped: int = 0
    thinking_dropped: Dict[str, Any] = field(default_factory=lambda: {"n": 0, "chars": 0, "sha256": []})
    response_models: List[str] = field(default_factory=list)
    stop_reasons: List[str] = field(default_factory=list)
    error: Optional[str] = None
    tool_choice: Optional[dict] = None
    usage: Dict[str, int] = field(default_factory=lambda: {"calls": 0, "input_tokens": 0, "output_tokens": 0, "cache_read_input_tokens": 0, "cache_creation_input_tokens": 0})

    def to_obj(self) -> dict:
        return {k: getattr(self, k) for k in ("ended", "turns", "api_calls", "tool_calls", "calls_skipped_after_report", "text_blocks_dropped", "thinking_dropped", "response_models",
                                              "stop_reasons", "error", "tool_choice", "usage")}


def run_story_session(client: Any, door: Any, model: str, system: str, intro: str, messages: Sequence[Tuple[str, str]], tools: Sequence[dict], *,
                      tool_choice: Optional[dict] = None, max_calls: int = MAX_CALLS_PER_TURN, max_tokens: int = drv.MAX_TOKENS, extra: Optional[dict] = None,
                      force_report: bool = False) -> StoryResult:
    """Drive one story session.  `messages` = [(turn id "1-1", text shown to the model)], `intro` = the session's first words (the begin result), `tools` = the API tool dicts the door
    offers (memdoor.api_tools).  `door`: call / harness / set_turn / closed.

    `force_report` (MEM-fix, L-MEM-62; the mem.v3 meter, every arm): a turn that ends without an ok report of its own (`turn_limit`, `no_tool_call`) gets ONE more step: the harness row
    `report_forced` {turn, reason, calls}, then a request that offers ONLY the `report` tool (forced with tool_choice where the model accepts it) -- up to FORCE_ATTEMPTS tries.  An ok report
    ends the turn `report_forced` (t["forced"] = the reason); if none comes, the harness row `report_missing` is written and the turn ends `report_missing`.  The rule is the driver's and the
    same for all four arms; without it (the default) the turn ends as in the meter v1."""
    res = StoryResult()
    choice = tool_choice if tool_choice is not None else {"type": "any"}
    res.tool_choice = choice
    allowed = {t["name"] for t in tools}
    api: List[dict] = []
    pending: List[dict] = []                            # tool_result blocks owed for the last assistant turn
    ended_text_only = False

    def drop(text: str) -> None:
        res.text_blocks_dropped += 1
        door.harness(None, "free_text_dropped", {"sha256": _sha(text), "chars": len(text)})

    def absorb(resp: Any) -> Tuple[List[Any], List[Any]]:
        """The accounting of one API response (usage, model, stop reason, thinking dropped, text dropped) -> (content blocks, tool_use blocks)."""
        res.api_calls += 1
        res.usage["calls"] += 1
        us = _get(resp, "usage")
        for key in ("input_tokens", "output_tokens", "cache_read_input_tokens", "cache_creation_input_tokens"):
            v = _get(us, key) if us is not None else None
            if isinstance(v, int) and not isinstance(v, bool):
                res.usage[key] += v
        content = list(_get(resp, "content", []) or [])
        res.stop_reasons.append(str(_get(resp, "stop_reason", "")))
        rm = _get(resp, "model")
        if rm and rm not in res.response_models:
            res.response_models.append(rm)
        for b in content:
            if _get(b, "type") in ("thinking", "redacted_thinking"):
                body = _get(b, "thinking") if _get(b, "type") == "thinking" else _get(b, "data")
                body = body if isinstance(body, str) else ""
                td = res.thinking_dropped
                td["n"] += 1
                td["chars"] += len(body)
                td["sha256"].append(_sha(body))
        for tx in [_get(b, "text", "") or "" for b in content if _get(b, "type") == "text"]:
            drop(tx)
        return content, [b for b in content if _get(b, "type") == "tool_use"]

    def api_error(e: Exception, t: dict) -> StoryResult:
        res.ended, res.error = "api_error", "%s: %s" % (type(e).__name__, str(e)[:300])
        if door.closed(None) is None:
            door.harness(None, "abandoned", {"reason": "api_error"})
        t["ended"] = "api_error"
        return res

    report_tools = [x for x in tools if x["name"] == "report"]
    force_choice = {"type": "tool", "name": "report"} if drv.forced_choice_accepted(model) else {"type": "auto"}

    def force(t: dict, reason: str, owed: List[dict]) -> Optional[StoryResult]:
        """The forced final report of a turn that ended without one (see `run_story_session`).  `owed` = the tool_results the last assistant turn is owed.  Returns the result on an API error,
        else None; sets t["report"] / t["ended"] / t["forced"] and (via the closure) `pending` / `ended_text_only` for the next message."""
        nonlocal pending, ended_text_only
        door.harness(None, "report_forced", {"turn": t["turn"], "reason": reason, "calls": t["calls"]})
        t["forced"] = reason
        owed = list(owed)
        note: Any = FORCE_NOTE
        for attempt in range(FORCE_ATTEMPTS):
            if not report_tools:
                break
            api.append({"role": "user", "content": (owed + [{"type": "text", "text": note}]) if owed else note})
            kw = dict(model=model, max_tokens=max_tokens, system=system, tools=list(report_tools), tool_choice=force_choice, messages=list(api))
            if extra:
                kw.update(extra)
            try:
                resp = client.messages.create(**kw)
            except Exception as e:                                           # noqa: BLE001
                return api_error(e, t)
            content, uses = absorb(resp)
            api.append({"role": "assistant", "content": content})
            owed = []
            ok = False
            for tu in uses:
                if ok:                                                         # a call after the ok report of this step: skipped, as in the turn itself
                    res.calls_skipped_after_report += 1
                    owed.append({"type": "tool_result", "tool_use_id": _get(tu, "id"), "content": json.dumps(SKIPPED, sort_keys=True)})
                    continue
                if _get(tu, "name") != "report":                               # only `report` was offered: anything else is not a tool of this step
                    nm = _get(tu, "name")
                    owed.append({"type": "tool_result", "tool_use_id": _get(tu, "id"),
                                 "content": json.dumps({"ok": False, "refusal": "unknown_tool", "detail": {"tool": nm if isinstance(nm, str) else None}}, ensure_ascii=False, sort_keys=True)})
                    continue
                inp = _get(tu, "input")
                args = dict(inp) if isinstance(inp, dict) else {}
                args["run_id"] = "-"
                out = door.call("report", args)
                res.tool_calls += 1
                t["calls"] += 1
                owed.append({"type": "tool_result", "tool_use_id": _get(tu, "id"), "content": json.dumps(out, ensure_ascii=False, sort_keys=True)})
                if out.get("ok") is True:
                    ok = True
                    t["report"], t["ended"] = {"contradictions": out["contradictions"], "bugs": out["bugs"]}, "report_forced"
            if ok:
                pending, ended_text_only = owed, False
                return None
            note = FORCE_NOTE
            if not uses:
                owed = []
        door.harness(None, "report_missing", {"turn": t["turn"], "reason": reason, "calls": t["calls"]})
        t["ended"] = "report_missing"
        pending, ended_text_only = owed, not owed
        return None

    for k, (turn_id, text) in enumerate(messages):
        door.set_turn(turn_id)
        shown = (intro + "\n\n" if k == 0 else "") + text
        if k == 0 or ended_text_only or not pending:
            api.append({"role": "user", "content": shown})
        else:
            api.append({"role": "user", "content": pending + [{"type": "text", "text": shown}]})
        pending, ended_text_only = [], False
        t = {"turn": turn_id, "calls": 0, "report": None, "ended": "?"}
        res.turns.append(t)
        tool_less = 0
        while True:
            kw = dict(model=model, max_tokens=max_tokens, system=system, tools=list(tools), tool_choice=choice, messages=list(api))
            if extra:
                kw.update(extra)
            try:
                resp = client.messages.create(**kw)
            except Exception as e:                                           # noqa: BLE001  the driver must always leave a closed ledger
                return api_error(e, t)
            content, uses = absorb(resp)
            api.append({"role": "assistant", "content": content})             # the API's own blocks, unchanged (L-LOOM-16)
            if not uses:
                tool_less += 1
                if tool_less >= NO_TOOL_LIMIT:
                    t["ended"], ended_text_only = "no_tool_call", True
                    break
                api.append({"role": "user", "content": STORY_REMINDER})
                continue
            tool_less = 0
            results: List[dict] = []
            reported = False
            for tu in uses:
                if reported:
                    res.calls_skipped_after_report += 1
                    results.append({"type": "tool_result", "tool_use_id": _get(tu, "id"), "content": json.dumps(SKIPPED, sort_keys=True)})
                    continue
                name, inp = _get(tu, "name"), _get(tu, "input")
                args = dict(inp) if isinstance(inp, dict) else {}
                args["run_id"] = "-"                                          # the door pops it: the model cannot address another run
                if name in allowed:
                    out = door.call(name, args)
                else:                                                          # not offered to the model: refused, no row, no state
                    out = {"ok": False, "refusal": "unknown_tool", "detail": {"tool": name if isinstance(name, str) else None}}
                res.tool_calls += 1
                t["calls"] += 1
                results.append({"type": "tool_result", "tool_use_id": _get(tu, "id"), "content": json.dumps(out, ensure_ascii=False, sort_keys=True)})
                if name == "report" and out.get("ok") is True:
                    reported = True
                    t["report"], t["ended"] = {"contradictions": out["contradictions"], "bugs": out["bugs"]}, "report"
            pending = results
            if reported:
                break
            if t["calls"] >= max_calls:
                t["ended"] = "turn_limit"
                break
            api.append({"role": "user", "content": results})
            pending = []
        if force_report and t["report"] is None and t["ended"] in ("turn_limit", "no_tool_call"):
            err = force(t, t["ended"], pending if t["ended"] == "turn_limit" else [])
            if err is not None:
                return err
    res.ended = "complete"
    return res
