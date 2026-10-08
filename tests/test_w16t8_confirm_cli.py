"""W16-t8 (K681, docs/COARSE_PLACEMENT.md 12.21): `vera confirm set | frame | list | undo | suggest` through `cli.main`, on the placement r9 (read only; skipped when it is missing)."""
import json
from pathlib import Path

import pytest

from verantyx import cli
from verantyx import coarse_place as CP
from verantyx import placement_layer as PL
from verantyx.testimony_ledger import TestimonyLedger

R9 = '/Users/motonisihikoudai/Projects/vera-impl/wt/W3-a6-S/build/coarse-W3a/full/r9/run2'


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    for k in (PL.ENV_LAYER, PL.ENV_ROOT, 'VERA_PLACEMENT'):
        monkeypatch.delenv(k, raising=False)
    if not Path(R9).exists():
        pytest.skip('ENV_MISSING[coarse placement r9/run2]')


class Env:
    def __init__(self, tmp_path, capsys):
        self.layer, self.ledger, self.capsys = str(tmp_path / 'L.sqlite'), str(tmp_path / 'led.jsonl'), capsys
        self.tmp = tmp_path

    def run(self, *argv, base=True):
        full = ['confirm'] + list(argv)
        if base:
            full += ['--placement', R9]
        self.capsys.readouterr()
        rc = cli.main(full)
        out = self.capsys.readouterr().out
        return rc, out

    def write(self, op, *argv, by='tester'):
        rc, out = self.run(op, *argv, '--layer', self.layer, '--ledger-file', self.ledger, *(['--by', by] if by else []))
        return rc, json.loads(out)


@pytest.fixture
def env(tmp_path, capsys):
    return Env(tmp_path, capsys)


def test_set_writes_a_chain_ledger_then_layer_and_the_query_obeys_it(env):
    rc, out = env.write('set', '整備室', 'PLACE', '--reason', 'test')
    assert rc == 0 and out['kind'] == 'human_confirmation' and out['type'] == 'PLACE' and out['confirm_id']
    led = TestimonyLedger(env.ledger)
    kinds = [e['type'] for e in led.entries()]
    assert kinds == ['header', 'human_confirmation', 'promoted_to_layer']                         # the ledger row first (K294)
    assert led.entries()[1]['confirm_id'] == out['confirm_id'] and led.entries()[2]['from_seq'] == [led.entries()[1]['seq']]
    g = PL.growth(env.layer, led, None)
    assert g['ledger']['chain_ok'] is True and g['words']['human'] == 1
    a = CP.query('整備室', placement=R9, layer=env.layer)
    assert (a['layer_status'], a['top'], a['decided_by']) == ('HUMAN_CONFIRMED_USED', ['PLACE'], ['human:' + out['confirm_id']])
    base = CP.query('整備室', placement=R9, layer=False)
    assert base['state'] == 'UNPLACED' and a['axes']['layer']['overrode_base']['state'] == 'UNPLACED'


def test_a_human_type_overrides_a_decided_word_of_r9_and_the_answer_says_human(env):
    base = CP.query('学校', placement=R9, layer=False)
    assert base['state'] == 'DECIDED' and base['top'] == ['GROUP_ORG']
    rc, out = env.write('set', '学校', 'PLACE')
    a = CP.query('学校', placement=R9, layer=env.layer)
    assert a['top'] == ['PLACE'] and a['decided_by'][0].startswith('human:') and a['axes']['layer']['overrode_base']['top'] == ['GROUP_ORG']
    assert CP.query('学校', placement=R9, layer=False) == base                                       # the base file is not touched


