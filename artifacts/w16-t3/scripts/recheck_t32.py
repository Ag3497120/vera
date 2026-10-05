"""T3-2 の再照合（Ollama を流し直さない）: 保存された各行の vera.llm.raw を今の QC.check に掛け直し、保存された vera.quote_check と違う行を一覧する。
プロンプトは変わらないので LLM の出力も変わらない。使い方: recheck_t32.py [--results r3/w14/C/results.jsonl] [--out r3b/t32_recheck.txt]"""
import argparse
import json
import sys

CWD = "/Users/motonisihikoudai/Projects/vera-impl/wt/W16-t3-S"
sys.path.append("/Users/motonisihikoudai/Projects/vera-impl/wt/W14-bench-S")   # 読み取りのみ
from benchmarks.public_v1 import data as D  # noqa: E402
from verantyx import decode_grammar as G, quote_check as QC  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--results", default=CWD + "/artifacts/w16-t3/r3/w14/C/results.jsonl")
ap.add_argument("--out", default=CWD + "/artifacts/w16-t3/r3b/t32_recheck.txt")
a = ap.parse_args()
recs = {ds: G.load_records([D.doc_path(f) for f in D.docset_files(ds)]) for ds in D.DOCSETS}
qs = {q["id"]: q for q in D.load_questions()}
tot = same = 0
diff = []
for l in open(a.results, encoding="utf-8"):
    r = json.loads(l)
    v = r.get("vera") or {}
    if "quote_check" not in v:
        continue
    tot += 1
    pr = G._parse_quote_reply(v["llm"]["raw"])
    res = QC.check(pr[0] if pr[0] is not None else "", pr[1], recs[r["docset"]], question=qs[r["id"]]["question"])
    if res.to_dict() == v["quote_check"]:
        same += 1
    else:
        diff.append("%s rep=%s 保存 %s -> 今 %s uncovered=%s" % (r["id"], r.get("rep"), v["quote_check"]["verdict"], res.verdict, res.uncovered))
lines = ["保存された結果: %s" % a.results, "quote_check のある行: %d" % tot, "今の QC.check の to_dict が保存と同一: %d" % same, "違う行: %d" % len(diff)] + diff
open(a.out, "w", encoding="utf-8").write("\n".join(lines) + "\n")
print("\n".join(lines))
