"""Executable assertions for the frozen W3-b3 attack corpus."""
import importlib.util
import json
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("w3b3_attack_runner", HERE / "run_attack.py")
RUNNER = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(RUNNER)


@pytest.fixture(scope="module")
def rows():
    path = RUNNER.RESULTS / "observations.jsonl"
    assert path.is_file(), "run the frozen attack first: python attacks/W3-b3/run_attack.py"
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def _violations(rows, predicate):
    return ["%s: %s" % (row["id"], row["text"]) for row in rows for reason in predicate(row)]


def test_placement_free_output_is_byte_identical_to_the_base_for_all_170_sentences(rows):
    bad = ["%s: %s" % (r["id"], r["text"]) for r in rows if not r["absent"]["byte_equal_base"]]
    assert not bad, "placement-free base-byte mismatches: " + repr(bad)


def test_frozen_read_and_abstain_expectations(rows):
    def check(row):
        expected = row["expected"]
        if expected["mode"] == "base_parity":
            return []
        output = row["configured"]["output"]
        explain = row["configured"]["explain"]
        if expected["mode"] == "abstain":
            if output.get("readable") is True or output.get("relations"):
                return ["expected abstention, got readable/relation=%r" % (output.get("relations"),)]
            if explain.get("read") is True:
                return ["diagnostic says the W3-b3 path read the sentence"]
            return []
        bad = []
        if output.get("readable") is not True:
            return ["expected read, got abstention %r" % output.get("abstain")]
        expected_relation = expected.get("relation")
        matches = [rel for rel in output.get("relations", []) if rel.get("type") == expected_relation]
        if len(matches) != 1:
            bad.append("expected one %s relation, got %r" % (expected_relation, output.get("relations")))
        if expected_relation == "relative" and len(matches) == 1:
            rel = matches[0]
            if rel.get("head") != expected["head"]:
                bad.append("expected head %r, got %r" % (expected["head"], rel.get("head")))
        if "polarities" in expected:
            got = [clause.get("polarity") for clause in output.get("clauses", [])]
            if got != expected["polarities"]:
                bad.append("expected local polarities %r, got %r" % (expected["polarities"], got))
        if "tense" in expected:
            got = [clause.get("tense") for clause in output.get("clauses", [])]
            if got != expected["tense"]:
                bad.append("expected local tense %r, got %r" % (expected["tense"], got))
        for key, value in expected.get("role_values", {}).items():
            clause_index, role = key.split(".", 1)
            clauses = output.get("clauses", [])
            got = clauses[int(clause_index)].get("roles", {}).get(role) if int(clause_index) < len(clauses) else None
            if got != value:
                bad.append("expected %s=%r, got %r" % (key, value, got))
        return bad

    # W5-e2 (auditor's ruling K-W3B3, 2026-10-04 04:42): the copy asserts only the 6 sentences that hit (a coordination or a disjunction that the base read: now an abstention)
    # and the 5 control sentences the base read correctly (unchanged); the 38 coverage rows the attacker did not count as violations (report section 4) are not asserted here.
    # `check` is as it was.  The 11 ids must all be in `rows` (a row that disappears must not make this pass silently).
    hits = ["PARALLEL-002", "PARALLEL-003", "PARALLEL-008", "PARALLEL-011", "PARALLEL-017", "PARALLEL-020"]
    controls = ["RELATIVE-001", "SCOPE-003", "SCOPE-005", "SCOPE-007", "ELLIPSIS-019"]
    by_id = {row["id"]: row for row in rows}
    assert [i for i in hits + controls if i not in by_id] == []
    assert [by_id[i]["expected"]["mode"] for i in hits] == ["abstain"] * 6
    assert [by_id[i]["expected"]["mode"] for i in controls] == ["read"] * 5
    bad = _violations([by_id[i] for i in hits + controls], check)
    assert not bad, "frozen outcome/role/polarity expectations failed: " + repr(bad)


def test_english_never_gains_a_japanese_relative_head_or_changes_the_base(rows):
    bad = []
    for row in rows:
        if row["group"] != "english":
            continue
        output = row["configured"]["output"]
        events = row["configured"]["events"]
        if not row["configured"]["base_equal"]:
            bad.append("%s: configured English output differs from base" % row["id"])
        if any("head" in rel for rel in output.get("relations", [])):
            bad.append("%s: Japanese relation head appeared in English output" % row["id"])
        if any("embedded" in filler for cross in events.get("crosses", [])
               for arm in cross.get("arms", {}).values() for filler in arm.get("fillers", [])):
            bad.append("%s: embedded Japanese cross appeared in English output" % row["id"])
    assert not bad, "English route leakage: " + repr(bad)


def test_every_returned_relative_head_is_embedded_in_its_exact_target_arm(rows):
    bad = []
    for row in rows:
        output = row["configured"]["output"]
        relatives = [rel for rel in output.get("relations", []) if rel.get("type") == "relative"]
        if not relatives:
            continue
        events = row["configured"]["events"]
        crosses = events.get("crosses", [])
        for rel in relatives:
            head = rel.get("head")
            if not isinstance(head, dict):
                bad.append("%s: relative relation omitted head" % row["id"])
                continue
            src, dst = rel.get("from"), rel.get("to")
            role = head.get("to_role")
            try:
                filler = crosses[dst]["arms"][role]["fillers"][0]
                embedded = filler.get("embedded")
                if embedded != crosses[src]:
                    bad.append("%s: embedded cross is not relation source" % row["id"])
                if any("embedded" in f for arm in embedded.get("arms", {}).values() for f in arm.get("fillers", [])):
                    bad.append("%s: embedding is nested beyond one level" % row["id"])
            except (IndexError, KeyError, TypeError):
                bad.append("%s: relation head has no matching target filler" % row["id"])
            if events.get("counts", {}).get("crosses") != len(crosses):
                bad.append("%s: embedded cross changed the cross count" % row["id"])
        if events.get("status") != "CROSSED":
            bad.append("%s: readable relative output did not cross: %r" % (row["id"], events.get("status")))
    assert not bad, "relative cross embedding violations: " + repr(bad)


def test_parallel_and_disjunctive_filler_cases_are_not_read_as_single_winners(rows):
    bad = []
    for row in rows:
        if row["group"] == "parallel" and row["configured"]["output"].get("readable") is True:
            bad.append("%s: %s -> %r" % (row["id"], row["text"], row["configured"]["output"].get("clauses")))
    assert not bad, "parallel/disjunctive fillers were collapsed or distributed: " + repr(bad)
