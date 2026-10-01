"""Independent proof replay, source licensing, and evidence-universe audit.

This module never imports the producer or its matcher/arithmetic helpers.
The audit also detects applicable opponents and omitted alternative answers.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal, Inexact, localcontext
from fractions import Fraction
from typing import Any

from .semantic_coord import chunk, coordination_ok, own_subject_phrase, topic_phrase, tag
from .semantic_names import is_past_aux, name_split_in, tokens_covering
from .semantic_ir import (Clause, EventValue, Limit, Meter, Nominal, Pattern,
                          Plan, Proof, ProofNode, Quantity, Request, Variable, View, typed, unit_type)
from .semantic_validate import Invalid, occurrences, request_shape


class Rejected(Invalid):
    pass


class Conflict(Rejected):
    pass


def _number(q, unit):
    """Independent scaled rational arithmetic; no ambient Decimal context."""
    if not typed(q, "quantity"):
        raise Rejected("non-finite/non-quantity operand")
    d1, f1 = unit_type(q.unit); d2, f2 = unit_type(unit)
    if d1 != d2:
        raise Rejected("incompatible units")
    # Build rational from the integer coefficient and decimal exponent.
    def ratio(d):
        sign, digits, exp = d.as_tuple(); n = int(''.join(map(str, digits)) or '0')
        if sign: n = -n
        if abs(exp) > 256: raise Rejected("quantity exponent outside exact contract")
        return (n * 10 ** exp, 1) if exp >= 0 else (n, 10 ** -exp)
    n, d = ratio(q.amount); fn, fd = ratio(f1); gn, gd = ratio(f2)
    return Fraction(n * fn * gd, d * fd * gn)


def _finite(r):
    # A finite decimal's denominator contains only 2 and 5, independently
    # checked before constructing the exact coefficient.
    denominator = r.denominator; twos = fives = 0
    while denominator % 2 == 0: denominator //= 2; twos += 1
    while denominator % 5 == 0: denominator //= 5; fives += 1
    if denominator != 1: raise Rejected("non-terminating unit conversion")
    places = max(twos, fives)
    coefficient = r.numerator * 2 ** (places - twos) * 5 ** (places - fives)
    digits = tuple(map(int, str(abs(coefficient))))
    if len(digits) > 128 or places > 256: raise Rejected("exact result exceeds precision contract")
    return Decimal((1 if coefficient < 0 else 0, digits, -places))


def _operand(term, env):
    if isinstance(term, Variable):
        if term.name not in env or not typed(env[term.name], term.sort):
            raise Rejected("unbound/ill-typed operand")
        return env[term.name]
    return term


def _test(a, relation, b):
    if isinstance(a, Quantity) or isinstance(b, Quantity):
        if not isinstance(a, Quantity) or not isinstance(b, Quantity): raise Rejected("comparison type")
        a, b = _number(a, a.unit), _number(b, a.unit)
    elif relation not in ('=', '!='):
        raise Rejected("ordered non-quantity comparison")
    return {'=': lambda: a == b, '!=': lambda: a != b, '>': lambda: a > b,
            '<': lambda: a < b, '>=': lambda: a >= b, '<=': lambda: a <= b}[relation]()


def _calc(op, env):
    env = dict(env); answer = ()
    if op.op == 'Filter':
        if not all(_test(_operand(t.left, env), t.relation, _operand(t.right, env)) for t in op.tests):
            return None
    elif op.op in ('Sum', 'Difference'):
        values = [_operand(t, env) for t in op.terms]; unit = op.unit or values[0].unit
        values = [_number(v, unit) for v in values]
        amount = sum(values, Fraction(0)) if op.op == 'Sum' else values[0] - values[1]
        env[op.target.name] = Quantity(_finite(abs(amount) if op.absolute else amount), unit)
    elif op.op == 'Compare':
        a, b = [_operand(t, env) for t in op.terms]
        value = _test(a, op.relation, b)
        if op.choices:
            if _test(a, '=', b): raise Rejected("comparison tie")
            value = _operand(op.choices[0 if value else 1], env)
        env[op.target.name] = value
    elif op.op == 'Project':
        answer = tuple((o.label, Quantity(_finite(_number(_operand(o.term, env), o.unit)), o.unit)
                        if o.unit else _operand(o.term, env)) for o in op.outputs)
    if op.target and not typed(env[op.target.name], op.target.sort): raise Rejected("result sort")
    return env, answer


def _match(pattern, clause, seed=None, opposite=False):
    if pattern.predicate not in ('*', clause.predicate): return None
    if pattern.modality == 'normative':
        if clause.modality not in ('permission', 'prohibition'): return None
    elif pattern.modality != clause.modality: return None
    pol = ('-' if pattern.polarity == '+' else '+') if opposite else pattern.polarity
    if pol != '*' and pol != clause.polarity: return None
    if pattern.time and pattern.time != clause.time: return None
    actual = {r.name: r.term for r in clause.roles}
    if len(actual) != len(clause.roles): raise Rejected("duplicate source role")
    env = dict(seed or {})
    terms = list(pattern.roles)
    if pattern.event is not None:
        terms.append(('$event', pattern.event))
        actual['$event'] = EventValue(clause.sovereign, clause.family, clause.event.name, clause.time)
    for role, wanted in terms:
        if role not in actual: return None
        value = actual[role]
        if isinstance(wanted, Nominal):
            from .typed_edges import _tagger
            nouns = [w.surface for w in _tagger()(value) if w.feature.pos1 in ('名詞', '接尾辞')] if isinstance(value, str) else []
            if not nouns or nouns[-1] != wanted.head: return None
            wanted = wanted.term
        if isinstance(wanted, Variable):
            if not typed(value, wanted.sort): return None
            if wanted.name in env and env[wanted.name] != value: return None
            env[wanted.name] = value
        elif wanted != value: return None
    return env


def _attribute(text):
    from .typed_edges import _tagger, _base
    words = list(_tagger()(text))
    if len(words) == 2 and words[0].feature.pos1 == '形容詞' and words[1].surface == 'さ':
        return 'nominal:' + _base(words[0])
    return text


def _role_split(value, roles, name, raw, body, words, positions):
    """Validated (descriptor, name) split of a Frame role value, using the sentence's own tokens."""
    role = next((r for r in roles if r.name == name), None)
    if role is None: return None
    tagged = [(w.surface, w.feature.pos1, w.feature.pos2, at, at + len(w.surface)) for w, at in zip(words, positions)]
    start = 0
    while True:
        at = raw.find(value, start)
        if at < 0: return None
        split = name_split_in(tokens_covering(tagged, at, at + len(value)), value)
        if split and role.span.text == split[1] and role.span.start - body.start == at + len(split[0]):
            return split
        start = at + 1


