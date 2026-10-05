"""W10-f05 (docs/COARSE_PLACEMENT.md section 12.19, K290/K291/K294/K297): the placement layer and `coarse_place.query(..., layer=)`.

The table of the section (every `state` x `layer` row) is run on hand-made base answers (no placement needed); the r9 tests (read only) look at the real base answers."""
import json
import os
import sqlite3
from pathlib import Path
from types import SimpleNamespace

import pytest

from verantyx import coarse_place as CP
from verantyx import coarse_types as ct
from verantyx import placement_layer as PL
from verantyx import semantic_reader as R
from verantyx.testimony_ledger import TestimonyLedger

R9 = '/Users/motonisihikoudai/Projects/vera-impl/wt/W3-a6-S/build/coarse-W3a/full/r9/run2'
SHA = 'sha-of-the-base'
BASE = SimpleNamespace(sha=SHA, cfg=dict(ct.DEFAULT_CONFIG, rd_min_total=20, rd_store_min=20, rd_particle_min=10, rd_particle_share_pct=30, rd_type_share_pct=50,
                                         rd_min_sources=1, role_frame_min_sources=1, frame_cover_rule='k62_he_by_ni_place'))


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    for k in (PL.ENV_LAYER, PL.ENV_ROOT):
        monkeypatch.delenv(k, raising=False)


@pytest.fixture
def r9():
    if not Path(R9).exists():
        pytest.skip('ENV_MISSING[coarse placement r9/run2]')
    return R9


def base_answer(state, top=(), term='テスト語', with_role_frame=True):
    """A hand-made base answer with the key set and order of a real one."""
    top = list(top)
    direct = state == 'DECIDED'
    r = {'term': term, 'namespace': None if state in ('UNPLACED', 'UNKNOWN', 'NO_PLACEMENT') else 'N', 'state': state, 'origin': 'direct' if direct or state == 'MULTIPLE' else None,
         'estimate_basis': None, 'constructed': False, 'top': top, 'candidates': [{'type': t, 'axes': {'seed': 1}} for t in top], 'axes': {'seed': {'counts': {t: 1 for t in top}}},
         'neighbors': [], 'seen_in_material': state != 'UNKNOWN', 'context': {'role': None, 'predicate': None},
         'placement': {'path': '/p', 'content_sha256': SHA, 'reason': None}}
    if direct or state == 'MULTIPLE':
        r.update({'decided_by': ['seed'], 'generated': False, 'generated_definition': False})
    r['spelling'] = {'query': term, 'normalized': term, 'normalization': 'NFKC', 'kana': 'DISTINCT', 'kana_variant': None, 'why': None}
    r['frame_generated'] = None
    r['generated_frame'] = False
    r['frame_status'] = 'NO_ANSWER'
    r['frame'] = None
    if with_role_frame:
        r.update({'role_frame_status': 'NO_ROLE_FRAME', 'role_frame': None, 'role_frame_unconfirmed': None})
    return r


def make_layer(tmp_path, rows, sha=SHA, name='dom'):
    """A layer with the given rows [(word, type, origin, decided_by, evidence, role_frame)] written the only way there is: through `write_entry` and a ledger."""
    led = TestimonyLedger(tmp_path / 'ledger.jsonl')
    path = str(tmp_path / (name + '.sqlite'))
    for i, (word, typ, origin, by, ev, rf) in enumerate(rows):
        PL.write_entry(path, led, base_sha256=sha, word=word, type=typ, origin=origin, decided_by=by, evidence=ev, role_frame=rf, key='k%d' % i)
    return path, led


def keys_without_layer(a):
    return {k: v for k, v in a.items() if k not in ('layer', 'layer_status')}


H = ['layer_human']
G = ['hearst@doc:abc']


# ---------------------------------------------------------------------------------------------------------------- the table of 12.19
def test_no_placement_is_none_and_the_layer_is_not_opened(tmp_path):
    a = PL.apply(base_answer('NO_PLACEMENT'), str(tmp_path / 'absent.sqlite'), None)
    assert (a['layer'], a['layer_status']) == ('none', 'BASE_NO_PLACEMENT')


