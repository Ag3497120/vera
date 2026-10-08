# W5-b: copied from attacks/W3-a2/test_attack_contract.py; the assert of test_hiragana_katakana_variant_keeps_same_state revised per the auditor's ruling C1 (2026-10-03; before/after in docs/COARSE_PLACEMENT.md 11.9)
"""Executable counterexamples against the W3-a2 query contract.

Run from the clone root with the prescribed interpreter and environment:
PYTHONPATH="$PWD" PYTHONDONTWRITEBYTECODE=1 \
  /Users/motonisihikoudai/vera-wiring/env/bin/python -m pytest -q attacks/W3-a2/test_attack_contract.py
"""
import os

import pytest

from verantyx.coarse_place import query


PLACEMENT = "/Users/motonisihikoudai/Projects/vera-impl/build/coarse-W3a/full/r5/run1"
# integration (auditor): the placement is an artefact outside the tree; on a host without it the tests are an environment gap, not a failure
pytestmark = pytest.mark.skipif(not os.path.isdir(PLACEMENT), reason="ENV_MISSING[coarse placement r5/run1]")


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
    # W5-b round 4 (auditor ruling C1, 2026-10-03): the two kana spellings stay two words; an UNPLACED / UNKNOWN spelling whose other
    # kana spelling is DECIDED and direct gets that type as an ESTIMATE (estimate_basis kana_variant), never as a direct answer.
    assert (katakana["state"], katakana["origin"]) == ("DECIDED", "direct"), katakana
    assert (hiragana["state"], hiragana["top"]) == (katakana["state"], katakana["top"]), (hiragana["state"], hiragana["top"])
    assert (hiragana["origin"], hiragana["estimate_basis"], hiragana["constructed"]) == ("estimated", "kana_variant", True)
    assert hiragana["spelling"]["why"] == "ESTIMATED_FROM_KANA_VARIANT:アザミ"


def test_number_plus_time_unit_is_not_downgraded_to_quantity():
    result = ask("3年後")
    assert result["top"] == ["TIME"], (
        f"3年後 should be a time expression, got {result['top']} "
        f"via {result['axes'].get('notation')}"
    )
