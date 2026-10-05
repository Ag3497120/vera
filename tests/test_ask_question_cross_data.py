"""W3-c4 test data (tests/observe/question_ask/, frozen by FROZEN.json): the files are unchanged, and every frozen question goes through `vera ask --mode round5 --document ...`
(`cli.main`, in this process, the placement handed over by replacing `event_cross.default_lookup`) with no WRONG answer and no ERROR state.
The numbers of CORRECT / FALSE_NONE / ABSTAINED are not asserted here: they are measured into artifacts/w3-c4/ by tests/observe/question_ask/run_ask.py.
"""
import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

from verantyx import event_cross as EC
from verantyx import observe as O

HERE = Path(__file__).resolve().parent
DATA = HERE / 'observe' / 'question_ask'


def _load(name):
    spec = importlib.util.spec_from_file_location(name, DATA / (name + '.py'))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


run_ask = _load('run_ask')


def _digest(p): return hashlib.sha256(p.read_bytes()).hexdigest()


def test_the_frozen_files_are_unchanged():
    for name in ('FROZEN.json', 'FROZEN_EXTRA.json', 'FROZEN_EXTRA2.json'):
        frozen = json.loads((DATA / name).read_text(encoding='utf-8'))
        assert frozen['frozen_at'] and frozen['files']
        changed = [rel for rel, sha in frozen['files'].items() if _digest(DATA / rel) != sha]
        assert changed == [], (name, changed)
    assert len(json.loads((DATA / 'FROZEN.json').read_text(encoding='utf-8'))['files']) >= 30


def _questions(*names):
    return [json.loads(l) for n in names for l in (DATA / n).read_text(encoding='utf-8').splitlines() if l.strip()]


def test_the_frozen_data_has_the_registered_scale():
    qs = _questions('questions.jsonl', 'questions_nodoc.jsonl')
    docs = sorted(p.name for p in (DATA / 'docs').glob('AD*.txt'))
    assert len(docs) == 10 and len(qs) >= 60
    kinds = [q['truth']['kind'] for q in qs]
    assert kinds.count('ONE') >= 20 and kinds.count('NONE') >= 10 and kinds.count('SPLIT') >= 8
    assert sum(1 for q in qs if not q['docs']) >= 4 and sum(1 for q in qs if q['category'] == 'twodoc') >= 4
    assert sum(1 for q in qs if q['category'] == 'declarative') >= 2 and sum(1 for q in qs if q['category'] == 'unplaced') >= 3
    assert sum(1 for q in qs if q['category'] == 'negonly') >= 4 and sum(1 for q in qs if q['category'] == 'existing') >= 6
    assert sum(1 for q in qs if q['truth']['kind'] in ('YESNO', 'ILLFORMED') and q['category'] == 'illformed') >= 6


def _run_all(questions, docs_dir, placement, monkeypatch, tmp_path):
    monkeypatch.delenv('VERA_PLACEMENT', raising=False)
    fp = O.FilePlacement.from_path(str(placement))
    monkeypatch.setattr(EC, 'default_lookup', lambda *a, **k: fp)
    run = run_ask.make_inproc(HERE.parent, None)

    class Args:
        ask_mode = 'round5'; no_docs = False; ask_args = ''
    rows = []
    for l in Path(questions).read_text(encoding='utf-8').splitlines():
        if not l.strip(): continue
        q = json.loads(l)
        rc, stdout, _ = run(q, docs_dir, Args, str(tmp_path / 'st.json'))
        o = json.loads(stdout)
        cls, base, detail = run_ask.classify(q, o)
        rows.append((q['id'], cls, (o.get('question_cross') or {}).get('state'), detail))
    return rows


@pytest.mark.parametrize('name,questions,docs_dir,placement', [
    ('new', DATA / 'questions.jsonl', DATA / 'docs', DATA / 'placement_ask.json'),
    ('nodoc', DATA / 'questions_nodoc.jsonl', DATA / 'docs', DATA / 'placement_ask.json'),
    ('b2like', DATA / 'b2like' / 'questions.jsonl', DATA / 'b2like' / 'docs', DATA / 'placement_ask.json'),
    ('w3c2', DATA / 'w3c2' / 'questions.jsonl', DATA / 'w3c2', HERE / 'observe' / 'question' / 'placement_q.json'),
    ('extra2', DATA / 'extra2' / 'questions.jsonl', DATA / 'extra2' / 'docs', DATA / 'extra2' / 'placement_extra2.json'),
])
def test_no_wrong_answer_and_no_error_on_the_frozen_questions(name, questions, docs_dir, placement, monkeypatch, tmp_path):
    rows = _run_all(questions, docs_dir, placement, monkeypatch, tmp_path)
    assert len(rows) >= 3
    assert [r for r in rows if r[1] == 'WRONG'] == []
    assert [r for r in rows if r[2] == 'ERROR'] == []


def test_extra2_no_stage_answer_where_the_document_says_another_form(monkeypatch, tmp_path):
    """Round 2 (M1): every question of extra2 that expects no stage answer gets neither a stage answer nor a stage tie; the controls written in the same form still answer.
    Integration (auditor ruling 2026-10-06, W16-t1b K800): the three controls X011 (先生は何を読みたかった？), X012 (漁師は何を運びたがった？) and X014 (課長は何を見たがっていた？) ask about a desire
    sentence, which the reader no longer reads as an event, so they are abstentions now (answer -> abstention, the direction the ruling allows; measured: 3 controls still answer, 3 are lost). The floor of the answered controls is lowered from 6 to the measured 3 for exactly that reason. Old expectation: `len(controls) >= 6`."""
    monkeypatch.delenv('VERA_PLACEMENT', raising=False)
    fp = O.FilePlacement.from_path(str(DATA / 'extra2' / 'placement_extra2.json'))
    monkeypatch.setattr(EC, 'default_lookup', lambda *a, **k: fp)
    run = run_ask.make_inproc(HERE.parent, None)

    class Args:
        ask_mode = 'round5'; no_docs = False; ask_args = ''
    qs = _questions('extra2/questions.jsonl')
    assert len(qs) >= 40 and sum(1 for q in qs if q.get('expect_no_stage_answer')) >= 25
    answered = {}
    for q in qs:
        rc, stdout, _ = run(q, DATA / 'extra2' / 'docs', Args, str(tmp_path / 'st.json'))
        o = json.loads(stdout)
        stage = o.get('door') == 'question_cross' or o.get('verdict') == 'AMBIGUOUS_QUESTION_CROSS_TIE'
        if q.get('expect_no_stage_answer'): assert not stage, (q['id'], q['text'], o.get('text'))
        if stage and o.get('verdict') == 'ANSWER': answered[q['id']] = o['text']
    controls = {q['id']: q['truth']['fillers'][0] for q in qs if q['category'] in ('control_match', 'control_plain') and q['id'] in answered}
    assert len(controls) >= 3 and all(answered[i] == f for i, f in controls.items())
    assert not {'X011', 'X012', 'X014'} & set(answered), sorted(answered)     # the three desire-sentence controls abstain (K800); nothing else of the controls was lost
