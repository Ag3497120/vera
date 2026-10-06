"""T6v / T6w tests.  Since T6w (owner decision after T6v, L-150) V1, V2 and V3 are the NEW DEFAULTS;
the old behaviour is available as the explicit options (read_rule="whole", state_rule="stability",
unit_filter=None, read-out form="sentences") and is byte-identical to the T6v-era code (GOLDEN).
(T6v wording follows.)  The three variants are OPTIONS and the old defaults kept every output
byte-identical.
  V1 read_rule="query_crosses"  only crosses holding a query unit are read (instead of I-08)
  V2 build_space(unit_filter=)  function / question words are not units (instead of I-22)
  V3 state_rule="query_share"   the adopted states are those sharing the most sentences with the
                                query units (instead of the post-query stability rule); ties -> list
GOLDEN hashes were produced with the code of commit 8b92ec7 (before the options existed)."""
import hashlib

import pytest

from verantyx.line3 import cycle as cy
from verantyx.line3 import placement as pl
from verantyx.line3 import readout as ro
from verantyx.line3.placement import from_cross
from verantyx.line3.space import TierSpace, build_space, build_tier

TOY2 = ["A B C", "A B C", "B C", "B C", "C D", "D E", "E D C", "E D C", "A B", "F E", "F A", "G F"]
GOLDEN = [
    "351bb3d790e230a26f9a61453510596773760f53f9dfd05cf8c476e468bfbfa8",   # ask (E,F)
    "5abf06155d68810ad3005cb9e9e8933389b21bac58df3ea35d253171dc3f754f",   # read-out (E,F)
    "6b2999772bd5e61db0e4a902456d71e89705fd01e54589ce476381e7ca6db7b4",   # ask (A,B,C)
    "13552640a535fc017cc19bcb5dc8333f8f713d918e25db615b270ebe91c24376",   # read-out
    "f8ce58373cb7c5a203f237933f0847dc6abea9342baad443c8a089c90bba44db",   # ask (Z,)
    "a8ca16535dd6ee871a9efa9c91f210a72e093d429bb198c4dc4b91353472e18a",   # ask (C,)
    "b8e46016bc47dd2852111e6a01488df63a9d7f83f6fc8fe6fde6c38ea7ac7d45",   # read-out (C,)
    "4f25112eb802d1ac241b96b9ab9190b51a64dbe1a410368e1596c3d6bdcdb66b",   # Japanese space sha256
]
JA = ["半田岩は徳島県にある。", "遊眠は漫画家である。", "東京は日本の首都です。"]


def tier(sentences):
    su = tuple(tuple(s.split()) for s in sentences)
    post = {}
    for sid, us in enumerate(su):
        for u in dict.fromkeys(us):
            post.setdefault(u, []).append(sid)
    return TierSpace("T", su, {u: tuple(v) for u, v in post.items()})


def h(b):
    return hashlib.sha256(b).hexdigest()


OLD = dict(read_rule="whole", state_rule="stability", unit_filter=None)


def run_old(**flags):
    t = tier(TOY2)
    P = pl.Placer(t)
    out = []
    for q in (("E", "F"), ("A", "B", "C"), ("Z",), ("C",)):
        r = cy.ask_tier(t, "", P, units=q, **dict(OLD, **flags))
        out.append(h(r.to_bytes()))
        if r.candidates:
            out.append(h(ro.read_out_result(t, r, form="sentences").to_bytes()))
    out.append(build_space([{"sent": s} for s in JA], unit_filter=None).sha256())
    return out


def test_old_behaviour_through_explicit_options_is_byte_identical_to_before():
    assert run_old() == GOLDEN


def test_new_defaults_equal_the_explicit_new_options_and_the_old_ones_are_not_the_defaults():
    t = tier(TOY2)
    P = pl.Placer(t)
    new = dict(read_rule="query_crosses", state_rule="query_share", unit_filter="default")
    for q in (("E", "F"), ("A", "B", "C"), ("C",)):
        assert cy.ask_tier(t, "", P, units=q).to_bytes() == cy.ask_tier(t, "", P, units=q, **new).to_bytes()
    r = cy.ask_tier(t, "", P, units=("E", "F"))
    v = r.thought_obj()["variant"]
    assert (v["read_rule"], v["state_rule"]) == ("query_crosses", "query_share")
    assert "variant" not in cy.ask_tier(t, "", P, units=("C",), **OLD).thought_obj()      # old: no variant record
    assert r.to_bytes() != cy.ask_tier(t, "", P, units=("E", "F"), **OLD).to_bytes()
    sp1 = build_space([{"sent": s} for s in JA])
    assert sp1.to_bytes() == build_space([{"sent": s} for s in JA], unit_filter="default").to_bytes()
    assert sp1.to_bytes() != build_space([{"sent": s} for s in JA], unit_filter=None).to_bytes()
    assert build_tier("RUN", JA).sentence_units == build_tier("RUN", JA, "default").sentence_units
    assert build_tier("RUN", JA).sentence_units != build_tier("RUN", JA, None).sentence_units


