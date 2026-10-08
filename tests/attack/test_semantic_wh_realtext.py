"""Contract probes for predicate-elided role questions."""

from verantyx.semantic_ir import Pattern
from verantyx.semantic_wh import read_role_list_question


class RecordingBuilder:
    def __init__(self):
        self.next_variable = 0
        self.roots = []
        self.bound_sources = []
        self.outputs = []

    def variable(self):
        self.next_variable += 1
        return self.next_variable

    def bind(self, pattern, full):
        self.roots.append(pattern)
        self.bound_sources.append(full)

    def project(self, root):
        return root


def read(raw):
    builder = RecordingBuilder()
    full = object()
    plan = read_role_list_question(raw, builder, full)
    return plan, builder, full


def assert_plan(raw, expected):
    plan, builder, full = read(raw)
    assert plan == builder.roots[0]
    assert builder.bound_sources == [full]
    assert builder.roots == [
        Pattern('*', tuple((role, i) for i, (_, role) in enumerate(expected, 1)))
    ]
    assert builder.outputs == [
        (label, i, full, '') for i, (label, _) in enumerate(expected, 1)
    ]


def test_wh_particles_map_to_agent_and_patient():
    assert_plan('誰が何を?', [('誰が', 'agent'), ('何を', 'patient')])


def test_wh_aliases_and_particle_map_to_agent_and_location():
    assert_plan('だれはどこでですか？', [('だれは', 'agent'), ('どこで', 'location')])


def test_origin_and_recipient_particles_are_preserved_in_order():
    assert_plan('何から何へ。', [('何から', 'origin'), ('何へ', 'recipient')])


def test_role_nouns_accept_long_labels():
    assert_plan('渡した人、受取人は？', [('渡した人', 'agent'), ('受取人', 'recipient')])


def test_role_nouns_map_patient_and_origin():
    assert_plan('物、起点は', [('物', 'patient'), ('起点', 'origin')])


def test_role_noun_synonyms_map_to_agent_and_recipient():
    assert_plan('送り主、終点は', [('送り主', 'agent'), ('終点', 'recipient')])


def test_surrounding_whitespace_is_ignored():
    assert_plan('  誰が何をですか？  ', [('誰が', 'agent'), ('何を', 'patient')])


def test_one_requested_role_does_not_make_a_role_list_plan():
    plan, builder, _ = read('誰が?')
    assert plan is None
    assert builder.roots == []
    assert builder.outputs == []


def test_duplicate_semantic_roles_are_rejected():
    plan, builder, _ = read('誰がだれは')
    assert plan is None
    assert builder.roots == []
    assert builder.outputs == []


def test_descriptive_prose_is_not_read_as_a_role_list_question():
    plan, builder, _ = read('富士山は日本の静岡県と山梨県にまたがる活火山である。')
    assert plan is None
    assert builder.roots == []
    assert builder.outputs == []


def test_mixed_role_noun_and_particle_question_shape_is_rejected():
    plan, builder, _ = read('物、起点が')
    assert plan is None
    assert builder.roots == []
    assert builder.outputs == []


def test_long_prose_input_returns_without_a_plan():
    plan, builder, _ = read(('日本の地名を説明する文章です。' * 2000))
    assert plan is None
    assert builder.roots == []
    assert builder.outputs == []
