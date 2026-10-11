"""LOOM-c tests: the emit gate and stability under Vera's own full key (n, p, a) (docs/LINE3_LOOM_DESIGN.md 3.7;
owner OP-LOOM-1 (a) 「完全な鍵 (n,p,a)」; T-LOOM-13..16).

A woven cross has to be a fixed point of placement.seated_key before it can be emitted.  The refusal lists every improving swap and names the
best one.  The key is checked here against code that does not share the loom's move loop: placement.seated_key on a hand-built geometry.Cross,
and placement.verify_class_foundation.
"""
import pytest

from verantyx.line3 import foundation as fd
from verantyx.line3 import geometry as geo
from verantyx.line3 import placement as pl
from verantyx.loom import read as rd
from verantyx.loom.corpus import Corpus
from loom_common import CORPUS, TOY, server, task, weaver

SPEC = fd.DEFAULT_SPEC
ARM_A = {"+x": 2880, "-x": 89, "+y": 110, "-y": 34, "+z": 0, "-z": 13}       # the adhesion of 日本 with the particle of each arm (O, design 2)


@pytest.fixture(scope="module")
def corpus():
    return Corpus.load(open(CORPUS, "rb").read())


def hand_cross(L, centre, arms):
    cells = [[None] * L for _ in range(6)]
    for i, p in enumerate(SPEC.arms):
        cells[i][L - 1] = fd.token(p)
    for (ax, k), v in arms.items():
        cells[geo.AXES.index(ax)][k] = v
    return geo.Cross.make(L=L, center=centre, arms=cells)


def seat_name(s):
    return "centre" if s == geo.CENTER else "%s:%d" % (s.arm, s.k)


def oracle(corpus, tier, gc):
    """(key, improving) of a hand-built seated cross: every swap of two data seats, the moves of verify_class_foundation."""
    T, A, w = corpus.tier(tier), corpus.adhesion[tier], pl.Weights(corpus.tier(tier))
    base = pl.seated_key(T, A, gc, w)
    imp = []
    for p, q in geo.moves_swap(gc.L):
        vp, vq = gc.get(p), gc.get(q)
        if fd.is_constructed(vp) or fd.is_constructed(vq) or vp == vq:
            continue
        g2 = geo.swap(gc, p, q)
        if g2.center is None:
            continue
        k2 = pl.seated_key(T, A, g2, w)
        if k2 > base:
            imp.append([seat_name(p), seat_name(q), list(k2)])
    return base, imp


def two(tmp_path, arm, stability="strict_npa", centre="首都", other="日本", task_id="demo/tokyo_ca", L=2, k=0):
    srv = server(tmp_path, stability)
    w = weaver(srv, task_id)
    u_o = w.call("add", text=other, kind="record", tier="WORD")["uid"]
    u_c = w.call("add", text=centre, kind="record", tier="WORD")["uid"]
    c = w.call("open_cross", tier="WORD", L=L)["cid"]
    w.call("seat", cid=c, seat="centre", uid=u_c)
    w.call("seat", cid=c, seat="%s:%d" % (arm, k), uid=u_o)
    w.call("link", cid=c)
    return srv, w, c, u_o, u_c


# ---------------------------------------------------------------------------------------------------------------
# the worked cross: (2, 2, 2880)
# ---------------------------------------------------------------------------------------------------------------
def test_the_key_of_the_worked_cross_is_2_2_2880_on_independent_code(tmp_path, corpus):
    srv, w, c, *_ = two(tmp_path, "+x")
    r = w.call("read")
    e = r["stability"][0]
    assert e["key"] == [2, 2, 2880] and e["status"] == "stable" and e["improving"] == []
    gc = hand_cross(2, "首都", {("+x", 0): "日本"})
    assert pl.seated_key(corpus.tier("WORD"), corpus.adhesion["WORD"], gc) == (2, 2, 2880)
    assert oracle(corpus, "WORD", gc) == ((2, 2, 2880), [])
    assert r["refusals"] == [] and r["text"] == "日本の首都"


