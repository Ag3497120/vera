"""W3-c4 (docs/OBSERVATION.md, 文書 QA の後段): `vera ask --mode round5 --document ...` tries the question cross as a later stage ONLY when the round5 reading stopped with
UNKNOWN_UNREAD or UNKNOWN_NO_EVIDENCE. These tests drive `cli.main` (the entry of `vera ask`) in this process; the placement is handed over by replacing
`event_cross.default_lookup` (the path VERA_PLACEMENT takes), never by a file outside the tree. No test is skipped.
"""
import contextlib
import io
import json
from pathlib import Path

import pytest

from verantyx import cli
from verantyx import event_cross as EC
from verantyx import observe as O

HERE = Path(__file__).resolve().parent
Q_DIR = HERE / 'observe' / 'question'
MASK = ('ingest_ms', 'elapsed_ms')                 # the two keys whose values differ between two runs of the same input (artifacts/w3-c4/nondeterministic_keys.txt)

DOC_JA = '先生が生徒に地図を渡した。\n校長は本を読んだ。駅員が客に切符を渡した。\n'
PLACE_JA = {'先生': 'PERSON', '生徒': 'PERSON', '校長': 'PERSON', '駅員': 'PERSON', '客': 'PERSON', '地図': 'ARTIFACT', '本': 'ARTIFACT', '切符': 'ARTIFACT',
            'ＰＣ': 'ARTIFACT', 'PC': 'ARTIFACT', 'Smith': 'PERSON', 'student': 'PERSON', 'map': 'ARTIFACT', 'baker': 'PERSON', 'cook': 'PERSON', 'flour': 'ARTIFACT'}


def write_pl(tmp, lemmas):
    path = Path(tmp) / 'pl.json'
    path.write_text(json.dumps({'lemmas': {w: {'state': 'DECIDED', 'origin': 'direct', 'types': [t]} for w, t in lemmas.items()}, 'neighbors': {}}, ensure_ascii=False),
                    encoding='utf-8')
    return O.FilePlacement.from_path(str(path))


@pytest.fixture
def place(tmp_path, monkeypatch):
    monkeypatch.delenv('VERA_PLACEMENT', raising=False)
    fp = write_pl(tmp_path, PLACE_JA)
    monkeypatch.setattr(EC, 'default_lookup', lambda *a, **k: fp)
    return fp


@pytest.fixture
def noplace(monkeypatch):
    monkeypatch.delenv('VERA_PLACEMENT', raising=False)


def doc_file(tmp_path, name, text):
    p = Path(tmp_path) / name
    p.write_text(text, encoding='utf-8')
    return str(p)


def ask(tmp_path, capsys, docs, question, *extra, mode='round5'):
    argv = ['--store', str(Path(tmp_path) / 'st.json'), 'ask', '--mode', mode]
    for d in docs: argv += ['--document', d]
    argv += list(extra) + ['--', question]
    capsys.readouterr()
    rc = cli.main(argv)
    out = capsys.readouterr().out
    return rc, json.loads(out)


def mask(obj):
    if isinstance(obj, dict): return {k: (0 if k in MASK else mask(v)) for k, v in obj.items()}
    if isinstance(obj, list): return [mask(v) for v in obj]
    return obj


def strip_stage(out):
    out = dict(out)
    out.pop('question_cross', None)
    out['trace'] = [t for t in out.get('trace', []) if not (isinstance(t, dict) and t.get('part') == 'question_cross')]
    return out


def qc_steps(out): return [t for t in out.get('trace', []) if isinstance(t, dict) and t.get('part') == 'question_cross']


# ---------------------------------------------------------------------------------------------------------------------------------
# 1. the closed set
# ---------------------------------------------------------------------------------------------------------------------------------
def test_trigger_is_the_closed_set_of_two_values():
    assert cli._QC_TRIGGER == ('UNKNOWN_UNREAD', 'UNKNOWN_NO_EVIDENCE')


@pytest.mark.parametrize('result', [
    {'verdict': 'ANSWER', 'text': 'x', 'trace': []},
    {'verdict': 'UNKNOWN_UNSUPPORTED_EVIDENCE', 'trace': []},
    {'verdict': 'UNKNOWN_CONTENT_PERMISSION'},
    {'verdict': 'AMBIGUOUS'},
    {'verdict': 'UNKNOWN_SOURCE_ASSET'},
    {'no_verdict': True},
    'a string', None, ['UNKNOWN_UNREAD'],
])
def test_outside_the_closed_set_the_same_object_comes_back(result, monkeypatch):
    def boom(*a, **k): raise AssertionError('a document was read although the stage cannot run')
    from verantyx import document_loaders as DL
    monkeypatch.setattr(DL, 'load_paths', boom)
    monkeypatch.setattr(DL, 'load_directory', boom)
    assert cli._round5_question_cross(result, ['/nonexistent/doc.txt'], '誰が来た？') is result


