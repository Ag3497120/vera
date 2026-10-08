"""W16-t8 (T8-2, docs/COARSE_PLACEMENT.md 12.21.5): the synthetic check of the tools, on the writer's OWN 40 sentences (frozen: artifacts/w16-t8/data_freeze.sha256).  A pass shows the chain
suggest -> confirm -> read works; it is not evidence that the reader generalizes.  Needs the placement r9 (read only)."""
import json
import os
from pathlib import Path

import pytest

from tools.t8 import t82_flow as F
from verantyx import placement_layer as PL

R9 = '/Users/motonisihikoudai/Projects/vera-impl/wt/W3-a6-S/build/coarse-W3a/full/r9/run2'
DATA = str(Path(__file__).resolve().parent.parent / 'artifacts' / 'w16-t8' / 'data')


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    for k in (PL.ENV_LAYER, PL.ENV_ROOT, 'VERA_PLACEMENT'):
        monkeypatch.delenv(k, raising=False)
    if not Path(R9).exists():
        pytest.skip('ENV_MISSING[coarse placement r9/run2]')


@pytest.fixture(scope='module')
def flow(tmp_path_factory):
    if not Path(R9).exists():
        pytest.skip('ENV_MISSING[coarse placement r9/run2]')
    out = tmp_path_factory.mktemp('t82')
    saved = {k: os.environ.pop(k, None) for k in (PL.ENV_LAYER, PL.ENV_ROOT, 'VERA_PLACEMENT')}
    try:
        return F.run_flow(R9, DATA, str(out)), out
    finally:
        for k, v in saved.items():
            if v is not None:
                os.environ[k] = v


def test_the_data_are_the_frozen_ones():
    assert F.verify_freeze(DATA) == []
    t = (Path(DATA).parent / 'data_freeze_time.txt').read_text().strip()
    p = (Path(DATA).parent / 'prereg_time.txt').read_text().strip()
    assert t > p                                                                    # the freeze is after the registration (same format, same zone)


def test_the_set_is_forty_sentences_with_at_least_ten_controls():
    rows = [json.loads(x) for x in open(Path(DATA) / 'synthetic_40.jsonl', encoding='utf-8')]
    assert len(rows) == 40 and sum(1 for r in rows if r['group'] == 'control') >= 10
    truth = [json.loads(x) for x in open(Path(DATA) / 'confirmations_truth.jsonl', encoding='utf-8')]
    needles = []
    for t in truth:
        w = t['word']
        needles += [w] + ([w[:-2] if w.endswith('する') else w[:-1]] if t['type'].startswith('P_') else [])         # a verb is looked for by its stem too
    for r in rows:
        if r['group'] == 'control':
            assert not any(n in r['text'] for n in needles), r['text']


def test_the_confirmations_suggest_named_make_more_targets_readable(flow):
    # r3 (監査役の裁定 2026-10-06 00:24): was readable_after == n (26), abstained_after == [], written == in_truth, truth_not_named == [].  A `set` of 移動する no longer drops the base's 12.10 frame, which refuses
    # the subject が: t01-t09 (the 移動する sentences) stay abstained and suggest says they are not reachable; the other 17 are read.
    s, _ = flow
    t = s['groups']['target']
    assert t['readable_before'] < t['readable_after']
    assert (t['readable_before'], t['readable_after'], t['n']) == (0, 17, 26)
    assert t['abstained_after'] == ['t%02d' % i for i in range(1, 10)]
    assert (s['confirmations_written'], s['confirmations_in_truth']) == (9, 10) and s['truth_not_named'] == ['移動する']
    assert len(s['rounds']) <= 3


def test_only_the_words_suggest_named_were_confirmed(flow):
    s, out = flow
    listed = json.loads((Path(out) / 't82_list.json').read_text())['confirmations']
    named = {w for r in s['rounds'] for w in r['named']}
    assert {c['word'] for c in listed} <= named and len(listed) == s['confirmations_written']
    assert '転勤する' in named and '転勤する' not in {c['word'] for c in listed}              # named, but nobody confirmed it: it is not in the truth list


