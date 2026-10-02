"""Read the P4 corpus sovereigns without merging their evidence.

The SQLite indexes are built by tools/build_p4_corpus_index.py. They preserve
source, scene, and consecutive row order, and every row says where it came from
(source file and physical line). Rows are *generated text* (origin="generated"):
sentences a model wrote, not testimony about the world. Runtime connections are
read-only.

Absence of an index is not absence of a match. Every lookup returns a list that
carries a ``state``:

    FOUND / NO_MATCH                 the index was searched
    UNKNOWN_NO_INDEX                 the index directory is missing or holds no database
    UNKNOWN_FAMILY_DB_MISSING        other databases exist but not this family's
    UNKNOWN_INDEX_UNREADABLE         the database could not be opened or has no tables
    UNKNOWN_INDEX_REBUILD_REQUIRED   an index in an older format without provenance
    UNKNOWN_QUERY_NOT_SEARCHED       the query was empty or longer than 80 characters

The UNKNOWN_* kinds are ``CorpusUnknown`` (always empty), so existing code that
iterates, takes len() or tests ``if not rows`` behaves as before.
"""
from __future__ import annotations

import os
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


INDEX = Path(os.environ.get("VERA_P4_INDEX", Path(__file__).resolve().parents[1] / "build/p4"))
FAMILIES = ("local", "pro", "code", "conversation", "general_qa", "code_qa",
            "figurative_commonsense", "narrative", "paraphrase_entail")
MAX_QUERY = 80
INDEX_AVAILABLE = "INDEX_AVAILABLE"
GENERATED = "generated"
_COLUMNS = "r.id,r.text,r.source,r.scene,r.grp,r.sha,r.source_file,r.line,r.kind,r.origin,r.generator"


def basis_origin(sources: Iterable) -> str | None:
    """"generated" when any cited source is a corpus sentence (origin == "generated"), else None.

    The one place that defines the rule for a reply's top-level ``basis_origin``: a sentence a
    model wrote is a generated example, never testimony. Entries that are not dicts are ignored.
    """
    return GENERATED if any(isinstance(s, dict) and s.get("origin") == GENERATED for s in sources) else None


def basis_mark(sources: Iterable) -> dict:
    """``{"basis_origin": "generated"}`` or ``{}``, to be spread into a reply (the key is absent otherwise)."""
    origin = basis_origin(sources)
    return {} if origin is None else {"basis_origin": origin}


def default_root() -> Path:
    """The index directory chosen now (not at import): VERA_P4_INDEX, else <tree>/build/p4."""
    env = os.environ.get("VERA_P4_INDEX")
    return Path(env) if env else Path(__file__).resolve().parents[1] / "build/p4"


@dataclass(frozen=True)
class Witness:
    family: str
    id: int
    text: str
    source: str
    scene: str
    group: str
    sha: str
    source_file: str = ""
    line: int = 0
    kind: str = ""
    origin: str = GENERATED
    generator: str = "codex"

    def cite(self) -> dict:
        return {"family": self.family, "source": self.source,
                "text": self.text, "sha": self.sha, "scene": self.scene,
                "origin": self.origin, "generator": self.generator,
                "source_file": self.source_file, "line": self.line}


class CorpusHits(list):
    """Witnesses plus how they came about: ``state`` is FOUND or NO_MATCH."""

    def __init__(self, items: Iterable[Witness] = (), *, family: str = "", root: Path | None = None,
                 state: str | None = None, reason: str = ""):
        super().__init__(items)
        self.family = family
        self.root = root
        self.reason = reason
        self.state = state or ("FOUND" if len(self) else "NO_MATCH")


class CorpusUnknown(CorpusHits):
    """Nothing was searched; ``state`` says why. Always empty, never confusable with NO_MATCH."""

    def __init__(self, state: str, *, family: str = "", root: Path | None = None, reason: str = ""):
        super().__init__((), family=family, root=root, state=state, reason=reason)


