"""PUB-M2/M3/M4 measurement (offline, no model, no API): the mem.v4 memory crosses over

  (a) the bank5 story texts, each message text written VERBATIM as ONE write (no model) into a real mem.v4 store, one session per story session; a text over 64 characters (the cap of one write; 2 of
      156 messages) is cut after 「。」 into writes of its own; the task title is declared as the topic at the start of every session (the nest of the protocol, particles allowed);
  (b) the 36 meter v1 stores (6 tasks x blind / notes x 3 repeats): (b2) the model's RAW write calls (the ok ones and the refused ones, as the ledgers hold them) and its declare_topic calls, replayed in order
      into a fresh mem.v4 store, session by session, with the turn id they had; (b1) the sentences each store STORED (what the old structure accepted, topic-expanded), as H, through `build_index`.

A write is accepted iff every clause is F1-F4 (shape.v2); an F0 clause refuses it (counted F0, nothing stored; no keep_unshaped here); the weave_span thread is attempted for every accepted write and a
refusal is counted (`weave_refused`, the sentence is stored anyway).  The index of a store is `MemStore.index()` (derived from the verified ledgers).

  PYTHONPATH=. PYTHONHASHSEED=0 python experiments/line3/pub/m2/measure.py      (writes results.json and REPORT.md next to this file; deterministic)
"""
from __future__ import annotations

import collections
import glob
import json
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(HERE))))
sys.path.insert(0, ROOT)

from verantyx.loom import memcross as mx  # noqa: E402
from verantyx.loom import memory as mem   # noqa: E402
from verantyx.loom import memshape as ms  # noqa: E402

METER = os.path.join(ROOT, "experiments", "line3", "mem", "meter_v1")
BANK5 = os.path.join(ROOT, "experiments", "line3", "bank5", "bank5.jsonl")
WRITE_CAP = 64


def chunks(text):
    if len(text) <= WRITE_CAP:
        return [text]
    out, cur = [], ""
    for ch in text:
        cur += ch
        if ch == "。":
            out.append(cur)
            cur = ""
    if cur:
        out.append(cur)
    return out


class Tally:
    def __init__(self):
        self.writes = 0
        self.accepted = 0
        self.f0 = 0
        self.other_refused = collections.Counter()
        self.weave_refused = 0
        self.weave_refused_reasons = collections.Counter()
        self.f0_reasons = collections.Counter()
        self.clause_shapes = collections.Counter()
        self.completed = 0
        self.change_clauses = 0
        self.topics = 0

    def add(self, other):
        for k in ("writes", "accepted", "f0", "weave_refused", "completed", "change_clauses", "topics"):
            setattr(self, k, getattr(self, k) + getattr(other, k))
        for k in ("other_refused", "weave_refused_reasons", "f0_reasons", "clause_shapes"):
            getattr(self, k).update(getattr(other, k))

    def to_obj(self):
        pct = lambda a, b: round(100.0 * a / b, 1) if b else None
        return {"writes": self.writes, "accepted": self.accepted, "accepted_pct": pct(self.accepted, self.writes), "f0": self.f0, "f0_pct": pct(self.f0, self.writes),
                "other_refused": dict(sorted(self.other_refused.items())), "weave_refused_but_accepted": self.weave_refused, "weave_refused_pct_of_accepted": pct(self.weave_refused, self.accepted),
                "weave_refused_reasons": dict(sorted(self.weave_refused_reasons.items())), "f0_reasons": dict(sorted(self.f0_reasons.items())),
                "accepted_clauses_by_shape": dict(sorted(self.clause_shapes.items())), "completed_by_nest": self.completed, "change_clauses": self.change_clauses, "topics_declared": self.topics}


def drive(store_dir, sessions):
    """sessions: [[("declare", text) | ("write", text, turn)]].  A real mem.v4 store: begin / calls / commit per session.  -> (Tally, MemIndex, verify status, replay status)."""
    t = Tally()
    st = mem.MemStore(store_dir, "m")
    for ops in sessions:
        s = st.begin("measure", profile=mem.PROFILE_V4)
        for op in ops:
            if op[0] == "declare":
                r = s.call("declare_topic", {"text": op[1]})
                if r.get("ok"):
                    t.topics += 1
                else:
                    t.other_refused["declare:" + r["refusal"]] += 1
                continue
            args = {"text": op[1]}
            if op[2]:
                args["turn"] = op[2]
            r = s.call("write", args)
            t.writes += 1
            if r.get("ok"):
                t.accepted += 1
                for c in r["shape"]["clauses"]:
                    t.clause_shapes[c["shape"]] += 1
                    t.completed += c.get("via") == "nest"
                    t.change_clauses += c.get("change") is not None
                if r["weave"] != "ok":
                    t.weave_refused += 1
                    t.weave_refused_reasons[r["weave_refused"]] += 1
            elif r["refusal"] == "no_shape":
                t.f0 += 1
                for c in r["detail"]["clauses"]:
                    t.f0_reasons[c["reason"]] += 1
                if not r["detail"]["clauses"]:
                    t.f0_reasons["no_clause"] += 1
            else:
                t.other_refused[r["refusal"]] += 1
        s.commit()
    v = mem.verify_store(store_dir, mem.FROM_HEADER)
    return t, st.index(), v["status"], v["replay"]["status"] if "replay" in v else None