@pytest.mark.parametrize("arm", ["+x", "-x", "+y", "-y", "+z", "-z"])
def test_nihon_on_every_arm_matches_the_independent_oracle(tmp_path, corpus, arm):
    srv, w, c, *_ = two(tmp_path, arm)
    e = w.call("read")["stability"][0]
    gc = hand_cross(2, "首都", {(arm, 0): "日本"})
    base, imp = oracle(corpus, "WORD", gc)
    assert e["key"] == list(base) == [2, 2, ARM_A[arm]]
    assert e["improving"] == imp                                                  # the same swaps, the same keys, in moves_swap order
    assert e["status"] == ("stable" if arm == "+x" else "unstable")
    rep = pl.verify_class_foundation(corpus.tier("WORD"), [gc], corpus.adhesion["WORD"])
    assert (not imp) == rep.members_fixed_points and rep.key == base               # T-LOOM-15: the same fixed-point verdict


def test_nihon_on_the_ga_arm_is_refused_with_the_witness_that_moves_it_to_no(tmp_path):
    """The design's example: 「日本が首都」 is refused at emit; the witness is the move to +x:0 (a 13 -> 2880)."""
    srv, w, c, *_ = two(tmp_path, "-z")
    r = w.call("emit")
    assert r["ok"] is False and r["refusal"] == "unstable_cross"
    refs = r["detail"]["refusals"]
    assert [x["type"] for x in refs] == ["unstable_cross"]
    ref = refs[0]
    assert ref["cid"] == c and ref["key"] == [2, 2, 13] and ref["mode"] == "strict_npa"
    assert ref["improving"] == [["+x:0", "-z:0", [2, 2, 2880]], ["-x:0", "-z:0", [2, 2, 89]], ["+y:0", "-z:0", [2, 2, 110]], ["-y:0", "-z:0", [2, 2, 34]]]
    assert ref["best_key"] == [2, 2, 2880] and ref["best_swaps"] == [["+x:0", "-z:0"]]
    assert srv.closed(w.run_id) is None                                          # the run continues
    assert w.call("status")["counters"]["emit_attempts"] == 1


def test_the_named_swap_fixes_it_and_the_run_then_emits(tmp_path):
    srv, w, c, *_ = two(tmp_path, "-z")
    sa, sb = w.call("emit")["detail"]["refusals"][0]["best_swaps"][0]
    assert w.call("swap", cid=c, seat_a=sa, seat_b=sb)["ok"]
    r = w.call("emit")
    assert r["ok"] and r["text"] == "日本の首都" and r["stability"][0]["key"] == [2, 2, 2880]
    assert srv.closed(w.run_id)[0] == "emitted"


def test_the_wrong_word_order_is_refused_too(tmp_path, corpus):
    """首都 on the の arm and 日本 at the centre reads 「首都の日本」: p(首都, 日本) = 0, and the swap back raises the key."""
    srv, w, c, *_ = two(tmp_path, "+x", centre="日本", other="首都")
    r = w.call("emit")
    ref = r["detail"]["refusals"][0]
    assert r["refusal"] == "unstable_cross" and ref["key"][:2] == [2, 0]
    assert ["centre", "+x:0", [2, 2, 2880]] in ref["improving"]                      # the swap back reads 「日本の首都」
    gc = hand_cross(2, "日本", {("+x", 0): "首都"})
    assert ref["improving"] == oracle(corpus, "WORD", gc)[1]
    assert not pl.verify_class_foundation(corpus.tier("WORD"), [gc], corpus.adhesion["WORD"]).members_fixed_points


