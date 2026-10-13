"""PUB-M6b tests: the wrong emits of the PUB-M5/M6 measurement (meter v1, `updated/emitted_wrong: 16`), the guards of the answer run v3 (`quote_not_verbatim`, `replaced_value`) and the questions the gate is handed
after a nest or for a change clause (`via: nest`, `via: update`).  The cases are the real ones of meter v1 (the sentences the models wrote).  No network, no API."""
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


def store(tmp_path, writes, topics=(), name="mem"):
    st = new_store(tmp_path, name)
    s = st.begin("m", profile=V4)
    for t in topics:
        assert s.call("declare_topic", {"text": t})["ok"]
    for w in writes:
        assert s.write(w).get("ok"), w
    s.commit()
    return str(tmp_path / name)


def answer(path, question):
    a = ma.AnswerSession(path, question, "oracle", answer_version=ma.ANSWER_V3)
    return a, a.call("recall", {"question": question})


def weave(a, occ):
    return a.call("weave_span", {"sid": occ["sid"], "tier": "WORD", "first": occ["span"][0], "last": occ["span"][1]})


def occ_of(res, group=0, k=0):
    return res["answers"][group]["occurrences"][k]


# -- 1. the wrong emits: the loom reads a value out WITHOUT its punctuation ---------------------------------------------------------------------------------
@pytest.mark.parametrize("sentence,question,value,readout", [
    ("デモ用イメージのバージョンは v2.4 です", "デモ用イメージのバージョンは何ですか？", "v2.4", "v24"),                 # MEM-T01: emitted_wrong 'v24' (2 runs)
    ("試薬費の上限は6.5万円です", "試薬費の上限はいくらですか？", "6.5万円", "65万円"),                          # MEM-T03: emitted_wrong '65万円' (5 runs); 6.5 emitted as 65
    ("配布ビルドのバージョンは3.2.0-rc2です", "配布ビルドのバージョンは何ですか？", "3.2.0-rc2", "320rc2"),         # MEM-T04: emitted_wrong '320rc2' (3 runs)
    ("取込マニフェストのバージョンは v0.9 です", "取込マニフェストのバージョンは何ですか？", "v0.9", "v09"),          # MEM-T06: emitted_wrong 'v09' (6 runs)
])
def test_a_value_the_loom_would_read_out_without_its_punctuation_is_never_emitted(tmp_path, sentence, question, value, readout):
    p = store(tmp_path, [sentence])
    a, r = answer(p, question)
    assert r["verdict"] == "ANSWER" and r["answers"][0]["answers"] == [value]
    o = occ_of(r)
    assert o["verbatim"] is False and o["readout"] == readout                      # recall says so before anything is woven
    w = weave(a, o)
    assert w["ok"] is False and w["refusal"] == "quote_not_verbatim" and w["detail"]["readout"] == readout and value in w["detail"]["source"]
    assert a.run.state.thread == [] and a.closed() is None                         # nothing was woven, the run is still open
    assert a.call("abstain", {"type": "cannot_weave"})["ok"]
    assert ma.answer_output(a.ledger.dir)["status"] == "abstained" and ma.verify_answer(a.ledger.dir)["status"] == "OK"


def test_the_new_value_of_a_change_clause_with_a_date_is_not_emitted_as_614(tmp_path):
    p = store(tmp_path, ["QA締切は6/12です", "QA締切は6/12から6/14に変更"])
    a, r = answer(p, "QA締切はいつですか？")
    assert r["verdict"] == "UPDATED" and r["answers"][0]["answers"] == ["6/14"] and r["history"][0]["answers"] == ["6/12"]
    o = occ_of(r)
    assert o["verbatim"] is False and o["readout"] == "614" and o["change"]["form"] == "kara_ni_henkou"
    assert weave(a, o)["refusal"] == "quote_not_verbatim"
    assert mask.completions(a.run.index(), r, "QA締切はいつですか？") == []              # a completion is only offered for a stretch that can be emitted as it stands


def test_a_value_without_punctuation_is_still_emitted_and_whitespace_is_not_punctuation(tmp_path):
    p = store(tmp_path, ["会場費の上限は9万円です"])
    a, r = answer(p, "会場費の上限はいくらですか？")
    o = occ_of(r)
    assert o["verbatim"] is True and "readout" not in o
    assert weave(a, o)["ok"] and a.call("emit", {})["text"] == "9万円"


