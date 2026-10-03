"""W3-a3: the K62 copy and the reverse lookup that reads a predicate's distribution through it.

The table is the reader's (W3-b1); here it is only COPIED and read backwards.  No word appears below:
a distribution is a dict of "<particle>|<noun type>" counts."""
import re
from pathlib import Path

import pytest

from verantyx import coarse_types as ct

TREE = Path(__file__).resolve().parents[2]
SRC = TREE / "artifacts" / "w3-a3" / "k62_source.md"
KIND = {"項": "arg", "付加": "adjunct"}


def source_rows():
    text = SRC.read_text(encoding="utf-8")
    body = re.search(r"<!-- BEGIN table:w3b1_frames -->(.*)<!-- END table:w3b1_frames -->", text, re.S).group(1)
    rows = []
    for line in body.strip().splitlines()[2:]:
        c = [x.strip() for x in line.strip().strip("|").split("|")]
        rows.append((c[0].strip("`"), c[1], c[2], tuple(c[3].split()), KIND[c[4]]))
    return rows


def cfg(**kw):
    c = dict(ct.DEFAULT_CONFIG)
    c.update({"rd_min_total": 20, "rd_particle_min": 5, "rd_particle_share_pct": 10,
              "rd_type_share_pct": 50})
    c.update(kw)
    return c


def test_k62_frames_equal_the_pasted_table_and_hold_only_ids():
    got = [(t, r, p, tuple(sorted(ts)), k) for t, r, p, ts, k in ct.K62_FRAMES]
    want = [(t, r, p, tuple(sorted(ts)), k) for t, r, p, ts, k in source_rows()]
    assert got == want and len(got) == 9
    assert [t for t, *_ in ct.K62_FRAMES] == [t for t, *_ in source_rows()]     # the same order too
    assert {t for t, *_ in ct.K62_FRAMES} == {"P_MOVE", "P_COMMUNICATE"}
    for _t, _r, p, ts, _k in ct.K62_FRAMES:
        assert p in ct.CASE_PARTICLES_9 and all(x in ct.NOUN_TYPES for x in ts)


def test_the_source_note_names_the_commit_and_the_blob():
    t = SRC.read_text(encoding="utf-8")
    assert "5d863dd" in t and "0d6233b20c6a1cd717f9a16bb6d96476422864ab" in t


def test_distinguishing_rows_are_derived_from_the_table():
    move, comm = ct.k62_distinguishing("P_MOVE"), ct.k62_distinguishing("P_COMMUNICATE")
    assert move == {("へ", "PLACE"), ("から", "PLACE")}
    assert comm == {("を", t) for t in ct.K62_FRAMES[6][3]} and len(comm) == 14
    # derivation, not selection: rows both types hold are in neither set
    for pair in [("が", "PERSON"), ("で", "PLACE"), ("に", "TIME")]:
        assert pair not in move and pair not in comm
    assert ct.k62_distinguishing("P_ACT") == frozenset()          # a type without rows has none
    assert ct.k62_particles() == {"が", "を", "に", "で", "へ", "から"}


def rd(counts, base=None, **kw):
    base = base if base is not None else sum(counts.values())
    return ct.rd_analyze(counts, cfg(**kw), base)


def test_one_candidate_move_and_one_candidate_communicate():
    mv = rd({"が|PERSON": 30, "へ|PLACE": 20, "から|PLACE": 10})
    assert mv["candidates"] == ["P_MOVE"] and set(mv["sig"]) == {"が", "へ", "から"}
    cm = rd({"が|PERSON": 30, "を|INFO_LANGUAGE": 40})
    assert cm["candidates"] == ["P_COMMUNICATE"]
    assert ct.arm_verdict("role_distribution", {"が|PERSON": 30, "を|INFO_LANGUAGE": 40}, cfg()) == []   # no base given
    assert ct.arm_verdict("role_distribution", {"が|PERSON": 30, "を|INFO_LANGUAGE": 40}, cfg(), 70) == ["P_COMMUNICATE"]


