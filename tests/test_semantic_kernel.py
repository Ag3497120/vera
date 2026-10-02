"""Gold IR, broken DAGs and order/budget properties, separate from NL accuracy."""
from dataclasses import replace
from decimal import Decimal, localcontext
from itertools import permutations
import pytest

from round5a_gold import X, changed, fact, produce, prune, request, simple, view
from verantyx.semantic_ir import (Budget, EventValue, Limit, Meter, Nominal, Operator, Output,
                                 Pattern, Quantity, Test as PredicateTest, Unread, Variable, View)
from verantyx.semantic_execute import Producer, Unresolved
from verantyx.semantic_validate import Invalid, plan_shape
from verantyx.semantic_verify import Checker, Conflict, Rejected


def gate(v,r,p,props,meter=None):
    return Checker(v,'document',meter or Meter()).gate(r,p,props)


def test_gold_and_same_meter():
    r,p=simple();v=view(fact('f'));props,m=produce(v,p); before=m.steps
    assert list(gate(v,r,p,props,m))==[(('actor','A'),)]
    assert m.steps>before


SOURCE_MUTATIONS=[
    lambda c: replace(c,span=replace(c.span,text='FORGED SOURCE TEXT')),
    lambda c: replace(c,span=replace(c.span,start=1)),
    lambda c: replace(c,span=replace(c.span,end=c.span.end-1)),
    lambda c: replace(c,span=replace(c.span,source='absent')),
    lambda c: replace(c,predicate_span=replace(c.predicate_span,start=999,end=1003)),
    lambda c: replace(c,family='other'),lambda c: replace(c,sovereign='other'),
    lambda c: replace(c,time='invented-time'),lambda c: replace(c,modality='quote'),
    lambda c: replace(c,polarity='-'),lambda c: replace(c,id='new'),
    lambda c: replace(c,roles=(replace(c.roles[0],term='B'),)),
]


@pytest.mark.parametrize('mutation',SOURCE_MUTATIONS)
def test_source_changes_rejected_after_audit_cache(mutation):
    r,p=simple();v=view(fact('f'));props,_=produce(v,p)
    broken=changed(props,lambda n:n.op=='Source',lambda n:replace(n,clause=mutation(n.clause)))
    with pytest.raises(Invalid): gate(v,r,p,broken)
    with pytest.raises(Invalid): Checker(v,'document',Meter()).proof(r,p,broken[0][1])


@pytest.mark.parametrize('scope',['guard','exception'])
def test_canonical_scope_cannot_erase_original(scope):
    item=fact('f',**{scope:'key'})
    c=replace(item[1],conditions=(),condition_spans=(),exceptions=(),exception_spans=())
    v=View({'f':item[0]},(c,));r,p=simple();props,_=produce(v,p)
    with pytest.raises(Rejected): gate(v,r,p,props)
    # Clipping full span to the body also cannot remove the original guard.
    c=replace(c,span=c.body_span);v=View({'f':item[0]},(c,));props,_=produce(v,p)
    with pytest.raises(Rejected): gate(v,r,p,props)


@pytest.mark.parametrize('mutation',[
    lambda c:replace(c,predicate_span=c.roles[0].span),lambda c:replace(c,time='2099'),
    lambda c:replace(c,roles=(*c.roles,c.roles[0])),
])
def test_canonical_licensing_is_more_than_identity(mutation):
    raw,c=fact('f');c=mutation(c);v=View({'f':raw},(c,));r,p=simple()
    with pytest.raises((Invalid,Unresolved)): props,_=produce(v,p);gate(v,r,p,props)


def test_conditions_missing_negative_and_conflicting():
    r,p=simple(scoped=True); rule=fact('r',guard='key');key=fact('k','key');negative=fact('nk','key',polarity='-')
    good=view(rule,key);props,_=produce(good,p);assert list(gate(good,r,p,props))==[(('actor','A'),)]
    for v in (view(rule),view(rule,negative)):
        with pytest.raises(Invalid): gate(v,r,p,props)
    with pytest.raises(Conflict): gate(view(rule,key,negative),r,p,props)
    for order in permutations((rule,key,negative)):
        with pytest.raises(Unresolved) as e: produce(view(*order),p)
        assert e.value.verdict=='UNKNOWN_CONTRADICTION'


def test_exception_is_open_world():
    r,p=simple(scoped=True);rule=fact('r',exception='blocked');negative=fact('nb','blocked',polarity='-')
    v=view(rule,negative);props,_=produce(v,p);assert list(gate(v,r,p,props))==[(('actor','A'),)]
    with pytest.raises(Invalid): gate(view(rule),r,p,props)
    with pytest.raises(Invalid): gate(view(rule,negative,fact('b','blocked')),r,p,props)


