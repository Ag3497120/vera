"""PUB-M6d tests (owner 2026-10-13, stage 2 of the staged shape table): shape.v4 reads 「へ」 like 「に」 on the same arm and records the particle actually written.  No network, no API."""
import json
import os
import subprocess
import sys

import pytest

from verantyx.loom import memanswer as ma
from verantyx.loom import memask as mask
from verantyx.loom import memcross as mx
from verantyx.loom import memory as mem
from verantyx.loom import memshape as ms
from verantyx.loom.corpus import Corpus
from verantyx.loom.memguard import make_source
from mem_common import ROOT, new_store

V4 = mem.PROFILE_V4
M6D = mem.V4_VERSIONS_M6D


def clauses(text, version=ms.SHAPES_V4):
    return ms.exchange(text, version).clauses


def arms(c):
    return [(a.particle, a.seat.text, a.written) for a in c.arms]


def test_the_tables_are_frozen_and_v4_is_a_new_version():
    assert ms.SHAPES_SHA == "1908323f8690db16ebc7ea90ff46e00cb175ba6fd61021b6f31468c72dff7497"
    assert ms.SHAPES_SHA_V2 == "7c4e3d08d76e59fab592339bdf20ccfaad556a61b2492a47726251a3dd69f9fc"
    assert ms.SHAPES_SHA_V3 == "0e7dd04d71e18c991ce0f044b896fa2eb9a8d28d253e37e0dad0ce21b649b805"
    assert ms.SHAPES_SHA_V4 == ms._shapes_sha_v4() and ms.SHAPES_SHA_V4 not in (ms.SHAPES_SHA, ms.SHAPES_SHA_V2, ms.SHAPES_SHA_V3)
    assert ms.SHAPE_TABLES == {"shape.v1": ms.SHAPES_SHA, "shape.v2": ms.SHAPES_SHA_V2} and ms.SHAPE_TABLES_ALL["shape.v4"] == ms.SHAPES_SHA_V4
    assert ms.exchange("資料を机へ戻した", ms.SHAPES_V4).version == "shape.v4"


@pytest.mark.parametrize("sentence,centre,expected", [
    ("窓口の掲示を机へ戻しておく", "戻す", [("を", "掲示", ""), ("に", "机", "へ")]),
    ("薄い袋へ入れた", "入れる", [("に", "薄い袋", "へ")]),
    ("次の確認箇所へ進む", "進む", [("に", "確認箇所", "へ")]),
    ("基板の端子札は便名控えへ付けてある", "付ける", [("が", "端子札", ""), ("に", "便名控え", "へ")]),
])
def test_he_is_read_like_ni_on_the_same_arm_and_recorded_as_written(sentence, centre, expected):
    assert clauses(sentence, ms.SHAPES_V3)[0].shape == "F0"
    cs = clauses(sentence)
    assert len(cs) == 1 and cs[0].shape in ("F3", "F4") and cs[0].centre == centre and arms(cs[0]) == expected
    assert [a.to_obj().get("written") for a in cs[0].arms if a.particle == "に"] == ["へ"]


def test_ni_and_he_give_the_same_event_and_a_ni_arm_has_no_record_of_he():
    a, b = clauses("資料を机に戻した")[0], clauses("資料を机へ戻した")[0]
    assert (a.shape, a.centre, [(x.particle, x.seat.text) for x in a.arms]) == (b.shape, b.centre, [(x.particle, x.seat.text) for x in b.arms])
    assert "written" not in a.arms[1].to_obj() and b.arms[1].to_obj()["written"] == "へ"


@pytest.mark.parametrize("sentence", [
    "近隣への案内を出した",                 # へ + の: a chain, not an arm
    "机の端まで拭いた",                     # the other constructions stay F0 (stage 3, も, だけ ...)
    "清掃手順も確認した",
    "配架表から先に目を通す",
    "現場では通りやすかった",
    "先に取り出すことにした",
])
def test_what_stage_2_does_not_read_stays_f0(sentence):
    assert clauses(sentence)[0].shape == "F0" and clauses(sentence)[0].reason == clauses(sentence, ms.SHAPES_V3)[0].reason


SAMPLE = ["認証モジュールの担当は田中", "認証の期限は金曜から月曜に変更", "QA締切は6/12から6/14に変更になった", "会議は東京で行う", "資料を送付した", "新館開館日は2032年11月7日",
          "次の束を見た", "寄贈資料の受け入れ方は、確認票を作った", "念のため、確認票を作った", "珪戸分室の閉室日は2032年10月31日", "AからBへ変更", "認証の期限は金曜から月曜へ",
          "予備電池は問屋の予定表で24日着になっていた", "集音マイクの高さは維持できている", "窓口の掲示を机へ戻しておく", "遅れている"]


def test_a_clause_shape_v3_places_is_read_the_same_by_shape_v4():
    for t in SAMPLE:
        e3, e4 = ms.exchange(t, ms.SHAPES_V3), ms.exchange(t, ms.SHAPES_V4)
        placed = {c.text: c.to_obj() for c in e3.clauses if c.shape != "F0"}
        for c in e4.clauses:
            if c.text in placed:
                assert c.to_obj() == placed[c.text], t
        if e3.clauses and all(c.shape != "F0" for c in e3.clauses):
            assert [c.to_obj() for c in e4.clauses] == [c.to_obj() for c in e3.clauses], t


