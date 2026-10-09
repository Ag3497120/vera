"""G3-f tests (L-700..): the sliding-window placements read as FLAT crosses (verantyx/line3/slide_flat.py).

Part 1 (what the reading is): a window read flat gives the same entries as the cycle of T5 + the read-out of T6 reading the same cross built as a
plain placement (a hand cross without a shared unit through cycle._ask_tier_once on a real placement.Placement; the real toy windows, with shared units,
through the same call); the starts (strictly stable members only, pad cut, canonical legs, one start for members that read alike); the local space is the
corpus tier (the slide's corpus-scope x count IS n_pair, before_x IS p_pair).
Part 2 (two seats of a shared unit, L-703): "both" keeps the two seats as the same string on two cells, "n_only" one seat; both read, both trace.
Part 3 (labels): the per-axis answers are attached and decide nothing (switching them off or replacing them changes nothing else).
Part 4 (entries, abstentions, verdict, cap): T7b shape + window / centre_sentence / stable_strict / axis_labels; typed abstentions; the verdict rule;
V1 and the cap (windows) are slide_query's.
Part 5 (bytes): PYTHONHASHSEED 0 / 1 / 12345 give the same bytes; no floating-point number; the trace of every word and a trace that bites.
"""
import ast
import copy
import dataclasses
import json
import os
import subprocess
import sys

import pytest

from verantyx.line3 import ask as A
from verantyx.line3 import cycle as cy
from verantyx.line3 import placement as pl
from verantyx.line3 import readout as ro
from verantyx.line3 import slide as SL
from verantyx.line3 import slide_flat as F
from verantyx.line3 import slide_place as SP
from verantyx.line3 import slide_query as Q
from verantyx.line3 import slide_ratios as SR
from verantyx.line3 import space as sp
from verantyx.line3 import trace_check as TC

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
BUDGET = cy.QueryBudget(512, 64)
# G3-i (L-770, L-771): the defaults are z_deep "order" / seat_empty_axis "deny" now; these tests were written (G3-f) for the window index of z_deep "slide" with
# seat_empty_axis "allow", which is what the fixtures below pin; the new defaults are checked in the last test
PRE_G3I = {"z_deep": "slide", "place_kw": {"seat_empty_axis": "allow"}}


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
    return Q.WindowIndex.from_space(space, None, rows=rows, level=LEVEL, **PRE_G3I)


def edited(wi, n, edit):
    """A copy of the window index whose record of window n was edited by `edit(doc)` (the records are plain JSON)."""
    docs = [copy.deepcopy(w.doc) for w in wi.windows]
    edit(docs[[w.n for w in wi.windows].index(n)])
    return Q.WindowIndex(wi.space, wi.slide, wi.spec, docs)


def hand_members(flats, x_sides=None, stable=None, lengths=None):
    """An edit that replaces the members of a record by hand flats (seat tokens), with the per-member bookkeeping slide_query reads."""
    def edit(d):
        L = d["L"]
        k = len(flats)
        d["members"] = [list(f) for f in flats]
        d["class_size"] = k
        j = d["judgement"]
        j["member_judgement"] = [{"improving_moves_left": {"x": 0, "y": 0, "z": 0}, "stable_strict": True if stable is None else stable[i],
                                  "x_side": "this" if x_sides is None else x_sides[i]} for i in range(k)]
        d["centre_search"]["member_x_side"] = list(x_sides or ["this"] * k)
        d["centre_search"]["member_L"] = list(lengths or [L] * k)
        d["stable_strict"] = True
        d["judgement"]["stable_strict"] = True
    return edit


def cycle_side(wi, w, it, flats_by_L, budget=BUDGET, tsp=None, facts=None):
    """The T5 + T6 side, written out independently of slide_flat: a real Placement per arm length, cycle._ask_tier_once with a plan naming them,
    readout.read_out_result."""
    tsp = tsp if tsp is not None else wi.space.tiers[wi.tier]
    facts = facts if facts is not None else cy.TierFacts(tsp)
    pls = {}
    for lm in sorted(flats_by_L):
        fl = tuple(sorted(flats_by_L[lm], key=lambda f: tuple("" if c is None else "x" + c for c in f)))
        seed = "W%d/L%d" % (w.n, lm)
        pls[seed] = pl.Placement(seed=seed, cross=pl.to_cross(fl[0], lm), members=fl, L=lm, centres=tuple(sorted({f[0] for f in fl})),
                                 size=len({c for f in fl for c in f if c}), capacity=1, score=(0, 0), stop="exhausted", broke_on=None, steps=(),
                                 candidates=0, budget=pl.budget_level(LEVEL))
    names = tuple(sorted(pls))
    plan = cy.ReadPlan((("window", names),), names, (), len(names), None, False, 0)
    res = cy._ask_tier_once(tsp, it.question, cy.PlacementStore(pls), units=it.units, facts=facts, plan_override=plan, budget=budget,
                            observe=False)
    ans = ro.read_out_result(tsp, res, facts) if res.candidates else None
    return res, ans


