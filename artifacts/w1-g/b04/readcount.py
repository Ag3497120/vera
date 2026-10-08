"""B04 measurement: reads per question and verdict, over kind x state x path.

Same script before and after the fix. Counts Path.read_bytes / Path.read_text on the
fixture paths and `git` launches only. Prints one line per combination.
"""
import hashlib, pathlib, subprocess

from verantyx.memory_frame import Memory
from verantyx.memory_revalidate import RevalidatingMemory

SENT = 'routerのunread limitは12である。'
CONTENT = 'router unread limit: 12\n' + SENT + '\nother line\n'
OTHER_NEEDLE = 'other line'
reads = []
_orig_rb, _orig_rt, _orig_run = pathlib.Path.read_bytes, pathlib.Path.read_text, subprocess.run
GIT_MODE = {'rc': 0}


def _fixture(path):
    name = str(path)
    return name in ('src.txt', 'missing.txt')


def _rb(self):
    if not _fixture(self): return _orig_rb(self)
    reads.append(('rb', str(self)))
    if str(self) == 'missing.txt': raise FileNotFoundError(str(self))
    return CONTENT.encode()


def _rt(self, *a, **k):
    if not _fixture(self): return _orig_rt(self, *a, **k)
    reads.append(('rt', str(self)))
    if str(self) == 'missing.txt': raise FileNotFoundError(str(self))
    return CONTENT


class _R: returncode = 0


def _run(args, *a, **k):
    if args[:1] == ['git']:
        reads.append(('git', args[2]))
        if GIT_MODE['rc'] == 'oserror': raise OSError('no git')
        r = _R(); r.returncode = GIT_MODE['rc']; return r
    return _orig_run(args, *a, **k)


pathlib.Path.read_bytes, pathlib.Path.read_text, subprocess.run = _rb, _rt, _run


def rec(w):
    return {'id': 'r1', 'kind': 'FACT', 'slots': {'subject': 'router', 'attribute': 'unread limit', 'value': '12'},
            'author': 'o', 'ts': 't', 'witness': w, 'sentence': SENT, 'supersedes': None, 'normalized': {}}


def mem(r):
    m = Memory.__new__(Memory); m.records = {'r1': r}; m.superseded = {}; return m


good_sha = hashlib.sha256(CONTENT.encode()).hexdigest()
bad_sha = hashlib.sha256(b'different').hexdigest()
cases = []   # (kind, state, witness, git_rc)
for kind in ('file_sha256', 'file_hash'):
    cases += [(kind, 'FRESH', {'kind': kind, 'path': 'src.txt', 'sha256': good_sha}, 0),
              (kind, 'STALE_CONTENT', {'kind': kind, 'path': 'src.txt', 'sha256': bad_sha}, 0),
              (kind, 'FILE_MISSING', {'kind': kind, 'path': 'missing.txt', 'sha256': good_sha}, 0),
              (kind, 'BAD_SHAPE_63', {'kind': kind, 'path': 'src.txt', 'sha256': good_sha[:63]}, 0)]
cases += [('text_in_file', 'FRESH', {'kind': 'text_in_file', 'path': 'src.txt', 'needle': SENT}, 0),
          ('text_in_file', 'NEEDLE_ABSENT', {'kind': 'text_in_file', 'path': 'src.txt', 'needle': 'nowhere'}, 0),
          ('text_in_file', 'FILE_MISSING', {'kind': 'text_in_file', 'path': 'missing.txt', 'needle': SENT}, 0),
          ('text_in_file', 'BAD_SHAPE_BLANK_NEEDLE', {'kind': 'text_in_file', 'path': 'src.txt', 'needle': ' '}, 0),
          ('text_in_file', 'NEEDLE_NOT_THE_CLAIM', {'kind': 'text_in_file', 'path': 'src.txt', 'needle': OTHER_NEEDLE}, 0),
          ('git_commit', 'FRESH', {'kind': 'git_commit', 'repo': 'repo', 'commit': 'abc'}, 0),
          ('git_commit', 'STALE_RC1', {'kind': 'git_commit', 'repo': 'repo', 'commit': 'abc'}, 1),
          ('git_commit', 'UNVERIFIABLE_OSERROR', {'kind': 'git_commit', 'repo': 'repo', 'commit': 'abc'}, 'oserror'),
          ('git_commit', 'BAD_SHAPE_EMPTY_COMMIT', {'kind': 'git_commit', 'repo': 'repo', 'commit': ''}, 0),
          ('command_exit', 'FRESH', {'kind': 'command_exit', 'command': 'true', 'exit_code': 0}, 0),
          ('command_exit', 'STALE_EXIT1', {'kind': 'command_exit', 'command': 'true', 'exit_code': 1}, 0),
          ('command_exit', 'BAD_SHAPE_NO_EXIT', {'kind': 'command_exit', 'command': 'true'}, 0)]
paths = [('Memory.ask fresh=True', lambda m: Memory.ask_about(m, 'router', 'unread limit')),
         ('Memory.ask fresh=False', lambda m: Memory.ask_about(m, 'router', 'unread limit', require_fresh=False)),
         ('Revalidating.ask', lambda m: RevalidatingMemory(m, cache_size=0, cache_ttl=0).ask_about('router', 'unread limit'))]
for kind, state, w, rc in cases:
    GIT_MODE['rc'] = rc
    for label, fn in paths:
        reads.clear()
        try:
            a = fn(mem(rec(w))); verdict = a['verdict']; recs = len(a.get('records', []))
        except Exception as exc:
            verdict, recs = f'EXC:{type(exc).__name__}', -1
        print(f'{kind:12} {state:24} {label:22} verdict={verdict:20} records={recs} reads={len(reads)}')
