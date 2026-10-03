"""Third round (W3-a2): F1 (a wrong hypernym must not spread down a chain), F2 (a
number + a long or Latin unit is a QUANTITY) and F3 (the left-over of an image
caption is not a definition).  Synthetic material only."""
import json
import sqlite3
from collections import Counter
from pathlib import Path

import fugashi
import pytest

from tools import build_coarse_placement as bcp
from verantyx import coarse_place as cp
from verantyx import coarse_types as ct

from test_coarse_place_build import MINI_CFG, build, check_invariants, make_codex_db, q  # noqa: F401
from test_coarse_place_review2 import cfg_for, ctx_sources, ex_for  # noqa: F401

TAGGER = fugashi.Tagger()


def write_jawiki(path: Path, rows):
    with open(path, "w", encoding="utf-8") as f:
        for i, (title, text) in enumerate(rows):
            f.write(json.dumps({"title": title, "text": text, "source": "fixture",
                                "sha": "r3-%03d" % i, "split": "train"},
                               ensure_ascii=False) + "\n")


def manifest_of(pl):
    return json.loads((Path(pl) / "manifest.json").read_text(encoding="utf-8"))


# =========================================================================================
# F3: the left-over of an image caption ("の209型の何か") is not a definition
# =========================================================================================
def test_a_lead_that_starts_with_no_and_has_no_topic_is_not_a_definition(tmp_path):
    jw = tmp_path / "jw.jsonl"
    write_jawiki(jw, [
        ("カラクリ丸", "の209型の道具"),                                   # the caption's tail
        ("ハガネ丸", "ハガネ丸は、日本の道具である。"),                       # an ordinary lead
        ("ウツワ丸", "の209型の道具は、ひとつの道具である。"),               # starts with の BUT has a topic
    ])
    out = tmp_path / "p"
    assert build(out, jawiki=jw) == 0
    skips = manifest_of(out)["skipped_rows_by_reason"]["jawiki"]
    assert skips.get("caption_fragment") == 1
    assert q("カラクリ丸", out)["top"] == []                             # not typed from the fragment
    assert q("ハガネ丸", out)["top"] == ["ARTIFACT"]                      # the ordinary lead still is
    assert q("ウツワ丸", out)["top"] == ["ARTIFACT"]                      # a topic keeps the lead


def test_the_caption_rule_looks_past_leading_spaces(tmp_path):
    jw = tmp_path / "jw.jsonl"
    write_jawiki(jw, [("キカイ丸", "  の7型の道具")])
    out = tmp_path / "p"
    assert build(out, jawiki=jw) == 0
    assert manifest_of(out)["skipped_rows_by_reason"]["jawiki"].get("caption_fragment") == 1


# =========================================================================================
# F2: counters (a number followed by a unit)
# =========================================================================================
def test_the_counter_candidates_keep_one_morpheme_and_two_morpheme_units_apart():
    acc = bcp._empty_acc()
    bcp.analyze(bcp.tokenize(TAGGER, "水を5ミリリットル入れる。"), acc, 12)
    bcp.analyze(bcp.tokenize(TAGGER, "5ポイント獲得した。"), acc, 12)
    bcp.analyze(bcp.tokenize(TAGGER, "重さは3kgだ。"), acc, 12)
    assert acc["counters"]["ミリリットル"] == 1 and acc["counters"]["ポイント"] == 1
    assert acc["counters"]["kg"] == 1
    assert acc["counters2"]["ポイント獲得"] == 1                         # two morphemes: its own table
    assert "ポイント獲得" not in acc["counters"]


