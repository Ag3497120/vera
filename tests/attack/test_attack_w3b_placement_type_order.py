# W5-a: copied from attacks/W3-b/test_attack_placement_type_order.py; unchanged
"""W3-b attack: unordered MULTIPLE placement types should serialize alphabetically."""
import json

from verantyx.event_cross import PlaceResult, build_crosses


class UnsortedMultipleLookup:
    id = "attack-unsorted-multiple/1"

    def lookup(self, lemma):
        # A valid MULTIPLE result whose two type IDs arrive in reverse lexical order.
        return PlaceResult(
            state="MULTIPLE",
            origin="direct",
            estimate_basis=None,
            types=("PLACE", "PERSON"),
            provenance={},
        )


def test_multiple_type_ids_are_serialized_in_canonical_order():
    reader_output = {
        "schema": "verantyx.semantic_read/1",
        "lang": "ja",
        "readable": True,
        "clauses": [{
            "predicate": "する",
            "roles": {"agent": "対象"},
            "polarity": "+",
            "tense": "past",
            "modality": None,
            "voice": "active",
        }],
        "relations": [],
        "abstain": None,
        "unsupported": [],
        "clause_meta": [{"rule": "hand", "span": [0, 1]}],
    }

    out = build_crosses(reader_output, UnsortedMultipleLookup()).to_dict()
    placement = out["crosses"][0]["arms"]["agent"]["fillers"][0]["place"]

    assert placement["state"] == "MULTIPLE"
    assert placement["types"] == ["PERSON", "PLACE"]


def test_equal_inputs_with_relation_keys_in_a_different_order_serialize_identically():
    base = {
        "schema": "verantyx.semantic_read/1",
        "lang": "ja",
        "readable": True,
        "clauses": [
            {"predicate": "食べる", "roles": {}, "polarity": "+", "tense": "past", "modality": None, "voice": "active"},
            {"predicate": "寝る", "roles": {}, "polarity": "+", "tense": "past", "modality": None, "voice": "active"},
        ],
        "relations": [{"type": "sequence", "from": 0, "to": 1}],
        "abstain": None,
        "unsupported": [],
        "clause_meta": [{"rule": "hand", "span": [0, 1]}, {"rule": "hand", "span": [2, 3]}],
    }
    reordered = dict(base)
    reordered["relations"] = [{"to": 1, "from": 0, "type": "sequence"}]

    assert reordered == base
    a = json.dumps(build_crosses(base).to_dict(), ensure_ascii=False, separators=(",", ":"))
    b = json.dumps(build_crosses(reordered).to_dict(), ensure_ascii=False, separators=(",", ":"))
    assert a == b
