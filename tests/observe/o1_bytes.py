"""O1: the same (structure, viewpoint, state) gives byte-identical output, whatever the hash seed.

For each hash seed a CHILD process (PYTHONHASHSEED set) runs every frozen case twice through `observe.run_entry` (the function behind the
command line), each time with a fresh copy of the ledger; a two-turn case runs both turns each time. The parent compares run 1 with run 2 of
each child and the children with each other.

    python tests/observe/o1_bytes.py --cases tests/observe/data/viewpoints.jsonl --seeds 0 4242 --out artifacts/w3-c/o1_bytes.txt
"""
import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import ARTIFACTS, DATA, TREE, build_small_index, entry_kwargs, load_cases    # noqa: E402


def child(args):
    from verantyx import observe
    cases = load_cases(args.cases) + (load_cases(DATA / 'viewpoints_add1.jsonl') + load_cases(DATA / 'viewpoints_r2.jsonl') if args.with_add1 else [])    # r2: round 2
    rows = []
    for run in (1, 2):
        for case in cases:
            kw = entry_kwargs(case, Path(args.workdir) / ('run%d' % run), args.index)
            outs = []
            for _turn in range(case.get('turns', 1)):
                res = observe.run_entry(**kw)
                outs.append(res.stdout if res.exit_code == 0 else 'EXIT %s %s' % (res.exit_code, json.dumps(res.error)))
            rows.append({'case': case['case'], 'run': run, 'outputs': outs})
    Path(args.child_out).write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--cases', default=str(DATA / 'viewpoints.jsonl'))
    ap.add_argument('--seeds', nargs='+', default=['0', '4242'])
    ap.add_argument('--out')
    ap.add_argument('--no-add1', dest='with_add1', action='store_false')
    ap.add_argument('--child', action='store_true')
    ap.add_argument('--workdir', default=str(ARTIFACTS / 'work_o1'))
    ap.add_argument('--child-out')
    ap.add_argument('--index')
    args = ap.parse_args(argv)
    if args.child:
        return child(args)
    index = build_small_index()
    per_seed = {}
    for seed in args.seeds:
        out = ARTIFACTS / ('o1_child_seed%s.jsonl' % seed)
        env = {'HOME': os.environ.get('HOME', ''), 'PATH': '/usr/bin:/bin', 'PYTHONDONTWRITEBYTECODE': '1', 'PYTHONPATH': str(TREE), 'PYTHONHASHSEED': seed}
        cmd = [sys.executable, str(Path(__file__)), '--child', '--cases', args.cases, '--workdir', str(Path(args.workdir) / ('seed' + seed)),
               '--child-out', str(out), '--index', str(index)] + ([] if args.with_add1 else ['--no-add1'])
        subprocess.run(cmd, env=env, check=True, cwd=str(TREE))
        per_seed[seed] = [json.loads(l) for l in out.read_text(encoding='utf-8').splitlines()]
    n = len(per_seed[args.seeds[0]]) // 2
    mismatch = []
    for seed, rows in per_seed.items():
        run1 = {r['case']: r['outputs'] for r in rows if r['run'] == 1}
        run2 = {r['case']: r['outputs'] for r in rows if r['run'] == 2}
        for case in run1:
            if run1[case] != run2[case]: mismatch.append('%s: run 1 and run 2 differ under PYTHONHASHSEED=%s' % (case, seed))
    base = {r['case']: r['outputs'] for r in per_seed[args.seeds[0]] if r['run'] == 1}
    for seed in args.seeds[1:]:
        other = {r['case']: r['outputs'] for r in per_seed[seed] if r['run'] == 1}
        for case in base:
            if base[case] != other[case]: mismatch.append('%s: PYTHONHASHSEED=%s and %s differ' % (case, args.seeds[0], seed))
    lines = ['checked %d, mismatch %d' % (n, len(mismatch)), 'hash seeds %s, each case run twice per seed' % ', '.join(args.seeds)] + mismatch
    if args.out: Path(args.out).write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print('\n'.join(lines))
    return 0 if not mismatch else 1


if __name__ == '__main__':
    raise SystemExit(main())
