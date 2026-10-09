"""G3-e tests (L-640..): the question path over sliding windows (verantyx/line3/slide_query.py, `structure="slide"`).

Part 1 (the window index): build / cache / load, a cache for another corpus / slide spec / place spec / tier is refused, the seated set of a
window is the same for every member of its class (what "holds a question unit" relies on).
Part 2 (intake and grammar): the question is cut like the flat path (V2), the form (slot / predicate / standin / plain), the read order
(the slot's kind first, then the ladder), the axis order.
Part 3 (exact skip, L-644 / L-646): reading every window gives the same entries as reading only the windows that hold a question unit; the
admission gate is what makes it exact (without it a window with no question unit would answer).
Part 4 (read order, cap): the entries do not depend on the order of reading unless the budget stops; the cap reads whole tied blocks; the
presets are T7b's counts in windows; `partial` and the counts.
Part 5 (entries, abstentions, verdict): the shape (T7b keys + axis, window, stable_strict), never merged across axes or windows, typed
abstentions, the verdict rule, stable_strict handling.
Part 6 (defaults, bytes): structure="flat" is the default and changes nothing; the slide result under three hash seeds; no float; the
command line.
"""
import ast
import copy
import dataclasses
import json
import os
import pickle
import subprocess
import sys

import pytest

from verantyx.line3 import ask as A
from verantyx.line3 import grammar as gr
from verantyx.line3 import slide as SL
from verantyx.line3 import slide_place as SP
from verantyx.line3 import slide_query as Q
from verantyx.line3 import slide_ratios as SR
from verantyx.line3 import space as sp

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PY = sys.executable

TOY = [
    ("A", "東京は日本の首都である。"),      # 0
    ("A", "東京は日本の都市である。"),      # 1
    ("A", "日本の首都は東京である。"),      # 2
    ("B", "犬が猫を追う。"),                # 3
    ("B", "猫が魚を食べる。"),              # 4
    ("B", "魚が海にいる。"),                # 5
    ("C", "京都は古い都である。"),          # 6   a one-sentence article
    ("D", "東京タワーは東京にある。"),      # 7
    ("D", "東京は人口が多い。"),            # 8
]
QUESTIONS = ["日本の首都は何ですか", "東京は何ですか", "猫は何を食べますか", "犬が追うのは何ですか", "魚は何ですか", "京都は何ですか",
             "海は何ですか", "人口は何ですか", "東京タワーは何ですか", "首都は何ですか", "猫が食べるのは何ですか", "存在しない語は何ですか"]
LEVEL = "low"


def toy_rows():
    seen = {}
    out = []
    for t, s in TOY:
        i = seen.get(t, 0)
        seen[t] = i + 1
        out.append({"title": t, "sent": s, "source": "%s#%d" % (t, i)})
    return out


@pytest.fixture(scope="module")
def rows():
    return toy_rows()


@pytest.fixture(scope="module")
def space(rows):
    return sp.build_space(rows)


@pytest.fixture(scope="module")
def wi(space, rows):
    return Q.WindowIndex.from_space(space, None, rows=rows, level=LEVEL)


@pytest.fixture(scope="module")
def data_file(tmp_path_factory, rows):
    p = tmp_path_factory.mktemp("g3e") / "toy.jsonl"
    p.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
    return str(p)


def with_docs(wi, edit):
    """A copy of the window index whose placement records were edited by `edit(doc)` (the records are plain JSON)."""
    docs = [copy.deepcopy(w.doc) for w in wi.windows]
    for d in docs:
        edit(d)
    return Q.WindowIndex(wi.space, wi.slide, wi.spec, docs)


# ---------------------------------------------------------------------------------------------------------------------------------
# Part 1: the window index
# ---------------------------------------------------------------------------------------------------------------------------------
def test_index_has_every_window_and_pads_every_article(wi):
    # 9 sentences, 4 articles: 5 pairs + 4 last-sentence windows (padding "one": one constructed sentence per article)
    assert len(wi.windows) == 9
    assert sum(1 for w in wi.windows if len(w.window.sids) == 2) == 5
    assert sum(1 for w in wi.windows if w.constructed) == 4 and all(len(w.window.sids) == 1 for w in wi.windows if w.constructed)
    assert [w.n for w in wi.windows] == sorted(w.n for w in wi.windows)


def test_seated_set_is_the_same_for_every_member_of_a_class(wi):
    for w in wi.windows:
        assert w.seated == w.seated_any, w.n
        for m in w.doc["members"]:
            assert frozenset(SP.unit_of(t) for t in m if t is not None) == w.seated


def test_cache_roundtrip_and_refusals(tmp_path, space, rows):
    d = str(tmp_path)
    a = Q.WindowIndex.from_space(space, d, rows=rows, level=LEVEL)
    files = os.listdir(d)
    assert len(files) == 1 and files[0].startswith("slidewin_" + space.sha256()[:12] + "_RUN_" + a.slide.spec.sha256()[:12] + "_" + a.spec.sha256()[:12])
    b = Q.WindowIndex.from_space(space, d, rows=rows, level=LEVEL, build=False)       # loaded, not placed
    assert [w.doc for w in a.windows] == [w.doc for w in b.windows] and b.header["place_spec_sha256"] == a.spec.sha256()
    assert Q.ask_slide(a, QUESTIONS[2], agreement="two_if_single_edge").to_bytes() == Q.ask_slide(b, QUESTIONS[2], agreement="two_if_single_edge").to_bytes()
    # another place spec (budget level) has another file: with build=False it is not there
    with pytest.raises(FileNotFoundError):
        Q.WindowIndex.from_space(space, d, rows=rows, level="mid", build=False)
    # a file that is renamed to the name of another spec / corpus is refused by its header, never read
    path = os.path.join(d, files[0])
    with open(path, "rb") as f:
        rec = pickle.load(f)
    for key in ("corpus_sha256", "slide_spec_sha256", "place_spec_sha256", "tier", "padding"):
        bad = dict(rec, **{key: "0" * 64 if key.endswith("sha256") else "WORD" if key == "tier" else "none"})
        with open(path, "wb") as f:
            pickle.dump(bad, f)
        with pytest.raises(ValueError, match="not for this corpus"):
            Q.WindowIndex.from_space(space, d, rows=rows, level=LEVEL, build=False)
    with open(path, "wb") as f:
        pickle.dump(rec, f)
    # another corpus: its own file name; the old file copied under that name is refused
    rows2 = rows[:-1] + [dict(rows[-1], sent="東京は人口が少ない。")]
    space2 = sp.build_space(rows2)
    other = Q.WindowIndex.from_space(space2, None, rows=rows2, level=LEVEL)
    name2 = Q.cache_name(space2.sha256(), "RUN", other.slide.spec.sha256(), other.spec.sha256())
    with open(os.path.join(d, name2), "wb") as f:
        pickle.dump(rec, f)
    with pytest.raises(ValueError, match="not for this corpus"):
        Q.WindowIndex.from_space(space2, d, rows=rows2, level=LEVEL, build=False)
    with pytest.raises(ValueError, match="RUN tier only"):
        Q.WindowIndex.from_space(space, None, rows=rows, tier="WORD")