def test_a_long_single_morpheme_unit_and_a_latin_unit_are_learned_but_a_long_pair_is_not():
    # 4+ character single units pass (up to 6); a two-morpheme "unit" stays within 3 chars;
    # the Latin unit is not dropped because "1kg" reads as an alphanumeric code
    ctr = {"a": Counter({"ミリリットル": 300, "kg": 300, "ポイント": 300}),
           "b": Counter({"ミリリットル": 300, "kg": 300, "ポイント": 300})}
    ctr2 = {"a": Counter({"ポイント獲得": 300, "件取得": 300, "ミリリットル入れ": 300}),
            "b": Counter({"ポイント獲得": 300, "件取得": 300, "ミリリットル入れ": 300})}
    occ = ctx_sources({"a": {}, "b": {}})
    ex = ex_for(occ, counters=ctr)
    ex["counters2"] = ctr2
    res = bcp.resolve_all(ex, cfg_for(counter_min=100))
    units = dict(res["counters"])
    assert {"ミリリットル", "kg", "ポイント"} <= set(units)
    assert "ポイント獲得" not in units and "ミリリットル入れ" not in units
    assert "件取得" in units                                           # 3 chars: the old limit stays
    # a Latin-script unit is 2-3 characters: a single letter ("3D", "5G") or a longer word is code
    ctr4 = {"a": Counter({"D": 300, "Array": 300, "GHz": 300}), "b": Counter({"D": 300, "Array": 300, "GHz": 300})}
    res4 = bcp.resolve_all(ex_for(occ, counters=ctr4), cfg_for(counter_min=100))
    assert set(dict(res4["counters"])) == {"GHz"}
    # a unit that reads as a TIME unit never goes into the table
    ctr3 = {"a": Counter({"年": 500, "ミリリットル": 300}), "b": Counter({"年": 500, "ミリリットル": 300})}
    res3 = bcp.resolve_all(ex_for(occ, counters=ctr3), cfg_for(counter_min=100))
    assert "年" not in dict(res3["counters"]) and "ミリリットル" in dict(res3["counters"])


def test_notation_reads_a_learned_unit_before_the_alphanumeric_code_rule():
    ctr = ("kg", "ミリリットル")
    assert ct.notation_type("2kg", ctr) == ("QUANTITY", "number+counter")
    assert ct.notation_type("10ミリリットル", ctr) == ("QUANTITY", "number+counter")
    # without the learned table the spelling still reads as a code (unchanged)
    assert ct.notation_type("2kg") == ("IDENTIFIER", "alnum_code")
    # identifiers stay identifiers, even with counters given
    for s in ("A1-23", "ABC-123", "v2.1", "x86-64"):
        t = ct.notation_type(s, ctr)
        assert t is not None and t[0] == "IDENTIFIER", s
    # a unit that was not learned is not a quantity
    assert ct.notation_type("2gb", ctr) == ("IDENTIFIER", "alnum_code")
    # kanji numerals + a counter-looking unit stay out (as before)
    assert ct.notation_type("三kg", ctr) != ("QUANTITY", "number+counter")


def test_a_built_placement_answers_quantity_for_number_plus_long_or_latin_unit(tmp_path):
    texts_j = ["水を5ミリリットル入れる。", "容量は8メガバイトだ。", "重さは3kgだ。",
               "A1-23とABC-123を使う。", "5ポイント獲得した。"] * 4
    # a Latin unit must follow several DIFFERENT numerals (M2): "kg" does
    texts_j += ["重さは%dkgだ。" % n for n in (4, 5, 6, 7, 8, 9)]
    jw = tmp_path / "jw.jsonl"
    write_jawiki(jw, [("ホゲ%d丸" % i, t) for i, t in enumerate(texts_j)])
    cdir = tmp_path / "cx"
    make_codex_db(cdir, "conversation", texts_j)
    out = tmp_path / "p"
    assert build(out, jawiki=jw, codex_dir=cdir, families="conversation",
                 cfg={"counter_min": 3, "counter_min_sources": 2}) == 0
    for term in ("10ミリリットル", "7メガバイト", "2kg"):
        r = q(term, out)
        assert r["top"] == ["QUANTITY"] and r["origin"] == "direct", term
        assert r["axes"]["notation"]["rule"] == "number+counter"
    for term in ("A1-23", "ABC-123"):
        assert q(term, out)["top"] == ["IDENTIFIER"], term
    ctr = {r[0] for r in sqlite3.connect("file:%s/placement.sqlite?mode=ro" % out, uri=True)
           .execute("SELECT unit FROM counters")}
    assert {"ミリリットル", "メガバイト", "kg"} <= ctr
    assert "ポイント獲得" not in ctr


