"""W2-b: reading a verifier's typed verdict out of its text, and the one rule for comparing a re-run to a check.
No process is started."""
from __future__ import annotations

import json

import pytest

from test_conduct_entry_support import _own_modules   # no process is started in this file: only the origin guard
from verantyx.verifier_agents import (ConductCheck, PERSPECTIVES, check_satisfied, extract_conduct_verdict,
                                      new_verdict_nonce)

NONCE = "0123456789abcdef0123456789abcdef"
OTHER = "fedcba9876543210fedcba9876543210"
CHECK = {"argv": ["python", "x.py", "4"], "expect_exit": 0, "expect_stdout": "9"}


def line(value, nonce=NONCE):
    return f"VERA_VERDICT {nonce} " + (value if isinstance(value, str) else json.dumps(value))


def pass_verdict(**extra):
    return {"result": "PASS", "checks": [CHECK], "findings": [], **extra}


def fail_verdict(findings=None, **extra):
    return {"result": "FAIL", "findings": findings if findings is not None else
            [{"perspective": "WEAKENED_CHECKS", "claim": "a test was deleted", "check": CHECK}], **extra}


def malformed(value, why):
    got = extract_conduct_verdict(line(value), nonce=NONCE)
    assert got.status == "MALFORMED", (value, got)
    assert why in got.reason, got.reason
    return got


def test_verantyx_is_loaded_from_this_tree():
    assert _own_modules() == []


# ------------------------------------------------------------------ finding the line
def test_a_well_formed_verdict_is_parsed_with_its_checks_and_findings():
    got = extract_conduct_verdict("some prose\n" + line(pass_verdict(reason="fine")) + "\n", nonce=NONCE)
    assert got.status == "PARSED" and got.verdict.result == "PASS" and got.verdict.reason == "fine"
    assert got.verdict.checks == (ConductCheck(("python", "x.py", "4"), 0, "9"),)
    assert got.verdict_lines == 1 and got.other_nonce_lines == 0 and got.trailing_chars == 1
    failed = extract_conduct_verdict(line(fail_verdict()), nonce=NONCE)
    finding = failed.verdict.findings[0]
    assert finding.perspective == "WEAKENED_CHECKS" and finding.check.argv == ("python", "x.py", "4")


def test_the_json_may_span_several_lines_and_text_after_it_is_only_counted():
    text = line("{\n  \"result\": \"PASS\",\n  \"checks\": [" + json.dumps(CHECK) + "]\n}") + "\nthanks and bye"
    got = extract_conduct_verdict(text, nonce=NONCE)
    assert got.status == "PARSED" and got.trailing_chars == len("\nthanks and bye")


def test_no_verdict_line_is_no_verdict_and_other_nonces_are_counted_not_used():
    got = extract_conduct_verdict(line(pass_verdict(), OTHER) + "\n" + line(pass_verdict(), OTHER), nonce=NONCE)
    assert got.status == "NO_VERDICT" and got.other_nonce_lines == 2
    assert extract_conduct_verdict("", nonce=NONCE).status == "NO_VERDICT"
    assert extract_conduct_verdict("VERA_VERDICT", nonce=NONCE).status == "NO_VERDICT"


def test_a_verdict_with_the_right_nonce_next_to_one_with_a_wrong_nonce_is_still_one_verdict():
    got = extract_conduct_verdict(line(fail_verdict(), OTHER) + "\n" + line(pass_verdict()), nonce=NONCE)
    assert got.status == "PARSED" and got.verdict.result == "PASS" and got.other_nonce_lines == 1


def test_two_verdict_lines_with_the_right_nonce_are_not_resolved_by_choosing():
    for text in (line(pass_verdict()) + "\n" + line(pass_verdict()),
                 line(pass_verdict()) + "\n" + line(fail_verdict())):    # neither the first nor the last wins
        got = extract_conduct_verdict(text, nonce=NONCE)
        assert got.status == "MULTIPLE_VERDICTS" and got.verdict is None and got.verdict_lines == 2


