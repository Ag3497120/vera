"""PUB-M6g tests: memanswer.v7 = DEFAULT-DENY emit (designer decision, L-PUB-90).  An emit is allowed only if the task question, recalled WITHOUT any bridge of the run, yields exactly one live value (or is NONE
and the run's bridge then yields exactly one), the woven stretch is exactly an occurrence of that value, the frozen gate (or the completion of that same recall) passes, and the value is not replaced /
contested.  Every repro of the three reviews (chk/, r2/, r3/) is a regression test here, run with the EXHAUSTIVE attack of the third review: weave every span of every sentence, emit, and list what comes out.
No network, no API."""
import pytest

from verantyx.loom import memanswer as ma
from verantyx.loom import memory as mem
from mem_common import new_store

V7 = ma.ANSWER_V7
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


def attack(p, q, n_sentences, version=V7, bridges=(), recall_first=None):
    """Every span of every sentence, in a fresh run (optionally after bridges / a recall of ANOTHER question), woven and emitted: [(sid, text, via)] of what came out (verified and replayed)."""
    out = []
    for sid in range(n_sentences):
        n = len(ma.AnswerSession(p, q, "o", answer_version=version).call("read_sentence", {"sid": sid})["units"]["WORD"])
        for f in range(n):
            for l in range(f, n):
                a = ma.AnswerSession(p, q, "o", answer_version=version)
                for qp, mp in bridges:
                    assert a.call("bridge", {"question_phrase": qp, "memory_phrase": mp})["ok"]
                if recall_first:
                    a.call("recall", {"question": recall_first})
                if not a.call("weave_span", {"sid": sid, "tier": "WORD", "first": f, "last": l}).get("ok"):
                    continue
                e = a.call("emit", {})
                if e.get("ok"):
                    assert ma.verify_answer(a.ledger.dir)["status"] == "OK" and ma.replay_answer(a.ledger.dir).status == "IDENTICAL"
                    out.append((sid, e["text"], e.get("via")))
    return out


def test_the_third_review_repros_a_task_that_is_candidates_or_choice_emits_nothing(tmp_path):
    p = store(tmp_path, ["新製品のQA締切は金曜", "旧製品のQA締切は月曜"], ["新製品", "旧製品"])
    for q in ("QA締切はいつですか？", "QAの締切はいつですか？", "QAの締切は？", "締切はいつですか？"):
        assert attack(p, q, 2) == [], q
    assert attack(p, "QAの締切はいつですか？", 2, bridges=[("QAの締切", "旧製品のQA締切")]) == []        # the bridge cannot pick a nest: the unbridged task is CANDIDATES
    assert attack(p, "QA締切はいつですか？", 2, bridges=[("QA", "旧製品のQA締切")]) == []                 # F1 of the second review
    p2 = store(tmp_path, ["認証の期限は金曜", "認証の期限は月曜"], name="ss")
    for q in ("認証の期限はいつですか？", "認証期限はいつですか？", "認証のの期限はいつですか？", "認証の期限はいつ？", "期限はいつですか？", "認証の期限は何曜日ですか？", "認証の期限の日はいつですか？", "認証で期限はいつですか？"):
        assert attack(p2, q, 2) == [], q


def test_the_exact_answer_is_still_emitted_and_nothing_else(tmp_path):
    p = store(tmp_path, ["認証の期限は金曜", "発送の期限は火曜"])
    assert attack(p, "認証の期限はいつですか？", 2) == [(0, "金曜", None)]
    p = store(tmp_path, ["認証の期限は金曜", "認証の期限は金曜から月曜に変更"], name="upd")
    for q in ("認証の期限はいつですか？", "認証期限はいつですか？", "認証の期限は何曜日ですか？"):
        assert attack(p, q, 2) == [(1, "月曜", "update")], q
    assert attack(p, "期限はいつですか？", 2) == []


