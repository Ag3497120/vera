"""Mutate verantyx/agent_routing.py one way at a time and show that the tests notice.  The file is restored after each."""
import subprocess, sys
from pathlib import Path
W = Path("/Users/motonisihikoudai/Projects/vera-impl/wt/W2-h-S")
PY = "/Users/motonisihikoudai/vera-wiring/env/bin/python"
target = W / "verantyx" / "agent_routing.py"
original = target.read_text(encoding="utf-8")
MUTATIONS = {
    "verify is no longer independent of implement by default": (
        'if self.role == "verify" and explicit != NO_INDEPENDENCE:\n            roles.append("implement")',
        'if False:\n            roles.append("implement")'),
    "concurrency limit off by one": ("if busy >= agent.concurrency:", "if busy > agent.concurrency:"),
    "a tie is broken by the first head": (
        "    if len(heads) == 1:\n        return decided(heads[0]",
        "    if len(heads) >= 1:\n        return decided(heads[0]"),
    "same-lineage exclusion dropped": ("elif agent.lineage in used:", "elif False:"),
    "an unused prior role counts as satisfied": ("if not used:\n                problems.append", "if False:\n                problems.append"),
    "testimony not needed to agree (disagreement adopted)": (
        'if decision.status == "ADOPTED":\n        if decision.choice in heads:',
        'if decision.status in ("ADOPTED", "ABSTAINED"):\n        if (decision.choice or heads[0]) in heads:'),
    "precedence ignored": ("    survivors = _display(item.head for item in standing)", "    survivors = _display(item.head for item in headed)"),
    "default row consulted even when another rule has a head": (
        "    if not any(item.head for item in evaluations):\n        evaluations +=",
        "    if True:\n        evaluations +="),
}
try:
    for name, (old, new) in MUTATIONS.items():
        assert original.count(old) == 1, (name, original.count(old))
        target.write_text(original.replace(old, new), encoding="utf-8")
        done = subprocess.run([PY, "-m", "pytest", "-q", "-p", "no:cacheprovider", "-x", "--tb=no", "tests/test_agent_routing.py",
                               "tests/test_agent_routing_dsl.py"], cwd=W, capture_output=True, text=True,
                              env={"PYTHONPATH": str(W), "PYTHONDONTWRITEBYTECODE": "1", "PATH": "/usr/bin:/bin"})
        last = [l for l in done.stdout.splitlines() if l.strip()][-1]
        failing = [l for l in done.stdout.splitlines() if l.startswith("FAILED")][:1]
        print(f"{'CAUGHT' if done.returncode != 0 else 'NOT CAUGHT'} | {name} | {last} | {failing}")
finally:
    target.write_text(original, encoding="utf-8")
print("restored:", target.read_text(encoding="utf-8") == original)
