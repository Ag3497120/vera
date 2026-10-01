"""The composition boundary reads provenance-bearing materials, not answers."""
import hashlib
import json

from verantyx.family_library import FamilyLibrary
from verantyx.one import Vera


def put(tmp_path, family, rows):
    corpus = tmp_path / 'corpus'
    source = corpus / 'codex' / family / 'from_pro' / 'records_test.jsonl'
    source.parent.mkdir(parents=True)
    source.write_text(''.join(json.dumps(r, ensure_ascii=False)+'\n' for r in rows))
    out = tmp_path / 'indexes'
    FamilyLibrary.build(corpus, family, out/family)
    return out


def pair(sha, label='entails'):
    return {'family': 'paraphrase_entail', 'split': 'train', 'kind': 'pair',
            's1': 'ミオは青い箱を運んだ。', 's2': 'ミオは箱を運んだ。',
            'label': label, 'reason': '限定を落とした向きだけの含意。',
            'phenomenon': 'modifier', 'topic': '荷物', 'sha': sha,
            'source': 'llm_authored:codex:test-b000001'}


def test_public_material_reader_preserves_pair_direction_and_never_calls_answer(tmp_path, monkeypatch):
    record = pair('pair1')
    root = put(tmp_path, 'paraphrase_entail', [record])
    path = root/'paraphrase_entail/family.db'
    before = hashlib.sha256(path.read_bytes()).hexdigest()
    def forbidden(*args, **kwargs): raise AssertionError('legacy answer was called')
    monkeypatch.setattr(FamilyLibrary, 'ask', forbidden)
    v = Vera(round3_root=root)
    r = v.material_candidates('paraphrase_entail', record['s1']+' '+record['s2'])
    assert r['verdict'] == 'MATERIALS' and r['verified'] is False
    assert len(r['records']) == 1 and r['records'][0]['payload'] == record
    assert r['records'][0]['role'] == 'structural_material'
    assert 'values' not in r and 'answer' not in r and 'text' not in r
    assert r['trace'][0]['selection_is_evidence'] is False
    v.close()
    assert hashlib.sha256(path.read_bytes()).hexdigest() == before


def test_fiction_keeps_order_and_does_not_mix_families(tmp_path):
    record = {'family': 'narrative', 'split': 'train', 'kind': 'story', 'title': '雨の庭',
              'theme': '雨', 'setting': '庭', 'tone': '静か', 'sha': 'story1',
              'source': 'llm_authored:codex:test-story1',
              'sentences': [{'text': 'ミオは庭へ出た。', 'shape': 'start'},
                            {'text': '雨が止んだ。', 'shape': 'turn'},
                            {'text': 'ミオは家へ戻った。', 'shape': 'ending'}]}
    root = put(tmp_path, 'narrative', [record]); v = Vera(round3_root=root)
    r = v.material_candidates('narrative', '雨の庭 雨 庭')
    assert r['verdict'] == 'MATERIALS'
    assert r['records'][0]['payload']['sentences'] == record['sentences']
    assert r['records'][0]['role'] == 'fiction_material'
    assert v.material_candidates('paraphrase_entail', '雨の庭')['verdict'] == 'UNKNOWN_SOURCE_ASSET'
    v.close()


def test_candidate_overflow_does_not_choose_a_prefix_or_a_label(tmp_path):
    rows = [pair('one', 'entails'), pair('two', 'neutral')]
    root = put(tmp_path, 'paraphrase_entail', rows); v = Vera(round3_root=root)
    query = rows[0]['s1']+' '+rows[0]['s2']
    r = v.material_candidates('paraphrase_entail', query, limit=1)
    assert r['verdict'] == 'UNKNOWN_BUDGET' and not r['records']
    r = v.material_candidates('paraphrase_entail', query, limit=2)
    assert {x['payload']['label'] for x in r['records']} == {'entails', 'neutral'}
    assert r['verified'] is False
    v.close()