@pytest.mark.parametrize('origin,basis', [('direct', None), ('estimated', 'proximity')])
def test_a_decided_word_is_never_changed_by_the_layer(tmp_path, origin, basis):
    path, _ = make_layer(tmp_path, [('テスト語', 'PLANT', 'layer_human', H, {}, None)])
    base = base_answer('DECIDED', ['ARTIFACT'])
    base['origin'], base['estimate_basis'], base['constructed'] = origin, basis, origin == 'estimated'
    a = PL.apply(base, path, BASE)
    assert (a['layer'], a['layer_status']) == ('base', 'BASE_DECIDED')
    assert keys_without_layer(a) == base and list(a)[-2:] == ['layer', 'layer_status']
    assert json.dumps(keys_without_layer(a)) == json.dumps(base)             # byte for byte except the two keys


def test_a_layer_that_cannot_open_is_typed_and_the_base_stays(tmp_path, monkeypatch):
    base = base_answer('UNPLACED')
    status = lambda spec: PL.apply(base, spec, BASE)['layer_status']
    assert status(str(tmp_path / 'absent.sqlite')) == 'LAYER_UNAVAILABLE:MISSING'
    assert status('dom') == 'LAYER_UNAVAILABLE:ROOT_UNSET'
    assert status('bad name!') == 'LAYER_UNAVAILABLE:BAD_NAME'
    junk = tmp_path / 'junk.sqlite'
    junk.write_bytes(b'not a database')
    assert status(str(junk)) == 'LAYER_UNAVAILABLE:UNREADABLE'
    path, _ = make_layer(tmp_path, [('テスト語', 'ARTIFACT', 'layer_human', H, {}, None)], sha='another-base')
    assert status(path) == 'LAYER_UNAVAILABLE:BASE_MISMATCH'
    monkeypatch.setenv(PL.ENV_ROOT, str(tmp_path))
    a = PL.apply(base, 'absent-name', BASE)
    assert a['layer_status'] == 'LAYER_UNAVAILABLE:MISSING' and keys_without_layer(a) == base and a['layer'] == 'base'


def test_no_entry_conflict_and_estimated_leave_the_base(tmp_path):
    path, _ = make_layer(tmp_path, [('二重', 'ARTIFACT', 'layer_human', H, {}, None), ('二重', 'PLACE', 'layer_confirmed', G, {}, None),
                                    ('推定のみ', 'ARTIFACT', 'layer_estimated', ['gen_definition'], {}, None)])
    for term, status in (('無い語', 'LAYER_HAS_NO_ENTRY'), ('二重', 'LAYER_CONFLICT'), ('推定のみ', 'LAYER_ESTIMATED_NOT_USED')):
        base = base_answer('UNPLACED', term=term)
        a = PL.apply(base, path, BASE)
        assert (a['layer'], a['layer_status']) == ('base', status) and keys_without_layer(a) == base


def test_the_same_type_twice_is_not_a_conflict_and_a_human_row_names_the_provenance(tmp_path):
    path, _ = make_layer(tmp_path, [('語', 'ARTIFACT', 'layer_confirmed', G, {'model': 'm'}, None), ('語', 'ARTIFACT', 'layer_human', H, {'human': True}, None)])
    a = PL.apply(base_answer('UNKNOWN', term='語'), path, BASE)
    assert a['layer_status'] == 'LAYER_DIRECT_USED' and a['decided_by'] == H and a['axes']['layer']['entry_ids'] == [1, 2]


@pytest.mark.parametrize('state', ['UNPLACED', 'UNKNOWN'])
def test_an_undecided_word_takes_the_layers_direct_type(tmp_path, state):
    path, led = make_layer(tmp_path, [('テスト語', 'ARTIFACT', 'layer_human', H, {'human': True}, None)])
    base = base_answer(state)
    a = PL.apply(base, path, BASE)
    assert (a['layer'], a['layer_status']) == ('overlay:dom', 'LAYER_DIRECT_USED')
    assert (a['state'], a['origin'], a['top'], a['namespace'], a['estimate_basis'], a['constructed']) == ('DECIDED', 'direct', ['ARTIFACT'], 'N', None, False)
    assert a['candidates'] == [{'type': 'ARTIFACT', 'axes': {'layer': 1}}] and a['neighbors'] == []
    assert a['axes']['layer'] == {'name': 'dom', 'origin': 'layer_human', 'entry_ids': [1], 'ledger_seq': [1], 'evidence': {'human': True}}
    assert list(a)[:24] == ['term', 'namespace', 'state', 'origin', 'estimate_basis', 'constructed', 'top', 'candidates', 'axes', 'neighbors', 'seen_in_material', 'context', 'placement',
                            'decided_by', 'generated', 'generated_definition', 'spelling', 'frame_generated', 'generated_frame', 'frame_status', 'frame',
                            'role_frame_status', 'role_frame', 'role_frame_unconfirmed'] and list(a)[24:] == ['layer', 'layer_status']
    assert a['frame_status'] == 'NOT_PREDICATE' and a['role_frame_status'] == 'NO_ROLE_FRAME'
    assert R._placement_answer_problems(a) == [] and R.placement_type(a) == ('ARTIFACT', None)