def test_the_control_sentences_do_not_change_at_all(flow):
    s, out = flow
    c = s['groups']['control']
    assert c['changed_output'] == [] and c['readable_before'] == c['readable_after']
    b = [json.loads(x) for x in open(Path(out) / 't82_before.jsonl', encoding='utf-8')]
    a = [json.loads(x) for x in open(Path(out) / 't82_after.jsonl', encoding='utf-8')]
    for x, y in zip(b, a):
        if x['group'] == 'control':
            assert json.dumps(x, sort_keys=True, ensure_ascii=False) == json.dumps(y, sort_keys=True, ensure_ascii=False)       # byte for byte


def test_no_misreading_the_readings_are_the_confirmed_types_and_frames(flow):
    s, _ = flow
    assert s['groups']['target']['misread'] == [] and s['groups']['control']['misread'] == []


def test_three_or_more_decided_words_were_overridden_by_a_human(flow):
    s, out = flow
    assert len(s['overrode_decided']) >= 3
    over = json.loads((Path(out) / 't82_base_decided.json').read_text())
    # r3: 移動する is in the truth list but suggest no longer names it (its 12.10 frame is not reachable), so it was never confirmed: its answer is the base's (BASE_DECIDED)
    for o in over:
        if o['word'] == '移動する':
            assert o['layer_status'] == 'BASE_DECIDED' and not o['decided_by'][0].startswith('human:')
        else:
            assert o['layer_status'] == 'HUMAN_CONFIRMED_USED' and o['decided_by'][0].startswith('human:')
    decided = [o for o in over if o['base_state'] == 'DECIDED' and o['decided_by'][0].startswith('human:')]
    assert len(decided) >= 3 and {o['word'] for o in decided} == set(s['overrode_decided']) == {'学校', '会社', '移住する', '出向く', '赴く'}
    assert any(o['base_origin'] == 'direct' for o in decided) and any(o['base_origin'] == 'estimated' for o in decided)


# ---- r2 (12.21.6): the `frame` confirmation, from the suggestion to the reading -------------------------------------------------------------------------------------------------------
FRAME = dict(rows_file='synthetic_frame.jsonl', truth_file='confirmations_truth_frame.jsonl', freeze_file='data_freeze_frame.sha256')


@pytest.fixture(scope='module')
def flow_frame(tmp_path_factory):
    if not Path(R9).exists():
        pytest.skip('ENV_MISSING[coarse placement r9/run2]')
    out = tmp_path_factory.mktemp('t82f')
    saved = {k: os.environ.pop(k, None) for k in (PL.ENV_LAYER, PL.ENV_ROOT, 'VERA_PLACEMENT')}
    try:
        return F.run_flow(R9, DATA, str(out), **FRAME), out
    finally:
        for k, v in saved.items():
            if v is not None:
                os.environ[k] = v


def test_the_frame_data_are_the_frozen_ones_and_registered_before():
    assert F.verify_freeze(DATA, 'data_freeze_frame.sha256') == []
    base = Path(DATA).parent
    assert (base / 'data_freeze_frame_time.txt').read_text().strip() > (base / 'prereg_frame_time.txt').read_text().strip()


def test_suggest_names_the_frame_and_the_frame_row_is_written(flow_frame):
    # r3 (監査役の裁定 2026-10-06 00:24): was: suggest names `frame 移動する へ` as reachable, the flow writes `set` + `frame` (2 confirmations).  Now suggest still names the frame but says it is NOT reachable
    # (the base's 12.10 frame and role frame of 移動する are kept; J15), the flow writes nothing for it, and the only `set` rows suggest names are the filler nouns that the truth list does not hold.
    s, out = flow_frame
    first = (Path(out) / 't82_suggest_round1.tsv').read_text(encoding='utf-8').splitlines()
    head = first[0].split('\t')
    rows = [dict(zip(head, ln.split('\t'))) for ln in first[1:] if ln and not ln.startswith('#')]
    fr = [r for r in rows if r['op'] == 'frame' and r['word'] == '移動する']
    assert fr and all(r['reachable'] == 'false' for r in fr)
    assert {r['why'] for r in fr if r['particle'] == 'が'} == {'BASE_FRAME_1210_KEPT'}
    assert {r['why'] for r in fr if r['particle'] == 'へ'} == {'BASE_ROLE_FRAME_INVALID:ROLE_FRAME_INVALID:ENTRY_KEYS:に (J15)'}
    listed = json.loads((Path(out) / 't82_list.json').read_text())['confirmations']
    assert listed == [] and s['confirmations_written'] == 0 and s['truth_not_named'] == ['移動する', '移動する']
    assert s['rounds'][0]['named'] == ['学校', '会社', '山田'] and s['rounds'][0]['written'] == []


