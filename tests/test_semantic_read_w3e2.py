"""W3-e2 (docs/READING_SOUNDNESS.md section 10L): stage E2, the assumed reading. The frozen data is tests/reading_soundness/w3e2_p{1,2,3}.jsonl (frozen before the stage existed)."""
import json
import os
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
DATA = ROOT / 'tests' / 'reading_soundness'
R8 = '/Users/motonisihikoudai/Projects/vera-impl/build/coarse-W3a/full/r8/run2'
R9 = '/Users/motonisihikoudai/Projects/vera-impl/wt/W3-a6-S/build/coarse-W3a/full/r9/run2'
PLACEMENTS = {'none': None, 'r8': R8, 'r9': R9}
STANDINS = ('田中', '国連', '京都', '犬')
needs_placement = pytest.mark.skipif(not (os.path.isdir(R8) and os.path.isdir(R9)), reason='the placements r8 / r9 are not here')


def load_rows():
    rows = []
    for name in ('w3e2_p1.jsonl', 'w3e2_p2.jsonl', 'w3e2_p3.jsonl'):
        rows += [json.loads(l) for l in (DATA / name).read_text(encoding='utf-8').splitlines() if l.strip()]
    return rows


class FakeLayer:
    def __init__(self, rows):
        self.rows = rows or []

    def entries(self, word):
        return [{'word': r['word'], 'type': r['type'], 'origin': r['origin']} for r in self.rows if r['word'] == word]


class FakeLedger:
    def __init__(self, rows):
        self.rows = rows or []

    def fold(self):
        return {str(i): dict(r, fill_ids=['f%d' % i]) for i, r in enumerate(self.rows)}


def fake_chat(spec):
    """A scripted back end: spec {'answers': [type, type]} (the type's number in the list, or one outside the list) or {'error': ...}. Records the messages it was sent."""
    state = {'i': 0, 'sent': []}

    def chat(model, messages, fmt):
        state['sent'].append(messages)
        if 'error' in spec:
            return {'ok': False, 'content': None, 'error': {'type': spec['error'], 'detail': 'scripted'}}
        cands = [m.group(2) for m in (re.match(r'^(\d+): (\S+)$', ln) for ln in messages[-1]['content'].splitlines()) if m]
        t = spec['answers'][state['i'] % len(spec['answers'])]
        state['i'] += 1
        return {'ok': True, 'content': json.dumps({'choice': cands.index(t) if t in cands else len(cands)}), 'error': None, 'usage': {}}
    chat.state = state
    return chat


def config_of(row):
    from verantyx import semantic_read as SR
    s = row['sources']
    llm = s.get('llm')
    chat = fake_chat(llm) if isinstance(llm, dict) else None
    return SR.AssumeConfig(layer=FakeLayer(s['layer_rows']) if s.get('layer_rows') else None, ledger=FakeLedger(s['ledger_rows']) if s.get('ledger_rows') else None,
                           documents=s.get('documents') or (), chat=chat, model='fake-model' if chat else None), chat


def run_row(row):
    from verantyx import semantic_read as SR, constructions
    constructions.discover()
    cfg, chat = config_of(row)
    pl = PLACEMENTS[row['placement']]
    from verantyx import semantic_reader as R
    q = None if pl is None else R.CoarseQuery(pl)
    return SR.read_in_mode(row['input'], 'ja', placement=q, mode='assume', assume=cfg), chat


CLAUSE_KEYS = ('predicate', 'roles', 'polarity', 'tense', 'modality', 'voice')


