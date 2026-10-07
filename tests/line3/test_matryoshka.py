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
    # the T8 behaviour, explicitly (the library default is now variant A / compress / path words: L-250, L-251)
    kw.setdefault("variants", M.VARIANTS)
    kw.setdefault("granularity", "same")
    kw.setdefault("candidate", "bag")
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


# ======================================================================================================================
# T8b (L-250, L-251): layers ON by default (compress, query A); an upper-layer candidate = the PATH WORDS read under the
# question from the lower crosses packed in its bundles (never the whole bundled state)
# ======================================================================================================================
GOLDEN_OLD = {      # sha256 of to_bytes() produced by the T8 tree (bbf85e3) on the toy, BOUNDS, tiers RUN+WORD, effort full
    "off": "e2a29d889b723f974f981386595fcffc20bc3528ced274baef573718631866aa",
    "on-old": "f8091391da45068fecdee2b5116aa667ab12c74d3ebfb5f78ee3cac06888b689",
    "on-old-compress-A": "e93864f46f446b4dd09cfd389ffed946212a58f430acfb7278c9e71be5bb6ebd",
    "on-old-down": "99c526314fcb069590fbf11ae3ad2346825363569be6361b39d3f391244b2d8b",
}


def test_the_defaults_are_the_owners_choice_and_the_old_behaviour_is_reachable_by_explicit_flags(small_index):
    d = M.LayerOptions()
    assert d.variants == ("A",) and d.granularity == "compress" and d.candidate == "path"
    with pytest.raises(ValueError):
        M.LayerOptions(candidate="all")
    h = lambda b: hashlib.sha256(b).hexdigest()
    assert h(A.ask(small_index, QUESTION, TIERS, effort="full").to_bytes()) == GOLDEN_OLD["off"]       # layers off: untouched
    old = M.ask_layered(small_index, QUESTION, TIERS, effort="full",
                        options=M.LayerOptions(candidate="bag", variants=M.VARIANTS, granularity="same", bounds=BOUNDS))
    assert h(old.to_bytes()) == GOLDEN_OLD["on-old"]
    old_c = M.ask_layered(small_index, QUESTION, TIERS, effort="full",
                          options=M.LayerOptions(candidate="bag", variants=("A",), granularity="compress", bounds=BOUNDS))
    assert h(old_c.to_bytes()) == GOLDEN_OLD["on-old-compress-A"]
    old_d = M.ask_layered(small_index, QUESTION, TIERS, effort="full",
                          options=M.LayerOptions(candidate="bag", variants=M.VARIANTS, granularity="same", bounds=BOUNDS, feedback="down"))
    assert h(old_d.to_bytes()) == GOLDEN_OLD["on-old-down"]
    # the library default is a different (path-word) result
    new = M.ask_layered(small_index, QUESTION, TIERS, effort="full", options=M.LayerOptions(bounds=BOUNDS))
    assert new.options.candidate == "path" and h(new.to_bytes()) != GOLDEN_OLD["on-old-compress-A"]


@pytest.fixture(scope="module")
def pathed(small_index):
    return M.ask_layered(small_index, QUESTION, TIERS, effort="full", options=M.LayerOptions(bounds=BOUNDS))


def _path_words_of(read_ans):
    """The words on the section paths of a read-out (and its centres), computed from the arrangements, not from entry.words."""
    out = set()
    for e in read_ans.entries:
        for a in e.arrangements:
            for p in a.paths:
                out.update(p.words)
            out.add(a.centre)
    return out


def test_an_upper_candidate_shows_only_the_path_words_read_under_the_question(small_index, pathed):
    seen = 0
    for tl in pathed.layers:
        st = M.stack_of(small_index, tl.tier)
        for r in tl.runs:
            assert r.candidate == "path"
            for e in r.entries:
                seen += 1
                assert e.word_sources is not None and e.words and e.path_from
                # (1) every word is a path word of a lower read the entry records ...
                recorded = set()
                for d in e.path_from:
                    assert d["layer"] == 0 or d["layer"] < e.layer
                    recorded.update(d["words"])
                assert set(e.words) <= recorded
                # (2) ... which a fresh, independent read of that lower cross under the same question reproduces
                lows = [pa for j, pa in e.path_answers if j == 0]
                assert lows
                fresh = set()
                for pa in lows:
                    fresh |= _path_words_of(pa)
                base_words = {w for d in e.path_from if d["layer"] == 0 for w in d["words"]}
                assert base_words <= fresh
                # (3) and the trace says every one of them lies in a bundle of the entry (down to a base state)
                assert r.trace["ok"]
    assert seen > 0


