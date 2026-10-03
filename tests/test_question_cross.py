"""W3-c2: `semantic_read.read_question` — a question read as a cross whose one arm is a typed hole (docs/EVENT_CROSS.md 穴の型; docs/OBSERVATION.md 質問の観測).

The sentences here are NOT the sentences of the frozen test data (tests/observe/question/). The existing entry `read()` must stay what it was.
"""
import ast
import hashlib
import json
import os
import re
import subprocess
import sys
import unicodedata
from pathlib import Path

import pytest

from verantyx import semantic_read as SR

TREE = Path(__file__).resolve().parent.parent
KEYS = ['schema', 'lang', 'readable', 'clauses', 'relations', 'abstain', 'unsupported', 'clause_meta', 'question']
QKEYS = ['hole_role', 'hole_type', 'wh', 'kind', 'restrictor', 'hole_mark', 'declarative']


def rq(text, lang=None):
    return SR.read_question(text, lang, placement=None)


def reasons(out):
    return (out['abstain'] or {}).get('reasons')


# ---------------------------------------------------------------------------------------------------------------------------------
# Japanese
# ---------------------------------------------------------------------------------------------------------------------------------
def test_person_hole_is_an_agent_with_the_shape_and_key_order():
    out = rq('誰が妹に絵葉書を送った？')
    assert list(out) == KEYS and list(out['question']) == QKEYS
    assert out['readable'] is True and out['schema'] == 'verantyx.semantic_read/1' and out['abstain'] is None
    assert out['clauses'][0]['roles'] == {'agent': 'Ｘ', 'patient': '絵葉書', 'recipient': '妹'}
    assert out['question'] == {'hole_role': 'agent', 'hole_type': ['GROUP_ORG', 'PERSON'], 'wh': '誰', 'kind': 'WH_QUESTION', 'restrictor': None,
                               'hole_mark': 'Ｘ', 'declarative': 'Ｘが妹に絵葉書を送った。'}


def test_thing_hole_is_a_patient_and_expects_the_fifteen_types():
    from verantyx.event_cross import NOUN_TYPE_IDS
    out = rq('母は妹に何を送った？')
    assert out['clauses'][0]['roles'] == {'agent': '母', 'patient': 'Ｘ', 'recipient': '妹'}
    q = out['question']
    assert q['hole_role'] == 'patient' and q['wh'] == '何'
    assert q['hole_type'] == sorted(set(NOUN_TYPE_IDS) - {'PERSON', 'GROUP_ORG'}) and len(q['hole_type']) == 15


def test_place_hole_from_is_a_source():
    out = rq('どこから猫が走った？')
    assert out['clauses'][0]['roles'] == {'agent': '猫', 'source': 'Ｘ'}
    assert out['question']['hole_role'] == 'source' and out['question']['hole_type'] == ['PLACE'] and out['question']['wh'] == 'どこ'


def test_restrictor_keeps_its_noun_and_has_no_type_yet():
    out = rq('どの人が妹に絵葉書を送った？')
    q = out['question']
    assert out['clauses'][0]['roles']['agent'] == 'Ｘ'
    assert q['wh'] == 'どの' and q['restrictor'] == '人' and q['hole_role'] == 'agent' and q['hole_type'] is None
    assert q['declarative'] == 'Ｘが妹に絵葉書を送った。'    # the noun is inside the mark: the declarative holds no word of the question


def test_final_forms_polite_particle_and_halfwidth_mark_read_the_same_clause():
    base = rq('誰が妹に絵葉書を送った？')
    for text in ('誰が妹に絵葉書を送りましたか。', '誰が妹に絵葉書を送ったか？', '誰が妹に絵葉書を送った?'):
        out = rq(text)
        assert out['readable'] is True and out['clauses'] == base['clauses'], text
        assert out['question']['hole_role'] == 'agent'


