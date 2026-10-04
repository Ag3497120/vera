"""W3-b1: fake placements for the tests and the measurement scripts (no real placement is opened here).

`FixtureQuery` answers from `w3b1_placement_fixture.json` (an excerpt of `coarse_place.query` answers for every word of the new data and of the three
B1 samples; the placement path is not in it). A word that is not in the fixture is answered UNKNOWN and is recorded in `misses`, so a test can show
that nothing was asked outside the fixture. `to_estimated` / `to_multiple` rewrite the DECIDED / MULTIPLE direct answers into the shapes of an estimated
(proximity or generated) answer and of a split answer that satisfy the contract (docs/COARSE_PLACEMENT.md section 11.6), for the "direct only" test.
"""
import copy
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
FIXTURE = json.loads((HERE / 'w3b1_placement_fixture.json').read_text(encoding='utf-8'))
SHA = FIXTURE['_meta']['content_sha256']
# round 3: the words of ja_r9.jsonl (answers of the same placement; w3b1_placement_fixture_r9.json). `FIXTURE` (round 1) is not changed; FixtureQuery answers from all of them.
# round 4: the words of ja_r10.jsonl (w3b1_placement_fixture_r10.json). The files are read strictly (a missing file fails at import; it used to fall back to an empty
# answer silently, so a lost file would have shown up as a change in what a test means): the review of round 3 asked for it.
FIXTURE_R9 = json.loads((HERE / 'w3b1_placement_fixture_r9.json').read_text(encoding='utf-8'))
FIXTURE_R10 = json.loads((HERE / 'w3b1_placement_fixture_r10.json').read_text(encoding='utf-8'))
assert FIXTURE_R9['_meta']['content_sha256'] == SHA
assert FIXTURE_R10['_meta']['content_sha256'] == SHA
# the same word has the same answer in every fixture (they are excerpts of one placement)
for _a, _b in ((FIXTURE_R10, FIXTURE_R9), (FIXTURE_R10, FIXTURE), (FIXTURE_R9, FIXTURE)):
    for _t in set(_a['answers']) & set(_b['answers']):
        assert _a['answers'][_t] == _b['answers'][_t], 'fixtures disagree on %r' % _t
ANSWERS = dict(FIXTURE_R10['answers']); ANSWERS.update(FIXTURE_R9['answers']); ANSWERS.update(FIXTURE['answers'])

def unknown_answer(term):
    return {'term': term, 'namespace': None, 'state': 'UNKNOWN', 'origin': None, 'estimate_basis': None, 'constructed': False, 'top': [],
            'decided_by': None, 'generated': None, 'generated_definition': None, 'placement': {'content_sha256': SHA, 'reason': None}}


def to_estimated(answer, basis):
    """A direct DECIDED / MULTIPLE answer becomes an estimated one (the same types, constructed, `estimate_basis` = basis)."""
    a = copy.deepcopy(answer)
    if a['state'] in ('DECIDED', 'MULTIPLE') and a['origin'] == 'direct':
        a['origin'] = 'estimated'; a['estimate_basis'] = basis; a['constructed'] = True
        a['decided_by'] = ['gen_definition'] if basis == 'generated' else None
        a['generated'] = basis == 'generated'; a['generated_definition'] = basis == 'generated'
    return a


def to_multiple(answer):
    """A direct DECIDED answer becomes a split one (MULTIPLE: its type and one other of the same family)."""
    a = copy.deepcopy(answer)
    if a['state'] == 'DECIDED' and a['origin'] == 'direct':
        t = a['top'][0]
        other = ('P_ACT' if t != 'P_ACT' else 'P_STATE') if t.startswith('P_') else ('ABSTRACT' if t != 'ABSTRACT' else 'WORK')
        a['state'] = 'MULTIPLE'; a['top'] = sorted([t, other])
    return a


class FixtureQuery:
    """query(term) -> a dict of the shape of coarse_place.query. `mapper` rewrites each answer (for the estimated / multiple fakes)."""
    id = 'fixture:' + SHA

    def __init__(self, path=None, mapper=None):
        self.path, self.mapper, self.misses, self.calls = path, mapper, [], []

    def query(self, term):
        self.calls.append(term)
        a = ANSWERS.get(term)
        if a is None:
            self.misses.append(term); a = unknown_answer(term)
        a = copy.deepcopy(a)
        return self.mapper(a) if self.mapper else a


class MapQuery:
    """A hand-written placement for one test: term -> answer dict (built with `answer`); a missing word is UNKNOWN."""
    id = 'map-query'

    def __init__(self, mapping):
        self.mapping, self.calls = dict(mapping), []

    def query(self, term):
        self.calls.append(term)
        return copy.deepcopy(self.mapping.get(term) or unknown_answer(term))


def answer(top, *, state=None, origin='direct', basis=None, decided_by=('seed',), term='x'):
    """A contract-conforming answer: one type -> DECIDED, several -> MULTIPLE."""
    top = [top] if isinstance(top, str) else list(top)
    st = state or ('DECIDED' if len(top) == 1 else 'MULTIPLE')
    return {'term': term, 'namespace': 'N', 'state': st, 'origin': origin, 'estimate_basis': basis, 'constructed': origin == 'estimated', 'top': sorted(top),
            'decided_by': list(decided_by) if decided_by is not None else None, 'generated': False, 'generated_definition': False,
            'placement': {'content_sha256': SHA, 'reason': None}}


def bare(state, reason=None, term='x'):
    a = unknown_answer(term); a['state'] = state
    if reason: a['placement'] = {'content_sha256': None, 'reason': reason}
    return a


def patch_coarse_place(monkeypatch, mapper=None):
    """Replace `verantyx.coarse_place.query` by a function that answers from the fixture and records its keyword arguments."""
    from verantyx import coarse_place
    calls = []
    fq = FixtureQuery(mapper=mapper)

    def fake(term, *, context_role=None, context_predicate=None, placement=None):
        calls.append({'term': term, 'context_role': context_role, 'context_predicate': context_predicate, 'placement': placement})
        a = fq.query(term)
        a['placement'] = dict(a['placement'], path=placement)
        return a
    monkeypatch.setattr(coarse_place, 'query', fake)
    return calls, fq
