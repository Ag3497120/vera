"""G1-a / G1-b tests: the foundation's seats and adhesion (verantyx/line3/foundation.py) and the seated cross
(placement.build_cross(foundation="on")) -- docs/LINE3_G4_GROWTH_METER.md 4.2/4.3, docs/LINE3_G1_INITIAL_PLACEMENT.md 3.1,
owner decisions OP-G1-4 「固定かつ継ぎ目」, OP-G1-5 「鍵の 3 番目 (n, p, a)」, OP-G1-9 「腕＝関係の札」, D-1 「データの種を中心、助詞 6 語は最内環」.

Part 1  the spec (particles, arm order, ladder ratios as Fractions, sha) and the constructed tokens
Part 2  the adhesion counts with evidence on a 5-sentence toy (RUN / WORD / CHAR), distinct sids, the dictionary-free CHAR path
Part 3  a(arrangement) and the seam (contract)
Part 4  the seated cross: foundation seats fixed under every move, the seam key equals the plain key, a separates a tie, は on the centre
Part 5  F1 ordered insertion / stop / skip / max_class are unchanged in form; twins; contract_for_read; verify_class_foundation
Part 6  foundation off is byte-identical; PYTHONHASHSEED 0 / 1 / 12345 give the same bytes
"""
import dataclasses
import json
import os
import subprocess
import sys
from fractions import Fraction as Fr

import pytest

from verantyx.line3 import foundation as fd
from verantyx.line3 import geometry as geo
from verantyx.line3 import grammar as gr
from verantyx.line3 import placement as pl
from verantyx.line3 import space as sp
from test_placement import tier, TOYS

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PY = sys.executable
BIG = pl.Budget(max_class=100000, max_states=1000000, max_moves=100000000)
MID = pl.budget_level("mid")
SPEC = fd.DEFAULT_SPEC
TOK = {p: fd.token(p) for p in SPEC.ladder}
NO, NI, DE, TO, WO, GA = (TOK[p] for p in SPEC.arms)        # the arm tokens in axis order: の に で と を が

FIVE = [                      # the 5-sentence toy of Part 2
    "東京の人口は多い。",
    "城は東京にある。",
    "京都の寺と東京の駅。",
    "大阪の城を見る。",
    "東京の城と東京の駅。",
]
FIVE_COUNTS = {("京都", "の"): 1, ("人口", "は"): 1, ("城", "と"): 1, ("城", "は"): 1, ("城", "を"): 1, ("大阪", "の"): 1,
               ("寺", "と"): 1, ("東京", "に"): 1, ("東京", "の"): 3}
FIVE_CHAR = {("京", "に"): 1, ("京", "の"): 3, ("口", "は"): 1, ("城", "と"): 1, ("城", "は"): 1, ("城", "を"): 1,
             ("寺", "と"): 1, ("都", "の"): 1, ("阪", "の"): 1}


def adh(counts, name="T"):
    return fd.Adhesion(name, counts)


def seated(t, u, counts=None, budget=BIG, **kw):
    return pl.build_cross(t, u, budget=budget, foundation="on", adhesion=adh(counts or {}), **kw)


def col_of_arm(L, a):
    return range(1 + a * L, 1 + (a + 1) * L)


# =============================================================================================================
# Part 1: the spec
# =============================================================================================================
def test_spec_particles_arm_order_and_ratios():
    assert SPEC.centre == "は" and SPEC.arms == ("の", "に", "で", "と", "を", "が")
    assert SPEC.ladder == gr.LADDER and SPEC.arms == gr.ARM_PARTICLES
    assert SPEC.numerators == (233, 144, 89, 55, 34, 21, 13) and SPEC.den == 377
    assert dict(SPEC.ratios) == dict(gr.WEIGHTS) and all(isinstance(r, Fr) for _, r in SPEC.ratios)
    assert SPEC.ratio("が") == Fr(1, 29) and SPEC.numerator("が") == 13            # Fraction(13, 377) reduces; the numerator does not
    assert [SPEC.arm_of_axis(a) for a in geo.AXES] == ["の", "に", "で", "と", "を", "が"]
    assert SPEC.foundation_obj() == gr.foundation_obj()
    assert fd.foundation_flat("X") == ("X", NO, NI, DE, TO, WO, GA)


def test_the_hand_written_constants_equal_grammars():
    # foundation.py must not import grammar (placement imports it, and the slide_place / slide_ratios isolation tests forbid grammar in the
    # import closure of placement), so the particle list and the ladder are copied; every copy is pinned here.
    assert fd.P7 == gr.P7 and fd.LADDER == gr.LADDER and fd.ARM_PARTICLES == gr.ARM_PARTICLES and fd.CENTRE_PARTICLE == gr.CENTRE_PARTICLE
    assert fd.FIB_DEN == gr.FIB_DEN == 377 and dict(fd.WEIGHTS) == dict(gr.WEIGHTS) and fd.RECORD_TIERS == gr.RECORD_TIERS
    assert fd.GRAMMAR_FORMAT == gr.FORMAT
    assert SPEC.foundation_obj() == gr.foundation_obj()


def test_importing_placement_does_not_import_grammar():
    code = ("import sys\nimport verantyx.line3.placement, verantyx.line3.foundation\n"
            "print(','.join(m for m in sys.modules if m.startswith('verantyx.line3.') and m.split('.')[2] in "
            "('grammar', 'ask', 'cycle', 'matryoshka', 'carry', 'carry_query', 'readout', 'trace_check', 'wiring')))")
    r = subprocess.run([PY, "-c", code], capture_output=True, text=True, cwd=ROOT, env=dict(os.environ, PYTHONPATH=ROOT))
    assert r.returncode == 0 and r.stdout.strip() == "", r.stdout + r.stderr


