"""Capped, scene-grouped Japanese sentence library.

The on-disk format is a versioned pickle of the built tree and leaf payloads.
Only load a library directory you trust: pickle is not safe for untrusted input.
"""
from __future__ import annotations

import math
import pickle
import time
from collections import defaultdict
from itertools import islice
from pathlib import Path
from typing import Iterable, Mapping

from verantyx import conduct_tree
from verantyx.bot import _ja_words
from verantyx.cross_store import CrossStore
from verantyx.document_ingest import Document, ingest_documents
from verantyx.hierarchy import Node
from verantyx.lang import ja_content_runs
from verantyx.sovereign import _kanji, group_into_layers
from verantyx.verdict import read_records

LEAF_CAP = 400
FRAME_CAP = 2000
FORMAT_VERSION = 2


class Library:
    def __init__(self, leaf_cap: int = LEAF_CAP, frame_cap: int = FRAME_CAP):
        if leaf_cap < 1 or frame_cap < 1:
            raise ValueError("caps must be positive")
        self.leaf_cap = leaf_cap
        self.frame_cap = frame_cap
        self.records: dict[str, list[tuple[str, str, frozenset[str]]]] = {}
        self.root: Node | None = None
        self.routing_root: conduct_tree.Node | None = None
        self.leaves: dict[str, Node] = {}
        self.sentences_examined = 0
        self.frames_examined = 0
        # A frame points to one sentence. Predicate and argument indexes hold IDs,
        # never copies of every sentence or an all-frame query pool.
        self.frame_rows: list[tuple[str, int, str, str, str, str, bool, str]] = []
        self.frames_by_predicate: dict[str, list[int]] = defaultdict(list)
        self.frames_by_argument: dict[str, dict[str, list[int]]] = {}

    @classmethod
    def from_records(cls, records: Iterable[Mapping[str, str]], leaf_cap: int = LEAF_CAP,
                     frame_cap: int = FRAME_CAP, max_resident_mb: int | None = None) -> "Library":
        return cls(leaf_cap, frame_cap).build(records, max_resident_mb=max_resident_mb)

    def build(self, records: Iterable[Mapping[str, str]],
              max_resident_mb: int | None = None) -> "Library":
        def check_memory() -> None:
            if max_resident_mb is not None:
                import psutil
                if psutil.Process().memory_info().rss > max_resident_mb * 1024 * 1024:
                    raise MemoryError("library build reached resident memory limit")

        scenes: dict[str, list[str]] = defaultdict(list)
        for count, row in enumerate(records):
            text = str(row.get("text", "")).strip()
            if text:
                scenes[str(row.get("scene", "") or "不明")].append(text)
            if count % 10000 == 0:
                check_memory()
        self.records.clear()
        self.leaves.clear()
        self.routing_root = None
        self.frame_rows.clear()
        self.frames_by_predicate.clear()
        self.frames_by_argument.clear()
        by_sovereign: dict[str, dict[str, Node]] = defaultdict(dict)
        for scene_index, (scene, texts) in enumerate(scenes.items()):
            if scene_index % 10 == 0:
                check_memory()
            head = scene.split("（", 1)[0].strip() or "不明"
            chunks = math.ceil(len(texts) / self.leaf_cap)
            for part in range(chunks):
                name = scene if chunks == 1 else f"{scene}・{_kanji(part + 1)}"
                # Scenes can theoretically repeat a generated name. Keep labels unique.
                if name in self.leaves:
                    raise ValueError(f"duplicate leaf name: {name}")
                rows = [(s, scene, frozenset(_ja_words(s)))
                        for s in texts[part * self.leaf_cap:(part + 1) * self.leaf_cap]]
                store = CrossStore()
                ingest_documents(store, [Document(source=name, text="\n".join(s for s, _, _ in rows))])
                leaf = Node(name=name, store=store)
                self.records[name] = rows
                self.leaves[name] = leaf
                by_sovereign[head][name] = leaf
                for row_index, (sentence, _, _) in enumerate(rows):
                    for item in read_records(sentence):
                        f = item.frame
                        if not f.predicate:
                            continue
                        frame_id = len(self.frame_rows)
                        self.frame_rows.append((name, row_index, f.predicate,
                                                f.agent, f.patient, f.recipient,
                                                f.negated, item.condition))
                        self.frames_by_predicate[f.predicate].append(frame_id)
                        nouns = self._argument_nouns(f.agent, f.patient, f.recipient)
                        postings = self.frames_by_argument.setdefault(f.predicate, {})
                        for noun in nouns:
                            postings.setdefault(noun, []).append(frame_id)
        sovereigns = {head: group_into_layers(head, leaves)
                      for head, leaves in by_sovereign.items()}
        self.root = group_into_layers("図書館", sovereigns) if sovereigns else None
        if self.root is not None:
            self.routing_root = conduct_tree.build(
                {name: leaf.store.crosses for name, leaf in self.leaves.items()},
                hierarchy=self.root)
            check_memory()
        return self

    @staticmethod
    def _argument_nouns(*arguments: str) -> set[str]:
        from verantyx.typed_edges import _tagger
        return {((w.feature.lemma or w.surface).split("-")[0])
                for arg in arguments if arg for w in _tagger()(arg)
                if w.feature.pos1 == "名詞" and w.surface}

    @property
    def depth(self) -> int:
        return self.root.depth() if self.root else 0

    def save(self, directory: str | Path) -> None:
        path = Path(directory)
        path.mkdir(parents=True, exist_ok=True)
        with (path / "library.pkl").open("wb") as f:
            pickle.dump((FORMAT_VERSION, self), f, protocol=pickle.HIGHEST_PROTOCOL)

    @classmethod
    def load(cls, directory: str | Path) -> "Library":
        with (Path(directory) / "library.pkl").open("rb") as f:
            version, lib = pickle.load(f)
        if version != FORMAT_VERSION or not isinstance(lib, cls):
            raise ValueError("unsupported library format")
        if not hasattr(lib, "routing_root"):
            lib.routing_root = (conduct_tree.build(
                {name: leaf.store.crosses for name, leaf in lib.leaves.items()},
                hierarchy=lib.root) if lib.root is not None else None)
        return lib

    def _score(self, leaf: Node, words: set[str], k: int) -> list[tuple[str, str, float]]:
        found = []
        for text, scene, own in self.records[leaf.name]:
            self.sentences_examined += 1
            shared = len(words & own)
            if shared:
                found.append((text, scene, shared / math.sqrt(len(words) * len(own))))
        found.sort(key=lambda row: (-row[2], row[0]))
        return found[:k]

    def _fallback_frames(self, q: str, words: set[str], k: int
                         ) -> tuple[list[tuple[str, str, float]], str | None, int, bool]:
        # A question can mention several events. Probe the rarer predicates
        # first so a generic event cannot consume the entire frame budget.
        queries = sorted(read_records(q),
                         key=lambda item: len(self.frames_by_predicate.get(item.frame.predicate, ())))
        found: dict[tuple[str, int], tuple[str, str, float]] = {}
        touched = 0
        capped = False
        for item in queries:
            f = item.frame
            ids = self.frames_by_predicate.get(f.predicate, ())
            if not ids:
                continue
            nouns = self._argument_nouns(f.agent, f.patient, f.recipient)
            by_noun = self.frames_by_argument.get(f.predicate, {})
            if len(ids) > self.frame_cap and nouns:
                # A common predicate can have millions of frames. The argument
                # postings narrow it before any frame payload is inspected.
                candidates = sorted({i for n in nouns
                                     for i in islice(by_noun.get(n, ()), self.frame_cap + 1)})
            else:
                candidates = ids
            for frame_id in candidates:
                if touched >= self.frame_cap:
                    capped = True
                    break
                touched += 1
                self.frames_examined += 1
                name, row_index, _, agent, patient, recipient, negated, condition = self.frame_rows[frame_id]
                sentence, scene, own = self.records[name][row_index]
                shared = len(words & own)
                if not shared:
                    continue
                score = shared / math.sqrt(len(words) * len(own))
                score += .05 * sum(bool(a and a == b) for a, b in
                                   zip((f.agent, f.patient, f.recipient),
                                       (agent, patient, recipient)))
                if f.negated == negated:
                    score += .01
                if condition and condition in q:
                    score += .01
                key = (name, row_index)
                if key not in found or score > found[key][2]:
                    found[key] = (sentence, scene, score)
            if capped:
                break
        ranked = sorted(found.items(), key=lambda entry: (-entry[1][2], entry[1][0]))[:k]
        return [row for _, row in ranked], (ranked[0][0][0] if ranked else None), touched, capped

    def ask(self, q: str, k: int = 5) -> dict:
        started = time.perf_counter()
        words = _ja_words(q)
        refused = {"sentences": [], "path": "refused", "verdict": "UNKNOWN_NO_ROUTE",
                   "how_to_resolve": "Add a document with the requested fact or a distinguishing route term.",
                   "leaf": None, "depth": 0,
                   "frames_touched": 0, "frame_cap_hit": False,
                   "route_trace": {"verdict": "UNKNOWN_NO_ROUTE", "trail": [],
                                   "note": "no built route or content terms"}}
        if not self.routing_root or not words or k <= 0:
            return {**refused, "ms": round((time.perf_counter() - started) * 1000, 3)}
        runs = ja_content_runs(q)
        terms = sorted(words | set(runs))
        anchor = next((run for run in runs if len(run) >= 2), None)
        route_trace = conduct_tree.descend(self.routing_root, terms, anchor=anchor)
        depth = len(route_trace["trail"])
        leaf = self.leaves.get(route_trace.get("leaf")) if route_trace["verdict"] == "ROUTED" else None
        answer = self._score(leaf, words, k) if leaf is not None else []
        path = "conduct"
        frames_touched = 0
        frame_cap_hit = False
        leaf_name = leaf.name if answer else None
        if not answer:
            answer, leaf_name, frames_touched, frame_cap_hit = self._fallback_frames(q, words, k)
            path = "fallback_frames"
        if not answer:
            return {**refused, "depth": depth,
                    "frames_touched": frames_touched, "frame_cap_hit": frame_cap_hit,
                    "route_trace": route_trace,
                    "ms": round((time.perf_counter() - started) * 1000, 3)}
        return {"sentences": answer, "path": path, "leaf": leaf_name, "depth": depth,
                "frames_touched": frames_touched, "frame_cap_hit": frame_cap_hit,
                "route_trace": route_trace,
                "ms": round((time.perf_counter() - started) * 1000, 3)}


# Round 3 keeps question-answer sovereigns distinct from the sentence Library.
# Import here so callers have a single public library module.
from .family_library import FamilyLibrary, FAMILIES as QUESTION_FAMILIES  # noqa: E402