def indep_flats(w, two_seat="both"):
    """The strictly stable members of a record as flats by units, pad cut, canonical legs, by arm length (written without slide_flat)."""
    L = int(w.doc["L"])
    out = {}
    for i in range(w.class_size):
        if not w.readable(i):
            continue
        pad = L - w.doc["centre_search"]["member_L"][i]
        f = w.doc["members"][i]
        cut = [f[0]]
        for a in range(6):
            cut.extend(f[1 + a * L + pad: 1 + (a + 1) * L])
        flat = tuple(None if t is None else t.split("\x00")[0] for t in cut)
        out.setdefault(L - pad, set()).add(pl.canon(flat, L - pad))
    return out


def entry_key(e):
    return (tuple(e["words"]), tuple(e["centres"]), e["arrangements"], e["stability"])


def answer_key(e):
    return (tuple(e.words), tuple(e.centres), e.count, "%d/%d" % (e.stability.numerator, e.stability.denominator))


# ---------------------------------------------------------------------------------------------------------------------------------
# Part 1: what the reading is
# ---------------------------------------------------------------------------------------------------------------------------------
def test_hand_cross_equals_the_cycle_on_a_plain_placement(wi):
    """A hand cross (no unit twice) of window 6 (京都は古い都である。, a one-sentence window, L = 1): slide_flat's window read = the cycle + the read-out on
    the same cross held by a real placement.Placement.  Members a and a2 differ by a permutation of the legs (one start, two members), b has another
    centre."""
    a = ("京都", "古い", None, "都", None, None, None)
    a2 = ("京都", "都", None, "古い", None, None, None)
    b = ("都", "京都", "古い", None, None, None, None)
    w6i = edited(wi, 6, hand_members([a, a2, b], x_sides=["this", "this", "this"]))
    it = Q.intake(w6i, "京都は何ですか")
    w = w6i.by_n[6]
    r = F.read_window_flat(w6i, w, it, budget=BUDGET)
    assert r.starts == 2 and r.members_read == 3                       # a and a2 read alike (canonical legs): one start remembering both members
    res, ans = cycle_side(w6i, w, it, {1: {pl.canon(a, 1), pl.canon(b, 1)}})
    assert ans is not None and r.entries and len(r.entries) == len(ans.entries)
    assert [entry_key(e) for e in r.entries] == [answer_key(e) for e in ans.entries]
    assert r.digest == res.state_digest
    assert r.entries[0]["origin_members"] == [0, 1, 2] and r.entries[0]["arrangements"] == ans.entries[0].count >= 2
    assert set(r.entries[0]["words"]) == {"京都", "古い", "都"}


@pytest.mark.parametrize("n,q", [(0, "日本の首都は何ですか"), (3, "猫は何を食べますか"), (4, "魚は何ですか"), (4, "海は何ですか"), (6, "京都は何ですか"),
                                 (8, "人口は何ですか")])
def test_real_toy_windows_equal_the_cycle_on_the_same_starts(wi, n, q):
    w = wi.by_n[n]
    it = Q.intake(wi, q)
    r = F.read_window_flat(wi, w, it, budget=BUDGET, labels=False)
    flats = indep_flats(w)
    res, ans = cycle_side(wi, w, it, flats)
    assert [entry_key(e) for e in r.entries] == ([answer_key(e) for e in ans.entries] if ans is not None else [])
    if all(len({c for c in f if c}) == sum(1 for c in f if c) for fs in flats.values() for f in fs):
        assert r.digest == res.state_digest            # (a real Placement counts the arrangements of a cross with a unit twice wrongly: members_total)
    assert r.starts == sum(len(v) for v in flats.values())


def test_starts_strictly_stable_members_only_and_marking(wi):
    w4 = wi.by_n[4]
    w4i = edited(wi, 4, lambda d: d["judgement"]["member_judgement"][1].__setitem__("stable_strict", False))
    w = w4i.by_n[4]
    assert w.readable(0) and not w.readable(1)
    it = Q.intake(w4i, "魚は何ですか")
    r = F.read_window_flat(w4i, w, it, budget=BUDGET, labels=False)
    assert dict(r.tally).get(Q.UNSTABLE) == 1 and r.members_read == w.class_size - 1
    assert all(1 not in e["origin_members"] for e in r.entries)
    m = F.read_window_flat(w4i, w, it, budget=BUDGET, labels=False, strict="mark")
    assert m.members_read == w.class_size and Q.UNSTABLE not in dict(m.tally)
    flagged = [e for e in m.entries if 1 in e["origin_members"]]
    assert all(e["stable_strict"] is False for e in flagged)
    assert all(e["stable_strict"] is True for e in m.entries if 1 not in e["origin_members"])
    assert w4.class_size == w.class_size