def test_without_a_document_the_same_object_comes_back():
    r = {'verdict': 'UNKNOWN_UNREAD', 'trace': [{'part': 'x'}]}
    assert cli._round5_question_cross(r, [], '誰が来た？') is r
    assert cli._round5_question_cross(r, None, '誰が来た？') is r


def test_inside_the_closed_set_the_original_is_not_modified(tmp_path, place):
    trace = [{'part': 'one'}]
    r = {'kind': 'unknown', 'verdict': 'UNKNOWN_UNREAD', 'trace': trace, 'remedy': {'a': 1}}
    before = json.dumps(r, sort_keys=True)
    out = cli._round5_question_cross(r, [doc_file(tmp_path, 'ja.txt', DOC_JA)], '校長は何を読んだ？')
    assert out is not r and json.dumps(r, sort_keys=True) == before and trace == [{'part': 'one'}]


# ---------------------------------------------------------------------------------------------------------------------------------
# 2. the structure: cut, ids
# ---------------------------------------------------------------------------------------------------------------------------------
def test_records_cut_after_the_japanese_stop_and_after_dot_space_with_the_ids_by_hand(tmp_path):
    text = ('先生が本を読んだ。駅員が切符を渡した。\n'
            'The teacher read it. The doctor left.\n'
            'Version 3.5 was sold.\n'
            '# 見出し\n'
            '\n'
            '誰が来たか？本当に！\n')
    path = doc_file(tmp_path, 'f.txt', text)
    records, where, loaded, skipped = cli._qc_records([path])
    assert loaded == 1 and skipped == []
    assert records == [
        {'id': 'f.txt#1:1', 'text': '先生が本を読んだ。'}, {'id': 'f.txt#1:2', 'text': '駅員が切符を渡した。'},
        {'id': 'f.txt#2:1', 'text': 'The teacher read it.'}, {'id': 'f.txt#2:2', 'text': 'The doctor left.'},
        {'id': 'f.txt#3:1', 'text': 'Version 3.5 was sold.'},          # '3.5' is not cut: the dot is not followed by a space
        {'id': 'f.txt#4:1', 'text': '見出し'},                        # the heading mark is removed by the loader, the line stays line 4
        {'id': 'f.txt#6:1', 'text': '誰が来たか？本当に！'},           # an empty line 5 keeps its number; ？ and ！ cut nothing
    ]
    assert where['f.txt#2:2'] == {'source': 'f.txt', 'line': 2, 'text': 'The doctor left.', 'cut_uncertain': False}


def test_cut_uncertain_marks_a_piece_next_to_a_dot_that_may_not_end_a_sentence(tmp_path):
    path = doc_file(tmp_path, 'm.txt', 'Mr. Smith gave the map to the student.\nSmith Jr. sold the horse.\nShe left. He came.\n')
    records, where, _, _ = cli._qc_records([path])
    flags = {r['id']: where[r['id']]['cut_uncertain'] for r in records}
    assert flags == {'m.txt#1:1': False, 'm.txt#1:2': True,            # 'Mr.' is one token ending in '.': the piece after it is the middle of a sentence
                     'm.txt#2:1': True, 'm.txt#2:2': True,              # 'Smith Jr.' is followed by a lower-case piece
                     'm.txt#3:1': False, 'm.txt#3:2': False}


def test_a_directory_and_a_file_are_read_like_load_documents(tmp_path):
    (tmp_path / 'd').mkdir()
    (tmp_path / 'd' / 'a.txt').write_text('先生が本を読んだ。\n', encoding='utf-8')
    (tmp_path / 'd' / 'b.txt').write_text('校長が本を読んだ。\n', encoding='utf-8')
    records, where, loaded, skipped = cli._qc_records([str(tmp_path / 'd')])
    assert loaded == 2 and [r['id'] for r in records] == ['a.txt#1:1', 'b.txt#1:1']


