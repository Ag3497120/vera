"""W3-c4: write FROZEN.json = sha256 of every frozen data file (docs, placement, questions, w3c2, b2like, the two build scripts, check_lines.py) and frozen_at
(the `date` output passed with --frozen-at). Refuses to overwrite an existing FROZEN.json (a frozen file is changed only through corrections.jsonl)."""
import argparse
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
FROZEN_GLOBS = ('docs/**/*.txt', 'b2like/docs/*.txt', 'b2like/questions.jsonl', 'w3c2/*.txt', 'w3c2/*.jsonl', 'placement_ask.json', 'questions.jsonl',
                'build_data.py', 'build_w3c2.py', 'check_lines.py')


def frozen_files():
    out = set()
    for g in FROZEN_GLOBS: out.update(p for p in HERE.glob(g) if p.is_file())
    return sorted(out)


def digest(p): return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--frozen-at', required=True)
    args = ap.parse_args()
    target = HERE / 'FROZEN.json'
    if target.exists(): raise SystemExit('FROZEN.json exists: not overwritten')
    files = {str(p.relative_to(HERE)): digest(p) for p in frozen_files()}
    target.write_text(json.dumps({'frozen_at': args.frozen_at, 'files': files}, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    print(len(files), 'files')


if __name__ == '__main__':
    main()
