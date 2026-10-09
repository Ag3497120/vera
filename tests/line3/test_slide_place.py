"""G3-c tests (L-560..): placement of one WINDOW cross with the per-axis key (verantyx/line3/slide_place.py).

Part 1 (hand tables, 3-6 units): the per-axis key decides by the direction of x, a centre decided by z edges alone, the y arms
have no seats, the class is a fixed point by an independent verifier (written on geometry.edges / swap / rotate and the counts'
accessors, not on the search's flat layout), the verifier rejects a worse arrangement, the labels move with the rotations.
Part 2 (toy corpus, real slide counts): hand numbers of one window, the corpus-scope x weights equal today's (n_pair, p_pair),
insertion order, z self-links, padding windows are constructed and contribute nothing, a window where sentence N fills the
budget records that N+1 got no seat, the foundation labels are recorded and are not in the key, the diagnostic line.
Part 3 (spec): the sha carries the scope, the tier, the padding, the budget, the slide spec.
Part 4: defaults untouched (placement.py is not modified, nothing is hooked), PYTHONHASHSEED 0/1/12345 identical, no float.
Part 5 (fulllead, first windows): the numbers measured at the build of this ticket."""
import ast
import dataclasses
import hashlib
import itertools
import json
import os
import subprocess
import sys
from fractions import Fraction

import pytest

from verantyx.line3 import geometry as geo
from verantyx.line3 import placement as pl
from verantyx.line3 import slide as SL
from verantyx.line3 import slide_place as SP
from verantyx.line3 import space as sp

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PY = sys.executable


def mk_spec(slide, **kw):
    """G3-c2 (L-580): this file tests the G3-c behaviour, which is the configuration SP.LEGACY (stability sum, seats per unit,
    seats allowed on evidence-less arms, growth N then N+1); the module defaults are the owner's G3-c2 configuration and are
    tested in test_slide_place2.py."""
    return SP.make_spec(slide, **dict(SP.LEGACY, **kw))
FL = os.path.join(ROOT, "experiments/line3/bank2/data/fulllead_sents.jsonl")

TOY = [
    ("A", "東京は日本の首都である。"),      # sid 0   RUN 東京 日本 首都
    ("A", "東京は日本の都市である。"),      # sid 1   RUN 東京 日本 都市
    ("B", "犬が猫を追う。"),                # sid 2   RUN 犬 猫
    ("B", "猫が魚を食べる。"),              # sid 3   RUN 猫 魚 食
    ("C", "京都は古い都である。"),          # sid 4   RUN 京都 古い 都   (a one-sentence article)
]


def toy_rows():
    seen = {}
    out = []
    for t, s in TOY:
        i = seen.get(t, 0)
        seen[t] = i + 1
        out.append({"title": t, "sent": s, "source": "%s#%d" % (t, i)})
    return out


@pytest.fixture(scope="module")
def rows():
    return toy_rows()


@pytest.fixture(scope="module")
def space(rows):
    return sp.build_space(rows)


@pytest.fixture(scope="module")
def slide(space, rows):
    return SL.Slide(space, rows=rows)


@pytest.fixture(scope="module")
def spec(slide):
    return mk_spec(slide)


def pw_of(slide, n, padding="none"):
    return next(p for p in SP.place_windows(slide, padding) if p.window.n == n)


# ==== helpers: tables and a brute force that shares no code with the search ===========================================
def xz_table(units, pairs, z=()):
    """Hand table.  pairs: {(a, b): (n, p_ab)}: a and b share n sentences, a precedes b in p_ab of them (so b precedes a in
    n - p_ab).  z: {(u, v): n_z}: u in N and v in N+1 in n_z windows.  +x (o,i) = (n, p(o,i)); -x (o,i) = (n, p(i,o));
    +z (o,i) = (n_z(o,i),)*2; -z (o,i) = (n_z(i,o),)*2; y weighs nothing."""
    t = {}
    zd = dict(z)
    for (a, b), (n, p) in pairs.items():
        for o, i, po in ((a, b, p), (b, a, n - p)):
            t[("+x", o, i)] = (n, po)
            t[("-x", o, i)] = (n, n - po)
    for o in units:
        for i in units:
            if o == i:
                continue
            if zd.get((o, i), 0):
                t[("+z", o, i)] = (zd[(o, i)], zd[(o, i)])
            if zd.get((i, o), 0):
                t[("-z", o, i)] = (zd[(i, o)], zd[(i, o)])
    return t


def brute(wfn, units, L, y_seats=False):
    """The best total key over EVERY placement of the units on the seatable seats (centre non-empty) and the set of the
    arrangements that reach it (flat form).  Written on geometry only."""
    seats = [s for s in geo.seats(L) if SP._seat_ok(s, y_seats)]
    best, arrs = None, set()
    for perm in itertools.permutations(seats, len(units)):
        cells = dict(zip(perm, units))
        cen = cells.get(geo.CENTER)
        if cen is None:
            continue
        arms = [[cells.get(geo.Seat(a, k)) for k in range(L)] for a in geo.AXES]
        c = geo.Cross.make(L=L, center=cen, arms=arms)
        k = SP.cross_key(wfn, c)[0]
        if best is None or k > best:
            best, arrs = k, {SP._flat_of(c)}
        elif k == best:
            arrs.add(SP._flat_of(c))
    return best, arrs


