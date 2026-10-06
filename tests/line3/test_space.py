"""T1 space acceptance (docs/LINE3_DESIGN.md section 9 T1)."""
import hashlib
import itertools
import json
import os
import random
import re
import subprocess
import sys
import unicodedata
from fractions import Fraction

import pytest

from verantyx.line3 import space as S
from verantyx.line3.space import CHAR, RUN, TIERS, WORD
from verantyx.line3.space import build_from_jsonl as _build_from_jsonl
from verantyx.line3.space import build_space as _build_space


# Since L-150 the default space drops function / question words (V2).  The tests below describe the
# OLD space (I-22: function words are units) and run it through the explicit option unit_filter=None;
# the tests of the default space are at the end of this file.
def build_space(rows, unit_filter=None):
    return _build_space(rows, unit_filter)


def build_from_jsonl(path, unit_filter=None):
    return _build_from_jsonl(path, unit_filter)

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
S300 = os.path.join(ROOT, "experiments/line3/data/S300.jsonl")
S3000 = os.path.join(ROOT, "experiments/line3/data/S3000.jsonl")
PY = sys.executable


@pytest.fixture(scope="module")
def sp():
    return build_from_jsonl(S300)


def test_loaded_from_clone():
    assert S.__file__.startswith(ROOT + "/verantyx/line3/")
    import verantyx.lang
    assert verantyx.lang.__file__.startswith(ROOT + "/")


def test_data_is_manifest_file():
    m = json.load(open(os.path.join(ROOT, "experiments/line3/data_manifest.json")))
    for k, p in (("S300", S300), ("S3000", S3000)):
        assert hashlib.sha256(open(p, "rb").read()).hexdigest() == m["files"][k]["sha256"]


def test_three_tiers_independent(sp):
    assert tuple(sp.tiers) == TIERS == (RUN, WORD, CHAR)
    assert sp.N == 300 and all(sp.tiers[t].N == 300 for t in TIERS)


# ---- determinism ------------------------------------------------------------
def test_byte_identical_two_builds(sp):
    assert build_from_jsonl(S300).to_bytes() == sp.to_bytes()


@pytest.mark.parametrize("seed", ["0", "1", "12345"])
def test_hashseed_independent(sp, seed):
    code = ("from verantyx.line3.space import build_from_jsonl;"
            "print(build_from_jsonl(%r, None).sha256())" % S300)
    env = dict(os.environ, PYTHONHASHSEED=seed, PYTHONPATH=ROOT, PYTHONDONTWRITEBYTECODE="1")
    out = subprocess.run([PY, "-c", code], env=env, capture_output=True, text=True, check=True).stdout.strip()
    assert out == sp.sha256()


def test_cooccurrence_key_order_hashseed_independent(sp):
    code = ("from verantyx.line3.space import build_from_jsonl, WORD;"
            "s=build_from_jsonl(%r, None).tiers[WORD];"
            "import json;print(json.dumps([list(s.cooccurrence(u)) for u in s.units()[:150]]))" % S300)
    outs = set()
    for seed in ("0", "1", "12345"):
        env = dict(os.environ, PYTHONHASHSEED=seed, PYTHONPATH=ROOT, PYTHONDONTWRITEBYTECODE="1")
        outs.add(subprocess.run([PY, "-c", code], env=env, capture_output=True, text=True,
                                check=True).stdout)
    assert len(outs) == 1


def test_tier_counts_acceptance(sp):
    assert S.tier_counts(sp) == {"sentences": 300, RUN: 2175, WORD: 2444, CHAR: 1164}
    assert S.tier_counts(build_from_jsonl(S3000)) == {"sentences": 3000, RUN: 16193, WORD: 13132, CHAR: 2428}


def test_tier_counts_cli():
    env = dict(os.environ, PYTHONPATH=ROOT, PYTHONDONTWRITEBYTECODE="1")
    out = subprocess.run([PY, "-m", "verantyx.line3.space", S300, "--keep-function-words"], env=env,
                         capture_output=True, text=True, check=True).stdout
    assert json.loads(out.split(" ", 1)[1]) == {"sentences": 300, RUN: 2175, WORD: 2444, CHAR: 1164}   # old space
    out = subprocess.run([PY, "-m", "verantyx.line3.space", S300], env=env, capture_output=True,
                         text=True, check=True).stdout
    assert json.loads(out.split(" ", 1)[1]) == {"sentences": 300, RUN: 2033, WORD: 2278, CHAR: 1094}   # default


def test_run_tier_question_word_absorbed():
    # documents the actual behaviour (OPEN owner question): not a separate RUN unit
    assert S.units_run("半田岩はどこにありますか") == ["半田岩", "はどこにありますか"]


