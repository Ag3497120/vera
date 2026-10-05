"""W16-t2 (3): the placement has one name in the environment, VERA_PLACEMENT. VERA_COARSE_PLACEMENT is read as a compatible alias; both set to different places is the typed error
PLACEMENT_ENV_CONFLICT (never a pick). The placement is a fake here (`event_cross.default_lookup` answers it only when VERA_PLACEMENT names the sentinel path); no test is skipped."""
import contextlib
import io
import json
import os
from pathlib import Path

import pytest

from verantyx import cli
from verantyx import coarse_place as cp
from verantyx import event_cross as EC
from verantyx import observe as O

SENTINEL = '/sentinel/w16t2-placement'
DOC = '太郎は花子に本を渡した。花子は東京の大学で物理学を学んでいる。その本は昨年出版された。\n'
PLACE = {'太郎': 'PERSON', '花子': 'PERSON', '本': 'ARTIFACT', '東京': 'PLACE', '大学': 'PLACE', '物理学': 'INFO_LANGUAGE', '昨年': 'TIME'}
QUESTION = '太郎は花子に何を渡した？'          # answered only by the later stage (the question cross), which needs a typed hole = a placement


@pytest.fixture
def world(tmp_path, monkeypatch):
    for name in ('VERA_PLACEMENT', 'VERA_COARSE_PLACEMENT', 'VERA_SOVEREIGN_ROOT', 'VERA_SOVEREIGN_STORE'):
        monkeypatch.delenv(name, raising=False)
    path = tmp_path / 'pl.json'
    path.write_text(json.dumps({'lemmas': {w: {'state': 'DECIDED', 'origin': 'direct', 'types': [t]} for w, t in PLACE.items()}, 'neighbors': {}}, ensure_ascii=False), encoding='utf-8')
    fp = O.FilePlacement.from_path(str(path))

    def lookup(placement=None):
        named = placement if placement is not None else os.environ.get('VERA_PLACEMENT')
        return fp if named == SENTINEL else EC.StubLookup()
    monkeypatch.setattr(EC, 'default_lookup', lookup)
    doc = tmp_path / 'd.txt'
    doc.write_text(DOC, encoding='utf-8')
    return {'doc': str(doc), 'store': str(tmp_path / 'st.json'), 'tmp': tmp_path}


def run_ask(world, capsys, question=QUESTION):
    capsys.readouterr()
    rc = cli.main(['--store', world['store'], 'ask', '--mode', 'round5', '--document', world['doc'], '--', question])
    return rc, json.loads(capsys.readouterr().out)


def key(out):
    return json.dumps({k: out.get(k) for k in ('verdict', 'values', 'evidence')}, ensure_ascii=False, sort_keys=True)


# ---- placement_from_env ---------------------------------------------------------------------------------------------------------------------

def test_one_name_only(monkeypatch):
    monkeypatch.delenv('VERA_PLACEMENT', raising=False), monkeypatch.delenv('VERA_COARSE_PLACEMENT', raising=False)
    assert cp.placement_from_env() is None
    monkeypatch.setenv('VERA_PLACEMENT', '/a/b')
    assert cp.placement_from_env() == '/a/b'
    monkeypatch.delenv('VERA_PLACEMENT')
    monkeypatch.setenv('VERA_COARSE_PLACEMENT', '/c/d')
    assert cp.placement_from_env() == '/c/d'                      # the compatible name alone is read


def test_the_same_place_in_both_is_not_a_conflict(monkeypatch, tmp_path):
    monkeypatch.setenv('VERA_PLACEMENT', '/a/b')
    monkeypatch.setenv('VERA_COARSE_PLACEMENT', '/a/b')
    assert cp.placement_from_env() == '/a/b'
    monkeypatch.setenv('VERA_COARSE_PLACEMENT', '/a/./b/')           # the same place after normalisation
    monkeypatch.setenv('VERA_PLACEMENT', ' /a/b ')
    assert cp.placement_from_env().strip() == '/a/b'


