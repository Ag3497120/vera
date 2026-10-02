"""Make the two decision-A diffs against the tree (never applied to the tree).

Usage: python make_diffs.py <copy_dir>   (a copy of the tree; patched in place, then diffed)
"""
import difflib, pathlib, sys

W = pathlib.Path('/Users/motonisihikoudai/Projects/vera-impl/wt/W1-g-S')
T = pathlib.Path(sys.argv[1])
OUT = W / 'artifacts/w1-g/decision_a'


def patch(rel, old, new):
    src = (W / rel).read_text(encoding='utf-8')
    assert src.count(old) == 1, (rel, old)
    dst = src.replace(old, new)
    (T / rel).write_text(dst, encoding='utf-8')
    return ''.join(difflib.unified_diff(src.splitlines(True), dst.splitlines(True), f'a/{rel}', f'b/{rel}'))


va = patch('verantyx/verifier_agents.py',
'''    try:
        frame.record_verification(
            str(spec["acceptance_record_id"]), "PASS" if all_passed else "FAIL", verifier_id=verifier_id,
''',
'''    # Decision A: "could not be confirmed" is UNVERIFIED, not FAIL. FAIL only when evidence was re-run by a
    # runner, the verifiers agree with each other, and at least one re-run observed a value that differs
    # from the expected one.
    contradicted = any("observed" in item and not item["passed"]
                       for check in checks for item in check["items"])
    if all_passed:
        recorded_result = "PASS"
    elif has_evidence and runner is not None and not evidence_disagrees and contradicted:
        recorded_result = "FAIL"
    else:
        recorded_result = "UNVERIFIED"
    try:
        frame.record_verification(
            str(spec["acceptance_record_id"]), recorded_result, verifier_id=verifier_id,
''')
(OUT / 'verifier_agents_record_result.diff').write_text(va, encoding='utf-8')
tn = patch('tests/attack/test_verifier_agents_fabrication.py',
'''    assert acceptance_id == "accept-1"
    assert result == "PASS"
''',
'''    assert acceptance_id == "accept-1"
    assert result == "UNVERIFIED"
''')
(OUT / 'test_n106_expectation.diff').write_text(tn, encoding='utf-8')
print(len(va.splitlines()), len(tn.splitlines()))
