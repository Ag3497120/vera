"""T3-2: W14 の C 系を W16-t3 の木で流し直した結果を数える。run1 の C は同じスクリプトで旧の物差しを再計算する（0 を引用で済ませない）。"""
import collections
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ART = os.path.abspath(os.path.join(HERE, ".."))
W14 = "/Users/motonisihikoudai/Projects/vera-impl/wt/W14-bench-S"
sys.path.append(W14)
from benchmarks.public_v1 import data as D, score as SC  # noqa: E402

RUN1 = W14 + "/artifacts/w14-bench/run1/C/results.jsonl"
NEW = os.path.join(ART, "w14", "C", "results.jsonl")
R2 = None
if "--new" in sys.argv:                  # 第 3 ラウンド: 入力のパスを指定（既定は第 2 ラウンドの出力のまま）
    NEW = os.path.abspath(sys.argv[sys.argv.index("--new") + 1])
if "--r2" in sys.argv:                   # 比較用に第 2 ラウンドの results.jsonl
    R2 = os.path.abspath(sys.argv[sys.argv.index("--r2") + 1])


def rows(p):
    return [json.loads(l) for l in open(p, encoding="utf-8")]


def old_measure(rs):
    per = [len(SC.vera_verified_sources(r)) for r in rs]
    return sum(per), sum(1 for x in per if x)


def pos_of(q):
    if q["found"] == "exact":
        return ["%s:%s" % (q["source"], q["line"])]
    if q["found"] == "relocated":
        return list(q.get("relocated_to") or [])
    return []


def main():
    cats = {q["id"]: q["cat"] for q in D.load_questions()}
    r1, r2 = rows(RUN1), rows(NEW)
    L = ["T3-2: W14 の C 系（Vera 既定、qwen3.5:4b、温度 0）。run1 = %s、今回 = %s" % (RUN1, NEW), "行数: run1 %d、今回 %d" % (len(r1), len(r2)), ""]
    s1, n1 = old_measure(r1)
    s2, n2 = old_measure(r2)
    L += ["旧の物差し（score.vera_verified_sources の合計。reading.sources と provenance の evidence）を同じスクリプトで再計算:",
          "  run1: 出所の数の合計 %d、1 つ以上ある行 %d / %d" % (s1, n1, len(r1)), "  今回: 出所の数の合計 %d、1 つ以上ある行 %d / %d" % (s2, n2, len(r2)), ""]
    qc_rows = [r for r in r2 if (r.get("vera") or {}).get("quote_check") is not None]
    L.append("今回の行のうち vera.quote_check がある行: %d / %d（0 なら W14 の木を測っている）" % (len(qc_rows), len(r2)))
    dist = collections.Counter(((r.get("vera") or {}).get("quote_check") or {}).get("verdict", "(鍵なし)") for r in r2)
    L.append("印の分布（行）: " + json.dumps(dict(dist), ensure_ascii=False))
    z = sum(1 for r in qc_rows if r["vera"]["quote_check"]["verdict"] == "anchored" and not r["vera"]["quote_check"]["elements"])
    L.append("anchored のうち答えの要素が 0 個の行: %d / %d" % (z, dist.get("anchored", 0)))
    reasons = collections.Counter(((r.get("vera") or {}).get("quote_check") or {}).get("reason") for r in qc_rows)
    L.append("reason の分布: " + json.dumps(dict(reasons), ensure_ascii=False))
    found = collections.Counter(q["found"] for r in qc_rows for q in r["vera"]["quote_check"]["quotes"])
    L.append("引用 %d 個の found の分布: %s" % (sum(found.values()), dict(found)))
    entries = per_row = 0
    uniq = set()
    rows_with = 0
    for r in qc_rows:
        ps = []
        for q in r["vera"]["quote_check"]["quotes"]:
            p = pos_of(q)
            entries += 1 if p else 0
            ps += p
        u = set(ps)
        per_row += len(u)
        rows_with += 1 if u else 0
        uniq |= {(r["docset"], x) for x in u}
    L += ["", "「Vera が確かめた出典」（新: exact／relocated の引用の位置）:",
          "  実在した引用の数: %d" % entries, "  行ごとに重複を除いた位置の数の合計: %d（1 つ以上ある行 %d / %d）" % (per_row, rows_with, len(r2)),
          "  docset をまたいで重複を除いた位置の数: %d" % len(uniq), "  （run1 の 0 は 旧の物差し。新と旧は定義が違うので、この 2 つの数を直接の比較に使わない）", ""]
    L.append("印 × W14 の cat（参考。正解との突き合わせは人の採点の領分で、合否には使わない）:")
    tab = collections.defaultdict(collections.Counter)
    for r in r2:
        tab[cats.get(r["id"], "?")][((r.get("vera") or {}).get("quote_check") or {}).get("verdict", "(鍵なし)")] += 1
    for c in sorted(tab):
        L.append("  %-6s %s" % (c, json.dumps(dict(tab[c]), ensure_ascii=False)))
    ov = collections.Counter(((r.get("vera") or {}).get("outcome") or {}).get("outcome") for r in r2)
    L += ["", "outcome の分布: " + json.dumps(dict(ov), ensure_ascii=False)]
    rd = collections.Counter(((r.get("vera") or {}).get("reading") or {}).get("type") for r in r2)
    L.append("reading.type の分布: " + json.dumps(dict(rd), ensure_ascii=False))
    nf = sum(1 for r in r2 if not r.get("ok"))
    L.append("ok でない行: %d" % nf)
    wall = [r["wall_ms"] for r in r2]
    w1 = [r["wall_ms"] for r in r1]
    L.append("wall_ms の合計: 今回 %.0f 秒、run1 %.0f 秒" % (sum(wall) / 1000.0, sum(w1) / 1000.0))
    if R2:
        w2 = [r["wall_ms"] for r in rows(R2)]
        L.append("wall_ms の合計（3 つ）: run1 %.0f 秒、第 2 ラウンド %.0f 秒、今回 %.0f 秒" % (sum(w1) / 1000.0, sum(w2) / 1000.0, sum(wall) / 1000.0))
    nc = sum(1 for r in qc_rows if ((r["vera"]["quote_check"].get("reason")) or "").startswith("ANSWER_CONTENT_NOT_IN_QUOTE"))
    nj = sum(1 for r in r2 if (((r.get("vera") or {}).get("quote_check") or {}).get("reason")) == "REPLY_NOT_JSON")
    L.append("reason ANSWER_CONTENT_NOT_IN_QUOTE の行: %d、REPLY_NOT_JSON の行: %d（num_predict で JSON が切れた可能性）" % (nc, nj))
    tl = collections.Counter(((r.get("vera") or {}).get("llm") or {}).get("error", {}).get("type") if isinstance(((r.get("vera") or {}).get("llm") or {}).get("error"), dict) else None for r in r2)
    L.append("llm.error.type の分布: " + json.dumps(dict(tl), ensure_ascii=False))
    print("\n".join(L))


if __name__ == "__main__":
    main()
