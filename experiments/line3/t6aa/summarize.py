"""T6aa grading of results/S300_RUN_t6aa_common.jsonl (new default: a list's answer = the words common to all entries).
Rule B (official, owner): single entry = its word set, as in T6z (correct iff a gold string occurs in it, + T0 core-in-subject);
list with a NON-EMPTY common answer: correct iff a gold string occurs in the common answer words, wrong if not;
list with empty common answer = abstention; UNKNOWN / AMBIGUOUS / no state = abstention; unanswerable answered = wrong.
Also checks: common=None reproduces the stored T6z answer bytes (legacy sha) for every question."""
import collections
import hashlib
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
sys.path.insert(0, os.path.join(ROOT, "experiments", "line3"))
import grade as G                                              # noqa: E402

rows = sorted((json.loads(l) for l in open(os.path.join(HERE, "results", "S300_RUN_t6aa_common.jsonl"), encoding="utf-8")),
              key=lambda r: r["id"])
old = {}
for l in open(os.path.join(ROOT, "experiments/line3/t6z/results/S300_RUN_t6z_defaults.jsonl"), encoding="utf-8"):
    q = json.loads(l)
    old[q["id"]] = q
L = []


def out(s=""):
    L.append(s)
    print(s)


verdict = lambda r: r["answer"].get("verdict")
entries = lambda r: r["answer"].get("entries", [])
golds = lambda r: [x.casefold() for x in r["gold"].split("|") if x]
is_list = lambda r: verdict(r) == "CHOICE"
cwords = lambda r: r["answer"].get("common", {}).get("words", []) if is_list(r) else []


def text_B(r):
    if verdict(r) == "ANSWER":
        return "\n".join(entries(r)[0]["words"])
    return "\n".join(cwords(r))


def cls_of(r):
    v = verdict(r)
    if v == "CHOICE" and cwords(r):
        return "ANSWER"            # list with a non-empty common answer is answered
    return G.classify(v)


def graded():
    g = []
    for r in rows:
        gr, hit, sok = G.grade(cls_of(r), r["core"], text_B(r), r["subject"], r["gold"])
        g.append(dict(qid=r["id"], kind=r["kind"], cls=cls_of(r), grade=gr, gold_hit=hit))
    return g


# legacy reproduction
bad = []
for r in rows:
    if "legacy_answer_bytes_sha" in r:
        o = old[r["id"]]["answer"]
        if hashlib.sha256(json.dumps(o, sort_keys=True, ensure_ascii=False).encode()).hexdigest() != r["legacy_answer_bytes_sha"]:
            bad.append(r["id"])
out("## T6aa results (S300 RUN; T6z defaults + common answer of a list; 90 fixed questions; search budget 64/8; level mid)")
out()
out("- legacy check: common=None answer_obj equals the stored T6z answer object (sha256 of the sorted-key JSON) for %d of %d read-outs; mismatches: %s" % (
    sum("legacy_answer_bytes_sha" in r for r in rows) - len(bad), sum("legacy_answer_bytes_sha" in r for r in rows), bad or "none"))
tr = [r for r in rows if "trace_ok" in r]
out("- trace check (incl. common answers): %d / %d read-outs 100%% (failures %d)" % (sum(r["trace_ok"] for r in tr), len(tr), sum(r["trace"]["n_failures"] for r in tr)))
out()
gr = graded()
t = G.tally(gr)
vc = dict(sorted(collections.Counter("None" if verdict(r) is None else verdict(r) for r in rows).items()))
out("(1) rule B official (answerable a01..a60; unanswerable = fict + attr)")
out()
out("| system | correct/wrong/abstain | unanswerable answered (fict+attr) |")
out("|---|---|---|")
out("| T0 legacy a1 | 45/7/8 | 3+8 = 11 |")
out("| T6z rule B (list = abstention) | 18/3/39 | 2+2 = 4 |")
out("| **T6aa rule B (list answered by common words)** | %d/%d/%d | %d+%d = %d |" % (t["correct"], t["wrong"], t["abstain"], t["fict_answered"], t["attr_answered"], t["answered_unanswerable"]))
out()
out("verdicts: %s" % vc)
lists = [r for r in rows if is_list(r)]
com = [r for r in lists if cwords(r)]
goldin = lambda r: any(g in w.casefold() for g in golds(r) for w in cwords(r))
out()
out("(2) lists")
out()
out("- lists (CHOICE): %d; with a non-empty common answer: %d; with an empty common answer (stay a list = abstention): %d" % (len(lists), len(com), len(lists) - len(com)))
out("- common answers of answerable questions: %d, containing gold: %d; of unanswerable (fict/attr): %d (answered = wrong)" % (
    sum(r["id"].startswith("a") for r in com), sum(goldin(r) for r in com if r["id"].startswith("a")), sum(not r["id"].startswith("a") for r in com)))
out("- lists with empty common answer: intersection empty %d; intersection only query units/centres %d" % (
    sum(not r["answer"]["common"]["intersection"] for r in lists if not cwords(r)), sum(bool(r["answer"]["common"]["intersection"]) for r in lists if not cwords(r))))
out()
out("| id | gold | entries | intersection | query units | centres (n) | common answer | gold in it |")
out("|---|---|---|---|---|---|---|---|")
for r in lists:
    c = r["answer"]["common"]
    out("| %s | %s | %d | %d | %s | %d | %s | %s |" % (r["id"], r["gold"], len(entries(r)), len(c["intersection"]), "、".join(c["query_units"]), len(c["centres"]),
                                                    "、".join(c["words"]) if c["words"] else "(empty)", ("Y" if goldin(r) else "N") if r["id"].startswith("a") else "-"))
out()
out("(3) per-question grade changes vs T6z")
for r, g in zip(rows, gr):
    o = old[r["id"]]
    cl = G.classify(o["answer"].get("verdict"))
    ptext = "\n".join(entries(o)[0]["words"]) if o["answer"].get("verdict") == "ANSWER" else ""
    og = G.grade(cl, o["core"], ptext, o["subject"], o["gold"])[0]
    if og != g["grade"]:
        out("- %s: %s -> %s" % (r["id"], og, g["grade"]))
open(os.path.join(HERE, "results", "summary.md"), "w", encoding="utf-8").write("\n".join(L) + "\n")