def bank5_sessions(task):
    out = []
    for si, sess in enumerate(task["sessions"]):
        ops = [("declare", task["title"])]
        for mi, m in enumerate(sess):
            for c in chunks(m["text"]):
                ops.append(("write", c, "%d-%d" % (si + 1, mi + 1)))
        out.append(ops)
    return out


def meter_sessions(store):
    """The raw model calls of a meter v1 store's session ledgers: declare_topic (ok) and every write call (ok or refused) with its turn."""
    out = []
    for d in sorted(glob.glob(os.path.join(store, "sessions", "s*"))):
        ops = []
        for ln in open(os.path.join(d, "ops.jsonl"), encoding="utf-8"):
            r = json.loads(ln)
            if r.get("actor") != "model":
                continue
            if r["op"] == "declare_topic" and r["result"].get("ok") is True:
                ops.append(("declare", r["result"]["topic"]))
            elif r["op"] == "write" and isinstance(r["args"].get("text"), str):
                ops.append(("write", r["args"]["text"], r["args"].get("turn")))
        out.append(ops)
    return out


def stored_rows(store):
    rows = []
    for ln in open(os.path.join(store, "memory.jsonl"), encoding="utf-8"):
        if ln.strip():
            rows.append(json.loads(ln))
    return rows


def pool(indexes):
    """Per-tank numbers over a list of (label, MemIndex): crosses, seats, max ring L, F0 sentences, nests, nest members."""
    out = {t: {"crosses": 0, "seats": 0, "max_L": 0, "seats_by_slot": collections.Counter()} for t in mx.TANKS}
    f0 = nests = members = completed = under = positions = updates = others = 0
    for _, ix in indexes:
        for c in ix.crosses:
            o = out[c.tank]
            o["crosses"] += 1
            o["seats"] += c.n_seats()
            o["max_L"] = max(o["max_L"], c.L)
            for slot, seats in c.slots:
                o["seats_by_slot"][slot] += len(seats)
        f0 += len(ix.f0)
        nests += len(ix.nests)
        for n in ix.nests:
            members += len(n.members)
            completed += sum(1 for m in n.members if m.kind == "completed")
            under += len(n.under)
        positions += len(ix.positions)
        for pos in ix.positions:
            for e in ix.history_full(pos):
                updates += e.kind == "update"
                others += e.kind == "other"
    for t in out:
        out[t]["seats_by_slot"] = dict(sorted(out[t]["seats_by_slot"].items()))
    return {"tanks": out, "f0_tank_sentences": f0, "nests": nests, "nest_members": members, "nest_completed": completed, "nest_under": under, "positions": positions,
            "history_updates": updates, "history_other": others}


def pick_samples(named, n=10):
    """Ten crosses, chosen by a fixed rule: the 3 largest F1, 2 largest F2, 3 largest F3, the largest F4 (if any), then one cross that a nest completed, filled up with the next largest of any tank.
    Rendered as text."""
    cands = []
    for label, ix in named:
        for c in ix.crosses:
            cands.append((label, c, ix))
    key = lambda x: (-x[1].n_seats(), x[0], x[1].tank, x[1].centre)
    chosen = []
    seen = []                                                  # one cross per (source, task, tank, centre): the same story in another repeat or arm is not a new sample

    def take(pred, k):
        for x in sorted(cands, key=key):
            ident = tuple(x[0].split("/")[:2]) + (x[1].tank, x[1].centre)
            if ident not in seen and pred(x) and k > 0:
                chosen.append(x)
                seen.append(ident)
                k -= 1

    take(lambda x: x[1].tank == "F1", 3)
    take(lambda x: x[1].tank == "F2", 2)
    take(lambda x: x[1].tank == "F3", 3)
    take(lambda x: x[1].tank == "F4", 1)
    take(lambda x: any(s.via == "nest" for _, ss in x[1].slots for s in ss), 1)
    take(lambda x: True, n - len(chosen))
    return [{"store": lab, "tank": c.tank, "text": mx.render_cross(c)} for lab, c, ix in chosen[:n]]


