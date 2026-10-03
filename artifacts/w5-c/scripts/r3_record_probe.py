"""W5-c round 3: what a recorded 'yes' (a consenting sovereign, the same question, a sentence that differs from the
result's own text) does to seven kinds of result. Usage: r3_record_probe.py WORKDIR; PYTHONPATH=<tree to measure>.
Run once on the base tree (git archive 6d20016) and once on the working tree; the outputs are put side by side."""
import json, os, sys
from pathlib import Path
import verantyx.basis_policy as bp
from verantyx import sovereign as sov

work = Path(sys.argv[1]); work.mkdir(parents=True, exist_ok=True)
root = work / "sov"
assert sov.create(str(root), "s1", "o", consent_promote=True)["verdict"] == "CREATED"
os.environ["VERA_SOVEREIGN_ROOT"], os.environ["VERA_SOVEREIGN_STORE"] = str(root), "s1"
RECORD = "人の答え。"
rec = {"record": "basis_confirmation", "status": "HUMAN_CONFIRMED", "witness": "user_confirmation", "confirm_id": "abc",
       "query": "窓は？", "claim": RECORD, "generated_sources": [], "table_version": 1, "origin": "human_confirmed"}
assert sov.append_basis_confirmation(str(root), "s1", rec)["verdict"] == "APPENDED"
GEN = {"family": "local", "source": "g0", "text": "窓が光った。", "sha": "w", "origin": "generated",
       "source_file": "f.jsonl", "line": 4}
DOC = {"family": "document", "sovereign": "document", "source": "memo.txt", "text": "窓が光った。"}


def result(kind, verdict, sources):
    return {"kind": kind, "verdict": verdict, "text": "窓が光ります。", "door": "chat", "sources": sources,
            "evidence": [s["text"] for s in sources], "trace": [{"part": "p", "status": "ran"}]}


CASES = [
    ("no source / answer/ANSWER", result("answer", "ANSWER", []), "legacy", []),
    ("no source / unknown/UNKNOWN_X", result("unknown", "UNKNOWN_X", []), "legacy", []),
    ("generated / answer/ANSWER", result("answer", "ANSWER", [GEN]), "legacy", []),
    ("generated / unknown/UNKNOWN_X", result("unknown", "UNKNOWN_X", [GEN]), "legacy", []),
    ("document, round5 with documents / answer/ANSWER", result("answer", "ANSWER", [DOC]), "round5", ["memo.txt"]),
    ("document, legacy / answer/ANSWER", result("answer", "ANSWER", [DOC]), "legacy", []),
    ("document, round5 without documents / answer/ANSWER", result("answer", "ANSWER", [DOC]), "round5", []),
]
for label, res, mode, docs in CASES:
    out, rc = bp.apply_to_ask(res, bp.AskPolicy(), query="窓は？", mode=mode, documents=docs)
    n = out["basis_policy"]
    sv = n.get("sovereign", {})
    print(json.dumps({"case": label, "rc": rc, "applied": n.get("applied"), "outcome": n.get("outcome"),
                      "kind": out["kind"], "verdict": out["verdict"], "basis": n.get("basis"),
                      "used": sv.get("confirmed_records_used"), "not_used": sv.get("confirmed_records_not_used"),
                      "text_is_the_record_claim": out.get("text") == RECORD,
                      "classify_version": n.get("classify_version")}, ensure_ascii=False))
