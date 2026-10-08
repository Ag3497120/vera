"""C3 acceptance (docs/LINE3_CARRY_DESIGN.md 9 C3, 3.4, 3.5, 4.2, 4.5, 6; OP-1 a, conditions 1-3).

Hand examples are derived in the comments.  The collapse points of the design 4.5 example are fixed by the
test-only injection (L-376), not by the budget.  Closed classes are checked with placement.verify_class."""
import dataclasses
import json
import os
import subprocess
import sys

import pytest

from verantyx.line3 import carry as C
from verantyx.line3 import placement as pl
from verantyx.line3.carry import CarryTower, Ledger, Occ, build_tower, stream_header
from verantyx.line3.space import build_space

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
MID = pl.budget_level("mid")

# ---------------------------------------------------------------- design 4.5
S45 = {0: "富士山 静岡県 山梨県 山", 1: "静岡県 県庁 静岡市", 2: "山梨県 県庁 甲府市",
       3: "富士山 噴火 1707年", 4: "甲府市 武田 城", 5: "武田 信玄 甲斐"}
S45 = {k: v.split() for k, v in S45.items()}


def inj45(level, unit, item):
    """4.5 (assumed collapses): U0:0 at 甲府市 of s2, U0:1 at 城 of s4."""
    if (level, unit) == (0, "U0:0") and (item.sid, item.pos) == (2, 2):
        return "injected"
    if (level, unit) == (0, "U0:1") and (item.sid, item.pos) == (4, 2):
        return "injected"
    return None


def feed(sents, budget=MID, inject=None, per_sentence=None):
    led = Ledger(stream_header("T", list(sents), budget, copy=C.TOWER_COPY))
    tw = CarryTower("T", budget, led, inject=inject)
    fed = []
    for s, us in sents.items():
        tw.feed_sentence(s, [Occ(s, i, u) for i, u in enumerate(us)])
        fed += [(s, i, u) for i, u in enumerate(us)]
        cov = tw.covered_occurrences()
        assert sorted(cov) == sorted(fed) and len(cov) == len(set(cov)), "P-1 broke after sentence %d" % s
        # the levels above an open unit change only when that unit closes, so its copy IS the live frontier F(k)
        opened = [tw.black] + [st.black for st in tw.uppers]
        assert all(tw.carry[b.unit] == tw.frontier(b.level) for b in opened), "copy != F(k) after sentence %d" % s
        if per_sentence:
            per_sentence(tw, s)
    return tw


def flow(tw, kinds=("open", "close", "pack", "carry", "admit", "rollback", "activation_deferred")):
    return [(e["kind"], e["level"], e["unit"], e.get("item")) for e in tw.ledger.events() if e["kind"] in kinds]


def test_design_4_5_example_as_an_event_sequence():
    tw = feed(S45, inject=inj45)
    ev = tw.ledger.events()
    assert [e["seq"] for e in ev] == list(range(1, len(ev) + 1))                 # seq on every event
    rb = [e for e in ev if e["kind"] == "rollback"]
    assert [(e["unit"], e["item"], e["budget_reason"]) for e in rb] == [("U0:0", "甲府市", "injected"),
                                                                       ("U0:1", "城", "injected")]
    # no natural collapse at mid on this tiny example: the only rollbacks are the two injected ones
    # seq 1-2: U0:0 opens, empty copy; seq 3-7 s0; 8-11 s1 ...; 12 backup of s2; 13, 14 山梨県 県庁 admitted, 15 rollback to 12
    assert (ev[0]["kind"], ev[1]["kind"], ev[1]["group"]) == ("open", "carry", [])
    assert rb[0]["seq"] == 15 and rb[0]["to"] == 12 and ev[11]["kind"] == "backup" and ev[11]["item"] == 2
    close0 = ev[15]
    assert close0["kind"] == "close" and close0["to"] == 12
    assert ev[16]["kind"] == "pack" and ev[16]["item"] == "P1:0" and ev[16]["level"] == 1
    assert ev[16]["group"] == sorted(["富士山", "静岡県", "山梨県", "山", "県庁", "静岡市"])
    # the order of the rest: open U0:1, open U1:0 (+ its empty copy), admit P1:0 into U1:0, copy {P1:0} to U0:1, ...
    f = [x for x in flow(tw) if x[0] != "admit" or x[1] > 0]
    assert f[:2] == [("open", 0, "U0:0", None), ("carry", 0, "U0:0", None)]
    tail = [x for x in f if x[0] != "rollback"][2:]
    assert tail == [("close", 0, "U0:0", None), ("pack", 1, "U0:0", "P1:0"), ("open", 0, "U0:1", None),
                    ("open", 1, "U1:0", None), ("carry", 1, "U1:0", None), ("admit", 1, "U1:0", "P1:0"),
                    ("carry", 0, "U0:1", None),
                    ("close", 0, "U0:1", None), ("pack", 1, "U0:1", "P1:1"), ("open", 0, "U0:2", None),
                    ("admit", 1, "U1:0", "P1:1"), ("carry", 0, "U0:2", None)]
    carries = {e["unit"]: e["group"] for e in ev if e["kind"] == "carry"}
    assert carries == {"U0:0": [], "U1:0": [], "U0:1": ["P1:0"], "U0:2": ["P1:0", "P1:1"]}
    # wake: s2's 山梨県 wakes P1:0 (same group as the occurrence, seq 23); s4's 甲府市 wakes P1:1; P1:0 sleeps for ever
    act = [(e["unit"], e["item"], e["activated"], e["group"]) for e in ev if e["kind"] == "admit" and e["activated"]]
    assert act == [("U0:1", "山梨県", ["P1:0"], ["山梨県", "P1:0"]), ("U0:2", "甲府市", ["P1:1"], ["甲府市", "P1:1"])]
    assert [e["seq"] for e in ev if e["kind"] == "admit" and e["activated"]] == [23, 39]
    # packs
    p0, p1 = tw.packs["P1:0"], tw.packs["P1:1"]
    assert p0.vocab == frozenset(["富士山", "静岡県", "山梨県", "山", "県庁", "静岡市"])
    assert p1.vocab == frozenset(["山梨県", "県庁", "甲府市", "富士山", "噴火", "1707年"])      # P1:0's words are NOT added
    assert (p0.inherited, p1.inherited) == ((), ("P1:0",)) and p1.carry == ("P1:0",)
    assert sorted({(o.sid) for o in p0.own_occ}) == [0, 1] and sorted({o.sid for o in p1.own_occ}) == [2, 3]
    # units, sovereigns
    assert [(b.unit, st) for b, st in tw.units()] == [("U0:0", "closed"), ("U0:1", "closed"), ("U0:2", "open"),
                                                      ("U1:0", "open")]
    assert tw.level_sizes() == [3, 1]
    # local space of U0:1 (design 4.5): N = 2 (s2, s3); P1:0 counted ONLY through the new sentences
    sp = tw.closed[1].black.space
    assert sp.N == 2 and sp.sids == (2, 3)
    assert sp.n("P1:0") == 2 and sp.r0("P1:0") == 1 and sp.n_pair("P1:0", "甲府市") == 1
    assert sp.sentence_elements(0) == ("P1:0", "山梨県", "県庁", "甲府市")           # 4.5: P1:0 at position 0 (山梨県 is a vocab word)
    # U1:0: scope s0..s3, n(P1:0, P1:1) = 4 (every one of the four sentences holds both)
    u10 = tw.uppers[0].black
    assert u10.space.sids == (0, 1, 2, 3) and u10.space.n_pair("P1:0", "P1:1") == 4
    # the open black U0:2 woke P1:1 only; P1:0 is asleep (not in the local space at all)
    assert {e.id for e in tw.black.space.elements} == {"甲府市", "武田", "城", "信玄", "甲斐", "P1:1"}
    assert tw.frontier(0) == (p0, p1)
    # every class is a fixed point
    assert all(b.verify().is_stable_class for b, _ in tw.units())
    assert C.ledger_mismatches(tw) == []


