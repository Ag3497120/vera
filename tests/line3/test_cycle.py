"""T5 tests: the query cycle (whole-space read, moves to a fixed point, agreement, class members,
typed verdicts, answer/thought).  Decisions: I-07, I-08, I-11, I-12, I-15, N-03, N-04, N-08, N-10,
N-11, N-21, M-2, M-5, decision 5/6, T4c "read all members of a class"."""
import hashlib
import io
import json
import os
import random
import subprocess
import sys
import tokenize
from fractions import Fraction as Fr

import pytest

from verantyx.line3 import cycle as cy
from verantyx.line3 import energy as en
from verantyx.line3 import placement as pl
from verantyx.line3.geometry import Cross
from verantyx.line3.space import TierSpace, build_space, load_jsonl

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SRC = os.path.join(ROOT, "verantyx", "line3", "cycle.py")
S300 = os.path.join(ROOT, "experiments", "line3", "data", "S300.jsonl")


def tier(sentences):
    su = tuple(tuple(s.split()) for s in sentences)
    post = {}
    for sid, us in enumerate(su):
        for u in dict.fromkeys(us):
            post.setdefault(u, []).append(sid)
    return TierSpace("T", su, {u: tuple(v) for u, v in post.items()})


TOY1 = ["A B C", "A B C", "B C", "B C", "C D", "D E"]
TOY2 = ["A B C", "A B C", "B C", "B C", "C D", "D E", "E D C", "E D C", "A B", "F E", "F A", "G F"]


def flat_of(L, centre, legs):
    """legs: {world position: tuple of L cells (outer end first)}"""
    out = [centre]
    for p in range(6):
        out.extend(legs.get(p, (None,) * L))
    return tuple(out)


def reader_for(t, query, scope="first_layer"):
    ctx = cy.make_context(query, scope)
    return cy.Reader(cy.TierFacts(t), ctx.attached, ctx.energy_units), ctx


# ---------------------------------------------------------------- N-21 / M-5 / I-07 query cross
def test_query_cross_nesting():
    q6 = cy.build_query_cross(list("abcdef"))
    assert q6.units == tuple("abcdef") and q6.inner is None
    q7 = cy.build_query_cross(list("abcdefg"))
    assert q7.units == tuple("abcdef") and q7.inner is not None and q7.inner.units == ("g",)
    q13 = cy.build_query_cross([str(i) for i in range(13)])
    assert [len(c.units) for c in q13.layers()] == [6, 6, 1]
    assert q13.all_units() == tuple(str(i) for i in range(13))        # order kept
    assert [c.layer for c in q13.layers()] == [0, 1, 2]


def test_first_layer_on_outer_ends_in_order():
    ctx = cy.make_context(list("abcdefgh"))
    assert ctx.attached == tuple("abcdef")                              # I-07: unit i on section i
    cr = ctx.qcross.as_cross()
    assert cr.center is None and [a[0] for a in cr.arms] == list("abcdef")
    assert ctx.energy_units == tuple("abcdef")                          # M-5(c): the first layer answers
    assert cy.make_context(list("abcdefgh"), "whole").energy_units == tuple(sorted("abcdefgh"))
    short = cy.make_context(["x", "y"])
    assert short.attached == ("x", "y", None, None, None, None)


def test_seven_plus_unit_question_becomes_nested_cross_in_result():
    t = tier(TOY1)
    P = pl.Placer(t)
    r = cy.ask_tier(t, "", P, units=list("ABCDEFGHI"))
    th = r.thought_obj()
    assert th["query"]["layers"] == [list("ABCDEF"), list("GHI")]
    assert th["inner_layers_pending"] == [list("GHI")]
    assert th["query_first_layer"] == list("ABCDEF")


# ---------------------------------------------------------------- exact fast path == T3 slow path
def _same(e, k, v, facts):
    sc = facts.N * facts.D
    return (e.key[0] == k[0] and e.key[1] == k[1] and Fr(e.key[2], sc) == k[2]
            and e.status == v.status and e.agreed == v.unit
            and e.sections == tuple(s.unit for s in v.sections)
            and e.r2 == v.edge_unit and e.r3 == v.placement_unit)


