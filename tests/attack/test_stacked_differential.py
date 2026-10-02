"""Differential checks for the staged intersection path."""

from __future__ import annotations

import random
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set

from verantyx.stacked import staged


class Store:
    def __init__(self, crosses: Dict[str, Dict[str, int]]) -> None:
        self.crosses = crosses


def _naive_reference(crosses: Dict[str, Dict[str, int]],
                     query: str) -> Optional[Dict[str, Any]]:
    """Small exact-membership model of the documented stage hand-off."""
    parts = [part.strip() for part in query.replace("->", "→").split("→")
             if part.strip()]
    if len(parts) < 2:
        return None
    terms = [part.split() for part in parts]
    if not all(terms):
        return None

    def candidates_for(stage_terms: Sequence[str]) -> Set[str]:
        return {
            core for core, facets in crosses.items()
            if all(term in facets for term in stage_terms)
        }

    def touches(candidate: str, members: Iterable[str]) -> int:
        own = crosses.get(candidate, {})
        return sum(
            1 for member in members
            if member in own or candidate in crosses.get(member, {})
        )

    first = candidates_for(terms[0])
    if not first:
        return {"verdict": "UNKNOWN_STAGE1_EMPTY", "core": None,
                "text": "", "stages": []}
    if len(first) > 40:
        return {"verdict": "UNKNOWN_STAGE1_TOO_WIDE", "core": None,
                "text": "", "remaining": len(first), "stages": []}

    survivors = first
    trail: List[Dict[str, Any]] = [
        {"stage": 1, "conditions": terms[0],
         "survivors": sorted(survivors)[:8], "remaining": len(survivors)}
    ]
    for index, stage_terms in enumerate(terms[1:], start=2):
        final = index == len(terms)
        stage_candidates = candidates_for(stage_terms)
        if not stage_candidates:
            return {"verdict": "UNKNOWN_STAGE%d_EMPTY" % index,
                    "core": None, "text": "",
                    "stages": trail + [{"stage": index,
                                        "conditions": stage_terms,
                                        "candidates": 0}]}
        linked = {core: touches(core, survivors)
                  for core in stage_candidates}
        linked = {core: count for core, count in linked.items() if count}
        if not linked:
            return {"verdict": "UNKNOWN_STAGES_DISCONNECTED", "core": None,
                    "text": "", "stages": trail + [{"stage": index,
                        "conditions": stage_terms,
                        "candidates": len(stage_candidates)}]}
        if not final:
            if len(linked) > 40:
                return {"verdict": "UNKNOWN_STAGE%d_TOO_WIDE" % index,
                        "core": None, "text": "", "remaining": len(linked),
                        "stages": trail + [{"stage": index,
                            "conditions": stage_terms,
                            "candidates": len(stage_candidates)}]}
            survivors = set(linked)
            trail.append({"stage": index, "conditions": stage_terms,
                          "survivors": sorted(survivors)[:8],
                          "remaining": len(survivors)})
            continue
        ranked = sorted(linked.items(), key=lambda item: (-item[1], item[0]))
        if len(ranked) == 1 or ranked[0][1] > ranked[1][1]:
            return {"verdict": "ANSWER_BY_STAGES", "core": ranked[0][0],
                    "links": ranked[0][1],
                    "stages": trail + [{"stage": index,
                        "conditions": stage_terms,
                        "candidates": len(stage_candidates)}]}
        top = ranked[0][1]
        tied = [core for core, count in ranked if count == top]
        return {"verdict": "UNKNOWN_UNDERDETERMINED", "core": None,
                "candidates": tied[:12], "remaining": len(tied),
                "stages": trail + [{"stage": index,
                    "conditions": stage_terms,
                    "candidates": len(stage_candidates)}]}
    return None


def _observed_projection(out: Optional[Dict[str, Any]]) -> Any:
    if out is None:
        return None
    stages = tuple(
        (step.get("stage"), tuple(step.get("conditions", ())),
         tuple(step.get("survivors", ())), step.get("remaining"),
         step.get("candidates"))
        for step in out.get("stages", ())
    )
    return (out.get("verdict"), out.get("core"), out.get("links"),
            out.get("remaining"), tuple(out.get("candidates", ())), stages)


def _reference_projection(out: Optional[Dict[str, Any]]) -> Any:
    if out is None:
        return None
    stages = tuple(
        (step.get("stage"), tuple(step.get("conditions", ())),
         tuple(step.get("survivors", ())), step.get("remaining"),
         step.get("candidates"))
        for step in out.get("stages", ())
    )
    return (out.get("verdict"), out.get("core"), out.get("links"),
            out.get("remaining"), tuple(out.get("candidates", ())), stages)


def test_staged_requires_an_explicit_chain() -> None:
    store = Store({"core": {"甲": 1}})
    assert staged(store, "甲 乙") is None
    assert staged(store, "甲 →") is None
    assert staged(store, "→ 甲") is None


