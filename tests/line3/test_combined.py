"""G3-g tests (L-720..): ONE labelled candidate list from the flat cross, the layers and the windows (verantyx/line3/combined.py,
`structure="combined"`).

Part 1 (the combiner, on hand-built candidates): origins and their fixed order; the list is the union of the sources, each candidate keeps its
origin; candidates with the same word set are ONE entry that lists all its origins (also from two windows of one origin), different word sets are never
merged; the order does not depend on the order the sources are given in; foreign origins are refused.
Part 2 (the verdict): a candidate only windows give is never a single ANSWER; one entry with a non-window origin is; several = CHOICE; none = the first
UNKNOWN in the reporting precedence.
Part 3 (the real sources on the toy corpus): the combined list equals the union of what the three sources give when each is run on its own (with the
origins worked out independently of combined.py); both window evidence variants are listed and the window-evidence one is marked; typed abstentions per
source; provenance per word; P-4 (trace flags, and a flag that bites).
Part 4 (defaults and the entrance): the flat ask and the other structures are unchanged (bytes), slide_flat's new `word_sources` is off by default and adds
only its own key, refusals, `structure="combined"` through ask.ask and `vera line3 ask --structure combined`.
Part 5 (bytes): PYTHONHASHSEED 0 / 1 / 12345 give the same bytes; no floating-point number.
G3-g2 (L-740..), the owner's decisions after G3-g: Part 6 (no merging across sources by default, `also_in` marks, `merge="word_set"` reproduces the G3-g
bytes (tests/line3/golden_combined_g3g.json.gz: the full to_json_obj() of cc8be195 on the toy), the verdict on unmerged entries); Part 7 (per-origin
blocks in each source's own order, no ranking across blocks); Part 8 (the per-source typed abstentions first: header and text form); Part 9 (the CLI
switch, hash seeds and floats for both merge modes). The G3-g tests above that assert the merge pass `merge="word_set"` explicitly.
"""
import ast
import gzip
import hashlib
import json
import os
import subprocess
import sys
from collections import Counter
from fractions import Fraction as Fr

import pytest

from tests.line3 import test_slide_flat as TF
from verantyx.line3 import ask as A
from verantyx.line3 import combined as CB
from verantyx.line3 import matryoshka as M
from verantyx.line3 import readout as ro
from verantyx.line3 import slide_flat as F
from verantyx.line3 import slide_query as Q
from verantyx.line3 import space as sp

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PY = sys.executable
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
def wi(space, rows):
    # G3-i (L-770, L-771): the defaults are z_deep "order" / seat_empty_axis "deny" now; the G3-g golden (and these tests) were made with the window index of
    # z_deep "slide" / seat_empty_axis "allow", which is what this fixture pins
    return Q.WindowIndex.from_space(space, None, rows=rows, level=TF.LEVEL, z_deep="slide", place_kw={"seat_empty_axis": "allow"})


@pytest.fixture(scope="module")
def idx(space):
    return A.Index(space, level=TF.LEVEL)


@pytest.fixture(scope="module")
def data_file(tmp_path_factory, rows):
    p = tmp_path_factory.mktemp("g3g") / "toy.jsonl"
    p.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
    return str(p)


def ask_cb(*a, **kw):
    """The G3-g / G3-g2 tests were written before the G3-j assembly block (L-780..): they name assembly=False (the G3-i bytes), as G3-i named the former defaults
    (L-776).  The G3-j tests below call CB.ask_combined with the default or name assembly."""
    kw.setdefault("assembly", False)
    return CB.ask_combined(*a, **kw)


def cand(origin, words, **kw):
    return CB.Cand(origin, tuple(words), **kw)


def src(name, cands, verdict=None, **kw):
    v = verdict or (CB.ANSWER if len(cands) == 1 else CB.CHOICE if cands else "UNKNOWN_NO_EVIDENCE")
    return CB.Source(name, v, tuple(cands), **kw)


# ---------------------------------------------------------------------------------------------------------------------------------
# Part 1: the combiner
# ---------------------------------------------------------------------------------------------------------------------------------
def test_origin_labels_and_their_fixed_order():
    assert CB.flat_origin("WORD") == "flat/WORD"
    assert CB.layer_origin("RUN", 1, "A") == "layers/RUN/1A"
    assert CB.window_origin("plain") == "window/plain" and CB.window_origin("window") == "window/window-evidence"
    shuffled = ["window/window-evidence", "layers/WORD/2A", "flat/CHAR", "window/plain", "layers/RUN/1B", "flat/RUN", "layers/RUN/1A", "flat/WORD",
                "layers/CHAR/1A"]
    assert sorted(shuffled, key=CB.origin_key) == ["flat/RUN", "flat/WORD", "flat/CHAR", "layers/RUN/1A", "layers/RUN/1B", "layers/WORD/2A",
                                                    "layers/CHAR/1A", "window/plain", "window/window-evidence"]
    with pytest.raises(ValueError):
        CB.origin_key("cube/RUN")


def test_the_list_is_the_union_of_the_sources_with_their_origins():
    flat = src("flat", [cand("flat/RUN", "ab"), cand("flat/WORD", "cd"), cand("flat/CHAR", "e")])
    lay = src("layers", [cand("layers/RUN/1A", "fg")])
    wp = src("window/plain", [cand("window/plain", "hi"), cand("window/plain", "jk")])
    we = src("window/window-evidence", [cand("window/window-evidence", "lm")])
    c = CB.combine("q", [flat, lay, wp, we])
    assert [e.words for e in c.entries] == [("a", "b"), ("c", "d"), ("e",), ("f", "g"), ("h", "i"), ("j", "k"), ("l", "m")]
    assert [e.origins for e in c.entries] == [("flat/RUN",), ("flat/WORD",), ("flat/CHAR",), ("layers/RUN/1A",), ("window/plain",), ("window/plain",),
                                              ("window/window-evidence",)]
    assert c.listed_before_merge == 7 and c.answer_obj()["per_source_listed"] == {"flat": 3, "layers": 1, "window/plain": 2, "window/window-evidence": 1}
    # the order of the list does not depend on the order the sources are handed over
    d = CB.combine("q", [we, wp, lay, flat])
    assert d.to_bytes() == c.to_bytes()
    assert [s.name for s in c.sources] == ["flat", "layers", "window/plain", "window/window-evidence"]


def test_equal_word_sets_are_one_entry_with_all_their_origins():
    flat = src("flat", [cand("flat/RUN", ["東京", "日本"], stability=Fr(1, 2), arrangements=2, centres=("東京",)),
                        cand("flat/WORD", ["日本", "東京"], stability=Fr(1, 3), arrangements=1, centres=("日本",))])
    lay = src("layers", [cand("layers/WORD/1A", ["東京", "日本"], stability=Fr(2, 3))])
    wp = src("window/plain", [cand("window/plain", ["日本", "東京"], detail={"window": {"n": 3}}),
                              cand("window/plain", ["東京", "日本"], detail={"window": {"n": 5}})])
    we = src("window/window-evidence", [cand("window/window-evidence", ["東京", "日本"])])
    c = CB.combine("q", [flat, lay, wp, we], merge="word_set")
    assert len(c.entries) == 1 and c.listed_before_merge == 6
    e = c.entries[0]
    assert e.words == ("日本", "東京")
    assert e.origins == ("flat/RUN", "flat/WORD", "layers/WORD/1A", "window/plain", "window/window-evidence")
    assert e.families == ("flat", "layers", "window") and not e.window_only
    assert len(e.members) == 6                                               # every contributing candidate, each with its own details
    assert [m.stability for m in e.members[:3]] == [Fr(1, 2), Fr(1, 3), Fr(2, 3)]      # nothing compared, nothing summed
    assert [m.detail.get("window", {}).get("n") for m in e.members[3:5]] == [3, 5]    # two windows of one origin stay two members
    assert c.verdict == CB.ANSWER                                            # one entry, and flat gives it


def test_different_word_sets_are_never_merged():
    flat = src("flat", [cand("flat/RUN", ["a", "b"]), cand("flat/WORD", ["a", "b", "c"])])
    wp = src("window/plain", [cand("window/plain", ["a"]), cand("window/plain", ["b", "a"])])
    c = CB.combine("q", [flat, wp], merge="word_set")
    assert [e.words for e in c.entries] == [("a", "b"), ("a", "b", "c"), ("a",)]
    assert c.entries[0].origins == ("flat/RUN", "window/plain")
    assert c.verdict == CB.CHOICE


def test_a_candidate_of_another_origin_than_its_source_is_refused():
    with pytest.raises(ValueError):
        CB.combine("q", [src("flat", [cand("window/plain", "a")])])
    with pytest.raises(ValueError):
        CB.combine("q", [src("window/plain", [cand("window/window-evidence", "a")])])
    with pytest.raises(ValueError):
        CB.combine("q", [src("flat", []), src("flat", [])])
    with pytest.raises(ValueError):
        CB.combine("q", [src("cube", [])])


# ---------------------------------------------------------------------------------------------------------------------------------
# Part 2: the verdict
# ---------------------------------------------------------------------------------------------------------------------------------
def test_window_candidates_never_stand_as_a_single_answer():
    for name, o in (("window/plain", "window/plain"), ("window/window-evidence", "window/window-evidence")):
        c = CB.combine("q", [src("flat", [], "UNKNOWN_NO_STATE"), src(name, [cand(o, "ab")])])
        assert len(c.entries) == 1 and c.verdict == CB.CHOICE
        a = c.answer_obj()
        assert a["answer"] is None and a["window_only_single"] is True and a["listed"] == 1
    # the same word set from both evidence variants is still one entry only windows give: a list of one
    c = CB.combine("q", [src("window/plain", [cand("window/plain", "ab")]), src("window/window-evidence", [cand("window/window-evidence", "ba")])],
                   merge="word_set")
    assert len(c.entries) == 1 and c.entries[0].window_only and c.verdict == CB.CHOICE
    d = CB.combine("q", [src("window/plain", [cand("window/plain", "ab")]), src("window/window-evidence", [cand("window/window-evidence", "ba")])])
    assert len(d.entries) == 2 and all(e.window_only for e in d.entries) and d.verdict == CB.CHOICE      # unmerged: two entries, still a list
    # two window entries: a list
    c = CB.combine("q", [src("window/plain", [cand("window/plain", "ab"), cand("window/plain", "c")])])
    assert c.verdict == CB.CHOICE and not c.answer_obj()["window_only_single"]


