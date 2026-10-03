"""Sanity of the strict O4 judge (round 2): run with the OLD rule (the anchor sentence is NOT skipped for stage ii) it must flag the r1 counterexamples.
Monkeypatch only; no file of the tree changes. Output: o4_old_rule_check.txt. Run with artifacts/w3-c/py.sh."""
import sys
from pathlib import Path
TREE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(TREE / 'tests' / 'observe'))
from verantyx import salience as SAL    # noqa: E402
orig = SAL.build_context
SAL.build_context = lambda ledger, neighbors=None, anchor_text=None: orig(ledger, neighbors, None)
import measure    # noqa: E402


class A:
    cases = str(TREE / 'tests' / 'observe' / 'data' / 'viewpoints.jsonl')
    workdir = str(TREE / 'artifacts' / 'w3-c' / 'work_old_rule')
    out = str(TREE / 'artifacts' / 'w3-c' / 'work_old_rule' / 'o4_old_rule.json')


Path(A.workdir).mkdir(parents=True, exist_ok=True)
print('exit', measure.o4_mode(A))
