"""Second-round fixes (W3-a review r1): the arms decide only when their own
threshold is met, `met` says what really decided, sources never pool (namespace,
counters, context display), `]]` leads, paren aliases, taxonomic ranks, the
recursive left side and the left-unit estimate."""
import json
import sqlite3
from collections import Counter
from pathlib import Path

import pytest

from tools import build_coarse_placement as bcp
from verantyx import coarse_place as cp
from verantyx import coarse_types as ct

from test_coarse_place_build import (MINI_CFG, build, check_invariants, make_codex_db,
                                      mini, q, roles)  # noqa: F401

TREE = Path(__file__).resolve().parents[2]


def cfg_for(**kw):
    c = dict(ct.DEFAULT_CONFIG)
    c.update({"min_seen": 1, "ctx_min_total": 4, "ctx_min_share_pct": 60, "ctx_min_lift_pct": 150,
              "role_min": 2, "role_min_share_pct": 60, "ctx_store_min": 1,
              "role_min_sources": 2, "counter_min": 100, "counter_min_sources": 2})
    c.update(kw)
    return c


def ctx_sources(extra_by_src):
    """Context tables that make 食べる/を a food slot and 笑う/が a person slot, in
    every given source, plus the extra uses of the word under test."""
    foods = ["料理", "食品", "飲料", "野菜"]
    people = ["人", "選手", "俳優", "歌手"]
    occ = {}
    for src, extra in extra_by_src.items():
        c = Counter()
        for w in foods:
            c[(w, "を", "食べる")] += 3
        for w in people:
            c[(w, "が", "笑う")] += 3
        c.update(extra)
        occ[src] = c
    return occ


def ex_for(occ, pos=None, sahen=None, counters=None):
    srcs = list(occ)
    return {"occ": occ,
            "pos": pos or {s: Counter() for s in srcs},
            "sahen": sahen or {s: Counter() for s in srcs},
            "counters": counters or {s: Counter() for s in srcs},
            "defs": [], "aliases": [], "hearst": {}}


# --- M1: a role arm that did not meet its threshold is not a source ------------------
def test_a_role_source_below_its_threshold_does_not_count_as_a_source():
    occ = ctx_sources({"a": {("ホゲ", "を", "食べる"): 3}, "b": {("ホゲ", "を", "食べる"): 1}})
    # ホゲ has votes in BOTH sources, but only source a reaches role_min=2
    res = bcp.resolve_all(ex_for(occ), cfg_for())
    row = {r[0]: r for r in res["headwords"]}["ホゲ"]
    assert row[2] == "UNPLACED" and row[4] == "" and row[3] is None
    ev = {(e[1], e[2]) for e in res["evidence"] if e[0] == "ホゲ"}
    assert ev == {("role", "a"), ("role", "b")}                      # the votes are kept
    # both sources meet it -> decided (the same word, enough votes in b)
    occ2 = ctx_sources({"a": {("ホゲ", "を", "食べる"): 3}, "b": {("ホゲ", "を", "食べる"): 2}})
    row2 = {r[0]: r for r in bcp.resolve_all(ex_for(occ2), cfg_for())["headwords"]}["ホゲ"]
    assert row2[2] == "DECIDED" and row2[4] == "SUBSTANCE_FOOD"
    assert set(row2[7].split("+")) == {"role@a", "role@b"}


def test_decide_word_names_the_arm_that_was_set_aside():
    cfg = cfg_for()
    ev = [("definition", "jawiki", "PLACE", 1, None),
          ("role", "a", "PLACE", 5, None), ("role", "b", "PERSON", 1, None)]
    d = ct.decide_word(ev, cfg)
    assert d["state"] == "DECIDED" and d["tops"] == ["PLACE"] and d["by"] == ["definition"]
    assert d["arms"]["role@a"]["threshold_met"] is True and d["arms"]["role@a"]["met"] is False
    assert d["arms"]["role@a"]["why"] == "ROLE_SINGLE_SOURCE"
    assert d["arms"]["role@b"]["threshold_met"] is False and d["arms"]["role@b"]["why"] is None
    # nothing but the lone role source: no decision at all
    d2 = ct.decide_word([("role", "a", "PLACE", 5, None)], cfg)
    assert d2["state"] == "UNPLACED" and d2["tops"] == [] and d2["by"] == []
    # a tie inside one arm stays a tie
    d3 = ct.decide_word([("definition", "jawiki", "PLACE", 1, None),
                         ("definition", "jawiki", "PERSON", 1, None)], cfg)
    assert d3["state"] == "MULTIPLE" and d3["tops"] == ["PERSON", "PLACE"]