# ---------------------------------------------------------------------------------------------------------------------------------
# 3. FILLED -> ANSWER
# ---------------------------------------------------------------------------------------------------------------------------------
def test_the_premise_the_round5_reading_alone_stops_unread(tmp_path, capsys, place, monkeypatch):
    monkeypatch.setattr(cli, '_round5_question_cross', lambda r, d, q: r)
    rc, out = ask(tmp_path, capsys, [doc_file(tmp_path, 'ja.txt', DOC_JA)], '校長は何を読んだ？')
    assert out['verdict'] == 'UNKNOWN_UNREAD' and 'question_cross' not in out and qc_steps(out) == []


def test_filled_is_an_answer_with_the_sentence_as_evidence(tmp_path, capsys, place):
    rc, out = ask(tmp_path, capsys, [doc_file(tmp_path, 'ja.txt', DOC_JA)], '校長は何を読んだ？')
    assert rc == 0
    assert (out['kind'], out['verdict'], out['door']) == ('answer', 'ANSWER', 'question_cross')
    assert out['text'] == '本' and out['values'] == ['本'] and out['evidence'] == ['校長は本を読んだ。']
    assert out['sources'] == [{'family': 'document', 'source': 'ja.txt', 'line': 2, 'text': '校長は本を読んだ。', 'sentence_id': 'ja.txt#2:1'}]
    assert list(out['sources'][0]) == ['family', 'source', 'line', 'text', 'sentence_id'] and 'origin' not in out['sources'][0]
    assert all(out['text'] in s['text'] for s in out['sources'])
    qc = out['question_cross']
    assert (qc['state'], qc['mapped_to'], qc['hole_role']) == ('FILLED', 'ANSWER', 'patient') and qc['hole_type'] and qc['coord']
    assert list(qc) == ['state', 'reason', 'mapped_to', 'hole_role', 'hole_type', 'coord', 'structure', 'documents']
    assert qc['documents'] == {'loaded': 1, 'skipped': []} and qc['structure']['sentences'] == 3
    assert qc_steps(out) == [{'part': 'question_cross', 'status': 'ran', 'state': 'FILLED', 'mapped_to': 'ANSWER'}] and out['trace'][-1] == qc_steps(out)[0]
    assert 'basis_policy' in out                                   # the policy is applied after the later stage


def test_the_surface_is_written_as_the_evidence_writes_it_without_normalising(tmp_path, capsys, place):
    doc = doc_file(tmp_path, 'pc.txt', '先生は生徒にＰＣを貸した。\n校長は本を読んだ。駅員が客に切符を渡した。\n')
    rc, out = ask(tmp_path, capsys, [doc], '先生は生徒に何を貸した？')
    assert out['door'] == 'question_cross' and out['verdict'] == 'ANSWER'
    assert out['text'] == 'ＰＣ' and out['sources'][0]['text'] == '先生は生徒にＰＣを貸した。'      # full-width, as the sentence writes it (not 'PC')


# ---------------------------------------------------------------------------------------------------------------------------------
# 4. TIE
# ---------------------------------------------------------------------------------------------------------------------------------
def split_docs(tmp_path, first='baker', second='cook'):
    """Two documents that each name one buyer of the flour: the round5 reading alone stops UNREAD, the cross lays the two over each other."""
    return [doc_file(tmp_path, 'e1.txt', 'The %s bought the flour.\n' % first), doc_file(tmp_path, 'e2.txt', 'The %s bought the flour.\n' % second)]


def candidates(out): return {c['text']: [s['text'] for s in c['sources']] for c in out['candidates']}


def test_a_split_is_a_typed_abstention_with_the_candidates_laid_over_each_other(tmp_path, capsys, place):
    rc, out = ask(tmp_path, capsys, split_docs(tmp_path), 'Who bought the flour?')
    assert out['verdict'] == 'AMBIGUOUS_QUESTION_CROSS_TIE' and out['kind'] == 'unknown' and out['text'] == '' and out['door'] == 'question_cross'
    assert candidates(out) == {'baker': ['The baker bought the flour.'], 'cook': ['The cook bought the flour.']}
    assert [s['sentence_id'] for c in out['candidates'] for s in c['sources']] == ['e1.txt#1:1', 'e2.txt#1:1']
    assert out['sources'] == [] and out['evidence'] == [] and out['question_cross']['mapped_to'] == 'AMBIGUOUS_QUESTION_CROSS_TIE' and out['question_cross']['state'] == 'TIE'
    assert qc_steps(out)[0]['state'] == 'TIE' and qc_steps(out)[0]['mapped_to'] == 'AMBIGUOUS_QUESTION_CROSS_TIE'


