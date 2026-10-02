import pytest

from verantyx.semantic_ir import Pattern
from verantyx.semantic_wh import read_role_list_question


class PlanBuilder:
    def __init__(self):
        self.next_variable = 0
        self.roots = []
        self.binds = []
        self.outputs = []
        self.projected = []

    def variable(self):
        value = f"v{self.next_variable}"
        self.next_variable += 1
        return value

    def bind(self, pattern, full):
        self.binds.append((pattern, full))
        root = object()
        self.roots.append(root)
        return root

    def project(self, root):
        self.projected.append(root)
        return root


@pytest.mark.parametrize(
    ("question", "asked"),
    [
        ("誰が何を", [("誰が", "agent"), ("何を", "patient")]),
        ("だれはなにを？", [("だれは", "agent"), ("なにを", "patient")]),
        (
            "誰が何をどこで誰にですか。",
            [
                ("誰が", "agent"),
                ("何を", "patient"),
                ("どこで", "location"),
                ("誰に", "recipient"),
            ],
        ),
        (
            "渡した人、物、受取人は",
            [("渡した人", "agent"), ("物", "patient"), ("受取人", "recipient")],
        ),
        (
            "起点、物、終点は？",
            [("起点", "origin"), ("物", "patient"), ("終点", "recipient")],
        ),
    ],
)
def test_role_only_questions_make_one_wildcard_plan(question, asked):
    builder = PlanBuilder()
    full = object()

    plan = read_role_list_question(question, builder, full)

    variables = [f"v{i}" for i in range(len(asked))]
    expected_pattern = Pattern(
        "*", tuple((role, variable) for (_, role), variable in zip(asked, variables))
    )
    assert builder.binds == [(expected_pattern, full)]
    assert builder.outputs == [
        (label, variable, full, "")
        for (label, _), variable in zip(asked, variables)
    ]
    assert builder.projected == [builder.roots[0]]
    assert plan is builder.roots[0]


@pytest.mark.parametrize(
    "question",
    [
        "いつ誰が何をした？",
        "今年、誰が何をした？",
        "今誰が何をする？",
        "昨日誰が何を渡した？",
        "2026年に誰が何を渡した？",
        "誰が何を何個渡した？",
        "誰が何をした後、誰に渡した？",
        "誰が何を先に渡した？",
    ],
)
def test_tense_time_date_quantity_and_order_questions_are_not_role_lists(question):
    builder = PlanBuilder()

    assert read_role_list_question(question, builder, object()) is None
    assert builder.binds == []
    assert builder.outputs == []
    assert builder.projected == []


def test_relative_time_words_alone_do_not_create_a_wildcard_plan():
    builder = PlanBuilder()

    assert read_role_list_question("今年", builder, object()) is None
    assert builder.binds == []


def test_single_role_is_not_promoted_to_a_role_list_plan():
    builder = PlanBuilder()

    assert read_role_list_question("誰が", builder, object()) is None
    assert builder.binds == []
