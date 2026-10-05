"""W10-f05 (K291-K296, docs/COARSE_PLACEMENT.md section 12.19): `placement_grow.grow` with the fake back end only. The frozen data are in tests/fusion/w10f05/ (checked in before the code;
`artifacts/w10-f05/data_freeze.sha256`); the base placement is r9 (read only)."""
import copy
import hashlib
import json
import shutil
from pathlib import Path

import pytest

from verantyx import cli
from verantyx import coarse_place as CP
from verantyx import coarse_types as ct
from verantyx import placement_grow as G
from verantyx import placement_layer as PL
from verantyx import semantic_reader as R
from verantyx.testimony_ledger import TestimonyLedger

R9 = '/Users/motonisihikoudai/Projects/vera-impl/wt/W3-a6-S/build/coarse-W3a/full/r9/run2'
DATA = Path(__file__).parent / 'fusion' / 'w10f05'
SYN = DATA / 'synthetic'
HEARST_DOC = SYN / 'hearst_doc.txt'
CFG = dict(ct.DEFAULT_CONFIG, rd_min_total=20, rd_store_min=20, rd_particle_min=10, rd_particle_share_pct=30, rd_type_share_pct=50, rd_min_sources=1, role_frame_min_sources=1,
           frame_cover_rule='k62_he_by_ni_place')


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    for k in (PL.ENV_LAYER, PL.ENV_ROOT, 'VERA_PLACEMENT', 'VERA_SOVEREIGN_ROOT', 'VERA_SOVEREIGN_STORE'):
        monkeypatch.delenv(k, raising=False)


@pytest.fixture
def r9():
    if not Path(R9).exists():
        pytest.skip('ENV_MISSING[coarse placement r9/run2]')
    return R9


def noun(t, hyp=None):
    return {'type': t, 'definition': None if t is None else 'x', 'hypernym': hyp}


def run(tmp_path, r9, table, docs=(HEARST_DOC,), layer='dom', **kw):
    be = G.TableBackend(table)
    out = G.grow([str(d) for d in docs], str(tmp_path / (layer + '.sqlite')), backend='fake', model='fake-model', ledger_path=str(tmp_path / 'ledger.jsonl'), placement=r9, chat=be,
                 **kw)
    return out, be


def layer_rows(tmp_path, layer='dom'):
    lay = PL.open_layer(str(tmp_path / (layer + '.sqlite')))[0]
    return {} if lay is None else {e['word']: e for e in lay.all_entries()}


TABLE = {'ポルミナ': noun('ARTIFACT'), 'ヘクタス': noun('ARTIFACT'), '午前': noun('TIME')}


# ---------------------------------------------------------------------------------------------------------------- the three ways to direct, and what is never direct
def test_the_three_ways_a_word_gets_into_the_layer_k291(r9, tmp_path, capsys, monkeypatch):
    out, _ = run(tmp_path, r9, TABLE)
    assert out['verdict'] == 'GREW' and out['written'] == {'layer_confirmed': 2, 'layer_estimated': 1, 'layer_human': 0}, out
    rows = layer_rows(tmp_path)
    assert rows['ポルミナ']['origin'] == 'layer_confirmed' and rows['ポルミナ']['decided_by'][0].startswith('hearst@doc:') and rows['午前']['origin'] == 'layer_estimated'
    layer = str(tmp_path / 'dom.sqlite')
    # (a) generated x documents agree -> direct, and the reader may use it
    a = CP.query('ポルミナ', placement=r9, layer=layer)
    assert (a['layer_status'], a['top']) == ('LAYER_DIRECT_USED', ['ARTIFACT']) and R.placement_type(a) == ('ARTIFACT', None) and R._placement_answer_problems(a) == []
    # the model alone -> an estimate: shown in the layer and the ledger, never in the answer
    base = CP.query('午前', placement=r9)
    e = CP.query('午前', placement=r9, layer=layer)
    assert e['layer_status'] == 'LAYER_ESTIMATED_NOT_USED' and e['state'] == base['state'] and e['top'] == base['top'] and R.placement_type(e) == R.placement_type(base)
    # (b) a human confirms through the ledger -> promote -> layer_human (direct)
    led = TestimonyLedger(tmp_path / 'ledger.jsonl')
    fid = [x for x in led.entries() if x['type'] == 'testimony' and x['word'] == '午前'][0]['fill_id']
    monkeypatch.setenv('VERA_PLACEMENT', r9)
    assert cli.main(['ledger', 'confirm', fid, '--ledger-file', str(tmp_path / 'ledger.jsonl')]) == 0
    capsys.readouterr()
    assert cli.main(['ledger', 'promote', '--ledger-file', str(tmp_path / 'ledger.jsonl'), '--layer', layer]) == 0
    promoted = json.loads(capsys.readouterr().out)
    assert promoted['written']['layer_human'] == 1
    h = CP.query('午前', placement=r9, layer=layer)
    assert (h['layer_status'], h['top'], h['decided_by']) == ('LAYER_DIRECT_USED', ['TIME'], ['layer_human']) and R.placement_type(h) == ('TIME', None)


