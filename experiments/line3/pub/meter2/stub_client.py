"""PUB-M10: the DETERMINISTIC STUB CLIENT of the long-story meter (instrument v2).  Not a model: a fixed policy that exercises the harness path (doors, driver, caps, budget, commit, snapshot, answer runs, scoring)
without any API or network.  `client.messages.create(**kw)` has the shape the drivers expect (blocks of type tool_use with id / name / input, `usage`, `stop_reason`, `model`).

THE POLICY (a pure function of the request; no state, no clock, no random):
  story phase   A0: report([]).   A1: one log_append per sentence ("<turn> <sentence>", at most 64 characters), then report([]).
                A3 / A3f: declare_topic on the first message of a session, then one write (keep_unshaped for a sentence the shape exchanger gives an F0 clause) per sentence, then
                report(pairs): the pairs the structure's own notes named in this turn's results (`! SAME_SEAT ... turns=a,b,c` / `! REVERSAL_X ...`: [a, current], [b, current], ...), i.e. the stub copies the
                structure's notes into its report.  So `model reports` of a stub run are "the notes, relayed", and the scoring separates them from the notes themselves.
  question phase  structure arms: recall(question); an ANSWER / UPDATED with a quotable stretch -> weave_span + emit (abstain cannot_weave if either is refused); CHOICE -> abstain contested;
                  NONE or an unreadable (budget-cut) result -> abstain no_record.   A1: log_grep on the first 6 characters of the question, then answer none.   A0: answer none.
Usage is ESTIMATED from the characters of the request and the response (`est_tokens`: one token per non-ASCII character, one per 4 ASCII characters): the stub reports no real tokens, and every number
that comes from it says "estimated".
"""
from __future__ import annotations

import json
import os
import re
import sys
from types import SimpleNamespace
from typing import Any, Dict, List, Optional, Tuple

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(HERE))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from verantyx.loom import memshape as ms   # noqa: E402

TOPIC = "進捗確認"
WRITE_CAP = 64
TURN_RX = re.compile(r"\[(\d+-\d+)\] ([^:\n]*): (.*)", re.S)
TURNS_RX = re.compile(r"turns=([0-9,\-s]+)")


def est_tokens(text: str) -> int:
    """The estimate of the stub: 1 token per non-ASCII character + 1 per 4 ASCII characters (rounded up).  Japanese text is about one token per character; JSON and tool schemas are ASCII."""
    na = sum(1 for ch in text if ord(ch) > 127)
    return na + (len(text) - na + 3) // 4


def _get(o: Any, k: str, d: Any = None) -> Any:
    return o.get(k, d) if isinstance(o, dict) else getattr(o, k, d)


def chunks(text: str) -> List[str]:
    """The writes of one message: its sentences cut after 「。」, each at most 64 characters (a longer one is cut at 64: a stub does not rewrite)."""
    out, cur = [], ""
    for ch in text:
        cur += ch
        if ch == "。":
            out.append(cur)
            cur = ""
    if cur.strip():
        out.append(cur)
    return [c[:WRITE_CAP] for c in out if c.strip()]


def op_for(text: str) -> str:
    e = ms.exchange(text, ms.SHAPES_V2)
    return "write" if e.clauses and all(c.shape != "F0" for c in e.clauses) else "keep_unshaped"


def _blocks(content: Any) -> List[Any]:
    return list(content) if isinstance(content, list) else []


def _text_of(content: Any) -> str:
    if isinstance(content, str):
        return content
    return "\n".join(str(_get(b, "text", "")) for b in _blocks(content) if _get(b, "type") == "text")


