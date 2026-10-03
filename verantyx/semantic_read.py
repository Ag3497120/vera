"""The reading entry: `python -m verantyx.semantic_read --text <sentence> [--lang ja|en]`.

One JSON object on standard output, in the shape fixed by docs/READING_CONVENTIONS.md §1:

    {"schema": "verantyx.semantic_read/1", "lang": "ja", "readable": true,
     "clauses": [{"predicate", "roles", "polarity", "tense", "modality", "voice"[, "quantifiers", "scope", "comparison"]}, ...],
     "relations": [{"type", "from", "to"}, ...],
     "abstain": null, "unsupported": [...], "clause_meta": [{"rule", "span": [start, end]}, ...]}

`readable: false` is a TYPED abstention: `clauses: []`, `relations: []`, `abstain: {"kind", "reasons"}`.
  kind "unreadable_input": there is POSITIVE evidence that the input is not a proposition (a greeting / interjection the reader names, a
                           sentence with no token that can be a predicate, a predicate word the dictionary does not know);
  kind "not_supported":    anything else the reader could not return with confidence (a clause it left unsupported, a role or a field it
                           cannot map to the convention, a competing reading ...). It does NOT say the input is unreadable.
`unsupported` lists the clauses the reader found and could not support, with their typed reasons.

Rule of the entry: an output field is written only when its value is decided by evidence in the reader's output or in the surface. When a
field cannot be decided (tense, modality, voice, the type of a subject, a role name, a quantifier, a relation) the WHOLE input is returned
`readable: false` / `not_supported` with the typed reason: a half-filled structure of a sentence whose main predicate is unread, or a guessed
field, is a misreading (the convention counts a structured reading of an unreadable input as one), while an abstention is not.
What the convention has and this entry does not produce is the closed table NOT_PRODUCED (docs/READING_SOUNDNESS.md §9 is built from it).

With `--events` one more key, `events`, is appended LAST (the event cross of verantyx/event_cross.py, built from this output alone); without it
the output is unchanged to the byte, and a refused input answers the same with or without it.

With a coarse placement (`--placement <dir>` or the variable VERA_PLACEMENT; the argument wins) a refused input may be read once more with the DIRECT type of
its words (docs/READING_SOUNDNESS.md section 10): only the two typed paths there, only when the reader itself refused for the one reason the path answers;
the clause then carries `predicate_basis` / `role_basis` (where the role or predicate came from). Without a placement the output is unchanged to the byte
and none of the placement code is loaded.

Exit code: 0 for readable true and false alike; 2 for an input that is refused (a typed `{"error": {"type", "detail"}}` object on standard
output). The entry writes no file, uses no network, prints nothing but the JSON object, and gives the same output to the same input.

質問の十字 (W3-c2): `read_question(text, lang)` takes a QUESTION (an interrogative sentence) as a cross with one typed hole (疑問文を「穴の空いた十字」に写す): the wh word is replaced by
a mark (`Ｘ` / `X`, a symbol and never a word), the declarative form is read by the same reader, and the answer is the shape of `read()` plus the last key `question`
({hole_role, hole_type, wh, kind, restrictor, hole_mark, declarative}). `read()` itself still refuses a question. The registered table of wh words is `WH_TABLE`
(docs/EVENT_CROSS.md, 穴の型); the observation that fills the hole from the sentences of a structure is `verantyx.observe` (docs/OBSERVATION.md, 質問の観測).
Keywords: 疑問文 穴 質問の十字 read_question question hole wh.
"""
from __future__ import annotations

import argparse
import functools
import json
import os
import re
import sys
import unicodedata
from dataclasses import replace
from types import SimpleNamespace

SCHEMA = 'verantyx.semantic_read/1'
# A design constant (not a measurement): the construction reader gives up above 256 tokens (semantic_reader._read_constructions) and the
# convention's inputs are one or two sentences; 1000 characters keeps any such input far inside both bounds.
MAX_TEXT_CHARS = 1000
ERROR_TYPES = ('MISSING_TEXT', 'EMPTY_TEXT', 'TEXT_TOO_LONG', 'BAD_LANG', 'LANG_MISMATCH', 'CONTROL_CHARACTERS', 'BAD_ARGUMENTS')

# What the convention has and this entry does not produce (it abstains instead): type -> why.
NOT_PRODUCED = {
    'role:beneficiary': 'V-てあげる/くれる/もらう: the reader names the phrase recipient; naming it beneficiary needs the verb to be read as a benefit, so the clause is not read',
    'role:experiencer': 'the reader has no indirect (adversative) passive reading',
    'role:cause': 'a noun-phrase cause (で): the reader leaves the で-phrase place|means ambiguous',
    'role:instrument': 'only when the reader decides means; an ambiguous で-phrase is not decided',
    'role:entity(non-person subject of an intransitive verb)': 'the reader names every subject agent; a non-person is not shown, so the subject type is undecided (SUBJECT_TYPE_UNDETERMINED)',
    'comparison:equative': 'ほど / くらい / as ... as: not mapped',
    'comparison:superlative': 'not mapped',
    'comparison:verb': 'a comparison whose predicate is a verb: not mapped',
    'quantifiers': 'every quantity word or numeral outside a time phrase is returned unread (QUANTIFIER_NOT_MAPPED)',
    'scope': 'no quantifier is produced, so no scope is',
    'modality:ability/permission/volition/desire/request/possibility/conjecture/hearsay/question': 'any surface mark of these makes the input unread (UNDETERMINED_MODALITY)',
    'tense:null (subordinate clauses)': 'a sentence of more than one clause is returned unread unless the relation is mapped',
    'relation:cause': 'not mapped', 'relation:contrast': 'not mapped', 'relation:concession': 'not mapped', 'relation:condition': 'not mapped',
    'relation:purpose': 'not mapped', 'relation:sequence': 'not mapped', 'relation:simultaneous': 'not mapped', 'relation:manner': 'not mapped',
    'relation:quote': 'not mapped', 'relation:content': 'not mapped',
    'voice:passive (indirect, honorific, potential, spontaneous)': 'れる/られる is passive only on positive evidence: による/によって; or a に/から phrase of a verb of the closed class _NI_KARA_FREE_PREDICATES. Not evidence: a subject missing from the person table, a subject that is not a person, a verb outside a class. No agent phrase: always UNDETERMINED_VOICE (passive and spontaneous are not told apart without the predicate\'s type; W5-a). られる (potential), a verb of thought/feeling (spontaneous) and any other case: UNDETERMINED_VOICE',
    'voice:causative_passive': 'only from the reader\'s causer/causee roles',
    'en:time and place phrases': 'the English frame has no time/place role; a sentence that has one is returned unread (UNREPRESENTED_CONTENT)',
    'en:possessive determiners': 'her/his/their ... are dropped by the frame; the value cannot be restored, so the sentence is returned unread',
    'en:perfect, progressive, modal verbs': 'tense / modality cannot be decided from the frame',
    'en:verbs outside the known list': 'a verb is accepted only when it is in the closed list of known verbs (UNKNOWN_PREDICATE): a coined verb must not be read; the refusal is `not_supported`, never `unreadable_input` (round 5)',
    'predicate:converse verbs': 'verbs of receiving / borrowing / learning / hearing: the reader names the converse verb and swaps the roles; the convention forbids a replaced word as the predicate, so only the restoration it states (4.6, もらう) is made and the others are not read (PREDICATE_NORMALIZED)',
    'role:goal for existence / residence verbs': 'the place of existence or residence is `place` (convention 2, 4.2); with no shown place the input is not read (PLACE_TYPE_UNDETERMINED)',
    'role:agent / recipient for a capitalised name (English)': 'a capital letter says "a name", not "a person" (a city is written like a person): an intransitive subject and the recipient after `to` need a pronoun or an animate noun (SUBJECT_TYPE_UNDETERMINED / RECIPIENT_TYPE_UNDETERMINED); only the first object of a double-object clause is a recipient by its construction',
    'role:path (を of a verb of going through a space)': 'the convention has no role for the path a motion verb covers (走る・歩く・渡る の を-phrase); the reader calls it patient, which is wrong, so the input is not read (PATH_ROLE_NOT_MAPPED). Also a compound verb whose parts are of that class (the structure of the word, not a word added), and an active clause with an を-phrase whose subject is shown not to be a person, or whose subject has no person evidence and whose を-phrase has place evidence (SUBJECT_TYPE_UNDETERMINED:object or path; W5-a); and an active clause with an を-phrase whose subject has no person evidence and whose predicate is in none of the reader\'s closed classes with an を-object (the corpus transitivity table is not counted as evidence of an object): AGENT_EVIDENCE_MISSING (W5-a rounds 2-3, K64)',
    'predicate:する with a サ変 noun apart from its する (掃除をさせた)': 'convention 3 writes a サ変 verb as noun + する, the reader splits it into する and a patient; the input is not read (PREDICATE_NOT_MAPPED:light verb)',
    'en:two names in a row': 'a proper name before a common noun (a double object) may be one phrase or two roles; not read (NP_BOUNDARY_UNDETERMINED)',
    'en:be + a participle that is also a state adjective': 'closed / opened / finished ... without a by-phrase are a passive and a state alike; the voice is undecided (UNDETERMINED_VOICE)',
}

_JA_CHAR = re.compile('[぀-ヿ㐀-䶿一-鿿ｦ-ﾟ]')
_EN_CHAR = re.compile('[A-Za-z]')


class ReadError(Exception):
    def __init__(self, type_, detail):
        super().__init__(f'{type_}: {detail}')
        self.type = type_; self.detail = detail


# ---------------------------------------------------------------------------------------------------------------------------------
# input checks
# ---------------------------------------------------------------------------------------------------------------------------------
def detect_lang(text):
    """'ja' when the text holds any hiragana / katakana / kanji; else 'en' when it holds an ASCII letter; else None."""
    if _JA_CHAR.search(text): return 'ja'
    if _EN_CHAR.search(text): return 'en'
    return None


def check_input(text, lang=None):
    """Return the language to read in, or raise ReadError with one of ERROR_TYPES."""
    if text is None: raise ReadError('MISSING_TEXT', 'no text was given')
    if not isinstance(text, str): raise ReadError('BAD_ARGUMENTS', 'the text is not a string')
    if not text.strip(): raise ReadError('EMPTY_TEXT', 'the text is empty or only blanks')
    if len(text) > MAX_TEXT_CHARS: raise ReadError('TEXT_TOO_LONG', f'more than {MAX_TEXT_CHARS} characters')
    for ch in text:
        cat = unicodedata.category(ch)
        if cat == 'Cs' or (cat == 'Cc' and ch not in '\n\t\r'):
            raise ReadError('CONTROL_CHARACTERS', f'control character U+{ord(ch):04X}')
    if lang is not None and lang not in ('ja', 'en'): raise ReadError('BAD_LANG', "lang must be 'ja' or 'en'")
    detected = detect_lang(text)
    if lang is not None and detected is not None and detected != lang:
        raise ReadError('LANG_MISMATCH', f'--lang {lang} but the script of the text is {detected}')
    return lang or detected


# ---------------------------------------------------------------------------------------------------------------------------------
# output
# ---------------------------------------------------------------------------------------------------------------------------------
def _refusal(lang, kind, reasons, unsupported=()):
    reasons = list(dict.fromkeys(reasons))
    return {'schema': SCHEMA, 'lang': lang, 'readable': False, 'clauses': [], 'relations': [],
            'abstain': {'kind': kind, 'reasons': reasons}, 'unsupported': list(unsupported), 'clause_meta': []}


def _answer(lang, clauses, relations, meta, unsupported):
    return {'schema': SCHEMA, 'lang': lang, 'readable': True, 'clauses': clauses, 'relations': relations,
            'abstain': None, 'unsupported': list(unsupported), 'clause_meta': meta}


class _Abstain(Exception):
    def __init__(self, kind, reason):
        super().__init__(reason); self.kind = kind; self.reason = reason


def _no(reason, kind='not_supported'):
    raise _Abstain(kind, reason)


# ---------------------------------------------------------------------------------------------------------------------------------
# Japanese
# ---------------------------------------------------------------------------------------------------------------------------------
# reader role name -> convention role name (a closed table; a name that is not here is UNMAPPED_ROLE). `agent`, `recipient` are decided below.
_ROLE_TABLE = {'patient': 'patient', 'causer': 'causer', 'causee': 'causee', 'time': 'time', 'quotation': 'quotation', 'standard': 'standard',
               'attribute': 'attribute', 'value': 'value', 'entity': 'entity', 'result': 'result', 'companion': 'companion',
               'source': 'source', 'origin': 'source', 'location': 'place', 'place': 'place', 'means': 'instrument',
               'direction': 'goal', 'limit': 'goal'}
_DEMONSTRATIVES = frozenset(('この', 'その', 'あの', 'どの'))
# a quantity word anywhere in the input is returned unread (nothing quantified is produced)
_QUANT_SURFACES = frozenset(('すべて', '全て', '全部', '全員', '皆', 'みんな', '各', '各自', 'それぞれ', '誰も', '何も', 'だれも', 'どれも', 'だけ', 'しか',
                             'のみ', 'ばかり', 'ほとんど', '大半', '一部', '約', 'およそ', '以上', '以下', '未満', '少なくとも', '多く', 'いくつか',
                             '何人か', 'いくつも', '少し', 'たくさん', '全く', 'まったく', '毎回', 'すべての', '全ての'))
