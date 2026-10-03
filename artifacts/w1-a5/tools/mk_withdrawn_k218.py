"""Make the list of the rows of ja_r12.jsonl that round 2 (K218) turns back to an abstention, from the OUTPUT OF ROUND 1 (artifacts/w1-a5/data_check_none.json) by two rules only.
The rows are never chosen by hand and never chosen by the output of round 2.

  adverb_mark          the round-1 row has a non-empty `adverbs`  -> predicted (path, reason) = ('not_triggered', None)
  noun_phrase_quantity the round-1 path is `reread` and the counter of its quantity is not an event counter (回・度) -> ('reread_refused', 'QUANTIFIER_TARGET_UNDETERMINED:noun_phrase'),
                       round1_value = the value of the quantity

Usage: python mk_withdrawn_k218.py [--out FILE]   (default artifacts/w1-a5/r2/k218_withdrawn_rows.json)
"""
import argparse
import collections
import json
import pathlib

TREE = pathlib.Path(__file__).resolve().parents[3]
A = TREE / 'artifacts' / 'w1-a5'
EVENT = ('回', '度')                                     # the registered event counters (K212); copied here as a rule of the list, not read from the reader
RULE = ('adverb_mark: the round-1 row has a non-empty `adverbs` -> (not_triggered, None). '
        'noun_phrase_quantity: the round-1 path is reread and the counter of the quantity is not 回・度 -> (reread_refused, QUANTIFIER_TARGET_UNDETERMINED:noun_phrase).')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default=str(A / 'r2' / 'k218_withdrawn_rows.json'))
    a = ap.parse_args()
    round1 = json.loads((A / 'data_check_none.json').read_text(encoding='utf-8'))
    data = {}
    for line in (TREE / 'tests' / 'reading_soundness' / 'ja_r12.jsonl').read_text(encoding='utf-8').splitlines():
        if line.strip():
            r = json.loads(line); data[r['id']] = r
    rows, kinds = [], collections.Counter()
    for x in round1:
        kind = None
        if x['adverbs']:
            kind, path, reason, value = 'adverb_mark', 'not_triggered', None, None
        elif x['path'] == 'reread' and x['quantity'] and x['quantity']['counter'] not in EVENT:
            kind, path, reason, value = 'noun_phrase_quantity', 'reread_refused', 'QUANTIFIER_TARGET_UNDETERMINED:noun_phrase', x['quantity']['value']
        if kind is None: continue
        d = data[x['id']]
        kinds[kind] += 1
        rows.append({'id': x['id'], 'kind': kind, 'input': d['input'], 'construction': d['construction'], 'frozen_entry_expect': d['entry_expect'],
                     'frozen_w1a5_expect': d['w1a5_expect'], 'pinned_path': path, 'pinned_reason': reason, 'round1_value': value})
    out = {'note': 'The rows of ja_r12.jsonl (the 151 rows of round 1) that K218 round 2 turns back to an abstention. Made from artifacts/w1-a5/data_check_none.json (round 1) by the rule below, before the implementation.',
           'change_record': (A / 'r2' / 'change_time.txt').read_text(encoding='utf-8').strip(), 'rule': RULE, 'rows': rows}
    pathlib.Path(a.out).write_text(json.dumps(out, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    print('rows=%d %s' % (len(rows), json.dumps(dict(kinds), ensure_ascii=False)))


if __name__ == '__main__':
    main()
