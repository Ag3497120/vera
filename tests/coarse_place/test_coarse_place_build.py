"""Build + query on small synthetic material (W3-a, L4 / L5 unit part)."""
import json
import os
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

from tools import build_coarse_placement as bcp
from verantyx import coarse_place as cp
from verantyx import coarse_types as ct

TREE = Path(__file__).resolve().parents[2]
FIX = Path(__file__).parent / "fixtures"
MINI = FIX / "jawiki_mini.jsonl"
PYTHON = sys.executable

MINI_CFG = {"min_seen": 1, "kin_min_count": 2, "kin_store_min": 2, "ctx_min_total": 2,
            "ctx_store_min": 2, "role_min": 1, "est_ctx_min_total": 2,
            "counter_min": 1, "counter_min_sources": 1, "qual_min": 1, "ctx_min_lift_pct": 150,
            "est_ctx_min_lift_pct": 150, "ctx_min_share_pct": 60,
            "est_ctx_min_share_pct": 60, "role_min_share_pct": 60,
            "sahen_min": 2, "frame_min_total": 99999,
            # the small fixture has role contexts of its own: let the definition-like arms
            # decide first so the tests below isolate one arm at a time
            "definition_outranks_role": True}

CODEX_COLS = ("id, text, source, scene, grp, sha, family, source_file, line, kind, "
              "fields, origin, generator, body_sha")


def make_codex_db(dirpath: Path, family: str, texts):
    dirpath.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(dirpath / (family + ".db")))
    con.execute("CREATE TABLE rows(id INTEGER PRIMARY KEY, text TEXT, source TEXT, scene TEXT,"
                " grp TEXT, sha TEXT, family TEXT, source_file TEXT, line INTEGER, kind TEXT,"
                " fields TEXT, origin TEXT, generator TEXT, body_sha TEXT)")
    for i, t in enumerate(texts, 1):
        con.execute("INSERT INTO rows VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (i, t, "x", "", "", "s%d" % i, family, "f", i, "k", "{}", "generated", "g",
                     "b-%s-%d" % (family, i)))
    con.commit()
    con.close()


def build(out: Path, jawiki=MINI, cfg=None, extra=(), codex_dir=None, families=None, jobs=2):
    cfgp = out.parent / (out.name + ".cfg.json")
    cfgp.write_text(json.dumps({**MINI_CFG, **(cfg or {})}), encoding="utf-8")
    argv = ["build", "--jawiki", str(jawiki), "--out", str(out), "--jobs", str(jobs),
            "--config", str(cfgp), *extra]
    if codex_dir:
        argv += ["--codex-dir", str(codex_dir)]
    if families:
        argv += ["--families", families]
    return bcp.main(argv)


@pytest.fixture(scope="module")
def mini(tmp_path_factory):
    out = tmp_path_factory.mktemp("mini") / "p1"
    assert build(out) == 0
    return out


def q(term, pl, **kw):
    return cp.query(term, placement=str(pl), **kw)


def check_invariants(r):
    top, st, og = r["top"], r["state"], r["origin"]
    assert (st == "DECIDED") == (len(top) == 1)
    assert (st == "MULTIPLE") == (len(top) >= 2)
    assert (st in ("UNPLACED", "UNKNOWN", "NO_PLACEMENT")) == (top == [])
    assert (og == "estimated") == (r["constructed"] is True)
    assert (og == "estimated") == (r["estimate_basis"] in ("proximity", "generated"))
    if og != "estimated":
        assert r["estimate_basis"] is None
    if og == "estimated":
        assert r["neighbors"], "an estimate must say what it was built on"
    if st == "NO_PLACEMENT":
        assert r["placement"]["reason"] in ("UNSET", "MISSING", "UNREADABLE", "MANIFEST_MISMATCH")
    for t in top:
        assert t in ct.ALL_TYPES
    assert set(r) >= {"term", "namespace", "state", "origin", "constructed", "top", "candidates",
                      "axes", "neighbors", "seen_in_material", "context", "placement"}


