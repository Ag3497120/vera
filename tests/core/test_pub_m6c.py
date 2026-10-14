"""PUB-M6c tests (owner 2026-10-13, 「記憶の想起と出力の 4 点」 + the designer's decision on the default gate): the source slice is emitted for a value with . , - : / inside (weave_span.v4), one side of a contradiction
is refused (contested_value), the shape table stage 1 (shape.v3), CANDIDATES + bridge (ask.v3, qwords.v2), and the evidence version a memory answer run / session records and replays under.  The sentences are the real
ones of the meter v1 and of bank_ls dev.  No network, no API."""


import hashlib


import json


import os


import subprocess


import sys


import pytest


from verantyx.loom import evidence as ev


from verantyx.loom import memanswer as ma


from verantyx.loom import memask as mask


from verantyx.loom import memcross as mx


from verantyx.loom import memory as mem


from verantyx.loom import memqwords as qw


from verantyx.loom import memrecall as mr


from verantyx.loom import memshape as ms


from verantyx.loom.corpus import Corpus


from verantyx.loom.memguard import make_source


from mem_common import ROOT, new_store


V4 = mem.PROFILE_V4


M6C = mem.V4_VERSIONS_M6C


def store(tmp_path, writes, topics=(), name="mem", versions=M6C):
    st = new_store(tmp_path, name)
    s = st.begin("m", profile=V4, versions=versions)
    for t in topics:
        assert s.call("declare_topic", {"text": t})["ok"]
    for w in writes:
        assert s.write(w).get("ok"), w
    s.commit()
    return str(tmp_path / name)


def answer(path, question, version=ma.ANSWER_V4, **kw):
    a = ma.AnswerSession(path, question, "oracle", answer_version=version, **kw)
    return a, a.call("recall", {"question": question})


def weave(a, occ):
    return a.call("weave_span", {"sid": occ["sid"], "tier": "WORD", "first": occ["span"][0], "last": occ["span"][1]})


def occ_of(res, group=0, k=0):
    return res["answers"][group]["occurrences"][k]


def clauses(text, version=ms.SHAPES_V3):
    return ms.exchange(text, version).clauses


def arms(c):
    return [(a.particle, a.seat.text) for a in c.arms]


@pytest.mark.parametrize("sentence,question,value", [
    ("デモ用イメージのバージョンはv2.4です", "デモ用イメージのバージョンは何ですか？", "v2.4"),          # MEM-T01: emitted 'v24' (2 runs) before
    ("試薬費の上限は6.5万円です", "試薬費の上限はいくらですか？", "6.5万円"),                      # MEM-T03: '65万円'
    ("配布ビルドのバージョンは3.2.0-rc2です", "配布ビルドのバージョンは何ですか？", "3.2.0-rc2"),   # MEM-T04: '320rc2'
    ("取込マニフェストのバージョンはv0.9です", "取込マニフェストのバージョンは何ですか？", "v0.9"),   # MEM-T06: 'v09'
    ("広報チラシの印刷部数は1,400部です", "広報チラシの印刷部数は何部ですか？", "1,400部"),
    ("配布計画の開始時刻は12:30です", "配布計画の開始時刻は何時ですか？", "12:30"),
    ("見積書の締切は6/14です", "見積書の締切はいつですか？", "6/14"),
])
def test_a_value_with_joiners_inside_is_emitted_as_the_source_slice(tmp_path, sentence, question, value):
    p = store(tmp_path, [sentence])
    a, r = answer(p, question)
    assert r["verdict"] == "ANSWER" and r["answers"][0]["answers"] == [value]
    o = occ_of(r)
    assert o["verbatim"] is True and "readout" not in o                                    # recall: this stretch can be emitted as it stands
    w = weave(a, o)
    assert w["ok"] and w["wv"] == "weave_span.v4" and w["text"] == value                   # the weave reads out the source slice, joiners included
    e = a.call("emit", {})
    assert e["ok"] and e["text"] == value and e["output_sha"] == hashlib.sha256(value.encode("utf-8")).hexdigest()
    assert ma.answer_output(a.ledger.dir)["text"] == value
    assert ma.verify_answer(a.ledger.dir)["status"] == "OK" and ma.replay_answer(a.ledger.dir).status == "IDENTICAL"


def test_any_other_difference_stays_quote_not_verbatim(tmp_path):
    p = store(tmp_path, ["試験の規格は3×5です"])                                            # × is no joiner: the loom would read it out as 35
    a, r = answer(p, "試験の規格は何ですか？")
    o = occ_of(r)
    assert o["answer"] == "3×5" and o["verbatim"] is False and o["readout"] == "35"
    w = weave(a, o)
    assert w["ok"] is False and w["refusal"] == "quote_not_verbatim" and a.run.state.thread == []


