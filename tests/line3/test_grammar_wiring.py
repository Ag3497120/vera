"""G3-k tests (L-800..): the unknown-word stand-ins and the grammar layer's read order wired into the question path
(verantyx/line3/wiring.py; cycle.py, ask.py, matryoshka.py, slide_query.py, slide_flat.py, combined.py, cli.py `--grammar on|off`).

Part 1 (the stem rule): a unit that ends inside a WORD takes the particle after the whole WORD (grammar `stem="whole_word"`); the default records keep their bytes.
Part 2 (the intake): an unknown RUN word of the question gets its stand-ins (WORD parts known to the corpus; CHAR parts when none is) as ADDITIONAL query units,
marked and listed with their chance counts; a word that V2 drops, a known word, a unit already in the question gets nothing; the query cross, the sections and E_Q
stay the original units'.
Part 3 (the flat read): the crosses read are chosen by the original units AND the stand-ins (V1), a full read grows only through crosses that hold a stand-in and no
original unit, and only the entries of such crosses are marked `via_standin`; a question with no unknown word has the same entries on a full read, in every tier,
with and without a slot; under a cap the read order is (original units held, stand-in units held), then the grammar kind of the cross (the slot first), then the
order of T7b (group, E_Q) -- checked against an independent construction for every cap; a tie is one block, never split.
Part 4 (the windows and the layers): windows that hold only stand-ins are candidates and are read after those that hold an original unit; their entries are marked;
the layers' re-asks keep the stand-ins and the read hook.
Review fixes (L-810..L-816): the layer-1 bundles are the read crosses, not every stand-in; `read_via_standin` is the exact diff of the read sets of the order with and without the
stand-ins (flat and windows), next to `via_standin` (cross by placement, twins counted); the stem count lives outside `follow`; the marks of equal entries are by position.
Part 5 (the combined list and the entrance): the `grammar` row of the header, `grammar_form` / `standins` in the answer, the mark in the text form, the CLI switch.
Part 6 (defaults and bytes): grammar "off" is byte-identical in every structure, no new key appears; PYTHONHASHSEED 0 / 1 / 12345; no floating-point number.
"""
import ast
import json
import os
import subprocess
import sys
from fractions import Fraction
from types import SimpleNamespace

import pytest

from tests.line3 import test_slide_flat as TF
from verantyx.line3 import ask as A
from verantyx.line3 import combined as CB
from verantyx.line3 import cycle as cy
from verantyx.line3 import grammar as Gr
from verantyx.line3 import matryoshka as M
from verantyx.line3 import slide_flat as F
from verantyx.line3 import slide_query as Q
from verantyx.line3 import space as sp
from verantyx.line3 import wiring as W
from verantyx.line3.placement import from_cross

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PY = sys.executable
SENTS_PATH = os.path.join(ROOT, "experiments", "line3", "bank2", "data", "fulllead_sents.jsonl")
UNK = ["東京都庁の人口は何ですか", "東京都庁の首都は何ですか", "東京都庁はどこですか", "ネコは何を食べますか", "東京の東京都庁は何ですか"]
KNOWN = [q for q in TF.QUESTIONS if q != "存在しない語は何ですか"]
EFFORT = "fast"


# ---------------------------------------------------------------------------------------------------------------------------------
# fixtures
# ---------------------------------------------------------------------------------------------------------------------------------
@pytest.fixture(scope="module")
def rows():
    return TF.toy_rows()


@pytest.fixture(scope="module")
def space(rows):
    return sp.build_space(rows)


@pytest.fixture(scope="module")
def idx(space):
    return A.Index(space, level=TF.LEVEL)


@pytest.fixture(scope="module")
def wi(space, rows):
    return Q.WindowIndex.from_space(space, None, rows=rows, level=TF.LEVEL, z_deep="slide", place_kw={"seat_empty_axis": "allow"})


@pytest.fixture(scope="module")
def ctx_(idx):
    return W.context_of(idx)


@pytest.fixture(scope="module")
def data_file(tmp_path_factory, rows):
    p = tmp_path_factory.mktemp("g3k") / "toy.jsonl"
    p.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
    return str(p)


def units_of(store, seed):
    p = store.cross_for(seed)
    u = {c for c in from_cross(p.cross) if c is not None}
    for t in p.twin_sets:
        u.update(t)
    return u


# ---------------------------------------------------------------------------------------------------------------------------------
# Part 1: the stem rule
# ---------------------------------------------------------------------------------------------------------------------------------
def test_follower_stem_rule_by_hand():
    words = [("食べる", 0, 3), ("を", 3, 4), ("魚", 4, 5), ("が", 5, 6)]
    assert Gr.follower(words, 1) == ("straddle", "食べる", (0, 3))                       # the default: nothing is decided
    assert Gr.follower(words, 1, "whole_word") == ("particle", "を", (3, 4))             # the owner: the particle after the whole WORD
    assert Gr.follower(words, 3, "whole_word") == Gr.follower(words, 3) == ("particle", "を", (3, 4))   # a span that ends at a word end is read as before
    assert Gr.follower([("食べる", 0, 3), ("魚", 3, 4)], 2, "whole_word") == ("other", "魚", (3, 4))
    assert Gr.follower([("食べる", 0, 3)], 2, "whole_word") == ("end", None, None)
    with pytest.raises(ValueError):
        Gr.Records([], {}, {}, 0, [], "nope")


