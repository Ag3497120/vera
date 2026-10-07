"""T8 tests (L-230..): layers (matryoshka).  Decisions: line 3 (answers flow to the next layer, the initial query passed
or not), decision 9 / I-18 / N-08 / N-11 (stack when the energy is no longer stable, checked when a question is asked,
stack on the spot), N-05 (the state that was stable just before is restored), N-06 / N-07 / I-19 / M-1(c) (all stable
states go up, one large cross by the same stability rule, quantity = union of the sentences), N-12 (re-read to a fixed
point), N-19 (the trace goes down), I-20 (both variants), M-2 (compress vs same granularity, effort bounds), M-5."""
import hashlib
import io
import json
import os
import subprocess
import sys
import tokenize
from fractions import Fraction as Fr

import pytest

from verantyx.line3 import ask as A
from verantyx.line3 import cycle as cy
from verantyx.line3 import matryoshka as M
from verantyx.line3 import placement as pl
from verantyx.line3.space import build_space

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SRC = os.path.join(ROOT, "verantyx", "line3", "matryoshka.py")

DATA = ["東京は日本の首都である。", "大阪は日本の西の都市である。", "京都は日本の古い都市である。",
        "東京は大きな都市である。", "富士山は日本一高い山である。", "富士山は静岡と山梨にまたがる。",
        "大阪は食べ物で有名である。", "京都は寺で有名である。", "東京タワーは東京にある。",
        "琵琶湖は滋賀にある湖である。", "滋賀は京都の隣である。", "静岡は富士山の南にある。"]
QUESTION = "東京は何の都市ですか"
SMALL = pl.Budget(max_class=2, max_states=30, max_moves=300)
BOUNDS = M.LayerBounds(max_layers=2, nodes=6, pass_cap=8, pool_groups=3, members=6, level="low", rounds=4)
TIERS = ["RUN", "WORD"]


@pytest.fixture(scope="module")
def space():
    return build_space([{"sent": s, "source": "toy"} for s in DATA])


def make_index(space, budget=None):
    idx = A.Index(space)
    if budget is not None:
        for t in idx.tiers:
            idx.stores[t].placer = pl.Placer(space.tiers[t], budget)
    return idx


@pytest.fixture(scope="module")
def stable_index(space):
    return make_index(space)


@pytest.fixture(scope="module")
def small_index(space):
    return make_index(space, SMALL)


def opts(**kw):
    kw.setdefault("bounds", BOUNDS)
    return M.LayerOptions(**kw)


@pytest.fixture(scope="module")
def layered(small_index):
    return M.ask_layered(small_index, QUESTION, TIERS, effort="full", options=opts())


# ---- layers appear only when the stability is lost ---------------------------------------------------------------------
ROOMY = cy.QueryBudget(4096, 4096)          # a query budget no member of the toy reaches


def test_no_layer_when_every_read_cross_is_stable_and_layer_zero_is_untouched(stable_index):
    c = M.ask_layered(stable_index, QUESTION, TIERS, effort="full", options=opts(), budget=ROOMY)
    assert not c.stacked
    for tl in c.layers:
        assert not tl.triggered and tl.runs == () and tl.triggers["growth_budget"] == []
        assert tl.fixed_point["reached"] and tl.fixed_point["rounds"] == 0
    plain = A.ask(stable_index, QUESTION, TIERS, ROOMY, effort="full")
    assert c.base.to_bytes() == plain.to_bytes()
    assert [e["words"] for e in c.listed()] == [list(e.words) for _, e in plain.entries]
    assert "積み上げなし" in M.format_layers_text(c)


