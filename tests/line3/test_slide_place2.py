"""G3-c2 tests (L-580..): the owner's decisions after G3-c as spec switches of verantyx/line3/slide_place.py.

Part 1 (hand tables): the per-axis (Pareto) fixed point -- a move that improves x and worsens z is not taken, a move that improves
both is, a move with a zero summed change but x +1 / z -1 is not an equal-key move; incomparable gains branch; the verifier
(independent of the search) agrees and rejects a Pareto-improvable state.
Part 2 (seats): a unit in both sentences has two seats keyed (unit, sentence), linked by the z self-edge; provenance per seat.
Part 3 (seat_empty_axis): deny leaves the z arms of a one-sentence window empty; allow does not.
Part 4 (growth): interleave order, z_reserved reservation (insertion and swaps) and its capacity rule.
Part 5 (regression): stability sum + seat_key unit + allow + n_then_n1 equals the committed G3-c code / records byte for byte; on
one-sentence windows (no z, no y) per_axis equals sum.
Part 6: spec sha, hash seeds, no float."""
import ast
import hashlib
import importlib.util
import json
import os
import subprocess
import sys

import pytest

from verantyx.line3 import geometry as geo
from verantyx.line3 import placement as pl
from verantyx.line3 import slide as SL
from verantyx.line3 import slide_place as SP
from verantyx.line3 import space as sp

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PY = sys.executable
FL = os.path.join(ROOT, "experiments/line3/bank2/data/fulllead_sents.jsonl")
G3C_COMMIT = "6af87ba9"

TOY = [
    ("A", "東京は日本の首都である。"),
    ("A", "東京は日本の都市である。"),
    ("B", "犬が猫を追う。"),                # 犬 猫
    ("B", "猫が魚を食べる。"),              # 猫 魚 食     (猫 in both sentences)
    ("C", "京都は古い都である。"),          # a one-sentence article
]


def mk2(slide, **kw):
    """G3-c3 (L-628): this file tests the G3-c2 behaviour; the G3-c3 switches are pinned to what G3-c2 did (SP.C2_EQUIV: centre in N,
    arms grow until the budget stops, Pareto judgement), exactly as test_slide_place.py pins G3-c with SP.LEGACY."""
    return SP.make_spec(slide, **dict(SP.C2_EQUIV, **kw))


def toy_rows():
    seen = {}
    out = []
    for t, s in TOY:
        i = seen.get(t, 0)
        seen[t] = i + 1
        out.append({"title": t, "sent": s, "source": "%s#%d" % (t, i)})
    return out


@pytest.fixture(scope="module")
def slide():
    rows = toy_rows()
    return SL.Slide(sp.build_space(rows), rows=rows)


@pytest.fixture(scope="module")
def slide_d():
    rws = [{"title": "D", "sent": "山と川と海と空と森が見える。", "source": "D#0"},
           {"title": "D", "sent": "星と月が光る。", "source": "D#1"}]
    return SL.Slide(sp.build_space(rws), rows=rws)


def pw_of(slide, n, padding="none"):
    return next(p for p in SP.place_windows(slide, padding) if p.window.n == n)


def flat_at(L, centre, **arms):
    out = [centre]
    for a in ("+x", "-x", "+y", "-y", "+z", "-z"):
        v = arms.get(a.replace("+", "p").replace("-", "m"))
        if v is None:
            out.extend([None] * L)
        else:
            out.extend(v if isinstance(v, (list, tuple)) else [v])
    return tuple(out)


def swapped(flat, i, j):
    f = list(flat)
    f[i], f[j] = f[j], f[i]
    return tuple(f)


def scans(table, flat, L=1):
    w = SP.ArmWeights.from_table(table)
    idx = SP.seat_idx(L, SP.arms_ok())
    return SP._scan(w, flat, L, idx), SP._scan_pa(w, flat, L, idx)


