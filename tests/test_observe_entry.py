"""W3-c: the entry `python -m verantyx.cli observe` (a subprocess each time): arguments, exit codes, the ledger file, hash seeds, replay."""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from verantyx import observe as O
from verantyx import salience as SAL

TREE = Path(__file__).resolve().parent.parent
GIVE = '太郎は花子に本をあげた。'
PLACEMENT = {
    'lemmas': {'太郎': {'state': 'DECIDED', 'origin': 'direct', 'types': ['PERSON']},
               '花子': {'state': 'DECIDED', 'origin': 'direct', 'types': ['PERSON']},
               '次郎': {'state': 'DECIDED', 'origin': 'direct', 'types': ['PERSON']},
               '机': {'state': 'DECIDED', 'origin': 'direct', 'types': ['ARTIFACT']}},
    'neighbors': {'太郎': ['机', '次郎', '花子', '太郎']},
}


def run(*args, seed='0', cwd=TREE):
    env = {'HOME': os.environ.get('HOME', ''), 'PATH': '/usr/bin:/bin', 'PYTHONDONTWRITEBYTECODE': '1', 'PYTHONPATH': str(TREE), 'PYTHONHASHSEED': seed}
    return subprocess.run([sys.executable, '-m', 'verantyx.cli', 'observe', *args], capture_output=True, text=True, env=env, cwd=str(cwd), timeout=180)


@pytest.fixture()
def files(tmp_path):
    (tmp_path / 'placement.json').write_text(json.dumps(PLACEMENT, ensure_ascii=False), encoding='utf-8')
    (tmp_path / 'structure.jsonl').write_text(json.dumps({'id': 's1', 'text': GIVE}, ensure_ascii=False) + '\n' + json.dumps({'id': 's2', 'text': '次郎は花子に本をあげた。'}, ensure_ascii=False) + '\n', encoding='utf-8')
    return tmp_path


def test_help_lists_the_command():
    r = subprocess.run([sys.executable, '-m', 'verantyx.cli', '--help'], capture_output=True, text=True, cwd=str(TREE),
                       env={'HOME': os.environ.get('HOME', ''), 'PATH': '/usr/bin:/bin', 'PYTHONPATH': str(TREE), 'PYTHONDONTWRITEBYTECODE': '1'})
    assert r.returncode == 0 and 'observe' in r.stdout


def test_default_entry_returns_one_json_line_and_exit_0():
    r = run('--anchor-text', GIVE, '--no-index')
    assert r.returncode == 0 and r.stderr == '' and r.stdout.count('\n') == 1
    d = json.loads(r.stdout)
    assert d['schema'] == 'verantyx.observe/1' and d['focus']['kind'] == 'FOCUS' and d['anchor']['coords'][0]['moves'] == []
    assert set(d) == {'schema', 'viewpoint', 'structure', 'anchor', 'ranks', 'focus', 'realization', 'abstain', 'counts', 'salience_trace'}


def test_default_placement_licenses_no_face_swap():
    d = json.loads(run('--anchor-text', GIVE, '--direction', 'FACE_SWAP:agent', '--no-index').stdout)
    assert d['focus'] == {'kind': 'NO_MOVE_LICENSED'}
    assert d['abstain'] == {'type': 'NO_MOVE_LICENSED', 'reasons': {'FACE_SWAP:NO_PLACEMENT': 1}}


def test_no_index_marks_unknown_no_index_and_the_default_index_root_does_too(files):
    d = json.loads(run('--anchor-text', GIVE, '--direction', 'FACE_SWAP:agent', '--placement', str(files / 'placement.json'), '--no-index').stdout)
    assert d['ranks'][0]['elements'][0]['occupied'] == 'UNKNOWN_NO_INDEX' and d['structure']['index'] is None
    d2 = json.loads(run('--anchor-text', GIVE, '--direction', 'FACE_SWAP:agent', '--placement', str(files / 'placement.json'), '--index', str(files / 'absent')).stdout)
    assert d2['ranks'][0]['elements'][0]['occupied'] == 'UNKNOWN_NO_INDEX' and d2['structure']['index']['root_name'] == 'absent'


def test_face_swap_through_the_entry_with_a_placement_file(files):
    d = json.loads(run('--anchor-text', GIVE, '--direction', 'FACE_SWAP:agent', '--placement', str(files / 'placement.json'),
                       '--structure', str(files / 'structure.jsonl'), '--no-index').stdout)
    els = [e for g in d['ranks'] for e in g['elements']]
    assert d['focus']['kind'] == 'TIE' and len(els) == 2    # 花子 and 次郎 agree; 机 disagrees; 太郎 is the original; the field is flat -> TIE
    assert d['structure']['placement'].startswith('file:') and d['structure']['by_reading_source'] == {'semantic_read': 2, 'injected': 0}
    by = {e['cross']['arms']['agent']['fillers'][0]['surface']: e for e in els}
    assert by['次郎']['claim'] == 'OBSERVED_OCCUPIED' and by['次郎']['occupancy'][0]['witness'] == [{'reading': 's2', 'cross_index': 0}]
    assert by['花子']['claim'] == 'UNKNOWN_OCCUPANCY'


