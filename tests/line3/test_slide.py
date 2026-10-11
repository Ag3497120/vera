"""G3-a / G3-b tests (L-520..): the sliding windows, the exact counts of their three axes, the spec and its sha, and the
reproduction of the designer's reach probe (docs/LINE3_G3_SLIDING_PACKS.md 2.5, experiments/line3/g3/reach_windows.py).

Part 1 (toy corpus, hand counts): 3 articles (3, 2 and 1 sentences) -- the window list, the lone windows and the
one-sentence article; x / y / z counted by hand on named sentences; every count checked against an independent brute-force
reference written here; every source traced to the surface; the Space is not changed.
Part 2 (spec): the sha changes when any axis definition, the window rule, the corpus or the foundation changes; the P7
ladder in exact Fractions.
Part 3: byte identity under PYTHONHASHSEED 0 / 1 / 12345, no float.
Part 4 (fulllead, bank2): windows 592 / 2-sentence windows 292, RUN window median 15, and every number of design 2.5."""
import ast
import dataclasses
import hashlib
import json
import os
import subprocess
import sys
from fractions import Fraction

import pytest

from verantyx.line3 import slide as SL
from verantyx.line3 import space as sp

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
G3 = os.path.join(ROOT, "experiments/line3/g3")

TOY = [
    ("東京", "東京は日本の首都である。"),      # sid 0, 東京#0
    ("東京", "京は東京である。"),              # sid 1, 東京#1
    ("東京", "東京は日本の都市である。"),      # sid 2, 東京#2
    ("ハッシュ", "ハッシュ表は表である。"),    # sid 3, ハッシュ#0   (表 twice)
    ("ハッシュ", "ハッシュ表ともいう。"),      # sid 4, ハッシュ#1   (RUN ともいう contains WORD いう)
    ("京都", "京都は古い都である。"),          # sid 5, 京都#0       (a one-sentence article)
]


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
def toy(space, rows):
    return SL.Slide(space, rows=rows)


def W(toy, n):
    return next(w for w in toy.sequence() if w.n == n)


# ==== part 1: articles and the window lists ===================================================================================
def test_articles_exact(toy):
    assert [(a.title, a.sids, a.idx) for a in toy.articles] == [
        ("東京", (0, 1, 2), (0, 1, 2)), ("ハッシュ", (3, 4), (0, 1)), ("京都", (5,), (0,))]


def test_pairs_are_the_adjacent_sentences_inside_one_article(toy):
    assert [w.sids for w in toy.pairs()] == [(0, 1), (1, 2), (3, 4)]
    assert [w.n for w in toy.pairs()] == [0, 1, 3]
    assert [w.idx for w in toy.pairs()] == [(0, 1), (1, 2), (0, 1)]
    assert [w.title for w in toy.pairs()] == ["東京", "東京", "ハッシュ"]
    assert (2, 3) not in [w.sids for w in toy.pairs()]          # no pair across the article end (OP-G3-2)
    assert (4, 5) not in [w.sids for w in toy.pairs()]
    assert toy.windows is not None and [w.sids for w in toy.windows()] == [w.sids for w in toy.pairs()]


def test_the_last_sentence_forms_no_pair_and_the_one_sentence_article_is_recorded(toy):
    assert [w.sids for w in toy.singletons()] == [(5,)]                       # recorded
    assert [w.sids for w in toy.lasts()] == [(2,), (4,), (5,)]                # last sentence of every article
    assert all(len(w.sids) == 1 for w in toy.lasts() + toy.singletons())


def test_lone_rule_default_is_last_and_the_sequence_is_in_W_N_order(space, rows):
    t = SL.Slide(space, rows=rows)
    assert t.spec.window.lone == "last"
    assert [(w.n, w.sids) for w in t.sequence()] == [(0, (0, 1)), (1, (1, 2)), (2, (2,)), (3, (3, 4)), (4, (4,)), (5, (5,))]
    none = SL.Slide(space, SL.default_spec(space, lone="none"), rows)
    assert [w.sids for w in none.sequence()] == [(0, 1), (1, 2), (3, 4)] and none.lone() == ()
    single = SL.Slide(space, SL.default_spec(space, lone="singleton"), rows)
    assert [w.sids for w in single.sequence()] == [(0, 1), (1, 2), (3, 4), (5,)]


def test_article_rule_refuses_instead_of_guessing(space):
    def mk(srcs, extra=None):
        rs = [{"sent": "東京は日本の首都である。", "source": s} for s in srcs]
        sp_ = sp.build_space(rs)
        return sp_, (rs if extra is None else extra)
    with pytest.raises(ValueError):                                  # a source without #i
        SL.articles(sp.build_space([{"sent": "東京は日本の首都である。", "source": "t"}]))
    with pytest.raises(ValueError):                                  # an article that comes back
        SL.articles(mk(["A#0", "B#0", "A#1"])[0])
    with pytest.raises(ValueError):                                  # a sentence number that skips
        SL.articles(mk(["A#0", "A#2"])[0])
    with pytest.raises(ValueError):                                  # a title field that disagrees with the source
        s_, r_ = mk(["A#0", "A#1"])
        r_ = [dict(r_[0], title="A"), dict(r_[1], title="B")]
        SL.articles(s_, r_)
    s_, r_ = mk(["A#0", "A#1"])
    with pytest.raises(ValueError):                                  # rows that are not the space's
        SL.articles(s_, r_[:1])


