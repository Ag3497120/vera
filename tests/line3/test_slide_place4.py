"""G3-c4 tests (L-660..): the spec switch z_deep "slide" | "order" (owner, 「G3-c3 の実装後の決定」: measure both evidence rules for the deeper
z-arm edges).  slide.SlideSpec carries it (the sha changes), slide_place keys the edges by it, slide_ratios reads the same per-edge
evidence.

Part 1 (the spec): the default spec / counts keep their bytes and sha; "order" changes the spec sha and the place spec sha; bad values raise.
Part 2 (the evidence): `WindowCounts.deep_z` reads the x table; the arm codes of the layout (the innermost z edge keeps the arm code, a
deeper one gets DEEP_Z + arm); ArmWeights with a deep rule; on a hand window the deeper z edges of the other sentence get order evidence
under "order" and none under "slide", the innermost z edge and every x / y weight are the same under both.
Part 3 (the placement): a toy window under "order" records the rule of each z-arm edge, the evidence is the x pair's count, the independent
verifier (counts_weight_fn with the rule) accepts every member and its strict counts equal the record's; a verifier without the rule
disagrees.
Part 4 (the ratios): the edge flow, the binding and the section walk of a z arm read the same per-edge evidence (by hand, an independent
route over geometry.neighbours); the walk steps over a deeper edge with its evidence and the step says so; check_trace holds.
Part 5 (regression): z_deep "slide" reproduces the committed G3-c3 run-A records of the first 40 pair windows (every field, spec shas
included) and the G3-d toy ratios (a digest computed with the committed G3-c3 code).
Part 6: PYTHONHASHSEED 0 / 1 / 12345 give identical bytes; no float."""
import dataclasses
import hashlib
import itertools
import json
import os
import subprocess
import sys
from fractions import Fraction as Fr

import pytest

from verantyx.line3 import energy as en
from verantyx.line3 import geometry as geo
from verantyx.line3 import slide as SL
from verantyx.line3 import slide_place as SP
from verantyx.line3 import slide_ratios as SR
from verantyx.line3 import space as sp

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PY = sys.executable
FL = os.path.join(ROOT, "experiments/line3/bank2/data/fulllead_sents.jsonl")
RUNA = os.path.join(ROOT, "experiments/line3/g3/place3/fulllead_RUN_mid_none_per_axis_unit_sid_allow_z_reserved_centre-both_cap-budget_strict_pairs292.jsonl")

TOY = [("A", "犬が走る。"), ("A", "猫と魚と鳥が走る。"), ("B", "猫と魚と鳥が泳ぐ。"), ("B", "犬が鳥を追う。")]    # window (0, 1): N+1 holds 猫 魚 鳥 in an order
TOY_N1 = [("A", "犬が走る。"), ("A", "猫と魚と鳥が走る。"), ("B", "猫と魚と鳥が泳ぐ。"), ("B", "犬が鳥を追う。")]
TOY_EQ = [("A", "山が高い。"), ("A", "川と海と空と森が見える。"), ("B", "川と海が広い。"), ("B", "空と森が青い。")]
TOY_D = [("D", "山と川と海と空と森が見える。"), ("D", "星と月が光る。")]
TOY_OLD = [("A", "東京は日本の首都である。"), ("A", "東京は日本の都市である。"), ("B", "犬が猫を追う。"), ("B", "猫が魚を食べる。"), ("C", "京都は古い都である。")]
# the digests of the G3-d toy ratios and of its slide spec, computed with the committed G3-c3 code (git HEAD e423e572)
RATIOS_DIGEST = "649f264b72926cb6448c98b3cf25e69de3687f0f3e238d9fe2a86868c3e740a7"
RATIOS_SPEC_SHA = "613eff7a7f720840bd1c1b35c3a51881001f68b3d54cc037259ab47e0faad0e3"


def rows_of(toy):
    seen = {}
    rows = []
    for t, s in toy:
        i = seen.get(t, 0)
        seen[t] = i + 1
        rows.append({"title": t, "sent": s, "source": "%s#%d" % (t, i)})
    return rows


def mk(toy, z_deep="slide", **kw):
    rows = rows_of(toy)
    space = sp.build_space(rows)
    return SL.Slide(space, SL.default_spec(space, z_deep=z_deep, **kw), rows=rows)


@pytest.fixture(scope="module")
def s_slide():
    return mk(TOY, "slide")


@pytest.fixture(scope="module")
def s_order():
    return mk(TOY, "order")


def pw_of(slide, n):
    return next(p for p in SP.place_windows(slide, "none") if p.window.n == n)


