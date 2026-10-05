"""W10-f05 (docs/COARSE_PLACEMENT.md section 12.19, docs/FUSION.md section 7): the entrances. `vera read/ask/serve/chat --layer` (= VERA_PLACEMENT_LAYER), `vera placement grow|growth`, and the `vera.placement_layer`
key of `vera serve`. Without a layer nothing changes (K297)."""
import json
import os
from pathlib import Path

import pytest

from verantyx import cli
from verantyx import coarse_place as CP
from verantyx import placement_layer as PL
from verantyx import vera_server as VS
from verantyx.testimony_ledger import TestimonyLedger

R9 = '/Users/motonisihikoudai/Projects/vera-impl/wt/W3-a6-S/build/coarse-W3a/full/r9/run2'
DATA = Path(__file__).parent / 'fusion' / 'w10f05'
SENT = 'ウサギが図書館へ走った。'          # two words the base leaves MULTIPLE: with a layer that types them the sentence is readable and has no hole


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    if not Path(R9).exists():
        pytest.skip('ENV_MISSING[coarse placement r9/run2]')
    monkeypatch.setenv(PL.ENV_LAYER, '')               # registered, so that a variable the CLI sets is removed again
    for k in (PL.ENV_ROOT, 'VERA_SOVEREIGN_ROOT', 'VERA_SOVEREIGN_STORE'):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv('VERA_PLACEMENT', R9)


@pytest.fixture(autouse=True)
def _isolated_caches(monkeypatch):
    # vera serve opens the placement on its own thread (vera-fusion); a sqlite connection made there must not stay in the
    # module-wide caches, or a later test on the main thread gets sqlite3.ProgrammingError. monkeypatch restores the originals.
    monkeypatch.setattr(CP, '_CACHE', {})
    monkeypatch.setattr(PL, '_CACHE', {})


def make_layer(tmp_path, words, name='dom'):
    led = TestimonyLedger(tmp_path / (name + '.ledger.jsonl'))
    path = str(tmp_path / (name + '.sqlite'))
    sha = CP._open(R9)[0].sha
    for i, (w, t) in enumerate(words):
        PL.write_entry(path, led, base_sha256=sha, word=w, type=t, origin='layer_human', decided_by=['layer_human'], evidence={'human': True}, role_frame=None, key='k%d' % i)
    return path


def call(capsys, *argv):
    code = cli.main(list(argv))
    return code, capsys.readouterr().out


def test_the_flag_and_the_variable_do_the_same_and_without_either_the_output_is_the_base(tmp_path, capsys, monkeypatch):
    layer = make_layer(tmp_path, [('ウサギ', 'ANIMAL'), ('図書館', 'PLACE')])
    code, base = call(capsys, 'read', '--text', SENT, '--holes', '--placement', R9)
    assert code == 0 and json.loads(base)['holes_status'] == 'HOLES_FOUND'
    monkeypatch.setenv(PL.ENV_LAYER, '')
    assert call(capsys, 'read', '--text', SENT, '--holes', '--placement', R9) == (0, base)                 # an empty variable is the same as no layer: byte for byte
    code, flagged = call(capsys, 'read', '--text', SENT, '--holes', '--placement', R9, '--layer', layer)
    assert os.environ[PL.ENV_LAYER] == layer and json.loads(flagged)['holes'] == [] and flagged != base
    monkeypatch.setenv(PL.ENV_LAYER, layer)
    assert call(capsys, 'read', '--text', SENT, '--holes', '--placement', R9) == (0, flagged)             # the variable alone gives the same output as the flag
    monkeypatch.setenv(PL.ENV_LAYER, '')
    assert call(capsys, 'read', '--text', SENT, '--holes', '--placement', R9) == (0, base)                # take the layer away and the base is back


def test_read_without_holes_is_byte_identical_without_a_layer(capsys, monkeypatch):
    from verantyx import semantic_read
    for text in ('母が部屋で本を読んだ。', SENT, '整備士が工房でポルミナを調整した。'):
        code, out = call(capsys, 'read', '--text', text, '--placement', R9)
        code2 = semantic_read.main(['--text=' + text, '--placement=' + R9])
        assert code == code2 and out == capsys.readouterr().out


def test_every_entrance_takes_layer(capsys):
    for sub in ('read', 'ask', 'chat', 'serve'):
        with pytest.raises(SystemExit):
            cli.main([sub, '--help'])
        assert '--layer' in capsys.readouterr().out, sub


