#!/usr/bin/env python3
"""W1-a5 step 9: the output of the entry of this tree against the output of the base commit df4f001, input by input (two dumps of tests/reading_soundness/w3b1_entry_dump.py, the same
inputs in the same order). The kinds:
  same                    the same output
  newly_read              the base abstains, now it reads        (EVERY one gets a verdict: CORRECT / WRONG / INCOMPLETE / UNSURE)
  refusal_reason_changed  both abstain, the output differs (the reasons W1-a5 adds behind the base's reasons)
  read_to_refused         the base reads, now it abstains (the gates of the aspect rule)   (EVERY one gets a label: what the base had read and why the refusal is right)
  reading_changed         both read and the output differs (the aspect rule corrects the polarity and the tense)   (EVERY one gets a label: the base reading or the new one is the right one by convention 5)
  error_changed           one of the two is a typed error object and they differ
`newly_read` gets its verdict from, in this order: the data it comes from (ja_r12.jsonl and the sources of tests/reading_soundness/w3b2_delta.py -> b1.judge / classify.agrees / the
gold of the frozen banks), else from the manual file --manual (text<TAB>label<TAB>reason, written by a person who read the sentence and the new reading). The two other kinds that need
a label (read_to_refused, reading_changed) are labeled by the same file (a sentence without a line is UNCLASSIFIED). Exit code 1 when anything is UNCLASSIFIED, error_changed is above 0,
reading_changed has a label other than CORRECTION (a changed reading that is not the correction of a base misread), or a newly_read verdict is WRONG or INCOMPLETE.
Usage: cd <tree> && PYTHONPATH=<tree> python artifacts/w1-a5/tools/delta_w1a5.py --before A --after B --out C --manual D [--labels-out E] [--frozen-sources F,G,...]"""
import argparse
import collections
import importlib.util
import json
import os
import sys
from pathlib import Path

TREE = Path(__file__).resolve().parents[3]
RS = TREE / 'tests' / 'reading_soundness'
sys.path.insert(0, str(RS)); sys.path.insert(0, str(TREE)); sys.path.insert(0, str(TREE / 'tests' / 'event_cross'))
spec = importlib.util.spec_from_file_location('w3b2_delta_of_the_tree_w1a5', RS / 'w3b2_delta.py')
D = importlib.util.module_from_spec(spec); spec.loader.exec_module(D)
_original = D.gold_sources