# ==== part 1: per-axis fixed point on hand tables ==================================================================
def test_a_move_that_improves_x_and_worsens_z_is_not_taken():
    t = {("+x", "A", "C"): (1, 1), ("+x", "B", "C"): (3, 3), ("+z", "B", "C"): (2, 2), ("+z", "A", "C"): (1, 1)}
    s = flat_at(1, "C", px="A", pz="B")                      # x (1,1) z (2,2); after A<->B: x (3,3) z (1,1)
    s2 = swapped(s, 1, 5)
    (sum_imp, sum_eq, _), (pa_imp, pa_eq, _) = scans(t, s)
    assert sum_imp == [s2]                                    # the summed key rises (3,3) -> (4,4): sum takes it
    assert pa_imp == [] and pa_eq == []                       # per axis: x rises, z falls: neither improving nor equal
    w = SP.ArmWeights.from_table(t)
    tr = SP.tradeoff_counts(w, s, 1, SP.arms_ok())
    assert tr["improve_one_worsen_another"] == 1 and tr["improved_axis"] == {"x": 1, "y": 0, "z": 0} and tr["pareto_improving"] == 0
    cross, wfn = SP.to_cross(s, 1), SP.table_weight_fn(t)
    r = SP.verify_fixed_point_slide(wfn, cross, stability="per_axis")
    assert r.is_fixed_point and r.swaps_improving == 0 and r.swaps_tradeoff == 1
    assert not SP.verify_fixed_point_slide(wfn, cross, stability="sum").is_fixed_point
    assert SP.verify_class_slide(wfn, [cross], stability="per_axis").is_stable_class
    assert not SP.verify_class_slide(wfn, [cross], stability="sum").is_stable_class


def test_a_move_that_improves_both_axes_is_taken():
    t = {("+x", "A", "C"): (1, 1), ("+x", "B", "C"): (3, 3), ("+z", "B", "C"): (1, 1), ("+z", "A", "C"): (2, 2)}
    s = flat_at(1, "C", px="A", pz="B")
    (sum_imp, _e, _t), (pa_imp, _pe, _pt) = scans(t, s)
    assert pa_imp == sum_imp == [swapped(s, 1, 5)]
    cross, wfn = SP.to_cross(s, 1), SP.table_weight_fn(t)
    assert not SP.verify_fixed_point_slide(wfn, cross, stability="per_axis").is_fixed_point
    g = SP.grow(SP.ArmWeights.from_table(t), [("C", "this"), ("A", "this"), ("B", "next")], pl.Budget(), SP.arms_ok(),
                stability="per_axis")
    best = SP.to_cross(g.members[0], g.L)
    assert SP.verify_class_slide(wfn, g.members and [SP.to_cross(m, g.L) for m in g.members], stability="per_axis").is_stable_class
    assert best.center == "C"


def test_zero_summed_change_with_x_up_and_z_down_is_not_an_equal_key_move():
    t = {("+x", "A", "C"): (1, 1), ("+x", "B", "C"): (2, 2), ("+z", "B", "C"): (2, 2), ("+z", "A", "C"): (1, 1)}
    s = flat_at(1, "C", px="A", pz="B")                      # summed key (3,3) before and after the swap
    s2 = swapped(s, 1, 5)
    (sum_imp, sum_eq, _), (pa_imp, pa_eq, _) = scans(t, s)
    assert sum_imp == [] and s2 in sum_eq                     # sum: an equal-key move, the class closes over it
    assert pa_imp == [] and pa_eq == []                       # per axis: not equal (x +1, z -1)
    cross, wfn = SP.to_cross(s, 1), SP.table_weight_fn(t)
    assert SP.verify_fixed_point_slide(wfn, cross, stability="sum").swaps_equal_key_different == 1
    assert SP.verify_fixed_point_slide(wfn, cross, stability="per_axis").swaps_equal_key_different == 0


def test_incomparable_gains_branch_and_a_dominated_gain_is_dropped():
    t = {("+x", "U", "C"): (2, 2), ("-x", "U", "C"): (1, 1), ("+z", "U", "C"): (1, 1)}
    order = [("C", "this"), ("U", "next")]
    pa = SP.grow(SP.ArmWeights.from_table(t), order, pl.Budget(), SP.arms_ok(), stability="per_axis")
    sm = SP.grow(SP.ArmWeights.from_table(t), order, pl.Budget(), SP.arms_ok(), stability="sum")
    assert sm.members == (flat_at(1, "C", px="U"),)                          # the summed key picks +x alone
    assert set(pa.members) == {flat_at(1, "C", px="U"), flat_at(1, "C", pz="U")}   # x-heavy and z-only gains are incomparable; -x is dominated
    wfn = SP.table_weight_fn(t)
    rep = SP.verify_class_slide(wfn, [SP.to_cross(m, 1) for m in pa.members], stability="per_axis")
    assert rep.is_stable_class and rep.keys == 2 and not rep.one_key and rep.antichain
    # a class holding a key dominated by another member's is not stable
    bad = SP.verify_class_slide(wfn, [SP.to_cross(flat_at(1, "C", px="U"), 1), SP.to_cross(flat_at(1, "C", mx="U"), 1)], stability="per_axis")
    assert not bad.antichain and not bad.is_stable_class


