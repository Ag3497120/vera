"""C5 acceptance (docs/LINE3_CARRY_DESIGN.md 5, 6 P-4, 9 C5): question answering over the carry tower.

Two towers: the design 4.5 / 5.5 example (collapse points fixed by the test-only injection, L-376) and a natural tower
of the first 40 S300 sentences (RUN, low).  The reference descents below are written in the test, independently of
`ask` (they only use `read_unit`, `rq`, the tower's own packs and the unit's seated elements)."""
import dataclasses
import hashlib
import json
import os
import random
import subprocess
import sys

import pytest

from verantyx.line3 import carry as C
from verantyx.line3 import carry_query as CQ
from verantyx.line3 import cycle as cy
from verantyx.line3 import placement as pl
from verantyx.line3.carry import CarryTower, Ledger, Occ, stream_header
from verantyx.line3.space import build_space

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
MID = pl.budget_level("mid")
T7B_ENTRY_KEYS = {"tier", "words", "arrangements", "centres", "stability", "source_sids", "tier_is_most_stable"}  # ask.Combined.answer_obj

S45 = {0: "富士山 静岡県 山梨県 山", 1: "静岡県 県庁 静岡市", 2: "山梨県 県庁 甲府市",
       3: "富士山 噴火 1707年", 4: "甲府市 武田 城", 5: "武田 信玄 甲斐"}
S45 = {k: v.split() for k, v in S45.items()}


def inj45(level, unit, item):
    if (level, unit) == (0, "U0:0") and (item.sid, item.pos) == (2, 2):
        return "injected"
    if (level, unit) == (0, "U0:1") and (item.sid, item.pos) == (4, 2):
        return "injected"
    return None


def toy_tower():
    led = Ledger(stream_header("T", list(S45), MID, copy=C.TOWER_COPY))
    tw = CarryTower("T", MID, led, inject=inj45)
    for s, us in S45.items():
        tw.feed_sentence(s, [Occ(s, i, u) for i, u in enumerate(us)])
    return tw


_CACHE = {}


def head_tower(order="file"):
    """The first 40 S300 sentences, RUN, low: 56 blacks, 9 + 1 upper units; local sids differ from global ones when
    the stream order is reversed."""
    if order not in _CACHE:
        rows = [json.loads(l) for l in open(os.path.join(ROOT, "experiments/line3/data/S300.jsonl"), encoding="utf-8")][:40]
        ts = build_space(rows).tiers["RUN"]
        sids = list(range(40)) if order == "file" else list(range(39, -1, -1))
        tw = C.build_tower("RUN", ts, sids, pl.budget_level("low"), order_kind=order)
        _CACHE[order] = (tw, ts)
    return _CACHE[order]


def asked(tag, tw, ts, q, **kw):
    k = (tag, q, tuple(sorted(kw.items())))
    if k not in _CACHE:
        _CACHE[k] = CQ.ask(tw, "", units=q, tier_space=ts, **kw)
    return _CACHE[k]