def test_the_nonce_inside_the_json_text_makes_a_second_line_and_is_refused():
    claim = f"see VERA_VERDICT {NONCE} {{}}"
    got = extract_conduct_verdict(line(fail_verdict([{"perspective": "WEAKENED_CHECKS", "claim": claim,
                                                       "check": CHECK}])), nonce=NONCE)
    assert got.status == "MULTIPLE_VERDICTS"


def test_the_json_must_follow_the_tag_directly():
    assert extract_conduct_verdict(f"VERA_VERDICT {NONCE}\n" + json.dumps(pass_verdict()), nonce=NONCE).status == "NO_VERDICT"
    assert extract_conduct_verdict(f"VERA_VERDICT {NONCE} not json", nonce=NONCE).status == "MALFORMED"
    assert extract_conduct_verdict(f"VERA_VERDICT {NONCE} [1]", nonce=NONCE).status == "MALFORMED"


# ------------------------------------------------------------------ the type rules
def test_duplicate_keys_unknown_keys_and_non_finite_numbers_are_malformed():
    malformed('{"result":"PASS","result":"FAIL"}', "cannot be read")
    malformed({**pass_verdict(), "extra": 1}, "unknown key")
    malformed({"result": "PASS", "checks": [{**CHECK, "cwd": "/"}]}, "unknown key")
    malformed({"result": "FAIL", "findings": [{"perspective": "WEAKENED_CHECKS", "claim": "c", "extra": 1}]}, "unknown key")
    malformed('{"result":"PASS","checks":[{"argv":["x"],"expect_exit":NaN}]}', "cannot be read")


def test_the_result_and_the_shape_rules():
    malformed({"result": "pass"}, "result must be")
    malformed({"result": "MAYBE"}, "result must be")
    malformed({"result": "PASS", "findings": [{"perspective": "WEAKENED_CHECKS", "claim": "c", "check": CHECK}]},
              "PASS verdict must not carry findings")
    malformed({"result": "FAIL"}, "at least one finding")
    malformed({"result": "FAIL", "findings": []}, "at least one finding")
    malformed({"result": "UNDETERMINED"}, "must say why")
    malformed({"result": "UNDETERMINED", "reason": "   "}, "must say why")
    assert extract_conduct_verdict(line({"result": "UNDETERMINED", "reason": "cannot tell"}), nonce=NONCE).status == "PARSED"
    malformed({"result": "PASS", "checks": "x"}, "must be lists")


def test_a_finding_without_a_check_is_parsed_and_will_be_counted_as_no_evidence():
    got = extract_conduct_verdict(line({"result": "FAIL", "findings": [
        {"perspective": "UNRELATED_CHANGE", "claim": "it touches an unrelated file"}]}), nonce=NONCE)
    assert got.status == "PARSED" and got.verdict.findings[0].check is None


def test_the_perspective_set_is_closed():
    assert PERSPECTIVES == ("HARDCODED_ACCEPTANCE", "WEAKENED_CHECKS", "UNRELATED_CHANGE", "INVARIANT_VIOLATION")
    for name in PERSPECTIVES:
        got = extract_conduct_verdict(line(fail_verdict([{"perspective": name, "claim": "c", "check": CHECK}])), nonce=NONCE)
        assert got.status == "PARSED"
    malformed(fail_verdict([{"perspective": "STYLE", "claim": "c", "check": CHECK}]), "perspective")
    malformed(fail_verdict([{"claim": "c", "check": CHECK}]), "perspective")