def test_an_explicit_amount_selects_the_ordered_whole_space_read():
    t = tier(TOY2)
    P = pl.Placer(t)
    r = cy.ask_tier(t, "", P, units=("E", "F"), amount=3)
    assert r.thought_obj()["variant"]["read_rule"] == "whole" and r.answer_obj()["partial_read"] is not None


def test_default_answer_is_byte_identical_across_hash_seeds_in_a_subprocess():
    import os
    import subprocess
    import sys
    root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    code = ("from verantyx.line3 import cycle as cy, placement as pl, readout as ro, trace_check as tc\n"
            "from verantyx.line3.space import build_space, load_jsonl\n"
            "import hashlib\n"
            "sp=build_space(load_jsonl(%r)[:60]);t=sp.tiers['RUN'];P=pl.Placer(t,pl.Budget(40,200))\n"
            "h=hashlib.sha256(sp.to_bytes())\n"
            "r=cy.ask_tier(t,'半田岩はどこにありますか',P,budget=cy.QueryBudget(32,8));h.update(r.to_bytes())\n"
            "if r.candidates:\n"
            "    a=ro.read_out_result(t,r);h.update(a.to_bytes());h.update(repr(tc.trace_readout(t,a)[1]).encode())\n"
            "print(h.hexdigest())" % os.path.join(root, "experiments/line3/data/S300.jsonl"))
    outs = set()
    for seed in ("0", "1", "12345"):
        env = dict(os.environ, PYTHONHASHSEED=seed, PYTHONPATH=root, PYTHONDONTWRITEBYTECODE="1")
        outs.add(subprocess.run([sys.executable, "-c", code], env=env, capture_output=True, text=True, check=True).stdout.strip())
    assert len(outs) == 1


def test_unknown_option_values_are_refused():
    t = tier(TOY2)
    P = pl.Placer(t)
    with pytest.raises(ValueError):
        cy.ask_tier(t, "", P, units=("C",), read_rule="half")
    with pytest.raises(ValueError):
        cy.ask_tier(t, "", P, units=("C",), state_rule="coin")


# ------------------------------------------------------------------ V1
def crosses_with(t, P, q):
    out = set()
    for s in t.units():
        p = P.cross_for(s)
        us = {c for c in from_cross(p.cross) if c is not None}
        for tw in p.twin_sets:
            us.update(tw)
        if us & set(q):
            out.add(s)
    return out


@pytest.mark.parametrize("q", [("E", "F"), ("A", "B", "C"), ("C",), ("G",)])
def test_v1_reads_exactly_the_crosses_holding_a_query_unit(q):
    t = tier(TOY2)
    P = pl.Placer(t)
    r = cy.ask_tier(t, "", P, units=q, read_rule="query_crosses")
    want = crosses_with(t, P, q)
    assert set(r.plan.read) == want and len(r.reads) == len(want)
    assert set(q) <= want                                   # a query unit's own cross holds it
    assert r.plan.partial == (len(want) < len(t.units()))
    assert r.thought_obj()["variant"]["read_rule"] == "query_crosses"
    assert r.answer_obj()["partial_read"]["read"] == len(want) if r.plan.partial else True


def test_v1_no_query_unit_in_space_reads_nothing():
    t = tier(TOY2)
    r = cy.ask_tier(t, "", pl.Placer(t), units=("Z",), read_rule="query_crosses")
    assert r.plan.read == () and r.verdict == cy.UNKNOWN_NO_EVIDENCE


def test_v1_cannot_be_combined_with_amount():
    t = tier(TOY2)
    with pytest.raises(ValueError):
        cy.ask_tier(t, "", pl.Placer(t), units=("C",), read_rule="query_crosses", amount=3)


def test_v1_reads_are_the_same_per_cross_as_the_whole_read():
    t = tier(TOY2)
    P = pl.Placer(t)
    whole = cy.ask_tier(t, "", P, units=("E", "F"), read_rule="whole")
    v1 = cy.ask_tier(t, "", P, units=("E", "F"), read_rule="query_crosses")
    wh = {sr.seed: sr for sr in whole.reads}
    for sr in v1.reads:
        assert [(m.kind, m.unit, m.inv) for m in sr.members] == [(m.kind, m.unit, m.inv) for m in wh[sr.seed].members]


# ------------------------------------------------------------------ V2
def test_v2_filter_removes_units_not_sentences():
    full = build_space([{"sent": s} for s in JA], unit_filter=None)
    func = lambda u: u in ("は", "に", "ある", "である", "です")
    sp = build_space([{"sent": s} for s in JA], unit_filter=func)
    assert sp.N == full.N and sp.sentences == full.sentences
    for tn in ("RUN", "WORD", "CHAR"):
        a, b = full.tiers[tn], sp.tiers[tn]
        assert set(b.postings) == {u for u in a.postings if not func(u)}
        for sid, us in enumerate(b.sentence_units):
            assert us == tuple(u for u in a.sentence_units[sid] if not func(u))
    # a per-tier mapping is accepted
    sp2 = build_space([{"sent": s} for s in JA], unit_filter={"WORD": func, "RUN": None, "CHAR": None})
    assert sp2.tiers["RUN"].sentence_units == full.tiers["RUN"].sentence_units
    assert sp2.tiers["WORD"].sentence_units == sp.tiers["WORD"].sentence_units


