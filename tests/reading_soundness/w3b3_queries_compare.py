#!/usr/bin/env python3
"""W3-b3: the number of questions to the placement per input, in this tree and in the base commit (c875ed3, extracted by `git archive` into a temporary directory and run in a child
process with its own PYTHONPATH), and the inputs for which they differ. All must be inputs the path was triggered on (the path asks only after it was; an input it did not trigger on
asks exactly what the base asks). Prints: inputs, inputs whose count differs, how many of them are triggered (all must be), the questions in total (base / now).
Usage: cd <tree> && PYTHONPATH=<tree> python tests/reading_soundness/w3b3_queries_compare.py --inputs FILE --placement DIR   (the child: --count-only OUT)
"""
import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import w3b3_common as C


def count(inputs, placement):
    from verantyx import semantic_read as SR, semantic_reader as R, constructions
    constructions.discover()

    class Counting:
        def __init__(self): self.inner, self.calls = R.CoarseQuery(placement), 0
        def query(self, term): self.calls += 1; return self.inner.query(term)
    out = []
    for item in inputs:
        q = Counting()
        try: SR.read(item['text'], placement=q)
        except SR.ReadError: pass
        out.append(q.calls)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--inputs', required=True); ap.add_argument('--placement', required=True); ap.add_argument('--count-only')
    a = ap.parse_args()
    inputs = C.load_jsonl(a.inputs)
    if a.count_only:
        Path(a.count_only).write_text(json.dumps(count(inputs, a.placement)), encoding='utf-8'); return
    from verantyx import semantic_read as SR, semantic_reader as R, constructions
    constructions.discover()
    C.isolation()
    now = count(inputs, a.placement)
    with tempfile.TemporaryDirectory() as tmp:
        dev = Path(tmp) / 'dev'; dev.mkdir()
        arch = subprocess.run(['git', '-C', str(C.TREE), 'archive', C.BASE_COMMIT], capture_output=True, check=True).stdout
        subprocess.run(['tar', '-x', '-C', str(dev)], input=arch, check=True)
        out = Path(tmp) / 'dev_counts.json'
        env = {k: os.environ[k] for k in ('HOME', 'PATH', 'TMPDIR') if k in os.environ}
        env.update({'PYTHONDONTWRITEBYTECODE': '1', 'PYTHONPATH': str(dev)})
        subprocess.run([sys.executable, str(HERE / 'w3b3_queries_compare.py'), '--inputs', a.inputs, '--placement', a.placement, '--count-only', str(out)], cwd=str(dev), env=env, check=True)
        base = json.loads(out.read_text(encoding='utf-8'))
    differ = [(i, b, n) for i, (b, n) in enumerate(zip(base, now)) if b != n]
    untriggered = []
    for i, b, n in differ:
        ex = SR.clause_scope_explain_ja(inputs[i]['text'], R.CoarseQuery(a.placement))
        if not ex['triggered']: untriggered.append(inputs[i]['text'])
    print('inputs=%d questions_base=%d questions_now=%d differ=%d differ_and_triggered=%d differ_not_triggered=%d' % (len(inputs), sum(base), sum(now), len(differ), len(differ) - len(untriggered), len(untriggered)))
    for i, b, n in differ[:400]:
        print('DIFFERS %d -> %d  %s' % (b, n, inputs[i]['text']))
    for t in untriggered: print('NOT_TRIGGERED_BUT_DIFFERS %s' % t)
    sys.exit(1 if untriggered else 0)


if __name__ == '__main__':
    main()
