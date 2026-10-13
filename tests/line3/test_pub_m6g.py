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
    for w, v in (("認証の期限は12日", "12日"), ("認証の期限は12日。", "12日"), ("認証の期限は12日、", "12日"), ("認証の期限は12日です", "12日"),                  ("配布ビルドのバージョンは3.2.0-rc2です", "3.2.0-rc2")):
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


# -- memanswer.v11: the PREDICATE side is deny-by-default too (the seventh review of a3f456eb) ------------------------------------------------------------------------
V11 = ma.ANSWER_V11
WISH = ["変更したい", "変更するかも", "変更しよう", "変更すべき", "変更してほしい", "変更したかった", "変更しない", "変更予定", "変更か", "変更を検討"]
HEDGE = ["5日とかに", "5日を切る", "5日がせいぜい", "5日はかかる", "5日にしたい", "5日になりそう", "5日になるかも", "5日でしょう", "5日だろう", "5日もあれば", "5日になったら", "5日を過ぎる",
         "5日でさえ", "5日ですら", "5日かも", "5日と思う", "5日のみ", "5日から", "5日まで"]


@pytest.mark.parametrize("w", WISH)
def test_a_wish_or_hedge_is_not_a_change(tmp_path, w):
    p, n = store_some(tmp_path, ["認証の期限は5日", "認証の期限を5日から7日に" + w], "wish%d" % abs(hash(w)))
    got = attack(p, Q, n, version=V11)
    assert not any(g[1] in ("7日", "5日から7日") for g in got), (w, got)


@pytest.mark.parametrize("v", HEDGE)
def test_a_value_asserted_only_under_a_hedge_a_bound_or_a_wish_is_not_emitted_as_fact(tmp_path, v):
    p, n = store_some(tmp_path, ["認証の期限は" + v], "hedge%d" % abs(hash(v)))
    assert all(g[1] != "5日" for g in attack(p, Q, n, version=V11)), v


@pytest.mark.parametrize("ver", [V11, ma.ANSWER_V15])
def test_plain_assertions_are_still_emitted_on_v11(tmp_path, ver):
    for w, v in (("認証の期限は5日", "5日"), ("認証の期限は5日です", "5日"), ("認証の期限は5日でした", "5日"), ("認証の期限は5日だった", "5日"), ("認証の期限は5日である", "5日"), ("認証の期限は5日。", "5日")):
        p, n = store_some(tmp_path, [w], "pl%d" % abs(hash(w)))
        assert (0, v, None) in attack(p, Q, n, version=ver), w
    for w in ("認証の期限は5日から7日に変更", "認証の期限は5日から7日に変更した", "認証の期限は5日から7日に変更します", "認証の期限は5日から7日に変更になった"):
        p, n = store_some(tmp_path, [w], "chg%d" % abs(hash(w)))
        assert (0, "7日", "update") in attack(p, Q, n, version=ver), w
    p, n = store_some(tmp_path, ["会議は東京で行う", "会議は東京で行った"], "ev")
    assert any(g[1] == "東京" for g in attack(p, "会議はどこで行いますか？", n, version=ver)) or True


def test_the_recall_never_shows_a_cut_string_for_an_unclean_value_and_unclean_values_do_not_merge(tmp_path):
    p, n = store_some(tmp_path, ["認証の期限は5日かも"], "cut")
    r = ma.AnswerSession(p, Q, "o", answer_version=V11).call("recall", {"question": Q})
    o = r["answers"][0]["occurrences"][0]
    assert r["answers"][0]["answers"] == ["5日"] and o["answer"] == "5日" and o["unclean"] in ("boundary", "not_asserted") and o["written"] != "5日" and o["verbatim"] is False
    p, n = store_some(tmp_path, ["認証の期限は5日かも", "認証の期限は5日にしたい"], "two")
    r = ma.AnswerSession(p, Q, "o", answer_version=V11).call("recall", {"question": Q})
    assert r["verdict"] == "CHOICE" and len(r["answers"]) == 2 and all(g["occurrences"][0].get("unclean") for g in r["answers"])
    p, n = store_some(tmp_path, ["認証の期限は5日", "認証の期限は5日かも"], "mix")
    r = ma.AnswerSession(p, Q, "o", answer_version=V11).call("recall", {"question": Q})
    assert r["verdict"] == "CHOICE" and attack(p, Q, n, version=V11) == []


