"""W1-a2 X4: the reading entry `python -m verantyx.semantic_read` (verantyx/semantic_read.py).

* the output is the JSON shape of docs/READING_CONVENTIONS.md §1 (checked by a validator written here, not by the entry);
* over the self-made B1 v2 sample (tests/bank_score/fixtures/B1_v2/items.jsonl: Japanese 40, English 12, unreadable 13) every output is valid,
  an unreadable gold is `readable: false`, and `tools.bank_score.v2.b1.judge` calls no item a misreading;
* a broken input is a typed refusal (7 types), exit code 2; a child process in an empty cwd loads only modules of this tree.
"""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from tools.bank_score.v2 import b1
from verantyx import semantic_read as SR

TREE = Path(__file__).resolve().parent.parent
FIXTURE = TREE / 'tests' / 'bank_score' / 'fixtures' / 'B1_v2' / 'items.jsonl'
ITEMS = [json.loads(l) for l in FIXTURE.read_text(encoding='utf-8').splitlines() if l.strip()]
CLAUSE_KEYS = {'predicate', 'roles', 'polarity', 'tense', 'modality', 'voice'}
OPTIONAL_KEYS = {'quantifiers', 'scope', 'comparison'}
ABSTAIN_KINDS = {'unreadable_input', 'not_supported'}


def validate(out):
    """The convention's shape (§1, §1.1, §1.2), checked field by field. Returns a list of problems (empty when valid)."""
    bad = []
    top = {'schema', 'lang', 'readable', 'clauses', 'relations', 'abstain', 'unsupported', 'clause_meta'}
    if set(out) != top: bad.append(('keys', sorted(set(out) ^ top)))
    if out.get('schema') != SR.SCHEMA: bad.append('schema')
    if not isinstance(out.get('readable'), bool): bad.append('readable type')
    clauses, relations = out.get('clauses'), out.get('relations')
    if not isinstance(clauses, list) or not isinstance(relations, list): return bad + ['clauses/relations type']
    if out.get('readable') is False:
        if clauses or relations: bad.append('readable false with clauses or relations')
        ab = out.get('abstain')
        if not (isinstance(ab, dict) and ab.get('kind') in ABSTAIN_KINDS and isinstance(ab.get('reasons'), list) and ab['reasons']
                and all(isinstance(r, str) and r for r in ab['reasons'])): bad.append('abstain not typed')
        if out.get('clause_meta'): bad.append('meta on a refusal')
        return bad
    if out.get('abstain') is not None: bad.append('abstain on a reading')
    if len(out.get('clause_meta', [])) != len(clauses): bad.append('clause_meta length')
    for i, c in enumerate(clauses):
        keys = set(c)
        if not CLAUSE_KEYS <= keys or not keys <= CLAUSE_KEYS | OPTIONAL_KEYS: bad.append((i, 'clause keys', sorted(keys)))
        if not isinstance(c.get('predicate'), str) or not c['predicate']: bad.append((i, 'predicate'))
        roles = c.get('roles')
        if not isinstance(roles, dict): bad.append((i, 'roles type'))
        else:
            for name, value in roles.items():
                if name not in b1.ROLES: bad.append((i, 'role name', name))
                if not isinstance(value, str) or not value.strip(): bad.append((i, 'role value', name))
        if c.get('polarity') not in ('+', '-'): bad.append((i, 'polarity'))
        if c.get('tense') not in ('past', 'nonpast', None): bad.append((i, 'tense'))
        if c.get('modality') not in b1.MODALITIES: bad.append((i, 'modality'))
        if c.get('voice') not in b1.VOICES: bad.append((i, 'voice'))
        if c.get('comparison') is not None and c['comparison'] not in b1.COMPARISONS: bad.append((i, 'comparison'))
        if 'quantifiers' in c and not (isinstance(c['quantifiers'], dict) and c['quantifiers']): bad.append((i, 'quantifiers'))
    for r in relations:
        if set(r) != {'type', 'from', 'to'} or r['type'] not in b1.REL_TYPES or not all(isinstance(r[k], int) and 0 <= r[k] < len(clauses) for k in ('from', 'to')):
            bad.append(('relation', r))
    return bad


def run_main(argv):
    """main() with its standard output captured; returns (exit code, the JSON object)."""
    import io, contextlib
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        code = SR.main(argv)
    text = buf.getvalue()
    assert text.endswith('\n') and text.count('\n') == 1, text
    return code, json.loads(text)


# ---- the sample -----------------------------------------------------------------------------------------------------------------------
def test_the_sample_has_the_planned_shape():
    ja = [i for i in ITEMS if i['lang'] == 'ja' and i['expect']['readable']]
    en = [i for i in ITEMS if i['lang'] == 'en' and i['expect']['readable']]
    un = [i for i in ITEMS if not i['expect']['readable']]
    assert len(ja) >= 30 and len(en) >= 10 and len(un) >= 10, (len(ja), len(en), len(un))
    assert {'ja', 'en'} <= {i['lang'] for i in un}