def test_spec_sha_is_stable_and_pinned():
    assert fd.seats_sha() == "a2083d4536377ac0b8381db5df6d0ba6ebcc6d20ec5d16f80f34f74fa802a5d7"
    assert fd.seats_sha() == SPEC.sha256() == fd.seats_sha(SPEC)
    o = json.loads(SPEC.to_bytes())
    assert o["format"] == "line3.foundation_seats.v1" and o["position_rule"] == "ring1" and o["seam"] == "contract"
    assert o["attach"] == {"CHAR": "char_next", "RUN": "records/straddle", "WORD": "records/straddle"}
    assert o["numerators"] == {"は": 233, "の": 144, "に": 89, "で": 55, "と": 34, "を": 21, "が": 13} and o["den"] == 377
    assert o["arms"] == {"+x": "の", "-x": "に", "+y": "で", "-y": "と", "+z": "を", "-z": "が"}
    assert fd.placement_key_part("off") == "" and fd.placement_key_part("on") == "found-" + fd.seats_sha()[:12]
    with pytest.raises(ValueError):
        fd.check_foundation("maybe")


def test_ratios_must_be_exact_distinct_fractions():
    ok = dict(gr.WEIGHTS)
    assert fd.check_ratios(ok) == ok
    with pytest.raises(TypeError):
        fd.check_ratios({**ok, "が": 0.5})                                 # a float
    with pytest.raises(TypeError):
        fd.check_ratios({**ok, "が": 1})                                   # an int is not a ratio either
    with pytest.raises(ValueError):
        fd.check_ratios({**ok, "が": ok["を"]})                            # a tie: the arm of a unit would be left to an order
    with pytest.raises(ValueError):
        fd.check_ratios({**ok, "が": Fr(0)})
    with pytest.raises(ValueError):
        fd.Spec.make("は", gr.ARM_PARTICLES, {**ok, "が": ok["を"]}, 377)
    with pytest.raises(ValueError):
        fd.Spec.make("は", gr.ARM_PARTICLES, ok, 30)                       # not whole numbers over the recorded denominator


def test_constructed_tokens_are_never_data_units():
    for p in SPEC.ladder:
        t = fd.token(p)
        assert fd.is_constructed(t) and fd.particle_of(t) == p and t.startswith("\u0000") and t != p
    assert not fd.is_constructed(None) and not fd.is_constructed("の") and not fd.is_constructed("A")
    with pytest.raises(ValueError):
        fd.particle_of("の")
    space = sp.build_space([{"sent": s} for s in FIVE])
    for ts in space.tiers.values():
        assert not any(fd.is_constructed(u) for u in ts.postings)


# =============================================================================================================
# Part 2: adhesion
# =============================================================================================================
@pytest.fixture(scope="module")
def five():
    space = sp.build_space([{"sent": s} for s in FIVE])
    return space, fd.adhesions_of_space(space)


def test_adhesion_counts_with_evidence_on_five_sentences(five):
    space, ads = five
    assert ads["RUN"].counts == FIVE_COUNTS and ads["WORD"].counts == FIVE_COUNTS and ads["CHAR"].counts == FIVE_CHAR
    for t in sp.TIERS:                                                  # every count is backed by evidence (sid, span) and re-derives from the text
        a = ads[t]
        recs = fd.adhesion_records(space, t)
        assert fd.check_trace(recs, lambda sid: FIVE[sid]) == []
        for (u, p), n in a.counts.items():
            ev = a.evidence(u, p)
            assert len({r.sid for r in ev}) == n and all(r.unit == u and r.particle == p and r.tier == t for r in ev)
            for r in ev:
                assert FIVE[r.sid][r.start:r.end] == u and FIVE[r.sid][r.p_start:r.p_end] == p and r.p_start == r.end
    ev = ads["WORD"].evidence("東京", "の")                              # distinct sids: sentence 4 holds 東京の twice, it counts once
    assert [(r.sid, r.start, r.end) for r in ev] == [(0, 0, 2), (2, 5, 7), (4, 0, 2), (4, 5, 7)]
    assert ads["WORD"].adj("東京", "の") == 3 and len(ev) == 4
    assert ads["WORD"].adj("東京", "を") == 0 and ads["WORD"].adj("無い", "の") == 0 and ads["WORD"].adj(None, "の") == 0


def test_run_unit_followed_by_a_gap_counts_through_the_inner_word_particle(five):
    space, ads = five
    # 「城は東京にある。」: the RUN cut has 城 and 東京 (the gap 「にある」 is function words and no unit), 東京 ends where the WORD 「に」 starts
    assert list(space.tiers["RUN"].sentence_units[1]) == ["城", "東京"]
    assert ads["RUN"].adj("東京", "に") == 1
    r = ads["RUN"].evidence("東京", "に")[0]
    assert (r.sid, r.start, r.end, r.p_start, r.p_end) == (1, 2, 4, 4, 5) and FIVE[1][4:5] == "に"
    # and it is exactly the distinct-sid count of the grammar records (L-G1-2 unchanged)
    rec = gr.records_of_space(space)
    for t in ("RUN", "WORD"):
        for u in rec.units(t):
            for p in gr.P7:
                assert ads[t].adj(u, p) == len({a.sid for a in rec.of(t, u) if a.particle == p})


def test_char_adhesion_is_character_by_character_without_a_dictionary():
    code = (
        "import sys\n"
        "sys.modules['fugashi'] = None\n"
        "sys.modules['unidic_lite'] = None\n"
        "from verantyx.line3 import foundation as fd\n"
        "texts = %r\n"
        "recs = fd.char_records(enumerate(texts))\n"
        "a = fd.Adhesion.from_records('CHAR', recs)\n"
        "import json\n"
        "print(json.dumps(sorted([u, p, n] for (u, p), n in a.counts.items()), ensure_ascii=False))\n"
        "assert 'fugashi' not in [k for k, v in sys.modules.items() if v is not None]\n" % (FIVE,))
    r = subprocess.run([PY, "-c", code], capture_output=True, text=True, cwd=ROOT,
                       env=dict(os.environ, PYTHONPATH=ROOT, PYTHONHASHSEED="0"))
    assert r.returncode == 0, r.stderr
    assert json.loads(r.stdout) == sorted([u, p, n] for (u, p), n in FIVE_CHAR.items())


