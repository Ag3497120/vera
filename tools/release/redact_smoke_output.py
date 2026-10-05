"""smoke artifacts から作業機ごとの絶対 path を伏せる。"""
from __future__ import annotations

from pathlib import Path
import sys


def main(argv):
    source, destination = map(Path, argv[1:3])
    scratch, worktree = argv[3:5]
    value = source.read_text(encoding="utf-8", errors="replace")
    value = value.replace(scratch, "<SMOKE_TMP>").replace(worktree, "<WORKTREE>")
    destination.write_text(value, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
