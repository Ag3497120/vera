from concurrent.futures import ThreadPoolExecutor

import pytest

from verantyx.remedy import remedy


def test_empty_result_returns_typed_unknown_fallback():
    assert remedy({}) == {
        "verdict": "",
        "needs_registration": None,
        "note": "no remedy recorded for this verdict",
    }


def test_answer_verdicts_are_terminal_and_idempotent():
    result = {"verdict": "ANSWER", "subject": "ignored"}
    expected = {"verdict": "ANSWER", "needs_registration": False}

    assert remedy(result) == expected
    assert remedy(remedy(result)) == expected


def test_known_refusal_propagates_only_addressing_fields_without_mutation():
    result = {
        "verdict": "NOT_ATTESTED",
        "subject": "contract",
        "terms": ["payment"],
        "missing": ["breach"],
        "language": "en",
        "deictic": "today",
        "unrelated": "not part of the remedy form",
    }
    original = result.copy()

    out = remedy(result)

    assert out == {
        "verdict": "NOT_ATTESTED",
        "needs_registration": True,
        "register": (
            "sentences connecting the subject to the asked condition, "
            "if the connection is in fact true"
        ),
        "how": "remember / propose_ai_facts then accept_ai_fact",
        "then": (
            "the same question returns ATTESTED with the new facet "
            "as the citation"
        ),
        "minimum": 1,
        "note": (
            "this verdict is a coverage gap, not a denial — the corpus "
            "never wrote the negative either, and closure forbids "
            "inventing it"
        ),
        "subject": "contract",
        "terms": ["payment"],
        "missing": ["breach"],
        "language": "en",
        "deictic": "today",
    }
    assert result == original


def test_falsey_optional_fields_are_not_copied():
    result = {
        "verdict": "NOT_ATTESTED",
        "subject": "",
        "terms": [],
        "missing": None,
        "language": False,
        "deictic": 0,
    }

    out = remedy(result)

    assert set(out) == {
        "verdict", "needs_registration", "register", "how", "then",
        "minimum", "note",
    }


@pytest.mark.xfail(
    strict=False,
    reason="DEFECT: unlisted verdict fallback drops supplied subject",
)
def test_unknown_verdict_keeps_a_typed_fallback():
    assert remedy({"verdict": "UNKNOWN_FUTURE_CASE", "subject": "topic"}) == {
        "verdict": "UNKNOWN_FUTURE_CASE",
        "needs_registration": None,
        "note": "no remedy recorded for this verdict",
        "subject": "topic",
    }


def test_dictionary_insertion_order_does_not_change_the_remedy():
    left = {"verdict": "UNKNOWN_TIME_DEPENDENT", "deictic": "today", "subject": "weather"}
    right = {"subject": "weather", "deictic": "today", "verdict": "UNKNOWN_TIME_DEPENDENT"}

    assert remedy(left) == remedy(right)


def test_registered_remedy_output_is_idempotent():
    result = {"verdict": "UNKNOWN_NO_CITATION", "subject": "topic"}

    first = remedy(result)

    assert remedy(first) == first


def test_megabyte_field_is_carried_without_truncation():
    long_term = "x" * (1024 * 1024)
    result = {"verdict": "NOT_ATTESTED", "terms": long_term}

    out = remedy(result)

    assert out["terms"] is long_term
    assert len(out["terms"]) == 1024 * 1024


def test_repeated_calls_return_equal_results_without_changing_input():
    result = {"verdict": "UNKNOWN_UNDERDETERMINED", "terms": ["a", "b"]}
    original = result.copy()

    first = remedy(result)
    second = remedy(result)

    assert first == second
    assert result == original


def test_two_concurrent_readers_keep_results_independent():
    def repeated(verdict, subject):
        expected = remedy({"verdict": verdict, "subject": subject})
        for _ in range(200):
            assert remedy({"verdict": verdict, "subject": subject}) == expected
        return expected

    with ThreadPoolExecutor(max_workers=2) as readers:
        left = readers.submit(repeated, "UNKNOWN_TIME_DEPENDENT", "weather")
        right = readers.submit(repeated, "UNKNOWN_NO_SUBJECT", "greeting")

        left_result = left.result()
        right_result = right.result()

    assert left_result["verdict"] == "UNKNOWN_TIME_DEPENDENT"
    assert left_result["subject"] == "weather"
    assert right_result["verdict"] == "UNKNOWN_NO_SUBJECT"
    assert right_result["subject"] == "greeting"
