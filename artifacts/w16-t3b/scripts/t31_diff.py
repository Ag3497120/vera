"""W16-t3b: 2 つの t31_result.json（基点・新）の rows を id で突き合わせ、印か reason か to_dict が変わった行を全件出す。使い方: t31_diff.py 基点.json 新.json"""
import json
import sys
old = {r["id"]: r for r in json.load(open(sys.argv[1]))["rows"]}
new = {r["id"]: r for r in json.load(open(sys.argv[2]))["rows"]}
assert old.keys() == new.keys()
n_wrong_fix = n_false_up = n_to_anch = n_changed = n_dict = 0
for i in sorted(new):
    o, n = old[i], new[i]
    if o["qc"] != n["qc"]:
        n_dict += 1
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
print("to_dict（全体）が変わった行: %d / %d" % (n_dict, len(new)))
print("誤答で anchored -> 非 anchored になった数: %d" % n_wrong_fix)
print("正しい ANS（wrong=false, cat=ANS）で anchored -> 非 anchored（偽の錨なしの増加）: %d" % n_false_up)
print("anchored 以外 -> anchored（あってはならない）: %d" % n_to_anch)