def test_a_cross_is_stable_exactly_when_the_oracle_finds_no_improving_swap(tmp_path, corpus):
    """T-LOOM-15 over many small crosses: every placement of two units on L = 2 and L = 3 crosses."""
    pairs = [("日本", "首都"), ("東京", "日本"), ("首都", "東京")]
    n_checked = 0
    for (a, b), L in ((p, L) for p in pairs for L in (2, 3)):
        seats = ["centre"] + ["%s:0" % ax for ax in geo.AXES]
        for sa in seats:
            for sb in seats:
                if sa == sb:
                    continue
                srv = server(tmp_path / ("%s%s%d%s%s" % (a, b, L, sa, sb)).replace(":", "_").replace("+", "p").replace("-", "m"))
                w = weaver(srv, "demo/tokyo_ca")
                ua = w.call("add", text=a, kind="record", tier="WORD")["uid"]
                ub = w.call("add", text=b, kind="record", tier="WORD")["uid"]
                c = w.call("open_cross", tier="WORD", L=L)["cid"]
                k = L - 2
                name = lambda s: s if s == "centre" else "%s:%d" % (s.split(":")[0], k)
                w.call("seat", cid=c, seat=name(sa), uid=ua)
                w.call("seat", cid=c, seat=name(sb), uid=ub)
                w.call("link", cid=c)
                r = w.call("read")
                cells = {}
                for sname, surf in ((name(sa), a), (name(sb), b)):
                    cells[sname] = surf
                centre = cells.pop("centre", None)
                gc = hand_cross(L, centre, {(s.split(":")[0], int(s.split(":")[1])): v for s, v in cells.items()})
                rep = pl.verify_class_foundation(corpus.tier("WORD"), [gc], corpus.adhesion["WORD"])
                refs = [x["type"] for x in r["refusals"]]
                if centre is None:
                    assert refs[:1] == ["empty_centre"]
                    continue
                stable = "unstable_cross" not in refs
                assert stable == rep.members_fixed_points, (a, b, L, sa, sb)
                assert r["stability"][0]["key"] == list(rep.key)
                n_checked += 1
    assert n_checked > 60


# ---------------------------------------------------------------------------------------------------------------
# the switch for the owner's answer
# ---------------------------------------------------------------------------------------------------------------
def test_strict_np_ignores_the_adhesion_and_report_never_refuses(tmp_path):
    srv, w, c, *_ = two(tmp_path / "np", "-z", stability="strict_np")
    r = w.call("emit")
    assert r["ok"] and r["text"] == "日本が首都" and r["stability"][0]["status"] == "stable"
    assert srv.runs[w.run_id].run.header()["stability_mode"] == "strict_np"
    srv2, w2, *_ = two(tmp_path / "rep", "-z", stability="report")
    r2 = w2.call("emit")
    assert r2["ok"] and r2["text"] == "日本が首都" and r2["stability"][0]["status"] == "unstable"          # reported, not a refusal
    srv3, w3, *_ = two(tmp_path / "np2", "+x", centre="日本", other="首都", stability="strict_np")
    assert w3.call("emit")["refusal"] == "unstable_cross"                                                  # (n, p) still decides the word order


def test_the_stability_mode_is_in_the_header_and_a_wrong_one_is_refused(tmp_path):
    srv = server(tmp_path, "strict_np")
    assert srv.begin("demo/tokyo_ca", "m", "r")["header"]["stability_mode"] == "strict_np"
    with pytest.raises(ValueError):
        server(tmp_path / "x", "loose")


# ---------------------------------------------------------------------------------------------------------------
# evidence: constructed units, trivially stable, no evidence
# ---------------------------------------------------------------------------------------------------------------
def test_single_unit_and_constructed_crosses_are_trivially_stable(tmp_path):
    srv = server(tmp_path)
    w = weaver(srv, "demo/tokyo_ca")
    u1 = w.call("add", text="東京", kind="record", tier="WORD")["uid"]
    u2 = w.call("add", text="です", kind="constructed")["uid"]
    u3 = w.call("add", text="Ωa", kind="constructed")["uid"]
    c1 = w.call("open_cross", tier="WORD", L=1)["cid"]
    c2 = w.call("open_cross", tier="WORD", L=1)["cid"]
    c3 = w.call("open_cross", tier="WORD", L=2)["cid"]
    w.call("seat", cid=c1, seat="centre", uid=u1)
    w.call("seat", cid=c2, seat="centre", uid=u2)
    w.call("seat", cid=c3, seat="centre", uid=u3)
    for c in (c1, c2, c3):
        w.call("link", cid=c)
    st = w.call("read")["stability"]
    assert [(e["status"], e["key"]) for e in st] == [("trivially_stable", [0, 0, 0])] * 3