def test_ask_sets_the_variable_before_anything_is_read(tmp_path, capsys, monkeypatch):
    layer = make_layer(tmp_path, [('ウサギ', 'ANIMAL')])
    doc = tmp_path / 'd.txt'
    doc.write_text('母が部屋で本を読んだ。\n', encoding='utf-8')
    code, out = call(capsys, 'ask', '--mode', 'round5', '--document', str(doc), '--layer', layer, '--', '誰が本を読んだ？')
    assert os.environ[PL.ENV_LAYER] == layer and json.loads(out)['verdict'] in ('ANSWER', 'UNKNOWN_UNREAD', 'UNKNOWN_NO_EVIDENCE', 'UNKNOWN_UNSUPPORTED_EVIDENCE', 'AMBIGUOUS')


def test_grow_and_growth_through_the_command(tmp_path, capsys, monkeypatch):
    monkeypatch.setenv(PL.ENV_ROOT, str(tmp_path / 'layers'))
    (tmp_path / 'layers').mkdir()
    table = DATA / 'fake_declarations_bicycle.json'
    ledger = tmp_path / 'ledger.jsonl'
    code, out = call(capsys, 'placement', 'grow', '--documents', str(DATA / 'domain_bicycle.txt'), '--layer', 'bike', '--backend', 'fake', '--fake-table', str(table),
                     '--ledger-file', str(ledger), '--placement', R9, '--dump-sent', str(tmp_path / 'sent.jsonl'))
    rep = json.loads(out)
    assert code == 0 and rep['verdict'] == 'GREW' and rep['documents']['read'] == 1 and rep['candidates'] >= 30 and rep['written']['layer_human'] == 0
    assert sum(rep['written'].values()) > 0 and (tmp_path / 'sent.jsonl').read_text(encoding='utf-8').strip()
    code, out = call(capsys, 'placement', 'growth', '--layer', 'bike', '--ledger-file', str(ledger), '--placement', R9, '--list')
    g = json.loads(out)
    assert code == 0 and g['words']['direct'] == rep['written']['layer_confirmed'] and g['words']['estimated'] == rep['written']['layer_estimated'] and g['words']['human'] == 0
    assert g['ledger']['chain_ok'] is True and g['ledger']['promoted_to_layer'] == sum(rep['written'].values()) and g['last_grown'] and len(g['list']) == g['words_total']
    assert rep['ledger']['rows_added'] == g['ledger']['rows'] - 1                                          # the header was there before
    assert set(json.loads(l)['kind'] for l in (tmp_path / 'sent.jsonl').read_text(encoding='utf-8').splitlines()) == {'noun', 'predicate'}


def test_grow_refuses_with_a_type_and_writes_nothing(tmp_path, capsys, monkeypatch):
    doc = str(DATA / 'domain_bicycle.txt')
    table = str(DATA / 'fake_declarations_bicycle.json')
    base = ['placement', 'grow', '--documents', doc, '--backend', 'fake', '--fake-table', table, '--ledger-file', str(tmp_path / 'l.jsonl'), '--placement', R9]
    for argv, verdict in ((base, 'LAYER_REQUIRED'), (base + ['--layer', 'bike'], 'LAYER_UNAVAILABLE:ROOT_UNSET'), (base[:3] + ['/no/such/doc.txt'] + base[4:] + ['--layer', str(tmp_path / 'x.sqlite')], 'DOCUMENT_NOT_FOUND'),
                          (base + ['--layer', str(tmp_path / 'x.sqlite'), '--fake-script', table], 'FAKE_NEEDS_ONE_OF'),
                          ([a for a in base if a != '--ledger-file' and a != str(tmp_path / 'l.jsonl')] + ['--layer', str(tmp_path / 'x.sqlite')], 'LEDGER_REQUIRED')):
        code, out = call(capsys, *argv)
        assert code == 2 and json.loads(out)['verdict'] == verdict, (verdict, out)
    assert not (tmp_path / 'x.sqlite').exists() and not (tmp_path / 'l.jsonl').exists()
    code, out = call(capsys, 'placement', 'growth', '--layer', str(tmp_path / 'absent.sqlite'))
    assert code == 2 and json.loads(out)['verdict'] == 'LAYER_UNAVAILABLE:MISSING'


