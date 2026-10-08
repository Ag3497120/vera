"""W3-b4: the machinery of the generator of tests/reading_soundness/ja_r10_w3b4.jsonl (the sentences are in mk_data_sentences.py).
Nothing here reads a sentence with a placement. For each sentence it uses (1) facts of the READER ALONE (trigger, tail gate, derived gate, what the entry does with no placement:
reader_facts.facts_of) to fill `path` and to refuse a row whose trigger is not the one intended, (2) the answers of the placement r7 (read only) for every word that a plan would
ask, written into `placement` as the fake placement of the row (a contract-conforming answer built from the real one: state, origin, top, decided_by, estimate_basis).
The expectation of a row (`behavior`, `expect`, `entry_expect`, `w3b4_expect`) comes from the intent written in the sentence file, not from any run through the new table.
"""
import json
import os
import sys

R7 = '/Users/motonisihikoudai/Projects/vera-impl/build/coarse-W3a/full/r7/run1'
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

_CACHE = {}
ROWS = []
COUNT = {}
ERRORS = []


def bad(msg):
    ERRORS.append(msg)


def r7_spec(word):
    """The fake-placement spec of a word, from the real answer of r7."""
    if word in _CACHE: return _CACHE[word]
    from verantyx import coarse_place
    q = coarse_place.query(word, placement=R7)
    st = q['state']
    if st in ('UNPLACED', 'UNKNOWN', 'NO_PLACEMENT'): spec = {'state': st}
    elif q['origin'] == 'estimated': spec = {'top': list(q['top']), 'origin': 'estimated', 'basis': q['estimate_basis']}
    else: spec = {'top': list(q['top']), 'decided_by': list(q.get('decided_by') or [])}
    _CACHE[word] = spec
    return spec


def _tail(text):
    t = text.rstrip('。')
    if t.endswith('なかった'): return '-', 'past'
    if t.endswith('ない'): return '-', 'nonpast'
    if t.endswith(('た', 'だ')): return '+', 'past'     # 遊んだ・飲んだ (the voiced form of た)
    return '+', 'nonpast'


MUST_NOT = {'agent': lambda v: [{'clause': 0, 'role': 'patient', 'value': v}],
            'goal': lambda v: [{'clause': 0, 'role': 'recipient', 'value': v}, {'clause': 0, 'role': 'place', 'value': v}],
            'place': lambda v: [{'clause': 0, 'role': 'instrument', 'value': v}]}


def add(typ, kind, text, pred, roles, fill, reason, cons, note, pred_type, readable=True):
    """kind: R (read), A (abstain), X (a type that is not read). reason: for A/X the registered prefix of the reason (what typed_explain_ja(...)['w3b2'] starts with):
    'NT' = the trigger does not fire (the reader's own refusal stands)."""
    from reader_facts import facts_of
    COUNT[(typ, kind)] = COUNT.get((typ, kind), 0) + 1
    rid = 'W3B4-%s-%s-%03d' % (typ, kind, COUNT[(typ, kind)])
    f = facts_of(text)
    path = 'U' if f['trigger_w3b1'] != '-' else ('U3' if f['trigger_w3b2'] != '-' else 'none')
    if f['trigger_w3b1'] == 'S4': path = 'S4'
    if f['base_entry'] != 'abstain': bad('%s %s: the reader reads it alone (%s)' % (rid, text, f['base_entry']))
    if kind == 'R':
        if path not in ('U', 'U3') or f['tail_gate'] != 'ok' or f['derived_gate'] != 'ok': bad('%s %s: not reachable: %s' % (rid, text, f))
        w3b4 = 'READ'
    else:
        if reason == 'NT':
            if path != 'none': bad('%s %s: expected not triggered but path=%s' % (rid, text, path))
            w3b4 = 'PLACEMENT_W3B2_NOT_TRIGGERED'
        else:
            if path not in ('U', 'U3'): bad('%s %s: expected a trigger (%s) but path=%s %s' % (rid, text, reason, path, f))
            w3b4 = reason
            if reason.startswith('PLACEMENT_PREDICATE_TAIL_UNINTERPRETED') and f['tail_gate'] == 'ok': bad('%s tail gate is ok' % rid)
            if reason.startswith('PLACEMENT_PREDICATE_POSSIBLY_DERIVED') and (f['derived_gate'] == 'ok' or f['tail_gate'] != 'ok'): bad('%s derived gate: %s' % (rid, f))
    pol, tense = _tail(text)
    if readable and roles is not None:
        expect = {'readable': True, 'clauses': [{'predicate': pred, 'roles': dict(roles), 'polarity': pol, 'tense': tense, 'modality': None, 'voice': 'active'}], 'relations': [],
                  'must_not': [m for role, v in roles.items() if role in MUST_NOT for m in MUST_NOT[role](v)]}
    else:
        expect = {'readable': False, 'clauses': [], 'relations': [], 'must_not': []}
    placement = {w: r7_spec(w) for w in list(fill) + [pred]}
    ROWS.append({'id': rid, 'lang': 'ja', 'input': text, 'text': text, 'behavior': 'read' if expect['readable'] else 'abstain', 'expect': expect, 'pred_type': pred_type, 'path': path,
                 'construction': cons, 'placement': placement, 'entry_expect': 'read' if kind == 'R' else 'abstain', 'w3b4_expect': w3b4, 'note': note})


def write(path):
    seen = set()
    for r in ROWS:
        if r['input'] in seen: bad('duplicate sentence: ' + r['input'])
        seen.add(r['input'])
    if ERRORS:
        for e in ERRORS: print('ERROR', e[:300])
        raise SystemExit('%d errors; nothing written' % len(ERRORS))
    with open(path, 'w', encoding='utf-8') as fh:
        for r in ROWS: fh.write(json.dumps(r, ensure_ascii=False) + '\n')
    return len(ROWS)
