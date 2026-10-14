"""A run of the harness is a pure function of its inputs: the ledger bytes do not depend on PYTHONHASHSEED (0 / 1 / 12345), and replay finds them identical."""
import os
import subprocess
import sys

from fakes import DOCS

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PY = sys.executable

SCRIPT = r'''
import sys, os
sys.path.insert(0, %(root)r); sys.path.insert(0, os.path.join(%(root)r, "tests", "harness"))
from fakes import FakeOpenAI, ASK_TURNS, QUESTION
from verantyx.harness import runner as rn
from verantyx.harness.backends import make_backend
clean = [[b for b in t if b[0] != "text"] for t in ASK_TURNS]
a = rn.ask(QUESTION, sys.argv[1], make_backend("openai", "fake-gpt", client=FakeOpenAI(clean)), sys.argv[2], run_id="fixed-run")
print(a.status, a.text)
'''


def test_ledger_bytes_do_not_depend_on_the_hash_seed(tmp_path):
    d = tmp_path / "docs"
    d.mkdir()
    for k, v in DOCS.items():
        (d / k).write_text(v, encoding="utf-8")
    out = {}
    for seed in ("0", "1", "12345"):
        runs = tmp_path / ("runs_" + seed)
        p = subprocess.run([PY, "-c", SCRIPT % {"root": ROOT}, str(d), str(runs)], env=dict(os.environ, PYTHONHASHSEED=seed, PYTHONDONTWRITEBYTECODE="1"), cwd=str(tmp_path),
                           capture_output=True, text=True, timeout=300)
        assert p.returncode == 0 and p.stdout.strip() == "answered 松風庵", p.stderr
        out[seed] = (open(runs / "fixed-run" / "ops.jsonl", "rb").read(), open(runs / "fixed-run" / "HEAD").read())
    assert out["0"] == out["1"] == out["12345"]