# ==== the pack and its provenance ===============================================================================================
def test_pack_holds_every_occurrence_of_the_three_tiers_of_both_sentences(toy):
    w = W(toy, 3)                                                    # (3, 4)
    pack = toy.pack(w)
    for t in SL.TIERS:
        n = sum(len(toy.space.tiers[t].sentence_units[s]) for s in w.sids)
        assert sum(1 for o in pack if o.tier == t) == n
    assert [(o.sid, SL.TIER_RANK[o.tier], o.k) for o in pack] == sorted((o.sid, SL.TIER_RANK[o.tier], o.k) for o in pack)
    reps = [o for o in pack if o.tier == "RUN" and o.sid == 3 and o.unit == "表"]
    assert [(o.k, o.start, o.end) for o in reps] == [(1, 4, 5), (2, 6, 7)]       # a repeated unit keeps both places
    for o in pack:                                                   # provenance: the span shows the unit
        assert toy.spans.text(o.sid)[o.start:o.end] == o.unit
        assert toy.space.tiers[o.tier].sentence_units[o.sid][o.k] == o.unit


# ==== part 1b: the three axes by hand ===========================================================================================
def test_x_word_order_by_hand_first_occurrence(toy):
    c = toy.counts(W(toy, 0), "window")                              # (0, 1)
    # 京 and 東 (CHAR): sentence 0 "東京..." 東 (0,1) then 京 (1,2); sentence 1 "京は東京" first 京 (0,1) then 東 (2,3)
    assert c.x[("CHAR", "京", "東")] == (((1, 0, 1, 2, 3),), ((0, 1, 2, 0, 1),))
    assert c.n_x("CHAR", "京", "東") == 2 and c.before_x("CHAR", "京", "東") == 1 and c.after_x("CHAR", "京", "東") == 1
    # the other direction is the mirror
    assert c.x[("CHAR", "東", "京")] == (((0, 0, 1, 1, 2),), ((1, 2, 3, 0, 1),))
    # the second 京 of sentence 1 (3,4) is not used: x uses the first occurrence (p_pair)
    assert all(s[0] != 1 or (s[1], s[2]) != (3, 4) for k, (b, a) in c.x.items() for s in b + a if k[1] == "京" and k[0] == "CHAR")
    # WORD: 東京 comes before 日本 and before 首都 in sentence 0; 日本 before 首都
    assert c.x[("WORD", "東京", "日本")] == (((0, 0, 2, 3, 5),), ())
    assert c.x[("WORD", "日本", "東京")] == ((), ((0, 3, 5, 0, 2),))
    assert c.before_x("WORD", "日本", "首都") == 1 and c.after_x("WORD", "首都", "日本") == 1
    # no pair of units from different sentences and none across tiers
    assert ("WORD", "日本", "多い") not in c.x and c.n_x("WORD", "日本", "京") == 0
    assert all(k[0] in SL.TIERS for k in c.x)


def test_x_counts_a_unit_that_repeats_by_its_first_place(toy):
    c = toy.counts(W(toy, 3), "window")                              # (3, 4): "ハッシュ表は表である" / "ハッシュ表ともいう"
    # RUN 表 is at k=1 (4,5) and k=2 (6,7) in sentence 3; the pair with ハッシュ uses (4,5)
    assert c.x[("RUN", "ハッシュ", "表")] == (((3, 0, 4, 4, 5), (4, 0, 4, 4, 5)), ())
    assert c.n_x("RUN", "ハッシュ", "表") == 2
    assert ("RUN", "表", "表") not in c.x                            # the same unit is no pair with itself


def test_x_corpus_scope_equals_the_spaces_own_n_pair_and_p_pair(toy):
    c = toy.counts(W(toy, 0), "corpus")
    t = toy.space.tiers["CHAR"]
    assert (c.n_x("CHAR", "京", "東"), c.before_x("CHAR", "京", "東")) == (t.n_pair("京", "東"), t.p_pair("京", "東")) == (3, 1)
    assert c.after_x("CHAR", "京", "東") == 2
    t = toy.space.tiers["WORD"]
    assert (c.n_x("WORD", "東京", "日本"), c.before_x("WORD", "東京", "日本")) == (2, 2)   # sentences 0 and 2
    for tier in SL.TIERS:
        ts = toy.space.tiers[tier]
        for (t_, o, i), (b, a) in c.x.items():
            if t_ == tier:
                assert len(b) + len(a) == ts.n_pair(o, i) and len(b) == ts.p_pair(o, i)


