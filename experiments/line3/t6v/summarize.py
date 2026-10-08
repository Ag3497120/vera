"""T6v summary: one table for T0 legacy / baseline (T6 stored) / V1 / V2 / V3 / V123 -> results/summary.md.
Grading = experiments/line3/grade.py exactly as T6 (strict: adopted candidate; list = abstention;
unanswerable answered = wrong)."""
import collections
import glob
import json
import os
import statistics
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import common as C                                              # noqa: E402
import grade as G                                               # noqa: E402

COND = "S300"
L = []


def out(s=""):
    L.append(s)
    print(s)


Q = {r[0]: r for r in C.questions()}
T0 = json.load(open(os.path.join(C.ROOT, "experiments/line3/results/base_%s.json" % COND[1:])))
base0 = {p: G.tally([r for r in T0["rows"] if r["path"] == p and r["qid"] != "id"]) for p in ("a1", "a2")}


def load_variant(tn, v):
    rows = []
    for p in sorted(glob.glob(os.path.join(HERE, "results", "%s_%s_%s.*jsonl" % (COND, tn, v)))):
        rows += [json.loads(l) for l in open(p, encoding="utf-8")]
    return sorted(rows, key=lambda r: r["id"])


def load_baseline(tn):
    rows = [json.loads(l) for l in open(os.path.join(C.ROOT, "experiments/line3/t6/results/%s_%s_mid_64x8.jsonl" % (COND, tn)), encoding="utf-8")]
    out_rows = []
    for r in rows:
        d = r.get("diag")
        n = {"id": r["id"], "kind": r["kind"], "gold": r["gold"], "variant": "baseline",
             "cycle": {"verdict": r["t5_verdict"], "units": r["t5_units"]},
             "strict_verdict": r["strict_verdict"], "strict_text": r["strict"]["text"],
             "readout": r["readout"], "states_total": r.get("states_total", 0)}
        if d:
            n["diag"] = {"gold_in_sentence": d["gold_in_sentence"], "gold_in_a_path": d["gold_in_a_path"],
                         "gold_in_path_words_union": d["gold_in_path_words_union"],
                         "content_words": d["content_words"], "core": r["strict"]["core"],
                         "paths_first3": r["paths"], "all_states_function_only": d["all_states_function_only"]}
            n["counts"] = r["counts"]
        out_rows.append(n)
    return out_rows


def strict_rows(rows):
    g = []
    for r in rows:
        subj = Q[r["id"]][2]
        core = r.get("diag", {}).get("core", "")
        v = r["strict_verdict"]
        cls = G.classify(v)
        text = r.get("strict_text", "")
        gr, hit, sok = G.grade(cls, core, text, subj, r["gold"])
        g.append(dict(qid=r["id"], kind=r["kind"], cls=cls, grade=gr, gold_hit=hit))
    return g


def unit_rows(rows):
    g = []
    for r in rows:
        subj = Q[r["id"]][2]
        core = r.get("diag", {}).get("core", "")
        v = r["cycle"]["verdict"]
        cls = G.classify(v)
        text = "".join(r["cycle"]["units"]) if v == "ANSWER" else ""
        gr, hit, sok = G.grade(cls, core, text, subj, r["gold"])
        g.append(dict(qid=r["id"], kind=r["kind"], cls=cls, grade=gr, gold_hit=hit))
    return g


def fo_paths(r, tn):
    """(function-only paths, paths) over the first 3 adopted states (the T6 metric) and over all states."""
    d = r.get("diag")
    if not d:
        return 0, 0, 0, 0
    if "paths_first3_total" in d:
        return d["paths_first3_function_only"], d["paths_first3_total"], d["paths_all_function_only"], d["paths_all_total"]
    tot = fo = 0
    for st in d["paths_first3"]:
        for p in st:
            tot += 1
            fo += all(C.RR.func_pos(w, tn) for w in p["words"])
    return fo, tot, fo, tot


