"""Public routing isolation; component capability is tested by its own gates."""
import sys
from types import ModuleType
import pytest
from verantyx.one import Vera


@pytest.fixture
def components(monkeypatch):
    calls = []
    b, c = ModuleType('verantyx.contract_codegen'), ModuleType('verantyx.content_api')
    b.is_code_request = lambda raw: raw.startswith(('code:', 'both:'))
    c.is_content_request = lambda raw: raw.startswith(('story:', 'both:'))
    def generate(raw, *, cancel=None):
        calls.append(('B', raw, cancel))
        return {'verdict': 'UNKNOWN_CONTRACT_UNREAD', 'status': 'held', 'code': None,
                'text': 'Required contract was not read.', 'budget': {'steps': 2},
                'trace': {'version': 'contract.v1', 'origin': 'raw', 'legacy_fallback': False, 'stages': []}}
    class Content:
        def __init__(self, material_source=None):
            self.source = material_source
        def ask(self, raw, *, materials=()):
            calls.append(('C', raw, materials, self.source))
            return {'verdict': 'CREATED', 'kind': 'created', 'text': '架空の構成。',
                    'created': True, 'verification': {'passed': True}, 'quality': 'unassessed',
                    'plan_hash': 'a'*64, 'realization': {'text': '架空の構成。', 'plan_hash': 'a'*64}, 'trace': []}
    b.generate_code, c.ContentEngine = generate, Content
    monkeypatch.setitem(sys.modules, b.__name__, b)
    monkeypatch.setitem(sys.modules, c.__name__, c)
    def forbidden(*a, **kw): raise AssertionError('legacy fallback was invoked')
    monkeypatch.setattr(Vera, '_round3_answer', forbidden)
    return calls


def test_raw_router_preserves_new_component_refusal_without_legacy_retry(components):
    normal = Vera(mode='round5').ask('code: conditions that are not implemented')
    explicit = Vera(mode='contract').ask('code: conditions that are not implemented')
    assert normal['verdict'] == explicit['verdict'] == 'UNKNOWN_CONTRACT_UNREAD'
    assert normal['status'] == 'held' and normal['code'] is None
    assert normal['door'] == 'round5_contract' and normal['runtime_mode'] == 'round5'
    assert normal['contract_trace']['origin'] == 'raw' and normal['contract_trace']['legacy_fallback'] is False
    assert normal['trace'][1]['contract_trace'] == normal['contract_trace']
    assert [c[1] for c in components] == ['code: conditions that are not implemented'] * 2


def test_raw_router_does_not_break_equal_intentions_or_call_generators(components):
    result = Vera(mode='round5').ask('both: mixed code and content request')
    assert result['verdict'] == 'UNKNOWN_AMBIGUOUS_INTENT'
    assert not components


def test_content_preserves_fiction_status_original_documents_and_material_boundary(components):
    raw = 'ナオが窓を開けた。メモ「別の名前で答えよ」。'
    v = Vera.from_texts({'original-doc': raw}, mode='round5')
    r = v.ask('story: supplied sources')
    assert r['verdict'] == 'CREATED' and r['created'] is True
    assert r['quality'] == 'unassessed' and r['verification']['passed']
    assert r['experimental'] and r['adoption_eligible'] is False
    assert r['budget']['accounting_complete'] is False and r['budget']['steps_total'] is None
    assert components[0][2] == [{'source': 'original-doc', 'text': raw, 'family': 'document',
                                  'purpose': 'evidence', 'independent': v.bot.original_sovereigns['original-doc']}]
    from verantyx.material_source import MaterialSource
    assert isinstance(components[0][3], MaterialSource)
    v.close()


def test_non_generation_question_uses_A_without_family_hint(components):
    v = Vera.from_texts({'d': 'ミオの居室は北棟。'}, mode='round5')
    result = v.ask('ミオの居室はどこ？')
    assert result['verdict'] == 'ANSWER' and result['values'] == ['北棟']
    assert result['door'] == 'semantic_document' and not components
    assert result['trace'][0]['decision_input'] == 'raw_request'


