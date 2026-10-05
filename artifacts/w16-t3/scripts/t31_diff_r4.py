"""第 4 ラウンド: r3b/t31_result.json と r4/t31_result.json の rows を id で突き合わせ、印か reason が変わった行を全件出す。"""
import json
W = "/Users/motonisihikoudai/Projects/vera-impl/wt/W16-t3-S/artifacts/w16-t3"
old = {r["id"]: r for r in json.load(open(W + "/r3b/t31_result.json"))["rows"]}
new = {r["id"]: r for r in json.load(open(W + "/r4/t31_result.json"))["rows"]}
assert old.keys() == new.keys()
n_wrong_fix = n_false_up = n_to_anch = n_changed = 0
for i in sorted(new):
    o, n = old[i], new[i]
    if (o["verdict"], o["reason"]) == (n["verdict"], n["reason"]):
        continue
    n_changed += 1
    q = n["qc"]["quotes"][0]["text"] if n["qc"]["quotes"] else ""
    print("%s %s wrong=%s %s->%s reason=%s 引用=%s" % (i, n["type"], n["wrong"], o["verdict"], n["verdict"], n["reason"], q))
    if o["verdict"] == "anchored" and n["verdict"] != "anchored":
        if n["wrong"]:
            n_wrong_fix += 1
        elif n["cat"] == "ANS":
            n_false_up += 1
    if o["verdict"] != "anchored" and n["verdict"] == "anchored":
        n_to_anch += 1
print("印か reason が変わった行: %d / %d" % (n_changed, len(new)))
print("誤答で anchored -> 非 anchored になった数: %d" % n_wrong_fix)
print("正しい ANS（wrong=false, cat=ANS）で anchored -> 非 anchored（偽の錨なしの増加）: %d" % n_false_up)
print("anchored 以外 -> anchored（あってはならない）: %d" % n_to_anch)