def test_an_empty_value_is_unset(monkeypatch):
    monkeypatch.setenv('VERA_PLACEMENT', '')
    monkeypatch.setenv('VERA_COARSE_PLACEMENT', '')
    assert cp.placement_from_env() is None
    monkeypatch.setenv('VERA_COARSE_PLACEMENT', '/x')
    assert cp.placement_from_env() == '/x'                          # an empty main name does not hide the alias, and is not a conflict


def test_two_different_places_are_the_typed_error(monkeypatch):
    monkeypatch.setenv('VERA_PLACEMENT', '/a/b')
    monkeypatch.setenv('VERA_COARSE_PLACEMENT', '/c/d')
    with pytest.raises(cp.PlacementEnvConflict) as exc:
        cp.placement_from_env()
    assert exc.value.error == 'PLACEMENT_ENV_CONFLICT' and exc.value.detail == {'VERA_PLACEMENT': '/a/b', 'VERA_COARSE_PLACEMENT': '/c/d'}
    assert isinstance(exc.value, ValueError)


# ---- the entrances --------------------------------------------------------------------------------------------------------------------------

def test_ask_refuses_a_conflict_with_the_typed_error_and_exit_2(world, capsys, monkeypatch):
    monkeypatch.setenv('VERA_PLACEMENT', SENTINEL)
    monkeypatch.setenv('VERA_COARSE_PLACEMENT', '/another/place')
    rc, out = run_ask(world, capsys)
    assert rc == 2 and out['verdict'] == 'PLACEMENT_ENV_CONFLICT' and out['kind'] == 'unknown'
    assert out['detail'] == {'VERA_PLACEMENT': SENTINEL, 'VERA_COARSE_PLACEMENT': '/another/place'}


def test_chat_refuses_a_conflict_before_reading_anything(world, capsys, monkeypatch):
    monkeypatch.setenv('VERA_PLACEMENT', SENTINEL)
    monkeypatch.setenv('VERA_COARSE_PLACEMENT', '/another/place')
    monkeypatch.setattr('verantyx.tui.read_input', lambda _p: pytest.fail('the REPL must not start'))
    capsys.readouterr()
    rc = cli.main(['--store', world['store'], 'chat', '--mode', 'round5', '--document', world['doc']])
    assert rc == 2 and json.loads(capsys.readouterr().out)['verdict'] == 'PLACEMENT_ENV_CONFLICT'


@pytest.mark.parametrize('extra', [['--no-llm'], ['--backend', 'ollama', '--model', 'm']])
def test_serve_refuses_a_conflict_and_does_not_start(world, capsys, monkeypatch, extra):
    monkeypatch.setenv('VERA_PLACEMENT', SENTINEL)
    monkeypatch.setenv('VERA_COARSE_PLACEMENT', '/another/place')
    started = []
    monkeypatch.setattr('verantyx.vera_server.serve', lambda *a, **k: started.append(1) or 0)
    capsys.readouterr()
    rc = cli.main(['--store', world['store'], 'serve', '--document', world['doc']] + extra)
    out = json.loads(capsys.readouterr().out)
    assert rc == 2 and out['verdict'] == 'PLACEMENT_ENV_CONFLICT' and started == []


def test_serve_with_the_argument_ignores_the_alias_the_argument_wins(world, capsys, monkeypatch):
    """`--placement` is the user's word for this run: the compatible name cannot disagree with it."""
    monkeypatch.setenv('VERA_COARSE_PLACEMENT', '/another/place')
    started = []
    monkeypatch.setattr('verantyx.vera_server.serve', lambda *a, **k: started.append(1) or 0)
    capsys.readouterr()
    rc = cli.main(['--store', world['store'], 'serve', '--no-llm', '--document', world['doc'], '--placement', SENTINEL])
    assert rc == 0 and started == [1] and os.environ['VERA_PLACEMENT'] == SENTINEL and 'VERA_COARSE_PLACEMENT' not in os.environ
    os.environ.pop('VERA_PLACEMENT', None)           # the entrance wrote it for the process (as before); not left behind for other tests