def test_cache_with_a_changed_record_is_refused(wi):
    docs = [copy.deepcopy(w.doc) for w in wi.windows]
    docs[0]["window"]["n"] = 99
    with pytest.raises(ValueError, match="does not match"):
        Q.WindowIndex(wi.space, wi.slide, wi.spec, docs)
    with pytest.raises(ValueError, match="holds 3 windows"):
        Q.WindowIndex(wi.space, wi.slide, wi.spec, [w.doc for w in wi.windows[:3]])


# ---------------------------------------------------------------------------------------------------------------------------------
# Part 2: intake, form, order
# ---------------------------------------------------------------------------------------------------------------------------------
def test_intake_cuts_the_question_like_the_flat_path(wi):
    it = Q.intake(wi, "猫は何を食べますか")
    flat = A.cy.split_question("RUN", "猫は何を食べますか")
    assert it.all_units == tuple(flat)
    assert set(it.units) <= set(flat) and "は" not in it.units and "何" not in it.units          # V2: function / question words are not units
    assert it.qset == frozenset(it.ctx.energy_units) and "猫" in it.qset


def test_form_slot_predicate_standin_plain(wi):
    f = lambda q: Q.intake(wi, q)
    assert f("猫は何を食べますか").form == "slot" and f("猫は何を食べますか").slot == "を"
    assert f("日本の首都は何ですか").form == "predicate" and f("日本の首都は何ですか").slot is None
    assert f("存在しない語は何ですか").form == "predicate"          # predicate before stand-in (L-642)
    assert f("犬が追うのは何ですか").form == "standin"
    assert f("東京は日本の首都").form == "plain" and Q.classify_form(f("東京は日本の首都").reading) == "plain"
    o = f("猫は何を食べますか").form_obj()
    assert o["form"] == "slot" and o["slot"] == "を" and "kind" in o["read_order"]


def test_read_order_puts_the_slot_kind_first_then_the_ladder(wi):
    it = Q.intake(wi, "魚は何ですか")
    plain = Q.plan_windows(wi, dataclasses.replace(it, slot=None), within="none")
    assert [b.reason for b in plain.blocks][0] != "match"
    ladder = [gr.WEIGHTS[b.kind.particles[0]] for b in plain.blocks if b.reason == "particle"]
    assert ladder == sorted(ladder, reverse=True)                  # single-particle kinds by the ladder weight, then tied, then none
    order = [b.reason for b in plain.blocks]
    assert order == sorted(order, key=["match", "particle", "tied", "none"].index)
    some = next(b for b in plain.blocks if b.reason == "particle" and b.kind.particles[0] != "の")
    m = Q.plan_windows(wi, dataclasses.replace(it, slot=some.kind.particles[0]), within="none")
    assert m.blocks[0].reason == "match" and m.blocks[0].kind == some.kind
    assert sorted(w for b in m.blocks for w in b.windows) == sorted(w for b in plain.blocks for w in b.windows)     # only ordered


def test_axis_order_follows_the_slot_arm(wi):
    f = wi.foundation
    assert Q.axis_order(None, f) == SR.read_order(SR.foundation_weights(f)) == ("x", "y", "z")
    assert Q.axis_order("の", f) == ("x", "y", "z") and Q.axis_order("を", f)[0] == "z" and Q.axis_order("で", f)[0] == "y"
    assert Q.axis_order("は", f) == ("x", "y", "z")                 # は is the centre: no arm


# ---------------------------------------------------------------------------------------------------------------------------------
# Part 3: the exact skip
# ---------------------------------------------------------------------------------------------------------------------------------
@pytest.mark.parametrize("agreement", SR.AGREEMENTS)
@pytest.mark.parametrize("members", Q.MEMBERS)
def test_exact_skip_reading_everything_gives_the_same_entries(wi, agreement, members):
    skipped_somewhere = False
    for q in QUESTIONS:
        a = Q.ask_slide(wi, q, agreement=agreement, members=members)
        b = Q.ask_slide(wi, q, agreement=agreement, members=members, skip="none")
        assert a.entries == b.entries and a.abstentions == b.abstentions and a.verdict == b.verdict, q
        assert a.answer_obj()["entries"] == b.answer_obj()["entries"]
        assert b.windows_read == len(wi.windows) and a.windows_read == len(a.plan.read) <= b.windows_read
        skipped_somewhere = skipped_somewhere or a.windows_read < b.windows_read
        # what exact skip did not read changes nothing: those reads admit no entry, every axis is typed no_question_unit or abstains
        planned = set(a.plan.read)
        for r in b.reads:
            if r.window not in planned:
                assert r.entries == () and all(x["kind"] in (Q.NO_QUESTION_UNIT, Q.MIXED) or x["kinds"] for x in r.abstentions)
                assert all(k in Q.ABSTENTION_KINDS for x in r.abstentions for k in x["kinds"])
    assert skipped_somewhere


