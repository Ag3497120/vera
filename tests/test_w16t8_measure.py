"""W16-t8 (T8-3, K682, docs/COARSE_PLACEMENT.md 12.21.4): tools/t8/measure.py on the writer's own synthetic train / test / real sets (artifacts/w16-t8/data).  Needs the placement r9 (read only)."""
import json
import os
from pathlib import Path

import pytest

from tools.t8 import measure as M
from verantyx import placement_layer as PL

R9 = '/Users/motonisihikoudai/Projects/vera-impl/wt/W3-a6-S/build/coarse-W3a/full/r9/run2'
DATA = Path(__file__).resolve().parent.parent / 'artifacts' / 'w16-t8' / 'data'


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    for k in (PL.ENV_LAYER, PL.ENV_ROOT, 'VERA_PLACEMENT'):
        monkeypatch.delenv(k, raising=False)


def sets():
    return {n: M.load_jsonl(str(DATA / ('measure_%s.jsonl' % n))) for n in ('train', 'test', 'real')}


def need_r9():
    if not Path(R9).exists():
        pytest.skip('ENV_MISSING[coarse placement r9/run2]')


# ---- pure parts (no placement) -----------------------------------------------------------------------------------------------------------------
def test_slope_is_the_least_squares_slope_and_none_with_one_step():
    assert M.slope([(0, 0), (5, 10), (10, 20)]) == pytest.approx(2.0)
    assert M.slope([(0, 3), (5, 3), (10, 3)]) == 0.0
    assert M.slope([(0, 0), (4, 1), (8, 5), (12, 6)]) == pytest.approx(((0 - 6) * (0 - 3) + (4 - 6) * (1 - 3) + (8 - 6) * (5 - 3) + (12 - 6) * (6 - 3)) / (36 + 4 + 4 + 36))
    assert M.slope([(0, 0)]) is None and M.slope([]) is None


def test_judge_rules():
    exp = [{'predicate': 'a', 'roles': {'agent': 'x'}, 'polarity': '+', 'tense': 'past', 'voice': 'active'}]
    read = {'readable': True, 'clauses': [dict(exp[0], modality=None, predicate_basis='b')]}
    assert M.judge(read, exp) == 'correct'
    assert M.judge(read, [dict(exp[0], tense='present')]) == 'misread'
    assert M.judge(read, []) == 'misread'
    assert M.judge(read, 'ABSTAIN') == 'misread'
    assert M.judge(read, None) == 'unjudged'
    assert M.judge({'readable': False, 'clauses': []}, exp) == 'abstain' and M.judge({'readable': False, 'clauses': []}, 'ABSTAIN') == 'abstain'


def test_overlap_finds_a_confirmed_word_or_its_stem_in_a_sentence():
    conf = [{'op': 'set', 'word': '移送する', 'type': 'P_MOVE'}, {'op': 'frame', 'predicate': '赴く', 'particle': 'へ', 'role': 'goal', 'types': ['PLACE']}, {'op': 'set', 'word': '倉庫', 'type': 'PLACE'}]
    sent = [{'id': 'a', 'text': '田中が工房へ移送した。'}, {'id': 'b', 'text': '田中が工房へ出張した。'}, {'id': 'c', 'text': '田中が倉庫へ赴いた。'}]
    got = M.overlap(conf, sent)
    assert sorted((o['id'], o['word']) for o in got) == sorted([('a', '移送する'), ('c', '赴く'), ('c', '倉庫')])
    assert not any(o['id'] == 'b' for o in got)


# ---- the tool on r9 -----------------------------------------------------------------------------------------------------------------------------
def test_three_sets_give_a_curve_and_a_slope_each(tmp_path):
    need_r9()
    res = M.measure(R9, M.load_jsonl(str(DATA / 'measure_confirmations.jsonl')), sets(), str(tmp_path / 'o'))
    assert res['steps_run'] == [0, 5, 10, 15, 20] and res['steps_skipped_beyond_rows'] == [25, 30, 35, 40, 45, 50]
    for name in ('train', 'test', 'real'):
        s = res['sets'][name]
        assert [m['k'] for m in s['per_k']] == res['steps_run'] and s['slope'] is not None
        assert s['per_k'][0]['newly_read'] == 0 and s['per_k'][0]['lost'] == 0
    tr, te, re_ = (res['sets'][n] for n in ('train', 'test', 'real'))
    assert tr['slope'] > 0 and tr['per_k'][-1]['readable'] > tr['per_k'][0]['readable']          # the confirmed words come back in the training sentences
    assert te['slope'] == 0.0 and te['verdict'] == 'TEST_DISJOINT_FROM_CONFIRMED' and te['overlap'] == []      # words nobody confirmed: nothing new is read
    assert re_['slope'] > 0
    assert sum(res['sets'][n]['misread_total_over_k'] for n in res['sets']) == 0
    assert res['owner_minutes'] is None and res['minutes_per_newly_read_real_at_last_k'] is None
    tsv = (tmp_path / 'o' / 'curve.tsv').read_text()
    assert tsv.splitlines()[0] == 'set\tk\tn\treadable\tnewly_read\tlost\tcorrect\tmisread\tunjudged' and '# slope\ttest\t0.000000' in tsv and '# owner_minutes\tnull' in tsv


