"""W16-t8 (K680, docs/COARSE_PLACEMENT.md 12.21): a human's confirmation row acts ABOVE the base answer; every other layer row stays under K290.

Hand-made base answers (no placement needed), the rows written the only way there is (`write_entry` + a ledger)."""
import json
from types import SimpleNamespace

import pytest

from verantyx import coarse_types as ct
from verantyx import placement_layer as PL
from verantyx import semantic_reader as R
from verantyx.testimony_ledger import TestimonyLedger

SHA = 'sha-of-the-base'
BASE = SimpleNamespace(sha=SHA, cfg=dict(ct.DEFAULT_CONFIG))


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    for k in (PL.ENV_LAYER, PL.ENV_ROOT):
        monkeypatch.delenv(k, raising=False)


def base_answer(state, top=(), term='テスト語', origin=None, decided_by=('seed',), with_role_frame=True):
    top = list(top)
    direct = state in ('DECIDED', 'MULTIPLE')
    origin = origin or ('direct' if direct else None)
    r = {'term': term, 'namespace': None if state in ('UNPLACED', 'UNKNOWN', 'NO_PLACEMENT') else 'N', 'state': state, 'origin': origin,
         'estimate_basis': 'generated' if origin == 'estimated' else None, 'constructed': origin == 'estimated', 'top': top,
         'candidates': [{'type': t, 'axes': {'seed': 1}} for t in top], 'axes': {'seed': {'counts': {t: 1 for t in top}}}, 'neighbors': [], 'seen_in_material': state != 'UNKNOWN',
         'context': {'role': None, 'predicate': None}, 'placement': {'path': '/p', 'content_sha256': SHA, 'reason': None}}
    if direct or origin == 'estimated':
        r.update({'decided_by': list(decided_by), 'generated': False, 'generated_definition': False})
    r['spelling'] = {'query': term, 'normalized': term, 'normalization': 'NFKC', 'kana': 'DISTINCT', 'kana_variant': None, 'why': None}
    r['frame_generated'] = None
    r['generated_frame'] = False
    r['frame_status'] = 'CONFIRMED' if state == 'DECIDED' and top and top[0].startswith('P_') else 'NO_ANSWER'
    r['frame'] = {'が': ['PERSON']} if r['frame_status'] == 'CONFIRMED' else None
    if with_role_frame:
        r.update({'role_frame_status': 'NO_ROLE_FRAME', 'role_frame': None, 'role_frame_unconfirmed': None})
    return r


class Layer:
    def __init__(self, tmp_path, name='dom'):
        self.led = TestimonyLedger(tmp_path / 'ledger.jsonl')
        self.path = str(tmp_path / (name + '.sqlite'))
        self.n = 0

    def human(self, word, type_, kind='type', frame=None, undoes=None, cid=None):
        self.n += 1
        cid = cid or '%016x' % self.n                               # r3: a confirm id in the W10-f04 form (a test-input change; the old default 'c<n>' is not one)
        ev = {'kind': kind, 'confirm_id': cid, 'by': 'tester', 'reason': None, 'human': True}
        if frame:
            ev['frame'] = frame
        if undoes:
            ev['undoes'] = undoes
        PL.write_entry(self.path, self.led, base_sha256=SHA, word=word, type=type_, origin='layer_human', decided_by=['human:' + cid], evidence=ev, role_frame=None, key='human:' + cid)
        return cid

    def raw(self, word, type_, origin, by, evidence=None, role_frame=None):
        self.n += 1
        PL.write_entry(self.path, self.led, base_sha256=SHA, word=word, type=type_, origin=origin, decided_by=by, evidence=evidence or {}, role_frame=role_frame, key='k%d' % self.n)


def without_layer_keys(a):
    return {k: v for k, v in a.items() if k not in ('layer', 'layer_status')}


