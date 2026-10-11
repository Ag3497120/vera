"""LOOM-code: reading a fixture repo into a CodeIndex (L-LOOM-70).

The one place (next to the ledger and the server) that touches files for the CODE tier.  `reader(path) -> bytes` is the caller's door:
the server passes `Sandbox.read_bytes` (so every file is checked against the sandbox roots), a replay passes its `loader`.  The listing
is sorted and relative, so the index does not depend on the directory order, the machine or the folder's absolute path.
"""
from __future__ import annotations

from pathlib import Path
from typing import Callable, Dict, List

from verantyx.loom.code import CodeIndex, indexed_path


ROOT_PROBE = ".loom-root-probe"


def check_root(base: Path, reader: Callable[[str], bytes]) -> None:
    """L-LOOM-81: the ROOT goes through the reader too.  A sandbox refuses a path outside its roots before it touches the file, so asking
    for a name that does not exist under `base` raises SandboxError for a root it does not allow, and FileNotFoundError for one it does
    (swallowed here).  Without it a root with no `*.py` file was never read, and `fixture_outside_sandbox` could not fire.  A root that is
    not a folder is an OSError (`fixture_unreadable`)."""
    try:
        reader(str(base / ROOT_PROBE))
    except FileNotFoundError:
        pass
    if not base.is_dir():
        raise NotADirectoryError(str(base))


def list_files(root) -> List[str]:
    """The relative paths (posix, sorted) of the files of `root` that the record index holds."""
    base = Path(root).resolve()
    rels = [p.relative_to(base).as_posix() for p in base.rglob("*.py") if p.is_file()]
    return sorted(r for r in rels if indexed_path(r))


def read_files(root, reader: Callable[[str], bytes]) -> Dict[str, bytes]:
    base = Path(root).resolve()
    check_root(base, reader)
    return {rel: reader(str(base / rel)) for rel in list_files(base)}


def build_index(root, reader: Callable[[str], bytes]) -> CodeIndex:
    """Raises SandboxError (from `reader`), OSError (unreadable) or ValueError (a file does not tokenize / parse)."""
    return CodeIndex(read_files(root, reader))
