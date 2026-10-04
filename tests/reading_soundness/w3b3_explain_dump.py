#!/usr/bin/env python3
"""W3-b3: `semantic_read.clause_scope_explain_ja` for every input of a set (JSON lines {text, source}), one JSON line per input: {text, source, explain}. The summary counts, for the inputs
the path was triggered on, the kind of cut, the reasons it stopped (by their first part, and the head and the ellipsis reasons by their detail) and what it read (by kind of cut); and the
inputs the path did not trigger on (by reason), for the public inputs and for the new data apart. The placement: --placement DIR (the real one).
Usage: cd <tree> && PYTHONPATH=<tree> python tests/reading_soundness/w3b3_explain_dump.py --inputs FILE --placement DIR --out FILE.jsonl
"""
import argparse
import collections
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import w3b3_common as C


def group_of(source):
    return 'new_data' if source.startswith('w3b3_') else 'public'


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--inputs', required=True); ap.add_argument('--placement', required=True); ap.add_argument('--out', required=True)
    a = ap.parse_args()
    from verantyx import semantic_read as SR, semantic_reader as R, constructions
    constructions.discover()
    C.isolation()
    rows = []
    stat = {g: {'inputs': 0, 'triggered': collections.Counter(), 'read': collections.Counter(), 'stopped': collections.Counter(), 'stopped_detail': collections.Counter(),
                'not_triggered': collections.Counter()} for g in ('public', 'new_data')}
    for item in C.load_jsonl(a.inputs):
        text = item['text']
        if SR.detect_lang(text) != 'ja': continue
        ex = SR.clause_scope_explain_ja(text, R.CoarseQuery(a.placement))
        rows.append({'text': text, 'source': item['source'], 'explain': ex})
        s = stat[group_of(item['source'])]
        s['inputs'] += 1
        why = ex['reason'] or ''
        if ex['triggered']:
            kind = ex['cut']['kind']
            s['triggered'][kind] += 1
            if ex['read']: s['read'][kind] += 1
            else:
                s['stopped']['%s|%s' % (kind, why.split(':')[0])] += 1
                if why.split(':')[0] in ('HEAD_ROLE_UNDETERMINED', 'ELLIPSIS_UNDETERMINED', 'CLAUSE_FORM_NOT_READ', 'RELATION_TYPE_UNDETERMINED', 'CLAUSE_SCOPE_AMBIGUOUS'):
                    s['stopped_detail'][why.split(':')[0] + ':' + (why.split(':')[1].split('=')[0] if ':' in why else '')] += 1
        elif why != 'W3B3_NOT_TRIGGERED:not_reached':
            s['not_triggered'][why.split(':')[0] + (':' + why.split(':')[1].split('=')[0] if why.startswith('W3B3') else '')] += 1
        else:
            s['not_triggered']['not_reached'] += 1
    Path(a.out).write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
    for g, s in stat.items():
        print('group=%s japanese_inputs=%d triggered=%d read=%d' % (g, s['inputs'], sum(s['triggered'].values()), sum(s['read'].values())))
        for k in ('triggered', 'read', 'stopped', 'stopped_detail', 'not_triggered'):
            print('  %s_%s=%s' % (g, k, json.dumps(dict(sorted(s[k].items())), ensure_ascii=False)))


if __name__ == '__main__':
    main()