def test_path_candidates_are_smaller_than_the_bags_they_replace_and_are_never_bigger(small_index, layered, pathed):
    # the same question, bag mode (T8) vs path mode: every path entry is contained in the words of the lower states of its bundles
    bag = M.ask_layered(small_index, QUESTION, TIERS, effort="full", options=M.LayerOptions(candidate="bag", bounds=BOUNDS))
    n_bag = sum(len(e.words) for tl in bag.layers for e in tl.entries)
    n_path = sum(len(e.words) for tl in pathed.layers for e in tl.entries)
    assert n_path > 0
    for tl in bag.layers:
        for e in tl.entries:
            assert all(0 < len(x) for x in [e.words])
    assert n_path <= n_bag


def test_every_path_word_has_source_sentences_that_hold_it_and_the_trace_is_complete(small_index, pathed):
    n = 0
    for tl in pathed.layers:
        ts = small_index.space.tiers[tl.tier]
        for r in tl.runs:
            assert r.trace["ok"] and r.trace["words_traced"] == r.trace["words_checked"] and r.trace["fraction"] == "1/1"
            for e in r.entries:
                assert dict(e.word_sources).keys() == set(e.words)
                for w, ss in e.word_sources:
                    assert ss
                    for sid in ss:
                        assert w in ts.sentence_units[sid]            # the source sentence really contains the word
                        n += 1
                assert set(e.source_sids) == {s for _, ss in e.word_sources for s in ss}
    assert n > 0
    # the sentences of the sources are given in the answer
    ans = pathed.answer_obj()
    for e in ans["entries"]:
        for s in e["source_sids"]:
            assert any(x["sid"] == s and x["text"] for x in ans["sources"])
    # not vacuous: a word the lower reads did not give fails the trace
    from dataclasses import replace
    tl = [t for t in pathed.layers if any(r.entries for r in t.runs)][0]
    r = [r for r in tl.runs if r.entries][0]
    st = M.stack_of(small_index, tl.tier)
    lay = st.layer1(r.granularity, [M._strip(x) for x in r.query_units], BOUNDS)
    e = r.entries[0]
    bad = replace(e, words=e.words + ("存在しない語",))
    t = M.trace_run(st.base, [lay], lay, None, [bad], st.store)
    assert not t["ok"]


def test_a_layer_two_candidate_is_read_down_through_layer_one_to_base_path_words(space, monkeypatch):
    monkeypatch.setitem(pl.LEVELS, "low", pl.Budget(max_class=2, max_states=30, max_moves=300))
    idx = make_index(space, SMALL)
    b3 = M.LayerBounds(3, 6, 8, 3, 6, "low", 2)
    c = M.ask_layered(idx, QUESTION, ["RUN", "WORD"], effort="full", options=M.LayerOptions(bounds=b3))
    deep = [r for tl in c.layers for r in tl.runs if r.k >= 2 and r.entries]
    assert deep, "no layer-2 candidate on this toy"
    for r in deep:
        assert r.trace["ok"] and r.trace["fraction"] == "1/1"
        for e in r.entries:
            layers_read = {d["layer"] for d in e.path_from}
            assert 0 in layers_read and (r.k - 1) in layers_read          # the lower layer is read, then down to the base
            base_words = {w for d in e.path_from if d["layer"] == 0 for w in d["words"]}
            assert set(e.words) == base_words                              # only the base path words, nothing else
            assert set(e.words) <= set(idx.space.tiers[r.tier].postings)


def test_path_mode_has_no_float_and_is_exact(pathed):
    def walk(o):
        if isinstance(o, dict):
            for v in o.values():
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)
        else:
            assert not isinstance(o, float)

    walk(pathed.to_json_obj())
    assert json.loads(pathed.to_bytes())["thought"]["layers"]["options"]["candidate"] == "path"


def _digest_script_path():
    return _digest_script().replace("M.LayerOptions(bounds=b,feedback='down')",
                                    "M.LayerOptions(bounds=b,variants=M.VARIANTS,granularity='same')")


def test_path_mode_output_is_byte_identical_across_hash_seeds():
    for script in (_digest_script(), _digest_script_path()):          # the default options (A, compress, path) and both/same
        outs = []
        for seed in ("0", "1", "12345"):
            env = dict(os.environ, PYTHONHASHSEED=seed, PYTHONDONTWRITEBYTECODE="1", PYTHONPATH=ROOT)
            r = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True, env=env, cwd=ROOT,
                               timeout=900, stdin=subprocess.DEVNULL)
            assert r.returncode == 0, r.stderr
            outs.append(r.stdout.strip())
        assert outs[0] == outs[1] == outs[2] and int(outs[0].split()[1]) > 1000


