"""PUB-M5 tests: detection on the crosses (verantyx/loom/memdetect.py, memcross.py, memory.py; notes profile mem.v4): SAME_SEAT, UPDATE, REVERSAL_X, ENUMERATION, the nest scope (designer decision L-PUB-39),
`context` members, the agreement with SAME_QUESTION, the incremental index equal to the full rebuild byte for byte (designer decision L-PUB-40), replay, byte identity across PYTHONHASHSEED.  No network, no API."""
import ast
import json
import os
import subprocess
import sys

import pytest

from verantyx.loom import memcross as mx
from verantyx.loom import memdetect as mdt
from verantyx.loom import memnotes as mn
from verantyx.loom import memory as mem
from verantyx.loom.memguard import make_source
from verantyx.loom.state import canonical
from mem_common import ROOT, new_store

V4 = mem.PROFILE_V4


def sess(tmp_path, name="mem", **kw):
    return new_store(tmp_path, name).begin("test-model", profile=V4, **kw)


def rows(texts, session=1, start=0):
    return [{"kind": "base", "sent": t, "source": make_source("t", session, start + i)} for i, t in enumerate(texts)]


def notes_of(ix, sid=None, typ=None):
    return [n for n in ix.notes if (sid is None or n["sid"] == sid) and (typ is None or n["type"] == typ)]


def test_the_note_types_and_the_counted_set_are_one_definition_in_both_modules():
    assert mdt.CROSS_NOTE_TYPES == mn.NOTE_TYPES_V4[len(mn.NOTE_TYPES):] == ("SAME_SEAT", "UPDATE", "REVERSAL_X", "ENUMERATION")
    assert mdt.COUNTED_V4 == mn.COUNTED_V4 == ("SAME_SEAT", "REVERSAL_X") and mn.MEM_NOTES_V4 == "mem.v4" and mn.MEM_NOTES_V4 in mn.MEM_NOTES_VERSIONS
    assert mn.NOTE_TYPES == ("CONFLICT", "UNANCHORED", "REVERSAL", "NEW_RELATION", "SAME_QUESTION", "SELF_QUESTION_UNREADABLE", "IDENTIFIER_FLATTENED", "NO_RELATION_SEATED")     # the older profiles' list is untouched


# -- SAME_SEAT -----------------------------------------------------------------------------------------------------------------------------------
def test_same_seat_is_a_different_value_at_the_same_position_from_another_sentence():
    ix = mx.build_index(rows(["認証の期限は金曜", "認証の期限は月曜", "認証の期限は金曜", "認証の期限は水曜"]))
    ns = notes_of(ix, typ="SAME_SEAT")
    assert [(n["sid"], n["value"], [e["sid"] for e in n["earlier"]], n["earlier_n"]) for n in ns] == [(1, "月曜", [0], 1), (3, "水曜", [0, 1], 2)]       # a repeat of a live value (sid 2) is no note
    n = ns[0]
    assert (n["tank"], n["centre"], n["path"], n["scope"], n["clause"]) == ("F1", "期限", [["の", "認証"]], None, 0) and n["earlier"][0]["value"] == "金曜"
    assert notes_of(ix, typ="UPDATE") == []


def test_two_clauses_of_one_sentence_are_not_two_sources():
    ix = mx.build_index(rows(["認証の期限は金曜、認証の期限は月曜"]))
    assert notes_of(ix, typ="SAME_SEAT") == []


def test_another_owner_is_an_enumeration_not_a_same_seat_and_equal_values_say_nothing():
    ix = mx.build_index(rows(["認証の期限は金曜", "決済の期限は月曜", "監視の期限は月曜"]))
    assert notes_of(ix, typ="SAME_SEAT") == []
    e = notes_of(ix, typ="ENUMERATION")
    assert [(n["sid"], n["reason"], n["others_n"]) for n in e] == [(1, "arm_owner", 1), (2, "arm_owner", 1)] and e[0]["others"][0]["path"] == [["の", "認証"]]       # 監視 = 月曜 differs from 認証 only (決済 has 月曜 too)
    assert mdt.COUNTED_V4 == ("SAME_SEAT", "REVERSAL_X")


