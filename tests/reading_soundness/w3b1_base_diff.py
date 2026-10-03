#!/usr/bin/env python3
"""W3-b1: the entry's output with the placement against the base commit's, input by input (the two dumps of w3b1_entry_dump.py, same inputs in the same order).

  same               the same output
  reason_changed     both abstain; only the reasons differ (a PLACEMENT_* reason was added)
  false->readable    the base abstains, now it reads        (EVERY one gets a verdict: CORRECT / WRONG / INCOMPLETE / UNSURE)
  readable->false    the base reads, now it abstains
  changed            both read and the clauses or the relations differ (counted twice: with the source fields `predicate_basis` / `role_basis` taken out
                     of the new clauses, and as they are)
  error_changed      one of the two is a typed error object and they differ
Everything but `same` is written to --out as {text, source, kind, dev, now}. A false->readable input gets its verdict from, in this order: the data it comes from
(ja_r8 / en_r4 / the three B1 samples -> tools.bank_score.v2.b1.judge; the event cross sentences -> tests/event_cross/classify.agrees; the frozen
Japanese banks -> their gold alternatives, role names of the reader mapped to the convention's), else from the manual file --classified (text<TAB>label<TAB>reason,
written by a person who read the sentence and the new reading). No verdict at all -> UNCLASSIFIED. Exit code 1 when anything is UNCLASSIFIED, when `changed` (source fields
taken out) / readable->false / error_changed is above 0, or when a verdict is WRONG or INCOMPLETE. UNSURE is listed and does not fail (the reviewer decides).
"""
import argparse
import collections
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
TREE = HERE.parent.parent
sys.path.insert(0, str(HERE)); sys.path.insert(0, str(TREE)); sys.path.insert(0, str(TREE / 'tests' / 'event_cross'))
BASIS = ('predicate_basis', 'role_basis')
JA_BANKS = ('table7.jsonl', 'ja.jsonl', 'ja_r2.jsonl', 'ja_r3.jsonl', 'ja_r4.jsonl', 'ja_r5.jsonl', 'ja_r6.jsonl')
READER_TO_CONVENTION = {'origin': 'source', 'location': 'place', 'direction': 'goal', 'means': 'instrument', 'limit': 'goal'}


def rows_of(path):
    return [json.loads(l) for l in Path(path).read_text(encoding='utf-8').splitlines() if l.strip()]


def strip_basis(out):
    c = json.loads(json.dumps(out))
    for clause in c.get('clauses', []) or []:
        for k in BASIS: clause.pop(k, None)
    return c


def gold_sources():
    from tools.bank_score.v2 import b1
    import classify
    src = {}
    for name in ('ja_r8.jsonl', 'en_r4.jsonl', 'ja_r9.jsonl', 'ja_r10.jsonl'):
        for r in rows_of(HERE / name): src[r['input']] = ('new_data', r)
    for fx in ('B1_v2', 'B1_v2_r2', 'B1_v2_r3'):
        for r in rows_of(TREE / 'tests' / 'bank_score' / 'fixtures' / fx / 'items.jsonl'): src.setdefault(r['input'], ('b1_sample', r))
    for lang, s, exp in classify.sentences(): src.setdefault(s['text'], ('event_cross', exp))
    for name in JA_BANKS:
        for r in rows_of(HERE / name): src.setdefault(r['text'], ('ja_bank', r))
    return src, b1, classify


def bank_verdict(item, out):
    gold = item['gold']
    if gold['kind'] in ('none', 'unsupported'): return 'WRONG', 'the gold says the sentence is not to be read (%s)' % gold['kind']
    mapped = []
    for c in out['clauses']:
        mapped.append({'predicate': c['predicate'], 'polarity': c['polarity'], 'roles': c['roles']})
    for alt in gold['alternatives']:
        if len(alt) != len(mapped): continue
        used = set(); ok = True
        for g in alt:
            hit = None
            for i, c in enumerate(mapped):
                if i in used: continue
                roles = {READER_TO_CONVENTION.get(k, k): (v if isinstance(v, str) else v.get('term')) for k, v in g['roles'].items()}
                if c['predicate'] in g['predicate'] and c['polarity'] == g['polarity'] and c['roles'] == roles: hit = i; break
            if hit is None: ok = False; break
            used.add(hit)
        if ok: return 'CORRECT', 'matches a gold alternative of the frozen bank'
    return None, None


