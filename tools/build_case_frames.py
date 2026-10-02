"""Build a small count-only case-role table from licensed train clauses.

The corpus reader accepts only files explicitly marked train and belonging to
the three configured source families.  Wikipedia leads come from the existing
read_coverage helpers.  No source sentence is written to the output table.
"""
from __future__ import annotations

import argparse
import collections
import inspect
import json
import os
import re
from pathlib import Path
from typing import Iterable, Iterator, Mapping

ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT / "verantyx" / "data" / "case_frames.json"
DATASETS = frozenset(("paraphrase_entail", "general_qa", "narrative"))
PARTICLES = frozenset(("に", "で", "と"))
CASE_PARTICLES = frozenset(("が", "を", "に", "で", "と", "から", "まで", "へ"))
BLOCKED_PARTS = frozenset(("dev", "heldout", "sealed", "round5-dev", "round5_dev",
                           "fixture", "fixtures"))
COMPOUNDS = ("における", "において", "について", "に対して", "によって", "による",
             "により", "として", "と共に", "ともに", "では")
MIN_COUNT = 8
CLEAR_MAJORITY = 0.80
TEXT_KEYS = ("text", "sentence", "sentences", "premise", "hypothesis", "context",
             "passage", "paragraph", "content", "source_text", "statement",
             "lead", "lead_text")
ROLE_PARTICLES = {
    "に": frozenset(("agent", "recipient", "goal", "location", "time", "purpose")),
    "で": frozenset(("place", "means", "time", "location")),
    "と": frozenset(("companion", "quotation")),
}


def _parts(path: Path) -> set[str]:
    return {part for part in re.split(r"[^a-z0-9]+", str(path).lower()) if part}


def _training_files(root: Path) -> Iterator[tuple[str, Path]]:
    if not root.is_dir():
        raise FileNotFoundError(f"training corpus directory is unavailable: {root}")
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.is_symlink() or path.name.lower() == "fixtures.jsonl":
            continue
        parts = _parts(path)
        if parts & BLOCKED_PARTS or not parts & DATASETS or "train" not in parts:
            continue
        if path.suffix.lower() not in (".jsonl", ".json", ".txt"):
            continue
        dataset = next((name for name in sorted(DATASETS) if name in parts), None)
        if dataset is not None:
            yield dataset, path


def _record_values(value: object) -> Iterator[str]:
    if isinstance(value, str):
        text = value.strip()
        if text:
            yield text
        return
    if isinstance(value, list):
        for item in value:
            yield from _record_values(item)
        return
    if not isinstance(value, Mapping):
        return
    split = value.get("split")
    if isinstance(split, str) and split.strip().lower() != "train":
        return
    for key in TEXT_KEYS:
        if key in value:
            yield from _record_values(value[key])


def _file_records(path: Path) -> Iterator[object]:
    if path.suffix.lower() == ".txt":
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                if line.strip():
                    yield line
        return
    if path.suffix.lower() == ".jsonl":
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                if not line.strip():
                    continue
                try:
                    yield json.loads(line)
                except json.JSONDecodeError:
                    continue
        return
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return
    yield value


def corpus_sentences(root: Path | None = None) -> Iterator[tuple[str, str]]:
    """Yield (source family, sentence text) from the allowed train families."""
    if root is None:
        root = Path(os.environ.get("VERA_CORPUS_DIR", Path.home() / "vera-codex-corpus"))
    for dataset, path in _training_files(root):
        for record in _file_records(path):
            for text in _record_values(record):
                yield dataset, text