def test_whole_word_records_on_fulllead_and_the_default_bytes():
    texts = [json.loads(l)["sent"] for l in open(SENTS_PATH, encoding="utf-8")]
    d = Gr.build_records(texts)
    assert d.to_bytes() == Gr.build_records(texts, stem="straddle").to_bytes() and b'"stem"' not in d.to_bytes()      # the default bytes are unchanged
    w = Gr.build_records(texts, stem="whole_word")
    assert w.stem == "whole_word" and json.loads(w.to_bytes())["stem"] == "whole_word"
    assert d.follow["RUN"]["straddle"] == 353 and w.follow["RUN"]["straddle"] == 0
    # L-814: the stems that took the whole word's particle are counted OUTSIDE `follow` (they are inside particle / other / end there): a plain sum over `follow` is the heads
    assert w.stemmed["RUN"] == 353 and w.stemmed["WORD"] == 0 and d.stemmed == {} and "stem_whole_word" not in w.follow["RUN"]
    assert json.loads(w.to_bytes())["stem_whole_word"] == {"RUN": 353, "WORD": 0} and b"stem_whole_word" not in d.to_bytes()
    for tier in ("RUN", "WORD"):
        assert sum(w.follow[tier].values()) == sum(n for (t, _u), n in w.heads.items() if t == tier) == sum(d.follow[tier].values())
    assert w.follow["WORD"]["straddle"] == 0 == d.follow["WORD"]["straddle"]          # the WORD cut has no stem
    heads = sum(1 for k in w.heads if k[0] == "RUN")
    for tier in ("RUN", "WORD"):
        f = w.follow[tier]
        assert sum(f[k] for k in Gr.P7) + f["other"] + f["end"] == sum(n for (t, _u), n in w.heads.items() if t == tier)       # nothing dropped silently
    assert heads == sum(1 for k in d.heads if k[0] == "RUN")
    assert w.n_attachments("WORD") == d.n_attachments("WORD") and w.n_attachments("RUN") >= d.n_attachments("RUN")
    assert [a for a in w.attachments if a.tier == "WORD"] == [a for a in d.attachments if a.tier == "WORD"]
    assert Gr.trace_check(w, lambda sid: texts[sid]) == [] and Gr.trace_check(d, lambda sid: texts[sid]) == []
    # a stem that now has a record: the attachment's particle is the one after the whole WORD, not adjacent to the unit
    grown = [a for a in w.attachments if a.tier == "RUN" and a.p_start > a.end]
    from verantyx.lang import strip_attribution
    assert grown and all(strip_attribution(texts[a.sid])[a.p_start:a.p_end] == a.particle for a in grown)


# ---------------------------------------------------------------------------------------------------------------------------------
# Part 2: the intake and the stand-ins
# ---------------------------------------------------------------------------------------------------------------------------------
def test_standins_are_added_marked_and_counted_on_a_toy(space, ctx_):
    ix, _recs = ctx_
    gi = W.intake(space, "東京都庁の人口は何ですか", ix)
    assert gi.units == ("東京都庁", "人口") and gi.standins == ("東京", "東京タワー") and gi.run_units == ("東京都庁", "人口", "東京", "東京タワー")
    (w,) = gi.words
    assert (w.word, w.type, w.via) == ("東京都庁", "T3", "WORD") and w.parts == (("WORD", "東京"),)
    assert w.units == ("東京", "東京タワー") == w.added and w.n_standins == 2
    # independent: the RUN units of the space whose surface holds the known part (the toy has no unit whose string holds it without the part cut there)
    run = space.tiers["RUN"]
    assert set(w.units) == {u for u in run.postings if "東京" in u}
    assert w.pool == len(run.postings) and w.chance() == Fraction(2, len(run.postings))
    assert w.to_obj()["chance"] == "2/%d" % len(run.postings) and w.to_obj()["provenance"] == "stand-in"
    assert all(u in run.postings for u in gi.standins)                        # a stand-in is a unit of the corpus; the unknown word is not
    assert "東京都庁" not in run.postings
    assert gi.form == "predicate" and gi.slot is None and gi.header_row()["standins"] == 2 and gi.header_row()["unknown_words"] == ["東京都庁"]
    # a known question has none; an unknown word with no known part (T5) is reported with zero
    k = W.intake(space, "日本の首都は何ですか", ix)
    assert k.standins == () and k.words == () and k.run_units == k.units
    n = W.intake(space, "ネコは何を食べますか", ix)
    assert n.standins == () and [(x.word, x.type, x.n_standins) for x in n.words] == [("ネコ", "T5", 0)] and n.form == "slot" and n.slot == "を"
    # a stand-in that is already a question unit is not added again, and one word's stand-ins are not added twice
    d = W.intake(space, "東京の東京都庁は何ですか", ix)
    assert d.units == ("東京", "東京都庁") and d.standins == ("東京タワー",) and d.words[0].units == ("東京", "東京タワー") and d.words[0].added == ("東京タワー",)


def test_a_word_that_v2_drops_gets_no_standins(space, ctx_):
    ix, _ = ctx_
    for q in UNK + KNOWN:
        gi = W.intake(space, q, ix)
        assert all(x.word in gi.units for x in gi.words)                        # only query units get stand-ins
        assert set(gi.standins).isdisjoint(gi.units) and len(set(gi.standins)) == len(gi.standins)
        assert all(u in space.tiers["RUN"].postings for u in gi.standins)


def test_context_keeps_the_originals_cross_and_energies(space):
    plain = cy.make_context(("東京都庁", "人口"))
    marked = cy.make_context(("東京都庁", "人口", "東京", "東京タワー"), standins=("東京", "東京タワー"))
    assert marked.standins == ("東京", "東京タワー") and marked.query == ("東京都庁", "人口", "東京", "東京タワー")
    assert marked.qcross == plain.qcross and marked.attached == plain.attached and marked.energy_units == plain.energy_units
    assert plain.standins == () and cy.make_context(("a", "b")) == cy.make_context(("a", "b"), "first_layer", ())
    seven = tuple("abcdefg")
    assert cy.make_context(seven + ("x",), standins=("x",)).qcross == cy.make_context(seven).qcross             # the stand-ins never take a section


# ---------------------------------------------------------------------------------------------------------------------------------
# Part 3: the flat read
# ---------------------------------------------------------------------------------------------------------------------------------
def test_candidate_crosses_grow_only_through_standin_crosses(idx, space, ctx_):
    ix, recs = ctx_
    ts, facts, st = space.tiers["RUN"], idx.facts["RUN"], idx.stores["RUN"]
    grew = False
    for q in UNK + KNOWN:
        gi = W.intake(space, q, ix)
        kw = W.tier_kw(gi, "RUN", recs)
        off = cy.plan_read(ts, facts, cy.make_context(gi.units), st, None, True, False, None)
        on = cy.plan_read(ts, facts, cy.make_context(kw.get("units", gi.units), standins=kw.get("standins", ())), st, None, True, False, None)
        a, b = set(off.read), set(on.read)
        assert a <= b                                                            # nothing is dropped from the candidates
        orig = set(cy.make_context(gi.units).energy_units)
        extra = b - a
        for s in extra:
            u = units_of(st, s)
            assert u & set(gi.standins) and not (u & orig)                       # a new cross holds a stand-in and no original unit
        assert all((units_of(st, s) & set(gi.standins)) or (units_of(st, s) & orig) for s in b)
        if not gi.standins:
            assert a == b
        grew = grew or bool(extra)
    assert grew                                                                  # the toy has a question where the stand-ins add a cross