def grown(table, order, budget=pl.Budget(), y_seats=False):
    return SP.grow(SP.ArmWeights.from_table(table), order, budget, SP.arms_ok(y_seats))


def flat_at(L, centre, **arms):
    """flat_at(1, "C", px="A", mx="B") -> the flat of L=1 with those units; keys px mx py my pz mz (k = 0 .. L-1 as a list)."""
    out = [centre]
    for a in ("+x", "-x", "+y", "-y", "+z", "-z"):
        v = arms.get(a.replace("+", "p").replace("-", "m"))
        if v is None:
            out.extend([None] * L)
        else:
            out.extend(v if isinstance(v, (list, tuple)) else [v])
    return tuple(out)


# ==== part 1: hand tables ==========================================================================================
def test_x_direction_decides_the_arrangement():
    """A precedes C in both sentences, B follows C in both: the arrangement is fixed by the direction of x alone (the n of
    every pair is the same whichever arm holds it)."""
    units = ["A", "B", "C"]
    t = xz_table(units, {("A", "C"): (2, 2), ("C", "B"): (2, 2)})
    g = grown(t, [("A", "this"), ("C", "this"), ("B", "this")])
    assert g.stop == "exhausted" and g.L == 1
    assert g.members == (flat_at(1, "C", px="A", mx="B"),)
    wfn = SP.table_weight_fn(t)
    best, arrs = brute(wfn, units, 1)
    assert best == (4, 4) and arrs == set(g.members)
    # the mirror: A follows C, B precedes it -> the arms swap, and only the direction of x says so
    t2 = xz_table(units, {("C", "A"): (2, 2), ("B", "C"): (2, 2)})
    g2 = grown(t2, [("A", "this"), ("C", "this"), ("B", "this")])
    assert g2.members == (flat_at(1, "C", px="B", mx="A"),)
    assert brute(SP.table_weight_fn(t2), units, 1)[1] == set(g2.members)
    # the same counts n with the wrong directions would score (4, 0): the second component is the direction
    c = SP.to_cross(flat_at(1, "C", px="B", mx="A"), 1)
    assert SP.cross_key(wfn, c)[0] == (4, 0)


def test_centre_decided_by_z_edges_alone():
    """No x evidence at all.  M lies in both sentences, U in N, V in N+1: z(U, M) = 1 and z(M, V) = 1.  The only arrangement
    with both z edges has M at the centre, U on +z (outer in N, inner in N+1) and V on -z; the mirrored counts swap the arms."""
    units = ["U", "M", "V"]
    t = xz_table(units, {}, {("U", "M"): 1, ("M", "V"): 1})
    order = [("M", "both"), ("U", "this"), ("V", "next")]            # sentence N reads M then U; then sentence N+1
    g = grown(t, order)
    assert g.members == (flat_at(1, "M", pz="U", mz="V"),)
    best, arrs = brute(SP.table_weight_fn(t), units, 1)
    assert best == (2, 2) and arrs == set(g.members)
    t2 = xz_table(units, {}, {("M", "U"): 1, ("V", "M"): 1})
    g2 = grown(t2, order)
    assert g2.members == (flat_at(1, "M", pz="V", mz="U"),)
    # the insertion order matters (F1 open point 2): U, M, V gets stuck in a local fixed point below the optimum
    g3 = grown(t, [("U", "this"), ("M", "both"), ("V", "next")])
    assert SP.cross_key(SP.table_weight_fn(t), SP.to_cross(g3.members[0], 1))[0] == (1, 1)
    assert SP.verify_class_slide(SP.table_weight_fn(t), [SP.to_cross(m, 1) for m in g3.members]).is_stable_class
    # the per-axis split of the key: x contributes nothing, z everything
    w = SP.ArmWeights.from_table(t)
    assert SP.axis_key_flat(w, g.members[0], 1) == (("x", 0, 0), ("y", 0, 0), ("z", 2, 2))


def test_every_hand_table_class_is_a_fixed_point_by_the_independent_verifier():
    units = ["A", "B", "C", "D", "E"]
    cases = [
        xz_table(units, {("A", "B"): (3, 3), ("B", "C"): (2, 1), ("C", "D"): (2, 2), ("A", "E"): (1, 0)},
                 {("A", "D"): 2, ("B", "E"): 1, ("C", "E"): 1}),
        xz_table(units, {("A", "B"): (2, 2), ("B", "C"): (2, 2), ("C", "D"): (2, 2), ("D", "E"): (2, 2)}),
        xz_table(units, {}, {("A", "C"): 2, ("A", "D"): 1, ("B", "E"): 2, ("B", "C"): 1}),
    ]
    for t in cases:
        order = [(u, "this") for u in units]
        g = grown(t, order)
        assert g.stop == "exhausted"
        crosses = [SP.to_cross(m, g.L) for m in g.members]
        rep = SP.verify_class_slide(SP.table_weight_fn(t), crosses)
        assert rep.is_stable_class and rep.one_key and rep.members_fixed_points and rep.closed
        assert rep.centres_nonempty and rep.no_unit_on_unseatable_arm and rep.labels_follow_rotation
        fp = SP.verify_fixed_point_slide(SP.table_weight_fn(t), crosses[0])
        assert fp.is_fixed_point and fp.rotations_tested == 23 and fp.rotations_changing_key == 0 and fp.swaps_improving == 0
        # no unit ever on a y arm; L from 4 seatable arms
        assert g.L == SP.min_L(5, 4) == 1
        for m in g.members:
            assert m[1 + 2 * g.L: 1 + 4 * g.L] == (None,) * (2 * g.L)


