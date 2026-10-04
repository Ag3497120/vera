"""顕著さの場と会話の台帳 (docs/OBSERVATION.md): Salience field over a conversation ledger, a LIST OF STAGES, never a sum.

The field only reorders the cells that can already be observed (docs/OBSERVATION.md, P8). It makes no fact and no cell. Its input is an
append-only ledger of events; its stages are fixed functions of numbers read from that ledger (formulas registered in docs/OBSERVATION.md
before any test data was written; no hand-tuned constant appears here):

    (i)    distance        s1 = number of moves on the path                          smaller is higher
    (ii-a) utter_verbatim  s2 = changed fillers that occur verbatim in the latest utterance   larger is higher
                           (latest = the latest utterance that is NOT the anchor sentence of this turn; P8, change record 3)
    (ii-b) utter_neighbor  s3 = changed fillers one of whose neighbours occurs verbatim there larger is higher
    (iii)  recency         s4 = ledger.last_seq("observed_cell", key)  (None = never focused: top, then older first)
    (iv)   decided         s5 = ledger.count("decided_cell", key)                    larger is higher

The stages are compared in this order as a tuple (lexicographic); cells with the same tuple in EVERY stage form one rank. A first rank with
more than one cell is a TIE and nothing is chosen from it. There is no random number, no hash, no iteration order of a set and no clock in
any rank or output (the only clock is the default time stamp of `MemoryLedger`, stored and never read by a stage).

The `Ledger` protocol is shared with W4-m (the persistent ledger); this module has only the in-memory implementation and two thin helpers
for the jsonl file form. No deletion, no detaching and no persistence policy lives here.
"""
from __future__ import annotations

import copy
import datetime
import json
from dataclasses import dataclass
from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional, Protocol, Sequence, Tuple, runtime_checkable

EVENT_KINDS: Tuple[str, ...] = ('utterance', 'observation', 'decision')
LEDGER_INVALID = 'LEDGER_INVALID'


@runtime_checkable
class Ledger(Protocol):
    def append(self, event: Mapping[str, Any]) -> str: ...          # {"kind": "utterance"|"observation"|"decision", "payload": {...}}。seq と ts を付けて保存
    def events(self, since: Optional[str] = None) -> Iterable[Mapping[str, Any]]: ...   # seq の昇順
    def count(self, key: str, value: str) -> int: ...
    def last_seq(self, key: str, value: str) -> Optional[int]: ...


class _Flat:
    """The flat field: no ledger. A single instance, `FLAT`."""
    def __repr__(self) -> str:
        return 'FLAT'


FLAT = _Flat()


def is_flat(state: Any) -> bool:
    return state is FLAT or state is None


def _invalid(reason: str) -> ValueError:
    return ValueError('%s:%s' % (LEDGER_INVALID, reason))


def _default_clock() -> str:
    # The only clock in this module. The value is stored with the event and is never read by a stage or written to an output.
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='seconds')


def _event_id(seq: int) -> str:
    return 'ev:%d' % seq


def _seq_of_id(event_id: str) -> int:
    if isinstance(event_id, str) and event_id.startswith('ev:') and event_id[3:].isdigit():
        return int(event_id[3:])
    raise _invalid('EVENT_ID_UNKNOWN:%r' % (event_id,))