def _literal(role):
    if isinstance(role.term, Quantity):
        m = re.fullmatch(r'([+-]?[0-9]+(?:\.[0-9]+)?)\s*([^0-9\s]+)', role.span.text)
        return bool(m and Decimal(m[1]) == role.term.amount and m[2] == role.term.unit and typed(role.term, 'quantity'))
    if role.rule == 'nominal': return role.term == _attribute(role.span.text)
    if role.rule == 'frame':
        from .frames import canonical
        return role.term == canonical(role.span.text)
    return role.term == role.span.text


def _ranges(raw):
    """Independent original-sentence boundaries, including quoted punctuation."""
    opened = []; begin = 0; spans = set()
    for match in re.finditer(r'[。！？\n「」『』]', raw):
        mark = match[0]
        if mark in ('「','『'): opened.append(mark)
        elif mark in ('」','』'):
            if not opened or opened.pop() != ('「' if mark == '」' else '『'):
                raise Rejected('unbalanced source quotation')
        elif not opened:
            end = match.end()
            if raw[begin:end].strip(): spans.add((begin,end))
            begin = end
    if opened: raise Rejected('unclosed source quotation')
    if raw[begin:].strip(): spans.add((begin,len(raw)))
    return spans


def _native_guard_scope(clause, body):
    """Bind an antecedent to its entire original prefix, not any valid span."""
    raw = clause.span.text
    left = len(raw) - len(raw.lstrip())
    # Independently reject unrepresented prefix scope. A producer cannot
    # turn a hypothesis, correction or rule heading into an asserted fact by
    # moving body_span to the text after a colon.
    colon_positions = [m.start() + clause.span.start for m in re.finditer('[:：]', raw)]
    if colon_positions:
        value = next((r for r in clause.roles if r.name == 'value'), None)
        if (clause.rule not in ('copula', 'identity') or value is None
                or re.fullmatch(r'[0-9]+(?:[:：][0-9]+)+', value.span.text) is None
                or any(not value.span.start <= at < value.span.end for at in colon_positions)):
            raise Rejected('uninterpreted colon scope')
    while left < len(raw) and raw[left] in ' 、,': left += 1
    antecedent = re.match(r'^(.*?)(場合(?:は|には|に)?|ならば|(?<!な)(?<!けれ)なら(?!な)|(?<!なけ)れば|ときは|時は|際は|際には)[、,]?', raw[left:])
    if antecedent and antecedent[1].strip():
        expected_start = clause.span.start + left
        expected_end = expected_start + len(antecedent[1])
        expected_body = expected_start + antecedent.end()
        if len(clause.conditions) != 1 or len(clause.condition_spans) != 1:
            raise Rejected('missing or duplicate source condition')
        guard = clause.condition_spans[0]
        if (guard.start, guard.end, guard.text) != (expected_start, expected_end, antecedent[1]):
            raise Rejected('condition full-prefix scope')
    else:
        expected_body = clause.span.start + left
        if clause.conditions or clause.condition_spans:
            raise Rejected('invented source condition')
    if body.start != expected_body or body.end != clause.span.end:
        raise Rejected('native body boundary')


