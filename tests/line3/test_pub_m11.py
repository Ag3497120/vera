"""PUB-M11 tests: (1) the safety probes of the update / replaced-value rounds written back as regression tests on the memanswer.v16 / v17 / v18 answer path (the scratchpad probe files r11p-r14p and
h8/probes were lost): a replaced, contested, corrected, hedged, mismatched-old or model-superseded value is never emitted, and the right new value still is; (2) the revision cycle of the meter v2,
arms.v2: verbatim whole-sentence writes for A3 / A3f, topics from the story's own words, the arm A1v (the harness fills the log), the load pause and the token cap.  No network, no API."""
import json
import os
import sys

import pytest

from verantyx.loom import memanswer as ma
from verantyx.loom import memory as mem
from mem_common import ROOT
from test_pub_m6g import attack, store, store_sessions

METER2 = os.path.join(ROOT, "experiments", "line3", "pub", "meter2")
if METER2 not in sys.path:
    sys.path.insert(0, METER2)

Q = "認証の期限は何日ですか？"
LATE = (ma.ANSWER_V16, ma.ANSWER_V17, ma.ANSWER_V18)


def _emits(p, n, v):
    return sorted({t for (_s, t, _v) in attack(p, Q, n, version=v)})


# (writes, allowed emits): what may come out of ANY span of ANY sentence woven and emitted
CASES = [
    (["認証の期限は3日だ", "認証の期限は5日に変更"], {"5日"}),                                  # replaced: 3日 never, the new value yes
    (["認証の期限は3日だ", "認証の期限を3日から5日に変更"], {"5日"}),
    (["認証の期限は3日だ", "認証の期限を3日から5日に変更", "認証の期限を5日から7日に変更"], {"7日"}),
    (["認証の期限は3日だ", "認証の期限は4日だ"], set()),                                          # contested
    (["認証の期限は3日だ", "認証の期限は4日だ", "認証の期限を3日から5日に変更"], set()),            # a change replaces only the side it names: 4日 / 5日 contested
    (["認証の期限は5日、正しくは7日"], set()),                                                    # a correction inside one write
    (["誤：認証の期限は5日"], set()),                                                              # a label
    (["認証の期限は約5日"], set()),                                                                # a qualifier
    (["認証の期限は5日にしたい"], set()),                                                          # a wish
    (["認証の期限は3日だ", "認証の期限を4日から5日に変更"], set()),                              # a mismatched old value: nothing is replaced, nothing is asserted
    (["認証の期限は3日だ", "認証の期限を次回3日から5日に変更"], set()),                          # a non-value as the old seat
    (["認証の期限は5日に変更し忘れた"], set()),                                                    # an event, not a change
    (["認証の期限は3日だ、納品は4日だ"], set()),                                                  # a multi-clause write is evidence, not an answer
]


@pytest.mark.parametrize("v", LATE)
@pytest.mark.parametrize("writes,allowed", CASES)
def test_replaced_contested_and_unclean_values_are_never_emitted(tmp_path, v, writes, allowed):
    p = store(tmp_path, writes, name="c")
    got = set(_emits(p, len(writes), v))
    if v == ma.ANSWER_V16 and len(writes) == 3 and "3日から5日" in writes[2] and "4日" in writes[1]:
        allowed = {"5日"}                                  # v16 replaced both sides with 5日; v17 (L-PUB-118) replaces only the side the change names (replays as it was)
    assert got <= allowed, (writes, v, got)
    if allowed:
        assert got == allowed, (writes, v, got)


@pytest.mark.parametrize("v", LATE)
def test_a_value_replaced_by_the_models_own_supersede_is_history_never_an_answer(tmp_path, v):
    st = store(tmp_path, ["認証の期限は3日だ", "認証の期限は5日だ"], name="sup")           # a contested pair, then the model resolves it in a later session
    from mem_common import new_store
    s = mem.MemStore(st).begin("m", profile=mem.PROFILE_V4, versions=mem.V4_VERSIONS_M6C)
    r = s.call("supersede", {"new_sid": 1, "reason": "変更", "old_sid": 0})
    assert r.get("ok"), r
    s.commit()
    got = {t for (_s, t, _v) in attack(st, Q, 2, version=v)}
    assert "3日" not in got, got
    r = ma.AnswerSession(st, Q, "o", answer_version=v).call("recall", {"question": Q})
    assert "3日" not in [a for g in r["answers"] for a in g["answers"]]