def test_polar_question_makes_a_cross_and_puts_the_hole_on_polarity():
    for text in ('母は妹に絵葉書を送ったか？', '母が妹に絵葉書を送ったの？', '母は妹に絵葉書を送ったかな？'):
        out = rq(text)
        assert out['readable'] is True and out['clauses'][0]['roles'] == {'agent': '母', 'patient': '絵葉書', 'recipient': '妹'}, text
        assert out['question'] == {'hole_role': 'polarity', 'hole_type': None, 'wh': None, 'kind': 'POLAR_QUESTION', 'restrictor': None,
                                   'hole_mark': 'Ｘ', 'declarative': out['question']['declarative']}
        assert 'Ｘ' not in json.dumps(out['clauses'], ensure_ascii=False)


@pytest.mark.parametrize('text,reason,wh', [
    ('母は誰に絵葉書を送った？', 'RECIPIENT_TYPE_UNDETERMINED:Ｘ', '誰'),     # the reader's own reason: a mark gives no type evidence to the recipient
    ('猫がどこで走った？', 'NO_SUPPORTED_CLAUSE', 'どこ'),
    ('猫はどこへ行った？', 'NO_SUPPORTED_CLAUSE', 'どこ'),
    ('母はいつ絵葉書を送った？', 'HOLE_NOT_ISOLATED', 'いつ'),                     # the mark joined the next noun: not an isolated arm
])
def test_positions_that_need_a_type_evidence_are_refused_with_the_readers_reason(text, reason, wh):
    out = rq(text)
    assert out['readable'] is False and out['clauses'] == [] and out['abstain']['kind'] == 'not_supported'
    assert reasons(out) == [reason]
    assert out['question']['wh'] == wh and out['question']['hole_role'] is None and out['question']['kind'] == 'WH_QUESTION'


@pytest.mark.parametrize('text,reason', [
    ('Ｘが来た？', 'HOLE_MARK_IN_INPUT'),
    ('誰が誰に絵葉書を送った？', 'MULTIPLE_HOLES'),
    ('誰か妹に絵葉書を送った？', 'WH_INDEFINITE'),
    ('何も送らなかった？', 'WH_INDEFINITE'),
    ('何人が妹に絵葉書を送った？', 'WH_NOT_IN_TABLE'),
    ('母が来た。誰が来た？', 'QUESTION_MULTI_SENTENCE'),
    ('どんな絵葉書を母は妹に送った？', 'HOLE_NOT_AN_ARM:property'),
    ('なぜ母は妹に絵葉書を送った？', 'HOLE_RELATION_NOT_PRODUCED:cause'),
    ('どうして母は妹に絵葉書を送ったの？', 'HOLE_RELATION_NOT_PRODUCED:cause'),
    ('どうやって母は絵葉書を送った？', 'HOLE_RELATION_NOT_PRODUCED:manner'),
    ('何が妹に絵葉書を送った？', 'HOLE_ROLE_NOT_ALLOWED:何:agent'),
    ('誰から猫が走った？', 'HOLE_ROLE_NOT_ALLOWED:誰:source'),
    ('どこが妹に絵葉書を送った？', 'HOLE_ROLE_NOT_ALLOWED:どこ:agent'),
])
def test_typed_refusals_of_the_question_reader(text, reason):
    out = rq(text)
    assert out['readable'] is False and out['clauses'] == []
    assert reasons(out) == [reason]
    assert 'question' in out and list(out['question']) == QKEYS


@pytest.mark.parametrize('text', ['誰が来たかを母は知らなかった？', '母は誰が来たか知らなかった？', '誰が来たか母は知らないか？'])
def test_a_ka_left_in_the_middle_is_interrogative_not_final(text):
    # the reader takes ANY particle か as an interrogative; only the end is taken off, so what remains is refused, not rewritten (not every か is deleted)
    out = rq(text)
    assert out['readable'] is False and reasons(out) == ['INTERROGATIVE_NOT_FINAL']
    assert out['question']['declarative'].count('か') >= 1


def test_a_statement_is_not_a_question_and_has_no_question_key():
    out = rq('母は妹に絵葉書を送った。')
    assert out['readable'] is False and reasons(out) == ['NOT_A_QUESTION'] and 'question' not in out
    assert list(out) == KEYS[:-1]


def test_read_still_refuses_a_question_as_before():
    for text in ('誰が妹に絵葉書を送った？', '母は妹に絵葉書を送ったか？'):
        out = SR.read(text, None, placement=None)
        assert out['readable'] is False and 'question' not in out
        assert reasons(out) == ['UNREAD_SPAN:interrogative source does not assert a fact']


