from decimal import Decimal

import pytest

from verantyx.semantic_reader import document_view, read_request
from verantyx.semantic_ir import Quantity


def _one_clause(text):
    view = document_view({"source": text})
    assert len(view.clauses) == 1
    assert not view.unread
    return view.clauses[0]


def _roles(clause):
    return {role.name: role.term for role in clause.roles}


def _event_question_pattern(text):
    request = read_request(text)
    assert len(request.plans) == 1
    assert not request.unread
    patterns = [node.pattern for node in request.plans[0].nodes
                if node.op == "Bind" and node.pattern is not None]
    assert len(patterns) == 1
    return patterns[0]


def test_subject_marking_word_order_and_politeness_keep_the_same_frame():
    variants = (
        "さくらが箱を運んだ。",
        "さくらは箱を運びました。",
        "箱をさくらが運んだ。",
    )
    clauses = [_one_clause(text) for text in variants]
    for clause in clauses:
        assert clause.predicate == "運ぶ"
        assert clause.polarity == "+"
        assert clause.time == "past"
        assert clause.unsupported == ()
        assert _roles(clause) == {"agent": "さくら", "patient": "箱"}


def test_recipient_order_and_politeness_keep_the_same_roles():
    variants = (
        "ゆきが鍵を太郎に渡した。",
        "鍵を太郎にゆきが渡しました。",
    )
    clauses = [_one_clause(text) for text in variants]
    assert all(clause.predicate == "渡す" for clause in clauses)
    assert all(clause.time == "past" for clause in clauses)
    assert all(_roles(clause) == {
        "agent": "ゆき", "patient": "鍵", "recipient": "太郎"
    } for clause in clauses)


def test_plain_and_polite_copulas_preserve_identity():
    clauses = [_one_clause(text) for text in (
        "東京は都市です。",
        "東京は都市だ。",
    )]
    assert all(clause.rule == "copula" for clause in clauses)
    assert all(clause.predicate == "identity" for clause in clauses)
    assert all(_roles(clause) == {"entity": "東京", "value": "都市"}
               for clause in clauses)


def test_numeric_spacing_preserves_typed_quantity():
    clauses = [_one_clause(text) for text in (
        "箱の数は3個です。",
        "箱の数は3 個です。",
    )]
    expected = Quantity(Decimal("3"), "個")
    assert all(_roles(clause)["value"] == expected for clause in clauses)
    assert all(_roles(clause)["attribute"] == "数" for clause in clauses)


def test_entity_swap_changes_only_the_agent_term():
    first = _one_clause("ゆきが箱を運んだ。")
    second = _one_clause("みさきが箱を運んだ。")
    assert first.predicate == second.predicate == "運ぶ"
    assert _roles(first)["patient"] == _roles(second)["patient"] == "箱"
    assert _roles(first)["agent"] == "ゆき"
    assert _roles(second)["agent"] == "みさき"


def test_predicate_change_changes_the_relation():
    carried = _one_clause("さくらが箱を運んだ。")
    made = _one_clause("さくらが箱を作った。")
    assert _roles(carried) == _roles(made)
    assert carried.predicate == "運ぶ"
    assert made.predicate == "作る"


def test_negation_changes_polarity_without_changing_roles():
    positive = _one_clause("さくらが箱を運んだ。")
    negative = _one_clause("さくらが箱を運ばなかった。")
    assert positive.predicate == negative.predicate == "運ぶ"
    assert _roles(positive) == _roles(negative)
    assert positive.polarity == "+"
    assert negative.polarity == "-"


def test_changed_quantity_changes_typed_value():
    three = _one_clause("箱の数は3個です。")
    four = _one_clause("箱の数は4個です。")
    assert _roles(three)["value"] == Quantity(Decimal("3"), "個")
    assert _roles(four)["value"] == Quantity(Decimal("4"), "個")
    assert _roles(three)["value"] != _roles(four)["value"]


def test_interrogative_document_sentence_is_unread_not_an_assertion():
    view = document_view({"source": "誰が箱を運びましたか？"})
    assert view.clauses == ()
    assert len(view.unread) == 1
    assert "interrogative" in view.unread[0].reason


def test_direct_who_question_binds_the_missing_agent_role():
    pattern = _event_question_pattern("誰が箱を運びましたか？")
    roles = dict(pattern.roles)
    assert pattern.predicate == "運ぶ"
    assert roles["patient"] == "箱"
    assert getattr(roles["agent"], "sort", None) == "entity"


@pytest.mark.xfail(
    strict=False,
    reason="DEFECT: cleft who-question is unread while its direct paraphrase is typed",
)
def test_cleft_who_question_keeps_the_direct_question_role():
    direct = _event_question_pattern("誰が箱を運びましたか？")
    cleft = _event_question_pattern("箱を運んだのは誰ですか？")
    direct_roles = dict(direct.roles)
    cleft_roles = dict(cleft.roles)
    assert direct.predicate == cleft.predicate == "運ぶ"
    assert direct_roles["patient"] == cleft_roles["patient"] == "箱"
    assert getattr(direct_roles["agent"], "sort", None) == "entity"
    assert getattr(cleft_roles["agent"], "sort", None) == "entity"
