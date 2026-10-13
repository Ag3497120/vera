"""PUB-M1 measurement (offline, no API): the shape exchanger (verantyx/loom/memshape.py) over
  (a) every sentence STORED by memory meter v1 (experiments/line3/mem/meter_v1/*/*/r0*/store/memory.jsonl), deduplicated;
  (a2) the same runs' RAW model-written texts of the ok `write` rows (session ledgers; no topic prefix), deduplicated -- what an M1 write would see;
  (b) every message text of experiments/line3/bank5/bank5.jsonl (a dev set: the rules are NOT tuned to it; the long-story bank is held out);
  (c) the meter_v1 write refusals (`span_inexpressible` rows of the session ledgers): how many texts would now be F1-F4.
Run:  PYTHONPATH=. PYTHONHASHSEED=0 python experiments/line3/pub/m1/measure.py     (writes results.json and REPORT.md next to this file)
Deterministic: dedupe keeps the first occurrence in sorted path order; examples are the first 10 of each group in that order."""
from __future__ import annotations

import collections
import glob
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(HERE))))
sys.path.insert(0, ROOT)

from verantyx.loom import memshape as ms  # noqa: E402

METER = os.path.join(ROOT, "experiments", "line3", "mem", "meter_v1")
BANK5 = os.path.join(ROOT, "experiments", "line3", "bank5", "bank5.jsonl")


def stored_sentences():
    seen, out, total = set(), [], 0
    for f in sorted(glob.glob(os.path.join(METER, "*", "*", "r0*", "store", "memory.jsonl"))):
        for ln in open(f, encoding="utf-8"):
            if ln.strip():
                total += 1
                s = json.loads(ln)["sent"]
                if s not in seen:
                    seen.add(s)
                    out.append(s)
    return total, out


def write_texts():
    """(ok raw texts, refused raw texts) of the `write` rows of every session ledger of the meter, deduplicated, with the refusal reason of the refused ones."""
    ok, refused, seen_ok, seen_ref = [], [], set(), set()
    n_ok = n_ref = 0
    reasons = collections.Counter()
    for f in sorted(glob.glob(os.path.join(METER, "*", "*", "r0*", "store", "sessions", "*", "ops.jsonl"))):
        for ln in open(f, encoding="utf-8"):
            r = json.loads(ln)
            if r.get("actor") != "model" or r.get("op") != "write":
                continue
            t = r["args"].get("text")
            if not isinstance(t, str):
                continue
            res = r["result"]
            if res.get("ok") is True:
                n_ok += 1
                if t not in seen_ok:
                    seen_ok.add(t)
                    ok.append(t)
            elif res.get("refusal") == "span_inexpressible":
                n_ref += 1
                reasons[res["detail"].get("reason")] += 1
                if t not in seen_ref:
                    seen_ref.add(t)
                    refused.append(t)
    return n_ok, ok, n_ref, refused, dict(sorted(reasons.items()))


def bank5_messages():
    out = []
    for ln in open(BANK5, encoding="utf-8"):
        if ln.strip():
            t = json.loads(ln)
            for sess in t["sessions"]:
                for m in sess:
                    out.append(m["text"])
    return out


def run(texts):
    """-> dict: sentences, clauses, per-shape counts, F0 reasons with 10 example clause texts each, sentences with a clause of F0 / all clauses F1-F4, skipped labels."""
    shape = collections.Counter()
    reason = collections.Counter()
    ex = collections.defaultdict(list)
    f0_sent = ok_sent = any_ok_sent = no_clause = skipped = 0
    change = via = adv = verb = 0
    for s in texts:
        e = ms.exchange(s)
        skipped += len(e.skipped)
        if not e.clauses:
            no_clause += 1
            continue
        k = [c.shape for c in e.clauses]
        for c in e.clauses:
            shape[c.shape] += 1
            if c.change is not None:
                change += 1
            if c.via_topic:
                via += 1
            adv += len(c.adverbial)
            if c.surface is not None:
                verb += 1
            if c.shape == "F0":
                reason[c.reason] += 1
                if len(ex[c.reason]) < 10:
                    ex[c.reason].append({"clause": c.text, "detail": c.detail, "sentence": s})
        if "F0" in k:
            f0_sent += 1
        else:
            ok_sent += 1
        if any(x != "F0" for x in k):
            any_ok_sent += 1
    n = sum(shape.values())
    return {"inputs": len(texts), "inputs_without_clause": no_clause, "labels_skipped": skipped, "clauses": n,
            "shape": {k: shape.get(k, 0) for k in ms.SHAPE_ORDER}, "change_clauses": change, "via_topic_clauses": via, "adverbials_attached": adv, "verb_events_with_surface": verb,
            "f0_reason": {k: reason[k] for k in sorted(reason)}, "f0_examples": {k: ex[k] for k in sorted(ex)},
            "inputs_all_clauses_F1_F4": ok_sent, "inputs_with_an_F0_clause": f0_sent, "inputs_with_some_F1_F4_clause": any_ok_sent}


