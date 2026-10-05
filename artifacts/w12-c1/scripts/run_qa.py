"""R5: each question through `python -m verantyx.cli ask --mode round5 --document <doc> [--layer <spec>] -- <question>` in its OWN process (cwd = the tree; VERA_PLACEMENT from the environment); the JSON the command
printed is saved. usage: run_qa.py --questions Q.jsonl --document DOC --layer <none|spec> --out OUT.jsonl"""
import argparse
import json
import os
import subprocess
import sys
import time

ap = argparse.ArgumentParser()
ap.add_argument("--questions", required=True)
ap.add_argument("--document", required=True)
ap.add_argument("--layer", default="none")
ap.add_argument("--out", required=True)
a = ap.parse_args()
env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", PYTHONPATH=os.getcwd())
env.pop("VERA_PLACEMENT_LAYER", None)               # the layer comes from --layer only
assert env.get("VERA_PLACEMENT"), "VERA_PLACEMENT must be set"
n = 0
with open(a.out, "w", encoding="utf-8") as fo:
    for line in open(a.questions, encoding="utf-8"):
        if not line.strip():
            continue
        q = json.loads(line)
        cmd = [sys.executable, "-m", "verantyx.cli", "ask", "--mode", "round5", "--document", a.document]
        if a.layer != "none":
            cmd += ["--layer", a.layer]
        cmd += ["--", q["question"]]
        t0 = time.perf_counter()
        p = subprocess.run(cmd, capture_output=True, text=True, env=env)
        try:
            out = json.loads(p.stdout)
        except ValueError:
            out = {"verdict": "PROCESS_ERROR", "stdout": p.stdout[-300:], "stderr": p.stderr[-300:]}
        fo.write(json.dumps({"id": q["id"], "question": q["question"], "expect": q["expect"], "layer": a.layer, "rc": p.returncode, "ms": round((time.perf_counter() - t0) * 1000.0, 1), "out": out},
                            ensure_ascii=False) + "\n")
        n += 1
print("ran", n, "layer", a.layer)
