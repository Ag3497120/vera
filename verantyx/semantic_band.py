"""A non-voting agreement annotation for verified semantic answers.

The semantic path currently exposes one parsed view to its producer and
checker. Those stages share evidence, and the route tree only indexes that
same view. No audited, lineage-distinct structure is available here, so
``band`` returns the typed ``NO_INDEPENDENT_VIEW`` status instead of a
numeric agreement count. This annotation never changes a semantic verdict.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, Mapping


@dataclass(frozen=True)
class Band:
    """A typed band outcome; unavailable outcomes contain no numeric vote."""

    status: Literal["NO_INDEPENDENT_VIEW"]
    reason: str


def band(view: Any, request: Any, result: Mapping[str, Any]) -> Band:
    """Report that no independent typed view exists for this result.

    Call only for a verified semantic ``ANSWER``. The primary view, producer,
    checker, and route index do not constitute independent structures.
    Without a lineage-audited comparator there is no honest denominator or
    agreement count. Inputs are inspected only by reference and ``result`` is
    never changed.
    """
    return Band(
        "NO_INDEPENDENT_VIEW",
        "no audited lineage-distinct typed comparator is wired",
    )
