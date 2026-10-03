"""W3-b2: fake placements for the tests and the measurement scripts (no real placement is opened here).

`FixtureQuery` answers from `w3b2_placement_fixture.json` (answers of `coarse_place.query` of the placement r6 with `frame_status` and `frame`; the placement path is not in
it). A word that is not there is answered UNKNOWN and recorded in `misses`, and every question is recorded in `calls`. The fixtures W3-b1 froze are excerpts of an EARLIER
placement (another content hash; the types of some verbs differ), so they are not mixed in. W3-b1's `w3b1_fakes.py` is loaded by path under a unique name (the module is not
changed) for `answer`, `bare`, `unknown_answer`, `to_estimated`, `to_multiple`, `MapQuery`; `with_frame` adds the keys of W3-a3 to an answer.
"""
import copy
import importlib.util
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location('w3b1_fakes_loaded_by_w3b2', HERE / 'w3b1_fakes.py')
B1 = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(B1)
FIXTURE = json.loads((HERE / 'w3b2_placement_fixture.json').read_text(encoding='utf-8'))
SHA = FIXTURE['_meta']['content_sha256']
ANSWERS = dict(FIXTURE['answers'])

unknown_answer, answer, bare, to_estimated, to_multiple, MapQuery = B1.unknown_answer, B1.answer, B1.bare, B1.to_estimated, B1.to_multiple, B1.MapQuery


def with_frame(a, frame_status, frame=None):
    """A copy of a placement answer with the two keys of W3-a3 (`frame_status`, `frame`) at the end."""
    a = copy.deepcopy(a)
    a['frame_status'] = frame_status
    a['frame'] = frame
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
