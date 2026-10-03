"""W3-a3: the wrong and the surprising answers of a verbs measurement, written to a file (not to the docs).
  errors_report.py <eval_runs/NNN directory> <out.md>"""
import json
import sys

run, out = sys.argv[1], sys.argv[2]
s = json.load(open(run + "/summary.json", encoding="utf-8"))
items = [json.loads(l) for l in open(run + "/items.jsonl", encoding="utf-8")]
L = ["# W3-a3: verbs of %s on %s" % (s["data_path"].split("/")[-1], s["placement"].split("/")[-2] + "/" + s["placement"].split("/")[-1]),
     "(run %s, content_sha256 %s)\n" % (run.split("/")[-1], s["content_sha256"])]
L.append("## direct answers that are wrong (typed words)")
for i in items:
    if i["kind"] == "typed" and i["origin"] == "direct" and i["cls"] == "wrong_single":
        L.append("- %s gold=%s top=%s by=%s" % (i["term"], ",".join(i["gold"]), ",".join(i["top"]), i["decided_by"]))
L.append("\n## direct answers that are right")
for i in items:
    if i["kind"] == "typed" and i["origin"] == "direct" and i["cls"] == "correct":
        L.append("- %s gold=%s top=%s by=%s frame_status=%s" % (i["term"], ",".join(i["gold"]), ",".join(i["top"]), i["decided_by"], i["frame_status"]))
L.append("\n## words that are not typed but got a type (any origin)")
for i in items:
    if i["kind"] != "typed" and i["top"]:
        L.append("- %s kind=%s top=%s origin=%s basis=%s by=%s" % (i["term"], i["kind"], ",".join(i["top"]), i["origin"], i["estimate_basis"], i["decided_by"]))
L.append("\n## estimated (generated) typed answers: right / wrong counts")
est = [i for i in items if i["kind"] == "typed" and i["origin"] == "estimated"]
L.append("- right %d, wrong %d, other %d" % tuple(sum(1 for i in est if i["cls"] == k) for k in ("correct", "wrong_single", "other")))
open(out, "w", encoding="utf-8").write("\n".join(L) + "\n")
print("written", out)