def gold_sources():
    src, b1, classify = _original()
    for name in ('ja_r10_w3b4.jsonl', 'ja_r12.jsonl'):
        for r in D.rows_of(RS / name): src.setdefault(r['input'], ('new_data', r))
    return src, b1, classify


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--before', required=True); ap.add_argument('--after', required=True); ap.add_argument('--out', required=True); ap.add_argument('--manual', required=True)
    ap.add_argument('--labels-out', default=None)
    ap.add_argument('--frozen-sources', default='table7.jsonl,ja.jsonl,ja_r2.jsonl,ja_r3.jsonl,ja_r4.jsonl,ja_r5.jsonl,ja_r6.jsonl,ja_r8.jsonl,ja_r9.jsonl,ja_r10.jsonl,ja_r10_w3b4.jsonl,en.jsonl,en_r2.jsonl,en_r4.jsonl',
                    help='the data files that are the frozen data of the ticket: the rows of the kinds above that come from them are counted apart (docs C1)')
    a = ap.parse_args()
    root = os.path.realpath(os.environ.get('PYTHONPATH', '.').split(os.pathsep)[0])
    foreign = [m.__file__ for k, m in list(sys.modules.items()) if (k == 'verantyx' or k.startswith('verantyx.')) and getattr(m, '__file__', None)
               and not os.path.realpath(m.__file__).startswith(root + os.sep)]
    if foreign: print('ISOLATION FAILED', foreign); sys.exit(2)
    before, after = D.rows_of(a.before), D.rows_of(a.after)
    assert [r['text'] for r in before] == [r['text'] for r in after], 'the two dumps are not on the same inputs'
    manual = {}
    if Path(a.manual).exists():
        for line in Path(a.manual).read_text(encoding='utf-8').splitlines():
            if line.strip() and not line.startswith('#'):
                parts = line.split('\t'); manual[parts[0]] = (parts[1], parts[2] if len(parts) > 2 else '')
    frozen = set(a.frozen_sources.split(','))
    # the sentences of the frozen data files (a sentence may be in several sources of the dump: the dump keeps the first; the frozen data is looked up by sentence)
    frozen_texts = set()
    for name in frozen:
        p = RS / name
        if p.exists():
            for r in D.rows_of(p): frozen_texts.add(r.get('input') or r.get('text'))
    gold = gold_sources()
    counts = collections.Counter(); rows, labels = [], []
    for d, n in zip(before, after):
        do, no = d['out'], n['out']
        if do == no: counts['same'] += 1; continue
        if 'error' in do or 'error' in no: kind = 'error_changed'
        elif not do['readable'] and not no['readable']: kind = 'refusal_reason_changed'
        elif not do['readable'] and no['readable']: kind = 'newly_read'
        elif do['readable'] and not no['readable']: kind = 'read_to_refused'
        else: kind = 'reading_changed'
        counts[kind] += 1
        row = {'text': d['text'], 'source': d['source'], 'kind': kind, 'frozen': d['text'] in frozen_texts, 'before': do, 'after': no}
        if kind == 'newly_read':
            label, why = D.verdict_of(d['text'], no, gold, manual)
        elif kind in ('read_to_refused', 'reading_changed'):
            label, why = manual.get(d['text'], ('UNCLASSIFIED', 'no manual line'))
        else:
            label, why = None, None
        if label is not None:
            row['verdict'] = label; row['verdict_reason'] = why; counts['%s:%s' % (kind, label)] += 1
            labels.append((kind, d['text'], d['source'], label, why))
        if row['frozen']: counts['frozen:' + kind] += 1
        rows.append(row)
    Path(a.out).write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
    if a.labels_out:
        Path(a.labels_out).write_text(''.join('%s\t%s\t%s\t%s\t%s\n' % l for l in labels), encoding='utf-8')
    kinds = ('newly_read', 'refusal_reason_changed', 'read_to_refused', 'reading_changed', 'error_changed')
    print('inputs=%d same=%d ' % (len(before), counts['same']) + ' '.join('%s=%d' % (k, counts[k]) for k in kinds))
    for k in ('newly_read', 'read_to_refused', 'reading_changed'):
        print('%s labels: %s' % (k, json.dumps({x.split(':', 1)[1]: v for x, v in sorted(counts.items()) if x.startswith(k + ':')}, ensure_ascii=False)))
    print('rows that come from the frozen data files: ' + json.dumps({x[7:]: v for x, v in sorted(counts.items()) if x.startswith('frozen:')}))
    by_source = collections.Counter((r['source'], r['kind']) for r in rows)
    print('by source and kind: ' + json.dumps({'%s|%s' % k: v for k, v in sorted(by_source.items())}, ensure_ascii=False))
    for kind, t, s, l, w in labels:
        if l in ('UNSURE', 'UNCLASSIFIED', 'WRONG', 'INCOMPLETE') or (kind == 'reading_changed' and l != 'CORRECTION'): print('%s\t%s\t%s\t%s\t%s' % (kind, l, s, t, w))
    bad = (sum(v for k, v in counts.items() if k.endswith(':UNCLASSIFIED')) or counts['error_changed'] or counts['newly_read:WRONG'] or counts['newly_read:INCOMPLETE']
           or sum(v for k, v in counts.items() if k.startswith('reading_changed:') and not k.endswith(':CORRECTION')))
    sys.exit(1 if bad else 0)


if __name__ == '__main__':
    main()