def test_verifier_rejects_a_worse_arrangement_and_a_unit_on_a_y_arm():
    units = ["A", "B", "C"]
    t = xz_table(units, {("A", "C"): (2, 2), ("C", "B"): (2, 2)})
    wfn = SP.table_weight_fn(t)
    bad = SP.to_cross(flat_at(1, "C", px="B", mx="A"), 1)             # the directions reversed: key (4, 0)
    r = SP.verify_fixed_point_slide(wfn, bad)
    assert not r.is_fixed_point and r.swaps_improving >= 1
    onY = SP.to_cross(flat_at(1, "C", py="A", mx="B"), 1)
    assert not SP.verify_class_slide(wfn, [onY]).no_unit_on_unseatable_arm
    assert not SP.verify_class_slide(wfn, [onY]).is_stable_class
    assert SP.verify_class_slide(wfn, [onY], y_seats=True).no_unit_on_unseatable_arm


def test_the_verifier_does_not_use_the_search_layout():
    src = open(SP.__file__).read()
    tree = ast.parse(src)
    fns = {n.name: n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)}
    for name in ("cross_key", "verify_fixed_point_slide", "verify_class_slide"):
        called = {c.func.id for c in ast.walk(fns[name]) if isinstance(c, ast.Call) and isinstance(c.func, ast.Name)}
        assert not called & {"_scan", "_settle", "score_flat", "_swapped", "_swap_delta", "_edge_sum", "ArmWeights",
                             "axis_key_flat", "grow", "seat_idx", "_earm", "_lay"}, (name, called)


def test_labels_move_with_the_arms_under_all_23_rotations():
    units = ["A", "B", "C"]
    t = xz_table(units, {("A", "C"): (2, 2), ("C", "B"): (2, 2)})
    wfn = SP.table_weight_fn(t)
    c = SP.to_cross(flat_at(1, "C", px="A", mx="B"), 1)
    base = SP.cross_key(wfn, c)
    assert base[0] == (4, 4)
    seen = set()
    for r in geo.moves_rotate():
        c2 = geo.rotate(c, r)
        assert SP.cross_key(wfn, c2) == base                                      # the key (and its axis split) is rotation-invariant
        assert c2.arms == c.arms and c2.center == c.center                        # the contents stay on their labelled arms
        w = c2.world_arms()
        assert w[c2.orientation(0)] == ("A",) and w[c2.orientation(1)] == ("B",)  # +x still holds A, -x still holds B, at their new directions
        seen.add((c2.orientation(0), c2.orientation(1)))
    assert len(seen) > 1 and SP.verify_fixed_point_slide(wfn, c).labels_follow_rotation
    # labels at fixed WORLD directions would change the key: the reading the owner did not choose (G2 4)
    rot = next(r for r in geo.moves_rotate() if r(0) == 1 and r(1) == 0)         # +x and -x exchange their world directions
    w = geo.rotate(c, rot).world_arms()
    assert w[0] == ("B",) and w[1] == ("A",)                                      # world view changed ...
    assert SP.cross_key(wfn, geo.rotate(c, rot))[0] == (4, 4)                     # ... the key did not


def test_y_arms_have_no_seats_in_s1_and_capacity_is_four_arms():
    assert SP.arms_ok() == (0, 1, 4, 5) and SP.arms_ok(True) == (0, 1, 2, 3, 4, 5)
    assert [SP.min_L(n, 4) for n in (1, 5, 6, 9, 10, 13)] == [1, 1, 2, 2, 3, 3]
    assert SP.seat_idx(2, SP.arms_ok()) == (0, 1, 2, 3, 4, 9, 10, 11, 12)
    units = [chr(65 + i) for i in range(6)]
    t = xz_table(units, {(units[i], units[i + 1]): (2, 2) for i in range(5)})
    g = grown(t, [(u, "this") for u in units])
    assert g.L == 2 and g.size == 6 and g.stop == "exhausted"
    for m in g.members:
        assert m[1 + 2 * 2: 1 + 4 * 2] == (None,) * 4                              # +y, -y hold nothing


def test_search_result_is_a_local_fixed_point_not_always_the_global_optimum():
    """The class is a fixed point of single swaps (as every class of placement.py); it need not be the best of all
    arrangements.  The brute force bounds it from above; on this table the search stops below the optimum."""
    units = ["P", "Q", "R"]
    t = xz_table(units, {("P", "Q"): (2, 2), ("P", "R"): (1, 1), ("Q", "R"): (1, 1)})
    order = [(u, "this") for u in units]
    g = grown(t, order)
    wfn = SP.table_weight_fn(t)
    best, _ = brute(wfn, units, 1)
    got = SP.cross_key(wfn, SP.to_cross(g.members[0], g.L))[0]
    assert got <= best
    assert SP.verify_class_slide(wfn, [SP.to_cross(m, g.L) for m in g.members]).is_stable_class