def expected_blocks(idx, ts, ctx, slot, recs, tier="RUN"):
    """The read order under a cap, constructed independently of cycle._plan_read_grammar: seeds that hold a query unit (original or stand-in), the key
    (-originals held, -stand-ins held, grammar group, group query_unit < holds_query_unit, -E_Q), equal keys one block."""
    st, facts = idx.stores[tier], idx.facts[tier]
    q, sq = set(ctx.energy_units), set(ctx.standins) - set(ctx.energy_units)
    cand = []
    for s in ts.units():
        u = units_of(st, s)
        if u & (q | sq):
            cand.append((s, len(u & q), len(u & sq)))
    hook = W.ReadHook(tier, recs, slot)
    rank = hook([c[0] for c in cand])
    rq = lambda u: facts.n[u] + sum(facts.npair(x, u) for x in ctx.energy_units)
    by = {}
    for s, no, ns in cand:
        g = 0 if (s in q or s in sq) else 1
        by.setdefault((-no, -ns, rank[s][0], g, -rq(s)), []).append(s)
    return [tuple(sorted(by[k])) for k in sorted(by)], {k: v for k, v in by.items()}


def _cases_of(space, ix, recs, tier):
    """(question, context, kw, slot) per question for one tier: RUN with the stand-ins; WORD (no stand-ins) cut like the tier cuts it, V2 applied."""
    from verantyx.line3.funcwords import default_filter
    out = []
    for q in UNK + KNOWN:
        gi = W.intake(space, q, ix)
        kw = W.tier_kw(gi, tier, recs)
        if tier == "RUN":
            units, marks = kw.get("units", gi.units), kw.get("standins", ())
        else:
            flt = default_filter(tier)
            units, marks = tuple(u for u in cy.split_question(tier, q) if not (flt is not None and flt(u))), ()
        out.append((q, cy.make_context(units, standins=marks), kw, gi.slot))
    return out


def test_read_order_under_a_cap_is_count_then_kind_then_eq(idx, space, ctx_):
    """Checks the cap / block / boundary / partial mechanics and the sort key against `expected_blocks`.  HONEST SCOPE (L-816): `expected_blocks` shares ReadHook and the E_Q
    formula with the code, so it pins the key's STRUCTURE (which fields, in which order, ties as one block), not the meaning of the kind or of E_Q.  Run on RUN and on WORD."""
    ix, recs = ctx_
    differs = ties = slots = 0
    for tier in ("RUN", "WORD"):
        ts, facts, st = space.tiers[tier], idx.facts[tier], idx.stores[tier]
        for q, ctx, kw, slot in _cases_of(space, ix, recs, tier):
            blocks, _by = expected_blocks(idx, ts, ctx, slot, recs, tier)
            slots += slot is not None
            total = sum(len(b) for b in blocks)
            ties += any(len(b) > 1 for b in blocks)
            for cap in range(0, total + 2):
                plan = cy.plan_read(ts, facts, ctx, st, None, True, False, cap, kw["grammar"])
                assert [s for _g, s in plan.order_groups] == blocks                  # the blocks, in order
                rd, bnd = [], 0
                for b in blocks:
                    if len(rd) + len(b) > cap:
                        bnd = len(b)
                        break
                    rd.extend(b)
                assert list(plan.read) == rd and plan.boundary == bnd               # whole blocks, the first that does not fit stops the read, a tie is not split
                assert plan.cap == cap and plan.cap_total == total and plan.cap_unread == total - len(rd) and plan.partial == (total > len(rd))
                assert plan.grammar is not None and len(plan.grammar) == len(plan.order_groups)
                # the rows: originals held, stand-ins held, group reason, kind label -- non-increasing in the first two across the list
                keys = [(r[0], r[1]) for r in plan.grammar]
                assert keys == sorted(keys, reverse=True)
            off = cy.plan_read(ts, facts, cy.make_context(ctx.query[:len(ctx.query) - len(ctx.standins)]), st, None, True, False, 2)
            on = cy.plan_read(ts, facts, ctx, st, None, True, False, 2, kw["grammar"])
            differs += off.read != on.read
    assert differs and ties and slots                                            # not vacuous: the order differs from T7b's somewhere, there are ties and slots


def test_the_original_count_comes_first_and_a_slot_kind_breaks_only_a_tie(idx, space, ctx_):
    ix, recs = ctx_
    ts = space.tiers["RUN"]
    for q in UNK + KNOWN:
        gi = W.intake(space, q, ix)
        kw = W.tier_kw(gi, "RUN", recs)
        ctx = cy.make_context(kw.get("units", gi.units), standins=kw.get("standins", ()))
        plan = cy.plan_read(ts, idx.facts["RUN"], ctx, idx.stores["RUN"], None, True, False, 1000, kw["grammar"])
        no_ns = [(r[0], r[1]) for r in plan.grammar]
        assert no_ns == sorted(no_ns, reverse=True)                              # (originals held, stand-ins held) never increases down the list
        # inside one (originals, stand-ins) value the grammar group comes next: match, particle, tied, none (the reason order of grammar.read_order)
        order = {"match": 0, "particle": 1, "tied": 2, "none": 3}
        for key in set(no_ns):
            rs = [order[r[2]] for r in plan.grammar if (r[0], r[1]) == key]
            assert rs == sorted(rs)
        if gi.slot is None:
            assert all(r[2] != "match" for r in plan.grammar)                    # no slot particle (predicate, plain, standin): no match group (L-642 / L-548)


def test_the_hook_is_the_kind_of_the_centre_word(idx, space, ctx_):
    _ix, recs = ctx_
    for tier in ("RUN", "WORD"):
        h = W.ReadHook(tier, recs, "を")
        for s in space.tiers[tier].units():
            assert h.kind(s) == recs.kind(tier, s)
    c = W.ReadHook("CHAR", recs, "を")
    assert all(c.kind(s) == Gr.NONE_KIND for s in space.tiers["CHAR"].units())          # CHAR has no records (L-541): one group
    assert set(r[0] for r in c(space.tiers["CHAR"].units()).values()) == {0}
    assert recs.stem == "whole_word"


def entries_of(c, tier):
    return {e.words for t, e in c.entries if t == tier}


def test_no_unknown_word_means_the_same_entries_on_a_full_read(idx, space, ctx_):
    ix, _ = ctx_
    slotted = plain = 0
    for q in KNOWN:
        gi = W.intake(space, q, ix)
        if gi.standins:
            continue
        a = A.ask(idx, q, nodes=1000)
        b = A.ask(idx, q, nodes=1000, grammar="on")
        for t in ("RUN", "WORD", "CHAR"):
            assert entries_of(a, t) == entries_of(b, t), (q, t)
        assert a.verdict == b.verdict
        slotted += gi.slot is not None
        plain += gi.slot is None
    assert slotted and plain