def test_the_older_answer_runs_are_unchanged_they_still_refuse_the_slice(tmp_path):
    p = store(tmp_path, ["試薬費の上限は6.5万円です"], versions=None)
    a, r = answer(p, "試薬費の上限はいくらですか？", ma.ANSWER_V3)
    o = occ_of(r)
    assert o["verbatim"] is False and o["readout"] == "65万円"
    assert weave(a, o)["refusal"] == "quote_not_verbatim"


def test_the_change_clause_with_a_date_is_emitted_via_update(tmp_path):
    p = store(tmp_path, ["QA締切は6/12です", "QA締切は6/12から6/14に変更"])
    a, r = answer(p, "QA締切はいつですか？")
    assert r["verdict"] == "UPDATED" and r["answers"][0]["answers"] == ["6/14"]
    assert weave(a, occ_of(r))["ok"]
    e = a.call("emit", {})
    assert e["ok"] and e["text"] == "6/14" and e["via"] == "update"
    assert a.call("weave_span", {"sid": 0, "tier": "WORD", "first": "6", "last": "12", "wv": "weave_span.v4"})["refusal"] in ("replaced_value", "run_closed")
    assert ma.replay_answer(a.ledger.dir).status == "IDENTICAL"


def test_weave_span_v4_is_v3_when_there_is_no_joiner_and_a_v3_ledger_replays_as_it_was(tmp_path):
    p = store(tmp_path, ["会場費の上限は9万円です"])
    a, r = answer(p, "会場費の上限はいくらですか？")
    assert weave(a, occ_of(r))["ok"] and a.call("emit", {})["text"] == "9万円" and not a.run.joints
    p3 = store(tmp_path, ["会場費の上限は9万円です"], name="old", versions=None)
    a3, r3 = answer(p3, "会場費の上限はいくらですか？", ma.ANSWER_V3)
    assert weave(a3, occ_of(r3))["wv"] == "weave_span.v3" and a3.call("emit", {})["text"] == "9万円"
    assert ma.replay_answer(a3.ledger.dir).status == "IDENTICAL"


def test_an_emit_of_one_value_of_a_same_seat_choice_is_refused_contested_value(tmp_path):
    p = store(tmp_path, ["認証モジュールの担当は田中", "認証モジュールの担当は佐藤"])
    a, r = answer(p, "認証モジュールの担当は誰ですか？")
    assert r["verdict"] == "CHOICE" and r["choice_kind"] == "same_seat" and r["sources"] == 2
    assert weave(a, occ_of(r, 0))["ok"]
    e = a.call("emit", {})
    assert e["ok"] is False and e["refusal"] == "contested_value" and "abstain" in e["detail"]["hint"]
    assert a.closed() is None                                                               # the run is still open: the model abstains
    assert a.call("abstain", {"type": "contested"})["ok"]
    out = ma.answer_output(a.ledger.dir)
    assert out["status"] == "abstained" and out["type"] == "contested" and [g for g in out["recalls"][0]["answers"]] == [["田中"], ["佐藤"]]
    assert ma.verify_answer(a.ledger.dir)["status"] == "OK"


def test_the_older_answer_run_can_still_emit_one_side(tmp_path):
    p = store(tmp_path, ["認証モジュールの担当は田中", "認証モジュールの担当は佐藤"], versions=None)
    a, r = answer(p, "認証モジュールの担当は誰ですか？", ma.ANSWER_V3)
    assert r["verdict"] == "CHOICE" and weave(a, occ_of(r, 0))["ok"]
    assert a.call("emit", {})["ok"]                                                         # memanswer.v3 is as it was; the guard is memanswer.v4's


def test_a_value_the_memory_repeats_is_not_contested_and_a_single_answer_can_be_emitted(tmp_path):
    p = store(tmp_path, ["認証モジュールの担当は田中", "認証モジュールの担当は田中"])
    a, r = answer(p, "認証モジュールの担当は誰ですか？")
    assert r["verdict"] == "ANSWER" and weave(a, occ_of(r))["ok"] and a.call("emit", {})["text"] == "田中"


def test_the_tables_are_frozen_and_the_older_ones_are_untouched():
    assert ms.SHAPES_SHA == "1908323f8690db16ebc7ea90ff46e00cb175ba6fd61021b6f31468c72dff7497"
    assert ms.SHAPES_SHA_V2 == "7c4e3d08d76e59fab592339bdf20ccfaad556a61b2492a47726251a3dd69f9fc"
    assert ms.SHAPES_SHA_V3 == ms._shapes_sha_v3() and ms.SHAPES_SHA_V3 not in (ms.SHAPES_SHA, ms.SHAPES_SHA_V2)
    assert ms.SHAPE_TABLES == {"shape.v1": ms.SHAPES_SHA, "shape.v2": ms.SHAPES_SHA_V2} and ms.SHAPE_TABLES_ALL["shape.v3"] == ms.SHAPES_SHA_V3
    assert ms.exchange("次の束を見た", ms.SHAPES_V3).version == "shape.v3"
    with pytest.raises(ValueError):
        ms.exchange("x", "shape.v9")


