import pytest

from verantyx.semantic_ir import Pattern
from verantyx.semantic_wh import read_role_list_question


class RecordingBuilder:
    def __init__(self):
        self.roots = []
        self.outputs = []
        self.bindings = []
        self._next_variable = 0

    def variable(self):
        self._next_variable += 1
        return f"v{self._next_variable}"

    def bind(self, pattern, full):
        self.bindings.append((pattern, full))
        self.roots.append(pattern)

    def project(self, root):
        return root


def read(raw):
    builder = RecordingBuilder()
    plan = read_role_list_question(raw, builder, "full-question")
    return builder, plan


def test_plain_wh_roles_make_one_wildcard_bind():
    builder, plan = read("誰が何を")
    expected = Pattern("*", (("agent", "v1"), ("patient", "v2")))

    assert plan == expected
    assert builder.bindings == [(expected, "full-question")]
    assert builder.outputs == [
        ("誰が", "v1", "full-question", ""),
        ("何を", "v2", "full-question", ""),
    ]


def test_polite_and_punctuated_wh_form_preserves_roles():
    _, plain = read("誰が何を")
    _, polite = read("誰が何をですか？。")

    assert polite == plain


def test_reordering_wh_roles_preserves_the_asked_role_set():
    _, plan = read("何を誰が?")

    assert plan == Pattern("*", (("patient", "v1"), ("agent", "v2")))


def test_wh_spelling_variants_preserve_the_role_plan():
    _, kanji = read("誰が何を")
    _, kana = read("だれがなにを")

    assert kanji == kana


def test_agent_particle_variant_preserves_the_role_plan():
    _, ga = read("誰が何を")
    _, wa = read("誰は何を")

    assert ga == wa


def test_entity_swap_preserves_roles_when_particles_are_unchanged():
    _, person_agent = read("誰が何を")
    _, thing_agent = read("何が誰を")

    assert person_agent == thing_agent


def test_patient_to_recipient_particle_changes_the_plan():
    _, patient = read("誰が何を")
    _, recipient = read("誰が何に")

    assert patient == Pattern("*", (("agent", "v1"), ("patient", "v2")))
    assert recipient == Pattern("*", (("agent", "v1"), ("recipient", "v2")))
    assert patient != recipient


def test_role_noun_paraphrase_preserves_the_role_plan():
    _, giver = read("渡した人、物は？")
    _, sender = read("送り主、物は?")

    assert giver == sender


def test_recipient_role_noun_variants_preserve_the_role_plan():
    _, endpoint = read("物、終点は")
    _, recipient = read("物、受取人は")

    assert endpoint == recipient


def test_repeated_role_is_not_projected_as_a_distinct_role_list():
    builder, plan = read("誰がだれは?")

    assert plan is None
    assert builder.bindings == []
    assert builder.outputs == []


@pytest.mark.xfail(strict=False, reason="DEFECT: a single wh-marked role is rejected by the role-only-question reader")
def test_single_wh_role_is_a_role_only_question():
    results = [read("誰が？")[1] for _ in range(2)]

    assert all(result == Pattern("*", (("agent", "v1"),)) for result in results)
