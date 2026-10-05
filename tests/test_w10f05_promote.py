"""W10-f05 (O3, K291/K294, docs/COARSE_PLACEMENT.md section 12.19): `vera ledger promote --layer` and the `promoted_to_layer` rows of the testimony ledger."""
import json
from pathlib import Path

import pytest

from verantyx import cli
from verantyx import coarse_place as CP
from verantyx import placement_layer as PL
from verantyx import semantic_reader as R
from verantyx.testimony_ledger import TestimonyLedger, key_of, sentence_sha256

R9 = '/Users/motonisihikoudai/Projects/vera-impl/wt/W3-a6-S/build/coarse-W3a/full/r9/run2'


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    for k in (PL.ENV_LAYER, PL.ENV_ROOT, 'VERA_PLACEMENT', 'VERA_SOVEREIGN_ROOT', 'VERA_SOVEREIGN_STORE'):
        monkeypatch.delenv(k, raising=False)


@pytest.fixture
def r9():
    if not Path(R9).exists():
        pytest.skip('ENV_MISSING[coarse placement r9/run2]')
    return R9


def add_testimony(led, word, typ, sentence, *, candidate=None, fill_id=None, basis='LLM_TESTIMONY_FILL:m:d', frame=None):
    fid = fill_id or ('f-%s-%s' % (word, sentence_sha256(sentence)[:6]))
    decl = {'type': typ, 'role': None}
    if frame:
        decl['frame'] = frame
    led.record_decision({'fill_id': fid, 'word': word, 'declaration': decl, 'candidate': candidate or word, 'hole': None, 'provenance': {'backend': 'fake', 'model': 'm', 'version': ''},
                         'context': {'doc_id': 'd', 'sentence_sha256': sentence_sha256(sentence)}, 'gate_log': [], 'status': 'ADOPTED', 'reason': 'ADOPTED', 'choice_decision_id': None,
                         'basis': basis, 'mask_user_text': True, 'records_checked': 0})
    return fid


def by_word(plan):
    return {it['word']: it for it in plan}


def test_a_human_confirmation_is_layer_human_and_a_reread_alone_is_estimated_never_direct(tmp_path):
    led = TestimonyLedger(tmp_path / 'l.jsonl', promote_n=3)
    f1 = add_testimony(led, '人の語', 'ARTIFACT', 's0')
    led.confirm(f1)
    for i in range(4):                                            # 3 re-readings of the same (word, candidate, type) on other sentences
        add_testimony(led, '再読の語', 'ARTIFACT', 's%d' % i)
    for i in range(3):                                            # only 2 re-readings: not promotable
        add_testimony(led, '足りない語', 'ARTIFACT', 's%d' % i)
    plan = by_word(led.promotion_plan('dom'))
    assert (plan['人の語']['origin'], plan['人の語']['decided_by']) == ('layer_human', ['layer_human'])
    assert plan['再読の語']['origin'] == 'layer_estimated' and plan['再読の語']['decided_by'] == []
    assert plan['足りない語']['origin'] is None and plan['足りない語']['skip'].startswith('NOT_PROMOTABLE')
    assert all(it['origin'] != 'layer_confirmed' for it in plan.values())                   # promote never makes a `layer_confirmed` row (that needs the documents)


def test_a_conflicting_testimony_does_not_promote_except_through_a_human(tmp_path):
    led = TestimonyLedger(tmp_path / 'l.jsonl', promote_n=1)
    add_testimony(led, '争う語', 'ARTIFACT', 's0', candidate='候補甲', fill_id='fa')
    b = add_testimony(led, '争う語', 'ARTIFACT', 's0', candidate='候補乙', fill_id='fb')
    for i in range(1, 3):
        add_testimony(led, '争う語', 'ARTIFACT', 's%d' % i, candidate='候補甲')
        add_testimony(led, '争う語', 'ARTIFACT', 's%d' % i, candidate='候補乙')
    plan = led.promotion_plan('dom')
    assert all(it['origin'] is None and it['skip'] == 'NOT_PROMOTABLE:CONFLICTING_TESTIMONY' for it in plan)
    led.confirm(b)
    plan = {it['candidate']: it for it in led.promotion_plan('dom')}
    assert plan['候補乙']['origin'] == 'layer_human' and plan['候補甲']['origin'] is None