def test_one_entry_with_a_non_window_origin_is_the_answer():
    assert CB.combine("q", [src("flat", [cand("flat/CHAR", "ab")])]).verdict == CB.ANSWER
    assert CB.combine("q", [src("layers", [cand("layers/RUN/1A", "ab")])]).verdict == CB.ANSWER
    c = CB.combine("q", [src("flat", [cand("flat/RUN", "ab")]), src("window/plain", [cand("window/plain", "ba")])], merge="word_set")
    assert c.verdict == CB.ANSWER and c.answer_obj()["answer"]["origins"] == ["flat/RUN", "window/plain"]
    # a window entry next to a different flat entry: a list, not an answer
    c = CB.combine("q", [src("flat", [cand("flat/RUN", "ab")]), src("window/plain", [cand("window/plain", "c")])])
    assert c.verdict == CB.CHOICE


def test_no_entry_gives_the_first_unknown_in_the_reporting_precedence():
    f = src("flat", [], "UNKNOWN_NO_PATH")
    lay = src("layers", [], CB.NOT_STACKED)
    wp = src("window/plain", [], "UNKNOWN_NO_WINDOW")
    we = src("window/window-evidence", [], "UNKNOWN_NOT_READ")
    assert CB.combine("q", [f, lay, wp, we]).verdict == "UNKNOWN_NO_PATH"
    assert CB.combine("q", [lay, wp, we]).verdict == CB.NOT_STACKED          # the layers' report is not an UNKNOWN of its own, but it is the first report
    assert CB.combine("q", [wp, we]).verdict == "UNKNOWN_NO_WINDOW"
    assert CB.combine("q", [we]).verdict == "UNKNOWN_NOT_READ"
    assert CB.combine("q", []).verdict == CB.UNKNOWN_NO_STATE
    assert CB.combine("q", [f]).answer_obj()["answer"] is None


def test_the_window_evidence_variant_is_marked():
    c = CB.combine("q", [src("window/plain", [cand("window/plain", "a")]),
                         src("window/window-evidence", [cand("window/window-evidence", "a"), cand("window/window-evidence", "b")])])
    c = CB.combine("q", [src("window/plain", [cand("window/plain", "a")]),
                         src("window/window-evidence", [cand("window/window-evidence", "a"), cand("window/window-evidence", "b")])], merge="word_set")
    a, b = c.entries
    assert a.marks == (CB.MARK_WINDOW_EVIDENCE,) and b.marks == (CB.MARK_WINDOW_EVIDENCE,)
    only = CB.combine("q", [src("window/plain", [cand("window/plain", "a")])])
    assert only.entries[0].marks == ()
    assert [e["marks"] for e in c.answer_obj()["entries"]] == [["window_evidence_variant"]] * 2
    u = CB.combine("q", [src("window/plain", [cand("window/plain", "a")]),
                         src("window/window-evidence", [cand("window/window-evidence", "a"), cand("window/window-evidence", "b")])])
    assert [e.marks for e in u.entries] == [(), (CB.MARK_WINDOW_EVIDENCE,), (CB.MARK_WINDOW_EVIDENCE,)]          # unmerged: only the variant's own entries


# ---------------------------------------------------------------------------------------------------------------------------------
# Part 3: the real sources on the toy corpus
# ---------------------------------------------------------------------------------------------------------------------------------
def independent_origins(idx, wi, q, evidences=("plain", "window"), members="representative", effort=EFFORT):
    """word set -> origins, worked out from the three sources run on their own, without combined.py's adapters."""
    out = {}
    for k, o in independent_pairs(idx, wi, q, evidences, members, effort):
        out.setdefault(k, set()).add(o)
    return out


def independent_pairs(idx, wi, q, evidences=("plain", "window"), members="representative", effort=EFFORT):
    """[(word set, origin)] one per candidate of the three sources run on their own, in the sources' order (no merging at all)."""
    out = []

    def put(words, origin):
        out.append((tuple(sorted(set(words))), origin))

    c0 = A.ask(idx, q, effort=effort)
    for t, e in c0.entries:
        put(e.words, "flat/" + t)
    opts = M.LayerOptions(variants=("A",), granularity="compress", feedback="none", candidate="stable-seats-path", bounds=M.bounds_for(effort))
    lc = M.ask_layered(idx, q, options=opts, base=c0, effort=effort)
    for tl in lc.layers:
        for e in tl.entries:
            put(e.words, "layers/%s/%d%s" % (tl.tier, e.layer, e.variant))
    for ev in evidences:
        fa = F.ask_flat(wi, q, effort=effort, members=members, evidence=ev)
        for e in fa.entries:
            put(e["words"], "window/" + ("plain" if ev == "plain" else "window-evidence"))
    return out


def test_combined_is_the_union_of_the_three_sources_each_run_on_its_own(idx, wi):
    seen_families = set()
    for q in TF.QUESTIONS:
        c = ask_cb(idx, q, effort=EFFORT, windows=wi, merge="word_set")
        want = independent_origins(idx, wi, q)
        got = {e.words: set(e.origins) for e in c.entries}
        assert got == want, q
        assert len(got) == len(c.entries)                                    # one entry per word set
        for e in c.entries:
            seen_families.update(e.families)
        # the number of candidates before the merge is the sum of the sources'
        assert c.listed_before_merge == sum(len(s.cands) for s in c.sources)
    assert seen_families == {"flat", "layers", "window"}                     # the toy questions exercise all three


def test_the_list_is_flat_then_layers_then_window_plain_then_window_evidence(idx, wi):
    c = ask_cb(idx, "猫は何を食べますか", effort=EFFORT, windows=wi)
    firsts = [CB.origin_key(e.origins[0]) for e in c.entries]
    # an entry stands where its first (lowest-origin) candidate stands: the keys never go back to an earlier family
    fams = [k[0] for k in firsts]
    assert fams == sorted(fams)
    assert c.sources[0].name == "flat" and c.sources[1].name == "layers" and [s.name for s in c.sources[2:]] == ["window/plain", "window/window-evidence"]


def test_equal_word_sets_from_different_sources_on_the_toy(idx, wi):
    c = ask_cb(idx, "京都は何ですか", effort=EFFORT, windows=wi, merge="word_set")
    e = next(x for x in c.entries if x.words == ("京都", "古い", "都"))
    assert e.origins == ("flat/RUN", "flat/WORD", "window/plain", "window/window-evidence")
    assert sum(1 for x in c.entries if x.words == e.words) == 1
    assert c.listed < c.listed_before_merge


def test_window_evidence_both_plain_or_window(idx, wi):
    q = "猫は何を食べますか"
    both = ask_cb(idx, q, effort=EFFORT, windows=wi)
    plain = ask_cb(idx, q, effort=EFFORT, windows=wi, window_evidence="plain")
    evid = ask_cb(idx, q, effort=EFFORT, windows=wi, window_evidence="window")
    assert [s.name for s in plain.sources] == ["flat", "layers", "window/plain"]
    assert [s.name for s in evid.sources] == ["flat", "layers", "window/window-evidence"]
    assert [s.name for s in both.sources] == ["flat", "layers", "window/plain", "window/window-evidence"]
    for name in ("flat", "layers"):
        assert [c.words for c in plain.entries and next(s for s in plain.sources if s.name == name).cands] == \
               [c.words for c in next(s for s in both.sources if s.name == name).cands]
    pw = {c.key for c in next(s for s in both.sources if s.name == "window/plain").cands}
    assert pw == {c.key for c in next(s for s in plain.sources if s.name == "window/plain").cands}
    ew = {c.key for c in next(s for s in both.sources if s.name == "window/window-evidence").cands}
    assert ew == {c.key for c in next(s for s in evid.sources if s.name == "window/window-evidence").cands}
    # the marked entries are exactly those the window-evidence source gives
    assert {e.words for e in both.entries if e.marks} == ew
    assert not any(e.marks for e in plain.entries)
    assert pw != ew                                                          # the variants differ on this question: both are worth listing


def test_a_window_only_single_candidate_is_a_list_on_the_toy(idx, wi):
    # a question that only the windows answer: the flat cross has no fixed point; with one window kept (nodes=1) the list may hold one entry
    found = None
    for q in TF.QUESTIONS + ["魚が海にいるのは何ですか", "猫は何ですか", "犬は何ですか"]:
        for ev in ("plain", "window"):
            for n in (1, 2):
                c = ask_cb(idx, q, nodes=n, windows=wi, window_evidence=ev)
                if c.listed == 1 and c.entries[0].window_only:
                    found = c
                    break
            if found:
                break
        if found:
            break
    if found is None:                                                        # no toy question gives one: the rule is covered on hand-built sources (Part 2)
        pytest.skip("no toy question gives a window-only single entry")
    assert found.verdict == CB.CHOICE and found.answer_obj()["answer"] is None and found.answer_obj()["window_only_single"]


def test_typed_abstentions_per_source(idx, wi):
    c = ask_cb(idx, "魚は何ですか", effort=EFFORT, windows=wi)
    cnt = c.answer_obj()["abstention_counts"]
    assert cnt["flat"] == {"UNKNOWN_NO_FIXED_POINT": 3}                       # every tier ended without a fixed point: typed, per tier
    assert "layers" in cnt and set(cnt["layers"]) <= {"UNKNOWN_NO_FIXED_POINT", "UNKNOWN_RATIO_DISAGREEMENT", "UNKNOWN_NO_EVIDENCE", "UNKNOWN_SECTION_DISAGREEMENT"}
    assert set(cnt["window/plain"]) <= {"points_nowhere", "ratio_disagreement", "section_disagreement", "mixed", "unstable_axis_improvable",
                                        "no_question_unit", "no_path", "not_grounded", "ambiguous", "no_fixed_point"}
    assert all(a["source"] in ("flat", "layers", "window/plain", "window/window-evidence") and a["kind"] for a in c.abstentions())
    # the abstentions of a source are the source's own: the same as ask_flat reports on its own
    fa = F.ask_flat(wi, "魚は何ですか", effort=EFFORT, members="representative")
    assert [a["kind"] for a in next(s for s in c.sources if s.name == "window/plain").abstentions] == [a["kind"] for a in fa.abstentions]
    # nothing at all: the verdict is the flat source's, every source says why
    n = ask_cb(idx, "存在しない語は何ですか", effort=EFFORT, windows=wi)
    assert n.verdict == "UNKNOWN_NO_STATE" and n.listed == 0 and n.answer_obj()["answer"] is None
    assert {s.name for s in n.sources} == {"flat", "layers", "window/plain", "window/window-evidence"}
    assert all(s.abstentions for s in n.sources if s.name != "layers")
    assert next(s for s in n.sources if s.name == "layers").verdict == CB.NOT_STACKED          # no layer was needed: a report, not an abstention
    w = next(s for s in n.sources if s.name == "window/plain")
    assert w.verdict == "UNKNOWN_NO_WINDOW" and w.abstentions[0]["kind"] == "UNKNOWN_NO_WINDOW"


