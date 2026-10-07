"""C1 acceptance (docs/LINE3_CARRY_DESIGN.md section 9 C1, 3.5, 3.7, 6.2 I-1 / I-2): local space and ledger."""
import json
import os
import random
import subprocess
import sys
from fractions import Fraction

import pytest

from verantyx.line3 import carry as C
from verantyx.line3 import placement as pl
from verantyx.line3.carry import Element, Ledger, LocalSpace, Occ, pack, word
from verantyx.line3.space import build_tier

# design 4.5: the stream and the pack P1:0 (vocab of U0:0 = scope s0, s1)
S = {
    0: ["富士山", "静岡県", "山梨県", "山"],
    1: ["静岡県", "県庁", "静岡市"],
    2: ["山梨県", "県庁", "甲府市"],
    3: ["富士山", "噴火", "1707年"],
    4: ["甲府市", "武田", "城"],
}
P10 = pack("P1:0", ["富士山", "静岡県", "山梨県", "山", "県庁", "静岡市"], C.ORIGIN_INHERITED)


def occs(sids):
    return [Occ(s, i, u) for s in sids for i, u in enumerate(S[s])]


def u01():
    """U0:1 of the design example: scope s2, s3; seats: new words + the woken inherited pack."""
    el = [P10] + [word(u) for s in (2, 3) for u in S[s]]
    return LocalSpace.build(occs([2, 3]), el, "RUN")


# ---------------------------------------------------------------- 3.5 definition
def test_local_space_matches_hand_computation_of_design_4_5():
    ls = u01()
    assert ls.N == 2 and ls.sids == (2, 3)
    assert ls.n("P1:0") == 2 and ls.r0("P1:0") == Fraction(1)
    assert ls.n_pair("P1:0", "甲府市") == 1
    assert ls.p_pair("P1:0", "甲府市") == 1 and ls.p_pair("甲府市", "P1:0") == 0
    assert ls.n("山梨県") == 1 and ls.r0("山梨県") == Fraction(1, 2)
    # P1:0 is in s2 at position 0 (山梨県) and in s3 at position 0 (富士山); its past (s0, s1) is not counted
    assert ls.first_pos["P1:0"] == {0: 0, 1: 0}
    assert ls.sentence_elements(0) == ("P1:0", "山梨県", "県庁", "甲府市")


def test_red_unit_local_space_matches_design_4_5():
    # U1:0: scope = union of the children's scopes (s0..s3); seats = the two child packs (new at level 1).
    # P1:1's vocab = the NEW words of U0:1 only (L-312): P1:0's words are not in it.
    p11 = pack("P1:1", ["山梨県", "県庁", "甲府市", "富士山", "噴火", "1707年"], C.ORIGIN_NEW)
    p10 = pack("P1:0", P10.vocab, C.ORIGIN_NEW)
    ls = LocalSpace.build(occs([0, 1, 2, 3]), [p10, p11], "RUN")
    assert ls.N == 4 and ls.n("P1:0") == 4 and ls.n("P1:1") == 4 and ls.n_pair("P1:0", "P1:1") == 4
    # s1: P1:0 at 0 (静岡県), P1:1 at 1 (県庁); s0, s2, s3: both at 0 -> strict, neither side (L-311)
    assert ls.p_pair("P1:0", "P1:1") == 1 and ls.p_pair("P1:1", "P1:0") == 0
    # design 5.5: n(甲府市, P1:0) = 1 (s2) as a question word on the red unit
    assert ls.n_query("甲府市", "P1:0") == 1 and ls.n_query("甲府市", "P1:1") == 1


def test_energy_is_exact_fraction_and_uses_scope_only():
    ls = u01()
    e = ls.energy("甲府市", ["甲府市", "県庁"])          # r0 + (n(甲府市,甲府市) + n(県庁,甲府市)) / N
    assert e == Fraction(1 + 1 + 1, 2) and isinstance(e, Fraction)
    assert ls.energy("甲府市", ["武田"]) == Fraction(1, 2)       # 武田 is outside the scope: 0 (like L-52)
    assert ls.energy("甲府市", ["甲府市", "甲府市"]) == ls.energy("甲府市", ["甲府市"])   # the query is a set


def test_empty_scope_has_no_evidence():
    ls = LocalSpace.build([], [word("a")])
    assert ls.N == 0 and ls.r0("a") == 0 and ls.energy("a", ["a"]) == 0     # L-327
    assert ls.to_tier().r0("a") == 0                                         # L-334: the bridge agrees


