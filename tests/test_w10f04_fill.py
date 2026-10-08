"""W10-f04 (O1/O4/O5, K281-K283, K285, K286): `fill_candidates.ask_and_gate`. The frozen scripts (tests/fusion/w10f04/fake_scripts.jsonl, written before the code) run against the placement r8 (read only);
the K285/K286 tests use a small fake placement and look at what is SENT at the backend boundary (`FakeBackend.sent`), not at the arguments of a function."""
import collections
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from verantyx import decode_grammar as G
from verantyx import fill_candidates as F
from verantyx import llm_backend as LB
from verantyx import llm_choice as LC
from verantyx import semantic_read as S
from verantyx.testimony_ledger import TestimonyLedger
from tests.test_w10f04_holes import FakePlacement, decided, fake, fake_two_holes, multiple

R8 = '/Users/motonisihikoudai/Projects/vera-impl/build/coarse-W3a/full/r8/run2'
DATA = Path(__file__).parent / 'fusion' / 'w10f04' / 'fake_scripts.jsonl'


def rows():
    return [json.loads(l) for l in DATA.read_text(encoding='utf-8').splitlines()]


def decide(sentence, steps, placement, hole=('へ', '図書館'), *, name='fake', mask=True, records=None, ledger=None, k=5, model='fake-model'):
    ho = S.read_with_holes(sentence, placement=placement)
    idx = next(i for i, h in enumerate(ho['holes']) if (h['particle'], h['head']) == hole)
    fb = LB.FakeBackend(steps)
    n = [0]

    def ids():
        n[0] += 1
        return 'id%03d' % n[0]
    d = F.ask_and_gate(ho, text=sentence, chat=lambda m, msgs, f: LB.chat('fake', m, msgs, f, fake=fb), model=model, backend_name=name, hole=idx, placement=placement,
                       choice_ledger=LC.ChoiceLedger(None), records=records, mask_user_text=mask, id_source=ids, order_source=lambda m: list(range(m)), ledger=ledger, k=k)
    return d, fb


def op(type_, words, role='goal'):
    return {'raw': json.dumps({'type': type_, 'role': role, 'near_words': words}, ensure_ascii=False)}


SENT2, HOLE2 = 'ウサギが図書館へ歩いた。', ('が', 'ウサギ')        # r3: a sentence of TWO holes whose が hole a candidate can be adopted for (a one-hole sentence is never adopted: J16)


def op2(words, type_='ANIMAL'):
    return op(type_, words, 'agent')


def record_of(sentence, roles):
    """A record cross made by hand: a readable sentence of the same predicate and polarity, with the arms replaced (no reader types the hole word in a record)."""
    return SimpleNamespace(crosses={'rec0': dict(G.cross_of(sentence)[0], roles=dict(roles))})


@pytest.fixture
def r8(monkeypatch):
    if not Path(R8).exists(): pytest.skip('ENV_MISSING[coarse placement r8/run2]')       # integration (auditor, 2026-10-04): the W5-e2/W3-b4 pattern; r8 only exists on the Pro
    monkeypatch.setenv('VERA_PLACEMENT', R8)
    return R8


