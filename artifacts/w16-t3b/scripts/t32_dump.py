"""W16-t3b: T3-2 の保存 raw（artifacts/w16-t3/r3/w14/C/results.jsonl の quote_check のある行）を今の QC.check に掛け、1 行ずつ JSONL に書く。使い方: t32_dump.py out.jsonl"""
import json
import os
import sys

WROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))
from benchmarks.public_v1 import data as D  # noqa: E402
from verantyx import decode_grammar as G, quote_check as QC  # noqa: E402

assert all(m.__file__.startswith(WROOT + "/") for n, m in sys.modules.items() if n.startswith("verantyx") and getattr(m, "__file__", None))
recs = {ds: G.load_records([D.doc_path(f) for f in D.docset_files(ds)]) for ds in D.DOCSETS}
qs = {q["id"]: q for q in D.load_questions()}
n = 0
with open(sys.argv[1], "w", encoding="utf-8") as out:
    for l in open(os.path.join(WROOT, "artifacts/w16-t3/r3/w14/C/results.jsonl"), encoding="utf-8"):
        r = json.loads(l)
        v = r.get("vera") or {}
        if "quote_check" not in v:
            continue
        pr = G._parse_quote_reply(v["llm"]["raw"])
        res = QC.check(pr[0] if pr[0] is not None else "", pr[1], recs[r["docset"]], question=qs[r["id"]]["question"])
        out.write(json.dumps({"id": r["id"], "rep": r.get("rep"), "cat": qs[r["id"]].get("cat"), "answer": pr[0], "question": qs[r["id"]]["question"],
                              "saved": v["quote_check"], "qc": res.to_dict()}, ensure_ascii=False) + "\n")
        n += 1
print("rows", n)
