#!/usr/bin/env python3
"""W3-b2: the entry's output of W3-b2 against the output of W3-b1 (the tree of the base commit), input by input (two dumps of w3b1_entry_dump.py, same inputs in the same order,
both with the placement). The kinds (K94: the only differences allowed are a sentence read now and a sentence a frame stopped):
  same                   the same output
  newly_read             the base abstains, now it reads          (EVERY one gets a verdict: CORRECT / WRONG / INCOMPLETE / UNSURE)
  frame_stopped          the base reads, now it abstains with a second reason that begins with PLACEMENT_FRAME_ (the frame of a CONFIRMED predicate)
  read_to_abstain_other  the base reads, now it abstains for another reason
  changed                both read and the output differs
  refusal_changed        both abstain and the output differs
  error_changed          one of the two is a typed error object and they differ
Everything but `same` is written to --out as {text, source, kind, before, after[, verdict]}. A newly_read input gets its verdict from, in this order: the data it comes from
(w3b2_*.jsonl, ja_r8 / ja_r9 / ja_r10 / en_r4 / the three B1 samples -> tools.bank_score.v2.b1.judge; the event cross sentences -> tests/event_cross/classify.agrees; the frozen
Japanese banks -> their gold alternatives, role names of the reader mapped to the convention's), else from the manual file --manual (text<TAB>label<TAB>reason, written by a person who
read the sentence and the new reading). No verdict at all -> UNCLASSIFIED. Exit code 1 when anything is UNCLASSIFIED, read_to_abstain_other / changed / refusal_changed / error_changed is
above 0, or a verdict is WRONG or INCOMPLETE. UNSURE is listed and does not fail (the reviewer decides). frame_stopped is listed in full.
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
JA_BANKS = ('table7.jsonl', 'ja.jsonl', 'ja_r2.jsonl', 'ja_r3.jsonl', 'ja_r4.jsonl', 'ja_r5.jsonl', 'ja_r6.jsonl')
READER_TO_CONVENTION = {'origin': 'source', 'location': 'place', 'direction': 'goal', 'means': 'instrument', 'limit': 'goal'}


def rows_of(path):
    return [json.loads(l) for l in Path(path).read_text(encoding='utf-8').splitlines() if l.strip()]


def gold_sources():
    from tools.bank_score.v2 import b1
    import classify
    src = {}
    for name in ('w3b2_frame.jsonl', 'w3b2_multiple.jsonl', 'w3b2_determiner.jsonl', 'w3b2_no.jsonl', 'ja_r8.jsonl', 'en_r4.jsonl', 'ja_r9.jsonl', 'ja_r10.jsonl'):
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
    ap.add_argument('--before', required=True); ap.add_argument('--after', required=True); ap.add_argument('--out', required=True)
    ap.add_argument('--manual', required=True, help='manual verdicts: text<TAB>label<TAB>reason (read; may be empty)')
    ap.add_argument('--labels-out', default=None)
    a = ap.parse_args()
    root = os.path.realpath(os.environ.get('PYTHONPATH', '.').split(os.pathsep)[0])
    foreign = [m.__file__ for k, m in list(sys.modules.items()) if (k == 'verantyx' or k.startswith('verantyx.')) and getattr(m, '__file__', None)
               and not os.path.realpath(m.__file__).startswith(root + os.sep)]
    if foreign: print('ISOLATION FAILED', foreign); sys.exit(2)
    before, after = rows_of(a.before), rows_of(a.after)
    assert [r['text'] for r in before] == [r['text'] for r in after], 'the two dumps are not on the same inputs'
    manual = {}
    cpath = Path(a.manual)
    if cpath.exists():
        for line in cpath.read_text(encoding='utf-8').splitlines():
            if line.strip() and not line.startswith('#'):
                parts = line.split('\t')
                manual[parts[0]] = (parts[1], parts[2] if len(parts) > 2 else '')
    gold = gold_sources()
    counts = collections.Counter(); out_rows, labels = [], []
    second = collections.Counter()
    for d, n in zip(before, after):
        do, no = d['out'], n['out']
        if do == no: counts['same'] += 1; continue
        if 'error' in do or 'error' in no: kind = 'error_changed'
        elif not do['readable'] and not no['readable']: kind = 'refusal_changed'
        elif not do['readable'] and no['readable']: kind = 'newly_read'
        elif do['readable'] and not no['readable']:
            rs = no['abstain']['reasons']
            kind = 'frame_stopped' if len(rs) >= 2 and rs[1].startswith('PLACEMENT_FRAME_') else 'read_to_abstain_other'
            if kind == 'frame_stopped': second[rs[1].split(':')[0]] += 1
        else: kind = 'changed'
        counts[kind] += 1
        row = {'text': d['text'], 'source': d['source'], 'kind': kind, 'before': do, 'after': no}
        if kind == 'newly_read':
            label, why = verdict_of(d['text'], no, gold, manual)
            row['verdict'] = label; row['verdict_reason'] = why
            counts['verdict:' + label] += 1
            labels.append((d['text'], d['source'], label, why, no['clauses']))
        out_rows.append(row)
    Path(a.out).write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in out_rows), encoding='utf-8')
    if a.labels_out:
        Path(a.labels_out).write_text(''.join('%s\t%s\t%s\t%s\t%s\n' % (t, s, l, w, json.dumps(c, ensure_ascii=False)) for t, s, l, w, c in labels), encoding='utf-8')
    by_source = collections.Counter((r['source'], r['kind']) for r in out_rows)
    print('inputs=%d same=%d newly_read=%d frame_stopped=%d read_to_abstain_other=%d changed=%d refusal_changed=%d error_changed=%d'
          % (len(before), counts['same'], counts['newly_read'], counts['frame_stopped'], counts['read_to_abstain_other'], counts['changed'], counts['refusal_changed'], counts['error_changed']))
    print('verdicts: ' + json.dumps({k[8:]: v for k, v in sorted(counts.items()) if k.startswith('verdict:')}))
    print('frame_stopped by reason: ' + json.dumps(dict(sorted(second.items())), ensure_ascii=False))
    print('by source and kind: ' + json.dumps({'%s|%s' % k: v for k, v in sorted(by_source.items())}, ensure_ascii=False))
    for t, s, l, w, c in labels:
        if l in ('UNSURE', 'UNCLASSIFIED', 'WRONG', 'INCOMPLETE'): print('%s\t%s\t%s\t%s' % (l, s, t, w))
    for r in out_rows:
        if r['kind'] in ('frame_stopped', 'read_to_abstain_other', 'changed', 'refusal_changed', 'error_changed'): print('%s\t%s\t%s' % (r['kind'], r['source'], r['text']))
    bad = (counts['verdict:UNCLASSIFIED'] or counts['read_to_abstain_other'] or counts['changed'] or counts['refusal_changed'] or counts['error_changed']
           or counts['verdict:WRONG'] or counts['verdict:INCOMPLETE'])
    sys.exit(1 if bad else 0)


if __name__ == '__main__':
    main()