# ==== part 1: the spec =================================================================================================
def test_the_default_spec_keeps_its_bytes_and_order_changes_the_sha(s_slide, s_order):
    rows = rows_of(TOY)
    space = sp.build_space(rows)
    plain = SL.default_spec(space, z_deep="slide")          # G3-i (L-770): the spec's own default is "order" now; "slide" is the G3-a..G3-h default spec
    assert plain.to_bytes() == s_slide.spec.to_bytes()
    assert SL.DEFAULT_Z_DEEP == "order" and SL.default_spec(space).to_bytes() == s_order.spec.to_bytes() != plain.to_bytes()
    assert plain.z_deep == "slide" and "deep" not in dict(plain.axis("z").params) and "z_deep" not in plain.doc()
    assert b"deep" not in plain.to_bytes()
    assert s_order.spec.z_deep == "order" and dict(s_order.spec.axis("z").params)["deep"] == "order"
    assert s_order.spec.sha256() != plain.sha256() and "z_deep=order" in s_order.spec.axis("z").text
    assert SL.default_spec(space, z_tiers="same", z_deep="order").z_deep == "order"
    with pytest.raises(ValueError):
        SL.default_spec(space, z_deep="both")
    with pytest.raises(ValueError):
        SL.SlideSpec(plain.corpus_sha, plain.window, SL.default_axes()[:2] + (SL.AxisDef("z", "z", (("occurrence", "first"), ("tiers", "all"), ("deep", "x"))),),
                     plain.foundation)
    # the place spec follows the slide spec's sha
    p0, p1 = SP.make_spec(s_slide), SP.make_spec(s_order)
    assert p0.slide_spec_sha == s_slide.spec.sha256() != p1.slide_spec_sha == s_order.spec.sha256() and p0.sha256() != p1.sha256()
    assert p0.doc() == dict(p1.doc(), slide_spec_sha256=p0.slide_spec_sha)
    # a placement made for the other slide spec is refused
    with pytest.raises(ValueError):
        SP.place_window(s_order, pw_of(s_order, 0), p0)


def test_the_counts_keep_their_bytes_under_the_default_and_say_z_deep_under_order(s_slide, s_order):
    c0 = s_slide.counts(pw_of(s_slide, 0).window, "corpus")
    c1 = s_order.counts(pw_of(s_order, 0).window, "corpus")
    assert c0.z_deep == "slide" and c1.z_deep == "order"
    d0, d1 = c0.doc(), c1.doc()
    assert "z_deep" not in d0 and d1.pop("z_deep") == "order" and d0 == d1             # the counts themselves do not change


def test_deep_z_reads_the_x_table_of_the_pair(s_order):
    for scope in SL.SCOPES:
        c = s_order.counts(pw_of(s_order, 0).window, scope)
        for o, i in (("猫", "魚"), ("魚", "鳥"), ("鳥", "猫"), ("犬", "走")):
            b, a = c.x.get(("RUN", o, i), ((), ()))
            assert c.deep_z("RUN", "+z", o, i) == (len(b) + len(a), len(b), tuple(b) + tuple(a))          # forward: o before i
            assert c.deep_z("RUN", "-z", o, i) == (len(b) + len(a), len(a), tuple(b) + tuple(a))           # backward: o after i
        with pytest.raises(ValueError):
            c.deep_z("RUN", "+x", "猫", "魚")
    c = s_order.counts(pw_of(s_order, 0).window, "corpus")
    assert c.deep_z("RUN", "+z", "猫", "魚")[:2] == (2, 2) and c.deep_z("RUN", "-z", "猫", "魚")[:2] == (2, 0)      # 猫 before 魚 in s1 and s2
    assert c.deep_z("RUN", "+z", "鳥", "猫")[:2] == (2, 0) and c.deep_z("RUN", "-z", "鳥", "猫")[:2] == (2, 2)
    assert c.n_z("RUN", "猫", "RUN", "魚") == 0                                           # both are in N+1: no slide edge between them


