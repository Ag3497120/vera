"""W3-b3: the event cross of a relative clause: the head is a filler of an arm of the main clause and the cross of the relative clause is INSIDE that filler (`Filler.embedded`); the
relation holds `head`. The edge of a connective sentence is a relation of the convention; the `te` and the continuative edges are not (they never enter a `CrossReading`).
Registered in docs/EVENT_CROSS.md ("W3-b3 の追記") and docs/READING_SOUNDNESS.md section 10C before this file was written. Fixture placements only; no real placement is opened.
"""
import copy
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

TREE = Path(__file__).resolve().parent.parent
RS = TREE / 'tests' / 'reading_soundness'
BASE_COMMIT = 'c875ed3'


def _load_by_path(name, path):
    if name in sys.modules: return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, str(path))
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


F = _load_by_path('w3b3_fakes_in_events_test', RS / 'w3b3_fakes.py')
COMMON = _load_by_path('w3b3_common_in_events_test', RS / 'w3b3_common.py')

from tools.bank_score.v2 import b1    # noqa: E402
from verantyx import event_cross as EC    # noqa: E402
from verantyx import observe as OB    # noqa: E402
from verantyx import semantic_read as SR    # noqa: E402

DOCS_EC = (TREE / 'docs' / 'EVENT_CROSS.md').read_text(encoding='utf-8')
REL = '母が弟に話した人を兄が呼んだ。'
CON = '兄が本を読んだので、弟が歌を歌った。'


@pytest.fixture(autouse=True)
def _no_placement_in_the_environment(monkeypatch):
    monkeypatch.delenv('VERA_PLACEMENT', raising=False)
    monkeypatch.delenv('VERA_COARSE_PLACEMENT', raising=False)


def git(*args):
    return subprocess.run(['git', '-C', str(TREE)] + list(args), capture_output=True, check=True).stdout.decode('utf-8')


def _base_ec():
    src = git('show', '%s:verantyx/event_cross.py' % BASE_COMMIT)
    spec = importlib.util.spec_from_loader('verantyx._event_cross_base_w3b3', loader=None)
    mod = importlib.util.module_from_spec(spec)
    mod.__package__ = 'verantyx'
    sys.modules[spec.name] = mod
    exec(compile(src, 'verantyx/event_cross.py@%s' % BASE_COMMIT, 'exec'), mod.__dict__)
    return mod


BEC = _base_ec()


def read(text):
    return SR.read(text, placement=F.FixtureQuery())


def synthetic(clauses, relations):
    return {'schema': EC.SOURCE_SCHEMA, 'lang': 'ja', 'readable': True, 'clauses': clauses, 'relations': relations, 'abstain': None, 'unsupported': [],
            'clause_meta': [{'rule': 'frame', 'span': [0, 1]} for _ in clauses]}


def cl(pred, roles):
    return {'predicate': pred, 'roles': roles, 'polarity': '+', 'tense': 'past', 'modality': None, 'voice': 'active'}


HEAD = {'from_role': 'patient', 'to_role': 'patient'}


def two(head=HEAD, rtype='relative'):
    return synthetic([cl('話す', {'agent': '母', 'patient': '人'}), cl('呼ぶ', {'agent': '兄', 'patient': '人'})], [{'type': rtype, 'from': 0, 'to': 1, 'head': head}])


# ---- the table of the reasons --------------------------------------------------------------------------------------------------------------------------
def test_the_reasons_of_the_docs_are_the_constant_of_the_module():
    import re
    m = re.search(r'<!-- BEGIN table:w3b3_head_reasons -->\n(.*?)<!-- END table:w3b3_head_reasons -->', DOCS_EC, re.S)
    rows = [re.split(r' \| ', l.strip()[1:-1].strip())[0].strip().strip('`') for l in m.group(1).splitlines() if l.startswith('|') and not set(l) <= set('|- ')][1:]
    assert rows == list(EC.RELATION_HEAD_REASONS) and len(rows) == 7


# ---- the cross: embedded ---------------------------------------------------------------------------------------------------------------------------------
def test_a_filler_without_embedded_is_the_bases_bytes_and_embedded_comes_last_when_it_is_there():
    place = EC.PlaceResult(state='NO_PLACEMENT')
    f = EC.Filler('人', '人', 'surface', place, {})
    assert f.embedded is None and list(f.to_dict()) == ['surface', 'head', 'head_basis', 'place', 'flags']
    assert json.dumps(f.to_dict(), ensure_ascii=False) == json.dumps(BEC.Filler('人', '人', 'surface', BEC.PlaceResult(state='NO_PLACEMENT'), {}).to_dict(), ensure_ascii=False)
    cross = EC.build_crosses(read(REL), EC.StubLookup()).crosses[0]
    g = EC.Filler('人', '人', 'surface', place, {}, cross)
    assert list(g.to_dict())[-1] == 'embedded' and g.to_dict()['embedded'] == cross.to_dict()


