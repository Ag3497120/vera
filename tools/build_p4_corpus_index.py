"""Build separate, read-only-at-runtime sentence indexes for P4.

Usage: python3.11 tools/build_p4_corpus_index.py [--root CORPUS] [--out DIR]
Each family gets its own database. No cross-family votes or merged postings.
The row id preserves narrative order within a source/dialogue.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path


INPUTS = {
    "local": "local/sentences.jsonl",
    "pro": "pro/sentences_2026-09-29.jsonl",
    "code": "code/items.jsonl",
    "conversation": "conversation/utterances.jsonl",
}


def build(path: Path, output: Path, family: str) -> int:
    stat = path.stat()
    if output.exists():
        con = sqlite3.connect(f"file:{output}?mode=ro", uri=True)
        try:
            meta = dict(con.execute("SELECT key,value FROM meta"))
            if meta.get("size") == str(stat.st_size) and meta.get("mtime_ns") == str(stat.st_mtime_ns):
                return int(meta["rows"])
        except sqlite3.DatabaseError:
            pass
        finally:
            con.close()
    output.parent.mkdir(parents=True, exist_ok=True)
    tmp = output.with_suffix(".building")
    tmp.unlink(missing_ok=True)
    con = sqlite3.connect(tmp)
    con.executescript("""
        PRAGMA journal_mode=OFF;
        PRAGMA synchronous=OFF;
        CREATE TABLE rows(id INTEGER PRIMARY KEY, text TEXT NOT NULL, source TEXT,
                          scene TEXT, grp TEXT, sha TEXT);
        CREATE VIRTUAL TABLE search USING fts5(text, scene, content='rows',
                                                content_rowid='id', tokenize='trigram');
        CREATE TABLE meta(key TEXT PRIMARY KEY,value TEXT);
    """)
    batch = []
    n = 0
    with path.open(encoding="utf-8") as inp:
        for raw in inp:
            try:
                rec = json.loads(raw)
            except json.JSONDecodeError:
                continue  # a concurrently appended partial final line
            sentence = str(rec.get("text") or "").strip()
            if not sentence:
                continue
            n += 1
            grp = rec.get("dialogue_id") if family == "conversation" else rec.get("source")
            batch.append((n, sentence, str(rec.get("source") or ""),
                          str(rec.get("scene") or rec.get("topic") or ""),
                          str(grp or ""), str(rec.get("sha") or "")))
            if len(batch) == 5000:
                con.executemany("INSERT INTO rows VALUES (?,?,?,?,?,?)", batch)
                batch.clear()
    if batch:
        con.executemany("INSERT INTO rows VALUES (?,?,?,?,?,?)", batch)
    con.execute("INSERT INTO search(search) VALUES ('rebuild')")
    con.execute("CREATE INDEX ix_group ON rows(grp,id)")
    con.executemany("INSERT INTO meta VALUES (?,?)", [
        ("size", str(stat.st_size)), ("mtime_ns", str(stat.st_mtime_ns)),
        ("rows", str(n)), ("family", family),
    ])
    con.commit()
    con.close()
    tmp.replace(output)
    return n


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--root", type=Path, default=Path.home() / "Projects/vera-corpus/codex")
    p.add_argument("--out", type=Path, default=Path(__file__).resolve().parents[1] / "build/p4")
    p.add_argument("--family", choices=[*INPUTS, "all"], default="all")
    args = p.parse_args()
    for family in INPUTS if args.family == "all" else [args.family]:
        src = args.root / INPUTS[family]
        if src.exists():
            print(f"{family}: {build(src, args.out / (family + '.db'), family)} rows", flush=True)


if __name__ == "__main__":
    main()