def test_member_with_a_padded_arm_length_is_read_at_its_own_length(wi):
    w4 = wi.by_n[4]
    assert w4.member_pad(0) == 1
    lm, flat = F.member_flat(w4, 0)
    assert lm == 1 and len(flat) == 1 + 6 * 1
    L = w4.doc["L"]
    f = w4.doc["members"][0]
    assert flat == tuple(None if t is None else t.split("\x00")[0] for t in [f[0]] + [f[1 + a * L + 1] for a in range(6)])
    other = F.member_flat(w4, 1)
    assert other[0] == 2 and len(other[1]) == 13
    it = Q.intake(wi, "魚は何ですか")
    sts, gated = F.starts_of(w4, list(range(w4.class_size)), it.qset)
    assert sorted({s.L for s in sts}) == [1, 2] and gated == 0


def test_member_cap_counts_the_starts_it_leaves_unsettled(wi):
    """`member_cap` (cycle's, per arm length) never cuts silently: the starts it leaves are counted in the tally and in members_not_read."""
    w = wi.by_n[4]
    it = Q.intake(wi, "魚は何ですか")
    full = F.read_window_flat(wi, w, it, budget=BUDGET, labels=False)
    per_L = {}
    for s in F.starts_of(w, list(range(w.class_size)), it.qset)[0]:
        per_L[s.L] = per_L.get(s.L, 0) + 1
    assert F.MEMBER_CAP not in dict(full.tally)
    capped = F.read_window_flat(wi, w, it, budget=BUDGET, labels=False, member_cap=1)
    left = sum(n - 1 for n in per_L.values())
    assert left > 0 and dict(capped.tally).get(F.MEMBER_CAP) == left
    assert all(e["members_not_read"].get(F.MEMBER_CAP) == left for e in capped.entries)


def test_a_start_that_holds_no_question_unit_is_not_read(wi):
    flat_q = ("魚", None, "海", None, None, None, None, None, None, None, None, None, None)      # window 5 (魚が海にいる。), L = 1 read as L = 1
    # window 5 is a one-sentence window: L = 1, 7 entries
    a = ("魚", "海", None, None, None, None, None)
    b = ("魚", None, None, None, None, None, None)
    w5i = edited(wi, 5, hand_members([a, b]))
    it = Q.intake(w5i, "海は何ですか")
    w = w5i.by_n[5]
    r = F.read_window_flat(w5i, w, it, budget=BUDGET, labels=False)
    assert r.starts == 1 and dict(r.tally).get(Q.NO_QUESTION_UNIT) == 1


def test_local_space_is_the_corpus_tier(wi):
    """L-701: the slide's corpus-scope count of a pair of seated units IS the tier's same-sentence count, its 'before' IS p_pair: E_Q, n, p of the
    placement are the corpus tier's, which is what the flat reader reads."""
    tsp = wi.space.tiers[wi.tier]
    seen = 0
    for w in wi.windows:
        c = wi.counts(w)
        us = sorted(w.sentence_units)
        for o in us:
            for i in us:
                if o == i:
                    continue
                assert c.n_x(wi.tier, o, i) == tsp.n_pair(o, i), (w.n, o, i)
                assert c.before_x(wi.tier, o, i) == tsp.p_pair(o, i), (w.n, o, i)
                seen += 1
    assert seen > 50
    f = F.flat_facts(wi)
    assert f is F.flat_facts(wi) and f.tier is tsp and f.N == tsp.N


# ---------------------------------------------------------------------------------------------------------------------------------
# Part 2: two seats of a shared unit
# ---------------------------------------------------------------------------------------------------------------------------------
def test_two_seats_both_keeps_the_unit_on_two_cells_n_only_on_one(wi):
    w0 = wi.by_n[0]
    toks = [t for t in w0.doc["members"][0] if t is not None]
    assert sum(1 for t in toks if t.startswith("東京")) == 2                     # the record has two seats of 東京
    _, both = F.member_flat(w0, 0, "both")
    _, one = F.member_flat(w0, 0, "n_only")
    assert sum(1 for c in both if c == "東京") == 2 and sum(1 for c in both if c == "日本") == 2
    assert sum(1 for c in one if c == "東京") == 1 and sum(1 for c in one if c == "日本") == 1
    assert one[0] is not None                                                   # the centre is never emptied
    first = w0.window.sids[0]
    for i, t in enumerate(w0.doc["members"][0]):
        if t is not None and "\x00" in t and one[i] is not None and i != 0:
            assert int(t.split("\x00")[1]) == first                            # the kept seat of a non-centre shared unit is that of sentence N
    with pytest.raises(ValueError):
        F.member_flat(w0, 0, "first")


@pytest.mark.parametrize("two_seat", F.TWO_SEATS)
def test_both_two_seat_modes_read_and_trace(wi, two_seat):
    for q in ("日本の首都は何ですか", "東京は何ですか"):
        it = Q.intake(wi, q)
        r = F.read_window_flat(wi, wi.by_n[0], it, two_seat=two_seat, budget=BUDGET, labels=False)
        assert r.trace_ok and r.starts >= 1
        for e in r.entries:
            assert e["trace"]["ok"] and list(e["words"]) == sorted(set(e["words"]))


