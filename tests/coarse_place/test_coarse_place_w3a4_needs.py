"""W3-a4 (docs section 12.17, D6): the list of common-noun + する predicates to write a frame for.  A small
pickle and a small sqlite; nothing here calls codex."""
import inspect
import json
import pickle
import sqlite3
from collections import Counter
from pathlib import Path

from tools import gen_coarse_evidence as gce


def make_placement(tmp: Path, rows):
    d = tmp / "pl"
    d.mkdir()
    con = sqlite3.connect(str(d / "placement.sqlite"))
    con.execute("CREATE TABLE headwords(word TEXT PRIMARY KEY, ns TEXT, state TEXT, origin TEXT,"
                " top TEXT, kind TEXT, n_seen INTEGER, by TEXT) WITHOUT ROWID")
    con.execute("CREATE TABLE evidence(word TEXT, arm TEXT, src TEXT, type TEXT, n INTEGER, base INTEGER,"
                " PRIMARY KEY(word, arm, src, type)) WITHOUT ROWID")
    for r in rows:
        con.execute("INSERT INTO headwords VALUES (?,?,?,?,?,?,?,?)", r)
    con.commit()
    con.close()
    (d / "manifest.json").write_text(json.dumps({"content_sha256": "abc123"}), encoding="utf-8")
    return d


def write_cache(path: Path, sahen):
    """sahen: {word: {src: uses}}"""
    sv = {"jawiki": Counter(), "codex:code": Counter()}
    for w, per in sahen.items():
        for src, k in per.items():
            sv[src][w] += k
    with open(path, "wb") as f:
        pickle.dump({"pos": {}, "sahen_verb": sv}, f)


def hw(word, n_seen, ns="P", state="UNPLACED"):
    return (word, ns, state, None, "", "token", n_seen, "")


def frames_file(path: Path, words):
    path.write_text("".join(json.dumps({"word": w, "ptype": None, "frame": {}, "abstained": True}) + "\n"
                            for w in words), encoding="utf-8")
    return path


def test_the_signature_of_the_old_selector_is_unchanged():
    assert list(inspect.signature(gce.select_needs_pred).parameters) == ["placement", "n", "stage_cache"]


def test_a_word_is_kept_by_its_largest_source_and_sources_are_never_added(tmp_path):
    rows = [hw("あ", 50), hw("い", 40), hw("う", 30)]
    pl = make_placement(tmp_path, rows)
    cache = tmp_path / "c.pkl"
    # あ: 20 in one source; い: 12 + 12 (a sum would pass, the maximum does not); う: 19
    write_cache(cache, {"あ": {"jawiki": 20, "codex:code": 1}, "い": {"jawiki": 12, "codex:code": 12},
                        "う": {"jawiki": 19}})
    out, boundary, reasons = gce.select_needs_sahen(str(pl), str(cache), 20, [], 100)
    assert [r["word"] for r in out] == ["あ"]
    assert out[0]["sahen_uses_max_src"] == 20
    assert out[0]["sahen_uses_by_src"] == {"codex:code": 1, "jawiki": 20}
    assert reasons == {"below_min_uses": 2}


def test_each_exclusion_is_counted_under_its_own_reason_in_order(tmp_path):
    rows = [hw("あ", 90), hw("い", 80, ns="N"), hw("う", 70, state="DECIDED"), hw("え", 60), hw("お", 50, ns="NP"),
            hw("か", 40, state="MULTIPLE")]
    pl = make_placement(tmp_path, rows)
    cache = tmp_path / "c.pkl"
    write_cache(cache, {w: {"jawiki": 25} for w in ("あ", "い", "う", "え", "お", "か", "ここにない")})
    ex = frames_file(tmp_path / "f.jsonl", ["え"])             # an abstention row also excludes
    out, boundary, reasons = gce.select_needs_sahen(str(pl), str(cache), 20, [str(ex)], 100)
    assert [r["word"] for r in out] == ["あ", "お", "か"]
    assert reasons == {"not_headword": 1, "ns_not_predicate": 1, "already_decided": 1, "in_exclude_frames": 1}
    assert [r["evidence_status"] for r in out] == ["NO_EVIDENCE", "NO_EVIDENCE", "SPLIT"]


def test_several_exclude_files_are_all_read(tmp_path):
    pl = make_placement(tmp_path, [hw("あ", 9), hw("い", 8), hw("う", 7)])
    cache = tmp_path / "c.pkl"
    write_cache(cache, {w: {"jawiki": 20} for w in ("あ", "い", "う")})
    a, b = frames_file(tmp_path / "a.jsonl", ["あ"]), frames_file(tmp_path / "b.jsonl", ["い"])
    out, _b, reasons = gce.select_needs_sahen(str(pl), str(cache), 20, [str(a), str(b)], 100)
    assert [r["word"] for r in out] == ["う"] and reasons["in_exclude_frames"] == 2