@pytest.mark.parametrize('origin,by', [('direct', ('seed',)), ('estimated', ('gen_frame',))])
def test_a_human_type_overrides_a_decided_base_and_says_so(tmp_path, origin, by):
    L = Layer(tmp_path)
    cid = L.human('テスト語', 'PLACE')
    base = base_answer('DECIDED', ['GROUP_ORG'], origin=origin, decided_by=by)
    a = PL.apply(base, L.path, BASE)
    assert (a['layer_status'], a['layer'], a['state'], a['origin'], a['top']) == ('HUMAN_CONFIRMED_USED', 'overlay:dom', 'DECIDED', 'direct', ['PLACE'])
    assert a['decided_by'] == ['human:' + cid] and a['generated'] is False and a['generated_definition'] is False and a['generated_frame'] is False
    assert a['axes']['layer']['overrode_base'] == {'state': 'DECIDED', 'top': ['GROUP_ORG'], 'origin': origin, 'decided_by': list(by)}
    assert a['axes']['layer']['confirm_ids'] == [cid] and a['axes']['layer']['origin'] == 'layer_human'
    assert list(a)[-2:] == ['layer', 'layer_status']
    assert R._placement_answer_problems(a) == [] and R.placement_type(a) == ('PLACE', None)


@pytest.mark.parametrize('state,top', [('MULTIPLE', ['GROUP_ORG', 'PLACE']), ('UNPLACED', []), ('UNKNOWN', [])])
def test_a_human_type_decides_an_undecided_word_even_outside_the_candidates(tmp_path, state, top):
    L = Layer(tmp_path)
    L.human('テスト語', 'ARTIFACT')                                    # not among the MULTIPLE candidates: K680 is above the base
    a = PL.apply(base_answer(state, top), L.path, BASE)
    assert a['layer_status'] == 'HUMAN_CONFIRMED_USED' and a['top'] == ['ARTIFACT']
    assert a['axes']['layer']['overrode_base']['state'] == state
    assert R.placement_type(a) == ('ARTIFACT', None)


def test_two_human_types_are_a_tie_and_the_base_stays(tmp_path):
    L = Layer(tmp_path)
    L.human('テスト語', 'PLACE')
    L.human('テスト語', 'ARTIFACT')
    base = base_answer('DECIDED', ['GROUP_ORG'])
    a = PL.apply(base, L.path, BASE)
    assert a['layer_status'] == 'HUMAN_CONFLICT' and without_layer_keys(a) == base
    a2 = PL.apply(base_answer('UNPLACED'), L.path, BASE)
    assert a2['layer_status'] == 'HUMAN_CONFLICT' and a2['state'] == 'UNPLACED'


def test_two_rows_of_the_same_human_type_are_not_a_tie(tmp_path):
    L = Layer(tmp_path)
    c1, c2 = L.human('テスト語', 'PLACE'), L.human('テスト語', 'PLACE')
    a = PL.apply(base_answer('UNPLACED'), L.path, BASE)
    assert a['layer_status'] == 'HUMAN_CONFIRMED_USED' and a['decided_by'] == ['human:' + c1, 'human:' + c2]


def test_undo_gives_back_the_k290_answer_byte_for_byte(tmp_path):
    L = Layer(tmp_path)
    c = L.human('テスト語', 'PLACE')
    L.human('テスト語', 'PLACE', kind='undo', undoes=c)
    for base in (base_answer('DECIDED', ['GROUP_ORG']), base_answer('MULTIPLE', ['GROUP_ORG', 'PLACE']), base_answer('UNPLACED')):
        a = PL.apply(base, L.path, BASE)
        assert without_layer_keys(a) == base
        assert a['layer_status'] == ('BASE_DECIDED' if base['state'] == 'DECIDED' else 'LAYER_HAS_NO_ENTRY' if base['state'] == 'UNPLACED' else 'LAYER_HAS_NO_ENTRY')
        assert list(a)[-2:] == ['layer', 'layer_status']


def test_undo_leaves_the_other_rows_of_the_word_under_k290(tmp_path):
    L = Layer(tmp_path)
    L.raw('テスト語', 'PLANT', 'layer_confirmed', ['hearst@doc:abc'])
    c = L.human('テスト語', 'PLACE')
    assert PL.apply(base_answer('UNPLACED'), L.path, BASE)['top'] == ['PLACE']
    L.human('テスト語', 'PLACE', kind='undo', undoes=c)
    a = PL.apply(base_answer('UNPLACED'), L.path, BASE)
    assert (a['layer_status'], a['top']) == ('LAYER_DIRECT_USED', ['PLANT'])
    assert PL.apply(base_answer('DECIDED', ['GROUP_ORG']), L.path, BASE)['layer_status'] == 'BASE_DECIDED'


