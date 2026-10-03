"""W5-e (docs/READING_SOUNDNESS.md section 10E, B-1 / B-2): AとB・AやB (coordination) and AかB (disjunction) are not read as one role value, and not split into a
companion; the entry abstains with a typed reason instead.

The rule is read off the tokens, not off a list of nouns: a particle token と・や・か (not inside a compound particle) that follows a noun-like token, is followed without a gap
by noun-like tokens and の, and then by a particle (格助詞・係助詞・副助詞).  The 6 sentences of the attack corpus of W3-b3 that were read (PARALLEL-002, -003, -008, -011, -017, -020)
are run live here, with no placement and with the placement r7; the cases that must not change are run too.
"""
import json
from dataclasses import replace

import pytest

from verantyx import semantic_read as SR
from verantyx import semantic_reader as R
from verantyx.semantic_ir import Clause, Role, Span, Variable

R7 = "/Users/motonisihikoudai/Projects/vera-impl/build/coarse-W3a/full/r7/run1"

HITS = [  # (id in the attack corpus of W3-b3, sentence, the typed reason)
    ("PARALLEL-002", "太郎か花子が本を買った。", "DISJUNCTION_UNDETERMINED"),
    ("PARALLEL-003", "本か雑誌を花子が買った。", "DISJUNCTION_UNDETERMINED"),
    ("PARALLEL-008", "父か母が弟に本を渡した。", "DISJUNCTION_UNDETERMINED"),
    ("PARALLEL-011", "太郎と花子が手紙を読んだ。", "COORDINATION_UNDETERMINED"),
    ("PARALLEL-017", "太郎と次郎が雑誌を買った。", "COORDINATION_UNDETERMINED"),
    ("PARALLEL-020", "先生か学生が手紙を送った。", "DISJUNCTION_UNDETERMINED"),
]


@pytest.fixture(params=["none", "r7"])
def placement(request, monkeypatch):
    monkeypatch.delenv("VERA_COARSE_PLACEMENT", raising=False)
    if request.param == "r7":
        monkeypatch.setenv("VERA_PLACEMENT", R7)
    else:
        monkeypatch.delenv("VERA_PLACEMENT", raising=False)
    return request.param


def reasons_of(out):
    return [r for u in out["unsupported"] for r in u["reasons"]]


@pytest.mark.parametrize("ident,text,reason", HITS, ids=[h[0] for h in HITS])
def test_b_the_six_hits_of_the_attack_are_abstentions_with_a_typed_reason(placement, ident, text, reason):
    out = SR.read(text, "ja")
    assert out["readable"] is False and out["clauses"] == [] and out["relations"] == []
    assert out["abstain"]["kind"] in ("not_supported",) and reason in reasons_of(out), json.dumps(out, ensure_ascii=False)
    other = ({"COORDINATION_UNDETERMINED", "DISJUNCTION_UNDETERMINED"} - {reason}).pop()
    assert other not in reasons_of(out)          # the two reasons are not mixed up


def test_b_a_question_goes_through_the_same_gate(placement):
    out = SR.read_question("太郎と花子が何を読んだ？", "ja")
    assert out["readable"] is False and "COORDINATION_UNDETERMINED" in reasons_of(out)
    out = SR.read_question("太郎か花子が何を買った？", "ja")
    assert out["readable"] is False and "DISJUNCTION_UNDETERMINED" in reasons_of(out)


@pytest.mark.parametrize("text", ["太郎と花子は手紙を読んだ。", "太郎と花子の本を読んだ。", "先生が太郎と次郎に本を渡した。", "本や雑誌を読んだ。", "犬と猫が庭を走った。",
                                  "兄や弟も旅に出た。", "兄と姉と妹が夕食を作った。"])
def test_b_a_particle_after_the_run_is_enough_not_only_a_case_particle(placement, text):
    assert SR.read(text, "ja")["readable"] is False and "COORDINATION_UNDETERMINED" in reasons_of(SR.read(text, "ja"))


# ---------------------------------------------------------------------------------------------------------------------------------
# what is not changed
# ---------------------------------------------------------------------------------------------------------------------------------
def test_b_a_companion_that_a_comma_separates_is_still_a_companion(placement):
    out = SR.read("太郎と、花子が来た。", "ja")
    assert out["readable"] is True and out["clauses"][0]["roles"] == {"agent": "花子", "companion": "太郎"}


def test_b_a_companion_that_is_not_adjacent_to_a_case_particle_is_still_a_companion(placement):
    out = SR.read("花子が太郎と話した。", "ja")
    assert out["readable"] is True and out["clauses"][0]["roles"] == {"agent": "花子", "companion": "太郎"}


