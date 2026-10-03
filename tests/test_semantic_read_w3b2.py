"""W3-b2: the second step of reading by the type of a word (the coarse placement): the frame of a predicate (W3-a3) narrows, a split answer whose every
candidate fits is read (`AGREE_ALL_CANDIDATES`), `X の Y` is typed by its head, and この・その are written as a mark of the filler. The tables and rules were registered in
docs/READING_SOUNDNESS.md section 10B (K94-K99) before the data (w3b2_*.jsonl) and this file were written.

Placement answers here come from fakes (tests/reading_soundness/w3b2_fakes.py, w3b1_fakes.py) and from the fixture of the placement r6; no real placement is opened.
Run under a clean environment (env -i): a VERA_PLACEMENT left in the shell would change the default path of the entry.
"""
import ast
import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

TREE = Path(__file__).resolve().parent.parent
RS = TREE / 'tests' / 'reading_soundness'
BASE_COMMIT = '3b31258'    # dev: the commit W3-b2 starts from


def _load_by_path(name, path):
    """Load a helper module by its path under a unique name (sys.path is NOT changed: see the note of tests/test_semantic_read_w3b1.py)."""
    if name in sys.modules: return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, str(path))
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


F = _load_by_path('w3b2_fakes_in_test', RS / 'w3b2_fakes.py')
COMMON = _load_by_path('w3b2_common_in_test', RS / 'w3b2_common.py')

from tools.bank_score.v2 import b1    # noqa: E402
from verantyx import semantic_read as SR    # noqa: E402
from verantyx import semantic_reader as R    # noqa: E402

DOCS = (TREE / 'docs' / 'READING_SOUNDNESS.md').read_text(encoding='utf-8')


@pytest.fixture(autouse=True)
def _no_placement_in_the_environment(monkeypatch):
    monkeypatch.delenv('VERA_PLACEMENT', raising=False)
    monkeypatch.delenv('VERA_COARSE_PLACEMENT', raising=False)


def git(*args):
    return subprocess.run(['git', '-C', str(TREE)] + list(args), capture_output=True, check=True).stdout.decode('utf-8')


def _base_module():
    """The reading entry of the base commit (its own control flow), on top of the reader of this tree (the base functions that it calls are unchanged)."""
    src = git('show', '%s:verantyx/semantic_read.py' % BASE_COMMIT)
    spec = importlib.util.spec_from_loader('verantyx._semantic_read_base_w3b2', loader=None)
    mod = importlib.util.module_from_spec(spec)
    mod.__package__ = 'verantyx'
    sys.modules[spec.name] = mod
    exec(compile(src, 'verantyx/semantic_read.py@%s' % BASE_COMMIT, 'exec'), mod.__dict__)
    return mod


BASE = _base_module()


def block(name):
    m = re.search(r'<!-- BEGIN table:%s -->\n(.*?)<!-- END table:%s -->' % (name, name), DOCS, re.S)
    assert m, name
    return [line for line in m.group(1).splitlines() if line.startswith('|') and not set(line) <= set('|- ')][1:]


def first_cells(name):
    """The first cell of every row of a docs table (a cell may hold a `|` that has no blank beside it: the rule names of K94; cells are cut at ' | ')."""
    return [re.split(r' \| ', line.strip()[1:-1].strip())[0].strip().strip('`') for line in block(name)]


def tokens_of(text):
    """The tokens of the reader with their features read at once: the tagger's nodes are valid until the next parse (a `document_view` after `_tokens` would leave the features
    of the earlier tokens unread and wrong). The entry reads them in its own order before it asks for the view; a test that calls a plan on its own must do the same."""
    toks = R._tokens(text)
    for w, a, b in toks: w.feature.pos1, w.feature.pos2, w.feature.pos3
    return toks


def P(top, by=('seed',), **kw):
    return F.answer(top, decided_by=list(by), **kw)


def Q(mapping):
    return F.MapQuery(mapping)


def pair(text, mapping):
    """(this tree's output, the base commit's output) with two fresh, equal fakes."""
    return SR.read(text, placement=Q(mapping)), BASE.read(text, placement=Q(mapping))


def reasons(out):
    assert out['readable'] is False, out
    return out['abstain']['reasons']


GA = ('hearst@x', 'role@y')           # arms that are not only role distributions (an adjunct may use them)
ROLE_ONLY = ('role@x', 'role@y')      # arms that are only role distributions (an adjunct may not)


def u3_map(**over):
    m = {'兄': P('PERSON'), '校庭': P('PLACE', by=('definition', 'role@y')), '走る': P('P_MOVE')}
    m.update(over)
    return m


# ===================================================================================================================================
# K94 / K99: the tables of the docs are the constants of the code; what the base commit has is not changed
# ===================================================================================================================================
def test_the_ambiguous_rules_of_u3_are_the_two_of_the_docs():
    assert list(R.W3B2_AMBIGUOUS_RULES) == first_cells('w3b2_ambiguous_rules') == ['case:で:place|means', 'case:に:location|goal|time']


def test_the_demonstratives_are_the_three_of_the_ticket_and_not_the_question_word():
    assert list(R.W3B2_DEMONSTRATIVES) == [r.strip('|` ') for r in block('w3b2_demonstratives')] == ['この', 'その', 'あの']
    assert 'どの' in SR._DEMONSTRATIVES and 'どの' not in R.W3B2_DEMONSTRATIVES


def test_the_relational_pos3_are_the_two_of_the_docs():
    assert list(R.W3B2_HEAD_RELATIONAL_POS3) == [r.strip('|` ') for r in block('w3b2_head_relational_pos3')] == ['副詞可能', '助数詞可能']


def test_the_reasons_of_the_docs_are_the_names_of_the_code_in_the_same_order():
    names = [c.split(':')[0].strip() for c in first_cells('w3b2_reasons')]    # the name is what stands before the first colon
    assert names == list(R.W3B2_REASON_NAMES)
    assert len(names) == len(set(names)) == 8


def test_the_role_basis_grammar_is_the_one_of_the_docs_and_accepts_exactly_the_four_forms():
    assert 'placement_(direct|all_candidates)(_head)?:[A-Z_]+(\\+[A-Z_]+)*' in DOCS
    rx = re.compile(R.W3B2_ROLE_BASIS_RE)
    for ok in ('placement_direct:PLACE', 'placement_direct_head:PLACE', 'placement_all_candidates:GROUP_ORG+PERSON', 'placement_all_candidates_head:ABSTRACT+PERSON'):
        assert rx.fullmatch(ok), ok
    for bad in ('placement_direct:', 'placement_direct:place', 'placement_estimated:PLACE', 'placement_direct_head_head:PLACE', 'placement_all_candidates:GROUP_ORG+'):
        assert not rx.fullmatch(bad), bad


def _literal(source, name):
    for node in ast.parse(source).body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == name for t in node.targets):
            return ast.literal_eval(node.value)
    raise AssertionError(name)