def _license_measure(clause, body, raw, view):
    """Independent re-reading of a measure sentence (split-based, not the producer's pattern).

    Every list segment must be represented as its own clause, the whole body must be
    consumed, and the role set / answer label / predicate dimension must follow the rules.
    """
    from .semantic_ir import unit_type
    text = re.sub(r'(?:です|だ|である)?[。！？!?]*\s*$', '', raw)
    parts = text.split('、')
    segment = re.compile(r'([^0-9\s：:の]+[0-9]*)(は|が|に|も)([0-9]+(?:\.[0-9]+)?)((?:[A-Za-z]+)|(?:[一-鿿]{1,2}))')
    tail = None; cuts = []; offset = 0
    for index, part in enumerate(parts):
        last = index == len(parts) - 1
        m = re.fullmatch(segment.pattern + r'(?:の([一-鿿ァ-ヶー]+))?', part) if last else segment.fullmatch(part)
        if not m: raise Rejected('measure grammar')
        if last and m.lastindex == 5: tail = m[5]
        cuts.append((offset, m)); offset += len(part) + 1
    count = sum(1 for c in view.clauses if c.rule == 'measure' and c.span == clause.span and c.body_span == clause.body_span)
    if count != len(parts): raise Rejected('measure segment omitted or duplicated')
    mine = [(o, m) for o, m in cuts
            if clause.roles and body.start + o + m.start(1) == next(r for r in clause.roles if r.name == 'entity').span.start]
    if len(mine) != 1: raise Rejected('measure segment alignment')
    o, m = mine[0]
    label, particle, number, unit = m[1], m[2], m[3], m[4]
    roles = {r.name: r for r in clause.roles}
    wanted = {'entity', 'label', 'value'}
    split = re.fullmatch(r'(.+?)([A-Za-z]|[0-9]+)', label) if not re.search(r'[A-Za-z0-9]', label[:1]) else None
    if split and re.search(r'[A-Za-z0-9]', split[1]): split = None
    if split: wanted.add('kind')
    if tail: wanted.add('substance')
    if set(roles) != wanted: raise Rejected('measure role set')
    if roles['entity'].term != label or roles['entity'].span.text != label: raise Rejected('measure entity')
    if clause.predicate_span.text != particle or clause.predicate_span.start != roles['entity'].span.end:
        raise Rejected('measure particle position')
    expected_label = split[2] if split and split[2].isalpha() else label
    if roles['label'].term != expected_label or roles['label'].span.text != expected_label: raise Rejected('measure label')
    if split and (roles['kind'].term != split[1] or roles['kind'].span.text != split[1]): raise Rejected('measure kind')
    value = roles['value']
    if (not isinstance(value.term, Quantity) or value.term.amount != Decimal(number) or value.term.unit != unit
            or value.span.text != number + unit): raise Rejected('measure quantity')
    if tail and roles['substance'].term != tail: raise Rejected('measure substance')
    if clause.predicate != 'measure.' + unit_type(unit)[0]: raise Rejected('measure dimension predicate')
    if (clause.polarity, clause.modality, clause.time) != ('+', 'assert', ''): raise Rejected('measure polarity/modality/time')
    if clause.conditions or clause.exceptions: raise Rejected('measure invented scope')


