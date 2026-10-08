"""T6x A grading: default read rule (query_crosses) vs query_share_crosses, on all 90 questions (S300 RUN).
Rule B (official, owner decision 2): answer = the path words (each path joined, paths separated by a line break);
correct iff a gold string occurs in them (+ the T0 core-in-subject check).  Rule A (reference): answer = the agreed centre.
A single (centre, paths) item is an answer; a list of differing items, UNKNOWN_*, AMBIGUOUS = abstention;
an unanswerable question (fict / attr) answered = wrong.  Same grader as t6w (experiments/line3/grade.py).
"""
import collections
import json
import os
import statistics
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
sys.path.insert(0, os.path.join(ROOT, "experiments", "line3"))
import grade as G                                              # noqa: E402

RULES = ["query_crosses", "query_share_crosses"]
D = {}
for rule in RULES:
    D[rule] = sorted((json.loads(l) for l in open(os.path.join(HERE, "results", "S300_RUN_%s.jsonl" % rule), encoding="utf-8")),
                     key=lambda r: r["id"])
L = []


def out(s=""):
    L.append(s)
    print(s)


verdict = lambda r: r["answer"].get("verdict")
items = lambda r: r["answer"].get("items", [])
path_texts = lambda it: ["".join(p["words"]) for p in it["paths"]]
golds = lambda r: [x.casefold() for x in r["gold"].split("|") if x]
text_A = lambda r: items(r)[0]["centre"] if verdict(r) == "ANSWER" else ""
text_B = lambda r: "\n".join(path_texts(items(r)[0])) if verdict(r) == "ANSWER" else ""


def graded(rows, textf, subject_check=True):
    g = []
    for r in rows:
        cls = G.classify(verdict(r))
        subj = r["subject"] if subject_check else r["subject"] + (r["core"] or "")
        gr, hit, sok = G.grade(cls, r["core"], textf(r), subj, r["gold"])
        g.append(dict(qid=r["id"], kind=r["kind"], cls=cls, grade=gr, gold_hit=hit))
    return g


def gold_in_any_path(r):
    return any(g in t.casefold() for g in golds(r) for it in items(r) for t in path_texts(it))


out("## T6x A (S300 RUN, default space V2, V3 adoption, official answer object; 90 fixed questions; search budget 64/8; level mid)")
out()
out("(1) strict grading, T0 grader (answerable a01..a60; unanswerable = fict + attr, answered = wrong)")
out()
out("| read rule | grading | correct/wrong/abstain (answerable) | unanswerable answered (fict+attr) | verdicts of the answer |")
out("|---|---|---|---|---|")
for rule in RULES:
    rows = D[rule]
    vc = collections.Counter(verdict(r) for r in rows)
    vcs = dict(sorted(("None" if k is None else k, v) for k, v in vc.items()))
    for name, f, sc in (("B official (path words)", text_B, True), ("B without core-in-subject check", text_B, False),
                        ("A reference (centre)", text_A, True)):
        t = G.tally(graded(rows, f, sc))
        out("| %s | %s | %d/%d/%d | %d+%d = %d | %s |" % (rule, name, t["correct"], t["wrong"], t["abstain"], t["fict_answered"],
                                                          t["attr_answered"], t["answered_unanswerable"], vcs))
out()
out("(2) gold in the path words (answerable, 60) and question dependence (gold of question i against the path words of j)")
out()
out("| read rule | with a read-out | gold in some path (any item) | gold in some centre | single-item answers | single-item with gold | matched hit | mismatched hit (mean fraction) | ratio |")
out("|---|---|---|---|---|---|---|---|---|")
for rule in RULES:
    rows = D[rule]
    A = [r for r in rows if r["id"].startswith("a")]
    W = [r for r in A if items(r)]
    single = [r for r in W if verdict(r) == "ANSWER"]
    words = {r["id"]: [t.casefold() for it in items(r) for t in path_texts(it)] for r in W}
    gl = {r["id"]: golds(r) for r in W}
    m = sum(any(g in t for g in gl[r["id"]] for t in words[r["id"]]) for r in W)
    mm = [sum(any(g in t for g in gl[q["id"]] for t in words[r["id"]]) for q in W if q["id"] != r["id"]) / max(len(W) - 1, 1) for r in W]
    mf, xf = m / len(W), sum(mm) / len(mm)
    out("| %s | %d | %d | %d | %d | %d | %d/%d (%.2f) | %.3f | %s |" % (
        rule, len(W), sum(gold_in_any_path(r) for r in W),
        sum(any(g in it["centre"].casefold() for g in golds(r) for it in items(r)) for r in W),
        len(single), sum(gold_in_any_path(r) for r in single), m, len(W), mf, xf, ("%.1f" % (mf / xf)) if xf else "inf"))