def test_the_first_review_repros_on_v7(tmp_path):
    p = store(tmp_path, ["認証モジュールの担当は田中", "認証モジュールの担当は佐藤"])
    assert attack(p, "認証モジュールの担当は誰ですか？", 2) == []                                       # contested, no recall
    p = store(tmp_path, ["認証モジュールの担当は田中", "認証モジュールの担当は佐藤", "経理部の担当は田中"], name="laun")
    assert attack(p, "認証モジュールの担当は誰ですか？", 3, recall_first="経理部の担当は誰ですか？") == []   # laundered through a recall of another question
    p = store(tmp_path, ["認証の期限は金曜", "認証の期限は金曜から月曜に変更"], name="rep")
    assert (0, "金曜", None) not in attack(p, "認証の期限はいつですか？", 2)                              # the old value, no recall
    p = store(tmp_path, ["認証の期限は金曜から月曜に変更", "新製品の発売日は火曜"], name="cross")
    got = attack(p, "新製品の発売日はいつですか？", 2, recall_first="認証の期限はいつですか？")
    assert [g[:2] for g in got] == [(1, "火曜")] or got == []                                           # never 月曜 via the completion of another question
    p = store(tmp_path, ["新製品のQA締切は金曜", "新製品のリリース日は月曜"], ["新製品"], name="nest")
    got = attack(p, "QA締切はいつですか？", 2, recall_first="リリース日はいつですか？")
    assert (1, "月曜", "nest") not in got and all(g[1] != "月曜" for g in got)


def test_the_second_review_repros_on_v7(tmp_path):
    p = store(tmp_path, ["認証の期限は金曜", "認証の期限は月曜に変わった"])
    got = attack(p, "認証の期限はいつですか？", 2)
    assert all(g[1] != "月曜" for g in got)                                                              # the unindexed new value is never emitted


@pytest.mark.xfail(strict=True, reason="OPEN reader-coverage item (L-PUB-88): 「…に変わった」 is not read as a change clause, so the index does not know 金曜 was replaced")
def test_the_old_value_before_an_unread_change_form_is_not_detected_yet(tmp_path):
    p = store(tmp_path, ["認証の期限は金曜", "認証の期限は月曜に変わった"])
    assert (0, "金曜", None) not in attack(p, "認証の期限はいつですか？", 2)


@pytest.mark.xfail(strict=True, reason="OPEN reader-coverage item (L-PUB-88): 「X は Y が担当」 is not read, so a contradiction through it is invisible")
def test_a_contradiction_through_an_unread_form_is_not_detected_yet(tmp_path):
    p = store(tmp_path, ["認証モジュールの担当は田中", "認証モジュールは佐藤が担当"])
    assert (0, "田中", None) not in attack(p, "認証モジュールの担当は誰ですか？", 2)


def test_default_deny_refusals_are_typed(tmp_path):
    p = store(tmp_path, ["認証の期限は金曜", "認証の期限は月曜"])
    a = ma.AnswerSession(p, "認証の期限はいつですか？", "o", answer_version=V7)
    assert a.call("weave_span", {"sid": 0, "tier": "WORD", "first": 2, "last": 2})["ok"]
    assert a.call("emit", {})["refusal"] == "ambiguous_task"
    p = store(tmp_path, ["認証の期限は金曜", "発送の期限は火曜"], name="one")
    b = ma.AnswerSession(p, "認証の期限はいつですか？", "o", answer_version=V7)
    assert b.call("weave_span", {"sid": 1, "tier": "WORD", "first": 2, "last": 2})["ok"]
    assert b.call("emit", {})["refusal"] == "not_the_task_answer"
    p = store(tmp_path, ["棚ラベル照合の締切は9月24日"], name="none")
    c = ma.AnswerSession(p, "棚ラベルの確認作業はいつまでですか？", "o", answer_version=V7)            # NONE-or-CANDIDATES unbridged
    assert c.call("recall", {"question": "棚ラベルの確認作業はいつまでですか？"})["verdict"] == "CANDIDATES"
    assert c.call("bridge", {"question_phrase": "確認作業", "memory_phrase": "棚ラベル照合の締切"})["ok"]
    assert c.call("weave_span", {"sid": 0, "tier": "WORD", "first": 3, "last": 5}).get("ok") in (True, False)
    assert c.call("emit", {})["ok"] is False                                                             # CANDIDATES is always an abstention


