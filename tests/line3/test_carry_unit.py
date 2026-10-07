"""C2 acceptance (docs/LINE3_CARRY_DESIGN.md 9 C2, 3.6 items 1-4, 4.1, 4.2; OP-2 b, OP-3 a, N-05, L-308).

The hand examples are computed by hand in the comments and asserted; the placement search itself is not
re-implemented here: closed classes are checked with placement.verify_class (independent of the search)."""
import json
import os
import subprocess
import sys

import pytest

from verantyx.line3 import carry as C
from verantyx.line3 import placement as pl
from verantyx.line3.carry import (Black, BlackStream, Collapse, Element, Ledger, LocalSpace, Occ, pack,
                                  stream_header, word)
from verantyx.line3.space import build_tier

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def feed(sentences, budget, wake=None):
    """sentences: {sid: [units]} (stream order = dict order).  Returns the BlackStream."""
    led = Ledger(stream_header("T", list(sentences), budget))
    bs = BlackStream("T", budget, led, wake=wake)
    for s, us in sentences.items():
        bs.feed_sentence(s, [Occ(s, i, u) for i, u in enumerate(us)])
    return bs


def kinds(bs):
    return [e["kind"] for e in bs.ledger.events()]


# ---------------------------------------------------------------- hand example 1: the closing point
# Stream s0 = [a b], s1 = [c d]; budget max_class = 1 (a tied class of 2 or more is "not settled", OP-3 a).
# Weights are (n, p) with the outer element first (I-04); every pair inside a sentence has n = 1.
#  s0: a is the centre.  b: the arm b / centre a scores (1, 0); the swap (b centre, a arm) scores (1, 1)
#      because p(a, b) = 1 (a is before b), so the class is {b centre, a arm}: ONE state.
#  s1: c has no shared sentence with a or b (all weights 0): it lands on an arm, one state again
#      ({b centre; a, c arms}, key (1, 1)).
#      d: n(c, d) = 1, p(c, d) = 1.  Centre d with c as an arm scores (1, 1) (c before d), the same key
#      as centre b with a as an arm (1, 1).  So after d two different states tie -> class size 2 > 1
#      -> collapse at d (OP-3 a).
# OP-2 (b): d collapsed in the middle of s1, so the black goes back to the boundary before s1 (c is
# dropped again), closes with scope {s0} and class {b centre, a arm}; s1 is replayed whole into U0:1.
def test_hand_example_closing_point_and_replay_of_the_whole_sentence():
    bs = feed({0: ["a", "b"], 1: ["c", "d"]}, pl.Budget(max_class=1))
    assert len(bs.closed) == 1
    u0 = bs.closed[0]
    assert u0.unit == "U0:0" and u0.reason == "max_class"
    assert u0.black.space.sids == (0,)                              # only s0
    assert [(o.sid, o.pos, o.unit) for o in u0.black.space.scope] == [(0, 0, "a"), (0, 1, "b")]
    assert u0.black.state == (("b", None, None, None, None, None, "a"),) and u0.black.L == 1
    assert u0.pack.vocab == frozenset(("a", "b")) and u0.pack.id == "P1:0" and u0.pack.unit == "U0:0"
    u1 = bs.black                                                    # still open (L-310)
    assert u1.unit == "U0:1" and u1.space.sids == (1,)
    assert {e.id for e in u1.space.elements} == {"c", "d"}
    assert u1.state == (("d", None, None, None, None, None, "c"),)   # d centre, c arm: (1, 1) beats (1, 0)


def test_hand_example_ledger_has_a_seq_on_every_event_and_names_the_restore_point():
    bs = feed({0: ["a", "b"], 1: ["c", "d"]}, pl.Budget(max_class=1))
    ev = bs.ledger.events()
    assert [e["seq"] for e in ev] == list(range(1, len(ev) + 1))     # every event, 1-based (owner after C1)
    assert [e["kind"] for e in ev] == ["open", "backup", "admit", "admit", "backup", "admit", "rollback",
                                       "close", "pack", "open", "admit", "admit"]
    backup_s1 = ev[4]
    assert backup_s1["item"] == 1 and backup_s1["class_size"] == 1
    rb, close = ev[6], ev[7]
    assert rb["to"] == backup_s1["seq"] == 5                         # restored to the sentence boundary
    assert rb["occ"] == [1, 1] and rb["item"] == "d" and rb["budget_reason"] == "max_class"
    assert close["to"] == 5 and close["occ"] == [1, 1]
    assert ev[8]["item"] == "P1:0" and ev[8]["group"] == ["a", "b"]
    assert ev[9]["unit"] == "U0:1"
    # the one admit of s1 before the collapse was c (kept in the ledger as a record, then undone by the rollback)
    assert ev[5]["item"] == "c" and ev[10]["item"] == "c" and ev[11]["item"] == "d"
    assert all("float" not in repr(type(v)) for e in ev for v in e.values())
    assert Ledger.from_bytes(bs.ledger.to_bytes()).to_bytes() == bs.ledger.to_bytes()