def test_provenance_per_word(idx, wi, space):
    for q in ("猫は何を食べますか", "京都は何ですか", "日本の首都は何ですか"):
        c = ask_cb(idx, q, effort=EFFORT, windows=wi)
        c0 = A.ask(idx, q, effort=EFFORT)
        flat_ws = {(t, e.words): e for t, e in c0.entries}
        for e in c.entries:
            prov = e.word_provenance()
            assert set(prov) == set(e.words)
            for w, rows in prov.items():
                assert rows, (q, w)
                for r in rows:
                    m = e.members[r["member"]]
                    assert m.origin == r["origin"]
                    assert all(0 <= s < len(space.sentences) for s in r["sids"])
                    if r["level"] == "none":                                 # only the window evidence: a word whose edge is the window's constructed pair count
                        assert r["origin"] == "window/window-evidence" and m.detail["trace"]["constructed_edge_words"] > 0
                        continue
                    assert r["sids"]
                    if r["origin"].startswith("flat/"):
                        want = list(ro.entry_word_sources(flat_ws[(r["origin"].split("/")[1], m.words)], w))
                        assert r["level"] == "word" and r["sids"] == want
                    else:
                        assert r["level"] == "word"                          # layers and windows give the sentences of each word's steps
            cited = {s["sid"] for s in c.answer_obj()["cited"]}
            assert set(e.source_sids) <= cited


def test_window_word_sources_are_off_by_default_and_change_nothing_else(wi):
    q = "猫は何を食べますか"
    base = F.ask_flat(wi, q, budget=TF.BUDGET, members="representative")
    off = F.ask_flat(wi, q, budget=TF.BUDGET, members="representative", word_sources=False)
    on = F.ask_flat(wi, q, budget=TF.BUDGET, members="representative", word_sources=True)
    assert base.to_bytes() == off.to_bytes()
    assert not any("word_sources" in e for e in base.entries) and "word_sources" not in base.config
    assert all(set(e["word_sources"]) == set(e["words"]) and all(v for v in e["word_sources"].values()) for e in on.entries)
    stripped = [{k: v for k, v in e.items() if k != "word_sources"} for e in on.entries]
    assert stripped == [dict(e) for e in base.entries]
    assert on.config["word_sources"] is True and {k: v for k, v in on.config.items() if k != "word_sources"} == dict(base.config)


def test_p4_trace_flags_and_one_that_bites(idx, wi):
    for q in TF.QUESTIONS:
        c = ask_cb(idx, q, effort=EFFORT, windows=wi)
        assert all(e.trace_ok is True for e in c.entries), q
        assert c.trace_ok in (True, None)
        for s in c.sources:
            assert s.trace.get("ok") in (True, None, False) and s.trace.get("ok") is not False
    c = ask_cb(idx, "猫は何を食べますか", effort=EFFORT, windows=wi)
    s0 = c.sources[0]
    bad = CB.Source(s0.name, s0.verdict, tuple(CB.Cand(x.origin, x.words, x.centres, x.stability, x.arrangements, x.source_sids, x.word_sources,
                                                      False, x.detail) for x in s0.cands), s0.abstentions, s0.read, {"ok": False}, {})
    d = CB.combine(c.question, [bad] + list(c.sources[1:]))
    assert d.trace_ok is False and any(e.trace_ok is False for e in d.entries)
    # a merged entry is untraced as soon as one of its candidates failed its trace
    assert all(e.trace_ok is False for e in d.entries if any(m.origin.startswith("flat/") for m in e.members))


def test_the_text_form_lists_origins_and_the_window_only_note(idx, wi):
    c = ask_cb(idx, "魚は何ですか", effort=EFFORT, windows=wi)
    txt = CB.format_text(c, True)
    assert "window/plain" in txt and "window/window-evidence" in txt and "【窓の証拠の変種】" in txt and "思考過程" in txt
    h = CB.combine("q", [src("window/plain", [cand("window/plain", "ab")])])
    assert "窓の候補は 1 件でも" in CB.format_text(h)


# ---------------------------------------------------------------------------------------------------------------------------------
# Part 4: defaults and the entrance
# ---------------------------------------------------------------------------------------------------------------------------------
def test_flat_and_slide_are_the_default_and_nothing_leaks_into_them(data_file):
    i2 = A.Index.from_jsonl(data_file, None, "low", ("RUN", "WORD"))
    q = "日本の首都は何ですか"
    base = A.ask(i2, q, effort="full")
    assert base.to_bytes() == A.ask(i2, q, effort="full", structure="flat").to_bytes()
    assert "combined" not in base.to_bytes().decode("utf-8") and "structure" not in base.to_json_obj()["answer"]
    s1 = A.ask(i2, "猫は何を食べますか", effort="full", structure="slide", agreement="two_if_single_edge")
    assert isinstance(s1, Q.SlideAnswer)
    assert A.STRUCTURES == ("flat", "slide", "combined")


def test_refusals(idx, wi):
    q = "猫は何を食べますか"
    with pytest.raises(ValueError, match="window_evidence"):
        ask_cb(idx, q, effort=EFFORT, windows=wi, window_evidence="both-ish")
    with pytest.raises(ValueError, match="view"):
        ask_cb(idx, q, effort=EFFORT, windows=wi, view="stable")
    with pytest.raises(ValueError, match="slide_members"):
        ask_cb(idx, q, effort=EFFORT, windows=wi, slide_members="some")
    with pytest.raises(ValueError, match="granularity"):
        A.ask(idx, q, effort=EFFORT, structure="combined", granularity="entry")
    with pytest.raises(ValueError, match="structure"):
        A.ask(idx, q, effort=EFFORT, structure="cube")


def test_ask_structure_combined_through_an_index(tmp_path, data_file):
    i2 = A.Index.from_jsonl(data_file, str(tmp_path), "low", ("RUN", "WORD", "CHAR"))
    Q.WindowIndex.from_space(i2.space, str(tmp_path), level="low")           # what `line3 build --structure combined` writes besides the placements
    r = A.ask(i2, "猫は何を食べますか", effort=EFFORT, structure="combined", assembly=False)
    assert isinstance(r, CB.CombinedAnswer) and r.answer_obj()["structure"] == "combined"
    assert [s.name for s in r.sources] == ["flat", "layers", "window/plain", "window/window-evidence"]       # window_evidence defaults to both
    assert r.config["window"]["members"] == "representative" and r.config["layers"]["candidate"] == "stable-seats-path"
    assert r.to_bytes() == A.ask(i2, "猫は何を食べますか", effort=EFFORT, structure="combined", assembly=False).to_bytes()
    assert len([f for f in os.listdir(str(tmp_path)) if f.startswith("slidewin_")]) == 1          # the same window file; nothing re-placed
    p = A.ask(i2, "猫は何を食べますか", effort=EFFORT, structure="combined", window_evidence="plain", assembly=False)
    assert [s.name for s in p.sources] == ["flat", "layers", "window/plain"]


def cli(args, seed="0"):
    env = dict(os.environ, PYTHONHASHSEED=seed, PYTHONPATH=ROOT)
    return subprocess.run([PY, "-m", "verantyx.cli", "line3"] + args, capture_output=True, text=True, env=env, cwd=ROOT, timeout=900,
                          stdin=subprocess.DEVNULL)


def test_cli_structure_combined(tmp_path, data_file):
    cache = str(tmp_path / "c")
    b = cli(["build", "--structure", "combined", "--data", data_file, "--cache", cache, "--level", "low"])
    assert b.returncode == 0, b.stderr[-2000:]
    rep = json.loads(b.stdout)
    assert rep["windows"]["windows"] > 0 and set(rep) >= {"RUN", "WORD", "CHAR", "windows"}
    names = os.listdir(cache)
    assert any(n.startswith("slidewin_") for n in names) and any(n.startswith("placements_") for n in names)
    base = ["ask", "--data", data_file, "--cache", cache, "--level", "low", "--question", "猫は何を食べますか", "--effort", EFFORT,
            "--structure", "combined", "--assembly", "off", "--format", "json", "--show-thought"]
    outs = [cli(base, s) for s in ("0", "1", "12345")]
    for r in outs:
        assert r.returncode == 0, r.stderr[-2000:]
    assert outs[0].stdout == outs[1].stdout == outs[2].stdout
    obj = json.loads(outs[0].stdout)
    assert obj["answer"]["structure"] == "combined" and [s["name"] for s in obj["answer"]["sources"]] == \
        ["flat", "layers", "window/plain", "window/window-evidence"]
    pl = cli(base + ["--window-evidence", "plain"])
    assert pl.returncode == 0 and [s["name"] for s in json.loads(pl.stdout)["answer"]["sources"]] == ["flat", "layers", "window/plain"]
    txt = cli(["ask", "--data", data_file, "--cache", cache, "--level", "low", "--question", "猫は何を食べますか", "--effort", EFFORT,
               "--structure", "combined", "--assembly", "off"])
    assert txt.returncode == 0 and "候補" in txt.stdout and "window/plain" in txt.stdout
    for extra in (["--choose", "0"], ["--record", str(tmp_path / "r.jsonl")], ["--granularity", "all"], ["--view", "stable"], ["--layers", "off"],
                  ["--layer-feedback", "down"], ["--layer-candidate", "stable"], ["--layer-down-query", "seed+question"]):
        r = cli(["ask", "--data", data_file, "--cache", cache, "--level", "low", "--question", "猫は何を食べますか", "--effort", EFFORT,
                 "--structure", "combined"] + extra)
        assert r.returncode == 2 and "combined" in r.stderr, extra
    # the other structures are untouched by the new switches
    flat = cli(["ask", "--data", data_file, "--cache", cache, "--level", "low", "--question", "猫は何を食べますか", "--effort", EFFORT, "--layers", "off"])
    assert flat.returncode == 0 and "window/" not in flat.stdout