# surface marks of the convention's modalities (§5). assert with one of these is not null-modality: the input is returned unread.
_MODAL_MARKS = re.compile(
    r'なければ|なくては|なくちゃ|なきゃ|ねばならな|べき|べく|てもいい|てもよい|てもかまわ|てはいけ|てはなら|ちゃいけ|たい(?!へ)|たがる|つもり|ましょう|'
    r'よう(?:と|か|に(?:なる|する))|てください|て下さい|なさい|てくれ(?:ない)?[。！？?]?$|かもしれ|かも[。！？?]?$|だろう|でしょう|はず|に違いない|'
    r'そうだ|そうです|そうだった|らしい|ようだ|ようです|みたい|という(?:こと|話|噂)|と(?:言|いわ)れ|ことができ|できる|できた|できな|'
    r'ようになっ|(?:か|かね|かな)[。！？?]*$|[？?]')
_OBLIGATION_MARKS = re.compile(r'なければならな|なくてはならな|なきゃならな|ねばならな|べき')
_PROHIBITION_MARKS = re.compile(r'てはいけな|てはならな|ちゃいけな')
_PAST_COPULA = re.compile(r'(?:だった|でした|ではなかった|でなかった|じゃなかった|ではありませんでした|でありました)[。！？?]*\s*$')
_NONPAST_COPULA = re.compile(r'(?:だ|です|である|ではない|でない|じゃない|ではありません|でありません)[。！？?]*\s*$')
_CONNECTIVE_POS = ('接続詞',)
# transitive-looking potential forms: a lemma in -eru whose -u verb exists (読める / 読む) may be a potential form
_E_ROW = {'える': 'う', 'ける': 'く', 'せる': 'す', 'てる': 'つ', 'ねる': 'ぬ', 'べる': 'ぶ', 'める': 'む', 'れる': 'る', 'げる': 'ぐ', 'でる': 'づ'}


def _strip_demonstrative(role, toks):
    text = role.span.text
    inside = [t for t in toks if t[1] >= role.span.start and t[2] <= role.span.end]
    if inside and inside[0][0].feature.pos1 == '連体詞' and inside[0][0].surface in _DEMONSTRATIVES:
        rest = text[len(inside[0][0].surface):].lstrip()
        return rest
    return text


def _clause_sort_key(c):
    return (c.predicate_span.start, c.predicate_span.end)


def _comparable(c):
    return (c.predicate, tuple(sorted((r.name, r.span.text) for r in c.roles)), c.polarity, c.modality, c.time)


def _is_predicate_token(toks, i):
    """A token that heads a predicate: a verb (not an auxiliary use after て / で / ば: ている, てしまう, なければならない), an adjective, an
    adjectival noun, the negative copula の ない of ではない, or the copula だ / です. The auxiliaries れる, せる, ない, た are not."""
    w = toks[i][0]; f = w.feature
    prev = toks[i - 1][0] if i else None
    if f.pos1 == '動詞':
        return not (f.pos2 == '非自立可能' and prev is not None and prev.feature.pos1 == '助詞' and prev.surface in ('て', 'で', 'ば'))
    if f.pos1 == '形容詞':
        if f.pos2 != '非自立可能': return True
        return prev is not None and prev.feature.pos1 == '助詞' and prev.surface in ('は', 'も') and i > 1 and toks[i - 2][0].surface in ('で', 'じゃ')
    if f.pos1 == '形状詞': return True
    if f.pos1 == '助動詞' and _lemma(w) in ('だ', 'です'): return i > 0 and toks[i - 1][0].feature.pos1 in ('名詞', '代名詞', '形状詞', '助詞', '接尾辞', '数詞')
    return False


def _lemma(word):
    return getattr(word.feature, 'lemma', None) or word.surface


def _base_of(word):
    from .typed_edges import _base
    return _base(word)


def _potential_suspect(word):
    """A verb lemma that could be a potential form of another verb (読める of 読む): the e-row ending swapped for the u-row ending is a verb the
    dictionary knows. Over-reports (開ける, 届ける are pairs, not potentials): an over-report only abstains."""
    lemma = _base_of(word)
    from .frames import transitivity
    if transitivity(lemma) == 'trans': return False         # a verb the corpus uses with を (食べる, 育てる) is the verb itself, not a potential form
    for tail, rep in _E_ROW.items():
        if lemma.endswith(tail) and len(lemma) > len(tail):
            from .typed_edges import _tagger
            cand = lemma[:-len(tail)] + rep
            ws = list(_tagger()(cand))
            return len(ws) == 1 and ws[0].feature.pos1 == '動詞' and not ws[0].is_unk and ws[0].surface == cand
    return False


def _read_ja(text, placement=None):
    from . import semantic_reader as R
    from .typed_edges import _tagger
    toks = R._tokens(text)
    unk_pred = []
    for i, (w, a, b) in enumerate(toks):
        if w.is_unk and (w.feature.pos1 in ('動詞', '形容詞', '形状詞') or (
                i + 1 < len(toks) and toks[i + 1][0].feature.pos1 == '動詞' and _lemma(toks[i + 1][0]) in ('為る', 'する') and w.feature.pos1 == '名詞')):
            unk_pred.append(w.surface)
    if unk_pred:
        return _refusal('ja', 'unreadable_input', ['UNKNOWN_PREDICATE_WORD:' + unk_pred[0]])
    if not any(_is_predicate_token(toks, i) for i in range(len(toks))):
        view0 = R.document_view({'d': text})
        reasons = [u.reason for u in view0.unread]
        if any(r == 'interjection is not a proposition' for r in reasons):
            return _refusal('ja', 'unreadable_input', ['INTERJECTION_OR_FORMULA'])
        return _refusal('ja', 'unreadable_input', ['NO_PREDICATE_TOKEN'])
    view = R.document_view({'d': text})
    if any(u.reason == 'interjection is not a proposition' for u in view.unread):
        return _refusal('ja', 'unreadable_input', ['INTERJECTION_OR_FORMULA'],
                        [{'predicate': None, 'span': [u.span.start, u.span.end], 'reasons': [u.reason]} for u in view.unread])
    unsupported_report = []
    for c in view.clauses:
        if c.unsupported:
            unsupported_report.append({'predicate': c.predicate, 'span': [c.predicate_span.start, c.predicate_span.end], 'reasons': list(c.unsupported)})
    for u in view.unread:
        unsupported_report.append({'predicate': None, 'span': [u.span.start, u.span.end], 'reasons': [u.reason]})
    try:
        clauses, relations, meta = _map_ja(text, toks, view, R)
    except _Abstain as stop:
        if placement is not None:
            out = _typed_reread_ja(text, toks, view, R, placement, stop, unsupported_report)
            return out if out['readable'] else _w3b3_read_ja(text, R, placement, out, unsupported_report)
        return _refusal('ja', stop.kind, [stop.reason], unsupported_report)
    return _answer('ja', clauses, relations, meta, unsupported_report)


class _CachedQuery:
    """W3-b2: the placement as the plans ask it, for ONE sentence: a word is asked once, whichever plan asks it first (the plans of W3-b1 and of W3-b2 share the answers).
    `id` is the id of the placement it wraps."""
    def __init__(self, inner):
        self.inner, self.answers = inner, {}

    def query(self, term):
        if term not in self.answers: self.answers[term] = self.inner.query(term)
        return self.answers[term]

    @property
    def id(self):
        return getattr(self.inner, 'id', None)


def _typed_reread_ja(text, toks, view, R, placement, stop, report):
    """W3-b1 / W3-b2: a refusal of the reader gets one more look with the DIRECT types of the words (docs/READING_SOUNDNESS.md K62-K65, K94-K99). The decisions (the
    tables, the gates) are the reader's (R.typed_plan_*, R.typed_trigger_*); what is done here is to run this entry's own rules over the roles they decide (_map_ja with
    `typed`) and to write the reasons. A refusal keeps its own reason first; one PLACEMENT_* reason follows it.
    The order (K94): W3-b1's trigger and plan first. A sentence W3-b1 reads is returned as W3-b1 reads it (W3-b2 does not run), except that the frame of a CONFIRMED predicate
    (K95) may stop a path U reading. A sentence W3-b1's plan refuses gets W3-b2's plan of the same path; when that is refused too, the output is W3-b1's refusal. A
    sentence W3-b1 has no trigger for gets the trigger of W3-b2 (U3). What W3-b2's plan refused is in the diagnosis (typed_explain_ja), not in the output."""
    trace = getattr(placement, 'w3b2_trace', None)
    note = trace if trace is not None else {}
    note.update({'w3b1_trigger': None, 'w3b1': None, 'w3b2_trigger': None, 'w3b2': None, 'frame': None})
    query = _CachedQuery(placement)
    first = [stop.reason]

    def refuse(why):
        return _refusal('ja', stop.kind, first + [why], report)
    kind = R.typed_trigger_ja(text, view)
    second = None
    if kind is None:
        second = R.typed_trigger_w3b2_ja(text, view)
        if second is None:
            note['w3b2'] = 'PLACEMENT_W3B2_NOT_TRIGGERED'
            return _refusal('ja', stop.kind, first, report)
    clause = view.clauses[0]
    pred_i = next((i for i, (w, a, b) in enumerate(toks) if a == clause.predicate_span.start), None)
    written = _written_predicate(toks, pred_i) if kind != 'S4' else None
    voice = None
    if kind != 'S4':
        from .frames import transitivity
        try:
            voice = _voice_ja(clause, toks, pred_i, transitivity)
        except _Abstain:
            voice = None
    strip = lambda role: _strip_demonstrative(role, toks)

    def reread(typed):
        """Our own rules over what a plan decided: (clauses, relations, meta) or (None, the reason of the refusal). The order of the gates is W3-b1's (K63)."""
        try:
            clauses, relations, meta = _map_ja(text, toks, SimpleNamespace(clauses=(typed['clause'],), unread=()), R, typed=typed)
        except _Abstain as again:
            return None, 'PLACEMENT_REREAD_ABSTAINS:' + again.reason
        # K63 (table change record 2): the ending of the predicate must be one of the four that the present rules turn into a polarity and a tense; checked
        # after the reread, so the reasons of everything refused before are unchanged
        ending = R.typed_tail_ja(toks, typed['clause'])
        if ending: return None, ending
        # K63 (table change record 3): the head may be a derived verb (a potential, a spontaneous or a short causative looks like a verb of its own); checked after the
        # ending, so the reasons of everything refused before are unchanged
        derived = R.typed_head_derived_ja(toks, typed['clause'])
        if derived: return None, derived
        for c in clauses:               # K97: the demonstrative the part stood after, as the last key of the clause (nothing before it changes)
            if typed.get('role_flags'): c['role_flags'] = {role: dict(flags) for role, flags in typed['role_flags'].items()}
        return (clauses, relations, meta), None
    if second is None:
        note['w3b1_trigger'] = kind
        if kind == 'U':
            typed, why = R.typed_plan_u_ja(clause, toks, query, voice=voice, written=written, strip=strip, role_map=_ROLE_TABLE)
        else:
            typed, why = R.typed_plan_s4_ja(text, toks, clause, query)
        if typed is not None:
            done, why_read = reread(typed)
            if done is None:
                note['w3b1'] = why_read
                return refuse(why_read)
            note['w3b1'] = 'READ'
            if kind == 'U':             # K95: the frame of a CONFIRMED predicate narrows what W3-b1 read (no new question: the predicate was asked)
                why_frame = R.typed_frame_check_ja(toks, typed, query.query(written))
                if why_frame:
                    note['frame'] = why_frame
                    return refuse(why_frame)
            return _answer('ja', done[0], done[1], done[2], report)
        note['w3b1'] = why
        note['w3b2_trigger'] = kind
        refused = why
    else:
        note['w3b2_trigger'] = second
        refused = None
    if kind == 'S4':
        typed2, why2 = R.typed_plan_s4_w3b2_ja(text, toks, clause, query, role_map=_ROLE_TABLE)
    else:
        typed2, why2 = R.typed_plan_u_w3b2_ja(clause, toks, query, voice=voice, written=written, strip=strip, role_map=_ROLE_TABLE)
    if typed2 is not None:
        done, why_read = reread(typed2)
        if done is not None:
            note['w3b2'] = 'READ'
            return _answer('ja', done[0], done[1], done[2], report)
        why2 = why_read
    note['w3b2'] = why2
    return refuse(refused) if refused is not None else _refusal('ja', stop.kind, first, report)


class _ExplainQuery:
    """W3-b2: wraps a placement for `typed_explain_ja`: the same questions go through, and `w3b2_trace` is where `_typed_reread_ja` writes what each step decided."""
    def __init__(self, inner):
        self.inner, self.w3b2_trace = inner, {}

    def query(self, term):
        return self.inner.query(term)

    @property
    def id(self):
        return getattr(self.inner, 'id', None)


