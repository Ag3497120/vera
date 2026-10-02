from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

import pytest

from verantyx.memory_revalidate import RevalidatingMemory


def reference_check(witness, runner):
    """Small contract-based oracle for the supported local witness kinds."""
    if not witness or not isinstance(witness, dict):
        return 'UNVERIFIABLE'

    kind = witness.get('kind')
    if kind == 'testimony':
        return 'UNVERIFIABLE'
    if kind == 'file_sha256':
        try:
            data = Path(witness['path']).expanduser().read_bytes()
        except (OSError, KeyError, TypeError, ValueError):
            return 'STALE'
        return 'FRESH' if hashlib.sha256(data).hexdigest() == witness.get('sha256') else 'STALE'
    if kind == 'text_in_file':
        try:
            text = Path(witness['path']).expanduser().read_text()
            needle = witness['needle']
        except (OSError, KeyError, TypeError, ValueError):
            return 'STALE'
        return 'FRESH' if needle in text else 'STALE'
    if kind == 'git_commit':
        try:
            result = runner(
                ['git', '-C', str(Path(witness['repo']).expanduser()), 'cat-file', '-e',
                 str(witness['commit']) + '^{commit}'],
                capture_output=True, text=True, timeout=5, stdin=subprocess.DEVNULL)
        except Exception:
            return 'UNVERIFIABLE'
        return 'FRESH' if result.returncode == 0 else 'STALE'
    return 'UNVERIFIABLE'


class ReferenceCache:
    """Deliberately simple TTL/LRU model, separate from the implementation."""

    def __init__(self, ttl, size, clock, runner):
        self.ttl = ttl
        self.size = size
        self.clock = clock
        self.runner = runner
        self.values = {}
        self.order = []

    def status(self, witness):
        key = json.dumps(witness, ensure_ascii=False, sort_keys=True, default=str)
        now = self.clock()
        if key in self.values:
            checked_at, status = self.values[key]
            if self.ttl > 0 and now - checked_at < self.ttl:
                self.order.remove(key)
                self.order.append(key)
                return status
            self.values.pop(key)
            self.order.remove(key)

        status = reference_check(witness, self.runner)
        if self.size and self.ttl:
            self.values[key] = (self.clock(), status)
            self.order.append(key)
            while len(self.order) > self.size:
                oldest = self.order.pop(0)
                self.values.pop(oldest)
        return status


class MutableClock:
    def __init__(self, value=0.0):
        self.value = value

    def __call__(self):
        return self.value


class GitRunner:
    def __init__(self, returncode=0, error=None):
        self.returncode = returncode
        self.error = error
        self.calls = []

    def __call__(self, args, **kwargs):
        self.calls.append((args, kwargs))
        if self.error:
            raise self.error
        return type('Completed', (), {'returncode': self.returncode})()


def subject(*, runner=None, cache_ttl=1.0, cache_size=256, clock=None):
    return RevalidatingMemory(
        None, runner=runner, cache_ttl=cache_ttl, cache_size=cache_size,
        clock=clock or MutableClock())


@pytest.mark.parametrize('matches', [True, False])
def test_file_sha256_matches_reference(tmp_path, matches):
    path = tmp_path / 'payload.bin'
    data = b'known bytes'
    path.write_bytes(data)
    expected_digest = hashlib.sha256(data).hexdigest()
    witness = {'kind': 'file_sha256', 'path': str(path),
               'sha256': expected_digest if matches else '0' * 64}

    actual = subject()._check(witness)

    assert actual == reference_check(witness, GitRunner())
    assert actual == ('FRESH' if matches else 'STALE')


@pytest.mark.parametrize(('needle', 'expected'), [('needle', 'FRESH'), ('absent', 'STALE')])
def test_text_in_file_matches_reference(tmp_path, needle, expected):
    path = tmp_path / 'note.txt'
    path.write_text('alpha needle omega')
    witness = {'kind': 'text_in_file', 'path': str(path), 'needle': needle}

    actual = subject()._check(witness)

    assert actual == reference_check(witness, GitRunner()) == expected


@pytest.mark.parametrize('witness', [
    None,
    '',
    [],
    {},
    {'kind': 'testimony', 'text': 'a person said so'},
    {'kind': 'future_kind'},
])
def test_unsupported_or_testimony_witness_is_unverifiable(witness):
    assert subject()._check(witness) == reference_check(witness, GitRunner()) == 'UNVERIFIABLE'


@pytest.mark.parametrize('witness', [
    {'kind': 'file_sha256'},
    {'kind': 'text_in_file', 'path': '/absent/file'},
    {'kind': 'file_sha256', 'path': '/absent/file', 'sha256': 'x'},
])
def test_missing_or_unavailable_local_witness_is_stale(witness):
    assert subject()._check(witness) == reference_check(witness, GitRunner()) == 'STALE'


@pytest.mark.parametrize(('returncode', 'expected'), [(0, 'FRESH'), (1, 'STALE')])
def test_git_commit_uses_runner_result(returncode, expected):
    runner = GitRunner(returncode=returncode)
    witness = {'kind': 'git_commit', 'repo': '/local/repo', 'commit': 'abc123'}

    actual = subject(runner=runner)._check(witness)

    assert actual == reference_check(witness, runner) == expected
    args, kwargs = runner.calls[0]
    assert args == ['git', '-C', '/local/repo', 'cat-file', '-e', 'abc123^{commit}']
    assert kwargs == {
        'capture_output': True, 'text': True, 'timeout': 5,
        'stdin': subprocess.DEVNULL,
    }