# ---------------------------------------------------------------------------------------------------------------------------------
# Part 5: bytes and floats
# ---------------------------------------------------------------------------------------------------------------------------------
def test_bytes_do_not_depend_on_the_hash_seed(tmp_path):
    script = tmp_path / "run.py"
    script.write_text(
        "import hashlib, sys\n"
        "sys.path.insert(0, %r)\n"
        "from tests.line3 import test_slide_flat as T\n"
        "from verantyx.line3 import ask as A, combined as CB, slide_query as Q, space as sp\n"
        "rows = T.toy_rows(); space = sp.build_space(rows)\n"
        "wi = Q.WindowIndex.from_space(space, None, rows=rows, level=T.LEVEL)\n"
        "idx = A.Index(space, level=T.LEVEL)\n"
        "h = hashlib.sha256()\n"
        "for q in T.QUESTIONS:\n"
        "    for kw in ({}, {'window_evidence': 'plain'}, {'window_evidence': 'window', 'slide_members': 'all'}, {'merge': 'word_set'},\n"
        "               {'merge': 'none', 'window_evidence': 'window'}):\n"
        "        h.update(CB.ask_combined(idx, q, effort='fast', windows=wi, **dict(dict(assembly=False), **kw)).to_bytes())\n"
        "print(h.hexdigest())\n" % ROOT)
    out = set()
    for seed in ("0", "1", "12345"):
        env = dict(os.environ, PYTHONHASHSEED=seed, PYTHONPATH=ROOT)
        r = subprocess.run([PY, str(script)], capture_output=True, text=True, env=env, cwd=ROOT, timeout=900)
        assert r.returncode == 0, r.stderr[-2000:]
        out.add(r.stdout.strip())
    assert len(out) == 1 and len(next(iter(out))) == 64


def test_no_floating_point_number_anywhere(idx, wi):
    src_ = open(os.path.join(ROOT, "verantyx/line3/combined.py"), encoding="utf-8").read()
    tree = ast.parse(src_)
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
    for q in TF.QUESTIONS:
        for mg in CB.MERGES:
            walk(ask_cb(idx, q, effort=EFFORT, windows=wi, merge=mg).to_json_obj())


# ---------------------------------------------------------------------------------------------------------------------------------
# G3-g2 helpers
# ---------------------------------------------------------------------------------------------------------------------------------
NEW_ANSWER_KEYS = ("merge", "header", "blocks")                    # what G3-g2 adds to the answer in word_set mode
NEW_THOUGHT_KEYS = ("merge",)                                      # ... and to the thought
G3G_KW = {"both": {}, "plain": {"window_evidence": "plain"}, "evid_all": {"window_evidence": "window", "slide_members": "all"}}


def g3g_golden():
    with gzip.open(os.path.join(ROOT, "tests/line3/golden_combined_g3g.json.gz"), "rb") as f:
        return json.loads(f.read().decode("utf-8"))


def strip_g2(obj):
    return {"answer": {k: v for k, v in obj["answer"].items() if k not in NEW_ANSWER_KEYS},
            "thought": {k: v for k, v in obj["thought"].items() if k not in NEW_THOUGHT_KEYS}}


def big_sources():
    """hand-built sources with every block filled; candidates deliberately NOT in stability order and the flat tiers out of the block order; the layers
    candidates carry no stability (as layers replayed from T10's records)."""
    flat = src("flat", [cand("flat/WORD", "wx", stability=Fr(1, 2)), cand("flat/RUN", "ab", stability=Fr(1, 3)), cand("flat/RUN", "cd", stability=Fr(2, 3)),
                        cand("flat/RUN", "ef", stability=Fr(1, 3)), cand("flat/CHAR", "q", stability=Fr(1, 5)), cand("flat/WORD", "yz", stability=Fr(3, 4))],
               abstentions=({"tier": "WORD", "kind": "X"},))
    lay = src("layers", [cand("layers/WORD/1A", "lw"), cand("layers/RUN/1A", "ab"), cand("layers/RUN/2A", "lr")],
              abstentions=({"tier": "CHAR", "layer": 1, "variant": "A", "kind": "UNKNOWN_NO_FIXED_POINT"},))
    wp = src("window/plain", [cand("window/plain", "ab", stability=Fr(1, 2), detail={"window": {"n": 1}}),
                              cand("window/plain", "ab", stability=Fr(1, 2), detail={"window": {"n": 2}}), cand("window/plain", "wp", stability=Fr(3, 4))])
    we = src("window/window-evidence", [cand("window/window-evidence", "ba", stability=Fr(1, 5)), cand("window/window-evidence", "we", stability=Fr(2, 5))])
    return flat, lay, wp, we


# ---------------------------------------------------------------------------------------------------------------------------------
# Part 6: no merging across sources (L-740, L-741), merge="word_set" is G3-g (L-745), the verdict (L-744)
# ---------------------------------------------------------------------------------------------------------------------------------
def test_merge_modes_and_the_default():
    assert CB.MERGES == ("none", "word_set")
    f = src("flat", [cand("flat/RUN", "ab")])
    assert CB.combine("q", [f]).merge == "none" and CB.combine("q", [f], merge="word_set").merge == "word_set"
    with pytest.raises(ValueError, match="merge"):
        CB.combine("q", [f], merge="subset")
    assert CB.merge is CB.build_entries


def test_equal_word_sets_from_different_origins_stay_separate_entries():
    fl, ly, wp, we = big_sources()
    c = CB.combine("q", [fl, ly, wp, we])
    assert len(c.entries) == c.listed_before_merge == 6 + 3 + 3 + 2
    assert all(len(e.members) == 1 and len(e.origins) == 1 for e in c.entries)               # nothing merged, not even two windows of one origin
    ab = [e for e in c.entries if e.words == ("a", "b")]
    assert [e.origins[0] for e in ab] == ["flat/RUN", "layers/RUN/1A", "window/plain", "window/plain", "window/window-evidence"]
    assert [m.detail.get("window", {}).get("n") for e in ab for m in e.members][2:4] == [1, 2]    # the two windows keep their own details
    # the same list, merged by word set, is G3-g's: one entry for {a,b} with its five members
    g = CB.combine("q", [fl, ly, wp, we], merge="word_set")
    assert len(g.entries) == 14 - 4 and [m.origin for m in next(e for e in g.entries if e.words == ("a", "b")).members] == [e.origins[0] for e in ab]


def test_also_in_is_a_mark_of_the_other_origins_only():
    fl, ly, wp, we = big_sources()
    c = CB.combine("q", [fl, ly, wp, we])
    ab = [e for e in c.entries if e.words == ("a", "b")]
    assert [e.also_in for e in ab] == [("layers/RUN/1A", "window/plain", "window/window-evidence"),
                                        ("flat/RUN", "window/plain", "window/window-evidence"),
                                        ("flat/RUN", "layers/RUN/1A", "window/window-evidence"),          # a twin window of the same origin is not an "other origin"
                                        ("flat/RUN", "layers/RUN/1A", "window/window-evidence"),
                                        ("flat/RUN", "layers/RUN/1A", "window/plain")]
    assert all(e.also_in == () for e in c.entries if e.words != ("a", "b"))
    # the mark does not enter anything else: origins, members, marks, centres, provenance, verdict
    assert all(e.origins == (e.members[0].origin,) for e in ab)
    assert [e.marks for e in ab] == [(), (), (), (), (CB.MARK_WINDOW_EVIDENCE,)]
    a = c.answer_obj()
    assert [e["also_in"] for e in a["entries"] if e["words"] == ["a", "b"]][0] == ["layers/RUN/1A", "window/plain", "window/window-evidence"]
    assert all("block" in e and "also_in" in e for e in a["entries"])
    # word_set mode carries no per-entry mark (the entry lists all its origins): the G3-g entry objects have exactly their old keys
    g = CB.combine("q", [fl, ly, wp, we], merge="word_set").answer_obj()
    assert all("also_in" not in e and "block" not in e for e in g["entries"])


def test_also_in_never_selects_sums_or_changes_the_verdict():
    one = CB.combine("q", [src("flat", [cand("flat/RUN", "ab")])])
    assert one.verdict == CB.ANSWER and one.entries[0].also_in == ()
    # the same word set from two sources is TWO entries and so a list (L-744); merged by word set it was one ANSWER (G3-g)
    two = CB.combine("q", [src("flat", [cand("flat/RUN", "ab")]), src("window/plain", [cand("window/plain", "ba")])])
    assert len(two.entries) == 2 and two.verdict == CB.CHOICE and two.answer_obj()["answer"] is None
    assert [e.also_in for e in two.entries] == [("window/plain",), ("flat/RUN",)]
    assert CB.combine("q", [src("flat", [cand("flat/RUN", "ab")]), src("window/plain", [cand("window/plain", "ba")])], merge="word_set").verdict == CB.ANSWER
    # a window-only single is still a list of one; a non-window single is an ANSWER
    w = CB.combine("q", [src("window/plain", [cand("window/plain", "ab")])])
    assert w.verdict == CB.CHOICE and w.answer_obj()["window_only_single"]
    # nothing in the agreement report selects (it is by word set, the same in both modes)
    fl, ly, wp, we = big_sources()
    a = CB.combine("q", [fl, ly, wp, we]).agreement()
    b = CB.combine("q", [fl, ly, wp, we], merge="word_set").agreement()
    assert a == b and a["used_for_selection"] is False and a["entries_by_families"]["flat+layers+window"] == 1


def test_default_mode_lists_every_candidate_of_the_toy_sources_each_with_its_origin(idx, wi):
    seen_pair = 0
    for q in TF.QUESTIONS:
        c = ask_cb(idx, q, effort=EFFORT, windows=wi)
        want = Counter(independent_pairs(idx, wi, q))
        got = Counter((e.words, e.origins[0]) for e in c.entries)
        assert got == want, q                                                                # multiset: duplicates are not hidden
        assert c.listed == c.listed_before_merge == sum(want.values())
        assert all(len(e.members) == 1 for e in c.entries)
        by_key = {}
        for e in c.entries:
            by_key.setdefault(e.words, []).append(e)
        for k, es in by_key.items():
            for e in es:
                assert set(e.also_in) == {x.origins[0] for x in es} - {e.origins[0]}
                assert len(e.also_in) == len(set(e.also_in))
                seen_pair += len(e.also_in)
    assert seen_pair > 0                                                                      # the toy has word sets that two origins give


def test_merge_word_set_reproduces_the_g3g_bytes_on_the_toy(idx, wi):
    gold = g3g_golden()
    assert len(gold) == len(TF.QUESTIONS) * len(G3G_KW)
    for q in TF.QUESTIONS:
        for k, kw in G3G_KW.items():
            c = ask_cb(idx, q, effort=EFFORT, windows=wi, merge="word_set", **kw)
            obj = c.to_json_obj()
            assert strip_g2(obj) == gold["%s|%s" % (q, k)], (q, k)                              # entries, origins, members, abstentions, cited, thought: all as committed
            assert set(obj["answer"]) - set(strip_g2(obj)["answer"]) == set(NEW_ANSWER_KEYS)          # and only the new keys are added
    # the default (none) keeps every candidate and its details of those G3-g entries
    for q in TF.QUESTIONS:
        old = gold["%s|both" % q]["answer"]["entries"]
        new = ask_cb(idx, q, effort=EFFORT, windows=wi).to_json_obj()["answer"]["entries"]
        members_old = Counter(json.dumps(dict(m, words=e["words"]), sort_keys=True) for e in old for m in e["members"])
        members_new = Counter(json.dumps(dict(m, words=e["words"]), sort_keys=True) for e in new for m in e["members"])
        assert members_old == members_new, q