def test_quote_check_compares_the_readout_with_the_sentence_up_to_the_loom_own_equivalence():
    rs = [{"kind": "base", "sent": x, "source": make_source("t", 1, i)} for i, x in enumerate(["QA締切は6/14です", "会場費の上限は9万円です"])]
    c = Corpus(mem.rows_bytes(rs))
    assert c.tier("WORD").sentence_units[0] == ("QA", "締切", "6", "14") and c.tier("WORD").sentence_units[1] == ("会場", "費", "上限", "9", "万", "円")
    readout, source, verbatim = mask.quote_check(c, 0, 2, 3)
    assert (readout, source, verbatim) == ("614", "6/14", False)
    assert mask.quote_check(c, 1, 3, 5) == ("9万円", "9万円", True)
    assert mask._squash("カール・マルクス 1") == "カールマルクス1" and mask._squash("6.5") == "6.5"


# -- 2. an UPDATED verdict emits the latest value only ---------------------------------------------------------------------------------------------------
def test_the_replaced_value_of_a_change_is_never_a_quote_not_from_its_own_sentence_nor_from_the_change_sentence(tmp_path):
    p = store(tmp_path, ["認証の期限は金曜", "認証の期限は金曜から月曜に変更"])
    a, r = answer(p, "認証の期限はいつですか？")
    assert r["verdict"] == "UPDATED" and r["answers"][0]["answers"] == ["月曜"] and r["history"][0]["answers"] == ["金曜"]
    old = r["history"][0]["occurrences"][0]
    assert old["sid"] == 0 and weave(a, old)["refusal"] == "replaced_value"
    again = a.call("weave_span", {"sid": 1, "tier": "WORD", "first": 2, "last": 2})                 # 「金曜」 in the change sentence 「認証の期限は金曜から月曜に変更」
    assert again["ok"] is False and again["refusal"] == "replaced_value" and again["detail"]["text"] == "金曜"
    assert a.run.state.thread == []


def test_a_superseded_sentence_and_its_value_restated_elsewhere_in_the_same_run(tmp_path):
    st = new_store(tmp_path)
    s = st.begin("m", profile=V4)
    s.write("認証の期限は金曜")
    s.write("認証の期限は月曜")
    assert s.call("supersede", {"new_sid": 1, "old_sid": 0, "reason": "変更"})["ok"]
    s.commit()
    a, r = answer(str(tmp_path / "mem"), "認証の期限はいつですか？")
    assert r["verdict"] == "UPDATED" and r["answers"][0]["answers"] == ["月曜"]
    assert a.call("weave_span", {"sid": 0, "tier": "WORD", "first": 2, "last": 2})["refusal"] == "superseded_sentence"          # the existing guard, unchanged
    assert weave(a, occ_of(r))["ok"] and a.call("emit", {})["text"] == "月曜"


def test_a_value_that_is_live_again_after_its_replacement_is_not_blocked(tmp_path):
    p = store(tmp_path, ["認証の期限は金曜", "認証の期限は金曜から月曜に変更", "認証の期限は金曜に変更"])
    a, r = answer(p, "認証の期限はいつですか？")
    assert r["answers"][0]["answers"] == ["金曜"] and r["verdict"] == "UPDATED"
    assert weave(a, occ_of(r))["ok"]


def test_the_latest_value_of_a_change_clause_is_emitted_with_via_update(tmp_path):
    p = store(tmp_path, ["認証の期限は金曜", "認証の期限は金曜から月曜に変更"])
    a, r = answer(p, "認証の期限はいつですか？")
    o = occ_of(r)
    assert o["verbatim"] is True and o["change"]["old"] == "金曜"
    cs = mask.completions(a.run.index(), r, "認証の期限はいつですか？")
    assert [(c["via"], c["question"], c["sid"]) for c in cs] == [("update", "変更は何に変更", 1)]
    assert weave(a, o)["ok"]
    e = a.call("emit", {})                                                       # the clause 「月曜に変更」 has no subject: the plain gate refuses, the form of the change is judged
    assert e["ok"] and e["text"] == "月曜" and e["via"] == "update" and e["completed_question"] == "変更は何に変更" and e["position"][:2] == ["F1", "期限"]
    out = ma.answer_output(a.ledger.dir)
    assert out["status"] == "emitted" and out["via"] == "update" and out["completed_question"] == "変更は何に変更" and out["text"] == "月曜"
    assert ma.verify_answer(a.ledger.dir)["status"] == "OK" and ma.replay_answer(a.ledger.dir).status == "IDENTICAL"


