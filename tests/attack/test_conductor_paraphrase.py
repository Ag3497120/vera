import pytest

from verantyx.conductor import AgentQuestion, ProjectFrame, classify_question


def _archive_frame(path, answer="yes"):
    frame = ProjectFrame(path)
    authority = frame.add_decision("archive decision", "Archive is allowed")
    frame.add_policy("CONFIRM", "archive the draft", answer, authority["id"])
    return frame


def test_order_surface_variants_keep_order_classification():
    questions = (
        "What is the next phase?",
        "Which phase follows this one?",
        "Could you tell me the order of work?",
        "次はどの作業ですか？",
    )

    assert [classify_question(text) for text in questions] == ["ORDER"] * len(questions)


def test_confirm_polite_variants_keep_confirm_classification():
    questions = (
        "Can I archive the draft?",
        "Could I archive the draft?",
        "May I archive the draft?",
    )

    assert [classify_question(text) for text in questions] == ["CONFIRM"] * len(questions)


def test_confirm_paraphrases_use_the_same_active_policy(tmp_path):
    frame = _archive_frame(tmp_path / "memory.jsonl")

    replies = [
        frame.answer(AgentQuestion("q", text))
        for text in (
            "Can I archive the draft?",
            "Could I archive the draft?",
            "May I archive the draft?",
        )
    ]

    assert [(reply.kind, reply.answer) for reply in replies] == [("ANSWER", "yes")] * 3


def test_order_paraphrases_return_the_same_ready_successor(tmp_path):
    frame = ProjectFrame(tmp_path / "memory.jsonl")
    reason = frame.add_decision("phase ordering", "A must precede B")
    frame.add_order("phase A", "phase B", reason["id"])
    frame.add_task("phase A", "完了")
    frame.add_task("phase B", "未着手")

    replies = [
        frame.answer(AgentQuestion("q", text))
        for text in ("What is the next phase?", "Which phase follows phase A?")
    ]

    assert [(reply.kind, reply.answer) for reply in replies] == [("ANSWER", "phase B")] * 2


def test_changed_protected_action_escalates_despite_related_policy(tmp_path):
    frame = _archive_frame(tmp_path / "memory.jsonl")

    reply = frame.answer(AgentQuestion("q", "Can I delete the draft?"))

    assert reply.kind == "ESCALATE"
    assert reply.answer is None


def test_confirm_without_matching_policy_escalates(tmp_path):
    frame = ProjectFrame(tmp_path / "memory.jsonl")

    reply = frame.answer(AgentQuestion("q", "Can I archive the draft?"))

    assert reply.kind == "ESCALATE"
    assert reply.missing == "POLICY"


def test_malformed_option_list_escalates(tmp_path):
    frame = ProjectFrame(tmp_path / "memory.jsonl")

    reply = frame.answer(AgentQuestion("q", "Which option?", ["", "phase B"]))

    assert reply.kind == "ESCALATE"
    assert reply.answer is None


def test_done_claim_without_task_identity_escalates(tmp_path):
    frame = ProjectFrame(tmp_path / "memory.jsonl")

    reply = frame.answer(AgentQuestion("q", "Is it done?", claimed_state="done"))

    assert reply.kind == "ESCALATE"
    assert reply.missing == "task_id"


@pytest.mark.xfail(
    strict=False,
    reason="DEFECT: unrecognized polite confirmation paraphrases do not reach the matching policy",
)
def test_would_it_be_okay_paraphrases_keep_the_policy_verdict(tmp_path):
    frame = _archive_frame(tmp_path / "memory.jsonl")

    replies = [
        frame.answer(AgentQuestion("q", text))
        for text in (
            "Would it be okay if I archive the draft?",
            "Would archiving the draft be acceptable?",
        )
    ]

    assert [(reply.kind, reply.answer) for reply in replies] == [("ANSWER", "yes")] * 2


@pytest.mark.xfail(
    strict=False,
    reason="DEFECT: policy substring matching treats plural entities as the singular policy condition",
)
def test_plural_entity_swap_does_not_reuse_singular_policy(tmp_path):
    frame = _archive_frame(tmp_path / "memory.jsonl")

    replies = [
        frame.answer(AgentQuestion("q", text))
        for text in ("Can I archive the drafts?", "Could I archive the drafts?")
    ]

    assert [(reply.kind, reply.answer) for reply in replies] == [("ESCALATE", None)] * 2


@pytest.mark.xfail(
    strict=False,
    reason="DEFECT: policy substring matching ignores negation in the agent question",
)
def test_negated_action_does_not_reuse_positive_action_policy(tmp_path):
    frame = _archive_frame(tmp_path / "memory.jsonl")

    replies = [
        frame.answer(AgentQuestion("q", text))
        for text in ("Can I not archive the draft?", "Could I not archive the draft?")
    ]

    assert [(reply.kind, reply.answer) for reply in replies] == [("ESCALATE", None)] * 2