# --- determinism / verify -----------------------------------------------------------------
def test_two_builds_have_the_same_content_sha_and_verify(tmp_path, mini):
    out2 = tmp_path / "p2"
    assert build(out2, jobs=3) == 0
    m1 = json.loads((mini / "manifest.json").read_text(encoding="utf-8"))
    m2 = json.loads((out2 / "manifest.json").read_text(encoding="utf-8"))
    assert m1["content_sha256"] == m2["content_sha256"]
    assert m1["outputs"] == m2["outputs"]
    assert bcp.main(["verify", "--placement", str(mini)]) == 0
    assert bcp.main(["verify", "--placement", str(out2)]) == 0


def test_verify_detects_a_changed_row(tmp_path, mini):
    cp_dir = tmp_path / "tampered"
    shutil.copytree(mini, cp_dir)
    con = sqlite3.connect(str(cp_dir / "placement.sqlite"))
    con.execute("UPDATE headwords SET top='WORK' WHERE word='土手'")
    con.commit()
    con.close()
    assert bcp.main(["verify", "--placement", str(cp_dir)]) == 4


def test_manifest_counts_match_the_database(mini):
    m = json.loads((mini / "manifest.json").read_text(encoding="utf-8"))
    con = sqlite3.connect(str(mini / "placement.sqlite"))
    for t, n in m["outputs"]["tables"].items():
        assert con.execute("SELECT COUNT(*) FROM %s" % t).fetchone()[0] == n
    assert m["outputs"]["placed_direct"] == con.execute(
        "SELECT COUNT(*) FROM headwords WHERE origin='direct'").fetchone()[0]
    assert m["no_weights_no_models"] is True
    names = [x["name"] for x in m["materials"]]
    assert any("unidic" in n for n in names) and any("seed" in n for n in names)


def test_same_query_same_json(mini):
    a = q("石土手", mini)
    b = q("石土手", mini)
    assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)


# --- direct placement: arms overlaid, never added ------------------------------------------
def test_dote_style_word_is_not_a_person(mini):
    # every word ending in 手 here is a person; the definition says the word is a place
    people = [q(w, mini) for w in ("歌い手", "書き手", "売り手", "聞き手", "語り手")]
    assert all(r["top"] == ["PERSON"] for r in people)
    r = q("土手", mini)
    assert r["top"] == ["PLACE"] and r["origin"] == "direct" and not r["constructed"]
    assert r["axes"]["definition"]["counts"] == {"PLACE": 1}
    r = q("石土手", mini)
    assert r["top"] == ["PLACE"]


def test_arms_that_split_give_multiple_not_a_winner(mini):
    # definition says PERSON (歌手), alias says PLANT (柚子): two arms disagree
    r = q("ゆず", mini)
    assert r["state"] == "MULTIPLE" and r["top"] == ["PERSON", "PLANT"]
    assert set(r["axes"]) >= {"definition", "alias"}
    check_invariants(r)


def test_a_tie_inside_one_arm_stays_a_tie(mini):
    # two plain articles titled サクラ: one says PLANT, one says PERSON
    r = q("サクラ", mini)
    assert r["state"] == "MULTIPLE" and r["top"] == ["PERSON", "PLANT"]
    assert r["axes"]["definition"]["top"] == ["PERSON", "PLANT"]


def test_title_qualifier_polysemy_is_kept(mini):
    r = q("ライオン", mini)
    assert r["state"] == "MULTIPLE" and r["top"] == ["ANIMAL", "GROUP_ORG"]
    assert "title_qualifier" in r["axes"]


def test_alias_is_its_own_arm(mini):
    r = q("餅鏡", mini)
    assert r["top"] == ["SUBSTANCE_FOOD"] and list(r["axes"]) == ["alias"]


def test_notation_is_decided_from_the_spelling(mini):
    r = q("2024年", mini)
    assert r["top"] == ["TIME"] and list(r["axes"]) == ["notation"] and r["origin"] == "direct"
    assert q("ABC-123", mini)["top"] == ["IDENTIFIER"]
    assert q("1,000", mini)["top"] == ["QUANTITY"]


