import pytest

from verantyx.polarity import (
    POLARITY_NEGATIVE,
    POLARITY_POSITIVE,
    POLARITY_UNDECIDED,
    InferredNegation,
    ObservedNegation,
    detect,
    detect_ja,
    fold_polarity,
    inferred_from_absence,
    observe_negation,
    polarity_key,
)


def test_observed_ending_is_bound_to_its_source_span():
    source = "水が流れない。"

    reading = observe_negation(source)

    assert reading.verdict == POLARITY_NEGATIVE
    assert reading.count == 1
    observation = reading.observed[0]
    assert isinstance(observation, ObservedNegation)
    assert observation.surface == "ない"
    assert observation.lemma == "流れる"
    assert source[slice(*observation.span)] == observation.surface
    assert observation.context is None


def test_lexicalized_nai_does_not_fabricate_negation():
    reading = observe_negation("この映画はつまらない。")

    assert reading.verdict == POLARITY_POSITIVE
    assert reading.observed == ()
    assert reading.count == 0


def test_unrecognized_negative_looking_stem_does_not_create_a_lemma():
    reading = observe_negation("大人げない態度だ。")

    assert reading.verdict == POLARITY_POSITIVE
    assert reading.observed == ()


def test_embedded_negation_is_retained_but_does_not_set_sentence_verdict():
    source = "知らない人が来た。"

    reading = observe_negation(source)

    assert reading.verdict == POLARITY_POSITIVE
    assert len(reading.observed) == 1
    observation = reading.observed[0]
    assert observation.lemma == "知る"
    assert source[slice(*observation.span)] == observation.surface == "ない"


def test_unfoldable_modality_abstains_without_testimony():
    reading = observe_negation("彼が来ないとは言えない。")

    assert reading.verdict == POLARITY_UNDECIDED
    assert reading.observed == ()
    assert reading.count == 0


def test_double_negation_keeps_both_written_spans_and_folds_even():
    source = "彼は行かなくない。"

    reading = observe_negation(source)

    assert reading.verdict == POLARITY_POSITIVE
    assert reading.category == "double"
    assert len(reading.observed) == 2
    assert [source[slice(*item.span)] for item in reading.observed] == [
        "なく", "ない",
    ]
    assert {item.lemma for item in reading.observed} == {"行く"}


def test_noun_plus_nai_keeps_the_noun_as_context():
    source = "問題はない。"
    observation = observe_negation(source).observed[0]

    assert observation.lemma == "ある"
    assert observation.context == "問題"
    assert source[slice(*observation.span)] == "ない"
    assert polarity_key(observation) == "¬ある"


def test_copula_negation_span_covers_the_written_copula():
    source = "彼は学生ではない。"

    reading = observe_negation(source)

    assert reading.verdict == POLARITY_NEGATIVE
    assert len(reading.observed) == 1
    observation = reading.observed[0]
    assert observation.kind == "copula"
    assert observation.lemma == "である"
    assert source[slice(*observation.span)] == observation.surface == "ではない"


def test_explicit_japanese_negation_flips_the_attested_pole():
    assert detect_ja("この道は安全ではありません") == [
        ("安全", "not_安全", "-"),
    ]


def test_explicit_english_negation_is_retained_on_its_aspect():
    assert detect("not closed") == [("open", "not_closed", "+")]


def test_absence_inference_is_not_storable_testimony():
    inferred = inferred_from_absence("流れる")

    assert isinstance(inferred, InferredNegation)
    with pytest.raises(TypeError):
        polarity_key(inferred)


def test_fold_marks_only_a_predicate_with_matching_observed_lemma():
    folded = fold_polarity(["流れる", "知る"], "水が流れない。")

    assert folded == ["¬流れる", "知る"]


@pytest.mark.xfail(
    strict=False,
    reason="DEFECT: polarity_key lets a caller retarget observed negation to an unrelated lemma",
)
def test_polarity_key_rejects_an_unobserved_lemma_override():
    observation = observe_negation("水が流れない。").observed[0]

    with pytest.raises((TypeError, ValueError)):
        polarity_key(observation, "死ぬ")


@pytest.mark.xfail(
    strict=False,
    reason="DEFECT: a caller-constructed observation is accepted as source-backed testimony",
)
def test_polarity_key_rejects_a_constructed_observation_without_source():
    constructed = ObservedNegation(
        kind="ending", surface="ない", lemma="死ぬ", span=(0, 2))

    with pytest.raises((TypeError, ValueError)):
        polarity_key(constructed)
