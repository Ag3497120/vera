#!/usr/bin/env python3
"""route_log と ask_log を集計する（標準出力に JSON 1 つ）。

影運用の間、この集計で判断を変えない。昇格の条件は表示するだけで、昇格は監査役・オーナーが決める。
各分類の和が total_entries と合わなければ rc=2（見えない落ち方を作らない）。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROUTE_CLASSES = ("route", "undecided", "not_called", "error")
ASK_CLASSES = ("answer", "answer_untraced", "abstain", "unclassified_output", "error")
ROUTE_ABSTAIN = ("undecided", "not_called")
ASK_ABSTAIN = ("abstain",)
ROUTE_V = ("agree", "disagree")
ASK_V = ("correct", "wrong")
# 事前登録（docs/OPS_SHADOW.md）: 連続を切るもの
ROUTE_BREAK_V = "disagree"
ASK_BREAK_V = "wrong"
ASK_BREAK_CLASSES = ("answer_untraced", "unclassified_output")


class SumMismatch(Exception):
    pass


def read_log(path):
    entries, verdict_rows, bad, unknown = [], [], [], []
    p = Path(path)
    if not p.is_file():
        return entries, verdict_rows, bad, unknown, False
    with open(p, encoding="utf-8") as f:
        for i, ln in enumerate(f, 1):
            if not ln.strip():
                continue
            try:
                d = json.loads(ln)
            except Exception:
                bad.append(i)
                continue
            if not isinstance(d, dict):
                bad.append(i)
            elif d.get("type") == "entry":
                entries.append(d)
            elif d.get("type") == "verdict":
                verdict_rows.append(d)
            else:
                unknown.append(i)
    return entries, verdict_rows, bad, unknown, True


def inc(d, k):
    d[k] = d.get(k, 0) + 1


def summarize(kind, path, n):
    classes = ROUTE_CLASSES if kind == "route" else ASK_CLASSES
    abstain = ROUTE_ABSTAIN if kind == "route" else ASK_ABSTAIN
    vals = ROUTE_V if kind == "route" else ASK_V
    entries, vrows, bad, unknown, present = read_log(path)
    ids = {e.get("entry_id") for e in entries}
    by_ref, invalid, orphan = {}, 0, 0
    for r in vrows:
        if r.get("ref") not in ids:
            orphan += 1
            continue
        if r.get("verdict") not in vals:
            invalid += 1
            continue
        by_ref.setdefault(r["ref"], []).append(r["verdict"])
    by_class = {c: 0 for c in classes}
    other = {}
    verd = {vals[0]: 0, vals[1]: 0, "pending": 0, "verdict_conflict": 0, "verdict_on_abstain": 0,
            "abstain_unjudged": 0, "error_entries": 0}
    by_reason, by_abs, by_source, by_status = {}, {}, {}, {}
    run = best = 0
    for e in entries:
        c = e.get("shadow_class")
        if c in by_class:
            by_class[c] += 1
        else:
            inc(other, str(c))
        vs = list(by_ref.get(e.get("entry_id"), []))
        m = e.get("verdict")
        if m is not None:
            if m in vals:
                vs.append(m)
            else:
                invalid += 1
        distinct = sorted(set(vs))
        state = "pending" if not distinct else distinct[0] if len(distinct) == 1 else "verdict_conflict"
        v = e.get("vera") or {}
        if kind == "route":
            inc(by_source, str(e.get("task_source")))
            inc(by_status, str(e.get("task_status")))
            if c == "undecided":
                inc(by_reason, str(v.get("undecided_reason")))
                inc(by_abs, str(v.get("abstention_type")))
        elif c == "abstain":
            t = ("SOVEREIGN_" + str((e.get("sovereign") or {}).get("state"))) if not v.get("called") else str(v.get("verdict"))
            inc(by_abs, t)
        if c in abstain:
            verd["verdict_on_abstain" if distinct else "abstain_unjudged"] += 1
            continue  # 棄権は連続に数えず、途切れさせもしない
        if c == "error":
            verd["error_entries"] += 1
            continue
        verd[state] += 1
        brk = state == "verdict_conflict" or (
            state == (ROUTE_BREAK_V if kind == "route" else ASK_BREAK_V)
            or (kind == "ask" and c in ASK_BREAK_CLASSES))
        if brk:
            run = 0
        elif state in vals:
            run += 1
            best = max(best, run)
    total = len(entries)
    if sum(by_class.values()) != total or sum(verd.values()) != total:
        raise SumMismatch(f"{kind}: classes={sum(by_class.values())} verdicts={sum(verd.values())} total={total}")
    if bad:
        ok, why = False, "UNPARSEABLE_LINES"
    elif run >= n:
        ok, why = True, "STREAK_AT_LEAST_N"
    else:
        ok, why = False, "STREAK_BELOW_N"
    out = {"log": str(path), "log_present": present, "total_entries": total, "by_class": by_class,
           "verdicts": verd, "streak": run, "max_streak": best,
           "eligible_for_promotion": {"eligible": ok, "reason": why, "n": n, "streak": run,
                                      "n_basis": "policy value, not measured"},
           "verdict_rows": len(vrows), "orphan_verdict_rows": orphan, "invalid_verdict_values": invalid,
           "unparseable_lines": bad, "unknown_type_lines": unknown, "unknown_classes": other}
    if kind == "route":
        out.update(by_undecided_reason=by_reason, by_abstention_type=by_abs, by_task_source=by_source,
                   by_task_status=by_status)
    else:
        out.update(by_abstain_type=by_abs)
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--route-log", required=True)
    ap.add_argument("--ask-log", required=True)
    ap.add_argument("--n", type=int, default=30)
    a = ap.parse_args(argv)
    try:
        res = {"route": summarize("route", a.route_log, a.n), "ask": summarize("ask", a.ask_log, a.n)}
    except SumMismatch as e:
        print(json.dumps({"verdict": "SUM_MISMATCH", "detail": str(e)}))
        return 2
    print(json.dumps(res, sort_keys=True, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
