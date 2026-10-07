"""T6z tests (L-180..L-183): the owner's defaults merge_sections=True, similar="word_set" (items using the SAME SET of
words are one list entry carrying all its arrangements; no representative), on-demand budget raise; the old
behaviour through explicit options; trace check on entries; determinism; exact arithmetic."""
import dataclasses
import os
import subprocess
import sys
from fractions import Fraction as Fr

import pytest

from verantyx.line3 import cycle as cy
from verantyx.line3 import readout as ro
from verantyx.line3 import trace_check as tc
from test_readout import HUB, ROOT, TOY2, ctx_for, flat_with, ref, tier


def fl(legs):
    return ("c",) + tuple(legs)


def S(name, legs, stab=Fr(1, 2)):
    return ro.StateRef("T", name, 0, fl(legs), stab, "c", 0)


X = S("X", ["a0", "a1", None, None, None, None], Fr(1, 3))
Y = S("Y", ["a0", "a1", "a0", None, None, None], Fr(2, 3))        # same words as X, the multiset of paths differs
W = S("W", ["a0", "a2", None, None, None, None])


def run(states, **kw):
    t = tier(HUB)
    return t, ro.read_out(cy.TierFacts(t), ctx_for(), states, question="q", window=0, **kw)


def test_defaults_are_the_new_ones_and_the_old_ones_are_explicit_options():
    t, a = run([X, Y, W])
    assert a.merge_sections is True and a.similar == "word_set"
    _, b = run([X, Y, W], merge_sections=True, similar="word_set")
    assert a.to_bytes() == b.to_bytes()
    _, old = run([X, Y, W], merge_sections=False, similar=None, common=None)
    assert len(old.items) == len(old.entries) == 3 and old.similar is None and not old.merge_sections
    o = old.answer_obj()
    assert "entries" not in o and "similar" not in o and "merge_sections" not in o        # the previous object
    _, t6y = run([X, Y, W], merge_sections=True, similar=None, common=None)
    assert t6y.answer_obj()["merge_sections"] is True and "entries" not in t6y.answer_obj()
    with pytest.raises(ValueError):
        run([X], similar="jaccard")


def test_same_word_set_items_are_one_entry_with_all_arrangements_and_the_union_of_origins():
    t, a = run([X, Y, W])
    assert len(a.items) == 3 and len(a.entries) == 2 and a.verdict == cy.CHOICE
    e = a.entries[0]
    assert e.words == ("a0", "a1", "c") and e.count == 2 and e.origins == (0, 1) and e.centres == ("c",)
    assert e.stability == Fr(2, 3) and isinstance(e.stability, Fr)
    assert sorted(len(p) for p in (x.paths for x in e.arrangements)) == [2, 3]                  # both kept
    assert a.entries[1].words == ("a0", "a2", "c") and a.entries[1].count == 1
    o = a.answer_obj()
    assert o["listed"] == 2 and o["arrangements"] == 3 and len(o["entries"]) == 2
    assert o["entries"][0]["count"] == 2 and len(o["entries"][0]["arrangements"]) == 2
    assert o["answer"] is None and o["centre"] is None                               # L-200: default = T6z again
    _, nc = run([X, Y, W], common="intersection")
    assert nc.answer_obj()["answer"]["form"] == "common_words"
    assert a.thought_obj()["counts"]["listed"] == 2


def test_no_order_bias_the_entry_does_not_depend_on_the_order_of_the_states():
    def shape(a):
        return [(e.words, e.count, [it.key for it in e.arrangements], e.stability) for e in a.entries]
    ref_shape = shape(run([X, Y, W])[1])
    for perm in ([Y, X, W], [W, Y, X], [Y, W, X]):
        assert shape(run(perm)[1]) == ref_shape
    # the entry carries no representative: answer path words of a collapsed list = the word set (sorted label)
    _, one = run([X, Y])
    assert one.entries[0].words == tuple(sorted(one.entries[0].words))


