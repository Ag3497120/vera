"""G3-h tests (L-760..): the spec value z_deep "order_window" (owner, 「両方測ってから決める」 for the scope of the deeper z-arm edge count: the
corpus-wide pair count "order" (G3-c4) or the OTHER SENTENCE ONLY, count 1, direction only).  The default and "order" keep their bytes.

Part 1 (the spec): Z_DEEPS has three values; the default spec / counts / place spec keep their bytes; "order_window" has its own sha, text and
place spec sha; bad values raise.
Part 2 (the evidence): `WindowCounts.deep_z_window` -- n is 1 when the sentence both ends lie in holds both units (not the corpus count), omega the
direction inside that sentence; ends in different sentences, an end in both sentences with no sid, a unit outside the window, one unit twice:
no evidence; the verifier's own route (`window_order`, on the x rows) equals it for every ordered pair, arm and sid combination.
Part 3 (the placement): weights by arm code (< 6 equal under every rule), the record says rule "order_window" on the deeper z edges and equals
`deep_z_window`, the independent verifier accepts every member and its strict counts / keys equal the record's.
Part 4 (the ratios): the edge flow / binding / walk of a z arm read the same evidence by an independent route; a hand cross; check_trace.
Part 5 (regression): "order" and the default are byte-identical to the committed G3-c4 code (a digest computed with git HEAD e4706982).
Part 6: the window index and ask_slide take the value; PYTHONHASHSEED 0 / 1 / 12345 give identical bytes; no float."""
import itertools
import json
import os
import subprocess
import sys
from fractions import Fraction as Fr

import pytest

from verantyx.line3 import geometry as geo
from verantyx.line3 import slide as SL
from verantyx.line3 import slide_place as SP
from verantyx.line3 import slide_query as Q
from verantyx.line3 import slide_ratios as SR
from verantyx.line3 import space as sp
from test_slide_place4 import TOY, TOY_D, TOY_EQ, TOY_OLD, mk, pw_of, ref_z, rows_of, verify_all, z_edges

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PY = sys.executable

# digest of the "order" spec, counts, placements (4 toys x 3 growth / centre combinations, padding one) and ratios, computed with the committed
# code (git HEAD e4706982, before this ticket); the same program on the working tree gives the same value
ORDER_DIGEST = "53f589a985637dae5e88e55da78c4849f48f11bbe79db60160a4a68c2c291156"
DEEP_ARMS = ("+z", "-z")


@pytest.fixture(scope="module")
def s_slide():
    return mk(TOY, "slide")


@pytest.fixture(scope="module")
def s_order():
    return mk(TOY, "order")


@pytest.fixture(scope="module")
def s_win():
    return mk(TOY, "order_window")


# ==== part 1: the spec =================================================================================================
def test_z_deeps_and_the_spec_bytes(s_slide, s_order, s_win):
    assert SL.Z_DEEPS == ("slide", "order", "order_window") and Q.Z_DEEPS == SL.Z_DEEPS
    rows = rows_of(TOY)
    space = sp.build_space(rows)
    plain = SL.default_spec(space)
    assert plain.to_bytes() == s_slide.spec.to_bytes() and b"deep" not in plain.to_bytes()          # the default keeps its bytes
    assert s_win.spec.z_deep == "order_window" and dict(s_win.spec.axis("z").params)["deep"] == "order_window"
    assert len({plain.sha256(), s_order.spec.sha256(), s_win.spec.sha256()}) == 3
    t = s_win.spec.axis("z").text
    assert "z_deep=order_window" in t and "z_deep=order (G3-c4)" not in t and "n = 1" in t
    assert s_order.spec.axis("z").text != t
    assert SL.default_spec(space, z_tiers="same", z_deep="order_window").z_deep == "order_window"
    with pytest.raises(ValueError):
        SL.default_spec(space, z_deep="window")
    # the place specs follow the slide spec's sha; nothing else in them changes
    p = [SP.make_spec(s) for s in (s_slide, s_order, s_win)]
    assert len({x.sha256() for x in p}) == 3 and [x.slide_spec_sha for x in p] == [s.spec.sha256() for s in (s_slide, s_order, s_win)]
    assert p[2].doc() == dict(p[1].doc(), slide_spec_sha256=p[2].slide_spec_sha)
    with pytest.raises(ValueError):                                                 # a placement made for another slide spec is refused
        SP.place_window(s_win, pw_of(s_win, 0), p[1])


