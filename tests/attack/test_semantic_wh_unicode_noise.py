"""Unicode and noise attacks against the role-only semantic WH reader."""

from dataclasses import dataclass

import pytest

from verantyx import semantic_wh


@dataclass(frozen=True)
class CapturedPattern:
    predicate: str
    roles: tuple


class RecordingBuilder:
    def __init__(self):
        self.roots = [object()]
        self.outputs = []
        self.bindings = []
        self.variables = 0
        self.projected = object()

    def variable(self):
        self.variables += 1
        return f"v{self.variables}"

    def bind(self, pattern, full):
        self.bindings.append((pattern, full))

    def project(self, root):
        assert root is self.roots[0]
        return self.projected


@pytest.fixture(autouse=True)
def capture_ir_pattern(monkeypatch):
    monkeypatch.setattr(semantic_wh, "Pattern", CapturedPattern)


def read(raw, full="source-span"):
    builder = RecordingBuilder()
    result = semantic_wh.read_role_list_question(raw, builder, full)
    return result, builder


def assert_wildcard(builder, roles, labels, full="source-span"):
    assert len(builder.bindings) == 1
    pattern, bound_full = builder.bindings[0]
    assert pattern == CapturedPattern("*", tuple(roles))
    assert bound_full == full
    assert builder.outputs == [
        (label, variable, full, "")
        for label, (_, variable) in zip(labels, roles)
    ]


def test_full_width_wh_question_builds_ordered_wildcard_roles():
    full = object()
    result, builder = read("誰が何を？", full)

    assert result is builder.projected
    assert_wildcard(
        builder,
        [("agent", "v1"), ("patient", "v2")],
        ["誰が", "何を"],
        full,
    )


def test_role_noun_list_builds_wildcard_roles_and_keeps_surface_labels():
    result, builder = read("起点、終点は？")

    assert result is builder.projected
    assert_wildcard(
        builder,
        [("origin", "v1"), ("recipient", "v2")],
        ["起点", "終点"],
    )


def test_hiragana_wh_forms_and_location_particle_are_read_faithfully():
    result, builder = read("だれがどこで?")

    assert result is builder.projected
    assert_wildcard(
        builder,
        [("agent", "v1"), ("location", "v2")],
        ["だれが", "どこで"],
    )


def test_optional_politeness_and_allowed_terminal_punctuation_are_accepted():
    result, builder = read("誰が何をですか。")

    assert result is builder.projected
    assert_wildcard(
        builder,
        [("agent", "v1"), ("patient", "v2")],
        ["誰が", "何を"],
    )


@pytest.mark.parametrize(
    "raw",
    [
        "ﾀﾞﾚが何を?",  # half-width katakana
        "誰か\u3099何を?",  # decomposed dakuten in the case particle
        "誰\u200bが何を?",  # zero-width space inside a token boundary
        "誰が何ヲ?",  # katakana lookalike for the hiragana particle
        "<b>誰が何を?</b>",  # markup residue
        "誰が何を? :-) ",  # ASCII art residue
        "誰が何を? 😀",  # emoji residue
        "誰が何を?0",  # OCR-like trailing glyph
        "物､起点は?",  # half-width ideographic comma
    ],
)
def test_unicode_or_markup_noise_is_refused_without_partial_plan(raw):
    result, builder = read(raw)

    assert result is None
    assert builder.bindings == []
    assert builder.outputs == []
    assert builder.variables == 0


def test_canonically_equivalent_decomposed_particle_is_refused_safely():
    result, builder = read("誰か\u3099何を?")

    assert result is None
    assert builder.bindings == []
    assert builder.outputs == []


def test_mixed_script_noise_in_role_noun_list_is_refused():
    result, builder = read("物、起点ロは?")

    assert result is None
    assert builder.bindings == []
    assert builder.outputs == []


def test_duplicate_semantic_role_is_refused_even_with_distinct_labels():
    result, builder = read("誰がだれは?")

    assert result is None
    assert builder.bindings == []
    assert builder.outputs == []