def test_a_list_that_collapses_to_one_entry_becomes_an_answer():
    t, a = run([X, Y])
    assert a.verdict == cy.ANSWER and len(a.entries) == 1 and len(a.items) == 2 and not a.too_many
    o = a.answer_obj()
    assert o["verdict"] == cy.ANSWER and o["listed"] == 1 and o["arrangements"] == 2
    assert o["answer"] == {"path_words": ["a0", "a1", "c"], "arrangements": 2, "source_sids": o["answer"]["source_sids"],
                           "reference_centre": "c", "reference_centres": ["c"]}
    assert o["centre"] == "c" and o["paths"] is None                 # two arrangements: no single path list
    assert a.centre == "c"
    _, old = run([X, Y], similar=None, common=None)
    assert old.verdict == cy.CHOICE and len(old.items) == 2
    # one arrangement: the paths are given
    _, single = run([X])
    assert single.answer_obj()["paths"] == single.answer_obj()["entries"][0]["arrangements"][0]["paths"]


def test_entry_with_several_centres_keeps_all_of_them():
    def item(centre, words):
        return ro.AnswerItem(centre, (ro.AnswerPath(0, "q", words),), Fr(1, 2), (0,))
    e = ro._make_entry((item("x", ("a", "x")), item("a", ("x", "a"))))
    assert e.words == ("a", "x") and e.centres == ("a", "x") and e.count == 2
    assert ro.item_words(item("x", ("a", "x"))) == frozenset({"a", "x"}) == ro.item_words(item("a", ("x", "a")))
    # the centre is part of the set even when a path does not hold it
    assert ro.item_words(ro.AnswerItem("z", (ro.AnswerPath(0, "q", ("a",)),), Fr(1), (0,))) == frozenset({"a", "z"})


def test_intake_of_an_entry_is_the_whole_group():
    _, a = run([X, Y, W])
    ad = ro.choose_item(a, 0)
    rec = ad.memory_record()
    assert rec["form"] == "word_set" and rec["words"] == ["a0", "a1", "c"] and len(rec["arrangements"]) == 2
    assert rec["offered"] == 2 and rec["choice_index"] == 0 and rec["origins"] == [0, 1] and rec["base_changed"] is False
    assert rec["stability"] == "2/3"
    assert ad.to_bytes() == ro.choose_item(a, 0).to_bytes()
    with pytest.raises(IndexError):
        ro.choose_item(a, 2)
    with pytest.raises(ValueError):
        ro.adopt_item(a)
    _, one = run([X, Y])
    r1 = ro.adopt_item(one).memory_record()
    assert r1["source"] == "auto" and r1["offered"] == 1 and len(r1["arrangements"]) == 2
    # old options: the old record form
    _, old = run([X, Y, W], merge_sections=False, similar=None, common=None)
    assert ro.choose_item(old, 0).memory_record()["form"] == "centre_paths"


def test_trace_check_on_entries_is_100_percent_and_catches_tampering():
    t, a = run([X, Y, W])
    _, rep = tc.trace_readout(t, a)
    assert rep.ok and rep.sentences_checked == 2 == rep.sentences_ok and rep.fraction == 1
    # words_checked counts the arrangements' path words (2 + 3 + 2 paths of 2 words)
    assert rep.words_checked == 2 * 2 + 3 * 2 + 2 * 2
    _, one = run([X, Y])
    assert tc.trace_readout(t, one)[1].ok
    e = a.entries[0]
    bad_words = dataclasses.replace(e, words=("a0", "a1", "c", "extra"))
    assert not tc.trace_readout(t, dataclasses.replace(a, entries=(bad_words, a.entries[1])))[1].ok
    bad_arr = dataclasses.replace(e, arrangements=e.arrangements[:1])
    assert not tc.trace_readout(t, dataclasses.replace(a, entries=(bad_arr, a.entries[1])))[1].ok          # an item is missing
    bad_org = dataclasses.replace(e, origins=(0,))
    assert not tc.trace_readout(t, dataclasses.replace(a, entries=(bad_org, a.entries[1])))[1].ok
    assert not tc.trace_readout(t, dataclasses.replace(a, entries=(a.entries[1],)))[1].ok                  # items not covered
    # the old options trace as before
    _, old = run([X, Y, W], merge_sections=False, similar=None, common=None)
    assert tc.trace_readout(t, old)[1].ok