def test_a_declaration_alone_never_makes_a_word_direct(r9, tmp_path):
    out, _ = run(tmp_path, r9, {'午前': noun('TIME'), 'ポルミナ': noun('ARTIFACT'), 'ヘクタス': noun('PLACE')}, docs=[])
    assert out['documents']['read'] == 0
    out, _ = run(tmp_path, r9, {'午前': noun('TIME')}, docs=[HEARST_DOC], layer='alone')
    # with the documents' hearst arm for ポルミナ / ヘクタス but no declaration for them, nothing about them is written; 午前 has no document arm: estimate only
    rows = layer_rows(tmp_path, 'alone')
    assert [(w, e['origin']) for w, e in rows.items()] == [('午前', 'layer_estimated')]
    assert all(e['origin'] != 'layer_confirmed' for e in rows.values())


def test_a_declaration_that_the_documents_contradict_is_not_written(r9, tmp_path):
    out, _ = run(tmp_path, r9, {'ポルミナ': noun('PLANT'), 'ヘクタス': noun('ARTIFACT')})
    assert out['not_written'].get('GEN_DISAGREES_WITH_DOCUMENTS') == 1 and set(layer_rows(tmp_path)) == {'ヘクタス'}
    led = TestimonyLedger(tmp_path / 'ledger.jsonl')
    assert any(e['type'] == 'testimony' and e['word'] == 'ポルミナ' for e in led.entries())     # the testimony itself stays on the record (K294)


def test_a_predicate_with_a_matching_distribution_is_direct_and_a_contradicted_one_is_not_written():
    """The synthetic evidence rows (frozen): decide_word on the declaration laid over the documents' rows."""
    cases = [json.loads(line) for line in (SYN / 'evidence_cases.jsonl').read_text(encoding='utf-8').splitlines() if line.strip()]
    assert len(cases) == 10
    for c in cases:
        decl = dict(c['declaration'], kind=c['kind'], type=c['declaration'].get('type') or c['declaration'].get('ptype'))
        res = G.decide_candidate(c['word'], decl, [tuple(r) for r in c['rows']], CFG, model='m', hypernym_base_type=c.get('hypernym_base_type'))
        assert (res['write'], res['reason']) == (c['expect']['write'], c['expect']['reason']), c['case']
        if res['write'] == 'layer_confirmed':
            assert (G.ct.GEN_ARM in res['dec']['by'] or G.ct.GEN_FRAME_ARM in res['dec']['by']) or res['dec']['by'][0].startswith('hearst@')


