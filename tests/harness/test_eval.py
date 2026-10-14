"""H5: `vera eval` -- the shipped eval sets are intact, the record is consistent, the comparison fails on a safety regression, and a few items of each kind run end to end.
The full sweeps run in CI (`vera eval --quick`), not here."""
import copy
import json
import os

import pytest

from verantyx.harness import cli
from verantyx.harness import evalrun as er


def test_the_shipped_files_are_the_bytes_the_manifest_names():
    er.check_manifest()


def test_item_counts_match_the_banks_they_come_from():
    got = {n: (sum(i["kind"] == "ans" for i in er.items_of(n)), sum(i["kind"] == "unans" for i in er.items_of(n))) for n in er.GATE_SETS}
    assert got == {"dev": (69, 60), "bank6": (26, 34), "bank7": (32, 47), "bank8": (35, 50)}
    for n in er.GATE_SETS:
        assert all(it["titles"] for it in er.items_of(n)), "every item names an article to sweep in --quick"


def test_the_record_holds_both_modes_and_the_claims_it_documents():
    rec = er.load_expected()
    for mode in ("quick", "full"):
        g = rec[mode]["gate_sets"]
        assert {n: x["unans_admitted"] for n, x in g.items()} == {"dev": 0, "bank6": 0, "bank7": 0, "bank8": 0}
        assert g["bank6"]["wrong_admitting"] == 3 and g["bank8"]["wrong_admitting"] == 1
    assert rec["quick"]["gate_sets"] == rec["full"]["gate_sets"]                    # the cut slice holds every stretch the gate passes


def _m(unans=0, wrong=0, reach=3):
    g = {"answerable": 26, "unanswerable": 34, "reach": reach, "wrong_admitting": wrong, "unans_admitted": unans, "reach_ids": ["a", "b", "c"][:reach], "wrong_ids": [], "admitted_ids": ["U1"] * unans}
    return {"gate": er.GATE_VERSION, "v6_digest": "d" * 64, "mode": "quick", "gate_sets": {"bank6": g}}


def _rec(**kw):
    return {"v6_digest": "d" * 64, "quick": {"gate_sets": {"bank6": dict(_m()["gate_sets"]["bank6"], **kw)}}}


def test_compare_is_silent_when_nothing_changed_and_flags_each_kind_of_regression():
    assert er.compare(_m(), _rec()) == {"safety": [], "capability": [], "notes": []}
    assert er.compare(_m(unans=1), _rec())["safety"]                                  # a new unanswerable admission
    assert er.compare(_m(wrong=1), _rec())["safety"]                                  # a new wrong answer admitted
    assert er.compare(_m(reach=2), _rec())["capability"] and not er.compare(_m(reach=2), _rec())["safety"]
    assert er.compare(_m(reach=3), _rec(reach=2))["notes"]                            # a rise is noted, not an error
    other = _rec()
    other["v6_digest"] = "e" * 64
    assert "rules changed" in er.compare(_m(), other)["notes"][0]


def test_memory_safety_counters_must_be_zero_whatever_the_record_says():
    m = dict(_m(), memory={"verified": True, "safety": {"emitted_old": 1}, "capability": {}, "notes": {}})
    assert any("emitted_old" in s for s in er.compare(m, _rec())["safety"])
    m["memory"]["safety"] = {"emitted_old": 0}
    m["memory"]["verified"] = False
    assert any("verify" in s for s in er.compare(m, _rec())["safety"])


def test_a_few_items_through_the_gate_in_quick_mode():
    # B6-A05 is answerable: the gate lets the gold-bearing stretches through (reach) and B6-U01 (an alias that is not written) is refused
    out = er.gate_eval(["bank6"], quick=True, only=["B6-A05", "B6-U01", "B6-U35"])
    g = out["bank6"]
    assert g["answerable"] == 1 and g["unanswerable"] == 2
    assert g["unans_admitted"] == 0 and g["admitted_ids"] == []                   # B6-U35 is the item evidence.v2 let through and v6 refuses
    assert g["reach"] == 1 and g["reach_ids"] == ["B6-A05"] and g["wrong_admitting"] == 1


def test_the_memory_red_teams_run_end_to_end_on_a_few_questions():
    out = er.memory_eval(limit_q=2, only=["MEM-T01"])
    assert out["stores"] == ["MEM-T01"] and out["verified"] is True
    assert all(v == 0 for v in out["safety"].values()), out["safety"]
    assert out["capability"]["questions"] == 2 and out["writes"] > 10 and out["accepted"] > 0


def test_the_cli_prints_the_table_and_exits_by_the_comparison(tmp_path, capsys):
    rc = cli.main(["eval", "--quick", "--set", "bank6", "--no-memory", "--workers", "1", "--item", "B6-A05", "--item", "B6-U35"])
    out = capsys.readouterr().out
    assert "bank6" in out and "RESULT:" in out
    assert rc in (0, 1)
    rec = tmp_path / "rec.json"
    rc = cli.main(["eval", "--quick", "--set", "bank6", "--no-memory", "--workers", "1", "--item", "B6-U35", "--freeze", str(rec)])
    capsys.readouterr()
    data = json.loads(rec.read_text(encoding="utf-8"))
    assert data["quick"]["gate_sets"]["bank6"]["unans_admitted"] == 0 and data["v6_digest"]