def test_a_constructed_unit_contributes_nothing_to_the_key(tmp_path, corpus):
    srv = server(tmp_path)
    w = weaver(srv, "demo/tokyo_ca")
    u1 = w.call("add", text="日本", kind="record", tier="WORD")["uid"]
    u2 = w.call("add", text="です", kind="constructed")["uid"]
    c = w.call("open_cross", tier="WORD", L=2)["cid"]
    w.call("seat", cid=c, seat="+x:0", uid=u1)
    w.call("seat", cid=c, seat="centre", uid=u2)
    w.call("link", cid=c)
    e = w.call("read")["stability"][0]
    assert e["key"] == [0, 0, 2880] and e["status"] == "stable"                  # L-52: weight 0; only the adhesion of the record unit counts
    w.call("swap", cid=c, seat_a="+x:0", seat_b="-z:0")
    e = w.call("read")["stability"][0]
    assert e["key"] == [0, 0, 13] and e["status"] == "unstable" and e["best_swaps"] == [["+x:0", "-z:0"]]
    # a constructed unit is "\0C:uid" in the flat: never equal to another cell, never in the postings
    run = srv.runs[w.run_id].run
    gc = rd.geometry_cross(run.state, run.state.crosses[c])
    assert gc.center == rd.CONSTRUCTED_PREFIX + u2 and gc.arms[5][0] == "日本"


def test_two_instances_of_the_same_word_are_equal_cells_and_swap_is_a_noop(tmp_path):
    srv = server(tmp_path)
    w = weaver(srv, "demo/tokyo_ca")
    us = [w.call("add", text="日本", kind="record", tier="WORD")["uid"] for _ in range(2)]
    uc = w.call("add", text="首都", kind="record", tier="WORD")["uid"]
    c = w.call("open_cross", tier="WORD", L=2)["cid"]
    w.call("seat", cid=c, seat="centre", uid=uc)
    w.call("seat", cid=c, seat="+x:0", uid=us[0])
    w.call("seat", cid=c, seat="-x:0", uid=us[1])
    w.call("link", cid=c)
    e = w.call("read")["stability"][0]
    assert e["status"] in ("stable", "unstable")
    assert not any({i[0], i[1]} == {"+x:0", "-x:0"} for i in e["improving"])        # equal contents: not a move


def test_the_foundation_swaps_are_never_moves(tmp_path):
    srv, w, c, *_ = two(tmp_path, "-z", L=3, k=1)
    e = w.call("read")["stability"][0]
    seats = {s for i in e["improving"] for s in i[:2]}
    assert all(not s.endswith(":2") for s in seats)                              # k = L-1 is the foundation


# ---------------------------------------------------------------------------------------------------------------
# T-LOOM-16: the other refusals, alone and together
# ---------------------------------------------------------------------------------------------------------------
def types(r):
    return [x["type"] for x in r["detail"]["refusals"]] if r["ok"] is False else [x["type"] for x in r["refusals"]]


def test_empty_thread(tmp_path):
    w = weaver(server(tmp_path), "prose/ca")
    r = w.call("emit")
    assert r["refusal"] == "empty_thread" and types(r) == ["empty_thread"]
    c = w.call("open_cross", tier="WORD", L=1)["cid"]
    w.call("link", cid=c)
    assert types(w.call("emit")) == ["empty_thread"]                              # a linked cross that holds nothing


