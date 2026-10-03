#!/usr/bin/env python3
"""W3-b2: the event cross with the real placement as its lookup (verantyx.event_cross.default_lookup(<placement>)): how many arms AGREE / DISAGREE / are NOT_CHECKED
(by reason), and every DISAGREE (sentence, role, value, expected types, observed types). Inputs: the sentences the entry reads (readable true, with the placement) among
the set of w3b1_entry_dump.py (--inputs FILE, JSON lines {text, source}); the groups are the cross sentences (sentences_*.jsonl), the new data (ja_r8 / en_r4) and the rest (x3 and the
English / B1 files). The placement: --placement DIR, else the variable VERA_PLACEMENT. Loaded verantyx* modules must be under PYTHONPATH (else exit 2).
The same count as w3b1_events_measure.py with the verdict AGREE_ALL_CANDIDATES and the fillers that got `flags.determiner` counted, and the new data of W3-b2 as a group
of its own (the W3-b1 script counts three fixed verdicts and would stop with a KeyError).
Usage: cd <tree> && PYTHONPATH=<tree> python tests/reading_soundness/w3b2_events_measure.py --inputs FILE --out JSON --placement DIR
"""
import argparse, collections, json, os, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--inputs', required=True); ap.add_argument('--out', required=True); ap.add_argument('--placement')
    a = ap.parse_args()
    from verantyx import event_cross as EC, semantic_read as SR, constructions
    constructions.discover()
    root = os.path.realpath(os.environ.get('PYTHONPATH', '.').split(os.pathsep)[0])
    foreign = [m.__file__ for k, m in list(sys.modules.items()) if (k == 'verantyx' or k.startswith('verantyx.'))
               and getattr(m, '__file__', None) and not os.path.realpath(m.__file__).startswith(root + os.sep)]
    if foreign: print('ISOLATION FAILED', foreign); sys.exit(2)
    path = a.placement or os.environ.get('VERA_PLACEMENT')
    if not path: print('no placement: give --placement or VERA_PLACEMENT'); sys.exit(2)
    inputs = [json.loads(l) for l in Path(a.inputs).read_text(encoding='utf-8').splitlines() if l.strip()]
    def group(source):
        if source.startswith('sentences_'): return 'event_cross_sentences'
        if source.startswith('w3b2_'): return 'w3b2_data'
        if source in ('ja_r8.jsonl', 'en_r4.jsonl', 'ja_r9.jsonl', 'ja_r10.jsonl'): return 'new_data'
        return 'rest'
    stats = collections.defaultdict(lambda: {'sentences_read': 0, 'with_a_cross_of_a_typed_clause': 0, 'arms': 0, 'AGREE': 0, 'DISAGREE': 0, 'NOT_CHECKED': 0, 'AGREE_ALL_CANDIDATES': 0, 'fillers_with_a_determiner': 0, 'not_checked_by_reason': collections.Counter(),
                                              'lookup_ids': collections.Counter()})
    disagree, all_candidates = [], []
    for item in inputs:
        lookup = EC.default_lookup(path)
        out = EC.attach_events(SR.read(item['text'], placement=path), lookup)
        if not out['readable']: continue
        g = stats[group(item['source'])]
        g['sentences_read'] += 1
        ev = out['events']
        g['lookup_ids'][ev['lookup']['id']] += 1
        if any('role_basis' in c or 'predicate_basis' in c or 'role_flags' in c for c in out['clauses']): g['with_a_cross_of_a_typed_clause'] += 1
        for cross in ev['crosses']:
            for role, arm in cross['arms'].items():
                ag = arm['agreement']; g['arms'] += 1; g[ag['verdict']] += 1
                if ag['verdict'] == 'NOT_CHECKED': g['not_checked_by_reason'][ag['reason']] += 1
                g['fillers_with_a_determiner'] += sum(1 for f in arm['fillers'] if 'determiner' in f['flags'])
                if ag['verdict'] == 'AGREE_ALL_CANDIDATES':
                    all_candidates.append({'group': group(item['source']), 'source': item['source'], 'sentence': item['text'], 'role': role, 'value': [f['surface'] for f in arm['fillers']],
                                           'expected': ag['expected'], 'observed': ag['observed']})
                if ag['verdict'] == 'DISAGREE':
                    disagree.append({'group': group(item['source']), 'source': item['source'], 'sentence': item['text'], 'role': role,
                                     'value': [f['surface'] for f in arm['fillers']], 'expected': ag['expected'], 'observed': ag['observed'],
                                     'typed_by_the_entry': role in ((out['clauses'][cross['index']].get('role_basis')) or {})})
    doc = {'agree_all_candidates': all_candidates, 'placement_sha_in_lookup_id_example': next(iter(next(iter(stats.values()))['lookup_ids']), None) if stats else None, 'groups': {}, 'disagree': disagree}
    for k, v in stats.items():
        doc['groups'][k] = dict(v, not_checked_by_reason=dict(sorted(v['not_checked_by_reason'].items())), lookup_ids=dict(v['lookup_ids']))
    Path(a.out).write_text(json.dumps(doc, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    for k in sorted(doc['groups']):
        v = doc['groups'][k]
        print('%s: sentences_read=%d typed=%d arms=%d AGREE=%d AGREE_ALL_CANDIDATES=%d DISAGREE=%d NOT_CHECKED=%d fillers_with_a_determiner=%d %s' % (k, v['sentences_read'], v['with_a_cross_of_a_typed_clause'], v['arms'], v['AGREE'], v['AGREE_ALL_CANDIDATES'], v['DISAGREE'], v['NOT_CHECKED'], v['fillers_with_a_determiner'],
                                                                                              json.dumps(v['not_checked_by_reason'], ensure_ascii=False)))
    print('AGREE_ALL_CANDIDATES total=%d' % len(all_candidates))
    for d in all_candidates: print('AGREE_ALL_CANDIDATES\t%s\t%s\t%s\t%s\texpected=%s\tobserved=%s' % (d['group'], d['sentence'], d['role'], d['value'], d['expected'], d['observed']))
    print('DISAGREE total=%d' % len(disagree))
    for d in disagree: print('DISAGREE\t%s\t%s\t%s\t%s\texpected=%s\tobserved=%s\ttyped_by_the_entry=%s' % (d['group'], d['sentence'], d['role'], d['value'], d['expected'], d['observed'], d['typed_by_the_entry']))


if __name__ == '__main__':
    main()
