"""G3-c3 tests (L-620..): the owner's decisions after G3-c2 and after the G3-c2 audit as spec switches of verantyx/line3/slide_place.py.

Part 1 (the centre in N+1): Policy with x_side "next" / centre_only; a hand table where the best centre is a unit of N+1 (x arms hold
N+1, z arms hold N, the independent verifier accepts, every seat is legal); a toy window whose placement picks the centre in N+1;
both growths kept when their keys are equal / incomparable; the shorter growth is padded to the longer arm length and judged at its own
(L-623); the record's insertion order (order_log / items) is the representative's growth's, like its steps.
Part 2 (arm_cap): "x" freezes the arm length when the centre's sentence has been read, the units of the other sentence that do not
fit are recorded as unseated (not a stop); "budget" is the G3-c2 growth.
Part 3 (strict judgement): a Pareto-stable state with an improving x move is UNSTABLE_AXIS_IMPROVABLE (axis x), the record's counts equal
the independent verifier's; the Pareto rule marks nothing; committed run-4 windows that have trade-off moves are marked.
Part 4 (regression): centre_scope "n" + arm_cap "budget" + judgement "pareto" (SP.C2_EQUIV) equals the committed G3-c2 run-4 records of
the first 40 pair windows byte for byte (timing / runner fields excluded, the G3-c3 fields stripped); LEGACY still equals G3-c (also
in test_slide_place*.py).
Part 5: spec switches, hash seeds, no float."""
import json
import os
import subprocess
import sys

import pytest

from verantyx.line3 import placement as pl
from verantyx.line3 import slide as SL
from verantyx.line3 import slide_place as SP
from verantyx.line3 import space as sp

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PY = sys.executable
FL = os.path.join(ROOT, "experiments/line3/bank2/data/fulllead_sents.jsonl")
RUN4 = os.path.join(ROOT, "experiments/line3/g3/place2/fulllead_RUN_mid_none_per_axis_unit_sid_allow_z_reserved_pairs292.jsonl")

TOY_N1 = [("A", "犬が走る。"), ("A", "猫と魚と鳥が走る。"), ("B", "猫と魚と鳥が泳ぐ。"), ("B", "犬が鳥を追う。")]           # window (0, 1): the best centre is in N+1
TOY_EQ = [("A", "山が高い。"), ("A", "川と海と空と森が見える。"), ("B", "川と海が広い。"), ("B", "空と森が青い。")]           # window (2, 3): equal keys
TOY_INC = [("A", "星が光る。"), ("A", "星と月と雲と空が光る。"), ("B", "月と雲が白い。"), ("B", "空と星が青い。")]
TOY_D = [("D", "山と川と海と空と森が見える。"), ("D", "星と月が光る。")]
TOY_OLD = [("A", "東京は日本の首都である。"), ("A", "東京は日本の都市である。"), ("B", "犬が猫を追う。"), ("B", "猫が魚を食べる。"), ("C", "京都は古い都である。")]


def mkslide(toy):
    seen = {}
    rows = []
    for t, s in toy:
        i = seen.get(t, 0)
        seen[t] = i + 1
        rows.append({"title": t, "sent": s, "source": "%s#%d" % (t, i)})
    return SL.Slide(sp.build_space(rows), rows=rows)


@pytest.fixture(scope="module")
def s_n1():
    return mkslide(TOY_N1)


@pytest.fixture(scope="module")
def s_old():
    return mkslide(TOY_OLD)


@pytest.fixture(scope="module")
def s_d():
    return mkslide(TOY_D)


def pw_of(slide, n):
    return next(p for p in SP.place_windows(slide, "none") if p.window.n == n)


def verify(slide, pw, p, spec, sample=None):
    """The independent verifier on a record, with each member's own reservation (member_x_side)."""
    wfn = SP.counts_weight_fn(slide.counts(pw.window, spec.scope), spec.tier)
    arms = [n for n in SP.ARM_NAMES if n not in p.seatless_arms]
    zres = spec.growth == "z_reserved"
    return SP.verify_class_slide(wfn, p.crosses(), stability=spec.stability, arm_names=arms, sides={i.token: i.side for i in p.items},
                                 z_reserved=zres, centre_only=zres and spec.centre_scope == "both", x_sides=list(p.member_x_side), own_Ls=list(p.member_L),
                                 sample=sample)