def test_the_tables_of_w3b1_are_not_widened():
    base_src = git('show', '%s:verantyx/semantic_reader.py' % BASE_COMMIT)
    for name in ('TYPED_FRAMES', 'TYPED_FRAMES_NOT_READ', 'PLACEMENT_PART_CONSTRUCTIONS', 'W3B1_MARKERS_JA', 'DERIVED_GATE'):
        assert _literal(base_src, name) == getattr(R, name), name


def test_the_gate_of_w3b1_and_its_triggers_and_plans_are_the_same_source_as_at_the_base_commit():
    base_src, now = git('show', '%s:verantyx/semantic_reader.py' % BASE_COMMIT), (TREE / 'verantyx' / 'semantic_reader.py').read_text(encoding='utf-8')

    def seg(src, name):
        for node in ast.parse(src).body:
            if isinstance(node, (ast.FunctionDef, ast.ClassDef)) and node.name == name: return ast.get_source_segment(src, node)
        raise AssertionError(name)
    for name in ('placement_type', 'typed_trigger_ja', 'typed_plan_u_ja', 'typed_plan_s4_ja', 'typed_tail_ja', 'typed_head_derived_ja', 'CoarseQuery',
                 '_placement_answer_problems', '_Asker', '_w3b1_marker'):
        assert seg(base_src, name) == seg(now, name), name


def test_the_reader_file_only_gains_lines():
    diff = git('diff', BASE_COMMIT, '--', 'verantyx/semantic_reader.py').splitlines()
    removed = [l for l in diff if l.startswith('-') and not l.startswith('---')]
    assert removed == []


def test_the_functions_of_the_entry_that_are_not_the_typed_reread_are_the_base_commits():
    base_src, now = git('show', '%s:verantyx/semantic_read.py' % BASE_COMMIT), (TREE / 'verantyx' / 'semantic_read.py').read_text(encoding='utf-8')

    def fns(src):
        return {n.name: ast.get_source_segment(src, n) for n in ast.parse(src).body if isinstance(n, (ast.FunctionDef, ast.ClassDef))}
    b, n = fns(base_src), fns(now)
    assert [k for k in b if k not in n] == []
    assert [k for k in b if b[k] != n[k]] == ['_read_ja', '_typed_reread_ja']    # W3-b3 (docs/READING_SOUNDNESS.md 10C K114): the two lines of `_read_ja` that call the typed re-reading and, when it refuses, the path of two predicates
    assert set(n) - set(b) >= {'typed_explain_ja'}


# ===================================================================================================================================
# K95: placement_fit (the gate with a set of allowed types) and the frame of a predicate
# ===================================================================================================================================
PLACE = {'PLACE'}
AGENT = {'PERSON', 'GROUP_ORG', 'ANIMAL'}


def test_fit_direct_inside_and_outside_the_allowed_set():
    assert R.placement_fit(P('PERSON'), AGENT) == ('direct', ('PERSON',))
    assert R.placement_fit(P('PLACE'), AGENT) == ('mismatch', ('PLACE',))


def test_fit_a_split_answer_whose_every_candidate_is_allowed_is_all_candidates_in_alphabetical_order():
    assert R.placement_fit(P(['PERSON', 'GROUP_ORG']), AGENT) == ('all_candidates', ('GROUP_ORG', 'PERSON'))
    assert R.placement_fit(P(['PERSON', 'GROUP_ORG', 'ANIMAL']), AGENT) == ('all_candidates', ('ANIMAL', 'GROUP_ORG', 'PERSON'))


def test_fit_a_split_answer_with_one_candidate_outside_is_the_reason_of_w3b1_with_the_same_text():
    for top in (['PERSON', 'ABSTRACT'], ['PLACE', 'GROUP_ORG'], ['TIME', 'PLACE']):
        assert R.placement_fit(P(top), AGENT) == (None, 'PLACEMENT_MULTIPLE')
        assert R.placement_type(P(top)) == (None, 'PLACEMENT_MULTIPLE')


def test_fit_an_estimated_split_is_the_estimated_reason_even_when_every_candidate_fits():
    near = F.to_estimated(P(['PERSON', 'GROUP_ORG']), 'proximity')
    gen = F.to_estimated(P(['PERSON', 'GROUP_ORG']), 'generated')
    assert R.placement_fit(near, AGENT) == (None, 'PLACEMENT_ESTIMATED_NEAR')
    assert R.placement_fit(gen, AGENT) == (None, 'PLACEMENT_ESTIMATED_GENERATED')


def test_fit_a_split_answer_a_generated_definition_decided_is_not_used():
    assert R.placement_fit(P(['PERSON', 'GROUP_ORG'], by=('gen_definition',)), AGENT) == (None, 'PLACEMENT_DIRECT_VIA_GENERATED')


def test_fit_an_adjunct_decided_only_by_role_distributions_is_not_used_split_or_not():
    assert R.placement_fit(P('PLACE', by=ROLE_ONLY), PLACE, adjunct=True) == (None, 'PLACEMENT_SLOT_EVIDENCE_ONLY')
    assert R.placement_fit(P(['PLACE', 'TIME'], by=ROLE_ONLY), {'PLACE', 'TIME'}, adjunct=True) == (None, 'PLACEMENT_SLOT_EVIDENCE_ONLY')
    assert R.placement_fit(P('PLACE', by=ROLE_ONLY), PLACE) == ('direct', ('PLACE',))     # an argument may use them
    assert R.placement_fit(P('PLACE', by=GA), PLACE, adjunct=True) == ('direct', ('PLACE',))


def test_fit_the_other_reasons_are_the_reasons_of_the_gate():
    assert R.placement_fit(F.bare('UNKNOWN'), PLACE) == (None, 'PLACEMENT_UNKNOWN')
    assert R.placement_fit(F.bare('UNPLACED'), PLACE) == (None, 'PLACEMENT_UNPLACED')
    assert R.placement_fit(F.bare('NO_PLACEMENT', 'UNSET'), PLACE) == (None, 'PLACEMENT_NO_PLACEMENT:UNSET')
    broken = P(['PERSON', 'GROUP_ORG']); broken['state'] = 'DECIDED'
    assert R.placement_fit(broken, AGENT)[0] is None and R.placement_fit(broken, AGENT)[1].startswith('PLACEMENT_INVALID:')
    assert R.placement_fit('not a mapping', AGENT)[1].startswith('PLACEMENT_INVALID:')


def test_predicate_frame_without_a_frame_status_or_not_confirmed_is_the_table_only():
    assert R.predicate_frame(P('P_MOVE')) == ('table', None)
    for status in ('NOT_CONFIRMED', 'NO_FRAME_TABLE'):
        assert R.predicate_frame(F.with_frame(P('P_MOVE'), status)) == ('table', None)


def test_predicate_frame_confirmed_gives_the_particles_and_the_types_as_sets():
    a = F.with_frame(P('P_MOVE', by=('gen_frame', 'role_distribution@x'), ), 'CONFIRMED', {'が': ['ANIMAL', 'PERSON'], 'へ': ['PLACE']})
    a['namespace'] = 'P'
    assert R.predicate_frame(a) == ('confirmed', {'が': frozenset({'ANIMAL', 'PERSON'}), 'へ': frozenset({'PLACE'})})