def test_input_errors_are_the_readers():
    for bad, kind in (('', 'EMPTY_TEXT'), (None, 'MISSING_TEXT')):
        with pytest.raises(SR.ReadError) as err:
            SR.read_question(bad, None, placement=None)
        assert err.value.type == kind


def test_hole_is_isolated_by_the_one_role_that_equals_the_mark():
    mark = 'Ｘ'
    clause = {'predicate': '送る', 'roles': {'agent': mark, 'patient': '絵葉書'}, 'polarity': '+', 'tense': 'past', 'modality': None, 'voice': 'active'}
    assert SR._isolate_hole(clause, mark) == ('agent', None)
    assert SR._isolate_hole(dict(clause, roles={'agent': '母', 'patient': '絵葉書'}), mark) == (None, 'HOLE_DROPPED')    # the mark vanished (P7)
    assert SR._isolate_hole(dict(clause, roles={'agent': 'Ｘ生徒', 'patient': '絵葉書'}), mark) == (None, 'HOLE_NOT_ISOLATED')
    assert SR._isolate_hole(dict(clause, roles={'agent': mark, 'patient': mark}), mark) == (None, 'HOLE_NOT_ISOLATED')
    assert SR._isolate_hole(dict(clause, roles={'agent': [mark, '母'], 'patient': '絵葉書'}), mark) == (None, 'HOLE_NOT_ISOLATED')
    assert SR._isolate_hole(dict(clause, predicate='Ｘ送る'), mark) == (None, 'HOLE_NOT_ISOLATED')


def test_finish_question_names_the_dropped_mark_when_the_reading_has_none():
    reading = {'schema': SR.SCHEMA, 'lang': 'ja', 'readable': True, 'abstain': None, 'unsupported': [], 'relations': [], 'clause_meta': [{'rule': 'frame', 'span': [0, 3]}],
               'clauses': [{'predicate': '送る', 'roles': {'patient': '絵葉書', 'recipient': '妹'}, 'polarity': '+', 'tense': 'past', 'modality': None, 'voice': 'active'}]}
    row = SR._hole_row('PERSON')
    out = SR._finish_question('ja', reading, row, '誰', None, 'Ｘ', '妹に絵葉書を送った。')
    assert out['readable'] is False and reasons(out) == ['HOLE_DROPPED'] and out['question']['hole_role'] is None


# ---------------------------------------------------------------------------------------------------------------------------------
# English
# ---------------------------------------------------------------------------------------------------------------------------------
def test_en_who_subject():
    out = rq('Who sent a postcard to the nurse?')
    assert out['clauses'][0]['roles'] == {'agent': 'X', 'patient': 'postcard', 'recipient': 'nurse'}
    assert out['question'] == {'hole_role': 'agent', 'hole_type': ['GROUP_ORG', 'PERSON'], 'wh': 'who', 'kind': 'WH_QUESTION', 'restrictor': None,
                               'hole_mark': 'X', 'declarative': 'X sent a postcard to the nurse.'}


def test_en_what_object_before_to_and_at_the_end():
    out = rq('What did the pilot send to the nurse?')
    assert out['clauses'][0]['roles'] == {'agent': 'pilot', 'patient': 'X', 'recipient': 'nurse'}
    assert out['question']['declarative'] == 'The pilot did send X to the nurse.' and out['question']['hole_role'] == 'patient'
    out = rq('What does the pilot read?')
    assert out['clauses'][0]['tense'] == 'nonpast' and out['clauses'][0]['roles'] == {'agent': 'pilot', 'patient': 'X'}


def test_en_stranded_to_puts_the_mark_on_the_recipient_which_is_refused():
    out = rq('Who did the pilot send the postcard to?')
    assert out['question']['declarative'] == 'The pilot did send the postcard to X.'
    assert out['readable'] is False and reasons(out) == ['RECIPIENT_TYPE_UNDETERMINED:X']


