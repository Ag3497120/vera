"""Vera base: records in predicate-argument structure, reached through the stereo cross with a flat fallback.

    content   every record sentence is read into frames (verdict.read_records: event, doer, object,
              recipient, negation, rule kind, condition, exception, filled-in omissions) and keeps its source
    route     1. the stereo cross: one leaf per document (CrossStore via document_ingest), grouped six
                 arms per node; a question is lowered root -> leaf, or refused (never a guessed leaf)
              2. fallback: when the tree refuses, the flat pool of all frames is used (optionally also
                 when the reached leaf cannot decide: measured +0.5 pt accuracy for 16x the time and one
                 harmful verdict, so off by default)
    use       judge(claim)   -> the verdict contract, with the path taken
              find(question) -> the record sentences of the reached leaf (or the flat pool)
Capabilities (skills, chat, generation) sit on top of this and do not reach the records any other way."""
from __future__ import annotations

import re
import time
from typing import Dict, List, Optional

from verantyx.verdict import Item, judge as judge_items, read_records

UNDECIDED = {"UNCONFIRMED", "NOT_IN_DOCS"}


class Base:
    def __init__(self):
        self.docs: Dict[str, dict] = {}
        self.items: Dict[str, List[Item]] = {}
        self.flat: List[Item] = []
        self.root = None

    # --- content -------------------------------------------------------------------
    def add(self, name: str, text: str, kind: str = "record", sovereign: str = "") -> None:
        """sovereign: the domain the document belongs to (defaults to its kind: rules / record).
        Documents of different sovereigns get separate trees joined under one root — measured:
        wrong routing 13% -> 7.5% over 160 documents, same speed, no harmful verdicts."""
        self.docs[name] = {"text": text, "kind": kind, "sovereign": sovereign or kind,
                           "sentences": [s.strip() for s in re.split(r"(?<=。)", text) if s.strip()]}
        self.items[name] = read_records(text, kind)
        self.root = None

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
        self.flat = [it for v in self.items.values() for it in v]
        return self

    # --- route -----------------------------------------------------------------------
    def lower(self, query: str) -> Optional[str]:
        if self.root is None:
            return next(iter(self.docs)) if len(self.docs) == 1 else None
        from verantyx.hierarchy import probe, route
        from verantyx.lang import ja_content_runs
        node = self.root
        for _ in range(16):
            if node.is_leaf:
                return node.name
            step = route(node, query)
            if step["verdict"] != "ANSWER":
                step = probe(node, ja_content_runs(query) or [query])
            if step["verdict"] != "ANSWER":
                return None
            node = node.children[step["child"]]
        return None

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
            fv = judge_items(self.flat, claim)
            if v is None or fv["verdict"] not in UNDECIDED:
                v, path = fv, ("fallback" if leaf is None else "fallback_after_leaf")
        v.update({"leaf": leaf, "path": path, "ms": round(1000 * (time.perf_counter() - t), 3)})
        return v

    def find(self, question: str) -> dict:
        if self.root is None and not self.flat:
            self.build()
        leaf = self.lower(question)
        if leaf:
            return {"leaf": leaf, "path": "tree", "sentences": self.docs[leaf]["sentences"]}
        return {"leaf": None, "path": "fallback", "sentences": [s for d in self.docs.values() for s in d["sentences"]]}
