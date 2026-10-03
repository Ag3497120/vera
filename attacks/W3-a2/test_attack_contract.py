"""Executable counterexamples against the W3-a2 query contract.

Run from the clone root with the prescribed interpreter and environment:
PYTHONPATH="$PWD" PYTHONDONTWRITEBYTECODE=1 \
  /Users/motonisihikoudai/vera-wiring/env/bin/python -m pytest -q attacks/W3-a2/test_attack_contract.py
"""
from verantyx.coarse_place import query


PLACEMENT = "/Users/motonisihikoudai/Projects/vera-impl/build/coarse-W3a/full/r5/run1"


def ask(term):
    return query(term, placement=PLACEMENT)


def test_nfkc_width_variant_keeps_same_state():
    fullwidth = ask("ＮＰＯ")
    ascii_form = ask("NPO")
    assert fullwidth["state"] == ascii_form["state"], (
        f"NFKC-equivalent terms changed state: ＮＰＯ={fullwidth['state']} "
        f"{fullwidth['top']}, NPO={ascii_form['state']} {ascii_form['top']}"
    )


def test_hiragana_katakana_variant_keeps_same_state():
    hiragana = ask("あざみ")
    katakana = ask("アザミ")
    assert hiragana["state"] == katakana["state"], (
        f"kana spelling variants changed state: あざみ={hiragana['state']} "
        f"{hiragana['top']}, アザミ={katakana['state']} {katakana['top']}"
    )


def test_number_plus_time_unit_is_not_downgraded_to_quantity():
    result = ask("3年後")
    assert result["top"] == ["TIME"], (
        f"3年後 should be a time expression, got {result['top']} "
        f"via {result['axes'].get('notation')}"
    )
