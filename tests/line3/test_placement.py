"""T4b tests: placement = deliberately built stable CLASS of tied arrangements + energy log
(decision 8, I-04, I-05, I-02, N-02, N-05, N-09, M-1(a)(b); owner: grow tied arrangements as
one state, arm assignment not distinguished; L-70..L-73)."""
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


SMALL = pl.Budget(max_class=200, max_states=1500)     # keeps the S300 tests fast; always recorded

TOYS = [
    ["A B C", "A B", "A C D", "B D"],
    ["A B", "A B", "A B C", "A C D", "A D", "C E"],
    ["X A", "X A", "X A B", "X B C", "X B C", "X C D", "X D"],
    ["P Q R S T U V W", "P Q R", "R S T", "V W P", "Q W", "U P", "S P Q"],
]


# ---------------- I-05 / L-70: every member of every class is a fixed point; class closed
@pytest.mark.parametrize("sents", TOYS)
def test_every_member_of_every_class_is_a_fixed_point_and_class_is_closed(sents):
    t = tier(sents)
    for u in t.units():
        p = pl.build_cross(t, u)
        assert p.stop == "exhausted"
        for c in p.crosses():
            r = pl.verify_fixed_point(t, c)
            assert r.is_fixed_point and r.swaps_improving == 0
            assert r.rotations_tested == 23 and r.rotations_changing_key == 0
            assert r.swaps_total == comb(6 * p.L + 1, 2)
        rep = pl.verify_class(t, p.crosses())
        assert rep.one_key and rep.members_fixed_points and rep.closed and rep.is_stable_class
        assert rep.size == p.class_size == len(set(p.members))
        # closure by an independent route: every equal-key different arrangement one swap away
        # from a member is a member
        here = set(p.members)
        for c in p.crosses():
            r = pl.verify_fixed_point(t, c)
            assert r.swaps_equal_key_different <= len(here)


def test_verifier_is_not_vacuous():
    t = tier(TOYS[0])
    bad = Cross.make(L=1, center="D", arms=[("A",), ("B",), ("C",), (None,), (None,), (None,)])
    r = pl.verify_fixed_point(t, bad)
    assert not r.is_fixed_point and r.swaps_improving > 0
    assert not pl.verify_class(t, [bad]).is_stable_class
    # a class that is a fixed point but NOT closed is detected
    p = pl.build_cross(tier(["A B", "B A"]), "A")
    assert p.class_size >= 2
    rep = pl.verify_class(tier(["A B", "B A"]), p.crosses()[:1])
    assert rep.members_fixed_points and not rep.closed and not rep.is_stable_class


@pytest.mark.skipif(not os.path.exists(S300), reason="S300 not present")
@pytest.mark.parametrize("tn", ["RUN", "WORD", "CHAR"])
def test_s300_slice_classes(tn):
    sp = build_space(load_jsonl(S300))
    t = sp.tiers[tn]
    placer = pl.Placer(t, SMALL)
    for u in t.units()[:12]:
        p = placer.cross_for(u)
        assert pl.verify_class(t, p.crosses()).is_stable_class
        assert p.capacity == p.size >= 1
        assert p.stop in ("exhausted", "budget")
        assert p.budget == SMALL                       # the budget used is recorded


# ---------------- symmetric corpora GROW (the T4 problem); ties are one state, never resolved
def test_symmetric_toys_grow():
    p = pl.build_cross(tier(["A B C"]), "A")
    assert p.capacity == 3 and p.stop == "exhausted"
    t = tier(["A B", "B A"])                    # A and B exactly interchangeable
    p = pl.build_cross(t, "A")
    assert p.size == 2 and p.stop == "exhausted"
    assert p.class_size == 2 and p.centres == ("A", "B")          # both centres, one state
    assert p.centre is None and p.centre_moved
    # no member is preferred: the same space with the labels reversed gives the same shape
    q = pl.build_cross(tier(["Y Z", "Z Y"]), "Z")
    assert (q.size, q.class_size, q.stop) == (p.size, p.class_size, p.stop)
    chain = [" ".join(("A V%d" % i).split()) for i in range(1, 10) for _ in range(i)]
    big = pl.build_cross(tier(chain), "A")                    # distinct shares: grows past L=1
    assert big.capacity == 10 and big.L == 2 and big.stop == "exhausted"
    assert pl.verify_class(tier(chain), big.crosses()).is_stable_class


