"""Adversarial regression probes for the W3-c observation promises.

These tests intentionally assert the registered behavior and are expected to
fail against the current implementation when a counterexample is reproduced.
"""
import json
import os
import subprocess
import sys
from pathlib import Path

from verantyx import observe as O
from verantyx.event_cross import PlaceResult


TREE = Path(__file__).resolve().parents[2]
PYTHON = sys.executable
GIVE = "太郎は花子に本をあげた。"


def _cli(*args):
    env = {
        "HOME": os.environ.get("HOME", ""),
        "PATH": "/usr/bin:/bin",
        "PYTHONPATH": str(TREE),
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONHASHSEED": "0",
    }
    return subprocess.run(
        [PYTHON, "-m", "verantyx.cli", "observe", *map(str, args)],
        cwd=str(TREE), env=env, capture_output=True, text=True, timeout=180,
    )


def test_neighbor_file_order_does_not_change_the_output(tmp_path):
    lemmas = {
        word: {"state": "DECIDED", "origin": "direct", "types": ["PERSON"]}
        for word in ("太郎", "花子", "次郎")
    }
    outputs = []
    for name, neighbors in (("a", ["花子", "次郎"]), ("b", ["次郎", "花子"])):
        path = tmp_path / f"{name}.json"
        path.write_text(json.dumps({"lemmas": lemmas, "neighbors": {"太郎": neighbors}}, ensure_ascii=False), encoding="utf-8")
        result = _cli("--anchor-text", GIVE, "--direction", "FACE_SWAP:agent", "--placement", path, "--no-index")
        assert result.returncode == 0, result.stderr
        outputs.append(result.stdout)

    first, second = map(json.loads, outputs)
    same_observation = (
        first["focus"] == second["focus"]
        and [[e["cell_key"] for e in group["elements"]] for group in first["ranks"]]
        == [[e["cell_key"] for e in group["elements"]] for group in second["ranks"]]
    )
    assert outputs[0] == outputs[1], (
        "same neighbor set in different list order changed JSON bytes; "
        f"focus/ranks equal={same_observation}; "
        f"placement ids=({first['structure']['placement']!r}, {second['structure']['placement']!r}); "
        f"neighbor ids=({first['structure']['neighbors']!r}, {second['structure']['neighbors']!r})"
    )


class _People:
    id = "attack-people/1"

    def lookup(self, lemma):
        return PlaceResult("DECIDED", "direct", None, ("PERSON",), {"attack": True})

    def neighbors(self, lemma):
        return O.NeighborResult("NO_NEIGHBORS", (), {"attack": True})


def _clause(predicate, agent):
    return {
        "predicate": predicate,
        "roles": {"agent": agent},
        "polarity": "+",
        "tense": "past",
        "modality": None,
        "voice": "active",
    }


def _reading(*clauses):
    return {
        "schema": "verantyx.semantic_read/1",
        "lang": "ja",
        "readable": True,
        "clauses": list(clauses),
        "relations": [{"type": "cause", "from": 0, "to": 1}],
        "abstain": None,
        "unsupported": [],
        "clause_meta": [{"rule": "frame", "span": [i, i + 1]} for i in range(len(clauses))],
    }


def _edge_item(identifier, left, right):
    return {"id": identifier, "reading": _reading(left, right)}


def test_all_paths_are_carried_through_a_merged_cell():
    people = _People()
    anchor_reading = _reading(_clause("行く", "太郎"), _clause("買う", "花子"))
    items = [
        _edge_item("structure-ab", _clause("行く", "太郎"), _clause("買う", "花子")),
        _edge_item("structure-bc-1", _clause("買う", "花子"), _clause("話す", "次郎")),
        _edge_item("structure-bc-2", _clause("買う", "花子"), _clause("話す", "次郎")),
        _edge_item("structure-cd", _clause("話す", "次郎"), _clause("笑う", "三郎")),
    ]
    structure = O.Structure.from_injected(items, people, people)
    viewpoint = O.Viewpoint(
        O.AnchorText("seed", "seed", None, 0, anchor_reading),
        (O.Edge("cause"), O.Edge("cause"), O.Edge("cause")),
    )
    observation = O.observe(viewpoint, structure)
    by_predicate = {
        element.cell.cross.center["predicate"]: element.to_dict()
        for element in observation.elements()
    }

    # A->B has two witnesses (anchor reading and structure-ab); B->C has two
    # readings, so the same C and its D descendant each have four valid paths.
    got_c = [
        [move["reading"] for move in coord["moves"]]
        for coord in by_predicate["話す"]["coords"]
    ]
    got_d = [
        [move["reading"] for move in coord["moves"]]
        for coord in by_predicate["笑う"]["coords"]
    ]
    replay_check = O.reobserve(by_predicate["笑う"], viewpoint, structure)
    assert len(got_c) == 4 and len(got_d) == 4, (
        "converged paths were not propagated to later levels; "
        f"C paths={got_c!r}; D paths={got_d!r}; "
        f"the incomplete coordinate still reports {replay_check!r}"
    )


def test_malformed_ledger_is_rejected_without_appending(tmp_path):
    ledger = tmp_path / "broken.jsonl"
    ledger.write_text(
        json.dumps({"seq": 1, "ts": "t", "kind": "utterance", "payload": {"text": [], "anchor": "seed"}}) + "\n",
        encoding="utf-8",
    )
    before = ledger.read_bytes()
    result = _cli("--anchor-text", GIVE, "--no-index", "--ledger", ledger)
    after = ledger.read_bytes()
    assert result.returncode == 3 and after == before, (
        "malformed utterance payload was accepted and the broken ledger was modified; "
        f"returncode={result.returncode}, appended_lines={len(after.splitlines()) - len(before.splitlines())}, "
        f"stdout_is_json={result.stdout.startswith('{')}, stderr={result.stderr!r}"
    )
