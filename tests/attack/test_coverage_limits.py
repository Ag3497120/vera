from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace

import pytest

from verantyx.coverage import closing_domains, document_needed


def shelf(*crosses, source_labels=()):
    return SimpleNamespace(crosses=set(crosses), source_labels=set(source_labels))


def test_empty_and_whitespace_subject_reports_a_hole():
    result = closing_domains({}, "   \t  ")

    assert result == {"subject": "", "closest": [], "coverage_hole": True}


def test_no_exact_presence_reports_a_hole():
    result = closing_domains({"shelf": shelf("different")}, "target")

    assert result["coverage_hole"] is True
    assert result["closest"] == []


def test_exact_subject_presence_is_ranked():
    result = closing_domains({"atlas": shelf("target")}, "target")

    assert result["coverage_hole"] is False
    assert result["closest"] == [
        {"domain": "atlas", "score": 2, "signals": ["held: target"]}
    ]


def test_alias_is_one_hop_and_names_the_canonical_title():
    result = closing_domains(
        {"atlas": shelf("canonical")},
        "alias",
        aliases={"alias": "canonical", "canonical": "final"},
    )

    assert result["canonical"] == "canonical"
    assert result["closest"] == [
        {
            "domain": "atlas",
            "score": 2,
            "signals": ["alias held: alias → canonical"],
        }
    ]


def test_source_label_alone_does_not_count_as_a_core():
    result = closing_domains(
        {"atlas": shelf("target", source_labels={"target"})}, "target"
    )

    assert result["coverage_hole"] is True
    assert result["closest"] == []


def test_top_four_are_stable_under_domain_insertion_order():
    names = ["zeta", "alpha", "gamma", "beta", "epsilon", "delta"]
    forward = {name: shelf("target") for name in names}
    reverse = {name: shelf("target") for name in reversed(names)}

    a = closing_domains(forward, "target")
    b = closing_domains(reverse, "target")

    assert a == b
    assert [row["domain"] for row in a["closest"]] == [
        "alpha", "beta", "delta", "epsilon"
    ]
    assert len(a["closest"]) == 4


def test_repeated_calls_are_idempotent_and_do_not_mutate_inputs():
    domains = {"atlas": shelf("target")}
    crosses_before = set(domains["atlas"].crosses)
    labels_before = set(domains["atlas"].source_labels)

    first = closing_domains(domains, "target")
    second = closing_domains(domains, "target")

    assert first == second
    assert domains["atlas"].crosses == crosses_before
    assert domains["atlas"].source_labels == labels_before
    first["closest"].clear()
    assert closing_domains(domains, "target")["closest"]


def test_million_character_subject_is_bounded_and_does_not_crash():
    subject = "x" * 1_000_000
    result = closing_domains({}, subject)

    assert result["subject"] == subject
    assert result["coverage_hole"] is True
    assert result["closest"] == []


def test_many_domains_keep_the_returned_ranking_bounded():
    domains = {"shelf-%05d" % i: shelf("target") for i in range(10_000)}
    result = closing_domains(domains, "target")

    assert len(result["closest"]) == 4
    assert [row["domain"] for row in result["closest"]] == [
        "shelf-00000", "shelf-00001", "shelf-00002", "shelf-00003"
    ]


def test_two_concurrent_readers_return_the_same_result():
    domains = {
        "atlas-a": shelf("target"),
        "atlas-b": shelf("other", "target"),
        "atlas-c": shelf("elsewhere"),
    }
    expected = closing_domains(domains, "target")

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _n: closing_domains(domains, "target"), range(64)))

    assert all(result == expected for result in results)


def test_document_needed_reports_the_hole_without_naming_a_shelf():
    result = document_needed({}, "target")

    assert result["coverage_hole"] is True
    assert "どの棚も" in result["document"]
    assert "target" in result["document"]
    assert result["verdict"] == "UNKNOWN_NOT_PRESENT"


@pytest.mark.xfail(strict=False, reason="DEFECT: a four-row cap drops tied shelves despite the tie-display contract")
def test_all_equal_top_shelves_remain_displayed_as_a_tie():
    domains = {"shelf-%d" % i: shelf("target") for i in range(5)}

    result = closing_domains(domains, "target")

    assert [row["domain"] for row in result["closest"]] == [
        "shelf-0", "shelf-1", "shelf-2", "shelf-3", "shelf-4"
    ]