def test_a_unit_on_two_cells_of_one_walked_leg_is_a_word_once_in_the_entry(wi):
    """Window 4 (猫が魚を食べる。/ 魚が海にいる。): 魚 is in both sentences and keeps both seats.  The section walk steps from one cell of the unit to the
    other (n(u,u) = n(u) > 0, the energy does not drop), so a path lists the unit twice; the entry's word set lists it once; the trace holds
    (L-703).  The same answer is read by the cycle on a real Placement."""
    q = "魚は何ですか"
    w = wi.by_n[4]
    it = Q.intake(wi, q)
    r = F.read_window_flat(wi, w, it, budget=BUDGET, labels=False)
    res, ans = cycle_side(wi, w, it, indep_flats(w))
    paths = [p.words for i in ans.items for p in i.paths]
    assert any(len(p) != len(set(p)) for p in paths)                              # the scenario is exercised: a unit twice on one path
    assert [entry_key(e) for e in r.entries] == [answer_key(e) for e in ans.entries]
    for e in r.entries:
        assert len(e["words"]) == len(set(e["words"])) and e["trace"]["ok"]
    assert r.trace_ok


# ---------------------------------------------------------------------------------------------------------------------------------
# Part 3: labels
# ---------------------------------------------------------------------------------------------------------------------------------
def strip_labels(obj):
    o = json.loads(json.dumps(obj))
    for e in o["answer"]["entries"]:
        e.pop("axis_labels", None)
    o["thought"]["config"].pop("labels", None)
    o["thought"]["config"].pop("label_agreement", None)
    return o


def test_labels_are_attached_and_decide_nothing(wi, monkeypatch):
    for q in QUESTIONS:
        a = F.ask_flat(wi, q, budget=BUDGET)
        b = F.ask_flat(wi, q, budget=BUDGET, labels=False)
        assert a.verdict == b.verdict
        assert strip_labels(a.to_json_obj()) == strip_labels(b.to_json_obj())
        for e in a.entries:
            lab = e["axis_labels"]
            assert sorted(lab) == ["x", "y", "z"]
            for ax in lab:
                assert lab[ax]["of"] == len(e["origin_members"])
                assert lab[ax]["agreed"] == sum(lab[ax]["units"].values()) and lab[ax]["agreed"] + sum(lab[ax]["abstained"].values()) == lab[ax]["of"]
        for e in b.entries:
            assert e["axis_labels"] is None
    # replacing every label by another one changes nothing else
    q = "猫は何を食べますか"
    a = F.ask_flat(wi, q, budget=BUDGET)
    monkeypatch.setattr(F, "_axis_labels", lambda *x, **k: {"x": {"agreed": 99, "of": 99, "units": {"猫": 99}, "abstained": {}}})
    c = F.ask_flat(wi, q, budget=BUDGET)
    assert c.verdict == a.verdict and strip_labels(c.to_json_obj()) == strip_labels(a.to_json_obj())
    assert all(e["axis_labels"]["x"]["agreed"] == 99 for e in c.entries) and c.to_bytes() != a.to_bytes()


def test_a_label_is_the_per_axis_answer_of_the_placed_member(wi):
    """The label of an entry is slide_ratios' read of the START member (the placement as seated), computed here again independently."""
    q = "猫は何を食べますか"
    a = F.ask_flat(wi, q, budget=BUDGET)
    it = a.intake
    tsp = wi.space.tiers[wi.tier]
    for e in a.entries:
        w = wi.by_n[e["window"]["n"]]
        ev = SR.counts_evidence(wi.counts(w), wi.tier)
        agreed = {ax: 0 for ax in SR.AXES}
        for m in e["origin_members"]:
            r = SR.read_axes(Q.member_cross(w, m), ev, tsp, it.ctx, wi.foundation, z_self_edges=True, agreement="three")
            for ax in SR.AXES:
                agreed[ax] += r.answer(ax) is not None
        assert {ax: e["axis_labels"][ax]["agreed"] for ax in SR.AXES} == agreed


# ---------------------------------------------------------------------------------------------------------------------------------
# Part 4: entries, abstentions, verdict, cap
# ---------------------------------------------------------------------------------------------------------------------------------
def test_entry_shape_is_t7b_plus_the_window_fields(wi):
    a = F.ask_flat(wi, "猫は何を食べますか", budget=BUDGET)
    assert a.entries
    for e in a.entries:
        assert e["tier"] == "RUN" and e["structure"] == "slide_flat" and e["label"] == "slide:flat"
        assert list(e["words"]) == sorted(e["words"]) and e["arrangements"] >= 1 and e["centres"] == sorted(e["centres"])
        n, d = e["stability"].split("/")
        assert int(n) >= 0 and int(d) >= 1
        assert e["window"]["n"] in wi.by_n and e["window"]["sids"] == list(wi.by_n[e["window"]["n"]].window.sids)
        assert e["centre_sentence"] in ("this", "next", "both") and sum(e["centre_sentences"].values()) == len(e["origin_members"])
        assert e["stable_strict"] is True and e["class_size"] == wi.by_n[e["window"]["n"]].class_size
        assert e["trace"]["ok"] and e["trace"]["words_checked"] >= len(e["words"]) - 1
        assert e["source_sids"] == sorted(e["source_sids"])
    # never merged across windows: the same word set from two windows is two entries
    keys = [(e["window"]["n"], tuple(e["words"])) for e in a.entries]
    assert len(keys) == len(set(keys))
    ans = a.answer_obj()
    assert ans["structure"] == "slide_flat" and ans["listed"] == len(a.entries) and ans["tiers"] == ["RUN"]
    assert ans["read"]["windows_read"] == a.windows_read


