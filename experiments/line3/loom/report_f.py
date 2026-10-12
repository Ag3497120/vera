"""LOOM-evidence v2 re-measurement (claude-haiku-5-5, loom modes only): the tables of REPORT.md in results_h55f.

    python experiments/line3/loom/report_f.py            # print the tables

Sets: (a) runs_h55f / results_h55f (bank2's 10 tasks), (b) runs_unans_f (25 unanswerable bank2 items), (c) runs_unans_adv_f (35 bank4 items), (d) runs_reach_f
(the 10 reachable answerable items x 2 modes x 3 repeats, tags r1..r3).  The v1 comparison is the stored measurement under evidence.v1 (runs_h55e, runs_unans_e,
runs_unans_adv_e).  Every ledger is VERIFIED and replayed (score.score_run) before it is counted.  Nothing here calls a model; the gold is read by score.py from bank2.tsv.
"""
from __future__ import annotations

import glob
import json
import os
import statistics
import sys
from collections import Counter, OrderedDict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import report_evidence as RE   # noqa: E402
import report_unans as RU      # noqa: E402

S = RU.S
LOOM = RU.LOOM_MODES
d = lambda *p: os.path.join(HERE, *p)
REACH_IDS = ("I2-003", "I2-004", "I2-005", "I2-006", "I2-013", "I2-014", "I2-018", "R2-I005", "R2-I007", "R2-I017")
PRICE_IN, PRICE_OUT = 0.10, 0.50          # claude-haiku-5-5, USD per 1M tokens, prompts up to 100K tokens (above: 0.50 / 2.50); no caching was used


def loom(R):
    return [r for r in R if r["mode"] in LOOM and not r["missing"]]


def summ(rr, answerable):
    n = len(rr)
    he = sum(1 for r in rr if r["hit_exact"])
    hc = sum(1 for r in rr if (not r["hit_exact"]) and r["hit_cited"])
    if answerable:
        wrong = sum(1 for r in rr if r["text"] is not None and not r["hit_exact"])
        ab = sum(1 for r in rr if r["status"] == "abstained_wrong")
    else:
        wrong = sum(1 for r in rr if r["status"] == "answered_unans")
        ab = sum(1 for r in rr if r["status"] == "abstained_correct")
    no = sum(1 for r in rr if r["status"] == "no_output")
    nv = sum(1 for r in rr if not r["verified"])
    return dict(n=n, exact=he, cited=hc, wrong=wrong, abst=ab, noout=no, notver=nv)


def cmp_table(title, old, new, answerable):
    out = ["", "**%s**" % title, "", "| mode | rule | runs | exact hits | + hit_cited (longer, quoted) | wrong emits (confident wrong) | abstentions | no output | not verified |", "|---|---|---|---|---|---|---|---|---|"]
    for m in LOOM:
        for lab, R in (("v1 (h55e-era)", old), ("**v2 (now)**", new)):
            s = summ([r for r in loom(R) if r["mode"] == m], answerable)
            out.append("| %s | %s | %d | %d | %d | %d | %d | %d | %d |" % (m, lab, s["n"], s["exact"], s["cited"], s["wrong"], s["abst"], s["noout"], s["notver"]))
    return out


def tokens(R):
    rr = loom(R)
    i = [r["usage"].get("input_tokens", 0) for r in rr]
    o = [r["usage"].get("output_tokens", 0) for r in rr]
    c = [r["usage"].get("calls", 0) for r in rr]
    return dict(n=len(rr), i=sum(i), o=sum(o), c=sum(c), med=int(statistics.median(i)) if i else 0)


def cost(i, o):
    return i / 1e6 * PRICE_IN + o / 1e6 * PRICE_OUT


