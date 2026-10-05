"""W12-c1 T1: the vocabulary layer (K401, K405-K407) on small synthetic documents. No placement, no corpus."""
import importlib.util
import json
import os
import sqlite3
import sys
from collections import Counter

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
spec = importlib.util.spec_from_file_location('build_initial_layers', os.path.join(ROOT, 'tools', 'build_initial_layers.py'))
BIL = importlib.util.module_from_spec(spec)
sys.modules['build_initial_layers'] = BIL
spec.loader.exec_module(BIL)

from verantyx import granularity as GR


def count(docs):
    """Documents (a list of texts) -> Counter of the number of documents a word stands alone in."""
    c = Counter()
    mixed = set()
    for t in docs:
        k, a, m = BIL.runs_of(t)
        c.update(k | a)
        mixed |= m
    return c, mixed


def test_three_documents_of_one_class_make_a_word():
    h, _ = count(['契約を結ぶ。', '契約は守る。', 'その契約だ。'])
    v = BIL.select_vocab(dict(h), {})
    assert v['契約']['origin_class'] == 'human' and v['契約']['docs_human'] == 3 and v['契約']['in_base_material'] is True


def test_two_documents_are_not_enough():
    h, _ = count(['契約を結ぶ。', '契約は守る。', '別の話。'])
    assert '契約' not in BIL.select_vocab(dict(h), {})


def test_classes_are_never_added_together():
    # human 2 + generated 1 = 3 documents in all, but neither class has 3: the word does not enter (K407: stacked, not bundled)
    h, _ = count(['契約を結ぶ。', '契約は守る。'])
    g, _ = count(['契約だ。'])
    assert '契約' not in BIL.select_vocab(dict(h), dict(g))
    g3, _ = count(['契約だ。', '契約です。', '契約の話。'])
    v = BIL.select_vocab(dict(h), dict(g3))
    assert v['契約']['origin_class'] == 'generated' and v['契約']['in_base_material'] is False
    h3, _ = count(['契約1。', '契約2。', '契約3。'])
    assert BIL.select_vocab(dict(h3), dict(g3))['契約']['origin_class'] == 'both'


def test_a_word_inside_a_longer_kanji_run_is_not_counted():
    docs = ['民事訴訟法の話。', '民事訴訟法を読む。', '民事訴訟法だ。']
    h, _ = count(docs)
    v = BIL.select_vocab(dict(h), {})
    assert '民事訴訟法' in v and '事訴' not in v and '訴訟' not in v
    # the same decision by the part of vera1 that is imported: a kanji word flanked by kanji is not standalone
    assert GR.standalone_count('事訴', '民事訴訟法') == 0 and GR.standalone_count('訴訟', '民事訴訟法') == 0


def test_a_katakana_word_inside_a_longer_katakana_run_is_not_counted():
    docs = ['チェーンリングを買う。', 'チェーンリングだ。', 'チェーンリングの話。']
    h, _ = count(docs)
    v = BIL.select_vocab(dict(h), {})
    assert 'チェーンリング' in v and 'リング' not in v
    assert GR.standalone_count('リング', 'チェーンリング') == 1       # the imported kanji-only test counts it: the gap (docs section 7) the builder closes


def test_long_vowel_mark_belongs_to_the_run():
    k, a, m = BIL.runs_of('コンピューターを使う。')
    assert 'コンピューター' in a and 'コンピュータ' not in a


def test_mixed_script_is_out_of_scope_and_counted_only():
    k, a, m = BIL.runs_of('電話ボックスで話す。')
    assert m == {'電話ボックス'}
    assert 'ボックス' in a and '電話' in k          # the single-script runs next to it are candidates; the mixed string itself is not
    docs = ['電話ボックスだ。'] * 3
    h, mixed = count(docs)
    v = BIL.select_vocab(dict(h), {})
    assert '電話ボックス' not in v and mixed == {'電話ボックス'}


def test_length_limits_and_one_character_words():
    k, a, m = BIL.runs_of('山に登る。' + '漢' * 9 + 'ア。' + 'カ' * 21)
    assert '山' not in k and '漢' * 9 not in k and 'ア' not in a and 'カ' * 21 not in a


def test_a_word_counts_once_per_document():
    k, a, m = BIL.runs_of('契約と契約と契約。')
    assert k == {'契約'}
    h, _ = count(['契約と契約と契約と契約。', '別。'])
    assert h['契約'] == 1