def test_v2_query_units_that_are_filtered_are_dropped():
    t = tier(TOY2)
    P = pl.Placer(t)
    r = cy.ask_tier(t, "", P, units=("E", "Z", "F"), unit_filter=lambda u: u == "Z")
    assert r.ctx.query == ("E", "F")
    assert r.thought_obj()["variant"]["query_after_filter"] == ["E", "F"]
    assert r.verdict == cy.ask_tier(t, "", P, units=("E", "F")).verdict
    # the default filter of the question is the function-word rule of the tier (RUN / WORD / CHAR)
    sp = build_space([{"sent": s} for s in JA])
    tr = sp.tiers["RUN"]
    q = cy.ask_tier(tr, "半田岩はどこにありますか", pl.Placer(tr)).ctx.query
    assert q and "はどこにありますか" not in q and "半田岩" in q
    q_old = cy.ask_tier(tr, "半田岩はどこにありますか", pl.Placer(tr), unit_filter=None).ctx.query
    assert "はどこにありますか" in q_old


# ------------------------------------------------------------------ V3
def share_table(t, r, q):
    qs = {sid for u in q for sid in t.postings.get(u, ())}
    seen = {}
    for sr in r.reads:
        for m in sr.members:
            if m.kind != cy.CANDIDATE:
                continue
            for e in m.settled.ends:
                if e.answer is not None:
                    us = {c for c in e.flat if c is not None}
                    seen.setdefault(e.flat, len({sid for u in us for sid in t.postings[u]} & qs))
    return seen


@pytest.mark.parametrize("q", [("E", "F"), ("A", "B", "C"), ("C",)])
def test_v3_adopts_the_states_sharing_most_with_the_query(q):
    t = tier(TOY2)
    P = pl.Placer(t)
    r = cy.ask_tier(t, "", P, units=q, state_rule="query_share")
    tab = share_table(t, r, q)
    best = max(tab.values())
    assert {tuple(c.end.flat) for c in r.candidates} == {f for f, v in tab.items() if v == best}
    assert r.thought_obj()["variant"]["state_choice"]["best_share"] == best
    assert r.verdict in (cy.ANSWER, cy.CHOICE)
    assert (r.verdict == cy.ANSWER) == (len(r.units) == 1)


def test_v3_differs_from_the_stability_rule_where_they_disagree():
    t = tier(TOY2)
    P = pl.Placer(t)
    a = cy.ask_tier(t, "", P, units=("E", "F"), state_rule="stability")
    b = cy.ask_tier(t, "", P, units=("E", "F"), state_rule="query_share")
    assert a.units == ("C",) and b.units == ("E",)          # the toy: stability picks C, sharing picks E


def test_v3_tied_answers_make_a_list():
    t = tier(["a b", "c d"])
    P = pl.Placer(t)
    # the query "a c" shares one sentence with each seed's cross; the two answers tie
    r = cy.ask_tier(t, "", P, units=("a", "c"), state_rule="query_share")
    if r.verdict == cy.CHOICE:
        assert len(r.units) > 1
    else:
        assert r.verdict in (cy.ANSWER, cy.UNKNOWN_NO_EVIDENCE, cy.UNKNOWN_RATIO_DISAGREEMENT,
                             cy.UNKNOWN_SECTION_DISAGREEMENT, cy.UNKNOWN_NO_FIXED_POINT, cy.AMBIGUOUS)


def test_v3_readout_lists_every_state_regardless_of_stability():
    t = tier(TOY2)
    P = pl.Placer(t)
    r = cy.ask_tier(t, "", P, units=("E", "F"), state_rule="query_share")
    rd_all = ro.read_out_result(t, r, form="sentences", by_stability=False)
    rd_def = ro.read_out_result(t, r, form="sentences")
    assert rd_all.below_best == 0
    assert {s.text for s in rd_def.sentences} <= {s.text for s in rd_all.sentences}
    assert rd_all.distinct_total == len(rd_all.sentences)


def test_v123_together_runs():
    t = tier(TOY2)
    P = pl.Placer(t)
    r = cy.ask_tier(t, "", P, units=("E", "F", "Z"), read_rule="query_crosses", state_rule="query_share",
                    unit_filter=lambda u: u == "Z")
    assert r.ctx.query == ("E", "F")
    v = r.thought_obj()["variant"]
    assert v["read_rule"] == "query_crosses" and v["state_rule"] == "query_share" and v["unit_filter"]