# ---------------------------------------------------------------------------------------------------------------------------------
# Part 7: per-origin blocks in each source's own order (L-743)
# ---------------------------------------------------------------------------------------------------------------------------------
def test_blocks_are_in_the_fixed_order_each_most_stable_first_ties_in_source_order():
    fl, ly, wp, we = big_sources()
    for order in ([fl, ly, wp, we], [we, wp, ly, fl]):
        c = CB.combine("q", order)
        bl = c.blocks()
        assert [b["block"] for b in bl] == ["flat/RUN", "flat/WORD", "flat/CHAR", "layers", "window/plain", "window/window-evidence"]
        assert [(b["first"], b["listed"]) for b in bl] == [(0, 3), (3, 2), (5, 1), (6, 3), (9, 3), (12, 2)]
        first = 0
        for b in bl:
            assert b["first"] == first
            first += b["listed"]
        assert first == len(c.entries)
        seq = lambda block: [e.words for e in c.entries if e.block == block]
        # inside a block (L-749): most stable first (exact Fractions), the source's order breaking ties
        assert seq("flat/RUN") == [("c", "d"), ("a", "b"), ("e", "f")]                             # 2/3, then 1/3 and 1/3 (a tie: source order a, e)
        assert seq("flat/WORD") == [("y", "z"), ("w", "x")]                                        # the source gave 1/2 then 3/4
        assert seq("window/plain") == [("p", "w"), ("a", "b"), ("a", "b")]                         # 3/4, then 1/2 twice (twin windows 1, 2 in source order)
        assert [m.detail.get("window", {}).get("n") for e in c.entries if e.block == "window/plain" for m in e.members][1:] == [1, 2]
        assert seq("window/window-evidence") == [("e", "w"), ("a", "b")]                           # the source gave 1/5 then 2/5
        # the layers candidates carry no stability (as a replayed record): the block stays in the source's order and says so
        assert seq("layers") == [("l", "w"), ("a", "b"), ("l", "r")]                              # WORD/1A, RUN/1A, RUN/2A: the layers source's order
        assert [e.origins[0] for e in c.entries if e.block == "layers"] == ["layers/WORD/1A", "layers/RUN/1A", "layers/RUN/2A"]
        assert {b["block"]: b["order"] for b in bl} == {"flat/RUN": "stability", "flat/WORD": "stability", "flat/CHAR": "stability", "layers": "source",
                                                         "window/plain": "stability", "window/window-evidence": "stability"}
    # every entry keeps its own stability (shown per member)
    c = CB.combine("q", [fl, ly, wp, we])
    assert [e.members[0].stability for e in c.entries if e.block == "flat/RUN"] == [Fr(2, 3), Fr(1, 3), Fr(1, 3)]
    assert [e["block"] for e in c.answer_obj()["entries"]][:3] == ["flat/RUN"] * 3
    assert [b["order"] for b in c.answer_obj()["blocks"]] == ["stability", "stability", "stability", "source", "stability", "stability"]
    # word_set mode never sorts: every block says "source"
    g = CB.combine("q", [fl, ly, wp, we], merge="word_set")
    assert {b["order"] for b in g.answer_obj()["blocks"]} == {"source"}


def non_increasing(c):
    for b in c.blocks():
        st = [e.members[0].stability for e in c.entries[b["first"]:b["first"] + b["listed"]]]
        if b["order"] == "stability":
            assert all(x is not None for x in st)
            assert all(x >= y for x, y in zip(st, st[1:])), (b["block"], st)
    return True


def test_each_block_is_non_increasing_in_stability_with_exact_fractions(idx, wi):
    seen = set()
    for q in TF.QUESTIONS:
        c = ask_cb(idx, q, effort=EFFORT, windows=wi)
        assert non_increasing(c)
        for b in c.blocks():
            seen.add((b["block"], b["order"]))
            for e in c.entries[b["first"]:b["first"] + b["listed"]]:
                assert e.members[0].stability is None or isinstance(e.members[0].stability, Fr)
    assert ("flat/RUN", "stability") in seen and ("window/plain", "stability") in seen
    # live layers carry a stability: a layers block is sorted by it, never marked "source"
    assert not any(b == "layers" and o == "source" for b, o in seen)
    fl, ly, wp, we = big_sources()
    assert non_increasing(CB.combine("q", [fl, ly, wp, we]))


def test_ties_keep_the_source_order_and_nothing_is_picked_among_equal_stabilities():
    f = src("flat", [cand("flat/RUN", w, stability=Fr(1, 2)) for w in "ab"] + [cand("flat/RUN", "c", stability=Fr(3, 5)), cand("flat/RUN", "d", stability=Fr(1, 2))])
    c = CB.combine("q", [f])
    assert [e.words for e in c.entries] == [("c",), ("a",), ("b",), ("d",)]                    # 3/5 first; the 1/2 tie in the order the source gave
    # Fractions are compared exactly: 2/6 and 1/3 tie (source order), both above 333333333333/10**12
    f2 = src("flat", [cand("flat/RUN", "a", stability=Fr(2, 6)), cand("flat/RUN", "b", stability=Fr(333333333333, 10 ** 12)), cand("flat/RUN", "c", stability=Fr(1, 3))])
    assert [e.words for e in CB.combine("q", [f2]).entries] == [("a",), ("c",), ("b",)]
    # a block in which one candidate has no stability is not sorted at all
    m = src("flat", [cand("flat/RUN", "a", stability=Fr(1, 4)), cand("flat/RUN", "b"), cand("flat/RUN", "c", stability=Fr(3, 4))])
    cm = CB.combine("q", [m])
    assert [e.words for e in cm.entries] == [("a",), ("b",), ("c",)] and cm.blocks()[0]["order"] == "source"
    # one block unsorted does not stop the others from being sorted
    both = CB.combine("q", [src("flat", [cand("flat/RUN", "a"), cand("flat/WORD", "x", stability=Fr(1, 4)), cand("flat/WORD", "y", stability=Fr(1, 2))])])
    assert [e.words for e in both.entries] == [("a",), ("y",), ("x",)] and [b["order"] for b in both.blocks()] == ["source", "stability"]


def test_toy_blocks_are_the_sources_candidates_in_stability_order_ties_in_source_order(idx, wi):
    for q in TF.QUESTIONS:
        c = ask_cb(idx, q, effort=EFFORT, windows=wi)
        by_origin = {s.name: s for s in c.sources}
        assert [b["block"] for b in c.blocks()] == sorted({e.block for e in c.entries}, key=CB.block_key)
        for b in c.blocks():
            got = [(e.words, e.centres, e.members[0].stability, e.members[0].arrangements) for e in c.entries[b["first"]:b["first"] + b["listed"]]]
            blk = b["block"]
            srcname = "flat" if blk.startswith("flat/") else blk
            pool = [(i, x) for i, x in enumerate(by_origin[srcname].cands) if CB.block_of(x.origin) == blk]
            # the same candidates, worked out without build_entries: sort by (-stability, index in the source)
            want = [(x.key, x.centres, x.stability, x.arrangements) for _i, x in sorted(pool, key=lambda ix: (-ix[1].stability, ix[0]))]
            assert got == want, (q, blk)
            assert b["order"] == "stability"
        assert sum(b["listed"] for b in c.blocks()) == c.listed
        for b, nxt in zip(c.blocks(), c.blocks()[1:]):
            assert CB.block_key(b["block"]) < CB.block_key(nxt["block"])


def test_flat_defaults_stay_byte_identical(idx, space):
    # the digest was computed with the code of HEAD 6b62f0fd (before G3-g2) and with this tree: ask.ask structure="flat" is untouched by G3-g2
    h = hashlib.sha256()
    for q in TF.QUESTIONS:
        h.update(A.ask(idx, q, effort="full").to_bytes())
    assert len(TF.QUESTIONS) == 12
    assert h.hexdigest() == "ef50e562192c7f274872679b2f8acabd6cc28a323aedaa5ee13885f4f8e810e0"
    assert A.ask(idx, TF.QUESTIONS[0], effort="full").to_bytes() == A.ask(idx, TF.QUESTIONS[0], effort="full", structure="flat").to_bytes()


def test_flat_tiers_are_shown_run_word_char_whatever_order_the_source_gives():
    f = src("flat", [cand("flat/CHAR", "c"), cand("flat/WORD", "w"), cand("flat/CHAR", "d"), cand("flat/RUN", "r")])
    c = CB.combine("q", [f])
    assert [(e.block, e.words) for e in c.entries] == [("flat/RUN", ("r",)), ("flat/WORD", ("w",)), ("flat/CHAR", ("c",)), ("flat/CHAR", ("d",))]
    g = CB.combine("q", [f], merge="word_set")                                                  # G3-g: the source's order, untouched
    assert [e.words for e in g.entries] == [("c",), ("w",), ("d",), ("r",)]


def test_no_ranking_across_blocks(idx, wi):
    # a block's entries are never moved by what another block holds: dropping the window sources leaves the flat and layers blocks as they were
    for q in TF.QUESTIONS:
        full = ask_cb(idx, q, effort=EFFORT, windows=wi)
        flat_only = CB.combine(q, [s for s in full.sources if s.name in ("flat", "layers")])
        assert [(e.words, e.origins) for e in flat_only.entries] == [(e.words, e.origins) for e in full.entries[:flat_only.listed]]


