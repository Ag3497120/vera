"""W16-t6 / T6-1: the frozen 40 synthetic reports (artifacts/w16-t6/synth). Missed false claims 0, false alarms 0 for V and a. Fixtures are materialised in tmp."""
import importlib.util
from pathlib import Path

import pytest

from verantyx import attest

ROOT = Path(__file__).resolve().parents[1] / "artifacts" / "w16-t6" / "synth"
spec = importlib.util.spec_from_file_location("synth_lib", ROOT / "synth_lib.py")
sl = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sl)


@pytest.fixture(scope="module")
def run(tmp_path_factory):
    ok, bad = sl.freeze_ok()
    assert ok, "frozen synth files changed: %s" % bad            # the freeze is checked before anything is measured
    return sl.run_all(attest, tmp_path_factory.mktemp("synth"))


def test_the_set_has_the_registered_shape(run):
    cases, expected, results, m = run
    assert len(cases) == 40
    groups = {g: sum(1 for c in cases if c["group"] == g) for g in "ABC"}
    assert groups["A"] >= 13 and groups["B"] >= 20 and groups["C"] >= 5
    kinds = {"file_sha": 0, "test_count": 0, "test_exists": 0, "exit": 0, "number": 0}
    for e in expected:
        for c in e["claims"]:
            for f in c["facts"]:
                if f["truth"] == "false":
                    kinds[f["sig"].split(":")[0]] += 1
    assert all(v >= 4 for v in kinds.values()), kinds
    for c in cases:
        if c["has_json"]:
            assert "```json" in c["report"]
    assert any(c["flags"]["rerun"] for c in cases) and any(c["ledger"] is not None for c in cases)


@pytest.mark.parametrize("ex", ["V", "a"])
def test_no_false_claim_is_recorded_and_no_true_claim_is_flagged(run, ex):
    cases, expected, results, m = run
    x = m[ex]
    assert x["false_facts"] >= 20
    assert x["missed"] == 0 and x["claim_missed"] == 0
    assert x["false_positive"] == 0 and x["claim_false_positive"] == 0
    assert x["detected"] == x["false_facts"]
    assert x["claim_alignment_errors"] == 0
    assert x["mismatched_expectations"] == [] and x["exact"] == x["facts"]


def test_off_form_line_is_counted_in_V(run):
    m = run[3]
    assert m["V"]["offform_actual"] == m["V"]["offform_expected"] == 1


def test_b_never_records_a_false_claim_either(run):
    x = run[3]["b"]
    assert x["missed"] == 0 and x["false_positive"] == 0 and x["extra"] == 0
