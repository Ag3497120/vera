"""W3-b: the entries `python -m verantyx.semantic_read --text=... --events` and `python -m verantyx.cli read-events --text=...`.

* without --events the output is exactly what it was (the reader's own `read()` serialised the way `main` does);
* with --events the only difference is the key `events`, added last; the output is deterministic;
* a refused input answers the same with and without --events (same bytes, exit code 2);
* the default output does not load verantyx.event_cross.
"""
import io
import json
import os
import subprocess
import sys
from contextlib import redirect_stdout
from pathlib import Path

import pytest

from verantyx import semantic_read as SR

TREE = Path(__file__).resolve().parent.parent
INPUTS = [
    '先生が生徒に地図を渡した。',                  # readable, Japanese
    '犬が猫を追いかけた。',
    'The teacher gave the student a map.',        # readable, English (or a typed abstention; either is fine here)
    'The dog chased the cat.',
    'おはようございます。',                        # unreadable_input
    '弟は兄より背が高い。',                        # comparison
    '木の下にいる子どもが本を読んだ。',            # relative clause
    '-- 先生が笑った。',                           # starts with dashes (given as --text=...)
    '先生が笑った。\n生徒が笑った。',              # a newline
    'zzzz qqqq',                                   # English text that is not a sentence
    '1234',                                        # no language
]
REFUSED = [
    ('--text=', 'EMPTY_TEXT'), ('--text=   ', 'EMPTY_TEXT'), ('--text=' + 'あ' * 1001, 'TEXT_TOO_LONG'),
    ('--text=あ\x01', 'CONTROL_CHARACTERS'),
]


def run_main(argv):
    buf = io.StringIO()
    with redirect_stdout(buf):
        code = SR.main(argv)
    return buf.getvalue(), code


def default_bytes(text, lang=None):
    return json.dumps(SR.read(text, lang), ensure_ascii=False) + '\n'


@pytest.mark.parametrize('text', INPUTS)
def test_default_output_is_the_reader_output_unchanged(text):
    out, code = run_main(['--text=' + text])
    assert out == default_bytes(text) and code == 0


@pytest.mark.parametrize('text', INPUTS)
def test_events_output_is_the_default_output_plus_events_last(text):
    plain, code0 = run_main(['--text=' + text])
    with_events, code1 = run_main(['--text=' + text, '--events'])
    assert code0 == code1 == 0
    obj = json.loads(with_events)
    assert list(obj)[-1] == 'events' and list(obj)[:-1] == list(json.loads(plain))
    stripped = {k: v for k, v in obj.items() if k != 'events'}
    assert json.dumps(stripped, ensure_ascii=False) + '\n' == plain          # byte for byte once `events` is taken away
    assert obj['events']['schema'] == 'verantyx.event_cross/1'
    assert len(obj['events']['relations']) == len(obj['relations'])
    assert (obj['events']['status'] == 'CROSSED') == obj['readable']
    assert obj['events']['counts']['crosses'] == len(obj['clauses'])
    again, _ = run_main(['--text=' + text, '--events'])
    assert again == with_events                                              # deterministic


def test_the_events_of_a_readable_sentence_follow_the_clause():
    obj = json.loads(run_main(['--text=先生が生徒に地図を渡した。', '--events'])[0])
    x = obj['events']['crosses'][0]
    assert x['center']['predicate'] == '渡す'
    assert {k: v['fillers'][0]['surface'] for k, v in x['arms'].items()} == obj['clauses'][0]['roles']
    assert x['provenance']['rule'] == obj['clause_meta'][0]['rule'] and x['provenance']['span'] == obj['clause_meta'][0]['span']


def test_an_unreadable_sentence_gets_no_cross_and_its_abstain_is_copied():
    obj = json.loads(run_main(['--text=おはようございます。', '--events'])[0])
    assert obj['readable'] is False and obj['events']['status'] == 'ABSTAINED'
    assert obj['events']['crosses'] == [] and obj['events']['abstain'] == obj['abstain']


@pytest.mark.parametrize('arg,etype', REFUSED)
def test_a_refused_input_answers_the_same_with_events(arg, etype):
    plain, c0 = run_main([arg]); ev, c1 = run_main([arg, '--events'])
    assert plain == ev and c0 == c1 == 2 and json.loads(ev)['error']['type'] == etype and 'events' not in json.loads(ev)


def test_refusals_without_text_and_with_language_mismatch_are_unchanged_by_events():
    for argv in (['--events'], ['--text=犬が走った。', '--lang=en', '--events'], ['--text=a dog ran', '--lang=xx', '--events']):
        plain = [a for a in argv if a != '--events']
        assert run_main(argv) == run_main(plain) and run_main(argv)[1] == 2


def test_events_with_a_value_is_a_bad_argument():
    out, code = run_main(['--text=犬が走った。', '--events=x'])
    assert code == 2 and json.loads(out)['error']['type'] == 'BAD_ARGUMENTS'


def _base_main():
    """main() of the reading entry as it was at the base commit (the same in-memory load that tests/event_cross/e1_parity.py uses)."""
    import importlib.util
    spec = importlib.util.spec_from_file_location('w3b_e1_parity', TREE / 'tests' / 'event_cross' / 'e1_parity.py')
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    return mod.load_base()[0].main


