#!/usr/bin/env python3
"""W3-b1: write w3b1_expect_exceptions.json = every row of the new data whose registered `entry_expect` / `expect_reason_prefix` the entry (with the fixture
placement) does not meet, with the exact output it gives and the evidence for why (the reader's own view of the sentence). The data is not changed.
Run after the implementation: cd <tree> && PYTHONPATH=<tree> python tests/reading_soundness/w3b1_mk_exceptions.py [--out FILE]
"""
import argparse, json, os, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))


# The K62 row that was returned to "not read" (docs/READING_SOUNDNESS.md, K62 table change record 1, 2026-10-03 15:28:43 +0900). A type id, a role name and a particle only.
RETURNED_ROW = ('recipient', ('に',), ('PERSON', 'GROUP_ORG'), 'arg')
# The date of table change record 3 (the gate on a head that may be a derived verb), docs/READING_SOUNDNESS.md K63; the same as `registered` in artifacts/w3-b1/r4_gate_prereg_time.txt.
CHANGE3_TIME = '2026-10-03 17:09:34 +0900'


# W3-b1-5 (integration of W3-b1 with W5-a): the commits, and the closed table of the reasons W5-a registered in docs/READING_SOUNDNESS.md section 10A
# (NOT the K62-K66 of section 10, which are W3-b1's). Reason type names only, no words. A reason that is not in this table makes the question below stop with an assert.
W3B1_COMMIT, PRE_W5A_COMMIT, BASE_COMMIT = 'f410469', '0ff3f35', '2732274'
W5A_RULES = (('UNDETERMINED_VOICE:passive or spontaneous', 'docs/READING_SOUNDNESS.md section 10A K62 (W5-a H1: rule 2c withdrawn; a passive is not decided on a non-person subject alone)'),
             ('UNSUPPORTED_CLAUSE', 'docs/READING_SOUNDNESS.md section 10A K63 (W5-a H2: an unsupported clause makes readable false; round 2, auditor decision B2: only the comparison/copula alternative is set aside)'),
             ('AGENT_EVIDENCE_MISSING:', 'docs/READING_SOUNDNESS.md section 10A K64 (W5-a H3: an active clause with an o-phrase and no person evidence for the subject abstains)'))


def module_at(commit):
    """verantyx/semantic_read.py as it is at `commit` (git show of the tree under PYTHONPATH), run as a module of its own."""
    import importlib.util, subprocess
    tree = os.path.realpath(os.environ.get('PYTHONPATH', '.').split(os.pathsep)[0])
    src = subprocess.run(['git', '-C', tree, 'show', '%s:verantyx/semantic_read.py' % commit], capture_output=True, check=True).stdout
    spec = importlib.util.spec_from_loader('verantyx._semantic_read_at_%s_mkx' % commit, loader=None)
    mod = importlib.util.module_from_spec(spec); mod.__package__ = 'verantyx'; sys.modules[spec.name] = mod
    exec(compile(src.decode('utf-8'), 'verantyx/semantic_read.py@%s' % commit, 'exec'), mod.__dict__)
    return mod