def test_cli_defaults_are_layers_on_compress_a_path_and_flags_restore_the_old_output(tmp_path):
    p = tmp_path / "toy.jsonl"
    with open(p, "w", encoding="utf-8") as f:
        for s in DATA:
            f.write(json.dumps({"sent": s, "source": "toy"}, ensure_ascii=False) + "\n")
    base = ["ask", "--data", str(p), "--question", QUESTION, "--tiers", "RUN,WORD", "--effort", "fast", "--format", "json",
            "--show-thought"]
    dflt = cli(base)
    assert dflt.returncode == 0, dflt.stderr
    o = json.loads(dflt.stdout)
    opt = o["thought"]["layers"]["options"]
    assert opt["variants"] == ["A"] and opt["granularity"] == "compress" and opt["candidate"] == "path"
    off = cli(base + ["--layers", "off"])
    assert off.returncode == 0 and "layers" not in json.loads(off.stdout)["answer"]
    old = cli(base + ["--query-pass", "both", "--layer-granularity", "same", "--layer-candidate", "bag"])
    assert old.returncode == 0, old.stderr
    oo = json.loads(old.stdout)["thought"]["layers"]["options"]
    assert oo["variants"] == ["A", "B"] and oo["granularity"] == "same" and "candidate" not in oo
    assert cli(base + ["--layer-candidate", "all"]).returncode == 2


# ======================================================================================================================
# T8c (L-340..L-345): candidate="stable": the question is applied to a lower cross unit by unit; the boundary between
# stable and unstable is recorded; an unstable cross is restored to its last stable state, and the candidate words are the
# path words of that state
# ======================================================================================================================
GOLDEN_PATH = {     # sha256 of to_bytes() of the T8b tree (dad327f), toy, BOUNDS, RUN+WORD, effort full: path mode must not move
    "path-default": "2814fd9cf01d1d0b0beff0e033ad28347013c183de5f64ab0e62859d379f7477",
    "path-both-same": "4ed78fc7d684fa760f160fd9349b5e62e026ca568842ebb2db6200d578a6a77b",
    "path-seed+question": "9aa13270934750599349e50348f4603ffe07c7fefbfc10e25ce6a8359c7fab2e",
}


@pytest.fixture(scope="module")
def stabled(small_index):
    return M.ask_layered(small_index, QUESTION, TIERS, effort="full", options=M.LayerOptions(bounds=BOUNDS, candidate="stable"))


def test_the_t8b_path_mode_and_the_default_are_byte_identical_after_t8c(small_index):
    h = lambda o: hashlib.sha256(M.ask_layered(small_index, QUESTION, TIERS, effort="full", options=o).to_bytes()).hexdigest()
    assert M.LayerOptions().candidate == "path"
    assert h(M.LayerOptions(bounds=BOUNDS)) == GOLDEN_PATH["path-default"]
    assert h(M.LayerOptions(bounds=BOUNDS, variants=("A", "B"), granularity="same")) == GOLDEN_PATH["path-both-same"]
    assert h(M.LayerOptions(bounds=BOUNDS, down_query="seed+question")) == GOLDEN_PATH["path-seed+question"]


def _stable_runs(c):
    return [(tl, r) for tl in c.layers for r in tl.runs if r.candidate == "stable"]


def test_the_boundary_is_recorded_per_bundle_with_the_unit_that_broke_it(stabled):
    runs = _stable_runs(stabled)
    assert runs
    obj = stabled.to_json_obj()
    restored = kept = 0
    for tl in obj["thought"]["layers"]["per_tier"].values():
        for r in tl["runs"]:
            assert r["candidate"] == "stable" and r["boundaries"]
            for d in r["boundaries"]:
                b = d["boundary"]
                n, last, bad = b["query_units"], b["last_stable_step"], b["first_unstable_step"]
                assert 0 <= last <= n and b["read_at_step"] == last
                if bad is None:                                  # stable through the whole question: nothing to restore
                    assert last == n and b["restored"] is False and b["unstable_unit"] is None
                    kept += 1
                else:                                            # the first unit that made it unstable; the step before is the backup
                    assert bad == last + 1 and b["restored"] is True and b["unstable_unit"] is not None
                    assert b["unstable_unit_attached"] == (bad <= 6)
                    restored += 1
                assert set(b["backup"]) == {"kind", "members", "states", "sha256"}
                assert b["backup"]["kind"] == ("stored_cross" if last == 0 else "fixed_points")
    assert restored > 0 and kept > 0


def test_the_recorded_boundary_is_the_real_one_by_an_independent_prefix_scan(small_index, stabled):
    n = 0
    for tl, r in _stable_runs(stabled):
        for e in r.entries:
            for d in e.path_from:
                b = d["boundary"]
                if d["layer"] != 0:
                    continue
                st = M.stack_of(small_index, tl.tier)
                units = None
                # re-derive the question units of this lower read: the upper run's query bundles mapped one layer down (layer 1)
                if r.k == 1:
                    units = M.lower_units(r.query_units)
                    if r.passed_words:
                        pass
                if units is None or len(units) != b["query_units"]:
                    continue
                for j in range(1, len(units) + 1):
                    res = M._prefix_read(st.base, st.facts, st.store, d["seed"], units[:j], BOUNDS, A.DEFAULT_BUDGET)
                    stable = M._is_stable_read(res)
                    assert stable == (j <= b["last_stable_step"]) or j > b["last_stable_step"] + 1
                    if not stable:
                        assert j == b["first_unstable_step"]
                        break
                n += 1
    assert n > 0


