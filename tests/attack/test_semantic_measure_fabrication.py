from decimal import Decimal

import pytest

from verantyx.semantic_ir import Span, Variable
from verantyx.semantic_measure import read_measure_request, read_measure_sentence


class _Builder:
    """Small recording builder for checking the measure request IR shape."""

    def __init__(self):
        self.nodes = []
        self.roots = []
        self.bindings = []
        self.outputs = []
        self.obligations = []
        self._variables = 0
        self.projected = None

    def variable(self, sort):
        self._variables += 1
        return Variable(f'{sort}_{self._variables}', sort)

    def bind(self, pattern, span):
        self.bindings.append((pattern, span))
        self.roots.append(f'r{len(self.roots)}')

    def obligation(self, node, kind, span, description):
        ident = f'obligation_{len(self.obligations)}'
        self.obligations.append((ident, node, kind, span, description))
        return ident

    def project(self, root):
        self.projected = root
        return root


def _read(raw, *, start=0, left=0, sovereign=True, family='facts'):
    return read_measure_sentence(
        'ledger', raw, start, left, len(raw), sovereign, family)


def _request(text):
    builder = _Builder()
    full = Span('question', 0, len(text), text)
    result = read_measure_request(text, builder, full)
    return result, builder


def _roles(clause):
    return {role.name: role for role in clause.roles}


def test_sentence_keeps_decimal_and_role_spans_tied_to_source():
    raw = '箱Aは1.20kg'
    clauses = _read(raw)

    assert len(clauses) == 1
    clause = clauses[0]
    roles = _roles(clause)
    assert clause.predicate == 'measure.mass'
    assert clause.predicate_span.text == 'は'
    assert roles['entity'].term == '箱A'
    assert roles['entity'].span.text == '箱A'
    assert roles['label'].term == 'A'
    assert roles['label'].span.text == 'A'
    assert roles['value'].term.amount == Decimal('1.20')
    assert roles['value'].term.amount.as_tuple().exponent == -2
    assert roles['value'].term.unit == 'kg'
    assert roles['value'].span.text == '1.20kg'
    assert clause.span.text == clause.body_span.text == raw
    assert clause.rule == 'measure'
    assert clause.sovereign is True
    assert clause.family == 'facts'


def test_shared_head_noun_and_segment_values_keep_their_own_provenance():
    raw = '箱Aは1kg、箱Bが2gの水です。'
    clauses = _read(raw)

    assert len(clauses) == 2
    assert [_roles(c)['entity'].term for c in clauses] == ['箱A', '箱B']
    assert [_roles(c)['label'].term for c in clauses] == ['A', 'B']
    assert [_roles(c)['value'].term.amount for c in clauses] == [Decimal('1'), Decimal('2')]
    assert [_roles(c)['value'].term.unit for c in clauses] == ['kg', 'g']
    for clause in clauses:
        roles = _roles(clause)
        assert roles['substance'].term == '水'
        assert roles['substance'].span.text == '水'
        assert clause.body_span.text == raw
        for role in clause.roles:
            assert raw[role.span.start:role.span.end] == role.span.text


def test_negation_remainder_is_not_rewritten_as_a_measure_fact():
    assert _read('箱Aは3kgではない') is None


def test_partial_or_unconsumed_sentence_is_rejected():
    assert _read('箱Aは3kgと思う') is None
    assert _read('箱Aは3kg、') is None


def test_measure_particle_is_preserved_in_its_predicate_span():
    raw = '箱Aも3kg'
    clauses = _read(raw)

    assert len(clauses) == 1
    assert clauses[0].predicate_span.text == 'も'
    assert clauses[0].body_span.text == raw


def test_sum_question_binds_two_mass_values_and_preserves_requested_unit():
    result, builder = _request('合計は何kgですか？')

    assert result == builder.projected
    assert [pattern.predicate for pattern, _ in builder.bindings] == [
        'measure.mass', 'measure.mass']
    sum_op = next(node for node in builder.nodes if node.op == 'Sum')
    value_vars = [dict(pattern.roles)['value'] for pattern, _ in builder.bindings]
    assert sum_op.terms == tuple(value_vars)
    assert sum_op.unit == 'kg'
    assert builder.outputs[0][0] == '計算結果'
    assert builder.outputs[0][1] == sum_op.target


def test_heaviest_question_compares_mass_and_returns_source_labels():
    _, builder = _request('どちらが重いですか？')

    assert [pattern.predicate for pattern, _ in builder.bindings] == [
        'measure.mass', 'measure.mass']
    compare = next(node for node in builder.nodes if node.op == 'Compare')
    label_vars = [dict(pattern.roles)['label'] for pattern, _ in builder.bindings]
    value_vars = [dict(pattern.roles)['value'] for pattern, _ in builder.bindings]
    assert compare.relation == '>'
    assert compare.terms == tuple(value_vars)
    assert compare.choices == tuple(label_vars)
    assert builder.outputs[0][0] == '比較結果'


def test_same_length_question_uses_equality_over_length_values():
    _, builder = _request('長さは同じですか？')

    assert [pattern.predicate for pattern, _ in builder.bindings] == [
        'measure.length', 'measure.length']
    compare = next(node for node in builder.nodes if node.op == 'Compare')
    value_vars = [dict(pattern.roles)['value'] for pattern, _ in builder.bindings]
    assert compare.relation == '='
    assert compare.terms == tuple(value_vars)
    assert builder.outputs[0][0] == '可否'


def test_different_mass_question_uses_inequality_and_distinct_entities():
    _, builder = _request('重さは違う？')

    filter_op = next(node for node in builder.nodes if node.op == 'Filter')
    compare = next(node for node in builder.nodes if node.op == 'Compare')
    entity_vars = [dict(pattern.roles)['entity'] for pattern, _ in builder.bindings]
    assert filter_op.tests[0].relation == '!='
    assert (filter_op.tests[0].left, filter_op.tests[0].right) == tuple(entity_vars)
    assert compare.relation == '!='


def test_request_with_extra_unparsed_material_is_not_partially_accepted():
    result, _ = _request('重い方は？ 箱A')

    assert result is None


@pytest.mark.xfail(
    strict=False,
    reason='DEFECT: accepts an anchor after the source range and emits a reversed provenance span',
)
def test_sentence_rejects_anchor_after_its_source_range():
    raw = '箱Aは3kg'
    results = [
        read_measure_sentence('src', raw, len(raw) + 1, 0, len(raw), True, 'facts')
        for _ in range(2)
    ]

    assert results == [None, None]