def test_the_counts_say_order_window_and_nothing_else_changes(s_slide, s_win):
    c0, c1 = s_slide.counts(pw_of(s_slide, 0).window, "corpus"), s_win.counts(pw_of(s_win, 0).window, "corpus")
    d0, d1 = c0.doc(), c1.doc()
    assert "z_deep" not in d0 and d1.pop("z_deep") == "order_window" and d0 == d1


# ==== part 2: the evidence =============================================================================================
def counts_of(slide, n=0, scope="corpus"):
    return slide.counts(pw_of(slide, n).window, scope)


@pytest.mark.parametrize("scope", SL.SCOPES)
def test_deep_z_window_counts_one_sentence_and_reads_its_direction(s_win, scope):
    c = counts_of(s_win, 0, scope)
    s0, s1 = c.window.sids
    assert (s0, s1) == (0, 1)
    # 猫 魚 鳥 stand in this order in sentence 1 (and in sentence 2, outside the window): n is 1, not the corpus count 2
    assert c.deep_z_window("RUN", "+z", "猫", "魚")[:2] == (1, 1) and c.deep_z_window("RUN", "-z", "猫", "魚")[:2] == (1, 0)
    assert c.deep_z_window("RUN", "+z", "魚", "猫")[:2] == (1, 0) and c.deep_z_window("RUN", "-z", "魚", "猫")[:2] == (1, 1)
    assert c.deep_z_window("RUN", "+z", "鳥", "猫")[:2] == (1, 0) and c.deep_z_window("RUN", "-z", "鳥", "猫")[:2] == (1, 1)
    # the row is the x row of that sentence (first occurrences)
    n, om, rows = c.deep_z_window("RUN", "+z", "猫", "魚")
    assert len(rows) == 1 and rows[0][0] == s1 and rows[0] in c.x[("RUN", "猫", "魚")][0]
    # a unit of both sentences read with a sid of its own: 犬 走 in sentence 0 (犬 before 走)
    assert c.deep_z_window("RUN", "+z", "犬", "走", s0, s0)[:2] == (1, 1) and c.deep_z_window("RUN", "-z", "犬", "走", s0, s0)[:2] == (1, 0)
    assert c.deep_z_window("RUN", "+z", "走", "犬", s0, s0)[:2] == (1, 0)
    # ends in different sentences, or a unit of both sentences with no sid, or a unit outside the window, or one unit twice: no evidence
    assert c.deep_z_window("RUN", "+z", "犬", "走", s0, s1) == (0, 0, ())
    assert c.deep_z_window("RUN", "+z", "犬", "猫") == (0, 0, ())                      # 犬 only in sentence 0, 猫 only in sentence 1
    assert c.deep_z_window("RUN", "+z", "走", "猫") == (0, 0, ())                      # 走 lies in both sentences and has no sid of its own
    assert c.deep_z_window("RUN", "+z", "猫", "追う") == (0, 0, ())                    # outside the window
    assert c.deep_z_window("RUN", "+z", "猫", "猫") == (0, 0, ())
    assert c.deep_z_window("RUN", "+z", "猫", "魚", 99, 99) == (0, 0, ())            # a sid that is not a sentence of the window
    # a pair that is not in the one sentence of the window is not evidence even where the corpus has it (犬 鳥 are together in sentence 3)
    assert c.deep_z_window("RUN", "+z", "犬", "鳥") == (0, 0, ())
    with pytest.raises(ValueError):
        c.deep_z_window("RUN", "+x", "猫", "魚")


def test_the_corpus_pair_count_is_not_the_window_count(s_order, s_win):
    co, cw = counts_of(s_order), counts_of(s_win)
    assert co.deep_z("RUN", "+z", "猫", "魚")[:2] == (2, 2)                         # G3-c4's "order": both sentences of the corpus
    assert cw.deep_z_window("RUN", "+z", "猫", "魚")[:2] == (1, 1)                  # G3-h: the sentence of the window only
    assert cw.deep_z_window("RUN", "+z", "鳥", "猫")[:2] == (1, 0) and co.deep_z("RUN", "+z", "鳥", "猫")[:2] == (2, 0)


