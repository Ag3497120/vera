"""W16-t2 (T2-1): `vera ask --mode round5 --document`, `vera serve` (decode_grammar.read_turn, the reading of `--no-llm` and of the fusion) and `vera chat --mode round5` answer a document
question through ONE function, `doc_answer.answer`. The same document and the same question give the same AnswerResult (verdict, values, evidence: byte for byte) at the three entrances.

The placement is a fake (`event_cross.default_lookup`, the path VERA_PLACEMENT takes) in every test; the same comparison also runs against the real placement r9 when it is on this machine
(the only skip of this file). The expectations of the hand-written table are written by hand from the meaning of the sentences; the other checks compare the entrances with each other."""
import contextlib
import io
import json
import os
from pathlib import Path

import pytest

from verantyx import cli
from verantyx import decode_grammar as G
from verantyx import doc_answer
from verantyx import event_cross as EC
from verantyx import observe as O

ROOT = Path(__file__).resolve().parents[1]
SETS = ROOT / 'artifacts' / 'w16-t2' / 'sets'
R9 = Path('/Users/motonisihikoudai/Projects/vera-impl/wt/W3-a6-S/build/coarse-W3a/full/r9/run2')

U4_DOC = '太郎は花子に本を渡した。花子は東京の大学で物理学を学んでいる。その本は昨年出版された。\n'
U4 = ['誰が花子に本を渡したか', '誰が花子に本を渡しましたか', '花子に本を渡したのは誰ですか', '太郎は花子に何を渡したか', '太郎は誰に本を渡したか', '花子はどこで物理学を学んでいるか',
      'その本はいつ出版されたか', '誰が花子に本を渡した？', '誰が花子に本を渡した', '太郎は花子に何を渡した？', '太郎は誰に本を渡した？']
# by hand, from the three sentences: the questions the product answers at all entrances (value) -- the others it may abstain on, never answer wrongly
U4_ANSWERED = {'誰が花子に本を渡したか': '太郎', '誰が花子に本を渡しましたか': '太郎', '太郎は誰に本を渡したか': '花子', '誰が花子に本を渡した？': '太郎', '誰が花子に本を渡した': '太郎',
               '太郎は誰に本を渡した？': '花子'}
PLACE = {w: 'PERSON' for w in ('太郎', '花子', '次郎', '先生', '生徒', '校長', '母', '弟', '店主', '客', '店員', '運転手', '父', '祖母', '漁師', '画家', '医者', '看護師', '技師', '姉', '妹', '兄', '学生')}
PLACE.update({w: 'ARTIFACT' for w in ('本', 'ノート', '手紙', '傘', '果物', '野菜', '箱', '荷物', '魚', '鍵', '地図', '論文', '人形', '絵', '薬', '書類', '橋', '図', '木', 'パン', '小説', '雑誌', '写真', '切符', '資料')})
PLACE.update({w: 'PLACE' for w in ('教室', '図書館', '市場', '港', '庭', '台所', '山', '海', '病院', '川', '体育館', '駅', '黒板', '研究室', '倉庫', '東京', '大学')})


def jdump(o):
    return json.dumps(o, ensure_ascii=False, sort_keys=True)


def result_key(ar):
    return jdump({k: ar.get(k) for k in ('verdict', 'values', 'evidence')})


@pytest.fixture(params=['fake', 'r9'])
def placement(request, tmp_path, monkeypatch):
    for name in ('VERA_PLACEMENT', 'VERA_COARSE_PLACEMENT', 'VERA_SOVEREIGN_ROOT', 'VERA_SOVEREIGN_STORE'):
        monkeypatch.delenv(name, raising=False)
    if request.param == 'r9':
        if not (R9 / 'manifest.json').is_file():
            pytest.skip('the real placement r9 is not on this machine (the fake placement runs the same comparison)')
        monkeypatch.setenv('VERA_PLACEMENT', str(R9))
        return 'r9'
    path = tmp_path / 'pl.json'
    path.write_text(json.dumps({'lemmas': {w: {'state': 'DECIDED', 'origin': 'direct', 'types': [t]} for w, t in PLACE.items()}, 'neighbors': {}}, ensure_ascii=False), encoding='utf-8')
    fp = O.FilePlacement.from_path(str(path))
    monkeypatch.setattr(EC, 'default_lookup', lambda *a, **k: fp)
    return 'fake'