def test_frozen_scripts_every_row_as_expected(r8):
    got = collections.Counter()
    reasons = collections.Counter()
    q = S._placement_query(r8)
    for r in rows():
        ho = S.read_with_holes(r['sentence'], placement=r8)
        idx = next(i for i, h in enumerate(ho['holes']) if (h['particle'], h['head']) == (r['hole']['particle'], r['hole']['head']))
        e = r['expect']
        recs = SimpleNamespace(crosses={'rec%d' % i: (dict(G.cross_of(s)[0], roles=dict(r['record_roles'][i])) if r.get('record_roles') else G.cross_of(s)[0]) for i, s in enumerate(r['records'])}) if r['records'] else None
        if r.get('call'):            # r3: the gate itself is called (the pipeline does not reach it in a sentence of r8: docs section 6.6, J17)
            decl0 = json.loads(r['steps'][0]['raw'])
            word, wtype = decl0['near_words'][0], decl0['type']
            reason = F._gate_b(r['sentence'], ho, idx, word, wtype, q, None, {})[0] if r['call'] == 'gate_b' else F._gate_c(r['sentence'], ho, idx, word, q, recs, {})[0]
            assert e['status'] == 'NOT_ADOPTED' and reason and reason.startswith(e['reason']), (r['id'], reason)
            got[r['gate']] += 1
            reasons[(r['gate'], reason.split(':')[0])] += 1
            continue
        fb = LB.FakeBackend(r['steps'])
        n = [0]

        def ids():
            n[0] += 1
            return 'id%03d' % n[0]
        d = F.ask_and_gate(ho, text=r['sentence'], chat=lambda m, msgs, f, fb=fb: LB.chat('fake', m, msgs, f, fake=fb), model='fake-model', hole=idx, placement=r8,
                           choice_ledger=LC.ChoiceLedger(None), records=recs, id_source=ids, order_source=lambda m: list(range(m)))
        assert (d.status, d.candidate) == (e['status'], e['word']), r['id']
        assert d.reason.startswith(e['reason']), (r['id'], d.reason)
        if d.status == 'ADOPTED':
            assert d.origin == 'testimony' and d.basis.startswith('LLM_TESTIMONY_FILL:fake-model:') and d.basis.endswith(d.choice_decision_id)
            assert any(x['gate'] == 'passed' and x.get('b_prime') == 'PASSED' and x.get('a4_role') for x in d.gate_log), r['id']       # every adoption passed (a4) and (b')
        if e.get('split_kind'):
            assert [x['split_kind'] for x in d.gate_log if x['gate'] == 'a4'], r['id']
            assert all(x['split_kind'] == e['split_kind'] for x in d.gate_log if x['gate'] == 'a4'), r['id']
        if e.get('gate_log_passed'):
            (passed,) = [x for x in d.gate_log if x['gate'] == 'passed']
            assert all(passed.get(k) == v for k, v in e['gate_log_passed'].items()), r['id']
        got[r['gate']] += 1
        reasons[(r['gate'], d.reason.split(':')[0])] += 1
    for gate in ('A1', 'A2', 'A3', 'B', 'C', 'ADOPT', 'BP', 'D', 'BACKEND'):
        assert got[gate] >= 10, gate
    assert got['A4U'] >= 10 and got['A4S'] >= 10 and got['A4'] >= 10
    assert reasons[('A4U', 'GATE_A_HOLE_WORD_UNPLACED')] >= 10 and reasons[('A4S', 'GATE_A_ROLE_SPLIT')] >= 10
    # the label of a group and the reason of its rows correspond (round 3: a group cannot be satisfied by rows of another reason)
    want = {'A1': ('GATE_A_NOT_PLACED', 'GATE_A_TYPE_NOT_EXPECTED'), 'A2': ('GATE_A_DECLARED_TYPE_MISMATCH',), 'A3': ('GATE_A_DECLARED_TYPE_NOT_OF_HOLE_WORD',),
            'A4': ('GATE_A_HOLE_WORD_UNPLACED', 'GATE_A_ROLE_SPLIT'), 'A4U': ('GATE_A_HOLE_WORD_UNPLACED',), 'A4S': ('GATE_A_ROLE_SPLIT',), 'ADOPT': ('ADOPTED',), 'BP': ('ADOPTED',),
            'B': ('GATE_B_',), 'C': ('GATE_C_CONTRADICTS_RECORD',), 'D': ('GATE_D_',), 'BACKEND': ('BACKEND_FAILED',), 'OPEN': ('OPEN_DECLARATION_INVALID',), 'NONE': ('NO_CANDIDATE_WORDS',)}
    for (gate, reason), n_ in reasons.items():
        assert any(reason.startswith(w) for w in want[gate]), (gate, reason)


def test_gate_order_records_the_first_gate_that_fails():
    p = fake_two_holes()
    d, _ = decide(SENT2, [op2(['駅', '犬'])], p, HOLE2)
    log = {x['word']: x for x in d.gate_log}
    assert log['駅'] == dict(word='駅', gate='a1', reason='GATE_A_TYPE_NOT_EXPECTED') and log['犬']['gate'] == 'passed' and log['犬']['a4_role'] == 'agent' and log['犬']['b_prime'] == 'PASSED'
    d, _ = decide(SENT2, [op2(['犬'], 'PERSON')], p, HOLE2)
    assert d.reason == 'GATE_A_DECLARED_TYPE_MISMATCH' and d.gate_log[0]['gate'] == 'a2'


def test_a_tie_is_an_abstention_whatever_the_order():
    p = fake_two_holes()
    for words in (['犬', '猫'], ['猫', '犬']):
        d, fb = decide(SENT2, [op2(words)], p, HOLE2)
        assert (d.status, d.reason, d.candidate) == ('NOT_ADOPTED', 'GATE_D_TIE', None)
        assert fb.calls == 1          # the closed ask is never made: there is no winner to confirm


def test_near_words_order_does_not_change_the_decision():
    p = fake_two_holes()
    outs = []
    for words in (['犬', '駅'], ['駅', '犬']):
        d, _ = decide(SENT2, [op2(words), {'pick': '犬'}, {'pick': '犬'}], p, HOLE2)
        outs.append((d.status, d.reason, d.candidate))
    assert outs[0] == outs[1] == ('ADOPTED', 'ADOPTED', '犬')


def test_candidate_is_testimony_never_a_record():
    d, _ = decide(SENT2, [op2(['犬']), {'pick': '犬'}, {'pick': '犬'}], fake_two_holes(), HOLE2)
    assert d.status == 'ADOPTED' and d.origin == 'testimony' and d.basis.startswith('LLM_TESTIMONY_FILL:')
    assert d.provenance == {'backend': 'fake', 'model': 'fake-model', 'version': ''}


