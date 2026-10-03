#!/usr/bin/env python3
"""W3-b1-5: the combination of W3-b1 (typed reading over direct placement types) and W5-a (attack wave 1 fixes) on the entry inputs.

Does the typed re-reading of W3-b1 run on a sentence that W5-a newly made abstain, and make a new reading of it? Five outputs of `w3b1_entry_dump.py` over the same inputs in the same order:
  --pre       the commit before W5-a and W3-b1 (0ff3f35), no placement
  --base      the base commit (2732274: W5-a in, W3-b1 not), no placement
  --w3b1      the W3-b1 tree alone (f410469), with the placement
  --now       the merged tree, with the placement
  --now-none  the merged tree, no placement
Prints key=value lines (and, with --list, one tab-separated line per input of interest). Exit 1 when: now-none differs from base on any input, a sentence W5-a newly made abstain is
read with the placement, a sentence is read only by the merged tree (not by W3-b1 alone), or a sentence both read differs. `only_w3b1` (W5-a stopped a reading of W3-b1: the safe
direction) is not a failure, but every such input is listed with its reasons. Standard library only; verantyx is not imported (no isolation check is needed).
"""
import argparse, collections, json, sys


def rd(path):
    with open(path, encoding='utf-8') as f: return [json.loads(l) for l in f if l.strip()]


def readable(r): return bool(r['out'].get('readable'))


def reasons(r): return list((r['out'].get('abstain') or {}).get('reasons') or [])


def first_type(r):
    x = reasons(r)
    return x[0].split(':')[0] if x else '-'


def main():
    ap = argparse.ArgumentParser()
    for k in ('pre', 'base', 'w3b1', 'now', 'now-none'): ap.add_argument('--' + k, required=True)
    ap.add_argument('--list', default=None)
    a = ap.parse_args()
    pre, base, w3b1, now, none = (rd(p) for p in (a.pre, a.base, a.w3b1, a.now, getattr(a, 'now_none')))
    n = len(pre)
    assert all(len(x) == n for x in (base, w3b1, now, none)), 'different numbers of rows'
    for x in (base, w3b1, now, none): assert [r['text'] for r in x] == [r['text'] for r in pre], 'different inputs or order'
    c = collections.Counter(); types = collections.Counter(); rows = []; only_w3b1 = []
    for p, b, w, m, z in zip(pre, base, w3b1, now, none):
        t = p['text']
        if json.dumps(z['out'], ensure_ascii=False, sort_keys=True) == json.dumps(b['out'], ensure_ascii=False, sort_keys=True): c['now_none_equals_base'] += 1
        if readable(p) and not readable(b):              # W5-a newly makes this input abstain
            c['w5a_new_abstain'] += 1
            types[first_type(b)] += 1
            if readable(m): c['now_readable'] += 1
            if len(reasons(m)) >= 2: c['now_second_reason'] += 1
            rows.append(('W5A_NEW_ABSTAIN', t, 'now_readable=%s' % readable(m), json.dumps(reasons(m), ensure_ascii=False)))
        if not readable(p) and not readable(b) and p['out'] != b['out']: c['w5a_reason_changed'] += 1
        mt = readable(m) and not readable(b)             # a reading the typed path made over the base
        wt = readable(w) and not readable(p)             # a reading the typed path made over the commit before
        if mt: c['typed_read_now'] += 1
        if wt: c['typed_read_w3b1'] += 1
        if mt and wt:
            if m['out'] == w['out']: c['both_identical'] += 1
            else: c['both_different'] += 1; rows.append(('BOTH_DIFFERENT', t, '', ''))
        if mt and not wt: c['only_now'] += 1; rows.append(('ONLY_NOW', t, '', json.dumps(m['out'], ensure_ascii=False)))
        if wt and not mt:
            c['only_w3b1'] += 1
            only_w3b1.append(t); rows.append(('ONLY_W3B1', t, 'now_reasons=%s' % json.dumps(reasons(m), ensure_ascii=False), 'base_reasons=%s' % json.dumps(reasons(b), ensure_ascii=False)))
    keys = ('now_none_equals_base', 'w5a_new_abstain', 'now_readable', 'now_second_reason', 'w5a_reason_changed', 'typed_read_now', 'typed_read_w3b1', 'both_identical', 'both_different', 'only_now', 'only_w3b1')
    print('inputs=%d' % n)
    for k in keys: print('%s=%d' % (k, c[k]))
    print('w5a_new_abstain_first_reason_types=%s' % json.dumps(dict(sorted(types.items())), ensure_ascii=False))
    for t in only_w3b1: print('only_w3b1_input=%s' % t)
    if a.list:
        with open(a.list, 'w', encoding='utf-8') as f:
            for r in rows: f.write('\t'.join(r) + '\n')
    fail = c['now_none_equals_base'] != n or c['now_readable'] > 0 or c['only_now'] > 0 or c['both_different'] > 0
    sys.exit(1 if fail else 0)


if __name__ == '__main__':
    main()