# ---------------------------------------------------------------- design 5.5
def test_design_5_5_example():
    tw = toy_tower()
    a = CQ.ask(tw, "甲府市はどこにありますか", units=("甲府市",))
    # 5.1: the entrance is the open units; rq counts the scope sentences that hold a question unit (hand count)
    assert a.entrance == (("U1:0", 1, 1), ("U0:2", 0, 1))                  # U1:0: s2 only; U0:2: s4 only
    idx = {b.unit: b for b, _ in tw.units()}
    assert {u: CQ.rq(b, ["甲府市"]) for u, b in idx.items()} == {"U0:0": 0, "U0:1": 1, "U0:2": 1, "U1:0": 1}
    # 5.2: U0:0 (s0, s1: no 甲府市) is skipped exactly, and the skip is recorded with the link that led to it
    assert [(u, lv) for u, lv, _ in a.skipped] == [("U0:0", 0)]
    assert a.skipped[0][2] == (("U0:1", "P1:0", True),)                     # P1:0 is inherited in U0:1: a lateral link
    # three units are read (design: "読んだ単位 3"); U0:0 is not
    assert sorted(r.unit for r in a.reads) == ["U0:1", "U0:2", "U1:0"]
    assert a.verdict == CQ.CHOICE and len(a.entries) == 2 and not a.partial
    e1 = [e for e in a.entries if "山梨県" in e.words]
    assert len(e1) == 1                                                       # the gold of the example is in a candidate
    e1 = e1[0]
    assert set(e1.words) == {"1707年", "噴火", "富士山", "山梨県", "甲府市", "県庁"} and e1.source_sids == (2, 3)
    assert [p for p, _, _ in e1.inherited] == ["P1:0"] and e1.inherited[0][1] == "U0:0"   # named, never expanded
    e2 = [e for e in a.entries if "武田" in e.words][0]
    assert e2.source_sids == (4, 5) and [p for p, _, _ in e2.inherited] == ["P1:1"]
    # chains: here U1:0 (two packs, symmetric: the tie abstains) adopts no state, so U0:1 is reached through the
    # inherited P1:1 of the newest black (lateral); with fallback="index" the coarse link U1:0 -> P1:1 -> U0:1 exists too
    o1 = e1.origins[0]
    assert o1.unit == "U0:1" and o1.entrances == ("U0:2",) and o1.links == (("U0:2", "P1:1", "U0:1", True),)
    b = CQ.ask(tw, "", units=("甲府市",), fallback="index")
    o1b = [o for e in b.entries for o in e.origins if o.unit == "U0:1"][0]
    assert o1b.entrances == ("U0:2", "U1:0")
    assert o1b.links == (("U0:2", "P1:1", "U0:1", True), ("U1:0", "P1:1", "U0:1", False))
    o2 = [o for e in a.entries for o in e.origins if o.unit == "U0:2"][0]
    assert o2.entrances == ("U0:2",) and o2.links == ()                        # an entrance unit read directly
    assert CQ.trace(tw, a).ok and CQ.trace(tw, b).ok


def test_read_tier_of_an_upper_unit_gives_the_question_unit_postings_from_the_scope():
    tw = toy_tower()
    b = [b for b, _ in tw.units() if b.unit == "U1:0"][0]
    rt = CQ.read_tier("T", b, ["甲府市", "不在"])
    assert rt.sids == (0, 1, 2, 3) and rt.N == 4
    assert rt.postings["甲府市"] == (2,) and "不在" not in rt.postings            # not an element, not in the scope
    assert rt.postings["P1:0"] == (0, 1, 2, 3) and rt.postings["P1:1"] == (0, 1, 2, 3)
    assert all(len(s) <= 3 for s in rt.sentence_units)


# ---------------------------------------------------------------- the exact skip (L-313)
def _closure(tw, q, skip, seed=None):
    """Reference descent: read every reachable unit (rq = 0 ones too unless `skip`), in an arbitrary order."""
    idx = {b.unit: (b, st) for b, st in tw.units()}
    stack = [u for u, (_, st) in idx.items() if st == C.STATUS_OPEN]
    rng = random.Random(seed)
    reads = {}
    while stack:
        if seed is not None:
            rng.shuffle(stack)
        u = stack.pop()
        if u in reads:
            continue
        b = idx[u][0]
        if skip and CQ.rq(b, q) == 0:
            continue
        r = CQ.read_unit(tw, u, q)
        reads[u] = r
        els = {e.id: e for e in b.space.elements}
        for x in r.path_elements():
            if els[x].kind == "pack":
                stack.append(tw.packs[x].unit)
    return reads, idx


def _entry_keys(entries):
    return sorted((e.words, tuple(p for p, _, _ in e.inherited), e.centres, e.stability, e.arrangements, e.source_sids)
                  for e in entries)