@pytest.mark.parametrize("sentence,shape,centre,expected_arms", [
    ("次の束を見た", "F4", "見る", [("を", "束")]),                                            # LIGHT_PRED
    ("原本をしまった", "F4", "仕舞う", [("を", "原本")]),
    ("初回会合を始めた", "F4", "始める", [("を", "初回会合")]),
    ("脇に置き", "F4", "置く", [("に", "脇")]),                                                 # NI_LIGHT
    ("目印をつけ", "F4", "付ける", [("を", "目印")]),                                           # NOUN_HEAD
    ("試験用カードに目を通してから", "F4", "通す", [("を", "目"), ("に", "試験用カード")]),
    ("返却用箱の集荷日は11月19日と輸送表にある", "F3", "有る", [("が", "集荷日"), ("と", "11月19日"), ("に", "輸送表")]),      # EXIST_ARU
    ("読みにくさを探した", "F4", "探す", [("を", "読みにくさ")]),                             # SUFFIX_SA
    ("珪戸分室の閉室日は2032年10月31日", "F1", "閉室日", [("の", "珪戸分室")]),               # PREFIX
    ("寄贈資料の受け入れ方は、確認票を作った", "F3", "作る", [("が", "受け入れ方"), ("を", "確認票")]),      # FRAG_TOPIC
])
def test_shape_v3_reads_the_artefacts_of_stage_1(sentence, shape, centre, expected_arms):
    assert [c.shape for c in clauses(sentence, ms.SHAPES_V2)] != [shape] or shape in ("F3", "F4") and False   # shape.v2 did not read it as this
    cs = clauses(sentence)
    assert len(cs) == 1 and cs[0].shape == shape and cs[0].centre == centre and arms(cs[0]) == expected_arms


def test_the_quantity_and_the_adverbial_fragments():
    c = clauses("一つ足した")[0]
    assert c.shape == "F4" and c.centre == "足す" and c.quantity.text == "一つ"             # COUNTER_TSU
    c = clauses("念のため、確認票を作った")[0]
    assert c.shape == "F4" and [a.text for a in c.adverbial] == ["念のため"]                 # FRAG_ADV
    c = clauses("清掃、点検、記録を取った")[0]
    assert [a.text for a in c.adverbial] == ["清掃", "点検"] and c.centre == "取る"
    cs = clauses("清掃、点検。")
    assert [c.shape for c in cs] == ["F0"] and [a.text for a in cs[0].adverbial] == ["清掃"]   # no clause after them: they stay what they were (an F0 clause; v2 does the same with its adverbials)


@pytest.mark.parametrize("sentence", [
    "机の端まで拭いた",                                     # LIMITER (だけ まで ずつ): the particle carries the meaning
    "清掃手順も確認した",                                   # MO: subject or object?
    "窓口の掲示を机へ戻しておく",                           # HE: stage 2
    "配架表から先に目を通す",                               # KARA
    "混ぜない方針を置いた",                                 # NEGREL
    "部材番号ごとに安全資料を紐づける",                     # DISTRIB
    "隣の資料と取り違えないようにした",                     # NEG
    "現場では通りやすかった",                               # CASE_TOPIC: stage 2
    "先に取り出すことにした",                               # ことにした: a decision, not an event
    "出荷前の見本機チェックは岩黒紬が見ることになった",     # ことになった
    "集音マイクの高さは維持できている",                     # a verb after the value: no value clause
])
def test_shape_v3_leaves_the_constructions_that_change_the_meaning_as_f0(sentence):
    assert [c.shape for c in clauses(sentence, ms.SHAPES_V2)] == [c.shape for c in clauses(sentence)] and clauses(sentence)[0].shape == "F0"
    assert [c.reason for c in clauses(sentence, ms.SHAPES_V2)] == [c.reason for c in clauses(sentence)]


SAMPLE = ["認証モジュールの担当は田中", "認証の期限は金曜から月曜に変更", "QA締切は6/12から6/14に変更になった", "会議は東京で行う", "資料を送付した", "サーバーのポートは8080", "新館開館日は2032年11月7日",
          "窓口の掲示を机へ戻しておく", "来館者が迷いそうな角を洗い出した", "次の束を見た", "予備電池は問屋の予定表で24日着になっていた", "1,400部を印刷した", "認証端末の設置日は2032年10月2日から2032年10月4日に変更になった",
          "遅れている", "確認用の札の控えを作ってから、原本をしまった", "珪戸分室の閉室日は2032年10月31日"]