def main():
    tmp = tempfile.mkdtemp(prefix="m2_")
    res = {"shape_table": ms.SHAPES_V2, "shapes_sha": ms.SHAPES_SHA_V2, "cross_version": mx.CROSS_VERSION, "checks": {}}

    # -- (a) bank5 --------------------------------------------------------------------------------------------------------------------------------
    tally_a, idx_a, checks = Tally(), [], []
    for ln in open(BANK5, encoding="utf-8"):
        if not ln.strip():
            continue
        task = json.loads(ln)
        t, ix, v, rp = drive(os.path.join(tmp, "a_" + task["id"]), bank5_sessions(task))
        tally_a.add(t)
        idx_a.append((task["id"], ix))
        checks.append((task["id"], v, rp, ix.index_sha))
    res["bank5"] = {"stories": len(idx_a), "acceptance": tally_a.to_obj(), "index": pool(idx_a), "verify": {c[0]: [c[1], c[2]] for c in checks}, "index_sha": {c[0]: c[3] for c in checks}}

    # -- (b2) the meter's raw calls replayed ---------------------------------------------------------------------------------------------------
    tally_b, idx_b, bad, n = Tally(), [], [], 0
    for arm in ("blind", "notes"):
        for d in sorted(glob.glob(os.path.join(METER, "*", arm, "r0*"))):
            lab = os.path.relpath(d, METER)
            sessions = meter_sessions(os.path.join(d, "store"))
            t, ix, v, rp = drive(os.path.join(tmp, "b_" + lab.replace(os.sep, "_")), sessions)
            tally_b.add(t)
            idx_b.append((lab, ix))
            n += 1
            if v != "OK" or rp != "IDENTICAL":
                bad.append([lab, v, rp])
    res["meter_v1_raw_writes"] = {"stores": n, "acceptance": tally_b.to_obj(), "index": pool(idx_b), "not_verified": bad}

    # -- (b1) the meter's stored sentences through build_index ----------------------------------------------------------------------------------
    idx_c, f0_unplaced = [], collections.Counter()
    for arm in ("blind", "notes"):
        for d in sorted(glob.glob(os.path.join(METER, "*", arm, "r0*"))):
            rows = stored_rows(os.path.join(d, "store"))
            ix = mx.build_index(rows)
            idx_c.append((os.path.relpath(d, METER), ix))
            for c in ix.clauses:
                f0_unplaced[c.shape] += 1
    res["meter_v1_stored_sentences"] = {"stores": len(idx_c), "sentences": sum(ix.n for _, ix in idx_c), "clauses_by_shape": dict(sorted(f0_unplaced.items())), "index": pool(idx_c)}

    samples = pick_samples([("bank5/" + l, ix) for l, ix in idx_a] + [("meter_v1/" + l, ix) for l, ix in idx_b])
    res["samples"] = samples
    with open(os.path.join(HERE, "results.json"), "w", encoding="utf-8") as f:
        f.write(json.dumps(res, ensure_ascii=False, sort_keys=True, indent=1) + "\n")
    with open(os.path.join(HERE, "REPORT.md"), "w", encoding="utf-8") as f:
        f.write(report(res))
    print(report(res))


def row(t, p):
    o = p["tanks"][t]
    return "| %s | %d | %d | %d |" % (t, o["crosses"], o["seats"], o["max_L"])


def report(res):
    out = ["# PUB-M2/M3/M4 measurement (offline, no model)", "",
           "shape table %s (sha %s), cross serialisation %s.  Script: `experiments/line3/pub/m2/measure.py`; numbers: `results.json`." % (res["shape_table"], res["shapes_sha"], res["cross_version"]), ""]
    for key, title in (("bank5", "(a) bank5: 6 stories, each message text one write"), ("meter_v1_raw_writes", "(b2) the 36 meter v1 stores: the model's raw write calls replayed")):
        a, p = res[key]["acceptance"], res[key]["index"]
        out += ["## " + title, "",
                "writes %d: accepted %d (%s %%), F0 refused %d (%s %%), other refusals %s; accepted but weave_span refused %d (%s %% of accepted); topics declared %d." % (
                    a["writes"], a["accepted"], a["accepted_pct"], a["f0"], a["f0_pct"], a["other_refused"], a["weave_refused_but_accepted"], a["weave_refused_pct_of_accepted"], a["topics_declared"]),
                "F0 reasons (clauses): %s.  weave refusals: %s.  Accepted clauses by shape: %s.  Completed by a nest: %d.  Change clauses: %d." % (
                    a["f0_reasons"], a["weave_refused_reasons"], a["accepted_clauses_by_shape"], a["completed_by_nest"], a["change_clauses"]), "",
                "| tank | crosses | seats | max ring L |", "|---|---|---|---|"] + [row(t, p) for t in mx.TANKS]
        out += ["", "F0 tank sentences %d; nests %d (members %d, of which completed %d; written under a nest and not members %d); positions %d; history entries: update %d, other %d." % (
            p["f0_tank_sentences"], p["nests"], p["nest_members"], p["nest_completed"], p["nest_under"], p["positions"], p["history_updates"], p["history_other"]), ""]
    b1 = res["meter_v1_stored_sentences"]
    out += ["## (b1) the 36 meter v1 stores' stored sentences (%d sentences) through build_index" % b1["sentences"], "", "clauses by shape: %s." % b1["clauses_by_shape"], "",
            "| tank | crosses | seats | max ring L |", "|---|---|---|---|"] + [row(t, b1["index"]) for t in mx.TANKS]
    out += ["", "## 10 sample crosses", ""]
    for s in res["samples"]:
        out += ["```", "# " + s["store"], s["text"], "```"]
    return "\n".join(out) + "\n"


if __name__ == "__main__":
    main()