def test_empty_centre(tmp_path):
    srv = server(tmp_path)
    w = weaver(srv, "prose/ca")
    u = w.call("add", text="Ωa", kind="constructed")["uid"]
    c = w.call("open_cross", tier="WORD", L=2)["cid"]
    w.call("seat", cid=c, seat="+x:0", uid=u)
    w.call("link", cid=c)
    r = w.call("emit")
    assert types(r) == ["empty_centre"] and r["detail"]["refusals"][0]["cid"] == c
    assert r["detail"]["stability"][0]["status"] == "not_evaluated"
    w.call("unseat", cid=c, seat="+x:0")
    w.call("topic", cid=c, on=True)
    assert types(w.call("emit")) == ["empty_centre"]                              # は with nothing to attach to


def test_leg_gap(tmp_path):
    srv = server(tmp_path)
    w = weaver(srv, "prose/ca")
    us = [w.call("add", text=t, kind="constructed")["uid"] for t in TOY[:2]]
    c = w.call("open_cross", tier="WORD", L=4)["cid"]
    w.call("seat", cid=c, seat="centre", uid=us[0])
    w.call("seat", cid=c, seat="+x:0", uid=us[1])                                  # the innermost data seat is +x:2: a gap
    w.call("link", cid=c)
    r = w.call("emit")
    assert types(r) == ["leg_gap"] and r["detail"]["refusals"][0]["arm"] == "+x" and r["detail"]["refusals"][0]["seats"] == ["+x:0"]
    w.call("swap", cid=c, seat_a="+x:0", seat_b="+x:2")
    assert w.call("emit")["ok"]
    # a hole in the middle is a gap too
    w2 = weaver(server(tmp_path / "w2"), "prose/ca")
    us = [w2.call("add", text=t, kind="constructed")["uid"] for t in TOY[:3]]
    c = w2.call("open_cross", tier="WORD", L=4)["cid"]
    w2.call("seat", cid=c, seat="centre", uid=us[0])
    w2.call("seat", cid=c, seat="+x:0", uid=us[1])
    w2.call("seat", cid=c, seat="+x:2", uid=us[2])
    w2.call("link", cid=c)
    assert types(w2.call("emit")) == ["leg_gap"]


def test_unlinked_cross_and_tier_mix(tmp_path):
    srv = server(tmp_path)
    w = weaver(srv, "prose/ca")
    us = [w.call("add", text=t, kind="constructed")["uid"] for t in TOY[:3]]
    cs = [w.call("open_cross", tier=t, L=1)["cid"] for t in ("WORD", "RUN", "WORD")]
    for c, u in zip(cs, us):
        w.call("seat", cid=c, seat="centre", uid=u)
    w.call("link", cid=cs[0])
    r = w.call("emit")
    assert types(r) == ["unlinked_cross", "unlinked_cross"] and [x["cid"] for x in r["detail"]["refusals"]] == [cs[1], cs[2]]
    w.call("link", cid=cs[1])
    r = w.call("emit")
    assert types(r) == ["unlinked_cross", "tier_mix"]
    assert r["detail"]["refusals"][1]["tiers"] == {cs[0]: "WORD", cs[1]: "RUN"}


