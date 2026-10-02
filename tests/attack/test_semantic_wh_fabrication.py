"""Attacks against role-only question reading and its provenance."""

import pytest

from verantyx.semantic_ir import Pattern
from verantyx.semantic_wh import read_role_list_question


class RecordingBuilder:
    def __init__(self):
        self.roots = []
        self.binds = []
        self.outputs = []
        self.project_calls = []
        self.projected = object()
        self._variables = 0

    def variable(self):
        variable = f"v{self._variables}"
        self._variables += 1
        return variable

    def bind(self, pattern, full):
        self.binds.append((pattern, full))
        self.roots.append(object())

    def project(self, root):
        self.project_calls.append(root)
        return self.projected


def assert_role_plan(raw, expected_roles):
    builder = RecordingBuilder()
    source = object()

    result = read_role_list_question(raw, builder, source)

    variables = [f"v{i}" for i in range(len(expected_roles))]
    expected_pattern = Pattern(
        "*", tuple((role, variable) for (_, role), variable in zip(expected_roles, variables))
    )
    assert result is builder.projected
    assert builder.binds == [(expected_pattern, source)]
    assert builder.project_calls == [builder.roots[0]]
    assert builder.outputs == [
        (label, variable, source, "")
        for (label, _), variable in zip(expected_roles, variables)
    ]


@pytest.mark.parametrize(
    ("raw", "expected_roles"),
    [
        ("誰が何を?", [("誰が", "agent"), ("何を", "patient")]),
        ("どこから誰へ？", [("どこから", "origin"), ("誰へ", "recipient")]),
        ("なにで誰に。", [("なにで", "location"), ("誰に", "recipient")]),
        ("送り主、物は", [("送り主", "agent"), ("物", "patient")]),
        ("起点、受取人は？", [("起点", "origin"), ("受取人", "recipient")]),
    ],
)
def test_roles_and_labels_are_taken_from_the_question(raw, expected_roles):
    assert_role_plan(raw, expected_roles)


@pytest.mark.parametrize(
    "raw",
    [
        "誰が",
        "誰がだれは?",  # two labels that both name the agent role
        "誰と何を?",  # unsupported particle
        "先行語誰が何を?",  # partial question span
        "誰が何を運んだ?",  # predicate and possible answer material
        "誰が何をしなかった？",  # negated predicate
        "物,起点は",  # unsupported list separator
        "物、誰がは",  # mixed role-noun and wh shapes
    ],
)
def test_non_role_only_or_ambiguous_shapes_do_not_make_a_plan(raw):
    builder = RecordingBuilder()

    assert read_role_list_question(raw, builder, object()) is None
    assert builder.binds == []
    assert builder.roots == []
    assert builder.outputs == []
    assert builder.project_calls == []


def test_outer_whitespace_does_not_change_role_labels_or_provenance():
    assert_role_plan("  誰が何を？  ", [("誰が", "agent"), ("何を", "patient")])