def assert_legal(p, spec):
    """Written from the rule: x arms hold the sentence of the member's centre, z arms the other; the centre takes only the x arms' sentence."""
    side = {i.token: i.side for i in p.items}
    for m, xs in zip(p.members, p.member_x_side):
        zs = "next" if xs == "this" else "this"
        for a in range(6):
            for c in m[1 + a * p.L: 1 + (a + 1) * p.L]:
                if c is None:
                    continue
                ax = SP.ARM_NAMES[a][1]
                assert ax != "y"
                if spec.growth == "z_reserved":
                    assert side[c] in ((xs, "both") if ax == "x" else (zs, "both")), (m, xs)
        if spec.growth == "z_reserved" and spec.centre_scope == "both":
            assert side[m[0]] in (xs, "both")


# ==== part 1: the centre in N+1 =====================================================================================
def test_policy_x_side_exchanges_the_roles_and_centre_only_restricts_the_centre():
    sides = {"a": "this", "b": "next", "c": "both"}
    arms = SP.arms_ok()
    p_this = SP.Policy(arms, True, sides)
    p_next = SP.Policy(arms, True, sides, "next")
    x_arm, z_arm = 0, 4                                                  # +x, +z
    assert p_this.arm_ok("a", x_arm) and not p_this.arm_ok("b", x_arm) and p_this.arm_ok("b", z_arm) and not p_this.arm_ok("a", z_arm)
    assert p_next.arm_ok("b", x_arm) and not p_next.arm_ok("a", x_arm) and p_next.arm_ok("a", z_arm) and not p_next.arm_ok("b", z_arm)
    assert p_this.arm_ok("c", x_arm) and p_next.arm_ok("c", z_arm)
    assert all(0 in p.allowed(t, 2) for p in (p_this, p_next) for t in sides)                  # G3-c2: the centre takes any token
    q = SP.Policy(arms, True, sides, "next", True)
    assert 0 in q.allowed("b", 2) and 0 in q.allowed("c", 2) and 0 not in q.allowed("a", 2)
    # capacity: x_side "next": 4 tokens of N+1 need the x arms (1 + 2 L >= 4 -> L = 2); 4 tokens of N need the z arms (2 L >= 4 with the centre closed)
    assert not q.capacity_ok(1, 0, 4, 0) and q.capacity_ok(2, 0, 4, 0)
    assert not q.capacity_ok(1, 3, 0, 0) and q.capacity_ok(2, 3, 0, 0) and not q.capacity_ok(2, 5, 0, 0) and q.capacity_ok(3, 5, 0, 0)
    free = SP.Policy(arms, False, sides)
    assert free.centre_ok("a") and free.capacity_ok(1, 2, 2, 1)


def test_hand_table_the_best_centre_is_a_unit_of_n_plus_1():
    # b1 (N+1) is the hub: b2 hangs on its +x arm, a1 on +z (outer in N, inner in N+1: the right direction), a2 on -z
    t = {("+x", "b2", "b1"): (5, 5), ("-x", "b2", "b1"): (5, 5), ("+z", "a1", "b1"): (4, 4), ("-z", "a2", "b1"): (4, 4),
         ("+x", "a2", "a1"): (1, 1), ("+z", "b1", "a1"): (1, 1), ("-x", "a2", "a1"): (1, 1)}
    w = SP.ArmWeights.from_table(t)
    mid = pl.budget_level("mid")
    arms = SP.arms_ok()
    ord_a = [("a1", "this"), ("a2", "this"), ("b1", "next"), ("b2", "next")]
    ord_b = [("b1", "next"), ("b2", "next"), ("a1", "this"), ("a2", "this")]
    ga = SP.grow(w, ord_a, mid, arms, stability="per_axis", z_reserved=True, centre_only=True)
    gb = SP.grow(w, ord_b, mid, arms, stability="per_axis", z_reserved=True, x_side="next", centre_only=True)
    assert ga.size == gb.size == 4 and ga.stop == gb.stop == "exhausted"
    va = {SP.score_vec(w, m, ga.L) for m in ga.members}
    vb = {SP.score_vec(w, m, gb.L) for m in gb.members}
    assert any(SP._vdom(b, a) for a in va for b in vb) and not any(SP._vdom(a, b) for a in va for b in vb)    # N+1 centre dominates
    sides = {tk: sd for tk, sd in ord_a}
    for m in gb.members:
        assert m[0] == "b1"
        L = gb.L
        xs = [c for c in m[1:1 + 2 * L] if c is not None]
        zs = [c for c in m[1 + 4 * L:] if c is not None]
        assert xs == ["b2"] and sorted(zs) == ["a1", "a2"]                  # x arms hold N+1, z arms hold N
    crosses = [SP.to_cross(m, gb.L) for m in gb.members]
    wfn = SP.table_weight_fn(t)
    r = SP.verify_class_slide(wfn, crosses, stability="per_axis", sides=sides, z_reserved=True, x_side="next", centre_only=True)
    assert r.is_stable_class and r.no_unit_on_unseatable_arm
    # the same class under the wrong reservation (x arms = N) is rejected: the seats are illegal there
    bad = SP.verify_class_slide(wfn, crosses, stability="per_axis", sides=sides, z_reserved=True, x_side="this")
    assert not bad.is_stable_class and not bad.no_unit_on_unseatable_arm
    # the independent fixed-point check agrees
    fp = SP.verify_fixed_point_slide(wfn, crosses[0], stability="per_axis", sides=sides, z_reserved=True, x_side="next", centre_only=True)
    assert fp.is_fixed_point and fp.strictly_stable


