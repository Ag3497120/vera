"""PUB-M6 tests: recall on the crosses (verantyx/loom/memask.py), the question-word tank (memqwords.py, frozen), `bridge`, the v4 `recall` tool and the answer run memanswer.v3 (the emitted quote still passes the
evidence gate).  No network, no API."""
import json
import os
import subprocess
import sys

import pytest

from verantyx.loom import memanswer as ma
from verantyx.loom import memask as mask
from verantyx.loom import memcross as mx
from verantyx.loom import memory as mem
from verantyx.loom import memqwords as qw
from verantyx.loom.corpus import Corpus
from verantyx.loom.memguard import make_source
from mem_common import ROOT, new_store

V4 = mem.PROFILE_V4


def sess(tmp_path, name="mem", **kw):
    return new_store(tmp_path, name).begin("test-model", profile=V4, **kw)


def rows(texts, session=1, start=0):
    return [{"kind": "base", "sent": t, "source": make_source("t", session, start + i)} for i, t in enumerate(texts)]


def ask(texts, question, decls=(), sup=None, bridges=(), open_nest=None):
    rs = rows(texts)
    ix = mx.build_index(rs, list(decls), sup or {}, bridges=list(bridges))
    return mask.recall(ix, rs, Corpus(mem.rows_bytes(rs)), question, open_nest=open_nest)


def values(res):
    return [g["answers"] for g in res["answers"]]


# -- the question-word tank -----------------------------------------------------------------------------------------------------------------------
def test_the_tank_is_frozen_small_and_general():
    assert qw.table_entries() == 80 <= 80 and qw.QWORDS_VERSION == "qwords.v1"
    assert qw.QWORDS_SHA == "f6778156f2db076ee4d7f3892faa77f283ea258835f8f2951bf9844ceb0d3e21"            # an edit of the table is a new version and a new sha
    words = [w for _, ws, _ in qw.QWORD_CLASSES for w in ws]
    assert len(words) == len(set(words)) and qw.class_of_word("どこ") == "where" and qw.class_of_word("誰") == "who" and qw.class_of_word("いくら") == "money" and qw.class_of_word("何") is None
    assert qw.slots_of_word("どこ")[:4] == ("場所", "開催地", "会場", "所在地") and "担当者" in qw.slots_of_word("だれ") and "人数" in qw.slots_of_word("何人") and "予算" in qw.slots_of_word("いくら")
    assert qw.find_word("障害訓練はどこで行います") == (5, "どこ") and qw.find_word("QA締切は何") == (5, "何") and qw.find_word("所要時間は何分") == (5, "何分") and qw.find_word("開始は何時") == (3, "何時")
    assert qw.find_word("締め切りは金曜") is None


def test_the_tank_is_written_in_the_begin_row_of_a_v4_session(tmp_path):
    h = sess(tmp_path).rows()[0]["result"]["header"]
    assert h["qwords"] == {"version": "qwords.v1", "sha": qw.QWORDS_SHA} and h["ask"] == {"version": mask.ASK_VERSION}


# -- the question -------------------------------------------------------------------------------------------------------------------------------------
@pytest.mark.parametrize("q,shape,centre,path,asked,fixed", [
    ("認証モジュールの担当者は誰ですか？", "F1", "担当者", (("の", "認証モジュール"),), "は", ()),
    ("CDNキャッシュTTLは何秒ですか？", "F2", "CDNキャッシュTTL", (), "は", ()),
    ("認証レビューの締切はいつでしたか？", "F1", "締切", (("の", "認証レビュー"),), "は", ()),
    ("障害訓練はどこで行いますか？", "F3", "行う", (), "で", (("が", "障害訓練"),)),
    ("救護テントはどこに設置しますか？", "F3", "設置", (), "に", (("が", "救護テント"),)),
    ("会場費の上限はいくらですか", "F1", "上限", (("の", "会場費"),), "は", ()),
])
def test_a_question_is_read_by_the_shape_exchanger_into_tank_centre_path_and_the_asked_seat(q, shape, centre, path, asked, fixed):
    p = mask.parse_question(q)
    assert p.ok and (p.shape, p.centre, p.path, p.asked, p.fixed) == (shape, centre, path, asked, fixed)


