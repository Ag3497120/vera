"""W3-a6 (docs 12.18): the 18th noun type, the 17-type list the frames use, the role names and their descriptions."""
import json
import re
from pathlib import Path

from verantyx import coarse_types as ct
from verantyx import event_cross

TREE = Path(__file__).resolve().parents[2]
DATA = TREE / "tests/coarse_place/data"
EXPECT = json.loads((DATA / "w3a6_expect.json").read_text(encoding="utf-8"))
FIRST_17 = ["PERSON", "GROUP_ORG", "ANIMAL", "PLANT", "ARTIFACT", "SUBSTANCE_FOOD", "PLACE", "TIME", "QUANTITY",
            "EVENT_ACT", "STATE_PROPERTY", "ABSTRACT", "INFO_LANGUAGE", "BODY_PART", "NATURAL_PHENOMENON", "WORK",
            "IDENTIFIER"]


def test_the_relative_position_type_is_appended_and_the_first_seventeen_are_unchanged():
    ids = list(ct.NOUN_TYPES)
    assert ids[-1] == "RELATIVE_POSITION" and ids[:17] == FIRST_17 and len(ids) == 18
    assert ct.NOUN_TYPES["RELATIVE_POSITION"] == "相対位置・方向"
    assert "RELATIVE_POSITION" in ct.type_ids("N") and ct.type_namespace("RELATIVE_POSITION") == "N"


def test_the_frame_noun_types_are_the_seventeen_in_the_same_order():
    assert list(ct.FRAME_NOUN_TYPES) == FIRST_17
    assert "RELATIVE_POSITION" not in ct.FRAME_NOUN_TYPES
    assert all(ct.FRAME_NOUN_TYPES[k] == ct.NOUN_TYPES[k] for k in FIRST_17)


def test_the_note_of_the_new_type_is_the_ticket_definition():
    assert ct.NOUN_TYPE_NOTES == {"RELATIVE_POSITION": "他の物や場所を基準にした位置・方向を表す語。それ自体は場所ではない"}


def test_the_pinned_arm_constants_did_not_grow():
    assert ct.GEN_ARMS == ("gen_definition", "gen_frame")
    assert "gen_relpos" not in ct.ARMS and "gen_relpos" not in ct.GEN_ARMS
    assert ct.GEN_RELPOS_ARM == "gen_relpos"
    assert set(ct.AGREEMENT_ONLY_ARMS) == {"role_distribution", "slot"}
    assert ct.ARMS[-3:] == ("role_distribution", "gen_frame", "slot")


def conventions_roles():
    text = (TREE / "docs/READING_CONVENTIONS.md").read_text(encoding="utf-8")
    sec = text[text.index("## 2. 役割名"):text.index("## 3. 値の書き方")]
    out = []
    for line in sec.splitlines():
        m = re.match(r"^\|\s*`([a-z]+)`\s*\|", line)
        if m:
            out.append(m.group(1))
    return out


def test_the_role_names_are_those_of_the_conventions_and_of_the_event_cross():
    assert ct.ROLE_NAMES == tuple(event_cross.ROLE_NAMES)
    assert list(ct.ROLE_NAMES) == conventions_roles() and len(ct.ROLE_NAMES) == 20
    assert set(ct.ROLE_DESCRIPTIONS) == set(ct.ROLE_NAMES)
    assert all(isinstance(v, str) and v.strip() for v in ct.ROLE_DESCRIPTIONS.values())


def _test_terms():
    out = set()
    for p in sorted(DATA.glob("*.jsonl")):
        for line in p.read_text(encoding="utf-8").splitlines():
            if line.strip():
                t = json.loads(line).get("term")
                if isinstance(t, str) and len(t) >= 2:
                    out.add(t)
    return out


def test_no_description_quotes_a_test_word_or_a_word_of_the_expectations():
    preds = {r["pred"] for r in EXPECT["roles"]}
    terms = _test_terms()
    for role, text in list(ct.ROLE_DESCRIPTIONS.items()) + list(ct.NOUN_TYPE_NOTES.items()):
        pieces = set(re.split(r"[\s、。・（）()「」]+", text))
        assert not (pieces & terms), (role, pieces & terms)
        for pred in preds:
            assert pred not in text, (role, pred)
        for w in EXPECT["relative_position"]:
            assert w not in pieces, (role, w)