def test_pareto_helpers():
    a, b, c = (2, 2, 0, 0, 0, 0), (1, 1, 0, 0, 0, 0), (0, 0, 0, 0, 1, 1)
    assert SP._vdom(a, b) and not SP._vdom(b, a) and not SP._vdom(a, a)
    assert not SP._vdom(a, c) and not SP._vdom(c, a)
    assert SP._maximal([a, b, c, SP.ZERO6]) == sorted([a, c])
    assert SP._vflags((1, -5, 0, 0, 0, 0)) == (True, False)                  # n up, omega down: lexicographic, n decides
    assert SP._vflags((0, 1, 0, 0, 0, -1)) == (True, True)
    assert SP._vflags(SP.ZERO6) == (False, False)


def test_new_verifier_helpers_do_not_use_the_search():
    tree = ast.parse(open(SP.__file__).read())
    fns = {n.name: n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)}
    for name in ("cross_key", "verify_fixed_point_slide", "verify_class_slide", "_pareto_better", "_legal_seat", "_move_ok"):
        called = {c.func.id for c in ast.walk(fns[name]) if isinstance(c, ast.Call) and isinstance(c.func, ast.Name)}
        assert not called & {"_scan", "_scan_pa", "_settle", "_settle_pa", "score_flat", "score_vec", "_swapped", "_swap_delta",
                             "_swap_dvec", "_edge_sum", "_edge_vec", "ArmWeights", "axis_key_flat", "grow", "seat_idx", "_earm",
                             "_lay", "Policy", "_maximal", "_vdom", "_vflags"}, (name, called)


def test_per_axis_search_ends_in_stable_classes_on_the_toy_windows(slide):
    for growth in SP.GROWTHS:
        for seat_key in SP.SEAT_KEYS:
            for empty in SP.SEAT_EMPTY:
                spec = mk2(slide, stability="per_axis", seat_key=seat_key, seat_empty_axis=empty, growth=growth)
                for pw in SP.place_windows(slide, "none"):
                    p = SP.place_window(slide, pw, spec)
                    wfn = SP.counts_weight_fn(slide.counts(pw.window, "corpus"), "RUN")
                    arms = [n for n in SP.ARM_NAMES if n not in p.seatless_arms]
                    r = SP.verify_class_slide(wfn, p.crosses(), stability="per_axis", arm_names=arms,
                                              sides={i.token: i.side for i in p.items}, z_reserved=growth == "z_reserved")
                    assert r.is_stable_class, (growth, seat_key, empty, pw.window.sids, r)


# ==== part 2: two seats for a unit of both sentences ===============================================================
def test_toy_window_has_two_seats_for_the_unit_of_both_sentences(slide):
    pw = pw_of(slide, 2)                                           # 犬 猫 | 猫 魚 食
    one = SP.place_window(slide, pw, mk2(slide, seat_key="unit"))
    two = SP.place_window(slide, pw, mk2(slide, seat_key="unit_sid", growth="n_then_n1"))
    assert [i.unit for i in one.items] == ["犬", "猫", "魚", "食"] and [i.side for i in one.items] == ["this", "both", "next", "next"]
    assert [(i.unit, i.sid, i.side) for i in two.items] == [("犬", 2, "this"), ("猫", 2, "this"), ("猫", 3, "next"), ("魚", 3, "next"), ("食", 3, "next")]
    assert len({i.token for i in two.items}) == 5 and two.items[1].token != two.items[2].token
    rep = two.seats
    assert sorted((r["unit"], r["sid"]) for r in rep) == sorted((i.unit, i.sid) for i in two.items) and two.size == 5
    cat = [r for r in rep if r["unit"] == "猫"]
    assert sorted(r["sid"] for r in cat) == [2, 3]
    assert [r["unit"] for r in one.seats].count("猫") == 1
    sl = {d["unit"]: d for d in two.self_links}
    assert set(sl) == {"猫"} and sl["猫"]["n_z_self"] == 1 and sl["猫"]["both_seated"]
    # "linked" read independently from geometry: the two seats are the two ends of one cross edge
    cr = two.cross
    where = {}
    for s in geo.seats(cr.L):
        c = cr.get(s)
        if c is not None and str(c).startswith("猫"):
            where[str(c)] = s
    assert len(where) == 2
    ends = [{a, b} for a, b in geo.edges(cr.L)]
    assert sl["猫"]["linked"] == ({where[t] for t in where} in ends)


