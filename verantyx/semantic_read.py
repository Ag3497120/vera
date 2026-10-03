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

Exit code: 0 for readable true and false alike; 2 for an input that is refused (a typed `{"error": {"type", "detail"}}` object on standard
output). The entry writes no file, uses no network, prints nothing but the JSON object, and gives the same output to the same input.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata

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
    'voice:passive (indirect, honorific, potential, spontaneous)': 'れる/られる is passive only on positive evidence: による/によって; a に/から phrase of a verb of the closed class _NI_KARA_FREE_PREDICATES; or no agent phrase and a subject headed by a noun that is never a person (_not_person_evidence). Not evidence: a subject missing from the person table, a verb outside a class. られる (potential), a verb of thought/feeling (spontaneous) and any other case: UNDETERMINED_VOICE',
    'voice:causative_passive': 'only from the reader\'s causer/causee roles',
    'en:time and place phrases': 'the English frame has no time/place role; a sentence that has one is returned unread (UNREPRESENTED_CONTENT)',
    'en:possessive determiners': 'her/his/their ... are dropped by the frame; the value cannot be restored, so the sentence is returned unread',
    'en:perfect, progressive, modal verbs': 'tense / modality cannot be decided from the frame',
    'en:verbs outside the known list': 'a verb is accepted only when it is in the closed list of known verbs (UNKNOWN_PREDICATE): a coined verb must not be read; the refusal is `not_supported`, never `unreadable_input` (round 5)',
    'predicate:converse verbs': 'verbs of receiving / borrowing / learning / hearing: the reader names the converse verb and swaps the roles; the convention forbids a replaced word as the predicate, so only the restoration it states (4.6, もらう) is made and the others are not read (PREDICATE_NORMALIZED)',
    'role:goal for existence / residence verbs': 'the place of existence or residence is `place` (convention 2, 4.2); with no shown place the input is not read (PLACE_TYPE_UNDETERMINED)',
    'role:agent / recipient for a capitalised name (English)': 'a capital letter says "a name", not "a person" (a city is written like a person): an intransitive subject and the recipient after `to` need a pronoun or an animate noun (SUBJECT_TYPE_UNDETERMINED / RECIPIENT_TYPE_UNDETERMINED); only the first object of a double-object clause is a recipient by its construction',
    'role:path (を of a verb of going through a space)': 'the convention has no role for the path a motion verb covers (走る・歩く・渡る の を-phrase); the reader calls it patient, which is wrong, so the input is not read (PATH_ROLE_NOT_MAPPED)',
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


def _read_ja(text):
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
        return _refusal('ja', stop.kind, [stop.reason], unsupported_report)
    return _answer('ja', clauses, relations, meta, unsupported_report)


def _map_ja(text, toks, view, R):
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
    def inside(u, sup):
        """u is a rejected alternative reading of the predicate of the supported clause sup: its predicate range lies wholly in sup's, or --
        the one other shape -- u is a copula / negative-copula reading whose predicate range is the whole predicate phrase ('弟より強い') and
        sup is the comparison read from inside it. Any other overlap is not an alternative reading of the same predicate."""
        if sup.predicate_span.start <= u.predicate_span.start and u.predicate_span.end <= sup.predicate_span.end: return True
        return (u.rule in ('copula', 'negation') and sup.rule == 'comparison'
                and u.predicate_span.start <= sup.predicate_span.start and sup.predicate_span.end <= u.predicate_span.end)
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
        out.append(_clause_ja(c, text, toks, R)); meta.append({'rule': c.rule, 'span': [c.predicate_span.start, c.predicate_span.end]})
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