def test_a_layer_human_row_without_a_confirm_id_stays_under_k290(tmp_path):
    L = Layer(tmp_path)
    L.raw('テスト語', 'PLACE', 'layer_human', ['layer_human'], evidence={'ledger_key': 'x'})
    base = base_answer('DECIDED', ['GROUP_ORG'])
    a = PL.apply(base, L.path, BASE)
    assert a['layer_status'] == 'BASE_DECIDED' and without_layer_keys(a) == base
    assert json.dumps(without_layer_keys(a)) == json.dumps(base)
    assert PL.apply(base_answer('UNPLACED'), L.path, BASE)['layer_status'] == 'LAYER_DIRECT_USED'


def test_the_other_origins_with_a_confirm_id_shaped_evidence_are_not_confirmations(tmp_path):
    L = Layer(tmp_path)
    L.raw('テスト語', 'PLACE', 'layer_confirmed', ['human:c9'], evidence={'kind': 'type', 'confirm_id': 'c9'})
    L.raw('語2', 'PLACE', 'layer_human', ['layer_human'], evidence={'kind': 'type', 'confirm_id': 'c9'})        # decided_by is not human:<id>
    assert PL.apply(base_answer('DECIDED', ['GROUP_ORG']), L.path, BASE)['layer_status'] == 'BASE_DECIDED'
    assert PL.apply(base_answer('DECIDED', ['GROUP_ORG'], term='語2'), L.path, BASE)['layer_status'] == 'BASE_DECIDED'


def test_with_no_confirmation_row_a_layer_changes_nothing_for_a_decided_word(tmp_path):
    L = Layer(tmp_path)
    L.raw('別の語', 'PLANT', 'layer_confirmed', ['hearst@doc:abc'])
    base = base_answer('DECIDED', ['PLACE'])
    a = PL.apply(base, L.path, BASE)
    assert (a['layer'], a['layer_status']) == ('base', 'BASE_DECIDED') and without_layer_keys(a) == base


def test_a_layer_that_cannot_open_keeps_a_decided_word_BASE_DECIDED(tmp_path):
    base = base_answer('DECIDED', ['PLACE'])
    for spec in (str(tmp_path / 'absent.sqlite'), 'dom', 'bad name!'):
        a = PL.apply(base, spec, BASE)
        assert (a['layer'], a['layer_status']) == ('base', 'BASE_DECIDED') and without_layer_keys(a) == base
    L = Layer(tmp_path)
    L.human('テスト語', 'PLACE')
    other = SimpleNamespace(sha='another', cfg=BASE.cfg)
    assert PL.apply(base, L.path, other)['layer_status'] == 'BASE_DECIDED'          # a layer made on another base: not used, not typed for a DECIDED word (as before)