# ---------------------------------------------------------------- set (d)
def collect_reach():
    bank = S.load_bank(d("tasks_reach.jsonl"))
    gold = S.load_gold()
    out = []
    for tag in ("r1", "r2", "r3"):
        for row in bank.values():
            base, mode = row["base"], row["mode"]
            name = "%s.%s.api.%s" % (base, mode, tag)
            rd, rj = d("runs_reach_f", name), d("results_reach_f", name + ".json")
            if not os.path.isdir(rd):
                out.append(dict(base=base, mode=mode, rep=tag, missing=True))
                continue
            rs = S.score_run(rd, bank, gold)
            res = json.load(open(rj, encoding="utf-8")) if os.path.isfile(rj) else {}
            dr = res.get("driver_report") or {}
            rec = dict(base=base, mode=mode, rep=tag, missing=False, status=rs.status, text=rs.text, hit=bool(rs.hit_exact), layer=rs.stop_layer, L=rs.layer or {},
                       verified=rs.verify_status == "OK" and rs.replay_verified, usage=dr.get("usage") or {}, ended=dr.get("ended"), gold=gold[base]["gold"],
                       abstain_type=rs.abstain_type)
            rec.update(diagnose(rd, gold[base]["gold"], d("..", "bank2", "bank2.tsv")))
            out.append(rec)
    return out


def evsource(base):
    import csv
    with open(d("..", "bank2", "bank2.tsv"), encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f, delimiter="\t"):
            if r["#id"] == base:
                return r["evidence"]


def codes_in(res):
    """every no_evidence code listed anywhere in a read / emit result"""
    cs = []

    def walk(x):
        if isinstance(x, dict):
            if x.get("type") == "no_evidence":
                for w in x.get("weaves") or []:
                    cs.extend(w.get("codes") or [])
                for c in x.get("crosses") or []:
                    cs.append(c.get("code"))
            for v in x.values():
                walk(v)
        elif isinstance(x, list):
            for v in x:
                walk(v)
    walk(res)
    return cs


def diagnose(rd, gold, _tsv):
    base = os.path.basename(rd).split(".")[0]
    ev = evsource(base)
    alts = [g for g in gold.split("|") if g]
    rows = [json.loads(l) for l in open(os.path.join(rd, "ops.jsonl"), encoding="utf-8")]
    seen = read = False
    weaves, drops, read_codes, emit_codes = [], 0, Counter(), Counter()
    n_reads = n_emits = n_lookups = 0
    last_thread = []
    for r in rows:
        if r["actor"] != "model":
            continue
        op, res = r["op"], r["result"]
        if op == "lookup" and res.get("ok"):
            n_lookups += 1
            for m in res.get("matches") or []:
                for s in m.get("sentences") or []:
                    if s.get("source") == ev:
                        seen = True
        elif op == "read_sentence" and res.get("ok") and res.get("source") == ev:
            read = True
        elif op == "weave_span" and res.get("ok"):
            txt = res.get("text")
            isg = res.get("source") == ev if res.get("source") else None
            weaves.append(dict(sid=res.get("sid"), text=txt, cids=[c["cid"] for c in res.get("crosses", [])], gold_stretch=any(S.hit_exact(g, txt or "") for g in alts)))
        elif op == "drop" and res.get("ok"):
            drops += 1
        elif op == "read" and res.get("ok"):
            n_reads += 1
            read_codes.update(codes_in(res))
        elif op == "emit":
            n_emits += 1
            if not res.get("ok"):
                emit_codes.update(codes_in(res))
                read_codes.update([])
    return dict(seen_gold=seen, read_gold=read, weaves=weaves, drops=drops, read_codes=dict(read_codes), emit_codes=dict(emit_codes), n_reads=n_reads, n_emits=n_emits,
                n_lookups=n_lookups)