def test_the_z_self_edge_is_a_real_z_edge_between_the_two_seats():
    M0, M1 = "M" + SP.SEP + "0", "M" + SP.SEP + "1"
    t = {("+z", M1, M0): (3, 3), ("-z", M1, M0): (3, 3), ("+z", M0, M1): (3, 3), ("-z", M0, M1): (3, 3)}
    g = SP.grow(SP.ArmWeights.from_table(t), [(M0, "this"), (M1, "next")], pl.Budget(), SP.arms_ok(), stability="per_axis", z_reserved=True)
    assert set(g.members) == {flat_at(1, M0, pz=M1), flat_at(1, M0, mz=M1)}   # the N+1 seat is on a z arm next to the N seat
    wfn = SP.table_weight_fn(t)
    assert all(SP.cross_key(wfn, SP.to_cross(m, 1))[1]["z"] == (3, 3) for m in g.members)
    assert SP.unit_of(M1) == "M" and SP.unit_of("M") == "M"


def test_every_seat_carries_its_provenance(slide):
    pw = pw_of(slide, 0)
    p = SP.place_window(slide, pw, mk2(slide, growth="n_then_n1"))
    counts = slide.counts(pw.window, "corpus")
    assert [r["arm"] for r in p.seats][0] == "centre" and p.seats[0]["position"] == 0
    for r in p.seats:
        assert set(r) >= {"unit", "sid", "arm", "position", "sources"}
        assert r["sid"] in pw.window.sids and r["arm"] in ("centre",) + SP.ARM_NAMES
        occ = r["sources"]["occ"]
        assert occ[0] == "RUN" and occ[1] == r["sid"] and occ[3] == r["unit"]       # the unit's first occurrence in that sentence
        e = r["sources"]["edge"]
        if e is not None:                                                            # the edge to the inner neighbour, from the counts
            assert e["n"] == len(e["sources"])
            if e["axis"] == "z":
                u, v = (r["unit"], e["with"]["unit"]) if r["arm"] == "+z" else (e["with"]["unit"], r["unit"])
                assert e["n"] == counts.n_z("RUN", u, "RUN", v)
            if e["axis"] == "x":
                assert e["n"] == counts.n_x("RUN", r["unit"], e["with"]["unit"])
    ak = p.axis_keys
    assert set(ak) == {"x", "y", "z"} and all(len(v) == 2 for v in ak.values()) and ak["y"] == [0, 0]
    assert p.doc()["axis_keys"] == ak and p.doc()["seats"] == p.seats
    assert [(i["token"], i["unit"], i["side"], i["sid"]) for i in p.doc()["items"]] == [(i.token, i.unit, i.side, i.sid) for i in p.items]
    # the summed key stays recorded and equals the sum of the axis keys
    assert list(p.key) == [sum(v[0] for v in ak.values()), sum(v[1] for v in ak.values())]


# ==== part 3: seat_empty_axis ======================================================================================
def test_min_L_with_fewer_arms():
    assert SP.min_L(7, 4) == 2 and SP.min_L(7, 2) == 3 and SP.min_L(1, 0) == 1 and SP.min_L(2, 0) is None


