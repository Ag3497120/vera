"""W3-c2: the frozen test data of the question observation (tests/observe/question/): it is the data that was frozen, it has the registered size, and the questions
run now (in this test, through `observe.run_entry`) give no wrong answer."""
import hashlib
import importlib.util
import json
from collections import Counter
from pathlib import Path

import pytest

TREE = Path(__file__).resolve().parent.parent
Q = TREE / 'tests' / 'observe' / 'question'


def _runner():
    spec = importlib.util.spec_from_file_location('w3c2_run_questions', Q / 'run_questions.py')
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _questions():
    return [json.loads(l) for l in (Q / 'questions.jsonl').read_text(encoding='utf-8').splitlines() if l.strip()]


def test_the_frozen_files_are_the_frozen_bytes():
    frozen = json.loads((Q / 'FROZEN_Q.json').read_text(encoding='utf-8'))
    assert frozen['frozen_at'].startswith('2026-10-03') and sorted(frozen['files']) == sorted(
        ['docs/QD%02d.jsonl' % i for i in range(1, 11)] + ['questions.jsonl', 'placement_q.json'])
    for name, sha in frozen['files'].items():
        assert hashlib.sha256((Q / name).read_bytes()).hexdigest() == sha, name


def test_the_data_has_the_registered_size_and_mix():
    docs = {}
    for p in sorted((Q / 'docs').glob('*.jsonl')):
        rows = [json.loads(l) for l in p.read_text(encoding='utf-8').splitlines() if l.strip()]
        docs[p.stem] = rows
        assert 5 <= len(rows) <= 10, p.name
        assert len({r['lang'] for r in rows}) == 1, 'a document does not mix languages: ' + p.name
    assert len(docs) == 10
    langs = Counter(rows[0]['lang'] for rows in docs.values())
    assert langs['ja'] >= 7 and langs['en'] >= 3
    qs = _questions()
    assert len(qs) >= 84 and len({q['id'] for q in qs}) == len(qs)
    by_hole = Counter(q['hole'] for q in qs)
    for hole in ('PERSON', 'THING', 'PLACE', 'TIME', 'RESTRICTOR', 'PROPERTY', 'CAUSE', 'MANNER'):
        assert by_hole[hole] >= 8, hole
    assert by_hole['POLAR'] >= 4 and by_hole['ILLFORMED'] >= 4
    assert sum(1 for q in qs if q['placement']) >= 10 and sum(1 for q in qs if q['direction']) >= 2
    kinds = Counter(q['truth']['kind'] for q in qs)
    assert all(kinds[k] > 0 for k in ('ONE', 'NONE', 'SPLIT', 'YESNO', 'ILLFORMED'))
    for hole in ('PERSON', 'THING', 'PLACE', 'TIME', 'RESTRICTOR', 'PROPERTY', 'CAUSE', 'MANNER'):
        assert {q['truth']['kind'] for q in qs if q['hole'] == hole} >= {'NONE'}, hole
    for q in qs:
        assert q['doc'] in docs and q['lang'] == docs[q['doc']][0]['lang']
        ids = {r['id'] for r in docs[q['doc']]}
        t = q['truth']
        assert set(t['evidence']) <= ids and set(t['extension_support']) <= ids and set(t['unread_support']) <= ids, q['id']


def test_the_docs_table_is_the_table_of_the_code_and_the_registration_precedes_the_freeze():
    text = (TREE / 'docs' / 'EVENT_CROSS.md').read_text(encoding='utf-8')
    assert '<!-- BEGIN table:w3c2_holes -->' in text and '<!-- END table:w3c2_holes -->' in text and '<!-- w3c2-prereg:begin -->' in text
    frozen = json.loads((Q / 'FROZEN_Q.json').read_text(encoding='utf-8'))
    import re
    reg = re.search(r'登録日時: (\d{4}-\d\d-\d\d \d\d:\d\d:\d\d)', text[text.index('穴の型（W3-c2。事前登録）'):]).group(1)
    obs = open(TREE / 'docs' / 'OBSERVATION.md', encoding='utf-8').read()
    reg2 = re.search(r'登録日時: (\d{4}-\d\d-\d\d \d\d:\d\d:\d\d)', obs[obs.index('事前登録（W3-c2）'):]).group(1)
    assert max(reg, reg2) < frozen['frozen_at'][:19]


def _corrections():
    path = Q / 'corrections.jsonl'
    rows = [json.loads(l) for l in path.read_text(encoding='utf-8').splitlines() if l.strip()] if path.exists() else []
    return {r['id']: r['after'] for r in rows}


def test_no_question_of_the_frozen_data_gets_a_wrong_answer_with_or_without_the_corrections():
    run = _runner()
    corr = _corrections()
    wrong, fill = [], Counter()
    for q in _questions():
        res, _ = run.run_one(q, str(Q / 'docs'), str(Q))
        assert res.exit_code == 0, (q['id'], res.error)
        out = json.loads(res.stdout)
        answer = out.get('answer')
        status = answer['status'] if answer else 'NO_ANSWER_KEY'
        for name, truth in (('as frozen', q['truth']), ('corrected', dict(q['truth'], **corr.get(q['id'], {})))):
            cls, detail = run.classify(truth, status, answer)
            if name == 'as frozen': fill[cls] += 1
            if cls == 'WRONG': wrong.append((name, q['id'], q['text'], status, detail))
        assert 'ANSWER' not in res.stdout
    assert wrong == []
    assert fill['CORRECT'] > 0
    assert set(corr) <= {q['id'] for q in _questions()}
