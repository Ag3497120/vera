"""PUB-M6c stage 1 of the staged shape table (owner 2026-10-13: 「段階的に足す」): what shape.v3 gains and what it costs, BEFORE stage 2 (へ -> に) is built.  Offline, no model, no API, no store: only the shape
exchanger (shape.v2 against shape.v3) over the writes of

  (a) bank_ls dev (experiments/line3/bank_ls/dev/stories.jsonl; the held-out splits are never opened): every message cut into writes exactly as bank_ls_dev.py does (a text over 64 characters is cut after
      「。」); the FACTS are the story ledger's entries {slot, value, ref = (session, message)};
  (b) meter v1: the RAW write calls (ok and refused, as the ledgers hold them) of the 36 structure runs (`pub/m2/measure.py meter_sessions`); the FACTS are the gold values of the questions of the task
      (with their message refs) and the values of its plants (with their message refs).

For each source it reports
  accepted writes          shape.v2 vs shape.v3 (a write is accepted iff every clause is F1-F4), writes lost (must be 0), v2 clauses that v3 reads differently (must be 0)
  FACTS GAINED             a fact is INDEXED iff an accepted write of one of its messages has a placed clause (F1-F4) one of whose seats holds the fact's value (normalised text); gained = indexed under
                           v3 and not under v2; lost (must be 0)
  NEW CLAUSES              the placed clauses that shape.v2 did not place (the clause text is not a v2 placed clause of the same write), by shape
  WRONG SEATS INTRODUCED   among the new clauses that CONTAIN the value of a fact of their message (fact-bearing): `value_seat_wrong` = no seat of the clause is exactly the value (the value sits inside a
                           bigger phrase, or is split); `owner_unmatched` = (F1) an owner / centre phrase that shares no two-character piece with the fact's slot / plant name, shown for REVIEW, not counted as wrong.
                           A seat the ledger / plants cannot judge (a new clause with no fact of its message) is not counted; the first 40 fact-bearing new clauses are printed with all their seats for the auditor.

  PYTHONPATH=. PYTHONHASHSEED=0 python experiments/line3/pub/m6c/stage1.py [--workers 4] [--limit N]      -> stage1.{json,md} next to this file
"""
from __future__ import annotations

import argparse
import collections
import json
import os
import sys
from typing import Any, Dict, List, Optional, Sequence, Tuple

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "m5m6"))

import common as K  # noqa: E402  (puts the repo root on sys.path)
from common import C  # noqa: E402
from verantyx.loom import memshape as ms  # noqa: E402

OUT = HERE
DEV = os.path.join(K.ROOT, "experiments", "line3", "bank_ls", "dev", "stories.jsonl")
CAP = 64
V2, V3 = ms.SHAPES_V2, ms.SHAPES_V3


def chunks(text: str) -> List[str]:
    if len(text) <= CAP:
        return [text]
    out: List[str] = []
    cur = ""
    for ch in text:
        cur += ch
        if ch == "。":
            out.append(cur)
            cur = ""
    if cur:
        out.append(cur)
    return out


def nrm(t: str) -> str:
    return C.norm(t)


def accepted(ex: ms.Exchange) -> bool:
    return bool(ex.clauses) and all(c.shape != "F0" for c in ex.clauses)


def seats_of(c: ms.Clause) -> List[Tuple[str, str]]:
    """[(kind, text)] of every seat of a placed clause: centre, value, quantity, object_bare and the arms (nested arms too)."""
    out: List[Tuple[str, str]] = []
    if c.centre:
        out.append(("centre", c.centre))
    if c.value is not None:
        out.append(("value", c.value.text))
    if c.quantity is not None:
        out.append(("quantity", c.quantity.text))
    if c.object_bare is not None:
        out.append(("object_bare", c.object_bare.text))

    def chain(a: ms.Arm) -> str:                          # 「目線の高さ」: the seat with the の chain it owns, as the sentence writes it
        return (chain(a.arms[0]) + "の" if a.arms and a.arms[0].particle == "の" else "") + a.seat.text

    def arm(a: ms.Arm, path: str) -> None:
        out.append((path + a.particle, a.seat.text))
        if a.arms:
            out.append((path + a.particle + "(chain)", chain(a)))
        for b in a.arms:
            arm(b, path + a.particle + ">")
    for a in c.arms:
        arm(a, "")
    return out


