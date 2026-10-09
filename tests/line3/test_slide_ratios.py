"""G3-d tests (L-600..): the three ratios per axis of a window cross and the labelled per-axis answer
(verantyx/line3/slide_ratios.py).

Part 1 (hand toy windows of test_slide_place's corpus, a question): the section walk / edge flow / placement binding of each axis by hand,
agreement per axis, typed abstention per axis (tie, ratio disagreement, no edges), an asymmetric z edge read from both ends, the
labelled answer with its seats and sources.
Part 2 (weights): the weight multiplies the edge terms of F_a and B_a only; changing a weight never changes a section walk, E_Q,
the counts or the plain sums; the read order follows the axis weights.
Part 3 (merged check, 7.3): with n_a = n_pair on every arm and no weights, the per-axis sums over x, y, z equal energy.edge_flow /
placement_binding of today's cycle on the same cross, in all 24 orientations; on the real counts the z terms differ, and so
do the weighted sums.
Part 4 (orientation, windows): the labels follow the arms; a rotation changes only which sections see an arm of an axis.
Part 5 (two seats per unit keyed (unit, sid), z self edges), the record adapter (the real slide_place record), the question
attachment (cycle.make_context), the trace, bytes under three hash seeds, no float, nothing hooked.
Part 6 (fulllead, first windows): the invariants (merged equality, trace, determinism) on real records."""
import ast
import dataclasses
import itertools
import json
import os
import subprocess
import sys
from fractions import Fraction as Fr
from types import SimpleNamespace

import pytest

from verantyx.line3 import cycle as cy
from verantyx.line3 import energy as en
from verantyx.line3 import geometry as geo
from verantyx.line3 import slide as SL
from verantyx.line3 import slide_ratios as SR
from verantyx.line3 import space as sp

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PY = sys.executable
FL = os.path.join(ROOT, "experiments/line3/bank2/data/fulllead_sents.jsonl")

TOY = [
    ("A", "東京は日本の首都である。"),      # sid 0   RUN 東京 日本 首都
    ("A", "東京は日本の都市である。"),      # sid 1   RUN 東京 日本 都市
    ("B", "犬が猫を追う。"),                # sid 2   RUN 犬 猫
    ("B", "猫が魚を食べる。"),              # sid 3   RUN 猫 魚 食
    ("C", "京都は古い都である。"),          # sid 4   RUN 京都 古い 都   (a one-sentence article)
]
# n (RUN): 東京 2, 日本 2, 首都 1, 都市 1, 犬 1, 猫 2, 魚 1, 食 1, 京都 1, 古い 1, 都 1;  N = 5
W = {a: Fr(f, 377) for a, f in zip(geo.AXES, (144, 89, 55, 34, 21, 13))}      # the P7 weights on +x -x +y -y +z -z


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
def tier(space):
    return space.tiers["RUN"]


@pytest.fixture(scope="module")
def counts(slide):
    return slide.counts(slide.pairs()[0], "corpus")


@pytest.fixture(scope="module")
def ev(counts):
    return SR.counts_evidence(counts, "RUN")


@pytest.fixture(scope="module")
def fnd(slide):
    return slide.spec.foundation


def S(unit, sid, arm, pos=0, sources=()):
    return SR.SeatRec(unit, sid, arm, pos, sources)


def cross_of(*seats, L=1, tier="RUN", sids=(0, 1), orientation=geo.IDENTITY):
    return SR.WindowCross(L, tuple(sorted(seats, key=lambda s: {x: i for i, x in enumerate(geo.seats(L))}[s.seat])), tier, sids,
                          orientation)


# window (0, 1): 東京 日本 首都 | 東京 日本 都市
T1 = cross_of(S("東京", 0, "center"), S("日本", 0, "-x"), S("首都", 0, "+z"), S("都市", 1, "-z"))
T2 = cross_of(S("東京", 0, "center"), S("首都", 0, "+x"), S("日本", 0, "-x"), S("都市", 1, "-z"))
T3 = cross_of(S("東京", 0, "center"), S("首都", 0, "-x"), S("日本", 0, "+z"), S("都市", 1, "-z"))
Q1 = ("首都", "東京")        # I-07: 首都 attached to section 0, 東京 to section 1
Q3 = ("東京",)


def ref_flows(wc, evidence, tier, q, w):
    """An independent route to F_a, B_a (weighted and plain): from each seat over geometry.neighbours (not over geometry.edges), the
    edge's arm taken from whichever of the two seats lies on an arm.  Returns {axis: (F, B, Fp, Bp)} over the distinct units."""
    by = wc.by_seat()
    out = {a: ({u: Fr(0) for u in wc.units()}, {u: Fr(0) for u in wc.units()}, {u: Fr(0) for u in wc.units()},
               {u: Fr(0) for u in wc.units()}) for a in SR.AXES}
    for s, rec in by.items():
        for nb in geo.neighbours(s, wc.L):
            if nb not in by:
                continue
            o = by[nb]
            if rec.unit == o.unit:
                continue
            outer, inner = (s, nb) if s != geo.CENTER and (nb == geo.CENTER or nb.k == s.k + 1) else (nb, s)
            arm = outer.arm
            n, _ = evidence(arm, by[outer].unit, by[inner].unit)
            if n <= 0:
                continue
            F, B, Fp, Bp = out[arm[1]]
            nu, nv = len(tier.postings[o.unit]), len(tier.postings[rec.unit])
            t = en.energy(tier, o.unit, q) * Fr(n, nu)
            Fp[rec.unit] += t
            F[rec.unit] += w[arm] * t
            Bp[rec.unit] += Fr(n, nv)
            B[rec.unit] += w[arm] * Fr(n, nv)
    return out


def read(wc, ev, tier, fnd, q, **kw):
    return SR.read_axes(wc, ev, tier, q, fnd, **kw)


# ==== part 1: hand numbers ==========================================================================================
def test_t1_x_tie_gives_a_typed_abstention_with_the_hand_sections(tier, ev, fnd):
    """Cross 東京 centre, 日本 on -x, 首都 on +z, 都市 on -z; question (首都, 東京).  E_Q: 東京 1, 日本 1, 首都 3/5, 都市 2/5.
    Axis x has one edge (日本 -> 東京, n_x = 2, weight 89/377): F_x(東京) = F_x(日本) = 89/377 and B likewise: a tie on both."""
    r = read(T1, ev, tier, fnd, Q1)
    x = r.axis("x")
    assert dict(x.edge_flow) == {"東京": W["-x"], "日本": W["-x"], "首都": 0, "都市": 0}
    assert dict(x.binding) == {"東京": W["-x"], "日本": W["-x"], "首都": 0, "都市": 0}
    assert dict(x.binding_plain) == {"東京": 1, "日本": 1, "首都": 0, "都市": 0}
    assert x.edge_unit is None and x.binding_unit is None            # ties point nowhere (I-11, L-58)
    # R1_x: the sections that see an arm of x are 0 (-z +x -x), 1 (+x -x +y), 2 (-x +y -y), 5 (+z -z +x); 5 sees only the empty +x
    assert [s.section for s in x.sections] == [0, 1, 2, 5]
    assert [(s.section, s.attached, s.unit, s.energy) for s in x.sections] == [
        (0, "首都", "東京", Fr(3, 5)), (1, "東京", "東京", Fr(4, 5)), (2, None, "東京", Fr(1)), (5, None, None, None)]
    assert x.section_unit == "東京" and x.working == 3 and x.grounded == 2
    assert x.status == SR.POINTS_NOWHERE and x.unit is None
    a = r.abstention("x")
    assert a.kind == SR.POINTS_NOWHERE and a.nowhere == ("edge", "binding") and a.units == ("東京", None, None)


