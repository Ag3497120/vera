"""The centre edge: a seat for the link between two cores, and speech that
walks it.

The cross has two kinds of edge. An arm edge joins two faces of ONE core —
two facets one sentence wrote together — and that is what `in_words` has
used since the edge sidecar went in: it re-licensed speech on 97/97 silenced
cores. A centre edge joins faces on DIFFERENT arms, core to core: the
octahedron's twelve. The design table left it as the one unfilled seat —
"核間リンク(引用層 74.5%)の幾何座席が未実装 — 腕内の辺だけ入れた" — and named
what it would open: speech that crosses leaves, a paragraph that goes from
one core to the next instead of re-saying one subject.

## What makes a centre edge

A -> B is seated only when the corpus wrote the link BOTH ways:

    arm side     B is an endpoint of one of A's arm edges — some sentence
                 filed under A wrote B next to another facet of A
    centre side  A is a facet of B — the corpus, writing about B, wrote A
    speakable    B is itself a core with enough facets to say anything
                 (the same floor attest_llm uses) and a vocabulary word

One direction alone is a mention; both directions is the corpus treating
the two as each other's context, which is the relation a sentence joining
them asserts. Nothing here is inferred: every seat is two lookups into
what ingest already recorded, so "placement cannot add information" holds.

## How the walk speaks, and where it stops

From the start core the walk takes the strongest seated edge (weight =
the weaker of the two directions' counts — a link is as strong as its
thinner side), says ONE sentence about A whose content is only B and the
facets A's sentences wrote next to B, then stands on B and repeats.

It stops, typed, instead of guessing:

    HUB_TIED      the top two edges weigh the same — the choice would be
                  an accident of ordering, so no hop (ties abstain, as
                  everywhere else in this package)
    HUB_NONE      no seated edge leaves this core
    HUB_REVISIT   the only way on leads back to a core already spoken
    HUB_SILENT    a hop was seated but the writer produced no sentence

Every sentence carries its hop: which two cores, the weights both ways and
the arm pairs that licensed its content, so a reader can check each joint.
"""
from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

#: Same floor as attest_llm.MIN_FACETS: below it, one facet decides.
MIN_FACETS = 3

#: A core that is a facet of nearly every other core carries no subject —
#: fusion.py measured the same thing across fields (作成, 必要, 規定 span all
#: twelve). Cut by QUANTILE of in-degree over the store, not by a word list:
#: on the repaired federation the 0.999 quantile is 766, which removes
#: 規定(10,898) 法律(3,591) 必要(2,072) 日本(1,922) 行為(1,167) 問題(876)
#: and keeps 犯罪(342) 故意(128) 侵害(209) 債務者(143).
GENERIC_QUANTILE = 0.999


def generic_cut(store: Any, q: float = GENERIC_QUANTILE) -> Tuple[int, Dict[str, int]]:
    """In-degree of every word as someone's facet, and the cut above which a
    core is treated as grammar rather than a subject."""
    indeg: Dict[str, int] = {}
    for cr in store.crosses.values():
        for f in cr:
            indeg[f] = indeg.get(f, 0) + 1
    vals = sorted(indeg.get(c, 0) for c in store.crosses)
    if not vals:
        return 0, indeg
    return vals[max(0, int(q * len(vals)) - 1)], indeg

EdgesOf = Callable[[str], Sequence[Tuple[str, str]]]


def _cross(store: Any, core: str) -> Dict[str, Any]:
    labels = getattr(store, "source_labels", set()) or set()
    return {f: n for f, n in (store.crosses.get(core) or {}).items()
            if f not in labels}


def _count(v: Any) -> int:
    return v if isinstance(v, int) else 1


