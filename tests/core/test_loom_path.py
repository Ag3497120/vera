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


REL = "tests/fixtures/line3/bank2/data/fulllead_sents.jsonl"


DEAD = "/nonexistent/wt/line3-loom-gone/" + REL


def _sha():
    with open(CORPUS, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


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
