"""T6z grading of results/S300_RUN_t6z_defaults.jsonl (new defaults: merge_sections, similar=word_set, on-demand raise).
Rule B (official): answer = the word set of the single entry (one word per line); correct iff a gold string is in it
(+ T0 core-in-subject); a list of >= 2 entries / UNKNOWN / AMBIGUOUS = abstention; unanswerable answered = wrong.
Rule A (reference): answer = the reference centre(s) of the single entry.
Sensitivity row B': answer text = every arrangement's path texts (each path joined, as T6w..T6y) instead of the word set.
Same T0 grader (experiments/line3/grade.py)."""
import collections
import json
import os
import statistics
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
sys.path.insert(0, os.path.join(ROOT, "experiments", "line3"))
import grade as G                                              # noqa: E402

rows = sorted((json.loads(l) for l in open(os.path.join(HERE, "results", "S300_RUN_t6z_defaults.jsonl"), encoding="utf-8")),
              key=lambda r: r["id"])
L = []


def out(s=""):
    L.append(s)
    print(s)


verdict = lambda r: r["answer"].get("verdict")
entries = lambda r: r["answer"].get("entries", [])
golds = lambda r: [x.casefold() for x in r["gold"].split("|") if x]
arr_texts = lambda e: ["".join(p["words"]) for a in e["arrangements"] for p in a["paths"]]
text_B = lambda r: "\n".join(entries(r)[0]["words"]) if verdict(r) == "ANSWER" else ""
text_Bp = lambda r: "\n".join(dict.fromkeys(arr_texts(entries(r)[0]))) if verdict(r) == "ANSWER" else ""
text_A = lambda r: "\n".join(entries(r)[0]["centres"]) if verdict(r) == "ANSWER" else ""


def graded(textf):
    g = []
    for r in rows:
        cls = G.classify(verdict(r))
        gr, hit, sok = G.grade(cls, r["core"], textf(r), r["subject"], r["gold"])
        g.append(dict(qid=r["id"], kind=r["kind"], cls=cls, grade=gr, gold_hit=hit))
    return g


gold_arr = lambda r: any(g in t.casefold() for g in golds(r) for e in entries(r) for t in arr_texts(e))
gold_word = lambda r: any(g in w.casefold() for g in golds(r) for e in entries(r) for w in e["words"])
gold_set = lambda r: any(g in "".join(e["words"]).casefold() for g in golds(r) for e in entries(r))

out("## T6z results (S300 RUN; new defaults merge_sections + similar=word_set + on-demand budget raise; 90 fixed questions; search budget 64/8; level mid)")
out()
out("(1) strict grading, T0 grader (answerable a01..a60; unanswerable = fict + attr, answered = wrong)")
out()
out("| system | correct/wrong/abstain (answerable) | unanswerable answered (fict+attr) | answer verdicts |")
out("|---|---|---|---|")
out("| T0 legacy a1 | 45/7/8 | 3+8 = 11 | - |")
out("| T0 legacy a2 | 44/9/7 | 0+10 = 10 | - |")
out("| T6w rule B (path words; no merge) | 17/3/40 | 2+2 = 4 | ANSWER 24, CHOICE 18, none 48 |")
out("| T6w rule A (centre) | 2/18/40 | 2+2 = 4 | same |")
out("| T6y rule B (merge_sections, option) | 18/3/39 | 2+2 = 4 | ANSWER 25, CHOICE 17, none 48 |")
vc = collections.Counter("None" if verdict(r) is None else verdict(r) for r in rows)
vcs = dict(sorted(vc.items()))
for name, f in (("T6z rule B official (word set of the entry)", text_B), ("T6z rule B' (arrangements' path texts)", text_Bp),
                ("T6z rule A reference (centre)", text_A)):
    t = G.tally(graded(f))
    out("| %s | %d/%d/%d | %d+%d = %d | %s |" % (name, t["correct"], t["wrong"], t["abstain"], t["fict_answered"], t["attr_answered"],
                                                 t["answered_unanswerable"], vcs))
tB = graded(text_B)
out()
out("T6z rule B per-question outcome changes vs T6y/T6x-default are listed in (6).")
out()
W = [r for r in rows if r["id"].startswith("a") and entries(r)]
A60 = [r for r in rows if r["id"].startswith("a")]
S = [r for r in W if verdict(r) == "ANSWER"]
out("(2) gold in the answer, answerable (60)")
out()
words = {r["id"]: [t.casefold() for e in entries(r) for t in arr_texts(e)] for r in W}
wsets = {r["id"]: ["".join(e["words"]).casefold() for e in entries(r)] for r in W}
gl = {r["id"]: golds(r) for r in W}
m_arr = sum(gold_arr(r) for r in W)
mm = [sum(any(g in t for g in gl[q["id"]] for t in words[r["id"]]) for q in W if q["id"] != r["id"]) / max(len(W) - 1, 1) for r in W]
m_w = sum(gold_set(r) for r in W)
mmw = [sum(any(g in t for g in gl[q["id"]] for t in wsets[r["id"]]) for q in W if q["id"] != r["id"]) / max(len(W) - 1, 1) for r in W]
out("| answerable | with a read-out | gold in some arrangement's path text | gold in the word sets (joined) | gold as a part of some word | single-entry answers | single-entry with gold (word set) | single-entry with gold (arrangement path text) |")
out("|---|---|---|---|---|---|---|---|")
out("| 60 | %d | %d | %d | %d | %d | %d | %d |" % (len(W), m_arr, m_w, sum(gold_word(r) for r in W), len(S),
                                                   sum(gold_set(r) for r in S), sum(gold_arr(r) for r in S)))
