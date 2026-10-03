#!/bin/sh
# W2-g2: every acceptance check of the ticket in one run.  Output: artifacts/w2-g/g2/final_run_g2.log (this script writes only into
# artifacts/w2-g/g2/ and artifacts/w2-g/g2/final/; nothing of rounds 1-3 and no live ledger is touched; no real provider is started).
cd /Users/motonisihikoudai/Projects/vera-impl/wt/W2-g-S || exit 1
mkdir -p artifacts/w2-g/g2/final
PY=artifacts/w2-g/py.sh
say() { echo; echo "=== $*"; }
say "origin of the imported modules (expected: outside [])"
$PY -c "import sys,os,verantyx.conduct_ask,verantyx.conduct_map,verantyx.llm_choice;r=os.getcwd();m=[x for x in sys.modules if x.startswith('verantyx')];print('verantyx modules',len(m),'outside',[x for x in m if getattr(sys.modules[x],'__file__',None) and not os.path.abspath(sys.modules[x].__file__).startswith(r)])"
say "paths outside the permitted ones (expected: no output)"
git status --porcelain --untracked-files=all | grep -vE '^( M (verantyx/(conduct_ask|conduct_map|llm_choice)\.py|docs/CONDUCT_ASK\.md|tests/test_conduct_map[^/]*\.py|tests/conduct_ask/(w2g/run_map_bank\.py|map_helpers\.py))|\?\? (tests/test_conduct_map[^/]*\.py|tests/conduct_ask/w2g3/|artifacts/w2-g/))'
say "tracked files of artifacts/w2-g modified (expected: no output)"
git status --porcelain -- artifacts/w2-g | grep -v '^?? '
say "protected paths diff against eb5b2e1 (expected: no output)"
git diff --stat eb5b2e1 -- verantyx/cli.py verantyx/conductor.py verantyx/conductor_run.py tests/conduct_ask/run_bank.py tests/conduct_ask/ca_helpers.py tests/conduct_ask/fixtures tests/conduct_ask/w2g/items.jsonl tests/conduct_ask/w2g/frames tests/conduct_ask/w2g2 tools
say "llm_choice.py deleted lines against dev and against eb5b2e1 (expected: 0 and 0)"
git diff dev -- verantyx/llm_choice.py | grep -c '^-[^-]'; git diff eb5b2e1 -- verantyx/llm_choice.py | grep -c '^-[^-]'
say "no bytecode or cache files (expected: no output)"
find . -path ./.git -prune -o \( -name __pycache__ -o -name '*.pyc' -o -name .pytest_cache \) -print | head
say "G1 G2 G5 G9: the conduct_map tests and the llm_choice tests"
$PY -m pytest -p no:cacheprovider -q tests/test_conduct_map_*.py tests/test_llm_choice.py 2>&1 | tail -3
$PY -m pytest -p no:cacheprovider -v tests/test_conduct_map_g9.py tests/test_conduct_map_reply2.py > artifacts/w2-g/g2/final/g9_tests.txt 2>&1; tail -1 artifacts/w2-g/g2/final/g9_tests.txt
say "'or True' (expected 0)"
grep -n 'or True' tests/test_conduct_map*.py | wc -l
say "skip / xfail marks (expected: the one of test_conduct_map_live.py)"
grep -nE 'pytest\.mark\.(skip|xfail)|pytest\.(skip|xfail)\(' tests/test_conduct_map*.py
say "number of test functions per migrated file, before -> after (expected: after >= before)"
for f in tests/test_conduct_map_{bank,cli,g1,g2,g5,live,order,reply,unit}.py; do echo "$f $(git show eb5b2e1:$f | grep -c 'def test_') -> $(grep -c 'def test_' $f)"; done
say "removed test lines against eb5b2e1 (all explained in the report's migration table)"
git diff eb5b2e1 -- tests/test_conduct_map_*.py tests/conduct_ask/map_helpers.py | grep -E '^-' | grep -vE '^---' > artifacts/w2-g/g2/final/removed_test_lines.txt; wc -l < artifacts/w2-g/g2/final/removed_test_lines.txt; cmp artifacts/w2-g/g2/removed_test_lines.txt artifacts/w2-g/g2/final/removed_test_lines.txt && echo "same as the saved list"
say "G4: the 161 questions of W2-c with off and fake (expected: diff 0 / diff 0)"
for m in off fake; do $PY tests/conduct_ask/run_bank.py --items tests/conduct_ask/fixtures/items.jsonl --frames tests/conduct_ask/fixtures/frames --vocab-llm $m --split all --out artifacts/w2-g/g2/final/g4_after_$m > /dev/null; done
$PY -c "
import json
def load(p): return {json.loads(l)['id']: json.loads(l) for l in open(p, encoding='utf-8')}
def sig(r): o=r['observed']; return (o['decision'],o['answer_option_index'],o['answer'],o['reason'],o['detail'])
for m in ('off','fake'):
    a=load(f'artifacts/w2-c/bank/{m}/results.jsonl'); b=load(f'artifacts/w2-g/g2/final/g4_after_{m}/results.jsonl')
    d=[i for i in a if i not in b or sig(a[i])!=sig(b[i])]; print(m,'n',len(a),len(b),'diff',len(d),d[:5])"