def test_the_verifier_route_equals_the_search_route_for_every_pair_arm_and_sid(s_win):
    for toy in (TOY, TOY_EQ, TOY_D, TOY_OLD):
        sl = mk(toy, "order_window")
        for pw in SP.place_windows(sl, "one"):
            c = sl.counts(pw.window, "corpus")
            units = sorted({u for (t, u) in c.z_side if t == "RUN"})
            for o, i in itertools.permutations(units, 2):
                for arm in DEEP_ARMS:
                    for so, si in itertools.product((None,) + tuple(pw.window.sids) + (99,), repeat=2):
                        n, om, _ = c.deep_z_window("RUN", arm, o, i, so, si)
                        assert SP.window_order(c, "RUN", arm, o, i, so, si) == (n, om), (pw.window.sids, o, i, arm, so, si)
                        assert n in (0, 1) and om <= n
            assert SP.window_order(c, "RUN", "+z", "x", "x", None, None) == (0, 0)


# ==== part 3: the placement ============================================================================================
def test_weights_from_counts_differ_only_on_the_deeper_z_edges(s_slide, s_order, s_win):
    pw = pw_of(s_win, 0)
    cs = [counts_of(s, 0) for s in (s_slide, s_order, s_win)]
    ws = [SP.ArmWeights.from_counts(c, "RUN") for c in cs]
    assert [w.deep for w in ws] == [False, True, True]
    units = sorted({u for (t, u) in cs[2].z_side if t == "RUN"})
    for o, i in itertools.permutations(units, 2):
        for arm in range(6):                                                         # the arms and the innermost edges: equal under all rules
            assert ws[0](arm, o, i) == ws[1](arm, o, i) == ws[2](arm, o, i)
        for k, arm in ((SP.DEEP_Z + 4, "+z"), (SP.DEEP_Z + 5, "-z")):
            assert SP.ARM_NAMES[k - SP.DEEP_Z] == arm
            n, om, _ = cs[2].deep_z_window("RUN", arm, o, i)
            assert ws[2](k, o, i) == (n, om)
    # a token with a sid of its own: 犬 走 (sid 0) is an edge inside sentence 0
    S = SP.SEP
    assert SP.sid_of("走" + S + "0") == 0 and SP.sid_of("走") is None and SP.unit_of("走" + S + "0") == "走"
    assert ws[2](SP.DEEP_Z + 4, "犬", "走" + S + "0") == (1, 1) and ws[2](SP.DEEP_Z + 4, "犬", "走" + S + "1") == (0, 0)
    assert ws[2](SP.DEEP_Z + 4, "犬", "走") == (0, 0) and ws[2](SP.DEEP_Z + 5, "犬", "走" + S + "0") == (1, 0)


@pytest.mark.parametrize("centre_scope", ["n", "both"])
def test_the_record_says_order_window_on_the_deeper_z_edges_and_equals_the_evidence(s_win, centre_scope):
    pw = pw_of(s_win, 0)
    p = SP.place_window(s_win, pw, SP.make_spec(s_win, centre_scope=centre_scope))
    c = s_win.counts(pw.window, "corpus")
    assert p.z_deep == "order_window" and p.doc()["z_deep"] == "order_window"
    deeper = [(a, d, r) for a, d, r in z_edges(p) if d >= 2]
    inner = [(a, d, r) for a, d, r in z_edges(p) if d == 1]
    assert deeper and inner
    for a, d, r in deeper:
        e = r["sources"]["edge"]
        assert e["rule"] == "order_window" and e["axis"] == "z" and e["arm"] == a and e["n"] in (0, 1) and e["omega"] <= e["n"]
        tok = next(row["token"] for row in p.seats if row["unit"] == e["with"]["unit"] and row["sid"] == e["with"]["sid"])
        n, om, src = c.deep_z_window("RUN", a, r["unit"], e["with"]["unit"], SP.sid_of(r["token"]), SP.sid_of(tok))
        assert (e["n"], e["omega"], e["sources"]) == (n, om, [list(t) for t in src]) and len(e["sources"]) == e["n"]
        if e["n"]:
            assert e["sources"][0][0] == r["sid"] == e["with"]["sid"]                  # the one sentence both ends lie in
    for a, d, r in inner:                                                            # the innermost z edge stays the slide edge
        e = r["sources"]["edge"]
        assert e["rule"] == "slide" and e["n"] == e["omega"]
    assert all("rule" not in r["sources"]["edge"] for r in p.seats if r["arm"][1:] != "z" and r["sources"]["edge"] is not None)
    assert sum(e["sources"]["edge"]["n"] for _, _, e in deeper) >= 1                  # the toy has deeper edges with evidence


