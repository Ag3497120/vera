import pytest

from verantyx.conductor import AgentQuestion, ProjectFrame


def _reference_next(states, edges):
    """Independent reference for a small, conflict-free phase graph."""
    ready = set()
    for before, after in edges:
        if (before in states and after in states and
                states[before] == "完了" and states[after] != "完了"):
            ready.add(after)
    if len(ready) == 1:
        return "ANSWER", next(iter(ready))
    return "ESCALATE", None


@pytest.mark.parametrize(
    "states,edges",
    [
        ({"A": "完了", "B": "未着手", "C": "未着手"}, [("A", "B")]),
        ({"A": "未着手", "B": "未着手"}, [("A", "B")]),
        ({"A": "完了", "B": "完了"}, [("A", "B")]),
        ({"A": "完了", "B": "完了", "C": "未着手"}, [("A", "B"), ("A", "C")]),
        ({"A": "完了", "B": "未着手", "C": "未着手"}, [("A", "B"), ("A", "C")]),
        ({"A": "完了", "B": "未着手"}, [("A", "missing")]),
    ],
)
def test_generated_order_cases_match_naive_reference(tmp_path, states, edges):
    frame = ProjectFrame(tmp_path / "frame.jsonl")
    reason = frame.add_decision("ordering basis", "recorded phase order")
    for task, state in states.items():
        frame.add_task(task, state)
    for before, after in edges:
        frame.add_order(before, after, reason["id"])

    reply = frame.answer(AgentQuestion("q", "What is the next phase?"))
    assert (reply.kind, reply.answer) == _reference_next(states, edges)


@pytest.mark.xfail(
    strict=False,
    reason="DEFECT: order endpoints do not use normalized task identity",
)
def test_order_identity_case_difference_is_reproduced_twice(tmp_path):
    observations = []
    for run in range(2):
        frame = ProjectFrame(tmp_path / f"identity-{run}.jsonl")
        reason = frame.add_decision("ordering basis", "recorded phase order")
        frame.add_task("Draft", "完了")
        frame.add_task("Review", "未着手")
        frame.add_order("draft", "review", reason["id"])

        reply = frame.answer(AgentQuestion("q", "What is the next phase?"))
        observations.append((reply.kind, reply.answer))
    assert observations == [("ANSWER", "Review")] * 2


def test_policy_answer_cites_its_decision_authority(tmp_path):
    frame = ProjectFrame(tmp_path / "policy.jsonl")
    authority = frame.add_decision("local edits", "permitted")
    policy = frame.add_policy("CONFIRM", "modify local draft", "yes", authority["id"])

    reply = frame.answer(AgentQuestion("q", "May I modify local draft?"))
    assert reply.kind == "ANSWER"
    assert reply.answer == "yes"
    assert set(reply.record_ids) == {authority["id"], policy["id"]}


def test_protected_action_escalates_even_with_an_allow_policy(tmp_path):
    frame = ProjectFrame(tmp_path / "protected.jsonl")
    authority = frame.add_decision("publishing", "permitted in principle")
    frame.add_policy("CONFIRM", "publish local draft", "yes", authority["id"])

    reply = frame.answer(AgentQuestion("q", "May I publish the local draft?"))
    assert reply.kind == "ESCALATE"
    assert reply.missing == "human"
    assert "outside frame authority" in reply.reason


def test_policy_does_not_answer_a_different_condition(tmp_path):
    frame = ProjectFrame(tmp_path / "unmatched.jsonl")
    authority = frame.add_decision("local edits", "permitted")
    frame.add_policy("CONFIRM", "modify local draft", "yes", authority["id"])

    reply = frame.answer(AgentQuestion("q", "May I change the project schedule?"))
    assert reply.kind == "ESCALATE"
    assert reply.missing == "POLICY"
    assert reply.answer is None


@pytest.mark.parametrize(
    "question",
    [
        AgentQuestion("q", "  "),
        AgentQuestion("q", "Which option should I choose?", options=("A", "B")),
    ],
)
def test_malformed_questions_escalate_without_an_answer(tmp_path, question):
    frame = ProjectFrame(tmp_path / "malformed.jsonl")
    reply = frame.answer(question)
    assert reply.kind == "ESCALATE"
    assert reply.answer is None


def test_done_claim_without_a_goal_escalates(tmp_path):
    frame = ProjectFrame(tmp_path / "no-goal.jsonl")
    reply = frame.answer(AgentQuestion(
        "q", "What is the task status?",
        claimed_state={"task_id": "task-a", "state": "done"},
    ))
    assert reply.kind == "ESCALATE"
    assert reply.missing == "GOAL"
    assert reply.answer is None


def test_human_judged_acceptance_needs_human_verification(tmp_path):
    frame = ProjectFrame(tmp_path / "human.jsonl")
    frame.add_acceptance("task-a", "reviewed by owner", human_judged=True)
    frame.add_goal("task-a", "reviewed by owner")

    reply = frame.answer(AgentQuestion(
        "q", "What is the task status?",
        claimed_state={"task_id": "task-a", "state": "complete"},
    ))
    assert reply.kind == "ESCALATE"
    assert reply.missing == "human verification"
    assert reply.answer is None


def test_independent_acceptance_requests_a_separate_verifier(tmp_path):
    artifact = tmp_path / "artifact.txt"
    artifact.write_text("approved marker\n", encoding="utf-8")
    frame = ProjectFrame(tmp_path / "independent.jsonl")
    frame.add_acceptance(
        "task-a", "approval marker", witness_kind="text_in_file",
        target={"path": str(artifact), "needle": "approved marker"}, independent=True,
    )
    frame.add_goal("task-a", "approval marker")

    reply = frame.answer(AgentQuestion(
        "q", "What is the task status?",
        claimed_state={"task_id": "task-a", "state": "done", "claimant_id": "agent-a"},
    ))
    assert reply.kind == "ASK_VERIFIER"
    assert reply.template_id == "acceptance_independent_v1"
    assert reply.target == "approval marker"
    assert reply.spec["must_be_different_agent_from"] == "agent-a"


def test_independent_pass_is_required_before_done_is_answered(tmp_path):
    artifact = tmp_path / "artifact.txt"
    artifact.write_text("approved marker\n", encoding="utf-8")
    frame = ProjectFrame(tmp_path / "verified.jsonl")
    acceptance = frame.add_acceptance(
        "task-a", "approval marker", witness_kind="text_in_file",
        target={"path": str(artifact), "needle": "approved marker"}, independent=True,
    )
    frame.add_goal("task-a", "approval marker")

    pending = frame.verify_claim("task-a", {"claimant_id": "agent-a"})
    assert pending.kind == "ASK_VERIFIER"
    frame.record_verification(
        acceptance["id"], "PASS", verifier_id="agent-b", claimant_id="agent-a",
        evidence_ref=str(artifact), template_id="acceptance_independent_v1",
    )

    verified = frame.verify_claim("task-a", {"claimant_id": "agent-a"})
    assert verified.kind == "ANSWER"
    assert verified.answer == "done"