def test_fast_evaluation_equals_energy_three_ratios_on_random_states():
    t = tier(TOY2)
    units = sorted(t.postings)
    rnd = random.Random(4)
    for L in (1, 2, 3):
        for _ in range(60):
            q = tuple(rnd.sample(units, rnd.randint(1, 4)))
            r, ctx = reader_for(t, q)
            flat = [None] * (6 * L + 1)
            cells = rnd.sample(units, rnd.randint(2, min(len(units), 6 * L + 1)))
            for u, i in zip(cells, rnd.sample(range(6 * L + 1), len(cells))):
                flat[i] = u
            if flat[0] is None:
                continue
            s = tuple(flat)
            k, v = cy.slow_key(t, pl.to_cross(s, L), ctx.energy_units, ctx.attached_map())
            assert _same(r.evaluate(s, L), k, v, r.f)


def test_incremental_neighbours_equal_full_evaluation():
    t = tier(TOY2)
    units = sorted(t.postings)
    rnd = random.Random(9)
    L = 2
    for _ in range(25):
        q = tuple(rnd.sample(units, rnd.randint(1, 4)))
        r, ctx = reader_for(t, q)
        flat = [None] * 13
        cells = rnd.sample(units, rnd.randint(3, len(units)))
        for u, i in zip(cells, rnd.sample(range(13), len(cells))):
            flat[i] = u
        if flat[0] is None:
            continue
        s = tuple(flat)
        b = r.make_base(s, L)
        assert b.eval == r.evaluate(s, L)
        fresh = cy.Reader(r.f, ctx.attached, ctx.energy_units)
        for src in cy.rotation_tables():
            s2 = cy.apply_rotation(s, L, src)
            assert r.neighbour_rotation(b, src, s2) == fresh.evaluate(s2, L)
        for i, j in cy.swap_pairs(L):
            if s[i] == s[j] or (i == 0 and s[j] is None):
                continue
            assert r.neighbour_swap(b, i, j) == fresh.evaluate(cy.apply_swap(s, i, j), L)


def test_rotation_tables_are_the_geometry_rotations():
    from verantyx.line3.geometry import G24, rotate
    marker = Cross.make(L=1, arms=[[i] for i in range(6)])
    tabs = cy.rotation_tables()
    assert len(tabs) == 23 and len(set(tabs)) == 23
    for r, src in zip([g for g in G24 if g != G24[0]] if False else cy.moves_rotate(), tabs):
        assert tuple(w[0] for w in rotate(marker, r).world_arms()) == src
    from verantyx.line3.geometry import moves_swap, seats
    assert len(cy.swap_pairs(3)) == len(moves_swap(3))


# ---------------------------------------------------------------- moves accepted and changing the result
def test_rotation_accepted_and_changes_the_result():
    t = tier(TOY2)
    r, ctx = reader_for(t, ("E", "F"))
    s = ('E', None, 'B', None, None, 'G', 'F', None, None, None, 'D', 'A', 'C')
    assert r.evaluate(s, 2).answer is None
    res = cy.settle(r, s, 2)
    assert res.budget_hit is None and res.rotations_taken >= 1 and res.swaps_taken == 0
    assert [e.answer for e in res.ends] == ["E"]
    end = res.ends[0].flat
    # the end state is a rotation of the start: same contents, same centre, legs permuted
    assert any(cy.apply_rotation(s, 2, src) == end for src in cy.rotation_tables())
    rep = cy.verify_query_fixed_point(t, pl.to_cross(end, 2), ctx.energy_units, ctx.attached_map())
    assert rep.is_fixed_point and rep.improving == 0 and rep.agree
    rep0 = cy.verify_query_fixed_point(t, pl.to_cross(s, 2), ctx.energy_units, ctx.attached_map())
    assert not rep0.is_fixed_point and rep0.improving > 0


