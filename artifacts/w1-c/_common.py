"""Shared constants and small helpers for the W1-c verification scripts (read-only on corpus and index)."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

HERE = Path(__file__).resolve().parent
CORPUS = Path("/Users/motonisihikoudai/vera-codex-corpus")
IDX = Path("/Users/motonisihikoudai/Projects/vera-impl/build/p4-W1c")
SEED = 20261002
FAMS = ("pro", "code", "conversation", "general_qa", "code_qa",
        "figurative_commonsense", "narrative", "paraphrase_entail")
HELDOUT = {
    "pro": [],
    "code": ["code/heldout/items.jsonl", "even/code/heldout/items.jsonl"],
    "conversation": ["conversation/heldout/utterances.jsonl", "even/conversation/heldout/utterances.jsonl"],
    "general_qa": ["general_qa/heldout/records.jsonl"],
    "code_qa": ["code_qa/heldout/records.jsonl"],
    "figurative_commonsense": ["figurative_commonsense/heldout/records.jsonl"],
    "narrative": ["narrative/heldout/records.jsonl"],
    "paraphrase_entail": ["paraphrase_entail/heldout/records.jsonl"],
}


def db(family: str) -> sqlite3.Connection:
    return sqlite3.connect(f"file:{IDX / (family + '.db')}?mode=ro", uri=True)


def raw_lines_at(root: Path, rel: str, wanted: set[int]) -> dict[int, bytes]:
    """Physical lines (1-based, cut on b"\\n" only) of one file, found in a single binary pass."""
    out: dict[int, bytes] = {}
    if not wanted:
        return out
    top = max(wanted)
    n = 0
    carry = b""
    with (root / rel).open("rb") as handle:
        while n < top:
            chunk = handle.read(8 << 20)
            if not chunk:
                break
            pieces = (carry + chunk).split(b"\n")
            carry = pieces.pop()
            for piece in pieces:
                n += 1
                if n in wanted:
                    out[n] = piece
                if n >= top:
                    break
        else:
            pass
        if n < top and carry:
            n += 1
            if n in wanted:
                out[n] = carry
    return out


def dump(path: Path, obj) -> None:
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
