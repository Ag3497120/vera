"""W1-g decisions B and C: a supersede event that is not operative is kept, typed and counted.

C: the merged log keeps a supersede event whose replacement record does not point back, as
   ``op: "supersede"``; it retires nothing (the replacement record is the authority).
B: nothing is dropped silently: ``merge_report`` classifies every relation and reports
   declared / retained / dropped counts that are measured by matching the output;
   ``Memory.supersede_accounting`` reports what the store did with each event.
"""
import itertools
import json

import pytest

from verantyx.memory_frame import Memory
from verantyx.memory_merge import (
    MergeReport, SupersedeStatus, active_records, conflicts, merge_files, merge_logs, merge_report,
)


def fact(rid, value='v', supersedes=None):
    record = {'id': rid, 'kind': 'FACT', 'slots': {'subject': 'Mika', 'attribute': 'city', 'value': value},
              'author': 'a', 'ts': 't', 'witness': None, 'sentence': f'Mikaのcityは{value}である。',
              'normalized': {}}
    record['supersedes'] = supersedes
    return {'op': 'write', 'record': record}


def event(old, new, op='supersede', **extra):
    return {'op': op, 'id': old, 'by': new, **extra}


def ids(records):
    return [record['id'] for record in records]


# ------------------------------------------------------------- decision C
def test_event_without_pointer_is_kept_as_supersede_and_retires_nothing():
    log = [fact('old', 'Kyoto'), fact('new', 'Osaka'), event('old', 'new', ts='T1')]
    merged = merge_logs(log, [])
    assert event('old', 'new', ts='T1') in merged                  # op stays "supersede", payload verbatim
    assert not any(e['op'] == 'pending_supersede' for e in merged)
    assert ids(active_records(merged)) == ['new', 'old']          # old is not retired
    assert [c.record_ids for c in conflicts(merged)] == [('new', 'old')]


def test_event_with_a_pointer_to_another_record_is_kept_and_retires_nothing():
    log = [fact('old'), fact('other'), fact('new', supersedes='other'), event('old', 'new')]
    merged = merge_logs(log, [])
    assert event('old', 'new') in merged
    assert ids(active_records(merged)) == ['new', 'old']          # 'other' is retired by its own pointer


def test_operative_event_still_retires():
    merged = merge_logs([fact('old'), fact('new', supersedes='old'), event('old', 'new')], [])
    assert ids(active_records(merged)) == ['new']
    assert event('old', 'new') in merged


# ------------------------------------------------------------- decision B: typed reasons and counts
def _by_pair(report):
    return {(s.old, s.new): s for s in report.supersedes}


def test_no_pointer_and_wrong_pointer_have_different_reasons():
    report = merge_report(
        [fact('a'), fact('b'), event('a', 'b')],
        [fact('c'), fact('d', supersedes='c'), event('e', 'd'), fact('e')],
    )
    pairs = _by_pair(report)
    assert isinstance(report, MergeReport) and isinstance(pairs[('a', 'b')], SupersedeStatus)
    assert (pairs[('a', 'b')].status, pairs[('a', 'b')].reason) == ('NONOPERATIVE', 'REPLACEMENT_POINTER_ABSENT')
    assert (pairs[('e', 'd')].status, pairs[('e', 'd')].reason) == ('NONOPERATIVE', 'REPLACEMENT_POINTER_MISMATCH')
    assert (pairs[('c', 'd')].status, pairs[('c', 'd')].reason, pairs[('c', 'd')].declared) == (
        'OPERATIVE', 'RECORD_POINTER_ONLY', False)