class MemoryLedger:
    """An in-memory, append-only ledger. `events` (already stored events with seq and ts, as `load_jsonl` reads them) are validated;
    `clock` gives the time stamp of a new event (default: UTC ISO string; the stamp is kept and never used by a stage)."""

    def __init__(self, events: Iterable[Mapping[str, Any]] = (), clock: Optional[Callable[[], str]] = None):
        self._clock = clock if clock is not None else _default_clock
        self._events: List[Dict[str, Any]] = []
        for ev in events:
            if not isinstance(ev, Mapping): raise _invalid('EVENT_NOT_A_MAPPING')
            for key in ('seq', 'ts', 'kind', 'payload'):
                if key not in ev: raise _invalid('MISSING_FIELD:%s' % key)
            seq = ev['seq']
            if not isinstance(seq, int) or isinstance(seq, bool) or seq != len(self._events) + 1:
                raise _invalid('SEQ_NOT_CONSECUTIVE_FROM_1:%r' % (seq,))
            if 'id' in ev and ev['id'] != _event_id(seq): raise _invalid('ID_MISMATCH:%r' % (ev['id'],))
            if not isinstance(ev['ts'], str): raise _invalid('TS_NOT_A_STRING')
            self._check_body(ev['kind'], ev['payload'])
            self._events.append({'seq': seq, 'id': _event_id(seq), 'ts': ev['ts'], 'kind': ev['kind'], 'payload': copy.deepcopy(dict(ev['payload']))})

    @staticmethod
    def _check_body(kind: Any, payload: Any) -> None:
        if kind not in EVENT_KINDS: raise _invalid('KIND_NOT_IN_CLOSED_LIST:%r' % (kind,))
        if not isinstance(payload, Mapping): raise _invalid('PAYLOAD_NOT_A_MAPPING')

    def append(self, event: Mapping[str, Any]) -> str:
        if not isinstance(event, Mapping): raise _invalid('EVENT_NOT_A_MAPPING')
        extra = [k for k in event if k not in ('kind', 'payload')]
        if extra: raise _invalid('UNKNOWN_EVENT_KEY:%s' % ','.join(sorted(map(str, extra))))
        if 'kind' not in event or 'payload' not in event: raise _invalid('MISSING_FIELD:kind_or_payload')
        self._check_body(event['kind'], event['payload'])
        seq = len(self._events) + 1
        self._events.append({'seq': seq, 'id': _event_id(seq), 'ts': self._clock(), 'kind': event['kind'], 'payload': copy.deepcopy(dict(event['payload']))})
        return _event_id(seq)

    def events(self, since: Optional[str] = None) -> Iterable[Mapping[str, Any]]:
        start = 0 if since is None else _seq_of_id(since)
        if start > len(self._events): raise _invalid('EVENT_ID_UNKNOWN:%r' % (since,))
        return [copy.deepcopy(e) for e in self._events[start:]]

    def count(self, key: str, value: str) -> int:
        return sum(1 for e in self._events if key in e['payload'] and e['payload'][key] == value)

    def last_seq(self, key: str, value: str) -> Optional[int]:
        found: Optional[int] = None
        for e in self._events:    # ascending: the last match is the newest
            if key in e['payload'] and e['payload'][key] == value: found = e['seq']
        return found

    def __len__(self) -> int:
        return len(self._events)


def load_jsonl(path: Any) -> MemoryLedger:
    """Read a ledger file (one json event per line, seq from 1 without gaps). A broken file raises ValueError('LEDGER_INVALID:<reason>')."""
    try:
        with open(path, 'rb') as fh:
            raw = fh.read()
    except FileNotFoundError:
        raise _invalid('FILE_NOT_FOUND')
    except OSError as exc:
        raise _invalid('FILE_UNREADABLE:%s' % type(exc).__name__)
    if not raw: return MemoryLedger()
    try:
        text = raw.decode('utf-8')
    except UnicodeDecodeError:
        raise _invalid('NOT_UTF8')
    if not text.endswith('\n'): raise _invalid('NO_FINAL_NEWLINE')
    events: List[Any] = []
    for n, line in enumerate(text.split('\n')[:-1], 1):
        if not line.strip(): raise _invalid('BLANK_LINE:%d' % n)
        try:
            events.append(json.loads(line))
        except ValueError:
            raise _invalid('BAD_LINE:line %d' % n)
    return MemoryLedger(events)


def dump_event(event: Mapping[str, Any]) -> str:
    """One stored event as one jsonl line (fixed key order, no trailing newline)."""
    return json.dumps({'seq': event['seq'], 'id': event['id'], 'ts': event['ts'], 'kind': event['kind'], 'payload': event['payload']},
                      ensure_ascii=False, separators=(',', ':'))


def append_jsonl(path: Any, events: Iterable[Mapping[str, Any]]) -> int:
    """Append stored events (as `MemoryLedger.events` returns them) to a ledger file: opens with "a" and adds lines. Never rewrites."""
    lines = [dump_event(e) + '\n' for e in events]
    if not lines: return 0
    with open(path, 'a', encoding='utf-8') as fh:
        fh.write(''.join(lines))
    return len(lines)


# ---------------------------------------------------------------------------------------------------------------------------------
# the field
# ---------------------------------------------------------------------------------------------------------------------------------
@dataclass(frozen=True)
class Candidate:
    """What the field needs to know about an observable cell: its key, its distance from the anchor and the fillers that differ from it."""
    key: str
    distance: int
    changed: Tuple[str, ...] = ()


