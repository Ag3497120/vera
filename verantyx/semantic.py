"""Public Round5-A orchestration: only independently checked DAGs can answer."""
from __future__ import annotations

from .semantic_execute import Producer, Unresolved
from .semantic_ir import Budget, Limit, Meter, Quantity, data
from .semantic_validate import Invalid, request_shape
from .semantic_verify import Checker, Conflict, Rejected


def refusal(verdict, reason, *, phase, request=None, trace=(), meter=None):
    result = {'kind': 'unknown', 'verdict': verdict, 'text': 'この要求を裏づける導出を確認できません。',
              'reason': reason, 'phase': phase, 'values': [], 'evidence': [], 'sources': [],
              'trace': list(trace), 'semantic': {'version': 'round5a', 'verified': False}}
    if request is not None:
        result['semantic'].update(request=data(request), unread=data(request.unread))
    if meter is not None:
        result['semantic']['budget'] = {'limits': data(meter.budget), 'steps': meter.steps,
                                       'candidates': meter.candidates, 'peak_bindings': meter.peak_bindings}
    return result


def render(value):
    if isinstance(value, bool): return 'はい' if value else 'いいえ'
    return str(value)


def answer(request, views, *, budget=Budget(), trace=()):
    """Each view/sovereign is independent; the whole ask shares its step meter.

    Missing rows in one sovereign never receive bindings from another. Distinct
    verified answers remain a tie, regardless of evidence count or source order.
    """
    steps = list(trace); meter = Meter(budget); verified = {}; attempts = []
    if request.unread or not request.plans:
        return refusal('UNKNOWN_UNREAD', 'mandatory request spans remain unread', phase='reader',
                       request=request, trace=steps, meter=meter)
    try:
        if len(request.plans) > budget.parse: raise Limit('parse')
        for view in views:
            if view.invalid: raise Rejected('; '.join(view.invalid))
            unlicensed = [u for u in view.unread if u.reason != 'document instruction excluded']
            if unlicensed:
                result = refusal('UNKNOWN_UNSUPPORTED_EVIDENCE', 'source clauses remain unread', phase='reader',
                                 request=request, trace=steps, meter=meter)
                result['semantic']['source_unread'] = data(unlicensed)
                return result
            for sovereign in view.by_sovereign:
                for plan in request.plans:
                    request_shape(request, plan, budget)
                    before = meter.steps
                    proposals, execution = Producer(view, sovereign, meter).run(plan)
                    steps.append({'part': 'semantic_execute.Producer', 'status': 'ran', 'sovereign': sovereign,
                                  'steps': meter.steps-before, 'proposals': len(proposals), **execution})
                    checked = Checker(view, sovereign, meter).gate(request, plan, proposals)
                    steps.append({'part': 'semantic_verify.Checker.gate', 'status': 'ran', 'sovereign': sovereign,
                                  'verified_answers': len(checked), 'shared_steps': meter.steps})
                    attempts.append({'sovereign': sovereign, 'plan': plan.root, 'answers': len(checked)})
                    for claimed, (replayed, proof) in checked.items():
                        verified.setdefault(replayed, (proof, view, plan))
        if len(verified) > 1:
            out = refusal('AMBIGUOUS', 'distinct independently verified answers remain', phase='selection',
                          request=request, trace=steps, meter=meter)
            out['semantic']['alternatives'] = data(list(verified))
            out['semantic']['attempts'] = attempts
            return out
        if not verified:
            return refusal('UNKNOWN_NO_EVIDENCE', 'no complete supported derivation', phase='execution',
                           request=request, trace=steps, meter=meter)
        terms, (proof, view, plan) = next(iter(verified.items()))
        citations = {}; sources = []
        for n in proof.nodes:
            if n.op == 'Source' and n.clause.id not in citations:
                c = n.clause; citations[c.id] = c.span.text
                sources.append({'family': c.family, 'sovereign': c.sovereign, 'source': c.span.source,
                                'clause': c.id, 'text': c.span.text, 'span': data(c.span)})
        booleans = [v for _, v in terms if isinstance(v, bool)]
        by_id = {n.id:n for n in proof.nodes}
        queried_polarities = {by_id[n.parents[0]].clause.polarity for n in proof.nodes if n.op == 'Bind'}
        polarity = ('+' if booleans[0] else '-') if len(booleans) == 1 else (
            next(iter(queried_polarities)) if len(queried_polarities) == 1 else None)
        return {'kind': 'answer', 'verdict': 'ANSWER', 'text': '、'.join(f'{k}: {render(v)}' for k, v in terms),
                'values': [render(v) for _, v in terms], 'answer_values': data(terms),
                'polarity': polarity,
                'evidence': list(citations.values()), 'sources': sources, 'trace': steps,
                'semantic': {'version': 'round5a', 'verified': True, 'request': data(request),
                             'plan': data(plan), 'proof': data(proof), 'attempts': attempts,
                             'budget': {'limits': data(budget), 'steps': meter.steps, 'candidates': meter.candidates,
                                        'peak_bindings': meter.peak_bindings}}}
    except Limit as exc:
        return refusal('UNKNOWN_BUDGET', str(exc), phase='budget', request=request, trace=steps, meter=meter)
    except Conflict as exc:
        return refusal('CONFLICT', str(exc), phase='checker', request=request, trace=steps, meter=meter)
    except Unresolved as exc:
        verdict = 'CONFLICT' if exc.verdict == 'UNKNOWN_CONTRADICTION' else exc.verdict
        return refusal(verdict, str(exc), phase='producer', request=request, trace=steps, meter=meter)
    except (Invalid, Rejected) as exc:
        return refusal('UNKNOWN_INVALID_PROOF', str(exc), phase='checker', request=request, trace=steps, meter=meter)