def test_the_gate_is_what_makes_the_skip_exact(wi):
    """E_Q is the corpus', so a window with no question unit still has flows and agreements: without the gate it answers."""
    extra = 0
    for q in QUESTIONS[:11]:
        a = Q.ask_slide(wi, q, agreement="two_if_single_edge")
        b = Q.ask_slide(wi, q, agreement="two_if_single_edge", skip="none", gate=False)
        planned = set(a.plan.read)
        extra += sum(len(r.entries) for r in b.reads if r.window not in planned)
        assert [e for r in b.reads if r.window in planned for e in r.entries] == list(a.entries)          # candidates read the same
    assert extra > 0
    # with the gate, a window that holds no question unit gives only typed abstentions
    r = Q.read_window(wi, wi.by_n[6], Q.intake(wi, "猫は何を食べますか"), agreement="two_if_single_edge")
    assert r.entries == () and any(Q.NO_QUESTION_UNIT in x["kinds"] for x in r.abstentions)


def test_hold_sentences_variant_holds_a_superset(wi):
    it = Q.intake(wi, "猫は何を食べますか")
    seats = Q.plan_windows(wi, it, hold="seats")
    sents = Q.plan_windows(wi, it, hold="sentences")
    assert set(seats.read) <= set(sents.read)


def test_standins_extend_the_candidates_only(wi):
    it = Q.intake(wi, "犬が追うのは何ですか")
    off = Q.plan_windows(wi, it, standins="off")
    on = Q.plan_windows(wi, dataclasses.replace(it, standins=("魚", "海")), standins="on")
    assert set(off.read) <= set(on.read) and on.candidates > off.candidates
    r = Q.ask_slide(wi, "犬が追うのは何ですか", standins="on")
    assert r.windows_read >= 1 and all(e["via_standin"] is False or e["via_standin"] is True for e in r.entries)


# ---------------------------------------------------------------------------------------------------------------------------------
# Part 4: order and the cap
# ---------------------------------------------------------------------------------------------------------------------------------
@pytest.mark.parametrize("within", Q.WITHINS)
def test_entries_do_not_depend_on_the_order_of_reading(wi, within):
    moved = False
    for q in QUESTIONS:
        base = Q.ask_slide(wi, q, agreement="two_if_single_edge", within=within)
        for seed in (1, 2, 3):
            r = Q.ask_slide(wi, q, agreement="two_if_single_edge", within=within, shuffle=seed)
            assert r.entry_keys() == base.entry_keys() and r.verdict == base.verdict and r.partial is False, (q, seed)
            assert sorted(r.plan.read) == sorted(base.plan.read)
            assert sorted(SL.canonical(e) for e in r.entries) == sorted(SL.canonical(e) for e in base.entries)
            moved = moved or r.plan.read != base.plan.read
    assert moved


def test_cap_reads_whole_blocks_and_reports_partial(wi):
    it = Q.intake(wi, "東京は何ですか")
    full = Q.plan_windows(wi, it, within="none")
    assert full.candidates >= 4 and not full.partial and full.boundary == 0
    sizes = [len(b.windows) for b in full.blocks]
    flat = [n for b in full.blocks for n in b.windows]
    for cap in range(0, full.candidates + 2):
        p = Q.plan_windows(wi, it, within="none", cap=cap)
        # the windows read are a prefix of the read order made of WHOLE blocks; the first block that does not fit stops the read
        acc, k = 0, 0
        while k < len(sizes) and acc + sizes[k] <= cap:
            acc += sizes[k]
            k += 1
        assert p.read == tuple(flat[:acc]) and set(p.read) | set(p.unread) == set(flat)
        assert p.partial == (acc < len(flat)) and p.boundary == (sizes[k] if k < len(sizes) else 0)
        assert p.read_obj()["left_unread"] == len(p.unread) and p.read_obj()["would_read_in_full"] == full.candidates
    with pytest.raises(ValueError):
        Q.plan_windows(wi, it, cap=-1)


def test_a_tied_block_larger_than_the_cap_is_not_split_and_nothing_is_read(wi):
    q = "日本の首都は何ですか"                                        # three windows of the same kind (の, で): one block
    it = Q.intake(wi, q)
    full = Q.plan_windows(wi, it, within="none")
    first = len(full.blocks[0].windows)
    assert first >= 2
    p = Q.plan_windows(wi, it, within="none", cap=first - 1)
    assert p.read == () and p.boundary == first and p.partial
    r = Q.ask_slide(wi, q, nodes=first - 1, within="none")
    assert r.verdict == Q.UNKNOWN_NOT_READ and r.windows_read == 0 and r.partial and r.entries == ()


def test_within_key_splits_a_grammar_group_by_the_question_units_held(wi):
    it = Q.intake(wi, "日本の首都は何ですか")
    coarse = Q.plan_windows(wi, it, within="none")
    fine = Q.plan_windows(wi, it, within="qcount")
    assert sorted(n for b in fine.blocks for n in b.windows) == sorted(n for b in coarse.blocks for n in b.windows)
    assert len(fine.blocks) >= len(coarse.blocks)
    keys = {}
    for b in fine.blocks:
        keys.setdefault((b.reason, b.kind), []).append(b.key)
    for ks in keys.values():
        assert ks == sorted(ks, reverse=True) and len(set(ks)) == len(ks)       # inside a group, more question units first; equal = one block


def test_the_presets_are_t7bs_counts_in_windows(wi):
    assert A.EFFORTS["fast"][0] == 4 and A.EFFORTS["standard"][0] == 10 and A.EFFORTS["full"][0] is None
    for q in ("東京は何ですか", "猫は何を食べますか"):
        for eff, cap in (("fast", 4), ("standard", 10), ("full", None)):
            r = Q.ask_slide(wi, q, effort=eff)
            assert r.plan.cap == cap and r.effort == eff and r.config["node_budget"] == cap
            assert r.plan.read == Q.plan_windows(wi, Q.intake(wi, q), cap=cap).read
        r = Q.ask_slide(wi, q, nodes=2)
        assert r.effort == "nodes" and r.plan.cap == 2 and len(r.plan.read) <= 2
        assert Q.ask_slide(wi, q).plan.cap is None
    with pytest.raises(ValueError):
        Q.ask_slide(wi, "東京は何ですか", effort="slow")
    with pytest.raises(ValueError):
        Q.ask_slide(wi, "東京は何ですか", agreement="all")


