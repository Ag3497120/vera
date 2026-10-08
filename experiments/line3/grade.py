"""T0 scoring, the A report's rule (docs/LINE3_DESIGN.md 7.2), extracted from probe.py.

answered: ANSWER*, REVERSE_UNIQUE, REVERSE_SPECIFIC, SEEDED (and L3's ANSWER).
abstain : everything else (CHOICE, AMBIGUOUS, UNKNOWN_*, None ...). Not a wrong.
correct : answered AND a gold word is in the answer text AND the core is a
          substring of the subject.
wrong   : answerable question answered but not correct, or an unanswerable
          question (empty gold) answered.
"""
import json


def classify(verdict):
    if verdict is None:
        return 'ABSTAIN'
    if verdict.startswith('ANSWER') or verdict in ('REVERSE_UNIQUE', 'REVERSE_SPECIFIC'):
        return 'ANSWER'
    if verdict == 'SEEDED':
        return 'SEEDED'
    return 'ABSTAIN'


def load_questions(path):
    return [l.rstrip('\n').split('\t') for l in open(path, encoding='utf-8') if not l.startswith('#')]


def grade(cls, core, text, subject, gold):
    """-> (grade, gold_hit, subj_ok)"""
    golds = [g.casefold() for g in gold.split('|') if g]
    cl = str(core or '').casefold()
    tl = (text or '').casefold()
    subj_ok = bool(cl) and (cl in subject.casefold())
    gold_hit = any(g in tl for g in golds)
    if cls == 'ABSTAIN':
        g = 'abstain'
    elif not golds:
        g = 'wrong'
    elif gold_hit and subj_ok:
        g = 'correct'
    else:
        g = 'wrong'
    return g, gold_hit, subj_ok


def extract(r):
    """(verdict, core, text) from an answer dict, as probe.py did."""
    v = r.get('verdict')
    core = r.get('core') or (r.get('seed') if isinstance(r.get('seed'), str) else None) or ''
    text = r.get('text') or r.get('answer') or ''
    if not isinstance(text, str):
        text = json.dumps(text, ensure_ascii=False)
    return v, core, text


def tally(rows):
    """Counts for one (cond, path): answerable = qid starting with 'a' (60), fict/attr = unanswerable (30)."""
    a = [r for r in rows if r['qid'].startswith('a')]
    f = [r for r in rows if r['kind'] == 'fict']
    t = [r for r in rows if r['kind'] == 'attr']
    return dict(
        correct=sum(r['grade'] == 'correct' for r in a),
        wrong=sum(r['grade'] == 'wrong' for r in a),
        abstain=sum(r['grade'] == 'abstain' for r in a),
        loose=sum(bool(r['gold_hit']) and r['cls'] != 'ABSTAIN' for r in a),
        fict_answered=sum(r['cls'] != 'ABSTAIN' for r in f),
        attr_answered=sum(r['cls'] != 'ABSTAIN' for r in t),
        answered_unanswerable=sum(r['cls'] != 'ABSTAIN' for r in f + t),
        gold_held=sum(bool(r.get('gold_held')) for r in a),
        n_answerable=len(a), n_unanswerable=len(f) + len(t))