def test_t1_z_ratio_disagreement_and_the_weights_decide_the_binding(tier, ev, fnd):
    """Axis z: +z edge (首都 outer in N, 東京 inner in N+1, n_z = 1, w 21/377) and -z edge (都市 outer, 東京 inner, n_z(東京, 都市)
    = 1, w 13/377).  F_z(東京) = 21/377 * 3/5 * 1/1 + 13/377 * 2/5 * 1/1 = 89/1885; F_z(首都) = 21/377 * 1 * 1/2 = 21/754;
    F_z(都市) = 13/754.  B_z plain: 1 for 東京, 首都, 都市 (a tie) but weighted 東京 17/377, 首都 21/377, 都市 13/377: the weight
    makes 首都 the binding's unit while the edge flow and the sections say 東京."""
    r = read(T1, ev, tier, fnd, Q1)
    z = r.axis("z")
    assert dict(z.edge_flow) == {"東京": Fr(89, 1885), "日本": 0, "首都": Fr(21, 754), "都市": Fr(13, 754)}
    assert dict(z.binding) == {"東京": Fr(17, 377), "日本": 0, "首都": Fr(21, 377), "都市": Fr(13, 377)}
    assert dict(z.edge_flow_plain) == {"東京": Fr(1), "日本": 0, "首都": Fr(1, 2), "都市": Fr(1, 2)}      # 3/5 + 2/5 ; 1 * 1/2
    assert dict(z.binding_plain) == {"東京": 1, "日本": 0, "首都": 1, "都市": 1}
    assert [s.section for s in z.sections] == [0, 3, 4, 5]
    assert all(s.unit == "東京" for s in z.sections)
    assert (z.section_unit, z.edge_unit, z.binding_unit) == ("東京", "東京", "首都")
    assert z.status == SR.RATIO_DISAGREEMENT
    plain_tie = en.unique_argmax(dict(z.binding_plain))
    assert plain_tie is None                      # without the weight the binding of z would point nowhere
    assert r.abstention("z").kind == SR.RATIO_DISAGREEMENT and r.abstention("z").units == ("東京", "東京", "首都")


def test_t1_y_has_no_edges_in_one_tier_and_the_result_is_three_abstentions(tier, ev, fnd):
    r = read(T1, ev, tier, fnd, Q1)
    y = r.axis("y")
    assert y.status == SR.NO_EDGES and y.seated_edges == 0 and y.unit is None and y.working == 0
    assert all(v == 0 for v in y.edge_flow.values()) and all(v == 0 for v in y.binding.values())
    assert r.answers == () and [a.axis for a in r.abstentions] == ["x", "y", "z"]
    assert [a.kind for a in r.abstentions] == [SR.POINTS_NOWHERE, SR.NO_EDGES, SR.RATIO_DISAGREEMENT]
    assert r.abstention("y").nowhere == ("section", "edge", "binding")


def test_t2_x_agrees_with_hand_numbers_and_a_labelled_answer(tier, ev, fnd, counts):
    """Cross 東京 centre, 首都 on +x (n_x 1, w 144/377), 日本 on -x (n_x 2, w 89/377), 都市 on -z.  Question (首都, 東京).
    F_x(東京) = 144/377 * 3/5 * 1/1 + 89/377 * 1 * 2/2 = 877/1885; F_x(日本) = 89/377 * 1 * 2/2; F_x(首都) = 144/377 * 1 * 1/2.
    B_x(東京) = 144/377 * 1/2 + 89/377 * 2/2 = 161/377; B_x(日本) = 89/377; B_x(首都) = 144/377.  Every section walks to the centre."""
    r = read(T2, ev, tier, fnd, Q1)
    x = r.axis("x")
    assert dict(x.edge_flow) == {"東京": Fr(877, 1885), "首都": Fr(72, 377), "日本": Fr(89, 377), "都市": 0}
    assert dict(x.binding) == {"東京": Fr(161, 377), "首都": Fr(144, 377), "日本": Fr(89, 377), "都市": 0}
    assert (x.section_unit, x.edge_unit, x.binding_unit, x.status, x.unit) == ("東京", "東京", "東京", SR.AGREE, "東京")
    assert [s.section for s in x.sections] == [0, 1, 2, 5] and all(s.unit == "東京" for s in x.sections)
    a = r.answer("x")
    assert (a.axis, a.label, a.unit) == ("x", "slide:x", "東京")
    assert (a.section, a.edge_flow, a.binding) == (Fr(1), Fr(877, 1885), Fr(161, 377))       # section: the largest ending energy
    assert (a.edge_flow_plain, a.binding_plain) == (Fr(3, 5) + 1, Fr(3, 2))                   # E(首都)/1 + E(日本) * 2/2 ; 1/2 + 1
    assert a.grounded == 2
    assert [(s.unit, s.sid, s.arm, s.position) for s in a.seats] == [("東京", 0, "center", 0)]
    assert sorted((t.arm, t.other, t.n) for t in a.edges) == [("+x", ("首都", 0), 1), ("-x", ("日本", 0), 2)]
    for t in a.edges:                                                                      # the counts' own source rows, n of them
        assert len(t.sources) == t.n and all(isinstance(r_, tuple) and r_[0] in (0, 1) for r_ in t.sources)
    assert r.answer("z") is None and r.abstention("z").kind == SR.RATIO_DISAGREEMENT
    # z of T2: only the -z edge (都市 -> 東京): F_z(東京) = 13/377 * 2/5, F_z(都市) = 13/377 * 1 * 1/2 -> the edge flow and the binding say 都市
    z = r.axis("z")
    assert dict(z.edge_flow) == {"東京": Fr(26, 1885), "都市": Fr(13, 754), "首都": 0, "日本": 0}
    assert (z.section_unit, z.edge_unit, z.binding_unit) == ("東京", "都市", "都市")


def test_t3_z_agrees_while_x_does_not_each_axis_is_judged_on_its_own(tier, ev, fnd):
    """Cross 東京 centre, 首都 on -x, 日本 on +z, 都市 on -z; question (東京).  E_Q: 東京 4/5, 日本 4/5, 首都 2/5, 都市 2/5.
    z: F_z(東京) = 21/377 * 4/5 * 1/2 + 13/377 * 2/5 * 1/1 = 68/1885, F_z(日本) = 21/377 * 4/5 * 1/2 = 42/1885, F_z(都市) = 26/1885;
    B_z(東京) = 17/377 > B_z(都市) = 13/377 > B_z(日本) = 21/754: AGREE on 東京 and an answer slide:z.
    x: F_x(東京) = F_x(首都) = 178/1885 (a tie) while B_x says 首都: the abstention names exactly the edge flow."""
    r = read(T3, ev, tier, fnd, Q3)
    assert dict(r.axis("z").edge_flow) == {"東京": Fr(68, 1885), "日本": Fr(42, 1885), "都市": Fr(26, 1885), "首都": 0}
    assert dict(r.axis("z").binding) == {"東京": Fr(17, 377), "日本": Fr(21, 754), "都市": Fr(13, 377), "首都": 0}
    z = r.answer("z")
    assert (z.label, z.unit, z.edge_flow, z.binding, z.section) == ("slide:z", "東京", Fr(68, 1885), Fr(17, 377), Fr(4, 5))
    assert (z.edge_flow_plain, z.binding_plain) == (Fr(4, 5), Fr(1))
    assert dict(r.axis("x").edge_flow) == {"東京": Fr(178, 1885), "首都": Fr(178, 1885), "日本": 0, "都市": 0}
    x = r.abstention("x")
    assert x.kind == SR.POINTS_NOWHERE and x.nowhere == ("edge",) and x.units == ("東京", None, "首都")
    assert [a.axis for a in r.answers] == ["z"] and [a.axis for a in r.abstentions] == ["x", "y"]
    assert r.axis("z").grounded == 1                        # only section 0 carries an attached query unit (東京)