@dataclass(frozen=True)
class Context:
    """Numbers read once from the ledger before the turn. `neighbors` maps a word to its neighbour words (empty when not FOUND)."""
    ledger: Any
    utterance_text: str
    utterance_seq: Optional[int]
    decisions: Mapping[str, Tuple[int, ...]]
    neighbors: Callable[[str], Sequence[str]]
    skipped_as_anchor: Tuple[int, ...] = ()    # seqs of utterances equal to the anchor sentence that were skipped (counted, never dropped silently)


def build_context(ledger: Any, neighbors: Optional[Callable[[str], Sequence[str]]] = None, anchor_text: Optional[str] = None) -> Context:
    """`anchor_text` is the anchor sentence of THIS turn. The latest utterance for stage ii is the latest one whose text is not that sentence (docs/OBSERVATION.md,
    P8 as changed in change record 3): the anchor already acts through stage i, so the same sentence is not counted again as "what the person said last"."""
    nb = neighbors if neighbors is not None else (lambda word: ())
    if is_flat(ledger):
        return Context(FLAT, '', None, {}, nb)
    text, seq = '', None
    skipped: List[int] = []
    decisions: Dict[str, List[int]] = {}
    for ev in ledger.events():    # seq ascending
        payload = ev['payload']
        if ev['kind'] == 'utterance' and isinstance(payload.get('text'), str):
            if anchor_text is not None and payload['text'] == anchor_text:
                skipped.append(ev['seq'])
            else:
                text, seq = payload['text'], ev['seq']
        if 'decided_cell' in payload:
            decisions.setdefault(payload['decided_cell'], []).append(ev['seq'])
    return Context(ledger, text, seq, {k: tuple(v) for k, v in decisions.items()}, nb, tuple(skipped))


Value = Any
StageFn = Callable[[Candidate, Any, Context], Tuple[Value, Tuple[int, ...]]]


def stage_distance(cell: Candidate, ledger: Any, ctx: Context) -> Tuple[Value, Tuple[int, ...]]:
    return cell.distance, ()


def stage_utter_verbatim(cell: Candidate, ledger: Any, ctx: Context) -> Tuple[Value, Tuple[int, ...]]:
    if is_flat(ledger) or ctx.utterance_seq is None: return 0, ()
    n = sum(1 for h in cell.changed if h and h in ctx.utterance_text)
    return n, ((ctx.utterance_seq,) if n else ())


def stage_utter_neighbor(cell: Candidate, ledger: Any, ctx: Context) -> Tuple[Value, Tuple[int, ...]]:
    if is_flat(ledger) or ctx.utterance_seq is None: return 0, ()
    n = 0
    for h in cell.changed:
        if any(w and w in ctx.utterance_text for w in ctx.neighbors(h)): n += 1
    return n, ((ctx.utterance_seq,) if n else ())


def stage_recency(cell: Candidate, ledger: Any, ctx: Context) -> Tuple[Value, Tuple[int, ...]]:
    if is_flat(ledger): return None, ()
    seq = ledger.last_seq('observed_cell', cell.key)
    return seq, (() if seq is None else (seq,))


def stage_decided(cell: Candidate, ledger: Any, ctx: Context) -> Tuple[Value, Tuple[int, ...]]:
    if is_flat(ledger): return 0, ()
    n = ledger.count('decided_cell', cell.key)
    return n, (ctx.decisions.get(cell.key, ()) if n else ())


# (name, function, formula, which direction is higher, key of the comparison tuple: smaller tuple = higher rank)
STAGES: Tuple[Tuple[str, StageFn, str, str], ...] = (
    ('distance', stage_distance, 's1 = number of moves on the path', 'smaller'),
    ('utter_verbatim', stage_utter_verbatim, 's2 = |{h in changed fillers : h is a substring of U}|, U = the latest utterance that is not the anchor sentence of the turn', 'larger'),
    ('utter_neighbor', stage_utter_neighbor, 's3 = |{h in changed fillers : some neighbour of h is a substring of U}|, U = the latest utterance that is not the anchor sentence of the turn', 'larger'),
    ('recency', stage_recency, 's4 = ledger.last_seq("observed_cell", cell_key); None (never focused) is the top, then older first', 'None, then older'),
    ('decided', stage_decided, 's5 = ledger.count("decided_cell", cell_key)', 'larger'),
)
STAGE_NAMES: Tuple[str, ...] = tuple(s[0] for s in STAGES)


