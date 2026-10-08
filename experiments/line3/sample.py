"""T0: deterministic nested sampling of jawiki lead FIRST sentences (one per article).

Same rule as the A report's sample.py/sample2.py (docs/LINE3_DESIGN.md 6.1):
lead sentence opens with its title, topic marker 'ha' within 12 chars after the
title, 12..160 chars, sorted by sha ascending.  Reads the source read-only,
never copies it.  Usage: python sample.py [--out-dir DIR]  -> writes the files
and data_manifest.json (sha256 of every file).
"""
import hashlib, json, os, sys

SRC = '/Users/motonisihikoudai/vera-wiring/data/jawiki_leads.full.jsonl'
HERE = os.path.dirname(os.path.abspath(__file__))
SCRATCH = ('/private/tmp/claude-501/-Users-motonisihikoudai-Projects-Verantyx-Vera-alpha/'
           'd52dc51d-8cb5-4487-931c-cc143bce928f/scratchpad/line3/data')
SMALL = 1_000_000  # bytes: files below this live in the repo (experiments/line3/data)
SIZES = (300, 3000, 30000, 100000)  # plus 'all eligible' (= S269710)


def eligible():
    rows, n = [], 0
    for line in open(SRC, encoding='utf-8'):
        n += 1
        r = json.loads(line)
        t = r.get('title') or ''
        x = (r.get('text') or '').strip()
        if not t or not x or '(' in t or '（' in t or '一覧' in t:
            continue
        s = x.split('。')[0]
        if not s.startswith(t):
            continue
        if not (12 <= len(s) <= 160):
            continue
        if 'は' not in s[len(t):len(t) + 12]:
            continue
        rows.append((r['sha'], t, s + '。', r.get('source')))
    rows.sort()
    return n, rows


def sha_file(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''):
            h.update(b)
    return h.hexdigest()


def place(name, content_lines):
    """Write to the scratchpad first; small files are moved to the repo dir."""
    os.makedirs(SCRATCH, exist_ok=True)
    tmp = os.path.join(SCRATCH, name)
    with open(tmp, 'w', encoding='utf-8') as f:
        for l in content_lines:
            f.write(l)
    size = os.path.getsize(tmp)
    if size < SMALL:
        dst = os.path.join(HERE, 'data', name)
        with open(tmp, 'rb') as a, open(dst, 'wb') as b:
            b.write(a.read())
        return dst, size
    return tmp, size


def main():
    n, rows = eligible()
    out = {'source': SRC, 'source_records': n, 'eligible': len(rows), 'files': {}}
    sizes = list(SIZES) + [len(rows)]
    for k in sizes:
        name = f'S{k}.jsonl'
        lines = (json.dumps({'sha': s, 'title': t, 'sent': x, 'source': src}, ensure_ascii=False) + '\n'
                 for s, t, x, src in rows[:k])
        path, size = place(name, lines)
        out['files'][f'S{k}'] = {'path': path, 'bytes': size, 'sha256': sha_file(path), 'articles': k}
    # S300full: full lead paragraphs of the same 300 articles
    want = {r[0] for r in rows[:300]}
    full = []
    for line in open(SRC, encoding='utf-8'):
        r = json.loads(line)
        if r.get('sha') in want:
            full.append(json.dumps({'sha': r['sha'], 'title': r['title'], 'text': r['text']}, ensure_ascii=False) + '\n')
    path, size = place('S300_fulllead.jsonl', full)
    out['files']['S300full'] = {'path': path, 'bytes': size, 'sha256': sha_file(path), 'articles': len(full)}
    out['files']['S0'] = {'path': None, 'bytes': 0, 'sha256': hashlib.sha256(b'').hexdigest(), 'articles': 0}
    with open(os.path.join(HERE, 'data_manifest.json'), 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=1, sort_keys=True)
    print(json.dumps({k: v['sha256'][:12] for k, v in out['files'].items()}), 'eligible', len(rows))


if __name__ == '__main__':
    main()
