"""The two closed reply readers added to llm_choice for the record mapping (W2-g)."""
from __future__ import annotations

import json

import pytest

from verantyx import llm_choice as L


def rec(text, n=4):
    return L.classify_records_reply(text, n)


def rel(text, k=3):
    return L.classify_relations_reply(text, k)


def test_records_none_pick_and_order():
    assert rec('{"records": []}') == ("NONE", None, None, None)
    assert rec(' {"records": [2, 0], "decides": "決まる"}\n') == ("PICK", (0, 2), "決まる", None)
    assert rec('{"decides": "決まらない", "records": [3]}') == ("PICK", (3,), "決まらない", None)


@pytest.mark.parametrize("text,why", [
    ("not json", "NOT_JSON"),
    ('```json\n{"records": []}\n```', "NOT_JSON"),
    ('{"records": []} 以上です', "NOT_JSON"),
    ('{"records": [0], "records": [1], "decides": "決まる"}', "NOT_JSON"),
    ('[0, 1]', "NOT_RECORDS_OBJECT"),
    ('{"records": 1, "decides": "決まる"}', "NOT_RECORDS_OBJECT"),
    ('{"records": [0], "decides": "決まる", "answer": "はい"}', "NOT_RECORDS_OBJECT"),
    ('{"records": [0], "decides": "決まる", "option": 1}', "NOT_RECORDS_OBJECT"),
    ('{"records": [], "decides": "決まる"}', "NOT_RECORDS_OBJECT"),
    ('{"records": [0]}', "NOT_RECORDS_OBJECT"),
    ('{"answer": 1}', "NOT_RECORDS_OBJECT"),
    ('{"records": [true], "decides": "決まる"}', "NOT_INTEGER"),
    ('{"records": ["0"], "decides": "決まる"}', "NOT_INTEGER"),
    ('{"records": [1.0], "decides": "決まる"}', "NOT_INTEGER"),
    ('{"records": [4], "decides": "決まる"}', "OUT_OF_RANGE"),
    ('{"records": [-1], "decides": "決まる"}', "OUT_OF_RANGE"),
    ('{"records": [1, 1], "decides": "決まる"}', "DUPLICATE"),
    ('{"records": [0], "decides": "たぶん決まる"}', "BAD_DECIDES"),
    ('{"records": [0], "decides": null}', "BAD_DECIDES"),
    ('{"records": [0], "decides": ["決まる"]}', "BAD_DECIDES"),
])
def test_records_invalid_forms(text, why):
    verdict, picks, decides, reason = rec(text)
    assert (verdict, picks, decides, reason) == ("INVALID", None, None, why)


def test_records_needs_text():
    with pytest.raises(TypeError):
        L.classify_records_reply(None, 3)


def test_relations_valid():
    assert rel('{"relations": ["一致", "矛盾", "無関係"]}') == ("PICK", ("一致", "矛盾", "無関係"), None)
    assert rel('{"relations": ["無関係", "無関係"]}', 2) == ("PICK", ("無関係", "無関係"), None)


@pytest.mark.parametrize("text,why", [
    ("{", "NOT_JSON"),
    ('```\n{"relations": ["一致", "一致", "一致"]}\n```', "NOT_JSON"),
    ('{"relations": ["一致"], "relations": ["矛盾"]}', "NOT_JSON"),
    ('["一致", "矛盾", "無関係"]', "NOT_RELATIONS_OBJECT"),
    ('{"relations": "一致"}', "NOT_RELATIONS_OBJECT"),
    ('{"relations": ["一致", "矛盾", "無関係"], "answer": 1}', "NOT_RELATIONS_OBJECT"),
    ('{"relations": ["一致", "矛盾"]}', "BAD_LENGTH"),
    ('{"relations": ["一致", "矛盾", "無関係", "一致"]}', "BAD_LENGTH"),
    ('{"relations": ["一致", "反する", "無関係"]}', "BAD_LABEL"),
    ('{"relations": [0, 1, 2]}', "BAD_LABEL"),
    ('{"relations": [true, "矛盾", "無関係"]}', "BAD_LABEL"),
])
def test_relations_invalid_forms(text, why):
    assert rel(text) == ("INVALID", None, why)


def test_relations_needs_text():
    with pytest.raises(TypeError):
        L.classify_relations_reply(None, 1)


def test_names_are_exported_and_nothing_else_changed():
    for name in ("classify_records_reply", "classify_relations_reply"):
        assert name in L.__all__
    assert json.loads('{"choice": null}') == {"choice": None}
    assert L.classify_reply('{"choice": null}', 2)[0] == "NONE"      # the single-choice reader is untouched


# ---- classify_phases_reply (the order route: which phases does the question / do the options speak of, and does their order
# ---- alone settle the question: the same closed form as the records reply) ------------------------------------------------

def phs(text, n=5):
    return L.classify_phases_reply(text, n)


def test_phases_none_pick_and_order():
    assert phs('{"phases": []}') == ("NONE", None, None, None)
    assert phs(' {"phases": [3, 0], "decides": "決まる"}\n') == ("PICK", (0, 3), "決まる", None)
    assert phs('{"decides": "決まらない", "phases": [4]}') == ("PICK", (4,), "決まらない", None)


@pytest.mark.parametrize("text,why", [
    ("not json", "NOT_JSON"),
    ('```json\n{"phases": [0], "decides": "決まる"}\n```', "NOT_JSON"),
    ('{"phases": [0], "decides": "決まる"} 以上です', "NOT_JSON"),
    ('{"phases": [0], "phases": [1], "decides": "決まる"}', "NOT_JSON"),
    ('{"phases": [0], "decides": "決まる", "decides": "決まらない"}', "NOT_JSON"),
    ('[0, 1]', "NOT_PHASES_OBJECT"),
    ('{"phases": 1}', "NOT_PHASES_OBJECT"),
    ('{"phases": [0], "decides": "決まる", "answer": "はい"}', "NOT_PHASES_OBJECT"),
    ('{"phases": [0], "decides": "決まる", "option": 1}', "NOT_PHASES_OBJECT"),
    ('{"phases": [0]}', "NOT_PHASES_OBJECT"),                                   # a phase without the closed decides is not a reply
    ('{"phases": [], "decides": "決まらない"}', "NOT_PHASES_OBJECT"),             # decides without a phase
    ('{"records": [0], "decides": "決まる"}', "NOT_PHASES_OBJECT"),
    ('{"phases": [true], "decides": "決まる"}', "NOT_INTEGER"),
    ('{"phases": ["0"], "decides": "決まる"}', "NOT_INTEGER"),
    ('{"phases": [1.0], "decides": "決まる"}', "NOT_INTEGER"),
    ('{"phases": [5], "decides": "決まる"}', "OUT_OF_RANGE"),
    ('{"phases": [-1], "decides": "決まる"}', "OUT_OF_RANGE"),
    ('{"phases": [1, 1], "decides": "決まる"}', "DUPLICATE"),
    ('{"phases": [0], "decides": "たぶん決まる"}', "BAD_DECIDES"),
    ('{"phases": [0], "decides": null}', "BAD_DECIDES"),
    ('{"phases": [0], "decides": ["決まる"]}', "BAD_DECIDES"),
])
def test_phases_invalid_replies(text, why):
    assert phs(text) == ("INVALID", None, None, why)


def test_phases_reply_needs_text_not_a_failure():
    with pytest.raises(TypeError):
        L.classify_phases_reply(None, 3)
