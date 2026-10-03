"""観測としての生成 (docs/OBSERVATION.md): 視点から構造を観測して生成する。Generation as OBSERVATION: look at a structure from a viewpoint and let the realizer say what is seen.

    observe(viewpoint, structure) -> Observation      a list of event crosses, each with a coordinate (which cross, which moves)
    realize (inside observe)      -> a sentence       made by `semantic_realize.realize_observed` from the observed cross only

A VIEWPOINT is (anchor, direction, range, state). The anchor is a record id, a question or a seed sentence (told apart by type), the
direction is a closed list of moves in order (`FACE_SWAP(role)`: swap ONE arm's filler for a neighbour word whose type the convention
accepts; `EDGE(relation)`: go to the cross that the reader linked to this one by that relation), the range is how many of the leading
moves may be applied, and the state is the ledger of the conversation (or FLAT).

What is observed is decided by (structure, viewpoint, state) alone. Nothing is sampled; no random number, no hash and no iteration order of
a set decides anything; a tie is never broken (it is returned as TIE with its candidates). Every clause of the output carries its
coordinate, and `reobserve` walks the coordinate again from the structure to the same cross. The only thing that varies between turns of
a conversation is the ledger, and the output says which ledger line moved which observation (`salience_trace`).

Honest limits (docs/OBSERVATION.md, 既知の穴): through the default entry (stub placement, the reader's own relations) almost only the anchor
cross is seen; a FACE_SWAP needs a placement file, an EDGE needs a reading with `relations` (the reader produced none in the measured
inputs). Nothing here makes either work by loosening a rule.

Nothing in this module is an ANSWER: an observed sentence is `OBSERVED_OCCUPIED`, `CONSTRUCTED_UNOCCUPIED` or `UNKNOWN_OCCUPANCY`, never an
answer to a question (an answer needs a record as evidence, which is outside this ticket).
Only the path of an anchor of kind `question` returns an `answer` (W3-c2): the fillers of the hole of a question, each with the ids of the structure's
own sentences that attest it. The anchor's reading and the index are never evidence (docs/OBSERVATION.md, 質問の観測).
"""
from __future__ import annotations

import copy
import hashlib
import json
import os
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional, Protocol, Sequence, Tuple, runtime_checkable

from . import event_cross as EC
from . import salience as SAL
from .salience import FLAT

SCHEMA = 'verantyx.observe/1'
WINDOW = 200                       # design constant (docs/OBSERVATION.md P6), not a measurement
DEFAULT_FAMILIES: Tuple[str, ...] = ('pro',)
ANCHOR_KINDS: Tuple[str, ...] = ('seed', 'question')
READING_SOURCES: Tuple[str, ...] = ('semantic_read', 'injected')
ANCHOR_READING_ID = 'anchor'       # the id of the anchor sentence's own reading (a structure sentence may not use it)

FACE_SWAP = 'FACE_SWAP'
EDGE = 'EDGE'

FACE_CELL_REASONS: Tuple[str, ...] = ('NO_ARM', 'ARM_TIE', 'ROLE_NOT_IN_TABLE', 'NO_PLACEMENT', 'NO_NEIGHBORS', 'UNKNOWN',
                                      'NEIGHBORS_RESULT_INVALID', 'NO_CANDIDATE_LICENSED')
FACE_CANDIDATE_REASONS: Tuple[str, ...] = (('DISAGREE', 'SYNTHETIC_READING_REJECTED')
                                           + tuple('NOT_CHECKED:%s' % r for r in EC.NOT_CHECKED_REASONS))
EDGE_CELL_REASONS: Tuple[str, ...] = ('NO_RELATION_IN_STRUCTURE',)
OCCUPANCY_STATES: Tuple[str, ...] = ('ATTESTED', 'UNOCCUPIED', 'UNKNOWN_NO_INDEX', 'UNKNOWN_FAMILY_DB_MISSING', 'UNKNOWN_INDEX_UNREADABLE',
                                     'UNKNOWN_INDEX_REBUILD_REQUIRED', 'UNKNOWN_QUERY_NOT_SEARCHED', 'UNKNOWN_WINDOW_SATURATED')
CLAIMS: Tuple[str, ...] = ('OBSERVED_OCCUPIED', 'CONSTRUCTED_UNOCCUPIED', 'UNKNOWN_OCCUPANCY')
OUTCOMES: Tuple[str, ...] = ('FOCUS', 'TIE', 'NO_ANCHOR', 'NO_MOVE_LICENSED')
# Refusal reasons of `semantic_realize` that only the answer realizer and the source-view realizer raise (semantic_realize.py, the `_fail` calls of those two functions); `realize_observed`
# never returns them, so listing them with a 0 would say a thing this path could do. Dropped on purpose and named here (decision E22): the closed list of the zero counts is
# REFUSAL_REASONS minus these two, and a test fails if the realizer's list grows, so a new reason is never dropped silently.
REFUSAL_NOT_ON_THIS_PATH: Tuple[str, ...] = ('NO_ANSWER_RESULT', 'NO_SOURCE_VIEW')


def _cj(obj: Any) -> str:
    """Canonical json: a text that is the same for the same value (keys sorted, no ASCII escapes, no spaces)."""
    return json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(',', ':'))


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def _bad(detail: str) -> ValueError:
    return ValueError('BAD_ARGUMENTS:%s' % detail)


# ---------------------------------------------------------------------------------------------------------------------------------
# cell identity (P1)
# ---------------------------------------------------------------------------------------------------------------------------------
def content_of_cross(cross: EC.EventCross) -> Dict[str, Any]:
    """The content of a cross: the centre as it is and, per arm, role / kind / the surfaces of the fillers. The placement is NOT included."""
    return {'center': copy.deepcopy(dict(cross.center)),
            'arms': [{'role': role, 'kind': arm.kind, 'surfaces': [f.surface for f in arm.fillers]} for role, arm in cross.arms.items()]}


def cell_key_of_content(content: Mapping[str, Any]) -> str:
    return 'cell:' + _cj(content)


def cell_key_of(cross: EC.EventCross) -> str:
    return cell_key_of_content(content_of_cross(cross))


def _surfaces_of(cross: EC.EventCross) -> Tuple[str, ...]:
    return tuple(f.surface for arm in cross.arms.values() for f in arm.fillers)


# ---------------------------------------------------------------------------------------------------------------------------------
# neighbours and placement from a file (D14)
# ---------------------------------------------------------------------------------------------------------------------------------
NEIGHBOR_STATES: Tuple[str, ...] = ('FOUND', 'NO_NEIGHBORS', 'NO_PLACEMENT', 'UNKNOWN')


@dataclass(frozen=True)
class NeighborResult:
    """The neighbours of one word in the placement. `items` is a SET written in string order: it is not a ranking."""
    state: str
    items: Tuple[str, ...] = ()
    provenance: Mapping[str, Any] = field(default_factory=dict)

    def problems(self) -> List[str]:
        bad: List[str] = []
        if self.state not in NEIGHBOR_STATES: bad.append('STATE_UNKNOWN:%s' % (self.state,))
        if not isinstance(self.items, tuple) or not all(isinstance(w, str) and w for w in self.items):
            bad.append('ITEMS_NOT_A_TUPLE_OF_STRINGS'); return bad
        if len(set(self.items)) != len(self.items): bad.append('ITEMS_DUPLICATED')
        if (self.state == 'FOUND') != bool(self.items): bad.append('FOUND_IFF_ITEMS')
        return bad


@runtime_checkable
class NeighborSource(Protocol):
    def neighbors(self, lemma: str) -> NeighborResult: ...


class StubNeighbors:
    """The default until the coarse placement is wired in: there is no placement, so there are no neighbours to ask (NO_PLACEMENT)."""
    id = 'stub-no-neighbors/1'

    def neighbors(self, lemma: str) -> NeighborResult:
        return NeighborResult('NO_PLACEMENT', (), {'reason': 'STUB'})


class FilePlacement:
    """A placement read from ONE json file: {"lemmas": {word: PlaceResult fields}, "neighbors": {word: [word, ...]}}. It answers both the
    placement query (`lookup`) and the neighbour query (`neighbors`). A word the file does not mention is UNKNOWN (not UNPLACED, which says
    the word is in the material and the evidence is short). The id is the sha256 of the CONTENT the file gives (words in string order, each
    answer as `PlaceResult` fields, each neighbour set in string order, written as canonical json), not of the bytes of the file: a file whose
    neighbour lists are in another order, or whose keys or blanks differ, gives the same id and the same output; a different SET of neighbours
    or a different answer gives another id. The path never appears in an output."""

    def __init__(self, data: Mapping[str, Any], sha256: str):
        if not isinstance(data, Mapping): raise _bad('PLACEMENT_FILE_INVALID:not an object')
        extra = [k for k in data if k not in ('lemmas', 'neighbors')]
        if extra: raise _bad('PLACEMENT_FILE_INVALID:unknown key %s' % ','.join(sorted(map(str, extra))))
        lemmas, neighbors = data.get('lemmas', {}), data.get('neighbors', {})
        if not isinstance(lemmas, Mapping) or not isinstance(neighbors, Mapping): raise _bad('PLACEMENT_FILE_INVALID:lemmas and neighbors must be objects')
        self._lemmas: Dict[str, EC.PlaceResult] = {}
        for word, fields in lemmas.items():
            if not isinstance(fields, Mapping) or 'state' not in fields: raise _bad('PLACEMENT_FILE_INVALID:lemma %s has no state' % word)
            bad_keys = [k for k in fields if k not in ('state', 'origin', 'estimate_basis', 'types', 'provenance')]
            if bad_keys: raise _bad('PLACEMENT_FILE_INVALID:lemma %s has unknown key %s' % (word, bad_keys[0]))
            types = fields.get('types', [])
            if not isinstance(types, list): raise _bad('PLACEMENT_FILE_INVALID:types of %s is not a list' % word)
            self._lemmas[word] = EC.PlaceResult(state=fields['state'], origin=fields.get('origin'), estimate_basis=fields.get('estimate_basis'),
                                                types=tuple(sorted(types)), provenance=dict(fields.get('provenance', {'file': True})))
        self._neighbors: Dict[str, Tuple[str, ...]] = {}
        for word, items in neighbors.items():
            if not isinstance(items, list) or not all(isinstance(w, str) for w in items): raise _bad('PLACEMENT_FILE_INVALID:neighbors of %s is not a list of strings' % word)
            self._neighbors[word] = tuple(sorted(set(items)))
        self.file_sha256 = sha256    # the bytes of the file, kept for whoever reads the file; the id below does not use it (W5-b, A1)
        content = {'lemmas': {w: {'state': r.state, 'origin': r.origin, 'estimate_basis': r.estimate_basis, 'types': list(r.types),
                                  'provenance': dict(r.provenance)} for w, r in self._lemmas.items()},
                   'neighbors': {w: list(items) for w, items in self._neighbors.items()}}
        self.id = 'file:' + _sha(_cj(content))

    @classmethod
    def from_path(cls, path: Any) -> 'FilePlacement':
        try:
            raw = Path(path).read_bytes()
        except OSError as exc:
            raise _bad('PLACEMENT_FILE_UNREADABLE:%s' % type(exc).__name__)
        try:
            data = json.loads(raw.decode('utf-8'))
        except ValueError:
            raise _bad('PLACEMENT_FILE_INVALID:not json')
        return cls(data, hashlib.sha256(raw).hexdigest())

    def lookup(self, lemma: str) -> EC.PlaceResult:
        got = self._lemmas.get(lemma)
        if got is not None: return got
        return EC.PlaceResult(state='UNKNOWN', provenance={'reason': 'NOT_IN_PLACEMENT_FILE'})

    def neighbors(self, lemma: str) -> NeighborResult:
        if lemma not in self._neighbors: return NeighborResult('UNKNOWN', (), {'reason': 'NOT_IN_PLACEMENT_FILE'})
        items = self._neighbors[lemma]
        return NeighborResult('FOUND' if items else 'NO_NEIGHBORS', items, {'file': True})