def test_the_z_edge_has_a_direction_and_both_ends_see_the_same_number(tier, ev, fnd, counts):
    """+z wants the outer unit in N and the inner in N+1.  都市 lies only in N+1: on -z next to 東京 it has n_z = 1, on +z none.
    Both ends of the edge read the same n_a(outer, inner) (F_z(都市) divides by n(東京), F_z(東京) by n(都市))."""
    on_minus = cross_of(S("東京", 0, "center"), S("都市", 1, "-z"))
    on_plus = cross_of(S("東京", 0, "center"), S("都市", 1, "+z"))
    a, b = read(on_minus, ev, tier, fnd, Q3), read(on_plus, ev, tier, fnd, Q3)
    assert counts.n_z("RUN", "東京", "RUN", "都市") == 1 and counts.n_z("RUN", "都市", "RUN", "東京") == 0
    assert a.axis("z").seated_edges == 1 and dict(a.axis("z").edge_flow) == {
        "東京": W["-z"] * Fr(2, 5) / 1, "都市": W["-z"] * Fr(4, 5) / 2}
    assert dict(a.axis("z").binding) == {"東京": W["-z"] / 2, "都市": W["-z"]}
    assert all(v == 0 for v in b.axis("z").edge_flow.values()) and all(v == 0 for v in b.axis("z").binding.values())
    assert b.axis("z").status == SR.POINTS_NOWHERE and b.axis("z").seated_edges == 1     # an edge is there, no evidence on it


@pytest.mark.parametrize("wc,q", [(T1, Q1), (T2, Q1), (T3, Q3), (T2, ("zzz",)), (T3, ())])
def test_the_hand_crosses_equal_an_independent_route(wc, q, tier, ev, fnd):
    r = read(wc, ev, tier, fnd, q)
    ctx = cy.make_context(q)
    ref = ref_flows(wc, ev, tier, tuple(sorted(set(ctx.energy_units))), W)
    for a in SR.AXES:
        ax = r.axis(a)
        F, B, Fp, Bp = ref[a]
        assert (dict(ax.edge_flow), dict(ax.binding), dict(ax.edge_flow_plain), dict(ax.binding_plain)) == (F, B, Fp, Bp)


def test_an_unplaced_or_out_of_space_unit_is_neither_an_error_nor_evidence(tier, ev, fnd):
    wc = cross_of(S("東京", 0, "center"), S("日本", 0, "-x"), S("ない語", 0, "+x"))
    r = read(wc, ev, tier, fnd, ("ない語",))
    assert r.axis("x").edge_flow["ない語"] == 0 and r.axis("x").binding["ない語"] == 0         # L-52 / L-53
    assert r.axis("x").seated_edges == 2


def test_an_answer_is_not_gated_by_the_question_attachment_but_records_grounded(tier, ev, fnd):
    """N-03 (an answer needs a working section with an in-space query unit) is G3-e's: here `grounded` is recorded only."""
    r = read(T2, ev, tier, fnd, ("zzz",))
    x = r.answer("x")
    assert x is not None and x.unit == "東京" and x.grounded == 0
    assert dict(r.axis("x").edge_flow)["東京"] == Fr(322, 1885)             # E_Q = r0 only: 144/377 * 1/5 + 89/377 * 2/5 * 2/2
    assert r.attached == ((0, "zzz"),)


# ==== part 2: where the weights enter =============================================================================
def test_weights_multiply_the_edge_terms_of_F_and_B_and_nothing_else(tier, ev, fnd):
    base = read(T2, ev, tier, fnd, Q1)
    w2 = dict(W)
    w2["+x"] = Fr(150, 377)                                                   # only the +x arm changes
    alt = read(T2, ev, tier, None, Q1, weights=w2)
    for a in SR.AXES:
        assert base.axis(a).sections == alt.axis(a).sections                   # the section walk never sees a weight
        assert base.axis(a).edge_flow_plain == alt.axis(a).edge_flow_plain      # nor does the plain sum
        assert base.axis(a).binding_plain == alt.axis(a).binding_plain
        assert base.axis(a).section_unit == alt.axis(a).section_unit
    for a in ("y", "z"):                                                       # the other axes' weighted values are untouched
        assert base.axis(a) == alt.axis(a)
    bx, ax = base.axis("x"), alt.axis("x")
    assert dict(ax.edge_flow) != dict(bx.edge_flow) and dict(ax.binding) != dict(bx.binding)
    # F_x(東京) = w(+x) * 3/5 + w(-x) * 1 : only the +x term moved
    assert ax.edge_flow["東京"] - bx.edge_flow["東京"] == (w2["+x"] - W["+x"]) * Fr(3, 5)
    assert ax.binding["東京"] - bx.binding["東京"] == (w2["+x"] - W["+x"]) * Fr(1, 2)
    assert ax.edge_flow["首都"] - bx.edge_flow["首都"] == (w2["+x"] - W["+x"]) * Fr(1, 2)
    assert ax.edge_flow["日本"] == bx.edge_flow["日本"] and ax.binding["日本"] == bx.binding["日本"]
    # E_Q, n, the counts are not weighted: the answer's section value and the query are the same
    assert base.query == alt.query and base.answer("x").unit == alt.answer("x").unit == "東京"
    assert base.answer("x").section == alt.answer("x").section                   # the walk's energy is not weighted


def test_unit_weights_make_the_weighted_sums_the_plain_sums_and_a_common_factor_changes_no_agreement(tier, ev, fnd):
    for wc, q in ((T1, Q1), (T2, Q1), (T3, Q3)):
        u = read(wc, ev, tier, None, q, weights=SR.UNIT_WEIGHTS)
        base = read(wc, ev, tier, fnd, q)
        for a in SR.AXES:
            assert dict(u.axis(a).edge_flow) == dict(u.axis(a).edge_flow_plain) == dict(base.axis(a).edge_flow_plain)
            assert dict(u.axis(a).binding) == dict(u.axis(a).binding_plain)
        scaled = {arm: 10 * w for arm, w in W.items()}                          # one factor on every arm: the same decisions
        s = read(wc, ev, tier, None, q, weights=scaled)
        assert [a.status for a in s.axes] == [a.status for a in base.axes] and [a.unit for a in s.axes] == [a.unit for a in base.axes]
        for a in SR.AXES:
            assert all(s.axis(a).edge_flow[k] == 10 * base.axis(a).edge_flow[k] for k in base.axis(a).edge_flow)


def test_a_weight_can_move_a_decision_inside_an_axis_and_the_plain_value_shows_it(tier, ev, fnd):
    """T1's z binding: plain it is a three-way tie (points nowhere), weighted it points to 首都 (21/377 against 17/377)."""
    r = read(T1, ev, tier, fnd, Q1)
    p = read(T1, ev, tier, None, Q1, weights=SR.UNIT_WEIGHTS)
    assert r.axis("z").binding_unit == "首都" and p.axis("z").binding_unit is None


def test_read_order_is_the_axis_weight_descending_and_the_third_place_of_the_weights(tier, fnd):
    """Two answers (x and z) from a hand evidence table on 東京 + 首都/日本 (x) + 猫/魚 (z).  Ladder weights read x before z;
    weights that make z heavier read z first without changing either answer (the factor is common to both arms of an axis)."""
    t = {("+x", "日本", "東京"): 1, ("-x", "首都", "東京"): 1, ("+z", "猫", "東京"): 1, ("-z", "都市", "東京"): 1}
    wc = cross_of(S("東京", 0, "center"), S("日本", 0, "+x"), S("首都", 0, "-x"), S("猫", 0, "+z"), S("都市", 1, "-z"))
    r = read(wc, SR.table_evidence(t), tier, fnd, ("東京",))
    assert [a.axis for a in r.answers] == ["x", "z"] and r.read_order == ("x", "y", "z")
    assert [a.axis for a in r.abstentions] == ["y"]
    # by hand (E_Q: 東京 4/5, 日本 4/5, 首都 2/5, 猫 2/5, 都市 2/5): F_x(東京) = 144/377 * 4/5 * 1/2 + 89/377 * 2/5 * 1/1 = 466/1885,
    # B_x(東京) = (144 + 89)/377 * 1/2 = 233/754; F_z(東京) = 21/377 * 2/5 * 1/2 + 13/377 * 2/5 * 1/1 = 47/1885, B_z(東京) = 34/754
    assert (r.answer("x").unit, r.answer("x").edge_flow, r.answer("x").binding) == ("東京", Fr(466, 1885), Fr(233, 754))
    assert (r.answer("z").unit, r.answer("z").edge_flow, r.answer("z").binding) == ("東京", Fr(47, 1885), Fr(17, 377))
    heavy = dict(W)
    for arm in ("+z", "-z"):
        heavy[arm] = W[arm] * 100
    for arm in ("+x", "-x"):
        heavy[arm] = W[arm] / 100
    r2 = read(wc, SR.table_evidence(t), tier, None, ("東京",), weights=heavy)
    assert r2.read_order == ("z", "y", "x") and [a.axis for a in r2.answers] == ["z", "x"]
    assert [a.unit for a in r2.answers] == [r.answer("z").unit, r.answer("x").unit]
    assert r2.answer("x").edge_flow == r.answer("x").edge_flow / 100 and r2.answer("z").binding == r.answer("z").binding * 100
    assert SR.read_order(SR.UNIT_WEIGHTS) == ("x", "y", "z")                       # equal axis weights keep the ladder order
    assert SR.read_order(SR.foundation_weights(fnd)) == ("x", "y", "z")


