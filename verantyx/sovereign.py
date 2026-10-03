"""Documents in, one sovereign node out — the whole procedure, run for real.

Everything the tree needs was measured separately. This assembles it into an
ordered build, because the order matters and each stage constrains the next:

    1  ingest      documents -> one store per domain, kept SEPARATE
    2  simulate    per-domain placement, gated on held-out questions
    3  plan        capacity -> how many layers this vocabulary requires
    4  assemble    routers, with intermediate layers inserted where needed
    5  federate    domain nodes under one sovereign
    6  verify      descend real questions and record what refused

Nothing here is new machinery. `egov` and `document_ingest` do stage 1,
`placement` does stage 2, `hierarchy` does 3–5. What this module adds is the
sequence and the refusal to skip a stage — a tree assembled without stage 2
routes on whichever four facts sorted first, and the measurement that
motivated the whole design says that is the difference between a 30.9% and a
13.2% fabrication rate.

## Why stage 3 cannot be a preference

A node has six arms and four fact faces, so it routes on 24 terms and, past
that, on nothing: measured, terms on the faces reached the right domain 20
of 24 times and terms off them 0 of 60. Depth follows arithmetically,

    depth ~= log6(V / 4)

and `plan` reports it rather than accepting a number from the caller. A
caller who wants a shallower tree is asking for a router that cannot route.

## Why the leaves stay apart

Flat, the six statutes here share 184 terms across three or more of them and
行為 across all six; 民法's 法律行為 is not 刑法's. Merging domains into one
store is the failure this shape exists to avoid, so no stage ever writes two
domains into the same CrossStore — `_merged` in `hierarchy` builds a view for
ranking router terms and is never what a question is answered from.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

from .cross_store import CrossStore
from .hierarchy import (
    CAPACITY,
    gather,
    N_FACES,
    Node,
    build_router,
    descend,
    federate,
    over_capacity,
    shape,
)
from .consensus_store import MAX_ARMS

#: File suffixes routed to the statute reader rather than the document reader.
_STATUTE_SUFFIX = {".xml"}


@dataclass
class Stage:
    """One step's outcome, kept whole so the build can be read afterwards."""

    name: str
    verdict: str
    detail: Dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# 1 — ingest
# ---------------------------------------------------------------------------

def _store_from_sentences(sentences: List[str], source: str) -> CrossStore:
    from .document_ingest import Document, ingest_documents

    st = CrossStore()
    if sentences:
        ingest_documents(st, [Document(source=source, text="".join(sentences))])
    return st


def ingest_domain(name: str, source: Path) -> Tuple[Dict[str, CrossStore], Dict[str, Any]]:
    """One folder becomes a domain's LEAF STORES — plural, and that is stage 3
    doing its work at ingest rather than being discovered later.

    A statute is already a tree the legislature drew: 刑法 is two 編 over 55
    章 over 357 条. So a law's leaves are its 章, not the law itself. The
    first version made one store per domain, the whole of 法律 hung under a
    single 24-term router, and every question refused at the root — the
    capacity report said "3 more layers" and it was right.

    Partitioning any other way (article-number buckets, term clustering)
    would invent divisions where authoritative ones exist, and a routing
    path through an invented group tells a reader nothing about why the
    question went that way. Non-statute documents split per document, which
    is the same principle: the source is the division.
    """
    from .document_ingest import Document, ingest_documents
    from .document_loaders import load_directory, load_paths
    from .egov import divisions, law_title

    src = Path(source)
    paths = sorted(p for p in (src.rglob("*") if src.is_dir() else [src])
                   if p.is_file() and not p.name.startswith("."))
    statutes = [p for p in paths if p.suffix.lower() in _STATUTE_SUFFIX]
    others = [p for p in paths if p.suffix.lower() not in _STATUTE_SUFFIX]

    leaves: Dict[str, CrossStore] = {}
    groups: Dict[str, List[str]] = {}
    n_articles = 0

    for p in statutes:
        law = law_title(p)
        for div in divisions(p, law=law):
            label = f"{law}／{div['division']}"
            sents = [f"{core}は{t}である。"
                     for core, _cap, terms in div["articles"] for t in terms]
            if not sents:
                continue
            st = _store_from_sentences(sents, law)
            if st.n_cores() == 0:
                continue
            leaves[label] = st
            groups.setdefault(law, []).append(label)
            n_articles += len(div["articles"])

    n_docs = 0
    if others:
        loaded = (load_directory(str(src)) if src.is_dir()
                  else load_paths([str(p) for p in others]))
        for doc in loaded["documents"]:
            if Path(getattr(doc, "source", "")).suffix.lower() in _STATUTE_SUFFIX:
                continue
            st = CrossStore()
            ingest_documents(st, [doc])
            if st.n_cores() == 0:
                continue
            label = f"{name}／{doc.source}"
            leaves[label] = st
            groups.setdefault(name, []).append(label)
            n_docs += 1

    return leaves, {
        "domain": name,
        "source": str(src),
        "statutes": len(statutes),
        "articles": n_articles,
        "documents": n_docs,
        "leaves": len(leaves),
        "groups": {k: len(v) for k, v in groups.items()},
        "cores": sum(st.n_cores() for st in leaves.values()),
        "_groups": groups,
    }


# ---------------------------------------------------------------------------
# 2 — simulate placement
# ---------------------------------------------------------------------------

def simulate_domain(name: str, store: CrossStore, *, n_queries: int = 200,
                    write: bool = True) -> Dict[str, Any]:
    """Pre-compute what goes on the faces, and refuse to bake it if it loses.

    The gate is the one from `placement`: the answer rate must not fall,
    uncovered query terms must not rise, and something must actually improve.
    A domain whose questions are flat has nothing to learn and is left on the
    frequency rule — that is a correct outcome, not a failure, and the
    report says which happened.
    """
    from .placement import accept, compare, derive_split, simulate

    train, test = derive_split(store, n_queries, demand="zipf")
    if not train or not test:
        return {"domain": name, "verdict": "SKIPPED",
                "reason": "not enough contested cores to form a query split"}
    cmp_ = compare(store, test, train=train, weight=0.0)
    gate = accept(cmp_)
    out = {
        "domain": name,
        "verdict": gate["verdict"],
        "reasons": gate["reasons"],
        "delta": cmp_["delta"],
        "mean_arms": cmp_["mean_arms"],
        "n_train": len(train),
        "n_test": cmp_["n_queries"],
    }
    if gate["verdict"] == "ACCEPTED" and write:
        placement = simulate(store, queries=train, weight=0.0)
        store.placement = placement
        store.placement_meta = {"policy": "simulated", "weight": 0.0,
                                "n_cores": len(placement),
                                "delta": cmp_["delta"]}
        out["placed_cores"] = len(placement)
    return out


# ---------------------------------------------------------------------------
# 3 — plan
# ---------------------------------------------------------------------------

def _flatten(leaves: Dict[str, CrossStore]) -> CrossStore:
    """A read-only view of a domain's leaves, for counting only.

    Never answered from, never routed on. Two domains are never flattened
    together — that is the merge the whole shape exists to avoid.
    """
    out = CrossStore()
    for st in leaves.values():
        for core, cross in st.crosses.items():
            out.crosses.setdefault(core, {}).update(cross)
            out.core_count[core] = out.core_count.get(core, 0) + 1
    return out


def plan(domains: Dict[str, CrossStore]) -> Dict[str, Any]:
    """How deep this vocabulary forces the tree to be.

    Reported, never accepted from the caller. Asking for fewer layers than
    the vocabulary needs is asking for a router that cannot route, and the
    measured failure is not graceful — it is zero.
    """
    per: Dict[str, Any] = {}
    total_terms = 0
    for name, st in domains.items():
        terms = len({t for c in st.crosses.values() for t in c})
        total_terms += terms
        per[name] = {
            "cores": st.n_cores(),
            "distinct_terms": terms,
            "layers_required": _layers_for(terms),
        }
    return {
        "capacity_per_node": CAPACITY,
        "arms": MAX_ARMS,
        "faces": N_FACES,
        "domains": per,
        "total_terms": total_terms,
        "domain_layer_required": _layers_for(len(domains) * N_FACES),
        "sovereign_layers_required": _layers_for(total_terms),
    }


def _layers_for(v: int) -> int:
    if v <= N_FACES:
        return 1
    return max(1, math.ceil(math.log(v / N_FACES, MAX_ARMS)))


# ---------------------------------------------------------------------------
# 4 — assemble, inserting layers where the arms run out
# ---------------------------------------------------------------------------

_KANJI = "〇一二三四五六七八九"


def _kanji(n: int) -> str:
    """Small integers as kanji, so a synthetic node name survives the
    Japanese run splitter that every core name goes through."""
    if n < 10:
        return _KANJI[n]
    return "".join(_KANJI[int(c)] for c in str(n))


