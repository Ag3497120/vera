from concurrent.futures import ThreadPoolExecutor
import gc
import tracemalloc

import pytest

from verantyx.semantic_ir import Pattern
from verantyx.semantic_wh import read_role_list_question


class _Builder:
    def __init__(self):
        self.serial = 0
        self.roots = []
        self.outputs = []
        self.bind_calls = []
        self.projected = []

    def variable(self):
        value = f"v{self.serial}"
        self.serial += 1
        return value

    def bind(self, pattern, full):
        self.bind_calls.append((pattern, full))
        self.roots.append(pattern)

    def project(self, root):
        self.projected.append(root)
        return root


def _read(raw, full="source"):
    builder = _Builder()
    plan = read_role_list_question(raw, builder, full)
    return plan, builder


def test_wh_question_builds_one_wildcard_bind_with_roles():
    plan, builder = _read("誰が何を？", "evidence text")

    assert plan == Pattern("*", (("agent", "v0"), ("patient", "v1")))
    assert builder.bind_calls == [(plan, "evidence text")]
    assert builder.outputs == [
        ("誰が", "v0", "evidence text", ""),
        ("何を", "v1", "evidence text", ""),
    ]
    assert builder.projected == [plan]


def test_role_nouns_build_their_declared_roles():
    plan, builder = _read("物、起点、終点は？")

    assert plan == Pattern(
        "*", (("patient", "v0"), ("origin", "v1"), ("recipient", "v2"))
    )
    assert [item[0] for item in builder.outputs] == ["物", "起点", "終点"]


@pytest.mark.parametrize(
    "raw",
    ["", " \t\n", "誰が?", "物は", "わからない", "誰が誰は？"],
)
def test_empty_malformed_single_role_and_duplicate_shapes_are_refused(raw):
    plan, builder = _read(raw)

    assert plan is None
    assert builder.bind_calls == []
    assert builder.roots == []
    assert builder.outputs == []
    assert builder.projected == []


@pytest.mark.parametrize("raw", ["誰が何は？", "渡した人、送り主は？"])
def test_duplicate_semantic_roles_are_refused(raw):
    plan, builder = _read(raw)

    assert plan is None
    assert builder.bind_calls == []
    assert builder.outputs == []


def test_role_order_changes_layout_but_not_label_to_role_mapping():
    first, first_builder = _read("誰が何を？")
    reversed_plan, reversed_builder = _read("何を誰が？")

    assert first == Pattern("*", (("agent", "v0"), ("patient", "v1")))
    assert reversed_plan == Pattern("*", (("patient", "v0"), ("agent", "v1")))
    assert {label: role for (label, _, _, _), (role, _) in zip(first_builder.outputs, first.roles)} == {
        "誰が": "agent",
        "何を": "patient",
    }
    assert {label: role for (label, _, _, _), (role, _) in zip(reversed_builder.outputs, reversed_plan.roles)} == {
        "誰が": "agent",
        "何を": "patient",
    }


def test_repeated_fresh_calls_are_deterministic_and_do_not_leak_full_text():
    first, first_builder = _read("何を誰が？", "first source")
    _read("物、起点は？", "intervening source")
    repeated, repeated_builder = _read("何を誰が？", "later source")

    assert first == repeated
    assert first_builder.outputs == [
        ("何を", "v0", "first source", ""),
        ("誰が", "v1", "first source", ""),
    ]
    assert repeated_builder.outputs == [
        ("何を", "v0", "later source", ""),
        ("誰が", "v1", "later source", ""),
    ]


def test_large_unrecognized_input_returns_none_without_mutation():
    plan, builder = _read("x" * (256 * 1024))

    assert plan is None
    assert builder.bind_calls == []
    assert builder.outputs == []


def test_long_duplicate_role_sequence_is_refused_without_building_a_plan():
    plan, builder = _read("誰が" * 4096)

    assert plan is None
    assert builder.bind_calls == []
    assert builder.outputs == []


def test_two_concurrent_readers_keep_plans_and_outputs_separate():
    questions = ["誰が何を？", "何を誰が？"] * 100

    def read_one(raw):
        plan, builder = _read(raw, raw)
        return plan, tuple(builder.outputs), tuple(builder.bind_calls)

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(read_one, questions))

    for raw, (plan, outputs, binds) in zip(questions, results):
        assert len(binds) == 1
        assert binds[0] == (plan, raw)
        assert all(item[2] == raw for item in outputs)
        assert plan.predicate == "*"
        assert {role for role, _ in plan.roles} == {"agent", "patient"}


def test_repeated_calls_do_not_retain_reader_allocations():
    raw = "誰が何を？"
    tracemalloc.start()
    try:
        for _ in range(20):
            _read(raw)
        gc.collect()
        before, _ = tracemalloc.get_traced_memory()
        for _ in range(1200):
            _read(raw)
        gc.collect()
        after, _ = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()

    assert after - before < 128 * 1024
