"""W3-b5 (docs/COARSE_PLACEMENT.md 11.6 / 12.10, W3-b5 addition; docs/READING_SOUNDNESS.md section 10F K200-K202): the key `frame_generated` of a query.
The key is added, nothing else changes: the answer without it is the answer of the base commit byte for byte, the value is the row of `generated_frames` of the word
(whatever `frame_status` is), the key stands just before the first key of W3-a3's tail, and it is null for no placement, for a placement with no such table and for a word with no row.
A small placement made by the real builder is used here (the real placements r7 and r8 are tested in tests/test_semantic_read_w3b5.py)."""
import importlib.util
import json
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path

from verantyx import coarse_place as cp
from verantyx import coarse_types as ct

from test_coarse_place_w3a3_query import BATCH, built, q  # noqa: F401

TREE = Path(__file__).resolve().parents[2]
BASE_COMMIT = '7494ba2'
TAIL = ('generated_frame', 'frame_status', 'frame', 'frame_unconfirmed', 'frame_disagreement')


def base_module():
    src = subprocess.run(['git', '-C', str(TREE), 'show', '%s:verantyx/coarse_place.py' % BASE_COMMIT], capture_output=True, check=True).stdout.decode('utf-8')
    spec = importlib.util.spec_from_loader('verantyx._coarse_place_base_w3b5_small', loader=None)
    mod = importlib.util.module_from_spec(spec)
    mod.__package__ = 'verantyx'
    sys.modules[spec.name] = mod
    exec(compile(src, 'verantyx/coarse_place.py@%s' % BASE_COMMIT, 'exec'), mod.__dict__)
    return mod


def probes(path):
    con = sqlite3.connect('file:%s/placement.sqlite?mode=ro' % path, uri=True)
    words = [r[0] for r in con.execute('SELECT word FROM headwords ORDER BY word')]
    return words + ['ニセ叫ぶ', '全然ない語', '10kg', '2024年', '昨日', 'ホゲ'], con


def test_every_answer_has_the_key_just_before_the_tail_and_the_rest_is_the_answer_of_the_base_commit_byte_for_byte(built):
    base = base_module()
    words, con = probes(built['out'])
    n_value = 0
    for w in words:
        a, b = q(w, built['out']), base.query(w, placement=str(built['out']))
        assert 'frame_generated' in a and 'frame_generated' not in b, w
        assert json.dumps({k: v for k, v in a.items() if k != 'frame_generated'}, ensure_ascii=False) == json.dumps(b, ensure_ascii=False), w
        keys = list(a)
        tail = [k for k in TAIL if k in a]
        assert keys[keys.index('frame_generated') + 1] == tail[0] and keys[keys.index('frame_generated') - 1] == 'spelling', w
        if a['frame_generated'] is not None: n_value += 1
    assert n_value >= 4        # the predicates of the small placement have a row (叫ぶ 急ぐ 呟く 囁く, and the words that only the table has)


def test_the_value_is_the_row_of_the_table_of_the_word_whatever_the_status_of_the_frame_is(built):
    words, con = probes(built['out'])
    statuses = set()
    for w in words:
        a = q(w, built['out'])
        row = con.execute('SELECT model, effort, batch_id, attempt, ptype, frame FROM generated_frames WHERE word=?', (a['spelling']['normalized'],)).fetchone()
        if row is None:
            assert a['frame_generated'] is None, w
            continue
        want = {'origin': 'generated', 'constructed': True, 'ptype': row[4], 'frame': json.loads(row[5]), 'provenance': {'model': row[0], 'effort': row[1], 'batch_id': row[2], 'attempt': row[3]}}
        assert a['frame_generated'] == want, w
        statuses.add(a['frame_status'])
        # the invariants of the contract
        fg = a['frame_generated']
        assert fg['origin'] == 'generated' and fg['constructed'] is True and isinstance(fg['ptype'], str)
        assert all(p in ct.CASE_PARTICLES_9 for p in fg['frame']) and all(ts and all(t in ct.NOUN_TYPES for t in ts) for ts in fg['frame'].values())
    assert {'CONFIRMED', 'ESTIMATED'} <= statuses          # the key does not depend on whether the frame was confirmed


def test_a_confirmed_predicate_keeps_its_frame_and_the_generated_frame_is_the_whole_row_beside_it(built):
    a = q('叫ぶ', built['out'])
    assert a['frame_status'] == 'CONFIRMED' and a['frame'] == {'が': ['PERSON'], 'を': ['INFO_LANGUAGE']} and a['frame_unconfirmed'] == {'に': ['PERSON']}
    assert a['frame_generated']['frame'] == {'が': ['PERSON'], 'を': ['INFO_LANGUAGE'], 'に': ['PERSON']}       # everything the model wrote, confirmed or not
    assert a['frame_generated']['provenance'] == {'model': 'gpt-6-luna', 'effort': 'low', 'batch_id': BATCH, 'attempt': 1}
    e = q('急ぐ', built['out'])
    assert e['frame_status'] == 'ESTIMATED' and e['frame'] is None and e['frame_generated']['frame'] == {'が': ['PERSON'], 'を': ['INFO_LANGUAGE'], 'へ': ['PLACE']}


def test_no_placement_and_a_placement_without_the_table_give_null_and_the_other_keys_are_unchanged(built, tmp_path, monkeypatch):
    monkeypatch.delenv(cp.ENV_PLACEMENT, raising=False)
    base = base_module()
    a = cp.query('駅')
    assert a['state'] == 'NO_PLACEMENT' and a['frame_generated'] is None
    assert json.dumps({k: v for k, v in a.items() if k != 'frame_generated'}, ensure_ascii=False) == json.dumps(base.query('駅'), ensure_ascii=False)
    old = tmp_path / 'old'
    shutil.copytree(built['out'], old)
    con = sqlite3.connect(str(old / 'placement.sqlite'))
    con.execute('DROP TABLE generated_frames')
    con.commit(); con.close()
    m = json.loads((old / 'manifest.json').read_text(encoding='utf-8'))
    del m['outputs']['tables']['generated_frames']
    (old / 'manifest.json').write_text(json.dumps(m), encoding='utf-8')
    for w in ('叫ぶ', '急ぐ', '駅'):
        a = cp.query(w, placement=str(old))
        assert a['frame_generated'] is None, w
        assert json.dumps({k: v for k, v in a.items() if k != 'frame_generated'}, ensure_ascii=False) == json.dumps(base.query(w, placement=str(old)), ensure_ascii=False)
