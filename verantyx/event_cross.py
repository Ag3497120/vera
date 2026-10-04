"""Event cross (事象の十字): the middle layer between a word's coarse placement and the relations between events.

The centre of a cross is an event (the predicate of one clause), the arms are the roles of docs/READING_CONVENTIONS.md section 2, and a word
is a FILLER of an arm. The cross is built ONLY from the output of the reading entry (`verantyx.semantic_read`, schema
`verantyx.semantic_read/1`): the input sentence is never parsed again here, the reader's rules are not changed, and nothing is guessed.

    reader output  --build_crosses-->  CrossReading { crosses[EventCross{center, arms{role: Arm{fillers, agreement}}}], relations, abstain }

What this layer does:
  * one clause -> one cross (same order, same index); the clause keys other than `roles` become the centre as they are;
  * every role of the clause becomes an arm (in the fixed order ROLE_NAMES, so a cross serialises to the same bytes every time);
  * every filler gets a coarse placement from a `PlacementLookup` (the type candidates and where they come from);
  * every arm gets a TypeAgreement (AGREE / DISAGREE / NOT_CHECKED with a typed reason) comparing the placed type with the type the
    convention expects of the role (EXPECTED_TYPES, registered in docs/EVENT_CROSS.md before any test data was written).
What it does NOT do: it never changes a role, a value or an arm because of a type (a DISAGREE is a statement, not a repair), it never adds
a relation, it never picks one of several candidates (an arm with several candidates is an ARM_TIE and stays split; a placement with several
types is MULTIPLE and is not checked), it never turns a missing placement into a negative answer (NO_PLACEMENT, UNKNOWN, UNPLACED and the
estimated kinds are all different typed reasons), and it holds no word list of any topic.

Only the standard library is imported at module level. `read_events` imports the reading entry inside the function.
"""
from __future__ import annotations

import copy
import dataclasses    # W3-b3: dataclasses.replace for the embedded cross (the import line below is not changed)
from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping, Optional, Protocol, Tuple, runtime_checkable

SCHEMA = 'verantyx.event_cross/1'
SOURCE_SCHEMA = 'verantyx.semantic_read/1'

# docs/READING_CONVENTIONS.md section 2: the closed list of role names, in the order of its table. NOT extended here.
ROLE_NAMES: Tuple[str, ...] = (
    'agent', 'patient', 'recipient', 'goal', 'result', 'source', 'place', 'time', 'instrument',
    'companion', 'cause', 'quotation', 'entity', 'value', 'attribute', 'standard', 'causer', 'causee',
    'beneficiary', 'experiencer')

# docs/READING_CONVENTIONS.md section 1.2: the closed list of relation types.
RELATION_TYPES: Tuple[str, ...] = (
    'cause', 'contrast', 'concession', 'condition', 'purpose', 'sequence', 'simultaneous', 'manner', 'quote', 'relative', 'content')

# docs/READING_CONVENTIONS.md section 1.1: the keys of a clause.
CLAUSE_REQUIRED_KEYS: Tuple[str, ...] = ('predicate', 'roles', 'polarity', 'tense', 'modality', 'voice')
CLAUSE_OPTIONAL_KEYS: Tuple[str, ...] = ('quantifiers', 'scope', 'comparison')
CLAUSE_KEYS: Tuple[str, ...] = CLAUSE_REQUIRED_KEYS + CLAUSE_OPTIONAL_KEYS
CENTER_KEYS: Tuple[str, ...] = tuple(k for k in CLAUSE_KEYS if k != 'roles')    # the order of the centre in a serialised cross
# W3-b1: the source fields the reading entry writes on a clause that it decided by a type (`predicate_basis`: a string, `role_basis`: {role: string}).
# They are NOT keys of the convention (CLAUSE_KEYS stays the table of docs/READING_CONVENTIONS.md 1.1): the cross accepts them and copies them to the
# provenance of the cross, never to its centre.
ENTRY_BASIS_KEYS: Tuple[str, ...] = ('predicate_basis', 'role_basis')
# W3-b2: the other source field the entry writes on a clause of a type path: `role_flags` = {role: {"determiner": the demonstrative that stood before the filler}}. Not a key of the
# convention either: the cross accepts it, checks its shape, and writes `flags['determiner']` of the filler of that role (it is not copied to the centre or to the provenance).
ENTRY_FLAG_KEYS: Tuple[str, ...] = ('role_flags',)
# W5-e: a `role_flags` entry may also carry `coordination` (one of these three particles). The cross does not build a filler for a role that carries it (`COORDINATION_UNMARKED:<role>`):
# the reading entry abstains on a coordination or a disjunction, so this is only the form that receives the mark (docs/EVENT_CROSS.md, W5-e).
COORDINATION_MARKS: Tuple[str, ...] = ('と', 'や', 'か')
# W3-b3: the `head` of a relation of type `relative` (docs/EVENT_CROSS.md, W3-b3 の追記): {from_role: the arm of the relative clause the head fills, to_role: the role of the head in the main
# clause}. Not a key of the convention (the scorer reads type, from, to only); the closed list of what `_check` can say is wrong about it.
RELATION_HEAD_REASONS: Tuple[str, ...] = ('not_a_mapping', 'keys', 'type_not_relative', 'role_not_in_convention', 'values_differ', 'duplicate_target', 'nested')