def test_example_4_5_has_the_two_injected_collapses_only_by_injection():
    """Without the injection the tiny example never collapses at mid: one black, no pack, no upper level."""
    tw = feed(S45)
    assert tw.level_sizes() == [1] and not tw.packs
    assert [e["kind"] for e in tw.ledger.events() if e["kind"] in ("rollback", "close", "pack")] == []


# ---------------------------------------------------------------- carry-up recursion (a deep tower by injection)
# s0 = a b, s1 = b c, s2 = c d, s3 = d e; level 0: a black holds ONE sentence (collapse at the first word of
# the next one); levels 1 and 2: a unit holds ONE child (collapse of any non-empty unit); level 3 never collapses.
# Hand run (see the numbers in the comments):
#   s1: U0:0 closes -> P1:0 {a b} -> U1:0 (new level 1).  U0:1 copies F(0) = {P1:0}; 'b' wakes P1:0.
#   s2: U0:1 closes -> P1:1 {b c}; U1:0 (holds P1:0) collapses -> closes -> P2:0 {a b} -> U2:0 (new level 2);
#       U1:1 copies F(1) = {P2:0}; P1:1 wakes P2:0 (b); U0:2 copies F(0) = {P1:1, P2:0}; 'c' wakes P1:1.
#   s3: U0:2 closes -> P1:2 {c d}; U1:1 collapses -> closes -> P2:1 {b c} (children [P1:1], woke P2:0);
#       U2:0 collapses -> closes -> P3:0 {a b} -> U3:0; U2:1 copies {P3:0}, P2:1 wakes it; U1:2 copies F(1) =
#       {P2:1, P3:0}, P1:2 wakes P2:1 (c); U0:3 copies F(0) = {P1:2, P2:1, P3:0}; 'd' wakes P1:2.
S_DEEP = {0: ["a", "b"], 1: ["b", "c"], 2: ["c", "d"], 3: ["d", "e"]}


def inj_deep(level, unit, item):
    if level == 0:
        return "injected" if item.pos == 0 else None
    return "injected" if level in (1, 2) else None


