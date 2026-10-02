import hashlib
import itertools
import json
import subprocess
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace

import pytest

from verantyx import memory_frame
from verantyx.memory_frame import Memory, WriteRejected
from verantyx.memory_revalidate import RevalidatingMemory


def new_memory(tmp_path):
    ticks = itertools.count()
    return Memory(str(tmp_path / 'memory.jsonl'), now=lambda: f't{next(ticks)}')


def write_fact(memory, witness, *, subject='ルーター', value='8件', supersedes=None):
    return memory.write('FACT', 'test', witness=witness, supersedes=supersedes,
                        subject=subject, attribute='未読上限', value=value)


def write_legacy_fact(tmp_path, witness, *, record_id='legacy-blank'):
    path = tmp_path / 'legacy.jsonl'
    record = {'id': record_id, 'kind': 'FACT', 'slots': {}, 'author': 'test',
              'witness': witness, 'sentence': 'ルーターの未読上限は999件である。'}
    path.write_text(json.dumps({'op': 'write', 'record': record}, ensure_ascii=False) + '\n')
    return Memory(str(path)), record


def hash_witness(path):
    return {'kind': 'file_sha256', 'path': str(path),
            'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def answer_about(wrapper, subject='ルーター'):
    return wrapper.ask_about(subject, '未読上限')


@pytest.mark.parametrize('contents', ['changed', '', 'different bytes', '新しい内容'])
def test_changed_file_hash_is_stale_and_excluded(tmp_path, contents):
    source = tmp_path / 'source.txt'
    source.write_text('original')
    memory = new_memory(tmp_path)
    record = write_fact(memory, hash_witness(source))
    source.write_text(contents)

    result = answer_about(RevalidatingMemory(memory, cache_ttl=0))

    assert record['id'] not in result['records']
    assert result['witness_status'][record['id']] == 'STALE'
    assert record['id'] in result['stale']


def test_deleted_file_hash_is_stale(tmp_path):
    source = tmp_path / 'source.txt'
    source.write_text('original')
    memory = new_memory(tmp_path)
    record = write_fact(memory, hash_witness(source))
    source.unlink()

    result = answer_about(RevalidatingMemory(memory, cache_ttl=0))

    assert result['witness_status'][record['id']] == 'STALE'
    assert record['id'] not in result['records']


def test_unchanged_file_hash_is_fresh_and_answerable(tmp_path):
    source = tmp_path / 'source.txt'
    source.write_text('original')
    memory = new_memory(tmp_path)
    record = write_fact(memory, hash_witness(source))

    result = answer_about(RevalidatingMemory(memory, cache_ttl=0))

    assert record['id'] in result['records']
    assert result['witness_status'][record['id']] == 'FRESH'


@pytest.mark.parametrize('text, expected', [
    ('needle is here', 'FRESH'),
    ('needle moved', 'FRESH'),
    ('something else', 'STALE'),
])
def test_text_witness_is_checked_against_current_file(tmp_path, text, expected):
    source = tmp_path / 'source.txt'
    source.write_text(text)
    memory = new_memory(tmp_path)
    record = write_fact(memory, {'kind': 'text_in_file', 'path': str(source), 'needle': 'needle'})

    result = answer_about(RevalidatingMemory(memory, cache_ttl=0))

    assert result['witness_status'][record['id']] == expected
    # Needle presence alone does not make unrelated file text evidence for the stored fact.
    assert record['id'] not in result['records']
    assert result['verdict'] != 'ANSWER'


def test_deleted_text_witness_is_stale(tmp_path):
    source = tmp_path / 'source.txt'
    source.write_text('needle')
    memory = new_memory(tmp_path)
    record = write_fact(memory, {'kind': 'text_in_file', 'path': str(source), 'needle': 'needle'})
    source.unlink()

    result = answer_about(RevalidatingMemory(memory, cache_ttl=0))

    assert result['witness_status'][record['id']] == 'STALE'
    assert record['id'] not in result['records']


@pytest.mark.parametrize('needle', ['', ' \t\n'])
def test_blank_text_witness_is_stale_and_cannot_support_answer(tmp_path, needle):
    memory, record = write_legacy_fact(
        tmp_path, {'kind': 'text_in_file', 'path': str(tmp_path / 'source.txt'), 'needle': needle})

    result = answer_about(RevalidatingMemory(memory, cache_ttl=0))

    assert result['witness_status'][record['id']] == 'STALE'
    assert record['id'] in result['stale']
    assert record['id'] not in result['records']
    assert result['verdict'] != 'ANSWER'


@pytest.mark.parametrize('needle', ['', ' \t\n'])
def test_blank_text_witness_is_rejected_on_write(tmp_path, needle):
    source = tmp_path / 'source.txt'
    source.write_text('source')
    memory = new_memory(tmp_path)

    with pytest.raises(WriteRejected):
        write_fact(memory, {'kind': 'text_in_file', 'path': str(source), 'needle': needle},
                   value='999件')

    assert memory.records == {}
    assert not memory.path.exists()


def test_core_checker_and_direct_ask_reject_legacy_blank_needle(tmp_path):
    witness = {'kind': 'text_in_file', 'path': str(tmp_path / 'source.txt'), 'needle': ' \t'}
    memory, _ = write_legacy_fact(tmp_path, witness)

    assert memory_frame.check_witness(witness) == 'STALE'
    result = memory.ask_about('ルーター', '未読上限', require_fresh=False)

    assert result['verdict'] == 'UNKNOWN_NO_EVIDENCE'
    assert result['records'] == []


def test_missing_git_commit_is_stale(tmp_path):
    calls = []

    def runner(command, **kwargs):
        calls.append((command, kwargs))
        return SimpleNamespace(returncode=1)

    memory = new_memory(tmp_path)
    record = write_fact(memory, {'kind': 'git_commit', 'repo': str(tmp_path), 'commit': 'missing'})
    result = answer_about(RevalidatingMemory(memory, runner=runner, cache_ttl=0))

    assert result['witness_status'][record['id']] == 'STALE'
    assert record['id'] not in result['records']
    assert calls[0][0][-2:] == ['-e', 'missing^{commit}']


def test_existing_git_commit_is_fresh(tmp_path):
    def runner(command, **kwargs):
        return SimpleNamespace(returncode=0)

    memory = new_memory(tmp_path)
    record = write_fact(memory, {'kind': 'git_commit', 'repo': str(tmp_path), 'commit': 'present'})
    result = answer_about(RevalidatingMemory(memory, runner=runner, cache_ttl=0))

    assert result['witness_status'][record['id']] == 'FRESH'
    assert record['id'] in result['records']


def test_git_runner_is_local_and_does_not_request_network(tmp_path):
    calls = []

    def runner(command, **kwargs):
        calls.append((command, kwargs))
        return SimpleNamespace(returncode=0)

    memory = new_memory(tmp_path)
    write_fact(memory, {'kind': 'git_commit', 'repo': str(tmp_path), 'commit': 'abc123'})
    answer_about(RevalidatingMemory(memory, runner=runner, cache_ttl=0))

    assert len(calls) == 1
    command, kwargs = calls[0]
    assert command[:4] == ['git', '-C', str(tmp_path), 'cat-file']
    assert 'fetch' not in command and 'pull' not in command and 'push' not in command
    assert kwargs['stdin'] is subprocess.DEVNULL


def test_git_runner_failure_is_unverifiable_and_answerable(tmp_path):
    def runner(command, **kwargs):
        raise OSError('git is unavailable')

    memory = new_memory(tmp_path)
    record = write_fact(memory, {'kind': 'git_commit', 'repo': str(tmp_path), 'commit': 'abc123'})
    result = answer_about(RevalidatingMemory(memory, runner=runner, cache_ttl=0))

    assert result['witness_status'][record['id']] == 'UNVERIFIABLE'
    assert record['id'] in result['records']


def test_testimony_is_unverifiable_but_answerable(tmp_path):
    memory = new_memory(tmp_path)
    record = write_fact(memory, {'kind': 'testimony'})

    result = answer_about(RevalidatingMemory(memory, cache_ttl=0))

    assert result['witness_status'][record['id']] == 'UNVERIFIABLE'
    assert record['id'] in result['records']
    assert record['id'] not in result['stale']


@pytest.mark.parametrize('witness, answerable', [
    (None, True), ({'kind': 'unknown'}, False),
])
def test_missing_or_unknown_witness_is_unverifiable_with_safe_answerability(
        tmp_path, witness, answerable):
    path = tmp_path / 'legacy.jsonl'
    record = {'id': 'legacy', 'sentence': 'ルーターの未読上限は8件である。'}
    if witness is not None:
        record['witness'] = witness
    path.write_text(json.dumps({'op': 'write', 'record': record}, ensure_ascii=False) + '\n')
    result = answer_about(RevalidatingMemory(Memory(str(path)), cache_ttl=0))

    assert result['witness_status']['legacy'] == 'UNVERIFIABLE'
    # An unsupported witness kind cannot support an answer; absence keeps legacy behavior.
    assert ('legacy' in result['records']) is answerable


def test_stale_record_is_excluded_even_if_freshness_flag_is_false(tmp_path):
    source = tmp_path / 'source.txt'
    source.write_text('before')
    memory = new_memory(tmp_path)
    record = write_fact(memory, hash_witness(source))
    source.write_text('after')

    result = RevalidatingMemory(memory, cache_ttl=0).ask_about(
        'ルーター', '未読上限', require_fresh=False)

    assert record['id'] not in result['records']
    assert record['id'] in result['stale']


def test_stale_value_does_not_contribute_when_fresh_value_exists(tmp_path):
    old_file = tmp_path / 'old.txt'
    new_file = tmp_path / 'new.txt'
    old_file.write_text('old')
    new_file.write_text('new')
    memory = new_memory(tmp_path)
    stale = write_fact(memory, hash_witness(old_file), value='8件')
    fresh = write_fact(memory, hash_witness(new_file), value='9件')
    old_file.write_text('changed')

    result = answer_about(RevalidatingMemory(memory, cache_ttl=0))

    assert stale['id'] not in result['records']
    assert fresh['id'] in result['records']
    assert stale['id'] in result['stale']


def test_ask_revalidates_records_and_adds_statuses(tmp_path):
    source = tmp_path / 'source.txt'
    source.write_text('source')
    memory = new_memory(tmp_path)
    record = write_fact(memory, hash_witness(source))

    result = RevalidatingMemory(memory, cache_ttl=0).ask('ルーターの未読上限は？')

    assert record['id'] in result['records']
    assert result['witness_status'][record['id']] == 'FRESH'
    assert result['stale'] == []


def test_ask_about_keeps_memory_answer_shape(tmp_path):
    source = tmp_path / 'source.txt'
    source.write_text('source')
    memory = new_memory(tmp_path)
    write_fact(memory, hash_witness(source))

    result = answer_about(RevalidatingMemory(memory, cache_ttl=0))

    assert {'verdict', 'values', 'records', 'witness_status', 'stale'} <= set(result)


def test_empty_memory_returns_unknown_with_empty_statuses(tmp_path):
    result = answer_about(RevalidatingMemory(new_memory(tmp_path), cache_ttl=0))

    assert result['verdict'] == 'UNKNOWN_NO_EVIDENCE'
    assert result['records'] == []
    assert result['witness_status'] == {}
    assert result['stale'] == []


def test_stale_active_records_are_listed_even_when_not_answering_question(tmp_path):
    source = tmp_path / 'source.txt'
    source.write_text('source')
    memory = new_memory(tmp_path)
    record = write_fact(memory, hash_witness(source))
    source.write_text('changed')

    result = RevalidatingMemory(memory, cache_ttl=0).ask('別の質問は？')

    assert record['id'] in result['stale']
    assert result['witness_status'][record['id']] == 'STALE'


def test_superseded_record_is_not_revalidated_or_listed(tmp_path):
    source = tmp_path / 'source.txt'
    source.write_text('source')
    memory = new_memory(tmp_path)
    first = write_fact(memory, hash_witness(source), value='8件')
    second = write_fact(memory, hash_witness(source), value='9件', supersedes=first['id'])

    result = answer_about(RevalidatingMemory(memory, cache_ttl=0))

    assert first['id'] not in result['witness_status']
    assert second['id'] in result['witness_status']


def test_repeated_reads_are_deterministic(tmp_path):
    source = tmp_path / 'source.txt'
    source.write_text('source')
    memory = new_memory(tmp_path)
    write_fact(memory, hash_witness(source))
    wrapper = RevalidatingMemory(memory, cache_ttl=0)

    first = answer_about(wrapper)
    second = answer_about(wrapper)

    assert first == second


def test_concurrent_readers_get_the_same_answer(tmp_path):
    source = tmp_path / 'source.txt'
    source.write_text('source')
    memory = new_memory(tmp_path)
    write_fact(memory, hash_witness(source))
    wrapper = RevalidatingMemory(memory)

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(lambda _: answer_about(wrapper), range(16)))

    assert all(result == results[0] for result in results)


