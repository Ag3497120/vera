"""Differential checks for the coverage shelf ranking."""

from __future__ import annotations

import random
from types import SimpleNamespace

import pytest

from verantyx.coverage import closing_domains, document_needed
from verantyx.granularity import SPLITS


def _store(crosses=(), source_labels=()):
    return SimpleNamespace(crosses=set(crosses), source_labels=set(source_labels))


def _reference_units(subject):
    """Apply the split table directly, without calling coverage helpers."""
    units = []
    for offset, _kind in SPLITS.get(len(subject), ()):
        units.extend((subject[:offset], subject[offset:]))
    return [unit for unit in units if len(unit) >= 2]


def _reference(domains, subject, aliases=None):
    """Small contract-based oracle: exact cores, exact units, one alias hop."""
    subject = (subject or "").strip()
    canonical = (aliases or {}).get(subject)
    units = _reference_units(subject)
    ranked = []
    for name in sorted(domains):
        store = domains[name]
        crosses = store.crosses
        labels = getattr(store, "source_labels", set()) or set()
        score = 0
        signals = []
        if subject in crosses and subject not in labels:
            score += 2
            signals.append("held: %s" % subject)
        if canonical and canonical in crosses and canonical not in labels:
            score += 2
            signals.append("alias held: %s → %s" % (subject, canonical))
        for unit in units:
            if unit in crosses and unit not in labels:
                score += 1
                signals.append("unit held: %s" % unit)
        if score:
            ranked.append({"domain": name, "score": score, "signals": signals[:4]})
    ranked.sort(key=lambda item: (-item["score"], item["domain"]))
    result = {"subject": subject, "closest": ranked[:4], "coverage_hole": not ranked}
    if canonical:
        result["canonical"] = canonical
    return result


def _subject_with_units():
    for length, splits in SPLITS.items():
        if splits:
            subject = "x" * length
            if _reference_units(subject):
                return subject
    raise AssertionError("the split table has no entries for a unit-count check")


def test_exact_core_presence_adds_two_and_matches_reference():
    subject = "coverage-subject"
    domains = {"main": _store({subject})}

    expected = _reference(domains, subject)
    assert expected["closest"][0]["score"] == 2
    assert closing_domains(domains, subject) == expected


def test_source_label_does_not_count_as_a_core():
    subject = "labelled-subject"
    domains = {"main": _store({subject}, {subject})}

    expected = _reference(domains, subject)
    assert expected["coverage_hole"] is True
    assert closing_domains(domains, subject) == expected


def test_every_matching_unit_counts_even_when_signals_are_capped():
    subject = _subject_with_units()
    units = _reference_units(subject)
    domains = {"units": _store(units)}

    expected = _reference(domains, subject)
    assert expected["closest"][0]["score"] == len(units)
    assert len(expected["closest"][0]["signals"]) == min(4, len(units))
    assert closing_domains(domains, subject) == expected


def test_equal_scores_are_ordered_by_domain_name():
    subject = "tie-subject"
    domains = {
        "zeta": _store({subject}),
        "alpha": _store({subject}),
        "middle": _store({subject}),
    }

    result = closing_domains(domains, subject)
    assert [item["domain"] for item in result["closest"]] == [
        "alpha", "middle", "zeta"
    ]
    assert result == _reference(domains, subject)


def test_only_the_named_alias_hop_is_counted():
    subject = "topic"
    aliases = {"topic": "canonical-topic", "canonical-topic": "ultimate-title"}
    domains = {"canonical shelf": _store({"ultimate-title"})}

    expected = _reference(domains, subject, aliases)
    assert expected["coverage_hole"] is True
    assert closing_domains(domains, subject, aliases=aliases) == expected


def test_top_four_shelves_are_selected_after_score_and_name_sorting():
    subject = "ranked-subject"
    domains = {name: _store({subject}) for name in ("f", "d", "b", "e", "a", "c")}

    expected = _reference(domains, subject)
    assert [item["domain"] for item in expected["closest"]] == ["a", "b", "c", "d"]
    assert closing_domains(domains, subject) == expected


def test_empty_atlas_reports_hole_and_hole_document():
    subject = "absent-genre"
    expected = _reference({}, subject)
    assert expected["coverage_hole"] is True
    assert closing_domains({}, subject) == expected

    result = document_needed({}, subject)
    assert result["coverage_hole"] is True
    assert result["document"] == (
        "どの棚もこの主題の近くを持っていない — %r のジャンルごと"
        "不足。まずこの分野の概説文書を1本(浅くて良い)" % subject
    )


def test_nonempty_atlas_names_the_highest_ranked_shelf():
    subject = "known-genre"
    domains = {"zeta": _store({subject}), "alpha": _store({subject})}

    result = document_needed(domains, subject)
    assert result["coverage_hole"] is False
    assert result["document"].startswith(
        "alpha・zeta の文書 — %s を独立した文で書くもの(" % subject
    )


def test_generated_cases_match_independent_reference():
    rng = random.Random(24019)
    subjects = ["abcdefgh", "mnopqrstu", "coverage-case", "atlas-entry"]
    for case in range(80):
        subject = rng.choice(subjects)
        units = _reference_units(subject)
        canonical = "canonical-%02d" % case
        possible = {subject, canonical, *units, "unrelated-%02d" % case}
        domains = {}
        for shelf in range(7):
            crosses = {token for token in possible if rng.random() < 0.38}
            labels = {token for token in crosses if rng.random() < 0.22}
            domains["shelf-%02d" % shelf] = _store(crosses, labels)
        aliases = {subject: canonical} if case % 2 else None

        assert closing_domains(domains, subject, aliases=aliases) == _reference(
            domains, subject, aliases
        ), "generated case %d" % case


@pytest.mark.xfail(
    strict=False,
    reason="DEFECT: alias lookup casefolds a title against exact core names",
)
def test_alias_core_match_uses_exact_title_presence():
    subject = "topic"
    aliases = {subject: "Widget"}
    domains = {"lowercase only": _store({"widget"})}

    expected = _reference(domains, subject, aliases)
    assert expected["coverage_hole"] is True
    assert closing_domains(domains, subject, aliases=aliases) == expected
