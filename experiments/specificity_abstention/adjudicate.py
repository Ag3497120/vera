"""Frozen, experimental facet-coverage refusal; no ranking or store mutation."""
from dataclasses import replace

from verantyx.consensus import query_content

THRESHOLD_NUMERATOR = 1
THRESHOLD_DENOMINATOR = 20


def adjudicate(store, query, result):
    """Return a separate result and audit evidence, preserving the search trace."""
    audit = {"forward_verdict": result.verdict, "forward_core": result.core,
             "threshold_numerator": THRESHOLD_NUMERATOR,
             "threshold_denominator": THRESHOLD_DENOMINATOR,
             "evaluated": False, "refused": False}
    if result.verdict != "ANSWER":
        return result, audit
    qset, _ = query_content(query)
    facets = store.crosses.get(result.core) or {}
    covered = sorted(qset.intersection(facets))
    denominator = max(1, len(facets))
    insufficient = (THRESHOLD_DENOMINATOR * len(covered)
                    < THRESHOLD_NUMERATOR * denominator)
    audit.update(evaluated=True, covered=covered, facet_count=len(facets),
                 numerator=len(covered), denominator=denominator,
                 specificity=len(covered) / denominator, refused=insufficient)
    if insufficient:
        return replace(result, verdict="UNKNOWN_INSUFFICIENT_EVIDENCE",
                       core=None, text="", tokens=[]), audit
    return result, audit