def pieces2(t: str) -> List[str]:
    t = nrm(t)
    return [t[i:i + 2] for i in range(len(t) - 1)]


class Tally:
    def __init__(self) -> None:
        self.c: collections.Counter = collections.Counter()
        self.examples: Dict[str, List[dict]] = collections.defaultdict(list)
        self.review: List[dict] = []

    def ex(self, key: str, item: dict, cap: int = 12) -> None:
        if len(self.examples[key]) < cap:
            self.examples[key].append(item)

    def add(self, o: "Tally") -> None:
        self.c.update(o.c)
        for k, v in o.examples.items():
            for it in v:
                self.ex(k, it)
        self.review += o.review


def analyse(source: str, writes: Sequence[dict], facts: Sequence[dict]) -> Tally:
    """writes: [{text, msg}] (msg = a hashable message key); facts: [{value, msgs: [message keys], slot}]."""
    t = Tally()
    by_msg: Dict[Any, List[dict]] = collections.defaultdict(list)
    for w in writes:
        e2, e3 = ms.exchange(w["text"], V2), ms.exchange(w["text"], V3)
        w["e2"], w["e3"] = e2, e3
        w["a2"], w["a3"] = accepted(e2), accepted(e3)
        by_msg[w["msg"]].append(w)
        t.c["writes"] += 1
        t.c["accepted_v2"] += w["a2"]
        t.c["accepted_v3"] += w["a3"]
        if w["a2"] and not w["a3"]:
            t.c["writes_lost"] += 1
        if w["a3"] and not w["a2"]:
            t.c["writes_gained"] += 1
        p2 = {x.text: x for x in e2.clauses if x.shape != "F0"}
        for x in e3.clauses:
            if x.text in p2 and x.to_obj() != p2[x.text].to_obj():
                t.c["v2_clauses_read_differently"] += 1
        w["new"] = [x for x in e3.clauses if x.shape != "F0" and x.text not in p2]
        for x in w["new"]:
            t.c["new_clauses"] += 1
            t.c["new_" + x.shape] += 1
            t.c["new_in_accepted_write" if w["a3"] else "new_in_refused_write"] += 1
    def indexed(f: dict, key: str) -> bool:
        v = nrm(f["value"])
        for m in f["msgs"]:
            for w in by_msg.get(m, ()):
                if not w[key]:
                    continue
                for x in w["e3" if key == "a3" else "e2"].clauses:
                    if x.shape != "F0" and any(v in nrm(txt) for _k, txt in seats_of(x)):
                        return True
        return False
    for f in facts:
        i2, i3 = indexed(f, "a2"), indexed(f, "a3")
        t.c["facts"] += 1
        t.c["facts_indexed_v2"] += i2
        t.c["facts_indexed_v3"] += i3
        if i3 and not i2:
            t.c["facts_gained"] += 1
            t.ex("facts_gained", {"value": f["value"], "slot": f.get("slot"), "texts": [w["text"] for m in f["msgs"] for w in by_msg.get(m, ()) if nrm(f["value"]) in nrm(w["text"])][:2]})
        if i2 and not i3:
            t.c["facts_lost"] += 1
    # wrong seats among the new clauses of fact-bearing messages
    fact_by_msg: Dict[Any, List[dict]] = collections.defaultdict(list)
    for f in facts:
        for m in f["msgs"]:
            fact_by_msg[m].append(f)
    for w in writes:
        for x in w["new"]:
            if not w["a3"]:
                continue                                   # the clause is not in the memory when the write is refused
            seats = seats_of(x)
            for f in fact_by_msg.get(w["msg"], ()):
                v = nrm(f["value"])
                if v not in nrm(x.text):
                    continue
                t.c["new_fact_bearing_clauses"] += 1
                exact = any(nrm(txt) == v for _k, txt in seats)
                holds = any(v in nrm(txt) for _k, txt in seats)
                item = {"source": source, "text": x.text, "shape": x.shape, "centre": x.centre, "value": f["value"], "slot": f.get("slot"), "seats": seats}
                if not exact:
                    t.c["value_seat_wrong"] += 1
                    t.c["value_inside_bigger_seat" if holds else "value_split"] += 1
                    t.ex("value_seat_wrong", item)
                else:
                    t.c["value_seat_exact"] += 1
                slot = nrm(f.get("slot") or "")
                if x.shape in ("F1", "F2") and slot:
                    own = [txt for k, txt in seats if k.startswith("の") or k == "centre"]
                    if own and not any(p in slot for txt in own for p in pieces2(txt)):
                        t.c["owner_unmatched"] += 1
                        t.ex("owner_unmatched", item)
                if len(t.review) < 40:
                    t.review.append(item)
    return t


