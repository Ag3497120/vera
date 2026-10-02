import pytest

from verantyx.memory_merge import active_records, conflicts, merge_logs


def record(rid, subject='Mika', attribute='status', value='ready', **extra):
    return {
        'id': rid,
        'slots': {'subject': subject, 'attribute': attribute, 'value': value},
        **extra,
    }


def write(rec):
    return {'op': 'write', 'record': rec}


def test_duplicate_write_with_reordered_keys_is_idempotent():
    first = {'id': 'r1', 'slots': {'subject': 'Mika', 'attribute': 'status', 'value': 'ready'}}
    second = {'slots': {'value': 'ready', 'attribute': 'status', 'subject': 'Mika'}, 'id': 'r1'}

    merged = merge_logs([write(first)], [write(second)])

    assert len(merged) == 1
    assert merged[0]['record']['id'] == 'r1'
    assert active_records(merged) == [merged[0]['record']]


def test_merge_is_commutative_for_surface_variants():
    plain = write(record('r1', surface='Mika is ready.'))
    polite = write(record('r2', surface='Mika is ready, please.'))

    assert merge_logs([plain], [polite]) == merge_logs([polite], [plain])


def test_polite_plain_surface_variants_do_not_create_typed_conflict():
    events = [
        write(record('r1', surface='Mika is ready.')),
        write(record('r2', surface='Mika is ready, please.')),
    ]

    assert conflicts(events) == []
    assert len(active_records(events)) == 2


def test_word_order_and_particle_variants_do_not_create_typed_conflict():
    events = [
        write(record('r1', surface='太郎は東京に行く')),
        write(record('r2', surface='東京に太郎が行く')),
    ]

    assert conflicts(events) == []


def test_surface_paraphrases_do_not_hide_different_typed_values():
    events = [
        write(record('r1', value='approved', surface='Sure, that works.')),
        write(record('r2', value='rejected', surface='I cannot agree.')),
    ]

    found = conflicts(events)

    assert len(found) == 1
    assert found[0].subject == 'Mika'
    assert found[0].attribute == 'status'
    assert found[0].record_ids == ('r1', 'r2')
    assert found[0].values == ('approved', 'rejected')


@pytest.mark.xfail(
    strict=False,
    reason='DEFECT: synonymous textual values are compared exactly and produce a false conflict',
)
def test_synonymous_slot_value_paraphrases_keep_same_verdict():
    events = [
        write(record('r1', attribute='readiness', value='ready')),
        write(record('r2', attribute='readiness', value='all set')),
    ]

    assert conflicts(events) == []


def test_number_change_changes_verdict_to_conflict():
    events = [
        write(record('r1', attribute='count', value=2)),
        write(record('r2', attribute='count', value=3)),
    ]

    found = conflicts(events)

    assert len(found) == 1
    assert found[0].record_ids == ('r1', 'r2')
    assert found[0].values == (2, 3)


def test_entity_swap_changes_subject_grouping():
    same_entity = [
        write(record('r1', subject='Mika', value='ready')),
        write(record('r2', subject='Mika', value='waiting')),
    ]
    swapped_entity = [
        write(record('r1', subject='Mika', value='ready')),
        write(record('r2', subject='Ren', value='waiting')),
    ]

    assert len(conflicts(same_entity)) == 1
    assert conflicts(swapped_entity) == []


def test_alias_surface_variants_do_not_change_conflicts():
    base = [write(record('r1', value='approved'))]
    aliases = [
        {'op': 'alias', 'id': 'r1', 'surface': 'Mika approved it.'},
        {'op': 'alias', 'id': 'r1', 'surface': 'Approval came from Mika.'},
    ]

    assert conflicts(base) == conflicts(base + aliases)
    assert len(merge_logs(aliases, aliases)) == 2


def test_three_way_staged_merge_keeps_supersession_state():
    old = write(record('r1', value='draft'))
    new = write(record('r2', value='final', supersedes=['r1']))
    annotation = {'op': 'alias', 'id': 'r2', 'surface': 'final version'}

    left_grouped = merge_logs(merge_logs([old], [new]), [annotation])
    right_grouped = merge_logs([old], merge_logs([new], [annotation]))

    assert left_grouped == right_grouped
    assert [item['id'] for item in active_records(left_grouped)] == ['r2']
    assert conflicts(left_grouped) == []


def test_duplicate_id_collision_is_rejected_in_both_writer_orders():
    first = write(record('r1', value='approved'))
    changed = write(record('r1', value='rejected'))

    with pytest.raises(ValueError, match='record id collision'):
        merge_logs([first], [changed])
    with pytest.raises(ValueError, match='record id collision'):
        merge_logs([changed], [first])


def test_supersession_cycle_is_rejected():
    events = [
        write(record('r1', supersedes=['r2'])),
        write(record('r2', supersedes=['r1'])),
    ]

    with pytest.raises(ValueError, match='supersession cycle'):
        merge_logs(events, [])