def test_partial_is_in_the_answer(wi):
    r = Q.ask_slide(wi, "東京は何ですか", nodes=1, within="qcount")
    a = r.answer_obj()
    assert a["structure"] == "slide" and a["partial"] == r.partial and a["windows_read"] == r.windows_read
    assert a["read"]["left_unread"] == len(r.plan.unread) and a["read"]["candidate_windows"] == r.plan.candidates
    if r.partial:
        assert "未読" in Q.format_text(r)


# ---------------------------------------------------------------------------------------------------------------------------------
# Part 5: entries, abstentions, the verdict
# ---------------------------------------------------------------------------------------------------------------------------------
T7B_KEYS = {"tier", "words", "arrangements", "centres", "stability", "source_sids"}


def all_answers(wi):
    return [Q.ask_slide(wi, q, agreement=ag) for q in QUESTIONS for ag in SR.AGREEMENTS]


def test_entry_shape(wi):
    seen = 0
    for r in all_answers(wi):
        for e in r.entries:
            seen += 1
            assert T7B_KEYS <= set(e) and {"axis", "label", "window", "stable_strict", "trace", "ratios", "sources", "seats"} <= set(e)
            assert e["tier"] == "RUN" and e["structure"] == "slide" and e["label"] == "slide:" + e["axis"] and e["axis"] in ("x", "z")
            assert len(e["words"]) == 1 and e["arrangements"] >= 1 and e["arrangements"] == e["members_agreeing"] <= e["members_read"] <= e["class_size"]
            assert e["stability"] is None and e["stable_strict"] is True          # committed records carry no stable_strict: treated as True
            assert set(e["window"]) == {"n", "title", "sids", "idx", "constructed"} and e["window"]["n"] in wi.by_n
            assert e["trace"] == {"ok": True, "members_checked": e["members_agreeing"]}
            assert set(e["ratios"]) == {"section", "edge_flow", "binding"} and e["sources"] and e["seats"]
            assert all(s["unit"] == e["words"][0] for s in e["seats"])            # every answer unit maps to seats (keyed unit, sid)
            assert set(e["source_sids"]) >= {s["sid"] for s in e["seats"]}
            assert set(e["centres"]) <= wi.by_n[e["window"]["n"]].seated
        js = r.to_json_obj()                                                       # plain JSON, Fractions as "n/d"
        assert json.loads(json.dumps(js)) == js
    assert seen > 0


def test_every_trace_holds(wi):
    for r in all_answers(wi):
        assert all(x.trace_ok for x in r.reads)
        assert all(x.trace_checks >= 0 for x in r.reads)
        for e in r.entries:
            assert e["trace"]["ok"]


def test_axes_and_windows_are_never_merged(wi):
    for r in all_answers(wi):
        keys = [(e["window"]["n"], e["axis"], e["words"][0]) for e in r.entries]
        assert len(keys) == len(set(keys))
        assert r.verdict == (Q.ANSWER if len(r.entries) == 1 else Q.CHOICE if len(r.entries) > 1 else r.verdict)
    # the same article twice: the same unit answers in two windows, and the list shows it twice (one entry per window)
    rws = toy_rows()
    twin = rws[:3] + [dict(r, title="A2", source=r["source"].replace("A#", "A2#")) for r in rws[:3]] + rws[3:]
    sp2 = sp.build_space(twin)
    wi2 = Q.WindowIndex.from_space(sp2, None, rows=twin, level=LEVEL)
    r = Q.ask_slide(wi2, "猫は何を食べますか", agreement="two_if_single_edge")
    r2 = Q.ask_slide(wi2, "日本の首都は何ですか", agreement="two_if_single_edge")
    units = {}
    for e in r2.entries:
        units.setdefault((e["axis"], e["words"][0]), set()).add(e["window"]["n"])
    assert any(len(v) >= 2 for v in units.values()), r2.entries
    assert len(r2.entries) == sum(len(v) for v in units.values())


def test_two_agreeing_axes_of_one_window_are_two_entries(wi):
    """Looked for over the toy questions (what a placement gives is not assumed): when one window agrees on two axes, the list has one
    entry per axis, with the axis label, and nothing is merged."""
    hit = 0
    for r in all_answers(wi):
        by_w = {}
        for e in r.entries:
            by_w.setdefault(e["window"]["n"], []).append(e)
        for n, es in by_w.items():
            axes = [e["axis"] for e in es]
            if len(set(axes)) >= 2:
                hit += 1
                assert {e["label"] for e in es} >= {"slide:x", "slide:z"} or len(set(axes)) >= 2
                assert len({(e["axis"], e["words"][0]) for e in es}) == len(es)
    if not hit:
        pytest.skip("no window of this toy agrees on two axes under this placement")


def test_typed_abstentions(wi):
    kinds = set()
    for r in all_answers(wi):
        for a in r.abstentions:
            assert a["axis"] in ("x", "y", "z") and a["label"] == "slide:" + a["axis"] and a["kind"] in Q.ABSTENTION_KINDS
            assert sum(a["kinds"].values()) == a["members"] and set(a["kinds"]) <= set(Q.ABSTENTION_KINDS)
            assert (a["kind"] == Q.MIXED) == (len(a["kinds"]) > 1)
            kinds.update(a["kinds"])
        # an axis is either listed or abstained, once per window read
        for x in r.reads:
            if x.window in set(r.plan.read):
                for ax in ("x", "y", "z"):
                    n_e = sum(1 for e in x.entries if e["axis"] == ax)
                    n_a = sum(1 for a in x.abstentions if a["axis"] == ax)
                    assert (n_e > 0) != (n_a > 0)
    assert {SR.NO_EDGES, SR.POINTS_NOWHERE} <= kinds
    assert kinds & {SR.SECTION_DISAGREEMENT, SR.RATIO_DISAGREEMENT}


