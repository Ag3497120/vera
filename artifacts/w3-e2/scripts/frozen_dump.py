"""W3-e2 measurement tool: every frozen reading_soundness jsonl line's input through read() (placement none / r9). Not a product file."""
import argparse, glob, json, os, sys
from pathlib import Path
TREE = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(TREE))
R9 = '/Users/motonisihikoudai/Projects/vera-impl/wt/W3-a6-S/build/coarse-W3a/full/r9/run2'
ap = argparse.ArgumentParser(); ap.add_argument('--out-dir', required=True); ap.add_argument('--exclude', default='w3e2_')
a = ap.parse_args()
from verantyx import semantic_read as SR, semantic_reader as R, constructions
constructions.discover()
root = os.path.realpath(str(TREE))
foreign = [m.__file__ for k, m in list(sys.modules.items()) if k.startswith('verantyx') and getattr(m, '__file__', None) and not os.path.realpath(m.__file__).startswith(root + os.sep)]
if foreign: print('ISOLATION FAILED', foreign); sys.exit(2)
rows, skipped = [], 0
for f in sorted(glob.glob(str(TREE / 'tests/reading_soundness/*.jsonl'))):
    if os.path.basename(f).startswith(a.exclude): continue
    for i, l in enumerate(open(f, encoding='utf-8')):
        if not l.strip(): continue
        r = json.loads(l)
        t = r.get('input', r.get('text'))
        if not isinstance(t, str): skipped += 1; continue
        rows.append((os.path.basename(f), i, t))
q = R.CoarseQuery(R9)
for name, pl in (('none', None), ('r9', q)):
    with open(os.path.join(a.out_dir, 'frozen_%s.jsonl' % name), 'w', encoding='utf-8') as fo:
        for fn, i, t in rows:
            try: out = SR.read(t, placement=pl)
            except Exception as e: out = {'error': type(e).__name__, 'code': getattr(e, 'code', None)}
            fo.write(json.dumps({'f': fn, 'i': i, 'text': t, 'out': out}, ensure_ascii=False, sort_keys=True, default=str) + '\n')
print('rows', len(rows), 'skipped', skipped)