def test_a_clause_shape_v2_places_is_read_the_same_by_shape_v3():
    for t in SAMPLE:
        e2, e3 = ms.exchange(t, ms.SHAPES_V2), ms.exchange(t, ms.SHAPES_V3)
        placed = {c.text: c.to_obj() for c in e2.clauses if c.shape != "F0"}
        for c in e3.clauses:
            if c.text in placed:
                assert c.to_obj() == placed[c.text], t
        if e2.clauses and all(c.shape != "F0" for c in e2.clauses):
            assert [c.to_obj() for c in e3.clauses] == [c.to_obj() for c in e2.clauses], t        # a write v2 accepts is read the same


def test_a_new_reading_never_has_two_subjects():
    for t in ("開館準備の掲示文は、来館者の目線で順番を入れ替えた", "出荷前の見本機チェックは岩黒紬が見ることになった"):
        for c in clauses(t):
            assert sum(1 for a in c.arms if a.particle == "が") <= 1


def test_the_question_word_table_v2_is_a_new_version_and_v1_is_pinned():
    assert qw.QWORDS_SHA == "f6778156f2db076ee4d7f3892faa77f283ea258835f8f2951bf9844ceb0d3e21" and qw.QWORDS_SHA_V2 != qw.QWORDS_SHA
    assert qw.QWORDS_SHAS == {"qwords.v1": qw.QWORDS_SHA, "qwords.v2": qw.QWORDS_SHA_V2} and qw.table_entries() == 80
    assert qw.find_word("説明会はどの部屋で開きますか", qw.QWORDS_V2) == (4, "どの") and qw.find_word("説明会はどの部屋で開きますか") is None
    assert qw.find_word("どの日がいつですか", qw.QWORDS_V2) == (0, "どの")


def test_which_noun_is_one_question_word_in_ask_v3_only():
    q = mask.parse_question("ボランティア説明会はどの部屋で開きますか？", mask.ASK_V3)
    assert q.ok and q.qword == "どの部屋" and q.kind_noun == "部屋" and q.shape == "F3" and q.centre == "開く" and q.asked == "で" and q.fixed == (("が", "ボランティア説明会"),)
    assert mask.parse_question("ボランティア説明会はどの部屋で開きますか？").reason == "no_question_word"
    assert q.to_obj()["v"] == "ask.v3" and q.to_obj()["kind_noun"] == "部屋"


def test_a_relative_clause_is_read_by_its_last_noun_and_is_never_answered_by_it_alone(tmp_path):
    q = mask.parse_question("新館を開ける日はいつですか？", mask.ASK_V3)
    assert q.ok and q.relative and q.shape == "F2" and q.centre == "日" and q.path == () and q.qword == "いつ"
    assert mask.parse_question("新館を開ける日はいつですか？").reason == "frame_not_read:case_before_topic"          # ask.v2: not read
    assert not mask.parse_question("分室を閉じるのは何日ですか？", mask.ASK_V3).ok                                  # the last word before 「は」 is no noun: not read
    p = store(tmp_path, ["新館の日は5月1日です"])                                              # a position whose centre IS the last noun: still no answer by it alone
    a, r = answer(p, "新館を開ける日はいつですか？")
    assert r["verdict"] == "CANDIDATES" and r["answers"] == [] and r["route"] is None and r["question"]["relative"] is True
    assert r["candidates"][0]["phrase"] == "新館の日"


def test_the_v2_ask_is_unchanged_it_offers_no_candidates(tmp_path):
    p = store(tmp_path, ["新館開館日は2032年11月7日"], versions=None)
    a, r = answer(p, "新館を開ける日はいつですか？", ma.ANSWER_V3)
    assert r["verdict"] == "NONE" and "candidates" not in r and r["engine"] == "ask.v2" and r["qwords"] == qw.QWORDS_SHA


STORY = ["新館開館日は2032年11月7日", "棚ラベル照合の締切は2032年9月22日から2032年9月24日に変更になった", "ボランティア説明会の会場は研修室藍", "認証端末の検収日は2032年10月3日",
         "職員休憩室の内線番号は413", "蔵書の第一陣移送日は2032年10月15日"]