@pytest.mark.parametrize("q", [("村",), ("村", "日本"), ("州",), ("日本",), ("該当なし",)])
def test_exact_skip_gives_the_verdict_of_reading_over_all_units(q):
    tw, ts = head_tower()
    # (1) every single unit with rq = 0: actually reading it gives no state, no answer, no entry
    idx = {b.unit: b for b, _ in tw.units()}
    for u, b in sorted(idx.items()):
        if CQ.rq(b, q) == 0:
            r = CQ.read_unit(tw, u, q)
            assert r.states == 0 and r.answer is None and r.verdict not in (cy.ANSWER, cy.CHOICE), (u, r.verdict)
    # (2) the whole descent with and without the skip reads the same units that matter and gives the same entries
    ref_all, ridx = _closure(tw, q, skip=False)
    ref_skip, _ = _closure(tw, q, skip=True)
    a = asked("head", tw, ts, q, effort="full")
    ans_all = {u for u, r in ref_all.items() if r.answer is not None}
    assert ans_all == {u for u, r in ref_skip.items() if r.answer is not None} == {r.unit for r in a.reads if r.answer is not None}
    order = [ref_all[u] for u in sorted(ref_all, key=CQ._unit_key)]
    e_all = CQ._entries(tw, {u: ridx[u] for u in ridx}, order, {}, set())
    assert _entry_keys(e_all) == _entry_keys(a.entries)
    ref_verdict = cy.ANSWER if len(e_all) == 1 else (cy.CHOICE if e_all else None)
    if ref_verdict:
        assert a.verdict == ref_verdict
    else:
        assert a.verdict in (CQ.UNKNOWN_NO_STATE, CQ.UNKNOWN_NO_PATH, CQ.UNKNOWN_NO_EVIDENCE)
    # (3) what the skip saved: units that were reached or are entrance units with rq = 0 are all recorded
    assert {u for u, _, _ in a.skipped} <= {u for u, b in idx.items() if CQ.rq(b, q) == 0}


def test_no_question_unit_anywhere_is_no_evidence_without_a_read():
    tw, ts = head_tower()
    a = asked("head", tw, ts, ("該当なし",), effort="full")
    assert a.verdict == CQ.UNKNOWN_NO_EVIDENCE and a.reads == () and not a.partial and a.index_positive == 0
    assert a.answer_obj()["entries"] == [] and a.answer_obj()["answer"] is None


# ---------------------------------------------------------------- reading order
@pytest.mark.parametrize("seed", [1, 2, 3])
def test_result_does_not_depend_on_the_reading_order(seed):
    tw, ts = head_tower()
    q = ("村", "日本")
    ref, ridx = _closure(tw, q, skip=True, seed=seed)                          # a shuffled stack order
    a = asked("head", tw, ts, q, effort="full")
    assert set(ref) == {r.unit for r in a.reads}
    order = [ref[u] for u in sorted(ref, key=CQ._unit_key)]
    assert _entry_keys(CQ._entries(tw, ridx, order, {}, set())) == _entry_keys(a.entries)


# ---------------------------------------------------------------- presets, groups, partial counts
def test_presets_are_the_t7b_ones_and_bound_the_units_read():
    from verantyx.line3 import ask as A
    assert {k: v[0] for k, v in A.EFFORTS.items()} == {"fast": 4, "standard": 10, "full": None}
    tw, ts = head_tower()
    q = ("村", "日本")
    full = asked("head", tw, ts, q, effort="full")
    for eff, cap in (("fast", 4), ("standard", 10)):
        a = asked("head", tw, ts, q, effort=eff)
        assert len(a.reads) <= cap and a.node_budget == cap and a.effort == eff
        assert a.read_obj()["rebuild_levels"] == []                           # never rebuilds (L-315)
        # the cap stops the SAME descent: its reads are a prefix of the full read order
        assert [r.unit for r in a.reads] == [r.unit for r in full.reads][:len(a.reads)]
    assert [r.unit for r in full.reads][:3] == ["U2:0", "U0:55", "U1:0"]


