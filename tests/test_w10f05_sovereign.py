"""W10-f05 (J13, docs/FUSION.md section 7): gate (c) also compares a candidate with the SOVEREIGN's utterances when `VERA_SOVEREIGN_*` is set, and `sovereign_checked` says what was really compared.

The sentence and the hole are the ones of W10-f04's gate-(c) test (`ウサギが図書館へ…`, hole `が ウサギ`); the base placement is r9 (read only); the sovereign is a temporary one (`sovereign.create`)."""
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from verantyx import decode_grammar as G
from verantyx import fill_candidates as F
from verantyx import llm_backend as LB
from verantyx import llm_choice as LC
from verantyx import semantic_read as S
from verantyx import sovereign as sov

R9 = '/Users/motonisihikoudai/Projects/vera-impl/wt/W3-a6-S/build/coarse-W3a/full/r9/run2'
SENT, HOLE = 'ウサギが図書館へ走った。', ('が', 'ウサギ')


@pytest.fixture(autouse=True)
def r9(monkeypatch):
    if not Path(R9).exists():
        pytest.skip('ENV_MISSING[coarse placement r9/run2]')
    for k in ('VERA_SOVEREIGN_ROOT', 'VERA_SOVEREIGN_STORE', 'VERA_PLACEMENT_LAYER'):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv('VERA_PLACEMENT', R9)
    return R9


def op(words):
    return {'raw': json.dumps({'type': 'PERSON', 'role': 'agent', 'near_words': words}, ensure_ascii=False)}


def decide(records=None):
    ho = S.read_with_holes(SENT, placement=R9)
    idx = next(i for i, h in enumerate(ho['holes']) if (h['particle'], h['head']) == HOLE)
    fb = LB.FakeBackend([op(['母']), {'pick': '母'}, {'pick': '母'}])
    n = [0]

    def ids():
        n[0] += 1
        return 'id%03d' % n[0]
    return F.ask_and_gate(ho, text=SENT, chat=lambda m, msgs, f: LB.chat('fake', m, msgs, f, fake=fb), model='fake-model', backend_name='fake', hole=idx, placement=R9,
                          choice_ledger=LC.ChoiceLedger(None), records=records, id_source=ids, order_source=lambda m: list(range(m)))


def hand_made(monkeypatch):
    """No reader types 図書館 in a plain sentence (r9): as in W10-f04's gate-(c) test, the sovereign's utterances that name it get a cross made by hand (the reader's real cross of a sentence of the same
    shape, with the arms replaced); every other text is read by the real reader."""
    real = G.cross_of
    made = {'母が図書館へ走らなかった。': '-', '母が図書館へ走った。': '+'}

    def cross_of(text):
        if text in made:
            c = dict(real('母が駅へ走らなかった。')[0], roles={'agent': '母', 'goal': '図書館'})
            c['center'] = tuple((k, made[text] if k == 'polarity' else v) for k, v in c['center'])
            return c, None
        return real(text)
    monkeypatch.setattr(G, 'cross_of', cross_of)


def sovereign(tmp_path, monkeypatch, utterances, consent=True):
    hand_made(monkeypatch)
    root = str(tmp_path / 'sov')
    assert sov.create(root, 'sid', 'tester', consent_promote=consent)['verdict'] == 'CREATED'
    led = sov.open_ledger(root, 'sid')
    for u in utterances:
        led.append({'kind': 'utterance', 'payload': u})
    monkeypatch.setenv('VERA_SOVEREIGN_ROOT', root)
    monkeypatch.setenv('VERA_SOVEREIGN_STORE', 'sid')
    return root


def c_rows(d):
    return [r for r in d.gate_log if 'c_sovereign' in r]


def test_the_premise_a_candidate_passes_with_no_sovereign_and_nothing_is_added():
    d = decide()
    assert d.status == 'ADOPTED' and d.sovereign_checked is False and d.to_dict()['sovereign_checked'] is False
    assert all('c_sovereign' not in r for r in d.gate_log)                                        # not set: not a key more in gate_log