def test_a_human_predicate_answer_has_no_twelve_ten_frame_and_a_frame_row_makes_a_role_frame(tmp_path):
    # r3 (監査役の裁定 2026-10-06 00:24): a human `set` changes the type only; the base's 12.10 frame and role frame stay.  A frame row overlays the role frame (the base's entry has backed_by: J15, the reader refuses it).
    L = Layer(tmp_path)
    L.human('移動する', 'P_MOVE')
    base = base_answer('DECIDED', ['P_MOVE'], term='移動する', decided_by=('gen_frame',))
    base['role_frame_status'], base['role_frame'] = 'CONFIRMED', {'を': [{'role': 'patient', 'types': ['ARTIFACT'], 'backed_by': ['x']}]}
    a = PL.apply(base, L.path, BASE)
    assert (a['frame_status'], a['frame']) == ('CONFIRMED', {'が': ['PERSON']})                  # the base's 12.10 frame is kept, with gen_frame after the human's id
    assert a['decided_by'] == ['human:%016x' % 1, 'gen_frame']
    assert (a['role_frame_status'], a['role_frame']) == ('CONFIRMED', base['role_frame'])        # the base's role frame (with backed_by) is carried over byte for byte
    assert R._placement_answer_problems(a) == [] and R.predicate_role_frame(a)[0] is None and R.predicate_role_frame(a)[1].startswith('ROLE_FRAME_INVALID')
    L.human('移動する', 'P_MOVE', kind='frame', frame={'particle': 'へ', 'role': 'goal', 'types': ['PLACE']})
    L.human('移動する', 'P_MOVE', kind='frame', frame={'particle': 'が', 'role': 'agent', 'types': ['PERSON']})
    L.human('移動する', 'P_MOVE', kind='frame', frame={'particle': 'が', 'role': 'agent', 'types': ['GROUP_ORG']})
    a = PL.apply(base, L.path, BASE)
    assert a['role_frame_status'] == 'CONFIRMED' and a['axes']['layer']['frame_confirm_ids'] == ['%016x' % n for n in (2, 3, 4)]
    assert a['role_frame'] == {'が': [{'role': 'agent', 'types': ['GROUP_ORG', 'PERSON']}], 'を': [{'role': 'patient', 'types': ['ARTIFACT'], 'backed_by': ['x']}],
                               'へ': [{'role': 'goal', 'types': ['PLACE']}]}
    assert a['frame'] == {'が': ['PERSON']} and R.predicate_frame(a) == ('confirmed', {'が': frozenset({'PERSON'})})
    assert R.placement_type(a) == ('P_MOVE', None)
    # J15 (not fixed here): the base's backed_by entry stays in the frame, so the reader still refuses the role frame of this predicate
    assert R.predicate_role_frame(a)[0] is None


def test_a_noun_answer_and_a_nonpredicate_have_no_role_frame(tmp_path):
    L = Layer(tmp_path)
    L.human('テスト語', 'PLACE')
    a = PL.apply(base_answer('UNPLACED'), L.path, BASE)
    assert (a['frame_status'], a['role_frame_status']) == ('NOT_PREDICATE', 'NO_ROLE_FRAME')
    a2 = PL.apply(base_answer('UNPLACED', with_role_frame=False), L.path, BASE)
    assert 'role_frame_status' not in a2


def test_a_predicate_with_two_human_types_is_a_tie_whatever_its_frame_rows(tmp_path):
    L = Layer(tmp_path)
    L.human('述語', 'P_MOVE')
    L.human('述語', 'P_MOVE', kind='frame', frame={'particle': 'へ', 'role': 'goal', 'types': ['PLACE']})
    L.human('述語', 'P_ACT')
    a = PL.apply(base_answer('UNPLACED', term='述語'), L.path, BASE)
    assert a['layer_status'] == 'HUMAN_CONFLICT'                                           # two types


def test_a_frame_row_alone_does_not_make_an_answer(tmp_path):
    L = Layer(tmp_path)
    L.human('移動する', 'P_MOVE', kind='frame', frame={'particle': 'へ', 'role': 'goal', 'types': ['PLACE']})
    base = base_answer('DECIDED', ['P_MOVE'], term='移動する', decided_by=('gen_frame',))
    a = PL.apply(base, L.path, BASE)
    assert a['layer_status'] == 'BASE_DECIDED' and without_layer_keys(a) == base
    a = PL.apply(base_answer('UNPLACED', term='移動する'), L.path, BASE)
    assert a['layer_status'] == 'LAYER_HAS_NO_ENTRY'


def test_fold_leaves_out_undo_undone_and_frame_rows(tmp_path):
    L = Layer(tmp_path)
    c1 = L.human('語', 'PLACE')
    L.human('語', 'PLACE', kind='undo', undoes=c1)
    L.human('語', 'PLACE', kind='frame', frame={'particle': 'へ', 'role': 'goal', 'types': ['PLACE']})
    layer, why = PL.open_layer(L.path, SHA)
    assert why is None
    assert PL.fold(layer.entries('語')) == {'direct': {}, 'estimated': {}}
    c4 = L.human('語', 'ARTIFACT')
    layer, _ = PL.open_layer(L.path, SHA)
    f = PL.fold(layer.entries('語'))
    assert list(f['direct']) == ['ARTIFACT'] and [e['evidence']['confirm_id'] for e in f['direct']['ARTIFACT']] == [c4]


