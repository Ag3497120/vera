"""Differential checks for typed refusal repairs.

The reference below is a deliberately small transcription of the public
contract in remedy.py. It does not import the implementation's remedy table
or call the implementation to derive expected values.
"""
from itertools import product

import pytest

from verantyx.remedy import remedy


_NO_GAP = {
    "UNKNOWN_SUBJECT_NOT_A_WORD",
    "UNKNOWN_TIME_DEPENDENT",
    "UNKNOWN_NO_SUBJECT",
    "UNKNOWN_UNPARSED",
    "UNKNOWN_UNDERDETERMINED",
    "UNKNOWN_CONDITIONS_CONFLICT",
}
_TERMINAL = {"SEEDED", "AGREED", "LEAD", "ATTESTED", "COMPARISON"}

# Kept separate from verantyx.remedy.REMEDIES so changes there are detected.
_REFERENCE = {
    "UNKNOWN_NO_EVIDENCE": {
        "register": "sentences about the subject — the census found nothing to count",
        "how": "remember / propose_ai_facts then accept_ai_fact",
        "then": "rebuild the judge — measured 1.4s on 86,967 cores",
        "minimum": 3,
        "note": "if the question names no content word at all, the honest route is a generator rather than a registration; see UNKNOWN_NO_SUBJECT",
    },
    "UNKNOWN_NOT_PRESENT": {
        "register": "sentences about the subject, in the register the corpus is judged in",
        "how": "remember / propose_ai_facts then accept_ai_fact",
        "then": "rebuild the judge — measured 1.4s on 54,244 cores",
        "minimum": 3,
    },
    "UNKNOWN_SUBJECT_TOO_THIN": {
        "register": "more facts about a subject the store already holds",
        "how": "remember",
        "then": "the subject becomes judgeable at MIN_FACETS",
        "minimum": 3,
        "note": "one fact left it NOT_HELD; four made it answerable",
    },
    "UNKNOWN_NO_CITATION": {
        "register": "a document ABOUT the topic that cites articles by name",
        "how": "ingest the document; links.harvest takes the topic from the filename",
        "then": "cited articles are listed, never chosen",
    },
    "UNKNOWN_LANGUAGE_NOT_HELD": {
        "register": "documents in that language, as their own sovereign",
        "how": "build a store and Polyglot.add(lang, store)",
        "then": "questions in that language route to it and never pool with the others",
    },
    "UNKNOWN_SUBJECT_NOT_A_WORD": {
        "register": "nothing — the path is the answer",
        "why": "the centre is a retrieval key the corpus does not write standalone. Admitting it as a word was measured to cost more than it buys: MIN_ATTEST 3 -> 1 lifted speakable centres to 64% at 4% real words",
    },
    "UNKNOWN_TIME_DEPENDENT": {
        "register": "nothing here — resolve the deictic first",
        "why": "今日 is a property of the question and the store has no clock. Registering the fact does not change the verdict; asking with the date does. Ingest the tool result with its timestamp as the source label to make the answer citable",
    },
    "UNKNOWN_NO_SUBJECT": {
        "register": "nothing — route it to a generator",
        "why": "the text read fine and holds no content word. It CAN be registered — 「こんにちはは挨拶である」 makes a greeting answerable — and a knowledge store answering こんにちは with 挨拶 is not an improvement",
    },
    "UNKNOWN_UNPARSED": {"register": "nothing — the input was empty or unreadable"},
    "NOT_ATTESTED": {
        "register": "sentences connecting the subject to the asked condition, if the connection is in fact true",
        "how": "remember / propose_ai_facts then accept_ai_fact",
        "then": "the same question returns ATTESTED with the new facet as the citation",
        "minimum": 1,
        "note": "this verdict is a coverage gap, not a denial — the corpus never wrote the negative either, and closure forbids inventing it",
    },
    "UNKNOWN_UNDERDETERMINED": {
        "register": "nothing — supply another condition instead",
        "why": "the conditions given leave several cores standing and ties must abstain; a fourth condition narrows where registration would only thicken the tie",
    },
    "UNKNOWN_CONDITIONS_CONFLICT": {
        "register": "nothing about the corpus — the conditions cannot all hold together",
        "why": "a finding about the question, not about coverage",
    },
}