def test_carry_up_recursion_hand_tower():
    tw = feed(S_DEEP, inject=inj_deep)
    assert tw.level_sizes() == [4, 3, 2, 1]
    carries = {u: [p.id for p in v] for u, v in tw.carry.items()}
    assert carries == {"U0:0": [], "U0:1": ["P1:0"], "U0:2": ["P1:1", "P2:0"], "U0:3": ["P1:2", "P2:1", "P3:0"],
                       "U1:0": [], "U1:1": ["P2:0"], "U1:2": ["P2:1", "P3:0"], "U2:0": [], "U2:1": ["P3:0"],
                       "U3:0": []}
    pk = tw.packs
    assert sorted(pk) == ["P1:0", "P1:1", "P1:2", "P2:0", "P2:1", "P3:0"]
    assert pk["P2:0"].children == ("P1:0",) and pk["P2:0"].vocab == frozenset("ab")
    assert pk["P2:1"].children == ("P1:1",) and pk["P2:1"].inherited == ("P2:0",) and pk["P2:1"].vocab == frozenset("bc")
    assert pk["P3:0"].children == ("P2:0",) and pk["P3:0"].vocab == frozenset("ab")
    assert pk["P1:1"].inherited == ("P1:0",) and pk["P1:2"].inherited == ("P1:1",)
    # a pack above level 1 is the union of its children's own occurrences (condition 1, P-2)
    for p in pk.values():
        if p.level >= 2:
            assert p.own_occ == tuple(o for c in p.children for o in pk[c].own_occ)
    # who woke whom
    wake = {(e["unit"], e["item"]): e["activated"] for e in tw.ledger.events() if e["kind"] == "admit" and e["activated"]}
    assert wake == {("U0:1", "b"): ["P1:0"], ("U1:1", "P1:1"): ["P2:0"], ("U0:2", "c"): ["P1:1"],
                    ("U2:1", "P2:1"): ["P3:0"], ("U1:2", "P1:2"): ["P2:1"], ("U0:3", "d"): ["P1:2"]}
    # frontier: P1:2 (U1:2), P2:1 (U2:1), P3:0 (U3:0) cover s0 (P3:0), s1 (P2:1), s2 (P1:2); U0:3 holds s3
    assert [p.id for p in tw.frontier(0)] == ["P1:2", "P2:1", "P3:0"]
    assert [p.id for p in tw.frontier(1)] == ["P2:1", "P3:0"] and [p.id for p in tw.frontier(2)] == ["P3:0"]
    assert tw.frontier(3) == ()
    assert sorted(tw.covered_occurrences()) == [(s, i, u) for s, us in S_DEEP.items() for i, u in enumerate(us)]
    # P-1 per level: the scopes of all units of a level partition all occurrences
    allocc = sorted((s, i, u) for s, us in S_DEEP.items() for i, u in enumerate(us))
    for lv in range(4):                              # P-1 per level: scopes of level lv + open scopes below it = every occurrence once
        cov = tw.level_covered(lv)
        assert len(cov) == len(set(cov)) and sorted(cov) == allocc
    assert sorted((o.sid, o.pos, o.unit) for b, _ in tw.units() if b.level == 0 for o in b.space.scope) == allocc
    # each closed unit's pack is a NEW element of exactly one unit one level up
    for p in pk.values():
        holders = [b.unit for b, _ in tw.units() if any(e.id == p.id and e.origin == "new" for e in b.space.elements)]
        assert len(holders) == 1 and int(holders[0][1]) == p.level
    assert C.ledger_mismatches(tw) == []
    assert all(b.verify().is_stable_class for b, _ in tw.units())


def test_natural_deep_tower_with_a_tiny_budget_covers_every_event_at_every_step():
    """max_states = 1: every black holds one unit, so the tower grows by itself (no injection)."""
    sents = {0: ["a", "b", "c"], 1: ["c", "d", "a"], 2: ["e", "b", "f", "a"], 3: ["a", "g"], 4: ["b", "e"]}
    tw = feed(sents, budget=pl.Budget(max_states=1))
    assert len(tw.uppers) >= 2                                                    # more than one level of carry-up
    for lv in range(len(tw.uppers) + 1):
        cov = tw.level_covered(lv)
        assert len(cov) == len(set(cov)) and sorted(cov) == sorted((s, i, u) for s, us in sents.items() for i, u in enumerate(us))
    allocc = sorted((s, i, u) for s, us in sents.items() for i, u in enumerate(us))
    assert sorted((o.sid, o.pos, o.unit) for b, _ in tw.units() if b.level == 0 for o in b.space.scope) == allocc
    assert C.ledger_mismatches(tw) == []
    assert all(b.verify().is_stable_class for b, _ in tw.units())


# ---------------------------------------------------------------- copies are immutable (L-309, L-371)
def test_copies_are_immutable_and_frozen_at_copy_time():
    seen = {}

    def snap(tw, s):
        for u, v in tw.carry.items():
            seen.setdefault(u, (v, tuple((p.id, p.vocab, p.own_occ, p.state) for p in v)))
    tw = feed(S_DEEP, inject=inj_deep, per_sentence=snap)
    for u, (v, rep) in seen.items():
        now = tw.carry[u]
        assert now == v and now is v                                              # never replaced
        assert tuple((p.id, p.vocab, p.own_occ, p.state) for p in now) == rep    # and never mutated
    p = tw.packs["P1:0"]
    with pytest.raises(dataclasses.FrozenInstanceError):
        p.vocab = frozenset("x")
    assert isinstance(p.vocab, frozenset) and isinstance(tw.carry["U0:1"], tuple)
    # a pack's vocab does not change when the packs after it grow (ledger pack event = the vocab at copy time)
    pe = {e["item"]: e["group"] for e in tw.ledger.events() if e["kind"] == "pack"}
    assert all(sorted(tw.packs[i].vocab) == g for i, g in pe.items())


# ---------------------------------------------------------------- condition 2: inherited packs are not recounted
def test_inherited_pack_is_counted_only_through_new_sentences():
    tw = feed(S45, inject=inj45)
    u01 = tw.closed[1].black
    # P1:0's own sentences s0, s1 are not in U0:1; its n is the number of NEW sentences that hold a word of its vocab
    assert u01.space.sids == (2, 3) and u01.space.n("P1:0") == 2
    p = tw.packs["P1:0"]
    assert {o.sid for o in p.own_occ} == {0, 1} and not {0, 1} & set(u01.space.sids)
    # a sleeping pack takes no seat and adds no count: P1:0 in U0:2 (no word of s4, s5 in its vocab)
    assert "P1:0" not in {e.id for e in tw.black.space.elements}
    assert tw.black.space.n_pair("甲府市", "P1:1") == 1
    # origin marks: P1:1 is `inherited` in U0:2 and `new` in U1:0; never both in one unit
    assert tw.black.space.element("P1:1").origin == "inherited"
    assert tw.uppers[0].black.space.element("P1:1").origin == "new"
    for b, _ in tw.units():
        new = {e.id for e in b.space.elements if e.origin == "new"}
        inh = {e.id for e in b.space.elements if e.origin == "inherited"}
        assert not new & inh
        # I-1: rebuilding the local space from (scope, elements) alone gives the same bytes
        assert b.space.to_bytes() == C.LocalSpace.build(b.space.scope, b.space.elements, b.space.tier).to_bytes()