def test_budget_stop_in_sentence_n_gives_next_sentence_no_seat():
    """Seven units that all tie (each pair n = 1, direction consistent): the class grows with every unit; with a small
    budget growth stops before the collapse inside sentence N, and sentence N+1 got no seat."""
    units = ["a", "b", "c", "d", "e", "f", "g"]
    pairs = {(u, v): (1, 1) for u, v in itertools.combinations(units, 2)}
    t = xz_table(units, pairs)
    order = [(u, "this") for u in units[:5]] + [(u, "next") for u in units[5:]]
    tight = pl.Budget(max_class=3, max_states=20000, max_moves=400000)
    g = grown(t, order, tight)
    assert g.stop == "budget" and g.broke_on is not None and g.broke_on.reason == "max_class"
    assert g.broke_on.side == "this"                                             # it broke inside sentence N
    assert set(g.left) >= {"f", "g"} and g.size == len(order) - len(g.left)
    seated = [u for u in g.members[0] if u is not None]
    ns = SP.next_seat(order, seated)
    assert not ns.strict and not ns.loose and ns.exclusive_units == 2 and ns.exclusive_seated == 0
    # with room enough everything is seated and N+1 has its seats
    g2 = grown(t, order, pl.Budget(max_class=100000, max_states=1000000, max_moves=50000000))
    ns2 = SP.next_seat(order, [u for u in g2.members[0] if u is not None])
    assert g2.stop == "exhausted" and ns2.strict and ns2.exclusive_seated == 2
    # the state before the breaking unit is what is kept: the same as growing the inserted units alone
    g3 = grown(t, order[:g.size], tight)
    assert g3.members == g.members and g3.stop == "exhausted"


def test_shared_unit_has_one_seat_and_strict_versus_loose_next_seat():
    order = [("a", "this"), ("m", "both"), ("n", "next")]
    assert SP.next_seat(order, ["a", "m"]) == SP.NextSeat(1, 0, 2, 1)
    assert not SP.next_seat(order, ["a", "m"]).strict and SP.next_seat(order, ["a", "m"]).loose
    assert SP.next_seat(order, ["n"]).strict
    with pytest.raises(ValueError):
        SP.grow(SP.ArmWeights.from_table({}), [("a", "this"), ("a", "next")], pl.Budget(), SP.arms_ok())


def test_a_window_without_units_is_recorded_not_guessed():
    g = SP.grow(SP.ArmWeights.from_table({}), [], pl.Budget(), SP.arms_ok())
    assert g.stop == "empty" and g.size == 0


# ==== part 2: the toy corpus with the real slide counts ===========================================================
def test_insertion_order_is_sentence_n_word_order_then_sentence_n_plus_1(slide):
    assert SP.insertion_order(slide, pw_of(slide, 0).window, "RUN") == (
        ("東京", "both"), ("日本", "both"), ("首都", "this"), ("都市", "next"))
    assert SP.insertion_order(slide, pw_of(slide, 2).window, "RUN") == (
        ("犬", "this"), ("猫", "both"), ("魚", "next"), ("食", "next"))
    assert SP.insertion_order(slide, pw_of(slide, 4).window, "RUN") == (("京都", "this"), ("古い", "this"), ("都", "this"))


def test_corpus_scope_x_weights_equal_todays_pair_weights(space, slide):
    tier = space.tiers["RUN"]
    w0 = pl.Weights(tier)
    for n in (0, 2):
        pw = pw_of(slide, n)
        counts = slide.counts(pw.window, "corpus")
        w = SP.ArmWeights.from_counts(counts, "RUN")
        units = [u for u, _ in SP.insertion_order(slide, pw.window, "RUN")]
        for o, i in itertools.permutations(units, 2):
            assert w(0, o, i) == w0(o, i)                                        # +x : (n_pair, p_pair(o, i))
            assert w(1, o, i) == (w0(o, i)[0], w0(i, o)[1])                      # -x : (n_pair, p_pair(i, o))
            assert w(2, o, i) == w(3, o, i) == (0, 0)                             # one tier: y has no edge (L-G3-5)
            assert w(4, o, i)[0] == w(4, o, i)[1] == counts.n_z("RUN", o, "RUN", i)
            assert w(5, o, i)[0] == counts.n_z("RUN", i, "RUN", o)
    assert SP.ArmWeights.from_counts(slide.counts(pw_of(slide, 0).window, "corpus"), "RUN")(0, None, "x") == (0, 0)