class StubClient:
    def __init__(self, model: str = "stub-model") -> None:
        self.model = model
        self.messages = SimpleNamespace(create=self._create)
        self.requests = 0
        self.est_input_tokens = 0
        self.est_output_tokens = 0

    # ------------------------------------------------------------------------------------------------------
    def _create(self, **kw: Any) -> Any:
        names = [t["name"] for t in kw["tools"]]
        msgs = kw["messages"]
        calls = self._policy(names, msgs)
        blocks = [SimpleNamespace(type="tool_use", id="toolu_stub_%d_%d" % (self.requests, i), name=n, input=dict(a)) for i, (n, a) in enumerate(calls)]
        req = json.dumps({"system": kw.get("system", ""), "tools": kw["tools"], "messages": msgs}, ensure_ascii=False, default=lambda o: dict(vars(o)) if hasattr(o, "__dict__") else str(o))
        t_in = est_tokens(req)
        t_out = est_tokens(json.dumps([[n, a] for n, a in calls], ensure_ascii=False)) + 4
        self.requests += 1
        self.est_input_tokens += t_in
        self.est_output_tokens += t_out
        usage = SimpleNamespace(input_tokens=t_in, output_tokens=t_out, cache_read_input_tokens=0, cache_creation_input_tokens=0)
        return SimpleNamespace(content=blocks, stop_reason="tool_use", model=self.model, usage=usage)

    # ------------------------------------------------------------------------------------------------------
    def _policy(self, names: List[str], msgs: List[dict]) -> List[Tuple[str, dict]]:
        if names == ["report"]:                                         # the forced final report of a turn that ended without one
            return [("report", {"contradictions": []})]
        if "answer" in names or "emit" in names:
            return self._question(names, msgs)
        return self._story(names, msgs)

    # -- the story phase -------------------------------------------------------------------------------------
    def _current_turn(self, msgs: List[dict]) -> Tuple[Optional[int], Optional[str], str]:
        """(index of the user message that delivered the current message, its turn id, its text)."""
        for i in range(len(msgs) - 1, -1, -1):
            m = msgs[i]
            if _get(m, "role") != "user":
                continue
            txt = _text_of(_get(m, "content"))
            hits = TURN_RX.findall(txt)
            if hits:
                last = None
                for mm in TURN_RX.finditer(txt):
                    last = mm
                return i, last.group(1), last.group(3)
        return None, None, ""

    def _story(self, names: List[str], msgs: List[dict]) -> List[Tuple[str, dict]]:
        i0, turn, text = self._current_turn(msgs)
        if turn is None:
            return [("report", {"contradictions": []})]
        done: List[Tuple[str, Any]] = []                                # (tool name, parsed result) of this turn, in order
        uses: Dict[str, str] = {}
        for m in msgs[i0 + 1:]:
            if _get(m, "role") == "assistant":
                for b in _blocks(_get(m, "content")):
                    if _get(b, "type") == "tool_use":
                        uses[_get(b, "id")] = _get(b, "name")
                        done.append((_get(b, "name"), None))
        k = 0
        results: List[Any] = []
        for m in msgs[i0 + 1:]:                                         # the results of THIS turn only (the message that delivered the turn also carries the previous turn's results)
            if _get(m, "role") == "user":
                for b in _blocks(_get(m, "content")):
                    if _get(b, "type") == "tool_result":
                        try:
                            results.append(json.loads(_get(b, "content")))
                        except (ValueError, TypeError):
                            results.append(None)
        n_done = len(done)
        sents = chunks(text)
        plan: List[Tuple[str, dict]] = []
        structure = "write" in names
        if structure:
            if turn.endswith("-1"):
                plan.append(("declare_topic", {"text": TOPIC}))
            for c in sents:
                plan.append((op_for(c), {"text": c}))
        elif "log_append" in names:
            for c in sents:
                plan.append(("log_append", {"text": ("%s %s" % (turn, c))[:WRITE_CAP]}))
        if n_done < len(plan):
            return [plan[n_done]]
        pairs: List[List[str]] = []
        for r in results:
            if isinstance(r, dict) and isinstance(r.get("lines"), list):
                for ln in r["lines"]:
                    if isinstance(ln, str) and (ln.startswith("! SAME_SEAT") or ln.startswith("! REVERSAL_X")):
                        mt = TURNS_RX.search(ln)
                        if mt:
                            ts = [t for t in mt.group(1).split(",") if re.fullmatch(r"\d+-\d+", t)]
                            for t in ts[:-1]:
                                if t != ts[-1] and [t, ts[-1]] not in pairs:
                                    pairs.append([t, ts[-1]])
        return [("report", {"contradictions": pairs[:10]})]

    # -- the question phase ---------------------------------------------------------------------------------
    def _question_text(self, msgs: List[dict]) -> str:
        txt = _text_of(_get(msgs[0], "content"))
        j = txt.find("{")
        if j >= 0:
            try:
                d = json.loads(txt[j:])
                q = d.get("question")
                if isinstance(q, dict):
                    q = q.get("text")
                if not isinstance(q, str):
                    t = d.get("task")
                    q = t.get("text") if isinstance(t, dict) else None
                if isinstance(q, str):
                    return q
            except ValueError:
                pass
        return ""

    def _question(self, names: List[str], msgs: List[dict]) -> List[Tuple[str, dict]]:
        q = self._question_text(msgs)
        steps: List[Tuple[str, str]] = []                               # (tool name, id)
        results: Dict[str, Any] = {}
        for m in msgs[1:]:
            if _get(m, "role") == "assistant":
                for b in _blocks(_get(m, "content")):
                    if _get(b, "type") == "tool_use":
                        steps.append((_get(b, "name"), _get(b, "id")))
            elif _get(m, "role") == "user":
                for b in _blocks(_get(m, "content")):
                    if _get(b, "type") == "tool_result":
                        try:
                            results[_get(b, "tool_use_id")] = json.loads(_get(b, "content"))
                        except (ValueError, TypeError):
                            results[_get(b, "tool_use_id")] = None
        if "recall" in names:
            if not steps:
                return [("recall", {"question": q[:64]})]
            last_name, last_id = steps[-1]
            res = results.get(last_id)
            if last_name == "recall":
                if not isinstance(res, dict):
                    return [("abstain", {"type": "no_record"})]
                v = res.get("verdict")
                if v == "CHOICE":
                    return [("abstain", {"type": "contested"})]
                if v in ("ANSWER", "UPDATED") and res.get("answers"):
                    occ = res["answers"][0]["occurrences"]
                    occ = max(occ, key=lambda o: o["sid"]) if occ else None
                    if occ and occ.get("span"):
                        return [("weave_span", {"sid": occ["sid"], "tier": "WORD", "first": occ["span"][0], "last": occ["span"][1]})]
                return [("abstain", {"type": "no_record"})]
            if last_name == "weave_span":
                return [("emit", {})] if isinstance(res, dict) and res.get("ok") else [("abstain", {"type": "cannot_weave"})]
            return [("abstain", {"type": "cannot_weave"})]
        if "log_grep" in names and not steps:
            return [("log_grep", {"terms": [q[:6] or "x"], "max_lines": 10})]
        return [("answer", {"kind": "none", "values": []})]