# ---- I-22 / N-15: function words, question words, no punctuation -------------
def test_function_and_question_words_are_units():
    s = build_space([{"sent": "遊眠は日本の漫画家。"}, {"sent": "遊眠はどこにある。"}])
    w = s.tiers[WORD]
    for u in ("は", "の", "どこ"):
        assert u in w.postings
    assert s.tiers[WORD].postings["は"] == (0, 1)
    assert "は" in s.tiers[RUN].postings and "の" in s.tiers[RUN].postings
    assert "どこ" in s.tiers[CHAR].postings or "ど" in s.tiers[CHAR].postings
    assert "は" in s.tiers[CHAR].postings and "の" in s.tiers[CHAR].postings


def test_no_punctuation_or_symbols_in_any_tier(sp):
    for t in TIERS:
        for u in sp.tiers[t].postings:
            assert any(unicodedata.category(c)[0] in "LNM" for c in u), (t, u)
    s = build_space([{"sent": "遊眠（ゆうみん）は、日本の漫画家。"}])
    for t in TIERS:
        assert not any(set("（）、。") & set(u) for u in s.tiers[t].postings)


def test_char_tier_is_every_letter_char():
    s = build_space([{"sent": "遊眠は日本の漫画家。"}])
    assert s.tiers[CHAR].sentence_units[0] == tuple("遊眠は日本の漫画家")


# ---- I-06 --------------------------------------------------------------------
def test_r0_exact_fractions(sp):
    for t in TIERS:
        ts = sp.tiers[t]
        for u in ts.units():
            r = ts.r0(u)
            assert type(r) is Fraction
            assert r == Fraction(len(ts.postings[u]), sp.N)
            assert 0 < r <= 1
    doc = json.loads(sp.to_bytes())
    for t in TIERS:
        for e in doc["tiers"][t]["units"]:
            assert re.fullmatch(r"\d+(/\d+)?", e["r0"]), e
            assert Fraction(e["r0"]) == Fraction(e["n"], 300)


def test_r0_hand_computed_tiny_space():
    # 3 sentences in the CHAR tier: "ab", "ac", "a" -> n(a)=3, n(b)=1, n(c)=1, N=3
    t = build_space([{"sent": "ab"}, {"sent": "ac"}, {"sent": "a"}]).tiers[CHAR]
    assert {u: (t.n(u), t.r0(u)) for u in t.units()} == {
        "a": (3, Fraction(1)), "b": (1, Fraction(1, 3)), "c": (1, Fraction(1, 3))}
    assert t.n_pair("a", "b") == 1 and t.n_pair("b", "c") == 0
    assert list(t.cooccurrence("a")) == ["b", "c"] and t.cooccurrence("a") == {"b": 1, "c": 1}


def test_no_floats_in_module():
    src = open(S.__file__, encoding="utf-8").read()
    assert "float(" not in src and "math." not in src


def test_r0_values_on_tiny_space():
    s = build_space([{"sent": "遊眠は日本の漫画家。"}, {"sent": "遊眠は何ですか。"}])
    w = s.tiers[WORD]
    assert w.r0("は") == Fraction(1, 1) and w.r0("遊") == 1
    assert w.r0("の") == Fraction(1, 2)


# ---- trace: every unit goes back to a stored sentence containing it -----------
@pytest.mark.parametrize("t", TIERS)
def test_trace_all_units_S300(sp, t):
    ts = sp.tiers[t]
    assert ts.postings
    for u in ts.units():
        tr = sp.trace(t, u)
        assert len(tr) >= 1
        for sid, text in tr:
            assert text == sp.sentences[sid][0]
            assert u in ts.sentence_units[sid]
            assert u in text                    # independent of the splitter
    # converse: every unit occurrence is registered
    for sid, us in enumerate(ts.sentence_units):
        for u in us:
            assert sid in ts.postings[u]


def test_source_and_text_kept(sp):
    rows = S.load_jsonl(S300)
    assert [r["sent"] for r in rows] == [x[0] for x in sp.sentences]
    assert [r["source"] for r in rows] == [x[1] for x in sp.sentences]


# ---- counts ---------------------------------------------------------------
@pytest.mark.parametrize("t", TIERS)
def test_count_rules(sp, t):
    ts = sp.tiers[t]
    rnd = random.Random(7)
    us = ts.units()
    sets = [set(x) for x in ts.sentence_units]
    # postings recomputed from sentences
    for u in rnd.sample(us, min(60, len(us))):
        assert ts.n(u) == sum(1 for s in sets if u in s)
    pairs = [tuple(rnd.sample(us, 2)) for _ in range(300)]
    for u, v in pairs:
        n_uv = sum(1 for s in sets if u in s and v in s)
        assert ts.n_pair(u, v) == n_uv == ts.n_pair(v, u)          # symmetric, recomputed
        assert n_uv <= min(ts.n(u), ts.n(v))
        p_uv = sum(1 for x in ts.sentence_units
                   if u in x and v in x and x.index(u) < x.index(v))
        assert ts.p_pair(u, v) == p_uv
        assert ts.p_pair(u, v) + ts.p_pair(v, u) == n_uv            # firsts differ => equality, which is <= n
        assert ts.p_pair(u, v) + ts.p_pair(v, u) <= n_uv