def test_window_a_hand_numbers(slide, spec):
    """Window (0, 1): 東京 日本 首都 | 東京 日本 都市.  n_x(東京, 日本) = 2 with 東京 first both times; every other pair of one
    sentence n_x = 1, every pair (N, N+1) n_z = 1.  Best arrangement by hand: 東京 at the centre, 日本 on -x (2, 2), 首都
    on +z (1, 1), 都市 on -z (1, 1): key (4, 4)."""
    p = SP.place_window(slide, pw_of(slide, 0), spec)
    assert p.key == (4, 4) and p.size == 4 and p.L == 1 and p.stop == "exhausted"
    assert p.members == (flat_at(1, "東京", mx="日本", pz="首都", mz="都市"),)
    assert p.axis_key == (("x", 2, 2), ("y", 0, 0), ("z", 2, 2)) and p.axis_splits == 1
    assert p.order_log == (("東京", "both"), ("日本", "both"), ("首都", "this"), ("都市", "next"))
    assert p.next_seat == SP.NextSeat(1, 1, 3, 3) and p.next_seat.strict
    assert p.centres == ("東京",) and p.seatless_arms == ("+y", "-y")
    wfn = SP.counts_weight_fn(slide.counts(p.window.window, "corpus"), "RUN")
    best, arrs = brute(wfn, [u for u, _ in p.order_log], 1)
    assert best == p.key and set(p.members) <= arrs


def test_every_toy_window_class_is_a_fixed_point_and_below_or_at_the_brute_force_optimum(slide, spec):
    below = 0
    for pw in SP.place_windows(slide):
        for scope in ("corpus", "window"):
            sc = dataclasses.replace(spec, scope=scope)
            p = SP.place_window(slide, pw, sc)
            counts = slide.counts(pw.window, scope)
            wfn = SP.counts_weight_fn(counts, "RUN")
            rep = SP.verify_class_slide(wfn, p.crosses())
            assert rep.is_stable_class, (pw.window.sids, scope, rep)
            assert rep.size == p.class_size
            fp = SP.verify_fixed_point_slide(wfn, p.cross)
            assert fp.is_fixed_point and fp.rotations_changing_key == 0
            units = [u for u, _ in p.order_log]
            best, arrs = brute(wfn, units, SP.min_L(len(units), 4))
            assert p.key <= best and set(p.members) <= arrs | set(p.members)
            below += p.key < best
            # the search's own score equals the verifier's key, member by member (two routes, one number)
            for m in p.crosses():
                assert SP.cross_key(wfn, m)[0] == p.key
    assert below >= 1                                                           # a local fixed point is not always the optimum (window (1,))


def test_z_self_link_is_counted_but_a_unit_has_one_seat(slide, spec):
    p = SP.place_window(slide, pw_of(slide, 2), spec)               # 猫 in both sentences of B
    assert ("猫", 1) in p.z_self
    cells = [c for m in p.members for c in m if c is not None]
    assert cells.count("猫") == len(p.members)                       # exactly one seat per member
    q = SP.place_window(slide, pw_of(slide, 4), spec)
    assert q.z_self == ()


@pytest.fixture(scope="module")
def slide_d():
    rws = [{"title": "D", "sent": "山と川と海と空と森が見える。", "source": "D#0"},      # RUN 山 川 海 空 森
           {"title": "D", "sent": "星と月が光る。", "source": "D#1"}]                  # RUN 星 月 光
    s = sp.build_space(rws)
    return SL.Slide(s, rows=rws)


def test_window_where_n_fills_the_budget_records_that_n_plus_1_got_no_seat(slide_d):
    spec = mk_spec(slide_d)
    pw = SP.place_windows(slide_d)[0]
    full = SP.place_window(slide_d, pw, spec)
    assert full.stop == "exhausted" and full.size == 8 and full.next_seat == SP.NextSeat(3, 3, 3, 3) and full.next_seat.strict
    assert [s.class_size for s in full.steps] == [1, 1, 1, 8, 20, 1, 26, 138]
    tight = dataclasses.replace(spec, budget=pl.Budget(max_class=8, max_states=20000, max_moves=400000))
    p = SP.place_window(slide_d, pw, tight)
    assert p.stop == "budget" and p.broke_on is not None and p.broke_on.reason == "max_class"
    assert (p.broke_on.unit, p.broke_on.side) == ("森", "this")            # it broke while reading sentence N
    assert p.left == ("森", "星", "月", "光") and p.size == 4
    assert p.next_seat == SP.NextSeat(3, 0, 3, 0) and not p.next_seat.strict and not p.next_seat.loose
    d = p.doc()
    assert d["next_seat"]["strict"] is False and d["stop"] == "budget" and d["broke_on"]["status"] == "budget"
    assert d["left"] == ["森", "星", "月", "光"] and d["budget"]["max_class"] == 8
    # what is kept is the class before the breaking unit: the same as placing the first four units alone
    order = [(u, s) for u, s in p.order_log][:4]
    g = SP.grow(SP.ArmWeights.from_counts(slide_d.counts(pw.window, "corpus"), "RUN"), order, pl.budget_level("mid"), SP.arms_ok())
    assert tuple(sorted(g.members, key=SP._fk)) == p.members
    # the stop does not hide: stopping inside sentence N+1 is recorded the same way, with part of N+1 seated
    mid = dataclasses.replace(spec, budget=pl.Budget(max_class=30, max_states=20000, max_moves=400000))
    q = SP.place_window(slide_d, pw, mid)
    assert q.stop == "budget" and q.broke_on.side == "next" and q.next_seat.exclusive_seated == 0