def test_the_order_of_the_documents_does_not_change_the_candidates(tmp_path, capsys, place):
    docs = split_docs(tmp_path)
    a = ask(tmp_path, capsys, docs, 'Who bought the flour?')[1]
    b = ask(tmp_path, capsys, list(reversed(docs)), 'Who bought the flour?')[1]
    assert a['verdict'] == b['verdict'] == 'AMBIGUOUS_QUESTION_CROSS_TIE'
    assert candidates(a) == candidates(b) == {'baker': ['The baker bought the flour.'], 'cook': ['The cook bought the flour.']}
    ids = lambda o: {c['text']: [s['sentence_id'] for s in c['sources']] for c in o['candidates']}
    assert ids(a) == {'baker': ['e1.txt#1:1'], 'cook': ['e2.txt#1:1']} == ids(b)       # the id names the file, not the position of the file in the command


def test_surfaces_that_differ_only_in_width_are_a_tie_not_a_choice(tmp_path, capsys, place):
    doc = doc_file(tmp_path, 'w.txt', '先生は生徒にＰＣを貸した。\n先生は生徒にPCを貸した。\n駅員は本を読んだ。\n')
    rc, out = ask(tmp_path, capsys, [doc], '先生は生徒に何を貸した？')
    assert out['verdict'] == 'AMBIGUOUS_QUESTION_CROSS_TIE' and out['question_cross']['reason'] == 'SURFACES_DIFFER:2'
    assert sorted(candidates(out)) == ['PC', 'ＰＣ'] and out['question_cross']['state'] == 'FILLED' and out['sources'] == []


# ---------------------------------------------------------------------------------------------------------------------------------
# 5. the original abstention stays (question_cross and one step added, nothing else changes)
# ---------------------------------------------------------------------------------------------------------------------------------
@pytest.mark.parametrize('question,state', [
    ('校長は何を渡した？', 'NO_ATTESTED_CELL'),
    ('今日の天気はどうですか？', 'QUESTION_NOT_READ'),
])
def test_original_abstention_is_kept_with_question_cross_added(tmp_path, capsys, place, monkeypatch, question, state):
    docs = [doc_file(tmp_path, 'ja.txt', DOC_JA)]
    new = ask(tmp_path, capsys, docs, question)[1]
    monkeypatch.setattr(cli, '_round5_question_cross', lambda r, d, q: r)
    base = ask(tmp_path, capsys, docs, question)[1]
    assert base['verdict'] in cli._QC_TRIGGER
    assert new['question_cross']['state'] == state and new['question_cross']['mapped_to'] == 'ORIGINAL' and new['question_cross']['coord'] is None
    assert len(qc_steps(new)) == 1 and qc_steps(new)[0]['mapped_to'] == 'ORIGINAL'
    assert mask(strip_stage(new)) == mask(base)


def test_no_placement_no_typed_candidate_and_the_original_is_kept(tmp_path, capsys, noplace, monkeypatch):
    docs = [doc_file(tmp_path, 'ja.txt', DOC_JA)]
    new = ask(tmp_path, capsys, docs, '校長は何を読んだ？')[1]
    monkeypatch.setattr(cli, '_round5_question_cross', lambda r, d, q: r)
    base = ask(tmp_path, capsys, docs, '校長は何を読んだ？')[1]
    assert new['verdict'] == base['verdict'] == 'UNKNOWN_UNREAD' and new['question_cross']['state'] == 'NO_TYPED_CANDIDATE'
    assert mask(strip_stage(new)) == mask(base)


def test_a_question_the_existing_path_answers_does_not_run_the_stage(tmp_path, capsys, place):
    rc, out = ask(tmp_path, capsys, [doc_file(tmp_path, 'ja.txt', DOC_JA)], '誰が切符を渡した？')
    assert out['verdict'] == 'ANSWER' and out['door'] != 'question_cross' and 'question_cross' not in out and qc_steps(out) == []


# ---------------------------------------------------------------------------------------------------------------------------------
# 6. a negated sentence does not answer an affirmative question
# ---------------------------------------------------------------------------------------------------------------------------------
def test_a_negated_sentence_is_not_an_answer_to_the_affirmative_question(tmp_path, capsys, place):
    doc = doc_file(tmp_path, 'neg.txt', '校長は本を読まなかった。\n先生が生徒に地図を渡した。\n')
    rc, out = ask(tmp_path, capsys, [doc], '校長は何を読んだ？')
    assert not (out.get('door') == 'question_cross' and out.get('verdict') == 'ANSWER')
    assert out['question_cross']['state'] == 'NO_ATTESTED_CELL'
    # the question that matches the negation is answered, and the answer carries the negated sentence
    rc, out = ask(tmp_path, capsys, [doc], '校長は何を読まなかった？')
    assert out['verdict'] == 'ANSWER' and out['door'] == 'question_cross' and out['text'] == '本' and out['sources'][0]['text'] == '校長は本を読まなかった。'


