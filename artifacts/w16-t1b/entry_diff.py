"""入口の前後を行ごとに比べる。usage: entry_diff.py BEFORE AFTER OUT.tsv
same / read_to_abstain / abstain_reason_changed / abstain_to_read / other に分け、件数を標準出力、変わった行を全件 TSV。"""
import json, sys, collections
from pathlib import Path
def load(p): return [json.loads(l) for l in Path(p).read_text(encoding='utf-8').splitlines() if l.strip()]
B, A = load(sys.argv[1]), load(sys.argv[2])
assert len(B) == len(A), (len(B), len(A))
cnt = collections.Counter(); rows = ['idx\tclass\ttext\tbefore_readable\tafter_readable\tbefore_reasons\tafter_reasons\tafter_unsupported']
def reasons(o): return json.dumps((o.get('abstain') or {}).get('reasons'), ensure_ascii=False)
def uns(o): return json.dumps([u.get('reasons') for u in (o.get('unsupported') or [])], ensure_ascii=False)
for i, (b, a) in enumerate(zip(B, A)):
    assert b['text'] == a['text']
    if json.dumps(b['out'], sort_keys=True, ensure_ascii=False) == json.dumps(a['out'], sort_keys=True, ensure_ascii=False):
        cnt['same'] += 1; continue
    br, ar = b['out'].get('readable'), a['out'].get('readable')
    if br and not ar: c = 'read_to_abstain'
    elif not br and not ar: c = 'abstain_reason_changed'
    elif not br and ar: c = 'abstain_to_read'
    else: c = 'other'
    cnt[c] += 1
    rows.append('\t'.join([str(i), c, b['text'], str(br), str(ar), reasons(b['out']), reasons(a['out']), uns(a['out'])]))
Path(sys.argv[3]).write_text('\n'.join(rows) + '\n', encoding='utf-8')
print(dict(cnt), 'total', len(B))