def test_a_restored_state_is_a_fixed_point_for_all_its_members(small_index, stabled):
    n = 0
    for tl, r in _stable_runs(stabled):
        st = M.stack_of(small_index, tl.tier)
        assert r.trace["ok"]
        for e in r.entries:
            assert e.stable and e.restored
            for j, res in e.restored:
                facts = st.facts if j == 0 else None
                if facts is None:
                    continue
                assert res.members_read > 0 and not res.stack_points
                reader = cy.Reader(facts, res.ctx.attached, res.ctx.energy_units)
                for sr in res.reads:
                    for m in sr.members:
                        assert m.kind != cy.NOFIX and m.settled.ends and m.settled.budget_hit is None
                        for end in m.settled.ends:                       # no single move improves it (I-05), checked afresh
                            assert cy._scan(reader, end.flat, cy._L_of(end.flat))[5] == []
                            n += 1
    assert n > 0


def test_the_candidate_words_are_path_words_of_the_restored_states_and_nothing_else(small_index, stabled):
    seen = 0
    for tl, r in _stable_runs(stabled):
        for e in r.entries:
            seen += 1
            assert dict(e.word_sources).keys() == set(e.words) and e.path_from
            base_reads = [d for d in e.path_from if d["layer"] == 0]
            assert base_reads and all(d["boundary"]["read_at_step"] == d["boundary"]["last_stable_step"] for d in e.path_from)
            fresh = set()
            for j, pa in e.path_answers:
                if j == 0:
                    fresh |= _path_words_of(pa)
            assert set(e.words) <= fresh
            for d in base_reads:
                assert set(d["words"]) <= fresh
            for w, ss in e.word_sources:                                  # provenance: every word keeps its source sentences
                assert ss and all(w in small_index.space.tiers[tl.tier].sentence_units[s] for s in ss)
            # the restored state has no path at step 0 (no unit applied -> no working section): such a bundle gives no word
            for d in e.path_from:
                if d["boundary"]["last_stable_step"] == 0:
                    assert d["words"] == [] and d["listed"] == 0
        assert r.trace["fraction"] == "1/1" and r.trace["restored_states_checked"] > 0
    assert seen > 0


def test_a_layer_two_stable_candidate_is_read_down_through_layer_one(space, monkeypatch):
    monkeypatch.setitem(pl.LEVELS, "low", pl.Budget(max_class=2, max_states=30, max_moves=300))
    idx = make_index(space, SMALL)
    b3 = M.LayerBounds(3, 6, 8, 3, 6, "low", 2)
    c = M.ask_layered(idx, QUESTION, ["RUN", "WORD"], effort="full", options=M.LayerOptions(bounds=b3, candidate="stable"))
    for tl in c.layers:
        for r in tl.runs:
            assert r.trace["ok"]
            for e in r.entries:
                assert set(e.words) <= set(idx.space.tiers[r.tier].postings)
                assert all("boundary" in d for d in e.path_from)


def test_stable_mode_is_exact_and_labelled(stabled):
    def walk(o):
        if isinstance(o, dict):
            for v in o.values():
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)
        else:
            assert not isinstance(o, float)

    walk(stabled.to_json_obj())
    obj = json.loads(stabled.to_bytes())
    assert obj["thought"]["layers"]["options"]["candidate"] == "stable"
    assert all(e["candidate"] == "stable" for e in obj["answer"]["entries"] if e["layer"] > 0)


def _digest_script_stable():
    return _digest_script().replace("M.LayerOptions(bounds=b,feedback='down')", "M.LayerOptions(bounds=b,candidate='stable')")


def test_stable_mode_output_is_byte_identical_across_hash_seeds():
    outs = []
    for seed in ("0", "1", "12345"):
        env = dict(os.environ, PYTHONHASHSEED=seed, PYTHONDONTWRITEBYTECODE="1", PYTHONPATH=ROOT)
        r = subprocess.run([sys.executable, "-c", _digest_script_stable()], capture_output=True, text=True, env=env, cwd=ROOT,
                           timeout=900, stdin=subprocess.DEVNULL)
        assert r.returncode == 0, r.stderr
        outs.append(r.stdout.strip())
    assert outs[0] == outs[1] == outs[2] and int(outs[0].split()[1]) > 1000


def test_cli_accepts_layer_candidate_stable(tmp_path):
    p = tmp_path / "toy.jsonl"
    with open(p, "w", encoding="utf-8") as f:
        for s in DATA:
            f.write(json.dumps({"sent": s, "source": "toy"}, ensure_ascii=False) + "\n")
    r = cli(["ask", "--data", str(p), "--question", QUESTION, "--tiers", "RUN,WORD", "--effort", "fast", "--format", "json",
             "--show-thought", "--layer-candidate", "stable"])
    assert r.returncode == 0, r.stderr
    assert json.loads(r.stdout)["thought"]["layers"]["options"]["candidate"] == "stable"