# ---------------------------------------------------------------------------------------------------------------------------------
# 7. A4: the basis policy
# ---------------------------------------------------------------------------------------------------------------------------------
def test_policy_the_document_sentence_is_a_human_basis(tmp_path, capsys, place):
    rc, out = ask(tmp_path, capsys, [doc_file(tmp_path, 'ja.txt', DOC_JA)], '校長は何を読んだ？', '--request-kind', 'factual', '--human-present')
    bp = out['basis_policy']
    assert out['door'] == 'question_cross' and out['verdict'] == 'ANSWER' and bp['outcome'] == 'ANSWER_HUMAN_BASIS'
    assert bp['counts']['human'] == len(out['sources']) == 1 and bp['counts']['unknown_origin'] == 0
    assert out['question_cross']['state'] == 'FILLED'


def test_policy_human_basis_without_human_present_too(tmp_path, capsys, place):
    rc, out = ask(tmp_path, capsys, [doc_file(tmp_path, 'ja.txt', DOC_JA)], '校長は何を読んだ？', '--request-kind', 'factual')
    assert out['basis_policy']['outcome'] == 'ANSWER_HUMAN_BASIS' and out['basis_policy']['counts']['human'] == 1


def test_policy_a_tie_is_an_abstention_and_keeps_the_candidates(tmp_path, capsys, place):
    rc, out = ask(tmp_path, capsys, split_docs(tmp_path), 'Who bought the flour?', '--request-kind', 'factual', '--human-present')
    assert out['verdict'] == 'AMBIGUOUS_QUESTION_CROSS_TIE' and out['basis_policy']['outcome'] == 'ABSTAIN' and len(out['candidates']) == 2


# ---------------------------------------------------------------------------------------------------------------------------------
# 8. the other states (helper called directly: the trigger result is made by hand)
# ---------------------------------------------------------------------------------------------------------------------------------
def trigger(verdict='UNKNOWN_UNREAD'):
    return {'kind': 'unknown', 'verdict': verdict, 'door': 'semantic_document', 'trace': [{'part': 'one'}], 'remedy': {'k': 'v'}}


def check_original(out, orig, state, reason=None):
    qc = out['question_cross']
    assert qc['state'] == state and qc['mapped_to'] == 'ORIGINAL' and (reason is None or qc['reason'] == reason)
    assert list(qc) == ['state', 'reason', 'mapped_to', 'hole_role', 'hole_type', 'coord', 'structure', 'documents']
    assert {k: v for k, v in out.items() if k not in ('question_cross', 'trace')} == {k: v for k, v in orig.items() if k != 'trace'}
    assert out['trace'][:-1] == orig['trace'] and out['trace'][-1]['part'] == 'question_cross' and out['trace'][-1]['mapped_to'] == 'ORIGINAL'
    assert out is not orig and orig['trace'] == [{'part': 'one'}]


def test_the_same_file_twice_is_a_structure_invalid(tmp_path, place):
    path = doc_file(tmp_path, 'ja.txt', DOC_JA)
    orig = trigger()
    out = cli._round5_question_cross(orig, [path, path], '校長は何を読んだ？')
    check_original(out, orig, 'STRUCTURE_INVALID')
    assert out['question_cross']['reason'].startswith('DUPLICATE_ID:ja.txt#1:1') and out['trace'][-1]['status'] == 'abstained'
    assert out['question_cross']['structure'] is None and out['question_cross']['documents'] == {'loaded': 2, 'skipped': []}


def test_a_statement_is_not_a_question(tmp_path, place):
    orig = trigger()
    out = cli._round5_question_cross(orig, [doc_file(tmp_path, 'ja.txt', DOC_JA)], '校長は本を読んだ。')
    check_original(out, orig, 'NOT_A_QUESTION')
    assert out['question_cross']['structure'] is None and out['question_cross']['documents']['loaded'] == 1


def test_documents_that_cannot_be_read_are_documents_not_loaded(tmp_path, place):
    bad = doc_file(tmp_path, 'x.xyz', 'abc')
    orig = trigger('UNKNOWN_NO_EVIDENCE')
    out = cli._round5_question_cross(orig, [bad, str(tmp_path / 'missing.txt')], '校長は何を読んだ？')
    check_original(out, orig, 'DOCUMENTS_NOT_LOADED')
    docs = out['question_cross']['documents']
    assert docs['loaded'] == 0 and [d['verdict'] for d in docs['skipped']] == ['UNKNOWN_NO_PARSER', 'UNKNOWN_UNREADABLE'] and out['trace'][-1]['status'] == 'abstained'


