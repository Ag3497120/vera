#!/usr/bin/env python3
"""W12-c1: builder of the initial layers (docs/INITIAL_LAYERS.md). No LLM, no network.

    build_initial_layers.py vocab        --jawiki F --heldout-root DIR --placement R9 --out vocab.sqlite --report x2_vocab.json
    build_initial_layers.py domain-db    --codex-db general_qa.db --scene S --out DIR/general_qa.db [--control-of S --seed N]
    build_initial_layers.py domain-layer --domain-placement P --base R9 --layer L.sqlite --ledger LEDGER --domain law --scene S --report r.json
    build_initial_layers.py combine      --base R9 --layer A.sqlite --layer B.sqlite --out C.sqlite --ledger LEDGER --report r.json
    build_initial_layers.py capacity     --layer A.sqlite ... --report r.json

The parts of vera1 are imported and called, never copied: `hierarchy._layers_for` / `CAPACITY` (the capacity law), `placement_layer.write_entry` / `growth` (the only way into a layer), `coarse_place.query`
(the base's own answer), `testimony_ledger` (the hash-chained ledger a layer row has to name first).
NOT imported (review r1 M3, deviation recorded in docs/INITIAL_LAYERS.md section J): `granularity.standalone_count`. The vocabulary builder takes
MAXIMAL single-script runs, which by construction are not flanked by further kanji, so the vocabulary decision is the same as
`standalone_count(w, text) > 0` for texts without the iteration mark; tests/test_w12c1_vocab.py checks that equivalence on synthetic texts and checks
the one place where the builder differs on purpose: the iteration mark U+3005 (see _ITER) belongs to a kanji run here and does not in `granularity`.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import re
import sqlite3
import sys
import time
import unicodedata
from collections import Counter
from typing import Any, Dict, Iterable, Iterator, List, Optional, Sequence, Set, Tuple

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

VOCAB_SCHEMA = "verantyx.vocab_layer/1"
MIN_DOCS = 3                    # K401: independent documents (the same threshold as granularity.MIN_STANDALONE, used as a number of documents here)
KANJI_MIN, KANJI_MAX = 2, 8     # K405
KATA_MIN, KATA_MAX = 2, 20      # K405

# The iteration mark U+3005 repeats the kanji before it (代々木, 佐々木, 人々, 様々): it is part of a kanji run. `granularity._KANJI` does not have it, so there
# `代々木公園` is cut into `木公園` (review r1 M2; a hole of the imported part, docs/INITIAL_LAYERS.md section 7). A run that STARTS with the mark has no kanji
# to repeat: it is not a candidate (the whole run is dropped, not trimmed).
_ITER = "々"
_KANJI_RUN = re.compile(r"[㐀-䶿一-鿿々]+")          # the range of granularity._KANJI plus the iteration mark
_KATA_RUN = re.compile(r"[ァ-ヺー]+")                # katakana letters and the long-vowel mark (U+30FC)
_MIXED_SPAN = re.compile(r"[㐀-䶿一-鿿々ァ-ヺー]+")    # kanji and katakana touching each other: not a candidate (K405)
_HAS_KANJI = re.compile(r"[㐀-䶿一-鿿]")
_HAS_KATA = re.compile(r"[ァ-ヺ]")


def _nfkc(s: str) -> str:
    return unicodedata.normalize("NFKC", s)


# ------------------------------------------------------------------------------------------------------------------------ vocabulary layer
def runs_of(text: str) -> Tuple[Set[str], Set[str], Set[str]]:
    """One document -> (kanji words, katakana words, mixed-script spans) of the document, each a SET (a word counts once per document).

    A candidate is a maximal run of ONE script (K405): kanji 2..8 characters, katakana (long-vowel mark included) 2..20 characters.
    A kanji run (the iteration mark included) is by construction not flanked by kanji and a katakana run is not flanked by katakana or the long-vowel mark,
    which is K406 (same decision as `granularity.standalone_count` for texts without the iteration mark; the katakana condition and the iteration mark are the
    builder's own additions, docs sections 7 and J)."""
    t = _nfkc(text)
    kanji = {m for m in _KANJI_RUN.findall(t) if KANJI_MIN <= len(m) <= KANJI_MAX and not m.startswith(_ITER)}
    kata = {m for m in _KATA_RUN.findall(t) if KATA_MIN <= len(m) <= KATA_MAX}
    mixed = {m for m in _MIXED_SPAN.findall(t) if _HAS_KANJI.search(m) and _HAS_KATA.search(m)}
    return kanji, kata, mixed


def script_of(word: str) -> str:
    return "kanji" if _HAS_KANJI.search(word) else "katakana"


def select_vocab(docs_human: Dict[str, int], docs_generated: Dict[str, int], min_docs: int = MIN_DOCS) -> Dict[str, Dict[str, Any]]:
    """K401/K407: a word enters when ONE class (human or generated) has it in at least `min_docs` documents. The classes are never added together.
    Returns word -> {script, docs_human, docs_generated, origin_class, in_base_material}."""
    out: Dict[str, Dict[str, Any]] = {}
    for w in set(docs_human) | set(docs_generated):
        h, g = docs_human.get(w, 0), docs_generated.get(w, 0)
        hh, gg = h >= min_docs, g >= min_docs
        if not (hh or gg):
            continue
        out[w] = {"script": script_of(w), "docs_human": h, "docs_generated": g,
                  "origin_class": "both" if (hh and gg) else "human" if hh else "generated",
                  "in_base_material": bool(hh)}
    return out


#: the fields a generated family is read from (K407; docs section 2): family -> fields. A field may be a string, a list of strings, or "sentences[].text".
FAMILY_FIELDS = {
    "general_qa": ("q_variants", "answer", "why"),
    "conversation": ("text",),
    "code": ("text",),
    "code_qa": ("question", "answer_text", "usage"),
    "narrative": ("title", "sentences[].text", "setting"),
    # figurative_commonsense has four kinds (pun, simile_metaphor, haiku, cause_effect), paraphrase_entail two (pair, who_did_what): the union of their text fields
    "figurative_commonsense": ("pun", "mechanism", "word_a", "word_b", "example", "expression", "plain_meaning", "property", "target", "vehicle", "haiku", "lines", "kigo", "note",
                               "cause", "effect", "phrasings", "relation"),
    "paraphrase_entail": ("sentence", "question", "answer", "s1", "s2", "reason"),
}
FAMILY_FILE = {"general_qa": "records.jsonl", "conversation": "utterances.jsonl", "code": "items.jsonl", "code_qa": "records.jsonl", "narrative": "records.jsonl",
               "figurative_commonsense": "records.jsonl", "paraphrase_entail": "records.jsonl"}


def row_text(family: str, row: Dict[str, Any]) -> Optional[str]:
    """The text of a generated row from the fields of its family; None when no field could be read (counted by the caller)."""
    parts: List[str] = []
    for f in FAMILY_FIELDS[family]:
        if f.endswith("[].text"):
            v = row.get(f[:-len("[].text")])
            if isinstance(v, list):
                parts.extend(str(x.get("text", "")) for x in v if isinstance(x, dict))
        else:
            v = row.get(f)
            if isinstance(v, str):
                parts.append(v)
            elif isinstance(v, list):
                parts.extend(str(x) for x in v if isinstance(x, str))
    return "\n".join(p for p in parts if p) if any(parts) else None


def _jawiki_chunk(lines: List[str]):
    out = []
    for ln in lines:
        try:
            d = json.loads(ln)
        except ValueError:
            out.append((None, None, "BAD_JSON"))
            continue
        title = d.get("title")
        if not isinstance(title, str) or not isinstance(d.get("text"), str):
            out.append((None, None, "REDIRECT_NO_TEXT" if isinstance(title, str) and "redirect" in d else "NO_TITLE_OR_TEXT"))
            continue
        k, a, m = runs_of(title + "\n" + d["text"])
        out.append((title, (k | a, m), None))
    return out


def _chunks(fh, n: int) -> Iterator[List[str]]:
    buf: List[str] = []
    for ln in fh:
        buf.append(ln)
        if len(buf) >= n:
            yield buf
            buf = []
    if buf:
        yield buf


def count_jawiki(path: str, jobs: int = 4) -> Dict[str, Any]:
    """jawiki: one article (`title`) = one document, class `human` (K407). A title seen again is the same document (not counted twice)."""
    import multiprocessing as mp
    docs: Counter = Counter()
    mixed: Set[str] = set()
    seen: Set[str] = set()
    skipped: Counter = Counter()
    n = 0
    with open(path, encoding="utf-8") as fh:
        with mp.get_context("fork").Pool(jobs) as pool:
            for res in pool.imap(_jawiki_chunk, _chunks(fh, 4000), chunksize=1):
                for title, got, why in res:
                    if why:
                        skipped[why] += 1
                        continue
                    if title in seen:
                        skipped["DUPLICATE_TITLE"] += 1
                        continue
                    seen.add(title)
                    n += 1
                    words, mx = got
                    docs.update(words)
                    mixed |= mx
    return {"docs": docs, "mixed": mixed, "n_docs": n, "skipped": dict(skipped)}


def count_generated(root: str, families: Sequence[str] = tuple(FAMILY_FIELDS)) -> Dict[str, Any]:
    """Generated heldout: one `source` (a generation bundle) = one document, class `generated` (K407). A row without `source` gets the document `family#line`."""
    docs: Counter = Counter()
    mixed: Set[str] = set()
    skipped: Counter = Counter()
    per_family: Dict[str, Dict[str, int]] = {}
    for fam in families:
        p = os.path.join(root, fam, "heldout", FAMILY_FILE[fam])
        if not os.path.exists(p):
            skipped["FAMILY_FILE_MISSING:" + fam] += 1
            continue
        bundles: Dict[str, Tuple[Set[str], Set[str]]] = {}
        rows = no_source = unread = 0
        with open(p, encoding="utf-8") as fh:
            for i, ln in enumerate(fh):
                try:
                    d = json.loads(ln)
                except ValueError:
                    skipped["BAD_JSON:" + fam] += 1
                    continue
                rows += 1
                txt = row_text(fam, d)
                if txt is None:
                    unread += 1
                    skipped["NO_READABLE_FIELD:" + fam] += 1
                    continue
                src = d.get("source")
                if not isinstance(src, str) or not src:
                    no_source += 1
                    src = "%s#%d" % (fam, i)
                k, a, m = runs_of(txt)
                cur = bundles.setdefault(src, (set(), set()))
                cur[0].update(k | a)
                cur[1].update(m)
        for src, (ws, mx) in bundles.items():
            docs.update(ws)
            mixed |= mx
        per_family[fam] = {"rows": rows, "documents": len(bundles), "rows_without_source": no_source, "rows_unreadable": unread}
    return {"docs": docs, "mixed": mixed, "per_family": per_family, "skipped": dict(skipped)}


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for b in iter(lambda: fh.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def write_vocab_sqlite(path: str, vocab: Dict[str, Dict[str, Any]], meta: Dict[str, Any]) -> None:
    if os.path.exists(path):
        raise SystemExit("exists (nothing is overwritten): %s" % path)
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    con = sqlite3.connect(path)
    con.execute("CREATE TABLE words(word TEXT PRIMARY KEY, script TEXT, docs_human INTEGER, docs_generated INTEGER, origin_class TEXT, in_base_material INTEGER) WITHOUT ROWID")
    con.execute("CREATE TABLE meta(k TEXT PRIMARY KEY, v TEXT) WITHOUT ROWID")
    con.executemany("INSERT INTO words VALUES (?,?,?,?,?,?)",
                    [(w, r["script"], r["docs_human"], r["docs_generated"], r["origin_class"], 1 if r["in_base_material"] else 0) for w, r in sorted(vocab.items())])
    con.executemany("INSERT INTO meta VALUES (?,?)", [(k, json.dumps(v, ensure_ascii=False, sort_keys=True)) for k, v in sorted(meta.items())])
    con.commit()
    con.close()


def base_states(placement_dir: str) -> Dict[str, str]:
    """word -> state of the base's headword table for the words the base leaves UNPLACED or MULTIPLE (read only)."""
    p = os.path.join(placement_dir, "placement.sqlite")
    con = sqlite3.connect("file:%s?mode=ro" % p, uri=True)
    try:
        return {w: s for w, s in con.execute("SELECT word, state FROM headwords WHERE state IN ('UNPLACED','MULTIPLE')")}
    finally:
        con.close()


def cmd_vocab(a) -> int:
    t0 = time.time()
    jw = count_jawiki(a.jawiki, jobs=a.jobs)
    t1 = time.time()
    gen = count_generated(a.heldout_root)
    t2 = time.time()
    vocab = select_vocab(dict(jw["docs"]), dict(gen["docs"]), MIN_DOCS)
    meta = {"schema": VOCAB_SCHEMA, "min_docs": MIN_DOCS, "kanji_len": [KANJI_MIN, KANJI_MAX], "katakana_len": [KATA_MIN, KATA_MAX],
            "inputs": {"jawiki": {"path": a.jawiki, "sha256": sha256_file(a.jawiki) if a.hash_inputs else None, "documents": jw["n_docs"]},
                       "generated_heldout": {"root": a.heldout_root, "families": gen["per_family"]}},
            "built": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "llm_declarations": False}
    write_vocab_sqlite(a.out, vocab, meta)
    cls = Counter(r["origin_class"] for r in vocab.values())
    scr = Counter((r["origin_class"], r["script"]) for r in vocab.values())
    rep = {"schema": VOCAB_SCHEMA, "out": a.out, "out_sha256": sha256_file(a.out), "out_bytes": os.path.getsize(a.out), "min_docs": MIN_DOCS,
           "candidates": {"distinct_jawiki": len(jw["docs"]), "distinct_generated": len(gen["docs"]), "distinct_union": len(set(jw["docs"]) | set(gen["docs"]))},
           "words": {"total": len(vocab), "by_class": dict(cls), "by_class_script": {"%s/%s" % k: v for k, v in sorted(scr.items())}},
           "OUT_OF_SCOPE_MIXED_SCRIPT": {"distinct_spans_jawiki": len(jw["mixed"]), "distinct_spans_generated": len(gen["mixed"]),
                                         "distinct_union": len(jw["mixed"] | gen["mixed"])},
           "documents": {"jawiki": jw["n_docs"], "generated": gen["per_family"]},
           "skipped": {"jawiki": jw["skipped"], "generated": gen["skipped"]},
           "seconds": {"jawiki": round(t1 - t0, 1), "generated": round(t2 - t1, 1), "total": round(time.time() - t0, 1)}}
    if a.placement:
        st = base_states(a.placement)
        inside = {w: s for w, s in st.items() if w in vocab}
        by = Counter((s, vocab[w]["origin_class"]) for w, s in inside.items())
        rep["base_undecided"] = {"placement": a.placement, "UNPLACED_total": sum(1 for s in st.values() if s == "UNPLACED"),
                                 "MULTIPLE_total": sum(1 for s in st.values() if s == "MULTIPLE"), "confirmed_total": len(inside),
                                 "confirmed_by_state_class": {"%s/%s" % k: v for k, v in sorted(by.items())},
                                 "note": "the vocabulary layer confirms that a string is a word; it does not type it. The reader does not consult it yet (docs section 7)."}
        if a.sample_out:
            pool = sorted(inside)
            pick = random.Random(20261005).sample(pool, min(a.sample_n, len(pool)))
            with open(a.sample_out, "w", encoding="utf-8") as fo:
                fo.write("# NOT ground truth: a look by the implementer at 60 words drawn with random.Random(20261005).sample(sorted(words), 60). The 4th column is filled by hand.\n")
                fo.write("word\tbase_state\tclass\tdocs_human\tdocs_generated\tjudgement\treason\n")
                for w in pick:
                    r = vocab[w]
                    fo.write("%s\t%s\t%s\t%d\t%d\t\t\n" % (w, inside[w], r["origin_class"], r["docs_human"], r["docs_generated"]))
    with open(a.report, "w", encoding="utf-8") as fo:
        json.dump(rep, fo, ensure_ascii=False, indent=1, sort_keys=True)
    print(json.dumps({"words": rep["words"], "seconds": rep["seconds"]}, ensure_ascii=False))
    return 0


# ------------------------------------------------------------------------------------------------------------------------ domain material
CODEX_ROW_COLUMNS = ("id", "text", "source", "scene", "grp", "sha", "family", "source_file", "line", "kind", "fields", "origin", "generator", "body_sha")


def make_domain_db(src: str, out: str, ids: Sequence[int]) -> Dict[str, Any]:
    """Copy the rows `ids` of a generated family index (read only) into a new db with the same `rows` table (the ids are kept; the holdout lists name rows by id)."""
    if os.path.exists(out):
        raise SystemExit("exists (nothing is overwritten): %s" % out)
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    s = sqlite3.connect("file:%s?mode=ro" % src, uri=True)
    o = sqlite3.connect(out)
    o.execute("CREATE TABLE rows(id INTEGER PRIMARY KEY, text TEXT NOT NULL, source TEXT, scene TEXT, grp TEXT, sha TEXT, family TEXT, source_file TEXT, line INTEGER, kind TEXT, fields TEXT, origin TEXT, generator TEXT, body_sha TEXT)")
    h = hashlib.sha256()
    n = 0
    ids = sorted(ids)
    for i in range(0, len(ids), 500):
        part = ids[i:i + 500]
        q = "SELECT %s FROM rows WHERE id IN (%s) ORDER BY id" % (",".join(CODEX_ROW_COLUMNS), ",".join("?" * len(part)))
        got = s.execute(q, part).fetchall()
        o.executemany("INSERT INTO rows VALUES (%s)" % ",".join("?" * len(CODEX_ROW_COLUMNS)), got)
        for r in got:
            h.update(json.dumps(r, ensure_ascii=False).encode("utf-8"))
        n += len(got)
    o.commit()
    o.close()
    s.close()
    return {"rows": n, "rows_sha256": h.hexdigest(), "ids_min": ids[0] if ids else None, "ids_max": ids[-1] if ids else None, "bytes": os.path.getsize(out), "sha256": sha256_file(out)}


def cmd_domain_db(a) -> int:
    s = sqlite3.connect("file:%s?mode=ro" % a.codex_db, uri=True)
    law = [r[0] for r in s.execute("SELECT id FROM rows WHERE scene=? ORDER BY id", (a.scene,))]
    if a.control_of:
        n_law = len([r for r in s.execute("SELECT id FROM rows WHERE scene=?", (a.control_of,))])
        others = [r[0] for r in s.execute("SELECT id FROM rows WHERE scene IS NOT ? ORDER BY id", (a.control_of,))]
        ids = random.Random(a.seed).sample(sorted(others), n_law)               # K409
        what = {"control_of_scene": a.control_of, "seed": a.seed, "n": n_law, "population": len(others)}
    else:
        ids, what = law, {"scene": a.scene}
    s.close()
    rep = make_domain_db(a.codex_db, a.out, ids)
    rep.update(what)
    rep["source_db"] = a.codex_db
    rep["source_db_bytes"] = os.path.getsize(a.codex_db)
    with open(a.report, "w", encoding="utf-8") as fo:
        json.dump(rep, fo, ensure_ascii=False, indent=1, sort_keys=True)
    print(json.dumps(rep, ensure_ascii=False))
    return 0


# ------------------------------------------------------------------------------------------------------------------------ domain layer
def domain_candidates(domain_pl_dir: str) -> List[Tuple[str, str, str]]:
    """The words the domain placement decided DIRECT: [(word, type, decided_by)] (read only)."""
    p = os.path.join(domain_pl_dir, "placement.sqlite")
    con = sqlite3.connect("file:%s?mode=ro" % p, uri=True)
    try:
        return [(w, top, by) for w, top, by in con.execute("SELECT word, top, by FROM headwords WHERE state='DECIDED' AND origin='direct' ORDER BY word")]
    finally:
        con.close()


def _base_headword_states(base_dir: str, words: Sequence[str]) -> Dict[str, str]:
    con = sqlite3.connect("file:%s?mode=ro" % os.path.join(base_dir, "placement.sqlite"), uri=True)
    out: Dict[str, str] = {}
    try:
        for i in range(0, len(words), 500):
            part = list(words[i:i + 500])
            for w, s in con.execute("SELECT word, state FROM headwords WHERE word IN (%s)" % ",".join("?" * len(part)), part):
                out[w] = s
    finally:
        con.close()
    return out


def plan_domain_layer(cands: Sequence[Tuple[str, str, str]], base_query, base_headword_state) -> Dict[str, Any]:
    """K408, pure: which candidate words go into the layer and why the others do not.
    `base_query(word)` is the base's own answer with no layer (`coarse_place.query(..., layer=False)`); `base_headword_state(word)` the state in the base's table (or None)."""
    from verantyx import coarse_types as ct
    write: List[Dict[str, Any]] = []
    why: Counter = Counter()
    seen: Set[Tuple[str, str]] = set()
    for w0, top, by in cands:
        w = _nfkc(w0)                                              # the layer stores NFKC words (`write_entry`), the base is asked with NFKC
        if (w, top) in seen:
            why["DUPLICATE_AFTER_NFKC"] += 1
            continue
        if top not in ct.ALL_TYPES:
            why["DOMAIN_TYPE_NOT_A_TYPE_ID"] += 1
            continue
        if base_headword_state(w0) == "DECIDED" or base_headword_state(w) == "DECIDED":                  # the cheap prefilter: the table already says the base decided it
            why["BASE_DECIDED"] += 1
            continue
        r = base_query(w)
        st = r.get("state")
        if st not in ("UNPLACED", "UNKNOWN", "MULTIPLE"):
            why["BASE_" + str(st)] += 1
            continue
        if st == "MULTIPLE" and top not in (r.get("top") or []):
            why["TYPE_NOT_AMONG_BASE_CANDIDATES"] += 1
            continue
        seen.add((w, top))
        write.append({"word": w, "type": top, "by": [x for x in str(by).split("+") if x] or [str(by)], "base_state": st, "base_top": list(r.get("top") or [])})
    return {"write": write, "not_written": dict(why)}


import contextlib


@contextlib.contextmanager
def bulk_ledger(ledger: Any) -> Iterator[None]:
    """Many appends to one `TestimonyLedger` without the O(n^2) cost of the stock append (every append re-reads and re-verifies the whole file and rewrites the manifest: 1,200 rows took
    100 seconds and the cost grows with the square; the domain layer has about 10^4 rows). Inside the block an append only extends the chain in memory (the hash is `llm_choice._chain_hash`,
    the line is `llm_choice._canonical`, the manifest row is `llm_choice.row_content_sha256`: the same functions the stock append and verify call); on leaving the block the file is fsynced, the
    manifest is written once, the instance is restored and the WHOLE ledger is verified by the stock `verify()` (it raises if the chain or the manifest does not hold). docs section 7."""
    from verantyx import llm_choice as LC
    led = ledger._led
    entries = ledger.entries()
    manifest = led.read_manifest()
    state = {"seq": len(entries), "prev": entries[-1]["hash"] if entries else LC.GENESIS}
    if manifest is None:
        raise RuntimeError("bulk_ledger needs a manifested ledger (a TestimonyLedger always is)")
    fh = open(led.path, "ab")
    old_verify, old_locked, old_entries = ledger.__dict__.get("verify"), led.__dict__.get("_append_locked"), ledger.__dict__.get("entries")
    head = entries[0]

    def fast(entry, handle, manifested=False):
        body = {k: v for k, v in entry.items() if k not in ("hash", "seq", "prev")}
        body["seq"], body["prev"] = state["seq"], state["prev"]
        stored = dict(body, hash=LC._chain_hash(state["prev"], body))
        fh.write((LC._canonical(stored) + "\n").encode("utf-8"))
        if manifested:
            manifest["rows"][str(stored["seq"])] = LC.row_content_sha256(stored)
        state["seq"] += 1
        state["prev"] = stored["hash"]
        return stored
    ledger.verify = lambda: {}
    ledger.entries = lambda: (head,)             # `store_id` is `entries()[0]["store_id"]`, and `write_entry` asks for it twice per row (each time a full read and verification)
    led._append_locked = fast
    try:
        yield
    finally:
        fh.flush()
        os.fsync(fh.fileno())
        fh.close()
        led._write_manifest(manifest)
        if old_verify is None:
            del ledger.__dict__["verify"]
        else:
            ledger.verify = old_verify
        if old_entries is None:
            del ledger.__dict__["entries"]
        else:
            ledger.entries = old_entries
        if old_locked is None:
            del led.__dict__["_append_locked"]
        else:
            led._append_locked = old_locked
        ledger.verify()                      # the stock verification of the whole chain and the manifest: raises LedgerIntegrityError


@contextlib.contextmanager
def fast_layer_writes() -> Iterator[None]:
    """`placement_layer.write_entry` opens a SQLite connection per row and commits it; on macOS every commit is a full fsync (about 50 ms: 20,000 rows = 17 minutes). Inside the block the
    connections `placement_layer` opens are `synchronous=OFF, journal_mode=MEMORY` (a build artifact that is verified afterwards and rebuilt, never repaired, if the process dies). The rows written are the same."""
    import sqlite3 as _sq
    from verantyx import placement_layer as PL

    class _Proxy:
        def __getattr__(self, name):
            return getattr(_sq, name)

        @staticmethod
        def connect(*a, **k):
            con = _sq.connect(*a, **k)
            con.execute("PRAGMA synchronous=OFF")
            con.execute("PRAGMA journal_mode=MEMORY")
            return con
    old = PL.sqlite3
    PL.sqlite3 = _Proxy()
    try:
        yield
    finally:
        PL.sqlite3 = old


class CachedLedgerView:
    """A read-only view of a `TestimonyLedger` for `placement_layer.growth`: `growth` asks `ledger.store_id` once per layer row and every ask reads and verifies the whole ledger (16,000 rows: minutes).
    The view verifies ONCE (the stock `verify()`) and answers `entries()`, `store_id` and `verify()` from that."""

    def __init__(self, ledger: Any) -> None:
        ledger.verify()
        self._entries = ledger.entries()
        self.store_id = self._entries[0]["store_id"]
        self.path = getattr(ledger, "path", None)

    def entries(self) -> tuple:
        return self._entries

    def verify(self) -> Dict[str, Any]:
        return {}


def write_plan(plan: Dict[str, Any], layer_path: str, ledger: Any, base_sha: Optional[str], common: Dict[str, Any]) -> int:
    """K408: write the planned rows with `placement_layer.write_entry` (origin layer_confirmed; the testimony ledger has the `promoted_to_layer` row first). Returns the number written."""
    from verantyx import placement_layer as PL
    from verantyx.testimony_ledger import key_of
    wrote = 0
    with bulk_ledger(ledger), fast_layer_writes():
        for item in plan["write"]:
            ev = {"decision": "builder_domain", "model": None, "material_origin": "generated", "base_state": item["base_state"]}
            ev.update(common)
            PL.write_entry(layer_path, ledger, base_sha256=base_sha, word=item["word"], type=item["type"], origin="layer_confirmed", decided_by=item["by"],
                           evidence=ev, role_frame=None, key=key_of(item["word"], item["word"], item["type"], None), candidate=item["word"])
            wrote += 1
    return wrote


def cmd_domain_layer(a) -> int:
    from verantyx import coarse_place
    from verantyx import placement_layer as PL
    from verantyx.testimony_ledger import TestimonyLedger, key_of
    t0 = time.time()
    base_pl, why = coarse_place._open(a.base)
    if base_pl is None:
        print(json.dumps({"verdict": "BASE_UNAVAILABLE", "why": list(why)}))
        return 2
    if a.plan_cache and os.path.exists(a.plan_cache):
        plan = json.load(open(a.plan_cache, encoding="utf-8"))
        cands = None
    else:
        cands = domain_candidates(a.domain_placement)
        states = _base_headword_states(a.base, [c[0] for c in cands])
        plan = plan_domain_layer(cands, lambda w: coarse_place.query(w, placement=a.base, layer=False), lambda w: states.get(w))
        plan["candidates"] = len(cands)
        if a.plan_cache:
            json.dump(plan, open(a.plan_cache, "w", encoding="utf-8"), ensure_ascii=False)
    n_cands = len(cands) if cands is not None else plan.get("candidates")
    plan["candidates"] = n_cands
    dom_sha = json.load(open(os.path.join(a.domain_placement, "manifest.json")))["content_sha256"]
    scene_rows = []
    if a.rows_db:
        c = sqlite3.connect("file:%s?mode=ro" % a.rows_db, uri=True)
        scene_rows = [r[0] for r in c.execute("SELECT id FROM rows ORDER BY id")]
        c.close()
    ledger = TestimonyLedger(a.ledger)
    reused = False
    if os.path.exists(a.layer):
        if not a.reuse_written:
            raise SystemExit("exists (nothing is overwritten): %s" % a.layer)
        layer, why = PL.open_layer(a.layer, base_pl.sha)          # a layer written by an earlier run of this very plan: it must say exactly what the plan says
        have = sorted((e["word"], e["type"]) for e in layer.all_entries())
        want = sorted((x["word"], x["type"]) for x in plan["write"])
        if layer is None or have != want:
            print(json.dumps({"verdict": "WRITTEN_LAYER_DISAGREES_WITH_PLAN", "have": len(have), "want": len(want)}))
            return 2
        ledger.verify()
        wrote, reused = len(plan["write"]), True
    else:
        wrote = write_plan(plan, a.layer, ledger, base_pl.sha, {"domain": a.domain, "scene": a.scene, "domain_placement_content_sha256": dom_sha, "evidence_rows": scene_rows[:5]})
    g = PL.growth(a.layer, CachedLedgerView(ledger), base_pl.sha) if wrote else {"layer_status": "EMPTY_NOT_CREATED"}
    rep = {"domain": a.domain, "scene": a.scene, "domain_placement": a.domain_placement, "domain_placement_content_sha256": dom_sha, "base_content_sha256": base_pl.sha,
           "domain_direct_candidates": n_cands, "written": wrote, "layer_reused_after_check": reused, "not_written": plan["not_written"], "growth": g, "layer": a.layer,
           "layer_sha256": sha256_file(a.layer) if wrote else None, "seconds": round(time.time() - t0, 1)}
    with open(a.report, "w", encoding="utf-8") as fo:
        json.dump(rep, fo, ensure_ascii=False, indent=1, sort_keys=True)
    print(json.dumps({"written": wrote, "not_written": plan["not_written"]}, ensure_ascii=False))
    return 0


# ------------------------------------------------------------------------------------------------------------------------ combine
def cmd_combine(a) -> int:
    from verantyx import coarse_place
    from verantyx import placement_layer as PL
    from verantyx.testimony_ledger import TestimonyLedger, key_of
    base_pl, why = coarse_place._open(a.base)
    if base_pl is None:
        print(json.dumps({"verdict": "BASE_UNAVAILABLE", "why": list(why)}))
        return 2
    if os.path.exists(a.out):
        raise SystemExit("exists (nothing is overwritten): %s" % a.out)
    ledger = TestimonyLedger(a.ledger)
    copied: Counter = Counter()
    with bulk_ledger(ledger), fast_layer_writes():
        for spec in a.layer:
            layer, lwhy = PL.open_layer(spec, base_pl.sha)
            if layer is None:
                print(json.dumps({"verdict": "SOURCE_LAYER_UNAVAILABLE", "layer": spec, "why": lwhy}))
                return 2
            for e in layer.all_entries():
                ev = {"from_layer": layer.name, "from_layer_path": os.path.abspath(spec), "from_entry_id": e["id"], "from_ledger_seq": e["ledger_seq"], "from_evidence": e["evidence"]}
                PL.write_entry(a.out, ledger, base_sha256=base_pl.sha, word=e["word"], type=e["type"], origin=e["origin"], decided_by=e["decided_by"], evidence=ev,
                               role_frame=e.get("role_frame"), key=key_of(e["word"], e["word"], e["type"], None), candidate=e["word"])
                copied[layer.name] += 1
    g = PL.growth(a.out, CachedLedgerView(ledger), base_pl.sha, with_list=True)
    conflicts = [x["word"] for x in g.get("list", []) if x["state"] == "conflict"]
    rep = {"out": a.out, "out_sha256": sha256_file(a.out), "sources": dict(copied), "growth": {k: v for k, v in g.items() if k != "list"},
           "conflict_words": conflicts, "note": "a word with two direct types abstains at query time (LAYER_CONFLICT); it is counted here, not resolved"}
    with open(a.report, "w", encoding="utf-8") as fo:
        json.dump(rep, fo, ensure_ascii=False, indent=1, sort_keys=True)
    print(json.dumps({"copied": dict(copied), "conflicts": len(conflicts)}, ensure_ascii=False))
    return 0


# ------------------------------------------------------------------------------------------------------------------------ capacity
def capacity_report(counts: Dict[str, int]) -> Dict[str, Any]:
    """The capacity law of `hierarchy` applied to the number of direct words of each layer (V is measured, not chosen)."""
    from verantyx import hierarchy as H
    return {"CAPACITY": H.CAPACITY, "MAX_ARMS": H.MAX_ARMS, "N_FACES": H.N_FACES,
            "layers": {k: {"V_direct_words": v, "layers_for_V": H._layers_for(v), "fits_one_node": v <= H.CAPACITY} for k, v in sorted(counts.items())},
            "rule": "depth = ceil(log_6(V / 4)); one node routes on at most CAPACITY = 24 distinct terms (hierarchy docstring)"}


def cmd_capacity(a) -> int:
    from verantyx import placement_layer as PL
    counts: Dict[str, int] = {}
    for spec in a.layer:
        g = PL.growth(spec, None, None)
        if g.get("layer_status") != "OK":
            print(json.dumps({"verdict": "LAYER_UNAVAILABLE", "layer": spec, "status": g.get("layer_status")}))
            return 2
        counts[os.path.basename(spec)] = g["words"]["direct"] + g["words"]["human"]
    rep = capacity_report(counts)
    with open(a.report, "w", encoding="utf-8") as fo:
        json.dump(rep, fo, ensure_ascii=False, indent=1, sort_keys=True)
    print(json.dumps(rep, ensure_ascii=False))
    return 0


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("vocab")
    p.add_argument("--jawiki", required=True)
    p.add_argument("--heldout-root", required=True, dest="heldout_root")
    p.add_argument("--placement", default=None)
    p.add_argument("--out", required=True)
    p.add_argument("--report", required=True)
    p.add_argument("--jobs", type=int, default=4)
    p.add_argument("--hash-inputs", action="store_true", dest="hash_inputs")
    p.add_argument("--sample-out", default=None, dest="sample_out")
    p.add_argument("--sample-n", type=int, default=60, dest="sample_n")
    p.set_defaults(fn=cmd_vocab)
    p = sub.add_parser("domain-db")
    p.add_argument("--codex-db", required=True, dest="codex_db")
    p.add_argument("--scene", default=None)
    p.add_argument("--control-of", default=None, dest="control_of")
    p.add_argument("--seed", type=int, default=20261005)
    p.add_argument("--out", required=True)
    p.add_argument("--report", required=True)
    p.set_defaults(fn=cmd_domain_db)
    p = sub.add_parser("domain-layer")
    p.add_argument("--domain-placement", required=True, dest="domain_placement")
    p.add_argument("--base", required=True)
    p.add_argument("--layer", required=True)
    p.add_argument("--ledger", required=True)
    p.add_argument("--domain", required=True)
    p.add_argument("--scene", required=True)
    p.add_argument("--rows-db", default=None, dest="rows_db")
    p.add_argument("--plan-cache", default=None, dest="plan_cache")
    p.add_argument("--reuse-written", action="store_true", dest="reuse_written")
    p.add_argument("--report", required=True)
    p.set_defaults(fn=cmd_domain_layer)
    p = sub.add_parser("combine")
    p.add_argument("--base", required=True)
    p.add_argument("--layer", action="append", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--ledger", required=True)
    p.add_argument("--report", required=True)
    p.set_defaults(fn=cmd_combine)
    p = sub.add_parser("capacity")
    p.add_argument("--layer", action="append", required=True)
    p.add_argument("--report", required=True)
    p.set_defaults(fn=cmd_capacity)
    a = ap.parse_args(argv)
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