def test_the_foundation_weights_are_the_exact_ladder(fnd):
    assert SR.foundation_weights(fnd) == W and all(type(v) is Fr for v in W.values())
    with pytest.raises(ValueError):
        SR.read_axes(T1, SR.table_evidence({}), None, (), None)
    with pytest.raises(ValueError):
        SR.read_axes(T1, SR.table_evidence({}), None, (), None, weights={a: 1 for a in geo.AXES})       # ints, not Fractions


def test_an_axis_with_one_evidenced_edge_never_agrees_when_a_section_of_its_arm_reads_E_Q(tier, fnd):
    """On one edge (centre C, outer O, count n) R2 = C needs E_Q(O)/n(O) > E_Q(C)/n(C) and R3 = C needs n(C) < n(O), so
    E_Q(O) > E_Q(C); R1 = C needs the walk O -> C, i.e. E_s(C) >= E_s(O) in EVERY section that sees the arm, with E_s = E_q of the
    section's attached unit (L-59) or E_Q.  A section reading E_Q contradicts; so does a question of at most 3 units (window 3:
    the three sections of the arm then carry the whole query, and the sum of their three conditions gives E_Q(C) > E_Q(O)).
    Symmetrically for O.  (review, 2026-10-09) The claim is NOT "never": with 4+ query units, attached sections can all favour C
    while E_Q favours O (next test).  Checked exhaustively on the toy corpus: every ordered pair of in-space units, every arm,
    n in 1..3, every question of 0, 1 or 2 units: no axis agrees."""
    units = sorted(tier.postings)
    qs = [()] + [(u,) for u in units[:5]] + list(itertools.combinations(units[:4], 2))
    checked = 0
    for c, o in itertools.permutations(units, 2):
        for arm in geo.AXES:
            for n in (1, 2, 3):
                wc = cross_of(S(c, 0, "center"), S(o, 0, arm))
                ev_ = SR.table_evidence({(arm, o, c): n})
                for q in qs:
                    r = SR.read_axes(wc, ev_, tier, q, fnd)
                    assert r.answers == (), (c, o, arm, n, q)
                    checked += 1
    assert checked > 10000


def test_one_evidenced_edge_can_agree_when_every_section_of_its_arm_reads_an_attached_unit(fnd):
    """(review, 2026-10-09) The counter-example to "a single-edge axis never agrees": R1 reads E_q of the attached query unit (L-59),
    R2 reads E_Q.  Space: C in s0..s3, O in s3..s7 (n 4 / 5, n(C,O) = 1); a, b, c only in s0 (with C); d in s4..s7 (with O).  -x is
    seen by sections 0, 1, 2 (identity), which carry a, b, c: each favours C (4 + 1 >= 5 + 0), so the walk O -> C reaches the centre;
    d (section 3) pulls E_Q toward O: E_Q(O)/n(O) = 9/40 > E_Q(C)/n(C) = 7/32, so R2 = C; n(C) < n(O), so R3 = C.  One evidenced
    edge, AGREE.  With the three units a, b, c alone (no d) it does not agree."""
    from verantyx.line3.space import TierSpace
    sents = [("C", "a", "b", "c"), ("C",), ("C",), ("C", "O"), ("O", "d"), ("O", "d"), ("O", "d"), ("O", "d")]
    post = {}
    for i, s_ in enumerate(sents):
        for u in dict.fromkeys(s_):
            post.setdefault(u, []).append(i)
    t = TierSpace("RUN", tuple(sents), {u: tuple(v) for u, v in post.items()})
    wc = cross_of(S("C", 0, "center"), S("O", 1, "-x"))
    ev_ = SR.table_evidence({("-x", "O", "C"): 1})
    r = SR.read_axes(wc, ev_, t, ("a", "b", "c", "d"), fnd)
    x = r.axis("x")
    assert x.evidenced_edges == 1 and x.status == SR.AGREE and x.unit == "C"
    assert (x.section_unit, x.edge_unit, x.binding_unit) == ("C", "C", "C")
    assert [s_.attached for s_ in x.sections if s_.unit is not None] == ["a", "b", "c"]
    SR.check_trace(r)
    r3 = SR.read_axes(wc, ev_, t, ("a", "b", "c"), fnd)
    assert r3.answers == () and r3.axis("x").status == SR.RATIO_DISAGREEMENT
    assert SR.read_axes(wc, ev_, t, ("a", "b", "c", "d"), fnd, agreement="two_if_single_edge").axis("x").unit == "C"


# ==== part 2b: the agreement switch (L-615) and the z self edge default (L-616) ===================================
def test_the_agreement_switch_on_t1_one_evidenced_edge_is_judged_on_edge_flow_and_binding_only(tier, ev, fnd):
    """T1's x has ONE evidenced edge (日本 -> 東京): under "two_if_single_edge" its section walk is skipped and recorded as not
    applicable; F_x and B_x still tie, so the abstention names edge and binding and no longer the section.  z has two evidenced
    edges: identical under both rules."""
    a = read(T1, ev, tier, fnd, Q1)
    b = read(T1, ev, tier, fnd, Q1, agreement="two_if_single_edge")
    assert a.agreement == "three" and b.agreement == "two_if_single_edge"
    xa, xb = a.axis("x"), b.axis("x")
    assert (xa.evidenced_edges, xb.evidenced_edges) == (1, 1) and xa.section_applicable and not xb.section_applicable
    assert xb.sections == () and xb.working == 0 and xb.section_unit is None and xb.grounded == 0
    assert dict(xb.edge_flow) == dict(xa.edge_flow) and dict(xb.binding) == dict(xa.binding)
    assert xb.status == SR.POINTS_NOWHERE and b.abstention("x").nowhere == ("edge", "binding") and b.abstention("x").units == (None, None, None)
    assert a.abstention("x").nowhere == ("edge", "binding") and a.abstention("x").units == ("東京", None, None)
    assert a.axis("z") == b.axis("z") and b.axis("z").evidenced_edges == 2 and b.axis("z").section_applicable    # two edges: same rule
    assert a.axis("y") == b.axis("y") and b.axis("y").status == SR.NO_EDGES
    assert a.to_bytes() != b.to_bytes() and b.to_bytes() == read(T1, ev, tier, fnd, Q1, agreement="two_if_single_edge").to_bytes()


def test_the_agreement_switch_on_t3_x_stays_an_abstention_and_z_is_unchanged(tier, ev, fnd):
    """T3's x has one evidenced edge (首都 -> 東京): F_x ties (178/1885 each) and B_x says 首都, so it abstains under both rules
    (edge flow points nowhere); the answer slide:z (two edges) is the same under both rules."""
    a = read(T3, ev, tier, fnd, Q3)
    b = read(T3, ev, tier, fnd, Q3, agreement="two_if_single_edge")
    assert not b.axis("x").section_applicable and b.axis("x").status == SR.POINTS_NOWHERE
    assert b.abstention("x").nowhere == ("edge",) and b.abstention("x").units == (None, None, "首都")
    assert a.answers == b.answers and [x.axis for x in b.answers] == ["z"] and b.answer("z").section == Fr(4, 5)


