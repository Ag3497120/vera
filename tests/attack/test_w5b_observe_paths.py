"""W5-b / W3-c: every path of a merged cell is carried on, reobserve asks for all of them, the placement id is the content, a
broken ledger is refused before anything is written.

The structures here are not the one of the attack file (tests/attack/test_attack_w3c_observe.py): other words, other shapes. The number
of coordinates of every element was counted by hand from the structure (comments name the paths) and is written into the tests.
The builders are module functions so that artifacts/w5-b/scripts/l4_merge_reobserve.py counts the same structures.
"""
import copy
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from verantyx import observe as O
from verantyx.event_cross import PlaceResult

TREE = Path(__file__).resolve().parents[2]


class _Everyone:
    """Every word is a person; the neighbour sets are given per word."""
    id = "w5b-everyone/1"

    def __init__(self, neighbors=None):
        self._nb = neighbors or {}

    def lookup(self, lemma):
        return PlaceResult("DECIDED", "direct", None, ("PERSON",), {"w5b": True})

    def neighbors(self, lemma):
        if lemma in self._nb:
            return O.NeighborResult("FOUND", tuple(sorted(self._nb[lemma])), {"w5b": True})
        return O.NeighborResult("NO_NEIGHBORS", (), {"w5b": True})


def _clause(predicate, agent):
    return {"predicate": predicate, "roles": {"agent": agent}, "polarity": "+", "tense": "past",
            "modality": None, "voice": "active"}


def _reading(clauses, relations):
    return {"schema": "verantyx.semantic_read/1", "lang": "ja", "readable": True,
            "clauses": [_clause(p, a) for p, a in clauses],
            "relations": [{"type": "cause", "from": i, "to": j} for i, j in relations],
            "abstain": None, "unsupported": [],
            "clause_meta": [{"rule": "frame", "span": [i, i + 1]} for i in range(len(clauses))]}


def _item(ident, left, right):
    return {"id": ident, "reading": _reading([left, right], [(0, 1)])}


def _viewpoint(anchor_clauses, anchor_relations, direction):
    anchor = O.AnchorText("seed", "seed", None, 0, _reading(anchor_clauses, anchor_relations))
    return O.Viewpoint(anchor, direction)


def build_two_level_merge():
    """A -> B -> C -> D. A->B is said twice (the anchor sentence and s0), B->C twice (s1, s2), C->D once (s3).
    Paths by hand: B 2 (anchor, s0); C 2 x 2 = 4; D 4 x 1 = 4."""
    A, B, C, D = ("走る", "犬"), ("眠る", "猫"), ("食べる", "鳥"), ("泳ぐ", "魚")
    people = _Everyone()
    items = [_item("s0", A, B), _item("s1", B, C), _item("s2", B, C), _item("s3", C, D)]
    vp = _viewpoint([A, B], [(0, 1)], (O.Edge("cause"),) * 3)
    return vp, O.Structure.from_injected(items, people, people), {"眠る": 2, "食べる": 4, "泳ぐ": 4}


def build_merge_after_face_swap():
    """The anchor reaches two cells that differ in the agent only (猫 / 鼠 sleeping), then FACE_SWAP(agent) turns both into
    'a bird sleeps' (鳥 is a neighbour of both): that cell has 2 paths (one through each), the other swap target (兎, a
    neighbour of 猫 only) has 1; then one sentence (s0) says what follows 'a bird sleeps': its target carries the 2 paths.
    Paths by hand: 眠る(鳥) 2; 眠る(兎) 1; 歌う(馬) 2 x 1 = 2."""
    A, B1, B2 = ("走る", "犬"), ("眠る", "猫"), ("眠る", "鼠")
    sleeping_bird, sings = ("眠る", "鳥"), ("歌う", "馬")
    people = _Everyone({"猫": ["鳥", "兎"], "鼠": ["鳥"]})
    items = [_item("s0", sleeping_bird, sings)]
    vp = _viewpoint([A, B1, B2], [(0, 1), (0, 2)], (O.Edge("cause"), O.FaceSwap("agent"), O.Edge("cause")))
    return vp, O.Structure.from_injected(items, people, people), {"眠る": None, "歌う": 2}


def build_two_merges_in_a_row():
    """A -> {B1, B2} -> C -> {D1, D2} -> E; each arrow is said once.
    Paths by hand: B1 1, B2 1; C 2; D1 2, D2 2; E 2 + 2 = 4."""
    A, B1, B2, C = ("走る", "犬"), ("眠る", "猫"), ("眠る", "鼠"), ("食べる", "鳥")
    D1, D2, E = ("泳ぐ", "魚"), ("泳ぐ", "蟹"), ("笑う", "馬")
    people = _Everyone()
    items = [_item("s1", B1, C), _item("s2", B2, C), _item("s3", C, D1), _item("s4", C, D2),
             _item("s5", D1, E), _item("s6", D2, E)]
    vp = _viewpoint([A, B1, B2], [(0, 1), (0, 2)], (O.Edge("cause"),) * 4)
    return vp, O.Structure.from_injected(items, people, people), {"食べる": 2, "笑う": 4}


