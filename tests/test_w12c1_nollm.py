"""W12-c1 T4: `serve --no-llm`. An LLM that raises if it is called is plugged in everywhere; the placement is a hand-made one (the way test_serve_fusion.py does it)."""
import json
from pathlib import Path

import pytest

from verantyx import cli
from verantyx import confidence_tiers as CT
from verantyx import decode_grammar as G
from verantyx import event_cross as EC
from verantyx import observe as O
from verantyx import vera_server as VS

DOC = '太郎が地図を渡した。\n花子は本を読んだ。\n'
PLACE = {'太郎': 'PERSON', '花子': 'PERSON', '次郎': 'PERSON', '地図': 'ARTIFACT', '本': 'ARTIFACT'}


class Boom:
    def __init__(self):
        self.calls = 0

    def __call__(self, model, messages, fmt):
        self.calls += 1
        raise AssertionError('an LLM was called')


@pytest.fixture
def place(tmp_path, monkeypatch):
    for k in ('VERA_PLACEMENT', 'VERA_SOVEREIGN_ROOT', 'VERA_SOVEREIGN_STORE', 'VERA_PLACEMENT_LAYER', 'VERA_PLACEMENT_LAYER_ROOT'):
        # setenv-then-delenv makes monkeypatch record the ORIGINAL state (absent) so that a value written later by cli.main (--layer writes
        # os.environ directly) is removed at teardown; delenv(raising=False) alone records nothing when the variable was absent (review r1 M1)
        monkeypatch.setenv(k, 'x')
        monkeypatch.delenv(k)
    path = Path(tmp_path) / 'pl.json'
    path.write_text(json.dumps({'lemmas': {w: {'state': 'DECIDED', 'origin': 'direct', 'types': [t]} for w, t in PLACE.items()}, 'neighbors': {}}, ensure_ascii=False), encoding='utf-8')
    fp = O.FilePlacement.from_path(str(path))
    monkeypatch.setattr(EC, 'default_lookup', lambda *a, **k: fp)
    d = Path(tmp_path) / 'd.txt'
    d.write_text(DOC, encoding='utf-8')
    return str(d)


def single_cfg(doc, boom):
    cfg = VS.FusionConfig.load(model='fake', documents=[doc], llm_chat=boom)
    cfg.no_llm = True
    return cfg


def msg(q):
    return [{'role': 'user', 'content': q}]


def test_no_llm_never_calls_the_llm_whatever_the_reading(place):
    boom = Boom()
    cfg = single_cfg(place, boom)
    cases = [('太郎は何を渡した？', {}, 'QUESTION_CROSS'),                   # a record answers
             ('太郎は何を買った？', {}, 'NO_RECORD'),
             ('誰かが何かをしたのですか？', {}, None),                          # whatever the reader makes of it: still no LLM
             ('詩を書いて', {'request_kind': 'creative'}, 'RECORDS')]
    for q, opts, want in cases:
        out = VS.fusion_turn(msg(q), opts or None, cfg)
        assert boom.calls == 0 and out['vera']['llm']['called'] is False and out['vera']['no_llm'] is True
        if want:
            assert out['vera']['reading']['type'] == want
        assert out['content']
    assert boom.calls == 0


def test_a_record_answers_and_the_rest_is_a_typed_fixed_text(place):
    cfg = single_cfg(place, Boom())
    out = VS.fusion_turn(msg('太郎は何を渡した？'), None, cfg)
    assert out['content'] == '太郎が地図を渡した。' and out['vera']['outcome']['outcome'] in G.ANSWER_OUTCOMES
    out = VS.fusion_turn(msg('太郎は何を買った？'), None, cfg)
    assert out['content'] == G.FIXED_TEXT['NO_RECORD'] and out['vera']['outcome']['outcome'] == 'NO_RECORD'
    out = VS.fusion_turn(msg('詩を書いて'), {'request_kind': 'creative'}, cfg)           # RECORDS is not a key of FIXED_TEXT: no KeyError, a typed ABSTAIN, the reader's type kept
    assert out['content'] == G.FIXED_TEXT['ABSTAIN'] and out['vera']['reading']['type'] == 'RECORDS' and out['vera']['no_llm_fixed_as'] == 'ABSTAIN'


def test_structure_undetermined_is_typed(place):
    cfg = single_cfg(place, Boom())
    turn = G.plan_turn('太郎は何を渡した？', 'factual', cfg.records, cfg.documents, strict=False)
    forced = dict(turn, call_llm=True, record_answer=None, reading=dict(turn['reading'], type='STRUCTURE_UNDETERMINED', state='X', reason='forced'))
    t = CT.no_llm_plan(forced)
    content, vera = G.conclude(t, None, cfg.records, model='m')
    assert content == G.FIXED_TEXT['STRUCTURE_UNDETERMINED'] and vera['llm']['called'] is False