@pytest.mark.parametrize('args', [
    [],
    ['--anchor-text', 'x', '--anchor-record', 'y'],
    ['--anchor-text', 'x', '--direction', 'FACE_SWAP'],
    ['--anchor-text', 'x', '--direction', 'FACE_SWAP:agent,'],
    ['--anchor-text', 'x', '--direction', 'EDGE:because'],
    ['--anchor-text', 'x', '--direction', 'FACE_SWAP:agent', '--range', '2'],
    ['--anchor-text', 'x', '--direction', 'FACE_SWAP:agent', '--range', '-1'],
    ['--anchor-text', 'x', '--range', '1'],
    ['--anchor-text', 'x', '--no-index', '--index', '/tmp/none'],
    ['--anchor-text', 'x', '--index-family', 'nope'],
    ['--anchor-text', 'x', '--lang', 'fr'],
    ['--anchor-text', 'x', '--structure', '/nonexistent/s.jsonl'],
    ['--anchor-text', 'x', '--placement', '/nonexistent/p.json'],
])
def test_bad_arguments_exit_2_with_a_typed_error_on_stderr(args):
    r = run(*args)
    assert r.returncode == 2 and r.stdout == ''
    assert json.loads(r.stderr.strip().splitlines()[-1])['error']['type'] == 'BAD_ARGUMENTS'


def test_a_broken_ledger_exits_3_and_is_not_touched(tmp_path):
    led = tmp_path / 'l.jsonl'
    led.write_bytes(b'{"seq":2,"ts":"t","kind":"utterance","payload":{}}\n')
    before = led.read_bytes()
    r = run('--anchor-text', GIVE, '--no-index', '--ledger', str(led))
    assert r.returncode == 3 and r.stdout == '' and json.loads(r.stderr)['error']['type'] == 'LEDGER_INVALID'
    assert led.read_bytes() == before


def test_ledger_gets_exactly_two_lines_per_turn_and_a_record_anchor_one(files):
    led = files / 'l.jsonl'
    assert run('--anchor-text', GIVE, '--no-index', '--ledger', str(led)).returncode == 0
    lines = led.read_text(encoding='utf-8').splitlines()
    assert [json.loads(x)['kind'] for x in lines] == ['utterance', 'observation']
    assert run('--anchor-text', GIVE, '--no-index', '--ledger', str(led)).returncode == 0
    assert len(led.read_text(encoding='utf-8').splitlines()) == 4
    assert run('--anchor-record', 's1', '--structure', str(files / 'structure.jsonl'), '--no-index', '--ledger', str(led)).returncode == 0
    kinds = [json.loads(x)['kind'] for x in led.read_text(encoding='utf-8').splitlines()]
    assert kinds == ['utterance', 'observation', 'utterance', 'observation', 'observation']
    # appended lines only: the first lines are byte-identical after later turns
    assert led.read_text(encoding='utf-8').splitlines()[:2] == lines


def test_hashseed_does_not_change_the_bytes(files):
    args = ['--anchor-text', GIVE, '--direction', 'FACE_SWAP:agent', '--placement', str(files / 'placement.json'),
            '--structure', str(files / 'structure.jsonl'), '--no-index']
    a, b, c = run(*args, seed='0'), run(*args, seed='4242'), run(*args, seed='random')
    assert a.returncode == b.returncode == c.returncode == 0
    assert a.stdout == b.stdout == c.stdout and json.loads(a.stdout)['ranks']


def test_hashseed_with_a_tie_and_a_ledger(files):
    p = dict(PLACEMENT, neighbors={'太郎': ['次郎', '花子', '太郎']})
    (files / 'p2.json').write_text(json.dumps(p, ensure_ascii=False), encoding='utf-8')
    outs = []
    for seed in ('0', '4242'):
        led = files / ('l%s.jsonl' % seed)
        led.write_bytes(b'')
        args = ['--anchor-text', GIVE, '--direction', 'FACE_SWAP:agent', '--placement', str(files / 'p2.json'), '--no-index', '--ledger', str(led)]
        outs.append((run(*args, seed=seed).stdout, run(*args, seed=seed).stdout))
    assert outs[0] == outs[1] and json.loads(outs[0][0])['focus']['kind'] == 'TIE'


def test_replay_of_the_turns_recorded_by_the_entry(files):
    led = files / 'l.jsonl'
    args = ['--anchor-text', GIVE, '--direction', 'FACE_SWAP:agent', '--placement', str(files / 'placement.json'),
            '--structure', str(files / 'structure.jsonl'), '--no-index', '--ledger', str(led)]
    # a decision in the ledger first, so that the first turn has a focus and the second moves on
    structure = O.Structure.from_jsonl(files / 'structure.jsonl', O.FilePlacement.from_path(files / 'placement.json'),
                                       O.FilePlacement.from_path(files / 'placement.json'))
    vp = O.Viewpoint(O.AnchorText('seed', GIVE), (O.FaceSwap('agent'),))
    key = [e.cell.key for g in O.observe(vp, structure).ranks for e in g if e.cell.cross.arms['agent'].fillers[0].surface == '次郎'][0]
    seed = SAL.MemoryLedger()
    O.record_decision(seed, key)
    SAL.append_jsonl(led, seed.events())
    outs = [json.loads(run(*args).stdout) for _ in range(3)]
    assert outs[0]['focus'] == {'kind': 'FOCUS', 'cell_key': key}
    assert outs[1]['focus']['kind'] in ('FOCUS', 'TIE') and outs[1]['focus'] != outs[0]['focus']
    loaded = SAL.load_jsonl(led)
    evs = list(loaded.events())
    obs_events = [e for e in evs if e['kind'] == 'observation']
    assert len(obs_events) == 3
    for ev in obs_events:
        assert O.replay(evs, ev, structure) is True