def test_toy_window_places_the_centre_in_n_plus_1(s_n1):
    spec = SP.make_spec(s_n1)
    assert spec.switches3() == SP.DEFAULTS3 == {"centre_scope": "both", "arm_cap": "budget", "stability_judgement": "strict"}
    pw = pw_of(s_n1, 0)
    p = SP.place_window(s_n1, pw, spec)
    cs = p.centre_search
    assert cs["choice"] == "next" and p.centre_sentence == "next" and set(p.member_x_side) == {"next"}
    g_this, g_next = cs["growths"]
    assert g_this["centre_sentence"] == "this" and g_next["centre_sentence"] == "next" and g_this["kept_members"] == 0 and g_next["kept_members"] == p.class_size
    assert any(a > b for a, b in zip(g_next["axis_keys"][0], g_this["axis_keys"][0])) and all(a >= b for a, b in zip(g_next["axis_keys"][0], g_this["axis_keys"][0]))
    assert_legal(p, spec)
    side = {i.token: i.side for i in p.items}
    for s in p.seats:
        if s["arm"] in ("+x", "-x"):
            assert s["side"] == "next"                                      # x arms hold sentence N+1 (the centre's sentence)
        if s["arm"] in ("+z", "-z"):
            assert s["side"] == "this"                                      # z arms hold sentence N
        if s["arm"] == "centre":
            assert s["side"] == "next" and side[s["token"]] == "next"
    assert p.size == 6 and p.stop == "exhausted"
    r = verify(s_n1, pw, p, spec)
    assert r.is_stable_class and r.members_checked == p.class_size
    # the other sentence (the one the z arms hold) is N here; both of its exclusive units are seated
    assert p.other_seat.exclusive_units > 0 and p.other_seat.exclusive_seated == p.other_seat.exclusive_units and p.other_seat.strict
    # the same window with the centre restricted to N (G3-c2): the centre is in N and the key is lower
    q = SP.place_window(s_n1, pw, SP.make_spec(s_n1, centre_scope="n"))
    assert q.centre_sentence == "this" and q.axis_keys["x"][0] < p.axis_keys["x"][0]
    assert q.centre_search["choice"] == "single" and len(q.centre_search["growths"]) == 1
    # the record's insertion order is the representative's growth's (N+1 first), the same order as its steps (review fix)
    assert [u for u, _s in p.order_log][:len(p.steps)] == [s.unit for s in p.steps]
    assert p.items[0].side == "next" and [[it.unit, it.sid] for it in p.items] == p.doc(False)["seat_order"]