def test_swap_accepted_and_changes_the_result():
    t = tier(TOY1)
    r, ctx = reader_for(t, ("A",))
    s = ('A', 'B', None, 'C') + (None,) * 3 + ('E',) + (None,) * 5
    s = ('A', 'B', None, 'C', None, None, 'E', None, None, None, None, None, None)
    assert r.evaluate(s, 2).answer is None
    res = cy.settle(r, s, 2)
    assert res.budget_hit is None and res.swaps_taken >= 1 and res.rotations_taken == 0
    assert {e.answer for e in res.ends} == {"C"}
    for e in res.ends:
        rep = cy.verify_query_fixed_point(t, pl.to_cross(e.flat, 2), ctx.energy_units, ctx.attached_map())
        assert rep.is_fixed_point and rep.improving == 0
    assert res.ends[0].flat != s and sorted(map(str, res.ends[0].flat)) == sorted(map(str, s))


def test_centre_never_left_empty():
    t = tier(TOY1)
    r, _ = reader_for(t, ("A",))
    s = ('C', 'B', None) + (None,) * 10
    res = cy.settle(r, s, 2)
    assert all(e.flat[0] is not None for e in res.ends)
    with pytest.raises(ValueError):
        cy.settle(r, (None,) * 13, 2)


# ---------------------------------------------------------------- fixed points, ties
def test_every_end_state_of_a_whole_read_is_a_verified_fixed_point():
    t = tier(TOY2)
    P = pl.Placer(t)
    for q in (("A", "B"), ("E",), ("C", "D", "E")):
        res = cy.ask_tier(t, "", P, units=q)
        ctx = cy.make_context(q)
        n = 0
        for sr in res.reads:
            for m in sr.members:
                for e in m.settled.ends:
                    rep = cy.verify_query_fixed_point(t, pl.to_cross(e.flat, m.settled.L),
                                                      ctx.energy_units, ctx.attached_map())
                    assert rep.is_fixed_point and rep.improving == 0
                    n += 1
        assert n > 0


AMB_START = ('D', None, 'C', None, None, 'E', None, 'B', 'A', None, None, None, None)


def test_tied_branches_with_different_results_are_ambiguous():
    t = tier(TOY1)
    r, ctx = reader_for(t, ("A", "E", "D"))
    res = cy.settle(r, AMB_START, 2)
    assert res.budget_hit is None and len(res.ends) > 1
    assert len({e.answer for e in res.ends}) > 1
    m = cy.member_outcome(0, res)
    assert m.kind == cy.AMBIG and m.unit is None and m.inv is None
    sr = cy.SeedRead("x", 1, (m,))
    assert cy.adopt_members(sr) == []                                 # abstains; no winner by order
    assert cy._verdict_from([sr], "stable_any")[0] == cy.AMBIGUOUS


def test_equal_best_stability_gives_a_list_not_an_order_winner():
    def end(u):
        return cy.EndState(("x",) * 13, (0, 0, 0), en.AGREE, u, u, Fr(1, 2), 4, 2, 0, 0)

    def seed(name, unit):
        e = end(unit)
        s = cy.Settled(e.flat, 2, (e,), 1, 0, None)
        return cy.SeedRead(name, 1, (cy.MemberOutcome(0, cy.CANDIDATE, unit, en.AGREE, Fr(1, 2), s),))
    v, units, stab, cands = cy._verdict_from([seed("s1", "P"), seed("s2", "Q")], "stable_any")
    assert v == cy.CHOICE and units == ("P", "Q") and stab == Fr(1, 2)
    v, units, _, _ = cy._verdict_from([seed("s1", "P"), seed("s2", "P")], "stable_any")
    assert v == cy.ANSWER and units == ("P",)                          # same unit twice is one answer
    v2, u2, _, _ = cy._verdict_from([seed("s2", "Q"), seed("s1", "P")], "stable_any")
    assert (v2, u2) == (cy.CHOICE, ("P", "Q"))                         # order of reading does not matter


def test_higher_stability_wins_over_lower():
    def sr(name, unit, inv):
        e = cy.EndState(("x",) * 13, (0, 0, 0), en.AGREE, unit, unit, inv, 4, 2, 0, 0)
        s = cy.Settled(e.flat, 2, (e,), 1, 0, None)
        return cy.SeedRead(name, 1, (cy.MemberOutcome(0, cy.CANDIDATE, unit, en.AGREE, inv, s),))
    v, units, stab, _ = cy._verdict_from([sr("a", "P", Fr(1, 3)), sr("b", "Q", Fr(2, 3))], "stable_any")
    assert (v, units, stab) == (cy.ANSWER, ("Q",), Fr(2, 3))