def test_layers_appear_exactly_where_a_read_cross_stopped_by_the_budget(small_index):
    c = M.ask_layered(small_index, QUESTION, TIERS, effort="full", options=opts())
    seen = set()
    for o, tl in zip(c.base.outcomes, c.layers):
        full = [s for s in o.result.plan.read if small_index.stores[o.tier].cross_for(s).stop == "budget"]
        nofix = len(o.result.stack_points)
        assert tl.triggered == bool(full or nofix)
        assert tl.triggers["growth_budget"] == sorted(full)
        assert bool(tl.runs) == tl.triggered
        seen.add(tl.triggered)
    assert True in seen                    # the small budget does stack here (otherwise this test proves nothing)
    assert c.stacked


def test_a_collapse_in_the_middle_of_the_question_stacks_on_the_spot_and_the_upper_layer_answers(stable_index):
    # every cross is stable (default budgets) but the QUERY budget cannot reach a fixed point: N-11
    c = M.ask_layered(stable_index, QUESTION, ["RUN"], effort="full", options=opts(), budget=cy.QueryBudget(1, 1))
    (tl,) = c.layers
    assert tl.triggers["growth_budget"] == [] and tl.triggers["query_no_fixed_point"]
    assert tl.triggered and tl.runs
    a = [r for r in tl.runs if r.variant == "A"][0]
    assert a.verdict != M.UNKNOWN_NOTHING_TO_PASS and a.query_units      # the upper layer carries the question on
    for x in tl.triggers["query_no_fixed_point"]:
        assert x["reason"] in ("max_states", "max_ends")


# ---- N-05: the state that was stable just before is restored ------------------------------------------------------------
def test_a_full_cross_holds_the_state_that_was_stable_just_before_the_step_that_broke(space):
    t = space.tiers["RUN"]
    w = pl.Weights(t)
    checked = 0
    for s in t.units():
        p = pl.build_cross(t, s, w, budget=SMALL)
        if p.stop != "budget":
            continue
        assert p.broke_on is not None and p.broke_on.status == pl.BUDGET and p.broke_on.size_after is None
        placed = set(M.placed_units(p))
        assert not (set(p.broke_on.units) & placed)                       # the step that broke is not in the state
        stable_units = {u for st in p.steps if st.status == pl.STABLE for u in st.units} | {s}
        assert placed == stable_units and p.size == len(placed) == p.capacity
        if p.expanded_size <= 300:                                        # the restored state is a stable class (I-05)
            rep = pl.verify_class(t, p.crosses())
            assert rep.is_stable_class
        # and the bundle that goes up is exactly this state, quantity = union of the sentences of its words
        lay = M.LayerStack(t, type("S", (), {"cross_for": lambda self, x, w=w: pl.build_cross(t, x, w, budget=SMALL)})()
                           ).layer1("compress", [s], BOUNDS)
        b = M.bundle_id(1, s)
        assert lay.words[b] == frozenset(placed) and lay.lower_units[b] == tuple(sorted(placed))
        assert lay.space.postings[b] == t.postings_union(placed)
        checked += 1
    assert checked >= 3


def test_a_member_with_no_fixed_point_under_the_question_goes_up_as_its_pre_question_state(stable_index):
    ts = stable_index.space.tiers["RUN"]
    res = cy.ask_tier(ts, QUESTION, stable_index.stores["RUN"], budget=cy.QueryBudget(1, 1), raise_budget=None)
    assert res.stack_points
    sp = res.stack_points[0]
    p = stable_index.stores["RUN"].cross_for(sp["seed"])
    start_units = {u for u in sp["state"] if u is not None}
    assert start_units == set(M.placed_units(p))                         # the restored state is the stable one before