def test_the_agreement_switch_can_give_a_single_edge_axis_an_answer_with_no_section_value(tier, ev, fnd):
    """Centre 東京, 首都 on +x (n_x 1, w 144/377), question (都市): E_Q 東京 3/5, 首都 1/5.  F_x(首都) = 144/377 * 3/5 * 1/2 = 216/1885 >
    F_x(東京) = 144/377 * 1/5 * 1/1 = 144/1885 and B_x(首都) = 144/377 > B_x(東京) = 144/754: edge flow and binding both say 首都.
    Under "three" the walk climbs to the centre (R1 = 東京): ratio_disagreement.  Under "two_if_single_edge" the answer is 首都,
    its section value is None (not applicable), it carries the edge term and no walk step, and the trace holds."""
    wc = cross_of(S("東京", 0, "center"), S("首都", 0, "+x"))
    three = read(wc, ev, tier, fnd, ("都市",))
    two = read(wc, ev, tier, fnd, ("都市",), agreement="two_if_single_edge")
    assert three.axis("x").status == SR.RATIO_DISAGREEMENT
    assert three.axis("x").section_unit == "東京" and three.abstention("x").units == ("東京", "首都", "首都")
    a = two.answer("x")
    assert a is not None and (a.unit, a.label, a.section) == ("首都", "slide:x", None)
    assert (a.edge_flow, a.binding) == (Fr(216, 1885), Fr(144, 377)) and a.walk_steps == () and a.grounded == 0
    assert [(t.this, t.other, t.n) for t in a.edges] == [(("首都", 0), ("東京", 0), 1)] and a.sources
    assert two.axis("x").unit == "首都" and two.axis("x").section_unit is None and two.axis("x").working == 0
    assert SR.check_trace(two) > 0
    doc = json.loads(two.to_bytes().decode("utf-8"))
    assert doc["agreement"] == "two_if_single_edge" and doc["answers"][0]["ratios"]["section"] is None
    assert doc["axes"][0]["section_applicable"] is False
    with pytest.raises(ValueError):
        read(wc, ev, tier, fnd, (), agreement="two")


def test_the_agreement_switch_exhaustive_single_edge_answers_have_r2_equal_r3_and_no_walk(tier, fnd):
    """Same space as the "never agrees" test: under "three" no single-edge axis answers; under "two_if_single_edge" some do, and
    each answer is exactly the case where the edge flow and the binding point to the same unit; every other axis is unchanged."""
    units = sorted(tier.postings)
    qs = [()] + [(u,) for u in units[:5]] + list(itertools.combinations(units[:4], 2))
    answered = 0
    for c, o in itertools.permutations(units, 2):
        for arm in geo.AXES:
            for n in (1, 2, 3):
                wc = cross_of(S(c, 0, "center"), S(o, 0, arm))
                ev_ = SR.table_evidence({(arm, o, c): n})
                for q in qs:
                    a3 = SR.read_axes(wc, ev_, tier, q, fnd)
                    a2 = SR.read_axes(wc, ev_, tier, q, fnd, agreement="two_if_single_edge")
                    assert a3.answers == ()
                    ax = a2.axis(arm[1])
                    assert ax.evidenced_edges == 1 and not ax.section_applicable
                    same = ax.edge_unit is not None and ax.edge_unit == ax.binding_unit
                    assert (a2.answer(arm[1]) is not None) == same
                    for other in SR.AXES:
                        if other != arm[1]:
                            assert a2.axis(other) == a3.axis(other)
                    if same:
                        answered += 1
                        assert a2.answer(arm[1]).walk_steps == () and a2.answer(arm[1]).section is None
    assert answered > 0


def test_two_evidenced_edges_are_judged_alike_under_both_rules(tier, ev, fnd):
    for wc, q in ((T2, Q1), (T3, Q3)):
        a = read(wc, ev, tier, fnd, q)
        b = read(wc, ev, tier, fnd, q, agreement="two_if_single_edge")
        for ax in SR.AXES:
            if a.axis(ax).evidenced_edges != 1:
                assert a.axis(ax) == b.axis(ax)


def test_z_self_edges_default_is_on_and_the_merged_check_stays_equal(tier, ev, fnd):
    import inspect
    assert inspect.signature(SR.read_axes).parameters["z_self_edges"].default is True
    wc = cross_of(S("東京", 0, "center"), S("日本", 0, "-x"), S("東京", 1, "+z"), S("都市", 1, "-z"))
    assert SR.merged_check(wc, tier, Q3).equal                      # merged_check fixes z_self_edges=False (energy.py's L-56)
    assert read(wc, ev, tier, fnd, Q3).z_self_edges and not read(wc, ev, tier, fnd, Q3, z_self_edges=False).z_self_edges


# ==== part 3: the merged check of 7.3 ==============================================================================
UNITS7 = ["東京", "日本", "犬", "首都", "猫", "都市", "魚"]       # centre, +x -x +y -y +z -z: 日本 首都 都市 pair with 東京 (x, y, z)


def full_cross(L=1, units=UNITS7):
    seats = [S(units[0], 0, "center")]
    it = iter(units[1:])
    for arm in geo.AXES:
        for k in range(L):
            u = next(it, None)
            if u is not None:
                seats.append(S(u, 0 if k % 2 == 0 else 1, arm, k))
    return cross_of(*seats, L=L)


MERGED_CROSSES = [
    ("T1", T1, Q1), ("T2", T2, Q1), ("T3", T3, Q3),
    ("full L1", full_cross(), ("東京", "猫")),
    ("full L2", full_cross(2, UNITS7 + ["食", "京都", "古い", "都", "ない語", "東京"][:5]), ("日本", "魚", "猫")),
    ("no query", full_cross(), ()),
]


@pytest.mark.parametrize("name,wc,q", MERGED_CROSSES)
def test_merged_per_axis_sums_equal_todays_edge_flow_and_binding(name, wc, q, tier):
    rep = SR.merged_check(wc, tier, q)
    assert rep.edge_equal and rep.binding_equal and rep.equal
    assert rep.edge_flow_sum == rep.edge_flow_today and rep.binding_sum == rep.binding_today
    assert any(v != 0 for v in rep.edge_flow_today.values()) and any(v != 0 for v in rep.binding_today.values())
    for r in geo.G24:                                       # edges and counts do not depend on the orientation
        wc2 = dataclasses.replace(wc, orientation=r)
        assert SR.merged_check(wc2, tier, q).equal


def test_the_merged_check_is_not_vacuous_across_the_three_axes(tier):
    """The sums really run over all three axes: with every arm occupied each axis contributes, and no single axis equals the whole."""
    wc = full_cross()
    res = SR.read_axes(wc, SR.label_blind_evidence(tier), tier, ("東京", "猫"), weights=SR.UNIT_WEIGHTS)
    f0 = en.edge_flow(tier, wc.to_cross(), ("東京", "猫"))
    parts = [res.axis(a).edge_flow_plain for a in SR.AXES]
    assert all(any(v != 0 for v in p.values()) for p in parts)                           # x, y and z each carry flow
    assert all(parts[i] != f0 for i in range(3))
    assert {u: sum((p[u] for p in parts), Fr(0)) for u in wc.units()} == f0
    assert [res.axis(a).seated_edges for a in SR.AXES] == [2, 2, 2]                      # the edges partition by arm: 6 in all


