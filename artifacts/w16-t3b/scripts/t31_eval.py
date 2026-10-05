"""T3-1: 60 候補に quote_check.check を直接掛け、(a) LLM 自身の引用を信じる と (b) Vera の照合を比べる。式は docs/FUSION.md §9.2（事前登録）。
加えて同じ 60 候補を serve の経路（偽の LLM が候補の JSON を返す）に通し、vera.quote_check が直接の結果と同じかを t31_serve_path.txt に残す。"""
import collections
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ART = os.path.abspath(os.path.join(HERE, ".."))
WROOT = os.path.abspath(os.path.join(ART, "..", ".."))
from benchmarks.public_v1 import data as D  # noqa: E402
from verantyx import decode_grammar as G  # noqa: E402
from verantyx import quote_check as QC  # noqa: E402
from verantyx import vera_server as VS  # noqa: E402

assert all(m.__file__.startswith(os.path.abspath(os.path.join(ART, "..", "..")) + "/") for n, m in sys.modules.items() if n.startswith("verantyx") and getattr(m, "__file__", None))


def pct(a, b):
    return "%d/%d = %s" % (a, b, ("%.1f%%" % (100.0 * a / b)) if b else "n/a")


def main():
    assert "--out" in sys.argv, "--out is required"
    OUT = os.path.abspath(sys.argv[sys.argv.index("--out") + 1])
    os.makedirs(OUT, exist_ok=True)
    items = [json.loads(l) for l in open(os.path.join(WROOT, "artifacts", "w16-t3", "t31", "items.jsonl"), encoding="utf-8")]
    recs = {}
    for ds in ("S1", "S2", "S3", "S4"):
        recs[ds] = G.load_records([D.doc_path(f) for f in D.docset_files(ds)])
    rows = []
    for it in items:
        c = it["candidate"]
        r = QC.check(c["answer"], c["quotes"], recs[it["docset"]], question=it["question"])
        rows.append(dict(id=it["id"], cat=it["cat"], type=it["type"], wrong=it["wrong"], n_quotes=len(c["quotes"]), verdict=r.verdict, reason=r.reason, uncovered=list(r.uncovered),
                         found=[q["found"] for q in r.quotes], n_elements=len(r.elements), skipped=r.skipped, qc=r.to_dict()))
    wrong = [r for r in rows if r["wrong"]]
    ok_ans = [r for r in rows if not r["wrong"] and r["cat"] == "ANS"]
    ok_none = [r for r in rows if not r["wrong"] and r["cat"] == "NONE"]
    a_det = sum(1 for r in wrong if r["n_quotes"] == 0)
    b_det = sum(1 for r in wrong if r["verdict"] != "anchored")
    by_type = {}
    for t in ("W1", "W2", "N1", "N2"):
        rs = [r for r in wrong if r["type"] == t]
        by_type[t] = {"n": len(rs), "a": sum(1 for r in rs if r["n_quotes"] == 0), "b": sum(1 for r in rs if r["verdict"] != "anchored"),
                      "verdicts": dict(collections.Counter(r["verdict"] for r in rs))}
    fp = sum(1 for r in ok_ans if r["verdict"] != "anchored")
    res = {"n_items": len(rows), "n_wrong": len(wrong), "a_detect": a_det, "b_detect": b_det, "by_type": by_type,
           "false_alarm": fp, "n_ok_ans": len(ok_ans), "none_ok_verdicts": dict(collections.Counter(r["verdict"] for r in ok_none)), "n_ok_none": len(ok_none),
           "anchored_with_zero_elements": sum(1 for r in rows if r["verdict"] == "anchored" and r["n_elements"] == 0),
           "anchored_with_zero_elements_among_wrong": sum(1 for r in wrong if r["verdict"] == "anchored" and r["n_elements"] == 0),
           "skipped_total": sum(r["skipped"] for r in rows), "rows": rows}
    json.dump(res, open(os.path.join(OUT, "t31_result.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    L = ["T3-1（自作の集合。通っても証拠にならない。T3-4 の伏せた集合が本番）",
         "(a) LLM 自身の引用を信じる: 検出 %s" % pct(a_det, len(wrong)),
         "(b) Vera の照合:            検出 %s" % pct(b_det, len(wrong)),
         "上乗せ (b)-(a): %d 件（%+.1f 点）" % (b_det - a_det, 100.0 * (b_det - a_det) / len(wrong)),
         "誤検出（正しい ANS %d のうち anchored 以外）: %s" % (len(ok_ans), pct(fp, len(ok_ans))),
         "型ごとの検出（a / b）:"]
    for t, v in by_type.items():
        L.append("  %s n=%d  a=%d  b=%d  印=%s" % (t, v["n"], v["a"], v["b"], v["verdicts"]))
    L += ["NONE の正しい候補 %d の印の分布: %s（誤検出の分母に入れない）" % (len(ok_none), res["none_ok_verdicts"]),
          "要素 0 個で anchored: 全 %d 件のうち %d、誤答のうち %d" % (len(rows), res["anchored_with_zero_elements"], res["anchored_with_zero_elements_among_wrong"]),
          "取り出せなかった漢数字の並び（skipped）: %d" % res["skipped_total"]]
    miss = [r for r in wrong if r["verdict"] == "anchored"]
    zero = [r for r in miss if r["n_elements"] == 0]
    some = [r for r in miss if r["n_elements"] > 0]
    L.append("誤答なのに anchored（見逃し）: %d = 要素 0 個 %s ＋ 要素あり %s" % (
        len(miss), "%d（%s）" % (len(zero), ", ".join("%s %d" % kv for kv in sorted(collections.Counter(r["type"] for r in zero).items()))),
        "%d（%s）" % (len(some), ", ".join("%s %d" % kv for kv in sorted(collections.Counter(r["type"] for r in some).items())))))
    for r in some:
        L.append("  要素あり・見逃し: %-12s %-3s 要素=%s" % (r["id"], r["type"], [(e["kind"], e["value"], e["found_in"]) for e in r["qc"]["elements"]]))
    r3b = [r for r in wrong if r["verdict"] == "unanchored" and (r["reason"] or "").startswith("ANSWER_CONTENT_NOT_IN_QUOTE")]
    L.append("誤答のうち規則 3b（ANSWER_CONTENT_NOT_IN_QUOTE）で unanchored になった件: %d（%s）" % (len(r3b), ", ".join(r["id"] for r in r3b)))
    fa = [r for r in ok_ans if r["verdict"] != "anchored"]
    L.append("誤検出（正しい ANS で anchored でない）の一覧: %d 件" % len(fa))
    for r in fa:
        L.append("  誤検出: %-12s -> %s reason=%s 未被覆=%s" % (r["id"], r["verdict"], r["reason"], r["uncovered"]))
    fa3b = [r for r in ok_ans + ok_none if r["verdict"] != "anchored" and (r["reason"] or "").startswith("ANSWER_CONTENT_NOT_IN_QUOTE")]
    L.append("正しい候補（ANS・NONE）のうち規則 3b で anchored でなくなった件（第 2 ラウンドでは anchored だったかは t31_result.txt の 1 行目以降と比べる）: %d" % len(fa3b))
    for r in fa3b:
        L.append("  3b の偽の錨なし: %-12s %s 未被覆=%s" % (r["id"], r["cat"], r["uncovered"]))
    L += ["", "候補ごとの印:"]
    for r in rows:
        L.append("  %-12s %-4s wrong=%-5s quotes=%d found=%s elements=%d -> %s" % (r["id"], r["type"], r["wrong"], r["n_quotes"], ",".join(r["found"]) or "-", r["n_elements"], r["verdict"]))
    open(os.path.join(OUT, "t31_result.txt"), "w", encoding="utf-8").write("\n".join(L) + "\n")

    # serve の経路（同じ 60 候補。偽の LLM が候補の JSON を返す）
    S = []
    same = diff = skipped_rec = 0
    cfgs = {}
    for it in items:
        c = it["candidate"]
        cfg = cfgs.get(it["docset"])
        if cfg is None:
            cfg = VS.FusionConfig.load(model="fake-model", documents=[D.doc_path(f) for f in D.docset_files(it["docset"])], llm_chat=None)
            cfgs[it["docset"]] = cfg
        calls = []

        def fake(model, messages, fmt, _c=c, _calls=calls):
            _calls.append(1)
            return {"ok": True, "content": json.dumps(_c, ensure_ascii=False), "error": None, "usage": {}}
        cfg.llm_chat = fake
        out = VS.fusion_turn([{"role": "user", "content": it["question"]}], {"request_kind": "factual"}, cfg)
        direct = [r for r in rows if r["id"] == it["id"]][0]["qc"]
        got = out["vera"].get("quote_check")
        if not calls:
            skipped_rec += 1
            S.append("%-12s %-4s LLM_NOT_CALLED reading=%s（記録が答えた。quote_check なし）" % (it["id"], it["type"], out["vera"]["reading"]["type"]))
        elif got == direct:
            same += 1
            S.append("%-12s %-4s SAME verdict=%s" % (it["id"], it["type"], got["verdict"]))
        else:
            diff += 1
            S.append("%-12s %-4s DIFFERENT serve=%s direct=%s" % (it["id"], it["type"], json.dumps(got, ensure_ascii=False)[:200], json.dumps(direct, ensure_ascii=False)[:200]))
    hdr = ["serve の経路（FusionConfig + 偽の LLM）に 60 候補を通した: 同じ %d、違う %d、LLM を呼ばなかった（記録が答えた）%d" % (same, diff, skipped_rec)]
    open(os.path.join(OUT, "t31_serve_path.txt"), "w", encoding="utf-8").write("\n".join(hdr + S) + "\n")
    print(open(os.path.join(OUT, "t31_result.txt"), encoding="utf-8").read())


if __name__ == "__main__":
    main()