def test_every_status_and_reason_is_reported_and_counts_add_up():
    log = [
        fact('p1'), fact('n1', supersedes='p1'), event('p1', 'n1'),         # OPERATIVE, matches
        fact('p2'), fact('n2'), event('p2', 'n2'),                           # NONOPERATIVE, absent
        event('p3', 'n3'),                                                   # PENDING, record missing
        fact('p4'), fact('n4', supersedes='p4'),                             # OPERATIVE, record pointer only
    ]
    report = merge_report(log, [])
    got = {(s.old, s.new): (s.status, s.reason, s.declared) for s in report.supersedes}
    assert got == {
        ('p1', 'n1'): ('OPERATIVE', 'REPLACEMENT_POINTER_MATCHES', True),
        ('p2', 'n2'): ('NONOPERATIVE', 'REPLACEMENT_POINTER_ABSENT', True),
        ('p3', 'n3'): ('PENDING', 'REPLACEMENT_NOT_PRESENT', True),
        ('p4', 'n4'): ('OPERATIVE', 'RECORD_POINTER_ONLY', False),
    }
    assert dict(report.counts) == {'OPERATIVE': 2, 'PENDING': 1, 'NONOPERATIVE': 1}
    assert sum(report.counts.values()) == len(report.supersedes)
    assert [(s.old, s.new) for s in report.supersedes] == sorted(got)
    assert list(report.events) == merge_logs(log, [])             # the same output as merge_logs


def test_counts_list_zero_statuses_too():
    report = merge_report([fact('a')], [])
    assert dict(report.counts) == {'OPERATIVE': 0, 'PENDING': 0, 'NONOPERATIVE': 0}
    assert (report.declared_events, report.retained_events, report.dropped_events) == (0, 0, 0)


def test_declared_retained_and_dropped_are_counted_from_the_output():
    # three distinct declared events (two for one relation, one duplicate that must not count twice)
    log = [fact('a'), fact('b'), event('a', 'b', ts=1), event('a', 'b', ts=2), event('a', 'b', ts=2),
           event('x', 'y', op='pending_supersede')]
    report = merge_report(log, [])
    assert report.declared_events == 3
    assert report.retained_events == sum(
        1 for e in report.events if e['op'] in ('supersede', 'pending_supersede'))
    assert report.dropped_events == report.declared_events - report.retained_events == 0


def test_a_supersede_and_its_pending_form_are_one_declaration():
    report = merge_report([event('x', 'y')], [event('x', 'y', op='pending_supersede')])
    assert report.declared_events == 1 and report.retained_events == 1
    assert [e['op'] for e in report.events] == ['pending_supersede']


# ------------------------------------------------ pending becomes operative or non-operative
def test_pending_event_becomes_operative_when_the_pointer_arrives():
    pending = merge_logs([fact('old'), event('old', 'new')], [])
    assert [e['op'] for e in pending if e['op'] != 'write'] == ['pending_supersede']
    done = merge_report(pending, [fact('new', supersedes='old')])
    assert _by_pair(done)[('old', 'new')].status == 'OPERATIVE'
    assert event('old', 'new') in done.events
    assert ids(active_records(list(done.events))) == ['new']


def test_pending_event_becomes_nonoperative_without_a_pointer_and_is_still_in_the_output():
    pending = merge_logs([fact('old'), event('old', 'new')], [])
    done = merge_report(pending, [fact('new')])
    assert _by_pair(done)[('old', 'new')].status == 'NONOPERATIVE'
    assert event('old', 'new') in done.events
    assert ids(active_records(list(done.events))) == ['new', 'old']


# ----------------------------------------- merge algebra with the non-operative events kept
def _three_logs():
    a = [fact('o1'), fact('n1'), event('o1', 'n1', ts=1)]                       # non-operative (absent)
    b = [fact('o2'), event('o2', 'n2', ts=2), fact('o3'), fact('n3', supersedes='o3'), event('o3', 'n3')]  # pending + operative
    c = [fact('n2', supersedes='nothing'), fact('o4'), fact('n4', supersedes='o4'), event('o1', 'n1', ts=1),
         event('o4', 'n4'), event('o2', 'n2', ts=2, op='pending_supersede')]    # non-operative (mismatch) + dups
    return a, b, c


def test_merge_is_commutative_associative_and_idempotent_with_every_kind_of_event():
    a, b, c = _three_logs()
    assert merge_logs(a, b) == merge_logs(b, a)
    for x, y, z in itertools.permutations((a, b, c)):
        assert merge_logs(merge_logs(x, y), z) == merge_logs(x, merge_logs(y, z)) == merge_logs(merge_logs(x, z), y)
    ab = merge_logs(a, b)
    assert merge_logs(ab, []) == ab
    assert merge_logs(ab, ab) == ab
    abc = merge_logs(merge_logs(a, b), c)
    assert merge_logs(abc, a) == abc


