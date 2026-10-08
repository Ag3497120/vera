"""A general typed store: unfiltered, so selectional statistics and noun
classes (is-a) are available for any word — the ground metaphor detection,
inheritance and generation stand on.

    python3.11 tools/build_general.py [lines_per_file]

Reads the first N non-tab lines of each jawiki+aozora sentence file, plus
every Codex sentence, extracts typed edges and is-a in parallel, and writes
~/Projects/vera-corpus/build/general.db (same schema as typed_edges.build).
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

SENT = (Path.home() / "Downloads" / "vera-cleanroom-transfer-20260926" /
        "vera-engine" / "corpora-large" / "sentences")
CODEX = Path.home() / "Projects" / "vera-corpus" / "codex"
OUT = Path.home() / "Projects" / "vera-corpus" / "build" / "general.db"


def _work(args):
    from verantyx.typed_edges import extract, isa
    rows = args
    out = []
    for sha, text, src in rows:
        try:
            es = extract(text)
            ia = isa(text)
        except Exception:
            continue
        out.append((sha, text, src,
                    [e.as_tuple() + (e.mod, e.ev, int(e.past)) for e in es], ia))
    return out


def _lines(n_per_file: int):
    for f in sorted(SENT.glob("*.txt")):
        k = 0
        with open(f, encoding="utf-8", errors="ignore") as fh:
            for i, line in enumerate(fh):
                if "\t" in line or not line.strip():
                    continue
                s = line.strip()
                yield (hashlib.sha1(s.encode()).hexdigest(), s,
                       "human:%s:%d" % (f.stem, i // 40))
                k += 1
                if k >= n_per_file:
                    break
    for f in sorted(CODEX.rglob("sentences.jsonl")):
        for line in open(f, encoding="utf-8"):
            try:
                r = json.loads(line)
            except ValueError:
                continue
            yield (hashlib.sha1(r["text"].encode()).hexdigest(), r["text"], r["source"])


def main() -> None:
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 40000
    if OUT.exists():
        OUT.unlink()
    con = sqlite3.connect(str(OUT))
    from verantyx.typed_edges import SCHEMA
    con.executescript(SCHEMA)
    seen = set()
    chunk, chunks = [], []

    def batches():
        nonlocal chunk
        for r in _lines(n):
            if r[0] in seen:
                continue
            seen.add(r[0])
            chunk.append(r)
            if len(chunk) >= 2000:
                yield chunk
                chunk = []
        if chunk:
            yield chunk

    tot = {"sentences": 0, "edges": 0, "isa": 0}
    with ProcessPoolExecutor(8) as ex:
        for part in ex.map(_work, batches(), chunksize=1):
            con.executemany("INSERT INTO tsent VALUES (?,?,?,?)",
                            [(sha, t, src, len(es)) for sha, t, src, es, _ in part])
            con.executemany("INSERT INTO tedges VALUES (?,?,?,?,?,?,?,?,?)",
                            [e[:4] + (src, sha) + e[4:] for sha, _t, src, es, _ in part for e in es])
            con.executemany("INSERT INTO isa VALUES (?,?,?,?)",
                            [(x, y, src, sha) for sha, _t, src, _es, ia in part for x, y in ia])
            con.commit()
            tot["sentences"] += len(part)
            tot["edges"] += sum(len(p[3]) for p in part)
            tot["isa"] += sum(len(p[4]) for p in part)
            if tot["sentences"] % 200000 < 2000:
                print(json.dumps(tot), flush=True)
    print(json.dumps(tot))


if __name__ == "__main__":
    main()