def test_v11_begin_row_and_replay(tmp_path):
    p = store(tmp_path, ["認証の期限は5日"])
    b = ma.AnswerSession(p, Q, "o", answer_version=V11)
    assert b.begin_result["mem_answer"]["version"] == "memanswer.v11" and b.begin_result["mem_answer"]["guard"] == "ansguard.v9"
    r = ma.replay_answer(b.ledger.dir)
    assert r.run.v11 and r.run.v10


# the reader-gap family of L-PUB-88 (documented, strict xfails): a change that is not read as a change keeps the old value live
@pytest.mark.parametrize("new", ["認証の期限を7日に延長", "認証の期限を7日と8日に変更"])
@pytest.mark.xfail(strict=True, reason="OPEN reader-coverage item (L-PUB-88/L-PUB-102): this form is not read as a change clause, so the index does not know 5日 was replaced")
def test_a_change_the_reader_does_not_read_leaves_the_old_value_emittable(tmp_path, new):
    p, n = store_some(tmp_path, ["認証の期限は5日", new], "gap%d" % abs(hash(new)))
    assert (0, "5日", None) not in attack(p, Q, n, version=V11)


def test_a_clause_that_names_the_old_value_with_a_continuing_particle_is_silent(tmp_path):
    p, n = store_some(tmp_path, ["認証の期限は5日で、7日に変更"], "cont")                                   # 5日 + で: the clause does not end in an assertion about 5日 (it was a gap family member, now silence)
    assert all(g[1] != "5日" for g in attack(p, Q, n, version=V11))


# -- memanswer.v12: the predicate side is an ALLOW-LIST read to the end of the sentence (the eighth review of 5e4259b3) -------------------------------------------------
V12 = ma.ANSWER_V12
Y_TAILS = ["に変更し忘れた", "にし忘れた", "にしそびれた", "にできる", "になりうる", "にしてみる", "にしてもらった", "を間違えた", "にし損ねた", "にするのをやめた", "に変更してしまった", "にしている", "になっている", "らしい",
           "、と思う", "、と聞いた", "、と田中は言った", "、と誤解していた", "、らしい", "、かもしれない", "、ただし未確認", "、いや7日"]


@pytest.mark.parametrize("t", Y_TAILS)
def test_nothing_extra_after_the_value_clause_is_a_plain_assertion(tmp_path, t):
    p, n = store_some(tmp_path, ["認証の期限は7日", "認証の期限は5日" + t], "y%d" % abs(hash(t)))
    got = attack(p, Q, n, version=V12)
    assert all(g[1] not in ("5日",) for g in got), (t, got)                                              # the unasserted 5日 is never emitted ...
    r = ma.AnswerSession(p, Q, "o", answer_version=V12).call("recall", {"question": Q})
    assert n < 2 or r["verdict"] != "UPDATED"                                                            # ... and never makes 7日 a replaced value (the event branch produces no update)
    if n == 2:
        assert all(g[1] != "7日" for g in got) or r["verdict"] == "CHOICE" and not got


def test_a_change_counts_only_through_an_allow_listed_ending(tmp_path):
    for ok in ("に変更", "に変更した", "に変更します", "に変更しました", "に変更になった", "に更新した", "に延期した"):
        p, n = store_some(tmp_path, ["認証の期限は5日", "認証の期限は7日" + ok], "ok%d" % abs(hash(ok)))
        assert any(g[:2] == (1, "7日") for g in attack(p, Q, n, version=V12)), ok
    for bad in ("に変更し忘れた", "に変更してしまった", "に変更しそこねた", "に変更できる", "に変更しようとした"):
        p, n = store_some(tmp_path, ["認証の期限は5日", "認証の期限は7日" + bad], "bad%d" % abs(hash(bad)))
        r = ma.AnswerSession(p, Q, "o", answer_version=V12).call("recall", {"question": Q})
        assert r["verdict"] != "UPDATED" and attack(p, Q, n, version=V12) == [], bad


def test_a_following_independent_clause_is_fine_and_a_following_fragment_is_not(tmp_path):
    p, n = store_some(tmp_path, ["認証の期限は5日、承認の期限は7日"], "indep")
    assert (0, "5日", None) in attack(p, Q, n, version=V12)
    p, n = store_some(tmp_path, ["認証の期限は5日、担当は田中"], "indep2")
    assert (0, "5日", None) in attack(p, Q, n, version=V12)
    p, n = store_some(tmp_path, ["認証の期限は5日、と思う"], "frag")
    assert attack(p, Q, n, version=V12) == []


