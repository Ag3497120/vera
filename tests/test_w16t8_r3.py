"""W16-t8 r3 (docs/COARSE_PLACEMENT.md 12.21.7): the auditor's two rulings (2026-10-06 00:24), on the frozen synthetic set `synthetic_r3.jsonl` (artifacts/w16-t8/data) and the placement r9 (read only).
(1) a human `set` changes the type only and the base's frames stay; (2) a confirmation row copied by `build_initial_layers.py combine` is not a human's confirmation.  A pass shows the tools do what the
rulings say; it is not evidence that the reader generalizes."""
import json
import os
from pathlib import Path

import pytest

from tools.t8 import r3_check as R3
from tools.t8 import set_only_vs_frame as S
from tools.t8 import t82_flow as F
from verantyx import placement_layer as PL

R9 = '/Users/motonisihikoudai/Projects/vera-impl/wt/W3-a6-S/build/coarse-W3a/full/r9/run2'
DATA = str(Path(__file__).resolve().parent.parent / 'artifacts' / 'w16-t8' / 'data')
ENVS = (PL.ENV_LAYER, PL.ENV_ROOT, 'VERA_PLACEMENT')
ARGS = dict(rows_file='synthetic_r3.jsonl', truth_file='confirmations_truth_r3.jsonl', freeze_file='data_freeze_r3.sha256')


def _isolated(fn):
    saved = {k: os.environ.pop(k, None) for k in ENVS}
    try:
        return fn()
    finally:
        for k, v in saved.items():
            if v is not None:
                os.environ[k] = v


@pytest.fixture(scope='module')
def flow(tmp_path_factory):
    if not Path(R9).exists():
        pytest.skip('ENV_MISSING[coarse placement r9/run2]')
    out = tmp_path_factory.mktemp('r3flow')
    return _isolated(lambda: R3.run_apply(R9, DATA, str(out), **ARGS)), out


def test_the_r3_data_are_the_frozen_ones_and_registered_before():
    if not Path(R9).exists():
        pytest.skip('ENV_MISSING[coarse placement r9/run2]')
    assert F.verify_freeze(DATA, 'data_freeze_r3.sha256') == []
    base = Path(DATA).parent
    assert (base / 'data_freeze_r3_time.txt').read_text().strip() > (base / 'r3' / 'prereg_r3_time.txt').read_text().strip()
    rows = [json.loads(x) for x in open(Path(DATA) / 'synthetic_r3.jsonl', encoding='utf-8')]
    n = {g: sum(1 for r in rows if r['group'] == g) for g in ('frame_kept', 'frame_reach', 'control')}
    assert n['frame_kept'] >= 6 and n['frame_reach'] >= 3 and n['control'] >= 4


def test_frame_kept_a_set_of_the_bases_own_type_does_not_free_the_sentences_the_12_10_frame_refuses(flow):
    s, _ = flow
    g = s['groups']['frame_kept']
    assert (g['n'], g['readable_before'], g['readable_after'], g['misread'], g['changed_output']) == (8, 0, 0, [], [])
    for sid, reasons in g['abstained_after'].items():
        assert any(r.startswith('PLACEMENT_FRAME_PARTICLE_NOT_CONFIRMED:P_MOVE:が') for r in reasons), sid
    words = {w['word']: w for w in s['confirmed_words'] if w['word'] in ('移動する', '避難する')}
    assert set(words) == {'移動する', '避難する'}
    for w in words.values():
        assert w['layer_status'] == 'HUMAN_CONFIRMED_USED' and w['decided_by_first'] == 'human' and w['decided_by_ends_with_gen_frame'] is True
        assert w['frame_same_as_base'] is True and w['role_frame_same_as_base'] is True and w['frame_status'] == ['CONFIRMED', 'CONFIRMED']


def test_frame_kept_is_not_driven_by_suggest(flow):
    s, _ = flow
    sb = s['suggest_before']
    assert not set(sb['reachable_words']) & {'移動する', '避難する'}
    assert sb['frame_rows_not_reachable'] == ['移動する:BASE_FRAME_1210_KEPT', '避難する:BASE_FRAME_1210_KEPT']


def test_frame_reach_a_human_frame_makes_the_goal_readable_where_the_base_has_no_confirmed_frame(flow):
    s, out = flow
    g = s['groups']['frame_reach']
    assert (g['n'], g['readable_before'], g['readable_after'], g['misread'], g['abstained_after']) == (5, 0, 5, [], {})       # measured (12.21.7)
    assert set(s['suggest_before']['reachable_words']) == {'出向く', '赴く', '転勤する'}
    tsv = S.build(R9, DATA, 'synthetic_r3.jsonl', '出向く', 'P_MOVE', 'へ', 'goal', ['GROUP_ORG'])
    line = [l.split('\t') for l in tsv.splitlines() if '田中が学校へ出向いた。' in l][0]
    assert line[3].startswith('ABSTAIN') and 'PLACEMENT_TYPE_MISMATCH:P_MOVE:へ:GROUP_ORG' in line[3] and line[4] == 'READ'                  # `set` alone is not enough, `frame` adds the reading


def test_control_sentences_do_not_change_at_all(flow):
    s, out = flow
    c = s['groups']['control']
    assert (c['n'], c['changed_output'], c['misread'], c['readable_before'], c['readable_after']) == (6, [], [], 6, 6)
    b = [json.loads(x) for x in open(Path(out) / 'r3_before.jsonl', encoding='utf-8')]
    a = [json.loads(x) for x in open(Path(out) / 'r3_after.jsonl', encoding='utf-8')]
    for x, y in zip(b, a):
        if x['group'] == 'control':
            assert json.dumps(x, sort_keys=True, ensure_ascii=False) == json.dumps(y, sort_keys=True, ensure_ascii=False)


def test_a_layer_copied_by_combine_reads_exactly_as_no_layer_and_no_copied_confirmation_is_used(flow, tmp_path):
    s, out = flow
    c = _isolated(lambda: R3.run_combine(R9, DATA, str(tmp_path / 'c'), 'synthetic_r3.jsonl', 'data_freeze_r3.sha256', str(Path(out) / 'r3_layer.sqlite')))
    assert c['identical_to_no_layer'] is True and c['differs'] == [] and c['human_confirmed_or_direct_used'] == 0
    assert c['combined_layer']['rows_that_are_confirmation_rows'] == 0 and c['combined_layer']['rows_unbacked_human'] == c['combined_layer']['rows'] == 8
    assert c['readable_no_layer'] == c['readable_combined'] == 6
