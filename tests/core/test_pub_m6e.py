"""PUB-M6e tests: the three emit-safety bypasses the review of a6970cd3..67fe932f found, and memanswer.v5 that closes them.  What may be emitted is decided from the INDEX and the run's TASK QUESTION;
what the model happened to recall (or not) decides nothing.  Each case is run on memanswer.v4 too, to show the hole it had (recorded v4 runs are unchanged) and on memanswer.v5 to show it closed.
No network, no API."""


import json


import os


import pytest


from verantyx.loom import memanswer as ma


from verantyx.loom import memory as mem


from mem_common import new_store


V4 = mem.PROFILE_V4


M6C = mem.V4_VERSIONS_M6C


def store(tmp_path, writes, topics=(), name="mem"):
    st = new_store(tmp_path, name)
    s = st.begin("m", profile=V4, versions=M6C)
    for t in topics:
        assert s.call("declare_topic", {"text": t})["ok"]
    for w in writes:
        assert s.write(w).get("ok"), w
    s.commit()
    return str(tmp_path / name)


def run(p, q, version):
    return ma.AnswerSession(p, q, "oracle", answer_version=version)


def occ(p, q, group=0, hist=False, version=ma.ANSWER_V5):
    r = run(p, q, version).call("recall", {"question": q})
    return (r["history"] if hist else r["answers"])[group]["occurrences"][0]


def wv(a, o):
    return a.call("weave_span", {"sid": o["sid"], "tier": "WORD", "first": o["span"][0], "last": o["span"][1]})


VERSIONS = [ma.ANSWER_V4, ma.ANSWER_V5]


def test_a_completion_found_by_a_recall_of_another_question_is_not_judged_instead_of_the_task(tmp_path):
    p = store(tmp_path, ["認証の期限は金曜から月曜に変更", "新製品の発売日は火曜"])
    task = "新製品の発売日はいつですか？"
    res = {}
    for v in VERSIONS:
        a = run(p, task, v)
        o = a.call("recall", {"question": "認証の期限はいつですか？"})["answers"][0]["occurrences"][0]
        assert wv(a, o)["ok"]
        res[v] = a.call("emit", {})
        assert ma.verify_answer(a.ledger.dir)["status"] == "OK" and ma.replay_answer(a.ledger.dir).status == "IDENTICAL"
    assert res[ma.ANSWER_V4]["ok"] and res[ma.ANSWER_V4]["via"] == "update"                       # the hole: 月曜 is emitted as the answer to the launch date (recorded v4 runs replay as they were)
    e = res[ma.ANSWER_V5]
    assert e["ok"] is False and e["refusal"] == "no_evidence" and "completion" not in e["detail"]


def test_a_completion_is_computed_from_the_task_question_only_a_change_at_another_position_gets_none(tmp_path):
    p = store(tmp_path, ["認証の期限は金曜から月曜に変更", "発送の期限は火曜から水曜に変更"])
    a = run(p, "認証の期限はいつですか？", ma.ANSWER_V5)
    o = a.call("recall", {"question": "発送の期限はいつですか？"})["answers"][0]["occurrences"][0]
    assert o["answer"] == "水曜" and wv(a, o)["ok"]
    assert a.call("emit", {})["ok"] is False
    b = run(p, "認証の期限はいつですか？", ma.ANSWER_V5)                                            # the task's own position: still completed (via: update), with or without a recall
    assert wv(b, occ(p, "認証の期限はいつですか？"))["ok"]
    e = b.call("emit", {})
    assert e["ok"] and e["text"] == "月曜" and e["via"] == "update" and e["completed_question"] == "変更は何に変更"
    assert ma.verify_answer(b.ledger.dir)["status"] == "OK" and ma.replay_answer(b.ledger.dir).status == "IDENTICAL"


def test_a_nest_completion_needs_the_task_question_not_the_recalled_one(tmp_path):
    p = store(tmp_path, ["新製品のQA締切は金曜", "新製品のリリース日は月曜"], topics=["新製品"])
    task = "QA締切はいつですか？"
    a = run(p, task, ma.ANSWER_V5)                                                                  # the legitimate case: the task question is completed by the nest the store holds
    assert wv(a, occ(p, task))["ok"]
    e = a.call("emit", {})
    assert e["ok"] and e["text"] == "金曜" and e["via"] == "nest" and e["completed_question"] == "新製品のQA締切はいつですか？"
    out = {}
    for v in VERSIONS:
        b = run(p, task, v)
        o = b.call("recall", {"question": "リリース日はいつですか？"})["answers"][0]["occurrences"][0]
        assert o["answer"] == "月曜" and wv(b, o)["ok"]
        out[v] = b.call("emit", {})
    assert out[ma.ANSWER_V4]["ok"] and out[ma.ANSWER_V4]["via"] == "nest"                           # the hole: the launch day emitted as the QA deadline
    assert out[ma.ANSWER_V5]["ok"] is False and out[ma.ANSWER_V5]["refusal"] == "no_evidence"


