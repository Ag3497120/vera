"""Compile one human project-frame file and print its typed record table."""
from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from verantyx.project_frame import FrameError, compile_frame, load_frame


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("frame", help="path to a strict human project-frame file")
    args = parser.parse_args(argv)
    try:
        spec = load_frame(args.frame)
        with tempfile.TemporaryDirectory(prefix=".frame-compile-", dir=ROOT) as scratch:
            compilation = compile_frame(spec, Path(scratch) / "memory.jsonl")
            print("id\tkind\tslots\twitness")
            for record in compilation.records:
                slots = json.dumps(record["slots"], ensure_ascii=False, sort_keys=True, separators=(",", ":"))
                witness = json.dumps(record.get("witness"), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
                print(f"{record['id']}\t{record['kind']}\t{slots}\t{witness}")
    except FrameError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