def license_clause(clause, view, ranges=None):
    """Check original text, roles and grammatical scope independently of reader."""
    if clause != view.by_id.get(clause.id): raise Rejected("noncanonical source clause")
    spans = [clause.span, clause.predicate_span, *(r.span for r in clause.roles),
             *clause.condition_spans, *clause.exception_spans]
    if clause.body_span: spans.append(clause.body_span)
    if any(not s.valid(view.sources) for s in spans): raise Rejected("source span mismatch")
    if any(s.source != clause.span.source for s in spans): raise Rejected("cross-source span")
    body = clause.body_span or clause.span
    if not (clause.span.start <= body.start < body.end <= clause.span.end): raise Rejected("body scope")
    if any(not (body.start <= r.span.start < r.span.end <= body.end) for r in clause.roles): raise Rejected("role scope")
    if clause.event.sort != 'event' or clause.unsupported: raise Rejected("unsupported/ill-typed source")
    if len({r.name for r in clause.roles}) != len(clause.roles): raise Rejected("duplicate role")
    if any(not _literal(r) for r in clause.roles): raise Rejected("role/value licensing")
    if len(clause.conditions) != len(clause.condition_spans) or len(clause.exceptions) != len(clause.exception_spans):
        raise Rejected("guard span count")
    if clause.rule != 'record':
        _native_guard_scope(clause, body)
    raw = body.text
    if clause.rule in ('frame', 'copula', 'identity'):
        from .typed_edges import _tagger
        significant = list(_tagger()(raw))
        if raw.rstrip().endswith(('?', '？')) or any(w.feature.pos1 == '助詞' and w.surface in ('か', 'かな', 'かしら', 'かい', 'かね', 'っけ') for w in significant):
            raise Rejected('interrogative source is not an assertion')
        if any('意志推量' in str(w.feature.cForm) for w in significant):
            raise Rejected('volitional source is not an assertion')
    before = clause.span.text[:clause.predicate_span.start - clause.span.start]
    quoted = before.count('「') > before.count('」') or before.count('『') > before.count('』')
    from .bot import _INJECTED
    if _INJECTED.search(clause.span.text) and clause.modality != 'instruction': raise Rejected("instruction assertion")
    if quoted and clause.modality != 'quote': raise Rejected("quoted assertion")
    if clause.rule == 'record':
        # Explicit symbolic axioms are a kernel-only input format, not a natural
        # language success. Their full formula, polarity and guard must agree.
        roles = {r.name: r.term for r in clause.roles}
        if clause.span.start != 0 or clause.span.end != len(view.sources[clause.span.source]):
            raise Rejected('symbolic full-source scope')
        actor = roles.get('actor'); amount = roles.get('amount')
        expected = f'{clause.predicate}({actor})'
        expected += '=' + str(amount.amount) + amount.unit if isinstance(amount, Quantity) else ''
        expected += ' is false.' if clause.polarity == '-' else '.'
        if raw != expected: raise Rejected("symbolic source formula")
        if set(roles) != ({'actor', 'amount'} if amount is not None else {'actor'}):
            raise Rejected('symbolic role set')
        if clause.time or clause.modality != 'assert': raise Rejected('symbolic time/modality')
        if (clause.predicate_span.start, clause.predicate_span.end, clause.predicate_span.text) != (
                body.start, body.start + len(clause.predicate), clause.predicate):
            raise Rejected('symbolic predicate position')
        actor_role = next(r for r in clause.roles if r.name == 'actor')
        if (actor_role.span.start, actor_role.span.end) != (
                body.start + len(clause.predicate) + 1, body.start + len(clause.predicate) + 1 + len(str(actor))):
            raise Rejected('symbolic actor position')
        prefix = clause.span.text[:body.start - clause.span.start]
        guards = clause.conditions or clause.exceptions
        if clause.conditions and clause.exceptions or len(guards) > 1:
            raise Rejected('unsupported symbolic guard grammar')
        if guards:
            g = guards[0]
            if len(g.roles) != 1 or g.roles[0][0] != 'actor' or g.polarity != '+' or g.modality != 'assert' or g.time or g.event:
                raise Rejected('symbolic guard shape')
            word = 'When ' if clause.conditions else 'Unless '
            guard_text = f'{g.predicate}({g.roles[0][1]})'
            spans_guard = clause.condition_spans or clause.exception_spans
            if prefix != word + guard_text + ', ' or len(spans_guard) != 1 or (
                    spans_guard[0].start, spans_guard[0].end, spans_guard[0].text) != (
                        clause.span.start + len(word), body.start - 2, guard_text):
                raise Rejected('symbolic guard position/content')
        elif prefix:
            raise Rejected('unrepresented symbolic source scope')
    elif clause.rule in ('copula', 'identity'):
        if (clause.span.start, clause.span.end) not in (ranges if ranges is not None else _ranges(view.sources[clause.span.source])):
            raise Rejected('copula full-clause boundary')
        m = re.fullmatch(r'\s*(.*?)\s*[はが]\s*(.*?)(?:です|である|だ|ではない|でない|じゃない)?[。！？?]*\s*', raw)
        if not m: raise Rejected("copula source grammar")
        roles = {r.name: r for r in clause.roles}; entity = roles.get('entity'); value = roles.get('value')
        if not entity or not value: raise Rejected("copula roles")
        lhs = entity.span.text
        if 'attribute' in roles: lhs += 'の' + roles['attribute'].span.text
        if m[1] != lhs or m[2] != value.span.text: raise Rejected("copula argument assignment")
        negative = bool(re.search(r'(?:ではない|でない|じゃない)[。！？?]*$', raw))
        if (clause.polarity == '-') != negative: raise Rejected("copula polarity")
        if clause.predicate != ('property' if 'attribute' in roles else 'identity'): raise Rejected("copula predicate")
        if clause.predicate_span != value.span: raise Rejected('copula predicate position')
        if clause.time: raise Rejected('unsupported copula time')
    elif clause.rule == 'frame':
        if (clause.span.start, clause.span.end) not in (ranges if ranges is not None else _ranges(view.sources[clause.span.source])):
            raise Rejected('event full-clause boundary')
        from .frames import canonical, read_all
        from .typed_edges import extract
        from .verdict import _clause_kind
        from .frames import _predicates
        from .typed_edges import _tagger, _base
        words = list(_tagger()(raw)); predicates = _predicates(words); all_frames = read_all(raw)
        cursor = 0; positions = []
        for word in words:
            at = raw.find(word.surface, cursor); positions.append(at); cursor = at+len(word.surface)
        tagged = tag(words, positions); pidx = [p0 for p0, _ in predicates]
        multi = len(all_frames) > 1
        if multi:
            # Plain te/renyō coordination only, with every predicate represented as its own clause.
            if (len(all_frames) != len(predicates) or _clause_kind(raw, 'record', False) != 'fact'
                    or not coordination_ok(tagged, pidx)):
                raise Rejected('unsupported multiple-event scope')
            sentence = sum(1 for c in view.clauses if c.rule == 'frame' and c.span == clause.span and c.body_span == clause.body_span)
            if sentence != len(all_frames): raise Rejected('coordinated clause omitted or duplicated')
        elif len(all_frames) != 1: raise Rejected('unsupported multiple-event scope')
        matching = [i for i, f in enumerate(all_frames) if i < len(predicates)
                    and f.predicate == clause.predicate
                    and body.start + positions[predicates[i][0]] == clause.predicate_span.start]
        if len(matching) != 1: raise Rejected("event predicate licensing")
        index = matching[0]; facts = [all_frames[index]]
        ev = predicates[index][0]
        c_first, c_last = chunk(tagged, pidx, index) if multi else (0, ev)
        lo = tagged[c_first][4] if multi and c_first < len(tagged) else 0
        if clause.predicate_span.end != body.start + positions[ev] + len(words[ev].surface):
            raise Rejected('event predicate end')
        frame = facts[0]; declared = {r.name: r.term for r in clause.roles}
        for name in ('agent', 'patient', 'recipient'):
            value = getattr(frame, name)
            allowed = {canonical(value)} if value else set()
            split = _role_split(value, clause.roles, name, raw, body, words, positions) if value else None
            if split: allowed.add(canonical(split[1]))
            if value and declared.get(name) not in allowed: raise Rejected("event role assignment")
            if not value and name in declared: raise Rejected("invented event role")
        for role in clause.roles:
            if role.name in ('agent', 'patient', 'recipient') and multi and role.span.start - body.start < lo:
                # a phrase outside this clause's own tokens: only the topic-scope borrow of the first clause's agent
                topic = topic_phrase(tagged, pidx)
                if (role.name != 'agent' or index == 0 or topic is None
                        or (role.span.start - body.start, role.span.end - body.start) != topic
                        or own_subject_phrase(tagged, c_first, c_last)):
                    raise Rejected('unlicensed role borrowing')
        normalized = _clause_kind(raw, 'record', frame.negated)
        if not quoted and clause.modality not in ('quote', 'hedge', 'instruction'):
            expected = 'assert' if normalized == 'fact' else normalized
            if clause.modality != expected: raise Rejected("normative modality")
        normalized_neg = frame.negated and normalized not in ('prohibition', 'obligation')
        if (clause.polarity == '-') != normalized_neg: raise Rejected("event polarity")
        edges = extract(raw)
        if clause.modality == 'quote' and not quoted and not any(e.mod == 'quote' for e in edges):
            raise Rejected('invented quote modality')
        if clause.modality == 'hedge' and not any(e.mod in ('hedge','simile') for e in edges) and not re.search(r'はず|かもしれ|だろう|らしい|もし', raw):
            raise Rejected('invented hedge modality')
        for role in clause.roles:
            if role.name in ('agent', 'patient', 'recipient'): continue
            case = {'location': 'で', 'origin': 'から', 'instrument': 'で'}.get(role.name)
            if case and not re.search(re.escape(role.span.text) + case, raw): raise Rejected("extra case role")
            elif role.name == 'quantity' and not isinstance(role.term, Quantity): raise Rejected("quantity role")
            elif role.name == 'time' and role.span.text not in raw: raise Rejected("time role")
            elif not case and role.name not in ('quantity', 'time'): raise Rejected("unknown event role")
        # Reconstruct coverage from raw positions and licensed role spans.
        # Do not trust a canonical reader's unsupported flag or Frame's subset.
        licensed = [(r.span.start, r.span.end) for r in clause.roles]
        for name in ('agent', 'patient', 'recipient'):
            value = getattr(frame, name)
            split = _role_split(value, clause.roles, name, raw, body, words, positions) if value else None
            role = next((r for r in clause.roles if r.name == name), None)
            if split and role: licensed.append((role.span.start - len(split[0]), role.span.start))
        licensed.append((clause.predicate_span.start, clause.predicate_span.end))
        if ev and _base(words[ev]) == 'する' and words[ev-1].feature.pos1 == '名詞' and _base(words[ev-1])+'する' == predicates[index][1]:
            licensed.append((body.start+positions[ev-1], body.start+positions[ev-1]+len(words[ev-1].surface)))
        for word, at in zip(words, positions):
            if multi and not (lo <= at < tagged[ev][5]): continue      # other clauses are checked as their own clauses
            if word.feature.pos1 in ('名詞', '代名詞', '形容詞', '形状詞', '副詞', '接頭辞', '接尾辞'):
                start = body.start + at
                if not any(a <= start and start + len(word.surface) <= b for a, b in licensed):
                    raise Rejected('unlicensed source content')
        if any(e.mod in ('quote', 'hedge', 'simile') for e in edges if e.head == clause.predicate) and clause.modality == 'assert':
            raise Rejected("nonasserted modality")
        # Independently inspect raw auxiliaries after the source predicate;
        # Frame.past can omit the tail of a compound verb.
        from .typed_edges import _base
        source_past = any(is_past_aux(w) for w in words[ev+1:])
        if clause.time not in ('past', 'nonpast') or (clause.time == 'past') != source_past: raise Rejected("tense licensing")
    elif clause.rule == 'measure':
        _license_measure(clause, body, raw, view)
    else: raise Rejected("unrecognized source grammar rule")
    # Source metadata cannot erase an antecedent outside the body span.
    prefix = clause.span.text[:body.start - clause.span.start]
    if re.search(r'場合|なら(?!な)|たら|れば|ときは', prefix) and not clause.conditions:
        raise Rejected("missing source condition")
    for pattern, span in zip(clause.conditions, clause.condition_spans):
        if not _license_guard(pattern, span): raise Rejected("condition licensing")
    for pattern, span in zip(clause.exceptions, clause.exception_spans):
        if clause.rule != 'record':
            # A native exception belongs to the immediately following original
            # sentence. It cannot borrow a convenient assertion elsewhere.
            raw_source = view.sources[clause.span.source]
            following = next(((a, b) for a, b in sorted(_ranges(raw_source)) if a == clause.span.end), None)
            if not following or not re.match(r'\s*ただし', raw_source[following[0]:following[1]]):
                raise Rejected('exception source boundary')
            prefix = raw_source[following[0]:following[1]].lstrip()
            cm = re.match(r'^(.*?)(場合(?:は|には|に)?|ならば|(?<!な)(?<!けれ)なら(?!な)|(?<!なけ)れば|ときは|時は|際は|際には)[、,]?', prefix)
            start = following[1] - len(prefix)
            if not cm or (span.start, span.end, span.text) != (start, start+len(cm[1]), cm[1]):
                raise Rejected('exception full-prefix scope')
        if not _license_guard(pattern, span): raise Rejected("exception licensing")


