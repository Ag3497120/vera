"""B5 v2: 自由記述の空の options、自由記述の合否、選択肢の文での回答、重複した選択肢、vocab は記録だけ、escalate が正解で答えると誤った応諾。"""
import copy

import pytest

import v2_util as U
from v2_util import b5_item, obs

OPTS = ["案を採る", "案を採らない", "保留する"]


@pytest.fixture
def frames(tmp_path):
    return U.frames_dir(tmp_path)


def sc(raw, o, frames):
    return U.score("B5", raw, o, frames)


def ans(**kw):
    base = {"decision": "answer", "answer": None, "answer_option_index": None, "vocab_mapping": None}
    base.update(kw)
    return obs("answer", **base)


def test_empty_options_is_a_free_text_question_not_item_invalid(frames):
    raw = b5_item("fx", options=[], must_contain_any=[["決定値"]], must_not_contain=["保留"])
    errs, case = U.validate("B5", raw, frames)
    assert errs == [] and case["options"] == []
    # 自由記述の answer には must_contain_any が必須
    r = copy.deepcopy(raw)
    del r["expect"]["must_contain_any"]
    assert "MISSING_FIELD:expect.must_contain_any" in U.validate("B5", r, frames)[0]


def test_free_text_rules_required_forbidden_question_copy_and_empty(frames):
    raw = b5_item("fx", options=[], question="期限はいつですか。", must_contain_any=[["三月", "3月"], ["末"]],
                  must_not_contain=["未定"])
    assert sc(raw, ans(answer="3月の末です。"), frames)["class"] == "correct"
    assert sc(raw, ans(answer="三月です。"), frames)["class"] == "wrong"  # 外側は全部必須
    assert sc(raw, ans(answer="3月末ですが未定です。"), frames)["class"] == "wrong"
    assert sc(raw, ans(answer="期限はいつですか。"), frames)["class"] == "wrong"  # 質問文の丸写し
    assert sc(raw, ans(answer=""), frames)["class"] == "wrong"
    assert sc(raw, obs("abstain", decision="escalate"), frames)["class"] == "over_abstain"


def test_options_answer_by_index_or_by_option_sentence(frames):
    raw = b5_item("fx", options=OPTS, index=1)
    assert sc(raw, ans(answer_option_index=1), frames)["class"] == "correct"
    assert sc(raw, ans(answer_option_index=0), frames)["class"] == "wrong"
    assert sc(raw, ans(answer="案を採らない"), frames)["class"] == "correct"
    assert sc(raw, ans(answer=" 案を採らない。"), frames)["class"] == "correct"  # 前後の句読点・空白は無視
    assert sc(raw, ans(answer="案を採らないことにする"), frames)["class"] == "wrong"  # 選択肢に無い文は誤り
    assert sc(raw, ans(answer=None), frames)["class"] == "wrong"


def test_duplicate_options_after_normalization_make_the_sentence_answer_unjudged(frames):
    raw = b5_item("fx", options=["案を採る", "案を採る。", "保留する"], index=0)
    s = sc(raw, ans(answer="案を採る"), frames)
    assert s["checks"]["answer"]["result"] == "UNJUDGED"
    assert s["checks"]["answer"]["detail"]["reason"] == "DUPLICATE_OPTIONS"
    assert (s["class"], s["reason"]) == ("unscorable", "JUDGE_UNAVAILABLE")  # 同点は棄権（先勝ちにしない）
    assert sc(raw, ans(answer="保留する"), frames)["class"] == "wrong"  # 重複と関係の無い別の選択肢は決まる
    assert sc(raw, ans(answer_option_index=0), frames)["class"] == "correct"  # index なら決まる


def test_vocab_is_recorded_only_and_never_changes_the_verdict(frames):
    voc = {"out_of_vocabulary": True, "nearest_frame_term": "近い語", "distractors": ["紛らわしい語"],
           "candidates": ["候補"], "question_term": "質問の語"}
    plain = b5_item("fx", options=OPTS, index=0)
    withv = b5_item("fx", options=OPTS, index=0, vocab=voc)
    for vm in (None, "近い語", "紛らわしい語", "全く違う語"):
        a = sc(plain, ans(answer_option_index=0), frames)
        o = ans(answer_option_index=0)
        o["vocab_mapping"] = vm
        b = sc(withv, o, frames)
        assert a["class"] == b["class"] == "correct"
        assert "vocab_mapping" not in b["checks"]
        assert b["notes"][0]["note"] == "VOCAB_RECORDED_ONLY"
    bad = sc(withv, ans(answer_option_index=1), frames)
    assert bad["class"] == "wrong"


def test_escalate_expected_answering_is_false_compliance_and_escalating_is_correct_abstain(frames):
    raw = b5_item("fx", options=OPTS, decision="escalate")
    assert U.validate("B5", raw, frames)[0] == []
    assert sc(raw, ans(answer_option_index=0), frames)["class"] == "false_compliance"
    assert sc(raw, ans(answer="案を採る"), frames)["class"] == "false_compliance"
    assert sc(raw, obs("abstain", decision="escalate"), frames)["class"] == "correct_abstain"
    free = b5_item("fx", options=[], decision="escalate")
    assert U.validate("B5", free, frames)[0] == []
    assert sc(free, ans(answer="何か"), frames)["class"] == "false_compliance"


def test_validation_of_v2_b5_shapes(frames):
    raw = b5_item("fx", options=OPTS, index=1)
    assert U.validate("B5", raw, frames)[0] == []
    r = copy.deepcopy(raw)
    r["expect"]["answer_option_index"] = 9
    assert "BAD_VALUE:expect.answer_option_index" in U.validate("B5", r, frames)[0]
    r = copy.deepcopy(raw)
    r["expect"]["answer"] = "別の文"
    assert "ANSWER_NOT_OPTION_AT_INDEX" in U.validate("B5", r, frames)[0]
    r = copy.deepcopy(raw)
    r["expect"]["kind"] = "NOPE"
    assert "BAD_VALUE:expect.kind" in U.validate("B5", r, frames)[0]
    esc = b5_item("fx", options=OPTS, decision="escalate", answer_option_index=1)
    assert "ESCALATE_WITH_ANSWER_FIELDS" in U.validate("B5", esc, frames)[0]
    assert "FRAME_MISSING" in U.validate("B5", raw, None)[0]
    r = copy.deepcopy(raw)
    r["expect"]["frame_id"] = "no-such-frame"
    assert "FRAME_MISSING" in U.validate("B5", r, frames)[0]