def test_frame_needs_a_confirmed_predicate_type_first_and_then_makes_a_role_frame(env):
    # r3 (監査役の裁定 2026-10-06 00:24): the expected values of the answer after the `frame` row changed (a `set` keeps the base's frames); see docs 12.21.7
    rc, out = env.write('frame', '移動する', 'が', 'agent', 'PERSON')
    assert (rc, out['verdict']) == (2, 'PREDICATE_TYPE_NOT_CONFIRMED') and not Path(env.layer).exists() and not Path(env.ledger).exists()
    env.write('set', '移動する', 'P_MOVE')
    rc, out = env.write('frame', '移動する', 'が', 'agent', 'PERSON', 'GROUP_ORG', '--reason', 'r')
    assert rc == 0 and out['frame'] == {'particle': 'が', 'role': 'agent', 'types': ['GROUP_ORG', 'PERSON']}
    a = CP.query('移動する', placement=R9, layer=env.layer)
    assert a['layer_status'] == 'HUMAN_CONFIRMED_USED' and a['role_frame_status'] == 'CONFIRMED'
    # r3 (監査役の裁定 2026-10-06 00:24): the 12.10 frame of the base stays (a `set` changes the type only) and the base's role frame is kept with the human's entry laid over it
    assert a['frame_status'] == 'CONFIRMED' and a['frame'] == {'へ': ['PLACE']} and a['decided_by'][-1] == 'gen_frame'
    base = CP.query('移動する', placement=R9, layer=False)
    assert a['role_frame'] == dict(base['role_frame'], が=[{'role': 'agent', 'types': ['GROUP_ORG', 'PERSON']}]) and list(a['role_frame']) == ['が', 'に', 'へ']
    assert PL.is_confirm_row(PL.open_layer(env.layer)[0].entries('移動する')[-1])


def test_list_and_undo_are_appends_and_undo_gives_the_base_answer_back(env):
    base = CP.query('整備室', placement=R9, layer=False)
    _, c1 = env.write('set', '整備室', 'PLACE')
    _, c2 = env.write('set', '実験棟', 'PLACE')
    rc, out = env.run('list', '--layer', env.layer, '--json')
    rows = json.loads(out)
    assert rc == 0 and rows['active'] == 2 and [r['word'] for r in rows['confirmations']] == ['整備室', '実験棟']
    n_before = len(PL.open_layer(env.layer)[0].all_entries())
    rc, u = env.write('undo', c1['confirm_id'], '--reason', 'oops')
    assert rc == 0 and u['kind'] == 'human_confirmation_undone' and u['undoes'] == c1['confirm_id']
    assert len(PL.open_layer(env.layer)[0].all_entries()) == n_before + 1                              # appended, nothing removed
    a = CP.query('整備室', placement=R9, layer=env.layer)
    assert {k: v for k, v in a.items() if k not in ('layer', 'layer_status')} == base and a['layer_status'] == 'LAYER_HAS_NO_ENTRY'
    rows = json.loads(env.run('list', '--layer', env.layer, '--json')[1])
    assert rows['active'] == 1
    rows_all = json.loads(env.run('list', '--layer', env.layer, '--all', '--json')[1])['confirmations']
    assert [r['state'] for r in rows_all] == ['undone', 'active', 'undo']
    g = PL.growth(env.layer, TestimonyLedger(env.ledger), None)
    assert g['ledger']['chain_ok'] is True and g['words']['human'] == 1
    assert [e['type'] for e in TestimonyLedger(env.ledger).entries()].count('human_confirmation_undone') == 1


def test_refusals_are_typed_exit_two_and_write_nothing(env):
    cases = [(('set', '整備室', 'PLACE'), None, 'CONFIRMER_REQUIRED'), (('set', '整備室', 'NOT_A_TYPE'), 'tester', 'BAD_TYPE'), (('frame', '移動する', 'の', 'agent', 'PERSON'), 'tester', 'BAD_PARTICLE'),
             (('frame', '移動する', 'が', 'nobody', 'PERSON'), 'tester', 'BAD_ROLE'), (('frame', '移動する', 'が', 'agent', 'RELATIVE_POSITION'), 'tester', 'BAD_TYPE'),
             (('undo', 'nope'), 'tester', 'NO_SUCH_CONFIRMATION')]
    for argv, by, verdict in cases:
        rc, out = env.write(*argv, by=by)
        assert (rc, out['verdict'], out['kind']) == (2, verdict, 'unknown'), argv
    assert not Path(env.layer).exists() and not Path(env.ledger).exists()


def test_undo_refusals(env):
    _, c = env.write('set', '整備室', 'PLACE')
    rc, u = env.write('undo', c['confirm_id'])
    assert rc == 0
    assert env.write('undo', c['confirm_id'])[1]['verdict'] == 'ALREADY_UNDONE'
    assert env.write('undo', u['confirm_id'])[1]['verdict'] == 'CANNOT_UNDO_UNDO'