@pytest.mark.parametrize("bad, why", [
    ({"argv": [], "expect_exit": 0}, "argv"),
    ({"argv": "python x.py", "expect_exit": 0}, "argv"),
    ({"argv": ["python", ""], "expect_exit": 0}, "argv"),
    ({"argv": ["python", 1], "expect_exit": 0}, "argv"),
    ({"argv": ["x"] * 65, "expect_exit": 0}, "argv"),
    ({"argv": ["x" * 513], "expect_exit": 0}, "argv"),
    ({"argv": ["a\nb"], "expect_exit": 0}, "argv"),
    ({"argv": ["a‮b"], "expect_exit": 0}, "argv"),
    ({"argv": ["x"], "expect_exit": True}, "expect_exit"),
    ({"argv": ["x"], "expect_exit": "0"}, "expect_exit"),
    ({"argv": ["x"], "expect_exit": 2 ** 31}, "expect_exit"),
    ({"argv": ["x"]}, "expect_exit"),
    ({"expect_exit": 0}, "argv"),
    ({"argv": ["x"], "expect_exit": 0, "expect_stdout": 5}, "expect_stdout"),
    ({"argv": ["x"], "expect_exit": 0, "expect_stdout": "x" * 4097}, "expect_stdout"),
])
def test_a_check_is_typed_strictly(bad, why):
    malformed({"result": "PASS", "checks": [bad]}, why)


def test_boundary_values_of_a_check_are_accepted():
    ok = {"argv": ["x" * 512] * 64, "expect_exit": -(2 ** 31), "expect_stdout": "line\nwith newline\n"}
    got = extract_conduct_verdict(line({"result": "PASS", "checks": [ok]}), nonce=NONCE)
    assert got.status == "PARSED" and got.verdict.checks[0].expect_exit == -(2 ** 31)


def test_at_most_sixteen_checks_and_findings_together():
    sixteen = {"result": "PASS", "checks": [{**CHECK, "argv": ["x", str(i)]} for i in range(16)]}
    assert extract_conduct_verdict(line(sixteen), nonce=NONCE).status == "PARSED"
    malformed({"result": "PASS", "checks": [{**CHECK, "argv": ["x", str(i)]} for i in range(17)]}, "exceed 16")
    mixed = {"result": "FAIL", "checks": [CHECK] * 8, "findings": [
        {"perspective": "WEAKENED_CHECKS", "claim": "c", "check": CHECK}] * 9}
    malformed(mixed, "exceed 16")


def test_claims_and_reasons_are_single_line_text_with_a_limit():
    malformed(pass_verdict(reason="a\nb"), "reason")
    malformed(pass_verdict(reason="x" * 2001), "reason")
    assert extract_conduct_verdict(line(pass_verdict(reason="x" * 2000)), nonce=NONCE).status == "PARSED"
    malformed(fail_verdict([{"perspective": "WEAKENED_CHECKS", "claim": "", "check": CHECK}]), "claim")
    malformed(fail_verdict([{"perspective": "WEAKENED_CHECKS", "claim": "a\x00b", "check": CHECK}]), "claim")
    malformed(fail_verdict([{"perspective": "WEAKENED_CHECKS", "claim": "x" * 2001, "check": CHECK}]), "claim")


# ------------------------------------------------------------------ the comparison rule (one place)
@pytest.mark.parametrize("expect_stdout, stdout, exit_code, expected", [
    ("9", "9\n", 0, True), ("9", "9\r\n", 0, True), ("9\n", "9", 0, True), ("9", "9", 0, True),
    ("9", "9\n\n", 0, True),            # every trailing CR / LF is dropped on both sides
    ("9", " 9\n", 0, False),            # nothing else is trimmed
    ("9", "9 \n", 0, False), ("9", "90\n", 0, False), ("9", "", 0, False), ("9", None, 0, False),
    ("9", "9\n", 1, False),             # the exit status must match as well
    (None, "anything\n", 0, True), (None, None, 0, True), (None, "x", 3, False),
])
def test_the_one_rule_for_comparing_a_re_run_to_a_check(expect_stdout, stdout, exit_code, expected):
    check = ConductCheck(("x",), 0, expect_stdout)
    assert check_satisfied(check, exit_code, stdout) is expected


def test_a_missing_exit_status_never_satisfies_a_check():
    assert check_satisfied(ConductCheck(("x",), 0), None, "") is False
    assert check_satisfied(ConductCheck(("x",), 0), True, "") is False          # a bool is not an exit status


def test_nonces_are_32_hex_characters_and_not_repeated():
    nonces = {new_verdict_nonce() for _ in range(50)}
    assert len(nonces) == 50 and all(len(n) == 32 and int(n, 16) >= 0 for n in nonces)
