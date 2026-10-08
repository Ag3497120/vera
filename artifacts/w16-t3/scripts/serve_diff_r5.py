"""第 5 ラウンド: serve の 310 行を r4c の出力と行ごとに比べ、違う行の id・quote_check の verdict／reason の新旧・本文の最後の 1 行の新旧を全件出す。
使い方: serve_diff_r5.py OLD.jsonl NEW.jsonl"""
import json
import sys

A = [json.loads(l) for l in open(sys.argv[1], encoding="utf-8") if l.strip()]
B = [json.loads(l) for l in open(sys.argv[2], encoding="utf-8") if l.strip()]
assert len(A) == len(B), (len(A), len(B))


def qc(r):
    v = (r.get("res") or {}).get("vera") or {}
    d = v.get("quote_check") or {}
    return d.get("verdict"), d.get("reason")


def last(r):
    c = ((r.get("res") or {}).get("content")) or ""
    return c.strip().splitlines()[-1] if c.strip() else ""


n = nonqc = 0
for x, y in zip(A, B):
    if x == y:
        continue
    n += 1
    assert x["id"] == y["id"]
    # quote_check と本文の添え書き以外が変わっていないか: 両方から quote_check を除き、本文の最後の行を除いて比べる
    def strip(r):
        r = json.loads(json.dumps(r))
        v = (r.get("res") or {}).get("vera") or {}
        v.pop("quote_check", None)
        c = (r.get("res") or {}).get("content")
        if isinstance(c, str):
            r["res"]["content"] = "\n".join(c.strip().splitlines()[:-1])
        return r
    other = strip(x) != strip(y)
    nonqc += other
    print("%s old=%s new=%s | 最後の行 old=%r new=%r%s" % (x["id"], qc(x), qc(y), last(x), last(y), "  [quote_check・本文の最後の行以外も違う]" if other else ""))
print("違う行: %d / %d" % (n, len(A)))
print("quote_check・本文の最後の 1 行以外も違う行: %d" % nonqc)