def test_the_boundary_tie_is_kept_whole_and_the_order_is_by_n_seen(tmp_path):
    rows = [hw("あ", 100), hw("い", 50), hw("う", 50), hw("え", 50), hw("お", 10)]
    pl = make_placement(tmp_path, rows)
    cache = tmp_path / "c.pkl"
    write_cache(cache, {r[0]: {"jawiki": 20} for r in rows})
    out, boundary, _r = gce.select_needs_sahen(str(pl), str(cache), 20, [], 2)
    assert boundary == 50
    assert [r["word"] for r in out] == ["あ", "い", "う", "え"]          # n = 2 cuts inside the tie: all of it is kept
    out, boundary, _r = gce.select_needs_sahen(str(pl), str(cache), 20, [], 100)
    assert [r["word"] for r in out] == ["あ", "い", "う", "え", "お"]


def test_a_cache_without_the_key_is_reported_not_read_as_zero(tmp_path):
    pl = make_placement(tmp_path, [hw("あ", 9)])
    cache = tmp_path / "c.pkl"
    with open(cache, "wb") as f:
        pickle.dump({"pos": {}}, f)
    assert gce.select_needs_sahen(str(pl), str(cache), 20, [], 100) == (None, None, None)


def test_the_command_writes_the_meta_with_rule_exclusions_and_reasons(tmp_path):
    pl = make_placement(tmp_path, [hw("あ", 9), hw("い", 8)])
    cache = tmp_path / "c.pkl"
    write_cache(cache, {"あ": {"jawiki": 20}, "い": {"jawiki": 20}})
    ex = frames_file(tmp_path / "f.jsonl", ["い"])
    out, meta = tmp_path / "needs.jsonl", tmp_path / "meta.json"
    rc = gce.main(["needs", "--kind", "pred", "--placement", str(pl), "--stage-cache", str(cache),
                   "--sahen-min-uses", "20", "--exclude-frames", str(ex), "--n", "1000000",
                   "--out", str(out), "--meta", str(meta)])
    assert rc == 0
    m = json.loads(meta.read_text(encoding="utf-8"))
    assert m["min_uses"] == 20 and m["total"] == 1 and m["reasons"] == {"in_exclude_frames": 1}
    assert m["exclude_frames"][0]["path"] == str(ex) and len(m["exclude_frames"][0]["sha256"]) == 64
    assert "ONE source" in m["rule"]
    row = json.loads(out.read_text(encoding="utf-8").splitlines()[0])
    assert row["word"] == "あ" and row["sahen_uses_max_src"] == 20


def test_the_new_arguments_need_kind_pred_and_a_stage_cache_and_exit_2_otherwise(tmp_path, capsys):
    pl = make_placement(tmp_path, [hw("あ", 9)])
    base = ["needs", "--placement", str(pl), "--out", str(tmp_path / "o"), "--meta", str(tmp_path / "m")]
    assert gce.main(base + ["--sahen-min-uses", "20"]) == 2                          # kind noun
    assert json.loads(capsys.readouterr().out)["state"] == "UNKNOWN_SAHEN_NEEDS_ARGS"
    assert gce.main(base + ["--kind", "pred", "--sahen-min-uses", "20"]) == 2        # no stage cache
    capsys.readouterr()
    assert gce.main(base + ["--exclude-frames", str(tmp_path / "x")]) == 2           # not silently ignored
    assert json.loads(capsys.readouterr().out)["state"] == "UNKNOWN_EXCLUDE_FRAMES_WITHOUT_SAHEN_MIN_USES"
    assert not (tmp_path / "o").exists() and not (tmp_path / "m").exists()
    # a stage cache without the key: typed, exit 2, nothing written
    cache = tmp_path / "c.pkl"
    with open(cache, "wb") as f:
        pickle.dump({"pos": {}}, f)
    assert gce.main(base + ["--kind", "pred", "--stage-cache", str(cache), "--sahen-min-uses", "20"]) == 2
    assert json.loads(capsys.readouterr().out)["state"] == "UNKNOWN_STAGE_CACHE_STALE"
    assert not (tmp_path / "o").exists()


def test_without_the_new_argument_the_old_output_is_what_it_was(tmp_path):
    rows = [hw("あ", 9), hw("い", 8)]
    pl = make_placement(tmp_path, rows)
    cache = tmp_path / "c.pkl"
    with open(cache, "wb") as f:
        pickle.dump({"pos": {"jawiki": Counter({("あ", "V"): 5, ("い", "A"): 5})}}, f)
    out, meta = tmp_path / "needs.jsonl", tmp_path / "meta.json"
    assert gce.main(["needs", "--kind", "pred", "--placement", str(pl), "--stage-cache", str(cache),
                     "--out", str(out), "--meta", str(meta)]) == 0
    m = json.loads(meta.read_text(encoding="utf-8"))
    assert [json.loads(l)["word"] for l in out.read_text(encoding="utf-8").splitlines()] == ["あ"]
    for k in ("min_uses", "exclude_frames", "reasons", "stage_cache"):
        assert k not in m
    assert "extraction cache saw the word more often as a verb" in m["rule"]
    row = json.loads(out.read_text(encoding="utf-8").splitlines()[0])
    assert "sahen_uses_max_src" not in row and "verb_uses" in row