def test_a_layer_and_a_ledger_are_needed(env):
    rc, out = env.run('set', '整備室', 'PLACE', '--by', 'x', '--ledger-file', env.ledger)
    assert (rc, json.loads(out)['verdict']) == (2, 'LAYER_REQUIRED')
    rc, out = env.run('set', '整備室', 'PLACE', '--by', 'x', '--layer', env.layer)
    assert (rc, json.loads(out)['verdict']) == (2, 'LEDGER_REQUIRED')
    rc, out = env.run('set', '整備室', 'PLACE', '--by', 'x', '--layer', env.layer, '--ledger-file', env.ledger, base=False)
    assert (rc, json.loads(out)['verdict']) == (2, 'NO_PLACEMENT')


def test_a_layer_made_on_another_base_is_refused_and_nothing_is_written(env):
    led = TestimonyLedger(Path(env.tmp) / 'other.jsonl')
    PL.write_entry(env.layer, led, base_sha256='another-base', word='x', type='PLACE', origin='layer_confirmed', decided_by=['hearst@doc:abc'], evidence={}, role_frame=None, key='k')
    n = len(led.entries())
    rc, out = env.write('set', '整備室', 'PLACE')
    assert (rc, out['verdict']) == (2, 'LAYER_BASE_MISMATCH')
    assert not Path(env.ledger).exists() and len(led.entries()) == n


def test_a_broken_ledger_is_exit_three(env):
    env.write('set', '整備室', 'PLACE')
    lines = Path(env.ledger).read_text(encoding='utf-8').splitlines()
    lines[1] = lines[1].replace('整備室', '整備所')
    Path(env.ledger).write_text('\n'.join(lines) + '\n', encoding='utf-8')
    rc, out = env.write('set', '実験棟', 'PLACE')
    assert (rc, out['verdict']) == (3, 'LEDGER_INTEGRITY')


def test_the_vera_ledger_confirm_path_is_not_a_human_confirmation_row(env, tmp_path):
    """`vera ledger confirm` + `promote` writes a layer_human row WITHOUT a confirm id: it stays under K290."""
    led = TestimonyLedger(Path(env.ledger))
    PL.write_entry(env.layer, led, base_sha256=CP._open(R9)[0].sha, word='学校', type='PLACE', origin='layer_human', decided_by=['layer_human'], evidence={'ledger_key': 'k'}, role_frame=None, key='k')
    a = CP.query('学校', placement=R9, layer=env.layer)
    assert a['layer_status'] == 'BASE_DECIDED' and a['top'] == ['GROUP_ORG']


def test_suggest_lists_a_blocked_sentence_one_line_per_candidate_and_does_not_guess_a_type(env, tmp_path):
    text = tmp_path / 't.txt'
    text.write_text('田中が整備室へ移動した。\nハルがミナに話した。\n田中が本を読んだ。\n', encoding='utf-8')
    rc, out = env.run('suggest', '--text', str(text))
    lines = out.splitlines()
    assert rc == 0 and lines[0].split('\t') == ['sentence_id', 'text', 'status', 'op', 'word', 'particle', 'role', 'candidates', 'reason', 'reachable', 'why']
    rows = [l.split('\t') for l in lines[1:] if not l.startswith('#')]
    by_text = {}
    for r in rows:
        by_text.setdefault(r[1], []).append(r)
    s1 = by_text['田中が整備室へ移動した。']
    assert [(r[2], r[3], r[4], r[7], r[9]) for r in s1] == [('ABSTAIN', 'set', '整備室', '', 'true')]               # UNPLACED: the candidates are empty, nothing is guessed
    s2 = by_text['ハルがミナに話した。']
    assert [(r[3], r[9], r[10]) for r in s2] == [('none', 'false', 'NOT_REACHABLE_BY_CONFIRMATION')]               # the reader never asks the placement about ミナ
    assert [r[2] for r in by_text['田中が本を読んだ。']] == ['READ']
    assert any(l.startswith('# sentences=3 read=1 abstained=2') for l in lines)
    rc, js = env.run('suggest', '--text', str(text), '--json')
    d = json.loads(js)
    assert d['summary']['sentences'] == 3 and d['summary']['abstained_unreachable_only'] == 1 and d['summary']['abstained_with_reachable_candidate'] == 1


