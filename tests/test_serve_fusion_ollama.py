"""W10-f01: the real Ollama behind the entrance. Skipped with ENV_MISSING when Ollama or the model is not there (docs/FUSION.md)."""
import json
import urllib.request
from pathlib import Path

import pytest

from verantyx import decode_grammar as G
from verantyx import event_cross as EC
from verantyx import observe as O
from verantyx import vera_server as VS

MODEL = 'qwen3.8:27b-mlx'
URL = 'http://127.0.0.1:11434'


def _env_or_skip():
    try:
        with urllib.request.urlopen(URL + '/api/tags', timeout=3) as r:
            names = [m.get('name') for m in json.loads(r.read()).get('models', [])]
    except Exception as exc:
        pytest.skip('ENV_MISSING: Ollama is not reachable at %s (%s)' % (URL, type(exc).__name__))
    if MODEL not in names:
        pytest.skip('ENV_MISSING: model %s is not pulled (have: %s)' % (MODEL, ', '.join(names)))


@pytest.fixture
def cfg(tmp_path, monkeypatch):
    _env_or_skip()
    monkeypatch.delenv('VERA_PLACEMENT', raising=False)
    pl = Path(tmp_path) / 'pl.json'
    pl.write_text(json.dumps({'lemmas': {w: {'state': 'DECIDED', 'origin': 'direct', 'types': [t]} for w, t in
                                         {'太郎': 'PERSON', '花子': 'PERSON', '地図': 'ARTIFACT', '本': 'ARTIFACT'}.items()}, 'neighbors': {}}, ensure_ascii=False), encoding='utf-8')
    fp = O.FilePlacement.from_path(str(pl))
    monkeypatch.setattr(EC, 'default_lookup', lambda *a, **k: fp)
    d = Path(tmp_path) / 'd.txt'
    d.write_text('太郎が地図を渡した。\n花子は本を読んだ。\n', encoding='utf-8')

    def make(strict):
        return VS.FusionConfig.load(model=MODEL, documents=[str(d)], strict=strict, ollama_url=URL, timeout=180)
    return make


def test_real_strict_answer_is_inside_the_grammar_and_a_record(cfg):
    v = VS.fusion_turn([{'role': 'user', 'content': '誰が地図を渡した？'}], None, cfg(True))['vera']
    assert v['llm']['ok'] is True, v['llm']
    assert v['grammar_check']['in_grammar'] is True and v['outcome']['outcome'] == 'ANSWER_HUMAN_BASIS'
    assert v['provenance'][0]['sentence_kind'] == 'record'


def test_real_strict_does_not_call_the_llm_without_a_record(cfg):
    v = VS.fusion_turn([{'role': 'user', 'content': '太郎は何を買った？'}], None, cfg(True))['vera']
    assert v['llm']['called'] is False and v['reading']['type'] == 'NO_RECORD'


def test_real_default_marks_the_llm_answer_as_testimony(cfg):
    """Integration (auditor, 2026-10-06, W16-t3c K655): an anchored answer carries MARK_ANCHORED_TESTIMONY, any other
    testimony MARK_TESTIMONY. The real LLM may or may not be anchored, so the mark is checked against the verdict.
    Old expectation: always MARK_TESTIMONY."""
    res = VS.fusion_turn([{'role': 'user', 'content': '太郎は何を買った？'}], None, cfg(False))
    assert res['vera']['llm']['ok'] is True and res['vera']['outcome']['outcome'] == 'TESTIMONY'
    verdict = ((res['vera'].get('quote_check') or {}).get('verdict'))
    mark = G.MARK_ANCHORED_TESTIMONY if verdict == 'anchored' else G.MARK_TESTIMONY
    assert res['content'].startswith(mark), (verdict, res['content'][:80])
