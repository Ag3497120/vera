"""Generated definitions in the placement (W3-a2): their origin stays on the answer,
a word placed by a generated sentence ALONE is an estimate (generated), a generated
sentence never settles a tie, and what it placed is never passed on."""
import json
import shutil
import sqlite3
from collections import Counter
from pathlib import Path

import fugashi
import pytest

from tools import build_coarse_placement as bcp
from verantyx import coarse_place as cp
from verantyx import coarse_types as ct

from test_coarse_place_build import (MINI, MINI_CFG, build, check_invariants,  # noqa: F401
                                     make_codex_db, q)
from test_coarse_place_review2 import cfg_for, ctx_sources, ex_for  # noqa: F401
from test_coarse_place_review3 import write_jawiki  # noqa: F401

SRC = "generated:gpt-6-luna:low"
BATCH = "b00000_0123456789ab"


def gen_entry(definition, hypernym, phrases=None, batch=BATCH):
    return {"definition": definition, "hypernym": hypernym,
            "phrases": phrases if phrases is not None else [hypernym], "model": "gpt-6-luna",
            "effort": "low", "batch_id": batch, "attempt": 1, "src": SRC}


def rows_of(res):
    return {r[0]: r for r in res["headwords"]}


def with_pos(ex, words, cls="N"):
    for src in ex["pos"]:
        for w in words:
            ex["pos"][src][(w, cls)] += 5
    return ex


# =========================================================================================
# decide_word: the rule itself
# =========================================================================================
def test_a_generated_arm_alone_places_a_word_as_an_estimate_generated():
    d = ct.decide_word([("gen_definition", SRC, "ARTIFACT", 1, None)], cfg_for())
    assert d["state"] == "DECIDED" and d["tops"] == ["ARTIFACT"] and d["by"] == ["gen_definition"]
    assert d["origin"] == "estimated" and d["estimate_basis"] == "generated"
    assert d["arms"]["gen_definition"]["met"] is True


def test_a_generated_arm_never_settles_a_split_or_a_decision():
    cfg = cfg_for()
    # a tie INSIDE the generated arm: nothing is placed
    d = ct.decide_word([("gen_definition", SRC, "ARTIFACT", 1, None),
                        ("gen_definition", SRC, "PERSON", 1, None)], cfg)
    assert d["state"] == "UNPLACED" and d["tops"] == []
    assert d["arms"]["gen_definition"]["why"] == "GENERATED_SPLIT" and d["origin"] is None
    # the other arms split (MULTIPLE): the generated arm does not break it
    split = [("definition", "jawiki", "ARTIFACT", 1, None), ("definition", "jawiki", "PERSON", 1, None)]
    d = ct.decide_word(split + [("gen_definition", SRC, "PERSON", 1, None)], cfg)
    assert d["state"] == "MULTIPLE" and d["tops"] == ["ARTIFACT", "PERSON"] and d["origin"] == "direct"
    assert d["arms"]["gen_definition"]["met"] is False
    assert d["arms"]["gen_definition"]["why"] == "GENERATED_NOT_DECIDING"
    assert d["by"] == ["definition"]
    # an existing DECIDED stays, whatever the generated type is
    d = ct.decide_word([("definition", "jawiki", "ARTIFACT", 1, None),
                        ("gen_definition", SRC, "PERSON", 1, None)], cfg)
    assert d["state"] == "DECIDED" and d["tops"] == ["ARTIFACT"] and d["by"] == ["definition"]
    assert d["origin"] == "direct" and d["estimate_basis"] is None
    # the answer without the generated arm is byte-for-byte the answer with a disagreeing one
    base = ct.decide_word([("definition", "jawiki", "ARTIFACT", 1, None)], cfg)
    assert {k: v for k, v in d.items() if k != "arms"} == {k: v for k, v in base.items() if k != "arms"}


