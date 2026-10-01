"""Build separate QA/prose/jawiki evidence indexes; never read heldout records."""
from __future__ import annotations

import argparse
import hashlib
import json
import statistics
import sqlite3
import time
from pathlib import Path

from verantyx.evidence_library import EvidenceLibrary
from verantyx.family_library import FamilyLibrary
from verantyx.answer_slots import read_slot


def source_records(paths: list[Path], family: str, offsets: dict[str, int] | None = None):
    offsets = offsets or {}
    for path in paths:
        size = path.stat().st_size
        with path.open("rb") as stream:
            offset = offsets.get(str(path), 0)
            if offset > size:
                raise ValueError("source was truncated: " + str(path))
            stream.seek(offset)
            while stream.tell() < size:
                line = stream.readline(size - stream.tell())
                if not line.endswith(b"\n"):
                    break
                try:
                    row = json.loads(line)
                except (ValueError, UnicodeDecodeError):
                    yield {"_skip": True, "_file": str(path), "_offset": stream.tell()}
                    continue
                if not isinstance(row, dict):
                    yield {"_skip": True, "_file": str(path), "_offset": stream.tell()}
                    continue
                if "verdict" in row or row.get("split", "train") != "train":
                    yield {"_skip": True, "_file": str(path), "_offset": stream.tell()}
                    continue
                if family == "jawiki":
                    yield dict(row, _file=str(path), _offset=stream.tell())
                    continue
                sentences = row.get("sentences") or []
                if isinstance(sentences, str):
                    sentences = [sentences]
                if not sentences:
                    sentences = [row.get("text") or ""]
                source = str(row.get("source") or path.name)
                sha = str(row.get("sha") or hashlib.sha256(line).hexdigest())
                cleaned = []
                for text in sentences:
                    if isinstance(text, dict):
                        text = text.get("text") or ""
                    if text:
                        cleaned.append(str(text))
                if cleaned:
                    yield {"text": "\n".join(cleaned), "source": source + ":" + sha,
                           "sha": sha, "independent": source}
                yield {"_skip": True, "_file": str(path), "_offset": stream.tell()}


def build(corpus: Path, output: Path, families: tuple[str, ...], *, probes: int = 30) -> dict:
    results = {}
    for family in families:
        directory = output / family / "evidence"
        if family == "general_qa":
            imported = FamilyLibrary.build(corpus, family, output / family)
            result = imported["evidence"]
            result["train_records"] = imported["rows"]
            relation = FamilyLibrary.build(corpus, "paraphrase_entail", output / "paraphrase_entail")
            with sqlite3.connect(f"file:{output / 'paraphrase_entail/family.db'}?mode=ro", uri=True) as con:
                result["predicate_relations"] = con.execute("SELECT COUNT(*) FROM predicate_relations").fetchone()[0]
            result["relation_build_s"] = relation["build_s"]
        else:
            paths = ([corpus / "codex/local/sentences.jsonl"] if family == "local" else
                     sorted((corpus / "codex/pro").glob("*.jsonl")) if family == "pro" else
                     [corpus / "build/round4/jawiki_leads.jsonl"])
            paths = [path for path in paths if path.is_file() and "heldout" not in path.parts]
            offsets = {}
            if (directory / "evidence.db").exists():
                with sqlite3.connect(f"file:{directory / 'evidence.db'}?mode=ro", uri=True) as con:
                    offsets = dict(con.execute("SELECT path,offset FROM offsets"))
            result = EvidenceLibrary.build(directory, family, source_records(paths, family, offsets))
            result["source_files"] = len(paths)
        library = EvidenceLibrary(directory, family)
        timings = []
        for subject, context, text, slot in library.con.execute(
                "SELECT subject,context,text,slot FROM rows ORDER BY id LIMIT ?", (probes,)):
            query = read_slot(context or text, slot or "what")
            start = time.perf_counter()
            library.candidates(query)
            timings.append((time.perf_counter() - start) * 1000)
        if timings:
            result.update(median_ms=round(statistics.median(timings), 3),
                          p95_ms=round(sorted(timings)[max(0, int(len(timings) * .95) - 1)], 3))
        library.close()
        results[family] = result
        print(json.dumps(result, ensure_ascii=False), flush=True)
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", type=Path, default=Path.home() / "Projects/vera-corpus")
    parser.add_argument("--out", type=Path)
    parser.add_argument("--families", nargs="+", choices=("general_qa", "local", "pro", "jawiki"),
                        default=["general_qa", "local", "pro", "jawiki"])
    parser.add_argument("--probes", type=int, default=30)
    args = parser.parse_args()
    results = build(args.corpus, args.out or args.corpus / "build/round3", tuple(args.families), probes=args.probes)
    manifest = args.corpus / "build/round4/build.json"
    manifest.parent.mkdir(parents=True, exist_ok=True)
    previous = json.loads(manifest.read_text()) if manifest.exists() else {}
    manifest.write_text(json.dumps(dict(previous, **results), ensure_ascii=False, indent=2) + "\n")


if __name__ == "__main__":
    main()
