"""Read the four P4 corpus sovereigns without merging their evidence.

The optional SQLite indexes are built by tools/build_p4_corpus_index.py. They
preserve source, scene, and consecutive row order; they contain no generated
answers or inferred frames. Runtime connections are read-only.
"""
from __future__ import annotations

import os
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


INDEX = Path(os.environ.get("VERA_P4_INDEX", Path(__file__).resolve().parents[1] / "build/p4"))
FAMILIES = ("local", "pro", "code", "conversation")


@dataclass(frozen=True)
class Witness:
    family: str
    id: int
    text: str
    source: str
    scene: str
    group: str
    sha: str

    def cite(self) -> dict:
        return {"family": self.family, "source": self.source,
                "text": self.text, "sha": self.sha, "scene": self.scene}


class Corpus:
    def __init__(self, root: Path = INDEX):
        self.root = Path(root)
        self._connections: dict[str, sqlite3.Connection] = {}

    def connection(self, family: str) -> sqlite3.Connection | None:
        if family not in FAMILIES:
            raise ValueError(family)
        if family not in self._connections:
            path = self.root / (family + ".db")
            if not path.exists():
                return None
            self._connections[family] = sqlite3.connect(
                f"file:{path}?mode=ro", uri=True, check_same_thread=False)
        return self._connections[family]

    @staticmethod
    def _row(family: str, row: tuple) -> Witness:
        return Witness(family, *row)

    def search(self, term: str, family: str = "local", limit: int = 100,
               *, scene: bool = False) -> list[Witness]:
        con = self.connection(family)
        term = term.strip()
        if con is None or not term or len(term) > 80:
            return []
        column = "scene" if scene else "text"
        # FTS5's trigram LIKE index accelerates three-character and longer
        # terms. Short words use a bounded ordinary scan on this sovereign.
        sql = (f"SELECT r.id,r.text,r.source,r.scene,r.grp,r.sha FROM search f "
               f"JOIN rows r ON r.id=f.rowid WHERE f.{column} LIKE ? LIMIT ?")
        return [self._row(family, row) for row in con.execute(sql, ("%" + term + "%", limit))]

    def neighbors(self, witness: Witness, before: int = 0, after: int = 5) -> list[Witness]:
        con = self.connection(witness.family)
        if con is None:
            return []
        rows = con.execute(
            "SELECT id,text,source,scene,grp,sha FROM rows WHERE id BETWEEN ? AND ? "
            "AND grp=? ORDER BY id",
            (max(1, witness.id - before), witness.id + after, witness.group),
        )
        return [self._row(witness.family, row) for row in rows]

    def search_scene(self, focus: str, modifiers: Iterable[str], family: str = "local",
                     limit: int = 180) -> list[Witness]:
        con = self.connection(family)
        if con is None or not focus:
            return []
        mods = [m for m in modifiers if m and m != focus][:2]
        where = " AND ".join(["f.scene LIKE ?", "f.text LIKE ?"] + ["f.scene LIKE ?"] * len(mods))
        params = ["%" + focus + "%", "%" + focus + "%"] + ["%" + m + "%" for m in mods]
        sql = ("SELECT r.id,r.text,r.source,r.scene,r.grp,r.sha FROM search f "
               f"JOIN rows r ON r.id=f.rowid WHERE {where} LIMIT ?")
        return [self._row(family, row) for row in con.execute(sql, (*params, limit))]

    def distinct_sources(self, rows: Iterable[Witness]) -> list[Witness]:
        out, seen = [], set()
        for row in rows:
            if row.group not in seen:
                out.append(row)
                seen.add(row.group)
        return out
