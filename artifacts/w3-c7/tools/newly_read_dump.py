#!/usr/bin/env python3
"""W3-c7: every sentence of the data files that stage C7 reads (the base refused it): sentence, path, edges, clauses, relations and the crosses of event_cross.build_crosses (one JSON line each)."""
import argparse, dataclasses, json, os, sys
from pathlib import Path
TREE = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(TREE))


def plain(x):
    if dataclasses.is_dataclass(x): return {k: plain(v) for k, v in dataclasses.asdict(x).items()}
    if isinstance(x, dict): return {k: plain(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)): return [plain(v) for v in x]
    return x


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--placement', required=True); ap.add_argument('--data', required=True); ap.add_argument('--out', required=True)
    a = ap.parse_args()
    from verantyx import semantic_read as SR, semantic_reader as R, event_cross as EC, constructions
    constructions.discover()
    root = os.path.realpath(os.environ.get('PYTHONPATH', '.').split(os.pathsep)[0])
    if [m for k, m in sys.modules.items() if k.startswith('verantyx') and getattr(m, '__file__', None) and not os.path.realpath(m.__file__).startswith(root + os.sep)]:
        print('ISOLATION FAILED'); sys.exit(2)
    q = R.CoarseQuery(a.placement)
    lines = []
    for path in a.data.split(','):
        for l in Path(path).read_text(encoding='utf-8').splitlines():
            if not l.strip(): continue
            r = json.loads(l)
            ex = R.w3c7_explain_ja(r['input'], q)
            if not ex['read']: continue
            out = SR.read(r['input'], placement=q)
            cr = EC.build_crosses(out)
            lines.append(json.dumps({'id': r['id'], 'text': r['input'], 'path': ex['path'], 'edges': ex['edges'], 'clauses': out['clauses'], 'relations': out['relations'],
                                     'cross_status': cr.status, 'crosses': plain(cr.crosses)}, ensure_ascii=False))
    Path(a.out).write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print('read=%d' % len(lines))


if __name__ == '__main__':
    main()