def test_class_is_the_union_of_equal_key_branches_and_arm_assignment_is_not_distinguished():
    t = tier(["A B", "A C", "B C"])             # B and C interchangeable around A (up to order)
    p = pl.build_cross(t, "A")
    assert p.stop == "exhausted"
    # arrangements equal up to arm assignment are ONE arrangement: members are canonical
    for m in p.members:
        assert pl.canon(m, p.L) == m
    # permuting the arms of a member is the same state
    c = p.crosses()[0]
    arms = [c.arms[a] for a in range(6)]
    c2 = Cross.make(L=p.L, center=c.center, arms=list(reversed(arms)))
    assert pl.canon(pl.from_cross(c2), p.L) == pl.canon(pl.from_cross(c), p.L)
    assert pl.cross_score(pl.Weights(t), c) == pl.cross_score(pl.Weights(t), c2)


def test_settle_class_from_a_symmetric_start_returns_the_whole_class():
    t = tier(["A B", "B A", "Z"])
    c = Cross.make(L=1, center="Z", arms=[("A",), ("B",), (None,), (None,), (None,), (None,)])
    s = pl.settle_class(t, [c])
    assert s.status == pl.STABLE
    assert pl.verify_class(t, s.members).is_stable_class
    cs = {str(x.center) for x in s.members}
    assert {"A", "B"} <= cs


def test_budget_is_explicit_and_recorded():
    t = tier(["A B C D E F G H"])
    tiny = pl.Budget(max_class=3, max_states=10)
    p = pl.build_cross(t, "A", budget=tiny)
    assert p.stop == "budget" and p.broke_on.status == pl.BUDGET and p.broke_on.reason
    assert p.budget == tiny and p.to_json_obj()["budget"] == {"max_class": 3, "max_states": 10,
                                                      "max_moves": pl.MAX_MOVES}
    assert p.capacity == p.size == 1                      # the previous class restored (N-05)
    t2 = tier(["A B", "B A"])             # A, B interchangeable: the class has 2 members
    st = Cross.make(L=1, center="A", arms=[("B",)] + [(None,)] * 5)
    assert pl.settle_class(t2, [st], pl.Budget(max_class=1, max_states=10)).status == pl.BUDGET
    assert pl.settle_class(t2, [st], pl.Budget(max_class=2, max_states=10)).status == pl.STABLE
    # a larger budget is a different, recorded result — never silently cut
    # 9 units of EQUAL share in one sentence: the tied class exceeds the default budget:
    # typed BUDGET, previous class restored, never a silent cut
    d = pl.build_cross(tier(["A B C D E F G H I J"]), "A")
    assert d.stop == "budget" and d.capacity == 1 and d.broke_on.reason in (
        "max_class", "max_states", "max_moves")


def test_tie_result_independent_of_unit_label_order():
    a = pl.build_cross(tier(["A B", "B A"]), "A")
    b = pl.build_cross(tier(["Y Z", "Z Y"]), "Z")
    assert (a.stop, a.size, a.class_size) == (b.stop, b.size, b.class_size)


# ---------------- N-05 / N-09 capacity
@pytest.mark.parametrize("sents", TOYS)
def test_capacity_recorded_and_restored(sents):
    t = tier(sents)
    for u in t.units():
        p = pl.build_cross(t, u)
        kept = [s for s in p.steps if s.status == pl.STABLE]
        assert p.capacity == p.size == (kept[-1].size_after if kept else 1)
        for c in p.crosses():
            occupied = sum(1 for s in [Seat("center", 0)] + [Seat(a, k) for a in
                           ("+x", "-x", "+y", "-y", "+z", "-z") for k in range(p.L)]
                           if c.get(s) is not None)
            assert occupied == p.size
        assert p.stop == "exhausted" and p.size == p.candidates + 1 and p.broke_on is None


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
    assert all(s.class_size >= 1 for s in p.steps)


