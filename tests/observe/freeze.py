"""Record the sha256 of data files and the time (the `date` command's output) in tests/observe/data/FROZEN.json under a stage name.

    python tests/observe/freeze.py --stage inputs --date "$(date '+%Y-%m-%d %H:%M:%S %z')" PATH...
Adds an entry; an existing stage name is refused (a frozen stage is never rewritten).
"""
import argparse
import hashlib
import json
from pathlib import Path

DATA = Path(__file__).resolve().parent / 'data'


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--stage', required=True)
    ap.add_argument('--date', required=True)
    ap.add_argument('--note', default='')
    ap.add_argument('paths', nargs='*')
    args = ap.parse_args(argv)
    frozen_path = DATA / 'FROZEN.json'
    frozen = json.loads(frozen_path.read_text(encoding='utf-8')) if frozen_path.exists() else {'stages': {}}
    if args.stage in frozen['stages']:
        raise SystemExit('stage %s is already frozen' % args.stage)
    files = {}
    for p in args.paths:
        path = DATA / p
        files[p] = hashlib.sha256(path.read_bytes()).hexdigest()
    frozen['stages'][args.stage] = {'date': args.date, 'note': args.note, 'files': files}
    frozen_path.write_text(json.dumps(frozen, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    print('froze', args.stage, args.date, len(files), 'files')


if __name__ == '__main__':
    main()