# The noun type ids of the coarse placement, as named in the W3-a2 working tree on 2026-10-03 (its list is append-only). Kept here as strings
# because this module does not import the placement code (it asks a PlacementLookup). Not used to reject a type id the lookup returns.
NOUN_TYPE_IDS: Tuple[str, ...] = (
    'PERSON', 'GROUP_ORG', 'ANIMAL', 'PLANT', 'ARTIFACT', 'SUBSTANCE_FOOD', 'PLACE', 'TIME', 'QUANTITY', 'EVENT_ACT', 'STATE_PROPERTY',
    'ABSTRACT', 'INFO_LANGUAGE', 'BODY_PART', 'NATURAL_PHENOMENON', 'WORK', 'IDENTIFIER',
    'RELATIVE_POSITION')      # appended 2026-10-05 at the integration of W3-a6 (the 18th noun type; the list is append-only, see above)

# The registered table (docs/EVENT_CROSS.md, section "事前登録"): the type the convention says a role holds. Roles that the convention does
# not tie to a type are NOT in the table.
EXPECTED_TYPES: Dict[str, frozenset] = {
    'agent': frozenset({'PERSON', 'GROUP_ORG', 'ANIMAL'}),
    'recipient': frozenset({'PERSON', 'GROUP_ORG'}),
    'place': frozenset({'PLACE'}),
    'time': frozenset({'TIME'}),
    'companion': frozenset({'PERSON'}),
    'causee': frozenset({'PERSON'}),
    'beneficiary': frozenset({'PERSON'}),
    'experiencer': frozenset({'PERSON'}),
}
EXPECTED_TYPES_VERSION = '1'

VERDICTS: Tuple[str, ...] = ('AGREE', 'DISAGREE', 'NOT_CHECKED')
# W3-b2: a verdict that exists beside the three, counted under its own key only when it occurs (a count without it has the form it always had).
EXTRA_VERDICTS: Tuple[str, ...] = ('AGREE_ALL_CANDIDATES',)
NOT_CHECKED_REASONS: Tuple[str, ...] = (
    'ARM_TIE', 'ROLE_NOT_IN_TABLE', 'LOOKUP_RESULT_INVALID', 'NO_PLACEMENT', 'UNKNOWN', 'UNPLACED',
    'ESTIMATED_NEAR', 'ESTIMATED_GENERATED', 'MULTIPLE')

PLACE_STATES: Tuple[str, ...] = ('DECIDED', 'MULTIPLE', 'UNPLACED', 'UNKNOWN', 'NO_PLACEMENT')
INVALID_STATE = 'INVALID'    # the state written on a filler whose lookup returned something that breaks the contract (not a state of the placement)
ORIGINS: Tuple[str, ...] = ('direct', 'estimated')
ESTIMATE_BASES: Tuple[str, ...] = ('proximity', 'generated')