def test_min_sources_is_a_setting_and_the_thresholds_are_not_lowered():
    cases = {json.loads(l)['case']: json.loads(l) for l in (SYN / 'evidence_cases.jsonl').read_text(encoding='utf-8').splitlines() if l.strip()}
    c = cases['p1_confirmed']
    decl = dict(c['declaration'], kind='predicate', type='P_COMMUNICATE')
    rows = [tuple(r) for r in c['rows']]
    assert G.decide_candidate(c['word'], decl, rows, CFG)['write'] == 'layer_confirmed'
    two = dict(CFG, rd_min_sources=2, role_frame_min_sources=2)
    assert G.decide_candidate(c['word'], decl, rows, two)['write'] == 'layer_estimated'                  # one document is not two sources
    rows2 = rows + [(a, 'doc:syn000000002', t, n, b) for (a, _s, t, n, b) in rows]
    assert G.decide_candidate(c['word'], decl, rows2, two)['write'] == 'layer_confirmed'
    low = [(a, s, t, n, 5) for (a, s, t, n, b) in rows]                                                    # below rd_min_total: the arm is not met
    assert G.decide_candidate(c['word'], decl, low, CFG)['write'] == 'layer_estimated'


# ---------------------------------------------------------------------------------------------------------------- K292 / K293 / K294 / K295 / K296
def test_the_same_document_twice_is_one_source(r9, tmp_path):
    copy_ = tmp_path / 'copy.txt'
    shutil.copy(HEARST_DOC, copy_)
    out, _ = run(tmp_path, r9, TABLE, docs=[HEARST_DOC, copy_])
    assert out['documents']['read'] == 1 and len(out['documents']['sources']) == 1
    assert [s['reason'].split(':')[0] for s in out['documents']['skipped']] == ['DUPLICATE_DOCUMENT']
    one = layer_rows(tmp_path)['ポルミナ']['evidence']['doc_rows']
    out2, _ = run(tmp_path, r9, TABLE, docs=[HEARST_DOC], layer='single')
    assert layer_rows(tmp_path, 'single')['ポルミナ']['evidence']['doc_rows'] == one and one == [['hearst', out['documents']['sources'][0], 'ARTIFACT', 2, None]]


def test_a_backend_that_fails_writes_nothing_to_the_layer(r9, tmp_path):
    out, be = run(tmp_path, r9, dict(TABLE, __fail_batches__=[0]))
    assert out['verdict'] == 'GREW' and out['backend_failed'] >= 1 and out['written'] == {'layer_confirmed': 0, 'layer_estimated': 0, 'layer_human': 0}
    assert not (tmp_path / 'dom.sqlite').exists()                                                           # nothing was written, not even an empty layer
    led = TestimonyLedger(tmp_path / 'ledger.jsonl')
    kinds = {e['type'] for e in led.entries()}
    assert 'backend_failed' in kinds and 'testimony' not in kinds and 'promoted_to_layer' not in kinds
    assert all(e['reason'] == 'BACKEND_FAILED:TIMEOUT' for e in led.entries() if e['type'] == 'backend_failed')


def test_a_batch_that_is_unreadable_or_incomplete_is_typed_and_writes_nothing(r9, tmp_path):
    for content, reason in (('not json', 'DECLARATION_INVALID:BAD_JSON'), ('', 'DECLARATION_INVALID:EMPTY_CONTENT'), (json.dumps({'items': []}), 'DECLARATION_INVALID:MISSING'),
                            (json.dumps({'nothing': 1}), 'DECLARATION_INVALID:NO_ITEMS')):
        d = tmp_path / reason.split(':')[1]
        d.mkdir()
        out = G.grow([str(HEARST_DOC)], str(d / 'dom.sqlite'), backend='fake', model='m', ledger_path=str(d / 'l.jsonl'), placement=r9,
                     chat=lambda m, msgs, f, c=content: {'ok': True, 'content': c, 'usage': {}, 'error': None})
        assert out['written'] == {'layer_confirmed': 0, 'layer_estimated': 0, 'layer_human': 0} and out['not_written'].get(reason, 0) >= 1 and not (d / 'dom.sqlite').exists()
    batch = G.parse_noun_batch(['a', 'b'], json.dumps({'items': [{'word': 'a', 'definition': 'x', 'hypernym': None, 'type': 'ARTIFACT'}, {'word': 'a', 'definition': 'x', 'hypernym': None, 'type': 'PLACE'},
                                                             {'word': 'b', 'definition': None, 'hypernym': None, 'type': 'NOT_A_TYPE'}]}))
    assert batch['a'] == (None, 'DECLARATION_INVALID:DUPLICATE') and batch['b'] == (None, 'DECLARATION_INVALID:TYPE')          # a repeated word is not taken: no entry is chosen by order