def test_char_adhesion_rules():
    # the head must be a non-hiragana letter; the particle must follow IMMEDIATELY (nothing skipped); the attribution is stripped
    recs = fd.char_records([(0, "犬の猫"), (1, "犬、の猫"), (2, "いのち"), (3, "犬 の"), (4, "犬に猫を")])
    assert [(r.sid, r.unit, r.particle) for r in recs] == [(0, "犬", "の"), (4, "犬", "に"), (4, "猫", "を")]
    assert all(r.p_start == r.end and r.end - r.start == 1 for r in recs)


def test_adhesion_refuses_floats_and_bad_input():
    with pytest.raises(TypeError):
        fd.Adhesion("T", {("a", "の"): 0.5})
    with pytest.raises(TypeError):
        fd.Adhesion("T", {("a", "の"): True})
    with pytest.raises(ValueError):
        fd.Adhesion("T", {("a", "から"): 1})                                # not a particle of the foundation
    with pytest.raises(ValueError):
        fd.Adhesion("T", {("a", "の"): -1})
    a = adh({("a", "の"): 2, ("a", "は"): 1, ("b", "が"): 0})
    assert a.counts == {("a", "は"): 1, ("a", "の"): 2}                      # a zero is no count
    assert a.weighted("a") == (233, 288, 0, 0, 0, 0, 0) and a.weighted("zz") == (0,) * 7 and a.weighted(None) == (0,) * 7
    assert a.sha256() == adh({("a", "の"): 2, ("a", "は"): 1}).sha256()


def test_check_trace_catches_a_wrong_span(five):
    space, _ = five
    recs = list(fd.adhesion_records(space, "WORD"))
    bad = recs[0].__class__(recs[0].tier, recs[0].sid, recs[0].start + 1, recs[0].end + 1, recs[0].unit, recs[0].particle,
                            recs[0].p_start, recs[0].p_end)
    assert fd.check_trace([bad], lambda sid: FIVE[sid])


# =============================================================================================================
# Part 3: a(arrangement) and the seam
# =============================================================================================================
def test_a_num_reads_the_arm_from_the_innermost_seat_and_adds_the_centre_relation():
    a = adh({("x", "は"): 2, ("u", "の"): 3, ("v", "に"): 1, ("w", "が"): 4, ("u", "に"): 5, ("v", "の"): 7})
    L = 2
    # legs are (outer, particle) for the arms の に で と を が
    flat = ("x", "u", NO, "v", NI, None, DE, None, TO, None, WO, "w", GA)
    assert fd.a_num(a, flat, L) == 233 * 2 + 144 * 3 + 89 * 1 + 13 * 4
    assert fd.a_exact(a, flat, L) == Fr(233 * 2 + 144 * 3 + 89 * 1 + 13 * 4, 377)
    # swap the legs of の and に: the units travel with their particle, the arm is the particle at the innermost seat, not the leg index
    swapped = ("x", "v", NI, "u", NO, None, DE, None, TO, None, WO, "w", GA)
    assert fd.a_num(a, swapped, L) == 233 * 2 + 89 * 1 + 144 * 3 + 13 * 4
    # u on the に arm and v on the の arm: each takes its OWN adhesion to the arm it sits on
    cross = ("x", "v", NO, "u", NI, None, DE, None, TO, None, WO, "w", GA)
    assert fd.a_num(a, cross, L) == 233 * 2 + 144 * 7 + 89 * 5 + 13 * 4
    # a unit in an outer seat of a longer leg counts too (every data seat of an arm is bound to its particle, OP-G1-9)
    L3 = 3
    flat3 = ("x", "u", None, NO, None, None, NI, None, None, DE, None, None, TO, None, None, WO, "w", None, GA)
    assert fd.a_num(a, flat3, L3) == 233 * 2 + 144 * 3 + 13 * 4
    # the lone seed
    assert fd.a_num(a, fd.foundation_flat("x"), 1) == 233 * 2
    with pytest.raises(ValueError):
        fd.a_num(a, ("x", "u", "v", None, None, None, None, None, None, None, None, None, None), 2)   # a leg without a foundation seat


def test_contract_drops_the_innermost_seat_of_every_leg():
    flat = ("x", "u", NO, "v", NI, None, DE, None, TO, None, WO, "w", GA)
    assert fd.contract(flat, 2) == (("x", "u", "v", None, None, None, "w"), 1)
    assert fd.contract(fd.foundation_flat("x"), 1) == (("x", None, None, None, None, None, None), 1)
    flat3 = ("x", "u", "y", NO, None, None, NI, None, None, DE, None, None, TO, None, None, WO, "w", None, GA)
    cf, L2 = fd.contract(flat3, 3)
    assert L2 == 2 and cf == ("x", "u", "y", None, None, None, None, None, None, None, None, "w", None)
    with pytest.raises(ValueError):
        fd.contract(("x", "u", "v", None, None, None, None), 1)
    assert fd.arms_of(flat, 2) == SPEC.arms


def test_layout_edges_are_those_of_the_contracted_cross():
    for L in (1, 2, 3, 4):
        lay = pl._flayout(L)
        plain = pl._layout(max(1, L - 1))
        assert lay.cons == frozenset(1 + a * L + L - 1 for a in range(6)) and len(lay.data) == 6 * (L - 1) + 1
        assert all(not lay.inc[i] for i in lay.cons)                    # a foundation seat has no (n, p) edge
        if L >= 2:
            assert len(lay.edges) == len(plain.edges) == 6 * (L - 1)
    # key[:2] == the plain score of the contracted flat, on a hand-made flat
    t = tier(["A B C", "A B", "A C D", "B D"])
    w = pl.Weights(t, adh({}))
    flat = ("A", "B", "C", NO, "D", None, NI, None, None, DE, None, None, TO, None, None, WO, None, None, GA)
    cf, L2 = fd.contract(flat, 3)
    assert pl.score_flat(w, flat, 3)[:2] == pl.score_flat(pl.Weights(t), cf, L2)


