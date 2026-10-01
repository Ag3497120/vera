"""Lossless, non-learning storage experiment for the shared content contract.

This does not replace FamilyLibrary, conduct_tree, corpus storage or any live
ingest. It packs an immutable ledger and verifies byte/hash restoration.
Routing weights are counts of *declared* structural signatures, partitioned
by world; they cannot establish meaning, remove a denial or vote on facts.
General corpus compression, indexing and a semantic/code schema adapter are
integration work outside this C patch. A compression ratio proves no ability.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import asdict
import base64
import json
import zlib

from .content_ir import Atom, Budget, ContentError, Ledger, Obligation, Rule, Source, Span, State, digest
from .events import ACT_ROLE, Event, ROLE_BY_PARTICLE

MAX_PACKED = 65536
MAX_RESTORED = 524288
CODEC = "vera.content.ledger.zlib.v1"


def structural_view(ledger: Ledger) -> dict:
    """Existing Event roles + explicit world/provenance, never an ingest."""
    events, weights = [], Counter()
    for obligation in ledger.obligations:
        atom = obligation.atom
        if atom is None or atom.kind != "event":
            continue
        roles = {ACT_ROLE: atom.predicate}
        for case, name in (("が", atom.agent), ("を", atom.patient), ("に", atom.recipient)):
            if name:
                roles[ROLE_BY_PARTICLE[case]] = name
        event = Event("content:" + obligation.id, roles)
        events.append({"event": asdict(event), "world": atom.world,
                       "entity_ids": {name: digest((atom.world, name)) for name in atom.names()},
                       "polarity": "negative" if atom.negated else "positive",
                       "tense": atom.tense, "condition": [asdict(a) for a in atom.condition],
                       "obligation": obligation.id, "obligation_kind": obligation.kind,
                       "assertion_role": "constraint", "source": asdict(obligation.span)})
        signature = (atom.world, atom.predicate, atom.negated,
                     bool(atom.agent), bool(atom.patient), bool(atom.recipient), obligation.kind)
        weights[signature] += 1
    return {"events": events,
            "structure_parameters": [{"signature": key, "count": value} for key, value in sorted(weights.items())],
            "weight_role": "routing_only", "neural_training": False,
            "independent_sources": [asdict(s) for s in (ledger.brief,) + ledger.materials],
            "added_facts": 0, "store_writes": 0}


def pack_ledger(ledger: Ledger) -> dict:
    raw = json.dumps(asdict(ledger), ensure_ascii=False, sort_keys=True,
                     separators=(",", ":")).encode()
    if len(raw) > MAX_RESTORED:
        raise ContentError("UNKNOWN_CONTENT_BUDGET", "ledger serialization exceeds codec bound")
    packed = zlib.compress(raw, level=6)
    if len(packed) > MAX_PACKED:
        raise ContentError("UNKNOWN_CONTENT_BUDGET", "compressed ledger exceeds codec bound")
    return {"codec": CODEC, "ledger_hash": ledger.hash,
            "payload": base64.b64encode(packed).decode("ascii"),
            "raw_bytes": len(raw), "packed_bytes": len(packed),
            "byte_ratio": len(packed) / max(1, len(raw)),
            "retains": ["original_sources", "spans", "roles", "worlds", "conditions",
                        "polarity", "rules", "obligations", "unread", "permissions"],
            "semantic_verified": False}


def _atom(value: dict, depth: int = 0) -> Atom:
    if depth > 2:
        raise ContentError("UNKNOWN_CONTENT_BUDGET", "compressed atom nesting exceeds bound")
    data = dict(value)
    data["condition"] = tuple(_atom(a, depth + 1) for a in data.get("condition", ()))
    return Atom(**data)


def unpack_ledger(container: dict) -> Ledger:
    """Restore identical meaning contract; this is not a creation/QA gate."""
    try:
        if not isinstance(container, dict):
            raise ValueError("compressed container must be a mapping")
        if container.get("codec") != CODEC or not isinstance(container.get("payload"), str):
            raise ValueError("codec version or payload type")
        if len(container["payload"]) > ((MAX_PACKED + 2) // 3) * 4:
            raise ContentError("UNKNOWN_CONTENT_BUDGET", "encoded ledger exceeds codec bound")
        packed = base64.b64decode(container["payload"], validate=True)
        if len(packed) > MAX_PACKED:
            raise ContentError("UNKNOWN_CONTENT_BUDGET", "packed ledger exceeds codec bound")
        decoder = zlib.decompressobj()
        raw = decoder.decompress(packed, MAX_RESTORED + 1)
        if len(raw) > MAX_RESTORED or decoder.unconsumed_tail:
            raise ContentError("UNKNOWN_CONTENT_BUDGET", "ledger expansion exceeds codec bound")
        if not decoder.eof or decoder.unused_data:
            raise ValueError("truncated or trailing compressed data")
        data = json.loads(raw)
        obligations = []
        for encoded in data["obligations"]:
            item = dict(encoded)
            item["span"] = Span(**item["span"])
            item["atom"] = _atom(item["atom"]) if item["atom"] is not None else None
            item["state"] = State(**item["state"]) if item["state"] is not None else None
            item["relation"] = tuple(item["relation"])
            obligations.append(Obligation(**item))
        rules = tuple(Rule(r["id"], _atom(r["action"]), tuple(State(**s) for s in r["requires"]),
                           tuple(State(**s) for s in r["effects"]), Span(**r["source"]),
                           tuple(State(**s) for s in r["exceptions"])) for r in data["rules"])
        ledger = Ledger(Source(**data["brief"]), tuple(Source(**s) for s in data["materials"]),
                        tuple(obligations), rules, tuple(Span(**s) for s in data["unread"]),
                        data["mode"], tuple(data["choice"]))
        if ledger.hash != container.get("ledger_hash"):
            raise ValueError("restored ledger hash mismatch")
        if len(raw) != container.get("raw_bytes") or len(packed) != container.get("packed_bytes"):
            raise ValueError("byte-count mismatch")
        budget = Budget()
        budget.size("brief_chars", len(ledger.brief.text))
        budget.size("material_chars", sum(len(s.text) for s in ledger.materials))
        budget.size("candidates", len(ledger.obligations) + len(ledger.rules) + len(ledger.materials))
        return ledger
    except ContentError:
        raise
    except (ValueError, KeyError, TypeError, zlib.error, UnicodeError) as error:
        raise ContentError("CONTENT_CONSTRAINT_VIOLATION", "compressed contract failed restoration", detail=str(error)) from error