def test_sahen_and_pos_class_use_their_own_base():
    cfg = cfg_for(sahen_min=3, sahen_min_share_pct=30, pos_min=3)
    # 3 sahen uses out of 20 noun uses (15%) are below the share; of 6 uses, above
    assert ct.arm_verdict("sahen", {"EVENT_ACT": 3}, cfg, 20) == []
    assert ct.arm_verdict("sahen", {"EVENT_ACT": 3}, cfg, 6) == ["EVENT_ACT"]
    # adjective uses must not be outnumbered by verb uses
    assert ct.arm_verdict("pos_class", {"P_STATE": 4}, cfg, 9) == []
    assert ct.arm_verdict("pos_class", {"P_STATE": 4}, cfg, 4) == ["P_STATE"]


# --- M2: `met` is what decided ---------------------------------------------------------
def _all_direct_words(pl):
    con = sqlite3.connect("file:%s?mode=ro" % (pl / "placement.sqlite"), uri=True)
    try:
        return [r[0] for r in con.execute(
            "SELECT word FROM headwords WHERE origin='direct' ORDER BY word")]
    finally:
        con.close()


@pytest.mark.parametrize("which", ["mini", "roles"])
def test_the_met_arms_are_exactly_the_deciding_arms(which, mini, roles):
    pl = {"mini": mini, "roles": roles}[which]
    words = _all_direct_words(pl)
    assert words
    for w in words:
        r = q(w, pl)
        assert r["state"] in ("DECIDED", "MULTIPLE")
        met = {k for k, a in r["axes"].items() if a["met"]}
        assert met == set(r["decided_by"]), (w, met, r["decided_by"])
        for k, a in r["axes"].items():
            if a["met"]:
                assert a["threshold_met"] is True and a["why"] is None
            if a["why"]:
                assert a["threshold_met"] is True and a["met"] is False
        check_invariants(r)


def test_the_query_recomputes_the_stored_decision(mini, roles):
    for pl in (mini, roles):
        con = sqlite3.connect("file:%s?mode=ro" % (pl / "placement.sqlite"), uri=True)
        cfg = dict(ct.DEFAULT_CONFIG)
        cfg.update(json.loads(con.execute("SELECT v FROM meta WHERE k='config'").fetchone()[0]))
        evs = {}
        for w, a, s, t, n, b in con.execute("SELECT word,arm,src,type,n,base FROM evidence"):
            evs.setdefault(w, []).append((a, s, t, n, b))
        for w, state, top, by in con.execute(
                "SELECT word,state,top,by FROM headwords WHERE state IN ('DECIDED','MULTIPLE')"):
            d = ct.decide_word(evs.get(w, []), cfg)
            assert (d["state"], ",".join(d["tops"]), "+".join(d["by"])) == (state, top, by), w
        con.close()


# --- M3: no pooling across sources ---------------------------------------------------------
def test_a_word_noun_in_one_source_and_adjective_in_another_is_not_called_a_noun():
    occ = ctx_sources({"a": {}, "b": {}})
    pos = {"a": Counter({("ホゲ", "N"): 5}), "b": Counter({("ホゲ", "A"): 5})}
    sahen = {"a": Counter({"ホゲ": 4}), "b": Counter()}
    res = bcp.resolve_all(ex_for(occ, pos=pos, sahen=sahen), cfg_for(sahen_min=3, pos_min=3))
    row = {r[0]: r for r in res["headwords"]}["ホゲ"]
    # both sets of arms are evaluated; they overlay and split: no namespace is chosen
    assert row[1] == "NP" and row[2] == "MULTIPLE" and row[4] == "EVENT_ACT,P_STATE"
    votes = {(e[2], e[3]): e[4] for e in res["evidence"] if e[0] == "ホゲ" and e[1] == "ns_vote"}
    assert votes == {("a", "N"): 5, ("a", "P"): 0, ("b", "N"): 0, ("b", "P"): 5}


def test_a_tie_between_noun_and_verb_uses_does_not_default_to_noun():
    occ = ctx_sources({"a": {}})
    pos = {"a": Counter({("ホゲ", "N"): 2, ("ホゲ", "V"): 2})}
    res = bcp.resolve_all(ex_for(occ, pos=pos), cfg_for())
    row = {r[0]: r for r in res["headwords"]}["ホゲ"]
    assert row[1] == "NP" and row[2] == "UNPLACED"


def test_sources_that_agree_on_the_namespace_keep_it():
    occ = ctx_sources({"a": {}, "b": {}})
    pos = {"a": Counter({("ホゲ", "N"): 5}), "b": Counter({("ホゲ", "N"): 1, ("ホゲ", "V"): 0})}
    res = bcp.resolve_all(ex_for(occ, pos=pos), cfg_for())
    row = {r[0]: r for r in res["headwords"]}["ホゲ"]
    assert row[1] == "N"