# =============================================================================================================
# Part 4: the seated cross
# =============================================================================================================
def tokens_in_place(flat, L):
    return tuple(flat[1 + a * L + L - 1] for a in range(6)) == (NO, NI, DE, TO, WO, GA)


def test_seated_cross_shape_and_L_rule():
    t = tier(["S a b c d e f g h"])                                      # S shares with 8 units; the adhesion keeps the class small
    cnt = {("a", "の"): 8, ("b", "に"): 7, ("c", "で"): 6, ("d", "と"): 5, ("e", "を"): 4, ("f", "が"): 3, ("g", "の"): 2, ("h", "に"): 1}
    p = seated(t, "S", counts=cnt, group_insert="ordered", order="forward")
    assert p.foundation == fd.seats_sha() and not p.contracted and p.stop == "exhausted"
    assert p.size == 9 and p.L == pl.min_L(9 + 6) == 3                    # 6L + 1 >= 9 + 6 seats
    for m in p.members:
        assert tokens_in_place(m, p.L)
        assert sorted(x for x in m if x is not None and not fd.is_constructed(x)) == sorted("S a b c d e f g h".split())
    # the six arm-particle units sit innermost, the data seats are exactly the seats of a plain cross at L - 1
    assert len(pl._flayout(p.L).data) == 6 * (p.L - 1) + 1
    # the lone seed: L = 1, centre + six particles
    q = seated(t, "S", max_groups=0)
    assert q.size == 1 and q.L == 1 and q.members == (fd.foundation_flat("S"),)
    # seed + 1 unit forces L = 2 (6L+1 >= 8)
    t2 = tier(["S a"])
    assert seated(t2, "S").L == 2 and pl.build_cross(t2, "S").L == 1
    # the cross object carries the tokens and renders
    assert fd.is_constructed(str(p.cross.get(geo.Seat("+x", p.L - 1))))


def test_foundation_seats_are_fixed_under_every_move():
    cases = [(TOYS[0], {("A", "の"): 2, ("B", "に"): 1, ("C", "の"): 1, ("D", "が"): 3}),
             (TOYS[1], {("A", "は"): 1, ("B", "を"): 2, ("C", "と"): 2}),
             (["S a b", "S a b c", "S c d"], {("a", "の"): 2, ("b", "に"): 1, ("d", "で"): 1})]
    seen_moves = 0
    for sents, counts in cases:
        t = tier(sents)
        a = adh(counts)
        for u in t.units():
            p = pl.build_cross(t, u, budget=BIG, foundation="on", adhesion=a, quotient=False)
            w = pl.Weights(t, a)
            lay = pl._flayout(p.L)
            for m in p.members:
                assert tokens_in_place(m, p.L)
                improved, eq, tested = pl._scan(w, m, p.L)
                # the moves tested are exactly the pairs of non-foundation seats (minus equal contents / the empty centre)
                pairs = [(i, j) for ii, i in enumerate(lay.data) for j in lay.data[ii + 1:]
                         if m[i] != m[j] and not (i == 0 and m[j] is None)]
                assert tested == len(pairs)
                for r in improved + eq:                                   # no generated move changes a foundation seat
                    assert tokens_in_place(r, p.L) and r[0] is not None
                    assert {i for i in range(len(m)) if m[i] != r[i]}.isdisjoint(lay.cons)
                seen_moves += tested
            # an independent re-check of the whole class over every swap of two non-foundation seats
            rep = pl.verify_class_foundation(t, [pl.to_cross(m, p.L) for m in p.members], a)
            assert rep.is_stable_class and rep.constructed_intact and rep.closed and rep.members_fixed_points
            assert rep.key == (p.score[0], p.score[1], p.a_num)
    assert seen_moves > 100


def test_rotations_stay_but_are_the_identity_on_a_seated_cross():
    t = tier(TOYS[0])
    a = adh({("A", "の"): 2, ("B", "に"): 1})
    p = pl.build_cross(t, "A", budget=BIG, foundation="on", adhesion=a, quotient=False)
    c = p.cross
    here = pl.canon(pl.from_cross(c), p.L)
    for r in geo.moves_rotate():
        c2 = geo.rotate(c, r)
        assert pl.canon(pl.from_cross(c2), p.L) == here                  # the legs are told apart by their particle
        assert pl.canon(pl.from_cross(c2), p.L) in set(p.members)


def test_seam_key_equals_the_plain_key_on_a_toy_without_particles():
    # adhesion = nothing at all (a corpus without a single particle): a == 0 everywhere, so the seated search is the plain search on the
    # contracted cross and the contracted class is the plain class, member for member.
    for sents in TOYS[:3] + [["S a b", "S a b c", "S c d", "d S"]]:
        t = tier(sents)
        for u in t.units():
            for q in (False, True):
                off = pl.build_cross(t, u, budget=BIG, quotient=q)
                on = seated(t, u, quotient=q)
                cm = pl.contract_for_read(on)
                assert set(cm.members) == set(off.members) and cm.members == off.members
                assert on.score == off.score and on.stop == off.stop and on.size == off.size and on.a_num == 0
                assert cm.L == off.L and on.L == pl.min_L(off.size + 6) and cm.twin_sets == off.twin_sets
                assert pl.score_flat(pl.Weights(t, adh({})), on.members[0], on.L) == (off.score[0], off.score[1], 0)
                assert on.class_size >= off.class_size                    # the arms are told apart: ties multiply
        # ... also for the ordered build
        t = tier(sents)
        u = t.units()[0]
        off = pl.build_cross(t, u, budget=BIG, quotient=False, group_insert="ordered")
        on = seated(t, u, quotient=False, group_insert="ordered")
        assert pl.contract_for_read(on).members == off.members and on.score == off.score