def test_not_grounded_is_gated_but_a_skipped_walk_is_not(wi):
    """N-03 on the answer: an agreeing axis whose working sections have no in-space query unit attached is not admitted; under
    two_if_single_edge an axis whose walk was not applicable (section None) is not judged by it."""
    for q in QUESTIONS:
        for ag in SR.AGREEMENTS:
            for e in Q.ask_slide(wi, q, agreement=ag).entries:
                assert e["grounded"] >= 1 or e["ratios"]["section"] is None
    # the gate itself, on a read the unit-level way: every admitted-or-dropped answer is counted under a kind
    r = Q.read_window(wi, wi.by_n[4], dataclasses.replace(Q.intake(wi, "猫は何を食べますか"), qset=frozenset(wi.by_n[4].seated)), agreement="three")
    assert all(sum(x["kinds"].values()) == x["members"] for x in r.abstentions)


def test_verdict_rule():
    plan0 = Q.Plan(0, (), (), (), None, 0, "grammar")
    plan_c = Q.Plan(3, (), (), (1, 2, 3), 0, 3, "grammar")
    plan_r = Q.Plan(3, (), (1,), (2, 3), 1, 2, "grammar")
    ab = lambda *ks: [{"kinds": {k: 1 for k in ks}}]
    assert Q.verdict_of(1, plan_r, []) == Q.ANSWER and Q.verdict_of(2, plan_r, []) == Q.CHOICE
    assert Q.verdict_of(0, plan0, []) == Q.UNKNOWN_NO_WINDOW and Q.verdict_of(0, plan_c, []) == Q.UNKNOWN_NOT_READ
    assert Q.verdict_of(0, plan_r, ab(SR.RATIO_DISAGREEMENT, SR.SECTION_DISAGREEMENT, Q.UNSTABLE)) == Q.UNKNOWN_RATIO_DISAGREEMENT
    assert Q.verdict_of(0, plan_r, ab(SR.SECTION_DISAGREEMENT, Q.UNSTABLE)) == Q.UNKNOWN_SECTION_DISAGREEMENT
    assert Q.verdict_of(0, plan_r, ab(Q.UNSTABLE, SR.NO_EDGES)) == Q.UNKNOWN_UNSTABLE
    assert Q.verdict_of(0, plan_r, ab(SR.NO_EDGES, SR.POINTS_NOWHERE, Q.NOT_GROUNDED)) == Q.UNKNOWN_NO_EVIDENCE
    assert Q.verdict_of(0, plan_r, []) == Q.UNKNOWN_NO_EVIDENCE


def test_unknown_question_is_typed(wi):
    r = Q.ask_slide(wi, "存在しない語は何ですか")
    assert r.verdict == Q.UNKNOWN_NO_WINDOW and r.entries == () and r.windows_read == 0 and r.plan.candidates == 0
    assert r.answer_obj()["answer"] is None and r.answer_obj()["listed"] == 0
    assert "答えなし" in Q.format_text(r)


def test_answer_is_one_entry_exactly(wi):
    r = Q.ask_slide(wi, "日本の首都は何ですか")
    assert r.verdict == Q.ANSWER and len(r.entries) == 1
    a = r.answer_obj()["answer"]
    assert a["path_words"] == r.entries[0]["words"] and a["axis"] == r.entries[0]["axis"] and a["window"] == r.entries[0]["window"]


def test_stable_strict_absent_means_true_false_abstains_or_marks(wi):
    base = Q.ask_slide(wi, "猫は何を食べますか", agreement="two_if_single_edge")
    assert base.entries and all(e["stable_strict"] for e in base.entries)
    n4 = {e["window"]["n"] for e in base.entries}
    # the whole window false
    def flag(value):
        def edit(d):
            if d["window"]["n"] in n4:
                d["stable_strict"] = value
                d.pop("judgement", None)              # (a G3-c3 record also carries per-member flags, which take precedence)
        return edit
    bad = with_docs(wi, flag(False))
    ab = Q.ask_slide(bad, "猫は何を食べますか", agreement="two_if_single_edge")                       # strict="abstain" (default)
    assert ab.entries == () and ab.verdict.startswith("UNKNOWN")           # (typed by the precedence of verdict_of)
    assert any(Q.UNSTABLE in a["kinds"] for a in ab.abstentions)
    mk = Q.ask_slide(bad, "猫は何を食べますか", agreement="two_if_single_edge", strict="mark")
    assert len(mk.entries) == len(base.entries) and all(e["stable_strict"] is False for e in mk.entries)
    assert [(e["window"]["n"], e["axis"], e["words"]) for e in mk.entries] == [(e["window"]["n"], e["axis"], e["words"]) for e in base.entries]
    # per axis: only x false
    px = with_docs(wi, flag({"x": False, "y": True, "z": True}))
    r = Q.ask_slide(px, "猫は何を食べますか", agreement="two_if_single_edge")
    assert {e["axis"] for e in base.entries} >= {"x", "z"} and {e["axis"] for e in r.entries} == {e["axis"] for e in base.entries} - {"x"}
    assert Q.ask_slide(px, "猫は何を食べますか", agreement="two_if_single_edge", strict="mark").entry_keys() != r.entry_keys()


def answered_window(wi):
    """(question, window number) of a window with a class of several members that answers a toy question, or a skip."""
    found = [(q, e["window"]["n"]) for q in QUESTIONS for e in Q.ask_slide(wi, q, agreement="two_if_single_edge").entries
             if e["class_size"] > 1 and e["members_read"] > 1]
    if not found:
        pytest.skip("no window with a class of several members answers a toy question under this placement")
    return found[0]


def doctor_window(n, **fields):
    """An edit for with_docs: set fields of window n's record; `judgement` / `centre_search` are given as they are in the record."""
    def edit(d):
        if d["window"]["n"] == n:
            d.pop("stable_strict", None)
            d.update(fields)
    return edit


