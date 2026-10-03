"""W3-a4 (docs section 12.17, D8): ``--compare-to`` puts the differences to another placement in the manifest
(the other placement is only read)."""
import hashlib
import json

import pytest

from test_coarse_place_build import build, make_codex_db  # noqa: F401
from test_coarse_place_review3 import write_jawiki  # noqa: F401
from test_coarse_place_w3a3_query import CFG  # noqa: F401

CFG4 = dict(CFG, frame_cover_rule="k62_he_by_ni_place")


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


@pytest.fixture(scope="module")
def pair(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("w3a4c")
    jw = tmp / "jw.jsonl"
    write_jawiki(jw, [("ダミー", "ダミーは、日本の町である。")])
    old_texts = ["人が言葉を叫んだ。"] * 14
    new_texts = old_texts + ["人が町へ移動した。"] * 14
    for name, texts in (("old", old_texts), ("new", new_texts)):
        for fam in ("conversation", "narrative"):
            make_codex_db(tmp / (name + "_cx"), fam, texts)
    old = tmp / "old"
    assert build(old, jawiki=jw, codex_dir=tmp / "old_cx", families="conversation,narrative", cfg=CFG4) == 0
    before = {f: sha(old / f) for f in ("placement.sqlite", "manifest.json")}
    new = tmp / "new"
    assert build(new, jawiki=jw, codex_dir=tmp / "new_cx", families="conversation,narrative", cfg=CFG4,
                 extra=["--compare-to", str(old)]) == 0
    return {"old": old, "new": new, "before": before}


def test_the_other_placement_is_not_changed(pair):
    assert {f: sha(pair["old"] / f) for f in pair["before"]} == pair["before"]


def test_headwords_ctx_and_frames_differences_are_counted(pair):
    m = json.loads((pair["new"] / "manifest.json").read_text(encoding="utf-8"))
    c = m["compare_to"]
    h = c["headwords"]
    assert h["rows"][1] > h["rows"][0] and h["removed"] == 0 and h["removed_words"] == []
    assert h["added"] == h["added_sahen_verb"] + h["added_other"] > 0
    assert h["added_sahen_verb"] >= 1                       # the verbal-noun predicate is new
    assert "移動" in h["added_other_words"] and "移動する" not in h["added_other_words"]
    assert c["ctx"]["rows"][1] >= c["ctx"]["rows"][0]
    assert c["generated_frames"] == {"rows": [0, 0], "added": 0, "removed": 0}
    assert c["dir"] == str(pair["old"]) and c["content_sha256"]
    assert m["args"]["compare_to"] == str(pair["old"])
    assert m["duration_sec"] >= c["compare_sec"] >= 0


def test_a_changed_decision_is_listed_by_namespace_and_kind(pair):
    m = json.loads((pair["new"] / "manifest.json").read_text(encoding="utf-8"))
    h = m["compare_to"]["headwords"]
    for ns, d in h["changed_by_ns"].items():
        assert d["total"] == d.get("decision_changed", 0) + d.get("by_only", 0)
    assert len(h["changed_P_words"]) == sum(d["total"] for ns, d in h["changed_by_ns"].items() if "P" in ns)
    for r in h["changed_P_words"]:
        assert r["kind"] in ("decision_changed", "by_only") and len(r["before"]) == len(r["after"]) == 6
    assert len(h["changed_N_decision_top20"]) <= 20


def test_without_the_argument_the_manifest_has_no_compare_key(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("w3a4c2")
    jw = tmp / "jw.jsonl"
    write_jawiki(jw, [("ダミー", "ダミーは、日本の町である。")])
    out = tmp / "p"
    assert build(out, jawiki=jw, cfg=CFG4) == 0
    assert "compare_to" not in json.loads((out / "manifest.json").read_text(encoding="utf-8"))
