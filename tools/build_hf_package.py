"""Assemble Vera base, its four ability indexes and round-3 build command."""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import shutil
import sqlite3
import tempfile
from pathlib import Path

try:
    from tools.build_p4_corpus_index import INPUTS, build as build_ability_index
except ModuleNotFoundError:  # direct ``python tools/build_hf_package.py``
    from build_p4_corpus_index import INPUTS, build as build_ability_index

ROOT = Path(__file__).resolve().parent.parent
BUILD = Path.home() / "Projects/vera-corpus/build"
START = ("one", "base", "bot", "chat", "answer", "abilities", "question", "cascade",
         "document_loaders", "document_structure", "library", "remedy",
         "gap_graph", "vera", "skills", "core_abilities", "crossverify")


def closure() -> list[str]:
    """Follow relative and verantyx imports, including `from . import x`."""
    seen: set[str] = set()
    todo = list(START)
    source_dir = ROOT / "verantyx"
    while todo:
        name = todo.pop()
        path = source_dir / (name + ".py")
        if name in seen or not path.is_file():
            continue
        seen.add(name)
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.ImportFrom):
                module = node.module or ""
                if node.level and module:
                    todo.append(module.split(".")[0])
                elif node.level:
                    todo.extend(alias.name for alias in node.names)
                elif module == "verantyx":
                    todo.extend(alias.name for alias in node.names)
                elif module.startswith("verantyx."):
                    todo.append(module.split(".")[1])
            elif isinstance(node, ast.Import):
                todo.extend(alias.name.split(".")[1] for alias in node.names
                            if alias.name.startswith("verantyx."))
    return sorted(seen)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sync_runtime(out: Path) -> dict:
    """Refresh runtime source without deleting modules or copying corpus databases."""
    modules = closure()
    package = out / "vera_base" / "verantyx"
    package.mkdir(parents=True, exist_ok=True)
    for name in modules:
        shutil.copy2(ROOT / "verantyx" / (name + ".py"), package / (name + ".py"))
    for source, destination in (("build_round3.py", "round3_build.py"),
                                ("build_round4.py", "round4_build.py"),
                                ("build_jawiki_leads.py", "jawiki_build.py")):
        shutil.copy2(ROOT / "tools" / source, out / "vera_base" / destination)
    return {"modules": len(modules), "output": str(out), "assets": "preserved; no database copies",
            "round4": "python -m vera_base.round4_build"}


def _indexed_source(source: Path, index: Path, family: str) -> tuple[int, int]:
    """Index one complete newline-delimited snapshot of a growing corpus."""
    size = source.stat().st_size
    if index.is_file():
        with sqlite3.connect(f"file:{index}?mode=ro", uri=True) as con:
            meta = dict(con.execute("SELECT key,value FROM meta"))
        if meta.get("size") == str(size) and meta.get("mtime_ns") == str(source.stat().st_mtime_ns):
            return int(meta["rows"]), size
    with tempfile.TemporaryDirectory(prefix=f"vera-{family}-") as temp:
        snapshot = Path(temp) / source.name
        remaining = size
        with source.open("rb") as inp, snapshot.open("wb") as out:
            while remaining:
                chunk = inp.read(min(8 * 1024 * 1024, remaining))
                if not chunk:
                    break
                out.write(chunk)
                remaining -= len(chunk)
        with snapshot.open("rb+") as stream:
            end = stream.seek(0, 2)
            if end:
                stream.seek(-1, 2)
            if end and stream.read(1) != b"\n":
                start = max(0, end - 1024 * 1024)
                stream.seek(start)
                tail = stream.read()
                last = tail.rfind(b"\n")
                stream.truncate(start + last + 1 if last >= 0 else 0)
        rows = build_ability_index(snapshot, index, family)
        return rows, snapshot.stat().st_size