def _reference(result):
    """Naive contract model: classify, copy the repair, then add context."""
    verdict = str(result.get("verdict", ""))
    if verdict.startswith("ANSWER") or verdict in _TERMINAL:
        return {"verdict": verdict, "needs_registration": False}
    spec = _REFERENCE.get(verdict)
    if spec is None:
        return {
            "verdict": verdict,
            "needs_registration": None,
            "note": "no remedy recorded for this verdict",
        }
    out = {
        "verdict": verdict,
        "needs_registration": verdict not in _NO_GAP,
        **spec,
    }
    for key in ("subject", "terms", "missing", "language", "deictic"):
        if result.get(key):
            out[key] = result[key]
    return out


@pytest.mark.parametrize("verdict", ["ANSWER", "ANSWER_FACT", "ANSWER_WITH_CITATION"])
def test_answer_verdicts_are_terminal(verdict):
    expected = {"verdict": verdict, "needs_registration": False}
    assert remedy({"verdict": verdict}) == expected


@pytest.mark.parametrize("verdict", sorted(_TERMINAL))
def test_other_positive_verdicts_are_terminal(verdict):
    assert remedy({"verdict": verdict}) == {
        "verdict": verdict,
        "needs_registration": False,
    }


def test_unrecorded_verdict_has_no_guessed_repair():
    assert remedy({"verdict": "UNKNOWN_FUTURE_CASE", "subject": "x"}) == {
        "verdict": "UNKNOWN_FUTURE_CASE",
        "needs_registration": None,
        "note": "no remedy recorded for this verdict",
    }


def test_registration_gaps_have_distinct_typed_repairs():
    for verdict, minimum in (
        ("UNKNOWN_NO_EVIDENCE", 3),
        ("UNKNOWN_NOT_PRESENT", 3),
        ("UNKNOWN_SUBJECT_TOO_THIN", 3),
        ("NOT_ATTESTED", 1),
    ):
        result = remedy({"verdict": verdict})
        assert result["needs_registration"] is True
        assert result["minimum"] == minimum
        assert result["register"]


def test_routing_refusals_do_not_request_registration():
    for verdict in _NO_GAP:
        result = remedy({"verdict": verdict})
        assert result["needs_registration"] is False
        assert result["register"]


def test_context_is_carried_on_known_repairs():
    context = {
        "subject": "mercury",
        "terms": ["metal", "planet"],
        "missing": ["density"],
        "language": "en",
        "deictic": "today",
    }
    result = remedy({"verdict": "UNKNOWN_SUBJECT_TOO_THIN", **context})
    assert all(result[key] == value for key, value in context.items())


def test_unrecognized_verdict_does_not_invent_a_contextual_repair():
    result = remedy({"verdict": "UNKNOWN_NEW", "missing": ["cause"]})
    assert result["needs_registration"] is None
    assert "missing" not in result


def test_reference_agrees_for_generated_verdict_and_context_cases():
    verdicts = (
        list(_REFERENCE)
        + ["ANSWER", "ANSWER_DETAIL", *_TERMINAL, "UNKNOWN_NEW", "", "NOT_A_VERDICT"]
    )
    context_values = (None, "", "subject-value")
    keys = ("subject", "terms", "missing", "language", "deictic")
    for verdict, values in product(verdicts, product(context_values, repeat=len(keys))):
        case = {"verdict": verdict}
        case.update({key: value for key, value in zip(keys, values)})
        assert remedy(case) == _reference(case), case


def test_reference_agrees_when_verdict_is_absent_or_coerced():
    for case in ({}, {"verdict": None}, {"verdict": 17}, {"verdict": "ANSWERISH"}):
        assert remedy(case) == _reference(case), case