def fake_obs(fillers, status='FILLED', excluded=None):
    return {'answer': {'status': status, 'question': {'hole_role': 'patient', 'hole_type': ['ARTIFACT']}, 'fillers': fillers, 'excluded': excluded or [],
                       'structure': {'sentences': 2, 'crossed': 2, 'unread': 0}, 'reasons': []}, 'ranks': []}


def test_a_surface_that_is_not_in_its_evidence_is_not_an_answer(tmp_path, monkeypatch):
    path = doc_file(tmp_path, 'ja.txt', DOC_JA)
    monkeypatch.setattr(O, 'observe_question_records', lambda q, r, **k: fake_obs([{'surface': '鉛筆', 'evidence': [{'reading': 'ja.txt#2:1'}]}]))
    orig = trigger()
    check_original(cli._round5_question_cross(orig, [path], '校長は何を読んだ？'), orig, 'FILLED', None)
    out = cli._round5_question_cross(orig, [path], '校長は何を読んだ？')
    assert out['question_cross']['reason'] == 'SURFACE_NOT_IN_EVIDENCE' and out['trace'][-1]['status'] == 'ran'


@pytest.mark.parametrize('text', ['先生は「本を読んだ。', '「先生は本を読んだ。', '先生は『本を読んだ。', 'The teacher read "the book.'])
def test_evidence_cut_in_the_middle_of_a_quotation_is_not_an_answer(tmp_path, monkeypatch, text):
    path = doc_file(tmp_path, 'q.txt', text + '\n')
    surface = '本' if '本' in text else 'book'
    monkeypatch.setattr(O, 'observe_question_records', lambda q, r, **k: fake_obs([{'surface': surface, 'evidence': [{'reading': 'q.txt#1:1'}]}]))
    out = cli._round5_question_cross(trigger(), [path], '先生は何を読んだ？')
    assert out['question_cross']['reason'] == 'QUOTE_UNBALANCED_EVIDENCE' and out['question_cross']['mapped_to'] == 'ORIGINAL' and out.get('door') == 'semantic_document'


def test_a_quotation_that_closes_inside_the_sentence_is_not_a_reason_to_abstain(tmp_path, monkeypatch):
    path = doc_file(tmp_path, 'q.txt', '先生は「本」を読んだ。\n')
    # round 2: the reader cannot read a sentence with brackets, so the predicate check (M1) would abstain on it by itself; it is switched off here to test the bracket check alone
    monkeypatch.setattr(cli, '_qc_predicate_form', lambda text, tail: None)
    monkeypatch.setattr(O, 'observe_question_records', lambda q, r, **k: fake_obs([{'surface': '本', 'evidence': [{'reading': 'q.txt#1:1'}]}]))
    out = cli._round5_question_cross(trigger(), [path], '先生は何を読んだ？')
    assert out['verdict'] == 'ANSWER' and out['text'] == '本'


def test_evidence_next_to_a_dot_that_may_be_an_abbreviation_is_not_an_answer(tmp_path, place):
    path = doc_file(tmp_path, 'mr.txt', 'Mr. Smith gave the map to the student.\n')
    orig = trigger()
    out = cli._round5_question_cross(orig, [path], 'Who gave the map to the student?')
    check_original(out, orig, 'FILLED', 'PERIOD_CUT_UNCERTAIN')


def test_an_exception_in_the_stage_is_an_error_state_and_the_original_stays(tmp_path, monkeypatch):
    path = doc_file(tmp_path, 'ja.txt', DOC_JA)
    def boom(q, r, **k): raise RuntimeError('boom')
    monkeypatch.setattr(O, 'observe_question_records', boom)
    orig = trigger()
    out = cli._round5_question_cross(orig, [path], '校長は何を読んだ？')
    check_original(out, orig, 'ERROR', 'RuntimeError: boom')
    assert out['question_cross']['documents'] is None and out['trace'][-1]['status'] == 'abstained'


