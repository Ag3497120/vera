"""Measure sentences (source side) and measure questions (request side) for Round5-A.

Source side: a sentence made only of ``<label><particle><number><unit>`` segments,
joined by 、, with an optional list-level head noun (…の水), becomes one
``measure`` Clause per segment. Anything else is not read here; the caller keeps
its own typed Unread. Nothing is guessed: the whole sentence must be consumed.

Request side: a closed set of structural question shapes (total of two measures,
longest/heaviest pick between two, same/different) is expanded into the existing
Bind / Join / Filter / Sum / Compare / Project operators. The unit's physical
dimension comes from ``semantic_ir.UNITS`` (a proof rule), never from a word list.
"""
from __future__ import annotations

import hashlib
import re
from decimal import Decimal

from .semantic_ir import (Clause, Operator, Output, Pattern, Plan, Quantity, Role,
                          Span, Test, Variable, unit_type)

_NUM = r'[0-9]+(?:\.[0-9]+)?'
_UNIT = r'(?:kg|km|cm|mL|ml|g|m|L|[一-鿿]{1,2})'
_SEGMENT = re.compile(
    r'(?P<label>[^、。！？!?\s0-9：:の]+[0-9]*)(?P<part>は|が|に|も)(?P<num>' + _NUM + r')(?P<unit>' + _UNIT + r')')
_TAIL = re.compile(r'(?:の(?P<noun>[一-鿿ァ-ヶー]+))?(?:です|だ|である)?(?:[。！？!?]*)\s*')
_LABEL = re.compile(r'(?P<kind>[^A-Za-z0-9]+?)(?P<ident>[A-Za-z]|[0-9]+)')

# dimension per comparison word: (dimension, relation). Dimensions are IR unit types.
_ADJECTIVE = {'長い': ('length', '>'), '短い': ('length', '<'),
              '重い': ('mass', '>'), '軽い': ('mass', '<')}
_NOUN_DIMENSION = {'長さ': 'length', '重さ': 'mass'}


def _span(source, raw, start, end):
    return Span(source, start, end, raw[start:end])


def read_measure_sentence(source, raw, start, left, right, sovereign, family):
    """Return Clauses for a pure measure sentence in raw[left:right], else None."""
    text = raw[left:right]
    position = 0; segments = []
    while True:
        m = _SEGMENT.match(text, position)
        if not m: return None
        segments.append(m); position = m.end()
        if text.startswith('、', position): position += 1; continue
        break
    tail = _TAIL.fullmatch(text, position)
    if not tail: return None
    out = []
    for index, m in enumerate(segments):
        try:
            amount = Decimal(m['num'])
        except Exception:
            return None
        if len(amount.as_tuple().digits) > 128: return None
        unit = m['unit']
        dimension = unit_type(unit)[0]
        label = m['label']; label_at = left + m.start('label')
        roles = [Role('entity', label, _span(source, raw, label_at, label_at + len(label)), 'literal')]
        lm = _LABEL.fullmatch(label)
        if lm:
            roles.append(Role('kind', lm['kind'], _span(source, raw, label_at, label_at + len(lm['kind'])), 'literal'))
            ident_at = label_at + lm.start('ident')
            # An alphabetic identifier distinguishes entities; a numeral alone does not.
            answer = lm['ident'] if lm['ident'].isalpha() else label
            answer_span = _span(source, raw, ident_at, ident_at + len(lm['ident'])) if lm['ident'].isalpha() \
                else roles[0].span
        else:
            answer = label; answer_span = roles[0].span
        roles.append(Role('label', answer, answer_span, 'literal'))
        unit_at = left + m.start('unit')
        num_at = left + m.start('num')
        roles.append(Role('value', Quantity(amount, unit), _span(source, raw, num_at, unit_at + len(unit)), 'quantity'))
        if tail['noun'] and index == len(segments) - 1:
            noun_at = left + tail.start('noun')
            roles.append(Role('substance', tail['noun'], _span(source, raw, noun_at, noun_at + len(tail['noun'])), 'literal'))
        seg_start = left + m.start(); seg_end = left + m.end()
        ident = hashlib.sha256(f'{source}:{left}:{right}:measure:{index}'.encode()).hexdigest()[:24]
        out.append(Clause(ident, Variable('event_' + ident, 'event'), 'measure.' + dimension,
                          _span(source, raw, label_at + len(label), label_at + len(label) + len(m['part'])),
                          tuple(roles), _span(source, raw, start, right), _span(source, raw, left, right),
                          rule='measure', sovereign=sovereign, family=family))
    if tail['noun']:
        # propagate the shared head noun to the earlier segments so every clause is complete
        noun_at = left + tail.start('noun'); noun = tail['noun']
        shared = Role('substance', noun, _span(source, raw, noun_at, noun_at + len(noun)), 'literal')
        out = [c if any(r.name == 'substance' for r in c.roles)
               else Clause(c.id, c.event, c.predicate, c.predicate_span, c.roles + (shared,), c.span, c.body_span,
                           rule=c.rule, sovereign=c.sovereign, family=c.family) for c in out]
    return out