def test_the_contract_origin_of_an_answer_is_never_a_layer_origin(tmp_path):
    path, _ = make_layer(tmp_path, [('テスト語', 'ARTIFACT', 'layer_confirmed', G, {}, None)])
    a = PL.apply(base_answer('UNPLACED'), path, BASE)
    assert a['origin'] == 'direct' and 'layer_confirmed' not in json.dumps({k: v for k, v in a.items() if k not in ('axes',)})


def test_a_multiple_word_takes_the_layers_type_only_among_its_candidates(tmp_path):
    path, _ = make_layer(tmp_path, [('内', 'PLACE', 'layer_human', H, {}, None), ('外', 'PLANT', 'layer_human', H, {}, None)])
    a = PL.apply(base_answer('MULTIPLE', ['ARTIFACT', 'PLACE'], term='内'), path, BASE)
    assert (a['state'], a['top'], a['layer'], a['layer_status']) == ('DECIDED', ['PLACE'], 'overlay:dom', 'LAYER_DIRECT_USED')
    base = base_answer('MULTIPLE', ['ARTIFACT', 'PLACE'], term='外')
    b = PL.apply(base, path, BASE)
    assert (b['layer'], b['layer_status']) == ('base', 'LAYER_TYPE_NOT_AMONG_CANDIDATES') and keys_without_layer(b) == base


def test_a_confirmed_row_that_a_generated_definition_decided_is_not_read_by_the_reader(tmp_path):
    path, _ = make_layer(tmp_path, [('語', 'ARTIFACT', 'layer_confirmed', ['gen_definition', 'hearst@doc:abc'], {}, None),
                                    ('人語', 'ARTIFACT', 'layer_human', H, {}, None), ('文書語', 'ARTIFACT', 'layer_confirmed', G, {}, None)])
    a = PL.apply(base_answer('UNPLACED', term='語'), path, BASE)
    assert a['generated'] is True and a['generated_definition'] is True                  # decided_by is decide_word's `by`, gen_definition kept (J4)
    assert R._placement_answer_problems(a) == [] and R.placement_type(a) == (None, 'PLACEMENT_DIRECT_VIA_GENERATED')
    assert R.placement_type(PL.apply(base_answer('UNPLACED', term='人語'), path, BASE)) == ('ARTIFACT', None)
    assert R.placement_type(PL.apply(base_answer('UNPLACED', term='文書語'), path, BASE)) == ('ARTIFACT', None)


def test_a_predicate_row_has_a_not_confirmed_frame_and_a_role_frame_checked_against_its_documents(tmp_path):
    frame = {'を': [{'role': 'patient', 'types': ['ARTIFACT']}], 'が': [{'role': 'agent', 'types': ['PERSON']}]}
    rows = [['role_distribution', 'doc:abc', 'が|PERSON', 12, 30], ['role_distribution', 'doc:abc', 'を|ARTIFACT', 14, 30]]
    path, _ = make_layer(tmp_path, [('述語する', 'P_COMMUNICATE', 'layer_confirmed', ['gen_frame', 'role_distribution@doc:abc'], {'doc_rows': rows}, frame),
                                    ('枠なしする', 'P_ACT', 'layer_human', H, {}, None)])
    a = PL.apply(base_answer('UNPLACED', term='述語する'), path, BASE)
    assert (a['namespace'], a['top'], a['frame_status'], a['frame'], a['generated'], a['generated_frame']) == ('P', ['P_COMMUNICATE'], 'NOT_CONFIRMED', None, True, True)
    cfg = BASE.cfg
    checked = ct.role_frame_check(frame, [tuple(r) for r in rows], cfg)
    assert a['role_frame_status'] == checked['status'] and (a['role_frame'] or None) == (checked['confirmed'] if checked['status'] == 'CONFIRMED' else None)
    assert R._placement_answer_problems(a) == [] and R.placement_type(a) == ('P_COMMUNICATE', None)
    b = PL.apply(base_answer('UNPLACED', term='枠なしする'), path, BASE)
    assert b['role_frame_status'] == 'NO_ROLE_FRAME' and b['frame_status'] == 'NOT_CONFIRMED'
    c = PL.apply(base_answer('UNPLACED', term='述語する', with_role_frame=False), path, BASE)
    assert 'role_frame_status' not in c                                                     # a base answer without the role-frame keys gets none


