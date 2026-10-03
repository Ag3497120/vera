"""Run the separately preregistered W1-a4 shape controls."""
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

from verantyx import semantic_read as SR

TREE = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
PLACEMENT = "/Users/motonisihikoudai/Projects/vera-impl/build/coarse-W3a/full/r7/run1"


def base_module():
    src = subprocess.run(["git", "-C", str(TREE), "show", "c875ed3:verantyx/semantic_read.py"],
                         capture_output=True, check=True).stdout.decode("utf-8")
    name = "verantyx._semantic_read_base_w3b3_wave2"
    spec = importlib.util.spec_from_loader(name, loader=None)
    module = importlib.util.module_from_spec(spec)
    module.__package__ = "verantyx"
    sys.modules[name] = module
    exec(compile(src, "semantic_read.py@c875ed3", "exec"), module.__dict__)
    return module


BASE = base_module()


def wire(value):
    return json.dumps(value, ensure_ascii=False) + "\n"


def run():
    os.environ.pop("VERA_PLACEMENT", None)
    os.environ.pop("VERA_COARSE_PLACEMENT", None)
    cases = [json.loads(line) for line in (HERE / "cases_wave2.jsonl").read_text(encoding="utf-8").splitlines()]
    rows = []
    for case in cases:
        absent = SR.read(case["text"], case["lang"])
        absent_base = BASE.read(case["text"], case["lang"], placement=None)
        os.environ["VERA_PLACEMENT"] = PLACEMENT
        configured = SR.read(case["text"], case["lang"])
        explain = SR.clause_scope_explain_ja(case["text"], PLACEMENT)
        rows.append({"case": case, "absent": absent, "absent_base": absent_base,
                     "absent_byte_equal": wire(absent) == wire(absent_base),
                     "configured": configured, "explain": explain})
        os.environ.pop("VERA_PLACEMENT", None)
    out = HERE / "results" / "wave2_observations.jsonl"
    with out.open("w", encoding="utf-8", newline="\n") as stream:
        for row in rows:
            stream.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")
    summary = {"cases": len(rows), "placement_free_byte_mismatches": sum(not r["absent_byte_equal"] for r in rows),
               "configured_readable": sum(r["configured"].get("readable") is True for r in rows),
               "configured_relations": sum(bool(r["configured"].get("relations")) for r in rows)}
    (HERE / "results" / "wave2_summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, sort_keys=True))
    return rows


if __name__ == "__main__":
    run()