INVALID_NEIGHBORS = 'INVALID'


def _neighbors_of(source: Any, word: str) -> NeighborResult:
    """Ask the source about ONE word. An answer that breaks the contract is kept as an INVALID result with the problems named."""
    got = source.neighbors(word)
    if not isinstance(got, NeighborResult):
        return NeighborResult(INVALID_NEIGHBORS, (), {'problems': ['NOT_A_NEIGHBOR_RESULT:%s' % type(got).__name__]})
    problems = got.problems()
    if problems: return NeighborResult(INVALID_NEIGHBORS, (), {'problems': problems})
    return NeighborResult(got.state, tuple(sorted(set(got.items))), got.provenance)    # a set written in string order, not a ranking


def _source_id(source: Any) -> str:
    ident = getattr(source, 'id', None)
    return ident if isinstance(ident, str) and ident else 'unidentified'


# ---------------------------------------------------------------------------------------------------------------------------------
# readings and the structure (D1)
# ---------------------------------------------------------------------------------------------------------------------------------
@dataclass(frozen=True)
class Reading:
    """One sentence read: the crosses and the relations the reader gave. `source` says where the reading came from: `semantic_read` (the entry)
    or `injected` (the public interface only: a hand-written reader output, used by tests; never reachable from the command line)."""
    id: str
    text: Optional[str]
    lang: Optional[str]
    source: str
    status: str                                  # CROSSED | ABSTAINED | INPUT_REJECTED | READ_ERROR
    crosses: Tuple[EC.EventCross, ...] = ()
    relations: Tuple[Mapping[str, Any], ...] = ()
    abstain: Optional[Mapping[str, Any]] = None


def read_sentence(rid: str, text: str, lang: Optional[str], lookup: Any) -> Reading:
    from . import semantic_read    # inside the function: the entry imports the cross module only for --events
    try:
        out = semantic_read.read(text, lang)
    except semantic_read.ReadError as exc:
        return Reading(rid, text, lang, 'semantic_read', 'READ_ERROR', abstain={'kind': 'read_error', 'type': exc.type, 'detail': exc.detail})
    crossed = EC.build_crosses(out, lookup)
    got_lang = out.get('lang') if isinstance(out, Mapping) else None
    return Reading(rid, text, got_lang, 'semantic_read', crossed.status, crossed.crosses, crossed.relations, crossed.abstain)


def injected_reading(rid: str, text: Optional[str], read_output: Mapping[str, Any], lookup: Any) -> Reading:
    crossed = EC.build_crosses(read_output, lookup)
    lang = read_output.get('lang') if isinstance(read_output, Mapping) else None
    return Reading(rid, text, lang, 'injected', crossed.status, crossed.crosses, crossed.relations, crossed.abstain)


@dataclass(frozen=True)
class IndexSpec:
    root: Optional[Path]              # None: the default root of the corpus index, resolved when first used
    families: Tuple[str, ...] = DEFAULT_FAMILIES
    window: int = WINDOW


class Structure:
    """What can be observed: readings (the sentences of a structure file, or injected readings), a placement, a neighbour source and,
    optionally, a corpus index that tells whether a cell is occupied by a sentence there. The structure is built once and not changed."""

    def __init__(self, readings: Sequence[Reading], lookup: Any = None, neighbors: Any = None, index: Optional[IndexSpec] = None,
                 file_sha: Optional[str] = None, blank_lines: int = 0):
        self.readings: Tuple[Reading, ...] = tuple(readings)
        self.lookup = lookup if lookup is not None else EC.StubLookup()
        self.neighbors = neighbors if neighbors is not None else StubNeighbors()
        self.index = index
        self.file_sha = file_sha
        self.blank_lines = blank_lines
        ids: Dict[str, Reading] = {}
        for r in self.readings:
            if r.id == ANCHOR_READING_ID: raise _bad('STRUCTURE_INVALID:RESERVED_ID:%s' % r.id)
            if r.id in ids: raise _bad('STRUCTURE_INVALID:DUPLICATE_ID:%s' % r.id)
            ids[r.id] = r
        self._by_id = ids
        self._matches: Dict[str, List[Tuple[str, int]]] = {}
        for r in self.readings:
            for i, cross in enumerate(r.crosses):
                self._matches.setdefault(cell_key_of(cross), []).append((r.id, i))
        self._index_reader: Optional['_IndexReader'] = None

    @classmethod
    def empty(cls, lookup: Any = None, neighbors: Any = None, index: Optional[IndexSpec] = None) -> 'Structure':
        return cls((), lookup, neighbors, index)

    @classmethod
    def from_jsonl(cls, path: Any, lookup: Any = None, neighbors: Any = None, index: Optional[IndexSpec] = None) -> 'Structure':
        """Sentences from a jsonl file: one object per line, {"id", "text"} (other keys are ignored; "lang" is used when present)."""
        lookup = lookup if lookup is not None else EC.StubLookup()
        try:
            raw = Path(path).read_bytes()
            text = raw.decode('utf-8')
        except (OSError, UnicodeDecodeError) as exc:
            raise _bad('STRUCTURE_FILE_UNREADABLE:%s' % type(exc).__name__)
        readings: List[Reading] = []
        blank = 0
        for n, line in enumerate(text.splitlines(), 1):
            if not line.strip(): blank += 1; continue
            try:
                obj = json.loads(line)
            except ValueError:
                raise _bad('STRUCTURE_INVALID:line %d is not json' % n)
            if not isinstance(obj, Mapping) or not isinstance(obj.get('id'), str) or not obj['id'] or not isinstance(obj.get('text'), str):
                raise _bad('STRUCTURE_INVALID:line %d needs a string id and a string text' % n)
            lang = obj.get('lang')
            if lang is not None and lang not in ('ja', 'en'): raise _bad('STRUCTURE_INVALID:line %d has a bad lang' % n)
            readings.append(read_sentence(obj['id'], obj['text'], lang, lookup))
        return cls(readings, lookup, neighbors, index, hashlib.sha256(raw).hexdigest(), blank)

    @classmethod
    def from_injected(cls, items: Iterable[Mapping[str, Any]], lookup: Any = None, neighbors: Any = None,
                      index: Optional[IndexSpec] = None) -> 'Structure':
        """Readings written by hand: each item {"id", "text" (optional), "reading": a `verantyx.semantic_read/1` dict}. Public interface only."""
        lookup = lookup if lookup is not None else EC.StubLookup()
        readings = [injected_reading(it['id'], it.get('text'), it['reading'], lookup) for it in items]
        return cls(readings, lookup, neighbors, index)

    def reading(self, rid: str) -> Optional[Reading]:
        return self._by_id.get(rid)

    def matches(self, key: str) -> List[Tuple[str, int]]:
        return list(self._matches.get(key, ()))

    def index_reader(self) -> '_IndexReader':
        if self._index_reader is None: self._index_reader = _IndexReader(self)
        return self._index_reader

    def info(self) -> Dict[str, Any]:
        by_status = {s: 0 for s in ('CROSSED', 'ABSTAINED', 'INPUT_REJECTED', 'READ_ERROR')}
        by_source = {s: 0 for s in READING_SOURCES}
        for r in self.readings:
            by_status[r.status] += 1
            by_source[r.source] += 1
        index = None
        if self.index is not None:
            index = {'root_name': (self.index.root.name if self.index.root is not None else None), 'families': list(self.index.families),
                     'window': self.index.window}
        return {'file_sha256': self.file_sha, 'sentences': len(self.readings), 'blank_lines_skipped': self.blank_lines,
                'by_status': by_status, 'by_reading_source': by_source, 'index': index,
                'placement': _source_id(self.lookup), 'neighbors': _source_id(self.neighbors)}


# ---------------------------------------------------------------------------------------------------------------------------------
# the corpus index: occupancy by a sentence there, compared as a cross (P6)
# ---------------------------------------------------------------------------------------------------------------------------------
class _IndexReader:
    def __init__(self, structure: Structure):
        self._structure = structure
        self._corpus: Any = None
        self._searches: Dict[Tuple[str, str], Tuple[str, Tuple[Any, ...]]] = {}
        self._rows: Dict[str, Reading] = {}

    def _corpus_obj(self) -> Any:
        if self._corpus is None:
            from .ability_corpus import Corpus    # read-only: Corpus opens each database with mode=ro
            spec = self._structure.index
            self._corpus = Corpus(root=spec.root if spec is not None and spec.root is not None else None)
        return self._corpus

    def _search(self, surface: str, family: str) -> Tuple[str, Tuple[Any, ...]]:
        key = (family, surface)
        if key not in self._searches:
            hits = self._corpus_obj().search(surface, family, limit=self._structure.index.window)
            self._searches[key] = (hits.state, tuple(hits))
        return self._searches[key]

    def _read_row(self, text: str) -> Reading:
        if text not in self._rows:
            self._rows[text] = read_sentence('row', text, None, self._structure.lookup)
        return self._rows[text]

    def occupancy(self, key: str, surfaces: Sequence[str], family: str) -> 'OccupancySource':
        window = self._structure.index.window
        rows: Dict[Tuple[str, int], Any] = {}
        searches: List[Dict[str, Any]] = []
        unknown: List[str] = []
        saturated = False
        done: Dict[str, bool] = {}
        for surface in surfaces:
            if surface in done: continue
            done[surface] = True
            state, hits = self._search(surface, family)
            searches.append({'surface': surface, 'state': state, 'hits': len(hits)})
            if state.startswith('UNKNOWN_'): unknown.append(state); continue
            if len(hits) >= window: saturated = True
            for w in hits: rows[(w.family, w.id)] = w
        if not searches:
            # no surface to look up (a cell with no filler): the index was never asked, which is not the same as "nothing there" (decision E21)
            return OccupancySource('index:%s' % family, 'UNKNOWN_QUERY_NOT_SEARCHED', None,
                                   {'searches': [], 'rows_read': 0, 'rows_unreadable': 0, 'reason': 'NO_SURFACE_TO_SEARCH'})
        read = unreadable = 0
        for rk in sorted(rows):
            w = rows[rk]
            reading = self._read_row(w.text)
            read += 1
            if reading.status != 'CROSSED': unreadable += 1; continue
            for i, cross in enumerate(reading.crosses):
                if cell_key_of(cross) == key:
                    witness = {'family': w.family, 'id': w.id, 'origin': w.origin, 'generator': w.generator, 'cross_index': i}
                    return OccupancySource('index:%s' % family, 'ATTESTED', [witness],
                                           {'searches': searches, 'rows_read': read, 'rows_unreadable': unreadable})
        detail = {'searches': searches, 'rows_read': read, 'rows_unreadable': unreadable}
        if unknown: return OccupancySource('index:%s' % family, unknown[0], None, detail)
        if saturated: return OccupancySource('index:%s' % family, 'UNKNOWN_WINDOW_SATURATED', None, detail)
        return OccupancySource('index:%s' % family, 'UNOCCUPIED', None, detail)