def test_a_relative_clause_becomes_a_cross_inside_the_filler_of_the_head():
    out = read(REL)
    assert out['readable'] is True and out['relations'][0]['head'] == {'from_role': 'patient', 'to_role': 'patient'}
    crossed = EC.build_crosses(out, EC.StubLookup())
    assert crossed.status == 'CROSSED' and len(crossed.crosses) == 2
    filler = crossed.crosses[1].arms['patient'].fillers[0]
    assert filler.embedded is not None and filler.embedded.index == 0 and filler.embedded.center['predicate'] == '話す'
    assert filler.embedded.arms['patient'].fillers[0].surface == '人' and filler.embedded.arms['patient'].fillers[0].embedded is None     # one level
    assert crossed.crosses[0].arms['patient'].fillers[0].embedded is None                                                               # the relative clause's own cross is the same as before
    d = crossed.to_dict()
    assert list(d['crosses'][1]['arms']['patient']['fillers'][0])[-1] == 'embedded'
    assert d['crosses'][1]['arms']['patient']['fillers'][0]['embedded'] == d['crosses'][0]
    assert d['relations'][0]['head'] == {'from_role': 'patient', 'to_role': 'patient'}
    other = crossed.crosses[1].arms['agent'].fillers[0]
    assert other.embedded is None and 'embedded' not in other.to_dict()


def test_the_counts_and_the_other_arms_do_not_change_because_of_the_embedding():
    out = read(REL)
    stripped = copy.deepcopy(out)
    for r in stripped['relations']: r.pop('head')
    with_head = EC.build_crosses(out, EC.StubLookup())
    without = EC.build_crosses(stripped, EC.StubLookup())
    assert with_head.counts == without.counts and [c.index for c in with_head.crosses] == [0, 1]
    a, b = with_head.to_dict(), without.to_dict()
    for d in (a, b): d.pop('relations')
    del a['crosses'][1]['arms']['patient']['fillers'][0]['embedded']
    assert a == b


def test_an_output_without_head_gives_the_same_bytes_as_the_base_module():
    texts = [r['input'] for r in COMMON.load_data('connective') if r['entry_expect'] == 'read'] + ['兄が本を読んだ。', '兄が来た。']
    n = 0
    for text in texts:
        out = SR.read(text, placement=F.FixtureQuery())
        a = EC.build_crosses(out, EC.StubLookup()).to_dict(); b = BEC.build_crosses(out, BEC.StubLookup()).to_dict()
        assert json.dumps(a, ensure_ascii=False) == json.dumps(b, ensure_ascii=False), text
        n += 1
    assert n >= 20
    for name in ('ROLE_NAMES', 'RELATION_TYPES', 'EXPECTED_TYPES', 'VERDICTS', 'EXTRA_VERDICTS', 'NOT_CHECKED_REASONS', 'CLAUSE_KEYS', 'ENTRY_BASIS_KEYS', 'ENTRY_FLAG_KEYS'):
        assert getattr(EC, name) == getattr(BEC, name), name


def test_read_events_attaches_the_embedded_cross_to_the_output_of_the_entry():
    out = SR.read(REL, placement=F.FixtureQuery())
    ev = EC.attach_events(out, EC.StubLookup())
    assert ev['events']['crosses'][1]['arms']['patient']['fillers'][0]['embedded']['index'] == 0
    assert {k: v for k, v in ev.items() if k != 'events'} == out


# ---- the check of `head` ---------------------------------------------------------------------------------------------------------------------------------
def rejected(out):
    crossed = EC.build_crosses(out, EC.StubLookup())
    assert crossed.status == 'INPUT_REJECTED', crossed.status
    return crossed.abstain['reasons']


def test_a_well_formed_head_is_accepted():
    assert EC.build_crosses(two(), EC.StubLookup()).status == 'CROSSED'
    assert EC._check(two()) == []


@pytest.mark.parametrize('out,why', [
    (two('x'), 'not_a_mapping'),
    (two({'from_role': 'patient', 'to_role': 'patient', 'extra': 1}), 'keys'),
    (two({'from_role': 'patient'}), 'keys'),
    (two(HEAD, 'cause'), 'type_not_relative'),
    (two({'from_role': 'zzz', 'to_role': 'patient'}), 'role_not_in_convention'),
    (two({'from_role': 'patient', 'to_role': 5}), 'role_not_in_convention'),
    (two({'from_role': 'agent', 'to_role': 'patient'}), 'values_differ'),
    (two({'from_role': 'goal', 'to_role': 'patient'}), 'values_differ'),
])
def test_each_way_a_head_can_be_wrong_is_a_typed_rejection(out, why):
    assert 'RELATION_HEAD_NOT_WELL_FORMED:' + why in rejected(out)