def test_the_v5_run_ignores_the_completions_its_recalls_stored(tmp_path):
    p = store(tmp_path, ["認証の期限は金曜から月曜に変更", "新製品の発売日は火曜"])
    a = run(p, "新製品の発売日はいつですか？", ma.ANSWER_V5)
    a.call("recall", {"question": "認証の期限はいつですか？"})
    assert a.run.completions                                                                        # the recall still notes them (the record of what was seen) ...
    assert wv(a, occ(p, "認証の期限はいつですか？"))["ok"] and a.call("emit", {})["ok"] is False        # ... and emit does not read them


def test_one_side_of_a_contradiction_cannot_be_emitted_without_any_recall(tmp_path):
    p = store(tmp_path, ["認証モジュールの担当は田中", "認証モジュールの担当は佐藤"])
    q = "認証モジュールの担当は誰ですか？"
    o = occ(p, q)
    assert o["answer"] == "田中"
    for v, ok in ((ma.ANSWER_V4, True), (ma.ANSWER_V5, False)):
        a = run(p, q, v)
        assert wv(a, o)["ok"]                                                                       # no recall at all
        e = a.call("emit", {})
        assert e["ok"] is ok and (ok or e["refusal"] == "contested_value")
    a = run(p, q, ma.ANSWER_V5)
    assert wv(a, occ(p, q, 1))["ok"] and a.call("emit", {})["refusal"] == "contested_value"        # the other side too
    assert a.call("abstain", {"type": "contested"})["ok"] and ma.verify_answer(a.ledger.dir)["status"] == "OK"


def test_laundering_a_contested_value_through_a_recall_of_another_question(tmp_path):
    p = store(tmp_path, ["認証モジュールの担当は田中", "認証モジュールの担当は佐藤", "経理部の担当は田中"])
    q = "認証モジュールの担当は誰ですか？"
    res = {}
    for v in VERSIONS:
        a = run(p, q, v)
        r = a.call("recall", {"question": "経理部の担当は誰ですか？"})                                  # 田中 ALONE: a v4 run now believes 田中 is not contested
        assert r["verdict"] == "ANSWER" and r["answers"][0]["answers"] == ["田中"]
        assert wv(a, occ(p, q))["ok"]                                                               # sid 0, the contested 田中
        res[v] = a.call("emit", {})
    assert res[ma.ANSWER_V4]["ok"] is True                                                           # the hole
    assert res[ma.ANSWER_V5]["ok"] is False and res[ma.ANSWER_V5]["refusal"] == "contested_value"
    b = run(p, "経理部の担当は誰ですか？", ma.ANSWER_V5)                                               # the uncontested one is still emitted
    assert wv(b, occ(p, "経理部の担当は誰ですか？"))["ok"] and b.call("emit", {})["text"] == "田中"


def test_a_contradiction_of_an_event_is_decided_from_the_task_question(tmp_path):
    p = store(tmp_path, ["会議は東京で行う", "会議は大阪で行う"])
    q = "会議はどこで行いますか？"
    r = run(p, q, ma.ANSWER_V5).call("recall", {"question": q})
    assert r["verdict"] == "CHOICE" and r["choice_kind"] == "same_seat" and r["route"] == "event"
    a = run(p, q, ma.ANSWER_V5)
    assert wv(a, r["answers"][0]["occurrences"][0])["ok"]
    assert a.call("emit", {})["refusal"] == "contested_value"


def test_a_repeated_value_and_an_enumeration_are_not_contested(tmp_path):
    p = store(tmp_path, ["認証モジュールの担当は田中", "認証モジュールの担当は田中"])
    q = "認証モジュールの担当は誰ですか？"
    a = run(p, q, ma.ANSWER_V5)
    assert wv(a, occ(p, q))["ok"] and a.call("emit", {})["text"] == "田中"


def test_a_replaced_value_cannot_be_woven_without_any_recall(tmp_path):
    p = store(tmp_path, ["認証の期限は金曜", "認証の期限は金曜から月曜に変更"])
    q = "認証の期限はいつですか？"
    old = occ(p, q, 0, hist=True)
    assert old["answer"] == "金曜" and old["sid"] == 0
    a = run(p, q, ma.ANSWER_V4)
    assert wv(a, old)["ok"] and a.call("emit", {})["text"] == "金曜"                                   # the hole in v4: the old value, no recall
    b = run(p, q, ma.ANSWER_V5)
    w = wv(b, old)
    assert w["ok"] is False and w["refusal"] == "replaced_value" and b.run.state.thread == []
    w = b.call("weave_span", {"sid": 1, "tier": "WORD", "first": "金曜", "last": "金曜"})              # the old value named inside the change sentence
    assert w["ok"] is False and w["refusal"] == "replaced_value"
    assert wv(b, occ(p, q))["ok"] and b.call("emit", {})["text"] == "月曜"


