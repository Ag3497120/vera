"""Reproduce one unchanged conductor failure from review r1 and print its measured outcome."""
from __future__ import annotations

import json
from pathlib import Path
import runpy
import sys


TREE = Path(__file__).resolve().parents[3]
BASE = Path("/private/tmp/claude-501/-Users-motonisihikoudai-Projects-Verantyx-Vera-alpha/516c6003-3687-4f5e-a07a-ae6b080c15b8/scratchpad/codex-w5f-r2-i6-sample")
sys.path[:0] = [str(TREE), str(TREE / "tests")]
module = runpy.run_path(str(TREE / "tests/test_conduct_routing.py"))
chooser, prompts = module["fake_chooser"](["CodexImplB"])
run = module["routed_execute"](
    BASE / "run",
    module["routed_frame"](module["tie_conduct_spec"]()),
    routing_chooser=chooser,
)
print("PROMPT_COUNT", len(prompts))
print("OUTCOME", run.out.get("outcome"), "VERDICT", run.out.get("verdict"))
print("RESULT", json.dumps(run.out, ensure_ascii=False, sort_keys=True))
print("ROWS", json.dumps(run.rows, ensure_ascii=False, sort_keys=True))
