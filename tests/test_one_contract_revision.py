"""Raw r2 SQL intent reaches the ordinary one router without a gold mode.

Generator is a transport stub; these are not OS execution or capability scores.
"""
import pytest
from verantyx import contract_codegen
from verantyx.one import Vera


def sql_request(column):
    return (f'SQLite query inputs entries columns {column}; table entries: '
            'Relation[Record{ord:Int[1..16], value:Int[-4..4]}], length 0..6, '
            'ordinal ord; finally return sum entries.value')


@pytest.mark.parametrize('column', ['what', 'how', 'why'])
def test_real_sql_intent_routes_original_request_and_retains_r2_accounting(monkeypatch, column):
    raw = sql_request(column)
    received = []
    budget = {'stop': {'code': 'REQUEST_TIMEOUT', 'phase': 'execution'},
              'resource_usage': {'child_output_bytes': {'actual_total': 12, 'reserved_total': 14}}}
    def generate(text, *, cancel=None):
        received.append(text)
        return {'verdict': 'REQUEST_TIMEOUT', 'status': 'held', 'code': None,
                'text': 'request stopped', 'budget': budget,
                'trace': {'origin': 'raw', 'development_revision': 'r2', 'legacy_fallback': False}}
    monkeypatch.setattr(contract_codegen, 'generate_code', generate)
    result = Vera(mode='round5').ask(raw)
    assert received == [raw]
    assert result['door'] == 'round5_contract' and result['code'] is None
    assert result['verdict'] == 'REQUEST_TIMEOUT' and result['budget'] == budget
    assert result['contract_trace']['development_revision'] == 'r2'


@pytest.mark.parametrize('wrap', [lambda raw: '引用:「' + raw + '」',
                                  lambda raw: raw + '; Explain this query'])
def test_quoted_or_explanatory_sql_does_not_call_codegen(monkeypatch, wrap):
    def forbidden(*args, **kwargs):
        raise AssertionError('explanation or quote routed as code generation')
    monkeypatch.setattr(contract_codegen, 'generate_code', forbidden)
    result = Vera(mode='round5').ask(wrap(sql_request('total')))
    assert result['door'] == 'semantic_qa'
