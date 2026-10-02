"""Differential checks for the typed, raw Japanese negation reader."""

import pytest

from verantyx import polarity


def _raw_reader(monkeypatch):
    """Use the documented no-tagger path with a fresh lemma cache."""
    monkeypatch.setattr(polarity, "_try_fugashi_tokens", lambda _text: None)
    monkeypatch.setattr(polarity, "_LEMMA_CACHE", {})


def _naive_reference(predicate):
    """Tiny independent reference for isolated, sentence-final forms.

    This deliberately covers only four unambiguous dictionary forms. It does
    not call the implementation's scanner, stemmer, or lemma helpers.
    """
    endings = {
        "しない": "する",
        "いない": "いる",
        "できない": "できる",
        "来ない": "来る",
    }
    lemma = endings.get(predicate)
    if lemma is None:
        return ("positive", (), 0, None)
    return ("negative", (lemma,), 1, "ending")


def _signature(reading):
    return (
        reading.verdict,
        tuple(item.lemma for item in reading.observed),
        reading.count,
        reading.category,
    )


@pytest.mark.parametrize(
    ("positive", "negative"),
    [
        ("する", "しない"),
        ("いる", "いない"),
        ("できる", "できない"),
        ("来る", "来ない"),
    ],
)
def test_generated_simple_predicates_match_naive_reference(
    monkeypatch, positive, negative
):
    _raw_reader(monkeypatch)
    for predicate in (positive, negative):
        sentence = f"{predicate}。"
        actual = polarity.observe_negation(sentence, tokens=())
        assert _signature(actual) == _naive_reference(predicate)


def test_written_copula_negation_is_observed_as_dictionary_form(monkeypatch):
    _raw_reader(monkeypatch)
    reading = polarity.observe_negation("彼は学生ではない。", tokens=())

    assert reading.verdict == polarity.POLARITY_NEGATIVE
    assert reading.count == 1
    assert reading.category == "copula"
    assert [(o.kind, o.lemma, o.surface) for o in reading.observed] == [
        ("copula", "である", "ではない")
    ]


def test_lexicalized_nai_adjective_is_not_counted_as_written_negation(monkeypatch):
    _raw_reader(monkeypatch)
    reading = polarity.observe_negation("この映画はつまらない。", tokens=())

    assert reading.verdict == polarity.POLARITY_POSITIVE
    assert reading.observed == ()


def test_unfoldable_modality_abstains(monkeypatch):
    _raw_reader(monkeypatch)
    reading = polarity.observe_negation("彼は来ないとは言えない。", tokens=())

    assert reading.verdict == polarity.POLARITY_UNDECIDED
    assert reading.count == 0
    assert reading.observed == ()


def test_double_negation_folds_by_even_parity(monkeypatch):
    _raw_reader(monkeypatch)
    reading = polarity.observe_negation("しなくない。", tokens=())

    assert reading.verdict == polarity.POLARITY_POSITIVE
    assert reading.count == 2
    assert reading.category == "double"
    assert [o.lemma for o in reading.observed] == ["する", "する"]


def test_embedded_negation_is_observed_but_does_not_set_sentence_verdict(monkeypatch):
    _raw_reader(monkeypatch)
    reading = polarity.observe_negation("しない人だ。", tokens=())

    assert reading.verdict == polarity.POLARITY_POSITIVE
    assert reading.count == 1
    assert reading.observed[0].lemma == "する"


def test_noun_plus_nai_uses_aru_and_keeps_the_noun_context(monkeypatch):
    _raw_reader(monkeypatch)
    reading = polarity.observe_negation("問題ない。", tokens=())

    assert reading.verdict == polarity.POLARITY_NEGATIVE
    assert [(o.lemma, o.context) for o in reading.observed] == [("ある", "問題")]


def test_noun_plus_nai_inside_a_larger_phrase_is_not_sentence_evidence(monkeypatch):
    _raw_reader(monkeypatch)
    reading = polarity.observe_negation("問題ない人だ。", tokens=())

    assert reading.verdict == polarity.POLARITY_POSITIVE
    assert reading.observed == ()


def test_sentence_final_negation_allows_trailing_desu_clause(monkeypatch):
    _raw_reader(monkeypatch)
    reading = polarity.observe_negation("しないでしょう。", tokens=())

    assert reading.verdict == polarity.POLARITY_NEGATIVE
    assert reading.count == 1


def test_unknown_lemma_is_not_inferred_as_observed_negation(monkeypatch):
    _raw_reader(monkeypatch)
    reading = polarity.observe_negation("水が流れない。", tokens=())

    assert reading.verdict == polarity.POLARITY_POSITIVE
    assert reading.observed == ()


def test_prefix_negation_without_an_attesting_lattice_is_not_observed(monkeypatch):
    _raw_reader(monkeypatch)
    reading = polarity.observe_negation("不可能である。", tokens=())

    assert reading.verdict == polarity.POLARITY_POSITIVE
    assert reading.observed == ()


def test_inferred_negation_cannot_be_stored_as_written_testimony(monkeypatch):
    _raw_reader(monkeypatch)
    inferred = polarity.inferred_from_absence("流れる")
    observed = polarity.observe_negation("しない。", tokens=()).observed[0]

    assert isinstance(inferred, polarity.InferredNegation)
    assert isinstance(observed, polarity.ObservedNegation)
    assert polarity.polarity_key(observed) == "¬する"
    with pytest.raises(TypeError):
        polarity.polarity_key(inferred)


@pytest.mark.xfail(
    strict=False,
    reason="DEFECT: raw fallback crosses the subject particle and drops しない",
)
def test_subject_particle_does_not_hide_an_attested_negated_verb(monkeypatch):
    _raw_reader(monkeypatch)
    readings = [
        polarity.observe_negation("彼はしない。", tokens=()),
        polarity.observe_negation("彼はしない。", tokens=()),
    ]

    assert all(
        reading.verdict == polarity.POLARITY_NEGATIVE
        and [o.lemma for o in reading.observed] == ["する"]
        for reading in readings
    )