def typed_explain_ja(text, placement):
    """W3-b2, for tests and measurements: what the typed steps decided for a Japanese input, the output of `read` unchanged. {'w3b1_trigger': 'U' | 'S4' | None,
    'w3b1': 'READ' | the reason W3-b1 stopped | None, 'w3b2_trigger': 'U' | 'S4' | 'U3' | None, 'w3b2': 'READ' | the reason W3-b2 stopped | None, 'frame': None | the
    reason the frame of the predicate stopped a reading of W3-b1}. All None when no typed step ran (no placement, English, the reader read it alone). It runs `read` itself
    (the same functions in the same order): no second decision is written here."""
    blank = {'w3b1_trigger': None, 'w3b1': None, 'w3b2_trigger': None, 'w3b2': None, 'frame': None}
    chosen = check_input(text, None)
    query = _placement_query(placement)
    if chosen != 'ja' or query is None: return blank
    probe = _ExplainQuery(query)
    _read_ja(text, probe)
    return dict(blank, **probe.w3b2_trace) if probe.w3b2_trace else blank


# ---------------------------------------------------------------------------------------------------------------------------------
# W3-b3: a sentence of two predicates read as two crosses and an edge (docs/READING_SOUNDNESS.md section 10C, K114-K122). The decisions that need no question (the cut, its
# uniqueness, the gates of the whole sentence, the text of each clause) are the reader's (R.w3b3_*, on a snapshot of the tokens); what is done here is to read each clause with this
# entry's own rules (`_read_ja`), to ask the placement, to decide the arm of the head of a relative clause by type, and to write the output. A sentence this path does not read gets
# the output it was handed back, the same object; the reason is in the diagnosis (`clause_scope_explain_ja`), not in the output.
# ---------------------------------------------------------------------------------------------------------------------------------
_W3B3_DEPTH = [0]       # > 0 while a clause is being read: the path does not start again inside a clause (K114 2)


def _w3b3_blank():
    return {'triggered': False, 'cut': None, 'clause_texts': [], 'clause_reads': [], 'head': None, 'edges': [], 'reason': 'W3B3_NOT_TRIGGERED:not_reached', 'read': False}


def _w3b3_snapshot(text, R):
    """The tokens of `text` as plain values, taken at once (the features of the tagger's nodes are valid only until the next parse)."""
    toks = R._tokens(text)
    preds = [_is_predicate_token(toks, i) for i in range(len(toks))]
    return R.w3b3_snapshot(toks, preds)


def _w3b3_read_clause(string, query, R):
    """K117 4: one clause text through the entry itself (a placement is given, so the typed readings of W3-b1 / W3-b2 run as they always do). The path is switched off inside."""
    _W3B3_DEPTH[0] += 1
    try:
        return _read_ja(string, query)
    finally:
        _W3B3_DEPTH[0] -= 1


def _w3b3_clause(string, query, R, number):
    """(out, None) when the clause text is read as exactly one clause with no relation and the two existing gates (the ending, the derived verb) let it through; else (None, reason)."""
    out = _w3b3_read_clause(string, query, R)
    if not out['readable'] or len(out['clauses']) != 1 or out['relations']:
        return None, 'CLAUSE_UNREAD:%d:%s' % (number, out['abstain']['reasons'][0] if not out['readable'] else 'not one clause')
    why = _w3b3_gates(string, out, R)
    if why: return None, 'CLAUSE_FORM_NOT_READ:' + why
    return out, None


def _w3b3_gates(string, out, R):
    """K117 5: the ending gate and the derived-verb gate (W3-b1, K63) on the clause text and the predicate range the entry gave it. The reason or None."""
    span = out['clause_meta'][0]['span']
    clause = SimpleNamespace(predicate_span=SimpleNamespace(start=span[0], end=span[1]))
    toks = R._tokens(string)
    return R.typed_tail_ja(toks, clause) or R.typed_head_derived_ja(toks, clause)


def _w3b3_has_subject(c):
    return 'agent' in c['roles'] or 'entity' in c['roles'] or (c['voice'] == 'passive' and 'patient' in c['roles'])


def _w3b3_same_but(a, b, role):
    """The reading `a` is the reading `b` apart from the arm `role` of `a` (the predicate, the polarity, the tense, the modality, the voice and every other role)."""
    keep = lambda c: {k: c[k] for k in ('predicate', 'polarity', 'tense', 'modality', 'voice')}
    return keep(a) == keep(b) and {k: v for k, v in a['roles'].items() if k != role} == b['roles']


def _w3b3_head_arm(snap, cut, text, texts, a_out, b_out, query, R, note):
    """K118 (relative only): (the reading of the relative clause with the head in its arm, the relation, None) or (None, None, reason)."""
    head, why = R.w3b3_head(snap, cut)
    if why: return None, None, why
    c0 = a_out['clauses'][0]
    if c0['voice'] != 'active': return None, None, 'HEAD_ROLE_UNDETERMINED:voice'
    answer = query.query(c0['predicate'])
    ptype, why = R.placement_type(answer)
    if why or ptype not in R.TYPED_FRAMES: return None, None, 'HEAD_ROLE_UNDETERMINED:frame_not_read:' + (why or ptype)
    rows = R.TYPED_FRAMES[ptype]
    if set(c0['roles']) - ({r[0] for r in rows} | {'recipient'}): return None, None, 'HEAD_ROLE_UNDETERMINED:role_outside_frame'
    empty = [r for r in rows if r[3] == 'arg' and r[0] not in c0['roles']]
    ni_filled = 'recipient' in c0['roles']    # round 2 (review r1 M1): this arm is filled only by a recipient that the entry read; a case-marked noun read as a time or a place leaves it empty
    undecided = ptype == 'P_COMMUNICATE' and not ni_filled
    note['head'] = {'arm': None, 'basis': None, 'empty_arms': [r[0] for r in empty] + (['NI_UNDECIDED'] if undecided else []), 'candidates': []}
    if len(empty) + (1 if undecided else 0) != 1: return None, None, 'HEAD_ROLE_UNDETERMINED:empty_arms=%d' % (len(empty) + (1 if undecided else 0))
    if not empty: return None, None, 'HEAD_ROLE_UNDETERMINED:undecided_arm'
    row = empty[0]
    head_answer = query.query(head['surface'])
    kind, payload = R.placement_fit(head_answer, row[2])
    if kind == 'mismatch': return None, None, 'HEAD_ROLE_UNDETERMINED:type:mismatch:' + payload[0]
    if kind is None: return None, None, 'HEAD_ROLE_UNDETERMINED:type:' + payload
    fkind, finfo = R.predicate_frame(answer)
    if fkind is None: return None, None, 'HEAD_ROLE_UNDETERMINED:type:' + finfo
    if fkind == 'confirmed':
        if row[1][0] not in finfo: return None, None, 'HEAD_ROLE_UNDETERMINED:type:PLACEMENT_FRAME_PARTICLE_NOT_CONFIRMED:%s:%s' % (ptype, row[1][0])
        if not set(payload) <= finfo[row[1][0]]: return None, None, 'HEAD_ROLE_UNDETERMINED:type:PLACEMENT_FRAME_TYPE_NOT_CONFIRMED:%s:%s:%s' % (ptype, row[1][0], '+'.join(payload))
    note['head'].update({'arm': row[0], 'basis': 'placement_%s:%s' % (kind, '+'.join(payload)), 'candidates': list(payload)})
    for adjunct in rows:
        if adjunct[3] != 'adjunct' or adjunct[0] in c0['roles']: continue
        k2, _ = R.placement_fit(head_answer, adjunct[2], adjunct=True)
        if k2 in ('direct', 'all_candidates'): return None, None, 'HEAD_ROLE_UNDETERMINED:adjunct_tie'
    if set(payload) & set(R.W3B3_OUTER_TYPES): return None, None, 'HEAD_ROLE_UNDETERMINED:outer_relation_type'
    # the head put in its arm, read again by the entry (its gates are the clause's)
    refill = head['surface'] + row[1][0] + texts['a']
    again, why = _w3b3_clause(refill, query, R, 0)
    if again is None: return None, None, 'HEAD_ROLE_UNDETERMINED:refill_reread'
    r0 = again['clauses'][0]
    if r0['roles'].get(row[0]) != head['surface'] or not _w3b3_same_but(r0, c0, row[0]): return None, None, 'HEAD_ROLE_UNDETERMINED:refill_reread'
    hosts = [name for name, value in b_out['clauses'][0]['roles'].items() if value == head['surface']]
    if len(hosts) != 1: return None, None, 'HEAD_NOT_IN_HOST'
    c0 = dict(r0)
    if not c0.get('predicate_basis'): c0['predicate_basis'] = 'placement_direct:' + ptype
    c0['role_basis'] = dict(c0.get('role_basis') or {}, **{row[0]: 'placement_%s:%s' % (kind, '+'.join(payload))})
    return c0, {'type': 'relative', 'from': 0, 'to': 1, 'head': {'from_role': row[0], 'to_role': hosts[0]}}, None


def _w3b3_relation(cut, c1, query, R):
    """K119: (the relation, None) or (None, the reason)."""
    relation = cut['relation']
    if relation in ('TE_UNDETERMINED', 'PARALLEL_UNDETERMINED'): return None, 'RELATION_TYPE_UNDETERMINED:' + relation
    if relation == 'condition':
        if c1['tense'] == 'past': return None, 'RELATION_TYPE_UNDETERMINED:condition_past_main'
        if cut['kind'] == 'と':
            ptype, why = R.placement_type(query.query(c1['predicate']))
            if c1['predicate'] in R.W3B3_QUOTE_VERBS or why or ptype in R.W3B3_QUOTE_TYPES: return None, 'RELATION_TYPE_UNDETERMINED:quote_possible'
    return {'type': relation, 'from': 0, 'to': 1}, None


def _w3b3_ellipsis(snap, cut, texts, c0, c1, b_out, query, R):
    """K120: (the second clause, None) or (None, the reason). The only fill is the topic into a main clause that has no subject and no phrase of its own with が / は."""
    from .frames import transitivity
    a_phr, b_phr = R.w3b3_sides(snap, cut)
    subject = lambda ps: any(p['particle'] == 'が' or (p['particle'] is not None and p['particle'].endswith('は')) for p in ps)
    if (cut['kind'] != 'relative' and a_phr and a_phr[0]['particle'] == 'は' and c0['voice'] == 'active' and c1['voice'] == 'active' and 'agent' not in c1['roles']
            and not subject(b_phr)):
        topic = ''.join(snap[k].surface for k in range(a_phr[0]['lo'], a_phr[0]['plo']))
        if c0['roles'].get('agent') == topic:
            again, why = _w3b3_clause(topic + 'は' + texts['b'], query, R, 1)
            if again is None or again['clauses'][0]['roles'].get('agent') != topic or not _w3b3_same_but(again['clauses'][0], c1, 'agent'): return None, 'ELLIPSIS_UNDETERMINED:subject'
            c1 = again['clauses'][0]
    sides = ((c0, c1, a_phr, b_phr), (c1, c0, b_phr, a_phr))
    for c, other, own, others in sides:
        if not _w3b3_has_subject(c) and subject(others): return None, 'ELLIPSIS_UNDETERMINED:subject'
    for c, other, own, others in sides:
        if c['voice'] == 'active' and 'patient' not in c['roles'] and transitivity(c['predicate']) != 'intrans':
            if any(value != c['roles'].get('agent') for value in other['roles'].values()): return None, 'ELLIPSIS_UNDETERMINED:object'
    for c, other, own, others in sides:
        for role in ('goal', 'source', 'place', 'recipient', 'instrument', 'companion', 'time'):
            if role in other['roles'] and role not in c['roles']:
                if c['predicate'] == other['predicate'] or (role in ('goal', 'source') and (c['predicate'] in R._GOAL_PREDICATES or c['predicate'] in _PATH_VERBS)):
                    return None, 'ELLIPSIS_UNDETERMINED:' + role
    return c1, None