def test_log_is_unchanged_by_read(tmp_path):
    source = tmp_path / 'source.txt'
    source.write_text('source')
    memory = new_memory(tmp_path)
    write_fact(memory, hash_witness(source))
    before = memory.path.read_bytes()

    answer_about(RevalidatingMemory(memory, cache_ttl=0))

    assert memory.path.read_bytes() == before


def test_git_cache_honors_maximum_staleness_bound(tmp_path):
    current = [0.0]
    present = [True]
    calls = []

    def runner(command, **kwargs):
        calls.append(command)
        return SimpleNamespace(returncode=0 if present[0] else 1)

    memory = new_memory(tmp_path)
    record = write_fact(memory, {'kind': 'git_commit', 'repo': str(tmp_path), 'commit': 'abc123'})
    wrapper = RevalidatingMemory(memory, runner=runner, cache_ttl=10,
                                 clock=lambda: current[0])

    assert answer_about(wrapper)['witness_status'][record['id']] == 'FRESH'
    present[0] = False
    current[0] = 9.99
    assert answer_about(wrapper)['witness_status'][record['id']] == 'FRESH'
    current[0] = 10.0
    assert answer_about(wrapper)['witness_status'][record['id']] == 'STALE'
    assert len(calls) == 2


def test_git_cache_reuses_a_check_within_the_bound(tmp_path):
    calls = []

    def runner(command, **kwargs):
        calls.append(command)
        return SimpleNamespace(returncode=0)

    memory = new_memory(tmp_path)
    write_fact(memory, {'kind': 'git_commit', 'repo': str(tmp_path), 'commit': 'abc123'})
    wrapper = RevalidatingMemory(memory, runner=runner, cache_ttl=30)

    answer_about(wrapper)
    answer_about(wrapper)

    assert len(calls) == 1


