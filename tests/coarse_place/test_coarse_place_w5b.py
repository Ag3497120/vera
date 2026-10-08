"""W5-b / W3-a2: the contract of the query's spelling, and the time-unit reading of a learned counter.

Contract (docs/COARSE_PLACEMENT.md section 11.9): the question is NFKC-normalized and every lookup uses that one spelling; hiragana and
katakana are different words (no reading normalization), so ``state`` / ``top`` come from the evidence of the asked spelling alone;
``spelling`` only reports what the other kana spelling's headword row says.  Synthetic material only (made-up words, not the words of the
attack file).
"""
import json
import shutil
import sqlite3
from pathlib import Path

import pytest

from verantyx import coarse_place as cp
from verantyx import coarse_types as ct

from test_coarse_place_build import build, check_invariants, q  # noqa: F401

ROWS = [
    # the two spellings of a sound with DIFFERENT evidence
    ("ヒナタ丸", "ヒナタ丸は、日本の道具である。"),
    ("ひなた丸", "ひなた丸は、日本の会社である。"),
    # the two spellings with the SAME evidence
    ("モモ丸", "モモ丸は、日本の道具である。"),
    ("もも丸", "もも丸は、日本の道具である。"),
    # only one spelling is placed
    ("ハガネ丸", "ハガネ丸は、日本の道具である。"),
    # a Latin-letter word
    ("ABC丸", "ABC丸は、日本の会社である。"),
]


@pytest.fixture(scope="module")
def placement(tmp_path_factory):
    d = tmp_path_factory.mktemp("w5b")
    jw = d / "jw.jsonl"
    with open(jw, "w", encoding="utf-8") as f:
        for i, (title, text) in enumerate(ROWS):
            f.write(json.dumps({"title": title, "text": text, "source": "fixture", "sha": "w5b-%03d" % i,
                                "split": "train"}, ensure_ascii=False) + "\n")
    out = d / "p"
    assert build(out, jawiki=jw) == 0
    return out


def _edited_copy(src: Path, dst: Path, *, headwords=(), counters=()):
    """A copy of a placement with rows added (the manifest's table counts follow, so it still opens)."""
    shutil.copytree(src, dst)
    con = sqlite3.connect(str(dst / "placement.sqlite"))
    for row in headwords:
        con.execute("INSERT INTO headwords(word, ns, state, origin, top, kind, n_seen, by) VALUES (?,?,?,?,?,?,?,?)", row)
    for unit in counters:
        con.execute("INSERT INTO counters(unit, n) VALUES (?, 99)", (unit,))
    n_head = con.execute("SELECT COUNT(*) FROM headwords").fetchone()[0]
    n_ctr = con.execute("SELECT COUNT(*) FROM counters").fetchone()[0]
    con.commit()
    con.close()
    mp = dst / "manifest.json"
    m = json.loads(mp.read_text(encoding="utf-8"))
    m["outputs"]["tables"]["headwords"] = n_head
    m["outputs"]["tables"]["counters"] = n_ctr
    mp.write_text(json.dumps(m), encoding="utf-8")
    return dst


def _answer(r):
    return (r["state"], r["top"], r["origin"], r["candidates"])


# ------------------------------------------------------------------ NFKC: one spelling for every lookup
def test_a_half_width_kana_and_a_full_width_latin_term_answer_as_their_nfkc_form(placement):
    assert _answer(q("ﾋﾅﾀ丸", placement)) == _answer(q("ヒナタ丸", placement))
    assert _answer(q("ＡＢＣ丸", placement)) == _answer(q("ABC丸", placement))
    assert q("ＡＢＣ丸", placement)["top"] == ["GROUP_ORG"]


def test_the_term_of_the_answer_is_the_callers_string_and_the_spelling_says_what_was_searched(placement):
    r = q("  ＡＢＣ丸 ", placement)
    assert r["term"] == "ＡＢＣ丸"                                    # stripped, not normalized
    sp = r["spelling"]
    assert (sp["query"], sp["normalized"], sp["normalization"], sp["kana"]) == ("ＡＢＣ丸", "ABC丸", "NFKC", "DISTINCT")


