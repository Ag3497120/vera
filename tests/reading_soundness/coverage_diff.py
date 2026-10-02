#!/usr/bin/env python3
"""作業前後の supported 文を突き合わせる。

使い方: coverage_diff.py before.jsonl after.jsonl --out-dir <dir> [--classified dropped_classified.tsv] [--gained-classified gained.tsv]
  dropped.tsv : before に有り after に無い文(supported でなくなった文)
  gained.tsv  : after に有り before に無い文(新たに supported になった文)
  changed.tsv : 両方 supported だが supported 節の構造が違う文
--classified を渡すと、dropped の全件に分類(WAS_WRONG / DROPPED_CORRECT)と理由が入っているかを検査する。
  DROPPED_CORRECT が 1 件でもあれば終了コード 1。分類が欠けていても 1。判断できないものは DROPPED_CORRECT に数える(保守側)。
"""
import argparse, csv, json, sys
from pathlib import Path


def load(path):
    rows = {}
    for line in Path(path).read_text(encoding='utf-8').splitlines():
        if line.strip():
            r = json.loads(line); rows[tuple(r['key'])] = r
    return rows


def sup(r):
    return sorted(json.dumps([c['rule'], c['predicate'], c['polarity'], c['roles']], ensure_ascii=False)
                  for c in r['clauses'] if not c['unsupported'])


def render(r, only_supported=True):
    parts = []
    for c in r['clauses']:
        if only_supported and c['unsupported']: continue
        parts.append(f"{c['rule']}:{c['predicate']}{'-' if c['polarity']=='-' else ''}(" + ','.join(f'{n}={v}' for n, v in c['roles']) + ')')
    return ' | '.join(parts)


def reasons(r):
    return ' ; '.join(sorted({u for c in r['clauses'] for u in c['unsupported']}))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('before'); ap.add_argument('after'); ap.add_argument('--out-dir', required=True)
    ap.add_argument('--classified'); ap.add_argument('--gained-classified'); ap.add_argument('--after-all', help='coverage_sentences.py --all-clauses output of the after tree (reasons of dropped sentences)')
    a = ap.parse_args()
    b, f = load(a.before), load(a.after)
    fa = load(a.after_all) if a.after_all else f
    out = Path(a.out_dir); out.mkdir(parents=True, exist_ok=True)
    dropped = [k for k in b if k not in f]; gained = [k for k in f if k not in b]
    changed = [k for k in b if k in f and sup(b[k]) != sup(f[k])]
    def write(name, keys, cols):
        with open(out / name, 'w', encoding='utf-8', newline='') as fh:
            w = csv.writer(fh, delimiter='\t'); w.writerow(['source', 'start', 'sentence'] + [c[0] for c in cols])
            for k in sorted(keys):
                w.writerow([k[0], k[1], (b.get(k) or f.get(k))['text'].strip().replace('\t', ' ').replace('\n', ' ')] + [c[1](k) for c in cols])
    write('dropped.tsv', dropped, [('before_supported', lambda k: render(b[k])), ('after_reasons', lambda k: reasons(fa[k]) if k in fa else '(not in after)'), ('after_clauses', lambda k: render(fa[k], False) if k in fa else '')])
    write('gained.tsv', gained, [('after_supported', lambda k: render(f[k]))])
    write('changed.tsv', changed, [('before_supported', lambda k: render(b[k])), ('after_supported', lambda k: render(f[k]))])
    print(f'before={len(b)} after={len(f)} dropped={len(dropped)} gained={len(gained)} changed={len(changed)}')
    print(f'identity: before - dropped + gained = {len(b) - len(dropped) + len(gained)} (after={len(f)})')
    code = 0 if len(b) - len(dropped) + len(gained) == len(f) else 1
    if a.classified:
        rows = list(csv.DictReader(open(a.classified, encoding='utf-8'), delimiter='\t'))
        have = {(r['source'], int(r['start'])): r for r in rows}
        missing = [k for k in dropped if k not in have]
        bad = [r for r in rows if r.get('class') not in ('WAS_WRONG', 'DROPPED_CORRECT') or not r.get('reason', '').strip()]
        counts = {}
        for r in rows: counts[r.get('class')] = counts.get(r.get('class'), 0) + 1
        print(f'classified={len(rows)} missing={len(missing)} malformed={len(bad)} counts={counts}')
        if missing or bad or counts.get('DROPPED_CORRECT', 0): code = 1
    if a.gained_classified:
        rows = list(csv.DictReader(open(a.gained_classified, encoding='utf-8'), delimiter='\t'))
        have = {(r['source'], int(r['start'])): r for r in rows}
        missing = [k for k in gained if k not in have]
        counts = {}
        for r in rows: counts[r.get('class')] = counts.get(r.get('class'), 0) + 1
        print(f'gained classified={len(rows)} missing={len(missing)} counts={counts}')
        if missing or counts.get('MISREAD', 0): code = 1
    sys.exit(code)


if __name__ == '__main__':
    main()
