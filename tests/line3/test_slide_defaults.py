"""G3-i tests (L-770..): the owner's defaults of the window placements after G3-h -- arm_cap "budget" (unchanged), z_deep "order" (was "slide"),
seat_empty_axis "deny" (was "allow"); padding "one" at every entrance of the question path (was already so).

What is pinned: the defaults themselves; that a default build equals the build with every value spelled out; that the former defaults stay reachable by
passing the old values (SP.DEFAULTS_G3H, z_deep "slide") and build the former bytes (the G3-c..G3-h tests pin those bytes against the committed
records); that the real corpus' default slide / place spec shas are the ones of the G3-h cache (budget, order, deny); the first fulllead windows with the
independent verifier; the command line's help and default.
"""
import os
import subprocess
import sys

import pytest

from verantyx.line3 import slide as SL
from verantyx.line3 import slide_flat as F
from verantyx.line3 import slide_place as SP
from verantyx.line3 import slide_query as Q
from verantyx.line3 import space as sp

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PY = sys.executable
FL = os.path.join(ROOT, "experiments/line3/bank2/data/fulllead_sents.jsonl")

TOY = [("A", "東京は日本の首都である。"), ("A", "東京は日本の都市である。"), ("B", "犬が猫を追う。"), ("B", "猫が魚を食べる。"), ("C", "京都は古い都である。")]
OWNER = {"stability": "per_axis", "seat_key": "unit_sid", "seat_empty_axis": "deny", "growth": "z_reserved"}
OWNER3 = {"centre_scope": "both", "arm_cap": "budget", "stability_judgement": "strict"}


def toy_rows():
    seen = {}
    out = []
    for t, s in TOY:
        i = seen.get(t, 0)
        seen[t] = i + 1
        out.append({"title": t, "sent": s, "source": "%s#%d" % (t, i)})
    return out


# ==== the values ===================================================================================================
def test_the_defaults_are_the_owners_after_g3h():
    assert SL.DEFAULT_Z_DEEP == "order" and SP.DEFAULTS == OWNER and SP.DEFAULTS3 == OWNER3
    assert SP.DEFAULTS_G3H == dict(OWNER, seat_empty_axis="allow") and set(SP.DEFAULTS_G3H) == set(SP.DEFAULTS)
    # the named former configurations are untouched
    assert SP.LEGACY4 == {"stability": "sum", "seat_key": "unit", "seat_empty_axis": "allow", "growth": "n_then_n1"}
    assert SP.C2_EQUIV == {"centre_scope": "n", "arm_cap": "budget", "stability_judgement": "pareto"}
    assert SP.LEGACY == dict(SP.LEGACY4, **SP.C2_EQUIV)


def test_a_default_spec_equals_the_spec_with_every_value_spelled_out_and_the_former_ones_stay_reachable():
    rows = toy_rows()
    space = sp.build_space(rows)
    d = SL.default_spec(space)
    assert d.z_deep == "order" and d.to_bytes() == SL.default_spec(space, z_deep="order").to_bytes()
    former = SL.default_spec(space, z_deep="slide")
    assert former.z_deep == "slide" and b"deep" not in former.to_bytes() and former.sha256() != d.sha256()
    sl = SL.Slide(space, rows=rows)
    assert sl.spec.to_bytes() == d.to_bytes()
    p = SP.make_spec(sl)
    q = SP.make_spec(sl, **dict(OWNER, **OWNER3))
    assert p.to_bytes() == q.to_bytes() and p.padding == "none"       # the low-level make_spec / place_windows keep padding "none"; every entrance of the question path says "one"
    g3h = SP.make_spec(sl, **dict(SP.DEFAULTS_G3H, **OWNER3))
    assert g3h.sha256() != p.sha256() and g3h.seat_empty_axis == "allow" and g3h.arm_cap == "budget"
    # nothing else differs: the two place specs' docs differ in the switch and its rule text only
    dp, dg = p.doc(), g3h.doc()
    assert {k for k in dp if dp[k] != dg[k]} == {"switches", "rules"}