def test_both_growths_are_pooled_and_labelled(wi):
    a = F.ask_flat(wi, "魚は何ですか", budget=BUDGET)
    sides = {sd for e in a.entries for sd in e["centre_sentences"]}
    assert sides == {"this", "next"}                                             # window 4: the centre in N for member 0, in N+1 for the others


def test_typed_abstentions_and_the_verdict_rule(wi):
    seen = set()
    for question in QUESTIONS:
        a = F.ask_flat(wi, question, budget=BUDGET)
        seen.add(a.verdict)
        if a.verdict in (F.ANSWER, F.CHOICE):
            assert (a.verdict == F.ANSWER) == (len(a.entries) == 1)
        else:
            assert not a.entries and (a.verdict.startswith("UNKNOWN") or a.verdict == cy.AMBIGUOUS)
        for ab in a.abstentions:
            assert ab["kind"] in F_KINDS or ab["kind"] == F.MIXED
            assert sum(ab["kinds"].values()) >= 1 and all(k in F_KINDS for k in ab["kinds"])
    assert F.UNKNOWN_NO_WINDOW in seen and F.ANSWER in seen and F.CHOICE in seen


F_KINDS = {F.RATIO_DISAGREEMENT, F.SECTION_DISAGREEMENT, F.POINTS_NOWHERE, F.NOT_GROUNDED, F.AMBIGUOUS_KIND, F.NO_FIXED_POINT_KIND, F.NO_PATH_KIND,
           F.UNSTABLE, F.NO_QUESTION_UNIT, F.MIXED}


def _plan(candidates, read):
    return Q.Plan(candidates, (), tuple(read), (), None, 0, "qcount_first")


def test_verdict_of_is_the_precedence_of_the_cycle_then_slide_query():
    P = _plan(3, (1, 2))
    ab = lambda *ks: [{"kinds": {k: 1 for k in ks}}]
    assert F.verdict_of(1, P, []) == F.ANSWER and F.verdict_of(2, P, []) == F.CHOICE
    assert F.verdict_of(0, _plan(0, ()), []) == F.UNKNOWN_NO_WINDOW and F.verdict_of(0, _plan(2, ()), []) == F.UNKNOWN_NOT_READ
    assert F.verdict_of(0, P, ab(F.AMBIGUOUS_KIND, F.NO_FIXED_POINT_KIND, F.RATIO_DISAGREEMENT)) == cy.AMBIGUOUS
    assert F.verdict_of(0, P, ab(F.NO_FIXED_POINT_KIND, F.RATIO_DISAGREEMENT)) == cy.UNKNOWN_NO_FIXED_POINT
    assert F.verdict_of(0, P, ab(F.RATIO_DISAGREEMENT, F.SECTION_DISAGREEMENT)) == cy.UNKNOWN_RATIO_DISAGREEMENT
    # cycle's member status "mixed" (end states with different non-answer statuses) is typed as cycle._verdict_from types "none:mixed"
    assert F.verdict_of(0, P, ab(F.MIXED)) == cy.UNKNOWN_RATIO_DISAGREEMENT
    assert F.verdict_of(0, P, ab(F.MIXED, F.SECTION_DISAGREEMENT, F.UNSTABLE)) == cy.UNKNOWN_RATIO_DISAGREEMENT
    assert F.verdict_of(0, P, ab(F.MIXED, F.NO_FIXED_POINT_KIND)) == cy.UNKNOWN_NO_FIXED_POINT
    assert F.verdict_of(0, P, ab(F.SECTION_DISAGREEMENT, F.UNSTABLE)) == cy.UNKNOWN_SECTION_DISAGREEMENT
    assert F.verdict_of(0, P, ab(F.UNSTABLE, F.NO_PATH_KIND)) == Q.UNKNOWN_UNSTABLE
    assert F.verdict_of(0, P, ab(F.NO_PATH_KIND)) == F.UNKNOWN_NO_PATH
    assert F.verdict_of(0, P, ab(F.POINTS_NOWHERE)) == cy.UNKNOWN_NO_EVIDENCE


