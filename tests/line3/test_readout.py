"""T6 tests: read-out along section -> centre paths, orderings of whole section paths (I-13, N-13),
adopt / list (I-14, N-14), stability (I-15), list without a cap and the too-many flag (N-20), the
intake of the user's choice (M-4 (a)), trace check 100%, determinism, exact arithmetic."""
import dataclasses
import io
import os
import subprocess
import sys
import tokenize
from fractions import Fraction as Fr
from math import factorial

import pytest

from verantyx.line3 import cycle as cy
from verantyx.line3 import placement as pl
from verantyx.line3 import readout as ro
from verantyx.line3 import trace_check as tc
from verantyx.line3.space import TierSpace

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
T5_WORD = os.path.join(ROOT, "experiments", "line3", "t5", "results", "S300_CHAR_mid_64x8.jsonl")


def tier(sentences):
    su = tuple(tuple(s.split()) for s in sentences)
    post = {}
    for sid, us in enumerate(su):
        for u in dict.fromkeys(us):
            post.setdefault(u, []).append(sid)
    return TierSpace("T", su, {u: tuple(v) for u, v in post.items()})


# a hub "c" that every leg unit a0..a5 shares sentences with, and that is more frequent than any of them:
# every walk a_i -> c is evidenced and the energy does not drop, so every filled leg reaches the centre.
HUB = [s for i in range(6) for s in ("a%d c" % i, "a%d c" % i)] + ["c", "c", "c", "c"]


def flat_with(positions, L=1):
    """centre c; leg at world position p holds a<p>."""
    legs = [(("a%d" % p,) if p in positions else (None,)) for p in range(6)]
    return ("c",) + tuple(x for leg in legs for x in leg)


def ctx_for(units=("zz",)):
    return cy.make_context(units)


def ref(flat, stab=Fr(1, 2), seed="s", member=0, unit="c", tier_name="T"):
    return ro.StateRef(tier_name, seed, member, flat, stab, unit, 0)


def do(states, window=0, **kw):
    t = tier(HUB)
    return t, ro.read_out(cy.TierFacts(t), ctx_for(), states, question="q", window=window, **kw)


# ---------------------------------------------------------------- paths
def test_section_path_walks_outer_end_to_centre_and_stops_where_the_section_stops():
    t = tier(HUB + ["x y"])
    facts = cy.TierFacts(t)
    ctx = ctx_for()
    rd = cy.Reader(facts, ctx.attached, ctx.energy_units, 0)
    flat = flat_with({1})
    (p,) = ro.section_paths(rd, flat, 1)
    assert (p.section, p.words, p.seats, p.unit, p.segments) == (1, ("a1", "c"), (2, 0), "c", ((2, 0),))
    # an unevidenced edge stops the walk at the leg's own unit: the path is that unit only
    flat2 = ("c", None, "x", None, None, None, None)
    (p2,) = ro.section_paths(rd, flat2, 1)
    assert p2.words == ("x",) and p2.unit == "x" and p2.seats == (2,)
    # no walk can start on an empty seat: no working section, no path
    assert ro.section_paths(rd, ("c",) + (None,) * 6, 1) == ()


def test_section_path_agrees_with_the_cycle_walk_on_every_state_of_a_toy_run():
    t = tier(["A B C", "A B C", "B C", "B C", "C D", "D E", "E D C", "E D C", "A B", "F E", "F A", "G F"])
    P = pl.Placer(t)
    res = cy.ask_tier(t, "", P, units=("E", "F"))
    facts = cy.TierFacts(t)
    rdr = cy.Reader(facts, res.ctx.attached, res.ctx.energy_units)
    n = 0
    for c in res.candidates:
        L = (len(c.end.flat) - 1) // 6
        ev = rdr.evaluate(c.end.flat, L)
        paths = ro.section_paths(rdr, c.end.flat, L)
        assert [p.section for p in paths] == [s for s in range(6) if ev.sections[s] is not None]
        for p in paths:
            assert p.unit == ev.sections[p.section] and p.words[-1] == p.unit
            n += 1
    assert n > 0


def test_a_section_reads_every_leg_it_sees_that_reaches_its_unit_in_ring_order_end_unit_once():
    t = tier(HUB)
    rd = cy.Reader(cy.TierFacts(t), ctx_for().attached, ctx_for().energy_units)          # window 1
    paths = ro.section_paths(rd, flat_with({0, 2, 4}), 1)
    assert [p.section for p in paths] == [0, 1, 2, 3, 4, 5]           # k = 6 with three legs
    by = {p.section: p for p in paths}
    assert by[0].words == ("a0", "c")                                    # sees legs 5, 0, 1
    assert by[1].words == ("a0", "a2", "c")                              # sees legs 0, 1, 2 : a0 and a2
    assert by[1].segments == ((1, 0), (3, 0))