def test_on_the_real_counts_x_equals_todays_n_but_z_does_not(tier, ev, counts):
    """n_x = n_pair on the corpus-scope counts (verify_counts), so a cross with x arms only equals today's sums; n_z is the
    slide evidence (u in N, v in N+1) and is not n_pair: the z terms differ, which is why 7.3 injects n_a = n."""
    xonly = cross_of(S("東京", 0, "center"), S("首都", 0, "+x"), S("日本", 0, "-x"))
    r = SR.read_axes(xonly, ev, tier, Q1, weights=SR.UNIT_WEIGHTS)
    cr = xonly.to_cross()
    assert dict(r.axis("x").edge_flow_plain) == en.edge_flow(tier, cr, tuple(sorted(Q1)))
    assert dict(r.axis("x").binding_plain) == en.placement_binding(tier, cr)
    zonly = cross_of(S("東京", 0, "center"), S("日本", 0, "+z"))
    rz = SR.read_axes(zonly, ev, tier, Q1, weights=SR.UNIT_WEIGHTS)
    assert counts.n_z("RUN", "日本", "RUN", "東京") == 1 and tier.n_pair("日本", "東京") == 2
    assert dict(rz.axis("z").binding_plain) != en.placement_binding(tier, zonly.to_cross())
    assert dict(rz.axis("z").edge_flow_plain) != en.edge_flow(tier, zonly.to_cross(), tuple(sorted(Q1)))


def test_the_weighted_variant_is_not_the_merged_quantity(tier, fnd):
    """With the Fibonacci weights (all < 1) the weighted sums are strictly smaller wherever there is flow, so the equality of 7.3 is
    stated, and tested, on the unweighted variant only."""
    wc = full_cross()
    res = SR.read_axes(wc, SR.label_blind_evidence(tier), tier, ("東京", "猫"), fnd)
    f0 = en.edge_flow(tier, wc.to_cross(), ("東京", "猫"))
    b0 = en.placement_binding(tier, wc.to_cross())
    fs = {u: sum((res.axis(a).edge_flow[u] for a in SR.AXES), Fr(0)) for u in wc.units()}
    bs = {u: sum((res.axis(a).binding[u] for a in SR.AXES), Fr(0)) for u in wc.units()}
    assert fs != f0 and bs != b0
    assert all(fs[u] <= f0[u] and bs[u] <= b0[u] for u in wc.units())
    assert any(fs[u] < f0[u] for u in wc.units())


def test_the_merged_check_covers_two_seats_of_one_unit(tier):
    wc = cross_of(S("東京", 0, "center"), S("日本", 0, "-x"), S("東京", 1, "+z"), S("都市", 1, "-z"))
    assert SR.merged_check(wc, tier, ("東京",)).equal           # energy.py's L-56: same-unit pairs add nothing, seats add up


# ==== part 4: orientation and windows =============================================================================
def test_rotation_changes_only_which_sections_see_an_axis_never_F_or_B(tier, ev, fnd):
    base = read(T2, ev, tier, fnd, Q1)
    seen = set()
    for r in geo.G24:
        wc = dataclasses.replace(T2, orientation=r)
        res = read(wc, ev, tier, fnd, Q1)
        for a in SR.AXES:
            ax, b = res.axis(a), base.axis(a)
            assert (dict(ax.edge_flow), dict(ax.binding), dict(ax.edge_flow_plain), dict(ax.binding_plain)) == (
                dict(b.edge_flow), dict(b.binding), dict(b.edge_flow_plain), dict(b.binding_plain))
            assert ax.seated_edges == b.seated_edges
            # the window table: section s sees exactly the visible arms of axis a (checked against geometry, 24 orientations)
            want = [s for s in range(6) if any(arm[1] == a for arm in geo.visible_arms(r, s))]
            assert [s.section for s in ax.sections] == want
            for s in ax.sections:
                assert s.arms == tuple(arm for arm in geo.visible_arms(r, s.section) if arm[1] == a)
            seen.add((a, tuple(want)))
    assert len({w for a, w in seen if a == "x"}) > 1                    # the sections of x do change with the orientation


def test_identity_window_table_sections_per_axis(tier, ev, fnd):
    """G3 3.3: with the world orientation the arms of x are visible in sections 0, 1, 2, 5; y in 1, 2, 3, 4; z in 3, 4, 5, 0."""
    full = read(full_cross(), ev, tier, fnd, Q1)
    assert [s.section for s in full.axis("x").sections] == [0, 1, 2, 5]
    assert [s.section for s in full.axis("y").sections] == [1, 2, 3, 4]
    assert [s.section for s in full.axis("z").sections] == [0, 3, 4, 5]


def test_the_section_walk_of_an_axis_is_todays_section_pointer_when_only_that_axis_is_occupied(tier):
    """R1 restricted to an axis is today's section pointer restricted to the arms of that axis: with label-blind evidence and a
    cross whose only occupied arms are those of x, every section of x points where energy.section_pointer points, through the
    same termini (the arms of the other axes are empty in both)."""
    wc = cross_of(S("東京", 0, "center"), S("首都", 0, "+x"), S("日本", 0, "-x"))
    res = SR.read_axes(wc, SR.label_blind_evidence(tier), tier, Q1, weights=SR.UNIT_WEIGHTS)
    q = tuple(sorted(Q1))
    att = cy.make_context(Q1).attached_map()
    for sec in res.axis("x").sections:
        sp_ = en.section_pointer(tier, wc.to_cross(), sec.section, q, att.get(sec.section))
        assert sp_.unit == sec.unit and [w.terminus for w in sp_.walks if w.terminus is not None] == [
            w.terminus[0] for w in sec.walks if w.terminus is not None]


def test_a_rotated_cross_keeps_its_labels_and_the_section_walk_follows_the_arm_windows(tier, ev, fnd):
    """After a rotation the arm "+x" points elsewhere, its contents stay, and the sections that see it are those the new
    orientation puts in front of it.  Quarter turn about z: +x -> +y."""
    r = next(g for g in geo.G24 if g.perm[0] == 2 and g.perm[4] == 4)             # +x -> +y, +z fixed
    res = read(dataclasses.replace(T2, orientation=r), ev, tier, fnd, Q1)
    want = [s for s in range(6) if "+x" in geo.visible_arms(r, s)]
    assert want != [5, 0, 1]
    seen_plus_x = [s.section for s in res.axis("x").sections if "+x" in s.arms]
    assert seen_plus_x == want


# ==== part 5: seats keyed (unit, sid), the record, the question, the trace, bytes ===================================
def test_two_seats_of_one_unit_are_keyed_unit_sid_and_the_z_self_edge_counts_by_default(tier, ev, fnd, counts):
    """東京 lies in both sentences: one seat per sentence, linked by a z edge (outer in N on +z, inner = the centre in N+1):
    n_z(東京, 東京) = 1.  Default (energy.py's L-56): the pair of seats of one unit adds nothing.  With z_self_edges each END adds
    w(+z) * E(東京) * 1 / n(東京) to F_z and w(+z) * 1 / n(東京) to B_z (E_Q(東京) = 4/5 under (東京))."""
    rec = {"tier": "RUN", "window": {"n": 0, "sids": (0, 1), "title": "A"}, "L": 1, "seats": [
        {"unit": "東京", "sid": 1, "arm": "center", "position": 0, "sources": [[1, 0, 2]]},
        {"unit": "東京", "sid": 0, "arm": "+z", "position": 0, "sources": [[0, 0, 2]]},
        {"unit": "日本", "sid": 0, "arm": "-x", "position": 0}]}
    wc = SR.window_cross(rec)
    assert [s.key for s in wc.seats] == [("東京", 1), ("日本", 0), ("東京", 0)] and wc.seats[0].sources == ((1, 0, 2),)
    assert counts.n_z("RUN", "東京", "RUN", "東京") == 1
    off = SR.read_axes(wc, ev, tier, Q3, fnd, z_self_edges=False)
    assert dict(off.axis("z").edge_flow) == {"東京": 0, "日本": 0} and off.axis("z").seated_edges == 1
    assert off.axis("z").status == SR.POINTS_NOWHERE
    on = SR.read_axes(wc, ev, tier, Q3, fnd)                           # owner after G3-d: the z self edge counts by default
    assert on.z_self_edges and on.to_bytes() == SR.read_axes(wc, ev, tier, Q3, fnd, z_self_edges=True).to_bytes()
    assert not off.z_self_edges and on.to_bytes() != off.to_bytes()
    assert dict(on.axis("z").edge_flow) == {"東京": 2 * W["+z"] * Fr(4, 5) * Fr(1, 2), "日本": 0}
    assert dict(on.axis("z").binding) == {"東京": 2 * W["+z"] * Fr(1, 2), "日本": 0}
    assert on.axis("z").status == SR.AGREE and on.answer("z").unit == "東京"        # the self edge alone makes 東京 the only unit with flow
    assert [(t.this, t.other) for t in on.answer("z").edges] == [(("東京", 0), ("東京", 1)), (("東京", 1), ("東京", 0))]
    assert SR.check_trace(on) > 0 and off.answer("z") is None
    assert on.axis("x").edge_flow == off.axis("x").edge_flow          # only z has the option
    with pytest.raises(ValueError):
        cross_of(S("東京", 0, "center"), S("東京", 0, "+z"))            # (unit, sid) on two seats
    with pytest.raises(ValueError):
        cross_of(S("東京", 0, "center"), S("日本", 0, "+z"), S("首都", 0, "+z"))     # two units on one seat
    assert SR.merged_check(wc, tier, Q3).equal