# ---------------------------------------------------------------------------------------------------------------- writing (K294) and the file
def test_write_entry_names_the_ledger_row_first_and_refuses_a_foreign_base_without_touching_either(tmp_path):
    path, led = make_layer(tmp_path, [('語', 'ARTIFACT', 'layer_human', H, {}, None)])
    before = len(led.entries())
    with pytest.raises(PL.LayerError) as e:
        PL.write_entry(path, led, base_sha256='other', word='別', type='ARTIFACT', origin='layer_human', decided_by=H, evidence={}, role_frame=None, key='kx')
    assert e.value.type == 'LAYER_BASE_MISMATCH' and len(led.entries()) == before
    assert PL.open_layer(path)[0].all_entries().__len__() == 1
    row = PL.open_layer(path)[0].entries('語')[0]
    p = [x for x in led.entries() if x['seq'] == row['ledger_seq']][0]
    assert p['type'] == 'promoted_to_layer' and (p['word'], p['declared_type'], p['origin'], p['layer_name']) == ('語', 'ARTIFACT', 'layer_human', 'dom') and row['ledger_store_id'] == led.store_id


@pytest.mark.parametrize('kw,err', [({'origin': 'direct'}, 'BAD_ORIGIN'), ({'type': 'NOT_A_TYPE'}, 'BAD_TYPE'), ({'decided_by': []}, 'DIRECT_WITHOUT_DECIDED_BY'), ({'word': ' '}, 'EMPTY_WORD')])
def test_write_entry_refuses_a_malformed_row(tmp_path, kw, err):
    led = TestimonyLedger(tmp_path / 'l.jsonl')
    args = dict(base_sha256=SHA, word='語', type='ARTIFACT', origin='layer_human', decided_by=H, evidence={}, role_frame=None, key='k')
    args.update(kw)
    with pytest.raises(PL.LayerError) as e:
        PL.write_entry(str(tmp_path / 'x.sqlite'), led, **args)
    assert e.value.type == err and len(led.entries()) == 1                              # only the header: nothing was appended


def test_the_layer_is_append_only(tmp_path):
    src = Path(PL.__file__).read_text(encoding='utf-8').upper()
    assert 'UPDATE ' not in src.replace('# UPDATE', '') and 'DELETE ' not in src
    path, led = make_layer(tmp_path, [('一', 'ARTIFACT', 'layer_human', H, {}, None)])
    first = sqlite3.connect(path).execute('SELECT * FROM entries').fetchall()
    PL.write_entry(path, led, base_sha256=SHA, word='二', type='PLACE', origin='layer_human', decided_by=H, evidence={}, role_frame=None, key='k2')
    after = sqlite3.connect(path).execute('SELECT * FROM entries').fetchall()
    assert after[:1] == first and len(after) == 2


def test_names_resolve_under_the_root_only(tmp_path, monkeypatch):
    assert PL.resolve('dom')[2] == 'ROOT_UNSET'
    monkeypatch.setenv(PL.ENV_ROOT, str(tmp_path))
    assert PL.resolve('dom') == (str(tmp_path / 'dom.sqlite'), 'dom', None)
    assert PL.resolve(str(tmp_path / 'x.sqlite'))[1] == 'x' and PL.resolve('../x')[1] == 'x' and PL.resolve('a b')[2] == 'BAD_NAME'
    monkeypatch.setenv(PL.ENV_LAYER, '')
    assert PL.spec_from_env() is None                                                       # an empty variable is unset