def test_equivalent_groups_are_never_split_and_partial_counts_are_reported():
    tw, ts = head_tower()
    q = ("村", "日本")
    full = asked("head", tw, ts, q, effort="full")
    assert not full.partial and full.read_obj()["per_tier"]["RUN"]["left_unread"] == 0
    # nodes = 3 reads U2:0, U0:55, U1:0 (rq 2); the next group {U1:5, U1:7} (level 1, rq 1) has 2 units: it does not fit
    a = asked("head", tw, ts, q, nodes=3)
    assert [r.unit for r in a.reads] == ["U2:0", "U0:55", "U1:0"]
    assert a.partial and [u for u, _, _ in a.queue_left] == ["U1:5", "U1:7"] and a.tied_group_not_split == 2
    ro_ = a.read_obj()
    assert ro_["partial"] and ro_["per_tier"]["RUN"] == {"crosses_read": 3, "left_unread": 2, "would_read_in_full": a.index_positive}
    assert a.index_positive == sum(1 for b, _ in tw.units() if CQ.rq(b, q) > 0) == 15
    # nodes = 4 would split that group: it does not (still 3 read), nodes = 5 reads it whole
    assert [r.unit for r in asked("head", tw, ts, q, nodes=4).reads] == ["U2:0", "U0:55", "U1:0"]
    assert asked("head", tw, ts, q, nodes=4).tied_group_not_split == 2
    five = asked("head", tw, ts, q, nodes=5)
    assert {r.unit for r in five.reads} >= {"U1:5", "U1:7"} and len(five.reads) == 5
    # a budget smaller than the first group reads nothing and says so (T7b open point 1)
    z = asked("head", tw, ts, q, nodes=0)
    assert z.reads == () and z.partial and z.verdict == CQ.UNKNOWN_NO_STATE and z.tied_group_not_split == 1
    # a budget that covers everything is not partial and reads exactly like the whole read
    big = asked("head", tw, ts, q, nodes=len(full.reads))
    assert not big.partial and big.entries == full.entries and [r.unit for r in big.reads] == [r.unit for r in full.reads]


def test_fallback_index_reads_at_least_what_the_selected_path_reads():
    tw, ts = head_tower()
    for q in (("村",), ("日本",)):
        d = asked("head", tw, ts, q, effort="full")
        f = asked("head", tw, ts, q, effort="full", fallback="index")
        assert {r.unit for r in d.reads} <= {r.unit for r in f.reads}
        assert f.fallback == "index" and d.fallback is None
    # 日本: the top unit adopts no state, so the default descent stops there; the index descent goes on
    assert asked("head", tw, ts, ("日本",), effort="full").verdict == CQ.UNKNOWN_NO_STATE
    assert asked("head", tw, ts, ("日本",), effort="full", fallback="index").verdict == cy.CHOICE
    with pytest.raises(ValueError):
        CQ.ask(tw, "", units=("村",), fallback="x")