def test_the_states_and_reasons_are_the_closed_lists():
    src = Path(cli.__file__).read_text(encoding='utf-8')
    states = set(O.ANSWER_STATUSES) | {'NOT_A_QUESTION', 'DOCUMENTS_NOT_LOADED', 'STRUCTURE_INVALID', 'ERROR'}
    assert len(O.ANSWER_STATUSES) == 11 and len(states) == 15
    for word in ('SURFACE_NOT_IN_EVIDENCE', 'QUOTE_UNBALANCED_EVIDENCE', 'PERIOD_CUT_UNCERTAIN', 'PREDICATE_FORM_DIFFERS', 'PREDICATE_POSITION_UNKNOWN', 'SURFACES_DIFFER',
                 'DOCUMENTS_NOT_LOADED', 'STRUCTURE_INVALID', 'NOT_A_QUESTION'):
        assert word in src
    assert 'tempfile' not in src.split('def _qc_records')[1].split('def cmd_ask')[0]               # no file is made by the stage


# ---------------------------------------------------------------------------------------------------------------------------------
# 8b. round 2 (M1): the WRITTEN predicate of the evidence must be the end of the question (the reader gives `読みたかった` the clause of `読んだ`)
# ---------------------------------------------------------------------------------------------------------------------------------
FORMS = [('先生は本を読みたかった。', '先生は何を読んだ？'), ('漁師は魚を運びたがった。', '漁師は何を運んだ？'), ('母は手紙を書きたかったです。', '母は何を書いた？'),
         ('校長は新聞を読んでみたかった。', '校長は何を読んだ？'), ('社長は資料を渡したらしかった。', '社長は何を渡した？'), ('課長は地図を見たがっていた。', '課長は何を見た？'),
         ('駅員は切符を渡したら。', '駅員は何を渡した？')]
PLACE_FORMS = dict(PLACE_JA, **{'漁師': 'PERSON', '母': 'PERSON', '社長': 'PERSON', '課長': 'PERSON', '魚': 'ANIMAL', '手紙': 'ARTIFACT', '新聞': 'ARTIFACT', '資料': 'ARTIFACT'})


@pytest.fixture
def place_forms(tmp_path, monkeypatch):
    monkeypatch.delenv('VERA_PLACEMENT', raising=False)
    fp = write_pl(tmp_path, PLACE_FORMS)
    monkeypatch.setattr(EC, 'default_lookup', lambda *a, **k: fp)


@pytest.mark.parametrize('sentence,tail,want', [
    ('先生は本を読んだ。', '先生は何を読んだ', None),                        # the same written predicate
    ('先生は本を読みたかった。', '先生は何を読みたかった', None),            # the question is written in the same form
    ('先生は本を読みたかった。', '先生は何を読んだ', 'PREDICATE_FORM_DIFFERS'),
    ('先生は本を読んだ。', '先生は何を読みたかった', 'PREDICATE_FORM_DIFFERS'),   # the reverse
    ('先生は本を読んだらしかった。', '先生は何を読んだ', 'PREDICATE_FORM_DIFFERS'),
    ('先生は本を読んだら。', '先生は何を読んだ', 'PREDICATE_FORM_DIFFERS'),
    ('先生は本を読みました。', '先生は何を読んだ', 'PREDICATE_FORM_DIFFERS'),        # polite vs plain: an over-abstention that is accepted
    ('先生は本を読みました。', '先生は何を読みました', None),
    ('先生は昨日本を読んだ。', '先生は何を読んだ', 'PREDICATE_POSITION_UNKNOWN'),    # the reader gives no clause
    ('先生は本を読み、校長は新聞を読んだ。', '校長は何を読んだ', 'PREDICATE_POSITION_UNKNOWN'),
    ('The teacher did read the book.', 'What did the teacher read', None),   # not applied to English
])
def test_predicate_form_check_directly(sentence, tail, want):
    assert cli._qc_predicate_form(sentence, tail) == want


@pytest.mark.parametrize('sentence,question', FORMS)
def test_a_desire_or_hearsay_sentence_is_not_the_answer_of_a_plain_past_question(tmp_path, capsys, place_forms, sentence, question):
    path = doc_file(tmp_path, 'f.txt', sentence + '\n')
    rc, out = ask(tmp_path, capsys, [path], question)
    assert out['verdict'] == 'UNKNOWN_UNREAD' and out.get('door') != 'question_cross'
    assert out['question_cross']['mapped_to'] == 'ORIGINAL' and out['question_cross']['reason'] == 'PREDICATE_FORM_DIFFERS' and out['question_cross']['state'] == 'FILLED'
    assert qc_steps(out)[0]['mapped_to'] == 'ORIGINAL'


