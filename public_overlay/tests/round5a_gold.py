"""Hand-authored symbolic axioms and requests, independent of the NL reader.

Expected answers live in the tests. This helper formats input/provenance only;
it does not infer an oracle with the producer or the reader.
"""
from dataclasses import replace
from decimal import Decimal
from verantyx.semantic_ir import (Clause, Meter, Obligation, Operator, Output, Pattern,
                                 Plan, Quantity, Request, Role, Span, Variable, View)
from verantyx.semantic_execute import Producer

X = Variable('x')


def fact(ident, predicate='open', actor='A', *, guard='', exception='', polarity='+', amount=None,
         family='document', sovereign='document'):
    body = f'{predicate}({actor})' + (f'={amount.amount}{amount.unit}' if amount else '')
    body += ' is false.' if polarity == '-' else '.'
    prefix = (f'When {guard}({actor}), ' if guard else f'Unless {exception}({actor}), ' if exception else '')
    raw = prefix+body; offset=len(prefix)
    span=lambda a,b: Span(ident,a,b,raw[a:b])
    roles=[Role('actor',actor,span(offset+len(predicate)+1,offset+len(predicate)+1+len(actor)))]
    if amount:
        a=raw.index('=',offset)+1; roles.append(Role('amount',amount,span(a,a+len(str(amount.amount))+len(amount.unit)),'quantity'))
    g=guard or exception; gp=Pattern(g,(('actor',actor),)) if g else None
    gs=span(5 if guard else 7, offset-2) if g else None
    c=Clause(ident,Variable('event_'+ident,'event'),predicate,span(offset,offset+len(predicate)),tuple(roles),span(0,len(raw)),
             body_span=span(offset,len(raw)),polarity=polarity,rule='record',family=family,sovereign=sovereign,
             conditions=(gp,) if guard else (),condition_spans=(gs,) if guard else (),
             exceptions=(gp,) if exception else (),exception_spans=(gs,) if exception else ())
    return raw,c


def view(*items):
    return View({c.span.source:raw for raw,c in items},tuple(c for _,c in items))


def request(nodes, outputs=None):
    nodes=list(nodes); outputs=outputs or (Output('actor',X,'answer'),)
    nodes[-1]=replace(nodes[-1],outputs=tuple(outputs),obligations=tuple(o.obligation for o in outputs))
    p=Plan(tuple(nodes),nodes[-1].id)
    raw='Return every requested output using the specified relations and constraints.'
    s=Span('question',0,len(raw),raw)
    obligations=tuple(Obligation(o.obligation,s,'output',p.root,o.label) for o in outputs)
    return Request(raw,(p,),obligations,(s,)),p


def simple(*, scoped=False, constant=False):
    nodes=[Operator('b','Bind',pattern=Pattern('open',(('actor','A' if constant else X),)))]
    if scoped:
        nodes.extend((Operator('c','ApplyCondition',inputs=('b',)),Operator('e','Except',inputs=('c',))))
    nodes.append(Operator('p','Project',inputs=(nodes[-1].id,)))
    return request(nodes,(Output('actor','A' if constant else X,'answer'),))


def produce(v,p):
    meter=Meter(); proposals,trace=Producer(v,'document',meter).run(p)
    return proposals,meter


def changed(proposals,predicate,fn):
    return [(a,replace(pr,nodes=tuple(fn(n) if predicate(n) else n for n in pr.nodes))) for a,pr in proposals]


def prune(proof):
    nodes={n.id:n for n in proof.nodes}; keep=set(); pending=[proof.root]
    while pending:
        k=pending.pop()
        if k not in keep: keep.add(k); pending.extend(nodes[k].parents)
    return replace(proof,nodes=tuple(n for n in proof.nodes if n.id in keep))
