"""Type inventory, seeds and notation rules (W3-a, step 1)."""
import json
from pathlib import Path

from verantyx import coarse_types as ct

TREE = Path(__file__).resolve().parents[2]

# The inventory as frozen at the time the first placement was built.  The system
# only GROWS: ids may be added, never removed or renamed.
FROZEN_NOUN_TYPES = {
    "PERSON", "GROUP_ORG", "ANIMAL", "PLANT", "ARTIFACT", "SUBSTANCE_FOOD",
    "PLACE", "TIME", "QUANTITY", "EVENT_ACT", "STATE_PROPERTY", "ABSTRACT",
    "INFO_LANGUAGE", "BODY_PART", "NATURAL_PHENOMENON", "WORK", "IDENTIFIER"}
FROZEN_PRED_TYPES = {
    "P_GIVE", "P_MOVE", "P_CHANGE", "P_CREATE", "P_COMMUNICATE", "P_PERCEIVE",
    "P_EXIST", "P_POSSESS", "P_STATE", "P_COGNITION", "P_EMOTION", "P_CONSUME",
    "P_ACT"}
TICKET_TRAP_WORDS = ["土手", "分母", "器官", "空母", "民家", "商社", "教会",
                     "本部", "手", "目"]


def test_inventory_only_grows():
    """2026-10-04 20:38:46 +0900: before 17, now 18 NOUN_TYPES because RELATIVE_POSITION was added; retain the old 17 ids."""
    assert FROZEN_NOUN_TYPES <= set(ct.NOUN_TYPES)
    assert FROZEN_PRED_TYPES <= set(ct.PRED_TYPES)
    assert set(ct.type_ids("N")) == set(ct.NOUN_TYPES)
    assert set(ct.type_ids("P")) == set(ct.PRED_TYPES)
    assert all(t.startswith("P_") for t in ct.PRED_TYPES)
    assert not any(t.startswith("P_") for t in ct.NOUN_TYPES)
    assert ct.type_namespace("P_GIVE") == "P" and ct.type_namespace("PLACE") == "N"
    assert 18 == len(ct.NOUN_TYPES) and 13 == len(ct.PRED_TYPES)


def test_seed_limits_and_known_types():
    total = 0
    for t, ws in ct.SEEDS_NOUN.items():
        assert t in ct.NOUN_TYPES
        assert len(ws) == len(set(ws)) <= ct.MAX_SEEDS_PER_NOUN_TYPE
        total += len(ws)
    assert total <= ct.MAX_SEEDS_NOUN_TOTAL
    for t, ws in ct.SEEDS_PRED.items():
        assert t in ct.PRED_TYPES
        assert len(set(ws)) <= ct.MAX_SEEDS_PER_PRED_TYPE
    flat = [w for ws in ct.SEEDS_NOUN.values() for w in ws]
    assert len(flat) == len(set(flat)), "a seed word has exactly one type"


def test_seeds_do_not_contain_the_ticket_trap_words():
    flat = {w for ws in ct.SEEDS_NOUN.values() for w in ws}
    assert not (flat & set(TICKET_TRAP_WORDS))


def test_boundary_rules_are_written_down():
    text = "\n".join(ct.BOUNDARY_RULES)
    for needle in ("PLACE", "ARTIFACT", "GROUP_ORG", "SUBSTANCE_FOOD",
                   "STATE_PROPERTY", "ABSTRACT", "INFO_LANGUAGE", "WORK",
                   "TIME", "QUANTITY", "IDENTIFIER"):
        assert needle in text


def test_notation_rules():
    n = ct.notation_type
    assert n("2006") == ("QUANTITY", "number")
    assert n("２００６")[0] == "QUANTITY"            # full-width digits
    assert n("2024年")[0] == "TIME"
    assert n("12月25日")[0] == "TIME"
    assert n("2024-10-03")[0] == "TIME"
    assert n("10:30")[0] == "TIME"
    assert n("令和6年")[0] == "TIME"
    assert n("午前9時")[0] == "TIME"
    assert n("3個") is None                          # a counter must be learned
    assert n("3個", ["個"])[0] == "QUANTITY"
    assert n("https://example.com/a")[0] == "IDENTIFIER"
    assert n("user@example.com")[0] == "IDENTIFIER"
    assert n("ABC-123")[0] == "IDENTIFIER"
    assert n("v2.3.1")[0] == "IDENTIFIER"
    assert n("土手") is None and n("犬") is None and n("") is None
    assert n("3人称") is None                         # not a learned counter
    assert n("192.168.0.1")[0] == "IDENTIFIER"       # an address, not a number
    assert n("3.14")[0] == "QUANTITY"                # a decimal, not a version
    # a learned counter counts only after an Arabic number: a kanji numeral + that
    # unit is as often an ordinary word
    assert n("5座", ["座"])[0] == "QUANTITY"
    assert n("一座", ["座"]) is None and n("九州", ["州"]) is None


def test_frozen_data_does_not_leak_into_seeds_beyond_the_recorded_overlap():
    fz = json.loads((TREE / "artifacts/w3-a/FROZEN.json").read_text(encoding="utf-8"))
    seeds = {w for ws in ct.SEEDS_NOUN.values() for w in ws}
    rows = [json.loads(l) for l in
            (TREE / "tests/coarse_place/data/typed_vocab.jsonl").read_text(encoding="utf-8").splitlines()]
    overlap = sorted(r["term"] for r in rows if r["term"] in seeds)
    assert set(overlap) <= set(fz["seed_overlap_terms"]), \
        "seeds must not grow into the frozen test vocabulary"


def test_predicate_seeds_do_not_overlap_the_frozen_predicate_check_beyond_the_recorded_overlap():
    """Review r1 M4: the predicate seeds may overlap the frozen predicate check
    only in the words the frozen file marked ``seed_overlap: true`` (ten of
    them, from before the freeze); here the overlap is in fact empty."""
    rows = [json.loads(l) for l in
            (TREE / "tests/coarse_place/data/predicate_check.jsonl").read_text(encoding="utf-8").splitlines()]
    frozen_overlap = {r["term"] for r in rows if r.get("seed_overlap")}
    assert len(frozen_overlap) == 10
    seeds = {w for ws in ct.SEEDS_PRED.values() for w in ws}
    overlap = {r["term"] for r in rows if r["term"] in seeds}
    assert overlap <= frozen_overlap, sorted(overlap - frozen_overlap)


def test_predicate_seeds_come_from_the_head_of_the_material_frequency_list():
    """Review r1 M4(b): every predicate seed has a rank in
    ``artifacts/w3-a/pred_verb_freq.tsv`` (made by ``pred_seed_freq.py`` from the
    material's own counts) no larger than the range recorded next to it."""
    summ = json.loads((TREE / "artifacts/w3-a/pred_seed_freq_summary.json").read_text(encoding="utf-8"))
    ranks = {}
    for i, line in enumerate((TREE / "artifacts/w3-a/pred_verb_freq.tsv").read_text(encoding="utf-8").splitlines()):
        if i:
            f = line.split("\t")
            ranks[f[1]] = int(f[0])
    seeds = {w for ws in ct.SEEDS_PRED.values() for w in ws}
    assert seeds, "no predicate seeds"
    assert all(w in ranks and ranks[w] <= summ["range"] for w in seeds), \
        sorted(w for w in seeds if ranks.get(w, 10 ** 9) > summ["range"])
    assert summ["seeds_outside_range"] == [] and summ["predicate_seeds"] == len(seeds)
