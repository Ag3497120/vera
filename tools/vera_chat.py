"""Text chat over a local document folder through :class:`VeraSystem`."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, TextIO

from verantyx.vera_system import VeraSystem, VeraSystemResult


def _display(value: Any) -> str:
    if isinstance(value, VeraSystemResult):
        value = value.as_dict()
    elif hasattr(value, "as_dict"):
        value = value.as_dict()
    elif hasattr(value, "to_dict"):
        value = value.to_dict()
    return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)


def chat_loop(system: VeraSystem, *, input_stream: TextIO = sys.stdin,
              output_stream: TextIO = sys.stdout) -> None:
    """Read one line at a time and print its typed capability result."""
    for line in input_stream:
        if line.strip().casefold() in {"exit", "quit", "終了"}:
            break
        result = system.dispatch(line)
        print(_display(result), file=output_stream)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Chat over a local Vera document folder")
    parser.add_argument("document_folder", type=Path,
                        help="folder containing the source documents")
    parser.add_argument("--frame", type=Path, help="optional human-authored project frame")
    parser.add_argument("--memory", type=Path, help="optional typed memory path for the frame")
    args = parser.parse_args(argv)

    with VeraSystem(args.document_folder, frame=args.frame, memory=args.memory) as system:
        chat_loop(system)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