def dev_part() -> dict:
    stories = [json.loads(ln) for ln in open(DEV, encoding="utf-8") if ln.strip()]
    writes: List[dict] = []
    facts: List[dict] = []
    for s in stories:
        for si, sess in enumerate(s["sessions"]):
            for mi, m in enumerate(sess):
                for c in chunks(m["text"]):
                    writes.append({"text": c, "msg": (s["id"], si, mi)})
        for e in s["ledger"]:
            facts.append({"value": e["value"], "msgs": [(s["id"], e["ref"][0], e["ref"][1])], "slot": e["slot"]})
    return {"writes": writes, "facts": facts}


def meter_run(run_dir: str) -> Tally:
    m2 = K.load_m2()
    r = C.load_result(run_dir)
    task = C.mem_run.find_task(r["task_id"])
    writes: List[dict] = []
    for ops in m2.meter_sessions(os.path.join(run_dir, "store")):
        for op in ops:
            if op[0] == "write":
                writes.append({"text": op[1], "msg": op[2]})
    facts: List[dict] = []
    for q in task["questions"]:
        gk, gv = C.mem_run.gold_values(q["gold"])
        refs = [C.mem_run.turn_id(s_, i_) for s_, i_ in q.get("refs", [])]
        for k, v in enumerate(gv):
            msgs = [refs[k]] if gk == "contested" and len(refs) == len(gv) else refs
            facts.append({"value": v, "msgs": msgs, "slot": q["q"]})
    for p in task["plants"]:
        refs = [C.mem_run.turn_id(s_, i_) for s_, i_ in p["message_refs"]]
        for k, v in enumerate(p.get("values", [])):
            msgs = [refs[k]] if len(refs) == len(p["values"]) else refs
            facts.append({"value": v, "msgs": msgs, "slot": p.get("fact", "")})
    # the same writes of one run belong to messages by their turn (None: no turn)
    return analyse(os.path.basename(os.path.dirname(os.path.dirname(run_dir))) + "/" + C.label(run_dir), [w for w in writes if w["msg"]], facts)


def dev_tally() -> Tally:
    d = dev_part()
    return analyse("bank_ls_dev", d["writes"], d["facts"])


def pct(a: int, b: int) -> Optional[float]:
    return round(100.0 * a / b, 1) if b else None


def block(name: str, t: Tally) -> dict:
    c = t.c
    return {"name": name, "counts": dict(sorted(c.items())), "accepted_pct_v2": pct(c["accepted_v2"], c["writes"]), "accepted_pct_v3": pct(c["accepted_v3"], c["writes"]),
            "facts_indexed_pct_v2": pct(c["facts_indexed_v2"], c["facts"]), "facts_indexed_pct_v3": pct(c["facts_indexed_v3"], c["facts"]),
            "examples": {k: v for k, v in sorted(t.examples.items())}}