def test_equal_and_incomparable_keys_keep_both_growths():
    for toy, n, want in ((TOY_EQ, 2, "both_equal"), (TOY_INC, 0, "both_incomparable")):
        sl = mkslide(toy)
        spec = SP.make_spec(sl)
        p = SP.place_window(sl, pw_of(sl, n), spec)
        assert p.centre_search["choice"] == want, toy
        assert set(p.member_x_side) == {"this", "next"}
        assert p.centre_sentence == "this"                                   # members: the growth with the centre in N first
        assert p.member_x_side[0] == "this" and p.member_x_side.index("next") > p.member_x_side.index("this")
        assert_legal(p, spec)
        assert verify(sl, pw_of(sl, n), p, spec).is_stable_class
        assert p.axis_splits >= (2 if want == "both_incomparable" else 1)


def test_the_shorter_growth_is_padded_to_the_longer_arm_length_and_stays_stable_at_its_own():
    sl = mkslide(TOY_INC)
    spec = SP.make_spec(sl)
    pw = pw_of(sl, 0)
    p = SP.place_window(sl, pw, spec)                                      # incomparable keys, both growths kept, arm lengths 3 and 2
    g = p.centre_search["growths"]
    assert p.centre_search["choice"] == "both_incomparable" and g[0]["L"] != g[1]["L"] and p.L == max(g[0]["L"], g[1]["L"])
    short = 0 if g[0]["L"] < g[1]["L"] else 1
    assert g[short]["padded_to_L"] == p.L and g[1 - short]["padded_to_L"] is None
    assert all(len(m) == 1 + 6 * p.L for m in p.members)
    assert sorted(set(p.member_L)) == sorted(g[k]["L"] for k in (0, 1))
    assert p.doc(True)["centre_search"]["member_L"] == list(p.member_L)
    for m, ml in zip(p.members, p.member_L):                              # the padding is empty: the outer p.L - ml seats of every arm
        for a in range(6):
            assert all(c is None for c in m[1 + a * p.L: 1 + a * p.L + (p.L - ml)])
    r = verify(sl, pw, p, spec)
    assert r.is_stable_class and r.members_checked == p.class_size
    # a member's strict judgement is made at its own length (the padding is not a seat of it)
    mj = p.doc(True)["judgement"]["member_judgement"]
    assert len(mj) == p.class_size
    # without the member's own length the verifier also counts the moves into the padding
    wfn = SP.counts_weight_fn(sl.counts(pw.window, "corpus"), "RUN")
    arms = [n for n in SP.ARM_NAMES if n not in p.seatless_arms]
    r2 = SP.verify_class_slide(wfn, p.crosses(), stability="per_axis", arm_names=arms, sides={i.token: i.side for i in p.items}, z_reserved=True,
                               centre_only=True, x_sides=list(p.member_x_side))
    assert r2.swaps_tested > r.swaps_tested


def test_every_member_of_every_toy_window_is_legal_and_stable_under_every_switch_combination(s_old, s_n1, s_d):
    for sl in (s_old, s_n1, s_d):
        for cscope in SP.CENTRE_SCOPES:
            for cap in SP.ARM_CAPS:
                for seat_key in SP.SEAT_KEYS:
                    for growth in ("n_then_n1", "z_reserved"):
                        spec = SP.make_spec(sl, centre_scope=cscope, arm_cap=cap, seat_key=seat_key, growth=growth)
                        for pw in SP.place_windows(sl, "one"):
                            p = SP.place_window(sl, pw, spec)
                            assert_legal(p, spec)
                            assert verify(sl, pw, p, spec).is_stable_class, (cscope, cap, seat_key, growth, pw.window.sids)
                            assert len(p.member_x_side) == len(p.members) == len(p.doc(True)["judgement"]["member_judgement"])


def test_centre_scope_both_without_the_reservation_is_the_same_growth():
    sl = mkslide(TOY_N1)
    a = SP.place_window(sl, pw_of(sl, 0), SP.make_spec(sl, growth="n_then_n1", centre_scope="both"))
    b = SP.place_window(sl, pw_of(sl, 0), SP.make_spec(sl, growth="n_then_n1", centre_scope="n"))
    assert a.members == b.members and a.steps == b.steps and a.centre_search["choice"] == "single"


