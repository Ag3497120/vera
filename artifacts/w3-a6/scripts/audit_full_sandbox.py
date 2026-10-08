#!/usr/bin/env python
"""Record sandbox self-check failures left by the final full pytest run."""
import json
from pathlib import Path

root = Path(__file__).resolve().parents[1]
bt = Path("/private/tmp/claude-501/-Users-motonisihikoudai-Projects-Verantyx-Vera-alpha/516c6003-3687-4f5e-a07a-ae6b080c15b8/scratchpad/W3-a6-impl/bt_full")
rows = []
for path in sorted(bt.rglob("ledger.jsonl")):
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if row.get("type") == "SANDBOX_CHECK":
            rows.append((path.relative_to(bt), row))
out = [f"bt_full ledger files: {sum(1 for _ in bt.rglob('ledger.jsonl'))}",
       f"SANDBOX_CHECK rows: {len(rows)}",
       f"SANDBOX_SELFCHECK_FAILED rows: {sum(r.get('error') == 'SANDBOX_SELFCHECK_FAILED' for _, r in rows)}"]
for path, row in rows:
    out.append(f"{path}: error={row.get('error')} exit_code={row.get('exit_code')} sandbox={row.get('sandbox')} stderr={row.get('stderr')}")
(root / "sandbox_full_evidence.txt").write_text("\n".join(out) + "\n", encoding="utf-8")
print("\n".join(out[:3]))
