"""Shared helpers of the loom tests (tests/line3/test_loom_*.py): the corpus, the task bank and a server on a temp folder."""
import json
import os

from verantyx.loom.mcp import LoomServer
from verantyx.loom.scripted import ScriptedWeaver

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CORPUS = os.path.join(ROOT, "tests/fixtures/line3/bank2/data/fulllead_sents.jsonl")
PY = os.environ.get("VERA_TEST_PYTHON") or __import__("sys").executable
TOY = ["Ωa", "Ωb", "Ωc", "Ωd", "Ωe", "Ωf", "Ωg", "Ωh", "Ωi", "Ωj"]        # never a unit of the corpus (checked by the tests that use them)


def task(task_id, mode="constructed_allowed", lang="prose", tiers=None, text="織れ"):
    t = {"task_id": task_id, "text": text, "lang": lang, "mode": mode, "corpus": CORPUS}
    if tiers is not None:
        t["tiers"] = tiers
    return t


TASKS = [
    task("demo/tokyo_ca", "constructed_allowed", tiers=["WORD"]),
    task("demo/tokyo_ro", "record_only", tiers=["WORD"]),
    task("prose/ca", "constructed_allowed"),                  # RUN WORD CHAR
    task("prose/ro", "record_only"),
    task("code/ca", "constructed_allowed", lang="code"),
]


def server(tmp_path, stability="strict_npa", tasks=None, evidence="off", **kw):
    """evidence="off" by default: the older loom tests build their threads by hand (no evidence gate, the profile every ledger before LOOM-evidence has); the evidence tests pass "v1"."""
    return LoomServer(tasks if tasks is not None else TASKS, str(tmp_path / "runs"), (), stability, evidence=evidence, **kw)


def weaver(srv, task_id="prose/ca", run_id=None, model="test-weaver"):
    w = ScriptedWeaver(srv, task_id, model, run_id)
    w.begin()
    return w


def rows(run_dir):
    with open(os.path.join(str(run_dir), "ops.jsonl"), encoding="utf-8") as f:
        return [json.loads(ln) for ln in f if ln.strip()]