# ======================================================================================================================
# T8d (L-390..L-399): candidate="stable-seats" (the restored stable state laid out by seats) and candidate="stable-seated"
# (the L-341 boundary scan counting only the question units that take a seat)
# ======================================================================================================================
GOLDEN_STABLE = {   # sha256 of to_bytes() of the T8c tree (505b2e9), toy, SMALL budget, BOUNDS, RUN+WORD, effort full: stable must not move
    "stable-A": "a488c4d11a4a1ad5cc4afa9486a045815c25dfe4373dbb8e2d1fe075f22b594b",
    "stable-B": "c6890f9976b596f03f815606a83ddc96e8f38b2fe1b1655904d675d0ed45a439",
    "stable-both-same": "89e39214b70f20eb64185baff432712868bc2c1c02ddb5719fc14160034a494e",
    "stable-seed+question": "8dba85cf575ae977000c5bdd6895187e17a2c490c544a1babfa924c571a2847c",
}


@pytest.fixture(scope="module")
def seated_run(small_index):
    return M.ask_layered(small_index, QUESTION, TIERS, effort="full", options=M.LayerOptions(bounds=BOUNDS, candidate="stable-seated"))


@pytest.fixture(scope="module")
def seats_run(small_index):
    return M.ask_layered(small_index, QUESTION, TIERS, effort="full", options=M.LayerOptions(bounds=BOUNDS, candidate="stable-seats"))


def test_defaults_path_bag_and_stable_stay_byte_identical_after_t8d(small_index):
    h = lambda o: hashlib.sha256(M.ask_layered(small_index, QUESTION, TIERS, effort="full", options=o).to_bytes()).hexdigest()
    assert M.LayerOptions().candidate == "path"
    assert h(M.LayerOptions(bounds=BOUNDS)) == GOLDEN_PATH["path-default"]
    assert h(M.LayerOptions(bounds=BOUNDS, variants=("A", "B"), granularity="same")) == GOLDEN_PATH["path-both-same"]
    assert h(M.LayerOptions(bounds=BOUNDS, candidate="stable")) == GOLDEN_STABLE["stable-A"]
    assert h(M.LayerOptions(bounds=BOUNDS, candidate="stable", variants=("B",))) == GOLDEN_STABLE["stable-B"]
    assert h(M.LayerOptions(bounds=BOUNDS, candidate="stable", variants=("A", "B"), granularity="same")) == GOLDEN_STABLE["stable-both-same"]
    assert h(M.LayerOptions(bounds=BOUNDS, candidate="stable", down_query="seed+question")) == GOLDEN_STABLE["stable-seed+question"]
    assert h(M.LayerOptions(bounds=BOUNDS, candidate="bag", variants=M.VARIANTS, granularity="same")) == \
        hashlib.sha256(M.ask_layered(small_index, QUESTION, TIERS, effort="full",
                                     options=opts()).to_bytes()).hexdigest()


def _independent_layout(small_index, tier, r, d):
    """The laid-out restored state of the lower read d of the upper run r, re-derived with a fresh prefix scan."""
    st = M.stack_of(small_index, tier)
    units = M.lower_units(r.query_units)
    j = d["boundary"]["last_stable_step"]
    X = d["seed"]
    if j == 0:
        flats, _ = cy.members_of(st.store.cross_for(X), BOUNDS.members, True)
    else:
        res = M._prefix_read(st.base, st.facts, st.store, X, units[:j], BOUNDS, A.DEFAULT_BUDGET)
        assert M._is_stable_read(res)
        flats = [e.flat for sr in res.reads for m in sr.members for e in m.settled.ends]
    flats = sorted(dict.fromkeys(flats), key=pl._flat_sort_key)
    return M.layout_of(flats[0], lambda c: c), len(flats), st


def test_stable_seats_is_the_restored_state_laid_out_by_seats_exactly(small_index, seats_run):
    checked = step0 = 0
    for tl in seats_run.layers:
        for r in tl.runs:
            assert r.candidate == "stable-seats" and r.entries and r.trace["ok"] and r.trace["fraction"] == "1/1"
            assert r.without_path_words == 0                       # no path is needed: every bundle gives its state
            for e in r.entries:
                assert e.mode == "stable-seats" and e.seats is not None
                centre, arms = e.seats
                assert len(arms) == 6 and centre is not None
                assert e.words == tuple(sorted({centre} | {c for leg in arms for c in leg if c is not None}))
                assert dict(e.word_sources).keys() == set(e.words) and all(ss for _, ss in e.word_sources)
                for w, ss in e.word_sources:
                    assert all(w in small_index.space.tiers[tl.tier].sentence_units[s] for s in ss)
                assert r.k == 1
                for d in e.path_from:
                    lay, n_flats, st = _independent_layout(small_index, tl.tier, r, d)
                    assert lay == e.seats                           # the same seats as the restored state, nothing else
                    assert set(e.words) == set(M.placed_units(st.store.cross_for(d["seed"])))   # a move only permutes seats
                    assert d["seats"] == sum(1 for leg in lay[1] for c in leg if c is not None)
                    assert d["boundary"]["restored"] in (True, False)
                    checked += 1
                    step0 += d["boundary"]["last_stable_step"] == 0
    assert checked > 0 and step0 > 0                               # a state restored to step 0 still gives a candidate