# ---- the upper layer: one large cross by the same stability rule, whole states, no copy of a lower arm -----------------
def test_the_upper_layer_holds_whole_lower_states_in_crosses_stable_by_the_same_rule(space, small_index):
    st = M.stack_of(small_index, "RUN")
    lay = st.layer1("same", [], BOUNDS)
    t = space.tiers["RUN"]
    assert set(lay.words) == {M.bundle_id(1, u) for u in t.units()}       # every stable state goes up (N-06)
    lower_arms = set()
    for u in t.units():
        p = small_index.stores["RUN"].cross_for(u)
        flat = pl.from_cross(p.cross)
        for a in range(6):
            lower_arms.add(tuple(c for c in flat[1 + a * p.L: 1 + (a + 1) * p.L] if c is not None))
    done = 0
    for b in sorted(lay.words)[:12]:
        up = lay.cross_for(b)
        cells = {c for m in up.members for c in m if c is not None}
        for tw in up.twin_sets:
            cells.update(tw)
        assert cells <= set(lay.words) and not (cells & set(t.units()))  # seats hold bundles, never base words
        for m in up.members:                                              # no upper arm is a copy of a lower arm
            for a in range(6):
                arm = tuple(c for c in m[1 + a * up.L: 1 + (a + 1) * up.L] if c is not None)
                assert arm not in lower_arms or arm == ()
        if up.expanded_size <= 300:
            assert pl.verify_class(lay.space, up.crosses()).is_stable_class   # the SAME stability rule, independent check
        done += 1
    assert done >= 6
    for b in lay.words:
        assert lay.space.postings[b] == t.postings_union(lay.words[b])


def test_the_bundle_tier_order_key_is_strict_and_symmetric_counts_are_consistent(space, small_index):
    st = M.stack_of(small_index, "RUN")
    lay = st.layer1("same", [], BOUNDS)
    bs = sorted(lay.words)[:15]
    for x in bs:
        for y in bs:
            if x == y:
                continue
            both = lay.space.n_pair(x, y)
            assert both == len(set(lay.space.postings[x]) & set(lay.space.postings[y]))
            # strict earliest-position comparison: x before y plus y before x never exceeds the shared sentences
            assert lay.space.p_pair(x, y) + lay.space.p_pair(y, x) <= both


# ---- both query variants ------------------------------------------------------------------------------------------------
def test_both_query_variants_are_built_and_give_output(layered):
    ran = {(r.tier, r.variant) for tl in layered.layers for r in tl.runs if r.k == 1}
    for tl in layered.layers:
        if tl.triggered:
            assert {(tl.tier, "A"), (tl.tier, "B")} <= ran
    got = {e.variant for tl in layered.layers for e in tl.entries}
    assert got == {"A", "B"}                                              # both produce candidates
    out = layered.answer_obj()
    assert {e["variant"] for e in out["entries"] if e["layer"] >= 1} == {"A", "B"}
    assert any(e["layer"] == 0 for e in out["entries"])                   # layer 0 stays in the list, labelled


def test_variant_a_carries_the_initial_query_and_b_only_the_lower_answer(small_index, layered):
    for tl in layered.layers:
        o = layered.base.outcome(tl.tier)
        ans_words = set(M._answer_units(o.answer))
        qwords = set(o.result.ctx.query)
        for r in tl.runs:
            if r.k != 1:
                continue
            under = {b[len("⟦1:"):-1] for b in r.query_units}
            if r.variant == "A":
                assert qwords & set(u for u in qwords if M.bundle_id(1, u) in set(r.query_units)) == qwords & under
                assert qwords & under                                      # the question's own bundles are on the query cross
            else:
                assert under <= ans_words                                  # B: nothing but the lower answer
    # B with nothing to pass up is typed, not silently empty
    st = M.stack_of(small_index, "RUN")
    res0 = cy.ask_tier(small_index.space.tiers["RUN"], QUESTION, small_index.stores["RUN"], raise_budget=None)
    tl = M.run_layers(st, res0, None, opts(variants=("B",)))
    if tl.triggered:
        assert all(r.verdict == M.UNKNOWN_NOTHING_TO_PASS and not r.entries for r in tl.runs)