# ---------------------------------------------------------------- k working sections -> k! candidates
@pytest.mark.parametrize("k", [1, 2, 3, 4, 5, 6])
def test_k_working_sections_give_exactly_k_factorial_candidates(k):
    t, r = do([ref(flat_with(set(range(k))))])
    assert r.states[0].k == k
    assert r.orderings_total == factorial(k) and r.states[0].orderings == factorial(k)
    assert r.distinct_total == factorial(k) and len(r.sentences) == factorial(k)   # all paths read differently
    assert factorial(k) <= 720
    assert r.verdict == (cy.ANSWER if k == 1 else cy.CHOICE)
    for s in r.sentences:
        assert len(s.words) == 2 * k and len(s.origins) == 1
    # every ordering of the WHOLE section paths occurs once
    orders = sorted(o for s in r.sentences for _, o in s.origins)
    assert len(set(orders)) == factorial(k)


def test_counts_over_several_states_and_identical_sentences_collapse_but_keep_every_origin():
    f = flat_with({0, 1, 2})
    t, r = do([ref(f, seed="s1"), ref(f, seed="s2"), ref(flat_with({0, 1}), seed="s3")])
    assert r.orderings_total == 6 + 6 + 2
    assert r.distinct_total == 6 + 2
    assert len(r.sentences) == r.distinct_total
    two = [s for s in r.sentences if len(s.origins) > 1]
    assert two and all(len(s.origins) == 2 for s in two)      # same words from the two identical states
    # no cap: a list of any size is returned in full
    assert len(r.sentences) == r.distinct_total


def test_paths_that_read_the_same_make_the_orderings_one_sentence():
    # two legs hold the same unit?  a section path is by words, so two states with the same words coincide
    f = flat_with({0})
    t, r = do([ref(f, seed="s1"), ref(f, seed="s2")])
    assert r.orderings_total == 2 and len(r.sentences) == 1 and len(r.sentences[0].origins) == 2
    assert r.verdict == cy.ANSWER                      # one sentence at the best stability: adopted


# ---------------------------------------------------------------- adopt / list (I-14, N-14, I-15)
def test_one_most_stable_sentence_is_adopted_ties_are_listed_never_ordered():
    f1, f2 = flat_with({0}), flat_with({1})
    _, r = do([ref(f1, Fr(1, 2), "s1"), ref(f2, Fr(1, 2), "s2")])
    assert r.verdict == cy.CHOICE and [s.text for s in r.sentences] == ["a0c", "a1c"]
    _, r = do([ref(f1, Fr(1, 2), "s1"), ref(f2, Fr(2, 3), "s2")])
    assert r.verdict == cy.ANSWER and r.sentences[0].text == "a1c" and r.best_stability == Fr(2, 3)
    assert r.below_best == 1 and r.distinct_total == 2
    assert isinstance(r.best_stability, Fr) and isinstance(r.sentences[0].stability, Fr)


def test_stability_of_a_sentence_is_the_best_stability_of_its_origins():
    f = flat_with({0})
    _, r = do([ref(f, Fr(1, 3), "s1"), ref(f, Fr(3, 4), "s2")])
    assert len(r.sentences) == 1 and r.sentences[0].stability == Fr(3, 4) and r.below_best == 0


def test_no_working_section_gives_no_readout_typed():
    _, r = do([ref(("c",) + (None,) * 6)])
    assert r.verdict == ro.UNKNOWN_NO_PATH and r.sentences == () and r.states_without_path == 1
    assert r.orderings_total == 0 and r.best_stability is None
    _, r0 = do([])
    assert r0.verdict == ro.UNKNOWN_NO_PATH
    with pytest.raises(ValueError):
        ro.adopt(r)


def test_too_many_flag_is_a_display_value_and_never_shortens_the_list():
    _, r = do([ref(flat_with(set(range(6))))])                   # 720
    assert len(r.sentences) == 720 and r.too_many and r.too_many_limit == 20
    _, r2 = do([ref(flat_with(set(range(6))))], too_many=720)
    assert len(r2.sentences) == 720 and not r2.too_many
    _, r3 = do([ref(flat_with({0, 1, 2}))])
    assert len(r3.sentences) == 6 and not r3.too_many