def judge(row, out):
    """-> (ok, why). The expectation was typed before the stage existed."""
    e = row['expect']
    if e['mode'] == 'assumed':
        if out.get('read_mode') != 'assumed':
            return False, 'not assumed: %s' % ((out.get('abstain') or {}).get('reasons'),)
        got = [{k: a[k] for k in ('word', 'kind', 'assumed', 'source')} for a in out['assumptions']]
        if got != e['assumptions']:
            return False, 'assumption %s != %s' % (got, e['assumptions'])
        cl = [{k: c[k] for k in CLAUSE_KEYS} for c in out['clauses']]
        if cl != e['clauses']:
            return False, 'clauses %s != %s' % (cl, e['clauses'])
        return True, ''
    if out.get('read_mode') != 'strict' or out.get('readable'):
        return False, 'read although the expectation is an abstention'
    reasons = (out.get('abstain') or {}).get('reasons') or []
    if not reasons or reasons[0] != e['abstain_reason']:
        return False, 'first reason %s != %s' % (reasons[:1], e['abstain_reason'])
    added = [r for r in reasons if r.startswith(('ASSUMPTION_UNDETERMINED', 'ASSUMPTION_BACKEND_FAILED'))]
    if e['added_reason'] is None:
        return (not added), 'a reason was added: %s' % added
    return (added == [e['added_reason']]), 'added %s != %s' % (added, e['added_reason'])


ROWS = load_rows()


def test_the_frozen_data_has_the_registered_shape():
    assert len(ROWS) >= 75
    for p in ('P1', 'P2', 'P3'):
        rs = [r for r in ROWS if r['premise'] == p]
        assert len(rs) >= 25
        a = sum(1 for r in rs if r['expect']['mode'] == 'assumed')
        assert a >= 12 and len(rs) - a >= 12                      # about half and half


# r1 review 4 / round 3 ruling 1: the three frozen rows that v2 expected to read through the DOCUMENTS (P1-014, P3-012, P3-013). Their documents are plain sentences with no `XなどのY` form, so
# W10-f05's distribution holds no row for the word (and with no placement the documents cannot be read at all): the auditor ruled the v2 expectation a data error. Their expectation is now an
# abstention (ASSUMPTION_UNDETERMINED) in the v3 data (see the change record in docs section 10L.6) and they are judged like every other row.
FROZEN_DOCUMENT_ROWS = ('W3E2-P1-014', 'W3E2-P3-012', 'W3E2-P3-013')
POSTHOC = [json.loads(l) for l in (DATA / 'w3e2_c_posthoc.jsonl').read_text(encoding='utf-8').splitlines() if l.strip()]


def check_row(row):
    out, _chat = run_row(row)
    ok, why = judge(row, out)
    assert ok, (row['input'], why)
    flat = json.dumps(out, ensure_ascii=False)
    for s in STANDINS:
        if s not in row['input']:
            assert s not in flat, ('a stand-in leaked into the output', s)


@needs_placement
@pytest.mark.parametrize('row', ROWS, ids=[r['id'] for r in ROWS])
def test_frozen_row(row):
    check_row(row)


def test_the_frozen_document_rows_are_among_the_rows_with_documents():
    assert set(FROZEN_DOCUMENT_ROWS) <= {r['id'] for r in ROWS if r['sources'].get('documents')}


@needs_placement
@pytest.mark.parametrize('rid', FROZEN_DOCUMENT_ROWS)
def test_the_frozen_document_rows_have_no_document_row_for_the_word(rid):
    # with no placement (P1-014) the base's types are missing, so the documents cannot be read at all (None); with r9 they are read and hold no row for the word ([])
    from verantyx import semantic_read as SR
    row = next(r for r in ROWS if r['id'] == rid)
    cfg, _ = config_of(row)
    word = row['expect']['added_reason'].split(':')[1]      # v3: these rows expect an abstention, the word is in the added reason
    assert SR._w3e2_document_rows(word, cfg, PLACEMENTS[row['placement']]) == (None if row['placement'] == 'none' else [])


