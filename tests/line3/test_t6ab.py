"""T6ab tests (L-200..): the default read-out is the T6z one again (common=None); proven on the 45 stored S300 RUN read-outs by
sha256; the exported user lists are blind (no gold / no grading keys)."""
import inspect
import json
import os
import subprocess
import sys

import pytest

from verantyx.line3 import readout as ro
from test_readout import ROOT

T6AB = os.path.join(ROOT, "experiments/line3/t6ab")
STORED = os.path.join(ROOT, "experiments/line3/t6z/results/S300_RUN_t6z_defaults.jsonl")


def test_default_common_is_none_and_the_option_is_kept():
    for f in (ro.read_answer,):
        assert inspect.signature(f).parameters["common"].default is None
    with pytest.raises(ValueError):
        ro.read_answer(None, None, (), common="union")


@pytest.mark.skipif(not os.path.exists(STORED), reason="stored T6z results not present")
def test_default_answer_object_equals_the_stored_t6z_one_by_sha256_on_all_readouts():
    r = subprocess.run([sys.executable, os.path.join(T6AB, "check_default.py")], capture_output=True, text=True,
                       cwd=T6AB, env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1", PYTHONPATH=ROOT), timeout=1800)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "45 / 45" in r.stdout


def test_exported_user_lists_are_blind():
    d = os.path.join(T6AB, "user_lists")
    if not os.path.isdir(d):
        pytest.skip("not exported")
    files = [f for f in os.listdir(d) if f.endswith(".json")]
    assert len(files) == 20
    for f in files:
        o = json.load(open(os.path.join(d, f), encoding="utf-8"))
        assert set(o) == {"question", "entries"}
        for i, e in enumerate(o["entries"]):
            assert set(e) == {"index", "words", "arrangements", "sentence"} and e["index"] == i
