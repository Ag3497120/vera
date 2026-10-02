"""W1-g B04: one question reads one piece of evidence once, and the verdicts do not move.

Reads are counted by wrapping ``Path.read_bytes`` / ``Path.read_text`` for the fixture
file and ``subprocess.run`` for ``git`` only. The "verdict unchanged" tests pin the cases
that a shape-only shortcut would silently change (a git that cannot start, a needle that
is not in the file, a malformed hash).
"""
import hashlib
import pathlib
import subprocess

import pytest

from verantyx.memory_frame import Memory
from verantyx.memory_revalidate import RevalidatingMemory

SENTENCE = 'routerのunread limitは12である。'
CONTENT = 'router unread limit: 12\n' + SENTENCE + '\nother line\n'


def _record(witness, record_id='r1'):
    return {
        'id': record_id, 'kind': 'FACT',
        'slots': {'subject': 'router', 'attribute': 'unread limit', 'value': '12'},
        'author': 'owner', 'ts': '2026-10-03T00:00:00', 'witness': witness,
        'sentence': SENTENCE, 'supersedes': None, 'normalized': {},
    }


def _memory(*records):
    # the same "appearance of a Memory" memory_revalidate and the attack tests build
    memory = Memory.__new__(Memory)
    memory.records = {record['id']: record for record in records}
    memory.superseded = {}
    return memory


@pytest.fixture
def counter(monkeypatch, tmp_path):
    src = tmp_path / 'src.txt'
    src.write_text(CONTENT, encoding='utf-8')
    reads = []
    git = {'mode': 0}
    orig_rb, orig_rt, orig_run = pathlib.Path.read_bytes, pathlib.Path.read_text, subprocess.run

    def rb(self, *a, **k):
        if self == src: reads.append('read_bytes')
        return orig_rb(self, *a, **k)

    def rt(self, *a, **k):
        if self == src: reads.append('read_text')
        return orig_rt(self, *a, **k)

    class _Done:
        def __init__(self, rc): self.returncode = rc

    def run(args, *a, **k):
        if list(args[:1]) == ['git']:
            reads.append('git')
            if git['mode'] == 'oserror': raise OSError('git cannot start')
            return _Done(git['mode'])
        return orig_run(args, *a, **k)

    monkeypatch.setattr(pathlib.Path, 'read_bytes', rb)
    monkeypatch.setattr(pathlib.Path, 'read_text', rt)
    monkeypatch.setattr(subprocess, 'run', run)
    return type('C', (), {'src': src, 'reads': reads, 'git': git})


def _sha(text): return hashlib.sha256(text.encode()).hexdigest()


def _ask_memory(record, **kw):
    return Memory.ask_about(_memory(record), 'router', 'unread limit', **kw)


def _ask_revalidating(record):
    return RevalidatingMemory(_memory(record), cache_size=0, cache_ttl=0).ask_about('router', 'unread limit')


# ---------------------------------------------------------------- reads once
def test_file_sha256_is_read_once_by_memory_ask(counter):
    w = {'kind': 'file_sha256', 'path': str(counter.src), 'sha256': _sha(CONTENT)}
    answer = _ask_memory(_record(w))
    assert answer['verdict'] == 'ANSWER' and answer['values'] == ['12']
    assert counter.reads == ['read_bytes']


def test_file_sha256_is_read_once_by_revalidating_memory(counter):
    w = {'kind': 'file_sha256', 'path': str(counter.src), 'sha256': _sha(CONTENT)}
    answer = _ask_revalidating(_record(w))
    assert answer['verdict'] == 'ANSWER' and answer['values'] == ['12']
    assert counter.reads == ['read_bytes']


def test_file_hash_is_read_once_by_memory_ask(counter):
    w = {'kind': 'file_hash', 'path': str(counter.src), 'sha256': _sha(CONTENT)}
    answer = _ask_memory(_record(w))
    assert answer['verdict'] == 'ANSWER'
    assert counter.reads == ['read_bytes']


def test_text_in_file_is_read_once_by_memory_ask(counter):
    w = {'kind': 'text_in_file', 'path': str(counter.src), 'needle': SENTENCE}
    answer = _ask_memory(_record(w))
    assert answer['verdict'] == 'ANSWER' and answer['values'] == ['12']
    assert counter.reads == ['read_text']


def test_git_commit_is_launched_once_by_memory_ask(counter):
    w = {'kind': 'git_commit', 'repo': 'repo', 'commit': 'abc'}
    answer = _ask_memory(_record(w))
    assert answer['verdict'] == 'ANSWER'
    assert counter.reads == ['git']


