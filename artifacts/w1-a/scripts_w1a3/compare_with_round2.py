# Compares the reader (x3 dumps) and the entry (entry_dump.py outputs) of the round-2 copy with the final tree.
# usage: compare_with_round2.py <x3_round2code.jsonl> <x3_after.jsonl> <x3_dev.jsonl> <entry_round2code.jsonl> <entry_now.jsonl> <out_dir>
import json, sys
r2p, nowp, devp, e2p, enp, out = sys.argv[1:7]
def load(p): return {json.loads(l)['text']: json.loads(l) for l in open(p, encoding='utf-8')}
def pairs(r): return {(n, v) for c in r['supported'] for n, v in c['roles']}
r2, now, dev = load(r2p), load(nowp), load(devp)
with open(out + '/r3_lost_vs_round2.tsv', 'w', encoding='utf-8') as f:
    f.write('sentence\trole\tvalue\tdev(191db17)も同じ組を supported\n')
    for t in now:
        for n, v in sorted(pairs(r2[t]) - pairs(now[t])):
            f.write('\t'.join((t, n, v, 'yes' if (n, v) in pairs(dev[t]) else 'no')) + '\n')
e2, en = load(e2p), load(enp)
with open(out + '/r3_entry_changes_vs_round2.tsv', 'w', encoding='utf-8') as f:
    f.write('text\tkind\tround-2 reading (clauses)\tround-3 abstain reason\n')
    for t, a in e2.items():
        b = en[t]
        if a['readable'] and not b['readable']:
            f.write('\t'.join((t, 'readable→false', json.dumps(a['clauses'], ensure_ascii=False)[:160], '; '.join(b['abstain']['reasons'])[:80])) + '\n')
        elif a['readable'] and b['readable'] and a['clauses'] != b['clauses']: f.write('\t'.join((t, 'changed', '', '')) + '\n')
        elif (not a['readable']) and b['readable']: f.write('\t'.join((t, 'false→readable', '', '')) + '\n')
