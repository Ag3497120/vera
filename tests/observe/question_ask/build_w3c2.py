"""W3-c4: re-use the W3-c2 test data (tests/observe/question/) for `vera ask`: docs/QDnn.jsonl -> w3c2/QDnn.txt (one sentence per line, in order), and
questions.jsonl -> w3c2/questions.jsonl (docs: ["QDnn.txt"], evidence `QDnn-Smm` -> `QDnn.txt#<mm>:1`) and w3c2/questions_corrected.jsonl (the W3-c2 corrections applied).
The W3-c2 files are only read. Does not import verantyx."""
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE.parent / 'question'
OUT = HERE / 'w3c2'


def sid_map(sid, order):
    m = re.fullmatch(r'(QD\d\d)-S(\d\d)', sid)
    assert m, sid
    doc, n = m.group(1), int(m.group(2))
    assert order[doc][n - 1] == sid, (sid, order[doc][n - 1])    # S numbering is the line order
    return '%s.txt#%d:1' % (doc, n)


def main():
    OUT.mkdir(exist_ok=True)
    order = {}
    for p in sorted((SRC / 'docs').glob('QD*.jsonl')):
        rows = [json.loads(l) for l in p.read_text(encoding='utf-8').splitlines() if l.strip()]
        order[p.stem] = [r['id'] for r in rows]
        (OUT / (p.stem + '.txt')).write_text(''.join(r['text'] + '\n' for r in rows), encoding='utf-8')
    corr = {}
    for l in (SRC / 'corrections.jsonl').read_text(encoding='utf-8').splitlines():
        if l.strip():
            c = json.loads(l); corr[c['id']] = c['after']
    plain, fixed = [], []
    for l in (SRC / 'questions.jsonl').read_text(encoding='utf-8').splitlines():
        if not l.strip(): continue
        q = json.loads(l)
        def conv(truth):
            t = dict(truth)
            t['evidence'] = [sid_map(s, order) for s in truth.get('evidence', [])]
            t['extension_support'] = [sid_map(s, order) for s in truth.get('extension_support', [])]
            t['unread_support'] = [sid_map(s, order) for s in truth.get('unread_support', [])]
            return t
        base = {'id': q['id'], 'docs': [q['doc'] + '.txt'], 'text': q['text'], 'lang': q.get('lang'), 'hole': q.get('hole'), 'direction': q.get('direction', ''),
                'category': 'w3c2', 'note': q.get('note', '')}
        plain.append(dict(base, truth=conv(q['truth'])))
        fixed.append(dict(base, truth=conv(dict(q['truth'], **corr[q['id']]) if q['id'] in corr else q['truth'])))
    (OUT / 'questions.jsonl').write_text(''.join(json.dumps(x, ensure_ascii=False) + '\n' for x in plain), encoding='utf-8')
    (OUT / 'questions_corrected.jsonl').write_text(''.join(json.dumps(x, ensure_ascii=False) + '\n' for x in fixed), encoding='utf-8')
    print(len(plain), len(fixed), len(corr))


if __name__ == '__main__':
    main()