@pytest.mark.parametrize("toy", [TOY, TOY_EQ, TOY_D, TOY_OLD])
@pytest.mark.parametrize("growth,centre_scope,seat_key", [("z_reserved", "both", "unit_sid"), ("z_reserved", "n", "unit_sid"),
                                                           ("n_then_n1", "n", "unit_sid"), ("z_reserved", "n", "unit"), ("n_then_n1", "n", "unit")])
def test_the_independent_verifier_accepts_every_member_under_order_window(toy, growth, centre_scope, seat_key):
    sl = mk(toy, "order_window")
    spec = SP.make_spec(sl, growth=growth, centre_scope=centre_scope, seat_key=seat_key)
    n_deep = n_ev = 0
    for pw in SP.place_windows(sl, "one"):
        p = SP.place_window(sl, pw, spec)
        rep, frep = verify_all(sl, pw, p, spec)
        assert rep.is_stable_class and rep.members_checked == p.class_size, (pw.window.sids, rep)
        assert dict(frep.axis_improvable) == p.improving_moves_left and frep.strictly_stable == p.stable_strict
        wfn = SP.counts_weight_fn(sl.counts(pw.window, spec.scope), spec.tier)
        assert wfn.z_deep
        tot, per = SP.cross_key(wfn, p.cross)
        assert {a: list(per[a]) for a in SL.AXES} == p.axis_keys and tuple(tot) == p.key       # the record's key = the verifier's
        deeper = [(a, d, r) for a, d, r in z_edges(p) if d >= 2]
        n_deep += len(deeper)
        n_ev += sum(r["sources"]["edge"]["n"] for _, _, r in deeper)
    if toy is TOY and growth == "z_reserved":
        assert n_deep > 0 and (n_ev > 0 or seat_key == "unit")


def test_a_verifier_that_reads_the_corpus_count_disagrees_somewhere(s_win, s_order):
    """The verifier of the other rule reads another z key on at least one window of the toy (the rules differ: n 1 vs the corpus count)."""
    spec = SP.make_spec(s_win, centre_scope="n")
    seen = False
    for pw in SP.place_windows(s_win, "one"):
        p = SP.place_window(s_win, pw, spec)
        good = SP.counts_weight_fn(s_win.counts(pw.window, "corpus"), "RUN")
        other = SP.counts_weight_fn(s_order.counts(pw.window, "corpus"), "RUN")
        g, _ = SP.cross_key(good, p.cross)
        o, _ = SP.cross_key(other, p.cross)
        seen = seen or g != o
    assert seen


def test_deeper_evidence_never_exceeds_the_corpus_reading(s_order, s_win):
    for toy in (TOY, TOY_EQ, TOY_D, TOY_OLD):
        so, sw = mk(toy, "order"), mk(toy, "order_window")
        for pw in SP.place_windows(sw, "one"):
            co, cw = so.counts(pw.window, "corpus"), sw.counts(pw.window, "corpus")
            units = sorted({u for (t, u) in cw.z_side if t == "RUN"})
            for o, i in itertools.permutations(units, 2):
                for arm in DEEP_ARMS:
                    for sid in pw.window.sids:
                        n, om, _ = cw.deep_z_window("RUN", arm, o, i, sid, sid)
                        no, omo, _ = co.deep_z("RUN", arm, o, i)
                        assert n <= no and om <= omo and (n == 0 or no >= 1)


