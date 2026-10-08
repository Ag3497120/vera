"""Independent differential checks for the agreement-band judge."""
from __future__ import annotations

import random
from collections import Counter
from types import SimpleNamespace

import pytest

from verantyx.graded import GradedJudge, band_annotation


WHOLE = (("whole", {"rungs": (("whole", 0),), "grammar": "raw", "depth": 1}),)
MENTIONS = (("mentions", {"rungs": (("whole", 0),), "grammar": "raw"}),)


def _store(crosses, labels=()):
    return SimpleNamespace(crosses=crosses, source_labels=set(labels))


def _items(crosses, labels, depth):
    """Naive contract model: a core name followed by its sorted facets."""
    labels = set(labels or ())
    result = {}
    for core, facets in crosses.items():
        if core in labels:
            continue
        terms = [core] + sorted(term for term in (facets or ()) if term not in labels)
        result[core] = terms[:depth] if depth else terms
    return result


def _naive_exact_reading(terms, crosses, labels=(), depth=None):
    """Score exact whole-term matches, with ties abstaining."""
    items = _items(crosses, labels, depth)
    scores = {
        core: sum(term in item_terms for term in terms)
        for core, item_terms in items.items()
    }
    high = max(scores.values(), default=0)
    leaders = sorted(core for core, score in scores.items() if score == high and score > 0)
    return leaders[0] if len(leaders) == 1 else None


def _naive_report(terms, crosses, labels, settings):
    """Outer report for exact whole-grain ladders, independently tallied."""
    labels = set(labels or ())
    held = {core for core in crosses if core not in labels}
    for facets in crosses.values():
        held.update(term for term in (facets or ()) if term not in labels)
    readings = {
        name: _naive_exact_reading(terms, crosses, labels, depth)
        for name, depth in settings
    }
    covered = [term for term in terms if term in held]
    missing = [term for term in terms if term not in held]
    spoke = list(readings.values())
    spoke = [item for item in spoke if item]
    if not spoke:
        return {
            "verdict": "UNKNOWN_NOT_PRESENT", "item": None, "terms": terms,
            "agreeing": 0, "of": len(settings), "covered": covered,
            "missing": missing,
            "coverage": round(len(covered) / max(len(terms), 1), 3),
            "readings": readings,
        }
    tally = Counter(spoke)
    top = max(tally.values())
    leaders = sorted(item for item, count in tally.items() if count == top)
    coverage = round(len(covered) / max(len(terms), 1), 3)
    if len(leaders) > 1:
        return {
            "verdict": "AMBIGUOUS", "item": None, "terms": terms,
            "agreeing": top, "of": len(settings), "leaders": leaders[:4],
            "covered": covered, "missing": missing, "coverage": coverage,
            "readings": readings,
        }
    item = leaders[0]
    strict = readings.get("whole")
    return {
        "verdict": "ANSWER" if strict == item else "ANSWER_BY_COARSENING",
        "item": item, "terms": terms, "agreeing": top, "of": len(settings),
        "covered": covered, "missing": missing, "coverage": coverage,
        "spoke": len(spoke), "concord": round(top / len(spoke), 3),
        "readings": readings,
    }


def _terms(query):
    return query.split()


def _compare_report(actual, expected):
    for key, value in expected.items():
        assert actual[key] == value, key


def test_unique_exact_core_matches_independent_reference():
    crosses = {"alpha": ["facet-a"], "beta": ["facet-b"]}
    judge = GradedJudge(WHOLE, read=_terms).build(_store(crosses))
    expected = _naive_report(["alpha"], crosses, (), [("whole", 1)])
    _compare_report(judge.ask("alpha"), expected)
    assert expected["verdict"] == "ANSWER"
    assert expected["item"] == "alpha"


def test_two_exact_core_matches_tie_and_abstain():
    crosses = {"alpha": [], "beta": []}
    judge = GradedJudge(WHOLE, read=_terms).build(_store(crosses))
    actual = judge.ask("alpha beta")
    expected = _naive_report(["alpha", "beta"], crosses, (), [("whole", 1)])
    _compare_report(actual, expected)
    assert actual["verdict"] == "UNKNOWN_NOT_PRESENT"
    assert actual["readings"] == {"whole": None}


def test_mentions_setting_can_add_a_typed_coarse_reading():
    crosses = {"alpha": ["needle"], "beta": ["other"]}
    judge = GradedJudge(MENTIONS, read=_terms).build(_store(crosses))
    actual = judge.ask("needle")
    expected = _naive_report(["needle"], crosses, (), [("mentions", None)])
    _compare_report(actual, expected)
    assert actual["verdict"] == "ANSWER_BY_COARSENING"
    assert actual["item"] == "alpha"


