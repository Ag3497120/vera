from decimal import Decimal

import pytest

from verantyx.semantic_ir import Variable
from verantyx.semantic_reader import document_view, read_request


def _only_clause(text, source="source"):
    view = document_view({source: text})
    assert len(view.clauses) == 1
    assert not view.unread
    return view.clauses[0]


def _roles(clause):
    return {role.name: role for role in clause.roles}


def test_active_frame_roles_are_source_bound():
    text = "太郎は花子に本を渡した。"
    clause = _only_clause(text)

    roles = _roles(clause)
    assert clause.predicate == "渡す"
    assert {name: role.term for name, role in roles.items()} == {
        "agent": "太郎",
        "patient": "本",
        "recipient": "花子",
    }
    for role in roles.values():
        assert text[role.span.start:role.span.end] == role.span.text == role.term
        assert clause.span.start <= role.span.start < role.span.end <= clause.span.end
    assert clause.unsupported == ()


def test_passive_clause_keeps_the_roles_tied_to_their_phrases():
    text = "本は太郎によって花子に渡された。"
    clause = _only_clause(text)

    roles = _roles(clause)
    assert {name: role.term for name, role in roles.items()} == {
        "agent": "太郎",
        "patient": "本",
        "recipient": "花子",
    }
    assert all(text[r.span.start:r.span.end] == r.term for r in roles.values())


def test_negation_and_past_tense_are_preserved():
    clause = _only_clause("太郎は花子に本を渡さなかった。")

    assert clause.polarity == "-"
    assert clause.time == "past"
    assert _roles(clause)["patient"].term == "本"


def test_interrogative_document_sentence_is_not_asserted_as_a_clause():
    view = document_view({"source": "太郎は花子に本を渡したか？"})

    assert view.clauses == ()
    assert len(view.unread) == 1
    assert view.unread[0].span.text == "太郎は花子に本を渡したか？"


def test_multiple_sources_keep_their_own_provenance():
    view = document_view(
        {"first": "太郎は本を渡した。", "second": "花子は鍵を持つ。"},
        sovereigns={"first": "primary", "second": "secondary"},
        family="ledger",
    )

    assert [(c.span.source, c.sovereign, c.family) for c in view.clauses] == [
        ("first", "primary", "ledger"),
        ("second", "secondary", "ledger"),
    ]
    assert _roles(view.clauses[0])["agent"].term == "太郎"
    assert _roles(view.clauses[1])["agent"].term == "花子"
    assert all(r.span.source == c.span.source for c in view.clauses for r in c.roles)


def test_supersession_marker_is_retained_as_unsupported_scope():
    view = document_view({"source": "最新版では太郎は花子に本を渡した。"})

    assert view.clauses or view.unread
    assert any(
        "unsupported source quantifier/exception/time" in clause.unsupported
        for clause in view.clauses
    ) or any("unsupported" in item.reason for item in view.unread)


def test_copula_quantity_keeps_value_and_exact_source_span():
    text = "太郎の年齢は20歳です。"
    clause = _only_clause(text)

    value = _roles(clause)["value"]
    assert clause.rule == "copula"
    assert value.term.amount == Decimal("20")
    assert value.term.unit == "歳"
    assert text[value.span.start:value.span.end] == value.span.text == "20歳"


def test_direct_wh_request_projects_the_asked_recipient():
    request = read_request("太郎は誰に本を渡したか？")

    assert len(request.plans) == 1
    bind = next(node for node in request.plans[0].nodes if node.op == "Bind")
    output = request.plans[0].nodes[-1].outputs[0]
    roles = dict(bind.pattern.roles)
    assert output.label == "recipient"
    assert isinstance(output.term, Variable)
    assert roles["agent"] == "太郎"
    assert roles["patient"] == "本"
    assert roles["recipient"] == output.term


def test_unsupported_recency_question_is_typed_unread():
    request = read_request("最新版で太郎は本を渡しましたか？")

    assert request.plans == ()
    assert request.unread
    assert request.unread[0].span.text == request.text


@pytest.mark.xfail(
    strict=False,
    reason="DEFECT: passive によって questions bind 花子 as agent and ask for recipient",
)
def test_passive_niyotte_question_projects_the_agent():
    request = read_request("本は誰によって花子に渡されたか？")

    assert len(request.plans) == 1
    bind = next(node for node in request.plans[0].nodes if node.op == "Bind")
    output = request.plans[0].nodes[-1].outputs[0]
    roles = dict(bind.pattern.roles)
    assert output.label == "agent"
    assert isinstance(roles["agent"], Variable)
    assert roles["patient"] == "本"
    assert roles["recipient"] == "花子"
