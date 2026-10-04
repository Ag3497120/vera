#!/usr/bin/env python3
"""Run the frozen W5-f reading cases through the public semantic-read entry."""
import argparse
import collections
import importlib.util
import json
import os
from pathlib import Path
import sys


TREE = Path(__file__).resolve().parents[2]
DATA_FILES = (Path(__file__).with_name("w5f_gates.jsonl"), Path(__file__).with_name("w5f_gates_r3.jsonl"),
              Path(__file__).with_name("w5f_gates_r3b.jsonl"))
NARROWED_F2 = Path(__file__).with_name("w5f_gates_f2_narrowed.json")
R8 = Path("/Users/motonisihikoudai/Projects/vera-impl/build/coarse-W3a/full/r8/run2")


def _load_fakes():
    path = TREE / "tests" / "reading_soundness" / "w3b1_fakes.py"
    spec = importlib.util.spec_from_file_location("w5f_gate_fakes", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _tree_modules_only():
    foreign = [
        module.__file__
        for name, module in list(sys.modules.items())
        if (name == "verantyx" or name.startswith("verantyx."))
        and getattr(module, "__file__", None)
        and not Path(module.__file__).resolve().is_relative_to(TREE)
    ]
    assert not foreign, foreign


def load_narrowed_f2(rows):
    """W5-f r3 review r2: narrowed (deferred) rows are recorded, the frozen data rows are not rewritten."""
    record = json.loads(NARROWED_F2.read_text(encoding="utf-8"))["rows"]
    by_id = {row["id"]: row for row in rows}
    for row_id in record:
        assert row_id in by_id, row_id
        assert by_id[row_id]["group"] == "F2" and by_id[row_id]["expect"] == "abstain", row_id
    return set(record)


def evaluate(mode, rows):
    deferred_ids = load_narrowed_f2(rows)
    if mode == "r8":
        if not R8.is_dir():
            raise RuntimeError("ENV_MISSING[r8_placement]: %s" % R8)
        os.environ["VERA_PLACEMENT"] = str(R8)
    else:
        os.environ.pop("VERA_PLACEMENT", None)

    from verantyx import semantic_read as SR

    fakes = _load_fakes() if mode == "fake" else None
    results = []
    for row in rows:
        if mode == "fake" and row["placement"] is not None:
            mapping = {term: fakes.answer(kind, term=term) for term, kind in row["placement"].items()}
            out = SR.read(row["text"], "ja", placement=fakes.MapQuery(mapping))
        elif mode == "fake":
            out = SR.read(row["text"], "ja", placement=None)
        elif mode == "none":
            out = SR.read(row["text"], "ja", placement=None)
        else:
            out = SR.read(row["text"], "ja")

        clauses = out.get("clauses") or []
        roles = clauses[0].get("roles") or {} if len(clauses) == 1 else None
        if row["id"] in deferred_ids:
            # W5-f r3: F-2 removed by the auditor; counted, never a misread (checked again in W3-b6)
            status = "DEFERRED_READ" if out.get("readable") else "DEFERRED_ABSTAIN"
        elif row["expect"] == "abstain":
            status = "MISREAD" if out.get("readable") else "ABSTAIN"
        elif not out.get("readable"):
            status = "ABSTAIN"
        elif len(clauses) != 1 or roles != row.get("roles"):
            status = "MISREAD"
        else:
            status = "CORRECT"
        results.append({"id": row["id"], "group": row["group"], "status": status,
                        "readable": bool(out.get("readable")), "roles": roles})

    _tree_modules_only()
    counts = collections.defaultdict(collections.Counter)
    for result in results:
        counts[result["group"]][result["status"]] += 1
    summary = {
        "mode": mode,
        "rows": len(results),
        "misread": sum(x["status"] == "MISREAD" for x in results),
        "groups": {name: dict(sorted(values.items())) for name, values in sorted(counts.items())},
        "results": results,
    }
    return summary


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("fake", "none", "r8"), required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    rows = [json.loads(line) for path in DATA_FILES for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    ids = [row["id"] for row in rows]
    assert len(ids) == len(set(ids)), "duplicate ids"
    summary = evaluate(args.mode, rows)
    Path(args.out).write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    for group, counts in summary["groups"].items():
        print("%s %s" % (group, json.dumps(counts, ensure_ascii=False, sort_keys=True)))
    for result in summary["results"]:
        if result["status"] == "MISREAD":
            print("MISREAD " + json.dumps(result, ensure_ascii=False, sort_keys=True))
    print("summary " + json.dumps({k: v for k, v in summary.items() if k != "results"}, ensure_ascii=False, sort_keys=True))
    return 1 if summary["misread"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