@pytest.mark.parametrize('kind', ['TIMEOUT', 'CONNECT_FAILED', 'HTTP_ERROR', 'BAD_RESPONSE', 'SCRIPT_EXHAUSTED'])
def test_backend_failures_are_typed_and_are_not_no_candidate(kind):
    d, _ = decide('母が図書館へ歩いた。', [{'fail': kind}], fake())
    assert (d.status, d.reason) == ('BACKEND_FAILED', 'BACKEND_FAILED:' + kind) and d.candidate is None
    d, _ = decide(SENT2, [op2(['犬']), {'fail': kind}], fake_two_holes(), HOLE2)            # the closed ask fails (r3: in a two-hole sentence; a one-hole sentence never reaches it)
    assert d.status == 'BACKEND_FAILED' and d.reason == 'BACKEND_FAILED:' + kind
    assert d.reason != 'NO_CANDIDATE_WORDS'


def test_an_empty_answer_is_typed():
    d, _ = decide('母が図書館へ歩いた。', [{'raw': '   '}], fake())
    assert (d.status, d.reason) == ('BACKEND_FAILED', 'BACKEND_FAILED:EMPTY_CONTENT')


@pytest.mark.parametrize('raw,why', [('駅です', 'NOT_JSON'), ('{"type":"STATION","role":null,"near_words":["駅"]}', 'TYPE_NOT_IN_ENUM'),
                                     ('{"type":"PLACE","role":"patient","near_words":["駅"]}', 'ROLE_NOT_IN_ENUM'), ('{"type":"PLACE","role":null,"near_words":["a","b","c","d","e","f"]}', 'NEAR_WORDS'),
                                     ('{"type":"PLACE","role":null}', 'KEYS'), ('{"type":"PLACE","role":null,"near_words":["駅"],"x":1}', 'KEYS'),
                                     ('{"type":"PLACE","type":"TIME","role":null,"near_words":[]}', 'NOT_JSON')])
def test_open_declaration_outside_the_schema(raw, why):
    d, _ = decide('母が図書館へ歩いた。', [{'raw': raw}], fake())
    assert d.status == 'NOT_ADOPTED' and d.reason == 'OPEN_DECLARATION_INVALID:' + why


def test_the_open_schema_is_closed_and_built_from_the_17_types():
    # Integration of W3-a6 (auditor, 2026-10-05): NOUN_TYPES gained RELATIVE_POSITION (18). The open declaration asks the type of the hole WORD, and a word can be a
    # relative position, so the enum follows NOUN_TYPES (18); a RELATIVE_POSITION claim never matches a place/goal hole and falls at (a2)/(a3). Name kept.
    p = fake()
    d, fb = decide('母が図書館へ歩いた。', [op('PLACE', [])], p)
    fmt = fb.sent[0]['fmt']
    assert fmt['additionalProperties'] is False and fmt['properties']['type']['enum'] == sorted(S.NOUN_TYPES if hasattr(S, 'NOUN_TYPES') else __import__('verantyx.coarse_types', fromlist=['x']).NOUN_TYPES)
    assert len(fmt['properties']['type']['enum']) == len(__import__('verantyx.coarse_types', fromlist=['x']).NOUN_TYPES) == 18 and fmt['properties']['role']['enum'] == ['goal', None] and fmt['properties']['near_words']['maxItems'] == 5
    assert d.reason == 'NO_CANDIDATE_WORDS'


def test_a_contradicting_record_stops_the_candidate(r8):
    steps = [op2(['犬']), {'pick': '犬'}, {'pick': '犬'}]
    recs = record_of('母が駅へ走らなかった。', {'agent': '犬', 'goal': '図書館'})            # the same arms, the opposite polarity
    d, _ = decide('ウサギが図書館へ走った。', steps, r8, HOLE2, records=recs)
    assert d.reason == 'GATE_C_CONTRADICTS_RECORD:rec0' and d.records_checked == 1
    d, _ = decide('ウサギが図書館へ走った。', steps, r8, HOLE2, records=record_of('母が駅へ走らなかった。', {'agent': '兄', 'goal': '図書館'}))
    assert d.status == 'ADOPTED' and d.records_checked == 1


def test_the_gate_b_reread_rejects_a_slot_the_reader_does_not_read(r8):
    ho = S.read_with_holes('兄が窓口で名乗った。', placement=r8)            # r3: the gate itself (a one-hole sentence is stopped by (a4) before it)
    assert F._gate_b('兄が窓口で名乗った。', ho, 0, '玄関', 'PLACE', S._placement_query(r8), None, {})[0] == 'GATE_B_REREAD_NOT_READABLE'


def test_realize_is_recorded_and_can_be_required(r8):
    q = S._placement_query(r8)
    ho = S.read_with_holes('母が図書館へ歩いた。', placement=r8)            # r3: the gate itself, on a one-hole sentence (the realizer step exists only there)
    # Integration of W3-d1 (auditor, 2026-10-05): the realizer now accepts a typed cross and rereads with the same placement, so J10 is closed: the gate
    # realizes `母が駅へ歩いた。` and reads it back (REALIZED). The frozen value REFUSED was the hole W3-d1 was opened for.
    assert F._gate_b('母が図書館へ歩いた。', ho, 0, '駅', 'PLACE', q, r8, {}) == (None, 'REALIZED')
    assert F._gate_b('母が図書館へ歩いた。', ho, 0, '駅', 'PLACE', q, r8, {}, True) == (None, 'REALIZED')
    d, _ = decide('ウサギが図書館へ走った。', [op2(['犬']), {'pick': '犬'}, {'pick': '犬'}], r8, HOLE2)
    assert d.status == 'ADOPTED' and d.gate_log[0]['realize'] == 'SKIPPED_OTHER_HOLES'                       # in a two-hole sentence the step is skipped, and the record says so