def test_generated_family_fields_and_unreadable_rows(tmp_path):
    root = tmp_path
    for fam, fname in BIL.FAMILY_FILE.items():
        (root / fam / 'heldout').mkdir(parents=True)
    rows = [{'q_variants': ['契約とは？'], 'answer': '約束です。', 'why': '決まりだから。', 'source': 'b1'},
            {'q_variants': ['契約とは？'], 'answer': '約束です。', 'source': 'b2'},
            {'q_variants': ['契約とは？'], 'source': 'b3'},
            {'nothing': 1, 'source': 'b4'}]
    with open(root / 'general_qa' / 'heldout' / 'records.jsonl', 'w', encoding='utf-8') as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + '\n')
        fh.write('not json\n')
    got = BIL.count_generated(str(root), families=['general_qa'])
    assert got['docs']['契約'] == 3                              # one document = one `source` (bundle)
    assert got['per_family']['general_qa']['rows_unreadable'] == 1
    assert got['skipped']['NO_READABLE_FIELD:general_qa'] == 1 and got['skipped']['BAD_JSON:general_qa'] == 1


def test_sqlite_layout_and_no_llm_marker(tmp_path):
    v = BIL.select_vocab({'契約': 3}, {})
    p = str(tmp_path / 'v.sqlite')
    BIL.write_vocab_sqlite(p, v, {'schema': BIL.VOCAB_SCHEMA, 'llm_declarations': False})
    con = sqlite3.connect(p)
    assert con.execute('SELECT word, script, docs_human, docs_generated, origin_class, in_base_material FROM words').fetchall() == [('契約', 'kanji', 3, 0, 'human', 1)]
    assert dict(con.execute('SELECT k, v FROM meta').fetchall())['llm_declarations'] == 'false'
    with pytest.raises(SystemExit):
        BIL.write_vocab_sqlite(p, v, {})               # nothing is overwritten


# ---- review r1 M2: the iteration mark U+3005 belongs to a kanji run
def test_iteration_mark_words_are_kept_whole_and_their_fragments_are_not_words():
    docs = ['代々木公園で会う。', '代々木公園を歩く。', '代々木公園だ。']
    h, _ = count(docs)
    v = BIL.select_vocab(dict(h), {})
    assert '代々木公園' in v and v['代々木公園']['script'] == 'kanji'
    assert '木公園' not in v and '代々' not in v
    # the imported part cuts at the mark (the hole this builder closes): `木公園` stands alone after `々`
    assert GR.standalone_count('木公園', '代々木公園') == 1


def test_iteration_mark_words_are_candidates():
    docs = ['人々は歩く。', '人々が来た。', '様々な人々。', '様々だ。', '様々の色。', '佐々木さん。', '佐々木が来た。', '佐々木だ。']
    h, _ = count(docs)
    v = BIL.select_vocab(dict(h), {})
    assert {'人々', '様々', '佐々木'} <= set(v)
    assert v['人々']['docs_human'] == 3 and v['様々']['docs_human'] == 3 and v['佐々木']['docs_human'] == 3
    assert '佐' not in v and '々木' not in v and '木' not in v


def test_a_run_that_starts_with_the_mark_is_dropped_not_trimmed():
    k, a, m = BIL.runs_of('あ々木々だ。ア々木。')
    assert '々木々' not in k and '木々' not in k and '々木' not in k
    assert k == set() or all(not w.startswith('々') for w in k)
    k2, _, _ = BIL.runs_of('草木々を見る。')
    assert k2 == {'草木々'}


def test_runs_of_kanji_equals_standalone_count_on_texts_without_the_mark():
    """review r1 M3: the builder does not import `granularity.standalone_count`; on texts without U+3005 the maximal kanji runs (length 2..8) are exactly
    the kanji strings w for which standalone_count(w, text) > 0, among all substrings of length 2..8 that are kanji."""
    import re
    texts = ['民事訴訟法の話。', '東京都立代々は無い。'.replace('々', ''), '契約を結び、契約は守る。', '日本国憲法と日本。', 'ABC漢字DEF学校。',
             '電話ボックスで話す。', '吾輩は猫である。名前はまだ無い。', '漢' * 9 + 'あ' + '山川', '三島由紀夫と川端康成の対談。']
    for t in texts:
        k, _, _ = BIL.runs_of(t)
        cands = {t[i:j] for i in range(len(t)) for j in range(i + 2, min(len(t), i + 8) + 1) if re.fullmatch(r'[㐀-䶿一-鿿]+', t[i:j])}
        standalone = {w for w in cands if GR.standalone_count(w, t) > 0}
        assert k == standalone, (t, sorted(k ^ standalone))