def _w3b3_read_ja(text, R, placement, out, report):
    """The path of two predicates (K114-K122). Returns a reading when the whole chain of gates lets the sentence through, else `out` itself (the refusal it was given)."""
    note = getattr(placement, 'w3b3_trace', None)
    if note is None: note = {}
    note.update(_w3b3_blank())

    def stop(why):
        note['reason'] = why
        return out
    if _W3B3_DEPTH[0]: return stop('W3B3_NOT_TRIGGERED:depth')
    if len(list(R._sentences(text))) != 1: return stop('W3B3_NOT_TRIGGERED:sentences')
    snap = _w3b3_snapshot(text, R)
    cut, why = R.w3b3_scope(snap)
    if cut is None: return stop(why)
    note['triggered'] = True
    note['cut'] = {'kind': cut['kind'], 'connective': cut['connective'], 'token_span': [snap[(cut['tokens'] or (cut['a_end'],))[0]].start, snap[(cut['tokens'] or (cut['a_end'],))[-1]].end]}
    why = R.w3b3_form_gate(snap, cut) or R.w3b3_unique(snap, cut)
    if why: return stop(why)
    texts, why = R.w3b3_texts(snap, text, cut)
    if why: return stop(why)
    note['clause_texts'] = [texts['a'], texts['b']]
    for which in ('a', 'b'):
        why = R.w3b3_tokens_match(snap, _w3b3_snapshot(texts[which], R), cut, which)
        if why: return stop(why)
    # from here on the placement is asked: one cache for the whole path
    query = _CachedQuery(placement)
    reads = []
    for number, which in enumerate(('a', 'b')):
        got, why = _w3b3_clause(texts[which], query, R, number)
        if got is None:
            note['clause_reads'].append({'text': texts[which], 'readable': False, 'clause': None, 'reason': why})
            return stop(why)
        reads.append(got)
        note['clause_reads'].append({'text': texts[which], 'readable': True, 'clause': dict(got['clauses'][0]), 'reason': None})
    c0, c1 = dict(reads[0]['clauses'][0]), dict(reads[1]['clauses'][0])
    relation = None
    if cut['kind'] == 'relative':
        c0, relation, why = _w3b3_head_arm(snap, cut, text, texts, reads[0], reads[1], query, R, note)
        if why: return stop(why)
        note['clause_reads'][0]['clause'] = dict(c0)
    if not cut['tense_kept']:
        c0 = dict(c0, tense=None)
        note['clause_reads'][0]['clause'] = dict(c0)
    if relation is None:
        relation, why = _w3b3_relation(cut, c1, query, R)
        if why:
            if why.split(':')[1] in ('TE_UNDETERMINED', 'PARALLEL_UNDETERMINED'): note['edges'] = [{'type': why.split(':')[1], 'from': 0, 'to': 1}]
            return stop(why)
    c1, why = _w3b3_ellipsis(snap, cut, texts, c0, c1, reads[1], query, R)
    if why: return stop(why)
    note['clause_reads'][1]['clause'] = dict(c1)
    why = R.w3b3_focus_gate(snap, cut)
    if why: return stop(why)
    meta = [{'rule': reads[0]['clause_meta'][0]['rule'], 'span': list(texts['a_span'])}, {'rule': reads[1]['clause_meta'][0]['rule'], 'span': list(texts['b_span'])}]
    note['reason'] = None
    note['read'] = True
    return _answer('ja', [c0, c1], [relation], meta, report)


class _Explain3Query:
    """W3-b3: wraps a placement for `clause_scope_explain_ja`: the same questions go through, and `w3b3_trace` is where `_w3b3_read_ja` writes what each gate decided."""
    def __init__(self, inner):
        self.inner, self.w3b3_trace = inner, {}

    def query(self, term):
        return self.inner.query(term)

    @property
    def id(self):
        return getattr(self.inner, 'id', None)


def clause_scope_explain_ja(text, placement):
    """W3-b3, for tests and measurements: what the path of two predicates decided for a Japanese input, the output of `read` unchanged. {'triggered': bool, 'cut': {kind, connective,
    token_span} | None, 'clause_texts': [...], 'clause_reads': [{text, readable, clause, reason}], 'head': {arm, basis, empty_arms, candidates} | None, 'edges': [...] (TE_UNDETERMINED /
    PARALLEL_UNDETERMINED: not relations of the convention, never in the output), 'reason': None | a reason of K122, 'read': bool}. When the path was not reached (no placement, English,
    the entry or a typed reading read the input alone) the reason is W3B3_NOT_TRIGGERED:not_reached. It runs `read` itself: no second decision is written here."""
    blank = _w3b3_blank()
    chosen = check_input(text, None)
    query = _placement_query(placement)
    if chosen != 'ja' or query is None: return blank
    probe = _Explain3Query(query)
    _read_ja(text, probe)
    return dict(blank, **probe.w3b3_trace) if probe.w3b3_trace else blank


def _map_ja(text, toks, view, R, typed=None):
    sentences = list(R._sentences(text))
    if view.unread:
        _no('UNREAD_SPAN:' + view.unread[0].reason)
    supported = [c for c in view.clauses if not c.unsupported]
    unsupported = [c for c in view.clauses if c.unsupported]
    if not supported:
        _no('NO_SUPPORTED_CLAUSE')
    # a rejected alternative reading of the same predicate (a copula read as 'A is B-than-C' beside the comparison) is listed, not counted
    def overlaps(a, b):
        return a.predicate_span.start <= b.predicate_span.start and b.predicate_span.end <= a.predicate_span.end or (
            b.predicate_span.start <= a.predicate_span.start and a.predicate_span.end <= b.predicate_span.end)
    def answered(u, sup):
        """W5-a round 2 (auditor's decision B2): the one rejected alternative reading that READING_CONVENTIONS §9.2 (1) writes down -- a
        copula / negative-copula reading left unsupported only because its value is a predicate phrase, and the comparison read from inside
        it is supported. Any other reason, alone or beside that one, is not set aside: the input is not read (UNSUPPORTED_CLAUSE)."""
        return (sup.rule == 'comparison' and u.rule in ('copula', 'negation') and bool(u.unsupported)
                and all(reason == R._PREDICATE_VALUE_REASON for reason in u.unsupported))

    def inside(u, sup):
        """u is a rejected alternative reading of the predicate of the supported clause sup: its predicate range lies wholly in sup's, or --
        the one other shape -- u is a copula / negative-copula reading whose predicate range is the whole predicate phrase ('弟より強い') and
        sup is the comparison read from inside it. Any other overlap is not an alternative reading of the same predicate. Either way every
        reason u was unsupported for must be answered by sup (answered)."""
        if sup.predicate_span.start <= u.predicate_span.start and u.predicate_span.end <= sup.predicate_span.end: return answered(u, sup)
        return (u.rule in ('copula', 'negation') and sup.rule == 'comparison'
                and u.predicate_span.start <= sup.predicate_span.start and sup.predicate_span.end <= u.predicate_span.end) and answered(u, sup)
    stray = [c for c in unsupported if not any(inside(c, s) for s in supported)]
    if stray:
        _no('UNSUPPORTED_CLAUSE')
    # one reading per predicate: identical readings are one; different readings of the same predicate are a tie (abstain)
    merged = []
    for c in sorted(supported, key=_clause_sort_key):
        twin = next((m for m in merged if overlaps(m, c)), None)
        if twin is None: merged.append(c)
        elif _comparable(twin) != _comparable(c) and twin.rule != c.rule:
            if {twin.rule, c.rule} <= {'frame', 'copula', 'negation', 'comparison'} and 'comparison' in (twin.rule, c.rule):
                merged[merged.index(twin)] = c if c.rule == 'comparison' else twin
            else:
                _no('COMPETING_READINGS')
        elif _comparable(twin) != _comparable(c):
            _no('COMPETING_READINGS')
    supported = merged
    # every sentence: no sentence-initial connective (a relation between sentences the entry does not map), the verbs covered
    for (s0, s1) in sentences:
        inside = [i for i, (w, a, b) in enumerate(toks) if a >= s0 and b <= s1]
        if inside and toks[inside[0]][0].feature.pos1 in _CONNECTIVE_POS:
            _no('RELATION_NOT_MAPPED:sentence-initial connective')
    pred_idx = [i for i in range(len(toks)) if _is_predicate_token(toks, i)]
    covered = set()
    for i in pred_idx:
        a, b = toks[i][1], toks[i][2]
        if any(c.predicate_span.start <= a and b <= c.predicate_span.end for c in supported): covered.add(i)
        elif toks[i][0].feature.pos1 in ('助動詞', '形容詞') and any(c.rule in ('copula', 'negation') for c in supported): covered.add(i)   # だ / です / ではない
    changed = True
    while changed:                                   # the tail of a compound verb (stem + stem, two tokens) continues a covered verb
        changed = False
        for i in pred_idx:
            if i not in covered and i > 0 and (i - 1) in covered and toks[i][0].feature.pos1 == '動詞' and toks[i - 1][0].feature.pos1 == '動詞':
                covered.add(i); changed = True
    last = max(pred_idx)
    if last not in covered:
        _no('MAIN_PREDICATE_NOT_READ')
    if any(i not in covered for i in pred_idx):
        _no('UNCOVERED_PREDICATE')
    # surface checks that apply to the whole input
    for w, a, b in toks:
        if w.surface in _QUANT_SURFACES:
            _no('QUANTIFIER_NOT_MAPPED:' + w.surface)
    time_spans = [(r.span.start, r.span.end) for c in supported for r in c.roles if r.name == 'time']
    for w, a, b in toks:
        if w.feature.pos2 == '数詞' and not any(x <= a and b <= y for x, y in time_spans):
            _no('QUANTIFIER_NOT_MAPPED:numeral')
    if _benefactive_in(toks):
        _no('BENEFACTIVE_NOT_PRODUCED')
    if len(supported) > 1:
        relations = _relations_ja(supported)
    else:
        relations = []
    out = []; meta = []
    for c in supported:
        out.append(_clause_ja(c, text, toks, R, typed=typed)); meta.append({'rule': c.rule, 'span': [c.predicate_span.start, c.predicate_span.end]})
    return out, relations, meta


_BEN_VERBS = ('あげる', 'やる', 'くれる', '差し上げる', 'もらう', '貰う', 'いただく', '頂く', 'くださる')


def _benefactive_in(toks):
    from .typed_edges import _base
    for k in range(len(toks) - 1):
        if toks[k][0].surface in ('て', 'で') and _base(toks[k + 1][0]) in _BEN_VERBS: return True
    return False


def _relations_ja(clauses):
    """Only a relative clause's relation is mapped (the 'adnominal' rule, from the modifying clause to the clause that holds its head noun). A
    sentence of several clauses with any other joint is returned unread (RELATION_NOT_MAPPED)."""
    if len(clauses) != 2: _no('RELATION_NOT_MAPPED:' + ','.join(sorted({c.rule for c in clauses})))
    mods = [i for i, c in enumerate(clauses) if c.rule == 'adnominal']
    mains = [i for i, c in enumerate(clauses) if c.rule != 'adnominal']
    if len(mods) != 1 or len(mains) != 1: _no('RELATION_NOT_MAPPED:' + ','.join(sorted({c.rule for c in clauses})))
    return [{'type': 'relative', 'from': mods[0], 'to': mains[0]}]


# Verbs of going through a space: the を-phrase is the path covered (the convention has no role for it), not the thing acted on. A closed class of
# verbs that name a movement through a place; decided by the verb alone.
_PATH_VERBS = frozenset(('走る', '歩く', '渡る', '飛ぶ', '跳ぶ', '進む', '通る', '泳ぐ', '越える', '歩む', '駆ける', '横切る', '登る', '上る', '下る',
                         '降りる', '出る', '離れる', '巡る', '辿る', '滑る', '散歩する', '通過する', '横断する', '移動する', '出発する', '旅する'))


@functools.lru_cache(maxsize=None)
def _single_verb(surface):
    """The tagger's one word for `surface` when it is a single verb written as it is; else None."""
    from .typed_edges import _tagger
    ws = list(_tagger()(surface))
    return ws[0] if len(ws) == 1 and ws[0].surface == surface and ws[0].feature.pos1 == '動詞' else None


@functools.lru_cache(maxsize=None)
def _stem_lemma(stem):
    """The lemma of the verb whose continuative form (stem + ます) is `stem`, when the tagger reads stem + ます as a verb and ます; else None."""
    from .typed_edges import _tagger, _base
    ws = list(_tagger()(stem + 'ます'))
    return _base(ws[0]) if len(ws) == 2 and ws[0].feature.pos1 == '動詞' and ws[1].surface == 'ます' else None


@functools.lru_cache(maxsize=None)
def _is_compound_path_verb(lemma):
    """A compound verb made of the closed class _PATH_VERBS: split the lemma in two; the second half is one verb that is, or whose lemma is, a verb
    of _PATH_VERBS (飛び越える: 越える), or the first half is the continuative form of such a verb (突っ走る: 走る). The class is extended by the
    structure of the word, not by a word added to it. A lemma that is itself in the class is the existing test's, not this one's."""
    from .typed_edges import _base
    if lemma in _PATH_VERBS: return False
    for i in range(1, len(lemma)):
        first, second = lemma[:i], lemma[i:]
        word = _single_verb(second)
        if word is None: continue
        if second in _PATH_VERBS or _base(word) in _PATH_VERBS: return True
        if _stem_lemma(first) in _PATH_VERBS: return True
    return False


def _object_frame_known(predicate, R):
    """W5-a round 3 (auditor's decision B3, (β) variant C): a predicate is known to take an を-object only when it is in one of the reader's
    own closed classes whose frame writes the を-phrase as the thing acted on (X が Y に Z を渡す, X を Y に変える / 任命する / 置く,
    X を囲む ...). The corpus table (frames.transitivity) is not a source: its 'trans' is the share of を among a verb's case edges, which
    does not tell a path を from an object を (docs/READING_SOUNDNESS.md K64). A predicate in no class is not known to take an object."""
    classes = (R._TRANSFER_PREDICATES, R._SHARING_PREDICATES, R._CHANGE_PREDICATES - R._INTRANSITIVE_CHANGE_PREDICATES, R._SELECTION_PREDICATES,
               R._PROCESSING_PREDICATES, R._PRODUCT_PREDICATES, R._CONTAINMENT_PREDICATES, R._PLACEMENT_PREDICATES)
    return any(predicate in cls for cls in classes)