# ---- K285: another backend name, the same script, the same decision --------------------------------------------------------------------
def test_the_backend_name_does_not_change_the_decision():
    runs = []
    for name in ('ollama', 'openai', 'fake'):
        out = []
        for sent, steps, hole in [(SENT2, [op2(['犬']), {'pick': '犬'}, {'pick': '犬'}], HOLE2),
                                  (SENT2, [op2(['駅', '犬'])] + [{'pick': None}], HOLE2),
                                  ('母が図書館へ歩いた。', [op('PLACE', ['駅'])], ('へ', '図書館')),            # r3: a one-hole sentence, refused by (a4)
                                  (SENT2, [{'fail': 'TIMEOUT'}], HOLE2)]:
            d, _ = decide(sent, steps, fake_two_holes(), hole, name=name)
            out.append((d.status, d.reason, d.candidate, d.gate_log, d.declaration))
        runs.append(out)
    assert runs[0] == runs[1] == runs[2]


# ---- K286: what is sent ----------------------------------------------------------------------------------------------------------------
def sent_text(fb):
    return '\n'.join(m['content'] for s in fb.sent for m in s['messages']) + '\n' + '\n'.join(json.dumps(s['fmt'], ensure_ascii=False) for s in fb.sent)


def test_mask_the_sentence_and_the_other_arms_do_not_leave():
    sentence = '母が図書館へ歩いた。'            # r3: a one-hole sentence (the open ask only: (a4) refuses it); a non-hole arm (母) exists only here
    d, fb = decide(sentence, [op('PLACE', ['駅'])], fake())
    blob = sent_text(fb)
    assert d.mask_user_text is True and len(fb.sent) == 1 and d.reason == 'GATE_A_ROLE_SPLIT'
    for leaked in (sentence, sentence.rstrip('。'), hashlib.sha256(sentence.encode()).hexdigest(), '母'):
        assert leaked not in blob, leaked
    assert '図書館' in blob and '歩く' in blob and '〈PERSON〉' in blob and F.CROSS_TOKENS_VERSION in blob      # the hole's word, the predicate and the coordinates are sent
    sentence = SENT2                           # r3: the whole flow (the open ask and the two closed asks) of an adoption
    d, fb = decide(sentence, [op2(['犬']), {'pick': '犬'}, {'pick': '犬'}], fake_two_holes(), HOLE2)
    blob = sent_text(fb)
    assert d.status == 'ADOPTED' and len(fb.sent) == 3
    for leaked in (sentence, sentence.rstrip('。'), hashlib.sha256(sentence.encode()).hexdigest()):
        assert leaked not in blob, leaked
    assert 'ウサギ' in blob and '図書館' in blob and '歩く' in blob and F.CROSS_TOKENS_VERSION in blob          # the hole's word, the other hole's word (a hole: J5), the predicate, the coordinates


def test_mask_off_sends_the_sentence_and_the_detector_sees_it():
    sentence = '母が図書館へ歩いた。'
    d, fb = decide(sentence, [op('PLACE', ['駅']), {'pick': '駅'}, {'pick': '駅'}], fake(), mask=False)
    assert d.mask_user_text is False and sentence in sent_text(fb) and '母' in sent_text(fb)
    d, fb = decide(SENT2, [op2(['犬']), {'pick': '犬'}, {'pick': '犬'}], fake_two_holes(), HOLE2, mask=False)            # r3: added: the whole flow of an adoption, unmasked
    assert d.status == 'ADOPTED' and SENT2 in sent_text(fb)