def test_v7_begin_row_and_replay_and_older_versions_replay(tmp_path):
    p = store(tmp_path, ["認証の期限は金曜"])
    a = ma.AnswerSession(p, "認証の期限はいつですか？", "o", answer_version=V7)
    m = a.begin_result["mem_answer"]
    assert m["version"] == "memanswer.v7" and m["guard"] == "ansguard.v5"
    r = ma.replay_answer(a.ledger.dir)
    assert r.run.v7 and r.run.v6 and r.run.v5
    for v in (ma.ANSWER_V5, ma.ANSWER_V6):
        b = ma.AnswerSession(p, "認証の期限はいつですか？", "o", answer_version=v)
        assert not ma.replay_answer(b.ledger.dir).run.v7


# -- memanswer.v8: the identity of a value is the value AS WRITTEN (the fourth review of 70e3b152) ---------------------------------------------------------------
V8 = ma.ANSWER_V8


@pytest.mark.parametrize("pair,q", [
    (("休業日は1・2日", "休業日は12日"), "休業日はいつですか？"),                    # c1
    (("面積は10²", "面積は102"), "面積は何ですか？"),
    (("認証の期限は1・2日", "認証の期限は12日"), "認証の期限はいつですか？"),          # c3
    (("認証の版はv2・1", "認証の版はv21"), "認証の版は何ですか？"),
    (("認証の部屋は10²", "認証の部屋は102"), "認証の部屋はどこですか？"),
    (("認証の部屋は1 02", "認証の部屋は102"), "認証の部屋はどこですか？"),
    (("会議の場所は3・4階", "会議の場所は34階"), "会議の場所はどこですか？"),          # c4
    (("認証の期限は12日", "認証の期限は1・2日"), "認証の期限はいつですか？"),
])
def test_values_that_differ_only_in_a_dot_a_space_or_a_width_are_a_contradiction_and_nothing_is_emitted(tmp_path, pair, q):
    p = store(tmp_path, list(pair))
    r = ma.AnswerSession(p, q, "o", answer_version=V8).call("recall", {"question": q})
    assert r["verdict"] == "CHOICE" and len(r["answers"]) == 2                                          # two written values, never one
    assert attack(p, q, 2, version=V8) == []


def test_a_value_with_a_dot_or_a_space_inside_is_never_emitted_squashed(tmp_path):
    for w, q in (("認証の期限は1・2日", "認証の期限はいつですか？"), ("認証の部屋は1 02", "認証の部屋はどこですか？")):
        p = store(tmp_path, [w], name="s" + str(abs(hash(w)) % 1000))
        got = attack(p, q, 1, version=V8)
        assert got == [], (w, got)                                                                      # the loom would read it out as 12日 / 102: refused (quote_not_verbatim), not emitted
        a = ma.AnswerSession(p, q, "o", answer_version=V8)
        o = a.call("recall", {"question": q})["answers"][0]["occurrences"][0]
        assert o["verbatim"] is False
        assert a.call("weave_span", {"sid": 0, "tier": "WORD", "first": o["span"][0], "last": o["span"][1]})["refusal"] == "quote_not_verbatim"


def test_v8_keeps_the_exact_answers_and_the_owner_joiners(tmp_path):
    p = store(tmp_path, ["認証の期限は12日"])
    assert attack(p, "認証の期限はいつですか？", 1, version=V8) == [(0, "12日", None)]
    p = store(tmp_path, ["配布ビルドのバージョンは3.2.0-rc2です"], name="j")
    assert (0, "3.2.0-rc2", None) in attack(p, "配布ビルドのバージョンは何ですか？", 1, version=V8)
    b = ma.AnswerSession(p, "配布ビルドのバージョンは何ですか？", "o", answer_version=V8)
    assert b.begin_result["mem_answer"]["version"] == "memanswer.v8" and b.begin_result["mem_answer"]["guard"] == "ansguard.v6"
    r = ma.replay_answer(b.ledger.dir)
    assert r.run.v8 and r.run.v7


def test_written_identity_merges_nothing_but_nfc_forms():
    from verantyx.loom import memask as mask
    assert mask.written_id("1・2日") != mask.written_id("12日") and mask.written_id("1 2") != mask.written_id("12") and mask.written_id("V2") != mask.written_id("v2")
    assert mask.written_id("10²") != mask.written_id("102") and mask.written_id("１２") != mask.written_id("12")
    assert mask.written_id("\u30ac") == mask.written_id("\u30ab\u3099")                              # canonical equivalents only