say "G4: the calls of the existing tests against the start (expected: no change of off / scripted calls)"
[ -e artifacts/w2-g/g2/calls_final.jsonl ] || sh artifacts/w2-g/g2/dump_calls_g2.sh final
$PY artifacts/w2-g/g2/compare_calls_g2.py final
say "G4: real agent questions with off (expected: same)"
env -i HOME="$HOME" PATH=/usr/bin:/bin PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=$PWD PYTHONIOENCODING=utf-8 LANG=en_US.UTF-8 VERA_REAL_QUESTIONS=/Users/motonisihikoudai/vera-wiring/data/real_agent_questions.jsonl /Users/motonisihikoudai/vera-wiring/env/bin/python tools/real_questions_eval.py --conduct-ask --out artifacts/w2-g/g2/final/real_questions_off > /dev/null 2>&1; diff -q artifacts/w2-c/real_questions/results.jsonl artifacts/w2-g/g2/final/real_questions_off/results.jsonl && echo same
say "G4: off does not import conduct_map (expected: False)"
$PY -c "import sys,verantyx.conduct_ask as c;c.answer_question('tests/conduct_ask/fixtures/frames/f01_loan.md','保存形式はどれにしますか？',['CSV','SQLite']);print('conduct_map' in ' '.join(sys.modules))"
say "G6: the whole test suite against the baseline (expected: no new failure)"
sh artifacts/w2-g/g2/full_pytest_g2.sh final
comm -13 artifacts/w2-g/g2/baseline_failures.txt artifacts/w2-g/g2/final_failures.txt
tail -1 artifacts/w2-g/g2/final_pytest.txt
grep -A6 'environment classification of skips' artifacts/w2-g/g2/final_pytest.txt
say "G6: the guard (expected: all pass, no process start recorded)"
[ -e artifacts/w2-g/g2/guard_log.jsonl ] && echo "(guard_log.jsonl of the earlier run is kept: $(wc -l < artifacts/w2-g/g2/guard_log.jsonl) lines)" || echo "no guard log"
sh artifacts/w2-g/g2/guard_run_g2.sh 2>&1 | tail -4
say "G7: round 1-3 numbers (expected: MISSING lines: 0)"
$PY artifacts/w2-g/docs_check.py g3_w2g2/off live/w2g2/codex_codex live/w2g2/codex_claude live/w2g2/codex_codex_r3_order live/w2g2/codex_codex_r3b_order live/calib_r3/run1 live/w2g2/codex_claude_r3b_order g3/off:short live/codex_codex_r2:short live/codex_claude:short live/w2g1_rerun/codex_codex_subset:short | tail -1
say "G7: section 14 numbers (expected: MISSING lines: 0)"
$PY artifacts/w2-g/g2/docs_check_g2.py | tail -1
say "G7: --recount of the saved runs of rounds 1-3 (expected: all MATCH)"
for d in live/codex_codex live/codex_codex_r2 live/codex_claude live/smoke/run1; do $PY tests/conduct_ask/w2g/run_map_bank.py --recount artifacts/w2-g/$d | cut -c1-120; done
for d in live/w2g2/codex_codex live/w2g2/codex_claude live/w2g2/codex_codex_r3_order live/w2g2/codex_codex_r3b_order live/w2g2/codex_claude_r3b_order; do $PY tests/conduct_ask/w2g/run_map_bank.py --items tests/conduct_ask/w2g2/items.jsonl --frames tests/conduct_ask/w2g2/frames --recount artifacts/w2-g/$d | cut -c1-120; done
say "freeze: data, code and runner against the frozen sha256 (expected 0 and 0)"
grep -E '^[0-9a-f]{64} ' artifacts/w2-g/fixtures_freeze3.txt | shasum -a 256 -c - | grep -vc ': OK$'
grep -E '^[0-9a-f]{64} ' artifacts/w2-g/g2/freeze_code.txt | shasum -a 256 -c - | grep -vc ': OK$'
say "freeze: distinct lines of the sha files taken around the real runs (expected 4) and each equal to the frozen line (expected: no output)"
cat artifacts/w2-g/g2/sha_run_*.txt | sort -u | wc -l
cat artifacts/w2-g/g2/sha_run_*.txt | sort -u | while read h f; do grep -q "^$h  $f$" artifacts/w2-g/g2/freeze_code.txt || echo "DIFF $f"; done
say "G3' G8: --recount of the real runs (expected: all MATCH)"
for d in live_g2/w2g3/low live_g2/w2g3/xhigh; do $PY tests/conduct_ask/w2g/run_map_bank.py --items tests/conduct_ask/w2g3/items.jsonl --frames tests/conduct_ask/w2g3/frames --recount artifacts/w2-g/$d | cut -c1-140; done
for d in live_g2/w2g2/low_answer live_g2/w2g2/low_escalate; do [ -d artifacts/w2-g/$d ] && $PY tests/conduct_ask/w2g/run_map_bank.py --items tests/conduct_ask/w2g2/items.jsonl --frames tests/conduct_ask/w2g2/frames --recount artifacts/w2-g/$d | cut -c1-140; done
for d in off fake_oracle; do $PY tests/conduct_ask/w2g/run_map_bank.py --items tests/conduct_ask/w2g3/items.jsonl --frames tests/conduct_ask/w2g3/frames --recount artifacts/w2-g/g2/g3_w2g3/$d | cut -c1-140; done
say "G3' G8: the numbers (wrong <= 5% of 60; invalid rate below 26/296 = 0.0878 at effort low)"
$PY -c "
import json
for d in ('low','xhigh'):
    s=json.load(open(f'artifacts/w2-g/live_g2/w2g3/{d}/summary.json'))
    print(d,'total',s['total'],'wrong',s['q1_wrong_count'],'q1_rate',s['q1_rate'],'correct',s['correct'],'/',s['answer_expected'],'esc',s['escalate_correct'],'/',s['escalate_expected'],'asks',s['asks']['total'],'not_run',len(s.get('not_run_budget') or []))
    print('  g2',json.dumps({k:s['g2'][k] for k in s['g2'] if k.startswith('invalid_rate')},ensure_ascii=False))"