def _clause_ja(c, text, toks, R):
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
        if c.predicate in _PATH_VERBS: _no('PATH_ROLE_NOT_MAPPED:' + c.predicate)
        if c.predicate == 'する': _no('PREDICATE_NOT_MAPPED:light verb')
    if voice == 'causative' and c.predicate == 'する' and any(r.name == 'patient' for r in raw_roles): _no('PREDICATE_NOT_MAPPED:light verb')
    # ---- roles ----
    roles = {}
    has_patient = 'patient' in names
    for r in raw_roles:
        name = r.name
        value = _strip_demonstrative(r, toks)
        if not value: _no('EMPTY_ROLE_VALUE:' + name)
        if value not in text: _no('VALUE_NOT_IN_INPUT:' + name)
        if name == 'agent':
            if voice == 'passive' or has_patient:
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
        #   2   no agent phrase and a transitive verb: られる -> abstain (also the potential); a verb of _SPONTANEOUS_PREDICATES -> abstain; a subject
        #       whose head is a noun that is never a person (_not_person_evidence) -> passive; otherwise abstain
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
            if _not_person_evidence(patients[0].span.text): return 'passive'
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


def _read_en(text):
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
        return _refusal('en', 'not_supported', ['UNKNOWN_PREDICATE'])
    frame, why = en.read_typed(text)
    if frame is None:
        return _refusal('en', 'not_supported', ['EN_UNREAD:' + r for r in why] or ['EN_UNREAD'])
    try:
        clause, meta = _clause_en(text, words, low, frame, known, aux, en)
    except _Abstain as stop:
        return _refusal('en', stop.kind, [stop.reason])
    return _answer('en', [clause], [], [meta], [])


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


def _clause_en(text, words, low, frame, known, aux, en):
    if frame.ambiguous or frame.inferred: _no('EN_AMBIGUOUS_OR_INFERRED')
    head = frame.predicate.split()[0]
    if head not in known and en.lemma(head) not in known and head.rstrip('e') not in {k.rstrip('e') for k in known}:
        _no('UNKNOWN_PREDICATE:' + frame.predicate)
    if any(w in _EN_QUANT for w in low): _no('QUANTIFIER_NOT_MAPPED')
    if any(w in _EN_POSSESSIVES for w in low): _no('UNREPRESENTED_CONTENT:possessive determiner')
    if re.search(r'[0-9]', text): _no('QUANTIFIER_NOT_MAPPED:numeral')
    if re.search(r'[?]|^(?:who|what|where|when|why|how|do|does|did|is|are|was|were)\b', text.strip(), re.I) and not text.strip().lower().startswith(('did not', 'does not')):
        _no('UNDETERMINED_MODALITY:question')
    # locate the verb group
    k = next((i for i, w in enumerate(low) if i > 0 and (en.lemma(w) == head or w == head)), None)
    if k is None: _no('UNDETERMINED_TENSE:verb token')
    table = _en_irregular_table()
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
    accounted.update(w for w in frame.predicate.split())
    accounted.update(low[i] for i in range(len(low)) if low[i] in aux or low[i] in en.NEG)
    leftover = [w for i, w in enumerate(low) if w not in accounted and i != k]
    if leftover: _no('UNREPRESENTED_CONTENT:' + leftover[0])
    clause = {'predicate': frame.predicate, 'roles': ordered, 'polarity': '-' if frame.negated else '+', 'tense': tense, 'modality': None, 'voice': voice}
    if bool(neg) != bool(frame.negated): _no('UNDETERMINED_POLARITY')
    return clause, {'rule': 'en_frames', 'span': [0, len(text)]}


# ---------------------------------------------------------------------------------------------------------------------------------
# entry
# ---------------------------------------------------------------------------------------------------------------------------------
def read(text, lang=None):
    """The reading of `text` as a JSON-ready dict. Raises ReadError for an input that is refused (see ERROR_TYPES)."""
    chosen = check_input(text, lang)
    if chosen is None:
        return _refusal(None, 'not_supported', ['NO_LANGUAGE'])
    return _read_ja(text) if chosen == 'ja' else _read_en(text)


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
    try:
        args = parser.parse_args(argv)
        out = read(args.text, args.lang)
        if events:
            from . import event_cross    # only for --events: the default output does not load the module
            out = event_cross.attach_events(out)
        code = 0
    except ReadError as err:
        out = {'error': {'type': err.type, 'detail': err.detail}}; code = 2
    sys.stdout.write(json.dumps(out, ensure_ascii=False) + '\n')
    return code


if __name__ == '__main__':
    sys.exit(main())