def test_changing_the_past_inside_a_frozen_vocab_changes_no_count_of_the_later_unit():
    """Poisoned past (I-2, read as the C1 review note 4 asks: the vocab stays fixed): the words of s0, s1 are
    written in another order; the packs have the same vocab, so U0:1's local space and class are identical."""
    other = dict(S45)
    other[0] = ["山", "山梨県", "静岡県", "富士山"]
    other[1] = ["静岡市", "県庁", "静岡県"]
    a, b = feed(S45, inject=inj45), feed(other, inject=inj45)
    assert a.packs["P1:0"].vocab == b.packs["P1:0"].vocab
    assert a.closed[1].black.space.to_bytes() == b.closed[1].black.space.to_bytes()
    assert a.closed[1].black.state == b.closed[1].black.state and a.closed[1].black.L == b.closed[1].black.L
    assert a.black.space.to_bytes() == b.black.space.to_bytes()
    # and the vocab of a pack of a LATER unit never takes the words of the inherited pack
    assert not (a.packs["P1:0"].vocab - a.packs["P1:1"].vocab) & a.packs["P1:1"].vocab


# ---------------------------------------------------------------- waking (OP-1 a)
def test_a_pack_wakes_only_when_a_new_occurrence_has_a_word_of_its_vocab():
    sents = {0: ["a", "b"], 1: ["x", "a", "y"], 2: ["z", "w"], 3: ["b", "z"]}
    tw = feed(sents, inject=lambda lv, u, i: "injected" if (lv, u) == (0, "U0:0") and i.sid == 1 else None)
    assert tw.carry["U0:1"][0].id == "P1:0"
    ev = [e for e in tw.ledger.events() if e["unit"] == "U0:1" and e["kind"] == "admit"]
    # s1 x: no word of vocab {a, b} -> asleep; s1 a: wakes (same group as the occurrence); y, z, w: nothing; s3 b: already seated
    assert [(e["item"], e["activated"]) for e in ev] == [("x", []), ("a", ["P1:0"]), ("y", []), ("z", []), ("w", []),
                                                         ("b", []), ("z", [])][:len(ev)]
    assert tw.black.space.element("P1:0").origin == "inherited"
    # before the waking occurrence the pack is not in the space; it was seated together with 'a' (one group, L-64)
    i = [e["item"] for e in ev].index("a")
    assert ev[i]["group"] == ["P1:0", "a"] or ev[i]["group"] == ["a", "P1:0"]
    assert tw.black.space.n("P1:0") == 2                                             # s1 (a) and s3 (b); s0 is not counted


def test_an_activation_that_does_not_fit_is_deferred_at_every_level():
    """max_states = 1: a first group of two (item + woken pack) never fits; the pack stays asleep (L-308 / L-380)."""
    sents = {0: ["a", "b", "c"], 1: ["c", "d", "a"], 2: ["e", "b", "f", "a"], 3: ["a", "g", "c"], 4: ["b", "e", "a"]}
    tw = feed(sents, budget=pl.Budget(max_states=1))
    ev = tw.ledger.events()
    de = [e for e in ev if e["kind"] == "activation_deferred"]
    assert de and {e["level"] for e in de} >= {0, 1}
    for e in de:
        nxt = ev[e["seq"]]                                                         # the admit that follows (seq is 1-based)
        assert nxt["kind"] == "admit" and nxt["unit"] == e["unit"] and nxt["activated"] == []
        assert not set(e["group"]) & set(nxt["group"])
    assert C.ledger_mismatches(tw) == []


def test_a_deferred_pack_wakes_again_only_through_a_word_of_its_vocab():
    """Review: three packs whose vocab holds 'a' are copied to U0:3; s3's 'a' wakes all three, the first group of four
    does not fit an empty black at max_states=16 (activation_deferred, measured), 'a' goes in alone.  The later
    occurrences x, y, y, z are in no vocab, so the packs stay asleep: a seated word of the black (a) wakes nothing."""
    sents = {0: ["a", "b"], 1: ["a", "c"], 2: ["a", "d"], 3: ["a", "x", "y"], 4: ["y", "z"]}
    inj = lambda lv, u, i: "injected" if lv == 0 and i.pos == 0 and i.sid in (1, 2, 3) else None
    tw = feed(sents, budget=pl.Budget(max_states=16), inject=inj)
    assert [p.id for p in tw.carry["U0:3"]] == ["P1:0", "P1:1", "P1:2"]
    ev = [e for e in tw.ledger.events() if e["unit"] == "U0:3" and e["kind"] in ("admit", "activation_deferred")]
    assert [(e["kind"], e["item"], e["group"]) for e in ev] == [
        ("activation_deferred", "a", ["P1:0", "P1:1", "P1:2"]), ("admit", "a", ["a"]), ("admit", "x", ["x"]),
        ("admit", "y", ["y"]), ("admit", "y", []), ("admit", "z", ["z"])]
    assert all(e["activated"] == [] for e in ev if e["kind"] == "admit")
    assert {e.id for e in tw.black.space.elements} == {"a", "x", "y", "z"}
    assert C.ledger_mismatches(tw) == []