def test_agreement_with_an_arm_that_reached_its_threshold_is_a_direct_placement():
    ev = [("role", "a", "SUBSTANCE_FOOD", 5, None), ("gen_definition", SRC, "SUBSTANCE_FOOD", 1, None)]
    cfg = cfg_for()
    base = ct.decide_word(ev[:1], cfg)
    assert base["state"] == "UNPLACED" and base["arms"]["role@a"]["why"] == "ROLE_SINGLE_SOURCE"
    d = ct.decide_word(ev, cfg)
    assert d["state"] == "DECIDED" and d["origin"] == "direct" and d["estimate_basis"] is None
    assert d["by"] == ["gen_definition", "role@a"]
    assert d["arms"]["role@a"]["met"] is True and d["arms"]["role@a"]["why"] is None
    # switched off: the same evidence is an estimate (generated)
    d2 = ct.decide_word(ev, cfg_for(gen_upgrade_on_agreement=False))
    assert d2["origin"] == "estimated" and d2["by"] == ["gen_definition"]
    # an arm that did NOT reach its threshold is no agreement
    d3 = ct.decide_word([("role", "a", "SUBSTANCE_FOOD", 1, None),
                         ("gen_definition", SRC, "SUBSTANCE_FOOD", 1, None)], cfg)
    assert d3["origin"] == "estimated"
    # an arm that names ANOTHER type is no agreement either
    d4 = ct.decide_word([("role", "a", "PERSON", 5, None),
                         ("gen_definition", SRC, "SUBSTANCE_FOOD", 1, None)], cfg)
    assert d4["origin"] == "estimated" and d4["tops"] == ["SUBSTANCE_FOOD"]


# =========================================================================================
# the resolution (synthetic counts)
# =========================================================================================
def test_resolve_places_gen_only_words_and_counts_what_it_did_not_place():
    ex = ex_for(ctx_sources({"a": {}}))
    with_pos(ex, ["ホゲラ", "ワレ", "ドウ", "フタ"])
    ex["pos"]["a"][("ウゴク", "V")] += 9
    ex["gen"] = {
        "ホゲラ": gen_entry("ホゲラは道具である。", "道具"),                      # only a generated sentence
        "ワレ": gen_entry("x", "x", ["道具", "人"]),                              # splits
        "ドウ": gen_entry("x", "x", ["ゼンゼン知らない語"]),                       # types to nothing
        "ウゴク": gen_entry("x", "x", ["道具"]),                                 # a verb: no noun type
        "マボロシ": gen_entry("x", "x", ["道具"]),                               # not in the material
    }
    res = bcp.resolve_all(ex, cfg_for())
    rows = rows_of(res)
    assert rows["ホゲラ"][2] == "DECIDED" and rows["ホゲラ"][3] == "estimated"
    assert rows["ホゲラ"][4] == "ARTIFACT" and rows["ホゲラ"][7] == "gen_definition"
    assert rows["ワレ"][2] == "UNPLACED" and rows["ドウ"][2] == "UNPLACED"
    assert "ウゴク" not in rows or rows["ウゴク"][2] == "UNPLACED"
    assert "マボロシ" not in rows
    gs = res["gen_stats"]
    assert gs["used"] == 2 and gs["tie"] == 1 and gs["no_type"] == 1
    assert gs["ns_not_noun"] == 1 and gs["not_in_material"] == 1
    assert gs["decided_estimated_generated"] == 1
    tbl = {r[0]: r for r in res["gen_table"]}
    assert set(tbl) == {"ホゲラ", "ワレ", "ドウ"}                                 # the origin is kept
    assert tbl["ホゲラ"][1:5] == ("gpt-6-luna", "low", BATCH, 1)
    assert json.loads(tbl["ホゲラ"][7]) == [["道具", "ARTIFACT"]]
    assert rows["ホゲラ"][3] == "estimated" and "estimated" not in {r[3] for r in res["headwords"]
                                                                      if r[0] != "ホゲラ"}


def test_resolve_agreement_makes_the_word_direct_and_a_decided_word_ignores_the_generated_type():
    occ = ctx_sources({"a": {("ホゲ", "を", "食べる"): 3}})
    ex = ex_for(occ)
    with_pos(ex, ["ホゲ"])
    ex["gen"] = {"ホゲ": gen_entry("x", "x", ["食品"])}
    res = bcp.resolve_all(ex, cfg_for())
    r = rows_of(res)["ホゲ"]
    assert r[2] == "DECIDED" and r[3] == "direct" and r[4] == "SUBSTANCE_FOOD"
    assert set(r[7].split("+")) == {"role@a", "gen_definition"}
    assert res["gen_stats"]["decided_direct_upgrade"] == 1
    res2 = bcp.resolve_all(ex, cfg_for(gen_upgrade_on_agreement=False))
    r2 = rows_of(res2)["ホゲ"]
    assert r2[3] == "estimated" and r2[7] == "gen_definition"
    # a word the Wikipedia definition decides keeps that decision against a different generated type
    ex3 = ex_for(ctx_sources({"a": {}}))
    ex3["defs"] = [("ホガ", None, ["道具"], [])]
    ex3["gen"] = {"ホガ": gen_entry("x", "x", ["人"])}
    res3 = bcp.resolve_all(with_pos(ex3, ["ホガ"]), cfg_for())
    r3 = rows_of(res3)["ホガ"]
    assert r3[4] == "ARTIFACT" and r3[3] == "direct" and r3[7] == "definition"
    assert res3["gen_stats"]["base_decided_generated_ignored"] == 1


