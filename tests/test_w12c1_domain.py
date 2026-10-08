"""W12-c1 T2: the domain layer (K408) on a hand-made base: what is written, what is not, the base sha, the ledger chain."""
import importlib.util
import os
import sqlite3
import sys

import pytest

from verantyx import placement_layer as PL
from verantyx.testimony_ledger import TestimonyLedger

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
spec = importlib.util.spec_from_file_location('build_initial_layers', os.path.join(ROOT, 'tools', 'build_initial_layers.py'))
BIL = importlib.util.module_from_spec(spec)
sys.modules['build_initial_layers'] = BIL
spec.loader.exec_module(BIL)

SHA = 'sha-of-the-base'


def base_answers(table):
    return lambda w: {'state': table.get(w, ('UNPLACED', []))[0], 'top': list(table.get(w, ('UNPLACED', []))[1])}


def test_plan_follows_k408():
    cands = [('決まった語', 'PERSON', 'definition'),            # the base DECIDED it: not written
             ('未決の語', 'PLACE', 'alias'),                    # the base UNPLACED: written
             ('多義の語', 'WORK', 'definition'),                # MULTIPLE and the type is among the base's candidates: written
             ('多義の外', 'TIME', 'definition'),                # MULTIPLE and the type is outside: not written
             ('型でない', 'NOT_A_TYPE', 'x')]
    table = {'決まった語': ('DECIDED', ['PERSON']), '未決の語': ('UNPLACED', []), '多義の語': ('MULTIPLE', ['PLACE', 'WORK']), '多義の外': ('MULTIPLE', ['PLACE', 'WORK'])}
    plan = BIL.plan_domain_layer(cands, base_answers(table), lambda w: 'DECIDED' if w == '決まった語' else None)
    assert [x['word'] for x in plan['write']] == ['未決の語', '多義の語']
    assert plan['not_written'] == {'BASE_DECIDED': 1, 'TYPE_NOT_AMONG_BASE_CANDIDATES': 1, 'DOMAIN_TYPE_NOT_A_TYPE_ID': 1}


def test_prefilter_is_not_trusted_over_the_base_query():
    # the table says nothing (None) but the base's own answer is DECIDED (estimated, spelled differently...): the query decides
    plan = BIL.plan_domain_layer([('語', 'PERSON', 'definition')], base_answers({'語': ('DECIDED', ['PERSON'])}), lambda w: None)
    assert plan['write'] == [] and plan['not_written'] == {'BASE_DECIDED': 1}


def test_written_rows_name_the_base_and_the_ledger_goes_first(tmp_path):
    plan = {'write': [{'word': '未決の語', 'type': 'PLACE', 'by': ['alias'], 'base_state': 'UNPLACED', 'base_top': []},
                      {'word': '多義の語', 'type': 'WORK', 'by': ['definition'], 'base_state': 'MULTIPLE', 'base_top': ['PLACE', 'WORK']}], 'not_written': {}}
    led = TestimonyLedger(tmp_path / 'ledger.jsonl')
    path = str(tmp_path / 'law.sqlite')
    n = BIL.write_plan(plan, path, led, SHA, {'domain': 'law', 'scene': 'S', 'domain_placement_content_sha256': 'dsha', 'evidence_rows': [1, 2]})
    assert n == 2
    g = PL.growth(path, led, SHA)
    assert g['layer_status'] == 'OK' and g['base_content_sha256'] == SHA
    assert g['words']['direct'] == 2 and g['ledger']['chain_ok'] is True and g['ledger']['promoted_to_layer'] == 2
    con = sqlite3.connect(path)
    assert dict(con.execute('SELECT k, v FROM meta').fetchall())['base_content_sha256'] == SHA
    origins = {r[0] for r in con.execute('SELECT origin FROM entries')}
    assert origins == {'layer_confirmed'}
    ev = PL.open_layer(path, SHA)[0].all_entries()[0]['evidence']
    assert ev['material_origin'] == 'generated' and ev['model'] is None and ev['decision'] == 'builder_domain' and ev['domain'] == 'law'


def test_a_layer_made_on_another_base_is_refused(tmp_path):
    plan = {'write': [{'word': '語', 'type': 'PLACE', 'by': ['alias'], 'base_state': 'UNPLACED', 'base_top': []}], 'not_written': {}}
    led = TestimonyLedger(tmp_path / 'ledger.jsonl')
    path = str(tmp_path / 'l.sqlite')
    BIL.write_plan(plan, path, led, SHA, {})
    with pytest.raises(PL.LayerError):
        BIL.write_plan(plan, path, led, 'another-base', {})


def test_capacity_law_is_the_one_of_hierarchy():
    from verantyx import hierarchy as H
    rep = BIL.capacity_report({'a': 10, 'b': 24, 'c': 25, 'd': 5000})
    assert rep['CAPACITY'] == H.CAPACITY == 24
    assert rep['layers']['a']['fits_one_node'] and rep['layers']['b']['fits_one_node'] and not rep['layers']['c']['fits_one_node']
    assert rep['layers']['d']['layers_for_V'] == H._layers_for(5000)