def test_en_a_stranded_final_to_alone_puts_the_mark_after_the_to_and_is_never_the_object():
    # review r1 M1: with only `to` left after the verb the old order made `The girl did write X to.`, which the reader reads as an object X
    for text, declarative in [('Who did the girl write to?', 'The girl did write to X.'), ('Who did the boy run to?', 'The boy did run to X.'),
                              ('Who did the farmer sell to?', 'The farmer did sell to X.')]:
        out = rq(text)
        assert out['question']['declarative'] == declarative, text
        assert out['question']['hole_role'] != 'patient' and out['question']['hole_role'] is None, text
        assert out['readable'] is False and out['question']['wh'] == 'who', text
        assert not out['clauses'], text


def test_en_no_declarative_form_keeps_a_stranded_to_after_the_mark():
    for text in ['Who did the girl write to?', 'What did the girl give the dog to?', 'Who did the girl give to the boy to?', 'Who did the pilot send the postcard to?',
                 'Who did the girl write?', 'Who did the girl give to the boy?']:
        d = rq(text)['question']['declarative']
        assert d is None or not re.search(r'\bX\b.*\bto\.$', d), (text, d)


def test_en_which_noun():
    out = rq('Which person sent a postcard to the nurse?')
    q = out['question']
    assert q['wh'] == 'which' and q['restrictor'] == 'person' and q['hole_type'] is None and q['hole_role'] == 'agent'
    assert q['declarative'] == 'X sent a postcard to the nurse.'


def test_en_polar_questions_make_a_cross_with_the_hole_on_polarity():
    out = rq('Did the pilot send a postcard to the nurse?')
    assert out['readable'] is True and out['clauses'][0]['polarity'] == '+' and out['clauses'][0]['tense'] == 'past'
    assert out['question']['kind'] == 'POLAR_QUESTION' and out['question']['hole_role'] == 'polarity'
    assert out['question']['declarative'] == 'The pilot did send a postcard to the nurse.'
    out = rq('Does the pilot send a postcard to the nurse?')
    assert out['clauses'][0]['tense'] == 'nonpast'


@pytest.mark.parametrize('text,reason', [
    ('Is the pilot a nurse?', 'EN_FORM_NOT_REWRITTEN'),
    ('Can the pilot send a postcard?', 'EN_FORM_NOT_REWRITTEN'),
    ('Where did the pilot send a postcard?', 'HOLE_ROLE_NOT_PRODUCED:en:place'),
    ('When did the pilot send a postcard?', 'HOLE_ROLE_NOT_PRODUCED:en:time'),
    ('Why did the pilot send a postcard?', 'HOLE_RELATION_NOT_PRODUCED:cause'),
    ('How did the pilot send a postcard?', 'HOLE_RELATION_NOT_PRODUCED:manner'),
    ('How many postcards did the pilot send?', 'WH_NOT_IN_TABLE'),
    ('X sent a postcard to the nurse?', 'HOLE_MARK_IN_INPUT'),
    ('Who sent what to the nurse?', 'MULTIPLE_HOLES'),
    ('What did the pilot send the nurse?', 'HOLE_POSITION_UNDETERMINED'),
    ('What did the pilot not send to the nurse?', 'EN_FORM_NOT_REWRITTEN'),
    ('The pilot sent a postcard to the nurse?', 'EN_FORM_NOT_REWRITTEN'),
])
def test_en_typed_refusals(text, reason):
    out = rq(text)
    assert out['readable'] is False and reasons(out) == [reason], out
    assert 'question' in out


def test_en_statement_is_not_a_question():
    out = rq('The pilot sent a postcard to the nurse.')
    assert reasons(out) == ['NOT_A_QUESTION'] and 'question' not in out


def test_en_x_inside_a_word_is_not_the_mark():
    out = rq('Who sent the Xerox to the nurse?')
    assert 'HOLE_MARK_IN_INPUT' not in (reasons(out) or [])


