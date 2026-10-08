import pytest

from verantyx.semantic_reader import document_view, read_request


def _view(sentence):
    return document_view({"tense-time": sentence})


def _time_scope_is_explicit(view):
    return bool(view.unread) or all(
        clause.unsupported for clause in view.clauses
    )


def test_nonpast_event_is_typed_as_nonpast():
    sentence = "ユンが箱を運ぶ。"
    view = _view(sentence)

    assert not view.unread
    assert len(view.clauses) == 1
    assert view.clauses[0].time == "nonpast"
    assert view.clauses[0].span.text == sentence


def test_past_event_is_typed_as_past():
    view = _view("ユンが箱を運んだ。")

    assert not view.unread
    assert len(view.clauses) == 1
    assert view.clauses[0].time == "past"


def test_compound_verb_tail_keeps_past_auxiliary():
    view = _view("ユンが箱を受け取った。")

    assert not view.unread
    assert len(view.clauses) == 1
    assert view.clauses[0].time == "past"


def test_event_past_negation_is_separate_from_tense():
    view = _view("ユンが箱を運ばなかった。")

    assert not view.unread
    assert len(view.clauses) == 1
    assert view.clauses[0].time == "past"
    assert view.clauses[0].polarity == "-"


@pytest.mark.parametrize("word", ["現在", "以前"])
def test_supported_relative_time_words_mark_copula_scope_unsupported(word):
    view = _view(f"ユンは{word}技師だ。")

    assert not view.unread
    assert len(view.clauses) == 1
    assert "unsupported source quantifier/exception/time" in view.clauses[0].unsupported


@pytest.mark.parametrize(
    "sentence",
    [
        "ユンは今年何歳ですか？",
        "ユンは2024年に何歳ですか？",
        "ユンは以前何歳でしたか？",
    ],
)
def test_time_dependent_age_questions_are_typed_unread(sentence):
    request = read_request(sentence)

    assert not request.plans
    assert request.unread
    assert request.unread[0].span.text == sentence


@pytest.mark.xfail(
    strict=False,
    reason="DEFECT: 今年 is not marked as unsupported temporal scope in copulas",
)
def test_this_year_copula_has_explicit_time_scope():
    view = _view("ユンは今年の代表だ。")

    assert _time_scope_is_explicit(view)


@pytest.mark.xfail(
    strict=False,
    reason="DEFECT: past copulas are emitted without tense or refusal",
)
@pytest.mark.parametrize(
    ("sentence", "polarity"),
    [
        ("ユンは技師だった。", "+"),
        ("ユンは技師ではなかった。", "-"),
    ],
)
def test_past_copula_is_typed_as_past_or_unread(sentence, polarity):
    view = _view(sentence)

    assert view.unread or (
        len(view.clauses) == 1
        and view.clauses[0].time == "past"
        and view.clauses[0].polarity == polarity
    )


@pytest.mark.xfail(
    strict=False,
    reason="DEFECT: a date-like year becomes an unmarked malformed quantity unit",
)
def test_date_like_year_is_not_folded_into_a_quantity_unit():
    view = _view("ユンは2024年技師だ。")

    assert _time_scope_is_explicit(view)