# ---------------------------------------------------------------------------------------------------------------------------------
# Part 8: the per-source typed abstentions first (L-742)
# ---------------------------------------------------------------------------------------------------------------------------------
def test_header_rows_per_source_in_order_with_kinds():
    flat = src("flat", [cand("flat/RUN", "ab"), cand("flat/RUN", "cd")], abstentions=({"tier": "WORD", "kind": "UNKNOWN_NO_STATE"},
                                                                                       {"tier": "CHAR", "kind": "UNKNOWN_NO_FIXED_POINT"}))
    lay = src("layers", [cand("layers/RUN/1A", "ef")], abstentions=({"tier": "WORD", "layer": 1, "variant": "A", "kind": "UNKNOWN_NO_FIXED_POINT"},
                                                                     {"tier": "CHAR", "layer": 1, "variant": "A", "kind": "UNKNOWN_NO_FIXED_POINT"}))
    wp = src("window/plain", [], "UNKNOWN_NO_WINDOW", abstentions=({"kind": "UNKNOWN_NO_WINDOW", "windows": 0},))
    we = src("window/window-evidence", [cand("window/window-evidence", "gh"), cand("window/window-evidence", "ij")],
             abstentions=({"kind": "ratio_disagreement"}, {"kind": "ratio_disagreement"}, {"kind": "points_nowhere"}))
    c = CB.combine("q", [we, wp, lay, flat])
    assert c.header() == [
        {"source": "flat/RUN", "listed": 2, "kind": None, "kinds": {}},
        {"source": "flat/WORD", "listed": 0, "kind": "UNKNOWN_NO_STATE", "kinds": {"UNKNOWN_NO_STATE": 1}},
        {"source": "flat/CHAR", "listed": 0, "kind": "UNKNOWN_NO_FIXED_POINT", "kinds": {"UNKNOWN_NO_FIXED_POINT": 1}},
        {"source": "layers", "listed": 1, "kind": None, "kinds": {"UNKNOWN_NO_FIXED_POINT": 2}},
        {"source": "window/plain", "listed": 0, "kind": "UNKNOWN_NO_WINDOW", "kinds": {"UNKNOWN_NO_WINDOW": 1}},
        {"source": "window/window-evidence", "listed": 2, "kind": None, "kinds": {"points_nowhere": 1, "ratio_disagreement": 2}},
    ]
    a = c.answer_obj()
    assert a["header"] == c.header() and a["verdict"] == CB.CHOICE            # the overall verdict is still the entries' (L-724)
    assert "header" in a and "blocks" in a
    # nothing was read at all: one row per source, the source's own verdict as the kind; a flat source with no tier information is one row
    n = CB.combine("q", [src("flat", [], "UNKNOWN_NO_STATE"), src("layers", [], CB.NOT_STACKED)])
    assert n.header() == [{"source": "flat", "listed": 0, "kind": "UNKNOWN_NO_STATE", "kinds": {}},
                          {"source": "layers", "listed": 0, "kind": CB.NOT_STACKED, "kinds": {}}]
    assert n.verdict == "UNKNOWN_NO_STATE"
    # the header is the same in both merge modes
    assert CB.combine("q", [we, wp, lay, flat], merge="word_set").header() == c.header()


def test_header_on_the_toy_matches_the_sources_and_the_blocks(idx, wi):
    kinds_seen = set()
    for q in TF.QUESTIONS + ["魚は何ですか", "存在しない語は何ですか"]:
        c = ask_cb(idx, q, effort=EFFORT, windows=wi)
        h = c.header()
        order = [CB.origin_key(r["source"]) if r["source"] != "layers" else (1, 0, 0, "") for r in h]
        assert order == sorted(order)
        by_block = {b["block"]: b["listed"] for b in c.blocks()}
        for r in h:
            assert r["listed"] == by_block.get(r["source"], 0)
            assert (r["kind"] is None) == (r["listed"] > 0)
            if r["kind"]:
                kinds_seen.add(r["kind"])
        assert [r["source"] for r in h if r["source"].startswith("flat/")] == ["flat/RUN", "flat/WORD", "flat/CHAR"][:sum(1 for r in h if r["source"].startswith("flat/"))]
        assert [r["source"] for r in h if r["source"].startswith("window/")] == ["window/plain", "window/window-evidence"]
        # the abstention counts of the answer are the header's kinds
        cnt = c.answer_obj()["abstention_counts"]
        for r in h:
            fam = "flat" if r["source"].startswith("flat/") else r["source"]
            for k, n in r["kinds"].items():
                assert cnt[fam][k] >= n
    f = ask_cb(idx, "魚は何ですか", effort=EFFORT, windows=wi).header()
    assert [(r["source"], r["listed"], r["kind"]) for r in f[:3]] == [("flat/RUN", 0, "UNKNOWN_NO_FIXED_POINT"), ("flat/WORD", 0, "UNKNOWN_NO_FIXED_POINT"),
                                                                       ("flat/CHAR", 0, "UNKNOWN_NO_FIXED_POINT")]
    assert kinds_seen


def test_text_form_header_first_then_blocks_with_marks(idx, wi):
    c = ask_cb(idx, "京都は何ですか", effort=EFFORT, windows=wi)
    txt = CB.format_text(c)
    lines = txt.split("\n")
    assert lines[0].startswith("出所ごとの状況")
    nh = len(c.header())
    assert [l.split(":")[0].strip() for l in lines[1:1 + nh]] == [r["source"] for r in c.header()]
    assert lines[1 + nh].startswith("候補 %d 件" % c.listed)                                   # the header precedes the list
    for b in c.blocks():
        assert " == %s (%d 件) ==" % (b["block"], b["listed"]) in txt
    assert txt.count("ほかの出所にも同じ語の集合") == sum(1 for e in c.entries if e.also_in) > 0
    assert "答えなし（種類別）" not in txt
    pos = [txt.index(" == %s (" % b["block"]) for b in c.blocks()]
    assert pos == sorted(pos)
    # a question every source abstains on: the header says why, and the verdict line follows it
    n = CB.format_text(ask_cb(idx, "存在しない語は何ですか", effort=EFFORT, windows=wi))
    nl = n.split("\n")
    assert nl[0].startswith("出所ごとの状況") and any(l.startswith("答えなし: UNKNOWN_NO_STATE") for l in nl) and "flat/RUN: 答えなし" in n
    # the G3-g text form (merge word_set) also begins with the header and keeps the origins in brackets
    g = CB.format_text(ask_cb(idx, "京都は何ですか", effort=EFFORT, windows=wi, merge="word_set"))
    assert g.split("\n")[0].startswith("出所ごとの状況") and "(flat/RUN, flat/WORD, window/plain, window/window-evidence)" in g


# ---------------------------------------------------------------------------------------------------------------------------------
# Part 9: the entrance and the CLI switch
# ---------------------------------------------------------------------------------------------------------------------------------
def test_ask_ask_passes_merge_and_refuses_a_bad_one(idx, wi):
    q = "京都は何ですか"
    d = A.ask(idx, q, effort=EFFORT, structure="combined", windows=wi, assembly=False)
    g = A.ask(idx, q, effort=EFFORT, structure="combined", windows=wi, merge="word_set", assembly=False)
    assert d.merge == "none" and g.merge == "word_set" and g.listed < d.listed
    assert d.to_bytes() == ask_cb(idx, q, effort=EFFORT, windows=wi).to_bytes()
    with pytest.raises(ValueError, match="merge"):
        A.ask(idx, q, effort=EFFORT, structure="combined", windows=wi, merge="overlap")


def test_cli_merge_switch_and_text(tmp_path, data_file):
    cache = str(tmp_path / "c")
    assert cli(["build", "--structure", "combined", "--data", data_file, "--cache", cache, "--level", "low"]).returncode == 0
    base = ["ask", "--data", data_file, "--cache", cache, "--level", "low", "--question", "京都は何ですか", "--effort", EFFORT, "--structure", "combined"]
    d = cli(base + ["--format", "json"])
    g = cli(base + ["--format", "json", "--merge", "word_set"])
    assert d.returncode == 0 and g.returncode == 0, d.stderr[-1500:] + g.stderr[-1500:]
    da, ga = json.loads(d.stdout)["answer"], json.loads(g.stdout)["answer"]
    assert da["merge"] == "none" and ga["merge"] == "word_set" and ga["listed"] < da["listed"]
    assert all("also_in" in e and "block" in e for e in da["entries"]) and all("also_in" not in e for e in ga["entries"])
    assert da["header"] == ga["header"]
    t = cli(base)
    assert t.returncode == 0 and t.stdout.startswith("出所ごとの状況") and " == flat/RUN (" in t.stdout
    outs = [cli(base + ["--format", "json", "--show-thought"], seed).stdout for seed in ("1", "12345")]
    assert outs[0] == outs[1] and json.loads(outs[0])["thought"]["merge"] == "none"
    r = cli(base + ["--merge", "overlap"])
    assert r.returncode == 2


# ---------------------------------------------------------------------------------------------------------------------------------
# G3-j (L-780..): the F2 granularity assembly over the flat block, the block flat/assembled
# ---------------------------------------------------------------------------------------------------------------------------------
from verantyx.line3 import granularity as GR                      # noqa: E402
from verantyx.lang import strip_attribution                       # noqa: E402

HASH_TOY = [("H", "ハッシュ表ともいう。"), ("H", "ハッシュ表は連想配列を実現する。"), ("H", "連想配列はキーと値を対応させる。"),
            ("I", "犬が猫を追う。"), ("I", "猫が魚を食べる。")]
HASH_QUESTIONS = ["連想配列を実現するのは何ですか", "ハッシュ表は何ですか", "ハッシュは何ですか", "猫は何を食べますか"]


@pytest.fixture(scope="module")
def hrows():
    return [{"title": t, "sent": s, "source": "%s#%d" % (t, i)} for i, (t, s) in enumerate(HASH_TOY)]


@pytest.fixture(scope="module")
def hspace(hrows):
    return sp.build_space(hrows)


@pytest.fixture(scope="module")
def hwi(hspace, hrows):
    return Q.WindowIndex.from_space(hspace, None, rows=hrows, level=TF.LEVEL, z_deep="slide", place_kw={"seat_empty_axis": "allow"})


@pytest.fixture(scope="module")
def hidx(hspace):
    return A.Index(hspace, level=TF.LEVEL)


def assembled_entries(c):
    return [e for e in c.entries if e.origins == (CB.ASSEMBLED,)]