def test_the_frame_makes_the_organisation_goal_sentences_readable_as_the_frame_says(flow_frame):
    s, out = flow_frame
    t = s['groups']['target']
    # r3 (監査役の裁定 2026-10-06 00:24): was readable_after == 4, abstained_after == ['f05'], 移動する in overrode_decided.  Nothing is confirmed any more (see the test above): the five stay abstained.
    assert t['readable_before'] == 0 and t['readable_after'] == 0 and t['misread'] == []
    assert t['abstained_after'] == ['f01', 'f02', 'f03', 'f04', 'f05'] and t['changed_output'] == []
    assert s['groups']['control']['changed_output'] == [] and s['groups']['control']['misread'] == []
    assert s['overrode_decided'] == []


def test_the_set_alone_does_not_read_the_organisation_goal_sentences(tmp_path):
    rows = [json.loads(x) for x in open(Path(DATA) / 'synthetic_frame.jsonl', encoding='utf-8')]
    layer, ledger = str(tmp_path / 'l.sqlite'), str(tmp_path / 'g.jsonl')
    rc, _ = F._cli(['confirm', 'set', '移動する', 'P_MOVE', '--by', 't', '--layer', layer, '--ledger-file', ledger, '--placement', R9])
    assert rc == 0
    after = F._read_all(rows, R9, layer)
    for r, rd in zip(rows, after):
        if r['group'] == 'target':
            assert not rd.get('readable'), r['text']                                # without the frame the type table refuses the goal (GROUP_ORG)
        if r['group'] == 'frame_not_restrictive':
            assert not rd.get('readable'), r['text']                                # r3 (was: readable): the base's 12.10 frame of 移動する stays after the `set` and refuses the subject が


def test_a_human_frame_adds_but_does_not_restrict(flow_frame):
    s, out = flow_frame
    g = s['groups']['frame_not_restrictive']
    # r3 (監査役の裁定 2026-10-06 00:24): was not_stopped == 3 (the PLACE goals were read although the declared frame lists GROUP_ORG only).  With nothing confirmed they are not read; no misreading.
    assert g['n'] == 3 and g['not_stopped'] == 0 and g['misread'] == []


def test_the_flow_counts_a_reading_where_abstention_was_expected_as_misread(tmp_path):
    data = tmp_path / 'data'
    data.mkdir()
    (data / 'rows.jsonl').write_text(json.dumps({'id': 'x1', 'text': '田中が本を読んだ。', 'expect': 'ABSTAIN', 'group': 'control'}, ensure_ascii=False) + '\n', encoding='utf-8')
    (data / 'truth.jsonl').write_text('', encoding='utf-8')
    import hashlib
    (tmp_path / 'f.sha256').write_text(''.join('%s  %s\n' % (hashlib.sha256((data / n).read_bytes()).hexdigest(), n) for n in ('rows.jsonl', 'truth.jsonl')), encoding='utf-8')
    saved = {k: os.environ.pop(k, None) for k in (PL.ENV_LAYER, PL.ENV_ROOT, 'VERA_PLACEMENT')}
    try:
        s = F.run_flow(R9, str(data), str(tmp_path / 'out'), 'rows.jsonl', 'truth.jsonl', 'f.sha256')
    finally:
        for k, v in saved.items():
            if v is not None:
                os.environ[k] = v
    assert s['groups']['control']['readable_after'] == 1 and s['groups']['control']['misread'] == ['x1']