def test_suggest_with_a_layer_reads_with_it_and_restores_the_environment(env, tmp_path, monkeypatch):
    # r3: the expected value of the first sentence changed (see the comment below); the second sentence keeps the old intent (suggest reads with the layer)
    text = tmp_path / 't.txt'
    text.write_text('田中が整備室へ移動した。\n', encoding='utf-8')
    env.write('set', '整備室', 'PLACE')
    env.write('set', '移動する', 'P_MOVE')
    monkeypatch.setenv(PL.ENV_LAYER, 'sentinel')
    rc, out = env.run('suggest', '--text', str(text), '--layer', env.layer)
    # r3 (監査役の裁定 2026-10-06 00:24): was READ.  The `set` of 移動する keeps the base's 12.10 frame ({へ: PLACE}), which refuses the subject が: the sentence stays abstained and suggest says why it is not reachable
    row = out.splitlines()[1].split('\t')
    assert (row[2], row[3], row[8], row[9], row[10]) == ('ABSTAIN', 'frame', 'PLACEMENT_FRAME_PARTICLE_NOT_CONFIRMED:P_MOVE:が', 'false', 'BASE_FRAME_1210_KEPT')
    import os
    assert os.environ[PL.ENV_LAYER] == 'sentinel'
    t2 = tmp_path / 't2.txt'
    t2.write_text('田中が整備室へ出向いた。\n', encoding='utf-8')
    env.write('set', '出向く', 'P_MOVE')
    rc, out = env.run('suggest', '--text', str(t2), '--layer', env.layer)
    assert out.splitlines()[1].split('\t')[2] == 'READ'
    rc, out = env.run('suggest', '--text', str(text))                                                    # without the layer (the variable is 'sentinel': a name without a root): not read
    assert 'ABSTAIN' in out


# ---- r3 (12.21.7): suggest says honestly what `vera confirm` can reach -------------------------------------------------------------------------------------------------------------------
def _suggest_rows(env, tmp_path, sentences, *extra):
    text = tmp_path / 'r3.txt'
    text.write_text(''.join(s + '\n' for s in sentences), encoding='utf-8')
    rc, out = env.run('suggest', '--text', str(text), '--json', *extra)
    assert rc == 0
    return json.loads(out)['rows']


def test_r3_a_twelve_ten_frame_reason_is_not_reachable_by_a_confirmation(env, tmp_path):
    rows = _suggest_rows(env, tmp_path, ['田中が駅へ移動した。'])
    fr = [r for r in rows if r['reason'] == 'PLACEMENT_FRAME_PARTICLE_NOT_CONFIRMED:P_MOVE:が']
    assert len(fr) == 1 and fr[0]['op'] == 'frame' and fr[0]['reachable'] is False and fr[0]['why'] == 'BASE_FRAME_1210_KEPT'


def test_r3_a_set_does_not_make_the_twelve_ten_frame_go_away(env, tmp_path):
    env.write('set', '移動する', 'P_MOVE')
    rows = _suggest_rows(env, tmp_path, ['田中が駅へ移動した。'], '--layer', env.layer)
    assert all(r['reachable'] is not True for r in rows)                                     # nothing a confirmation can still do for this sentence
    a = CP.query('移動する', placement=R9, layer=env.layer)
    assert a['frame_status'] == 'CONFIRMED' and a['frame'] == {'へ': ['PLACE']} and a['decided_by'][-1] == 'gen_frame' and a['decided_by'][0].startswith('human:')


def test_r3_a_predicate_whose_base_role_frame_the_reader_refuses_is_not_reachable_by_a_frame_row(env, tmp_path):
    """J15 (not fixed): the base's role frame of 移動する has `backed_by` entries, the reader refuses them, so a `confirm frame` row would not be read either."""
    rows = _suggest_rows(env, tmp_path, ['田中が駅に移動した。'])
    fr = [r for r in rows if r['op'] == 'frame']
    assert len(fr) == 1 and fr[0]['word'] == '移動する' and fr[0]['particle'] == 'に' and fr[0]['reachable'] is False
    assert fr[0]['why'] == 'BASE_ROLE_FRAME_INVALID:ROLE_FRAME_INVALID:ENTRY_KEYS:に (J15)'
    assert [r for r in rows if r['op'] == 'set' and r['word'] == '駅'][0]['reachable'] is True        # the filler row stays as it was (not changed in r3)


def test_r3_frame_not_read_is_not_a_twelve_ten_reason():
    """`PLACEMENT_FRAME_NOT_READ:` is a K62 table reason: the 12.10 set is exactly three names (no prefix)."""
    from verantyx import confirm_cli as CC
    assert CC._FRAME_1210_REASONS == ('PLACEMENT_FRAME_PARTICLE_NOT_CONFIRMED', 'PLACEMENT_FRAME_TYPE_NOT_CONFIRMED', 'PLACEMENT_FRAME_INVALID')
