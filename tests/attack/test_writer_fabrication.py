"""Provenance attacks against the assembled sentence writer."""
from types import SimpleNamespace

import pytest

import verantyx.writer as writer_module
from verantyx.compose_ja import Form, load_selection
from verantyx.vocabulary import Vocabulary
from verantyx.writer import Writer


class _Draft:
    def __init__(self, value):
        self.value = value

    def as_dict(self):
        return dict(self.value)


def _writer(attested, *, norm_corpora=()):
    return Writer(
        vocab=Vocabulary(attested=attested),
        forms={"unused-shape": object()},
        norm_corpora=set(norm_corpora),
    )


def _store(crosses, *, source_labels=()):
    return SimpleNamespace(crosses=crosses, source_labels=set(source_labels))


def _capture_compose(monkeypatch, drafts=()):
    calls = []

    def compose(forms, subject, facets, **kwargs):
        calls.append((forms, subject, list(facets), kwargs))
        if callable(drafts):
            return drafts(forms, subject, facets, kwargs)
        return list(drafts)

    monkeypatch.setattr(writer_module, "compose", compose)
    return calls


def _geography_case():
    load_selection({})
    store = _store({"東京": {"近畿地方"}})
    prose = [("wiki", "東京は関東地方にある。京都は近畿地方にある。"
                       "大阪は近畿地方にある。名古屋は中部地方にある。"
                       "札幌は北海道にある。")]
    writer = Writer.build([store], prose)
    terms = ("東京", "関東地方", "京都", "近畿地方", "大阪", "名古屋",
             "中部地方", "札幌", "北海道")
    writer.vocab = Vocabulary(attested={term: {"wiki": 1} for term in terms})
    return writer, store


def test_unattested_subject_returns_nothing_without_composition(monkeypatch):
    calls = _capture_compose(monkeypatch)
    writer = _writer({"既知": {"wiki": 1}})

    assert writer.sentence(_store({"未知": {"既知"}}), "未知") == []
    assert calls == []


def test_subject_routing_does_not_borrow_another_entity_facets(monkeypatch):
    calls = _capture_compose(monkeypatch)
    writer = _writer({"甲": {"wiki": 1}, "乙": {"wiki": 1}})
    store = _store({"甲": {"青"}, "乙": {"赤"}})

    writer.sentence(store, "甲")

    assert len(calls) == 1
    forms, subject, facets, kwargs = calls[0]
    assert forms is writer.forms
    assert (subject, facets, kwargs["content_from"]) == ("甲", ["青"], ["甲"])


def test_source_labels_are_removed_from_candidate_facets(monkeypatch):
    calls = _capture_compose(monkeypatch)
    writer = _writer({"主体": {"wiki": 1}})
    store = _store({"主体": {"資料A", "概念"}}, source_labels={"資料A"})

    writer.sentence(store, "主体")

    assert calls[0][2] == ["概念"]


def test_sentence_passes_record_licence_for_record_dominant_subject(monkeypatch):
    calls = _capture_compose(monkeypatch)
    writer = _writer({"主体": {"wiki": 8, "law": 2}}, norm_corpora={"law"})

    writer.sentence(_store({"主体": set()}), "主体")

    assert calls[0][3]["licence"] == "record"


def test_sentence_passes_norm_licence_for_norm_dominant_subject(monkeypatch):
    calls = _capture_compose(monkeypatch)
    writer = _writer({"主体": {"wiki": 2, "law": 8}}, norm_corpora={"law"})

    writer.sentence(_store({"主体": set()}), "主体")

    assert calls[0][3]["licence"] == "norm"


def test_missing_attestation_has_unknown_licence():
    writer = _writer({})

    assert writer.licence("主体") == "unknown"


def test_sentence_forwards_limit_and_preserves_draft_sources(monkeypatch):
    payload = {
        "text": "甲は青です。",
        "template": "<0>は<1>です",
        "fills": ["甲", "青"],
        "content_from": ["甲"],
        "form_from": "wiki",
        "note": "draft; content and form have separate sources",
    }
    calls = _capture_compose(monkeypatch, [_Draft(payload)])
    writer = _writer({"甲": {"wiki": 1}})

    result = writer.sentence(_store({"甲": {"青"}}), "甲", limit=4)

    assert calls[0][3]["limit"] == 4
    assert result == [payload]


def test_passage_keeps_walk_path_trace_and_written_counts(monkeypatch):
    trace = object()
    walk_trace = SimpleNamespace(seen=["甲", "乙", "未登録"])
    walk_calls = []

    def walk(store, seed, *, mode, steps, trace=None):
        walk_calls.append((store, seed, mode, steps, trace))
        return walk_trace

    monkeypatch.setattr(writer_module, "walk", walk)
    payload = {
        "text": "甲は青です。",
        "template": "<0>は<1>です",
        "fills": ["甲", "青"],
        "content_from": ["甲"],
        "form_from": "wiki",
    }

    def draft_for_alpha(forms, subject, facets, kwargs):
        return [_Draft(payload)] if subject == "甲" else []

    calls = _capture_compose(monkeypatch, draft_for_alpha)
    writer = _writer({"甲": {"wiki": 1}, "乙": {"wiki": 1}})
    store = _store({"甲": {"青"}, "乙": {"赤"}})

    result = writer.passage(store, "甲", steps=3, mode="seed", trace=trace)

    assert walk_calls == [(store, "甲", "seed", 3, trace)]
    assert result["path"] == ["甲", "乙", "未登録"]
    assert result["sentences"] == [payload]
    assert (result["written"], result["skipped"]) == (1, 2)
    assert result["trace"] is walk_trace
    assert [call[1] for call in calls] == ["甲", "乙"]


def test_real_composition_retains_content_and_form_source_labels():
    writer, store = _geography_case()

    drafts = writer.sentence(store, "東京")

    assert drafts
    draft = drafts[0]
    assert draft["template"] == "<0>は<1>にある"
    assert draft["fills"] == ["東京", "近畿地方"]
    assert draft["content_from"] == ["東京"]
    assert draft["form_from"] == "wiki"
    assert "neither makes this sentence true" in draft["note"]


def test_real_composition_keeps_negation_in_the_learned_shape():
    load_selection({})
    store = _store({"東京": {"近畿地方"}})
    prose = [("wiki", "東京は近畿地方にはない。京都は関東地方にはない。"
                       "大阪は関東地方にはない。名古屋は近畿地方にはない。"
                       "札幌は近畿地方にはない。")]
    writer = Writer.build([store], prose)
    terms = ("東京", "近畿地方", "京都", "関東地方", "大阪", "名古屋", "札幌")
    writer.vocab = Vocabulary(attested={term: {"wiki": 1} for term in terms})

    drafts = writer.sentence(store, "東京")

    assert drafts
    assert drafts[0]["template"] == "<0>は<1>にはない"
    assert drafts[0]["text"].endswith("にはない。")


@pytest.mark.xfail(
    strict=False,
    reason="DEFECT: a reusable location form asserts an unsupported subject-facet relation.",
)
def test_writer_does_not_assert_location_from_a_reusable_shape():
    observed = []
    for _ in range(2):
        writer, store = _geography_case()
        observed.append(writer.sentence(store, "東京"))

    # The prose puts Tokyo in Kanto, and Kyoto and Osaka in Kinki. The store
    # supplies a Tokyo/Kinki facet pair, but no typed location relation.
    assert all(
        all(draft["text"] != "東京は近畿地方にある。" for draft in drafts)
        for drafts in observed
    )