def _order(name: str, value: Value) -> Tuple[int, ...]:
    """The comparison key of one stage value: a smaller tuple is a higher rank."""
    if name == 'distance': return (value,)
    if name in ('utter_verbatim', 'utter_neighbor', 'decided'): return (-value,)
    if name == 'recency': return (0, 0) if value is None else (1, value)
    raise ValueError('UNKNOWN_STAGE:%s' % name)


@dataclass(frozen=True)
class Ranking:
    ranks: Tuple[Tuple[str, ...], ...]    # rank 1 first; inside a rank the cell keys are in string order (display only)
    trace: Mapping[str, Any]


def rank(cells: Sequence[Candidate], ledger: Any = FLAT, context: Optional[Context] = None) -> Ranking:
    """Compute EVERY stage value of EVERY cell first, then put cells with the same tuple of stage keys into one rank. No `min`, no `max`
    and no `sorted(...)[0]` picks a winner: a rank with two cells is a TIE, whatever order the cells were passed in."""
    ctx = context if context is not None else build_context(ledger)
    seen_keys: Dict[str, bool] = {}
    rows: List[Tuple[Tuple[Tuple[int, ...], ...], str, Dict[str, Value], Dict[str, List[int]]]] = []
    for cell in cells:
        if cell.key in seen_keys: raise ValueError('DUPLICATE_CELL_KEY')
        seen_keys[cell.key] = True
        values: Dict[str, Value] = {}
        seqs: Dict[str, List[int]] = {}
        for name, fn, _formula, _better in STAGES:
            value, made_by = fn(cell, ledger, ctx)
            values[name], seqs[name] = value, list(made_by)
        rows.append((tuple(_order(n, values[n]) for n in STAGE_NAMES), cell.key, values, seqs))
    groups: Dict[Tuple[Tuple[int, ...], ...], List[Tuple[str, Dict[str, Value], Dict[str, List[int]]]]] = {}
    for order_key, key, values, seqs in rows:
        groups.setdefault(order_key, []).append((key, values, seqs))
    # the group keys are pairwise different, so ordering the groups cannot tie; this orders groups, it does not pick a cell
    ordered = sorted(groups.items(), key=lambda item: item[0])
    ranks: List[Tuple[str, ...]] = []
    trace_cells: List[Dict[str, Any]] = []
    for position, (_order_key, members) in enumerate(ordered, 1):
        members_in_display_order = sorted(members, key=lambda m: m[0])    # string order of cell keys: a display order, never a rank
        ranks.append(tuple(m[0] for m in members_in_display_order))
        for key, values, seqs in members_in_display_order:
            trace_cells.append({'cell_key': key, 'rank': position, 'values': values, 'ledger_seqs': seqs})
    boundaries: List[Dict[str, Any]] = []
    for i in range(len(ordered) - 1):
        a, b = ordered[i][0], ordered[i + 1][0]
        stage = next(STAGE_NAMES[j] for j in range(len(STAGE_NAMES)) if a[j] != b[j])
        boundaries.append({'between': [i + 1, i + 2], 'decided_by': stage})
    if is_flat(ledger):
        ledger_info: Dict[str, Any] = {'state': 'FLAT', 'events': 0, 'last_seq': None}
    else:
        evs = list(ledger.events())
        ledger_info = {'state': 'LEDGER', 'events': len(evs), 'last_seq': evs[-1]['seq'] if evs else None}
    trace = {
        'ledger': ledger_info,
        'stages': [{'name': n, 'formula': f, 'higher_is': b} for n, _fn, f, b in STAGES],
        'cells': trace_cells,
        'boundaries': boundaries,
        'rank1': ({'kind': 'EMPTY', 'size': 0} if not ranks else {'kind': 'SINGLE' if len(ranks[0]) == 1 else 'TIE', 'size': len(ranks[0])}),
        'utterance': {'used_seq': ctx.utterance_seq, 'skipped_same_as_anchor': list(ctx.skipped_as_anchor)},
    }
    return Ranking(tuple(ranks), trace)
