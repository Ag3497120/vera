"""T3-2 の再照合（Ollama を流し直さない）: 保存された各行の vera.llm.raw を今の QC.check に掛け直し、保存された vera.quote_check と違う行を一覧する。
プロンプトは変わらないので LLM の出力も変わらない。使い方: recheck_t32.py [--results r3/w14/C/results.jsonl] [--out r4/t32_recheck.txt]"""
import argparse
import json
import sys

CWD = "/Users/motonisihikoudai/Projects/vera-impl/wt/W16-t3-S"
sys.path.append("/Users/motonisihikoudai/Projects/vera-impl/wt/W14-bench-S")   # 読み取りのみ
from benchmarks.public_v1 import data as D  # noqa: E402
from verantyx import decode_grammar as G, quote_check as QC  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--results", default=CWD + "/artifacts/w16-t3/r3/w14/C/results.jsonl")
ap.add_argument("--out", default=CWD + "/artifacts/w16-t3/r4/t32_recheck.txt")
a = ap.parse_args()
recs = {ds: G.load_records([D.doc_path(f) for f in D.docset_files(ds)]) for ds in D.DOCSETS}
qs = {q["id"]: q for q in D.load_questions()}
tot = same = 0
diff = []
n_to_anchored = 0
dist_old, dist_new, reasons = {}, {}, {}
for l in open(a.results, encoding="utf-8"):
    r = json.loads(l)
    v = r.get("vera") or {}
    if "quote_check" not in v:
        continue
    tot += 1
    pr = G._parse_quote_reply(v["llm"]["raw"])
    res = QC.check(pr[0] if pr[0] is not None else "", pr[1], recs[r["docset"]], question=qs[r["id"]]["question"])
    dist_old[v["quote_check"]["verdict"]] = dist_old.get(v["quote_check"]["verdict"], 0) + 1
    dist_new[res.verdict] = dist_new.get(res.verdict, 0) + 1
    if res.verdict != v["quote_check"]["verdict"]:
        pass
    reasons[res.reason] = reasons.get(res.reason, 0) + 1
    if res.to_dict() == v["quote_check"]:
        same += 1
    else:
        qs_ = qs[r["id"]]
        anchored_up = v["quote_check"]["verdict"] != "anchored" and res.verdict == "anchored"
        n_to_anchored += anchored_up
        old_v = v["quote_check"]["verdict"]
        diff.append("%s rep=%s cat=%s %s -> %s reason=%s 答え=%s 引用=%s 問い=%s" % (
            r["id"], r.get("rep"), qs_.get("cat"), old_v, res.verdict, res.reason, pr[0],
            " / ".join(str(q_.get("text")) for q_ in (pr[1] or []) if isinstance(q_, dict)), qs_["question"]))
lines = ["保存された結果: %s" % a.results, "quote_check のある行: %d" % tot, "今の QC.check の to_dict が保存と同一: %d" % same, "違う行: %d" % len(diff)] + diff + [
    "保存の印の分布（255 行すべて）: %s" % dist_old,
    "今の印の分布（255 行すべて）: %s" % dist_new,
    "anchored 以外 -> anchored: %d" % n_to_anchored,
    "reason の分布（今）: %s" % reasons]
open(a.out, "w", encoding="utf-8").write("\n".join(lines) + "\n")
print("\n".join(lines))