def test_mask_the_ledgers_do_not_keep_the_sentence(tmp_path):
    sentence = SENT2
    led = TestimonyLedger(tmp_path / 't.jsonl')
    ho = S.read_with_holes(sentence, placement=fake_two_holes())
    fb = LB.FakeBackend([op2(['犬']), {'pick': '犬'}, {'pick': '犬'}])
    choice = LC.ChoiceLedger(tmp_path / 'c.jsonl')
    d = F.ask_and_gate(ho, text=sentence, chat=lambda m, msgs, f: LB.chat('fake', m, msgs, f, fake=fb), model='m', placement=fake_two_holes(), ledger=led, choice_ledger=choice, hole=0,
                       order_source=lambda n: list(range(n)))
    assert d.status == 'ADOPTED'
    for f in (tmp_path / 't.jsonl', tmp_path / 'c.jsonl'):
        text = f.read_text(encoding='utf-8')
        assert sentence not in text and hashlib.sha256(sentence.encode()).hexdigest() not in text.replace(d.context['sentence_sha256'], '')
    assert d.context['sentence_sha256'] in (tmp_path / 't.jsonl').read_text(encoding='utf-8')     # the sha is what the ledger keeps
    one = '母が図書館へ歩いた。'            # r3: a one-hole sentence that is not adopted is on the ledger too (J14), with no non-hole arm of the user's
    led2 = TestimonyLedger(tmp_path / 't2.jsonl')
    ho = S.read_with_holes(one, placement=fake())
    d = F.ask_and_gate(ho, text=one, chat=lambda m, msgs, f: LB.chat('fake', m, msgs, f, fake=LB.FakeBackend([op('PLACE', ['駅'])])), model='m', placement=fake(), ledger=led2,
                       choice_ledger=LC.ChoiceLedger(None))
    assert d.status == 'NOT_ADOPTED' and d.reason == 'GATE_A_ROLE_SPLIT'
    text = (tmp_path / 't2.jsonl').read_text(encoding='utf-8')
    assert one not in text and hashlib.sha256(one.encode()).hexdigest() not in text.replace(d.context['sentence_sha256'], '') and '"母"' not in text and '"not_adopted"' in text


def test_coordinates_carry_the_version_and_no_probe_type():
    p = fake()
    ho = S.read_with_holes('母が図書館へ歩いた。', placement=p)
    c = F.coordinates(ho, '母が図書館へ歩いた。', p, mask_user_text=True)
    assert c['cross_tokens_version'] == 'verantyx.cross_tokens/1' == F.CROSS_TOKENS_VERSION
    assert c['tokens'].startswith('<cross>') and 'hole_probe' not in c['tokens'] and '"state" : "MULTIPLE"' in c['tokens']       # the real answer of the hole's word
    assert '母' not in c['tokens'].replace('"母"', '') or '"term" : "母"' not in c['tokens']
    plain = F.coordinates(ho, '母が図書館へ歩いた。', p, mask_user_text=False)
    assert '"surface" : "母"' in plain['tokens']


def test_no_hole_and_no_placement_are_typed():
    ho = S.read_with_holes('母が駅へ歩いた。', placement=fake())
    d = F.ask_and_gate(ho, text='母が駅へ歩いた。', chat=lambda *a: {}, model='m', placement=fake())
    assert d.status == 'NO_HOLE'
    ho = S.read_with_holes('母が図書館へ歩いた。', placement=fake())
    d = F.ask_and_gate(ho, text='母が図書館へ歩いた。', chat=lambda *a: {}, model='m', placement=None)
    assert (d.status, d.reason) == ('NOT_ADOPTED', 'NO_PLACEMENT')


def test_a_backend_that_raises_is_a_typed_failure():
    def boom(model, msgs, fmt):
        raise RuntimeError('x')
    ho = S.read_with_holes('母が図書館へ歩いた。', placement=fake())
    d = F.ask_and_gate(ho, text='母が図書館へ歩いた。', chat=boom, model='m', placement=fake())
    assert (d.status, d.reason) == ('BACKEND_FAILED', 'BACKEND_FAILED:CONNECT_FAILED')


def test_fill_candidates_cannot_write_human_confirmed(tmp_path):
    import inspect
    src = inspect.getsource(F)
    assert 'human_confirmed' not in src and '.confirm(' not in src


# ---- r2 (review r1): M1 the declaration is about the WORD (J12), M2 no probe type in the coordinates, M3 gate (c) says what it compared -----------------------------------------
def _p4_shape(r8, sentence, hole, role, declared, word):
    """The shape qwen3.5:4b returned in P4 r1: the declaration fits the POSITION, and the candidate is a word the placement decides with that very type."""
    return decide(sentence, [op(declared, [word], role), {'pick': word}, {'pick': word}], r8, hole=hole)


@pytest.mark.parametrize('sentence,hole,role,declared,word', [
    ('手紙が駅へ飛んだ。', ('が', '手紙'), 'agent', 'ANIMAL', '鳥'), ('手紙が駅へ飛んだ。', ('が', '手紙'), 'agent', 'ANIMAL', '犬'),
    ('兄が山田に催促した。', ('に', '山田'), 'time', 'TIME', '夜'), ('姉が本社に請求した。', ('に', '本社'), 'time', 'TIME', '冬'),
    ('妹が山田に申告した。', ('に', '山田'), 'time', 'TIME', '夏'), ('夫婦が森へ歩いた。', ('が', '夫婦'), 'agent', 'ANIMAL', '鳥')])
def test_a_declaration_that_fits_the_position_but_not_the_word_is_not_adopted(r8, sentence, hole, role, declared, word):
    d, fb = _p4_shape(r8, sentence, hole, role, declared, word)
    assert (d.status, d.reason, d.candidate) == ('NOT_ADOPTED', 'GATE_A_DECLARED_TYPE_NOT_OF_HOLE_WORD', None)
    assert d.gate_log[0]['gate'] == 'a3' and fb.calls == 1                      # the closed ask is never made