def test_entries_of_a_standin_question_grow_only_through_marked_entries(idx, space):
    for q in UNK:
        a = A.ask(idx, q, nodes=1000)
        b = A.ask(idx, q, nodes=1000, grammar="on")
        for t in ("WORD", "CHAR"):
            assert entries_of(a, t) == entries_of(b, t)                          # only the RUN tier has stand-ins
        o = b.outcome("RUN")
        flags = dict(zip([e.words for e in o.entries], o.via_standin))
        new = entries_of(b, "RUN") - entries_of(a, "RUN")
        assert all(flags[w] for w in new), q                                     # what is new is marked
        # the mark is recomputed from the states: every state of a marked entry lies in a cross that holds no original unit
        orig = set(W.intake(space, q).units)
        for e, f in zip(o.entries, o.via_standin):
            sts = {si for arr in e.arrangements for si in arr.origins}
            # the cross of a state is the placement of its seed: its centre, seats AND twins (L-812), not the one arrangement the end state shows
            assert sts and f == all(not (cy.placement_units(idx.stores["RUN"].cross_for(o.answer.states[si].ref.seed)) & orig) for si in sts)
        assert all(x is False for x in A.ask(idx, q, nodes=1000, grammar="on").outcome("WORD").via_standin)


def test_via_standin_of_by_hand():
    from verantyx.line3.placement import to_cross

    def st(seed):
        return SimpleNamespace(ref=SimpleNamespace(seed=seed))
    n = (None,) * 4
    crosses = {"o1": (("a", None, None) + n, ()), "s1": (("s1", "s2", None) + n, ()),
               "t1": (("s3", None, None) + n, (("b", "b2"),))}          # t1 holds the original b ONLY as a twin: its end state shows s3 and one of b / b2 at most

    class Pl:
        def cross_for(self, seed):
            flat, tw = crosses[seed]
            return SimpleNamespace(cross=to_cross(flat, 1), twin_sets=tw)
    ans = SimpleNamespace(states=(st("o1"), st("s1"), st("t1")),
                          entries=(SimpleNamespace(arrangements=(SimpleNamespace(origins=(0,)),)),
                                   SimpleNamespace(arrangements=(SimpleNamespace(origins=(1,)), SimpleNamespace(origins=(1,)))),
                                   SimpleNamespace(arrangements=(SimpleNamespace(origins=(1,)), SimpleNamespace(origins=(1, 2)))),
                                   SimpleNamespace(arrangements=())))                      # an entry with no origin state
    # entry 0: a cross with an original; 1: only a stand-in cross; 2: one of its states is the twin cross (counts as holding b); 3: no origin => not marked (L-812)
    assert W.via_standin_of(ans, frozenset({"a", "b"}), Pl()) == (False, True, False, False)
    assert W.via_standin_of(ans, frozenset({"a"}), Pl()) == (False, True, True, False)         # without b the twin cross holds no original
    assert W.via_standin_of(None, frozenset({"a"}), Pl()) == ()
    # read_via_standin: every state's seed outside the crosses the same order reads without the stand-ins
    assert W.read_via_standin_of(ans, ("o1", "t1")) == (False, True, False, False)
    assert W.read_via_standin_of(ans, ("o1",)) == (False, True, True, False)                  # a cross that holds an original and was read only through the tie-break
    assert W.read_via_standin_of(ans, ()) == (True, True, True, False)
    assert W.read_via_standin_of(ans, None) == (False, False, False, False) and W.read_via_standin_of(None, ("o1",)) == ()


RV_CASES = [("日本海の東京タワーは何ですか", n) for n in range(1, 7)] + [("東京と日本海は何ですか", n) for n in range(1, 7)] + [(q, n) for q in UNK for n in (1, 2, 3, 4, 6)]


def test_read_via_standin_is_the_exact_diff_of_the_read_sets(idx, space, wi, ctx_):
    """L-811 (review fix 2): the entries of a cross / window that holds an ORIGINAL unit but was read only because the stand-ins decided the tie under the cap are marked
    `read_via_standin` (not `via_standin`).  The mark is the diff of two real plans: the one with the stand-ins and the one the SAME ordering makes without them."""
    import dataclasses
    ix, _ = ctx_
    flat_only = win_only = 0
    for q, n in RV_CASES:
        gi = W.intake(space, q, ix)
        oo_gi = dataclasses.replace(gi, words=(), standins=())
        c = A.ask(idx, q, nodes=n, grammar="on", grammar_intake=gi)
        oo = A.ask(idx, q, nodes=n, grammar="on", grammar_intake=oo_gi)            # the order alone: the run the ticket's "order-only" column is
        o = c.outcome("RUN")
        assert o.result.plan.order_only_read == (oo.outcome("RUN").result.plan.read if gi.standins else None), (q, n)      # the diff's second term IS that run's read set
        assert oo.outcome("RUN").result.plan.order_only_read is None and not any(oo.outcome("RUN").read_via_standin)
        ro_set = set(oo.outcome("RUN").result.plan.read)
        assert len(o.read_via_standin) == len(o.via_standin) == len(o.entries)
        for e, v, r in zip(o.entries, o.via_standin, o.read_via_standin):
            seeds = {o.answer.states[si].ref.seed for a in e.arrangements for si in a.origins}
            assert r == (bool(seeds) and not (seeds & ro_set)), (q, n, e.words)       # exact, no heuristic
            assert (not v) or r                                                       # a cross with no original unit is no candidate without the stand-ins
        flat_only += sum(1 for v, r in zip(o.via_standin, o.read_via_standin) if r and not v)
        for t in ("WORD", "CHAR"):
            assert not any(c.outcome(t).read_via_standin) and len(c.outcome(t).read_via_standin) == len(c.outcome(t).entries)
        fa = F.ask_flat(wi, q, nodes=n, members="representative", grammar="on", grammar_intake=gi)
        fo = F.ask_flat(wi, q, nodes=n, members="representative", grammar="on", grammar_intake=oo_gi)
        wset = set(fo.plan.read)
        for e in fa.entries:
            assert e["read_via_standin"] == (e["window"]["n"] not in wset), (q, n)
            win_only += e["read_via_standin"] and not e["via_standin"]
        assert all(e["read_via_standin"] is False for e in fo.entries)
    assert flat_only and win_only, "the toy never produced an entry read through the tie-break only: the mark would be untested"
    # grammar off: nothing named
    assert "read_via_standin" not in A.ask(idx, RV_CASES[0][0], nodes=1).to_bytes().decode("utf-8")
    # no cap: the plan without the stand-ins is the plan of the run without them, too (the stand-in-only crosses are the whole difference)
    q = "東京都庁の首都は何ですか"
    gi = W.intake(space, q, ix)
    full = A.ask(idx, q, nodes=1000, grammar="on", grammar_intake=gi).outcome("RUN").result.plan
    oo_full = A.ask(idx, q, nodes=1000, grammar="on", grammar_intake=dataclasses.replace(gi, words=(), standins=())).outcome("RUN").result.plan
    assert full.order_only_read == oo_full.read and set(full.read) > set(oo_full.read)