# ---------------------------------------------------------------- the entry shape and P-4
def test_entry_shape_is_a_t7b_entry_plus_a_chain():
    tw, ts = head_tower()
    a = asked("head", tw, ts, ("村",), effort="full")
    o = a.answer_obj()
    assert o["verdict"] == cy.CHOICE and o["listed"] == 2 == len(o["entries"])
    for k in ("verdict", "view", "tiers", "listed", "per_tier_listed", "read", "answer", "entries"):
        assert k in o
    for k in ("effort", "node_budget", "rebuild_levels", "partial", "per_tier", "rebuild_skipped"):
        assert k in o["read"]
    for e in o["entries"]:
        assert T7B_ENTRY_KEYS <= set(e) and "chain" in e and "inherited" in e
        assert e["tier"] == "RUN" and all(isinstance(w, str) for w in e["words"])
        assert not any(w in tw.packs for w in e["words"])                      # a pack is never expanded into the words
        for c in e["chain"]:
            assert c["entrances"] and set(c["entrances"]) <= {x for x, _, _ in a.entrance}
            assert all(set(l) == {"from", "pack", "to", "lateral"} for l in c["links"])
            assert c["lateral"] == any(l["lateral"] for l in c["links"])
    assert any(e["inherited"] for e in o["entries"])
    json.dumps(o)                                                              # plain JSON, no float / Fraction
    assert "ms" not in json.dumps(a.to_json_obj())
    # the user's choice: the T7b record shape plus the chain
    rec = a.memory_record(0)
    assert rec["kind"] == "memory_answer" and rec["source"] == "user_choice" and rec["base_changed"] is False
    assert rec["offered"] == 2 and rec["choice_index"] == 0 and rec["chain"] == o["entries"][0]["chain"]
    with pytest.raises(ValueError):
        a.memory_record()                                                      # a list is never auto-adopted
    with pytest.raises(IndexError):
        a.memory_record(2)


@pytest.mark.parametrize("order", ["file", "reverse"])
def test_every_answer_word_traces_to_global_source_sentences(order):
    tw, ts = head_tower(order)
    for q in ((("村",), ("村", "日本")) if order == "file" else (("漫画家",), ("旧約聖書",))):
        a = asked("head" + order, tw, ts, q, effort="full")
        t = CQ.trace(tw, a, ts)
        assert a.entries and t.ok and t.words_checked == t.words_traced > 0 and t.local_ok == t.local_checked > 0, t.failures
        for e in a.entries:
            for o in e.origins:
                b = [b for b, _ in tw.units() if b.unit == o.unit][0]
                assert set(o.source_sids) <= set(b.space.sids)                 # condition 2: only the black's new sentences
                for w, sids in o.word_sources:
                    for s in sids:
                        assert w in ts.sentence_units[s] or w in tw.packs        # the GLOBAL sentence holds the word
    if order == "reverse":
        b = [b for b, _ in tw.units() if b.level == 0][0]
        assert b.space.sids != tuple(range(len(b.space.sids)))                  # local index != global sid here


def test_trace_detects_tampering():
    tw, ts = head_tower()
    a = asked("head", tw, ts, ("村",), effort="full")
    assert CQ.trace(tw, a, ts).ok
    e = a.entries[0]
    o = e.origins[0]
    other = [s for b, _ in tw.units() for s in b.space.sids if s not in {x for b2, _ in tw.units() if b2.unit == o.unit for x in b2.space.sids}][0]

    def bad(entry):
        ents = (entry,) + a.entries[1:]
        return CQ.trace(tw, dataclasses.replace(a, entries=ents), ts)

    w0 = o.word_sources[0][0]
    assert not bad(dataclasses.replace(e, origins=(dataclasses.replace(o, word_sources=((w0, (other,)),) + o.word_sources[1:]),) + e.origins[1:])).ok
    assert not bad(dataclasses.replace(e, origins=(dataclasses.replace(o, source_sids=o.source_sids + (other,)),) + e.origins[1:])).ok
    assert not bad(dataclasses.replace(e, words=e.words + ("存在しない語",))).ok
    assert not bad(dataclasses.replace(e, origins=(dataclasses.replace(o, word_sources=o.word_sources + (("存在しない語", (o.source_sids[0],)),)),) + e.origins[1:])).ok
    sub = [(i, x) for i, x in enumerate(a.entries) for oo in x.origins if oo.links][0]
    ei, ex = sub
    oo = [oo for oo in ex.origins if oo.links][0]
    up, k, dn, lat = oo.links[0]

    def with_links(links, ents=None):
        o2 = dataclasses.replace(oo, links=links, entrances=oo.entrances if ents is None else ents)
        x2 = dataclasses.replace(ex, origins=tuple(o2 if q is oo else q for q in ex.origins))
        return CQ.trace(tw, dataclasses.replace(a, entries=tuple(x2 if j == ei else y for j, y in enumerate(a.entries))), ts)

    assert with_links(oo.links).ok
    assert not with_links(((up, k, dn, not lat),) + oo.links[1:]).ok                                                      # wrong lateral mark
    assert not with_links(((up, "P9:9", dn, lat),) + oo.links[1:]).ok                                                    # not a pack of the tower
    assert not with_links(oo.links, ()).ok                                                                                # starts nowhere
    e2 = [x for x in a.entries if x.inherited][0]
    bad_inh = (e2.inherited[0][0], "U9:9", e2.inherited[0][2])
    ents = tuple(dataclasses.replace(x, inherited=(bad_inh,) + x.inherited[1:]) if x is e2 else x for x in a.entries)
    assert not CQ.trace(tw, dataclasses.replace(a, entries=ents), ts).ok