def test_several_refusals_at_once_are_all_reported_in_the_fixed_order(tmp_path):
    srv = server(tmp_path)
    w = weaver(srv, "prose/ca")
    j = w.call("add", text="日本", kind="record", tier="WORD")["uid"]
    h = w.call("add", text="首都", kind="record", tier="WORD")["uid"]
    o = w.call("add", text="Ωa", kind="constructed")["uid"]
    o2 = w.call("add", text="Ωb", kind="constructed")["uid"]
    c_bad = w.call("open_cross", tier="WORD", L=2)["cid"]                           # unstable: 日本 on が
    w.call("seat", cid=c_bad, seat="centre", uid=h)
    w.call("seat", cid=c_bad, seat="-z:0", uid=j)
    c_nc = w.call("open_cross", tier="RUN", L=2)["cid"]                             # empty centre + tier mix
    w.call("seat", cid=c_nc, seat="+x:0", uid=o)
    c_free = w.call("open_cross", tier="WORD", L=1)["cid"]                          # not linked
    w.call("seat", cid=c_free, seat="centre", uid=o2)
    w.call("link", cid=c_nc)
    w.call("link", cid=c_bad)
    r = w.call("emit")
    assert types(r) == ["unlinked_cross", "empty_centre", "tier_mix", "unstable_cross"]
    assert [x.get("cid") for x in r["detail"]["refusals"]] == [c_free, c_nc, None, c_bad]
    assert r["refusal"] == "unlinked_cross"                                         # the first of the list names the call
    rd_ = w.call("read")
    assert types(rd_) == types(r) and rd_["ok"] is True                              # read is the same check as a dry run
    assert srv.closed(w.run_id) is None


def test_constructed_forbidden_is_a_second_line_of_defence(tmp_path):
    """`add` already refuses; if a constructed unit is somehow in the state in record_only the emit gate refuses it too."""
    srv = server(tmp_path)
    w = weaver(srv, "prose/ro")
    run = srv.runs[w.run_id].run
    u = run.state.new_unit("Ωa", "constructed", None, {"by": "m", "at": 1})            # not through add
    c = w.call("open_cross", tier="WORD", L=1)["cid"]
    run.state.place(run.state.crosses[c], None, None, u.uid)
    w.call("link", cid=c)
    r = w.call("emit")
    assert types(r) == ["constructed_forbidden"] and r["detail"]["refusals"][0]["uid"] == u.uid


def test_an_emit_that_succeeds_closes_the_run_and_the_second_is_run_closed(tmp_path):
    srv, w, c, *_ = two(tmp_path, "+x")
    r = w.call("emit")
    assert r["ok"] and r["status"] == "emitted" and len(r["output_sha"]) == 64 and r["shares"]["record"] == 4
    d = w.call("emit")
    assert d["ok"] is False and d["refusal"] == "run_closed"
    assert w.call("read")["refusal"] == "run_closed"


def test_every_refusal_of_emit_leaves_the_thread_unchanged(tmp_path):
    srv, w, c, *_ = two(tmp_path, "-z")
    run = srv.runs[w.run_id].run
    before = run.state.to_obj()
    before["counters"]["emit_attempts"] += 3
    for _ in range(3):
        assert w.call("emit")["ok"] is False
    assert run.state.to_obj() == before


def test_the_refusal_names_a_swap_the_model_can_execute_verbatim(tmp_path):
    """Every improving swap in the refusal is a legal `swap` call, and applying the best one never lowers the key."""
    srv, w, c, *_ = two(tmp_path, "-z")
    for sa, sb, key in w.call("emit")["detail"]["refusals"][0]["improving"]:
        srv2, w2, c2, *_ = two(tmp_path / (sa + sb).replace(":", "_").replace("+", "p").replace("-", "m"), "-z")
        assert w2.call("swap", cid=c2, seat_a=sa, seat_b=sb)["ok"]
        assert w2.call("read")["stability"][0]["key"] == key


# ---------------------------------------------------------------------------------------------------------------
# OP-LOOM-4 (L-LOOM-51): the centre word's は adhesion counts in `a` only when the cross is marked topic
# ---------------------------------------------------------------------------------------------------------------
def eki_mura(tmp_path, topic):
    """centre えき (は adhesion 11 x numerator 233 = 2563), むら on the の arm (+x:0), linked; `topic` marked or not."""
    srv = server(tmp_path)
    w = weaver(srv, "prose/ro", run_id="t")
    ue = w.call("add", text="えき", kind="record", tier="WORD")["uid"]
    um = w.call("add", text="むら", kind="record", tier="WORD")["uid"]
    c = w.call("open_cross", tier="WORD", L=2)["cid"]
    w.call("seat", cid=c, seat="centre", uid=ue)
    w.call("seat", cid=c, seat="+x:0", uid=um)
    if topic:
        w.call("topic", cid=c, on=True)
    w.call("link", cid=c)
    return srv, w, c