def _license_guard(pattern, span):
    from .frames import canonical, read_all, _predicates
    from .typed_edges import _tagger, _base
    words = list(_tagger()(span.text)); predicates = _predicates(words)
    if any(w.feature.pos1 == '助詞' and w.surface in ('か', 'かな', 'かしら', 'かい', 'かね', 'っけ') for w in words):
        return False
    if any('意志推量' in str(w.feature.cForm) for w in words): return False
    if re.search(r'もし|だったなら|はず|かも|だろう|らしい|[「『]', span.text):
        return False
    past = bool(len(predicates) == 1 and any(is_past_aux(w)
                                           for w in words[predicates[0][0]+1:]))
    frames = read_all(span.text)
    for frame in frames:
        roles = tuple((k, canonical(getattr(frame, k))) for k in ('agent', 'patient', 'recipient') if getattr(frame, k))
        if pattern.predicate == frame.predicate and pattern.roles == roles and pattern.polarity == ('-' if frame.negated else '+'):
            if len(frames) != 1 or len(predicates) != 1: return False
            from .verdict import _clause_kind
            if _clause_kind(span.text, 'record', frame.negated) != 'fact': return False
            positions = []; cursor = 0
            for word in words:
                at = span.text.find(word.surface, cursor); positions.append(at); cursor = at+len(word.surface)
            ev = predicates[0][0]
            covered = [(positions[ev], positions[ev]+len(words[ev].surface))]
            if ev and _base(words[ev]) == 'する' and words[ev-1].feature.pos1 == '名詞' and _base(words[ev-1])+'する' == predicates[0][1]:
                covered.append((positions[ev-1], positions[ev-1]+len(words[ev-1].surface)))
            for name in ('agent', 'patient', 'recipient'):
                value = getattr(frame, name)
                if value:
                    at = span.text.rfind(value, 0, positions[ev])
                    if at < 0: return False
                    covered.append((at, at+len(value)))
            for word, at in zip(words, positions):
                if word.feature.pos1 in ('名詞', '代名詞', '形容詞', '形状詞', '副詞', '接頭辞', '接尾辞'):
                    if not any(a <= at and at+len(word.surface) <= b for a, b in covered): return False
            return pattern.modality == 'assert' and pattern.time == ('past' if past else 'nonpast')
    m = re.fullmatch(r'(.*?)[はが](.*?)(?:です|だ|である)?[。]*', span.text)
    if m and pattern.predicate == 'identity':
        return dict(pattern.roles) == {'entity': m[1], 'value': m[2]} and pattern.polarity == '+'
    m = re.fullmatch(r'([A-Za-z_]+)\(([^()]+)\)', span.text)
    return bool(m and pattern.predicate == m[1] and pattern.roles == (('actor', m[2]),) and pattern.polarity == '+')


