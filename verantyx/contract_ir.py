"""Immutable, source-bound contracts for the experimental B sovereign.

This schema carries no vote from a knowledge, math, or semantic sovereign.
Gold contracts are diagnostic inputs and are never accepted by the raw API.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
from typing import Any, Optional, Tuple

VERSION = "contract-b-v1"
PROFILES = ("python_pure_v1", "node_commonjs_sync_v1", "sqlite_select_v1", "posix_numeric_stream_v1")


def canonical(value: Any) -> str:
    if hasattr(value, "__dataclass_fields__"):
        value = asdict(value)
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def digest(value: Any) -> str:
    return hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class Span:
    start: int
    end: int
    text: str

    def valid(self, raw: str) -> bool:
        return 0 <= self.start <= self.end <= len(raw) and raw[self.start:self.end] == self.text


@dataclass(frozen=True)
class Region:
    span: Span
    role: str = "request"


@dataclass(frozen=True)
class RequestSource:
    raw: str
    regions: Tuple[Region, ...] = ()
    language: str = "auto"
    coordinate: str = "unicode_codepoint_half_open"
    normalization: str = "identity"

    @property
    def hash(self) -> str:
        return digest(self)


@dataclass(frozen=True)
class Requirement:
    id: str
    kind: str
    spans: Tuple[Span, ...]
    target: str = ""
    scope: str = "request"
    payload_json: str = "{}"
    state: str = "interpreted"
    origin: str = "raw"

    @property
    def payload(self) -> dict:
        return json.loads(self.payload_json)


@dataclass(frozen=True)
class RequirementLedger:
    source_hash: str
    requirements: Tuple[Requirement, ...]
    unknown: Tuple[Span, ...] = ()
    alternatives: Tuple[str, ...] = ()

    @property
    def hash(self) -> str:
        return digest(self)


@dataclass(frozen=True)
class ValueType:
    kind: str
    item: Optional["ValueType"] = None
    fields: Tuple[Tuple[str, "ValueType"], ...] = ()
    low: Optional[int] = None
    high: Optional[int] = None
    max_items: Optional[int] = None
    max_length: Optional[int] = None

    def field(self, name: str) -> "ValueType":
        for field, typ in self.fields:
            if field == name:
                return typ
        raise ContractError("TYPE_OR_BINDING_FAILURE", "synthesis", "unknown field: " + name)


@dataclass(frozen=True)
class InputBinding:
    name: str
    type: ValueType
    kind: str = "positional_or_keyword"
    ordinal: str = ""


@dataclass(frozen=True)
class Interface:
    name: str
    parameters: Tuple[str, ...]
    keyword_only: Tuple[str, ...] = ()
    columns: Tuple[str, ...] = ()
    ordered: bool = True
    argv: Tuple[str, ...] = ()

    def runner_dict(self) -> dict:
        return json.loads(canonical(self))


@dataclass(frozen=True)
class Goal:
    """A desired relation between named values; narrative order is irrelevant.

    ``inputs`` names input/intermediate symbols, not textual neighbours.
    Every computation is in the registered ten-family vocabulary.
    """
    id: str
    kind: str
    inputs: Tuple[str, ...]
    output: str
    config_json: str = "{}"
    requirement_ids: Tuple[str, ...] = ()

    @property
    def config(self) -> dict:
        return json.loads(self.config_json)


@dataclass(frozen=True)
class Boundary:
    trigger: str
    symbol: str
    value_json: str
    requirement_id: str

    @property
    def value(self) -> Any:
        return json.loads(self.value_json)


@dataclass(frozen=True)
class ProgramContract:
    source_hash: str
    ledger_hash: str
    profile: str
    interface: Interface
    inputs: Tuple[InputBinding, ...]
    goals: Tuple[Goal, ...]
    return_symbol: str
    return_type: ValueType
    requirement_ids: Tuple[str, ...]
    boundaries: Tuple[Boundary, ...] = ()
    origin: str = "raw"
    effect: str = "pure_input_unchanged"

    @property
    def hash(self) -> str:
        return digest(self)


@dataclass(frozen=True)
class PlanNode:
    id: str
    kind: str
    inputs: Tuple[str, ...]
    output: str
    input_types: Tuple[ValueType, ...]
    output_type: ValueType
    config_json: str
    requirement_ids: Tuple[str, ...]
    law: str
    part: str

    @property
    def config(self) -> dict:
        return json.loads(self.config_json)


@dataclass(frozen=True)
class TypedProgramPlan:
    contract_hash: str
    profile: str
    nodes: Tuple[PlanNode, ...]
    return_symbol: str
    return_type: ValueType
    discharged: Tuple[str, ...]
    boundaries: Tuple[Boundary, ...] = ()

    @property
    def hash(self) -> str:
        return digest(self)


@dataclass(frozen=True)
class Artifact:
    profile: str
    source: str
    plan_hash: str
    interface: Interface

    @property
    def hash(self) -> str:
        return hashlib.sha256(self.source.encode("utf-8")).hexdigest()


class ContractError(Exception):
    def __init__(self, code: str, stage: str, message: str, details: Any = None):
        super().__init__(message)
        self.code, self.stage, self.message, self.details = code, stage, message, details

    def to_dict(self) -> dict:
        return {"code": self.code, "stage": self.stage, "message": self.message, "details": self.details}


def meaning_envelope(source: RequestSource, ledger: RequirementLedger,
                     contract: ProgramContract) -> dict:
    """Lossless shared-boundary envelope, not an A/C schema or success claim.

    A foundation reader can supply source-bound obligations, typed symbols,
    relations and effects to several realizers. This adapter exposes exactly
    those fields without adding interpretations, votes, corpus facts, or
    generated assertions. It retains the complete original objects so an
    integration adapter cannot quietly discard a program-specific constraint.
    """
    if source.hash != ledger.source_hash or source.hash != contract.source_hash or ledger.hash != contract.ledger_hash:
        raise ContractError("TYPE_OR_BINDING_FAILURE","adapter","meaning objects have different provenance")
    return {"schema":"vera-meaning-envelope-v1","domain":"program",
            "sovereign":"contract","source":json.loads(canonical(source)),
            "obligations":json.loads(canonical(ledger)),
            "symbols":[{"id":b.name,"scope":"request","role":"input","type":json.loads(canonical(b.type))} for b in contract.inputs],
            "relations":json.loads(canonical(contract.goals)),
            "effects":{"declared":contract.effect,"boundaries":json.loads(canonical(contract.boundaries))},
            "lossless_payload":json.loads(canonical(contract)),
            "composition_scope":"registered operator closure",
            "foundation_reader_complete":False,"free_prose_generation_complete":False}