def test_the_two_marks_in_the_combined_list(idx, wi, space, ctx_):
    """The exact example of the review: 日本海の東京タワー at one cross -- the cross of 東京 holds the original 東京タワー and the stand-in 日本, the order alone would read 東京タワー."""
    ix, _ = ctx_
    q = "日本海の東京タワーは何ですか"
    c = CB.ask_combined(idx, q, nodes=1, windows=wi, assembly=False, grammar="on")
    a = c.answer_obj()
    (e,) = [x for x in a["entries"] if x["origins"] == ["flat/RUN"]]
    (m,) = e["members"]
    assert m["via_standin"] is False and m["read_via_standin"] is True
    assert e["marks"] == ["read_via_standin"]                                          # holds an original unit (not via_standin), read only through the tie-break
    assert "【代役の並びで読んだ十字・窓】" in CB.format_text(c)
    for x in a["entries"]:
        ms = [mm for mm in x["members"] if mm["origin"].startswith("flat/") or mm["origin"].startswith("window/")]
        for mm in ms:
            if mm["origin"].startswith("flat/"):
                assert (not mm["via_standin"]) or mm["read_via_standin"]            # flat only: a window entry can be via_standin through a member that holds only a stand-in in a window both orders read
        assert ("read_via_standin" in x["marks"]) == all(mm.get("read_via_standin") is True for mm in x["members"])
    # an entry whose members are all via_standin shows both
    both = CB.combine("q", [CB.Source("flat", CB.CHOICE, (CB.Cand("flat/RUN", ("a", "b"), detail={"via_standin": True, "read_via_standin": True}),
                                                          CB.Cand("flat/RUN", ("c",), detail={"via_standin": False, "read_via_standin": True})), (), {}, {}, {})])
    assert [x.marks for x in both.entries] == [("via_standin", "read_via_standin"), ("read_via_standin",)]


def test_the_flat_answer_reports_the_form_and_the_standins(idx):
    b = A.ask(idx, "東京都庁の人口は何ですか", effort=EFFORT, grammar="on")
    a = b.answer_obj()
    assert a["grammar_form"]["form"] == "predicate" and a["grammar_form"]["standin_units"] == 2
    (s,) = a["standins"]
    assert s["word"] == "東京都庁" and s["units"] == ["東京", "東京タワー"] and s["provenance"] == "stand-in" and s["chance"].startswith("2/")
    assert all("via_standin" in e for e in a["entries"]) and a["read"]["order"] == "qcount+grammar"
    th = b.thought_obj()
    assert th["grammar"]["standins"][0]["unit_parts"][0][0] == "東京" and th["grammar"]["stem"] == "whole_word"
    assert th["tiers"]["RUN"]["cycle"]["standins"] == ["東京", "東京タワー"] and th["tiers"]["RUN"]["cycle"]["read"]["grammar_order"]
    assert "standins" not in th["tiers"]["WORD"]["cycle"]
    txt = A.format_text(b)
    assert "文法層" in txt and "東京都庁: 2/" in txt
    with pytest.raises(ValueError):
        A.ask(idx, "東京は何ですか", effort=EFFORT, grammar="maybe")
    with pytest.raises(ValueError):
        A.ask(idx, "東京は何ですか", effort=EFFORT, grammar="on", structure="slide")


# ---------------------------------------------------------------------------------------------------------------------------------
# Part 4: windows and layers
# ---------------------------------------------------------------------------------------------------------------------------------
def test_windows_that_hold_only_standins_are_read_after_the_others_and_marked(wi, space, ctx_):
    ix, _ = ctx_
    seen = False
    for q in UNK + KNOWN:
        gi = W.intake(space, q, ix)
        off = F.ask_flat(wi, q, nodes=100, members="representative")
        on = F.ask_flat(wi, q, nodes=100, members="representative", grammar="on", grammar_intake=gi)
        if not gi.standins:
            assert on.plan.candidates == off.plan.candidates and on.plan.read == off.plan.read
            assert [e["words"] for e in on.entries] == [e["words"] for e in off.entries]
            continue
        it = on.intake
        assert it.standin_set == frozenset(gi.standins) and it.qset == off.intake.qset and it.units == gi.run_units
        assert it.ctx.standins == gi.standins and it.ctx.energy_units == off.intake.ctx.energy_units
        assert set(off.plan.read) <= set(on.plan.read) and on.plan.candidates >= off.plan.candidates
        held = {w.n: Q.holds(w, it, "seats", "on") for w in wi.windows}
        keys = [held[n] for n in on.plan.read]
        assert keys == sorted(keys, reverse=True)                                # (originals held, stand-ins held), more first
        extra = [n for n in on.plan.read if n not in set(off.plan.read)]
        assert all(held[n][0] == 0 and held[n][1] > 0 for n in extra)
        seen = seen or bool(extra)
        old = {tuple(e["words"]) for e in off.entries}
        for e in on.entries:
            win = wi.by_n[e["window"]["n"]]
            assert e["via_standin"] == all(not (win.member_units(m) & it.qset) for m in e["origin_members"])
            if tuple(e["words"]) not in old:
                assert e["via_standin"] is True
        assert on.answer_obj()["standins"][0]["word"] == gi.words[0].word and on.config["grammar"] == "on"
        # the order alone (the intake with its stand-ins dropped): no window is added, no stand-in is a unit of the query
        import dataclasses
        oo = F.ask_flat(wi, q, nodes=100, members="representative", grammar="on", grammar_intake=dataclasses.replace(gi, words=(), standins=()))
        assert oo.plan.candidates == off.plan.candidates and oo.intake.standin_set == frozenset() and oo.intake.units == gi.units
        assert [e["words"] for e in oo.entries] == [e["words"] for e in off.entries] or oo.plan.read != off.plan.read     # same windows read: same entries
    assert seen


def _force_layers(monkeypatch):
    """The toy loses no stability by itself at these caps: name the layers' trigger (the rest of run_layers is the real code)."""
    orig = M.find_triggers
    monkeypatch.setattr(M, "find_triggers", lambda store, res: dict(orig(store, res), any=True))