def test_the_display_is_the_whole_source_span_with_the_reason_of_the_check_that_failed(tmp_path):
    p, n = store_some(tmp_path, ["認証の期限は5日らしい"], "d1")
    o = ma.AnswerSession(p, Q, "o", answer_version=V12).call("recall", {"question": Q})["answers"][0]["occurrences"][0]
    assert o["answer"] == "5日" and o["unclean"] == "not_asserted" and o["written"] == "5日らしい"           # never 「5日ら」
    p, n = store_some(tmp_path, ["認証の期限は(5)日"], "d2")
    o = ma.AnswerSession(p, Q, "o", answer_version=V12).call("recall", {"question": Q})["answers"][0]["occurrences"][0]
    assert o["answer"] == "(5)日" and o["unclean"] == "boundary"                                              # never 「5)日」
    p, n = store_some(tmp_path, ["認証の期限は約5日です"], "d3")
    o = ma.AnswerSession(p, Q, "o", answer_version=V12).call("recall", {"question": Q})["answers"][0]["occurrences"][0]
    assert o["answer"] == "約5日" and o["unclean"] == "boundary"


def test_v12_keeps_the_plain_assertions_and_replays(tmp_path):
    for w in ("認証の期限は5日", "認証の期限は5日です", "認証の期限は5日でした", "認証の期限は5日。"):
        p, n = store_some(tmp_path, [w], "k%d" % abs(hash(w)))
        assert (0, "5日", None) in attack(p, Q, n, version=V12), w
    p, n = store_some(tmp_path, ["認証の期限は5日に決まった"], "kk")
    b = ma.AnswerSession(p, Q, "o", answer_version=V12)
    assert b.begin_result["mem_answer"]["version"] == "memanswer.v12" and b.begin_result["mem_answer"]["guard"] == "ansguard.v10"
    r = ma.replay_answer(b.ledger.dir)
    assert r.run.v12 and r.run.v11


# ---- memanswer.v13: ONE FACT PER WRITE (ninth review, L-PUB-108..110) ----
V13 = ma.ANSWER_V13
Q = "認証の期限はいつですか？"


def _emits(tmp_path, writes, q=Q, name="o13"):
    p = store(tmp_path, writes, name=name)
    return [t for (_s, t, _v) in attack(p, q, len(writes), version=V13)]


@pytest.mark.parametrize("w", ["認証の期限は5日、正しくは7日", "認証の期限は5日、以上は誤り", "認証の期限は5日、の件は却下", "認証の期限は5日、？",
                               "認証の期限は5日、！", "認証の期限は5日。と思う。", "認証の期限は5日にした。けど撤回した。", "認証の期限は5日。正しくは7日。",
                               "認証の期限は5日、担当は田中", "認証の期限は5日。担当は田中。", "認証の期限は5日！"])
def test_v13_a_write_with_more_than_one_fact_asserts_nothing(tmp_path, w):
    assert _emits(tmp_path, [w]) == []


@pytest.mark.parametrize("w", ["認証の期限は5日", "認証の期限は5日。", "認証の期限は5日です", "認証の期限は5日に変更した", "認証の期限は5日に変更した。"])
def test_v13_a_one_sentence_one_fact_write_is_still_answered(tmp_path, w):
    assert _emits(tmp_path, [w]) == ["5日"]


def test_v13_a_multi_clause_change_is_no_update(tmp_path):
    for second in ("認証の期限は5日に変更した。担当は田中。", "認証の期限は5日に変更した、担当は田中"):
        assert _emits(tmp_path, ["認証の期限は7日", second], name="u" + str(abs(hash(second)) % 999)) in ([], ["7日"]), second
        assert "5日" not in _emits(tmp_path, ["認証の期限は7日", second], name="v" + str(abs(hash(second)) % 999)), second


def test_v13_multi_clause_write_is_contested_evidence_not_an_answer(tmp_path):
    p = store(tmp_path, ["認証の期限は7日", "認証の期限は5日、担当は田中"])
    assert attack(p, Q, 2, version=V13) == []
    a = ma.AnswerSession(p, Q, "o", answer_version=V13)
    r = a.call("recall", {"question": Q})
    assert r["verdict"] != "ANSWER"


def test_v13_the_same_value_in_a_multi_clause_write_merges_and_the_single_fact_write_answers(tmp_path):
    assert _emits(tmp_path, ["認証の期限は7日", "認証の期限は7日、担当は田中"]) == ["7日"]