BUILDERS = (build_two_level_merge, build_merge_after_face_swap, build_two_merges_in_a_row)


def _elements_by_predicate_and_agent(obs):
    return {(e.cell.cross.center["predicate"],
             next(iter(e.cell.cross.arms["agent"].fillers)).surface): e.to_dict() for e in obs.elements()}


# --------------------------------------------------------------------------- every path is carried and re-observable
def test_two_level_merge_counts_every_path_and_every_element_is_reobserved():
    vp, st, want = build_two_level_merge()
    obs = O.observe(vp, st)
    els = _elements_by_predicate_and_agent(obs)
    assert len(els[("眠る", "猫")]["coords"]) == 2
    assert len(els[("食べる", "鳥")]["coords"]) == 4
    assert len(els[("泳ぐ", "魚")]["coords"]) == 4
    for e in obs.elements():
        assert O.reobserve(e, vp, st) == {"status": "REOBSERVED", "reason": None}, e.cell.key


def test_a_merge_after_face_swap_keeps_both_swapped_paths_and_passes_them_on():
    vp, st, _ = build_merge_after_face_swap()
    obs = O.observe(vp, st)
    els = _elements_by_predicate_and_agent(obs)
    assert len(els[("眠る", "鳥")]["coords"]) == 2
    assert len(els[("眠る", "兎")]["coords"]) == 1
    assert len(els[("歌う", "馬")]["coords"]) == 2
    swapped = els[("眠る", "鳥")]["coords"]
    assert {c["moves"][1]["from"] for c in swapped} == {"猫", "鼠"}          # one path through each of the two cells
    assert {c["moves"][0]["to"] for c in swapped} == {1, 2}
    for e in obs.elements():
        assert O.reobserve(e, vp, st)["status"] == "REOBSERVED", e.cell.key


def test_two_merges_in_a_row_multiply_the_paths_correctly():
    vp, st, _ = build_two_merges_in_a_row()
    obs = O.observe(vp, st)
    els = _elements_by_predicate_and_agent(obs)
    got = {k[1]: len(v["coords"]) for k, v in els.items()}
    assert got == {"犬": 1, "猫": 1, "鼠": 1, "鳥": 2, "魚": 2, "蟹": 2, "馬": 4}
    for e in obs.elements():
        assert O.reobserve(e, vp, st)["status"] == "REOBSERVED", e.cell.key


def test_the_counts_of_the_observation_are_per_cell_not_per_path():
    vp, st, _ = build_two_merges_in_a_row()
    obs = O.observe(vp, st)
    assert obs.counts["candidates"] == 6                    # B1 B2 C D1 D2 E: six cells, twelve paths (1+1+2+2+2+4)
    assert sum(len(e.cell.coords) for e in obs.elements() if e.cell.distance > 0) == 12


def test_the_coordinates_are_in_string_order_and_without_repeats():
    vp, st, _ = build_two_level_merge()
    for e in O.observe(vp, st).elements():
        texts = [O._cj(c) for c in e.cell.coords]
        assert texts == sorted(set(texts))


# --------------------------------------------------------------------------- reobserve asks for all of them
def test_an_element_with_a_path_taken_away_is_not_reobserved():
    for build in BUILDERS:
        vp, st, _ = build()
        multi = [e for e in O.observe(vp, st).elements() if len(e.cell.coords) > 1]
        assert multi, build.__name__
        for e in multi:
            d = e.to_dict()
            d["coords"] = d["coords"][:-1]
            assert O.reobserve(d, vp, st) == {"status": "MISMATCH", "reason": "COORDS_INCOMPLETE"}, (build.__name__, e.cell.key)


def test_an_element_with_a_path_that_is_not_there_is_a_mismatch():
    vp, st, _ = build_two_merges_in_a_row()
    e = next(x for x in O.observe(vp, st).elements() if x.cell.cross.center["predicate"] == "食べる")
    d = e.to_dict()
    ghost = copy.deepcopy(d["coords"][0])
    ghost["moves"][-1]["reading"] = "no-such-sentence"
    d["coords"] = d["coords"] + [ghost]
    res = O.reobserve(d, vp, st)
    assert res["status"] == "MISMATCH" and res["reason"] in ("EDGE_NOT_IN_STRUCTURE", "COORDS_EXTRA"), res


