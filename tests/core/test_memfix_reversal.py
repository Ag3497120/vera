"""MEM-fix tests: a REVERSAL note CITES the two sentences it is about, and how precise REVERSAL was in the meter v1 (L-MEM-61 / offline precision).

The meter v1 found REVERSAL firing on 16-22 % of the stored sentences with no way to say which two messages it meant (a report cites turns).  A mem.v3 session's REVERSAL note carries
`sentence` (the write: sid, source, turn), `earlier` (the sentences of the history that hold the pair of words in the other order, at most 8, sid order) with `earlier_n`, and `cite`
(the turn pairs a report can name).  The witnesses are a pure function of the history (`memnotes.reversal_witnesses`), so the same call recomputes them for the stored meter_v1 ledgers,
which is what tests/fixtures/line3/mem/memfix/reversal_precision.py does."""


import json


import os


import sys


import pytest


from verantyx.loom import memdoor as md


from verantyx.loom import memnotes as mn


from verantyx.loom import memory as mem


from mem_common import ROOT, new_store


V3, V2 = mem.PROFILE_V3, mem.PROFILE_V2


STORY = [("1-1", "認証の前提は決済"), ("1-2", "田中の担当は認証"), ("1-3", "会議は東京で行う"), ("2-1", "決済の前提は認証")]


def play(tmp_path, profile, story=STORY, name="s"):
    door = md.StructureDoor(str(tmp_path / (name + profile)), "notes", "m", profile=profile)
    out = []
    for turn, text in story:
        door.set_turn(turn)
        out.append(door.call("write", {"text": text}))
    return door, out


def reversal(res):
    return [n for n in res.get("notes", []) if n["type"] == mn.REVERSAL]


def test_a_v3_reversal_cites_the_two_sentences(tmp_path):
    door, ws = play(tmp_path, V3)
    n = reversal(ws[3])
    assert len(n) == 1
    n = n[0]
    assert n["sentence"] == {"sid": 3, "source": ws[3]["source"], "turn": "2-1"}
    assert n["earlier"] == [{"sid": 0, "source": ws[0]["source"], "turn": "1-1"}] and n["earlier_n"] == 1 and n["cite"] == [["1-1", "2-1"]]
    assert n["counted"] is True                                                                       # still a counted detection (OP-MEM-2 (a))
    # the same write in a v2 session: the note as it always was
    d2, w2 = play(tmp_path, V2)
    n2 = reversal(w2[3])[0]
    assert "sentence" not in n2 and "earlier" not in n2 and "cite" not in n2
    assert {k: v for k, v in n.items() if k not in ("sentence", "earlier", "earlier_n", "cite")} == n2


def test_the_cite_names_witnesses_at_other_turns_only_and_is_capped(tmp_path):
    story = [("1-%d" % k, "認証の前提は決済") for k in range(1, 11)] + [("2-1", "決済の前提は認証")]
    door, ws = play(tmp_path, V3, story)
    n = reversal(ws[10])[0]
    assert n["earlier_n"] == 10 and [e["sid"] for e in n["earlier"]] == list(range(8)) and n["cite"] == [["1-1", "2-1"], ["1-2", "2-1"], ["1-3", "2-1"]]
    # a witness written at the very same turn names no pair
    door2, ws2 = play(tmp_path, V3, [("2-1", "認証の前提は決済"), ("2-1", "決済の前提は認証")], "same")
    m = reversal(ws2[1])
    assert m and m[0]["cite"] == [] and m[0]["earlier_n"] == 1


def test_a_write_without_a_turn_cites_the_sentences_but_no_pair(tmp_path):
    s = new_store(tmp_path, "nt").begin("m", profile=V3)
    for t in ("認証の前提は決済", "決済の前提は認証"):
        w = s.write(t)
    n = reversal(w)[0]
    assert n["sentence"] == {"sid": 1, "source": w["source"]} and n["earlier"] == [{"sid": 0, "source": n["earlier"][0]["source"]}] and n["cite"] == []


def test_the_witnesses_are_the_sentences_that_hold_the_pair_the_other_way_round(tmp_path):
    rows = [{"kind": "base", "sent": s, "source": "mem:t/1#%d" % k} for k, s in enumerate(["認証の前提は決済", "決済の前提は認証", "認証の前提は決済", "会議は東京で行う"])]
    c = mem.build_corpus(rows)
    assert mn.reversal_witnesses(c, "決済", ["認証"]) == [1]                       # 決済 before 認証: only sentence 1
    assert mn.reversal_witnesses(c, "認証", ["決済"]) == [0, 2]
    assert mn.reversal_witnesses(c, "東京", ["認証"]) == [] and mn.reversal_witnesses(c, "ない", ["認証"]) == []
    assert mn.reversal_witnesses(mem.build_corpus([]), "認証", ["決済"]) == []


def test_cited_notes_replay_identical(tmp_path):
    door, ws = play(tmp_path, V3)
    door.commit()
    door.close()
    assert mem.verify_store(str(tmp_path / ("s" + V3)), mem.FROM_HEADER)["status"] == "OK"
    rows = [json.loads(ln) for ln in open(tmp_path / ("s" + V3) / "sessions" / "s0001" / "ops.jsonl", encoding="utf-8")]
    note_rows = [r for r in rows if r["actor"] == mn.NOTE_ACTOR]
    assert note_rows[-1]["args"]["nv"] == "mem.v2" and any(n.get("cite") for r in note_rows for n in r["args"]["notes"])


def test_the_blind_arm_does_not_see_the_cite(tmp_path):
    door = md.StructureDoor(str(tmp_path / "b"), "blind", "m", profile=V3)
    for turn, text in STORY:
        door.set_turn(turn)
        w = door.call("write", {"text": text})
    assert "notes" not in w and "keys" not in w
    door.commit()
    rows = [json.loads(ln) for ln in open(tmp_path / "b" / "sessions" / "s0001" / "ops.jsonl", encoding="utf-8")]
    assert any(n["type"] == "REVERSAL" and n["cite"] == [["1-1", "2-1"]] for r in rows if r["actor"] == mn.NOTE_ACTOR for n in r["args"]["notes"])      # logged, not shown


PLANTS = [{"kind": "reversal", "turns": {"1-1", "2-1"}}, {"kind": "contradiction", "turns": {"1-2", "2-2"}}, {"kind": "update", "turns": {"1-3", "3-1"}}]
