#!/usr/bin/env python3
"""W3-b3: the entry's output of W3-b3 against the output of the base commit (dev c875ed3), input by input (two dumps of w3b1_entry_dump.py, same inputs in the same order, both with the
placement). The kinds: same | newly_read (the base abstains, now it reads: EVERY one gets a verdict CORRECT / WRONG / INCOMPLETE / UNSURE) | read_to_abstain | changed (both read, the output
differs) | refusal_changed (both abstain, the output differs: it must not happen: a refusal of the path is the base's output) | error_changed.
Everything but `same` is written to --out as {text, source, kind, before, after[, verdict]}. A newly_read input gets its verdict from, in this order: the data it comes from (the W3-b3
files, and everything that w3b2_delta.gold_sources knows: the W3-b2 / W3-b1 data, the three B1 samples, the event cross sentences, the frozen Japanese banks), else from the manual file --manual
(text<TAB>label<TAB>reason, written by a person who read the sentence and the new reading). No verdict at all -> UNCLASSIFIED. Exit code 1 when anything is UNCLASSIFIED, or not `same` /
`newly_read`, or a verdict is WRONG or INCOMPLETE. UNSURE is listed and does not fail (the reviewer decides).
"""
import argparse
import collections
import importlib.util
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import w3b3_common as C
_spec = importlib.util.spec_from_file_location('w3b2_delta_for_w3b3', HERE / 'w3b2_delta.py')
W2 = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(W2)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--before', required=True); ap.add_argument('--after', required=True); ap.add_argument('--out', required=True)
    ap.add_argument('--manual', required=True, help='manual verdicts: text<TAB>label<TAB>reason (read; may be missing)')
    ap.add_argument('--labels-out', default=None)
    a = ap.parse_args()
    C.isolation()
    before, after = C.load_jsonl(a.before), C.load_jsonl(a.after)
    assert [r['text'] for r in before] == [r['text'] for r in after], 'the two dumps are not on the same inputs'
    manual = {}
    mp = Path(a.manual)
    if mp.exists():
        for line in mp.read_text(encoding='utf-8').splitlines():
            if line.strip() and not line.startswith('#'):
                parts = line.split('\t')
                manual[parts[0]] = (parts[1], parts[2] if len(parts) > 2 else '')
    gold = W2.gold_sources()
    for name in C.DATA_ALL:
        for r in C.load_data(name): gold[0][r['input']] = ('new_data', r)
    counts, rows, labels = collections.Counter(), [], []
    for d, n in zip(before, after):
        do, no = d['out'], n['out']
        if do == no: counts['same'] += 1; continue
        if 'error' in do or 'error' in no: kind = 'error_changed'
        elif not do['readable'] and not no['readable']: kind = 'refusal_changed'
        elif not do['readable'] and no['readable']: kind = 'newly_read'
        elif do['readable'] and not no['readable']: kind = 'read_to_abstain'
        else: kind = 'changed'
        counts[kind] += 1
        row = {'text': d['text'], 'source': d['source'], 'kind': kind, 'before': do, 'after': no}
        if kind == 'newly_read':
            label, why = W2.verdict_of(d['text'], no, gold, manual)
            row['verdict'] = label; row['verdict_reason'] = why
            counts['verdict:' + label] += 1
            labels.append((d['text'], d['source'], label, why, no['clauses'], no['relations']))
        rows.append(row)
    Path(a.out).write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
    if a.labels_out:
        Path(a.labels_out).write_text(''.join('%s\t%s\t%s\t%s\t%s\t%s\n' % (t, s, l, w, json.dumps(c, ensure_ascii=False), json.dumps(rel, ensure_ascii=False)) for t, s, l, w, c, rel in labels), encoding='utf-8')
    by_source = collections.Counter((r['source'], r['kind']) for r in rows)
    print('inputs=%d same=%d newly_read=%d read_to_abstain=%d changed=%d refusal_changed=%d error_changed=%d'
          % (len(before), counts['same'], counts['newly_read'], counts['read_to_abstain'], counts['changed'], counts['refusal_changed'], counts['error_changed']))
    print('verdicts: ' + json.dumps({k[8:]: v for k, v in sorted(counts.items()) if k.startswith('verdict:')}))
    print('by source and kind: ' + json.dumps({'%s|%s' % k: v for k, v in sorted(by_source.items())}, ensure_ascii=False))
    for t, s, l, w, c, rel in labels:
        if l in ('UNSURE', 'UNCLASSIFIED', 'WRONG', 'INCOMPLETE'): print('%s\t%s\t%s\t%s' % (l, s, t, w))
    for r in rows:
        if r['kind'] not in ('newly_read',): print('%s\t%s\t%s' % (r['kind'], r['source'], r['text']))
    bad = counts['verdict:UNCLASSIFIED'] or counts['read_to_abstain'] or counts['changed'] or counts['refusal_changed'] or counts['error_changed'] or counts['verdict:WRONG'] or counts['verdict:INCOMPLETE']
    sys.exit(1 if bad else 0)


if __name__ == '__main__':
    main()