def test_a_real_path_that_is_not_one_of_the_observed_ones_is_extra():
    """There and back again: C -> B1 (backward) -> C is a path that replays, but it is not a path of distance 2."""
    vp, st, _ = build_two_merges_in_a_row()
    e = next(x for x in O.observe(vp, st).elements() if x.cell.cross.center["predicate"] == "食べる")
    d = e.to_dict()
    last = d["coords"][0]["moves"][-1]
    back = dict(last, **{"from": last["to"], "to": last["from"], "dir": "backward"})
    longer = copy.deepcopy(d["coords"][0])
    longer["moves"] += [back, last]
    d["coords"] = d["coords"] + [longer]
    assert O.reobserve(d, vp, st) == {"status": "MISMATCH", "reason": "COORDS_EXTRA"}


def test_a_coordinate_carried_twice_is_not_what_observe_gave():
    """The same set of coordinates is not enough: observe writes each path once, so an element that repeats one is not what it gave
    (a user who counts the coordinates would count a path twice)."""
    for build in BUILDERS:
        vp, st, _ = build()
        multi = [e for e in O.observe(vp, st).elements() if len(e.cell.coords) > 1]
        assert multi, build.__name__
        for e in multi:
            d = e.to_dict()
            d["coords"] = d["coords"] + [copy.deepcopy(d["coords"][0])]
            assert O.reobserve(d, vp, st) == {"status": "MISMATCH", "reason": "COORDS_DUPLICATED"}, (build.__name__, e.cell.key)
        # a single-path element repeated is the same mistake
        single = next((x for x in O.observe(vp, st).elements() if len(x.cell.coords) == 1), None)
        if single is not None:
            d = single.to_dict()
            d["coords"] = d["coords"] * 2
            assert O.reobserve(d, vp, st) == {"status": "MISMATCH", "reason": "COORDS_DUPLICATED"}, (build.__name__, single.cell.key)


def test_an_element_of_a_cell_that_is_not_observed_from_this_viewpoint_is_named():
    vp, st, _ = build_two_level_merge()
    e = next(x for x in O.observe(vp, st).elements() if x.cell.cross.center["predicate"] == "食べる")
    d = e.to_dict()
    shorter = O.Viewpoint(vp.anchor, vp.direction, 1)       # the cell is at distance 2: every path replays, but it is not observed
    assert O.reobserve(d, shorter, st) == {"status": "MISMATCH", "reason": "CELL_NOT_OBSERVED"}


# --------------------------------------------------------------------------- the placement id is the content
def _cli(*args):
    env = {"HOME": os.environ.get("HOME", ""), "PATH": "/usr/bin:/bin", "PYTHONPATH": str(TREE),
           "PYTHONDONTWRITEBYTECODE": "1", "PYTHONHASHSEED": "0"}
    return subprocess.run([sys.executable, "-m", "verantyx.cli", "observe", *map(str, args)], cwd=str(TREE), env=env,
                          capture_output=True, text=True, timeout=180)


SENTENCE = "次郎は三郎に本をあげた。"


def _placement(path, neighbors, *, indent=None, key_order=False, lemmas=None):
    words = lemmas or ["次郎", "三郎", "四郎", "五郎"]
    lem = {w: {"state": "DECIDED", "origin": "direct", "types": ["PERSON"]} for w in words}
    if key_order:
        lem = dict(reversed(list(lem.items())))
    body = {"neighbors": {"次郎": neighbors}, "lemmas": lem} if key_order else {"lemmas": lem, "neighbors": {"次郎": neighbors}}
    path.write_text(json.dumps(body, ensure_ascii=False, indent=indent), encoding="utf-8")
    return path


def _run(placement):
    r = _cli("--anchor-text", SENTENCE, "--direction", "FACE_SWAP:agent", "--placement", placement, "--no-index")
    assert r.returncode == 0, r.stderr
    return r.stdout


def test_a_placement_file_that_differs_in_bytes_only_gives_the_same_output(tmp_path):
    a = _run(_placement(tmp_path / "a.json", ["三郎", "四郎", "五郎"]))
    b = _run(_placement(tmp_path / "b.json", ["五郎", "三郎", "四郎"], indent=2, key_order=True))
    c = _run(_placement(tmp_path / "c.json", ["四郎", "五郎", "三郎", "三郎"]))        # a repeated word: a set has it once
    assert a == b == c
    assert json.loads(a)["structure"]["placement"].startswith("file:")


