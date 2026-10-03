"""W5-e (docs/EVENT_CROSS.md, W5-e): `role_flags` may carry `coordination` (と・や・か) and a role that carries it is not made a cross.

The reading entry does not write the mark (it abstains on a coordination or a disjunction: docs/READING_SOUNDNESS.md section 10E), so this is only the form that
receives it: `INPUT_REJECTED` with `COORDINATION_UNMARKED:<role>`.  Synthetic inputs only.  The inputs with `determiner` alone are exactly as before.
"""
import json
import sys
import importlib.util
from pathlib import Path

import pytest

from verantyx import event_cross as EC

TREE = Path(__file__).resolve().parent.parent


def _load_by_path(name, path):
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, str(path))
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


fakes = _load_by_path('w5e_event_cross_fakes', TREE / 'tests' / 'event_cross' / 'fakes.py')


def clause(**extra):
    c = {'predicate': '読む', 'roles': {'agent': '太郎と花子', 'patient': '手紙'}, 'polarity': '+', 'tense': 'past', 'modality': None, 'voice': 'active'}
    c.update(extra)
    return c


def reading(c):
    return {'schema': EC.SOURCE_SCHEMA, 'lang': 'ja', 'readable': True, 'clauses': [c], 'relations': [], 'abstain': None, 'unsupported': [],
            'clause_meta': [{'rule': 'frame', 'span': [3, 5]}]}


def cross(c, mapping=None):
    return EC.build_crosses(reading(c), fakes.MappingLookup(mapping or {}))


@pytest.mark.parametrize('mark', ['と', 'や', 'か'])
def test_a_role_that_carries_a_coordination_mark_is_not_made_a_cross(mark):
    r = cross(clause(role_flags={'agent': {'coordination': mark}}))
    assert r.status == 'INPUT_REJECTED' and r.crosses == ()
    assert r.abstain['reasons'] == ['COORDINATION_UNMARKED:agent']


def test_the_mark_together_with_a_determiner_is_well_formed_and_rejected_for_the_mark_only():
    r = cross(clause(role_flags={'agent': {'determiner': 'この', 'coordination': 'と'}}))
    assert r.status == 'INPUT_REJECTED' and r.abstain['reasons'] == ['COORDINATION_UNMARKED:agent']


def test_every_marked_role_is_named_once():
    r = cross(clause(role_flags={'agent': {'coordination': 'や'}, 'patient': {'coordination': 'か'}}))
    assert r.status == 'INPUT_REJECTED' and r.abstain['reasons'] == ['COORDINATION_UNMARKED:agent', 'COORDINATION_UNMARKED:patient']


def test_a_mark_on_one_role_does_not_make_the_other_role_a_problem():
    r = cross(clause(role_flags={'agent': {'coordination': 'と'}, 'patient': {'determiner': 'その'}}))
    assert r.abstain['reasons'] == ['COORDINATION_UNMARKED:agent']


@pytest.mark.parametrize('bad', [
    {'agent': {'coordination': ''}}, {'agent': {'coordination': 3}}, {'agent': {'coordination': 'または'}}, {'agent': {'coordination': 'と '}},
    {'agent': {'coordination': 'と', 'other': 'x'}}, {'agent': {'determiner': ''}}, {'agent': {}}, {'time': {'coordination': 'と'}},          # a role the clause does not have
    {}, [], 'と', {'agent': 'と'}, None,
])
def test_a_flag_of_a_bad_shape_is_still_refused_with_its_own_reason_and_not_as_unmarked(bad):
    r = cross(clause(role_flags=bad))
    assert r.status == 'INPUT_REJECTED' and 'ENTRY_FLAGS_NOT_WELL_FORMED' in r.abstain['reasons']
    assert not any(x.startswith('COORDINATION_UNMARKED') for x in r.abstain['reasons'])


def test_determiner_only_input_is_exactly_as_before():
    c = clause(roles={'agent': '母', 'place': '部屋'}, role_flags={'place': {'determiner': 'この'}})
    r = cross(c, {'母': fakes.direct('PERSON'), '部屋': fakes.direct('PLACE')})
    assert r.status == 'CROSSED' and dict(r.crosses[0].arms['place'].fillers[0].flags) == {'determiner': 'この'}
    assert 'role_flags' not in json.dumps(r.crosses[0].center)


def test_a_role_value_with_a_particle_inside_and_no_mark_is_not_refused_by_its_surface():
    # the guard is on the mark the reader writes, never on the characters of the value: a name that holds a か (赤坂) or a pair passed as one value is a value
    for value in ('赤坂', 'ハルとセキ', '太郎か花子'):
        r = cross(clause(roles={'agent': value, 'patient': '手紙'}))
        assert r.status == 'CROSSED' and r.crosses[0].arms['agent'].fillers[0].surface == value


def test_the_registered_keys_are_not_widened_and_the_filler_has_no_coordination_field():
    assert EC.ENTRY_FLAG_KEYS == ('role_flags',) and 'role_flags' not in EC.CLAUSE_KEYS
    assert 'coordination' not in {f for f in EC.Filler.__dataclass_fields__}
    r = cross(clause(role_flags={'agent': {'determiner': 'この'}}))
    assert 'coordination' not in json.dumps(r.to_dict())