def test_y_granularity_by_hand_any_occurrence_and_equal_spans(toy):
    c = toy.counts(W(toy, 0), "window")                              # (0, 1)
    # RUN 東京 contains CHAR 京 in both sentences; in sentence 1 the FIRST 京 (0,1) is outside 東京 (2,4), the second (3,4) is in
    assert c.y[("RUN", "東京", "CHAR", "京")] == ((0, 0, 2, 1, 2), (1, 2, 4, 3, 4))
    assert c.n_y("RUN", "東京", "CHAR", "京") == 2
    # equal spans are a link (RUN and WORD cut the same string), once per sentence
    assert c.y[("RUN", "東京", "WORD", "東京")] == ((0, 0, 2, 0, 2), (1, 2, 4, 2, 4))
    assert c.y[("RUN", "京", "CHAR", "京")] == ((1, 0, 1, 0, 1),)
    # a span that is only inside another one's: not the same string, still a link; and a miss: RUN 東京 (2,4) does not contain WORD 京 (0,1)
    assert ("RUN", "東京", "WORD", "京") not in c.y and c.n_y("RUN", "東京", "WORD", "京") == 0
    # only coarser -> finer keys; none inside one tier
    assert all(SL.TIER_RANK[k[0]] < SL.TIER_RANK[k[2]] for k in c.y)
    d = toy.counts(W(toy, 3), "window")                              # (3, 4): RUN ともいう (5,9) contains WORD いう (7,9)
    assert d.y[("RUN", "ともいう", "WORD", "いう")] == ((4, 5, 9, 7, 9),)
    assert d.y[("RUN", "ハッシュ", "CHAR", "シ")] == ((3, 0, 4, 2, 3), (4, 0, 4, 2, 3))
    # +y(o, i) / -y(i, o): the same list read from the other end (o is the coarser one)
    assert d.n_y("WORD", "ハッシュ", "CHAR", "ッ") == 2


def test_z_slide_by_hand(toy):
    c = toy.counts(W(toy, 0), "window")                              # (0, 1)
    assert c.z[("WORD", "東京", "WORD", "東京")] == ((0, 1, 0, 2, 2, 4),)     # 東京 in sentence 0, 東京 in sentence 1 (first place 2,4)
    assert c.z[("WORD", "日本", "WORD", "京")] == ((0, 1, 3, 5, 0, 1),)
    assert c.n_z("WORD", "日本", "WORD", "京") == 1
    assert c.n_z("WORD", "京", "WORD", "日本") == 0                   # -z: 京 is not in the first sentence
    assert c.n_z("RUN", "日本", "CHAR", "東") == 1                     # across tiers
    assert c.z_side[("WORD", "東京")] == ("this", "next")
    assert c.z_side[("WORD", "日本")] == ("this",)
    assert c.z_side[("WORD", "京")] == ("next",)
    # the corpus count of the same edge: windows (0,1) and (1,2) both have 東京 then 東京
    k = toy.counts(W(toy, 0), "corpus")
    assert k.z[("WORD", "東京", "WORD", "東京")] == ((0, 1, 0, 2, 2, 4), (1, 2, 2, 4, 0, 2))
    assert k.n_z("WORD", "東京", "WORD", "東京") == 2
    # 日本 is in sentences 0 and 2 but they are not neighbours: no (日本 -> 日本) edge, z reaches no further than N+1
    assert k.n_z("WORD", "日本", "WORD", "日本") == 0
    # a unit that repeats in both sentences makes an edge with itself (3 -> 4: 表)
    d = toy.counts(W(toy, 3), "window")
    assert d.z[("RUN", "表", "RUN", "表")] == ((3, 4, 4, 5, 4, 5),)


def test_a_one_sentence_window_has_no_z_and_its_units_are_this(toy):
    c = toy.counts(W(toy, 5), "window")                              # (5,)
    assert c.z == {} and set(c.z_side.values()) == {("this",)}
    assert c.n_x("WORD", "京都", "古い") == 1 and c.before_x("WORD", "京都", "古い") == 1
    assert toy.counts(W(toy, 2), "corpus").z == {}
    assert toy.pack(W(toy, 5))[0].sid == 5


def test_z_never_crosses_an_article_end(toy):
    pairs = {w.sids for w in toy.pairs()}
    seen = set()
    for w in toy.sequence():
        for scope in SL.SCOPES:
            for srcs in toy.counts(w, scope).z.values():
                for s in srcs:
                    seen.add((s[0], s[1]))
    assert seen <= pairs and seen == pairs                           # (2,3) and (4,5) are never a source


