#!/bin/sh
# Re-runs the checks of the ticket's section 7 (except the real-provider runs, which are only re-counted from their saved outputs,
# and the full test suite, whose output is artifacts/w2-g/after_pytest.txt).  Output: artifacts/w2-g/final_run.log
W=/Users/motonisihikoudai/Projects/vera-impl/wt/W2-g-S
cd $W || exit 1
PY=artifacts/w2-g/py.sh
echo "== freeze: sha256 of the frozen fixtures (not OK lines)";   grep -E '^[0-9a-f]{64} ' artifacts/w2-g/fixtures_freeze.txt | shasum -a 256 -c - | grep -vc ': OK$'
echo "== freeze: verantyx lines in status_at_freeze";            grep -c 'verantyx/' artifacts/w2-g/status_at_freeze.txt
echo "== freeze time vs conduct_map.py creation time";           stat -f 'birth %SB | mtime %Sm | %N' artifacts/w2-g/fixtures_freeze.txt verantyx/conduct_map.py tests/conduct_ask/w2g/items.jsonl; tail -1 artifacts/w2-g/fixtures_freeze.txt
echo "== freeze 2 (the second data set, w2g2): sha256 not OK lines";  grep -E '^[0-9a-f]{64} ' artifacts/w2-g/fixtures_freeze2.txt | shasum -a 256 -c - | grep -vc ': OK$'
echo "== freeze 2: time of the freeze vs the first change of conduct_map.py after it (see r2 notes: conduct_map.py changed after the freeze)"; stat -f 'birth %SB | mtime %Sm | %N' artifacts/w2-g/fixtures_freeze2.txt tests/conduct_ask/w2g2/items.jsonl; cat artifacts/w2-g/fixtures_freeze2.txt | tail -2
echo "== freeze 2: the code at the freeze is the round-1 code (sha256 of the saved copies vs status_at_freeze2)"; shasum -a 256 artifacts/w2-g/conduct_map.r2_start.py.txt artifacts/w2-g/conduct_ask.r2_start.py.txt artifacts/w2-g/llm_choice.r2_start.py.txt; tail -3 artifacts/w2-g/status_at_freeze2.txt
echo "== new tests (G1 G2 G5 unit cli reply bank llm_choice)"
$PY -m pytest -p no:cacheprovider -q tests/test_conduct_map_bank.py tests/test_conduct_map_g1.py tests/test_conduct_map_g2.py tests/test_conduct_map_g5.py tests/test_conduct_map_order.py tests/test_conduct_map_unit.py tests/test_conduct_map_cli.py tests/test_conduct_map_reply.py tests/test_llm_choice.py 2>&1 | tail -2
$PY -m pytest -p no:cacheprovider -v tests/test_conduct_map_g1.py tests/test_conduct_map_g2.py tests/test_conduct_map_g5.py tests/test_conduct_map_order.py > artifacts/w2-g/g125_tests.txt 2>&1; tail -1 artifacts/w2-g/g125_tests.txt
echo "== meaningless asserts in the new tests (none)"; grep -n 'or True' tests/test_conduct_map*.py | wc -l
echo "== skip/xfail marks in the new tests (only the live one)"; grep -nE 'pytest\.mark\.(skip|xfail)|pytest\.(skip|xfail)\(' tests/test_conduct_map*.py
echo "== removed lines of llm_choice.py vs dev (none)";          git diff dev -- verantyx/llm_choice.py | grep -c '^-[^-]'
echo "== G4 bank off / fake";
for m in off fake; do $PY tests/conduct_ask/run_bank.py --items tests/conduct_ask/fixtures/items.jsonl --frames tests/conduct_ask/fixtures/frames --vocab-llm $m --split all --out artifacts/w2-g/g4/after_$m > /dev/null; done
$PY artifacts/w2-g/compare_bank.py > artifacts/w2-g/g4/bank_compare.txt; cat artifacts/w2-g/g4/bank_compare.txt
echo "== G4 calls"; sh artifacts/w2-g/dump_calls.sh after | tail -1; $PY artifacts/w2-g/compare_calls.py; head -8 artifacts/w2-g/calls_changes.txt | cut -c1-200
echo "== real questions (off)"
env -i HOME="$HOME" PATH=/usr/bin:/bin PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=$W PYTHONIOENCODING=utf-8 LANG=en_US.UTF-8 VERA_REAL_QUESTIONS=/Users/motonisihikoudai/vera-wiring/data/real_agent_questions.jsonl /Users/motonisihikoudai/vera-wiring/env/bin/python tools/real_questions_eval.py --conduct-ask --out artifacts/w2-g/real_questions_off > /dev/null 2>&1
diff -q artifacts/w2-c/real_questions/results.jsonl artifacts/w2-g/real_questions_off/results.jsonl && echo "real questions: same as W2-c"
echo "== off does not import conduct_map"
$PY -c "import sys,verantyx.conduct_ask as c;c.answer_question('tests/conduct_ask/fixtures/frames/f01_loan.md','保存形式はどれにしますか？',['CSV','SQLite']);print('conduct_map' in ' '.join(sys.modules))"
echo "== G3 recount"
for d in live/codex_codex live/codex_codex_r2 live/codex_claude live/smoke/run1; do $PY tests/conduct_ask/w2g/run_map_bank.py --recount artifacts/w2-g/$d; done
echo "== G3 recount (second data set w2g2: the judged one)"
for d in live/w2g2/codex_codex live/w2g2/codex_claude; do $PY tests/conduct_ask/w2g/run_map_bank.py --items tests/conduct_ask/w2g2/items.jsonl --frames tests/conduct_ask/w2g2/frames --recount artifacts/w2-g/$d; done
$PY tests/conduct_ask/w2g/run_map_bank.py --items tests/conduct_ask/w2g/items.jsonl --frames tests/conduct_ask/w2g/frames --recount artifacts/w2-g/live/w2g1_rerun/codex_codex_subset
echo "== G3 round 3: order-route re-runs (recount) and the merged 64-question results"
for d in live/w2g2/codex_codex_r3_order live/w2g2/codex_codex_r3b_order live/w2g2/codex_claude_r3b_order; do $PY tests/conduct_ask/w2g/run_map_bank.py --items tests/conduct_ask/w2g2/items.jsonl --frames tests/conduct_ask/w2g2/frames --recount artifacts/w2-g/$d; done
$PY tests/conduct_ask/w2g/run_map_bank.py --items artifacts/w2-g/live/calib_r3/items.jsonl --frames tests/conduct_ask/fixtures/frames --recount artifacts/w2-g/live/calib_r3/run1
echo "-- the declared id list live/w2g2_r3_subset.txt was written before the re-run (make_r3_subset.py: order_status!=null united with an order cue in the round-2 run); the merges below are recomputed from the saved runs"
echo "-- the code at the re-runs (sha256 at the first re-run, at the second re-run, now)"; cat artifacts/w2-g/sha_r3_run.txt artifacts/w2-g/sha_r3b_run.txt; shasum -a 256 verantyx/conduct_map.py verantyx/conduct_ask.py verantyx/llm_choice.py
$PY artifacts/w2-g/merge_r3.py artifacts/w2-g/live/w2g2/codex_codex artifacts/w2-g/live/w2g2/codex_codex_r3b_order artifacts/w2-g/live/w2g2_r3_subset.txt artifacts/w2-g/live/w2g2/merged_r3b_codex_codex | head -2
$PY artifacts/w2-g/merge_r3.py artifacts/w2-g/live/w2g2/codex_codex artifacts/w2-g/live/w2g2/codex_codex_r3_order artifacts/w2-g/live/w2g2_r3_subset.txt artifacts/w2-g/live/w2g2/merged_r3a_codex_codex | head -2
$PY artifacts/w2-g/merge_r3.py artifacts/w2-g/live/w2g2/codex_claude artifacts/w2-g/live/w2g2/codex_claude_r3b_order artifacts/w2-g/live/w2g2_r3_claude_subset.txt artifacts/w2-g/live/w2g2/merged_r3b_codex_claude | head -2
$PY artifacts/w2-g/decides_dist.py artifacts/w2-g/live/w2g2/codex_codex_r3_order/ledger.jsonl artifacts/w2-g/live/w2g2/codex_codex_r3b_order/ledger.jsonl artifacts/w2-g/live/calib_r3/run1/ledger.jsonl artifacts/w2-g/live/w2g2/codex_claude_r3b_order/ledger.jsonl
$PY -c "import json;s=json.load(open('artifacts/w2-g/live/w2g2/codex_codex/summary.json'));print('w2g2 codex_codex: total',s['total'],'wrong',s['q1_wrong_count'],'q1_rate',s['q1_rate'],'q2',s['q2_answer_rate'],'escalate_correct',s['escalate_correct_rate'],'asks',s['asks']['total'],'elapsed',s['elapsed'])"
echo "== ledgers recounted from the raw replies (decisions, mismatches)"; $PY artifacts/w2-g/ledger_recheck.py artifacts/w2-g/live/w2g2/codex_codex/ledger.jsonl artifacts/w2-g/live/w2g2/codex_claude/ledger.jsonl artifacts/w2-g/live/w2g1_rerun/codex_codex_subset/ledger.jsonl artifacts/w2-g/live/w2g2/codex_codex_r3_order/ledger.jsonl artifacts/w2-g/live/w2g2/codex_codex_r3b_order/ledger.jsonl artifacts/w2-g/live/w2g2/codex_claude_r3b_order/ledger.jsonl artifacts/w2-g/live/calib_r3/run1/ledger.jsonl
echo "== docs numbers vs saved summaries (MISSING lines)"; $PY artifacts/w2-g/docs_check.py g3_w2g2/off live/w2g2/codex_codex live/w2g2/codex_claude live/w2g2/codex_codex_r3_order live/w2g2/codex_codex_r3b_order live/calib_r3/run1 live/w2g2/codex_claude_r3b_order g3/off:short live/codex_codex_r2:short live/codex_claude:short live/w2g1_rerun/codex_codex_subset:short | tail -1
# the saved rule-only baselines (g3/off, g3_w2g2/off) are what docs/CONDUCT_ASK.md cites: this script writes to *_rerun, never over them
$PY tests/conduct_ask/w2g/run_map_bank.py --mode off --out artifacts/w2-g/g3/off_rerun > /dev/null && $PY tests/conduct_ask/w2g/run_map_bank.py --recount artifacts/w2-g/g3/off_rerun
$PY tests/conduct_ask/w2g/run_map_bank.py --recount artifacts/w2-g/g3/off
$PY tests/conduct_ask/w2g/run_map_bank.py --items tests/conduct_ask/w2g2/items.jsonl --frames tests/conduct_ask/w2g2/frames --mode off --out artifacts/w2-g/g3_w2g2/off_rerun > /dev/null && $PY tests/conduct_ask/w2g/run_map_bank.py --items tests/conduct_ask/w2g2/items.jsonl --frames tests/conduct_ask/w2g2/frames --recount artifacts/w2-g/g3_w2g2/off_rerun
$PY tests/conduct_ask/w2g/run_map_bank.py --items tests/conduct_ask/w2g2/items.jsonl --frames tests/conduct_ask/w2g2/frames --recount artifacts/w2-g/g3_w2g2/off
$PY artifacts/w2-g/causes.py artifacts/w2-g/live/codex_codex artifacts/w2-g/live/codex_codex_r2 artifacts/w2-g/live/codex_claude > artifacts/w2-g/live/over_escalation_causes.txt; cat artifacts/w2-g/live/over_escalation_causes.txt
$PY artifacts/w2-g/budget.py
for f in artifacts/w2-g/live/codex_codex/ledger.jsonl artifacts/w2-g/live/codex_codex_r2/ledger.jsonl artifacts/w2-g/live/codex_claude/ledger.jsonl artifacts/w2-g/live/smoke/run1/ledger.jsonl artifacts/w2-g/live/smoke2/run1/ledger.jsonl artifacts/w2-g/live/smoke2/run2/ledger.jsonl artifacts/w2-g/live/w2g2/codex_codex/ledger.jsonl artifacts/w2-g/live/w2g2/codex_claude/ledger.jsonl artifacts/w2-g/live/w2g1_rerun/codex_codex_subset/ledger.jsonl artifacts/w2-g/live/w2g2/codex_codex_r3_order/ledger.jsonl artifacts/w2-g/live/w2g2/codex_codex_r3b_order/ledger.jsonl artifacts/w2-g/live/w2g2/codex_claude_r3b_order/ledger.jsonl artifacts/w2-g/live/calib_r3/run1/ledger.jsonl artifacts/w2-g/live/review_t06/ledger.jsonl artifacts/w2-g/live/review_v06/ledger.jsonl; do [ -f $f ] || continue; echo "$f chain OK count: $($PY -m verantyx.llm_choice verify $f | grep -c '"chain": "OK"')"; done
echo "== guard (codex / claude starts in the tests)"; sh artifacts/w2-g/guard_run.sh > artifacts/w2-g/guard_run.txt 2>&1; tail -1 artifacts/w2-g/guard_run.txt; if [ -f artifacts/w2-g/guard_log.jsonl ]; then wc -l < artifacts/w2-g/guard_log.jsonl; else echo 0; fi
echo "== Q7"; $PY artifacts/w2-g/q7_check.py
echo "== provenance (modules outside the tree)"
$PY -c "import sys,os,verantyx.conduct_ask,verantyx.conduct_map,verantyx.llm_choice;r=os.getcwd();m=[x for x in sys.modules if x.startswith('verantyx')];print('verantyx modules',len(m),'outside',[x for x in m if getattr(sys.modules[x],'__file__',None) and not os.path.abspath(sys.modules[x].__file__).startswith(r)])"
echo "== status outside the allowed paths"
git status --porcelain --untracked-files=all | grep -vE '^( M verantyx/(conduct_ask|llm_choice)\.py| M docs/CONDUCT_ASK\.md|\?\? (verantyx/conduct_map\.py|tests/test_conduct_map[^/]*\.py|tests/conduct_ask/(w2g2?/|map_helpers\.py)|artifacts/w2-g/))'
echo "== protected paths unchanged"; git diff --stat dev -- tests/conduct_ask/run_bank.py tests/conduct_ask/ca_helpers.py tests/conduct_ask/fixtures verantyx/cli.py verantyx/conductor.py verantyx/conductor_run.py
echo "== pycache"; find . -path ./.git -prune -o \( -name __pycache__ -o -name '*.pyc' \) -print | head