def test_growth_counts_the_words_and_checks_the_chain(tmp_path):
    path, led = make_layer(tmp_path, [('甲', 'ARTIFACT', 'layer_confirmed', G, {}, None), ('乙', 'ARTIFACT', 'layer_human', H, {}, None), ('丙', 'ARTIFACT', 'layer_estimated', ['gen_definition'], {}, None),
                                      ('丁', 'ARTIFACT', 'layer_human', H, {}, None), ('丁', 'PLACE', 'layer_human', H, {}, None)])
    g = PL.growth(path, led, SHA, True)
    assert g['words'] == {'direct': 1, 'human': 1, 'estimated': 1, 'conflict': 1} and g['rows'] == 5 and g['last_grown']
    assert g['ledger']['chain_ok'] is True and g['ledger']['promoted_to_layer'] == 5 and [x['word'] for x in g['list']] == ['丁', '丙', '乙', '甲']
    assert PL.growth(path, led, 'another')['layer_status'] == 'LAYER_UNAVAILABLE:BASE_MISMATCH'
    other = TestimonyLedger(tmp_path / 'other.jsonl')
    assert PL.growth(path, other, SHA)['ledger']['chain_ok'] is False                       # a ledger that does not hold the rows


# ---------------------------------------------------------------------------------------------------------------- with the real base (r9, read only)
def test_without_a_layer_the_answer_has_no_new_key_and_an_empty_variable_is_the_same(r9, monkeypatch):
    words = ['猫', 'ディレイラー', 'スプロケット', 'アウターケーシング', '午前', '客']
    plain = {w: json.dumps(CP.query(w, placement=r9), ensure_ascii=False) for w in words}
    monkeypatch.setenv(PL.ENV_LAYER, '')
    for w in words:
        assert json.dumps(CP.query(w, placement=r9), ensure_ascii=False) == plain[w] and 'layer' not in json.loads(plain[w])
    monkeypatch.delenv(PL.ENV_LAYER)
    assert {w: json.dumps(CP.query(w, placement=r9, layer=False), ensure_ascii=False) for w in words} == plain


def test_with_a_layer_the_base_part_is_byte_identical_and_two_keys_are_added(r9, tmp_path, monkeypatch):
    base_sha = CP._open(r9)[0].sha
    path, _ = make_layer(tmp_path, [('ディレイラー', 'ARTIFACT', 'layer_human', H, {}, None), ('猫', 'PLANT', 'layer_human', H, {}, None)], sha=base_sha)
    for w in ('猫', 'スプロケット', 'ディレイラー'):
        plain = CP.query(w, placement=r9)
        a = CP.query(w, placement=r9, layer=path)
        if w == 'ディレイラー':
            assert plain['state'] in ('UNPLACED', 'UNKNOWN', 'MULTIPLE') and (a['state'], a['top'], a['layer_status']) == ('DECIDED', ['ARTIFACT'], 'LAYER_DIRECT_USED')
            assert R._placement_answer_problems(a) == [] and R.placement_type(a) == ('ARTIFACT', None)
        else:
            assert len(a) == len(plain) + 2 and list(a)[-2:] == ['layer', 'layer_status']
            assert json.dumps({k: v for k, v in a.items() if k not in ('layer', 'layer_status')}) == json.dumps(plain)
    assert CP.query('猫', placement=r9, layer=path)['layer_status'] == 'BASE_DECIDED'
    monkeypatch.setenv(PL.ENV_LAYER, path)                                                    # the variable reaches query (what the reader's CoarseQuery relies on)
    assert CP.query('ディレイラー', placement=r9)['layer_status'] == 'LAYER_DIRECT_USED'
    assert 'layer' not in CP.query('ディレイラー', placement=r9, layer=False)                 # the layer's own growth never sees itself


def test_a_layer_made_on_another_base_does_not_answer(r9, tmp_path):
    path, _ = make_layer(tmp_path, [('ディレイラー', 'ARTIFACT', 'layer_human', H, {}, None)], sha='not-r9')
    a = CP.query('ディレイラー', placement=r9, layer=path)
    assert a['layer_status'] == 'LAYER_UNAVAILABLE:BASE_MISMATCH' and a['state'] == CP.query('ディレイラー', placement=r9)['state']