def test_inner_query_units_from_the_seventh_are_added_when_passing_up_in_variant_a(space):
    idx = make_index(space, SMALL)
    q = "東京は日本の古い都市である大阪京都富士山静岡"
    c = M.ask_layered(idx, q, ["WORD"], effort="full", options=opts(variants=("A", "B")))
    (tl,) = c.layers
    qwords = c.base.outcome("WORD").result.ctx.query
    assert len(qwords) > 6                                                 # the question is a nested query cross (N-21)
    assert tl.triggered
    ra = [r for r in tl.runs if r.variant == "A" and r.k == 1][0]
    rb = [r for r in tl.runs if r.variant == "B" and r.k == 1][0]
    under_a = {b[len("\u27e61:"):-1] for b in ra.query_units}
    in_space = {u for u in qwords if u in idx.space.tiers["WORD"].postings}
    assert in_space <= under_a                                             # all of them went up, not only the first six
    assert ra.result.thought_obj()["inner_layers_pending"]                 # and the upper cross itself is nested again
    under_b = {b[len("\u27e61:"):-1] for b in rb.query_units}
    assert not (under_b & set(qwords[6:]) - set(M._answer_units(c.base.outcome("WORD").answer)))   # B: the inner units are not added


# ---- re-read: a fixed point across the layers, or a typed budget stop (N-12) -----------------------------------------
def test_reread_with_feedback_reaches_a_fixed_point_or_stops_typed(small_index):
    c = M.ask_layered(small_index, QUESTION, TIERS, effort="full", options=opts(feedback="down"))
    for tl in c.layers:
        if not tl.triggered:
            continue
        fp = tl.fixed_point
        assert fp["feedback"] == "down"
        if fp["reached"]:
            assert fp["rounds"] >= 2 and "no layer changed" in fp["stop"]
        else:
            assert fp["stop"] == M.UNKNOWN_NO_FIXED_POINT_LAYERS and fp["rounds"] == BOUNDS.rounds


def test_a_round_budget_of_one_cannot_confirm_a_fixed_point_and_says_so(small_index):
    b1 = M.LayerBounds(1, 4, 8, 3, 4, "low", 1)
    c = M.ask_layered(small_index, QUESTION, ["WORD"], effort="full", options=opts(feedback="down", bounds=b1))
    (tl,) = c.layers
    assert tl.triggered
    assert tl.fixed_point == {"rounds": 1, "reached": False, "feedback": "down", "stop": M.UNKNOWN_NO_FIXED_POINT_LAYERS,
                              "budget_rounds": 1}


def test_feed_forward_rereading_changes_nothing(small_index):
    a = M.ask_layered(small_index, QUESTION, TIERS, effort="full", options=opts(feedback="none"))
    b = M.ask_layered(small_index, QUESTION, TIERS, effort="full", options=opts(feedback="none"))
    assert a.to_bytes() == b.to_bytes()
    for tl in a.layers:
        if tl.triggered:
            assert tl.fixed_point["reached"] and tl.fixed_point["feedback"] == "none"


# ---- trace through the layers (100%) ---------------------------------------------------------------------------------------
def test_every_word_of_every_upper_entry_traces_down_to_a_base_state(small_index, layered):
    n = 0
    for tl in layered.layers:
        for r in tl.runs:
            assert r.trace["ok"] and r.trace["words_traced"] == r.trace["words_checked"]
            n += r.trace["words_checked"]
    assert n > 0
    # the check is not vacuous: a word that no bundle of the entry holds, or an entry bundle that is not there, fails it
    tl = [t for t in layered.layers if any(r.entries for r in t.runs)][0]
    r = [r for r in tl.runs if r.entries][0]
    st = M.stack_of(small_index, tl.tier)
    lay = st.layer1("same", [], BOUNDS)
    e = r.entries[0]
    from dataclasses import replace
    bad = replace(e, words=e.words + ("存在しない語",))
    t = M.trace_run(st.base, [lay], lay, None, [bad], st.store)
    assert not t["ok"] and t["words_traced"] == t["words_checked"] - 1
    bad2 = replace(e, bundles=("⟦1:ない⟧",))
    t2 = M.trace_run(st.base, [lay], lay, None, [bad2], st.store)
    assert not t2["ok"]