def test_command_exit_has_nothing_to_read(counter):
    w = {'kind': 'command_exit', 'command': 'true', 'exit_code': 0}
    answer = _ask_memory(_record(w))
    assert answer['verdict'] == 'ANSWER'
    assert counter.reads == []


def test_fresh_false_still_reads_once(counter):
    w = {'kind': 'text_in_file', 'path': str(counter.src), 'needle': SENTENCE}
    answer = _ask_memory(_record(w), require_fresh=False)
    assert answer['verdict'] == 'ANSWER'
    assert counter.reads == ['read_text']


# ------------------------------------------------- verdicts that must not move
def test_stale_file_hash_is_not_an_answer_when_fresh_is_required(counter):
    w = {'kind': 'file_sha256', 'path': str(counter.src), 'sha256': _sha('different')}
    answer = _ask_memory(_record(w))
    assert answer['verdict'] != 'ANSWER' and answer['values'] == []
    assert counter.reads == ['read_bytes']      # one read decided STALE, nothing else was read


def test_malformed_hash_is_not_an_answer_even_without_the_freshness_check(counter):
    w = {'kind': 'file_sha256', 'path': str(counter.src), 'sha256': _sha(CONTENT)[:63]}
    answer = _ask_memory(_record(w), require_fresh=False)
    assert answer['verdict'] != 'ANSWER' and answer['values'] == []


def test_needle_absent_from_the_file_is_not_an_answer_even_without_the_freshness_check(counter):
    w = {'kind': 'text_in_file', 'path': str(counter.src), 'needle': 'nowhere in the file'}
    answer = _ask_memory(_record(w), require_fresh=False)
    assert answer['verdict'] != 'ANSWER'


def test_needle_present_but_not_the_claim_is_not_an_answer(counter):
    w = {'kind': 'text_in_file', 'path': str(counter.src), 'needle': 'other line'}
    answer = _ask_memory(_record(w))
    assert answer['verdict'] != 'ANSWER'
    assert counter.reads == ['read_text']


def test_git_that_cannot_start_does_not_become_support(counter):
    counter.git['mode'] = 'oserror'
    w = {'kind': 'git_commit', 'repo': 'repo', 'commit': 'abc'}
    for require_fresh in (True, False):
        counter.reads.clear()
        answer = _ask_memory(_record(w), require_fresh=require_fresh)
        assert answer['verdict'] != 'ANSWER' and answer['values'] == []
        assert counter.reads == ['git']


def test_unknown_commit_is_stale_and_not_an_answer(counter):
    counter.git['mode'] = 1
    w = {'kind': 'git_commit', 'repo': 'repo', 'commit': 'abc'}
    answer = _ask_memory(_record(w))
    assert answer['verdict'] != 'ANSWER'


# ---------------------------------------- the same rule, written once
def test_file_hash_shape_rule_is_shared_by_check_witness_and_support():
    import verantyx.memory_frame as mf
    good = {'kind': 'file_sha256', 'path': 'nowhere/x.txt', 'sha256': 'a' * 64}
    bad = [{'kind': 'file_sha256', 'path': 'x', 'sha256': 'a' * 63},
           {'kind': 'file_hash', 'path': '', 'sha256': 'a' * 64},
           {'kind': 'file_hash', 'path': 'x', 'sha256': 5},
           {'kind': 'file_hash', 'path': 7, 'sha256': 'a' * 64},
           {'kind': 'file_hash', 'path': 'x', 'sha256': 'g' * 64}]
    assert mf.check_witness(good) == 'STALE'            # well-formed, file absent: not UNVERIFIABLE
    assert mf.Memory._witness_supports(_record(good)) is True
    for witness in bad:
        assert mf.check_witness(witness) == 'UNVERIFIABLE'
        assert mf.Memory._witness_supports(_record(witness)) is False


def test_witness_supports_without_status_behaves_as_before(counter):
    w = {'kind': 'text_in_file', 'path': str(counter.src), 'needle': SENTENCE}
    assert Memory._witness_supports(_record(w)) is True
    assert Memory._witness_supports(_record(w), status='FRESH') is True
    assert Memory._witness_supports(_record({'kind': 'testimony'})) is True


def test_active_with_fresh_is_the_non_stale_set(counter):
    good = {'kind': 'file_sha256', 'path': str(counter.src), 'sha256': _sha(CONTENT)}
    stale = {'kind': 'file_sha256', 'path': str(counter.src), 'sha256': _sha('x')}
    m = _memory(_record(good, 'g'), _record(stale, 's'), _record({'kind': 'testimony'}, 't'))
    assert sorted(r['id'] for r in m.active(True)) == ['g', 't']
    assert sorted(r['id'] for r in m.active(False)) == ['g', 's', 't']