def test_the_same_written_form_in_the_question_is_answered_verbatim(tmp_path, capsys, place_forms):
    path = doc_file(tmp_path, 'f.txt', '先生は本を読みたかった。\n')
    rc, out = ask(tmp_path, capsys, [path], '先生は何を読みたかった？')
    assert out['verdict'] == 'ANSWER' and out['door'] == 'question_cross' and out['text'] == '本' and out['sources'][0]['sentence_id'] == 'f.txt#1:1'
    assert out['text'] in out['sources'][0]['text']


def test_a_tie_whose_candidate_is_written_in_another_form_is_not_a_tie_of_answers(tmp_path, monkeypatch):
    path = doc_file(tmp_path, 't.txt', '先生は本を読んだ。\n校長は雑誌を読みたかった。\n')
    monkeypatch.setattr(O, 'observe_question_records', lambda q, r, **k: fake_obs(
        [{'surface': '本', 'evidence': [{'reading': 't.txt#1:1'}]}, {'surface': '雑誌', 'evidence': [{'reading': 't.txt#2:1'}]}], status='TIE'))
    orig = trigger()
    out = cli._round5_question_cross(orig, [path], '誰かは何を読んだ？')
    check_original(out, orig, 'TIE', 'PREDICATE_FORM_DIFFERS')


# ---------------------------------------------------------------------------------------------------------------------------------
# 9. parity: the in-memory entry equals the entry of `vera observe` on the same sentences
# ---------------------------------------------------------------------------------------------------------------------------------
def test_in_memory_entry_equals_the_jsonl_entry_for_20_questions(tmp_path, monkeypatch):
    monkeypatch.delenv('VERA_PLACEMENT', raising=False)
    fp = O.FilePlacement.from_path(str(Q_DIR / 'placement_q.json'))
    monkeypatch.setattr(EC, 'default_lookup', lambda *a, **k: fp)
    qs = [json.loads(l) for l in (Q_DIR / 'questions.jsonl').read_text(encoding='utf-8').splitlines() if l.strip()][:20]
    for q in qs:
        path = Q_DIR / 'docs' / (q['doc'] + '.jsonl')
        recs = [json.loads(l) for l in path.read_text(encoding='utf-8').splitlines() if l.strip()]
        a = O.observe_question_records(q['text'], recs, lang=q.get('lang'))
        res = O.run_entry(anchor_text=q['text'], anchor_kind='question', lang=q.get('lang'), structure_path=str(path), no_index=True)
        b = json.loads(res.stdout)
        assert a['answer'] == b['answer'], q['id']
        a['structure'].pop('file_sha256'); b['structure'].pop('file_sha256')
        assert a == b, q['id']


def test_observe_question_records_makes_no_file_and_checks_its_records(tmp_path):
    before = sorted(p.name for p in tmp_path.iterdir())
    O.observe_question_records('先生は何を読んだ？', [{'id': 'a#1:1', 'text': '先生は本を読んだ。'}])
    assert sorted(p.name for p in tmp_path.iterdir()) == before
    with pytest.raises(ValueError, match='STRUCTURE_INVALID:DUPLICATE_ID'):
        O.observe_question_records('先生は何を読んだ？', [{'id': 'a#1:1', 'text': 'x。'}, {'id': 'a#1:1', 'text': 'y。'}])
    with pytest.raises(ValueError, match='STRUCTURE_INVALID:item 1'):
        O.observe_question_records('先生は何を読んだ？', [{'id': '', 'text': 'x。'}])
    with pytest.raises(ValueError, match='STRUCTURE_INVALID:item 1 has a bad lang'):
        O.observe_question_records('先生は何を読んだ？', [{'id': 'a', 'text': 'x。', 'lang': 'fr'}])


# ---------------------------------------------------------------------------------------------------------------------------------
# 10. the stage is not run outside round5 with a document
# ---------------------------------------------------------------------------------------------------------------------------------
def test_not_round5_and_round5_without_a_document_have_no_stage(tmp_path, capsys, place):
    rc, out = ask(tmp_path, capsys, [], '校長は何を読んだ？')
    assert 'question_cross' not in out and qc_steps(out) == []
    rc, out = ask(tmp_path, capsys, [], '校長は何を読んだ？', mode='legacy')
    assert 'question_cross' not in out and qc_steps(out) == []
    rc, out = ask(tmp_path, capsys, [doc_file(tmp_path, 'ja.txt', DOC_JA)], '校長は何を読んだ？', mode='legacy')
    assert out['verdict'] == 'UNKNOWN_ROUTE_CONFIGURATION' and 'question_cross' not in out