def test_the_base_sentences_of_an_upper_entry_are_real_sentences(small_index, layered):
    for tl in layered.layers:
        for e in tl.entries:
            assert all(0 <= s < small_index.space.N for s in e.source_sids)


# ---- effort bounds the layer work and marks partial reads -------------------------------------------------------------------
def test_the_effort_presets_bound_the_layers_and_a_bounded_read_is_marked(small_index):
    assert M.bounds_for("fast").nodes == 4 and M.bounds_for("standard").nodes == 10 and M.bounds_for("full").nodes == 24 and M.bounds_for("full").members == 64
    assert M.bounds_for(None) == M.LAYER_EFFORTS["full"] and M.bounds_for(nodes=3).nodes == 3
    tight = M.LayerBounds(1, 1, 2, 2, 1, "low", 2)
    c = M.ask_layered(small_index, QUESTION, TIERS, effort="full", options=opts(bounds=tight))
    marked = 0
    for tl in c.layers:
        for r in tl.runs:
            assert len(r.read) <= 1 or r.left_unread == 0 or r.partial
            assert r.k <= tight.max_layers
            if r.left_unread or r.members_read < r.members_total:
                assert r.partial
                marked += 1
    assert marked > 0
    # a need for a further layer that the effort does not allow is reported, not built
    lim = [r for tl in c.layers for r in tl.runs if r.layer_limit]
    assert all(r.k == tight.max_layers for r in lim)


def test_pool_groups_cuts_whole_share_groups_and_default_is_unchanged(space):
    t = space.tiers["WORD"]
    w = pl.Weights(t)
    for s in ("東京", "都市", "日本"):
        a = pl.build_cross(t, s, w)
        b = pl.build_cross(t, s, w, pool_groups=None)
        assert a.to_bytes() == b.to_bytes()
        c = pl.build_cross(t, s, w, pool_groups=1)
        assert c.size <= a.size and c.stop in ("max_groups", "budget", "exhausted")
        if len(pl._groups(t, s)) > 1:
            assert c.stop in ("max_groups", "budget")


def test_cycle_plan_override_default_is_unchanged(space, stable_index):
    ts = space.tiers["RUN"]
    a = cy.ask_tier(ts, QUESTION, stable_index.stores["RUN"], raise_budget=None)
    b = cy.ask_tier(ts, QUESTION, stable_index.stores["RUN"], raise_budget=None, observe=True, plan_override=None)
    assert a.to_bytes() == b.to_bytes()


# ---- compress vs same granularity (M-2) ---------------------------------------------------------------------------------------
def test_both_granularities_are_offered_and_their_sizes_are_shown(small_index):
    same = M.ask_layered(small_index, QUESTION, TIERS, effort="full", options=opts(granularity="same"))
    comp = M.ask_layered(small_index, QUESTION, TIERS, effort="full", options=opts(granularity="compress"))
    for a, b in zip(same.layers, comp.layers):
        assert a.choice["bundles_if_same"] == b.choice["bundles_if_same"] == len(small_index.space.tiers[a.tier].postings)
        assert a.choice["bundles_if_compress"] == b.choice["bundles_if_compress"] <= a.choice["bundles_if_same"]
        if a.triggered:
            assert all(r.n_bundles == a.choice["bundles_if_same"] for r in a.runs if r.k == 1)
            # compress bundles only the states the question touched (plus the units of the lower answer)
            assert all(r.n_bundles <= a.choice["bundles_if_same"] for r in b.runs if r.k == 1)
            assert any(r.n_bundles < a.choice["bundles_if_same"] for r in b.runs if r.k == 1)
    txt = M.format_layers_text(same, True)
    assert "圧縮" in txt and "同じ粒度" in txt
    with pytest.raises(ValueError):
        M.LayerOptions(granularity="x")
    with pytest.raises(ValueError):
        M.LayerOptions(variants=())
    with pytest.raises(ValueError):
        M.LayerOptions(feedback="up")


