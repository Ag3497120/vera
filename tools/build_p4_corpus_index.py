"""Build separate, read-only-at-runtime text indexes for P4 from the codex corpus.

Usage:
    python tools/build_p4_corpus_index.py --root CORPUS_ROOT --out INDEX_DIR [--manifest FILE]
                                          [--family F ...] [--jobs N]

``--root`` falls back to the environment variable VERA_CODEX_CORPUS and ``--out``
to VERA_P4_INDEX; if either is unset the command stops with a typed message
(UNKNOWN_CORPUS_ROOT_UNSET / UNKNOWN_INDEX_OUT_UNSET). Nothing is assumed about
the home directory.

Design, in short:
  * One database per family; families are never merged and no row is shared.
  * ``SOURCES`` is the explicit table of which files and which record fields make
    up the searchable body of each family. A record whose shape is not in the
    table is counted under a typed reason, never silently dropped.
  * One physical input line is one index row, or one counted skip, so for every
    file ``lines == indexed + sum(skipped.values())``.
  * Only train-side files are listed. Paths with a ``heldout`` or
    ``overlap_dropped`` component are refused, and a record whose own ``split``
    key is not "train" is skipped.
  * ``HELDOUT`` lists, per family, the evaluation files. They are read by a separate
    function (``heldout_bodies``) that returns only body hashes, never rows or text.
    A train row whose body equals a heldout body of the same family is skipped by
    rule under the reason ``heldout_body_overlap`` and counted. A listed heldout
    file that is missing (UNKNOWN_HELDOUT_MISSING) or a heldout file in the corpus
    that no family lists (``heldout_unlisted``) stops the run with exit code 3.
  * Every row keeps family, source file, 1-based physical line number, record sha
    and the fields that formed the body, plus ``origin`` = "generated": these are
    sentences a model wrote, not testimony about the world.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sqlite3
import sys
import time
from pathlib import Path
from typing import Any, Iterator


FORMAT = "w1c-1"
ORIGIN = "generated"
GENERATOR = "codex"
SOURCE_TAG_PREFIX = "llm_authored:codex:"
EXCLUDED_PARTS = ("heldout", "overlap_dropped")
BATCH = 5000

# Kept only because tools/build_hf_package.py imports it. This CLI uses SOURCES.
INPUTS = {
    "local": "local/sentences.jsonl",
    "pro": "pro/sentences_2026-09-29.jsonl",
    "code": "code/items.jsonl",
    "conversation": "conversation/utterances.jsonl",
}

_TEXT_KIND = {"text": dict(body=("text",), required=("text",))}

# family -> files (explicit, train side only), the record kinds with the fields that
# form the body (in order, joined by newline) and the fields that must be present,
# plus the columns used for the scene and the group.
#
# A field name is "name" (a non-empty string), "name[*]" (a list of strings) or
# "name[*].sub" (a list of objects whose "sub" is a string).
# ``kind_key`` is the record key that selects the kind; None means a single kind
# that is labelled with the family name.
SOURCES: dict[str, dict] = {
    "pro": dict(files=("out/sentences.jsonl",), kind_key=None, kinds=_TEXT_KIND,
                scene=("scene", "topic"), grp="source"),
    "code": dict(files=("code/items.jsonl", "even/code/items.jsonl"), kind_key=None,
                 kinds=_TEXT_KIND, scene=("topic", "scene"), grp="source"),
    "conversation": dict(files=("conversation/utterances.jsonl", "even/conversation/utterances.jsonl"),
                         kind_key=None, kinds=_TEXT_KIND, scene=("scene", "topic"), grp="dialogue_id"),
    "general_qa": dict(
        files=("general_qa/train/records.jsonl",), kind_key="kind",
        kinds={k: dict(body=("q_variants[*]", "answer", "why"), required=("q_variants[*]", "answer"))
               for k in ("fact", "howto", "advice", "comparison", "definition", "needs_live_data", "greeting")},
        scene=("domain",), grp="source"),
    "code_qa": dict(
        files=("code_qa/train/records.jsonl",), kind_key=None,
        kinds={"code_qa": dict(body=("question", "answer_text", "code", "usage"),
                               required=("question", "answer_text"))},
        scene=("context",), grp="source"),
    "figurative_commonsense": dict(
        files=("figurative_commonsense/train/records.jsonl",), kind_key="kind",
        kinds={"pun": dict(body=("pun", "mechanism"), required=("pun",)),
               "haiku": dict(body=("haiku", "note"), required=("haiku",)),
               "simile_metaphor": dict(body=("expression", "plain_meaning", "example"), required=("expression",)),
               "cause_effect": dict(body=("cause", "effect", "phrasings[*]"), required=("cause", "effect"))},
        scene=("theme",), grp="source"),
    "narrative": dict(
        files=("narrative/train/records.jsonl",), kind_key="kind",
        kinds={"story": dict(body=("title", "sentences[*].text"), required=("title", "sentences[*].text")),
               "poem": dict(body=("title", "lines[*]"), required=("title", "lines[*]"))},
        scene=("setting",), grp="source"),
    "paraphrase_entail": dict(
        files=("paraphrase_entail/train/records.jsonl",), kind_key="kind",
        kinds={"pair": dict(body=("s1", "s2", "reason"), required=("s1", "s2")),
               "who_did_what": dict(body=("sentence", "question", "answer"),
                                    required=("sentence", "question", "answer"))},
        scene=("topic",), grp="source"),
}

# family -> heldout files (explicit). Read only by heldout_bodies(), never by the indexer.
# ``pro`` has no heldout file in the corpus (``out/`` holds train-side sentences only).
HELDOUT: dict[str, tuple[str, ...]] = {
    "pro": (),
    "code": ("code/heldout/items.jsonl", "even/code/heldout/items.jsonl"),
    "conversation": ("conversation/heldout/utterances.jsonl", "even/conversation/heldout/utterances.jsonl"),
    "general_qa": ("general_qa/heldout/records.jsonl",),
    "code_qa": ("code_qa/heldout/records.jsonl",),
    "figurative_commonsense": ("figurative_commonsense/heldout/records.jsonl",),
    "narrative": ("narrative/heldout/records.jsonl",),
    "paraphrase_entail": ("paraphrase_entail/heldout/records.jsonl",),
}

# used by the legacy build(path, output, family) for families that have no SOURCES entry
_GENERIC = dict(files=(), kind_key=None, kinds=_TEXT_KIND, scene=("scene", "topic"), grp="source")


class ExcludedPathError(RuntimeError):
    """An evaluation / dropped-overlap path was handed to the indexer."""


class _BadType(Exception):
    pass


def guard_path(rel: str) -> None:
    parts = Path(rel).parts
    if Path(rel).is_absolute() or ".." in parts:
        raise ExcludedPathError(f"path must be relative to the corpus root: {rel}")
    for part in parts:
        if part in EXCLUDED_PARTS:
            raise ExcludedPathError(f"{rel}: '{part}' is evaluation data and is never indexed")


# --------------------------------------------------------------------------- reading
def read_lines(path: Path, digest: "hashlib._Hash", counter: dict) -> Iterator[tuple[int, bytes, bool]]:
    """Yield (line_no, raw_line_without_newline, ends_with_newline).

    The file is opened in binary mode and cut on b"\\n" only, so line numbers equal
    ``wc -l`` / ``sed -n`` numbers. Only the first ``st_size`` bytes (taken at open
    time) are read; bytes, sha256 and line count come from this same read.
    """
    with path.open("rb") as handle:
        remaining = os.fstat(handle.fileno()).st_size
        carry = b""
        line_no = 0
        counter["bytes"] = 0
        while remaining > 0:
            chunk = handle.read(min(8 << 20, remaining))
            if not chunk:
                break
            remaining -= len(chunk)
            counter["bytes"] += len(chunk)
            digest.update(chunk)
            pieces = (carry + chunk).split(b"\n")
            carry = pieces.pop()
            for piece in pieces:
                line_no += 1
                yield line_no, piece, True
        if carry:
            line_no += 1
            yield line_no, carry, False
        counter["lines"] = line_no


# ------------------------------------------------------------------------ extraction
def _base(field: str) -> str:
    return field.split("[", 1)[0]


def _field_values(rec: dict, spec: str) -> list[str]:
    """Strings found under ``spec``; [] when absent/empty; raises _BadType on a wrong type."""
    name, _, rest = spec.partition("[*]")
    value = rec.get(name)
    if value is None:
        return []
    if not rest and "[*]" not in spec:
        if not isinstance(value, str):
            raise _BadType(spec)
        value = value.strip()
        return [value] if value else []
    if not isinstance(value, list):
        raise _BadType(spec)
    out: list[str] = []
    sub = rest[1:] if rest.startswith(".") else ""
    for item in value:
        if sub:
            if not isinstance(item, dict):
                raise _BadType(spec)
            item = item.get(sub)
            if item is None:
                continue
        if not isinstance(item, str):
            raise _BadType(spec)
        item = item.strip()
        if item:
            out.append(item)
    return out


def extract_body(rec: dict, family: str, spec: dict) -> tuple[str, str, list[str], list[str]]:
    """Return (kind, body, used_fields, optional_absent) or raise ValueError(reason)."""
    key = spec["kind_key"]
    if key is None:
        kind = next(iter(spec["kinds"]))  # a single kind, labelled with the family name below
    else:
        raw = rec.get(key)
        kind = raw if isinstance(raw, str) else ("(none)" if raw is None else str(raw))
        if kind not in spec["kinds"]:
            raise ValueError(f"unmapped_kind:{kind}")
    plan = spec["kinds"][kind]
    label = kind if key is not None else family
    values: dict[str, list[str]] = {}
    for field in dict.fromkeys(plan["required"] + plan["body"]):
        try:
            values[field] = _field_values(rec, field)
        except _BadType:
            raise ValueError(f"bad_field_type:{label}.{_base(field)}") from None
    for field in plan["required"]:
        if not values[field]:
            raise ValueError(f"missing_required:{label}.{_base(field)}")
    used = [f for f in plan["body"] if values[f]]
    absent = [f"{label}.{_base(f)}" for f in plan["body"] if f not in plan["required"] and not values[f]]
    body = "\n".join(v for f in plan["body"] for v in values[f])
    if not body.strip():
        raise ValueError("empty_body")
    return label, body, used, absent


def _column(rec: dict, names: tuple[str, ...] | str) -> str:
    for name in ((names,) if isinstance(names, str) else names):
        value = rec.get(name)
        if isinstance(value, str) and value:
            return value
    return ""


def _prefix(source: str) -> str | None:
    if not source.startswith(SOURCE_TAG_PREFIX):
        return None
    rest = source[len(SOURCE_TAG_PREFIX):]
    m = re.match(r"^(.*?)-b\d+$", rest)
    return m.group(1) if m else rest


def classify_line(raw: bytes, ends_nl: bool, family: str, spec: dict) -> tuple[str | None, dict | None]:
    """Return (skip_reason, row_or_None). One physical line gives exactly one of them."""
    if not ends_nl:
        return "partial_final_line", None
    if not raw.strip():
        return "blank_line", None
    try:
        rec = json.loads(raw.decode("utf-8"))
    except UnicodeDecodeError:
        return "bad_utf8", None
    except json.JSONDecodeError:
        return "bad_json", None
    if not isinstance(rec, dict):
        return "not_object", None
    if "split" in rec and rec["split"] != "train":
        return f"split_not_train:{rec['split']}", None
    if "family" in rec and rec["family"] != family:
        return f"family_mismatch:{rec['family']}", None
    try:
        kind, body, used, absent = extract_body(rec, family, spec)
    except ValueError as err:
        return str(err), None
    source = rec.get("source") if isinstance(rec.get("source"), str) else ""
    sha = rec.get("sha")
    return None, dict(
        text=body, source=source, scene=_column(rec, spec["scene"]), grp=_column(rec, spec["grp"]),
        sha=sha if isinstance(sha, str) else ("" if sha is None else str(sha)),
        kind=kind, fields=json.dumps(used, ensure_ascii=False),
        body_sha=hashlib.sha256(body.encode("utf-8")).hexdigest(),
        _split_absent="split" not in rec, _absent=absent)


# --------------------------------------------------------------------------- heldout
def heldout_bodies(root: Path, family: str) -> tuple[set[str], dict]:
    """Body sha256 set of the family's heldout files, plus a report. Returns no rows and no text.

    ``classify_line`` is not used: every heldout line says ``split: "heldout"`` and would
    be skipped as ``split_not_train``. ``extract_body`` is the same extraction the
    indexer uses, so the two hashes are comparable. Lines that give no body are counted
    by reason in the report (``unextractable``). ``guard_path`` is not applied here on
    purpose: it guards the index input, and this is a different path.
    """
    spec = SOURCES[family]
    bodies: set[str] = set()
    files: list[dict] = []
    records = 0
    for rel in HELDOUT[family]:
        digest, counter = hashlib.sha256(), {}
        unextractable: dict[str, int] = {}
        for _line_no, raw, ends_nl in read_lines(Path(root) / rel, digest, counter):
            reason = None
            if not ends_nl:
                reason = "partial_final_line"
            elif not raw.strip():
                reason = "blank_line"
            else:
                try:
                    rec = json.loads(raw.decode("utf-8"))
                except UnicodeDecodeError:
                    reason = "bad_utf8"
                except json.JSONDecodeError:
                    reason = "bad_json"
                else:
                    if not isinstance(rec, dict):
                        reason = "not_object"
                    else:
                        try:
                            body = extract_body(rec, family, spec)[1]
                        except ValueError as err:
                            reason = str(err)
            if reason is not None:
                _count(unextractable, reason)
                continue
            records += 1
            bodies.add(hashlib.sha256(body.encode("utf-8")).hexdigest())
        files.append(dict(path=rel, bytes=counter.get("bytes", 0), lines=counter.get("lines", 0),
                          sha256=digest.hexdigest(), unextractable=unextractable))
    return bodies, dict(files=files, records=records, distinct_bodies=len(bodies),
                        none_listed=not HELDOUT[family])


# ----------------------------------------------------------------------------- build
_SCHEMA = """
    PRAGMA journal_mode=OFF;
    PRAGMA synchronous=OFF;
    CREATE TABLE rows(id INTEGER PRIMARY KEY, text TEXT NOT NULL, source TEXT, scene TEXT, grp TEXT,
                      sha TEXT, family TEXT, source_file TEXT, line INTEGER, kind TEXT, fields TEXT,
                      origin TEXT, generator TEXT, body_sha TEXT);
    CREATE VIRTUAL TABLE search USING fts5(text, scene, content='rows', content_rowid='id',
                                            tokenize='trigram');
    CREATE TABLE meta(key TEXT PRIMARY KEY,value TEXT);