def test_status_of_each_relation_does_not_depend_on_merge_order():
    # A merge writes pointer-derived events into its output, so a later merge sees them as declared:
    # `declared` / the OPERATIVE reason / declared_events may differ by staging. The relation and its
    # status do not.
    a, b, c = _three_logs()
    r1, r2 = merge_report(merge_logs(a, b), c), merge_report(a, merge_logs(c, b))
    assert [(s.old, s.new, s.status) for s in r1.supersedes] == [(s.old, s.new, s.status) for s in r2.supersedes]
    assert dict(r1.counts) == dict(r2.counts)
    assert r1.dropped_events == r2.dropped_events == 0
    assert r1.events == r2.events


# ------------------------------------------------- Memory: the reader applies the same rule
def _write_log(path, events):
    path.write_text(''.join(json.dumps(e) + '\n' for e in events), encoding='utf-8')


def test_merge_files_then_memory_keeps_the_target_active_and_accounts_for_the_event(tmp_path):
    left, right, out = tmp_path / 'l.jsonl', tmp_path / 'r.jsonl', tmp_path / 'm.jsonl'
    _write_log(left, [fact('old', 'x'), event('old', 'new')])
    _write_log(right, [fact('new', 'y')])
    merge_files(left, right, out)
    reopened = Memory(str(out))
    assert sorted(ids(reopened.active())) == ['new', 'old']
    assert reopened.superseded == {}
    accounting = reopened.supersede_accounting()
    assert accounting['applied'] == 0
    assert accounting['nonoperative'] == [
        {'id': 'old', 'by': 'new', 'op': 'supersede', 'reason': 'REPLACEMENT_POINTER_ABSENT'}]
    assert accounting['waiting_for_record'] == []
    assert accounting['counts'] == {'applied': 0, 'nonoperative': 1, 'waiting_for_record': 0, 'events': 1}


def test_memory_gives_a_different_reason_for_a_pointer_to_another_record(tmp_path):
    path = tmp_path / 'm.jsonl'
    _write_log(path, [fact('old'), fact('other'), fact('new', supersedes='other'), event('old', 'new')])
    memory = Memory(str(path))
    assert [e['reason'] for e in memory.supersede_accounting()['nonoperative']] == ['REPLACEMENT_POINTER_MISMATCH']
    assert 'old' in ids(memory.active())


def test_memory_event_before_its_record_waits_and_is_then_settled(tmp_path):
    ok, bad = tmp_path / 'ok.jsonl', tmp_path / 'bad.jsonl'
    _write_log(ok, [fact('old'), event('old', 'new'), fact('new', supersedes='old')])
    _write_log(bad, [fact('old'), event('old', 'new'), fact('new')])
    retired, kept = Memory(str(ok)), Memory(str(bad))
    assert ids(retired.active()) == ['new'] and retired.supersede_accounting()['counts']['applied'] == 1
    assert sorted(ids(kept.active())) == ['new', 'old']
    assert kept.supersede_accounting()['counts'] == {
        'applied': 0, 'nonoperative': 1, 'waiting_for_record': 0, 'events': 1}
    waiting = tmp_path / 'wait.jsonl'
    _write_log(waiting, [fact('old'), event('old', 'new')])
    held = Memory(str(waiting))
    assert held.supersede_accounting()['waiting_for_record'] == [
        {'id': 'old', 'by': 'new', 'op': 'supersede', 'reason': 'REPLACEMENT_NOT_PRESENT'}]
    assert ids(held.active()) == ['old']


def test_memory_with_a_malformed_pointer_does_not_raise_and_does_not_apply(tmp_path):
    path = tmp_path / 'm.jsonl'
    _write_log(path, [fact('old'), fact('new', supersedes=['old', 7]), event('old', 'new')])
    memory = Memory(str(path))
    assert sorted(ids(memory.active())) == ['new', 'old']
    assert [e['reason'] for e in memory.supersede_accounting()['nonoperative']] == ['REPLACEMENT_POINTER_INVALID']