@pytest.mark.parametrize('mutate, problem', [
    (lambda a: a.update(namespace='N'), 'NAMESPACE_NOT_P'),
    (lambda a: a.update(origin='estimated', estimate_basis='proximity', constructed=True), 'NOT_DECIDED_DIRECT'),
    (lambda a: a.update(decided_by=['seed']), 'GEN_FRAME_NOT_IN_DECIDED_BY'),
    (lambda a: a.update(frame=['が']), 'FRAME_NOT_A_MAPPING'),
    (lambda a: a.update(frame={'を': ['PLACE'], 'ほか': ['PLACE']}), 'PARTICLE_NOT_CASE:ほか'),
    (lambda a: a.update(frame={'を': []}), 'TYPES_NOT_A_SORTED_LIST:を'),
    (lambda a: a.update(frame={'を': ['PLACE', 'ANIMAL']}), 'TYPES_NOT_A_SORTED_LIST:を'),
    (lambda a: a.update(frame={'を': ['PLACE', 'PLACE']}), 'TYPES_NOT_A_SORTED_LIST:を'),
    (lambda a: a.update(frame_status='ESTIMATED'), 'FRAME_STATUS_UNEXPECTED'),
])
def test_predicate_frame_that_breaks_the_invariants_of_section_12_10_is_invalid(mutate, problem):
    a = F.with_frame(P('P_MOVE', by=('gen_frame', 'role_distribution@x')), 'CONFIRMED', {'を': ['PLACE']})
    a['namespace'] = 'P'
    mutate(a)
    assert R.predicate_frame(a) == (None, 'PLACEMENT_FRAME_INVALID:' + problem)


# ===================================================================================================================================
# K94: U3 (the で of a clause the reader leaves ambiguous)
# ===================================================================================================================================
def test_u3_reads_a_place_with_the_type_of_a_place_and_says_where_every_role_came_from():
    out = SR.read('兄が校庭で走った。', placement=Q(u3_map()))
    assert out['readable'] is True
    c = out['clauses'][0]
    assert c['predicate'] == '走る' and c['roles'] == {'agent': '兄', 'place': '校庭'} and c['voice'] == 'active' and c['tense'] == 'past'
    assert c['predicate_basis'] == 'placement_direct:P_MOVE' and c['role_basis'] == {'agent': 'placement_direct:PERSON', 'place': 'placement_direct:PLACE'}
    assert list(c)[-2:] == ['predicate_basis', 'role_basis'] and 'role_flags' not in c
    ex = SR.typed_explain_ja('兄が校庭で走った。', Q(u3_map()))
    assert ex == {'w3b1_trigger': None, 'w3b1': None, 'w3b2_trigger': 'U3', 'w3b2': 'READ', 'frame': None}


def test_u3_without_a_placement_is_the_same_refusal_as_always():
    assert SR.read('兄が校庭で走った。', placement=None) == BASE.read('兄が校庭で走った。', placement=None)
    out = SR.read('兄が校庭で走った。', placement=None)
    assert reasons(out) == ['NO_SUPPORTED_CLAUSE'] and out['unsupported'][0]['reasons'] == ['ambiguous case role: で']


def test_u3_with_a_patient_of_a_type_the_table_holds_and_a_time_with_ni():
    m = u3_map(**{'弟': P('PERSON'), '呼ぶ': P('P_COMMUNICATE'), '夜': P('TIME', by=('definition',))})
    out = SR.read('兄が校庭で弟を呼んだ。', placement=Q(m))
    c = out['clauses'][0]
    assert c['roles'] == {'agent': '兄', 'place': '校庭', 'patient': '弟'} and c['predicate_basis'] == 'placement_direct:P_COMMUNICATE'
    out = SR.read('兄が夜に校庭で走った。', placement=Q(m))
    c = out['clauses'][0]
    assert c['roles'] == {'agent': '兄', 'time': '夜', 'place': '校庭'} and c['role_basis']['time'] == 'placement_direct:TIME'


@pytest.mark.parametrize('noun, answer, why', [
    ('杖', P('ARTIFACT', by=('definition',)), 'PLACEMENT_TYPE_MISMATCH'),
    ('窓口', P(['ABSTRACT', 'PLACE'], by=GA), 'PLACEMENT_MULTIPLE'),
    ('廊下', P('PLACE', by=ROLE_ONLY), 'PLACEMENT_SLOT_EVIDENCE_ONLY'),
    ('受付', P(['IDENTIFIER', 'PLACE'], by=ROLE_ONLY), 'PLACEMENT_SLOT_EVIDENCE_ONLY'),
    ('テラス', P('PLACE', by=('gen_definition', 'role@x')), 'PLACEMENT_DIRECT_VIA_GENERATED'),
    ('蔵', F.to_estimated(P('PLACE'), 'generated'), 'PLACEMENT_ESTIMATED_GENERATED'),
    ('土間', F.bare('UNPLACED'), 'PLACEMENT_UNPLACED'),
])
def test_u3_does_not_read_a_place_that_is_not_a_place_in_the_registered_sense(noun, answer, why):
    text = '兄が%sで走った。' % noun
    m = u3_map(**{noun: answer})
    new, base = pair(text, m)
    assert new == base and new['readable'] is False and reasons(new) == ['NO_SUPPORTED_CLAUSE']
    assert SR.typed_explain_ja(text, Q(m))['w3b2'].startswith(why)


def test_u3_does_not_read_when_the_predicate_is_not_of_a_type_the_table_reads_or_is_split():
    for pred, top, why in (('遊ぶ', 'P_ACT', 'PLACEMENT_FRAME_NOT_READ:P_ACT'), ('眠る', 'P_EXIST', 'PLACEMENT_FRAME_NOT_READ:P_EXIST')):
        m = u3_map(**{pred: P(top)})
        text = '兄が校庭で%s。' % {'遊ぶ': '遊んだ', '眠る': '眠った'}[pred]
        new, base = pair(text, m)
        assert new == base and not new['readable']
        assert SR.typed_explain_ja(text, Q(m))['w3b2'] == why
    m = u3_map(**{'走る': P(['P_MOVE', 'P_ACT'])})            # a predicate that is split is never an "all candidates"
    new, base = pair('兄が校庭で走った。', m)
    assert new == base and not new['readable'] and SR.typed_explain_ja('兄が校庭で走った。', Q(m))['w3b2'] == 'PLACEMENT_MULTIPLE:predicate:走る'


def test_u3_is_asked_only_for_the_two_registered_rules_and_asks_nothing_before_it_is_decided():
    # does not look at a clause the reader splits some other way: `case:に:result|beneficiary`, an `ambiguous frame role` (は), a quantifier
    for text in ('兄が弟に作文を直した。', '猫は庭へ歩いた。', '兄が校庭ですべて走った。'):
        q = Q(u3_map())
        out = SR.read(text, placement=q)
        assert out['readable'] is False and q.calls == [], text
        assert out == BASE.read(text, placement=Q(u3_map())), text
    ex = SR.typed_explain_ja('兄が弟に作文を直した。', Q({}))
    assert ex['w3b1_trigger'] is None and ex['w3b2_trigger'] is None and ex['w3b2'] == 'PLACEMENT_W3B2_NOT_TRIGGERED'


