"""Independently audit saved paired results with exact rational arithmetic."""
import json
from fractions import Fraction
from pathlib import Path

HERE = Path(__file__).resolve().parent


def main():
    data = json.loads((HERE / "results.json").read_text())
    checked = 0
    for row in data["rows"]:
        for raw, gate in (("baseline", "specificity"),
                          ("no_junk", "no_junk_specificity")):
            a, b = row["arms"][raw], row["arms"][gate]
            evidence = b["evidence"]
            assert a["candidates"] == b["candidates"]
            assert a["placement"] == b["placement"]
            if a["result"]["verdict"] == "ANSWER":
                assert len(evidence["covered"]) == evidence["numerator"]
                assert set(evidence["covered"]) <= set(row["query_content"])
                assert evidence["denominator"] == max(1, evidence["facet_count"])
                refusal = (Fraction(evidence["numerator"], evidence["denominator"])
                           < Fraction(1, 20))
                assert refusal == evidence["refused"]
                assert (b["result"]["verdict"] == "UNKNOWN_INSUFFICIENT_EVIDENCE") == refusal
                if refusal:
                    assert b["result"]["core"] is None
                    assert b["result"]["text"] == "" and b["result"]["tokens"] == []
                else:
                    assert a["result"] == b["result"]
            else:
                assert a["result"] == b["result"]
            checked += 1
    report = {"verified_pairs": checked, "exact_fraction_audit": "PASS",
              "candidate_and_placement_identity": "PASS",
              "non_answer_preservation": "PASS"}
    (HERE / "audit_result.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