def test_deny_leaves_the_z_arms_of_a_one_sentence_window_empty(slide):
    pw = pw_of(slide, 4)                                            # 京都 古い 都, no next sentence
    deny = SP.place_window(slide, pw, mk2(slide, seat_empty_axis="deny", growth="n_then_n1"))
    assert dict(deny.axis_evidence) == {"x": True, "y": False, "z": False}
    assert {"+z", "-z"} <= set(deny.seatless_arms)
    for m in deny.members:
        assert all(c is None for c in m[1 + 4 * deny.L:])                    # arms +z and -z hold nothing
    allow = SP.place_window(slide, pw, mk2(slide, seat_empty_axis="allow", growth="n_then_n1"))
    assert "+z" not in allow.seatless_arms
    assert allow.size == deny.size == 3
    # more units than 2 L + 1: the arm length grows (the z arms never take the rest)
    mid = pl.budget_level("mid")
    four = [(u, "this") for u in "ABCD"]
    assert SP.grow(SP.ArmWeights.from_table({}), four, mid, (0, 1), stability="per_axis").L == 2
    assert SP.grow(SP.ArmWeights.from_table({}), four, mid, (0, 1, 4, 5), stability="per_axis").L == 1
    # a pair window keeps its z arms (evidence exists)
    pair = SP.place_window(slide, pw_of(slide, 2), mk2(slide, seat_empty_axis="deny"))
    assert dict(pair.axis_evidence)["z"] and "+z" not in pair.seatless_arms
    # the deny spec differs from the allow spec
    assert mk2(slide, seat_empty_axis="deny").sha256() != mk2(slide, seat_empty_axis="allow").sha256()


def test_a_window_with_no_seatable_arm_holds_only_its_centre():
    g = SP.grow(SP.ArmWeights.from_table({}), [("A", "this"), ("B", "this")], pl.Budget(), (), stability="per_axis")
    assert g.stop == "budget" and g.broke_on.reason == "no_seat" and g.size == 1 and g.left == ("B",)


# ==== part 4: growth orders ========================================================================================
def test_interleave_order(slide):
    w = pw_of(slide, 2).window                                       # 犬 猫 | 猫 魚 食
    it = SP.seat_items(slide, w, "RUN", "unit_sid", "interleave")
    assert [(i.unit, i.sid) for i in it] == [("犬", 2), ("猫", 3), ("猫", 2), ("魚", 3), ("食", 3)]
    nn = SP.seat_items(slide, w, "RUN", "unit_sid", "n_then_n1")
    assert [(i.unit, i.sid) for i in nn] == [("犬", 2), ("猫", 2), ("猫", 3), ("魚", 3), ("食", 3)]
    assert SP.seat_items(slide, w, "RUN", "unit_sid", "z_reserved") == nn
    # seats="unit": a unit is seated once, at its first read
    u = SP.seat_items(slide, w, "RUN", "unit", "interleave")
    assert [(i.unit, i.side, i.sid) for i in u] == [("犬", "this", 2), ("猫", "both", 3), ("魚", "next", 3), ("食", "next", 3)]
    assert tuple((i.token, i.side) for i in SP.seat_items(slide, w, "RUN", "unit", "n_then_n1")) == SP.insertion_order(slide, w, "RUN")
    # sentence N shorter and longer than N+1: the longer one continues alone
    wd = SP.place_windows(slide_d_cache())[0].window
    d = SP.seat_items(slide_d_cache(), wd, "RUN", "unit_sid", "interleave")
    assert [i.unit for i in d] == ["山", "星", "川", "月", "海", "光", "空", "森"]
    assert SP.seat_items(slide, pw_of(slide, 4).window, "RUN", "unit_sid", "interleave") == SP.seat_items(slide, pw_of(slide, 4).window, "RUN", "unit_sid", "n_then_n1")


_SD = []


def slide_d_cache():
    if not _SD:
        rws = [{"title": "D", "sent": "山と川と海と空と森が見える。", "source": "D#0"}, {"title": "D", "sent": "星と月が光る。", "source": "D#1"}]
        _SD.append(SL.Slide(sp.build_space(rws), rows=rws))
    return _SD[0]


def test_interleave_changes_the_order_log_and_seats_n_plus_1_first_words(slide_d):
    base = mk2(slide_d, growth="n_then_n1")
    il = mk2(slide_d, growth="interleave")
    pw = SP.place_windows(slide_d)[0]
    a, b = SP.place_window(slide_d, pw, base), SP.place_window(slide_d, pw, il)
    assert [s.unit for s in b.steps][:4] == ["山", "星", "川", "月"] and [s.unit for s in a.steps][:4] == ["山", "川", "海", "空"]
    tight = mk2(slide_d, growth="interleave", level="low")
    assert SP.place_window(slide_d, pw, tight).size >= 1