def test_the_default_entrance_is_unchanged_without_no_llm(place):
    boom = Boom()
    cfg = VS.FusionConfig.load(model='fake', documents=[place], llm_chat=lambda m, msgs, f: {'ok': True, 'content': '何か。', 'error': None, 'usage': {}})
    out = VS.fusion_turn(msg('太郎は何を買った？'), None, cfg)
    assert 'no_llm' not in out['vera'] and 'confidence_tiers' not in out['vera'] and out['vera']['llm']['called'] is True


def test_runner_adds_the_new_keys_and_keeps_vera_layer(place):
    runner = CT.TierRunner([], [place], profile='strict', order=('base',), with_default_missing=False)
    cfg = VS.FusionConfig(model='vera-no-llm', documents=[], records=None)
    cfg.no_llm, cfg.tiers = True, runner
    out = VS.fusion_turn(msg('太郎は何を渡した？'), None, cfg)
    v = out['vera']
    assert v['layer'] == 0 and v['no_llm'] is True and v['profile'] == 'strict' and v['assumptions'] == [] and v['assumptions_status'] == CT.ASSUMPTIONS_NOT_USED
    assert v['confidence_tiers']['agree'] == 1 and v['confidence_tiers']['answered'] == 1 and v['confidence_tiers']['counted'] == 1 and v['initial_layers']['tiers'][0]['name'] == 'base'
    assert runner.llm_calls == 0 and v['llm']['called'] is False
    assert out['content'] == '太郎が地図を渡した。'


def test_runner_abstention_has_agree_zero(place):
    runner = CT.TierRunner([], [place], profile='strict', order=('base',), with_default_missing=False)
    cfg = VS.FusionConfig(model='vera-no-llm', documents=[], records=None)
    cfg.no_llm, cfg.tiers = True, runner
    out = VS.fusion_turn(msg('太郎は何を買った？'), None, cfg)
    ct = out['vera']['confidence_tiers']
    assert ct['agree'] == 0 and ct['answered'] == 0 and ct['counted'] == 1
    assert runner.llm_calls == 0


def test_assume_profile_says_it_is_not_wired(place):
    runner = CT.TierRunner([], [place], profile='assume', order=('base',), with_default_missing=False)
    cfg = VS.FusionConfig(model='vera-no-llm', documents=[], records=None)
    cfg.no_llm, cfg.tiers = True, runner
    a = VS.fusion_turn(msg('太郎は何を買った？'), None, cfg)
    s = CT.TierRunner([], [place], profile='strict', order=('base',), with_default_missing=False)
    cfg2 = VS.FusionConfig(model='vera-no-llm', documents=[], records=None)
    cfg2.no_llm, cfg2.tiers = True, s
    b = VS.fusion_turn(msg('太郎は何を買った？'), None, cfg2)
    assert a['vera']['assumptions'] == [] and a['vera']['assumptions_status'] == 'NOT_WIRED_UNTIL_W3-e3'
    assert a['content'] == b['content'] and a['vera']['outcome'] == b['vera']['outcome']      # the same answer as strict, and it says so


def test_bad_requests_still_raise_from_the_base_stage(place):
    runner = CT.TierRunner([], [place], order=('base',), with_default_missing=False)
    cfg = VS.FusionConfig(model='vera-no-llm', documents=[], records=None)
    cfg.no_llm, cfg.tiers = True, runner
    with pytest.raises(VS.FusionBadRequest):
        VS.fusion_turn([], None, cfg)
    with pytest.raises(VS.FusionBadRequest):
        VS.fusion_turn(msg('x'), {'request_kind': 'nonsense'}, cfg)


# ---- the CLI --------------------------------------------------------------------------------------------------------------------------------
@pytest.fixture
def fake_serve(monkeypatch):
    calls = []

    def fake(st, save, **kw):
        calls.append(kw)
        return 0
    monkeypatch.setattr(VS, 'serve', fake)
    return calls


def cli_run(capsys, *argv):
    capsys.readouterr()
    rc = cli.main(list(argv))
    text = capsys.readouterr().out
    dec, i, outs = json.JSONDecoder(), 0, []
    while i < len(text):
        if text[i].isspace():
            i += 1
            continue
        obj, i = dec.raw_decode(text, i)
        outs.append(obj)
    return rc, outs


def test_cli_no_llm_is_refused_with_a_backend_and_the_flags_of_the_llm(tmp_path, fake_serve, capsys, place):
    st = str(tmp_path / 'S.json')
    for extra in (['--backend', 'ollama'], ['--model', 'm'], ['--strict'], ['--free'], ['--fill']):
        rc, outs = cli_run(capsys, '--store', st, 'serve', '--no-llm', *extra)
        assert rc == 2 and outs[-1]['verdict'] == 'NO_LLM_WITH_BACKEND'
    assert fake_serve == []