def test_a_new_reading_never_has_two_subjects():
    for t in ("開館準備の掲示文は、来館者の目線で順番を机へ入れ替えた", "出荷前の見本機チェックは岩黒紬が見ることになった"):
        for c in clauses(t):
            assert sum(1 for a in c.arms if a.particle == "が") <= 1


def test_the_index_records_the_written_particle_and_older_indexes_are_unchanged():
    rows = [{"kind": "base", "sent": x, "source": make_source("t", 1, i)} for i, x in enumerate(["資料を机へ戻した", "資料を机に戻した"])]
    ix4 = mx.build_index(rows, shape_version=ms.SHAPES_V4)
    cr = ix4.cross("F4", "戻す")
    ni = cr.seats_of("に")
    assert [(s.phrase, s.written, s.prov.sid) for s in ni] in ([("机", "へ", 0), ("机", "", 1)], [("机", "", 1), ("机", "へ", 0)])
    assert "written" in json.dumps(ix4.to_obj()) and "written" not in json.dumps(mx.build_index(rows[1:], shape_version=ms.SHAPES_V3).to_obj())
    ix3 = mx.build_index(rows[1:], shape_version=ms.SHAPES_V3)
    ix4b = mx.build_index(rows[1:], shape_version=ms.SHAPES_V4)
    assert [s.to_obj() for s in ix3.cross("F4", "戻す").seats_of("に")] == [s.to_obj() for s in ix4b.cross("F4", "戻す").seats_of("に")]       # no へ, no difference


def test_the_session_bundle_of_stage_2_writes_recalls_and_replays(tmp_path):
    assert M6D == dict(mem.V4_VERSIONS_M6C, shape="shape.v4") and mem.check_versions(M6D) == M6D
    st = new_store(tmp_path)
    s = st.begin("m", profile=V4, versions=M6D)
    h = s.run.header()
    assert h["shape"] == {"version": "shape.v4", "sha": ms.SHAPES_SHA_V4} and h["ask"] == {"version": "ask.v3"}
    r = s.write("資料を机へ戻した")
    assert r["ok"] and r["shape"]["v"] == "shape.v4" and r["shape"]["clauses"][0]["centre"] == "戻す"
    assert s.write("窓口の掲示を棚に戻した")["ok"]
    for q in ("資料はどこに戻しましたか？", "資料はどこへ戻しましたか？"):                    # asked with に or with へ: the same arm, the written へ does not matter
        res = s.call("recall", {"question": q})
        assert res["verdict"] == "ANSWER" and res["route"] == "event" and res["answers"][0]["answers"] == ["机"], q
    s.commit()
    v = mem.verify_store(str(tmp_path / "mem"), mem.FROM_HEADER)
    assert v["status"] == "OK" and v["replay"]["status"] == "IDENTICAL"
    with pytest.raises(Exception) as ei:
        new_store(tmp_path, "other").begin("m", profile=V4, versions={"shape": "shape.v9"})
    assert getattr(ei.value, "type", "") == "bad_policy"
    r3 = new_store(tmp_path, "v3").begin("m", profile=V4, versions=mem.V4_VERSIONS_M6C).write("資料を机へ戻した")
    assert r3["ok"] is False and r3["refusal"] == "no_shape"                              # stage 1 still refuses it
    a = ma.AnswerSession(str(tmp_path / "mem"), "資料はどこに戻しましたか？", "m", answer_version=ma.ANSWER_V4)
    assert a.begin_result["mem_answer"]["shape"] == "shape.v4" and a.run.index().shape_version == "shape.v4"


@pytest.mark.parametrize("seed", ["0", "1", "12345"])
def test_bytes_are_identical_across_hash_seeds(seed):
    code = ("import json;from verantyx.loom import memcross as mx, memshape as ms;from verantyx.loom.memguard import make_source\n"
            "S=['窓口の掲示を机へ戻しておく','基板の端子札は便名控えへ付けてある','近隣への案内を出した','資料を机に戻した','次の束を見た']\n"
            "rows=[{'kind':'base','sent':x,'source':make_source('t',1,i)} for i,x in enumerate(S)]\n"
            "ix=mx.build_index(rows,shape_version=ms.SHAPES_V4)\n"
            "print(ms.SHAPES_SHA_V4,ix.index_sha);print(json.dumps([ms.exchange(s,ms.SHAPES_V4).to_obj() for s in S],ensure_ascii=False,sort_keys=True))")
    env = dict(os.environ, PYTHONHASHSEED=seed, PYTHONPATH=ROOT)
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, env=env, cwd=ROOT, check=True).stdout
    ref = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, env=dict(env, PYTHONHASHSEED="0"), cwd=ROOT, check=True).stdout
    assert out == ref and out.startswith(ms.SHAPES_SHA_V4) and '"written": "へ"' in out