# ---------------------------------------------------------------- real data: S300 head
def _rows(n):
    with open(os.path.join(ROOT, "experiments", "line3", "data", "S300.jsonl"), encoding="utf-8") as f:
        return [json.loads(l) for l in f][:n]


@pytest.fixture(scope="module", params=["RUN", "WORD"])
def real(request):
    tier, n = request.param, 16
    ts = build_space(_rows(n)).tiers[tier]
    fed = []

    def check(tw, s):                                                              # P-1 after every sentence
        fed.extend((s, o.pos, o.unit) for o in C.occurrences_of(ts, s))
        cov = tw.covered_occurrences()
        assert len(cov) == len(set(cov)) and sorted(cov) == sorted(fed)
    tw = build_tower(tier, ts, list(range(n)), pl.budget_level("low"), after_sentence=check)
    return tier, ts, n, tw


def want0(ts, n):
    return [(s, o.pos, o.unit) for s in range(n) for o in C.occurrences_of(ts, s)]


def test_real_stream_builds_a_tower_with_stable_classes_and_a_complete_ledger(real):
    tier, ts, n, tw = real
    assert len(tw.uppers) >= 1 and len(tw.closed) >= 2
    assert all(b.verify().is_stable_class for b, _ in tw.units())
    assert C.ledger_mismatches(tw) == []
    for lv in range(len(tw.uppers) + 1):
        cov = tw.level_covered(lv)
        assert len(cov) == len(set(cov)) and sorted(cov) == sorted(want0(ts, n))
    # O-2: the surviving level-0 admits are every occurrence once, in the header's order
    rep = C.replay_ledger(tw.ledger)
    scopes = [o for u in sorted((u for u in rep if rep[u]["level"] == 0), key=lambda x: int(x.split(":")[1]))
              for o in rep[u]["scope"]]
    want = [[s, o.pos, o.unit] for s in range(n) for o in C.occurrences_of(ts, s)]
    assert scopes == want
    assert tw.ledger.header["order_sha256"] == C.order_sha256(range(n))
    # I-1 for every unit; copies of upper levels are packs only
    for b, _ in tw.units():
        assert b.space.to_bytes() == C.LocalSpace.build(b.space.scope, b.space.elements, b.space.tier).to_bytes()
    assert all(isinstance(p, C.Pack) for v in tw.carry.values() for p in v)


def test_replay_reproduces_tower_and_ledger_bytes_O1(real):
    tier, ts, n, tw = real
    again = build_tower(tier, ts, list(range(n)), pl.budget_level("low"))
    assert again.ledger.to_bytes() == tw.ledger.to_bytes() and again.to_bytes() == tw.to_bytes()
    rp = C.replay_tower(tw.ledger.to_bytes(), ts, tier, list(range(n)), pl.budget_level("low"))
    assert rp.to_bytes() == tw.to_bytes()
    # the compared bytes hold every unit's copy (L-379)
    doc = json.loads(tw.to_bytes().decode("utf-8"))
    assert {u["id"]: u["carry"] for u in doc["units"]} == {u: [p.id for p in v] for u, v in tw.carry.items()}
    # a ledger with the right key but other events is refused (the rebuild does not reproduce its bytes)
    short = Ledger(tw.ledger.header)
    for e in tw.ledger.events()[:-1]:
        e = dict(e)
        short.append(e.pop("kind"), **{k: v for k, v in e.items() if k != "seq"})
    with pytest.raises(ValueError):
        C.replay_tower(short.to_bytes(), ts, tier, list(range(n)), pl.budget_level("low"))


# ---------------------------------------------------------------- O-2: completeness and tamper detection
def test_the_ledger_alone_rebuilds_every_unit_net_of_rollbacks():
    tw = feed(S45, inject=inj45)
    rep = C.replay_ledger(tw.ledger)
    assert rep["U0:0"]["status"] == "closed" and rep["U0:0"]["pack"] == "P1:0"
    # the rolled-back admits of s2 (山梨県, 県庁) are NOT in U0:0's scope
    assert [o[:2] for o in rep["U0:0"]["scope"]] == [[0, 0], [0, 1], [0, 2], [0, 3], [1, 0], [1, 1], [1, 2]]
    assert rep["U0:1"]["active"] == ["P1:0"] and rep["U0:1"]["carry"] == ["P1:0"]
    assert rep["U1:0"]["new"] == ["P1:0", "P1:1"] and len(rep["U1:0"]["scope"]) == 7 + 6
    adm = [e for e in tw.ledger.events() if e["kind"] == "admit" and e["level"] == 0]
    assert len(adm) > sum(len(us) for us in S45.values())                           # gross count includes undone admits
    assert sum(len(v["scope"]) for v in rep.values() if v["level"] == 0) == sum(len(us) for us in S45.values())


def _tampered(tw, edit):
    led = Ledger(tw.ledger.header)
    for e in edit([dict(x) for x in tw.ledger.events()]):
        e = dict(e)
        led.append(e.pop("kind"), **{k: v for k, v in e.items() if k != "seq"})
    tw.ledger = led
    return tw


@pytest.mark.parametrize("how", ["drop_rollback", "move_occ", "drop_carry_id", "drop_activation",
                                 "extra_new_id", "extra_activation", "pack_vocab_word"])