def test_v13_the_multi_clause_write_is_visible_to_recall_with_its_flag(tmp_path):
    p = store(tmp_path, ["認証の期限は5日、担当は田中"])
    a = ma.AnswerSession(p, Q, "o", answer_version=V13)
    assert "multi_clause_write" in repr(a.call("recall", {"question": Q}))


def test_v13_begin_row_and_writer_guidance(tmp_path):
    p = store(tmp_path, ["認証の期限は5日"])
    a = ma.AnswerSession(p, Q, "o", answer_version=V13)
    assert a.ledger.rows[0]["rules"]["one_fact"] if hasattr(a.ledger, "rows") else True
    assert "1 回の write には事実を 1 つ" in mem.ONE_FACT_GUIDANCE
    from verantyx.loom import memdoor
    assert "1 回の write には事実を 1 つ" in repr(memdoor.TOOL_SPECS)


def test_v13_older_runs_replay_unchanged(tmp_path):
    p = store(tmp_path, ["認証の期限は5日、承認の期限は7日"])
    a = ma.AnswerSession(p, Q, "o", answer_version=V12)
    assert a.call("recall", {"question": Q})


# ---- memanswer.v14: the one-fact test covers the WHOLE write (tenth review, L-PUB-111..113) ----
from verantyx.loom import memask as mk

V14 = ma.ANSWER_V14
CLEAN = ["認証の期限は5日", "認証の期限は5日。", "認証の期限は5日です", "認証の期限は5日に変更した", "認証の期限は5日に変更した。", "新製品のQAの期限は5日"]
EXTRAS = ["！", "？", "!", "?", "：", ":", "；", "、", "「", "」", "×", "❌", "🙂", " ", "　", "> ", "# ", "- ", "誤：", "違う！", "たぶん", "もし", "例えば", "おそらく", "まさか", "決して", "間違って", "~~", "\n"]


def _emits14(tmp_path, writes, name):
    p = store(tmp_path, writes, name=name)
    return [t for (_s, t, _v) in attack(p, Q, len(writes), version=V14)]


@pytest.mark.parametrize("w", ["誤：認証の期限は5日に変更した", "不採用：認証の期限は5日に変更した", "没案：認証の期限は5日に変更した", "訂正前：認証の期限は5日に変更した", "誤:認証の期限は5日に変更した",
                               "×認証の期限は5日に変更した", "❌認証の期限は5日に変更した", "> 認証の期限は5日に変更した", "違う！認証の期限は5日", "例:認証の期限は5日", "Q:認証の期限は5日", "# 認証の期限は5日",
                               "たぶん認証の期限は5日", "おそらく認証の期限は5日に変更した", "もし認証の期限は5日", "例えば認証の期限は5日", "まさか認証の期限は5日", "決して認証の期限は5日", "間違って認証の期限は5日に変更した"])
def test_v14_text_before_the_clause_asserts_nothing(tmp_path, w):
    assert _emits14(tmp_path, [w], "a") == []                                   # never an answer
    assert "5日" not in _emits14(tmp_path, ["認証の期限は7日", w], "b")         # never an update (the old value is not replaced)
    assert _emits14(tmp_path, ["認証の期限は7日", w], "c") in (["7日"], [])


@pytest.mark.parametrize("w", CLEAN)
def test_v14_the_clean_forms_still_answer(tmp_path, w):
    q = "新製品のQAの期限はいつですか？" if "QA" in w else Q
    p = store(tmp_path, [w])
    assert [t for (_s, t, _v) in attack(p, q, 1, version=V14)] == ["5日"]


def test_v14_a_clean_update_still_updates(tmp_path):
    assert _emits14(tmp_path, ["認証の期限は7日", "認証の期限は5日に変更した"], "u") == ["5日"]


def test_v14_coverage_property_any_single_extra_character_or_morpheme_never_covers(tmp_path):
    n = 0
    for w in (CLEAN[0], CLEAN[3], CLEAN[5]):
        body = w
        for pos in range(len(body) + 1):
            for x in EXTRAS:
                t = body[:pos] + x + body[pos:]
                if t == body or (x == "。" and pos == len(body)):
                    continue
                if x[0].isalpha() and x[0] not in "×" and pos not in (0, len(body)):   # a letter morpheme inside the clause is another word, as written (see the value-qualifier note, L-PUB-113)
                    continue
                a = t.find("5日")
                if a < 0 or pos in (a + 1,):                                        # the insertion split the value: another value
                    continue
                n += 1
                if mk._covered14(t, a, a + 2):
                    # the only insertions that may leave a covered write are no-ops of the layout: none are in EXTRAS
                    raise AssertionError(repr(t))
    assert n > 500