def reach_tables(R):
    have = [r for r in R if not r["missing"]]
    out = []
    p = out.append
    p("RUNS: %d of %d; verified and replayed IDENTICAL: %d" % (len(have), len(R), sum(1 for r in have if r["verified"])))
    p("")
    p("| mode | rep | n | exact hits | wrong emits | abstained | no output |")
    p("|---|---|---|---|---|---|---|")
    for m in LOOM:
        for rep in ("r1", "r2", "r3"):
            xs = [r for r in have if r["mode"] == m and r["rep"] == rep]
            p("| %s | %s | %d | %d | %d | %d | %d |" % (m, rep, len(xs), sum(r["hit"] for r in xs), sum(1 for r in xs if r["text"] is not None and not r["hit"]),
                                                    sum(1 for r in xs if r["text"] is None and r["status"] == "abstained_wrong"), sum(1 for r in xs if r["status"] == "no_output")))
        xs = [r for r in have if r["mode"] == m]
        p("| %s | all | %d | %d | %d | %d | %d |" % (m, len(xs), sum(r["hit"] for r in xs), sum(1 for r in xs if r["text"] is not None and not r["hit"]),
                                                    sum(1 for r in xs if r["text"] is None and r["status"] == "abstained_wrong"), sum(1 for r in xs if r["status"] == "no_output")))
    xs = have
    p("| both | all | %d | %d | %d | %d | %d |" % (len(xs), sum(r["hit"] for r in xs), sum(1 for r in xs if r["text"] is not None and not r["hit"]),
                                                  sum(1 for r in xs if r["text"] is None and r["status"] == "abstained_wrong"), sum(1 for r in xs if r["status"] == "no_output")))
    p("")
    p("Per item (hits out of 6 = 2 modes x 3 repeats; R = record_only, C = constructed_allowed; 1 = exact hit, . = no)")
    p("")
    p("| item | question gold | hits /6 | R r1 r2 r3 | C r1 r2 r3 | texts emitted that are not a hit |")
    p("|---|---|---|---|---|---|")
    for b in REACH_IDS:
        xs = [r for r in have if r["base"] == b]
        mk = lambda m: " ".join(("1" if r["hit"] else ".") for r in sorted([x for x in xs if x["mode"] == m], key=lambda x: x["rep"]))
        wr = ["%s/%s:%s" % (r["mode"][0], r["rep"], r["text"]) for r in xs if r["text"] is not None and not r["hit"]]
        p("| %s | %s | %d | %s | %s | %s |" % (b, xs[0]["gold"] if xs else "", sum(r["hit"] for r in xs), mk("record_only"), mk("constructed_allowed"), "; ".join(wr) or "-"))
    p("")
    p("Misses, one line each (found = the gold sentence was shown by a lookup (L) or read_sentence (R); woven = texts of every weave_span; gold? = a woven stretch equals the gold; "
      "read-codes / emit-codes = no_evidence codes listed by a dry-run `read` / a refused `emit`; end = how the run ended)")
    p("")
    p("| run | found | woven (gold stretch marked *) | drops | reads | emits | read-codes | emit-codes | end |")
    p("|---|---|---|---|---|---|---|---|---|")
    for r in have:
        if r["hit"]:
            continue
        found = "R" if r["read_gold"] else ("L" if r["seen_gold"] else "-")
        wv = ", ".join(("*" if w["gold_stretch"] else "") + (w["text"] or "?") for w in r["weaves"]) or "-"
        p("| %s.%s.%s | %s | %s | %d | %d | %d | %s | %s | %s |" % (r["base"], r["mode"], r["rep"], found, wv, r["drops"], r["n_reads"], r["n_emits"],
                                                              json.dumps(r["read_codes"], ensure_ascii=False) if r["read_codes"] else "-",
                                                              json.dumps(r["emit_codes"], ensure_ascii=False) if r["emit_codes"] else "-",
                                                              (r["status"] + ((" " + r["abstain_type"]) if r["abstain_type"] else "") + ((" text=" + r["text"]) if r["text"] else ""))))
    return out


def classify(r):
    """why a non-hit (d) run missed: a single label"""
    if r["hit"]:
        return "hit"
    if r["text"] is not None:
        return "emitted a wrong text"
    gs = [w for w in r["weaves"] if w["gold_stretch"]]
    if not r["read_gold"] and not r["seen_gold"]:
        return "never saw the gold sentence"
    if not gs:
        return "saw the sentence, wove another stretch" if r["weaves"] else "saw the sentence, wove nothing"
    cod = Counter(list(r["read_codes"]) + list(r["emit_codes"]))
    if cod:
        return "wove the gold stretch, refused: " + ",".join(sorted(cod))
    return "wove the gold stretch, no refusal shown, did not emit"


