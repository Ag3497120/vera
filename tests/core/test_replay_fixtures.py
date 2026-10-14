"""The replay-identical property on STORED ledgers: every ledger under tests/fixtures/ledgers replays byte-identical under today's code.

The fixtures are a small selection (about 0.7 MB) of the research tree's ledgers, one or two per kind: scripted baseline runs, API runs of every evidence profile
(none / evidence.v1 / v2) and notes profile, constructed_allowed and record_only, a free-text control; memory stores (mem.v2 structure arms blind / notes with their answer runs,
and the context / log baselines).  Their `meta.json` corpus pointer was rewritten to the fixture corpus (it is outside the hash chain).

Every ledger records the Python it was made under (3.11.14) and a replay refuses any other (`python_mismatch`, a typed REPLAY_INPUTS_MISMATCH): on another Python the chain is still
verified byte for byte and the replay is expected to be refused, not to pass; CI pins 3.11.14, where the replay itself is asserted.
"""
import glob
import os
import sys

import pytest

from verantyx.loom import ledger as lg
from verantyx.loom import memanswer as ma
from verantyx.loom import memdoor as md
from verantyx.loom import memory as mem

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
FIX = os.path.join(ROOT, "tests", "fixtures", "ledgers")
RECORDED = (3, 11, 14)
SAME_PYTHON = tuple(sys.version_info[:3]) == RECORDED


def loom_dirs():
    return sorted(os.path.dirname(p) for p in glob.glob(os.path.join(FIX, "loom", "**", "HEAD"), recursive=True))


def test_the_fixture_set_is_small_and_covers_every_kind():
    dirs = loom_dirs()
    groups = {os.path.relpath(d, os.path.join(FIX, "loom")).split(os.sep)[0] for d in dirs}
    assert len(dirs) >= 20 and {"baseline_scripted", "runs_h55", "runs_h55e", "runs_h55f", "runs_unans_f", "runs_unans_adv_f", "runs_reach_f"} <= groups
    total = sum(os.path.getsize(os.path.join(dp, f)) for dp, _, fn in os.walk(FIX) for f in fn)
    assert total < 5 * 1024 * 1024


@pytest.mark.parametrize("d", loom_dirs(), ids=lambda d: os.path.relpath(d, os.path.join(FIX, "loom")))
def test_a_stored_loom_ledger_verifies_and_replays_identical(d):
    chain = lg.verify_chain(d)
    assert chain["status"] == "OK"
    v = lg.verify(d)
    if SAME_PYTHON:
        assert v["status"] == "OK" and v["replay"]["status"] == "IDENTICAL"
    else:
        assert v["status"] in ("OK", "REPLAY_INPUTS_MISMATCH") and (v["status"] == "OK" or v["replay"]["mismatch"] == "python_mismatch")


def test_a_stored_ledger_that_is_changed_by_one_byte_is_tampered(tmp_path):
    import shutil
    src = loom_dirs()[0]
    dst = tmp_path / "x"
    shutil.copytree(src, str(dst))
    p = dst / "ops.jsonl"
    b = bytearray(p.read_bytes())
    i = b.index(b'"op"') + 6
    b[i] = ord("z")
    p.write_bytes(bytes(b))
    assert lg.verify_chain(str(dst))["status"] != "OK"


@pytest.mark.parametrize("arm", ["notes", "blind"])
def test_a_stored_memory_store_and_its_answer_runs_verify(arm):
    st = os.path.join(FIX, "mem", "MEM-T06", arm)
    v = mem.verify_store(st, mem.FROM_HEADER)
    answers = sorted(os.listdir(os.path.join(st, "answers")))
    assert len(answers) >= 5
    if SAME_PYTHON:
        assert v["status"] == "OK"
        assert all(ma.verify_answer(os.path.join(st, "answers", a), st)["status"] == "OK" for a in answers)
    else:
        assert v["status"] in ("OK", "REPLAY_INPUTS_MISMATCH")
        assert all(lg.verify_chain(os.path.join(st, "answers", a))["status"] == "OK" for a in answers)


@pytest.mark.parametrize("arm", ["context", "log"])
def test_a_stored_baseline_arm_verifies(arm):
    st = os.path.join(FIX, "mem", "MEM-T06", arm)
    for sub in ("sessions", "answers"):
        for x in sorted(os.listdir(os.path.join(st, sub))):
            assert md.verify_baseline(os.path.join(st, sub, x))["status"] == "OK"


def test_a_dead_corpus_pointer_in_meta_json_is_found_again_by_sha(tmp_path):
    """meta.json is outside the hash chain and only a pointer: with a dead absolute path the corpus is found through the registry of shipped corpora, and the sha decides."""
    import json
    import shutil
    src = loom_dirs()[0]
    dst = tmp_path / "moved"
    shutil.copytree(src, str(dst))
    meta = json.load(open(dst / "meta.json", encoding="utf-8"))
    meta["corpus"] = "/nonexistent/gone/experiments/line3/bank2/data/fulllead_sents.jsonl"
    (dst / "meta.json").write_text(json.dumps(meta), encoding="utf-8")
    v = lg.verify(str(dst))
    if SAME_PYTHON:
        assert v["status"] == "OK"
    else:
        assert v["status"] in ("OK", "REPLAY_INPUTS_MISMATCH") and (v["status"] == "OK" or v["replay"]["mismatch"] == "python_mismatch")
    meta["corpus"] = "/nonexistent/gone/other.jsonl"
    (dst / "meta.json").write_text(json.dumps(meta), encoding="utf-8")
    assert lg.verify(str(dst))["status"] in ("OK", "REPLAY_INPUTS_MISMATCH")                 # still resolved through the registry; never a crash
