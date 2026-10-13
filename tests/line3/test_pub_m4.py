"""PUB-M4 tests: the shape table shape.v2 (the change forms 「A から B へ」 「B に更新」 「B に延期 / 変更」 as clauses, every form recorded and hashed; shape.v1 untouched), the slide order (sentence N -> N+1,
session boundaries), the positions and their histories (first | update | other).  Detection itself is M5 and is not tested here.  No network, no API."""
import json
import os
import subprocess
import sys

import pytest

from verantyx.loom import memcross as mx
from verantyx.loom import memory as mem
from verantyx.loom import memshape as ms
from verantyx.loom.memguard import make_source
from mem_common import ROOT, new_store

V4 = mem.PROFILE_V4
V2 = ms.SHAPES_V2


def rows(texts, session=1, start=0):
    return [{"kind": "base", "sent": t, "source": make_source("t", session, start + i)} for i, t in enumerate(texts)]


def brief(text, version=V2):
    return [(c.shape, c.centre, None if c.value is None else c.value.text, None if c.change is None else (c.change.form, None if c.change.old is None else c.change.old.text), c.reason)
            for c in ms.exchange(text, version).clauses]


# -- the table -----------------------------------------------------------------------------------------------------------------------------------
def test_shape_v1_is_untouched_and_shape_v2_is_a_new_table_with_its_own_sha():
    assert ms.SHAPES_SHA == "1908323f8690db16ebc7ea90ff46e00cb175ba6fd61021b6f31468c72dff7497" and ms._shapes_sha() == ms.SHAPES_SHA
    assert ms.SHAPES_SHA_V2 == "7c4e3d08d76e59fab592339bdf20ccfaad556a61b2492a47726251a3dd69f9fc" and ms._shapes_sha_v2() == ms.SHAPES_SHA_V2 != ms.SHAPES_SHA
    assert ms.SHAPE_TABLES == {"shape.v1": ms.SHAPES_SHA, "shape.v2": ms.SHAPES_SHA_V2}
    assert ms.CHANGE_FORMS_V2 == ("kara_ni_henkou", "kara_he_henkou", "kara_ni_koushin", "kara_he_koushin", "kara_ni_enki", "kara_he_enki", "kara_he", "ni_henkou", "ni_koushin", "ni_enki")
    assert ms.CONSTANTS_V2["change_forms"] == list(ms.CHANGE_FORMS_V2) and ms.CONSTANTS_V2["version"] == "shape.v2" and ms.CONSTANTS["version"] == "shape.v1"
    assert ms.exchange("期限は金曜").version == "shape.v1" and ms.exchange("期限は金曜", V2).version == "shape.v2" and ms.exchange("期限は金曜", V2).to_obj()["v"] == "shape.v2"
    with pytest.raises(ValueError):
        ms.exchange("期限は金曜", "shape.v9")


FORMS = [
    ("QA締切は6/12から6/14に変更になりました", ("F2", "QA締切", "6/14", ("kara_ni_henkou", "6/12"))),
    ("会場を大阪から京都へ変更", ("F2", "会場", "京都", ("kara_he_henkou", "大阪"))),
    ("期限は水曜から金曜に更新", ("F2", "期限", "金曜", ("kara_ni_koushin", "水曜"))),
    ("期限は水曜から金曜へ更新", ("F2", "期限", "金曜", ("kara_he_koushin", "水曜"))),
    ("開始は月曜から水曜に延期", ("F2", "開始", "水曜", ("kara_ni_enki", "月曜"))),
    ("認証の期限は水曜から金曜へ延期", ("F1", "期限", "金曜", ("kara_he_enki", "水曜"))),
    ("期限は水曜から金曜へ", ("F2", "期限", "金曜", ("kara_he", "水曜"))),
    ("会議を大阪に変更", ("F2", "会議", "大阪", ("ni_henkou", None))),
    ("認証の期限は金曜に更新", ("F1", "期限", "金曜", ("ni_koushin", None))),
    ("期限は金曜に延期した", ("F2", "期限", "金曜", ("ni_enki", None))),
]


@pytest.mark.parametrize("text,want", FORMS)
def test_every_change_form_is_a_clause_of_its_own_in_shape_v2(text, want):
    got = brief(text)
    assert len(got) == 1 and got[0][:4] == want and got[0][4] is None
    assert got[0][3][0] in ms.CHANGE_FORMS_V2


def test_the_ten_forms_are_the_ten_ids_of_the_table():
    assert sorted(w[3][0] for _, w in FORMS) == sorted(ms.CHANGE_FORMS_V2)


def test_shape_v1_reads_the_same_sentences_as_before():
    assert brief("会場を大阪から京都へ変更", "shape.v1")[0][0] == "F0" and brief("期限は水曜から金曜へ", "shape.v1")[0][4] == "gap_is_not_a_particle"
    assert brief("会議を大阪に変更", "shape.v1")[0][:2] == ("F4", "変更") and brief("期限は金曜に延期した", "shape.v1")[0][:2] == ("F3", "延期")
    assert brief("QA締切は6/12から6/14に変更になりました", "shape.v1")[0][3] == ("", "6/12")                # the one change form of v1 has no id there