def test_u3_does_not_take_a_predicate_of_the_four_lists_of_the_reader():
    for text in ('兄が校庭で渡した。', '兄が校庭で話した。'):          # 渡す・話す: a verb of transfer / telling
        q = Q(u3_map(**{'渡す': P('P_GIVE'), '話す': P('P_COMMUNICATE')}))
        assert SR.read(text, placement=q) == BASE.read(text, placement=Q(u3_map(**{'渡す': P('P_GIVE'), '話す': P('P_COMMUNICATE')})))


def test_u3_does_not_override_a_role_the_reader_decided_with_another_name():
    # the reader reads the time word 夜 as `time`; the table says the same, so the sentence is read; a table that said otherwise would be `PLACEMENT_READER_DISAGREES`
    m = u3_map(**{'夜': P('TIME', by=('definition',))})
    assert SR.typed_explain_ja('兄が夜に校庭で走った。', Q(m))['w3b2'] == 'READ'


# ===================================================================================================================================
# R3: a split answer with a candidate that does not fit is never read (U, U3, S4 / D2), and every candidate that fits is
# ===================================================================================================================================
def u_map(**over):
    m = {'兄': P('PERSON'), '庭': P('PLACE'), '走る': P('P_MOVE'), '家族': P(['GROUP_ORG', 'PERSON'], by=GA)}
    m.update(over)
    return m


def test_u_reads_a_split_agent_when_every_candidate_is_in_the_agents_set_and_says_so():
    out = SR.read('家族が庭へ走った。', placement=Q(u_map()))
    assert out['readable'] is True
    c = out['clauses'][0]
    assert c['roles'] == {'agent': '家族', 'goal': '庭'}
    assert c['role_basis'] == {'agent': 'placement_all_candidates:GROUP_ORG+PERSON', 'goal': 'placement_direct:PLACE'} and c['predicate_basis'] == 'placement_direct:P_MOVE'
    ex = SR.typed_explain_ja('家族が庭へ走った。', Q(u_map()))
    assert ex == {'w3b1_trigger': 'U', 'w3b1': 'PLACEMENT_MULTIPLE:が:家族', 'w3b2_trigger': 'U', 'w3b2': 'READ', 'frame': None}


@pytest.mark.parametrize('top', [['ABSTRACT', 'PERSON'], ['PERSON', 'PLACE'], ['PERSON', 'TIME'], ['GROUP_ORG', 'QUANTITY']])
def test_u_does_not_read_a_split_agent_with_one_candidate_outside(top):
    new, base = pair('家族が庭へ走った。', u_map(**{'家族': P(top, by=GA)}))
    assert new == base and reasons(new)[1] == 'PLACEMENT_MULTIPLE:が:家族'


def test_u_does_not_read_a_split_goal_even_when_the_agent_fits():
    new, base = pair('兄が図書館へ走った。', u_map(**{'図書館': P(['GROUP_ORG', 'PLACE'], by=GA)}))
    assert new == base and reasons(new)[1] == 'PLACEMENT_MULTIPLE:へ:図書館'
    new, base = pair('家族が図書館へ走った。', u_map(**{'図書館': P(['GROUP_ORG', 'PLACE'], by=GA)}))
    assert new == base and not new['readable']


def test_u_does_not_read_an_estimated_or_a_generated_split_even_when_every_candidate_fits():
    for answer in (F.to_estimated(P(['GROUP_ORG', 'PERSON']), 'proximity'), F.to_estimated(P(['GROUP_ORG', 'PERSON']), 'generated'),
                   P(['GROUP_ORG', 'PERSON'], by=('gen_definition',))):
        new, base = pair('家族が庭へ走った。', u_map(**{'家族': answer}))
        assert new == base and not new['readable']


def test_u3_reads_a_split_patient_when_every_candidate_is_in_the_tables_patient_set_and_not_when_one_is_outside():
    m = u3_map(**{'断る': P('P_COMMUNICATE'), '注文': P(['EVENT_ACT', 'NATURAL_PHENOMENON'], by=GA)})
    out = SR.read('兄が校庭で注文を断った。', placement=Q(m))
    assert out['readable'] is True and out['clauses'][0]['role_basis']['patient'] == 'placement_all_candidates:EVENT_ACT+NATURAL_PHENOMENON'
    for top in (['EVENT_ACT', 'TIME'], ['EVENT_ACT', 'PLACE']):
        m = u3_map(**{'断る': P('P_COMMUNICATE'), '注文': P(top, by=GA)})
        new, base = pair('兄が校庭で注文を断った。', m)
        assert new == base and not new['readable']


def test_a_split_place_of_u3_is_never_read_because_a_split_cannot_be_inside_a_single_type():
    for top in (['PLACE', 'GROUP_ORG'], ['PLACE', 'ABSTRACT'], ['PLACE', 'TIME']):
        new, base = pair('兄が校庭で走った。', u3_map(**{'校庭': P(top, by=GA)}))
        assert new == base and not new['readable']


def s4_map(**over):
    m = {'夜': P('TIME', by=('definition',))}
    m.update(over)
    return m


def test_s4_part_with_a_split_answer_is_not_read_the_table_gives_one_role_to_one_type():
    for top in (['TIME', 'PLACE'], ['TIME', 'ABSTRACT']):
        new, base = pair('母が夜、手紙を書いた。', {'夜': P(top, by=GA)})
        assert new == base and not new['readable']


def test_d2_does_not_read_a_split_place_after_a_demonstrative():
    new, base = pair('母がこの部屋で休んだ。', {'部屋': P(['PLACE', 'ABSTRACT'], by=GA)})
    assert new == base and not new['readable']
    assert SR.typed_explain_ja('母がこの部屋で休んだ。', Q({'部屋': P(['PLACE', 'ABSTRACT'], by=GA)}))['w3b2'].startswith('PLACEMENT_MULTIPLE')


# ===================================================================================================================================
# K95: the frame of the predicate narrows (and only narrows)
# ===================================================================================================================================
def confirmed(top, frame):
    a = F.with_frame(P(top, by=('gen_frame', 'role_distribution@x')), 'CONFIRMED', frame)
    a['namespace'] = 'P'
    return a


def test_a_sentence_w3b1_reads_is_stopped_when_the_confirmed_frame_has_no_such_particle():
    m = u_map(**{'走る': confirmed('P_MOVE', {'へ': ['PLACE']}), '猫': P('ANIMAL')})
    text = '猫が庭へ走った。'
    assert BASE.read(text, placement=Q(m))['readable'] is True              # W3-b1 reads it
    out = SR.read(text, placement=Q(m))
    assert out['readable'] is False
    assert reasons(out) == [SR.read(text, placement=None)['abstain']['reasons'][0], 'PLACEMENT_FRAME_PARTICLE_NOT_CONFIRMED:P_MOVE:が']
    ex = SR.typed_explain_ja(text, Q(m))
    assert ex['w3b1'] == 'READ' and ex['w3b2'] is None and ex['frame'] == 'PLACEMENT_FRAME_PARTICLE_NOT_CONFIRMED:P_MOVE:が'