out()
out("Question dependence (gold of question i against the answers of question j, answerable with a read-out): arrangement path texts: matched %d/%d (%.2f), mismatched mean fraction %.3f, ratio %.1f; word sets: matched %d/%d (%.2f), mismatched %.3f, ratio %.1f" % (
    m_arr, len(W), m_arr / len(W), sum(mm) / len(mm), (m_arr / len(W)) / (sum(mm) / len(mm)) if sum(mm) else float("inf"),
    m_w, len(W), m_w / len(W), sum(mmw) / len(mmw), (m_w / len(W)) / (sum(mmw) / len(mmw)) if sum(mmw) else float("inf")))
out()
out("(3) list sizes (entries), collapse")
out()
allw = [r for r in rows if entries(r)]
ent_n = [len(entries(r)) for r in allw]
arr_n = [r["answer"]["arrangements"] for r in allw]
lists = [r for r in allw if r["answer"]["arrangements"] > 1]
coll = [r for r in lists if len(entries(r)) == 1]
out("- questions with a read-out: %d of 90 (ANSWER %d, list %d, UNKNOWN_NO_PATH %d); no adopted state: %d" % (
    len(allw), sum(verdict(r) == "ANSWER" for r in rows), sum(verdict(r) == "CHOICE" for r in rows),
    sum(verdict(r) == "UNKNOWN_NO_PATH" for r in rows), sum(r["states_adopted"] == 0 for r in rows)))
out("- arrangements (items after merge_sections) per question min/median/max: %d/%s/%d" % (min(arr_n), statistics.median(arr_n), max(arr_n)))
out("- entries per question min/median/max: %d/%s/%d" % (min(ent_n), statistics.median(ent_n), max(ent_n)))
cl = [len(entries(r)) for r in rows if verdict(r) == "CHOICE"]
out("- lists (CHOICE) entries min/median/max: %d/%s/%d; too_many flagged (>20): %d" % (min(cl), statistics.median(cl), max(cl), sum(x > 20 for x in cl)))
out("- lists before the word-set collapse (arrangements > 1): %d; collapse to ONE entry (an ANSWER): %d (%s); lists that stay: %d" % (
    len(lists), len(coll), ", ".join(r["id"] for r in coll), len(lists) - len(coll)))
out("- reduction arrangements -> entries over the lists that stay (sum): %d -> %d" % (
    sum(r["answer"]["arrangements"] for r in lists if len(entries(r)) > 1), sum(len(entries(r)) for r in lists if len(entries(r)) > 1)))
out("- stay-lists with gold in some arrangement path: %d of %d (answerable only: %d of %d)" % (
    sum(gold_arr(r) for r in lists if len(entries(r)) > 1), sum(len(entries(r)) > 1 for r in lists),
    sum(gold_arr(r) for r in lists if len(entries(r)) > 1 and r["id"].startswith("a")),
    sum(len(entries(r)) > 1 and r["id"].startswith("a") for r in lists)))
mx = [e["count"] for r in rows for e in entries(r)]
out("- arrangements per entry: max %d, entries with >1 arrangement: %d of %d; entries whose arrangements have different centres: %d" % (
    max(mx), sum(x > 1 for x in mx), len(mx), sum(len(e["centres"]) > 1 for r in rows for e in entries(r))))
out()
out("(4) on-demand budget raise, trace check, time")
out()
raised = [r for r in rows if r["budget_raise"] and r["budget_raise"]["needed"]]
out("- questions where a raise was needed: %d (%s); of those with a state afterwards: %s" % (
    len(raised), ", ".join(r["id"] for r in raised), ", ".join("%s(%s)" % (r["id"], r["answer"].get("verdict")) for r in raised if r["states_adopted"])))
tr = [r for r in rows if "trace_ok" in r]
out("- trace check: %d / %d read-outs 100%% (words traced %d / %d); failures: %d" % (
    sum(r["trace_ok"] for r in tr), len(tr), sum(r["trace"]["words_traced"] for r in tr), sum(r["trace"]["words_checked"] for r in tr),
    sum(len(r["trace"]["failures"]) for r in tr)))
st = [r["secs_total"] for r in rows]
out("- per-question time (s; ask incl. raise + read-out + trace; 9 workers in parallel) median/max/sum: %.2f/%.1f/%.0f; read-out+trace of the largest: %.1f" % (
    statistics.median(st), max(st), sum(st), max(r.get("secs_readout", 0) + r.get("secs_trace", 0) for r in rows)))
out()
out("(5) cycle verdict mix: %s" % dict(sorted(collections.Counter(r["cycle"]["verdict"] for r in rows).items())))
out()
out("(6) answerable questions whose rule B grade differs from T6x default (the T6w/T6x 17/3/40 run)")
prev = {}
for l in open(os.path.join(ROOT, "experiments/line3/t6x/results/S300_RUN_query_crosses.jsonl"), encoding="utf-8"):
    q = json.loads(l)
    cls = G.classify(q["answer"].get("verdict"))
    ptext = "\n".join("".join(p["words"]) for p in q["answer"]["items"][0]["paths"]) if q["answer"].get("verdict") == "ANSWER" else ""
    prev[q["id"]] = G.grade(cls, q["core"], ptext, q["subject"], q["gold"])[0]
out()
for g in tB:
    if g["qid"] in prev and prev[g["qid"]] != g["grade"]:
        out("- %s: %s -> %s" % (g["qid"], prev[g["qid"]], g["grade"]))
out()
out("(7) every list (arrangements -> entries; gold in some path: Y/N)")
out()
out("- " + ", ".join("%s %d->%d%s" % (r["id"], r["answer"]["arrangements"], len(entries(r)), ("Y" if gold_arr(r) else "N") if r["id"].startswith("a") else "") for r in lists))
open(os.path.join(HERE, "results", "summary.md"), "w", encoding="utf-8").write("\n".join(L) + "\n")