def test_no_candidate_when_a_significant_particle_is_outside_the_rows_of_the_type():
    # に+PLACE: K62's P_MOVE has に only for TIME, so a motion verb that takes に+PLACE is no candidate
    r = rd({"が|PERSON": 20, "に|PLACE": 40, "へ|PLACE": 10})
    assert r["candidates"] == []
    # を is not a P_MOVE row, で+PERSON is outside P_MOVE's types
    assert rd({"が|PERSON": 20, "を|PLACE": 40, "へ|PLACE": 10})["candidates"] == []
    assert rd({"が|PERSON": 20, "で|PERSON": 40, "へ|PLACE": 10})["candidates"] == []


def test_no_candidate_without_a_distinguishing_row():
    # が+PERSON alone fits both types (their rows share it) but distinguishes none: no vote
    r = rd({"が|PERSON": 50})
    assert r["candidates"] == [] and r["sig"] == ["が"]
    # で+PLACE and に+TIME are shared rows too
    assert rd({"が|PERSON": 30, "で|PLACE": 25, "に|TIME": 25})["candidates"] == []


def test_two_candidates_are_a_split_and_a_split_is_no_vote():
    # へ+PLACE distinguishes P_MOVE, を+<noun> distinguishes P_COMMUNICATE.  A particle seen with both
    # kinds of arguments cannot fit either type (を is no P_MOVE row; へ is no P_COMMUNICATE row)
    r = rd({"が|PERSON": 30, "へ|PLACE": 25, "を|INFO_LANGUAGE": 25})
    assert r["candidates"] == []
    assert ct.arm_verdict("role_distribution", {"が|PERSON": 30, "へ|PLACE": 25, "を|INFO_LANGUAGE": 25},
                          cfg(), 80) == []


def test_to_made_yori_never_make_or_break_a_candidate_but_are_shown():
    base = {"が|PERSON": 30, "を|INFO_LANGUAGE": 40}
    plain = rd(base)
    with_to = rd({**base, "と|INFO_LANGUAGE": 20, "まで|TIME": 20, "より|QUANTITY": 20})
    assert plain["candidates"] == with_to["candidates"] == ["P_COMMUNICATE"]
    assert {"と", "まで", "より"} <= set(with_to["sig"]) and "と" not in plain["sig"]
    # alone they make nothing
    assert rd({"と|PERSON": 50, "まで|TIME": 50, "より|QUANTITY": 50})["candidates"] == []


def test_the_thresholds_are_the_registered_ones():
    counts = {"が|PERSON": 30, "を|INFO_LANGUAGE": 40}
    assert rd(counts, rd_min_total=100)["candidates"] == []              # base 70 < 100
    assert rd(counts, rd_particle_min=50)["candidates"] == []            # no particle reaches 50
    assert rd(counts, rd_particle_share_pct=60)["sig"] == []             # 40/70 < 60%
    # a type is significant in a particle from rd_type_share_pct of the particle's count
    spread = {"が|PERSON": 30, "を|INFO_LANGUAGE": 20, "を|ARTIFACT": 20}
    assert rd(spread, rd_type_share_pct=70)["types"]["を"] == []          # 20/40 = 50% < 70
    assert rd(spread, rd_type_share_pct=70)["candidates"] == []           # no significant distinguishing pair
    assert rd(spread, rd_type_share_pct=50)["types"]["を"] == ["ARTIFACT", "INFO_LANGUAGE"]
    assert rd(spread, rd_type_share_pct=50)["candidates"] == ["P_COMMUNICATE"]


def test_an_empty_distribution_and_a_missing_base_vote_for_nothing():
    assert ct.rd_analyze({}, cfg(), 100)["candidates"] == []
    assert ct.rd_analyze({"が|PERSON": 99}, cfg(), None)["candidates"] == []
    assert ct.arm_verdict("role_distribution", {}, cfg(), 100) == []
