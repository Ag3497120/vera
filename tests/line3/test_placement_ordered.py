"""F1 tests (L-460..): placement option group_insert="ordered" -- the members of a tied share-group
are inserted one at a time in the recorded order of the seed's sentences, settling after each; a member
that hits the budget is restored away and growth stops there.  Default ("whole", L-72) is untouched."""
import ast
import io
import os
import subprocess
import sys
import tokenize

import pytest

from verantyx.line3 import placement as pl
from test_placement import tier, TOYS

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PY = sys.executable

BIG = ["S a b c d e f g h i j", "a b", "c d x"]       # S's only sentence is 10 words: one tied group of 10
TIGHT = pl.Budget(max_class=200, max_states=300, max_moves=5000)
MID = pl.Budget(max_class=200, max_states=1500)
ORD = ["S a b c d e f g h", "S a b", "S z a", "q S z y"]


def test_default_is_whole_and_json_has_no_new_keys():
    t = tier(TOYS[0])
    for u in t.units():
        a = pl.build_cross(t, u)
        b = pl.build_cross(t, u, group_insert="whole")
        assert a.to_bytes() == b.to_bytes()
        assert a.group_insert == "whole" and a.order_log == ()
        assert "order_log" not in a.to_json_obj() and "group_insert" not in a.to_json_obj()
    assert pl.Placer(t).group_insert == "whole"


def test_bad_options_raise():
    t = tier(TOYS[0])
    with pytest.raises(ValueError):
        pl.build_cross(t, "A", group_insert="x")
    with pytest.raises(ValueError):
        pl.build_cross(t, "A", order="x")


def test_group_order_is_sentence_word_order():
    t = tier(ORD)
    # share 3: a; share 2: b (sentence 0) then z (sentence 2); share 1: rest of sentence 0, then q, y of sentence 3
    p = pl.build_cross(t, "S", budget=MID, group_insert="ordered")
    assert p.order_log == ((3, ("a",)), (2, ("b", "z")), (1, ("c", "d", "e", "f", "g", "h", "q", "y")))
    assert pl.group_order(t, "S", ("z", "b")) == ("b", "z")             # input order is irrelevant
    assert pl.group_order(t, "S", ("y", "q", "c"), reverse=True) == ("y", "q", "c")
    assert pl.group_order(t, "S", ("y", "q", "c")) == ("c", "q", "y")


def test_group_order_uses_first_occurrence_and_earliest_sentence():
    t = tier(["S b a b", "x S a", "S b"])        # sentence 0 holds b first (repeat ignored), a second
    assert pl.group_order(t, "S", ("a", "b")) == ("b", "a")
    t2 = tier(["x S z", "S y z"])                 # z first appears in sentence 0, y only in 1
    assert pl.group_order(t2, "S", ("y", "z")) == ("z", "y")


def test_ordered_matches_whole_when_every_group_is_one_unit():
    t = tier(["S a", "S a", "S b", "a b"])
    for u in t.units():
        a = pl.build_cross(t, u)
        b = pl.build_cross(t, u, group_insert="ordered")
        assert a.members == b.members and a.size == b.size and a.stop == b.stop
        assert a.L == b.L and a.score == b.score


def test_ordered_not_a_bare_seed_where_whole_is():
    t = tier(BIG)
    w = pl.build_cross(t, "S", budget=TIGHT)
    o = pl.build_cross(t, "S", budget=TIGHT, group_insert="ordered")
    assert w.size == 1 and w.stop == "budget"            # the cause: the whole group blows the budget
    assert o.size > 1 and o.size == 1 + (10 - o.left_in_group)
    assert o.stop == "budget" and o.left_in_group >= 1 and o.left_after == 0
    assert o.broke_on is not None and len(o.broke_on.units) == 1


def test_stop_before_collapse_restores_exactly_the_previous_state(monkeypatch):
    t = tier(BIG)
    o = pl.build_cross(t, "S", budget=TIGHT, group_insert="ordered")
    done = 10 - o.left_in_group
    seq = o.order_log[-1][1]
    # an independent route to "the state just before the collapsing member": the same build with the
    # group cut to the members that were inserted (the budget never changes earlier steps)
    real = pl.group_order
    monkeypatch.setattr(pl, "group_order", lambda *a, **k: real(*a, **k)[:done])
    ref = pl.build_cross(t, "S", budget=pl.Budget(max_class=1000, max_states=20000, max_moves=400000),
                         group_insert="ordered", max_groups=1)
    assert ref.members == o.members and ref.L == o.L and ref.size == o.size
    assert ref.score == o.score and ref.twin_sets == o.twin_sets
    assert [s.units for s in ref.steps] == [s.units for s in o.steps if s.status == "stable"]
    # the units seated are the seed and the first `done` of the recorded order
    placed = {u for s in o.steps if s.status == "stable" for u in s.units}
    assert placed == set(seq[:done])
    assert o.broke_on.units == (seq[done],)


