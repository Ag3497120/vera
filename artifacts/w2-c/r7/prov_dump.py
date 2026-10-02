# pytest -p prov_dump : per conduct_ask call, the provenance keys of the output (resolver, derivation, basis ids, trace)
import json, os
import verantyx.conduct_ask as ca
_orig = ca._answer_question
def _wrapped(frame_path, question, options=None, **kw):
    r = _orig(frame_path, question, options, **kw)
    ok = None
    if str(frame_path).endswith(".md") and r.get("decision") == "answer":
        try:
            lines = open(frame_path, encoding="utf-8").read().splitlines()
            ok = all(0 < b["line"] <= len(lines) and b["text"] in lines[b["line"] - 1] for b in r["basis"])
        except OSError:
            ok = None
    with open(os.environ["PROV_LOG"], "a", encoding="utf-8") as f:
        f.write(json.dumps({"source": "tests", "test": os.environ.get("PYTEST_CURRENT_TEST", "").split(" ")[0],
                            "decision": r.get("decision"), "resolver": r.get("resolver"), "derivation": r.get("derivation"),
                            "basis_ids": [b["id"] for b in r.get("basis") or []],
                            "trace_answer": sorted(k for k, v in (r.get("trace") or {}).get("resolver_outcomes", {}).items() if v == "ANSWER"),
                            "basis_line_ok": ok}, ensure_ascii=False) + "\n")
    return r
ca._answer_question = _wrapped