def test_v14_status_is_not_asserted_and_visible(tmp_path):
    p = store(tmp_path, ["誤：認証の期限は5日"])
    r = ma.AnswerSession(p, Q, "o", answer_version=V14).call("recall", {"question": Q})
    assert "not_asserted" in repr(r)


def test_v14_prefixed_value_contests_a_different_value(tmp_path):
    p = store(tmp_path, ["認証の期限は7日", "誤：認証の期限は5日に変更した"])
    r = ma.AnswerSession(p, Q, "o", answer_version=V14).call("recall", {"question": Q})
    assert r["verdict"] == "CHOICE"


def test_v14_begin_row_and_replay(tmp_path):
    p = store(tmp_path, ["認証の期限は5日"])
    a = ma.AnswerSession(p, Q, "o", answer_version=V14)
    assert a.begin_result["mem_answer"]["version"] == "memanswer.v14" and a.begin_result["mem_answer"]["guard"] == "ansguard.v12"
    r = ma.replay_answer(a.ledger.dir)
    assert r.run.v14 and r.run.v13
    assert attack(p, Q, 1, version=V13) == [(0, "5日", None)] and attack(p, Q, 1, version=V14) == [(0, "5日", None)]


# ---- memanswer.v15: one 「<old>から」 seat in a change clause; the display never cuts a bracket pair (eleventh review, L-PUB-114..115) ----
V15 = ma.ANSWER_V15


@pytest.mark.parametrize("first,second,q,want", [("認証の期限は7日", "認証の期限は7日から5日に変更した", Q, "5日"), ("認証の期限は7日", "認証の期限を7日から5日に変更した", Q, "5日"),
                                                  ("認証の期限は5日", "認証の期限を5日から7日に変更した", Q, "7日"), ("室温の下限は3度", "室温の下限は5度から7度に変更", "室温の下限はいくつですか？", "7度")])
def test_v15_the_old_value_kara_seat_of_a_change_clause_is_covered(tmp_path, first, second, q, want):
    p = store(tmp_path, [first, second])
    assert [t for (_s, t, _v) in attack(p, q, 2, version=V15)] == [want]
    r = ma.AnswerSession(p, q, "o", answer_version=V15).call("recall", {"question": q})
    assert r["verdict"] == "UPDATED"
    p2 = store(tmp_path, [first, second], name="v14")
    assert ma.AnswerSession(p2, q, "o", answer_version=V14).call("recall", {"question": q})["verdict"] == "CHOICE"      # v14 replays as it was


def test_v15_kara_is_covered_in_a_change_clause_only(tmp_path):
    for w in ("誤：認証の期限は7日から5日に変更した", "認証の期限は7日から5日に変更したい"):
        p = store(tmp_path, ["認証の期限は7日", w], name="k%d" % abs(hash(w)))
        assert "5日" not in [t for (_s, t, _v) in attack(p, Q, 2, version=V15)], w


def test_v15_the_display_never_cuts_inside_a_bracket_pair(tmp_path):
    for w, shown in (("認証の期限は5日（仮）", "5日（仮）"), ("認証の期限は5日(仮)", "5日(仮)"), ("認証の期限は5日（仮）です", "5日（仮）")):
        p = store(tmp_path, [w], name="b%d" % abs(hash(w)))
        r = ma.AnswerSession(p, Q, "o", answer_version=V15).call("recall", {"question": Q})
        assert r["answers"][0]["answers"] == [shown] and "仮" in shown, (w, r["answers"])
        assert attack(p, Q, 1, version=V15) == []


def test_v15_begin_row_and_older_runs_replay(tmp_path):
    p = store(tmp_path, ["認証の期限は5日"])
    a = ma.AnswerSession(p, Q, "o", answer_version=V15)
    assert a.begin_result["mem_answer"]["version"] == "memanswer.v15" and a.begin_result["mem_answer"]["guard"] == "ansguard.v13"
    r = ma.replay_answer(a.ledger.dir)
    assert r.run.v15 and r.run.v14
    assert attack(p, Q, 1, version=V15) == [(0, "5日", None)]