def test_a_form_without_a_slot_is_an_f4_clause_with_the_predicate_as_centre_and_the_bare_form_needs_a_slot():
    assert brief("金曜に延期") == [("F4", "延期", "金曜", ("ni_enki", None), None)]
    assert brief("水曜から金曜へ変更") == [("F4", "変更", "金曜", ("kara_he_henkou", "水曜"), None)]
    assert brief("水曜から金曜へ")[0][0] == "F0"                                                      # 「A から B へ」 with no slot says nothing about what changed


def test_negated_and_questioned_forms_and_other_uses_of_から_are_not_change_clauses():
    for t in ("期限は水曜から金曜に延期しない", "期限は水曜から金曜に変更しますか", "期限は水曜から金曜に変更？", "9時から会議を開始する", "担当は田中から佐藤へ交代", "田中が会議を大阪に変更した"):
        got = brief(t)
        assert all(g[3] is None for g in got), (t, got)
    assert brief("期限は水曜から金曜に延期しない")[0][4] == "negated" and brief("田中が会議を大阪に変更した")[0][:2] == ("F3", "変更")


def test_the_v1_change_form_reads_the_same_in_v2_except_for_its_id():
    for t in ("QA締切は6/12から6/14に変更になりました", "会議を大阪から京都に変更", "認証の期限は水曜から金曜に変更しました", "水曜から金曜に変更"):
        a, b = ms.exchange(t).clauses, ms.exchange(t, V2).clauses
        assert len(a) == len(b) == 1
        assert b[0].change.form == "kara_ni_henkou" and a[0].change.form == ""
        assert ms.replace(b[0], change=ms.replace(b[0].change, form="")) == a[0], t


def test_a_sentence_without_a_change_form_reads_the_same_in_both_tables():
    for t in ("認証の期限は金曜", "田中が会議を開いた", "52本保管します", "担当表では認証モジュール担当は田中です", "A社のB事業の担当は田中です。会議を開く", "昨日、期限は金曜です"):
        assert ms.exchange(t).clauses == ms.exchange(t, V2).clauses and ms.exchange(t).to_obj()["clauses"] == ms.exchange(t, V2).to_obj()["clauses"]


def test_change_to_obj_has_the_form_key_only_in_v2_and_an_old_value_may_be_none():
    assert "form" not in ms.exchange("QA締切は6/12から6/14に変更", "shape.v1").clauses[0].change.to_obj()
    o = ms.exchange("会議を大阪に変更", V2).clauses[0].change.to_obj()
    assert o["old"] is None and o["form"] == "ni_henkou" and o["new"]["text"] == "大阪"


# -- the slide order -----------------------------------------------------------------------------------------------------------------------------
def test_order_edges_run_from_sentence_n_to_n_plus_1_and_flag_the_session_boundaries():
    rs = rows(["a の b は c", "d の e は f"], 1) + rows(["g の h は i"], 2) + rows(["j の k は l", "m の n は o"], 3)
    ix = mx.build_index(rs)
    assert ix.edges == ((0, 1, 0), (1, 2, 1), (2, 3, 1), (3, 4, 0)) and ix.sessions == (1, 1, 2, 3, 3)
    assert mx.build_index([]).edges == () and mx.build_index(rs[:1]).edges == ()
    assert ix.to_obj()["sessions"] == [[1, 0, 1], [2, 2, 2], [3, 3, 4]]


def test_the_values_of_a_position_are_listed_in_slide_order_with_their_provenance():
    rs = rows(["認証の期限は金曜", "決済の期限は月曜"], 1) + rows(["認証の期限は水曜から木曜に変更"], 2) + rows(["認証の期限は日曜", "認証の期限は金曜に延期した"], 3)
    rs[0]["turn"] = "1-1"
    ix = mx.build_index(rs)
    pos = ("F1", "期限", (("の", "認証"),))
    assert pos in ix.positions and ("F1", "期限", (("の", "決済"),)) in ix.positions and len(ix.positions) == 2
    assert ix.history(pos) == [("金曜", 0, "first"), ("木曜", 2, "update"), ("日曜", 3, "other"), ("金曜", 4, "update")]
    full = ix.history_full(pos)
    assert [(e.sid, e.session, e.turn) for e in full] == [(0, 1, "1-1"), (2, 2, None), (3, 3, None), (4, 3, None)]
    assert full[1].change.old == "水曜" and full[1].old_matches is False and full[3].change.form == "ni_enki" and full[3].old_matches is None
    assert ix.history(("F1", "期限", (("の", "決済"),))) == [("月曜", 1, "first")]
    assert ix.history(("F1", "期限", (("の", "存在しない"),))) == [] and mx.history(ix, pos) == ix.history(pos)