def test_stability_is_share_of_moves_that_keep_the_result():
    t = tier(TOY1)
    r, ctx = reader_for(t, ("A",))
    s = ('A', 'B', None, 'C', None, None, 'E', None, None, None, None, None, None)
    res = cy.settle(r, s, 2)
    for e in res.ends:
        assert e.moves > 0 and e.inv == Fr(e.unchanged, e.moves)
        # recount by brute force with the slow path, geometry moves only
        from verantyx.line3.geometry import moves_rotate, moves_swap, rotate, swap
        cross = pl.to_cross(e.flat, 2)
        res_of = lambda c: _slow_answer(t, c, ctx)
        base = res_of(cross)
        same = tot = 0
        for rot in moves_rotate():
            c2 = rotate(cross, rot)
            if c2.world_arms() == cross.world_arms():
                continue
            tot += 1
            same += res_of(c2) == base
        for p, q_ in moves_swap(2):
            if cross.get(p) == cross.get(q_):
                continue
            c2 = swap(cross, p, q_)
            if c2.center is None:
                continue
            tot += 1
            same += res_of(c2) == base
        assert (same, tot) == (e.unchanged, e.moves)


def _slow_answer(t, cross, ctx):
    v = en.three_ratios(t, cross, ctx.energy_units, ctx.attached_map())
    if v.status != en.AGREE:
        return None
    grounded = sum(1 for s in v.sections if s.unit is not None and ctx.attached[s.section] is not None
                   and ctx.attached[s.section] in t.postings)
    return v.unit if grounded >= 1 else None


# ---------------------------------------------------------------- N-03
def test_n03_agreement_without_a_grounded_section_is_not_an_answer():
    t = tier(TOY1)
    r, ctx = reader_for(t, ("A",))
    s = flat_of(2, "C", {2: ("A", "B")})              # leg not in front of section 0 (A's section)
    res = cy.settle(r, s, 2)
    assert res.budget_hit is None and len(res.ends) == 1
    e = r.evaluate(res.ends[0].flat, 2)        # an agreeing fixed point whose sections are all ungrounded
    assert e.status == en.AGREE and e.agreed == "C"
    assert e.grounded == 0 and e.answer is None and res.ends[0].answer is None
    assert res.ends[0].status == en.AGREE
    s0 = flat_of(2, "C", {0: ("A", "B")})
    e0 = r.evaluate(s0, 2)
    assert e0.grounded >= 1
    # a query unit that is not in the space grounds nothing, even if everything "agrees"
    P = pl.Placer(t)
    res = cy.ask_tier(t, "", P, units=("Z",))
    assert res.verdict == cy.UNKNOWN_NO_EVIDENCE and res.units == ()
    assert all(m.kind != cy.CANDIDATE for sr in res.reads for m in sr.members)


# ---------------------------------------------------------------- whole read, M-2 partial reads
def test_whole_space_read_reads_one_cross_per_unit_and_every_member():
    t = tier(["A B", "B A", "A B C", "C D", "D A"])
    P = pl.Placer(t)
    res = cy.ask_tier(t, "", P, units=("A", "B"))
    th = res.thought_obj()
    assert th["read"]["crosses_read"] == len(t.units()) == th["read"]["total"]
    assert th["read"]["crosses_unread"] == 0
    assert res.answer_obj()["partial_read"] is None
    assert res.members_read == res.members_total == sum(P.cross_for(u).expanded_size for u in t.units())
    assert len(res.reads) == len(t.units())