def test_a_generated_placement_is_not_a_donor_and_reaches_no_context_table_or_unit_family():
    ex = ex_for(ctx_sources({"a": {}}))
    with_pos(ex, ["ホゲラ"])
    ex["gen"] = {"ホゲラ": gen_entry("x", "x", ["道具"])}
    # another head's definition names ホゲラ as its hypernym; ホゲラ has only a generated sentence
    ex["defs"] = [("ダミー", None, ["ホゲラ"], [])]
    # and ホゲラ is the right-hand unit of long compounds that are DECIDED words
    ex["defs"] += [("%sホゲラ" % x, None, ["道具"], []) for x in ("アア", "イイ", "ウウ", "エエ")]
    ex["occ"]["a"][("ホゲラ", "を", "食べる")] += 50
    res = bcp.resolve_all(ex, cfg_for(kin_store_min=1))
    rows = rows_of(res)
    assert rows["ホゲラ"][3] == "estimated"
    assert "ダミー" not in rows or rows["ダミー"][2] == "UNPLACED"          # nothing was handed down
    # the context table did not count ホゲラ's 50 uses for ARTIFACT
    ctx = {(c[1], c[2], c[3]): c[4] for c in res["ctx"]}
    assert ctx.get(("を", "食べる", "ARTIFACT"), 0) == 0
    # not a member of any unit family (ホゲラ's own pieces would list it as a sample word) ...
    assert not [u for u in res["unit_sample"] if "ホゲラ" in u[2].split("|")]
    # ... while the DECIDED compounds that END in it do make "ホゲラ" a unit (control)
    assert ("ホゲラ", "R") in {(u[0], u[1]) for u in res["unit_kin"]}