def test_gate_a4_refuses_a_hole_word_the_placement_has_no_type_for(r8, tmp_path):
    led = TestimonyLedger(tmp_path / 'z.jsonl')
    d, fb = decide('父が税務署に申告した。', [op('TIME', ['夜'], 'time'), {'pick': '夜'}, {'pick': '夜'}], r8, hole=('に', '税務署'), ledger=led)
    assert (d.status, d.reason, d.candidate) == ('NOT_ADOPTED', 'GATE_A_HOLE_WORD_UNPLACED', None) and fb.calls == 1        # the closed ask is never made
    row = d.gate_log[0]
    assert row['gate'] == 'a4' and row['word'] == '夜' and row['hole_word_types'] == [] and row['hole_word_state'] in ('UNPLACED', 'UNKNOWN') and row['role_by_type'] == {} and 'split_kind' not in row
    rows = [r for r in led.entries() if r['type'] == 'not_adopted']                    # J14: the declaration and the candidate stay on the ledger as testimony
    assert len(rows) == 1 and rows[0]['word'] == '税務署' and rows[0]['declaration']['near_words'] == ['夜'] and rows[0]['gate_log'][0]['gate'] == 'a4'
    d, _ = decide('母が荷物を後へ押した。', [op('INFO_LANGUAGE', ['本'], 'patient'), {'pick': '本'}, {'pick': '本'}], r8, hole=('を', '荷物'))
    assert d.reason == 'GATE_A_HOLE_WORD_UNPLACED'


def test_gate_a4_refuses_when_the_types_of_the_hole_word_do_not_fall_in_one_role(r8):
    d, fb = decide('妹が東京に旅行した。', [op('TIME', ['夏'], 'time'), {'pick': '夏'}, {'pick': '夏'}], r8, hole=('に', '東京'))            # 東京 [PLACE, TIME]: PLACE is not read, TIME reads `time`
    assert (d.status, d.reason, d.candidate) == ('NOT_ADOPTED', 'GATE_A_ROLE_SPLIT', None) and fb.calls == 1
    row = d.gate_log[0]
    assert row['gate'] == 'a4' and row['split_kind'] == 'TYPE_NOT_READ' and row['role_by_type'] == {'PLACE': None, 'TIME': 'time'} and row['hole_word_types'] == ['PLACE', 'TIME']
    d, _ = decide('隊員が港へ走った。', [op('PERSON', ['兵士'], 'agent'), {'pick': '兵士'}, {'pick': '兵士'}], r8, hole=('が', '隊員'))     # the adoption of P4 r2: 隊員 [PERSON, QUANTITY]
    assert d.reason == 'GATE_A_ROLE_SPLIT' and d.gate_log[0]['split_kind'] == 'TYPE_NOT_READ' and d.gate_log[0]['role_by_type']['QUANTITY'] is None


def test_gate_a4_lets_through_a_hole_whose_types_all_read_the_same_role(r8):
    d, fb = decide('ウサギが図書館へ走った。', [op2(['犬']), {'pick': '犬'}, {'pick': '犬'}], r8, HOLE2)
    assert (d.status, d.reason, d.candidate) == ('ADOPTED', 'ADOPTED', '犬') and fb.calls == 3
    (passed,) = [x for x in d.gate_log if x['gate'] == 'passed']
    assert passed['a4_role'] == 'agent' and passed['b_prime'] == 'PASSED' and d.origin == 'testimony'
    d, _ = decide('ウサギが図書館へ走った。', [op('PLACE', ['駅'], 'goal'), {'pick': '駅'}, {'pick': '駅'}], r8, hole=('へ', '図書館'))      # the other hole of the same sentence: GROUP_ORG is not read
    assert d.reason == 'GATE_A_ROLE_SPLIT'


def test_gate_a4_counts_a_type_that_is_not_read_as_a_split_and_the_reason_does_not_depend_on_the_number_of_words(r8):
    d, _ = decide('妹が東京に旅行した。', [op('TIME', ['夏', '夜'], 'time')], r8, hole=('に', '東京'))
    assert d.reason == 'GATE_A_ROLE_SPLIT' and [x['gate'] for x in d.gate_log] == ['a4', 'a4']          # J18: two words, the hole's reason
    d, _ = decide('父が税務署に申告した。', [op('TIME', ['夜', '駅'], 'time')], r8, hole=('に', '税務署'))
    assert d.reason == 'GATE_A_HOLE_WORD_UNPLACED' and [x['gate'] for x in d.gate_log] == ['a4', 'a1']      # a word that fails earlier never reaches (a4)


def test_gate_a4_roles_that_differ_are_a_split_with_its_own_kind():
    class Roles:                            # a hole word whose two types are both read, as two different roles: the reader is replaced by a stub of `_HoleProbe`'s reading
        pass
    p = fake_two_holes()
    ho = S.read_with_holes(SENT2, placement=p)
    import verantyx.semantic_read as SR
    real_arm = SR._hole_arm
    try:
        SR._hole_arm = lambda clause, term, t: ('agent' if t == 'ANIMAL' else 'patient') if term == 'ウサギ' else real_arm(clause, term, t)
        a = F._gate_a4(SENT2, ho, 0, p, {})
    finally:
        SR._hole_arm = real_arm
    assert a['ok'] is False and a['reason'] == 'GATE_A_ROLE_SPLIT' and a['split_kind'] == 'ROLES_DIFFER' and a['role_by_type'] == {'ANIMAL': 'agent', 'PERSON': 'patient'}