def pct(a, b):
    return "%d.%d %%" % ((1000 * a + b // 2) // b // 10, ((1000 * a + b // 2) // b) % 10) if b else "-"


def main() -> None:
    total_rows, stored = stored_sentences()
    n_ok, ok_raw, n_ref, refused, ref_reasons = write_texts()
    msgs = bank5_messages()
    out = {"shapes_version": ms.SHAPES_VERSION, "shapes_sha": ms.SHAPES_SHA,
           "meter_stored": dict(rows=total_rows, distinct=len(stored), **run(stored)),
           "meter_raw_ok_writes": dict(rows=n_ok, distinct=len(ok_raw), **run(ok_raw)),
           "bank5_messages": dict(run(msgs)),
           "meter_refusals": dict(rows=n_ref, distinct=len(refused), refusal_reasons=ref_reasons, **run(refused))}
    # the refusals, once more row by row (not deduplicated): how many ROWS would now be a sentence of F1-F4 clauses only
    row_ok = 0
    by_reason = collections.defaultdict(lambda: [0, 0])                 # refusal reason -> [rows, rows now all F1-F4]
    for f in sorted(glob.glob(os.path.join(METER, "*", "*", "r0*", "store", "sessions", "*", "ops.jsonl"))):
        for ln in open(f, encoding="utf-8"):
            r = json.loads(ln)
            if r.get("actor") == "model" and r.get("op") == "write" and r["result"].get("refusal") == "span_inexpressible" and isinstance(r["args"].get("text"), str):
                e = ms.exchange(r["args"]["text"])
                rr = r["result"]["detail"].get("reason")
                by_reason[rr][0] += 1
                if e.clauses and all(c.shape != "F0" for c in e.clauses):
                    row_ok += 1
                    by_reason[rr][1] += 1
    out["meter_refusals"]["rows_now_all_clauses_F1_F4"] = row_ok
    out["meter_refusals"]["rows_by_refusal_reason"] = {k: {"rows": v[0], "now_F1_F4": v[1]} for k, v in sorted(by_reason.items())}
    with open(os.path.join(HERE, "results.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1, sort_keys=True)
        f.write("\n")
    L = ["# PUB-M1 measurement: the shape exchanger over the meter v1 sentences and bank5", "",
         "shapes %s, SHAPES_SHA %s.  Script: measure.py; numbers: results.json.  bank5 is a dev set (the rules were not tuned to it)." % (ms.SHAPES_VERSION, ms.SHAPES_SHA), ""]
    for key, title in (("meter_stored", "(a) sentences stored by meter v1 (deduplicated)"), ("meter_raw_ok_writes", "(a2) raw texts of the ok writes of meter v1 (deduplicated)"),
                       ("bank5_messages", "(b) bank5 message texts"), ("meter_refusals", "(c) texts of the meter v1 `span_inexpressible` write refusals (deduplicated)")):
        d = out[key]
        L += ["## " + title, "", "inputs %d%s; clauses %d; labels skipped %d; inputs with no clause %d" % (
            d["inputs"], ("" if "rows" not in d else " (from %d rows)" % d["rows"]), d["clauses"], d["labels_skipped"], d["inputs_without_clause"]), "",
            "| shape | clauses | share |", "|---|---|---|"]
        for k in ms.SHAPE_ORDER:
            L.append("| %s %s | %d | %s |" % (k, ms.SHAPE_NAMES[k], d["shape"][k], pct(d["shape"][k], d["clauses"])))
        L += ["", "inputs whose clauses are all F1-F4: %d of %d (%s); with an F0 clause: %d (%s); with some F1-F4 clause: %d (%s)" % (
            d["inputs_all_clauses_F1_F4"], d["inputs"], pct(d["inputs_all_clauses_F1_F4"], d["inputs"]), d["inputs_with_an_F0_clause"], pct(d["inputs_with_an_F0_clause"], d["inputs"]),
            d["inputs_with_some_F1_F4_clause"], pct(d["inputs_with_some_F1_F4_clause"], d["inputs"])),
            "change clauses %d, F3 with the topic as subject %d, leading adverbials attached %d, events with a verb lemma (surface kept) %d" % (d["change_clauses"], d["via_topic_clauses"], d["adverbials_attached"], d["verb_events_with_surface"]), "", "F0 reasons:", "", "| reason | clauses | share of F0 | share of all clauses |", "|---|---|---|---|"]
        for k, v in sorted(d["f0_reason"].items(), key=lambda kv: (-kv[1], kv[0])):
            L.append("| %s | %d | %s | %s |" % (k, v, pct(v, d["shape"]["F0"]), pct(v, d["clauses"])))
        L.append("")
        if key == "meter_refusals":
            L += ["meter v1 refusal rows %d (reasons %s); the rows whose text is now a sentence of F1-F4 clauses only: %d (%s)" % (
                d["rows"], json.dumps(d["refusal_reasons"], ensure_ascii=False), d["rows_now_all_clauses_F1_F4"], pct(d["rows_now_all_clauses_F1_F4"], d["rows"])),
                  "by the loom's refusal reason: " + json.dumps(d["rows_by_refusal_reason"], ensure_ascii=False, sort_keys=True), ""]
        for k in sorted(d["f0_examples"]):
            L += ["F0 `%s` (first %d):" % (k, len(d["f0_examples"][k])), ""]
            L += ["- 「%s」%s" % (e["clause"], "" if e["detail"] is None else " [%s]" % e["detail"]) for e in d["f0_examples"][k]]
            L.append("")
    with open(os.path.join(HERE, "REPORT.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(L) + "\n")
    print("\n".join(L[:60]))


if __name__ == "__main__":
    main()
