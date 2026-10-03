# usage: entry_changes.py <entry_r3end.jsonl> <entry_now.jsonl> <out.tsv>   (outputs of entry_dump.py on the same input list)
import json, sys, collections
a_p, b_p, out = sys.argv[1:4]
def load(p): return {json.loads(l)['text']: json.loads(l) for l in open(p, encoding='utf-8')}
e2, en = load(a_p), load(b_p)
assert list(e2) == list(en), 'input lists differ'
cnt = collections.Counter(); reasons = collections.Counter()
with open(out, 'w', encoding='utf-8') as f:
    f.write('text\tkind\tround-3-end reading (clauses)\tnow: abstain reason\n')
    for t, a in e2.items():
        b = en[t]
        if a['readable'] and not b['readable']:
            r = '; '.join(b['abstain']['reasons'])[:120]
            f.write('\t'.join((t, 'readable→false', json.dumps(a['clauses'], ensure_ascii=False)[:160], r)) + '\n'); cnt['readable→false'] += 1; reasons[r] += 1
        elif a['readable'] and b['readable'] and a['clauses'] != b['clauses']: f.write('\t'.join((t, 'changed', '', '')) + '\n'); cnt['changed'] += 1
        elif (not a['readable']) and b['readable']: f.write('\t'.join((t, 'false→readable', '', '')) + '\n'); cnt['false→readable'] += 1
        elif (not a['readable']) and (not b['readable']) and a['abstain'] != b['abstain']:
            f.write('\t'.join((t, 'reason_changed', '; '.join(a['abstain']['reasons'])[:120], '; '.join(b['abstain']['reasons'])[:120])) + '\n'); cnt['reason_changed'] += 1
print('inputs', len(e2), 'readable_before', sum(a['readable'] for a in e2.values()), 'readable_now', sum(b['readable'] for b in en.values()))
print(dict(cnt))
for r, n in reasons.most_common(): print(n, r)
