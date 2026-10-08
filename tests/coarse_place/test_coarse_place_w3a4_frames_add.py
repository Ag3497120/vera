"""W3-a4 (docs section 12.17, D7): the builder reads a second generated-frames file; a word in both stops
the build before anything is written; with no second file the manifest has the old form."""
import json

import pytest

from tools import build_coarse_placement as bcp

from test_coarse_place_build import build, make_codex_db  # noqa: F401
from test_coarse_place_review3 import write_jawiki  # noqa: F401
from test_coarse_place_w3a3_query import BATCH, CFG, frow  # noqa: F401

B2 = "b00001_abcdefabcdef"


def write_frames(path, rows):
    path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
    return path


def write_ledger(path, batch, calls=1, status="ok"):
    ev = []
    for a in range(1, calls + 1):
        ev.append({"ev": "start", "batch": batch, "attempt": a})
        ev.append({"ev": "end", "batch": batch, "attempt": a, "status": status if a == calls else "fail"})
    path.write_text("".join(json.dumps(e) + "\n" for e in ev), encoding="utf-8")
    return path


@pytest.fixture(scope="module")
def mat(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("w3a4f")
    texts = ["人が言葉を叫んだ。"] * 14 + ["人が町へ移動した。"] * 14
    cdir = tmp / "cx"
    for fam in ("conversation", "narrative"):
        make_codex_db(cdir, fam, texts)
    jw = tmp / "jw.jsonl"
    write_jawiki(jw, [("ダミー", "ダミーは、日本の町である。")])
    f1 = write_frames(tmp / "f1.jsonl", [frow("叫ぶ", "P_COMMUNICATE", {"が": ["PERSON"], "を": ["INFO_LANGUAGE"]})])
    l1 = write_ledger(tmp / "l1.jsonl", BATCH)
    f2 = write_frames(tmp / "f2.jsonl", [frow("移動する", "P_MOVE", {"が": ["PERSON"], "へ": ["PLACE"]}, batch=B2)])
    l2 = write_ledger(tmp / "l2.jsonl", B2, calls=2)
    return {"tmp": tmp, "cdir": cdir, "jw": jw, "f1": f1, "l1": l1, "f2": f2, "l2": l2}


def mk(mat, out, *extra):
    return build(out, jawiki=mat["jw"], codex_dir=mat["cdir"], families="conversation,narrative",
                 extra=list(extra), cfg=CFG)


def test_two_files_are_read_and_the_manifest_has_the_parts_and_the_totals(mat):
    out = mat["tmp"] / "two"
    assert mk(mat, out, "--generated-frames", str(mat["f1"]), "--generated-frames-ledger", str(mat["l1"]),
              "--generated-frames-add", str(mat["f2"]), "--generated-frames-add-ledger", str(mat["l2"])) == 0
    m = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    g = m["generated_frames"]
    assert g["path"].endswith("f1.jsonl") and g["ledger_path"].endswith("l1.jsonl")      # the first file keeps its meaning
    assert [p["path"].rsplit("/", 1)[1] for p in g["parts"]] == ["f1.jsonl", "f2.jsonl"]
    assert g["lines"] == 2 and g["rows_read"] == 2
    assert [p["calls"] for p in g["parts"]] == [1, 2] and g["calls"] == 3
    assert g["batches_ok"] == 2 and g["batches_failed"] == 0
    assert g["parts"][1]["effort"] == "low" and g["effort"] == "low"
    assert g["models"] == ["gpt-6-luna:low"]
    assert g["parts"][1]["ledger_sha256"] and g["parts"][1]["sha256"]
    assert m["args"]["generated_frames_add"].endswith("f2.jsonl")
    assert any(x["name"].startswith("generated predicate frames, second file") for x in m["materials"])
    # both files' words carry a gen_frame row
    from verantyx import coarse_place as cp
    assert cp.query("叫ぶ", placement=str(out))["generated_frame"] is True
    assert cp.query("移動する", placement=str(out))["axes"]["gen_frame"]["top"] == ["P_MOVE"]


def test_a_word_in_both_files_stops_the_build_with_exit_5_and_writes_nothing(mat, capsys):
    f3 = write_frames(mat["tmp"] / "f3.jsonl", [frow("叫ぶ", None, {}, batch=B2)])     # an abstention counts too
    out = mat["tmp"] / "overlap"
    rc = mk(mat, out, "--generated-frames", str(mat["f1"]), "--generated-frames-add", str(f3))
    assert rc == bcp.EXIT_GEN_FRAMES_OVERLAP == 5
    res = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert res == {"state": "GENERATED_FRAMES_OVERLAP", "n": 1, "words": ["叫ぶ"]}
    assert not out.exists()


def test_the_second_file_needs_the_first(mat, capsys):
    out = mat["tmp"] / "noadd"
    assert mk(mat, out, "--generated-frames-add", str(mat["f2"])) == 2
    assert json.loads(capsys.readouterr().out.strip().splitlines()[-1])["state"] == "UNKNOWN_GENERATED_FRAMES_ADD_ARGS"
    assert not out.exists()


def test_without_the_second_file_the_manifest_has_the_old_form(mat):
    out = mat["tmp"] / "one"
    assert mk(mat, out, "--generated-frames", str(mat["f1"]), "--generated-frames-ledger", str(mat["l1"])) == 0
    m = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    assert "parts" not in m["generated_frames"]
    assert "generated_frames_add" not in m["args"] and "compare_to" not in m["args"]
    assert "compare_to" not in m
    assert not any("second file" in x["name"] for x in m["materials"])
    assert m["generated_frames"]["calls"] == 1 and m["generated_frames"]["rows_read"] == 1