def test_stable_seats_equal_structures_are_one_entry_and_counts_are_recorded(seats_run):
    obj = seats_run.to_json_obj()
    for tl in obj["thought"]["layers"]["per_tier"].values():
        for r in tl["runs"]:
            keys = [json.dumps(e["seats"], sort_keys=True) for e in r["entries"]]
            assert len(keys) == len(set(keys))
            for e in r["entries"]:
                s = e["seats"]
                assert e["candidate"] == "stable-seats" and e["words"] == sorted(e["words"])
                assert s["n_words"] == len(e["words"]) and s["n_seats"] == s["n_words"] - 1 == sum(1 for leg in s["arms"] for c in leg if c is not None)
                assert e["word_sources"].keys() == set(e["words"]) and e["path_from"]
    assert json.loads(seats_run.to_bytes())["thought"]["layers"]["options"]["candidate"] == "stable-seats"


def test_stable_seats_candidates_are_not_a_flat_bag(seats_run):
    # the layout carries the seat of each word: two entries with the same word set but another layout stay two entries
    ents = [e for tl in seats_run.layers for r in tl.runs for e in r.entries]
    assert any(any(c is not None for leg in e.seats[1] for c in leg) for e in ents)
    assert all(len([c for leg in e.seats[1] for c in leg if c is not None]) + 1 == len(e.words) for e in ents)


def test_stable_seated_never_puts_the_boundary_at_an_energy_only_unit(seated_run):
    n = 0
    for tl in seated_run.layers:
        for r in tl.runs:
            assert r.candidate == "stable-seated" and r.trace["ok"]
            for d in r.boundaries:
                b = d["boundary"]
                assert b["mode"] == "seated" and b["seated_units"] == min(b["query_units"], 6)
                if b["restored"]:
                    assert b["first_unstable_step"] <= 6 and b["unstable_unit_attached"] is True
                    assert b["last_stable_step"] == b["first_unstable_step"] - 1 and b["state_stable"] is True
                else:
                    assert b["first_unstable_step"] is None and b["last_stable_step"] == b["query_units"]
                n += 1
    assert n > 0


def test_stable_seated_skips_a_break_made_by_an_energy_only_unit(small_index, monkeypatch):
    st = M.stack_of(small_index, "RUN")
    units = tuple(sorted(st.base.postings))[:9]
    orig = M._is_stable_read
    monkeypatch.setattr(M, "_is_stable_read", lambda res: orig(res) and len(res.ctx.query) != 8)      # the 8th unit breaks the cross
    for X in ("東京", "日本"):
        plain = M.stable_boundary(st.base, st.facts, st.store, X, units, BOUNDS, A.DEFAULT_BUDGET, {})
        seated = M.stable_boundary(st.base, st.facts, st.store, X, units, BOUNDS, A.DEFAULT_BUDGET, {}, seated=True)
        assert plain["boundary"]["first_unstable_step"] == 8 and plain["boundary"]["last_stable_step"] == 7
        b = seated["boundary"]
        assert b["first_unstable_step"] is None and b["restored"] is False and b["last_stable_step"] == 9   # applied, never a boundary
        assert b["seated_units"] == 6 and b["unstable_unit"] is None
    # a break at a seated unit is the same boundary in both modes
    monkeypatch.setattr(M, "_is_stable_read", lambda res: orig(res) and len(res.ctx.query) != 3)
    a = M.stable_boundary(st.base, st.facts, st.store, "東京", units, BOUNDS, A.DEFAULT_BUDGET, {})["boundary"]
    s = M.stable_boundary(st.base, st.facts, st.store, "東京", units, BOUNDS, A.DEFAULT_BUDGET, {}, seated=True)["boundary"]
    assert a["first_unstable_step"] == s["first_unstable_step"] == 3 and a["last_stable_step"] == s["last_stable_step"] == 2
    assert a["backup"] == s["backup"]


def test_t8d_modes_are_exact_and_equal_across_hash_seeds():
    def walk(o):
        if isinstance(o, dict):
            for v in o.values():
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)
        else:
            assert not isinstance(o, float)

    for cand in ("stable-seats", "stable-seated"):
        script = _digest_script().replace("M.LayerOptions(bounds=b,feedback='down')", "M.LayerOptions(bounds=b,candidate=%r)" % cand)
        outs = []
        for seed in ("0", "1", "12345"):
            env = dict(os.environ, PYTHONHASHSEED=seed, PYTHONDONTWRITEBYTECODE="1", PYTHONPATH=ROOT)
            r = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True, env=env, cwd=ROOT,
                               timeout=900, stdin=subprocess.DEVNULL)
            assert r.returncode == 0, r.stderr
            outs.append(r.stdout.strip())
        assert outs[0] == outs[1] == outs[2] and int(outs[0].split()[1]) > 1000


