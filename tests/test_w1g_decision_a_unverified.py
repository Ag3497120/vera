"""W1-g decision A: "could not be confirmed" is its own verification record type, not FAIL.

The conductor accepts, validates and reads an ``UNVERIFIED`` verification record. It does not
turn it into "failed", does not ignore it (that would fall back to ASK_VERIFIER, as if nothing
had been recorded) and never lets it complete the task.
"""
import pytest

from verantyx.conductor import ProjectFrame
from verantyx.memory_frame import Memory, WriteRejected

CLAIMANT = "worker-a"
TEMPLATE = "acceptance_independent_v1"


def _frame(tmp_path):
    frame = ProjectFrame(Memory(str(tmp_path / "memory.jsonl")), command_runner=lambda spec: 0)
    return frame


def _independent(tmp_path):
    frame = _frame(tmp_path)
    acceptance = frame.add_acceptance("task-1", "independent check", witness_kind="command_exit",
                                      target={"command": ["check-acceptance"], "expected_exit": 0},
                                      independent=True)
    frame.add_goal("task-1", "independent check")
    return frame, acceptance


def _record(frame, acceptance, result, *, supersedes=None, verifier="agent-auditor", claimant=CLAIMANT):
    return frame.record_verification(acceptance["id"], result, verifier_id=verifier, claimant_id=claimant,
                                     evidence_ref="evidence-1", template_id=TEMPLATE, supersedes=supersedes)


def _verify(frame):
    return frame.verify_claim("task-1", {"claimant_id": CLAIMANT})


def test_unverified_record_is_accepted_and_read_as_neither_failure_nor_done(tmp_path):
    frame, acceptance = _independent(tmp_path)
    assert _verify(frame).kind == "ASK_VERIFIER"
    record = _record(frame, acceptance, "UNVERIFIED")
    reply = _verify(frame)
    assert record["slots"]["result"] == "UNVERIFIED"
    assert reply.kind == "ESCALATE"
    assert reply.reason.startswith("UNVERIFIED:")
    assert "failed" not in reply.reason
    assert record["id"] in reply.record_ids
    assert reply.kind != "ANSWER" and reply.kind != "ASK_VERIFIER"


def test_unverified_is_superseded_by_pass_and_then_completes(tmp_path):
    frame, acceptance = _independent(tmp_path)
    first = _record(frame, acceptance, "UNVERIFIED")
    second = _record(frame, acceptance, "PASS", supersedes=first["id"])
    reply = _verify(frame)
    assert reply.kind == "ANSWER" and reply.answer == "done"
    assert second["id"] in reply.record_ids


def test_fail_record_keeps_its_own_failure_message(tmp_path):
    frame, acceptance = _independent(tmp_path)
    _record(frame, acceptance, "FAIL")
    reply = _verify(frame)
    assert reply.kind == "ESCALATE"
    assert "independent verification failed" in reply.reason
    assert not reply.reason.startswith("UNVERIFIED:")


def test_unverified_can_supersede_a_fail_and_a_pass(tmp_path):
    frame, acceptance = _independent(tmp_path)
    failed = _record(frame, acceptance, "FAIL")
    unverified = _record(frame, acceptance, "UNVERIFIED", supersedes=failed["id"])
    reply = _verify(frame)
    assert reply.reason.startswith("UNVERIFIED:") and unverified["id"] in reply.record_ids
    passed = _record(frame, acceptance, "PASS", supersedes=unverified["id"])
    assert _verify(frame).answer == "done"
    again = _record(frame, acceptance, "UNVERIFIED", supersedes=passed["id"])
    assert _verify(frame).reason.startswith("UNVERIFIED:") and again["id"] in _verify(frame).record_ids


@pytest.mark.parametrize("bad", ["MAYBE", "pass", "unverified", "", "PASS "])
def test_other_result_values_are_still_rejected(tmp_path, bad):
    frame, acceptance = _independent(tmp_path)
    with pytest.raises(WriteRejected, match="PASS, FAIL or UNVERIFIED"):
        _record(frame, acceptance, bad)


def test_human_judged_unverified_does_not_complete(tmp_path):
    frame = _frame(tmp_path)
    acceptance = frame.add_acceptance("task-1", "visual check", human_judged=True)
    frame.add_goal("task-1", "visual check")
    record = frame.record_verification(acceptance["id"], "UNVERIFIED", verifier_id="human:reviewer",
                                       claimant_id=CLAIMANT, evidence_ref="could not open the build")
    reply = _verify(frame)
    assert reply.kind == "ESCALATE" and reply.answer is None
    assert reply.reason.startswith("UNVERIFIED:") and record["id"] in reply.record_ids


def test_verifier_must_still_differ_from_claimant_for_unverified(tmp_path):
    frame, acceptance = _independent(tmp_path)
    with pytest.raises(WriteRejected):
        _record(frame, acceptance, "UNVERIFIED", verifier=CLAIMANT)


def test_independent_unverified_still_needs_the_other_checks(tmp_path):
    frame, acceptance = _independent(tmp_path)
    with pytest.raises(WriteRejected):          # a human may not record an independent agent result
        frame.record_verification(acceptance["id"], "UNVERIFIED", verifier_id="human:r", claimant_id=CLAIMANT,
                                  evidence_ref="x", template_id=TEMPLATE)
    with pytest.raises(WriteRejected):          # the returned template must be cited
        frame.record_verification(acceptance["id"], "UNVERIFIED", verifier_id="agent-auditor",
                                  claimant_id=CLAIMANT, evidence_ref="x")


def test_verifier_result_schema_still_offers_only_pass_or_fail(tmp_path):
    frame, _ = _independent(tmp_path)
    ask = _verify(frame)
    assert ask.kind == "ASK_VERIFIER"
    assert ask.spec["result_schema"]["result"] == ["PASS", "FAIL"]