def test_recall_offers_candidates_with_their_sentence_and_never_answers(tmp_path):
    p = store(tmp_path, STORY)
    a, r = answer(p, "棚ラベルの確認作業はいつまでですか？")
    assert r["verdict"] == "CANDIDATES" and r["answers"] == [] and r["route"] is None and r["issues"][0] == "no_position"
    c = r["candidates"][0]
    assert c["rank"] == 1 and c["phrase"] == "棚ラベル照合の締切" and c["score"] == 2 and c["shared"] == ["棚", "ラベル"] and c["values"] == ["2032年9月24日"]
    assert c["entries"][0]["sentence"].startswith("棚ラベル照合の締切は") and c["bridge"] == {"question_word": "棚ラベルの確認作業", "memory_phrase": "棚ラベル照合の締切"}
    a, r = answer(p, "ボランティア説明会はどの部屋で開きますか？")
    assert r["verdict"] == "CANDIDATES" and r["candidates"][0]["phrase"] == "ボランティア説明会の会場" and r["candidates"][0]["score"] == 3
    assert [x["rank"] for x in r["candidates"]] == list(range(1, len(r["candidates"]) + 1)) and len(r["candidates"]) <= mask.CANDIDATE_CAP


def test_candidates_need_two_shared_units_and_a_value_of_the_type_the_word_asks(tmp_path):
    p = store(tmp_path, STORY)
    for q in ("新館の屋根の色は何ですか？", "蔵書の屋根の色は何ですか？"):                       # the absent questions: one shared unit at most
        a, r = answer(p, q)
        assert r["verdict"] in ("NONE",) and r.get("candidates") == [] and r["answers"] == []
    a, r = answer(p, "職員休憩室へつなぐ内線は何番ですか？")                                # 413 has no 「番」: the type filter of 何<counter>
    assert r["verdict"] == "NONE"
    a, r = answer(p, "新館を開ける日は何時ですか？")                                           # 何時 asks a clock; the date is no clock
    assert r["verdict"] == "NONE"
    a, r = answer(p, "認証端末の保守はいつですか？")                                           # two shared units (認証 端末) and a date: offered, as a candidate, never answered
    assert r["verdict"] == "CANDIDATES" and r["answers"] == [] and r["candidates"][0]["phrase"] == "認証端末の検収日"


def test_a_question_that_reaches_a_value_exactly_gets_no_candidates(tmp_path):
    p = store(tmp_path, STORY)
    a, r = answer(p, "認証端末の検収日はいつですか？")
    assert r["verdict"] == "ANSWER" and r["route"] == "exact" and "candidates" not in r and r["positions_found"] == 1


def test_the_model_confirms_a_candidate_with_a_bridge_and_only_then_recall_answers(tmp_path):
    p = store(tmp_path, STORY)
    q = "棚ラベルの確認作業はいつまでですか？"
    a, r = answer(p, q)
    assert r["verdict"] == "CANDIDATES"
    b = a.call("bridge", {"question_phrase": "確認作業", "memory_phrase": "棚ラベル照合の締切"})
    assert b["ok"] and b["origin"] == "constructed" and b["positions"] == 1 and b["question_word"] == "確認作業"
    r2 = a.call("recall", {"question": q})
    assert r2["verdict"] == "ANSWER" and r2["route"] == "bridge" and r2["answers"][0]["answers"] == ["2032年9月24日"] and r2["answers"][0]["occurrences"][0]["change"]["old"] == "2032年9月22日"
    assert ma.verify_answer(a.ledger.dir)["status"] == "OK" and ma.replay_answer(a.ledger.dir).status == "IDENTICAL"
    rows = [json.loads(ln) for ln in open(os.path.join(a.ledger.dir, "ops.jsonl"), encoding="utf-8")]
    assert [x["op"] for x in rows if x["actor"] == "model"] == ["begin", "recall", "bridge", "recall"] and rows[0]["result"]["rules"]["bridge"]


def test_a_bridge_refusals_and_the_alias_and_the_cap(tmp_path):
    p = store(tmp_path, STORY)
    a, r = answer(p, "棚ラベルの確認作業はいつまでですか？")
    assert a.call("bridge", {"question_phrase": "確認作業", "memory_phrase": "存在しない席"})["refusal"] == "unknown_phrase"
    assert a.call("bridge", {"question_phrase": "確認作業"})["ok"] is False
    assert a.call("bridge", {"question_phrase": "x", "question_word": "y", "memory_phrase": "棚ラベル照合の締切"})["refusal"] == "bad_args"
    assert a.call("bridge", {"question_phrase": "同じ", "memory_phrase": "同じ"})["refusal"] in ("bad_bridge", "unknown_phrase")
    assert a.call("bridge", {"question_word": "確認作業", "memory_phrase": "棚ラベル照合の締切"})["ok"]
    assert a.call("bridge", {"question_phrase": "確認作業", "memory_phrase": "棚ラベル照合の締切"})["refusal"] == "bridge_exists"
    for k in range(ma.BRIDGE_CAP - 1):
        assert a.call("bridge", {"question_phrase": "作業%d" % k, "memory_phrase": "新館開館日"})["ok"]
    assert a.call("bridge", {"question_phrase": "作業9", "memory_phrase": "新館開館日"})["refusal"] == "bridge_cap"
    v3 = ma.AnswerSession(store(tmp_path, STORY, name="v3", versions=None), "棚ラベルの確認作業はいつまでですか？", "m", answer_version=ma.ANSWER_V3)
    assert v3.call("bridge", {"question_phrase": "確認作業", "memory_phrase": "棚ラベル照合の締切"})["refusal"] == "unknown_tool"


