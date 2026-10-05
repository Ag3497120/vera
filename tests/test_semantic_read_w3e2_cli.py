"""W3-e2 (K333, D3): the entrances: `vera read` (assume by default; --strict-read; VERA_READ_MODE), `vera chat --strict-read`, `vera placement growth` (assumption_rate)."""
import io
import json
import os
import subprocess
import sys
from contextlib import redirect_stdout
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
R9 = '/Users/motonisihikoudai/Projects/vera-impl/wt/W3-a6-S/build/coarse-W3a/full/r9/run2'
PY = sys.executable


def vera(*args, env=None, check_code=None):
    e = dict(os.environ, PYTHONPATH=str(ROOT), PYTHONDONTWRITEBYTECODE='1')
    e.pop('VERA_READ_MODE', None); e.pop('VERA_PLACEMENT', None); e.pop('VERA_PLACEMENT_LAYER', None)
    e.update(env or {})
    p = subprocess.run([PY, '-m', 'verantyx.cli', *args], capture_output=True, text=True, env=e, cwd=str(ROOT))
    return p.returncode, p.stdout


def main_out(*argv):
    from verantyx import semantic_read
    buf = io.StringIO()
    with redirect_stdout(buf):
        code = semantic_read.main(list(argv))
    return code, buf.getvalue()


@pytest.mark.parametrize('text', ['母が部屋で本を読んだ。', 'ウサギが図書館へ走った。', '整備士が工房でポルミナを調整した。', 'ハルは本をぐるんと見た。'])
def test_a_sentence_stage_e2_does_not_change_is_byte_identical_to_main(text):
    code, out = vera('read', '--text', text, '--placement', R9)
    code2, out2 = main_out('--text=' + text, '--placement=' + R9)
    assert (code, out) == (code2, out2)


def test_an_assumed_reading_is_printed_in_the_assume_form_and_strict_read_turns_it_off():
    code, out = vera('read', '--text', 'ハルは本をザクった。')
    d = json.loads(out)
    assert code == 0 and d['read_mode'] == 'assumed' and d['assumption_note'] == '（ザクを動詞として）'
    code, out = vera('read', '--strict-read', '--text', 'ハルは本をザクった。')
    code2, out2 = main_out('--text=ハルは本をザクった。')
    assert (code, out) == (code2, out2) and json.loads(out)['abstain']['reasons'] == ['NO_PREDICATE_TOKEN']


def test_the_environment_variable_and_the_flag():
    code, out = vera('read', '--text', 'ハルは本をザクった。', env={'VERA_READ_MODE': 'strict'})
    assert code == 0 and 'read_mode' not in json.loads(out)
    code, out = vera('read', '--strict-read', '--text', 'ハルは本をザクった。', env={'VERA_READ_MODE': 'assume'})
    assert 'read_mode' not in json.loads(out)                                   # the flag wins
    code, out = vera('read', '--text', 'ハルは本をザクった。', env={'VERA_READ_MODE': 'maybe'})
    assert code == 2 and json.loads(out)['error']['type'] == 'BAD_READ_MODE'
    code, out = vera('read', '--text', 'ハルは本をザクった。', env={'VERA_READ_MODE': 'assume'})
    assert json.loads(out)['read_mode'] == 'assumed'


def test_a_premise_that_nothing_decides_is_a_typed_reason_at_the_end():
    code, out = vera('read', '--text', 'ハルはミナに本を渡した。', '--placement', R9)
    d = json.loads(out)
    assert code == 0 and d['readable'] is False and d['read_mode'] == 'strict'
    assert d['abstain']['reasons'] == ['RECIPIENT_TYPE_UNDETERMINED:ミナ', 'ASSUMPTION_UNDETERMINED:ミナ:に']


def test_the_assumption_is_written_to_the_ledger_with_the_hash_of_the_sentence_only(tmp_path):
    led = tmp_path / 'l.jsonl'
    code, out = vera('read', '--text', 'ナナが来た。', '--ledger-file', str(led))
    d = json.loads(out)
    assert d['read_mode'] == 'assumed' and d['assumptions'][0]['ledger_id']
    rows = [json.loads(l) for l in led.read_text(encoding='utf-8').splitlines()]
    a = [r for r in rows if r.get('type') == 'assumption']
    assert len(a) == 1 and 'sentence' not in a[0]['context'] and a[0]['context']['sentence_sha256']


def test_help_of_the_entrances_names_strict_read():
    for cmd in ('read', 'chat', 'serve'):
        code, out = vera(cmd, '--help')
        assert '--strict-read' in out, cmd


def test_growth_adds_the_assumption_rate_only_when_there_are_assumption_rows():
    from verantyx import cli
    class Led:
        def __init__(self, rows): self.rows = rows
        def entries(self): return self.rows
    base = {'layer': 'lay', 'layer_status': 'OK'}
    assert cli._growth_with_assumption(base, Led([{'type': 'testimony', 'word': 'x'}])) == base
    rows = [{'type': 'assumption', 'word': 'フレーム'}, {'type': 'assumption', 'word': 'ホイール'}, {'type': 'assumption', 'word': 'フレーム'},
            {'type': 'promoted_to_layer', 'word': 'フレーム', 'layer_name': 'lay'}, {'type': 'promoted_to_layer', 'word': 'ホイール', 'layer_name': 'other'}]
    out = cli._growth_with_assumption(base, Led(rows))
    assert out['assumption'] == {'rows': 3, 'words': 2, 'promoted_words': 1, 'assumption_rate': 0.5} and list(out)[-1] == 'assumption'