@pytest.fixture
def spy(monkeypatch):
    """Every call of `doc_answer.answer` (the one function) is recorded as a deep copy of what it returned, in call order."""
    log = []
    orig = doc_answer.answer

    def wrapper(*a, **k):
        res = orig(*a, **k)
        log.append(json.loads(json.dumps(res, ensure_ascii=False, default=str)))
        return res
    monkeypatch.setattr(doc_answer, 'answer', wrapper)
    return log


def run_main(argv):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = cli.main(argv)
    return rc, buf.getvalue()


def entrances(spy, store, docs, question, monkeypatch):
    """The three entrances for one question: {'ask': (output, [AnswerResult]), 'serve': (reading, [..]), 'chat': (output, [..])}."""
    doc_args = sum([['--document', d] for d in docs], [])
    spy.clear()
    rc, out = run_main(['--store', store, 'ask', '--mode', 'round5'] + doc_args + ['--', question])
    got = {'ask': (json.loads(out), list(spy))}
    spy.clear()
    reading, _res = G.read_turn(question, 'factual', G.load_records(docs), docs)
    got['serve'] = (reading, list(spy))
    spy.clear()
    pending = iter([question, '/quit'])
    monkeypatch.setattr('verantyx.tui.read_input', lambda _p: next(pending))
    rc, out = run_main(['--store', store, 'chat', '--mode', 'round5', '--json'] + doc_args)
    body = '\n'.join(line for line in out.split('\n') if not line.startswith('[round5]'))
    got['chat'] = (json.loads(body), list(spy))
    return got


def check_one(got, question):
    ask, serve, chat = got['ask'], got['serve'], got['chat']
    assert [len(x[1]) for x in (ask, serve, chat)] == [1, 1, 1], question           # each entrance calls the one function once
    keys = {name: result_key(got[name][1][0]) for name in got}
    assert keys['ask'] == keys['serve'] == keys['chat'], (question, keys)            # T2-1: byte for byte
    ar = ask[1][0]
    for out in (ask[0], chat[0]):                                                     # (b) what ask and chat print is the AnswerResult's verdict, values and evidence
        assert out.get('verdict') == ar.get('verdict') and out.get('values') == ar.get('values') and out.get('evidence') == ar.get('evidence'), question
    reading = serve[0]
    if reading['type'] == 'QUESTION_CROSS':                                           # (c) serve shows the record answer only when it is the AnswerResult's
        assert ar['verdict'] == 'ANSWER' and reading['filler'] == ar['values'][0], question
        assert [s['text'] for s in reading['sources']] == ar['evidence'], question
        assert set(reading['sources'][0]) == {'source', 'line', 'text', 'sentence_id'}
    return ar, reading


def test_the_eleven_questions_of_u4_are_one_answer_at_the_three_entrances(placement, tmp_path, spy, monkeypatch):
    doc = tmp_path / 'doc.txt'
    doc.write_text(U4_DOC, encoding='utf-8')
    store = str(tmp_path / 'st.json')
    answered = {}
    for q in U4:
        ar, reading = check_one(entrances(spy, store, [str(doc)], q, monkeypatch), q)
        if ar['verdict'] == 'ANSWER':
            answered[q] = ar['values'][0]
    for q, want in U4_ANSWERED.items():                      # by hand: these are answered, and rightly
        assert answered.get(q) == want, q
    assert set(answered) - set(U4_ANSWERED) <= {'太郎は花子に何を渡した？', '太郎は花子に何を渡したか'}    # nothing else is answered, except the 何 question the later stage answers with a placement
    assert answered.get('太郎は花子に何を渡した？') in (None, '本') and answered.get('太郎は花子に何を渡したか') in (None, '本')