def test_by_default_only_typed_shapes_are_sent_and_the_ledger_holds_no_sentence_k296(r9, tmp_path):
    out, be = run(tmp_path, r9, TABLE)
    sentences = [s.strip() for s in HEARST_DOC.read_text(encoding='utf-8').splitlines() if s.strip()]
    sent = json.dumps(be.sent, ensure_ascii=False)
    for s in sentences:
        assert s not in sent and s.rstrip('。') not in sent
    shapes = [json.loads(line[len('SHAPES_JSON: '):]) for m in be.sent for x in m['messages'] for line in x['content'].split('\n') if line.startswith('SHAPES_JSON: ')]
    values = ''.join(v for d in shapes for vs in d.values() for v in vs)                         # the shapes themselves (the keys are the candidate words, which are sent anyway)
    assert values and not any(w in values for w in ('整備士', '工房', '調整', '部品', '点検', '交換', 'ヘクタス', 'ポルミナ', '午前'))
    assert '〈語〉' in values and 'SENTENCES_JSON' not in sent and '〈ARTIFACT〉' in values
    ledger = (tmp_path / 'ledger.jsonl').read_text(encoding='utf-8')
    assert '整備士' not in ledger and '工房' not in ledger and '"sentence"' not in ledger
    led = TestimonyLedger(tmp_path / 'ledger.jsonl')
    t = [e for e in led.entries() if e['type'] == 'testimony'][0]
    assert t['mask_user_text'] is True and t['provenance']['send_sentences'] is False and len(t['context']['sentence_sha256']) == 64
    # the candidate words are the only content words handed over (they are in WORDS_JSON)
    words = [json.loads(line[len('WORDS_JSON: '):]) for m in be.sent for x in m['messages'] for line in x['content'].split('\n') if line.startswith('WORDS_JSON: ')]
    assert sorted(w for ws in words for w in ws) == sorted(set(w for ws in words for w in ws))
    assert set(w for ws in words for w in ws) >= {'ポルミナ', 'ヘクタス', '午前'} and not ({'整備士', '部品', '調整'} & set(w for ws in words for w in ws))


def test_send_sentences_is_explicit_and_marked_in_the_ledger(r9, tmp_path):
    out, be = run(tmp_path, r9, TABLE, send_sentences=True)
    sent = json.dumps(be.sent, ensure_ascii=False)
    assert '整備士が工房でポルミナを調整した。' in sent and 'SENTENCES_JSON: ' in sent and 'SHAPES_JSON' not in sent and out['send_sentences'] is True
    led = TestimonyLedger(tmp_path / 'ledger.jsonl')
    t = [e for e in led.entries() if e['type'] == 'testimony'][0]
    assert t['provenance']['send_sentences'] is True and t['mask_user_text'] is False and t['context']['sentence'] in HEARST_DOC.read_text(encoding='utf-8')


def test_the_record_is_not_changed_and_without_the_layer_the_base_comes_back_k293(r9, tmp_path):
    doc = tmp_path / 'doc.txt'
    shutil.copy(HEARST_DOC, doc)
    before = hashlib.sha256(doc.read_bytes()).hexdigest()
    plain = {w: json.dumps(CP.query(w, placement=r9), ensure_ascii=False) for w in ('ポルミナ', '午前', '猫')}
    run(tmp_path, r9, TABLE, docs=[doc])
    assert hashlib.sha256(doc.read_bytes()).hexdigest() == before
    assert {w: json.dumps(CP.query(w, placement=r9), ensure_ascii=False) for w in plain} == plain             # the layer is a separate file: not asked for, no effect
    assert {w: json.dumps(CP.query(w, placement=r9, layer=False), ensure_ascii=False) for w in plain} == plain


