"""W3-b3: fake placements for the tests and the measurement scripts (no real placement is opened here).

`FixtureQuery` answers from `w3b3_placement_fixture.json` (answers of `coarse_place.query` of the placement r6; the placement path is not in it). The answers of the words
W3-b2 froze (`w3b2_placement_fixture.json`) are the answers of the same placement: they must agree with the new fixture on every word they share (asserted at import), and the
two are merged (the W3-b3 words first). A word that is in neither is answered UNKNOWN and recorded in `misses`; every question is recorded in `calls`.
W3-b2's `w3b2_fakes.py` (which loads W3-b1's) is loaded by path under a unique name (not changed) for `answer`, `bare`, `unknown_answer`, `to_estimated`, `to_multiple`,
`MapQuery`, `with_frame`.
"""
import copy
import importlib.util
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location('w3b2_fakes_loaded_by_w3b3', HERE / 'w3b2_fakes.py')
B2 = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(B2)
FIXTURE = json.loads((HERE / 'w3b3_placement_fixture.json').read_text(encoding='utf-8'))
SHA = FIXTURE['_meta']['content_sha256']
assert B2.SHA == SHA, 'the W3-b2 fixture is of another placement'
for _t in set(FIXTURE['answers']) & set(B2.ANSWERS):
    assert FIXTURE['answers'][_t] == B2.ANSWERS[_t], 'fixtures disagree on %r' % _t
ANSWERS = dict(B2.ANSWERS); ANSWERS.update(FIXTURE['answers'])

unknown_answer, answer, bare, to_estimated, to_multiple, MapQuery, with_frame = (B2.unknown_answer, B2.answer, B2.bare, B2.to_estimated, B2.to_multiple, B2.MapQuery, B2.with_frame)


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
