"""Run a project frame through the conduct entry (thin wrapper over ``verantyx.cli conduct``).

    python tools/run_project.py --frame F --repo R --adapter codex|claude|fake [--dry-run] ...

The old ``--adapter command:<exe>`` and the JSONL-only frame loader were removed: the
loader looked for a ``write_allowlist`` slot in POLICY records, which the POLICY kind
(slots ``subject`` and ``answer`` only) cannot hold, so it could never succeed.  The frame
now declares its allowlist in a ``[write_allowlist]`` section (see docs/CONDUCT_ENTRY.md).
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from verantyx.cli import main as cli_main  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    return cli_main(["conduct", *(sys.argv[1:] if argv is None else argv)])


if __name__ == "__main__":
    raise SystemExit(main())
