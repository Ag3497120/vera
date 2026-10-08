from concurrent.futures import ThreadPoolExecutor
from itertools import islice, product

import pytest

import verantyx.polarity as polarity


def test_empty_input_is_a_neutral_reading():
    reading = polarity.observe_negation("", tokens=[])

    assert reading.verdict == polarity.POLARITY_POSITIVE
    assert reading.observed == ()
    assert reading.count == 0
    assert reading.category is None


def test_written_copula_negation_is_typed_with_its_span():
    reading = polarity.observe_negation("学生ではない。", tokens=[])

    assert reading.verdict == polarity.POLARITY_NEGATIVE
    assert reading.category == "copula"
    assert reading.count == 1
    observation = reading.observed[0]
    assert isinstance(observation, polarity.ObservedNegation)
    assert (observation.kind, observation.surface, observation.lemma) == (
        "copula", "ではない", "である")
    assert observation.span == (2, 6)


def test_unfoldable_modality_abstains_without_claiming_negation():
    reading = polarity.observe_negation("彼が来ないとは言えない。", tokens=[])

    assert reading.verdict == polarity.POLARITY_UNDECIDED
    assert reading.category == polarity.POLARITY_UNDECIDED
    assert reading.observed == ()
    assert reading.count == 0


def test_inferred_absence_and_untyped_values_are_refused_as_storage_keys():
    inferred = polarity.inferred_from_absence("流れる")

    with pytest.raises(TypeError, match="not testimony"):
        polarity.polarity_key(inferred)
    with pytest.raises(TypeError, match="only ObservedNegation"):
        polarity.polarity_key(object())


def test_adjacent_written_negations_fold_by_parity():
    reading = polarity.observe_negation("ではないではない", tokens=[])

    assert reading.verdict == polarity.POLARITY_POSITIVE
    assert reading.category == "double"
    assert reading.count == 2
    assert [item.span for item in reading.observed] == [(0, 4), (4, 8)]


def test_repeated_reading_and_predicate_fold_are_deterministic():
    text = "できない。"
    first_reading = polarity.observe_negation(text, tokens=[])
    second_reading = polarity.observe_negation(text, tokens=[])
    predicates = ["できる", "ある"]

    first_fold = polarity.fold_polarity(predicates, text, tokens=[])
    second_fold = polarity.fold_polarity(predicates, text, tokens=[])

    assert first_reading == second_reading
    assert first_fold == second_fold == ["¬できる", "ある"]
    assert predicates == ["できる", "ある"]


@pytest.mark.xfail(
    strict=False,
    reason="DEFECT: refolding an already marked predicate appends a duplicate ¬ key",
)
def test_folding_an_already_folded_predicate_is_idempotent():
    once = polarity.fold_polarity(["できる"], "できない。", tokens=[])
    twice = polarity.fold_polarity(once, "できない。", tokens=[])

    assert twice == once


def test_large_irrelevant_input_returns_without_fabricating_observations():
    reading = polarity.observe_negation("x" * 100_000, tokens=[])

    assert reading.verdict == polarity.POLARITY_POSITIVE
    assert reading.observed == ()
    assert reading.count == 0


def test_many_adjacent_negation_marks_are_counted_and_folded():
    reading = polarity.observe_negation("ではない" * 512, tokens=[])

    assert reading.count == 512
    assert reading.verdict == polarity.POLARITY_POSITIVE
    assert reading.category == "double"


def test_clause_order_does_not_change_the_observed_multiset():
    left_to_right = polarity.observe_negation(
        "学生ではない。危険でない。", tokens=[])
    right_to_left = polarity.observe_negation(
        "危険でない。学生ではない。", tokens=[])

    project = lambda reading: sorted(
        (item.kind, item.surface, item.lemma, item.context)
        for item in reading.observed)
    assert project(left_to_right) == project(right_to_left)
    assert left_to_right.count == right_to_left.count == 2
    assert left_to_right.verdict == right_to_left.verdict


def test_two_concurrent_readers_do_not_share_sentence_state():
    inputs = ["学生ではない。", "彼が来ないとは言えない。"] * 16
    expected = [polarity.observe_negation(text, tokens=[]) for text in inputs]

    with ThreadPoolExecutor(max_workers=2) as pool:
        actual = list(pool.map(
            lambda text: polarity.observe_negation(text, tokens=[]), inputs))

    assert actual == expected


@pytest.mark.xfail(
    strict=False,
    reason="DEFECT: rejected unique lemmas accumulate in an unbounded global cache",
)
def test_unrecognized_lemma_cache_stays_bounded_under_unique_inputs():
    before = set(polarity._LEMMA_CACHE)
    stems = ("".join(chars) for chars in islice(product("かきくけこ", repeat=4), 160))

    for stem in stems:
        polarity.observe_negation(stem + "ない。", tokens=[])

    added = set(polarity._LEMMA_CACHE) - before
    assert len(added) <= 32