def test_seed_is_a_direct_hand_anchor(mini):
    r = q("言語", mini)
    assert r["top"] == ["INFO_LANGUAGE"] and "seed" in r["axes"]


def test_arithmetic_of_arms_is_never_a_sum():
    # a sum of per-source role counts would let two weak sources pass: it must not
    comb = bcp.combine_arms({"role@a": ["PERSON"], "role@b": ["PLACE"]})
    assert comb[0] == "MULTIPLE" and comb[1] == ["PERSON", "PLACE"]
    assert bcp.combine_arms({"role@a": ["PERSON"], "role@b": ["PERSON"]})[0] == "DECIDED"
    assert bcp.combine_arms({"x": []}) is None
    # a tie inside one arm is kept (no dictionary-order winner)
    assert bcp.arm_top({"A": 3, "B": 3}, 1) == ["A", "B"]
    assert bcp.arm_top({"A": 3, "B": 1}, 1) == ["A"]
    assert bcp.arm_top({"A": 3, "B": 3}, 1, 70) == []   # a 50/50 split is no majority
    assert bcp.arm_top({"A": 2}, 3) == []


# --- estimation: nearness, always marked as a construction ---------------------------------
def test_estimate_from_a_placed_right_hand_word(mini):
    r = q("谷土手", mini)
    assert r["state"] == "DECIDED" and r["origin"] == "estimated" and r["constructed"] is True
    assert r["top"] == ["PLACE"]
    assert any(n["via"].startswith("head:土手") for n in r["neighbors"])
    assert "morphology:head" in r["axes"]
    check_invariants(r)


def test_bare_one_character_suffix_never_decides(mini):
    # the only right-hand unit is the single character 手: abstain
    r = q("押し手", mini)
    assert r["top"] == [] and r["state"] in ("UNKNOWN", "UNPLACED")
    assert r["origin"] is None and r["constructed"] is False
    check_invariants(r)


def test_estimate_from_kin_words_with_the_same_right_unit(mini):
    r = q("犬会社", mini)
    assert r["origin"] == "estimated" and r["top"] == ["GROUP_ORG"]
    assert any(n["via"].startswith("kin:") for n in r["neighbors"])
    assert r["constructed"] is True


def test_no_neighbours_means_unknown_not_a_guess(mini):
    r = q("ポルメリス", mini, context_role="が", context_predicate="ある")
    assert r["state"] == "UNKNOWN" and r["top"] == [] and r["seen_in_material"] is False
    assert r["origin"] is None
    check_invariants(r)


def test_invariants_on_every_headword_and_many_probes(mini):
    con = sqlite3.connect(str(mini / "placement.sqlite"))
    words = [w for (w,) in con.execute("SELECT word FROM headwords")]
    probes = words + ["谷土手", "犬会社", "ポルメリス", "押し手", "2020年", "x@y.jp", "石石石石石石石石石石石石石石"]
    for w in probes:
        for role, pred in ((None, None), ("を", "食べる"), ("が", None)):
            check_invariants(q(w, mini, context_role=role, context_predicate=pred))


def test_unknown_context_role_is_a_value_error(mini):
    with pytest.raises(ValueError):
        q("土手", mini, context_role="ほげ")
    with pytest.raises(ValueError):
        q("", mini)


# --- no placement / empty placement ----------------------------------------------------------
def test_no_placement_is_a_type(tmp_path, monkeypatch, mini):
    monkeypatch.delenv("VERA_COARSE_PLACEMENT", raising=False)
    r = cp.query("土手")
    assert r["state"] == "NO_PLACEMENT" and r["placement"]["reason"] == "UNSET" and r["top"] == []
    check_invariants(r)
    r = cp.query("土手", placement=str(tmp_path / "nowhere"))
    assert r["placement"]["reason"] == "MISSING" and r["state"] == "NO_PLACEMENT"
    bad = tmp_path / "bad"
    bad.mkdir()
    (bad / "manifest.json").write_text(json.dumps({"content_sha256": "x", "outputs": {"tables": {}}}))
    (bad / "placement.sqlite").write_bytes(b"this is not a database")
    assert cp.query("土手", placement=str(bad))["placement"]["reason"] == "UNREADABLE"
    mm = tmp_path / "mm"
    shutil.copytree(mini, mm)
    m = json.loads((mm / "manifest.json").read_text(encoding="utf-8"))
    m["outputs"]["tables"]["headwords"] += 1
    (mm / "manifest.json").write_text(json.dumps(m), encoding="utf-8")
    assert cp.query("土手", placement=str(mm))["placement"]["reason"] == "MANIFEST_MISMATCH"
    monkeypatch.setenv("VERA_COARSE_PLACEMENT", str(mini))          # the environment variable
    r = cp.query("土手")
    assert r["state"] == "DECIDED"