def test_the_detection_is_scoped_by_the_nest_that_was_open():
    base = ["締め切りは金曜", "締め切りは月曜"]
    same = mx.build_index(rows(base), [{"session": 1, "at": 0, "topic": "新製品"}])
    assert [(n["sid"], n["scope"]) for n in notes_of(same, typ="SAME_SEAT")] == [(1, "N1")] and notes_of(same, typ="ENUMERATION") == []
    two = mx.build_index(rows(base), [{"session": 1, "at": 0, "topic": "新製品"}, {"session": 1, "at": 1, "topic": "旧製品"}])
    assert notes_of(two, typ="SAME_SEAT") == []
    e = notes_of(two, typ="ENUMERATION")
    assert [(n["sid"], n["reason"], n["scope"], n["others"][0]["scope"]) for n in e] == [(1, "nest", "N2", "N1")]
    none_then_nest = mx.build_index(rows(base), [{"session": 1, "at": 1, "topic": "旧製品"}])
    assert notes_of(none_then_nest, typ="SAME_SEAT") == [] and [n["reason"] for n in notes_of(none_then_nest, typ="ENUMERATION")] == ["nest"]
    plain = mx.build_index(rows(base))
    assert [n["scope"] for n in notes_of(plain, typ="SAME_SEAT")] == [None]


def test_a_clause_written_under_a_nest_is_a_member_of_kind_context_and_its_text_is_untouched():
    ix = mx.build_index(rows(["締め切りは金曜", "資料を送付した", "認証の期限は月曜"]), [{"session": 1, "at": 0, "topic": "新製品"}])
    n = ix.nest("新製品")
    assert [(m.sid, m.kind, m.exact) for m in n.members] == [(0, "context", False), (1, "completed", True), (2, "context", False)] and "under" not in n.to_obj()
    assert ix.cross("F2", "締め切り").seats_of("は")[0].scope == "N1" and ix.history_full(("F2", "締め切り", ()))[0].scope == "N1"


def test_events_vary_on_the_adjunct_arms_and_need_a_subject_or_object_in_the_context():
    ix = mx.build_index(rows(["会議を大阪で開く", "会議を東京で開く", "説明会を名古屋で開く", "大阪で開く", "東京で開く", "会議を東京で開く"]))
    ns = notes_of(ix, typ="SAME_SEAT")
    assert [(n["sid"], n["tank"], n["centre"], n["arm"], n["value"], n["path"]) for n in ns] == [(1, "F4", "開く", "で", "東京", [["を", "会議"], ["@", "で"]])]            # no nest: the clauses stay F4


# -- UPDATE --------------------------------------------------------------------------------------------------------------------------------------
def test_a_change_clause_is_an_update_and_replaces_what_was_there():
    ix = mx.build_index(rows(["QA締切は6/12", "QA締切は6/12から6/14に変更", "QA締切は6/20"]))
    up = notes_of(ix, typ="UPDATE")
    assert [(n["sid"], n["value"], n["old"], n["first"], n["old_matches"], n["earlier_n"], n["form"]) for n in up] == [(1, "6/14", "6/12", False, True, 1, "kara_ni_henkou")]
    ss = notes_of(ix, typ="SAME_SEAT")
    assert [(n["sid"], [e["sid"] for e in n["earlier"]]) for n in ss] == [(2, [1])]                  # the 6/12 of sid 0 was replaced: the third value contradicts the update, not the replaced value


def test_a_change_clause_with_nothing_before_it_is_an_update_with_first_true_and_a_wrong_old_value_is_flagged():
    ix = mx.build_index(rows(["QA締切は6/12から6/14に変更", "期限は6/1", "期限は6/12から6/14に変更"]))
    up = notes_of(ix, typ="UPDATE")
    assert [(n["sid"], n["first"], n["old_matches"], n["earlier_n"]) for n in up] == [(0, True, None, 0), (2, False, False, 1)]
    assert notes_of(ix, typ="SAME_SEAT") == []


# -- REVERSAL_X ----------------------------------------------------------------------------------------------------------------------------------
def test_reversal_x_the_same_pair_in_opposite_roles_across_sentences():
    ix = mx.build_index(rows(["認証の決済は田中", "決済の認証は佐藤", "認証の決済は鈴木"]))
    r = notes_of(ix, typ="REVERSAL_X")
    assert [(n["sid"], n["relation"], n["pair"], [e["sid"] for e in n["earlier"]]) for n in r] == [(1, "の", ["決済", "認証"], [0]), (2, "の", ["認証", "決済"], [1])]
    k = r[0]["key"]
    assert set(k) == {"base", "swapped", "agrees"} and isinstance(k["agrees"], bool) and len(k["base"]) == 3