def test_only_the_strictly_stable_members_are_read(wi):
    """Owner (G3-c3 decision): read ONLY the class members that are strictly stable; judgement.member_judgement[i].stable_strict is the
    flag; a window with no stable member is an abstention of type UNSTABLE_AXIS_IMPROVABLE."""
    q, n = answered_window(wi)
    w = wi.by_n[n]
    it = Q.intake(wi, q)
    kw = dict(agreement="two_if_single_edge")
    k = w.class_size
    flags = [i % 2 == 0 for i in range(k)]
    half = with_docs(wi, doctor_window(n, judgement={"member_judgement": [{"stable_strict": f} for f in flags]}))
    hw = half.by_n[n]
    sel, skipped = Q.choose_members(hw, "all", "abstain")
    assert sel == [i for i in range(k) if flags[i]] and skipped == k - len(sel)
    r = Q.read_window(half, hw, it, **kw)
    assert r.members_read == len(sel) and r.class_size == k
    for e in r.entries:
        assert e["members_read"] == len(sel) and e["stable_strict"] is True and e["member"] in sel
        assert e["members_not_admitted"].get(Q.UNSTABLE) == skipped
    for a in r.abstentions:
        assert a["kinds"].get(Q.UNSTABLE) == skipped and a["members"] == k and sum(a["kinds"].values()) == k
    # "mark" (a measurement hook) reads them all and flags
    m = Q.read_window(half, hw, it, strict="mark", **kw)
    assert m.members_read == k and all((not e["stable_strict"]) or e["members_agreeing"] <= sum(flags) for e in m.entries)
    # no stable member: every axis is an abstention of that type, nothing else is said
    none = with_docs(wi, doctor_window(n, judgement={"member_judgement": [{"stable_strict": False} for _ in range(k)]}))
    r0 = Q.read_window(none, none.by_n[n], it, **kw)
    assert r0.members_read == 0 and r0.entries == () and r0.trace_checks == 0
    assert [(a["axis"], a["kind"], a["members"]) for a in r0.abstentions] == [(ax, Q.UNSTABLE, k) for ax in ("x", "y", "z")]
    ans = Q.ask_slide(none, q, **kw)
    assert not [e for e in ans.entries if e["window"]["n"] == n]
    assert any(a["window"] == n and a["kind"] == Q.UNSTABLE for a in ans.abstentions)
    only = Q.verdict_of(0, ans.plan, [a for a in ans.abstentions if a["window"] == n])
    assert only == Q.UNKNOWN_UNSTABLE
    # absent fields = one growth, every member strictly stable
    plain = with_docs(wi, lambda d: [d.pop(x, None) for x in ("judgement", "stable_strict", "centre_search", "unstable")])
    pw = plain.by_n[n]
    assert Q.choose_members(pw, "all", "abstain") == (list(range(k)), 0) and pw.centre_side(k - 1) == "this" and pw.member_pad(k - 1) == 0
    assert Q.choose_members(pw, "representative", "abstain") == ([0], 0)


def test_both_growths_are_read_and_listed_apart_when_they_differ(wi):
    """Owner (G3-c3 decision): a record that holds both growths (centre in N, centre in N+1; centre_search.member_x_side) is read on
    BOTH; the same answer from both is one entry, a different answer is another; nothing is picked by order."""
    q, n = answered_window(wi)
    w = wi.by_n[n]
    k = w.class_size
    it = Q.intake(wi, q)
    kw = dict(agreement="two_if_single_edge")
    sides = ["this" if i % 2 == 0 else "next" for i in range(k)]
    two = with_docs(wi, doctor_window(n, centre_search={"member_x_side": sides, "member_L": [int(w.doc["L"])] * k}))
    tw = two.by_n[n]
    assert [tw.centre_side(i) for i in range(k)] == sides
    assert Q.choose_members(tw, "all", "abstain") == (list(range(k)), 0)
    assert Q.choose_members(tw, "representative", "abstain") == ([0, 1], 0)            # one representative PER growth
    one = with_docs(wi, doctor_window(n, centre_search={"member_x_side": ["this"] * k, "member_L": [int(w.doc["L"])] * k}))
    assert Q.choose_members(one.by_n[n], "representative", "abstain") == ([0], 0)
    r = Q.read_window(two, tw, it, **kw)
    base = Q.read_window(wi, w, it, **kw)
    assert [(e["axis"], e["words"]) for e in r.entries] == [(e["axis"], e["words"]) for e in base.entries]       # same set of answers
    keys = [(e["axis"], e["words"][0]) for e in r.entries]
    assert len(keys) == len(set(keys))
    for e in r.entries:
        assert set(e["centre_sentences"]) <= {"this", "next"} and sum(e["centre_sentences"].values()) == e["arrangements"]
    assert any(len(e["centre_sentences"]) == 2 for e in r.entries) or any(e["arrangements"] < k for e in r.entries)
    rep = Q.read_window(two, tw, it, members="representative", **kw)
    assert rep.members_read == 2
    # members of the two growths that disagree give two entries of the same axis (never one picked)
    for e in rep.entries:
        assert e["members_read"] == 2 and e["arrangements"] in (1, 2)
    # a growth that seats different units: the window is a candidate when ANY member holds a question unit, the gate asks it of each member
    diff = with_docs(wi, doctor_window(n, members=[w.doc["members"][0]] + [[None] * len(w.doc["members"][0])] * (w.class_size - 1)))
    dw = diff.by_n[n]
    assert dw.member_seated is not None and dw.member_units(1) == frozenset() and dw.member_units(0) == w.seated
    assert dw.member_units(None) == w.seated and Q.holds(dw, it, member=0) == Q.holds(wi.by_n[n], it, member=0) and Q.holds(dw, it, member=1) == (0, 0)


