"""W16-t3c M2/K656: 基点と新の serve 出力（同じスクリプト・同じ偽の LLM）を行ごとに比べ、変わった行を全件列挙する。
合格: (a) 行数が同じ (b) 変わった行はすべて新の vera.quote_check.verdict == anchored
(c) 変わった行の違いは content の 1 行目だけ（基点 = 旧い印、新 = 新しい印。2 行目以降と res の他の鍵・行の他の鍵は同一）
(d) quote_check が anchored の行はすべて変わっている（変わらない anchored 行 = 0）。
使い方: k656_compare.py BASE.jsonl NEW.jsonl OLD_MARK NEW_MARK"""
import collections, json, sys


def main(a, b, old_mark, new_mark):
    A = [json.loads(l) for l in open(a, encoding="utf-8")]
    B = [json.loads(l) for l in open(b, encoding="utf-8")]
    print("rows base", len(A), "new", len(B))
    if len(A) != len(B):
        print("LENGTH_MISMATCH"); return 1
    verdicts = collections.Counter()
    changed, bad, anchored_unchanged = [], [], []
    for i, (x, y) in enumerate(zip(A, B)):
        qc = (y.get("res") or {}).get("vera", {}).get("quote_check")
        v = qc["verdict"] if qc else None
        verdicts[v] += 1
        if x == y:
            if v == "anchored": anchored_unchanged.append((i, y["id"], y["layer"]))
            continue
        changed.append((i, y["id"], y["layer"], v))
        ok = v == "anchored" and "res" in x and "res" in y
        if ok:
            cx, cy = x["res"]["content"].split("\n"), y["res"]["content"].split("\n")
            ok = cx[0] == old_mark and cy[0] == new_mark and cx[1:] == cy[1:]
            x2 = json.loads(json.dumps(x)); x2["res"]["content"] = "\n".join([new_mark] + cx[1:])
            ok = ok and x2 == y
        if not ok: bad.append((i, y["id"], y["layer"], v))
    print("quote_check verdict (new):", dict(verdicts))
    print("changed rows:", len(changed))
    for c in changed: print("  CHANGED row=%d id=%s layer=%s verdict=%s" % c)
    print("changed rows that are not 'anchored, first line only' (pass = 0):", len(bad))
    for c in bad: print("  BAD row=%d id=%s layer=%s verdict=%s" % c)
    print("anchored rows that did not change (pass = 0):", len(anchored_unchanged))
    for c in anchored_unchanged: print("  UNCHANGED_ANCHORED row=%d id=%s layer=%s" % c)
    return 0 if not bad and not anchored_unchanged else 1


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:5]))