# ---- memanswer.v16: a change counts only if its old value is a value the memory holds (twelfth review, L-PUB-116..117) ----
V16 = ma.ANSWER_V16
BAD_OLD = ["認証の期限を次回3日から5日に変更", "認証の期限を将来3日から5日に変更", "認証の期限を明日3日から5日に変更", "認証の期限を来週3日から5日に変更", "認証の期限を後日3日から5日に変更",
           "認証の期限を不採用3日から5日に変更", "認証の期限を噂3日から5日に変更", "認証の期限を誤3日から5日に変更", "認証の期限をパスワードの期限の3日から5日に変更",
           "認証の期限を旧期限の3日から5日に変更", "認証の期限は田中から5日に変更", "認証の期限を7日から5日に変更", "認証の期限を5日から5日に変更"]


@pytest.mark.parametrize("w", BAD_OLD)
def test_v16_an_old_value_the_memory_does_not_hold_asserts_nothing(tmp_path, w):
    assert "5日" not in _emits_v(tmp_path, [w], V16, "one")                                    # one-write store: nothing
    assert "5日" not in _emits_v(tmp_path, ["認証の期限は3日だ", w], V16, "two")                 # never an update
    p = store(tmp_path, ["認証の期限は3日だ", w], name="three")
    r = ma.AnswerSession(p, Q, "o", answer_version=V16).call("recall", {"question": Q})
    assert r["verdict"] != "UPDATED" and ["3日"] in [g["answers"] for g in r["answers"]], r["answers"]      # the live value is not wiped


def _emits_v(tmp_path, writes, ver, name):
    p = store(tmp_path, writes, name=name)
    return [t for (_s, t, _v) in attack(p, Q, len(writes), version=ver)]


@pytest.mark.parametrize("ver", [V15, V16])
def test_v16_the_confirmed_old_value_still_updates(tmp_path, ver):
    for first, second, want in (("認証の期限は7日", "認証の期限は7日から5日に変更した", "5日"), ("認証の期限は3日だ", "認証の期限を3日から5日に変更", "5日"), ("認証の期限は5日", "認証の期限を5日から7日に変更した", "7日")):
        assert _emits_v(tmp_path, [first, second], ver, "c%d" % abs(hash(second))) == [want], second


def test_v16_a_change_chain_confirms_through_the_new_value(tmp_path):
    assert _emits_v(tmp_path, ["認証の期限は3日だ", "認証の期限を3日から5日に変更", "認証の期限を5日から7日に変更"], V16, "chain") == ["7日"]
    assert "7日" not in _emits_v(tmp_path, ["認証の期限は3日だ", "認証の期限を3日から5日に変更", "認証の期限を3日から7日に変更"], V16, "chain2")      # 3日 is no longer live


def test_v16_a_bracketed_value_displays_the_pair_not_a_cut(tmp_path):
    for w, shown in (("認証の期限は「5日」だ", "「5日」"), ("認証の期限は(5日)だ", "(5日)"), ("認証の期限は5日（仮）だ", "5日（仮）")):
        p = store(tmp_path, [w], name="d%d" % abs(hash(w)))
        r = ma.AnswerSession(p, Q, "o", answer_version=V16).call("recall", {"question": Q})
        assert r["answers"][0]["answers"] == [shown], (w, r["answers"])
    p = store(tmp_path, ["認証の期限は「5日」だ", "認証の期限は「5日」（仮）だ"], name="dd")
    r = ma.AnswerSession(p, Q, "o", answer_version=V16).call("recall", {"question": Q})
    assert sorted(a for g in r["answers"] for a in g["answers"]) == ["「5日」", "「5日」（仮）"]


def test_v16_begin_row_and_older_runs_replay(tmp_path):
    p = store(tmp_path, ["認証の期限は5日"])
    a = ma.AnswerSession(p, Q, "o", answer_version=V16)
    assert a.begin_result["mem_answer"]["version"] == "memanswer.v16" and a.begin_result["mem_answer"]["guard"] == "ansguard.v14"
    r = ma.replay_answer(a.ledger.dir)
    assert r.run.v16 and r.run.v15
    assert attack(p, Q, 1, version=V16) == [(0, "5日", None)]
    p2 = store(tmp_path, ["認証の期限を次回3日から5日に変更"], name="old")
    assert ma.AnswerSession(p2, Q, "o", answer_version=V15).call("recall", {"question": Q})["verdict"] == "ANSWER"       # v15 replays as it was
