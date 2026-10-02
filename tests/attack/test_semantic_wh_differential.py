from itertools import combinations, product

import pytest

from verantyx.semantic_wh import read_role_list_question


FULL = object()
WH_WORDS = ("誰", "だれ", "何", "なに", "どこ")
CASE_PARTICLES = {
    "が": "agent",
    "は": "agent",
    "を": "patient",
    "に": "recipient",
    "へ": "recipient",
    "で": "location",
    "から": "origin",
}
ROLE_NOUNS = {
    "物": "patient",
    "起点": "origin",
    "終点": "recipient",
    "受取人": "recipient",
    "渡した人": "agent",
    "送り主": "agent",
}


class RecordingBuilder:
    def __init__(self):
        self.next_variable = 0
        self.binds = []
        self.roots = []
        self.outputs = []
        self.projected = []

    def variable(self):
        value = "v{}".format(self.next_variable)
        self.next_variable += 1
        return value

    def bind(self, pattern, full):
        self.binds.append((pattern, full))
        self.roots.append(len(self.roots))

    def project(self, root):
        self.projected.append(root)
        return ("projected", root)


def _peel_question_ending(raw):
    body = raw.strip()
    while body and body[-1] in "？?。":
        body = body[:-1]
    if body.endswith("ですか"):
        body = body[:-3]
    return body


def _read_wh_case_pairs(body):
    """Naively consume alternating wh words and case particles from the left."""
    cursor = 0
    pairs = []
    while cursor < len(body):
        word = next((w for w in WH_WORDS if body.startswith(w, cursor)), None)
        if word is None:
            return None
        cursor += len(word)
        particle = next(
            (p for p in sorted(CASE_PARTICLES, key=len, reverse=True) if body.startswith(p, cursor)),
            None,
        )
        if particle is None:
            return None
        cursor += len(particle)
        pairs.append((word + particle, CASE_PARTICLES[particle]))
    return pairs or None


def _read_role_noun_list(body):
    if not body.endswith("は"):
        return None
    labels = body[:-1].split("、")
    if not labels or any(label not in ROLE_NOUNS for label in labels):
        return None
    return [(label, ROLE_NOUNS[label]) for label in labels]


def reference_roles(raw):
    """Independent contract model: accepted labels paired with semantic roles."""
    body = _peel_question_ending(raw)
    pairs = _read_wh_case_pairs(body)
    if pairs is None:
        pairs = _read_role_noun_list(body)
    if pairs is None or len(pairs) < 2:
        return None
    roles = [role for _, role in pairs]
    if len(set(roles)) != len(roles):
        return None
    return pairs


def assert_matches_reference(raw):
    expected = reference_roles(raw)
    builder = RecordingBuilder()
    result = read_role_list_question(raw, builder, FULL)

    if expected is None:
        assert result is None
        assert builder.binds == []
        assert builder.outputs == []
        assert builder.projected == []
        assert builder.next_variable == 0
        return

    assert result == ("projected", 0)
    assert len(builder.binds) == 1
    pattern, full = builder.binds[0]
    variables = [(label, role, "v{}".format(i)) for i, (label, role) in enumerate(expected)]
    assert pattern.predicate == "*"
    assert pattern.roles == tuple((role, variable) for _, role, variable in variables)
    assert pattern.polarity == "+"
    assert pattern.modality == "assert"
    assert pattern.time == ""
    assert pattern.event is None
    assert full is FULL
    assert builder.outputs == [(label, variable, FULL, "") for label, _, variable in variables]
    assert builder.projected == [0]
    assert builder.next_variable == len(expected)


def _generated_distinct_role_questions():
    particles_by_role = {}
    for particle, role in CASE_PARTICLES.items():
        particles_by_role.setdefault(role, []).append(particle)
    roles = tuple(particles_by_role)
    endings = ("", "ですか", "?", "？。")
    for role_a, role_b in combinations(roles, 2):
        for wh_a, particle_a, wh_b, particle_b in product(
            WH_WORDS,
            particles_by_role[role_a],
            WH_WORDS,
            particles_by_role[role_b],
        ):
            for ending in endings:
                yield "  {}{}{}{}{}  ".format(wh_a, particle_a, wh_b, particle_b, ending)


def test_generated_wh_case_sequences_match_independent_reference():
    for raw in _generated_distinct_role_questions():
        assert_matches_reference(raw)


def test_role_noun_lists_match_reference_and_preserve_label_order():
    labels = tuple(ROLE_NOUNS)
    for first, second in combinations(labels, 2):
        assert_matches_reference("{}、{}は？".format(first, second))


def test_all_surface_words_and_case_particles_map_to_their_contract_roles():
    cases = (
        ("誰が何を", ("agent", "patient")),
        ("だれはどこで", ("agent", "location")),
        ("何に誰から", ("recipient", "origin")),
        ("どこへ何で", ("recipient", "location")),
        ("物、起点は", ("patient", "origin")),
        ("終点、送り主は", ("recipient", "agent")),
    )
    for raw, expected_roles in cases:
        assert tuple(role for _, role in reference_roles(raw)) == expected_roles
        assert_matches_reference(raw)


def test_valid_question_emits_one_wildcard_bind_and_one_output_per_requested_role():
    assert_matches_reference("何が誰をどこでですか？")


@pytest.mark.parametrize(
    "raw",
    (
        "誰が",
        "物は",
        "誰が何は",
        "受取人、終点は",
    ),
)
def test_single_or_duplicate_semantic_roles_abstain(raw):
    assert reference_roles(raw) is None
    assert_matches_reference(raw)


@pytest.mark.parametrize(
    "raw",
    (
        "何が誰を誰に",
        "起点、物、終点は",
        "だれから何へどこで",
    ),
)
def test_three_distinct_roles_are_supported_and_keep_source_order(raw):
    assert_matches_reference(raw)


@pytest.mark.parametrize(
    "raw",
    (
        "誰が何",
        "誰が、何を",
        "物と起点は",
        "物、起点が",
        "誰が何を?ですか",
        "誰 が何を",
    ),
)
def test_near_miss_shapes_return_none_without_partial_plan(raw):
    assert reference_roles(raw) is None
    assert_matches_reference(raw)


def test_outer_whitespace_and_allowed_trailing_punctuation_are_accepted():
    for suffix in ("", "ですか", "?", "？", "。", "ですか？。"):
        assert_matches_reference("  何が誰を{}  ".format(suffix))