def test_padded_members_are_read_without_their_padding(wi):
    """G3-c3 pads a member grown at a shorter arm length with empty OUTER seats (centre_search.member_L): the reader skips them, so
    the padded record reads exactly like the unpadded one."""
    from verantyx.line3 import geometry as geo
    q, n = answered_window(wi)
    it = Q.intake(wi, q)

    def pad_one(d):
        if d["window"]["n"] != n:
            return
        L = int(d["L"])
        d["members"] = [list(SP.extend_flat(tuple(m), L, L + 1)) for m in d["members"]]
        d["seats"] = [dict(x, position=x["position"] + 1) if x["arm"] != "centre" else x for x in d["seats"]]
        d["L"] = L + 1
        d["centre_search"] = {"member_x_side": ["this"] * len(d["members"]), "member_L": [L] * len(d["members"])}
    padded = with_docs(wi, pad_one)
    pw, w = padded.by_n[n], wi.by_n[n]
    assert int(pw.doc["L"]) == int(w.doc["L"]) + 1 and all(pw.member_pad(i) == 1 for i in range(w.class_size))
    for i in range(w.class_size):
        a, b = Q.member_cross(w, i), Q.member_cross(pw, i)
        assert a.L == b.L == int(w.doc["L"])
        assert {s: (x.unit, x.sid) for s, x in a.by_seat().items()} == {s: (x.unit, x.sid) for s, x in b.by_seat().items()}
    # the unpadded reading of the padded record is the reading of the original; the padded cross itself would have an empty outer seat
    # on every arm, where the walk stops at once
    raw = SR.window_cross(pw.doc, 0)
    assert raw.L == int(w.doc["L"]) + 1 and all(geo.Seat(a, 0) not in raw.by_seat() for a in geo.AXES)
    for ag in SR.AGREEMENTS:
        x = Q.read_window(wi, w, it, agreement=ag)
        y = Q.read_window(padded, pw, it, agreement=ag)
        strip = lambda es: [{k: v for k, v in e.items() if k not in ("centre_sentences",)} for e in es]
        assert strip(x.entries) == strip(y.entries) and x.abstentions == y.abstentions


def test_members_representative_is_a_subset_with_the_count(wi):
    for q in QUESTIONS:
        allm = Q.ask_slide(wi, q, agreement="two_if_single_edge")
        rep = Q.ask_slide(wi, q, agreement="two_if_single_edge", members="representative")
        ka = {(e["window"]["n"], e["axis"], e["words"][0]) for e in allm.entries}
        kr = {(e["window"]["n"], e["axis"], e["words"][0]) for e in rep.entries}
        assert kr <= ka
        for e in rep.entries:
            w = wi.by_n[e["window"]["n"]]
            growths = {w.centre_side(i) for i in range(w.class_size) if w.readable(i)}       # one representative per growth (L-658)
            assert e["members_read"] == len(growths) and e["arrangements"] <= len(growths) and e["class_size"] == w.class_size
        for a in rep.abstentions:                     # review: `members` = the members accounted (read + not read as unstable), not the class
            assert sum(a["kinds"].values()) == a["members"] <= wi.by_n[a["window"]].class_size
    assert any(w.class_size > 1 for w in wi.windows)


def test_one_class_with_several_members_is_read_member_by_member(wi):
    w = next(w for w in wi.windows if w.class_size > 1)
    it = Q.intake(wi, "魚は何ですか")
    r = Q.read_window(wi, w, dataclasses.replace(it, qset=frozenset(w.seated)), agreement="two_if_single_edge")
    assert r.members_read == w.class_size
    for e in r.entries:
        assert e["members_read"] == w.class_size and e["members_agreeing"] <= w.class_size


# ---------------------------------------------------------------------------------------------------------------------------------
# Part 6: defaults, bytes, no float, the command line
# ---------------------------------------------------------------------------------------------------------------------------------
def test_flat_is_the_default_and_nothing_new_leaks_into_it(data_file):
    idx = A.Index.from_jsonl(data_file, None, "low", ("RUN", "WORD"))
    q = "日本の首都は何ですか"
    base = A.ask(idx, q, effort="full")
    assert base.to_bytes() == A.ask(idx, q, effort="full", structure="flat").to_bytes()
    obj = base.to_json_obj()
    assert not ({"structure", "windows_read", "partial", "grammar_form"} & set(obj["answer"]) | set(obj["thought"]) & {"structure", "grammar_form"})
    assert idx.cache_dir is None
    with pytest.raises(ValueError, match="structure"):
        A.ask(idx, q, effort="full", structure="cube")
    with pytest.raises(ValueError, match="RUN tier only"):
        A.ask(idx, q, tiers=["RUN", "WORD"], effort="full", structure="slide")
    with pytest.raises(ValueError, match="RUN tier only"):
        A.ask(idx, q, effort="full", structure="slide", granularity="entry")


def test_ask_structure_slide_through_an_index(tmp_path, data_file, space, rows):
    idx = A.Index.from_jsonl(data_file, str(tmp_path), "low", ("RUN",))
    Q.WindowIndex.from_space(idx.space, str(tmp_path), level="low")          # what `line3 build --structure slide` writes
    r = A.ask(idx, "猫は何を食べますか", effort="full", structure="slide", agreement="two_if_single_edge")
    assert isinstance(r, Q.SlideAnswer) and r.verdict == Q.CHOICE and r.answer_obj()["structure"] == "slide"
    assert idx._slide_windows                                                 # kept on the index: built once
    assert r.to_bytes() == A.ask(idx, "猫は何を食べますか", effort="full", structure="slide", agreement="two_if_single_edge").to_bytes()
    assert len([f for f in os.listdir(str(tmp_path)) if f.startswith("slidewin_")]) == 1          # the same file; nothing re-placed


SCRIPT = r"""
import hashlib, sys
sys.path.insert(0, %(root)r)
from verantyx.line3 import slide_query as Q, space as sp
TOY = %(toy)r
seen = {}; rows = []
for t, s in TOY:
    i = seen.get(t, 0); seen[t] = i + 1
    rows.append({"title": t, "sent": s, "source": "%%s#%%d" %% (t, i)})
wi = Q.WindowIndex.from_space(sp.build_space(rows), None, rows=rows, level="low")
h = hashlib.sha256()
for q in %(qs)r:
    for ag in ("three", "two_if_single_edge"):
        h.update(Q.ask_slide(wi, q, agreement=ag).to_bytes())
        h.update(Q.ask_slide(wi, q, agreement=ag, effort="fast", shuffle=7).to_bytes())
print(h.hexdigest())
"""