def test_domain_db_keeps_ids_and_does_not_overwrite(tmp_path):
    src = str(tmp_path / 's.db')
    con = sqlite3.connect(src)
    con.execute('CREATE TABLE rows(id INTEGER PRIMARY KEY, text TEXT NOT NULL, source TEXT, scene TEXT, grp TEXT, sha TEXT, family TEXT, source_file TEXT, line INTEGER, kind TEXT, fields TEXT, origin TEXT, generator TEXT, body_sha TEXT)')
    con.executemany('INSERT INTO rows(id, text, scene, body_sha) VALUES (?,?,?,?)', [(i, 't%d' % i, 'A' if i % 2 else 'B', 'b%d' % i) for i in range(1, 11)])
    con.commit()
    con.close()
    out = str(tmp_path / 'o' / 'general_qa.db')
    rep = BIL.make_domain_db(src, out, [3, 5, 7])
    assert rep['rows'] == 3 and rep['ids_min'] == 3 and rep['ids_max'] == 7
    assert [r[0] for r in sqlite3.connect(out).execute('SELECT id FROM rows ORDER BY id')] == [3, 5, 7]
    with pytest.raises(SystemExit):
        BIL.make_domain_db(src, out, [1])


def test_bulk_ledger_writes_the_bytes_the_stock_append_writes(tmp_path):
    import shutil
    clock = lambda: '2026-10-05T00:00:00+0900'
    head = TestimonyLedger(tmp_path / 'h.jsonl', clock=clock)
    for suffix in ('', '.manifest.json'):
        shutil.copy(str(tmp_path / 'h.jsonl') + suffix, str(tmp_path / 'a.jsonl') + suffix)
        shutil.copy(str(tmp_path / 'h.jsonl') + suffix, str(tmp_path / 'b.jsonl') + suffix)
    stock = TestimonyLedger(tmp_path / 'a.jsonl', clock=clock)
    bulk = TestimonyLedger(tmp_path / 'b.jsonl', clock=clock)
    plan = {'write': [{'word': 'w%d' % i, 'type': 'PLACE', 'by': ['alias'], 'base_state': 'UNPLACED', 'base_top': []} for i in range(7)], 'not_written': {}}
    from verantyx.testimony_ledger import key_of
    for i, item in enumerate(plan['write']):
        PL.write_entry(str(tmp_path / 'a' / 'layer.sqlite'), stock, base_sha256=SHA, word=item['word'], type=item['type'], origin='layer_confirmed', decided_by=item['by'], evidence={'i': i}, role_frame=None,
                       key=key_of(item['word'], item['word'], item['type'], None), candidate=item['word'])
    with BIL.bulk_ledger(bulk):
        for i, item in enumerate(plan['write']):
            PL.write_entry(str(tmp_path / 'b' / 'layer.sqlite'), bulk, base_sha256=SHA, word=item['word'], type=item['type'], origin='layer_confirmed', decided_by=item['by'], evidence={'i': i}, role_frame=None,
                           key=key_of(item['word'], item['word'], item['type'], None), candidate=item['word'])
    assert (tmp_path / 'a.jsonl').read_bytes() == (tmp_path / 'b.jsonl').read_bytes()
    assert (tmp_path / 'a.jsonl.manifest.json').read_bytes() == (tmp_path / 'b.jsonl.manifest.json').read_bytes()
    bulk.verify()                                             # the stock verification, after the block (instance restored)
    assert 'verify' not in bulk.__dict__ and PL.growth(str(tmp_path / 'b' / 'layer.sqlite'), bulk, SHA)['ledger']['chain_ok'] is True


def test_bulk_ledger_still_verifies_when_the_block_raises(tmp_path):
    led = TestimonyLedger(tmp_path / 'l.jsonl')
    with pytest.raises(RuntimeError):
        with BIL.bulk_ledger(led):
            PL.write_entry(str(tmp_path / 'l.sqlite'), led, base_sha256=SHA, word='語', type='PLACE', origin='layer_confirmed', decided_by=['alias'], evidence={}, role_frame=None, key='k')
            raise RuntimeError('boom')
    led.verify()
    assert len([e for e in led.entries() if e.get('type') == 'promoted_to_layer']) == 1


def test_plan_normalizes_words_and_counts_duplicates():
    cands = [('ア＝イ', 'INFO_LANGUAGE', 'alias'), ('ア=イ', 'INFO_LANGUAGE', 'alias'), ('ア=イ', 'PLACE', 'alias')]
    plan = BIL.plan_domain_layer(cands, base_answers({}), lambda w: None)
    assert [(x['word'], x['type']) for x in plan['write']] == [('ア=イ', 'INFO_LANGUAGE'), ('ア=イ', 'PLACE')]       # one row per (NFKC word, type); two types stay two rows (the layer then abstains: LAYER_CONFLICT)
    assert plan['not_written'] == {'DUPLICATE_AFTER_NFKC': 1}


def test_cached_ledger_view_answers_for_growth(tmp_path):
    led = TestimonyLedger(tmp_path / 'l.jsonl')
    path = str(tmp_path / 'x.sqlite')
    plan = {'write': [{'word': 'w%d' % i, 'type': 'PLACE', 'by': ['alias'], 'base_state': 'UNPLACED', 'base_top': []} for i in range(5)], 'not_written': {}}
    BIL.write_plan(plan, path, led, SHA, {})
    view = BIL.CachedLedgerView(led)
    g = PL.growth(path, view, SHA)
    assert g['words']['direct'] == 5 and g['ledger']['chain_ok'] is True and g['ledger']['store_id'] == led.store_id
