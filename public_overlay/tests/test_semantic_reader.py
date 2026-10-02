"""Independent small language oracles; not evidence of general NL coverage."""
from dataclasses import replace
import pytest
from verantyx.semantic_ir import Meter, View
from verantyx.semantic_reader import document_view, read_request
from verantyx.semantic_verify import Checker, Rejected
from verantyx.semantic_execute import Producer


def test_source_spans_and_clause_local_negation():
    raw='ユキはソラを助けなかった。ソラはミズを助けた。'
    v=document_view({'doc':raw});assert len(v.clauses)==2
    assert [(c.polarity,c.modality,c.time) for c in v.clauses]==[('-','assert','past'),('+','assert','past')]
    assert [dict((r.name,r.term) for r in c.roles) for c in v.clauses]==[
        {'agent':'ユキ','patient':'ソラ'},{'agent':'ソラ','patient':'ミズ'}]
    for c in v.clauses:
        assert all(s.valid({'doc':raw}) for s in [c.span,c.body_span,c.predicate_span,*(r.span for r in c.roles)])


def test_requests_distinguish_role_swaps_and_all_outputs():
    first=read_request('誰がソラに銅鍵を渡した？'); second=read_request('ソラが誰に銅鍵を渡した？')
    a=first.plans[0].nodes[0].pattern;b=second.plans[0].nodes[0].pattern
    assert dict(a.roles)['recipient']=='ソラ';assert dict(b.roles)['agent']=='ソラ'
    both=read_request('誰が誰に銅鍵を渡した？')
    assert len(both.plans[0].nodes[-1].outputs)==2
    assert {o.detail for o in both.obligations if o.kind=='role'}=={'agent','recipient','patient'}
    assert all(o.span.valid({'question':both.text}) for o in both.obligations)


@pytest.mark.parametrize('q',[
    '最後に誰が銅鍵を渡した？','ソラが来た場合、誰が窓を開ける？',
    '銅鍵を渡した人と受け取った人をそれぞれ教えて。','昨日誰が窓を開けた？',
])
def test_mandatory_scope_is_kept_as_unread(q):
    r=read_request(q);assert r.unread and not r.plans
    assert r.unread[0].span.text==q


def test_condition_source_and_unresolved_exception_retained():
    raw='ソラが来た場合、ユキが窓を開ける。'
    v=document_view({'doc':raw});c=v.clauses[0]
    assert c.conditions[0].predicate=='来る'
    assert c.condition_spans[0].text=='ソラが来た'
    assert c.condition_spans[0].valid(v.sources)
    v=document_view({'doc':'ユキが窓を開ける。ただし休日には開けない。'})
    assert v.clauses[0].unsupported


def test_independent_license_rejects_canonical_role_and_polarity_corruption():
    raw='ユキがソラに銅鍵を渡した。';v=document_view({'doc':raw});c=v.clauses[0]
    r=read_request('誰がソラに銅鍵を渡した？');p=r.plans[0]
    # Values remain verbatim but their grammatical roles are exchanged.
    roles=tuple(replace(role,name={'agent':'recipient','recipient':'agent'}.get(role.name,role.name)) for role in c.roles)
    for bad in (replace(c,roles=roles),replace(c,polarity='-'),replace(c,time='2099'),
                replace(c,predicate_span=c.roles[0].span),replace(c,modality='quote')):
        nv=View(v.sources,(bad,))
        with pytest.raises(Rejected):Checker(nv,'document',Meter())._source(bad)


def test_original_span_cannot_clip_a_condition_to_its_consequent():
    v=document_view({'doc':'ソラが来た場合、ユキが窓を開ける。'})
    c=v.clauses[0];bad=replace(c,span=c.body_span,conditions=(),condition_spans=())
    with pytest.raises(Rejected):Checker(View(v.sources,(bad,)),'document',Meter())._source(bad)


def test_quote_and_hypothetical_do_not_become_actual_assertions():
    for raw in ('ユキは「ソラが窓を開けた」と言った。','もしソラが来たなら、ユキが窓を開ける。'):
        v=document_view({'doc':raw})
        assert v.unread or all(c.modality!='assert' or c.conditions or c.unsupported for c in v.clauses)