def test_adhesion_separates_a_tie_that_n_and_p_leave():
    t = tier(["S a b", "S a b", "S c"])
    a = adh({("a", "の"): 3, ("b", "に"): 2})
    # two arrangements that differ only by which particle arm a unit sits on: equal (n, p), different a
    f1 = ("S", "a", NO, "b", NI, None, DE, None, TO, None, WO, None, GA)
    f2 = ("S", "b", NO, "a", NI, None, DE, None, TO, None, WO, None, GA)
    w = pl.Weights(t, a)
    k1, k2 = pl.score_flat(w, f1, 2), pl.score_flat(w, f2, 2)
    assert k1[:2] == k2[:2] and k1[2] == 144 * 3 + 89 * 2 and k2[2] == 0 and k1 > k2
    # the search sees it: with adhesion the class keeps only the best-a arrangements, without it the ties stay
    free = seated(t, "S", quotient=False)
    stuck = seated(t, "S", counts=a.counts, quotient=False)
    assert stuck.class_size < free.class_size and stuck.score == free.score
    best = pl.contract_for_read(stuck)
    for m in stuck.members:
        legs = {fd.particle_of(m[1 + i * stuck.L + stuck.L - 1]): m[1 + i * stuck.L: 1 + i * stuck.L + stuck.L - 1]
                for i in range(6)}
        assert "a" in legs["の"] and "b" in legs["に"]                            # a on the の arm, b on the に arm, in every member
    assert stuck.a_num == 144 * 3 + 89 * 2 and free.a_num == 0
    assert {fd.a_num(a, m, stuck.L) for m in stuck.members} == {stuck.a_num}
    # the free class is the union over the arm labellings; the adhesion keeps a subset of it, and (n, p) are the same
    assert set(stuck.members) < set(free.members)
    assert pl.cross_score(pl.Weights(t), best.cross) == stuck.score


def test_n_and_p_decide_before_a():
    # a unit with a huge adhesion to the wrong place does not beat a better (n, p): a only breaks ties (OP-G1-5)
    t = tier(["S a", "S a", "S a b", "a b", "a b"])
    free = seated(t, "S", quotient=False)
    for counts in ({("b", "の"): 50, ("a", "に"): 1}, {("a", "の"): 1, ("b", "と"): 100}, {("S", "は"): 9, ("b", "が"): 99}):
        on = seated(t, "S", counts=counts, quotient=False)
        assert on.score == free.score                                         # (n, p) never changes: a only chooses among the ties
        assert set(pl.contract_for_read(on).members) <= set(pl.contract_for_read(free).members)


def test_ha_weight_is_applied_to_the_centre_word():
    # "A B" and "B A": the p edges tie, so the centre could be either; adhesion of A to は (233/377 each) decides
    t = tier(["A B", "B A"])
    free = seated(t, "A", quotient=False)
    assert {m[0] for m in free.members} == {"A", "B"}
    on = seated(t, "A", counts={("A", "は"): 2}, quotient=False)
    assert {m[0] for m in on.members} == {"A"} and on.a_num == 233 * 2
    on_b = seated(t, "A", counts={("B", "は"): 1}, quotient=False)
    assert {m[0] for m in on_b.members} == {"B"} and on_b.a_num == 233
    # は is no arm: a unit on an arm does not get the は weight there, and the centre word does not get an arm particle's weight
    a = adh({("A", "は"): 4, ("A", "の"): 1})
    assert fd.a_num(a, ("A", None, NO, None, NI, None, DE, None, TO, None, WO, None, GA), 2) == 233 * 4
    assert fd.a_num(a, ("B", "A", NO, None, NI, None, DE, None, TO, None, WO, None, GA), 2) == 144 * 1


def test_the_centre_is_found_by_search_not_fixed_to_the_seed():
    t = tier(["S a", "S a", "a b", "a b", "a c"])
    p = seated(t, "S", quotient=False)
    assert p.centres == ("a",) or "a" in p.centres                           # I-02: whatever the search leaves at the centre
    off = pl.build_cross(t, "S", budget=BIG, quotient=False)
    assert set(p.centres) == set(off.centres)


# =============================================================================================================
# Part 5: F1 ordered insertion, stop / skip, max_class, twins, the read view
# =============================================================================================================
def test_f1_ordered_stop_skip_and_budget_work_unchanged_in_form():
    t = tier(["S a b c d e f g h", "S a b", "S z a", "q S z y"])
    a = adh({("a", "の"): 2, ("b", "に"): 1})
    on = pl.build_cross(t, "S", budget=MID, foundation="on", adhesion=a, group_insert="ordered", quotient=False)
    off = pl.build_cross(t, "S", budget=MID, group_insert="ordered", quotient=False)
    assert on.order_log == off.order_log and on.group_insert == "ordered" and on.order == "forward"
    rev = pl.build_cross(t, "S", budget=MID, foundation="on", adhesion=a, group_insert="ordered", order="reverse", quotient=False)
    assert rev.order == "reverse"
    # a tight max_class: the seated class (arms told apart) hits the cap where the plain class does not; the state before is restored
    big = tier(["S a b c d e f g"])
    plain = pl.build_cross(big, "S", budget=MID, quotient=False, group_insert="ordered")
    on = pl.build_cross(big, "S", budget=MID, quotient=False, group_insert="ordered", foundation="on", adhesion=adh({}))
    assert plain.stop == "exhausted" and plain.size == 8 and plain.class_size == 231
    assert on.stop == pl.BUDGET and on.broke_on.reason == "max_class" and on.size == 7 and on.class_size == 720
    assert on.left_in_group >= 1 and on.size == len({u for s in on.steps if s.status == pl.STABLE for u in s.units} | {"S"})
    assert all(tokens_in_place(m, on.L) for m in on.members)
    # skip: the collapsing member is restored away, recorded, and growth goes on
    sk = pl.build_cross(big, "S", budget=MID, quotient=False, group_insert="ordered", on_collapse="skip",
                        foundation="on", adhesion=adh({}))
    assert sk.on_collapse == "skip" and len(sk.skipped) >= 1 and sk.size == 7
    assert all(tokens_in_place(m, sk.L) for m in sk.members)
    # whole-group insertion works too
    wh = pl.build_cross(tier(TOYS[0]), "A", budget=BIG, foundation="on", adhesion=adh({}), quotient=False)
    assert wh.group_insert == "whole" and wh.stop == "exhausted"