def test_a_replaced_value_is_not_laundered_by_a_live_value_of_another_position(tmp_path):
    p = store(tmp_path, ["認証の期限は金曜", "認証の期限は金曜から月曜に変更", "発送の期限は金曜"])
    q = "認証の期限はいつですか？"
    old = occ(p, q, 0, hist=True)
    a = run(p, q, ma.ANSWER_V5)
    assert a.call("recall", {"question": "発送の期限はいつですか？"})["answers"][0]["answers"] == ["金曜"]     # 金曜 is live elsewhere
    assert wv(a, old)["refusal"] == "replaced_value"


def test_a_value_that_is_live_again_a_superseded_sentence_and_a_value_of_another_position_are_still_judged_right(tmp_path):
    p = store(tmp_path, ["認証の期限は金曜", "認証の期限は金曜から月曜に変更", "認証の期限は金曜に変更"])
    q = "認証の期限はいつですか？"
    a = run(p, q, ma.ANSWER_V5)
    o = a.call("recall", {"question": q})["answers"][0]["occurrences"][0]
    assert o["answer"] == "金曜" and wv(a, o)["ok"]                                                    # restated: live again
    p2 = store(tmp_path, ["認証の期限は金曜", "認証の期限は月曜"], name="sup")
    st = new_store(tmp_path, "sup")
    s = st.begin("m", profile=V4, versions=M6C)
    assert s.call("supersede", {"new_sid": 1, "old_sid": 0, "reason": "変更"})["ok"]
    s.commit()
    b = run(p2, q, ma.ANSWER_V5)
    assert b.call("weave_span", {"sid": 0, "tier": "WORD", "first": 2, "last": 2})["refusal"] == "superseded_sentence"
    assert wv(b, occ(p2, q))["ok"] and b.call("emit", {})["text"] == "月曜"


def test_memanswer_v5_is_recorded_in_the_begin_row_and_replays(tmp_path):
    p = store(tmp_path, ["認証の期限は金曜から月曜に変更"])
    a = run(p, "認証の期限はいつですか？", ma.ANSWER_V5)
    b = a.begin_result
    assert b["mem_answer"]["version"] == "memanswer.v5" and b["mem_answer"]["guard"] == "ansguard.v3" and "decide" in b["rules"] and list(b["tools"]) == list(ma.ANSWER_TOOLS_V4)
    assert wv(a, occ(p, "認証の期限はいつですか？"))["ok"] and a.call("emit", {})["ok"]
    assert ma.verify_answer(a.ledger.dir)["status"] == "OK"
    rep = ma.replay_answer(a.ledger.dir)
    assert rep.status == "IDENTICAL" and rep.run.v5 and rep.run.v4
    v4 = run(p, "認証の期限はいつですか？", ma.ANSWER_V4)
    assert v4.begin_result["mem_answer"]["version"] == "memanswer.v4" and v4.begin_result["mem_answer"]["guard"] == "ansguard.v2" and "decide" not in v4.begin_result["rules"]
    assert ma.replay_answer(v4.ledger.dir).status == "IDENTICAL" and not ma.replay_answer(v4.ledger.dir).run.v5


def test_a_recall_less_ledger_is_just_weave_and_emit(tmp_path):
    p = store(tmp_path, ["認証の期限は金曜から月曜に変更"])
    a = run(p, "認証の期限はいつですか？", ma.ANSWER_V5)
    a.call("weave_span", {"sid": 0, "tier": "WORD", "first": "月曜", "last": "月曜"})
    e = a.call("emit", {})
    assert e["ok"] and e["via"] == "update"
    rows = [json.loads(ln) for ln in open(os.path.join(a.ledger.dir, "ops.jsonl"), encoding="utf-8")]
    assert [r["op"] for r in rows if r["actor"] == "model"] == ["begin", "weave_span", "emit"]


def test_verify_and_replay_default_to_the_recorded_hook_and_the_old_default_is_reachable(tmp_path):
    st = new_store(tmp_path, "latest")
    s = st.begin("m", self_question=mem.LATEST)
    s.write("田中の担当は認証")
    s.commit()
    assert st.verify()["status"] == "OK" and st.replay().identical and mem.verify_store(str(tmp_path / "latest"))["status"] == "OK"
    assert mem.main(["verify", "--store", str(tmp_path / "latest")]) == 0
    assert st.replay(mem.DEFAULT).status == "INPUTS" and mem.main(["replay", "--store", str(tmp_path / "latest"), "--hook", "default"]) == 2
