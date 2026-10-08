#!/usr/bin/env python3
"""T2: realize the 100 typed crosses of t2_pool.jsonl with the placement r9 and read every REALIZED sentence again.

The independent reread is done HERE (semantic_read.read + build_crosses with the same placement) and compares the five things of K312 with its own
code; it does not use the product's `checks`, `_reread_check` or `_facts_diff`. The reference is the pool row's own clause dict (read from the ORIGINAL
text), never the product's internal copy. Run with VERA_PLACEMENT / VERA_REALIZE_FORMS unset.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import unicodedata
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
for _v in ("VERA_PLACEMENT", "VERA_REALIZE_FORMS"):
    if os.environ.get(_v):
        sys.exit("refusing to run with %s set" % _v)

ROLE_FIX = {}  # the pool clause dicts and the rereads both use the observed role names (agent, place, source, ...): no renaming is needed


def n(x):
    return unicodedata.normalize("NFKC", x) if isinstance(x, str) else x


def reference(clause):
    return {"predicate": n(clause["predicate"]), "polarity": clause["polarity"], "tense": clause["tense"],
            "roles": {r: n(s) for r, s in clause["roles"].items()}}


def independent_reread(text, placement):
    from verantyx import event_cross, semantic_read

    try:
        out = semantic_read.read(text, "ja", placement=placement)
        got = event_cross.build_crosses(out, event_cross.default_lookup(placement))
    except Exception as exc:
        return None, "READ_ERROR:" + type(exc).__name__
    if got.status != "CROSSED":
        return None, "NOT_CROSSED:" + got.status
    if len(got.crosses) != 1:
        return None, "NOT_ONE_CROSS:%d" % len(got.crosses)
    c = got.crosses[0].to_dict()
    roles = {}
    for role, arm in c["arms"].items():
        surfaces = [f["surface"] for f in arm["fillers"]]
        if len(surfaces) != 1:
            return None, "ARM_NOT_SINGLE:" + role
        roles[role] = n(surfaces[0])
    return {"predicate": n(c["center"]["predicate"]), "polarity": c["center"]["polarity"], "tense": c["center"]["tense"], "roles": roles}, None


def compare(ref, got):
    diffs = []
    if set(ref["roles"]) != set(got["roles"]):
        diffs.append("role_set")
    for r in set(ref["roles"]) & set(got["roles"]):
        if ref["roles"][r] != got["roles"][r]:
            diffs.append("filler:" + r)
    for k in ("polarity", "tense", "predicate"):
        if ref[k] != got[k]:
            diffs.append(k)
    return diffs


def first_word(detail):
    """The head of a refusal detail: the first two ':' parts of a REREAD_MISMATCH, else the first four words."""
    d = str(detail or "")
    if d.startswith("REREAD_MISMATCH"):
        return ":".join(d.split(":")[:2])
    return " ".join(d.split(" ")[:4])


def topic_of(text, agent):
    for t in ("は", "が"):
        if text.startswith(n(agent) + t) or text.startswith(agent + t):
            return t
    return "?"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pool", required=True)
    ap.add_argument("--placement", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--summary", required=True)
    args = ap.parse_args()
    from verantyx import cross_tokens, semantic_read, semantic_realize as SR

    rows = [json.loads(l) for l in Path(args.pool).read_text(encoding="utf-8").splitlines() if l.strip()]
    summ = {"rows": len(rows)}
    results = []
    counters = {k: Counter() for k in ("plain_status", "plain_reasons", "plain_topic", "tokens_status", "tokens_reasons", "polite_status", "polite_reasons",
                                       "polite_topic")}
    bad = {"plain": 0, "tokens": 0, "polite": 0}
    unread = {"plain": 0, "tokens": 0, "polite": 0}
    agree_plain_tokens = Counter()
    for row in rows:
        clause, ref = row["clause"], reference(row["clause"])
        # M1 (review r1): the dict path does not know the reader rule, the caller passes it. It is read from the ORIGINAL text with the same placement
        # (clause_meta[0].rule); the pool itself is frozen and is not rebuilt.
        meta = semantic_read.read(row["text"], "ja", placement=args.placement)["clause_meta"]
        assert len(meta) == 1
        clause = dict(clause, rule=meta[0]["rule"])
        rec = {"text": row["text"], "sha": row["sha"]}
        plain = SR.realize_clause(clause, "plain", placement=args.placement)
        polite = SR.realize_clause(clause, "polite", placement=args.placement)
        tok = cross_tokens.realize_tokens(row["tokens"], "ja", placement=args.placement)
        for label, res in (("plain", plain), ("polite", polite)):
            if isinstance(res, SR.Realized):
                counters[label + "_status"]["REALIZED"] += 1
                got, why = independent_reread(res.text, args.placement)
                diffs = [why] if got is None else compare(ref, got)
                rec[label] = {"status": "REALIZED", "text": res.text, "independent_diffs": diffs,
                              "topic_attempts": res.checks.get("topic_attempts")}
                counters[label + "_topic"][topic_of(res.text, clause["roles"]["agent"])] += 1
                if got is None:
                    unread[label] += 1
                if diffs:
                    bad[label] += 1
            else:
                counters[label + "_status"]["REFUSED"] += 1
                reason = res.reason + "/" + first_word(res.detail)
                counters[label + "_reasons"][reason] += 1
                rec[label] = {"status": "REFUSED", "reason": res.reason, "detail": res.detail}
        if tok["status"] == "REALIZED":
            counters["tokens_status"]["REALIZED"] += 1
            got, why = independent_reread(tok["text"], args.placement)
            diffs = [why] if got is None else compare(ref, got)
            rec["tokens"] = {"status": "REALIZED", "text": tok["text"], "independent_diffs": diffs}
            if got is None:
                unread["tokens"] += 1
            if diffs:
                bad["tokens"] += 1
        else:
            counters["tokens_status"][tok["status"]] += 1
            counters["tokens_reasons"][str(tok.get("reason")) + "/" + first_word(tok.get("detail"))] += 1
            rec["tokens"] = {"status": tok["status"], "reason": tok.get("reason"), "detail": tok.get("detail")}
        pt = rec.get("plain", {}).get("text"), rec.get("tokens", {}).get("text")
        agree_plain_tokens["both_realized_same_text" if pt[0] and pt[0] == pt[1] else "both_realized_different_text" if pt[0] and pt[1] else "not_both"] += 1
        results.append(rec)
    summ.update({
        "plain_realized": counters["plain_status"]["REALIZED"], "plain_refused": counters["plain_status"]["REFUSED"],
        "plain_refusal_reasons": dict(sorted(counters["plain_reasons"].items())),
        "plain_topic_of_realized": dict(sorted(counters["plain_topic"].items())),
        "plain_independent_reread_mismatch_among_realized": bad["plain"], "plain_independent_reread_unreadable_among_realized": unread["plain"],
        "tokens_status": dict(sorted(counters["tokens_status"].items())),
        "tokens_refusal_reasons": dict(sorted(counters["tokens_reasons"].items())),
        "tokens_independent_reread_mismatch_among_realized": bad["tokens"], "tokens_independent_reread_unreadable_among_realized": unread["tokens"],
        "plain_vs_tokens_text": dict(agree_plain_tokens),
        "polite_reference": {"realized": counters["polite_status"]["REALIZED"], "refused": counters["polite_status"]["REFUSED"],
                             "refusal_reasons": dict(sorted(counters["polite_reasons"].items())),
                             "topic_of_realized": dict(sorted(counters["polite_topic"].items())),
                             "independent_reread_mismatch_among_realized": bad["polite"], "unreadable_among_realized": unread["polite"]},
    })
    Path(args.out).write_text("".join(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n" for r in results), encoding="utf-8")
    Path(args.summary).write_text(json.dumps(summ, ensure_ascii=False, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summ, ensure_ascii=False, indent=1, sort_keys=True))
    return 0 if bad["plain"] == 0 and bad["tokens"] == 0 and bad["polite"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