def table(tn, variants):
    out("### Tier %s" % tn)
    out()
    out("(1) strict grading (T0 grader 7.2: adopted read-out candidate; list = abstention; unanswerable answered = wrong)")
    out()
    out("| system | questions | correct/wrong/abstain (answerable) | unanswerable answered (fict+attr) | of which wrong | read-out verdicts | cycle unit answer: correct/wrong/abstain, unanswerable answered |")
    out("|---|---|---|---|---|---|---|")
    if tn == "RUN":
        for p in ("a1", "a2"):
            t = base0[p]
            out("| T0 legacy %s | 90 | %d/%d/%d | %d+%d | %d | - | - |" % (p, t["correct"], t["wrong"], t["abstain"], t["fict_answered"],
                                                                    t["attr_answered"], t["answered_unanswerable"]))
    for name, rows in variants:
        t = G.tally(strict_rows(rows))
        u = G.tally(unit_rows(rows))
        vc = collections.Counter(r["strict_verdict"] for r in rows)
        out("| %s | %d | %d/%d/%d | %d+%d | %d | %s | %d/%d/%d, %d |" % (
            name, len(rows), t["correct"], t["wrong"], t["abstain"], t["fict_answered"], t["attr_answered"],
            t["answered_unanswerable"], dict(sorted(("None" if k is None else k, v) for k, v in vc.items())),
            u["correct"], u["wrong"], u["abstain"], u["answered_unanswerable"]))
    out()
    out("(2) diagnostic: gold string in the read-out, answerable questions only (a01..a60 for RUN)")
    out()
    out("| system | answerable | with an adopted state | gold in some candidate sentence | gold in some single section path | gold in union of path words | gold in the cycle's unit answer | gold held in subject's sentences |")
    out("|---|---|---|---|---|---|---|---|")
    by_title = collections.defaultdict(list)
    for l in open(os.path.join(C.ROOT, "experiments/line3/data/%s.jsonl" % COND), encoding="utf-8"):
        j = json.loads(l)
        by_title[j["title"]].append(j["sent"])
    for name, rows in variants:
        A = [r for r in rows if r["id"].startswith("a")]
        W = [r for r in A if "diag" in r]
        held = sum(1 for r in A if any(g and any(g in s for s in by_title.get(Q[r["id"]][2], [])) for g in r["gold"].split("|")))
        gu = sum(1 for r in A if any(g and g in "".join(r["cycle"]["units"]) for g in r["gold"].split("|")))
        out("| %s | %d | %d | %d | %d | %d | %d | %d |" % (name, len(A), len(W), sum(r["diag"]["gold_in_sentence"] for r in W),
                                                       sum(r["diag"]["gold_in_a_path"] for r in W),
                                                       sum(r["diag"]["gold_in_path_words_union"] for r in W), gu, held))
    out()
    out("(3) question-dependence and (4) function-word-only paths, plus size of the read-out")
    out()
    out("| system | questions with a read-out | distinct content-word sets across them | distinct adopted-state sets (union of path words incl. function words) | function-only paths, first 3 states (T6 metric) | function-only paths, all states | adopted states per question min/median/max | listed sentences min/median/max |")
    out("|---|---|---|---|---|---|---|---|")
    for name, rows in variants:
        W = [r for r in rows if "diag" in r]
        cs = len({tuple(r["diag"]["content_words"]) for r in W})
        a3 = b3 = a = b = 0
        for r in W:
            x = fo_paths(r, tn)
            a3 += x[0]; b3 += x[1]; a += x[2]; b += x[3]
        st = [r["states_total"] for r in W] or [0]
        ls = [r["counts"]["listed"] for r in W] or [0]
        f = lambda xs: "%d/%d/%d" % (min(xs), statistics.median(xs), max(xs))
        # distinct sets of all path words (function words included) = how much the adopted states vary
        ds = len({tuple(sorted({w for stt in r.get("paths", r.get("diag", {}).get("paths_first3", [])) for p in stt for w in p["words"]})) for r in W})
        out("| %s | %d | %d | %d | %d / %d (%.1f%%) | %s | %s | %s |" % (
            name, len(W), cs, ds, a3, b3, 100.0 * a3 / max(b3, 1),
            ("%d / %d (%.1f%%)" % (a, b, 100.0 * a / max(b, 1))) if variants and name != "baseline (T5/T6 stored)" else "n/a (only first 3 states stored)",
            f(st), f(ls)))
    out()


def walls(tn, names):
    for p in sorted(glob.glob(os.path.join(HERE, "logs", "Q_*%s*.log" % tn))):
        last = [l for l in open(p, encoding="utf-8") if l.startswith("QUEUE_DONE")]
        n = sum(1 for l in open(p, encoding="utf-8") if l[:1] in "aft" and "{" in l)
        out("- %s: %s (questions logged: %d)" % (os.path.basename(p), last[-1].strip() if last else "stopped by the experimenter", n))