def test_twins_must_also_agree_on_adhesion():
    t = tier(["S a b", "S b a", "S c"])
    w = pl.Weights(t)
    rep = pl.find_twins(w, ["S", "a", "b", "c"])
    assert rep["a"] == rep["b"]                                               # a and b are interchangeable for (n, p)
    a_same = adh({("a", "の"): 2, ("b", "の"): 2})
    a_diff = adh({("a", "の"): 2, ("b", "に"): 2})
    assert pl._refine_twins(rep, a_same)["b"] == "a"
    assert pl._refine_twins(rep, a_diff)["b"] == "b" and pl._refine_twins(rep, a_diff)["a"] == "a"
    # quotient on = the T4c search up to the twins: the expanded class of the quotient build is the class of the unit build
    for counts in ({}, dict(a_same.counts), dict(a_diff.counts)):
        q = seated(t, "S", counts=counts, quotient=True)
        n = seated(t, "S", counts=counts, quotient=False)
        assert set(q.expanded_members()) == set(n.members) and q.expanded_size == n.class_size
        assert q.score == n.score and q.a_num == n.a_num
    assert seated(t, "S", counts=dict(a_same.counts), quotient=True).twin_sets == (("a", "b"),)
    assert seated(t, "S", counts=dict(a_diff.counts), quotient=True).twin_sets == ()


def test_contract_for_read_is_the_plain_view():
    t = tier(["S a b", "S a b c", "S c d"])
    a = adh({("a", "の"): 2, ("b", "に"): 1, ("d", "で"): 1, ("S", "は"): 1})
    on = pl.build_cross(t, "S", budget=BIG, foundation="on", adhesion=a, quotient=False)
    cm = pl.contract_for_read(on)
    assert cm.contracted and cm.foundation == on.foundation and cm.L == max(1, on.L - 1) and pl.contract_for_read(cm) is cm
    assert all(len(m) == 6 * cm.L + 1 and not any(fd.is_constructed(x) for x in m) for m in cm.members)
    assert cm.members == tuple(sorted(set(cm.members), key=pl._flat_sort_key)) and len(cm.members) <= len(on.members)
    assert cm.size == on.size and cm.score == on.score and cm.a_num == on.a_num
    assert not any(fd.is_constructed(str(c)) for c in [cm.cross.get(s) for s in geo.seats(cm.L)] if c is not None)
    # a plain placement is returned as it is
    off = pl.build_cross(t, "S", budget=BIG, quotient=False)
    assert pl.contract_for_read(off) is off
    # the JSON names the foundation only when on
    assert json.loads(on.to_bytes())["foundation"] == fd.seats_sha() and json.loads(cm.to_bytes())["contracted"] is True
    assert "foundation" not in json.loads(off.to_bytes())


def test_verify_class_foundation_detects_a_broken_class():
    t = tier(["S a b", "S a b"])
    a = adh({("a", "の"): 3, ("b", "に"): 2})
    p = pl.build_cross(t, "S", budget=BIG, foundation="on", adhesion=a, quotient=False)
    ok = [pl.to_cross(m, p.L) for m in p.members]
    assert pl.verify_class_foundation(t, ok, a).is_stable_class
    # a member with a unit on the wrong arm is not a fixed point (a swap improves a), and the class has two keys
    worse = ("S", "b", NO, "a", NI, None, DE, None, TO, None, WO, None, GA)
    rep = pl.verify_class_foundation(t, ok + [pl.to_cross(worse, 2)], a)
    assert not rep.is_stable_class and not rep.one_key
    rep2 = pl.verify_class_foundation(t, [pl.to_cross(worse, 2)], a)
    assert not rep2.members_fixed_points and not rep2.is_stable_class
    # a class missing one equal-key member is not closed
    if len(ok) > 1:
        assert not pl.verify_class_foundation(t, ok[:-1], a).closed