"""


def _count(table: dict, key: str, n: int = 1) -> None:
    table[key] = table.get(key, 0) + n


def build_db(files: list[tuple[Path, str]], output: Path, family: str, spec: dict,
             exclude_bodies: "frozenset[str] | set[str]" = frozenset(), heldout: dict | None = None) -> dict:
    """Build one family database from ``[(absolute path, name stored as source_file)]``.

    A row that would be indexed but whose body sha256 is in ``exclude_bodies`` (the family's
    heldout bodies) is skipped and counted as ``heldout_body_overlap``.
    """
    started = time.perf_counter()
    output.parent.mkdir(parents=True, exist_ok=True)
    tmp = output.with_suffix(".building")
    tmp.unlink(missing_ok=True)
    con = sqlite3.connect(tmp)
    con.executescript(_SCHEMA)
    row_id = 0
    batch: list[tuple] = []
    reports: list[dict] = []
    size_total, mtime_max = 0, 0
    try:
        for path, name in files:
            digest, counter = hashlib.sha256(), {}
            rep = dict(path=name, family=family, indexed=0, skipped={}, split_absent=0,
                       optional_absent={}, source_tag_prefixes={}, source_tag_unexpected=0)
            st = path.stat()
            size_total += st.st_size
            mtime_max = max(mtime_max, st.st_mtime_ns)
            last_newline = True
            for line_no, raw, ends_nl in read_lines(path, digest, counter):
                last_newline = ends_nl
                reason, row = classify_line(raw, ends_nl, family, spec)
                if reason is not None:
                    _count(rep["skipped"], reason)
                    continue
                if row["body_sha"] in exclude_bodies:
                    _count(rep["skipped"], "heldout_body_overlap")
                    continue
                row_id += 1
                rep["indexed"] += 1
                rep["split_absent"] += row.pop("_split_absent")
                for key in row.pop("_absent"):
                    _count(rep["optional_absent"], key)
                prefix = _prefix(row["source"])
                if prefix is None:
                    rep["source_tag_unexpected"] += 1
                else:
                    _count(rep["source_tag_prefixes"], prefix)
                batch.append((row_id, row["text"], row["source"], row["scene"], row["grp"], row["sha"],
                              family, name, line_no, row["kind"], row["fields"], ORIGIN, GENERATOR,
                              row["body_sha"]))
                if len(batch) >= BATCH:
                    con.executemany("INSERT INTO rows VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)", batch)
                    batch.clear()
            rep.update(bytes=counter.get("bytes", 0), lines=counter.get("lines", 0),
                       sha256=digest.hexdigest(), final_newline=last_newline)
            rep["balanced"] = rep["lines"] == rep["indexed"] + sum(rep["skipped"].values())
            reports.append(rep)
        if batch:
            con.executemany("INSERT INTO rows VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)", batch)
        con.execute("INSERT INTO search(search) VALUES ('rebuild')")
        con.execute("CREATE INDEX ix_group ON rows(grp,id)")
        con.execute("CREATE INDEX ix_body ON rows(body_sha)")
        skipped: dict[str, int] = {}
        for rep in reports:
            for reason, n in rep["skipped"].items():
                _count(skipped, reason, n)
        con.executemany("INSERT INTO meta VALUES (?,?)", [
            ("size", str(size_total)), ("mtime_ns", str(mtime_max)), ("rows", str(row_id)),
            ("family", family), ("format", FORMAT), ("origin", ORIGIN),
            ("files", json.dumps(reports, ensure_ascii=False)),
            ("skipped", json.dumps(skipped, ensure_ascii=False))]
            + ([("heldout", json.dumps(heldout, ensure_ascii=False))] if heldout is not None else []))
        con.commit()
    finally:
        con.close()
    tmp.replace(output)
    return dict(state="BUILT", db=str(output), rows=row_id, db_bytes=output.stat().st_size,
                elapsed_seconds=round(time.perf_counter() - started, 3), files=reports,
                **({} if heldout is None else {"heldout": heldout}))


def build(path: Path, output: Path, family: str) -> int:
    """Legacy entry: one jsonl file -> one family database; returns the indexed row count."""
    path, output = Path(path), Path(output)
    stat = path.stat()
    if output.exists():
        con = sqlite3.connect(f"file:{output}?mode=ro", uri=True)
        try:
            meta = dict(con.execute("SELECT key,value FROM meta"))
            if (meta.get("size") == str(stat.st_size) and meta.get("mtime_ns") == str(stat.st_mtime_ns)
                    and meta.get("format") == FORMAT):
                return int(meta["rows"])
        except sqlite3.DatabaseError:
            pass
        finally:
            con.close()
    spec = SOURCES.get(family, _GENERIC)
    return build_db([(path, str(path))], output, family, spec)["rows"]


# --------------------------------------------------------------------------- the CLI
def _hash_file(path: Path) -> dict:
    digest, counter = hashlib.sha256(), {}
    for _ in read_lines(path, digest, counter):
        pass
    return dict(bytes=counter.get("bytes", 0), lines=counter.get("lines", 0), sha256=digest.hexdigest())


def _find_excluded(root: Path) -> list[dict]:
    found = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d != "__pycache__")
        parts = Path(dirpath).relative_to(root).parts
        reason = next((p for p in parts if p in EXCLUDED_PARTS), None)
        if reason:
            for name in sorted(filenames):
                path = Path(dirpath) / name
                found.append(dict(path=str(path.relative_to(root)), reason=reason, **_hash_file(path)))
    return sorted(found, key=lambda e: e["path"])


def _find_heldout_unlisted(root: Path) -> list[str]:
    """Heldout files found under the corpus root that no family lists in HELDOUT."""
    listed = {rel for paths in HELDOUT.values() for rel in paths}
    found = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d != "__pycache__")
        for name in sorted(filenames):
            rel = str((Path(dirpath) / name).relative_to(root))
            if any(p == "heldout" or Path(p).stem == "heldout" for p in Path(rel).parts) and rel not in listed:
                found.append(rel)
    return sorted(found)


def _family_job(args: tuple) -> tuple[str, dict]:
    root, out, family, spec = args
    for rel in spec["files"]:
        guard_path(rel)
    files = [(Path(root) / rel, rel) for rel in spec["files"]]
    bodies, report = heldout_bodies(Path(root), family)     # in the child: only hashes cross this line
    return family, build_db(files, Path(out) / (family + ".db"), family, spec,
                            exclude_bodies=frozenset(bodies), heldout=report)


def _git_head() -> str:
    import subprocess
    try:
        return subprocess.run(["git", "-C", str(Path(__file__).resolve().parents[1]), "rev-parse", "HEAD"],
                              capture_output=True, text=True, timeout=10).stdout.strip() or "UNKNOWN"
    except (OSError, subprocess.SubprocessError):
        return "UNKNOWN"


def _typed_exit(state: str, message: str) -> int:
    print(json.dumps({"state": state, "message": message}, ensure_ascii=False), file=sys.stderr)
    return 2


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--root", type=Path, default=None, help="codex corpus root (or VERA_CODEX_CORPUS)")
    p.add_argument("--out", type=Path, default=None, help="index directory (or VERA_P4_INDEX)")
    p.add_argument("--manifest", type=Path, default=None, help="write the reconciliation manifest here")
    p.add_argument("--family", action="append", choices=sorted(SOURCES), default=None,
                   help="build only this family (repeatable); default: all")
    p.add_argument("--jobs", type=int, default=1, help="families built in parallel processes")
    args = p.parse_args(argv)
    root = args.root or (Path(os.environ["VERA_CODEX_CORPUS"]) if os.environ.get("VERA_CODEX_CORPUS") else None)
    if root is None:
        return _typed_exit("UNKNOWN_CORPUS_ROOT_UNSET", "give --root or set VERA_CODEX_CORPUS")
    out = args.out or (Path(os.environ["VERA_P4_INDEX"]) if os.environ.get("VERA_P4_INDEX") else None)
    if out is None:
        return _typed_exit("UNKNOWN_INDEX_OUT_UNSET", "give --out or set VERA_P4_INDEX")
    started_at = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    t0 = time.perf_counter()
    families = [f for f in SOURCES if args.family is None or f in args.family]
    jobs, results, missing_any = [], {}, False
    for family in families:
        spec = SOURCES[family]
        for rel in spec["files"]:
            guard_path(rel)
        missing = [rel for rel in spec["files"] if not (root / rel).is_file()]
        missing_heldout = [rel for rel in HELDOUT[family] if not (root / rel).is_file()]
        if missing:
            results[family] = dict(state="UNKNOWN_SOURCE_MISSING", missing=missing)
            missing_any = True
            print(f"{family}: UNKNOWN_SOURCE_MISSING {missing}", flush=True)
        elif missing_heldout:
            # without the heldout files the exclusion rule cannot be applied: do not build
            results[family] = dict(state="UNKNOWN_HELDOUT_MISSING", missing_heldout=missing_heldout)
            missing_any = True
            print(f"{family}: UNKNOWN_HELDOUT_MISSING {missing_heldout}", flush=True)
        else:
            jobs.append((str(root), str(out), family, spec))
    done = []
    if args.jobs > 1 and len(jobs) > 1:
        from concurrent.futures import ProcessPoolExecutor, as_completed
        with ProcessPoolExecutor(max_workers=args.jobs) as pool:
            for future in as_completed([pool.submit(_family_job, job) for job in jobs]):
                done.append(future.result())
                print(f"{done[-1][0]}: {done[-1][1]['rows']} rows in {done[-1][1]['elapsed_seconds']}s", flush=True)
    else:
        for job in jobs:
            done.append(_family_job(job))
            print(f"{done[-1][0]}: {done[-1][1]['rows']} rows in {done[-1][1]['elapsed_seconds']}s", flush=True)
    for family, result in done:
        results[family] = result
    files = [dict(rep) for family in families if results[family]["state"] == "BUILT"
             for rep in results[family]["files"]]
    excluded = _find_excluded(Path(root))
    heldout_unlisted = _find_heldout_unlisted(Path(root))
    if heldout_unlisted:
        missing_any = True
        print(f"heldout_unlisted: {heldout_unlisted}", flush=True)
    manifest = dict(
        corpus_root=str(root), index_out=str(out), git_head=_git_head(), python=sys.version.split()[0],
        sqlite_version=sqlite3.sqlite_version, format=FORMAT, started_at=started_at,
        finished_at=time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        elapsed_seconds=round(time.perf_counter() - t0, 3),
        files=files,
        families={f: {k: v for k, v in results[f].items() if k != "files"} for f in families},
        excluded=excluded, heldout_unlisted=heldout_unlisted)
    if args.manifest:
        args.manifest.parent.mkdir(parents=True, exist_ok=True)
        args.manifest.write_text(json.dumps(manifest, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    unbalanced = [f["path"] for f in files if not f["balanced"]]
    if unbalanced:
        print(json.dumps({"state": "UNBALANCED", "files": unbalanced}), file=sys.stderr)
        return 4
    return 3 if missing_any else 0


if __name__ == "__main__":
    sys.exit(main())