@pytest.mark.parametrize('error', [subprocess.TimeoutExpired('git', 5), RuntimeError('runner fault')])
def test_git_runner_error_is_unverifiable(error):
    witness = {'kind': 'git_commit', 'repo': '/local/repo', 'commit': 'abc123'}
    runner = GitRunner(error=error)

    assert subject(runner=runner)._check(witness) == reference_check(witness, runner) == 'UNVERIFIABLE'


def test_generated_file_witness_matrix_matches_reference(tmp_path):
    verifier = subject()
    witnesses = []
    for index in range(8):
        path = tmp_path / f'generated-{index}.txt'
        content = f'case {index} token-{index % 3}'
        path.write_text(content)
        witnesses.extend([
            {'kind': 'file_sha256', 'path': str(path),
             'sha256': hashlib.sha256(content.encode()).hexdigest()},
            {'kind': 'file_sha256', 'path': str(path), 'sha256': 'bad-digest'},
            {'kind': 'text_in_file', 'path': str(path), 'needle': f'token-{index % 3}'},
            {'kind': 'text_in_file', 'path': str(path), 'needle': 'never-present'},
        ])

    for witness in witnesses:
        assert verifier._check(witness) == reference_check(witness, GitRunner()), witness


def test_cache_ttl_rechecks_exactly_at_expiry(tmp_path):
    path = tmp_path / 'changing.txt'
    path.write_text('old')
    witness = {'kind': 'text_in_file', 'path': str(path), 'needle': 'old'}
    clock = MutableClock(10.0)
    runner = GitRunner()
    actual = subject(runner=runner, cache_ttl=1.0, clock=clock)
    reference = ReferenceCache(1.0, 256, clock, runner)

    results = [actual._status(witness)]
    expected = [reference.status(witness)]
    path.write_text('new')
    clock.value = 10.5
    results.append(actual._status(witness))
    expected.append(reference.status(witness))
    clock.value = 11.0
    results.append(actual._status(witness))
    expected.append(reference.status(witness))

    assert results == expected == ['FRESH', 'FRESH', 'STALE']


@pytest.mark.parametrize(('ttl', 'size'), [(0.0, 8), (1.0, 0)])
def test_zero_ttl_or_size_disables_cache(tmp_path, ttl, size):
    path = tmp_path / 'no-cache.txt'
    path.write_text('old')
    witness = {'kind': 'text_in_file', 'path': str(path), 'needle': 'old'}
    runner = GitRunner()
    clock = MutableClock()
    actual = subject(runner=runner, cache_ttl=ttl, cache_size=size, clock=clock)
    reference = ReferenceCache(ttl, size, clock, runner)

    first = actual._status(witness), reference.status(witness)
    path.write_text('new')
    second = actual._status(witness), reference.status(witness)

    assert first == ('FRESH', 'FRESH')
    assert second == ('STALE', 'STALE')


def test_cache_size_is_lru_bounded(tmp_path):
    path_a = tmp_path / 'a.txt'
    path_b = tmp_path / 'b.txt'
    path_a.write_text('a')
    path_b.write_text('b')
    witness_a = {'kind': 'text_in_file', 'path': str(path_a), 'needle': 'a'}
    witness_b = {'kind': 'text_in_file', 'path': str(path_b), 'needle': 'b'}
    runner = GitRunner()
    clock = MutableClock()
    actual = subject(runner=runner, cache_size=1, clock=clock)
    reference = ReferenceCache(1.0, 1, clock, runner)

    results = []
    expected = []
    for witness in (witness_a, witness_b):
        results.append(actual._status(witness))
        expected.append(reference.status(witness))
    path_a.write_text('zzz')
    results.append(actual._status(witness_a))
    expected.append(reference.status(witness_a))

    assert results == expected == ['FRESH', 'FRESH', 'STALE']


def test_cache_key_ignores_mapping_insertion_order(tmp_path):
    path = tmp_path / 'ordered.txt'
    path.write_text('before')
    first = {'kind': 'text_in_file', 'path': str(path), 'needle': 'before'}
    reordered = {'needle': 'before', 'path': str(path), 'kind': 'text_in_file'}
    runner = GitRunner()
    clock = MutableClock()
    actual = subject(runner=runner, clock=clock)
    reference = ReferenceCache(1.0, 256, clock, runner)

    initial = actual._status(first), reference.status(first)
    path.write_text('after')
    reused = actual._status(reordered), reference.status(reordered)

    assert initial == ('FRESH', 'FRESH')
    assert reused == ('FRESH', 'FRESH')


class ActiveRecords:
    def __init__(self, records):
        self.records = records

    def active(self, *, require_fresh):
        assert require_fresh is False
        return list(self.records)


def test_view_omits_stale_and_keeps_unverifiable_records(tmp_path):
    path = tmp_path / 'source.txt'
    path.write_text('current')
    records = [
        {'id': 'fresh', 'witness': {'kind': 'text_in_file', 'path': str(path), 'needle': 'current'}},
        {'id': 'stale', 'witness': {'kind': 'text_in_file', 'path': str(path), 'needle': 'old'}},
        {'id': 'unverifiable', 'witness': {'kind': 'testimony'}},
    ]
    original_records = list(records)
    wrapper = RevalidatingMemory(ActiveRecords(records), cache_ttl=0)

    view, statuses = wrapper._view()

    assert statuses == {
        'fresh': 'FRESH', 'stale': 'STALE', 'unverifiable': 'UNVERIFIABLE',
    }
    assert set(view.records) == {'fresh', 'unverifiable'}
    assert records == original_records