def test_a_placement_with_zero_words_is_unknown_not_no_placement(tmp_path):
    d = tmp_path / "empty"
    d.mkdir()
    con = sqlite3.connect(str(d / "placement.sqlite"))
    con.executescript(bcp.SCHEMA)
    con.execute("INSERT INTO meta VALUES ('config', ?)", (json.dumps(MINI_CFG),))
    con.commit()
    counts = bcp.table_counts(con)
    con.close()
    (d / "manifest.json").write_text(json.dumps(
        {"content_sha256": "0" * 64, "outputs": {"tables": counts}}), encoding="utf-8")
    r = cp.query("土手", placement=str(d))
    assert r["state"] == "UNKNOWN" and r["state"] != "NO_PLACEMENT" and r["top"] == []
    assert r["placement"]["reason"] is None
    assert cp.query("2024年", placement=str(d))["state"] == "DECIDED"   # spelling needs no table


# --- the command line ----------------------------------------------------------------------------
def run_cli(*args, env_extra=None):
    env = {k: v for k, v in os.environ.items() if k != "VERA_COARSE_PLACEMENT"}
    env["PYTHONPATH"] = str(TREE)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    if env_extra:
        env.update(env_extra)
    p = subprocess.run([PYTHON, "-m", "verantyx.coarse_place", *args], capture_output=True,
                       text=True, env=env, cwd=str(TREE))
    return p.returncode, (json.loads(p.stdout) if p.stdout.strip() else None)


def test_cli_exit_codes_and_json(mini):
    rc, out = run_cli("--term", "土手", "--placement", str(mini))
    assert rc == 0 and out["top"] == ["PLACE"] and out["state"] == "DECIDED"
    rc, out = run_cli("--term", "土手")
    assert rc == 2 and out["state"] == "NO_PLACEMENT" and out["placement"]["reason"] == "UNSET"
    rc, out = run_cli("--term", "土手", "--placement", "/nonexistent/dir")
    assert rc == 2 and out["placement"]["reason"] == "MISSING"
    rc, out = run_cli("--term", "土手", "--context-role", "ほげ", "--placement", str(mini))
    assert rc == 64 and out["state"] == "BAD_ARGUMENT"
    rc, out = run_cli("--placement", str(mini))                       # --term missing
    assert rc == 64 and out["state"] == "BAD_ARGUMENT"
    rc, out = run_cli("--term", "ポルメリス", "--context-role", "が", "--context-predicate", "ある",
                      "--placement", str(mini))
    assert rc == 0 and out["state"] == "UNKNOWN"
    rc, out = run_cli("--term", "土手", env_extra={"VERA_COARSE_PLACEMENT": str(mini)})
    assert rc == 0 and out["top"] == ["PLACE"]


def test_query_module_does_not_load_the_tagger_at_import():
    code = ("import sys; import verantyx.coarse_place, verantyx.coarse_types; "
            "print('fugashi' in sys.modules, 'MeCab' in sys.modules)")
    p = subprocess.run([PYTHON, "-c", code], capture_output=True, text=True,
                       env={"PYTHONPATH": str(TREE), "PATH": os.environ.get("PATH", ""),
                           "PYTHONDONTWRITEBYTECODE": "1"})
    assert p.stdout.split() == ["False", "False"], p.stderr


