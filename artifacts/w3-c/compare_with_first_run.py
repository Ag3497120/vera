"""Round 2: the summaries of every case now (`view.summarize` of each turn, through the entry function) against `first_run_summaries.json` (the round-1 first observation, 12:44:44).
The cases whose summaries differ are listed; they must be exactly the ones the change of round 2 (docs change record 3) can reach. Output: compare_with_first_run.txt. Run with py.sh."""
import json
import sys
from pathlib import Path
TREE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(TREE / 'tests' / 'observe'))
import measure    # noqa: E402
import view       # noqa: E402

old = json.loads((TREE / 'artifacts' / 'w3-c' / 'first_run_summaries.json').read_text(encoding='utf-8'))
cases = measure.all_cases(str(TREE / 'tests' / 'observe' / 'data' / 'viewpoints.jsonl'))
data = measure.collect([c for c in cases if c['case'] in old], str(TREE / 'artifacts' / 'w3-c' / 'work_compare_first_run'))
same, differ = [], []
for name, (turns, _kw) in sorted(data.items()):
    now = [view.summarize(t) for t in turns]
    (same if now == old[name] else differ).append(name)
print('cases in the first-run record: %d; summaries equal: %d; summaries differ: %d' % (len(old), len(same), len(differ)))
print('differ:', differ)
print('cases only in the second round (not in the first-run record):', sorted(c['case'] for c in cases if c['case'] not in old))
