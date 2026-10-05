"""W16-t2 比較: old_*.jsonl と new_*.jsonl（run_paths.py の出力）を行ごとに 正答(correct)／誤答(wrong)／棄権(abstain) に分け、変わった行を全件列挙する。
判定は docs/OBSERVATION.md「W16-t2（事前登録）」のとおり: 答えの表層（values。無ければ text の「role: 値」の値）が gold.values のどれかと NFKC で等しければ正答、
gold が ABSTAIN で答えたら誤答、ANSWER でない出力は棄権。旧の最大 = 旧 ask・旧 serve のどちらかが正答。
  compare.py --out t2_compare.txt --withheld t2_1_serve_withheld.tsv NAME=OLD:NEW ...
"""
import argparse
import json
import unicodedata
from collections import Counter

NF = lambda s: unicodedata.normalize("NFKC", str(s)).strip()


def surfaces_of_out(o):
    if not isinstance(o, dict) or o.get("verdict") != "ANSWER":
        return None
    vals = o.get("values")
    if isinstance(vals, list) and vals:
        return [NF(v) for v in vals]
    return [NF(p.split(": ", 1)[-1]) for p in (o.get("text") or "").split("、") if p.strip()]


def surfaces_of_reading(r):
    if isinstance(r, dict) and r.get("type") == "QUESTION_CROSS" and r.get("filler") is not None:
        return [NF(r["filler"])]
    return None


def cls(gold, surf):
    if surf is None:
        return "abstain"
    if gold["verdict"] == "NOT_JUDGED":
        return "notjudged"
    if gold["verdict"] != "ANSWER":
        return "wrong"
    return "correct" if len(surf) == 1 and surf[0] in {NF(v) for v in gold["values"]} else "wrong"


def rows_of(path):
    return {r["id"]: r for r in (json.loads(l) for l in open(path, encoding="utf-8") if l.strip())}


def ar_key(a):
    return json.dumps({k: a.get(k) for k in ("verdict", "values", "evidence")}, ensure_ascii=False, sort_keys=True)


ENT = ("ask", "serve", "chat")


def entrance_class(row, ent):
    """(class, surfaces) of one entrance of one row of a jsonl; ("n/a", None) when the row has no such entrance (an old jsonl without chat)."""
    if ent == "serve":
        surf = surfaces_of_reading(row.get("serve"))
    else:
        if ent not in row:
            return "n/a", None
        surf = surfaces_of_out((row.get(ent) or {}).get("out"))
    return cls(row["gold"], surf), surf