@pytest.mark.parametrize('item', ITEMS, ids=[i['id'] for i in ITEMS])
def test_every_sample_input_gets_a_valid_output_and_no_misreading(item):
    out = SR.read(item['input'])
    assert validate(out) == [], out
    assert out['lang'] == item['lang']
    if not item['expect']['readable']:
        assert out['readable'] is False, out
    verdict = b1.judge(item['expect'], item['lang'], {'readable': out['readable'], 'clauses': out['clauses'], 'relations': out['relations']})
    assert verdict['verdict'] != 'misread', (verdict, out)
    assert verdict['verdict'] != 'UNJUDGED', verdict


def test_the_sample_is_mostly_read_not_only_refused():
    verdicts = [b1.judge(i['expect'], i['lang'], {k: SR.read(i['input'])[k] for k in ('readable', 'clauses', 'relations')})['verdict'] for i in ITEMS]
    assert verdicts.count('correct') >= len(ITEMS) // 2, verdicts
    assert verdicts.count('misread') == 0


# ---- refusals of broken input ---------------------------------------------------------------------------------------------------------
@pytest.mark.parametrize('argv,error', [
    ([], 'MISSING_TEXT'),
    (['--text='], 'EMPTY_TEXT'),
    (['--text=  \t '], 'EMPTY_TEXT'),
    (['--text=' + 'あ' * (SR.MAX_TEXT_CHARS + 1)], 'TEXT_TOO_LONG'),
    (['--text=犬が走った。', '--lang=fr'], 'BAD_LANG'),
    (['--text=犬が走った。', '--lang=en'], 'LANG_MISMATCH'),
    (['--text=The dog ran.', '--lang=ja'], 'LANG_MISMATCH'),
    (['--text=犬が\x00走った。'], 'CONTROL_CHARACTERS'),
    (['--text=犬が\x1b走った。'], 'CONTROL_CHARACTERS'),
    (['--text=犬が\ud800走った。'], 'CONTROL_CHARACTERS'),
    (['--bogus'], 'BAD_ARGUMENTS'),
    (['--text'], 'BAD_ARGUMENTS'),
])
def test_a_broken_input_is_a_typed_refusal(argv, error):
    code, out = run_main(argv)
    assert code == 2 and set(out) == {'error'} and out['error']['type'] == error and out['error']['detail'], out
    assert error in SR.ERROR_TYPES


def test_all_seven_error_types_are_covered():
    covered = {'MISSING_TEXT', 'EMPTY_TEXT', 'TEXT_TOO_LONG', 'BAD_LANG', 'LANG_MISMATCH', 'CONTROL_CHARACTERS', 'BAD_ARGUMENTS'}
    assert covered == set(SR.ERROR_TYPES)


def test_a_text_that_starts_with_a_dash_is_taken_with_the_equal_sign():
    code, out = run_main(['--text=-犬が走った。'])
    assert code == 0 and validate(out) == [], out


def test_newline_and_tab_are_not_control_characters():
    code, out = run_main(['--text=兄が本を読んだ。\n弟が手紙を書いた。'])
    assert code == 0 and validate(out) == [], out


def test_text_without_any_letter_is_a_typed_abstention_not_an_error():
    code, out = run_main(['--text=1234 !?'])
    assert code == 0 and out['readable'] is False and out['abstain']['reasons'] == ['NO_LANGUAGE'] and validate(out) == [], out


def test_lang_is_taken_from_the_script_when_not_given():
    assert SR.read('犬が走った。')['lang'] == 'ja' and SR.read('The dog ran.')['lang'] == 'en'
    assert SR.read('Ann はい')['lang'] == 'ja'


# ---- soundness of the fields the entry decides ---------------------------------------------------------------------------------------
def test_a_coined_predicate_is_unreadable_not_read_from_its_readable_parts():
    for text in ('先生が生徒に地図をフォルノした。', '雨が降ったので、試合をゴルマンした。'):
        out = SR.read(text)
        assert out['readable'] is False and out['abstain']['kind'] == 'unreadable_input' and out['clauses'] == [], out
    out = SR.read('Ann blorped the report to Ben.')
    assert out['readable'] is False and out['clauses'] == [], out


def test_a_subject_that_is_not_shown_to_be_a_person_is_not_called_an_agent():
    out = SR.read('桜が咲いた。')
    assert out['readable'] is False and out['abstain']['reasons'][0].startswith('SUBJECT_TYPE_UNDETERMINED'), out
    assert SR.read('犬が走った。')['clauses'][0]['roles'] == {'agent': '犬'}


def test_a_benefactive_is_not_called_a_recipient():
    out = SR.read('母が娘に着物を仕立ててやった。')
    assert out['readable'] is False and out['abstain']['reasons'] == ['BENEFACTIVE_NOT_PRODUCED'], out


@pytest.mark.parametrize('text', ['すべての生徒が宿題を終えた。', '生徒が宿題だけ終えた。', '三人の生徒が宿題を終えた。', '兄は宿題を終えなければならない。',
                                  '妹はピアノが弾ける。', '兄は明日、本を読むかもしれない。', '先生が手紙を読まれた。'])
