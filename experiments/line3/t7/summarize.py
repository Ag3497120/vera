"""T7 summary of results/S300_all_tiers.jsonl: CANDIDATE QUALITY first (owner's principle, 2026-10-07), rule-B scores for
reference only.  usage: summarize.py [IN] [OUT=results/summary.md]"""
import collections
import hashlib
import json
import os
import statistics
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
sys.path.insert(0, os.path.join(ROOT, "experiments", "line3"))
import grade as G                                              # noqa: E402

IN = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "results", "S300_all_tiers.jsonl")
OUT = sys.argv[2] if len(sys.argv) > 2 else os.path.join(HERE, "results", "summary.md")
rows = sorted((json.loads(l) for l in open(IN, encoding="utf-8")), key=lambda r: r["id"])
TIERS = ("RUN", "WORD", "CHAR")
L = []


def out(s=""):
    L.append(s)
    print(s)


golds = lambda r: [x.casefold() for x in r["gold"].split("|") if x]
contains = lambda r, e: any(g in w.casefold() for g in golds(r) for w in e["words"])
ans = lambda r: r["id"].startswith("a")
med = lambda xs: statistics.median(xs) if xs else "-"

# ---- per question facts ----
for r in rows:
    r["tier_hit"] = {t: any(contains(r, e) for e in r["tiers"][t]["entries"]) for t in TIERS}
    r["tier_n"] = {t: len(r["tiers"][t]["entries"]) for t in TIERS}
    r["shown_entries"] = r["combined"]["entries"]
    r["shown_hit"] = any(contains(r, e) for e in r["shown_entries"])
    r["pool_hit"] = any(r["tier_hit"].values())
    r["pool_n"] = sum(r["tier_n"].values())
    r["cv"] = r["combined"]["verdict"]
A_ = [r for r in rows if ans(r)]
U_ = [r for r in rows if not ans(r)]
assert len(A_) == 60 and len(U_) == 30, (len(A_), len(U_))

out("# T7 — three tiers combined, S300, 90 questions (placements: level mid, function-word filter; all defaults of T6z/T6ab)")
out()
out("## 1. Candidate quality (what a user can pick from)")
out()
out("Gold in a candidate = a gold string occurs in a word of the entry (the oracle rule of T6ab, no core condition). "
    "'shown' = what the combination hands the user (the most stable tier, or the tied tiers' lists); "
    "'pool' = the union of every tier's entries (reference: what the user would see if all tiers were listed).")
out()
out("### Answerable questions (60)")
out()
out("| | RUN only | WORD only | CHAR only | **combined: shown** | pool of all tiers |")
out("|---|---|---|---|---|---|")
out("| a candidate holds the gold (single answer or list entry) | %d | %d | %d | **%d** | %d |" % (
    *(sum(r["tier_hit"][t] for r in A_) for t in TIERS), sum(r["shown_hit"] for r in A_), sum(r["pool_hit"] for r in A_)))
out("| ... as the single ANSWER (gold in it) | %d | %d | %d | **%d** | - |" % (
    *(sum(r["tiers"][t]["verdict"] == "ANSWER" and r["tier_hit"][t] for r in A_) for t in TIERS),
    sum(r["cv"] == "ANSWER" and r["shown_hit"] for r in A_)))
out("| ... inside a list of >= 2 entries | %d | %d | %d | **%d** | - |" % (
    *(sum(r["tiers"][t]["verdict"] == "CHOICE" and r["tier_hit"][t] for r in A_) for t in TIERS),
    sum(r["cv"] == "CHOICE" and r["shown_hit"] for r in A_)))
out("| no candidate at all (no state / no path) | %d | %d | %d | **%d** | %d |" % (
    *(sum(r["tier_n"][t] == 0 for r in A_) for t in TIERS), sum(r["cv"].startswith("UNKNOWN") for r in A_),
    sum(r["pool_n"] == 0 for r in A_)))
out("| candidates but none holds the gold | %d | %d | %d | **%d** | %d |" % (
    *(sum(r["tier_n"][t] > 0 and not r["tier_hit"][t] for r in A_) for t in TIERS),
    sum(len(r["shown_entries"]) > 0 and not r["shown_hit"] for r in A_), sum(r["pool_n"] > 0 and not r["pool_hit"] for r in A_)))