def test_memorys_own_write_with_supersedes_still_retires(tmp_path):
    memory = Memory(str(tmp_path / 'm.jsonl'), now=lambda: '2026-10-03T00:00:00')
    old = memory.write('FACT', 'a', witness={'kind': 'testimony'}, subject='Mika', attribute='city', value='Kyoto')
    new = memory.write('FACT', 'a', witness={'kind': 'testimony'}, supersedes=old['id'], subject='Mika', attribute='city', value='Osaka')
    assert ids(memory.active()) == [new['id']]
    assert memory.superseded == {old['id']: new['id']}
    reopened = Memory(str(tmp_path / 'm.jsonl'))
    assert ids(reopened.active()) == [new['id']]
    assert reopened.supersede_accounting()['counts'] == {
        'applied': 1, 'nonoperative': 0, 'waiting_for_record': 0, 'events': 1}


def test_a_view_of_a_memory_with_only_records_and_superseded_can_report_accounting():
    view = Memory.__new__(Memory)
    view.records, view.superseded = {}, {}
    assert view.supersede_accounting() == {
        'applied': 0, 'nonoperative': [], 'waiting_for_record': [],
        'counts': {'applied': 0, 'nonoperative': 0, 'waiting_for_record': 0, 'events': 0}}
    assert view.active() == []


def test_many_events_before_their_records_are_all_settled(tmp_path):
    # 2000 events arrive before their records; each is settled when its record arrives.
    n = 2000
    events = [event(f'o{i}', f'n{i}') for i in range(n)]
    events += [fact(f'o{i}') for i in range(n)] + [fact(f'n{i}', supersedes=f'o{i}') for i in range(n)]
    path = tmp_path / 'big.jsonl'
    _write_log(path, events)
    memory = Memory(str(path))
    assert memory.supersede_accounting()['counts'] == {
        'applied': n, 'nonoperative': 0, 'waiting_for_record': 0, 'events': n}
    assert len(memory.active()) == n


# ------------------------------------------------- Memory built without Memory.__init__ (round 2 review)
class _NoInitMemory(Memory):
    """Same shape as project_frame._ExchangeMemory: a subclass that never calls Memory.__init__.

    It sets only the attributes that existed before W1-g and routes ``_append`` to ``_apply``.
    """

    def __init__(self):
        from pathlib import Path
        self.path = Path('<no-init-memory>')
        self.now = lambda: '1970-01-01T00:00:00'
        self.resolver = None
        self.records = {}
        self.superseded = {}
        self.aliases = {}
        self._view = None

    def _append(self, event):
        self._apply(event)


def test_decision_from_exchange_without_memory_returns_a_draft():
    from verantyx.project_frame import DecisionDraft, decision_from_exchange
    result = decision_from_exchange('ルーターの未読の上限は？', ['100', '200'], '100', session='s1')
    assert isinstance(result, DecisionDraft)


def test_subclass_without_init_can_write_and_supersede_and_account():
    memory = _NoInitMemory()
    old = memory.write('FACT', 'a', witness={'kind': 'testimony'}, subject='Mika', attribute='city', value='Kyoto')
    new = memory.write('FACT', 'a', witness={'kind': 'testimony'}, supersedes=old['id'], subject='Mika', attribute='city', value='Osaka')
    assert memory.superseded == {old['id']: new['id']}
    assert ids(memory.active()) == [new['id']]
    assert memory.supersede_accounting()['counts'] == {
        'applied': 1, 'nonoperative': 0, 'waiting_for_record': 0, 'events': 1}


def test_subclass_without_init_applies_an_event_that_arrives_before_its_record():
    memory = _NoInitMemory()
    memory._apply(event('o1', 'n1'))                      # the event first: waits
    assert memory.supersede_accounting()['counts']['waiting_for_record'] == 1
    memory._apply(fact('o1'))
    memory._apply(fact('n1', supersedes='o1'))            # its record arrives with the pointer
    assert memory.superseded == {'o1': 'n1'}
    assert memory.supersede_accounting()['counts'] == {
        'applied': 1, 'nonoperative': 0, 'waiting_for_record': 0, 'events': 1}