# ---------------------------------------------------------------- intake (M-4 (a), N-20)
def test_intake_of_the_users_choice_is_the_adopted_answer_record():
    _, r = do([ref(flat_with({0, 1}))])
    assert r.verdict == cy.CHOICE
    a = ro.choose(r, 1)
    b = ro.choose(r, r.sentences[1].text)
    assert a == b and a.source == "user_choice" and a.choice_index == 1
    rec = a.memory_record()
    assert rec["kind"] == "memory_answer" and rec["answer"] == r.sentences[1].text
    assert rec["base_changed"] is False and rec["offered"] == 2 and rec["question"] == "q"
    assert a.to_bytes() == b.to_bytes()
    assert tc.check_adoption(r, a)
    for bad in (2, -1, "not on the list", ""):
        with pytest.raises((IndexError, ValueError)):
            ro.choose(r, bad)
    with pytest.raises(TypeError):
        ro.choose(r, True)
    with pytest.raises(TypeError):
        ro.choose(r, 1.0)
    # an automatic adoption has the same record shape, source auto
    _, r1 = do([ref(flat_with({0}))])
    c = ro.adopt(r1)
    assert c.memory_record()["source"] == "auto" and c.memory_record()["kind"] == "memory_answer"
    with pytest.raises(ValueError):
        ro.adopt(r)                                  # a list is not adopted automatically
    _, rn = do([ref(("c",) + (None,) * 6)])
    with pytest.raises(ValueError):
        ro.choose(rn, 0)


# ---------------------------------------------------------------- trace check
def test_trace_check_is_100_percent_and_records_where_each_word_is():
    t, r = do([ref(flat_with(set(range(4))), seed="seedX", member=3)])
    traces, rep = tc.trace_readout(t, r)
    assert rep.ok and rep.fraction == 1 and rep.words_checked == 24 * 8 == rep.words_traced
    assert rep.sentences_ok == rep.sentences_checked == 24
    assert all(w.ok and w.sid is not None and w.n_sentences >= 1 for w in traces)
    assert {w.seed for w in traces} == {"seedX"} and {w.member for w in traces} == {3}
    assert any(w.edge_sid is not None for w in traces)                   # a1 -> c edges carry their sentence
    first = [w for w in traces if w.pos == 0]
    assert all(w.edge_sid is None for w in first)                        # a leg opens with no edge


def test_trace_check_catches_a_word_not_in_the_structure():
    t, r = do([ref(flat_with({0, 1}))])
    st = r.states[0]
    p0 = dataclasses.replace(st.paths[0], words=("a0x", "c"))              # not held at that seat
    r2 = dataclasses.replace(r, states=(dataclasses.replace(st, paths=(p0,) + st.paths[1:]),))
    _, rep = tc.trace_readout(t, r2)
    assert not rep.ok and rep.fraction < 1
    # the sentence list no longer reproduces from the paths either
    # a sentence with a word that no path gives
    s = r.sentences[0]
    bad = dataclasses.replace(s, words=("zzz",) + s.words[1:], text="zzz" + "".join(s.words[1:]))
    _, rep2 = tc.trace_readout(t, dataclasses.replace(r, sentences=(bad,) + r.sentences[1:]))
    assert not rep2.ok and rep2.words_traced < rep2.words_checked


def test_trace_check_catches_an_edge_no_sentence_evidences():
    t = tier(HUB + ["x", "y"])
    flat = ("c", "x", None, None, None, None, None)
    # hand-built path: x -> c with no sentence holding both
    p = ro.SectionPath(0, None, "c", ("x", "c"), (1, 0), ((1, 0),))
    st = ro.StateRead(ref(flat), (p,))
    s = ro.Sentence("xc", ("x", "c"), Fr(1, 2), ((0, (0,)),))
    r = ro.Readout("q", "T", (st,), (s,), cy.ANSWER, Fr(1, 2), 1, 1, 0, 0, False, 20)
    traces, rep = tc.trace_readout(t, r)
    assert not rep.ok and any("edge" in w.reason for w in traces if not w.ok)
    # a walk that is not a chain of neighbouring seats
    p2 = ro.SectionPath(0, None, "c", ("c", "x"), (0, 1), ((0, 1),))
    st2 = ro.StateRead(ref(flat), (p2,))
    r2 = dataclasses.replace(r, states=(st2,), sentences=(ro.Sentence("cx", ("c", "x"), Fr(1, 2), ((0, (0,)),)),))
    _, rep2 = tc.trace_readout(t, r2)
    assert not rep2.ok


