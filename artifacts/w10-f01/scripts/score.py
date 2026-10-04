"""W10-f01: 採点（docs/FUSION.md §1.8 の定義）。

  python score.py --questions Q.jsonl --run RUN.jsonl --out SCORE.json   -> 人が読む形を標準出力に
"""
import argparse
import json
import statistics
import unicodedata
from collections import Counter

ANSWER = ("ANSWER_HUMAN_BASIS", "ANSWER_FORM_FROM_GENERATED", "REFERENCE_GENERATED")


def nf(s):
    return unicodedata.normalize("NFKC", str(s)).strip()


def stats(xs):
    return {"n": len(xs), "median": round(statistics.median(xs), 1), "max": round(max(xs), 1)} if xs else {"n": 0, "median": None, "max": None}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--questions", required=True)
    ap.add_argument("--run", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    qs = {}
    for l in open(a.questions, encoding="utf-8"):
        if l.strip():
            r = json.loads(l)
            qs[r["id"]] = r
    runs = {}
    for l in open(a.run, encoding="utf-8"):
        if l.strip():
            r = json.loads(l)
            runs[r["id"]] = r
    one = {"n": 0, "correct": 0, "wrong": 0, "missed": 0, "missed_by": Counter(), "wrong_ids": []}
    none = {"n": 0, "correct": 0, "wrong": 0, "llm_called": 0, "testimony_shown": 0, "record_marked_sentences": 0, "wrong_ids": [], "wrong_reasons": {}}
    cre = {"n": 0, "constructed": 0, "abstained": 0, "wrong": 0, "abstained_by": Counter(), "wrong_ids": []}
    errors, gen_only = [], []
    lat = {"vera_ms_llm_called": [], "vera_ms_llm_not_called": [], "llm_ms": [], "wall_ms": []}
    layers = Counter()
    missing = [i for i in qs if i not in runs]
    for qid, q in qs.items():
        r = runs.get(qid)
        if r is None:
            continue
        v = (r.get("response") or {}).get("vera")
        if r.get("http_status") != 200 or not isinstance(v, dict):
            errors.append(qid)
            continue
        layers[v.get("layer")] += 1
        oc = v["outcome"]["outcome"]
        shown = bool(v["outcome"]["content_shown"])
        content = r["response"]["choices"][0]["message"]["content"]
        prov = v.get("provenance") or []
        rec_sents = [p for p in prov if p.get("sentence_kind") == "record"]
        t = v.get("timing") or {}
        (lat["vera_ms_llm_called"] if v["llm"]["called"] else lat["vera_ms_llm_not_called"]).append(t.get("vera_ms", 0))
        if v["llm"]["called"]:
            lat["llm_ms"].append(t.get("llm_ms", 0))
        lat["wall_ms"].append(r.get("wall_ms", 0))
        is_answer = oc in ANSWER
        if is_answer and not rec_sents:
            gen_only.append(qid)
        kind = q["truth"]["kind"]
        if kind == "ONE":
            one["n"] += 1
            if is_answer:
                ev = {s["sentence_id"] for s in v["reading"]["sources"]}
                ok = (oc == "ANSWER_HUMAN_BASIS" and nf(v["reading"]["filler"] or "") == nf(q["truth"]["filler"]) and ev == set(q["truth"]["sentence_ids"])
                      and nf(q["truth"]["filler"]) in nf(content))
                if ok:
                    one["correct"] += 1
                else:
                    one["wrong"] += 1
                    one["wrong_ids"].append(qid)
            else:
                one["missed"] += 1
                one["missed_by"]["%s|%s|%s" % (oc, v["reading"]["type"], v["reading"]["state"])] += 1
        elif kind == "NONE":
            none["n"] += 1
            if v["llm"]["called"]:
                none["llm_called"] += 1
            if oc == "TESTIMONY":
                none["testimony_shown"] += 1
            none["record_marked_sentences"] += len(rec_sents)
            reasons = []
            if is_answer:
                reasons.append("ANSWER_CLASS")
            if v.get("layer") == 1 and shown:
                reasons.append("LLM_TEXT_SHOWN_IN_STRICT")
            if v.get("layer") == 0 and shown and oc != "TESTIMONY":
                reasons.append("CONTENT_SHOWN_WITHOUT_TESTIMONY_MARK")
            if v.get("layer") == 0 and rec_sents:
                reasons.append("RECORD_MARKED_SENTENCE")
            if reasons:
                none["wrong"] += 1
                none["wrong_ids"].append(qid)
                none["wrong_reasons"][qid] = reasons
            else:
                none["correct"] += 1
        else:
            cre["n"] += 1
            if is_answer:
                cre["wrong"] += 1
                cre["wrong_ids"].append(qid)
            elif oc == "CONSTRUCTED":
                cre["constructed"] += 1
            else:
                cre["abstained"] += 1
                cre["abstained_by"][oc] += 1
    wrong = one["wrong"] + none["wrong"] + cre["wrong"]
    res = {"questions": len(qs), "answered_by_run": len(runs), "missing": missing, "http_or_shape_errors": errors, "layers": dict(layers), "wrong": wrong,
           "generated_only_answers": len(gen_only), "generated_only_answer_ids": gen_only, "one": dict(one, missed_by=dict(one["missed_by"])), "none": none,
           "creative": dict(cre, abstained_by=dict(cre["abstained_by"])),
           "latency_ms": {k: stats(v) for k, v in lat.items()}}
    json.dump(res, open(a.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("layers=%s wrong=%d generated_only_answers=%d errors=%d missing=%d" % (dict(layers), wrong, len(gen_only), len(errors), len(missing)))
    print("ONE   n=%d correct=%d wrong=%d missed=%d" % (one["n"], one["correct"], one["wrong"], one["missed"]))
    for k, n in sorted(one["missed_by"].items(), key=lambda kv: -kv[1]):
        print("        missed %3d  %s" % (n, k))
    print("NONE  n=%d correct=%d wrong=%d llm_called=%d testimony_shown=%d record_marked_sentences=%d" % (none["n"], none["correct"], none["wrong"], none["llm_called"], none["testimony_shown"], none["record_marked_sentences"]))
    for qid, rs in none["wrong_reasons"].items():
        print("        WRONG %s %s" % (qid, ",".join(rs)))
    print("CREATIVE n=%d constructed=%d abstained=%d wrong=%d" % (cre["n"], cre["constructed"], cre["abstained"], cre["wrong"]))
    for k, n in cre["abstained_by"].items():
        print("        abstained %3d  %s" % (n, k))
    for k, s in res["latency_ms"].items():
        print("latency %-24s n=%d median=%s max=%s" % (k, s["n"], s["median"], s["max"]))


if __name__ == "__main__":
    main()