def test_two_heads_into_the_same_arm_and_a_nested_head_are_rejected():
    three = synthetic([cl('話す', {'agent': '母', 'patient': '人'}), cl('頼む', {'agent': '姉', 'patient': '人'}), cl('呼ぶ', {'agent': '兄', 'patient': '人'})],
                      [{'type': 'relative', 'from': 0, 'to': 2, 'head': HEAD}, {'type': 'relative', 'from': 1, 'to': 2, 'head': HEAD}])
    assert 'RELATION_HEAD_NOT_WELL_FORMED:duplicate_target' in rejected(three)
    nested = synthetic([cl('話す', {'agent': '母', 'patient': '人'}), cl('頼む', {'agent': '姉', 'patient': '人'}), cl('呼ぶ', {'agent': '兄', 'patient': '人'})],
                       [{'type': 'relative', 'from': 0, 'to': 1, 'head': HEAD}, {'type': 'relative', 'from': 1, 'to': 2, 'head': HEAD}])
    assert 'RELATION_HEAD_NOT_WELL_FORMED:nested' in rejected(nested)


def test_a_relation_without_head_is_what_it_was_and_te_and_the_continuative_are_not_relations():
    plain = synthetic([cl('話す', {'agent': '母'}), cl('呼ぶ', {'agent': '兄'})], [{'type': 'relative', 'from': 0, 'to': 1}])
    assert EC._check(plain) == [] and EC.build_crosses(plain, EC.StubLookup()).status == 'CROSSED'
    for t in ('TE_UNDETERMINED', 'PARALLEL_UNDETERMINED'):
        bad = synthetic([cl('話す', {'agent': '母'}), cl('呼ぶ', {'agent': '兄'})], [{'type': t, 'from': 0, 'to': 1}])
        assert rejected(bad) == ['RELATION_TYPE_NOT_IN_CONVENTION:%s' % t]
    assert [r for r in EC.RELATION_TYPES] == [r for r in BEC.RELATION_TYPES]


# ---- observation: an EDGE of a real reading ---------------------------------------------------------------------------------------------------------------
def observed(text, direction, cross_index=None, query=None):
    out = SR.read(text, placement=query or F.FixtureQuery())
    anchor = OB.AnchorText('seed', text, 'ja', cross_index, reading=out)
    vp = OB.Viewpoint(anchor, OB.parse_direction(direction))
    structure = OB.Structure.empty(EC.StubLookup(), OB.StubNeighbors(), None)
    obs = OB.observe(vp, structure)
    return vp, structure, obs


@pytest.mark.parametrize('text,relation,predicate', [(CON, 'cause', '歌う'), ('兄が来れば、弟が帰る。', 'condition', '帰る'), ('兄が本を読みながら、弟が歌を歌った。', 'simultaneous', '歌う'),
                                                    ('兄が来ても、弟が帰る。', 'concession', '帰る'), ('兄が本を読んだが、弟が歌を歌った。', 'contrast', '歌う'),
                                                    (REL, 'relative', '呼ぶ')])
def test_an_edge_move_walks_a_relation_that_the_new_path_wrote_and_every_element_is_reobserved(text, relation, predicate):
    vp, structure, obs = observed(text, 'EDGE:' + relation, 0)
    assert obs.outcome == 'FOCUS', obs.outcome
    moved = [e for e in obs.elements() if e.cell.distance > 0]
    assert moved and moved[0].cell.cross.center['predicate'] == predicate
    assert moved[0].cell.coord['moves'][-1]['move'] == 'EDGE' and moved[0].cell.coord['moves'][-1]['dir'] == 'forward'
    for e in obs.elements():
        assert OB.reobserve(e, vp, structure)['status'] == 'REOBSERVED'


def test_an_edge_move_goes_backward_from_the_main_clause_and_the_embedded_cross_is_in_the_element():
    vp, structure, obs = observed(REL, 'EDGE:relative', 1)
    moved = [e for e in obs.elements() if e.cell.distance > 0]
    assert moved and moved[0].cell.coord['moves'][-1]['dir'] == 'backward' and moved[0].cell.cross.center['predicate'] == '話す'
    d = obs.anchor.to_dict()
    assert d['cross']['arms']['patient']['fillers'][0]['embedded']['center']['predicate'] == '話す'
    for e in obs.elements(): assert OB.reobserve(e, vp, structure)['status'] == 'REOBSERVED'


def test_the_relation_the_path_did_not_write_is_not_walked():
    vp, structure, obs = observed(CON, 'EDGE:relative', 0)
    assert obs.outcome == 'NO_MOVE_LICENSED'