def _latin_ex(**over):
    """Two sources; Latin candidates told apart by share and by how many numerals they follow."""
    nums = lambda n: {str(i) for i in range(n)}                                  # noqa: E731
    ctr = {src: Counter({"zq": 100, "ab": 100, "yy": 500, "AB": 100, "mm": 100})
           for src in ("a", "b")}
    pos = {src: Counter({("zq", "N"): 100, ("ab", "N"): 5000, ("aB", "N"): 4000,
                         ("yy", "N"): 50, ("mm", "N"): 100})
           for src in ("a", "b")}
    cn = {src: {"zq": nums(8), "ab": nums(30), "yy": {"4", "5"}, "AB": nums(30), "mm": nums(8)}
          for src in ("a", "b")}
    ex = ex_for(ctx_sources({"a": {}, "b": {}}), counters=ctr)
    ex["pos"] = pos
    ex["counter_nums"] = cn
    ex.update(over)
    return ex


def test_a_latin_unit_must_follow_numerals_about_as_often_as_it_occurs_and_after_many_numerals():
    units = set(dict(bcp.resolve_all(_latin_ex(), cfg_for(counter_min=50))["counters"]))
    assert "zq" in units and "mm" in units                  # a unit: share 100 %, 8 numerals
    assert "ab" not in units                                # follows numerals 100 of 5000+4000 times
    assert "AB" not in units                                # case-insensitive: the same word as "ab"
    assert "yy" not in units                                # "4xx": 500 of 50 (all of it), 2 numerals only


def test_the_share_and_the_numerals_are_counted_per_source_and_never_pooled():
    ex = _latin_ex()
    ex["counter_nums"]["b"]["zq"] = {"1", "2"}              # in source b it follows only 2 numerals
    units = set(dict(bcp.resolve_all(ex, cfg_for(counter_min=50))["counters"]))
    assert "zq" not in units                                # one source left < counter_min_sources
    assert "zq" in set(dict(bcp.resolve_all(ex, cfg_for(counter_min=50, counter_min_sources=1))["counters"]))
    # the share of "zq" is judged per source as well
    ex2 = _latin_ex()
    ex2["pos"]["a"][("zq", "N")] = 5000
    assert "zq" not in set(dict(bcp.resolve_all(ex2, cfg_for(counter_min=50))["counters"]))


def test_a_latin_pair_from_the_two_morpheme_table_is_never_a_unit_and_an_unmeasured_stage_is_not_judged():
    ex = _latin_ex()
    ex["counters2"] = {src: Counter({"qz": 300}) for src in ("a", "b")}      # two morphemes, Latin
    units = set(dict(bcp.resolve_all(ex, cfg_for(counter_min=50))["counters"]))
    assert "qz" not in units
    # no numerals recorded (an old cache): no verdict, the unit is kept as before
    ex3 = _latin_ex()
    del ex3["counter_nums"]
    units3 = set(dict(bcp.resolve_all(ex3, cfg_for(counter_min=50))["counters"]))
    assert {"zq", "ab", "yy"} <= units3


def test_the_extraction_records_which_numerals_a_latin_unit_follows_and_merging_is_capped():
    acc = bcp._empty_acc()
    for n in (3, 4, 5, 3):
        bcp.analyze(bcp.tokenize(TAGGER, "重さは%dzqだ。" % n), acc, 12)
    bcp.analyze(bcp.tokenize(TAGGER, "水を5ミリリットル入れる。"), acc, 12)
    assert acc["counter_nums"]["zq"] == {"3", "4", "5"}
    assert "ミリリットル" not in acc["counter_nums"]                 # only Latin units
    big = {"zq": {str(i) for i in range(bcp.NUMS_CAP + 10)}}
    dst: dict = {}
    bcp._merge_nums(dst, big)
    bcp._merge_nums(dst, {"zq": {"x1", "x2"}})
    assert len(dst["zq"]) == bcp.NUMS_CAP


