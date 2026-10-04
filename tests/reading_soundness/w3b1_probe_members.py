#!/usr/bin/env python3
"""W3-b1 (probe, not a test): put every member of the two predicate types the table reads (artifacts/w3-b1/type_members.json) into four frames
(<animal>が<place>へ<verb>。, <person>が<place>から<place>へ<verb>。, <person>が<person>に<verb>。, <person>が<person>に<noun>を<verb>。) and list what the entry newly reads
with the placement. Shows which members the table lets through in a frame where the verb is odd (a reading of a nonsense sentence says nothing, but the list is the evidence for a review
of the members). Also counts the English predicates and the people-name-like TIME words of the placement.
Usage: cd <tree> && PYTHONPATH=<tree> python tests/reading_soundness/w3b1_probe_members.py --placement DIR --members FILE --out FILE
"""
import argparse, json, os, random, re, sqlite3, sys
from pathlib import Path


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--placement', required=True); ap.add_argument('--members', required=True); ap.add_argument('--out', required=True)
    a = ap.parse_args()
    from verantyx import semantic_read as SR, semantic_reader as R
    root = os.path.realpath(os.environ.get('PYTHONPATH', '.').split(os.pathsep)[0])
    foreign = [m.__file__ for k, m in list(sys.modules.items()) if (k == 'verantyx' or k.startswith('verantyx.')) and getattr(m, '__file__', None)
               and not os.path.realpath(m.__file__).startswith(root + os.sep)]
    if foreign: print('ISOLATION FAILED', foreign); sys.exit(2)
    members = json.loads(Path(a.members).read_text(encoding='utf-8'))
    q = R.CoarseQuery(a.placement)
    lines, n, total = [], 0, 0
    for typ, tmpl in (('P_MOVE', '猫が庭へ%s。'), ('P_MOVE', '兄が駅から公園へ%s。'), ('P_COMMUNICATE', '兄が弟に%s。'), ('P_COMMUNICATE', '母が先生に結果を%s。')):
        for v in members[typ]:
            total += 1
            t = tmpl % v
            base, out = SR.read(t, placement=None), SR.read(t, placement=q)
            if out['readable'] and not base['readable']:
                n += 1; c = out['clauses'][0]
                lines.append('%s\t%s\t%s\t%s' % (typ, t, c['predicate'], json.dumps(c['roles'], ensure_ascii=False)))
    db = sqlite3.connect('file:%s/placement.sqlite?mode=ro' % os.path.abspath(a.placement), uri=True)
    ascii_pred = db.execute("select count(*) from headwords where ns='P' and word not glob '*[^ -~]*'").fetchone()[0]
    all_pred = db.execute("select count(*) from headwords where ns='P'").fetchone()[0]
    lines.insert(0, 'frames_tried=%d newly_readable=%d members_of_the_two_types=%d' % (total, n, sum(len(members[t]) for t in ('P_MOVE', 'P_COMMUNICATE'))))
    lines.insert(1, 'placement predicates (ns=P headwords): %d, of them written with ASCII only: %d' % (all_pred, ascii_pred))
    rows = db.execute("select word, top, by from headwords where ns='N' and state='DECIDED' and origin='direct'").fetchall()
    random.seed(5)
    for typ in ('TIME',):
        ws = [r for r in rows if r[1] == typ and re.fullmatch(r'[぀-ヿ一-鿿]{1,6}', r[0]) and 'gen_definition' not in r[2]]
        lines.insert(2, 'sample (seed 5) of %d direct TIME nouns written in 1-6 Japanese characters: %s' % (len(ws), ' '.join(w[0] for w in random.sample(ws, min(70, len(ws))))))
    Path(a.out).write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print(lines[0]); print(lines[1])


if __name__ == '__main__':
    main()