def test_a_bridge_of_a_session_is_ledgered_carried_to_the_next_session_and_replays(tmp_path):
    st = new_store(tmp_path)
    s = st.begin("m", profile=V4, versions=M6C)
    for w in STORY:
        assert s.write(w)["ok"]
    q = "棚ラベルの確認作業はいつまでですか？"
    assert s.call("recall", {"question": q})["verdict"] == "CANDIDATES"
    b = s.call("bridge", {"question_phrase": "確認作業", "memory_phrase": "棚ラベル照合の締切"})
    assert b["ok"] and b["question_word"] == "確認作業" and b["positions"] == 1
    assert s.call("recall", {"question": q})["route"] == "bridge"
    s.commit()
    s2 = st.begin("m", profile=V4, versions=M6C)                                         # the next session sees it
    assert s2.call("recall", {"question": q})["route"] == "bridge" and s2.run.bridge_log[0]["phrase"] == "棚ラベル照合の締切"
    s2.commit()
    v = mem.verify_store(str(tmp_path / "mem"), mem.FROM_HEADER)
    assert v["status"] == "OK" and v["replay"]["status"] == "IDENTICAL"
    a, r = answer(str(tmp_path / "mem"), q)
    assert r["route"] == "bridge" and r["answers"][0]["answers"] == ["2032年9月24日"]


def test_a_bridge_made_through_an_old_session_keeps_its_old_rules(tmp_path):
    st = new_store(tmp_path)
    s = st.begin("m", profile=V4)                                                           # the bundle of PUB-M2..M6b
    s.write("新館の開館日は2032年11月7日")
    assert s.call("bridge", {"question_phrase": "x", "memory_phrase": "開館日"})["refusal"] == "bad_args"       # question_phrase is not an argument of the old bridge
    assert s.call("bridge", {"question_word": "開ける日", "memory_phrase": "新館の開館日"})["refusal"] == "unknown_phrase"      # a whole position is not a centre
    assert s.call("bridge", {"question_word": "開ける日", "memory_phrase": "開館日"})["ok"]
    s.commit()


def test_the_begin_row_records_the_versions_and_the_default_bundle_is_the_old_one(tmp_path):
    st = new_store(tmp_path, "new")
    h = st.begin("m", profile=V4, versions=M6C).run.header()
    assert h["shape"] == {"version": "shape.v3", "sha": ms.SHAPES_SHA_V3} and h["ask"] == {"version": "ask.v3"} and h["qwords"] == {"version": "qwords.v2", "sha": qw.QWORDS_SHA_V2}
    h0 = new_store(tmp_path, "old").begin("m", profile=V4).run.header()
    assert h0["shape"] == {"version": "shape.v2", "sha": ms.SHAPES_SHA_V2} and h0["ask"] == {"version": "ask.v2"} and h0["qwords"] == {"version": "qwords.v1", "sha": qw.QWORDS_SHA}
    with pytest.raises(Exception) as ei:
        new_store(tmp_path, "bad").begin("m", profile=V4, versions={"shape": "shape.v1"})
    assert getattr(ei.value, "type", "") == "bad_policy"
    with pytest.raises(Exception) as ei:
        new_store(tmp_path, "bad2").begin("m", profile=V4, versions={"ask": "ask.v3"})                      # ask.v3 reads qwords.v2
    assert getattr(ei.value, "type", "") == "bad_policy"
    with pytest.raises(Exception) as ei:
        new_store(tmp_path, "bad3").begin("m", profile=mem.PROFILE_V3, versions=M6C)
    assert getattr(ei.value, "type", "") == "bad_policy"


def test_one_store_one_bundle(tmp_path):
    st = new_store(tmp_path)
    s = st.begin("m", profile=V4, versions=M6C)
    s.write("新館開館日は2032年11月7日")
    s.commit()
    with pytest.raises(Exception) as ei:
        st.begin("m", profile=V4)
    assert getattr(ei.value, "type", "") == "policy_mismatch"
    with pytest.raises(Exception) as ei:
        ma.write_snapshot(str(tmp_path / "mem"), crosses=True)                                  # memanswer.v3 would rebuild the index with shape.v2
    assert getattr(ei.value, "type", "") == "versions_unverified"


