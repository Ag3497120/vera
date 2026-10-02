import pytest

from verantyx import semantic_wh


class PatternCall:
    def __init__(self, predicate, roles):
        self.predicate = predicate
        self.roles = roles


class RecordingBuilder:
    def __init__(self):
        self.roots = [object()]
        self.variables = []
        self.bind_calls = []
        self.outputs = []
        self.project_calls = []
        self.projected = object()

    def variable(self):
        value = f"v{len(self.variables)}"
        self.variables.append(value)
        return value

    def bind(self, pattern, full):
        self.bind_calls.append((pattern, full))

    def project(self, root):
        self.project_calls.append(root)
        return self.projected


@pytest.fixture
def builder(monkeypatch):
    monkeypatch.setattr(semantic_wh, "Pattern", PatternCall)
    return RecordingBuilder()


def assert_plan(raw, roles, labels, builder):
    full = object()
    root = builder.roots[0]

    result = semantic_wh.read_role_list_question(raw, builder, full)

    assert result is builder.projected
    assert len(builder.bind_calls) == 1
    pattern, bound_full = builder.bind_calls[0]
    assert isinstance(pattern, PatternCall)
    assert pattern.predicate == "*"
    expected_variables = [f"v{i}" for i in range(len(roles))]
    assert pattern.roles == tuple(
        (role, variable) for role, variable in zip(roles, expected_variables)
    )
    assert bound_full is full
    assert builder.outputs == [
        (label, variable, full, "")
        for label, variable in zip(labels, expected_variables)
    ]
    assert builder.project_calls == [root]


def assert_unhandled_without_plan(raw, builder):
    result = semantic_wh.read_role_list_question(raw, builder, object())

    assert result is None
    assert builder.variables == []
    assert builder.bind_calls == []
    assert builder.outputs == []
    assert builder.project_calls == []


def test_wh_case_question_builds_wildcard_for_asked_roles(builder):
    assert_plan("誰が何を？", ["agent", "patient"], ["誰が", "何を"], builder)


def test_wh_origin_and_recipient_question_keeps_role_order(builder):
    assert_plan("何から誰へですか？", ["origin", "recipient"], ["何から", "誰へ"], builder)


def test_role_noun_question_builds_wildcard_for_listed_roles(builder):
    assert_plan("渡した人、物は？", ["agent", "patient"], ["渡した人", "物"], builder)


def test_role_noun_question_accepts_other_distinct_roles(builder):
    assert_plan("物、起点は？", ["patient", "origin"], ["物", "起点"], builder)


def test_outer_whitespace_does_not_change_role_question(builder):
    assert_plan("  誰が何をですか？  ", ["agent", "patient"], ["誰が", "何を"], builder)


@pytest.mark.parametrize(
    "raw",
    [
        "誰が何を渡さなかった？",       # negated predicate
        "誰が何をしないわけではない？", # double negation
        "誰が何をいらない？",           # いらない, adjective-like negative
        "誰が何をすべき？",             # obligation
        "誰が何をしてもいい？",         # permission
        "誰が何をしてはいけない？",     # prohibition
        "誰が何をしたそうだ？",         # hearsay / report
        "誰が何を渡した。",             # assertion
    ],
)
def test_predicate_negation_modality_and_assertions_are_not_role_only_plans(raw, builder):
    assert_unhandled_without_plan(raw, builder)


@pytest.mark.parametrize("raw", ["誰が？", "誰が誰は？"])
def test_single_or_duplicate_semantic_roles_do_not_make_a_plan(raw, builder):
    assert_unhandled_without_plan(raw, builder)