def test_end_to_end_cycle_result_to_readout_with_trace_100_percent():
    t = tier(["A B C", "A B C", "B C", "B C", "C D", "D E", "E D C", "E D C", "A B", "F E", "F A", "G F"])
    P = pl.Placer(t)
    res = cy.ask_tier(t, "", P, units=("E", "F"))
    assert res.candidates
    r = ro.read_out_result(t, res)
    assert len(r.states) == len(res.candidates)
    assert all(s.ref.stability == res.stability for s in r.states)
    assert r.orderings_total == sum(factorial(s.k) for s in r.states)
    _, rep = tc.trace_readout(t, r)
    assert rep.ok and rep.fraction == 1 and rep.words_checked > 0
    # the stored-object route gives the same read-out as the in-memory route
    r2 = ro.read_out_stored(cy.TierFacts(t), "", res.answer_obj(), units=("E", "F"))
    assert r2.to_json_obj() == dataclasses.replace(r, question="").to_json_obj()
    # output is plain data: answer / thought
    o = r.to_json_obj()
    assert set(o) == {"answer", "thought"} and o["thought"]["counts"]["orderings"] == r.orderings_total


def test_stored_t5_result_reads_out_with_trace_100_percent():
    if not os.path.exists(T5_WORD):
        pytest.skip("T5 stored results not present")
    import json
    from verantyx.line3.space import build_space, load_jsonl
    row = json.loads(open(T5_WORD, encoding="utf-8").readline())
    sp = build_space(load_jsonl(os.path.join(ROOT, "experiments", "line3", "data", "S300.jsonl")))
    t = sp.tiers["CHAR"]
    r = ro.read_out_stored(cy.TierFacts(t), row["question"], row["answer"])
    assert r.states and all(s.k == 6 for s in r.states)
    assert r.orderings_total == 720 * len(r.states)
    _, rep = tc.trace_readout(t, r)
    assert rep.ok and rep.fraction == 1


# ---------------------------------------------------------------- determinism and exactness
_SCRIPT = r"""
import sys, hashlib
sys.path.insert(0, %r)
from fractions import Fraction as Fr
from verantyx.line3 import cycle as cy, placement as pl, readout as ro, trace_check as tc
from verantyx.line3.space import TierSpace
def tier(ss):
    su=tuple(tuple(s.split()) for s in ss); post={}
    for i,us in enumerate(su):
        for u in dict.fromkeys(us): post.setdefault(u,[]).append(i)
    return TierSpace("T",su,{u:tuple(v) for u,v in post.items()})
h=hashlib.sha256()
t=tier(%r); P=pl.Placer(t)
for q in (("E","F"),("A","B","C")):
    res=cy.ask_tier(t,"",P,units=q)
    r=ro.read_out_result(t,res)
    h.update(r.to_bytes())
    h.update(repr(tc.trace_readout(t,r)[1]).encode())
    if r.verdict==cy.CHOICE:
        h.update(ro.choose(r,0).to_bytes())
print(h.hexdigest())
"""
TOY2 = ["A B C", "A B C", "B C", "B C", "C D", "D E", "E D C", "E D C", "A B", "F E", "F A", "G F"]


def test_byte_identical_across_hash_seeds():
    outs = []
    for seed in ("0", "1", "12345"):
        env = dict(os.environ, PYTHONHASHSEED=seed, PYTHONDONTWRITEBYTECODE="1", PYTHONPATH=ROOT)
        r = subprocess.run([sys.executable, "-c", _SCRIPT % (ROOT, TOY2)], capture_output=True, text=True,
                           env=env, timeout=900)
        assert r.returncode == 0, r.stderr
        outs.append(r.stdout.strip())
    assert len(set(outs)) == 1 and len(outs[0]) == 64


@pytest.mark.parametrize("name", ["readout.py", "trace_check.py"])
def test_no_float_in_source(name):
    with open(os.path.join(ROOT, "verantyx", "line3", name), "rb") as f:
        toks = list(tokenize.tokenize(io.BytesIO(f.read()).readline))
    for tk in toks:
        if tk.type == tokenize.NUMBER:
            assert "." not in tk.string and "e" not in tk.string.lower()
        if tk.type == tokenize.NAME:
            assert tk.string != "float"
        if tk.type == tokenize.OP:
            assert tk.string != "/"                              # no division at all


def test_readout_does_not_change_the_committed_modules():
    # T6v: space.py / cycle.py got optional parameters (defaults proved byte-identical in test_variants.py)
    r = subprocess.run(["git", "status", "--porcelain", "verantyx/line3/geometry.py",
                        "verantyx/line3/energy.py", "verantyx/line3/placement.py"],
                       cwd=ROOT, capture_output=True, text=True)
    assert r.stdout.strip() == ""