# ==== part 2: arm_cap =================================================================================================
def test_arm_cap_x_stops_the_z_arms_at_the_x_length_and_records_the_unseated_units():
    t = {("+z", "o1", "c"): (3, 3), ("-z", "o2", "c"): (3, 3), ("+z", "o3", "o1"): (2, 2), ("-z", "o4", "o2"): (2, 2)}
    w = SP.ArmWeights.from_table(t)
    order = [("c", "this"), ("x1", "this"), ("o1", "next"), ("o2", "next"), ("o3", "next"), ("o4", "next")]
    mid = pl.budget_level("mid")
    bud = SP.grow(w, order, mid, SP.arms_ok(), stability="per_axis", z_reserved=True)
    cap = SP.grow(w, order, mid, SP.arms_ok(), stability="per_axis", z_reserved=True, cap_x=True)
    assert bud.L == 2 and bud.size == 6 and bud.stop == "exhausted" and bud.unseated == () and bud.L_cap is None
    # the x arms hold the centre's sentence (c, x1): L = 1; the z arms then hold two units (2 L), the other two do not fit
    assert cap.L == 1 and cap.L_cap == 1 and cap.size == 4 and cap.stop == "cap"
    assert cap.unseated == ("o3", "o4") and cap.left == ("o3", "o4") and cap.broke_on.unit == "o3" and cap.broke_on.reason == "arm_cap"
    st = {s.unit: s for s in cap.steps}
    assert st["o1"].status == st["o2"].status == "stable" and st["o3"].status == st["o4"].status == "unseated"
    assert st["o3"].reason == "arm_cap" and st["o3"].size_after == 4
    for m in cap.members:
        assert "o3" not in m and "o4" not in m and {m[5], m[6]} == {"o1", "o2"}
    # a budget stop after unseated units: `left` lists both
    tiny = pl.budget_level("low")
    assert SP.grow(w, order, tiny, SP.arms_ok(), stability="per_axis", z_reserved=True, cap_x=True).stop in ("cap", "budget")
    # the cap does nothing without the reservation and is inert when the other sentence fits
    free = SP.grow(w, order, mid, SP.arms_ok(), stability="per_axis", cap_x=True)
    assert free.stop == "exhausted" and free.unseated == ()
    short = SP.grow(w, order[:4], mid, SP.arms_ok(), stability="per_axis", z_reserved=True, cap_x=True)
    assert short.stop == "exhausted" and short.size == 4 and short.L_cap == 1


def test_arm_cap_x_in_the_record(s_d):
    spec = SP.make_spec(s_d, arm_cap="x")
    pw = pw_of(s_d, 0)
    p = SP.place_window(s_d, pw, spec)
    g_this, g_next = p.centre_search["growths"]
    assert g_this["unseated"] == 0 and g_this["stop"] == "exhausted"             # centre in N: N has 5 units (L 2), N+1's 2 units fit
    assert g_next["unseated"] == 3 and g_next["stop"] == "cap" and g_next["L"] == g_next["L_cap"] == 1   # centre in N+1: 2 units (L 1), N's 5 do not fit
    assert g_next["L"] == 1
    # the representative is the centre-in-N growth: no unseated units; force the other one to read the record fields
    q = SP.place_window(s_d, pw, SP.make_spec(s_d, arm_cap="x", centre_scope="n"))
    assert q.unseated == () and q.stop == "exhausted"
    b = SP.place_window(s_d, pw, SP.make_spec(s_d, arm_cap="budget"))
    assert b.centre_search["growths"][1]["unseated"] == 0 and b.centre_search["growths"][1]["stop"] == "exhausted"
    assert b.centre_search["growths"][1]["L"] > g_next["L"]


def test_arm_cap_x_unseated_units_are_named_in_the_record():
    sl = mkslide([("E", "星と月が光る。"), ("E", "山と川と海と空と森が見える。")])        # N has 2 units, N+1 has 5: centre in N, z arms cannot hold 5
    spec = SP.make_spec(sl, arm_cap="x", centre_scope="n")
    pw = pw_of(sl, 0)
    p = SP.place_window(sl, pw, spec)
    assert p.stop == "cap" and p.broke_on.reason == "arm_cap" and p.L == 1
    assert len(p.unseated) == 3 and all(set(u) == {"unit", "sid"} and u["sid"] == pw.window.sids[1] for u in p.unseated)
    assert [u["unit"] for u in p.unseated] == list(p.left)
    d = p.doc(False)
    assert d["unseated"] == list(p.unseated) and d["stop"] == "cap"
    assert verify(sl, pw, p, spec).is_stable_class and p.size + len(p.unseated) == len(p.items)


