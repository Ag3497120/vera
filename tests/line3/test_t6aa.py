"""T6aa tests (L-190..L-193): the answer of a list = the words common to ALL entries (minus the query's own units
and the entries' centres); the list stays for the user's choice; empty common answer = the list stays a plain list;
`common=None` is the T6z behaviour byte for byte; trace check of the common answer; determinism."""
import dataclasses
import os
import subprocess
import sys
from fractions import Fraction as Fr

import pytest

from verantyx.line3 import cycle as cy
from verantyx.line3 import readout as ro
from verantyx.line3 import trace_check as tc
from test_readout import HUB, ROOT, TOY2, ctx_for, tier
from test_t6z import X, Y, W, S


def run(states, units=("zz",), **kw):
    t = tier(HUB)
    return t, ro.read_out(cy.TierFacts(t), ctx_for(units), states, question="q", window=0, **kw)


def test_common_answer_is_the_intersection_minus_query_units_and_centres():
    t, a = run([X, Y, W])                                  # entries {a0,a1,c} and {a0,a2,c}
    assert a.verdict == cy.CHOICE and len(a.entries) == 2 and a.common_mode == "intersection"
    c = a.common
    assert c.intersection == ("a0", "c") and c.query_units == ("zz",) and c.centres == ("c",)
    assert c.words == ("a0",)                              # c is the centre, removed
    o = a.answer_obj()
    assert o["verdict"] == cy.CHOICE and o["listed"] == 2 and len(o["entries"]) == 2          # the list is kept
    assert o["answer"]["form"] == "common_words" and o["answer"]["path_words"] == ["a0"]
    assert o["common"]["words"] == ["a0"] and o["centre"] is None and o["paths"] is None
    # every common word traces to sentences in EVERY entry (one tuple per entry, non-empty, union = source_sids)
    per = c.word_sources("a0")
    assert len(per) == 2 and all(per) and o["answer"]["source_sids"] == sorted({s for ss in per for s in ss})
    assert tc.trace_readout(t, a)[1].ok


def test_query_units_are_removed_from_the_common_answer_and_an_empty_one_leaves_a_plain_list():
    t, a = run([X, Y, W], units=("a0",))                   # a0 is the question's own unit (attached in the cycle)
    assert a.common.intersection == ("a0", "c") and a.common.query_units == ("a0",)
    assert a.common.words == () and a.verdict == cy.CHOICE
    o = a.answer_obj()
    assert o["answer"] is None and o["common"]["words"] == [] and len(o["entries"]) == 2      # abstention for grading
    assert tc.trace_readout(t, a)[1].ok
    # disjoint entries: empty intersection
    _, b = run([S("P", ["a0", None, None, None, None, None]), S("Q", ["a1", None, None, None, None, None])])
    assert b.common.intersection == ("c",) and b.common.words == () and b.answer_obj()["answer"] is None


def test_centres_of_all_entries_are_removed_even_when_only_one_arrangement_has_them():
    def item(centre, words):
        return ro.AnswerItem(centre, (ro.AnswerPath(0, "q", words, ((words[0], words[-1], (0,)),)),), Fr(1, 2), (0,))
    e1 = ro._make_entry((item("x", ("a", "m", "x")), item("m", ("a", "x", "m"))))      # centres m and x
    e2 = ro._make_entry((item("a", ("m", "x", "a")),))
    c = ro.make_common([e1, e2], ["q"])
    assert c.intersection == ("a", "m", "x") and c.centres == ("a", "m", "x") and c.words == ()
    e3 = ro._make_entry((item("k", ("a", "m", "x", "k")),))
    c3 = ro.make_common([e1, e3], ["q"])
    assert c3.intersection == ("a", "m", "x") and c3.centres == ("k", "m", "x") and c3.words == ("a",)


def test_a_single_entry_has_no_common_answer_and_is_unchanged():
    t, a = run([X, Y])
    assert a.verdict == cy.ANSWER and a.common is None
    o = a.answer_obj()
    assert "common" not in o and o["answer"]["path_words"] == ["a0", "a1", "c"]
    _, none = run([X, Y], common=None)
    assert none.answer_obj() == {k: v for k, v in o.items() if k != "common_mode"}


