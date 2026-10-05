"""W16-t6: 合成 40 件を tmp に実体化して `attest.run_attest` に掛け、期待（expected.jsonl）と比べる。測定の本体（T6-1）。
テスト（tests/test_w16t6_synth.py）と run_synth.py の両方が使う。ファイル名は test_*.py ではない（全体テストの収集に混ざらない）。
"""
import hashlib
import json
import os
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent


def load_jsonl(p):
    return [json.loads(l) for l in Path(p).read_text(encoding="utf-8").splitlines() if l.strip()]


def freeze_ok():
    """(ok, detail) for `shasum -a 256 -c freeze.sha256` done in python."""
    bad = []
    for line in (HERE / "freeze.sha256").read_text().splitlines():
        digest, name = line.split()
        name = Path(name).name
        if hashlib.sha256((HERE / name).read_bytes()).hexdigest() != digest:
            bad.append(name)
    return (not bad), bad


def _git(root, *args):
    env = dict(os.environ, GIT_CONFIG_GLOBAL="/dev/null", GIT_CONFIG_SYSTEM="/dev/null")
    subprocess.run(["git", "-C", str(root), "-c", "user.name=t", "-c", "user.email=t@t", "-c", "commit.gpgsign=false"] + list(args),
                   check=True, capture_output=True, env=env)


def materialize(case, root):
    """Writes the fixture tree of `case` under root/<id>; returns (tree, ledger path or None)."""
    tree = Path(root) / case["id"]
    tree.mkdir(parents=True, exist_ok=True)
    base_files = case["git_base"] if case["git_base"] is not None else ({"pytest.ini": ""} if case["flags"]["base"] else None)
    if base_files is not None:
        for p, c in base_files.items():
            (tree / p).parent.mkdir(parents=True, exist_ok=True)
            (tree / p).write_text(c, encoding="utf-8")
        _git(tree, "init", "-q")
        _git(tree, "add", "-A")
        _git(tree, "commit", "-q", "-m", "base")
    for p, c in case["files"].items():
        (tree / p).parent.mkdir(parents=True, exist_ok=True)
        (tree / p).write_text(c, encoding="utf-8")
    led = None
    if case["ledger"] is not None:
        led = Path(root) / (case["id"] + ".ledger.jsonl")
        led.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in case["ledger"]), encoding="utf-8")
    return tree, led


def run_case(attest, case, root, extractors):
    tree, led = materialize(case, root)
    return attest.run_attest(case["report"], str(tree), ledger=str(led) if led else None, rerun=case["flags"]["rerun"], base=case["flags"]["base"],
                             extractors=extractors, report_path="synth/%s.md" % case["id"])


def evaluate(cases, expected, results):
    """results: {case_id: attest result}. Metrics of docs/ATTEST.md section 5 (fact level; claim level for V and a)."""
    out = {}
    for ex in ("V", "a", "b"):
        m = dict(cases=0, facts=0, false_facts=0, true_facts=0, unknown_facts=0, detected=0, missed=0, abstain_false=0, false_positive=0, insufficient=0,
                 not_extracted=0, not_extracted_false=0, extra=0, exact=0, mismatched_expectations=[], claim_missed=0, claim_false_positive=0, offform_expected=0, offform_actual=0,
                 claim_alignment_errors=0)
        for case, exp in zip(cases, expected):
            if ex == "a" and not case["has_json"]:
                continue
            m["cases"] += 1
            res = results[case["id"]]["extractors"][ex]
            actual = {}
            for c in res["claims"]:
                for f in c["facts"]:
                    actual.setdefault(f["fact"], f)
            exp_sigs = set()
            for ec in exp["claims"]:
                for ef in ec["facts"]:
                    exp_sigs.add(ef["sig"])
                    m["facts"] += 1
                    m[{"false": "false_facts", "true": "true_facts", "unknown": "unknown_facts"}[ef["truth"]]] += 1
                    af = actual.get(ef["sig"])
                    if af is None:
                        m["not_extracted"] += 1
                        if ef["truth"] == "false":
                            m["not_extracted_false"] += 1
                        continue
                    if (af["mark"], af["reason"]) == (ef["mark"], ef["reason"]):
                        m["exact"] += 1
                    else:
                        m["mismatched_expectations"].append({"case": case["id"], "fact": ef["sig"], "expected": [ef["mark"], ef["reason"]], "actual": [af["mark"], af["reason"]]})
                    if ef["truth"] == "false":
                        if af["mark"] == "RECORD":
                            m["missed"] += 1
                        elif af["mark"] == "MISMATCH":
                            m["detected"] += 1
                        else:
                            m["abstain_false"] += 1
                    elif ef["truth"] == "true":
                        if af["mark"] == "MISMATCH":
                            m["false_positive"] += 1
                        elif af["mark"] == "TESTIMONY":
                            m["insufficient"] += 1
            m["extra"] += len([s for s in actual if s not in exp_sigs])
            m["offform_expected"] += exp["offform"] if ex == "V" else 0
            m["offform_actual"] += len([c for c in res["claims"] if c["kind"] == "offform"])
            if ex in ("V", "a"):
                acts = [c for c in res["claims"] if c["kind"] != "offform"]
                if len(acts) != len(exp["claims"]):
                    m["claim_alignment_errors"] += 1
                else:
                    for ac, ec in zip(acts, exp["claims"]):
                        has_false = any(f["truth"] == "false" for f in ec["facts"])
                        all_true = all(f["truth"] == "true" for f in ec["facts"])
                        if has_false and ac["mark"] == "RECORD":
                            m["claim_missed"] += 1
                        if all_true and ac["mark"] == "MISMATCH":
                            m["claim_false_positive"] += 1
        m["detection_rate"] = (m["detected"] / m["false_facts"]) if m["false_facts"] else None
        out[ex] = m
    return out


def run_all(attest, workdir, extractors=("V", "a", "b")):
    cases = load_jsonl(HERE / "cases.jsonl")
    expected = load_jsonl(HERE / "expected.jsonl")
    results = {}
    for case in cases:
        results[case["id"]] = run_case(attest, case, workdir, extractors)
    return cases, expected, results, evaluate(cases, expected, results)