def _clause_ja(c, text, toks, R, typed=None):
    from .frames import transitivity
    pred_i = next((i for i, (w, a, b) in enumerate(toks) if a == c.predicate_span.start), None)
    body = c.body_span or c.span
    surface_tail = text[c.predicate_span.start:body.end]
    raw_roles = list(c.roles)
    names = [r.name for r in raw_roles]
    # ---- predicate ----
    if c.rule in ('copula', 'negation') and c.predicate in ('identity', 'property'):
        if c.predicate == 'property' or any(r.name == 'attribute' for r in raw_roles): _no('UNMAPPED_ROLE:attribute')
        value = next(r for r in raw_roles if r.name == 'value')
        vtoks = [t for t in toks if t[1] >= value.span.start and t[2] <= value.span.end]
        content = [t for t in vtoks if t[0].feature.pos1 not in ('助詞', '助動詞', '補助記号', '記号')]
        if any(t[0].feature.pos1 in ('動詞', '形容詞', '形状詞') for t in content): _no('PREDICATE_VALUE_NOT_MAPPED')
        if value.rule == 'quantity': _no('QUANTIFIER_NOT_MAPPED:value')
        predicate = 'だ'
    elif c.rule == 'comparison':
        predicate = _comparison_predicate(c)
    else:
        predicate = c.predicate
        if predicate in ('identity', 'property', 'comparison'): _no('PREDICATE_NOT_MAPPED:' + predicate)
        # The reader normalizes a verb of receiving / borrowing / learning to its converse (frames.CONVERSE: the verb of giving / lending / teaching) and swaps the roles.
        # The convention (3) forbids a replaced word as the predicate, so a predicate that is not the dictionary form of the verb actually
        # written is not returned (round 5, M7). The roles are not turned back: the convention has no rule for them.
        # One restoration the convention itself states (4.6): もらう is the predicate, the giver (に / から) is `agent` and the subject is `recipient`;
        # the reader's roles for it are already those (agent = the giver, recipient = the subject) under the name あげる, so only the name is restored.
        written = _written_predicate(toks, pred_i)
        if written in ('もらう', '貰う') and predicate == 'あげる': predicate = written
        if written is None or written != predicate: _no('PREDICATE_NORMALIZED:' + str(predicate) + '<-' + str(written))
    if pred_i is not None and toks[pred_i][0].feature.pos1 == '動詞' and _potential_suspect(toks[pred_i][0]):
        _no('UNDETERMINED_MODALITY:possible potential form')
    # ---- voice ----
    voice = _voice_ja(c, toks, pred_i, transitivity)
    # A verb of going through a space takes the path with を (道を歩く): the convention has no role for it and the reader names it patient;
    # a サ変 noun apart from its する (掃除をさせた) is written by the convention as one predicate (掃除する), not as する with a patient. Neither is guessed.
    if voice == 'active' and any(r.name == 'patient' for r in raw_roles):
        if c.predicate in _PATH_VERBS or _is_compound_path_verb(c.predicate): _no('PATH_ROLE_NOT_MAPPED:' + c.predicate)
        if c.predicate == 'する': _no('PREDICATE_NOT_MAPPED:light verb')
    if voice == 'causative' and c.predicate == 'する' and any(r.name == 'patient' for r in raw_roles): _no('PREDICATE_NOT_MAPPED:light verb')
    # ---- roles ----
    roles = {}
    has_patient = 'patient' in names
    override = typed is not None and typed.get('mode') == 'override'
    for r in ([] if override else raw_roles):
        name = r.name
        value = _strip_demonstrative(r, toks)
        if not value: _no('EMPTY_ROLE_VALUE:' + name)
        if value not in text: _no('VALUE_NOT_IN_INPUT:' + name)
        if name == 'agent':
            if voice != 'passive' and has_patient:
                # W5-a: an active clause with an object names its subject agent only when nothing says the subject is not a person, and the を-phrase
                # is not a place (a place with を is a path or a starting point of a movement: 庭を歩く). Otherwise the type is not decided.
                objects = [x.span.text for x in raw_roles if x.name == 'patient']
                if _not_person_evidence(r.span.text, R) or (not R._is_person_phrase(r.span.text) and any(
                        R._is_place_phrase(o) or o.replace(' ', '').replace('\u3000', '').split('の')[-1] in R._SPOT_NOUNS for o in objects)):
                    _no('SUBJECT_TYPE_UNDETERMINED:object or path:' + r.span.text)
                # W5-a rounds 2-3 (auditor's decision B3, (β) variant C): an を-phrase is the thing acted on only in a frame the reader's own closed
                # classes know. A subject with no person evidence (_is_person_phrase: persons, bodies of persons, animals; the tree has no class of
                # vehicles, so none counts) and an を-phrase of a predicate in none of those classes may be a thing moving along a path: not an agent,
                # the input is not read. The corpus transitivity table does not count as a known frame (K64).
                if (not R._is_person_phrase(r.span.text)
                        and any(x.name == 'patient' and R._particle_after(toks, x.span.end) == 'を' for x in raw_roles)
                        and not _object_frame_known(c.predicate, R)):
                    _no('AGENT_EVIDENCE_MISSING:' + r.span.text)
                mapped = 'agent'
            elif voice == 'passive' or has_patient:
                mapped = 'agent'
            elif R._is_person_phrase(r.span.text):
                mapped = 'agent'
            else:
                _no('SUBJECT_TYPE_UNDETERMINED:' + r.span.text)
        elif name == 'recipient':
            mapped = _recipient_ja(c, r, R)
        elif name in _ROLE_TABLE:
            mapped = _ROLE_TABLE[name]
            if c.rule == 'comparison' and name == 'direction': continue
        elif c.rule == 'comparison' and name in ('dimension', 'direction'):
            continue
        else:
            _no('UNMAPPED_ROLE:' + name)
        if mapped in roles: _no('DUPLICATE_ROLE:' + mapped)
        roles[mapped] = value
    if override:
        # W3-b1 path U: the roles were decided by the type table (reader.typed_plan_u_ja); the checks of a value are the ones above
        for mapped, r in typed['roles']:
            value = _strip_demonstrative(r, toks)
            if not value: _no('EMPTY_ROLE_VALUE:' + r.name)
            if value not in text: _no('VALUE_NOT_IN_INPUT:' + r.name)
            if mapped in roles: _no('DUPLICATE_ROLE:' + mapped)
            roles[mapped] = value
    # ---- polarity, tense, modality ----
    polarity = c.polarity
    if polarity not in ('+', '-'): _no('UNDETERMINED_POLARITY')
    tense = c.time if c.time in ('past', 'nonpast') else None
    if tense is None:
        if _PAST_COPULA.search(surface_tail): tense = 'past'
        elif _NONPAST_COPULA.search(surface_tail): tense = 'nonpast'
        elif c.rule == 'comparison' and re.search(r'(?:でした|だった)[。！？?]*$', surface_tail): tense = 'past'
        elif c.rule == 'comparison' and re.search(r'(?:だ|です|である)?[。！？?]*$', surface_tail) and surface_tail.rstrip('。！？? ').endswith(('い', 'だ', 'です')): tense = 'nonpast'
        else: _no('UNDETERMINED_TENSE')
    modality = {'assert': None, 'obligation': 'obligation', 'prohibition': 'prohibition'}.get(c.modality, 'unmapped')
    if modality == 'unmapped': _no('UNDETERMINED_MODALITY:' + c.modality)
    sentence_tail = text[body.start:body.end]
    marks = _MODAL_MARKS.search(sentence_tail)
    if modality is None and marks: _no('UNDETERMINED_MODALITY:' + marks.group(0))
    if modality == 'obligation' and not _OBLIGATION_MARKS.search(sentence_tail): _no('UNDETERMINED_MODALITY:obligation without its mark')
    if modality == 'prohibition' and not _PROHIBITION_MARKS.search(sentence_tail): _no('UNDETERMINED_MODALITY:prohibition without its mark')
    if modality in ('obligation', 'prohibition') and polarity == '-': _no('UNDETERMINED_POLARITY')
    out = {'predicate': predicate, 'roles': roles, 'polarity': polarity, 'tense': tense, 'modality': modality, 'voice': voice}
    if c.rule == 'comparison':
        out['comparison'] = _comparison_kind(c, text)
    if typed is not None:             # where the roles / the predicate came from (last keys; nothing before them changes)
        if typed.get('predicate_basis'): out['predicate_basis'] = typed['predicate_basis']
        if typed.get('role_basis'): out['role_basis'] = dict(typed['role_basis'])
    return out


def _written_predicate(toks, pred_i):
    """The dictionary form of the predicate verb as it is WRITTEN: the base form of the token that starts the predicate span, and for a
    サ変 verb the noun + する. None when there is no such token."""
    if pred_i is None: return None
    from .typed_edges import _base
    w, a, b = toks[pred_i]
    lemma = _base(w)
    if w.feature.pos1 == '名詞' and pred_i + 1 < len(toks) and _base(toks[pred_i + 1][0]) == 'する' and toks[pred_i + 1][1] == b:
        return w.surface + 'する'
    if lemma == 'する' and pred_i > 0 and toks[pred_i - 1][0].feature.pos1 == '名詞' and toks[pred_i - 1][2] == a:
        return toks[pred_i - 1][0].surface + 'する'
    return lemma


def _comparison_predicate(c):
    if c.predicate in ('comparison',) or not c.predicate: _no('PREDICATE_NOT_MAPPED:comparison')
    return c.predicate


def _comparison_kind(c, text):
    standard = next((r for r in c.roles if r.name == 'standard'), None)
    if standard is None: _no('UNMAPPED_ROLE:standard')
    after = text[standard.span.end:standard.span.end + 2]
    if after.startswith('より'): return 'comparative'
    _no('COMPARISON_NOT_PRODUCED:' + after)


def _recipient_ja(c, r, R):
    """recipient -> recipient (a verb of transfer / telling and a person) ; goal (a verb of motion / placement and a place) ; place (a verb of
    existence / residence and a place: convention 2 and 4.2 keep `goal` for the end point of motion or placement only); else undecided."""
    pred = c.predicate
    value = r.span.text
    if pred in R._TRANSFER_PREDICATES:
        if R._is_person_phrase(value): return 'recipient'
        _no('RECIPIENT_TYPE_UNDETERMINED:' + value)
    if pred in R._GOAL_PREDICATES or pred in R._PLACEMENT_PREDICATES:
        if R._is_place_phrase(value): return 'goal'
        _no('GOAL_TYPE_UNDETERMINED:' + value)
    if pred in R._LOCATION_PREDICATES:
        if R._is_place_phrase(value): return 'place'
        _no('PLACE_TYPE_UNDETERMINED:' + value)
    _no('RECIPIENT_TYPE_UNDETERMINED:' + pred)


# A transitive verb that acts on its object and takes NO argument with に / から in any sense of the active verb (a recipient, a goal, a result or a
# starting point of its own). With such a verb a に/から phrase of a れる/られる clause cannot be an argument of the active verb (an honorific
# reading: <person>が<person>に V-れた = "<person> V-ed to <person>"), so it is the agent of a passive. NOT 割る (a に-result: <物>を<数>つに割る), 盗む (a
# から-origin), 蹴る (a に-goal), 叩く (a wide sense), 怒る (a に-addressee), nor any verb of _TRANSFER/_GOAL/_PLACEMENT/_LOCATION/_CHANGE_PREDICATES.
# Closed: a word is added only for a verb every sense of which meets this basis, and adding one makes the entry say `passive` more often.
_NI_KARA_FREE_PREDICATES = frozenset(('叱る', '褒める', '追いかける', '殴る', '噛む'))

# Verbs of thought, feeling, recollection, expectation and perception whose れる/られる is also SPONTANEOUS ("it comes to mind"): the form does not
# choose between the passive and the spontaneous, so a clause with one of them and no agent phrase is a tie. A list that makes the entry
# abstain more often: a verb that meets the basis may be added.
_SPONTANEOUS_PREDICATES = frozenset((
    '思う', '思い出す', '偲ぶ', '感じる', '感ずる', '案じる', '案ずる', '悔やむ', '惜しむ', '待つ', '考える', '予想する', '期待する', '心配する',
    '懸念する', '危惧する', '想像する', '推測する', '聞く', '見る'))


def _not_person_evidence(phrase, R=None):
    """Positive evidence that the subject is NOT a person: the head of the phrase (the part after the last の) is a noun of a closed class every
    sense of which is not a person (R._SPOT_NOUNS a spot or a geographic feature, _FORMAT_NOUNS a format, _LANGUAGE_NAMES a language or a script,
    _COLOR_NAMES a colour, _GATHERING_NOUNS an event). A phrase that is also person-evidence (R._is_person_phrase) is a tie, so no evidence.
    Not evidence: the absence of a person-phrase, a word-ending (_PLACE_SUFFIXES: 会社, 局 name bodies that act), a place name, a time word, a number+counter."""
    if R is None:
        from . import semantic_reader as R
    compact = phrase.replace(' ', '').replace('\u3000', '')
    if not compact or R._is_person_phrase(compact): return False
    head = compact.split('の')[-1]
    return any(head in cls for cls in (R._SPOT_NOUNS, R._FORMAT_NOUNS, R._LANGUAGE_NAMES, R._COLOR_NAMES, R._GATHERING_NOUNS))