def test_the_adapter_reads_the_g3c_configuration_of_the_real_record_into_the_hand_cross(slide, tier, ev, fnd):
    from verantyx.line3 import slide_place as SP
    spec = SP.make_spec(slide, **SP.LEGACY)                       # one seat per unit: the G3-c record
    pw = next(p for p in SP.place_windows(slide) if p.window.n == 0)
    rec = SP.place_window(slide, pw, spec)
    cnt = slide.counts(pw.window, "corpus")
    wc = SR.window_cross(rec)
    assert [(s.unit, s.sid, s.arm, s.position) for s in wc.seats] == [(s.unit, s.sid, s.arm, s.position) for s in T1.seats]
    assert (wc.L, wc.tier, wc.sids) == (1, "RUN", (0, 1))
    by = {s.unit: s for s in wc.seats}
    assert by["東京"].sources[0][:5] == ("occ", "RUN", 0, 0, "東京") and by["都市"].sources[0][2] == 1      # the record's own provenance
    assert dict(wc.meta)["spec_sha256"] == rec.spec_sha and dict(wc.meta)["window_n"] == 0
    r = SR.read_axes(wc, SR.counts_evidence(cnt, "RUN"), tier, Q1, fnd)
    assert r.axes == read(T1, ev, tier, fnd, Q1).axes and r.answers == () and r.query == ("東京", "首都")
    # the same cross read without `seats` (the G3-c route through order_log, with the pack for sources) gives the same keys
    legacy = SimpleNamespace(tier=rec.tier, window=rec.window, L=rec.L, members=rec.members, order_log=rec.order_log,
                             spec_sha=rec.spec_sha, scope=rec.scope)
    wl = SR.window_cross(legacy, pack=slide.pack(pw.window))
    assert [(s.key, s.arm, s.position) for s in wl.seats] == [(s.key, s.arm, s.position) for s in wc.seats]
    assert [row[:4] for row in {s.unit: s for s in wl.seats}["東京"].sources] == [("RUN", 0, 0, "東京"), ("RUN", 1, 0, "東京")]
    mem = SR.window_crosses(rec)
    assert len(mem) == rec.class_size
    reads = SR.read_members(mem, SR.counts_evidence(cnt, "RUN"), tier, Q1, fnd)
    assert len(reads.reads) == rec.class_size and dict(reads.agreeing).keys() == {"x", "y", "z"}


def test_the_adapter_reads_the_two_seat_default_record_keyed_unit_sid(slide, tier, fnd):
    from verantyx.line3 import slide_place as SP
    spec = SP.make_spec(slide)                                    # the module default: a unit of both sentences has two seats
    pw = next(p for p in SP.place_windows(slide) if p.window.n == 0)
    rec = SP.place_window(slide, pw, spec)
    cnt = slide.counts(pw.window, "corpus")
    wc = SR.window_cross(rec)
    assert len(wc.seats) == len(rec.seats) and [s.key for s in wc.seats] == [(r_["unit"], r_["sid"]) for r_ in rec.seats]
    twins = [u for u in wc.units() if sum(1 for s in wc.seats if s.unit == u) == 2]
    assert twins and all({s.sid for s in wc.seats if s.unit == u} == {0, 1} for u in twins)        # 東京 and 日本: one seat per sentence
    ev_ = SR.counts_evidence(cnt, "RUN")
    for z_self in (False, True):
        r = SR.read_axes(wc, ev_, tier, Q1, fnd, z_self_edges=z_self)
        SR.check_trace(r)
        assert [a.axis for a in r.answers] + [a.axis for a in r.abstentions] and len(r.answers) + len(r.abstentions) == 3
    assert SR.merged_check(wc, tier, Q1).equal
    for c in SR.window_crosses(rec):                              # every member of the class, through the record's tokens
        assert {s.key for s in c.seats} == {s.key for s in wc.seats} and SR.merged_check(c, tier, Q1).equal
    assert SR.window_cross(rec, 0).seats == wc.seats
    # (review, 2026-10-09) the jsonl form of the record (its doc, members left out) reads to the same bytes as the object
    doc = json.loads(SL.canonical(rec.doc(members=False)))
    wj = SR.window_cross(doc)
    assert wj == wc and dict(wj.meta)["spec_sha256"] == rec.spec_sha and dict(wj.meta)["slide_spec_sha256"] == rec.slide_spec_sha
    for rule in SR.AGREEMENTS:
        assert SR.read_axes(wj, ev_, tier, Q1, fnd, agreement=rule).to_bytes() == SR.read_axes(wc, ev_, tier, Q1, fnd, agreement=rule).to_bytes()


def test_a_record_with_seats_carries_the_representative_only():
    rec = {"tier": "RUN", "window": {"n": 0, "sids": (0, 1)}, "seats": [{"unit": "東京", "sid": 0, "arm": "center", "position": 0}]}
    assert SR.window_cross(rec).L == 1 and len(SR.window_crosses(rec)) == 1
    with pytest.raises(ValueError):
        SR.window_cross(rec, 1)
    with pytest.raises(ValueError):
        SR.window_cross({"tier": "RUN", "window": {"sids": (0, 1)}, "members": ((None,) * 7,), "L": 1, "order_log": ()}, 1)


def test_the_question_is_attached_as_cycle_does_and_a_query_context_is_accepted(tier, ev, fnd):
    ctx = cy.make_context(("首都", "東京"))
    a = SR.read_axes(T2, ev, tier, ctx, fnd)
    b = SR.read_axes(T2, ev, tier, ("首都", "東京"), fnd)
    assert a.to_bytes() == b.to_bytes() and a.attached == ((0, "首都"), (1, "東京")) == tuple(sorted(ctx.attached_map().items()))
    assert a.query == ("東京", "首都")                                    # the set E_Q reads, in code point order
    seven = tuple("東京 日本 首都 都市 犬 猫 魚".split())
    c = SR.read_axes(T2, ev, tier, seven, fnd)
    assert len(c.query) == 6 and set(c.query) == set(seven[:6]) and [u for _s, u in c.attached] == list(seven[:6])    # L-109: the first layer
    assert SR.read_axes(T2, ev, tier, ("東京", "東京", "首都"), fnd).query == a.query                               # L-51: a set