# =========================================================================================
# a built placement
# =========================================================================================
def write_defs(path: Path, rows):
    with open(path, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def drow(word, definition, hypernym, batch=BATCH, abstained=False):
    return {"word": word, "definition": definition, "hypernym": hypernym, "abstained": abstained,
            "provenance": {"origin": "generated", "model": "gpt-6-luna", "effort": "low",
                           "batch_id": batch, "attempt": 1, "out_sha256": "0" * 64}}


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("gen")
    jw = tmp / "jw.jsonl"
    write_jawiki(jw, [
        ("ハガネ丸", "ハガネ丸は、日本の道具である。"),
        ("ダミー1", "ホゲラが走った。"),
        ("ダミー2", "ホゲラ会社が走った。"),
        ("ダミー3", "ダミー3は、日本のホゲラである。"),
        ("ダミー4", "ダミー4は、日本のハガネ丸である。"),
        ("ダミー5", "ダミー5は、ガメラの一種である。"),
    ])
    defs = tmp / "definitions.jsonl"
    write_defs(defs, [
        drow("ホゲラ", "ホゲラは道具の一種である。", "道具"),
        drow("ガメラ", "ガメラは動物である。", "動物"),
        drow("マボロシ", "マボロシは人である。", "人"),                       # not in the material
        drow("ホゲラ会社", None, None, abstained=True),                        # the model said it did not know
        drow("シッパイ丸", "シッパイ丸は人である。", "人"),
    ])
    ledger = tmp / "ledger.jsonl"
    ledger.write_text(
        json.dumps({"ev": "start", "batch": BATCH, "attempt": 1}) + "\n"
        + json.dumps({"ev": "end", "batch": BATCH, "attempt": 1, "status": "ok"}) + "\n"
        + json.dumps({"ev": "start", "batch": "b00001_x", "attempt": 1}) + "\n"
        + json.dumps({"ev": "end", "batch": "b00001_x", "attempt": 1, "status": "failed"}) + "\n",
        encoding="utf-8")
    excl = tmp / "excl.jsonl"
    excl.write_text(json.dumps({"term": "シッパイ"}, ensure_ascii=False) + "\n", encoding="utf-8")
    out = tmp / "p1"
    extra = ["--generated", str(defs), "--generated-ledger", str(ledger),
             "--exclude-terms", str(excl)]
    assert build(out, jawiki=jw, extra=extra, cfg={"left_attested": False}) == 0
    return {"tmp": tmp, "out": out, "jw": jw, "defs": defs, "ledger": ledger, "extra": extra}


def test_a_word_placed_by_a_generated_sentence_alone_is_marked_and_keeps_its_origin(built):
    r = q("ホゲラ", built["out"])
    assert r["state"] == "DECIDED" and r["top"] == ["ARTIFACT"]
    assert r["origin"] == "estimated" and r["estimate_basis"] == "generated"
    assert r["constructed"] is True and r["decided_by"] == ["gen_definition"]
    assert r["neighbors"] and r["neighbors"][0]["via"] == "generated:" + BATCH
    assert r["neighbors"][0]["type"] == "ARTIFACT" and r["neighbors"][0]["word"] == "道具"
    ax = r["axes"]["gen_definition"]
    assert ax["met"] is True and ax["provenance"] == {"model": "gpt-6-luna", "effort": "low",
                                                       "batch_id": BATCH}
    assert ax["generated"] is False                      # the codex-corpus mark keeps its old meaning
    assert r["generated_definition"] is True
    check_invariants(r)
    con = sqlite3.connect("file:%s/placement.sqlite?mode=ro" % built["out"], uri=True)
    row = con.execute("SELECT word,model,effort,batch_id,attempt,definition,hypernym,phrases "
                      "FROM generated WHERE word='ホゲラ'").fetchone()
    assert row[1:5] == ("gpt-6-luna", "low", BATCH, 1) and row[5] == "ホゲラは道具の一種である。"
    # an ordinary placement is not marked
    r2 = q("ハガネ丸", built["out"])
    assert r2["origin"] == "direct" and r2["estimate_basis"] is None and r2["generated_definition"] is False


def test_the_invariants_hold_for_every_headword_and_every_probe(built):
    con = sqlite3.connect("file:%s/placement.sqlite?mode=ro" % built["out"], uri=True)
    words = [r[0] for r in con.execute("SELECT word FROM headwords ORDER BY word")]
    probes = words + ["ニセホゲラ", "ニセハガネ丸", "全然ない語", "10kg"]
    kinds = Counter()
    for w in probes:
        r = q(w, built["out"])
        check_invariants(r)
        o, c, b = r["origin"], r["constructed"], r["estimate_basis"]
        assert (o == "estimated") == c == (b in ("proximity", "generated")), w
        if o == "estimated":
            assert r["neighbors"], w
        if o == "direct":
            assert b is None, w
        kinds[(o, b)] += 1
    assert ("estimated", "generated") in kinds and ("estimated", "proximity") in kinds
    assert ("direct", None) in kinds


def test_what_a_generated_sentence_placed_is_not_passed_on(built):
    out = built["out"]
    # as a hypernym: ダミー3 says "日本のホゲラ", ホゲラ is only a generated placement
    r = q("ダミー3", out)
    assert r["top"] == [] and r["state"] in ("UNPLACED", "UNKNOWN")
    # control: a hypernym that is a direct placement does hand its type down
    assert q("ダミー4", out)["top"] == ["ARTIFACT"]
    # as the right-hand word of an unknown compound (the head stage of the estimate)
    r = q("ニセホゲラ", out)
    assert r["top"] == [] and r["origin"] is None
    r = q("ニセハガネ丸", out)
    assert r["top"] == ["ARTIFACT"] and r["origin"] == "estimated" and r["estimate_basis"] == "proximity"
    # not a member of a unit family
    con = sqlite3.connect("file:%s/placement.sqlite?mode=ro" % out, uri=True)
    assert con.execute("SELECT COUNT(*) FROM unit_kin WHERE unit='ホゲラ'").fetchone()[0] == 0
    for (smp,) in con.execute("SELECT sample FROM unit_sample"):
        assert "ホゲラ" not in smp.split("|")


def test_a_generated_sentence_does_not_decide_a_word_the_definition_already_decided(built):
    # ダミー5: its lead says "ガメラの一種" (ガメラ is generated-only, so no type from the lead),
    # and ガメラ itself is placed only by the generated sentence
    r = q("ガメラ", built["out"])
    assert r["origin"] == "estimated" and r["top"] == ["ANIMAL"]
    assert q("ダミー5", built["out"])["top"] == []


def test_the_manifest_counts_the_generated_rows_calls_and_hashes(built):
    m = json.loads((built["out"] / "manifest.json").read_text(encoding="utf-8"))
    g = m["generated"]
    assert g["path"] == str(built["defs"]) and g["sha256"] == bcp.sha256_file(str(built["defs"]))
    assert g["lines"] == 5 and g["used"] == 2
    assert g["dropped_by_reason"]["abstained"] == 1 and g["dropped_by_reason"]["excluded_term"] == 1
    assert g["dropped_by_reason"]["not_in_material"] == 1
    assert g["calls"] == 2 and g["batches_ok"] == 1 and g["batches_failed"] == 1
    assert g["model"] == "gpt-6-luna" and g["effort"] == "low"
    assert g["ledger_sha256"] == bcp.sha256_file(str(built["ledger"]))
    assert g["outcomes"]["decided_estimated_generated"] == 2
    mats = [x for x in m["materials"] if x.get("origin") == "generated"]
    assert mats and mats[0]["model"] == "gpt-6-luna" and mats[0]["effort"] == "low"
    assert m["outputs"]["tables"]["generated"] == 2
    assert m["outputs"]["placed_estimated_generated"] == 2
    assert m["no_weights_no_models"] is True
    con = sqlite3.connect("file:%s/placement.sqlite?mode=ro" % built["out"], uri=True)
    assert con.execute("SELECT COUNT(*) FROM generated WHERE word='シッパイ丸'").fetchone()[0] == 0


def test_the_generated_table_is_part_of_content_sha_and_verify_and_the_build_is_deterministic(built, tmp_path):
    out2 = tmp_path / "p2"
    assert build(out2, jawiki=built["jw"], extra=built["extra"], cfg={"left_attested": False}, jobs=3) == 0
    m1 = json.loads((built["out"] / "manifest.json").read_text(encoding="utf-8"))
    m2 = json.loads((out2 / "manifest.json").read_text(encoding="utf-8"))
    assert m1["content_sha256"] == m2["content_sha256"]
    assert bcp.main(["verify", "--placement", str(built["out"])]) == 0
    # the table is hashed: changing a generated row is detected
    bad = tmp_path / "bad"
    shutil.copytree(built["out"], bad)
    con = sqlite3.connect(str(bad / "placement.sqlite"))
    con.execute("UPDATE generated SET model='x' WHERE word='ホゲラ'")
    con.commit()
    con.close()
    assert bcp.main(["verify", "--placement", str(bad)]) == 4
    # and a build without the generated input has a different content hash
    out3 = tmp_path / "p3"
    assert build(out3, jawiki=built["jw"], cfg={"left_attested": False}) == 0
    m3 = json.loads((out3 / "manifest.json").read_text(encoding="utf-8"))
    assert m3["content_sha256"] != m1["content_sha256"] and m3["generated"] is None
    assert q("ホゲラ", out3)["top"] == [] and q("ホゲラ", out3)["estimate_basis"] is None


def test_a_placement_without_a_generated_table_still_opens(built, tmp_path):
    old = tmp_path / "old"
    shutil.copytree(built["out"], old)
    con = sqlite3.connect(str(old / "placement.sqlite"))
    con.execute("DROP TABLE generated")
    con.commit()
    con.close()
    m = json.loads((old / "manifest.json").read_text(encoding="utf-8"))
    del m["outputs"]["tables"]["generated"]
    (old / "manifest.json").write_text(json.dumps(m), encoding="utf-8")
    r = q("ハガネ丸", old)
    assert r["state"] == "DECIDED" and r["estimate_basis"] is None
    r = q("ホゲラ", old)
    assert r["origin"] == "estimated" and r["estimate_basis"] == "generated"   # evidence rows remain
    assert r["axes"]["gen_definition"]["provenance"]["model"] == "gpt-6-luna"


def test_read_generated_reads_phrases_like_a_lead_and_drops_with_counts(tmp_path):
    p = tmp_path / "d.jsonl"
    write_defs(p, [drow("アルファ", "アルファは、日本の道具である。", "道具"),
                   drow("ベータ", "ベータは筋肉に生じる痛みであり、その原因はさまざまである。", "痛み"),
                   drow("ガンマ", "ガンマは人である。", "人"),
                   drow("ガンマ", "ガンマは道具である。", "道具"),            # twice: not taken
                   drow("デルタ", None, None, abstained=True),
                   drow("イプシロン", "イプシロンはゼータの一種である。", "ゼータ")])
    rows, drops, n = bcp.read_generated(str(p), ["ゼータ"], fugashi.Tagger())
    assert n == 6 and set(rows) == {"アルファ", "ベータ"}
    assert rows["アルファ"]["phrases"] == ["道具"]                     # the sentence and the field: one phrase
    assert rows["ベータ"]["phrases"] == ["痛み"]
    assert drops["dup_word"] == 1 and drops["abstained"] == 1 and drops["excluded_term"] == 1
    assert rows["アルファ"]["src"] == SRC


# =========================================================================================
# an upgrade to "direct" is still a generated sentence's work: not passed on (review r1 M1)
# =========================================================================================
@pytest.fixture(scope="module")
def upgraded(tmp_path_factory):
    """ポロロ: ONE codex source says it is eaten (a role arm that cannot decide alone,
    ROLE_SINGLE_SOURCE) and a generated sentence says food -> upgraded to "direct".
    ハガネ丸 and the compounds of 道具: plain direct placements (the control: no generated
    sentence)."""
    base = tmp_path_factory.mktemp("upg")
    conv = []
    for w in ["料理", "食品", "飲料", "野菜", "果物", "肉", "食材", "菓子"]:
        conv += ["%sを食べた。" % w] * 4
    for w in ["人", "人物", "選手", "俳優", "歌手", "作家", "医師", "教師"]:
        conv += ["%sが笑った。" % w] * 4                  # a second type: eating is typical of FOOD here
    conv += ["ポロロを食べた。"] * 6
    cdir = base / "cx"
    make_codex_db(cdir, "conversation", conv)
    jw = base / "jw.jsonl"
    write_jawiki(jw, [
        ("ハガネ丸", "ハガネ丸は、日本の道具である。"),
        ("ダミー6", "ダミー6は、日本のポロロである。"),
        ("アア道具", "アア道具は、日本の道具である。"),
        ("イイ道具", "イイ道具は、日本の道具である。"),
        ("ウウ道具", "ウウ道具は、日本の道具である。"),
        ("エエ道具", "エエ道具は、日本の道具である。"),
    ])
    defs = base / "definitions.jsonl"
    write_defs(defs, [drow("ポロロ", "ポロロは食品である。", "食品")])
    out = base / "p"
    assert build(out, jawiki=jw, codex_dir=cdir, families="conversation",
                 extra=["--generated", str(defs)],
                 cfg={"left_attested": False, "kin_store_min": 1, "kin_min_count": 1}) == 0
    return out


def test_the_upgraded_word_really_is_an_upgrade_the_fixture_is_not_vacuous(upgraded):
    r = q("ポロロ", upgraded)
    assert r["state"] == "DECIDED" and r["top"] == ["SUBSTANCE_FOOD"]
    assert r["origin"] == "direct" and r["estimate_basis"] is None
    assert set(r["decided_by"]) == {"gen_definition", "role@codex:conversation"}
    # the control is a plain direct word
    c = q("ハガネ丸", upgraded)
    assert c["origin"] == "direct" and c["decided_by"] == ["definition"]


def test_an_upgraded_word_does_not_lend_its_type_as_the_head_of_an_unknown_compound(upgraded):
    r = q("ニセポロロ", upgraded)
    assert r["top"] == [] and r["origin"] is None and r["state"] == "UNKNOWN"
    # the control: the same form with a plain direct word as its right-hand side does
    c = q("ニセハガネ丸", upgraded)
    assert c["top"] == ["ARTIFACT"] and c["origin"] == "estimated" and c["estimate_basis"] == "proximity"
    assert c["neighbors"][0]["via"] == "head:ハガネ丸@R"


def test_an_upgraded_word_is_not_a_member_of_a_unit_family(upgraded):
    con = sqlite3.connect("file:%s/placement.sqlite?mode=ro" % upgraded, uri=True)
    samples = [(u, s, smp.split("|")) for u, s, smp in con.execute("SELECT unit, pos, sample FROM unit_sample")]
    assert not [x for x in samples if "ポロロ" in x[2]]
    # the control: the plain direct words are what the families are made of
    assert [x for x in samples if "ハガネ丸" in x[2] or "アア道具" in x[2]]
    # and no family is counted from the upgraded word either
    row = con.execute("SELECT by, origin FROM headwords WHERE word='ポロロ'").fetchone()
    assert row == ("gen_definition+role@codex:conversation", "direct")