# ==== part 3: the strict judgement ====================================================================================
def _tradeoff_state():
    t = {("+x", "A", "C"): (1, 1), ("+x", "B", "C"): (3, 3), ("+z", "B", "C"): (2, 2), ("+z", "A", "C"): (1, 1)}
    flat = ("C", "A", None, None, None, "B", None)                       # L = 1: centre, +x A, -x, +y, -y, +z B, -z
    return t, flat


def test_a_pareto_stable_state_with_an_improving_x_move_is_unstable_axis_improvable():
    t, flat = _tradeoff_state()
    w = SP.ArmWeights.from_table(t)
    arms = SP.arms_ok()
    j = SP.judge_state(w, flat, 1, arms)
    assert j["stable_pareto"] and not j["stable_strict"] and j["pareto_improving"] == 0
    assert j["improving_moves_left"]["x"] >= 1 and j["improving_moves_left"]["z"] == 0 and j["improving_moves_left"]["y"] == 0
    # independent: geometry's swaps and the table
    r = SP.verify_fixed_point_slide(SP.table_weight_fn(t), SP.to_cross(flat, 1), stability="per_axis")
    assert r.is_fixed_point and not r.strictly_stable and dict(r.axis_improvable) == j["improving_moves_left"]
    jd = SP._judgement("strict", j, [j])
    assert jd["stable"] is False and jd["unstable"] == {"type": "UNSTABLE_AXIS_IMPROVABLE", "axes": ["x"]}
    assert jd["members_stable_strict"] == 0 and jd["first_stable_strict_member"] is None
    jp = SP._judgement("pareto", j, [j])
    assert jp["stable"] is True and jp["unstable"] is None and jp["stable_strict"] is False
    # a strictly stable state
    ok = SP.judge_state(SP.ArmWeights.from_table({("+x", "A", "C"): (3, 3)}), ("C", "A", None, None, None, None, None), 1, arms)
    assert ok["stable_strict"] and ok["improving_moves_left"] == {"x": 0, "y": 0, "z": 0}
    assert SP._judgement("strict", ok, [ok, j])["members_stable_strict"] == 1 and SP._judgement("strict", ok, [j, ok])["first_stable_strict_member"] == 1


def test_judgement_respects_the_reservation():
    # B wants the +x arm but is a unit of N+1: under the reservation it cannot go there, so the state is stable
    t = {("+x", "B", "C"): (9, 9), ("+z", "B", "C"): (1, 1)}
    flat = ("C", None, None, None, None, "B", None)
    w = SP.ArmWeights.from_table(t)
    pol = SP.Policy(SP.arms_ok(), True, {"C": "this", "B": "next"})
    assert not SP.judge_state(w, flat, 1, SP.arms_ok())["stable_strict"]
    assert SP.judge_state(w, flat, 1, SP.arms_ok(), pol)["stable_strict"]
    nxt = SP.Policy(SP.arms_ok(), True, {"C": "this", "B": "next"}, "next", True)         # centre in N+1: C (N) may not be the centre
    assert SP.judge_state(w, ("B", None, None, None, None, "C", None), 1, SP.arms_ok(), nxt)["stable_strict"]