# ---------------------------------------------------------------- question units, determinism
def test_question_units_use_the_tier_cut_and_the_v2_filter():
    tw, ts = head_tower()
    assert CQ.question_units("RUN", "村とは何ですか") == ("村",)
    assert CQ.question_units("RUN", "ignored", units=("村", "村", "日本")) == ("村", "日本")
    a = CQ.ask(tw, "村とは何ですか", effort="fast")
    assert a.query == ("村",)


_SCRIPT = r"""
import hashlib, json, sys
sys.path.insert(0, %(root)r); sys.path.insert(0, %(tests)r)
import test_carry_query as T
from verantyx.line3 import carry_query as CQ
out = []
tw = T.toy_tower()
for kw in ({}, {"fallback": "index"}, {"nodes": 2}):
    out.append(hashlib.sha256(CQ.ask(tw, "", units=("甲府市",), **kw).to_bytes()).hexdigest())
tw, ts = T.head_tower()
a = CQ.ask(tw, "", units=("村",), effort="fast", tier_space=ts)
out.append(hashlib.sha256(a.to_bytes()).hexdigest())
print(json.dumps(out))
"""


def test_bytes_are_identical_across_hash_seeds():
    runs = []
    for seed in ("0", "1", "12345"):
        env = dict(os.environ, PYTHONHASHSEED=seed, PYTHONPATH=ROOT)
        p = subprocess.run([sys.executable, "-c", _SCRIPT % {"root": ROOT, "tests": os.path.join(ROOT, "tests", "line3")}],
                           capture_output=True, text=True, env=env, cwd=ROOT, timeout=600)
        assert p.returncode == 0, p.stderr[-2000:]
        runs.append(p.stdout.strip().splitlines()[-1])
    assert runs[0] == runs[1] == runs[2]
    assert len(json.loads(runs[0])) == 4


def test_no_float_and_no_wall_time_in_the_bytes():
    tw = toy_tower()
    a = CQ.ask(tw, "", units=("甲府市",))
    obj = json.loads(a.to_bytes())

    def walk(x):
        if isinstance(x, float):
            raise AssertionError("float in the output")
        if isinstance(x, dict):
            for v in x.values():
                walk(v)
        if isinstance(x, list):
            for v in x:
                walk(v)
    walk(obj)
    assert CQ.ask(tw, "", units=("甲府市",)).to_bytes() == a.to_bytes()


def test_chain_marks_stay_polynomial_on_a_ladder_of_parents():
    """L-423: a ladder of 40 rungs with two parents each has 2**40 ways down; the closure has 80 links."""
    parents = {}
    for i in range(1, 41):
        parents["U0:%d" % i] = {("U0:%d" % (i - 1), "P1:%da" % i, False), ("U0:%d" % (i - 1), "P1:%db" % i, True)}
    ent, links = CQ._links(parents, {"U0:0"}, "U0:40")
    assert ent == ("U0:0",) and len(links) == 80 == len(set(links))