def round2(specs):
    """W16-t2 round 2 (rulings 1, 2, 5; docs/OBSERVATION.md 'pre-registration change'): per-entrance transitions (own old -> new), the T2-2 (a)-(d) judgement per set and in total,
    the enumeration of the rows that matter, the number of calls (rows with documents vs. rows without), and the no-placement listing."""
    L = ["", "######## round 2: per-entrance transitions and T2-2 (a)-(d) ########"]
    tot_wrong_new = {e: set() for e in ENT}
    tot_old_ask_wrong = set()
    tot_correct = {e: 0 for e in ENT}
    tot_old_max = 0
    tot_old_max_by = {e: 0 for e in ENT}
    tot_ar_serve = [0]
    tot_d = [0, 0]          # w3f1 NOT_JUDGED rows: [checked, equal]
    tot_calls = Counter()
    trans_tot = {e: Counter() for e in ENT}
    for spec in specs:
        name, files = spec.split("=")
        of, nf = files.split(":")
        old, new = rows_of(of), rows_of(nf)
        L.append("== [%s] n=%d" % (name, len(new)))
        trans = {e: Counter() for e in ENT}
        listed = []
        oldcls = {e: {} for e in ENT}
        newcls = {e: {} for e in ENT}
        calls = Counter()
        d_checked = d_equal = 0
        d_diff = []
        only_old, first_new = [], []
        for i, nr in new.items():
            o = old[i]
            for e in ENT:
                oc, osurf = entrance_class(o, e)
                nc, nsurf = entrance_class(nr, e)
                oldcls[e][i], newcls[e][i] = oc, nc
                trans[e]["%s->%s" % (oc, nc)] += 1
                if (oc == "abstain" and nc == "wrong") or (oc == "correct" and nc in ("abstain", "wrong")) or oc == "wrong":
                    listed.append("  ROW %s %s->%s | %s %s | gold=%s | old %s new %s" % (e, oc, nc, i, nr["question"], nr["gold"]["verdict"] + str(nr["gold"]["values"]), osurf, nsurf))
                if oc in ("correct", "wrong") and nc == "abstain":
                    only_old.append("  ONLY-OLD-ANSWERED %s %s (%s->abstain) %s | old %s" % (e, i, oc, nr["question"], osurf))
                if oc == "abstain" and nc in ("correct", "wrong", "notjudged") and nsurf is not None:
                    first_new.append("  NEW-FIRST-ANSWERED %s %s (abstain->%s) %s | new %s" % (e, i, nc, nr["question"], nsurf))
            # (d) w3f1: NOT_JUDGED rows: new ask == old ask on (verdict, values, evidence)
            if nr["gold"]["verdict"] == "NOT_JUDGED" and name == "w3f1":
                d_checked += 1
                ko = json.dumps({k: (o["ask"]["out"] or {}).get(k) for k in ("verdict", "values", "evidence")}, ensure_ascii=False, sort_keys=True)
                kn = json.dumps({k: (nr["ask"]["out"] or {}).get(k) for k in ("verdict", "values", "evidence")}, ensure_ascii=False, sort_keys=True)
                if ko == kn:
                    d_equal += 1
                else:
                    d_diff.append("  (d) DIFF %s %s | old %s | new %s" % (i, nr["question"], ko, kn))
            n_ask, n_serve, n_chat = (len(nr["ar_" + t]) if nr.get("ar_" + t) is not None else None for t in ENT)
            if (n_ask, n_serve, n_chat) == (1, 1, 1):
                calls["rows with documents: ask, serve and chat each called doc_answer.answer once"] += 1
            elif (n_ask, n_serve, n_chat) == (1, 0, 1) and nr["serve"].get("state") == "DOCUMENTS_NOT_LOADED":
                calls["rows without documents: ask and chat once, serve 0 (NO_RECORD/DOCUMENTS_NOT_LOADED, the function is not called; same as the base)"] += 1
            else:
                calls["UNEXPECTED %r" % ((n_ask, n_serve, n_chat),)] += 1
        for e in ENT:
            L.append("  transitions %s (own old -> new): %s" % (e, ", ".join("%s: %d" % (k, v) for k, v in sorted(trans[e].items()))))
            for k, v in trans[e].items():
                trans_tot[e][k] += v
        for k in sorted(calls):
            L.append("  calls: %d x %s" % (calls[k], k))
            tot_calls[k] += calls[k]
        # a transition table in one line per entrance for the grep of M1: "serve abstain->wrong: N"
        for e in ENT:
            for k in ("abstain->wrong", "correct->abstain", "correct->wrong"):
                L.append("  %s %s: %d" % (e, k, trans[e][k]))
            L.append("  %s wrong->*: %d" % (e, sum(v for k, v in trans[e].items() if k.startswith("wrong->"))))
        L.extend(sorted(set(listed)))
        L.append("  -- no-placement style listing (rows an entrance answered in old only / answered first in new) --")
        L.extend(only_old or ["  (none: no row that old answered and new abstains on)"])
        L.extend(first_new or ["  (none: no row that new answers and old abstained on)"])
        # (a)
        old_ask_wrong = {i for i, c in oldcls["ask"].items() if c == "wrong"}
        for e in ENT:
            nw = {i for i, c in newcls[e].items() if c == "wrong"}
            ok = nw <= old_ask_wrong
            L.append("T2-2a [%s] %s: new wrong ids subset of old ask wrong ids: %s (new wrong = %s; old ask wrong = %s)" % (name, e, "PASS" if ok else "FAIL", sorted(nw), sorted(old_ask_wrong)))
            tot_wrong_new[e] |= {name + ":" + i for i in nw}
        tot_old_ask_wrong |= {name + ":" + i for i in old_ask_wrong}
        # (b)
        by = {}
        for e in ENT:
            by[e] = sum(1 for c in oldcls[e].values() if c == "correct") if all(c != "n/a" for c in oldcls[e].values()) else None
        old_max = max(v for v in by.values() if v is not None)
        for e in ENT:
            nc_ = sum(1 for c in newcls[e].values() if c == "correct")
            L.append("T2-2b [%s] %s: new correct %d >= max(old ask, old serve, old chat) %d (old: %s): %s" % (name, e, nc_, old_max, ", ".join("%s=%s" % (k, v if v is not None else "n/a") for k, v in by.items()), "PASS" if nc_ >= old_max else "FAIL"))
            tot_correct[e] += nc_
        if all(nr.get("ar_serve") is not None for nr in new.values()):
            # informational: the serve rows by the AnswerResult the function returned (a row whose answer serve cannot show -- ROUND5_ANSWER_NOT_MAPPED, e.g. a yes/no -- counts as answered by the function)
            ar_c = sum(1 for i, nr in new.items() if nr["ar_serve"] and cls(nr["gold"], surfaces_of_out(nr["ar_serve"][0])) == "correct")
            tot_ar_serve[0] += ar_c
            L.append("T2-2b-info [%s] serve by AnswerResult (withheld rows counted as the function answered them): correct %d (shown by serve: %d)" % (name, ar_c, sum(1 for c in newcls["serve"].values() if c == "correct")))
        tot_old_max += old_max
        for e in ENT:
            if by[e] is not None:
                tot_old_max_by[e] += by[e]
        # (c)
        bad = sum(trans[e]["correct->wrong"] for e in ENT)
        L.append("T2-2c [%s] transitions enumerated above (abstain->wrong, correct->abstain, correct->wrong, wrong->*): %s (correct->wrong = %d)" % (name, "PASS" if bad == 0 else "FAIL", bad))
        # (d)
        if name == "w3f1":
            L.extend(d_diff)
            L.append("T2-2d [%s] NOT_JUDGED rows: new ask (verdict, values, evidence) == old ask: %s (%d of %d equal)" % (name, "PASS" if d_checked == d_equal else "FAIL", d_equal, d_checked))
            tot_d[0] += d_checked
            tot_d[1] += d_equal
        else:
            L.append("T2-2d [%s] n/a (only the w3f1 set has NOT_JUDGED rows by construction of its gold)" % name)
    L.append("== [TOTAL over the sets above]")
    for e in ENT:
        L.append("  transitions %s: %s" % (e, ", ".join("%s: %d" % (k, v) for k, v in sorted(trans_tot[e].items()))))
        for k in ("abstain->wrong", "correct->abstain", "correct->wrong"):
            L.append("  %s %s: %d" % (e, k, trans_tot[e][k]))
    for k in sorted(tot_calls):
        L.append("  calls: %d x %s" % (tot_calls[k], k))
    for e in ENT:
        ok = tot_wrong_new[e] <= tot_old_ask_wrong
        L.append("T2-2a [TOTAL] %s: new wrong ids subset of old ask wrong ids: %s (new wrong = %s; old ask wrong = %s)" % (e, "PASS" if ok else "FAIL", sorted(tot_wrong_new[e]), sorted(tot_old_ask_wrong)))
    old_max_total = max(tot_old_max_by.values())
    for e in ENT:
        L.append("T2-2b [TOTAL] %s: new correct %d >= max(old ask, old serve, old chat) summed over the sets %d (old totals: %s): %s" % (
            e, tot_correct[e], old_max_total, ", ".join("%s=%d" % kv for kv in tot_old_max_by.items()), "PASS" if tot_correct[e] >= old_max_total else "FAIL"))
    L.append("T2-2b-info [TOTAL] serve by AnswerResult: correct %d (shown by serve: %d)" % (tot_ar_serve[0], tot_correct["serve"]))
    L.append("T2-2c [TOTAL] see the per-set lines")
    L.append("T2-2d [TOTAL] w3f1 NOT_JUDGED rows equal: %s (%d of %d)" % ("PASS" if tot_d[0] == tot_d[1] else "FAIL", tot_d[1], tot_d[0]))
    return L


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--withheld", required=True)
    ap.add_argument("sets", nargs="+")
    a = ap.parse_args()
    L = []
    W = ["set\tid\tquestion\tanswer_result_values\treading_type\treading_state\treading_reason"]
    tot = Counter()
    for spec in a.sets:
        name, files = spec.split("=")
        of, nf = files.split(":")
        old, new = rows_of(of), rows_of(nf)
        c = Counter()
        L.append("== %s (old=%s new=%s, n=%d)" % (name, of, nf, len(new)))
        changed = []
        for i, nr in new.items():
            o = old[i]
            g = nr["gold"]
            oa = cls(g, surfaces_of_out(o["ask"]["out"])); os_ = cls(g, surfaces_of_reading(o["serve"]))
            na = cls(g, surfaces_of_out(nr["ask"]["out"])); ns = cls(g, surfaces_of_reading(nr["serve"])); nc = cls(g, surfaces_of_out((nr.get("chat") or {}).get("out")))
            for tag, v in (("old_ask", oa), ("old_serve", os_), ("new_ask", na), ("new_serve", ns), ("new_chat", nc)):
                c["%s_%s" % (tag, v)] += 1
            old_best_correct = "correct" in (oa, os_)
            for tag, v in (("ask", na), ("serve", ns), ("chat", nc)):
                if v == "wrong" and "wrong" not in (oa, os_):
                    c["wrong_new_not_in_old_%s" % tag] += 1
                if old_best_correct and v not in ("correct",):
                    c["correct_to_nonCorrect_%s" % tag] += 1
                    if v == "abstain":
                        c["correct_to_abstain_%s" % tag] += 1
            # AnswerResult の入口間の一致
            ars = {t: nr.get("ar_" + t) for t in ("ask", "serve", "chat")}
            counts = {t: (len(v) if v is not None else None) for t, v in ars.items()}
            if counts["ask"] != 1 or counts["chat"] != 1 or counts["serve"] not in (0, 1):
                c["answer_calls_unexpected"] += 1
                L.append("  CALLS %s %s: %r" % (i, nr["question"], counts))
            keys = {t: ar_key(v[0]) for t, v in ars.items() if v}
            if len(set(keys.values())) > 1:
                c["answer_result_mismatch"] += 1
                L.append("  AnswerResult mismatch %s %s: %r" % (i, nr["question"], keys))
            if ars["serve"] and ars["serve"][0].get("verdict") == "ANSWER" and ns != "correct" and surfaces_of_reading(nr["serve"]) is None:
                r = nr["serve"]
                W.append("\t".join([name, i, nr["question"], json.dumps(ars["serve"][0].get("values"), ensure_ascii=False), str(r.get("type")), str(r.get("state")), str(r.get("reason"))]))
            sig = lambda x: (x, )
            if (oa, os_) != (na, ns) or (na, ns) != (nc, nc) or surfaces_of_out(o["ask"]["out"]) != surfaces_of_out(nr["ask"]["out"]):
                changed.append("  %s %s | gold=%s | old ask=%s %s, old serve=%s %s | new ask=%s %s, new serve=%s %s, new chat=%s %s" % (
                    i, nr["question"], g["verdict"] + str(g["values"]), oa, surfaces_of_out(o["ask"]["out"]), os_, surfaces_of_reading(o["serve"]),
                    na, surfaces_of_out(nr["ask"]["out"]), ns, surfaces_of_reading(nr["serve"]), nc, surfaces_of_out((nr.get("chat") or {}).get("out"))))
        for k in sorted(c):
            L.append("  %s: %d" % (k, c[k]))
        L.append("  -- changed rows (any entrance differs from old ask/serve, or entrances differ) %d --" % len(changed))
        L.extend(changed)
        tot.update(c)
    L.append("== TOTAL ==")
    for k in sorted(tot):
        L.append("  %s: %d" % (k, tot[k]))
    L.append("wrong (new, all entrances): ask=%d serve=%d chat=%d" % (tot["new_ask_wrong"], tot["new_serve_wrong"], tot["new_chat_wrong"]))
    L.append("wrong that is NOT in old (new regressions into wrong): ask=%d serve=%d chat=%d" % (tot["wrong_new_not_in_old_ask"], tot["wrong_new_not_in_old_serve"], tot["wrong_new_not_in_old_chat"]))
    L.append("  (old = old ask OR old serve; per-entrance transitions and the T2-2 (a)-(d) judgement are below)")
    L.append("AnswerResult mismatch count: %d" % tot["answer_result_mismatch"])
    L.extend(round2(a.sets))
    open(a.out, "w", encoding="utf-8").write("\n".join(L) + "\n")
    open(a.withheld, "w", encoding="utf-8").write("\n".join(W) + "\n")


if __name__ == "__main__":
    main()