def test_the_compatible_name_alone_gives_ask_the_placement_and_the_same_answer(world, capsys, monkeypatch):
    monkeypatch.setenv('VERA_PLACEMENT', SENTINEL)
    rc_main, via_main = run_ask(world, capsys)
    monkeypatch.delenv('VERA_PLACEMENT')
    monkeypatch.setenv('VERA_COARSE_PLACEMENT', SENTINEL)
    rc_alias, via_alias = run_ask(world, capsys)
    assert rc_main == rc_alias == 0
    assert via_main['verdict'] == 'ANSWER' and via_main['values'] == ['本'] and via_main['door'] == 'question_cross'
    assert key(via_alias) == key(via_main)                                  # the alias gives the same answer
    assert 'VERA_PLACEMENT' not in os.environ                               # and the call put the environment back
    monkeypatch.delenv('VERA_COARSE_PLACEMENT')
    rc_none, none = run_ask(world, capsys)
    assert none['verdict'] != 'ANSWER'                                      # control: without a placement this question is not answered


def test_both_names_with_the_same_place_work(world, capsys, monkeypatch):
    monkeypatch.setenv('VERA_PLACEMENT', SENTINEL)
    monkeypatch.setenv('VERA_COARSE_PLACEMENT', SENTINEL)
    rc, out = run_ask(world, capsys)
    assert rc == 0 and out['values'] == ['本']


def test_the_scope_puts_the_environment_back_even_when_the_call_raises(monkeypatch):
    from verantyx import doc_answer
    monkeypatch.setenv('VERA_PLACEMENT', '/before')
    with pytest.raises(RuntimeError):
        with doc_answer.placement_scope('/inside'):
            assert os.environ['VERA_PLACEMENT'] == '/inside'
            raise RuntimeError('boom')
    assert os.environ['VERA_PLACEMENT'] == '/before'
    monkeypatch.delenv('VERA_PLACEMENT')
    with doc_answer.placement_scope('/inside'):
        pass
    assert 'VERA_PLACEMENT' not in os.environ


def test_the_coarse_query_reads_the_main_name(monkeypatch):
    """`coarse_place._open(None)` (the `vera placement` / coarse query path) resolves the environment like the entrances (ruling 6): VERA_PLACEMENT is the one name that is read."""
    monkeypatch.delenv('VERA_COARSE_PLACEMENT', raising=False)
    monkeypatch.setenv('VERA_PLACEMENT', '/nowhere/w16t2-main')
    pl, why = cp._open(None)
    assert pl is None and why[0] == 'MISSING' and why[1] == '/nowhere/w16t2-main'


def test_the_coarse_query_reads_the_compatible_name_alone(monkeypatch):
    monkeypatch.delenv('VERA_PLACEMENT', raising=False)
    monkeypatch.setenv('VERA_COARSE_PLACEMENT', '/nowhere/w16t2-alias')
    pl, why = cp._open(None)
    assert pl is None and why[0] == 'MISSING' and why[1] == '/nowhere/w16t2-alias'


def test_the_coarse_query_types_a_conflict(monkeypatch):
    monkeypatch.setenv('VERA_PLACEMENT', '/nowhere/w16t2-a')
    monkeypatch.setenv('VERA_COARSE_PLACEMENT', '/nowhere/w16t2-b')
    assert cp._open(None) == (None, ('PLACEMENT_ENV_CONFLICT', None))
    r = cp.query('土手')
    assert r['state'] == 'NO_PLACEMENT' and r['placement']['reason'] == 'PLACEMENT_ENV_CONFLICT' and r['top'] == []
    assert 'PLACEMENT_ENV_CONFLICT' in cp.NO_PLACEMENT_REASONS
    assert cp._open('/nowhere/given')[1] == ('MISSING', '/nowhere/given')       # a path that is given is never the environment's


def test_the_layer_summary_types_a_conflict(monkeypatch):
    import types
    from verantyx import vera_server as VS
    monkeypatch.setenv('VERA_PLACEMENT', '/nowhere/w16t2-a')
    monkeypatch.setenv('VERA_COARSE_PLACEMENT', '/nowhere/w16t2-b')
    got = VS._layer_summary(types.SimpleNamespace(layer='w16t2-no-such-layer'))
    assert got['status'] == 'PLACEMENT_ENV_CONFLICT' and got['growth'] is None and set(got) == {'name', 'status', 'growth'}
