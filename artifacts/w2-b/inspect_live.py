import json, sys, pathlib
d = pathlib.Path(sys.argv[1]); out = json.loads((d / "stdout.json").read_text())
rows = [json.loads(l) for l in (d / "ledger.jsonl").read_text().splitlines()]
rows = [x for x in rows if x["run_id"] == out["run_id"]]
assert [x["seq"] for x in rows] == sorted(x["seq"] for x in rows)
print("verdict", out["verdict"], "outcome", out.get("outcome"))
print("types", [x["type"] for x in rows])
for x in rows:
    t = x["type"]
    if t == "LAUNCH_PLANNED": print("impl argv0", x["argv"][0], x["model"]["value"], x["effort"]["value"])
    if t == "VERIFIER_LAUNCH_PLANNED": print("verifier argv", x["argv"][:1], x["argv"][-6:], "same_model", x.get("same_model_as_implementer"))
    if t == "AGENT_EXITED": print("impl exited", x.get("attempt"), x["runtime_terminal"], x["exit_code"], x["changed_paths"])
    if t == "ACCEPTANCE_COMMAND": print("acc", x.get("attempt"), x["status"], repr((x["stdout"] or "")[:40]))
    if t == "VERIFIER_EXITED": print("verifier exited", x.get("attempt"), x["runtime_terminal"], x["exit_code"], x["limit_text_seen"])
    if t == "VERDICT": print("verdict", x.get("attempt"), x["status"], x.get("result"), x["source"])
    if t == "VERIFIER_EVIDENCE": print("evidence", x.get("attempt"), x.get("conclusion"), x.get("argv"), repr((x.get("stdout") or "")[:40]))
    if t == "VERIFICATION_RESULT": print("result", x.get("attempt"), x["decision"], x.get("counts"))
    if t in ("CANDIDATE_COMMIT", "COMMIT"): print(t, x.get("sha"))
