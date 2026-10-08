from __future__ import annotations

from collections import Counter
from pathlib import Path
import json
import re

ROOT = Path(__file__).resolve().parents[3]
BASELINE = Path("/Users/motonisihikoudai/Projects/vera-impl/baselines/dev_6bc410d_failures.txt")
CURRENT = ROOT / "artifacts/w3-a7/current-r3/tests_full.txt"
OUT = CURRENT.parent


def failures(path: Path) -> set[str]:
    found: set[str] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("FAILED "):
            value = line[len("FAILED "):]
            value = re.sub(r" - .*\Z", "", value)
            found.add(value)
    return found


base = failures(BASELINE)
current = failures(CURRENT)
shared, new, resolved = base & current, current - base, base - current
summary = {
    "baseline_count": len(base),
    "current_count": len(current),
    "shared_count": len(shared),
    "new_count": len(new),
    "resolved_count": len(resolved),
    "delta": len(current) - len(base),
    "new_by_file": dict(sorted(Counter(x.split("::", 1)[0] for x in new).items())),
}
(OUT / "baseline_comparison_r3.json").write_text(
    json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
)
(OUT / "baseline_new_failures_r3.txt").write_text("".join(x + "\n" for x in sorted(new)), encoding="utf-8")
(OUT / "baseline_resolved_failures_r3.txt").write_text("".join(x + "\n" for x in sorted(resolved)), encoding="utf-8")
(OUT / "baseline_shared_failures_r3.txt").write_text("".join(x + "\n" for x in sorted(shared)), encoding="utf-8")
print(json.dumps(summary, ensure_ascii=False, indent=2))