# ---- output: labelled, never merged; memory record --------------------------------------------------------------------------
def test_the_list_is_labelled_by_layer_and_variant_and_nothing_is_merged_across_labels(layered):
    ent = layered.listed()
    n0 = len(layered.base.entries)
    assert [e["layer"] for e in ent[:n0]] == [0] * n0
    up = [e for tl in layered.layers for e in tl.entries]
    assert len(ent) == n0 + len(up)
    keys = [(e["tier"], e["layer"], e["variant"], tuple(e["words"])) for e in ent]
    assert len(keys) == len(set(keys))                                    # the same words under another label stay apart
    assert layered.verdict in (A.ANSWER, A.CHOICE)
    if up:
        i = n0
        rec = layered.memory_record(i)
        assert rec["layer"] == up[0].layer and rec["variant"] == up[0].variant and rec["base_changed"] is False
    if n0:
        rec0 = layered.memory_record(0)
        assert rec0["layer"] == 0 and rec0["tier"] == layered.base.entries[0][0]
    with pytest.raises(IndexError):
        layered.memory_record(len(ent))


def test_layers_do_not_change_layer_zero(small_index, layered):
    plain = A.ask(small_index, QUESTION, TIERS, effort="full")
    assert layered.base.to_bytes() == plain.to_bytes()


# ---- exact arithmetic and determinism ---------------------------------------------------------------------------------------
def test_no_float_in_source_and_none_in_the_output(layered):
    with open(SRC, "rb") as f:
        toks = list(tokenize.tokenize(io.BytesIO(f.read()).readline))
    for tk in toks:
        if tk.type == tokenize.NUMBER:
            assert "." not in tk.string and "e" not in tk.string.lower()
        if tk.type == tokenize.NAME:
            assert tk.string != "float"

    def walk(o):
        if isinstance(o, dict):
            for v in o.values():
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)
        else:
            assert not isinstance(o, float)

    walk(layered.to_json_obj())
    for e in layered.listed():
        if e["stability"] is not None:
            n, d = e["stability"].split("/")
            assert Fr(int(n), int(d)) <= 1


def _digest_script():
    return ("import json,hashlib,sys\n"
            "from verantyx.line3 import ask as A, placement as pl, matryoshka as M\n"
            "from verantyx.line3.space import build_space\n"
            "D=%r\n" % (DATA,) +
            "sp=build_space([{'sent':s,'source':'t'} for s in D])\n"
            "idx=A.Index(sp)\n"
            "for t in idx.tiers: idx.stores[t].placer=pl.Placer(sp.tiers[t], pl.Budget(2,30,300))\n"
            "b=M.LayerBounds(2,6,8,3,6,'low',4)\n"
            "c=M.ask_layered(idx,%r,['RUN','WORD'],effort='full',options=M.LayerOptions(bounds=b,feedback='down'))\n" % QUESTION +
            "print(hashlib.sha256(c.to_bytes()).hexdigest(), len(c.to_bytes()))\n")


def test_output_is_byte_identical_across_hash_seeds():
    outs = []
    for seed in ("0", "1", "12345"):
        env = dict(os.environ, PYTHONHASHSEED=seed, PYTHONDONTWRITEBYTECODE="1", PYTHONPATH=ROOT)
        r = subprocess.run([sys.executable, "-c", _digest_script()], capture_output=True, text=True, env=env, cwd=ROOT,
                           timeout=900, stdin=subprocess.DEVNULL)
        assert r.returncode == 0, r.stderr
        outs.append(r.stdout.strip())
    assert outs[0] == outs[1] == outs[2] and int(outs[0].split()[1]) > 1000