def test_padding_windows_are_constructed_and_contribute_nothing(slide, spec):
    none = SP.place_windows(slide, "none")
    one = SP.place_windows(slide, "one")
    assert [p.window.sids for p in none] == [(0, 1), (1,), (2, 3), (3,), (4,)]
    assert [p.window.sids for p in one] == [(0, 1), (1,), (2, 3), (3,), (4,)]    # same units: the lone window IS the padded one
    assert [p.constructed for p in none] == [False] * 5 and [p.constructed for p in one] == [False, True, False, True, True]
    assert [p.pad for p in one] == [None, "pad:A#2", None, "pad:B#2", "pad:C#1"]
    # every real sentence is the first sentence of a window (it has a next-sentence window) only with padding
    firsts_one = {p.window.sids[0] for p in one}
    assert firsts_one == set(range(5))
    pad_spec = dataclasses.replace(spec, padding="one")
    assert pad_spec.sha256() != spec.sha256()
    for a, b in zip(none, one):
        pa = SP.place_window(slide, a, spec)
        pb = SP.place_window(slide, b, pad_spec)
        assert pa.members == pb.members and pa.key == pb.key and pa.order_log == pb.order_log and pa.axis_key == pb.axis_key
        assert pa.doc()["class_sha256"] == pb.doc()["class_sha256"]
        assert pb.window.constructed == b.constructed
        d = pb.doc()
        assert d["padding"] == {"constructed": b.constructed, "sentence": b.pad, "evidence": False,
                                "contributes": "no unit, no edge, no count, no seat"}
        assert d["spec_sha256"] == pad_spec.sha256()
        # the padding sentence is nowhere in the record as a unit, an edge or a count
        flat = [c for m in pb.members for c in m if c is not None] + [u for u, _ in pb.order_log] + [u for u, _ in pb.z_self]
        assert not any(isinstance(c, str) and c.startswith("pad:") for c in flat)
        if b.constructed:
            assert pb.next_seat is None and pb.z_self == ()
            counts = slide.counts(b.window, "corpus")
            assert counts.z == {} and all(src[0] != -1 for srcs in counts.z.values() for src in srcs)
    # a pad that has no sentence cannot change a count: counts of the padded window == counts of the lone window
    assert slide.counts(one[1].window, "corpus").to_bytes() == slide.counts(none[1].window, "corpus").to_bytes()


def test_padding_table_lists_the_round_number_options(slide):
    tbl = SP.padding_table(slide)
    assert tbl["real_sentences"] == 5 and tbl["articles"] == 3
    assert tbl["one_per_article"] == {"pads": 3, "total": 8}
    # article sizes 2, 2, 1.  Every reading first gives each article's last sentence a next sentence (one pad at least).
    assert tbl["per_article_even"] == {"pads": 2 + 2 + 1, "total": 10}                # 2->4, 2->4, 1->2
    assert tbl["per_article_multiple_of_4"] == {"pads": 2 + 2 + 3, "total": 12}       # 2->4, 2->4, 1->4
    assert tbl["corpus_multiple_of_100_after_one_per_article"] == {"pads": 95, "total": 100}
    assert tbl["corpus_multiple_of_100_alone"]["total"] == 100 and "note" in tbl["corpus_multiple_of_100_alone"]


def test_foundation_labels_are_recorded_and_are_not_in_the_key(space, rows, slide, spec):
    p = SP.place_window(slide, pw_of(slide, 0), spec)
    assert p.arm_labels == (("+x", "の"), ("-x", "に"), ("+y", "で"), ("-y", "と"), ("+z", "を"), ("-z", "が"))
    assert dict(p.arm_weights) == {"+x": Fraction(144, 377), "-x": Fraction(89, 377), "+y": Fraction(55, 377),
                                   "-y": Fraction(34, 377), "+z": Fraction(21, 377), "-z": Fraction(1, 29)}
    d = p.doc()
    assert d["axis_labels"] == {"+x": "の", "-x": "に", "+y": "で", "-y": "と", "+z": "を", "-z": "が"}
    assert d["arm_weights"]["+x"] == Fraction(144, 377) and d["weights_in_key"] is False
    # another ladder: another slide spec sha, the same arrangement and key (the weights enter neither)
    other = SL.Slide(space, SL.default_spec(space, foundation=SL.p7(("は", "が", "を", "と", "で", "に", "の"))), rows)
    sp2 = mk_spec(other)
    assert sp2.sha256() != mk_spec(slide).sha256()
    q = SP.place_window(other, pw_of(other, 0), sp2)
    assert q.members == p.members and q.key == p.key and q.arm_labels != p.arm_labels


