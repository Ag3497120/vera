#!/bin/zsh
# W2-a acceptance criteria in one script (R5 only inspects the saved live run; it launches nothing).
W=/Users/motonisihikoudai/Projects/vera-impl/wt/W2-a-S
PY=/Users/motonisihikoudai/vera-wiring/env/bin/python
export PYTHONPATH=$W PYTHONDONTWRITEBYTECODE=1
A=$W/artifacts/w2-a
# a trap so a hand-run shell can never start a real codex / claude by mistake
mkdir -p $A/guardbin
for n in codex claude; do
  printf '#!/bin/sh\necho "GUARD: real %s was about to start: $*" >&2\necho "%s $*" >> %s/guardbin/STARTED\nexit 97\n' $n $n $A > $A/guardbin/$n
  chmod 755 $A/guardbin/$n
done
export PATH=$A/guardbin:$PATH
cd $W

echo '----- modules come from this tree'
$PY - <<'PYEOF'
import sys, os, verantyx, verantyx.conductor_run, verantyx.agent_runtime, verantyx.agent_adapter, verantyx.project_frame, verantyx.cli
W = os.environ["PYTHONPATH"]
bad = [m.__file__ for n, m in sys.modules.items() if n.split(".")[0] == "verantyx" and getattr(m, "__file__", None) and not os.path.realpath(m.__file__).startswith(os.path.realpath(W) + "/")]
print("outside:", bad)
PYEOF

echo '----- R1'
$PY -m pytest -p no:cacheprovider -q -rA tests/test_conduct_run.py -k "r1_" 2>&1 | tail -5
echo '----- R2'
$PY -m pytest -p no:cacheprovider -q -rA tests/test_conduct_run.py -k "r2_" 2>&1 | tail -30
$PY - <<'PYEOF'
import sys; sys.path.insert(0, "tests")
import test_conduct_run as t
print({k: v[3] for k, v in t.SCENARIOS.items()}); print("distinct:", len({v[3] for v in t.SCENARIOS.values()}))
PYEOF
echo '----- R3'
$PY -m pytest -p no:cacheprovider -q -rA tests/test_conduct_run_policy.py -k "r3_" 2>&1 | tail -12
echo '----- R4'
$PY -m pytest -p no:cacheprovider -q -rA tests/test_conduct_run_policy.py tests/test_conduct_run.py -k "r4_" 2>&1 | tail -8
echo '----- R5 (inspect the saved live run; nothing is started)'
LIVE=$A/live; ls $LIVE; cat $LIVE/launches.txt
for r in $LIVE/run1 $LIVE/run2; do [ -d $r ] || continue; echo "== $r"; cat $r/exit.txt; $PY - $r <<'PYEOF'
import json, sys, pathlib
r = pathlib.Path(sys.argv[1]); out = json.loads((r / "stdout.json").read_text())
rows = [json.loads(l) for l in (r / "ledger.jsonl").read_text().splitlines()]
rows = [x for x in rows if x["run_id"] == out["run_id"]]
print("verdict", out["verdict"], "outcome", out.get("outcome"))
print("types", [x["type"] for x in rows])
plan = [x for x in rows if x["type"] == "LAUNCH_PLANNED"][0]; print("argv0", plan["argv"][0], "model", plan["model"], "effort", plan["effort"])
ex = [x for x in rows if x["type"] == "AGENT_EXITED"][0]; print("exited", ex["runtime_terminal"], ex["exit_code"], ex["elapsed_seconds"], ex["changed_paths"], ex["limit_text_seen"])
for c in (x for x in rows if x["type"] == "ACCEPTANCE_COMMAND"): print("acc", c["status"], c["argv"][:3], c["exit_code"], repr(c["stdout"][:80]))
print("commit", [x.get("sha") for x in rows if x["type"] == "COMMIT"], "check", [x["group_alive"] for x in rows if x["type"] == "AGENT_PROCESS_CHECK"])
PYEOF
cmp $r/refs_before.txt $r/refs_after.txt && cmp $r/head_before.txt $r/head_after.txt && echo REPO_REFS_UNCHANGED; done
echo '----- R6'
$PY -m pytest -p no:cacheprovider -q -rA tests/test_conduct_run_settings.py -k "r6_" 2>&1 | tail -8
( cd $(mktemp -d) && git init -q r && git -C r -c user.email=t@t -c user.name=t commit -q --allow-empty -m i && \
  $PY -m verantyx.cli conduct --frame $W/docs/frames/vera_project_frame.md --repo r --adapter claude --dry-run \
    --model claude-sonnet-5-5 --effort low --permission-mode acceptEdits --allowed-tools Edit,Write | \
  $PY -c "import json,sys; o=json.load(sys.stdin); rows=[json.loads(l) for l in open(o['ledger'])]; print([x['argv'] for x in rows if x['type']=='LAUNCH_PLANNED'][0])" )
echo '----- R7 (W1-d tests; the full-suite comparison is in before*/after* files)'
$PY -m pytest -p no:cacheprovider -q tests/test_conduct_entry*.py 2>&1 | tail -1
wc -l $A/new_failures.txt; grep -h " in [0-9.]*s" $A/before?_pytest.txt $A/after?_pytest.txt
echo '----- scope'
git -C $W status --porcelain=v1 --untracked-files=all | awk '{print $2}' | \
  grep -vE '^(verantyx/(conductor_run|agent_runtime|agent_adapter|cli|vera_system|project_frame)\.py|tools/run_project\.py|docs/frames/|docs/CONDUCT_(ENTRY|RUN)\.md|tests/test_conduct_run[^/]*\.py|artifacts/w2-a/)' ; echo "(empty above = in scope)"
git -C $W diff --stat
echo '----- the trap was never started'
[ -e $A/guardbin/STARTED ] && cat $A/guardbin/STARTED || echo "no trap mark"
rm -rf $A/guardbin