def test_reversal_x_events_and_the_value_form_and_not_the_same_direction():
    ix = mx.build_index(rows(["甲社が乙社を招待した", "乙社が甲社を招待した", "甲社が乙社を招待した", "A工程はB工程の前提", "B工程はA工程の前提", "C工程はD工程の前提", "C工程はD工程の前提"]))
    r = notes_of(ix, typ="REVERSAL_X")
    assert [(n["sid"], n["relation"], n["label"], n["pair"]) for n in r] == [(1, "event", "招待", ["乙社", "甲社"]), (2, "event", "招待", ["甲社", "乙社"]), (4, "value", "前提", ["B工程", "A工程"])]
    assert notes_of(ix, sid=3, typ="REVERSAL_X") == [] and notes_of(ix, sid=6, typ="REVERSAL_X") == []


def test_the_key_swap_agrees_when_the_history_holds_the_pair_in_the_other_order():
    ix = mx.build_index(rows(["甲社が乙社を招待した", "乙社が甲社を招待した"]))
    k = notes_of(ix, typ="REVERSAL_X")[0]["key"]
    assert k["agrees"] is True and k["swapped"][:2] > k["base"][:2]
    ix2 = mx.build_index(rows(["甲社が乙社を招待した", "乙社が甲社を招待した", "乙社が甲社を招待した", "乙社が甲社を招待した"]))
    # by sentence 3 the history holds the pair twice in the order the sentence writes and once in the other: the swap does not improve, the key does not agree
    k2 = notes_of(ix2, sid=3, typ="REVERSAL_X")[0]["key"]
    assert k2["agrees"] is False


# -- the session: notes in the write, two witnesses, replay ------------------------------------------------------------------------------------------
def test_a_write_returns_the_cross_notes_counted_and_with_the_second_witness(tmp_path):
    s = sess(tmp_path)
    s.write("認証モジュールの担当は田中")
    r = s.write("認証モジュールの担当は佐藤")
    by = {n["type"]: n for n in r["notes"]}
    assert by["SAME_SEAT"]["counted"] is True and by["SAME_SEAT"]["witness"] == {"by": "SAME_QUESTION", "state": "agree"}
    assert by["SAME_QUESTION"]["counted"] is False and by["SAME_QUESTION"]["witness"] == {"by": "SAME_SEAT", "state": "agree"}
    assert s.run.notes_profile == "mem.v4" and s.rows()[0]["result"]["header"]["notes_profile"] == "mem.v4" and s.rows()[0]["result"]["header"]["detect"] == {"version": mdt.DETECT_VERSION}
    # the notes are in the ledger, in a loom_note row after the write row
    rows_ = s.rows()
    k = [i for i, x in enumerate(rows_) if x["op"] == "write"][-1]
    assert rows_[k + 1]["op"] == "loom_note" and {n["type"] for n in rows_[k + 1]["args"]["notes"]} >= {"SAME_SEAT", "SAME_QUESTION"} and rows_[k + 1]["args"]["nv"] == "mem.v4"
    s.commit()
    assert mem.verify_store(str(tmp_path / "mem"), mem.FROM_HEADER)["status"] == "OK"


def test_a_sentence_the_loom_cannot_weave_still_gets_its_cross_notes_and_the_witness_says_unavailable(tmp_path):
    s = sess(tmp_path)
    s.write("会議を大阪で開く")
    r = s.write("会議を東京で開く")
    assert r["weave"].startswith("refused") or r["weave"] == "ok"
    ss = [n for n in r.get("notes", []) if n["type"] == "SAME_SEAT"]
    assert len(ss) == 1 and ss[0]["tank"] == "F4" and ss[0]["witness"]["state"] in ("unavailable", "not_applicable")


def test_notes_never_block_a_write_and_the_older_notes_are_witnesses_not_counted(tmp_path):
    s = sess(tmp_path)
    for t in ("認証の期限は金曜", "認証の期限は月曜", "決済の期限は火曜"):
        assert s.write(t)["ok"] is True
    ev = s.events()
    assert ev["counted"] == {"SAME_SEAT": 1, "REVERSAL_X": 0} and ev["notes"]["ENUMERATION"] >= 1 and ev["notes"]["SAME_QUESTION"] >= 1
    assert ev["detections"]["notes"] == 1