def test_a_built_placement_keeps_a_code_with_a_word_as_an_identifier_and_a_real_unit_as_a_quantity(tmp_path):
    # "ab" is a word that is also used right after numbers (as in "3 ab"); "zq" only ever follows numbers
    texts = ["%d ab と ab を使う。" % n + "ab を見る。" * 12 for n in (1, 2, 3, 4, 5, 6)] * 4
    texts += ["重さは%dzqだ。" % n for n in (3, 4, 5, 6, 7, 8, 9, 10)]
    jw = tmp_path / "jw.jsonl"
    write_jawiki(jw, [("ホゲ%d丸" % i, t) for i, t in enumerate(texts)])
    cdir = tmp_path / "cx"
    make_codex_db(cdir, "conversation", texts)
    out = tmp_path / "p"
    assert build(out, jawiki=jw, codex_dir=cdir, families="conversation",
                 cfg={"counter_min": 3, "counter_min_sources": 2}) == 0
    ctr = {r[0] for r in sqlite3.connect("file:%s/placement.sqlite?mode=ro" % out, uri=True)
           .execute("SELECT unit FROM counters")}
    assert "zq" in ctr and "ab" not in ctr
    r = q("5zq", out)
    assert r["top"] == ["QUANTITY"] and r["axes"]["notation"]["rule"] == "number+counter"
    r = q("5ab", out)
    assert r["top"] == ["IDENTIFIER"] and r["axes"]["notation"]["rule"] == "alnum_code"


# =========================================================================================
# F1: a chain must not spread one wrong definition
# =========================================================================================
def hyp(sentence):
    return bcp.hypernym_phrases(TAGGER, bcp.first_sentence(sentence))


def test_parallel_hypernyms_joined_by_a_conjunction_are_all_taken():
    ys, why = hyp("ホゲ丸は、何かを行っている者、もしくはグループ。")
    assert why == "" and set(ys) == {"者", "グループ"}, ys
    ys, why = hyp("ホゲ丸は、人あるいは組織。")
    assert set(ys) == {"人", "組織"}, ys
    ys, why = hyp("ホゲ丸は、人、または団体。")
    assert set(ys) == {"人", "団体"}, ys
    ys, why = hyp("ホゲ丸は、人及び組織。")
    assert set(ys) == {"人", "組織"}, ys
    ys, why = hyp("ホゲ丸は、人ないし組織。")
    assert set(ys) == {"人", "組織"}, ys
    # nothing changes for an ordinary single hypernym
    assert hyp("ホゲ丸は、日本の道具である。")[0] == ["道具"]


def test_split_hypernym_types_tie_inside_the_definition_arm_and_decide_nothing():
    defs = [("ホゲ丸", None, ["グループ", "者"], []),
            ("ホゲ子", None, ["ホゲ丸"], [])]
    ex = ex_for(ctx_sources({"a": {}}))
    ex["defs"] = defs
    res = bcp.resolve_all(ex, cfg_for())
    rows = {r[0]: r for r in res["headwords"]}
    assert rows["ホゲ丸"][2] == "MULTIPLE" and rows["ホゲ丸"][4] == "GROUP_ORG,PERSON"
    assert "ホゲ子" not in rows or rows["ホゲ子"][2] == "UNPLACED"      # nothing was handed down


def test_the_fallback_does_not_take_an_adverbial_phrase_before_a_comma():
    s = "ホゲ丸とは、平安から鎌倉時代、国を治めた領主の道具のことであり、重要である。"
    assert hyp(s)[0] == []                                           # ends in an adjective: fallback
    ys = bcp.first_clause_phrases(TAGGER, bcp.first_sentence(s))
    assert "鎌倉時代" not in ys and ys == ["道具"], ys
    # an ordinary first clause is still found
    assert bcp.first_clause_phrases(
        TAGGER, "筋肉痛は、筋肉に生じる痛みであり、その原因はさまざまである。") == ["痛み"]