@dataclass
class State:
    env: dict
    covers: set
    basis: set
    conditions: set
    exceptions: set
    source: Clause | None = None
    answer: tuple = ()


class Checker:
    def __init__(self, view: View, sovereign: str, meter: Meter):
        self.view, self.sovereign, self.meter = view, sovereign, meter
        if view.invalid: raise Rejected('; '.join(view.invalid))
        self.clauses = []; self.index = {}; self.licensed = set()
        self.plan = None; self.predicates = set()
        self.effective = {}
        self.ranges = {}
        self.fixed_request = None; self.fixed_plan = None; self.operators = None

    def _shape(self, request, plan):
        self.meter.spend()
        # Request/Plan and their relevant children are immutable dataclasses.
        # This avoids revalidating the same fixed plan for every proposal. It
        # conveys no trust to proof nodes, which are all replayed separately.
        if request is self.fixed_request and plan is self.fixed_plan:
            return self.operators
        self.meter.shape(plan, request)
        operators = request_shape(request, plan, self.meter.budget)
        self.fixed_request, self.fixed_plan, self.operators = request, plan, operators
        return operators

    def _source(self, clause):
        if not isinstance(clause,Clause) or not isinstance(clause.id,str): raise Rejected('source type')
        self.meter.spend(1 + len(clause.roles) + len(clause.conditions) + len(clause.exceptions))
        if clause.sovereign != self.sovereign: raise Rejected("sovereign splice")
        if clause != self.view.by_id.get(clause.id): raise Rejected("noncanonical source clause")
        if clause.id not in self.licensed:
            source = clause.span.source
            if source not in self.view.sources: raise Rejected('missing original source')
            if clause.rule != 'record' and source not in self.ranges:
                self.meter.spend(len(self.view.sources[source]))
                self.ranges[source] = _ranges(self.view.sources[source])
            license_clause(clause, self.view, self.ranges.get(source)); self.licensed.add(clause.id)

    def _setup(self, plan):
        self.index = {}; self.predicates = set(); self.effective = {}; self.plan = plan
        todo = [n.pattern.predicate for n in plan.nodes if n.pattern]; seen = set(); selected = {}
        while todo:
            self.meter.spend(); pred = todo.pop()
            if pred in seen: continue
            seen.add(pred)
            pool = self.view.by_sovereign.get(self.sovereign, ()) if pred == '*' else self.view.by_predicate.get((self.sovereign, pred), ())
            for c in pool:
                self.meter.spend()
                if c.id in selected: continue
                selected[c.id] = c
                if len(selected) > self.meter.budget.candidates: raise Limit('candidates')
                self.meter.spend(len(c.conditions) + len(c.exceptions))
                todo.extend(p.predicate for p in (*c.conditions, *c.exceptions))
        self.clauses = list(selected.values())
        if len({c.family for c in self.clauses}) > 1: raise Rejected('family splice')
        for c in self.clauses:
            self.meter.spend(); self.index.setdefault((c.predicate, c.polarity, c.modality), []).append(c)
            self.predicates.add(c.predicate)

    def _pool(self, pattern, opposite=False):
        pol = ('-' if pattern.polarity == '+' else '+') if opposite else pattern.polarity
        polarities = ('+', '-') if pol == '*' else (pol,)
        modalities = ('permission', 'prohibition') if pattern.modality == 'normative' else (pattern.modality,)
        preds = self.predicates if pattern.predicate == '*' else (pattern.predicate,)
        for p in preds:
            for s in polarities:
                for m in modalities:
                    self.meter.spend()
                    yield from self.index.get((p, s, m), ())

    def _guard(self, pattern, env, negative=False, trail=()):
        positive = self._matching(pattern, env, trail)
        opposite = self._matching(pattern, env, trail, True)
        if positive and opposite: raise Conflict('opposing condition/exception evidence')
        return bool(opposite and not positive) if negative else bool(positive)

    def _matching(self, pattern, env, trail=(), opposite=False):
        found = []
        for c in self._pool(pattern, opposite):
            self.meter.spend(1 + len(pattern.roles))
            if _match(pattern, c, env, opposite) == env and self._effective(c, env, trail): found.append(c)
        return found

    def _effective(self, c, env, trail=()):
        self.meter.spend()
        if c.id in trail or c.unsupported: return False
        if len(trail) >= self.meter.budget.depth: return False
        self._source(c)
        key = (c.id, tuple(sorted(env.items())), frozenset(trail))
        if key in self.effective: return self.effective[key]
        for guard in c.conditions:
            if not self._guard(guard, env, trail=(*trail, c.id)):
                self.effective[key] = False; return False
        for guard in c.exceptions:
            if not self._guard(guard, env, True, (*trail, c.id)):
                self.effective[key] = False; return False
        self.effective[key] = True; return True

    def _scope_support(self, state, op):
        ids = state.conditions if op == 'ApplyCondition' else state.exceptions
        guards = []
        for ident in sorted(ids):
            self.meter.spend(); c = self.view.by_id[ident]
            guards.extend((g, op == 'Except') for g in (c.conditions if op == 'ApplyCondition' else c.exceptions))
        return guards

    def audit(self, plan):
        """Enumerate independently to check omitted outputs and proof-external conflict."""
        self._setup(plan); tables = {}
        for op in plan.nodes:
            self.meter.spend(); ins = [tables[i] for i in op.inputs]; out = []
            if op.op == 'Bind':
                for c in self._pool(op.pattern):
                    self.meter.spend(); env = _match(op.pattern, c)
                    if env is None or c.unsupported: continue
                    self._source(c)
                    opposite = Pattern(op.pattern.predicate, op.pattern.roles,
                                       '-' if c.polarity == '+' else '+', op.pattern.modality, op.pattern.time, op.pattern.event)
                    if op.pattern.modality == 'normative':
                        opposite = Pattern(op.pattern.predicate, op.pattern.roles, c.polarity,
                                           'prohibition' if c.modality == 'permission' else 'permission', op.pattern.time, op.pattern.event)
                    for opponent in self._pool(opposite):
                            self.meter.spend()
                            if _match(opposite, opponent, env) is not None and self._effective(c, env) and self._effective(opponent, env):
                                raise Conflict('applicable opponent outside proof')
                    if op.relation in ('whether','whether-negative'): env[op.target.name] = c.modality == 'permission' if op.pattern.modality == 'normative' else c.polarity == ('-' if op.relation == 'whether-negative' else '+')
                    out.append(State(env, set(op.obligations), {c.id}, {c.id} if c.conditions else set(), {c.id} if c.exceptions else set()))
            elif op.op == 'Join':
                for a in ins[0]:
                    for b in ins[1]:
                        self.meter.spend()
                        if any(a.env[k] != b.env[k] for k in a.env.keys() & b.env.keys()): continue
                        out.append(State(a.env | b.env, a.covers | b.covers | set(op.obligations), a.basis | b.basis, a.conditions | b.conditions, a.exceptions | b.exceptions))
            elif op.op in ('ApplyCondition', 'Except'):
                for a in ins[0]:
                    self.meter.spend(); ok = True
                    for guard, negative in self._scope_support(a, op.op):
                        if not self._guard(guard, a.env, negative): ok = False; break
                    if ok: out.append(State(a.env, a.covers | set(op.obligations), a.basis,
                                            set() if op.op == 'ApplyCondition' else a.conditions,
                                            set() if op.op == 'Except' else a.exceptions))
            else:
                for a in ins[0]:
                    self.meter.spend()
                    if op.op == 'Project' and (a.conditions or a.exceptions): continue
                    result = _calc(op, a.env)
                    if result: out.append(State(result[0], a.covers | set(op.obligations), a.basis, a.conditions, a.exceptions, answer=result[1]))
            unique = {}
            for a in out:
                self.meter.spend(); unique.setdefault((tuple(sorted(a.env.items())), tuple(sorted(a.basis)), tuple(sorted(a.conditions)), tuple(sorted(a.exceptions))), a)
            self.meter.states(len({tuple(sorted(a.env.items())) for a in unique.values()})); tables[op.id] = list(unique.values())
        return {s.answer for s in tables[plan.root]}

    def proof(self, request: Request, plan: Plan, proof: Proof):
        operators = self._shape(request, plan)
        if self.plan != plan: self._setup(plan)
        if proof.sovereign != self.sovereign: raise Rejected('proof sovereign')
        nodes = {}; states = {}; depths = {}
        for node in proof.nodes:
            if (not isinstance(node,ProofNode) or not isinstance(node.id,str) or not isinstance(node.op,str)
                or not all(isinstance(getattr(node,f),tuple) for f in ('parents','bindings','covers','answer'))
                or any(not isinstance(p,str) for p in node.parents)):
                raise Rejected('proof field types')
            self.meter.spend(1 + len(node.parents) + len(node.bindings) + len(node.covers) + len(node.answer))
            if node.id in nodes or any(p not in nodes for p in node.parents): raise Rejected('duplicate/cyclic/missing proof reference')
            depths[node.id] = 1 + max((depths[p] for p in node.parents), default=0)
            if depths[node.id] > self.meter.budget.depth: raise Limit('depth')
            parents = [states[p] for p in node.parents]
            if node.op == 'Source':
                if node.parents or node.plan_node or node.clause is None: raise Rejected('Source arity')
                c = node.clause
                self._source(c); state = State({}, set(), {c.id}, {c.id} if c.conditions else set(),
                                               {c.id} if c.exceptions else set(), c)
            elif node.op == 'Witness':
                if not parents or parents[0].source is None or node.plan_node or node.clause: raise Rejected('guard witness shape')
                c = parents[0].source; env = dict(node.bindings)
                guards = [(g, False) for g in c.conditions] + [(g, True) for g in c.exceptions]
                if len(parents) != 1 + len(guards): raise Rejected('missing guard witness')
                for (g, negative), p in zip(guards, parents[1:]):
                    if not p.source or p.conditions or p.exceptions or p.env != env or _match(g, p.source, env, negative) != env:
                        raise Rejected('guard witness does not discharge source condition')
                    if not self._guard(g, env, negative, (c.id,)):
                        raise Rejected('guard witness lacks consistent applicable support')
                state = State(env, set(), {c.id}, set(), set(), c)
            else:
                if node.clause or node.plan_node not in operators: raise Rejected('operator/source mismatch')
                op = operators[node.plan_node]
                if op.op != node.op: raise Rejected('operator mismatch')
                head = node.parents[:len(op.inputs)]
                if tuple(nodes[p].plan_node for p in head) != op.inputs: raise Rejected('plan dependency splice')
                if op.op == 'Bind':
                    if len(parents) != 1 or parents[0].source is None: raise Rejected('Bind source')
                    c = parents[0].source; env = _match(op.pattern, c)
                    if env is None: raise Rejected('Bind roles/polarity/time')
                    if op.relation in ('whether','whether-negative'): env[op.target.name] = c.modality == 'permission' if op.pattern.modality == 'normative' else c.polarity == ('-' if op.relation == 'whether-negative' else '+')
                    state = State(env, set(op.obligations), {c.id}, {c.id} if c.conditions else set(), {c.id} if c.exceptions else set())
                elif op.op == 'Join':
                    if len(parents) != 2: raise Rejected('Join arity')
                    a, b = parents
                    if any(a.env[k] != b.env[k] for k in a.env.keys() & b.env.keys()): raise Rejected('Join shared variable')
                    state = State(a.env | b.env, a.covers | b.covers | set(op.obligations), a.basis | b.basis, a.conditions | b.conditions, a.exceptions | b.exceptions)
                elif op.op in ('ApplyCondition', 'Except'):
                    if not parents: raise Rejected('scope arity')
                    a = parents[0]; guards = self._scope_support(a, op.op)
                    if len(parents) != len(guards) + 1: raise Rejected('source scope missing')
                    for (guard, negative), p in zip(guards, parents[1:]):
                        if not p.source or p.conditions or p.exceptions or p.env != a.env or _match(guard, p.source, a.env, negative) != a.env:
                            raise Rejected('source scope mismatch')
                        if not self._guard(guard, a.env, negative):
                            raise Rejected('source scope has opposing/missing support')
                    state = State(a.env, a.covers | set(op.obligations), a.basis,
                                  set() if op.op == 'ApplyCondition' else a.conditions,
                                  set() if op.op == 'Except' else a.exceptions)
                else:
                    if len(parents) != 1: raise Rejected('operator proof arity')
                    a = parents[0]
                    if op.op == 'Project' and (a.conditions or a.exceptions): raise Rejected('unresolved ancestor scope')
                    result = _calc(op, a.env)
                    if result is None: raise Rejected('false filter')
                    state = State(result[0], a.covers | set(op.obligations), a.basis, a.conditions, a.exceptions, answer=result[1])
            if tuple(sorted(state.env.items())) != node.bindings or tuple(sorted(state.covers)) != node.covers or state.answer != node.answer:
                raise Rejected('producer binding/coverage/answer differs from replay')
            states[node.id] = state; nodes[node.id] = node
        if proof.root not in nodes or nodes[proof.root].plan_node != plan.root: raise Rejected('root mismatch')
        reachable = set(); todo = [proof.root]
        while todo:
            self.meter.spend(); k = todo.pop()
            if k not in reachable: reachable.add(k); todo.extend(nodes[k].parents)
        if reachable != set(nodes): raise Rejected('unreachable proof node')
        state = states[proof.root]
        if state.covers != {o.id for o in request.obligations}: raise Rejected('incomplete obligations')
        return state.answer

    def gate(self, request, plan, proposals):
        self._shape(request, plan)
        expected = self.audit(plan)
        if {a for a, _ in proposals} != expected: raise Rejected('producer omitted/invented alternative answers')
        checked = {}
        for answer, proof in proposals:
            self.meter.spend()
            replayed = self.proof(request, plan, proof)
            if replayed != answer: raise Rejected('claimed answer/proof mismatch')
            # Validate every submitted proof; duplicates may share only the
            # final rendering, never a cached acceptance of unchecked content.
            checked.setdefault(answer, (replayed, proof))
        if not checked: return {}
        return checked