def test_the_status_of_a_v3_session_is_unchanged_by_the_new_note_types(tmp_path):
    s3 = new_store(tmp_path, "v3").begin("m", profile="mem.v3")
    assert set(s3.status()["notes"]) == set(mn.NOTE_TYPES)
    s4 = sess(tmp_path, "v4")
    assert set(s4.status()["notes"]) == set(mn.NOTE_TYPES_V4)


# -- the incremental index is the full rebuild -----------------------------------------------------------------------------------------------------
def story(tmp_path, name="mem"):
    st = new_store(tmp_path, name)
    s = st.begin("m", profile=V4)
    s.call("declare_topic", {"text": "A社のB事業"})
    for t in ("認証の期限は金曜", "認証の期限は水曜", "決済の期限は月曜", "資料を送付した", "認証の期限は木曜から日曜に変更", "甲社が乙社を招待した", "会議を大阪で開く", "会議を東京で開く", "締め切りは火曜"):
        s.write(t)
    s.call("keep_unshaped", {"text": "担当表では認証モジュール担当は田中です"})
    s.call("supersede", {"new_sid": 1, "old_sid": 0, "reason": "変更"})
    s.call("bridge", {"question_word": "締切", "memory_phrase": "期限"})
    s.commit()
    s2 = st.begin("m", profile=V4)
    s2.call("declare_topic", {"text": "新製品"})
    for t in ("乙社が甲社を招待した", "締め切りは金曜", "締め切りは水曜", "会議を開いた"):
        s2.write(t)
    s2.call("bridge", {"question_word": "日", "memory_phrase": "締め切り"})
    return st, s2


def test_the_incremental_index_equals_the_full_rebuild_byte_for_byte(tmp_path):
    st, s2 = story(tmp_path)
    live = s2.run.builder.index()
    full = mx.build_index(s2.run.rows, s2.run.decls, s2.run.superseded, bridges=s2.run.bridge_log)
    assert canonical(live.to_obj()) == canonical(full.to_obj()) and live.index_sha == full.index_sha
    assert s2.run.builder._assemble() == canonical(live.to_obj())                                       # the parts joined = the canonical JSON of the whole
    s2.commit()
    assert st.index().index_sha == live.index_sha and mem.verify_store(str(tmp_path / "mem"), mem.FROM_HEADER)["status"] == "OK"
    assert mem.replay_store(str(tmp_path / "mem"), mem.FROM_HEADER).identical


def test_the_fold_of_one_write_equals_the_index_of_the_prefix(tmp_path):
    texts = ["認証の期限は金曜", "決済の期限は月曜", "認証の期限は水曜", "甲社が乙社を招待した", "乙社が甲社を招待した", "会議を大阪で開く", "会議を東京で開く"]
    rs = rows(texts)
    b = mx.IndexBuilder()
    from verantyx.loom.corpus import Corpus
    prev = Corpus(b"")
    for t, row in enumerate(rs):
        if t == 3:
            b.declare(1, 3, "新製品")
        b.add_row(t, row, prev)
        prev = Corpus(mx._rows_bytes(rs[:t + 1]))
        decls = [{"session": 1, "at": 3, "topic": "新製品"}] if t >= 3 else []
        assert b.index().index_sha == mx.build_index(rs[:t + 1], decls).index_sha, t


def test_a_supersede_and_a_bridge_after_the_rows_change_the_index_but_not_the_notes(tmp_path):
    st, s2 = story(tmp_path)
    ix = s2.run.builder.index()
    assert ix.bridges[0].qword == "締切" and ix.bridges[0].origin == "constructed" and len(ix.bridges) == 2
    before = [n for n in ix.notes]
    plain = mx.build_index(s2.run.rows, s2.run.decls, {}, bridges=[])
    assert before == [n for n in plain.notes]                                                           # notes are made at the write, marks and bridges do not move them