def test_restored_state_equals_the_state_before_the_sentence():
    """N-05: the closed black equals what feeding only the earlier sentences gives."""
    big = feed({0: ["a", "b"], 1: ["c", "d"]}, pl.Budget(max_class=1))
    only = feed({0: ["a", "b"]}, pl.Budget(max_class=1))
    assert big.closed[0].black.state == only.black.state
    assert big.closed[0].black.space.to_bytes() == only.black.space.to_bytes()


# ---------------------------------------------------------------- split of a sentence that does not fit
# max_states = 1: the first element of a black is free (L-351), but every later admission needs at least
# 2 states (re-settle = one scan state for the start + one for the class) -> every black holds ONE unit.
# s0 = [a b]: a fits, b does not fit even the (non-empty, same-sentence) black.  The black held nothing
# before s0, so this is the empty-at-start case: the sentence is split after a.  Hand result: four blacks
# a | b | c | d, split events at b and at d, a backup + rollback to the boundary for c.
def test_split_of_a_sentence_that_does_not_fit_an_empty_black():
    bs = feed({0: ["a", "b"], 1: ["c", "d"]}, pl.Budget(max_states=1))
    assert [cb.black.space.sids for cb in bs.closed] == [(0,), (0,), (1,)]
    assert [sorted(cb.pack.vocab) for cb in bs.closed] == [["a"], ["b"], ["c"]]
    assert bs.black.space.sids == (1,) and {e.id for e in bs.black.space.elements} == {"d"}
    ev = bs.ledger.events()
    splits = [e for e in ev if e["kind"] == "split"]
    assert [(e["occ"], e["item"]) for e in splits] == [([0, 1], "b"), ([1, 1], "d")]
    assert bs.split_sids == [0, 1]
    for i, e in enumerate(ev):
        if e["kind"] == "split":                                     # rollback (to the last stable event), split, close
            assert ev[i - 1]["kind"] == "rollback" and ev[i + 1]["kind"] == "close"
            assert ev[i - 1]["to"] == ev[i - 2]["seq"] and ev[i - 2]["kind"] == "admit"
    # s1 started in a non-empty black ({b}): c did not fit -> boundary rollback (to the backup), NOT a split
    rbs = [e for e in ev if e["kind"] == "rollback" and e["item"] == "c"]
    assert len(rbs) == 1 and ev[rbs[0]["to"] - 1]["kind"] == "backup"


def test_sentence_scope_is_covered_exactly_once_across_blacks():
    sents = {0: ["a", "b", "c"], 1: ["c", "d", "a"], 2: ["e", "b", "f", "a"]}
    bs = feed(sents, pl.Budget(max_states=1))
    seen = [(o.sid, o.pos, o.unit) for cb in bs.closed for o in cb.black.space.scope]
    seen += [(o.sid, o.pos, o.unit) for o in bs.black.space.scope]
    want = [(s, i, u) for s, us in sents.items() for i, u in enumerate(us)]
    assert sorted(seen) == sorted(want) and len(seen) == len(set(seen))          # P-1 at level 0
    for cb in bs.closed:                                              # pack provenance = the black's scope
        assert cb.pack.own_occ == cb.black.space.scope


# ---------------------------------------------------------------- progress guarantee (L-308)
def test_progress_even_with_a_zero_budget():
    """max_states = 0: nothing that needs a search can pass, yet every black accepts its first element."""
    sents = {0: ["a", "b", "a2"], 1: ["a", "c"], 2: ["b", "c", "d", "a"]}
    bs = feed(sents, pl.Budget(max_states=0))
    n_occ = sum(len(v) for v in sents.values())
    assert len(bs.closed) + 1 == n_occ                               # one unit per black
    assert all(cb.black.n_elements == 1 for cb in bs.closed)
    assert sum(cb.black.space.N and 1 for cb in bs.closed) == len(bs.closed)
    adm = [e for e in bs.ledger.events() if e["kind"] == "admit"]
    assert len(adm) == n_occ and all(e["work"] == {"states": 0, "moves": 0} for e in adm)