def test_the_slide_order_is_not_the_rank_order_of_the_seats():
    ix = mx.build_index(rows(["認証の期限は金曜", "決済の期限は月曜", "認証の期限は金曜"]))
    c = ix.cross("F1", "期限")
    assert [s.prov.sid for s in c.seats_of("は")] == [2, 1, 0]                                         # rank: sentence 2 has the pair 期限 / 金曜 in its history (n = 1); sentence 1 only 期限 + は (a = 233); sentence 0 has no history
    pos = ("F1", "期限", (("の", "認証"),))
    assert [(e.sid, e.value, e.kind) for e in ix.history_full(pos)] == [(0, "金曜", "first"), (2, "金曜", "other")]       # time: by sid; a repeat of the same value is not an update
    assert ix.history(("F1", "期限", (("の", "決済"),))) == [("月曜", 1, "first")]


def test_a_value_the_model_superseded_is_an_update_and_the_old_one_keeps_its_seat_with_a_mark():
    rs = rows(["認証の期限は金曜", "認証の期限は水曜"])
    pos = ("F1", "期限", (("の", "認証"),))
    assert mx.build_index(rs).history(pos) == [("金曜", 0, "first"), ("水曜", 1, "other")]
    ix = mx.build_index(rs, superseded={0: {"by": 1, "reason": "変更", "session": 1}})
    assert ix.history(pos) == [("金曜", 0, "first"), ("水曜", 1, "update")]
    assert ix.history_full(pos)[0].marks == (mx.Mark("superseded", 1, "変更", 1),)
    assert len(ix.cross("F1", "期限").seats_of("は")) == 2


def test_a_supersede_by_another_sentence_does_not_make_this_value_an_update():
    rs = rows(["認証の期限は金曜", "認証の期限は水曜", "認証の期限は月曜"])
    ix = mx.build_index(rs, superseded={0: {"by": 1, "reason": "x", "session": 1}})
    assert [k for _, _, k in ix.history(("F1", "期限", (("の", "認証"),)))] == ["first", "update", "other"]


def test_the_position_is_the_clause_path_so_an_enumeration_is_another_position():
    ix = mx.build_index(rows(["認証の期限は金曜", "決済の期限は月曜", "期限は水曜", "A社のB事業の担当は田中", "B事業の担当は佐藤"]))
    assert [(t, c, [ph for _, ph in p]) for t, c, p in ix.positions] == [("F1", "期限", ["認証"]), ("F1", "期限", ["決済"]), ("F2", "期限", []), ("F1", "担当", ["B事業", "A社"]), ("F1", "担当", ["B事業"])]
    assert [len(ix.history(p)) for p in ix.positions] == [1, 1, 1, 1, 1]


def test_a_change_clause_in_a_nest_keeps_the_position_of_its_nest_centre():
    ix = mx.build_index(rows(["期限は金曜に延期した", "金曜に延期した", "月曜に延期した"]), [{"session": 1, "at": 1, "topic": "新製品"}])
    assert ix.history(("F2", "期限", ())) == [("金曜", 0, "first")]
    assert ix.history(("F3", "延期", (("が", "新製品"),))) == [("金曜", 1, "first"), ("月曜", 2, "update")]


def test_history_through_a_real_store_with_a_supersede_and_two_sessions(tmp_path):
    st = new_store(tmp_path)
    s = st.begin("m", profile=V4)
    s.write("認証の期限は金曜")
    s.write("認証の期限は水曜")
    sup = s.call("supersede", {"new_sid": 1, "old_sid": 0, "reason": "変更"})
    s.commit()
    s2 = st.begin("m", profile=V4)
    s2.write("認証の期限は木曜から日曜に変更")
    s2.commit()
    assert sup["ok"], sup
    ix = st.index()
    assert ix.history(("F1", "期限", (("の", "認証"),))) == [("金曜", 0, "first"), ("水曜", 1, "update"), ("日曜", 2, "update")]
    assert ix.edges == ((0, 1, 0), (1, 2, 1)) and mem.verify_store(str(tmp_path / "mem"), mem.FROM_HEADER)["status"] == "OK"
    assert s2.run.builder.index().index_sha == ix.index_sha and ix.cross("F1", "期限").seats_of("は")[-1].marks in ((), (mx.Mark("superseded", 1, "変更", 1),))


@pytest.mark.parametrize("seed", ["0", "1", "12345"])
def test_shape_v2_is_byte_identical_across_hash_seeds(seed):
    code = ("import json;from verantyx.loom import memshape as ms;"
            "S=['QA締切は6/12から6/14に変更になりました','会場を大阪から京都へ変更','期限は水曜から金曜へ','会議を大阪に変更','認証の期限は金曜に更新','期限は金曜に延期した','金曜に延期','田中が会議を開いた'];"
            "print(ms.SHAPES_SHA_V2);print(json.dumps([ms.exchange(s,'shape.v2').to_obj() for s in S],ensure_ascii=False,sort_keys=True))")
    env = dict(os.environ, PYTHONHASHSEED=seed, PYTHONPATH=ROOT)
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, env=env, cwd=ROOT, check=True).stdout
    ref = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, env=dict(env, PYTHONHASHSEED="0"), cwd=ROOT, check=True).stdout
    assert out == ref and out.startswith(ms.SHAPES_SHA_V2)
