"""W1-c2 / R1: a train row whose body equals a heldout body of the same family is skipped by rule.

Synthetic data only (tmp_path). Nothing here touches the real corpus or the real index.
The rule: ``heldout_body_overlap`` is counted per file, per reason, and the identity
``lines == indexed + sum(skipped)`` still holds. Families are never mixed.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from tools import build_p4_corpus_index as bi
from verantyx.ability_corpus import Corpus

SHARED = "共有の文です。"
SRC = "llm_authored:codex:pro-conv-b00001"


def J(**kw) -> str:
    return json.dumps(kw, ensure_ascii=False)


def _write(root: Path, rel: str, lines: list[str], *, final_newline: bool = True) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(("\n".join(lines) + ("\n" if final_newline else "")).encode("utf-8"))


def _corpus(root: Path) -> None:
    """conversation (two shards, two heldout files) and pro (no heldout), all sharing one body."""
    _write(root, "conversation/utterances.jsonl", [
        J(text=SHARED, scene="職場", dialogue_id="d1", source=SRC, sha="a1"),
        J(text="会話だけの文です。", scene="職場", dialogue_id="d1", source=SRC, sha="a2"),
    ])
    _write(root, "even/conversation/utterances.jsonl", [
        J(text=SHARED, scene="駅", dialogue_id="d2", split="train", source=SRC, sha="b1"),
        J(text="偶数側だけの文です。", scene="駅", dialogue_id="d2", split="train", source=SRC, sha="b2"),
    ])
    _write(root, "conversation/heldout/utterances.jsonl", [
        J(text=SHARED, split="heldout", family="conversation", source=SRC),
    ])
    _write(root, "even/conversation/heldout/utterances.jsonl", [
        J(text="評価にだけある文です。", split="heldout", family="conversation", source=SRC),
    ])
    _write(root, "out/sentences.jsonl", [
        J(text=SHARED, scene="朝", source="llm_authored:codex:pro-b00001", sha="p1"),
    ])


def _run(root: Path, tmp: Path, *families: str):
    out, manifest = tmp / "idx", tmp / "manifest.json"
    argv = ["--root", str(root), "--out", str(out), "--manifest", str(manifest)]
    for f in families:
        argv += ["--family", f]
    code = bi.main(argv)
    return code, json.loads(manifest.read_text()), out


def _files(manifest: dict) -> dict:
    return {f["path"]: f for f in manifest["files"]}


def test_h1_overlap_rows_are_skipped_by_rule_per_family_only(tmp_path):
    root = tmp_path / "corpus"
    _corpus(root)
    code, manifest, out = _run(root, tmp_path, "conversation", "pro")
    assert code == 0
    files = _files(manifest)
    for rel in ("conversation/utterances.jsonl", "even/conversation/utterances.jsonl"):
        assert files[rel]["skipped"] == {"heldout_body_overlap": 1}
        assert files[rel]["indexed"] == 1
        assert files[rel]["lines"] == files[rel]["indexed"] + sum(files[rel]["skipped"].values())
        assert files[rel]["balanced"] is True
    assert files["out/sentences.jsonl"]["skipped"] == {}
    assert files["out/sentences.jsonl"]["indexed"] == 1
    corpus = Corpus(out)
    assert corpus.search("共有の文", "conversation").state == "NO_MATCH"
    assert corpus.search("共有の文", "pro").state == "FOUND"          # another family is untouched
    assert corpus.search("会話だけの文", "conversation").state == "FOUND"
    assert corpus.search("偶数側だけの文", "conversation").state == "FOUND"
    assert manifest["heldout_unlisted"] == []


def test_h2_unextractable_heldout_lines_are_counted_by_reason(tmp_path):
    root = tmp_path / "corpus"
    _corpus(root)
    _write(root, "conversation/heldout/utterances.jsonl", [
        J(text=SHARED, split="heldout"),
        J(split="heldout"),                    # no text field
        "{not json",
        "",
    ])
    _write(root, "even/conversation/heldout/utterances.jsonl", [
        J(text="評価にだけある文です。", split="heldout"),
        J(text="末尾に改行が無い行です。", split="heldout"),
    ], final_newline=False)
    code, manifest, _ = _run(root, tmp_path, "conversation", "pro")
    assert code == 0
    held = manifest["families"]["conversation"]["heldout"]
    by_path = {f["path"]: f for f in held["files"]}
    one = by_path["conversation/heldout/utterances.jsonl"]
    two = by_path["even/conversation/heldout/utterances.jsonl"]
    assert one["unextractable"] == {"missing_required:conversation.text": 1, "bad_json": 1, "blank_line": 1}
    assert two["unextractable"] == {"partial_final_line": 1}
    raw = (root / "conversation/heldout/utterances.jsonl").read_bytes()
    assert one["lines"] == 4 and one["bytes"] == len(raw) and one["sha256"] == hashlib.sha256(raw).hexdigest()
    assert two["lines"] == 2
    assert held["records"] == 2 and held["distinct_bodies"] == 2 and held["none_listed"] is False
    pro = manifest["families"]["pro"]["heldout"]
    assert pro["none_listed"] is True and pro["files"] == [] and pro["records"] == 0


def test_h3_missing_listed_heldout_file_means_family_not_built(tmp_path):
    root = tmp_path / "corpus"
    _corpus(root)
    (root / "even/conversation/heldout/utterances.jsonl").unlink()
    code, manifest, out = _run(root, tmp_path, "conversation", "pro")
    assert code == 3
    fam = manifest["families"]["conversation"]
    assert fam["state"] == "UNKNOWN_HELDOUT_MISSING"
    assert fam["missing_heldout"] == ["even/conversation/heldout/utterances.jsonl"]
    assert not (out / "conversation.db").exists()
    assert (out / "pro.db").exists()                      # the other family is unaffected
    assert not any(f["family"] == "conversation" for f in manifest["files"])


def test_h4_unlisted_heldout_file_is_reported_and_fails_the_run(tmp_path):
    root = tmp_path / "corpus"
    _corpus(root)
    _write(root, "out/heldout/x.jsonl", [J(text="どの系列にも載っていない評価データです。")])
    code, manifest, _ = _run(root, tmp_path, "conversation", "pro")
    assert code == 3
    assert manifest["heldout_unlisted"] == ["out/heldout/x.jsonl"]
    assert manifest["families"]["conversation"]["state"] == "BUILT"   # building continues


def test_h4b_nothing_unlisted_is_an_empty_list(tmp_path):
    root = tmp_path / "corpus"
    _corpus(root)
    code, manifest, _ = _run(root, tmp_path, "conversation", "pro")
    assert code == 0 and manifest["heldout_unlisted"] == []


def test_h5_split_heldout_train_row_keeps_its_earlier_reason(tmp_path):
    root = tmp_path / "corpus"
    _corpus(root)
    _write(root, "conversation/utterances.jsonl", [
        J(text=SHARED, split="heldout", source=SRC, sha="a1"),     # same body, but its own split says heldout
        J(text=SHARED, split="train", source=SRC, sha="a3"),
    ])
    code, manifest, _ = _run(root, tmp_path, "conversation")
    assert code == 0
    f = _files(manifest)["conversation/utterances.jsonl"]
    assert f["skipped"] == {"split_not_train:heldout": 1, "heldout_body_overlap": 1}
    assert f["indexed"] == 0 and f["balanced"] is True


def test_h5b_split_absent_is_counted_only_for_indexed_rows(tmp_path):
    root = tmp_path / "corpus"
    _corpus(root)
    code, manifest, _ = _run(root, tmp_path, "conversation")
    f = _files(manifest)["conversation/utterances.jsonl"]
    assert f["indexed"] == 1 and f["split_absent"] == 1          # the overlap row (split absent too) is not counted


def test_h6_heldout_bodies_return_only_hashes_and_tables_are_separate(tmp_path):
    root = tmp_path / "corpus"
    _corpus(root)
    bodies, report = bi.heldout_bodies(root, "conversation")
    assert isinstance(bodies, (set, frozenset)) and len(bodies) == 2
    assert all(len(b) == 64 and set(b) <= set("0123456789abcdef") for b in bodies)
    assert hashlib.sha256(SHARED.encode("utf-8")).hexdigest() in bodies
    flat = json.dumps(report, ensure_ascii=False)
    assert SHARED not in flat and "評価にだけある文です。" not in flat
    assert not any(SHARED in b for b in bodies)
    for family, paths in bi.HELDOUT.items():
        for rel in paths:
            assert "heldout" in Path(rel).parts, rel
    for family, spec in bi.SOURCES.items():
        for rel in spec["files"]:
            assert "heldout" not in Path(rel).parts, rel
    assert bi.HELDOUT["pro"] == ()
    assert set(bi.HELDOUT) == set(bi.SOURCES)


def test_h6b_index_input_guard_still_refuses_heldout_paths():
    for paths in bi.HELDOUT.values():
        for rel in paths:
            try:
                bi.guard_path(rel)
            except bi.ExcludedPathError:
                continue
            raise AssertionError(f"guard_path accepted {rel}")


def test_h7_legacy_build_does_not_look_at_heldout(tmp_path):
    src = tmp_path / "c.jsonl"
    src.write_text(J(text=SHARED, source=SRC) + "\n" + J(text=SHARED, source=SRC) + "\n", encoding="utf-8")
    rows = bi.build(src, tmp_path / "idx" / "conversation.db", "conversation")
    assert rows == 2
    result = bi.build_db([(src, "c.jsonl")], tmp_path / "idx2" / "conversation.db", "conversation",
                         bi.SOURCES["conversation"])
    assert result["rows"] == 2 and result["files"][0]["skipped"] == {}


def test_h7b_build_db_with_exclusion_set_counts_reason_and_keeps_identity(tmp_path):
    src = tmp_path / "c.jsonl"
    src.write_text(J(text=SHARED, source=SRC) + "\n" + J(text="残る文です。", source=SRC) + "\n", encoding="utf-8")
    exclude = frozenset({hashlib.sha256(SHARED.encode("utf-8")).hexdigest()})
    result = bi.build_db([(src, "c.jsonl")], tmp_path / "idx" / "conversation.db", "conversation",
                         bi.SOURCES["conversation"], exclude_bodies=exclude)
    rep = result["files"][0]
    assert rep["indexed"] == 1 and rep["skipped"] == {"heldout_body_overlap": 1}
    assert rep["lines"] == rep["indexed"] + sum(rep["skipped"].values())