def test_the_layers_keep_the_standins_and_the_read_order_in_their_re_asks(idx, space, ctx_, monkeypatch):
    """L-807 / L-813: feedback "down" really re-asks (a spy sees it), every re-ask carries the mark AND the same read hook as layer 0, so originals-first holds there too."""
    ix, recs = ctx_
    q = "東京都庁の人口は何ですか"
    gi = W.intake(space, q, ix)
    c0 = A.ask(idx, q, nodes=2, grammar="on", grammar_intake=gi)
    _force_layers(monkeypatch)
    asked = []
    orig_ask_tier = cy.ask_tier

    def spy(ts, question, store, **kw):
        r = orig_ask_tier(ts, question, store, **kw)
        asked.append((ts.name, kw.get("units"), kw.get("standins"), kw.get("grammar"), r.plan))
        return r

    monkeypatch.setattr(cy, "ask_tier", spy)
    opts = M.LayerOptions(variants=("A",), granularity="compress", feedback="down", candidate="stable-seats-path", bounds=M.bounds_for(None, 2))
    kw = W.reask_kw(gi, [o.tier for o in c0.outcomes], recs)
    assert set(kw) == {"RUN", "WORD", "CHAR"} and "units" not in kw["RUN"] and kw["RUN"]["standins"] == gi.standins and "standins" not in kw["WORD"]
    lc = M.ask_layered(idx, q, options=opts, view="all", nodes=2, base=c0, tier_kw=kw)
    assert lc.base is c0
    runs = [a for a in asked if a[0] == "RUN"]
    assert runs, "feedback 'down' made no re-ask: the test would check nothing"
    for t, units, marks, hook, plan in asked:
        assert hook is not None and hook.tier == t and hook.slot == gi.slot       # the same hook as layer 0's, per tier
        assert plan.grammar is not None                                           # and the read order under the cap is the count-first one
        if t == "RUN":
            assert marks == gi.standins and set(gi.standins) <= set(units)
        else:
            assert marks is None
    # the gap before L-813: without the hook the re-ask files a stand-in seed under T7b's `query_unit` group (E_Q order only)
    asked.clear()
    M.ask_layered(idx, q, options=opts, view="all", nodes=2, base=c0, tier_kw={"RUN": {"standins": gi.standins}})
    assert [a for a in asked if a[0] == "RUN"] and all(a[3] is None and a[4].grammar is None for a in asked if a[0] == "RUN")


def test_layer1_bundles_are_the_read_crosses_and_not_every_standin(idx, space, ctx_, monkeypatch):
    """L-810 (review fix 1): layer 1 is built from plan.read + the ORIGINAL query units + the answer units.  A stand-in whose cross was not read under the cap and that is not in
    the answer is no bundle (before: every stand-in of ctx.query was, up to 431 of them)."""
    ix, recs = ctx_
    q = "東京都庁はどこですか"                                   # only unknown word: the stand-ins 東京 and 東京タワー; no original unit, no answer
    gi = W.intake(space, q, ix)
    assert gi.units == ("東京都庁",) and gi.standins == ("東京", "東京タワー")
    _force_layers(monkeypatch)
    RUN = idx.space.tiers["RUN"]
    seen = []
    orig_l1 = M.LayerStack.layer1

    def spy(self, granularity, seeds, bounds):
        lay = orig_l1(self, granularity, seeds, bounds)
        if self.base is RUN:
            seen.append((frozenset(seeds), frozenset(lay.words)))
        return lay
    monkeypatch.setattr(M.LayerStack, "layer1", spy)
    opts = M.LayerOptions(variants=("A",), granularity="compress", feedback="none", candidate="stable-seats-path", bounds=M.bounds_for(None, 1))
    for n, read, expect in ((1, ("東京",), {"東京"}), (2, ("東京", "東京タワー"), {"東京", "東京タワー"})):
        seen.clear()
        c0 = A.ask(idx, q, nodes=n, grammar="on", grammar_intake=gi)
        r0 = c0.outcome("RUN")
        assert r0.result.plan.read == read and r0.answer is None
        opts = M.LayerOptions(variants=("A",), granularity="compress", feedback="none", candidate="stable-seats-path", bounds=M.bounds_for(None, n))
        lc = M.ask_layered(idx, q, options=opts, view="all", nodes=n, base=c0, tier_kw=W.reask_kw(gi, [o.tier for o in c0.outcomes], recs))
        (tl,) = [t for t in lc.layers if t.tier == "RUN"]
        assert tl.triggered
        assert seen, "no layer 1 was built"
        seeds, words = seen[0]
        assert seeds == frozenset(expect)                                       # the SET: the crosses read (+ the original query units, none here), nothing else
        assert words == frozenset(M.bundle_id(1, u) for u in expect)
        assert tl.choice["bundles_if_compress"] == len(set(read) | set(gi.units))      # n_cmp: the read crosses + the original query units (the unknown word itself is one; no stand-in)
        if n == 1:
            assert M.bundle_id(1, "東京タワー") not in words                      # the stand-in whose cross was NOT read
    # the original query units are still seeds (a question with a known word): the set is read crosses + originals + answer, minus nothing but the unread stand-ins
    q2 = "東京都庁の首都は何ですか"
    gi2 = W.intake(space, q2, ix)
    seen.clear()
    c2 = A.ask(idx, q2, nodes=2, grammar="on", grammar_intake=gi2)
    r2 = c2.outcome("RUN").result
    M.ask_layered(idx, q2, options=opts, view="all", nodes=2, base=c2, tier_kw=W.reask_kw(gi2, [o.tier for o in c2.outcomes], recs))
    ans2 = set(M._answer_units(c2.outcome("RUN").answer))
    assert seen[0][0] == frozenset(set(r2.plan.read) | {"首都"} | ans2)


def test_the_layers_do_not_carry_the_standins_up_as_question_units(idx, space, ctx_):
    ix, _ = ctx_
    opts = M.LayerOptions(variants=("A",), granularity="compress", feedback="none", candidate="stable-seats-path", bounds=M.bounds_for(EFFORT, None))
    q = "東京都庁はどこですか"                                   # the only original unit is unknown: nothing of the question is in the layers
    gi = W.intake(space, q, ix)
    assert gi.standins == ("東京", "東京タワー")
    c0 = A.ask(idx, q, effort=EFFORT, grammar="on", grammar_intake=gi)
    lc = M.ask_layered(idx, q, options=opts, view="all", effort=EFFORT, base=c0, tier_kw={"RUN": {"standins": gi.standins}})
    runs = [r for tl in lc.layers if tl.tier == "RUN" for r in tl.runs]
    assert runs and all(r.query_units == () for r in runs)       # before L-807 the stand-ins 東京 / 東京タワー stood here as question bundles
    # a question with original units: those are the question bundles, in question order, and no stand-in is among them unless layer 0's answer has it
    q2 = "東京都庁の首都は何ですか"
    gi2 = W.intake(space, q2, ix)
    c2 = A.ask(idx, q2, effort=EFFORT, grammar="on", grammar_intake=gi2)
    l2 = M.ask_layered(idx, q2, options=opts, view="all", effort=EFFORT, base=c2, tier_kw={"RUN": {"standins": gi2.standins}})
    r2 = [r for tl in l2.layers if tl.tier == "RUN" for r in tl.runs]
    assert r2 and r2[0].query_units[0] == M.bundle_id(1, "首都")
    # without the grammar the layers are what they were
    c0n = A.ask(idx, q2, effort=EFFORT)
    assert c0n.outcome("RUN").result.ctx.standins == ()