# ---- an independent brute-force reference (no code shared with slide.py except the spans) ---------------------------------
def reference(toy, w, scope):
    space, spans = toy.space, toy.spans
    sids = list(w.sids) if scope == "window" else list(range(space.N))
    pack = {t: set(u for s in w.sids for u in space.tiers[t].sentence_units[s]) for t in SL.TIERS}
    art = {s: a.title for a in toy.articles for s in a.sids}
    x, y, z = {}, {}, {}
    for t in SL.TIERS:
        for s in sids:
            us = space.tiers[t].sentence_units[s]
            sp_ = spans.spans(t, s)
            first = {}
            for k, u in enumerate(us):
                first.setdefault(u, k)
            for o in first:
                for i in first:
                    if o != i and o in pack[t] and i in pack[t]:
                        so, si = sp_[first[o]], sp_[first[i]]
                        b, a = x.setdefault((t, o, i), ([], []))
                        (b if first[o] < first[i] else a).append((s, so[0], so[1], si[0], si[1]))
    for tc, tf in SL.DEFAULT_Y_PAIRS:
        for s in sids:
            uc, uf = space.tiers[tc].sentence_units[s], space.tiers[tf].sentence_units[s]
            sc, sf = spans.spans(tc, s), spans.spans(tf, s)
            done = set()
            for kc, o in enumerate(uc):
                for kf, i in enumerate(uf):
                    if (o, i) in done or o not in pack[tc] or i not in pack[tf]:
                        continue
                    if sc[kc][0] <= sf[kf][0] and sf[kf][1] <= sc[kc][1]:
                        done.add((o, i))
                        y.setdefault((tc, o, tf, i), []).append((s, sc[kc][0], sc[kc][1], sf[kf][0], sf[kf][1]))
    if len(w.sids) == 2:
        a, b = w.sids
        for n in ([a] if scope == "window" else range(space.N - 1)):
            if scope == "corpus" and not (n + 1 < space.N and art[n] == art[n + 1]):
                continue
            for ta in SL.TIERS:
                for tb in SL.TIERS:
                    for u in set(space.tiers[ta].sentence_units[n]) & pack_side(space, ta, a):
                        for v in set(space.tiers[tb].sentence_units[n + 1]) & pack_side(space, tb, b):
                            ku = space.tiers[ta].sentence_units[n].index(u)
                            kv = space.tiers[tb].sentence_units[n + 1].index(v)
                            su, sv = spans.spans(ta, n)[ku], spans.spans(tb, n + 1)[kv]
                            z.setdefault((ta, u, tb, v), []).append((n, n + 1, su[0], su[1], sv[0], sv[1]))
    return ({k: (tuple(sorted(b)), tuple(sorted(a))) for k, (b, a) in x.items() if b or a},
            {k: tuple(sorted(v)) for k, v in y.items()}, {k: tuple(sorted(v)) for k, v in z.items()})


def pack_side(space, t, sid):
    return set(space.tiers[t].sentence_units[sid])


@pytest.mark.parametrize("scope", SL.SCOPES)
def test_counts_equal_an_independent_reference_on_every_window(toy, scope):
    for w in toy.sequence():
        c = toy.counts(w, scope)
        x, y, z = reference(toy, w, scope)
        assert {k: (tuple(sorted(b)), tuple(sorted(a))) for k, (b, a) in c.x.items()} == x, (w, "x")
        assert {k: tuple(sorted(v)) for k, v in c.y.items()} == y, (w, "y")
        assert {k: tuple(sorted(v)) for k, v in c.z.items()} == z, (w, "z")


def test_every_count_is_an_int_and_the_length_of_its_sources(toy):
    for w in toy.sequence():
        c = toy.counts(w, "corpus")
        for (b, a) in c.x.values():
            assert isinstance(len(b) + len(a), int)
            assert all(isinstance(v, int) for s in b + a for v in s)
        for srcs in list(c.y.values()) + list(c.z.values()):
            assert srcs and all(isinstance(v, int) for s in srcs for v in s)


def test_every_source_traces_to_the_surface(toy):
    total = 0
    for w in toy.sequence():
        for scope in SL.SCOPES:
            total += SL.verify_counts(toy, toy.counts(w, scope))
    assert total > 500


def test_verify_counts_rejects_a_wrong_source(toy):
    c = toy.counts(W(toy, 0), "window")
    bad_x = dict(c.x)
    k = ("WORD", "東京", "日本")
    bad_x[k] = (((0, 0, 2, 3, 6),), ())                              # span (3,6) is not 日本
    with pytest.raises(ValueError):
        SL.verify_counts(toy, dataclasses.replace(c, x=bad_x))
    bad_x[k] = (((0, 3, 5, 0, 2),), ())                              # surfaces right, but "before" is false (日本 follows 東京)
    with pytest.raises(ValueError):
        SL.verify_counts(toy, dataclasses.replace(c, x=bad_x))
    bad_y = dict(c.y)
    bad_y[("RUN", "東京", "CHAR", "京")] = ((1, 2, 4, 0, 1),)        # 京 (0,1) is outside 東京 (2,4)
    with pytest.raises(ValueError):
        SL.verify_counts(toy, dataclasses.replace(c, y=bad_y))
    bad_z = dict(c.z)
    bad_z[("WORD", "日本", "WORD", "日本")] = ((0, 2, 3, 5, 3, 5),)  # sentences 0 and 2 are not neighbours
    with pytest.raises(ValueError):
        SL.verify_counts(toy, dataclasses.replace(c, z=bad_z))
    bad_z = dict(c.z)
    bad_z[("WORD", "東京", "WORD", "東京")] = ((1, 2, 2, 4, 0, 2),)  # a real pair, but not this window's
    with pytest.raises(ValueError):
        SL.verify_counts(toy, dataclasses.replace(c, z=bad_z))
    # (review) surfaces and order right, but the cited span is the SECOND 京 of sentence 1 (3,4), not its first (0,1)
    bad_x = dict(c.x)
    bad_x[("CHAR", "京", "東")] = (((1, 3, 4, 2, 3),), ((0, 1, 2, 0, 1),))
    with pytest.raises(ValueError):
        SL.verify_counts(toy, dataclasses.replace(c, x=bad_x))
    d = toy.counts(W(toy, 3), "window")                              # (3, 4): RUN 表 at (4,5) and (6,7) in sentence 3
    bad_z = dict(d.z)
    bad_z[("RUN", "表", "RUN", "表")] = ((3, 4, 6, 7, 4, 5),)
    with pytest.raises(ValueError):
        SL.verify_counts(toy, dataclasses.replace(d, z=bad_z))
    SL.verify_counts(toy, d)


