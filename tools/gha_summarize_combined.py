"""GitHub Actions helper (line3-sweep.yml, structure=combined): the combined labelled candidate list of one preset, built the way
experiments/line3/g3/combined/summarize_combined.py builds it, but from the merged shard files of ONE run.

usage: gha_summarize_combined.py RESULTS_DIR PRESET GROUP_INSERT [--evidence plain,window] [--merge none|word_set]
Inputs:  RESULTS_DIR/ask_fulllead_PRESET_GROUP_INSERT-stop.jsonl   (t10/measure_ask.py records: flat cross = layer0, layers = on.seatsPath)
         RESULTS_DIR/combined/win_PRESET_EV.jsonl                  (g3/combined/measure_windows.py records, one file per evidence variant)
Output:  RESULTS_DIR/combined/summary.md, RESULTS_DIR/combined/combined_PRESET.jsonl (the combined list per question); both are printed (summary.md).
Only the questions present in the flat file AND in every window file are combined; the counts say how many that is.
Grading is t9's (scorer.hits_words); COMBINED rows follow the combined verdict (a candidate only windows give is never a single answer), the other
rows t9's count rule (exactly one candidate = single), as summarize_combined.py."""
import argparse, json, os, statistics, sys
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
L3 = os.path.join(ROOT, "experiments", "line3")
for p in (ROOT, os.path.join(L3, "t9"), os.path.join(L3, "g3", "combined")):
    sys.path.insert(0, p)
import scorer as S                                              # noqa: E402
from replay import flat_src, layers_src, win_src               # noqa: E402
from verantyx.line3 import combined as CB                       # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("results")
ap.add_argument("preset")
ap.add_argument("group_insert")
ap.add_argument("--evidence", default="plain,window")
ap.add_argument("--merge", default="none", choices=["none", "word_set"])
A = ap.parse_args()
EVS = [e for e in A.evidence.split(",") if e]
COMB = os.path.join(A.results, "combined")


def jl(path):
    out = {}
    for l in open(path, encoding="utf-8"):
        if l.strip():
            r = json.loads(l)
            if "error" not in r:
                out[r["id"]] = r
    return out


bank = {}
for l in open(os.path.join(L3, "bank2", "bank2.tsv"), encoding="utf-8"):
    if l.startswith("#") or not l.strip():
        continue
    f = l.rstrip("\n").split("\t")
    bank[f[0]] = {"id": f[0], "kind": f[1], "corpus": f[2], "question": f[4], "gold": f[5]}

FLAT = jl(os.path.join(A.results, "ask_fulllead_%s_%s-stop.jsonl" % (A.preset, A.group_insert)))
WIN = {ev: jl(os.path.join(COMB, "win_%s_%s.jsonl" % (A.preset, ev))) for ev in EVS}
ids = sorted(i for i in FLAT if i in bank and all(i in WIN[ev] for ev in EVS))


def row(meta, srcs, rule):
    if rule == "verdict":
        c = CB.combine(meta["question"], srcs, merge=A.merge)
        ents = [(list(e.words), sorted(e.origins)) for e in c.entries]
        return dict(meta, entries=ents, verdict=c.verdict, before=c.listed_before_merge)
    ents = [(list(cd.words), [cd.origin]) for s in sorted(srcs, key=lambda s: CB._source_rank(s.name)) for cd in s.cands]
    return dict(meta, entries=ents, verdict=CB.ANSWER if len(ents) == 1 else CB.CHOICE if ents else "NONE", before=len(ents))


def grade(r):
    n = len(r["entries"])
    hit = any(S.hits_words(r["gold"], w) for w, _o in r["entries"])
    if r["kind"] == "unans":
        return ("none" if n == 0 else "single" if r["verdict"] == CB.ANSWER else "list"), n
    if n == 0:
        return "none", 0
    if r["verdict"] == CB.ANSWER:
        return ("single_right" if hit else "single_wrong"), n
    return ("list_gold" if hit else "list_nogold"), n


SYS, ORDER = {}, []
LOG = []
for i in ids:
    meta = {k: bank[i][k] for k in ("id", "kind", "gold", "question")}
    rec = FLAT[i]
    f_s = flat_src(rec)
    l_s = layers_src(rec) if "seatsPath" in rec.get("on", {}) else None
    w_s = {ev: win_src(WIN[ev][i], ev) for ev in EVS}
    rows = [("flat (3 tiers)", [f_s])]
    if l_s is not None:
        rows.append(("flat + layers (ssp)", [f_s, l_s]))
    rows += [("windows alone, %s" % ev, [w_s[ev]]) for ev in EVS]
    base = [f_s] + ([l_s] if l_s is not None else [])
    rows.append(("COMBINED (flat + layers + windows %s)" % "/".join(EVS), base + [w_s[ev] for ev in EVS]))
    for name, srcs in rows:
        if name not in SYS:
            SYS[name] = {}
            ORDER.append(name)
        SYS[name][i] = row(meta, srcs, "verdict" if name.startswith("COMBINED") else "count")
    LOG.append(SYS[ORDER[-1]][i])


def med(x): return "-" if not x else "%.1f" % statistics.median(x)


L = ["# line3 combined list, %s, %s (flat records: group_insert %s; window evidence %s; merge %s)" % (A.preset, "fulllead", A.group_insert, ",".join(EVS), A.merge),
     "", "Questions combined: %d (flat file %d, window files %s). Code: line3 combined.combine, the one `ask(structure=\"combined\")` uses." %
     (len(ids), len(FLAT), ", ".join("%s %d" % (ev, len(WIN[ev])) for ev in EVS)), "",
     "## intra2: is the gold in a candidate", "",
     "| system | n | gold in a candidate | single right | single wrong | list with gold | list without gold | no candidate | list size median / max |",
     "|---|---|---|---|---|---|---|---|---|"]
for nm in ORDER:
    d = SYS[nm]
    sel = [i for i in ids if d[i]["kind"] == "intra2"]
    if not sel:
        continue
    cnt, sizes = defaultdict(int), []
    for i in sel:
        c, n = grade(d[i]); cnt[c] += 1
        if n >= 2:
            sizes.append(n)
    g = cnt["single_right"] + cnt["list_gold"]
    L.append("| %s | %d | %d (%.0f%%) | %d | %d | %d | %d | %d | %s / %s |" % (nm, len(sel), g, 100 * g / len(sel), cnt["single_right"], cnt["single_wrong"],
             cnt["list_gold"], cnt["list_nogold"], cnt["none"], med(sizes), max(sizes) if sizes else "-"))
L += ["", "## unans: can a user reject what is shown", "",
      "| system | n | no candidate (abstained) | list (rejectable) | single answer (confident wrong) |", "|---|---|---|---|---|"]
for nm in ORDER:
    d = SYS[nm]
    sel = [i for i in ids if d[i]["kind"] == "unans"]
    if not sel:
        continue
    cnt = defaultdict(int)
    for i in sel:
        cnt[grade(d[i])[0]] += 1
    L.append("| %s | %d | %d | %d | %d |" % (nm, len(sel), cnt["none"], cnt["list"], cnt["single"]))
L.append("")
os.makedirs(COMB, exist_ok=True)
with open(os.path.join(COMB, "summary.md"), "w", encoding="utf-8") as f:
    f.write("\n".join(L) + "\n")
with open(os.path.join(COMB, "combined_%s.jsonl" % A.preset), "w", encoding="utf-8") as f:
    for r in LOG:
        f.write(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n")
print("\n".join(L))