def test_cooccurrence_matches_pair_counts(sp):
    ts = sp.tiers[WORD]
    for u in ts.units()[:40:3]:
        co = ts.cooccurrence(u)
        assert u not in co
        for v, c in co.items():
            assert c == ts.n_pair(u, v) == ts.n_pair(v, u)
    u = "は"
    co = ts.cooccurrence(u)
    assert all(ts.n_pair(u, v) == c for v, c in co.items())


def test_n_pair_self_is_n(sp):
    ts = sp.tiers[WORD]
    for u in ts.units()[:30]:
        assert ts.n_pair(u, u) == ts.n(u)


def test_exhaustive_counts_small_space():
    rows = [{"sent": x} for x in ("遊眠は日本の漫画家。", "日本の首都は東京。", "東京は日本にある。", "何ですか。")]
    s = build_space(rows)
    for t in TIERS:
        ts = s.tiers[t]
        for u, v in itertools.permutations(ts.units(), 2):
            sets = [set(x) for x in ts.sentence_units]
            assert ts.n_pair(u, v) == sum(1 for z in sets if u in z and v in z)


# ---- no centre chosen (I-02) -------------------------------------------------
def test_no_centre_stored(sp):
    doc = json.loads(sp.to_bytes())
    assert set(doc) == {"format", "sentences", "tiers"}
    for t in TIERS:
        assert set(doc["tiers"][t]) == {"N", "sentence_units", "units"}
        assert all(set(e) == {"u", "n", "r0", "sids"} for e in doc["tiers"][t]["units"])


# ---- scale -------------------------------------------------------------------
def test_build_S3000():
    s = build_from_jsonl(S3000)
    assert s.N == 3000
    for t in TIERS:
        ts = s.tiers[t]
        assert ts.N == 3000
        for u in ts.units()[:200]:
            assert len(ts.postings[u]) >= 1
    assert s.sha256() == build_from_jsonl(S3000).sha256()


# ---- T1b: append, kind/source, postings union -------------------------------
_ROWS = [
    {"sent": "遊眠は日本の漫画家。", "source": "a"},
    {"sent": "遊眠はどこにある。", "source": "b"},
    {"sent": "東京は日本の首都。", "source": "c"},
]
_NEW = [
    {"sent": "遊眠は何をした。", "source": "mem", "kind": "memory_query"},
    {"sent": "日本の漫画家。", "source": "mem", "kind": "memory_answer"},
    {"sent": "私は東京にいる。", "source": "user", "kind": "memory_user"},
]


def test_append_keeps_existing_and_equals_scratch():
    old = build_space(_ROWS)
    new = old.append(_NEW)
    scratch = build_space(_ROWS + _NEW)
    assert new.to_bytes() == scratch.to_bytes() and new.sha256() == scratch.sha256()
    assert old.N == 3 and new.N == 6                      # old object untouched
    assert new.sentences[:3] == old.sentences
    for t in TIERS:
        o, n = old.tiers[t], new.tiers[t]
        assert n.sentence_units[:3] == o.sentence_units
        for u, v in o.postings.items():                   # old postings are a prefix
            assert n.postings[u][:len(v)] == v
            assert all(s >= 3 for s in n.postings[u][len(v):])
        assert set(o.postings) <= set(n.postings)


def test_append_unchanged_part_of_serialisation():
    old = build_space(_ROWS)
    new = old.append(_NEW)
    do, dn = json.loads(old.to_bytes()), json.loads(new.to_bytes())
    assert dn["sentences"][:3] == do["sentences"]
    for t in TIERS:
        assert dn["tiers"][t]["sentence_units"][:3] == do["tiers"][t]["sentence_units"]
        un = {e["u"]: e for e in dn["tiers"][t]["units"]}
        for e in do["tiers"][t]["units"]:
            assert un[e["u"]]["sids"][:len(e["sids"])] == e["sids"]


def test_append_in_chunks_and_empty():
    one = build_space(_ROWS)
    chunked = one.append(_NEW[:1]).append([]).append(_NEW[1:])
    assert chunked.to_bytes() == build_space(_ROWS + _NEW).to_bytes()
    assert one.append([]) is one


def test_append_on_s300_equals_scratch(sp):
    rows = S.load_jsonl(S300)
    head, tail = build_space(rows[:250]), rows[250:]
    assert head.append(tail).to_bytes() == sp.to_bytes()