# ---------------------------------------------------------------------------------------------------------------------------------
# Part 5: the combined list and the entrance
# ---------------------------------------------------------------------------------------------------------------------------------
def test_combined_with_grammar_on(idx, wi, ctx_):
    ix, _ = ctx_
    q = "東京都庁の人口は何ですか"
    c = CB.ask_combined(idx, q, effort=EFFORT, windows=wi, assembly=False, grammar="on")
    a = c.answer_obj()
    h0 = a["header"][0]
    assert h0 == {"source": "grammar", "form": "predicate", "slot": None, "predicate": "人口", "standins": 2, "unknown_words": ["東京都庁"]}
    assert a["header"][1]["source"].startswith("flat/")
    assert a["grammar_form"]["form"] == "predicate" and a["standins"][0]["added"] == ["東京", "東京タワー"]
    assert c.config["grammar"]["on"] and c.thought_obj()["grammar"]["stem"] == "whole_word"
    for e in a["entries"]:
        for m in e["members"]:
            if m["origin"].startswith("flat/") or m["origin"].startswith("window/"):
                assert m["via_standin"] in (True, False)
            else:
                assert "via_standin" not in m                                   # the layers' entries are not marked per entry (open point)
        assert ("via_standin" in e["marks"]) == all(m.get("via_standin") is True for m in e["members"])
    txt = CB.format_text(c)
    assert "grammar: 形 predicate" in txt and "東京都庁" in txt
    # the shared intake is the same as the one the call makes
    gi = W.intake(idx.space, q, ix)
    c2 = CB.ask_combined(idx, q, effort=EFFORT, windows=wi, assembly=False, grammar="on", grammar_intake=gi)
    assert c2.to_bytes() == c.to_bytes()
    # a question with no unknown word: a grammar row without stand-ins
    k = CB.ask_combined(idx, "猫は何を食べますか", effort=EFFORT, windows=wi, assembly=False, grammar="on")
    assert k.answer_obj()["header"][0]["standins"] == 0 and k.answer_obj()["header"][0]["slot"] == "を" and k.answer_obj()["standins"] == []
    with pytest.raises(ValueError):
        CB.ask_combined(idx, q, effort=EFFORT, windows=wi, grammar="x")


def test_a_marked_entry_is_marked_in_the_text_and_the_list():
    flat = CB.Source("flat", CB.CHOICE, (CB.Cand("flat/RUN", ("a", "b"), detail={"via_standin": True}), CB.Cand("flat/RUN", ("c",), detail={"via_standin": False}),
                                          CB.Cand("flat/WORD", ("d",), detail={"via_standin": False})), (), {}, {}, {})
    wp = CB.Source("window/plain", CB.CHOICE, (CB.Cand("window/plain", ("a", "b"), detail={"via_standin": True}),), (), {}, {}, {})
    c = CB.combine("q", [flat, wp], merge="word_set", grammar={"form": {}, "standins": [], "header": {"source": "grammar", "form": "plain", "slot": None, "predicate": None,
                                                                                                    "standins": 1, "unknown_words": ["x"]},
                                                                 "full": {}})
    ents = {e.words: e for e in c.entries}
    assert ents[("a", "b")].marks == (CB.MARK_STANDIN,) and ents[("c",)].marks == () and ents[("d",)].marks == ()      # a merged entry is marked when every member is
    mixed = CB.combine("q", [CB.Source("flat", CB.CHOICE, (CB.Cand("flat/RUN", ("a",), detail={"via_standin": True}),), (), {}, {}, {}),
                             CB.Source("window/plain", CB.CHOICE, (CB.Cand("window/plain", ("a",), detail={"via_standin": False}),), (), {}, {}, {})], merge="word_set")
    assert mixed.entries[0].marks == ()
    nogrammar = CB.combine("q", [CB.Source("flat", CB.CHOICE, (CB.Cand("flat/RUN", ("a",)),), (), {}, {}, {})])
    assert nogrammar.entries[0].marks == () and nogrammar.header()[0]["source"] == "flat/RUN"                # no grammar key: no row, no mark


def cli(args, seed="0"):
    env = dict(os.environ, PYTHONHASHSEED=seed, PYTHONPATH=ROOT)
    return subprocess.run([PY, "-m", "verantyx.cli", "line3"] + args, capture_output=True, text=True, env=env, cwd=ROOT, timeout=900, stdin=subprocess.DEVNULL)


def test_cli_grammar_switch(tmp_path, data_file):
    cache = str(tmp_path / "c")
    b = cli(["build", "--structure", "combined", "--data", data_file, "--cache", cache, "--level", "low"])
    assert b.returncode == 0, b.stderr[-2000:]
    base = ["ask", "--data", data_file, "--cache", cache, "--level", "low", "--question", "東京都庁の人口は何ですか", "--effort", EFFORT]
    off = cli(base + ["--structure", "combined", "--assembly", "off", "--format", "json"])
    dflt = cli(base + ["--structure", "combined", "--assembly", "off", "--grammar", "off", "--format", "json"])
    assert off.returncode == 0 and off.stdout == dflt.stdout and "grammar" not in json.loads(off.stdout)["answer"]["header"][0]["source"]
    on = [cli(base + ["--structure", "combined", "--assembly", "off", "--grammar", "on", "--format", "json", "--show-thought"], s) for s in ("0", "1", "12345")]
    assert all(r.returncode == 0 for r in on), on[0].stderr[-2000:]
    assert on[0].stdout == on[1].stdout == on[2].stdout
    obj = json.loads(on[0].stdout)
    assert obj["answer"]["header"][0]["source"] == "grammar" and obj["answer"]["standins"][0]["word"] == "東京都庁"
    txt = cli(base + ["--structure", "combined", "--assembly", "off", "--grammar", "on"])
    assert txt.returncode == 0 and "grammar:" in txt.stdout
    flat = cli(base + ["--layers", "off", "--grammar", "on", "--format", "json"])
    assert flat.returncode == 0 and json.loads(flat.stdout)["answer"]["grammar_form"]["form"] == "predicate"
    layered = cli(base + ["--grammar", "on"])
    assert layered.returncode == 0 and "文法層" in layered.stdout
    flat_off = cli(base + ["--layers", "off", "--format", "json"])
    assert "grammar_form" not in json.loads(flat_off.stdout)["answer"]
    sl = cli(base + ["--structure", "slide", "--grammar", "on"])
    assert sl.returncode == 2 and "grammar" in sl.stderr