# ---------------------------------------------------------------------------------------------------------------------------------
# placement
# ---------------------------------------------------------------------------------------------------------------------------------
@dataclass(frozen=True)
class PlaceResult:
    """What a placement says about one word. `types` is an UNORDERED set written in alphabetical order: it is not a ranking."""
    state: str
    origin: Optional[str] = None
    estimate_basis: Optional[str] = None
    types: Tuple[str, ...] = ()
    provenance: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        # `types` is a set, not a ranking: a well-formed tuple of non-empty strings is written in alphabetical order, whatever order the lookup
        # returned it in. Any other shape (a list, an empty string, a non-string) is left as it is and refused by invariant_problems().
        if isinstance(self.types, tuple) and self.types and all(isinstance(t, str) and t for t in self.types):
            object.__setattr__(self, 'types', tuple(sorted(self.types)))

    @property
    def source(self) -> str:
        """direct | estimated_near | estimated_generated | UNPLACED | UNKNOWN | NO_PLACEMENT (| INVALID for a broken lookup answer)."""
        if self.types:
            if self.origin == 'direct':
                return 'direct'
            if self.origin == 'estimated' and self.estimate_basis == 'proximity':
                return 'estimated_near'
            if self.origin == 'estimated' and self.estimate_basis == 'generated':
                return 'estimated_generated'
        return self.state

    def invariant_problems(self) -> List[str]:
        """The contract of the placement query (docs of W3-a2): empty when the answer is well formed."""
        bad: List[str] = []
        if self.state not in PLACE_STATES: bad.append('STATE_UNKNOWN:%s' % (self.state,))
        if not isinstance(self.types, tuple) or not all(isinstance(t, str) and t for t in self.types):
            bad.append('TYPES_NOT_A_TUPLE_OF_STRINGS'); return bad
        n = len(self.types)
        if len(set(self.types)) != n: bad.append('TYPES_DUPLICATED')
        if list(self.types) != sorted(self.types): bad.append('TYPES_NOT_IN_ALPHABETICAL_ORDER')
        if (self.state == 'DECIDED') != (n == 1): bad.append('DECIDED_IFF_ONE_TYPE')
        if (self.state == 'MULTIPLE') != (n >= 2): bad.append('MULTIPLE_IFF_TWO_OR_MORE_TYPES')
        if self.origin not in (None,) + ORIGINS: bad.append('ORIGIN_UNKNOWN:%s' % (self.origin,))
        if self.estimate_basis not in (None,) + ESTIMATE_BASES: bad.append('ESTIMATE_BASIS_UNKNOWN:%s' % (self.estimate_basis,))
        if (self.origin == 'estimated') != (self.estimate_basis is not None): bad.append('ESTIMATED_IFF_BASIS')
        if n and self.origin is None: bad.append('TYPES_WITHOUT_ORIGIN')
        if not isinstance(self.provenance, Mapping): bad.append('PROVENANCE_NOT_A_MAPPING')
        return bad

    @classmethod
    def from_coarse_query(cls, d: Mapping[str, Any]) -> 'PlaceResult':
        """Write down the dict that the placement query returns (keys `state`, `origin`, `estimate_basis`, `top`, `namespace`, `term`,
        `constructed`, `placement`). A pure function: the placement code is not imported. Raises ValueError for a dict without the keys."""
        if not isinstance(d, Mapping): raise ValueError('BAD_COARSE_QUERY_RESULT:not a mapping')
        for key in ('state', 'top'):
            if key not in d: raise ValueError('BAD_COARSE_QUERY_RESULT:missing %s' % key)
        top = d['top']
        if not isinstance(top, (list, tuple)): raise ValueError('BAD_COARSE_QUERY_RESULT:top is not a list')
        prov: Dict[str, Any] = {}
        for key in ('term', 'namespace', 'constructed'):
            if key in d: prov[key] = d[key]
        if isinstance(d.get('placement'), Mapping): prov['placement'] = copy.deepcopy(dict(d['placement']))
        return cls(state=d['state'], origin=d.get('origin'), estimate_basis=d.get('estimate_basis'),
                   types=tuple(sorted(top)), provenance=prov)

    def to_dict(self) -> Dict[str, Any]:
        return {'state': self.state, 'origin': self.origin, 'estimate_basis': self.estimate_basis, 'types': list(self.types),
                'source': self.source, 'provenance': copy.deepcopy(dict(self.provenance)) if isinstance(self.provenance, Mapping) else None}


@runtime_checkable
class PlacementLookup(Protocol):
    """Ask the coarse placement about ONE word. The only argument is the word: no role and no predicate is passed, because a placement that
    uses the role slot to estimate a type would make the role decide the type that is then compared with the role (a circle)."""
    def lookup(self, lemma: str) -> PlaceResult: ...


class StubLookup:
    """The default lookup when no placement is named: there is no placement, so every answer is NO_PLACEMENT (reason STUB).
    (UNPLACED would say that the word is in the material and the evidence is short; that is a different statement.)"""
    id = 'stub-no-placement/1'

    def lookup(self, lemma: str) -> PlaceResult:
        return PlaceResult(state='NO_PLACEMENT', origin=None, estimate_basis=None, types=(), provenance={'reason': 'STUB'})