def test_z_reserved_binds_insertion_and_swaps_and_grows_the_arms():
    # N-only A wants the z arm, N+1-only B wants the x arm: the reservation forbids both, in insertion and in every swap
    t = {("+z", "A", "C"): (5, 5), ("+x", "B", "C"): (9, 9), ("-z", "A", "C"): (5, 5), ("-x", "B", "C"): (9, 9)}
    order = [("C", "this"), ("A", "this"), ("B", "next")]
    free = SP.grow(SP.ArmWeights.from_table(t), order, pl.Budget(), SP.arms_ok(), stability="per_axis")
    res = SP.grow(SP.ArmWeights.from_table(t), order, pl.Budget(), SP.arms_ok(), stability="per_axis", z_reserved=True)
    assert any(m[5] == "A" or m[6] == "A" for m in free.members) and any(m[1] == "B" or m[2] == "B" for m in free.members)
    for m in res.members:
        L = res.L
        assert "A" not in m[1 + 4 * L:] and "B" not in m[1:1 + 2 * L]
    # capacity: four tokens of sentence N need the x arms only: 1 + 2 L >= 4 -> L = 2 (unreserved: 4 L + 1 >= 4 -> L = 1)
    mid = pl.budget_level("mid")
    four = [(c, "this") for c in "ABCD"]
    assert SP.grow(SP.ArmWeights.from_table({}), four, mid, SP.arms_ok(), stability="per_axis").L == 1
    r4 = SP.grow(SP.ArmWeights.from_table({}), four, mid, SP.arms_ok(), stability="per_axis", z_reserved=True)
    assert r4.L == 2 and r4.size == 4 and r4.stop == "exhausted"
    assert all(c is None for m in r4.members for c in m[1 + 4 * 2:])
    pol = SP.Policy(SP.arms_ok(), True, {"a": "this", "b": "next", "c": "both"})
    assert pol.capacity_ok(3, 6, 0, 0) and not pol.capacity_ok(2, 6, 0, 0) and pol.capacity_ok(1, 1, 1, 1) is True
    assert not pol.capacity_ok(1, 4, 0, 0)


def test_z_reserved_on_the_toy_windows_puts_n_on_x_and_n_plus_1_on_z(slide_d, slide):
    for sl, n in ((slide_d, 0), (slide, 2), (slide, 0)):
        for seat_key in SP.SEAT_KEYS:
            spec = mk2(sl, seat_key=seat_key, growth="z_reserved")
            p = SP.place_window(sl, pw_of(sl, n), spec)
            side = {i.token: i.side for i in p.items}
            for m in p.members:
                for a in range(6):
                    for c in m[1 + a * p.L: 1 + (a + 1) * p.L]:
                        if c is None:
                            continue
                        if SP.ARM_NAMES[a][1] == "x":
                            assert side[c] in ("this", "both")
                        if SP.ARM_NAMES[a][1] == "z":
                            assert side[c] in ("next", "both")
    lone = SP.place_window(slide, pw_of(slide, 4), mk2(slide, growth="z_reserved"))
    assert all(c is None for m in lone.members for c in m[1 + 4 * lone.L:])      # a one-sentence window: no z seat at all
    assert lone.stop == "exhausted" and lone.size == 3


# ==== part 5: regression -- the G3-c behaviour is one named configuration ===========================================
def _old_module():
    src = os.popen("cd %s && git show %s:verantyx/line3/slide_place.py 2>/dev/null" % (ROOT, G3C_COMMIT)).read()
    if not src.strip():
        pytest.skip("the G3-c commit is not available")
    spec = importlib.util.spec_from_loader("slide_place_g3c", loader=None)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["slide_place_g3c"] = mod
    exec(compile(src, "slide_place_g3c", "exec"), mod.__dict__)
    return mod


def test_legacy_configuration_equals_the_committed_g3c_module_on_the_toy_corpus(slide):
    old = _old_module()
    for pad in ("none", "one"):
        for scope in ("corpus", "window"):
            for mode in ("search", "line"):
                o_spec = old.make_spec(slide, scope=scope, padding=pad, mode=mode)
                n_spec = mk2(slide, scope=scope, padding=pad, mode=mode, **SP.LEGACY)
                assert o_spec.to_bytes() == n_spec.to_bytes() and o_spec.sha256() == n_spec.sha256()
                assert [p.doc() for p in old.place_windows(slide, pad)] == [p.doc() for p in SP.place_windows(slide, pad)]
                for opw, npw in zip(old.place_windows(slide, pad), SP.place_windows(slide, pad)):
                    o = old.place_window(slide, opw, o_spec)
                    n = SP.place_window(slide, npw, n_spec)
                    nd = {k: v for k, v in n.doc(True).items() if k not in SP.NEW_RECORD_FIELDS}
                    assert SL.canonical(nd) == o.to_bytes()