def test_a_tampered_ledger_is_detected(how):
    tw = feed(S45, inject=inj45)

    def edit(ev):
        if how == "drop_rollback":
            i = next(i for i, e in enumerate(ev) if e["kind"] == "rollback")
            return ev[:i] + ev[i + 1:]
        if how == "move_occ":
            i = next(i for i, e in enumerate(ev) if e["kind"] == "admit" and e["level"] == 0)
            ev[i]["occ"] = [ev[i]["occ"][0], ev[i]["occ"][1] + 5]
        if how == "drop_carry_id":
            i = next(i for i, e in enumerate(ev) if e["kind"] == "carry" and e["group"])
            ev[i]["group"] = []
        if how == "drop_activation":
            i = next(i for i, e in enumerate(ev) if e["kind"] == "admit" and e["activated"])
            ev[i]["activated"] = []
        if how == "extra_new_id":                     # only the "new elements" comparison sees this one
            i = next(i for i, e in enumerate(ev) if e["kind"] == "admit" and e["level"] == 0)
            ev[i]["group"] = ev[i]["group"] + ["zz"]
        if how == "extra_activation":                 # only the "woken" comparison sees this one (U0:2 woke P1:1 only)
            i = next(i for i, e in enumerate(ev) if e["kind"] == "admit" and e["unit"] == "U0:2" and e["activated"])
            ev[i]["activated"] = ["P1:0"] + ev[i]["activated"]
        if how == "pack_vocab_word":
            i = next(i for i, e in enumerate(ev) if e["kind"] == "pack")
            ev[i]["group"] = sorted(ev[i]["group"] + ["zz"])
        return ev
    assert C.ledger_mismatches(_tampered(tw, edit)) != []


# ---------------------------------------------------------------- O-3: the order is part of the cache key
def test_other_order_other_key_and_the_cache_is_refused():
    ts = build_space(_rows(10)).tiers["RUN"]
    bud, sids = pl.budget_level("low"), list(range(10))
    fwd = build_tower("RUN", ts, sids, bud)
    rev = build_tower("RUN", ts, C.ordered_sids(sids, "reverse"), bud, order_kind="reverse")
    assert fwd.ledger.header["order_sha256"] != rev.ledger.header["order_sha256"]
    assert fwd.ledger.header["order"] == {"kind": "file", "seed": None} and rev.ledger.header["order"]["kind"] == "reverse"
    C.check_cache_key(fwd.ledger.header, "RUN", sids, bud)
    with pytest.raises(ValueError):
        C.check_cache_key(fwd.ledger.header, "RUN", sids[::-1], bud)               # another order
    with pytest.raises(ValueError):
        C.replay_tower(fwd.ledger.to_bytes(), ts, "RUN", sids[::-1], bud)          # replay refuses it
    with pytest.raises(ValueError):
        C.check_cache_key(fwd.ledger.header, "WORD", sids, bud)                    # another tier
    with pytest.raises(ValueError):
        C.check_cache_key(fwd.ledger.header, "RUN", sids, pl.budget_level("mid"))  # another build level
    with pytest.raises(ValueError):
        C.check_cache_key(fwd.ledger.header, "RUN", sids, bud, data_sha256="0" * 64)
    with pytest.raises(ValueError):                                                 # a ledger that does not belong to the data
        C.replay_tower(fwd.ledger.to_bytes(), build_space(_rows(11)).tiers["RUN"], "RUN", list(range(11)), bud)
    a, b = C.ordered_sids(range(20), "shuffle", 1), C.ordered_sids(range(20), "shuffle", 1)
    assert a == b and a != list(range(20)) and C.ordered_sids(range(20), "shuffle", 2) != a
    assert sorted(a) == list(range(20))
    with pytest.raises(ValueError):
        C.ordered_sids(range(3), "shuffle")


# ---------------------------------------------------------------- the injection is test-only and bounded
def test_injection_never_blocks_an_empty_unit_and_is_recorded():
    always = lambda lv, u, i: "injected"
    tw = feed({0: ["a", "b"], 1: ["c", "d"]}, inject=always)
    assert tw.level_sizes()[0] == 4 and all(b.n_elements >= 1 for b, _ in tw.units())      # every unit took its first element
    assert {e["budget_reason"] for e in tw.ledger.events() if e["kind"] == "rollback"} == {"injected"}
    assert not [e for e in tw.ledger.events() if e["kind"] == "split" and e["budget_reason"] != "injected"]
    # an injected reason must say so (L-376): a budget-looking reason is refused
    with pytest.raises(ValueError):
        feed({0: ["a", "b"]}, inject=lambda lv, u, i: "max_states")


# ---------------------------------------------------------------- determinism (O-1, hash seeds)
_PROBE = r"""
import json, sys
from verantyx.line3 import carry as C, placement as pl
from verantyx.line3.space import build_space
rows = [json.loads(l) for l in open("experiments/line3/data/S300.jsonl", encoding="utf-8")][:12]
tier = sys.argv[1]
ts = build_space(rows).tiers[tier]
tw = C.build_tower(tier, ts, list(range(12)), pl.budget_level("low"))
print(tw.ledger.sha256(), tw.sha256(), len(tw.ledger), tw.level_sizes())
"""


@pytest.mark.parametrize("tier", ["RUN", "WORD"])
def test_byte_identical_across_hash_seeds(tier):
    outs = []
    for seed in ("0", "1", "12345"):
        env = dict(os.environ, PYTHONHASHSEED=seed, PYTHONPATH=ROOT)
        r = subprocess.run([sys.executable, "-c", _PROBE, tier], cwd=ROOT, env=env, capture_output=True, text=True)
        assert r.returncode == 0, r.stderr
        outs.append(r.stdout)
    assert outs[0] == outs[1] == outs[2] and outs[0].strip()


