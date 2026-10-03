"""Shared helpers of the W3-c measurement tools: the frozen cases, the small index, the arguments of one case for `observe.run_entry`."""
import json
import shutil
import sys
from pathlib import Path

TREE = Path(__file__).resolve().parents[2]
DATA = TREE / 'tests' / 'observe' / 'data'
ARTIFACTS = TREE / 'artifacts' / 'w3-c'
INDEX_SMALL = ARTIFACTS / 'index_small'
if str(TREE) not in sys.path:
    sys.path.insert(0, str(TREE))


def load_cases(path=None):
    path = Path(path) if path else DATA / 'viewpoints.jsonl'
    return [json.loads(l) for l in path.read_text(encoding='utf-8').splitlines() if l.strip()]


def build_small_index(out=None, corpus_root=None):
    """Build the small `pro` index from the frozen corpus root (idempotent: a database that is there is rebuilt only by the builder's own rule)."""
    from tools import build_p4_corpus_index as bi
    out = Path(out) if out else INDEX_SMALL
    root = Path(corpus_root) if corpus_root else DATA / 'corpus_root'
    manifest = out.parent / (out.name + '_manifest.json')
    code = bi.main(['--root', str(root), '--out', str(out), '--manifest', str(manifest), '--family', 'pro'])
    if code != 0:
        raise SystemExit('index build failed: %s' % code)
    return out


def entry_kwargs(case, workdir, index_dir=None):
    """The keyword arguments of `observe.run_entry` for one case. A ledger is copied into `workdir` (the frozen file is never written)."""
    kw = {'anchor_kind': case['anchor'].get('kind', 'seed'), 'direction': case['direction'], 'range_': case['range']}
    if 'text' in case['anchor']:
        kw['anchor_text'] = case['anchor']['text']
    else:
        kw['anchor_record'] = case['anchor']['record']
    if case.get('structure'):
        kw['structure_path'] = str(DATA / case['structure'])
    if case.get('placement'):
        kw['placement_path'] = str(DATA / case['placement'])
    if case.get('index'):
        kw['index_root'] = str(index_dir or INDEX_SMALL)
        kw['index_families'] = tuple(case.get('families') or ('pro',))
    else:
        kw['no_index'] = True
    if case.get('ledger'):
        work = Path(workdir)
        work.mkdir(parents=True, exist_ok=True)
        dst = work / (case['case'] + '.ledger.jsonl')
        shutil.copyfile(DATA / 'ledgers' / (case['ledger'] + '.jsonl'), dst)
        kw['ledger_path'] = str(dst)
    return kw