def test_v1_and_the_cap_are_slide_querys(wi):
    q = "猫は何を食べますか"
    it = Q.intake(wi, q)
    full = Q.plan_windows(wi, it)
    a = F.ask_flat(wi, q, budget=BUDGET)
    assert list(a.plan.read) == list(full.read) and [r.window for r in a.reads] == list(full.read)
    assert all(wi.by_n[n].seated_any & it.qset for n in a.plan.read)             # V1: only windows that hold a question unit
    z = F.ask_flat(wi, q, nodes=0, budget=BUDGET)
    assert z.verdict == F.UNKNOWN_NOT_READ and not z.reads and z.plan.partial
    c = F.ask_flat(wi, q, nodes=1, budget=BUDGET)
    p1 = Q.plan_windows(wi, it, cap=1)
    assert [r.window for r in c.reads] == list(p1.read) and c.plan.read_obj() == p1.read_obj()
    g = F.ask_flat(wi, q, read_order="grammar_first", budget=BUDGET)
    assert g.plan.order == "grammar_first" and sorted(g.plan.read) == sorted(full.read)
    # the entries do not depend on the order of reading when nothing is cut
    assert sorted(json.dumps(e, sort_keys=True) for e in g.entries) == sorted(json.dumps(e, sort_keys=True) for e in a.entries)
    with pytest.raises(ValueError):
        F.ask_flat(wi, q, z_deep="order")                                       # a window index placed under the other rule is refused
    with pytest.raises(ValueError):
        F.ask_flat(wi, q, members="some")


def test_representative_reads_one_start_per_growth(wi):
    q = "魚は何ですか"
    full = F.ask_flat(wi, q, budget=BUDGET)
    rep = F.ask_flat(wi, q, members="representative", budget=BUDGET)
    for rf, rr in zip(full.reads, rep.reads):
        assert rf.window == rr.window and rr.starts <= rf.starts and rr.members_read <= rf.members_read
    w4 = next(r for r in rep.reads if r.window == 4)
    assert w4.members_read == 2                                                  # the centre in N and the centre in N+1
    assert all(e["members_read"] == w4.members_read for e in rep.entries if e["window"]["n"] == 4)
    # ... and the entry says how many members each growth has, i.e. what its representative stands for
    assert all(e["growth_members"] == {"next": 4, "this": 1} for e in rep.entries if e["window"]["n"] == 4)
    assert all(e["growth_members"] == {"next": 4, "this": 1} for e in full.entries if e["window"]["n"] == 4)


def test_a_one_sentence_window_and_the_one_sentence_article(wi):
    a = F.ask_flat(wi, "京都は何ですか", budget=BUDGET)
    assert a.verdict == F.ANSWER and a.entries[0]["window"]["sids"] == [6] and a.entries[0]["window"]["constructed"] is True


# ---------------------------------------------------------------------------------------------------------------------------------
# Part 5: bytes, floats, trace
# ---------------------------------------------------------------------------------------------------------------------------------
def test_bytes_do_not_depend_on_the_hash_seed(tmp_path):
    script = tmp_path / "run.py"
    script.write_text(
        "import hashlib, sys\n"
        "sys.path.insert(0, %r)\n"
        "from tests.line3 import test_slide_flat as T\n"
        "from verantyx.line3 import slide_flat as F, slide_query as Q, space as sp\n"
        "rows = T.toy_rows(); space = sp.build_space(rows)\n"
        "wi = Q.WindowIndex.from_space(space, None, rows=rows, level=T.LEVEL)\n"
        "h = hashlib.sha256()\n"
        "for q in T.QUESTIONS:\n"
        "    for kw in ({}, {'members': 'representative'}, {'two_seat': 'n_only'}, {'effort': 'fast'}, {'evidence': 'window'}):\n"
        "        h.update(F.ask_flat(wi, q, budget=T.BUDGET, **kw).to_bytes())\n"
        "print(h.hexdigest())\n" % ROOT)
    out = set()
    for seed in ("0", "1", "12345"):
        env = dict(os.environ, PYTHONHASHSEED=seed, PYTHONPATH=ROOT)
        r = subprocess.run([PY, str(script)], capture_output=True, text=True, env=env, cwd=ROOT, timeout=600)
        assert r.returncode == 0, r.stderr[-2000:]
        out.add(r.stdout.strip())
    assert len(out) == 1 and len(next(iter(out))) == 64


def test_no_floating_point_number_anywhere(wi):
    src = open(os.path.join(ROOT, "verantyx/line3/slide_flat.py"), encoding="utf-8").read()
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant):
            assert type(node.value).__name__ != "float", node.lineno
        if isinstance(node, ast.Name):
            assert node.id != "float", node.lineno
        assert not isinstance(node, ast.Div), node.lineno
    def walk(o):
        if isinstance(o, dict):
            for v in o.values():
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)
        else:
            assert type(o).__name__ != "float"
    for q in QUESTIONS:
        walk(F.ask_flat(wi, q, budget=BUDGET).to_json_obj())