# ---- the command switch ----------------------------------------------------------------------------------------------------------
def cli(args, seed="0"):
    env = dict(os.environ, PYTHONHASHSEED=seed, PYTHONDONTWRITEBYTECODE="1", PYTHONPATH=ROOT)
    for k in [k for k in env if k.startswith("VERA_")]:
        del env[k]
    return subprocess.run([sys.executable, "-m", "verantyx.cli", "line3"] + args, capture_output=True, text=True, env=env,
                          cwd=ROOT, timeout=900, stdin=subprocess.DEVNULL)


def test_cli_layers_switch(tmp_path):
    p = tmp_path / "toy.jsonl"
    with open(p, "w", encoding="utf-8") as f:
        for s in DATA:
            f.write(json.dumps({"sent": s, "source": "toy"}, ensure_ascii=False) + "\n")
    base = ["ask", "--data", str(p), "--question", QUESTION, "--tiers", "RUN,WORD", "--effort", "fast"]
    off = cli(base + ["--layers", "off"])
    on = cli(base + ["--layers", "on"])
    assert off.returncode == 0 and on.returncode == 0, on.stderr
    assert "層:" not in off.stdout and "層:" in on.stdout
    on_json = cli(base + ["--layers", "on", "--format", "json", "--show-thought"])
    assert on_json.returncode == 0, on_json.stderr
    obj = json.loads(on_json.stdout)
    assert obj["answer"]["layers"] == "on" and "layers" in obj["thought"]
    bad = cli(base + ["--layers", "maybe"])
    assert bad.returncode == 2
    badv = cli(base + ["--layers", "on", "--query-pass", "C"])
    assert badv.returncode == 2


# ---- bundling again: when an upper cross is about to overflow the crosses that were needed are bundled into a larger one ----
def test_a_full_upper_cross_is_bundled_again_into_a_third_layer(space, monkeypatch):
    monkeypatch.setitem(pl.LEVELS, "low", pl.Budget(max_class=2, max_states=30, max_moves=300))
    idx = make_index(space, SMALL)
    b3 = M.LayerBounds(3, 6, 8, 3, 6, "low", 2)
    c = M.ask_layered(idx, QUESTION, ["RUN", "WORD"], effort="full", options=opts(bounds=b3, variants=("A",)))
    deep = [r for tl in c.layers for r in tl.runs if r.k >= 2]
    assert deep, "no upper cross stopped by the budget, so nothing was bundled again"
    for r in deep:
        assert all(b.startswith("\u27e6%d:\u27e6" % r.k) for b in r.query_units)      # bundles of bundles
        assert r.trace["ok"]
        for e in r.entries:
            assert all(b.startswith("\u27e6%d:" % r.k) for b in e.bundles)
            assert set(e.words) <= set(idx.space.tiers[r.tier].postings)               # expanded down to base words
    # the lower layer's run said it needed the next one before it was built; one that was not allowed is reported
    for tl in c.layers:
        ks = sorted({r.k for r in tl.runs})
        assert ks == list(range(1, len(ks) + 1))
        for r in tl.runs:
            if r.k == b3.max_layers:
                assert r.layer_limit == bool(r.full_crosses or r.no_fixed_point)


# ---- the descent (coarse -> fine): the shortcut reads only the lower crosses under the selected path ---------------------
def test_descent_reads_only_crosses_under_the_selected_path_and_never_more_than_the_flat_read(small_index):
    for tier in TIERS:
        d = M.descend_tier(small_index, tier, QUESTION, opts(granularity="same"))
        cr = d.crosses_read
        under = {M._centre_word(None, b) for e in d.coarse.entries for b in e.bundles}
        assert set(d.fine_seeds) <= under                      # nothing outside the packed elements on the paths
        assert cr["lower"] <= cr["flat"] or cr["flat"] == 0
        assert cr["total"] == cr["upper"] + cr["lower"]
        if d.fine is not None:
            assert set(d.fine.plan.read) == set(d.fine_seeds)
        d2 = M.descend_tier(small_index, tier, QUESTION, opts(granularity="same"))
        assert d.to_json_obj() == d2.to_json_obj()
