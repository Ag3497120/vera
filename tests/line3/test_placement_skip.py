"""F1c tests (L-500..): placement option on_collapse="skip" (with group_insert="ordered") -- a member that
hits the budget is restored away, recorded in `skipped`, and growth goes on with the next member of the
recorded order and then the next groups.  Default on_collapse="stop" (L-463) is byte-identical."""
import os
import subprocess
import sys

import pytest

from verantyx.line3 import placement as pl
from test_placement import tier, TOYS
from test_placement_ordered import BIG, ORD, MID, TIGHT

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PY = sys.executable

TWO = ["S a b c d e f g h i j", "S a b c d e f g h i j", "S k m", "k m x"]    # groups: a..j (share 2), k m (share 1)
B_TWO = pl.Budget(max_class=200, max_states=300, max_moves=2500)            # stop: 7 seated; skip: also seats k
B_ORD = pl.Budget(max_class=10, max_states=300, max_moves=2500)             # ORD: stop 8, skip 8 (skipped g h q y) since L-G4-47; before it: skip 9 (q kept at 11 > 10)
B_ORD12 = pl.Budget(max_class=12, max_states=300, max_moves=2500)           # ORD: stop 8, skip 9 (skipped g h y): the original L-502 case, kept


def _placed(p):
    return {u for s in p.steps if s.status == pl.STABLE for u in s.units}


def test_default_is_stop_and_json_has_no_new_keys():
    for sents in TOYS + [ORD, BIG, TWO]:
        t = tier(sents)
        for b in (MID, TIGHT, B_TWO):
            for u in t.units():
                for gi in ("whole", "ordered"):
                    a = pl.build_cross(t, u, budget=b, group_insert=gi)
                    c = pl.build_cross(t, u, budget=b, group_insert=gi, on_collapse="stop")
                    assert a.to_bytes() == c.to_bytes()
                    assert a.on_collapse == "stop" and a.skipped == ()
                    assert "on_collapse" not in a.to_json_obj() and "skipped" not in a.to_json_obj()
    assert pl.Placer(tier(ORD)).on_collapse == "stop"


def test_bad_options_raise():
    t = tier(ORD)
    with pytest.raises(ValueError):                                  # L-500: nothing to skip in a whole group
        pl.build_cross(t, "S", on_collapse="skip")
    with pytest.raises(ValueError):
        pl.build_cross(t, "S", group_insert="whole", on_collapse="skip")
    with pytest.raises(ValueError):
        pl.build_cross(t, "S", group_insert="ordered", on_collapse="x")
    pl.build_cross(t, "S", group_insert="ordered", on_collapse="skip")   # fine


@pytest.mark.parametrize("budget, size, skipped", [
    # L-G4-47 + owner decision 「規則を適用、数え方の差は受け入れる」 (ops/decisions, 2026-10-10): the class built from the terminal arrangements is
    # held to max_class.  At max_class=10 the member q used to be KEPT with a class of 11 (> 10, never checked); it is now refused, so skip seats 8
    # (not 9) and skips g h q y.  The original case (skip seats one more than stop, skipped g h y) is kept at max_class=12.
    (B_ORD, 8, ["g", "h", "q", "y"]),
    (B_ORD12, 9, ["g", "h", "y"]),
])
def test_skip_continues_after_a_collapse_and_records_the_member(budget, size, skipped):
    t = tier(ORD)
    s = pl.build_cross(t, "S", budget=budget, group_insert="ordered")
    k = pl.build_cross(t, "S", budget=budget, group_insert="ordered", on_collapse="skip")
    assert s.stop == "budget" and s.size == 8
    assert k.stop == "exhausted" and k.size == size >= s.size             # L-502 (k.size > s.size at max_class=12 only)
    assert k.on_collapse == "skip"
    seq = [u for _, g in k.order_log for u in g]
    assert [u for _, u, _ in k.skipped] == skipped                       # in the recorded order
    assert all(why in ("max_class", "max_states", "max_moves") for _, _, why in k.skipped)
    assert set(seq) == _placed(k) - {"S"} | {u for _, u, _ in k.skipped}   # every candidate tried once
    # the skipped member is in the steps as a budget step with its reason, in the recorded order
    bad = [st for st in k.steps if st.status == "budget"]
    assert [st.units for st in bad] == [(u,) for u in skipped]
    assert [st.reason for st in bad] == [why for _, _, why in k.skipped]
    assert [st.units[0] for st in k.steps] == seq                        # one step per member, in order
    # up to the first collapse the two builds are the same build (L-503)
    assert k.broke_on == s.broke_on
    n = k.steps.index(k.broke_on)
    assert k.steps[:n + 1] == s.steps
    d = k.to_json_obj()
    assert d["on_collapse"] == "skip" and d["skipped"] == [[sh, u, why] for sh, u, why in k.skipped]
    assert d["stop"] == "exhausted" and d["group_insert"] == "ordered"


def test_a_skipped_member_is_never_seated():
    for sents in (ORD, BIG, TWO):
        t = tier(sents)
        for b in (MID, TIGHT, B_TWO, B_ORD):
            for u in t.units():
                k = pl.build_cross(t, u, budget=b, group_insert="ordered", on_collapse="skip")
                gone = {x for _, x, _ in k.skipped}
                assert not gone & _placed(k)
                shown = {str(k.cross.get(seat)) for seat in pl.seats(k.L) if k.cross.get(seat) is not None}
                assert not gone & shown and not gone & {x for tw in k.twin_sets for x in tw}
                assert k.size == len(_placed(k) | {u})
                assert k.stop == "exhausted" and k.size - 1 + len(k.skipped) == k.candidates
                assert k.left_in_group + k.left_after == len(k.skipped)


