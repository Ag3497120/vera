"""Independent checks for the writer's small, externally checkable rules."""

from types import SimpleNamespace

import pytest

from verantyx import writer as writer_module
from verantyx.writer import Writer, modernize_form


# This is deliberately a local reference table rather than the implementation's
# private constant. The writer's contract limits modernization to these forms.
_REFERENCE_OLD_KANA = (
    ("によつて", "によって"),
    ("であつて", "であって"),
    ("であつた", "であった"),
    ("わたつて", "わたって"),
    ("つづつて", "つづって"),
    ("もつて", "もって"),
    ("あつた", "あった"),
    ("なつた", "なった"),
    ("よつて", "よって"),
)


def _reference_modernize(template):
    for old, new in _REFERENCE_OLD_KANA:
        template = template.replace(old, new)
    return template


def _reference_licence(attested, norm_corpora, subject):
    counts = attested.get(subject) or {}
    if not counts:
        return "unknown"
    # The contract selects the corpus with the greatest count; label order
    # resolves ties deterministically.
    winner = sorted(counts.items(), key=lambda pair: (pair[1], pair[0]))[-1][0]
    return "norm" if winner in norm_corpora else "record"


@pytest.mark.parametrize("old,new", _REFERENCE_OLD_KANA)
def test_modernize_each_attested_old_kana_form(old, new):
    source = "前" + old + "後"
    expected = _reference_modernize(source)
    assert expected == "前" + new + "後"
    assert modernize_form(source) == expected


def test_modernize_replaces_multiple_forms_and_preserves_other_text():
    source = "によつて/であつて/わたつて/未知の表記"
    assert modernize_form(source) == _reference_modernize(source)


def test_modernize_leaves_unlisted_spelling_unchanged():
    source = "かつた とつた"
    assert modernize_form(source) == _reference_modernize(source) == source


@pytest.mark.parametrize(
    "attested,norm_corpora,subject,expected",
    [
        ({}, set(), "対象", "unknown"),
        ({"対象": {}}, {"法令"}, "対象", "unknown"),
        ({"対象": {"百科": 4, "法令": 2}}, {"法令"}, "対象", "record"),
        ({"対象": {"百科": 2, "法令": 4}}, {"法令"}, "対象", "norm"),
        # Equal counts are resolved by corpus label, independently of insertion
        # order. Here "z法令" wins and is explicitly a norm source.
        ({"対象": {"z法令": 3, "a百科": 3}}, {"z法令"}, "対象", "norm"),
    ],
)
def test_licence_matches_independent_corpus_count_reference(
    attested, norm_corpora, subject, expected
):
    instance = Writer()
    instance.vocab.attested = attested
    instance.norm_corpora = norm_corpora
    reference = _reference_licence(attested, norm_corpora, subject)
    assert reference == expected
    assert instance.licence(subject) == reference


class _Vocabulary:
    def __init__(self, terms):
        self.terms = set(terms)
        self.attested = {}

    def __contains__(self, term):
        return term in self.terms


def test_sentence_does_not_compose_an_unattested_subject(monkeypatch):
    instance = Writer()
    instance.vocab = _Vocabulary({"既知"})
    called = []
    monkeypatch.setattr(writer_module, "compose", lambda *args, **kwargs: called.append(1))
    assert instance.sentence(SimpleNamespace(crosses={}), "未知") == []
    assert called == []


def test_sentence_filters_source_labels_sorts_facets_and_passes_licence(monkeypatch):
    instance = Writer(forms={"形": object()})
    instance.vocab = _Vocabulary({"対象"})
    instance.vocab.attested = {"対象": {"百科": 2}}
    instance.norm_corpora = set()
    store = SimpleNamespace(
        source_labels={"出典語"},
        crosses={"対象": {"z面", "出典語", "a面"}},
    )
    calls = []

    def compose_reference(forms, subject, facets, *, limit, content_from, vocab, licence):
        calls.append(
            {
                "forms": forms,
                "subject": subject,
                "facets": facets,
                "limit": limit,
                "content_from": content_from,
                "vocab": vocab,
                "licence": licence,
            }
        )
        return [SimpleNamespace(as_dict=lambda: {"draft": "typed output"})]

    monkeypatch.setattr(writer_module, "compose", compose_reference)
    result = instance.sentence(store, "対象", limit=3)

    assert result == [{"draft": "typed output"}]
    assert calls == [
        {
            "forms": instance.forms,
            "subject": "対象",
            "facets": ["a面", "z面"],
            "limit": 3,
            "content_from": ["対象"],
            "vocab": instance.vocab,
            "licence": "record",
        }
    ]


def test_passage_reports_written_and_skipped_steps(monkeypatch):
    instance = Writer()
    trace = SimpleNamespace(seen=["起点", "書ける", "書けない"])
    monkeypatch.setattr(writer_module, "walk", lambda *args, **kwargs: trace)
    monkeypatch.setattr(
        instance,
        "sentence",
        lambda store, subject, limit=1: ([{"subject": subject}] if subject == "書ける" else []),
    )

    result = instance.passage(object(), "起点", steps=3)

    assert result["seed"] == "起点"
    assert result["path"] == ["起点", "書ける", "書けない"]
    assert result["sentences"] == [{"subject": "書ける"}]
    assert result["written"] == 1
    assert result["skipped"] == 2
    assert result["trace"] is trace


def test_build_keeps_corpus_labels_and_reports_the_learned_components(monkeypatch):
    class FakeVocabulary:
        def report(self):
            return {"terms": 1}

    monkeypatch.setattr(writer_module, "from_stores", lambda stores, corpora: FakeVocabulary())
    monkeypatch.setattr(writer_module, "learn_selection", lambda corpora: {"slot": 2})
    monkeypatch.setattr(writer_module, "learn_joins", lambda corpora: {"join": 1})
    monkeypatch.setattr(
        writer_module,
        "harvest",
        lambda corpora: {"form": SimpleNamespace(register="norm")},
    )
    prose = [("百科", "abc"), ("法令抜粋", "xy")]

    instance = Writer.build(iter([object()]), prose, norm_corpora={"法令抜粋"})

    assert prose == [("百科", "abc"), ("法令抜粋", "xy")]
    assert instance.norm_corpora == {"法令抜粋"}
    assert instance.built == {
        "corpora": {"百科": 3, "法令抜粋": 2},
        "vocabulary": {"terms": 1},
        "forms": 1,
        "norm_forms": 1,
        "norm_corpora": ["法令抜粋"],
        "selection": {"slot": 2},
        "joins": {"join": 1},
    }