def test_the_assembled_block_is_there_by_default_and_not_when_the_switch_is_off(hidx, hwi):
    q = "ハッシュ表は何ですか"
    on = CB.ask_combined(hidx, q, effort=EFFORT, windows=hwi)
    off = CB.ask_combined(hidx, q, effort=EFFORT, windows=hwi, assembly=False)
    assert [s.name for s in on.sources] == ["flat", "flat/assembled", "layers", "window/plain", "window/window-evidence"]
    assert [s.name for s in off.sources] == ["flat", "layers", "window/plain", "window/window-evidence"]
    assert "ハッシュ表" in [e.words[0] for e in assembled_entries(on)] and assembled_entries(off) == []
    bn = [b["block"] for b in on.answer_obj()["blocks"]]
    k = bn.index("flat/assembled")
    assert all(b.startswith("flat/") for b in bn[:k]) and not any(b.startswith("flat/") for b in bn[k + 1:])       # after the flat tiers, before the layers and the windows
    # off = the G3-i list: no key, no config entry, no header row, no sentence of its own
    ao = off.answer_obj()
    assert "assembly" not in ao and "assembled_only_single" not in ao and "assembly" not in off.config
    assert [h["source"] for h in off.header()] == ["flat/RUN", "flat/WORD", "flat/CHAR", "layers", "window/plain", "window/window-evidence"]
    assert "flat/assembled" not in off.to_bytes().decode("utf-8")
    # on adds exactly the assembled entries: every other entry, in its place, is the same
    rest = [e.to_obj() for e in on.entries if not e.assembled_only]
    assert rest == [e.to_obj() for e in off.entries]
    assert on.config["assembly"] == {"on": True, "scope": "all", "bridge": False, "layer": 0}
    assert on.answer_obj()["assembly"]["listed"] == len(assembled_entries(on)) > 0 and on.answer_obj()["assembly"]["scope"] == "all"
    assert "flat/assembled" in on.thought_obj()["rule"] and "flat/assembled" not in off.thought_obj()["rule"]
    # the default of the driver and of ask.ask(structure="combined") is on
    assert A.ask(hidx, q, effort=EFFORT, structure="combined", windows=hwi).to_bytes() == on.to_bytes()
    with pytest.raises(TypeError):
        CB.ask_combined(hidx, q, effort=EFFORT, windows=hwi, assembly="maybe", nothing=1)


def test_hash_table_assembles_from_a_run_unit_and_a_word_unit_across_tiers(hspace):
    # RUN gives ハッシュ, WORD gives 表, both pointing into sentence 0: the units of two tiers touch -> one string, the parts keep their tiers
    flat = CB.Source(CB.FLAT, CB.CHOICE, (CB.Cand("flat/RUN", ("ハッシュ",), source_sids=(0,)), CB.Cand("flat/WORD", ("表",), source_sids=(0,))))
    s = CB.assembled_source(flat, hspace)
    assert s.name == CB.ASSEMBLED and s.verdict == CB.ASSEMBLY_LISTED and [c.words for c in s.cands] == [("ハッシュ表",)]
    c = s.cands[0]
    assert c.origin == "flat/assembled" and c.source_sids == (0,) and c.stability is None and c.trace_ok is True
    d = c.detail
    assert d["sid"] == 0 and d["span"] == [0, 5] and d["part_tiers"] == ["RUN", "WORD"]
    assert [(p["tier"], p["unit"], p["span"], p["flat_pos"]) for p in d["parts"]] == [("RUN", "ハッシュ", [0, 4], [0]), ("WORD", "表", [4, 5], [1])]
    assert d["aligned_tiers"] == ["RUN", "WORD", "CHAR"] and d["lifted_tier"] == "RUN" and d["trace_check"] == {"ok": True, "problems": []}
    assert [(x["i"], x["ch"], x["parts"]) for x in d["chars"]] == [(0, "ハ", [0]), (1, "ッ", [0]), (2, "シ", [0]), (3, "ュ", [0]), (4, "表", [1])]
    assert s.read == {"scope": "all", "bridge": False, "layer": 0, "from": "flat", "flat_entries": 2, "sentences": 1}
    assert s.trace == {"ok": True, "strings_checked": 1}
    # the same units listed by ONE tier alone also assemble (scope all pools by sentence, not by tier)
    flat1 = CB.Source(CB.FLAT, CB.ANSWER, (CB.Cand("flat/RUN", ("ハッシュ", "表"), source_sids=(0,)),))
    assert [c.words for c in CB.assembled_source(flat1, hspace).cands] == [("ハッシュ表",)]
    # no function word is bridged: ハッシュ表 + ともいう are joined only through RUN adjacency (no letter between), and a gap with a letter is not
    fl2 = CB.Source(CB.FLAT, CB.CHOICE, (CB.Cand("flat/RUN", ("ハッシュ", "実現"), source_sids=(1,)),))
    assert CB.assembled_source(fl2, hspace).cands == () and CB.assembled_source(fl2, hspace).verdict == CB.NO_ASSEMBLY


def test_assembly_reads_the_flat_entries_only_and_their_own_sentences(hidx, hwi, hspace):
    for q in HASH_QUESTIONS:
        c = CB.ask_combined(hidx, q, effort=EFFORT, windows=hwi)
        flat = [(m.origin.split("/")[1], m.words, m.source_sids) for s in c.sources if s.name == CB.FLAT for m in s.cands]
        want = GR.assemble(hspace, flat, "all")
        got = [(m.detail["sid"], tuple(m.detail["span"]), m.words[0]) for s in c.sources if s.name == CB.ASSEMBLED for m in s.cands]
        assert got == [(a.sid, (a.start, a.end), a.text) for a in want], q
        # the layers' and the windows' candidates are not read: nothing they alone list is in the assembled block
        assert all(p["tier"] in ("RUN", "WORD", "CHAR") for m in (m for s in c.sources if s.name == CB.ASSEMBLED for m in s.cands) for p in m.detail["parts"])


def test_every_assembled_string_traces_per_character_and_to_the_entries_that_hold_its_parts(hidx, hwi, hspace):
    seen = 0
    for q in HASH_QUESTIONS:
        c = CB.ask_combined(hidx, q, effort=EFFORT, windows=hwi)
        a = c.answer_obj()
        for i, e in enumerate(a["entries"]):
            if e["origins"] != [CB.ASSEMBLED]:
                continue
            seen += 1
            m = e["members"][0]
            text = strip_attribution(hspace.sentences[m["sid"]][0])
            lo, hi = m["span"]
            assert e["words"] == [text[lo:hi]] and e["source_sids"] == [m["sid"]] and e["trace_ok"] is True
            assert m["trace_check"] == {"ok": True, "problems": []}
            # per character: one row per position, the right character, covering parts that really cover it; a character no part covers is one every tier drops
            assert [x["i"] for x in m["chars"]] == list(range(lo, hi))
            for x in m["chars"]:
                assert x["ch"] == text[x["i"]]
                for k in x["parts"]:
                    assert m["parts"][k]["span"][0] <= x["i"] < m["parts"][k]["span"][1]
                assert x["parts"] or not sp._letterlike(x["ch"])
            # parts: the unit of the tier's list of the sentence, at its place, held by the shown entries named
            for p in m["parts"]:
                assert hspace.tiers[p["tier"]].sentence_units[m["sid"]][p["idx"]] == p["unit"] == text[p["span"][0]:p["span"][1]]
                assert p["entries"] and "flat_pos" not in p
                for j in p["entries"]:
                    assert a["entries"][j]["origins"] == ["flat/" + p["tier"]] and p["unit"] in a["entries"][j]["words"]
            assert set(m["part_tiers"]) == {p["tier"] for p in m["parts"]} and set(m["aligned_tiers"]) <= {"RUN", "WORD", "CHAR"}
            # the word provenance of the entry is the sentence it was cut from
            assert [(r["level"], r["sids"]) for r in e["word_provenance"][e["words"][0]]] == [("word", [m["sid"]])]
    assert seen >= 3


def test_a_single_assembled_entry_is_a_choice_and_an_assembled_string_never_makes_an_answer(hspace):
    ac = CB.Cand(CB.ASSEMBLED, ("ハッシュ表",), source_sids=(0,), trace_ok=True, detail={"sid": 0, "span": [0, 5]})
    a_src = CB.Source(CB.ASSEMBLED, CB.ASSEMBLY_LISTED, (ac,))
    only = CB.combine("q", [CB.Source(CB.FLAT, "UNKNOWN_NO_EVIDENCE", ()), a_src])
    assert len(only.entries) == 1 and only.entries[0].assembled_only and only.verdict == CB.CHOICE
    o = only.answer_obj()
    assert o["answer"] is None and o["assembled_only_single"] is True and o["window_only_single"] is False
    # a window-only single is still a CHOICE, a flat single is still an ANSWER without the block
    w = CB.Cand("window/plain", ("犬",))
    assert CB.combine("q", [CB.Source("window/plain", CB.ANSWER, (w,))]).verdict == CB.CHOICE
    f = CB.Cand("flat/RUN", ("ハッシュ", "表"), source_sids=(0,))
    flat = CB.Source(CB.FLAT, CB.ANSWER, (f,))
    assert CB.combine("q", [flat]).verdict == CB.ANSWER
    # the owner's reading B (L-784, L-789): the assembled strings are display only; a flat single with an assembled string beside it stays an ANSWER
    both = CB.combine("q", [flat, CB.assembled_source(flat, hspace)])
    assert [e.origins for e in both.entries] == [("flat/RUN",), (CB.ASSEMBLED,)] and both.verdict == CB.ANSWER
    bo = both.answer_obj()
    assert bo["answer"]["origins"] == ["flat/RUN"] and bo["answer"]["path_words"] == ["ハッシュ", "表"] and bo["listed"] == 2 and bo["assembled_only_single"] is False
    assert [h["source"] for h in both.header()] == ["flat/RUN", "flat/assembled"] and both.header()[1]["listed"] == 1       # the block is still listed
    assert both.answer_obj()["blocks"][-1]["block"] == "flat/assembled"
    tx = CB.format_text(both)
    assert tx.count("答え (flat/RUN): ハッシュ / 表") == 1 and "【つなげた文字列（表示のみ）】 ハッシュ表" in tx and "候補 " not in tx.split("答え")[1].split("\n")[0]
    # the answer is the real entry even when the assembled block stands in front of it in the list (a layers / window single)
    w2 = CB.combine("q", [CB.Source(CB.FLAT, CB.ANSWER, ()), CB.Source(CB.ASSEMBLED, CB.ASSEMBLY_LISTED, (ac,)),
                          CB.Source(CB.LAYERS, CB.ANSWER, (CB.Cand("layers/RUN/1A", ("x",)),))])
    assert w2.verdict == CB.ANSWER and w2.answer_obj()["answer"]["path_words"] == ["x"]
    # several real entries are a CHOICE as before; a window-only single stays a CHOICE with or without the block
    two = CB.combine("q", [CB.Source(CB.FLAT, CB.CHOICE, (f, CB.Cand("flat/WORD", ("a",), source_sids=(0,)))), CB.assembled_source(flat, hspace)])
    assert two.verdict == CB.CHOICE
    assert CB.combine("q", [CB.Source("window/plain", CB.ANSWER, (w,)), a_src]).verdict == CB.CHOICE
    # the typed UNKNOWN of a later source is not preempted by the assembled source's NO_ASSEMBLY (it reports no UNKNOWN)
    na = CB.Source(CB.ASSEMBLED, CB.NO_ASSEMBLY, ())
    assert CB.verdict_of((), [CB.Source(CB.FLAT, CB.CHOICE, ()), na, CB.Source(CB.LAYERS, "UNKNOWN_X", ())]) == "UNKNOWN_X"
    # an assembled candidate belongs to the assembled source only, and the assembled source holds nothing else
    with pytest.raises(ValueError):
        CB.combine("q", [CB.Source(CB.FLAT, CB.CHOICE, (ac,))])
    with pytest.raises(ValueError):
        CB.combine("q", [CB.Source(CB.ASSEMBLED, CB.ASSEMBLY_LISTED, (CB.Cand("flat/RUN", ("a",)),))])


