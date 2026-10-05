"""W3-e2 V2 measurement (not a product file): the frozen rows through read_in_mode(mode='assume'). One line per file: rows assumed_expected assumed_ok abstain_expected abstain_ok wrong_assumption wrong_source.
`documents` rows (source (c)) are in assumed_expected and ALSO counted apart (documents_rows / documents_ok)."""
import argparse, importlib.util, json, os, sys
from pathlib import Path
TREE = Path(__file__).resolve().parents[3]; sys.path.insert(0, str(TREE))
ap = argparse.ArgumentParser(); ap.add_argument('--data', required=True); ap.add_argument('--r8'); ap.add_argument('--r9'); ap.add_argument('--out', required=True)
ap.add_argument('--verbose', action='store_true')
a = ap.parse_args()
spec = importlib.util.spec_from_file_location('t_w3e2', str(TREE / 'tests/test_semantic_read_w3e2.py'))
T = importlib.util.module_from_spec(spec); spec.loader.exec_module(T)
if a.r8: T.PLACEMENTS['r8'] = a.r8
if a.r9: T.PLACEMENTS['r9'] = a.r9
res, lines = {}, []
for f in a.data.split(','):
    rows = [json.loads(l) for l in open(f, encoding='utf-8') if l.strip()]
    c = dict(rows=len(rows), assumed_expected=0, assumed_ok=0, abstain_expected=0, abstain_ok=0, wrong_assumption=0, wrong_source=0, documents_rows=0, documents_ok=0, failures=[])
    for r in rows:
        out, _ = T.run_row(r)
        ok, why = T.judge(r, out)
        docs = bool(r['sources'].get('documents'))
        if docs:
            c['documents_rows'] += 1; c['documents_ok'] += int(ok)
        if r['expect']['mode'] == 'assumed':
            c['assumed_expected'] += 1; c['assumed_ok'] += int(ok)       # r1 review 4: the documents rows are in the denominator
        else:
            c['abstain_expected'] += 1; c['abstain_ok'] += int(ok)
        if not ok:
            if out.get('read_mode') == 'assumed':
                exp = r['expect']['assumptions']
                if exp and out['assumptions'][0]['assumed'] != exp[0]['assumed']: c['wrong_assumption'] += 1
                elif exp and out['assumptions'][0]['source'] != exp[0]['source']: c['wrong_source'] += 1
                elif not exp: c['wrong_assumption'] += 1
            c['failures'].append({'id': r['id'], 'input': r['input'], 'why': why})
    res[os.path.basename(f)] = c
    lines.append('%s rows=%d assumed_expected=%d assumed_ok=%d abstain_expected=%d abstain_ok=%d wrong_assumption=%d wrong_source=%d documents_rows=%d documents_ok=%d' % (
        os.path.basename(f), c['rows'], c['assumed_expected'], c['assumed_ok'], c['abstain_expected'], c['abstain_ok'], c['wrong_assumption'], c['wrong_source'], c['documents_rows'], c['documents_ok']))
    if a.verbose:
        for x in c['failures']: lines.append('   FAIL %s %s %s' % (x['id'], x['input'], x['why']))
json.dump(res, open(a.out, 'w'), ensure_ascii=False, indent=1)
print('\n'.join(lines))