def test_every_word_traces_on_the_window_tier_and_the_check_bites(wi):
    it = Q.intake(wi, "猫は何を食べますか")
    tsp = wi.space.tiers[wi.tier]
    facts = F.flat_facts(wi)
    w = wi.by_n[4]
    sts, _ = F.starts_of(w, list(range(w.class_size)), it.qset)
    seeds = {}
    for lm in sorted({s.L for s in sts}):
        seeds["W4/L%d" % lm] = F.FlatCross("W4/L%d" % lm, lm, tuple(s.flat for s in sts if s.L == lm))
    names = tuple(sorted(seeds))
    plan = cy.ReadPlan((("window", names),), names, (), len(names), None, False, 0)
    res = cy._ask_tier_once(tsp, it.question, F._Store(seeds), units=it.units, facts=facts, plan_override=plan, budget=BUDGET, observe=False)
    ans = ro.read_out_result(tsp, res, facts)
    _t, rep = TC.trace_answer(tsp, ans)
    assert rep.ok and rep.words_checked > 0 and rep.words_traced == rep.words_checked
    # a state that no longer holds the word at the seat the path names fails the trace
    st0 = ans.states[0]
    p0 = st0.paths[0]
    seat = p0.seats[0]
    bad_flat = tuple(("魚" if i == seat and c != "魚" else ("猫" if i == seat else c)) for i, c in enumerate(st0.ref.flat))
    bad_state = dataclasses.replace(st0, ref=dataclasses.replace(st0.ref, flat=bad_flat))
    bad = dataclasses.replace(ans, states=(bad_state,) + tuple(ans.states[1:]))
    _t, rep2 = TC.trace_answer(tsp, bad)
    assert not rep2.ok
    a = F.ask_flat(wi, "猫は何を食べますか", budget=BUDGET)
    assert a.reads and all(r.trace_ok and r.trace_checks >= 0 for r in a.reads)


def test_the_flat_read_does_not_touch_the_per_axis_path(wi):
    """slide_query's answer is unchanged by importing / using slide_flat (same bytes before and after a flat read)."""
    q = "猫は何を食べますか"
    before = Q.ask_slide(wi, q).to_bytes()
    F.ask_flat(wi, q, budget=BUDGET)
    assert Q.ask_slide(wi, q).to_bytes() == before


# ---------------------------------------------------------------------------------------------------------------------------------
# Part 6: evidence "window" (L-714): the pair count of the flat reader is the window's, label-blind
# ---------------------------------------------------------------------------------------------------------------------------------
def test_window_evidence_is_the_label_blind_sum_of_the_windows_counts(wi):
    tsp = wi.space.tiers[wi.tier]
    seen_z = 0
    for w in wi.windows:
        c = wi.counts(w)
        ev = F.window_evidence(c, wi.tier)
        wt = F.window_tier(wi, w)
        us = sorted(w.sentence_units)
        for o in us:
            for i in us:
                if o == i:
                    assert wt.n_pair(o, i) == tsp.n(o)
                    continue
                want = c.n_x(wi.tier, o, i) + c.n_y(wi.tier, o, wi.tier, i) + c.n_y(wi.tier, i, wi.tier, o) \
                    + c.n_z(wi.tier, o, wi.tier, i) + c.n_z(wi.tier, i, wi.tier, o)
                assert wt.n_pair(o, i) == wt.n_pair(i, o) == want, (w.n, o, i)
                assert (o, i) in ev or (i, o) in ev or want == 0
                seen_z += c.n_z(wi.tier, o, wi.tier, i) > 0 and c.n_x(wi.tier, o, i) == 0
        # a pair outside the pack, and any other unit, is the corpus tier's
        assert wt.n_pair("犬", "京都") == tsp.n_pair("犬", "京都") == 0
        with pytest.raises(NotImplementedError):
            wt.p_pair(us[0], us[-1])
    assert seen_z > 0                                                            # the toy has pairs evidenced by the slide only


def test_window_tier_shares_n_and_the_postings_with_the_corpus(wi):
    base = F.flat_facts(wi)
    w = wi.by_n[3]
    wt = F.window_tier(wi, w)
    wf = F.WindowFacts(wt, base)
    assert wf.N == base.N and wf.n is base.n and wf.D == base.D and wt.postings is wi.space.tiers[wi.tier].postings
    assert wf.npair("猫", "魚") == wt.n_pair("猫", "魚") and wf.npair("猫", "猫") == base.n["猫"]
    # a pair seated on two sides of the window and in no common sentence has slide evidence only
    assert base.npair("犬", "魚") == 0 and wf.npair("犬", "魚") == wi.counts(w).n_z(wi.tier, "犬", wi.tier, "魚") > 0


def test_trace_tier_appends_one_pair_sentence_per_adjacent_pair(wi):
    base = wi.space.tiers[wi.tier]
    t = F.trace_tier(wi)
    pairs = [pw.sids for pw in wi.slide.pairs()]
    assert t.N == base.N + len(pairs) and t is F.trace_tier(wi)
    for u, p in base.postings.items():
        assert t.postings[u][:len(p)] == p and all(s >= base.N for s in t.postings[u][len(p):])
    a, b = pairs[3]
    assert set(t.sentence_units[base.N + 3]) == set(base.sentence_units[a]) | set(base.sentence_units[b])