def test_untouched_element_has_zero_counts():
    ls = LocalSpace.build(occs([2]), [word("山梨県"), word("ゼロ")])
    assert ls.n("ゼロ") == 0 and ls.n_pair("ゼロ", "山梨県") == 0 and ls.r0("ゼロ") == 0   # L-326


# ---------------------------------------------------------------- exact comparison at the same position
def test_equal_position_counts_for_neither_side():
    a = pack("Pa", ["x", "y"], C.ORIGIN_NEW)
    b = pack("Pb", ["x", "z"], C.ORIGIN_INHERITED)
    ls = LocalSpace.build([Occ(0, 0, "x"), Occ(0, 1, "y"), Occ(0, 2, "z")], [a, b])
    assert ls.first_pos["Pa"] == {0: 0} and ls.first_pos["Pb"] == {0: 0}
    assert ls.p_pair("Pa", "Pb") == 0 and ls.p_pair("Pb", "Pa") == 0 and ls.n_pair("Pa", "Pb") == 1   # L-311
    assert ls.p_pair("Pa", "Pa") == 0
    t = ls.to_tier()
    assert t.p_pair("Pa", "Pb") == 0 and t.p_pair("Pb", "Pa") == 0


def test_position_is_exact_integer_and_min_over_vocab():
    ls = LocalSpace.build([Occ(7, 5, "y"), Occ(7, 2, "x"), Occ(7, 9, "w")], [pack("P", ["x", "y"], C.ORIGIN_NEW), word("w")])
    assert ls.first_pos["P"] == {0: 2}
    assert all(type(p) is int for f in ls.first_pos.values() for p in f.values())
    assert ls.p_pair("P", "w") == 1 and ls.p_pair("w", "P") == 0


def test_no_float_anywhere_in_space_bytes():
    doc = json.loads(u01().to_bytes().decode("utf-8"), parse_float=lambda s: (_ for _ in ()).throw(AssertionError(s)))
    assert doc["r0"]["P1:0"] == "1/1" and doc["r0"]["山梨県"] == "1/2"


# ---------------------------------------------------------------- I-1: rebuild == incremental
def _random_case(rng):
    sids = rng.sample(range(40), rng.randint(2, 7))
    stream, words = [], [chr(0x3042 + i) for i in range(9)]
    for s in sids:
        us = rng.sample(words, rng.randint(1, 6))
        stream += [Occ(s, i, u) for i, u in enumerate(us)]
    els = [word(w) for w in rng.sample(words, 4)]
    rest = [w for w in words if w not in {e.id for e in els}]
    els += [pack("P%d" % i, rng.sample(words, rng.randint(1, 4)), rng.choice(C.ORIGINS)) for i in range(3)]
    # pack ids are "P0".. and words are single kana: no collision
    return stream, els


def test_incremental_equals_rebuild_byte_for_byte_I1():
    rng = random.Random(20261007)
    for _ in range(60):
        stream, els = _random_case(rng)
        full = LocalSpace.build(stream, els, "WORD")
        # (a) occurrences appended in chunks after the elements
        ls, i = LocalSpace.build([], els, "WORD"), 0
        while i < len(stream):
            k = rng.randint(1, 4)
            ls = ls.with_occurrences(stream[i:i + k])
            i += k
        assert ls.to_bytes() == full.to_bytes()
        # (b) elements added after some occurrences
        cut_o, cut_e = rng.randint(0, len(stream)), rng.randint(0, len(els))
        ls = LocalSpace.build(stream[:cut_o], els[:cut_e], "WORD").with_occurrences(stream[cut_o:]).with_elements(els[cut_e:])
        assert ls.to_bytes() == full.to_bytes()
        ls = LocalSpace.build(stream[:cut_o], els[:cut_e], "WORD").with_elements(els[cut_e:]).with_occurrences(stream[cut_o:])
        assert ls.to_bytes() == full.to_bytes()


def test_appending_an_event_does_not_break_existing_counts():
    base = u01()
    before = base.to_bytes()
    n_before = {x: base.n(x) for x in ("P1:0", "山梨県", "県庁", "甲府市", "富士山")}
    # a NEW sentence: the old object is untouched, untouched elements keep their counts
    nxt = base.with_occurrences([Occ(4, 0, "甲府市"), Occ(4, 1, "武田")])
    assert base.to_bytes() == before and base.N == 2
    assert nxt.N == 3
    assert nxt.n("山梨県") == n_before["山梨県"] and nxt.n("富士山") == n_before["富士山"]
    assert nxt.n("甲府市") == 2 and nxt.n("P1:0") == 2          # P1:0 holds no word of s4's new occurrences
    assert nxt.n_pair("県庁", "山梨県") == base.n_pair("県庁", "山梨県")
    # an occurrence in an EXISTING sentence changes only what it touches (and r0 through N stays)
    more = base.with_occurrences([Occ(3, 3, "県庁")])
    assert more.N == 2 and more.n("県庁") == 2 and more.n("甲府市") == 1 and more.n("山梨県") == 1