# ---------------- I-04 key
def test_key_is_sharing_then_word_order():
    t = tier(["A B C", "A B", "A C D", "B D"])
    w = pl.Weights(t)
    c = Cross.make(L=1, center="A", arms=[("B",), ("C",), (None,), (None,), (None,), (None,)])
    assert pl.cross_score(w, c) == (2 + 2, t.p_pair("B", "A") + t.p_pair("C", "A"))
    c2 = Cross.make(L=1, center="B", arms=[("A",), ("D",), (None,), (None,), (None,), (None,)])
    assert pl.cross_score(w, c2)[0] == 2 + 1             # n(B,A) + n(B,D)
    assert (4, 0) > (3, 99) and (3, 2) > (3, 1)           # sharing first, then order (tuple order)


# ---------------- I-02: centre(s) come from the search, recorded
def test_centres_come_from_search_and_are_recorded():
    t = tier(TOYS[1])
    moved = [u for u in t.units() if pl.build_cross(t, u).centre_moved]
    assert moved                                         # some seeds end with another centre
    for u in moved:
        p = pl.build_cross(t, u)
        assert p.seed == u and p.centres != (u,)
        assert set(p.centres) == {c.center for c in p.crosses()}


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
        t = sp.tiers[tn]; P = pl.Placer(t, pl.Budget(200, 1500))
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


def test_observe_class_logs_every_member():
    t = tier(["A B", "B A"])
    p = pl.build_cross(t, "A")
    logs = pl.observe_class(t, p, [["A"], ["B"]])
    assert len(logs) == p.class_size == 2 and all(len(x) == 2 for x in logs)


def test_observe_logs_each_query_from_the_stable_arrangement():
    t = tier(TOYS[0])
    p = pl.build_cross(t, "A")
    logs = pl.observe(t, p, [["B"], ["C", "D"], ["B"]])
    assert len(logs) == 3 and logs[0] == logs[2] and logs[0] != logs[1]
    assert [r.r0 for r in logs[0].records] == [r.r0 for r in logs[1].records]   # the base never moves


# ---------------- L-77: an empty centre is not a state
def test_lone_seed_class_has_no_seed_at_arm_end_member():
    p = pl.build_cross(tier(["A"]), "A")
    assert p.class_size == 1 and p.centres == ("A",) and p.members[0][0] == "A"
    lone = pl.settle_class(tier(["A"]), [Cross.make(L=1, center="A", arms=[(None,)] * 6)])
    assert len(lone.members) == 1 and lone.members[0].center == "A"
    with pytest.raises(ValueError):
        pl.settle_class(tier(["A"]), [Cross.make(L=1, center=None, arms=[("A",)] + [(None,)] * 5)])


@pytest.mark.parametrize("sents", TOYS)
def test_no_member_has_an_empty_centre(sents):
    t = tier(sents)
    for u in t.units():
        p = pl.build_cross(t, u)
        assert all(m[0] is not None for m in p.members)
        assert None not in p.centres
        assert pl.verify_class(t, p.crosses()).centres_nonempty


def test_verify_class_flags_an_empty_centre():
    t = tier(["A B"])
    bad = Cross.make(L=1, center=None, arms=[("A",), ("B",)] + [(None,)] * 4)
    r = pl.verify_class(t, [bad])
    assert not r.centres_nonempty and not r.is_stable_class


@pytest.mark.skipif(not os.path.exists(S300), reason="S300 not present")
def test_s300_slice_has_no_empty_centre():
    t = build_space(load_jsonl(S300)).tiers["WORD"]
    placer = pl.Placer(t, SMALL)
    for u in t.units()[:12]:
        assert all(m[0] is not None for m in placer.cross_for(u).members)


# ---------------- L-76: five named budget levels
def test_budget_levels():
    assert pl.LEVEL_ORDER == ("low", "mid-low", "mid", "high", "max")
    bs = [pl.budget_level(n) for n in pl.LEVEL_ORDER]
    for a, b in zip(bs, bs[1:]):
        assert b.max_moves == 4 * a.max_moves
        assert b.max_states >= 3 * a.max_states and b.max_class >= 3 * a.max_class
    assert pl.budget_level("mid") == pl.Budget()          # the T4b default
    assert [pl.level_name(b) for b in bs] == list(pl.LEVEL_ORDER)
    assert pl.level_name(pl.Budget(1, 2, 3)) is None
    with pytest.raises(KeyError):
        pl.budget_level("huge")
    # a higher level never gives a smaller capacity on a toy that hits the low budget
    t = tier(["A B C D E F G H"])
    caps = [pl.build_cross(t, "A", budget=b).capacity for b in bs[:2]]
    assert caps == sorted(caps)
