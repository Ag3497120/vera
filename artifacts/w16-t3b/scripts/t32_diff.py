"""W16-t3b: t32_dump の 2 出力（基点・新）を行ごとに比べる。保存された vera.quote_check と今の to_dict の比較も出す。使い方: t32_diff.py 基点.jsonl 新.jsonl"""
import json
import sys
old = [json.loads(l) for l in open(sys.argv[1], encoding="utf-8")]
new = [json.loads(l) for l in open(sys.argv[2], encoding="utf-8")]
assert len(old) == len(new) and all((a["id"], a["rep"]) == (b["id"], b["rep"]) for a, b in zip(old, new))
diff = []
to_anch = 0
dist_old, dist_new, reasons = {}, {}, {}
saved_same_base = saved_same_new = 0
for a, b in zip(old, new):
    dist_old[a["qc"]["verdict"]] = dist_old.get(a["qc"]["verdict"], 0) + 1
    dist_new[b["qc"]["verdict"]] = dist_new.get(b["qc"]["verdict"], 0) + 1
    reasons[b["qc"].get("reason")] = reasons.get(b["qc"].get("reason"), 0) + 1
    saved_same_base += a["qc"] == a["saved"]
    saved_same_new += b["qc"] == b["saved"]
    if a["qc"] != b["qc"]:
        up = a["qc"]["verdict"] != "anchored" and b["qc"]["verdict"] == "anchored"
        to_anch += up
        diff.append("%s rep=%s cat=%s %s -> %s reason=%s->%s 答え=%s 引用=%s 問い=%s" % (
            b["id"], b["rep"], b["cat"], a["qc"]["verdict"], b["qc"]["verdict"], a["qc"].get("reason"), b["qc"].get("reason"), b["answer"],
            " / ".join(q.get("text", "") for q in b["qc"]["quotes"]), b["question"]))
lines = ["quote_check のある行: %d" % len(new), "基点のコードの to_dict が保存と同一: %d" % saved_same_base, "新しいコードの to_dict が保存と同一: %d" % saved_same_new,
         "基点と新で to_dict が違う行: %d" % len(diff)] + diff + [
        "基点の印の分布: %s" % dist_old, "新の印の分布: %s" % dist_new, "anchored 以外 -> anchored: %d" % to_anch, "reason の分布（新）: %s" % reasons]
print("\n".join(lines))
