"""W5-a (A1, A2): the serialised event cross does not depend on the order of the keys of the input, nor on the order a placement
lookup returns its types in.

For EVERY mapping of the input (the top level, each clause, each roles, quantifiers and the mappings inside it, each relation, each
clause_meta, the abstain), the keys of that mapping are written in ALL their orders (the other mappings stay as the base); the bytes of
`json.dumps(build_crosses(x).to_dict())` must be those of the base. Not a sample of orders: all of them.
"""
import itertools
import json
import time

import pytest

from verantyx.event_cross import PlaceResult, build_crosses


def _dump(read_output, lookup=None):
    return json.dumps(build_crosses(read_output, lookup).to_dict(), ensure_ascii=False)


def _readable():
    return {
        'schema': 'verantyx.semantic_read/1', 'lang': 'ja', 'readable': True,
        'clauses': [
            {'predicate': 'a', 'roles': {'agent': 'x1', 'patient': 'x2', 'place': 'x3'}, 'polarity': '+', 'tense': 'past',
             'modality': None, 'voice': 'active',
             'quantifiers': {'agent': {'kind': 'universal', 'word': 'w1', 'detail': {'p': 1, 'q': 2}}, 'patient': {'kind': 'k', 'word': 'w2'}},
             'scope': {'wide': 'agent', 'narrow': 'patient', 'basis': {'z': 1, 'y': 2}}},
            {'predicate': 'b', 'roles': {'agent': 'x4', 'recipient': 'x5'}, 'polarity': '-', 'tense': 'nonpast',
             'modality': None, 'voice': 'passive'},
        ],
        'relations': [{'type': 'relative', 'from': 0, 'to': 1}],
        'abstain': None, 'unsupported': [],
        'clause_meta': [{'rule': 'r1', 'span': [0, 1]}, {'rule': 'r2', 'span': [2, 3]}],
    }


def _readable_with_comparison():
    """The same, the first clause holding `comparison` in place of `scope` (a clause then has 8 keys, not 9: 9! orders take over a minute)."""
    x = _readable()
    clause = x['clauses'][0]
    del clause['scope']
    clause['comparison'] = 'comparative'
    return x


def _unreadable():
    return {
        'schema': 'verantyx.semantic_read/1', 'lang': 'ja', 'readable': False, 'clauses': [], 'relations': [],
        'abstain': {'kind': 'not_supported', 'reasons': ['R1'], 'extra': {'m': 1, 'n': 2}},
        'unsupported': [], 'clause_meta': [],
    }


def _paths(node, here=()):
    """Every path (a tuple of keys / indexes) that leads to a mapping inside `node`, the node itself first."""
    if isinstance(node, dict):
        yield here
        for k, v in node.items():
            yield from _paths(v, here + (k,))
    elif isinstance(node, list):
        for i, v in enumerate(node):
            yield from _paths(v, here + (i,))


def _at(node, path):
    for p in path:
        node = node[p]
    return node


def _with_order(base, path, order):
    """A deep copy of `base` in which the mapping at `path` has its keys in `order` (same content)."""
    out = json.loads(json.dumps(base))
    if not path:
        return {k: out[k] for k in order}
    parent = _at(out, path[:-1])
    target = parent[path[-1]]
    parent[path[-1]] = {k: target[k] for k in order}
    return out


def _all_orders(base, only=None):
    for path in _paths(base):
        if only is not None and path not in only: continue
        keys = list(_at(base, path).keys())
        for order in itertools.permutations(keys):
            yield path, order


@pytest.mark.parametrize('make, only', [(_readable, None), (_readable_with_comparison, {('clauses', 0)}), (_unreadable, None)],
                         ids=['readable', 'readable_with_comparison', 'unreadable'])
def test_every_key_order_of_every_mapping_gives_the_same_bytes(make, only):
    base = make()
    want = _dump(base)
    seen = 0
    started = time.perf_counter()
    for path, order in _all_orders(base, only):
        got = _dump(_with_order(base, path, order))
        assert got == want, (path, order)
        seen += 1
    elapsed = time.perf_counter() - started
    # the measurement the ticket asks for (K3): printed (visible with -s)
    print('K3 %s: %d orders, %.2f s' % (make.__name__, seen, elapsed))
    assert seen >= 40320


def test_the_orders_are_all_the_orders_of_the_top_level_and_a_nested_mapping():
    base = _readable()
    # the top level has 8 keys and the first clause 8 (predicate, roles, polarity, tense, modality, voice, quantifiers, scope)
    sizes = {path: len(_at(base, path)) for path in _paths(base)}
    assert sizes[()] == 8 and sizes[('clauses', 0)] == 8


class _Reversed:
    id = 'w5a-reversed-multiple/1'

    def __init__(self, types):
        self.types = types

    def lookup(self, lemma):
        return PlaceResult(state='MULTIPLE', origin='direct', estimate_basis=None, types=self.types, provenance={})


def test_a_lookup_that_returns_the_types_in_any_order_gives_the_same_bytes():
    base = _readable()
    want = _dump(base, _Reversed(('ABSTRACT', 'PERSON', 'PLACE')))
    for order in itertools.permutations(('ABSTRACT', 'PERSON', 'PLACE')):
        assert _dump(base, _Reversed(order)) == want
    assert '"types": ["ABSTRACT", "PERSON", "PLACE"]' in want


def test_a_place_result_is_written_in_alphabetical_order_and_a_changed_one_is_refused():
    p = PlaceResult(state='MULTIPLE', origin='direct', types=('PLACE', 'PERSON'))
    assert p.types == ('PERSON', 'PLACE') and p.invariant_problems() == []
    # a value that was put out of order after it was built (the frozen dataclass is bypassed) is not accepted
    object.__setattr__(p, 'types', ('PLACE', 'PERSON'))
    assert 'TYPES_NOT_IN_ALPHABETICAL_ORDER' in p.invariant_problems()
    # a duplicate stays a duplicate; a list / empty string / non-string is not repaired, it is refused as before
    assert 'TYPES_DUPLICATED' in PlaceResult(state='MULTIPLE', origin='direct', types=('A', 'A')).invariant_problems()
    assert PlaceResult(state='MULTIPLE', origin='direct', types=['B', 'A']).invariant_problems() == ['TYPES_NOT_A_TUPLE_OF_STRINGS']
    assert PlaceResult(state='MULTIPLE', origin='direct', types=('B', '')).invariant_problems() == ['TYPES_NOT_A_TUPLE_OF_STRINGS']
    assert PlaceResult(state='MULTIPLE', origin='direct', types=('B', 1)).invariant_problems() == ['TYPES_NOT_A_TUPLE_OF_STRINGS']


def test_a_relation_is_written_in_the_fixed_key_order_and_an_extra_key_is_kept_after_them():
    base = _readable()
    base['relations'] = [{'extra_b': 2, 'to': 1, 'extra_a': {'q': 1, 'p': 2}, 'from': 0, 'type': 'relative'}]
    out = build_crosses(base).to_dict()['relations'][0]
    assert list(out) == ['type', 'from', 'to', 'extra_a', 'extra_b']
    assert list(out['extra_a']) == ['p', 'q']
