"""Count-backed resolution for native ambiguous case roles.

The table is built from licensed training clauses.  This construction may
rename an already source-bound ambiguous role; it never adds a role span or a
fact.  Both the reader and checker require a unique role with a clear count
majority.
"""
from __future__ import annotations

import hashlib
import json
from contextlib import contextmanager
from dataclasses import replace
from pathlib import Path
from typing import Iterator, Mapping

from ..semantic_ir import Role
from . import Construction, Reading, register

NAME = "case_frames"
MIN_COUNT = 8
CLEAR_MAJORITY = 0.80
_PARTICLES = frozenset(("に", "で", "と"))
_COMPOUNDS = ("における", "において", "について", "に対して", "によって", "による",
              "により", "として", "と共に", "ともに", "では")
_ROLE_PARTICLES = {
    "に": frozenset(("agent", "recipient", "goal", "location", "time", "purpose")),
    "で": frozenset(("place", "means", "time", "location")),
    "と": frozenset(("companion", "quotation")),
}
_DATA = Path(__file__).resolve().parents[1] / "data" / "case_frames.json"


def _clean_counts(raw: object) -> dict[str, dict[str, dict[str, int]]]:
    if not isinstance(raw, dict):
        return {}
    frames: dict[str, dict[str, dict[str, int]]] = {}
    for predicate, by_particle in raw.items():
        if not isinstance(predicate, str) or not predicate or not isinstance(by_particle, dict):
            continue
        valid_particles: dict[str, dict[str, int]] = {}
        for particle, by_role in by_particle.items():
            if particle not in _PARTICLES or not isinstance(by_role, dict):
                continue
            roles = {
                role: count for role, count in by_role.items()
                if role in _ROLE_PARTICLES[particle]
                and type(count) is int and count > 0
            }
            if roles:
                valid_particles[particle] = roles
        if valid_particles:
            frames[predicate] = valid_particles
    return frames


