from dataclasses import replace

import pytest

from verantyx.content_api import ContentEngine
from verantyx.content_ir import Budget, ContentError, Source, Span, State
from verantyx.content_reader import read_brief
from verantyx.content_planner import build_plan


OPEN = "規則：箱が閉じているとき、ミナが箱を開けると、箱が開いている。"
CLOSE = "規則：箱が開いているとき、ミナが箱を閉めると、箱が閉じている。"


def test_backward_goal_requires_new_action_composition_not_stored_text():
    brief = "架空の物語を3文で書いて。過去形で。最初は箱が閉じている。" + OPEN + "出来事は自由に決めてよい。最後は箱が開いている。"
    result = ContentEngine().ask(brief)
    assert result["verdict"] == "CREATED", result
    assert "ミナが箱を開けた。" in result["text"]
    assert len(result["plan"]["transitions"]) == 1
    assert result["plan"]["author_choices"] == ("events",)
    assert result["plan"]["final"][0]["value"] == "open"
    assert not result["novelty_verified"]


def test_two_transitions_hold_final_state_without_automatic_causality():
    brief = "架空の物語を4文で書いて。最初は箱が閉じている。" + OPEN + CLOSE + "ミナが箱を開ける。その後、ミナが箱を閉める。最後は箱が閉じている。"
    result = ContentEngine().ask(brief)
    assert result["verdict"] == "CREATED", result
    assert len(result["plan"]["transitions"]) == 2
    assert "その後" in result["text"] and "そのため" not in result["text"]


@pytest.mark.parametrize("brief,verdict", [
    ("物語を書いて。" + OPEN + "ミナが箱を開ける。", "UNKNOWN_CONTENT_PRECONDITION"),
    ("物語を書いて。初期状態：箱が閉じていない。" + OPEN + "ミナが箱を開ける。", "UNKNOWN_CONTENT_PRECONDITION"),
    ("物語を書いて。初期状態：箱が閉じている。初期状態：箱が開いている。", "CONTENT_STATE_CONFLICT"),
    ("物語を書いて。最初は箱が閉じている。最後は箱が開いている。", "UNKNOWN_CONTENT_NO_PLAN"),
    ("物語を書いて。初期状態：箱が閉じている。" + OPEN + "ミナが箱を開ける。その後、箱が閉じている。", "CONTENT_STATE_CONFLICT"),
    ("物語を書いて。ミナが歩く。その後、箱が閉じている。", "UNKNOWN_CONTENT_STATE"),
])
def test_unknown_negative_and_conflicting_state_are_distinct(brief, verdict):
    result = ContentEngine().ask(brief)
    assert result["verdict"] == verdict, result


@pytest.mark.parametrize("permission", ["", "順序は自由に決めてよい。", "出来事は自由に決めてよい。"])
def test_rule_interpretation_tie_is_not_an_author_choice(permission):
    brief = ("物語を書いて。初期状態：箱が閉じている。"
             "規則：ミナが箱を開けると、箱が開いている。"
             "規則：ミナが箱を開けると、箱が閉じている。"
             "ミナが箱を開ける。" + permission)
    assert ContentEngine().ask(brief)["verdict"] == "UNKNOWN_CONTENT_RULE_AMBIGUOUS"


def test_supported_alternative_rule_is_not_lost_to_an_unknown_first_rule():
    brief = ("物語を書いて。初期状態：箱が閉じている。"
             "規則：手紙が開いているとき、ミナが箱を開けると、箱が開いている。" + OPEN +
             "ミナが箱を開ける。最後は箱が開いている。")
    assert ContentEngine().ask(brief)["verdict"] == "CREATED"


def test_rule_exception_needs_explicit_falsity():
    ledger = read_brief("物語を書いて。初期状態：箱が閉じている。" + OPEN + "ミナが箱を開ける。")
    rule = replace(ledger.rules[0], exceptions=(State("手紙", "open", "open"),))
    ledger = replace(ledger, rules=(rule,))
    with pytest.raises(ContentError) as caught:
        build_plan(ledger)
    assert caught.value.verdict == "UNKNOWN_CONTENT_EXCEPTION"


def test_new_ownership_rule_uses_bound_roles():
    brief = ("物語を3文で書いて。初期状態：鍵はエナの持ち物だ。"
             "作品内の規則：鍵はエナの持ち物だとき、エナがトウに鍵を渡すと、鍵はトウの持ち物だ。"
             "出来事は自由に決めてよい。最後は鍵はトウの持ち物だ。")
    result = ContentEngine().ask(brief)
    assert result["verdict"] == "CREATED", result
    assert "エナがトウに鍵を渡す。" in result["text"]
    assert result["plan"]["final"][0]["value"] == "トウ"