def test_every_answer_unit_maps_to_seats_and_sources(tier, ev, fnd, counts):
    for wc, q in ((T2, Q1), (T3, Q3)):
        r = read(wc, ev, tier, fnd, q)
        assert r.answers
        assert SR.check_trace(r) > 0
        for a in r.answers:
            assert a.seats and all(s.unit == a.unit for s in a.seats) and a.sources
            assert all(row[0] == a.axis for row in a.sources)
            # the source rows are the counts' rows: for x (sid, spans), for z (sid_N, sid_N+1, spans) -- all of the window's sentences
            for row in a.sources:
                body = row[1:]
                assert all(isinstance(v, int) for v in body)
                assert set(body[:1] if a.axis == "x" else body[:2]) <= {0, 1}
            assert a.edges and all(len(t.sources) == t.n for t in a.edges)
            assert a.walk_steps and all(len(w.sources) == w.n for w in a.walk_steps)
    # a trace that does not add up is refused
    r = read(T2, ev, tier, fnd, Q1)
    bad = dataclasses.replace(r, answers=(dataclasses.replace(r.answers[0], edge_flow=r.answers[0].edge_flow + 1),))
    with pytest.raises(ValueError):
        SR.check_trace(bad)
    bad2 = dataclasses.replace(r, answers=(dataclasses.replace(r.answers[0], sources=()),))
    with pytest.raises(ValueError):
        SR.check_trace(bad2)


def test_the_x_sources_are_the_counts_own_rows(tier, ev, fnd, counts):
    r = read(T2, ev, tier, fnd, Q1)
    a = r.answer("x")
    rows = {row[1:] for row in a.sources}
    expect = set()
    for (o, i) in (("日本", "東京"), ("首都", "東京")):
        b, af = counts.x[("RUN", o, i)]
        expect |= set(b) | set(af)
    assert rows == expect and len(a.sources) == 3          # 2 sentences for 日本-東京 and 1 for 首都-東京


def test_bytes_are_canonical_exact_and_repeatable(tier, ev, fnd):
    r = read(T2, ev, tier, fnd, Q1)
    assert r.to_bytes() == read(T2, ev, tier, fnd, Q1).to_bytes() and len(r.sha256()) == 64
    doc = json.loads(r.to_bytes().decode("utf-8"), parse_float=lambda s: (_ for _ in ()).throw(AssertionError("float " + s)))
    assert doc["format"] == SR.FORMAT and doc["answers"][0]["ratios"]["binding"] == "161/377"
    assert doc["weights"]["+x"] == "144/377" and doc["read_order"] == ["x", "y", "z"] and "weights_enter" in doc
    assert read(T2, ev, tier, fnd, ("東京",)).to_bytes() != r.to_bytes()


def test_no_float_in_the_module():
    tree = ast.parse(open(SR.__file__).read())
    for n in ast.walk(tree):
        if isinstance(n, ast.Constant):
            assert not isinstance(n.value, float)
        if isinstance(n, ast.Name):
            assert n.id != "float"
        if isinstance(n, ast.BinOp):
            assert not isinstance(n.op, ast.Div)


def test_nothing_is_hooked_and_importing_the_module_writes_nothing(tmp_path):
    code = ("import os,sys\nbefore=sorted(os.listdir('.'))\nimport verantyx.line3.slide_ratios\n"
            "bad=[m for m in sys.modules if m.startswith('verantyx.line3.') and m.split('.')[2] in "
            "('ask','matryoshka','carry','carry_query','readout','trace_check','grammar','slide_place')]\n"
            "print(','.join(bad)); print(sorted(os.listdir('.'))==before)")
    out = subprocess.run([PY, "-c", code], cwd=str(tmp_path), env=dict(os.environ, PYTHONPATH=ROOT), capture_output=True, text=True)
    assert out.returncode == 0, out.stderr
    assert out.stdout.split("\n")[:2] == ["", "True"] and out.stderr == ""
    for mod in ("ask", "cycle", "matryoshka", "cli", "energy", "slide", "slide_place"):
        p = os.path.join(ROOT, "verantyx/line3/%s.py" % mod) if mod != "cli" else os.path.join(ROOT, "verantyx/cli.py")
        assert "slide_ratios" not in open(p).read(), mod


def test_bytes_are_identical_under_three_hash_seeds():
    prog = (
        "import hashlib\n"
        "from fractions import Fraction as Fr\n"
        "from verantyx.line3 import slide as SL, slide_ratios as SR, space as sp, geometry as geo\n"
        "T=[('A','東京は日本の首都である。'),('A','東京は日本の都市である。'),('B','犬が猫を追う。'),('B','猫が魚を食べる。'),('C','京都は古い都である。')]\n"
        "seen={};rows=[]\n"
        "for t,s in T:\n i=seen.get(t,0);seen[t]=i+1;rows.append({'title':t,'sent':s,'source':'%s#%d'%(t,i)})\n"
        "S=sp.build_space(rows);sl=SL.Slide(S,rows=rows);t=S.tiers['RUN'];h=hashlib.sha256()\n"
        "ev=SR.counts_evidence(sl.counts(sl.pairs()[0],'corpus'),'RUN')\n"
        "def seat(u,sid,arm,pos=0): return SR.SeatRec(u,sid,arm,pos)\n"
        "crosses=[[seat('東京',0,'center'),seat('首都',0,'+x'),seat('日本',0,'-x'),seat('都市',1,'-z')],\n"
        "         [seat('東京',0,'center'),seat('首都',0,'-x'),seat('日本',0,'+z'),seat('都市',1,'-z')]]\n"
        "for cs in crosses:\n"
        " wc=SR.WindowCross(1,tuple(sorted(cs,key=lambda s:[x for x in geo.seats(1)].index(s.seat))),'RUN',(0,1))\n"
        " for q in (('首都','東京'),('東京',),()):\n"
        "  for r in (geo.IDENTITY,geo.G24[5]):\n"
        "   import dataclasses\n"
        "   res=SR.read_axes(dataclasses.replace(wc,orientation=r),ev,t,q,sl.spec.foundation);h.update(res.to_bytes())\n"
        "   h.update(repr(sorted(SR.merged_check(wc,t,q).edge_flow_sum.items())).encode())\n"
        "print(h.hexdigest())")
    outs = set()
    for seed in ("0", "1", "12345"):
        out = subprocess.run([PY, "-c", prog], cwd=ROOT, env=dict(os.environ, PYTHONPATH=ROOT, PYTHONHASHSEED=seed),
                             capture_output=True, text=True)
        assert out.returncode == 0, out.stderr
        outs.add(out.stdout.strip())
    assert len(outs) == 1 and len(next(iter(outs))) == 64


# ==== part 6: fulllead, first windows ==============================================================================
@pytest.fixture(scope="module")
def full():
    if not os.path.exists(FL):
        pytest.skip("no fulllead data")
    rws = sp.load_jsonl(FL)
    s = sp.build_space(rws)
    return SL.Slide(s, rows=rws)


def test_fulllead_first_pair_windows_merged_equality_trace_and_determinism(full):
    from verantyx.line3 import slide_place as SP
    spec = SP.make_spec(full)
    t = full.space.tiers["RUN"]
    pws = [p for p in SP.place_windows(full) if len(p.window.sids) == 2][:6]
    assert pws
    answered = 0
    for pw in pws:
        rec = SP.place_window(full, pw, spec)
        counts = full.counts(pw.window, "corpus")
        pack = full.pack(pw.window)
        units = [u for u, _ in rec.order_log]
        q = tuple(units[:2])
        evid = SR.counts_evidence(counts, "RUN")
        crosses = SR.window_crosses(rec, pack=pack)
        assert len(crosses) == rec.class_size
        for wc in crosses[:3]:
            assert SR.merged_check(wc, t, q).equal                                  # 7.3 on real window crosses
            r1 = SR.read_axes(wc, evid, t, q, full.spec.foundation)
            r2 = SR.read_axes(wc, evid, t, q, full.spec.foundation)
            assert r1.to_bytes() == r2.to_bytes()
            SR.check_trace(r1)
            assert len(r1.answers) + len(r1.abstentions) == 3
            answered += len(r1.answers)
            assert r1.axis("y").status == SR.NO_EDGES                               # S1: one tier
            for s in wc.seats:
                assert s.sid in pw.window.sids
        assert all(s.sources for s in crosses[0].seats)                                # the representative carries its provenance