def test_record_has_axis_labels_axis_key_padding_flag_spec_sha_and_order_log(slide, spec):
    p = SP.place_window(slide, pw_of(slide, 0), spec)
    d = json.loads(p.to_bytes().decode("utf-8"))
    for k in ("axis_labels", "axis_key", "padding", "spec_sha256", "slide_spec_sha256", "scope", "order_log", "steps", "key",
              "class_size", "next_seat", "members", "tier", "mode", "budget", "stop", "z_self", "axis_split_set"):
        assert k in d
    assert d["spec_sha256"] == spec.sha256() and d["slide_spec_sha256"] == slide.spec.sha256() and d["scope"] == "corpus"
    assert d["axis_key"] == {"x": [2, 2], "y": [0, 0], "z": [2, 2]} and d["order_log"][0] == ["東京", "both"]
    # the split by axis of EVERY member (review): counts add up to the class, one row per distinct split, each at the total key
    ss = d["axis_split_set"]
    assert len(ss) == d["axis_splits"] and sum(r[6] for r in ss) == d["class_size"] and ss == sorted(ss)
    assert all((r[0] + r[2] + r[4], r[1] + r[3] + r[5]) == tuple(d["key"]) for r in ss)
    assert [2, 2, 0, 0, 2, 2] in [r[:6] for r in ss]
    assert d["arm_weights"]["+x"] == "144/377"                       # exact, as a string
    assert p.to_bytes() == SL.canonical(p.doc(True))
    assert "members" not in p.doc(members=False) and p.doc(members=False)["class_sha256"] == d["class_sha256"]


def test_line_version_is_a_diagnostic_with_no_search(slide, spec):
    line = dataclasses.replace(spec, mode="line")
    p = SP.place_window(slide, pw_of(slide, 0), line)
    # 東京 日本 首都 | 都市: centre 日本 (lower middle), +x 東京 (the unit before it), -x 首都 (after), -z 都市 (N+1)
    assert p.members == (flat_at(1, "日本", px="東京", mx="首都", mz="都市",) ,) and p.stop == "line" and p.mode == "line"
    assert p.steps == () and line.sha256() != spec.sha256()
    wfn = SP.counts_weight_fn(slide.counts(p.window.window, "corpus"), "RUN")
    fp = SP.verify_fixed_point_slide(wfn, p.cross)
    assert fp.rotations_changing_key == 0
    assert p.key == SP.cross_key(wfn, p.cross)[0]
    # the lone window: one sentence on the x axis
    q = SP.place_window(slide, pw_of(slide, 4), line)
    assert q.members == (flat_at(1, "古い", px="京都", mx="都"),)
    # the line's fixed-point status is a measurement (recorded by the report), not a promise
    assert isinstance(fp.is_fixed_point, bool)


def test_y_seats_switch_changes_the_spec_and_the_class_is_still_stable(slide, spec):
    ys = dataclasses.replace(spec, y_seats=True)
    assert ys.sha256() != spec.sha256()
    p = SP.place_window(slide, pw_of(slide, 0), ys)
    wfn = SP.counts_weight_fn(slide.counts(p.window.window, "corpus"), "RUN")
    assert p.seatless_arms == () and SP.verify_class_slide(wfn, p.crosses(), y_seats=True).is_stable_class


# ==== part 3: the spec ============================================================================================
def test_spec_sha_carries_scope_tier_padding_budget_mode_and_the_slide_spec(space, rows, slide, spec):
    base = spec.sha256()
    assert spec.doc()["scope"] == "corpus" and spec.doc()["slide_spec_sha256"] == slide.spec.sha256()
    assert spec.short() == base[:12] and len(base) == 64
    for ch in (dict(scope="window"), dict(tier="WORD"), dict(padding="one"), dict(y_seats=True), dict(mode="line"),
               dict(budget=pl.budget_level("high")), dict(budget=pl.Budget(1, 2, 3))):
        assert dataclasses.replace(spec, **ch).sha256() != base, ch
    assert mk_spec(slide).sha256() == base
    assert mk_spec(slide, level="high").sha256() == dataclasses.replace(spec, budget=pl.budget_level("high")).sha256()
    other = SL.Slide(space, SL.default_spec(space, lone="none"), rows)
    assert mk_spec(other).sha256() != base
    with pytest.raises(ValueError):
        SP.place_window(other, SP.place_windows(other)[0], spec)       # a spec of another slide spec is refused
    for bad in (dict(scope="x"), dict(tier="X"), dict(padding="two"), dict(mode="x")):
        with pytest.raises(ValueError):
            dataclasses.replace(spec, **bad)


# ==== part 4: defaults untouched, determinism, no float ============================================================
def test_nothing_is_hooked_and_placement_py_is_unmodified():
    code = ("import sys\nimport verantyx.line3.slide_place\n"
            "bad=[m for m in sys.modules if m.startswith('verantyx.line3.') and m.split('.')[2] in "
            "('ask','cycle','matryoshka','carry','carry_query','readout','trace_check','grammar')]\n"
            "print(','.join(bad))")
    out = subprocess.run([PY, "-c", code], cwd=ROOT, env=dict(os.environ, PYTHONPATH=ROOT), capture_output=True, text=True)
    assert out.returncode == 0 and out.stdout.strip() == "", out.stdout + out.stderr
    for mod in ("ask", "cycle", "matryoshka", "cli"):
        p = os.path.join(ROOT, "verantyx/line3/%s.py" % mod) if mod != "cli" else os.path.join(ROOT, "verantyx/cli.py")
        assert "slide_place" not in open(p).read(), mod
    try:
        head = subprocess.run(["git", "show", "HEAD:verantyx/line3/placement.py"], cwd=ROOT, capture_output=True, check=True).stdout
    except Exception:
        pytest.skip("no git history here")
    assert head == open(os.path.join(ROOT, "verantyx/line3/placement.py"), "rb").read()