def own60():
    rows = [json.loads(line) for line in (SETS / 'own60' / 'questions.jsonl').read_text(encoding='utf-8').splitlines() if line.strip()]
    return rows


def test_the_sixty_questions_of_own60_are_one_answer_at_the_three_entrances(placement, tmp_path, spy, monkeypatch):
    store = str(tmp_path / 'st.json')
    n_answer = 0
    for row in own60():
        docs = [str(SETS / 'own60' / 'docs' / d) for d in row['docs']]
        ar, reading = check_one(entrances(spy, store, docs, row['question'], monkeypatch), row['question'])
        n_answer += ar['verdict'] == 'ANSWER'
    assert n_answer > 0                                                                 # the comparison is not between sixty abstentions


# by hand: a wish, hearsay and a bare `たら` are not the answer of a plain past question (the existing round-2 rule), at every entrance
TRAPS = [('次郎は小説を読みたかった。', '次郎は何を読んだ？'), ('恵子は写真を撮りたがっていた。', '恵子は何を撮った？'), ('駅員は切符を渡したら。', '駅員は何を渡したか'),
         ('社長は資料を渡したらしかった。', '社長は何を渡しましたか'), ('課長は地図を見たがっていた。', '課長は何を見たか')]


@pytest.mark.parametrize('sentence,question', TRAPS)
def test_a_wish_or_hearsay_is_not_an_answer_at_any_entrance(placement, tmp_path, spy, monkeypatch, sentence, question):
    """Not in the traps (by design): O38, `誰が小説を読んだ？` over `次郎は小説を読みたかった。` -- the reader drops the wish and answers 次郎. That is a known error of the reader (W16-t1b narrows it); it is
    not skipped or xfailed here because it is not in this table at all."""
    doc = tmp_path / 'trap.txt'
    doc.write_text(sentence + '\n', encoding='utf-8')
    ar, reading = check_one(entrances(spy, str(tmp_path / 'st.json'), [str(doc)], question, monkeypatch), question)
    assert ar['verdict'] != 'ANSWER' and reading['type'] != 'QUESTION_CROSS'


def test_the_form_of_the_question_does_not_change_the_serve_answer(placement, tmp_path, spy, monkeypatch):
    """The three forms that made serve abstain before (`か`, `ましたか`, no mark): serve answers as ask does, and a polar question is not made into an answer."""
    doc = tmp_path / 'doc.txt'
    doc.write_text(U4_DOC, encoding='utf-8')
    store = str(tmp_path / 'st.json')
    for q in ('誰が花子に本を渡したか', '誰が花子に本を渡しましたか', '誰が花子に本を渡した'):
        ar, reading = check_one(entrances(spy, store, [str(doc)], q, monkeypatch), q)
        assert ar['values'] == ['太郎'] and reading['type'] == 'QUESTION_CROSS' and reading['filler'] == '太郎', q
    ar, reading = check_one(entrances(spy, store, [str(doc)], '太郎は花子に本を渡しましたか？', monkeypatch), '太郎は花子に本を渡しましたか？')
    assert reading['type'] != 'QUESTION_CROSS'


def test_a_reader_reused_over_questions_answers_as_a_fresh_one_does(placement, tmp_path):
    """serve and chat keep one reader over many questions; ask builds one per question. The answers must not depend on that."""
    for name in ('u4', 'own60'):
        if name == 'u4':
            doc = tmp_path / 'doc.txt'
            doc.write_text(U4_DOC, encoding='utf-8')
            groups = [([str(doc)], U4)]
        else:
            by_doc = {}
            for row in own60():
                by_doc.setdefault(tuple(row['docs']), []).append(row['question'])
            groups = [([str(SETS / 'own60' / 'docs' / d) for d in docs], qs) for docs, qs in by_doc.items()]
        for docs, questions in groups:
            reused = doc_answer.prepare(docs)
            for q in questions:
                assert result_key(doc_answer.answer(q, reused)) == result_key(doc_answer.answer(q, docs)), q