def test_zero_ttl_rechecks_on_every_read(tmp_path):
    calls = []

    def runner(command, **kwargs):
        calls.append(command)
        return SimpleNamespace(returncode=0)

    memory = new_memory(tmp_path)
    write_fact(memory, {'kind': 'git_commit', 'repo': str(tmp_path), 'commit': 'abc123'})
    wrapper = RevalidatingMemory(memory, runner=runner, cache_ttl=0)

    answer_about(wrapper)
    answer_about(wrapper)

    assert len(calls) == 2


def test_cache_size_is_bounded(tmp_path):
    memory = new_memory(tmp_path)
    for index in range(3):
        source = tmp_path / f'{index}.txt'
        source.write_text(str(index))
        write_fact(memory, {'kind': 'text_in_file', 'path': str(source), 'needle': str(index)},
                   value=f'{index}件')
    wrapper = RevalidatingMemory(memory, cache_ttl=30, cache_size=1)

    wrapper._view()

    assert len(wrapper._cache) == 1


@pytest.mark.parametrize('kwargs', [
    {'cache_ttl': -1},
    {'cache_ttl': float('inf')},
    {'cache_size': -1},
    {'cache_size': 1.5},
])
def test_invalid_cache_bounds_are_rejected(tmp_path, kwargs):
    with pytest.raises(ValueError):
        RevalidatingMemory(new_memory(tmp_path), **kwargs)


def test_zero_cache_size_disables_storage_but_keeps_checks(tmp_path):
    calls = []

    def runner(command, **kwargs):
        calls.append(command)
        return SimpleNamespace(returncode=0)

    memory = new_memory(tmp_path)
    write_fact(memory, {'kind': 'git_commit', 'repo': str(tmp_path), 'commit': 'abc123'})
    wrapper = RevalidatingMemory(memory, runner=runner, cache_size=0)

    answer_about(wrapper)
    answer_about(wrapper)

    assert len(calls) == 2
    assert wrapper._cache == {}