def test_an_unplaced_row_for_the_raw_spelling_does_not_hide_the_decided_nfkc_row(placement, tmp_path):
    # a headword row for the FULL-WIDTH spelling that says only "in the material, nothing decided" (the old code looked at it first
    # and never reached the NFKC row)
    copy = _edited_copy(placement, tmp_path / "p2", headwords=[("ＡＢＣ丸", None, "UNPLACED", None, "", "title", 1, "")])
    assert cp._open(str(copy))[0].head("ＡＢＣ丸")[1] == "UNPLACED"
    r = q("ＡＢＣ丸", copy)
    assert (r["state"], r["top"]) == ("DECIDED", ["GROUP_ORG"])
    assert r["term"] == "ＡＢＣ丸"


def test_an_nfkc_equal_number_and_unit_has_the_same_type(placement, tmp_path):
    copy = _edited_copy(placement, tmp_path / "p3", counters=["年後"])
    for a, b in (("３年後", "3年後"), ("1０年後", "10年後")):
        assert _answer(q(a, copy)) == _answer(q(b, copy)), (a, b)
    assert q("３年後", copy)["top"] == ["TIME"]


# ------------------------------------------------------------------ kana: different words, one answer each
def test_each_kana_spelling_answers_from_its_own_evidence_and_says_the_other_one_differs(placement):
    kata, hira = q("ヒナタ丸", placement), q("ひなた丸", placement)
    assert (kata["state"], kata["top"]) == ("DECIDED", ["ARTIFACT"])
    assert (hira["state"], hira["top"]) == ("DECIDED", ["GROUP_ORG"])
    assert kata["spelling"]["kana_variant"] == {"term": "ひなた丸", "state": "DECIDED", "top": ["GROUP_ORG"], "origin": "direct"}
    assert hira["spelling"]["kana_variant"] == {"term": "ヒナタ丸", "state": "DECIDED", "top": ["ARTIFACT"], "origin": "direct"}
    assert kata["spelling"]["why"] == hira["spelling"]["why"] == "KANA_VARIANT_DIFFERS"


def test_two_spellings_that_agree_say_nothing_is_different(placement):
    r = q("モモ丸", placement)
    assert r["spelling"]["kana_variant"]["top"] == ["ARTIFACT"] and r["spelling"]["why"] is None
    assert q("もも丸", placement)["spelling"]["why"] is None


def test_a_spelling_with_no_answer_of_its_own_takes_the_type_of_its_other_kana_spelling_as_an_estimate(placement):
    """Auditor ruling C1 (W5-b round 4; replaces the test that pinned "the other kana form is never used"): an UNPLACED / UNKNOWN spelling whose
    other spelling is DECIDED and direct gets that type, marked as an estimate."""
    r = q("はがね丸", placement)                       # only the katakana form is in the placement
    assert (r["state"], r["top"], r["origin"], r["estimate_basis"], r["constructed"]) == ("DECIDED", ["ARTIFACT"], "estimated", "kana_variant", True)
    assert r["spelling"]["why"] == "ESTIMATED_FROM_KANA_VARIANT:ハガネ丸"
    assert r["spelling"]["kana_variant"] == {"term": "ハガネ丸", "state": "DECIDED", "top": ["ARTIFACT"], "origin": "direct"}
    assert r["neighbors"] == [{"word": "ハガネ丸", "type": "ARTIFACT", "via": "kana_variant:ハガネ丸"}]
    assert r["candidates"] == [{"type": "ARTIFACT", "axes": {"kana_variant": 1}}]
    assert r["axes"]["kana_variant"] == {"term": "ハガネ丸", "state": "DECIDED", "top": ["ARTIFACT"], "origin": "direct"}
    assert "decided_by" not in r and r["term"] == "はがね丸"
    k = q("ハガネ丸", placement)                         # the placed form has no other spelling row: unchanged, nothing invented
    assert (k["state"], k["origin"], k["estimate_basis"]) == ("DECIDED", "direct", None)
    assert k["spelling"]["kana_variant"] is None and k["spelling"]["why"] is None