def test_duplicates_and_collisions_are_errors_not_skips():
    ls = u01()
    with pytest.raises(ValueError):
        ls.with_occurrences([Occ(2, 7, "山梨県")])                 # (sid, unit) already in scope (L-324)
    with pytest.raises(ValueError):
        LocalSpace.build([Occ(0, 0, "a"), Occ(0, 1, "a")], [word("a")])
    with pytest.raises(ValueError):
        ls.with_elements([word("県庁")])                          # duplicate element id (L-325)
    with pytest.raises(ValueError):
        LocalSpace.build([Occ(0, 0, "P1:0")], [pack("P1:0", ["P1:0"], C.ORIGIN_NEW)])   # pack id equals a word surface
    with pytest.raises(ValueError):
        Element("e", frozenset())
    with pytest.raises(ValueError):
        Occ(0, -1, "a")
    with pytest.raises(ValueError):
        Occ(0, 1.5, "a")


# ---------------------------------------------------------------- I-2: a poisoned past does not change the counts
def _corpus(poison):
    texts = ["あいうえお", "かきくけこ", "あかさたな", "いうかきさ", "えおくけし", "あいかさと", "うえくこす", "おかたなひ"]
    if poison:                                                    # rewrite every sentence OUTSIDE the scope (and add query words)
        for sid in (0, 1, 5, 6, 7):
            texts[sid] = "あいうえおかきくけこひ" + texts[sid]
    return build_tier("CHAR", texts, None)


def test_poisoned_past_does_not_change_counts_I2():
    scope_sids = (2, 3, 4)
    vocab_past = ["あ", "い", "う", "え", "お", "か", "き", "く", "け", "こ"]      # an inherited pack of the poisoned past
    results = []
    for poison in (False, True):
        tier = _corpus(poison)
        stream = [o for s in scope_sids for o in C.occurrences_of(tier, s)]
        us = list(dict.fromkeys(u for s in scope_sids for u in tier.sentence_units[s] if u != "さ"))
        # P1:1: an inherited pack whose past (と, す, ひ) is outside the scope and which only s4 (し) touches
        els = ([pack("P1:0", vocab_past, C.ORIGIN_INHERITED), pack("P1:1", ["と", "す", "ひ", "し"], C.ORIGIN_INHERITED)]
               + [word(u) for u in us])
        ls = LocalSpace.build(stream, els, "CHAR")
        w = pl.Weights(ls.to_tier())
        keys = {(x, y): w(x, y) for x in ls.first_pos for y in ls.first_pos}
        query = ["あ", "か", "ひ"]                                # ひ: a query word that occurs only in the (poisoned) past
        # absolute checks (equal in both runs would not catch a leak that is the same in both runs)
        assert ls.N == 3 and ls.n("P1:1") == 1 and ls.r0("P1:1") == Fraction(1, 3)
        assert all(ls.n_query("ひ", x) == 0 for x in ls.first_pos)   # the past's ひ is never evidence
        energies = {x: ls.energy(x, query) for x in ls.first_pos}
        results.append((ls.to_bytes(), keys, energies, [ls.n_query(q, x) for q in query for x in ls.first_pos]))
    assert results[0] == results[1]
    # sanity: the poison really changed the global counts (otherwise the test proves nothing)
    assert _corpus(False).postings["あ"] != _corpus(True).postings["あ"]


def test_inherited_pack_is_counted_only_through_the_scope():
    # the pack's own past (vocab words that never occur in this scope) adds nothing
    ls = LocalSpace.build(occs([2]), [pack("P", ["山梨県", "富士山", "静岡市", "山"], C.ORIGIN_INHERITED), word("甲府市")])
    assert ls.N == 1 and ls.n("P") == 1 and ls.n_pair("P", "甲府市") == 1
    ls2 = LocalSpace.build(occs([2]), [pack("P", ["山梨県"], C.ORIGIN_INHERITED), word("甲府市")])
    assert ls2.first_pos["P"] == ls.first_pos["P"]


# ---------------------------------------------------------------- bridge to placement (read-only use)
def test_to_tier_weights_equal_direct_counts():
    ls = u01()
    t = ls.to_tier()
    assert t.N == ls.N and t.postings["P1:0"] == (0, 1)
    w = pl.Weights(t)
    ids = [e.id for e in ls.elements]
    for x in ids:
        for y in ids:
            assert w(x, y) == (ls.n_pair(x, y), ls.p_pair(x, y))
        assert t.r0(x) == ls.r0(x)