def test_fold_with_no_confirmation_row_is_what_it_was(tmp_path):
    L = Layer(tmp_path)
    L.raw('語', 'PLANT', 'layer_confirmed', ['hearst@doc:abc'])
    L.raw('語', 'PLANT', 'layer_human', ['layer_human'])
    L.raw('語', 'ARTIFACT', 'layer_estimated', ['x'])
    layer, _ = PL.open_layer(L.path, SHA)
    rows = layer.entries('語')
    f = PL.fold(rows)
    assert list(f['direct']) == ['PLANT'] and len(f['direct']['PLANT']) == 2 and list(f['estimated']) == ['ARTIFACT']


def test_growth_does_not_count_a_word_with_only_undone_or_frame_rows(tmp_path):
    L = Layer(tmp_path)
    c = L.human('語1', 'PLACE')
    L.human('語1', 'PLACE', kind='undo', undoes=c)
    L.human('語2', 'P_MOVE', kind='frame', frame={'particle': 'へ', 'role': 'goal', 'types': ['PLACE']})
    L.human('語3', 'PLACE')
    g = PL.growth(L.path, L.led, SHA, with_list=True)
    assert g['words'] == {'direct': 0, 'human': 1, 'estimated': 0, 'conflict': 0}
    assert g['ledger']['chain_ok'] is True and g['ledger']['promoted_to_layer'] == 4


def test_the_statuses_name_the_two_new_ones():
    assert PL.STATUSES[-2:] == ('HUMAN_CONFIRMED_USED', 'HUMAN_CONFLICT')


def test_a_no_placement_base_never_opens_the_layer(tmp_path):
    L = Layer(tmp_path)
    L.human('テスト語', 'PLACE')
    a = PL.apply(base_answer('NO_PLACEMENT'), L.path, BASE)
    assert (a['layer'], a['layer_status']) == ('none', 'BASE_NO_PLACEMENT')


# ---- r3 (12.21.7: the auditor's ruling of 2026-10-06 00:24): `set` changes the TYPE only, the base's frames stay; a row without a real confirm id is not a human's confirmation -------------------
import copy


def hid(n):
    """A confirm id in the W10-f04 form (16 lowercase hex digits)."""
    return '%016x' % n


def predicate_base(frame_status='CONFIRMED', role_status='CONFIRMED', top=('P_MOVE',), term='移動する'):
    b = base_answer('DECIDED', list(top), term=term, decided_by=('gen_frame', 'role_distribution@x'))
    b['generated'], b['generated_frame'] = True, True
    b['frame_status'] = frame_status
    if frame_status == 'CONFIRMED':
        b['frame'], b['frame_unconfirmed'] = {'へ': ['PLACE']}, {'が': ['PERSON']}
    elif frame_status == 'NOT_CONFIRMED':
        b['frame'], b['frame_disagreement'] = None, {'が': {'generated': ['PERSON'], 'distribution': {'x': ['ARTIFACT']}}}
    else:
        b['frame'] = None
    if role_status == 'CONFIRMED':
        b['role_frame_status'], b['role_frame_unconfirmed'] = 'CONFIRMED', {'が': [{'role': 'agent', 'types': ['PERSON'], 'why': 'NOT_BACKED'}]}
        b['role_frame'] = {'へ': [{'role': 'goal', 'types': ['PLACE'], 'backed_by': ['role_distribution@x']}]}
    else:
        b['role_frame_status'], b['role_frame'], b['role_frame_unconfirmed'] = role_status, None, None
    return b