def test_answer_checks_its_read_mode():
    assert doc_answer.answer('誰が来た？', [], read_mode=None)['verdict'] != 'ANSWER'
    for ok in (None, 'strict', 'assume'):
        doc_answer.answer('誰が来た？', [], read_mode=ok)
    with pytest.raises(ValueError, match='BAD_READ_MODE'):
        doc_answer.answer('誰が来た？', [], read_mode='guess')


# ---- ruling 5 (W16-t2 round 2): no placement does not make a second path -----------------------------------------------------------------------

@pytest.fixture
def noplace(tmp_path, monkeypatch):
    for name in ('VERA_PLACEMENT', 'VERA_COARSE_PLACEMENT', 'VERA_SOVEREIGN_ROOT', 'VERA_SOVEREIGN_STORE'):
        monkeypatch.delenv(name, raising=False)


@pytest.mark.parametrize('text,question,filler', [('太郎が地図を渡した。\n花子は本を読んだ。\n', '誰が地図を渡した？', '太郎'), ('母が部屋で手紙を読んだ。\nミナが走った。\n', '誰が走りましたか。', 'ミナ')])
def test_serve_without_a_placement_answers_through_the_same_function(noplace, tmp_path, spy, monkeypatch, text, question, filler):
    doc = tmp_path / 'd.txt'
    doc.write_text(text, encoding='utf-8')
    ar, reading = check_one(entrances(spy, str(tmp_path / 'st.json'), [str(doc)], question, monkeypatch), question)
    assert ar['verdict'] == 'ANSWER' and ar['values'] == [filler]
    assert reading['type'] == 'QUESTION_CROSS' and reading['filler'] == filler


def test_without_a_placement_a_question_only_the_later_stage_answers_is_an_abstention_at_all_three(noplace, tmp_path, spy, monkeypatch):
    doc = tmp_path / 'd.txt'
    doc.write_text('太郎が地図を渡した。\n花子は本を読んだ。\n', encoding='utf-8')
    q = '太郎は何を渡した？'
    ar, reading = check_one(entrances(spy, str(tmp_path / 'st.json'), [str(doc)], q, monkeypatch), q)
    assert ar['verdict'] != 'ANSWER' and reading['type'] == 'NO_RECORD' and reading['state'] == 'NO_TYPED_CANDIDATE'


def no_clock(o):
    if isinstance(o, dict):
        return {k: no_clock(v) for k, v in o.items() if not k.endswith('_ms')}
    return [no_clock(v) for v in o] if isinstance(o, list) else o


def test_ask_with_a_document_defaults_to_round5_and_legacy_is_refused_when_explicit(noplace, tmp_path):
    doc = tmp_path / 'doc.txt'
    doc.write_text(U4_DOC, encoding='utf-8')
    store = str(tmp_path / 'st.json')
    for q in U4:
        rc_a, out_a = run_main(['--store', store, 'ask', '--document', str(doc), '--', q])
        rc_b, out_b = run_main(['--store', store, 'ask', '--mode', 'round5', '--document', str(doc), '--', q])
        assert rc_a == rc_b and no_clock(json.loads(out_a)) == no_clock(json.loads(out_b)), q       # the same output but for the clock keys
    rc, out = run_main(['--store', store, 'ask', '--mode', 'legacy', '--document', str(doc), '--', U4[0]])
    assert rc == 2 and json.loads(out)['verdict'] == 'UNKNOWN_ROUTE_CONFIGURATION'