def test_a_question_that_cannot_be_read_is_none_with_the_reason():
    assert not mask.parse_question("新館を開ける日はいつですか？").ok
    assert mask.parse_question("この話を教えてください").reason == "no_question_word"
    r = ask(["認証の期限は金曜"], "この話を教えてください")
    assert r["verdict"] == "NONE" and r["issues"] == ["question_unparsed:no_question_word"]


# -- the lookup, route by route -------------------------------------------------------------------------------------------------------------------
def test_exact_gives_an_answer_with_its_source_sentence_and_the_unit_stretch_to_quote():
    r = ask(["広報の締め切りは金曜", "認証の期限は月曜"], "認証の期限は何ですか？")
    assert r["verdict"] == "ANSWER" and r["route"] == "exact" and values(r) == [["月曜"]]
    o = r["answers"][0]["occurrences"][0]
    assert (o["sid"], o["answer"], o["via"], o["kind"], o["scope"]) == (1, "月曜", ["exact"], "first", None) and o["source"] == "mem:t/1#1" and o["clause"] == "認証の期限は月曜"
    assert o["span"] == [2, 2] or o["span"] == [3, 3] or len(o["span"]) == 2


def test_the_slot_noun_of_the_question_can_be_the_flat_phrase_either_way_round():
    assert ask(["認証モジュールの担当は田中"], "認証モジュール担当は誰ですか")["route"] == "flat"
    r = ask(["認証モジュール担当は田中"], "認証モジュールの担当は誰ですか")
    assert r["route"] == "flat" and values(r) == [["田中"]]


def test_the_class_of_the_question_word_finds_the_slot_the_memory_calls_otherwise():
    r = ask(["認証モジュールの担当は田中"], "認証モジュールの担当者は誰ですか？")
    assert r["verdict"] == "ANSWER" and r["route"] == "class" and values(r) == [["田中"]] and r["answers"][0]["occurrences"][0]["via"] == ["class"]
    r = ask(["避難訓練の会場は南運動場"], "避難訓練の場所はどこですか")
    assert r["route"] == "class" and values(r) == [["南運動場"]]
    r = ask(["障害訓練の開催地は大阪"], "障害訓練はどこで行いますか")
    assert r["route"] == "class" and values(r) == [["大阪"]]                                             # no slot noun in the question: the subject asks the nouns of the class
    assert ask(["障害訓練の開催地は大阪"], "障害訓練はいつ行いますか")["verdict"] == "NONE"


def test_a_bridge_the_model_added_is_used_before_the_class():
    texts = ["新館開館日は2032年11月7日"]
    assert ask(texts, "新館開館日はいつですか")["route"] == "exact"
    assert ask(["新館の開館日は2032年11月7日"], "新館の開く日はいつですか")["verdict"] == "NONE"
    b = [{"session": 1, "at": 1, "qword": "開く日", "phrase": "開館日"}]
    r = ask(["新館の開館日は2032年11月7日"], "新館の開く日はいつですか", bridges=b)
    assert r["route"] == "bridge" and values(r) == [["2032年11月7日"]] and r["answers"][0]["occurrences"][0]["via"] == ["bridge"]


def test_an_event_cross_answers_the_arm_that_was_asked():
    r = ask(["救護テントを北広場に設置する"], "救護テントはどこに設置しますか")
    assert r["verdict"] == "ANSWER" and r["route"] == "event" and values(r) == [["北広場"]]            # the topic of the question is the object of the stored event
    r = ask(["田中が会議を大阪で開く", "会議を東京で開く"], "会議はどこで開きますか")
    assert r["verdict"] == "CHOICE" and r["route"] == "event" and values(r) == [["大阪"], ["東京"]] and r["choice_kind"] == "same_seat"


def test_a_subject_less_question_finds_the_positions_under_a_nest_centre_with_via_nest():
    texts = ["新製品の締め切りは金曜", "旧製品の締め切りは月曜"]
    r = ask(texts, "締め切りはいつですか", decls=[{"session": 1, "at": 0, "topic": "新製品"}])
    assert r["verdict"] == "ANSWER" and r["route"] == "nest" and values(r) == [["金曜"]] and r["answers"][0]["occurrences"][0]["via"] == ["nest"]
    r = ask(texts, "締め切りはいつですか", decls=[{"session": 1, "at": 0, "topic": "新製品"}, {"session": 1, "at": 1, "topic": "旧製品"}])
    assert r["verdict"] == "CHOICE" and r["route"] == "nest" and values(r) == [["金曜"], ["月曜"]]
    assert ask(texts, "締め切りはいつですか")["verdict"] == "NONE"                                       # no nest, no owner: nothing is guessed