def test_skip_in_an_earlier_group_goes_on_with_the_later_groups():
    t = tier(TWO)
    s = pl.build_cross(t, "S", budget=B_TWO, group_insert="ordered")
    k = pl.build_cross(t, "S", budget=B_TWO, group_insert="ordered", on_collapse="skip")
    assert s.stop == "budget" and s.left_after == 2 and len(s.order_log) == 1
    assert len(k.order_log) == 2 and [sh for sh, _ in k.order_log] == [2, 1]
    assert [u for _, u, _ in k.skipped] == ["g", "h", "i", "j", "m"]
    assert "k" in _placed(k) and "m" not in _placed(k)
    assert k.stop == "exhausted" and k.size == 8
    # counts: skipped in the first group that collapsed / in the groups after it (L-504)
    assert (k.left_in_group, k.left_after) == (4, 1)
    assert k.size - 1 + len(k.skipped) == k.candidates


def test_skip_equals_stop_when_nothing_collapses():
    for sents in TOYS + [ORD]:
        t = tier(sents)
        for u in t.units():
            a = pl.build_cross(t, u, budget=MID, group_insert="ordered")
            k = pl.build_cross(t, u, budget=MID, group_insert="ordered", on_collapse="skip")
            if a.stop == "budget":
                continue
            assert k.skipped == () and k.stop == a.stop
            assert (k.members, k.L, k.size, k.score, k.steps, k.order_log) == \
                   (a.members, a.L, a.size, a.score, a.steps, a.order_log)


def test_max_groups_is_still_reported():
    t = tier(TWO)
    k = pl.build_cross(t, "S", budget=MID, group_insert="ordered", on_collapse="skip", max_groups=1)
    assert k.stop == "max_groups"
    k2 = pl.build_cross(t, "S", budget=MID, group_insert="ordered", on_collapse="skip", pool_groups=1)
    assert k2.stop == "max_groups"


def test_kept_class_is_what_the_seated_members_alone_give(monkeypatch):
    # an independent route: the same build with the skipped members taken out of the recorded order and a
    # budget nothing exceeds gives the same class (a restore leaves exactly the state before the member)
    for sents, b in ((ORD, B_ORD), (TWO, B_TWO)):
        t = tier(sents)
        k = pl.build_cross(t, "S", budget=b, group_insert="ordered", on_collapse="skip")
        gone = {u for _, u, _ in k.skipped}
        assert gone
        real = pl.group_order
        monkeypatch.setattr(pl, "group_order", lambda *a, **kw: tuple(u for u in real(*a, **kw) if u not in gone))
        ref = pl.build_cross(t, "S", budget=pl.Budget(max_class=1000, max_states=20000, max_moves=400000),
                             group_insert="ordered")
        monkeypatch.setattr(pl, "group_order", real)
        assert ref.stop == "exhausted"
        assert (ref.members, ref.L, ref.size, ref.score, ref.twin_sets) == \
               (k.members, k.L, k.size, k.score, k.twin_sets)


@pytest.mark.parametrize("sents", TOYS + [ORD, BIG, TWO])
def test_every_kept_class_is_a_fixed_point(sents):
    t = tier(sents)
    for b in (MID, TIGHT, B_TWO, B_ORD):
        for u in t.units():
            for order in ("forward", "reverse"):
                p = pl.build_cross(t, u, budget=b, group_insert="ordered", order=order, on_collapse="skip")
                if p.expanded_size > 3000:
                    continue
                rep = pl.verify_class(t, p.crosses())
                assert rep.one_key and rep.members_fixed_points and rep.closed and rep.is_stable_class


def test_placer_passes_the_option():
    t = tier(ORD)
    # B_ORD12 = the original case (L-G4-47: at max_class=10 skip seats 8, the same as stop)
    p = pl.Placer(t, B_ORD12, group_insert="ordered", on_collapse="skip").cross_for("S")
    assert p.on_collapse == "skip" and p.size == 9
    assert pl.Placer(t, B_ORD12, group_insert="ordered").cross_for("S").size == 8
    assert pl.Placer(t, B_ORD, group_insert="ordered", on_collapse="skip").cross_for("S").size == 8


HASH_SCRIPT = r"""
import sys
sys.path.insert(0, %r); sys.path.insert(0, %r)
from test_placement import tier
from verantyx.line3 import placement as pl
import hashlib
t = tier(%r)
b = pl.Budget(max_class=10, max_states=300, max_moves=2500)
out = []
for order in ("forward", "reverse"):
    out.append(pl.serialize_all({u: pl.build_cross(t, u, budget=b, group_insert="ordered", order=order, on_collapse="skip") for u in t.units()}))
print(hashlib.sha256(b"|".join(out)).hexdigest())
"""


def test_hash_seed_independent():
    code = HASH_SCRIPT % (ROOT, os.path.join(ROOT, "tests", "line3"), BIG + ORD + TWO)
    res = set()
    for hs in ("0", "1", "12345"):
        env = dict(os.environ, PYTHONHASHSEED=hs)
        r = subprocess.run([PY, "-c", code], capture_output=True, text=True, env=env, cwd=ROOT)
        assert r.returncode == 0, r.stderr
        res.add(r.stdout.strip())
    assert len(res) == 1


def test_no_float_in_the_output():
    d = pl.build_cross(tier(TWO), "S", budget=B_TWO, group_insert="ordered", on_collapse="skip").to_json_obj()

    def walk(x):
        if isinstance(x, float):
            raise AssertionError("float in output")
        if isinstance(x, dict):
            [walk(v) for v in x.values()]
        if isinstance(x, list):
            [walk(v) for v in x]
    walk(d)
    assert d["skipped"]        # the skip path is what is walked
