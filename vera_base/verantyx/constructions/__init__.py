"""Registry contract for independently licensed semantic constructions.

Construction modules register one immutable rule at import time.  The reader
discovers modules in this package lazily; the verifier asks only for a rule's
independent licensor and never calls its reader.
"""
from __future__ import annotations

import importlib
import os
import pkgutil
import re
from dataclasses import dataclass
from threading import RLock
from typing import Any, Callable

from ..semantic_ir import Clause, Span


@dataclass(frozen=True)
class TokenSpan:
    token: Any
    start: int
    end: int


@dataclass(frozen=True)
class ConstructionBudget:
    """Deterministic input limits offered to pure construction readers."""
    max_tokens: int = 256
    max_clauses: int = 128
    max_steps: int = 4096


@dataclass(frozen=True)
class ConstructionContext:
    sentence_text: str
    sentence_span: Span
    tokens: tuple[TokenSpan, ...]
    document_id: str
    clauses: tuple[Clause, ...]
    budget: ConstructionBudget = ConstructionBudget()


@dataclass(frozen=True)
class TypedNote:
    kind: str
    span: Span | None
    detail: str


@dataclass(frozen=True)
class Reading:
    clauses: tuple[Clause, ...]
    consumed_spans: tuple[Span, ...]
    notes: tuple[TypedNote, ...] = ()


@dataclass(frozen=True)
class Construction:
    name: str
    priority: int
    reads: Callable[[ConstructionContext], Reading | None]
    licenses: Callable[[Clause, str], bool]
    refines: tuple[str, ...] = ()


_NAME = re.compile(r"[a-z][a-z0-9_]*\Z")
_RESERVED_RULES = frozenset(("record", "frame", "copula", "identity", "measure"))
_MAX_CONSTRUCTIONS = 64
_registry: dict[str, Construction] = {}
_imported: set[str] = set()
_lock = RLock()


def register(construction: Construction) -> Construction:
    """Register one rule; duplicate names are rejected unless identical."""
    if not isinstance(construction, Construction):
        raise TypeError("register expects a Construction")
    if (not isinstance(construction.name, str) or not _NAME.fullmatch(construction.name)
            or construction.name in _RESERVED_RULES
            or type(construction.priority) is not int or construction.priority < 0
            or not callable(construction.reads) or not callable(construction.licenses)
            or not isinstance(construction.refines, tuple)
            or any(not isinstance(name, str) or not _NAME.fullmatch(name)
                   for name in construction.refines)):
        raise ValueError("invalid construction contract")
    with _lock:
        prior = _registry.get(construction.name)
        if prior is construction:
            return construction
        if prior is not None:
            raise ValueError("duplicate construction: " + construction.name)
        if len(_registry) >= _MAX_CONSTRUCTIONS:
            raise ValueError("construction registry limit")
        _registry[construction.name] = construction
    return construction


def discover() -> tuple[Construction, ...]:
    """Import every module in this package and return all registered rules."""
    with _lock:
        modules = sorted(info.name for info in pkgutil.iter_modules(__path__, __name__ + "."))
        for module in modules:
            if module not in _imported:
                importlib.import_module(module)
                _imported.add(module)
        return tuple(sorted(_registry.values(), key=lambda c: (-c.priority, c.name)))


def enabled() -> tuple[Construction, ...]:
    """Return discovered constructions except names in VERA_CONSTRUCTIONS_OFF."""
    disabled = {part.strip() for part in os.environ.get("VERA_CONSTRUCTIONS_OFF", "").split(",")
                if part.strip()}
    return tuple(c for c in discover() if c.name not in disabled)


def licensor(name: str) -> Construction | None:
    """Find an enabled construction by its clause rule name."""
    return next((c for c in enabled() if c.name == name), None)


__all__ = ("Construction", "ConstructionBudget", "ConstructionContext", "Reading",
           "TokenSpan", "TypedNote", "discover", "enabled", "licensor", "register")
