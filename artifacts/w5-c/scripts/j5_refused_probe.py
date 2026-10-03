"""W5-c review r1 optional 1 (round 3: the recorded claim differs from the result text; the used / not_used counts are printed): a result that is already a refusal and cites a source, with a recorded 'yes' for the same
question in a consenting sovereign. Usage: j5_refused_probe.py WORKDIR (created fresh by the caller). PYTHONPATH=<tree>."""
import json, os, sys
from pathlib import Path
from verantyx import basis_policy as bp, sovereign as sov

work = Path(sys.argv[1]); work.mkdir(parents=True, exist_ok=True)
root = work / "sov"
assert sov.create(str(root), "s1", "o", consent_promote=True)["verdict"] == "CREATED"
os.environ["VERA_SOVEREIGN_ROOT"], os.environ["VERA_SOVEREIGN_STORE"] = str(root), "s1"
claim = "窓が光ります。"                # the text of every result below
record_claim = "人の答え。"             # round 3: the recorded "yes" carries a sentence that differs from the result's own text
rec = {"record": "basis_confirmation", "status": "HUMAN_CONFIRMED", "witness": "user_confirmation", "confirm_id": "abc",
       "query": "窓は？", "claim": record_claim, "generated_sources": [], "table_version": 1, "origin": "human_confirmed"}
assert sov.append_basis_confirmation(str(root), "s1", rec)["verdict"] == "APPENDED"
UNK = {"family": "local", "source": "u0", "text": "窓が光った。", "sha": "w", "source_file": "f.jsonl", "line": 4}
GEN = dict(UNK, origin="generated")


def result(kind, verdict, src, **extra):
    return {"kind": kind, "verdict": verdict, "text": claim, "door": "chat", "sources": [src], "evidence": [src["text"]],
            "trace": [{"part": "p", "status": "ran"}], **extra}


for label, src in (("source with origin missing (unknown_origin)", UNK), ("source with origin generated", GEN)):
    for kind, verdict in (("answer", "ANSWER"), ("unknown", "UNKNOWN_X"), ("refusal", "UNKNOWN_Y")):
        out, rc = bp.apply_to_ask(result(kind, verdict, src), bp.AskPolicy(), query="窓は？", mode="legacy", documents=[])
        n = out["basis_policy"]
        print(json.dumps({"source": label, "original": f"{kind}/{verdict}", "rc": rc, "kind": out["kind"],
                          "verdict": out["verdict"], "outcome": n["outcome"], "basis": n["basis"],
                          "unknown_origin": n["counts"].get("unknown_origin"),
                          "text_is_the_record_claim": out["text"] == record_claim,
                          "confirmed_records_used": n["sovereign"]["confirmed_records_used"],
                          "confirmed_records_not_used": n["sovereign"]["confirmed_records_not_used"]}, ensure_ascii=False))