def test_the_old_placement_command_is_not_taken_over(monkeypatch):
    seen = []
    import verantyx.placement as P
    monkeypatch.setattr(P, 'main', lambda argv: seen.append(list(argv)) or 0)
    assert cli.main(['placement', 'some-store.json', '--n-queries', '7']) == 0
    assert seen and seen[0][0] == 'some-store.json' and seen[0][1:3] == ['--n-queries', '7']


# ---------------------------------------------------------------------------------------------------------------- vera serve
class FakeLLM:
    def __call__(self, model, messages, fmt):
        return {'ok': True, 'content': '母が部屋で本を読んだ。', 'error': None, 'usage': {}}


def cfg_of(tmp_path, **kw):
    for key in list(CP._CACHE):
        try:
            CP._CACHE.pop(key).con.close()
        except Exception:
            pass
    d = Path(tmp_path) / 'd.txt'
    d.write_text('母が部屋で本を読んだ。\n', encoding='utf-8')
    return VS.FusionConfig.load(model='fake-model', documents=[str(d)], llm_chat=FakeLLM(), **kw)


def turn(cfg):
    return VS.fusion_turn([{'role': 'user', 'content': '誰が本を読んだ？'}], None, cfg)


def test_serve_adds_placement_layer_only_with_a_layer_and_leaves_the_fusion_layer_alone(tmp_path, monkeypatch):
    layer = make_layer(tmp_path, [('ウサギ', 'ANIMAL'), ('図書館', 'PLACE'), ('ディレイラー', 'ARTIFACT')])
    monkeypatch.setenv(PL.ENV_LAYER, '')
    base = turn(cfg_of(tmp_path))
    assert 'placement_layer' not in base['vera'] and list(base['vera']) == ['schema', 'layer', 'request_kind', 'reading', 'grammar', 'grammar_id', 'llm', 'grammar_check', 'provenance', 'outcome', 'timing']
    cfg = cfg_of(tmp_path, layer=layer)
    assert os.environ[PL.ENV_LAYER] == layer
    res = turn(cfg)
    pl = res['vera']['placement_layer']
    assert list(res['vera'])[-1] == 'placement_layer' and pl['name'] == 'dom' and pl['status'] == 'OK'
    assert pl['growth'] == {'words_direct': 0, 'words_human': 3, 'words_estimated': 0, 'last_grown': pl['growth']['last_grown']} and pl['growth']['last_grown']
    assert res['vera']['layer'] == base['vera']['layer'] == 0                                              # the fusion layer 0/1 is another key and is not changed
    strip = lambda r: {k: v for k, v in r['vera'].items() if k not in ('placement_layer', 'timing')}
    assert strip(res) == strip(base) and res['content'] == base['content']


def test_serve_says_when_the_layer_cannot_be_used_and_refuses_a_conflicting_variable(tmp_path, monkeypatch):
    monkeypatch.setenv(PL.ENV_LAYER, '')
    res = turn(cfg_of(tmp_path, layer=str(tmp_path / 'absent.sqlite')))
    assert res['vera']['placement_layer'] == {'name': 'absent', 'status': 'LAYER_UNAVAILABLE:MISSING', 'growth': None}
    monkeypatch.setenv(PL.ENV_LAYER, '/some/other.sqlite')
    with pytest.raises(VS.FusionBadRequest) as e:
        cfg_of(tmp_path, layer=str(tmp_path / 'mine.sqlite'))
    assert e.value.error == 'LAYER_ENV_CONFLICT'


def test_the_variable_alone_also_reports_the_layer_in_serve(tmp_path, monkeypatch):
    layer = make_layer(tmp_path, [('ウサギ', 'ANIMAL'), ('図書館', 'PLACE'), ('ディレイラー', 'ARTIFACT')])
    monkeypatch.setenv(PL.ENV_LAYER, layer)                 # no --layer: the environment is what makes the layer work for the reader
    cfg = cfg_of(tmp_path)
    assert cfg.layer == layer
    res = turn(cfg)
    pl = res['vera']['placement_layer']
    assert list(res['vera'])[-1] == 'placement_layer' and pl['name'] == 'dom' and pl['status'] == 'OK' and pl['growth']['words_human'] == 3
    monkeypatch.setenv(PL.ENV_LAYER, '')                    # an empty variable is no layer: no key
    assert 'placement_layer' not in turn(cfg_of(tmp_path))['vera']