def _voice_ja(c, toks, pred_i, transitivity):
    """active / passive / causative / causative_passive from the auxiliaries after the predicate and the roles; undecided -> abstain."""
    if pred_i is None: _no('UNDETERMINED_VOICE:predicate token')
    from .typed_edges import _base
    chain = []
    j = pred_i + 1
    while j < len(toks) and (toks[j][0].feature.pos1 == '助動詞' or (toks[j][0].feature.pos1 == '動詞' and toks[j][0].feature.pos2 == '非自立可能')):
        chain.append(_base(toks[j][0])); j += 1
    # サ変 predicate: the clause predicate token may be the noun; the voice auxiliaries follow the する verb
    if not chain and pred_i + 1 < len(toks) and toks[pred_i][0].feature.pos1 == '名詞' and _base(toks[pred_i + 1][0]) == 'する':
        j = pred_i + 2
        while j < len(toks) and (toks[j][0].feature.pos1 == '助動詞' or (toks[j][0].feature.pos1 == '動詞' and toks[j][0].feature.pos2 == '非自立可能')):
            chain.append(_base(toks[j][0])); j += 1
    passive = [x for x in chain if x in ('れる', 'られる')]
    causative = [x for x in chain if x in ('せる', 'させる')]
    names = {r.name for r in c.roles}
    if not passive and not causative: return 'active'
    if causative and not passive:
        if {'causer', 'causee'} <= names: return 'causative'
        _no('UNDETERMINED_VOICE:causative without causer and causee')
    if causative and passive:
        if {'causer', 'causee'} <= names: return 'causative_passive'
        _no('UNDETERMINED_VOICE:causative passive without causer and causee')
    # れる / られる alone: passive, honorific, potential and spontaneous all look alike
    agent = next((r for r in c.roles if r.name == 'agent'), None)
    patients = [r for r in c.roles if r.name == 'patient']
    from . import semantic_reader as R
    def particle_after(role):
        return R._particle_after([(w, a, b) for w, a, b in toks], role.span.end)
    if len(patients) == 1:
        subject_marked = particle_after(patients[0]) in ('が', 'は')
        # W1-a3: a passive is returned only on a POSITIVE piece of evidence. "The subject is not known to be a person" is no evidence of a thing
        # (a person who is owed respect may be missing from the person table), and "the verb is not in a class" is no evidence either.
        #   1a  a によって phrase                                                                      -> passive
        #   1b  a に/から phrase and a verb of _NI_KARA_FREE_PREDICATES (transitive, no に/から argument of its own) -> passive; any other verb -> abstain,
        #       whoever the subject is (the に/から phrase may be an argument of the active verb with an honorific, or the agent)
        #   2   no agent phrase and a transitive verb: always abstain (W5-a). れる/られる with no agent phrase is passive, spontaneous (a verb of
        #       recollection, thought or feeling that no list can close) or honorific alike, and "the subject is not a person" tells the
        #       passive from none of them; so no passive without 1a or 1b. (The earlier rule 2c, a passive on a non-person subject, is withdrawn.)
        if agent is not None:
            by = particle_after(agent)
            if subject_marked and by == 'によって': return 'passive'
            if subject_marked and by in ('に', 'から'):
                if c.predicate in _NI_KARA_FREE_PREDICATES and transitivity(c.predicate) == 'trans': return 'passive'
                _no('UNDETERMINED_VOICE:passive or honorific')
            _no('UNDETERMINED_VOICE:れる/られる with an object')
        if subject_marked and transitivity(c.predicate) == 'trans':
            if 'られる' in passive: _no('UNDETERMINED_VOICE:passive or potential')
            if c.predicate in _SPONTANEOUS_PREDICATES: _no('UNDETERMINED_VOICE:passive or spontaneous')
            # a subject that is not a person rules out the honorific, not the spontaneous (nothing tells the two apart without the verb's type)
            if _not_person_evidence(patients[0].span.text): _no('UNDETERMINED_VOICE:passive or spontaneous')
            _no('UNDETERMINED_VOICE:passive or honorific')
    _no('UNDETERMINED_VOICE:れる/られる')


# ---------------------------------------------------------------------------------------------------------------------------------
# English
# ---------------------------------------------------------------------------------------------------------------------------------
_EN_REGULAR_VERBS = frozenset((
    'open', 'close', 'finish', 'start', 'chase', 'approve', 'hire', 'call', 'follow', 'help', 'invite', 'visit', 'watch', 'wash', 'clean',
    'cook', 'carry', 'check', 'move', 'pull', 'push', 'kick', 'kiss', 'love', 'like', 'need', 'want', 'order', 'pick', 'plan', 'play', 'print',
    'repair', 'review', 'save', 'share', 'sign', 'stop', 'support', 'test', 'touch', 'train', 'use', 'wait', 'walk', 'work', 'paint', 'praise',
    'ask', 'answer', 'borrow', 'deliver', 'accept', 'reject', 'update', 'remove', 'replace', 'announce', 'approve', 'inspect', 'prepare',
    'schedule', 'cancel', 'confirm', 'notify', 'warn', 'thank', 'welcome', 'protect', 'attack', 'rescue', 'repair', 'discuss', 'examine',
    'complete', 'submit', 'publish', 'collect', 'arrange', 'design', 'produce', 'create', 'introduce', 'explain', 'promise', 'recommend',
    'offer', 'show', 'serve', 'return', 'forward', 'assign', 'provide', 'mail', 'email', 'hand', 'pass', 'lift', 'drop', 'fix', 'break',
    'organize', 'manage', 'lead', 'teach', 'train', 'greet', 'meet', 'visit', 'select', 'elect', 'appoint'))


def _en_known_verbs():
    from . import en_frames as en
    return set(en.IRREG.values()) | set(en.DITRANS) | set(_EN_REGULAR_VERBS)


_EN_PRONOUN_AGENTS = frozenset(('he', 'she', 'they', 'i', 'we', 'you', 'him', 'her', 'them', 'us', 'me'))
_EN_POSSESSIVES = frozenset(('his', 'her', 'their', 'its', 'our', 'my', 'your'))
_EN_QUANT = frozenset(('every', 'each', 'all', 'no', 'some', 'any', 'most', 'many', 'few', 'several', 'both', 'only', 'one', 'two', 'three',
                       'four', 'five', 'six', 'seven', 'eight', 'nine', 'ten', 'half', 'more', 'less', 'least', 'nobody', 'everyone', 'everybody'))
# participles that are also everyday adjectives of a state: 'was closed' is a passive and a description of the state alike
_EN_STATE_PARTICIPLES = frozenset(('closed', 'opened', 'broken', 'tired', 'finished', 'done', 'married', 'excited', 'interested', 'surprised',
                                   'worried', 'scared', 'pleased', 'satisfied', 'lost', 'prepared', 'crowded', 'crashed', 'stopped', 'hidden',
                                   'known', 'shut', 'filled', 'covered', 'locked', 'blocked', 'frozen', 'dressed', 'seated', 'tied', 'settled'))
_EN_GREETING_WORDS = frozenset(('thank', 'thanks', 'hello', 'hi', 'goodbye', 'bye', 'sorry', 'please', 'welcome', 'cheers', 'congratulations'))
_EN_INTERJECTIONS = frozenset(('oh', 'ah', 'wow', 'hmm', 'um', 'uh', 'hey', 'oops', 'ouch', 'yes', 'no', 'okay', 'ok', 'yeah', 'huh', 'aha', 'hurray'))


def _en_words(text):
    return re.findall(r"[A-Za-z][A-Za-z'\-]*|[0-9]+", text)


def _en_irregular_table():
    from . import en_frames as en
    table = {}
    for line in en._IRR.replace('\n', '').split('|'):
        p = line.split()
        if len(p) == 3: table[p[0]] = (p[1], p[2])
    return table


def _read_en(text, placement=None):
    from . import en_frames as en
    words = _en_words(text)
    low = [w.lower() for w in words]
    if not words: return _refusal('en', 'unreadable_input', ['NO_LANGUAGE'])
    known = _en_known_verbs()
    aux = set(en.AUX)
    # positive evidence that the input is no proposition: only a formula / interjection words, or no token that can be a verb
    if all(w in _EN_GREETING_WORDS | _EN_INTERJECTIONS | {'you', 'very', 'much', 'so', 'a', 'lot', 'for', 'your', 'the', 'help', 'again', 'all'} for w in low) and \
            any(w in _EN_GREETING_WORDS | _EN_INTERJECTIONS for w in low):
        return _refusal('en', 'unreadable_input', ['INTERJECTION_OR_FORMULA'])
    if not any((en.lemma(w) in known or w in aux or w in en.IRREG) for w in low):
        # no word of the closed verb list: that says the list is short, not that the input cannot be read (round 5, M8)
        return _refusal('en', 'not_supported', ['UNKNOWN_PREDICATE'] + (['PLACEMENT_PREDICATE_UNIDENTIFIED'] if placement is not None else []))
    frame, why = en.read_typed(text)
    if frame is None:
        return _refusal('en', 'not_supported', ['EN_UNREAD:' + r for r in why] or ['EN_UNREAD'])
    try:
        clause, meta = _clause_en(text, words, low, frame, known, aux, en)
    except _Abstain as stop:
        reasons = [stop.reason]
        if placement is not None and stop.reason.startswith('UNKNOWN_PREDICATE:'):
            reasons.append(_placement_reason_en(stop.reason, placement, en))
        return _refusal('en', stop.kind, reasons)
    return _answer('en', [clause], [], [meta], [])


def _placement_reason_en(reason, placement, en):
    """W3-b1: English is not read with a placement (the placement holds no English predicate and no everyday English noun has a direct type). The one
    thing added to `UNKNOWN_PREDICATE:<verb>` is what the placement says of the verb: the reason of the gate, or FRAME_NOT_READ:en."""
    from . import semantic_reader as R
    lemma = en.lemma(reason.split(':', 1)[1].split()[0])
    noun, why = R.placement_type(placement.query(lemma))
    return '%s:predicate:%s' % (why, lemma) if why else 'PLACEMENT_FRAME_NOT_READ:en'


def _person_en(value, text=None):
    """Positive evidence that the phrase names a person / animate: a personal pronoun or an animate head noun (en_frames.ANIMATE). A capital
    letter is evidence that a word is a NAME, not that the name is a person's (the name of a city is written like the name of a person): round 6,
    so it is not consulted, wherever the word stands in the input."""
    from . import en_frames as en
    head = value.split()[-1] if value else ''
    return value.lower() in _EN_PRONOUN_AGENTS or head.lower() in en.ANIMATE or head.lower().rstrip('s') in en.ANIMATE


def _recipient_by_construction_en(text, recipient, patient):
    """True when the recipient is the FIRST object of a double-object clause (Lisa sent Paul a message): that construction itself makes the
    first object the one who receives, whatever it is called, so no lexical evidence of a person is needed. A phrase after `to` (or any
    other preposition) has no such construction: it is a recipient only on evidence of a person (a place is written the same way)."""
    if not (recipient and patient): return False
    r, p = text.find(recipient), text.find(patient)
    if r < 0 or p < 0 or r >= p: return False
    return not re.search(r'\b(?:to|for|at|from|in|on|into|toward|towards)\s+$', text[:r], re.I)


def _en_inflections(verb, table):
    """The written forms a known verb can take (closed rules: -s, -es, -ed, -d, a doubled final letter + -ed, consonant + y -> -ied / -ies, and the
    irregular table's past and participle)."""
    out = {verb, verb + 's', verb + 'es', verb + 'ed', verb + 'd', verb + verb[-1] + 'ed'}
    if len(verb) > 1 and verb.endswith('y') and verb[-2] not in 'aeiou':
        out.update((verb[:-1] + 'ied', verb[:-1] + 'ies'))
    out.update(table.get(verb, ()))
    return out