out()
out("### List sizes (entries) on answerable questions that have a list")
out()
out("| | RUN | WORD | CHAR | shown (combined) | pool |")
out("|---|---|---|---|---|---|")
def sizes(f):
    xs = [f(r) for r in A_ if f(r) >= 2]
    return "n=%d median %s max %s" % (len(xs), med(xs), max(xs) if xs else "-")
out("| lists of >= 2 | %s | %s | %s | %s | %s |" % (*(sizes(lambda r, t=t: r["tier_n"][t]) for t in TIERS),
                                                    sizes(lambda r: len(r["shown_entries"])), sizes(lambda r: r["pool_n"])))
firsts = []
for r in A_:
    if r["cv"] == "CHOICE":
        pos = [i + 1 for i, e in enumerate(r["shown_entries"]) if contains(r, e)]
        if pos:
            firsts.append(pos[0])
out()
out("shown lists with gold: %d; first gold position (1-based, list order is a label): %s (median %s)" % (len(firsts), sorted(firsts), med(firsts)))
out()
out("### Unanswerable questions (30: fict + attr) — can a user reject what is shown?")
out()
out("| | RUN only | WORD only | CHAR only | **combined: shown** |")
out("|---|---|---|---|---|")
def ucls(r, t=None):
    v = r["tiers"][t]["verdict"] if t else r["cv"]
    return "single" if v == "ANSWER" else ("list" if v == "CHOICE" else "none")
for lab, key in (("no candidate (nothing to reject)", "none"), ("only a list (a user can reject it)", "list"),
                 ("a single answer (looks like a confident answer: wrong)", "single")):
    out("| %s | %d | %d | %d | **%d** |" % (lab, *(sum(ucls(r, t) == key for r in U_) for t in TIERS), sum(ucls(r) == key for r in U_)))
out()
out("### Questions with no state (no candidate): does the combination help?")
out()
out("| | RUN | WORD | CHAR | combined (no tier has any) |")
out("|---|---|---|---|---|")
out("| answerable (60) | %d | %d | %d | %d |" % (*(sum(r["tier_n"][t] == 0 for r in A_) for t in TIERS), sum(r["pool_n"] == 0 for r in A_)))
out("| all 90 | %d | %d | %d | %d |" % (*(sum(r["tier_n"][t] == 0 for r in rows) for t in TIERS), sum(r["pool_n"] == 0 for r in rows)))
runless = [r["id"] for r in A_ if r["tier_n"]["RUN"] == 0 and r["pool_n"] > 0]
out()
out("answerable questions with no RUN candidate but some candidate in another tier: %d (%s); of these the gold is in the pool for %d" % (
    len(runless), ",".join(runless), sum(1 for r in A_ if r["id"] in runless and r["pool_hit"])))
out("answerable questions where RUN has no gold but another tier does: %d (%s)" % (
    sum(1 for r in A_ if not r["tier_hit"]["RUN"] and r["pool_hit"]),
    ",".join(r["id"] for r in A_ if not r["tier_hit"]["RUN"] and r["pool_hit"])))
out()
out("### What the combination returned (90 questions)")
out()
c = collections.Counter((r["cv"], len(r["combined"]["shown"]) if r["combined"]["shown"] else 0, r["combined"]["tie_between_tiers"]) for r in rows)
out("| verdict | tiers shown | tie between tiers | questions |")
out("|---|---|---|---|")
for k, v in sorted(c.items()):
    out("| %s | %d | %s | %d |" % (k[0], k[1], k[2], v))
shown_by = collections.Counter(t for r in rows for t in r["combined"]["shown"])
out()
out("tier appears among the shown tiers (times): %s; stability values seen: %s" % (
    dict(sorted(shown_by.items())), dict(collections.Counter(r["tiers"][t]["stability"] for r in rows for t in TIERS if r["tier_n"][t]).most_common(8))))
agree = sum(1 for r in rows if any(p["shared_words"] for p in r["agreement"]))
out("questions where at least two tiers share a literal word (reported, never used): %d; where the gold-holding tiers are more than one: %d" % (
    agree, sum(1 for r in A_ if sum(r["tier_hit"].values()) > 1)))

