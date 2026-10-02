#!/bin/zsh
# Runs section 4 of the plan (E1-E6 and the scope check) and prints everything. Output: acceptance_run.txt
W=/Users/motonisihikoudai/Projects/vera-impl/wt/W1-d-S
PY=/Users/motonisihikoudai/vera-wiring/env/bin/python
export PYTHONPATH=$W PYTHONDONTWRITEBYTECODE=1
T=$(mktemp -d); git -C $T init -q && git -C $T -c user.email=t@t -c user.name=t commit -q --allow-empty -m init
cd $W
echo '----- module origin (all must be under W)'
$PY - <<'PYEOF'
import importlib, os, sys
W = os.path.realpath(os.environ["PYTHONPATH"])
for m in ["verantyx", "verantyx.cli", "verantyx.project_frame", "verantyx.agent_adapter",
          "verantyx.agent_runtime", "verantyx.conductor_run", "verantyx.vera_system"]:
    importlib.import_module(m)
bad = [(n, v.__file__) for n, v in sys.modules.items()
       if n.startswith("verantyx") and getattr(v, "__file__", None)
       and not os.path.realpath(v.__file__).startswith(W + os.sep)]
print("outside:", bad)
PYEOF
echo '----- E1'
$PY -m verantyx.cli conduct --frame $W/docs/frames/vera_project_frame.md --repo $T --adapter fake | cut -c1-200; echo "exit=${pipestatus[1]}"
echo -n "AGENT_START_RETURNED count: "; grep -c '"type":"AGENT_START_RETURNED"' $T/.verantyx-conduct/ledger.jsonl
grep '"type":"FRAME_COMPILED"' $T/.verantyx-conduct/ledger.jsonl | $PY -c "import sys,json; d=json.loads(sys.stdin.readline()); print('FRAME_COMPILED record_count=%d kinds=%s' % (d['record_count'], d['kinds']))"
$PY - <<PYEOF
import json, collections
rows = json.load(open("$W/artifacts/w1-d/compile_after.json"))
print("compile_after.json  record_count=%d kinds=%s" % (len(rows), dict(sorted(collections.Counter(r['kind'] for r in rows).items()))))
PYEOF
echo '----- E2'
$PY -m verantyx.cli conduct --frame $W/docs/frames/vera_project_frame.md --repo $T --adapter codex --dry-run --model gpt-6-luna --effort high | cut -c1-120; echo "exit=${pipestatus[1]}"
$PY -m verantyx.cli conduct --frame $W/docs/frames/vera_project_frame.md --repo $T --adapter claude --dry-run --model claude-sonnet-5-5 --effort high | cut -c1-120; echo "exit=${pipestatus[1]}"
grep '"type":"LAUNCH_PLANNED"' $T/.verantyx-conduct/ledger.jsonl | $PY -c "import sys,json; [print(json.loads(l)['argv'], json.loads(l)['stdin']['mode']) for l in sys.stdin]"
$PY -m verantyx.cli conduct --frame $W/docs/frames/vera_project_frame.md --repo $T --adapter codex --dry-run | $PY -c "import sys,json; d=json.load(sys.stdin); print(d['verdict'], d['refusal']['reason'])"; echo "exit=${pipestatus[1]} (AGENT_SETTING_MISSING expected)"
echo "worktree list:"; git -C $T worktree list
echo '----- E3'
printf '[goal]\nproject: X\n' > $T/broken.md
printf 'hello\nworld\n' > $T/plain.txt
sed '/^\[write_allowlist\]/,$d' $W/docs/frames/vera_project_frame.md > $T/no_allow.md
grep -v '^C6:' $W/docs/frames/vera_project_frame.md > $T/human_only.md
for f in $T/no_allow.md $T/human_only.md $T/broken.md $T/plain.txt $T/missing.md; do
  $PY -m verantyx.cli conduct --frame $f --repo $T --adapter fake 2>$T/err.txt | $PY -c "import sys,json; d=json.load(sys.stdin); print(d['verdict'], d['refusal']['reason'], '|', d['refusal']['missing'][:110])"
  echo -n "Traceback count: "; grep -c Traceback $T/err.txt
done
echo '----- E4'
ls $W/docs/frames/examples/*.md | wc -l
for f in $W/docs/frames/vera_project_frame.md $W/docs/frames/examples/*.md; do $PY $W/tools/frame_compile.py "$f" > /dev/null && echo "OK $f" || echo "NG $f"; done
cmp $W/artifacts/w1-d/compile_before.json $W/artifacts/w1-d/compile_after_original_text.json && echo BYTE_IDENTICAL
$PY $W/artifacts/w1-d/compile_snapshot.py --compare-subsequence $W/artifacts/w1-d/compile_before.json $W/artifacts/w1-d/compile_after.json --added-criteria C6 | tee $W/artifacts/w1-d/compile_compare.txt
echo '-- control: the comparison must fail when an old record is altered' | tee -a $W/artifacts/w1-d/compile_compare.txt
$PY - <<PYEOF
import json
rows = json.load(open("$W/artifacts/w1-d/compile_after.json"))
rows[3]["slots"]["subject"] = rows[3]["slots"]["subject"] + " X"
json.dump(rows, open("$T/altered.json", "w"))
PYEOF
$PY $W/artifacts/w1-d/compile_snapshot.py --compare-subsequence $W/artifacts/w1-d/compile_before.json $T/altered.json --added-criteria C6 | cut -c1-160 | tee -a $W/artifacts/w1-d/compile_compare.txt
$PY -m pytest -p no:cacheprovider -q $W/tests/test_conduct_entry*.py -k "frame or dsl or precedence or forbidden or allowlist" 2>&1 | tail -3
echo '----- E5'
$PY $W/tools/demo_conduct.py; env -u PYTHONPATH PYTHONDONTWRITEBYTECODE=1 $PY $W/tools/demo_conduct.py; $PY $W/tools/demo_driver.py; $PY $W/tools/demo_runtime.py
(cd /tmp && env -u PYTHONPATH PYTHONDONTWRITEBYTECODE=1 $PY $W/tools/demo_conduct.py)
echo "leftover .demo-* in W: $(print -l $W/.demo-*(N) | grep -c .)"
echo '----- new conduct tests'
$PY -m pytest -p no:cacheprovider -q $W/tests/test_conduct_entry*.py 2>&1 | tail -3
echo '----- scope check'
git -C $W status --porcelain=v1 --untracked-files=all | cut -c4- | grep -v -E '^(verantyx/(cli|project_frame|agent_adapter|agent_runtime|vera_system|conductor_run)\.py|tools/(run_project|frame_compile|demo_conduct)\.py|docs/frames/|docs/CONDUCT_ENTRY\.md|tests/test_conduct_entry[^/]*\.py|artifacts/w1-d/)' ; echo "(nothing above = OK)"
git -C $W diff --stat -- verantyx/conductor.py verantyx/conductor_vocab.py verantyx/verifier_agents.py verantyx/semantic_unknown_choice.py tools/demo_runtime.py; echo "(nothing above = untouched)"
echo -n "deleted lines in conductor_run.py: "; git -C $W diff -U0 -- verantyx/conductor_run.py | grep -c -E '^-[^-]'
echo -n "deleted lines in vera_project_frame.md: "; git -C $W diff -U0 -- docs/frames/vera_project_frame.md | grep -c -E '^-[^-]'
echo -n "deleted lines in agent_adapter.py: "; git -C $W diff -U0 -- verantyx/agent_adapter.py | grep -c -E '^-[^-]'