def md(blocks: Sequence[dict], review: Sequence[dict]) -> str:
    out = ["# PUB-M6c 段階 ① (shape.v3) の効果と費用 — 段階 ② の前の測定（offline、モデルなし）", "",
           "shape.v2 と shape.v3 を同じ書き込みに当てる。事実 = 物語の台帳（bank_ls dev）/ 設問の金と仕掛けの値（meter v1）。事実が「索引に入った」= 受理された書き込みの置かれた節の席に値がある。",
           "**誤った席** = 事実を含む新しい節で、値そのものの席がない（値が大きな句の中に埋もれた / 割れた）。`owner_unmatched` は目視用（誤りに数えない）。", ""]
    out += ["| 源 | 書き込み | 受理 v2 | 受理 v3 | 失った書き込み | 変わった v2 の節 | 新しい節 | 事実 | 索引 v2 | 索引 v3 | **増えた事実** | 失った事実 | 事実を含む新節 | **誤った席** | 値は正確な席 | owner_unmatched |",
            "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for b in blocks:
        c = b["counts"]
        out.append("| %s | %d | %d (%s %%) | %d (%s %%) | %d | %d | %d (%s) | %d | %d | %d | **%d** | %d | %d | **%d** | %d | %d |" % (
            b["name"], c.get("writes", 0), c.get("accepted_v2", 0), b["accepted_pct_v2"], c.get("accepted_v3", 0), b["accepted_pct_v3"], c.get("writes_lost", 0), c.get("v2_clauses_read_differently", 0),
            c.get("new_clauses", 0), {k[4:]: v for k, v in c.items() if k in ("new_F1", "new_F2", "new_F3", "new_F4")}, c.get("facts", 0), c.get("facts_indexed_v2", 0), c.get("facts_indexed_v3", 0),
            c.get("facts_gained", 0), c.get("facts_lost", 0), c.get("new_fact_bearing_clauses", 0), c.get("value_seat_wrong", 0), c.get("value_seat_exact", 0), c.get("owner_unmatched", 0)))
    for b in blocks:
        for key in ("facts_gained", "value_seat_wrong", "owner_unmatched"):
            ex = b["examples"].get(key, [])
            if ex:
                out += ["", "### %s — %s（最大 12）" % (b["name"], key), ""]
                for it in ex:
                    out.append("- %s" % json.dumps(it, ensure_ascii=False, sort_keys=True))
    out += ["", "## 事実を含む新しい節（監査用、先頭 40）", ""]
    for it in review:
        out.append("- [%s] %s %s 「%s」 値=%s 席=%s" % (it["source"], it["shape"], it["centre"], it["text"], it["value"], it["seats"]))
    return "\n".join(out) + "\n"


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--workers", type=int, default=K.DEFAULT_WORKERS)
    ap.add_argument("--limit", type=int, default=0, help="only the first N meter runs (a smoke test)")
    ns = ap.parse_args(argv)
    dev = dev_tally()
    dirs = C.structure_runs(C.METER_V1)
    if ns.limit:
        dirs = dirs[:ns.limit]
    runs = K.pmap(meter_run, dirs, ns.workers)
    meter = Tally()
    for r in runs:
        meter.add(r)
    blocks = [block("bank_ls dev", dev), block("meter v1 (%d runs)" % len(runs), meter)]
    res = {"stage": 1, "shape_v2": ms.SHAPES_SHA_V2, "shape_v3": ms.SHAPES_SHA_V3, "blocks": blocks, "review": dev.review + meter.review}
    K.write_json(os.path.join(OUT, "stage1.json"), res)
    K.write_text(os.path.join(OUT, "stage1.md"), md(blocks, (dev.review + meter.review)[:40]))
    print(md(blocks, (dev.review + meter.review)[:12]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