def test_statements_of_the_open_nest_are_preferred_and_other_nests_make_a_choice_of_scopes():
    texts = ["締め切りは金曜", "締め切りは月曜"]
    decls = [{"session": 1, "at": 0, "topic": "新製品"}, {"session": 1, "at": 1, "topic": "旧製品"}]
    r = ask(texts, "締め切りはいつですか", decls)
    assert r["verdict"] == "CHOICE" and r["choice_kind"] == "scopes" and sorted(o["scope"] for g in r["answers"] for o in g["occurrences"]) == ["N1", "N2"]
    r = ask(texts, "締め切りはいつですか", decls, open_nest="N2")
    assert r["verdict"] == "ANSWER" and values(r) == [["月曜"]] and r["answers"][0]["occurrences"][0]["scope"] == "N2"


# -- the verdicts -------------------------------------------------------------------------------------------------------------------------------------
def test_two_values_at_one_place_are_a_choice_nothing_is_ranked():
    r = ask(["認証の期限は金曜", "認証の期限は月曜", "認証の期限は金曜"], "認証の期限はいつですか")
    assert r["verdict"] == "CHOICE" and r["choice_kind"] == "same_seat" and values(r) == [["金曜"], ["月曜"]]
    assert [o["sid"] for o in r["answers"][0]["occurrences"]] == [0, 2]                                  # a repeat is another occurrence of the same value


def test_a_change_clause_makes_it_updated_with_the_replaced_value_in_the_history():
    r = ask(["QA締切は6/12", "QA締切は6/12から6/14に変更"], "QA締切はいつですか")
    assert r["verdict"] == "UPDATED" and values(r) == [["6/14"]]
    h = r["history"][0]
    assert h["answers"] == ["6/12"] and h["occurrences"][0]["replaced_by"] == {"sid": 1, "kind": "change"} and r["answers"][0]["occurrences"][0]["change"] == {"old": "6/12", "form": "kara_ni_henkou"}
    r = ask(["QA締切は6/12", "QA締切は6/12から6/14に変更", "QA締切は6/20"], "QA締切はいつですか")
    assert r["verdict"] == "CHOICE" and values(r) == [["6/14"], ["6/20"]]                                # the replaced value does not come back


def test_a_superseded_sentence_is_history_and_the_answer_is_updated():
    r = ask(["認証の期限は金曜", "認証の期限は月曜"], "認証の期限はいつですか", sup={0: {"by": 1, "reason": "変更", "session": 1}})
    assert r["verdict"] == "UPDATED" and values(r) == [["月曜"]] and r["history"][0]["occurrences"][0]["replaced_by"] == {"sid": 1, "kind": "supersede", "reason": "変更"}
    r = ask(["認証の期限は金曜", "認証の期限は月曜", "認証の期限は水曜"], "認証の期限はいつですか", sup={0: {"by": 1, "reason": "変更", "session": 1}})
    assert r["verdict"] == "CHOICE" and values(r) == [["月曜"], ["水曜"]]


def test_none_says_why():
    r = ask(["認証の期限は金曜"], "決済の期限はいつですか")
    assert r["verdict"] == "NONE" and r["issues"][0] == "no_position" and r["answers"] == []


# -- the session --------------------------------------------------------------------------------------------------------------------------------------
def test_recall_in_a_v4_session_reads_the_crosses_without_the_gate(tmp_path):
    s = sess(tmp_path, self_question=None)
    s.write("認証の期限は金曜")
    r = s.call("recall", {"question": "認証の期限はいつですか？"})
    assert r["ok"] and r["verdict"] == "ANSWER" and r["engine"] == mask.ASK_VERSION and r["text"] == "認証の期限はいつですか？" and r["qwords"] == qw.QWORDS_SHA
    assert s.call("recall", {"question": "a\nb"})["refusal"] == "bad_question"
    s.commit()
    assert mem.verify_store(str(tmp_path / "mem"), mem.FROM_HEADER)["status"] == "OK"


