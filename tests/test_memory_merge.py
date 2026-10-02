import json
import random

import pytest

from verantyx.memory_merge import (
    active_records,
    conflicts,
    merge_files,
    merge_logs,
)


def fact(rid, subject='router', attribute='limit', value='10', **extra):
    record = {
        'id': rid,
        'kind': 'FACT',
        'slots': {'subject': subject, 'attribute': attribute, 'value': value},
        'author': 'agent',
        'ts': '2026-01-01T00:00:00',
        'witness': {'kind': 'testimony'},
        'sentence': f'{subject}の{attribute}は{value}である。',
        'supersedes': None,
    }
    record.update(extra)
    return {'op': 'write', 'record': record}


def link(old, new):
    return {'op': 'supersede', 'id': old, 'by': new}


@pytest.mark.parametrize('left,right', [
    ('a', 'b'), ('1', '2'), ('red', 'blue'), ('low', 'high'),
    ('yes', 'no'), ('東京', '大阪'), ('10', '11'), ('known', 'unknown'),
    ('open', 'closed'), ('small', 'large'), ('x', 'y'), ('first', 'second'),
])
def test_active_distinct_values_are_typed_conflicts(left, right):
    merged = merge_logs([fact('left', value=left)], [fact('right', value=right)])
    report, = conflicts(merged)
    assert report.kind == 'CONFLICT'
    assert report.subject == 'router'
    assert report.attribute == 'limit'
    assert report.record_ids == ('left', 'right')
    assert report.ids == report.record_ids
    assert report.values == (left, right)


@pytest.mark.parametrize('seed', range(30))
def test_random_three_way_union_is_commutative_and_associative(seed):
    rng = random.Random(seed)
    logs = [[], [], []]
    for i in range(rng.randint(0, 24)):
        event = fact(
            f'{seed}-{i}',
            subject=f's{rng.randrange(4)}',
            attribute=f'a{rng.randrange(3)}',
            value=f'v{rng.randrange(5)}',
        )
        logs[rng.randrange(3)].append(event)

    left = merge_logs(merge_logs(logs[0], logs[1]), logs[2])
    right = merge_logs(logs[0], merge_logs(logs[1], logs[2]))
    reverse = merge_logs(logs[2], merge_logs(logs[1], logs[0]))
    assert left == right == reverse
    assert active_records(left) == active_records(right)
    assert conflicts(left) == conflicts(right)


@pytest.mark.parametrize('seed', range(15))
def test_random_supersession_graph_survives_three_way_merge(seed):
    rng = random.Random(1000 + seed)
    logs = [[], [], []]
    count = rng.randint(2, 20)
    for i in range(count):
        logs[rng.randrange(3)].append(fact(
            f'{seed}-{i}', subject=f's{rng.randrange(3)}',
            attribute='state', value=f'v{rng.randrange(4)}',
        ))
    # Increasing ids keep the generated relation graph acyclic while allowing
    # either endpoint of a link to live in a different input log.
    for old in range(count):
        for new in range(old + 1, count):
            if rng.random() < 0.035:
                logs[rng.randrange(3)].append(link(f'{seed}-{old}', f'{seed}-{new}'))
                replacement_id = f'{seed}-{new}'
                replacement = next(
                    event for log in logs for event in log
                    if event.get('op') == 'write' and event['record']['id'] == replacement_id
                )
                supersedes = replacement['record']['supersedes']
                if supersedes is None:
                    replacement['record']['supersedes'] = [f'{seed}-{old}']
                elif isinstance(supersedes, list):
                    supersedes.append(f'{seed}-{old}')
                else:
                    replacement['record']['supersedes'] = [supersedes, f'{seed}-{old}']

    ab_c = merge_logs(merge_logs(logs[0], logs[1]), logs[2])
    a_bc = merge_logs(logs[0], merge_logs(logs[1], logs[2]))
    assert ab_c == a_bc
    assert active_records(ab_c) == active_records(a_bc)
    assert conflicts(ab_c) == conflicts(a_bc)


def test_empty_logs_are_identity():
    events = [fact('one')]
    assert merge_logs([], []) == []
    assert merge_logs(events, []) == merge_logs([], events)


def test_exact_duplicate_record_is_deduplicated():
    event = fact('same')
    assert merge_logs([event], [event]) == [event]


def test_alias_events_are_deduplicated_without_order_dependent_picking():
    first = {'op': 'alias', 'scope': 'kind', 'word': '実測', 'choice': 'FACT', 'status': 'ADOPT'}
    second = {'op': 'alias', 'scope': 'kind', 'word': '実測', 'choice': None, 'status': 'NONE'}
    merged = merge_logs([first, second], [first])
    assert [event for event in merged if event['op'] == 'alias'] == sorted(
        [first, second], key=lambda event: json.dumps(event, ensure_ascii=False, sort_keys=True, separators=(',', ':'))
    )
    assert merge_logs([second], [first]) == merged


def test_same_id_with_different_record_is_rejected():
    with pytest.raises(ValueError, match='id collision'):
        merge_logs([fact('same', value='a')], [fact('same', value='b')])


def test_equal_values_do_not_create_conflict():
    merged = merge_logs([fact('a', value='same')], [fact('b', value='same')])
    assert conflicts(merged) == []
    assert [record['id'] for record in active_records(merged)] == ['a', 'b']