# ==== part 4: the ratios ===============================================================================================
def test_ratios_read_the_same_per_edge_evidence_as_the_placement(s_win, s_order):
    spec = SP.make_spec(s_win, centre_scope="n")
    pw = pw_of(s_win, 0)
    p = SP.place_window(s_win, pw, spec)
    wc = SR.window_cross(p.doc())
    tier = s_win.space.tiers["RUN"]
    fnd = s_win.spec.foundation
    c = s_win.counts(pw.window, "corpus")
    ev = SR.counts_evidence(c, "RUN")
    assert hasattr(ev, "deep") and ev.deep_sids and not hasattr(SR.counts_evidence(s_order.counts(pw.window, "corpus"), "RUN"), "deep_sids")
    q = ("魚", "鳥")
    w = SR.foundation_weights(fnd)
    r = SR.read_axes(wc, ev, tier, q, fnd)
    qe = tuple(sorted(set(SR.cy.make_context(q).energy_units)))
    by = wc.by_seat()

    F, B = ref_z_sids(wc, c, ev, tier, qe, w)
    assert dict(r.axis("z").edge_flow) == F and dict(r.axis("z").binding) == B
    centre_key = by[geo.CENTER].key
    for sec in r.axis("z").sections:
        for wk in sec.walks:
            for st in wk.steps:
                assert (st.rule == "order_window") == (st.to != centre_key) and st.n in (0, 1)
                if st.rule == "order_window":
                    assert st.n == 1 and all(row[0] == "order_window" and row[1] == st.frm[1] == st.to[1] for row in st.sources)
    assert all(t.rule in ("slide", "order_window") for a in r.answers for t in a.edges)
    SR.check_trace(r)
    ro = SR.read_axes(wc, SR.counts_evidence(s_order.counts(pw.window, "corpus"), "RUN"), tier, q, fnd)
    for a in ("x", "y"):
        assert r.axis(a).doc() == ro.axis(a).doc()                              # only the z axis reads the rule
    assert len(r.sha256()) == 64


def ref_z_sids(wc, counts, ev, tier, q, w):
    """F_z, B_z by an independent route over geometry.neighbours (as test_slide_place4.ref_z) with the order_window evidence read from the
    counts and the seats' sids."""
    from verantyx.line3 import energy as en
    by = wc.by_seat()
    F = {u: Fr(0) for u in wc.units()}
    B = {u: Fr(0) for u in wc.units()}
    for s, rec in by.items():
        for nb in geo.neighbours(s, wc.L):
            if nb not in by or by[nb].unit == rec.unit:
                continue
            o = by[nb]
            outer, inner = (s, nb) if s != geo.CENTER and (nb == geo.CENTER or nb.k == s.k + 1) else (nb, s)
            arm = outer.arm
            if arm[1] != "z":
                continue
            if inner != geo.CENTER:
                n = counts.deep_z_window("RUN", arm, by[outer].unit, by[inner].unit, by[outer].sid, by[inner].sid)[0]
            else:
                n = ev(arm, by[outer].unit, by[inner].unit)[0]
            if n <= 0:
                continue
            nu, nv = len(tier.postings[o.unit]), len(tier.postings[rec.unit])
            F[rec.unit] += w[arm] * en.energy(tier, o.unit, q) * Fr(n, nu)
            B[rec.unit] += w[arm] * Fr(n, nv)
    return F, B


def hand_cross():
    """centre 魚 (sid 1); +z arm of length 2: 猫 (outer, sid 1) then 鳥 (sid 1, next to the centre); -x: 走 (sid 1).  A second cross puts the
    outer unit in the other sentence."""
    def S(u, sid, arm, pos=0):
        return SR.SeatRec(u, sid, arm, pos)

    def build(sid_outer):
        seats = [S("魚", 1, "center"), S("走", 1, "-x", 1), S("猫", sid_outer, "+z", 0), S("鳥", 1, "+z", 1)]
        order = {s: i for i, s in enumerate(geo.seats(2))}
        return SR.WindowCross(2, tuple(sorted(seats, key=lambda s: order[s.seat])), "RUN", (0, 1))
    return build(1), build(0)


def test_the_walk_of_a_z_arm_over_a_deeper_edge_needs_one_sentence(s_win):
    tier = s_win.space.tiers["RUN"]
    fnd = s_win.spec.foundation
    c = counts_of(s_win, 0)
    ev = SR.counts_evidence(c, "RUN")
    same, other = hand_cross()                                                    # 猫 鳥 both sid 1; 猫 sid 0 / 鳥 sid 1
    q = ("魚",)
    r_same = SR.read_axes(same, ev, tier, q, fnd)
    r_other = SR.read_axes(other, ev, tier, q, fnd)
    wk_same = next(w for s in r_same.axis("z").sections for w in s.walks if w.arm == "+z")
    wk_other = next(w for s in r_other.axis("z").sections for w in s.walks if w.arm == "+z")
    # 猫 before 鳥 in sentence 1: +z n 1; the innermost edge 鳥 - 魚 has n_z(鳥, 魚) = 0 in this window (both lie in sentence 1), so the walk stops there
    assert wk_same.steps and wk_same.steps[0].rule == "order_window" and wk_same.steps[0].n == 1 and wk_same.steps[0].frm == ("猫", 1)
    assert wk_same.steps[0].sources[0][0] == "order_window"
    assert wk_other.steps == () and wk_other.stop == "unproven"                   # the ends lie in different sentences: no evidence, no step
    z_same, z_other = r_same.axis("z"), r_other.axis("z")
    assert z_same.evidenced_edges == z_other.evidenced_edges + 1
    SR.check_trace(r_same)
    SR.check_trace(r_other)


