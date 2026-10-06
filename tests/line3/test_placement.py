"""T4 tests: placement = deliberately built stable arrangement + energy log
(decision 8, I-04, I-05, I-02, N-02, N-05, N-09, M-1(a)(b))."""
import hashlib
import io
import os
import random
import subprocess
import sys
import tokenize
from fractions import Fraction as Fr
from math import comb

import pytest

from verantyx.line3 import placement as pl
from verantyx.line3.geometry import Cross, Seat
from verantyx.line3.space import TierSpace, build_space, load_jsonl

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SRC = os.path.join(ROOT, "verantyx", "line3", "placement.py")
S300 = os.path.join(ROOT, "experiments", "line3", "data", "S300.jsonl")


def tier(sentences):
    su = tuple(tuple(s.split()) for s in sentences)
    post = {}
    for sid, us in enumerate(su):
        for u in dict.fromkeys(us):
            post.setdefault(u, []).append(sid)
    return TierSpace("T", su, {u: tuple(v) for u, v in post.items()})


TOYS = [
    ["A B C", "A B", "A C D", "B D"],
    ["A B", "A B", "A B C", "A C D", "A D", "C E"],
    ["X A", "X A", "X A B", "X B C", "X B C", "X C D", "X D"],
    ["P Q R S T U V W", "P Q R", "R S T", "V W P", "Q W", "U P", "S P Q"],
]


# ---------------- I-05: every produced arrangement is a fixed point (all single moves)
@pytest.mark.parametrize("sents", TOYS)
def test_every_arrangement_is_a_fixed_point_against_all_moves(sents):
    t = tier(sents)
    for u in t.units():
        p = pl.build_cross(t, u)
        r = pl.verify_fixed_point(t, p.cross)
        assert r.is_fixed_point and r.swaps_improving == 0
        assert r.rotations_tested == 23 and r.rotations_changing_key == 0
        assert r.swaps_total == comb(6 * p.L + 1, 2)
        if p.size > 1:                                # a lone seed is stable by definition (L-63)
            assert r.swaps_equal_key_different == 0   # STABLE means no plateau (L-62)


def test_verifier_is_not_vacuous():
    t = tier(TOYS[0])
    bad = Cross.make(L=1, center="D", arms=[("A",), ("B",), ("C",), (None,), (None,), (None,)])
    r = pl.verify_fixed_point(t, bad)
    assert not r.is_fixed_point and r.swaps_improving > 0


@pytest.mark.skipif(not os.path.exists(S300), reason="S300 not present")
@pytest.mark.parametrize("tn", ["RUN", "WORD", "CHAR"])
def test_s300_slice_fixed_points(tn):
    sp = build_space(load_jsonl(S300))
    t = sp.tiers[tn]
    placer = pl.Placer(t)
    for u in t.units()[:25]:
        p = placer.cross_for(u)
        assert pl.verify_fixed_point(t, p.cross).is_fixed_point
        assert p.capacity == p.size >= 1


# ---------------- ties are flagged, never resolved by order
def test_symmetric_example_is_flagged_not_resolved():
    t = tier(["A B", "B A"])                    # A and B are exactly interchangeable
    p = pl.build_cross(t, "A")
    assert p.stop == "plateau" and p.broke_on.status == pl.PLATEAU
    assert p.size == 1                           # growth stopped at the tie (N-05)
    c = Cross.make(L=1, center="A", arms=[("B",), (None,), (None,), (None,), (None,), (None,)])
    s = pl.classify(t, c)
    assert s.status == pl.PLATEAU
    assert sorted(str(x.center) for x in s.plateau) == ["B"]       # B in the centre is equal
    assert pl.verify_fixed_point(t, c).swaps_equal_key_different == 1


def test_tied_terminals_are_all_reported():
    t = tier(["A B", "B A", "Z"])
    c = Cross.make(L=1, center="Z", arms=[("A",), ("B",), (None,), (None,), (None,), (None,)])
    s = pl.classify(t, c)
    assert s.status == pl.TIED
    assert sorted(str(x.center) for x in s.terminals) == ["A", "B"]   # both kept, none chosen


def test_tie_result_independent_of_unit_label_order():
    # the same space with every unit renamed in reverse alphabetical order: a tie stays a tie
    a = pl.build_cross(tier(["A B", "B A"]), "A")
    b = pl.build_cross(tier(["Y Z", "Z Y"]), "Z")
    assert (a.stop, a.size, a.broke_on.status) == (b.stop, b.size, b.broke_on.status)