@needs_placement
def test_the_documents_result_of_a_frozen_row_is_the_registered_one():
    # the registered (c) result of every frozen row that has one (auditor rulings 1 and 4): judge() only sees the abstention reasons, so this pins the documents entry of the trace itself
    from verantyx import semantic_read as SR
    rows = [r for r in ROWS if 'documents_result' in r['expect']]
    assert len(rows) == 10, [r['id'] for r in rows]
    for row in rows:
        cfg, _ = config_of(row)
        srcs = SR.assumption_explain_ja(row['input'], PLACEMENTS[row['placement']], cfg)['trace']['sources']
        docs = [x for x in srcs if x.get('source') == 'documents']
        assert len(docs) == 1, (row['id'], srcs)
        assert docs[0].get('result', 'TYPES') == row['expect']['documents_result'], (row['id'], docs[0])


@needs_placement
@pytest.mark.parametrize('row', POSTHOC, ids=[r['id'] for r in POSTHOC])
def test_posthoc_document_rows(row):
    check_row(row)


@needs_placement
def test_the_document_rows_are_those_grow_writes(tmp_path, capsys):
    """r1 review 4: for the bicycle documents of W10-f05 the rows of the thin function are the `doc_rows` that `placement_grow.grow()` wrote to the ledger (same rows, same source)."""
    from verantyx import cli, semantic_read as SR
    doc = str(ROOT / 'tests' / 'fusion' / 'w10f05' / 'domain_bicycle.txt')
    table = str(ROOT / 'tests' / 'fusion' / 'w10f05' / 'fake_declarations_bicycle.json')
    ledger = tmp_path / 'ledger.jsonl'
    code = cli.main(['placement', 'grow', '--documents', doc, '--layer', str(tmp_path / 'bike.sqlite'), '--backend', 'fake', '--fake-table', table, '--ledger-file', str(ledger), '--placement', R9])
    capsys.readouterr()
    assert code == 0
    written = {}
    for line in ledger.read_text(encoding='utf-8').splitlines():
        r = json.loads(line)
        rows = (r.get('evidence') or {}).get('doc_rows')
        if rows:
            written[r['word']] = [tuple(x) for x in rows]
    assert len(written) >= 2
    cfg = SR.AssumeConfig(documents=[doc])
    for word, rows in written.items():
        assert SR._w3e2_document_rows(word, cfg, R9) == rows, word
    assert SR._w3e2_document_types('ディレイラー', cfg, R9) == ('TYPES', ['ARTIFACT'])


@needs_placement
def test_strict_mode_is_the_same_object_as_read():
    from verantyx import semantic_read as SR
    a = SR.read_in_mode('ハルはミナに本を渡した。', 'ja', placement=None)
    assert a['abstain']['reasons'] == ['RECIPIENT_TYPE_UNDETERMINED:ミナ'] and 'read_mode' not in a
    with pytest.raises(SR.ReadError):
        SR.read_in_mode('ハルは本を読んだ。', 'ja', mode='loose')
    import unittest.mock as m
    sentinel = {'readable': True}
    with m.patch.object(SR, 'read', return_value=sentinel):
        assert SR.read_in_mode('x', placement=None, mode='strict') is sentinel


@needs_placement
def test_assume_mode_adds_only_a_last_key_when_nothing_is_assumed():
    from verantyx import semantic_read as SR
    base = SR.read('母が部屋で本を読んだ。', placement=None)
    got = SR.read_in_mode('母が部屋で本を読んだ。', placement=None, mode='assume')
    assert list(got)[-1] == 'read_mode' and got['read_mode'] == 'strict'
    assert {k: v for k, v in got.items() if k != 'read_mode'} == base
    assert list(got)[:-1] == list(base)


@needs_placement
def test_output_keys_of_an_assumed_reading_in_order():
    from verantyx import semantic_read as SR
    cfg = SR.AssumeConfig(layer=FakeLayer([{'word': 'ミナ', 'type': 'PERSON', 'origin': 'layer_human'}]))
    out = SR.read_in_mode('ハルはミナに本を渡した。', placement=None, mode='assume', assume=cfg)
    keys = list(out)
    assert keys[-4:] == ['read_mode', 'assumptions', 'strict', 'assumption_note']
    assert out['readable'] is True and out['abstain'] is None
    assert out['assumption_note'] == '（ミナを人として）'
    assert out['strict'] == {'readable': False, 'abstain': {'kind': 'not_supported', 'reasons': ['RECIPIENT_TYPE_UNDETERMINED:ミナ']}}
    assert out['clauses'][0]['role_basis']['recipient'] == 'assumed:PERSON'
    assert set(out['assumptions'][0]) == {'word', 'kind', 'assumed', 'alternatives', 'source', 'ledger_id'}
    assert out['assumptions'][0]['alternatives'] == ['GROUP_ORG', 'PLACE']