def test_contract_for_read_keeps_the_arm_labels_aside_without_changing_the_result():
    # review fix (L-G4-44): the labels that the contraction merges stay available for display; the contracted result is the same as before
    t = tier(["S a b c", "S a b", "S c d"])
    for counts in ({}, {("a", "の"): 2, ("b", "に"): 1, ("S", "は"): 1}):
        on = pl.build_cross(t, "S", budget=BIG, foundation="on", adhesion=adh(counts), quotient=False)
        cm = pl.contract_for_read(on)
        old_members = tuple(sorted({pl.canon(fd.contract(m, on.L)[0], cm.L) for m in on.members}, key=pl._flat_sort_key))
        assert cm.members == old_members and cm.contracted and cm.L == max(1, on.L - 1)
        assert cm.arm_labels is not None and len(cm.arm_labels) == len(cm.members)
        assert sum(len(x) for x in cm.arm_labels) == len(on.members)              # a full member = (contracted member, labelling), one to one
        ladder = tuple(SPEC.arms)
        for m, labs in zip(cm.members, cm.arm_labels):
            assert len(set(labs)) == len(labs) and labs == tuple(sorted(labs, key=lambda lab: tuple((q, pl._leg_key(leg)) for q, leg in lab)))
            data = sorted(x for x in m if x is not None)
            for lab in labs:
                assert tuple(q for q, _ in lab) == ladder                          # the six particles, in the ladder order
                assert sorted([m[0]] + [x for _, leg in lab for x in leg if x is not None]) == data   # same units, only the arm they sit on differs
        # the labelled full members are exactly the members of the class, rebuilt
        back = set()
        for m, labs in zip(cm.members, cm.arm_labels):
            for lab in labs:
                f = [m[0]]
                for q, leg in lab:
                    f.extend(tuple(leg) + (fd.token(q),))
                back.add(tuple(f))
        assert back == set(on.members)
        # not a part of the result: not compared, not written, not shown
        assert cm == dataclasses.replace(cm, arm_labels=None) and "arm_labels" not in cm.to_bytes().decode() and "arm_labels" not in repr(cm)
        assert pl.contract_for_read(cm) is cm and on.arm_labels is None
    free = pl.contract_for_read(pl.build_cross(t, "S", budget=BIG, foundation="on", adhesion=adh({}), quotient=False))
    assert any(len(x) > 1 for x in free.arm_labels)                                 # labels do get merged where a does not tell them apart
    assert pl.contract_for_read(pl.build_cross(t, "S", budget=BIG, quotient=False)).arm_labels is None


def test_the_first_class_is_held_to_max_class_and_the_counter_stays_zero():
    # review fix L-G4-47, owner 「規則を適用、数え方の差は受け入れる」 (ops/decisions): _settle used to check max_class only when a class GREW, so the class
    # built from the terminal arrangements could be kept at any size (seated: 1260 / 1080 / 2040 against mid's 1000).  Now it raises "max_class" like the
    # later check.  The toy "S a b c d e" seats classes of 6 / 30 / 120 / 360 / 720 arrangements; the first class of each batch is the terminal one.
    t = tier(["S a b c d e"])
    sizes = [6, 30, 120, 360, 720]
    ref = None
    for mc in (100000, 1000, 719, 360, 100, 29, 10):
        b = pl.Budget(max_class=mc, max_states=1000000, max_moves=100000000)
        for gi in ("ordered", "whole"):
            on = seated(t, "S", budget=b, quotient=False, group_insert=gi)
            kept = [s.class_size for s in on.steps if s.status == pl.STABLE]
            assert all(c <= mc for c in kept) and on.class_size <= mc and on.first_class_over_max == 0
            if gi == "ordered":
                assert kept == sizes[:len(kept)]
                if mc >= 720:
                    assert on.stop == "exhausted" and on.size == 6 and on.class_size == 720
                    ref = ref or on
                else:
                    assert on.stop == pl.BUDGET and on.broke_on.reason == "max_class" and on.size == 1 + len(kept) and on.size < 6
                    assert sizes[len(kept)] > mc                                              # the next class is the one that is refused
            assert json.loads(on.to_bytes())["first_class_over_max"] == 0
    # a budget that is big enough gives the placement it always gave
    assert ref is not None and ref.members == seated(t, "S", budget=BIG, quotient=False, group_insert="ordered").members
    # settle_class (public) refuses an oversize first class too
    one = seated(t, "S", budget=BIG, quotient=False, group_insert="ordered")
    starts = [pl.to_cross(one.members[0], one.L)]
    assert pl.settle_class(t, starts, BIG, pl.Weights(t, adh({}))).status == pl.STABLE
    assert pl.settle_class(t, starts, pl.Budget(max_class=100, max_states=1000000, max_moves=100000000), pl.Weights(t, adh({}))).status == pl.BUDGET
    # off is not serialised with the counter
    off = pl.build_cross(t, "S", budget=pl.Budget(max_class=1, max_states=1000000, max_moves=100000000), quotient=False, group_insert="ordered")
    assert off.first_class_over_max == 0 and "first_class_over_max" not in json.loads(off.to_bytes())


def test_verify_class_foundation_compares_the_recomputed_key_with_the_record():
    # review fix (L-G4-45): the recomputed key (n, p, a) has to equal the Placement's stored score / a_num
    t = tier(["S a b", "S a b", "S c"])
    a = adh({("a", "の"): 3, ("b", "に"): 2})
    p = pl.build_cross(t, "S", budget=BIG, foundation="on", adhesion=a, quotient=False)
    cl = [pl.to_cross(m, p.L) for m in p.members]
    rec = (p.score[0], p.score[1], p.a_num)
    ok = pl.verify_class_foundation(t, cl, a, expected=rec)
    assert ok.is_stable_class and ok.matches_record is True and ok.key == rec
    assert pl.verify_class_foundation(t, cl, a).matches_record is None                 # no record given: as before
    for bad in ((rec[0] + 1, rec[1], rec[2]), (rec[0], rec[1] + 1, rec[2]), (rec[0], rec[1], rec[2] + 1), (rec[0], rec[1], 0)):
        r = pl.verify_class_foundation(t, cl, a, expected=bad)
        assert r.matches_record is False and not r.is_stable_class and r.one_key and r.members_fixed_points and r.key == rec
    # a Placement whose record was tampered with (the a_num) is caught
    forged = dataclasses.replace(p, a_num=p.a_num + 1)
    assert not pl.verify_class_foundation(t, cl, a, expected=(forged.score[0], forged.score[1], forged.a_num)).is_stable_class