def _clause_en(text, words, low, frame, known, aux, en):
    if frame.ambiguous or frame.inferred: _no('EN_AMBIGUOUS_OR_INFERRED')
    frame_head = frame.predicate.split()[0]
    # locate the verb token as it is WRITTEN (the reader's head may be a lemma that en_frames guessed wrong, e.g. one with a letter too many)
    k = next((i for i, w in enumerate(low) if i > 0 and (en.lemma(w) == frame_head or w == frame_head)), None)
    table = _en_irregular_table()
    if k is None:                       # no written verb token: the old gate; the refusal for the missing token comes where the verb group is read
        head, predicate = frame_head, frame.predicate
        if head not in known and en.lemma(head) not in known and head.rstrip('e') not in {x.rstrip('e') for x in known}:
            _no('UNKNOWN_PREDICATE:' + frame.predicate)
    else:
        # the dictionary form is decided from the written form and the closed list alone: exactly one known verb that the written form is an
        # inflection of; none -> UNKNOWN_PREDICATE, more than one -> a tie (abstain)
        forms = sorted(v for v in known if low[k] in _en_inflections(v, table))
        if not forms: _no('UNKNOWN_PREDICATE:' + frame.predicate)
        if len(forms) > 1: _no('PREDICATE_FORM_UNDETERMINED:' + low[k] + ':' + ','.join(forms))
        head = forms[0]
        predicate = ' '.join([head] + frame.predicate.split()[1:])
    if any(w in _EN_QUANT for w in low): _no('QUANTIFIER_NOT_MAPPED')
    if any(w in _EN_POSSESSIVES for w in low): _no('UNREPRESENTED_CONTENT:possessive determiner')
    if re.search(r'[0-9]', text): _no('QUANTIFIER_NOT_MAPPED:numeral')
    if re.search(r'[?]|^(?:who|what|where|when|why|how|do|does|did|is|are|was|were)\b', text.strip(), re.I) and not text.strip().lower().startswith(('did not', 'does not')):
        _no('UNDETERMINED_MODALITY:question')
    # locate the verb group
    if k is None: _no('UNDETERMINED_TENSE:verb token')
    prev = low[k - 1]
    j = k - 1
    neg = False
    if prev in en.NEG or prev == "n't":
        neg = True; j = k - 2; prev = low[j] if j >= 0 else ''
    auxw = prev if prev in aux else None
    form = low[k]
    used = {k}
    voice = 'active'
    if auxw is None:
        if neg: _no('UNDETERMINED_TENSE:negation without an auxiliary')
        base = head
        if base in table:
            past_f, pp_f = table[base]
            if form in (base + 's', base + 'es'): tense = 'nonpast'
            elif form == base and past_f != base: tense = 'nonpast'
            elif form == past_f and past_f != base: tense = 'past'
            elif form == base == past_f: _no('UNDETERMINED_TENSE:past and present forms are the same')
            else: _no('UNDETERMINED_TENSE:participle without an auxiliary')
        else:
            if form.endswith('ed'): tense = 'past'
            elif form == base or form in (base + 's', base + 'es') or form.rstrip('s') == base: tense = 'nonpast'
            else: _no('UNDETERMINED_TENSE:' + form)
    elif auxw in ('did',): tense = 'past'
    elif auxw in ('does', 'do'): tense = 'nonpast'
    elif auxw == 'will': tense = 'nonpast'
    elif auxw in ('was', 'were', 'is', 'are', 'am'):
        base = head
        pp = table[base][1] if base in table else None
        if not (form.endswith('ed') or (pp is not None and form == pp)) or neg: _no('UNDETERMINED_VOICE:' + auxw + ' ' + form)
        # be + a participle that is also a common adjective (closed, broken, tired ...) and has no by-phrase says a STATE as readily as a passive:
        # the two readings tie, so the voice is undecided (a by-phrase decides it: it is a passive)
        if form in _EN_STATE_PARTICIPLES and not frame.agent: _no('UNDETERMINED_VOICE:state or passive: ' + form)
        voice = 'passive'; tense = 'past' if auxw in ('was', 'were') else 'nonpast'
        used.add(j)
    else:
        _no('UNDETERMINED_TENSE:auxiliary ' + auxw)
    if auxw in ('did', 'does', 'do', 'will'):
        if form != head and not (head in table and form == head): _no('UNDETERMINED_TENSE:' + form)
        used.add(j)
    if neg:
        used.add(j + 1)
    # roles
    roles = {}
    agent, patient, recipient = frame.agent, frame.patient, frame.recipient
    for name, value in (('agent', agent), ('patient', patient), ('recipient', recipient)):
        if not value: continue
        if value not in text: _no('VALUE_NOT_IN_INPUT:' + name)
    if agent:
        if patient or voice == 'passive':
            roles['agent'] = agent
        elif _person_en(agent):
            roles['agent'] = agent
        else:
            _no('SUBJECT_TYPE_UNDETERMINED:' + agent)
    for name, value in (('agent', agent), ('patient', patient), ('recipient', recipient)):
        parts = value.split() if value else []
        if len(parts) >= 2 and all(x[:1].isupper() for x in parts): _no('NP_BOUNDARY_UNDETERMINED:' + value)    # two names in a row: one phrase or two roles?
    if patient: roles['patient'] = patient
    if recipient:
        if not (_person_en(recipient) or _recipient_by_construction_en(text, recipient, patient)): _no('RECIPIENT_TYPE_UNDETERMINED:' + recipient)
        roles['recipient'] = recipient
    if not roles: _no('NO_ROLE')
    ordered = {k: roles[k] for k in ('agent', 'patient', 'recipient') if k in roles}
    # every word must be accounted for: a role phrase, the verb group, a determiner, the preposition of the agent / recipient phrase, a particle
    accounted = set()
    for value in (agent, patient, recipient):
        accounted.update(w.lower() for w in _en_words(value or ''))
    accounted.update(en.DET); accounted.update({'to', 'by'}); accounted.update(head.split()); accounted.update(low[i] for i in used)
    accounted.update(w for w in predicate.split())
    accounted.update(low[i] for i in range(len(low)) if low[i] in aux or low[i] in en.NEG)
    leftover = [w for i, w in enumerate(low) if w not in accounted and i != k]
    if leftover: _no('UNREPRESENTED_CONTENT:' + leftover[0])
    clause = {'predicate': predicate, 'roles': ordered, 'polarity': '-' if frame.negated else '+', 'tense': tense, 'modality': None, 'voice': voice}
    if bool(neg) != bool(frame.negated): _no('UNDETERMINED_POLARITY')
    return clause, {'rule': 'en_frames', 'span': [0, len(text)]}


# ---------------------------------------------------------------------------------------------------------------------------------
# entry
# ---------------------------------------------------------------------------------------------------------------------------------
_UNSET = object()


def _placement_query(placement):
    """The placement to ask: a path (the variable VERA_PLACEMENT when none is given; empty = no placement; the placement module's own variable is NOT
    read), an object with `query(term)` (a fake in a test), or None (no placement, whatever the variable says)."""
    if placement is _UNSET:
        placement = os.environ.get('VERA_PLACEMENT')
    if placement is None:
        return None
    if isinstance(placement, str):
        if not placement.strip(): return None
        from . import semantic_reader as R
        return R.CoarseQuery(placement)
    if callable(getattr(placement, 'query', None)):
        return placement
    raise ReadError('BAD_ARGUMENTS', 'placement must be a path or an object with query(term)')


def read(text, lang=None, *, placement=_UNSET):
    """The reading of `text` as a plain dict (what main() prints). Raises ReadError for an input that is refused (see ERROR_TYPES). `placement`: see _placement_query;
    without one the output is exactly what it was before the placement existed."""
    chosen = check_input(text, lang)
    if chosen is None:
        return _refusal(None, 'not_supported', ['NO_LANGUAGE'])
    query = _placement_query(placement)
    return _read_ja(text, query) if chosen == 'ja' else _read_en(text, query)


# ---------------------------------------------------------------------------------------------------------------------------------
# questions (W3-c2): a question is read as a cross whose ONE arm is a typed hole (docs/EVENT_CROSS.md, "穴の型"; docs/OBSERVATION.md, "質問の観測")
# ---------------------------------------------------------------------------------------------------------------------------------
# `read()` is NOT changed: it still refuses a question (UNREAD_SPAN: interrogative ...). `read_question()` is the new, separate entry. The hole is a
# MARK (one symbol put where the wh word was), never a word: no word is guessed for the hole, no particle is added to make a position readable, and
# a position that needs evidence of the type of the word (to whom, where at, to where, when) is therefore refused with the reader's own reason.
HOLE_MARK_JA = 'Ｘ'        # U+FF38: a common noun for the tagger; the one symbol that replaces a wh word of a Japanese question
HOLE_MARK_EN = 'X'
HOLE_TYPES_VERSION = 1
# The registered table (docs/EVENT_CROSS.md, 穴の型, between BEGIN table:w3c2_holes and END table:w3c2_holes; a test compares the two).
# `arms`: the roles the hole may take (the reader decides the role; a role outside this tuple is refused, never corrected). `types`: the types a filler
# of the hole is expected to have (`types_except`: every type of event_cross.NOUN_TYPE_IDS except these). `unread`: why this hole is not read at all.
WH_TABLE = (
    {'hole': 'PERSON', 'ja': ('誰', 'だれ'), 'en': ('who',), 'noun': False, 'arms': ('agent', 'recipient', 'patient'),
     'types': ('GROUP_ORG', 'PERSON'), 'types_except': None, 'unread': None, 'unread_en': None},
    {'hole': 'THING', 'ja': ('何', 'なに', 'なん'), 'en': ('what',), 'noun': False, 'arms': ('patient',),
     'types': None, 'types_except': ('GROUP_ORG', 'PERSON'), 'unread': None, 'unread_en': None},
    {'hole': 'PLACE', 'ja': ('どこ',), 'en': ('where',), 'noun': False, 'arms': ('place', 'goal', 'source'),
     'types': ('PLACE',), 'types_except': None, 'unread': None, 'unread_en': 'HOLE_ROLE_NOT_PRODUCED:en:place'},
    {'hole': 'TIME', 'ja': ('いつ',), 'en': ('when',), 'noun': False, 'arms': ('time',),
     'types': ('TIME',), 'types_except': None, 'unread': None, 'unread_en': 'HOLE_ROLE_NOT_PRODUCED:en:time'},
    {'hole': 'RESTRICTOR', 'ja': ('どの',), 'en': ('which',), 'noun': True, 'arms': None,
     'types': None, 'types_except': None, 'unread': None, 'unread_en': None},
    {'hole': 'PROPERTY', 'ja': ('どんな',), 'en': (), 'noun': True, 'arms': (),
     'types': None, 'types_except': None, 'unread': 'HOLE_NOT_AN_ARM:property', 'unread_en': 'HOLE_NOT_AN_ARM:property'},
    {'hole': 'CAUSE', 'ja': ('なぜ', 'どうして'), 'en': ('why',), 'noun': False, 'arms': (),
     'types': None, 'types_except': None, 'unread': 'HOLE_RELATION_NOT_PRODUCED:cause', 'unread_en': 'HOLE_RELATION_NOT_PRODUCED:cause'},
    {'hole': 'MANNER', 'ja': ('どうやって', 'どう'), 'en': ('how',), 'noun': False, 'arms': (),
     'types': None, 'types_except': None, 'unread': 'HOLE_RELATION_NOT_PRODUCED:manner', 'unread_en': 'HOLE_RELATION_NOT_PRODUCED:manner'},
)
QUESTION_KINDS = ('WH_QUESTION', 'POLAR_QUESTION')
# The closed list of the reasons that read_question itself gives (a reason of the reader is passed on as the reader wrote it).
QUESTION_REASONS = (
    'NOT_A_QUESTION', 'HOLE_MARK_IN_INPUT', 'QUESTION_MULTI_SENTENCE', 'QUESTION_MULTI_CLAUSE', 'INTERROGATIVE_NOT_FINAL', 'MULTIPLE_HOLES',
    'WH_INDEFINITE', 'WH_NOT_IN_TABLE', 'HOLE_DROPPED', 'HOLE_NOT_ISOLATED', 'HOLE_POSITION_UNDETERMINED', 'EN_FORM_NOT_REWRITTEN',
    'HOLE_NOT_AN_ARM:property', 'HOLE_RELATION_NOT_PRODUCED:cause', 'HOLE_RELATION_NOT_PRODUCED:manner',
    'HOLE_ROLE_NOT_PRODUCED:en:place', 'HOLE_ROLE_NOT_PRODUCED:en:time', 'HOLE_ROLE_NOT_ALLOWED:<wh>:<role>')
_EN_WH_WORDS = frozenset(w for row in WH_TABLE for w in row['en'])


def _hole_row(hole):
    return next(r for r in WH_TABLE if r['hole'] == hole)


def _question_dict(hole_role, hole_type, wh, kind, restrictor, mark, declarative):
    return {'hole_role': hole_role, 'hole_type': hole_type, 'wh': wh, 'kind': kind, 'restrictor': restrictor, 'hole_mark': mark,
            'declarative': declarative}


def _hole_types(row):
    """The sorted type ids a filler of this hole is expected to have (None: decided at observation time, for which+N)."""
    if row['types'] is not None: return sorted(row['types'])
    if row['types_except'] is not None:
        from .event_cross import NOUN_TYPE_IDS    # inside the function: importing the reading entry must not load the cross module
        return sorted(t for t in NOUN_TYPE_IDS if t not in row['types_except'])
    return None


def _with_question(out, question):
    out = dict(out); out['question'] = question
    return out


def _question_refusal(lang, kind, reasons, question, unsupported=()):
    return _with_question(_refusal(lang, kind, reasons, unsupported), question)


def _strings_of(obj):
    if isinstance(obj, str): yield obj
    elif isinstance(obj, dict):
        for k, v in obj.items():
            yield from _strings_of(k); yield from _strings_of(v)
    elif isinstance(obj, (list, tuple)):
        for v in obj: yield from _strings_of(v)


def _isolate_hole(clause, mark):
    """The role whose value is exactly the mark, when the mark stands in exactly one value of the clause and nowhere else; else the reason."""
    total = sum(s.count(mark) for s in _strings_of(clause))
    if total == 0: return None, 'HOLE_DROPPED'
    exact = [role for role, v in clause['roles'].items() if v == mark]
    if total == 1 and len(exact) == 1: return exact[0], None
    return None, 'HOLE_NOT_ISOLATED'