def test_every_layer_row_has_its_ledger_row_k294(r9, tmp_path):
    out, _ = run(tmp_path, r9, TABLE)
    led = TestimonyLedger(tmp_path / 'ledger.jsonl')
    g = PL.growth(str(tmp_path / 'dom.sqlite'), led, CP._open(r9)[0].sha, True)
    assert g['ledger']['chain_ok'] is True and g['rows'] == sum(out['written'].values()) == g['ledger']['promoted_to_layer']
    lay = PL.open_layer(str(tmp_path / 'dom.sqlite'))[0]
    for e in lay.all_entries():
        row = [x for x in led.entries() if x['seq'] == e['ledger_seq']][0]
        assert row['type'] == 'promoted_to_layer' and row['key'] == e['ledger_key'] and row['layer_name'] == 'dom' and e['ledger_store_id'] == led.store_id
    assert led.verify()['lines'] == len(led.entries())


def test_the_candidates_come_from_the_base_alone_whatever_the_environment_says(r9, tmp_path, monkeypatch):
    out, be = run(tmp_path, r9, TABLE)
    first = sorted(w for m in be.sent for x in m['messages'] for line in x['content'].split('\n') if line.startswith('WORDS_JSON: ') for w in json.loads(line[len('WORDS_JSON: '):]))
    monkeypatch.setenv(PL.ENV_LAYER, str(tmp_path / 'dom.sqlite'))
    d = tmp_path / 'again'
    d.mkdir()
    out2, be2 = run(d, r9, TABLE)
    second = sorted(w for m in be2.sent for x in m['messages'] for line in x['content'].split('\n') if line.startswith('WORDS_JSON: ') for w in json.loads(line[len('WORDS_JSON: '):]))
    assert first == second and out['candidates'] == out2['candidates'] and out['not_candidate'] == out2['not_candidate'] and out['not_candidate']['BASE_DECIDED'] > 0
    assert '整備士' not in first                                                                                  # a word the base decides is not asked


def test_the_run_is_refused_with_a_type_and_writes_nothing(r9, tmp_path):
    be = G.TableBackend(TABLE)
    kw = dict(backend='fake', model='m', ledger_path=str(tmp_path / 'l.jsonl'), chat=be)
    assert G.grow([str(HEARST_DOC)], 'dom', placement=r9, **kw)['verdict'] == 'LAYER_UNAVAILABLE:ROOT_UNSET'
    assert G.grow([str(HEARST_DOC)], str(tmp_path / 'd.sqlite'), placement=str(tmp_path / 'no-such-placement'), **kw)['verdict'] == 'NO_PLACEMENT'
    assert G.grow([str(HEARST_DOC)], str(tmp_path / 'd.sqlite'), placement=r9, min_sources=0, **kw)['verdict'] == 'BAD_ARGUMENT'
    assert be.calls == 0 and not (tmp_path / 'd.sqlite').exists() and not (tmp_path / 'l.jsonl').exists()


def test_a_layer_of_another_base_is_refused_before_any_question(r9, tmp_path):
    led = TestimonyLedger(tmp_path / 'other.jsonl')
    PL.write_entry(str(tmp_path / 'dom.sqlite'), led, base_sha256='not-r9', word='語', type='ARTIFACT', origin='layer_human', decided_by=['layer_human'], evidence={}, role_frame=None, key='k')
    be = G.TableBackend(TABLE)
    out = G.grow([str(HEARST_DOC)], str(tmp_path / 'dom.sqlite'), backend='fake', model='m', ledger_path=str(tmp_path / 'l.jsonl'), placement=r9, chat=be)
    assert out['verdict'] == 'LAYER_UNAVAILABLE:BASE_MISMATCH' and be.calls == 0