# ---------------- N-05 / N-09 capacity
@pytest.mark.parametrize("sents", TOYS)
def test_capacity_recorded_and_restored(sents):
    t = tier(sents)
    for u in t.units():
        p = pl.build_cross(t, u)
        kept = [s for s in p.steps if s.status == pl.STABLE]
        assert p.capacity == p.size == (kept[-1].size_after if kept else 1)
        occupied = sum(1 for s in [Seat("center", 0)] + [Seat(a, k) for a in
                       ("+x", "-x", "+y", "-y", "+z", "-z") for k in range(p.L)]
                       if p.cross.get(s) is not None)
        assert occupied == p.size
        if p.broke_on is not None:                       # the breaking group is NOT in the cross
            assert p.broke_on.status != pl.STABLE and p.broke_on.size_after is None
            assert p.stop == p.broke_on.status
            placed = {str(p.cross.get(s)) for s in [Seat("center", 0)] + [Seat(a, k) for a in
                      ("+x", "-x", "+y", "-y", "+z", "-z") for k in range(p.L)]}
            assert not set(p.broke_on.units) & placed
        else:
            assert p.stop == "exhausted" and p.size == p.candidates + 1


def test_capacity_is_not_a_fixed_number():
    caps = set()
    for sents in TOYS:
        t = tier(sents)
        caps |= {pl.build_cross(t, u).capacity for u in t.units()}
    assert len(caps) > 2
    assert pl.min_L(7) == 1 and pl.min_L(8) == 2 and pl.min_L(13) == 2 and pl.min_L(14) == 3


# ---------------- M-1(b): order of addition
def test_groups_added_in_descending_shares_equal_shares_together():
    t = tier(TOYS[1])
    p = pl.build_cross(t, "A")
    shares = [s.share for s in p.steps]
    assert shares == sorted(shares, reverse=True) and len(set(shares)) == len(shares)
    for s in p.steps:
        assert all(t.n_pair("A", v) == s.share for v in s.units)
    assert [s.units for s in p.steps] == [("B",), ("C", "D")]    # n(A,B)=3; n(A,C)=n(A,D)=2


# ---------------- I-04 key
def test_key_is_sharing_then_word_order():
    t = tier(["A B C", "A B", "A C D", "B D"])
    w = pl.Weights(t)
    c = Cross.make(L=1, center="A", arms=[("B",), ("C",), (None,), (None,), (None,), (None,)])
    assert pl.cross_score(w, c) == (2 + 2, t.p_pair("B", "A") + t.p_pair("C", "A"))
    c2 = Cross.make(L=1, center="B", arms=[("A",), ("D",), (None,), (None,), (None,), (None,)])
    assert pl.cross_score(w, c2)[0] == 2 + 1             # n(B,A) + n(B,D)
    assert (4, 0) > (3, 99) and (3, 2) > (3, 1)           # sharing first, then order (tuple order)


# ---------------- I-02: centre comes from the search, recorded
def test_centre_comes_from_search_and_is_recorded():
    t = tier(TOYS[1])
    moved = [u for u in t.units() if pl.build_cross(t, u).centre_moved]
    assert moved                                         # some seeds end with another centre
    for u in moved:
        p = pl.build_cross(t, u)
        assert p.centre != u and p.seed == u and p.cross.center == p.centre


# ---------------- on-demand == precomputed; order/cache independence
@pytest.mark.parametrize("sents", TOYS)
def test_on_demand_equals_precomputed(sents):
    t = tier(sents)
    full = pl.Placer(t).precompute_all()
    fwd = pl.serialize_all(full)
    units = t.units()
    for u in random.Random(7).sample(units, min(5, len(units))):
        assert pl.Placer(t).cross_for(u).to_bytes() == full[u].to_bytes()
    rev = pl.Placer(t)
    for u in reversed(units):
        rev.cross_for(u)
    assert pl.serialize_all(rev.precompute_all()) == fwd


@pytest.mark.parametrize("sents", TOYS)
def test_independent_of_sentence_order(sents):
    shuffled = list(sents)
    random.Random(3).shuffle(shuffled)
    assert (pl.serialize_all(pl.Placer(tier(sents)).precompute_all())
            == pl.serialize_all(pl.Placer(tier(shuffled)).precompute_all()))