def test_a_change_clause_with_no_old_value_is_emitted_with_via_update(tmp_path):
    p = store(tmp_path, ["QA締切は月曜に変更"])
    a, r = answer(p, "QA締切はいつですか？")
    assert r["verdict"] == "ANSWER" and r["answers"][0]["answers"] == ["月曜"]
    assert weave(a, occ_of(r))["ok"]
    e = a.call("emit", {})
    assert e["ok"] and e["text"] == "月曜" and e["via"] == "update"


def test_update_completion_needs_the_position_of_the_question_and_a_form_with_a_slot(tmp_path):
    p = store(tmp_path, ["認証の期限は水曜から金曜に変更"])
    a, r = answer(p, "認証の締切はいつですか？")                                      # 締切 is reached through the class of 「いつ」, not the position of the question
    assert r["route"] == "class" and r["verdict"] == "ANSWER"
    assert mask.completions(a.run.index(), r, "認証の締切はいつですか？") == []
    assert weave(a, occ_of(r))["ok"]
    e = a.call("emit", {})
    assert e["ok"] is False and e["refusal"] == "no_evidence" and "completion" not in e["detail"] and a.closed() is None
    p2 = store(tmp_path, ["認証の期限は水曜から金曜へ"], name="mem2")                  # kara_he: no predicate, no slot for the gate
    a2, r2 = answer(p2, "認証の期限はいつですか？")
    assert r2["answers"][0]["occurrences"][0]["change"]["form"] == "kara_he" and mask.completions(a2.run.index(), r2, "認証の期限はいつですか？") == []


def test_no_completion_for_a_choice(tmp_path):
    p = store(tmp_path, ["認証の期限は金曜", "認証の期限は月曜"])
    a, r = answer(p, "認証の期限はいつですか？")
    assert r["verdict"] == "CHOICE" and mask.completions(a.run.index(), r, "認証の期限はいつですか？") == []


# -- 3. subject-less questions through a nest (OP-PUB-4) ------------------------------------------------------------------------------------------------
def test_a_subject_less_question_reached_through_a_nest_is_judged_on_the_question_completed_by_the_nest_centre(tmp_path):
    p = store(tmp_path, ["新製品のQA締切は金曜", "旧製品のQA締切は月曜"], topics=["新製品"])
    q = "QA締切はいつですか？"
    a, r = answer(p, q)
    assert r["verdict"] == "ANSWER" and r["route"] == "nest" and r["answers"][0]["answers"] == ["金曜"]
    cs = mask.completions(a.run.index(), r, q)
    assert [(c["via"], c["nest"], c["centre"], c["question"]) for c in cs] == [("nest", "N1", "新製品", "新製品のQA締切はいつですか？")]
    assert weave(a, occ_of(r))["ok"]
    e = a.call("emit", {})                                                       # the plain gate: question_has_no_subject; the completed question: 新製品 is read in the clause
    assert e["ok"] and e["text"] == "金曜" and e["via"] == "nest" and e["nest"] == "N1" and e["completed_question"] == "新製品のQA締切はいつですか？"
    out = ma.answer_output(a.ledger.dir)
    assert (out["via"], out["nest"], out["completed_question"]) == ("nest", "N1", "新製品のQA締切はいつですか？")
    assert ma.verify_answer(a.ledger.dir)["status"] == "OK" and ma.replay_answer(a.ledger.dir).status == "IDENTICAL"


def test_a_seat_written_under_a_nest_whose_clause_does_not_name_it_is_refused_by_the_frozen_gate_and_the_refusal_says_so(tmp_path):
    p = store(tmp_path, ["QA締切は金曜"], topics=["新製品"])
    q = "QA締切はいつですか？"
    a, r = answer(p, q)
    assert r["route"] == "exact" and occ_of(r)["scope"] == "N1"
    assert [c["question"] for c in mask.completions(a.run.index(), r, q)] == ["新製品のQA締切はいつですか？"]
    assert weave(a, occ_of(r))["ok"]
    e = a.call("emit", {})
    assert e["ok"] is False and e["refusal"] == "no_evidence" and e["detail"]["completion"] == {"via": "nest", "question": "新製品のQA締切はいつですか？", "codes": ["no_subject"]}
    assert a.closed() is None and a.call("abstain", {"type": "cannot_weave"})["ok"]