def test_the_overlap_check_marks_a_test_set_that_reuses_a_confirmed_word(tmp_path):
    need_r9()
    S = sets()
    S['test'] = S['test'] + [{'id': 'te99', 'text': '田中が工房へ移送した。', 'expect': None}]
    res = M.measure(R9, M.load_jsonl(str(DATA / 'measure_confirmations.jsonl')), S, str(tmp_path / 'o'), [0, 5])
    assert res['sets']['test']['verdict'] == 'TEST_OVERLAPS_CONFIRMED' and [o['id'] for o in res['sets']['test']['overlap']] == ['te99']
    assert res['steps_run'] == [0, 5]


def test_the_same_input_gives_the_same_output(tmp_path):
    need_r9()
    a = M.measure(R9, M.load_jsonl(str(DATA / 'measure_confirmations.jsonl')), sets(), str(tmp_path / 'a'), [0, 5, 10])
    b = M.measure(R9, M.load_jsonl(str(DATA / 'measure_confirmations.jsonl')), sets(), str(tmp_path / 'b'), [0, 5, 10])
    assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)
    assert (tmp_path / 'a' / 'curve.tsv').read_text() == (tmp_path / 'b' / 'curve.tsv').read_text()


def test_a_misread_is_counted(tmp_path):
    need_r9()
    S = sets()
    wrong = dict(S['train'][0])
    wrong['id'] = 'tr_wrong'
    wrong['expect'] = [dict(wrong['expect'][0], tense='present')]
    S['train'] = [wrong] + S['train'][1:]
    res = M.measure(R9, M.load_jsonl(str(DATA / 'measure_confirmations.jsonl')), S, str(tmp_path / 'o'), [0, 5])
    assert res['sets']['train']['per_k'][-1]['misread'] == 1 and res['misread_detail'][0]['id'] == 'tr_wrong'


def test_the_owner_minutes_field_is_filled_only_from_a_file(tmp_path):
    need_r9()
    f = tmp_path / 'm.json'
    f.write_text('{"minutes": 30}')
    res = M.measure(R9, M.load_jsonl(str(DATA / 'measure_confirmations.jsonl')), sets(), str(tmp_path / 'o'), [0, 5, 10], M._owner_minutes(str(f)))
    assert res['owner_minutes'] == 30.0 and res['minutes_per_newly_read_real_at_last_k'] == pytest.approx(30.0 / res['sets']['real']['per_k'][-1]['newly_read'])


def test_a_used_output_directory_is_refused_and_the_environment_is_restored(tmp_path, monkeypatch):
    need_r9()
    monkeypatch.setenv(PL.ENV_LAYER, 'sentinel')
    conf = M.load_jsonl(str(DATA / 'measure_confirmations.jsonl'))
    M.measure(R9, conf, sets(), str(tmp_path / 'o'), [0, 5])
    assert os.environ[PL.ENV_LAYER] == 'sentinel'
    with pytest.raises(M.MeasureError):
        M.measure(R9, conf, sets(), str(tmp_path / 'o'), [0, 5])
    assert os.environ[PL.ENV_LAYER] == 'sentinel'


def test_the_command_line_runs_and_prints_one_json_line(tmp_path, capsys):
    need_r9()
    rc = M.main(['--placement', R9, '--confirmations', str(DATA / 'measure_confirmations.jsonl'), '--train', str(DATA / 'measure_train.jsonl'), '--test', str(DATA / 'measure_test.jsonl'),
                 '--real', str(DATA / 'measure_real.jsonl'), '--out', str(tmp_path / 'o'), '--steps', '0,5'])
    out = capsys.readouterr().out.strip().splitlines()
    assert rc == 0 and len(out) == 1 and json.loads(out[0])['steps_run'] == [0, 5]


def test_a_refused_confirmation_is_a_typed_refusal_not_a_traceback(tmp_path, capsys):
    need_r9()
    bad = tmp_path / 'c.jsonl'
    bad.write_text(json.dumps({'op': 'frame', 'predicate': 'ザクる', 'particle': 'を', 'role': 'patient', 'types': ['THING']}, ensure_ascii=False) + '\n', encoding='utf-8')
    rc = M.main(['--placement', R9, '--confirmations', str(bad), '--train', str(DATA / 'measure_train.jsonl'), '--test', str(DATA / 'measure_test.jsonl'),
                 '--real', str(DATA / 'measure_real.jsonl'), '--out', str(tmp_path / 'o'), '--steps', '0,1'])
    out = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert rc == 2 and out['verdict'].startswith('CONFIRMATION_REFUSED:ザクる:')
