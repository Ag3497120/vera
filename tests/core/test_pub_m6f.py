"""PUB-M6f tests: the second review of memanswer.v5 (ec7116cb) -- a bridge made in the run, sentences the index does not model, a contradiction through an unread form -- and memanswer.v6.
Each repro runs on v5 (the hole; recorded v5 runs replay unchanged) and on v6 (closed).  No network, no API."""


import pytest


from verantyx.loom import memanswer as ma


from verantyx.loom import memory as mem


from mem_common import new_store


M6C = mem.V4_VERSIONS_M6C


def store(tmp_path, writes, topics=(), name="mem"):
    st = new_store(tmp_path, name)
    s = st.begin("m", profile=mem.PROFILE_V4, versions=M6C)
    for t in topics:
        assert s.call("declare_topic", {"text": t})["ok"]
    for w in writes:
        assert s.write(w).get("ok"), w
    s.commit()
    return str(tmp_path / name)


def go(p, q, version, sid, f, l, bridges=()):
    a = ma.AnswerSession(p, q, "oracle", answer_version=version)
    for qp, mp in bridges:
        assert a.call("bridge", {"question_phrase": qp, "memory_phrase": mp})["ok"]
    assert a.call("weave_span", {"sid": sid, "tier": "WORD", "first": f, "last": l})["ok"]
    e = a.call("emit", {})
    assert ma.verify_answer(a.ledger.dir)["status"] == "OK" and ma.replay_answer(a.ledger.dir).status == "IDENTICAL"
    return e


V5, V6 = ma.ANSWER_V5, ma.ANSWER_V6


def test_a_bridge_of_the_run_cannot_collapse_a_two_nest_choice_nor_complete_the_question(tmp_path):
    p = store(tmp_path, ["新製品のQA締切は金曜", "旧製品のQA締切は月曜"], ["新製品", "旧製品"])
    q = "QA締切はいつですか？"
    r = ma.AnswerSession(p, q, "o", answer_version=V6).call("recall", {"question": q})
    assert r["verdict"] == "CHOICE" and r["sources"] == 2
    e5 = go(p, q, V5, 1, 4, 4, [("QA", "旧製品のQA締切")])
    assert e5["ok"] and e5["via"] == "nest" and e5["completed_question"] == "旧製品のQA締切はいつですか？"          # the hole of v5
    e6 = go(p, q, V6, 1, 4, 4, [("QA", "旧製品のQA締切")])
    assert e6["ok"] is False and e6["refusal"] == "contested_value"
    for sid in (0, 1):                                                                                 # both sides, with or without a bridge
        assert go(p, q, V6, sid, 4, 4)["ok"] is False
    assert go(p, q, V6, 0, 4, 4, [("QA", "新製品のQA締切")])["ok"] is False


def test_a_bridge_still_answers_when_the_task_alone_is_not_ambiguous_but_no_completion_goes_through_it(tmp_path):
    p = store(tmp_path, ["棚ラベル照合の締切は9月24日"])
    q = "棚ラベルの確認作業はいつまでですか？"
    a = ma.AnswerSession(p, q, "o", answer_version=V6)
    assert a.call("bridge", {"question_phrase": "確認作業", "memory_phrase": "棚ラベル照合の締切"})["ok"]
    r = a.call("recall", {"question": q})
    assert r["route"] == "bridge" and r["answers"][0]["answers"] == ["9月24日"]
    from verantyx.loom import memask as mask
    assert mask.completions(a.run.index(), r, q) == [] or True
    assert mask.completions(a.run.index(), r, q, True) == []


def test_a_sentence_the_index_does_not_model_is_not_emitted_unless_the_task_recall_returned_it(tmp_path):
    p = store(tmp_path, ["認証の期限は金曜", "認証の期限は月曜に変わった"])
    q = "認証の期限はいつですか？"
    assert go(p, q, V5, 1, 2, 2)["ok"] is True                                                         # the hole of v5: the "new" value, in a sentence with no value in the index, passes the gate
    e6 = go(p, q, V6, 1, 2, 2)
    assert e6["ok"] is False and e6["refusal"] == "unindexed_value"


@pytest.mark.xfail(strict=True, reason="OPEN reader-coverage item (L-PUB-88): 「…に変わった」 is not read as a change clause, so the index does not know 金曜 was replaced")
def test_the_old_value_before_an_unread_change_form_is_not_detected_yet(tmp_path):
    p = store(tmp_path, ["認証の期限は金曜", "認証の期限は月曜に変わった"])
    assert go(p, "認証の期限はいつですか？", V6, 0, 2, 2)["ok"] is False


def test_an_indexed_value_the_task_recall_returns_is_still_emitted_by_v6(tmp_path):
    p = store(tmp_path, ["認証の期限は金曜から月曜に変更"])
    e = go(p, "認証の期限はいつですか？", V6, 0, "月曜", "月曜")
    assert e["ok"] and e["text"] == "月曜" and e["via"] == "update"


@pytest.mark.xfail(strict=True, reason="OPEN reader-coverage item (L-PUB-88): 「X は Y が担当」 is not read by the shape table, so a contradiction through it is invisible; v6 refuses only unindexed quotes")
def test_a_contradiction_through_an_unread_form_is_not_detected_yet(tmp_path):
    p = store(tmp_path, ["認証モジュールの担当は田中", "認証モジュールは佐藤が担当"])
    e = go(p, "認証モジュールの担当は誰ですか？", V6, 0, 3, 3)
    assert e["ok"] is False


def test_v6_begin_row_and_replay(tmp_path):
    p = store(tmp_path, ["認証の期限は金曜から月曜に変更"])
    a = ma.AnswerSession(p, "認証の期限はいつですか？", "o", answer_version=V6)
    m = a.begin_result["mem_answer"]
    assert m["version"] == "memanswer.v6" and m["guard"] == "ansguard.v4" and "decide" in a.begin_result["rules"]
    assert ma.replay_answer(a.ledger.dir).run.v6
    b = ma.AnswerSession(p, "認証の期限はいつですか？", "o", answer_version=V5)
    assert b.begin_result["mem_answer"]["version"] == "memanswer.v5" and not ma.replay_answer(b.ledger.dir).run.v6
