from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
import gc
import tracemalloc

import pytest

from verantyx.semantic_measure import read_measure_request, read_measure_sentence


def _read(raw, source='attack', start=0, left=0, right=None):
    if right is None:
        right = len(raw)
    return read_measure_sentence(source, raw, start, left, right, True, 'attack')


def _role(clause, name):
    return next(role for role in clause.roles if role.name == name)


def _measure_pairs(clauses):
    return [(_role(clause, 'entity').term, _role(clause, 'value').term.amount)
            for clause in clauses]


class _Builder:
    def __init__(self):
        self.roots = []
        self.nodes = []
        self.outputs = []
        self._next_variable = 0

    def variable(self, sort):
        self._next_variable += 1
        return ('variable', self._next_variable, sort)

    def bind(self, pattern, span):
        self.roots.append(('root', len(self.roots)))

    def obligation(self, node, kind, span, description):
        return ('obligation', node, kind, description)

    def project(self, node):
        return ('project', node)


def test_decimal_lexeme_is_preserved_exactly():
    raw = '箱Aは12345678901234567890.012300kg'

    clause, = _read(raw)
    quantity = _role(clause, 'value').term

    assert quantity.amount.as_tuple() == Decimal('12345678901234567890.012300').as_tuple()
    assert quantity.unit == 'kg'
    assert _role(clause, 'value').span.text == '12345678901234567890.012300kg'


def test_decimal_digit_budget_accepts_128_significant_digits():
    raw = 'Aは' + '9' * 128 + 'kg'

    clause, = _read(raw)

    amount = _role(clause, 'value').term.amount
    assert amount.as_tuple() == Decimal('9' * 128).as_tuple()


def test_decimal_digit_budget_refuses_129_significant_digits():
    raw = 'Aは' + '9' * 129 + 'kg'

    assert _read(raw) is None


@pytest.mark.parametrize('raw', ['', '、', 'Aはkg', 'Aは1kg 余分', 'Aは1kg、'])
def test_empty_or_incomplete_measure_sentences_are_declined(raw):
    assert _read(raw) is None


def test_shared_head_noun_is_attached_to_each_measure():
    clauses = _read('箱Aは1.25kg、箱Bは2.50kgの水')

    assert [clause.predicate for clause in clauses] == ['measure.mass', 'measure.mass']
    assert [_role(clause, 'substance').term for clause in clauses] == ['水', '水']
    assert _measure_pairs(clauses) == [('箱A', Decimal('1.25')), ('箱B', Decimal('2.50'))]


def test_reordering_segments_keeps_each_entity_value_pair_together():
    forward = _read('箱Aは1kg、箱Bは2kg')
    reverse = _read('箱Bは2kg、箱Aは1kg')

    assert _measure_pairs(forward) == [('箱A', Decimal('1')), ('箱B', Decimal('2'))]
    assert _measure_pairs(reverse) == [('箱B', Decimal('2')), ('箱A', Decimal('1'))]


def test_sum_question_builds_a_bounded_operator_chain():
    builder = _Builder()

    result = read_measure_request('合計は何kgですか', builder, ('question-span',))

    assert result == ('project', builder.nodes[-1].id)
    assert [node.op for node in builder.nodes] == ['Join', 'Filter', 'Sum']
    assert builder.nodes[-1].unit == 'kg'
    assert builder.nodes[-1].relation == ''
    assert builder.outputs[0][0] == '計算結果'
    assert builder.outputs[0][3] == 'kg'


def test_unrecognized_question_returns_none_without_mutating_builder():
    builder = _Builder()

    assert read_measure_request('箱Aと箱Bの合計を教えて', builder, ('question-span',)) is None
    assert builder.roots == []
    assert builder.nodes == []
    assert builder.outputs == []


def test_repeated_reads_have_stable_clause_ids_and_values():
    raw = '箱Aは1.20kg、箱Bは2.40kg'

    first = _read(raw)
    second = _read(raw)

    assert first == second
    assert [clause.id for clause in first] == [clause.id for clause in second]


def test_two_readers_can_parse_independently_and_repeatedly():
    inputs = ['箱Aは1kg、箱Bは2kg', '箱Cは3m、箱Dは4m'] * 40

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(_read, inputs))

    assert [_measure_pairs(result) for result in results] == [
        [('箱A', Decimal('1')), ('箱B', Decimal('2'))]
        if raw.endswith('2kg') else [('箱C', Decimal('3')), ('箱D', Decimal('4'))]
        for raw, result in zip(inputs, results)
    ]


def test_discarded_repeated_reads_do_not_accumulate_live_memory():
    raw = '箱Aは1.20kg、箱Bは2.40kg'
    gc.collect()
    tracemalloc.start()
    try:
        for _ in range(300):
            _read(raw)
        gc.collect()
        live_bytes, peak_bytes = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()

    assert live_bytes < 512 * 1024
    assert peak_bytes < 2 * 1024 * 1024


def test_many_short_segments_are_consumed_in_input_order():
    raw = '、'.join(f'箱{i}は{i + 1}kg' for i in range(256))

    clauses = _read(raw)

    assert len(clauses) == 256
    assert _measure_pairs(clauses)[0] == ('箱0', Decimal('1'))
    assert _measure_pairs(clauses)[-1] == ('箱255', Decimal('256'))