# ---------------- byte identity across hash seeds
_SCRIPT = r"""
import hashlib, sys
sys.path.insert(0, %r)
from verantyx.line3 import placement as pl
from verantyx.line3.space import TierSpace, build_space, load_jsonl
def tier(ss):
    su = tuple(tuple(s.split()) for s in ss); post = {}
    for sid, us in enumerate(su):
        for u in dict.fromkeys(us): post.setdefault(u, []).append(sid)
    return TierSpace("T", su, {u: tuple(v) for u, v in post.items()})
h = hashlib.sha256()
for ss in %r:
    h.update(pl.serialize_all(pl.Placer(tier(ss)).precompute_all()))
import os
s300 = %r
if os.path.exists(s300):
    sp = build_space(load_jsonl(s300))
    for tn in ("RUN", "WORD", "CHAR"):
        t = sp.tiers[tn]; P = pl.Placer(t)
        h.update(pl.serialize_all(P.precompute_all(t.units()[:15])))
        log = pl.energy_log(t, P.cross_for(t.units()[3]).cross, [t.units()[5]])
        h.update(repr(log.to_json_obj()).encode())
print(h.hexdigest())
"""


def test_byte_identical_across_hash_seeds():
    outs = []
    for seed in ("0", "1", "12345"):
        env = dict(os.environ, PYTHONHASHSEED=seed, PYTHONDONTWRITEBYTECODE="1", PYTHONPATH=ROOT)
        r = subprocess.run([sys.executable, "-c", _SCRIPT % (ROOT, TOYS, S300)],
                           capture_output=True, text=True, env=env, timeout=600)
        assert r.returncode == 0, r.stderr
        outs.append(r.stdout.strip())
    assert len(set(outs)) == 1 and len(outs[0]) == 64


# ---------------- exact numbers only
def test_no_float_in_source():
    with open(SRC, "rb") as f:
        toks = list(tokenize.tokenize(io.BytesIO(f.read()).readline))
    for tk in toks:
        if tk.type == tokenize.NUMBER:
            assert "." not in tk.string and "e" not in tk.string.lower()
        if tk.type == tokenize.NAME:
            assert tk.string != "float"


def test_scores_ints_and_log_fractions():
    t = tier(TOYS[0])
    p = pl.build_cross(t, "A")
    assert all(type(x) is int for x in p.score)
    log = pl.energy_log(t, p.cross, ["C"])
    for r in log.records:
        assert isinstance(r.r0, Fr) and isinstance(r.energy, Fr)
        assert r.ratio is None or isinstance(r.ratio, Fr)


# ---------------- N-02 energy log
def test_energy_log_exact_values():
    t = tier(["A B C", "A B", "A C D", "B D"])           # N=4: n A=3 B=3 C=2 D=2
    c = Cross.make(L=2, center="A", arms=[("D", "B"), (None, "C"), (None, None), (None, None),
                                          (None, None), (None, None)])
    log = pl.energy_log(t, c, ["C"])
    got = {r.unit: (r.r0, r.energy, r.ratio) for r in log.records}
    assert got == {"A": (Fr(3, 4), Fr(5, 4), Fr(5, 3)), "B": (Fr(3, 4), Fr(1), Fr(4, 3)),
                   "C": (Fr(1, 2), Fr(1), Fr(2)), "D": (Fr(1, 2), Fr(3, 4), Fr(3, 2))}
    assert [r.unit for r in log.records] == ["A", "D", "B", "C"]      # centre, +x k0, +x k1, -x k1
    empty = pl.energy_log(t, c, [])
    assert all(r.energy == r.r0 and r.ratio == 1 for r in empty.records)   # no query: E = r0
    assert log.to_json_obj()["records"][0]["ratio"] == "5/3"


def test_observe_logs_each_query_from_the_stable_arrangement():
    t = tier(TOYS[0])
    p = pl.build_cross(t, "A")
    logs = pl.observe(t, p, [["B"], ["C", "D"], ["B"]])
    assert len(logs) == 3 and logs[0] == logs[2] and logs[0] != logs[1]
    assert [r.r0 for r in logs[0].records] == [r.r0 for r in logs[1].records]   # the base never moves