def test_a_definition_found_by_the_fallback_is_its_own_arm(tmp_path):
    jw = tmp_path / "jw.jsonl"
    write_jawiki(jw, [
        ("ホゲ丸", "ホゲ丸とは、平安から鎌倉時代、国を治めた領主の道具のことであり、重要である。"),
        ("ハガネ丸", "ハガネ丸は、日本の道具である。")])
    out = tmp_path / "p"
    assert build(out, jawiki=jw, cfg={"recovered_decides": True}) == 0
    r = q("ホゲ丸", out)
    assert r["axes"]["definition_recovered"]["counts"] == {"ARTIFACT": 1}
    assert "definition" not in r["axes"]
    assert r["top"] == ["ARTIFACT"] and r["decided_by"] == ["definition_recovered"]
    assert q("ハガネ丸", out)["decided_by"] == ["definition"]
    # evidence only: the arm is shown but does not decide
    out2 = tmp_path / "p2"
    assert build(out2, jawiki=jw, cfg={"recovered_decides": False}) == 0
    r2 = q("ホゲ丸", out2)
    assert r2["top"] == [] and r2["state"] == "UNPLACED"
    con = sqlite3.connect("file:%s/placement.sqlite?mode=ro" % out2, uri=True)
    ev = con.execute("SELECT arm,type,n FROM evidence WHERE word='ホゲ丸'").fetchall()
    assert ev == [("definition_recovered", "ARTIFACT", 1)]               # kept as evidence
    cfg2 = dict(ct.DEFAULT_CONFIG)
    cfg2.update(json.loads(con.execute("SELECT v FROM meta WHERE k='config'").fetchone()[0]))
    d = ct.decide_word([(a, "jawiki", t, n, None) for a, t, n in ev], cfg2)
    arm = d["arms"]["definition_recovered"]
    assert arm["threshold_met"] is True and arm["met"] is False and arm["why"] == "RECOVERED_NOT_DECIDING"
    assert d["state"] == "UNPLACED"
    assert any(k.endswith("_recovered") and v >= 1
               for k, v in manifest_of(out)["skipped_rows_by_reason"]["jawiki"].items())


def _rows(res):
    return {r[0]: r for r in res["headwords"]}


def test_a_head_whose_final_decision_is_multiple_is_not_a_donor():
    # ブレンダ: a definition says ARTIFACT, a hearst arm of its own says GROUP_ORG -> MULTIPLE
    ex = ex_for(ctx_sources({"a": {}}))
    ex["hearst"] = {"a": Counter({("ブレンダ", "組織"): 3})}
    ex["defs"] = [("ブレンダ", None, ["道具"], []),
                  ("ホゲ子", None, ["ブレンダ"], []),
                  ("ミキサ", None, ["道具"], []),
                  ("ホゲ男", None, ["ミキサ"], [])]
    res = bcp.resolve_all(ex, cfg_for())
    rows = _rows(res)
    assert rows["ブレンダ"][2] == "MULTIPLE"
    assert "ホゲ子" not in rows or rows["ホゲ子"][2] == "UNPLACED"        # no type handed down
    assert rows["ミキサ"][2] == "DECIDED" and rows["ホゲ男"][4] == "ARTIFACT"   # a clean donor still gives
    # the old behaviour (a what-if switch) hands the plain definition type down
    res0 = bcp.resolve_all(ex, cfg_for(donor_stage_b=False))
    assert _rows(res0)["ホゲ子"][4] == "ARTIFACT"
    st = res["donor_stats"]
    assert st["excluded"]["not_decided"] >= 1
    assert st["stage_b"]["donors"] < st["stage_a"]["donors"]


def _contra_ex():
    # ミキサ2: the definition says ARTIFACT (DECIDED).  A hearst arm that does NOT reach its
    # own share threshold still points at GROUP_ORG twice: a contrary arm of another kind.
    ex = ex_for(ctx_sources({"a": {}}))
    ex["hearst"] = {"a": Counter({("ミキサ2", "組織"): 2, ("ミキサ2", "人"): 1,
                                  ("ミキサ2", "動物"): 1})}
    ex["defs"] = [("ミキサ2", None, ["道具"], []), ("ホゲ2", None, ["ミキサ2"], [])]
    return ex


