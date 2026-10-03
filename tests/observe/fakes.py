"""Fakes for the W3-c tests: a placement (lookup and neighbours) built from dicts, and reader outputs written by hand.

`FakePlacement` records every word it is asked about. Its neighbour lists are returned in the order they were given (the code under test
must not depend on that order). `read_out` / `clause` write a `verantyx.semantic_read/1` output in the shape of docs/READING_CONVENTIONS.md.
"""
from verantyx.event_cross import PlaceResult
from verantyx.observe import NeighborResult

SCHEMA = 'verantyx.semantic_read/1'


def direct(*types):
    ts = tuple(sorted(types))
    return PlaceResult(state='DECIDED' if len(ts) == 1 else 'MULTIPLE', origin='direct', estimate_basis=None, types=ts, provenance={'fake': True})


def estimated(basis, *types):
    ts = tuple(sorted(types))
    return PlaceResult(state='DECIDED' if len(ts) == 1 else 'MULTIPLE', origin='estimated', estimate_basis=basis, types=ts,
                       provenance={'fake': True, 'constructed': True})


def bare(state):
    return PlaceResult(state=state, origin=None, estimate_basis=None, types=(), provenance={'fake': True})


class FakePlacement:
    id = 'fake-placement/1'

    def __init__(self, places=None, neighbors=None, neighbor_states=None):
        self.places = dict(places or {})
        self.near = {k: tuple(v) for k, v in (neighbors or {}).items()}
        self.states = dict(neighbor_states or {})        # word -> a NeighborResult returned as it is (for broken answers)
        self.lookup_calls = []
        self.neighbor_calls = []

    def lookup(self, lemma, *args, **kwargs):
        self.lookup_calls.append((lemma, args, kwargs))
        return self.places.get(lemma, bare('UNKNOWN'))

    def neighbors(self, lemma):
        self.neighbor_calls.append(lemma)
        if lemma in self.states: return self.states[lemma]
        if lemma not in self.near: return NeighborResult('UNKNOWN', (), {'fake': True})
        items = self.near[lemma]
        return NeighborResult('FOUND' if items else 'NO_NEIGHBORS', items, {'fake': True})


def clause(predicate='あげる', roles=None, polarity='+', tense='past', modality=None, voice='active', **extra):
    c = {'predicate': predicate, 'roles': {} if roles is None else roles, 'polarity': polarity, 'tense': tense, 'modality': modality, 'voice': voice}
    c.update(extra)
    return c


def read_out(clauses, relations=(), metas=None, lang='ja'):
    metas = metas if metas is not None else [{'rule': 'frame', 'span': [i, i + 1]} for i in range(len(clauses))]
    return {'schema': SCHEMA, 'lang': lang, 'readable': True, 'clauses': clauses, 'relations': list(relations),
            'abstain': None, 'unsupported': [], 'clause_meta': metas}


# the placement used by most tests: 太郎 is a person; its neighbours are of every kind the type agreement tells apart
GIVE = '太郎は花子に本をあげた。'
PEOPLE = {
    '太郎': direct('PERSON'), '花子': direct('PERSON'), '次郎': direct('PERSON'), '犬': direct('ANIMAL'),
    '机': direct('ARTIFACT'), '東京': direct('PLACE'), '彼': estimated('proximity', 'PERSON'), '謎': bare('UNPLACED'),
    '会社': direct('GROUP_ORG', 'PLACE'), '本': direct('ARTIFACT'),
}
PEOPLE_NEAR = {'太郎': ('花子', '次郎', '犬', '机', '東京', '彼', '謎', '会社', '太郎', '誰も知らない')}


def people_placement(order=None):
    near = {k: (tuple(v) if order is None else tuple(order(v))) for k, v in PEOPLE_NEAR.items()}
    return FakePlacement(PEOPLE, near)
