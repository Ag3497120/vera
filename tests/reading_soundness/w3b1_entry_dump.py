#!/usr/bin/env python3
"""W3-b1: the reading entry (`semantic_read.read`) on a fixed set of inputs, one JSON line per input: {text, source, out}.

  --mode none       no placement (`read(text, placement=None)`; at the base commit, whose `read` has no such argument, `read(text)`)
  --mode live       the real placement (--placement DIR, else the variable VERA_PLACEMENT); every question is counted
  --mode estimated  the live answers rewritten so that every direct DECIDED / MULTIPLE answer is an estimated one (proximity)
  --mode multiple   the live answers rewritten so that every direct DECIDED answer is a split one (MULTIPLE)
  --inputs FILE | --inputs-out FILE   read the set of inputs from FILE (JSON lines {text, source}) / build it and write it to FILE
  --queries FILE    questions per input (total, max, inputs with a question, states of the answers)
  --timing FILE     wall-clock time per input; only when the 1-minute load average is below 8 (else {"skipped": "load", "load": value})

The set (fixed order, duplicates removed): the x3 sentences (the frozen Japanese banks and the 13 example files = dump_reads.py --banks --extra ...), en.jsonl,
en_r2.jsonl, the inputs of the three B1 samples, the sentences of the event cross tests (Japanese and English, with add1), ja_r8.jsonl, en_r4.jsonl, ja_r9.jsonl (round 3) and ja_r10.jsonl (round 4).
The loaded verantyx* modules must all be under PYTHONPATH (else exit code 2).
"""
import argparse
import collections
import inspect
import json
import os
import statistics
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
TREE_OF_SCRIPT = HERE.parent.parent
sys.path.insert(0, str(HERE))

EX_FILES = ('r3_probe_ja.txt', 'review_r1_examples_ja.txt', 'r4_review_examples_ja.txt', 'b1v2_inputs_ja.txt', 'review_r2_examples_ja.txt', 'b1v2_r2_inputs_ja.txt',
            'w1a2r2_probe_ja.txt', 'coverage_texts_ja.txt', 'review_r3_examples_ja.txt', 'b1v2_r3_inputs_ja.txt', 'w1a2r3_probe_ja.txt',
            'w1a3_review_r3_examples_ja.txt', 'w1a3_r4_inputs_ja.txt')


def build_inputs():
    import dump_reads
    out, seen = [], set()

    def add(text, source):
        if text and text not in seen:
            seen.add(text); out.append({'text': text, 'source': source})
    for text, source in dump_reads.sentences(True, [str(TREE_OF_SCRIPT / 'artifacts' / 'w1-a' / f) for f in EX_FILES]):
        add(text, source)
    n_x3 = len(out)
    for name in ('en.jsonl', 'en_r2.jsonl'):
        for line in (HERE / name).read_text(encoding='utf-8').splitlines():
            if line.strip(): add(json.loads(line)['text'], name)
    for fx in ('B1_v2', 'B1_v2_r2', 'B1_v2_r3'):
        for line in (TREE_OF_SCRIPT / 'tests' / 'bank_score' / 'fixtures' / fx / 'items.jsonl').read_text(encoding='utf-8').splitlines():
            if line.strip(): add(json.loads(line)['input'], fx)
    for name in sorted(p.name for p in (TREE_OF_SCRIPT / 'tests' / 'event_cross' / 'data').glob('sentences_*.jsonl')):
        for line in (TREE_OF_SCRIPT / 'tests' / 'event_cross' / 'data' / name).read_text(encoding='utf-8').splitlines():
            if line.strip(): add(json.loads(line)['text'], name)
    for name in ('ja_r8.jsonl', 'en_r4.jsonl', 'ja_r9.jsonl', 'ja_r10.jsonl'):
        for line in (HERE / name).read_text(encoding='utf-8').splitlines():
            if line.strip(): add(json.loads(line)['input'], name)
    return out, n_x3


def load_average():
    try:
        out = subprocess.run(['/usr/sbin/sysctl', '-n', 'vm.loadavg'], capture_output=True, text=True, timeout=10).stdout.split()
        return float(out[1])
    except Exception:
        return None