def test_marked_topic_counts_the_centre_words_wa_adhesion(tmp_path, corpus):
    srv, w, c = eki_mura(tmp_path, True)
    A = corpus.adhesion["WORD"]
    wa = SPEC.numerator(SPEC.centre) * A.adj("えき", SPEC.centre)
    assert wa == 233 * 11 == 2563
    st = w.call("read")["stability"][0]
    assert st["key"] == [0, 0, 2563] and st["status"] == "stable" and st["improving"] == []
    # the rule is the only difference from placement.seated_key, which is untouched and still counts it unconditionally
    gc = rd.geometry_cross(srv.runs["t"].run.state, srv.runs["t"].run.state.crosses[c])
    assert tuple(pl.seated_key(corpus.tier("WORD"), A, gc, corpus.weights("WORD"))) == (0, 0, 2563)
    assert w.call("emit")["ok"] is True


def test_an_unmarked_cross_computes_a_from_the_arm_particles_alone(tmp_path, corpus):
    srv, w, c = eki_mura(tmp_path, False)
    A = corpus.adhesion["WORD"]
    st = w.call("read")["stability"][0]
    assert st["key"] == [0, 0, 0]                                                    # no arm unit has evidence: the は term is not counted
    gc = rd.geometry_cross(srv.runs["t"].run.state, srv.runs["t"].run.state.crosses[c])
    assert pl.seated_key(corpus.tier("WORD"), A, gc, corpus.weights("WORD"))[2] == 2563      # placement.seated_key is topic-blind (unchanged)
    # and the centre/arm swap now improves it (えき on the の arm: 144 = numerator(の) x 1), so the gate refuses where the marked cross emits
    assert st["status"] == "unstable" and st["improving"] == [["centre", "+x:0", [0, 0, 144]]]
    r = w.call("emit")
    assert r["refusal"] == "unstable_cross" and r["detail"]["refusals"][0]["best_swaps"] == [["centre", "+x:0"]]


def test_marking_the_topic_changes_the_key_by_exactly_the_wa_term(tmp_path, corpus):
    """Same structure, only the topic mark differs: the key moves by numerator(は) x adj(centre, は) and by nothing else."""
    srv, w, c = eki_mura(tmp_path, False)
    k0 = w.call("read")["stability"][0]["key"]
    assert w.call("topic", cid=c, on=True)["ok"]
    k1 = w.call("read")["stability"][0]["key"]
    assert (k1[0], k1[1]) == (k0[0], k0[1]) and k1[2] - k0[2] == 233 * corpus.adhesion["WORD"].adj("えき", "は")
    assert w.call("topic", cid=c, on=False)["ok"]
    assert w.call("read")["stability"][0]["key"] == k0


def test_a_centre_word_without_wa_evidence_is_the_same_marked_or_not(tmp_path, corpus):
    """東京 has no は adhesion (adj = 0): the worked example's key (0, 0, 0) and its bytes do not depend on the mark."""
    assert corpus.adhesion["WORD"].adj("東京", "は") == 0
    keys = []
    for topic in (True, False):
        srv = server(tmp_path / str(topic))
        w = weaver(srv, "demo/tokyo_ro", run_id="t")
        u = w.call("add", text="東京", kind="record", tier="WORD")["uid"]
        c = w.call("open_cross", tier="WORD", L=1)["cid"]
        w.call("seat", cid=c, seat="centre", uid=u)
        w.call("topic", cid=c, on=topic)
        w.call("link", cid=c)
        keys.append(w.call("read")["stability"][0]["key"])
    assert keys == [[0, 0, 0], [0, 0, 0]]