def test_undischarged_raw_guard_source_cannot_replace_witness():
    r,p=simple(scoped=True,constant=True)
    opening=fact('o',guard='p');guard=fact('g','p',guard='q');q=fact('q','q')
    v=view(opening,guard,q);props,_=produce(v,p);assert gate(v,r,p,props)
    source=next(n.id for n in props[0][1].nodes if n.op=='Source' and n.clause.id=='g')
    broken=changed(props,lambda n:n.op=='ApplyCondition',lambda n:replace(n,parents=(n.parents[0],source)))
    broken=[(a,prune(pr)) for a,pr in broken]
    with pytest.raises(Invalid): gate(v,r,p,broken)
    with pytest.raises(Invalid): Checker(view(opening,guard),'document',Meter()).proof(r,p,broken[0][1])


def test_alternative_condition_proofs_and_cycles_are_order_invariant():
    r,p=simple(scoped=True)
    facts=(fact('o',guard='p'),fact('p','p',guard='q'),fact('q','q',guard='p'),fact('direct','p'))
    for order in permutations(facts):
        v=view(*order);props,m=produce(v,p);assert list(gate(v,r,p,props,m))==[(('actor','A'),)]
    with pytest.raises(Unresolved): produce(view(*facts[:3]),p)
    # Same binding, different scopes: one unresolved rule cannot hide a fact.
    for order in permutations((fact('guarded',guard='absent'),fact('direct'))):
        v=view(*order);props,m=produce(v,p);assert list(gate(v,r,p,props,m))==[(('actor','A'),)]


def test_opponent_outside_submitted_proof():
    r,p=simple();base=fact('base');v=view(base);props,_=produce(v,p)
    for opponent in (fact('neg',polarity='-'),fact('neg',guard='key',polarity='-')):
        with pytest.raises(Conflict): gate(view(base,opponent,fact('key','key')),r,p,props)


def test_join_inherits_right_scope_and_shared_entity():
    nodes=(Operator('l','Bind',pattern=Pattern('left',(('actor',X),))),Operator('r','Bind',pattern=Pattern('right',(('actor',X),))),
           Operator('j','Join',inputs=('l','r')),Operator('c','ApplyCondition',inputs=('j',)),
           Operator('e','Except',inputs=('c',)),Operator('p','Project',inputs=('e',)))
    r,p=request(nodes);l=fact('l','left');rr=fact('r','right',guard='key')
    with pytest.raises(Unresolved): produce(view(l,rr),p)
    v=view(l,rr,fact('key','key'));props,m=produce(v,p);assert list(gate(v,r,p,props,m))==[(('actor','A'),)]
    assert produce(view(l,fact('r','right','B')),p)[0]==[]


def test_distinct_answers_and_claim_proof_correspondence():
    r,p=simple();v=view(fact('a',actor='A'),fact('b',actor='B'));props,_=produce(v,p)
    assert set(gate(v,r,p,props))=={(('actor','A'),),(('actor','B'),)}
    with pytest.raises(Invalid): gate(v,r,p,props[:1])
    with pytest.raises(Invalid): gate(v,r,p,[(props[0][0],props[1][1]),(props[1][0],props[0][1])])
    # Duplicate answer cannot shelter a corrupted duplicate proof.
    bad=changed([props[0]],lambda n:n.op=='Source',lambda n:replace(n,clause=replace(n.clause,time='invented')))
    with pytest.raises(Invalid): gate(v,r,p,[*props,*bad])


@pytest.mark.parametrize('edit',[
    lambda n:replace(n,bindings=(('x','B'),)),lambda n:replace(n,covers=()),
    lambda n:replace(n,covers=(*n.covers,'invented')),lambda n:replace(n,answer=(('actor','B'),)),
    lambda n:replace(n,op='Filter'),lambda n:replace(n,plan_node='b'),lambda n:replace(n,parents=()),
])
def test_binding_project_obligation_mutations(edit):
    r,p=simple();v=view(fact('f'));props,_=produce(v,p)
    with pytest.raises(Invalid): gate(v,r,p,changed(props,lambda n:n.op=='Project',edit))


