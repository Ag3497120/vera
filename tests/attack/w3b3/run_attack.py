"""Run the preregistered corpus through the public semantic-read and event-cross APIs."""
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

from verantyx import event_cross as EC
from verantyx import semantic_read as SR

TREE = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
CASES = HERE / "cases.jsonl"
RESULTS = HERE / "results"
PLACEMENT = "/Users/motonisihikoudai/Projects/vera-impl/build/coarse-W3a/full/r7/run1"
BASE_COMMIT = "c875ed3"


def _base_module():
    src = subprocess.run(["git", "-C", str(TREE), "show", "%s:verantyx/semantic_read.py" % BASE_COMMIT],
                         capture_output=True, check=True).stdout.decode("utf-8")
    name = "verantyx._semantic_read_base_w3b3_attack"
    spec = importlib.util.spec_from_loader(name, loader=None)
    module = importlib.util.module_from_spec(spec)
    module.__package__ = "verantyx"
    sys.modules[name] = module
    exec(compile(src, "semantic_read.py@%s" % BASE_COMMIT, "exec"), module.__dict__)
    return module


BASE = _base_module()


def _wire(value):
    return json.dumps(value, ensure_ascii=False) + "\n"


def _load_cases():
    return [json.loads(line) for line in CASES.read_text(encoding="utf-8").splitlines() if line]


def run():
    if not Path(PLACEMENT).is_dir():
        raise RuntimeError("registered read-only placement is unavailable: " + PLACEMENT)
    os.environ.pop("VERA_PLACEMENT", None)
    os.environ.pop("VERA_COARSE_PLACEMENT", None)
    rows = []
    lookup = EC.CoarseLookup(PLACEMENT)
    for case in _load_cases():
        text, lang = case["text"], case["lang"]
        absent = SR.read(text, lang)
        absent_base = BASE.read(text, lang, placement=None)
        absent_wire, absent_base_wire = _wire(absent), _wire(absent_base)

        os.environ["VERA_PLACEMENT"] = PLACEMENT
        configured = SR.read(text, lang)
        configured_base = BASE.read(text, lang, placement=PLACEMENT)
        configured_wire, configured_base_wire = _wire(configured), _wire(configured_base)
        explain = SR.clause_scope_explain_ja(text, PLACEMENT)
        events = EC.build_crosses(configured, lookup).to_dict()
        rows.append({
            "id": case["id"], "group": case["group"], "lang": lang, "text": text,
            "expected": case["expected"],
            "absent": {"output": absent, "base_output": absent_base,
                       "byte_equal_base": absent_wire == absent_base_wire},
            "configured": {"output": configured, "base_output": configured_base,
                           "base_equal": configured_wire == configured_base_wire,
                           "explain": explain, "events": events},
        })
        os.environ.pop("VERA_PLACEMENT", None)
    RESULTS.mkdir(exist_ok=True)
    with (RESULTS / "observations.jsonl").open("w", encoding="utf-8", newline="\n") as stream:
        for row in rows:
            stream.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")
    summary = {
        "cases": len(rows),
        "groups": {name: sum(row["group"] == name for row in rows)
                   for name in sorted({row["group"] for row in rows})},
        "placement_free_byte_mismatches": sum(not row["absent"]["byte_equal_base"] for row in rows),
        "configured_base_equal": sum(row["configured"]["base_equal"] for row in rows),
        "configured_readable": sum(row["configured"]["output"].get("readable") is True for row in rows),
        "configured_relative": sum(any(rel.get("type") == "relative" for rel in row["configured"]["output"].get("relations", []))
                                    for row in rows),
    }
    (RESULTS / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return rows


if __name__ == "__main__":
    run()