def test_quantity_modality_and_undecided_voice_are_not_filled_in(text):
    out = SR.read(text)
    assert validate(out) == [] and out['readable'] is False, out


def test_a_sentence_whose_main_predicate_is_unread_is_not_returned_from_its_subordinate_clause():
    for text in ('雨が降ったので、試合をゴルマンした。', '兄が買った本をゴルマンした。'):
        assert SR.read(text)['readable'] is False


def test_the_end_point_is_a_goal_only_when_it_shows_a_place():
    assert SR.read('妹が学校へ行った。')['clauses'][0]['roles']['goal'] == '学校'
    out = SR.read('母が荷物を棚に置いた。')
    assert out['readable'] is False, out


def test_a_degree_comparison_is_not_read_as_a_noun_sentence():
    for text in ('この町は昔ほど賑やかではない。', 'この湖は海くらい穏やかだ。'):
        out = SR.read(text)
        assert out['readable'] is False, out


def test_a_comparative_is_read_with_its_standard_and_kind():
    out = SR.read('兄は弟より強い。')
    assert out['readable'] and out['clauses'][0]['comparison'] == 'comparative' and out['clauses'][0]['roles'] == {'entity': '兄', 'standard': '弟'}, out


def test_english_perfect_progressive_and_modal_forms_are_not_read():
    for text in ('Ann has sent the report to Ben.', 'Ann is sending the report to Ben.', 'Ann can send the report to Ben.',
                 'Ann sent the report to Ben yesterday.', 'Ann sent her report to Ben.', 'Every teacher sent a report to Ben.'):
        out = SR.read(text)
        assert validate(out) == [] and out['readable'] is False, (text, out)


def test_the_closed_table_of_what_is_not_produced_is_typed_text():
    assert SR.NOT_PRODUCED and all(isinstance(k, str) and isinstance(v, str) and v for k, v in SR.NOT_PRODUCED.items())
    assert 'comparison:equative' in SR.NOT_PRODUCED and 'role:beneficiary' in SR.NOT_PRODUCED


# ---- the real entry, as a child process in an empty directory ------------------------------------------------------------------------
def _child(args, tmp_path, code=None):
    env = {'HOME': str(tmp_path), 'PATH': '/usr/bin:/bin', 'PYTHONDONTWRITEBYTECODE': '1', 'PYTHONPATH': str(TREE)}
    cmd = [sys.executable, '-c', code] if code else [sys.executable, '-m', 'verantyx.semantic_read', *args]
    return subprocess.run(cmd, cwd=tmp_path, env=env, capture_output=True, text=True, timeout=300)


@pytest.mark.parametrize('arg,want_code,want', [
    ('--text=先生が生徒に地図を渡した。', 0, {'lang': 'ja', 'readable': True}),
    ('--text=Ann sent Ben the report.', 0, {'lang': 'en', 'readable': True}),     # round 6: a name after `to` is no evidence of a person; the double-object form is
    ('--text=ありがとう。', 0, {'readable': False}),
    ('--text=', 2, None),
])
def test_the_module_runs_as_a_command_and_prints_one_json_line(arg, want_code, want, tmp_path):
    r = _child([arg], tmp_path)
    assert r.returncode == want_code, (r.stdout, r.stderr)
    assert r.stdout.count('\n') == 1 and r.stdout.endswith('\n'), r.stdout
    out = json.loads(r.stdout)
    if want_code == 0:
        assert validate(out) == []
        assert all(out[k] == v for k, v in want.items())
    else:
        assert out['error']['type'] == 'EMPTY_TEXT'
    assert list(tmp_path.iterdir()) == [], 'the entry wrote a file'


def test_the_child_loads_only_modules_of_this_tree(tmp_path):
    code = ("import sys, json, io, contextlib\n"
            "from verantyx import semantic_read as m\n"
            "buf = io.StringIO()\n"
            "with contextlib.redirect_stdout(buf): m.main(['--text=先生が生徒に地図を渡した。'])\n"
            "mods = sorted(getattr(x, '__file__', '') or '' for k, x in sys.modules.items() if (k == 'verantyx' or k.startswith('verantyx.')))\n"
            "print(json.dumps(mods))\n")
    r = _child([], tmp_path, code)
    assert r.returncode == 0, r.stderr
    files = [f for f in json.loads(r.stdout) if f]
    root = os.path.realpath(str(TREE))
    assert files and all(os.path.realpath(f).startswith(root + os.sep) for f in files), [f for f in files if not os.path.realpath(f).startswith(root + os.sep)]


def test_the_same_input_gives_the_same_output():
    for item in ITEMS[:20] + ITEMS[-6:]:
        assert SR.read(item['input']) == SR.read(item['input'])
        assert json.dumps(SR.read(item['input']), ensure_ascii=False) == json.dumps(SR.read(item['input']), ensure_ascii=False)