def _b_prime_inputs(r8, text='ウサギが図書館へ走った。', hi=0):
    q = S._placement_query(r8)
    ho = S.read_with_holes(text, placement=r8)
    return q, ho, F._gate_a4(text, ho, hi, q, {})


def test_gate_b_prime_passes_when_the_injected_reread_comes_back_to_the_same_cross(r8):
    q, ho, a4 = _b_prime_inputs(r8)
    assert a4['ok'] and F._gate_b_prime('ウサギが図書館へ走った。', ho, 0, 'ANIMAL', a4['role'], q, {}) == (None, None)
    assert F._gate_b_prime('ウサギが図書館へ走った。', ho, 0, 'PERSON', a4['role'], q, {}) == (None, None)


def test_gate_b_prime_refuses_an_arm_with_another_role(r8):
    q, ho, a4 = _b_prime_inputs(r8)
    assert F._gate_b_prime('ウサギが図書館へ走った。', ho, 0, 'ANIMAL', 'patient', q, {}) == ('GATE_B_REREAD_MISMATCH', 'ARM_ROLE_DIFFERS')


def test_gate_b_prime_refuses_a_centre_that_differs_from_the_partial(r8):
    import copy
    q, ho, a4 = _b_prime_inputs(r8)
    other = copy.deepcopy(ho)
    key = next(k for k, v in other['partial'].items() if k not in ('roles', 'role_basis') and isinstance(v, str))
    other['partial'][key] = other['partial'][key] + 'X'
    assert F._gate_b_prime('ウサギが図書館へ走った。', other, 0, 'ANIMAL', a4['role'], q, {}) == ('GATE_B_REREAD_MISMATCH', 'CENTER_DIFFERS')


def test_gate_b_prime_refuses_an_arm_that_is_not_a_hole_and_differs(r8):
    import copy
    q = S._placement_query(r8)
    text = '母がウサギを図書館へ押した。'
    ho = S.read_with_holes(text, placement=r8)             # a non-hole arm (母) beside the hole 図書館
    a4 = F._gate_a4(text, ho, 0, q, {})
    assert ho['holes'][0]['head'] == '図書館' and F._gate_b_prime(text, ho, 0, 'PLACE', 'goal', q, {}) == (None, None)
    other = copy.deepcopy(ho)
    other['partial']['roles']['agent'] = '父'
    assert F._gate_b_prime(text, other, 0, 'PLACE', 'goal', q, {}) == ('GATE_B_REREAD_MISMATCH', 'OTHER_ARMS_DIFFER')
    other = copy.deepcopy(ho)
    other['partial']['role_basis']['agent'] = 'something-else'
    assert F._gate_b_prime(text, other, 0, 'PLACE', 'goal', q, {}) == ('GATE_B_REREAD_MISMATCH', 'OTHER_ARMS_DIFFER')


def test_gate_b_prime_refuses_a_type_the_reader_does_not_read(r8):
    q = S._placement_query(r8)
    ho = S.read_with_holes('隊員が港へ走った。', placement=r8)
    assert ho['holes'][0]['head'] == '隊員' and F._gate_b_prime('隊員が港へ走った。', ho, 0, 'QUANTITY', 'agent', q, {}) == ('GATE_B_REREAD_MISMATCH', 'NOT_READABLE')


def test_every_adoption_passed_b_prime(r8):
    n = 0
    for r in rows():
        if r['expect']['status'] != 'ADOPTED' or r.get('call'):
            continue
        d, _ = decide(r['sentence'], [dict(st) for st in r['steps']], r8, (r['hole']['particle'], r['hole']['head']))
        assert d.status == 'ADOPTED' and sum(1 for x in d.gate_log if x['gate'] == 'passed') == 1
        (passed,) = [x for x in d.gate_log if x['gate'] == 'passed']
        assert passed['b_prime'] == 'PASSED' and passed['a4_role'] and not [x for x in d.gate_log if x['gate'] == 'b_prime']
        n += 1
    assert n >= 20


def test_the_declaration_prompt_asks_for_the_type_of_the_word_not_of_the_position():
    hole = {'particle': 'が', 'head': '手紙', 'expected_types': ['ANIMAL', 'GROUP_ORG', 'PERSON'], 'role_candidates': ['agent']}
    msgs = F.open_messages(hole, {'cross_tokens_version': F.CROSS_TOKENS_VERSION, 'tokens': '<cross></cross>'}, '飛ぶ', None, 5)
    text = '\n'.join(m['content'] for m in msgs)
    assert '上の型から' not in text and '入ってよい型' not in text
    lines = [l for l in text.splitlines() if l.startswith('お願い')]
    type_line = next(l for l in lines if l.startswith('お願い 1'))
    assert '「手紙」そのものの型' in type_line and '合わせず' in type_line
    for t in hole['expected_types']:
        assert t not in type_line and not any(t in l for l in lines if l.startswith(('お願い 1', 'お願い 2')))   # the position's types are not in the type request
    assert any('ANIMAL' in l for l in lines if l.startswith('お願い 3'))                                       # they are the condition of near_words only