def test_a_sentence_w3b1_reads_is_stopped_when_the_type_is_not_in_the_frame_for_that_particle():
    m = u_map(**{'走る': confirmed('P_MOVE', {'が': ['ANIMAL', 'PERSON'], 'へ': ['PLACE']}), '会社': P('GROUP_ORG')})
    out = SR.read('会社が庭へ走った。', placement=Q(m))
    assert reasons(out)[1] == 'PLACEMENT_FRAME_TYPE_NOT_CONFIRMED:P_MOVE:が:GROUP_ORG'


def test_a_confirmed_frame_that_holds_every_particle_and_type_of_the_sentence_changes_nothing():
    m = u_map(**{'走る': confirmed('P_MOVE', {'が': ['ANIMAL', 'PERSON'], 'へ': ['PLACE']}), '猫': P('ANIMAL')})
    new, base = pair('猫が庭へ走った。', m)
    assert new == base and new['readable'] is True


def test_the_frame_is_not_a_reason_to_read_a_particle_or_a_type_the_table_does_not_hold():
    # the frame holds へ → PLACE and を → INFO_LANGUAGE for the predicate; the table (K62) of P_COMMUNICATE has no へ: still not read
    m = u_map(**{'叫ぶ': confirmed('P_COMMUNICATE', {'が': ['ANIMAL', 'PERSON'], 'へ': ['PLACE']})})
    new, base = pair('兄が庭へ叫んだ。', m)
    assert new == base and not new['readable']


def test_a_predicate_not_confirmed_or_with_no_frame_table_is_read_by_the_table_only():
    for status in ('NOT_CONFIRMED', 'NO_FRAME_TABLE'):
        m = u_map(**{'走る': F.with_frame(P('P_MOVE'), status), '猫': P('ANIMAL')})
        new, base = pair('猫が庭へ走った。', m)
        assert new == base and new['readable'] is True


def test_a_frame_that_breaks_the_invariants_stops_a_sentence_w3b1_reads_with_the_invalid_reason():
    bad = confirmed('P_MOVE', {'が': ['ANIMAL', 'PERSON'], 'へ': ['PLACE']}); bad['frame']['まで?'] = ['PLACE']
    m = u_map(**{'走る': bad, '猫': P('ANIMAL')})
    out = SR.read('猫が庭へ走った。', placement=Q(m))
    assert reasons(out)[1] == 'PLACEMENT_FRAME_INVALID:PARTICLE_NOT_CASE:まで?'


def test_u3_with_a_confirmed_frame_that_has_no_de_is_not_read_and_one_with_a_wrong_type_for_ga_neither():
    m = u3_map(**{'叫ぶ': confirmed('P_COMMUNICATE', {'が': ['ANIMAL', 'PERSON'], 'を': ['INFO_LANGUAGE']})})
    assert SR.typed_explain_ja('兄が校庭で叫んだ。', Q(m))['w3b2'] == 'PLACEMENT_FRAME_PARTICLE_NOT_CONFIRMED:P_COMMUNICATE:で'
    m = u3_map(**{'叫ぶ': confirmed('P_COMMUNICATE', {'が': ['ANIMAL', 'PERSON'], 'を': ['INFO_LANGUAGE']}), '会社': P('GROUP_ORG')})
    assert SR.typed_explain_ja('会社が校庭で叫んだ。', Q(m))['w3b2'] == 'PLACEMENT_FRAME_TYPE_NOT_CONFIRMED:P_COMMUNICATE:が:GROUP_ORG'
    new, base = pair('会社が校庭で叫んだ。', m)
    assert new == base and not new['readable']


def test_w3b2_does_not_run_on_a_sentence_w3b1_read_and_does_not_ask_the_placement_anything_new():
    m = u_map(**{'猫': P('ANIMAL')})
    q1, q2 = Q(m), Q(m)
    SR.read('猫が庭へ走った。', placement=q1); BASE.read('猫が庭へ走った。', placement=q2)
    assert q1.calls == q2.calls
    m = {'夜': P('TIME', by=('definition',))}
    q1, q2 = Q(m), Q(m)
    SR.read('母が夜、手紙を書いた。', placement=q1); BASE.read('母が夜、手紙を書いた。', placement=q2)
    assert q1.calls == q2.calls == ['夜']


def test_the_questions_for_a_sentence_are_asked_once_per_word_and_those_of_w3b1_come_first():
    q = Q(u_map())
    SR.read('家族が庭へ走った。', placement=q)
    assert len(q.calls) == len(set(q.calls))
    assert q.calls[:2] == ['走る', '家族']


# ===================================================================================================================================
# K96: X の Y
# ===================================================================================================================================
def head_of(text, whole=None):
    toks = tokens_of(text)
    whole = whole or text
    start = text.index(whole)
    return R.no_phrase_head(toks, start, start + len(whole))


def test_no_phrase_head_is_the_part_after_the_last_no_when_the_structure_is_a_noun_chain():
    assert head_of('友人の家') == ('家', None)
    assert head_of('祖父の兄の畑') == ('畑', None)
    assert head_of('学校の校庭') == ('校庭', None)


def test_no_phrase_head_does_not_apply_without_the_structure():
    assert head_of('家') == (None, None)
    assert head_of('の家') == (None, None)
    assert head_of('友人の') == (None, None)
    assert head_of('友人のの家') == (None, None)
    assert head_of('3人の友人') == (None, None)         # a numeral
    assert head_of('彼の家') == (None, None)            # a pronoun is no noun of the structure
    assert head_of('走る友人の家', '友人の家') == ('家', None)    # a span is taken as it is given


def test_no_phrase_head_names_the_relational_nouns_by_the_part_of_speech_not_by_a_word_list():
    assert head_of('駅の前') == (None, 'PLACEMENT_HEAD_RELATIONAL:副詞可能')
    assert head_of('庭の中') == (None, 'PLACEMENT_HEAD_RELATIONAL:副詞可能')
    assert head_of('友人の度') == (None, 'PLACEMENT_HEAD_RELATIONAL:助数詞可能')
    assert head_of('友人の隣') == ('隣', None) and head_of('友人の方') == ('方', None) and head_of('友人の横') == ('横', None)


def test_u_reads_x_no_y_by_the_type_of_the_head_and_writes_the_whole_phrase_as_the_value():
    m = u_map(**{'畑': P('PLACE', by=ROLE_ONLY)})                    # a goal is an argument: role distributions may decide it
    out = SR.read('兄が町の畑へ走った。', placement=Q(m))
    assert out['readable'] is True
    c = out['clauses'][0]
    assert c['roles'] == {'agent': '兄', 'goal': '町の畑'} and c['role_basis'] == {'agent': 'placement_direct:PERSON', 'goal': 'placement_direct_head:PLACE'}