@pytest.mark.parametrize('edit',[
    lambda r:replace(r,obligations=()),
    lambda r:replace(r,obligations=(*r.obligations,replace(r.obligations[0],id='extra'))),
    lambda r:replace(r,obligations=(replace(r.obligations[0],node='b'),)),
    lambda r:replace(r,obligations=(replace(r.obligations[0],span=replace(r.obligations[0].span,start=1)),)),
    lambda r:replace(r,unread=(Unread(r.covered[0],'mandatory scope'),)),
    lambda r:replace(r,covered=()),
    lambda r:replace(r,obligations=(replace(r.obligations[0],span=replace(r.obligations[0].span,end=6,text=r.text[:6])),)),
])
def test_fixed_request_cannot_hide_unread_or_missing_obligation(edit):
    r,p=simple();v=view(fact('f'));props,_=produce(v,p)
    with pytest.raises(Invalid): gate(v,edit(r),p,props)


@pytest.mark.parametrize('edit',[
    lambda pr:replace(pr,nodes=(*pr.nodes,pr.nodes[-1])),lambda pr:replace(pr,root=pr.nodes[0].id),
    lambda pr:replace(pr,nodes=(replace(pr.nodes[0],parents=(pr.root,)),*pr.nodes[1:])),
    lambda pr:replace(pr,nodes=pr.nodes[1:]),lambda pr:replace(pr,sovereign='other'),
])
def test_broken_dag(edit):
    r,p=simple();v=view(fact('f'));props,_=produce(v,p)
    with pytest.raises(Invalid): gate(v,r,p,[(props[0][0],edit(props[0][1]))])


@pytest.mark.parametrize('reverse',[False,True])
@pytest.mark.parametrize('context',['output','filter','arithmetic','nominal','event'])
def test_all_variable_occurrences_checked_before_reduction(reverse,context):
    q=Variable('x','quantity');e=Variable('x','entity'); terms=[q,e]
    if reverse: terms.reverse()
    b=Operator('b','Bind',pattern=Pattern('open',(('actor',X),)))
    if context=='output': nodes=(b,Operator('p','Project',inputs=('b',),outputs=(Output('a',terms[0],'a'),Output('b',terms[1],'b'))))
    elif context=='filter': nodes=(b,Operator('f','Filter',inputs=('b',),tests=(PredicateTest(terms[0],'=',terms[1]),)),Operator('p','Project',inputs=('f',),outputs=(Output('a',X,'a'),)))
    elif context=='arithmetic': nodes=(b,Operator('a','Sum',inputs=('b',),terms=tuple(terms),target=Variable('z','quantity')),Operator('p','Project',inputs=('a',),outputs=(Output('a',X,'a'),)))
    elif context=='nominal': nodes=(replace(b,pattern=Pattern('open',(('actor',Nominal('人',terms[0])),('other',terms[1])))),Operator('p','Project',inputs=('b',),outputs=(Output('a',X,'a'),)))
    else: nodes=(replace(b,pattern=Pattern('open',(('actor',X),),event=e)),Operator('p','Project',inputs=('b',),outputs=(Output('a',X,'a'),)))
    with pytest.raises(Invalid): plan_shape(type(simple()[1])(nodes,'p'))


def test_event_sort_and_entity_time_identity():
    ev=Variable('ev','event'); b=Operator('b','Bind',pattern=Pattern('open',(('actor','A'),),event=ev))
    r,p=request((b,Operator('p','Project',inputs=('b',))),(Output('event',ev,'event'),))
    v=view(fact('f'));props,m=produce(v,p)
    assert list(gate(v,r,p,props,m))==[(('event',EventValue('document','document','event_f','')),)]
    with pytest.raises(Unresolved): produce(v,replace(p,nodes=(replace(b,pattern=replace(b.pattern,event=Variable('ev','entity'))),p.nodes[1])))
    # One shared event cannot splice two independent event identities.
    r,p=request((b,replace(b,id='r'),Operator('j','Join',inputs=('b','r')),Operator('p','Project',inputs=('j',))),(Output('event',ev,'event'),))
    # Both branches can reuse f; fabricated env changes are rejected by replay.
    props,_=produce(v,p);bad=changed(props,lambda n:n.op=='Join',lambda n:replace(n,bindings=(('ev',EventValue('document','document','different','')),)))
    with pytest.raises(Invalid):gate(v,r,p,bad)


def arithmetic(op='Sum',**kwargs):
    a=Variable('a','quantity');b=Variable('b','quantity');z=Variable('z','value' if op=='Compare' else 'quantity')
    nodes=(Operator('a','Bind',pattern=Pattern('mass',(('actor','A'),('amount',a)))),
           Operator('b','Bind',pattern=Pattern('mass',(('actor','B'),('amount',b)))),
           Operator('j','Join',inputs=('a','b')),Operator('calc',op,inputs=('j',),terms=(a,b),target=z,**kwargs),Operator('p','Project',inputs=('calc',)))
    return request(nodes,(Output('result',z,'answer'),))