# ---------------------------------------------------------------------------------------------------------------------------------
# what did not change
# ---------------------------------------------------------------------------------------------------------------------------------
BASE_FUNCTIONS = {    # sha256 of the source text of each function in the base commit 2478fc7 (artifacts/w3-c2/fnsha_base.txt)
    'read': '10761b45a0e08eacc4675a3dd99dac6520837d86b073ea2ecbe8b2d265108ea6',
    'main': 'a2208d1ed1e6882b96e701cd4ef8836f54876e715bebd4adbe34d25a3dcc367e',
    '_read_ja': 'caac7ccd5cb1cda7bb166f60e7788e8ea1ee8f500150011c2f098895d96d7a98',
    '_read_en': '015499340163651d39d5ef4b9c930d6edf3b260553fcd62346947c9f9480ff3d',
    '_map_ja': '32dab5a8a322e0251f7c3a16c6b32e4902426e27442baf82e344e41c0986719e',
    '_clause_ja': 'afb088537440431321ffcdb24c58a6e33e621178eb589d402ab25e7e4b797e26',
    '_voice_ja': '57d3a7737611dbde0ed5612b98006a1dd9d25eb583275077aca5d0396cad4b5e',
    'check_input': '4984949f63c4642d5ab6cb92101a08b26f7e41a8cd0ffd34e39635208c230330',
    '_refusal': '38eb3788267daf33badd1a2ae111ed1b556c353feb875d434b0b16999ce7d32e',
    '_answer': '5b3b9b5e074df602db8afc926a42e2bb0326776184bb603f94dc9639030ce5ed',
    '_placement_query': 'df3693b40146942ed53f442af2ea1343d4b64ae8b5b8de188558a728ca10d9e8',
    '_typed_reread_ja': 'fd2b60731abaf1b911bb2e33c55069b314c1507296fcaeede9550b5f857e829f',
    '_clause_en': '73694bde0e09aeef83b89ccb1500e2a7cc455f3f05c3fa145a4d6c1c668ac51d',
}
BASE_CONSTANTS = {
    'ERROR_TYPES': '3a15969d59371cb4174e06017974bb980afbcdf04dce5c741e485ab3f980e03a',
    'MAX_TEXT_CHARS': '216fa0f98e0a8f2576ed073e3666e272596cead6076e20efb31a9ff59c753701',
    'NOT_PRODUCED': '54501d8c7fb3129af8c9056080397e57de162e2c83d65c311ee6d0302d7bac36',
    'SCHEMA': '9ca90c5dcf0b07ab0e188212c21416921611ff31efbfd3f2913114ae8af36b0d',
    '_MODAL_MARKS': '2ec8119e285c8955e9e73955220041ccd1667e24e40e7e5125354eac5f359d6d',
    '_QUANT_SURFACES': '6748fb9630d145ba0e54571e91f5628b6eb93e2e87c70235013cd49918aa5b4d',
    '_ROLE_TABLE': '6250dffd87fcf45de8f6a302507c14629bb9f8edf782ae972a6927782616d167',
}


def test_existing_functions_and_constants_are_byte_identical_to_the_base():
    src = Path(SR.__file__).read_text(encoding='utf-8')
    lines = src.splitlines()
    tree = ast.parse(src)
    got_f, got_c = {}, {}
    for n in tree.body:
        if isinstance(n, ast.FunctionDef) and n.name in BASE_FUNCTIONS:
            got_f[n.name] = hashlib.sha256('\n'.join(lines[n.lineno - 1:n.end_lineno]).encode('utf-8')).hexdigest()
        if isinstance(n, ast.Assign) and len(n.targets) == 1 and isinstance(n.targets[0], ast.Name) and n.targets[0].id in BASE_CONSTANTS:
            got_c[n.targets[0].id] = hashlib.sha256('\n'.join(lines[n.lineno - 1:n.end_lineno]).encode('utf-8')).hexdigest()
    assert got_f == BASE_FUNCTIONS
    assert got_c == BASE_CONSTANTS


def _clean_env():
    return {'HOME': os.environ.get('HOME', ''), 'PATH': '/usr/bin:/bin', 'PYTHONDONTWRITEBYTECODE': '1', 'PYTHONPATH': str(TREE)}