def test_the_space_is_not_changed(space, rows):
    before = space.sha256()
    t = SL.Slide(space, rows=rows)
    for w in t.sequence():
        for scope in SL.SCOPES:
            t.counts(w, scope)
        t.pack(w)
    t.to_bytes()
    assert space.sha256() == before
    assert t.spec.corpus_sha == before


# ==== part 2: the spec ==========================================================================================================
def test_foundation_p7_in_ladder_order_with_the_fibonacci_weights_as_exact_fractions():
    f = SL.p7()
    assert [l for l, _ in f.ladder] == list("はのにでとをが")
    assert [w for _, w in f.ladder] == [Fraction(n, 377) for n in (233, 144, 89, 55, 34, 21, 13)]
    assert all(isinstance(w, Fraction) for _, w in f.ladder)
    assert SL.fibonacci(14) == 377 and [SL.fibonacci(14 - k) for k in range(1, 8)] == [233, 144, 89, 55, 34, 21, 13]
    assert f.centre == "は"
    assert dict(f.arms) == {"+x": "の", "-x": "に", "+y": "で", "-y": "と", "+z": "を", "-z": "が"}
    assert [f.arm_weight(a) for a in SL.ARMS] == [Fraction(n, 377) for n in (144, 89, 55, 34, 21, 13)]
    assert [f.axis_weight(a) for a in SL.AXES] == [Fraction(233, 377), Fraction(89, 377), Fraction(34, 377)]
    d = f.doc()
    assert d["per"] == 377 and [e[2] for e in d["ladder"]] == [233, 144, 89, 55, 34, 21, 13]
    assert d["weights_enter"] == ["edge_flow", "binding", "read_order"]


def test_foundation_refuses_ties_floats_and_a_bad_arm_map():
    lad = SL.p7().ladder
    with pytest.raises(ValueError):                                  # a tie places nothing
        SL.Foundation("P7", lad[:2] + ((lad[2][0], lad[1][1]),) + lad[3:], SL.p7().arms)
    with pytest.raises(TypeError):                                   # a float weight
        SL.Foundation("P7", ((lad[0][0], 0.5),) + lad[1:], SL.p7().arms)
    with pytest.raises(ValueError):                                  # a label twice
        SL.p7(list("はのにでとをを"))
    with pytest.raises(ValueError):                                  # arms out of order
        SL.Foundation("P7", lad, tuple(reversed(SL.p7().arms)))
    with pytest.raises(ValueError):
        SL.p7(list("はのに"))


def test_spec_sha_changes_when_any_axis_definition_the_window_rule_the_corpus_or_the_foundation_changes(space):
    base = SL.default_spec(space)
    seen = {base.sha256()}

    def differs(spec):
        h = spec.sha256()
        assert h not in seen
        seen.add(h)
    assert SL.default_spec(space).sha256() == base.sha256()          # reproducible
    for i, name in enumerate(SL.AXES):                               # the words of each axis definition
        axes = list(base.axes)
        axes[i] = dataclasses.replace(axes[i], text=axes[i].text + " ")
        differs(dataclasses.replace(base, axes=tuple(axes)))
    differs(SL.default_spec(space, y_pairs=(("RUN", "WORD"), ("WORD", "CHAR"))))      # y: a parameter the counting reads
    differs(SL.default_spec(space, z_tiers="same"))                                    # z: a parameter the counting reads
    for lone in ("none", "singleton"):
        differs(SL.default_spec(space, lone=lone))                                     # the window rule
    other = sp.build_space([{"sent": "東京は日本の首都である。", "source": "A#0"}, {"sent": "東京は広い。", "source": "A#1"}])
    differs(SL.default_spec(other))                                                    # the corpus
    f = SL.p7()
    swapped = list("はのにでとをが")
    swapped[1], swapped[2] = swapped[2], swapped[1]
    differs(SL.default_spec(space, foundation=SL.p7(swapped)))                         # labels in another ladder order
    lad = list(f.ladder)
    lad[6] = (lad[6][0], Fraction(1, 400))
    differs(SL.default_spec(space, foundation=SL.Foundation("P7", tuple(lad), f.arms)))  # one weight
    lad = list(f.ladder)
    lad[6] = ("も", lad[6][1])
    differs(SL.default_spec(space, foundation=SL.Foundation("P7", tuple(lad), tuple((a, "も" if l == "が" else l) for a, l in f.arms))))
    differs(SL.default_spec(space, foundation=SL.Foundation("P7x", f.ladder, f.arms)))  # the name
    assert len(base.short()) == 12 and base.sha256().startswith(base.short())


def test_spec_refuses_what_is_not_built(space):
    base = SL.default_spec(space)
    with pytest.raises(ValueError):
        dataclasses.replace(base, window=SL.WindowRule(span=3))
    with pytest.raises(ValueError):
        SL.default_spec(space, z_tiers="some")
    with pytest.raises(ValueError):
        SL.default_spec(space, y_pairs=(("WORD", "RUN"),))
    with pytest.raises(ValueError):
        SL.default_spec(space, lone="all")
    with pytest.raises(ValueError):
        dataclasses.replace(base, axes=(base.axes[1], base.axes[0], base.axes[2]))
    with pytest.raises(ValueError):                                  # a spec made for another corpus
        SL.Slide(sp.build_space([{"sent": "東京は日本の首都である。", "source": "A#0"}]), base)


