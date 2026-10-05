"""M3 の再流しの確認: 2 つの run_paths.py の出力（new）を、行ごとに (ask の out の verdict/values/evidence、serve の reading、chat の out) で比べる。
usage: rerun_check.py A.jsonl B.jsonl"""
import json
import sys


def rows(p):
    return {r["id"]: r for r in (json.loads(l) for l in open(p, encoding="utf-8") if l.strip())}


def sig(r):
    o, c = (r["ask"]["out"] or {}), (r["chat"]["out"] or {})
    return (tuple(json.dumps(o.get(k), ensure_ascii=False, sort_keys=True) for k in ("verdict", "values", "evidence")), json.dumps(r["serve"], ensure_ascii=False, sort_keys=True),
            tuple(json.dumps(c.get(k), ensure_ascii=False, sort_keys=True) for k in ("verdict", "values", "evidence")))


a, b = rows(sys.argv[1]), rows(sys.argv[2])
bad = [i for i in a if i not in b or sig(a[i]) != sig(b[i])]
print("rows: %d vs %d; differing rows: %d %s" % (len(a), len(b), len(bad), bad[:10]))
sys.exit(1 if bad or set(a) != set(b) else 0)