def test_recorded_order_is_in_the_output():
    t = tier(ORD)
    p = pl.build_cross(t, "S", budget=MID, group_insert="ordered")
    d = p.to_json_obj()
    assert d["group_insert"] == "ordered" and d["order"] == "forward"
    assert d["order_log"][1] == [2, ["b", "z"]]
    assert d["left_in_group"] == 0 and d["left_after"] == 0
    # the steps are one per member, in that order
    assert [s.units[0] for s in p.steps] == [u for _, g in p.order_log for u in g]
    pr = pl.build_cross(t, "S", budget=MID, group_insert="ordered", order="reverse")
    assert pr.order_log[1] == (2, ("z", "b")) and pr.order == "reverse"
    assert pr.to_json_obj()["order"] == "reverse"
    assert pl.Placer(t, MID, group_insert="ordered", order="reverse").cross_for("S").order == "reverse"


def test_left_after_counts_later_groups():
    t = tier(["S a b c d e f g h i j", "S k", "S k"])      # groups: k (share 2), then 10 units (share 1)
    p = pl.build_cross(t, "S", budget=pl.Budget(max_class=200, max_states=300, max_moves=2500), group_insert="ordered")
    assert p.stop == "budget"
    assert p.size - 1 + p.left_in_group + p.left_after == p.candidates


def test_a_stop_in_an_earlier_group_leaves_the_later_groups_out():
    # groups: a..j (share 2, breaks inside), then k, m (share 1): k and m are never inserted (L-463)
    t = tier(["S a b c d e f g h i j", "S a b c d e f g h i j", "S k m", "k m x"])
    p = pl.build_cross(t, "S", budget=pl.Budget(max_class=200, max_states=300, max_moves=2500), group_insert="ordered")
    assert p.stop == "budget" and p.left_after == 2 and p.left_in_group >= 1
    assert len(p.order_log) == 1 and p.order_log[0][0] == 2
    placed = {u for s in p.steps if s.status == "stable" for u in s.units}
    assert not placed & {"k", "m"}
    assert p.steps[-1] is p.broke_on
    assert p.size - 1 + p.left_in_group + p.left_after == p.candidates


@pytest.mark.parametrize("sents", TOYS + [ORD, BIG])
def test_every_closed_state_is_a_fixed_point(sents):
    t = tier(sents)
    for b in (MID, TIGHT):
        for u in t.units():
            for order in ("forward", "reverse"):
                p = pl.build_cross(t, u, budget=b, group_insert="ordered", order=order)
                if p.expanded_size > 3000:
                    continue
                rep = pl.verify_class(t, p.crosses())
                assert rep.one_key and rep.members_fixed_points and rep.closed and rep.is_stable_class


def test_order_keeps_the_size_when_it_all_fits():
    # only the size (and so the unit set) is order-free when every member fits; the settled class itself
    # can depend on the order (S300 RUN '竜游県': forward key (21,16), reverse (21,12), both exhausted)
    t = tier(ORD)
    a = pl.build_cross(t, "S", budget=MID, group_insert="ordered")
    b = pl.build_cross(t, "S", budget=MID, group_insert="ordered", order="reverse")
    assert a.size == b.size == 12 and a.order_log != b.order_log


HASH_SCRIPT = r"""
import sys
sys.path.insert(0, %r); sys.path.insert(0, %r)
from test_placement import tier
from verantyx.line3 import placement as pl
import hashlib
t = tier(%r)
b = pl.Budget(max_class=200, max_states=300, max_moves=5000)
out = []
for order in ("forward", "reverse"):
    out.append(pl.serialize_all({u: pl.build_cross(t, u, budget=b, group_insert="ordered", order=order) for u in t.units()}))
print(hashlib.sha256(b"|".join(out)).hexdigest())
"""


def test_hash_seed_independent():
    code = HASH_SCRIPT % (ROOT, os.path.join(ROOT, "tests", "line3"), BIG + ORD)
    res = set()
    for hs in ("0", "1", "12345"):
        env = dict(os.environ, PYTHONHASHSEED=hs)
        r = subprocess.run([PY, "-c", code], capture_output=True, text=True, env=env, cwd=ROOT)
        assert r.returncode == 0, r.stderr
        res.add(r.stdout.strip())
    assert len(res) == 1


def test_no_float_in_the_new_code():
    src = open(os.path.join(ROOT, "verantyx", "line3", "placement.py"), encoding="utf-8").read()
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant):
            assert not isinstance(node.value, float)
        if isinstance(node, ast.Name):
            assert node.id != "float"
    toks = [t for t in tokenize.generate_tokens(io.StringIO(src).readline)
            if t.type == tokenize.NUMBER and ("." in t.string or "e" in t.string.lower()) and not t.string.lower().startswith("0x")]
    assert toks == []
    t = tier(ORD)
    d = pl.build_cross(t, "S", budget=MID, group_insert="ordered").to_json_obj()

    def walk(x):
        if isinstance(x, float):
            raise AssertionError("float in output")
        if isinstance(x, dict):
            [walk(v) for v in x.values()]
        if isinstance(x, list):
            [walk(v) for v in x]
    walk(d)