def test_r3_a_set_alone_keeps_the_twelve_ten_frame_and_the_role_frame_of_the_base(tmp_path):
    L = Layer(tmp_path)
    cid = L.human('移動する', 'P_MOVE', cid=hid(1))
    base = predicate_base()
    a = PL.apply(base, L.path, BASE)
    for k in ('frame_status', 'frame', 'frame_unconfirmed', 'role_frame_status', 'role_frame', 'role_frame_unconfirmed'):
        assert json.dumps(a[k], sort_keys=True, ensure_ascii=False) == json.dumps(base[k], sort_keys=True, ensure_ascii=False), k
    assert a['decided_by'] == ['human:' + cid, 'gen_frame'] and a['generated_frame'] is True and a['generated'] is True and a['generated_definition'] is False
    assert a['layer_status'] == 'HUMAN_CONFIRMED_USED' and R._placement_answer_problems(a) == [] and R.predicate_frame(a)[0] == 'confirmed'
    assert a['axes']['layer']['base_frame'] == {'frame_status': 'CONFIRMED', 'role_frame_status': 'CONFIRMED'}


def test_r3_a_set_of_another_predicate_type_keeps_the_frame_the_base_confirmed(tmp_path):
    L = Layer(tmp_path)
    L.human('移動する', 'P_ACT', cid=hid(1))
    a = PL.apply(predicate_base(), L.path, BASE)
    assert a['top'] == ['P_ACT'] and a['frame_status'] == 'CONFIRMED' and a['frame'] == {'へ': ['PLACE']} and a['decided_by'][-1] == 'gen_frame'


@pytest.mark.parametrize('fs,want_fs,want_by_tail', [('NOT_CONFIRMED', 'NOT_CONFIRMED', False), ('NO_FRAME_TABLE', 'NO_FRAME_TABLE', False), ('ESTIMATED', 'NOT_CONFIRMED', False), ('NO_ANSWER', 'NOT_CONFIRMED', False)])
def test_r3_a_base_without_a_confirmed_frame_gets_no_gen_frame_from_a_human(tmp_path, fs, want_fs, want_by_tail):
    L = Layer(tmp_path)
    cid = L.human('移動する', 'P_MOVE', cid=hid(1))
    a = PL.apply(predicate_base(frame_status=fs, role_status='NO_ROLE_FRAME'), L.path, BASE)
    assert (a['frame_status'], a['frame']) == (want_fs, None) and a['decided_by'] == ['human:' + cid] and a['generated_frame'] is False
    assert ('frame_disagreement' in a) == (fs == 'NOT_CONFIRMED') and 'frame_unconfirmed' not in a
    assert R._placement_answer_problems(a) == []


def test_r3_a_frame_row_overlays_the_role_frame_and_never_changes_the_twelve_ten_frame(tmp_path):
    L = Layer(tmp_path)
    L.human('移動する', 'P_MOVE', cid=hid(1))
    L.human('移動する', 'P_MOVE', kind='frame', frame={'particle': 'へ', 'role': 'goal', 'types': ['GROUP_ORG']}, cid=hid(2))
    L.human('移動する', 'P_MOVE', kind='frame', frame={'particle': 'が', 'role': 'agent', 'types': ['PERSON']}, cid=hid(3))
    base = predicate_base()
    a = PL.apply(base, L.path, BASE)
    assert a['frame'] == base['frame'] and a['frame_status'] == 'CONFIRMED'                                  # a frame row changes the role frame only
    assert a['role_frame'] == {'が': [{'role': 'agent', 'types': ['PERSON']}], 'へ': [{'role': 'goal', 'types': ['GROUP_ORG', 'PLACE'], 'backed_by': ['role_distribution@x']}]}
    assert a['role_frame_unconfirmed'] == base['role_frame_unconfirmed'] and a['role_frame_status'] == 'CONFIRMED'
    assert base['role_frame'] == {'へ': [{'role': 'goal', 'types': ['PLACE'], 'backed_by': ['role_distribution@x']}]}      # the base answer is not mutated
    # J15 (not fixed): the base's backed_by entry stays, so the reader still refuses the role frame of this predicate
    assert R.predicate_role_frame(a)[0] is None and R.predicate_role_frame(a)[1].startswith('ROLE_FRAME_INVALID')