def _bind_measure(b, span, dimension, kind=None):
    x = b.variable('entity'); label = b.variable('entity'); value = b.variable('quantity')
    roles = [('entity', x), ('label', label), ('value', value)]
    if kind: roles.append(('kind', kind))
    b.bind(Pattern('measure.' + dimension, tuple(roles)), span)
    return x, label, value


def _two_measures(b, full, dimension, kind=None):
    x, lx, qx = _bind_measure(b, full, dimension, kind)
    y, ly, qy = _bind_measure(b, full, dimension, kind)
    current = b.roots[0]
    ident = 'n' + str(len(b.nodes))
    b.nodes.append(Operator(ident, 'Join', inputs=(current, b.roots[1]))); current = ident
    ident = 'n' + str(len(b.nodes))
    oid = b.obligation(ident, 'filter', full, 'two distinct entities')
    b.nodes.append(Operator(ident, 'Filter', inputs=(current,), tests=(Test(x, '!=', y),), obligations=(oid,)))
    return ident, (x, lx, qx), (y, ly, qy)


def read_measure_request(raw, b, full):
    """Expand a closed measure question into a plan, or return None if not this shape."""
    text = raw.strip()
    m = re.fullmatch(r'合計は(?:何|いくつ)(?P<unit>' + _UNIT + r')(?:ですか)?[？?。]*', text)
    if m:
        unit = m['unit']; dimension = unit_type(unit)[0]
        current, (x, lx, qx), (y, ly, qy) = _two_measures(b, full, dimension)
        ident = 'n' + str(len(b.nodes)); result = b.variable('quantity')
        oid = b.obligation(ident, 'operation', full, 'Sum')
        b.nodes.append(Operator(ident, 'Sum', inputs=(current,), terms=(qx, qy), target=result, unit=unit,
                                obligations=(oid,)))
        b.outputs.append(('計算結果', result, full, unit))
        return b.project(ident)
    m = (re.fullmatch(r'(?P<adj>長い|短い|重い|軽い)(?P<kind>[一-鿿ァ-ヶー]+?)は[？?。]*', text)
         or re.fullmatch(r'どちらが(?P<adj>長い|短い|重い|軽い)(?:ですか)?[？?。]*', text)
         or re.fullmatch(r'(?P<adj>長い|短い|重い|軽い)方は[？?。]*', text))
    if m:
        dimension, relation = _ADJECTIVE[m['adj']]
        kind = m.groupdict().get('kind')
        if kind == '方': kind = None
        current, (x, lx, qx), (y, ly, qy) = _two_measures(b, full, dimension, kind)
        ident = 'n' + str(len(b.nodes)); result = b.variable('entity')
        oid = b.obligation(ident, 'operation', full, 'Compare')
        b.nodes.append(Operator(ident, 'Compare', inputs=(current,), terms=(qx, qy), target=result, relation=relation,
                                choices=(lx, ly), obligations=(oid,)))
        b.outputs.append(('比較結果', result, full, ''))
        return b.project(ident)
    m = re.fullmatch(r'(?P<noun>長さ|重さ)は(?P<rel>違う|同じ|等しい)(?:ですか)?[？?。]*', text)
    if m:
        dimension = _NOUN_DIMENSION[m['noun']]
        relation = '!=' if m['rel'] == '違う' else '='
        current, (x, lx, qx), (y, ly, qy) = _two_measures(b, full, dimension)
        ident = 'n' + str(len(b.nodes)); result = b.variable('value')
        oid = b.obligation(ident, 'operation', full, 'Compare')
        b.nodes.append(Operator(ident, 'Compare', inputs=(current,), terms=(qx, qy), target=result, relation=relation,
                                obligations=(oid,)))
        b.outputs.append(('可否', result, full, ''))
        return b.project(ident)
    return None