def test_a_different_set_of_neighbours_or_answer_is_another_id(tmp_path):
    base = json.loads(_run(_placement(tmp_path / "a.json", ["三郎", "四郎"])))["structure"]
    other_set = json.loads(_run(_placement(tmp_path / "b.json", ["三郎", "五郎"])))["structure"]
    other_answer = tmp_path / "c.json"
    body = json.loads(_placement(other_answer, ["三郎", "四郎"]).read_text(encoding="utf-8"))
    body["lemmas"]["三郎"]["types"] = ["ANIMAL"]
    other_answer.write_text(json.dumps(body, ensure_ascii=False), encoding="utf-8")
    other_answer_id = json.loads(_run(other_answer))["structure"]
    assert len({base["placement"], other_set["placement"], other_answer_id["placement"]}) == 3
    assert base["neighbors"] == base["placement"]


def test_the_id_does_not_depend_on_the_path_or_the_file_name(tmp_path):
    (tmp_path / "x").mkdir()
    one = json.loads(_run(_placement(tmp_path / "one.json", ["三郎", "四郎"])))
    two = json.loads(_run(_placement(tmp_path / "x" / "two.json", ["四郎", "三郎"])))
    assert one == two


# --------------------------------------------------------------------------- a broken ledger is refused before it is written
def _ledger(tmp_path, name, *events):
    path = tmp_path / name
    path.write_text("".join(json.dumps({"seq": i, "id": f"ev:{i}", "ts": "t", **e}, ensure_ascii=False) + "\n"
                            for i, e in enumerate(events, 1)), encoding="utf-8")
    return path


GOOD_UTTERANCE = {"kind": "utterance", "payload": {"text": "次郎は三郎に本をあげた。", "anchor": "seed"}}
BAD_LEDGERS = {
    "text_is_a_list": [{"kind": "utterance", "payload": {"text": ["次郎"], "anchor": "seed"}}],
    "state_seq_is_a_string": [GOOD_UTTERANCE, {"kind": "observation", "payload": {
        "viewpoint": {}, "outcome": "FOCUS", "state_seq": "1", "output_sha256": "x", "observed_cell": "c"}}],
    "tie_cells_is_a_string": [GOOD_UTTERANCE, {"kind": "observation", "payload": {
        "viewpoint": {}, "outcome": "TIE", "state_seq": 1, "output_sha256": "x", "tie_cells": "abc"}}],
    "decided_cell_is_a_list": [GOOD_UTTERANCE, {"kind": "decision", "payload": {"decided_cell": ["a", "b"]}}],
    "anchor_kind_unknown": [{"kind": "utterance", "payload": {"text": "x", "anchor": "shout"}}],
    "outcome_unknown": [GOOD_UTTERANCE, {"kind": "observation", "payload": {
        "viewpoint": {}, "outcome": "MAYBE", "state_seq": 1, "output_sha256": "x"}}],
}


@pytest.mark.parametrize("name", sorted(BAD_LEDGERS))
def test_a_ledger_with_a_bad_payload_is_refused_with_code_3_and_not_changed(tmp_path, name):
    ledger = _ledger(tmp_path, name + ".jsonl", *BAD_LEDGERS[name])
    before = ledger.read_bytes()
    r = _cli("--anchor-text", SENTENCE, "--no-index", "--ledger", ledger)
    assert r.returncode == 3, (r.returncode, r.stdout[:200], r.stderr[:200])
    assert ledger.read_bytes() == before
    assert r.stdout == "" or "LEDGER_INVALID" in r.stdout + r.stderr


def test_the_refusal_names_the_event_and_the_field(tmp_path):
    ledger = _ledger(tmp_path, "l.jsonl", *BAD_LEDGERS["state_seq_is_a_string"])
    r = _cli("--anchor-text", SENTENCE, "--no-index", "--ledger", ledger)
    assert "PAYLOAD_INVALID:seq=2:state_seq" in r.stdout + r.stderr


def test_the_first_bad_event_decides_even_when_a_later_one_is_bad_too(tmp_path):
    events = [GOOD_UTTERANCE, {"kind": "decision", "payload": {"decided_cell": 3}},
              {"kind": "utterance", "payload": {"text": 5}}]
    ledger = _ledger(tmp_path, "l.jsonl", *events)
    r = _cli("--anchor-text", SENTENCE, "--no-index", "--ledger", ledger)
    assert r.returncode == 3 and "seq=2:decided_cell" in r.stdout + r.stderr


def test_a_ledger_the_observer_wrote_is_read_back_and_extended(tmp_path):
    ledger = tmp_path / "own.jsonl"
    for turn in (1, 2):
        r = _cli("--anchor-text", SENTENCE, "--no-index", "--ledger", ledger)
        assert r.returncode == 0, r.stderr
        assert len(ledger.read_text(encoding="utf-8").splitlines()) == 2 * turn