def test_two_stage_strict_link_leader_answers() -> None:
    store = Store({
        "r1": {"甲": 1, "乙": 1},
        "r2": {"甲": 1, "乙": 1},
        "winner": {"丙": 1, "r1": 1, "r2": 1},
        "runner": {"丙": 1, "r1": 1},
    })
    out = staged(store, "甲 乙 → 丙")
    assert out is not None
    assert (out["verdict"], out["core"], out["links"]) == (
        "ANSWER_BY_STAGES", "winner", 2)


def test_final_link_tie_abstains() -> None:
    store = Store({
        "r1": {"甲": 1, "乙": 1},
        "r2": {"甲": 1, "乙": 1},
        "alpha": {"丙": 1, "r1": 1, "r2": 1},
        "beta": {"丙": 1, "r1": 1, "r2": 1},
    })
    out = staged(store, "甲 乙 → 丙")
    assert out is not None
    assert out["verdict"] == "UNKNOWN_UNDERDETERMINED"
    assert out["core"] is None
    assert out["candidates"] == ["alpha", "beta"]


def test_final_stage_requires_a_link_to_the_handoff() -> None:
    store = Store({
        "r1": {"甲": 1, "乙": 1},
        "final": {"丙": 1},
    })
    out = staged(store, "甲 乙 → 丙")
    assert out is not None
    assert out["verdict"] == "UNKNOWN_STAGES_DISCONNECTED"
    assert out["core"] is None


def test_empty_later_stage_is_typed() -> None:
    store = Store({"r1": {"甲": 1, "乙": 1}})
    out = staged(store, "甲 乙 → 丙")
    assert out is not None
    assert out["verdict"] == "UNKNOWN_STAGE2_EMPTY"


def test_stage_one_width_guard_stops_handoff() -> None:
    crosses = {"c%02d" % i: {"甲": 1, "乙": 1}
               for i in range(41)}
    out = staged(Store(crosses), "甲 乙 → 丙")
    assert out is not None
    assert out["verdict"] == "UNKNOWN_STAGE1_TOO_WIDE"
    assert out["remaining"] == 41


def test_empty_first_stage_is_typed() -> None:
    out = staged(Store({"r1": {"乙": 1}}), "甲 → 丙")
    assert out is not None
    assert out["verdict"] == "UNKNOWN_STAGE1_EMPTY"


def test_three_stages_hand_forward_without_electing_in_the_middle() -> None:
    store = Store({
        "r1": {"甲": 1, "乙": 1},
        "r2": {"甲": 1, "乙": 1},
        "m1": {"丙": 1, "r1": 1, "r2": 1},
        "m2": {"丙": 1, "r1": 1},
        "f1": {"丁": 1, "m1": 1, "m2": 1},
        "f2": {"丁": 1, "m1": 1},
    })
    out = staged(store, "甲 乙 → 丙 → 丁")
    assert out is not None
    assert (out["verdict"], out["core"], out["links"]) == (
        "ANSWER_BY_STAGES", "f1", 2)
    assert [s["stage"] for s in out["stages"]] == [1, 2, 3]
    assert out["stages"][1]["survivors"] == ["m1", "m2"]


def test_intermediate_width_guard_stops_handoff() -> None:
    crosses: Dict[str, Dict[str, int]] = {"r1": {"甲": 1, "乙": 1}}
    crosses.update({"m%02d" % i: {"丙": 1, "r1": 1}
                    for i in range(41)})
    out = staged(Store(crosses), "甲 乙 → 丙 → 丁")
    assert out is not None
    assert out["verdict"] == "UNKNOWN_STAGE2_TOO_WIDE"
    assert out["remaining"] == 41


def test_generated_stage_graphs_match_independent_reference() -> None:
    rng = random.Random(20261002)
    terms = ["甲", "乙", "丙", "丁", "戊"]
    for case in range(32):
        core_names = ["c%02d" % i for i in range(7)]
        crosses: Dict[str, Dict[str, int]] = {core: {} for core in core_names}
        for core in core_names:
            for term in terms:
                if rng.random() < 0.38:
                    crosses[core][term] = rng.randint(1, 4)
        for core in core_names:
            for other in core_names:
                if core != other and rng.random() < 0.14:
                    crosses[core][other] = 1
        n_stages = rng.randint(2, 4)
        stages = [rng.sample(terms, rng.randint(1, 2))
                  for _ in range(n_stages)]
        query = " → ".join(" ".join(stage_terms)
                           for stage_terms in stages)
        expected = _naive_reference(crosses, query)
        actual = staged(Store(crosses), query)
        assert _observed_projection(actual) == _reference_projection(expected), (
            "generated case %d: %s" % (case, query)
        )