@needs_placement
def test_p2_reads_only_the_default_of_the_particles_and_gives_no_type():
    from verantyx import semantic_read as SR
    out = SR.read_in_mode('ハルは本をザクった。', placement=None, mode='assume')
    c = out['clauses'][0]
    assert c['predicate_basis'] == 'assumed:nonce_predicate' and c['role_basis'] == {'agent': 'particle_default:は', 'patient': 'particle_default:を'}
    assert out['assumptions'][0]['assumed'] == 'UNTYPED_VERB' and out['assumption_note'] == '（ザクを動詞として）'
    assert 'predicate_type' not in c


@needs_placement
def test_spans_point_into_the_original_sentence():
    from verantyx import semantic_read as SR
    cfg = SR.AssumeConfig(layer=FakeLayer([{'word': 'フレーム', 'type': 'ANIMAL', 'origin': 'layer_estimated'}]))
    from verantyx import semantic_reader as R
    text = 'フレームが走った。'                              # the stand-in (犬, one character) is shorter than the word (four)
    out = SR.read_in_mode(text, placement=R.CoarseQuery(R9), mode='assume', assume=cfg)
    assert out['read_mode'] == 'assumed'
    for m in out['clause_meta']:
        s, e = m['span']
        assert 0 <= s < e <= len(text) and text[s:e] in ('走', '走っ', '走った')
    assert '犬' not in json.dumps(out, ensure_ascii=False)


@needs_placement
def test_a_lower_source_does_not_override_a_conflict_of_a_higher_one():
    from verantyx import semantic_read as SR
    from verantyx import semantic_reader as R
    cfg = SR.AssumeConfig(layer=FakeLayer([{'word': 'ミナ', 'type': 'PERSON', 'origin': 'layer_human'}, {'word': 'ミナ', 'type': 'GROUP_ORG', 'origin': 'layer_human'}]),
                          chat=fake_chat({'answers': ['PERSON', 'PERSON']}), model='fake-model')
    out = SR.read_in_mode('ハルはミナに本を渡した。', placement=None, mode='assume', assume=cfg)
    assert out['read_mode'] == 'strict' and out['abstain']['reasons'][-1] == 'ASSUMPTION_UNDETERMINED:ミナ:に'
    assert cfg.chat.state['sent'] == []                          # the LLM was not even asked


@needs_placement
def test_the_masked_message_does_not_hold_the_sentence():
    from verantyx import semantic_read as SR
    chat = fake_chat({'answers': ['PERSON', 'PERSON']})
    cfg = SR.AssumeConfig(chat=chat, model='fake-model')
    text = 'ハルはミナに本を渡した。'
    out = SR.read_in_mode(text, placement=None, mode='assume', assume=cfg)
    assert out['assumptions'][0]['source'] == 'llm:fake-model'
    assert len(chat.state['sent']) == 2
    for msgs in chat.state['sent']:
        blob = json.dumps(msgs, ensure_ascii=False)
        assert text not in blob and '本' not in blob and 'ハル' not in blob and 'ミナ' in blob
        assert '述語: 渡す' in blob                     # r1 review 3: the predicate's lemma is sent, nothing else of the sentence


@needs_placement
def test_two_answers_that_split_or_leave_the_list_decide_nothing():
    from verantyx import semantic_read as SR
    for answers in (['PERSON', 'GROUP_ORG'], ['PLACE', 'PLACE'], [None, None]):
        cfg = SR.AssumeConfig(chat=fake_chat({'answers': answers}), model='fake-model')
        out = SR.read_in_mode('ハルはミナに本を渡した。', placement=None, mode='assume', assume=cfg)
        assert out['read_mode'] == 'strict' and out['abstain']['reasons'][-1] == 'ASSUMPTION_UNDETERMINED:ミナ:に', answers