def test_window_rows_are_tagged_and_not_cited_by_the_query_layer(s_win):
    """The rows of an order_window edge carry the tag ("order_window", sid, ...): slide_query's _sids_of reads x / z rows only, so (as for "order", G3-c4
    open point 6) a deeper edge's sentence is not added to `source_sids` by its row (the seats' own sids are)."""
    pw = pw_of(s_win, 0)
    p = SP.place_window(s_win, pw, SP.make_spec(s_win, centre_scope="n"))
    ev = SR.counts_evidence(s_win.counts(pw.window, "corpus"), "RUN")
    n, rows = ev.deep("+z", "猫", "魚", 1, 1)
    assert n == 1 and rows and rows[0][0] == "order_window" and rows[0][1] == 1
    assert Q._row_sids("x", rows[0]) == () and Q._row_sids("z", rows[0]) == ()
    fake = type("A", (), {"seats": (), "sources": (rows[0],)})()
    assert Q._sids_of(fake) == ()
    assert p.z_deep == "order_window"


# ==== part 5: regression ===============================================================================================
def test_order_and_slide_keep_the_bytes_of_the_committed_code():
    import hashlib
    h = hashlib.sha256()
    for toy in (TOY, TOY_EQ, TOY_D, TOY_OLD):
        sl = mk(toy, "order")
        h.update(sl.spec.to_bytes())
        for cs, gr in (("n", "z_reserved"), ("both", "z_reserved"), ("n", "n_then_n1")):
            spec = SP.make_spec(sl, centre_scope=cs, growth=gr)
            h.update(spec.to_bytes())
            for pw in SP.place_windows(sl, "one"):
                p = SP.place_window(sl, pw, spec)
                h.update(p.to_bytes())
                h.update(sl.counts(pw.window, "corpus").to_bytes())
                if len(pw.window.sids) == 2:
                    ev = SR.counts_evidence(sl.counts(pw.window, "corpus"), "RUN")
                    for ag in SR.AGREEMENTS:
                        h.update(SR.read_axes(SR.window_cross(p.doc()), ev, sl.space.tiers["RUN"], ("魚", "鳥"), sl.spec.foundation, agreement=ag).to_bytes())
    assert h.hexdigest() == ORDER_DIGEST
    # the default (G3-c4's test_slide_place4 pins it against the committed G3-c3 records); here: no trace of the new rule in its documents
    sl = mk(TOY, "slide")
    pw = pw_of(sl, 0)
    p = SP.place_window(sl, pw, SP.make_spec(sl))
    assert b"order_window" not in p.to_bytes() and b"order_window" not in sl.counts(pw.window, "corpus").to_bytes() and b"deep" not in sl.spec.to_bytes()


# ==== part 6: through the window index, hash seeds, floats ==============================================================
def test_the_window_index_and_ask_take_the_value(tmp_path):
    rows = rows_of(TOY + [("E", "猫が魚を食べる。"), ("E", "魚が泳ぐ。")])
    space = sp.build_space(rows)
    d = str(tmp_path)
    a = Q.WindowIndex.from_space(space, d, rows=rows, level="low", z_deep="order")
    b = Q.WindowIndex.from_space(space, d, rows=rows, level="low", z_deep="order_window")
    assert a.z_deep == "order" and b.z_deep == "order_window" and a.slide.spec.sha256() != b.slide.spec.sha256()
    assert len(os.listdir(d)) == 2 and b.header["z_deep"] == "order_window"
    b2 = Q.WindowIndex.from_space(space, d, rows=rows, level="low", z_deep="order_window", build=False)
    assert [w.doc for w in b2.windows] == [w.doc for w in b.windows]
    for w in b.windows:
        assert w.doc.get("z_deep", "order_window") == "order_window"
    r = Q.ask_slide(b, "猫が魚を食べるのは何ですか")
    assert r.config["z_deep"] == "order_window"
    with pytest.raises(ValueError, match="z_deep"):
        Q.ask_slide(b, "猫が魚を食べるのは何ですか", z_deep="order")
    with pytest.raises(ValueError, match="z_deep"):
        Q.ask_slide(a, "猫が魚を食べるのは何ですか", z_deep="order_window")