def test_a_decided_head_with_enough_contrary_votes_of_another_arm_is_not_a_donor():
    res = bcp.resolve_all(_contra_ex(), cfg_for(donor_contra_min=2))
    rows = _rows(res)
    assert rows["ミキサ2"][2] == "DECIDED" and rows["ミキサ2"][4] == "ARTIFACT"
    ev = [e for e in res["evidence"] if e[0] == "ミキサ2" and e[1] == "hearst"]
    assert {e[3]: e[4] for e in ev} == {"GROUP_ORG": 2, "PERSON": 1, "ANIMAL": 1}
    assert "ホゲ2" not in rows or rows["ホゲ2"][2] == "UNPLACED"
    assert res["donor_stats"]["excluded"]["contra_arm"] >= 1
    # below the limit the head stays a donor (the small vote is not enough to stop the chain)
    res3 = bcp.resolve_all(_contra_ex(), cfg_for(donor_contra_min=3))
    assert _rows(res3)["ホゲ2"][4] == "ARTIFACT"
    assert res3["donor_stats"]["excluded"]["contra_arm"] == 0


def test_the_two_stages_are_deterministic_and_stage_b_does_not_feed_back():
    a = bcp.resolve_all(_contra_ex(), cfg_for(donor_contra_min=2))
    b = bcp.resolve_all(_contra_ex(), cfg_for(donor_contra_min=2))
    assert a["headwords"] == b["headwords"] and a["evidence"] == b["evidence"]
    assert a["donor_stats"] == b["donor_stats"]
    assert set(a["donor_stats"]) >= {"stage_a", "stage_b", "excluded", "top_donors"}
    assert set(a["timing"]) >= {"stage_a_sec", "stage_b_sec"}


def test_donor_stats_reach_the_manifest_and_count_the_dependents(tmp_path):
    jw = tmp_path / "jw.jsonl"
    write_jawiki(jw, [("ホゲ丸", "ホゲ丸は、日本の道具である。"),
                      ("ホゲ1", "ホゲ1は、日本のホゲ丸である。"),
                      ("ホゲ2", "ホゲ2は、日本のホゲ丸である。")])
    out = tmp_path / "p"
    assert build(out, jawiki=jw) == 0
    m = manifest_of(out)
    st = m["donor_stats"]
    assert st["stage_a"]["donors"] >= st["stage_b"]["donors"] >= 1
    assert set(st["excluded"]) == {"not_decided", "contra_arm"}
    top = {d["donor"]: d for d in st["top_donors"]}
    assert top["ホゲ丸"]["dependents"] == 2
    assert top["ホゲ丸"]["dependents_with_other_met_arm_elsewhere"] == 0
    assert m["config"]["donor_contra_min"] == ct.DEFAULT_CONFIG["donor_contra_min"]
    assert {"stage_a_sec", "stage_b_sec"} <= set(m["stage_seconds"])
    assert bcp.main(["verify", "--placement", str(out)]) == 0


def test_the_new_arms_keep_the_decision_invariants(tmp_path):
    jw = tmp_path / "jw.jsonl"
    write_jawiki(jw, [
        ("ホゲ丸", "ホゲ丸とは、平安から鎌倉時代、国を治めた領主の道具のことであり、重要である。"),
        ("ハガネ丸", "ハガネ丸は、日本の道具である。"),
        ("ホゲ子", "ホゲ子は、何かを行っている者、もしくはグループ。")])
    out = tmp_path / "p"
    assert build(out, jawiki=jw, cfg={"recovered_decides": True}) == 0
    con = sqlite3.connect("file:%s/placement.sqlite?mode=ro" % out, uri=True)
    cfg = dict(ct.DEFAULT_CONFIG)
    cfg.update(json.loads(con.execute("SELECT v FROM meta WHERE k='config'").fetchone()[0]))
    evs = {}
    for w, a, s, t, n, b in con.execute("SELECT word,arm,src,type,n,base FROM evidence"):
        evs.setdefault(w, []).append((a, s, t, n, b))
    words = [r[0] for r in con.execute("SELECT word FROM headwords WHERE origin='direct'")]
    for w in words:
        r = q(w, out)
        met = {k for k, a in r["axes"].items() if a["met"]}
        assert met == set(r["decided_by"]), w
        check_invariants(r)
    for w, state, top, by in con.execute(
            "SELECT word,state,top,by FROM headwords WHERE state IN ('DECIDED','MULTIPLE')"):
        d = ct.decide_word(evs.get(w, []), cfg)
        assert (d["state"], ",".join(d["tops"]), "+".join(d["by"])) == (state, top, by), w
    assert q("ホゲ子", out)["state"] == "MULTIPLE"
