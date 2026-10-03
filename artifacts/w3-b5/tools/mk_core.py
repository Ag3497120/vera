#!/usr/bin/env python3
"""W3-b5 step 5 (core of the data generator): what the rows of tests/reading_soundness/ja_r11.jsonl are made of.

Nothing here reads the plan or the entry with a placement. It reads
  * the placement r8 (sqlite, read-only; `coarse_place.query`) for the REAL answer of every noun and for the REAL row of `generated_frames` of every predicate;
  * the reader alone (`reader_facts.facts_of`, no placement) for the trigger path of a sentence and the gates on the ending and on a derived head.
The expectations (`expect`, `entry_expect`, `w3b5_expect`) are written by the caller from the design of each row (the role the sentence has), before any run with a placement.
"""
import json
import os
import sqlite3
import sys

TREE = os.path.realpath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
R8 = '/Users/motonisihikoudai/Projects/vera-impl/build/coarse-W3a/full/r8/run2'
sys.path.insert(0, os.path.join(TREE, 'artifacts', 'w3-b5', 'tools'))
from verantyx import coarse_place as CP          # noqa: E402
from verantyx import semantic_reader as R        # noqa: E402
import reader_facts as RF                        # noqa: E402

_con = sqlite3.connect('file:%s?mode=ro' % os.path.join(R8, 'placement.sqlite'), uri=True)
_noun_cache = {}


def r8_frame_row(word):
    """The row of `generated_frames` of the word, as the entry would see it in `frame_generated`: None when the word has no row."""
    r = _con.execute('SELECT model, effort, batch_id, attempt, ptype, frame FROM generated_frames WHERE word=?', (word,)).fetchone()
    if r is None: return None
    return {'origin': 'generated', 'constructed': True, 'ptype': r[4], 'frame': json.loads(r[5]),
            'provenance': {'model': r[0], 'effort': r[1], 'batch_id': r[2], 'attempt': r[3]}}


def r8_answer(word):
    if word not in _noun_cache: _noun_cache[word] = CP.query(word, placement=R8)
    return _noun_cache[word]


def noun_spec(word, mode='r8'):
    """The fake answer of a noun, from the real answer of r8 (`mode` 'r8'), or a stated one:
      'r8'            DECIDED/MULTIPLE direct -> {top, decided_by}; UNPLACED/UNKNOWN -> {state}; estimated -> {top, origin, basis}
      'seed:TYPE'     an optimistic fake: DECIDED direct TYPE with evidence `seed` (r8 itself has only role@ evidence or another type; written in `note`)
    """
    if mode.startswith('seed:'): return {'top': [mode.split(':', 1)[1]], 'decided_by': ['seed']}
    a = r8_answer(word)
    if a['state'] in ('UNPLACED', 'UNKNOWN'): return {'state': a['state']}
    if a['state'] in ('DECIDED', 'MULTIPLE') and a.get('origin') == 'direct': return {'top': list(a['top']), 'decided_by': list(a['decided_by'])}
    if a['state'] in ('DECIDED', 'MULTIPLE') and a.get('origin') == 'estimated': return {'top': list(a['top']), 'origin': 'estimated', 'basis': a['estimate_basis']}
    raise ValueError((word, a['state']))


def noun_check(word, types, *, adjunct=False):
    """The real r8 answer must be DECIDED direct, in `types`, not decided by a generated definition; for an adjunct also not only by role distributions (the gates of the entry)."""
    a = r8_answer(word)
    ok = a['state'] == 'DECIDED' and a.get('origin') == 'direct' and a['top'][0] in types and 'gen_definition' not in (a.get('decided_by') or [])
    if ok and adjunct: ok = not all(x.startswith('role@') for x in a['decided_by'])
    return ok


def pred_spec(word, frame_source='r8', *, ptype=None, status='NOT_CONFIRMED', frame=None, frame_generated='row'):
    """The fake answer of a predicate.
      frame_source 'r8'        the `frame_generated` is the row of r8 for the word (not changed); the type is the ptype of that row
      frame_source 'absent'    `frame_generated: null` (a word with no row in r8: a seed verb); `ptype` is given
      frame_source 'synthetic' the `frame_generated` is given (`frame_generated`), the type is `ptype` (only the rows of the group `mechanism`)
    `status` NOT_CONFIRMED (the common case: a DECIDED direct predicate with an unconfirmed frame) or CONFIRMED (with `frame`: the particle -> types)."""
    if frame_source == 'r8':
        row = r8_frame_row(word); assert row is not None, word
        ptype = row['ptype']
        gf = row
    elif frame_source == 'absent':
        assert r8_frame_row(word) is None, 'the word has a row in r8: %s' % word
        gf = None
    else:
        gf = frame_generated
    spec = {'top': [ptype], 'namespace': 'P', 'decided_by': ['gen_frame', 'role_distribution@jawiki'] if frame_source != 'absent' else ['seed'],
            'frame_status': status, 'frame_generated': gf}
    if status == 'CONFIRMED': spec['frame'] = frame
    return spec


# ---- conjugation by the reader's own tokenizer (the type of conjugation of the last token) ----
def _ctype(word):
    toks = R._tokens(word)
    f = toks[-1][0].feature
    f.pos1, f.cType, f.cForm, f.lemma
    return f.cType


PAST_FIXED = {'引く': '引いた', '行く': '行った'}


def past(word):
    if word in PAST_FIXED: return PAST_FIXED[word]
    ct = _ctype(word)
    if ct is None: return None
    if word.endswith('する') and 'サ行変格' in ct: return word[:-2] + 'した'
    if '五段' in ct:
        stem, last = word[:-1], word[-1]
        m = {'う': 'った', 'つ': 'った', 'る': 'った', 'く': 'いた', 'ぐ': 'いだ', 'す': 'した', 'ぬ': 'んだ', 'ぶ': 'んだ', 'む': 'んだ'}
        return stem + m[last] if last in m else None
    if '一段' in ct and word.endswith('る'): return word[:-1] + 'た'
    return None


def neg_past(word):
    ct = _ctype(word)
    if word.endswith('する') and 'サ行変格' in ct: return word[:-2] + 'しなかった'
    if '五段' in ct:
        stem, last = word[:-1], word[-1]
        m = {'う': 'わ', 'つ': 'た', 'る': 'ら', 'く': 'か', 'ぐ': 'が', 'す': 'さ', 'ぬ': 'な', 'ぶ': 'ば', 'む': 'ま'}
        return stem + m[last] + 'なかった'
    if '一段' in ct and word.endswith('る'): return word[:-1] + 'なかった'
    return None


def path_of(text):
    """The trigger the reader alone gives to the sentence: U, U3 or none (S4 is not used in this data), plus the gates on the ending and on a derived head."""
    f = RF.facts_of(text)
    path = f['trigger_w3b1'] if f['trigger_w3b1'] != '-' else (f['trigger_w3b2'] if f['trigger_w3b2'] != '-' else 'none')
    return path, f


def expect_read(pred, roles, must_not, *, modality=None, polarity='+', tense='past'):
    return {'readable': True, 'clauses': [{'predicate': pred, 'roles': roles, 'polarity': polarity, 'tense': tense, 'modality': modality, 'voice': 'active'}],
            'relations': [], 'must_not': must_not}


EXPECT_ABSTAIN = {'readable': False, 'clauses': [], 'relations': [], 'must_not': []}
KEYS = ['id', 'lang', 'input', 'text', 'behavior', 'expect', 'pred_type', 'path', 'particle', 'role_group', 'construction', 'placement', 'frame_source', 'entry_expect',
        'w3b5_expect', 'note']