def group_into_layers(name: str, children: Dict[str, Node],
                      *, asked: Optional[Sequence[str]] = None) -> Node:
    """Bind children under one node, adding intermediate layers if needed.

    Six arms is a hard count. Seven children do not "mostly fit" — the
    seventh is not placed at all, so groups of at most MAX_ARMS are formed
    and the grouping repeats until one node can hold them. Group names carry
    their members, because a routing path through a node called "group 2"
    tells a reader nothing about why the question went that way.
    """
    nodes = dict(children)
    level = 0
    while len(nodes) > MAX_ARMS:
        level += 1
        grouped: Dict[str, Node] = {}
        keys = list(nodes)
        # Fill the arms, do not minimise the groups. Chunking by MAX_ARMS
        # put twelve fields into TWO groups of six, so the root used two of
        # its six arms and could route 2 x 4 = 8 terms — which is exactly
        # how many of 24 questions escaped it. Sizing the chunk instead by
        # ceil(n / MAX_ARMS) gives six groups of two and the full 24.
        # A node that leaves arms empty has thrown away capacity it cannot
        # get back at any depth.
        size = -(-len(keys) // MAX_ARMS)
        for i in range(0, len(keys), size):
            chunk = keys[i:i + size]
            # Kanji numerals, not "群1-1". The Japanese run splitter cuts a
            # name at the ASCII digit boundary, so 主権群1-1 became the core
            # 主権群1 and no longer matched the child key — the router held
            # exactly the right terms and still routed nothing, because the
            # thing it named was not a branch. Node names travel through the
            # same tokeniser as the documents; they have to survive it.
            label = f"{name}群{_kanji(level)}{_kanji(i // size + 1)}"
            sub = Node(name=label, children={k: nodes[k] for k in chunk})
            sub.router = build_router(sub.children, asked=asked)
            grouped[label] = sub
        nodes = grouped
    root = Node(name=name, children=nodes)
    root.router = build_router(root.children, asked=asked)
    return root


def assemble(
    domains: Dict[str, Dict[str, CrossStore]],
    grouping: Dict[str, Dict[str, List[str]]],
    *,
    sovereign: str = "主権",
    asked: Optional[Sequence[str]] = None,
) -> Node:
    """Leaves -> their own document's divisions -> domain -> sovereign.

    Four named levels before any synthetic grouping, all of them drawn from
    the sources: a chapter of a law, a law, a field, the federation. Only
    when one of those has more than six members does `group_into_layers`
    add a level of its own, and it says so in the name.
    """
    domain_nodes: Dict[str, Node] = {}
    for dname, leaves in domains.items():
        groups = grouping.get(dname) or {dname: list(leaves)}
        mid: Dict[str, Node] = {}
        for gname, members in groups.items():
            kids = {m: Node(name=m, store=leaves[m]) for m in members if m in leaves}
            if not kids:
                continue
            mid[gname] = (next(iter(kids.values())) if len(kids) == 1
                          else group_into_layers(gname, kids, asked=asked))
        if not mid:
            continue
        domain_nodes[dname] = (next(iter(mid.values())) if len(mid) == 1
                               else group_into_layers(dname, mid, asked=asked))
    return group_into_layers(sovereign, domain_nodes, asked=asked)


# ---------------------------------------------------------------------------
# 6 — verify
# ---------------------------------------------------------------------------

def verify(root: Node, questions: Sequence[str]) -> Dict[str, Any]:
    """Ask real questions and record what happened, refusals included.

    A refusal is reported beside its candidates rather than as a failure.
    The tree is built so that a question it cannot place goes nowhere, and
    a verification that treated that as an error would pressure the next
    change toward guessing.
    """
    rows: List[Dict[str, Any]] = []
    reached = refused = 0
    for q in questions:
        out = descend(root, q)
        bare = descend(root, q, use_probe=False)
        many = gather(root, q)
        v = out.get("verdict")
        if v == "ANSWER":
            reached += 1
        else:
            refused += 1
        rows.append({
            "question": q,
            "verdict": v,
            "path": out.get("path"),
            "via": out.get("via"),
            "core": out.get("core"),
            "text": out.get("text"),
            "stopped_at": out.get("stopped_at"),
            "candidates": out.get("candidates", [])[:4],
            "router_only": bare.get("verdict"),
            "destinations": many["destinations"],
            "listed": [{"leaf": r["leaf"], "text": r["text"][:60]}
                       for r in many["results"] if r["verdict"] == "ANSWER"][:4],
        })
    router_only = sum(1 for r in rows if r["router_only"] == "ANSWER")
    listed = sum(1 for r in rows if r["listed"])
    return {"asked": len(rows), "answered_single_branch": reached,
            "refused_single_branch": refused,
            "answered_by_router_alone": router_only,
            "answered_as_list": listed, "rows": rows}


# ---------------------------------------------------------------------------
# the procedure
# ---------------------------------------------------------------------------

def build_sovereign(
    sources: Dict[str, Path],
    *,
    questions: Optional[Sequence[str]] = None,
    n_queries: int = 200,
    sovereign: str = "主権",
) -> Dict[str, Any]:
    """Run every stage in order and return the whole record."""
    stages: List[Stage] = []

    domains: Dict[str, Dict[str, CrossStore]] = {}
    grouping: Dict[str, Dict[str, List[str]]] = {}
    ing: List[Dict[str, Any]] = []
    for name, src in sources.items():
        leaves, rec = ingest_domain(name, Path(src))
        grouping[name] = rec.pop("_groups", {})
        if not leaves:
            stages.append(Stage("ingest", "UNKNOWN_EMPTY_DOMAIN", rec))
            continue
        domains[name] = leaves
        ing.append(rec)
    stages.append(Stage("ingest", "ANSWER" if domains else "UNKNOWN_NO_DOMAINS",
                        {"domains": ing}))
    if not domains:
        return ({"verdict": "UNKNOWN_NO_DOMAINS",
                 "stages": [s.__dict__ for s in stages]}, None)

    # Placement is simulated PER LEAF, because that is where the faces are.
    sim: List[Dict[str, Any]] = []
    for dname, leaves in domains.items():
        acc = rej = skip = 0
        deltas: List[float] = []
        for lname, st in leaves.items():
            r = simulate_domain(lname, st, n_queries=n_queries)
            if r["verdict"] == "ACCEPTED":
                acc += 1
                deltas.append(r["delta"]["uncovered_terms"])
            elif r["verdict"] == "REJECTED":
                rej += 1
            else:
                skip += 1
        sim.append({
            "domain": dname, "leaves": len(leaves),
            "accepted": acc, "rejected": rej, "skipped": skip,
            "mean_uncovered_delta": (round(sum(deltas) / len(deltas), 4)
                                     if deltas else None),
        })
    stages.append(Stage("simulate", "ANSWER", {"domains": sim}))

    flat = {d: _flatten(leaves) for d, leaves in domains.items()}
    p = plan(flat)
    stages.append(Stage("plan", "ANSWER", p))

    root = assemble(domains, grouping, sovereign=sovereign,
                    asked=questions or None)
    cap = over_capacity(root)
    stages.append(Stage("assemble", "ANSWER" if not cap["over"] else "OVER_CAPACITY",
                        {"shape": shape(root), "capacity": cap}))

    ver = verify(root, questions or [])
    stages.append(Stage("verify", "ANSWER", ver))

    return ({
        "verdict": "ANSWER",
        "sovereign": sovereign,
        "shape": shape(root),
        "stages": [s.__dict__ for s in stages],
    }, root)


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(
        description="Build one sovereign node from documents, stage by stage.")
    ap.add_argument("--domain", action="append", metavar="NAME=PATH",
                    required=True,
                    help="a domain and the folder its documents live in")
    ap.add_argument("--ask", action="append", default=[],
                    help="a question to descend after the build")
    ap.add_argument("--questions", help="a file of questions, one per line")
    ap.add_argument("--n-queries", type=int, default=200)
    ap.add_argument("--name", default="主権")
    ap.add_argument("--out", help="write the build record as JSON")
    a = ap.parse_args(argv)

    sources: Dict[str, Path] = {}
    for spec in a.domain:
        if "=" not in spec:
            print(json.dumps({"verdict": "UNKNOWN_BAD_DOMAIN_SPEC",
                              "got": spec, "want": "NAME=PATH"},
                             ensure_ascii=False))
            return 1
        name, path = spec.split("=", 1)
        sources[name.strip()] = Path(path.strip())

    qs = list(a.ask)
    if a.questions:
        qs += [ln.strip() for ln in
               Path(a.questions).read_text(encoding="utf-8").splitlines()
               if ln.strip()]

    record, _root = build_sovereign(sources, questions=qs,
                                    n_queries=a.n_queries, sovereign=a.name)
    text = json.dumps(record, ensure_ascii=False, indent=2)
    if a.out:
        Path(a.out).write_text(text, encoding="utf-8")
        print(json.dumps({"verdict": record["verdict"], "wrote": a.out,
                          "shape": record["shape"]}, ensure_ascii=False, indent=2))
    else:
        print(text)
    return 0 if record["verdict"] == "ANSWER" else 1


# ======================================================================
# 記憶のソブリン (W4-m)
#
# この節より上は「文書から連合の木を組む」機能で、この節とは別物。
# ここから下は、人ごとの独立した貯蔵（1 ソブリン = 1 つの SQLite ファイル）。
#
#   階層: 貯蔵の中は追記専用（DB の層で UPDATE / DELETE / 置換を拒否）、
#   貯蔵という単位は利用者のもの（切り離し・持ち出し・手放しが単位ごと）。
#   Vera はソブリンのファイルを消さない・書き換えない。手放しは参照を切って
#   台帳へ RELEASE とハッシュを追記するだけで、ファイルを消すのは持ち主。
#
# 構造の側の台帳 <root>/structure.sqlite（追記専用）が、どのソブリンを読めるか
# を決める。詳細は docs/SOVEREIGN.md。
# ======================================================================
import functools
import hashlib
import os
import re
import shutil
import sqlite3
import urllib.parse
from collections.abc import Iterable, Mapping
from datetime import datetime, timezone
from typing import Callable, Protocol, runtime_checkable

SOVEREIGN_FORMAT = "verantyx.sovereign/1"
#: 名前の規則（公開版 vera session と同じ形）。
SOVEREIGN_NAME_RE = re.compile(r"[a-zA-Z0-9][a-zA-Z0-9_-]{0,63}")
EVENT_KINDS = ("utterance", "observation", "decision")
REGISTRY_OPS = ("CREATE", "ATTACH", "DETACH", "EXPORT", "RELEASE")
PROMOTION_KINDS = ("placement_evidence", "construction_evidence")
#: 事前登録（artifacts/w4-m/PREREG_W4m_promotion.md）の方針値。実測にもとづく値ではない。
PREREG_MIN_COUNT = 3
PREREG_MIN_DAYS = 2
_SOV_ROW_TABLES = ("meta", "consent_log", "event_log", "promotion_log")


# ---------------------------------------------------------------- types
@runtime_checkable
class Ledger(Protocol):
    """会話の台帳の契約（W3-c と同じ名前・同じ署名）。追記のみ。"""

    def append(self, event: Mapping[str, Any]) -> str: ...

    def events(self, since: Optional[str] = None) -> Iterable[Mapping[str, Any]]: ...

    def count(self, key: str, value: str) -> int: ...

    def last_seq(self, key: str, value: str) -> Optional[int]: ...


class SovereignUnavailable(LookupError):
    """読めない理由を型で分ける（「無い」「切り離した」「手放した」「読めない」は別）。"""

    verdict = "UNAVAILABLE"

    def __init__(self, store_id: Optional[str] = None, detail: Any = None):
        self.store_id = store_id
        self.detail = detail
        super().__init__(f"{self.verdict}: {store_id} {detail if detail is not None else ''}".strip())

    def as_dict(self) -> Dict[str, Any]:
        out: Dict[str, Any] = {"verdict": self.verdict, "store_id": self.store_id}
        if self.detail is not None:
            out["detail"] = self.detail
        return out


class UnknownStore(SovereignUnavailable):
    verdict = "UNKNOWN_STORE"


class Detached(SovereignUnavailable):
    verdict = "DETACHED"


class Released(SovereignUnavailable):
    verdict = "RELEASED"


class FileMissing(SovereignUnavailable):
    verdict = "UNREADABLE_FILE_MISSING"


class SchemaMismatch(SovereignUnavailable):
    verdict = "UNREADABLE_SCHEMA"


class NotSqlite(SovereignUnavailable):
    verdict = "UNREADABLE_NOT_SQLITE"


class UnknownSince(LookupError):
    """`since` がこの台帳の event id でない（空を返さず、分からないと言う）。"""

    verdict = "UNKNOWN_SINCE"


class LedgerRefusal(ValueError):
    """追記の拒否。code: BAD_KIND BAD_PAYLOAD EXTRA_KEYS UNKNOWN_CORRECTS_TARGET。"""

    def __init__(self, code: str, detail: Any = None):
        self.code = code
        self.verdict = code
        self.detail = detail
        super().__init__(f"{code}: {detail}" if detail is not None else code)


@dataclass(frozen=True)
class Sovereign:
    store_id: str
    owner: str
    created: str
    consent: Mapping[str, Any]  # {"promote": bool|None, "since": ts|None, "since_seq": int|None}
    status: str  # "ACTIVE" | "DETACHED" | "RELEASED"


@dataclass(frozen=True)
class PromotionRecord:
    """構造の側へ昇格する 1 件。出所は常に conversation:<store_id>。"""

    store_id: str
    kind: str
    payload: Mapping[str, Any]
    basis: str

    def __post_init__(self) -> None:
        if self.kind not in PROMOTION_KINDS:
            raise ValueError(f"kind must be one of {PROMOTION_KINDS}")
        if self.basis != f"conversation:{self.store_id}":
            raise ValueError("basis must be conversation:<store_id>")


# ------------------------------------------------- tables and triggers
def _sov_table(name: str, columns: str) -> List[str]:
    """表 1 つ分の文。主キーは seq だけ。他に UNIQUE・主キーを作らない。

    次の seq 以外の INSERT を拒否するトリガが、同じ seq の置換・飛んだ seq・
    seq 省略・OR IGNORE を止める。UNIQUE を足すと置換が古い行を黙って消せる
    ので足さない。
    """
    return [
        f"CREATE TABLE {name} (seq INTEGER PRIMARY KEY, {columns})",
        f"CREATE TRIGGER {name}_next_seq BEFORE INSERT ON {name} "
        f"WHEN NEW.seq IS NOT (SELECT IFNULL(MAX(seq),0)+1 FROM {name}) "
        f"BEGIN SELECT RAISE(ABORT, '{name} is append-only: seq must be next'); END",
        f"CREATE TRIGGER {name}_no_update BEFORE UPDATE ON {name} "
        f"BEGIN SELECT RAISE(ABORT, '{name} is append-only: no update'); END",
        f"CREATE TRIGGER {name}_no_delete BEFORE DELETE ON {name} "
        f"BEGIN SELECT RAISE(ABORT, '{name} is append-only: no delete'); END",
    ]


def _sov_statements(which: str) -> List[str]:
    kinds = ",".join(f"'{k}'" for k in EVENT_KINDS)
    ops = ",".join(f"'{o}'" for o in REGISTRY_OPS)
    pkinds = ",".join(f"'{k}'" for k in PROMOTION_KINDS)
    if which == "sovereign":
        out = _sov_table(
            "meta",
            f"format TEXT NOT NULL CHECK(format='{SOVEREIGN_FORMAT}'), "
            "store_id TEXT NOT NULL, owner TEXT NOT NULL, created TEXT NOT NULL")
        out.append(
            "CREATE TRIGGER meta_single BEFORE INSERT ON meta "
            "WHEN (SELECT COUNT(*) FROM meta) >= 1 "
            "BEGIN SELECT RAISE(ABORT, 'meta holds exactly one row'); END")
        out += _sov_table(
            "consent_log",
            "ts TEXT NOT NULL, promote INTEGER NOT NULL CHECK(promote IN (0,1)), "
            "since_seq INTEGER NOT NULL")
        out += _sov_table(
            "event_log",
            f"ts TEXT NOT NULL, kind TEXT NOT NULL CHECK(kind IN ({kinds})), "
            "payload TEXT NOT NULL")
        out += _sov_table(
            "promotion_log",
            "ts TEXT NOT NULL, promotion_id TEXT NOT NULL, kind TEXT NOT NULL, "
            "cand_key TEXT NOT NULL, structure_seq INTEGER NOT NULL, evidence TEXT NOT NULL, "
            "structure_ref TEXT NOT NULL")
        return out
    if which == "structure":
        out = _sov_table(
            "registry_log",
            f"ts TEXT NOT NULL, store_id TEXT NOT NULL, op TEXT NOT NULL CHECK(op IN ({ops})), "
            "path TEXT, file_sha256 TEXT, content_sha256 TEXT, detail TEXT")
        out += _sov_table(
            "promotion_log",
            f"ts TEXT NOT NULL, promotion_id TEXT NOT NULL, store_id TEXT NOT NULL, "
            f"kind TEXT NOT NULL CHECK(kind IN ({pkinds})), basis TEXT NOT NULL, "
            "payload TEXT NOT NULL, thresholds TEXT NOT NULL")
        # one row per (store_id, candidate): promotion_id is a function of (store_id, kind, key), so this
        # is the uniqueness of a candidate. A trigger and not a UNIQUE index (an index lets INSERT OR
        # REPLACE silently drop the old row; an ABORT leaves it). A retired row still counts: a candidate
        # that was promoted once is never promoted again in the same structure ledger.
        out.append(
            "CREATE TRIGGER promotion_log_one_per_candidate BEFORE INSERT ON promotion_log "
            "WHEN EXISTS (SELECT 1 FROM promotion_log "
            "WHERE store_id = NEW.store_id AND promotion_id = NEW.promotion_id) "
            "BEGIN SELECT RAISE(ABORT, 'DUPLICATE_PROMOTION'); END")
        out += _sov_table(
            "retire_log",
            "ts TEXT NOT NULL, promotion_seq INTEGER NOT NULL, promotion_id TEXT NOT NULL, "
            "store_id TEXT NOT NULL, reason TEXT NOT NULL CHECK(reason IN ('RELEASED')), "
            "registry_seq INTEGER")
        return out
    raise ValueError(which)


_SOV_EXPECTED: Dict[str, Dict[Tuple[str, str], str]] = {}


def _sov_expected(which: str) -> Dict[Tuple[str, str], str]:
    """期待する (type, name) -> sql。同じ文を空の接続に流して読み戻した定数。"""
    if which not in _SOV_EXPECTED:
        c = sqlite3.connect(":memory:", isolation_level=None)
        try:
            for s in _sov_statements(which):
                c.execute(s)
            _SOV_EXPECTED[which] = {
                (t, n): s for t, n, s in c.execute(
                    "SELECT type, name, sql FROM sqlite_master WHERE name NOT LIKE 'sqlite_%'")}
        finally:
            c.close()
    return _SOV_EXPECTED[which]


def _sov_dump(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, ensure_ascii=False,
                      separators=(",", ":"), allow_nan=False)


def _sov_ts(now: Optional[Callable[[], datetime]] = None) -> str:
    """UTC・秒精度の ISO 8601。tz の無い時刻は拒否する。"""
    t = now() if now is not None else datetime.now(timezone.utc)
    if not isinstance(t, datetime) or t.tzinfo is None or t.utcoffset() is None:
        raise ValueError("now must return a timezone-aware datetime")
    return t.astimezone(timezone.utc).isoformat(timespec="seconds")


def _sov_connect(path: str, write: bool) -> sqlite3.Connection:
    if write:
        return sqlite3.connect(path, isolation_level=None)
    uri = "file:" + urllib.parse.quote(os.path.abspath(path)) + "?mode=ro"
    return sqlite3.connect(uri, uri=True, isolation_level=None)


def _sov_check_shape(conn: sqlite3.Connection, which: str,
                     store_id: Optional[str]) -> None:
    """表とトリガの名前と sql が期待と一致し、meta が 1 行で store_id が合うこと。"""
    try:
        rows = conn.execute(
            "SELECT type, name, sql FROM sqlite_master WHERE name NOT LIKE 'sqlite_%'").fetchall()
    except sqlite3.DatabaseError as exc:
        if isinstance(exc, sqlite3.OperationalError) and "locked" in str(exc):
            raise
        raise NotSqlite(store_id, str(exc))
    got = {(t, n): s for t, n, s in rows}
    exp = _sov_expected(which)
    missing = sorted(f"{t}:{n}" for (t, n) in exp if (t, n) not in got)
    extra = sorted(f"{t}:{n}" for (t, n) in got if (t, n) not in exp)
    different = sorted(f"{t}:{n}" for (t, n) in exp if (t, n) in got and got[(t, n)] != exp[(t, n)])
    if missing or extra or different:
        raise SchemaMismatch(store_id, {"missing": missing, "unexpected": extra,
                                        "different": different})
    if which == "sovereign":
        metas = conn.execute("SELECT store_id FROM meta").fetchall()
        if len(metas) != 1:
            raise SchemaMismatch(store_id, {"meta_rows": len(metas)})
        if not SOVEREIGN_NAME_RE.fullmatch(str(metas[0][0])):
            raise SchemaMismatch(store_id, {"meta_store_id_not_a_valid_name": str(metas[0][0])})
        if store_id is not None and metas[0][0] != store_id:
            raise SchemaMismatch(store_id, {"meta_store_id": metas[0][0], "expected": store_id})


def _sov_insert(conn: sqlite3.Connection, table: str, cols: Mapping[str, Any]) -> int:
    """seq を明示して 1 行追記する（呼び手が BEGIN IMMEDIATE の中で呼ぶ）。"""
    seq = conn.execute(f"SELECT IFNULL(MAX(seq),0)+1 FROM {table}").fetchone()[0]
    names = ["seq"] + list(cols)
    conn.execute(
        f"INSERT INTO {table} ({','.join(names)}) VALUES ({','.join('?' * len(names))})",
        [seq] + list(cols.values()))
    return seq


def _sov_txn(conn: sqlite3.Connection, fn: Callable[[], Any]) -> Any:
    conn.execute("BEGIN IMMEDIATE")
    try:
        out = fn()
    except BaseException:
        conn.execute("ROLLBACK")
        raise
    conn.execute("COMMIT")
    return out


def sovereign_file_sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _sov_content_sha256(conn: sqlite3.Connection) -> str:
    parts = []
    for t in _SOV_ROW_TABLES:
        rows = conn.execute(f"SELECT * FROM {t} ORDER BY seq").fetchall()
        parts.append([t, [list(r) for r in rows]])
    return hashlib.sha256(_sov_dump(parts).encode("utf-8")).hexdigest()


# --------------------------------------------------- structure side
def _sov_struct_path(root: str) -> str:
    return os.path.join(os.fspath(root), "structure.sqlite")


def _sov_struct_open(root: str, *, write: bool = False,
                     create: bool = False) -> Optional[sqlite3.Connection]:
    """構造の側の台帳を開く。無ければ None（create のときだけ作る）。形を必ず検査する。"""
    path = _sov_struct_path(root)
    if not os.path.exists(path):
        if not create:
            return None
        os.makedirs(os.fspath(root), exist_ok=True)
        conn = sqlite3.connect(path, isolation_level=None)
        for s in _sov_statements("structure"):
            conn.execute(s)
        return conn
    conn = _sov_connect(path, write)
    try:
        _sov_check_shape(conn, "structure", None)
    except BaseException:
        conn.close()
        raise
    return conn


_REG_COLS = ("seq", "ts", "store_id", "op", "path", "file_sha256", "content_sha256", "detail")


def _sov_registry(conn: sqlite3.Connection, store_id: Optional[str] = None) -> List[Dict[str, Any]]:
    sql = f"SELECT {', '.join(_REG_COLS)} FROM registry_log"
    args: tuple = ()
    if store_id is not None:
        sql += " WHERE store_id = ?"
        args = (store_id,)
    out = []
    for r in conn.execute(sql + " ORDER BY seq", args):
        d = dict(zip(_REG_COLS, r))
        d["detail"] = json.loads(d["detail"]) if d["detail"] else {}
        out.append(d)
    return out


def _sov_struct_ref(conn: sqlite3.Connection) -> Optional[str]:
    """この構造の側の台帳を指す、決定的で動かない識別子（乱数を使わない）。

    registry_log の最初の行（追記専用なので書き換わらない）の正準 json の sha256。
    その行の detail には、台帳を作った root の絶対パス（`root`、`_sov_registry_append` が
    全行に入れる）が入る。最初の行が `attach --file` で、path が持ち出したファイルの場所
    （root を含まない）でも、root が違えば値が違う。同時に存在する 2 つの root が同じ
    絶対パスを持つことはない。残る重なり: root を移した後に元のパスで新しい root を作り
    同じ秒に同じ最初の行を書いた場合、`structure.sqlite` そのものの複製。台帳が空なら
    None。ソブリン側の back-link はこの値を持ち、どの台帳の seq を指すのかが
    export → 別の root で attach の後も曖昧にならない。
    """
    r = conn.execute(f"SELECT {', '.join(_REG_COLS)} FROM registry_log WHERE seq = 1").fetchone()
    if r is None:
        return None
    return hashlib.sha256(_sov_dump(list(r)).encode("utf-8")).hexdigest()


def _sov_fold(rows: Sequence[Mapping[str, Any]]) -> Optional[str]:
    """registry の行を seq 順に畳んで状態にする。RELEASED は動かない。"""
    st: Optional[str] = None
    for r in rows:
        if st == "RELEASED":
            break
        op = r["op"]
        if op in ("CREATE", "ATTACH"):
            st = "ACTIVE"
        elif op == "DETACH":
            st = "DETACHED"
        elif op == "RELEASE":
            st = "RELEASED"
    return st


def _sov_path_of(rows: Sequence[Mapping[str, Any]]) -> Optional[str]:
    path = None
    for r in rows:
        if r["op"] in ("CREATE", "ATTACH"):
            path = r["path"]
    return path


def _sov_state(root: str, store_id: str) -> Tuple[Optional[str], List[Dict[str, Any]]]:
    conn = _sov_struct_open(root)
    if conn is None:
        return None, []
    try:
        rows = _sov_registry(conn, store_id)
    finally:
        conn.close()
    return _sov_fold(rows), rows


def _sov_open_active(root: str, store_id: str, *, write: bool) -> Tuple[sqlite3.Connection, str]:
    """状態を引き直し、ACTIVE でなければ型つきの例外。形も検査して接続を返す。"""
    st, rows = _sov_state(root, store_id)
    if st is None:
        raise UnknownStore(store_id)
    if st == "DETACHED":
        raise Detached(store_id)
    if st == "RELEASED":
        raise Released(store_id)
    path = _sov_path_of(rows)
    if path is None or not os.path.exists(path):
        raise FileMissing(store_id, path)
    conn = _sov_connect(path, write)
    try:
        _sov_check_shape(conn, "sovereign", store_id)
    except BaseException:
        conn.close()
        raise
    return conn, path


def _sov_registry_append(root: str, *, store_id: str, op: str, path: Optional[str],
                         file_sha256: Optional[str], content_sha256: Optional[str],
                         detail: Mapping[str, Any], ts: str,
                         in_txn: Optional[Callable[[sqlite3.Connection, int], Mapping[str, Any]]] = None) -> int:
    """Append one registry row. `in_txn(conn, registry_seq)` (release only) runs inside the same
    transaction, before the row is written, and returns extra `detail` keys: whatever it wrote and
    the registry row are committed together or not at all."""
    conn = _sov_struct_open(root, write=True, create=(op in ("CREATE", "ATTACH")))
    if conn is None:
        raise UnknownStore(store_id)
    try:
        def work() -> int:
            extra: Mapping[str, Any] = {}
            if in_txn is not None:
                nxt = conn.execute("SELECT IFNULL(MAX(seq),0)+1 FROM registry_log").fetchone()[0]
                extra = in_txn(conn, nxt)
            return _sov_insert(conn, "registry_log", {
                "ts": ts, "store_id": store_id, "op": op, "path": path,
                "file_sha256": file_sha256, "content_sha256": content_sha256,
                "detail": _sov_dump({**dict(detail), **dict(extra),
                                     "root": os.path.abspath(os.fspath(root))})})
        return _sov_txn(conn, work)
    finally:
        conn.close()


def _sov_snapshot(path: Optional[str], store_id: str) -> Dict[str, Any]:
    """ファイルの状態をハッシュつきで写す。読めない型を例外にせず記録する。"""
    if path is None or not os.path.exists(path):
        return {"file_state": "MISSING", "file_sha256": None, "content_sha256": None,
                "consent": None}
    fh = sovereign_file_sha256(path)
    conn = _sov_connect(path, False)
    try:
        _sov_check_shape(conn, "sovereign", store_id)
        ch = _sov_content_sha256(conn)
        consent = _sov_consent(conn)
        return {"file_state": "PRESENT", "file_sha256": fh, "content_sha256": ch,
                "consent": consent}
    except SovereignUnavailable as exc:
        return {"file_state": exc.verdict, "file_sha256": fh, "content_sha256": None,
                "consent": None}
    finally:
        conn.close()


def _sov_consent(conn: sqlite3.Connection) -> Dict[str, Any]:
    r = conn.execute(
        "SELECT ts, promote, since_seq FROM consent_log ORDER BY seq DESC LIMIT 1").fetchone()
    if r is None:
        return {"promote": False, "since": None, "since_seq": None}
    return {"promote": bool(r[1]), "since": r[0], "since_seq": r[2]}


# ---------------------------------------------------------- ledger
def _sov_event_id(store_id: str, seq: int) -> str:
    return f"{store_id}:{seq}"


def _sov_parse_id(store_id: str, text: Any) -> Optional[int]:
    if not isinstance(text, str):
        return None
    head, sep, tail = text.rpartition(":")
    if not sep or head != store_id or not tail.isdigit() or tail != str(int(tail)):
        return None
    return int(tail)


class SovereignLedger:
    """`Ledger` の永続の実装。`open_ledger` だけが作る。

    すべての呼び出しの最初に構造の側の台帳で状態を引き直すので、開いた後に
    detach されたハンドルも読めない。
    """

    def __init__(self, root: str, store_id: str,
                 now: Optional[Callable[[], datetime]] = None):
        self._root = os.path.abspath(os.fspath(root))
        self.store_id = store_id
        self._now = now

    def _all(self, conn: sqlite3.Connection) -> List[Dict[str, Any]]:
        return [{"id": _sov_event_id(self.store_id, seq), "seq": seq, "ts": ts,
                 "kind": kind, "payload": json.loads(payload)}
                for seq, ts, kind, payload in conn.execute(
                    "SELECT seq, ts, kind, payload FROM event_log ORDER BY seq")]

    def append(self, event: Mapping[str, Any]) -> str:
        conn, _path = _sov_open_active(self._root, self.store_id, write=True)
        try:
            if not isinstance(event, Mapping):
                raise LedgerRefusal("BAD_PAYLOAD", "event must be a mapping")
            extra = sorted(str(k) for k in event if k not in ("kind", "payload"))
            if extra:
                raise LedgerRefusal("EXTRA_KEYS", extra)
            kind = event.get("kind")
            if kind not in EVENT_KINDS:
                raise LedgerRefusal("BAD_KIND", kind if isinstance(kind, str) else repr(kind))
            payload = event.get("payload")
            if not isinstance(payload, Mapping):
                raise LedgerRefusal("BAD_PAYLOAD", "payload must be a mapping")
            try:
                text = _sov_dump(dict(payload))
            except (TypeError, ValueError) as exc:
                raise LedgerRefusal("BAD_PAYLOAD", str(exc))
            if json.loads(text) != dict(payload):
                raise LedgerRefusal("BAD_PAYLOAD", "payload does not survive a json round trip")
            ts = _sov_ts(self._now)

            def work() -> int:
                if "corrects" in payload:
                    seq = _sov_parse_id(self.store_id, payload["corrects"])
                    ok = seq is not None and conn.execute(
                        "SELECT 1 FROM event_log WHERE seq = ?", (seq,)).fetchone()
                    if not ok:
                        raise LedgerRefusal("UNKNOWN_CORRECTS_TARGET", payload["corrects"])
                return _sov_insert(conn, "event_log",
                                   {"ts": ts, "kind": kind, "payload": text})

            return _sov_event_id(self.store_id, _sov_txn(conn, work))
        finally:
            conn.close()

    def events(self, since: Optional[str] = None) -> List[Dict[str, Any]]:
        """seq の昇順。since は「その事件より後」（その事件を含まない）。"""
        conn, _path = _sov_open_active(self._root, self.store_id, write=False)
        try:
            rows = self._all(conn)
        finally:
            conn.close()
        if since is None:
            return rows
        seq = _sov_parse_id(self.store_id, since)
        if seq is None or not any(r["seq"] == seq for r in rows):
            raise UnknownSince(since)
        return [r for r in rows if r["seq"] > seq]

    def _matching(self, key: str, value: Any) -> List[Dict[str, Any]]:
        return [e for e in self.events()
                if key in e["payload"]
                and type(e["payload"][key]) is type(value) and e["payload"][key] == value]

    def count(self, key: str, value: str) -> int:
        """生の数（訂正された事件も数える）。型も一致（3 と "3" は別）。"""
        return len(self._matching(key, value))

    def last_seq(self, key: str, value: str) -> Optional[int]:
        m = self._matching(key, value)
        return max(e["seq"] for e in m) if m else None


def open_ledger(root: str, store_id: str, *,
                now: Optional[Callable[[], datetime]] = None) -> SovereignLedger:
    """ACTIVE なソブリンの台帳。ACTIVE でなければ型つきの例外を投げる。"""
    root = os.path.abspath(os.fspath(root))
    conn, _path = _sov_open_active(root, store_id, write=False)
    conn.close()
    return SovereignLedger(root, store_id, now)


# ------------------------------------------------ unit operations
def _sov_typed(fn: Callable[..., Dict[str, Any]]) -> Callable[..., Dict[str, Any]]:
    """型つきの「読めない」を、dict の verdict にして返す（CLI 用）。"""

    @functools.wraps(fn)
    def wrapper(*args: Any, **kwargs: Any) -> Dict[str, Any]:
        try:
            return fn(*args, **kwargs)
        except SovereignUnavailable as exc:
            return exc.as_dict()
    return wrapper


def _sov_root(root: str) -> str:
    return os.path.abspath(os.fspath(root))


def _sov_unknown(store_id: Optional[str]) -> Dict[str, Any]:
    return {"verdict": "UNKNOWN_STORE", "store_id": store_id}


def describe(root: str, store_id: str) -> Sovereign:
    """状態は registry を畳んで決める。ACTIVE のときだけファイルから同意を読む。"""
    root = _sov_root(root)
    st, rows = _sov_state(root, store_id)
    if st is None:
        raise UnknownStore(store_id)
    first = rows[0]["detail"]
    consent: Mapping[str, Any] = {"promote": None, "since": None, "since_seq": None}
    for r in reversed(rows):
        if isinstance(r["detail"].get("consent"), Mapping):
            consent = r["detail"]["consent"]
            break
    if st == "ACTIVE":
        conn, _p = _sov_open_active(root, store_id, write=False)
        try:
            consent = _sov_consent(conn)
        finally:
            conn.close()
    return Sovereign(store_id=store_id, owner=first.get("owner"), created=first.get("created"),
                     consent=dict(consent), status=st)


@_sov_typed
def create(root: str, store_id: str, owner: str, *, consent_promote: bool = False,
           now: Optional[Callable[[], datetime]] = None) -> Dict[str, Any]:
    if not isinstance(store_id, str) or not SOVEREIGN_NAME_RE.fullmatch(store_id):
        return {"verdict": "REFUSED_BAD_STORE_ID", "store_id": store_id,
                "want": SOVEREIGN_NAME_RE.pattern}
    if not isinstance(owner, str) or not owner.strip():
        return {"verdict": "REFUSED_BAD_OWNER", "store_id": store_id}
    root = _sov_root(root)
    ts = _sov_ts(now)
    st, rows = _sov_state(root, store_id)
    if rows:
        return {"verdict": "REFUSED_STORE_ID_TAKEN", "store_id": store_id, "status": st}
    path = os.path.join(root, "stores", f"{store_id}.sqlite")
    if os.path.exists(path):
        return {"verdict": "REFUSED_FILE_EXISTS", "store_id": store_id, "path": path}
    os.makedirs(os.path.dirname(path), exist_ok=True)
    conn = sqlite3.connect(path, isolation_level=None)
    try:
        for s in _sov_statements("sovereign"):
            conn.execute(s)

        def work() -> None:
            _sov_insert(conn, "meta", {"format": SOVEREIGN_FORMAT, "store_id": store_id,
                                       "owner": owner, "created": ts})
            _sov_insert(conn, "consent_log", {"ts": ts, "promote": 1 if consent_promote else 0,
                                              "since_seq": 0})
        _sov_txn(conn, work)
    finally:
        conn.close()
    snap = _sov_snapshot(path, store_id)
    seq = _sov_registry_append(
        root, store_id=store_id, op="CREATE", path=path, file_sha256=snap["file_sha256"],
        content_sha256=snap["content_sha256"], ts=ts,
        detail={"owner": owner, "created": ts, "consent": snap["consent"]})
    return {"verdict": "CREATED", "store_id": store_id, "owner": owner, "path": path,
            "consent_promote": bool(consent_promote), "file_sha256": snap["file_sha256"],
            "content_sha256": snap["content_sha256"], "registry_seq": seq}


@_sov_typed
def set_consent(root: str, store_id: str, promote: bool, *,
                now: Optional[Callable[[], datetime]] = None) -> Dict[str, Any]:
    """同意の変更は consent_log への追記。最新の行が効き、since_seq はその時点の最後の事件。"""
    root = _sov_root(root)
    conn, _path = _sov_open_active(root, store_id, write=True)
    try:
        ts = _sov_ts(now)

        def work() -> int:
            last = conn.execute("SELECT IFNULL(MAX(seq),0) FROM event_log").fetchone()[0]
            _sov_insert(conn, "consent_log", {"ts": ts, "promote": 1 if promote else 0,
                                              "since_seq": last})
            return last
        since_seq = _sov_txn(conn, work)
    finally:
        conn.close()
    return {"verdict": "CONSENT_RECORDED", "store_id": store_id, "promote": bool(promote),
            "since": ts, "since_seq": since_seq}


@_sov_typed
def detach(root: str, store_id: str, *,
           now: Optional[Callable[[], datetime]] = None) -> Dict[str, Any]:
    """構造からの参照を切って読めなくする。ファイルには書かない・消さない。"""
    root = _sov_root(root)
    st, rows = _sov_state(root, store_id)
    if st is None:
        return _sov_unknown(store_id)
    if st == "RELEASED":
        return {"verdict": "RELEASED", "store_id": store_id}
    if st == "DETACHED":
        return {"verdict": "ALREADY_DETACHED", "store_id": store_id}
    path = _sov_path_of(rows)
    snap = _sov_snapshot(path, store_id)
    seq = _sov_registry_append(
        root, store_id=store_id, op="DETACH", path=path, file_sha256=snap["file_sha256"],
        content_sha256=snap["content_sha256"], ts=_sov_ts(now),
        detail={"file_state": snap["file_state"], "consent": snap["consent"]})
    return {"verdict": "DETACHED", "store_id": store_id, "file_state": snap["file_state"],
            "file_sha256": snap["file_sha256"], "file_left_in_place": path, "registry_seq": seq}


@_sov_typed
def attach(root: str, store_id: Optional[str] = None, file: Optional[str] = None, *,
           now: Optional[Callable[[], datetime]] = None) -> Dict[str, Any]:
    """(a) store_id: 切り離したものを戻す。(b) file: 持ち出した 1 ファイルをその場所のまま登録（複製しない）。"""
    root = _sov_root(root)
    if (store_id is None) == (file is None):
        return {"verdict": "REFUSED_BAD_ARGUMENTS",
                "want": "exactly one of store_id or file"}
    if store_id is not None:
        st, rows = _sov_state(root, store_id)
        if st is None:
            return _sov_unknown(store_id)
        if st == "RELEASED":
            return {"verdict": "REFUSED_RELEASED", "store_id": store_id}
        if st == "ACTIVE":
            return {"verdict": "ALREADY_ACTIVE", "store_id": store_id}
        path = _sov_path_of(rows)
        if path is None or not os.path.exists(path):
            raise FileMissing(store_id, path)
        fh = sovereign_file_sha256(path)
        conn = _sov_connect(path, False)
        try:
            _sov_check_shape(conn, "sovereign", store_id)
            ch = _sov_content_sha256(conn)
            consent = _sov_consent(conn)
        finally:
            conn.close()
        last_detach = [r for r in rows if r["op"] == "DETACH"][-1]
        same = last_detach["file_sha256"] == fh
        seq = _sov_registry_append(
            root, store_id=store_id, op="ATTACH", path=path, file_sha256=fh,
            content_sha256=ch, ts=_sov_ts(now),
            detail={"same_as_detached": same, "source": "store_id", "consent": consent})
        return {"verdict": "ATTACHED", "store_id": store_id, "path": path,
                "same_as_detached": same, "file_sha256": fh, "content_sha256": ch,
                "registry_seq": seq}
    path = os.path.abspath(os.fspath(file))
    if not os.path.isfile(path):
        raise FileMissing(None, path)
    conn = _sov_connect(path, False)
    try:
        _sov_check_shape(conn, "sovereign", None)
        meta = conn.execute("SELECT store_id, owner, created FROM meta").fetchone()
        ch = _sov_content_sha256(conn)
        consent = _sov_consent(conn)
    finally:
        conn.close()
    sid, owner, created = meta
    fh = sovereign_file_sha256(path)
    st, _rows = _sov_state(root, sid)
    if st == "RELEASED":
        return {"verdict": "REFUSED_RELEASED", "store_id": sid}
    if st is not None:
        return {"verdict": "REFUSED_STORE_ID_CONFLICT", "store_id": sid, "status": st}
    seq = _sov_registry_append(
        root, store_id=sid, op="ATTACH", path=path, file_sha256=fh, content_sha256=ch,
        ts=_sov_ts(now),
        detail={"same_as_detached": None, "source": "file", "owner": owner,
                "created": created, "consent": consent})
    return {"verdict": "ATTACHED", "store_id": sid, "path": path, "same_as_detached": None,
            "file_sha256": fh, "content_sha256": ch, "registry_seq": seq}


@_sov_typed
def export(root: str, store_id: str, to: str, *,
           now: Optional[Callable[[], datetime]] = None) -> Dict[str, Any]:
    """1 ファイルで持ち出す（バイト複製・ハッシュつき）。利用者が指示した 1 か所にだけ書く。"""
    root = _sov_root(root)
    st, rows = _sov_state(root, store_id)
    if st is None:
        return _sov_unknown(store_id)
    if st in ("RELEASED", "DETACHED"):
        return {"verdict": st, "store_id": store_id}
    to = os.path.abspath(os.fspath(to))
    if os.path.lexists(to):
        return {"verdict": "REFUSED_DESTINATION_EXISTS", "to": to}
    if not os.path.isdir(os.path.dirname(to)):
        return {"verdict": "REFUSED_DESTINATION_PARENT_MISSING", "to": to}
    path = _sov_path_of(rows)
    # a sidecar is checked before the file is opened: opening could roll a hot journal back
    sidecars = [path + s for s in ("-journal", "-wal", "-shm") if path and os.path.exists(path + s)]
    if sidecars:
        return {"verdict": "REFUSED_HOT_JOURNAL", "store_id": store_id, "sidecars": sidecars}
    conn, path = _sov_open_active(root, store_id, write=False)
    try:
        ch = _sov_content_sha256(conn)
    finally:
        conn.close()
    src_hash = sovereign_file_sha256(path)
    shutil.copyfile(path, to)
    dst_hash = sovereign_file_sha256(to)
    if src_hash != dst_hash:
        return {"verdict": "EXPORT_HASH_MISMATCH", "store_id": store_id, "to": to,
                "source_sha256": src_hash, "copy_sha256": dst_hash,
                "note": "the copy is left in place; delete it yourself if you do not want it"}
    seq = _sov_registry_append(
        root, store_id=store_id, op="EXPORT", path=path, file_sha256=src_hash,
        content_sha256=ch, ts=_sov_ts(now), detail={"to": to})
    return {"verdict": "EXPORTED", "store_id": store_id, "to": to, "file_sha256": dst_hash,
            "content_sha256": ch, "registry_seq": seq}


# ------------------------------------------- promotions: structure side
_PROMO_COLS = ("seq", "ts", "promotion_id", "store_id", "kind", "basis", "payload", "thresholds")
_RETIRE_COLS = ("seq", "ts", "promotion_seq", "promotion_id", "store_id", "reason", "registry_seq")


def _sov_load_promotions(conn: sqlite3.Connection,
                         store_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """構造の側の昇格の行。退役の行（あれば）を "retired" に添える。消えた行は無い。"""
    where, args = ("", ()) if store_id is None else (" WHERE store_id = ?", (store_id,))
    retired = {}
    for r in conn.execute(f"SELECT {', '.join(_RETIRE_COLS)} FROM retire_log{where} ORDER BY seq", args):
        d = dict(zip(_RETIRE_COLS, r))
        retired[d["promotion_seq"]] = d
    out = []
    for r in conn.execute(f"SELECT {', '.join(_PROMO_COLS)} FROM promotion_log{where} ORDER BY seq", args):
        d = dict(zip(_PROMO_COLS, r))
        d["payload"] = json.loads(d["payload"])
        d["thresholds"] = json.loads(d["thresholds"])
        d["retired"] = retired.get(d["seq"])
        out.append(d)
    return out


def _sov_retire_rows(conn: sqlite3.Connection, store_id: str, ts: str, reg: int) -> int:
    """retire_log へ、そのソブリン由来の退役していない昇格を追記する（呼び手が書き込みトランザクションの中で呼ぶ）。"""
    n = 0
    for p in _sov_load_promotions(conn, store_id):
        if p["retired"] is None:
            _sov_insert(conn, "retire_log", {
                "ts": ts, "promotion_seq": p["seq"], "promotion_id": p["promotion_id"],
                "store_id": store_id, "reason": "RELEASED", "registry_seq": reg})
            n += 1
    return n


def _sov_retire(root: str, store_id: str, ts: str,
                registry_seq: Optional[int]) -> int:
    """そのソブリン由来の、退役していない昇格を retire_log へ追記する（削除しない）。"""
    conn = _sov_struct_open(root, write=True)
    if conn is None:
        return 0
    try:
        def work() -> int:
            reg = registry_seq
            if reg is None:
                reg = conn.execute("SELECT IFNULL(MAX(seq),0)+1 FROM registry_log").fetchone()[0]
            return _sov_retire_rows(conn, store_id, ts, reg)
        return _sov_txn(conn, work)
    finally:
        conn.close()


@_sov_typed
def release(root: str, store_id: str, confirm: str, *,
            now: Optional[Callable[[], datetime]] = None) -> Dict[str, Any]:
    """利用者の明示の指示（--confirm が store_id と完全一致）で手放す。

    Vera は参照を切り、台帳に RELEASE とハッシュを追記し、そのソブリン由来の昇格分
    を退役の追記にするだけ。ファイルには触れず、消さない。消すのは持ち主。
    """
    root = _sov_root(root)
    if confirm != store_id:
        return {"verdict": "REFUSED_NOT_CONFIRMED", "store_id": store_id,
                "want": "--confirm <store_id> (exactly the same text)"}
    st, rows = _sov_state(root, store_id)
    if st is None:
        return _sov_unknown(store_id)
    ts = _sov_ts(now)
    if st == "RELEASED":
        rel = [r for r in rows if r["op"] == "RELEASE"][-1]
        again = _sov_retire(root, store_id, ts, rel["seq"])
        return {"verdict": "ALREADY_RELEASED", "store_id": store_id,
                "retired_on_rerun": again, "file_sha256": rel["file_sha256"]}
    path = _sov_path_of(rows)
    snap = _sov_snapshot(path, store_id)
    last_known = None
    for r in rows:
        if r["file_sha256"] is not None:
            last_known = r["file_sha256"]
    retired_first = _sov_retire(root, store_id, ts, None)
    late: List[int] = []

    def retire_late(conn: sqlite3.Connection, reg: int) -> Mapping[str, Any]:
        # a promote that wrote between the retirement above and this row is retired in the SAME
        # transaction as the RELEASE row, so no promotion is live once RELEASE exists
        late.append(_sov_retire_rows(conn, store_id, ts, reg))
        return {"retired_this_run": retired_first + late[0], "retired_with_release": late[0]}

    detail: Dict[str, Any] = {"file_state": snap["file_state"], "consent": snap["consent"]}
    if snap["file_sha256"] is None:
        detail["last_known_file_sha256"] = last_known
    seq = _sov_registry_append(
        root, store_id=store_id, op="RELEASE", path=path, file_sha256=snap["file_sha256"],
        content_sha256=snap["content_sha256"], ts=ts, detail=detail, in_txn=retire_late)
    retired_now = retired_first + (late[0] if late else 0)
    conn = _sov_struct_open(root)
    try:
        retired_total = len([p for p in _sov_load_promotions(conn, store_id)
                             if p["retired"] is not None])
    finally:
        conn.close()
    present = snap["file_state"] != "MISSING"
    return {"verdict": "RELEASED", "store_id": store_id, "file_state": snap["file_state"],
            "file_sha256": snap["file_sha256"],
            "last_known_file_sha256": last_known if snap["file_sha256"] is None else None,
            "retired": retired_total, "retired_this_run": retired_now,
            "file_left_in_place": path if present else None,
            "registry_seq": seq,
            "note": "Vera detached its reference and did not touch the file; deleting it is the owner's operation"}


@_sov_typed
def status(root: str, store_id: Optional[str] = None) -> Dict[str, Any]:
    """登録の一覧（書かない）。構造の側の台帳が無いのと、ソブリンが無いのは別の答え。"""
    root = _sov_root(root)
    conn = _sov_struct_open(root)
    if conn is None:
        if store_id is not None:
            return _sov_unknown(store_id)
        return {"verdict": "ANSWER", "structure": "ABSENT", "stores": []}
    try:
        rows = _sov_registry(conn, store_id)
        promos = _sov_load_promotions(conn, store_id)
    finally:
        conn.close()
    if store_id is not None and not rows:
        return _sov_unknown(store_id)
    order: List[str] = []
    by: Dict[str, List[Dict[str, Any]]] = {}
    for r in rows:
        if r["store_id"] not in by:
            order.append(r["store_id"])
            by[r["store_id"]] = []
        by[r["store_id"]].append(r)
    stores = []
    for sid in order:
        rs = by[sid]
        path = _sov_path_of(rs)
        mine = [p for p in promos if p["store_id"] == sid]
        stores.append({
            "store_id": sid, "status": _sov_fold(rs), "owner": rs[0]["detail"].get("owner"),
            "path": path, "file_present": bool(path and os.path.exists(path)),
            "registry_rows": len(rs),
            "promotions_active": len([p for p in mine if p["retired"] is None]),
            "promotions_retired": len([p for p in mine if p["retired"] is not None])})
    return {"verdict": "ANSWER", "structure": "PRESENT", "stores": stores}


def _sov_promotions_read(root: str, store_id: Optional[str]) -> Tuple[Optional[str], List[Dict[str, Any]]]:
    """(構造の側の状態, 昇格の行)。状態は PRESENT / ABSENT。登録の無い store_id は UnknownStore。"""
    conn = _sov_struct_open(_sov_root(root))
    if conn is None:
        if store_id is not None:
            raise UnknownStore(store_id)
        return "ABSENT", []
    try:
        if store_id is not None and not _sov_registry(conn, store_id):
            raise UnknownStore(store_id)
        return "PRESENT", _sov_load_promotions(conn, store_id)
    finally:
        conn.close()


def active_promotions(root: str, store_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """退役していない昇格だけ。これが「観測の候補」の入口。

    登録の無い store_id は空の列にせず UnknownStore を投げる（「候補が 0 件」と「そんなソブリン
    は無い」は別の答え）。store_id なしで構造の側の台帳が無い root は空の列を返すが、それが
    「昇格 0 件」なのか「台帳が無い」のかは `promotions_answer` の `structure` で分かる。
    """
    return [p for p in _sov_promotions_read(root, store_id)[1] if p["retired"] is None]


def all_promotions(root: str, store_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """構造の側の昇格のすべて（退役の行つき）。未登録の store_id は UnknownStore（active と同じ）。"""
    return _sov_promotions_read(root, store_id)[1]


@_sov_typed
def promotions_answer(root: str, store_id: Optional[str] = None, *,
                      include_retired: bool = False) -> Dict[str, Any]:
    """昇格の一覧を型つきの 1 つの答えにする（CLI の入口）。

    `structure` は PRESENT / ABSENT（台帳が無い root。何も作らない）、未登録の store_id は
    UNKNOWN_STORE。「昇格 0 件」「台帳が無い」「そんなソブリンは無い」は別々の答え。
    """
    state, rows = _sov_promotions_read(root, store_id)
    if not include_retired:
        rows = [p for p in rows if p["retired"] is None]
    return {"verdict": "ANSWER", "structure": state,
            "scope": "all" if include_retired else "active", "promotions": rows}


def trace_promotion(root: str, promotion_id: str) -> Dict[str, Any]:
    """構造の側の行・ソブリンの側の行・退役の行をまとめて返す。

    ソブリンが ACTIVE でなければ構造の側だけ返し、ソブリン側は型つきの理由を添える。
    ソブリン側の back-link は、`structure_ref` がこの root の構造の側の台帳と一致し、かつ
    `structure_seq` の行の promotion_id が同じものだけを `rows` に入れる。別の台帳を指す
    もの（export → 別の root で attach したファイルに入っていた分）は `other_structures`、
    同じ台帳を指すが行が合わないものは `mismatched` に、捨てずに分けて返す。
    """
    root = _sov_root(root)
    conn = _sov_struct_open(root)
    if conn is None:
        return {"verdict": "UNKNOWN_PROMOTION", "promotion_id": promotion_id}
    try:
        allp = _sov_load_promotions(conn)
        sref = _sov_struct_ref(conn)
    finally:
        conn.close()
    mine = [p for p in allp if p["promotion_id"] == promotion_id]
    if not mine:
        return {"verdict": "UNKNOWN_PROMOTION", "promotion_id": promotion_id}
    pid_at = {p["seq"]: p["promotion_id"] for p in allp}
    sid = mine[0]["store_id"]
    side: Dict[str, Any]
    try:
        sconn, _p = _sov_open_active(root, sid, write=False)
        try:
            found = [
                {"seq": s, "ts": t, "promotion_id": pid, "kind": k, "key": ck,
                 "structure_seq": ss, "evidence": json.loads(ev), "structure_ref": ref}
                for s, t, pid, k, ck, ss, ev, ref in sconn.execute(
                    "SELECT seq, ts, promotion_id, kind, cand_key, structure_seq, evidence, "
                    "structure_ref FROM promotion_log WHERE promotion_id = ? ORDER BY seq",
                    (promotion_id,))]
        finally:
            sconn.close()
        side = {"verdict": "ANSWER",
                "rows": [r for r in found if r["structure_ref"] == sref
                         and pid_at.get(r["structure_seq"]) == promotion_id],
                "other_structures": [r for r in found if r["structure_ref"] != sref],
                "mismatched": [r for r in found if r["structure_ref"] == sref
                               and pid_at.get(r["structure_seq"]) != promotion_id]}
    except SovereignUnavailable as exc:
        side = exc.as_dict()
    return {"verdict": "ANSWER", "promotion_id": promotion_id, "store_id": sid,
            "structure_ref": sref, "structure": mine, "sovereign": side,
            "retired": [p["retired"] for p in mine if p["retired"] is not None]}


# ------------------------------------------------------- promotion
def _sov_promotion_id(store_id: str, kind: str, key: str) -> str:
    return hashlib.sha256(f"{store_id}\x1f{kind}\x1f{key}".encode("utf-8")).hexdigest()[:24]


def _sov_cell_key(cell: Any) -> str:
    if isinstance(cell, str):
        return cell
    return json.dumps(cell, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


_SOV_COUNT_KEYS = ("outside_consent_window", "superseded_by_correction", "not_a_candidate",
                   "below_count", "below_days", "conflicting_occupancy",
                   "unknown_occupancy", "already_promoted", "promoted_events")


def _sov_analyze(events: Sequence[Mapping[str, Any]], since_seq: int, n: int, d: int,
                 store_id: str, active_ids: set) -> Tuple[Dict[str, int], List[Dict[str, Any]]]:
    """窓の中の事件を、1 件残らずどれかの分類に入れる（事前登録 §6）。

    返す昇格の候補は、最初の evidence の seq の順（表示のため。勝者選びではない）。
    """
    counts: Dict[str, int] = {k: 0 for k in _SOV_COUNT_KEYS}
    counts["candidates"] = 0
    corrected = {e["payload"]["corrects"] for e in events
                 if isinstance(e["payload"].get("corrects"), str)}
    live = []
    for e in events:
        if e["seq"] <= since_seq:
            counts["outside_consent_window"] += 1
        elif e["id"] in corrected:
            counts["superseded_by_correction"] += 1
        else:
            live.append(e)
    cells: Dict[str, Dict[str, List[Mapping[str, Any]]]] = {}
    phrases: Dict[str, List[Mapping[str, Any]]] = {}
    for e in live:
        p = e["payload"]
        cell = p.get("cell")
        phrase = p.get("phrase")
        if e["kind"] == "observation" and cell not in (None, "", [], {}):
            occ = p.get("occupied")
            if occ == "UNOCCUPIED":
                tag = "U"
            elif occ is None or (isinstance(occ, str) and occ.startswith("UNKNOWN")):
                tag = "K"
            else:
                tag = "X"
            cells.setdefault(_sov_cell_key(cell), {"U": [], "X": [], "K": []})[tag].append(e)
        elif e["kind"] == "utterance" and isinstance(phrase, str) and phrase != "":
            phrases.setdefault(phrase, []).append(e)
        else:
            counts["not_a_candidate"] += 1
    groups: List[Tuple[str, str, List[Mapping[str, Any]]]] = []
    for ck, g in cells.items():
        if g["U"] and (g["X"] or g["K"]):
            counts["candidates"] += 1
            counts["conflicting_occupancy"] += len(g["U"]) + len(g["X"]) + len(g["K"])
        elif not g["U"]:
            counts["unknown_occupancy"] += len(g["K"])
            counts["not_a_candidate"] += len(g["X"])
        else:
            groups.append(("placement_evidence", ck, g["U"]))
    for ph, evs in phrases.items():
        groups.append(("construction_evidence", ph, evs))
    to_promote: List[Dict[str, Any]] = []
    for kind, key, evs in groups:
        counts["candidates"] += 1
        days = len({e["ts"][:10] for e in evs})
        pid = _sov_promotion_id(store_id, kind, key)
        if pid in active_ids:
            counts["already_promoted"] += len(evs)
        elif len(evs) < n:
            counts["below_count"] += len(evs)
        elif days < d:
            counts["below_days"] += len(evs)
        else:
            counts["promoted_events"] += len(evs)
            to_promote.append({"promotion_id": pid, "kind": kind, "key": key,
                               "count": len(evs), "days": days,
                               "evidence": [e["id"] for e in evs],
                               "first_seq": min(e["seq"] for e in evs)})
    to_promote.sort(key=lambda g: g["first_seq"])
    return counts, to_promote


def _sov_consent_key(consent: Mapping[str, Any]) -> Tuple[Any, Any, Any]:
    return (consent.get("promote"), consent.get("since"), consent.get("since_seq"))


def _sov_append_structure_promotion(root: str, store_id: str, todo: Sequence[Mapping[str, Any]],
                                    thresholds: Mapping[str, Any], ts: str,
                                    consent0: Mapping[str, Any]) -> Dict[str, Any]:
    """The write stage of promote: ONE transaction pair, taken in the order structure -> sovereign.

    Nothing is analysed here. Under BEGIN IMMEDIATE on the structure ledger (the lock that serializes
    two promotes and a release) the state is read again: the registry must still be ACTIVE and no
    retirement may have started; then the sovereign file is opened and locked the same way and the
    consent is read again: it must still be on and equal to the consent the analysis read
    (`consent0`). Only then are the candidates appended to the structure side (a candidate that is
    already there is refused by the trigger and returned in `refused`, nothing is written for it).
    The structure side is committed; the sovereign side only held its lock (ROLLBACK, nothing
    written), so a consent that is withdrawn after this point cannot undo a row already committed
    but cannot be raced past either: set_consent needs the lock this stage held while it checked.

    Returns {"stopped": None | {verdict ...}, "written": [{promotion_id, structure_seq}],
    "refused": [{promotion_id, reason}]}.
    """
    conn = _sov_struct_open(root, write=True)
    if conn is None:
        raise UnknownStore(store_id)
    sconn: Optional[sqlite3.Connection] = None
    structure_open = False
    sovereign_open = False
    try:
        conn.execute("BEGIN IMMEDIATE")
        structure_open = True
        rows = _sov_registry(conn, store_id)
        st = _sov_fold(rows)
        if st is None:
            raise UnknownStore(store_id)
        if st == "DETACHED":
            return {"stopped": {"verdict": "DETACHED", "store_id": store_id, "wrote": 0},
                    "written": [], "refused": []}
        if st == "RELEASED":
            return {"stopped": {"verdict": "RELEASED", "store_id": store_id, "wrote": 0},
                    "written": [], "refused": []}
        started = conn.execute("SELECT COUNT(*) FROM retire_log WHERE store_id = ?",
                               (store_id,)).fetchone()[0]
        if started:
            return {"stopped": {"verdict": "RELEASE_IN_PROGRESS", "store_id": store_id, "wrote": 0,
                                "retired_rows": started,
                                "want": "run release again with --confirm to finish it"},
                    "written": [], "refused": []}
        path = _sov_path_of(rows)
        if path is None or not os.path.exists(path):
            raise FileMissing(store_id, path)
        sconn = _sov_connect(path, True)
        _sov_check_shape(sconn, "sovereign", store_id)
        sconn.execute("BEGIN IMMEDIATE")
        sovereign_open = True
        consent = _sov_consent(sconn)
        if not consent["promote"]:
            return {"stopped": {"verdict": "NO_CONSENT", "store_id": store_id, "consent": consent,
                                "wrote": 0},
                    "written": [], "refused": []}
        if _sov_consent_key(consent) != _sov_consent_key(consent0):
            return {"stopped": {"verdict": "CONSENT_CHANGED", "store_id": store_id,
                                "consent": consent, "consent_at_start": dict(consent0),
                                "wrote": 0},
                    "written": [], "refused": []}
        written: List[Dict[str, Any]] = []
        refused: List[Dict[str, Any]] = []
        for g in todo:
            payload = {"key": g["key"], "count": g["count"], "days": g["days"],
                       "evidence": g["evidence"]}
            rec = PromotionRecord(store_id=store_id, kind=g["kind"],
                                  basis=f"conversation:{store_id}", payload=payload)
            try:
                seq = _sov_insert(conn, "promotion_log", {
                    "ts": ts, "promotion_id": g["promotion_id"], "store_id": store_id,
                    "kind": rec.kind, "basis": rec.basis, "payload": _sov_dump(dict(rec.payload)),
                    "thresholds": _sov_dump(dict(thresholds))})
            except sqlite3.IntegrityError as exc:
                if "DUPLICATE_PROMOTION" not in str(exc):
                    raise
                refused.append({"promotion_id": g["promotion_id"], "reason": "DUPLICATE_PROMOTION"})
                continue
            written.append({"promotion_id": g["promotion_id"], "structure_seq": seq})
        conn.execute("COMMIT")
        structure_open = False
        sconn.execute("ROLLBACK")      # the sovereign side was only locked and read
        sovereign_open = False
        return {"stopped": None, "written": written, "refused": refused}
    finally:
        # on every path out the transactions are closed; a stop returns here with both still open
        if sovereign_open and sconn is not None:
            sconn.execute("ROLLBACK")
        if structure_open:
            conn.execute("ROLLBACK")
        if sconn is not None:
            sconn.close()
        conn.close()


def _sov_append_backlink(root: str, store_id: str, promotion_id: str, kind: str, key: str,
                         structure_seq: int, evidence: Sequence[str], ts: str,
                         structure_ref: str) -> int:
    """Append the sovereign side's back-link, once: an identical link already there is not added again
    (the repair at the start of two promotes that run together must not double it)."""
    conn, _path = _sov_open_active(root, store_id, write=True)
    try:
        def work() -> int:
            same = conn.execute(
                "SELECT seq FROM promotion_log WHERE promotion_id = ? AND structure_seq = ? "
                "AND structure_ref = ? ORDER BY seq LIMIT 1",
                (promotion_id, structure_seq, structure_ref)).fetchone()
            if same is not None:
                return same[0]
            return _sov_insert(conn, "promotion_log", {
                "ts": ts, "promotion_id": promotion_id, "kind": kind, "cand_key": key,
                "structure_seq": structure_seq, "evidence": _sov_dump(list(evidence)),
                "structure_ref": structure_ref})
        return _sov_txn(conn, work)
    finally:
        conn.close()


@_sov_typed
def promote(root: str, store_id: str, *, min_count: Optional[int] = None,
            min_days: Optional[int] = None,
            now: Optional[Callable[[], datetime]] = None) -> Dict[str, Any]:
    """同意のあるソブリンの、繰り返し観測された未占有の升・言い回しを構造の側へ昇格する。

    同意が無ければ何も書かない（NO_CONSENT）。解析は読むだけ（ロックなし）で、書き込みは
    `_sov_append_structure_promotion` の 1 つのトランザクション（構造 → ソブリンの順にロック）の中で、
    登録の状態・退役の開始・同意をもう一度確かめてから行う（RELEASED / DETACHED / RELEASE_IN_PROGRESS /
    NO_CONSENT / CONSENT_CHANGED は書かずに止まる）。同じ候補が既に構造の側にあれば、一意のトリガが
    拒否し、`refused`（DUPLICATE_PROMOTION）に数えて追記しない。構造の側が確定した後に候補ごとに
    ソブリンの側へ back-link を追記する（途中で止まっても次の実行が補修する）。返す `promoted` の並びは
    evidence の最初の seq の順で、表示のため（勝者選びではない）。
    しきい値は事前登録（PREREG_MIN_COUNT / PREREG_MIN_DAYS）で、方針値であり実測にもとづく値ではない。
    """
    root = _sov_root(root)
    override = min_count is not None or min_days is not None
    n = PREREG_MIN_COUNT if min_count is None else min_count
    d = PREREG_MIN_DAYS if min_days is None else min_days
    if not (isinstance(n, int) and isinstance(d, int)) or isinstance(n, bool) \
            or isinstance(d, bool) or n < 1 or d < 1:
        return {"verdict": "REFUSED_BAD_THRESHOLDS", "min_count": n, "min_days": d}
    thresholds = {"n": n, "d": d, "source": "override" if override else "prereg"}
    ts = _sov_ts(now)
    conn, _path = _sov_open_active(root, store_id, write=False)
    try:
        consent = _sov_consent(conn)
        events = [{"id": _sov_event_id(store_id, s), "seq": s, "ts": t, "kind": k,
                   "payload": json.loads(p)}
                  for s, t, k, p in conn.execute(
                      "SELECT seq, ts, kind, payload FROM event_log ORDER BY seq")]
        back_all = conn.execute(
            "SELECT promotion_id, structure_seq, structure_ref FROM promotion_log").fetchall()
    finally:
        conn.close()
    if not consent["promote"]:
        return {"verdict": "NO_CONSENT", "store_id": store_id, "consent": consent,
                "wrote": 0, "thresholds": thresholds}
    sconn = _sov_struct_open(root)
    try:
        sref = _sov_struct_ref(sconn)
        loaded = _sov_load_promotions(sconn, store_id)
        existing = [p for p in loaded if p["retired"] is None]
        release_started = [r for r in sconn.execute(
            "SELECT seq FROM retire_log WHERE store_id = ?", (store_id,))]
    finally:
        sconn.close()
    if release_started:
        # release wrote retirements and stopped before RELEASE: promoting now would make the
        # same promotion_id live again beside its retired row. Re-run release first.
        return {"verdict": "RELEASE_IN_PROGRESS", "store_id": store_id, "wrote": 0,
                "retired_rows": len(release_started),
                "want": "run release again with --confirm to finish it"}
    # only back-links that name THIS structure ledger and the row they point at count; links
    # that came along in an exported file name another ledger and are left alone (not dropped)
    back = {(pid, sseq) for pid, sseq, ref in back_all if ref == sref}
    repaired = 0
    for p in existing:
        if (p["promotion_id"], p["seq"]) not in back:
            _sov_append_backlink(root, store_id, p["promotion_id"], p["kind"],
                                 p["payload"]["key"], p["seq"], p["payload"]["evidence"], ts, sref)
            repaired += 1
    counts, todo = _sov_analyze(events, consent["since_seq"], n, d, store_id,
                                {p["promotion_id"] for p in existing})
    stage = _sov_append_structure_promotion(root, store_id, todo, thresholds, ts, consent)
    if stage["stopped"] is not None:
        return {**stage["stopped"], "thresholds": thresholds, "analysed_candidates": len(todo)}
    by_id = {g["promotion_id"]: g for g in todo}
    done = []
    for w in stage["written"]:
        g = by_id[w["promotion_id"]]
        bseq = _sov_append_backlink(root, store_id, g["promotion_id"], g["kind"], g["key"],
                                    w["structure_seq"], g["evidence"], ts, sref)
        done.append({"promotion_id": g["promotion_id"], "kind": g["kind"], "key": g["key"],
                     "count": g["count"], "days": g["days"], "structure_seq": w["structure_seq"],
                     "sovereign_seq": bseq})
    counts["promoted"] = len(done)
    counts["duplicate_promotion"] = len(stage["refused"])
    counts["repaired_backlink"] = repaired
    counts["events_total"] = len(events)
    return {"verdict": "PROMOTED" if done else "NOTHING_TO_PROMOTE", "store_id": store_id,
            "basis": f"conversation:{store_id}", "promoted": done, "refused": stage["refused"],
            "counts": counts, "thresholds": thresholds, "consent": consent}


# ------------------------------------------------------- basis confirmation (W6-a)
#: 利用者が「生成コーパスの文は正しい」と答えた記録 / 「正しくない」と答えた記録の status。
BASIS_CONFIRMATION_STATUSES = ("HUMAN_CONFIRMED", "REJECTED_GENERATED")
#: 昇格の候補の数え上げ・訂正が読む鍵。確認の記録には入れない（昇格や訂正の対象にしない）。
_SOV_CONFIRMATION_FORBIDDEN_KEYS = ("phrase", "cell", "occupied", "corrects")


def basis_confirmation_destination(root: str, store_id: str) -> Dict[str, Any]:
    """確認 id を束縛する宛先: `{"store_id", "structure_ref"}`（W5-c）。

    構造の側の台帳を **読み取り専用**（`write`・`create` を付けない）で開く。台帳が無い root、または
    その root が登録していない `store_id` は、何も作らず `UnknownStore`（型つきの「読めない」）。同じ root の 2 つのストアは同じ `structure_ref` を持ち `store_id`
    で分かれる。別の root は `structure_ref` で分かれる。
    """
    conn = _sov_struct_open(_sov_root(root))
    if conn is None:
        raise UnknownStore(store_id)
    try:
        known = bool(_sov_registry(conn, store_id))
        ref = _sov_struct_ref(conn)
    finally:
        conn.close()
    if not known:                       # a store this root never registered has no destination
        raise UnknownStore(store_id)
    return {"store_id": store_id, "structure_ref": ref}


def basis_confirmation_store_ids(root: str) -> List[str]:
    """root の registry に載っている `store_id` の、重複なしの昇順（読み取り専用。台帳が無ければ `[]`）。"""
    conn = _sov_struct_open(_sov_root(root))
    if conn is None:
        return []
    try:
        return sorted({r["store_id"] for r in _sov_registry(conn)})
    finally:
        conn.close()


@_sov_typed
def append_basis_confirmation(root: str, store_id: str, payload: Any, *,
                              now: Optional[Callable[[], datetime]] = None) -> Dict[str, Any]:
    """利用者の確認（はい／いいえ）を `decision` の事件として 1 件追記する口。

    同意（現在の consent.promote）が無ければ何も書かない（NO_CONSENT）。payload の形が違えば
    BAD_PAYLOAD で何も書かない。既存の事件は変えない・消さない（いいえ も追記）。`decision` は
    昇格の候補にならない（`promote` の数え上げでは not_a_candidate）。

    W5-c: payload に `destination`（`{"store_id", "structure_ref"}`）があれば、それが自分
    （`basis_confirmation_destination`）と等しいときだけ書く。鍵がちょうど 2 つの Mapping でなければ
    BAD_PAYLOAD、違えば CONFIRM_TARGET_MISMATCH（どちらも何も書かない）。`destination` の無い payload は
    従来どおり受ける（直接の呼び手は束縛されない）。
    """
    root = _sov_root(root)
    conn, _path = _sov_open_active(root, store_id, write=False)
    try:
        consent = _sov_consent(conn)
    finally:
        conn.close()
    if not consent["promote"]:
        return {"verdict": "NO_CONSENT", "store_id": store_id, "consent": consent, "wrote": 0}
    if (not isinstance(payload, Mapping) or payload.get("record") != "basis_confirmation"
            or payload.get("status") not in BASIS_CONFIRMATION_STATUSES
            or any(k in payload for k in _SOV_CONFIRMATION_FORBIDDEN_KEYS)):
        return {"verdict": "BAD_PAYLOAD", "store_id": store_id, "wrote": 0}
    if "destination" in payload:
        given = payload["destination"]
        if not isinstance(given, Mapping) or set(given) != {"store_id", "structure_ref"}:
            return {"verdict": "BAD_PAYLOAD", "store_id": store_id, "wrote": 0}
        expected = basis_confirmation_destination(root, store_id)
        if dict(given) != expected:
            return {"verdict": "CONFIRM_TARGET_MISMATCH", "store_id": store_id, "wrote": 0,
                    "expected": expected, "given": dict(given)}
    try:
        eid = SovereignLedger(root, store_id, now).append({"kind": "decision", "payload": dict(payload)})
    except LedgerRefusal as exc:
        return {"verdict": exc.verdict, "detail": exc.detail, "store_id": store_id, "wrote": 0}
    return {"verdict": "APPENDED", "event_id": eid, "store_id": store_id, "wrote": 1}


# -------------------------------------------------------------- cli
#: 操作ごとの「型つきの結果で終わった」verdict。同じ文字列（DETACHED など）が、ある操作では成功で
#: 別の操作では「読めない」の理由になるので、操作と組にして判断する。
_SOV_OK_VERDICTS = {
    "create": {"CREATED"}, "consent": {"CONSENT_RECORDED"}, "append": {"APPENDED"},
    "status": {"ANSWER"}, "detach": {"DETACHED", "ALREADY_DETACHED"},
    "attach": {"ATTACHED", "ALREADY_ACTIVE"}, "export": {"EXPORTED"},
    "release": {"RELEASED", "ALREADY_RELEASED"},
    "promote": {"PROMOTED", "NOTHING_TO_PROMOTE", "NO_CONSENT"}, "promotions": {"ANSWER"}}


def _sov_print(obj: Mapping[str, Any]) -> None:
    print(json.dumps(obj, ensure_ascii=False, sort_keys=True))


def memory_cli(args: Any) -> int:
    """`vera sovereign <op>` の本体。結果は stdout に 1 行（events だけ 1 事件 1 行）。"""
    op = args.sovereign_op
    parser = getattr(args, "sovereign_parser", None)
    root = args.sov_root
    sid = getattr(args, "sov_store_id", None)
    try:
        if op == "create":
            res = create(root, sid, args.sov_owner, consent_promote=bool(args.sov_consent_promote))
        elif op == "consent":
            res = set_consent(root, sid, args.sov_promote == "on")
        elif op == "append":
            try:
                payload = json.loads(args.sov_payload)
            except ValueError:
                if parser is not None:
                    parser.error("--payload must be one line of json")
                raise
            eid = open_ledger(root, sid).append({"kind": args.sov_kind, "payload": payload})
            res = {"verdict": "APPENDED", "id": eid, "store_id": sid}
        elif op == "events":
            evs = open_ledger(root, sid).events(since=args.sov_since)
            for e in evs:
                _sov_print(e)
            return 0
        elif op == "status":
            res = status(root, sid)
        elif op == "detach":
            res = detach(root, sid)
        elif op == "attach":
            if (sid is None) == (getattr(args, "sov_file", None) is None) and parser is not None:
                parser.error("attach needs exactly one of --store-id or --file")
            res = attach(root, store_id=sid, file=getattr(args, "sov_file", None))
        elif op == "export":
            res = export(root, sid, args.sov_to)
        elif op == "release":
            res = release(root, sid, args.sov_confirm)
        elif op == "promote":
            res = promote(root, sid, min_count=args.sov_min_count, min_days=args.sov_min_days)
        elif op == "promotions":
            res = promotions_answer(root, sid, include_retired=bool(args.sov_all))
        else:
            if parser is not None:
                parser.error(f"unknown sovereign operation: {op}")
            raise ValueError(op)
    except SovereignUnavailable as exc:
        res = exc.as_dict()
    except UnknownSince as exc:
        res = {"verdict": exc.verdict, "since": str(exc)}
    except LedgerRefusal as exc:
        res = {"verdict": exc.code, "detail": exc.detail}
    _sov_print(res)
    return 0 if res["verdict"] in _SOV_OK_VERDICTS.get(op, set()) else 1


if __name__ == "__main__":
    sys.exit(main())
