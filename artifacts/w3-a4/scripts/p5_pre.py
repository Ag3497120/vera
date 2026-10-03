"""p5_pre.py: P5 pre-evaluation, BEFORE r8/run1 exists.  In memory only.
For each word of the sahen needs list: r8/base's stored evidence + the gen_frame / gen_frame_slot rows the builder's stage 2
would add from the new frames file (same shape, same source string) -> the real ct.decide_word with r8's config.
usage: p5_pre.py <r8 base dir> <needs.jsonl> <new frames.jsonl> <outdir>
writes: pre_decisions.tsv (every word), sample60_raw.tsv (30 top by n_seen incl. ties + 30 random: random.Random(20261004)),
        direct_raw.tsv (every word that is direct; if > 200: random.Random(20261005).sample(sorted, 200))."""
import json, random, sqlite3, sys
import verantyx
from verantyx import coarse_types as ct
from tools import build_coarse_placement as bcp
W = '/Users/motonisihikoudai/Projects/vera-impl/wt/W3-a4-S/'
assert verantyx.__file__.startswith(W) and bcp.__file__.startswith(W)
base, needs, frames, outdir = sys.argv[1:5]
cfg = dict(ct.DEFAULT_CONFIG)
cfg.update(json.load(open(W + 'artifacts/w3-a4/config_w3a4.json', encoding='utf-8')))
con = sqlite3.connect('file:%s/placement.sqlite?mode=ro' % base, uri=True)
meta_cfg = json.loads(con.execute("select v from meta where k='config'").fetchone()[0])
assert meta_cfg == cfg, "config of r8/base differs from DEFAULT_CONFIG + config_w3a4.json"
excl = bcp._load_terms([W + 'tests/coarse_place/data/unknown_words.jsonl', W + 'tests/coarse_place/data/dev_unknown.jsonl',
                        W + 'artifacts/w3-a3/exclude_coined.jsonl'])
excl_terms = sorted({t for ts in excl.values() for t in ts})
rows, drops, nlines = bcp.read_generated_frames(frames, excl_terms)
print("frames: lines %d rows %d drops %s" % (nlines, len(rows), dict(drops)), file=sys.stderr)
order = {p: i for i, p in enumerate(ct.ROLE_PARTICLES)}
words = [json.loads(l) for l in open(needs, encoding='utf-8') if l.strip()]
out = []
for rec in words:
    w = rec['word']
    ev = con.execute("select arm,src,type,n,base from evidence where word=?", (w,)).fetchall()
    hw = con.execute("select ns,state,origin,top,n_seen from headwords where word=?", (w,)).fetchone()
    g = rows.get(w)
    gtype, gframe = None, None
    if g is not None and 'P' in hw[0]:
        ev = ev + [(ct.GEN_FRAME_ARM, g['src'], g['ptype'], 1, None)]
        for part in sorted(g['frame'], key=lambda x: order[x]):
            for typ in sorted(g['frame'][part]):
                ev.append(('gen_frame_slot', g['src'], '%s|%s' % (part, typ), 1, None))
        gtype, gframe = g['ptype'], g['frame']
    d = ct.decide_word(ev, cfg)
    gfa = d['arms'].get(ct.GEN_FRAME_ARM, {})
    out.append({'word': w, 'n_seen': hw[4], 'ns': hw[0], 'state': d['state'], 'origin': d.get('origin'),
                'top': (d['tops'] or [None])[0] if len(d['tops']) < 2 else ','.join(d['tops']),
                'by': ','.join(d['by']), 'why': gfa.get('why'), 'gen_type': gtype,
                'gen_frame': json.dumps(gframe, ensure_ascii=False, sort_keys=True) if gframe else None,
                'rd_sig': json.dumps({k: a['sig'] for k, a in d['arms'].items() if a['arm'] == 'role_distribution' and a['threshold_met']}, ensure_ascii=False, sort_keys=True),
                'sahen_uses_max_src': rec.get('sahen_uses_max_src')})
cols = ['word', 'n_seen', 'ns', 'state', 'origin', 'top', 'by', 'why', 'gen_type', 'gen_frame', 'rd_sig', 'sahen_uses_max_src']
def write(path, rs, extra=()):
    with open(path, 'w', encoding='utf-8') as f:
        f.write('\t'.join(cols + list(extra)) + '\n')
        for r in rs:
            f.write('\t'.join('' if r[c] is None else str(r[c]) for c in cols) + ''.join('\t' for _ in extra) + '\n')
write(outdir + '/pre_decisions.tsv', out)
srt = sorted(out, key=lambda r: (-r['n_seen'], r['word']))
cut = srt[29]['n_seen']
top = [r for r in srt if r['n_seen'] >= cut]
rest = sorted(r['word'] for r in srt if r['n_seen'] < cut)
rnd = random.Random(20261004).sample(rest, 30)
byw = {r['word']: r for r in out}
sample = top + [byw[w] for w in rnd]
write(outdir + '/sample60_raw.tsv', sample, ('judgement', 'reason'))
direct = sorted(r['word'] for r in out if r['origin'] == 'direct')
chosen = direct if len(direct) <= 200 else sorted(random.Random(20261005).sample(direct, 200))
write(outdir + '/direct_raw.tsv', [byw[w] for w in chosen], ('judgement', 'reason'))
import collections
print(json.dumps({'words': len(out), 'with_frame_row': sum(1 for r in out if r['gen_type']),
                  'state': collections.Counter(r['state'] for r in out), 'origin': collections.Counter(r['origin'] for r in out),
                  'why': collections.Counter(r['why'] for r in out), 'sample': len(sample), 'top_cut_n_seen': cut,
                  'top_n': len(top), 'direct_total': len(direct), 'direct_chosen': len(chosen)}, ensure_ascii=False))