def _helper_call(function):
    try:
        signature = inspect.signature(function)
    except (TypeError, ValueError):
        return None
    kwargs = {}
    for name, parameter in signature.parameters.items():
        if parameter.kind in (parameter.VAR_POSITIONAL, parameter.VAR_KEYWORD):
            continue
        if parameter.default is not inspect.Parameter.empty:
            continue
        if name in ("split", "partition"):
            kwargs[name] = "train"
        elif name in ("n", "limit", "count", "max_items"):
            kwargs[name] = 1500
        elif name == "stride":
            kwargs[name] = 1
        elif name in ("path", "source", "filename") and os.environ.get("VERA_LEADS"):
            kwargs[name] = os.environ["VERA_LEADS"]
        else:
            return None
    try:
        return function(**kwargs)
    except (OSError, RuntimeError, TypeError, ValueError):
        return None


def wikipedia_leads() -> Iterator[str]:
    """Read train Wikipedia leads through tools.read_coverage's public helpers."""
    try:
        from tools import read_coverage
    except Exception as exc:
        raise RuntimeError("could not import tools.read_coverage helpers") from exc

    preferred = ("iter_train_leads", "train_leads", "read_train_leads",
                 "load_train_leads", "iter_leads", "read_leads", "load_leads")
    candidates = []
    for name in preferred:
        candidate = getattr(read_coverage, name, None)
        if callable(candidate):
            candidates.append((name, candidate))
    if not candidates:
        candidates = [
            (name, value) for name, value in vars(read_coverage).items()
            if not name.startswith("_") and "lead" in name.lower() and callable(value)
            and name not in ("main",)
        ]
    for name, function in candidates:
        result = _helper_call(function)
        if result is None:
            continue
        if isinstance(result, Mapping):
            rows: Iterable[object] = (result,)
        else:
            try:
                rows = iter(result)
            except TypeError:
                continue
        found = False
        for row in rows:
            if isinstance(row, Mapping):
                split = row.get("split")
                if isinstance(split, str) and split.lower() != "train":
                    continue
                values = tuple(_record_values(row))
            elif isinstance(row, (tuple, list)) and row:
                # Helpers sometimes return (id, text, split) or (text, split).
                split_values = [item.lower() for item in row if isinstance(item, str)
                                and item.lower() in ("train", "dev", "heldout", "sealed")]
                if split_values and any(value != "train" for value in split_values):
                    continue
                fields = [item for item in row if not (isinstance(item, str)
                          and item.lower() in ("train", "dev", "heldout", "sealed"))]
                if not fields:
                    continue
                if split_values:
                    candidate = max((item for item in fields if isinstance(item, str)),
                                    key=len, default=None)
                    values = tuple(_record_values(candidate))
                else:
                    values = tuple(_record_values(row[-1]))
            else:
                values = tuple(_record_values(row))
            for value in values:
                found = True
                yield value
        if found:
            return
        if "train" in name.lower():
            return
    raise RuntimeError("tools.read_coverage exposed no usable train-lead helper")


def _compound_particle(sentence: str, start: int) -> bool:
    return any(sentence.startswith(compound, start) for compound in COMPOUNDS)


def _licensed_observations(clause, sentence: str, tagger_tokens) -> list[tuple[str, str, str]] | None:
    """Independently check complete source spans and one licensed phrase per case."""
    if clause.rule != "frame" or clause.unsupported:
        return None
    if (clause.span.start < 0 or clause.span.end > len(sentence)
            or clause.span.start >= clause.span.end
            or sentence[clause.span.start:clause.span.end] != clause.span.text
            or not (clause.span.start <= clause.predicate_span.start
                    < clause.predicate_span.end <= clause.span.end)
            or sentence[clause.predicate_span.start:clause.predicate_span.end]
            != clause.predicate_span.text):
        return None
    for role in clause.roles:
        if (role.span.source != clause.span.source or role.span.start < clause.span.start
                or role.span.end > clause.span.end or role.span.start >= role.span.end
                or sentence[role.span.start:role.span.end] != role.span.text):
            return None

    observed = []
    for index, (word, start, end) in enumerate(tagger_tokens):
        if (start < clause.span.start or end > clause.predicate_span.start
                or word.feature.pos1 != "助詞" or word.feature.pos2 != "格助詞"
                or word.surface not in PARTICLES):
            continue
        if _compound_particle(sentence, start):
            continue
        attached = [role for role in clause.roles if role.span.end == start]
        if len(attached) != 1:
            return None
        role = attached[0]
        if role.name not in ROLE_PARTICLES[word.surface]:
            return None
        observed.append((word.surface, role.name, role.span.text))
    if not observed:
        return []
    counts = collections.Counter(particle for particle, _, _ in observed)
    if any(number != 1 for number in counts.values()):
        return None
    # Every role immediately followed by one of the target particles must be
    # represented by the same tagged token used above.
    assigned = {(particle, phrase) for particle, _, phrase in observed}
    for role in clause.roles:
        for particle in PARTICLES:
            if sentence[role.span.end:role.span.end + len(particle)] == particle:
                if (particle, role.span.text) not in assigned:
                    return None
    return [(clause.predicate, particle, role) for particle, role, _ in observed]