class Counting:
    """Wraps a query object: counts every question and keeps the (state, origin) of every answer."""
    def __init__(self, inner, mapper=None):
        self.inner, self.mapper = inner, mapper
        self.count = 0
        self.states = collections.Counter()

    def query(self, term):
        a = self.inner.query(term)
        if self.mapper is not None: a = self.mapper(a)
        self.count += 1
        self.states['%s/%s/%s' % (a.get('state'), a.get('origin'), a.get('estimate_basis'))] += 1
        return a


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--mode', choices=['none', 'live', 'estimated', 'multiple'], required=True)
    ap.add_argument('--inputs'); ap.add_argument('--inputs-out'); ap.add_argument('--out', required=True)
    ap.add_argument('--placement'); ap.add_argument('--queries'); ap.add_argument('--timing')
    a = ap.parse_args()
    from verantyx import semantic_read as SR
    from verantyx import constructions
    constructions.discover()
    root = os.path.realpath(os.environ.get('PYTHONPATH', '.').split(os.pathsep)[0])
    foreign = [m.__file__ for k, m in list(sys.modules.items()) if (k == 'verantyx' or k.startswith('verantyx.'))
               and getattr(m, '__file__', None) and not os.path.realpath(m.__file__).startswith(root + os.sep)]
    print('tree=' + root)
    if foreign:
        print('ISOLATION FAILED', foreign); sys.exit(2)
    if a.inputs:
        inputs = [json.loads(l) for l in Path(a.inputs).read_text(encoding='utf-8').splitlines() if l.strip()]
    else:
        inputs, n_x3 = build_inputs()
        if a.inputs_out:
            Path(a.inputs_out).write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in inputs), encoding='utf-8')
        print('inputs=%d x3=%d' % (len(inputs), n_x3))
    takes_placement = 'placement' in inspect.signature(SR.read).parameters
    query = None
    if a.mode != 'none':
        if not takes_placement:
            print('this tree has no placement argument'); sys.exit(2)
        path = a.placement or os.environ.get('VERA_PLACEMENT')
        if not path:
            print('no placement: give --placement or VERA_PLACEMENT'); sys.exit(2)
        import w3b1_fakes as F
        from verantyx import semantic_reader as R
        mapper = {'live': None, 'estimated': lambda x: F.to_estimated(x, 'proximity'), 'multiple': F.to_multiple}[a.mode]
        query = Counting(R.CoarseQuery(path), mapper)
    load0 = load_average()
    rows, per_input, times = [], [], []
    t_all = time.perf_counter()
    for item in inputs:
        before = query.count if query else 0
        t0 = time.perf_counter()
        try:
            if a.mode == 'none':
                out = SR.read(item['text'], placement=None) if takes_placement else SR.read(item['text'])
            else:
                out = SR.read(item['text'], placement=query)
        except SR.ReadError as err:
            out = {'error': {'type': err.type, 'detail': err.detail}}
        times.append(time.perf_counter() - t0)
        per_input.append((query.count - before) if query else 0)
        rows.append({'text': item['text'], 'source': item['source'], 'out': out})
    wall = time.perf_counter() - t_all
    Path(a.out).write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
    if a.queries and query:
        Path(a.queries).write_text(json.dumps({'mode': a.mode, 'inputs': len(rows), 'questions_total': sum(per_input), 'questions_max_per_input': max(per_input),
                                              'inputs_with_a_question': sum(1 for n in per_input if n), 'answers_by_state_origin_basis': dict(sorted(query.states.items()))},
                                             ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    if a.timing:
        load1 = load_average()
        load = max(x for x in (load0, load1) if x is not None) if (load0 is not None or load1 is not None) else None
        if load is None or load >= 8:
            doc = {'skipped': 'load', 'load': load}
        else:
            doc = {'mode': a.mode, 'inputs': len(rows), 'load_1min_before': load0, 'load_1min_after': load1, 'wall_seconds': round(wall, 3),
                   'median_ms_per_input': round(statistics.median(times) * 1000, 3), 'max_ms_per_input': round(max(times) * 1000, 3),
                   'mean_ms_per_input': round(sum(times) / len(times) * 1000, 3)}
        Path(a.timing).write_text(json.dumps(doc, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    print('mode=%s inputs=%d readable=%d' % (a.mode, len(rows), sum(1 for r in rows if r['out'].get('readable'))))


if __name__ == '__main__':
    main()