@pytest.mark.parametrize('precision',[12,28,64])
def test_exact_arithmetic_under_ambient_context(precision):
    with localcontext() as ctx:
        ctx.prec=precision
        qa=Quantity(Decimal('1.00000000000000000000000000001'),'g');qb=Quantity(Decimal('1.00000000000000000000000000002'),'g')
        v=view(fact('a','mass','A',amount=qa),fact('b','mass','B',amount=qb));r,p=arithmetic('Compare',relation='>')
        props,m=produce(v,p);assert list(gate(v,r,p,props,m))==[(('result',False),)]
        assert str(qa)=='1.00000000000000000000000000001g'
        r,p=arithmetic('Difference',unit='g');props,m=produce(v,p)
        assert list(gate(v,r,p,props,m))==[(('result',Quantity(Decimal('-0.00000000000000000000000000001'),'g')),)]


@pytest.mark.parametrize('mutation',[
    lambda q:Quantity(q.amount+1,q.unit),lambda q:Quantity(q.amount,'kg'),lambda q:'12g',
])
def test_arithmetic_replay_mutations(mutation):
    v=view(fact('a','mass','A',amount=Quantity(Decimal(5),'g')),fact('b','mass','B',amount=Quantity(Decimal(7),'g')))
    r,p=arithmetic(unit='g');props,m=produce(v,p);assert list(gate(v,r,p,props,m))==[(('result',Quantity(Decimal(12),'g')),)]
    bad=changed(props,lambda n:n.op=='Sum',lambda n:replace(n,bindings=tuple((k,mutation(v) if k=='z' else v) for k,v in n.bindings)))
    with pytest.raises(Invalid):gate(v,r,p,bad)


def test_checker_does_not_use_producer_matching_or_arithmetic(monkeypatch):
    import verantyx.semantic_execute as execution
    v=view(fact('a','mass','A',amount=Quantity(Decimal(5),'g')),fact('b','mass','B',amount=Quantity(Decimal(7),'g')))
    r,p=arithmetic(unit='g');props,_=produce(v,p)
    def poisoned(*args,**kwargs):raise AssertionError('producer helper used by checker')
    for name in ('bind','_quantity','_rational','_get','_test','_decimal'):monkeypatch.setattr(execution,name,poisoned)
    assert list(gate(v,r,p,props))==[(('result',Quantity(Decimal(12),'g')),)]


@pytest.mark.parametrize('bad',[Quantity(7,'g'),Quantity(Decimal('NaN'),'g'),Quantity(Decimal('Infinity'),'g'),
                               Quantity(Decimal('1e-257'),'g'),Quantity(Decimal('1'),[])])
def test_invalid_quantity_literals_refuse(bad):
    r,p=simple();p=replace(p,nodes=(p.nodes[0],replace(p.nodes[1],outputs=(Output('q',bad,'answer'),))))
    with pytest.raises(Unresolved):produce(view(fact('f')),p)


def test_fixed_budget_bounds():
    r,p=simple();v=view(fact('f'));props,_=produce(v,p)
    assert gate(v,replace(r,plans=(p,)*32),p,props)
    with pytest.raises(Limit):gate(v,replace(r,plans=(p,)*33),p,props)
    assert Producer(view(*(fact('f'+str(i)) for i in range(256))),'document',Meter())._setup(p) is None
    with pytest.raises(Limit): Producer(view(*(fact('f'+str(i)) for i in range(257))),'document',Meter()).run(p)
    with pytest.raises(Limit):produce(view(*(fact('f'+str(i),actor='A'+str(i)) for i in range(65))),p)
    vv=view(*(fact('f'+str(i),actor='A'+str(i)) for i in range(64)))
    pp,mm=produce(vv,p);assert len(gate(vv,r,p,pp,mm))==64
    m=Meter();m.steps=4090
    with pytest.raises(Limit):gate(v,r,p,props,m)
    assert m.steps>4096
    for filters,valid in ((5,True),(6,False)):
        nodes=[p.nodes[0]]
        for i in range(filters): nodes.append(Operator('f'+str(i),'Filter',inputs=(nodes[-1].id,),tests=(PredicateTest(X,'=','A'),)))
        rr,pp=request((*nodes,Operator('p','Project',inputs=(nodes[-1].id,))))
        if valid:
            pr,mm=produce(v,pp);assert gate(v,rr,pp,pr,mm)
        else:
            with pytest.raises(Limit):produce(v,pp)
