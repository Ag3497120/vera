import pytest

from verantyx.remedy import remedy


def test_not_present_offers_registration_without_answering():
    result = remedy({"verdict": "UNKNOWN_NOT_PRESENT"})

    assert result["verdict"] == "UNKNOWN_NOT_PRESENT"
    assert result["needs_registration"] is True
    assert result["minimum"] == 3
    assert "sentences about the subject" in result["register"]
    assert "ANSWER" not in result


def test_context_fields_keep_their_source_roles_and_values():
    source = {
        "verdict": "UNKNOWN_NOT_PRESENT",
        "subject": "entity-A",
        "terms": ["term-B"],
        "missing": ["missing-C"],
        "language": "language-D",
        "deictic": "deictic-E",
    }

    result = remedy(source)

    for key in ("subject", "terms", "missing", "language", "deictic"):
        assert result[key] == source[key]


def test_unrelated_answer_and_record_metadata_are_not_emitted():
    result = remedy({
        "verdict": "UNKNOWN_NOT_PRESENT",
        "subject": "topic-X",
        "answer": "unsupported-answer",
        "citation": "stale-citation-v1",
        "source_record": "superseded-record-v0",
        "evidence": "partial-span-without-support",
    })

    assert result["subject"] == "topic-X"
    assert not {"answer", "citation", "source_record", "evidence"} & result.keys()


def test_negated_and_partial_context_is_copied_without_reinterpretation():
    source = {
        "verdict": "NOT_ATTESTED",
        "subject": "partial subject span: A",
        "terms": ["not verified: relation B"],
        "missing": ["not held: condition C"],
    }

    result = remedy(source)

    assert result["subject"] == source["subject"]
    assert result["terms"] == source["terms"]
    assert result["missing"] == source["missing"]
    assert result["needs_registration"] is True
    assert result["minimum"] == 1
    assert "coverage gap" in result["note"]
    assert "negative either" in result["note"]
    assert "answer" not in result


@pytest.mark.parametrize(
    "verdict",
    ["ANSWER", "ANSWER:超伝導", "SEEDED", "AGREED", "LEAD", "ATTESTED", "COMPARISON"],
)
def test_answer_like_and_terminal_verdicts_are_only_passed_through(verdict):
    result = remedy({"verdict": verdict, "answer": "untrusted-payload"})

    assert result == {"verdict": verdict, "needs_registration": False}


@pytest.mark.parametrize("verdict", ["UNKNOWN_TIME_DEPENDENT", "UNKNOWN_NO_SUBJECT"])
def test_routing_refusals_are_not_marked_as_registration_gaps(verdict):
    result = remedy({"verdict": verdict})

    assert result["verdict"] == verdict
    assert result["needs_registration"] is False
    assert result["register"].startswith("nothing")
    assert "minimum" not in result
    assert "how" not in result


def test_unrecognized_refusal_does_not_adopt_untrusted_answer_or_record():
    result = remedy({
        "verdict": "UNKNOWN_FROM_ATTACKER",
        "subject": "entity-Q",
        "answer": "fabricated-answer",
        "source_record": "obsolete-v7",
    })

    assert result == {
        "verdict": "UNKNOWN_FROM_ATTACKER",
        "needs_registration": None,
        "note": "no remedy recorded for this verdict",
    }


def test_empty_context_values_are_not_added_as_claims():
    result = remedy({
        "verdict": "UNKNOWN_NOT_PRESENT",
        "subject": "",
        "terms": [],
        "missing": None,
        "language": "",
        "deictic": None,
    })

    assert not {"subject", "terms", "missing", "language", "deictic"} & result.keys()


def test_non_gap_metadata_does_not_turn_a_refusal_into_an_answer():
    result = remedy({
        "verdict": "UNKNOWN_TIME_DEPENDENT",
        "subject": "weather-A",
        "answer": "sunny",
        "citation": "stale-weather-record",
    })

    assert result["needs_registration"] is False
    assert result["subject"] == "weather-A"
    assert "answer" not in result
    assert "citation" not in result