@needs_placement
def test_surface_is_not_used_for_a_particle_whose_role_splits_nor_for_p3():
    from verantyx import semantic_read as SR
    from verantyx import semantic_reader as R
    q = R.CoarseQuery(R9)
    a = SR.assumption_explain_ja('ハルはミナに本を渡した。', placement=q)
    assert a['status'] == 'UNDETERMINED' and not [s for s in a['trace']['sources'] if s['source'] == 'surface']
    b = SR.assumption_explain_ja('フレームが走った。', placement=q)
    assert b['status'] == 'UNDETERMINED' and not [s for s in b['trace']['sources'] if s['source'] == 'surface']
    c = SR.assumption_explain_ja('ナナが走った。', placement=None)
    assert c['status'] == 'ASSUMED' and c['trace']['sources'][-1]['source'] == 'surface'


@needs_placement
def test_the_reasons_of_the_stage_are_a_closed_list_and_the_stage_is_after_read():
    from verantyx import semantic_read as SR
    assert SR.W3E2_REASONS == ('ASSUMPTION_UNDETERMINED', 'ASSUMPTION_BACKEND_FAILED')
    for r in ROWS:
        e = r['expect']['added_reason']
        assert e is None or e.split(':')[0] in SR.W3E2_REASONS


@needs_placement
def test_the_hole_path_reads_an_unplaced_noun_through_the_probe_of_the_placement():
    """D7: `兄が土間で歩いた。` at r8: 土間 is UNPLACED, the reader stops on the で (a typed hole, PLACE only); a layer that says PLACE lets stage E2 read it with the reader's own probe."""
    from verantyx import semantic_read as SR, semantic_reader as R
    q = R.CoarseQuery(R8)
    text = '兄が土間で歩いた。'
    assert SR.read(text, placement=q)['abstain']['reasons'] == ['NO_SUPPORTED_CLAUSE']
    cfg = SR.AssumeConfig(layer=FakeLayer([{'word': '土間', 'type': 'PLACE', 'origin': 'layer_human'}]))
    out = SR.read_in_mode(text, placement=q, mode='assume', assume=cfg)
    assert out['read_mode'] == 'assumed' and out['assumptions'][0]['kind'] == 'noun_type' and out['assumptions'][0]['assumed'] == 'PLACE'
    c = out['clauses'][0]
    assert c['roles']['place'] == '土間' and c['role_basis']['place'] == 'assumed:PLACE'
    # no source: a typed refusal at the end
    out = SR.read_in_mode(text, placement=q, mode='assume')
    assert out['read_mode'] == 'strict' and out['abstain']['reasons'][-1] == 'ASSUMPTION_UNDETERMINED:土間:で'


# ---- r1 review (round 2) ---------------------------------------------------------------------------------------------------------------
@needs_placement
def test_a_word_the_base_types_by_an_estimate_gets_no_premise():
    """r1 review 1 (D9): r9 has ミカン as an ESTIMATE (SUBSTANCE_FOOD, kana variant): a type the reader cannot use. No P1 / P3 is assumed on top of it: the strict abstention stays."""
    from verantyx import semantic_read as SR, semantic_reader as R, constructions
    constructions.discover()
    q = R.CoarseQuery(R9)
    out = SR.read_in_mode('ミカンが腐った。', 'ja', placement=q, mode='assume')
    assert out['read_mode'] == 'strict' and not out.get('readable')
    assert out['abstain']['reasons'] == ['SUBJECT_TYPE_UNDETERMINED:ミカン']              # no ASSUMPTION_* reason: the stage did not apply
    assert SR.assumption_explain_ja('ミカンが腐った。', q)['why'] == 'BASE_HAS_UNUSABLE_TYPE'


