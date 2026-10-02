"""A non-voting agreement annotation for verified semantic answers.

The semantic path currently exposes one parsed view to its producer and
checker. Those stages share evidence and are not independent comparators; the
route tree also only indexes that same view. Until an audited, lineage-distinct
structure can be queried here, there is no honest numeric band to report.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Optional, Tuple


@dataclass(frozen=True)
class Band:
    """Agreement counts and inspectable outcomes from independent structures."""

    agree: int
    of: int
    matching: Tuple[str, ...] = ()
    different: Tuple[str, ...] = ()
    abstentions: Tuple[Tuple[str, str], ...] = ()


def band(view: Any, request: Any, result: Mapping[str, Any]) -> Optional[Band]:
    """Return an independent-structure annotation, or ``None`` if unavailable.

    ``view`` and ``result`` describe the primary semantic path. The producer
    and checker both use that path, and the view carries no audited lineage
    registry for another typed structure. Counting either stage, rerunning the
    same reader, or counting route-tree leaves would therefore overstate
    independence. No candidate comparator is currently wired, so every call
    abstains. This function is pure: it never edits the result or its verdict.
    """
    return None
