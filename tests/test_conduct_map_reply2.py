"""The minimal-form reply classifiers of conduct_map/v2 (``classify_index_list_reply`` and ``classify_label_reply``).

A reply is the *whole* text (only leading / trailing spaces, tabs and line breaks are removed): ``なし`` or ASCII digits
separated by commas for a selection, exactly one of the offered labels for a label.  Everything else is invalid and is never
repaired: no digit is read out of a sentence, no label out of an explanation, no JSON is unpacked."""
from __future__ import annotations

import pytest

from verantyx.llm_choice import classify_index_list_reply as idx
from verantyx.llm_choice import classify_label_reply as lab

DECIDES = ("決まる", "決まらない")
RELATIONS = ("一致", "矛盾", "無関係")


@pytest.mark.parametrize("text,expect", [
    ("3", ("PICK", (3,), None)),
    ("0,4", ("PICK", (0, 4), None)),
    ("4,0", ("PICK", (0, 4), None)),                           # ascending, whatever order the model wrote
    (" 0 , 4 ", ("PICK", (0, 4), None)),
    ("\n3\n", ("PICK", (3,), None)),
    ("\r\n0,\n4\r\n", ("PICK", (0, 4), None)),
    ("0", ("PICK", (0,), None)),
    ("なし", ("NONE", None, None)),
    ("\nなし\n", ("NONE", None, None)),
    ("  なし  ", ("NONE", None, None)),
])
def test_valid_index_list_replies(text, expect):
    assert idx(text, 5) == expect


@pytest.mark.parametrize("text,reason", [
    ("３", "NOT_MINIMAL_FORM"),                                  # a full-width digit
    ("３,４", "NOT_MINIMAL_FORM"),
    ("3。", "NOT_MINIMAL_FORM"),
    ('"3"', "NOT_MINIMAL_FORM"),
    ("```3```", "NOT_MINIMAL_FORM"),
    ("```\n3\n```", "NOT_MINIMAL_FORM"),
    ('{"records":[3]}', "NOT_MINIMAL_FORM"),
    ("[3]", "NOT_MINIMAL_FORM"),
    ("3\n答え: はい", "NOT_MINIMAL_FORM"),
    ("答え: 3", "NOT_MINIMAL_FORM"),
    ("番号は 3 です", "NOT_MINIMAL_FORM"),
    ("-1", "NOT_MINIMAL_FORM"),
    ("", "NOT_MINIMAL_FORM"),
    ("   \n", "NOT_MINIMAL_FORM"),
    ("なし。", "NOT_MINIMAL_FORM"),
    ("なし\n理由: 無関係", "NOT_MINIMAL_FORM"),
    ("None", "NOT_MINIMAL_FORM"),
    ("3,", "NOT_MINIMAL_FORM"),
    (",3", "NOT_MINIMAL_FORM"),
    ("3 4", "NOT_MINIMAL_FORM"),
    ("3、4", "NOT_MINIMAL_FORM"),                               # an ideographic comma
    ("03", "NOT_MINIMAL_FORM"),                                  # a leading zero
    ("1.5", "NOT_MINIMAL_FORM"),
    (" 3", "NOT_MINIMAL_FORM"),                             # a no-break space is not a space of the form
    ("5", "OUT_OF_RANGE"),
    ("0,5", "OUT_OF_RANGE"),
    ("99", "OUT_OF_RANGE"),
    ("1,1", "DUPLICATE"),
    ("0,2,0", "DUPLICATE"),
])
def test_invalid_index_list_replies_carry_their_reason(text, reason):
    assert idx(text, 5) == ("INVALID", None, reason)


def test_an_index_list_over_an_empty_list_has_no_valid_number():
    assert idx("0", 0) == ("INVALID", None, "OUT_OF_RANGE")
    assert idx("なし", 0) == ("NONE", None, None)


@pytest.mark.parametrize("labels", [DECIDES, ("決まらない", "決まる"), RELATIONS, ("無関係", "一致", "矛盾")])
def test_a_label_is_valid_whatever_order_it_was_offered_in(labels):
    for one in labels:
        assert lab(one, labels) == ("PICK", one, None)
        assert lab(f"\n {one}\n", labels) == ("PICK", one, None)


@pytest.mark.parametrize("text", [
    "一致。", "一致（肢1）", "決まる。答えは A", '{"relation":"一致"}', "```\n一致\n```", "一致\n理由: 同じ", "「一致」", "ichi",
    "", "  ", "決まる決まらない", "一致,矛盾", "はい", "1",
])
def test_an_invalid_label_reply_is_never_repaired(text):
    for labels in (RELATIONS, DECIDES):
        assert lab(text, labels) == ("INVALID", None, "NOT_MINIMAL_FORM")


def test_a_label_of_the_other_set_is_not_a_label():
    assert lab("決まる", RELATIONS) == ("INVALID", None, "NOT_MINIMAL_FORM")
    assert lab("一致", DECIDES) == ("INVALID", None, "NOT_MINIMAL_FORM")


def test_a_failure_is_not_a_reply_and_is_never_classified():
    with pytest.raises(TypeError):
        idx(None, 3)                                              # type: ignore[arg-type]
    with pytest.raises(TypeError):
        lab(None, DECIDES)                                        # type: ignore[arg-type]


def test_the_classifiers_of_the_earlier_protocol_are_still_there_and_unchanged_in_kind():
    from verantyx import llm_choice as L
    assert L.classify_records_reply('{"records": []}', 3)[0] == "NONE"
    assert L.classify_relations_reply('{"relations": ["一致"]}', 1)[0] == "PICK"
    assert L.classify_phases_reply('{"phases": []}', 3)[0] == "NONE"
    assert idx('{"records": []}', 3)[0] == "INVALID"              # and a JSON reply is not a valid reply of the new form