def test_the_crosses_file_of_memanswer_v4_carries_the_versions_and_is_verified(tmp_path):
    p = store(tmp_path, STORY)
    snap = ma.write_snapshot(p, crosses=True, versions=True)
    data, decls, brs, vs = ma.read_crosses_v4(snap["crosses_path"])
    assert vs == M6C and decls == [] and brs == []
    with pytest.raises(Exception):
        ma.read_crosses(snap["crosses_path"])                                                   # a v3 reader refuses the extra key
    a = ma.AnswerSession(p, "新館開館日はいつですか？", "m", snapshot=snap, answer_version=ma.ANSWER_V4)
    b = a.begin_result["mem_answer"]
    assert b["version"] == "memanswer.v4" and b["ask"] == "ask.v3" and b["shape"] == "shape.v3" and b["qwords"] == "qwords.v2" and b["guard"] == "ansguard.v2" and b["readout"] == "weave_span.v4"
    assert a.run.index().shape_version == "shape.v3"


def test_a_store_written_with_the_new_bundle_replays_and_an_old_store_still_replays(tmp_path):
    for name, versions in (("new", M6C), ("old", None)):
        st = new_store(tmp_path, name)
        for k in range(2):
            s = st.begin("m", profile=V4, versions=versions)
            assert s.call("declare_topic", {"text": "新館準備"})["ok"]
            s.write("開館準備の掲示文は、来館者の目線で順番を入れ替えた" if k == 0 and versions else "新館開館日は2032年11月%d日" % (7 + k))
            s.commit()
        v = mem.verify_store(str(tmp_path / name), mem.FROM_HEADER)
        assert v["status"] == "OK" and v["replay"]["status"] == "IDENTICAL", (name, v)


def test_a_v2_bundle_session_refuses_what_shape_v3_accepts(tmp_path):
    st = new_store(tmp_path, "a")
    r = st.begin("m", profile=V4).write("次の束を見た")
    assert r["ok"] is False and r["refusal"] == "no_shape"
    r = new_store(tmp_path, "b").begin("m", profile=V4, versions=M6C).write("次の束を見た")
    assert r["ok"] is True and r["shape"]["v"] == "shape.v3" and r["shape"]["clauses"][0]["centre"] == "見る"


def test_the_default_gate_of_a_new_memory_answer_run_and_session_is_the_constant_and_is_recorded(tmp_path):
    assert mr.MEM_GATE_VERSION == ev.EVIDENCE_V6 and ma.ANSWER_EVIDENCE == (ev.EVIDENCE_V6, ev.SCOPE_CLAUSE)
    p = store(tmp_path, ["田中の担当は認証"])
    a = ma.AnswerSession(p, "田中の担当は何ですか？", "m", answer_version=ma.ANSWER_V4)
    assert a.begin_result["evidence_profile"] == {"version": "evidence.v6", "subject_scope": "clause"} and a.begin_result["mem_answer"]["evidence"] == "evidence.v6"
    s = new_store(tmp_path, "sess").begin("m", self_question=mem.LATEST)                       # what the doors pass: the gate of today, recorded explicitly
    h = s.run.header()
    assert (h["self_question"], h["evidence_version"]) == ("gate.evidence.v6+subject", "evidence.v6")
    assert "evidence.v6" in s.rows()[0]["result"]["rules"]["recall"] and "evidence.v2" not in s.rows()[0]["result"]["rules"]["recall"]
    h0 = new_store(tmp_path, "dflt").begin("m").run.header()                                    # the meaning of DEFAULT is frozen: replay never depends on a mutable default
    assert (h0["self_question"], h0["evidence_version"]) == ("gate.evidence.v2+subject", "evidence.v2") and mem.DEFAULT_HOOK_FACTORY is mr.GateSubjectSelfQuestion
    from verantyx.loom import memdoor as md
    d = md.StructureDoor(str(tmp_path / "door"), "blind", "m", profile=V4)
    assert d.begin_result["header"]["self_question"] == "gate.evidence.v6+subject" and d.begin_result["header"]["evidence_version"] == "evidence.v6"
    d.close()


def test_the_gate_v2_fixture_pins_the_original_gate(gate_v2, tmp_path):
    assert mr.MEM_GATE_VERSION == ev.EVIDENCE_V2 and ma.ANSWER_EVIDENCE == (ev.EVIDENCE_V2, "clause")
    s = new_store(tmp_path).begin("m", self_question=mem.LATEST)
    assert s.run.header()["self_question"] == "gate.evidence.v2+subject"