def test_a_spelling_that_has_an_answer_of_its_own_keeps_it_exactly_as_the_answer_function_gives_it(placement):
    """The borrowing only fills a state that is UNPLACED / UNKNOWN: a direct answer, a nearness estimate and a DECIDED / MULTIPLE row all keep
    the answer of ``_answer``."""
    for term in ("ヒナタ丸", "ひなた丸", "モモ丸", "ﾋﾅﾀ丸", "ハガネ丸"):
        r = q(term, placement)
        without = {k: v for k, v in r.items() if k not in ("spelling", "term", "frame_generated")}      # W3-b5 (integration): `query` adds frame_generated; `_answer` does not
        again = cp._answer(cp._open(str(placement))[0], r["spelling"]["normalized"], None, None)
        again.pop("term")
        assert without == again, term
        assert r["spelling"]["why"] != "ESTIMATED_FROM_KANA_VARIANT:" + cp._kana_swapped(r["spelling"]["normalized"]), term


def test_the_borrowing_is_made_only_for_a_direct_decided_variant_of_a_single_script_spelling(placement, tmp_path):
    copy = _edited_copy(placement, tmp_path / "p4", headwords=[
        ("ツバキ丸", "N", "MULTIPLE", "direct", "ARTIFACT,GROUP_ORG", "title", 3, "x"),     # the variant is MULTIPLE
        ("ツル丸", "N", "DECIDED", "estimated", "ARTIFACT", "title", 3, "x"),               # the variant is an estimate
        ("ハガネまる", "N", "DECIDED", "direct", "ARTIFACT", "title", 3, "x"),               # the asked spelling mixes the two scripts
        ("はがねもも丸", "N", "DECIDED", "direct", "GROUP_ORG", "title", 3, "x"),            # the asked spelling has a nearness estimate of its own
        ("ひなたもも丸", "N", "DECIDED", "direct", "GROUP_ORG", "title", 3, "x"),
    ])
    for term, why in (("つばき丸", "KANA_VARIANT_DIFFERS"), ("つる丸", "KANA_VARIANT_DIFFERS"), ("はがねマル", "KANA_VARIANT_DIFFERS")):
        r = q(term, copy)
        assert (r["state"], r["top"], r["origin"], r["estimate_basis"]) in (("UNKNOWN", [], None, None), ("UNPLACED", [], None, None)), term
        assert r["spelling"]["why"] == why, term
    near = q("ハガネモモ丸", copy)                      # estimated by nearness (a placed right-hand word): not replaced by the variant
    assert (near["state"], near["origin"], near["estimate_basis"], near["top"]) == ("DECIDED", "estimated", "proximity", ["ARTIFACT"])
    assert near["spelling"]["why"] == "KANA_VARIANT_DIFFERS"
    # a variant that is borrowed from only when the asked spelling has nothing: the same shape one script over
    taken = q("ヒナタモモ丸", copy)
    assert (taken["origin"], taken["estimate_basis"], taken["top"]) == ("estimated", "kana_variant", ["GROUP_ORG"])


def test_an_answer_that_is_already_decided_or_multiple_is_never_replaced_by_the_borrowing(placement):
    pl = cp._open(str(placement))[0]
    for state, origin, basis in (("DECIDED", "estimated", "generated"), ("DECIDED", "estimated", "proximity"), ("MULTIPLE", "direct", None)):
        answer = {"state": state, "origin": origin, "estimate_basis": basis, "axes": {}, "context": {"role": None, "predicate": None},
                  "seen_in_material": True, "placement": {}}
        assert cp._borrow_kana_variant(pl, "はがね丸", answer) is None, (state, origin, basis)