def test_importing_the_reading_entry_loads_no_cross_or_placement_module():
    code = ('import sys, verantyx.semantic_read; '
            'print(json_dumps := __import__("json").dumps([m for m in ("verantyx.event_cross", "verantyx.coarse_place", "verantyx.observe") if m in sys.modules]))')
    done = subprocess.run([sys.executable, '-c', code], capture_output=True, text=True, env=_clean_env(), cwd=str(TREE), timeout=120)
    assert done.returncode == 0, done.stderr
    assert json.loads(done.stdout.strip().splitlines()[-1]) == []


def test_read_question_without_placement_does_not_read_the_placement_variable(monkeypatch):
    monkeypatch.setenv('VERA_PLACEMENT', '/nonexistent/placement')
    out = SR.read_question('誰が妹に絵葉書を送った？', None, placement=None)
    assert out['readable'] is True


# ---------------------------------------------------------------------------------------------------------------------------------
# the registered table (docs/EVENT_CROSS.md) and WH_TABLE are the same table
# ---------------------------------------------------------------------------------------------------------------------------------
def _docs_table():
    text = (TREE / 'docs' / 'EVENT_CROSS.md').read_text(encoding='utf-8')
    m = re.search(r'<!-- BEGIN table:w3c2_holes -->\n(.*?)\n<!-- END table:w3c2_holes -->', text, re.S)
    assert m, 'table:w3c2_holes not found in docs/EVENT_CROSS.md'
    rows = [[c.strip() for c in line.strip().strip('|').split('|')] for line in m.group(1).splitlines()]
    assert rows[0] == ['穴の型', '和文の wh', '英文の wh', '許す腕', '期待する型'] and set(rows[1]) == {'---'}
    return rows[2:]


def test_wh_table_is_the_registered_table_of_the_docs():
    from verantyx.event_cross import NOUN_TYPE_IDS, ROLE_NAMES
    rows = _docs_table()
    assert [r[0] for r in rows] == [r['hole'] for r in SR.WH_TABLE]
    for cells, row in zip(rows, SR.WH_TABLE):
        hole, ja, en, arms, types = cells
        assert hole == row['hole']
        want_ja = '・'.join(row['ja']) + ('＋N' if row['noun'] else '') if row['ja'] else '—'
        if row['hole'] == 'RESTRICTOR': want_ja = 'どの＋N'
        if row['hole'] == 'PROPERTY': want_ja = 'どんな＋N'
        assert ja == want_ja, hole
        want_en = ('which＋N' if row['hole'] == 'RESTRICTOR' else '・'.join(row['en'])) if row['en'] else '—'
        assert en == want_en, hole
        if row['arms'] is None: assert arms.startswith('ROLE_NAMES の全部'), hole
        elif not row['arms']: assert arms == '—', hole
        else: assert arms.split('・') == list(row['arms']), hole
        if row['types'] is not None: assert sorted(types.split('・')) == sorted(row['types']), hole
        elif row['types_except'] is not None: assert types == 'NOUN_TYPE_IDS から %s を除いた型' % '・'.join(('PERSON', 'GROUP_ORG')), hole
        elif row['hole'] == 'RESTRICTOR': assert types == 'N の配置の型'
        else: assert types == '—', hole
    # every arm the table names is a role of the convention, and every type it names is a type id (the table invents nothing)
    for row in SR.WH_TABLE:
        assert set(row['arms'] or ()) <= set(ROLE_NAMES) and set(row['types'] or ()) <= set(NOUN_TYPE_IDS) and set(row['types_except'] or ()) <= set(NOUN_TYPE_IDS)
    assert SR.HOLE_TYPES_VERSION == 1 and 'HOLE_TYPES_VERSION = 1' in (TREE / 'docs' / 'EVENT_CROSS.md').read_text(encoding='utf-8')


def test_the_marks_are_one_symbol_each_and_the_table_has_no_word_to_fill_the_hole_with():
    assert SR.HOLE_MARK_JA == 'Ｘ' and unicodedata.name(SR.HOLE_MARK_JA) == 'FULLWIDTH LATIN CAPITAL LETTER X'
    assert SR.HOLE_MARK_EN == 'X'
    for row in SR.WH_TABLE:    # only wh words and roles / type ids: nothing that could stand in the hole as a noun
        assert all(isinstance(w, str) for w in row['ja'] + row['en'])