def test_a_question_that_names_its_owner_is_not_completed(tmp_path):
    p = store(tmp_path, ["広報の締め切りは金曜です"], topics=["新製品"])
    q = "広報の締め切りはいつですか？"
    a, r = answer(p, q)
    assert r["verdict"] == "ANSWER" and mask.completions(a.run.index(), r, q) == []
    assert weave(a, occ_of(r))["ok"]
    e = a.call("emit", {})
    assert e["ok"] and e["text"] == "金曜" and "via" not in e                      # the plain gate passed: nothing was completed


def test_only_the_direct_owner_being_the_nest_centre_completes_a_question_and_a_stretch_nobody_recalled_gets_no_completion(tmp_path):
    p = store(tmp_path, ["新製品の営業の締め切りは月曜", "A社の新製品の準備日は金曜"], topics=["新製品"])
    q = "締め切りはいつですか？"
    a, r = answer(p, q)
    assert r["verdict"] == "ANSWER" and r["route"] == "nest" and r["answers"][0]["answers"] == ["月曜"]          # recall (unchanged) reaches the deadline of 営業, an owner under the nest
    assert mask.completions(a.run.index(), r, q) == []                                                          # ... but 営業 is not the nest centre: the question is NOT completed, the plain gate refuses it
    assert weave(a, occ_of(r))["ok"]
    e = a.call("emit", {})
    assert e["ok"] is False and e["refusal"] == "no_evidence" and "completion" not in e["detail"]
    a2, r2 = answer(p, "準備日はいつですか？")                                                                    # the direct owner is the nest centre, a chain above it is fine
    assert [c["question"] for c in mask.completions(a2.run.index(), r2, "準備日はいつですか？")] == ["新製品の準備日はいつですか？"]
    a3 = ma.AnswerSession(p, "準備日はいつですか？", "oracle", answer_version=ma.ANSWER_V3)                       # no recall: the model weaves a stretch itself, nothing is completed
    assert a3.call("weave_span", {"sid": 1, "tier": "WORD", "first": 4, "last": 4})["ok"]
    assert a3.call("emit", {})["ok"] is False


def test_the_begin_row_names_the_guards_and_a_v3_ledger_without_them_is_a_different_version(tmp_path):
    p = store(tmp_path, ["認証の期限は金曜"])
    a = ma.AnswerSession(p, "認証の期限はいつですか？", "m", answer_version=ma.ANSWER_V3)
    m = a.begin_result["mem_answer"]
    assert m["guard"] == ma.GUARD_V3 == "ansguard.v1" and m["complete"] == mask.COMPLETE_VERSION == "complete.v1" and "quote_not_verbatim" in a.begin_result["rules"]["recall"]


# -- determinism ---------------------------------------------------------------------------------------------------------------------------------------
@pytest.mark.parametrize("seed", ["0", "1", "12345"])
def test_recall_with_the_verbatim_flags_and_the_completions_is_byte_identical_across_hash_seeds(seed):
    code = ("import json;from verantyx.loom import memcross as mx, memask as mk, memory as me;from verantyx.loom.corpus import Corpus;from verantyx.loom.memguard import make_source as m;"
            "S=['試薬費の上限は6.5万円です','認証の期限は金曜','認証の期限は金曜から月曜に変更','新製品のQA締切は金曜','QA締切は6/12から6/14に変更','QA締切は月曜に変更'];"
            "R=[{'kind':'base','sent':s,'source':m('t',1,i)} for i,s in enumerate(S)];"
            "ix=mx.build_index(R,[{'session':1,'at':3,'topic':'新製品'}],{});C=Corpus(me.rows_bytes(R));"
            "Q=['試薬費の上限はいくらですか','認証の期限はいつですか','QA締切はいつですか'];"
            "out=[];\n"
            "for q in Q:\n"
            "    r=mk.recall(ix,R,C,q);out.append([r,mk.completions(ix,r,q)])\n"
            "print(json.dumps(out,ensure_ascii=False,sort_keys=True))")
    env = dict(os.environ, PYTHONHASHSEED=seed, PYTHONPATH=ROOT)
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, env=env, cwd=ROOT, check=True).stdout
    ref = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, env=dict(env, PYTHONHASHSEED="0"), cwd=ROOT, check=True).stdout
    assert out == ref and '"verbatim": false' in out and '"via": "update"' in out and '"readout": "65万円"' in out