# ---------------------------------------------------------------- 3.7 ledger
HEADER = {"format": C.LEDGER_FORMAT, "data_sha256": "ab" * 32, "tier": "RUN", "unit_filter": "default",
          "order": {"kind": "file", "seed": None}, "order_sha256": C.order_sha256([0, 1, 2]),
          "build_level": "mid", "admission": "OP-2(b)", "copy": "OP-1(a)", "instability": "OP-3(a)",
          "code_commit": "0" * 40}


def _ledger():
    led = Ledger(HEADER)
    led.append("admit", level=0, unit="U0:0", item="山梨県", occ=[2, 0], group=["山梨県", "P1:0"], class_size=3, L=2,
               stop="settled", work={"states": 10, "moves": 4})
    led.append("close", level=0, unit="U0:0", budget_reason="budget:max_states")
    led.append("activate", level=0, unit="U0:1", item="P1:0", activated=["P1:0"])
    return led


def test_ledger_is_canonical_json_lines():
    led = _ledger()
    raw = led.to_bytes()
    lines = raw.decode("utf-8").split("\n")
    assert lines[-1] == "" and len(lines) == 5
    for l in lines[:-1]:
        d = json.loads(l)
        assert l == json.dumps(d, sort_keys=True, ensure_ascii=False, separators=(",", ":"))     # L-319
    assert "山梨県" in raw.decode("utf-8") and b"\\u" not in raw                 # UTF-8, not escaped
    assert [e["seq"] for e in led.events()] == [1, 2, 3]
    assert Ledger.from_bytes(raw).to_bytes() == raw and Ledger.from_bytes(raw).sha256() == led.sha256()


def test_appending_an_event_keeps_earlier_lines_byte_identical():
    led = _ledger()
    before = led.to_bytes()
    led.append("pack", level=1, unit="U1:0", item="P1:0")
    assert led.to_bytes().startswith(before) and len(led) == 4


def test_ledger_rejects_floats_unknown_kinds_gaps_and_noncanonical_bytes():
    led = _ledger()
    with pytest.raises(ValueError):
        led.append("admit", work={"states": 1.5})
    with pytest.raises(ValueError):
        led.append("admit", work={"x": Fraction(1, 2)})
    with pytest.raises(ValueError):
        led.append("bogus")
    with pytest.raises(ValueError):
        led.append("admit", nonsense=1)
    with pytest.raises(ValueError):
        led.append("admit", occ=[1])
    assert len(led) == 3                                              # nothing half-written
    raw = led.to_bytes()
    lines = raw.split(b"\n")
    with pytest.raises(ValueError):                                   # swapped events -> seq gap
        Ledger.from_bytes(b"\n".join([lines[0], lines[2], lines[1], lines[3], b""]))
    with pytest.raises(ValueError):                                   # pretty-printed (not canonical)
        Ledger.from_bytes(raw.replace(b'"seq":1,', b'"seq": 1,'))
    with pytest.raises(ValueError):
        Ledger.from_bytes(raw[:-1])
    bad = dict(HEADER, order={"kind": "alphabetical", "seed": None})
    with pytest.raises(ValueError):
        Ledger(bad)
    with pytest.raises(ValueError):
        Ledger({k: v for k, v in HEADER.items() if k != "tier"})
    with pytest.raises(ValueError):
        Ledger(dict(HEADER, extra=1))


def test_order_sha256_depends_on_order():
    assert C.order_sha256([0, 1, 2]) != C.order_sha256([2, 1, 0])
    assert C.order_sha256([0, 1, 2]) == C.order_sha256((0, 1, 2))


# ---------------------------------------------------------------- hash-seed independence (O-1 style)
_SCRIPT = r"""
import sys
sys.path.insert(0, %r)
from tests.line3.test_carry_space import u01, _ledger
sys.stdout.buffer.write(u01().to_bytes() + b"\n" + _ledger().to_bytes())
"""


def test_bytes_do_not_depend_on_hash_seed():
    root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    outs = []
    for seed in ("0", "1", "12345"):
        env = dict(os.environ, PYTHONHASHSEED=seed)
        r = subprocess.run([sys.executable, "-c", _SCRIPT % root], env=env, cwd=root, capture_output=True, check=True)
        outs.append(r.stdout)
    assert outs[0] == outs[1] == outs[2] and outs[0]
    here = u01().to_bytes() + b"\n" + _ledger().to_bytes()
    assert outs[0] == here
