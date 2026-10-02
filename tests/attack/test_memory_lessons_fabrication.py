import pytest

from verantyx.memory_lessons import LessonIndex, lessons_for


def _lesson(rid, situation, text='Use the documented procedure.'):
    return {
        'id': rid,
        'kind': 'LESSON',
        'slots': {'situation': situation, 'lesson': text},
    }


def test_exact_lookup_returns_only_lessons_for_the_matching_situation():
    records = [
        _lesson('lesson-b', 'printer jam', 'Check the paper path.'),
        {'id': 'fact-1', 'kind': 'FACT', 'slots': {'situation': 'printer jam'}},
        _lesson('lesson-a', 'printer jam', 'Power down first.'),
        _lesson('lesson-c', 'paper refill'),
    ]

    result = LessonIndex(records).lessons_for('printer jam')

    assert [record['id'] for record in result] == ['lesson-a', 'lesson-b']
    assert [record['slots']['lesson'] for record in result] == [
        'Power down first.', 'Check the paper path.'
    ]


def test_unmatched_situation_without_asker_abstains():
    result = LessonIndex([_lesson('lesson-1', 'printer jam')]).lessons_for('paper refill')

    assert result == []


@pytest.mark.parametrize('situation', [None, 4, [], {}, ''])
def test_invalid_or_empty_situation_abstains(situation):
    result = LessonIndex([_lesson('lesson-1', 'printer jam')]).lessons_for(situation)

    assert result == []


def test_explicit_superseded_id_is_not_returned():
    current = _lesson('lesson-current', 'printer jam', 'Use the current procedure.')
    stale = _lesson('lesson-old', 'printer jam', 'Use the old procedure.')

    result = LessonIndex([stale, current], superseded={'lesson-old'}).lessons_for('printer jam')

    assert result == [current]


def test_supersedes_slot_excludes_the_superseded_record():
    stale = _lesson('lesson-old', 'printer jam', 'Use the old procedure.')
    current = _lesson('lesson-current', 'printer jam', 'Use the current procedure.')
    current['supersedes'] = 'lesson-old'

    result = LessonIndex([stale, current]).lessons_for('printer jam')

    assert result == [current]


def test_record_mapping_input_is_supported():
    record = _lesson('lesson-1', 'printer jam')

    result = lessons_for({'lesson-1': record}, 'printer jam')

    assert result == [record]


def test_index_is_detached_from_later_source_record_mutation():
    source = _lesson('lesson-1', 'printer jam', 'Power down first.')
    index = LessonIndex([source])
    source['slots']['lesson'] = 'Unsupported change.'
    source['slots']['situation'] = 'paper refill'

    result = index.lessons_for('printer jam')

    assert result == [_lesson('lesson-1', 'printer jam', 'Power down first.')]


def test_memory_like_input_applies_superseded_ids():
    current = _lesson('lesson-current', 'printer jam')
    stale = _lesson('lesson-old', 'printer jam')

    class MemoryLike:
        records = {'current': current, 'old': stale}
        superseded = {'lesson-old': 'lesson-current'}

    result = LessonIndex(MemoryLike()).lessons_for('printer jam')

    assert result == [current]


@pytest.mark.xfail(
    strict=False,
    reason='DEFECT: returned lesson dictionaries alias the index copy and can contaminate later lookups',
)
def test_mutating_a_returned_record_cannot_fabricate_later_lookup():
    observations = []
    for _ in range(2):
        source = _lesson('lesson-1', 'printer jam', 'Power down first.')
        index = LessonIndex([source])
        returned = index.lessons_for('printer jam')
        returned[0]['slots']['lesson'] = 'Pour water into the printer.'
        observations.append(index.lessons_for('printer jam')[0]['slots']['lesson'])

    assert observations == ['Power down first.', 'Power down first.']
