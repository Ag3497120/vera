#!/usr/bin/env python3
"""W3-b5 step 5: write tests/reading_soundness/ja_r11.jsonl (the data of the ticket; the keys are registered in docs/READING_SOUNDNESS.md section 10F K205).

Every row is a SENTENCE and what it means (`expect`), written from the design of the row (the role that the phrase has), never from a run with a placement. What is read from the
world is (1) the real answer of r8 for a noun and the real row of `generated_frames` of r8 for a predicate (`mk_core`), (2) the reader alone: the trigger path of the sentence (U, U3
or none) and the two gates on the ending. A row whose trigger path is not the one the design intends is REPORTED (not silently fixed): the design has to change, never the data to fit the plan.
`w3b5_expect` is the registered diagnosis (`typed_explain_ja(...)['w3b2']`, a prefix) or READ; it is written here from the design of the row too.
Usage: cd <tree> && PYTHONPATH=<tree> python artifacts/w3-b5/tools/mk_data_w3b5.py --out tests/reading_soundness/ja_r11.jsonl [--check]
"""
import argparse
import collections
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mk_core as C   # noqa: E402

ROWS = []
PROBLEMS = []
COUNTER = collections.Counter()


def agent_ok(w):
    return C.noun_check(w, ('PERSON', 'GROUP_ORG'))


def add(group, kind, text, pred, ptype, frame_source, particle, role_group, construction, nouns, expect, w3b5, note, *, status='NOT_CONFIRMED', frame=None, frame_generated=None,
        want_path=('U', 'U3'), pred_word=None, pred_override=None, entry=None, idnum=None):
    """Add a row. `nouns`: {word: spec or mode string}. `want_path`: the trigger paths the design intends (the reader alone decides the real one; 'none' for a row of the not-triggered group)."""
    if any(r['input'] == text for r in ROWS):
        PROBLEMS.append((text, 'duplicate')); return None
    if 'None' in text:
        PROBLEMS.append((text, 'None in text')); return None
    path, f = C.path_of(text)
    problem = None
    if path not in want_path: problem = 'path %s not in %s' % (path, want_path)
    if want_path != ('none',) and (f['tail_gate'] != 'ok' or f['derived_gate'] != 'ok') and not (kind == 'A' and ('gate' in note or 'voice' in note)):
        problem = (problem or '') + ' tail=%s derived=%s' % (f['tail_gate'], f['derived_gate'])
    if f['predicate'] != (pred_word or pred) and path != 'none' and 'gate' not in note and 'voice' not in note:
        problem = (problem or '') + ' predicate=%s' % f['predicate']
    if want_path == ('none',) and not problem:
        # the reader alone decides (no placement): what it does with the sentence must be what the row says (read and correct / abstain)
        from verantyx import semantic_read as SR
        from tools.bank_score.v2 import b1 as _b1
        out = SR.read(text, placement=None)
        if kind == 'R' and (not out['readable'] or _b1.judge(expect, 'ja', out)['verdict'] != 'correct'): problem = 'the reader alone does not read it correctly'
        if kind == 'A' and out['readable']: problem = 'the reader alone reads it'
    if problem:
        PROBLEMS.append((text, problem)); return None
    place = {}
    for w, s in nouns.items(): place[w] = C.noun_spec(w, s) if isinstance(s, str) else s
    if pred_override is not None: place[pred_word or pred] = pred_override
    else: place[pred_word or pred] = C.pred_spec(pred_word or pred, frame_source, ptype=ptype, status=status, frame=frame, frame_generated=frame_generated)
    COUNTER[group, kind] += 1
    rid = 'W3B5-%s-%s-%03d' % (group, kind, idnum if idnum is not None else COUNTER[group, kind])
    row = {'id': rid, 'lang': 'ja', 'input': text, 'text': text, 'behavior': 'read' if kind == 'R' else 'abstain', 'expect': expect, 'pred_type': ptype, 'path': path,
           'particle': particle, 'role_group': role_group, 'construction': construction, 'placement': place, 'frame_source': frame_source,
           'entry_expect': entry or ('read' if kind == 'R' else 'abstain'), 'w3b5_expect': w3b5, 'note': note}
    ROWS.append(row)
    return row


# -------------------------------------------------------------------------------------------------------------------------------------------------
# the lexicon (types are checked against the real r8 answer when a row is added by `place`)
# -------------------------------------------------------------------------------------------------------------------------------------------------
AGENTS = ['兄', '弟', '姉', '妹', '先生', '店員', '係員', '社員', '学生', '職員', '選手', '監督']
for _a in AGENTS: assert agent_ok(_a), _a


def ag(i): return AGENTS[i % len(AGENTS)]


def must_de(agent_, place_):
    return [{'clause': 0, 'role': 'patient', 'value': agent_}, {'clause': 0, 'role': 'instrument', 'value': place_}]


def must_ni(agent_, x, wrong):
    return [{'clause': 0, 'role': r, 'value': x} for r in wrong] + [{'clause': 0, 'role': 'patient', 'value': agent_}]


def build():
    exec(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'mk_groups_w3b5.py'), encoding='utf-8').read(), globals())


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--out', required=True); ap.add_argument('--report', default=None)
    a = ap.parse_args()
    build()
    ids = [r['id'] for r in ROWS]; texts = [r['input'] for r in ROWS]
    assert len(set(ids)) == len(ids), [i for i in ids if ids.count(i) > 1][:5]
    assert len(set(texts)) == len(texts), [t for t in texts if texts.count(t) > 1][:5]
    with open(a.out, 'w', encoding='utf-8') as fh:
        for r in ROWS:
            assert list(r) == C.KEYS, r['id']
            fh.write(json.dumps(r, ensure_ascii=False) + '\n')
    rep = ['rows=%d problems=%d' % (len(ROWS), len(PROBLEMS))] + ['PROBLEM\t%s\t%s' % p for p in PROBLEMS]
    if a.report: open(a.report, 'w', encoding='utf-8').write('\n'.join(rep) + '\n')
    print('\n'.join(rep[:80]))
    c = collections.Counter((r['role_group'], r['behavior']) for r in ROWS)
    for k in sorted(c): print(k, c[k])


if __name__ == '__main__':
    main()
