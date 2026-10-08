import pytest

from verantyx.conductor import AgentQuestion, ProjectFrame
from verantyx.memory_frame import WriteRejected


def make_frame(tmp_path, name="frame", command_runner=None):
    return ProjectFrame(tmp_path / f"{name}.jsonl", command_runner=command_runner)


def test_ready_order_answer_cites_order_tasks_and_authority(tmp_path):
    frame = make_frame(tmp_path)
    authority = frame.add_decision("build sequence", "design precedes build")
    predecessor = frame.add_task("design", "完了")
    successor = frame.add_task("build", "未着手")
    edge = frame.add_order("design", "build", authority["id"])

    reply = frame.answer(AgentQuestion("q1", "What is the next item in the order of work?"))

    assert reply.kind == "ANSWER"
    assert reply.answer == "build"
    assert {edge["id"], predecessor["id"], successor["id"], authority["id"]} <= set(reply.record_ids)


def test_order_with_two_ready_successors_abstains_and_cites_both_edges(tmp_path):
    frame = make_frame(tmp_path)
    authority = frame.add_decision("work sequence", "design comes first")
    frame.add_task("design", "完了")
    frame.add_task("build", "未着手")
    frame.add_task("review", "未着手")
    build_edge = frame.add_order("design", "build", authority["id"])
    review_edge = frame.add_order("design", "review", authority["id"])

    reply = frame.answer(AgentQuestion("q2", "What should happen next?"))

    assert reply.kind == "ESCALATE"
    assert "ties abstain" in reply.reason
    assert {build_edge["id"], review_edge["id"], authority["id"]} <= set(reply.record_ids)


def test_order_ignores_edge_whose_authority_was_superseded(tmp_path):
    frame = make_frame(tmp_path)
    old_authority = frame.add_decision("release order", "design before build")
    frame.add_task("design", "完了")
    frame.add_task("build", "未着手")
    edge = frame.add_order("design", "build", old_authority["id"])
    frame.add_decision("release order", "review before build", supersedes=old_authority["id"])

    reply = frame.answer(AgentQuestion("q3", "What is the next phase?"))

    assert reply.kind == "ESCALATE"
    assert reply.answer is None
    assert edge["id"] in reply.record_ids
    assert old_authority["id"] not in reply.record_ids


def test_confirm_policy_answer_cites_policy_and_authority(tmp_path):
    frame = make_frame(tmp_path)
    authority = frame.add_decision("internal draft permission", "internal drafts are allowed")
    policy = frame.add_policy("CONFIRM", "internal draft", "yes", authority["id"])

    reply = frame.answer(AgentQuestion("q4", "May I prepare the internal draft?"))

    assert reply.kind == "ANSWER"
    assert reply.answer == "yes"
    assert {policy["id"], authority["id"]} <= set(reply.record_ids)


def test_equally_specific_conflicting_policies_abstain_with_sources(tmp_path):
    frame = make_frame(tmp_path)
    allow_authority = frame.add_decision("draft approval", "approve the internal draft")
    deny_authority = frame.add_decision("external approval", "deny the internal draft")
    allow = frame.add_policy("CONFIRM", "internal draft", "yes", allow_authority["id"])
    deny = frame.add_policy("CONFIRM", "internal draft", "no", deny_authority["id"])

    reply = frame.answer(AgentQuestion("q5", "May I prepare the internal draft?"))

    assert reply.kind == "ESCALATE"
    assert "POLICY records conflict" in reply.reason
    assert {allow["id"], deny["id"], allow_authority["id"], deny_authority["id"]} <= set(reply.record_ids)


@pytest.mark.xfail(strict=False, reason="DEFECT: substring policy matching treats disapprove as approve")
def test_policy_condition_does_not_answer_opposite_partial_word(tmp_path):
    replies = []
    for index, wording in enumerate(("May I disapprove this proposal?", "Should I disapprove this change?")):
        frame = make_frame(tmp_path, f"partial-{index}")
        authority = frame.add_decision(f"approval authority {index}", "approve this proposal")
        frame.add_policy("CONFIRM", "approve", "yes", authority["id"])
        replies.append(frame.answer(AgentQuestion(f"q6-{index}", wording)))

    assert [(reply.kind, reply.answer) for reply in replies] == [("ESCALATE", None), ("ESCALATE", None)]


