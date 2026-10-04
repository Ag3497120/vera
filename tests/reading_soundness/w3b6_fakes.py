"""W3-b6: fake placements for the tests and the measurement tool (no real placement is opened here).

The data of W3-b6 (`ja_r13.jsonl`, and any file of the same shape, for example the unpublished sentences of the reviewer) writes for each sentence a `placement`: word -> a spec.
`answer_of(word, spec)` turns a spec into an answer of the shape of `coarse_place.query` (the contract of docs/COARSE_PLACEMENT.md), and `query_of(row)` into a query object.

A spec is one of
  {'state': 'UNPLACED' | 'UNKNOWN' | ...}                              a bare answer of that state (no type)
  {'top': [types], 'decided_by': [arms]}                                a noun: one type -> DECIDED direct, several -> MULTIPLE direct
  {'top': [types], 'origin': 'estimated', 'basis': 'generated' | 'proximity'}      an estimated noun
  {'top': ['P_ACT'], 'namespace': 'P', 'decided_by': [...], 'frame_status': ..., 'frame': ..., 'role_frame_status': ..., 'role_frame': ..., 'role_frame_unconfirmed': ...}
                                                                        a predicate; the three keys of the contract of W3-a6 (D8) are put at the END of the answer, in this order, and only
                                                                        when the spec has `role_frame_status` (no key in the spec = no key in the answer: the placements r7 and r8 and no placement)
`strip_role_frame(row)` is the same row without the three keys (the answer of a placement with no table of role frames).
"""
import copy
import importlib.util
from pathlib import Path

HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location('w3b2_fakes_loaded_by_w3b6', HERE / 'w3b2_fakes.py')
F = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(F)

ROLE_FRAME_KEYS = ('role_frame_status', 'role_frame', 'role_frame_unconfirmed')


def answer_of(word, spec):
    if 'state' in spec and 'top' not in spec: return F.bare(spec['state'], term=word)
    if spec.get('namespace') == 'P':
        a = F.answer(spec['top'], decided_by=spec.get('decided_by', ['seed']), term=word)
        a['namespace'] = 'P'
        if spec.get('origin') == 'estimated': a = F.to_estimated(a, spec['basis'])
        if 'frame_status' in spec:
            a['frame_status'] = spec['frame_status']
            a['frame'] = spec.get('frame')
        if 'role_frame_status' in spec:
            a['role_frame_status'] = copy.deepcopy(spec['role_frame_status'])
            a['role_frame'] = copy.deepcopy(spec.get('role_frame'))
            a['role_frame_unconfirmed'] = copy.deepcopy(spec.get('role_frame_unconfirmed'))
        return a
    if spec.get('origin') == 'estimated': return F.to_estimated(F.answer(spec['top'], decided_by=['seed'], term=word), spec['basis'])
    return F.answer(spec['top'], decided_by=spec.get('decided_by', ['seed']), term=word)


def query_of(row, mapper=None):
    answers = {w: answer_of(w, spec) for w, spec in row['placement'].items()}
    if mapper: answers = {w: mapper(a) for w, a in answers.items()}
    return F.MapQuery(answers)


def strip_role_frame(row):
    """The row without the three keys of the role frame (a deep copy)."""
    out = copy.deepcopy(row)
    for spec in out['placement'].values():
        for k in ROLE_FRAME_KEYS: spec.pop(k, None)
    return out
