"""k606_before と k606_after_r2 の --record 出力 (rec_*.jsonl) を、ts/hash/seq/store_id/prev/sha を除いて比べ、attest_id を並べる。"""
import json, sys
b, a = sys.argv[1:3]
ok = True
for n in ("none", "led_add", "led_run"):
    def rows(d):
        out = []
        for ln in open(f"{d}/rec_{n}.jsonl", encoding="utf-8"):
            if ln.strip():
                r = json.loads(ln)
                for k in ("ts", "hash", "seq", "store_id", "prev", "sha"):
                    r.pop(k, None)
                out.append(r)
        return out
    rb, ra = rows(b), rows(a)
    ids = lambda rs: [r.get("attest_id") or (r.get("data") or {}).get("attest_id") for r in rs]
    same = rb == ra
    ok &= same
    print(n, "rows_same=%s" % same, "n=%d/%d" % (len(rb), len(ra)), "attest_id before=%s after=%s" % (ids(rb), ids(ra)))
print("ALL_SAME" if ok else "SOME_DIFF")