def test_a_word_the_base_decides_is_skipped_k290(tmp_path):
    led = TestimonyLedger(tmp_path / 'l.jsonl')
    led.confirm(add_testimony(led, '基底が決める語', 'ARTIFACT', 's0'))
    led.confirm(add_testimony(led, '基底が決めない語', 'ARTIFACT', 's0'))
    plan = by_word(led.promotion_plan('dom', lambda w: {'state': 'DECIDED' if w == '基底が決める語' else 'UNPLACED'}))
    assert plan['基底が決める語']['skip'] == 'SKIP_BASE_DECIDED' and plan['基底が決める語']['origin'] is None
    assert plan['基底が決めない語']['origin'] == 'layer_human'


def test_a_distribution_backed_row_alone_is_not_promoted_a_fill_one_because_the_base_decides_a_grow_one_because_it_is_in_the_layer(tmp_path):
    led = TestimonyLedger(tmp_path / 'l.jsonl')
    add_testimony(led, '穴の語', 'ARTIFACT', 's0')
    led.mark_distribution_backed('穴の語', '穴の語', 'ARTIFACT', None, 'f1', {'state': 'DECIDED', 'top': ['ARTIFACT'], 'origin': 'direct', 'decided_by': ['seed']})
    add_testimony(led, '育った語', 'ARTIFACT', 's0', basis='LLM_TESTIMONY_PLACEMENT:m')
    led.mark_distribution_backed('育った語', '育った語', 'ARTIFACT', None, 'f2', {'state': 'DECIDED', 'top': ['ARTIFACT'], 'origin': 'direct', 'decided_by': ['hearst@doc:x']})
    plan = by_word(led.promotion_plan('dom', lambda w: {'state': 'UNPLACED'}))
    assert plan['穴の語']['skip'] == 'SKIP_BASE_DECIDED' and plan['育った語']['skip'] == 'SKIP_DISTRIBUTION_ONLY_NOT_IN_THIS_LAYER'      # nothing in the layer yet
    PL.write_entry(str(tmp_path / 'dom.sqlite'), led, base_sha256='b', word='育った語', type='ARTIFACT', origin='layer_confirmed', decided_by=['hearst@doc:x'], evidence={}, role_frame=None,
                   key=key_of('育った語', '育った語', 'ARTIFACT', None))
    assert by_word(led.promotion_plan('dom', lambda w: {'state': 'UNPLACED'}))['育った語']['skip'] == 'SKIP_ALREADY_IN_LAYER'


def test_the_plan_changes_neither_the_ledger_nor_a_layer(tmp_path):
    led = TestimonyLedger(tmp_path / 'l.jsonl')
    led.confirm(add_testimony(led, '語', 'ARTIFACT', 's0'))
    n = len(led.entries())
    led.promotion_plan('dom')
    assert len(led.entries()) == n and not list(tmp_path.glob('*.sqlite'))


# ---------------------------------------------------------------------------------------------------------------- the command (with the real base r9)
def run(capsys, *argv):
    code = cli.main(list(argv))
    out = capsys.readouterr().out
    return code, json.loads(out)