def test_option_validation():
    t = tier(TOYS[0])
    with pytest.raises(ValueError):
        pl.build_cross(t, "A", foundation="on")                               # needs the adhesion
    with pytest.raises(ValueError):
        pl.build_cross(t, "A", foundation="maybe")
    with pytest.raises(ValueError):
        pl.build_cross(t, "A", adhesion=adh({}))                              # an adhesion goes with 'on'
    with pytest.raises(ValueError):
        pl.build_cross(t, "A", foundation="on", adhesion=adh({}, name="RUN"))  # the adhesion of another tier
    with pytest.raises(ValueError):
        pl.build_cross(t, "A", foundation="on", adhesion=adh({}), w=pl.Weights(t))
    with pytest.raises(ValueError):
        pl.Placer(t, foundation="on")
    pr = pl.Placer(t, foundation="on", adhesion=adh({("A", "の"): 1}), quotient=False)
    assert pr.cross_for("A").foundation == fd.seats_sha() and pr.cross_for("A") is pr.cross_for("A")
    assert pl.Placer(t).foundation == "off"


def test_a_small_real_corpus_slice_builds_and_verifies():
    rows = [json.loads(l) for l in open(os.path.join(ROOT, "experiments", "line3", "bank2", "data", "fulllead_sents.jsonl"),
                                         encoding="utf-8")][:8]
    space = sp.build_space(rows)
    ads = fd.adhesions_of_space(space)
    small = pl.budget_level("low")
    for name in sp.TIERS:
        ts = space.tiers[name]
        a = ads[name]
        for u in ts.units()[:4]:
            p = pl.build_cross(ts, u, budget=small, foundation="on", adhesion=a, group_insert="ordered")
            assert p.foundation == fd.seats_sha() and all(tokens_in_place(m, p.L) for m in p.members)
            assert all(fd.a_num(a, m, p.L) == p.a_num for m in p.members)
            cm = pl.contract_for_read(p)
            assert all(len(m) == 6 * cm.L + 1 for m in cm.members)
        # the evidence behind every count re-derives from the text
        recs = fd.adhesion_records(space, name)
        assert fd.check_trace(recs, lambda sid: rows[sid]["sent"]) == []


# =============================================================================================================
# Part 6: off is byte-identical; hash seeds
# =============================================================================================================
def test_foundation_off_is_byte_identical():
    for sents in TOYS:
        t = tier(sents)
        for u in t.units():
            a = pl.build_cross(t, u)
            for b in (pl.build_cross(t, u, foundation="off"), pl.Placer(t, foundation="off").cross_for(u)):
                assert a.to_bytes() == b.to_bytes()
            assert a.foundation is None and a.a_num is None and not a.contracted
            o = a.to_json_obj()
            assert "foundation" not in o and "a_num" not in o and "contracted" not in o
        assert pl.serialize_all({u: pl.build_cross(t, u) for u in t.units()}) == \
            pl.serialize_all(pl.Placer(t, foundation="off").precompute_all())
    # the plain canon and layouts are untouched by the existence of the seated ones
    f = ("A", None, None, None, None, "x", "y")
    assert pl.canon(f, 1) == f and pl.canon(("A", "y", "x", None, None, None, None), 1) == f
    # no data unit can be taken for a foundation seat
    t = tier(TOYS[0])
    assert all(not fd.is_constructed(u) for u in t.units())


_SEED_CODE = r"""
import hashlib, sys
sys.path.insert(0, %r)
from test_placement import tier
from verantyx.line3 import placement as pl, foundation as fd
h = hashlib.sha256()
sents = ["S a b c d", "S a b", "S b e", "e S f", "a f"]
t = tier(sents)
a = fd.Adhesion("T", {("a", "の"): 2, ("b", "に"): 1, ("e", "の"): 1, ("S", "は"): 2, ("f", "で"): 3})
for q in (False, True):
    for gi in ("whole", "ordered"):
        for u in t.units():
            p = pl.build_cross(t, u, budget=pl.budget_level("mid"), quotient=q, group_insert=gi, foundation="on", adhesion=a)
            h.update(p.to_bytes())
            h.update(pl.contract_for_read(p).to_bytes())
h.update(a.sha256().encode())
h.update(fd.seats_sha().encode())
print(h.hexdigest())
"""


def test_bytes_are_the_same_for_hash_seeds_0_1_12345():
    outs = []
    for seed in ("0", "1", "12345"):
        env = dict(os.environ, PYTHONHASHSEED=seed, PYTHONDONTWRITEBYTECODE="1", PYTHONPATH=ROOT)
        r = subprocess.run([PY, "-c", _SEED_CODE % os.path.join(ROOT, "tests", "line3")], capture_output=True, text=True,
                           cwd=ROOT, env=env)
        assert r.returncode == 0, r.stderr
        outs.append(r.stdout.strip())
    assert len(outs[0]) == 64 and outs[0] == outs[1] == outs[2]


def test_adhesion_and_spec_bytes_are_the_same_for_hash_seeds():
    code = ("from verantyx.line3 import space as sp, foundation as fd\n"
            "S = %r\n"
            "sp_ = sp.build_space([{'sent': s} for s in S])\n"
            "print(','.join(a.sha256() for a in fd.adhesions_of_space(sp_).values()), fd.seats_sha())\n" % (FIVE,))
    outs = []
    for seed in ("0", "1", "12345"):
        r = subprocess.run([PY, "-c", code], capture_output=True, text=True, cwd=ROOT,
                           env=dict(os.environ, PYTHONHASHSEED=seed, PYTHONPATH=ROOT))
        assert r.returncode == 0, r.stderr
        outs.append(r.stdout.strip())
    assert outs[0] == outs[1] == outs[2] and len(outs[0].split(",")) == 3


def test_no_float_in_the_foundation_module():
    import ast
    for path in (os.path.join(ROOT, "verantyx", "line3", "foundation.py"),):
        tree = ast.parse(open(path, encoding="utf-8").read())
        floats = [n for n in ast.walk(tree) if isinstance(n, ast.Constant) and isinstance(n.value, float)]
        assert floats == []
        divs = [n for n in ast.walk(tree) if isinstance(n, ast.BinOp) and isinstance(n.op, ast.Div)]
        assert divs == []