def test_existing_placement_outputs_are_unchanged_by_importing_slide_place(tmp_path):
    prog = ("import hashlib,sys\n%s\n"
            "from verantyx.line3 import placement as pl\nfrom verantyx.line3 import space as sp\n"
            "rows=[{'sent':s,'source':'t#%%d'%%i} for i,s in enumerate(['東京は日本の首都である。','東京は日本の都市である。','犬が猫を追う。'])]\n"
            "t=sp.build_space(rows).tiers['RUN']\n"
            "pls={u:pl.build_cross(t,u,group_insert='ordered') for u in t.units()}\n"
            "print(hashlib.sha256(pl.serialize_all(pls)).hexdigest())")
    outs = []
    for pre in ("", "import verantyx.line3.slide_place"):
        out = subprocess.run([PY, "-c", prog % pre], cwd=ROOT, env=dict(os.environ, PYTHONPATH=ROOT, PYTHONHASHSEED="0"),
                             capture_output=True, text=True)
        assert out.returncode == 0, out.stderr
        outs.append(out.stdout.strip())
    assert outs[0] == outs[1] and len(outs[0]) == 64


def test_bytes_are_identical_under_three_hash_seeds():
    prog = (
        "import hashlib,dataclasses\n"
        "from verantyx.line3 import slide as SL, slide_place as SP, space as sp\n"
        "T=[('A','東京は日本の首都である。'),('A','東京は日本の都市である。'),('B','犬が猫を追う。'),('B','猫が魚を食べる。'),('C','京都は古い都である。')]\n"
        "seen={};rows=[]\n"
        "for t,s in T:\n i=seen.get(t,0);seen[t]=i+1;rows.append({'title':t,'sent':s,'source':'%s#%d'%(t,i)})\n"
        "S=sp.build_space(rows);sl=SL.Slide(S,rows=rows);h=hashlib.sha256()\n"
        "for pad in ('none','one'):\n"
        " for sc in ('corpus','window'):\n"
        "  for mode in ('search','line'):\n"
        "   spec=SP.make_spec(sl,scope=sc,padding=pad,mode=mode,**SP.LEGACY);h.update(spec.to_bytes())\n"
        "   for pw in SP.place_windows(sl,pad):h.update(SP.place_window(sl,pw,spec).to_bytes())\n"
        "h.update(repr(sorted(SP.padding_table(sl).items())).encode())\n"
        "print(h.hexdigest())")
    outs = set()
    for seed in ("0", "1", "12345"):
        out = subprocess.run([PY, "-c", prog], cwd=ROOT, env=dict(os.environ, PYTHONPATH=ROOT, PYTHONHASHSEED=seed),
                             capture_output=True, text=True)
        assert out.returncode == 0, out.stderr
        outs.add(out.stdout.strip())
    assert len(outs) == 1 and len(next(iter(outs))) == 64


def test_no_float_anywhere(slide, spec):
    src = open(SP.__file__).read()
    tree = ast.parse(src)
    for n in ast.walk(tree):
        if isinstance(n, ast.Constant):
            assert not isinstance(n.value, float)
        if isinstance(n, ast.Name):
            assert n.id != "float"
        if isinstance(n, ast.BinOp):
            assert not isinstance(n.op, ast.Div)
    for pw in SP.place_windows(slide):
        p = SP.place_window(slide, pw, spec)

        def hook(s):
            raise AssertionError("a float in the record: %s" % s)
        json.loads(p.to_bytes().decode("utf-8"), parse_float=hook)
    json.loads(spec.to_bytes().decode("utf-8"), parse_float=lambda s: (_ for _ in ()).throw(AssertionError(s)))


# ==== part 5: fulllead, first windows ==============================================================================
@pytest.fixture(scope="module")
def full():
    if not os.path.exists(FL):
        pytest.skip("no fulllead data")
    rws = sp.load_jsonl(FL)
    s = sp.build_space(rws)
    return SL.Slide(s, rows=rws)


def test_fulllead_first_windows_are_stable_classes_and_the_numbers_are_the_measured_ones(full):
    spec = mk_spec(full)
    pws = SP.place_windows(full)
    assert len(pws) == 592 and sum(len(p.window.sids) == 2 for p in pws) == 292
    got = []
    for pw in pws[:6]:
        p = SP.place_window(full, pw, spec)
        wfn = SP.counts_weight_fn(full.counts(pw.window, "corpus"), "RUN")
        assert SP.verify_class_slide(wfn, p.crosses()).is_stable_class
        got.append((pw.window.sids, p.size, p.L, p.class_size, p.stop, p.key))
    assert got == [((0, 1), 9, 2, 240, "budget", (8, 8)), ((1, 2), 5, 1, 2, "budget", (3, 3)),
                   ((2,), 7, 2, 252, "budget", (4, 4)), ((3, 4), 9, 2, 24, "budget", (6, 6)),
                   ((4, 5), 10, 3, 600, "budget", (11, 11)), ((5,), 7, 2, 252, "exhausted", (4, 4))]
