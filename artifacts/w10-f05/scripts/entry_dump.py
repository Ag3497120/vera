"""R1 (K297): every sentence of the 4,149-sentence entrance (artifacts/w3-b5/entry_inputs_r2.txt, one {"text","source"} per line) through semantic_read.read; one line per sentence
{"text","source","out": <the reading>} (sort_keys=False, ensure_ascii=False; a refused input is {"error": ...}). The same script runs on the base tree and on the new tree (cwd = the tree, PYTHONPATH = the tree).
usage: entry_dump.py <placement dir | none> <out.jsonl>"""
import json
import os
import sys

plc, out = sys.argv[1], sys.argv[2]
tree = os.getcwd()
from verantyx import semantic_read  # noqa: E402
assert os.path.realpath(semantic_read.__file__).startswith(os.path.realpath(tree) + os.sep), semantic_read.__file__
placement = None if plc == "none" else plc
n = 0
with open(out, "w", encoding="utf-8") as fo:
    for line in open("artifacts/w3-b5/entry_inputs_r2.txt", encoding="utf-8"):
        if not line.strip():
            continue
        r = json.loads(line)
        try:
            res = semantic_read.read(r["text"], placement=placement)
        except semantic_read.ReadError as err:
            res = {"error": {"type": err.type, "detail": err.detail}}
        fo.write(json.dumps({"text": r["text"], "source": r["source"], "out": res}, ensure_ascii=False) + "\n")
        n += 1
print("rows", n)
