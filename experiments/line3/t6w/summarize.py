"""T6w grading of results/S300_RUN_new_defaults.jsonl with experiments/line3/grade.py (T0 grader 7.2).

Rule A: the answer string = the agreed centre unit (core must be in the subject, gold in the centre).
Rule B: the answer string = the words of the section paths (each path joined, paths separated, so a gold
        string cannot span two paths); correct iff a gold string occurs in them (and the core is in the
        subject, as the T0 grader requires; the no-subject-check count is also given).
In both: only a single (centre, paths) item is an answer; a list of differing items, UNKNOWN_*,
AMBIGUOUS = abstention; an unanswerable question (fict / attr) answered = wrong.
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

SRC = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "results", "S300_RUN_new_defaults.jsonl")
rows = sorted((json.loads(l) for l in open(SRC, encoding="utf-8")), key=lambda r: r["id"])
T0 = json.load(open(os.path.join(ROOT, "experiments/line3/results/base_300.json")))
L = []


def out(s=""):
    L.append(s)
    print(s)


def verdict(r):
    return r["answer"].get("verdict")


def items(r):
    return r["answer"].get("items", [])


def path_texts(it):
    return ["".join(p["words"]) for p in it["paths"]]


def text_A(r):
    return items(r)[0]["centre"] if verdict(r) == "ANSWER" else ""


def text_B(r):
    return "\n".join(path_texts(items(r)[0])) if verdict(r) == "ANSWER" else ""


def graded(textf, subject_check=True):
    g = []
    for r in rows:
        cls = G.classify(verdict(r))
        subj = r["subject"] if subject_check else r["subject"] + (r["core"] or "")
        gr, hit, sok = G.grade(cls, r["core"], textf(r), subj, r["gold"])
        g.append(dict(qid=r["id"], kind=r["kind"], cls=cls, grade=gr, gold_hit=hit))
    return g


def golds(r):
    return [x.casefold() for x in r["gold"].split("|") if x]


out("## T6w results (S300 RUN, new defaults V1+V2+V3, new answer form; 90 fixed questions; search budget 64/8; level mid)")
out()
out("(1) strict grading, T0 grader (answerable a01..a60; unanswerable = fict + attr, answered = wrong)")
out()
out("| system | correct/wrong/abstain (answerable) | unanswerable answered (fict+attr) | of which wrong | answer verdicts |")
out("|---|---|---|---|---|")
for p in ("a1", "a2"):
    t = G.tally([r for r in T0["rows"] if r["path"] == p and r["qid"] != "id"])
    out("| T0 legacy %s | %d/%d/%d | %d+%d | %d | - |" % (p, t["correct"], t["wrong"], t["abstain"], t["fict_answered"],
                                                     t["attr_answered"], t["answered_unanswerable"]))
vc = collections.Counter(verdict(r) for r in rows)
vcs = dict(sorted(("None" if k is None else k, v) for k, v in vc.items()))
for name, f, sc in (("T6w rule A (answer = agreed centre unit)", text_A, True),
                    ("T6w rule B (answer counts if gold in the path words)", text_B, True),
                    ("T6w rule B without the core-in-subject check", text_B, False)):
    t = G.tally(graded(f, sc))
    out("| %s | %d/%d/%d | %d+%d | %d | %s |" % (name, t["correct"], t["wrong"], t["abstain"], t["fict_answered"],
                                                  t["attr_answered"], t["answered_unanswerable"], vcs))
out()
A = [r for r in rows if r["id"].startswith("a")]
W = [r for r in A if items(r)]
by_title = collections.defaultdict(list)
for l in open(os.path.join(ROOT, "experiments/line3/data/S300.jsonl"), encoding="utf-8"):
    j = json.loads(l)
    by_title[j["title"]].append(j["sent"])
held = sum(1 for r in A if any(g and any(g in s for s in by_title.get(r["subject"], [])) for g in r["gold"].split("|")))


def gold_in_any_path(r):
    return any(g in t.casefold() for g in golds(r) for it in items(r) for t in path_texts(it))


def gold_in_centre(r):
    return any(g in it["centre"].casefold() for g in golds(r) for it in items(r))


out("(2) diagnostic: gold in the answer, answerable questions (60)")
out()
out("| answerable | with an adopted state / read-out | gold in some path (any item) | gold in some centre (any item) | single-item answers | single-item with gold in its paths | gold held in the subject's sentences |")
out("|---|---|---|---|---|---|---|")
single = [r for r in W if verdict(r) == "ANSWER"]
out("| %d | %d | %d | %d | %d | %d | %d |" % (len(A), len(W), sum(gold_in_any_path(r) for r in W), sum(gold_in_centre(r) for r in W),
                                              len(single), sum(gold_in_any_path(r) for r in single), held))
out()
# question dependence
out("(3) question dependence: gold of question i against the path words of question j (answerable questions with a read-out)")
out()
words = {r["id"]: [t.casefold() for it in items(r) for t in path_texts(it)] for r in W}
gl = {r["id"]: golds(r) for r in W}
m = sum(any(g in t for g in gl[r["id"]] for t in words[r["id"]]) for r in W)
mm = [sum(any(g in t for g in gl[q["id"]] for t in words[r["id"]]) for q in W if q["id"] != r["id"]) / max(len(W) - 1, 1) for r in W]
mf, xf = m / len(W), sum(mm) / len(mm)
out("| matched hit (i = j) | mismatched hit, mean fraction per read-out (i != j) | ratio |")
out("|---|---|---|")
out("| %d / %d (%.2f) | %.3f | %s |" % (m, len(W), mf, xf, ("%.1f" % (mf / xf)) if xf else "inf"))
sets = {tuple(sorted(("|".join(map(str, [it["centre"]] + path_texts(it))) for it in items(r)))) for r in W}
out()
out("Distinct answers (centre + path words, whole answer) across the %d read-outs of answerable questions: %d. Distinct centres: %d." % (
    len(W), len(sets), len({it["centre"] for r in W for it in items(r)})))
out()
out("(4) list sizes, time")
out()
ni = [len(items(r)) for r in rows if items(r)]
ns = [r["states_adopted"] for r in rows if r["states_adopted"]]
f = lambda xs: "%d/%s/%d" % (min(xs), statistics.median(xs), max(xs))
out("- questions: %d; with a read-out: %d (ANSWER %d, list/CHOICE %d, UNKNOWN_NO_PATH %d); no adopted state: %d (cycle verdicts of those: %s)" % (
    len(rows), len(ni), vc.get("ANSWER", 0), vc.get("CHOICE", 0), vc.get("UNKNOWN_NO_PATH", 0), sum(1 for r in rows if not r["states_adopted"]),
    dict(collections.Counter(r["cycle"]["verdict"] for r in rows if not r["states_adopted"]))))
out("- items per answer (distinct (centre, paths)) min/median/max: %s; adopted states per question min/median/max: %s" % (f(ni), f(ns)))
lst = [len(items(r)) for r in rows if verdict(r) == "CHOICE"]
out("- list sizes (CHOICE answers only) min/median/max: %s; too_many flagged: %d" % (f(lst) if lst else "-", sum(1 for r in rows if r["answer"].get("too_many"))))
tr = [r["trace"] for r in rows if "trace" in r]
out("- trace check: %d / %d read-outs 100%% (words traced %d / %d); failures: %d" % (
    sum(r["trace_ok"] for r in rows if "trace" in r), len(tr), sum(t["words_traced"] for t in tr), sum(t["words_checked"] for t in tr),
    sum(t["n_failures"] for t in tr)))
st = [r["secs_total"] for r in rows]
out("- per-question time (s, ask + read-out + trace, one process, 9 questions running in parallel on 10 cores) min/median/max/sum: %.2f / %.2f / %.2f / %.1f" % (
    min(st), statistics.median(st), max(st), sum(st)))
out("- crosses read per question min/median/max: %s" % f([r["crosses_read"] for r in rows]))
out()
out("(5) answer examples (S300 RUN)")
out()
hits = [r for r in single if gold_in_any_path(r)]
miss = [r for r in single if not gold_in_any_path(r)]
lists = [r for r in rows if verdict(r) == "CHOICE" and gold_in_any_path(r)]
lmiss = [r for r in rows if verdict(r) == "CHOICE" and r["id"].startswith("a") and not gold_in_any_path(r)]
pick = hits[:2] + miss[:1] + lists[:1] + lmiss[:1]
for r in pick:
    out("- **%s** `%s`  gold = %s  subject = %s  | cycle: %s %s | answer: %s, %d item(s)" % (
        r["id"], r["question"], r["gold"], r["subject"], r["cycle"]["verdict"], r["cycle"]["units"], verdict(r), len(items(r))))
    for it in items(r)[:2]:
        out("    - centre **%s**" % it["centre"])
        for p in it["paths"]:
            out("        - section %d (question unit %s): %s" % (p["section"], p["attached"], " / ".join(p["words"])))
    if len(items(r)) > 2:
        out("    - ... %d more items" % (len(items(r)) - 2))
open(os.path.join(HERE, "results", "summary.md"), "w", encoding="utf-8").write("\n".join(L) + "\n")
