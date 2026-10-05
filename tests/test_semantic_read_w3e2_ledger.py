"""W3-e2 (K334, D5): the `assumption` row of the testimony ledger. The folded view of a ledger without assumption rows is byte for byte the base's."""
import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from verantyx import testimony_ledger as TL

LEDGERS = [ROOT / 'artifacts/w10-f05/r3_ledger_fake.jsonl', ROOT / 'artifacts/w10-f05/r1_r3_ledger_fake.jsonl']


def base_module():
    src = subprocess.run(['git', '-C', str(ROOT), 'show', 'bfb17b8:verantyx/testimony_ledger.py'], capture_output=True, text=True, check=True).stdout
    spec = importlib.util.spec_from_loader('verantyx.testimony_ledger_base_bfb17b8', loader=None, origin='bfb17b8')
    mod = importlib.util.module_from_spec(spec)
    mod.__package__ = 'verantyx'
    exec(compile(src, 'testimony_ledger_base_bfb17b8.py', 'exec'), mod.__dict__)
    return mod


def copy_ledger(src, tmp):
    dst = Path(tmp) / src.name
    shutil.copy(src, dst)
    m = Path(str(src) + '.manifest.json')
    if m.exists():
        shutil.copy(m, Path(str(dst) + '.manifest.json'))
    return dst


@pytest.mark.parametrize('src', LEDGERS, ids=[p.name for p in LEDGERS])
def test_a_ledger_without_assumption_rows_folds_byte_for_byte_like_the_base(src):
    if not src.exists():
        pytest.skip('artifact of W10-f05 missing')
    base = base_module()
    with tempfile.TemporaryDirectory() as tmp:
        p = copy_ledger(src, tmp)
        new, old = TL.TestimonyLedger(p), base.TestimonyLedger(p)
        dump = lambda led: json.dumps([led.fold(), led.listing(), led.promotion_plan('x')], ensure_ascii=False, sort_keys=True)
        assert dump(new) == dump(old)


def rec(led, word, assumed, sha, kind='noun_type', source='llm:fake-model'):
    return led.record_assumption({'word': word, 'kind': kind, 'assumed': assumed, 'source': source, 'alternatives': [], 'sentence_sha256': sha})


def test_three_sentences_make_an_assumption_promotable_and_a_human_can_confirm_it(tmp_path):
    led = TL.TestimonyLedger(tmp_path / 'l.jsonl', promote_n=3)
    ids = []
    for i in range(3):
        r = rec(led, 'フレーム', 'PLACE', 'sha%d' % i)
        ids.append(r['row']['fill_id'])
        assert r['row']['type'] == 'assumption' and r['row']['kind'] == 'assumption'
    g = next(iter(led.fold().values()))
    assert g['reread_agreed'] == 2 and not g['promotable']          # the first row + two agreeing re-reads of the same key on other sentences
    rec(led, 'フレーム', 'PLACE', 'sha3')
    g = next(iter(led.fold().values()))
    assert g['reread_agreed'] == 3 and g['promotable'] and g['state'] == 'reread_agreed:3'
    led2 = TL.TestimonyLedger(tmp_path / 'm.jsonl')
    r = rec(led2, 'ホイール', 'PLACE', 'a')
    assert not next(iter(led2.fold().values()))['promotable']
    out = led2.confirm(r['row']['fill_id'])
    assert out['fill_id'] == r['row']['fill_id'] and next(iter(led2.fold().values()))['promotable']
    plan = led2.promotion_plan('lay')
    assert plan[0]['origin'] == 'layer_human'


def test_the_same_sentence_twice_is_not_a_reread(tmp_path):
    led = TL.TestimonyLedger(tmp_path / 'l.jsonl')
    for _ in range(3):
        rec(led, 'フレーム', 'PLACE', 'same')
    assert next(iter(led.fold().values()))['reread_agreed'] == 0


def test_a_joined_type_and_an_untyped_verb_are_never_folded_or_promoted(tmp_path):
    led = TL.TestimonyLedger(tmp_path / 'l.jsonl')
    for i in range(5):
        rec(led, 'ミナ', 'GROUP_ORG+PERSON', 's%d' % i, 'name_type', 'surface')
        rec(led, 'ザク', 'UNTYPED_VERB', 's%d' % i, 'nonce_predicate', 'surface')
    assert led.fold() == {} and led.listing() == []
    assert len([e for e in led.entries() if e['type'] == 'assumption']) == 10
    with pytest.raises(TL.LedgerError):
        led.confirm([e for e in led.entries() if e['type'] == 'assumption'][0]['fill_id'])


def test_the_row_keeps_the_sentence_only_when_it_is_not_masked(tmp_path):
    led = TL.TestimonyLedger(tmp_path / 'l.jsonl')
    r = led.record_assumption({'word': 'フレーム', 'kind': 'noun_type', 'assumed': 'PLACE', 'source': 'layer', 'alternatives': [], 'sentence_sha256': 'x'})
    assert 'sentence' not in r['row']['context']
    r = led.record_assumption({'word': 'ホイール', 'kind': 'noun_type', 'assumed': 'PLACE', 'source': 'layer', 'alternatives': [], 'sentence_sha256': 'y', 'sentence': 'ハルは…'})
    assert r['row']['context']['sentence'] == 'ハルは…'
    assert TL.ROW_TYPES[-1] == 'assumption' and TL.ROW_TYPES[:9] == ('header', 'testimony', 'not_adopted', 'backend_failed', 'reread_agreed', 'distribution_backed', 'human_confirmed',
                                                                      'promotable', 'promoted_to_layer')


def test_a_surface_assumption_is_not_promoted_by_rereads_alone(tmp_path):
    """Round 3 ruling 5: re-reads of a source-'surface' assumption are shown but not counted toward N (the surface would confirm itself); a human confirmation promotes it."""
    led = TL.TestimonyLedger(tmp_path / 'l.jsonl', promote_n=3)
    first = None
    for i in range(5):
        r = rec(led, 'ヨモ', 'PERSON', 'sha%d' % i, source='surface')
        first = first or r['row']['fill_id']
    g = next(iter(led.fold().values()))
    assert g['reread_agreed'] == 4 and not g['promotable'] and g['blocked_by'] == 'SURFACE_ASSUMPTION'
    assert g['state'] == 'reread_agreed:4'
    assert led.promotion_plan('lay')[0]['skip'] == 'NOT_PROMOTABLE:SURFACE_ASSUMPTION'
    led.confirm(first)
    g = next(iter(led.fold().values()))
    assert g['promotable'] and g['blocked_by'] is None
    led2 = TL.TestimonyLedger(tmp_path / 'm.jsonl', promote_n=3)        # the same re-reads from the back end are still counted
    for i in range(4):
        rec(led2, 'ヨモ', 'PERSON', 'sha%d' % i)
    assert next(iter(led2.fold().values()))['promotable']