@pytest.mark.parametrize("v", LATE)
def test_distinct_nests_never_replace_each_other(tmp_path, v):
    for t1, t2 in (("旧製品", "新製品"), ("製品Aの開発", "製品Bの開発")):
        p = store_sessions(tmp_path, [[("T", t1), "認証の期限は3日だ"], [("T", t2), "認証の期限は5日に変更"]], "n")
        r = ma.AnswerSession(p, Q, "o", answer_version=v).call("recall", {"question": Q})
        assert r["verdict"] == "CHOICE", (t1, t2, v, r["verdict"])
        assert attack(p, Q, 2, version=v) == [], (t1, t2, v)


def test_v18_replays_and_older_versions_replay_unchanged(tmp_path):
    p = store_sessions(tmp_path, [[("T", "新製品の開発"), "認証の期限は3日だ"], [("T", "新製品開発"), "認証の期限は5日に変更"]], "rp")
    v = {}
    for ver in LATE:
        a = ma.AnswerSession(p, Q, "o", answer_version=ver)
        v[ver] = a.call("recall", {"question": Q})["verdict"]
        assert ma.replay_answer(a.ledger.dir).status == "IDENTICAL"
    assert v == {ma.ANSWER_V16: "CHOICE", ma.ANSWER_V17: "CHOICE", ma.ANSWER_V18: "UPDATED"}


# ---------------------------------------------------------------------------------------------------------------------------------------------
# the meter v2 revision cycle: arms.v2
# ---------------------------------------------------------------------------------------------------------------------------------------------
import meter2 as M2                                           # noqa: E402
import prompts as P                                           # noqa: E402

MSG = "蔵書移転の実務は鴇田悠司がまとめる。設計図を広げると、搬入口から曲がり角が多い。期限は5日に変更！"


def test_the_whole_sentence_rule():
    eq = M2.equals_whole_sentence
    assert eq("蔵書移転の実務は鴇田悠司がまとめる。", MSG) and eq("蔵書移転の実務は鴇田悠司がまとめる", MSG)
    assert eq("設計図を広げると、搬入口から曲がり角が多い。", MSG) and eq("期限は5日に変更！", MSG)
    for bad in ("蔵書移転の実務は鴇田悠司", "鴇田悠司がまとめる", "蔵書移転の実務は鴇田悠司がまとめる。設計図を広げると、搬入口から曲がり角が多い。", "設計図を広げると", "期限は5日に変更",
                "[1-1] 鴇田: 蔵書移転の実務は鴇田悠司がまとめる。", "", "。", "蔵書移転の実務は山本がまとめる"):
        assert not eq(bad, MSG), bad
    assert eq("蔵書移転の実務は鴇田悠司がまとめる。", "蔵書移転の実務は鴇田悠司がまとめる。")


class FakeInner:
    def __init__(self):
        self.calls, self.turn = [], None

    def set_turn(self, t):
        self.turn = t

    def call(self, tool, args=None):
        self.calls.append((tool, args))
        return {"ok": True}


def test_the_verbatim_door_refuses_pieces_paraphrases_other_turns_and_foreign_topics():
    inner = FakeInner()
    d = M2.VerbatimDoor(inner, {"1-1": MSG, "1-2": "窓口の掲示を戻す。"}, "燈架新館の開館準備週次ログ")
    d.set_turn("1-1")
    assert d.call("declare_topic", {"text": "燈架新館の開館準備"})["ok"]                   # a piece of the title
    assert d.call("declare_topic", {"text": "蔵書移転"})["ok"]                              # a piece of this message
    for t in ("燈架新館開館準備", "窓口の掲示", "新館の準備"):
        assert d.call("declare_topic", {"text": t})["refusal"] == "topic_not_from_story", t
    assert d.call("write", {"text": "蔵書移転の実務は鴇田悠司がまとめる。"})["ok"]
    assert d.call("keep_unshaped", {"text": "設計図を広げると、搬入口から曲がり角が多い"})["ok"]
    for bad in ("蔵書移転の実務は鴇田悠司", "窓口の掲示を戻す。", "鴇田悠司がまとめる"):
        r = d.call("write", {"text": bad})
        assert r["ok"] is False and r["refusal"] == "not_verbatim", bad
    n = len(inner.calls)
    d.set_turn("1-2")
    assert d.call("write", {"text": "窓口の掲示を戻す"})["ok"] and d.call("write", {"text": "蔵書移転の実務は鴇田悠司がまとめる。"})["refusal"] == "not_verbatim"
    assert d.call("declare_topic", {"text": "窓口の掲示"})["ok"]                            # now a piece of a message of the session
    assert d.gate == {"writes_refused": 4, "topics_refused": 3, "writes_ok": 3} and all(t in ("declare_topic", "write", "keep_unshaped") for t, _ in inner.calls)
    assert len(inner.calls) == n + 2