def test_t8d_json_has_no_float(seats_run, seated_run):
    def walk(o):
        if isinstance(o, dict):
            for v in o.values():
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)
        else:
            assert not isinstance(o, float)

    walk(seats_run.to_json_obj())
    walk(seated_run.to_json_obj())
    obj = json.loads(seated_run.to_bytes())
    assert obj["thought"]["layers"]["options"]["candidate"] == "stable-seated"
    assert all(e["candidate"] == "stable-seated" for e in obj["answer"]["entries"] if e["layer"] > 0)


def test_cli_accepts_the_t8d_layer_candidates(tmp_path):
    p = tmp_path / "toy.jsonl"
    with open(p, "w", encoding="utf-8") as f:
        for s in DATA:
            f.write(json.dumps({"sent": s, "source": "toy"}, ensure_ascii=False) + "\n")
    for cand in ("stable-seats", "stable-seated"):
        r = cli(["ask", "--data", str(p), "--question", QUESTION, "--tiers", "RUN,WORD", "--effort", "fast", "--format", "json",
                 "--show-thought", "--layer-candidate", cand])
        assert r.returncode == 0, r.stderr
        assert json.loads(r.stdout)["thought"]["layers"]["options"]["candidate"] == cand


def test_a_layer_two_seats_or_seated_candidate_traces_down_to_base_words(space, monkeypatch):
    monkeypatch.setitem(pl.LEVELS, "low", pl.Budget(max_class=2, max_states=30, max_moves=300))
    idx = make_index(space, SMALL)
    b3 = M.LayerBounds(3, 6, 8, 3, 6, "low", 2)
    for cand in ("stable-seats", "stable-seated"):
        c = M.ask_layered(idx, QUESTION, ["RUN", "WORD"], effort="full", options=M.LayerOptions(bounds=b3, candidate=cand))
        for tl in c.layers:
            for r in tl.runs:
                assert r.trace["ok"]
                for e in r.entries:
                    assert set(e.words) <= set(idx.space.tiers[r.tier].postings)
                    assert e.word_sources is not None and all(ss for _, ss in e.word_sources)


# ======================================================================================================================
# T8e (L-430..): candidate="stable-seats-path" = one candidate per upper entry: its bundles in the upper path's order,
# each with the seat layout of its restored stable state (as stable-seats builds it)
# ======================================================================================================================
@pytest.fixture(scope="module")
def seatspath_run(small_index):
    return M.ask_layered(small_index, QUESTION, TIERS, effort="full", options=M.LayerOptions(bounds=BOUNDS, candidate="stable-seats-path"))


def test_defaults_and_old_modes_stay_byte_identical_after_t8e(small_index):
    h = lambda o: hashlib.sha256(M.ask_layered(small_index, QUESTION, TIERS, effort="full", options=o).to_bytes()).hexdigest()
    assert M.LayerOptions().candidate == "path"
    assert h(M.LayerOptions(bounds=BOUNDS)) == GOLDEN_PATH["path-default"]
    assert h(M.LayerOptions(bounds=BOUNDS, variants=("A", "B"), granularity="same")) == GOLDEN_PATH["path-both-same"]
    assert h(M.LayerOptions(bounds=BOUNDS, candidate="stable")) == GOLDEN_STABLE["stable-A"]
    assert h(M.LayerOptions(bounds=BOUNDS, candidate="stable", variants=("A", "B"), granularity="same")) == GOLDEN_STABLE["stable-both-same"]
    assert h(M.LayerOptions(bounds=BOUNDS, candidate="stable", down_query="seed+question")) == GOLDEN_STABLE["stable-seed+question"]


def _order_independent(a_entry):
    """The bundles of an upper entry in the upper path's order, derived again from the answer's items."""
    out = []
    for a in a_entry.arrangements:
        for p in a.paths:
            out.extend(p.words)
        out.append(a.centre)
    out.extend(a_entry.words)
    return tuple(dict.fromkeys(out))