# ---------------------------------------------------------------------------------------------------------------------------------
# Part 6: defaults and bytes
# ---------------------------------------------------------------------------------------------------------------------------------
def test_grammar_off_is_byte_identical_and_names_nothing(idx, wi):
    for q in TF.QUESTIONS[:6] + UNK[:2]:
        d = A.ask(idx, q, effort=EFFORT)
        o = A.ask(idx, q, effort=EFFORT, grammar="off")
        assert d.to_bytes() == o.to_bytes() and o.grammar is None
        s = d.to_bytes().decode("utf-8")
        for key in ("grammar_order", "via_standin", "standins", "grammar_form", "qcount+grammar", "order_only_read", "stem_whole_word"):
            assert key not in s
        dc = CB.ask_combined(idx, q, effort=EFFORT, windows=wi, assembly=False)
        oc = CB.ask_combined(idx, q, effort=EFFORT, windows=wi, assembly=False, grammar="off")
        assert dc.to_bytes() == oc.to_bytes()
        sc = dc.to_bytes().decode("utf-8")
        for key in ("via_standin", "standins", "grammar_form", '"grammar"'):
            assert key not in sc
    fa = F.ask_flat(wi, UNK[0], effort=EFFORT, members="representative")
    assert fa.to_bytes() == F.ask_flat(wi, UNK[0], effort=EFFORT, members="representative", grammar="off").to_bytes()
    assert Q.intake(wi, UNK[0]).standin_set == frozenset() and Q.intake(wi, UNK[0]).grammar is None
    assert cy.make_context(("a",)).standins == ()


def test_classify_form_is_one_definition(wi, space, ctx_):
    ix, _ = ctx_
    for q in UNK + TF.QUESTIONS:
        r = Gr.read_question(q, space, ix)
        assert Q.classify_form(r) == W.classify_form(r) == Q.intake(wi, q).form == W.intake(space, q, ix).form


def test_bytes_do_not_depend_on_the_hash_seed(tmp_path):
    script = tmp_path / "run.py"
    script.write_text(
        "import hashlib, sys\n"
        "sys.path.insert(0, %r)\n"
        "from tests.line3 import test_slide_flat as T\n"
        "from verantyx.line3 import ask as A, combined as CB, slide_query as Q, space as sp, wiring as W\n"
        "rows = T.toy_rows(); space = sp.build_space(rows)\n"
        "wi = Q.WindowIndex.from_space(space, None, rows=rows, level=T.LEVEL)\n"
        "idx = A.Index(space, level=T.LEVEL)\n"
        "h = hashlib.sha256()\n"
        "for q in T.QUESTIONS + ['東京都庁の人口は何ですか', '東京都庁はどこですか', '東京の東京都庁は何ですか']:\n"
        "    h.update(A.ask(idx, q, effort='fast', grammar='on').to_bytes())\n"
        "    h.update(A.ask(idx, q, nodes=3, grammar='on').to_bytes())\n"
        "    h.update(CB.ask_combined(idx, q, effort='fast', windows=wi, assembly=False, grammar='on').to_bytes())\n"
        "    h.update(CB.ask_combined(idx, q, effort='fast', windows=wi, assembly=True, grammar='on', window_evidence='plain').to_bytes())\n"
        "    h.update(W.intake(space, q).reading.to_bytes())\n"
        "print(h.hexdigest())\n" % ROOT)
    out = set()
    for seed in ("0", "1", "12345"):
        env = dict(os.environ, PYTHONHASHSEED=seed, PYTHONPATH=ROOT)
        r = subprocess.run([PY, str(script)], capture_output=True, text=True, env=env, cwd=ROOT, timeout=900)
        assert r.returncode == 0, r.stderr[-2000:]
        out.add(r.stdout.strip())
    assert len(out) == 1 and len(next(iter(out))) == 64


def test_no_float_no_division_and_the_import_boundary():
    for name in ("wiring",):
        tree = ast.parse(open(os.path.join(ROOT, "verantyx/line3", name + ".py"), encoding="utf-8").read())
        for n in ast.walk(tree):
            assert not (isinstance(n, ast.Constant) and isinstance(n.value, float)), n.lineno
            assert not (isinstance(n, ast.BinOp) and isinstance(n.op, (ast.Div, ast.Pow))), n.lineno
            assert not (isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id in ("float", "round")), n.lineno
        mods = [n.module or "" for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)] + \
               [a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names] + \
               [a.name for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) for a in n.names]
        for bad in ("ask", "slide_query", "slide_flat", "combined", "matryoshka", "cli", "carry", "placement", "readout"):
            assert not any(m.split(".")[-1] == bad for m in mods), bad           # wiring depends on cycle / grammar / space only
    # the question path imports wiring, never the grammar module itself (tests/line3/test_grammar.py keeps that boundary)
    for name in ("ask", "cycle", "matryoshka", "readout", "placement"):
        tree = ast.parse(open(os.path.join(ROOT, "verantyx/line3", name + ".py"), encoding="utf-8").read())
        mods = [n.module or "" for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)]
        names = [a.name for n in ast.walk(tree) if isinstance(n, (ast.Import, ast.ImportFrom)) for a in n.names]
        assert not any(m.endswith("grammar") for m in mods) and "grammar" not in names


def test_the_marks_of_equal_entries_are_by_position_not_by_value(idx):
    """L-815 (review fix 9): `answer_obj` took the mark of an entry from `entries.index(e)`, which finds the FIRST equal entry; two equal entries must keep their own marks."""
    from dataclasses import replace
    c = A.ask(idx, "東京都庁の首都は何ですか", nodes=2, grammar="on")
    o = c.outcome("RUN")
    e = o.answer.entries[0]
    o2 = replace(o, answer=replace(o.answer, entries=(e, e)), via_standin=(False, True), read_via_standin=(True, False))
    c2 = replace(c, outcomes=tuple(o2 if x.tier == "RUN" else x for x in c.outcomes),
                 entries=tuple(te for te in c.entries if te[0] != "RUN") + (("RUN", e), ("RUN", e)))
    ents = [x for x in c2.answer_obj()["entries"] if x["tier"] == "RUN"]
    assert [(x["via_standin"], x["read_via_standin"]) for x in ents] == [(False, True), (True, False)]