if __name__ == "__main__":
    out("## T6v results (S300, placement level mid, search budget 64/8, same 90 fixed questions)")
    out()
    for tn, names in (("RUN", ["base", "V1", "V2", "V3", "V123"]), ("WORD", ["base", "V123"])):
        vs = []
        b = load_baseline(tn)
        vs.append(("baseline (T5/T6 stored)", b))
        for v in names:
            if v == "base":
                r = load_variant(tn, "base")
                if r:
                    vs.append(("baseline re-run (check)", r))
                continue
            r = load_variant(tn, v)
            if r:
                vs.append((v, r))
        table(tn, vs)
        v2 = [x for n_, x in vs if n_ == "V2"]
        if v2 and len(v2[0]) < len(vs[0][1]):
            ids = {r["id"] for r in v2[0]}
            out("#### Same table restricted to the %d questions on which V2 finished (V2 is ~4x costlier than the others: see wall times)" % len(ids))
            out()
            table(tn + " (V2 subset)", [(n_, [r for r in x if r["id"] in ids]) for n_, x in vs])
        m = [r for r in load_variant(tn, "base") if "matches_stored_T5" in r]
        if m:
            out("Baseline re-run equals the stored T5 answer (verdict, units, adopted-state trace) on %d / %d questions." % (
                sum(r["matches_stored_T5"] for r in m), len(m)))
            out()
    out("Wall times:")
    for tn in ("RUN", "WORD"):
        walls(tn, None)
    open(os.path.join(HERE, "results", "summary.md"), "w", encoding="utf-8").write("\n".join(L) + "\n")


def control_and_examples(best="V123", tn="RUN"):
    """(5) chance control: how often does a question's gold appear in the read-out of ANOTHER question
    (mismatched pairs) vs of its own (matched); (6) three read-out examples of the best variant."""
    L2 = []
    L2.append("### (5) Chance control: gold of question i against the read-out words of question j (answerable, RUN)")
    L2.append("")
    L2.append("| system | matched pairs hit (i = j) | mismatched pairs hit (i != j), mean per question | ratio |")
    L2.append("|---|---|---|---|")
    for name in ("baseline", "V1", "V2", "V3", "V123"):
        rows = load_baseline(tn) if name == "baseline" else load_variant(tn, name)
        W = [r for r in rows if r["id"].startswith("a") and "diag" in r]
        if not W:
            continue
        gold = {r["id"]: [g.casefold() for g in r["gold"].split("|") if g] for r in W}
        words = {r["id"]: "".join(r["diag"]["content_words"]).casefold() for r in W}
        m = sum(any(g in words[r["id"]] for g in gold[r["id"]]) for r in W)
        mm = [sum(any(g in words[r["id"]] for g in gold[q["id"]]) for q in W if q["id"] != r["id"]) / max(len(W) - 1, 1) for r in W]
        # hit fraction of the matched pairs vs the mean mismatched fraction
        mf = m / len(W)
        xf = sum(mm) / len(mm)
        L2.append("| %s | %d / %d (%.2f) | %.2f | %s |" % (name, m, len(W), mf, xf, ("%.1f" % (mf / xf)) if xf else "inf"))
    L2.append("")
    L2.append("### (6) Three read-out examples of %s (RUN)" % best)
    L2.append("")
    rows = load_variant(tn, best)
    A = [r for r in rows if r["id"].startswith("a") and "diag" in r]
    hits = [r for r in A if r["diag"]["gold_in_a_path"]]
    miss = [r for r in A if not r["diag"]["gold_in_a_path"]]
    pick = [hits[0], hits[len(hits) // 2]] + [miss[0]] if hits and miss else A[:3]
    for r in pick:
        L2.append("- **%s** %s  gold = %s  (cycle unit answer: %s %s; adopted states %d; listed sentences %s; gold in a path: %s)" % (
            r["id"], r["question"], r["gold"], r["cycle"]["verdict"], r["cycle"]["units"], r["states_total"],
            r["counts"]["listed"], r["diag"]["gold_in_a_path"]))
        for p in r["paths"][0]:
            L2.append("    - section %d (query unit %s): %s" % (p["section"], p["attached"], " / ".join(p["words"])))
        L2.append("    - first listed sentences: %s" % " | ".join(s[:60] for s in r["sentences_sample"][:3]))
    out("\n".join(L2))
    open(os.path.join(HERE, "results", "summary.md"), "a", encoding="utf-8").write("\n" + "\n".join(L2) + "\n")


if __name__ == "__main__":
    control_and_examples()