def seats(store: Any, core: str, edges_of: EdgesOf,
          vocab: Optional[Any] = None,
          generic: Optional[Tuple[int, Dict[str, int]]] = None
          ) -> List[Dict[str, Any]]:
    """Every centre edge leaving `core`, strongest first, with its witness."""
    a_cross = _cross(store, core)
    partners: Dict[str, List[Tuple[str, str]]] = {}
    for f1, f2 in edges_of(core) or ():
        for b, other in ((f1, f2), (f2, f1)):
            if b != core:
                partners.setdefault(b, []).append((b, other))
    out: List[Dict[str, Any]] = []
    for b, arm in partners.items():
        b_cross = _cross(store, b)
        if len(b_cross) < MIN_FACETS or core not in b_cross:
            continue
        if vocab is not None and b not in vocab:
            continue
        if generic is not None and generic[1].get(b, 0) > generic[0]:
            continue
        ab, ba = _count(a_cross.get(b, 1)), _count(b_cross[core])
        out.append({"from": core, "to": b, "weight": min(ab, ba),
                    "a_to_b": ab, "b_to_a": ba,
                    "arm_pairs": sorted(set(arm))})
    out.sort(key=lambda s: (-s["weight"], s["to"]))
    return out


def _content(seat: Dict[str, Any], vocab: Optional[Any], k: int) -> List[str]:
    """B, then the facets A's own sentences wrote beside B — nothing else."""
    words = [seat["to"]]
    for _b, other in seat["arm_pairs"]:
        if other not in words and (vocab is None or other in vocab):
            words.append(other)
        if len(words) >= k:
            break
    return words


def speak(a: str, content: Sequence[str]) -> str:
    """One sentence that asserts exactly what the seat proves and no more.

    The harvested writer forms were tried first and failed the joint: they
    carry a verb, and the verb asserts a direction the edge never recorded —
    「正当防衛が侵害している」 inverts the law, 「過失に故意に死亡される」 says
    nothing. A centre edge proves only that the corpus writes A and B as each
    other's context, and which of A's facets stood beside B. So that is the
    sentence: fixed form, no verb chosen, nothing to invert.
    """
    b, rest = content[0], list(content[1:])
    tail = "（" + "・".join(rest) + "とともに）" if rest else ""
    return f"{a}は{b}と結びつけて書かれる{tail}。"


def walk(store: Any, start: str, edges_of: EdgesOf, writer: Any = None,
         *, hops: int = 3, content: int = 4,
         generic: Optional[Tuple[int, Dict[str, int]]] = None,
         carry: bool = True) -> Dict[str, Any]:
    """Speak from `start` across up to `hops` centre edges.

    The writer is used only for its vocabulary (so a hop never lands on a
    clipped fragment); the sentence form is `speak`, fixed.
    """
    vocab = getattr(writer, "vocab", None)
    if len(_cross(store, start)) < MIN_FACETS:
        return {"verdict": "UNKNOWN_SUBJECT_TOO_THIN", "start": start,
                "path": [start], "stopped": "UNKNOWN_SUBJECT_TOO_THIN",
                "hops": [], "text": ""}
    visited = [start]
    start_cross = _cross(store, start)
    chain: List[Dict[str, Any]] = []
    stop = "HUB_DEPTH"
    here = start
    for _ in range(hops):
        cand = seats(store, here, edges_of, vocab, generic)
        if carry and here != start:
            # Carry the query (matryoshka mode A): past the first hop, a core
            # is only reachable if the START and it are each other's context
            # too. Every joint of 窃盗罪→意思→判例→事件→ロッキード was a real
            # edge and the paragraph still left theft behind by hop three.
            cand = [c for c in cand if c["to"] in start_cross
                    and start in _cross(store, c["to"])]
        fresh = [s for s in cand if s["to"] not in visited]
        if not cand:
            stop = "HUB_NONE"
            break
        if not fresh:
            stop = "HUB_REVISIT"
            break
        if len(fresh) > 1 and fresh[0]["weight"] == fresh[1]["weight"]:
            stop = "HUB_TIED"
            tied = [s["to"] for s in fresh
                    if s["weight"] == fresh[0]["weight"]][:6]
            # A tie forbids choosing, not speaking: the set is attested,
            # only its order is an accident. Said as a set, then stop.
            chain.append({"at": here, "stopped": stop, "tied": tied,
                          "sentence": f"{here}は{'・'.join(tied)}と"
                                      f"結びつけて書かれる（同じ重み）。"})
            break
        seat = fresh[0]
        hop: Dict[str, Any] = {"seat": seat,
                               "content": _content(seat, vocab, content)}
        hop["sentence"] = speak(here, hop["content"])
        chain.append(hop)
        visited.append(seat["to"])
        here = seat["to"]
    spoken = [h["sentence"] for h in chain if h.get("sentence")]
    return {"verdict": "HUB_WALK" if any("seat" in h and "stopped" not in h
                                         for h in chain) else stop,
            "start": start, "path": visited, "stopped": stop,
            "hops": chain, "text": "".join(spoken),
            "note": "each joint is a centre edge the corpus wrote both ways; "
                    "each sentence's content is only what A's sentences "
                    "wrote beside B. Grounded, not verified true."}