def build(out: Path, corpus_build: Path = BUILD, p4_root: Path = ROOT / "build/p4") -> dict:
    modules = closure()
    stale_build = out / "build"
    if stale_build.exists():
        shutil.rmtree(stale_build)
    pkg = out / "vera_base" / "verantyx"
    if pkg.exists():
        shutil.rmtree(pkg)
    pkg.mkdir(parents=True)
    for name in modules:
        shutil.copy2(ROOT / "verantyx" / (name + ".py"), pkg / (name + ".py"))
    shutil.copy2(ROOT / "tools" / "build_round3.py", out / "vera_base" / "round3_build.py")
    shutil.copy2(ROOT / "tools" / "build_round4.py", out / "vera_base" / "round4_build.py")
    shutil.copy2(ROOT / "tools" / "build_jawiki_leads.py", out / "vera_base" / "jawiki_build.py")
    (pkg / "__init__.py").write_text('"""Vera base packaged Verantyx runtime."""\n', encoding="utf-8")
    shutil.copytree(ROOT / "verantyx" / "lang_data", pkg / "lang_data",
                    ignore=shutil.ignore_patterns("ja_domain_disaster.json"))
    data = out / "vera_base" / "data"
    data.mkdir(parents=True, exist_ok=True)
    pack = json.loads((corpus_build / "chat_pack.json").read_text(encoding="utf-8"))
    # Pack-only mode keeps short composed text/counts, not redistributable
    # witness sentences. Live provenance requires the separately fetched DB.
    slim = {k: {"text": v["text"], "evidence": [], "sources": v.get("sources", [])}
            for k, v in pack.items() if v.get("text")}
    (data / "chat_pack.json").write_text(json.dumps(slim, ensure_ascii=False), encoding="utf-8")
    shutil.copy2(corpus_build / "pun_lexicon.json", data / "pun_lexicon.json")
    # The writer and full ability indexes travel with the package.
    bundled_build = out / "vera_base" / "vera-corpus" / "build"
    bundled_build.mkdir(parents=True, exist_ok=True)
    shutil.copy2(corpus_build / "writer.json", bundled_build / "writer.json")
    # The source map names entire corpus families. Rebuild changed families
    # before copying; no evaluation topic list enters the index builder.
    p4_data = out / "vera_base" / "build" / "p4"
    p4_data.mkdir(parents=True, exist_ok=True)
    manifest = {}
    for family, relative in INPUTS.items():
        source = corpus_build.parent / "codex" / relative
        if not source.is_file():
            raise FileNotFoundError(f"whole-corpus ability source missing: {source}")
        index = p4_root / (family + ".db")
        rows, indexed_bytes = _indexed_source(source, index, family)
        target = p4_data / index.name
        shutil.copy2(index, target)
        if _sha256(index) != (checksum := _sha256(target)):
            raise IOError(f"ability index copy failed verification: {family}")
        with sqlite3.connect(f"file:{target}?mode=ro", uri=True) as con:
            meta = dict(con.execute("SELECT key,value FROM meta"))
            if int(meta["rows"]) != rows or meta["size"] != str(indexed_bytes):
                raise ValueError(f"ability index is not the whole {family} corpus")
        manifest[family] = {"rows": rows, "bytes": target.stat().st_size,
                            "sha256": checksum, "indexed_source_bytes": indexed_bytes,
                            "source_bytes_at_package": source.stat().st_size}
    (p4_data / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    (out / "vera_base" / "__init__.py").write_text('''"""Vera base: model-free document, chat and verdict entry points."""
import os, sys
from pathlib import Path
_here = Path(__file__).resolve().parent
os.environ.setdefault("VERA_CORPUS_ROOT", str(_here / "vera-corpus"))
os.environ.setdefault("VERA_GENERAL", str(_here / "data" / "general.db"))
os.environ.setdefault("VERA_PACK", str(_here / "data" / "chat_pack.json"))
os.environ.setdefault("VERA_PUN_LEXICON", str(_here / "data" / "pun_lexicon.json"))
sys.path.insert(0, str(_here))
from verantyx.one import Vera
from verantyx.bot import Bot
from verantyx.chat import Chat
from verantyx.base import Base
from verantyx.verdict import judge, read_records
from verantyx.crossverify import verify as crossverify
''', encoding="utf-8")
    size = sum(f.stat().st_size for f in (out / "vera_base").rglob("*") if f.is_file())
    return {"modules": len(modules), "package_mb": round(size / 1024 ** 2, 2),
            "ability_rows": {k: v["rows"] for k, v in manifest.items()},
            "pack_topics": len(slim), "round3": "build separately with python -m vera_base.round3_build",
            "output": str(out)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=Path.home() / "Projects/vera-base-ja")
    parser.add_argument("--corpus-build", type=Path, default=BUILD)
    parser.add_argument("--runtime-only", action="store_true", help="preserve existing data and sync source only")
    args = parser.parse_args()
    print(json.dumps(sync_runtime(args.out) if args.runtime_only else build(args.out, args.corpus_build), ensure_ascii=False))


if __name__ == "__main__":
    main()
