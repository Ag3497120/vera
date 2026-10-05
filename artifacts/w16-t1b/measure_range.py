"""両データの全行を ask と semantic_read で流し、TSV に。usage: measure_range.py OUT.tsv"""
import json, sys, contextlib, io, tempfile, os
from pathlib import Path
from verantyx import cli, semantic_read
ROOT = Path(__file__).resolve().parents[2]
TMP = Path(os.environ['W16_TMP'])
def ask(doc, q):
    d = Path(tempfile.mkdtemp(dir=TMP)); (d/'d.txt').write_text(doc+'\n', encoding='utf-8')
    b = io.StringIO()
    with contextlib.redirect_stdout(b):
        cli.main(['--store', str(d/'st.json'), 'ask', '--mode', 'round5', '--document', str(d/'d.txt'), '--', q])
    return json.loads(b.getvalue())
out = []
for fn in ('w16t1b_modality.jsonl', 'w16t1b_title.jsonl'):
    for l in open(ROOT/'tests'/'reading_soundness'/fn, encoding='utf-8'):
        r = json.loads(l)
        qs = r.get('questions') or [r['question']]
        rd = semantic_read.read(r['document'], placement=None)
        reasons = [x for u in (rd.get('unsupported') or []) for x in (u.get('reasons') or [])]
        for q in qs:
            q = q['q'] if isinstance(q, dict) else q
            o = ask(r['document'], q)
            out.append('\t'.join([r['id'], r['kind'], r['document'], q, str(o.get('verdict')), json.dumps(o.get('values'), ensure_ascii=False), str(o.get('reason')), str(rd.get('readable')), ','.join(reasons)]))
Path(sys.argv[1]).write_text('id\tkind\tdocument\tquestion\tverdict\tvalues\treason\treadable\tunsupported_reasons\n' + '\n'.join(out) + '\n', encoding='utf-8')
print(len(out))