def test_bytes_are_identical_under_three_hash_seeds_for_order_window():
    prog = (
        "import hashlib,itertools\n"
        "from verantyx.line3 import slide as SL, slide_place as SP, slide_ratios as SR, space as sp\n"
        "T=[('A','犬が走る。'),('A','猫と魚と鳥が走る。'),('B','猫と魚と鳥が泳ぐ。'),('B','犬が鳥を追う。'),('C','星が光る。'),('C','星と月と雲と空が光る。'),('D','京都は古い都である。')]\n"
        "seen={};rows=[]\n"
        "for t,s in T:\n i=seen.get(t,0);seen[t]=i+1;rows.append({'title':t,'sent':s,'source':'%s#%d'%(t,i)})\n"
        "S=sp.build_space(rows);h=hashlib.sha256()\n"
        "sl=SL.Slide(S,SL.default_spec(S,z_deep='order_window'),rows=rows);h.update(sl.spec.to_bytes())\n"
        "for cs,gr,sk,ac,se in itertools.product(SP.CENTRE_SCOPES,('n_then_n1','z_reserved'),SP.SEAT_KEYS,('budget','x'),('allow','deny')):\n"
        " if ac=='x' and gr!='z_reserved': continue\n"
        " if cs=='both' and gr!='z_reserved': continue\n"
        " spec=SP.make_spec(sl,centre_scope=cs,growth=gr,seat_key=sk,arm_cap=ac,seat_empty_axis=se);h.update(spec.to_bytes())\n"
        " for pw in SP.place_windows(sl,'one'):\n"
        "  p=SP.place_window(sl,pw,spec);h.update(p.to_bytes())\n"
        "  if len(pw.window.sids)==2:\n"
        "   ev=SR.counts_evidence(sl.counts(pw.window,'corpus'),'RUN');t=S.tiers['RUN']\n"
        "   for ag in SR.AGREEMENTS:\n"
        "    h.update(SR.read_axes(SR.window_cross(p.doc()),ev,t,('魚','鳥'),sl.spec.foundation,agreement=ag).to_bytes())\n"
        "print(h.hexdigest())")
    outs = set()
    for seed in ("0", "1", "12345"):
        out = subprocess.run([PY, "-c", prog], cwd=ROOT, env=dict(os.environ, PYTHONPATH=ROOT, PYTHONHASHSEED=seed), capture_output=True, text=True)
        assert out.returncode == 0, out.stderr
        outs.add(out.stdout.strip())
    assert len(outs) == 1 and len(next(iter(outs))) == 64


def test_no_float_in_the_g3h_records_counts_and_ratios(s_win):
    def hook(s):
        raise AssertionError("a float: %s" % s)
    json.loads(s_win.spec.to_bytes().decode("utf-8"), parse_float=hook)
    for cs in SP.CENTRE_SCOPES:
        spec = SP.make_spec(s_win, centre_scope=cs)
        json.loads(spec.to_bytes().decode("utf-8"), parse_float=hook)
        for pw in SP.place_windows(s_win, "one"):
            p = SP.place_window(s_win, pw, spec)
            json.loads(p.to_bytes().decode("utf-8"), parse_float=hook)
            json.loads(s_win.counts(pw.window, "corpus").to_bytes().decode("utf-8"), parse_float=hook)
            if len(pw.window.sids) == 2:
                ev = SR.counts_evidence(s_win.counts(pw.window, "corpus"), "RUN")
                r = SR.read_axes(SR.window_cross(p.doc()), ev, s_win.space.tiers["RUN"], ("魚", "鳥"), s_win.spec.foundation)
                json.loads(r.to_bytes().decode("utf-8"), parse_float=hook)
