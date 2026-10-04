from __future__ import annotations

import importlib.util
import json
import runpy
import sys
from pathlib import Path


def load_fakes(tree: Path):
    path = tree / "tests/reading_soundness/w3b1_fakes.py"
    spec = importlib.util.spec_from_file_location("proposal_fakes", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def entry_results(SR, fakes, cases):
    results = []
    for case_id, text, mapping in cases:
        query = fakes.MapQuery({term: fakes.answer(kind, term=term) for term, kind in mapping.items()})
        out = SR.read(text, "ja", placement=query)
        results.append({"id": case_id, "text": text, "readable": out.get("readable"),
                        "roles": (out.get("clauses") or [{}])[0].get("roles"),
                        "reasons": (out.get("abstain") or {}).get("reasons")})
    return results


def entry_results_live(SR, R, cases, placement_path):
    query = R.CoarseQuery(str(placement_path))
    results = []
    for case_id, text, _mapping in cases:
        out = SR.read(text, "ja", placement=query)
        results.append({"id": case_id, "text": text, "readable": out.get("readable"),
                        "roles": (out.get("clauses") or [{}])[0].get("roles"),
                        "reasons": (out.get("abstain") or {}).get("reasons")})
    return results


def main() -> None:
    if len(sys.argv) < 4 or sys.argv[2] not in ("f2", "he"):
        raise SystemExit("usage: probe_table_proposals.py <scratch-tree> <f2|he> <output> [r8]")
    tree, proposal, out = Path(sys.argv[1]), sys.argv[2], Path(sys.argv[3])
    sys.path.insert(0, str(tree))
    sys.path.insert(0, str(tree / "tests/reading_soundness"))
    from verantyx import semantic_read as SR
    from verantyx import semantic_reader as R

    foreign = [module.__file__ for name, module in list(sys.modules.items())
               if (name == "verantyx" or name.startswith("verantyx."))
               and getattr(module, "__file__", None)
               and not Path(module.__file__).resolve().is_relative_to(tree.resolve())]
    if foreign:
        raise SystemExit(f"foreign modules: {foreign}")

    if proposal == "f2":
        fakes = load_fakes(tree)
        cases = [
            ("D06", "姉が東から倉庫へ箱を運んだ。", {"姉": "PERSON", "東": "PLACE", "倉庫": "PLACE", "箱": "ARTIFACT", "運ぶ": "P_ACT"}),
            ("D08", "兄が上司から倉庫へ叱られた。", {"兄": "PERSON", "上司": "PERSON", "倉庫": "PLACE", "叱る": "P_ACT"}),
            ("D10", "弟が右から倉庫へ打った。", {"弟": "PERSON", "右": "PLACE", "倉庫": "PLACE", "打つ": "P_ACT"}),
        ]
        before = entry_results(SR, fakes, cases)
        if len(sys.argv) < 5:
            raise SystemExit("F2 proposal also requires the r8 placement directory")
        before_live = entry_results_live(SR, R, cases, sys.argv[4])
        old = R.TYPED_FRAMES_W3B4["P_ACT"]
        filtered = tuple(row for row in old if row != ("source", ("から",), ("PLACE",), "arg"))
        if len(filtered) != len(old) - 1:
            raise SystemExit("expected exactly one P_ACT source/から/PLACE row")
        R.TYPED_FRAMES_W3B4["P_ACT"] = filtered
        after = entry_results(SR, fakes, cases)
        after_live = entry_results_live(SR, R, cases, sys.argv[4])
        print("proposal=K165-remove-P_ACT-source-から-PLACE")
        print("cases_before=" + json.dumps(before, ensure_ascii=False, sort_keys=True))
        print("cases_after=" + json.dumps(after, ensure_ascii=False, sort_keys=True))
        print("r8_cases_before=" + json.dumps(before_live, ensure_ascii=False, sort_keys=True))
        print("r8_cases_after=" + json.dumps(after_live, ensure_ascii=False, sort_keys=True))
        sys.argv = [str(tree / "tests/reading_soundness/w3b1_entry_dump.py"), "--mode", "live",
                    "--placement", sys.argv[4], "--inputs", str(tree / "artifacts/w3-b5/entry_inputs_r2.txt"),
                    "--out", str(out)]
        runpy.run_path(sys.argv[0], run_name="__main__")
    else:
        old = R.TYPED_FRAMES_W3B4["P_ACT"]
        filtered = tuple(row for row in old if row != ("goal", ("へ",), ("PLACE",), "arg"))
        if len(filtered) != len(old) - 1:
            raise SystemExit("expected exactly one P_ACT goal/へ/PLACE row")
        R.TYPED_FRAMES_W3B4["P_ACT"] = filtered
        sys.argv = [str(tree / "artifacts/w3-b4/tools/run_rows.py"), "--data",
                    str(tree / "tests/reading_soundness/ja_r10_w3b4.jsonl"), "--out", str(out),
                    "--exceptions", str(tree / "artifacts/w3-b4/expect_exceptions.json")]
        print("proposal=K165-remove-P_ACT-goal-へ-PLACE")
        try:
            runpy.run_path(sys.argv[0], run_name="__main__")
        except SystemExit as exc:
            print("run_rows_exit=" + str(exc.code))


if __name__ == "__main__":
    main()