def test_too_many_counts_entries_not_arrangements():
    states = [S("s%d" % i, ["a%d" % i, None, None, None, None, None]) for i in range(6)] + [X, Y]
    _, a = run(states, too_many=5)
    assert len(a.items) == 8 and len(a.entries) == 7 and a.too_many                  # 7 entries > 5
    _, b = run(states, too_many=7)
    assert not b.too_many


def test_ask_tier_defaults_to_on_demand_and_none_is_the_old_call():
    t = tier(TOY2)
    from verantyx.line3 import placement as pl
    P = pl.Placer(t)
    d = cy.ask_tier(t, "", P, units=("E", "F"))
    assert d.to_bytes() == cy.ask_tier(t, "", P, units=("E", "F"), raise_budget="on_demand").to_bytes()
    assert d.to_bytes() != cy.ask_tier(t, "", P, units=("E", "F"), raise_budget=None).to_bytes()    # only the variant record
    assert cy.ask_tier(t, "", P, units=("E", "F"), raise_budget=None).to_bytes() == \
        cy._ask_tier_once(t, "", P, units=("E", "F")).to_bytes()
    assert d.thought_obj()["variant"]["budget_raise"]["needed"] is False


_SCRIPT = r"""
import sys, hashlib
sys.path.insert(0, %r); sys.path.insert(0, %r)
from fractions import Fraction as Fr
from verantyx.line3 import cycle as cy, placement as pl, readout as ro, trace_check as tc
from test_t6z import X, Y, W, run, tier
from test_readout import TOY2
h = hashlib.sha256()
for sts in ([X, Y, W], [W, Y, X], [X, Y], [X]):
    t, a = run(sts)
    h.update(a.to_bytes()); h.update(repr(tc.trace_readout(t, a)[1]).encode())
    if a.verdict == cy.CHOICE:
        h.update(ro.choose_item(a, 0).to_bytes())
t = tier(TOY2); P = pl.Placer(t)
for q in (("E", "F"), ("A", "B", "C")):
    res = cy.ask_tier(t, "", P, units=q)
    a = ro.read_out_result(t, res)
    h.update(res.to_bytes()); h.update(a.to_bytes()); h.update(repr(tc.trace_readout(t, a)[1]).encode())
print(h.hexdigest())
"""


def test_byte_identical_across_hash_seeds():
    outs = []
    for seed in ("0", "1", "12345"):
        env = dict(os.environ, PYTHONHASHSEED=seed, PYTHONDONTWRITEBYTECODE="1", PYTHONPATH=ROOT)
        r = subprocess.run([sys.executable, "-c", _SCRIPT % (ROOT, os.path.dirname(os.path.abspath(__file__)))],
                           capture_output=True, text=True, env=env, timeout=900)
        assert r.returncode == 0, r.stderr
        outs.append(r.stdout.strip())
    assert len(set(outs)) == 1 and len(outs[0]) == 64


def test_default_run_on_a_real_space_traces_100_percent_and_entries_partition_the_items():
    from verantyx.line3 import placement as pl
    from verantyx.line3.space import build_space, load_jsonl
    sp = build_space(load_jsonl(os.path.join(ROOT, "experiments/line3/data/S300.jsonl"))[:60])
    t = sp.tiers["RUN"]
    P = pl.Placer(t, pl.Budget(40, 200))
    res = cy.ask_tier(t, "半田岩はどこにありますか", P, budget=cy.QueryBudget(32, 8))
    if res.candidates:
        a = ro.read_out_result(t, res)
        assert tc.trace_readout(t, a)[1].ok
        assert sum(e.count for e in a.entries) == len(a.items)
        assert len({e.words for e in a.entries}) == len(a.entries)