@dataclass(frozen=True)
class OccupancySource:
    source: str                                   # structure | index:<family> | index (no index asked)
    state: str
    witness: Optional[List[Dict[str, Any]]]
    detail: Mapping[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {'source': self.source, 'state': self.state, 'witness': copy.deepcopy(self.witness), 'detail': copy.deepcopy(dict(self.detail))}


@dataclass(frozen=True)
class Occupancy:
    sources: Tuple[OccupancySource, ...]

    @property
    def occupied(self) -> str:
        """ATTESTED when any source attests; UNOCCUPIED when every source is UNOCCUPIED; else the first UNKNOWN_* in the order the
        sources were asked (structure first, then the families as given). Sources are never added up."""
        if any(s.state == 'ATTESTED' for s in self.sources): return 'ATTESTED'
        if all(s.state == 'UNOCCUPIED' for s in self.sources): return 'UNOCCUPIED'
        return next(s.state for s in self.sources if s.state.startswith('UNKNOWN_'))

    @property
    def basis_origin(self) -> Optional[str]:
        for s in self.sources:
            if s.state == 'ATTESTED' and s.witness and any(w.get('origin') == 'generated' for w in s.witness): return 'generated'
        return None


def _occupancy(cell: 'Cell', structure: Structure, anchor_reading: Optional[Reading]) -> Occupancy:
    witnesses: List[Dict[str, Any]] = [{'reading': rid, 'cross_index': i} for rid, i in structure.matches(cell.key)]
    if anchor_reading is not None:
        witnesses.extend({'reading': ANCHOR_READING_ID, 'cross_index': i} for i, c in enumerate(anchor_reading.crosses) if cell_key_of(c) == cell.key)
    witnesses.sort(key=_cj)    # a display order of witnesses, not a choice
    sources: List[OccupancySource] = [OccupancySource('structure', 'ATTESTED' if witnesses else 'UNOCCUPIED', witnesses or None, {})]
    if structure.index is None:
        sources.append(OccupancySource('index', 'UNKNOWN_NO_INDEX', None, {'reason': 'NO_INDEX_REQUESTED'}))
    else:
        reader = structure.index_reader()
        surfaces = _surfaces_of(cell.cross)
        for family in structure.index.families:
            sources.append(reader.occupancy(cell.key, surfaces, family))
    return Occupancy(tuple(sources))


# ---------------------------------------------------------------------------------------------------------------------------------
# viewpoint (types)
# ---------------------------------------------------------------------------------------------------------------------------------
@dataclass(frozen=True)
class AnchorText:
    """A sentence typed by a person (`question`) or taken as a seed (`seed`). `reading` is a hand-written reader output (public interface only)."""
    kind: str = 'seed'
    text: str = ''
    lang: Optional[str] = None
    cross_index: Optional[int] = None
    reading: Optional[Mapping[str, Any]] = field(default=None, compare=False, repr=False)


@dataclass(frozen=True)
class AnchorRecord:
    """A sentence of the structure, by its id."""
    id: str
    cross_index: Optional[int] = None


@dataclass(frozen=True)
class FaceSwap:
    role: str


@dataclass(frozen=True)
class Edge:
    relation: str


@dataclass(frozen=True)
class Viewpoint:
    anchor: Any
    direction: Tuple[Any, ...] = ()
    range: Optional[int] = None
    state: Any = FLAT

    def __post_init__(self) -> None:
        if isinstance(self.anchor, AnchorText):
            if self.anchor.kind not in ANCHOR_KINDS: raise _bad('ANCHOR_KIND_NOT_IN_CLOSED_LIST:%s' % (self.anchor.kind,))
        elif not isinstance(self.anchor, AnchorRecord):
            raise _bad('ANCHOR_TYPE')
        for move in self.direction:
            if isinstance(move, FaceSwap):
                if move.role not in EC.ROLE_NAMES: raise _bad('FACE_SWAP_ROLE_NOT_IN_CONVENTION:%s' % (move.role,))
            elif isinstance(move, Edge):
                if move.relation not in EC.RELATION_TYPES: raise _bad('EDGE_RELATION_NOT_IN_CONVENTION:%s' % (move.relation,))
            else:
                raise _bad('MOVE_TYPE')
        if self.range is not None:
            if not isinstance(self.range, int) or isinstance(self.range, bool) or not 0 <= self.range <= len(self.direction):
                raise _bad('RANGE_OUT_OF_BOUNDS:%r (0..%d)' % (self.range, len(self.direction)))

    @property
    def effective_range(self) -> int:
        return len(self.direction) if self.range is None else self.range


def parse_direction(spec: str) -> Tuple[Any, ...]:
    """`FACE_SWAP:agent,EDGE:relative` -> moves. A closed syntax: no spaces, role / relation from the convention's closed lists."""
    if spec == '': return ()
    moves: List[Any] = []
    for part in spec.split(','):
        name, sep, arg = part.partition(':')
        if not sep or not arg or arg != arg.strip() or name != name.strip(): raise _bad('DIRECTION_SYNTAX:%r' % part)
        if name == FACE_SWAP:
            if arg not in EC.ROLE_NAMES: raise _bad('FACE_SWAP_ROLE_NOT_IN_CONVENTION:%s' % arg)
            moves.append(FaceSwap(arg))
        elif name == EDGE:
            if arg not in EC.RELATION_TYPES: raise _bad('EDGE_RELATION_NOT_IN_CONVENTION:%s' % arg)
            moves.append(Edge(arg))
        else:
            raise _bad('DIRECTION_MOVE_NOT_IN_CLOSED_LIST:%s' % name)
    return tuple(moves)


def _move_json(move: Any) -> Dict[str, Any]:
    return {'move': FACE_SWAP, 'role': move.role} if isinstance(move, FaceSwap) else {'move': EDGE, 'relation': move.relation}


def _state_info(state: Any) -> Dict[str, Any]:
    if SAL.is_flat(state): return {'kind': 'FLAT'}
    evs = list(state.events())
    return {'kind': 'LEDGER', 'events': len(evs), 'last_seq': evs[-1]['seq'] if evs else 0}


def viewpoint_to_dict(vp: Viewpoint, state_info: Mapping[str, Any]) -> Dict[str, Any]:
    a = vp.anchor
    if isinstance(a, AnchorText):
        anchor = {'type': 'AnchorText', 'kind': a.kind, 'text': a.text, 'lang': a.lang, 'cross_index': a.cross_index,
                  'reading_source': 'injected' if a.reading is not None else 'semantic_read'}
    else:
        anchor = {'type': 'AnchorRecord', 'id': a.id, 'cross_index': a.cross_index}
    return {'anchor': anchor, 'direction': [_move_json(m) for m in vp.direction], 'range': vp.effective_range, 'state': dict(state_info)}


def viewpoint_from_dict(d: Mapping[str, Any], anchor_reading: Optional[Mapping[str, Any]] = None) -> Viewpoint:
    """The viewpoint of a recorded observation (state left FLAT: replay supplies the ledger). An injected anchor needs its reading again."""
    a = d['anchor']
    if a['type'] == 'AnchorText':
        if a.get('reading_source') == 'injected' and anchor_reading is None: raise _bad('INJECTED_ANCHOR_NEEDS_ITS_READING')
        anchor: Any = AnchorText(a['kind'], a['text'], a.get('lang'), a.get('cross_index'), anchor_reading if a.get('reading_source') == 'injected' else None)
    else:
        anchor = AnchorRecord(a['id'], a.get('cross_index'))
    moves = tuple(FaceSwap(m['role']) if m['move'] == FACE_SWAP else Edge(m['relation']) for m in d['direction'])
    return Viewpoint(anchor, moves, d['range'])


# ---------------------------------------------------------------------------------------------------------------------------------
# cells and moves
# ---------------------------------------------------------------------------------------------------------------------------------
@dataclass(frozen=True)
class Cell:
    key: str
    cross: EC.EventCross
    coords: Tuple[Mapping[str, Any], ...]          # every path (origin + moves) that reached this cell at its distance, in string order
    cross_origin: str                              # read:semantic_read | read:injected | constructed:face_swap
    lang: Optional[str]

    @property
    def coord(self) -> Mapping[str, Any]:
        return self.coords[0]

    @property
    def distance(self) -> int:
        return len(self.coords[0]['moves'])


def _make_cell(cross: EC.EventCross, coord: Mapping[str, Any], cross_origin: str, lang: Optional[str]) -> Cell:
    return Cell(cell_key_of(cross), cross, (coord,), cross_origin, lang)


def _extended(cell: Cell, move: Mapping[str, Any]) -> Tuple[Mapping[str, Any], ...]:
    """EVERY coordinate of `cell` followed by `move` (W5-b, A2): a cell that several paths reached passes all of them on, not only the first."""
    return tuple({'origin': c['origin'], 'moves': list(c['moves']) + [move]} for c in cell.coords)


@dataclass(frozen=True)
class NoAnchor:
    reason: str
    detail: Mapping[str, Any]


@dataclass(frozen=True)
class NoMoveLicensed:
    reasons: Mapping[str, int]


@dataclass(frozen=True)
class Tie:
    candidates: Tuple[str, ...]


@dataclass(frozen=True)
class Focus:
    cell_key: str


def _resolve_anchor(vp: Viewpoint, structure: Structure, lookup: Any) -> Any:
    """(cell, reading of the anchor sentence or None when the anchor is a record) or NoAnchor."""
    a = vp.anchor
    if isinstance(a, AnchorRecord):
        reading = structure.reading(a.id)
        if reading is None: return NoAnchor('RECORD_NOT_IN_STRUCTURE', {'id': a.id})
        origin = {'kind': 'structure', 'id': a.id}
        anchor_reading: Optional[Reading] = None
    else:
        reading = (injected_reading(ANCHOR_READING_ID, a.text, a.reading, lookup) if a.reading is not None
                   else read_sentence(ANCHOR_READING_ID, a.text, a.lang, lookup))
        origin = {'kind': 'anchor', 'id': ANCHOR_READING_ID}
        anchor_reading = reading
    if reading.status == 'READ_ERROR': return NoAnchor('READ_ERROR:%s' % reading.abstain['type'], copy.deepcopy(dict(reading.abstain)))
    if reading.status == 'ABSTAINED': return NoAnchor('READER_ABSTAINED', copy.deepcopy(dict(reading.abstain or {})))
    if reading.status == 'INPUT_REJECTED': return NoAnchor('READER_INPUT_REJECTED', copy.deepcopy(dict(reading.abstain or {})))
    index = a.cross_index
    if index is None:
        if len(reading.crosses) != 1:
            return NoAnchor('ANCHOR_CROSS_AMBIGUOUS', {'candidates': [cell_key_of(c) for c in reading.crosses]})    # not chosen
        index = 0
    elif not isinstance(index, int) or isinstance(index, bool) or not 0 <= index < len(reading.crosses):
        return NoAnchor('ANCHOR_CROSS_INDEX_OUT_OF_RANGE', {'cross_index': index, 'crosses': len(reading.crosses)})
    coord = {'origin': dict(origin, cross_index=index), 'moves': []}
    return _make_cell(reading.crosses[index], coord, 'read:' + reading.source, reading.lang), anchor_reading


def _anchor_sentence(vp: Viewpoint, structure: Structure) -> Optional[str]:
    """The sentence the anchor stands for: the text of an `AnchorText`, the text of the structure's sentence for an `AnchorRecord` (None when it has none).
    Stage ii skips a ledger utterance equal to it (docs/OBSERVATION.md, P8 as changed in change record 3)."""
    a = vp.anchor
    if isinstance(a, AnchorText): return a.text
    reading = structure.reading(a.id)
    return reading.text if reading is not None else None


def _synthetic_output(cell: Cell, role: str, new_surface: str) -> Dict[str, Any]:
    """A reader output with the one clause of `cell` in which ONLY `role` has another filler: it goes through `build_crosses` like any reading."""
    roles: Dict[str, Any] = {}
    for r, arm in cell.cross.arms.items():
        values = [f.surface for f in arm.fillers]
        roles[r] = values if arm.kind == 'ARM_TIE' else values[0]
    roles[role] = new_surface
    clause = copy.deepcopy(dict(cell.cross.center))
    clause['roles'] = roles
    meta = {'rule': cell.cross.provenance.get('rule'), 'span': copy.deepcopy(cell.cross.provenance.get('span'))}
    return {'schema': EC.SOURCE_SCHEMA, 'lang': cell.lang, 'readable': True, 'clauses': [clause], 'relations': [], 'abstain': None,
            'unsupported': [], 'clause_meta': [meta]}


def _try_swap(cell: Cell, role: str, to: str, lookup: Any, neighbor_source_id: str) -> Tuple[Optional[Cell], Optional[str]]:
    """The cell with `role`'s filler replaced by `to`, when the W3-b type agreement of that arm is AGREE; else (None, reason)."""
    arm = cell.cross.arms[role]
    crossed = EC.build_crosses(_synthetic_output(cell, role, to), lookup)
    if crossed.status != 'CROSSED' or len(crossed.crosses) != 1: return None, 'SYNTHETIC_READING_REJECTED'
    new_cross = crossed.crosses[0]
    verdict = new_cross.arms[role].agreement
    if verdict.verdict == 'DISAGREE': return None, 'DISAGREE'
    if verdict.verdict == 'NOT_CHECKED': return None, 'NOT_CHECKED:%s' % verdict.reason
    move = {'move': FACE_SWAP, 'role': role, 'from': arm.fillers[0].surface, 'to': to, 'neighbor_source': neighbor_source_id}
    return Cell(cell_key_of(new_cross), new_cross, _extended(cell, move), 'constructed:face_swap', cell.lang), None


def _swap_gate(cell: Cell, role: str, neighbors: Any) -> Tuple[Optional[NeighborResult], Optional[str]]:
    """The cell-level licence of FACE_SWAP(role) (P4), from the top. (neighbours, None) when the arm may be swapped, else (None, reason)."""
    arm = cell.cross.arms.get(role)
    if arm is None: return None, 'NO_ARM'
    if arm.kind == 'ARM_TIE': return None, 'ARM_TIE'
    if role not in EC.EXPECTED_TYPES: return None, 'ROLE_NOT_IN_TABLE'
    got = _neighbors_of(neighbors, arm.fillers[0].head)
    if got.state == INVALID_NEIGHBORS: return None, 'NEIGHBORS_RESULT_INVALID'
    if got.state != 'FOUND': return None, got.state
    return got, None


def _edge_targets(cell: Cell, relation: str, structure: Structure, anchor_reading: Optional[Reading]) -> List[Tuple[Cell, Dict[str, Any]]]:
    """(target cell, the move) for every relation of this type that a reading holds about a cross with the content of `cell` (P5)."""
    sources: List[Tuple[Reading, int]] = []
    if anchor_reading is not None:
        sources.extend((anchor_reading, i) for i, c in enumerate(anchor_reading.crosses) if cell_key_of(c) == cell.key)
    for rid, i in structure.matches(cell.key):
        sources.append((structure.reading(rid), i))
    found: List[Tuple[Cell, Dict[str, Any]]] = []
    for reading, i in sources:
        for rel in reading.relations:
            if rel.get('type') != relation: continue
            if rel['from'] == i and rel['to'] != i: j, direction = rel['to'], 'forward'
            elif rel['to'] == i and rel['from'] != i: j, direction = rel['from'], 'backward'
            else: continue
            move = {'move': EDGE, 'relation': relation, 'reading': reading.id, 'from': i, 'to': j, 'dir': direction}
            target = reading.crosses[j]
            found.append((Cell(cell_key_of(target), target, _extended(cell, move), 'read:' + reading.source, reading.lang), move))
    return found


# ---------------------------------------------------------------------------------------------------------------------------------
# elements, observation
# ---------------------------------------------------------------------------------------------------------------------------------
def _realization(cell: Cell, claim: str, provenance: str) -> Dict[str, Any]:
    from . import semantic_realize as SR
    center = copy.deepcopy(dict(cell.cross.center))
    arms = {role: arm.to_dict() for role, arm in cell.cross.arms.items()}
    rule = cell.cross.provenance.get('rule')
    got = SR.realize_observed(center, arms, cell.lang, cell_id=cell.key, rule=rule)
    if not isinstance(got, SR.Realized):
        return {'status': 'REFUSED', 'reason': got.reason, 'detail': got.detail}
    alternatives: List[Dict[str, Any]] = []
    refused: List[str] = []
    for v in SR.observed_variants(center, arms, cell.lang, cell_id=cell.key, rule=rule):
        if isinstance(v, SR.Realized):
            alternatives.append({'text': v.text, 'style': v.style, 'topic': v.checks['variant']['topic'], 'role_order': v.checks['variant']['role_order']})
        else:
            refused.append(v.reason)
    return {'status': 'REALIZED', 'text': got.text, 'lang': cell.lang, 'style': got.style, 'derivation': got.derivation,
            'claim': claim, 'provenance': provenance, 'checks': got.checks, 'alternatives': alternatives, 'alternatives_refused': refused}


def _claim_of(occupancy: Occupancy) -> Tuple[str, str]:
    occ = occupancy.occupied
    if occ == 'ATTESTED': return 'OBSERVED_OCCUPIED', 'observed:attested'
    if occ == 'UNOCCUPIED': return 'CONSTRUCTED_UNOCCUPIED', 'constructed:observed_unoccupied'
    return 'UNKNOWN_OCCUPANCY', 'observed:occupancy_unknown:%s' % occ


@dataclass(frozen=True)
class ObservedElement:
    cell: Cell
    occupancy: Occupancy
    claim: str
    provenance: str
    realization: Mapping[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        cell = self.cell
        moved = None
        moves = cell.coord['moves']
        if moves and moves[-1]['move'] == FACE_SWAP:    # a cell reached by an EDGE is another cross: no arm of it was swapped
            last = moves[-1]
            moved = {'role': last['role'], 'from': last['from'], 'to': last['to'], 'agreement': cell.cross.arms[last['role']].agreement.to_dict()}
        return {'cell_key': cell.key, 'coords': copy.deepcopy([dict(c) for c in cell.coords]), 'distance': cell.distance,
                'cross': cell.cross.to_dict(), 'cross_origin': cell.cross_origin,
                'type_agreement': {'by_arm': {r: a.agreement.to_dict() for r, a in cell.cross.arms.items()}, 'moved_arm': moved},
                'occupancy': [s.to_dict() for s in self.occupancy.sources], 'occupied': self.occupancy.occupied,
                'claim': self.claim, 'provenance': self.provenance, 'basis_origin': self.occupancy.basis_origin,
                'realization': copy.deepcopy(dict(self.realization))}


@dataclass(frozen=True)
class Observation:
    viewpoint: Mapping[str, Any]
    structure: Mapping[str, Any]
    anchor: Optional[ObservedElement]
    ranks: Tuple[Tuple[ObservedElement, ...], ...]
    focus: Any                                      # Focus | Tie | NoAnchor | NoMoveLicensed
    counts: Mapping[str, Any]
    salience_trace: Mapping[str, Any]
    state_info: Mapping[str, Any]

    @property
    def outcome(self) -> str:
        return {Focus: 'FOCUS', Tie: 'TIE', NoAnchor: 'NO_ANCHOR', NoMoveLicensed: 'NO_MOVE_LICENSED'}[type(self.focus)]

    def elements(self) -> List[ObservedElement]:
        out = [e for group in self.ranks for e in group]
        return ([self.anchor] if self.anchor is not None else []) + [e for e in out if self.anchor is None or e.cell.key != self.anchor.cell.key]

    def element_for(self, key: str) -> Optional[ObservedElement]:
        return next((e for e in self.elements() if e.cell.key == key), None)

    def to_dict(self) -> Dict[str, Any]:
        focus = self.focus
        realization: Any = None
        if isinstance(focus, Focus):
            fe = self.element_for(focus.cell_key)
            focus_json: Dict[str, Any] = {'kind': 'FOCUS', 'cell_key': focus.cell_key}
            realization = copy.deepcopy(dict(fe.realization)) if fe is not None else None
        elif isinstance(focus, Tie):
            focus_json = {'kind': 'TIE', 'candidates': list(focus.candidates)}
            realization = [{'cell_key': k, 'realization': copy.deepcopy(dict(self.element_for(k).realization))} for k in focus.candidates]
        elif isinstance(focus, NoAnchor):
            focus_json = {'kind': 'NO_ANCHOR', 'reason': focus.reason}
        else:
            focus_json = {'kind': 'NO_MOVE_LICENSED'}
        abstain = None
        if isinstance(focus, NoAnchor):
            abstain = {'type': 'NO_ANCHOR', 'reason': focus.reason, 'detail': copy.deepcopy(dict(focus.detail))}
        elif isinstance(focus, NoMoveLicensed):
            abstain = {'type': 'NO_MOVE_LICENSED', 'reasons': dict(focus.reasons)}
        ranks = [{'rank': i + 1, 'kind': 'SINGLE' if len(g) == 1 else 'TIE', 'elements': [e.to_dict() for e in g]} for i, g in enumerate(self.ranks)]
        return {'schema': SCHEMA, 'viewpoint': copy.deepcopy(dict(self.viewpoint)), 'structure': copy.deepcopy(dict(self.structure)),
                'anchor': self.anchor.to_dict() if self.anchor is not None else None, 'ranks': ranks, 'focus': focus_json,
                'realization': realization, 'abstain': abstain, 'counts': copy.deepcopy(dict(self.counts)),
                'salience_trace': copy.deepcopy(dict(self.salience_trace))}


def to_json(observation: Observation) -> str:
    """One line of json. The key order is fixed by construction; nothing in it depends on time or on the environment."""
    return json.dumps(observation.to_dict(), ensure_ascii=False, separators=(',', ':'))


def _new_counts() -> Dict[str, Any]:
    from . import semantic_realize as SR    # inside the function, as the other users of the realizer do
    return {
        'candidates': 0, 'revisits_dropped': 0,
        'moves': {
            FACE_SWAP: {'cells_tried': 0, 'cells_unlicensed': {r: 0 for r in FACE_CELL_REASONS}, 'candidates_tried': 0,
                        'candidates_skipped_same_as_original': 0, 'candidates_unlicensed': {r: 0 for r in FACE_CANDIDATE_REASONS}, 'licensed': 0},
            EDGE: {'cells_tried': 0, 'cells_unlicensed': {r: 0 for r in EDGE_CELL_REASONS}, 'licensed': 0,
                   'licensed_by_reading_source': {s: 0 for s in READING_SOURCES}},
        },
        'occupancy': {s: 0 for s in OCCUPANCY_STATES}, 'claims': {c: 0 for c in CLAIMS},
        'realization': {'realized': 0, 'refused': {r: 0 for r in sorted(SR.REFUSAL_REASONS - set(REFUSAL_NOT_ON_THIS_PATH))}},    # a frozenset: sorted before use, so zero counts are listed in a fixed order
    }


def _apply_move(move: Any, cell: Cell, structure: Structure, lookup: Any, neighbors: Any, anchor_reading: Optional[Reading],
                counts: Dict[str, Any]) -> List[Cell]:
    if isinstance(move, FaceSwap):
        c = counts['moves'][FACE_SWAP]
        c['cells_tried'] += 1
        got, reason = _swap_gate(cell, move.role, neighbors)
        if reason is not None:
            c['cells_unlicensed'][reason] += 1
            return []
        here = cell.cross.arms[move.role].fillers[0].surface
        out: List[Cell] = []
        for word in got.items:    # already a set in string order
            if word == here: c['candidates_skipped_same_as_original'] += 1; continue
            c['candidates_tried'] += 1
            new, why = _try_swap(cell, move.role, word, lookup, _source_id(neighbors))
            if new is None: c['candidates_unlicensed'][why] += 1; continue
            c['licensed'] += 1
            out.append(new)
        if not out: c['cells_unlicensed']['NO_CANDIDATE_LICENSED'] += 1
        return out
    c = counts['moves'][EDGE]
    c['cells_tried'] += 1
    targets = _edge_targets(cell, move.relation, structure, anchor_reading)
    if not targets:
        c['cells_unlicensed']['NO_RELATION_IN_STRUCTURE'] += 1
        return []
    for new, _move in targets:
        c['licensed'] += 1
        c['licensed_by_reading_source'][new.cross_origin.split(':', 1)[1] if new.cross_origin.startswith('read:') else 'semantic_read'] += 1
    return [t[0] for t in targets]


def _changed_fillers(cell: Cell, anchor: Cell) -> Tuple[str, ...]:
    base = set(_surfaces_of(anchor.cross))
    return tuple(sorted({s for s in _surfaces_of(cell.cross) if s not in base}))


def _levels(viewpoint: Viewpoint, structure: Structure, lookup: Any, neighbors: Any, anchor: Cell, anchor_reading: Optional[Reading],
            counts: Dict[str, Any]) -> List[Cell]:
    """The observable cells: apply direction[k-1] to every cell of level k-1 (P3). Depends on (structure, viewpoint) only, never on the ledger:
    `reobserve` runs it again to check that the coordinates of an element are all the paths there are."""
    seen: Dict[str, int] = {anchor.key: 0}
    level: List[Cell] = [anchor]
    observable: List[Cell] = []
    for k in range(1, viewpoint.effective_range + 1):
        move = viewpoint.direction[k - 1]
        raw: Dict[str, List[Cell]] = {}
        for cell in sorted(level, key=lambda c: c.key):    # the order only fixes the order of work, never a winner
            for new in _apply_move(move, cell, structure, lookup, neighbors, anchor_reading, counts):
                if new.key in seen:
                    counts['revisits_dropped'] += 1
                    continue
                raw.setdefault(new.key, []).append(new)
        level = []
        for key in sorted(raw):
            # every path of every cell of the group, without repeats, in canonical-json string order (W5-b, A2). The cross shown is the one of
            # the cell that owns the first coordinate (a way of showing, not a winner: the cells of a group have the same content).
            by_text: Dict[str, Mapping[str, Any]] = {}
            for c in raw[key]:
                for co in c.coords: by_text.setdefault(_cj(co), co)
            group = sorted(raw[key], key=lambda c: min(_cj(co) for co in c.coords))
            merged = replace(group[0], coords=tuple(by_text[t] for t in sorted(by_text)))
            seen[key] = k
            level.append(merged)
            observable.append(merged)
    return observable


def observe(viewpoint: Viewpoint, structure: Structure, lookup: Any = None, neighbors: Any = None, ledger: Any = None) -> Observation:
    """Observe `structure` from `viewpoint`. The state is `ledger` when given, else `viewpoint.state` (FLAT when there is none).
    Deterministic in (structure, viewpoint, state); the ledger is only read."""
    q = _observe_question(viewpoint, structure, lookup, neighbors, ledger)    # W3-c2: an anchor that is a question has a path of its own
    if q is not None: return q
    lookup = lookup if lookup is not None else structure.lookup
    neighbors = neighbors if neighbors is not None else structure.neighbors
    state = ledger if ledger is not None else viewpoint.state
    state_info = _state_info(state)
    vp_json = viewpoint_to_dict(viewpoint, state_info)
    counts = _new_counts()
    info = structure.info()
    resolved = _resolve_anchor(viewpoint, structure, lookup)
    if isinstance(resolved, NoAnchor):
        trace = SAL.rank([], state).trace
        return Observation(vp_json, info, None, (), resolved, counts, trace, state_info)
    anchor, anchor_reading = resolved
    observable = _levels(viewpoint, structure, lookup, neighbors, anchor, anchor_reading, counts)
    counts['candidates'] = len(observable)
    # --- the elements: occupancy, claim, realization (every source separately)
    realized_cache: Dict[Tuple[str, Optional[str]], Dict[str, Any]] = {}

    def element(cell: Cell) -> ObservedElement:
        occupancy = _occupancy(cell, structure, anchor_reading)
        claim, provenance = _claim_of(occupancy)
        ck = (cell.key, cell.lang)
        if ck not in realized_cache: realized_cache[ck] = _realization(cell, claim, provenance)
        realization = realized_cache[ck]
        counts['occupancy'][occupancy.occupied] += 1
        counts['claims'][claim] += 1
        if realization['status'] == 'REALIZED': counts['realization']['realized'] += 1
        else: counts['realization']['refused'][realization['reason']] = counts['realization']['refused'].get(realization['reason'], 0) + 1
        return ObservedElement(cell, occupancy, claim, provenance, realization)

    anchor_element = element(anchor)
    elements: Dict[str, ObservedElement] = {c.key: element(c) for c in observable}
    # --- the field
    def neighbor_items(word: str) -> Tuple[str, ...]:
        got = _neighbors_of(neighbors, word)
        return got.items if got.state == 'FOUND' else ()

    ctx = SAL.build_context(state, neighbor_items, _anchor_sentence(viewpoint, structure))
    directed = viewpoint.effective_range > 0
    if directed:
        pool = [SAL.Candidate(c.key, c.distance, _changed_fillers(c, anchor)) for c in observable]
    else:
        pool = [SAL.Candidate(anchor.key, 0, ())]
    ranking = SAL.rank(pool, state, ctx)
    by_key = dict(elements)
    by_key[anchor.key] = anchor_element
    ranks = tuple(tuple(by_key[k] for k in group) for group in ranking.ranks)
    focus: Any
    if not pool:
        reasons: Dict[str, int] = {}
        for mname, mc in counts['moves'].items():
            for r, n in mc['cells_unlicensed'].items():
                if n: reasons['%s:%s' % (mname, r)] = n
            for r, n in mc.get('candidates_unlicensed', {}).items():
                if n: reasons['%s:candidate:%s' % (mname, r)] = n
        focus = NoMoveLicensed(reasons)
    elif len(ranking.ranks[0]) == 1:
        focus = Focus(ranking.ranks[0][0])
    else:
        focus = Tie(tuple(ranking.ranks[0]))
    return Observation(vp_json, info, anchor_element, ranks, focus, counts, ranking.trace, state_info)


# ---------------------------------------------------------------------------------------------------------------------------------
# re-observation (O2): walk the coordinate again from the structure
# ---------------------------------------------------------------------------------------------------------------------------------
def _cross_without_provenance(cross_dict: Mapping[str, Any]) -> str:
    d = dict(cross_dict)
    d.pop('provenance', None)
    return _cj(d)


def _replay_coord(coord: Mapping[str, Any], vp: Viewpoint, structure: Structure, lookup: Any, neighbors: Any) -> Any:
    """The cell that `coord` reaches, or a reason string (the first step that does not hold)."""
    origin = coord['origin']
    anchor_reading: Optional[Reading] = None
    if isinstance(vp.anchor, AnchorText):    # the anchor sentence's own reading is part of what can be observed (D1 c)
        anchor_reading = (injected_reading(ANCHOR_READING_ID, vp.anchor.text, vp.anchor.reading, lookup) if vp.anchor.reading is not None
                          else read_sentence(ANCHOR_READING_ID, vp.anchor.text, vp.anchor.lang, lookup))
    if origin['kind'] == 'anchor':
        reading = anchor_reading
        if reading is None: return 'ORIGIN_IS_ANCHOR_BUT_VIEWPOINT_ANCHOR_IS_A_RECORD'
    else:
        reading = structure.reading(origin['id'])
        if reading is None: return 'ORIGIN_RECORD_NOT_IN_STRUCTURE'
    if reading.status != 'CROSSED': return 'ORIGIN_NOT_READ:%s' % reading.status
    if not isinstance(origin['cross_index'], int) or not 0 <= origin['cross_index'] < len(reading.crosses): return 'ORIGIN_CROSS_INDEX_OUT_OF_RANGE'
    cell = _make_cell(reading.crosses[origin['cross_index']], {'origin': dict(origin), 'moves': []}, 'read:' + reading.source, reading.lang)
    for move in coord['moves']:
        if move['move'] == FACE_SWAP:
            role = move['role']
            arm = cell.cross.arms.get(role)
            if arm is None or arm.kind != 'FILLER' or arm.fillers[0].surface != move['from']: return 'FACE_SWAP_FROM_DOES_NOT_MATCH'
            got, reason = _swap_gate(cell, role, neighbors)
            if reason is not None: return 'FACE_SWAP_NOT_LICENSED:%s' % reason
            if move['to'] == move['from'] or move['to'] not in got.items: return 'FACE_SWAP_TO_NOT_A_NEIGHBOR'
            if move.get('neighbor_source') != _source_id(neighbors): return 'FACE_SWAP_NEIGHBOR_SOURCE_DIFFERS'
            new, why = _try_swap(cell, role, move['to'], lookup, _source_id(neighbors))
            if new is None: return 'FACE_SWAP_NOT_LICENSED:%s' % why
            cell = new
        elif move['move'] == EDGE:
            found = [c for c, m in _edge_targets(cell, move['relation'], structure, anchor_reading) if _cj(m) == _cj(move)]
            if not found: return 'EDGE_NOT_IN_STRUCTURE'
            cell = found[0]
        else:
            return 'MOVE_NOT_IN_CLOSED_LIST'
    return cell


def reobserve(element: Any, viewpoint: Viewpoint, structure: Structure, lookup: Any = None, neighbors: Any = None) -> Dict[str, Any]:
    """Walk every coordinate of an observed element again from the structure. REOBSERVED when each coordinate reaches a cell with the
    element's cell key, the first coordinate reaches a cross whose canonical json is byte-identical to the element's, the other coordinates
    reach the same cross apart from its provenance (the clause index and span of the sentence it came through), and the sentence of the
    realization (if any) is read again to the same cell, and the viewpoint and structure observed again hold exactly this set of coordinates for
    the cell (COORDS_INCOMPLETE when one is missing, COORDS_EXTRA when one is not a path there, COORDS_DUPLICATED when one is carried twice, CELL_NOT_OBSERVED when the cell is not there).
    Otherwise MISMATCH with the first reason."""
    d = element.to_dict() if isinstance(element, ObservedElement) else element
    lookup = lookup if lookup is not None else structure.lookup
    neighbors = neighbors if neighbors is not None else structure.neighbors
    for n, coord in enumerate(d['coords']):
        got = _replay_coord(coord, viewpoint, structure, lookup, neighbors)
        if isinstance(got, str): return {'status': 'MISMATCH', 'reason': got}
        if got.key != d['cell_key']: return {'status': 'MISMATCH', 'reason': 'CELL_KEY_DIFFERS'}
        have = got.cross.to_dict()
        if n == 0 and _cj(have) != _cj(d['cross']): return {'status': 'MISMATCH', 'reason': 'CROSS_BYTES_DIFFER'}
        if n > 0 and _cross_without_provenance(have) != _cross_without_provenance(d['cross']): return {'status': 'MISMATCH', 'reason': 'CROSS_DIFFERS_ON_A_LATER_COORD'}
    real = d.get('realization') or {}
    if real.get('status') == 'REALIZED':
        from . import semantic_read
        try:
            out = semantic_read.read(real['text'], 'ja')
        except Exception as exc:
            return {'status': 'MISMATCH', 'reason': 'REALIZATION_NOT_READ:%s' % type(exc).__name__}
        crossed = EC.build_crosses(out, lookup)
        if crossed.status != 'CROSSED' or len(crossed.crosses) != 1 or cell_key_of(crossed.crosses[0]) != d['cell_key']:
            return {'status': 'MISMATCH', 'reason': 'REALIZATION_NOT_REREAD_TO_THE_CELL'}
    # completeness (W5-b, A2): the coordinates the element carries are ALL the paths that reach its cell. Observe again from the same viewpoint
    # and structure (no ledger: the cells and their coordinates do not depend on it) and compare the sets of coordinates. A missing path is
    # not "fine because the rest replay": the promise is every path.
    resolved = _resolve_anchor(viewpoint, structure, lookup)
    if isinstance(resolved, NoAnchor): return {'status': 'MISMATCH', 'reason': 'CELL_NOT_OBSERVED'}
    anchor, anchor_reading = resolved
    cells: Dict[str, Cell] = {c.key: c for c in _levels(viewpoint, structure, lookup, neighbors, anchor, anchor_reading, _new_counts())}
    cells[anchor.key] = anchor
    again = cells.get(d['cell_key'])
    if again is None: return {'status': 'MISMATCH', 'reason': 'CELL_NOT_OBSERVED'}
    have, got = {_cj(c) for c in again.coords}, {_cj(c) for c in d['coords']}
    if have - got: return {'status': 'MISMATCH', 'reason': 'COORDS_INCOMPLETE'}
    if got - have: return {'status': 'MISMATCH', 'reason': 'COORDS_EXTRA'}
    # the same set is not yet "exactly what observe gives": observe writes each path once, so a coordinate carried twice is not what it gave
    if len(d['coords']) != len(got): return {'status': 'MISMATCH', 'reason': 'COORDS_DUPLICATED'}
    return {'status': 'REOBSERVED', 'reason': None}


# ---------------------------------------------------------------------------------------------------------------------------------
# the ledger: one turn (P9) and replay
# ---------------------------------------------------------------------------------------------------------------------------------
def record_turn(ledger: Any, viewpoint: Viewpoint, observation: Observation) -> List[str]:
    """Append the turn to the ledger: the utterance (when a person said something), then the observation. A TIE writes NO `observed_cell`
    (its candidates go into one event), so the order of candidates never makes a winner at the next turn. Returns the new event ids."""
    ids: List[str] = []
    a = viewpoint.anchor
    if isinstance(a, AnchorText):
        ids.append(ledger.append({'kind': 'utterance', 'payload': {'text': a.text, 'anchor': a.kind}}))
    payload: Dict[str, Any] = {'viewpoint': copy.deepcopy(dict(observation.viewpoint)), 'outcome': observation.outcome,
                               'state_seq': observation.state_info.get('last_seq', 0), 'output_sha256': _sha(to_json(observation))}
    if isinstance(observation.focus, Focus): payload['observed_cell'] = observation.focus.cell_key
    if isinstance(observation.focus, Tie): payload['tie_cells'] = list(observation.focus.candidates)
    ids.append(ledger.append({'kind': 'observation', 'payload': payload}))
    return ids


def record_decision(ledger: Any, cell_key: str) -> str:
    """A decision of the frame (a person or a project settled on this cell): the only way a `decided_cell` enters a ledger."""
    return ledger.append({'kind': 'decision', 'payload': {'decided_cell': cell_key}})


def replay(ledger_events: Iterable[Mapping[str, Any]], observation_event: Mapping[str, Any], structure: Structure,
           lookup: Any = None, neighbors: Any = None, anchor_reading: Optional[Mapping[str, Any]] = None) -> bool:
    """Observe again with the ledger as it was BEFORE that turn (the events up to `state_seq`) and compare the sha256 of the output with the
    one the observation event recorded. True when they are the same."""
    payload = observation_event['payload']
    vp = viewpoint_from_dict(payload['viewpoint'], anchor_reading)
    if payload['viewpoint']['state']['kind'] == 'FLAT':
        prior: Any = FLAT
    else:
        prior = SAL.MemoryLedger([e for e in ledger_events if e['seq'] <= payload['state_seq']])
    obs = observe(vp, structure, lookup, neighbors, ledger=prior)
    return _sha(to_json(obs)) == payload['output_sha256']


# ---------------------------------------------------------------------------------------------------------------------------------
# the entry (used by `python -m verantyx.cli observe`; the command line only parses and prints)
# ---------------------------------------------------------------------------------------------------------------------------------
@dataclass(frozen=True)
class EntryResult:
    exit_code: int
    stdout: Optional[str]
    error: Optional[Dict[str, Any]]


def _payload_problem(event: Mapping[str, Any]) -> Optional[str]:
    """The first field of a ledger event that the observer or the field (salience) reads and that has the wrong type, as `<field>`; None when
    the event is usable. Which fields are read is decided by P9 (what the observer writes) and by `salience.build_context` / the stages
    (what they read: `text` of an utterance, `decided_cell` of any event used as a dict key, `observed_cell` by equality). W5-b, A3."""
    kind, p = event['kind'], event['payload']
    def is_str(v: Any) -> bool: return isinstance(v, str)
    if 'decided_cell' in p and not is_str(p['decided_cell']): return 'decided_cell'
    if kind == 'utterance':
        if not is_str(p.get('text')): return 'text'
        if 'anchor' in p and p['anchor'] not in ANCHOR_KINDS: return 'anchor'
    elif kind == 'observation':
        if not isinstance(p.get('viewpoint'), Mapping): return 'viewpoint'
        if p.get('outcome') not in OUTCOMES: return 'outcome'
        if not isinstance(p.get('state_seq'), int) or isinstance(p.get('state_seq'), bool): return 'state_seq'
        if not is_str(p.get('output_sha256')): return 'output_sha256'
        if 'observed_cell' in p and not is_str(p['observed_cell']): return 'observed_cell'
        if 'tie_cells' in p and not (isinstance(p['tie_cells'], list) and all(is_str(c) for c in p['tie_cells'])): return 'tie_cells'
    elif kind == 'decision':
        if not is_str(p.get('decided_cell')): return 'decided_cell'
    return None


def validate_ledger_payloads(ledger: Any) -> None:
    """Check EVERY event of a loaded ledger before anything is observed or appended. Raises ValueError('LEDGER_INVALID:PAYLOAD_INVALID:seq=<n>:<field>')
    for the first event whose payload has a field of the wrong type (docs/OBSERVATION.md, E-W5b-4)."""
    for ev in ledger.events():
        field = _payload_problem(ev)
        if field is not None: raise ValueError('%s:PAYLOAD_INVALID:seq=%s:%s' % (SAL.LEDGER_INVALID, ev['seq'], field))


def build_structure(*, structure_path: Optional[str] = None, index_root: Optional[str] = None,
                    index_families: Sequence[str] = DEFAULT_FAMILIES, no_index: bool = False,
                    placement_path: Optional[str] = None) -> Structure:
    """The structure of the command line: sentences (file or none), the placement file (or the stubs) and the index spec. Raises
    ValueError('BAD_ARGUMENTS:...') for an argument that cannot be used."""
    if no_index and index_root is not None: raise _bad('NO_INDEX_AND_INDEX_TOGETHER')
    placement = FilePlacement.from_path(placement_path) if placement_path is not None else None
    lookup = placement if placement is not None else EC.StubLookup()
    neighbors = placement if placement is not None else StubNeighbors()
    index: Optional[IndexSpec] = None
    if not no_index:
        from .ability_corpus import FAMILIES
        fams = tuple(index_families) if index_families else DEFAULT_FAMILIES
        for f in fams:
            if f not in FAMILIES: raise _bad('INDEX_FAMILY_UNKNOWN:%s' % f)
        index = IndexSpec(Path(index_root) if index_root is not None else None, fams)
    if structure_path is not None:
        return Structure.from_jsonl(structure_path, lookup, neighbors, index)
    return Structure.empty(lookup, neighbors, index)


def build_viewpoint(*, anchor_text: Optional[str] = None, anchor_record: Optional[str] = None, anchor_kind: str = 'seed',
                    anchor_cross: Optional[int] = None, lang: Optional[str] = None, direction: str = '',
                    range_: Optional[int] = None) -> Viewpoint:
    if (anchor_text is None) == (anchor_record is None): raise _bad('EXACTLY_ONE_OF_ANCHOR_TEXT_AND_ANCHOR_RECORD')
    if anchor_kind not in ANCHOR_KINDS: raise _bad('ANCHOR_KIND_NOT_IN_CLOSED_LIST:%s' % anchor_kind)
    if lang not in (None, 'ja', 'en'): raise _bad('LANG_NOT_IN_CLOSED_LIST:%s' % (lang,))    # a wrong value is an argument error, not NO_ANCHOR (review r1, optional 2)
    anchor: Any = (AnchorText(anchor_kind, anchor_text, lang, anchor_cross) if anchor_text is not None
                   else AnchorRecord(anchor_record, anchor_cross))
    return Viewpoint(anchor, parse_direction(direction), range_)


def run_entry(*, anchor_text: Optional[str] = None, anchor_record: Optional[str] = None, anchor_kind: str = 'seed',
              anchor_cross: Optional[int] = None, lang: Optional[str] = None, direction: str = '', range_: Optional[int] = None,
              structure_path: Optional[str] = None, index_root: Optional[str] = None, index_families: Sequence[str] = DEFAULT_FAMILIES,
              no_index: bool = False, placement_path: Optional[str] = None, ledger_path: Optional[str] = None) -> EntryResult:
    """Build everything from the arguments, observe, and (with a ledger file) record the turn. Exit code 0: a typed result (an abstention or
    a TIE is a result); 2: the arguments are wrong (`BAD_ARGUMENTS`); 3: the ledger file is broken (`LEDGER_INVALID`, nothing is appended)."""
    try:
        vp = build_viewpoint(anchor_text=anchor_text, anchor_record=anchor_record, anchor_kind=anchor_kind, anchor_cross=anchor_cross,
                             lang=lang, direction=direction, range_=range_)
        structure = build_structure(structure_path=structure_path, index_root=index_root, index_families=index_families,
                                    no_index=no_index, placement_path=placement_path)
    except ValueError as exc:
        text = str(exc)
        if not text.startswith('BAD_ARGUMENTS:'): raise
        return EntryResult(2, None, {'error': {'type': 'BAD_ARGUMENTS', 'detail': text.split(':', 1)[1]}})
    ledger: Any = FLAT
    if ledger_path is not None:
        if os.path.exists(ledger_path):
            try:
                ledger = SAL.load_jsonl(ledger_path)
                validate_ledger_payloads(ledger)
            except ValueError as exc:
                text = str(exc)
                if not text.startswith(SAL.LEDGER_INVALID + ':'): raise
                return EntryResult(3, None, {'error': {'type': SAL.LEDGER_INVALID, 'detail': text.split(':', 1)[1]}})
        else:
            ledger = SAL.MemoryLedger()
    obs = observe(vp, structure, ledger=ledger)
    out = to_json(obs)
    if ledger_path is not None:
        before = len(ledger)
        record_turn(ledger, vp, obs)
        SAL.append_jsonl(ledger_path, list(ledger.events(since='ev:%d' % before)) if before else list(ledger.events()))
    return EntryResult(0, out, None)


# ---------------------------------------------------------------------------------------------------------------------------------
# questions (W3-c2): a question is a cross with one typed HOLE; the cells of the structure that agree with it everywhere but the hole fill it
# (docs/OBSERVATION.md, 質問の観測). Evidence = the crosses of the structure's own sentences only: not the anchor's reading, not the index.
# ---------------------------------------------------------------------------------------------------------------------------------
ANSWER_SCHEMA = 'verantyx.question_answer/1'
ANSWER_STATUSES: Tuple[str, ...] = ('FILLED', 'TIE', 'NO_ATTESTED_CELL', 'TYPE_EXCLUDED_ALL', 'HOLE_TYPE_UNDETERMINED', 'POLAR_QUESTION',
                                    'DIRECTION_NOT_APPLIED', 'QUESTION_NOT_READ', 'ANCHOR_CROSS_INDEX_OUT_OF_RANGE', 'INCOMPLETE_BY_EXTENSION')
HOLE_EXCLUSION_REASONS: Tuple[str, ...] = ('HOLE_TYPE_DISAGREE', 'HOLE_TYPE_NOT_CHECKED', 'SAME_AS_RESTRICTOR')


def _nfkc(surface: str) -> str:
    import unicodedata    # the only normalisation the match uses: on the SURFACE of a filler. A predicate, a polarity, a tense, a voice are compared as they are
    return unicodedata.normalize('NFKC', surface)


@dataclass(frozen=True)
class QuestionObservation(Observation):
    """An observation whose anchor is a question: the `Observation` shape (so the ledger, the replay and the entry work as they do) plus `answer`."""
    answer: Mapping[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        out = super().to_dict()
        out['answer'] = copy.deepcopy(dict(self.answer))
        return out


def _cross_matches_question(q: EC.EventCross, hole: str, d: EC.EventCross) -> bool:
    """docs/OBSERVATION.md, 一致の定義 (D9): the centre as it is (every key), the same arms but the hole's, each with the same kind and the surfaces
    equal elementwise under NFKC, and d has the hole's arm. Nothing else: no neighbour, no paraphrase, no swap of a face."""
    if dict(q.center) != dict(d.center): return False
    if hole not in d.arms: return False
    if set(q.arms) - {hole} != set(d.arms) - {hole}: return False
    for role, arm in q.arms.items():
        if role == hole: continue
        other = d.arms[role]
        if arm.kind != other.kind or len(arm.fillers) != len(other.fillers): return False
        if any(_nfkc(a.surface) != _nfkc(b.surface) for a, b in zip(arm.fillers, other.fillers)): return False
    return True


def _cross_extends_question(q: EC.EventCross, hole: str, d: EC.EventCross) -> List[str]:
    """The roles d has beyond the question, when d is the question's cross plus MORE arms (the same centre, every other arm of the question the same,
    the hole's arm present); else []. Such a cross is NOT a match (a negated question must not be answered by a sentence that is negated in one place only);
    it is listed so that an absence is not read as "the document says nothing"."""
    if dict(q.center) != dict(d.center) or hole not in d.arms: return []
    mine = set(q.arms) - {hole}
    extra = sorted(set(d.arms) - {hole} - mine)
    if not extra or not mine <= set(d.arms): return []
    for role in mine:
        a, b = q.arms[role], d.arms[role]
        if a.kind != b.kind or len(a.fillers) != len(b.fillers) or any(_nfkc(x.surface) != _nfkc(y.surface) for x, y in zip(a.fillers, b.fillers)): return []
    return extra


def _valid_place(lookup: Any, word: str) -> Optional[EC.PlaceResult]:
    got = lookup.lookup(word)
    return got if isinstance(got, EC.PlaceResult) and not got.invariant_problems() else None


def _hole_type_check(place: Any, expected: Sequence[str]) -> Dict[str, Any]:
    """The rules 3-7 of docs/EVENT_CROSS.md (型一致の決め方), in that order, against the types the HOLE expects (rules 1 and 2 do not apply: a filler of an
    ARM_TIE arm is a candidate of its own, and the hole's expected types are not the role table's)."""
    want = tuple(sorted(expected))
    if not isinstance(place, EC.PlaceResult) or place.invariant_problems():
        return {'verdict': 'NOT_CHECKED', 'reason': 'LOOKUP_RESULT_INVALID', 'expected': list(want), 'observed': None}
    if place.state in ('NO_PLACEMENT', 'UNKNOWN', 'UNPLACED'):
        return {'verdict': 'NOT_CHECKED', 'reason': place.state, 'expected': list(want), 'observed': None}
    if place.origin == 'estimated':
        return {'verdict': 'NOT_CHECKED', 'reason': 'ESTIMATED_NEAR' if place.estimate_basis == 'proximity' else 'ESTIMATED_GENERATED',
                'expected': list(want), 'observed': list(place.types)}
    if place.state == 'MULTIPLE':
        return {'verdict': 'NOT_CHECKED', 'reason': 'MULTIPLE', 'expected': list(want), 'observed': list(place.types)}
    return {'verdict': 'AGREE' if place.types[0] in want else 'DISAGREE', 'reason': None, 'expected': list(want), 'observed': list(place.types)}


def _public_question(question: Mapping[str, Any]) -> Dict[str, Any]:
    """The reader's `question` field without `declarative`: the declarative form holds the mark in a sentence, and no sentence with the mark is put in an output."""
    return {k: v for k, v in question.items() if k != 'declarative'}


def _question_answer(status: str, question: Mapping[str, Any], cross: Optional[EC.EventCross], fillers: List[Dict[str, Any]], excluded: List[Dict[str, Any]],
                     structure_info: Mapping[str, Any], reasons: List[str]) -> Dict[str, Any]:
    return {'schema': ANSWER_SCHEMA, 'status': status, 'question': _public_question(question),
            'question_cross': cross.to_dict() if cross is not None else None, 'fillers': fillers, 'excluded': excluded,
            'structure': dict(structure_info), 'reasons': reasons}


def _observe_question(viewpoint: Viewpoint, structure: Structure, lookup: Any, neighbors: Any, ledger: Any) -> Optional[QuestionObservation]:
    """The observation of an anchor that is a QUESTION (kind `question`, read by `semantic_read.read_question` to a cross with a hole). None when the anchor
    is not one: a seed, a record, or a text that is not a question (the reader says so by returning no `question` key) go the way they always went."""
    a = viewpoint.anchor
    if not (isinstance(a, AnchorText) and a.kind == 'question'): return None
    if a.reading is not None:
        read_out: Any = a.reading
        if not isinstance(read_out, Mapping) or 'question' not in read_out: return None
    else:
        from . import semantic_read
        try:
            read_out = semantic_read.read_question(a.text, a.lang)
        except semantic_read.ReadError:
            return None
        if 'question' not in read_out: return None
    lookup = lookup if lookup is not None else structure.lookup
    state = ledger if ledger is not None else viewpoint.state
    state_info = _state_info(state)
    vp_json = viewpoint_to_dict(viewpoint, state_info)
    counts = _new_counts()
    info = structure.info()
    trace = SAL.rank([], state).trace
    question = read_out['question']
    crossed_read = [r for r in structure.readings if r.status == 'CROSSED']
    unread = sorted(r.id for r in structure.readings if r.status != 'CROSSED')
    sinfo: Dict[str, Any] = {'sentences': len(structure.readings), 'crossed': len(crossed_read), 'unread': len(unread), 'unread_ids': unread,
                             'crosses_compared': 0, 'crosses_matched': 0, 'extending': []}
    counts['question'] = {'status': None, 'candidates': 0, 'excluded': 0}

    def finish(status: str, focus: Any, cross: Optional[EC.EventCross] = None, fillers: Optional[List[Dict[str, Any]]] = None,
               excluded: Optional[List[Dict[str, Any]]] = None, reasons: Optional[List[str]] = None,
               ranks: Tuple[Tuple[ObservedElement, ...], ...] = ()) -> QuestionObservation:
        counts['question']['status'] = status
        counts['question']['candidates'] = len(fillers or ())
        counts['question']['excluded'] = len(excluded or ())
        answer = _question_answer(status, question, cross, fillers or [], excluded or [], sinfo, reasons or [])
        return QuestionObservation(vp_json, info, None, ranks, focus, counts, trace, state_info, answer)

    def not_read(reason: str, detail: Mapping[str, Any]) -> QuestionObservation:
        return finish('QUESTION_NOT_READ', NoAnchor(reason, dict(detail, question=_public_question(question))), reasons=[reason])

    if not read_out.get('readable'):
        return not_read('READER_ABSTAINED', copy.deepcopy(dict(read_out.get('abstain') or {})))
    crossed = EC.build_crosses(read_out, lookup)
    if crossed.status != 'CROSSED' or len(crossed.crosses) != 1:
        return not_read('READER_INPUT_REJECTED', copy.deepcopy(dict(crossed.abstain or {})))
    if a.cross_index is not None and a.cross_index != 0:
        return finish('ANCHOR_CROSS_INDEX_OUT_OF_RANGE', NoAnchor('ANCHOR_CROSS_INDEX_OUT_OF_RANGE', {'cross_index': a.cross_index, 'crosses': 1}),
                      reasons=['ANCHOR_CROSS_INDEX_OUT_OF_RANGE'])
    qcross = crossed.crosses[0]
    if viewpoint.direction:
        return finish('DIRECTION_NOT_APPLIED', NoMoveLicensed({'FILL_HOLE:DIRECTION_NOT_APPLIED': 1}), qcross, reasons=['DIRECTION_NOT_APPLIED'])
    hole = question.get('hole_role')
    if hole == 'polarity':
        return finish('POLAR_QUESTION', NoMoveLicensed({'FILL_HOLE:POLAR_QUESTION': 1}), qcross, reasons=['POLAR_QUESTION_NOT_OBSERVED'])
    mark = question.get('hole_mark')
    harm = qcross.arms.get(hole) if isinstance(hole, str) else None
    if harm is None or harm.kind != 'FILLER' or harm.fillers[0].surface != mark:
        return not_read('QUESTION_HOLE_NOT_IN_CROSS', {'hole_role': hole})
    # --- the type the hole expects
    expected: Optional[Tuple[str, ...]] = tuple(question['hole_type']) if question.get('hole_type') else None
    restrictor = question.get('restrictor')
    if expected is None:
        got = _valid_place(lookup, restrictor) if isinstance(restrictor, str) and restrictor else None
        if got is None or got.state != 'DECIDED' or got.origin != 'direct':
            return finish('HOLE_TYPE_UNDETERMINED', NoMoveLicensed({'FILL_HOLE:HOLE_TYPE_UNDETERMINED': 1}), qcross, reasons=['RESTRICTOR_TYPE_NOT_DECIDED'])
        expected = tuple(got.types)
    strict = bool(restrictor)    # which+N presupposes "one of the N": only a candidate whose type is checked and agrees may answer
    # --- compare the question's cross with EVERY cross of EVERY read sentence of the structure (no sampling, no index, no anchor)
    matched: List[Tuple[Reading, int, EC.EventCross]] = []
    extending_fillers: List[EC.Filler] = []
    for r in crossed_read:
        for i, d in enumerate(r.crosses):
            sinfo['crosses_compared'] += 1
            if _cross_matches_question(qcross, hole, d):
                matched.append((r, i, d))
            else:
                extra = _cross_extends_question(qcross, hole, d)
                if extra:
                    sinfo['extending'].append({'reading': r.id, 'cross_index': i, 'extra_roles': extra,
                                               'fillers': [f.surface for f in d.arms[hole].fillers]})
                    extending_fillers.extend(d.arms[hole].fillers)
    sinfo['crosses_matched'] = len(matched)
    sinfo['extending'].sort(key=_cj)
    extending_reasons = ['EXTENDING_CROSSES_NOT_MATCHED:%d' % len(sinfo['extending'])] if sinfo['extending'] else []
    unread_reasons = ['UNREAD_SENTENCES:%d' % len(unread)] if unread else []
    if not matched:
        return finish('NO_ATTESTED_CELL', NoMoveLicensed({'FILL_HOLE:NO_ATTESTED_CELL': 1}), qcross,
                      reasons=['NO_MATCHING_CROSS_IN_READ_SENTENCES'] + extending_reasons + unread_reasons)
    # --- candidates: the fillers of the hole's arm of the matched crosses, judged against the hole's type
    kept: List[Dict[str, Any]] = []
    dropped: List[Dict[str, Any]] = []
    def judge(f: EC.Filler) -> Tuple[Dict[str, Any], Optional[str]]:
        check = _hole_type_check(f.place, expected)
        reason: Optional[str] = None
        if restrictor and _nfkc(f.surface) == _nfkc(restrictor): reason = 'SAME_AS_RESTRICTOR'
        elif check['verdict'] == 'DISAGREE': reason = 'HOLE_TYPE_DISAGREE'
        elif strict and check['verdict'] != 'AGREE': reason = 'HOLE_TYPE_NOT_CHECKED'
        return check, reason

    for r, i, d in sorted(matched, key=lambda t: (t[0].id, t[1])):
        cell_key = cell_key_of(d)
        arm = d.arms[hole]
        for f in arm.fillers:
            check, reason = judge(f)
            item = {'surface': f.surface, 'nfkc': _nfkc(f.surface), 'reading': r.id, 'cross_index': i, 'cell_key': cell_key, 'text': r.text,
                    'reading_source': r.source, 'check': check, 'agreement': arm.agreement.to_dict(), 'from_arm_tie': arm.kind == 'ARM_TIE',
                    'cross': d, 'lang': r.lang}
            (dropped if reason else kept).append(dict(item, reason=reason))

    def evidence_of(item: Mapping[str, Any]) -> Dict[str, Any]:
        return {'reading': item['reading'], 'cross_index': item['cross_index'], 'cell_key': item['cell_key'], 'text': item['text'],
                'reading_source': item['reading_source'], 'role_agreement': item['agreement']}

    def group(items: List[Dict[str, Any]], with_reason: bool) -> List[Dict[str, Any]]:
        by_surface: Dict[Tuple[str, str, Optional[str]], List[Dict[str, Any]]] = {}
        for it in items: by_surface.setdefault((it['nfkc'], it['surface'], it['reason']), []).append(it)
        out: List[Dict[str, Any]] = []
        for key in sorted(by_surface):    # a display order (the key is text), never a choice
            its = sorted(by_surface[key], key=lambda x: (x['reading'], x['cross_index']))
            row: Dict[str, Any] = {'surface': key[1], 'nfkc': key[0], 'evidence': [evidence_of(x) for x in its], 'hole_type_check': its[0]['check']}
            if with_reason: row['reason'] = key[2]
            else: row['role_agreement'] = its[0]['agreement']; row['from_arm_tie'] = any(x['from_arm_tie'] for x in its)
            out.append(row)
        return out

    fillers, excluded = group(kept, False), group(dropped, True)
    if not kept:
        reasons_count: Dict[str, int] = {}
        for it in dropped: reasons_count['FILL_HOLE:candidate:%s' % it['reason']] = reasons_count.get('FILL_HOLE:candidate:%s' % it['reason'], 0) + 1
        return finish('TYPE_EXCLUDED_ALL', NoMoveLicensed(dict(sorted(reasons_count.items()))), qcross, fillers, excluded,
                      reasons=['EVERY_CANDIDATE_EXCLUDED_BY_THE_TYPE_OF_THE_HOLE'] + extending_reasons + unread_reasons)
    # --- the cells that carry the kept candidates, as elements (the realizer says each one's sentence from the STRUCTURE's cross, never from the question's)
    cells: Dict[str, Cell] = {}
    for it in sorted(kept, key=lambda x: (x['cell_key'], x['reading'], x['cross_index'])):
        coord = {'origin': {'kind': 'structure', 'id': it['reading'], 'cross_index': it['cross_index']}, 'moves': []}
        if it['cell_key'] in cells:
            old = cells[it['cell_key']]
            if _cj(coord) not in {_cj(c) for c in old.coords}:
                cells[it['cell_key']] = replace(old, coords=tuple(sorted(old.coords + (coord,), key=_cj)))
        else:
            cells[it['cell_key']] = Cell(it['cell_key'], it['cross'], (coord,), 'read:' + it['reading_source'], it['lang'])
    realized: Dict[Tuple[str, Optional[str]], Dict[str, Any]] = {}
    elements: List[ObservedElement] = []
    for key in sorted(cells):
        cell = cells[key]
        occupancy = _occupancy(cell, structure, None)    # the structure's own sentences only: no anchor reading
        claim, provenance = _claim_of(occupancy)
        if (cell.key, cell.lang) not in realized: realized[(cell.key, cell.lang)] = _realization(cell, claim, provenance)
        realization = realized[(cell.key, cell.lang)]
        counts['occupancy'][occupancy.occupied] += 1
        counts['claims'][claim] += 1
        if realization['status'] == 'REALIZED': counts['realization']['realized'] += 1
        else: counts['realization']['refused'][realization['reason']] = counts['realization']['refused'].get(realization['reason'], 0) + 1
        elements.append(ObservedElement(cell, occupancy, claim, provenance, realization))
    counts['candidates'] = len(elements)
    kinds = {row['nfkc'] for row in fillers}
    # A cross that is the question's cross plus MORE arms is not a match, but if it names a candidate (one the hole's type does not exclude) that the matches do
    # not, the set of fillers above may be short of it: the answer is then not given as complete (the other fillers are in structure.extending).
    unseen = sorted({_nfkc(f.surface) for f in extending_fillers if judge(f)[1] is None} - kinds)
    if unseen:
        return finish('INCOMPLETE_BY_EXTENSION', NoMoveLicensed({'FILL_HOLE:INCOMPLETE_BY_EXTENSION': len(unseen)}), qcross, fillers, excluded,
                      reasons=['EXTENDING_CROSS_NAMES_ANOTHER_FILLER:%d' % len(unseen)] + extending_reasons + unread_reasons)
    status = 'FILLED' if len(kinds) == 1 else 'TIE'
    focus: Any = Focus(elements[0].cell.key) if len(elements) == 1 else Tie(tuple(e.cell.key for e in elements))    # a Tie is never broken
    return finish(status, focus, qcross, fillers, excluded, reasons=extending_reasons + unread_reasons, ranks=(tuple(elements),))