say "budget (expected: TOTAL <= 1140 OK, codex only)"
$PY artifacts/w2-g/g2/budget_g2.py | tail -5
say "ledgers: chain OK (expected 1 for each) and the recount of the decisions (expected mismatches 0)"
for f in $(find artifacts/w2-g/live_g2 -name ledger.jsonl); do echo "$f $($PY -m verantyx.llm_choice verify $f | grep -c '"chain": "OK"')"; done
$PY artifacts/w2-g/g2/ledger_recheck_g2.py $(find artifacts/w2-g/live_g2 -name ledger.jsonl) | tail -2
say "order of events: code freeze < data freeze < off / fake / first real ask"
$PY -c "
import json,glob
for p in sorted(glob.glob('artifacts/w2-g/live_g2/w2g3/*/ledger.jsonl')+glob.glob('artifacts/w2-g/live_g2/w2g2/*/ledger.jsonl')):
    first=next(json.loads(l) for l in open(p) if l.strip()); print(p, first.get('ts'))"
tail -2 artifacts/w2-g/g2/freeze_code.txt; tail -2 artifacts/w2-g/fixtures_freeze3.txt
ls -l --time-style=+%H:%M:%S artifacts/w2-g/g2/g3_w2g3/off/results.jsonl 2>/dev/null || ls -lT artifacts/w2-g/g2/g3_w2g3/off/results.jsonl
say "end: status of the tree"
git status --porcelain --untracked-files=all | grep -v 'artifacts/w2-g/' 
echo "(done)"
