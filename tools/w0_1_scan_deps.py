#!/usr/bin/env python3
"""Scan a tree for dependencies on things outside it (machine paths, home dir, .git, subprocess, VERA_* env).

Usage: w0_1_scan_deps.py <tree-root>
Output, one finding per line:  <relative file>:<line>: <kind>: <matched text>

Read-only. Kinds:
  ABS_USERS      a literal /Users/ path
  ABS_HOMEBREW   a literal /opt/homebrew path
  ABS_USR_LOCAL  a literal /usr/local path
  ABS_TMP        a literal /tmp/ path
  HOME_API       Path.home() / expanduser / os.path.expanduser
  TILDE_PATH     a quoted path starting with ~/
  GIT_DEP        a reference to .git or a git subprocess
  SUBPROCESS     subprocess / os.system / os.popen use (child may not inherit sys.executable / PYTHONPATH)
  VERA_ENV       an environment variable named VERA_* (a default may point outside the tree)
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

SCAN_DIRS = ("tests", "tools", "verantyx", "demo", "experiments")
PATTERNS = (
    ("ABS_USERS", re.compile(r"/Users/[^\s\"'`)\]]*")),
    ("ABS_HOMEBREW", re.compile(r"/opt/homebrew[^\s\"'`)\]]*")),
    ("ABS_USR_LOCAL", re.compile(r"/usr/local[^\s\"'`)\]]*")),
    ("ABS_TMP", re.compile(r"(?<![A-Za-z0-9_.])/tmp/[^\s\"'`)\]]*")),
    ("HOME_API", re.compile(r"Path\.home\(\)|expanduser")),
    ("TILDE_PATH", re.compile(r"[\"']~/[^\"']*[\"']")),
    ("GIT_DEP", re.compile(r"\.git\b(?!hub|ignore|attributes)|\"git\"|'git'")),
    ("SUBPROCESS", re.compile(r"\bsubprocess\.(?:run|Popen|call|check_call|check_output)\b|\bos\.system\b|\bos\.popen\b")),
    ("VERA_ENV", re.compile(r"\bVERA_[A-Z0-9_]+\b")),
)
SKIP_PARTS = {"__pycache__", "artifacts", ".git"}


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(__doc__, file=sys.stderr)
        return 2
    root = Path(argv[1]).resolve()
    count = 0
    for sub in SCAN_DIRS:
        base = root / sub
        if not base.is_dir():
            continue
        for path in sorted(base.rglob("*.py")):
            if SKIP_PARTS & set(path.relative_to(root).parts) or path.name == Path(__file__).name:
                continue
            try:
                lines = path.read_text(encoding="utf-8").splitlines()
            except (OSError, UnicodeDecodeError):
                print(f"{path.relative_to(root)}:0: UNREADABLE: skipped")
                continue
            for number, line in enumerate(lines, 1):
                for kind, pattern in PATTERNS:
                    for match in pattern.finditer(line):
                        print(f"{path.relative_to(root)}:{number}: {kind}: {match.group(0)}")
                        count += 1
    print(f"# findings: {count}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