@needs_placement
def test_p2_reads_wa_as_an_agent_only_beside_wo():
    """r1 review 2 (K336): は alone is a topic: strict abstains the same form of a known verb, so P2 does not read it. が and は beside を are read as before."""
    from verantyx import semantic_read as SR
    for t in ('本はザクった。', 'ハルはザクった。'):
        o = SR.read_in_mode(t, 'ja', placement=None, mode='assume')
        assert o['read_mode'] == 'strict' and not o.get('readable'), t
        assert SR.assumption_explain_ja(t, None)['why'] == 'P2_FORM_NOT_READ', t
    assert SR.read('本は読んだ。', placement=None)['abstain']['reasons'] == ['NO_SUPPORTED_CLAUSE']       # the strict form of a known verb
    o = SR.read_in_mode('ハルは本をザクった。', 'ja', placement=None, mode='assume')
    assert o['read_mode'] == 'assumed' and o['clauses'][0]['roles'] == {'agent': 'ハル', 'patient': '本'}
    # round 3 ruling 5: a が phrase is an agent only when its filler is typed (animate) by the base or a layer; ナナ is PERSON at r9, untyped with no placement
    from verantyx import semantic_reader as R
    o = SR.read_in_mode('ナナがザクった。', 'ja', placement=R.CoarseQuery(R9), mode='assume')
    assert o['read_mode'] == 'assumed' and o['clauses'][0]['roles'] == {'agent': 'ナナ'}
    o = SR.read_in_mode('ナナがザクった。', 'ja', placement=None, mode='assume')
    assert o['read_mode'] == 'strict' and o['abstain']['reasons'] == ['NO_PREDICATE_TOKEN']
    assert SR.assumption_explain_ja('ナナがザクった。', None)['why'] == 'P2_GA_FILLER_NOT_TYPED' 


@needs_placement
def test_the_note_names_every_type_that_was_assumed():
    """r1 review 6: a joined assumption (the types the surface cannot tell apart) is said as `A または B`, never as "no type"."""
    from verantyx import semantic_read as SR
    o = SR.read_in_mode('ミナが走った。', 'ja', placement=None, mode='assume')      # round 3: ソラ is a weak name form (lemma 空), ミナ a strong one (the frozen P1-029)
    assert o['assumptions'][0]['assumed'] == 'GROUP_ORG+PERSON'
    assert o['assumption_note'] == '（ミナを集団・組織または人として）'
    assert '決めずに' not in o['assumption_note']
    assert SR.assumption_note_ja([{'word': 'ミナ', 'kind': 'name_type', 'assumed': 'PERSON'}]) == '（ミナを人として）'


# --- round 3 (auditor rulings 2-5) ---------------------------------------------------------------------------------------------------------
def _tok(text, word):
    from verantyx import semantic_read as SR
    return next(t for t in SR._w3e2_tokens(text) if t[0] == word)


def test_r3_the_name_form_strength_is_from_the_tagger_only():
    from verantyx import semantic_read as SR
    for w in ('ミナ', 'ナナ', 'ヨモ'):
        assert SR._w3e2_name_form_strong(_tok('%sが来た。' % w, w)), w
    for w in ('リンゴ', 'リク', 'ソラ'):
        t = _tok('%sが来た。' % w, w)
        assert SR._w3e2_name_form(t), w      # a weak form stays a P1 candidate (it is only barred from the surface source (d))
        assert not SR._w3e2_name_form_strong(t), w
    assert SR._w3e2_hira('ミナー') == 'みなー'


@needs_placement
def test_r3_weak_name_form_is_not_assumed_by_the_surface():
    from verantyx import semantic_read as SR
    r = SR.assumption_explain_ja('リンゴが落ちた。', None)
    assert r['status'] == 'UNDETERMINED'
    assert {'source': 'surface', 'result': 'WEAK_NAME_FORM'} in r['trace']['sources']
    for t in ('ミナが走った。', 'ナナが走った。'):
        r = SR.assumption_explain_ja(t, None)
        assert r['status'] == 'ASSUMED' and r['assumptions'][0]['source'] == 'surface', t