def test_the_plan_of_w3b2_asks_the_head_of_x_no_y_and_never_the_whole_phrase():
    text = '兄が町の畑へ走った。'
    view = R.document_view({'d': text})
    toks = tokens_of(text)
    q = Q(u_map(**{'畑': P('PLACE', by=ROLE_ONLY)}))
    typed, why = R.typed_plan_u_w3b2_ja(view.clauses[0], toks, q, voice='active', written='走る', strip=lambda role: role.span.text, role_map=SR._ROLE_TABLE)
    assert why is None and typed is not None
    assert '畑' in q.calls and '町の畑' not in q.calls


@pytest.mark.parametrize('head, top, by, why', [
    ('前', ['PLACE', 'TIME'], GA, 'PLACEMENT_HEAD_RELATIONAL:副詞可能'),
    ('中', 'PLACE', GA, 'PLACEMENT_HEAD_RELATIONAL:副詞可能'),
])
def test_u_does_not_read_a_phrase_whose_head_is_a_relational_noun_even_when_the_placement_says_place(head, top, by, why):
    m = u_map(**{head: P(top, by=by)})
    text = '兄が庭の%sへ走った。' % head
    new, base = pair(text, m)
    assert new == base and not new['readable']
    assert SR.typed_explain_ja(text, Q(m))['w3b2'] == why


def test_a_head_that_the_placement_does_not_place_is_not_read_and_the_reason_is_the_gates():
    for answer, why in ((F.bare('UNPLACED'), 'PLACEMENT_UNPLACED:へ:町の窪地'), (P(['GROUP_ORG', 'PLACE'], by=GA), 'PLACEMENT_MULTIPLE:へ:町の窪地'),
                        (P('GROUP_ORG'), 'PLACEMENT_TYPE_MISMATCH:P_MOVE:へ:GROUP_ORG')):
        m = u_map(**{'窪地': answer})
        new, base = pair('兄が町の窪地へ走った。', m)
        assert new == base and not new['readable']
        assert SR.typed_explain_ja('兄が町の窪地へ走った。', Q(m))['w3b2'] == why


def test_u3_reads_a_place_x_no_y_by_the_head_which_the_reader_does_not_know():
    m = u3_map()
    out = SR.read('兄が学校の校庭で走った。', placement=Q(m))
    assert out['readable'] is True and out['clauses'][0]['roles'] == {'agent': '兄', 'place': '学校の校庭'}
    assert out['clauses'][0]['role_basis']['place'] == 'placement_direct_head:PLACE'


def s4_plan(text, mapping):
    """The plan of S4 alone, on the frame clause of the reader (the trigger of the entry is not asked: see the next test)."""
    view = R.document_view({'d': text})
    toks = tokens_of(text)
    frame = [c for c in view.clauses if c.rule == 'frame'][0]
    q = Q(mapping)
    return R.typed_plan_s4_w3b2_ja(text, toks, frame, q, role_map=SR._ROLE_TABLE), q


def test_s4_merges_two_runs_joined_by_one_no_into_one_part_and_types_it_by_its_head():
    (typed, why), q = s4_plan('兄が去年の大晦日、窓を拭いた。', {'大晦日': P('TIME', by=('definition',))})
    assert why is None and typed['mode'] == 'extra' and [(r.name, r.term) for r in typed['roles']] == [('time', '去年の大晦日')]
    assert typed['role_basis'] == {'time': 'placement_direct_head:TIME'} and 'role_flags' not in typed
    assert q.calls == ['大晦日']                          # the head only
    (typed, why), q = s4_plan('兄が夏の夕方、窓を拭いた。', {'夕方': P('TIME', by=('definition',))})
    assert typed is None and why == 'PLACEMENT_HEAD_RELATIONAL:副詞可能' and q.calls == []


def test_the_reader_reads_a_second_clause_beside_the_frame_for_x_no_y_before_a_comma_so_the_entry_does_not_reach_s4_there():
    # a fact about the reader of the base commit (not something this change decides): the clause count is 2, so no typed trigger fires and the output is the one without a placement
    for text in ('兄が去年の大晦日、窓を拭いた。', '母が冬の夜、窓を閉めた。'):
        view = R.document_view({'d': text})
        assert len(view.clauses) == 2 and [c.rule for c in view.clauses] == ['frame', 'np_internal']
        assert R.typed_trigger_ja(text, view) is None and R.typed_trigger_w3b2_ja(text, view) is None
        q = Q({'大晦日': P('TIME', by=('definition',)), '夜': P('TIME', by=('definition',))})
        assert SR.read(text, placement=q) == BASE.read(text, placement=None) and q.calls == []


# ===================================================================================================================================
# K97: demonstratives
# ===================================================================================================================================
def test_d1_a_demonstrative_before_a_time_part_is_dropped_from_the_value_and_written_as_a_mark():
    m = s4_map()
    out = SR.read('母がこの夜、手紙を書いた。', placement=Q(m))
    assert out['readable'] is True
    c = out['clauses'][0]
    assert c['roles'] == {'agent': '母', 'patient': '手紙', 'time': '夜'}
    assert c['role_basis'] == {'time': 'placement_direct:TIME'} and c['role_flags'] == {'time': {'determiner': 'この'}} and 'predicate_basis' not in c
    assert list(c)[-2:] == ['role_basis', 'role_flags']
    ex = SR.typed_explain_ja('母がこの夜、手紙を書いた。', Q(m))
    assert ex == {'w3b1_trigger': 'S4', 'w3b1': 'PLACEMENT_PART_NOT_ISOLATED', 'w3b2_trigger': 'S4', 'w3b2': 'READ', 'frame': None}
    assert SR.read('母がその夜、手紙を書いた。', placement=Q(m))['clauses'][0]['role_flags'] == {'time': {'determiner': 'その'}}


def test_d2_a_demonstrative_outside_the_span_of_a_role_the_reader_typed_is_a_mark_of_that_role_only_when_the_type_is_in_the_table():
    m = {'部屋': P('PLACE', by=GA)}
    out = SR.read('母がこの部屋で休んだ。', placement=Q(m))
    assert out['readable'] is True
    c = out['clauses'][0]
    assert c['roles'] == {'agent': '母', 'place': '部屋'} and c['role_basis'] == {'place': 'placement_direct:PLACE'} and c['role_flags'] == {'place': {'determiner': 'この'}}
    ex = SR.typed_explain_ja('母がこの部屋で休んだ。', Q(m))
    assert ex == {'w3b1_trigger': 'S4', 'w3b1': 'PLACEMENT_PART_NONE', 'w3b2_trigger': 'S4', 'w3b2': 'READ', 'frame': None}
    out = SR.read('兄がその夜に手紙を書いた。', placement=Q(s4_map()))
    assert out['readable'] is True and out['clauses'][0]['role_flags'] == {'time': {'determiner': 'その'}}