def test_run4_windows_with_trade_off_moves_are_marked_and_the_counts_match_the_old_diagnostic():
    if not (os.path.exists(FL) and os.path.exists(RUN4)):
        pytest.skip("no fulllead data / committed run-4 records")
    rows = sp.load_jsonl(FL)
    full = SL.Slide(sp.build_space(rows), rows=rows)
    recs = [json.loads(line) for line in open(RUN4, encoding="utf-8")]
    pairs = [p for p in SP.place_windows(full, "none") if len(p.window.sids) == 2]
    idx = [i for i, r in enumerate(recs[:40]) if r["tradeoffs"]["improve_one_worsen_another"] > 0]
    assert len(idx) >= 4
    for i in idx[:4] + [0, 1]:
        for jud in ("strict", "pareto"):
            spec = SP.make_spec(full, **dict(SP.C2_EQUIV, stability_judgement=jud))
            p = SP.place_window(full, pairs[i], spec)
            old = recs[i]["tradeoffs"]
            assert p.judgement["stable_pareto"] and p.tradeoffs["pareto_improving"] == 0
            assert p.improving_moves_left == old["improved_axis"]            # Pareto-stable: only trade-off moves are left
            if old["improve_one_worsen_another"]:
                assert not p.stable_strict
                if jud == "strict":
                    assert p.unstable == {"type": "UNSTABLE_AXIS_IMPROVABLE", "axes": [a for a in SP.AXES if old["improved_axis"][a]]}
                else:
                    assert p.unstable is None
            else:
                assert p.stable_strict and p.unstable is None
            wfn = SP.counts_weight_fn(full.counts(pairs[i].window, "corpus"), "RUN")
            arms = [n for n in SP.ARM_NAMES if n not in p.seatless_arms]
            fp = SP.verify_fixed_point_slide(wfn, p.cross, stability="per_axis", arm_names=arms, sides={it.token: it.side for it in p.items}, z_reserved=True)
            assert dict(fp.axis_improvable) == p.improving_moves_left and fp.strictly_stable == p.stable_strict
            mj = p.doc(True)["judgement"]["member_judgement"]
            assert len(mj) == p.class_size and mj[0]["stable_strict"] == p.stable_strict and mj[0]["improving_moves_left"] == p.improving_moves_left
            assert p.judgement["members_stable_strict"] == sum(m["stable_strict"] for m in mj)


def test_the_judgement_rule_does_not_change_the_search(s_old):
    for pw in SP.place_windows(s_old, "none"):
        a = SP.place_window(s_old, pw, SP.make_spec(s_old, stability_judgement="strict"))
        b = SP.place_window(s_old, pw, SP.make_spec(s_old, stability_judgement="pareto"))
        assert a.members == b.members and a.steps == b.steps and a.stop == b.stop and a.judgement["improving_moves_left"] == b.judgement["improving_moves_left"]
        assert a.spec_sha != b.spec_sha


# ==== part 4: regression =============================================================================================
def test_centre_scope_n_equals_the_committed_g3c2_run4_records_of_the_first_40_pair_windows():
    if not (os.path.exists(FL) and os.path.exists(RUN4)):
        pytest.skip("no fulllead data / committed run-4 records")
    rows = sp.load_jsonl(FL)
    full = SL.Slide(sp.build_space(rows), rows=rows)
    spec = SP.make_spec(full, **SP.C2_EQUIV)
    assert spec.switches() == SP.DEFAULTS and not spec.is_legacy
    recs = [json.loads(line) for line in open(RUN4, encoding="utf-8")]
    pairs = [p for p in SP.place_windows(full, "none") if len(p.window.sids) == 2][:40]
    timing_and_runner = {"wall_s", "verify", "z_arm_units", "z_arm_fillers", "z_arm_no_evidence"}
    assert len(pairs) == 40
    for pw, rec in zip(pairs, recs):
        d = SP.place_window(full, pw, spec).doc(members=False)
        d = json.loads(json.dumps(d, sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str))
        for f in SP.NEW_RECORD_FIELDS_C3:
            d.pop(f)
        assert d == {k: v for k, v in rec.items() if k not in timing_and_runner}, pw.window.sids
    assert spec.sha256() == recs[0]["spec_sha256"]


def test_the_g3c3_switches_are_listed_in_the_spec_only_when_they_differ_from_g3c2(s_old):
    c2 = SP.make_spec(s_old, **SP.C2_EQUIV)
    leg = SP.make_spec(s_old, **SP.LEGACY)
    assert "switches3" not in c2.doc() and "switches3" not in leg.doc() and leg.is_legacy and "switches" not in leg.doc()
    assert SP.LEGACY == dict(SP.LEGACY4, **SP.C2_EQUIV) and set(SP.LEGACY4) == set(SP.DEFAULTS)
    shas = {c2.sha256(), leg.sha256()}
    for k, v in (("centre_scope", "both"), ("arm_cap", "x"), ("stability_judgement", "strict")):
        sp3 = SP.make_spec(s_old, **dict(SP.C2_EQUIV, **{k: v}))
        assert sp3.doc()["switches3"][k] == v and set(sp3.doc()["rules3"]) == set(SP.C2_EQUIV) and not sp3.is_legacy
        shas.add(sp3.sha256())
    assert len(shas) == 5
    dflt = SP.make_spec(s_old)
    assert dflt.switches() == SP.DEFAULTS and dflt.switches3() == SP.DEFAULTS3 and dflt.doc()["switches3"] == SP.DEFAULTS3
    for bad in ({"centre_scope": "m"}, {"arm_cap": "z"}, {"stability_judgement": "lex"}):
        with pytest.raises(ValueError):
            SP.make_spec(s_old, **bad)
    p = SP.place_window(s_old, pw_of(s_old, 0), dflt)
    assert dict(p.switches3) == SP.DEFAULTS3 and dict(p.switches) == SP.DEFAULTS and p.spec_sha == dflt.sha256()