def test_legacy_configuration_equals_the_committed_records_of_the_first_40_fulllead_windows():
    path = os.path.join(ROOT, "experiments/line3/g3/place/fulllead_RUN_mid_none_first40.jsonl")
    if not (os.path.exists(FL) and os.path.exists(path)):
        pytest.skip("no fulllead data / committed records")
    rows = sp.load_jsonl(FL)
    full = SL.Slide(sp.build_space(rows), rows=rows)
    spec = mk2(full, **SP.LEGACY)
    recs = [json.loads(line) for line in open(path, encoding="utf-8")]
    assert len(recs) == 40
    timing_and_runner = {"wall_s", "verify", "line", "z_arm_units", "z_arm_fillers", "z_arm_no_evidence"}
    for pw, rec in zip(SP.place_windows(full, "none")[:40], recs):
        d = SP.place_window(full, pw, spec).doc(members=False)
        d = json.loads(json.dumps(d, sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str))
        for f in SP.NEW_RECORD_FIELDS:
            d.pop(f)
        assert d == {k: v for k, v in rec.items() if k not in timing_and_runner}, pw.window.sids


def test_per_axis_equals_sum_on_windows_without_z(slide):
    """A one-sentence window has no z and no y count: the only axis is x, so the per-axis rule and the summed key coincide."""
    for pad in ("none",):
        for pw in SP.place_windows(slide, pad):
            if len(pw.window.sids) != 1:
                continue
            a = SP.place_window(slide, pw, mk2(slide, **dict(SP.LEGACY, stability="sum")))
            b = SP.place_window(slide, pw, mk2(slide, **dict(SP.LEGACY, stability="per_axis")))
            assert a.members == b.members and a.steps == b.steps and a.key == b.key and a.stop == b.stop


def test_per_axis_equals_sum_on_fulllead_one_sentence_windows():
    if not os.path.exists(FL):
        pytest.skip("no fulllead data")
    rows = sp.load_jsonl(FL)
    full = SL.Slide(sp.build_space(rows), rows=rows)
    lone = [p for p in SP.place_windows(full, "none") if len(p.window.sids) == 1][:12]
    for pw in lone:
        a = SP.place_window(full, pw, mk2(full, **dict(SP.LEGACY, stability="sum")))
        b = SP.place_window(full, pw, mk2(full, **dict(SP.LEGACY, stability="per_axis")))
        assert a.members == b.members and a.steps == b.steps and a.stop == b.stop


# ==== part 6: spec, seeds, no float ================================================================================
def test_spec_switches(slide):
    legacy = mk2(slide, **SP.LEGACY)
    assert legacy.is_legacy and "switches" not in legacy.doc()
    dflt = mk2(slide)
    assert dflt.switches() == SP.DEFAULTS == {"stability": "per_axis", "seat_key": "unit_sid", "seat_empty_axis": "allow", "growth": "z_reserved"}
    assert dflt.doc()["switches"] == SP.DEFAULTS and set(dflt.doc()["rules"]) == set(SP.DEFAULTS)
    shas = {legacy.sha256(), dflt.sha256()}
    for k, v in (("stability", "per_axis"), ("seat_key", "unit_sid"), ("seat_empty_axis", "deny"), ("growth", "interleave"), ("growth", "z_reserved")):
        shas.add(mk2(slide, **dict(SP.LEGACY, **{k: v})).sha256())
    assert len(shas) == 7
    for bad in ({"stability": "lex"}, {"seat_key": "x"}, {"seat_empty_axis": "no"}, {"growth": "z"}):
        with pytest.raises(ValueError):
            mk2(slide, **bad)
    p = SP.place_window(slide, pw_of(slide, 0), dflt)
    assert dict(p.switches) == SP.DEFAULTS and p.spec_sha == dflt.sha256()


