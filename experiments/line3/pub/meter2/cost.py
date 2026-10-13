"""PUB-M10-prep: the COST ESTIMATE of the real API runs of the long-story meter, from the stub's transcripts (no API, no network).

  PYTHONPATH=. python experiments/line3/pub/meter2/cost.py --bank experiments/line3/bank_ls/dev/stories.jsonl --story LS-D01 --repeats 1 [--factor 1,2,3] [--rate 0.1019]
  PYTHONPATH=. python experiments/line3/pub/meter2/cost.py --bank ... --stories 6 --repeats 3            # a set of N stories of the size of the given one(s): the held-out_1 plan (6 stories x 4 arms x 3 repeats)

HOW.  (1) CALIBRATE: the stub meter is run on a tiny built-in story with each arm; the stub records the ESTIMATED input tokens of every request (`stub_client.est_tokens`: one token per non-ASCII character, one per 4 ASCII).  From
the transcripts: P = the tokens of the first request of a session (system prompt + tool schemas + the begin result + the first message), the increment of each kind of call (the model's tool call + the tool result the
driver puts back: write, declare_topic, log_append, report), and the tokens per question of the question phase.  (2) SIMULATE the story the bank gives (messages, sentences per message, per session): every API call of a
session re-sends the conversation of the session (no prompt caching is assumed), so a session costs  sum over its calls of (P + the tokens accumulated so far).  The question phase is  questions x tokens per question.
(3) Price: --rate dollars per million INPUT tokens, ALL-IN (the earlier meter: 62.8M input tokens ~ 6.4 dollars = 0.1019, output and the small model's price included).

THE STUB MAKES EXACTLY ONE CALL PER SENTENCE.  A real model also reads (`recall`, `view`, `log_grep`), rewrites a refused sentence and repeats: its calls per message are higher.  The estimate is therefore a LOWER BOUND
(factor 1); the factors 2 and 3 are the plausible band (the meter v1 spent 87,000 input tokens per message on the structure arm with the cross JSON piled into the conversation; the window of view.v1 is meant to cut
that, so the real factor is a measurement of the pilot, not a promise).  Nothing here is a measured API cost.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from typing import Any, Dict, List, Optional, Sequence

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(HERE))))
for p in (ROOT, HERE):
    if p not in sys.path:
        sys.path.insert(0, p)

import meter2 as M2               # noqa: E402
import stub_client as SC          # noqa: E402

RATE_PER_M = 0.1019               # dollars per million input tokens, all-in: 6.4 / 62.8 (the memory meter on gate v2, Haiku)
CALIB_STORY = {"id": "CALIB", "title": "calibration", "sessions": [
    [{"speaker": "佐藤", "text": "広報の担当は山本です。会議の会場は大阪です。"}, {"speaker": "田中", "text": "備品の期限は水曜です。"}, {"speaker": "鈴木", "text": "認証の期限は金曜です。広報の予算は十万円です。会議の議題は計画です。"}],
    [{"speaker": "佐藤", "text": "広報の担当は中村です。"}, {"speaker": "田中", "text": "会議の会場は大阪から福岡に変更です。備品の担当は小林です。"}]],
    "plants": [], "checkpoints": [{"index": 0, "fraction": 0.5, "after_session": 0}, {"index": 1, "fraction": 1.0, "after_session": 1}],
    "questions": [{"q": "会議の会場は何ですか", "gold": "大阪", "kind": "plain", "checkpoint": 0, "refs": []}, {"q": "総務の担当は何ですか", "gold": "記録なし", "kind": "absent", "checkpoint": 0, "refs": []},
                  {"q": "広報の担当は何ですか", "gold": "矛盾: 山本 と 中村", "kind": "contradiction", "checkpoint": 1, "refs": []}, {"q": "会議の会場は何ですか", "gold": "福岡", "kind": "update", "checkpoint": 1, "refs": []}]}


class TracingStub(SC.StubClient):
    def __init__(self) -> None:
        super().__init__()
        self.trace: List[dict] = []

    def _create(self, **kw: Any) -> Any:
        before = self.est_input_tokens
        r = super()._create(**kw)
        self.trace.append({"tools": [t["name"] for t in kw["tools"]], "tokens": self.est_input_tokens - before, "n_messages": len(kw["messages"]), "calls": [(b.name) for b in r.content],
                           "out": r.usage.output_tokens})
        return r


def calibrate(budget: int = M2.DEFAULT_BUDGET) -> Dict[str, dict]:
    """Per arm: P_story (first request of a session), d_call by tool (tokens one call + its result add), q_tokens (mean tokens per question), q_calls."""
    out: Dict[str, dict] = {}
    for arm in ("A0", "A1", "A3", "A3f"):
        cl = TracingStub()
        with tempfile.TemporaryDirectory() as d:
            M2.run_one(CALIB_STORY, arm, 1, client=cl, model="stub-model", out_root=d, budget=budget, n_checkpoints=2)
        story = [t for t in cl.trace if "report" in t["tools"] and not ("answer" in t["tools"] or "emit" in t["tools"])]
        quest = [t for t in cl.trace if "answer" in t["tools"] or "emit" in t["tools"]]
        first = [t["tokens"] for t in story if t["n_messages"] == 1]
        d_call: Dict[str, List[int]] = {}
        for a, b in zip(story, story[1:]):
            if a["calls"][0] != "report" and b["n_messages"] - a["n_messages"] == 2:                 # the next request of the SAME turn adds the assistant block and the user (tool_result) block; after a `report` the next turn's message comes along
                d_call.setdefault(a["calls"][0], []).append(b["tokens"] - a["tokens"])
        blk = {"type": "tool_use", "id": "toolu_stub_00_0", "name": "report", "input": {"contradictions": []}}
        res = {"type": "tool_result", "tool_use_id": "toolu_stub_00_0", "content": json.dumps({"bugs": [], "contradictions": [], "ok": True, "turn": "00-00"}, sort_keys=True)}
        d_call["report"] = SC.est_tokens(json.dumps(blk)) + SC.est_tokens(json.dumps(res))              # the increment of the closing call, computed (its measured successor also carries the next message)
        per_q = [sum(t["tokens"] for t in quest if t["n_messages"] >= 1) // max(1, sum(1 for t in quest if t["n_messages"] == 1))]
        q_calls = len(quest) // max(1, sum(1 for t in quest if t["n_messages"] == 1))
        out[arm] = {"P_story": sum(first) // max(1, len(first)), "d_call": {k: (v if isinstance(v, int) else sum(v) // len(v)) for k, v in sorted(d_call.items())}, "q_tokens": per_q[0], "q_calls": q_calls,
                    "q_prefix": min(t["tokens"] for t in quest) if quest else 0}
    return out


def simulate(story: dict, arm: str, cal: Dict[str, dict], n_checkpoints: int = 4, recall_extra: int = 0) -> Dict[str, int]:
    """The estimated input tokens of one run of `arm` on `story` (the stub's policy: one call per sentence, one per message for `report`, one `declare_topic` per session for the structure arms)."""
    c = cal[arm]
    cps = sorted(story["checkpoints"], key=lambda x: x["index"])[:n_checkpoints]
    last = cps[-1]["after_session"]
    structure = arm in ("A3", "A3f")
    wr = c["d_call"].get("write", c["d_call"].get("log_append", 0))
    d_dec, d_rep = c["d_call"].get("declare_topic", 0), c["d_call"].get("report", 0)
    story_in = calls = 0
    for s in range(last + 1):
        acc = 0
        if structure:
            story_in += c["P_story"] + acc
            acc += d_dec
            calls += 1
        for i, m in enumerate(story["sessions"][s]):
            acc += SC.est_tokens(M2.render(story, s, i))
            for _ in (SC.chunks(m["text"]) if arm != "A0" else []):                              # A0 has no memory tool: only `report`
                story_in += c["P_story"] + acc
                acc += wr
                calls += 1
            story_in += c["P_story"] + acc
            acc += d_rep
            calls += 1
    nq = sum(1 for q in story["questions"] if q["checkpoint"] in [x["index"] for x in cps])
    q_in = nq * (c["q_tokens"] + (recall_extra if structure else 0))
    return {"story_calls": calls, "story_input": story_in, "questions": nq, "question_input": q_in, "input": story_in + q_in}


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--bank", required=True)
    ap.add_argument("--story", default=None)
    ap.add_argument("--stories", type=int, default=None, help="plan N stories of the size of the selected one(s) (the selection is repeated)")
    ap.add_argument("--repeats", type=int, default=1)
    ap.add_argument("--checkpoints", type=int, default=4)
    ap.add_argument("--arms", default="A0,A1,A3,A3f")
    ap.add_argument("--factor", default="1,2,3")
    ap.add_argument("--rate", type=float, default=RATE_PER_M)
    ap.add_argument("--recall-extra", type=int, default=1500, help="structure arms: tokens a real recall / emit result adds per question beyond the tiny calibration memory (the budget caps a result at 6000 characters)")
    ns = ap.parse_args(list(sys.argv[1:] if argv is None else argv))
    stories = M2.load_stories(ns.bank)
    if ns.story:
        stories = [s for s in stories if s["id"] in ns.story.split(",")]
    if ns.stories:
        stories = [stories[i % len(stories)] for i in range(ns.stories)]
    cal = calibrate()
    arms = ns.arms.split(",")
    factors = [float(x) for x in ns.factor.split(",")]
    per_arm: Dict[str, Dict[str, int]] = {}
    for a in arms:
        tot = {"story_calls": 0, "story_input": 0, "questions": 0, "question_input": 0, "input": 0}
        for s in stories:
            r = simulate(s, a, cal, ns.checkpoints, ns.recall_extra)
            for k in tot:
                tot[k] += r[k]
        per_arm[a] = {k: v * ns.repeats for k, v in tot.items()}
    total = sum(v["input"] for v in per_arm.values())
    rep = {"estimated": True, "stories": [s["id"] for s in stories], "repeats": ns.repeats, "runs": len(stories) * len(arms) * ns.repeats, "calibration": cal, "per_arm": per_arm,
           "input_tokens_lower_bound": total, "rate_per_million_input_tokens": ns.rate,
           "dollars": {("x%g" % f): round(total * f * ns.rate / 1000000, 2) for f in factors}}
    print(json.dumps(rep, ensure_ascii=False, sort_keys=True, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