# ==== part 5: seeds, no float =========================================================================================
def test_bytes_are_identical_under_three_hash_seeds_for_the_new_switches():
    prog = (
        "import hashlib,itertools\n"
        "from verantyx.line3 import slide as SL, slide_place as SP, space as sp\n"
        "T=[('A','犬が走る。'),('A','猫と魚と鳥が走る。'),('B','猫と魚と鳥が泳ぐ。'),('B','犬が鳥を追う。'),('C','星が光る。'),('C','星と月と雲と空が光る。'),('D','京都は古い都である。')]\n"
        "seen={};rows=[]\n"
        "for t,s in T:\n i=seen.get(t,0);seen[t]=i+1;rows.append({'title':t,'sent':s,'source':'%s#%d'%(t,i)})\n"
        "S=sp.build_space(rows);sl=SL.Slide(S,rows=rows);h=hashlib.sha256()\n"
        "for cs,ac,jd,gr,sk in itertools.product(SP.CENTRE_SCOPES,SP.ARM_CAPS,SP.JUDGEMENTS,('n_then_n1','z_reserved'),SP.SEAT_KEYS):\n"
        " spec=SP.make_spec(sl,centre_scope=cs,arm_cap=ac,stability_judgement=jd,growth=gr,seat_key=sk);h.update(spec.to_bytes())\n"
        " for pw in SP.place_windows(sl,'one'):h.update(SP.place_window(sl,pw,spec).to_bytes())\n"
        "print(h.hexdigest())")
    outs = set()
    for seed in ("0", "1", "12345"):
        out = subprocess.run([PY, "-c", prog], cwd=ROOT, env=dict(os.environ, PYTHONPATH=ROOT, PYTHONHASHSEED=seed), capture_output=True, text=True)
        assert out.returncode == 0, out.stderr
        outs.add(out.stdout.strip())
    assert len(outs) == 1 and len(next(iter(outs))) == 64


def test_no_float_in_the_g3c3_records(s_n1, s_d):
    def hook(s):
        raise AssertionError("a float in the record: %s" % s)
    for sl in (s_n1, s_d):
        for cs in SP.CENTRE_SCOPES:
            for ac in SP.ARM_CAPS:
                spec = SP.make_spec(sl, centre_scope=cs, arm_cap=ac)
                json.loads(spec.to_bytes().decode("utf-8"), parse_float=hook)
                for pw in SP.place_windows(sl, "one"):
                    b = SP.place_window(sl, pw, spec).to_bytes().decode("utf-8")
                    json.loads(b, parse_float=hook)
                    assert "UNSTABLE" not in b or '"type"' in b


def test_the_verifier_does_not_use_the_search_names():
    import ast
    src = open(SP.__file__, encoding="utf-8").read()
    tree = ast.parse(src)
    forbidden = {"Policy", "_scan", "_scan_pa", "_settle", "_settle_pa", "_insert_one", "_insert_one_pa", "ArmWeights", "judge_state", "score_vec",
                 "_swap_dvec", "_edge_vec", "_lay", "_earm", "grow", "_resettle"}
    for fn in tree.body:
        if isinstance(fn, ast.FunctionDef) and fn.name in ("verify_fixed_point_slide", "verify_class_slide", "_legal_seat", "_move_ok", "cross_key"):
            used = {n.id for n in ast.walk(fn) if isinstance(n, ast.Name)} | {n.attr for n in ast.walk(fn) if isinstance(n, ast.Attribute)}
            assert not (used & forbidden), (fn.name, used & forbidden)
