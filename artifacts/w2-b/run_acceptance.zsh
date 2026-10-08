#!/bin/zsh
# W2-b acceptance script: runs every acceptance command of the ticket (B7 only inspects the saved live output; it starts nothing).
W=/Users/motonisihikoudai/Projects/vera-impl/wt/W2-b-S
PY=/Users/motonisihikoudai/vera-wiring/env/bin/python
export PYTHONPATH=$W PYTHONDONTWRITEBYTECODE=1
A=$W/artifacts/w2-b
# a trap so that a stray real codex / claude cannot start from this shell (outside the work tree, never deleted)
GUARD=/private/tmp/claude-501/-Users-motonisihikoudai-Projects-Verantyx-Vera-alpha/516c6003-3687-4f5e-a07a-ae6b080c15b8/scratchpad/W2-b/impl-r3/guardbin
mkdir -p $GUARD; for n in codex claude; do printf '#!/bin/sh\necho "GUARD: real %s was about to start" >&2\nexit 97\n' $n > $GUARD/$n; chmod 755 $GUARD/$n; done
export PATH=$GUARD:$PATH
cd $W
echo '----- module origin'
$PY - <<'PYEOF'
import sys, os, verantyx, verantyx.conductor_run, verantyx.agent_runtime, verantyx.agent_adapter, verantyx.project_frame, verantyx.verifier_agents, verantyx.cli
W = os.environ["PYTHONPATH"]
bad = [m.__file__ for n, m in sys.modules.items() if n.split(".")[0] == "verantyx" and getattr(m, "__file__", None) and not os.path.realpath(m.__file__).startswith(os.path.realpath(W) + "/")]
print("outside:", bad)
PYEOF
echo '----- frames'
$PY - <<'PYEOF'
import tempfile
from pathlib import Path
from verantyx import project_frame as pf
for name in ("greet", "sum_args", "mul_args_trap"):
    f = pf.load_conduct_frame(f"docs/frames/toy/{name}.md")
    comp = pf.compile_frame(f.spec, Path(tempfile.mkdtemp()) / "m.jsonl")
    print(name, pf.check_conduct_ready(f), f.machine_criteria, f.write_allowlist, {k: v for k, v in f.agent_settings.items() if k.startswith("verif")}, len(comp.records))
PYEOF
for b in b1 b2 b3 b4 b5 b6; do
  echo "----- $b"
  $PY -m pytest -p no:cacheprovider -q -rA tests/test_conduct_verify*.py -k "${b}_" 2>&1 | tail -14
done
echo '----- B4 help'
$PY -m verantyx.cli conduct --help | grep -E -- "--verifier-adapter|--verifier-model|--verifier-effort|--verifier-timeout-seconds|--verification-retries"
echo '----- B5 leftovers'
ps -axo pid,pgid,command | grep -E 'sleep 300|sleep 60|verify-' | grep -v grep; echo "(empty above = no process left)"
echo '----- B7 saved live output (nothing is started)'
LIVE=$A/live; ls $LIVE; cat $LIVE/launches.txt $LIVE/launch_count.txt
for d in $LIVE/*/; do [ -f $d/stdout.json ] || continue; echo "== $d"; cat $d/exit.txt; $PY $A/inspect_live.py $d
  cmp $d/refs_before.txt $d/refs_after.txt && cmp $d/head_before.txt $d/head_after.txt && echo REPO_REFS_UNCHANGED; done
echo '----- B8'
$PY -m pytest -p no:cacheprovider -q tests/test_conduct_run*.py tests/test_conduct_entry*.py 2>&1 | tail -1
$PY -m pytest -p no:cacheprovider -q tests/test_verifier_agents.py tests/attack/test_verifier_agents_*.py 2>&1 | tail -6
echo '----- B8: the new tests, 3 runs in a row'
for i in 1 2 3; do $PY -m pytest -p no:cacheprovider -q tests/test_conduct_verify*.py 2>&1 | tail -1; done
echo '----- B8: the conductor-side race (a late process check; the reviewer probe; passes only with the fix)'
REVIEW_RACE=1 PYTHONPATH=$W:$A/r4 $PY -m pytest -q -p no:cacheprovider -p race_after_read tests/test_conduct_run.py -k test_r2_prose 2>&1 | tail -2
echo '----- B8: the full suite on committed clones (round 4: r4/; order base, cand, cand, base)'
R=$A/r4
cat $R/timing_summary.txt
echo '(attempts and loads)'; cat $R/attempts.txt; cat $R/pair_progress.txt
echo "new failures (cand1 - base1):"; comm -13 $R/base1_failures.txt $R/cand1_failures.txt; echo "(empty above = none)"
echo "new failures (cand2 - base2):"; comm -13 $R/base2_failures.txt $R/cand2_failures.txt; echo "(empty above = none)"
echo "fixed (base1 - cand1):"; comm -23 $R/base1_failures.txt $R/cand1_failures.txt
cmp $R/base1_failures.txt $A/before1_failures.txt && echo "BASE_FAILURES_SAME_AS_ROUND1_BEFORE (124)"
echo '----- mutation results (round 4, committed clone; m13 is an equivalent mutant, see the report)'
cut -c1-150 $A/mutation_results.r4.txt
echo '----- code hash (16 non-artifact files; the plan expects ecaf4691...)'; git -C $W status --porcelain=v1 --untracked-files=all | awk '{print $2}' | grep -v '^artifacts/' | LC_ALL=C sort | (cd $W && xargs shasum -a 256) | shasum -a 256
echo '----- scope'
git -C $W status --porcelain=v1 --untracked-files=all | awk '{print $2}' | grep -vE '^(verantyx/(conductor_run|verifier_agents|agent_adapter|agent_runtime|cli|project_frame)\.py|docs/frames/|docs/CONDUCT_(RUN|VERIFY)\.md|tests/test_conduct_verify[^/]*\.py|artifacts/w2-b/)'; echo "(empty above = inside the allowed paths)"
git -C $W diff --stat
git -C $W diff --quiet -- verantyx/conductor.py verantyx/conductor_escalate.py verantyx/conductor_vocab.py verantyx/llm_choice.py tests/test_conduct_run.py tests/test_conduct_run_policy.py tests/test_conduct_run_settings.py tests/test_conduct_run_support.py tests/test_verifier_agents.py tests/attack docs/frames/examples docs/frames/vera_project_frame.md && echo UNTOUCHED_OK
ls $W/verantyx/conduct_ask.py 2>/dev/null; echo "(conduct_ask.py must not exist)"
diff <(git -C $W show dev:verantyx/conductor_run.py | head -896) <(head -896 $W/verantyx/conductor_run.py) && echo FROZEN_LINES_1_896_IDENTICAL
grep -nE "pytest\.skip|mark\.(skip|skipif|xfail)|xfail|importorskip" $W/tests/test_conduct_verify*.py; echo "(empty above = no pytest skip / xfail in the new tests)"
# (guardbin cleanup is done by hand with named "rm" calls; this script never deletes anything)
