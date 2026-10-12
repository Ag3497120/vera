"""LOOM-path tests (L-LOOM-158..): a run's corpus is found by the sha256 its begin row recorded, not by the absolute path in its (unhashed) meta.json.

Old meta.json files name the checkout the run was made in (wt/line3-loom-batch/... and the like), which no longer exists; NEW ones record the path relative
to the repository root plus `corpus_sha`.  None of these tests needs a symlink, a --corpus flag, or the old worktree to exist.
"""
import hashlib
import json
import os
import shutil

import pytest

from verantyx.loom import ledger as lg
from verantyx.loom import paths
from verantyx.loom.mcp import LoomServer, Sandbox
from verantyx.loom.scripted import ScriptedWeaver, weave_tokyo
from loom_common import CORPUS, ROOT, TASKS, rows

REL = "experiments/line3/bank2/data/fulllead_sents.jsonl"
STORED = ("runs_h55", "runs_h55b", "runs_h55c", "runs_h55d", "runs_unans", "baseline_scripted/runs")
DEAD = "/nonexistent/wt/line3-loom-gone/" + REL


def _sha():
    with open(CORPUS, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def _stored_run():
    base = os.path.join(ROOT, "experiments/line3/loom/runs_h55b")
    names = [n for n in sorted(os.listdir(base)) if os.path.exists(os.path.join(base, n, "ops.jsonl"))] if os.path.isdir(base) else []
    if not names:
        pytest.skip("no stored runs_h55b")
    return os.path.join(base, names[0])


def _copy_with_meta(src, dst, meta):
    shutil.copytree(src, str(dst))
    if meta is None:
        os.unlink(os.path.join(str(dst), "meta.json"))
    else:
        with open(os.path.join(str(dst), "meta.json"), "w", encoding="utf-8") as f:
            json.dump(meta, f)
    return str(dst)


def _fresh(tmp_path, corpus=CORPUS):
    tasks = [dict(TASKS[0], corpus=corpus)]
    srv = LoomServer(tasks, str(tmp_path / "runs"), (), "strict_npa", evidence="off")
    w = ScriptedWeaver(srv, "demo/tokyo_ca", "claude-haiku-4-5", "r1")
    assert weave_tokyo(w)["ok"]
    return srv, tmp_path / "runs" / "r1"


# ---- new runs ----------------------------------------------------------------------------------------------------
def test_a_new_runs_meta_records_the_corpus_relative_to_the_repo_root_and_its_sha(tmp_path):
    srv, d = _fresh(tmp_path)
    meta = json.load(open(str(d / "meta.json"), encoding="utf-8"))
    assert meta["corpus"] == REL and meta["corpus_sha"] == _sha() == rows(d)[0]["result"]["header"]["corpus_sha"]
    assert not os.path.isabs(meta["corpus"]) and ROOT not in json.dumps(meta)               # no absolute path anywhere in it
    assert lg.verify(d)["status"] == "OK"


def test_a_new_runs_relative_path_is_resolved_against_the_repo_root_not_the_working_directory(tmp_path, monkeypatch):
    srv, d = _fresh(tmp_path)
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.chdir(str(elsewhere))
    assert lg.replay(d).identical and lg.verify(d)["status"] == "OK"
    sb = Sandbox(tmp_path / "runs2", [CORPUS], [])                                              # and through a sandbox that lists the corpus by its absolute path
    assert lg.replay(d, loader=sb.read_bytes).identical
    srv2 = LoomServer(TASKS, str(tmp_path / "runs"), (), "strict_npa", evidence="off")                           # a restarted server reloads the run (replays it, no --corpus)
    assert srv2.call("status", {"run_id": "r1"})


def test_a_corpus_outside_the_repo_root_keeps_its_absolute_path_and_the_sha(tmp_path):
    toy = tmp_path / "toy.jsonl"
    toy.write_text(json.dumps({"sha": "0" * 64, "title": "t", "sent": "東京は日本の首都です。", "source": "t0#0"}, ensure_ascii=False) + "\n", encoding="utf-8")
    srv = LoomServer([dict(TASKS[0], corpus=str(toy))], str(tmp_path / "runs"), (), "strict_npa", evidence="off")
    ScriptedWeaver(srv, "demo/tokyo_ca", "m", "t1").begin()
    meta = json.load(open(str(tmp_path / "runs" / "t1" / "meta.json"), encoding="utf-8"))
    assert meta["corpus"] == str(toy.resolve()) and len(meta["corpus_sha"]) == 64
    assert lg.replay(tmp_path / "runs" / "t1").identical                                        # the absolute pointer is tried first


def test_rel_to_root_and_the_candidate_order():
    assert paths.rel_to_root(os.path.join(ROOT, REL)) == REL and paths.rel_to_root("/etc/hosts").startswith("/")
    c = paths.candidates(DEAD)
    assert c[0] == DEAD and c[1] == os.path.join(ROOT, REL)                                    # the recorded path, then its tail under this root
    assert [os.path.relpath(x, ROOT) for x in c[2:]] == [r for r in paths.KNOWN_CORPORA if r != REL] or os.path.join(ROOT, REL) in c
    assert paths.candidates(REL)[0] == os.path.join(ROOT, REL)                                  # a relative pointer is joined to the root
    assert paths.candidates(None)[0] == os.path.join(ROOT, paths.KNOWN_CORPORA[0])
    assert paths.candidates(DEAD, with_registry=False) == [DEAD, os.path.join(ROOT, REL)]
    for r in paths.KNOWN_CORPORA:
        assert not os.path.isabs(r)


# ---- old runs: dead absolute path ---------------------------------------------------------------------------------
@pytest.mark.parametrize("meta", [
    {"corpus": DEAD, "isolated": False, "task_id": "x"},                                          # the worktree prefix of an old checkout
    {"corpus": "/nonexistent/moved/fulllead_sents.jsonl", "isolated": False, "task_id": "x"},    # no tail exists under the root: the registry, by sha
    {"isolated": False, "task_id": "x"},                                                         # no path at all
    None,                                                                                         # no meta.json at all
])
def test_a_meta_json_with_a_dead_absolute_path_still_verifies_and_replays_by_sha(tmp_path, meta):
    d = _copy_with_meta(_stored_run(), tmp_path / "copy", meta)
    rep = lg.replay(d)
    assert rep.status == "IDENTICAL", (rep.mismatch, rep.first_diff)
    v = lg.verify(d)
    assert v["status"] == "OK" and v["replay"]["status"] == "IDENTICAL"
    out = lg.emitted_output(d)
    assert out["status"] in ("emitted", "no_output")
    meta_after = os.path.exists(os.path.join(d, "meta.json")) and json.load(open(os.path.join(d, "meta.json"), encoding="utf-8"))
    assert meta_after == (meta or False)                                                          # nothing was written back to meta.json


def test_a_dead_path_is_scored_through_score_run_without_the_corpus_flag(tmp_path):
    import importlib.util
    import sys
    if "loom_harness" not in sys.modules:                                                          # the same module object test_loom_harness uses
        spec = importlib.util.spec_from_file_location("loom_harness", os.path.join(ROOT, "experiments/line3/loom/harness.py"))
        mod = importlib.util.module_from_spec(spec)
        sys.modules["loom_harness"] = mod
        spec.loader.exec_module(mod)
    H = sys.modules["loom_harness"]
    score = H.score
    d = _copy_with_meta(_stored_run(), tmp_path / "copy", {"corpus": DEAD, "isolated": False, "task_id": "x"})
    rs = score.score_run(d, score.load_bank(H.BANK), score.load_gold())
    assert rs.status != "run_not_verified" and rs.replay_verified


def test_an_existing_pointer_to_another_file_is_a_sha_mismatch_and_an_explicit_path_is_still_read_as_given(tmp_path):
    other = tmp_path / "other.jsonl"
    other.write_text(open(CORPUS, encoding="utf-8").read().splitlines()[0] + "\n", encoding="utf-8")
    d = _copy_with_meta(_stored_run(), tmp_path / "copy", {"corpus": str(other)})
    assert lg.replay(d).identical                                                                 # the pointer is wrong, but another candidate IS the recorded corpus
    assert lg.replay(d, str(other)).mismatch == "corpus_sha_mismatch"                            # an explicit path is the caller's word, never second-guessed
    assert lg.replay(d, str(tmp_path / "gone.jsonl")).mismatch == "corpus_unreadable"
    assert lg.replay(d, CORPUS).identical


def test_corpus_unresolved_only_when_nothing_matches_the_sha(tmp_path):
    toy = tmp_path / "toy.jsonl"
    toy.write_text(json.dumps({"sha": "0" * 64, "title": "t", "sent": "東京は日本の首都です。", "source": "t0#0"}, ensure_ascii=False) + "\n", encoding="utf-8")
    srv = LoomServer([dict(TASKS[0], corpus=str(toy))], str(tmp_path / "runs"), (), "strict_npa", evidence="off")
    ScriptedWeaver(srv, "demo/tokyo_ca", "m", "t1").begin()
    d = tmp_path / "runs" / "t1"
    (d / "meta.json").write_text(json.dumps({"corpus": DEAD}), encoding="utf-8")
    rep = lg.replay(d)
    assert rep.status == "INPUTS" and rep.mismatch == "corpus_unresolved" and rep.exit_code() == 2
    v = lg.verify(d)
    assert v["status"] == "REPLAY_INPUTS_MISMATCH" and v["replay"]["mismatch"] == "corpus_unresolved"
    assert lg.replay(d, str(toy)).identical                                                       # --corpus still works for a corpus the registry does not know
    # a loader that refuses everything is still the sandbox status, not "unresolved"
    sb = Sandbox(tmp_path / "runs3", [], [])
    assert lg.replay(_copy_with_meta(_stored_run(), tmp_path / "c2", {"corpus": DEAD}), loader=sb.read_bytes).mismatch == "corpus_outside_sandbox"


def test_fixture_paths_follow_the_same_rule(tmp_path):
    fixture = os.path.join(ROOT, "experiments/line3/loom/fixture_repo")
    assert paths.rel_to_root(fixture) == "experiments/line3/loom/fixture_repo"
    assert paths.fixture_path("experiments/line3/loom/fixture_repo") == fixture
    assert paths.fixture_path("/nonexistent/wt/old/experiments/line3/loom/fixture_repo") == fixture
    gone = str(tmp_path / "no_such_folder")
    assert paths.fixture_path(gone) == gone and paths.fixture_path(None) is None


# ---- every stored ledger, with no symlink and no --corpus -----------------------------------------------------------
def test_every_stored_ledger_replays_identical_without_a_corpus_flag_or_a_symlink():
    got = {}

    def this_checkout_only(path):                                                                 # the old worktrees (wt/line3, wt/line3-loom-ctl ...) may exist on this machine; here they do not
        if not os.path.realpath(path).startswith(os.path.realpath(ROOT) + os.sep):
            raise FileNotFoundError(path)
        return open(path, "rb").read()

    for sub in STORED:
        base = os.path.join(ROOT, "experiments/line3/loom", sub)
        if not os.path.isdir(base):
            pytest.skip("no stored %s" % sub)
        for name in sorted(os.listdir(base)):
            d = os.path.join(base, name)
            if os.path.exists(os.path.join(d, "ops.jsonl")):
                rep = lg.replay(d, loader=this_checkout_only)
                assert rep.status == "IDENTICAL", (sub, name, rep.mismatch, rep.first_diff)
                got[sub] = got.get(sub, 0) + 1
    assert got == {"runs_h55": 30, "runs_h55b": 30, "runs_h55c": 30, "runs_h55d": 30, "runs_unans": 100, "baseline_scripted/runs": 30}
