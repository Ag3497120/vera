"""Pinned material files are immutable; incomplete WAL checkpoints are held."""
import hashlib
import json
import sqlite3

import pytest
from verantyx.family_library import FamilyLibrary, _norm
from verantyx.material_source import MaterialSource
from verantyx.one import Vera


QUERY = 'レナは緑の箱を運んだ。 レナは箱を運んだ。'
PAYLOAD = {'family': 'paraphrase_entail', 'kind': 'pair', 'split': 'train',
           's1': 'レナは緑の箱を運んだ。', 's2': 'レナは箱を運んだ。',
           'label': 'entails', 'source': 'authored:immutable-test', 'sha': 'fixture'}


def index(tmp_path, *, keep_writer=False):
    folder = tmp_path/'paraphrase_entail'
    folder.mkdir()
    db = folder/'family.db'
    connection = sqlite3.connect(db)
    connection.execute('PRAGMA journal_mode=WAL')
    connection.executescript('CREATE TABLE variants(norm TEXT,rid INTEGER);'
                             'CREATE TABLE records(id INTEGER,source TEXT,sha TEXT,payload TEXT);')
    connection.execute('INSERT INTO variants VALUES (?,1)', (_norm(QUERY),))
    connection.execute('INSERT INTO records VALUES (1,?,?,?)',
                       (PAYLOAD['source'],PAYLOAD['sha'],json.dumps(PAYLOAD,ensure_ascii=False)))
    connection.commit()
    if not keep_writer:
        connection.close()  # Fixture-only checkpoint; never a release/live DB.
    return db, connection if keep_writer else None


def hashes(root):
    return {str(path.relative_to(root)):hashlib.sha256(path.read_bytes()).hexdigest()
            for path in root.rglob('*') if path.is_file()}


def test_public_immutable_read_leaves_all_files_unchanged(tmp_path, monkeypatch):
    db, _ = index(tmp_path)
    before = hashes(tmp_path)
    def forbidden(*args, **kwargs):
        raise AssertionError('RW FamilyLibrary constructor invoked')
    monkeypatch.setattr(FamilyLibrary, '__init__', forbidden)
    vera = Vera(round3_root=tmp_path, material_immutable=True)
    try:
        for _ in range(2):
            result = vera.material_candidates('paraphrase_entail', QUERY)
            assert result['verdict'] == 'MATERIALS' and not result['verified']
            assert result['records'][0]['payload'] == PAYLOAD
            assert result['trace'][0]['immutable'] is True
    finally:
        vera.close()
    assert hashes(tmp_path) == before
    assert not (db.parent/'family.db-wal').exists()
    assert not (db.parent/'family.db-shm').exists()


def test_nonempty_wal_is_refused_without_connecting_or_changing_files(tmp_path, monkeypatch):
    db, writer = index(tmp_path, keep_writer=True)
    before = hashes(tmp_path)
    assert (db.parent/'family.db-wal').stat().st_size > 0
    def forbidden(*args, **kwargs):
        raise AssertionError('incomplete immutable database was opened')
    monkeypatch.setattr(sqlite3, 'connect', forbidden)
    try:
        result = MaterialSource(tmp_path, immutable=True).candidates('paraphrase_entail', QUERY)
        assert result['verdict'] == 'UNKNOWN_SOURCE_ASSET'
        assert result['records'] == [] and 'checkpointed' in result['reason']
        assert hashes(tmp_path) == before
    finally:
        writer.close()


def test_pending_rollback_journal_is_not_ignored(tmp_path):
    db, _ = index(tmp_path)
    (db.parent/'family.db-journal').write_bytes(b'pending fixture journal')
    before = hashes(tmp_path)
    result = MaterialSource(tmp_path, immutable=True).candidates('paraphrase_entail', QUERY)
    assert result['verdict'] == 'UNKNOWN_SOURCE_ASSET' and hashes(tmp_path) == before


@pytest.mark.parametrize('value', ['yes', 1, None])
def test_immutable_mode_requires_explicit_boolean(value, tmp_path):
    with pytest.raises(ValueError): MaterialSource(tmp_path, immutable=value)
    with pytest.raises(ValueError): Vera(material_immutable=value)


def test_content_consumer_gets_same_immutable_material_boundary(tmp_path, monkeypatch):
    from verantyx import content_api
    index(tmp_path)
    before = hashes(tmp_path)
    observed = []
    class Engine:
        def __init__(self, material_source): self.source = material_source
        def ask(self, raw, *, materials=()):
            observed.append(self.source.candidates('paraphrase_entail', QUERY))
            return {'verdict':'UNKNOWN_CONTENT_TEST', 'text':'', 'budget':{}, 'trace':[]}
    monkeypatch.setattr(content_api, 'ContentEngine', Engine)
    vera = Vera(mode='content', round3_root=tmp_path, material_immutable=True)
    try: vera.ask('構成用の材料を読む')
    finally: vera.close()
    assert observed[0]['verdict'] == 'MATERIALS' and observed[0]['trace'][0]['immutable']
    assert hashes(tmp_path) == before


def test_separate_material_root_does_not_replace_qa_root(tmp_path):
    material_root = tmp_path/'materials'
    material_root.mkdir()
    index(material_root)
    base_qa = tmp_path/'base-qa'
    base_qa.mkdir()
    vera = Vera(mode='round5', round3_root=base_qa,
                material_root=material_root, material_immutable=True)
    try:
        material = vera.material_candidates('paraphrase_entail', QUERY)
        assert material['verdict'] == 'MATERIALS'
        # The ordinary QA path must still see the original empty QA root,
        # never promote a synthetic pair material into factual evidence.
        answer = vera.ask('レナの担当は誰？')
        assert answer['door'] == 'semantic_qa'
        assert answer['verdict'] == 'UNKNOWN_SOURCE_ASSET'
        assert answer['values'] == []
    finally:
        vera.close()