class Corpus:
    def __init__(self, root: Path | str | None = None):
        self.root = Path(root) if root is not None else default_root()
        self._connections: dict[str, sqlite3.Connection] = {}

    def _open(self, family: str) -> tuple[sqlite3.Connection | None, str, str]:
        """(connection, state, reason). state is INDEX_AVAILABLE or an UNKNOWN_* type."""
        if family not in FAMILIES:
            raise ValueError(family)
        if family in self._connections:
            return self._connections[family], INDEX_AVAILABLE, ""
        path = self.root / (family + ".db")
        if not path.exists():
            if not self.root.is_dir() or not any(self.root.glob("*.db")):
                return None, "UNKNOWN_NO_INDEX", f"no index database under {self.root}"
            return None, "UNKNOWN_FAMILY_DB_MISSING", f"{family}.db is not in {self.root}"
        con = None
        try:
            con = sqlite3.connect(f"file:{path}?mode=ro", uri=True, check_same_thread=False)
            meta = dict(con.execute("SELECT key,value FROM meta"))
            con.execute("SELECT 1 FROM rows LIMIT 1").fetchall()
        except sqlite3.Error as err:
            if con is not None:
                con.close()
            return None, "UNKNOWN_INDEX_UNREADABLE", f"{path}: {err}"
        if "format" not in meta:
            con.close()
            return None, "UNKNOWN_INDEX_REBUILD_REQUIRED", f"{path} has no meta.format (old index)"
        self._connections[family] = con
        return con, INDEX_AVAILABLE, ""

    def connection(self, family: str) -> sqlite3.Connection | None:
        """The read-only connection, or None when the index is unavailable (see status())."""
        return self._open(family)[0]

    def status(self, family: str) -> str:
        """INDEX_AVAILABLE or the UNKNOWN_* state a lookup would return. Searches nothing."""
        return self._open(family)[1]

    @staticmethod
    def _row(family: str, row: tuple) -> Witness:
        return Witness(family, *row)

    def _unknown(self, family: str, state: str, reason: str) -> CorpusUnknown:
        return CorpusUnknown(state, family=family, root=self.root, reason=reason)

    def search(self, term: str, family: str = "local", limit: int = 100,
               *, scene: bool = False) -> CorpusHits:
        con, state, reason = self._open(family)
        term = term.strip()
        if not term or len(term) > MAX_QUERY:
            return self._unknown(family, "UNKNOWN_QUERY_NOT_SEARCHED",
                                 "empty query" if not term else f"query longer than {MAX_QUERY} characters")
        if con is None:
            return self._unknown(family, state, reason)
        column = "scene" if scene else "text"
        # FTS5's trigram LIKE index accelerates three-character and longer
        # terms. Short words use a bounded ordinary scan on this sovereign.
        sql = (f"SELECT {_COLUMNS} FROM search f "
               f"JOIN rows r ON r.id=f.rowid WHERE f.{column} LIKE ? LIMIT ?")
        return CorpusHits((self._row(family, row) for row in con.execute(sql, ("%" + term + "%", limit))),
                          family=family, root=self.root)

    def neighbors(self, witness: Witness, before: int = 0, after: int = 5) -> CorpusHits:
        con, state, reason = self._open(witness.family)
        if con is None:
            return self._unknown(witness.family, state, reason)
        rows = con.execute(
            f"SELECT {_COLUMNS} FROM rows r WHERE r.id BETWEEN ? AND ? "
            "AND r.grp=? ORDER BY r.id",
            (max(1, witness.id - before), witness.id + after, witness.group),
        )
        return CorpusHits((self._row(witness.family, row) for row in rows),
                          family=witness.family, root=self.root)

    def search_scene(self, focus: str, modifiers: Iterable[str], family: str = "local",
                     limit: int = 180) -> CorpusHits:
        con, state, reason = self._open(family)
        if not focus:
            return self._unknown(family, "UNKNOWN_QUERY_NOT_SEARCHED", "empty focus")
        if con is None:
            return self._unknown(family, state, reason)
        mods = [m for m in modifiers if m and m != focus][:2]
        where = " AND ".join(["f.scene LIKE ?", "f.text LIKE ?"] + ["f.scene LIKE ?"] * len(mods))
        params = ["%" + focus + "%", "%" + focus + "%"] + ["%" + m + "%" for m in mods]
        sql = (f"SELECT {_COLUMNS} FROM search f "
               f"JOIN rows r ON r.id=f.rowid WHERE {where} LIMIT ?")
        return CorpusHits((self._row(family, row) for row in con.execute(sql, (*params, limit))),
                          family=family, root=self.root)

    def distinct_sources(self, rows: Iterable[Witness]) -> list[Witness]:
        out, seen = [], set()
        for row in rows:
            if row.group not in seen:
                out.append(row)
                seen.add(row.group)
        return out
