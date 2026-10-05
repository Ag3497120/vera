"""W3-e2 S1-5 (not a product file): the Japanese sentences (ending with 。) written in the serve / fusion tests, read with the strict reader and the assume mode; counts the ones stage E2 would touch."""
import re, sys, glob
from pathlib import Path
TREE = Path(__file__).resolve().parents[3]; sys.path.insert(0, str(TREE))
from verantyx import semantic_read as SR, constructions
constructions.discover()
files = ['tests/test_serve_fusion.py', 'tests/test_w10f04_serve.py'] + sorted(glob.glob('tests/test_w10f05_*.py'))
sents = []
for f in files:
    for m in re.finditer(r"['\"]([^'\"\n]*?[぀-ヿ一-鿿][^'\"\n]*?。)['\"]", (TREE / f).read_text(encoding='utf-8')):
        sents.append((f, m.group(1)))
seen, touched = set(), 0
for f, t in sents:
    if t in seen: continue
    seen.add(t)
    try: o = SR.read_in_mode(t, mode='assume')
    except Exception as e: print('ERR', t, type(e).__name__); continue
    if o.get('read_mode') == 'assumed' or any(str(r).startswith('ASSUMPTION_') for r in ((o.get('abstain') or {}).get('reasons') or [])):
        touched += 1; print('TOUCHED', f, t, o.get('read_mode'))
print('sentences', len(seen), 'touched_by_stage_E2', touched)
