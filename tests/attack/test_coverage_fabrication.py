from types import SimpleNamespace

import pytest

from verantyx.coverage import closing_domains, document_needed
from verantyx.granularity import SPLITS


def _shelf(crosses=(), source_labels=()):
    return SimpleNamespace(crosses=set(crosses), source_labels=set(source_labels))


def test_exact_core_has_direct_signal_and_score_two():
    subject = "労働安全"
    result = closing_domains({"法令": _shelf({subject})}, subject)

    assert result["closest"] == [
        {"domain": "法令", "score": 2, "signals": ["held: %s" % subject]}
    ]
    assert result["coverage_hole"] is False


def test_source_label_alone_is_not_counted_as_a_core():
    subject = "地域福祉"
    result = closing_domains(
        {"百科": _shelf({subject}, {subject})}, subject
    )

    assert result["closest"] == []
    assert result["coverage_hole"] is True


def test_one_subject_unit_is_labeled_as_proximity_only():
    subject = "ABCDE"
    left, _right = SPLITS[len(subject)][0]
    unit = subject[:left]
    result = closing_domains({"百科": _shelf({unit})}, subject)

    assert result["closest"] == [
        {"domain": "百科", "score": 1, "signals": ["unit held: %s" % unit]}
    ]
    assert result["coverage_hole"] is False


def test_distinct_subject_units_each_contribute_one():
    subject = "ABCDE"
    first_start = SPLITS[len(subject)][0][0]
    second_start = SPLITS[len(subject)][1][0]
    units = {subject[:first_start], subject[:second_start]}
    result = closing_domains({"百科": _shelf(units)}, subject)

    assert result["closest"][0]["score"] == 2
    assert set(result["closest"][0]["signals"]) == {
        "unit held: %s" % unit for unit in units
    }


def test_direct_core_ranks_above_a_partial_unit():
    subject = "ABCDE"
    left, _right = SPLITS[len(subject)][0]
    unit = subject[:left]
    result = closing_domains(
        {"部分": _shelf({unit}), "完全": _shelf({subject})}, subject
    )

    assert [(row["domain"], row["score"]) for row in result["closest"]] == [
        ("完全", 2),
        ("部分", 1),
    ]
    assert result["closest"][0]["signals"] == ["held: %s" % subject]


def test_direct_alias_core_keeps_the_one_hop_visible():
    subject, canonical = "旧題", "現行題"
    result = closing_domains(
        {"百科": _shelf({canonical})}, subject, aliases={subject: canonical}
    )

    assert result["canonical"] == canonical
    assert result["closest"] == [
        {
            "domain": "百科",
            "score": 2,
            "signals": ["alias held: %s → %s" % (subject, canonical)],
        }
    ]


def test_alias_lookup_does_not_follow_an_unattested_chain():
    subject = "旧題"
    result = closing_domains(
        {"百科": _shelf({"最終題"})},
        subject,
        aliases={subject: "中間題", "中間題": "最終題"},
    )

    assert result["closest"] == []
    assert result["coverage_hole"] is True


def test_empty_atlas_reports_a_hole_without_inventing_a_shelf():
    subject = "海洋地質"
    result = closing_domains({}, subject)
    needed = document_needed({}, subject)

    assert result["closest"] == []
    assert result["coverage_hole"] is True
    assert subject in needed["document"]
    assert "ジャンルごと不足" in needed["document"]


def test_two_way_tie_is_shown_instead_of_broken():
    subject = "労働安全"
    needed = document_needed(
        {"wiki": _shelf({subject}), "law": _shelf({subject})}, subject
    )

    assert [row["domain"] for row in needed["closest"]] == ["law", "wiki"]
    assert needed["document"].startswith("law・wiki の文書")


def test_signal_stays_with_the_domain_that_holds_the_subject():
    subject = "自然保護"
    result = closing_domains(
        {"百科": _shelf({"別の語"}), "法令": _shelf({subject})}, subject
    )

    assert [row["domain"] for row in result["closest"]] == ["法令"]
    assert result["closest"][0]["signals"] == ["held: %s" % subject]


@pytest.mark.parametrize("count", [5, 6])
@pytest.mark.xfail(
    strict=False,
    reason="DEFECT: closest truncates equal-score shelves before displaying the full tie",
)
def test_all_shelves_tied_at_the_display_cutoff_are_included(count):
    subject = "労働安全"
    domains = {
        "shelf-%02d" % index: _shelf({subject}) for index in range(count)
    }
    result = closing_domains(domains, subject)

    assert [row["domain"] for row in result["closest"]] == sorted(domains)


@pytest.mark.parametrize(
    "subject,canonical",
    [("旧題甲", "Human Rights"), ("旧題乙", "Data Protection")],
)
@pytest.mark.xfail(
    strict=False,
    reason="DEFECT: mixed-case canonical core titles are missed by case-folded lookup",
)
def test_mixed_case_canonical_title_held_exactly_is_found(subject, canonical):
    result = closing_domains(
        {"百科": _shelf({canonical})}, subject, aliases={subject: canonical}
    )

    assert result["closest"] == [
        {
            "domain": "百科",
            "score": 2,
            "signals": ["alias held: %s → %s" % (subject, canonical)],
        }
    ]
