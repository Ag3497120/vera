"""Run the frozen test sentences through the reading entry (with --events, through `read_events`) and sort every sentence into
(a) the reader abstains, (b) the reader reads and agrees with the hand-written expectation, (c) the reader reads and disagrees.

Writes:  --obs   the machine's observation per sentence (id, readable, abstain, clauses, relations): never written back to the expectations
         --out   the classes (e2_classes.json)
         --disagreements-md / --disagreements-json   the (c) list (the json list is what tests/test_event_cross_data.py reads)
The expectation files are read only. Run: python tests/event_cross/classify.py --obs ... --out ...
"""
import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
TREE = HERE.parent.parent
sys.path.insert(0, str(TREE))

from verantyx import event_cross as E    # noqa: E402

DATA = HERE / 'data'
LANGS = ('ja', 'en')


def load(name):
    return [json.loads(l) for l in (DATA / name).read_text(encoding='utf-8').splitlines() if l.strip()]


def files(kind, lang):
    """The frozen files of a language in a fixed order: the first set, then the additions (sentences_ja_add1.jsonl, ...)."""
    return sorted(p.name for p in DATA.glob('%s_%s*.jsonl' % (kind, lang)))


def load_all(kind, lang):
    return [row for name in files(kind, lang) for row in load(name)]


def sentences():
    out = []
    for lang in LANGS:
        sents = load_all('sentences', lang)
        exps = {e['id']: e for e in load_all('expected', lang)}
        for s in sents:
            out.append((lang, s, exps[s['id']]))
    return out


def center_matches(expected_center, clause):
    """The keys the expectation writes must equal the clause's; the optional keys must be present in both or in neither."""
    for k, v in expected_center.items():
        if clause.get(k) != v: return False
    for k in E.CLAUSE_OPTIONAL_KEYS:
        if (k in clause and clause[k] is not None) != (k in expected_center and expected_center[k] is not None): return False
    return True


def agrees(exp, obs):
    """(True, '') when the observed clauses / relations equal the expected ones; else (False, why)."""
    ecs, ocs = exp['crosses'], obs['clauses']
    if len(ecs) != len(ocs): return False, 'clauses %d expected, %d read' % (len(ecs), len(ocs))
    for i, (ec, oc) in enumerate(zip(ecs, ocs)):
        if not center_matches(ec['center'], oc): return False, 'clause %d centre differs' % i
        if ec['arms'] != oc['roles']: return False, 'clause %d arms differ' % i
    key = lambda r: (r['type'], r['from'], r['to'])
    if sorted(map(key, exp['relations'])) != sorted(map(key, obs['relations'])): return False, 'relations differ'
    return True, ''


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--obs', required=True); ap.add_argument('--out', required=True)
    ap.add_argument('--disagreements-md'); ap.add_argument('--disagreements-json')
    args = ap.parse_args(argv)
    obs_rows, classes, detail = [], {}, {}
    for lang, s, exp in sentences():
        got = E.read_events(s['text'])
        obs_rows.append({'id': s['id'], 'readable': got['readable'], 'abstain': got['abstain'], 'clauses': got['clauses'],
                         'relations': got['relations'], 'events_status': got['events']['status']})
        if not got['readable']:
            cls = 'a'
            detail[s['id']] = {'sub': 'abstain_expected' if not exp['readable'] else 'over_abstain', 'abstain': got['abstain']}
        elif not exp['readable']:
            cls = 'c'; detail[s['id']] = {'why': 'expected unreadable, the reader read it'}
        else:
            ok, why = agrees(exp, got)
            cls = 'b' if ok else 'c'
            if not ok: detail[s['id']] = {'why': why}
        classes[s['id']] = cls
    Path(args.obs).write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in obs_rows), encoding='utf-8')
    count = {}
    for lang in LANGS:
        ids = [i for i in classes if i.startswith(lang + '-')]
        count[lang] = {k: sum(1 for i in ids if classes[i] == k) for k in 'abc'}
        count[lang]['a_expected_abstain'] = sum(1 for i in ids if detail.get(i, {}).get('sub') == 'abstain_expected')
        count[lang]['a_over_abstain'] = sum(1 for i in ids if detail.get(i, {}).get('sub') == 'over_abstain')
        count[lang]['total'] = len(ids)
        count[lang]['readable_by_reader'] = count[lang]['b'] + count[lang]['c']
    count['all'] = {k: sum(count[l][k] for l in LANGS) for k in count['ja']}
    Path(args.out).write_text(json.dumps({'counts': count, 'classes': classes, 'detail': detail}, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    if args.disagreements_json:
        Path(args.disagreements_json).write_text(json.dumps(sorted(i for i, c in classes.items() if c == 'c'), ensure_ascii=False) + '\n', encoding='utf-8')
    if args.disagreements_md:
        exps = {e['id']: e for lang in LANGS for e in load_all('expected', lang)}
        text = {s['id']: s['text'] for lang in LANGS for s in load_all('sentences', lang)}
        obs = {r['id']: r for r in obs_rows}
        lines = ['# (c) reader disagreements: draft table written by classify.py (the rule column is added by hand below the table)\n']
        for i, c in classes.items():
            if c != 'c': continue
            lines.append('## %s: %s\n- expected: `%s`\n- reader: `%s`\n- why: %s\n' % (
                i, text[i], json.dumps(exps[i].get('crosses', 'unreadable'), ensure_ascii=False),
                json.dumps({'clauses': obs[i]['clauses'], 'relations': obs[i]['relations']}, ensure_ascii=False), detail[i]['why']))
        Path(args.disagreements_md).write_text('\n'.join(lines), encoding='utf-8')
    print(json.dumps(count, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    sys.exit(main())