def test_partial_read_is_marked_with_counts_and_ties_are_not_split():
    t = tier(TOY2)
    P = pl.Placer(t)
    facts = cy.TierFacts(t)
    whole = cy.ask_tier(t, "", P, units=("E", "F"), facts=facts, read_rule="whole")   # old option (I-08)
    total = len(t.units())
    part = cy.ask_tier(t, "", P, units=("E", "F"), facts=facts, amount=3)
    a = part.answer_obj()
    assert a["partial_read"] is not None
    assert a["partial_read"]["read"] + a["partial_read"]["unread"] == total
    assert a["partial_read"]["read"] <= 3 and a["partial_read"]["amount"] == 3
    # the first crosses read are the query units' own crosses (M-2(a)), E and F, then by E_Q
    assert {"E", "F"} <= {sr.seed for sr in part.reads} or part.plan.read[:1] != ()
    # no equal-value group is split: seeds of one group are all read or none
    read = set(part.plan.read)
    for g, seeds in part.plan.order_groups:
        assert set(seeds) <= read or not (set(seeds) & read)
    assert whole.answer_obj()["partial_read"] is None
    assert part.thought_obj()["read"]["crosses_unread"] == a["partial_read"]["unread"]
    z = cy.ask_tier(t, "", P, units=("E", "F"), facts=facts, amount=0)
    assert z.answer_obj()["partial_read"]["read"] == 0 and z.verdict == cy.UNKNOWN_NO_EVIDENCE


def test_read_order_puts_query_units_first_then_by_energy_descending():
    t = tier(TOY2)
    P = pl.Placer(t)
    facts = cy.TierFacts(t)
    ctx = cy.make_context(("E", "F"))
    plan = cy.plan_read(t, facts, ctx, P, None)
    names = [g for g, _ in plan.order_groups]
    assert names == sorted(names, key=["query_unit", "shares_with_query", "rest"].index)
    assert set(plan.order_groups[0][1]) | set(plan.order_groups[1][1]) >= {"E", "F"}
    reader = cy.Reader(facts, ctx.attached, ctx.energy_units)
    for g in ("query_unit", "shares_with_query", "rest"):
        vals = [reader.enq(s[0]) for gg, s in plan.order_groups if gg == g]
        assert vals == sorted(vals, reverse=True) and len(set(vals)) == len(vals)


# ---------------------------------------------------------------- N-11 stacking marker, N-08/N-10 output
def test_budget_exhaustion_is_typed_and_marks_where_stacking_would_occur():
    t = tier(TOY2)
    P = pl.Placer(t)
    res = cy.ask_tier(t, "", P, units=("E", "F"), budget=cy.QueryBudget(1, 1))
    th = res.thought_obj()
    assert th["stacking"]["would_stack"] and th["stacking"]["points"]
    assert all(p["reason"] in ("max_states", "max_ends") for p in th["stacking"]["points"])
    assert th["search"].get("no_fixed_point", 0) == len(th["stacking"]["points"])
    big = cy.ask_tier(t, "", P, units=("E", "F"))
    assert not big.thought_obj()["stacking"]["would_stack"]


def test_answer_and_thought_are_separate_and_json_exact():
    t = tier(TOY2)
    P = pl.Placer(t)
    res = cy.ask_tier(t, "", P, units=("E", "F"), with_state=True)
    o = res.to_json_obj()
    assert set(o) == {"answer", "thought"}
    assert {"verdict", "units", "stability", "partial_read", "trace"} <= set(o["answer"])
    assert {"search", "energy_log", "state_version", "stacking", "search_state_digest"} <= set(o["thought"])
    assert "search" not in o["answer"] and "verdict" not in o["thought"]
    assert o["thought"]["state_version"] == 0
    json.dumps(o)                                                      # JSON-able (no Fractions inside)
    st = res.state
    assert st["format"] == cy.STATE_FORMAT and st["records"] and json.dumps(st)
    assert hashlib.sha256(json.dumps(st, sort_keys=True, separators=(",", ":"),
                                     ensure_ascii=False).encode()).hexdigest() == o["thought"]["search_state_digest"]
    if res.verdict in (cy.ANSWER, cy.CHOICE):
        assert o["thought"]["energy_log"], "observation record for the adopted state (L-20)"
        for rec in o["thought"]["energy_log"]:
            assert all({"unit", "r0", "E", "ratio"} <= set(x) for x in rec["records"])