@needs_placement
def test_r3_base_outside_p1_types_is_not_assumed_by_the_surface_and_the_llm_is_asked_among_the_base():
    from verantyx import semantic_read as SR, semantic_reader as R
    q = R.CoarseQuery(R9)
    r = SR.assumption_explain_ja('モモが落ちた。', q)
    assert r['status'] == 'UNDETERMINED'
    assert {'source': 'surface', 'result': 'BASE_OUTSIDE_P1_TYPES'} in r['trace']['sources']
    chat = fake_chat({'answers': ['PERSON', 'PERSON']})
    cfg = SR.AssumeConfig(chat=chat, model='fake-model')
    r = SR.assumption_explain_ja('モモが落ちた。', q, cfg)
    assert r['status'] == 'ASSUMED' and r['assumptions'][0]['source'] == 'llm:fake-model' and r['assumptions'][0]['alternatives'] == ['ANIMAL']
    lines = [l for l in chat.state['sent'][0][-1]['content'].splitlines() if re.match(r'^\d+: ', l)]
    assert lines == ['0: ANIMAL', '1: PERSON']
    r = SR.assumption_explain_ja('モモが落ちた。', q, SR.AssumeConfig(chat=fake_chat({'answers': ['ANIMAL', 'ANIMAL']}), model='fake-model'))
    assert r['status'] == 'UNDETERMINED' and r['trace']['sources'][-1]['result'] == 'TYPE_NOT_READABLE'


@needs_placement
def test_r3_a_weak_document_row_of_another_type_stops_the_search():
    from verantyx import semantic_read as SR, semantic_reader as R
    q = R.CoarseQuery(R9)
    r = SR.assumption_explain_ja('ヨモが走った。', q, SR.AssumeConfig(documents=['ヨモやサキなどの都市がある。']))
    assert r['status'] == 'UNDETERMINED'
    assert {'source': 'documents', 'result': 'NOT_DECISIVE_COUNTER', 'types': ['PLACE']} in r['trace']['sources']
    assert not any(s['source'] == 'surface' for s in r['trace']['sources'])
    for docs in (['ヨモやサキなどの人がいる。'], []):
        r = SR.assumption_explain_ja('ヨモが走った。', q, SR.AssumeConfig(documents=docs))
        assert r['status'] == 'ASSUMED' and r['assumptions'][0]['assumed'] == 'GROUP_ORG+PERSON' and r['assumptions'][0]['source'] == 'surface', docs


@needs_placement
def test_r3_p2_ga_needs_an_animate_type():
    from verantyx import semantic_read as SR, semantic_reader as R
    for t in ('本がザクった。', 'ハルがザクった。'):
        o = SR.read_in_mode(t, 'ja', placement=None, mode='assume')
        assert o['read_mode'] == 'strict' and o['abstain']['reasons'] == ['NO_PREDICATE_TOKEN'], t
        assert SR.assumption_explain_ja(t, None)['why'] == 'P2_GA_FILLER_NOT_TYPED', t
    q = R.CoarseQuery(R9)
    for t in ('ハルがザクった。', '先生がザクった。', '犬がザクった。'):
        assert SR.read_in_mode(t, 'ja', placement=q, mode='assume')['read_mode'] == 'assumed', t
    for t in ('本がザクった。', '机がザクった。'):
        assert SR.read_in_mode(t, 'ja', placement=q, mode='assume')['read_mode'] == 'strict', t
    o = SR.read_in_mode('ハルがザクった。', 'ja', placement=None, mode='assume', assume=SR.AssumeConfig(layer=FakeLayer([{'word': 'ハル', 'type': 'PERSON', 'origin': 'layer_human'}])))
    assert o['read_mode'] == 'assumed'
    assert SR.read_in_mode('ハルは本をザクった。', 'ja', placement=None, mode='assume')['read_mode'] == 'assumed'