# ---- rule B ----
out()
out("## 2. Rule-B scores (reference only; not the goal)")
out()
out("Rule B: the answer = the word set of the single entry; a list / UNKNOWN = abstention; correct iff a gold string is in it and the core is in the subject; unanswerable answered = wrong.")
out()
def gradeB(cls_v, entries, core, r):
    text = "\n".join(entries[0]["words"]) if cls_v == "ANSWER" else ""
    g, hit, _ = G.grade(G.classify(cls_v), core, text, r["subject"], r["gold"])
    return dict(qid=r["id"], kind=r["kind"], cls=G.classify(cls_v), grade=g, gold_hit=hit)
def tallyB(gs):
    t = G.tally(gs)
    return "%d/%d/%d (answered unanswerable %d)" % (t["correct"], t["wrong"], t["abstain"], t["answered_unanswerable"])
res = {}
for t in TIERS:
    res[t] = [gradeB(r["tiers"][t]["verdict"], r["tiers"][t]["entries"], r["tiers"][t]["core"], r) for r in rows]
comb = []
for r in rows:
    shown = r["combined"]["shown"]
    core = r["tiers"][shown[0]]["core"] if len(shown) == 1 else ""
    comb.append(gradeB(r["cv"], r["shown_entries"], core, r))
out("| system | correct/wrong/abstain (60 answerable) |")
out("|---|---|")
out("| T6z RUN only (recorded) | 18/3/39 (answered unanswerable 4) |")
out("| T6ab blind user on T6z lists (recorded) | 29/4/27 |")
for t in TIERS:
    out("| %s only (this run) | %s |" % (t, tallyB(res[t])))
out("| **combined (this run)** | **%s** |" % tallyB(comb))
out()

# ---- RUN sanity vs the stored T6z ----
stored = os.path.join(ROOT, "experiments/line3/t6z/results/S300_RUN_t6z_defaults.jsonl")
if os.path.exists(stored):
    st = {json.loads(l)["id"]: json.loads(l) for l in open(stored, encoding="utf-8")}
    n = same = 0
    for r in rows:
        s = st[r["id"]]
        if s["answer"].get("verdict") is None and not r["tiers"]["RUN"]["entries"]:
            continue
        n += 1
        h = hashlib.sha256(json.dumps(s["answer"], sort_keys=True, ensure_ascii=False).encode()).hexdigest()
        same += h == r["tiers"]["RUN"]["readout_answer_sha"]
    out("RUN tier vs the stored T6z read-out objects (sha256 of the answer object): %d / %d equal" % (same, n))
    out()

# ---- time ----
out("## 3. Time (per question, wall, 9 worker processes on one machine: contention included)")
out()
out("| | median s | p90 s | max s | total CPU-s |")
out("|---|---|---|---|---|")
def tt(xs):
    xs = sorted(xs)
    return "%.2f | %.2f | %.2f | %.0f" % (statistics.median(xs), xs[int(0.9 * (len(xs) - 1))], xs[-1], sum(xs))
for t in TIERS:
    out("| %s search + read-out | %s |" % (t, tt([r["tiers"][t]["ms"] / 1000 for r in rows])))
out("| all three tiers (one question) | %s |" % tt([r["secs_total"] for r in rows]))
out()
out("budget raised on demand (question x tier): %s" % {t: sum(r["tiers"][t]["raised"] for r in rows) for t in TIERS})
out()
out("slowest questions (all tiers): %s" % ", ".join("%s %.1fs" % (r["id"], r["secs_total"]) for r in sorted(rows, key=lambda r: -r["secs_total"])[:6]))
out()

# ---- per question table ----
out("## 4. Per question")
out()
out("| id | kind | RUN n/gold | WORD n/gold | CHAR n/gold | combined | shown | gold in shown | gold in pool |")
out("|---|---|---|---|---|---|---|---|---|")
for r in rows:
    f = lambda t: "%d/%s" % (r["tier_n"][t], "Y" if r["tier_hit"][t] else ("-" if ans(r) else "."))
    out("| %s | %s | %s | %s | %s | %s | %s%s | %s | %s |" % (r["id"], r["kind"], f("RUN"), f("WORD"), f("CHAR"), r["cv"],
        "+".join(r["combined"]["shown"]) or "-", " (tie)" if r["combined"]["tie_between_tiers"] else "",
        ("Y" if r["shown_hit"] else "-") if ans(r) else ".", ("Y" if r["pool_hit"] else "-") if ans(r) else "."))
open(OUT, "w", encoding="utf-8").write("\n".join(L) + "\n")