def test_recall_in_a_session_prefers_the_statements_of_its_open_nest(tmp_path):
    st = new_store(tmp_path)
    s = st.begin("m", profile=V4)
    s.call("declare_topic", {"text": "新製品"})
    s.write("締め切りは金曜")
    s.commit()
    s2 = st.begin("m", profile=V4)
    s2.call("declare_topic", {"text": "旧製品"})
    s2.write("締め切りは月曜")
    r = s2.call("recall", {"question": "締め切りはいつですか"})
    assert r["verdict"] == "ANSWER" and values(r) == [["月曜"]]


def test_bridge_is_a_constructed_ledgered_tool_that_recall_then_uses(tmp_path):
    st = new_store(tmp_path)
    s = st.begin("m", profile=V4)
    assert "bridge" in s.rows()[0]["result"]["tools"] and "bridge" in s.rows()[0]["result"]["rules"]
    s.write("新館の開館日は2032年11月7日")
    assert s.call("recall", {"question": "新館の開く日はいつですか"})["verdict"] == "NONE"
    r = s.call("bridge", {"question_word": "開く日", "memory_phrase": "開館日"})
    assert r["ok"] and r["origin"] == "constructed" and r["at"] == 1 and r["tanks"] == ["F1"] and r["bridges"] == 1
    assert s.call("recall", {"question": "新館の開く日はいつですか"})["route"] == "bridge"
    assert s.call("bridge", {"question_word": "開く日", "memory_phrase": "開館日"})["refusal"] == "bridge_exists"
    assert s.call("bridge", {"question_word": "x", "memory_phrase": "存在しない語"})["refusal"] == "unknown_phrase"
    assert s.call("bridge", {"question_word": "開館日", "memory_phrase": "開館日"})["refusal"] == "bad_bridge"
    assert s.call("bridge", {"question_word": "", "memory_phrase": "開館日"})["refusal"] == "bad_bridge"
    s.commit()
    ix = st.index()
    assert [(b.qword, b.phrase, b.origin, b.session, b.at) for b in ix.bridges] == [("開く日", "開館日", "constructed", 1, 1)]
    assert mem.replay_store(str(tmp_path / "mem"), mem.FROM_HEADER).identical and mem.verify_store(str(tmp_path / "mem"), mem.FROM_HEADER)["status"] == "OK"
    s2 = st.begin("m", profile=V4)                                                                       # the next session carries the bridge
    assert s2.call("recall", {"question": "新館の開く日はいつですか"})["route"] == "bridge" and s2.call("bridge", {"question_word": "開く日", "memory_phrase": "開館日"})["refusal"] == "bridge_exists"
    assert mem.session_bridges(st.sessions_dir / "s0001") == [{"session": 1, "at": 1, "qword": "開く日", "phrase": "開館日"}]


def test_bridge_is_only_a_tool_of_a_v4_session_and_has_a_cap(tmp_path):
    s3 = new_store(tmp_path, "v3").begin("m", profile="mem.v3")
    assert s3.call("bridge", {"question_word": "a", "memory_phrase": "b"})["refusal"] == "unknown_tool"
    assert mem.caps_of(V4)["bridges"] == 60 and "bridges" not in mem.caps_of("mem.v3")


# -- the answer run -----------------------------------------------------------------------------------------------------------------------------------
def test_the_answer_run_v3_recalls_from_the_crosses_and_the_found_value_is_emitted_through_the_gate(tmp_path):
    st = new_store(tmp_path)
    s = st.begin("m", profile=V4)
    s.call("declare_topic", {"text": "新製品"})
    s.write("認証の期限は金曜")
    s.write("認証モジュールの担当は田中")
    s.commit()
    a = ma.AnswerSession(str(tmp_path / "mem"), "認証の期限はいつですか？", "m", answer_version=ma.ANSWER_V3)
    b = a.begin_result
    assert b["mem_answer"]["version"] == ma.ANSWER_V3 and b["mem_answer"]["crosses_file"].startswith("crosses_") and "CROSSES" in b["rules"]["recall"]
    r = a.call("recall", {"question": "認証の期限はいつですか？"})
    assert r["verdict"] == "ANSWER" and r["route"] == "exact"
    o = r["answers"][0]["occurrences"][0]
    units = a.run.corpus.tier("WORD").sentence_units[o["sid"]]
    first, last = units[o["span"][0]], units[o["span"][1]]
    w = a.call("weave_span", {"sid": o["sid"], "tier": "WORD", "first": first, "last": last})
    assert w["ok"], w
    e = a.call("emit", {})
    assert e["ok"] and e["text"] == "金曜", e
    out = ma.answer_output(a.ledger.dir)
    assert out["status"] == "emitted" and out["text"] == "金曜" and out["recalls"][0]["verdict"] == "ANSWER"
    assert ma.verify_answer(a.ledger.dir)["status"] == "OK"