def test_the_spec_carries_what_a_cache_key_needs(space):
    d = json.loads(SL.default_spec(space).to_bytes())
    assert d["corpus_sha256"] == space.sha256()
    assert [a["axis"] for a in d["axes"]] == ["x", "y", "z"]
    assert d["foundation"]["arms"]["+x"] == "の" and d["foundation"]["ladder"][0][1] == "233/377"
    assert d["window"]["span"] == 2 and d["window"]["scope"] == "same-article"
    assert d["format"] == SL.FORMAT


# ==== part 3: determinism, no float ==============================================================================================
SCRIPT = r"""
import hashlib, json, sys
sys.path.insert(0, %r)
from tests.line3 import test_slide as T
from verantyx.line3 import slide as SL, space as sp
rows = T.toy_rows()
space = sp.build_space(rows)
toy = SL.Slide(space, rows=rows)
h = hashlib.sha256()
h.update(toy.spec.to_bytes()); h.update(toy.to_bytes())
for w in toy.sequence():
    for scope in SL.SCOPES:
        h.update(toy.counts(w, scope).to_bytes())
print(h.hexdigest())
"""


def digest_here(toy):
    h = hashlib.sha256()
    h.update(toy.spec.to_bytes())
    h.update(toy.to_bytes())
    for w in toy.sequence():
        for scope in SL.SCOPES:
            h.update(toy.counts(w, scope).to_bytes())
    return h.hexdigest()


