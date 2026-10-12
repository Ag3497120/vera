"""MEM-a: the guards that keep the memory space and a base corpus apart (OP-MEM-1 (a), L-MEM-02; docs/LINE3_LOOM_MEMORY_DESIGN.md 0.1, 9.2).

The model's own sentences are the evidence of a SEPARATE space (N-16): each is stored as `{sent, source, kind}` with `source = "mem:<store>/<session>#<i>[:user]"`.  Two
refusals, one each way, so the two kinds of corpus can never be mixed:
  not_memory_row    a MEMORY space refuses a row whose source is not a `mem:` source (`check_memory_rows`, used by every corpus the memory builds)
  memory_in_base    the LOOM refuses a corpus that is not a memory corpus but holds a `mem:` row (`assert_not_memory_corpus`, called by `LoomServer.begin` and by
                    `ledger.replay`): a base corpus never contains the model's memory, and the model's memory never reads as a record of a base corpus.
Pure functions of the bytes / rows; no file, no clock.  A corpus without a `mem:` source passes through the second guard untouched, so every stored run is as it was.
"""
from __future__ import annotations

import json
import re
from typing import Iterable, Optional, Tuple

from verantyx.loom.state import Refuse

MEM_PREFIX = "mem:"
MEM_KINDS: Tuple[str, ...] = ("base", "memory_answer")                      # the two kinds OP-MEM-1 allows a memory row (space.KINDS is closed: L-40)
STORE_ID_RX = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,31}$")
SOURCE_RX = re.compile(r"^mem:([A-Za-z0-9][A-Za-z0-9._-]{0,31})/([0-9]+)#([0-9]+)(:user)?$")


def make_source(store_id: str, session_no: int, i: int, role: str = "model") -> str:
    return "%s%s/%d#%d%s" % (MEM_PREFIX, store_id, session_no, i, ":user" if role == "user" else "")


def parse_source(source: str) -> Optional[Tuple[str, int, int, str]]:
    """(store_id, session_no, i, role) of a memory source, else None."""
    m = SOURCE_RX.match(source) if isinstance(source, str) else None
    return None if m is None else (m.group(1), int(m.group(2)), int(m.group(3)), "user" if m.group(4) else "model")


def check_memory_rows(rows: Iterable[dict]) -> None:
    """A memory space holds nothing but memory rows: `Refuse("not_memory_row", {"i"})` at the first row that is not one."""
    for i, r in enumerate(rows):
        if not (isinstance(r, dict) and isinstance(r.get("sent"), str) and isinstance(r.get("source"), str) and parse_source(r["source"]) is not None
                and r.get("kind", "base") in MEM_KINDS):
            raise Refuse("not_memory_row", {"i": i})


def holds_memory_rows(data: bytes) -> bool:
    """Does a corpus (jsonl bytes) hold a row whose source starts with `mem:`?  The substring is checked first, so a corpus without it costs one scan."""
    if MEM_PREFIX.encode() not in data:
        return False
    for line in data.decode("utf-8", errors="replace").splitlines():
        if MEM_PREFIX not in line:
            continue
        try:
            r = json.loads(line)
        except ValueError:
            continue
        if isinstance(r, dict) and isinstance(r.get("source"), str) and r["source"].startswith(MEM_PREFIX):
            return True
    return False


def assert_not_memory_corpus(data: bytes) -> None:
    if holds_memory_rows(data):
        raise Refuse("memory_in_base", {"reason": "the corpus holds a mem: row; a memory corpus is read only by a memory session"})