def test_conflict_ids_include_each_active_record():
    merged = merge_logs([fact('a', value='x'), fact('b', value='x')], [fact('c', value='y')])
    assert conflicts(merged)[0].record_ids == ('a', 'b', 'c')


def test_different_subject_or_attribute_does_not_conflict():
    merged = merge_logs(
        [fact('a', subject='one', value='x'), fact('b', attribute='other', value='x')],
        [fact('c', subject='two', value='y'), fact('d', subject='two', attribute='other', value='y')],
    )
    assert conflicts(merged) == []


def test_supersession_link_can_cross_input_logs():
    old = fact('old', value='old value')
    new = fact('new', value='new value', supersedes='old')
    merged = merge_logs([old, link('old', 'new')], [new])
    assert [record['id'] for record in active_records(merged)] == ['new']
    assert conflicts(merged) == []


def test_supersede_event_without_matching_record_pointer_does_not_retire_old():
    old, new = fact('old', value='old value'), fact('new', value='new value')
    merged = merge_logs([old, link('old', 'new')], [new])
    assert [record['id'] for record in active_records(merged)] == ['new', 'old']
    report, = conflicts(merged)
    assert report.record_ids == ('new', 'old')
    assert report.values == ('new value', 'old value')


def test_record_pointer_restores_missing_supersede_event():
    old = fact('old', value='old value')
    new = fact('new', value='new value', supersedes='old')
    merged = merge_logs([old], [new])
    assert link('old', 'new') in merged
    assert [record['id'] for record in active_records(merged)] == ['new']


def test_chained_supersession_across_logs_keeps_only_leaf_active():
    events = merge_logs(
        [fact('a', value='a'), link('a', 'b')],
        [fact('b', value='b', supersedes='a'), fact('c', value='c', supersedes='b'), link('b', 'c')],
    )
    assert [record['id'] for record in active_records(events)] == ['c']


def test_two_conflicts_resolve_with_one_new_record_superseding_both():
    left = [fact('red', value='red'), fact('blue', value='blue')]
    right = [fact('resolved', value='green', supersedes=['red', 'blue']), link('blue', 'resolved')]
    merged = merge_logs(left, right)
    assert [record['id'] for record in active_records(merged)] == ['resolved']
    assert conflicts(merged) == []


def test_conflict_remains_when_only_one_disagreement_is_superseded():
    merged = merge_logs(
        [fact('red', value='red'), fact('blue', value='blue')],
        [fact('resolved', value='green', supersedes='red')],
    )
    assert conflicts(merged)[0].record_ids == ('blue', 'resolved')


def test_competing_superseding_branches_remain_active_and_conflict():
    merged = merge_logs(
        [fact('base', value='base'), link('base', 'left')],
        [fact('left', value='left', supersedes='base'), fact('right', value='right', supersedes='base'),
         link('base', 'right')],
    )
    assert [record['id'] for record in active_records(merged)] == ['left', 'right']
    assert conflicts(merged)[0].record_ids == ('left', 'right')


def test_active_records_reject_dangling_supersession():
    partial = merge_logs([], [link('old', 'new')])
    with pytest.raises(ValueError, match='dangling supersession'):
        active_records(partial)


def test_supersession_cycle_is_rejected():
    with pytest.raises(ValueError, match='cycle'):
        merge_logs([link('a', 'b')], [link('b', 'a')])


def test_malformed_write_without_id_is_rejected():
    with pytest.raises(ValueError, match='non-empty string id'):
        merge_logs([{'op': 'write', 'record': {'kind': 'FACT'}}], [])


def test_file_merge_writes_deterministic_jsonl(tmp_path):
    left = tmp_path / 'left.jsonl'
    right = tmp_path / 'right.jsonl'
    output = tmp_path / 'merged' / 'all.jsonl'
    left.write_text(json.dumps(fact('a'), ensure_ascii=False) + '\n', encoding='utf-8')
    right.write_text(json.dumps(fact('b'), ensure_ascii=False) + '\n', encoding='utf-8')
    merged = merge_files(left, right, output)
    lines = output.read_text(encoding='utf-8').splitlines()
    assert [json.loads(line) for line in lines] == merged
    alternate = tmp_path / 'alternate.jsonl'
    assert merge_files(right, left, alternate) == merged
    assert alternate.read_text(encoding='utf-8') == output.read_text(encoding='utf-8')


def test_file_merge_refuses_to_overwrite_an_input(tmp_path):
    source = tmp_path / 'source.jsonl'
    other = tmp_path / 'other.jsonl'
    source.write_text('', encoding='utf-8')
    other.write_text('', encoding='utf-8')
    with pytest.raises(ValueError, match='separate'):
        merge_files(source, other, source)


def test_flat_typed_record_shape_is_inspected():
    merged = merge_logs(
        [{'op': 'write', 'record': {'id': 'a', 'subject': 's', 'attribute': 'a', 'value': 'x'}}],
        [{'op': 'write', 'record': {'id': 'b', 'subject': 's', 'attribute': 'a', 'value': 'y'}}],
    )
    assert conflicts(merged)[0].record_ids == ('a', 'b')