def test_the_extraction_is_the_builders_not_a_copy():
    src = Path(G.__file__).read_text(encoding='utf-8')
    for name in ('def tokenize', 'def analyze', 'def _hearst_scan', 'def type_of', 'def _chain_count'):
        assert name not in src
    assert 'bcp.analyze' in src and 'bcp.tokenize' in src and 'bcp.type_of' in src and 'ct.decide_word' in src


def test_the_question_forms_are_closed_enums_from_the_inventories():
    ns, ps = G.noun_schema(), G.predicate_schema()
    t = ns['properties']['items']['items']['properties']['type']['enum']
    assert t == list(ct.NOUN_TYPES) + [None] and len(ct.NOUN_TYPES) == 18
    p = ps['properties']['items']['items']['properties']
    assert p['ptype']['enum'] == list(ct.PRED_TYPES) + [None]
    assert p['frame']['items']['properties']['roles']['items']['properties']['types']['items']['enum'] == list(ct.FRAME_NOUN_TYPES) and len(ct.FRAME_NOUN_TYPES) == 17
    assert all(k in G.noun_head() for k in ct.NOUN_TYPES) and all(k in G.predicate_head() for k in ct.PRED_TYPES)


def test_the_frozen_data_are_the_frozen_ones():
    root = Path(__file__).resolve().parents[1]
    listed = (root / 'artifacts' / 'w10-f05' / 'data_freeze.sha256').read_text(encoding='utf-8').splitlines()
    assert len(listed) >= 5
    for line in listed:
        sha, name = line.split('  ')
        assert hashlib.sha256((root / name).read_bytes()).hexdigest() == sha, name


# ---------------------------------------------------------------------------------------------------------------- r2: the provenance of a testimony (document id, version)
def test_a_testimony_names_its_document_and_a_typed_version(r9, tmp_path):
    out, _ = run(tmp_path, r9, TABLE, model_version='fake-table:abcdef123456')
    sources = out['documents']['sources']
    assert sources and all(s.startswith('doc:') for s in sources)
    led = TestimonyLedger(tmp_path / 'ledger.jsonl')
    rows = [e for e in led.entries() if e['type'] in ('testimony', 'not_adopted')]
    assert rows
    for e in rows:
        assert e['context']['doc_id'] == sources[0] and e['context']['doc_ids'] == [sources[0]]
        assert e['provenance']['version'] == 'fake-table:abcdef123456'


def test_the_version_is_never_empty_and_an_unknown_is_typed(r9, tmp_path):
    out, _ = run(tmp_path, r9, TABLE)                       # an injected chat: no endpoint is asked, the version is a typed unknown
    led = TestimonyLedger(tmp_path / 'ledger.jsonl')
    versions = {e['provenance']['version'] for e in led.entries() if e['type'] in ('testimony', 'not_adopted')}
    assert versions and all(v.startswith('VERSION_UNKNOWN:') for v in versions)
    assert G.resolve_model_version('ollama', 'm', ollama_url='http://example.com:11434').startswith('VERSION_UNKNOWN:NOT_LOCAL_HOST')   # nothing but the local host is asked
    assert G.resolve_model_version('openai', 'm').startswith('VERSION_UNKNOWN:')


def test_with_two_documents_each_testimony_names_the_first_document_that_holds_the_word(r9, tmp_path):
    other = tmp_path / 'other.txt'
    other.write_text('ポルミナは部品である。\nヘクタスはポルミナなどの部品である。\n', encoding='utf-8')
    out, _ = run(tmp_path, r9, TABLE, docs=[HEARST_DOC, other])
    src = out['documents']['sources']
    assert len(src) == 2
    led = TestimonyLedger(tmp_path / 'ledger.jsonl')
    for e in led.entries():
        if e['type'] in ('testimony', 'not_adopted'):
            assert e['context']['doc_id'] in src and e['context']['doc_ids'][0] == e['context']['doc_id']