def test_bytes_are_identical_under_three_hash_seeds_for_every_switch_combination():
    prog = (
        "import hashlib,itertools\n"
        "from verantyx.line3 import slide as SL, slide_place as SP, space as sp\n"
        "T=[('A','東京は日本の首都である。'),('A','東京は日本の都市である。'),('B','犬が猫を追う。'),('B','猫が魚を食べる。'),('C','京都は古い都である。')]\n"
        "seen={};rows=[]\n"
        "for t,s in T:\n i=seen.get(t,0);seen[t]=i+1;rows.append({'title':t,'sent':s,'source':'%s#%d'%(t,i)})\n"
        "S=sp.build_space(rows);sl=SL.Slide(S,rows=rows);h=hashlib.sha256()\n"
        "for st,sk,se,gr in itertools.product(SP.STABILITIES,SP.SEAT_KEYS,SP.SEAT_EMPTY,SP.GROWTHS):\n"
        " spec=SP.make_spec(sl,**SP.C2_EQUIV,stability=st,seat_key=sk,seat_empty_axis=se,growth=gr);h.update(spec.to_bytes())\n"
        " for pw in SP.place_windows(sl,'one'):h.update(SP.place_window(sl,pw,spec).to_bytes())\n"
        "print(h.hexdigest())")
    outs = set()
    for seed in ("0", "1", "12345"):
        out = subprocess.run([PY, "-c", prog], cwd=ROOT, env=dict(os.environ, PYTHONPATH=ROOT, PYTHONHASHSEED=seed), capture_output=True, text=True)
        assert out.returncode == 0, out.stderr
        outs.add(out.stdout.strip())
    assert len(outs) == 1 and len(next(iter(outs))) == 64


def test_no_float_in_new_records(slide):
    def hook(s):
        raise AssertionError("a float in the record: %s" % s)
    for growth in SP.GROWTHS:
        spec = mk2(slide, growth=growth, seat_empty_axis="deny")
        json.loads(spec.to_bytes().decode("utf-8"), parse_float=hook)
        for pw in SP.place_windows(slide, "one"):
            json.loads(SP.place_window(slide, pw, spec).to_bytes().decode("utf-8"), parse_float=hook)


def test_next_seat_on_seat_tokens(slide):
    p = SP.place_window(slide, pw_of(slide, 2), mk2(slide, seat_key="unit_sid", growth="n_then_n1"))
    ns = p.next_seat
    assert ns.exclusive_units == 2 and ns.loose_units == 3                  # 魚 食 only in N+1; the N+1 seat of 猫 is a loose seat
    assert ns.loose_seated >= ns.exclusive_seated


EXPECTED_OWNER_FIRST6 = [((0, 1), 16, 7, 260, "budget", ((18, 16), (0, 0), (1, 1))), ((1, 2), 9, 3, 720, "budget", ((2, 2), (0, 0), (1, 1))),
                         ((2,), 8, 4, 1, "exhausted", ((7, 7), (0, 0), (0, 0))), ((3, 4), 12, 4, 204, "budget", ((9, 8), (0, 0), (2, 2))),
                         ((4, 5), 13, 3, 720, "budget", ((10, 10), (0, 0), (1, 1))), ((5,), 7, 3, 1, "exhausted", ((6, 6), (0, 0), (0, 0)))]


def test_owner_configuration_on_the_first_fulllead_windows_with_the_full_verifier():
    """The defaults (per_axis, unit_sid, allow, z_reserved) on real data: the first 6 windows, every member checked (no sample)."""
    if not os.path.exists(FL):
        pytest.skip("no fulllead data")
    rows = sp.load_jsonl(FL)
    full = SL.Slide(sp.build_space(rows), rows=rows)
    spec = mk2(full)
    assert spec.switches() == SP.DEFAULTS
    got = []
    for pw in SP.place_windows(full, "none")[:6]:
        p = SP.place_window(full, pw, spec)
        wfn = SP.counts_weight_fn(full.counts(pw.window, "corpus"), "RUN")
        arms = [n for n in SP.ARM_NAMES if n not in p.seatless_arms]
        r = SP.verify_class_slide(wfn, p.crosses(), stability="per_axis", arm_names=arms, sides={i.token: i.side for i in p.items},
                                  z_reserved=True)
        assert r.is_stable_class and r.members_checked == p.class_size, (pw.window.sids, r)
        got.append((pw.window.sids, p.size, p.L, p.class_size, p.stop, tuple(tuple(v) for v in p.axis_keys.values())))
    assert got == EXPECTED_OWNER_FIRST6
