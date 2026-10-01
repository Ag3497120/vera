"""Tiny disposable indexes exercise the real adapter, never corpus rebuilds."""
import hashlib
from pathlib import Path
from verantyx.evidence_library import EvidenceLibrary
from verantyx.one import Vera


def build(root,family,entries):
    return EvidenceLibrary.build(root/family/'evidence',family,
        [{'text':text,'source':'source'+str(i),'independent':independent} for i,(text,independent) in enumerate(entries)])


def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def test_read_only_existing_postings_public_semantic_route(tmp_path):
    build(tmp_path,'general_qa',[('ユキの担当はソラ。','one'),('ソラの居室は西棟。','one')])
    db=tmp_path/'general_qa/evidence/evidence.db';before=digest(db)
    v=Vera(mode='semantic',round3_root=tmp_path)
    try:
        r=v.ask('ユキの担当の居室はどこ？')
        assert r['verdict']=='ANSWER' and r['values']==['西棟']
        assert r['door']=='semantic_qa'
        assert {s['source'] for s in r['sources']}=={'source0','source1'}
        assert any(t['part']=='semantic_retrieve.Retriever' and t['read_only'] for t in r['trace'])
    finally:v.close()
    assert digest(db)==before


def test_family_and_independent_source_bindings_stay_separate(tmp_path):
    for fam,entries in [('general_qa',[('ユキの担当はソラ。','one')]),('local',[('ソラの居室は西棟。','one')])]:build(tmp_path,fam,entries)
    v=Vera(mode='semantic',round3_root=tmp_path)
    try:assert v.ask('ユキの担当の居室はどこ？')['verdict']=='UNKNOWN_NO_EVIDENCE'
    finally:v.close()
    independent=tmp_path/'independent';build(independent,'general_qa',[('ユキの担当はソラ。','one'),('ソラの居室は西棟。','two')])
    v=Vera(mode='semantic',round3_root=independent)
    try:assert v.ask('ユキの担当の居室はどこ？')['verdict']=='UNKNOWN_NO_EVIDENCE'
    finally:v.close()


def test_retrieval_overflow_abstains_without_prefix_answer(tmp_path):
    build(tmp_path,'general_qa',[(f'ユキの担当は人{i}。','one') for i in range(257)])
    v=Vera(mode='semantic',round3_root=tmp_path)
    try:
        r=v.ask('ユキの担当は誰？')
        assert r['verdict']=='UNKNOWN_BUDGET' and r['values']==[] and r['phase']=='retrieval'
    finally:v.close()


def test_missing_original_evidence_never_uses_general_answer(tmp_path):
    class Old:
        def ask(self,q):raise AssertionError('old ANSWER bypass')
    v=Vera(mode='semantic',round3_root=tmp_path,general=Old())
    try:assert v.ask('ユキの担当は誰？')['verdict']=='UNKNOWN_SOURCE_ASSET'
    finally:v.close()