def test_a1v_appends_the_raw_sentences_and_hides_log_append():
    inner = FakeInner()
    inner.intro = lambda: {"tools": ["log_append", "log_grep"], "caps": {}}
    d = M2.AutoLogDoor(inner, {"2-3": MSG})
    d.set_turn("2-3")
    assert [a["text"] for t, a in inner.calls if t == "log_append"] == ["2-3 蔵書移転の実務は鴇田悠司がまとめる。", "2-3 設計図を広げると、搬入口から曲がり角が多い。", "2-3 期限は5日に変更！"]
    assert d.intro()["tools"] == ["log_grep"] and M2.story_tool_names("A1v", ("log_append", "log_grep", "report")) == ("log_grep", "report")
    assert M2.story_tool_names("A1", ("log_append", "log_grep")) == ("log_append", "log_grep")


def test_the_load_pause_and_the_token_cap():
    loads = iter([13.0, 12.5, 9.0])
    slept = []
    assert M2.pause_while_loaded(12.0, sleep=slept.append, getload=lambda: next(loads), poll=7) == 2 and slept == [7, 7]
    assert M2.pause_while_loaded(None, getload=lambda: 99) == 0
    M2.TOKEN_CAP, M2.SPENT["input_tokens"] = 10, 11
    try:
        with pytest.raises(M2.MeterError):
            M2.check_token_cap()
    finally:
        M2.TOKEN_CAP, M2.SPENT["input_tokens"] = None, 0


def test_arm_versions_prompts_and_arms():
    assert P.system_prompt("A3", "story", "arms.v1") == P.STORY["A3"] and P.system_prompt("A3", "story", "arms.v2") == P.system_prompt("A3f", "story", "arms.v2") != P.STORY["A3"]
    assert P.system_prompt("A0", "story", "arms.v2") == P.STORY["A0"] and P.system_prompt("A1", "story", "arms.v2") == P.STORY["A1"]
    assert P.system_prompt("A1v", "question") == P.system_prompt("A1", "question")
    assert set(P.prompt_shas("arms.v1")["story"]) == {"A0", "A1", "A3", "A3f"} and "A1v" in P.prompt_shas("arms.v2")["story"]
    assert P.prompt_shas("arms.v1") == P.prompt_shas()                                     # the pilot's hashes are unchanged


def _story():
    return {"id": "MICRO", "title": "新館の準備ログ", "plants": [], "checkpoints": [{"index": 0, "after_session": 1}],
            "sessions": [[{"speaker": "a", "text": "認証の期限は金曜。会議は東京で開く。"}, {"speaker": "b", "text": "備品の担当は山本。"}], [{"speaker": "a", "text": "認証の期限は水曜に変更。"}]],
            "questions": [{"q": "認証の期限はいつですか？", "gold": "水曜", "checkpoint": 0, "kind": "update", "form": "same", "ref": None}]}


def test_arms_v2_end_to_end_with_the_stub(tmp_path):
    story = _story()
    out = str(tmp_path / "o")
    for arm in ("A3", "A3f", "A1v", "A1"):
        r = M2.run_one(story, arm, 1, client=M2.make_client("stub", False, "m"), model="m", out_root=out, arm_version="arms.v2", max_load=None)
        assert r["arm_version"] == "arms.v2" and r["ended"] == "complete"
        if arm in ("A3", "A3f"):
            assert r["writes_verbatim"] and r["store"]["verify"] == "OK" and sum((s["gate"] or {}).get("writes_refused", 0) for s in r["sessions"]) == 0
        assert (r["log_written_by"] or "").startswith({"A1v": "harness", "A1": "model"}.get(arm, "?")) or arm in ("A3", "A3f")
    log = open(os.path.join(out, "MICRO", "A1v", "r01", "store", "log.txt"), encoding="utf-8").read().splitlines()
    assert len(log) == 4 and log[0].endswith("1-1 認証の期限は金曜。")
    with pytest.raises(M2.MeterError):
        M2.run_one(story, "A1v", 2, client=M2.make_client("stub", False, "m"), model="m", out_root=out, arm_version="arms.v1")
    M2.write_report(out)
    assert "Updated questions, one by one" in open(os.path.join(out, "report.md"), encoding="utf-8").read()


def test_the_default_arm_version_is_the_pilot_and_records_it(tmp_path):
    r = M2.run_one(_story(), "A3", 1, client=M2.make_client("stub", False, "m"), model="m", out_root=str(tmp_path / "o"))
    assert r["arm_version"] == "arms.v1" and r["writes_verbatim"] is False and all((s["gate"] is None) for s in r["sessions"])
