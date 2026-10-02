import subprocess, sys, pathlib, os, json
C = pathlib.Path(sys.argv[1]); PY = sys.argv[2]
def edit(rel, old, new, count=1):
    p = C / rel; s = p.read_text(encoding="utf-8"); assert old in s, (rel, old[:60]); p.write_text(s.replace(old, new, count), encoding="utf-8")
def reset(): subprocess.run(["git", "-C", str(C), "checkout", "-q", "--", "."], check=True)
M = {
 "m1 finding confirmed without the re-run result": (lambda: edit("verantyx/conductor_run.py", '{"FAIL": "CONFIRMED", "PASS": "NOT_REPRODUCED"}.get(status, "UNVERIFIED")', '"CONFIRMED"'), "b3_ii or b2"),
 "m2 pass check matched without the re-run result": (lambda: edit("verantyx/conductor_run.py", '{"PASS": "MATCHED", "FAIL": "CONTRADICTED"}.get(status, "UNVERIFIED")', '"MATCHED"'), "b3_iii"),
 "m3 finding without a check counted as valid": (lambda: edit("verantyx/conductor_run.py", '"confirmed": count("finding", "CONFIRMED"),', '"confirmed": count("finding", "CONFIRMED") + count("finding", "NO_EVIDENCE"),'), "b3_i or b3_ii"),
 "m4 implementer last message put into the verifier brief": (lambda: (edit("verantyx/verifier_agents.py", 'BRIEF_PAYLOAD_KEYS = ("task",', 'BRIEF_PAYLOAD_KEYS = ("implementer_output", "task",'), edit("verantyx/conductor_run.py", 'payload = {"task": task_id,', 'payload = {"implementer_output": last.decode("utf-8", "replace") + output.decode("utf-8", "replace"), "task": task_id,')), "b6"),
 "m5 verifier runtime given the implementer's allowlist and the conductor's before/after comparison removed": (lambda: (edit("verantyx/conductor_run.py", "                worktree, (), backend=VERIFIER_BACKENDS[vadapter]", "                worktree, tuple(allowlist), backend=VERIFIER_BACKENDS[vadapter]"), edit("verantyx/conductor_run.py", "                timeout_seconds=vtimeout, output_limit=runtime.output_limit, poll_interval=runtime.poll_interval,\n                read_only=True)", "                timeout_seconds=vtimeout, output_limit=runtime.output_limit, poll_interval=runtime.poll_interval)"), edit("verantyx/conductor_run.py", 'impl_changed = impl_after != impl_before', 'impl_changed = False'), edit("verantyx/conductor_run.py", 'repo_changed_now = any(repo_after[name] != repo_before.get(name) for name in ("refs", "head", "symbolic_head", "status"))', 'repo_changed_now = False')), "b5_a or b5_each"),
 "m6 cmd_conduct does not require verification": (lambda: edit("verantyx/cli.py", "verification_retries=args.verification_retries, require_verification=True)", "verification_retries=args.verification_retries, require_verification=False)"), "b4_b"),
 "m7 default retries 1": (lambda: edit("verantyx/conductor_run.py", "DEFAULT_VERIFICATION_RETRIES = 2", "DEFAULT_VERIFICATION_RETRIES = 1"), "b2_always_hardcoded"),
 "m8 first of several verdict lines taken": (lambda: edit("verantyx/verifier_agents.py", "    if len(starts) > 1:\n        return VerdictExtraction(\"MULTIPLE_VERDICTS\", other_nonce_lines=other, verdict_lines=len(starts))\n", "    if False:\n        pass\n"), "two_verdict or verdict_lines"),
 "m9 verifier wait without process check": (lambda: edit("verantyx/conductor_run.py", 'put("VERIFIER_PROCESS_CHECK", **_process_check(vhandle), **extra)', 'pass'), "b5_each"),
 "m11 retry brief stacks the earlier findings (round-1 review r9)": (lambda: edit("verantyx/conductor_run.py", "        retry_brief = brief + section\n", "        retry_brief = current_brief + section\n"), "b2"),
 "m12 retry brief cut to the limit instead of stopping": (lambda: edit("verantyx/conductor_run.py", "        retry_brief = brief + section\n        if len(retry_brief) > agent_adapter.MAX_BRIEF_CHARS:", "        retry_brief = (brief + section)[:agent_adapter.MAX_BRIEF_CHARS]\n        if False:"), "retry_brief"),
 "m13 re-run of a verifier copy shares one copy (no fresh copy per command)": (lambda: edit("verantyx/conductor_run.py", 'copy_dir=vdir / f"rerun-{number}"', 'copy_dir=vdir / "rerun-1"'), "b3 or b1"),
 "m10 sandbox self-check failure ignored for re-runs": (lambda: edit("verantyx/conductor_run.py", 'sandbox_ok = bool(check_row.get("ok"))', 'sandbox_ok = True'), "sandbox_is_never_skipped"),
 "s1 supervisor: old behaviour (break at the first poll)": (lambda: edit("verantyx/agent_runtime.py", "            if drained_once:\n                break\n", "            break\n"), "supervisor"),
 "s2 supervisor: never break on poll (wait for EOF)": (lambda: edit("verantyx/agent_runtime.py", "            if drained_once:\n                break\n", "            if False:\n                break\n"), "supervisor"),
 "s3 supervisor: drain pass that does not read (sleep instead)": (lambda: edit("verantyx/agent_runtime.py", "            drained_once = True\n", "            time.sleep(0.1); break\n"), "supervisor"),
}
only = sys.argv[3:] 
results = []
for name, (apply, k) in M.items():
    if only and not any(name.startswith(o) for o in only): continue
    reset(); apply()
    env = {**os.environ, "PYTHONPATH": str(C), "PYTHONDONTWRITEBYTECODE": "1"}
    done = subprocess.run([PY, "-m", "pytest", "-p", "no:cacheprovider", "-q", "-x" if False else "-q", "tests/test_conduct_verify.py", "tests/test_conduct_verify_parse.py", "tests/test_conduct_verify_settings.py", "tests/test_conduct_verify_supervisor.py", "-k", " or ".join(k.split(" or ")) if False else k.replace(" or ", " or ")], cwd=C, capture_output=True, text=True, env=env)
    tail = [l for l in done.stdout.splitlines() if l.startswith(("FAILED", "ERROR")) or " passed" in l or " failed" in l]
    line = f"{name}: {'CAUGHT' if done.returncode != 0 else 'NOT CAUGHT'}  (-k {k!r}) | " + " | ".join(tail[-4:])
    print(line, flush=True); results.append(line)
reset()