def test_common_none_is_exactly_the_t6z_object_and_the_default_only_adds_the_common_fields():
    _, new = run([X, Y, W])
    _, old = run([X, Y, W], common=None)
    oo, no = old.answer_obj(), new.answer_obj()
    assert "common" not in oo and "common_mode" not in oo and oo["answer"] is None and old.common is None
    strip = {k: v for k, v in no.items() if k not in ("common", "common_mode")}
    strip["answer"] = None
    assert strip == oo                                       # nothing else changed
    assert old.thought_obj() == new.thought_obj()
    with pytest.raises(ValueError):
        run([X], common="union")


def test_no_order_bias():
    def shape(a):          # origins are indexes into the state order (a label); the common answer is not
        o = a.answer_obj()
        return o["answer"], o["common"], [(e["words"], e["count"]) for e in o["entries"]]
    ref_ = shape(run([X, Y, W])[1])
    for perm in ([Y, X, W], [W, Y, X], [Y, W, X]):
        assert shape(run(perm)[1]) == ref_


def test_trace_check_catches_a_wrong_common_answer():
    t, a = run([X, Y, W])
    c = a.common

    def bad(**kw):
        return not tc.trace_readout(t, dataclasses.replace(a, common=dataclasses.replace(c, **kw)))[1].ok
    assert bad(words=("a0", "a1"), sources=c.sources + (("a1", ((0,), (0,))),))      # a1 is not in every entry
    assert bad(words=()) is True                                                     # sources no longer match
    assert bad(intersection=("a0",))
    assert bad(centres=())
    assert bad(query_units=())                                                       # attached unit not listed
    assert bad(sources=(("a0", ((), c.word_sources("a0")[1])),))                     # no source in an entry
    assert bad(sources=(("a0", ((99,), c.word_sources("a0")[1])),))                  # a sentence that is not its source
    assert bad(sources=(("a0", (c.word_sources("a0")[0],)),))                        # one entry missing
    assert not tc.trace_readout(t, dataclasses.replace(a, common=None))[1].ok       # the list lost its common record
    _, one = run([X, Y])
    assert not tc.trace_readout(t, dataclasses.replace(one, common=c))[1].ok        # not a list
    assert not tc.trace_readout(t, dataclasses.replace(a, common_mode=None))[1].ok  # present without the option
    _, off = run([X, Y, W], common=None)
    assert tc.trace_readout(t, off)[1].ok


def test_real_space_common_answer_traces_100_percent():
    from verantyx.line3 import placement as pl
    from verantyx.line3.space import build_space, load_jsonl
    sp = build_space(load_jsonl(os.path.join(ROOT, "experiments/line3/data/S300.jsonl"))[:60])
    t = sp.tiers["RUN"]
    res = cy.ask_tier(t, "半田岩はどこにありますか", pl.Placer(t, pl.Budget(40, 200)), budget=cy.QueryBudget(32, 8))
    if res.candidates:
        a = ro.read_out_result(t, res)
        assert tc.trace_readout(t, a)[1].ok
        assert a.common_mode == "intersection"
        assert ro.read_out_result(t, res, common=None).common is None


_SCRIPT = r"""
import sys, hashlib
sys.path.insert(0, %r); sys.path.insert(0, %r)
from verantyx.line3 import cycle as cy, placement as pl, readout as ro, trace_check as tc
from test_t6aa import X, Y, W, run, tier
from test_readout import TOY2
h = hashlib.sha256()
for sts, u in (([X, Y, W], ("zz",)), ([W, Y, X], ("a0",)), ([X, Y], ("zz",)), ([X], ("zz",))):
    t, a = run(sts, units=u)
    h.update(a.to_bytes()); h.update(repr(tc.trace_readout(t, a)[1]).encode())
t = tier(TOY2); P = pl.Placer(t)
for q in (("E", "F"), ("A", "B", "C")):
    res = cy.ask_tier(t, "", P, units=q)
    if res.candidates:
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