def test_bytes_identical_under_three_hash_seeds():
    code = SCRIPT % {"root": ROOT, "toy": TOY, "qs": QUESTIONS}
    outs = []
    for seed in ("0", "1", "12345"):
        env = dict(os.environ, PYTHONHASHSEED=seed, PYTHONDONTWRITEBYTECODE="1")
        r = subprocess.run([PY, "-c", code], capture_output=True, text=True, env=env, cwd=ROOT, timeout=600)
        assert r.returncode == 0, r.stderr
        outs.append(r.stdout.strip())
    assert len(outs[0]) == 64 and outs[0] == outs[1] == outs[2]


def test_bytes_are_canonical_and_carry_the_shas(wi):
    r = Q.ask_slide(wi, "猫は何を食べますか", agreement="two_if_single_edge")
    b = r.to_bytes()
    assert b == SL.canonical(json.loads(b)) == SL.canonical({"answer": r.answer_obj(), "thought": r.thought_obj()})
    th = r.thought_obj()
    assert th["spec"]["slide_spec_sha256"] == wi.slide.spec.sha256() and th["spec"]["place_spec_sha256"] == wi.spec.sha256()
    assert th["spec"]["corpus_sha256"] == wi.space.sha256() and th["config"]["agreement"] == "two_if_single_edge"
    assert th["grammar"]["text"] and th["plan"]["blocks"] and th["windows"]
    assert b"\"ms\"" not in b                                                  # the wall time is not part of the bytes
    assert Q.ask_slide(wi, "猫は何を食べますか", agreement="two_if_single_edge").to_bytes() == b


def test_no_float_in_the_module():
    tree = ast.parse(open(Q.__file__, encoding="utf-8").read())
    for n in ast.walk(tree):
        if isinstance(n, ast.Constant):
            assert not isinstance(n.value, float)
        if isinstance(n, ast.Name):
            assert n.id != "float"
        if isinstance(n, ast.BinOp):
            assert not isinstance(n.op, ast.Div)
    with pytest.raises(TypeError):
        SL.canonical({"x": 1.5})


def test_import_does_not_touch_the_flat_machinery():
    code = ("import sys; sys.path.insert(0, %r); import verantyx.line3.slide_query; "
            "print(sorted(m for m in sys.modules if m.startswith('verantyx.line3.') and m.split('.')[-1] in ('matryoshka', 'carry', 'carry_query', 'readout')))" % ROOT)
    r = subprocess.run([PY, "-c", code], capture_output=True, text=True, cwd=ROOT, env=dict(os.environ, PYTHONHASHSEED="0"), timeout=300)
    assert r.returncode == 0, r.stderr
    assert r.stdout.strip() == "['verantyx.line3.readout']"                  # ask.py (flat) imports readout; no layer (matryoshka, carry) is loaded


def cli(args, seed="0"):
    env = dict(os.environ, PYTHONHASHSEED=seed, PYTHONDONTWRITEBYTECODE="1", PYTHONPATH=ROOT)
    for k in [k for k in env if k.startswith("VERA_")]:
        del env[k]
    return subprocess.run([PY, "-m", "verantyx.cli", "line3"] + args, capture_output=True, text=True, env=env, cwd=ROOT, timeout=900,
                          stdin=subprocess.DEVNULL)


def test_cli_structure_flag(tmp_path, data_file):
    cache = str(tmp_path / "cache")
    b = cli(["build", "--structure", "slide", "--data", data_file, "--cache", cache, "--level", "low"])
    assert b.returncode == 0, b.stderr
    info = json.loads(b.stdout)
    assert info["windows"] == 9 and len(os.listdir(cache)) == 1 and os.listdir(cache)[0].startswith("slidewin_")
    base = ["ask", "--data", data_file, "--cache", cache, "--level", "low", "--question", "猫は何を食べますか", "--format", "json", "--effort", "full"]
    outs = [cli(base + ["--structure", "slide", "--agreement", "two_if_single_edge", "--show-thought"], s) for s in ("0", "1", "12345")]
    for r in outs:
        assert r.returncode == 0, r.stderr
    assert outs[0].stdout == outs[1].stdout == outs[2].stdout
    obj = json.loads(outs[0].stdout)
    a = obj["answer"]
    assert set(obj) == {"answer", "thought"} and a["structure"] == "slide" and a["verdict"] == "CHOICE"
    assert {"windows_read", "partial", "grammar_form", "entries", "read"} <= set(a) and a["grammar_form"]["form"] == "slot"
    assert obj["thought"]["spec"]["place_spec_sha256"] == info["place_spec_sha256"]            # the cache the build wrote is the one read
    short = cli(base + ["--structure", "slide", "--agreement", "two_if_single_edge"])
    assert set(json.loads(short.stdout)) == {"answer"} and json.loads(short.stdout)["answer"] == a
    txt = cli(["ask", "--data", data_file, "--cache", cache, "--level", "low", "--question", "猫は何を食べますか", "--effort", "fast",
               "--structure", "slide", "--agreement", "two_if_single_edge"])
    assert txt.returncode == 0, txt.stderr
    assert "slide:" in txt.stdout and "問いの形: slot" in txt.stdout
    rep = cli(["ask", "--data", data_file, "--cache", cache, "--level", "low", "--question", "猫は何を食べますか", "--effort", "fast",
               "--structure", "slide", "--slide-members", "representative"])
    assert rep.returncode == 0, rep.stderr and "問いの形: slot" in rep.stdout
    # the refused combinations
    for extra in (["--choose", "0"], ["--granularity", "entry"]):
        r = cli(base + ["--structure", "slide"] + extra)
        assert r.returncode == 2 and "not built" in r.stderr
    # --structure flat is the default: the same bytes as without the flag, and no new key in the answer
    flat = cli(base + ["--layers", "off"])
    flat2 = cli(base + ["--layers", "off", "--structure", "flat"])
    assert flat.returncode == 0 and flat.stdout == flat2.stdout
    fo = json.loads(flat.stdout)["answer"]
    assert "structure" not in fo and "grammar_form" not in fo and "windows_read" not in fo
    bad = cli(base + ["--structure", "cube"])
    assert bad.returncode != 0