def test_a_counter_must_clear_its_threshold_in_enough_sources_never_pooled():
    occ = ctx_sources({"a": {}, "b": {}, "c": {}})
    ctr = {"a": Counter({"座": 300, "杯": 150}), "b": Counter({"座": 1, "杯": 150}),
           "c": Counter({"座": 1})}
    res = bcp.resolve_all(ex_for(occ, counters=ctr), cfg_for(counter_min=100))
    units = dict(res["counters"])
    # 座: 302 uses in all, but only ONE source clears 100 -> not a counter
    assert "座" not in units
    assert units["杯"] == 2                                  # two sources: kept (n = sources)
    res1 = bcp.resolve_all(ex_for(occ, counters=ctr), cfg_for(counter_min=100, counter_min_sources=1))
    assert "座" in dict(res1["counters"])


def test_the_context_stage_shows_each_sources_counts_not_their_sum(roles):
    r = q("ホゲラ", roles, context_role="を", context_predicate="食べる")
    ax = r["axes"]["context"]
    assert ax["counts"] == {}
    by = ax["counts_by_source"]
    assert set(by) == {"codex:conversation", "codex:narrative", "jawiki"} & set(by) and len(by) >= 2
    for src, counts in by.items():
        assert src.startswith("codex:") or src == "jawiki"
        assert counts.get("SUBSTANCE_FOOD", 0) > 0


# --- M5: a `]]` caption may come before or after the definition ---------------------------
def test_definition_text_takes_the_part_that_starts_with_the_topic_or_the_title():
    # the definition first, the caption's tail after (the old rule threw it away)
    t, how = bcp.definition_text("は、日本の元号の一つ。 。]] 大正の後、平成の前。", "ホゲ元")
    assert how == "part_first" and bcp.first_sentence(t.strip().lstrip("。、 ")) == "は、日本の元号の一つ。"
    # the caption's head first, the definition after
    t, how = bcp.definition_text("と形態学]] ホゲ（ほげ）は、哺乳類の一種である。", "ホゲ")
    assert how == "part" and t.strip().startswith("ホゲ（")
    # nothing recognisable: the last part, as before
    t, how = bcp.definition_text("どこか]] 次の文。", "ホゲ")
    assert how == "last" and t == " 次の文。"
    assert bcp.definition_text("括弧なし。", "ホゲ") == ("括弧なし。", "plain")
    # "とは" also counts as a topic marker
    assert bcp.definition_text("とは、人のこと。 ]] 絵", "ホゲ")[1] == "part_first"


def test_a_lead_with_the_definition_before_the_caption_is_typed_and_counted(tmp_path):
    rows = [
        {"title": "ホゲ元", "text": "は、日本の元号の一つ。 。]] 大正の後、平成の前。"},
        {"title": "ムゲン", "text": "と形態学]] ムゲン（無限）は、哺乳類の一種である。"},
        {"title": "ナシ", "text": "どこか]] ナシは、人である。"},
    ]
    jw = tmp_path / "jw.jsonl"
    jw.write_text("".join(json.dumps(dict(r, source="x", sha="s%d" % i, split="train"),
                                     ensure_ascii=False) + "\n" for i, r in enumerate(rows)),
                  encoding="utf-8")
    out = tmp_path / "p"
    assert build(out, jawiki=jw) == 0
    assert q("ホゲ元", out)["top"] == ["TIME"]
    assert q("ムゲン", out)["top"] == ["ANIMAL"]
    m = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    sk = m["skipped_rows_by_reason"]["jawiki"]
    assert sk["bracket_rule_changed"] == 1                    # only the first lead is read differently
    assert sk["bracket_text_part_first"] == 1 and sk["bracket_text_part"] == 2   # ムゲン, ナシ: the last part, as before
    # 無限 is another spelling of ムゲン (an arm of its own, never added to the others)
    r = q("無限", out)
    assert r["top"] == ["ANIMAL"] and r["decided_by"] == ["paren_alias"]
    assert r["axes"]["paren_alias"]["met"] is True and "alias" not in r["axes"]


def test_paren_alias_takes_only_a_plain_first_element():
    f = bcp.paren_alias_of
    assert f("キツネ（狐）は、哺乳類。", "キツネ", 12) == "狐"
    assert f("トラ（虎、学名：Panthera）は、", "トラ", 12) == "虎"
    assert f("甲（こう つ、1886年 - ）は、", "甲", 12) is None            # a reading with a space
    assert f("甲（学名：Canis）は、", "甲", 12) is None
    assert f("甲（Jaguar）は、", "甲", 12) is None
    assert f("甲（2000年）は、", "甲", 12) is None
    assert f("甲（甲）は、", "甲", 12) is None                              # itself
    assert f("乙は、甲（こう）の", "甲", 12) is None                        # not right after the title