def verdict_of(text, out, gold, manual):
    if text in gold[0]:
        kind, item = gold[0][text]
        b1, classify = gold[1], gold[2]
        if kind in ('new_data', 'b1_sample'):
            v = b1.judge(item['expect'], item['lang'], out)['verdict']
            return {'correct': 'CORRECT', 'misread': 'WRONG', 'incomplete': 'INCOMPLETE'}.get(v, 'UNSURE'), 'b1.judge on %s: %s' % (kind, v)
        if kind == 'event_cross':
            if not item['readable']: return 'WRONG', 'the frozen expectation says the sentence is not to be read'
            ok, why = classify.agrees(item, {'clauses': out['clauses'], 'relations': out['relations']})
            return ('CORRECT', 'classify.agrees') if ok else ('WRONG', 'classify.agrees: ' + why)
        v, why = bank_verdict(item, out)
        if v: return v, why
    if text in manual: return manual[text]
    return 'UNCLASSIFIED', 'no gold and no manual line'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dev', required=True); ap.add_argument('--now', required=True); ap.add_argument('--out', required=True)
    ap.add_argument('--classified', required=True, help='manual verdicts: text<TAB>label<TAB>reason (read; may be empty)')
    ap.add_argument('--labels-out', default=None)
    a = ap.parse_args()
    root = os.path.realpath(os.environ.get('PYTHONPATH', '.').split(os.pathsep)[0])
    foreign = [m.__file__ for k, m in list(sys.modules.items()) if (k == 'verantyx' or k.startswith('verantyx.')) and getattr(m, '__file__', None)
               and not os.path.realpath(m.__file__).startswith(root + os.sep)]
    if foreign: print('ISOLATION FAILED', foreign); sys.exit(2)
    dev, now = rows_of(a.dev), rows_of(a.now)
    assert [r['text'] for r in dev] == [r['text'] for r in now], 'the two dumps are not on the same inputs'
    manual = {}
    cpath = Path(a.classified)
    if cpath.exists():
        for line in cpath.read_text(encoding='utf-8').splitlines():
            if line.strip() and not line.startswith('#'):
                parts = line.split('\t')
                manual[parts[0]] = (parts[1], parts[2] if len(parts) > 2 else '')
    gold = gold_sources()
    counts = collections.Counter(); out_rows, labels = [], []
    changed_as_is = changed_stripped = 0
    second = collections.Counter()
    for d, n in zip(dev, now):
        do, no = d['out'], n['out']
        if do == no: counts['same'] += 1; continue
        if 'error' in do or 'error' in no: kind = 'error_changed'
        elif not do['readable'] and not no['readable']:
            kind = 'reason_changed'
            extra = [r for r in no['abstain']['reasons'] if r not in do['abstain']['reasons']]
            for r in extra: second[r.split(':')[0]] += 1
        elif not do['readable'] and no['readable']: kind = 'false->readable'
        elif do['readable'] and not no['readable']: kind = 'readable->false'
        else:
            kind = 'changed'
            changed_as_is += 1
            if (do['clauses'], do['relations']) != (strip_basis(no)['clauses'], strip_basis(no)['relations']): changed_stripped += 1
        counts[kind] += 1
        row = {'text': d['text'], 'source': d['source'], 'kind': kind, 'dev': do, 'now': no}
        if kind == 'false->readable':
            label, why = verdict_of(d['text'], no, gold, manual)
            row['verdict'] = label; row['verdict_reason'] = why
            counts['verdict:' + label] += 1
            labels.append((d['text'], d['source'], label, why, no['clauses']))
        out_rows.append(row)
    Path(a.out).write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in out_rows), encoding='utf-8')
    if a.labels_out:
        Path(a.labels_out).write_text(''.join('%s\t%s\t%s\t%s\t%s\n' % (t, s, l, w, json.dumps(c, ensure_ascii=False)) for t, s, l, w, c in labels), encoding='utf-8')
    by_source = collections.Counter((r['source'], r['kind']) for r in out_rows)
    print('inputs=%d same=%d reason_changed=%d false->readable=%d readable->false=%d changed=%d error_changed=%d'
          % (len(dev), counts['same'], counts['reason_changed'], counts['false->readable'], counts['readable->false'], changed_stripped, counts['error_changed']))
    print('changed_with_source_fields_taken_out=%d changed_as_they_are=%d' % (changed_stripped, changed_as_is))
    print('verdicts: ' + json.dumps({k[8:]: v for k, v in sorted(counts.items()) if k.startswith('verdict:')}))
    print('second reasons added (reason_changed): ' + json.dumps(dict(sorted(second.items())), ensure_ascii=False))
    print('by source and kind: ' + json.dumps({'%s|%s' % k: v for k, v in sorted(by_source.items())}, ensure_ascii=False))
    for t, s, l, w, c in labels:
        if l in ('UNSURE', 'UNCLASSIFIED', 'WRONG', 'INCOMPLETE'): print('%s\t%s\t%s\t%s' % (l, s, t, w))
    bad = (counts['verdict:UNCLASSIFIED'] or changed_stripped or counts['readable->false'] or counts['error_changed']
           or counts['verdict:WRONG'] or counts['verdict:INCOMPLETE'])
    sys.exit(1 if bad else 0)


if __name__ == '__main__':
    main()