# ==== part 2: arm codes and weights ====================================================================================
def test_arm_codes_of_the_layout():
    for L in (1, 2, 3, 4):
        plain, deep = SP._earm(L), SP._earm(L, True)
        lay = SP._lay(L)
        assert plain == tuple((o - 1) // L for o, _ in lay.edges)                         # unchanged
        for ei, (o, i) in enumerate(lay.edges):
            a = (o - 1) // L
            if SP.ARM_NAMES[a][1] == "z" and i != 0:
                assert deep[ei] == SP.DEEP_Z + a and deep[ei] % SP.DEEP_Z == a and plain[ei] == a
            else:
                assert deep[ei] == plain[ei] < SP.DEEP_Z
        assert sum(1 for c in deep if c >= SP.DEEP_Z) == 2 * (L - 1)                     # two z arms, L - 1 deeper edges each


def test_arm_weights_with_a_deep_rule_are_looked_up_by_the_arm_code():
    t = {("+z", "a", "b"): (3, 3), ("-z", "a", "b"): (5, 5), ("+x", "a", "b"): (2, 1)}
    d = {("+z", "a", "b"): (7, 6), ("-z", "a", "b"): (7, 1)}
    w0, w1 = SP.ArmWeights.from_table(t), SP.ArmWeights.from_table(t, d)
    assert not w0.deep and w1.deep and w0.earm(3) == SP._earm(3) and w1.earm(3) == SP._earm(3, True)
    assert w1(4, "a", "b") == (3, 3) and w1(5, "a", "b") == (5, 5) and w1(0, "a", "b") == (2, 1)       # the innermost z edge and x: the table
    assert w1(SP.DEEP_Z + 4, "a", "b") == (7, 6) and w1(SP.DEEP_Z + 5, "a", "b") == (7, 1)             # a deeper z edge: the deep table
    assert w1(SP.DEEP_Z + 4, "b", "a") == SP.ZERO2 and w1(SP.DEEP_Z + 4, None, "a") == SP.ZERO2
    # a flat of arm length 2: the +z arm holds a (outer) and b (inner); the edge a-b is the deeper one, b-centre the innermost
    L = 2
    flat = ["c"] + [None] * 12
    flat[1 + 4 * L + 0], flat[1 + 4 * L + 1] = "a", "b"
    assert SP.score_vec(w0, tuple(flat), L) == (0, 0, 0, 0, 3, 3) and SP.score_vec(w1, tuple(flat), L) == (0, 0, 0, 0, 7, 6)
    t2 = dict(t)
    t2[("+z", "b", "c")] = (2, 2)
    assert SP.score_vec(SP.ArmWeights.from_table(t2), tuple(flat), L) == (0, 0, 0, 0, 5, 5)
    assert SP.score_vec(SP.ArmWeights.from_table(t2, d), tuple(flat), L) == (0, 0, 0, 0, 9, 8)           # 7 + 2, 6 + 2
    assert SP.axis_key_flat(SP.ArmWeights.from_table(t2, d), tuple(flat), L) == (("x", 0, 0), ("y", 0, 0), ("z", 9, 8))


def test_weights_from_counts_differ_only_on_the_deeper_z_edges(s_slide, s_order):
    c0 = s_slide.counts(pw_of(s_slide, 0).window, "corpus")
    c1 = s_order.counts(pw_of(s_order, 0).window, "corpus")
    w0, w1 = SP.ArmWeights.from_counts(c0, "RUN"), SP.ArmWeights.from_counts(c1, "RUN")
    units = sorted({u for sid in (0, 1) for u in s_slide.space.tiers["RUN"].sentence_units[sid]})
    differ = 0
    for o, i in itertools.permutations(units, 2):
        for arm in range(6):
            assert w0(arm, o, i) == w1(arm, o, i)                                           # the innermost z edge, x, y: the same
        for arm in (4, 5):
            n, om, _src = c1.deep_z("RUN", SP.ARM_NAMES[arm], o, i)
            assert w1(SP.DEEP_Z + arm, o, i) == (n, om)                                      # the x pair, forward / backward
            differ += w1(SP.DEEP_Z + arm, o, i) != w0(arm, o, i)
    assert differ > 0
    # the units of N+1 that have no unit of N in common: the slide count of a pair inside N+1 is 0, the order count is not
    assert w0(4, "猫", "魚") == (0, 0) and w1(SP.DEEP_Z + 4, "猫", "魚") == (2, 2) and w1(SP.DEEP_Z + 5, "猫", "魚") == (2, 0)
    assert w1(SP.DEEP_Z + 4, "魚", "猫") == (2, 0) and w1(SP.DEEP_Z + 5, "鳥", "猫") == (2, 2)


# ==== part 3: the placement =============================================================================================
def z_edges(p):
    """The seats of the representative on a z arm that have an edge to the seat towards the centre: (arm, depth, row)."""
    out = []
    for r in p.seats:
        if r["arm"] in ("+z", "-z") and r["sources"]["edge"] is not None:
            out.append((r["arm"], r["depth"], r))
    return out


@pytest.mark.parametrize("centre_scope", ["n", "both"])
def test_a_hand_window_gets_order_evidence_on_its_deeper_z_edges_under_order_and_none_under_slide(s_slide, s_order, centre_scope):
    pw0, pw1 = pw_of(s_slide, 0), pw_of(s_order, 0)
    p0 = SP.place_window(s_slide, pw0, SP.make_spec(s_slide, centre_scope=centre_scope))
    p1 = SP.place_window(s_order, pw1, SP.make_spec(s_order, centre_scope=centre_scope))
    c0, c1 = s_slide.counts(pw0.window, "corpus"), s_order.counts(pw1.window, "corpus")
    assert p0.z_deep == "slide" and p1.z_deep == "order" and "z_deep" not in p0.doc() and p1.doc()["z_deep"] == "order"
    assert p0.size == p1.size == 6 and p0.stop == p1.stop == "exhausted"
    deeper0 = [(a, d, r) for a, d, r in z_edges(p0) if d >= 2]
    deeper1 = [(a, d, r) for a, d, r in z_edges(p1) if d >= 2]
    inner1 = [(a, d, r) for a, d, r in z_edges(p1) if d == 1]
    assert deeper0 and deeper1 and inner1
    side = {it.unit: it.side for it in p1.items if "\x00" not in it.token}
    for a, d, r in deeper0:                                  # slide: every z-arm edge is a slide edge; no `rule`; a pair inside one sentence has no n_z
        e = r["sources"]["edge"]
        assert "rule" not in e and e["n"] == c0.n_z("RUN", *((r["unit"], "RUN", e["with"]["unit"]) if a == "+z" else (e["with"]["unit"], "RUN", r["unit"])))
        if side.get(r["unit"]) == "next" and side.get(e["with"]["unit"]) == "next":
            assert e["n"] == 0
    for a, d, r in deeper1:                                  # order: the x pair's count of the other sentence, rule "order"
        e = r["sources"]["edge"]
        n, om, src = c1.deep_z("RUN", a, r["unit"], e["with"]["unit"])
        assert e["rule"] == "order" and (e["n"], e["omega"], e["sources"]) == (n, om, [list(t) for t in src]) and e["axis"] == "z" and e["arm"] == a
        if side.get(r["unit"]) == "next" and side.get(e["with"]["unit"]) == "next":
            assert e["n"] >= 1                               # two units of the same sentence: at least that sentence holds both
    for a, d, r in inner1:                                   # the innermost z edge stays the slide edge, and says so
        e = r["sources"]["edge"]
        o, i = (r["unit"], e["with"]["unit"]) if a == "+z" else (e["with"]["unit"], r["unit"])
        assert e["rule"] == "slide" and e["n"] == c1.n_z("RUN", o, "RUN", i) == e["omega"]
    assert all("rule" not in r["sources"]["edge"] for r in p1.seats if r["arm"][1:] != "z" and r["sources"]["edge"] is not None)


def verify_all(slide, pw, p, spec, wfn=None):
    counts = slide.counts(pw.window, spec.scope)
    wfn = wfn or SP.counts_weight_fn(counts, spec.tier)
    arms = [n for n in SP.ARM_NAMES if n not in p.seatless_arms]
    zres = spec.growth == "z_reserved"
    rep = SP.verify_class_slide(wfn, p.crosses(), stability=spec.stability, arm_names=arms, sides={i.token: i.side for i in p.items}, z_reserved=zres,
                                centre_only=zres and spec.centre_scope == "both", x_sides=list(p.member_x_side), own_Ls=list(p.member_L))
    frep = SP.verify_fixed_point_slide(wfn, p.cross, stability=spec.stability, arm_names=arms, sides={i.token: i.side for i in p.items}, z_reserved=zres,
                                       x_side=p.member_x_side[0], centre_only=zres and spec.centre_scope == "both", own_L=p.member_L[0])
    return rep, frep


@pytest.mark.parametrize("toy", [TOY, TOY_EQ, TOY_D, TOY_OLD])
@pytest.mark.parametrize("growth,centre_scope", [("z_reserved", "both"), ("z_reserved", "n"), ("n_then_n1", "n")])
def test_the_independent_verifier_accepts_every_member_under_order_and_agrees_with_the_record(toy, growth, centre_scope):
    sl = mk(toy, "order")
    spec = SP.make_spec(sl, growth=growth, centre_scope=centre_scope)
    n_deep = 0
    for pw in SP.place_windows(sl, "one"):
        p = SP.place_window(sl, pw, spec)
        rep, frep = verify_all(sl, pw, p, spec)
        assert rep.is_stable_class and rep.members_checked == p.class_size, (pw.window.sids, rep)
        assert dict(frep.axis_improvable) == p.improving_moves_left and frep.strictly_stable == p.stable_strict
        wfn = SP.counts_weight_fn(sl.counts(pw.window, spec.scope), spec.tier)
        assert wfn.z_deep
        # the record's per-axis key of the representative = the verifier's key of its cross (read through the counts' accessors)
        tot, per = SP.cross_key(wfn, p.cross)
        assert {a: list(per[a]) for a in SL.AXES} == p.axis_keys and tuple(tot) == p.key
        n_deep += sum(1 for a, d, r in z_edges(p) if d >= 2)
    assert n_deep >= 0 if toy is not TOY else n_deep > 0


def test_a_verifier_without_the_rule_reads_another_key(s_order):
    spec = SP.make_spec(s_order, centre_scope="n")
    pw = pw_of(s_order, 0)
    p = SP.place_window(s_order, pw, spec)
    counts = s_order.counts(pw.window, "corpus")
    good = SP.counts_weight_fn(counts, "RUN")
    plain = SP.counts_weight_fn(dataclasses.replace(counts, z_deep="slide"), "RUN")           # the same counts read as G3-c3 reads them
    assert good.z_deep and not plain.z_deep
    assert SP.cross_key(good, p.cross)[1]["z"] == tuple(p.axis_keys["z"]) != SP.cross_key(plain, p.cross)[1]["z"]


def test_hand_table_with_a_deep_rule_changes_the_best_arrangement():
    """Seven tokens: N has a1, a2; N+1 has b1, b2, b3 (centre a1).  Slide evidence only joins a-b pairs; the deep table orders b1, b2, b3 on a
    z arm (b2 -> b1 forward, b3 -> b2 forward): with it the z arm holding the N+1 units follows their order, without it nothing orders them."""
    from verantyx.line3 import placement as pl
    t = {("+z", "a1", "b1"): (3, 3), ("-z", "a2", "b1"): (3, 3), ("+x", "a2", "a1"): (2, 2), ("-x", "a2", "a1"): (2, 0)}
    deep = {("+z", "b3", "b2"): (4, 4), ("+z", "b2", "b1"): (4, 4), ("-z", "b3", "b2"): (4, 0), ("-z", "b2", "b1"): (4, 0)}
    order = [("a1", "this"), ("a2", "this"), ("b1", "next"), ("b2", "next"), ("b3", "next")]
    mid = pl.budget_level("mid")
    arms = SP.arms_ok()
    g0 = SP.grow(SP.ArmWeights.from_table(t), order, mid, arms, stability="per_axis", z_reserved=True)
    g1 = SP.grow(SP.ArmWeights.from_table(t, deep), order, mid, arms, stability="per_axis", z_reserved=True)
    w1 = SP.ArmWeights.from_table(t, deep)
    assert g0.size == g1.size == 5 and g1.stop == "exhausted"
    k0 = max(SP.score_vec(SP.ArmWeights.from_table(t, deep), m, g0.L) for m in g0.members)          # the slide-only placement, read with the deep rule
    k1 = max(SP.score_vec(w1, m, g1.L) for m in g1.members)
    assert k1 >= k0 and k1[5] > 0
    # every member of the order class is a verifier-stable arrangement under the same table
    sides = {tk: sd for tk, sd in order}
    wfn = SP.table_weight_fn(t, deep)
    r = SP.verify_class_slide(wfn, [SP.to_cross(m, g1.L) for m in g1.members], stability="per_axis", sides=sides, z_reserved=True)
    assert r.is_stable_class and r.members_checked == len(g1.members)


# ==== part 4: the ratios ================================================================================================
def ref_z(wc, ev, tier, q, w):
    """F_z, B_z (weighted) by an independent route: from each seat over geometry.neighbours; the evidence of an edge is the slide count when
    the inner seat is the centre, the pair's x count (deep rule) otherwise."""
    by = wc.by_seat()
    F = {u: Fr(0) for u in wc.units()}
    B = {u: Fr(0) for u in wc.units()}
    steps = []
    for s, rec in by.items():
        for nb in geo.neighbours(s, wc.L):
            if nb not in by or by[nb].unit == rec.unit:
                continue
            o = by[nb]
            outer, inner = (s, nb) if s != geo.CENTER and (nb == geo.CENTER or nb.k == s.k + 1) else (nb, s)
            arm = outer.arm
            if arm[1] != "z":
                continue
            fn = getattr(ev, "deep", None) if inner != geo.CENTER else None
            n, _ = (fn or ev)(arm, by[outer].unit, by[inner].unit)
            steps.append((arm, inner == geo.CENTER, n))
            if n <= 0:
                continue
            nu, nv = len(tier.postings[o.unit]), len(tier.postings[rec.unit])
            F[rec.unit] += w[arm] * en.energy(tier, o.unit, q) * Fr(n, nu)
            B[rec.unit] += w[arm] * Fr(n, nv)
    return F, B


def test_ratios_read_the_same_per_edge_evidence_as_the_placement(s_slide, s_order):
    spec = SP.make_spec(s_order, centre_scope="n")
    pw = pw_of(s_order, 0)
    p = SP.place_window(s_order, pw, spec)
    wc = SR.window_cross(p.doc())
    tier = s_order.space.tiers["RUN"]
    fnd = s_order.spec.foundation
    c_o, c_s = s_order.counts(pw.window, "corpus"), s_slide.counts(pw.window, "corpus")
    ev_o, ev_s = SR.counts_evidence(c_o, "RUN"), SR.counts_evidence(c_s, "RUN")
    assert hasattr(ev_o, "deep") and not hasattr(ev_s, "deep")
    q = ("魚", "鳥")
    w = SR.foundation_weights(fnd)
    r_o = SR.read_axes(wc, ev_o, tier, q, fnd)
    r_s = SR.read_axes(wc, ev_s, tier, q, fnd)                       # the same cross read with the slide rule everywhere
    qe = tuple(sorted(set(SR.cy.make_context(q).energy_units)))
    F, B = ref_z(wc, ev_o, tier, qe, w)
    assert dict(r_o.axis("z").edge_flow) == F and dict(r_o.axis("z").binding) == B
    Fs, Bs = ref_z(wc, ev_s, tier, qe, w)
    assert dict(r_s.axis("z").edge_flow) == Fs and dict(r_s.axis("z").binding) == Bs
    assert dict(r_o.axis("z").binding) != dict(r_s.axis("z").binding)                 # the rule changes the z axis ...
    for a in ("x", "y"):                                              # ... and only the z axis
        assert r_o.axis(a).doc() == r_s.axis(a).doc()
    assert r_o.axis("z").evidenced_edges > r_s.axis("z").evidenced_edges
    # every z-arm edge deeper than the innermost carries rule "order", and only in the order reading
    centre_key = wc.by_seat()[geo.CENTER].key
    for sec in r_o.axis("z").sections:
        for wk in sec.walks:
            for st in wk.steps:
                assert (st.rule == "order") == (st.to != centre_key)               # a step that ends at the centre is the innermost edge
    for sec in r_s.axis("z").sections:
        assert all(st.rule == "slide" for wk in sec.walks for st in wk.steps)
    assert all("rule" not in t.doc() for a in r_s.answers for t in a.edges)
    SR.check_trace(r_o)
    SR.check_trace(r_s)
    assert SL.canonical(r_o.doc()) != SL.canonical(r_s.doc()) and len(r_o.sha256()) == 64


def hand_cross():
    """centre 魚 (sid 1); +z arm of length 2: 猫 (outer, pos 0) then 鳥 (pos 1, next to the centre); -x: 走 (sid 1)."""
    def S(u, sid, arm, pos=0):
        return SR.SeatRec(u, sid, arm, pos)
    seats = [S("魚", 1, "center"), S("走", 1, "-x", 1), S("猫", 1, "+z", 0), S("鳥", 1, "+z", 1)]
    order = {s: i for i, s in enumerate(geo.seats(2))}
    return SR.WindowCross(2, tuple(sorted(seats, key=lambda s: order[s.seat])), "RUN", (0, 1))


def test_the_section_walk_of_a_z_arm_steps_over_the_deeper_edge_with_its_evidence(s_order):
    tier = s_order.space.tiers["RUN"]
    fnd = s_order.spec.foundation
    wc = hand_cross()
    # +z walk: 猫 -> 鳥 (deeper edge) -> 魚 (innermost).  Evidence by hand tables: slide n(+z, 鳥, 魚) = 1 ; deep n(+z, 猫, 鳥) = 2
    t = {("+z", "鳥", "魚"): 1, ("-x", "走", "魚"): 1}
    q = ("魚",)
    ev0 = SR.table_evidence(t)                                         # no deep rule: the deeper edge reads the table -> 0
    ev1 = SR.table_evidence(t, {("+z", "猫", "鳥"): 2})
    r0 = SR.read_axes(wc, ev0, tier, q, fnd)
    r1 = SR.read_axes(wc, ev1, tier, q, fnd)
    walk0 = next(w for s in r0.axis("z").sections for w in s.walks if w.arm == "+z")
    walk1 = next(w for s in r1.axis("z").sections for w in s.walks if w.arm == "+z")
    assert walk0.stop == "unproven" and walk0.path == (("猫", 1),) and walk0.steps == ()
    assert walk1.stop in ("centre", "drop") and walk1.steps[0].rule == "order" and walk1.steps[0].n == 2 and walk1.steps[0].frm == ("猫", 1)
    assert walk1.steps[0].to == ("鳥", 1) and walk1.steps[0].sources == (("table_deep", "+z", "猫", "鳥", 0), ("table_deep", "+z", "猫", "鳥", 1))
    if walk1.stop == "centre":
        assert walk1.steps[1].rule == "slide" and walk1.steps[1].n == 1 and walk1.steps[1].to == ("魚", 1)
        assert "rule" not in walk1.steps[1].doc() and walk1.steps[0].doc()["rule"] == "order"
    # flow and binding: the deeper edge (猫 outer, 鳥 inner, n 2, w(+z) = 21/377) enters both sums, in both directions
    z0, z1 = r0.axis("z"), r1.axis("z")
    wz = Fr(21, 377)
    n_ = lambda u: len(tier.postings[u])
    assert z1.binding["猫"] - z0.binding["猫"] == wz * Fr(2, n_("猫")) and z1.binding["鳥"] - z0.binding["鳥"] == wz * Fr(2, n_("鳥"))
    assert z1.seated_edges == z0.seated_edges == 2 and z0.evidenced_edges == 1 and z1.evidenced_edges == 2
    assert z1.status != SR.NO_EDGES


def test_two_if_single_edge_counts_the_deeper_edge_as_an_evidenced_edge(s_order):
    tier = s_order.space.tiers["RUN"]
    fnd = s_order.spec.foundation
    wc = hand_cross()
    t = {("+z", "鳥", "魚"): 1}
    q = ("魚",)
    a = SR.read_axes(wc, SR.table_evidence(t), tier, q, fnd, agreement="two_if_single_edge").axis("z")
    b = SR.read_axes(wc, SR.table_evidence(t, {("+z", "猫", "鳥"): 2}), tier, q, fnd, agreement="two_if_single_edge").axis("z")
    assert a.evidenced_edges == 1 and not a.section_applicable and b.evidenced_edges == 2 and b.section_applicable


def test_a_plain_three_argument_evidence_keeps_working_and_reads_every_z_edge_the_old_way(s_order):
    tier = s_order.space.tiers["RUN"]
    fnd = s_order.spec.foundation
    wc = hand_cross()
    plain = lambda arm, o, i: (1, (("p",),)) if (arm, o, i) == ("+z", "猫", "鳥") else (0, ())
    r = SR.read_axes(wc, plain, tier, ("魚",), fnd)
    assert r.axis("z").evidenced_edges == 1 and all(st.rule == "slide" for s in r.axis("z").sections for w in s.walks for st in w.steps)


# ==== part 5: regression ================================================================================================
def test_z_deep_slide_equals_the_committed_g3c3_run_a_records_of_the_first_40_pair_windows():
    if not (os.path.exists(FL) and os.path.exists(RUNA)):
        pytest.skip("no fulllead data / committed run-A records")
    rows = sp.load_jsonl(FL)
    space = sp.build_space(rows)
    full = SL.Slide(space, SL.default_spec(space, z_deep="slide"), rows=rows)
    spec = SP.make_spec(full, seat_empty_axis="allow")      # G3-i (L-771): the run was made under allow (the default is deny now)
    assert spec.switches3() == SP.DEFAULTS3 and spec.switches() == SP.DEFAULTS_G3H
    recs = [json.loads(line) for line in open(RUNA, encoding="utf-8")]
    runner = {"wall_s", "verify", "z_seat_stats", "real_edges", "real_edges_with_count", "members_by_centre_sentence"}
    pairs = [p for p in SP.place_windows(full, "none") if len(p.window.sids) == 2][:40]
    assert len(pairs) == 40
    for pw, rec in zip(pairs, recs):
        d = SP.place_window(full, pw, spec).doc(members=False)
        d = json.loads(json.dumps(d, sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str))
        assert d == {k: v for k, v in rec.items() if k not in runner}, pw.window.sids
    assert spec.sha256() == recs[0]["spec_sha256"] and full.spec.sha256() == recs[0]["slide_spec_sha256"]
    assert SL.default_spec(space, z_deep="slide").to_bytes() == full.spec.to_bytes()


def ratios_digest():
    T = [('A', '東京は日本の首都である。'), ('A', '東京は日本の都市である。'), ('B', '犬が猫を追う。'), ('B', '猫が魚を食べる。'), ('C', '京都は古い都である。')]
    rows = rows_of(T)
    S = sp.build_space(rows)
    sl = SL.Slide(S, SL.default_spec(S, z_deep="slide"), rows=rows)      # G3-i: the committed code's default spec = z_deep "slide"
    t = S.tiers['RUN']
    h = hashlib.sha256()
    for pair in sl.pairs():
        ev = SR.counts_evidence(sl.counts(pair, 'corpus'), 'RUN')
        h.update(sl.counts(pair, 'corpus').to_bytes())

        def seat(u, sid, arm, pos=0):
            return SR.SeatRec(u, sid, arm, pos)
        crosses = [[seat('東京', 0, 'center'), seat('首都', 0, '+x'), seat('日本', 0, '-x'), seat('都市', 1, '-z')],
                   [seat('東京', 0, 'center'), seat('首都', 0, '-x'), seat('日本', 0, '+z'), seat('都市', 1, '-z')]]
        for cs in crosses:
            wc = SR.WindowCross(1, tuple(sorted(cs, key=lambda s: [x for x in geo.seats(1)].index(s.seat))), 'RUN', (0, 1))
            for q in (('首都', '東京'), ('東京',), ()):
                for r in (geo.IDENTITY, geo.G24[5]):
                    for ag in SR.AGREEMENTS:
                        h.update(SR.read_axes(dataclasses.replace(wc, orientation=r), ev, t, q, sl.spec.foundation, agreement=ag).to_bytes())
    return h.hexdigest(), sl.spec.sha256()


def test_the_g3d_toy_ratios_and_the_default_slide_spec_keep_the_bytes_of_the_committed_code():
    assert ratios_digest() == (RATIOS_DIGEST, RATIOS_SPEC_SHA)


# ==== part 6: seeds, no float ============================================================================================
def test_bytes_are_identical_under_three_hash_seeds_for_z_deep():
    prog = (
        "import hashlib,itertools,dataclasses\n"
        "from verantyx.line3 import slide as SL, slide_place as SP, slide_ratios as SR, space as sp, geometry as geo\n"
        "T=[('A','犬が走る。'),('A','猫と魚と鳥が走る。'),('B','猫と魚と鳥が泳ぐ。'),('B','犬が鳥を追う。'),('C','星が光る。'),('C','星と月と雲と空が光る。'),('D','京都は古い都である。')]\n"
        "seen={};rows=[]\n"
        "for t,s in T:\n i=seen.get(t,0);seen[t]=i+1;rows.append({'title':t,'sent':s,'source':'%s#%d'%(t,i)})\n"
        "S=sp.build_space(rows);h=hashlib.sha256()\n"
        "for zd in SL.Z_DEEPS:\n"
        " sl=SL.Slide(S,SL.default_spec(S,z_deep=zd),rows=rows);h.update(sl.spec.to_bytes())\n"
        " for cs,gr,sk in itertools.product(SP.CENTRE_SCOPES,('n_then_n1','z_reserved'),SP.SEAT_KEYS):\n"
        "  spec=SP.make_spec(sl,centre_scope=cs,growth=gr,seat_key=sk);h.update(spec.to_bytes())\n"
        "  for pw in SP.place_windows(sl,'one'):\n"
        "   p=SP.place_window(sl,pw,spec);h.update(p.to_bytes())\n"
        "   if len(pw.window.sids)==2:\n"
        "    ev=SR.counts_evidence(sl.counts(pw.window,'corpus'),'RUN');t=S.tiers['RUN']\n"
        "    for ag in SR.AGREEMENTS:\n"
        "     h.update(SR.read_axes(SR.window_cross(p.doc()),ev,t,('魚','鳥'),sl.spec.foundation,agreement=ag).to_bytes())\n"
        "print(h.hexdigest())")
    outs = set()
    for seed in ("0", "1", "12345"):
        out = subprocess.run([PY, "-c", prog], cwd=ROOT, env=dict(os.environ, PYTHONPATH=ROOT, PYTHONHASHSEED=seed), capture_output=True, text=True)
        assert out.returncode == 0, out.stderr
        outs.add(out.stdout.strip())
    assert len(outs) == 1 and len(next(iter(outs))) == 64


def test_no_float_in_the_g3c4_records_counts_and_ratios(s_order):
    def hook(s):
        raise AssertionError("a float: %s" % s)
    json.loads(s_order.spec.to_bytes().decode("utf-8"), parse_float=hook)
    for cs in SP.CENTRE_SCOPES:
        spec = SP.make_spec(s_order, centre_scope=cs)
        json.loads(spec.to_bytes().decode("utf-8"), parse_float=hook)
        for pw in SP.place_windows(s_order, "one"):
            p = SP.place_window(s_order, pw, spec)
            json.loads(p.to_bytes().decode("utf-8"), parse_float=hook)
            json.loads(s_order.counts(pw.window, "corpus").to_bytes().decode("utf-8"), parse_float=hook)
            if len(pw.window.sids) == 2:
                ev = SR.counts_evidence(s_order.counts(pw.window, "corpus"), "RUN")
                r = SR.read_axes(SR.window_cross(p.doc()), ev, s_order.space.tiers["RUN"], ("魚", "鳥"), s_order.spec.foundation)
                json.loads(r.to_bytes().decode("utf-8"), parse_float=hook)
