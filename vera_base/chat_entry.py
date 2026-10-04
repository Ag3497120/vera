"""``vera-chat``: round5 を既定にする薄い CLI 入口。"""

from __future__ import annotations

import sys
from collections.abc import Sequence


def main(argv: Sequence[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if not any(arg == "--mode" or arg.startswith("--mode=") for arg in args):
        args[:0] = ["--mode", "round5"]
    from verantyx.cli import main as vera_main

    return vera_main(["chat", *args])


if __name__ == "__main__":
    raise SystemExit(main())