def test_every_gate_hook_is_registered_and_a_run_recorded_under_v2_replays_after_the_flip(tmp_path):
    assert {"gate.evidence.v2", "gate.evidence.v2+subject", "gate.evidence.v6", "gate.evidence.v6+subject"} <= set(mem.HOOKS)
    assert mr.hook_classes(ev.EVIDENCE_V6)[1]().subject_guard is True and mr.hook_classes(ev.EVIDENCE_V6)[0]().evidence_version == ev.EVIDENCE_V6
    p = store(tmp_path, ["田中の担当は認証"], versions=None)
    a = ma.AnswerSession(p, "田中の担当は何ですか？", "m", answer_version=ma.ANSWER_V3, evidence=ma.LEGACY_EVIDENCE)           # a run recorded under evidence.v2
    assert a.begin_result["evidence_profile"]["version"] == "evidence.v2"
    r = a.call("recall", {"question": "田中の担当は何ですか？"})
    assert weave(a, occ_of(r))["ok"] and a.call("emit", {})["text"] == "認証"
    rep = ma.replay_answer(a.ledger.dir)
    assert rep.status == "IDENTICAL" and rep.run.evidence == ma.LEGACY_EVIDENCE                  # replayed under what it recorded, not under the constant
    st = new_store(tmp_path, "oldgate")
    s = st.begin("m", self_question=mr.GateSubjectSelfQuestion())                               # a session recorded with the v2 hook
    s.write("田中の担当は認証")
    s.commit()
    v = mem.verify_store(str(tmp_path / "oldgate"), mem.FROM_HEADER)
    assert v["status"] == "OK" and v["replay"]["status"] == "IDENTICAL"


def test_answer_runs_v1_v2_recall_with_the_gate_the_run_recorded(tmp_path):
    st = new_store(tmp_path)
    s = st.begin("m")
    s.write("田中の担当は認証")
    s.commit()
    a = ma.AnswerSession(str(tmp_path / "mem"), "田中の担当は何ですか？", "m", answer_version=ma.ANSWER_VERSION)
    r = a.call("recall", {"question": "田中の担当は何ですか？"})
    assert r["evidence"] == "evidence.v6" and a.begin_result["evidence_profile"]["version"] == "evidence.v6"
    assert ma.replay_answer(a.ledger.dir).status == "IDENTICAL"


def test_position_text_and_positions_text(tmp_path):
    rows = [{"kind": "base", "sent": x, "source": make_source("t", 1, i)} for i, x in enumerate(["認証モジュールの担当は田中", "締切は金曜", "A社の経理部の担当は佐藤"])]
    ix = mx.build_index(rows, shape_version=ms.SHAPES_V3)
    assert [mx.position_text(p) for p in ix.positions] == ["認証モジュールの担当", "締切", "A社の経理部の担当"]
    assert ix.positions_text("認証モジュールの担当") == ix.positions_text("認証モジュール担当") == (ix.positions[0],)           # with or without 「の」
    assert ix.positions_text("経理部の担当") == () and mx.position_text(("F3", "開く", ())) is None


@pytest.mark.parametrize("seed", ["0", "1", "12345"])
def test_bytes_are_identical_across_hash_seeds(seed):
    code = ("import json;from verantyx.loom import memask as mask, memcross as mx, memshape as ms, memqwords as qw;from verantyx.loom.corpus import Corpus;from verantyx.loom import memory as mem;"
            "from verantyx.loom.memguard import make_source\n"
            "S=['次の束を見た','寄贈資料の受け入れ方は、確認票を作った','珪戸分室の閉室日は2032年10月31日','念のため、確認票を作った','読みにくさを探した','一つ足した','集音マイクの高さは維持できている']\n"
            "rows=[{'kind':'base','sent':x,'source':make_source('t',1,i)} for i,x in enumerate(['新館開館日は2032年11月7日','棚ラベル照合の締切は2032年9月24日','ボランティア説明会の会場は研修室藍','試薬費の上限は6.5万円です'])]\n"
            "ix=mx.build_index(rows,shape_version=ms.SHAPES_V3);c=Corpus(mem.rows_bytes(rows))\n"
            "R=[mask.recall(ix,rows,c,q,ask=mask.ASK_V3) for q in ['新館を開ける日はいつですか？','棚ラベルの確認作業はいつまでですか？','ボランティア説明会はどの部屋で開きますか？','試薬費の上限はいくらですか？']]\n"
            "print(ms.SHAPES_SHA_V3,ix.index_sha);print(json.dumps([ms.exchange(s,ms.SHAPES_V3).to_obj() for s in S]+R,ensure_ascii=False,sort_keys=True))")
    env = dict(os.environ, PYTHONHASHSEED=seed, PYTHONPATH=ROOT)
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, env=env, cwd=ROOT, check=True).stdout
    ref = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, env=dict(env, PYTHONHASHSEED="0"), cwd=ROOT, check=True).stdout
    assert out == ref and out.startswith(ms.SHAPES_SHA_V3) and "CANDIDATES" in out