def test_choice_maps_one_unique_option_and_cites_frame_terms(tmp_path):
    frame = make_frame(tmp_path)
    authority = frame.add_decision("backend policy", "alpha")
    other_term = frame.add_decision("alternate backend", "beta")
    policy = frame.add_policy("CHOICE", "backend", "alpha", authority["id"])

    reply = frame.answer(AgentQuestion("q7", "Which backend should I choose?", ["alpha", "beta"]))

    assert reply.kind == "ANSWER"
    assert reply.answer == "alpha"
    assert {authority["id"], other_term["id"], policy["id"]} <= set(reply.record_ids)


def test_policy_cannot_answer_with_protected_outside_authority_action(tmp_path):
    frame = make_frame(tmp_path)
    authority = frame.add_decision("draft work", "prepare an internal draft")
    policy = frame.add_policy("CONFIRM", "internal draft", "publish externally", authority["id"])

    reply = frame.answer(AgentQuestion("q8", "May I prepare the internal draft?"))

    assert reply.kind == "ESCALATE"
    assert reply.missing == "human"
    assert policy["id"] in reply.record_ids


def test_command_witness_done_answer_cites_goal_and_acceptance(tmp_path):
    frame = make_frame(tmp_path, command_runner=lambda target: {"returncode": 0})
    acceptance = frame.add_acceptance(
        "task-a", "local check", witness_kind="command_exit",
        target={"command": ["local-check"], "expected_exit": 0},
    )
    goal = frame.add_goal("task-a", "local check")

    reply = frame.verify_claim("task-a", {"claimant_id": "agent:claimant"})

    assert reply.kind == "ANSWER"
    assert reply.answer == "done"
    assert {goal["id"], acceptance["id"]} <= set(reply.record_ids)


def test_independent_verification_requires_different_claimant_and_is_cited(tmp_path):
    frame = make_frame(tmp_path, command_runner=lambda target: 0)
    acceptance = frame.add_acceptance(
        "task-b", "independent check", witness_kind="command_exit",
        target={"command": "local-check", "expected_exit": 0}, independent=True,
    )
    goal = frame.add_goal("task-b", "independent check")

    with pytest.raises(WriteRejected):
        frame.record_verification(
            acceptance["id"], "PASS", verifier_id="agent:claimant", claimant_id="agent:claimant",
            template_id="acceptance_independent_v1", evidence_ref="local-check output",
        )

    verification = frame.record_verification(
        acceptance["id"], "PASS", verifier_id="agent:verifier", claimant_id="agent:claimant",
        template_id="acceptance_independent_v1", evidence_ref="local-check output",
    )
    reply = frame.verify_claim("task-b", {"claimant_id": "agent:claimant"})

    assert reply.kind == "ANSWER"
    assert reply.answer == "done"
    assert {goal["id"], acceptance["id"], verification["id"]} <= set(reply.record_ids)


@pytest.mark.xfail(strict=False, reason="DEFECT: independent PASS is accepted without inspected evidence reference")
def test_independent_pass_without_evidence_reference_cannot_verify_done(tmp_path):
    replies = []
    for index in range(2):
        frame = make_frame(tmp_path, f"missing-evidence-{index}", command_runner=lambda target: 0)
        acceptance = frame.add_acceptance(
            f"task-{index}", "independent check", witness_kind="command_exit",
            target={"command": "local-check", "expected_exit": 0}, independent=True,
        )
        frame.add_goal(f"task-{index}", "independent check")
        frame.record_verification(
            acceptance["id"], "PASS", verifier_id=f"agent:verifier-{index}",
            claimant_id=f"agent:claimant-{index}", template_id="acceptance_independent_v1",
        )
        replies.append(frame.verify_claim(f"task-{index}", {"claimant_id": f"agent:claimant-{index}"}))

    assert [(reply.kind, reply.answer) for reply in replies] == [
        ("ASK_VERIFIER", None), ("ASK_VERIFIER", None)
    ]


def test_malformed_question_escalates_without_fabricated_answer(tmp_path):
    frame = make_frame(tmp_path)

    reply = frame.answer(AgentQuestion("q9", "", claimed_state="done"))

    assert reply.kind == "ESCALATE"
    assert reply.answer is None
    assert reply.missing == "agent question"