def test_independent_settings_disagree_and_outer_judge_abstains():
    crosses = {"alpha": [], "beta": ["alpha", "x", "y"]}
    settings = (
        ("whole", {"rungs": (("whole", 0),), "grammar": "raw", "depth": 1}),
        ("mentions", {"rungs": (("whole", 0),), "grammar": "raw"}),
    )
    judge = GradedJudge(settings, read=_terms).build(_store(crosses))
    actual = judge.ask("alpha x y")
    expected = _naive_report(["alpha", "x", "y"], crosses, (), [("whole", 1), ("mentions", None)])
    _compare_report(actual, expected)
    assert actual["verdict"] == "AMBIGUOUS"
    assert actual["leaders"] == ["alpha", "beta"]


def test_source_labels_are_excluded_from_candidates_and_coverage():
    crosses = {"alpha": ["label", "needle"], "label": ["alpha"]}
    judge = GradedJudge(WHOLE, read=_terms).build(_store(crosses, labels={"label"}))
    actual = judge.ask("label")
    expected = _naive_report(["label"], crosses, {"label"}, [("whole", 1)])
    _compare_report(actual, expected)
    assert actual["verdict"] == "UNKNOWN_NOT_PRESENT"
    assert actual["covered"] == []


def test_readable_query_without_terms_is_no_subject():
    judge = GradedJudge(WHOLE, read=lambda _query: []).build(_store({"alpha": []}))
    actual = judge.ask("こんにちは")
    assert actual["verdict"] == "UNKNOWN_NO_SUBJECT"
    assert actual["terms"] == []
    assert band_annotation(judge, "こんにちは") is None


def test_empty_query_is_unparsed_and_has_no_band():
    judge = GradedJudge(WHOLE, read=lambda _query: []).build(_store({"alpha": []}))
    assert judge.ask("  ")["verdict"] == "UNKNOWN_UNPARSED"
    assert band_annotation(judge, "  ") is None


def test_time_dependent_query_is_routed_before_any_reading():
    judge = GradedJudge(WHOLE, read=_terms).build(_store({"weather": []}))
    actual = judge.ask("今日 weather")
    assert actual["verdict"] == "UNKNOWN_TIME_DEPENDENT"
    assert actual["deictic"] == "今日"
    assert "readings" not in actual
    assert band_annotation(judge, "今日 weather") is None


def test_zero_agreement_is_an_annotation_not_absence():
    judge = GradedJudge(WHOLE, read=_terms).build(_store({"alpha": []}))
    assert judge.ask("missing")["verdict"] == "UNKNOWN_NOT_PRESENT"
    assert band_annotation(judge, "missing") == {"agree": 0, "of": 1}


def test_generated_exact_cases_match_naive_reference():
    rng = random.Random(20261002)
    for _case in range(80):
        core_count = rng.randint(1, 7)
        crosses = {
            "c%02d" % index: ["f%02d" % rng.randrange(12) for _ in range(rng.randrange(4))]
            for index in range(core_count)
        }
        pool = list(crosses)
        pool.extend(term for facets in crosses.values() for term in facets)
        pool.extend("absent%02d" % index for index in range(4))
        terms = rng.sample(sorted(set(pool)), rng.randint(1, min(5, len(set(pool)))))
        query = " ".join(terms)
        judge = GradedJudge(WHOLE, read=_terms).build(_store(crosses))
        actual = judge.ask(query)
        expected = _naive_report(terms, crosses, (), [("whole", 1)])
        _compare_report(actual, expected)


def test_generated_facet_cases_match_naive_reference():
    rng = random.Random(1602)
    for _case in range(60):
        core_count = rng.randint(1, 6)
        crosses = {
            "core%02d" % index: sorted({"facet%02d" % rng.randrange(10) for _ in range(rng.randrange(5))})
            for index in range(core_count)
        }
        pool = list(crosses)
        pool.extend(term for facets in crosses.values() for term in facets)
        pool.extend("absent%02d" % index for index in range(3))
        terms = rng.sample(sorted(set(pool)), rng.randint(1, min(5, len(set(pool)))))
        query = " ".join(terms)
        judge = GradedJudge(MENTIONS, read=_terms).build(_store(crosses))
        actual = judge.ask(query)
        expected = _naive_report(terms, crosses, (), [("mentions", None)])
        _compare_report(actual, expected)


@pytest.mark.xfail(
    strict=False,
    reason="DEFECT: substring detection treats the stable proper name 今昔物語 as time-dependent",
)
def test_stable_name_containing_time_character_is_not_refused():
    crosses = {"今昔物語": []}
    judge = GradedJudge(WHOLE, read=lambda _query: ["今昔物語"]).build(_store(crosses))
    actual = judge.ask("今昔物語とは")
    assert actual["verdict"] == "ANSWER"
    assert actual["item"] == "今昔物語"
