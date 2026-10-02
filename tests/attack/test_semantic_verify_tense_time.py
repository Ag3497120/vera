from dataclasses import replace

import pytest

from verantyx.semantic_ir import Meter
from verantyx.semantic_reader import document_view, read_request
from verantyx.semantic_verify import Checker, Rejected


def _view(sentence):
    return document_view({"doc": sentence})


def _checker(view):
    return Checker(view, "document", Meter())


def _answers(fact, question):
    request = read_request(question)
    assert len(request.plans) == 1
    return _checker(_view(fact)).audit(request.plans[0])


def test_past_event_source_is_licensed_as_past():
    view = _view("太郎は東京に行った。")
    clause = view.clauses[0]

    assert clause.time == "past"
    _checker(view)._source(clause)


def test_nonpast_event_source_is_licensed_as_nonpast():
    view = _view("太郎は東京に行く。")
    clause = view.clauses[0]

    assert clause.time == "nonpast"
    _checker(view)._source(clause)


def test_past_source_cannot_be_relabelled_nonpast():
    view = _view("太郎は東京に行った。")
    clause = replace(view.clauses[0], time="nonpast")
    forged_view = replace(view, clauses=(clause,))

    with pytest.raises(Rejected):
        _checker(forged_view)._source(clause)


def test_nonpast_source_cannot_be_relabelled_past():
    view = _view("太郎は東京に行く。")
    clause = replace(view.clauses[0], time="past")
    forged_view = replace(view, clauses=(clause,))

    with pytest.raises(Rejected):
        _checker(forged_view)._source(clause)


def test_past_question_does_not_bind_to_nonpast_source():
    assert _answers("太郎は東京に行く。", "太郎は東京に行ったか") == set()


def test_nonpast_question_does_not_bind_to_past_source():
    assert _answers("太郎は東京に行った。", "太郎は東京に行くか") == set()


def test_negative_past_event_remains_negative_in_whether_answer():
    assert _answers("太郎は東京に行かなかった。", "太郎は東京に行ったか") == {
        (("可否", False),)
    }


def test_nonpast_progressive_is_licensed_as_nonpast():
    view = _view("太郎は東京に行っている。")
    clause = view.clauses[0]

    assert clause.time == "nonpast"
    _checker(view)._source(clause)


def test_past_progressive_is_licensed_as_past():
    view = _view("太郎は東京に行っていた。")
    clause = view.clauses[0]

    assert clause.time == "past"
    _checker(view)._source(clause)


def test_unparsed_yesterday_scope_is_rejected():
    view = _view("太郎は昨日東京に行った。")
    clause = view.clauses[0]

    assert clause.unsupported
    with pytest.raises(Rejected):
        _checker(view)._source(clause)


def test_order_specific_question_is_left_unread():
    view = _view("太郎は東京に行ってから大阪に行った。")
    request = read_request("太郎は東京に行ってから大阪に行ったか")

    assert len(view.clauses) == 2
    assert not request.plans
    assert request.unread


@pytest.mark.xfail(
    strict=False,
    reason="DEFECT: 今年 is erased while the event is licensed as unqualified nonpast",
)
def test_this_year_scope_must_be_represented_or_rejected():
    view = _view("太郎は今年東京に行く。")
    clause = view.clauses[0]

    # The event IR only has nonpast here, so the source qualifier must either
    # be represented separately or make independent licensing refuse it.
    assert clause.time == "nonpast"
    assert not any(role.name == "time" for role in clause.roles)
    with pytest.raises(Rejected):
        _checker(view)._source(clause)