def test_the_window_index_and_the_question_path_default_to_the_new_values_and_to_padding_one(tmp_path):
    rows = toy_rows()
    space = sp.build_space(rows)
    wi = Q.WindowIndex.from_space(space, None, rows=rows, level="low")
    ex = Q.WindowIndex.from_space(space, None, rows=rows, level="low", padding="one", z_deep="order", place_kw=dict(OWNER, **OWNER3))
    assert wi.z_deep == "order" and wi.spec.seat_empty_axis == "deny" and wi.spec.arm_cap == "budget" and wi.spec.padding == "one"
    assert [w.doc for w in wi.windows] == [w.doc for w in ex.windows] and wi.spec.sha256() == ex.spec.sha256()
    old = Q.WindowIndex.from_space(space, None, rows=rows, level="low", z_deep="slide", place_kw={"seat_empty_axis": "allow"})
    assert old.z_deep == "slide" and old.spec.seat_empty_axis == "allow" and old.spec.sha256() != wi.spec.sha256()
    # the seats and the keys are those of the former default on the toy except where the deeper z edges matter; the record only says what was denied
    assert [w.n for w in old.windows] == [w.n for w in wi.windows]
    # ask_slide / ask_flat take the new rule when nothing is said and refuse an index of the other rule when it is said
    r = Q.ask_slide(wi, "猫は何を食べますか")
    assert r.config["z_deep"] == "order"
    with pytest.raises(ValueError, match="z_deep"):
        Q.ask_slide(wi, "猫は何を食べますか", z_deep="slide")
    with pytest.raises(ValueError, match="z_deep"):
        F.ask_flat(old, "猫は何を食べますか", z_deep="order")
    # a default Index builds the new default window index by itself
    from verantyx.line3 import ask as A
    data = tmp_path / "toy.jsonl"
    import json
    data.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
    idx = A.Index.from_jsonl(str(data), None, "low", ("RUN",))
    w2 = Q.window_index_for(idx)
    assert w2.z_deep == "order" and w2.spec.seat_empty_axis == "deny" and w2.spec.padding == "one"


# ==== the real corpus ================================================================================================
EXPECTED_DEFAULT_FIRST6 = [((0, 1), 17, 7, 100, "exhausted", ((18, 16), (0, 0), (3, 3)), ("+y", "-y")),
                           ((1, 2), 11, 4, 71, "exhausted", ((2, 2), (0, 0), (7, 7)), ("+y", "-y")),
                           ((2,), 8, 4, 1, "exhausted", ((7, 7), (0, 0), (0, 0)), ("+y", "-y", "+z", "-z")),
                           ((3, 4), 16, 5, 9, "exhausted", ((9, 8), (0, 0), (11, 10)), ("+y", "-y")),
                           ((4, 5), 14, 4, 120, "exhausted", ((10, 10), (0, 0), (6, 6)), ("+y", "-y")),
                           ((5,), 7, 3, 1, "exhausted", ((6, 6), (0, 0), (0, 0)), ("+y", "-y", "+z", "-z"))]


def test_fulllead_default_spec_shas_are_those_of_the_g3h_cache_budget_order_deny_and_the_first_windows_verify():
    if not os.path.exists(FL):
        pytest.skip("no fulllead data")
    rows = sp.load_jsonl(FL)
    space = sp.build_space(rows)
    full = SL.Slide(space, rows=rows)
    # the G3-h cache slidewin_725d5ac1a8d2_RUN_6b36bcb7306d_cf35f420cea6.pkl (results/cache_stats.md): corpus, slide spec, place spec (padding one, level mid)
    assert space.sha256()[:12] == "725d5ac1a8d2" and full.spec.sha256()[:12] == "6b36bcb7306d"
    assert SP.make_spec(full, padding="one", level="mid").sha256()[:12] == "cf35f420cea6"
    assert Q.cache_name(space.sha256(), "RUN", full.spec.sha256(), SP.make_spec(full, padding="one", level="mid").sha256()) == \
        "slidewin_725d5ac1a8d2_RUN_6b36bcb7306d_cf35f420cea6.pkl"
    spec = SP.make_spec(full)
    assert spec.switches() == OWNER and spec.switches3() == OWNER3
    got = []
    for pw in SP.place_windows(full, "none")[:6]:
        p = SP.place_window(full, pw, spec)
        wfn = SP.counts_weight_fn(full.counts(pw.window, "corpus"), "RUN")
        arms = [n for n in SP.ARM_NAMES if n not in p.seatless_arms]
        r = SP.verify_class_slide(wfn, p.crosses(), stability="per_axis", arm_names=arms, sides={i.token: i.side for i in p.items}, z_reserved=True,
                                  centre_only=True, x_sides=list(p.member_x_side), own_Ls=list(p.member_L))
        assert r.is_stable_class and r.members_checked == p.class_size, (pw.window.sids, r)
        got.append((pw.window.sids, p.size, p.L, p.class_size, p.stop, tuple(tuple(v) for v in p.axis_keys.values()), tuple(p.seatless_arms)))
    assert got == EXPECTED_DEFAULT_FIRST6


# ==== the command line ===============================================================================================
def test_cli_help_and_default_of_z_deep():
    env = dict(os.environ, PYTHONHASHSEED="0", PYTHONDONTWRITEBYTECODE="1", PYTHONPATH=ROOT)
    for k in [k for k in env if k.startswith("VERA_")]:
        del env[k]
    out = subprocess.run([PY, "-m", "verantyx.cli", "line3", "--help"], capture_output=True, text=True, env=env, cwd=ROOT, timeout=300, stdin=subprocess.DEVNULL)
    assert out.returncode == 0, out.stderr
    h = " ".join(out.stdout.split())
    assert "--z-deep {slide,order}" in h and "order (default since G3-i" in h and "slide = a slide edge" in h
    assert "seat_empty_axis deny" in h and "arm_cap budget" in h and "padding one" in h
