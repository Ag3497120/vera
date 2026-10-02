"""W1-c: corpus index builder and typed Corpus states, on synthetic data only.

Every test here builds a tiny corpus root shaped like the real codex corpus
(8 families, heldout/ and overlap_dropped/ siblings, ledgers) under tmp_path.
Nothing here touches the real corpus or the real index.
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from tools import build_p4_corpus_index as bi
from verantyx.ability_corpus import FAMILIES, Corpus, CorpusUnknown, Witness

SRC = "llm_authored:codex:pro-b00001"
FAMS = ("pro", "code", "conversation", "general_qa", "code_qa",
        "figurative_commonsense", "narrative", "paraphrase_entail")


def J(**kw) -> str:
    return json.dumps(kw, ensure_ascii=False)


def _write(root: Path, rel: str, lines: list[str], *, final_newline: bool = True) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    text = "\n".join(lines) + ("\n" if final_newline else "")
    path.write_bytes(text.encode("utf-8"))


def make_corpus(root: Path) -> dict:
    """Write the synthetic corpus; return the exact per-file expectations."""
    exp: dict[str, dict] = {}

    # --- pro: out/sentences.jsonl (the only file without a trailing newline)
    _write(root, "out/sentences.jsonl", [
        J(text="MKpro_a 朝の台所。", source=SRC, scene="朝", sha="p1"),
        J(text="MKpro_b 夜の道。", source=SRC, scene="夜", sha="p2"),
        "",
        "{not json",
        "[1, 2]",
        J(source=SRC, sha="x"),
        J(text=5, source=SRC),
        J(text="MKpro_c 別の出所。", source="human:other", sha="p3"),
        J(text="MKpro_split", split="heldout", source=SRC),
        J(text="MKpro_fam", family="code", source=SRC),
        J(text="MKpro_partial", source=SRC, sha="p9"),
    ], final_newline=False)
    exp["out/sentences.jsonl"] = dict(
        lines=11, indexed=3, skipped={
            "blank_line": 1, "bad_json": 1, "not_object": 1,
            "missing_required:pro.text": 1, "bad_field_type:pro.text": 1,
            "split_not_train:heldout": 1, "family_mismatch:code": 1,
            "partial_final_line": 1},
        split_absent=3, source_tag_unexpected=1)

    # --- code: two shards of one family
    _write(root, "code/items.jsonl", [
        J(text="MKcode_a 変数は値を持つ。", family="code", topic="変数", source="llm_authored:codex:pro-code-b00001", sha="c1"),
        J(text="MKcode_b 関数を呼ぶ。", family="code", split="train", topic="関数", source="llm_authored:codex:pro-code-b00001", sha="c2"),
    ])
    exp["code/items.jsonl"] = dict(lines=2, indexed=2, skipped={}, split_absent=1, source_tag_unexpected=0)
    _write(root, "even/code/items.jsonl", [
        J(text="MKcode_even 配列を回す。", family="code", split="train", topic="配列", source="llm_authored:codex:pro-code-b00002", sha="c3"),
        J(text="MKcode_even_bad", family="code", split="overlap", topic="配列", source="llm_authored:codex:pro-code-b00002"),
    ])
    exp["even/code/items.jsonl"] = dict(lines=2, indexed=1, skipped={"split_not_train:overlap": 1},
                                        split_absent=0, source_tag_unexpected=0)

    # --- conversation: two shards
    _write(root, "conversation/utterances.jsonl", [
        J(text="MKconv_a おはよう。", scene="職場", dialogue_id="d1", turn=0, source="llm_authored:codex:pro-conv-b00001", sha="v1"),
        J(text="MKconv_b 打ち合わせは何時？", scene="職場", dialogue_id="d1", turn=1, split="train", source="llm_authored:codex:pro-conv-b00001", sha="v2"),
    ])
    exp["conversation/utterances.jsonl"] = dict(lines=2, indexed=2, skipped={}, split_absent=1, source_tag_unexpected=0)
    _write(root, "even/conversation/utterances.jsonl", [
        J(text="MKconv_even 改札を出て左です。", scene="駅", dialogue_id="d9", turn=0, split="train", source="llm_authored:codex:pro-conv-b00009", sha="v3"),
    ])
    exp["even/conversation/utterances.jsonl"] = dict(lines=1, indexed=1, skipped={}, split_absent=0, source_tag_unexpected=0)

    base = dict(family="general_qa", split="train", source="llm_authored:codex:pro-general_qa-b000011")
    _write(root, "general_qa/train/records.jsonl", [
        J(kind="fact", q_variants=["MKgqa_q あんこは何から？"], answer="MKgqa_a 小豆です。", why="MKgqa_w 煮るから。", domain="食", sha="g1", **base),
        J(kind="greeting", q_variants=["MKgqa_hi こんにちは"], answer="こんにちは。", domain="挨拶", sha="g2", **base),
        J(kind="mystery", q_variants=["MKgqa_my"], answer="x", sha="g3", **base),
        J(kind="howto", q_variants="MKgqa_str", answer="x", sha="g4", **base),
        J(kind="howto", q_variants=["MKgqa_noanswer"], sha="g5", **base),
        J(q_variants=["MKgqa_nokind"], answer="x", sha="g6", **base),
        J(kind="fact", q_variants=[], answer="x", sha="g7", **base),
    ])
    exp["general_qa/train/records.jsonl"] = dict(
        lines=7, indexed=2, skipped={
            "unmapped_kind:mystery": 1, "bad_field_type:howto.q_variants": 1,
            "missing_required:howto.answer": 1, "unmapped_kind:(none)": 1,
            "missing_required:fact.q_variants": 1},
        split_absent=0, source_tag_unexpected=0, optional_absent={"greeting.why": 1})

    base = dict(family="code_qa", split="train", source="llm_authored:codex:pro-code_qa-b000000")
    _write(root, "code_qa/train/records.jsonl", [
        J(question="MKcqa_q 空白を整えますか？", answer_text="MKcqa_a 分割して結合。", code="MKcqa_code join", usage="MKcqa_use f()", context="文字列", task_kind="write_function", sha="q1", **base),
        J(question="MKcqa_q2 もう一つ", answer_text="答え。", context="文字列", task_kind="explain", sha="q2", **base),
        J(question="MKcqa_q3 答え無し", sha="q3", **base),
    ])
    exp["code_qa/train/records.jsonl"] = dict(
        lines=3, indexed=2, skipped={"missing_required:code_qa.answer_text": 1},
        split_absent=0, source_tag_unexpected=0,
        optional_absent={"code_qa.code": 1, "code_qa.usage": 1})

    base = dict(family="figurative_commonsense", split="train", theme="台所",
                source="llm_authored:codex:pro-figurative_commonsense-b000002")
    _write(root, "figurative_commonsense/train/records.jsonl", [
        J(kind="pun", pun="MKfig_pun あじがいい", mechanism="MKfig_mech 同じ読み", sha="f1", **base),
        J(kind="pun", pun="MKfig_pun2 ぬけぬけ", sha="f2", **base),
        J(kind="haiku", haiku="MKfig_haiku 古池や", note="MKfig_note 季語", sha="f3", **base),
        J(kind="simile_metaphor", expression="MKfig_expr 花のよう", plain_meaning="MKfig_plain 美しい", example="MKfig_ex 彼女は花のようだ", sha="f4", **base),
        J(kind="cause_effect", cause="MKfig_cause 雨", effect="MKfig_effect 濡れる", phrasings=["MKfig_ph1 雨だと", "MKfig_ph2 雨なら"], sha="f5", **base),
        J(kind="cause_effect", cause="MKfig_cause2 風", sha="f6", **base),
        J(kind="pun", mechanism="MKfig_orphan", sha="f7", **base),
    ])
    exp["figurative_commonsense/train/records.jsonl"] = dict(
        lines=7, indexed=4 + 1, skipped={
            "missing_required:cause_effect.effect": 1, "missing_required:pun.pun": 1},
        split_absent=0, source_tag_unexpected=0,
        optional_absent={"pun.mechanism": 1, "haiku.note": 0})

    base = dict(family="narrative", split="train", setting="朝の台所",
                source="llm_authored:codex:pro-narrative-b000002")
    _write(root, "narrative/train/records.jsonl", [
        J(kind="story", title="MKnar_title 小さな花屋", sentences=[{"text": "MKnar_s1 花が咲いた。", "shape": "a"}, {"text": "MKnar_s2 友人が笑った。", "shape": "b"}], sha="n1", **base),
        J(kind="poem", title="MKnar_ptitle 湯気の窓", lines=["MKnar_l1 朝の窓", "MKnar_l2 湯気に曇る"], sha="n2", **base),
        J(kind="story", title="MKnar_bad", sentences=["文字列のみ"], sha="n3", **base),
    ])
    exp["narrative/train/records.jsonl"] = dict(
        lines=3, indexed=2, skipped={"bad_field_type:story.sentences": 1},
        split_absent=0, source_tag_unexpected=0)

    base = dict(family="paraphrase_entail", split="train", topic="家族",
                source="llm_authored:codex:pro-paraphrase_entail-b000002")
    _write(root, "paraphrase_entail/train/records.jsonl", [
        J(kind="pair", s1="MKpar_s1 姉は母に送られた。", s2="MKpar_s2 母が姉を送った。", label="entail", reason="MKpar_why 受け身", sha="r1", **base),
        J(kind="who_did_what", sentence="MKpar_sent 姉が駅へ。", question="MKpar_qq 誰が？", answer="MKpar_ans 姉", sha="r2", **base),
        J(kind="pair", s1="MKpar_only_s1", label="x", sha="r3", **base),
    ])
    exp["paraphrase_entail/train/records.jsonl"] = dict(
        lines=3, indexed=2, skipped={"missing_required:pair.s2": 1},
        split_absent=0, source_tag_unexpected=0, optional_absent={"pair.reason": 0})

    # --- evaluation / bookkeeping files that must never be indexed
    for rel, key in [("code/heldout/items.jsonl", "text"), ("even/code/heldout/items.jsonl", "text"),
                     ("conversation/heldout/utterances.jsonl", "text"),
                     ("even/conversation/heldout/utterances.jsonl", "text"),
                     ("code/overlap_dropped/items.jsonl", "text")]:
        _write(root, rel, [J(**{key: f"HELDOUT_ONLY_{rel.replace('/', '_')}", "split": "heldout"})])
    for fam in ("general_qa", "code_qa", "figurative_commonsense", "narrative", "paraphrase_entail"):
        _write(root, f"{fam}/heldout/records.jsonl", [J(kind="fact", q_variants=[f"HELDOUT_ONLY_{fam}"], answer="a", split="heldout")])
        _write(root, f"{fam}/overlap_dropped/records.jsonl", [J(kind="fact", q_variants=[f"OVERLAP_ONLY_{fam}"], answer="a")])
    _write(root, "code/ledger.jsonl", [J(batch="x", verdict="KEPT", kept=1, text="LEDGER_ONLY")])
    _write(root, "rescreen_log.jsonl", [J(text="RESCREEN_ONLY")])
    return exp


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("w1c")
    root, out, manifest = tmp / "corpus", tmp / "idx", tmp / "manifest.json"
    exp = make_corpus(root)
    code = bi.main(["--root", str(root), "--out", str(out), "--manifest", str(manifest)])
    assert code == 0
    return dict(root=root, out=out, manifest=json.loads(manifest.read_text()), exp=exp, corpus=Corpus(out))


# ----------------------------------------------------------------- T1 balance
def test_t1_every_file_balances_and_reasons_match_exactly(built):
    files = {f["path"]: f for f in built["manifest"]["files"]}
    assert set(files) == set(built["exp"])
    for path, e in built["exp"].items():
        f = files[path]
        assert f["lines"] == e["lines"], path
        assert f["indexed"] == e["indexed"], path
        assert f["skipped"] == e["skipped"], path
        assert f["lines"] == f["indexed"] + sum(f["skipped"].values()) and f["balanced"], path
        assert f["split_absent"] == e["split_absent"], path
        assert f["source_tag_unexpected"] == e["source_tag_unexpected"], path
        for key, n in e.get("optional_absent", {}).items():
            assert f["optional_absent"].get(key, 0) == n, (path, key)


def test_t1_skipped_rows_are_counted_not_dropped_in_db(built):
    for fam in FAMS:
        con = sqlite3.connect(f"file:{built['out'] / (fam + '.db')}?mode=ro", uri=True)
        n = con.execute("SELECT COUNT(*) FROM rows").fetchone()[0]
        meta = dict(con.execute("SELECT key,value FROM meta"))
        con.close()
        want = sum(f["indexed"] for f in built["manifest"]["files"] if f["family"] == fam)
        assert n == want == int(meta["rows"])
        assert json.loads(meta["skipped"]) is not None


# -------------------------------------------------------------- T2 heldout
def test_t2_heldout_and_overlap_markers_absent_everywhere(built):
    c = built["corpus"]
    for fam in FAMS:
        for marker in ("HELDOUT_ONLY", "OVERLAP_ONLY", "LEDGER_ONLY", "RESCREEN_ONLY"):
            r = c.search(marker, fam)
            assert r.state == "NO_MATCH" and len(r) == 0, (fam, marker)
        con = sqlite3.connect(f"file:{built['out'] / (fam + '.db')}?mode=ro", uri=True)
        bad = con.execute("SELECT COUNT(*) FROM rows WHERE source_file LIKE '%heldout%' "
                          "OR source_file LIKE '%overlap_dropped%'").fetchone()[0]
        con.close()
        assert bad == 0


def test_t2_excluded_files_are_listed_with_hashes(built):
    ex = {e["path"]: e for e in built["manifest"]["excluded"]}
    assert "code/heldout/items.jsonl" in ex and "general_qa/overlap_dropped/records.jsonl" in ex
    assert all(len(e["sha256"]) == 64 and e["reason"] in ("heldout", "overlap_dropped") for e in ex.values())


def test_t2_guard_refuses_heldout_path_in_sources(built, monkeypatch, tmp_path):
    spec = dict(bi.SOURCES["code"], files=("code/heldout/items.jsonl",))
    monkeypatch.setattr(bi, "SOURCES", {"code": spec})
    with pytest.raises(bi.ExcludedPathError):
        bi.main(["--root", str(built["root"]), "--out", str(tmp_path / "o"),
                 "--manifest", str(tmp_path / "m.json"), "--family", "code"])


# ------------------------------------------------------------ T3 no mixing
MARK = {"pro": "MKpro_a", "code": "MKcode_a", "conversation": "MKconv_a", "general_qa": "MKgqa_q",
        "code_qa": "MKcqa_a", "figurative_commonsense": "MKfig_pun", "narrative": "MKnar_s1",
        "paraphrase_entail": "MKpar_s1"}


def test_t3_family_markers_stay_in_their_own_db(built):
    c = built["corpus"]
    for own, marker in MARK.items():
        assert c.search(marker, own).state == "FOUND", (own, marker)
        for other in FAMS:
            if other != own:
                assert c.search(marker, other).state == "NO_MATCH", (own, other)
    for fam in FAMS:
        con = sqlite3.connect(f"file:{built['out'] / (fam + '.db')}?mode=ro", uri=True)
        fams = {r[0] for r in con.execute("SELECT DISTINCT family FROM rows")}
        con.close()
        assert fams == {fam}


def test_t3_shards_share_one_db_and_differ_by_source_file(built):
    c = built["corpus"]
    a, b = c.search("MKcode_a", "code")[0], c.search("MKcode_even", "code")[0]
    assert a.source_file == "code/items.jsonl" and b.source_file == "even/code/items.jsonl"
    conv = c.search("MKconv_even", "conversation")[0]
    assert conv.source_file == "even/conversation/utterances.jsonl"
    assert not (built["out"] / "even_code.db").exists()


# ----------------------------------------------------------- T4 provenance
def _origin_line(root: Path, w: Witness) -> dict:
    raw = (root / w.source_file).read_bytes().split(b"\n")
    return json.loads(raw[w.line - 1])


def test_t4_provenance_round_trip_for_every_family(built):
    c = built["corpus"]
    for fam, marker in MARK.items():
        w = c.search(marker, fam)[0]
        rec = _origin_line(built["root"], w)
        assert rec["sha"] == w.sha, fam
        assert marker.strip() in w.text
        assert w.origin == "generated" and w.generator == "codex"
        cite = w.cite()
        for key in ("family", "source", "text", "sha", "scene", "origin", "generator", "source_file", "line"):
            assert key in cite, key
        assert cite["origin"] == "generated"


def test_t4_line_numbers_are_physical_newline_counts(built):
    # line 11 of sentences.jsonl is the final line without a newline: skipped, not indexed
    c = built["corpus"]
    w = c.search("MKpro_c", "pro")[0]
    assert w.line == 8 and w.source_file == "out/sentences.jsonl"
    assert c.search("MKpro_partial", "pro").state == "NO_MATCH"


def test_t4_structured_body_uses_declared_fields(built):
    c = built["corpus"]
    w = c.search("MKnar_s1", "narrative")[0]
    assert w.kind == "story" and "MKnar_title" in w.text and "MKnar_s2" in w.text
    w = c.search("MKfig_ph2", "figurative_commonsense")[0]
    assert w.kind == "cause_effect" and "MKfig_cause" in w.text and "MKfig_effect" in w.text
    w = c.search("MKgqa_a", "general_qa")[0]
    assert w.kind == "fact" and "MKgqa_q" in w.text and "MKgqa_w" in w.text
    # a field outside the table is not searchable
    assert c.search("llm_authored", "general_qa").state == "NO_MATCH"


# ------------------------------------------------------- T5 typed states
def _mini_db(path: Path, *, family: str, with_format: bool = True, text: str = "MKx 本文") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(path)
    con.executescript("""
        CREATE TABLE rows(id INTEGER PRIMARY KEY, text, source, scene, grp, sha, family, source_file,
                          line, kind, fields, origin, generator, body_sha);
        CREATE VIRTUAL TABLE search USING fts5(text, scene, content='rows', content_rowid='id', tokenize='trigram');
        CREATE TABLE meta(key TEXT PRIMARY KEY,value TEXT);
    """)
    con.execute("INSERT INTO rows VALUES (1,?, 's','sc','g','sha',?, 'f.jsonl',1,'k','[]','generated','codex','b')", (text, family))
    con.execute("INSERT INTO search(search) VALUES ('rebuild')")
    rows = [("family", family), ("rows", "1")]
    if with_format:
        rows.append(("format", bi.FORMAT))
    con.executemany("INSERT INTO meta VALUES (?,?)", rows)
    con.commit()
    con.close()


def test_t5_missing_root_is_unknown_no_index_not_zero_hits(tmp_path):
    r = Corpus(tmp_path / "nowhere").search("改札", "conversation")
    assert isinstance(r, CorpusUnknown) and r.state == "UNKNOWN_NO_INDEX" and len(r) == 0
    assert r.state != "NO_MATCH" and r.reason
    (tmp_path / "empty").mkdir()
    assert Corpus(tmp_path / "empty").search("改札", "pro").state == "UNKNOWN_NO_INDEX"


def test_t5_family_db_missing_when_other_dbs_exist(tmp_path):
    _mini_db(tmp_path / "code.db", family="code")
    r = Corpus(tmp_path).search("MKx", "pro")
    assert isinstance(r, CorpusUnknown) and r.state == "UNKNOWN_FAMILY_DB_MISSING"


def test_t5_unreadable_and_rebuild_required(tmp_path):
    (tmp_path / "pro.db").write_bytes(b"this is not a sqlite database at all" * 20)
    r = Corpus(tmp_path).search("MKx", "pro")
    assert r.state == "UNKNOWN_INDEX_UNREADABLE" and isinstance(r, CorpusUnknown)
    _mini_db(tmp_path / "code.db", family="code", with_format=False)
    r = Corpus(tmp_path).search("MKx", "code")
    assert r.state == "UNKNOWN_INDEX_REBUILD_REQUIRED" and isinstance(r, CorpusUnknown)
    # no tables at all
    sqlite3.connect(tmp_path / "narrative.db").close()
    assert Corpus(tmp_path).search("MKx", "narrative").state == "UNKNOWN_INDEX_UNREADABLE"


def test_t5_query_not_searched_found_and_no_match(tmp_path):
    _mini_db(tmp_path / "pro.db", family="pro")
    c = Corpus(tmp_path)
    assert c.search("", "pro").state == "UNKNOWN_QUERY_NOT_SEARCHED"
    assert c.search("   ", "pro").state == "UNKNOWN_QUERY_NOT_SEARCHED"
    assert c.search("あ" * 81, "pro").state == "UNKNOWN_QUERY_NOT_SEARCHED"
    hit = c.search("MKx", "pro")
    assert hit.state == "FOUND" and len(hit) == 1 and not isinstance(hit, CorpusUnknown)
    miss = c.search("存在しない語", "pro")
    assert miss.state == "NO_MATCH" and miss == [] and not isinstance(miss, CorpusUnknown)
    assert miss.state != "UNKNOWN_NO_INDEX"


def test_t5_other_entry_points_and_status(tmp_path):
    c = Corpus(tmp_path / "nowhere")
    assert isinstance(c.search_scene("朝", [], "pro"), CorpusUnknown)
    w = Witness("pro", 1, "t", "s", "sc", "g", "sha")
    n = c.neighbors(w)
    assert isinstance(n, CorpusUnknown) and n.state == "UNKNOWN_NO_INDEX"
    assert c.status("pro") == "UNKNOWN_NO_INDEX"
    _mini_db(tmp_path / "code.db", family="code")
    c2 = Corpus(tmp_path)
    assert c2.status("pro") == "UNKNOWN_FAMILY_DB_MISSING"
    assert c2.status("code") == "INDEX_AVAILABLE"
    assert c2.search_scene("sc", [], "code").state in ("FOUND", "NO_MATCH")
    assert c2.neighbors(c2.search("MKx", "code")[0]).state == "FOUND"
    with pytest.raises(ValueError):
        c2.search("x", "not_a_family")


def test_t5_families_cover_all_eight_plus_local():
    assert set(FAMS) | {"local"} == set(FAMILIES)


# ---------------------------------------------------------- T6 root choice
def test_t6_env_var_is_read_at_construction(tmp_path, monkeypatch):
    _mini_db(tmp_path / "pro.db", family="pro")
    monkeypatch.setenv("VERA_P4_INDEX", str(tmp_path))
    assert Corpus().root == tmp_path
    assert Corpus().search("MKx", "pro").state == "FOUND"
    monkeypatch.setenv("VERA_P4_INDEX", str(tmp_path / "elsewhere"))
    assert Corpus().search("MKx", "pro").state == "UNKNOWN_NO_INDEX"


# ----------------------------------------------------------- T7 builder CLI
def test_t7_unset_root_and_out_are_typed_exits(tmp_path, monkeypatch, capsys):
    monkeypatch.delenv("VERA_CODEX_CORPUS", raising=False)
    monkeypatch.delenv("VERA_P4_INDEX", raising=False)
    assert bi.main([]) == 2
    assert "UNKNOWN_CORPUS_ROOT_UNSET" in capsys.readouterr().err
    assert bi.main(["--root", str(tmp_path)]) == 2
    assert "UNKNOWN_INDEX_OUT_UNSET" in capsys.readouterr().err


def test_t7_env_vars_supply_root_and_out(tmp_path, monkeypatch):
    root = tmp_path / "c"
    make_corpus(root)
    monkeypatch.setenv("VERA_CODEX_CORPUS", str(root))
    monkeypatch.setenv("VERA_P4_INDEX", str(tmp_path / "i"))
    assert bi.main(["--manifest", str(tmp_path / "m.json"), "--family", "pro"]) == 0
    assert (tmp_path / "i" / "pro.db").exists() and not (tmp_path / "i" / "code.db").exists()


def test_t7_missing_source_is_recorded_and_family_not_built(tmp_path):
    root = tmp_path / "c"
    make_corpus(root)
    (root / "conversation" / "utterances.jsonl").unlink()
    code = bi.main(["--root", str(root), "--out", str(tmp_path / "i"), "--manifest", str(tmp_path / "m.json")])
    m = json.loads((tmp_path / "m.json").read_text())
    assert m["families"]["conversation"]["state"] == "UNKNOWN_SOURCE_MISSING"
    assert "conversation/utterances.jsonl" in m["families"]["conversation"]["missing"]
    assert not (tmp_path / "i" / "conversation.db").exists()
    assert (tmp_path / "i" / "pro.db").exists() and code == 3


# --------------------------------------------------------- T8 old build() API
def test_t8_legacy_build_signature_and_meta(tmp_path):
    src = tmp_path / "pro.jsonl"
    src.write_text(J(text="旧形式の文。", source="s", sha="a") + "\n" + J(source="no text") + "\n"
                   + "{broken\n", encoding="utf-8")
    out = tmp_path / "idx" / "pro.db"
    n = bi.build(src, out, "pro")
    assert n == 1 and isinstance(n, int)
    con = sqlite3.connect(f"file:{out}?mode=ro", uri=True)
    meta = dict(con.execute("SELECT key,value FROM meta"))
    con.close()
    for key in ("rows", "size", "mtime_ns", "family", "format", "skipped"):
        assert key in meta, key
    skipped = json.loads(meta["skipped"])
    assert skipped.get("bad_json") == 1 and sum(skipped.values()) == 2
    assert Corpus(tmp_path / "idx").search("旧形式", "pro")[0].text == "旧形式の文。"
    assert bi.build(src, out, "pro") == 1  # unchanged input: reused


def test_t8_hf_package_imports_inputs():
    import tools.build_hf_package  # noqa: F401
    assert sorted(bi.INPUTS) == ["code", "conversation", "local", "pro"]


# --------------------------------------------------------- T9 trace hand-off
def test_t9_generation_trace_carries_index_state(tmp_path):
    from verantyx.abilities import Abilities
    from verantyx.chat import Chat
    chat = Chat([], general=tmp_path / "absent_general.db")
    chat._abilities = Abilities(Corpus(tmp_path / "nowhere"), general=chat.general)
    out = chat.reply("窓の様子を一文で描写してください。")
    steps = [t for t in out["trace"] if t.get("part") == "ability_corpus.search"]
    assert steps and all(t.get("index") == "UNKNOWN_NO_INDEX" for t in steps)


def test_t9_generation_trace_says_index_available_when_present(built, tmp_path):
    from verantyx.abilities import Abilities
    from verantyx.chat import Chat
    chat = Chat([], general=tmp_path / "absent_general.db")
    chat._abilities = Abilities(built["corpus"], general=chat.general)
    out = chat.reply("窓の様子を一文で描写してください。")
    steps = [t for t in out["trace"] if t.get("part") == "ability_corpus.search"]
    assert steps and all(t.get("index") != "UNKNOWN_NO_INDEX" for t in steps)


def test_t9_round3_conversation_supply_reports_index_state(tmp_path, monkeypatch):
    from verantyx.question import read
    from verantyx.round3 import GeneralRouter
    monkeypatch.setenv("VERA_P4_INDEX", str(tmp_path / "nowhere"))
    router = GeneralRouter(tmp_path / "r3")
    text = "こんにちは。"
    result, trace = router.answer(text, read(text))
    conv = [t for t in trace if t.get("part") == "round3.family.conversation"]
    assert conv and conv[0]["index"] == "UNKNOWN_NO_INDEX"
    assert conv[0]["verdict"] == "UNKNOWN_NO_INDEX"           # not the "searched, found nothing" wording
    assert result.get("kind") == "social"                   # fall-through unchanged


def test_t9_round3_no_match_keeps_old_verdict_when_index_exists(built, monkeypatch, tmp_path):
    from verantyx.question import read
    from verantyx.round3 import GeneralRouter
    monkeypatch.setenv("VERA_P4_INDEX", str(built["out"]))
    router = GeneralRouter(tmp_path / "r3")
    text = "こんにちは。"
    _, trace = router.answer(text, read(text))
    conv = [t for t in trace if t.get("part") == "round3.family.conversation"]
    assert conv and conv[0]["index"] == "INDEX_AVAILABLE"
    assert conv[0]["verdict"] in ("UNKNOWN_NO_STRICT_TURN",) or conv[0]["status"] == "ran"
