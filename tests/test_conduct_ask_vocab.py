"""Q3: out-of-vocabulary terms through the closed LLM choice, with made-up providers only."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent / "conduct_ask"))
import ca_helpers as H  # noqa: E402
from ca_helpers import ask  # noqa: E402
from verantyx import conduct_ask  # noqa: E402
from verantyx.llm_choice import ChoiceLedger, LLMChooser, ProviderReply  # noqa: E402

Q = "備品の補修の依頼は範囲に含めますか？"
OPTS = ["含める", "含めない"]


@pytest.fixture(autouse=True)
def no_process(monkeypatch):
    def forbidden(*a, **k):
        raise AssertionError("a real provider process must never be started")
    monkeypatch.setattr(subprocess, "run", forbidden)
    monkeypatch.setattr(subprocess, "Popen", forbidden)


def script(tmp_path, **kw):
    p = tmp_path / "script.json"
    p.write_text(json.dumps(kw, ensure_ascii=False), encoding="utf-8")
    return str(p)


def run(tmp_path, q=Q, opts=OPTS, frame="f01_loan", **kw):
    return ask(frame, q, opts, vocab_llm="fake", vocab_fake=script(tmp_path, **kw))


def test_two_agreeing_answers_are_adopted_and_used_with_the_provenance_typed(tmp_path):
    res = run(tmp_path, pick="備品の修理依頼")
    assert res["decision"] == "answer" and res["answer"] == "含めない" and res["answer_option_index"] == 1
    v = res["vocab"]
    assert v["provenance"] == "LLM_TESTIMONY_MAPPING" and v["counts_as_evidence"] is False
    assert v["outcome"] == "ADOPTED" and v["frame_term"] == "備品の修理依頼" and v["ledger_decision_id"]
    assert v["question_term"] == "備品の補修の依頼" and "備品の修理依頼" in v["candidates"]
    assert [a["verdict"] for a in v["asks"]] == ["PICK", "PICK"]
    # the answer rests on the frame's own line; the testimony is not a basis record
    assert [b["id"] for b in res["basis"]] == ["D2"] and "LLM" not in json.dumps(res["basis"])


def test_two_different_answers_are_not_adopted(tmp_path):
    res = run(tmp_path, pick="備品の修理依頼", pick2="返却の延長")
    assert res["decision"] == "escalate" and res["escalate_reason"] == "VOCAB_UNMAPPED"
    assert res["escalate_detail"] == "LLM_ABSTAINED:DISAGREE" and res["answer"] is None
    assert res["vocab"]["outcome"] == "ABSTAINED:DISAGREE" and res["vocab"]["frame_term"] is None


def test_none_of_them_is_close_is_an_abstention(tmp_path):
    res = run(tmp_path, pick=None)
    assert res["escalate_reason"] == "VOCAB_UNMAPPED" and res["escalate_detail"] == "LLM_ABSTAINED:NONE_SELECTED"
    assert res["vocab"]["outcome"] == "ABSTAINED:NONE_SELECTED"


def test_a_pick_that_is_not_a_candidate_is_an_abstention_too(tmp_path):
    res = run(tmp_path, pick="貸出画面")        # a frame term, but not a scope condition
    assert res["decision"] == "escalate" and res["escalate_detail"].startswith("LLM_ABSTAINED")


def test_a_provider_failure_is_typed_and_never_an_answer(tmp_path):
    res = run(tmp_path, fail="TIMEOUT")
    assert res["decision"] == "escalate" and res["escalate_reason"] == "VOCAB_UNMAPPED"
    assert res["escalate_detail"] == "LLM_FAILED:TIMEOUT" and res["vocab"]["outcome"].startswith("FAILED")


def test_off_always_hands_the_question_up_and_builds_nothing(monkeypatch):
    def boom(*a, **k):
        raise AssertionError("no provider may be built when the mode is off")
    monkeypatch.setattr(conduct_ask, "make_chooser", boom)
    monkeypatch.setattr(conduct_ask, "CodexProvider", boom)
    monkeypatch.setattr(conduct_ask, "ClaudeProvider", boom)
    res = ask("f01_loan", Q, OPTS)
    assert res["escalate_reason"] == "VOCAB_UNMAPPED" and res["escalate_detail"] == "VOCAB_LLM_OFF"
    assert res["vocab"]["outcome"] == "OFF" and res["vocab"]["frame_term"] is None


def test_a_real_mode_builds_its_provider_only_when_a_term_is_out_of_vocabulary(monkeypatch):
    built = []

    def spy(mode, fake, ledger):
        built.append(mode)
        return None
    monkeypatch.setattr(conduct_ask, "make_chooser", spy)
    ask("f01_loan", "返却の延長は範囲に含めますか？", OPTS, vocab_llm="codex")     # in the vocabulary
    assert built == []
    ask("f01_loan", Q, OPTS, vocab_llm="codex")
    assert built == ["codex"]


def test_an_adopted_mapping_is_resolved_by_the_same_rules(tmp_path):
    # the term maps to a forbidden operation: the answer is "no", with the forbidden record as the basis
    res = ask("f01_loan", "予約の記録を消去してよいですか？", H.YN_JA,
              vocab_llm="fake", vocab_fake=script(tmp_path, pick="予約記録を削除する"))
    assert res["decision"] == "answer" and res["answer"] == "いいえ"
    assert res["basis"][0]["section"] == "forbidden_actions" and res["vocab"]["outcome"] == "ADOPTED"
    # a mapping onto a protected action still goes to a human
    res = ask("f01_loan", "住民のアドレスを外に出してよいですか？", H.YN_JA, vocab_llm="fake",
              vocab_fake=script(tmp_path, pick="住民の連絡先を公開する"))
    assert res["escalate_reason"] == "HUMAN_APPROVAL_REQUIRED"


def test_an_adopted_mapping_that_the_frame_cannot_use_is_still_handed_up(tmp_path):
    # mapped to a scope condition whose value conflicts: the rerun finds the conflict
    res = ask("f07_expense", "立替払いの精算は範囲に含めますか？", OPTS, vocab_llm="fake",
              vocab_fake=script(tmp_path, pick="立替金の精算"))
    assert res["escalate_reason"] == "FRAME_CONFLICT" and res["vocab"]["outcome"] == "ADOPTED"


def test_a_narrower_or_wider_term_is_not_mapped_by_testimony(tmp_path):
    res = ask("f04_stall", "価格の自動計算の見積りは範囲に含めますか？", OPTS, vocab_llm="fake",
              vocab_fake=script(tmp_path, pick="価格の自動計算"))
    assert res["decision"] == "escalate"        # contains the frame term: a wider phrase, never mapped


def test_too_many_candidates_is_a_typed_refusal(tmp_path):
    extra = "".join(f"D{n}: SCOPE | 項目{chr(0x3042 + n)}ぬ | in scope\n" for n in range(20, 40))
    base = (H.FRAMES / "f04_stall.md").read_text(encoding="utf-8").replace("[vocabulary_aliases]", extra + "\n[vocabulary_aliases]")
    p = tmp_path / "many.md"
    p.write_text(base, encoding="utf-8")
    res = ask(str(p), "料金の自動計算は範囲に含めますか？", OPTS, vocab_llm="fake", vocab_fake=script(tmp_path, pick="価格の自動計算"))
    assert res["escalate_reason"] == "VOCAB_UNMAPPED" and res["escalate_detail"] == "LLM_REFUSED:TOO_MANY_CANDIDATES"


def test_a_question_without_a_readable_role_or_single_term_is_not_sent_to_a_model(tmp_path):
    asked = []

    class Spy:
        def ask(self, prompt):
            asked.append(prompt)
            return ProviderReply.success('{"choice": null}')
    chooser = LLMChooser(Spy(), ChoiceLedger(None))
    res = ask("f01_loan", "ところで今日の天気はどうですか", None, vocab_llm="fake", chooser=chooser)
    assert res["escalate_reason"] == "VOCAB_UNMAPPED" and res["escalate_detail"] == "NO_ROLE" and asked == []
    res = ask("f01_loan", "補修の依頼と貸出の上限は範囲に含めますか？ 含めない？", OPTS, vocab_llm="fake", chooser=chooser)
    assert asked == [] and res["decision"] == "escalate"


def test_an_injected_chooser_is_used_and_a_reused_decision_is_not_asked_twice(tmp_path):
    asked = []

    class Provider:
        def ask(self, prompt):
            asked.append(prompt)
            lines = [ln for ln in prompt.splitlines() if ln[:1].isdigit() and ": {" in ln]
            n = next(int(ln.split(":", 1)[0]) for ln in lines if "備品の修理依頼" in ln)
            return ProviderReply.success(json.dumps({"choice": n}))
    chooser = LLMChooser(Provider(), ChoiceLedger(None))
    first = ask("f01_loan", Q, OPTS, vocab_llm="fake", chooser=chooser)
    n_first = len(asked)
    second = ask("f01_loan", Q, OPTS, vocab_llm="fake", chooser=chooser)
    assert first["answer"] == second["answer"] == "含めない" and n_first == 2 and len(asked) == 2