def test_b_a_compound_particle_is_not_the_particle_of_the_gate(placement):
    out = SR.read("太郎と共に花子が来た。", "ja")
    assert "COORDINATION_UNDETERMINED" not in reasons_of(out) and "DISJUNCTION_UNDETERMINED" not in reasons_of(out)


@pytest.mark.parametrize("text", ["犬が来ると花子が泣いた。", "誰か来た。", "手紙を読むと眠くなった。", "雨だと思った。", "これは本ですか。"])
def test_b_to_ya_ka_that_do_not_follow_a_noun_and_lead_a_noun_run_do_not_fire(placement, text):
    out = SR.read(text, "ja")
    assert "COORDINATION_UNDETERMINED" not in reasons_of(out) and "DISJUNCTION_UNDETERMINED" not in reasons_of(out)


@pytest.mark.parametrize("text", ["Taro and Hanako read the letter.", "Taro or Hanako bought a book.", "The teacher gave the student a map."])
def test_b_english_is_not_touched(placement, text):
    out = SR.read(text, "en")
    assert "COORDINATION_UNDETERMINED" not in reasons_of(out) and "DISJUNCTION_UNDETERMINED" not in reasons_of(out)


def test_b_an_indefinite_ka_that_the_base_already_refuses_is_still_refused_for_the_base_reason(placement):
    # 何か本を読んだ: か follows a pronoun and leads a noun run. The base reader already refuses it as an interrogative source before any clause exists, so the gate has
    # no clause to mark and the reason stays the base one (decided after the first run: the frozen version of this test expected the gate's reason, a wrong guess about the base)
    out = SR.read("何か本を読んだ。", "ja")
    assert out["readable"] is False and reasons_of(out) == ["interrogative source does not assert a fact"]


def test_b_a_plain_sentence_is_read_as_before(placement):
    out = SR.read("先生が生徒に地図を渡した。", "ja")
    assert out["readable"] is True and out["clauses"][0]["roles"] == {"agent": "先生", "recipient": "生徒", "patient": "地図"}


# ---------------------------------------------------------------------------------------------------------------------------------
# the gate itself: the marks of the syntactic reading (gold_parallel) and no duplicates
# ---------------------------------------------------------------------------------------------------------------------------------
def _clause(rule, text="X", extra=()):
    span = Span("d", 0, len(text), text)
    return Clause("c0", Variable("e", "event"), "行く", span, (Role("agent", text, span, rule),), span, rule="gold_parallel", unsupported=tuple(extra))


def test_b_the_gate_reads_the_role_marks_of_the_syntactic_reading():
    assert R._coordination_gate(_clause("gold_parallel:choice")).unsupported == ("DISJUNCTION_UNDETERMINED",)
    assert R._coordination_gate(_clause("gold_parallel:parallel")).unsupported == ("COORDINATION_UNDETERMINED",)
    assert R._coordination_gate(_clause("gold_parallel:role")).unsupported == ()
    assert R._coordination_gate(_clause("frame")).unsupported == ()


def test_b_the_gate_does_not_repeat_a_reason_and_keeps_the_old_ones():
    once = R._coordination_gate(_clause("gold_parallel:choice", extra=("unrepresented source content",)))
    assert once.unsupported == ("unrepresented source content", "DISJUNCTION_UNDETERMINED")
    assert R._coordination_gate(once).unsupported == once.unsupported
    assert R._coordination_gate(replace(_clause("gold_parallel:parallel"), unsupported=("COORDINATION_UNDETERMINED",))).unsupported == ("COORDINATION_UNDETERMINED",)


def test_b_the_gate_does_not_stop_the_other_sentence_of_a_document():
    # the particle sits in the second sentence: the clause of the first one is not stopped
    text = "太郎が来た。次郎と花子が笑った。"
    view = R.document_view({"d": text})
    stopped = [c for c in view.clauses if "COORDINATION_UNDETERMINED" in c.unsupported]
    plain = [c for c in view.clauses if "COORDINATION_UNDETERMINED" not in c.unsupported]
    assert stopped and plain
    assert all("次郎と花子" in c.span.text for c in stopped) and all("次郎と花子" not in c.span.text for c in plain)


def test_b_the_marks_are_a_function_of_the_tokens_only():
    assert [m[2] for m in R._coordination_marks("太郎と花子が手紙を読んだ。")] == ["と"]            # (start, end, surface) of the particle token
    assert [m[2] for m in R._coordination_marks("本や雑誌を読んだ。")] == ["や"] and [m[2] for m in R._coordination_marks("太郎か花子が買った。")] == ["か"]
    assert R._coordination_marks("太郎と、花子が来た。") == []
    assert R._coordination_marks("太郎と共に花子が来た。") == []
    assert R._coordination_marks("English only, no particle.") == []