def meets(row, out, b1):
    """Whether `out` meets the registered expectation of the row (entry_expect, expect_reason_prefix, never a wrong or half reading)."""
    verdict = b1.judge(row['expect'], row['lang'], out)['verdict']
    reasons = out['abstain']['reasons'] if not out['readable'] else None
    if out['readable']: return row['entry_expect'] == 'read' and verdict == 'correct'
    if row['entry_expect'] == 'read': return False
    return verdict in ('correct', 'abstain') and (not row['expect_reason_prefix'] or (len(reasons) >= 2 and reasons[1].startswith(row['expect_reason_prefix'])))


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--out', default=str(HERE / 'w3b1_expect_exceptions.json'))
    a = ap.parse_args()
    import w3b1_fakes as F
    from verantyx import semantic_read as SR, semantic_reader as R, constructions
    from tools.bank_score.v2 import b1
    constructions.discover()
    root = os.path.realpath(os.environ.get('PYTHONPATH', '.').split(os.pathsep)[0])
    foreign = [m.__file__ for k, m in list(sys.modules.items()) if (k == 'verantyx' or k.startswith('verantyx.'))
               and getattr(m, '__file__', None) and not os.path.realpath(m.__file__).startswith(root + os.sep)]
    if foreign: print('ISOLATION FAILED', foreign); sys.exit(2)
    exceptions = []
    W3B1, PRE, B27 = module_at(W3B1_COMMIT), module_at(PRE_W5A_COMMIT), module_at(BASE_COMMIT)
    for name in ('ja_r8.jsonl', 'en_r4.jsonl'):
        for line in (HERE / name).read_text(encoding='utf-8').splitlines():
            row = json.loads(line)
            out = SR.read(row['input'], row['lang'], placement=F.FixtureQuery())
            base = SR.read(row['input'], row['lang'], placement=None)
            verdict = b1.judge(row['expect'], row['lang'], out)['verdict']
            reasons = out['abstain']['reasons'] if not out['readable'] else None
            if meets(row, out, b1): continue
            # W3-b1-5: asked before every question below. Does the merged entry differ from the W3-b1 tree alone (f410469, the same fixed placement)? then W5-a is the cause:
            # the merged entry gives the base commit's own output (the typed path is not reached) and the W3-b1 tree alone gave the output of the commit before W5-a.
            w3b1_alone = W3B1.read(row['input'], row['lang'], placement=F.FixtureQuery())
            if out != w3b1_alone:
                pre, b27 = PRE.read(row['input'], row['lang']), B27.read(row['input'], row['lang'])
                assert out == base == b27 and not out['readable'] and len(out['abstain']['reasons']) == 1, row['id']
                assert w3b1_alone == pre, row['id']
                first = out['abstain']['reasons'][0]
                rule = [t for k, t in W5A_RULES if first == k or (k.endswith(':') and first.startswith(k))]
                assert len(rule) == 1, (row['id'], out['abstain']['reasons'])
                kind = 'row_returned_to_abstain' if row['entry_expect'] == 'read' else 'reason_differs'
                was = ('read: %s' % json.dumps([c['roles'] for c in w3b1_alone['clauses']], ensure_ascii=False)) if w3b1_alone['readable'] else ('reasons %s' % w3b1_alone['abstain']['reasons'])
                why = ('caused by W5-a (merged into the base commit %s), not by the W3-b1 change: with the merge the entry gives the base commit\'s own output, the same as with no placement '
                       '(reasons %s; the typed path is not reached), while the W3-b1 tree before the merge (%s) gave %s, the same as the commit before W5-a (%s) gave with no placement. '
                       'The cause is %s. Registered: %s%s. The entry abstains (the safe direction); the data is not changed.'
                       % (BASE_COMMIT, out['abstain']['reasons'], W3B1_COMMIT, was, PRE_W5A_COMMIT, rule[0], row['entry_expect'],
                          (' with the second reason %s' % row['expect_reason_prefix']) if row['expect_reason_prefix'] else ''))
                exceptions.append({'id': row['id'], 'input': row['input'], 'kind': kind, 'registered': {'entry_expect': row['entry_expect'], 'expect_reason_prefix': row['expect_reason_prefix']},
                                   'observed': {'readable': False, 'reasons': out['abstain']['reasons']}, 'why': why})
                continue
            # table change record 3 (2026-10-03, review.r3.md M8) is asked FIRST (review.r1 of round 4, M1): would the row have met its expectation with the table as it is now
            # and only the gate on a head that may be a derived verb taken off? then the gate is the cause, whatever record 1 says (a row can meet it both ways)
            by_derived = False
            if not out['readable'] and row['lang'] == 'ja':
                saved_gate = R.typed_head_derived_ja
                R.typed_head_derived_ja = lambda toks, clause: None
                try: out_no_gate = SR.read(row['input'], row['lang'], placement=F.FixtureQuery())
                finally: R.typed_head_derived_ja = saved_gate
                by_derived = meets(row, out_no_gate, b1)
            # would the row have met its expectation with the table as registered (the returned row put back)? then the change record is the cause
            registered = dict(R.TYPED_FRAMES); registered['P_COMMUNICATE'] = (R.TYPED_FRAMES['P_COMMUNICATE'][0], RETURNED_ROW) + tuple(R.TYPED_FRAMES['P_COMMUNICATE'][1:])
            saved = R.TYPED_FRAMES
            R.TYPED_FRAMES = registered
            # (as in round 3: the gate of record 3 did not exist when record 1 was decided, so it is off in this question; record 3 is asked below)
            saved_gate = R.typed_head_derived_ja
            R.typed_head_derived_ja = lambda toks, clause: None
            try: out_registered = SR.read(row['input'], row['lang'], placement=F.FixtureQuery())
            finally: R.TYPED_FRAMES = saved; R.typed_head_derived_ja = saved_gate
            by_table_change = meets(row, out_registered, b1) and not by_derived
            evidence = ''
            if row['lang'] == 'ja':
                view = R.document_view({'d': row['input']})
                evidence = 'the reader (document_view) returns clauses %s' % json.dumps([[c.rule, list(c.unsupported)] for c in view.clauses], ensure_ascii=False)
                if view.unread: evidence += ' and unread %s' % json.dumps([u.reason for u in view.unread], ensure_ascii=False)
            if by_table_change:
                assert not out['readable'], row['id']
                kind = 'row_returned_to_abstain' if row['entry_expect'] == 'read' else 'reason_differs'
                why = ('met its registered expectation with the table as registered (the K62 row recipient/に/PERSON GROUP_ORG put back: %s) and no longer does, because that row '
                       'was returned to "not read" (docs K62, table change record 1, 2026-10-03 15:28:43 +0900; review.r1.md M1). The entry now abstains (the safe direction); '
                       'the data is not changed. %s' % ('read: %s' % json.dumps([c['roles'] for c in out_registered['clauses']], ensure_ascii=False) if out_registered['readable'] else 'reasons %s' % out_registered['abstain']['reasons'], evidence)).strip()
                observed = {'readable': False, 'reasons': reasons}
            elif by_derived:
                assert not out['readable'] and row['entry_expect'] == 'read', row['id']
                kind = 'row_returned_to_abstain'
                why = ('met its registered expectation without the gate on a head that may be a derived verb (read: %s) and no longer does, because that gate was added '
                       '(docs K63, table change record 3, %s; review.r3.md M8): the head is a shimo-ichidan verb, which may be a potential or a spontaneous verb. The entry now '
                       'abstains (the safe direction); the data is not changed. %s' % (json.dumps([c['roles'] for c in out_no_gate['clauses']], ensure_ascii=False), CHANGE3_TIME, evidence)).strip()
                observed = {'readable': False, 'reasons': reasons}
            elif out['readable']:
                kind = 'baseline_reads'
                why = ('the base commit already reads this sentence the same way (the output with no placement is identical), so no typed path was reached; the reading is wrong '
                       '(judge: %s), which is an existing hole of the reader / the English frame, not of this change. %s' % (verdict, evidence)).strip()
                observed = {'readable': True, 'roles': [c['roles'] for c in out['clauses']], 'verdict': verdict}
                assert out == base, row['id']
            elif row['entry_expect'] == 'read':
                kind = 'trigger_not_reached'
                why = ('registered as read, the entry abstains (the safe direction): the typed path was not reached or did not read it, see the reasons. %s' % evidence).strip()
                observed = {'readable': False, 'reasons': reasons}
            else:
                kind = 'reason_differs'
                why = ('abstains as registered, but the second reason is not the registered prefix %s: the typed path that was expected to answer was not reached. %s'
                       % (row['expect_reason_prefix'], evidence)).strip()
                observed = {'readable': False, 'reasons': reasons}
            exceptions.append({'id': row['id'], 'input': row['input'], 'kind': kind, 'registered': {'entry_expect': row['entry_expect'], 'expect_reason_prefix': row['expect_reason_prefix']},
                               'observed': observed, 'why': why})
    Path(a.out).write_text(json.dumps({'exceptions': exceptions}, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    kinds = {}
    for e in exceptions: kinds[e['kind']] = kinds.get(e['kind'], 0) + 1
    print('exceptions=%d %s out=%s' % (len(exceptions), json.dumps(kinds), a.out))


if __name__ == '__main__':
    main()