@pytest.mark.parametrize("seed", ["0", "1", "12345"])
def test_bytes_are_identical_under_other_hash_seeds(toy, seed):
    env = dict(os.environ, PYTHONHASHSEED=seed, PYTHONDONTWRITEBYTECODE="1", PYTHONPATH=ROOT)
    out = subprocess.run([sys.executable, "-c", SCRIPT % ROOT], env=env, cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()
    assert out == digest_here(toy)


def _no_float_hook(s):
    raise AssertionError("float in the output: %s" % s)


def test_no_float_in_the_modules_or_their_output(toy):
    for path in (os.path.join(ROOT, "verantyx/line3/slide.py"), os.path.join(G3, "reach_windows.py")):
        tree = ast.parse(open(path, encoding="utf-8").read())
        for n in ast.walk(tree):
            assert not (isinstance(n, ast.Constant) and isinstance(n.value, float)), (path, n.lineno)
            assert not (isinstance(n, ast.Name) and n.id == "float"), (path, n.lineno)
            assert not (isinstance(n, ast.BinOp) and isinstance(n.op, ast.Div)), (path, n.lineno)   # true division makes floats
    for blob in (toy.spec.to_bytes(), toy.to_bytes(), toy.counts(W(toy, 0), "corpus").to_bytes()):
        json.loads(blob, parse_float=_no_float_hook)
    with pytest.raises(TypeError):
        SL.canonical({"a": 0.5})


def test_canonical_form_is_sorted_compact_utf8(toy):
    b = toy.spec.to_bytes()
    assert b == json.dumps(json.loads(b), sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    assert "の".encode("utf-8") in b
    assert toy.spec.sha256() == hashlib.sha256(b).hexdigest()


# ==== part 4: fulllead (bank2) -- G3-a reach reproduction and the G3-b window numbers ============================================
@pytest.fixture(scope="module")
def reach():
    sys.path.insert(0, G3)
    import reach_windows as R
    return R.Reach()


@pytest.fixture(scope="module")
def reach_report(reach):
    return reach.report()


def test_fulllead_windows_592_and_292(reach):
    s = reach.slide
    assert (len(s.articles), s.space.N) == (300, 592)
    assert len(s.pairs()) == 292 and len(s.sequence()) == 592
    assert len(s.singletons()) == 125 and len(s.lasts()) == 300
    assert [len(a.sids) for a in s.articles if len(a.sids) == 1] == [1] * 125
    assert all(w.title == s.space.sentences[w.sids[0]][1].rsplit("#", 1)[0] == s.space.sentences[w.sids[1]][1].rsplit("#", 1)[0] for w in s.pairs())
    assert all(w.sids[1] == w.sids[0] + 1 and w.idx[1] == w.idx[0] + 1 for w in s.pairs())
    assert len({w.n for w in s.sequence()}) == 592


def test_fulllead_run_window_size_median_is_15(reach):
    s = reach.slide
    sizes = sorted(len(set(u for sid in w.sids for u in s.space.tiers["RUN"].sentence_units[sid])) for w in s.pairs())
    assert (len(sizes), sizes[len(sizes) // 2 - 1], sizes[len(sizes) // 2]) == (292, 15, 15)      # median 15.0
    assert sizes[-1] == 42


def test_reach_design_2_5_numbers(reach):
    n = reach.numbers()
    assert (n["n"], n["one_hop"], n["two_hop"], n["tok"]) == (69, 41, 10, 18)
    assert n["two_hop_ids"] == "I2-011 I2-020 I2-039 I2-043 R2-I002 R2-I003 R2-I004 R2-I007 R2-I012 R2-I019".split()
    assert (n["s1"]["windows"], n["s1"]["rw"], n["s1"]["rw_two_hop"], n["s1"]["run"], n["s1"]["run_two_hop"]) == (592, 41, 0, 39, 0)
    assert (n["a2"]["windows"], n["a2"]["rw"], n["a2"]["rw_two_hop"], n["a2"]["run"], n["a2"]["run_two_hop"]) == (592, 45, 4, 44, 4)
    assert (n["f2"]["windows"], n["f2"]["rw"], n["f2"]["rw_two_hop"], n["f2"]["run"], n["f2"]["run_two_hop"]) == (591, 45, 4, 44, 4)
    assert (n["a3"]["windows"], n["a3"]["rw"], n["a3"]["rw_two_hop"], n["a3"]["run"], n["a3"]["run_two_hop"]) == (592, 51, 10, 50, 10)
    assert (n["art"]["windows"], n["art"]["rw"], n["art"]["rw_two_hop"], n["art"]["run"], n["art"]["run_two_hop"]) == (300, 51, 10, 50, 10)
    # chance (other golds reached per question, median / mean of 68): 0.9 / 1.7 / 2.2 / 1.9 / 2.0
    assert [(n[k]["chance_median"], n[k]["chance_mean"]) for k in ("s1", "a2", "f2", "a3", "art")] == [
        ("0", "0.9"), ("1", "1.7"), ("2", "2.2"), ("1", "1.9"), ("1", "2.0")]


def line(report, start):
    ls = [l for l in report if l.startswith(start)]
    assert len(ls) == 1, (start, ls)
    return ls[0]


def test_reach_report_lines_of_design_2_5(reach_report):
    r = reach_report
    assert line(r, "intra2 n=69").startswith("intra2 n=69  one-hop (s1, RUN or WORD, same-tier) = 41  two-hop (gold unit exists, not one hop) = 10  tok = 18")
    assert line(r, "| a2 | 592 |").startswith("| a2 | 592 | 45 | 4 | 44 | 4 | 51 | 10 | 1 / 1.7 |")
    assert line(r, "| a3 | 592 |").startswith("| a3 | 592 | 51 | 10 | 50 | 10 | 51 | 10 | 1 / 1.9 |")
    # granularity link (F2 containment): 6 of the 10 two-hop items; 17 of 69 over the corpus, 6 new over the 41; chance 0.9
    assert line(r, "contained:") == "contained: 6 of 10"
    assert line(r, "y-hop (WORD q inside") == "y-hop (WORD q inside RUN gold span, one sentence): 17 of 69; new over the 41 one-hop: 6; of the 10 two-hop: 6"
    assert line(r, "union one-hop(s1)") == "union one-hop(s1) | a2 RUN same-tier | y-hop: 49 of 69; two-hop covered 8 (R2-I003 R2-I004 left)"
    assert line(r, "y-hop chance:") == "y-hop chance: other golds reached per question median 0 mean 0.9 (of 68)"
    # packs: 2-sentence windows RUN median 15, 3-tier sum median 68; 1 sentence 37.5; windows read per question
    assert line(r, "| a2 | RUN | 292 |") == "| a2 | RUN | 292 | 15.0 | 25 | 42 | 3 / 4 | 171 |"
    assert line(r, "| a2 | RUN+WORD+CHAR |") == "| a2 | RUN+WORD+CHAR | 292 | 68.0 | 111 | 168 | 12 / - | - |"
    assert line(r, "| s1 | RUN+WORD+CHAR |") == "| s1 | RUN+WORD+CHAR | 592 | 37.5 | 67 | 112 | 7 / - | - |"
    assert line(r, "windows read per question (s1") == "windows read per question (s1, RUN): intra2 median 5 p90 16 max 23; unans median 3 max 18"
    assert line(r, "windows read per question (a2") == "windows read per question (a2, RUN): intra2 median 8 p90 24 max 41; unans median 3 max 26"
    assert line(r, "articles 300") == "articles 300, sentences 592, articles with 1 sentence 125"
    assert line(r, "F2 containment links") == "F2 containment links per sentence: RUN>WORD median 11.5 p90 23 max 39; WORD>CHAR median 23.5 p90 50 max 107"
    assert line(r, "mixed RUN|WORD s1") == "mixed RUN|WORD s1: 49 of 69, 8 of the 10 two-hop"
    assert line(r, "mixed RUN|WORD a2") == "mixed RUN|WORD a2: 51 of 69, 10 of the 10 two-hop"
    assert line(r, "| a3 | RUN | 117 |") == "| a3 | RUN | 117 | 23 | 39 | 49 | 4 / 7 | 300 |"
    assert line(r, "| a3 | RUN+WORD+CHAR |") == "| a3 | RUN+WORD+CHAR | 117 | 102 | 154 | 198 | 17 / - | - |"
    # (6) the units a question faces: 1 sentence 45 -> 2 sentences 71 (intra2), unans 30 -> 49
    assert line(r, "| s1 | 45 / 127") == "| s1 | 45 / 127 | 30 / 64 | 25 / 25 |"
    assert line(r, "| a2 | 71 / 211") == "| a2 | 71 / 211 | 49 / 112 | 25 / 25 |"


def _need_t9_audit_records():
    """reach_windows.py prints the line "question units recomputed from bank2.tsv equal the T9 records: 207 / 207" only when the gitignored
    experiments/line3/t9/audit/raw/ask_fulllead_standard.jsonl exists; the committed reports (probe_hops.txt, reach_windows.txt) carry that
    line, so on a clean checkout without the file the generated report has one line less and these two comparisons cannot hold (L-G4-48)."""
    if not os.path.exists(os.path.join(ROOT, "experiments/line3/t9/audit/raw/ask_fulllead_standard.jsonl")):
        pytest.skip("experiments/line3/t9/audit/raw/ask_fulllead_standard.jsonl (gitignored) is absent: the reach report omits the T9 line")


def test_reach_report_equals_the_probes_committed_output_but_for_its_cut_lists(reach_report):
    """Every line of the probe's committed output is reproduced byte for byte, except that the probe cut column 3 (the
    articles, first 2) and column 5 (the gold sentences, first 4) of the per-item lines; reach_windows prints them whole,
    so there the probe's list is the first 2 / 4 entries of ours (L-531 (5); I2-039 is the only cut line)."""
    _need_t9_audit_records()
    committed = open(os.path.join(G3, "probe_hops.txt"), encoding="utf-8").read().split("\n")
    if committed and committed[-1] == "":
        committed = committed[:-1]
    assert len(committed) == len(reach_report)
    differing = [(a, b) for a, b in zip(reach_report, committed) if a != b]
    assert [a.split(" | ")[0] for a, _ in differing] == ["I2-039"]
    for a, b in differing:
        fa, fb = a.split(" | "), b.split(" | ")
        assert len(fa) == len(fb) == 8 and fa[:2] == fb[:2] and fa[3] == fb[3] and fa[5:] == fb[5:]
        assert ast.literal_eval(fb[2]) == ast.literal_eval(fa[2])[:2] and len(ast.literal_eval(fa[2])) == 6
        assert ast.literal_eval(fb[4]) == ast.literal_eval(fa[4])[:4] and len(ast.literal_eval(fa[4])) == 6


def test_reach_report_equals_the_committed_report(reach_report):
    """In process (the run's own hash seed); the three seeds 0 / 1 / 12345 were diffed by running the script (L-531)."""
    _need_t9_audit_records()
    committed = open(os.path.join(G3, "reach_windows.txt"), encoding="utf-8").read().split("\n")
    if committed and committed[-1] == "":
        committed = committed[:-1]
    assert committed == reach_report


def test_a2_windows_are_slides_windows_and_equal_the_probes_own_definition(reach):
    """The probe's a2: for each sentence i, (i, i+1) if i+1 is in the same article else (i,).  Slide.sequence() gives the same."""
    N, art = reach.N, reach.art
    probe_a2 = [tuple(j for j in (i, i + 1) if j < N and art[j] == art[i]) for i in range(N)]
    assert [w.sids for w in reach.slide.sequence()] == probe_a2
    assert [w for w in probe_a2 if len(w) == 2] == [w.sids for w in reach.slide.pairs()]


def test_one_sentence_windows_do_not_change_the_reach_on_bank2(reach):
    """Measured for the open point (do the 125 one-sentence articles form a window?): on the 69 intra2 golds the reach of
    the pairs alone, with the singletons, and with every article's last sentence is the same 45 (RUN 44)."""
    s = reach.slide
    P = [w.sids for w in s.pairs()]
    for W_ in (P, P + [w.sids for w in s.singletons()], [w.sids for w in s.sequence()]):
        assert sum(reach.hop(i, W_, ("RUN", "WORD"), ("RUN", "WORD")) for i in reach.ids) == 45
        assert sum(reach.hop(i, W_, ("RUN",), ("RUN",)) for i in reach.ids) == 44


def test_y_link_of_the_two_hop_items_is_slides_contain(reach):
    """F2's containment as Slide.contain (any occurrence pair): 6 of the 10 two-hop items have a WORD question unit inside the RUN gold span."""
    got = [i for i in reach.twohop if reach.yhop(i, i)]
    assert got == ["I2-020", "I2-039", "I2-043", "R2-I002", "R2-I007", "R2-I012"]


def test_question_units_from_bank2_equal_the_t9_records(reach):
    r = reach.t9_check()
    if r is None:
        pytest.skip("T9 audit records not present")
    assert r == (207, 207)


def test_ladder_order_is_the_share_order_of_the_fulllead_word_sentences():
    """G1 3.1.3 (a): the default rank is the order of the share of fulllead WORD sentences holding the particle."""
    rows = sp.load_jsonl(os.path.join(ROOT, "experiments/line3/bank2/data/fulllead_sents.jsonl"))
    space = sp.build_space(rows, None)                               # the old space: particles are units
    n = [len(space.tiers["WORD"].postings[p]) for p in SL.P7_LADDER]
    assert n == [446, 399, 341, 260, 193, 162, 143] and n == sorted(n, reverse=True) and len(set(n)) == 7


def test_fulllead_slide_counts_are_traceable_and_deterministic(reach):
    s = reach.slide
    w = s.pairs()[0]
    a = s.counts(w, "corpus")
    assert SL.verify_counts(s, a) > 1000
    assert a.to_bytes() == s.counts(w, "corpus").to_bytes()
    b = s.counts(w, "window")
    assert SL.verify_counts(s, b) > 100
    assert all(len(v) == 1 for v in b.z.values())                    # a window's own pair, once
    assert s.spec.corpus_sha == s.space.sha256()