def test_a_candidate_that_contradicts_a_sovereign_utterance_is_dropped(tmp_path, monkeypatch):
    sovereign(tmp_path, monkeypatch, [{'text': '母が図書館へ走らなかった。'}])                       # the same arms as the candidate sentence, the opposite polarity
    d = decide()
    assert d.status == 'NOT_ADOPTED' and d.reason == 'GATE_C_CONTRADICTS_SOVEREIGN:sid:1' and d.sovereign_checked is True
    row = [r for r in d.gate_log if r['gate'] == 'c'][0]
    assert row['reason'] == d.reason and row['c_sovereign'] == {'state': 'ACTIVE_CONSENTED', 'compared': 1, 'note': None}
    assert d.records_checked == 0                                                                  # the documents' records are a separate count


def test_a_sovereign_that_agrees_or_says_something_else_lets_it_pass_and_is_counted(tmp_path, monkeypatch):
    sovereign(tmp_path, monkeypatch, [{'text': '母が図書館へ走った。'}, {'phrase': '兄が駅へ走らなかった。'}])
    d = decide()
    assert d.status == 'ADOPTED' and d.sovereign_checked is True
    assert c_rows(d)[0]['c_sovereign'] == {'state': 'ACTIVE_CONSENTED', 'compared': 2, 'note': None}   # `payload.text` and `payload.phrase` are both read


def test_without_consent_the_sovereign_is_not_compared_and_the_state_is_said(tmp_path, monkeypatch):
    sovereign(tmp_path, monkeypatch, [{'text': '母が図書館へ走らなかった。'}], consent=False)
    d = decide()
    assert d.status == 'ADOPTED' and d.sovereign_checked is False
    assert c_rows(d)[0]['c_sovereign'] == {'state': 'ACTIVE_NO_CONSENT', 'compared': 0, 'note': 'SOVEREIGN_NOT_COMPARED:ACTIVE_NO_CONSENT'}


def test_nothing_comparable_means_not_checked(tmp_path, monkeypatch):
    sovereign(tmp_path, monkeypatch, [{'text': '今日はいい天気です。'}, {'other': 1}])                  # an utterance the reader cannot read as one clause, and one with no text
    d = decide()
    assert d.status == 'ADOPTED' and d.sovereign_checked is False and c_rows(d)[0]['c_sovereign']['compared'] == 0
    monkeypatch.delenv('VERA_SOVEREIGN_STORE')                                                     # an incomplete configuration is typed, not guessed
    d = decide()
    assert d.status == 'ADOPTED' and d.sovereign_checked is False and c_rows(d)[0]['c_sovereign']['state'] == 'UNKNOWN_SOVEREIGN_CONFIG_INCOMPLETE'


def test_a_record_that_contradicts_is_still_reported_as_a_record_first(tmp_path, monkeypatch):
    sovereign(tmp_path, monkeypatch, [{'text': '母が図書館へ走らなかった。'}])
    rec = SimpleNamespace(crosses={'rec0': dict(G.cross_of('母が駅へ走らなかった。')[0], roles={'agent': '母', 'goal': '図書館'})})
    d = decide(records=rec)
    assert d.reason == 'GATE_C_CONTRADICTS_RECORD:rec0' and d.records_checked == 1 and d.sovereign_checked is False   # the documents' gate stopped it before the sovereign was asked
    assert c_rows(d) == []


def test_the_gate_c_function_keeps_its_three_part_return():
    ho = S.read_with_holes(SENT, placement=R9)
    idx = next(i for i, h in enumerate(ho['holes']) if (h['particle'], h['head']) == HOLE)
    out = F._gate_c(SENT, ho, idx, '母', S._placement_query(R9), SimpleNamespace(crosses={}), {})
    assert out == (None, 0, None)