def test_d2_does_not_read_a_role_that_has_no_place_in_the_type_table_whatever_the_placement_says():
    for text, why in (('兄がその車で走った。', 'PLACEMENT_DETERMINER_ROLE_UNTYPED:instrument'), ('兄がその駅から走った。', 'PLACEMENT_DETERMINER_ROLE_UNTYPED:source')):
        m = {'車': P('ARTIFACT'), '駅': P('PLACE'), '走る': P('P_MOVE')}
        new, base = pair(text, m)
        assert new == base and not new['readable']
        assert SR.typed_explain_ja(text, Q(m))['w3b2'] == why


def test_a_demonstrative_that_is_not_one_of_the_three_is_not_read():
    # どの: a question; あの: the tagger cuts it as an interjection (感動詞), not a 連体詞
    for text in ('兄がどの夜、手紙を書いた。', '兄があの夜、手紙を書いた。', '母がどの部屋で休んだ。', '母があの部屋で休んだ。'):
        m = {'夜': P('TIME', by=('definition',)), '部屋': P('PLACE', by=GA)}
        new, base = pair(text, m)
        assert new == base and not new['readable'], text


def test_the_mark_does_not_change_what_b1_judges():
    expect = {'readable': True, 'clauses': [{'predicate': '書く', 'roles': {'agent': '母', 'patient': '手紙', 'time': '夜'}, 'polarity': '+', 'tense': 'past', 'modality': None,
                                              'voice': 'active'}], 'relations': [], 'must_not': []}
    out = SR.read('母がこの夜、手紙を書いた。', placement=Q(s4_map()))
    assert b1.judge(expect, 'ja', out)['verdict'] == 'correct'
    stripped = json.loads(json.dumps(out)); del stripped['clauses'][0]['role_flags']
    assert b1.judge(expect, 'ja', stripped)['verdict'] == 'correct'


# ===================================================================================================================================
# K98: what is not read
# ===================================================================================================================================
def test_a_quantity_adverb_is_not_read_the_output_is_w3b1s():
    for text in ('兄が三回、窓を拭いた。', '兄が三度、窓を拭いた。', '兄が3回、窓を拭いた。', '兄が窓を3回拭いた。'):
        m = {'三回': P('QUANTITY'), '3回': P('QUANTITY', by=('notation',)), '3': P('QUANTITY', by=('notation',))}
        new, base = pair(text, m)
        assert new == base and not new['readable'], text


def test_english_is_not_read_with_a_placement_and_its_output_is_w3b1s():
    for text in ('The boy read this book.', 'A dog ran to the park.'):
        assert SR.read(text, placement=Q({})) == BASE.read(text, placement=Q({}))
        assert SR.read(text, placement=None) == BASE.read(text, placement=None)


def test_the_means_instrument_and_recipient_goal_of_the_chapters_example_sentences_are_not_read_the_table_is_not_widened():
    m = {'窓口': P(['ABSTRACT', 'PLACE'], by=GA), '胡麻油': F.bare('UNPLACED'), '参加者': P('PERSON', by=('role@a',)), '倉庫': P('PLACE'), '日程': P(['PLACE', 'TIME'], by=ROLE_ONLY),
         '運ぶ': P('P_MOVE'), '知らせる': F.bare('UNKNOWN'), '係': P('PERSON'), '荷物': P('ARTIFACT')}
    for text in ('係員が窓口で書類を確認した。', '料理人が魚を胡麻油で揚げた。', '事務局が参加者に日程を知らせた。'):
        new, base = pair(text, m)
        assert new == base and not new['readable'], text


# ===================================================================================================================================
# no placement: the output is the base commit's, with none of the new keys
# ===================================================================================================================================
def rows_of(*names):
    out = []
    for name in names:
        for line in (RS / name).read_text(encoding='utf-8').splitlines():
            if line.strip(): out.append(json.loads(line))
    return out


NEW_DATA = [r for name in COMMON.DATA for r in COMMON.load_data(name)]
OLD_DATA = rows_of('ja_r8.jsonl', 'ja_r9.jsonl', 'ja_r10.jsonl')
B1_SAMPLES = [r for fx in ('B1_v2', 'B1_v2_r2', 'B1_v2_r3')
              for r in (json.loads(l) for l in (TREE / 'tests' / 'bank_score' / 'fixtures' / fx / 'items.jsonl').read_text(encoding='utf-8').splitlines() if l.strip())]
JA = re.compile('[぀-ヿ㐀-䶿一-鿿]')
ALL_JA = list(dict.fromkeys(t for t in [r['input'] for r in NEW_DATA + OLD_DATA + B1_SAMPLES] if JA.search(t)))


def test_without_a_placement_the_output_is_the_base_commits_byte_for_byte_and_has_no_new_key():
    for text in ALL_JA:
        new, base = SR.read(text, placement=None), BASE.read(text, placement=None)
        assert json.dumps(new, ensure_ascii=False) == json.dumps(base, ensure_ascii=False), text
        for c in new['clauses']:
            assert not ({'role_flags', 'predicate_basis', 'role_basis'} & set(c)), text


# ===================================================================================================================================
# the control flow: what changes against W3-b1 is a sentence read now or a sentence stopped by a frame, nothing else
# ===================================================================================================================================
def fx_pair(text, mapper=None):
    return SR.read(text, placement=F.FixtureQuery(mapper=mapper)), BASE.read(text, placement=F.FixtureQuery(mapper=mapper))


def classify(text):
    new, base = fx_pair(text)
    if base['readable']:
        if new == base: return 'same_read'
        if (not new['readable']) and len(reasons(new)) == 2 and reasons(new)[1].startswith('PLACEMENT_FRAME_'): return 'frame_stopped'
        return 'READ_CHANGED'
    if not new['readable']:
        return 'same_refusal' if new == base else 'REFUSAL_CHANGED'
    return 'newly_read'


def test_every_difference_from_w3b1_is_a_sentence_read_now_or_a_sentence_stopped_by_a_frame_on_all_the_data():
    kinds = {}
    for text in ALL_JA:
        k = classify(text)
        kinds.setdefault(k, []).append(text)
    bad = {k: v[:5] for k, v in kinds.items() if k in ('READ_CHANGED', 'REFUSAL_CHANGED')}
    assert bad == {}, bad
    assert kinds.get('newly_read'), kinds.keys()
    for text in kinds['newly_read']:
        assert SR.typed_explain_ja(text, F.FixtureQuery())['w3b2'] == 'READ', text


def test_the_diagnosis_says_read_exactly_when_the_entry_reads_with_the_new_path_on_all_the_data():
    for text in ALL_JA:
        ex = SR.typed_explain_ja(text, F.FixtureQuery())
        new, base = fx_pair(text)
        assert set(ex) == {'w3b1_trigger', 'w3b1', 'w3b2_trigger', 'w3b2', 'frame'}
        new_path_read = bool(new['readable']) and not base['readable']
        assert (ex['w3b2'] == 'READ') == new_path_read, (text, ex)


def test_the_fixture_has_every_word_the_data_asks():
    q = F.FixtureQuery()
    for text in ALL_JA: SR.read(text, placement=q)
    assert sorted(set(q.misses)) == []