def test_promote_writes_layer_rows_once_and_each_has_its_ledger_row(r9, tmp_path, capsys, monkeypatch):
    monkeypatch.setenv('VERA_PLACEMENT', r9)
    layer = str(tmp_path / 'dom.sqlite')
    ledger = tmp_path / 'l.jsonl'
    led = TestimonyLedger(ledger, promote_n=3)
    pre = {w: CP.query(w, placement=r9)['state'] for w in ('ディレイラー', '猫', 'チェーンリング')}
    assert pre['ディレイラー'] in ('UNPLACED', 'UNKNOWN', 'MULTIPLE') and pre['猫'] == 'DECIDED'
    led.confirm(add_testimony(led, 'ディレイラー', 'ARTIFACT', 's0'))
    led.confirm(add_testimony(led, '猫', 'ARTIFACT', 's0'))
    for i in range(4):
        add_testimony(led, 'チェーンリング', 'ARTIFACT', 's%d' % i)
    code, out = run(capsys, 'ledger', 'promote', '--ledger-file', str(ledger), '--layer', layer, '--placement', r9)
    assert code == 0 and out['written'] == {'layer_confirmed': 0, 'layer_estimated': 1, 'layer_human': 1} and out['skipped'] == {'SKIP_BASE_DECIDED': 1}
    n_rows = len(TestimonyLedger(ledger).entries())
    code, again = run(capsys, 'ledger', 'promote', '--ledger-file', str(ledger), '--layer', layer, '--placement', r9)
    assert again['written'] == {'layer_confirmed': 0, 'layer_estimated': 0, 'layer_human': 0} and again['skipped'] == {'SKIP_ALREADY_PROMOTED': 2, 'SKIP_BASE_DECIDED': 1}
    assert len(TestimonyLedger(ledger).entries()) == n_rows                                  # two runs, the same rows
    led = TestimonyLedger(ledger)
    assert led.verify()['lines'] == n_rows                                                   # the chain is intact
    g = PL.growth(layer, led, CP._open(r9)[0].sha, True)
    assert g['words'] == {'direct': 0, 'human': 1, 'estimated': 1, 'conflict': 0} and g['ledger']['chain_ok'] is True and g['ledger']['promoted_to_layer'] == 2
    lay = PL.open_layer(layer)[0]
    for e in lay.all_entries():
        row = [x for x in led.entries() if x['seq'] == e['ledger_seq']][0]
        assert row['type'] == 'promoted_to_layer' and row['word'] == e['word'] and row['origin'] == e['origin'] and e['ledger_store_id'] == led.store_id
    a = CP.query('ディレイラー', placement=r9, layer=layer)
    assert (a['layer_status'], a['top'], a['decided_by']) == ('LAYER_DIRECT_USED', ['ARTIFACT'], ['layer_human']) and R.placement_type(a) == ('ARTIFACT', None)
    b = CP.query('チェーンリング', placement=r9, layer=layer)
    assert b['layer_status'] == 'LAYER_ESTIMATED_NOT_USED' and b['state'] == pre['チェーンリング']             # a re-reading alone is shown, never read


def test_promote_refuses_without_a_layer_or_a_placement_and_a_foreign_layer(r9, tmp_path, capsys, monkeypatch):
    led = TestimonyLedger(tmp_path / 'l.jsonl')
    led.confirm(add_testimony(led, 'ディレイラー', 'ARTIFACT', 's0'))
    code, out = run(capsys, 'ledger', 'promote', '--ledger-file', str(tmp_path / 'l.jsonl'), '--placement', r9)
    assert code == 2 and out['verdict'] == 'LAYER_REQUIRED'
    code, out = run(capsys, 'ledger', 'promote', '--ledger-file', str(tmp_path / 'l.jsonl'), '--layer', 'dom')
    assert code == 2 and out['verdict'] == 'LAYER_UNAVAILABLE:ROOT_UNSET'
    code, out = run(capsys, 'ledger', 'promote', '--ledger-file', str(tmp_path / 'l.jsonl'), '--layer', str(tmp_path / 'dom.sqlite'))
    assert code == 2 and out['verdict'] == 'NO_PLACEMENT'
    n = len(TestimonyLedger(tmp_path / 'l.jsonl').entries())
    PL.write_entry(str(tmp_path / 'dom.sqlite'), TestimonyLedger(tmp_path / 'other.jsonl'), base_sha256='not-r9', word='x', type='ARTIFACT', origin='layer_human', decided_by=['layer_human'],
                   evidence={}, role_frame=None, key='k')
    code, out = run(capsys, 'ledger', 'promote', '--ledger-file', str(tmp_path / 'l.jsonl'), '--layer', str(tmp_path / 'dom.sqlite'), '--placement', r9)
    assert code == 2 and out['verdict'] == 'LAYER_BASE_MISMATCH' and len(TestimonyLedger(tmp_path / 'l.jsonl').entries()) == n         # nothing appended to the ledger


def test_the_old_ledger_commands_are_unchanged(tmp_path, capsys):
    led = TestimonyLedger(tmp_path / 'l.jsonl')
    fid = add_testimony(led, '語', 'ARTIFACT', 's0')
    assert cli.main(['ledger', 'list', '--ledger-file', str(tmp_path / 'l.jsonl')]) == 0
    assert '語 -> 語' in capsys.readouterr().out
    assert cli.main(['ledger', 'confirm', '--ledger-file', str(tmp_path / 'l.jsonl')]) == 2          # still: an id is required
    assert cli.main(['ledger', 'confirm', fid, '--ledger-file', str(tmp_path / 'l.jsonl')]) == 0
