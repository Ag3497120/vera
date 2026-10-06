"""T6 summary: tables from t6/results/*.jsonl -> t6/results/summary.md (and stdout)."""
import collections
import glob
import json
import os
import statistics
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE)))
import grade as G                                             # noqa: E402

COND = sys.argv[1] if len(sys.argv) > 1 else "S300"
LEVEL = sys.argv[2] if len(sys.argv) > 2 else "mid_64x8"
L = []
ROOT = HERE


def out(s=""):
    L.append(s)
    print(s)


T0 = json.load(open(os.path.join(os.path.dirname(HERE), "results", "base_%s.json" % COND[1:])))
base = {p: G.tally([r for r in T0["rows"] if r["path"] == p and r["qid"] != "id"]) for p in ("a1", "a2")}

data = {}
for tn in ("RUN", "WORD", "CHAR"):
    p = os.path.join(HERE, "results", "%s_%s_%s.jsonl" % (COND, tn, LEVEL))
    if os.path.exists(p):
        data[tn] = [json.loads(l) for l in open(p, encoding="utf-8")]

out("## 1. Strict grading (T0 grader, 7.2 rule; CHOICE/UNKNOWN = abstain)")
out()
out("| system | tier | questions | correct/wrong/abstain (answerable) | loose | unanswerable answered (fict+attr) | of which wrong |")
out("|---|---|---|---|---|---|---|")
for p in ("a1", "a2"):
    t = base[p]
    out("| T0 legacy %s | - | 90 | %d/%d/%d | %d | %d+%d | %d |" % (p, t["correct"], t["wrong"], t["abstain"], t["loose"],
                                                              t["fict_answered"], t["attr_answered"], t["answered_unanswerable"]))
for tn, rows in data.items():
    graded = [dict(qid=r["id"], kind=r["kind"], cls=r["strict"]["cls"], grade=r["strict"]["grade"],
                   gold_hit=r["strict"]["gold_hit"]) for r in rows]
    t = G.tally(graded)
    out("| T6 read-out (adopted candidate / list=abstain) | %s | %d | %d/%d/%d | %d | %d+%d | %d |" % (
        tn, len(rows), t["correct"], t["wrong"], t["abstain"], t["loose"], t["fict_answered"], t["attr_answered"],
        t["answered_unanswerable"]))
    g5 = []
    for r in rows:
        v = r["t5_verdict"]
        c = G.classify(v)
        text = "".join(r["t5_units"]) if v == "ANSWER" else ""
        subj = [x for x in open(os.path.join(os.path.dirname(HERE), "questions.tsv"), encoding="utf-8").read().split("\n")
                if x.startswith(r["id"] + "\t")][0].split("\t")[2]
        g, hit, sok = G.grade(c, r["strict"]["core"], text, subj, r["gold"])
        g5.append(dict(qid=r["id"], kind=r["kind"], cls=c, grade=g, gold_hit=hit))
    t = G.tally(g5)
    out("| (reference) T5 unit answer, same core | %s | %d | %d/%d/%d | %d | %d+%d | %d |" % (
        tn, len(rows), t["correct"], t["wrong"], t["abstain"], t["loose"], t["fict_answered"], t["attr_answered"],
        t["answered_unanswerable"]))
out()
out("Verdict counts (T5 unit verdict -> T6 read-out verdict):")
for tn, rows in data.items():
    c = collections.Counter((r["t5_verdict"], r["readout"]["verdict"]) for r in rows)
    out("- %s: %s" % (tn, dict(sorted((("%s->%s" % k), v) for k, v in c.items()))))

out()
out("## 2. Diagnostic: is the gold string anywhere in the read-out? (answerable questions a01..a60 only)")
out()
out("| tier | answerable | with an adopted state | gold in some candidate sentence | gold in some single section path | gold in the union of path words | gold held in the subject's sentences (T0 gold_held) |")
out("|---|---|---|---|---|---|---|")
by_title = collections.defaultdict(list)
for l in open(os.path.join(os.path.dirname(HERE), "data", COND + ".jsonl"), encoding="utf-8"):
    j = json.loads(l)
    by_title[j["title"]].append(j["sent"])
