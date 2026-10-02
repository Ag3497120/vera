#!/usr/bin/env python3
"""Self-test of tools/w0_1_compare_runs.py (G3 gate): the gate must catch regressions, and only those.

Usage: w0_1_compare_selftest.py <before_junit.xml> <after_junit.xml>

Builds synthetic copies of the real after-junit in artifacts/w0-1/tmp (inside the tree; removed at the
end), changes one thing at a time, runs the comparison tool as a subprocess and checks the
`G3 NEW_FAIL=` line, the `G3 GATES` line and the exit code. Cases:
  E  no change                                                -> NEW_FAIL=0, gates 0, exit 0
  A  renamed case whose before-case PASSED fails              -> NEW_FAIL=1, exit 1 (the r1 review's scenario)
  B  renamed case whose before-case FAILED fails              -> NEW_FAIL=0, exit 0 (already failing before)
  C  renamed test, param id with no before-case, fails        -> NEW_FAIL=1, exit 1 (treated as absent in before)
  D  another renamed test (6 cases, same ids) fails           -> NEW_FAIL=1, exit 1
  F  non-renamed test that passed before fails                -> NEW_FAIL=1, exit 1
  G  (r2 review) all cases of a module that was collected in before are replaced by one
     collection error (junit error with empty classname)      -> NEW_FAIL=1 (COLLECTION_ERROR ... before=collected), exit 1
  H  collection error in after for a module that also failed to collect in before
     (its cases replaced by the error)                                    -> NEW_FAIL=0, exit 0 (before-failed side)
  I  collection error in after for a module that is not in before at all
                                                              -> NEW_FAIL=1 (before=ABSENT), exit 1
  J  one passed case removed from after                       -> NEW_FAIL=0, MISSING_IN_AFTER=1, exit 1
  K  one passed case becomes xfailed                          -> NEW_FAIL=0, PASS_TO_XFAIL=1, exit 1
  L  one passed case becomes skipped, reason names no resource -> NEW_FAIL=0, PASS_TO_SKIP_UNCLASSIFIED=1, exit 1
  M  one passed case becomes skipped with an ENV_MISSING[...] reason
                                                              -> NEW_FAIL=0, gates 0, exit 0 (allowed, listed)
Exit 0 only if every case behaves as listed.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "tools" / "w0_1_compare_runs.py"
MEM = "tests.test_memory_revalidate"
SAFE = "test_missing_or_unknown_witness_is_unverifiable_with_safe_answerability"


VER = "tests.test_verifier_agents"
DIRECT = "test_parse_accepts_direct_structured_verdict_event"
BEFORE_COLLECT_ERR_MODULE = "tests.attack.test_semantic_unknown_choice_paraphrase"


def _find(tree: ET.ElementTree, classname: str, name: str) -> tuple[ET.Element, ET.Element]:
    hits = [(suite, case) for suite in tree.getroot().iter("testsuite") for case in suite.findall("testcase")
            if case.get("classname") == classname and case.get("name") == name]
    if len(hits) != 1:
        raise SystemExit(f"selftest setup error: {classname}::{name} matched {len(hits)} cases")
    return hits[0]


def _collection_error(suite: ET.Element, module: str) -> None:
    case = ET.SubElement(suite, "testcase", {"classname": "", "name": module, "time": "0.000"})
    ET.SubElement(case, "error", {"message": "collection failure (SELFTEST injected)"})


def mutate(src: str, dst: Path, kind: str, spec: tuple) -> None:
    tree = ET.parse(src)
    if kind == "none":
        pass
    elif kind == "fail":  # (classname, name, new_name or None)
        _, case = _find(tree, spec[0], spec[1])
        ET.SubElement(case, "failure", {"message": "SELFTEST injected failure"})
        if spec[2]:
            case.set("name", spec[2])
    elif kind == "collect_error_replaces_module":  # (module,) all its cases -> one collection error
        removed = 0
        for suite in tree.getroot().iter("testsuite"):
            for case in list(suite.findall("testcase")):
                if case.get("classname") == spec[0]:
                    suite.remove(case)
                    removed += 1
            last = suite
        if removed == 0:
            raise SystemExit(f"selftest setup error: no case of {spec[0]}")
        _collection_error(last, spec[0])
    elif kind == "collect_error_added":  # (module,) no case of it exists in after
        suite = next(iter(tree.getroot().iter("testsuite")))
        if any(c.get("classname") == spec[0] for c in tree.getroot().iter("testcase")):
            raise SystemExit(f"selftest setup error: {spec[0]} has cases in after")
        _collection_error(suite, spec[0])
    elif kind == "remove":  # (classname, name)
        suite, case = _find(tree, spec[0], spec[1])
        suite.remove(case)
    elif kind == "xfail":
        _, case = _find(tree, spec[0], spec[1])
        ET.SubElement(case, "skipped", {"type": "pytest.xfail", "message": "SELFTEST injected xfail"})
    elif kind == "skip":  # (classname, name, message)
        _, case = _find(tree, spec[0], spec[1])
        ET.SubElement(case, "skipped", {"type": "pytest.skip", "message": spec[2]})
    else:
        raise SystemExit(f"selftest setup error: unknown kind {kind}")
    tree.write(dst)


def run(before: str, after: Path) -> tuple[int, str, str, list[str]]:
    proc = subprocess.run([sys.executable, str(TOOL), before, str(after)], capture_output=True, text=True)
    lines = proc.stdout.splitlines()
    new_fail = next((l for l in reversed(lines) if l.startswith("G3 NEW_FAIL=")), "NO G3 NEW_FAIL LINE")
    gates = next((l for l in reversed(lines) if l.startswith("G3 GATES ")), "NO G3 GATES LINE")
    detail = []
    if "NEW_FAIL (" in proc.stdout:
        detail = [l.strip() for l in proc.stdout.split("NEW_FAIL (", 1)[1].split("\n\n", 1)[0].splitlines()[1:] if l.strip()]
    return proc.returncode, new_fail, gates, detail


NO_GATES = "G3 GATES MISSING_IN_AFTER=0 PASS_TO_XFAIL=0 PASS_TO_SKIP_UNCLASSIFIED=0"


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print(__doc__, file=sys.stderr)
        return 2
    before, after = argv[1], argv[2]
    tmp = ROOT / "artifacts" / "w0-1" / "tmp" / "selftest"
    tmp.mkdir(parents=True, exist_ok=True)
    # (label, kind, spec, expected NEW_FAIL, expected exit, expected GATES line)
    cases = [
        ("E no change", "none", (), 0, 0, NO_GATES),
        ("A renamed case, before PASSED -> fails now", "fail", (MEM, f"{SAFE}[None-True]", None), 1, 1, NO_GATES),
        ("B renamed case, before FAILED -> fails now", "fail", (MEM, f"{SAFE}[witness1-False]", None), 0, 0, NO_GATES),
        ("C renamed test, param id with no before-case -> fails", "fail", (MEM, f"{SAFE}[None-True]", f"{SAFE}[zzz-True]"), 1, 1,
         "G3 GATES MISSING_IN_AFTER=1 PASS_TO_XFAIL=0 PASS_TO_SKIP_UNCLASSIFIED=0"),
        ("D other renamed test (same param ids) -> one case fails", "fail",
         (VER, "test_parse_accepts_legacy_evidence_reference_as_testimony[record:abc-123]", None), 1, 1, NO_GATES),
        ("F non-renamed test that passed before -> fails", "fail", (VER, DIRECT, None), 1, 1, NO_GATES),
        ("G module collected in before -> collection error in after", "collect_error_replaces_module", (VER,), 1, 1, None),
        ("H module that also failed to collect in before -> collection error in after", "collect_error_replaces_module",
         (BEFORE_COLLECT_ERR_MODULE,), 0, 0, NO_GATES),
        ("I module absent in before -> collection error in after", "collect_error_added", ("tests.selftest_not_in_before",), 1, 1, NO_GATES),
        ("J one passed case removed from after", "remove", (VER, DIRECT), 0, 1,
         "G3 GATES MISSING_IN_AFTER=1 PASS_TO_XFAIL=0 PASS_TO_SKIP_UNCLASSIFIED=0"),
        ("K one passed case becomes xfailed", "xfail", (VER, DIRECT), 0, 1,
         "G3 GATES MISSING_IN_AFTER=0 PASS_TO_XFAIL=1 PASS_TO_SKIP_UNCLASSIFIED=0"),
        ("L one passed case becomes skipped, reason names no resource", "skip", (VER, DIRECT, "SELFTEST skipped without a resource"), 0, 1,
         "G3 GATES MISSING_IN_AFTER=0 PASS_TO_XFAIL=0 PASS_TO_SKIP_UNCLASSIFIED=1"),
        ("M one passed case becomes skipped with ENV_MISSING[selftest_resource]", "skip",
         (VER, DIRECT, "ENV_MISSING[selftest_resource] SELFTEST"), 0, 0, NO_GATES),
    ]
    ok = True
    try:
        for label, kind, spec, want_new_fail, want_exit, want_gates in cases:
            out = tmp / "synthetic_after.xml"
            mutate(after, out, kind, spec)
            code, new_fail, gates, detail = run(before, out)
            good = code == want_exit and new_fail == f"G3 NEW_FAIL={want_new_fail}" and (want_gates is None or gates == want_gates)
            if label.startswith("G "):  # G: gate counts depend on the module size; require MISSING > 0
                good = good and not gates.startswith("G3 GATES MISSING_IN_AFTER=0") and any("COLLECTION_ERROR" in d and "before=collected" in d for d in detail)
            if label.startswith("H "):
                good = good and not detail  # the module is on the before-failed side: no NEW_FAIL line
            if label.startswith("I "):
                good = good and any("COLLECTION_ERROR" in d and "before=ABSENT" in d for d in detail)
            ok &= good
            print(f"[{'OK' if good else 'WRONG'}] {label}: exit={code} (expected {want_exit}); {new_fail}; {gates}")
            for line in detail:
                print(f"      {line[:230]}")
    finally:
        shutil.rmtree(tmp.parent / "selftest", ignore_errors=True)
        try:
            tmp.parent.rmdir()  # only if empty
        except OSError:
            pass
    print("SELFTEST " + ("PASS" if ok else "FAIL"))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