def test_window_evidence_equals_the_cycle_on_the_window_tier_and_traces(wi):
    for n, q in ((3, "猫は何を食べますか"), (4, "魚は何ですか"), (0, "日本の首都は何ですか")):
        w = wi.by_n[n]
        it = Q.intake(wi, q)
        r = F.read_window_flat(wi, w, it, budget=BUDGET, labels=False, evidence="window")
        wt = F.window_tier(wi, w)
        res, ans = cycle_side(wi, w, it, indep_flats(w), tsp=wt, facts=F.WindowFacts(wt, F.flat_facts(wi)))
        assert [entry_key(e) for e in r.entries] == ([answer_key(e) for e in ans.entries] if ans is not None else [])
        assert r.trace_ok and all(e["evidence"] == "window" and e["trace"]["ok"] for e in r.entries)
        if ans is not None:                                                      # every cited sentence holds a word of the entry
            for e in r.entries:
                assert e["source_sids"] == sorted(e["source_sids"]) and all(0 <= s < wi.space.N for s in e["source_sids"])


def test_the_evidence_switch_changes_the_reading_and_the_default_is_plain(wi):
    q = "猫は何を食べますか"
    p = F.ask_flat(wi, q, budget=BUDGET)
    assert p.config["evidence"] == "plain" and p.to_bytes() == F.ask_flat(wi, q, budget=BUDGET, evidence="plain").to_bytes()
    differ = 0
    for question in QUESTIONS:
        a = F.ask_flat(wi, question, budget=BUDGET, labels=False)
        b = F.ask_flat(wi, question, budget=BUDGET, labels=False, evidence="window")
        assert b.config["evidence"] == "window"
        differ += [(e["window"]["n"], e["words"]) for e in a.entries] != [(e["window"]["n"], e["words"]) for e in b.entries]
    assert differ >= 1
    with pytest.raises(ValueError):
        F.ask_flat(wi, q, evidence="axis")


def test_window_evidence_says_how_much_of_the_trace_rests_on_a_constructed_sentence(wi):
    """L-714: under evidence "window" the trace reads a tier with appended pair sentences; the entry counts the path words whose edge only such a
    sentence evidences (a real sentence sorts first, so 0 means every edge has a real sentence).  Under "plain" the count is 0 and the tier is real."""
    q = "犬が追うのは何ですか"
    a = F.ask_flat(wi, q, budget=BUDGET, labels=False, evidence="window")
    assert a.entries and all(e["trace"]["ok"] for e in a.entries)
    assert any(e["trace"]["constructed_edge_words"] > 0 for e in a.entries)
    assert all(0 < e["trace"]["constructed_edge_words"] <= e["trace"]["edge_words"] for e in a.entries)
    b = F.ask_flat(wi, q, budget=BUDGET, labels=False)
    assert all(e["trace"]["constructed_edge_words"] == 0 for e in b.entries)
    c = F.ask_flat(wi, "京都は何ですか", budget=BUDGET, labels=False, evidence="window")
    assert all(e["trace"]["constructed_edge_words"] == 0 for e in c.entries)             # one real sentence holds every edge


def test_ask_flat_through_an_ask_index_and_the_window_index_are_the_same_read(tmp_path, wi, rows):
    """`index` may be an ask.Index (its window index is built / kept like ask_slide's) or a slide_query.WindowIndex; same bytes either way."""
    data = tmp_path / "toy.jsonl"
    data.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
    idx = A.Index.from_jsonl(str(data), None, LEVEL, ("RUN",))
    q = "猫は何を食べますか"
    a = F.ask_flat(idx, q, budget=BUDGET, **PRE_G3I)
    assert idx._slide_windows and a.to_bytes() == F.ask_flat(wi, q, budget=BUDGET).to_bytes()
    assert F.ask_flat(idx, q, budget=BUDGET, **PRE_G3I).to_bytes() == a.to_bytes()
    # G3-i: with nothing said the index is the new default one (z_deep "order", seat_empty_axis "deny") and it equals an explicit one
    d = F.ask_flat(idx, q, budget=BUDGET)
    wd = Q.WindowIndex.from_space(sp.build_space(rows), None, rows=rows, level=LEVEL, z_deep="order", place_kw={"seat_empty_axis": "deny"})
    assert d.to_bytes() == F.ask_flat(wd, q, budget=BUDGET).to_bytes() and d.config["z_deep"] == "order"
    assert F.ask_flat(idx, q, budget=BUDGET, z_deep="order").to_bytes() == d.to_bytes()          # the default spelled out through the same Index = the default (was z_deep="slide" before G3-i)
    assert wd.spec.seat_empty_axis == "deny" and wd.z_deep == "order" and wd.slide.spec.sha256() != wi.slide.spec.sha256()
