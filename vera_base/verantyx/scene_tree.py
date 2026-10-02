"""The stereo cross over the general knowledge: one leaf per scene of the Codex corpus.

A question is lowered from the root to one scene (hierarchy.route, probe as fallback); the
answer then uses only sentences written in that scene. Leaves: build/scene_tree/*.json."""
from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Dict, Optional, Set

BUILD = Path.home() / "Projects/vera-corpus/build"
CORPUS = Path.home() / "Projects/vera-corpus/codex"


@lru_cache(maxsize=1)
def tree():
    from verantyx.cross_store import CrossStore
    from verantyx.hierarchy import Node
    from verantyx.sovereign import group_into_layers
    idx = json.loads((BUILD / "scene_tree" / "index.json").read_text())
    leaves = {n: Node(name=n, store=CrossStore.load(BUILD / "scene_tree" / (n + ".json"))) for n in idx}
    return group_into_layers("知識", leaves), idx


@lru_cache(maxsize=1)
def sources_by_scene() -> Dict[str, Set[str]]:
    out: Dict[str, Set[str]] = {}
    for f in ("pro/sentences.jsonl", "local/sentences.jsonl"):
        p = CORPUS / f
        if not p.exists():
            continue
        for line in open(p):
            try:
                r = json.loads(line)
            except ValueError:
                continue
            base = re.sub(r"（.*?）", "", r.get("scene") or "").strip()
            out.setdefault(base, set()).add(r["source"])
    return out


def lower(query: str) -> Optional[Dict[str, str]]:
    """Root to leaf; None when no branch is reachable (never a guessed scene)."""
    from verantyx.hierarchy import probe, route
    from verantyx.lang import ja_content_runs
    root, idx = tree()
    # a scene named in the question is the leaf (longest name first); the router can only
    # tell arms apart on ~24 terms each, and words like 台所 run through many scenes
    named = sorted(((v["scene"], k) for k, v in idx.items() if v["scene"] and v["scene"] in query),
                   key=lambda x: -len(x[0]))
    if named:
        return {"leaf": named[0][1], "scene": named[0][0], "path": ["scene-name"]}
    node, path = root, []
    for _ in range(16):
        if node.is_leaf:
            return {"leaf": node.name, "scene": idx[node.name]["scene"], "path": path}
        step = route(node, query)
        if step["verdict"] != "ANSWER":
            step = probe(node, ja_content_runs(query) or [query])
        if step["verdict"] != "ANSWER":
            return None
        node = node.children[step["child"]]
        path.append(node.name)
    return None