SUBJ = {x.split("\t")[0]: x.split("\t")[2] for x in open(os.path.join(os.path.dirname(HERE), "questions.tsv"), encoding="utf-8").read().split("\n")[1:] if x}
for tn, rows in data.items():
    A = [r for r in rows if r["id"].startswith("a")]
    W = [r for r in A if "diag" in r]
    held = sum(1 for r in A if any(g and any(g in s for s in by_title.get(SUBJ[r["id"]], [])) for g in r["gold"].split("|")))
    out("| %s | %d | %d | %d | %d | %d | %d |" % (tn, len(A), len(W), sum(r["diag"]["gold_in_sentence"] for r in W),
                                              sum(r["diag"]["gold_in_a_path"] for r in W),
                                              sum(r["diag"]["gold_in_path_words_union"] for r in W), held))
out()
out("## 3. Function-word paths")
out()
out("| tier | questions with a read-out | all adopted states' paths function-only (POS) | at least one adopted state function-only | all hiragana-only | function words / path words (distinct per state, summed) | questions whose paths hold at least one content word |")
out("|---|---|---|---|---|---|---|")
for tn, rows in data.items():
    W = [r for r in rows if "diag" in r]
    fw = sum(r["diag"]["function_words"] for r in W)
    aw = sum(r["diag"]["path_words"] for r in W)
    out("| %s | %d | %d | %d | %d | %d/%d | %d |" % (
        tn, len(W), sum(r["diag"]["all_states_function_only"] for r in W), sum(r["diag"]["any_state_function_only"] for r in W),
        sum(r["diag"]["all_states_hiragana_only"] for r in W), fw, aw, sum(1 for r in W if r["diag"]["content_words"])))
out()
out("## 4. Candidates, lists, trace")
out()
out("| tier | questions with a read-out | adopted states per question (min/median/max) | listed sentences (min/median/max) | orderings (min/median/max) | too many (> 20) | trace: words checked | words traced | all questions 100% |")
out("|---|---|---|---|---|---|---|---|---|")
for tn, rows in data.items():
    W = [r for r in rows if "diag" in r]
    ls = [r["counts"]["listed"] for r in W]
    od = [r["counts"]["orderings"] for r in W]
    st = [r["states_total"] for r in W]
    wc = sum(r["trace"]["words_checked"] for r in W)
    wt = sum(r["trace"]["words_traced"] for r in W)
    allok = all(r["trace"]["words_checked"] == r["trace"]["words_traced"] and r["trace"]["n_failures"] == 0 for r in W)
    f = lambda xs: "%d/%d/%d" % (min(xs), statistics.median(xs), max(xs))
    out("| %s | %d | %s | %s | %s | %d | %d | %d | %s |" % (tn, len(W), f(st), f(ls), f(od),
                                                         sum(r["readout"]["too_many"] for r in W), wc, wt, allok))
out()
for tn, rows in data.items():
    W = [r for r in rows if "diag" in r]
    out("distinct content-word sets of the paths across the %d %s questions with a read-out: %d" % (
        len(W), tn, len({tuple(r["diag"]["content_words"]) for r in W})))
out()
sys.path.insert(0, ROOT)
import run_readout as RR                                        # noqa: E402
for tn, rows in data.items():
    tot = fo = 0
    for r in rows:
        for st in r.get("paths", []):          # the first 3 adopted states of each question are stored
            for p in st:
                tot += 1
                fo += all(RR.func_pos(w, tn) for w in p["words"])
    out("%s section paths (first 3 adopted states per question): %d of %d consist only of function words" % (tn, fo, tot))
out()
out("k (working sections) per adopted state: " + str(dict(sorted(collections.Counter(
    k for rows in data.values() for r in rows for k in r.get("k_per_state", [])).items()))))
open(os.path.join(HERE, "results", "%s_summary.md" % COND), "w", encoding="utf-8").write("\n".join(L) + "\n")