def test_cli_profile_and_tier_need_no_llm(tmp_path, fake_serve, capsys, place):
    st = str(tmp_path / 'S.json')
    rc, outs = cli_run(capsys, '--store', st, 'serve', '--profile', 'assume')
    assert rc == 2 and outs[-1]['verdict'] == 'PROFILE_NEEDS_NO_LLM'
    rc, outs = cli_run(capsys, '--store', st, 'serve', '--tier', 'law=/x.sqlite')
    assert rc == 2 and outs[-1]['verdict'] == 'TIER_NEEDS_NO_LLM'
    assert fake_serve == []


def test_cli_no_llm_serves_a_tiered_entrance(tmp_path, fake_serve, capsys, place):
    st = str(tmp_path / 'S.json')
    rc, outs = cli_run(capsys, '--store', st, 'serve', '--no-llm', '--profile', 'assume', '--document', place, '--port', '1')
    assert rc == 0 and len(fake_serve) == 1
    f = fake_serve[0]['fusion']
    assert f.no_llm is True and f.tiers.profile == 'assume' and [s.name for s in f.tiers.stages] == ['base']
    assert outs[0]['serve']['no_llm'] is True and fake_serve[0]['default_model'] == 'vera-no-llm'
    rc, outs = cli_run(capsys, '--store', st, 'serve', '--no-llm', '--tier', 'badspec')
    assert rc == 2 and outs[-1]['verdict'] == 'BAD_TIER'
    rc, outs = cli_run(capsys, '--store', st, 'serve', '--no-llm', '--tier', 'base=/x')
    assert rc == 2 and outs[-1]['verdict'] == 'TIER_BASE_IS_IMPLICIT'
    rc, outs = cli_run(capsys, '--store', st, 'serve', '--no-llm', '--document', str(tmp_path / 'nope.txt'))
    assert rc == 2 and outs[-1]['verdict'] == 'DOCUMENT_NOT_FOUND'


def test_cli_layer_does_not_leak_into_the_base_stage(tmp_path, fake_serve, capsys, place, monkeypatch):
    """`--layer` sets VERA_PLACEMENT_LAYER at parse time; the base stage must not see it and the variable must be back afterwards."""
    from verantyx import placement_layer as PL
    from verantyx.testimony_ledger import TestimonyLedger
    led = TestimonyLedger(tmp_path / 'l.jsonl')
    lp = str(tmp_path / 'user.sqlite')
    PL.write_entry(lp, led, base_sha256=None, word='太郎', type='PERSON', origin='layer_human', decided_by=['layer_human'], evidence={}, role_frame=None, key='k1')
    seen = []
    real = VS.fusion_turn

    def spy(messages, opts, cfg, max_tokens=None):
        import os
        seen.append(os.environ.get(PL.ENV_LAYER))
        return real(messages, opts, cfg, max_tokens)
    st = str(tmp_path / 'S.json')
    rc, _ = cli_run(capsys, '--store', st, 'serve', '--no-llm', '--document', place, '--layer', lp, '--port', '1')
    assert rc == 0
    f = fake_serve[0]['fusion']
    assert [s.name for s in f.tiers.stages] == ['base', 'layer']
    monkeypatch.setattr(VS, 'fusion_turn', spy)
    import os
    assert os.environ[PL.ENV_LAYER] == lp
    out = f.tiers.turn(msg('太郎は何を渡した？'), None, f)
    assert seen == [None, lp]                                  # the base stage ran with no layer, the layer stage with the layer
    assert os.environ[PL.ENV_LAYER] == lp                      # and the variable is back
    assert out['vera']['confidence_tiers']['counted'] in (1, 2)


def test_a_vocab_tier_file_that_does_not_exist_is_refused(tmp_path, fake_serve, capsys, place):
    """review r1 O2: `--tier vocab=<no such file>` is refused with a typed verdict, not recorded as `sha256: null`."""
    st = str(tmp_path / 'S.json')
    rc, outs = cli_run(capsys, '--store', st, 'serve', '--no-llm', '--document', place, '--tier', 'vocab=' + str(tmp_path / 'nope.sqlite'), '--port', '1')
    assert rc == 2 and outs[-1]['verdict'] == 'TIER_FILE_NOT_FOUND' and not fake_serve
    real = tmp_path / 'v.sqlite'
    real.write_bytes(b'x')
    rc, outs = cli_run(capsys, '--store', st, 'serve', '--no-llm', '--document', place, '--tier', 'vocab=' + str(real), '--port', '1')
    assert rc == 0 and len(fake_serve) == 1
