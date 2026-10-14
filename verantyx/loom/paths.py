"""LOOM-path (L-LOOM-158..): how a run's corpus (and fixture) is FOUND again, without trusting an absolute path.

meta.json is outside the hash chain and used to record the ABSOLUTE path of the corpus of the checkout the run was made in; once that
checkout is gone, `verify` / `replay` / `score` needed `--corpus`.  The chain already records the thing that identifies the corpus: the
sha256 of its bytes (`begin` row, header.corpus_sha).  So the path is only a pointer and the sha decides (it always did: a wrong file
is `corpus_sha_mismatch`).  This module only builds the LIST of places to look, in order:

  1. what meta.json says: a repo-relative path is joined to the repository root; an absolute path is used as it stands;
  2. the same path under THIS repository root (the worktree prefix of an old checkout stripped: the longest tail of the recorded
     path, two components or more, that exists under the root);
  3. a small registry of the corpora the repository ships (KNOWN_CORPORA, relative to the root).

ledger.replay reads the candidates in that order through its loader (so the sandbox still decides what may be read) and takes the first
whose sha256 is the recorded one.  Nothing is written, and stored meta.json files are never rewritten.

New runs record `corpus` RELATIVE to the repository root (forward slashes) plus `corpus_sha`; a corpus outside the root (a temp folder)
cannot be relative and keeps its absolute path.  The `fixture` of a code run follows the same rule.  No file is opened here.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import List, Optional

REPO_ROOT = Path(__file__).resolve().parents[2]

# The corpora this repository ships (its test fixtures).  The research tree kept them under experiments/line3/...; the ledgers recorded there name that path, and the sha decides anyway.
KNOWN_CORPORA = (
    "tests/fixtures/line3/bank2/data/fulllead_sents.jsonl",
    "tests/fixtures/line3/data/S300.jsonl",
    "tests/fixtures/line3/data/S300_fulllead.jsonl",
    "tests/fixtures/line3/data/S3000.jsonl",
)


def rel_to_root(path, root: Path = REPO_ROOT) -> str:
    """The path as meta.json stores it: relative to the repository root (forward slashes) when it lies inside the root, else the resolved absolute path."""
    p = Path(path).resolve()
    try:
        return p.relative_to(Path(root).resolve()).as_posix()
    except ValueError:
        return str(p)


def _under_root(path: str, root: Path) -> str:
    return path if os.path.isabs(path) else str(Path(root) / path)


def _tails_under_root(path: str, root: Path) -> List[str]:
    """The same path in THIS checkout: every tail of the recorded path with at least two components that exists under the root, longest first."""
    parts = [x for x in Path(path).parts if x not in (os.sep, "")]
    out: List[str] = []
    for i in range(len(parts) - 1):
        cand = Path(root).joinpath(*parts[i:])
        if cand.exists():
            out.append(str(cand))
    return out


def candidates(recorded: Optional[str], root: Path = REPO_ROOT, registry=KNOWN_CORPORA, with_registry: bool = True) -> List[str]:
    """The places to look for a file meta.json names as `recorded`, in order, without duplicates (as strings)."""
    out: List[str] = []

    def add(p: str) -> None:
        if p not in out:
            out.append(p)
    if recorded:
        add(_under_root(recorded, root))
        for t in _tails_under_root(_under_root(recorded, root), root):
            add(t)
    if with_registry:
        for r in registry:
            add(str(Path(root) / r))
    return out


def fixture_path(recorded: Optional[str], root: Path = REPO_ROOT) -> Optional[str]:
    """The fixture folder of a code run: as recorded (a relative path against the root); when an absolute one does not exist, its tail under the root."""
    if not recorded:
        return recorded
    first = _under_root(recorded, root)
    if os.path.exists(first):
        return first
    tails = _tails_under_root(first, root)
    return tails[0] if tails else first