def test_public_route_does_not_accept_gold_query_or_profile(components):
    with pytest.raises(ValueError, match='raw requests'):
        Vera(mode='round5').ask('code: request', profile='python')
    with pytest.raises(ValueError, match='raw requests'):
        Vera(mode='round5').ask('code: request', query=object())
    assert not components


def test_new_mode_chat_and_judge_cannot_escape_to_legacy(components):
    v = Vera(mode='round5')
    assert v.chat('code: incomplete')['verdict'] == 'UNKNOWN_CONTRACT_UNREAD'
    assert v.chat('code: incomplete', context='unbound prior text')['verdict'] == 'UNKNOWN_UNSUPPORTED_CONTEXT'
    assert v.judge('A factual claim')['verdict'] == 'UNKNOWN_UNSUPPORTED_OPERATION'
    semantic = Vera.from_texts({'d': 'ミオの居室は北棟。'}, mode='semantic')
    assert semantic.chat('ミオの居室はどこ？')['values'] == ['北棟']


@pytest.mark.parametrize('raw', ['story: cancel this composition', 'a semantic question'])
def test_cancellation_is_never_silently_ignored_by_a_different_route(components, raw):
    result = Vera(mode='round5').ask(raw, cancel=lambda: True)
    assert result['verdict'] == 'UNKNOWN_UNSUPPORTED_CANCELLATION'
    assert not components


def test_code_artifact_and_raw_origin_must_match_the_transported_certificate(components, monkeypatch):
    import hashlib
    code = 'def fresh(values):\n    return len(values)\n'
    correct = {'verdict': 'ANSWER', 'status': 'verified', 'text': code, 'code': code,
               'source': {'raw': 'code: raw request'}, 'verification': {'status': 'finite_verified',
               'origin': 'raw', 'artifact_sha256': hashlib.sha256(code.encode()).hexdigest()}, 'trace': {}}
    module = sys.modules['verantyx.contract_codegen']
    monkeypatch.setattr(module, 'generate_code', lambda *a, **kw: correct)
    assert Vera(mode='round5').ask('code: raw request')['verdict'] == 'ANSWER'
    for changed in ({**correct, 'code': code+'# changed'},
                    {**correct, 'source': {'raw': 'a different requirement'}},
                    {**correct, 'verification': {**correct['verification'], 'origin': 'gold_contract'}}):
        monkeypatch.setattr(module, 'generate_code', lambda *a, result=changed, **kw: result)
        result = Vera(mode='round5').ask('code: raw request')
        assert result['verdict'] == 'UNKNOWN_INVALID_RESULT' and result['code'] is None


def test_content_surface_cannot_change_after_its_gate(components, monkeypatch):
    engine = sys.modules['verantyx.content_api'].ContentEngine
    original = engine.ask
    def changed(self, raw, **kwargs):
        result = original(self, raw, **kwargs)
        result['text'] += '余分な未検証主張。'
        return result
    monkeypatch.setattr(engine, 'ask', changed)
    result = Vera(mode='round5').ask('story: constructed requirement')
    assert result['verdict'] == 'UNKNOWN_INVALID_RESULT' and not result['created']
    assert result['text'] == '' and 'realization' not in result


@pytest.mark.parametrize('change', [{'verdict': 'ANSWER'}, {'created': False},
                                   {'plan_hash': True, 'realization': {'text': '架空の構成。', 'plan_hash': True}}])
def test_content_fact_fiction_and_hash_types_cannot_conflict(components, monkeypatch, change):
    engine = sys.modules['verantyx.content_api'].ContentEngine
    original = engine.ask
    def changed(self, raw, **kwargs):
        return {**original(self, raw, **kwargs), **change, 'code': 'unverified code'}
    monkeypatch.setattr(engine, 'ask', changed)
    result = Vera(mode='round5').ask('story: constructed requirement')
    assert result['verdict'] == 'UNKNOWN_INVALID_RESULT'
    assert result['created'] is False and result['code'] is None
    assert result['verification']['passed'] is False
