"""verantyx.accel -- the accelerator of the memory structure (owner decision, ops/decisions/2026-10-06_line3_faithful_build.md: 「cで書いて高速化」; L-PUB-160..).

  VERA_ACCEL=py    (default) the plain code, untouched: every function below is the reference.
  VERA_ACCEL=inc   the incremental algorithms in pure Python (inc.py): the corpus of a write is the corpus of the rows before it plus ONE appended row (space, adhesion tables, caches carried),
                   the canonical row lines and the loom state's canonical JSON are memoised under a fingerprint of everything they read.
  VERA_ACCEL=c     `inc` + the postings kernels in C (vxcore.c, loaded by cbind.py from a library `python -m verantyx.accel.build` made; there is NO silent fallback to Python).

Every mode gives the same bytes (stores, ledgers, index_sha); the agreement of the modes is the correctness check (tests/line3/test_accel*.py).  `VERA_ACCEL_CHECK=1` makes the
accelerated functions also run the plain ones and raise on the first difference (a debugging aid and the differential tests' engine; it is as slow as `py`).

`install(memory)` is the one dispatch hook (verantyx/loom/memory.py calls it once, at the end of the module): it replaces `memory.build_corpus`, `memory.rows_bytes`,
`MemRun.mem_state_sha` and, in memcross, the per-prefix `Corpus` / `_rows_bytes` of `build_index`, by wrappers that run the plain function when the mode is `py`.  Before it replaces a function
it checks the sha256 of the function's source against the one pinned here and raises AccelDrift on a difference: a changed reference must be re-read, then re-pinned.

This module imports nothing heavy; it never starts a process and never reads a clock.
"""
from __future__ import annotations

import hashlib
import inspect
import os
from typing import Any, Callable

MODES = ("py", "inc", "c")

# sha256 (first 16 hex) of inspect.getsource() of the reference functions the wrappers re-implement.  `verantyx.loom.memory._ACCEL_PINS()` returns the current values.
PINS = {
    "memory.build_corpus": "d9781472f66286ac",
    "memory.rows_bytes": "63e37c841a8cfd32",
    "memory.MemRun.mem_state_sha": "313f02297bebb7a3",
    "memcross._rows_bytes": "621921f6239888d1",
}


class AccelDrift(RuntimeError):
    pass


def mode() -> str:
    v = os.environ.get("VERA_ACCEL", "py") or "py"
    if v not in MODES:
        raise ValueError("VERA_ACCEL must be one of %s, not %r" % (MODES, v))
    return v


def check() -> bool:
    return os.environ.get("VERA_ACCEL_CHECK", "") not in ("", "0")


def src_pin(fn: Callable[..., Any]) -> str:
    return hashlib.sha256(inspect.getsource(fn).encode("utf-8")).hexdigest()[:16]


def _same(name: str, a: Any, b: Any) -> None:
    if a != b:
        raise AssertionError("VERA_ACCEL_CHECK: %s differs between the plain code and the accelerated code" % name)


def install(memory: Any) -> None:
    """The dispatch hook.  Idempotent."""
    if getattr(memory, "_ACCEL_INSTALLED", False):
        return
    memory._ACCEL_INSTALLED = True
    from verantyx.accel import _wrap
    _wrap.install(memory)