def test_the_assembled_block_is_never_merged_and_marks_nothing(hspace):
    d = {"sid": 0, "span": [0, 5]}
    ac = CB.Cand(CB.ASSEMBLED, ("ハッシュ表",), source_sids=(0,), detail=d)
    f = CB.Cand("flat/RUN", ("ハッシュ表",), source_sids=(0,))                       # the same word set, listed by the flat block
    w = CB.Cand("window/plain", ("ハッシュ表",))
    srcs = [CB.Source(CB.FLAT, CB.ANSWER, (f,)), CB.Source(CB.ASSEMBLED, CB.ASSEMBLY_LISTED, (ac,)), CB.Source("window/plain", CB.ANSWER, (w,))]
    for mode in CB.MERGES:
        c = CB.combine("q", srcs, merge=mode)
        a = [e for e in c.entries if e.assembled_only]
        assert len(a) == 1 and a[0].origins == (CB.ASSEMBLED,)                       # not merged with the flat or the window entry, in either mode
        assert [e.origins for e in c.entries if not e.assembled_only] == ([("flat/RUN",), ("window/plain",)] if mode == "none" else [("flat/RUN", "window/plain")])
        assert a[0].also_in == ()
        assert all(CB.ASSEMBLED not in e.also_in for e in c.entries)
    c = CB.combine("q", srcs)
    assert c.agreement()["entries_by_families"] == {"flat+window": 1}                # the assembled string is not an agreement of anything
    assert c.listed_before_merge == 3 and c.per_source_listed() == {"flat": 1, "flat/assembled": 1, "window/plain": 1}


def test_the_header_row_of_the_assembled_block_and_the_blocks_order(hidx, hwi):
    c = CB.ask_combined(hidx, "ハッシュ表は何ですか", effort=EFFORT, windows=hwi)
    rows = c.header()
    ix = [r["source"] for r in rows].index("flat/assembled")
    assert [r["source"] for r in rows][ix - 1] == "flat/CHAR" and rows[ix + 1]["source"] == "layers"
    assert rows[ix] == {"source": "flat/assembled", "listed": len(assembled_entries(c)), "kind": None, "kinds": {}}
    bl = c.blocks()
    b = [x for x in bl if x["block"] == "flat/assembled"][0]
    assert b["order"] == "source" and b["listed"] == rows[ix]["listed"]
    # the strings stand in the order of (sentence, start, end), no stability, no rank
    keys = [(e.members[0].detail["sid"], e.members[0].detail["span"][0], e.members[0].detail["span"][1]) for e in assembled_entries(c)]
    assert keys == sorted(keys) and all(e.members[0].stability is None for e in assembled_entries(c))
    # no assembly: a row that says so (nothing to assemble from), and it is not an abstention
    n = CB.ask_combined(hidx, "猫は何を食べますか", effort=EFFORT, windows=hwi)
    r = [r for r in n.header() if r["source"] == "flat/assembled"][0]
    assert r == {"source": "flat/assembled", "listed": 0, "kind": "NO_ASSEMBLY", "kinds": {}}
    assert [a for a in n.abstentions() if a["source"] == "flat/assembled"] == [] and "flat/assembled" not in n.abstention_counts()
    assert n.verdict == CB.CHOICE
    t = CB.format_text(c)
    assert "  flat/assembled: つなげた文字列" in t and " == flat/assembled (" in t and "【つなげた文字列】 ハッシュ表" in t and ("部品: RUN:ハッシュ" in t or "部品: WORD:ハッシュ" in t)
    assert "つなげた文字列なし (NO_ASSEMBLY)" in CB.format_text(n)
    assert "flat/assembled" not in CB.format_text(CB.ask_combined(hidx, "ハッシュ表は何ですか", effort=EFFORT, windows=hwi, assembly=False))


def test_the_assembled_flat_ask_defaults_stay_as_they_were(hidx):
    # the flat ask (T7b..T10) is untouched: no assembled key, the F2 option still its own opt-in
    base = A.ask(hidx, "ハッシュ表は何ですか", effort=EFFORT)
    assert "assembled" not in base.answer_obj() and base.assembled is None
    assert A.ask(hidx, "ハッシュ表は何ですか", effort=EFFORT).to_bytes() == base.to_bytes()
    import inspect
    assert inspect.signature(CB.ask_combined).parameters["assembly"].default is True
    assert inspect.signature(A.ask).parameters["granularity"].default is None


def test_assembly_bytes_do_not_depend_on_the_hash_seed_and_hold_no_float(tmp_path, hidx, hwi):
    script = tmp_path / "run_j.py"
    script.write_text(
        "import hashlib, sys\n"
        "sys.path.insert(0, %r)\n"
        "from tests.line3 import test_combined as T\n"
        "from verantyx.line3 import ask as A, combined as CB, slide_query as Q, space as sp\n"
        "rows = [{'title': t, 'sent': s, 'source': '%%s#%%d' %% (t, i)} for i, (t, s) in enumerate(T.HASH_TOY)]\n"
        "space = sp.build_space(rows)\n"
        "wi = Q.WindowIndex.from_space(space, None, rows=rows, level='low', z_deep='slide', place_kw={'seat_empty_axis': 'allow'})\n"
        "idx = A.Index(space, level='low')\n"
        "h = hashlib.sha256()\n"
        "for q in T.HASH_QUESTIONS:\n"
        "    for kw in ({}, {'merge': 'word_set'}, {'assembly': False}, {'window_evidence': 'plain'}):\n"
        "        c = CB.ask_combined(idx, q, effort='fast', windows=wi, **kw)\n"
        "        h.update(c.to_bytes()); h.update(CB.format_text(c, True).encode('utf-8'))\n"
        "print(h.hexdigest())\n" % ROOT)
    out = set()
    for seed in ("0", "1", "12345"):
        env = dict(os.environ, PYTHONHASHSEED=seed, PYTHONPATH=ROOT)
        r = subprocess.run([PY, str(script)], capture_output=True, text=True, env=env, cwd=ROOT, timeout=900)
        assert r.returncode == 0, r.stderr[-2000:]
        out.add(r.stdout.strip())
    assert len(out) == 1 and len(next(iter(out))) == 64

    def walk(o):
        if isinstance(o, dict):
            for v in o.values():
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)
        else:
            assert type(o).__name__ != "float"
    for q in HASH_QUESTIONS:
        for mg in CB.MERGES:
            walk(CB.ask_combined(hidx, q, effort=EFFORT, windows=hwi, merge=mg).to_json_obj())


def test_cli_assembly_switch(tmp_path):
    data = tmp_path / "h.jsonl"
    data.write_text("".join(json.dumps({"title": t, "sent": s, "source": "%s#%d" % (t, i)}, ensure_ascii=False) + "\n" for i, (t, s) in enumerate(HASH_TOY)),
                    encoding="utf-8")
    cache = str(tmp_path / "c")
    assert cli(["build", "--structure", "combined", "--data", str(data), "--cache", cache, "--level", "low"]).returncode == 0
    base = ["ask", "--data", str(data), "--cache", cache, "--level", "low", "--question", "ハッシュ表は何ですか", "--effort", EFFORT, "--structure", "combined"]
    on = cli(base + ["--format", "json"])
    explicit = cli(base + ["--format", "json", "--assembly", "on"])
    off = cli(base + ["--format", "json", "--assembly", "off"])
    assert on.returncode == explicit.returncode == off.returncode == 0, on.stderr[-1500:] + off.stderr[-1500:]
    assert on.stdout == explicit.stdout
    oa, fa = json.loads(on.stdout)["answer"], json.loads(off.stdout)["answer"]
    assert any(e["origins"] == ["flat/assembled"] for e in oa["entries"]) and "assembly" in oa and "flat/assembled" in [h["source"] for h in oa["header"]]
    assert not any(e["origins"] == ["flat/assembled"] for e in fa["entries"]) and "assembly" not in fa and "flat/assembled" not in [h["source"] for h in fa["header"]]
    t = cli(base)
    assert t.returncode == 0 and "つなげた文字列" in t.stdout and "flat/assembled" in t.stdout
    assert "つなげた文字列" not in cli(base + ["--assembly", "off"]).stdout
    seeds = [cli(base + ["--format", "json", "--show-thought"], s).stdout for s in ("0", "1", "12345")]
    assert seeds[0] == seeds[1] == seeds[2] and "flat/assembled" in seeds[0]
    assert cli(base + ["--assembly", "maybe"]).returncode == 2
    # the flat structure has no such block and takes no part in it
    flat = cli(["ask", "--data", str(data), "--cache", cache, "--level", "low", "--question", "ハッシュ表は何ですか", "--effort", EFFORT, "--layers", "off"])
    assert flat.returncode == 0 and "flat/assembled" not in flat.stdout


def test_the_block_never_changes_the_verdict_it_is_display_only(idx, wi, hidx, hwi):
    """G3-j addendum (L-789, the owner's reading B): with the switch on or off the verdict is the same for every question of both toys, and the answer
    (when there is one) is the same; the assembled strings are listed (header, blocks, entries) either way they exist."""
    n_asm = 0
    for index, windows, qs in ((idx, wi, TF.QUESTIONS), (hidx, hwi, HASH_QUESTIONS)):
        for q in qs:
            on = CB.ask_combined(index, q, effort=EFFORT, windows=windows)
            off = CB.ask_combined(index, q, effort=EFFORT, windows=windows, assembly=False)
            assert on.verdict == off.verdict, q
            assert on.answer_obj()["answer"] == off.answer_obj()["answer"], q
            n_asm += len(assembled_entries(on))
            if assembled_entries(on):
                assert [r for r in on.header() if r["source"] == "flat/assembled"][0]["listed"] == len(assembled_entries(on))
    assert n_asm > 0
