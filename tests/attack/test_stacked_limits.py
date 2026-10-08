"""Independent limit and determinism probes for the staged inference path."""

from concurrent.futures import ThreadPoolExecutor
import gc
import tracemalloc

import pytest

from verantyx import puzzle as puzzle_module
from verantyx import stacked


class _Store:
    def __init__(self, crosses):
        self.crosses = crosses


def _install_puzzle(monkeypatch, stage_candidates):
    """Supply fixed stage candidates while exercising stacked.staged itself."""

    class _ScriptedPuzzle:
        def __init__(self, store):
            self.store = store
            self.candidates = []
            self._verdict = "UNKNOWN_NO_EVIDENCE"

        def narrow(self, *terms):
            self.candidates = list(stage_candidates["".join(terms)])
            self._verdict = (
                "ANSWER" if len(self.candidates) == 1
                else "UNKNOWN_UNDERDETERMINED"
            )
            return self

        def answer(self):
            return {
                "verdict": self._verdict,
                "remaining": len(self.candidates),
                "candidates": list(self.candidates),
            }

    monkeypatch.setattr(puzzle_module, "Puzzle", _ScriptedPuzzle)


def _chain(monkeypatch, stage_candidates, crosses, query="殺人罪 → 時効 → 停止"):
    _install_puzzle(monkeypatch, stage_candidates)
    return stacked.staged(_Store(crosses), query)


def test_arrowless_huge_or_empty_query_returns_none():
    assert stacked.staged(_Store({}), "x" * 250_000) is None
    assert stacked.staged(_Store({}), " → → ") is None


def test_stage_one_width_guard_abstains_above_40_and_accepts_40(monkeypatch):
    within = [f"候補{i:02d}" for i in range(40)]
    store_crosses = {"終点": {within[0]: 1}}
    out = _chain(
        monkeypatch,
        {"殺人罪": within, "時効": ["終点"], "停止": ["終点"]},
        store_crosses,
        query="殺人罪 → 停止",
    )
    assert out["verdict"] == "ANSWER_BY_STAGES"
    assert out["core"] == "終点"
    assert out["links"] == 1

    beyond = within + ["候補40"]
    out = _chain(
        monkeypatch,
        {"殺人罪": beyond, "時効": ["終点"], "停止": ["終点"]},
        store_crosses,
        query="殺人罪 → 停止",
    )
    assert out["verdict"] == "UNKNOWN_STAGE1_TOO_WIDE"
    assert out["remaining"] == 41
    assert out["text"] == ""


def test_intermediate_stage_hands_all_linked_candidates_forward(monkeypatch):
    # The middle stage retains both nodes. The last stage distinguishes them
    # only if both are handed forward.
    out = _chain(
        monkeypatch,
        {"殺人罪": ["s1", "s2"], "時効": ["m1", "m2"],
         "停止": ["z1", "z2"]},
        {
            "m1": {"s1": 1, "s2": 1},
            "m2": {"s1": 1},
            "z1": {"m1": 1, "m2": 1},
            "z2": {"m1": 1},
        },
    )
    assert out["verdict"] == "ANSWER_BY_STAGES"
    assert out["core"] == "z1"
    assert out["links"] == 2
    assert out["stages"][1]["survivors"] == ["m1", "m2"]


def test_final_ties_abstain_and_are_candidate_order_independent(monkeypatch):
    crosses = {
        "left": {"seed": 1, "left": 1},
        "right": {"seed": 1, "right": 1},
    }
    first = _chain(
        monkeypatch,
        {"殺人罪": ["seed"], "時効": ["right", "left"],
         "停止": ["right", "left"]},
        crosses,
    )
    second = _chain(
        monkeypatch,
        {"殺人罪": ["seed"], "時効": ["left", "right"],
         "停止": ["left", "right"]},
        crosses,
    )
    assert first == second
    assert first["verdict"] == "UNKNOWN_UNDERDETERMINED"
    assert first["candidates"] == ["left", "right"]
    assert first["text"] == ""


def test_repeated_staged_calls_are_idempotent(monkeypatch):
    stage_candidates = {
        "殺人罪": ["s1", "s2"], "時効": ["m1", "m2"], "停止": ["z1", "z2"]
    }
    crosses = {
        "m1": {"s1": 1, "s2": 1},
        "m2": {"s1": 1},
        "z1": {"m1": 1, "m2": 1},
        "z2": {"m1": 1},
    }
    _install_puzzle(monkeypatch, stage_candidates)
    store = _Store(crosses)
    first = stacked.staged(store, "殺人罪 → 時効 → 停止")
    second = stacked.staged(store, "殺人罪 → 時効 → 停止")
    assert first == second
    assert store.crosses == crosses


def test_two_concurrent_readers_return_the_same_staged_result(monkeypatch):
    stage_candidates = {
        "殺人罪": ["s1", "s2"], "時効": ["m1", "m2"], "停止": ["z1", "z2"]
    }
    crosses = {
        "m1": {"s1": 1, "s2": 1},
        "m2": {"s1": 1},
        "z1": {"m1": 1, "m2": 1},
        "z2": {"m1": 1},
    }
    _install_puzzle(monkeypatch, stage_candidates)
    store = _Store(crosses)
    query = "殺人罪 → 時効 → 停止"
    with ThreadPoolExecutor(max_workers=2) as pool:
        left = pool.submit(stacked.staged, store, query)
        right = pool.submit(stacked.staged, store, query)
        assert left.result(timeout=5) == right.result(timeout=5)


def test_96_stage_chain_completes_with_typed_answer(monkeypatch):
    stage_count = 96
    _install_puzzle(monkeypatch, {"停止": ["node"]})
    store = _Store({"node": {"node": 1}})
    query = " → ".join(["停止"] * stage_count)
    out = stacked.staged(store, query)
    assert out["verdict"] == "ANSWER_BY_STAGES"
    assert out["core"] == "node"
    assert len(out["stages"]) == stage_count


def test_repeated_calls_do_not_retain_unbounded_stage_results(monkeypatch):
    _install_puzzle(
        monkeypatch,
        {"殺人罪": ["s1", "s2"], "時効": ["m1", "m2"], "停止": ["z1", "z2"]},
    )
    store = _Store({
        "m1": {"s1": 1, "s2": 1},
        "m2": {"s1": 1},
        "z1": {"m1": 1, "m2": 1},
        "z2": {"m1": 1},
    })
    query = "殺人罪 → 時効 → 停止"
    stacked.staged(store, query)  # warm imports and parser caches
    gc.collect()
    tracemalloc.start()
    before = tracemalloc.get_traced_memory()[0]
    for _ in range(200):
        result = stacked.staged(store, query)
    del result
    gc.collect()
    retained = tracemalloc.get_traced_memory()[0] - before
    tracemalloc.stop()
    assert retained < 128 * 1024


@pytest.mark.xfail(
    strict=False,
    reason="DEFECT: empty arrow stages are silently discarded and the shortened chain can answer",
)
def test_empty_arrow_stage_is_not_silently_accepted(monkeypatch):
    out = _chain(
        monkeypatch,
        {"殺人罪": ["seed"], "停止": ["winner"]},
        {"winner": {"seed": 1}},
        query="殺人罪 → → 停止",
    )
    # An explicit chain with a missing stage should be refused, not interpreted
    # as a different, shorter chain.
    assert out is None or str(out.get("verdict", "")).startswith("UNKNOWN")