# --- exclusions, holdout, frozen --------------------------------------------------------------------
def test_excluded_terms_are_not_headwords_and_the_drops_are_counted(tmp_path):
    rows = [json.loads(l) for l in MINI.read_text(encoding="utf-8").splitlines()]
    rows.append({"title": "雑記", "text": "雑記は、ポルメリスという名の場所である。", "sha": "zz1", "split": "train"})
    rows.append({"title": "ポルメリス", "text": "ポルメリスは、ある国の場所。", "sha": "zz2", "split": "train"})
    rows.append({"title": "ポルメリス棒", "redirect": "土手", "split": "train"})
    src = tmp_path / "jw.jsonl"
    src.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
    ex = tmp_path / "excl.jsonl"
    ex.write_text(json.dumps({"term": "ポルメリス"}, ensure_ascii=False) + "\n", encoding="utf-8")
    out = tmp_path / "pe"
    assert build(out, jawiki=src, extra=["--exclude-terms", str(ex)]) == 0
    m = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    assert m["excluded_terms_total"] == 1
    assert m["skipped_rows_by_reason"]["jawiki"]["excluded_term"] == 3
    assert m["excluded_term_hits"]["jawiki:ポルメリス"] == 3
    con = sqlite3.connect(str(out / "placement.sqlite"))
    assert con.execute("SELECT COUNT(*) FROM headwords WHERE word LIKE '%ポルメリス%'").fetchone()[0] == 0
    assert con.execute("SELECT COUNT(*) FROM headwords WHERE word='雑記'").fetchone()[0] == 0
    r = q("ポルメリス", out, context_role="が", context_predicate="ある")
    assert r["origin"] != "direct" and r["top"] == []


def test_holdout_rows_are_not_material(tmp_path):
    hold = tmp_path / "hold.jsonl"
    # line 0 of the fixture is 土手; its sha is fx000
    hold.write_text(json.dumps({"source": "jawiki", "line": 0, "sha": "fx000", "title": "土手",
                                "sentence": "x"}, ensure_ascii=False) + "\n", encoding="utf-8")
    out = tmp_path / "ph"
    assert build(out, extra=["--holdout", str(hold)]) == 0
    m = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    assert m["skipped_rows_by_reason"]["jawiki"]["holdout"] == 1
    assert m["holdout"][0]["jawiki_lines"] == 1
    r = q("土手", out)
    assert r["axes"].get("definition") is None          # its own article is gone
    # codex: a held-out row (family, rowid) and a row with the same body sha are dropped
    cdir = tmp_path / "cx"
    make_codex_db(cdir, "conversation", ["料理を食べた。"] * 3)
    hold2 = tmp_path / "hold2.jsonl"
    hold2.write_text(json.dumps({"source": "codex", "family": "conversation", "rowid": 1,
                                 "body_sha": "b-conversation-2", "sentence": "x"}) + "\n", encoding="utf-8")
    out2 = tmp_path / "ph2"
    assert build(out2, codex_dir=cdir, families="conversation", extra=["--holdout", str(hold2)]) == 0
    m2 = json.loads((out2 / "manifest.json").read_text(encoding="utf-8"))
    assert m2["skipped_rows_by_reason"]["codex:conversation"]["holdout"] == 2


def test_frozen_mismatch_stops_the_build(tmp_path):
    root = tmp_path / "root"
    (root / "artifacts/w3-a").mkdir(parents=True)
    (root / "tests/coarse_place/data").mkdir(parents=True)
    f = root / "tests/coarse_place/data/typed_vocab.jsonl"
    f.write_text("{}\n", encoding="utf-8")
    fz = root / "artifacts/w3-a/FROZEN.json"
    fz.write_text(json.dumps({"files": {"tests/coarse_place/data/typed_vocab.jsonl":
                                        {"sha256": "0" * 64}}}), encoding="utf-8")
    assert build(tmp_path / "pf", extra=["--frozen", str(fz)]) == 3
    assert not (tmp_path / "pf").exists()


def test_out_unset_is_a_typed_stop(capsys):
    assert bcp.main(["build", "--jawiki", str(MINI)]) == 2
    assert "UNKNOWN_OUT_UNSET" in capsys.readouterr().out


