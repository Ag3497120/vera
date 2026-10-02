"""W1-g B03: the closed-choice prompt shows the queried word as the JSON string, verbatim.

The word handed to ``Resolver`` by ``SemanticUnknownChoice`` is already a JSON string
(``_prompt_json``). The displayed word must therefore be that JSON text itself: nothing
may double the backslashes, and nothing may let a raw line separator or a raw frame
delimiter reach the prompt. Expected values are derived here from ``json``, not from the
product's helper.
"""
import json
import re
from types import SimpleNamespace

import pytest

from verantyx.semantic_unknown_choice import SemanticUnknownChoice

TERMS = {
    "backslash": "a\\b",
    "frame_quotes": "x「y」z",
    "line_separator_zl": "l1 l2",
    "paragraph_separator_zp": "p1 p2",
    "c1_nel": "nel\x85next",
    "del": "del\x7fx",
    "zero_width_cf": "zw​j",
    "six_char_u000a": "\\u000a",
    "quote_tab_cr_lf": '"q" \t\r\n',
}

_START, _END = "語: 「", "」\n使われた場面"


def _report(term):
    candidate = SimpleNamespace(
        term="widget", units=("widget",), families=(), options=(),
        kind="unit", constructed=True, provenance=(),
    )
    return SimpleNamespace(term=term, status="CANDIDATES", candidates=[candidate])


def _selecting_widget(prompts):
    def asker(prompt):
        prompts.append(prompt)
        for line in prompt.splitlines():
            match = re.match(r"^(\d+): (\{.*\})$", line)
            if match and json.loads(match.group(2)).get("term") == "widget":
                return json.dumps({"choice": int(match.group(1))})
        return '{"choice": null}'
    return asker


def _segment(prompt):
    assert prompt.count(_START) == 1
    head, rest = prompt.split(_START, 1)
    assert _END in rest
    return rest.split(_END, 1)[0]


def _run(term):
    prompts = []
    chooser = SemanticUnknownChoice(_selecting_widget(prompts), seed=7)
    result = chooser.choose(_report(term), [])
    return result, prompts


@pytest.fixture(scope="module")
def baseline_line_count():
    _, prompts = _run("flarn")
    assert len(prompts) == 2
    return [len(p.splitlines()) for p in prompts]


@pytest.mark.parametrize("name", sorted(TERMS))
def test_displayed_word_is_the_json_string_verbatim(name, baseline_line_count):
    term = TERMS[name]
    result, prompts = _run(term)
    assert len(prompts) == 2
    for variant, prompt in enumerate(prompts):
        seg = _segment(prompt)
        # 1. the segment decodes back to exactly the queried word
        assert json.loads(seg) == term
        # 2. it cannot be split into several lines, and holds no raw frame delimiter
        assert seg.splitlines() == [seg]
        assert "「" not in seg and "」" not in seg
        # 3. the word does not add lines to the prompt
        assert len(prompt.splitlines()) == baseline_line_count[variant]
    # 4. the decision type does not change
    assert result["decision"] == "ADOPT"
    assert result["option"] == "widget"


def test_backslash_is_not_doubled():
    # json.dumps('a\\b') is the 6-character text "a\\b" with an escaped backslash;
    # the old double escape produced 8 characters between the quotes.
    _, prompts = _run("a\\b")
    assert _segment(prompts[0]) == json.dumps("a\\b", ensure_ascii=False)
    assert _segment(prompts[0]) == '"a\\\\b"'


def test_c1_and_del_controls_never_appear_raw():
    for term in ("nel\x85next", "del\x7fx"):
        _, prompts = _run(term)
        for prompt in prompts:
            seg = _segment(prompt)
            assert not any(ch in seg for ch in ("\x85", "\x7f"))