EXCEPTIONS = {x['id']: x for x in json.loads((RS / 'w3b2_expect_exceptions.json').read_text(encoding='utf-8'))['exceptions']}


def test_the_new_data_rows_are_read_and_refused_as_registered_and_judged_correct_when_read():
    """Every row meets `entry_expect` and `w3b2_expect`, except the rows declared in w3b2_expect_exceptions.json (see the next tests): for those the observed result is pinned."""
    problems, misses = [], []
    for r in NEW_DATA:
        q = F.FixtureQuery()
        out = SR.read(r['input'], placement=q)
        misses += q.misses
        verdict = b1.judge(r['expect'], 'ja', out)['verdict']
        if verdict in ('misread', 'incomplete', 'UNJUDGED'): problems.append((r['id'], 'verdict', verdict))
        ex = SR.typed_explain_ja(r['input'], F.FixtureQuery())
        if r['id'] in EXCEPTIONS:
            x = EXCEPTIONS[r['id']]
            if ('read' if out['readable'] else 'abstain') != x['observed_entry'] or ex != x['observed_explain'] or verdict != x['observed_verdict']:
                problems.append((r['id'], 'declared exception no longer what was observed', x['observed_entry'], x['observed_explain']))
            continue
        if (r['entry_expect'] == 'read') != bool(out['readable']): problems.append((r['id'], 'entry_expect', r['entry_expect'], out['readable']))
        if r['entry_expect'] == 'read' and verdict != 'correct': problems.append((r['id'], 'read but not correct', verdict))
        if not out['readable']:
            base = SR.read(r['input'], placement=None)
            if not out['abstain']['reasons'][0] == base['abstain']['reasons'][0]: problems.append((r['id'], 'first reason differs from the one without a placement'))
        e = r['w3b2_expect']
        if e == 'READ': ok = ex['w3b2'] == 'READ'
        elif e.startswith('FRAME:'): ok = (ex['frame'] or '').startswith(e[6:])
        else: ok = (ex['w3b2'] or '').startswith(e)
        if not ok: problems.append((r['id'], 'w3b2_expect', e, ex))
    assert problems == []
    assert misses == []


def test_the_declared_exceptions_are_rows_of_the_frozen_data_each_explained_by_a_fact_of_the_reader_and_none_is_a_wrong_reading():
    ids = {r['id']: r for r in NEW_DATA}
    assert set(EXCEPTIONS) <= set(ids)
    for i, x in EXCEPTIONS.items():
        assert x['kind'] in COMMON.EXCEPTION_KINDS and x['kind'] == COMMON.exception_kind(ids[i]['input']), (i, x['kind'])     # the fact is a fact of the reader alone
        assert x['entry_expect'] == ids[i]['entry_expect'] and x['w3b2_expect'] == ids[i]['w3b2_expect'] and x['input'] == ids[i]['input']    # the frozen expectation is quoted as it is
        assert x['observed_verdict'] not in ('misread', 'incomplete', 'UNJUDGED')
        if x['kind'] != 'reader_reads_it_alone': assert x['observed_entry'] == 'abstain'
    # a declared row is a prediction that was wrong about the reader, never a row the new paths read: nothing the new paths read is declared
    for i, x in EXCEPTIONS.items():
        assert x['observed_explain']['w3b2'] != 'READ', i


def test_every_row_of_the_data_has_the_two_expectations_and_the_balance_the_ticket_asks():
    for name in COMMON.DATA:
        rows = COMMON.load_data(name)
        assert len(rows) >= 60, name
        read = sum(1 for r in rows if r['entry_expect'] == 'read')
        assert 0.4 <= read / len(rows) <= 0.6, (name, read, len(rows))


def check_shape(out):
    """The shape of an output of the new paths (the validate() of tests/test_semantic_read.py is not changed and does not know the new values)."""
    rx = re.compile(R.W3B2_ROLE_BASIS_RE)
    if not out['readable']: return
    for c in out['clauses']:
        keys = list(c)
        if 'role_flags' in c: assert keys[-1] == 'role_flags' and keys[-2] == 'role_basis', keys
        if 'role_basis' in c:
            assert isinstance(c['role_basis'], dict) and c['role_basis']
            for role, v in c['role_basis'].items():
                assert role in c['roles'] and (rx.fullmatch(v) or re.fullmatch('placement_direct:[A-Z_]+', v)), (role, v)
        if 'role_flags' in c:
            assert c['role_flags'] and set(c['role_flags']) <= set(c['roles'])
            for role, flags in c['role_flags'].items():
                assert set(flags) == {'determiner'} and flags['determiner'] in R.W3B2_DEMONSTRATIVES, flags
                assert flags['determiner'] not in c['roles'][role]


def test_every_output_of_the_new_data_has_the_registered_shape():
    for r in NEW_DATA:
        check_shape(SR.read(r['input'], placement=F.FixtureQuery()))


def test_no_value_of_a_role_holds_a_demonstrative_the_mark_was_taken_from():
    for r in NEW_DATA:
        out = SR.read(r['input'], placement=F.FixtureQuery())
        if not out['readable']: continue
        for c in out['clauses']:
            for role, flags in (c.get('role_flags') or {}).items():
                assert not c['roles'][role].startswith(flags['determiner'])


# ===================================================================================================================================
# A3 / R3: with the estimated and the split fakes nothing is newly read (a placement that only guesses gives no reading)
# ===================================================================================================================================
@pytest.mark.parametrize('mapper', [lambda a: F.to_estimated(a, 'proximity'), lambda a: F.to_estimated(a, 'generated'), F.to_multiple])
def test_with_a_placement_that_only_estimates_or_splits_nothing_is_newly_read(mapper):
    newly = []
    for text in ALL_JA:
        out = SR.read(text, placement=F.FixtureQuery(mapper=mapper))
        if out['readable'] and not SR.read(text, placement=None)['readable']: newly.append(text)
    assert newly == []


def test_the_new_data_with_the_estimated_fake_reads_nothing_the_reader_did_not_read_alone():
    for r in NEW_DATA:
        out = SR.read(r['input'], placement=F.FixtureQuery(mapper=lambda a: F.to_estimated(a, 'proximity')))
        alone = SR.read(r['input'], placement=None)
        assert out['readable'] == alone['readable'], r['id']
        if not out['readable']: assert out['abstain']['reasons'][0] == alone['abstain']['reasons'][0], r['id']          # a placement adds its own second reason


# ===================================================================================================================================
# the entry on the command line and in the default path (`--placement`, VERA_PLACEMENT) still work and write the new keys
# ===================================================================================================================================
def test_the_new_path_is_reachable_from_the_default_entry_with_a_placement_object_and_the_diagnosis_has_no_effect_on_read():
    q = Q(u3_map())
    before = SR.read('兄が校庭で走った。', placement=q)
    SR.typed_explain_ja('兄が校庭で走った。', Q(u3_map()))
    assert SR.read('兄が校庭で走った。', placement=Q(u3_map())) == before