# --- roles from codex-like material: sources never pool --------------------------------------------
def food_words():
    return ["料理", "食品", "飲料", "野菜", "果物", "肉", "食材", "菓子"]


def person_words():
    return ["人", "人物", "選手", "俳優", "歌手", "作家", "医師", "教師"]


def thing_words():
    return ["道具", "機械", "装置", "器具", "楽器", "家具", "工具", "容器"]


@pytest.fixture(scope="module")
def roles(tmp_path_factory):
    base = tmp_path_factory.mktemp("roles")
    conv, narr = [], []
    for w in food_words():
        conv += ["%sを食べた。" % w] * 4
    for w in person_words():
        conv += ["%sが笑った。" % w] * 4
    for w in thing_words():
        conv += ["%sを買った。" % w] * 4
    for w in food_words():
        narr += ["%sを食べた。" % w] * 4
    for w in person_words():
        narr += ["%sが笑った。" % w] * 4
    for w in thing_words():
        narr += ["%sを買った。" % w] * 4
    # ホゲパン: eaten in conversation, laughing in narrative; ホゲボン: eaten in both
    conv += ["ホゲパンを食べた。"] * 6 + ["ホゲボンを食べた。"] * 6
    narr += ["ホゲパンが笑った。"] * 6 + ["ホゲボンを食べた。"] * 6
    cdir = base / "cx"
    make_codex_db(cdir, "conversation", conv)
    make_codex_db(cdir, "narrative", narr)
    out = base / "p"
    assert build(out, codex_dir=cdir, families="conversation,narrative") == 0
    return out


def test_role_arm_from_one_generated_source_decides(roles):
    r = q("ホゲボン", roles)
    assert r["state"] == "DECIDED" and r["top"] == ["SUBSTANCE_FOOD"] and r["origin"] == "direct"
    assert r["generated"] is True                         # codex material is generated
    assert set(r["axes"]) == {"role@codex:conversation", "role@codex:narrative"}
    assert all(a["generated"] for a in r["axes"].values())


def test_sources_that_disagree_give_multiple_and_never_pool_counts(roles):
    r = q("ホゲパン", roles)
    assert r["state"] == "MULTIPLE" and r["top"] == ["PERSON", "SUBSTANCE_FOOD"]
    assert r["axes"]["role@codex:conversation"]["counts"] == {"SUBSTANCE_FOOD": 6}
    assert r["axes"]["role@codex:narrative"]["counts"] == {"PERSON": 6}
    check_invariants(r)


def test_estimate_from_the_role_slot_only(roles):
    r = q("ホゲラ", roles, context_role="を", context_predicate="食べる")
    assert r["state"] == "DECIDED" and r["origin"] == "estimated" and r["constructed"] is True
    assert r["top"] == ["SUBSTANCE_FOOD"]
    assert "context" in r["axes"] and r["neighbors"][0]["via"].startswith("context:")
    # no slot given -> nothing to be near to
    r2 = q("ホゲラ", roles)
    assert r2["top"] == [] and r2["state"] == "UNKNOWN"
    # an unbiased slot (a particle with no predicate in these data) says nothing
    r3 = q("ホゲラ", roles, context_role="は", context_predicate="食べる")
    assert r3["top"] == []
    check_invariants(r)


def test_contexts_are_per_source(roles):
    con = sqlite3.connect(str(roles / "placement.sqlite"))
    srcs = {s for (s,) in con.execute("SELECT DISTINCT src FROM ctx")}
    assert srcs == {"jawiki", "codex:conversation", "codex:narrative"}
    ev = {(a, s) for (a, s) in con.execute("SELECT DISTINCT arm, src FROM evidence WHERE arm='role'")}
    assert ev <= {("role", "jawiki"), ("role", "codex:conversation"), ("role", "codex:narrative")}
    # no evidence row ever carries a pooled source
    assert not [r for r in con.execute("SELECT src FROM evidence WHERE src LIKE '%+%' OR src='all'")]