@pytest.mark.parametrize('role_status', ['NO_ROLE_FRAME', 'ESTIMATED'])
def test_r3_a_frame_row_on_a_base_without_a_confirmed_role_frame_makes_the_human_only_frame(tmp_path, role_status):
    L = Layer(tmp_path)
    L.human('出向く', 'P_MOVE', cid=hid(1))
    L.human('出向く', 'P_MOVE', kind='frame', frame={'particle': 'へ', 'role': 'goal', 'types': ['GROUP_ORG']}, cid=hid(2))
    base = predicate_base(frame_status='ESTIMATED', role_status=role_status, term='出向く')
    a = PL.apply(base, L.path, BASE)
    assert (a['role_frame_status'], a['role_frame']) == ('CONFIRMED', {'へ': [{'role': 'goal', 'types': ['GROUP_ORG']}]}) and a['role_frame_unconfirmed'] == base['role_frame_unconfirmed']
    assert (a['frame_status'], a['frame']) == ('NOT_CONFIRMED', None) and R.predicate_role_frame(a)[0] == 'confirmed'


def test_r3_a_noun_answer_is_what_it_was(tmp_path):
    L = Layer(tmp_path)
    L.human('テスト語', 'PLACE', cid=hid(1))
    a = PL.apply(base_answer('DECIDED', ['GROUP_ORG']), L.path, BASE)
    assert (a['frame_status'], a['frame'], a['role_frame_status'], a['decided_by']) == ('NOT_PREDICATE', None, 'NO_ROLE_FRAME', ['human:' + hid(1)])


def test_r3_rows_that_look_like_a_confirmation_but_are_not_one_stay_estimated(tmp_path):
    L = Layer(tmp_path)
    cid = hid(7)
    ev = {'kind': 'type', 'confirm_id': cid, 'by': 't', 'human': True}
    L.raw('包み語', 'PLACE', 'layer_human', ['human:' + cid], evidence={'from_evidence': ev, 'ledger_key': 'x'})              # `combine`: the evidence is wrapped
    L.raw('形式語', 'PLACE', 'layer_human', ['human:zz'], evidence=dict(ev, confirm_id='zz'))                                     # not a W10-f04 id
    L.raw('取消語', 'PLACE', 'layer_human', ['human:' + hid(8)], evidence={'kind': 'undo', 'confirm_id': hid(8), 'undoes': 'bad'})
    for w in ('包み語', '形式語', '取消語'):
        a = PL.apply(base_answer('UNPLACED', term=w), L.path, BASE)
        assert a['layer_status'] == 'LAYER_ESTIMATED_NOT_USED' and a['state'] == 'UNPLACED', w
        base = base_answer('DECIDED', ['GROUP_ORG'], term=w)
        d = PL.apply(base, L.path, BASE)
        assert d['layer_status'] == 'BASE_DECIDED' and without_layer_keys(d) == base, w
    g = PL.growth(L.path, L.led, SHA, with_list=True)
    assert g['words'] == {'direct': 0, 'human': 0, 'estimated': 3, 'conflict': 0}


def test_r3_an_unbacked_undo_row_cancels_nothing(tmp_path):
    L = Layer(tmp_path)
    c = L.human('語', 'PLACE', cid=hid(1))
    L.raw('語', 'PLACE', 'layer_human', ['human:' + hid(2)], evidence={'from_evidence': {'kind': 'undo', 'confirm_id': hid(2), 'undoes': c}})
    a = PL.apply(base_answer('UNPLACED', term='語'), L.path, BASE)
    assert a['layer_status'] == 'HUMAN_CONFIRMED_USED' and a['top'] == ['PLACE']


def test_r3_a_plain_layer_human_row_of_the_ledger_promote_path_is_as_before(tmp_path):
    L = Layer(tmp_path)
    L.raw('語', 'PLACE', 'layer_human', ['layer_human'], evidence={'ledger_key': 'x'})
    a = PL.apply(base_answer('UNPLACED', term='語'), L.path, BASE)
    assert a['layer_status'] == 'LAYER_DIRECT_USED' and a['decided_by'] == ['layer_human']
