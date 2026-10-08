import pytest

from verantyx.semantic_wh import read_role_list_question


class RecordingBuilder:
    def __init__(self):
        self.roots = [object()]
        self.bound = []
        self.outputs = []
        self.projected = object()
        self.projected_roots = []
        self._next_variable = 0

    def variable(self):
        variable = f"v{self._next_variable}"
        self._next_variable += 1
        return variable

    def bind(self, pattern, full):
        self.bound.append((pattern, full))

    def project(self, root):
        self.projected_roots.append(root)
        return self.projected


def assert_plan(builder, result, full, expected):
    assert result is builder.projected
    assert len(builder.bound) == 1
    pattern, bound_full = builder.bound[0]
    assert bound_full is full
    assert pattern.predicate == "*"
    assert [role for role, _ in pattern.roles] == [role for _, role in expected]
    assert [variable for _, variable in pattern.roles] == [
        f"v{index}" for index in range(len(expected))
    ]
    assert builder.outputs == [
        (label, f"v{index}", full, "")
        for index, (label, _) in enumerate(expected)
    ]
    assert builder.projected_roots == [builder.roots[0]]


def test_case_marked_question_builds_one_wildcard_bind():
    builder = RecordingBuilder()
    full = object()

    result = read_role_list_question("誰が何を", builder, full)

    assert_plan(builder, result, full, [("誰が", "agent"), ("何を", "patient")])


@pytest.mark.parametrize(
    ("question", "expected"),
    [
        ("だれはなにを", [("だれは", "agent"), ("なにを", "patient")]),
        ("何が誰に", [("何が", "agent"), ("誰に", "recipient")]),
        ("どこで何から", [("どこで", "location"), ("何から", "origin")]),
        ("なにへ誰で", [("なにへ", "recipient"), ("誰で", "location")]),
    ],
)
def test_case_particle_aliases_keep_their_declared_roles(question, expected):
    builder = RecordingBuilder()
    full = object()

    result = read_role_list_question(question, builder, full)

    assert_plan(builder, result, full, expected)


def test_role_noun_list_builds_roles_in_question_order():
    builder = RecordingBuilder()
    full = object()

    result = read_role_list_question("送り主、物、起点、終点は。", builder, full)

    assert_plan(
        builder,
        result,
        full,
        [("送り主", "agent"), ("物", "patient"), ("起点", "origin"), ("終点", "recipient")],
    )


def test_case_question_accepts_optional_question_ending():
    builder = RecordingBuilder()
    full = object()

    result = read_role_list_question("誰が何にですか？。", builder, full)

    assert_plan(builder, result, full, [("誰が", "agent"), ("何に", "recipient")])


def test_long_multi_document_context_is_carried_without_changing_the_plan():
    repeated = "太郎が花子に本を渡した。"
    near_duplicate = "太郎は花子に本を渡した。"
    contradiction = "太郎が本を渡した。太郎は本を渡さなかった。"
    long_sentence = "太郎が本を渡した" + "、その後も花子が本を受け取った" * 8000 + "。"
    full = "\n".join(
        [repeated] * 40 + [near_duplicate] * 40 + [contradiction] * 40 + [long_sentence]
    )
    builder = RecordingBuilder()

    result = read_role_list_question("誰が何を?", builder, full)

    assert_plan(builder, result, full, [("誰が", "agent"), ("何を", "patient")])
    assert len(full) > 100_000


def test_long_repeated_role_question_abstains_without_partial_bindings():
    builder = RecordingBuilder()
    full = object()
    question = "誰が" * 2048 + "何を"

    result = read_role_list_question(question, builder, full)

    assert result is None
    assert builder.bound == []
    assert builder.outputs == []
    assert builder.projected_roots == []


@pytest.mark.parametrize(
    "question",
    [
        "誰が",
        "誰がだれは何を",
        "物、物は",
        "誰が誰と何を",
        "誰が何をしたの？",
        "",
    ],
)
def test_non_role_list_shapes_or_duplicate_roles_return_none(question):
    builder = RecordingBuilder()

    result = read_role_list_question(question, builder, object())

    assert result is None
    assert builder.bound == []
    assert builder.outputs == []
    assert builder.projected_roots == []