def _base_run(argv):
    buf = io.StringIO()
    with redirect_stdout(buf):
        code = _base_main()(argv)
    return buf.getvalue(), code


ABBREVIATIONS = [
    ['--text=犬が走った。', '--e'], ['--text=犬が走った。', '--ev'], ['--text=犬が走った。', '--eve'], ['--text=犬が走った。', '--event'],
    ['--e', '--text=犬が走った。'], ['--text', '犬が走った。', '--ev'], ['--ev'], ['--text=犬が走った。', '--even'],
    ['--text=犬が走った。', '--eventss'], ['--text=犬が走った。', '--Events'],
    ['--text=犬が走った。', '--', '--events'],          # after `--` it is not an option of ours, it never was
]


@pytest.mark.parametrize('argv', ABBREVIATIONS)
def test_argv_without_exactly_events_answers_as_the_base_commit_did(argv):
    """argparse's prefix matching must not turn `--e` / `--ev` / `--eve` / `--event` into `--events`: bytes and exit code equal the base."""
    out, code = run_main(argv)
    assert (out, code) == _base_run(argv)
    assert code == 2 and 'events' not in json.loads(out)


def test_an_abbreviation_is_a_bad_argument_with_the_base_detail():
    out, code = run_main(['--text=犬が走った。', '--ev'])
    assert code == 2 and json.loads(out) == {'error': {'type': 'BAD_ARGUMENTS', 'detail': 'unrecognized arguments: --ev'}}


def test_text_given_in_a_prefix_form_is_still_accepted_with_and_without_events():
    # `--te=` (a prefix of --text) worked at the base commit and must keep working; --events next to it adds the key only
    plain, c0 = run_main(['--te=犬が走った。'])
    assert (plain, c0) == _base_run(['--te=犬が走った。']) and c0 == 0
    ev, c1 = run_main(['--te=犬が走った。', '--events'])
    assert c1 == 0 and 'events' in json.loads(ev)
    obj = json.loads(ev); obj.pop('events')
    assert json.dumps(obj, ensure_ascii=False) + '\n' == plain


def test_unknown_argument_is_still_bad_arguments():
    out, code = run_main(['--text=犬が走った。', '--bogus'])
    assert code == 2 and json.loads(out)['error']['type'] == 'BAD_ARGUMENTS'


# ---------------------------------------------------------------------------------------------------------------------------------
# a child process: the real entries, the exit codes, the modules loaded
# ---------------------------------------------------------------------------------------------------------------------------------
def child(args, code=None):
    env = {'HOME': os.environ.get('HOME', ''), 'PATH': '/usr/bin:/bin', 'PYTHONDONTWRITEBYTECODE': '1', 'PYTHONPATH': str(TREE)}
    cmd = [sys.executable] + (['-c', code] if code else ['-m'] + args)
    return subprocess.run(cmd, cwd=str(TREE), env=env, capture_output=True, text=True, timeout=120)


@pytest.mark.parametrize('text', ['先生が生徒に地図を渡した。', '犬が猫を追いかけた。', 'おはようございます。', 'The dog chased the cat.', '-- 先生が笑った。'])
def test_cli_read_events_equals_semantic_read_events(text):
    a = child(['verantyx.cli', 'read-events', '--text=' + text])
    b = child(['verantyx.semantic_read', '--text=' + text, '--events'])
    assert a.returncode == b.returncode == 0
    assert a.stdout == b.stdout and a.stdout.endswith('\n') and a.stdout.count('\n') == 1
    assert a.stdout == run_main(['--text=' + text, '--events'])[0]
    assert json.loads(a.stdout)['events']['schema'] == 'verantyx.event_cross/1'


def test_cli_read_events_refusals_are_the_same_as_the_module():
    for extra in ([], ['--text='], ['--text=犬が走った。', '--lang=en']):
        a = child(['verantyx.cli', 'read-events'] + extra)
        b = child(['verantyx.semantic_read', '--events'] + extra)
        assert a.returncode == b.returncode == 2 and a.stdout == b.stdout


def test_the_default_output_does_not_load_the_event_cross_module():
    code = ("import sys, io, contextlib; from verantyx import semantic_read as s; "
            "buf = io.StringIO()\n"
            "with contextlib.redirect_stdout(buf): s.main(['--text=犬が猫を追いかけた。'])\n"
            "print('verantyx.event_cross' in sys.modules)\n"
            "with contextlib.redirect_stdout(buf): s.main(['--text=犬が猫を追いかけた。', '--events'])\n"
            "print('verantyx.event_cross' in sys.modules)")
    r = child(None, code)
    assert r.returncode == 0 and r.stdout.split() == ['False', 'True'], r.stderr


def test_every_loaded_verantyx_module_is_in_this_tree():
    code = ("import sys, io, contextlib; from verantyx import semantic_read as s\n"
            "with contextlib.redirect_stdout(io.StringIO()): s.main(['--text=犬が猫を追いかけた。', '--events'])\n"
            "print([m.__file__ for n, m in sys.modules.items() if n.startswith('verantyx') and getattr(m, '__file__', None) "
            "and not m.__file__.startswith(%r)])" % (str(TREE) + '/'))
    r = child(None, code)
    assert r.returncode == 0 and r.stdout.strip() == '[]', r.stdout