def test_a_missing_placement_borrows_nothing(tmp_path):
    r = cp.query("はがね丸", placement=str(tmp_path / "nothing"))
    assert r["state"] == "NO_PLACEMENT" and r["origin"] is None and r["estimate_basis"] is None and r["spelling"]["why"] is None


def test_contract_kana_distinct_hiragana_and_katakana_are_not_bound_into_one_head_word(placement):
    """The decision (W5-b, docs/COARSE_PLACEMENT.md 11.9): a reading normalization was measured on the frozen L2 data and turned two
    right answers into wrong ones, so the two spellings stay two words.  If this test must change, that is a change of contract."""
    kata, hira = q("ヒナタ丸", placement), q("ひなた丸", placement)
    assert kata["top"] != hira["top"]
    assert kata["spelling"]["kana"] == hira["spelling"]["kana"] == "DISTINCT"
    assert (kata["state"], kata["top"]) == (cp.query("ヒナタ丸", placement=str(placement))["state"], ["ARTIFACT"])


def test_a_missing_placement_answers_with_a_spelling_too(tmp_path):
    r = cp.query("ひなた丸", placement=str(tmp_path / "nothing"))
    assert r["state"] == "NO_PLACEMENT" and r["term"] == "ひなた丸"
    assert r["spelling"]["kana_variant"] is None and r["spelling"]["why"] is None and r["spelling"]["normalized"] == "ひなた丸"


def test_the_kana_offset_swaps_both_ways_and_leaves_the_rest():
    swap = cp._kana_swapped
    assert swap("ひなた丸") == "ヒナタ丸" and swap("ヒナタ丸") == "ひなた丸"
    assert swap("ゔー") == "ヴー" and swap("ABC123") == "ABC123"
    assert swap("あアa") == "アあa"


# ------------------------------------------------------------------ B1: a learned unit that begins with a time unit
COUNTERS = frozenset({"年後", "週間後", "か月後", "日前", "世紀末", "メートル", "ms", "人", "日本", "年生"})


@pytest.mark.parametrize("term,want", [
    ("3年後", ("TIME", "number+time_unit_head")),
    ("12週間後", ("TIME", "number+time_unit_head")),            # the longest head is 週間, not 週
    ("5か月後", ("TIME", "number+time_unit_head")),
    ("7日前", ("TIME", "number+time_unit_head")),
    ("21世紀末", ("TIME", "number+time_unit_head")),
    ("３年後", ("TIME", "number+time_unit_head")),               # full-width digits
    ("3メートル", ("QUANTITY", "number+counter")),              # a learned unit with no time unit at its head
    ("10ms", ("QUANTITY", "number+counter")),
    ("5人", ("QUANTITY", "number+counter")),
    ("3年", ("TIME", "number+time_unit")),                      # the seed rule, unchanged
    ("3時間", ("TIME", "number+time_unit")),
    ("三年後", None),                                           # a kanji numeral: not read as a number + unit
    ("千日前", None),
    ("3分の1", None),                                           # not a learned unit
    ("3秒ごと", None),                                          # begins with a time unit but is NOT in this counters set
])
def test_notation_type_reads_a_learned_unit_with_a_time_unit_head_as_time(term, want):
    assert ct.notation_type(term, COUNTERS) == want


def test_without_learned_counters_nothing_changes():
    assert ct.notation_type("3年後", None) is None
    assert ct.notation_type("3年後", frozenset()) is None
    assert ct.notation_type("3年", frozenset()) == ("TIME", "number+time_unit")


def test_the_head_is_found_by_structure_not_by_a_list_of_words():
    f = ct._time_unit_head
    assert f("年後") == "年" and f("週間後") == "週間" and f("時間制") == "時間" and f("か月後") == "か月"
    assert f("年") is None and f("メートル") is None and f("") is None
    assert f("ぬ年後") is None                                  # the head must be at the start