# --- M6: taxonomic ranks, recursive left side, left unit ----------------------------------
def test_a_taxonomic_rank_phrase_takes_the_type_of_its_last_taxon():
    donors = {"ホゲ": "ANIMAL"}
    assert bcp.type_of("哺乳綱食肉目ホゲ科ホゲ亜科", donors, 2) == "ANIMAL"
    assert bcp.type_of("ホゲ科", donors, 2) == "ANIMAL"
    assert bcp.type_of("ホゲ属", donors, 2) == "ANIMAL"
    assert bcp.type_of("二番目", donors, 2) is None                  # an ordinary word with 目
    assert bcp.type_of("科", donors, 2) is None
    ys, why = bcp.hypernym_phrases(
        __import__("fugashi").Tagger(), "ホゲ（甲）は、哺乳綱食肉目ホゲ科ホゲ亜科の一部。")
    assert why == "" and ys == ["哺乳綱食肉目ホゲ科ホゲ亜科"]


@pytest.fixture(scope="module")
def shape(tmp_path_factory):
    base = tmp_path_factory.mktemp("shape")
    rows = [
        {"title": "夜勤", "text": "夜勤は、夜に働くことである。夜勤と専従と看護の話。"},
        {"title": "専従", "text": "専従は、それだけに従うことである。"},
        {"title": "ガシラ主任", "text": "ガシラ主任は、人である。"},
        {"title": "ガシラ課長", "text": "ガシラ課長は、人である。"},
        {"title": "ガシラ部長", "text": "ガシラ部長は、人である。"},
        {"title": "ガシラ社員", "text": "ガシラ社員は、人である。"},
    ]
    jw = base / "jw.jsonl"
    jw.write_text("".join(json.dumps(dict(r, source="x", sha="s%d" % i, split="train"),
                                     ensure_ascii=False) + "\n" for i, r in enumerate(rows)),
                  encoding="utf-8")
    out, off = base / "on", base / "off"
    assert build(out, jawiki=jw, cfg={"kin_left": True, "kin_left_min_count": 3,
                                      "kin_left_min_share_pct": 70}) == 0
    assert build(off, jawiki=jw, cfg={"left_recursive": False, "kin_left": False}) == 0
    return out, off


def test_a_long_compound_whose_left_part_is_itself_made_of_words_is_estimated(shape):
    on, off = shape
    r = q("夜勤専従会社", on)
    assert r["origin"] == "estimated" and r["constructed"] is True and r["top"] == ["GROUP_ORG"]
    assert r["neighbors"] and r["neighbors"][0]["via"].startswith("head:")
    # without the recursion the left side must itself be a word: nothing to build on
    r0 = q("夜勤専従会社", off)
    assert r0["top"] == [] and r0["state"] in ("UNKNOWN", "UNPLACED")
    # a left side that is not made of words stays unknown (nodes are real words or atoms)
    r2 = q("ポルメリス会社", on)
    assert r2["top"] == [] and r2["state"] in ("UNKNOWN", "UNPLACED")
    r3 = q("夜勤ポルメ会社", on)
    assert r3["top"] == []


def test_a_fragment_that_is_the_left_unit_of_placed_words_is_estimated_from_them(shape):
    on, off = shape
    r = q("ガシラ", on)
    assert r["origin"] == "estimated" and r["constructed"] is True and r["top"] == ["PERSON"]
    assert any(n["via"] == "kin:ガシラ@L" for n in r["neighbors"])
    assert "morphology:kin_left" in r["axes"]
    check_invariants(r)
    assert q("ガシラ", off)["top"] == []


def test_the_left_unit_tier_is_off_by_default_and_strict_when_on(shape):
    """The default thresholds (chosen on dev) are stricter than the general kin
    thresholds: four words are not a family."""
    assert ct.DEFAULT_CONFIG["kin_left"] is False        # a coverage rule that added errors on dev
    assert ct.DEFAULT_CONFIG["kin_left_min_count"] > ct.DEFAULT_CONFIG["kin_min_count"]
    assert ct.DEFAULT_CONFIG["kin_left_min_share_pct"] >= ct.DEFAULT_CONFIG["kin_min_share_pct"]


def test_a_manifest_mismatch_in_any_table_is_detected(tmp_path, mini):
    import shutil
    d = tmp_path / "tampered"
    shutil.copytree(mini, d)
    con = sqlite3.connect(str(d / "placement.sqlite"))
    con.execute("INSERT INTO unit_sample VALUES ('ZZ','R','x')")      # a small table, not a big one
    con.commit()
    con.close()
    r = cp.query("土手", placement=str(d))
    assert r["state"] == "NO_PLACEMENT" and r["placement"]["reason"] == "MANIFEST_MISMATCH"