def test_c2_stream_is_unchanged_when_the_tower_hooks_are_unused():
    """BlackStream alone (no wake, no inject) still gives its C2 ledger: no `carry` event, copy text as in C2."""
    ts = build_space(_rows(10)).tiers["RUN"]
    bud = pl.budget_level("low")
    led = Ledger(stream_header("RUN", list(range(10)), bud))
    bs = C.BlackStream("RUN", bud, led)
    bs.feed_tier(ts, range(10))
    assert "carry" not in {e["kind"] for e in led.events()} and "C3" in led.header["copy"]


# ---------------------------------------------------------------- C3b: pack_overflow = "close" (default) | "defer"
# sha256 of Ledger / to_bytes of the S300 head (12 sentences, low) computed with the C3 code at HEAD b730efb
HEAD_SHA = {"RUN": ("112382d093a4b0b90850c4668f848da028e845c338eb81286e20e9cd6873aeef",
                    "d54957a981ce85ec3081251e1c3cc167dd66db15f2168d847b4e4e33d5a773e4"),
            "WORD": ("e1be2257b5c004f74d3bf5b07462fd56b2e8eccf347596d86dab94575f311ead",
                     "0667462f6642432f3ee53c794355a7d1ecc0022df6f11e8bd29144ada7657420")}
TINY = pl.Budget(max_states=16)          # the S300 head of 40 sentences then has non-empty-black pack overflows


@pytest.mark.parametrize("tier", ["RUN", "WORD"])
def test_default_pack_overflow_is_close_and_byte_identical_to_head(tier):
    ts = build_space(_rows(12)).tiers[tier]
    for kw in ({}, {"pack_overflow": "close"}):
        tw = build_tower(tier, ts, list(range(12)), pl.budget_level("low"), **kw)
        assert (tw.ledger.sha256(), tw.sha256()) == HEAD_SHA[tier]
        assert "pack_overflow" not in tw.ledger.header and tw.pack_overflow == "close"
    assert "pack_overflow" not in stream_header("RUN", [0], pl.budget_level("low"))


def test_pack_overflow_value_is_checked():
    with pytest.raises(ValueError):
        build_tower("RUN", build_space(_rows(2)).tiers["RUN"], [0, 1], pl.budget_level("low"), pack_overflow="open")


class _Spy:
    """Logs every Black.admit: (unit, black empty?, number of woken packs in the call, ok | collapse, occs)."""

    def __init__(self, monkeypatch):
        self.log, orig, self.alone_fits = [], C.Black.admit, 0
        log = self.log

        def admit(b, occs, elements=()):
            elements, occs = tuple(elements), tuple(occs)
            n = sum(e.origin == C.ORIGIN_INHERITED for e in elements)
            try:
                r = orig(b, occs, elements)
            except C.Collapse:
                log.append((b.unit, b.is_empty, n, "collapse", occs))
                if n and not b.is_empty:                                           # would the occurrence alone fit?
                    try:
                        orig(b, occs, [e for e in elements if e.origin != C.ORIGIN_INHERITED])
                        self.alone_fits += 1
                    except C.Collapse:
                        pass
                raise
            log.append((b.unit, b.is_empty, n, "ok", occs))
            return r
        monkeypatch.setattr(C.Black, "admit", admit)


@pytest.fixture(scope="module")
def run40():
    return build_space(_rows(40)).tiers["RUN"]


def _build40(ts, po):
    return build_tower("RUN", ts, list(range(40)), TINY, pack_overflow=po)


def test_defer_retries_without_the_packs_in_a_non_empty_black(run40, monkeypatch):
    spy = _Spy(monkeypatch)
    tw = _build40(run40, "defer")
    ev = tw.ledger.events()
    # the deferred packs are retried alone (one retry), in a black that already holds elements
    nonempty = [i for i, l in enumerate(spy.log) if l[3] == "collapse" and l[2] > 0 and not l[1]]
    assert nonempty, "the fixture must contain a non-empty-black pack overflow"
    for i in nonempty:
        nxt = spy.log[i + 1]
        assert nxt[0] == spy.log[i][0] and nxt[2] == 0 and nxt[4] == spy.log[i][4]      # same unit, same occurrences, no packs
    de = [e for e in ev if e["kind"] == "activation_deferred"]
    assert len(de) >= len(nonempty)
    for e in de:
        nxt = ev[e["seq"]]                                                         # the event right after (seq is 1-based)
        if nxt["kind"] == "admit":                                                 # the occurrence alone fits
            assert nxt["unit"] == e["unit"] and nxt["activated"] == [] and not set(e["group"]) & set(nxt["group"])
            assert not any(x in nxt["group"] for x in e["group"])
        assert e["budget_reason"] and e["group"]
    assert C.ledger_mismatches(tw) == []
    assert all(b.verify().is_stable_class for b, _ in tw.units())


def test_defer_never_closes_a_black_the_occurrence_alone_fits(run40, monkeypatch):
    spy = _Spy(monkeypatch)
    tw = _build40(run40, "defer")
    ev = tw.ledger.events()
    # every collapse that is NOT followed by an alone retry (i.e. every one without woken packs) is exactly one rollback
    final = [l for l in spy.log if l[3] == "collapse" and l[2] == 0]
    assert len(final) == sum(e["kind"] == "rollback" for e in ev)
    # and every collapse that had woken packs in a non-empty black was followed by the alone retry (no close by packs only)
    for i, l in enumerate(spy.log):
        if l[3] == "collapse" and l[2] > 0 and not l[1]:
            assert spy.log[i + 1][0] == l[0] and spy.log[i + 1][2] == 0
    # contrast: under close the same stream does close blacks the occurrence alone would fit
    spy.alone_fits = 0
    spy.log.clear()
    _build40(run40, "close")
    assert spy.alone_fits > 0


