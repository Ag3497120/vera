import pytest

from verantyx.memory_merge import active_records, conflicts, merge_logs


def write(record):
    return {'op': 'write', 'record': record}


def test_merge_is_commutative_and_deduplicates_identical_writes():
    first = write({'id': 'a', 'slots': {'subject': 'Mika', 'attribute': 'city', 'value': 'Kyoto'}})
    second = write({'id': 'b', 'slots': {'subject': 'Noah', 'attribute': 'city', 'value': 'Osaka'}})

    left = merge_logs([first, first], [second])
    right = merge_logs([second], [first])

    assert left == right
    assert left == [first, second]


def test_different_record_data_with_same_id_is_rejected():
    first = write({'id': 'same', 'value': 'source value'})
    second = write({'id': 'same', 'value': 'invented value'})

    with pytest.raises(ValueError, match='record id collision'):
        merge_logs([first], [second])


def test_conflict_lists_each_active_source_record_and_its_value():
    events = [
        write({'id': 'a', 'slots': {'subject': 'Mika', 'attribute': 'status', 'value': 'approved'}}),
        write({'id': 'b', 'slots': {'subject': 'Mika', 'attribute': 'status', 'value': 'declined'}}),
    ]

    found, = conflicts(events)

    assert found.kind == 'CONFLICT'
    assert found.subject == 'Mika'
    assert found.attribute == 'status'
    assert found.record_ids == ('a', 'b')
    assert found.values == ('approved', 'declined')


def test_equal_values_for_one_subject_are_not_a_conflict():
    events = [
        write({'id': 'a', 'subject': 'Mika', 'attribute': 'city', 'value': 'Kyoto'}),
        write({'id': 'b', 'subject': 'Mika', 'attribute': 'city', 'value': 'Kyoto'}),
    ]

    assert conflicts(events) == []


def test_different_subjects_are_not_combined_into_a_conflict():
    events = [
        write({'id': 'a', 'subject': 'Mika', 'attribute': 'city', 'value': 'Kyoto'}),
        write({'id': 'b', 'subject': 'Noah', 'attribute': 'city', 'value': 'Osaka'}),
    ]

    assert conflicts(events) == []


def test_superseded_record_does_not_contribute_a_stale_value():
    old = write({'id': 'old', 'subject': 'Mika', 'attribute': 'status', 'value': 'pending'})
    new = write({
        'id': 'new',
        'subject': 'Mika',
        'attribute': 'status',
        'value': 'approved',
        'supersedes': 'old',
    })
    other = write({'id': 'other', 'subject': 'Mika', 'attribute': 'status', 'value': 'declined'})

    merged = merge_logs([old, other], [new])

    assert [record['id'] for record in active_records(merged)] == ['new', 'other']
    found, = conflicts(merged)
    assert found.record_ids == ('new', 'other')
    assert found.values == ('approved', 'declined')


def test_negated_source_value_is_preserved_without_rewriting():
    event = write({
        'id': 'a',
        'slots': {
            'subject': 'Mika',
            'attribute': 'permission',
            'value': 'not approved',
        },
    })

    assert merge_logs([event], []) == [event]
    found, = conflicts([
        event,
        write({'id': 'b', 'slots': {'subject': 'Mika', 'attribute': 'permission', 'value': 'approved'}}),
    ])
    assert found.values == ('not approved', 'approved')


def test_partial_property_is_retained_without_completing_missing_slots():
    partial = write({'id': 'partial', 'slots': {'subject': 'Mika', 'value': 'Kyoto'}})

    assert merge_logs([partial], []) == [partial]
    assert conflicts([partial]) == []


def test_role_typed_entities_and_values_keep_their_source_structure():
    subject = {'entity': 'Mika', 'role': 'agent'}
    first_value = {'entity': 'Kyoto', 'role': 'destination'}
    second_value = {'entity': 'Osaka', 'role': 'destination'}
    events = [
        write({'id': 'a', 'slots': {'subject': subject, 'attribute': 'travel', 'value': first_value}}),
        write({'id': 'b', 'slots': {'subject': subject, 'attribute': 'travel', 'value': second_value}}),
    ]

    merged = merge_logs(events, [])
    found, = conflicts(merged)

    assert [event['record']['slots']['value'] for event in merged] == [first_value, second_value]
    assert found.subject == subject
    assert found.values == (first_value, second_value)
    assert found.record_ids == ('a', 'b')


def test_partial_supersession_link_stays_pending_until_target_record_arrives():
    old = write({'id': 'old', 'subject': 'Mika', 'attribute': 'city', 'value': 'Kyoto'})
    pending = merge_logs([old], [{'op': 'supersede', 'id': 'old', 'by': 'new'}])

    with pytest.raises(ValueError, match='dangling supersession reference'):
        active_records(pending)

    new = write({'id': 'new', 'subject': 'Mika', 'attribute': 'city', 'value': 'Osaka'})
    completed = merge_logs(pending, [new])

    assert [record['id'] for record in active_records(completed)] == ['new']
    assert conflicts(completed) == []
