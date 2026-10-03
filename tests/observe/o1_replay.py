"""O1: replay from the ledger. Every case that has a ledger runs its turn(s) through `observe.run_entry` on a copy of the frozen ledger; the observation
events the entry appended are then replayed (`observe.replay`: the ledger as it was BEFORE that turn, same structure) and the sha256 of the output is compared
with the one recorded in the event.

    python tests/observe/o1_replay.py --cases tests/observe/data/viewpoints.jsonl --out artifacts/w3-c/o1_replay.txt
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import ARTIFACTS, DATA, build_small_index, entry_kwargs, load_cases    # noqa: E402


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--cases', default=str(DATA / 'viewpoints.jsonl'))
    ap.add_argument('--out')
    ap.add_argument('--workdir', default=str(ARTIFACTS / 'work_replay'))
    args = ap.parse_args(argv)
    from verantyx import observe, salience
    index = build_small_index()
    replayed = mismatch = 0
    bad = []
    for case in load_cases(args.cases) + load_cases(DATA / 'viewpoints_add1.jsonl') + load_cases(DATA / 'viewpoints_r2.jsonl'):
        if not case.get('ledger'): continue
        kw = entry_kwargs(case, args.workdir, index)
        before = len(salience.load_jsonl(kw['ledger_path']))
        for _turn in range(case.get('turns', 1)):
            res = observe.run_entry(**kw)
            assert res.exit_code == 0, (case['case'], res.error)
        structure = observe.build_structure(structure_path=kw.get('structure_path'), index_root=kw.get('index_root'),
                                            index_families=kw.get('index_families', ('pro',)), no_index=kw.get('no_index', False),
                                            placement_path=kw.get('placement_path'))
        events = list(salience.load_jsonl(kw['ledger_path']).events())
        for ev in events[before:]:
            if ev['kind'] != 'observation': continue
            replayed += 1
            if not observe.replay(events, ev, structure):
                mismatch += 1
                bad.append('%s: replay of %s differs' % (case['case'], ev['id']))
    lines = ['replayed %d, digest_mismatch %d' % (replayed, mismatch)] + bad
    if args.out: Path(args.out).write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print('\n'.join(lines))
    return 0 if mismatch == 0 and replayed > 0 else 1


if __name__ == '__main__':
    raise SystemExit(main())
