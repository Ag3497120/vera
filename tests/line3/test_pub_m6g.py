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


# -- memanswer.v9: the value as written in the SOURCE (the fifth review of 7b8f546b) -----------------------------------------------------------------------------
V9 = ma.ANSWER_V9
Q = "認証の期限はいつですか？"
SYMBOLS = ["-5度", "−5度", "+5度", ".5日", "$5", "¥5", "#5", "~5日", "5%", "5％", "(5)日", "（5）日"]   # a combining mark / VS16 next to a digit is refused at WRITE (no_shape: the gap is no particle), so none reaches the memory


@pytest.mark.parametrize("v", SYMBOLS)
def test_a_value_with_a_symbol_next_to_it_is_never_emitted_without_it(tmp_path, v):
    p = store(tmp_path, ["認証の期限は" + v])
    r = ma.AnswerSession(p, Q, "o", answer_version=V9).call("recall", {"question": Q})
    assert r["answers"][0]["answers"] == [v] or r["verdict"] == "NONE"                                  # shown as written (「5)日」 was shown for 「(5)日」)
    assert attack(p, Q, 1, version=V9) == []


@pytest.mark.parametrize("a,b", [("-5度", "5度"), ("−5度", "5度"), ("+5度", "5度"), (".5日", "5日"), ("5%", "5"), ("$5", "5"), ("(5)日", "5日"), ("+3%", "-3%"), ("¥5", "$5")])
def test_values_that_differ_only_in_a_sign_a_currency_a_percent_a_bracket_or_a_combining_mark_are_a_contradiction(tmp_path, a, b):
    p = store(tmp_path, ["認証の期限は" + a, "認証の期限は" + b])
    r = ma.AnswerSession(p, Q, "o", answer_version=V9).call("recall", {"question": Q})
    assert r["verdict"] == "CHOICE" and len(r["answers"]) == 2
    assert attack(p, Q, 2, version=V9) == []


def test_the_replaced_value_before_a_signed_new_value_is_not_emitted(tmp_path):
    q = "室温の下限は何度ですか？"
    p = store(tmp_path, ["室温の下限は5度", "室温の下限は5度から-5度に変更"])
    r = ma.AnswerSession(p, q, "o", answer_version=V9).call("recall", {"question": q})
    assert r["verdict"] == "UPDATED" and r["answers"][0]["answers"] == ["-5度"] and r["history"][0]["answers"] == ["5度"]
    assert attack(p, q, 2, version=V9) == []                                                            # 5度 is replaced, -5度 cannot be quoted without its sign
    st = new_store(tmp_path, "two")                                                                     # ... also across sessions
    for w in ("室温の下限は5度", "室温の下限は5度から-5度に変更"):
        s = st.begin("m", profile=mem.PROFILE_V4, versions=M6C)
        assert s.write(w)["ok"]
        s.commit()
    assert attack(str(tmp_path / "two"), q, 2, version=V9) == []
    p = store(tmp_path, ["認証の期限は5%", "認証の期限は5に変更"], name="pct")                              # a plain 5 replacing 5% is a different written value: the change wins
    assert attack(p, Q, 2, version=V9) == [(1, "5", "update")] or attack(p, Q, 2, version=V9) == [(1, "5", None)]


def test_v9_keeps_the_clause_marks_and_the_owner_joiners(tmp_path):
    for w, v in (("認証の期限は12日。", "12日"), ("認証の期限は12日、", "12日"), ("配布ビルドのバージョンは3.2.0-rc2です", "3.2.0-rc2")):
        p = store(tmp_path, [w], name="k%d" % len(w))
        q = Q if "期限" in w else "配布ビルドのバージョンは何ですか？"
        assert (0, v, None) in attack(p, q, 1, version=V9), w
    b = ma.AnswerSession(store(tmp_path, ["認証の期限は12日"], name="b"), Q, "o", answer_version=V9)
    assert b.begin_result["mem_answer"]["version"] == "memanswer.v9" and b.begin_result["mem_answer"]["guard"] == "ansguard.v7"
    r = ma.replay_answer(b.ledger.dir)
    assert r.run.v9 and r.run.v8


def test_source_value_extends_over_symbols_and_not_over_the_clause_marks():
    from verantyx.loom import memask as mask
    from verantyx.loom import memory as m
    from verantyx.loom.memguard import make_source
    rows = [{"kind": "base", "sent": x, "source": make_source("t", 1, i)} for i, x in enumerate(["認証の期限は-5度。", "認証の期限は(5)日", "認証の期限は5日、"])]
    c = m.build_corpus(rows)
    assert mask.source_value(c, 0, 2, 3) == ("-5度", False)
    assert mask.source_value(c, 1, 2, 2) == ("(5)", False)
    assert mask.source_value(c, 2, 2, 3) == ("5日", True)