def main():
    old = {"bank2": RU.collect(d("tasks_bank2.jsonl"), d("runs_h55e"), d("results_h55e")), "unans": RU.collect(d("tasks_unans.jsonl"), d("runs_unans_e"), d("results_unans_e")),
           "adv": RU.collect(d("tasks_unans_adv.jsonl"), d("runs_unans_adv_f".replace("_f", "_e")), d("results_unans_adv_e"))}
    new = {"bank2": RU.collect(d("tasks_bank2.jsonl"), d("runs_h55f"), d("results_h55f")), "unans": RU.collect(d("tasks_unans.jsonl"), d("runs_unans_f"), d("results_unans_f")),
           "adv": RU.collect(d("tasks_unans_adv.jsonl"), d("runs_unans_adv_f"), d("results_unans_adv_f"))}
    P = []
    p = P.append
    for k in new:
        have = loom(new[k])
        bad = [(r["base"], r["mode"]) for r in have if not r["verified"]]
        p("%s: %d loom runs, verified+replayed IDENTICAL %d%s" % (k, len(have), sum(1 for r in have if r["verified"]), (" NOT: %s" % bad) if bad else ""))
        ev = Counter()
        for r in have:
            try:
                row0 = json.loads(open(d({"bank2": "runs_h55f", "unans": "runs_unans_f", "adv": "runs_unans_adv_f"}[k], "%s.%s.api" % (r["base"], r["mode"]), "ops.jsonl"), encoding="utf-8").readline())
                ev[(row0["result"].get("evidence_profile") or {}).get("version")] += 1
            except Exception as e:      # noqa: BLE001
                ev["ERR " + type(e).__name__] += 1
        p("   evidence profile recorded in row 0: %s" % dict(ev))
    p("")
    ANS = RE.ANSWERABLE
    b2o, b2n = [r for r in old["bank2"] if r["base"] in ANS], [r for r in new["bank2"] if r["base"] in ANS]
    P += cmp_table("bank2: the 7 answerable tasks (v1 = results_h55e, v2 = results_h55f)", b2o, b2n, True)
    b2uo, b2un = [r for r in old["bank2"] if r["base"] in RE.BANK2_UNANS], [r for r in new["bank2"] if r["base"] in RE.BANK2_UNANS]
    P += cmp_table("bank2: the 3 unanswerable tasks (UF-001, UF-015, R2-U003)", b2uo, b2un, False)
    P += cmp_table("bank2 unanswerable, 25 items (v1 = results_unans_e, v2 = results_unans_f)", old["unans"], new["unans"], False)
    P += cmp_table("bank4 adversarial, 35 items (v1 = results_unans_adv_e, v2 = results_unans_adv_f)", old["adv"], new["adv"], False)
    p("")
    p("### answerable tasks, one line per run (final thread under the recorded rule and under the other)")
    P += RE.answerable_table(loom(new["bank2"]))
    p("")
    p("### route (1) / route (2): final-thread definition, strict / shown / unseen")
    un, adv = loom(new["unans"]), loom(new["adv"])
    P += RE.route_table([r for r in loom(new["bank2"]) if r["base"] in RE.BANK2_UNANS], "the 3 unanswerable bank2 tasks")
    P += RE.route_table(un, "bank2 unans (25 items, 50 runs)")
    P += RE.route_table(adv, "bank4 (35 items, 70 runs)")
    both = un + adv
    P += RE.route_table(both, "bank2 unans + bank4 (60 items, 120 runs)")
    bo = loom(old["unans"]) + loom(old["adv"])
    P += RE.route_table(bo, "BEFORE: same 120 runs of the v1 measurement (results_unans_e + results_unans_adv_e)")
    for ver in (RE.V1, RE.V2):
        t = [r for r in both if RE._fails(r, ver)]
        c = Counter(RE._how(r) for r in t)
        p("")
        p("rule %s, 120 new runs: route (1) %d (%.1f%%): strict %d, shown %d, unseen %d; route (2) L_meta %d (%.1f%%); wrong text %d; other no-text %d" % (
            ver, len(t), 100.0 * len(t) / len(both), c["strict"], c["shown"], c["unseen"], sum(1 for r in both if r["layer"] == "L_meta"),
            100.0 * sum(1 for r in both if r["layer"] == "L_meta") / len(both), sum(1 for r in both if r["text"] is not None),
            sum(1 for r in both if r["text"] is None and r["layer"] != "L_meta" and not RE._fails(r, ver))))
    P += RE.route_runs(both)
    p("")
    p("### every text emitted on an unanswerable item (confident wrong)")
    for r in both + [r for r in loom(new["bank2"]) if r["base"] in RE.BANK2_UNANS]:
        if r["text"] is not None:
            p("  %s.%s: %s" % (r["base"], r["mode"], r["text"]))
    p("")
    p("### stop layers of the 120 unanswerable runs, v1 -> v2")
    for lab, rr in (("v1", bo), ("v2", both)):
        c = Counter(r["layer"] for r in rr)
        p("  %s: %s" % (lab, dict(c)))
    p("")
    p("### set (d): the reachable items")
    reach = collect_reach()
    P += reach_tables(reach)
    have = [r for r in reach if not r["missing"]]
    cl = Counter(classify(r) for r in have if not r["hit"])
    p("")
    p("why the misses missed: " + json.dumps(dict(cl), ensure_ascii=False))
    p("")
    p("### tokens and cost (claude-haiku-5-5 list price %.2f in / %.2f out per 1M, prompts up to 100K tokens; no cache was used)" % (PRICE_IN, PRICE_OUT))
    p("| set | runs | input tokens | output tokens | API calls | input per run (median) | cost USD |")
    p("|---|---|---|---|---|---|---|")
    tot = Counter()
    for lab, R in (("(a) bank2 10 tasks", new["bank2"]), ("(b) bank2 unans 25", new["unans"]), ("(c) bank4 35", new["adv"])):
        t = tokens(R)
        tot.update(i=t["i"], o=t["o"], c=t["c"], n=t["n"])
        p("| %s | %d | %s | %s | %d | %s | %.2f |" % (lab, t["n"], format(t["i"], ","), format(t["o"], ","), t["c"], format(t["med"], ","), cost(t["i"], t["o"])))
    ii = [r["usage"].get("input_tokens", 0) for r in have]
    oo = [r["usage"].get("output_tokens", 0) for r in have]
    cc = [r["usage"].get("calls", 0) for r in have]
    tot.update(i=sum(ii), o=sum(oo), c=sum(cc), n=len(have))
    p("| (d) reach 10 x 2 x 3 | %d | %s | %s | %d | %s | %.2f |" % (len(have), format(sum(ii), ","), format(sum(oo), ","), sum(cc), format(int(statistics.median(ii)) if ii else 0, ","), cost(sum(ii), sum(oo))))
    p("| all | %d | %s | %s | %d | | %.2f |" % (tot["n"], format(tot["i"], ","), format(tot["o"], ","), tot["c"], cost(tot["i"], tot["o"])))
    prev = Counter()
    for k in ("bank2", "unans", "adv"):
        t = tokens(old[k])
        prev.update(i=t["i"], o=t["o"], c=t["c"], n=t["n"])
    p("(v1 measurement, same three sets, loom modes: %d runs, %s in / %s out, %d calls, %.2f USD at the same price)" % (prev["n"], format(prev["i"], ","), format(prev["o"], ","), prev["c"], cost(prev["i"], prev["o"])))
    for lab, R in (("v1", [r for k in old for r in loom(old[k])]), ("v2", [r for k in new for r in loom(new[k])])):
        ii = [r["usage"].get("input_tokens", 0) for r in R]
        p("median input tokens per run, sets (a)+(b)+(c), %s: %s" % (lab, format(int(statistics.median(ii)), ",")))
    print("\n".join(P))


if __name__ == "__main__":
    main()