def _coords_for(r8, sentence, mask):
    ho = S.read_with_holes(sentence, placement=r8)
    return ho, F.coordinates(ho, sentence, S._placement_query(r8), mask_user_text=mask)


@pytest.mark.parametrize('sentence', ['手紙が駅へ飛んだ。', '夫婦が森へ歩いた。', '兄が山田に催促した。'])
def test_coordinates_do_not_depend_on_the_type_the_probe_tried(r8, sentence):
    import itertools
    ho, c = _coords_for(r8, sentence, True)
    q = S._placement_query(r8)
    (h,) = ho['holes']
    assert c['tokens'] is not None, c
    for t in h['expected_types']:                                               # whichever type the probe tries, the line is the same one
        out = S.read(sentence, 'ja', placement=S._HoleProbe(q, {h['head']: t}, {}))
        if not S._hole_probe_ok(out):
            continue
        reading = F.EC.build_crosses(out, F._QueryLookup(q))
        cross = F._masked_cross(F._scrub_probe(reading.crosses[0], [h['head']]), [h['head']])
        assert F.CT.cross_to_tokens(cross) == c['tokens'], t
    rb = c['tokens'].split('"role_basis"')[1]
    assert '"hole"' in rb                                                       # the hole's arm is marked as a hole, with no type
    for t in h['expected_types']:
        assert '"%s" : "placement_direct:%s"' % (h['arm'], t) not in rb


def test_coordinates_say_so_when_the_cross_depends_on_the_probe_type(r8, monkeypatch):
    ho = S.read_with_holes('手紙が駅へ飛んだ。', placement=r8)
    q = S._placement_query(r8)
    a = S.read('手紙が駅へ飛んだ。', 'ja', placement=S._HoleProbe(q, {'手紙': 'ANIMAL'}, {}))
    b = S.read('母が駅へ飛んだ。', 'ja', placement=q)                                 # a different reading
    monkeypatch.setattr(F, '_probe_readings', lambda *x, **k: [a, b])
    c = F.coordinates(ho, '手紙が駅へ飛んだ。', q)
    assert c['tokens'] is None and c['reason'] == 'COORDINATES_DEPEND_ON_PROBE_TYPE'


def test_gate_c_counts_what_it_really_compared_and_says_when_it_could_not(r8):
    q = S._placement_query(r8)
    ho = S.read_with_holes('母が図書館へ歩いた。', placement=r8)
    rec = SimpleNamespace(crosses={'rec0': G.cross_of('母が駅へ歩かなかった。')[0]})
    assert F._gate_c('母が図書館へ歩いた。', ho, 0, '駅', q, rec) == ('GATE_C_CONTRADICTS_RECORD:rec0', 1, None)
    assert F._gate_c('母が図書館へ歩いた。', ho, 0, 'ほげふが', q, rec) == (None, 0, 'GATE_C_NOT_CHECKED:NOT_READABLE')          # ほげふが is not placed: nothing was compared
    assert F._gate_c('母が図書館へ歩いた。', ho, 0, '駅', q, None) == (None, 0, None)


def test_gate_c_in_a_sentence_with_two_holes_compares_with_the_other_hole_typed_by_the_probe(r8):
    sentence = '客が図書館へ歩いた。'
    q = S._placement_query(r8)
    ho = S.read_with_holes(sentence, placement=r8)
    assert [h['head'] for h in ho['holes']] == ['客', '図書館']
    base = G.cross_of('母が駅へ歩かなかった。')[0]
    rec_c = dict(base, roles={'agent': '客', 'goal': '駅'})                        # a record that has the other hole's word (made by hand: no reader types 客)
    rec_o = dict(base, roles={'agent': '母', 'goal': '駅'})
    assert F._gate_c(sentence, ho, 1, '駅', q, SimpleNamespace(crosses={'r': rec_c})) == ('GATE_C_CONTRADICTS_RECORD:r', 1, None)
    assert F._gate_c(sentence, ho, 1, '駅', q, SimpleNamespace(crosses={'r': rec_o})) == (None, 1, None)                       # compared, nothing contradicts
    assert F._gate_c(sentence, ho, 1, 'ほげふが', q, SimpleNamespace(crosses={'r': rec_c})) == (None, 0, 'GATE_C_NOT_CHECKED:OTHER_HOLES_NOT_READABLE')


def test_the_sovereign_is_not_compared_and_the_decision_says_so(r8):
    d, _ = decide('母が図書館へ歩いた。', [op('PLACE', ['駅']), {'pick': '駅'}, {'pick': '駅'}], r8)
    assert d.sovereign_checked is False and d.to_dict()['sovereign_checked'] is False