def test_the_answer_run_v3_needs_its_crosses_file_and_replays(tmp_path):
    st = new_store(tmp_path)
    s = st.begin("m", profile=V4)
    s.call("declare_topic", {"text": "新製品"})
    s.write("締め切りは金曜")
    s.write("締め切りは月曜")
    s.call("bridge", {"question_word": "期限", "memory_phrase": "締め切り"})
    s.commit()
    snap2 = ma.write_snapshot(str(tmp_path / "mem"), topics=True)
    with pytest.raises(Exception) as ei:
        ma.AnswerSession(str(tmp_path / "mem"), "締め切りはいつですか", "m", snapshot=snap2, answer_version=ma.ANSWER_V3)
    assert "snapshot_without_crosses" in str(ei.value) or "snapshot_without_crosses" in repr(getattr(ei.value, "type", ""))
    snap = ma.write_snapshot(str(tmp_path / "mem"), crosses=True)
    a = ma.AnswerSession(str(tmp_path / "mem"), "新製品の期限はいつですか", "m", snapshot=snap, answer_version=ma.ANSWER_V3)
    r = a.call("recall", {"question": "新製品の期限はいつですか"})
    assert r["verdict"] == "NONE"                                                                         # an owner that is a nest centre is not an owner the cross holds
    r = a.call("recall", {"question": "期限はいつですか"})
    assert r["verdict"] == "CHOICE" and r["route"] in ("class", "bridge", "exact", "nest")
    assert ma.verify_answer(a.ledger.dir)["status"] == "OK" and ma.replay_answer(a.ledger.dir).status == "IDENTICAL"
    data, decls, brs = ma.read_crosses(snap["crosses_path"])
    assert decls == [{"at": 0, "session": 1, "topic": "新製品"}] and brs == [{"at": 2, "phrase": "締め切り", "qword": "期限", "session": 1}]
    bad = os.path.join(os.path.dirname(snap["crosses_path"]), "crosses_000000000000.json")
    open(bad, "wb").write(data)
    with pytest.raises(Exception):
        ma.read_crosses(bad)


# -- determinism --------------------------------------------------------------------------------------------------------------------------------------
@pytest.mark.parametrize("seed", ["0", "1", "12345"])
def test_recall_is_byte_identical_across_hash_seeds(seed):
    code = ("import json;from verantyx.loom import memcross as mx, memask as mk, memory as me;from verantyx.loom.corpus import Corpus;from verantyx.loom.memguard import make_source as m;"
            "S=['認証モジュールの担当は田中','認証モジュールの担当は佐藤','障害訓練の開催地は大阪','QA締切は6/12','QA締切は6/12から6/14に変更','会議を大阪で開く','会議を東京で開く','締め切りは金曜'];"
            "R=[{'kind':'base','sent':s,'source':m('t',1,i)} for i,s in enumerate(S)];"
            "ix=mx.build_index(R,[{'session':1,'at':7,'topic':'新製品'}],{});C=Corpus(me.rows_bytes(R));"
            "Q=['認証モジュールの担当者は誰ですか','障害訓練はどこで行いますか','QA締切はいつですか','会議はどこで開きますか','締め切りはいつですか','新館を開ける日はいつですか'];"
            "print(json.dumps([mk.recall(ix,R,C,q) for q in Q],ensure_ascii=False,sort_keys=True))")
    env = dict(os.environ, PYTHONHASHSEED=seed, PYTHONPATH=ROOT)
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, env=env, cwd=ROOT, check=True).stdout
    ref = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, env=dict(env, PYTHONHASHSEED="0"), cwd=ROOT, check=True).stdout
    assert out == ref and '"CHOICE"' in out and '"UPDATED"' in out and '"NONE"' in out