class CoarseLookup:
    """The coarse placement (verantyx/coarse_place.py) as a PlacementLookup: the word only (no role, no predicate), the placement's own path (never a
    None path: the placement module would then read its own variable). `id` is `coarse-placement:<content_sha256>` (`...:unavailable:<reason>` when the
    placement cannot be opened). An answer that cannot be opened is NO_PLACEMENT with its own reason, never a negative answer."""
    def __init__(self, path: str) -> None:
        self.path = path
        self._id: Optional[str] = None

    def lookup(self, lemma: str) -> PlaceResult:
        from . import coarse_place    # inside the function: the module is loaded only when a placement is named
        answer = coarse_place.query(lemma, placement=self.path)
        if self._id is None:
            info = (answer.get('placement') if isinstance(answer, Mapping) else None) or {}
            sha = info.get('content_sha256') if isinstance(info, Mapping) else None
            self._id = 'coarse-placement:%s' % sha if sha else 'coarse-placement:unavailable:%s' % (info.get('reason') if isinstance(info, Mapping) else None,)
        return PlaceResult.from_coarse_query(answer)

    @property
    def id(self) -> str:
        if self._id is None:
            self.lookup('a')          # the content hash is in every answer, whatever the word
        return self._id  # type: ignore[return-value]


def default_lookup(placement: Optional[str] = None) -> Any:
    """The lookup used when none is given: the coarse placement named by the argument, else by the variable VERA_PLACEMENT (empty or unset = none), else the
    stub. (The placement module's own variable is not read here.)"""
    if placement is None:
        import os    # inside the function: the module level holds the standard library only (a test says so)
        placement = os.environ.get('VERA_PLACEMENT')
    if placement is None or not str(placement).strip(): return StubLookup()
    return CoarseLookup(str(placement))


# ---------------------------------------------------------------------------------------------------------------------------------
# cross
# ---------------------------------------------------------------------------------------------------------------------------------
@dataclass(frozen=True)
class TypeAgreement:
    verdict: str                       # AGREE | DISAGREE | NOT_CHECKED | AGREE_ALL_CANDIDATES (a split placement of which every type the role expects)
    reason: Optional[str] = None       # one of NOT_CHECKED_REASONS when NOT_CHECKED, else None
    expected: Optional[Tuple[str, ...]] = None
    observed: Optional[Tuple[str, ...]] = None

    def to_dict(self) -> Dict[str, Any]:
        return {'verdict': self.verdict, 'reason': self.reason,
                'expected': None if self.expected is None else list(self.expected),
                'observed': None if self.observed is None else list(self.observed)}


@dataclass(frozen=True)
class Filler:
    surface: str
    head: str
    head_basis: str                    # 'surface': the reader gives no head, so the head is the surface (not guessed)
    place: PlaceResult
    flags: Mapping[str, Any] = field(default_factory=dict)
    embedded: Optional['EventCross'] = None    # W3-b3: the cross of the relative clause whose head this filler is (the last field; written only when there is one)

    def to_dict(self) -> Dict[str, Any]:
        d = {'surface': self.surface, 'head': self.head, 'head_basis': self.head_basis,
             'place': self.place.to_dict(), 'flags': _canon(dict(self.flags))}
        if self.embedded is not None: d['embedded'] = self.embedded.to_dict()
        return d


@dataclass(frozen=True)
class Arm:
    kind: str                          # FILLER (one candidate) | ARM_TIE (two or more candidates, none chosen)
    fillers: Tuple[Filler, ...]
    agreement: TypeAgreement

    def to_dict(self) -> Dict[str, Any]:
        return {'kind': self.kind, 'fillers': [f.to_dict() for f in self.fillers], 'agreement': self.agreement.to_dict()}