# -- memanswer.v10: the value boundary is DENY-BY-DEFAULT (the sixth review of 0e369d3c) ----------------------------------------------------------------------------
V10 = ma.ANSWER_V10


def store_some(tmp_path, writes, name):
    """The sentences the exchanger accepts (a refused write is skipped); -> (path, how many were written)."""
    st = new_store(tmp_path, name)
    s = st.begin("m", profile=mem.PROFILE_V4, versions=M6C)
    n = sum(1 for w in writes if s.write(w).get("ok"))
    s.commit()
    return str(tmp_path / name), n


NEIGHBOURS = ["10²", "10³", "1½", "5ª", "5々", "5ゝ", "5ー", "5〆", "5日超", "5日ほど", "5日くらい", "5日ぐらい", "5日程度", "5日以上", "5日未満", "5日前後", "5日のみ", "5日だけ", "約5日", "5日弱", "-5度", "+5度", "5%", "(5)日", "$5"]


@pytest.mark.parametrize("v", NEIGHBOURS)
def test_a_value_with_anything_else_next_to_it_is_never_emitted_shortened(tmp_path, v):
    p, n = store_some(tmp_path, ["認証の期限は" + v], "one%d" % abs(hash(v)))
    got = attack(p, Q, n, version=V10)
    assert all(g[1] == v for g in got), (v, got)                                                      # never a shortened text: either the whole value as written, or nothing


@pytest.mark.parametrize("a,b", [("約5日", "5日"), ("5日超", "5日"), ("5日ほど", "5日"), ("5日くらい", "5日"), ("5日程度", "5日"), ("10²", "10"), ("1½", "1"), ("5ª", "5"), ("5々", "5"), ("5ー", "5"), ("5〆", "5"), ("5日のみ", "5日")])
def test_a_qualified_value_and_the_bare_value_are_a_contradiction_not_one_answer(tmp_path, a, b):
    p, n = store_some(tmp_path, ["認証の期限は" + a, "認証の期限は" + b], "pair%d" % abs(hash(a)))
    if n < 2:
        pytest.skip("the exchanger refuses one of the sentences: nothing to merge")
    r = ma.AnswerSession(p, Q, "o", answer_version=V10).call("recall", {"question": Q})
    assert r["verdict"] == "CHOICE" and len(r["answers"]) == 2
    assert attack(p, Q, 2, version=V10) == []


def test_a_change_to_a_qualified_value_does_not_emit_the_bare_value_via_update(tmp_path):
    for new in ("約5日", "5日超", "5日ほど", "5日くらい"):
        p, n = store_some(tmp_path, ["認証の期限は5日", "認証の期限は%sに変更" % new], "chg%d" % abs(hash(new)))
        got = attack(p, Q, n, version=V10)
        assert (1, "5日", "update") not in got and all(g[1] != "5日" or g[0] == 0 for g in got), (new, got)


def test_v10_keeps_the_clean_boundaries_and_replays(tmp_path):
    for w, v in (("認証の期限は12日", "12日"), ("認証の期限は12日。", "12日"), ("認証の期限は12日、", "12日"), ("認証の期限は12日です", "12日"), ("認証の期限は5日まで", "5日"),
                 ("配布ビルドのバージョンは3.2.0-rc2です", "3.2.0-rc2")):
        q = Q if "期限" in w else "配布ビルドのバージョンは何ですか？"
        p, n = store_some(tmp_path, [w], "ok%d" % abs(hash(w)))
        assert (0, v, None) in attack(p, q, n, version=V10), w
    p = store(tmp_path, ["認証の期限は金曜から月曜に変更"], name="chgok")
    assert attack(p, Q, 1, version=V10) == [(0, "月曜", "update")]
    b = ma.AnswerSession(p, Q, "o", answer_version=V10)
    assert b.begin_result["mem_answer"]["version"] == "memanswer.v10" and b.begin_result["mem_answer"]["guard"] == "ansguard.v8"
    r = ma.replay_answer(b.ledger.dir)
    assert r.run.v10 and r.run.v9


def test_source_value_strict_extends_to_the_boundary_it_accepts():
    from verantyx.loom import memask as mask
    from verantyx.loom import memory as m
    from verantyx.loom.memguard import make_source
    rows = [{"kind": "base", "sent": x, "source": make_source("t", 1, i)} for i, x in enumerate(["認証の期限は約5日に変更", "認証の期限は5日ほどです", "認証の期限は5日です", "認証の期限は5日。"])]
    c = m.build_corpus(rows)
    assert mask.source_value(c, 0, 2, 3, True) == ("約5日", False)
    assert mask.source_value(c, 1, 2, 3, True)[1] is False and mask.source_value(c, 1, 2, 3, True)[0].startswith("5日ほど")
    assert mask.source_value(c, 2, 2, 3, True) == ("5日", True) and mask.source_value(c, 3, 2, 3, True) == ("5日", True)