def build_counts(sentences: Iterable[str], *, min_count: int = MIN_COUNT,
                 clear_majority: float = CLEAR_MAJORITY) -> dict:
    """Read sentences and count only unambiguous, source-licensed case roles."""
    if type(min_count) is not int or min_count < 1:
        raise ValueError("min_count must be a positive integer")
    if type(clear_majority) not in (float, int) or not 0.5 < float(clear_majority) <= 1.0:
        raise ValueError("clear_majority must be greater than one half and at most one")
    from verantyx.semantic_reader import _sentences, _tokens, document_view

    totals: dict[str, dict[str, collections.Counter[str]]] = collections.defaultdict(
        lambda: collections.defaultdict(collections.Counter))
    previous_off = os.environ.get("VERA_CONSTRUCTIONS_OFF")
    disabled = {item.strip() for item in (previous_off or "").split(",") if item.strip()}
    disabled.add("case_frames")
    os.environ["VERA_CONSTRUCTIONS_OFF"] = ",".join(sorted(disabled))
    try:
        serial = 0
        for text in sentences:
            if not isinstance(text, str):
                continue
            for start, end in _sentences(text):
                sentence = text[start:end]
                if not sentence.strip():
                    continue
                serial += 1
                source = f"case_frame_train_{serial}"
                view = document_view({source: sentence}, family="case_frame_build")
                if view.unread:
                    continue
                tagged = _tokens(sentence)
                for clause in view.clauses:
                    if clause.unsupported:
                        continue
                    observations = _licensed_observations(clause, sentence, tagged)
                    if observations is None:
                        continue
                    for predicate, particle, role in observations:
                        if particle in PARTICLES:
                            totals[predicate][particle][role] += 1
    finally:
        if previous_off is None:
            os.environ.pop("VERA_CONSTRUCTIONS_OFF", None)
        else:
            os.environ["VERA_CONSTRUCTIONS_OFF"] = previous_off

    frames = {
        predicate: {
            particle: dict(sorted(counts.items()))
            for particle, counts in sorted(by_particle.items()) if counts
        }
        for predicate, by_particle in sorted(totals.items()) if by_particle
    }
    return {"schema_version": 1, "min_count": min_count,
            "clear_majority": float(clear_majority), "frames": frames}


def build_training_table(corpus_root: Path | None = None) -> dict:
    """Combine the three train families and train Wikipedia leads."""
    rows = list(corpus_sentences(corpus_root))
    leads = list(wikipedia_leads())
    return build_counts([text for _, text in rows] + leads)


def save_table(table: Mapping[str, object], output: Path = OUTPUT) -> None:
    if output.resolve() != OUTPUT.resolve():
        raise ValueError("case-frame output is fixed to verantyx/data/case_frames.json")
    output.write_text(json.dumps(table, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
                      encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus-root", type=Path, default=None)
    args = parser.parse_args(argv)
    table = build_training_table(args.corpus_root)
    save_table(table)
    print(f"wrote {sum(sum(sum(p.values()) for p in v.values()) for v in table['frames'].values())} licensed counts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