@dataclass(frozen=True)
class EventCross:
    index: int
    center: Mapping[str, Any]
    arms: Mapping[str, Arm]            # role name -> Arm, in the order of ROLE_NAMES
    provenance: Mapping[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {'index': self.index, 'center': {k: _canon(v) for k, v in self.center.items()},
                'arms': {role: arm.to_dict() for role, arm in self.arms.items()},
                'provenance': {k: _canon(v) for k, v in self.provenance.items()}}


_RELATION_KEY_ORDER = ('type', 'from', 'to')


def _canon(v: Any) -> Any:
    """A value copied from the input, written with its mapping keys in alphabetical order (lists keep their order)."""
    if isinstance(v, Mapping): return {k: _canon(v[k]) for k in sorted(v, key=str)}
    if isinstance(v, (list, tuple)): return [_canon(x) for x in v]
    return copy.deepcopy(v)


def _relation_dict(r: Mapping[str, Any]) -> Dict[str, Any]:
    """A relation in the fixed key order type, from, to; any other key after them, alphabetical (kept, not dropped)."""
    out = {k: _canon(r[k]) for k in _RELATION_KEY_ORDER if k in r}
    out.update({k: _canon(r[k]) for k in sorted((k for k in r if k not in _RELATION_KEY_ORDER), key=str)})
    return out


def _empty_counts() -> Dict[str, Any]:
    return {'crosses': 0, 'arms': 0, 'arm_ties': 0,
            'agreement': {v: 0 for v in VERDICTS},
            'not_checked_by_reason': {r: 0 for r in NOT_CHECKED_REASONS}}


@dataclass(frozen=True)
class CrossReading:
    status: str                        # CROSSED | ABSTAINED | INPUT_REJECTED
    crosses: Tuple[EventCross, ...]
    relations: Tuple[Mapping[str, Any], ...]
    abstain: Optional[Mapping[str, Any]]
    lookup_id: str

    @property
    def counts(self) -> Dict[str, Any]:
        c = _empty_counts()
        c['crosses'] = len(self.crosses)
        for cross in self.crosses:
            for arm in cross.arms.values():
                c['arms'] += 1
                if arm.kind == 'ARM_TIE': c['arm_ties'] += 1
                c['agreement'][arm.agreement.verdict] = c['agreement'].get(arm.agreement.verdict, 0) + 1     # an extra verdict gets its key at the end, when it first occurs
                if arm.agreement.verdict == 'NOT_CHECKED': c['not_checked_by_reason'][arm.agreement.reason] += 1
        return c

    def to_dict(self) -> Dict[str, Any]:
        return {'schema': SCHEMA, 'status': self.status,
                'crosses': [c.to_dict() for c in self.crosses],
                'relations': [_relation_dict(r) for r in self.relations],
                'abstain': _canon(self.abstain) if self.abstain is not None else None,
                'lookup': {'id': self.lookup_id},
                'counts': self.counts}


# ---------------------------------------------------------------------------------------------------------------------------------
# type agreement
# ---------------------------------------------------------------------------------------------------------------------------------
def _agreement(role: str, kind: str, place: Any) -> TypeAgreement:
    """The first rule that applies, from the top (docs/EVENT_CROSS.md). Deterministic; never changes the arm."""
    if kind == 'ARM_TIE': return TypeAgreement('NOT_CHECKED', 'ARM_TIE')
    if role not in EXPECTED_TYPES: return TypeAgreement('NOT_CHECKED', 'ROLE_NOT_IN_TABLE')
    if not isinstance(place, PlaceResult) or place.invariant_problems(): return TypeAgreement('NOT_CHECKED', 'LOOKUP_RESULT_INVALID')
    if place.state in ('NO_PLACEMENT', 'UNKNOWN', 'UNPLACED'): return TypeAgreement('NOT_CHECKED', place.state)
    if place.origin == 'estimated':
        return TypeAgreement('NOT_CHECKED', 'ESTIMATED_NEAR' if place.estimate_basis == 'proximity' else 'ESTIMATED_GENERATED')
    if place.state == 'MULTIPLE':
        # W3-b2: a split placement is not a tie to break: when every candidate is a type the role expects, whichever it is the arm agrees. One candidate outside: not checked.
        if all(t in EXPECTED_TYPES[role] for t in place.types):
            return TypeAgreement('AGREE_ALL_CANDIDATES', None, tuple(sorted(EXPECTED_TYPES[role])), tuple(place.types))
        return TypeAgreement('NOT_CHECKED', 'MULTIPLE')
    # state DECIDED and origin direct (the invariants above leave no other case)
    expected = tuple(sorted(EXPECTED_TYPES[role]))
    observed = tuple(place.types)
    return TypeAgreement('AGREE' if observed[0] in EXPECTED_TYPES[role] else 'DISAGREE', None, expected, observed)


# ---------------------------------------------------------------------------------------------------------------------------------
# build
# ---------------------------------------------------------------------------------------------------------------------------------
def _is_index(v: Any, n: int) -> bool:
    return isinstance(v, int) and not isinstance(v, bool) and 0 <= v < n


def _check_heads(relations: List[Any], clauses: List[Any]) -> List[str]:
    """W3-b3: the reasons for which the `head` of a relation is not well formed (RELATION_HEAD_NOT_WELL_FORMED:<one of RELATION_HEAD_REASONS>); empty when there is none or all are well
    formed. A relation without `head` is not looked at."""
    bad: List[str] = []
    heads: List[Tuple[int, int, str]] = []
    for rel in relations:
        if not isinstance(rel, Mapping) or 'head' not in rel: continue
        head = rel['head']
        if not isinstance(head, Mapping): bad.append('RELATION_HEAD_NOT_WELL_FORMED:not_a_mapping'); continue
        if set(head) != {'from_role', 'to_role'}: bad.append('RELATION_HEAD_NOT_WELL_FORMED:keys'); continue
        if rel.get('type') != 'relative': bad.append('RELATION_HEAD_NOT_WELL_FORMED:type_not_relative'); continue
        from_role, to_role = head['from_role'], head['to_role']
        if not (isinstance(from_role, str) and isinstance(to_role, str) and from_role in ROLE_NAMES and to_role in ROLE_NAMES):
            bad.append('RELATION_HEAD_NOT_WELL_FORMED:role_not_in_convention'); continue
        if not (_is_index(rel.get('from'), len(clauses)) and _is_index(rel.get('to'), len(clauses))): continue      # said already: RELATION_INDEX_OUT_OF_RANGE
        a, b = clauses[rel['from']], clauses[rel['to']]
        va = a.get('roles', {}).get(from_role) if isinstance(a, Mapping) and isinstance(a.get('roles'), Mapping) else None
        vb = b.get('roles', {}).get(to_role) if isinstance(b, Mapping) and isinstance(b.get('roles'), Mapping) else None
        if not (isinstance(va, str) and va.strip() and va == vb): bad.append('RELATION_HEAD_NOT_WELL_FORMED:values_differ'); continue
        heads.append((rel['from'], rel['to'], to_role))
    targets = [(to, role) for _, to, role in heads]
    if len(set(targets)) != len(targets): bad.append('RELATION_HEAD_NOT_WELL_FORMED:duplicate_target')
    receivers = {to for _, to, _ in heads}
    if any(frm in receivers for frm, _, _ in heads): bad.append('RELATION_HEAD_NOT_WELL_FORMED:nested')
    return bad


def _embed(crosses: Tuple[EventCross, ...], relations: List[Any]) -> Tuple[EventCross, ...]:
    """W3-b3: for every relation that holds a `head`, the filler of the arm `to_role` of the cross `to` holds the cross `from` (as it was built: no head of its own, one level).
    The arms keep their order, their kind and their agreement; the counts are the counts of the crosses, which are the same."""
    out = list(crosses)
    for rel in relations:
        head = rel.get('head') if isinstance(rel, Mapping) else None
        if head is None: continue
        cross = out[rel['to']]
        arm = cross.arms[head['to_role']]
        filler = dataclasses.replace(arm.fillers[0], embedded=crosses[rel['from']])
        arms = dict(cross.arms)
        arms[head['to_role']] = dataclasses.replace(arm, fillers=(filler,))
        out[rel['to']] = dataclasses.replace(cross, arms=arms)
    return tuple(out)


def _flag_well_formed(flag: Any) -> bool:
    """One role's entry of `role_flags`: a mapping whose keys are `determiner`, `coordination` or both; `determiner` a non-blank string, `coordination` one of
    COORDINATION_MARKS (W5-e). A mapping with `determiner` alone is judged exactly as before."""
    if not isinstance(flag, Mapping) or not flag or not set(flag) <= {'determiner', 'coordination'}: return False
    if 'determiner' in flag and not (isinstance(flag['determiner'], str) and flag['determiner'].strip()): return False
    return 'coordination' not in flag or (isinstance(flag['coordination'], str) and flag['coordination'] in COORDINATION_MARKS)


def _check(read_output: Any) -> List[str]:
    """The reasons for which the reader output is refused as an input (empty when it can be crossed or is a typed abstention)."""
    if not isinstance(read_output, Mapping): return ['NOT_A_MAPPING']
    if 'error' in read_output and 'schema' not in read_output:
        err = read_output['error']
        return ['READER_ERROR:%s' % (err.get('type') if isinstance(err, Mapping) else 'unknown')]
    bad: List[str] = []
    if read_output.get('schema') != SOURCE_SCHEMA: bad.append('BAD_SCHEMA')
    for key in ('readable', 'clauses', 'relations', 'abstain', 'clause_meta'):
        if key not in read_output: bad.append('MISSING_FIELD:%s' % key)
    if bad: return bad
    readable, clauses, relations, meta = read_output['readable'], read_output['clauses'], read_output['relations'], read_output['clause_meta']
    if not isinstance(readable, bool): return ['READABLE_NOT_BOOL']
    if not isinstance(clauses, list): bad.append('CLAUSES_NOT_A_LIST')
    if not isinstance(relations, list): bad.append('RELATIONS_NOT_A_LIST')
    if not isinstance(meta, list): bad.append('CLAUSE_META_NOT_A_LIST')
    if bad: return bad
    if not readable:
        if not isinstance(read_output['abstain'], Mapping): bad.append('UNREADABLE_WITHOUT_ABSTAIN')
        if clauses or relations: bad.append('UNREADABLE_WITH_CLAUSES')
        return bad
    if not clauses: bad.append('READABLE_WITHOUT_CLAUSES')
    if len(meta) != len(clauses): bad.append('CLAUSE_META_LENGTH_MISMATCH')
    for i, rel in enumerate(relations):
        if not isinstance(rel, Mapping) or not {'type', 'from', 'to'} <= set(rel):
            bad.append('RELATION_NOT_WELL_FORMED'); continue
        if rel['type'] not in RELATION_TYPES: bad.append('RELATION_TYPE_NOT_IN_CONVENTION:%s' % (rel['type'],))
        if not (_is_index(rel['from'], len(clauses)) and _is_index(rel['to'], len(clauses))): bad.append('RELATION_INDEX_OUT_OF_RANGE')
    for i, clause in enumerate(clauses):
        if not isinstance(clause, Mapping): bad.append('CLAUSE_NOT_A_MAPPING'); continue
        for key in CLAUSE_REQUIRED_KEYS:
            if key not in clause: bad.append('MISSING_FIELD:%s' % key)
        for key in clause:
            if key in ENTRY_BASIS_KEYS or key in ENTRY_FLAG_KEYS: continue
            if key not in CLAUSE_KEYS: bad.append('UNKNOWN_CLAUSE_KEY:%s' % (key,))
        basis = clause.get('predicate_basis')
        if 'predicate_basis' in clause and not (isinstance(basis, str) and basis.strip()): bad.append('ENTRY_BASIS_NOT_WELL_FORMED:predicate_basis')
        rbasis = clause.get('role_basis')
        if 'role_basis' in clause and not (isinstance(rbasis, Mapping) and rbasis and all(isinstance(k, str) and isinstance(v, str) and v.strip() for k, v in rbasis.items())):
            bad.append('ENTRY_BASIS_NOT_WELL_FORMED:role_basis')
        roles = clause.get('roles')
        if 'role_flags' in clause:
            flags = clause['role_flags']
            if not (isinstance(flags, Mapping) and flags and isinstance(roles, Mapping) and all(
                    isinstance(k, str) and k in roles and _flag_well_formed(v) for k, v in flags.items())):
                bad.append('ENTRY_FLAGS_NOT_WELL_FORMED')
            else:
                bad.extend('COORDINATION_UNMARKED:%s' % k for k, v in flags.items() if 'coordination' in v)      # W5-e: a mark the cross cannot carry
        if 'roles' in clause and not isinstance(roles, Mapping): bad.append('ROLES_NOT_A_MAPPING'); continue
        for name, value in (roles or {}).items():
            if name not in ROLE_NAMES: bad.append('ROLE_NOT_IN_CONVENTION:%s' % (name,)); continue
            if isinstance(value, str):
                if not value.strip(): bad.append('EMPTY_ROLE_VALUE:%s' % name)
            elif isinstance(value, list):
                if not value: bad.append('EMPTY_ROLE_VALUE:%s' % name)
                elif len(value) == 1: bad.append('ROLE_VALUE_SINGLETON_ARRAY:%s' % name)
                elif not all(isinstance(x, str) and x.strip() for x in value): bad.append('ROLE_VALUE_NOT_STRING:%s' % name)
            else:
                bad.append('ROLE_VALUE_NOT_STRING:%s' % name)
    bad.extend(_check_heads(relations, clauses))
    return list(dict.fromkeys(bad))


def _lookup_id(lookup: Any) -> str:
    ident = getattr(lookup, 'id', None)
    return ident if isinstance(ident, str) and ident else 'unidentified'


def _place_of(lookup: Any, head: str) -> PlaceResult:
    """Ask the lookup about `head` (and nothing else). A lookup answer that breaks the contract is kept as an INVALID placement with the
    problems named; an exception of the lookup is not caught."""
    got = lookup.lookup(head)
    if isinstance(got, PlaceResult):
        problems = got.invariant_problems()
        if not problems: return got
        return PlaceResult(state=INVALID_STATE, provenance={'reason': 'LOOKUP_RESULT_INVALID', 'problems': problems, 'returned_state': got.state})
    return PlaceResult(state=INVALID_STATE, provenance={'reason': 'LOOKUP_RESULT_INVALID', 'problems': ['NOT_A_PLACE_RESULT:%s' % type(got).__name__]})


def _filler(value: str, role: str, clause: Mapping[str, Any], lookup: Any) -> Filler:
    quant = clause.get('quantifiers')
    flags: Dict[str, Any] = {}
    if isinstance(quant, Mapping) and role in quant: flags['quantifier'] = copy.deepcopy(quant[role])
    marks = clause.get('role_flags')
    if isinstance(marks, Mapping) and isinstance(marks.get(role), Mapping) and marks[role].get('determiner'): flags['determiner'] = marks[role]['determiner']      # W3-b2
    return Filler(surface=value, head=value, head_basis='surface', place=_place_of(lookup, value), flags=flags)


def _cross(i: int, clause: Mapping[str, Any], meta: Mapping[str, Any], lookup: Any) -> EventCross:
    center = {k: copy.deepcopy(clause[k]) for k in CENTER_KEYS if k in clause}
    arms: Dict[str, Arm] = {}
    roles = clause['roles']
    for role in ROLE_NAMES:
        if role not in roles: continue
        value = roles[role]
        if isinstance(value, list):
            kind, fillers = 'ARM_TIE', tuple(_filler(v, role, clause, lookup) for v in value)
        else:
            kind, fillers = 'FILLER', (_filler(value, role, clause, lookup),)
        arms[role] = Arm(kind=kind, fillers=fillers, agreement=_agreement(role, kind, fillers[0].place if kind == 'FILLER' else None))
    provenance = {'source_schema': SOURCE_SCHEMA, 'clause_index': i,
                  'rule': copy.deepcopy(meta.get('rule')) if isinstance(meta, Mapping) else None,
                  'span': copy.deepcopy(meta.get('span')) if isinstance(meta, Mapping) else None}
    for key in ENTRY_BASIS_KEYS:     # only when the entry wrote them: a cross of a clause without them is what it always was
        if key in clause: provenance[key] = copy.deepcopy(clause[key])
    return EventCross(index=i, center=center, arms=arms, provenance=provenance)


def build_crosses(read_output: Mapping[str, Any], lookup: Optional[PlacementLookup] = None) -> CrossReading:
    """Turn the output of the reading entry into crosses. Never changes `read_output`. A lookup of None is `default_lookup()` (the placement named by
    VERA_PLACEMENT, else the stub: no placement)."""
    lookup = default_lookup() if lookup is None else lookup
    lid = _lookup_id(lookup)
    problems = _check(read_output)
    if problems:
        return CrossReading('INPUT_REJECTED', (), (), {'kind': 'input_rejected', 'reasons': problems}, lid)
    src = copy.deepcopy(dict(read_output))    # nothing below touches the caller's object
    if not src['readable']:
        return CrossReading('ABSTAINED', (), (), src['abstain'], lid)
    crosses = tuple(_cross(i, c, src['clause_meta'][i], lookup) for i, c in enumerate(src['clauses']))
    crosses = _embed(crosses, src['relations'])    # W3-b3: a relative clause's cross inside the filler of its head
    return CrossReading('CROSSED', crosses, tuple(src['relations']), None, lid)


def attach_events(read_output: Mapping[str, Any], lookup: Optional[PlacementLookup] = None) -> Dict[str, Any]:
    """A new dict: the reader output as it is, plus the key `events` last. The input is not changed."""
    out = copy.deepcopy(dict(read_output)) if isinstance(read_output, Mapping) else read_output
    if not isinstance(out, dict): out = {}
    out['events'] = build_crosses(read_output, lookup).to_dict()
    return out


def read_events(text: str, lang: Optional[str] = None, lookup: Optional[PlacementLookup] = None) -> Dict[str, Any]:
    """`semantic_read.read(text, lang)` with the `events` key added. Raises the reader's ReadError for an input it refuses."""
    from . import semantic_read    # inside the function: the reading entry imports this module only for --events
    return attach_events(semantic_read.read(text, lang), lookup)