def _finish_question(lang, out, row, wh, restrictor, mark, declarative):
    """From the reading of the declarative form to the answer of read_question (D7, D2, D4, D8)."""
    kind = 'POLAR_QUESTION' if row is None else 'WH_QUESTION'
    if not out['readable']:
        q = _question_dict(None, None, wh, kind, restrictor, mark, declarative)
        return _question_refusal(lang, out['abstain']['kind'], out['abstain']['reasons'], q, out['unsupported'])
    q = _question_dict(None, None, wh, kind, restrictor, mark, declarative)
    if len(out['clauses']) != 1: return _question_refusal(lang, 'not_supported', ['QUESTION_MULTI_CLAUSE'], q, out['unsupported'])
    if row is None:
        q['hole_role'] = 'polarity'
        return _with_question(out, q)
    role, why = _isolate_hole(out['clauses'][0], mark)
    if why is not None: return _question_refusal(lang, 'not_supported', [why], q, out['unsupported'])
    if row['arms'] is not None and role not in row['arms']:
        return _question_refusal(lang, 'not_supported', ['HOLE_ROLE_NOT_ALLOWED:%s:%s' % (wh, role)], q, out['unsupported'])
    q['hole_role'] = role; q['hole_type'] = _hole_types(row)
    return _with_question(out, q)


def _wh_tokens_ja(text, toks):
    """The wh words of a Japanese question, found by the TOKEN: the surface of a token (or of the tokens in a row, for どうやって) that is a wh word of
    WH_TABLE and a pronoun / adnominal / adverb. Returns [(row, wh, start, end, restrictor, indefinite)]; start..end is what the mark replaces."""
    found = []
    wh_forms = sorted(((w, row) for row in WH_TABLE for w in row['ja']), key=lambda p: -len(p[0]))
    i = 0
    while i < len(toks):
        word, a, b = toks[i]
        if word.feature.pos1 not in ('代名詞', '連体詞', '副詞'): i += 1; continue
        hit = None
        for w, row in wh_forms:
            if text.startswith(w, a):
                j = i
                while j < len(toks) and toks[j][2] < a + len(w): j += 1
                if j < len(toks) and toks[j][2] == a + len(w): hit = (w, row, j)    # the wh word ends on a token boundary
                break
        if hit is None: i += 1; continue
        w, row, j = hit
        end, restrictor, k = a + len(w), None, j + 1
        if row['noun']:
            n0 = k
            while k < len(toks) and toks[k][0].feature.pos1 in ('名詞', '接尾辞'): k += 1
            if k > n0: restrictor = text[toks[n0][1]:toks[k - 1][2]]; end = toks[k - 1][2]
        nxt = toks[k] if k < len(toks) else None
        indefinite = bool(nxt is not None and nxt[0].feature.pos2 in ('副助詞', '係助詞') and nxt[0].surface in ('か', 'も', 'でも'))
        found.append((row, w, a, end, restrictor, indefinite))
        i = k
    return found


def _question_ja(text, query):
    from . import semantic_reader as R
    view = R.document_view({'d': text})
    # the reader's own detection of an interrogative (a final か, a ？, ...) or a final question mark that the construction reader read past
    if not (any(u.reason == 'interrogative source does not assert a fact' for u in view.unread) or text.rstrip().endswith(('?', '？'))):
        return _refusal('ja', 'not_supported', ['NOT_A_QUESTION'])
    mark = HOLE_MARK_JA
    plain = _question_dict(None, None, None, None, None, mark, None)    # the kind is told once the wh words are counted
    if len(list(R._sentences(text))) != 1: return _question_refusal('ja', 'not_supported', ['QUESTION_MULTI_SENTENCE'], plain)
    if mark in text: return _question_refusal('ja', 'not_supported', ['HOLE_MARK_IN_INPUT'], plain)
    toks = R._tokens(text)
    # the declarative form: the sentence-final marks and final particles (by part of speech, not by word) are taken off and a full stop is put
    cut = len(toks)
    while cut > 0 and (toks[cut - 1][0].feature.pos1 == '補助記号' or (toks[cut - 1][0].feature.pos1 == '助詞' and toks[cut - 1][0].feature.pos2 == '終助詞')): cut -= 1
    stop = toks[cut][1] if cut < len(toks) else len(text)
    found = _wh_tokens_ja(text, toks)
    if found: plain = _question_dict(None, None, None, 'WH_QUESTION', None, mark, None)
    if any(f[5] for f in found): return _question_refusal('ja', 'not_supported', ['WH_INDEFINITE'], plain)
    if len(found) >= 2: return _question_refusal('ja', 'not_supported', ['MULTIPLE_HOLES'], plain)
    row = wh = restrictor = None
    declarative = text[:stop].rstrip() + '。'
    if found:
        row, wh, a, end, restrictor, _ = found[0]
        if row['hole'] == 'RESTRICTOR' and restrictor is None: return _question_refusal('ja', 'not_supported', ['WH_NOT_IN_TABLE'], _question_dict(None, None, wh, 'WH_QUESTION', None, mark, None))
        if end > stop: return _question_refusal('ja', 'not_supported', ['WH_NOT_IN_TABLE'], plain)
        declarative = text[:a] + mark + text[end:stop].rstrip() + '。'
        plain = _question_dict(None, None, wh, 'WH_QUESTION', restrictor, mark, declarative)
        if row['unread'] is not None: return _question_refusal('ja', 'not_supported', [row['unread']], plain)
    else:
        plain = _question_dict(None, None, None, 'POLAR_QUESTION', None, mark, declarative)
    again = R.document_view({'d': declarative})
    if any(u.reason == 'interrogative source does not assert a fact' for u in again.unread):
        return _question_refusal('ja', 'not_supported', ['INTERROGATIVE_NOT_FINAL'], plain)
    if R._WH.search(declarative): return _question_refusal('ja', 'not_supported', ['WH_NOT_IN_TABLE'], dict(plain, kind='WH_QUESTION'))
    return _finish_question('ja', _read_ja(declarative, query), row, wh, restrictor, mark, declarative)


def _question_en(text, query):
    from . import en_frames as en
    stripped = text.strip()
    if not stripped.endswith('?'): return _refusal('en', 'not_supported', ['NOT_A_QUESTION'])
    mark = HOLE_MARK_EN
    plain = _question_dict(None, None, None, None, None, mark, None)
    if re.search(r'(?<![A-Za-z0-9\'\-])X(?![A-Za-z0-9\'\-])', text): return _question_refusal('en', 'not_supported', ['HOLE_MARK_IN_INPUT'], plain)
    body = stripped[:-1]
    if re.search(r'[.!?;:]', body): return _question_refusal('en', 'not_supported', ['QUESTION_MULTI_SENTENCE'], plain)
    words = _en_words(body)
    if re.sub(r"[A-Za-z][A-Za-z'\-]*|[0-9]+|\s+", '', body): return _question_refusal('en', 'not_supported', ['EN_FORM_NOT_REWRITTEN'], plain)
    low = [w.lower() for w in words]
    if not words: return _refusal('en', 'unreadable_input', ['NO_LANGUAGE'])
    aux = set(en.AUX); neg = set(en.NEG)
    holes = [i for i, w in enumerate(low) if w in _EN_WH_WORDS]
    if len(holes) >= 2: return _question_refusal('en', 'not_supported', ['MULTIPLE_HOLES'], _question_dict(None, None, None, 'WH_QUESTION', None, mark, None))
    row = wh = restrictor = None
    if holes:
        if holes[0] != 0: return _question_refusal('en', 'not_supported', ['EN_FORM_NOT_REWRITTEN'], plain)
        wh = low[0]
        row = next(r for r in WH_TABLE if wh in r['en'])
        k = 1
        if row['noun']:
            if len(words) < 3: return _question_refusal('en', 'not_supported', ['WH_NOT_IN_TABLE'], _question_dict(None, None, wh, 'WH_QUESTION', None, mark, None))
            restrictor = words[1]; k = 2
        plain = _question_dict(None, None, wh, 'WH_QUESTION', restrictor, mark, None)
        if row['hole'] == 'MANNER' and not (len(low) > 1 and low[1] in aux): return _question_refusal('en', 'not_supported', ['WH_NOT_IN_TABLE'], plain)
        if row['unread_en'] is not None: return _question_refusal('en', 'not_supported', [row['unread_en']], plain)
        if k >= len(words): return _question_refusal('en', 'not_supported', ['EN_FORM_NOT_REWRITTEN'], plain)
        if low[k] not in aux:    # E1: the wh word (and its noun) is the subject
            declarative = ' '.join([mark] + words[k:]) + '.'
            return _finish_question('en', _read_en(declarative, query), row, wh, restrictor, mark, declarative)
        start, hole_at = k, True
    else:
        if low[0] not in ('did', 'does', 'do'): return _question_refusal('en', 'not_supported', ['EN_FORM_NOT_REWRITTEN'], plain)
        start, hole_at = 0, False
        plain = _question_dict(None, None, None, 'POLAR_QUESTION', None, mark, None)
    # E2 (wh) and E3 (polar): <aux> <subject ...> <verb> <rest>  ->  <subject ...> <aux> <verb> <rest>  (the do of emphasis)
    if low[start] not in ('did', 'does', 'do'): return _question_refusal('en', 'not_supported', ['EN_FORM_NOT_REWRITTEN'], plain)
    known = _en_known_verbs()
    j = next((i for i in range(start + 1, len(words)) if en.lemma(low[i]) in known), None)
    if j is None or j == start + 1 or any(w in neg or w in aux for w in low[start + 1:j]):
        return _question_refusal('en', 'not_supported', ['EN_FORM_NOT_REWRITTEN'], plain)
    subject, verb, rest = words[start + 1:j], words[j], words[j + 1:]
    if hole_at:
        # a stranded final `to` (the preposition left behind by the wh word) is checked FIRST: the mark goes after it, so that the declarative form
        # never keeps a stranded `to` after the mark (the reader drops a final `to` silently and would read the mark as the object)
        if not rest: rest = [mark]
        elif low[-1] == 'to': rest = rest + [mark]
        elif low[j + 1] == 'to': rest = [mark] + rest
        else: return _question_refusal('en', 'not_supported', ['HOLE_POSITION_UNDETERMINED'], plain)
    sentence = ' '.join(subject + [low[start], verb] + rest)    # the auxiliary as it is in a sentence (not capitalised)
    declarative = sentence[:1].upper() + sentence[1:] + '.'
    plain = dict(plain, declarative=declarative)
    return _finish_question('en', _read_en(declarative, query), row, wh, restrictor, mark, declarative)


def read_question(text, lang=None, *, placement=_UNSET):
    """The reading of a QUESTION as a plain dict: the shape of `read()` plus the LAST key `question` ({hole_role, hole_type, wh, kind, restrictor,
    hole_mark, declarative}). The wh word is replaced by the hole mark (a symbol, never a word) and the declarative form is read by the same reader as
    any sentence; the hole is the one role whose value is the mark. A text that is not a question returns the refusal `NOT_A_QUESTION` WITHOUT the key
    `question`. Raises ReadError for an input that is refused (as `read()` does). Only the question path is here: `read()` is unchanged."""
    chosen = check_input(text, lang)
    if chosen is None: return _refusal(None, 'not_supported', ['NO_LANGUAGE'])
    query = _placement_query(placement)
    return _question_ja(text, query) if chosen == 'ja' else _question_en(text, query)


class _Parser(argparse.ArgumentParser):
    def error(self, message):
        raise ReadError('BAD_ARGUMENTS', message)


def main(argv=None):
    parser = _Parser(prog='python -m verantyx.semantic_read', add_help=False)
    parser.add_argument('--text'); parser.add_argument('--lang')
    argv = list(sys.argv[1:] if argv is None else argv)
    # `--events` is NOT registered with the parser: argparse would then take its abbreviations (--e, --ev, ...) too and change
    # the answer of argv that never contained `--events`. Only the exact argument, before any `--`, is taken out; the parser
    # that sees the rest is the one it always was.
    cut = argv.index('--') if '--' in argv else len(argv)
    events = '--events' in argv[:cut]
    argv = [a for i, a in enumerate(argv) if not (i < cut and a == '--events')]
    # `--placement <dir>` / `--placement=<dir>` is taken out the same way (exact argument, before any `--`, not registered with the parser).
    cut = argv.index('--') if '--' in argv else len(argv)
    placement, kept, i = None, [], 0
    try:
        while i < len(argv):
            a = argv[i]
            if i < cut and (a == '--placement' or a.startswith('--placement=')):
                if placement is not None: raise ReadError('BAD_ARGUMENTS', '--placement given twice')
                if a == '--placement':
                    if i + 1 >= cut: raise ReadError('BAD_ARGUMENTS', '--placement needs a directory')
                    placement = argv[i + 1]; i += 2
                else:
                    placement = a[len('--placement='):]; i += 1
                if not placement.strip(): raise ReadError('BAD_ARGUMENTS', '--placement needs a directory')
                continue
            kept.append(a); i += 1
        argv = kept
        args = parser.parse_args(argv)
        out = read(args.text, args.lang, placement=_UNSET if placement is None else placement)
        if events:
            from . import event_cross    # only for --events: the default output does not load the module
            out = event_cross.attach_events(out) if placement is None else event_cross.attach_events(out, event_cross.default_lookup(placement))
        code = 0
    except ReadError as err:
        out = {'error': {'type': err.type, 'detail': err.detail}}; code = 2
    sys.stdout.write(json.dumps(out, ensure_ascii=False) + '\n')
    return code


if __name__ == '__main__':
    sys.exit(main())