def test_failed_admission_changes_nothing():
    b = Black.new("U", "T", pl.Budget(max_states=1))
    b1, w1 = b.admit([Occ(0, 0, "a")], [word("a")])
    assert w1 == {"states": 0, "moves": 0}
    before = (b1.space.to_bytes(), b1.state, b1.L)
    with pytest.raises(Collapse) as ei:
        b1.admit([Occ(0, 1, "b")], [word("b")])
    assert ei.value.reason == "max_states" and ei.value.states >= 1
    assert b1.n_elements == 1 and b1.space.N == 1 and len(b1.space.scope) == 1
    assert (b1.space.to_bytes(), b1.state, b1.L) == before
    assert b.is_empty and b.state == ()


# ---------------------------------------------------------------- 3.6 items 1-3: re-settle on a word already seated
def test_a_repeated_word_is_an_admission_and_resettles_the_class():
    """L-353.  s0 = [a b], s1 = [b a]: in s1 b comes before a, so p(b, a) = 1 now matches p(a, b) = 1:
    (n, p) of the pair is (2, 1) either way round and the class must be re-settled and stay a fixed point."""
    bs = feed({0: ["a", "b"], 1: ["b", "a"]}, pl.Budget())
    assert len(bs.closed) == 0
    sp = bs.black.space
    assert sp.n_pair("a", "b") == 2 and sp.p_pair("a", "b") == 1 and sp.p_pair("b", "a") == 1
    adm = [e for e in bs.ledger.events() if e["kind"] == "admit"]
    assert [e["group"] for e in adm] == [["a"], ["b"], [], []]       # b, a of s1 are not new elements
    # hand: after s1 both arrangements (a centre, b arm) and (b centre, a arm) score (2, 1) -> class of 2.
    # Without the re-settle the class would stay {b centre, a arm} and not be closed under equal-key moves.
    assert sorted(bs.black.state) == [("a", None, None, None, None, None, "b"), ("b", None, None, None, None, None, "a")]
    assert bs.black.verify().is_stable_class


# ---------------------------------------------------------------- every closed class is a fixed point
def _s300_rows(n):
    with open(os.path.join(ROOT, "experiments", "line3", "data", "S300.jsonl"), encoding="utf-8") as f:
        return [json.loads(l)["sent"] for l in f][:n]


@pytest.mark.parametrize("tier", ["RUN", "WORD"])
def test_every_closed_class_is_a_fixed_point_for_all_members(tier):
    from verantyx.line3.space import build_space
    ts = build_space([{"sent": t} for t in _s300_rows(14)]).tiers[tier]
    bud = pl.budget_level("low")
    led = Ledger(stream_header(tier, list(range(14)), bud))
    bs = BlackStream(tier, bud, led)
    bs.feed_tier(ts, range(14))
    assert len(bs.closed) >= 2
    for cb in list(bs.closed) + [bs.black]:
        r = cb.verify()
        assert r.is_stable_class and r.members_fixed_points and r.closed and r.one_key
        assert r.size == len(cb.black.state if hasattr(cb, "black") else cb.state)
    # incremental space == from-scratch space (I-1) for every closed black
    for cb in bs.closed:
        sp = cb.black.space
        assert sp.to_bytes() == LocalSpace.build(sp.scope, sp.elements, sp.tier).to_bytes()
        assert sp.sha256() == LocalSpace.build(sp.scope, sp.elements, sp.tier).sha256()


# ---------------------------------------------------------------- pack vocab (L-356) and the wake hook (C3 extension points)
def test_pack_vocab_is_new_words_only_and_frozen():
    inh = pack("P1:9", ["a", "old"], C.ORIGIN_INHERITED)

    def wake(black, occ):
        if occ.unit == "a" and not any(e.id == "P1:9" for e in black.space.elements):
            return [inh]
        return []
    bs = feed({0: ["a", "b"], 1: ["c", "d"], 2: ["e", "f", "a"]}, pl.Budget(max_states=6), wake=wake)
    holders = [cb for cb in bs.closed if "P1:9" in {e.id for e in cb.black.space.elements}]
    assert holders                                                   # the woken pack sat in a closed black
    u0 = holders[0]
    assert "a" in u0.pack.vocab and not {"old", "P1:9"} & u0.pack.vocab   # inherited adds no words (L-312)
    adm = [e for e in bs.ledger.events() if e["kind"] == "admit" and e["activated"]]
    assert adm[0]["activated"] == ["P1:9"] and adm[0]["group"] == ["a", "P1:9"]
    assert all(cb.verify().is_stable_class for cb in holders)