def test_defer_alone_collapse_still_closes_as_before():
    """max_states = 1: nothing but a one-element black fits; a collapse of the occurrence alone closes (OP-2 b), under both rules."""
    sents = {0: ["a", "b", "c"], 1: ["c", "d", "a"], 2: ["e", "b", "f", "a"], 3: ["a", "g", "c"], 4: ["b", "e", "a"]}
    tws = {}
    for po in C.PACK_OVERFLOW:
        led = Ledger(stream_header("T", list(sents), pl.Budget(max_states=1), copy=C.TOWER_COPY, pack_overflow=po))
        tw = CarryTower("T", pl.Budget(max_states=1), led, pack_overflow=po)
        for s, us in sents.items():
            tw.feed_sentence(s, [Occ(s, i, u) for i, u in enumerate(us)])
        tws[po] = tw
        assert C.ledger_mismatches(tw) == []
    for tw in tws.values():
        assert any(e["kind"] == "close" for e in tw.ledger.events())
        assert any(e["kind"] == "split" for e in tw.ledger.events())


def test_defer_deferred_pack_wakes_only_through_a_word_of_its_vocab(run40):
    tw = _build40(run40, "defer")
    ev = tw.ledger.events()
    for e in ev:
        if e["kind"] == "admit" and e["level"] == 0:
            for pid in e["activated"]:
                assert e["item"] in tw.packs[pid].vocab                         # nothing else wakes (L-372)
    assert any(e["kind"] == "activation_deferred" and e["level"] == 0 for e in ev)


@pytest.mark.parametrize("tier", ["RUN", "WORD"])
def test_p1_o1_o2_o3_hold_under_defer(tier):
    n, bud = 30, pl.Budget(max_states=8)
    ts = build_space(_rows(n)).tiers[tier]
    fed = []

    def check(tw, s):                                                              # P-1 after every sentence
        fed.extend((s, o.pos, o.unit) for o in C.occurrences_of(ts, s))
        cov = tw.covered_occurrences()
        assert len(cov) == len(set(cov)) and sorted(cov) == sorted(fed)
    tw = build_tower(tier, ts, list(range(n)), bud, pack_overflow="defer", after_sentence=check)
    assert tw.ledger.header["pack_overflow"] == "defer"
    for lv in range(len(tw.uppers) + 1):                                          # P-1 per level
        cov = tw.level_covered(lv)
        assert len(cov) == len(set(cov)) and sorted(cov) == sorted(want0(ts, n))
    assert C.ledger_mismatches(tw) == []                                           # O-2
    assert all(b.verify().is_stable_class for b, _ in tw.units())
    again = build_tower(tier, ts, list(range(n)), bud, pack_overflow="defer")      # O-1
    assert again.ledger.to_bytes() == tw.ledger.to_bytes() and again.to_bytes() == tw.to_bytes()
    rp = C.replay_tower(tw.ledger.to_bytes(), ts, tier, list(range(n)), bud, pack_overflow="defer")
    assert rp.to_bytes() == tw.to_bytes()
    with pytest.raises(ValueError):                                                # O-3: the other rule is refused
        C.replay_tower(tw.ledger.to_bytes(), ts, tier, list(range(n)), bud)
    close = build_tower(tier, ts, list(range(n)), bud)
    with pytest.raises(ValueError):
        C.replay_tower(close.ledger.to_bytes(), ts, tier, list(range(n)), bud, pack_overflow="defer")
    C.replay_tower(close.ledger.to_bytes(), ts, tier, list(range(n)), bud)         # its own rule is accepted


def test_cache_key_differs_between_the_rules():
    ts = build_space(_rows(10)).tiers["RUN"]
    bud, sids = pl.budget_level("low"), list(range(10))
    a = build_tower("RUN", ts, sids, bud)
    b = build_tower("RUN", ts, sids, bud, pack_overflow="defer")
    assert a.ledger.header != b.ledger.header and a.ledger.sha256() != b.ledger.sha256()
    C.check_cache_key(a.ledger.header, "RUN", sids, bud)
    C.check_cache_key(b.ledger.header, "RUN", sids, bud, pack_overflow="defer")
    with pytest.raises(ValueError, match="pack_overflow"):
        C.check_cache_key(a.ledger.header, "RUN", sids, bud, pack_overflow="defer")
    with pytest.raises(ValueError, match="pack_overflow"):
        C.check_cache_key(b.ledger.header, "RUN", sids, bud)
    with pytest.raises(ValueError):                                                # only "defer" may be written in a header
        Ledger(dict(a.ledger.header, pack_overflow="close"))


_PROBE_DEFER = _PROBE.replace('[:12]', '[:30]').replace("range(12)", "range(30)").replace(
    'pl.budget_level("low"))', 'pl.Budget(max_states=8), pack_overflow="defer")')


@pytest.mark.parametrize("tier", ["RUN", "WORD"])
def test_defer_byte_identical_across_hash_seeds(tier):
    outs = []
    for seed in ("0", "1", "12345"):
        env = dict(os.environ, PYTHONHASHSEED=seed, PYTHONPATH=ROOT)
        r = subprocess.run([sys.executable, "-c", _PROBE_DEFER, tier], cwd=ROOT, env=env, capture_output=True, text=True)
        assert r.returncode == 0, r.stderr
        outs.append(r.stdout)
    assert outs[0] == outs[1] == outs[2] and outs[0].strip()
