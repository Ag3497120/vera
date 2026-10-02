"""Vera base: records in predicate-argument structure, reached through the stereo cross with a capped fallback.

    content   every record sentence is read into frames (verdict.read_records: event, doer, object,
              recipient, negation, rule kind, condition, exception, filled-in omissions) and keeps its source
    route     1. the stereo cross: one leaf per document (CrossStore via document_ingest), grouped six
                 arms per node; a question is lowered root -> leaf, or refused (never a guessed leaf)
              2. fallback: when the tree refuses, predicate/argument postings supply at most 2,000 frames (optionally also
                 when the reached leaf cannot decide: measured +0.5 pt accuracy for 16x the time and one
                 harmful verdict, so off by default)
    use       judge(claim)   -> the verdict contract, with the path taken
              find(question) -> the record sentences of the reached leaf (or capped predicate postings)
Capabilities (skills, chat, generation) sit on top of this and do not reach the records any other way."""
from __future__ import annotations

import re
import time
from collections import defaultdict
from itertools import islice
from typing import Dict, List, Optional

from verantyx import conduct_tree
from verantyx.verdict import Item, judge as judge_items, read_records

UNDECIDED = {"UNCONFIRMED", "NOT_IN_DOCS"}
FRAME_CAP = 2000


class Base:
    def __init__(self):
        self.docs: Dict[str, dict] = {}
        self.items: Dict[str, List[Item]] = {}
        self.flat: List[Item] = []
        self.frame_cap = FRAME_CAP
        self.frames_by_predicate: dict[str, list[int]] = defaultdict(list)
        self.frames_by_canonical: dict[str, list[int]] = defaultdict(list)
        self.frames_by_argument: dict[str, dict[str, list[int]]] = {}
        self.frame_rows: list[tuple[str, Item]] = []
        self.root = None
        self.routing_root: conduct_tree.Node | None = None
        self.last_route: dict = {"verdict": "UNKNOWN_NO_ROUTE", "trail": []}

    # --- content -------------------------------------------------------------------
    def add(self, name: str, text: str, kind: str = "record", sovereign: str = "") -> None:
        """sovereign: the domain the document belongs to (defaults to its kind: rules / record).
        Documents of different sovereigns get separate trees joined under one root — measured:
        wrong routing 13% -> 7.5% over 160 documents, same speed, no harmful verdicts."""
        self.docs[name] = {"text": text, "kind": kind, "sovereign": sovereign or kind,
                           "sentences": [s.strip() for s in re.split(r"(?<=。)", text) if s.strip()]}
        self.items[name] = read_records(text, kind)
        self.root = None
        self.routing_root = None

    def build(self) -> "Base":
        from verantyx.cross_store import CrossStore
        from verantyx.document_ingest import Document, ingest_documents
        from verantyx.hierarchy import Node
        from verantyx.sovereign import group_into_layers
        leaves = {}
        for name, d in self.docs.items():
            st = CrossStore()
            ingest_documents(st, [Document(source=name, text=d["text"])])
            leaves[name] = Node(name=name, store=st)
        by: Dict[str, dict] = {}
        for name, leaf in leaves.items():
            by.setdefault(self.docs[name]["sovereign"], {})[name] = leaf
        if len(leaves) <= 1:
            self.root = None
        elif len(by) == 1:
            self.root = group_into_layers("記録", leaves)
        else:
            from verantyx.hierarchy import federate
            self.root = federate("主権", {sov: (group_into_layers(sov, ls) if len(ls) > 1 else next(iter(ls.values())))
                                         for sov, ls in by.items()})
        self.routing_root = (conduct_tree.build(
            {name: leaf.store.crosses for name, leaf in leaves.items()},
            hierarchy=self.root) if self.root is not None else None)
        self.flat = [it for v in self.items.values() for it in v]
        self.frame_rows = []
        self.frames_by_predicate.clear()
        self.frames_by_canonical.clear()
        self.frames_by_argument.clear()
        from verantyx.frames import canonical
        for name, items in self.items.items():
            for item in items:
                pred = item.frame.predicate
                if not pred:
                    continue
                frame_id = len(self.frame_rows)
                self.frame_rows.append((name, item))
                self.frames_by_predicate[pred].append(frame_id)
                self.frames_by_canonical[canonical(pred)].append(frame_id)
                postings = self.frames_by_argument.setdefault(pred, {})
                for noun in self._argument_nouns(item.frame.agent, item.frame.patient,
                                                 item.frame.recipient):
                    postings.setdefault(noun, []).append(frame_id)
        return self

    @staticmethod
    def _argument_nouns(*arguments: str) -> set[str]:
        from verantyx.typed_edges import _tagger
        return {((w.feature.lemma or w.surface).split("-")[0])
                for arg in arguments if arg for w in _tagger()(arg)
                if w.feature.pos1 == "名詞" and w.surface}

    def fallback_items(self, query: str) -> tuple[list[Item], dict]:
        """Predicate postings, argument narrowed, with a hard frame inspection cap."""
        from verantyx.frames import canonical
        queries = sorted(read_records(query),
                         key=lambda it: len(self.frames_by_predicate.get(it.frame.predicate, ())))
        selected: list[Item] = []
        seen: set[int] = set()
        touched = 0
        capped = False
        for query_item in queries:
            f = query_item.frame
            ids = self.frames_by_predicate.get(f.predicate, ())
            if not ids:
                ids = self.frames_by_canonical.get(canonical(f.predicate), ())
            nouns = self._argument_nouns(f.agent, f.patient, f.recipient)
            postings = self.frames_by_argument.get(f.predicate, {})
            if len(ids) > self.frame_cap and nouns:
                candidates = sorted({i for n in nouns
                                     for i in islice(postings.get(n, ()), self.frame_cap + 1)})
            else:
                candidates = ids
            for frame_id in candidates:
                if frame_id in seen:
                    continue
                if touched >= self.frame_cap:
                    capped = True
                    break
                seen.add(frame_id)
                touched += 1
                selected.append(self.frame_rows[frame_id][1])
            if capped:
                break
        return selected, {"frames_touched": touched, "frame_cap_hit": capped,
                          "predicates": [it.frame.predicate for it in queries]}

    # --- route -----------------------------------------------------------------------
    def lower(self, query: str) -> Optional[str]:
        if self.root is None:
            leaf = next(iter(self.docs)) if len(self.docs) == 1 else None
            self.last_route = ({"verdict": "ROUTED", "leaf": leaf, "trail": [leaf]}
                               if leaf else {"verdict": "UNKNOWN_NO_ROUTE", "trail": []})
            return leaf
        from verantyx.bot import _en_words, _ja_words, lang
        from verantyx.lang import ja_content_runs
        language = lang(query)
        words = _ja_words(query) if language == "ja" else _en_words(query)
        runs = ja_content_runs(query)
        terms = sorted(words | set(runs))
        anchor = (next((run for run in runs if len(run) >= 2), None)
                  if language == "ja" else None)
        self.last_route = conduct_tree.descend(self.routing_root, terms, anchor=anchor)
        return self.last_route.get("leaf") if self.last_route["verdict"] == "ROUTED" else None

    # --- use -------------------------------------------------------------------------
    def judge(self, claim: str, recheck_undecided: bool = False) -> dict:
        if self.root is None and not self.flat:
            self.build()
        t = time.perf_counter()
        # a claim written in the records word for word is supported by that sentence (sentences with no verb,
        # such as 「休館日は毎週月曜日です」, have no frame to match)
        norm = lambda x: re.sub(r"[。、\s]", "", x)
        for name, d in self.docs.items():
            for sent in d["sentences"]:
                if norm(claim) and norm(claim) == norm(sent):
                    return {"verdict": "SUPPORTED", "evidence": [sent], "leaf": name, "path": "exact",
                            "ms": round(1000 * (time.perf_counter() - t), 3)}
        leaf = self.lower(claim)
        path = "tree"
        v = judge_items(self.items[leaf], claim) if leaf else None
        if v is None or (recheck_undecided and v["verdict"] in UNDECIDED):
            # fallback: the tree refused, or its leaf could not decide — the whole pool, flat
            candidates, fallback_trace = self.fallback_items(claim)
            fv = judge_items(candidates, claim)
            if v is None or fv["verdict"] not in UNDECIDED:
                v, path = fv, ("fallback" if leaf is None else "fallback_after_leaf")
        else:
            fallback_trace = {"frames_touched": 0, "frame_cap_hit": False, "predicates": []}
        v.update({"leaf": leaf, "path": path, "route_trace": self.last_route,
                  "fallback_trace": fallback_trace,
                  "ms": round(1000 * (time.perf_counter() - t), 3)})
        return v

    def find(self, question: str) -> dict:
        if self.root is None and not self.flat:
            self.build()
        leaf = self.lower(question)
        if leaf:
            return {"leaf": leaf, "path": "tree", "route_trace": self.last_route,
                    "sentences": self.docs[leaf]["sentences"]}
        candidates, fallback_trace = self.fallback_items(question)
        return {"leaf": None, "path": "fallback_frames", "route_trace": self.last_route,
                "fallback_trace": fallback_trace,
                "sentences": list(dict.fromkeys(it.sentence for it in candidates))}
