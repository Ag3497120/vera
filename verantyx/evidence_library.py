"""Independent answer-sentence sovereigns with conductive routing and capped frames."""
from __future__ import annotations

import hashlib
import json
import pickle
import re
import sqlite3
import time
from collections import defaultdict
from pathlib import Path
from typing import Iterable

from . import conduct_tree
from .answer_slots import index_slot, keys, nouns, read_slot
from .cross_store import CrossStore
from .hierarchy import Node


LEAF_CAP = 400
FRAME_CAP = 2000
FORMAT = 1


class EvidenceLibrary:
    def __init__(self, directory: str | Path, family: str):
        self.directory = Path(directory)
        self.family = family
        self.con = sqlite3.connect(f"file:{self.directory / 'evidence.db'}?mode=ro", uri=True)
        self.con.row_factory = sqlite3.Row
        self.root = None
        self._mtime = 0
        self._refresh()

    def _refresh(self) -> None:
        route = self.directory / "evidence.pkl"
        if route.exists() and route.stat().st_mtime_ns != self._mtime:
            with route.open("rb") as stream:
                version, self.root = pickle.load(stream)
            if version != FORMAT:
                raise ValueError("unsupported evidence format")
            self._mtime = route.stat().st_mtime_ns

    @staticmethod
    def _schema(con: sqlite3.Connection) -> None:
        con.executescript("""
            CREATE TABLE IF NOT EXISTS rows(id INTEGER PRIMARY KEY, sha TEXT UNIQUE,
                text TEXT NOT NULL, context TEXT NOT NULL, slot TEXT NOT NULL,
                subject TEXT NOT NULL, source TEXT NOT NULL, independent TEXT NOT NULL,
                leaf TEXT NOT NULL, position INTEGER NOT NULL);
            CREATE TABLE IF NOT EXISTS frames(predicate TEXT, subject TEXT, rid INTEGER,
                PRIMARY KEY(predicate,subject,rid)) WITHOUT ROWID;
            CREATE TABLE IF NOT EXISTS terms(token TEXT, leaf TEXT, rid INTEGER,
                PRIMARY KEY(token,leaf,rid)) WITHOUT ROWID;
            CREATE INDEX IF NOT EXISTS terms_leaf ON terms(leaf,token,rid);
            CREATE INDEX IF NOT EXISTS rows_leaf ON rows(leaf);
            CREATE TABLE IF NOT EXISTS aliases(alias TEXT PRIMARY KEY, subject TEXT);
            CREATE TABLE IF NOT EXISTS offsets(path TEXT PRIMARY KEY, offset INTEGER);
            CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY, value TEXT);
        """)

    @classmethod
    def build(cls, directory: str | Path, family: str, records: Iterable[dict]) -> dict:
        started = time.perf_counter()
        directory = Path(directory)
        directory.mkdir(parents=True, exist_ok=True)
        con = sqlite3.connect(directory / "evidence.db")
        cls._schema(con)
        con.execute("PRAGMA journal_mode=WAL")
        count = con.execute("SELECT COUNT(*) FROM rows").fetchone()[0]
        inserted = 0
        committed = 0
        for record in records:
            if record.get("_skip"):
                if record.get("_file"):
                    con.execute("INSERT OR REPLACE INTO offsets VALUES(?,?)", (record["_file"], record["_offset"]))
                continue
            if record.get("redirect"):
                con.execute("INSERT OR REPLACE INTO aliases VALUES(?,?)",
                            (record["title"], record["redirect"]))
                if record.get("_file"):
                    con.execute("INSERT OR REPLACE INTO offsets VALUES(?,?)", (record["_file"], record["_offset"]))
                continue
            sha = str(record.get("sha") or hashlib.sha256(json.dumps(record, sort_keys=True,
                                           ensure_ascii=False).encode()).hexdigest())
            source = str(record.get("source") or f"{family}:{sha}")
            context = str(record.get("context") or "")
            slot = str(record.get("slot") or "")
            sentences = re.split(r"(?<=[。！？])\s*|\n+", str(record.get("text") or ""))
            antecedent = context
            for position, sentence in enumerate(sentences):
                if not sentence.strip():
                    continue
                own_sha = f"{sha}:{position}"
                if con.execute("SELECT 1 FROM rows WHERE sha=?", (own_sha,)).fetchone():
                    continue
                from .bot import _INJECTED
                if _INJECTED.search(sentence):
                    continue
                frame = index_slot(sentence)
                prior = index_slot(antecedent) if antecedent else None
                subject = frame.subject or (prior.subject if prior else "") or str(record.get("title") or "")
                if not subject:
                    continue
                bound_context = antecedent if not frame.subject or context else ""
                leaf = f"{family}:{(count + inserted) // LEAF_CAP:06d}"
                cursor = con.execute("INSERT INTO rows(sha,text,context,slot,subject,source,independent,leaf,position)"
                                     " VALUES(?,?,?,?,?,?,?,?,?)", (own_sha, sentence, bound_context, slot, subject,
                                      source, str(record.get("independent") or source), leaf, position))
                rid = cursor.lastrowid
                predicates = set(keys(frame))
                if prior and (not frame.subject or prior.subject == frame.subject):
                    predicates.update(keys(prior))
                con.executemany("INSERT OR IGNORE INTO frames VALUES(?,?,?)",
                                ((predicate, subject, rid) for predicate in predicates))
                if prior:
                    con.executemany("INSERT OR IGNORE INTO frames VALUES(?,?,?)",
                                    ((predicate, prior.subject, rid) for predicate in keys(prior) if prior.subject))
                tokens = set(nouns(subject)) | set(nouns(sentence)) | {subject}
                con.executemany("INSERT OR IGNORE INTO terms VALUES(?,?,?)",
                                ((token, leaf, rid) for token in tokens if len(token) >= 1))
                inserted += 1
                antecedent = sentence if frame.subject else antecedent
            if record.get("_file"):
                con.execute("INSERT OR REPLACE INTO offsets VALUES(?,?)", (record["_file"], record["_offset"]))
            if inserted - committed >= 10000:
                con.commit()
                committed = inserted
        con.commit()
        route_path = directory / "evidence.pkl"
        if inserted or not route_path.exists():
            crosses = defaultdict(lambda: defaultdict(dict))
            for token, leaf in con.execute("SELECT DISTINCT token,leaf FROM terms"):
                crosses[leaf][token][token] = 1
            stores = {leaf: dict(values) for leaf, values in crosses.items()}
            level = {leaf: Node(name=leaf, store=CrossStore(crosses=cross)) for leaf, cross in stores.items()}
            depth = 0
            while len(level) > 6:
                names = list(level)
                size = (len(names) + 5) // 6
                level = {f"{family}:L{depth}:{begin // size}": Node(
                    name=f"{family}:L{depth}:{begin // size}",
                    children={name: level[name] for name in names[begin:begin + size]})
                    for begin in range(0, len(names), size)}
                depth += 1
            root = conduct_tree.build(stores, hierarchy=Node(name=family, children=level)) if stores else None
            temporary = route_path.with_suffix(".tmp")
            with temporary.open("wb") as stream:
                pickle.dump((FORMAT, root), stream, protocol=pickle.HIGHEST_PROTOCOL)
            temporary.replace(route_path)
        total = con.execute("SELECT COUNT(*) FROM rows").fetchone()[0]
        con.close()
        return {"family": family, "rows": total, "new_rows": inserted, "leaf_cap": LEAF_CAP,
                "frame_cap": FRAME_CAP, "build_s": round(time.perf_counter() - started, 3)}

    @classmethod
    def from_qa(cls, family_directory: Path) -> dict:
        source = sqlite3.connect(f"file:{family_directory / 'family.db'}?mode=ro", uri=True)
        checkpoint = family_directory / "evidence" / "qa_offset.json"
        offset = int(json.loads(checkpoint.read_text())["rid"]) if checkpoint.exists() else 0
        latest = offset
        def records():
            nonlocal latest
            for rid, sha, answer, source_id, slot, payload in source.execute(
                    "SELECT id,sha,answer,source,slot,payload FROM records WHERE slot!='social' AND id>? ORDER BY id", (offset,)):
                latest = rid
                row = json.loads(payload)
                variants = row.get("q_variants") or []
                yield {"sha": sha, "text": answer, "source": source_id + ":" + sha,
                       "independent": source_id, "context": variants[0] if variants else "", "slot": slot}
        try:
            result = cls.build(family_directory / "evidence", "general_qa", records())
            temporary = checkpoint.with_suffix(".tmp")
            temporary.write_text(json.dumps({"rid": latest}) + "\n")
            temporary.replace(checkpoint)
            return result
        finally:
            source.close()

    def candidates(self, asked, *, related_keys: tuple[str, ...] = ()) -> tuple[list[dict], dict]:
        self._refresh()
        tokens = tuple(dict.fromkeys((asked.subject, *nouns(asked.subject))))
        tokens = tuple(token for token in tokens if token)
        aliases = {}
        subject = asked.subject
        for _ in range(16):
            target = self.con.execute("SELECT subject FROM aliases WHERE alias=?", (subject,)).fetchone()
            if target is None or subject in aliases:
                break
            aliases[subject] = target[0]
            subject = target[0]
        tokens = tuple(dict.fromkeys((*tokens, subject, *nouns(subject))))
        route = conduct_tree.descend(self.root, list(tokens), anchor=subject) if self.root else {
            "verdict": "UNKNOWN_NO_ROUTE", "trail": []}
        ids = []
        if route.get("verdict") == "ROUTED":
            ids = [row[0] for row in self.con.execute(
                "SELECT id FROM rows WHERE leaf=? AND (subject=? OR context LIKE ?) LIMIT ?",
                (route["leaf"], subject, "%" + subject + "%", LEAF_CAP))]
        frame_ids = []
        for predicate in dict.fromkeys((*keys(asked), *related_keys)):
            frame_ids.extend(row[0] for row in self.con.execute(
                "SELECT rid FROM frames WHERE predicate=? AND subject=? LIMIT ?",
                (predicate, subject, FRAME_CAP - len(frame_ids))))
            if len(frame_ids) >= FRAME_CAP:
                break
        ids = list(dict.fromkeys((*ids, *frame_ids)))
        rows = []
        for begin in range(0, len(ids), 400):
            batch = ids[begin:begin + 400]
            marks = ",".join("?" for _ in batch)
            rows.extend(dict(row) | {"family": self.family} for row in self.con.execute(
                f"SELECT * FROM rows WHERE id IN ({marks})", batch))
        return rows, {"route": route, "path": "conduct+fallback_frames" if ids else "refused",
                      "frames_touched": len(frame_ids), "frame_cap_hit": len(frame_ids) == FRAME_CAP,
                      "leaf_rows": len(ids) - len(set(frame_ids)), "aliases": aliases}

    def close(self) -> None:
        self.con.close()
