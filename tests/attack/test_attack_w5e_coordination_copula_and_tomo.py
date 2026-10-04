"""W5-e B attack: coordinated noun phrases used as role values must abstain."""

import json

import pytest

from verantyx import semantic_read


@pytest.mark.parametrize("text", [
    "犯人は太郎と花子だ。",
    "太郎とも花子とも話した。",
])
def test_b_a_coordinated_noun_phrase_is_not_returned_as_one_role_value(text):
    out = semantic_read.read(text, "ja")
    reasons = [reason for unit in out.get("unsupported", [])
               for reason in unit.get("reasons", [])]
    assert not out["readable"] and "COORDINATION_UNDETERMINED" in reasons, json.dumps(out, ensure_ascii=False)