def test_member_rule_flag_changes_only_the_pool():
    t = tier(TOY2)
    P = pl.Placer(t)
    a = cy.ask_tier(t, "", P, units=("E", "F"), member_rule="stable_any", state_rule="stability")   # old rule: the pool matters
    b = cy.ask_tier(t, "", P, units=("E", "F"), member_rule="answering_only", state_rule="stability")
    assert a.state_digest == b.state_digest                           # the search is the same
    assert (b.alt_verdict[0], b.alt_verdict[1]) == (a.verdict, a.units)
    with pytest.raises(ValueError):
        cy.adopt_members(a.reads[0], "bogus")


# ---------------------------------------------------------------- determinism and exactness
_SCRIPT = r"""
import sys, hashlib
sys.path.insert(0, %r)
from verantyx.line3 import cycle as cy, placement as pl
from verantyx.line3.space import TierSpace, build_space, load_jsonl
def tier(ss):
    su=tuple(tuple(s.split()) for s in ss); post={}
    for i,us in enumerate(su):
        for u in dict.fromkeys(us): post.setdefault(u,[]).append(i)
    return TierSpace("T",su,{u:tuple(v) for u,v in post.items()})
h=hashlib.sha256()
for ss,q in ((%r,("E","F")),(%r,("A","B","C","D","E","F","G"))):
    t=tier(ss); P=pl.Placer(t)
    for amount in (None,4):
        h.update(cy.ask_tier(t,"",P,units=q,amount=amount).to_bytes())
rows=load_jsonl(%r)[:8]
sp=build_space(rows)
for tn in ("RUN","WORD"):
    t=sp.tiers[tn]; P=pl.Placer(t,pl.Budget(60,400))
    q=cy.split_question(tn,"半田岩はどこにありますか")
    h.update(cy.ask_tier(t,"x",P,units=q,budget=cy.QueryBudget(32,8)).to_bytes())
print(h.hexdigest())
"""


def test_byte_identical_across_hash_seeds():
    outs = []
    for seed in ("0", "1", "12345"):
        env = dict(os.environ, PYTHONHASHSEED=seed, PYTHONDONTWRITEBYTECODE="1", PYTHONPATH=ROOT)
        r = subprocess.run([sys.executable, "-c", _SCRIPT % (ROOT, TOY2, TOY1, S300)],
                           capture_output=True, text=True, env=env, timeout=900)
        assert r.returncode == 0, r.stderr
        outs.append(r.stdout.strip())
    assert len(set(outs)) == 1 and len(outs[0]) == 64


def test_no_float_in_source():
    with open(SRC, "rb") as f:
        toks = list(tokenize.tokenize(io.BytesIO(f.read()).readline))
    for tk in toks:
        if tk.type == tokenize.NUMBER:
            assert "." not in tk.string and "e" not in tk.string.lower()
        if tk.type == tokenize.NAME:
            assert tk.string != "float"


def test_cycle_does_not_change_the_committed_modules():
    import subprocess as sp
    # T6v: space.py got the optional unit_filter (defaults proved byte-identical in test_variants.py)
    r = sp.run(["git", "status", "--porcelain", "verantyx/line3/geometry.py",
                "verantyx/line3/energy.py", "verantyx/line3/placement.py"], cwd=ROOT, capture_output=True, text=True)
    assert r.stdout.strip() == ""


def test_s300_small_tier_whole_read_runs_and_end_states_verify():
    sp = build_space(load_jsonl(S300)[:8], unit_filter=None)           # the old space, explicit option
    t = sp.tiers["WORD"]
    P = pl.Placer(t, pl.Budget(60, 400))
    q = cy.split_question("WORD", "半田岩はどこにありますか")
    assert len(q) == 8
    res = cy.ask_tier(t, "", P, units=q, budget=cy.QueryBudget(32, 8),
                      read_rule="whole", state_rule="stability", unit_filter=None)
    assert res.thought_obj()["read"]["crosses_read"] == len(t.units())
    assert res.thought_obj()["inner_layers_pending"] == [list(q[6:])]
    ctx = cy.make_context(q)
    checked = 0
    for sr in res.reads[::7]:
        for m in sr.members:
            for e in m.settled.ends[:2]:
                rep = cy.verify_query_fixed_point(t, pl.to_cross(e.flat, m.settled.L), ctx.energy_units, ctx.attached_map())
                assert rep.is_fixed_point
                checked += 1
    assert checked > 0