def test_activation_is_deferred_when_the_first_group_does_not_fit_an_empty_black():
    inh = pack("P1:9", ["a", "old"], C.ORIGIN_INHERITED)
    bs = feed({0: ["a"]}, pl.Budget(max_states=1), wake=lambda b, o: [inh])
    ev = bs.ledger.events()
    assert [e["kind"] for e in ev] == ["open", "backup", "activation_deferred", "admit"]
    assert ev[2]["group"] == ["P1:9"] and ev[3]["activated"] == [] and ev[3]["group"] == ["a"]
    assert {e.id for e in bs.black.space.elements} == {"a"}          # the pack stayed asleep


def test_first_group_of_two_elements_settles_to_a_fixed_point():
    inh = pack("P1:9", ["a", "old"], C.ORIGIN_INHERITED)
    bs = feed({0: ["a", "b"]}, pl.Budget(), wake=lambda b, o: [inh] if o.unit == "a" else [])
    assert bs.black.n_elements == 3 and bs.black.verify().is_stable_class


# ---------------------------------------------------------------- small things
def test_empty_sentence_writes_no_event_and_a_duplicate_unit_raises():
    bs = feed({}, pl.Budget())
    n = len(bs.ledger)
    bs.feed_sentence(5, [])
    assert len(bs.ledger) == n
    bs2 = feed({0: ["a"]}, pl.Budget())
    with pytest.raises(ValueError):
        bs2.feed_sentence(0, [Occ(0, 1, "a")])                        # L-324: (sid, unit) already in the scope
    with pytest.raises(ValueError):
        bs2.feed_sentence(3, [Occ(4, 0, "x")])                        # an occurrence of another sentence


def test_timing_is_kept_outside_the_ledger():
    t = [0.0]

    def clock():
        t[0] += 1.0
        return t[0]
    led = Ledger(stream_header("T", [0], pl.Budget()))
    bs = BlackStream("T", pl.Budget(), led, clock=clock)
    bs.feed_sentence(0, [Occ(0, 0, "a"), Occ(0, 1, "b")])
    assert [s for _, s in bs.event_secs] == [1.0, 1.0] and [q for q, _ in bs.event_secs] == [3, 4]
    assert b"1.0" not in led.to_bytes()


def test_header_records_the_choices_and_a_custom_budget():
    h = stream_header("T", [3, 1, 2], pl.Budget(max_class=7, max_states=8, max_moves=9))
    assert h["build_level"] == "max_class=7,max_states=8,max_moves=9"
    assert "OP-2(b)" in h["admission"] and "OP-3(a)" in h["instability"]
    assert stream_header("T", [3, 1, 2], pl.budget_level("mid"))["build_level"] == "mid"
    assert h["order_sha256"] == C.order_sha256([3, 1, 2]) != C.order_sha256([1, 2, 3])


# ---------------------------------------------------------------- determinism
_PROBE = r"""
import json, sys
from verantyx.line3 import carry as C, placement as pl
from verantyx.line3.space import build_space
rows = [json.loads(l)["sent"] for l in open("experiments/line3/data/S300.jsonl", encoding="utf-8")][:10]
tier = sys.argv[1]
ts = build_space([{"sent": t} for t in rows]).tiers[tier]
bud = pl.budget_level("low")
led = C.Ledger(C.stream_header(tier, list(range(10)), bud))
bs = C.BlackStream(tier, bud, led)
bs.feed_tier(ts, range(10))
print(led.sha256(), len(led), len(bs.closed), bs.black.space.sha256())
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


def test_verify_detects_a_class_that_is_not_a_fixed_point():
    """The checker is independent of the search: a hand-broken state (centre a instead of b, key (1, 0)
    instead of (1, 1)) is reported as not stable."""
    bs = feed({0: ["a", "b"]}, pl.Budget())
    good = bs.black
    assert good.state == (("b", None, None, None, None, None, "a"),) and good.verify().is_stable_class
    bad = Black(good.unit, good.level, good.space, (("a", None, None, None, None, None, "b"),), good.L, good.budget)
    r = bad.verify()
    assert not r.members_fixed_points and not r.is_stable_class