# -- determinism and purity --------------------------------------------------------------------------------------------------------------------------
@pytest.mark.parametrize("seed", ["0", "1", "12345"])
def test_the_notes_and_the_index_are_byte_identical_across_hash_seeds(seed):
    code = ("import json;from verantyx.loom import memcross as mx;from verantyx.loom.memguard import make_source as m;"
            "S=['認証の期限は金曜','決済の期限は月曜','認証の期限は水曜','認証の期限は水曜から金曜に変更','甲社が乙社を招待した','乙社が甲社を招待した','会議を大阪で開く','会議を東京で開く','A工程はB工程の前提','B工程はA工程の前提','締め切りは金曜','締め切りは月曜'];"
            "R=[{'kind':'base','sent':s,'source':m('t',1 if i<6 else 2,i)} for i,s in enumerate(S)];"
            "ix=mx.build_index(R,[{'session':1,'at':2,'topic':'新製品'},{'session':2,'at':8,'topic':'旧製品'}],{0:{'by':2,'reason':'x','session':1}},bridges=[{'session':2,'at':9,'qword':'期日','phrase':'締め切り'}]);"
            "print(ix.index_sha);print(json.dumps(ix.to_obj(),ensure_ascii=False,sort_keys=True))")
    env = dict(os.environ, PYTHONHASHSEED=seed, PYTHONPATH=ROOT)
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, env=env, cwd=ROOT, check=True).stdout
    ref = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, env=dict(env, PYTHONHASHSEED="0"), cwd=ROOT, check=True).stdout
    assert out == ref and len(out.split("\n")[0]) == 64 and '"SAME_SEAT"' in out and '"REVERSAL_X"' in out


FORBIDDEN_IMPORTS = {"time", "datetime", "random", "subprocess", "socket", "os", "sys", "uuid", "secrets", "urllib", "http", "requests"}


@pytest.mark.parametrize("fn", ["memdetect.py", "memcross.py", "memqwords.py", "memask.py"])
def test_the_detection_and_recall_modules_have_no_clock_float_process_network_or_set_order(fn):
    tree = ast.parse(open(os.path.join(ROOT, "verantyx", "loom", fn), encoding="utf-8").read())
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            assert not ({a.name.split(".")[0] for a in n.names} & FORBIDDEN_IMPORTS)
        if isinstance(n, ast.ImportFrom) and n.module:
            assert n.module.split(".")[0] not in FORBIDDEN_IMPORTS
        if isinstance(n, ast.Constant):
            assert not isinstance(n.value, float)
        if isinstance(n, ast.Name):
            assert n.id not in ("float", "set", "frozenset", "eval", "exec", "open", "print")
        if isinstance(n, (ast.Div, ast.Set, ast.SetComp)):
            raise AssertionError("true division or a set in " + fn)


# -- keep_unshaped still indexes the F1-F4 clauses (designer decision L-PUB-42) ----------------------------------------------------------------------
def test_keep_unshaped_indexes_the_shaped_clauses_of_the_sentence_and_only_the_f0_clause_stays_unshaped(tmp_path):
    s = sess(tmp_path)
    s.write("認証の期限は金曜")
    k = s.call("keep_unshaped", {"text": "認証の期限は月曜。担当表では認証モジュール担当は田中です。"})
    assert k["ok"] and k["unshaped"] is True and k["shape"]["shapes"] == ["F1", "F0"] and [c["centre"] for c in k["shape"]["indexed"]] == ["期限"]
    assert k["index"]["crosses"] == 1 and k["index"]["f0"] == 1
    ss = [n for n in k["notes"] if n["type"] == "SAME_SEAT"]
    assert len(ss) == 1 and ss[0]["value"] == "月曜" and ss[0]["counted"] is True and ss[0]["witness"]["state"] == "unavailable"       # the sentence was not woven: no self-question
    assert s.run.state.thread == s.run.state.thread and "loom_note" == s.rows()[-1]["op"]                  # the cross notes travel in a note row after the keep_unshaped row
    s.commit()
    ix = mem.MemStore(str(tmp_path / "mem")).index()
    assert len(ix.f0) == 1 and [(c.sid, c.k, c.shape, c.tank) for c in ix.clauses] == [(0, 0, "F1", "F1"), (1, 0, "F1", "F1"), (1, 1, "F0", None)]
    assert [e.value for e in ix.history_full(("F1", "期限", (("の", "認証"),)))] == ["金曜", "月曜"]
    assert mem.verify_store(str(tmp_path / "mem"), mem.FROM_HEADER)["status"] == "OK"