def test_stable_seats_path_is_the_union_of_the_bundles_stable_seats_in_path_order(small_index, seatspath_run, seats_run):
    seats_by = {}                                   # (tier, k, variant, bundle) -> the layout stable-seats gives that bundle
    for tl in seats_run.layers:
        for r in tl.runs:
            for e in r.entries:
                for b in e.bundles:
                    seats_by.setdefault((tl.tier, r.k, r.variant, b), set()).add(e.seats)
    n = multi = 0
    for tl in seatspath_run.layers:
        for r in tl.runs:
            assert r.candidate == "stable-seats-path" and r.trace["ok"] and r.trace["fraction"] == "1/1"
            expected = []
            for ae in r.answer.entries:
                order = _order_independent(ae)
                lays = tuple((b, sorted(seats_by[(tl.tier, r.k, r.variant, b)], key=M.seats_key)[0]) for b in order
                             if (tl.tier, r.k, r.variant, b) in seats_by)
                if lays:
                    expected.append(lays)
            got = [e.layouts for e in r.entries]
            keyed = lambda L: tuple(M.seats_key(l) for _, l in L)
            assert sorted(set(map(keyed, expected))) == sorted(map(keyed, got))          # equal candidates are one, nothing else
            assert len({keyed(L) for L in got}) == len(got)
            for e in r.entries:
                assert e.mode == "stable-seats-path" and e.seats is None and e.layouts
                assert e.words == tuple(sorted({w for _, l in e.layouts for w in M.seats_words(l)}))     # the union of the layouts
                assert set(e.bundles) == {b for b, _ in e.layouts}
                assert dict(e.word_sources).keys() == set(e.words) and all(ss for _, ss in e.word_sources)
                for w, ss in e.word_sources:
                    assert all(w in small_index.space.tiers[tl.tier].sentence_units[s] for s in ss)
                for b, l in e.layouts:                                                  # each layout is a stable-seats layout of that bundle
                    assert l in seats_by[(tl.tier, r.k, r.variant, b)]
                n += 1
                multi += len(e.layouts) > 1
    assert n > 0 and multi > 0                                                           # at least one candidate holds several bundles


def test_stable_seats_path_json_records_bundles_words_seats(seatspath_run):
    obj = seatspath_run.to_json_obj()
    seen = 0
    for tl in obj["thought"]["layers"]["per_tier"].values():
        for r in tl["runs"]:
            assert r["candidate"] == "stable-seats-path" and r["entries_without_path_words"] >= 0
            for e in r["entries"]:
                assert e["candidate"] == "stable-seats-path" and e["words"] == sorted(e["words"])
                assert e["n_bundles"] == len(e["layouts"]) and e["n_words"] == len(e["words"])
                assert e["n_seats"] == sum(l["seats"]["n_seats"] for l in e["layouts"])
                assert all(l["seats"]["n_seats"] == l["seats"]["n_words"] - 1 for l in e["layouts"])
                assert e["word_sources"].keys() == set(e["words"]) and "seats" not in e
                seen += 1
    assert seen > 0
    assert json.loads(seatspath_run.to_bytes())["thought"]["layers"]["options"]["candidate"] == "stable-seats-path"

    def walk(o):
        if isinstance(o, dict):
            for v in o.values():
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)
        else:
            assert not isinstance(o, float)
    walk(obj)


def test_stable_seats_path_is_exact_and_equal_across_hash_seeds():
    script = _digest_script().replace("M.LayerOptions(bounds=b,feedback='down')", "M.LayerOptions(bounds=b,candidate='stable-seats-path')")
    outs = []
    for seed in ("0", "1", "12345"):
        env = dict(os.environ, PYTHONHASHSEED=seed, PYTHONDONTWRITEBYTECODE="1", PYTHONPATH=ROOT)
        r = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True, env=env, cwd=ROOT,
                           timeout=900, stdin=subprocess.DEVNULL)
        assert r.returncode == 0, r.stderr
        outs.append(r.stdout.strip())
    assert outs[0] == outs[1] == outs[2] and int(outs[0].split()[1]) > 1000


def test_cli_accepts_stable_seats_path(tmp_path):
    p = tmp_path / "toy.jsonl"
    with open(p, "w", encoding="utf-8") as f:
        for s in DATA:
            f.write(json.dumps({"sent": s, "source": "toy"}, ensure_ascii=False) + "\n")
    r = cli(["ask", "--data", str(p), "--question", QUESTION, "--tiers", "RUN,WORD", "--effort", "fast", "--format", "json",
             "--show-thought", "--layer-candidate", "stable-seats-path"])
    assert r.returncode == 0, r.stderr
    assert json.loads(r.stdout)["thought"]["layers"]["options"]["candidate"] == "stable-seats-path"


def test_a_layer_two_stable_seats_path_candidate_traces_down_to_base_words(space, monkeypatch):
    monkeypatch.setitem(pl.LEVELS, "low", pl.Budget(max_class=2, max_states=30, max_moves=300))
    idx = make_index(space, SMALL)
    b3 = M.LayerBounds(3, 6, 8, 3, 6, "low", 2)
    c = M.ask_layered(idx, QUESTION, ["RUN", "WORD"], effort="full", options=M.LayerOptions(bounds=b3, candidate="stable-seats-path"))
    for tl in c.layers:
        for r in tl.runs:
            assert r.trace["ok"]
            for e in r.entries:
                assert set(e.words) <= set(idx.space.tiers[r.tier].postings)
                assert e.word_sources is not None and all(ss for _, ss in e.word_sources)