def test_kind_and_source(sp):
    assert set(sp.kinds) == {"base"} and len(sp.kinds) == sp.N
    new = build_space(_ROWS).append(_NEW)
    assert new.kinds == ("base",) * 3 + ("memory_query", "memory_answer", "memory_user")
    assert [s for _, s in new.sentences][3:] == ["mem", "mem", "user"]
    doc = json.loads(new.to_bytes())
    assert [e["kind"] for e in doc["sentences"]] == list(new.kinds)
    assert [e["source"] for e in doc["sentences"]][:3] == ["a", "b", "c"]
    assert S.KINDS == ("base", "memory_query", "memory_answer", "memory_user")


def test_unknown_kind_rejected():
    with pytest.raises(ValueError):
        build_space([{"sent": "あ", "kind": "bogus"}])
    with pytest.raises(ValueError):
        build_space(_ROWS).append([{"sent": "あ", "kind": "bogus"}])


def test_kind_changes_bytes_but_not_postings():
    a = build_space([{"sent": "遊眠は日本の漫画家。"}])
    b = build_space([{"sent": "遊眠は日本の漫画家。", "kind": "memory_user"}])
    assert a.sha256() != b.sha256()
    for t in TIERS:
        assert a.tiers[t].postings == b.tiers[t].postings


def test_postings_union():
    s = build_space(_ROWS).append(_NEW)
    w = s.tiers[WORD]
    for t in TIERS:
        ts = s.tiers[t]
        us = ts.units()
        for a, b, c in itertools.islice(itertools.combinations(us, 3), 0, 400, 7):
            got = s.postings_union(t, [a, b, c])
            assert got == tuple(sorted(set(ts.postings[a]) | set(ts.postings[b]) | set(ts.postings[c])))
            assert got == s.postings_union(t, [c, a, b, a])        # order / repeats irrelevant
    assert s.postings_union(WORD, ["は"]) == w.postings["は"]
    assert s.postings_union(WORD, []) == ()
    with pytest.raises(KeyError):
        s.postings_union(WORD, ["は", "存在しない語zzz"])


# ---------------------------------------------------------------- the default space (L-150)
JA2 = [{"sent": "半田岩は徳島県にある。"}, {"sent": "遊眠は漫画家である。"}, {"sent": "半田岩はどこにありますか。"},
       {"sent": "遊眠は何ですか。"}]


def test_default_space_drops_function_and_question_words_old_option_keeps_them():
    new = _build_space(JA2)
    old = _build_space(JA2, unit_filter=None)
    assert new.N == old.N and new.sentences == old.sentences           # sentences stay and count in N
    for tn in ("RUN", "WORD"):
        assert "は" in old.tiers[tn].postings and "は" not in new.tiers[tn].postings
    assert "どこ" in old.tiers["WORD"].postings and "どこ" not in new.tiers["WORD"].postings
    assert "半田岩" in new.tiers["RUN"].postings and "遊眠" in new.tiers["RUN"].postings
    assert "はどこにありますか" in old.tiers["RUN"].postings and "はどこにありますか" not in new.tiers["RUN"].postings
    assert "は" not in new.tiers["CHAR"].postings and "半" in new.tiers["CHAR"].postings
    for tn in TIERS:                                                    # a filtered unit is in no sentence's list
        ps = new.tiers[tn].postings
        assert all(u in ps for us in new.tiers[tn].sentence_units for u in us)
        assert new.tiers[tn].unit_filter is not None and old.tiers[tn].unit_filter is None


def test_default_space_append_equals_building_from_scratch():
    a, b = JA2[:2], JA2[2:]
    chunked = _build_space(a).append(b)
    assert chunked.to_bytes() == _build_space(a + b).to_bytes()
    assert "は" not in chunked.tiers["WORD"].postings and "どこ" not in chunked.tiers["WORD"].postings


def test_default_space_is_hashseed_independent():
    code = ("from verantyx.line3.space import build_from_jsonl;"
            "print(build_from_jsonl(%r).sha256())" % S300)
    outs = set()
    for seed in ("0", "1", "12345"):
        env = dict(os.environ, PYTHONHASHSEED=seed, PYTHONPATH=ROOT, PYTHONDONTWRITEBYTECODE="1")
        outs.add(subprocess.run([PY, "-c", code], env=env, capture_output=True, text=True, check=True).stdout.strip())
    assert len(outs) == 1


def test_default_space_filter_rule_is_funcwords_and_unknown_string_refused():
    from verantyx.line3 import funcwords as fw
    assert fw.is_function_unit("は", "RUN") and fw.is_function_unit("どこ", "WORD") and not fw.is_function_unit("半田岩", "RUN")
    assert fw.is_function_unit("あ", "CHAR") and not fw.is_function_unit("半", "CHAR")
    assert fw.default_filter("T") is None
    with pytest.raises(ValueError):
        _build_space(JA2, unit_filter="bogus")