def _read_data() -> tuple[dict[str, dict[str, dict[str, int]]], int, float]:
    try:
        value = json.loads(_DATA.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return {}, MIN_COUNT, CLEAR_MAJORITY
    if not isinstance(value, dict):
        return {}, MIN_COUNT, CLEAR_MAJORITY
    minimum = value.get("min_count", MIN_COUNT)
    majority = value.get("clear_majority", CLEAR_MAJORITY)
    if type(minimum) is not int or minimum < 1:
        minimum = MIN_COUNT
    if type(majority) not in (float, int) or not 0.5 < float(majority) <= 1.0:
        majority = CLEAR_MAJORITY
    return _clean_counts(value.get("frames")), minimum, float(majority)


_COUNTS, _MIN_COUNT, _CLEAR_MAJORITY = _read_data()


def load_counts(data: Mapping[str, object] | None = None) -> dict[str, dict[str, dict[str, int]]]:
    """Return a validated, detached count table."""
    if data is None:
        return _clean_counts(_COUNTS)
    return _clean_counts(data)


@contextmanager
def using_counts(counts: Mapping[str, object], *, min_count: int = MIN_COUNT,
                 clear_majority: float = CLEAR_MAJORITY) -> Iterator[None]:
    """Temporarily install a deterministic table for an offline demonstration."""
    global _COUNTS, _MIN_COUNT, _CLEAR_MAJORITY
    old = _COUNTS, _MIN_COUNT, _CLEAR_MAJORITY
    if type(min_count) is not int or min_count < 1:
        raise ValueError("min_count must be a positive integer")
    if type(clear_majority) not in (float, int) or not 0.5 < float(clear_majority) <= 1.0:
        raise ValueError("clear_majority must be greater than one half and at most one")
    _COUNTS = _clean_counts(dict(counts))
    _MIN_COUNT = min_count
    _CLEAR_MAJORITY = float(clear_majority)
    try:
        yield
    finally:
        _COUNTS, _MIN_COUNT, _CLEAR_MAJORITY = old


def _choice(predicate: str, particle: str,
            counts: Mapping[str, Mapping[str, Mapping[str, int]]],
            min_count: int, clear_majority: float) -> str | None:
    roles = counts.get(predicate, {}).get(particle, {})
    total = sum(roles.values())
    if total < min_count or not roles:
        return None
    ranked = sorted(roles.items(), key=lambda item: (-item[1], item[0]))
    if len(ranked) > 1 and ranked[0][1] == ranked[1][1]:
        return None
    if ranked[0][1] / total < clear_majority:
        return None
    return ranked[0][0]


def _local_case_particle(ctx, start: int, end: int, particle: str) -> bool:
    left = start - ctx.sentence_span.start
    right = end - ctx.sentence_span.start
    if left < 0 or right <= left or right > len(ctx.sentence_text):
        return False
    if ctx.sentence_text[left:right] == "":
        return False
    return any(token.start == right and token.token.surface == particle
               and token.token.feature.pos1 == "助詞"
               and token.token.feature.pos2 == "格助詞" for token in ctx.tokens)


def reads(ctx):
    if len(ctx.tokens) > ctx.budget.max_tokens or len(ctx.clauses) > ctx.budget.max_clauses:
        return None
    clauses = []
    steps = 0
    for clause in ctx.clauses:
        if clause.rule != "frame" or clause.span.source != ctx.sentence_span.source:
            continue
        if not (ctx.sentence_span.start <= clause.span.start < clause.span.end
                <= ctx.sentence_span.end):
            continue
        new_roles = []
        resolved_reasons = set()
        changed = False
        for role in clause.roles:
            steps += 1
            if (role.name != "ambiguous" or not isinstance(role.rule, str)
                    or not role.rule.startswith("case:")):
                new_roles.append(role)
                continue
            particle = role.rule.split(":", 2)[1]
            reason = "ambiguous case role: " + particle
            chosen = _choice(clause.predicate, particle, _COUNTS,
                             _MIN_COUNT, _CLEAR_MAJORITY)
            if (particle not in _PARTICLES or chosen is None
                    or reason not in clause.unsupported
                    or role.span.source != clause.span.source
                    or not _local_case_particle(ctx, role.span.start, role.span.end, particle)):
                new_roles.append(role)
                continue
            new_roles.append(Role(chosen, role.term, role.span, NAME))
            resolved_reasons.add(reason)
            changed = True
        if steps > ctx.budget.max_steps:
            return None
        if not changed or len({role.name for role in new_roles}) != len(new_roles):
            continue
        unsupported = tuple(reason for reason in clause.unsupported
                            if reason not in resolved_reasons)
        signature = ";".join(
            f"{role.name}:{role.span.start}:{role.span.end}" for role in new_roles)
        ident = hashlib.sha256(f"{clause.id}:{NAME}:{signature}".encode("utf-8")).hexdigest()[:24]
        clauses.append(replace(clause, id=ident, rule=NAME, roles=tuple(new_roles),
                               unsupported=unsupported))
    if not clauses:
        return None
    return Reading(tuple(clauses), (ctx.sentence_span,))


def _licensed_vote(predicate: str, particle: str) -> str | None:
    """Independent count check used only by the source licensor."""
    try:
        roles = _COUNTS[predicate][particle]
    except (KeyError, TypeError):
        return None
    total = 0
    winner = None
    high = 0
    second = 0
    for role, count in roles.items():
        if not isinstance(role, str) or type(count) is not int or count <= 0:
            return None
        total += count
        if count > high:
            second, winner, high = high, role, count
        elif count > second:
            second = count
    if total < _MIN_COUNT or high <= second:
        return None
    if high / total < _CLEAR_MAJORITY:
        return None
    return winner


def _source_particle(source: str, offset: int, particle: str) -> bool:
    """Retag the original source and independently verify one simple case token."""
    if offset < 0 or offset >= len(source):
        return False
    if any(source.startswith(compound, offset) for compound in _COMPOUNDS):
        return False
    from ..semantic_reader import _tokens
    return any(start == offset and word.surface == particle
               and word.feature.pos1 == "助詞"
               and word.feature.pos2 == "格助詞"
               for word, start, _ in _tokens(source))


def licenses(clause, source: str) -> bool:
    if clause.rule != NAME or not isinstance(source, str) or not clause.predicate:
        return False
    if (clause.span.start < 0 or clause.span.start >= clause.span.end
            or clause.span.end > len(source)
            or source[clause.span.start:clause.span.end] != clause.span.text):
        return False
    if (clause.predicate_span.source != clause.span.source
            or not (clause.span.start <= clause.predicate_span.start
                    < clause.predicate_span.end <= clause.span.end)
            or source[clause.predicate_span.start:clause.predicate_span.end]
            != clause.predicate_span.text):
        return False
    from ..frames import _predicates
    from ..semantic_reader import _tokens
    positioned = _tokens(source[clause.span.start:clause.span.end])
    local_predicate = clause.predicate_span.start - clause.span.start
    predicate_indices = [index for index, (_, start, _) in enumerate(positioned)
                         if start == local_predicate]
    if len(predicate_indices) != 1:
        return False
    words = [word for word, _, _ in positioned]
    predicate_index = predicate_indices[0]
    if not any(index == predicate_index and predicate == clause.predicate
               for index, predicate in _predicates(words)):
        return False

    resolved = []
    for role in clause.roles:
        if role.rule != NAME:
            if role.name == "ambiguous" and isinstance(role.rule, str) and role.rule.startswith("case:"):
                particle = role.rule.split(":", 2)[1]
                if "ambiguous case role: " + particle not in clause.unsupported:
                    return False
            continue
        if (role.name == "ambiguous" or role.span.source != clause.span.source
                or role.span.start < clause.span.start or role.span.end > clause.span.end
                or role.span.start >= role.span.end
                or role.span.end > clause.predicate_span.start
                or str(role.term) != role.span.text
                or source[role.span.start:role.span.end] != role.span.text):
            return False
        particle = next((possible for possible in _PARTICLES
                         if source[role.span.end:role.span.end + len(possible)] == possible), None)
        if (particle is None or role.name not in _ROLE_PARTICLES[particle]
                or not _source_particle(source, role.span.end, particle)
                or _licensed_vote(clause.predicate, particle) != role.name):
            return False
        reason = "ambiguous case role: " + particle
        if reason in clause.unsupported:
            return False
        resolved.append((role, particle))
    if not resolved:
        return False
    if len({role.name for role in clause.roles}) != len(clause.roles):
        return False
    return True


register(Construction(name=NAME, priority=30, reads=reads, licenses=licenses))