out()
out("(3) verdict mix over the 90 questions (cycle verdict -> answer verdict), crosses read, time")
out()
out("| read rule | cycle verdicts | answer verdicts | crosses read min/median/max | per-question secs median/max/sum (8 workers) | trace 100% |")
out("|---|---|---|---|---|---|")
for rule in RULES:
    rows = D[rule]
    cv = dict(sorted(collections.Counter(r["cycle"]["verdict"] for r in rows).items()))
    av = dict(sorted(collections.Counter("None" if verdict(r) is None else verdict(r) for r in rows).items()))
    cr = [r["crosses_read"] for r in rows]
    st = [r["secs_total"] for r in rows]
    tr = [r["trace_ok"] for r in rows if "trace_ok" in r]
    out("| %s | %s | %s | %d/%s/%d | %.1f/%.1f/%.0f | %d/%d |" % (rule, cv, av, min(cr), statistics.median(cr), max(cr),
                                                                  statistics.median(st), max(st), sum(st), sum(tr), len(tr)))
out()
a, b = {r["id"]: r for r in D[RULES[0]]}, {r["id"]: r for r in D[RULES[1]]}
nostate = [q for q in a if a[q]["states_adopted"] == 0]
out("(4) the %d questions without an adopted state under the default: what the share rule does" % len(nostate))
out()
out("| default cycle verdict | n | share rule: still no state | share rule: answer verdict mix | gold in path (answerable, with read-out) |")
out("|---|---|---|---|---|")
for v in sorted({a[q]["cycle"]["verdict"] for q in nostate}):
    qs = [q for q in nostate if a[q]["cycle"]["verdict"] == v]
    mix = collections.Counter("no state: " + b[q]["cycle"]["verdict"] if b[q]["states_adopted"] == 0 else verdict(b[q]) for q in qs)
    ans = [q for q in qs if q.startswith("a") and items(b[q])]
    out("| %s | %d | %d | %s | %d/%d |" % (v, len(qs), sum(1 for q in qs if b[q]["states_adopted"] == 0), dict(mix),
                                          sum(gold_in_any_path(b[q]) for q in ans), len(ans)))
chg = [q for q in a if a[q]["states_adopted"] > 0 and (verdict(a[q]), json.dumps(items(a[q]), sort_keys=True)) != (verdict(b[q]), json.dumps(items(b[q]), sort_keys=True))]
out()
out("Questions that HAD a state under the default and whose answer changed under the share rule: %d / %d" % (len(chg), 90 - len(nostate)))
out()
out("(5) crosses read: extra crosses of group 2 per question (share rule), min/median/max: %s; questions with 0 extra: %d" % (
    "/".join(str(x) for x in (lambda xs: (min(xs), statistics.median(xs), max(xs)))([r["crosses_by_group"].get("shares_sentence_with_query_unit", 0) for r in D[RULES[1]]])),
    sum(1 for r in D[RULES[1]] if r["crosses_by_group"].get("shares_sentence_with_query_unit", 0) == 0)))
out()
out("(6) examples")
out()
ex = []
for q in nostate:
    r = b[q]
    if q.startswith("a") and items(r) and gold_in_any_path(r) and verdict(r) == "ANSWER":
        ex.append(q)
for q in nostate:
    r = b[q]
    if q.startswith("a") and items(r) and not gold_in_any_path(r) and len(ex) < 3:
        ex.append(q)
for q in [x for x in a if a[x]["states_adopted"] > 0 and x.startswith("a") and verdict(b[x]) == "ANSWER"][:1]:
    ex.append(q)
for q in ex[:4]:
    r = b[q]
    out("- **%s** `%s` gold=%s subject=%s | default: %s -> share: %s / %s, %d item(s), %d crosses read" % (
        q, r["question"], r["gold"], r["subject"], a[q]["cycle"]["verdict"], r["cycle"]["verdict"], verdict(r), len(items(r)), r["crosses_read"]))
    for it in items(r)[:1]:
        out("    - reference centre: %s" % it["centre"])
        sents = r["answer"].get("sentences", {})
        for p in it["paths"]:
            out("        - section %d (question unit %s): %s" % (p["section"], p["attached"], " / ".join(p["words"])))
        out("        - source sentences (sid: units): %s" % "; ".join("%s: %s" % (k, v[:50]) for k, v in list(sents.items())[:3]))
open(os.path.join(HERE, "results", "summary_A.md"), "w", encoding="utf-8").write("\n".join(L) + "\n")