def regression() -> Dict[str, Any]:
    """Toy store: the seat rule, the tie stop, and the one-way refusal."""
    from .cross_store import CrossStore

    s = CrossStore()
    s.crosses = {
        "時効": {"期間": 3, "援用": 2, "消滅": 1, "権利": 1},
        "期間": {"時効": 3, "起算": 1, "満了": 1, "日": 1},
        "援用": {"時効": 1, "当事者": 1, "意思": 1},       # weaker link
        "消滅": {"債権": 1, "権利": 1, "効果": 1},          # no 時効: one-way
        "起算": {"期間": 1, "初日": 1, "翌日": 1},
        "満了": {"期間": 1, "起算": 1, "日": 1},
    }
    e = {"時効": [("期間", "権利"), ("援用", "当事者"), ("消滅", "権利")],
         "期間": [("起算", "日"), ("満了", "日")]}
    edges_of = lambda c: e.get(c, [])  # noqa: E731
    checks: Dict[str, bool] = {}
    st = seats(s, "時効", edges_of)
    checks["one_way_not_seated"] = all(x["to"] != "消滅" for x in st)
    checks["strongest_first"] = [x["to"] for x in st][:1] == ["期間"]
    w = walk(s, "時効", edges_of, hops=3, carry=False)
    checks["tie_stops"] = w["stopped"] == "HUB_TIED" and w["path"] == ["時効", "期間"]
    checks["tie_spoken_as_set"] = "起算" in w["text"] and "満了" in w["text"] and "同じ重み" in w["text"]
    wc = walk(s, "時効", edges_of, hops=3, carry=True)
    checks["carry_stops_drift"] = wc["stopped"] == "HUB_NONE" and wc["path"] == ["時効", "期間"]
    checks["content_is_arm_only"] = w["hops"][0]["content"] == ["期間", "権利"]
    checks["thin_refused"] = walk(s, "無", edges_of)["verdict"] == "UNKNOWN_SUBJECT_TOO_THIN"
    return {"all_pass": all(checks.values()), **checks}


def open_on(root: Any = None) -> Tuple[Any, EdgesOf, Any]:
    """Store, edge lookup and writer from a built corpus (vera.db + sidecar)."""
    import sqlite3
    from pathlib import Path

    from .export_sqlite import vera
    from .paths import corpus_root

    build = Path(root or corpus_root()) / "build"
    v = vera(build / "vera.db")
    epath = build / "vera_edges.db"

    def edges_of(core: str) -> List[Tuple[str, str]]:
        con = sqlite3.connect(f"file:{epath}?mode=ro", uri=True)
        try:
            return con.execute("SELECT f1, f2 FROM edges WHERE core=?",
                               (core,)).fetchall()
        finally:
            con.close()

    return v.stores["ja"], edges_of, getattr(v, "writer", None)