# -- 4. the bare 「何」 with the counter that touches it (ask.v2; bank_ls dev same-form questions 認証端末の設置日は何日 / 新館カードの有効期間は何年) ----------------------------------------------
@pytest.mark.parametrize("q,centre,path,word", [
    ("認証端末の設置日は何日ですか？", "設置日", (("の", "認証端末"),), "何日"),
    ("新館カードの有効期間は何年ですか？", "有効期間", (("の", "新館カード"),), "何年"),
    ("一般書の移送箱は何箱ですか？", "移送箱", (("の", "一般書"),), "何箱"),
    ("職員休憩室の内線は何番ですか", "内線", (("の", "職員休憩室"),), "何番"),
    ("児童コーナーの書架は何段ですか？", "書架", (("の", "児童コーナー"),), "何段"),
])
def test_the_bare_nani_takes_the_counter_that_touches_it_as_the_question_word(q, centre, path, word):
    p = mask.parse_question(q)
    assert p.ok and (p.shape, p.centre, p.path, p.qword, p.asked, p.qclass) == ("F1", centre, path, word, "は", None)
    assert qw.QWORDS_SHA == "f6778156f2db076ee4d7f3892faa77f283ea258835f8f2951bf9844ceb0d3e21"          # the tank is unchanged: a counter is read by the tagger, not looked up


def test_the_bare_nani_keeps_every_other_reading_and_ask_v1_questions_still_read_the_same():
    for q, asked in [("会議は何を決めますか", "を"), ("資料は何ですか？", "は"), ("研修は何分で組みますか", "で"), ("連絡カードは何枚配布しますか？", "object_bare")]:
        p = mask.parse_question(q)
        assert p.ok and p.asked == asked, q
    assert mask.parse_question("会議は何を決めますか").qword == "何" and mask.parse_question("研修は何分で組みますか").qword == "何分"
    assert mask.ASK_VERSION == "ask.v2"


def test_the_two_same_form_questions_that_were_not_read_now_reach_their_value_the_dev_story_wrote(tmp_path):
    p = store(tmp_path, ["新館カードの有効期間は3年。", "認証端末の設置日は2032年10月2日。", "認証端末の設置日は2032年10月2日から2032年10月4日に変更になった。"])
    a, r = answer(p, "新館カードの有効期間は何年ですか？")
    assert r["verdict"] == "ANSWER" and r["answers"][0]["answers"] == ["3年"] and weave(a, occ_of(r))["ok"] and a.call("emit", {})["text"] == "3年"
    a2, r2 = answer(p, "認証端末の設置日は何日ですか？")
    assert r2["verdict"] == "UPDATED" and r2["answers"][0]["answers"] == ["2032年10月4日"] and r2["history"][0]["answers"] == ["2032年10月2日"]
    assert weave(a2, occ_of(r2))["ok"]
    e = a2.call("emit", {})
    assert e["ok"] and e["text"] == "2032年10月4日" and e["via"] == "update"                                    # the clause of the new value 「2032年10月4日に変更になった」 has no subject


def test_a_value_the_dropped_prefix_or_suffix_would_shorten_is_not_verbatim():
    rs = [{"kind": "base", "sent": "珪戸分室の閉室日は2032年10月31日", "source": make_source("t", 1, 0)}]
    c = Corpus(mem.rows_bytes(rs))
    units = c.tier("WORD").sentence_units[0]
    i = units.index("室")
    assert mask.quote_check(c, 0, i, i + 1)[2] is True                     # the stretch 「室日」 is what the sentence holds at those units ...
    assert mask.quote_check(c, 0, i, i + 1, "閉室日")[2] is False         # ... but the value of the seat is 「閉室日」: the loom does not write the prefix 「閉」, so 「室日」 is not the value
