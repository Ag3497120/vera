"""W1-a5: the slots of the convention that the reader could not fill -- the auxiliary verbs of aspect (convention 3: ている / てしまう / ておく), the floating quantity (convention 6) and
the mark of an adverb (`flags.adverbs`). The rules were registered in docs/READING_SOUNDNESS.md section 10G (K210-K218) before the data (tests/reading_soundness/ja_r12.jsonl) and
this file were written.

Run under a clean environment: a VERA_PLACEMENT left in the shell would change the default path of the entry (the fixture below removes it for the tests of this file).
The gates 5 and 6 of the aspect rule (K211) cannot be reached by a sentence the base entry reads (it reads no sentence of two clauses with an auxiliary chain), so they are tested through the
wrapper with a stand-in for the base entry that returns the output a reader would give.

Round 2 (docs section 10G, change record K218): the mark of an adverb and the quantity of a noun phrase were withdrawn; the rows of the data that this turns back to an abstention are the list
artifacts/w1-a5/r2/k218_withdrawn_rows.json (made by rule from the output of round 1 before the implementation). Such a row is tested to abstain as the list pins; every row is still tested
for no misread.
"""
import ast
import importlib.util
import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

TREE = Path(__file__).resolve().parent.parent
RS = TREE / 'tests' / 'reading_soundness'
BASE_COMMIT = 'df4f001'
# Integration (auditor, 2026-10-04): the two scope tests (`_added_lines`, the hunk count, the unchanged base functions) attest the W1-a5 ticket
# itself, so on dev they compare the ticket commit against its base instead of the working tree (W5-e, merged before, adds a line to
# document_view and a section in the middle of the reader).
TICKET_COMMIT = '616c330'


def _load_by_path(name, path):
    if name in sys.modules: return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, str(path))
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


F = _load_by_path('w3b2_fakes_in_test_w1a5', RS / 'w3b2_fakes.py')

from tools.bank_score.v2 import b1    # noqa: E402
from verantyx import event_cross as EC    # noqa: E402
from verantyx import semantic_read as SR    # noqa: E402
from verantyx import semantic_reader as R    # noqa: E402

DOCS = (TREE / 'docs' / 'READING_SOUNDNESS.md').read_text(encoding='utf-8')
CONVENTIONS = (TREE / 'docs' / 'READING_CONVENTIONS.md').read_text(encoding='utf-8')
DATA_FILE = RS / 'ja_r12.jsonl'
DATA = [json.loads(l) for l in DATA_FILE.read_text(encoding='utf-8').splitlines() if l.strip()]
EXC_FILE = TREE / 'artifacts' / 'w1-a5' / 'expect_exceptions.json'
EXCEPTIONS = {e['id']: e for e in json.loads(EXC_FILE.read_text(encoding='utf-8'))['exceptions']}
WD_FILE = TREE / 'artifacts' / 'w1-a5' / 'r2' / 'k218_withdrawn_rows.json'
WITHDRAWN = {r['id']: r for r in json.loads(WD_FILE.read_text(encoding='utf-8'))['rows']}
PATHS = ('not_triggered', 'aspect_kept', 'aspect_corrected', 'aspect_refused', 'reread', 'reread_refused')


@pytest.fixture(autouse=True)
def _no_placement_in_the_environment(monkeypatch):
    monkeypatch.delenv('VERA_PLACEMENT', raising=False)
    monkeypatch.delenv('VERA_COARSE_PLACEMENT', raising=False)


def git(*args):
    return subprocess.run(['git', '-C', str(TREE)] + list(args), capture_output=True, check=True).stdout.decode('utf-8')


def _base_module():
    src = git('show', '%s:verantyx/semantic_read.py' % BASE_COMMIT)
    spec = importlib.util.spec_from_loader('verantyx._semantic_read_base_w1a5', loader=None)
    mod = importlib.util.module_from_spec(spec)
    mod.__package__ = 'verantyx'
    sys.modules[spec.name] = mod
    exec(compile(src, 'verantyx/semantic_read.py@%s' % BASE_COMMIT, 'exec'), mod.__dict__)
    return mod


BASE = _base_module()


def block(name):
    m = re.search(r'<!-- BEGIN table:%s -->\n(.*?)<!-- END table:%s -->' % (name, name), DOCS, re.S)
    assert m, name
    return [line for line in m.group(1).splitlines() if line.startswith('|') and not set(line) <= set('|- ')][1:]


def cells(line):
    return [c.strip().strip('`') for c in re.split(r' \| ', line.strip()[1:-1].strip())]


def clause_of(out):
    assert out['readable'] is True, out
    assert len(out['clauses']) == 1, out
    return out['clauses'][0]


def reasons(out):
    assert out['readable'] is False, out
    return out['abstain']['reasons']


def last_reason(text):
    return reasons(SR.read(text, 'ja', placement=None))[-1]


# ------------------------------------------------------------------------------------------------ 1. the registered tables are the constants
def test_the_registered_tables_are_the_constants_of_the_reader():
    assert [cells(l)[0] for l in block('w1a5_aspect_aux')] == list(R.W1A5_ASPECT_AUX)
    rows = []
    for l in block('w1a5_aspect_endings'):
        c = cells(l)
        rows.append((c[0], () if c[1] == '(なし)' else tuple(c[1].split()), c[2], c[3]))
    assert rows == list(R.W1A5_ASPECT_ENDINGS) and len(rows) == 8
    assert [cells(l)[0] for l in block('w1a5_event_counters')] == list(R.W1A5_EVENT_COUNTERS) == ['回', '度']
    assert all(cells(l)[1] == 'event' for l in block('w1a5_event_counters'))
    numerals = {cells(l)[0]: tuple(cells(l)[1].split()) for l in block('w1a5_numerals')}
    assert numerals == {'digits': tuple(R.W1A5_KANJI_DIGITS), 'units': tuple(R.W1A5_KANJI_UNITS)}
    classes = {cells(l)[0]: tuple(cells(l)[1].split()) for l in block('w1a5_adverb_classes')}
    assert classes == {'convention': tuple(R.W1A5_CONVENTION_ADVERBS), 'modal': tuple(R.W1A5_ADVERB_CLASSES['modal']), 'approx': tuple(R.W1A5_ADVERB_CLASSES['approx'])}
    assert sum(len(v) for v in R.W1A5_ADVERB_CLASSES.values()) == 9
    assert list(R.W1A5_COMPARISON_PARTICLES) == ['より', 'ほど', 'くらい', 'ぐらい']
    assert [cells(l)[0].replace('\\|', '|') for l in block('w1a5_reasons')] == list(R.W1A5_REASONS)


def test_the_list_of_auxiliary_verbs_is_a_copy_of_the_convention_section_3():
    line = next(l for l in CONVENTIONS.splitlines() if l.startswith('- **述語**'))
    written = re.findall(r'〜(て[ぁ-ん]+)(?=／|」)', line)
    assert written == ['ている', 'てしまう', 'ておく']
    lemmas = []
    for w in written:
        toks = R._tokens('読んで' + w[1:])
        lemmas.append(toks[-1][0].feature.lemma)
    assert lemmas == list(R.W1A5_ASPECT_AUX)
    assert [cells(l)[1] for l in block('w1a5_aspect_aux')] == [w[1:] for w in written]
    assert '追記（W1-a5' in CONVENTIONS and 'flags.adverbs' in CONVENTIONS


# ------------------------------------------------------------------------------------------------ 3. no list of words of sentences
GRAMMAR = {
    # the terms of the tagger (part of speech, sub-class, form of conjugation)
    '名詞', '代名詞', '数詞', '接尾辞', '名詞的', '助数詞', '助数詞可能', '助詞', '格助詞', '接続助詞', '係助詞', '副助詞', '動詞', '非自立可能', '助動詞', '副詞', '接続詞',
    '補助記号', '句点', '読点', '連体詞', '形容詞', '形状詞', '接頭辞', '普通名詞', '固有名詞', '副詞可能', '一般', 'サ変可能', '終止形', '連用形', '未然形', '仮定形', '命令形', '連体形',
    # the particles and the auxiliaries of the closed grammar the rules name
    'が', 'を', 'に', 'で', 'へ', 'と', 'から', 'まで', 'は', 'も', 'か', 'て', 'の', 'ない', 'ぬ', 'ず', 'ます', 'た', 'です', 'れる', 'られる', 'せる', 'させる', 'する', '為る',
    'てる', 'でる', 'ちゃう', 'じゃう', '、', '。', 'ん', 'ませ', 'なかっ',
}


def _section_of_the_reader():
    """Integration (auditor ruling 2026-10-06, W16-t1b K800): the section ends before the next ticket's mark `# W16-t1b:` (the modality gate appended at the end of the reader, attested by
    tests/test_w16t1b_*.py); old expectation: the section runs from `# W1-a5:` to the end of the file."""
    src = (TREE / 'verantyx' / 'semantic_reader.py').read_text(encoding='utf-8')
    i = src.index('# W1-a5:')
    j = src.index('# W16-t1b:') if '# W16-t1b:' in src else len(src)
    return ast.parse(src[i:j])


def _registered_words():
    words = set(R.W1A5_ASPECT_AUX) | set(R.W1A5_EVENT_COUNTERS) | set(R.W1A5_KANJI_DIGITS) | set(R.W1A5_KANJI_UNITS) | set(R.W1A5_CONVENTION_ADVERBS) | set(R.W1A5_COMPARISON_PARTICLES)
    for v in R.W1A5_ADVERB_CLASSES.values(): words |= set(v)
    for cform, aux, pol, tense in R.W1A5_ASPECT_ENDINGS: words |= {cform} | set(aux)
    words |= set(R.W1A5_REASONS)
    words |= {a[:-1] for a in R.W1A5_ASPECT_AUX}
    return words


def test_the_w1a5_section_of_the_reader_holds_no_word_of_a_sentence():
    tree = _section_of_the_reader()
    docstrings = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.ClassDef, ast.Module)) and node.body and isinstance(node.body[0], ast.Expr) and isinstance(getattr(node.body[0], 'value', None), ast.Constant):
            docstrings.add(id(node.body[0].value))
    allowed = GRAMMAR | _registered_words()
    stray = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) not in docstrings:
            if any(ord(ch) > 127 for ch in node.value) and node.value not in allowed:
                stray.append(node.value)
    assert stray == [], stray
    assert len(R.W1A5_ASPECT_AUX) == 3


# ------------------------------------------------------------------------------------------------ 4. the range of the change
def _added_lines(path):
    added, removed = [], []
    for line in git('diff', '-U0', BASE_COMMIT, TICKET_COMMIT, '--', path).splitlines():
        if line.startswith('+++') or line.startswith('---'): continue
        if line.startswith('+'): added.append(line[1:])
        elif line.startswith('-'): removed.append(line[1:])
    return added, removed


def test_the_reader_file_only_gains_lines_at_its_end_and_the_entry_gains_two_lines_before_main():
    added, removed = _added_lines('verantyx/semantic_reader.py')
    assert removed == [] and added
    base_len = len(git('show', '%s:verantyx/semantic_reader.py' % BASE_COMMIT).splitlines())
    hunks = [l for l in git('diff', '-U0', BASE_COMMIT, TICKET_COMMIT, '--', 'verantyx/semantic_reader.py').splitlines() if l.startswith('@@')]
    assert len(hunks) == 1
    m = re.match(r'@@ -(\d+),0 \+(\d+)', hunks[0])
    assert m and int(m.group(1)) == base_len and int(m.group(2)) == base_len + 1    # the one hunk adds lines after the last line of the base and removes none
    added2, removed2 = _added_lines('verantyx/semantic_read.py')
    assert removed2 == [] and len(added2) == 2
    assert added2[0].startswith('from .semantic_reader import w1a5_wrap as _w1a5_wrap') and added2[1] == '_read_ja = _w1a5_wrap(_read_ja)'
    text = (TREE / 'verantyx' / 'semantic_read.py').read_text(encoding='utf-8')
    assert text.index('_read_ja = _w1a5_wrap(_read_ja)') < text.index("if __name__ == '__main__':")
    changed = [p for p in git('diff', '--name-only', BASE_COMMIT, TICKET_COMMIT, '--', 'verantyx').split()]
    assert sorted(changed) == ['verantyx/semantic_read.py', 'verantyx/semantic_reader.py']


def test_the_function_of_the_base_entry_are_unchanged_and_the_two_names_of_w3b4_are_not_assigned_again():
    def functions(src):
        return {n.name: ast.dump(n) for n in ast.parse(src).body if isinstance(n, ast.FunctionDef)}
    for name in ('semantic_read', 'semantic_reader'):
        base = functions(git('show', '%s:verantyx/%s.py' % (BASE_COMMIT, name)))
        now = functions(git('show', '%s:verantyx/%s.py' % (TICKET_COMMIT, name)))     # the ticket's own file (see the note at TICKET_COMMIT)
        assert {k: v for k, v in now.items() if k in base} == base, name
    tree = _section_of_the_reader()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Assign, ast.AugAssign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for t in targets:
                assert not (isinstance(t, ast.Name) and t.id in ('typed_plan_u_ja', 'typed_plan_u_w3b2_ja', 'typed_plan_u_w3b4_ja', 'typed_plan_u_w3b1_ungated_ja')), t.id
    assert SR._read_ja.__wrapped__.__name__ == '_read_ja'


# ------------------------------------------------------------------------------------------------ 5. the data
def test_the_data_has_the_registered_keys_ids_and_counts():
    keys = ['id', 'lang', 'category', 'behavior', 'input', 'text', 'expect', 'entry_expect', 'w1a5_expect', 'construction', 'note']
    assert len({r['input'] for r in DATA}) == len(DATA) == len({r['id'] for r in DATA})
    for r in DATA:
        assert list(r) == keys, r['id']
        assert r['input'] == r['text'] and r['lang'] == 'ja' and r['category'] in ('aspect', 'quantity', 'adverb')
        assert r['behavior'] in ('read', 'abstain') and r['entry_expect'] == r['behavior']
        assert r['behavior'] != 'read' or r['expect']['must_not'], r['id']
        assert list(r['w1a5_expect']) == ['path', 'reason_prefix', 'quantifiers', 'flags']
        assert r['w1a5_expect']['path'] in PATHS + (None,)
    for cat in ('aspect', 'quantity', 'adverb'):
        assert sum(1 for r in DATA if r['category'] == cat and r['behavior'] == 'read') >= 20
        assert sum(1 for r in DATA if r['category'] == cat and r['behavior'] == 'abstain') >= 20
    for cat in ('aspect',):
        paths = [r['w1a5_expect']['path'] for r in DATA if r['category'] == cat and r['behavior'] == 'read']
        for p in ('aspect_kept', 'aspect_corrected', 'reread'): assert paths.count(p) >= 3


ALLOWED_CLAUSE_KEYS = ('predicate', 'roles', 'polarity', 'tense', 'modality', 'voice', 'quantifiers', 'flags')


@pytest.mark.parametrize('row', DATA, ids=[r['id'] for r in DATA])
def test_every_row_of_the_data_is_read_or_refused_as_registered_and_judged_correct(row):
    out = SR.read(row['input'], 'ja', placement=None)
    verdict = b1.judge(row['expect'], 'ja', out)
    ex = R.w1a5_explain_ja(row['input'])
    want = row['w1a5_expect']
    assert ex['path'] in PATHS
    if row['id'] in WITHDRAWN:
        # a row that K218 (round 2) turned back to an abstention (artifacts/w1-a5/r2/k218_withdrawn_rows.json, made by rule before the implementation): it abstains, as the list pins
        wd = WITHDRAWN[row['id']]
        assert not out['readable'] and verdict['verdict'] in ('correct', 'abstain'), (out, verdict)
        assert (ex['path'], ex['reason']) == (wd['pinned_path'], wd['pinned_reason']), (ex, wd)
        base = BASE.read(row['input'], 'ja', placement=None)
        if wd['kind'] == 'adverb_mark':
            assert wd['pinned_path'] == 'not_triggered' and out == base
        else:
            assert wd['kind'] == 'noun_phrase_quantity' and wd['pinned_path'] == 'reread_refused'
            assert not base['readable'] and out['abstain']['kind'] == base['abstain']['kind']
            assert out['abstain']['reasons'][:-1] == base['abstain']['reasons'] and out['abstain']['reasons'][-1] == wd['pinned_reason']
            assert ex['quantity']['value'] == wd['round1_value']          # the value of the numerals is still converted (and checked) on the way to the refusal
        return
    assert ('read' if out['readable'] else 'abstain') == row['entry_expect'], out
    assert verdict['verdict'] == 'correct', verdict
    if row['id'] in EXCEPTIONS:
        # the frozen prediction of the path was another one (artifacts/w1-a5/expect_exceptions.json, docs 10G test change record 1): the entry abstains as registered, nothing is done
        pinned = EXCEPTIONS[row['id']]
        assert (ex['path'], ex['reason']) == (pinned['observed_path'], pinned['observed_reason']) and not out['readable']
        assert out == BASE.read(row['input'], 'ja', placement=None)
        return
    if want['path'] is not None: assert ex['path'] == want['path'], (ex, want)
    if want['reason_prefix'] is not None:
        assert ex['reason'] is not None and ex['reason'].startswith(want['reason_prefix']), (ex, want)
        assert out['abstain']['reasons'][-1] == ex['reason']
    if out['readable']:
        c = out['clauses'][0]
        assert set(c) <= set(ALLOWED_CLAUSE_KEYS), c
        if want['quantifiers'] is not None: assert c.get('quantifiers', {}) == want['quantifiers']
        if want['flags'] is not None: assert c.get('flags', {}) == want['flags']
        if 'quantifiers' in c or 'flags' in c: assert ex['path'] == 'reread'
        if 'flags' in c: assert list(c)[-1] == 'flags'
        if 'quantifiers' in c: assert list(c).index('quantifiers') == list(c).index('voice') + 1
    else:
        assert out['clauses'] == [] and out['relations'] == []


def test_no_row_of_the_data_is_misread_or_incomplete_and_the_three_kinds_are_read_in_at_least_twenty_rows_each():
    # round 2: the "at least twenty each" of round 1 is released by the auditor's decision (docs 10G H236); the number of rows read and judged correct is pinned to the measured value
    verdicts = {}
    for r in DATA:
        verdicts[r['id']] = b1.judge(r['expect'], 'ja', SR.read(r['input'], 'ja', placement=None))['verdict']
    assert not [i for i, v in verdicts.items() if v in ('misread', 'incomplete', 'UNJUDGED')]
    reads = {r['id'] for r in DATA if r['behavior'] == 'read'}
    correct = {i for i in reads if verdicts[i] == 'correct'}
    # a row that is expected to be read and is abstained from (verdict abstain) is allowed only on a withdrawn row; the other rows that are expected to be read are read and correct
    assert {i for i, v in verdicts.items() if v == 'abstain'} == reads & set(WITHDRAWN) == reads - correct and not (correct & set(WITHDRAWN))
    counts = {cat: sum(1 for r in DATA if r['category'] == cat and r['id'] in correct) for cat in ('aspect', 'quantity', 'adverb')}
    assert counts == {'aspect': 16, 'quantity': 6, 'adverb': 0}, counts


def test_a_read_output_of_w1a5_fits_the_check_of_the_cross_once_flags_is_a_key_of_the_entry(monkeypatch):
    monkeypatch.setattr(EC, 'ENTRY_FLAG_KEYS', EC.ENTRY_FLAG_KEYS + ('flags',))
    n = 0
    for r in DATA:
        out = SR.read(r['input'], 'ja', placement=None)
        if out['readable']:
            assert EC.build_crosses(out).status == 'CROSSED', r['id']
            assert 'flags' not in out['clauses'][0], r['id']; n += 1
    assert n == 22


# ------------------------------------------------------------------------------------------------ 6. the placement does not change what W1-a5 decides
@pytest.mark.parametrize('row', DATA, ids=[r['id'] for r in DATA])
def test_the_decision_of_w1a5_is_the_same_with_a_placement_that_knows_nothing_and_it_asks_nothing(row):
    q1, q2 = F.MapQuery({}), F.MapQuery({})
    none = R.w1a5_explain_ja(row['input'])
    with_q = R.w1a5_explain_ja(row['input'], q1)
    assert none['path'] == with_q['path'], (none, with_q)
    SR.read(row['input'], 'ja', placement=q1)
    q1.calls.clear(); BASE.read(row['input'], 'ja', placement=q2); q2.calls.clear()
    SR.read(row['input'], 'ja', placement=q1); BASE.read(row['input'], 'ja', placement=q2)
    assert q1.calls == q2.calls


# ------------------------------------------------------------------------------------------------ 7. nothing to do: the same object
def test_when_w1a5_does_nothing_the_output_is_the_object_of_the_base_entry():
    seen = 0
    for r in DATA:
        calls = []
        def spy(text, placement=None, _calls=calls):
            out = SR._read_ja.__wrapped__(text, placement); _calls.append(out); return out
        out = R.w1a5_wrap(spy)(r['input'], None)
        if R.w1a5_explain_ja(r['input'])['path'] == 'not_triggered':
            assert out is calls[0], r['id']; seen += 1
    assert seen >= 25


def _entry_inputs():
    lines = [json.loads(l)['text'] for l in (TREE / 'artifacts' / 'w3-b4' / 'entry_inputs.txt').read_text(encoding='utf-8').splitlines() if l.strip()]
    return [t for i, t in enumerate(lines) if i % 10 == 0 and SR.detect_lang(t) == 'ja']


def test_for_the_inputs_of_the_entry_w1a5_either_does_nothing_or_does_one_of_the_registered_things():
    seen = {}
    for text in _entry_inputs():
        try: base = BASE.read(text, 'ja', placement=None)
        except Exception: continue      # an input the entry refuses with an error (the error class of the base module is its own)
        out = SR.read(text, 'ja', placement=None)
        ex = R.w1a5_explain_ja(text)
        seen[ex['path']] = seen.get(ex['path'], 0) + 1
        if ex['path'] == 'not_triggered':
            assert out == base, text
        elif ex['path'] in ('aspect_kept',):
            assert out == base and base['readable'], text
        elif ex['path'] == 'aspect_corrected':
            assert base['readable'] and out['readable']
            a, b = base['clauses'][0], out['clauses'][0]
            assert {k: v for k, v in a.items() if k not in ('polarity', 'tense')} == {k: v for k, v in b.items() if k not in ('polarity', 'tense')}
        elif ex['path'] == 'aspect_refused':
            assert base['readable'] and not out['readable']
        else:
            assert not base['readable'], text
            assert out['readable'] or out['abstain']['reasons'][:-1] == base['abstain']['reasons'], text
    assert seen.get('not_triggered', 0) > 100


def test_the_english_entry_is_the_base_entry():
    rows = [json.loads(l) for l in (RS / 'en.jsonl').read_text(encoding='utf-8').splitlines() if l.strip()][:40]
    for r in rows:
        assert SR.read(r['text'], 'en', placement=None) == BASE.read(r['text'], 'en', placement=None), r['text']


def test_the_depth_is_given_back_even_when_the_base_raises_and_inside_the_base_nothing_is_done():
    def boom(text, placement=None): raise RuntimeError('x')
    with pytest.raises(RuntimeError): R.w1a5_wrap(boom)('兄が本を読んでいない。', None)
    assert R.W1A5_DEPTH == [0]
    seen = []
    def base(text, placement=None):
        seen.append(R.W1A5_DEPTH[0]); return SR._read_ja.__wrapped__(text, placement)
    w = R.w1a5_wrap(base)
    out = w('兄が本を読んでいない。', None)
    assert seen == [1] and R.W1A5_DEPTH == [0] and clause_of(out)['polarity'] == '-'
    R.W1A5_DEPTH[0] = 1
    try:
        inner = w('兄が本を読んでいない。', None)
    finally:
        R.W1A5_DEPTH[0] = 0
    assert clause_of(inner)['polarity'] == '+'      # at depth 1 the base is called as it is (W3-b3 reads clauses with it): the base misreads this
    assert getattr(w, '__wrapped__', None) is base and w.__name__ == base.__name__


# ------------------------------------------------------------------------------------------------ 8. aspect
ASPECT_ROWS = [
    ('兄が本を読んでいる。', '+', 'nonpast'), ('兄が本を読んでいた。', '+', 'past'), ('兄が本を読んでいます。', '+', 'nonpast'), ('兄が本を読んでいました。', '+', 'past'),
    ('兄が本を読んでいない。', '-', 'nonpast'), ('兄が本を読んでいなかった。', '-', 'past'), ('兄が本を読んでいません。', '-', 'nonpast'), ('兄が本を読んでいませんでした。', '-', 'past'),
    ('兄が本を読んでしまった。', '+', 'past'), ('兄が本を読んでしまいました。', '+', 'past'), ('兄が本を読んでしまわなかった。', '-', 'past'), ('兄が本を読んでしまいませんでした。', '-', 'past'),
    ('兄が本を読んでおいた。', '+', 'past'), ('兄が本を読んでおきました。', '+', 'past'), ('兄が本を読んでおかなかった。', '-', 'past'), ('兄が本を読んでおきませんでした。', '-', 'past'),
    ('母が手紙を書いていない。', '-', 'nonpast'), ('弟が庭で遊んでいなかった。', '-', 'past'), ('母が部屋を掃除していません。', '-', 'nonpast'), ('母が部屋を掃除していました。', '+', 'past'),
]


@pytest.mark.parametrize('text,pol,tense', ASPECT_ROWS, ids=[t for t, _, _ in ASPECT_ROWS])
def test_the_ending_of_the_auxiliary_decides_the_polarity_and_the_tense_as_the_table_says(text, pol, tense):
    c = clause_of(SR.read(text, 'ja', placement=None))
    assert (c['polarity'], c['tense']) == (pol, tense) and c['modality'] is None and c['voice'] == 'active'
    assert R.w1a5_explain_ja(text)['aspect']['polarity'] == pol


def test_the_corrected_output_differs_from_the_base_output_in_polarity_and_tense_only():
    for text in ('兄が本を読んでいない。', '兄が本を読んでいなかった。', '兄が本を読んでいません。', '兄が本を読んでしまわなかった。'):
        a, b = clause_of(BASE.read(text, 'ja', placement=None)), clause_of(SR.read(text, 'ja', placement=None))
        assert a['polarity'] == '+' and b['polarity'] == '-'
        assert {k: v for k, v in a.items() if k not in ('polarity', 'tense')} == {k: v for k, v in b.items() if k not in ('polarity', 'tense')}
        assert list(a) == list(b)
    assert R.w1a5_explain_ja('兄が本を読んでいない。')['path'] == 'aspect_corrected'
    assert R.w1a5_explain_ja('兄が本を読んでいる。')['path'] == 'aspect_kept'


def test_the_gate_1_an_auxiliary_that_is_not_in_the_convention_is_refused():
    for text in ('兄が本を読んでみた。', '兄が本を読んでみる。', '母が窓を開けてある。'):
        assert BASE.read(text, 'ja', placement=None)['readable'] is True
        assert last_reason(text).startswith('ASPECT_NOT_IN_CONVENTION:'), text
        assert R.w1a5_explain_ja(text)['path'] == 'aspect_refused'
    assert SR.read('兄が本を読んでみた。', 'ja', placement=None)['abstain']['kind'] == 'not_supported'


def test_the_gate_2_a_chain_behind_the_auxiliary_is_refused():
    for text in ('兄が本を読んでしまっている。', '兄が本を読んでしまっていた。'):
        assert last_reason(text) == 'ASPECT_CHAIN_NOT_READ', text


def test_the_gate_3_an_ending_that_is_not_in_the_table_is_refused():
    assert last_reason('兄が本を読んでいろ。') == 'ASPECT_ENDING_NOT_READ'


def test_the_gate_4_a_contracted_form_followed_by_a_negation_is_refused_and_the_other_contracted_forms_are_left_as_the_base_has_them():
    assert last_reason('兄が本を読んじゃわなかった。') == 'ASPECT_CONTRACTED_NEGATION'
    for text in ('兄が本を読んでる。', '兄が本を読んじゃった。'):
        assert SR.read(text, 'ja', placement=None) == BASE.read(text, 'ja', placement=None)
        assert R.w1a5_explain_ja(text)['path'] == 'not_triggered'
    assert last_reason('兄が本を三回読んでる。') == 'ASPECT_CONTRACTED'
    text = '兄がゆっくり本を読んでる。'                      # round 2: an adverb is not a trigger any more, so a contracted form behind it is the base's
    assert SR.read(text, 'ja', placement=None) == BASE.read(text, 'ja', placement=None) and R.w1a5_explain_ja(text)['path'] == 'not_triggered'


def _fake_base(clauses, relations=()):
    def base(text, placement=None):
        return SR._answer('ja', [dict(c) for c in clauses], list(relations), [{'rule': 'frame', 'span': [0, 1]} for _ in clauses], [])
    return base


def _clause(pred, roles, pol='+', tense='past'):
    return {'predicate': pred, 'roles': dict(roles), 'polarity': pol, 'tense': tense, 'modality': None, 'voice': 'active'}


def test_the_gate_5_a_chain_in_an_output_of_two_clauses_is_refused_only_when_it_is_not_in_the_table_or_it_is_followed_by_a_negation():
    two = [_clause('読む', {'agent': '兄', 'patient': '本'}), _clause('書く', {'agent': '母', 'patient': '手紙'})]
    rel = [{'type': 'sequence', 'from': 0, 'to': 1}]
    w = R.w1a5_wrap(_fake_base(two, rel))
    for text in ('兄が本を読んでみて、母が手紙を書いた。', '兄が本を読んでいなくて、母が手紙を書いた。'):
        out = w(text, None)
        assert out['readable'] is False and out['abstain']['reasons'][-1] == 'ASPECT_MULTI_CLAUSE', out
    text = '兄が本を読んでいる。母が手紙を書いた。'
    out = w(text, None)
    assert out['readable'] is True and out['clauses'] == two


def test_the_gate_6_a_chain_that_is_not_on_the_predicate_of_a_single_clause_is_refused():
    one = [_clause('来る', {'agent': '兄'})]
    out = R.w1a5_wrap(_fake_base(one))('兄が来て本を読んでいる。', None)
    assert out['readable'] is False and out['abstain']['reasons'][-1] == 'ASPECT_NOT_ON_PREDICATE', out


def test_a_chain_after_a_ない_で_is_not_a_chain_and_the_base_output_is_the_same_object():
    text = '兄が本を読まないでいる。'
    base = SR._read_ja.__wrapped__(text, None)
    seen = []
    def spy(t, placement=None):
        seen.append(base); return base
    assert R.w1a5_wrap(spy)(text, None) is base


# ------------------------------------------------------------------------------------------------ 9. the floating quantity
QTY_READ = [
    ('兄が本を一冊読んだ。', {'patient': 'exactly:1'}), ('兄が本を十冊読んだ。', {'patient': 'exactly:10'}), ('兄が本を三十冊読んだ。', {'patient': 'exactly:30'}),
    ('兄が本を三十五冊読んだ。', {'patient': 'exactly:35'}), ('兄が本を百冊集めた。', {'patient': 'exactly:100'}), ('兄が本を百五冊集めた。', {'patient': 'exactly:105'}),
    ('兄が本を百二十冊集めた。', {'patient': 'exactly:120'}), ('兄が本を千冊集めた。', {'patient': 'exactly:1000'}), ('兄が本を千二百冊集めた。', {'patient': 'exactly:1200'}),
    ('兄が本を二万冊集めた。', {'patient': 'exactly:20000'}), ('兄が本を一万二千冊集めた。', {'patient': 'exactly:12000'}), ('兄が本を十万冊集めた。', {'patient': 'exactly:100000'}),
    ('兄が本を３冊読んだ。', {'patient': 'exactly:3'}), ('兄が本を3冊読んだ。', {'patient': 'exactly:3'}), ('母が卵を２個割った。', {'patient': 'exactly:2'}),
    ('兄が本を一回読んだ。', {'event': 'exactly:1'}), ('兄が本を十回読んだ。', {'event': 'exactly:10'}), ('兄が本を3回読んだ。', {'event': 'exactly:3'}),
    ('学生が三人来た。', {'agent': 'exactly:3'}), ('兄は京都に三度来た。', {'event': 'exactly:3'}), ('兄が三回走った。', {'event': 'exactly:3'}),
]


@pytest.mark.parametrize('text,quant', QTY_READ, ids=[t for t, _ in QTY_READ])
def test_a_floating_quantity_is_written_with_the_key_the_convention_gives_and_the_counter_is_not_in_the_value(text, quant):
    out = SR.read(text, 'ja', placement=None)
    ex = R.w1a5_explain_ja(text)
    assert (ex['quantity']['counter'] in R.W1A5_EVENT_COUNTERS) == (list(quant)[0] == 'event')
    if list(quant)[0] != 'event':
        # round 2 (K218): the quantity of a noun phrase is not written; the entry abstains, the reason of the base entry is kept and the reason of K218 is added behind it
        base = BASE.read(text, 'ja', placement=None)
        assert not out['readable'] and not base['readable']
        assert out['abstain']['reasons'][-1] == 'QUANTIFIER_TARGET_UNDETERMINED:noun_phrase' and out['abstain']['reasons'][:-1] == base['abstain']['reasons']
        assert out['abstain']['kind'] == base['abstain']['kind'] and ex['path'] == 'reread_refused'
        assert ex['quantity']['value'] == list(quant.values())[0] and ex['quantity']['key'] is None      # the value of the numerals is still converted and checked
        return
    c = clause_of(out)
    assert c['quantifiers'] == quant and 'flags' not in c
    assert all(not any(ch in v for ch in '冊個人回度') for v in c['roles'].values()), c['roles']
    assert R.w1a5_explain_ja(text)['quantity']['value'] == list(quant.values())[0]
    key = list(quant)[0]
    assert key == 'event' or key in c['roles']


NOT_TRIGGERED = 'NOT_TRIGGERED'      # round 2: the observation is pinned (the numeral is inside a role of the base reading, or the clause is not the one of the trigger): W1-a5 does nothing
QTY_REFUSED = [
    ('兄が本を〇冊読んだ。', 'QUANTIFIER_VALUE_UNDETERMINED'), ('兄が本を数冊読んだ。', 'QUANTIFIER_VALUE_UNDETERMINED'), ('兄が本を二、三冊読んだ。', 'QUANTIFIER_VALUE_UNDETERMINED'),
    ('兄が本を三日読んだ。', 'QUANTIFIER_TARGET_UNDETERMINED:time'), ('兄が本を三年読んだ。', 'QUANTIFIER_TARGET_UNDETERMINED:time'), ('兄が本を三週間読んだ。', 'QUANTIFIER_TARGET_UNDETERMINED:time'),
    ('兄が三時間走った。', 'QUANTIFIER_TARGET_UNDETERMINED:time'), ('兄が牛乳を二リットル飲んだ。', 'QUANTIFIER_TARGET_UNDETERMINED:unit'), ('兄が車を三台買った。', 'QUANTIFIER_TARGET_UNDETERMINED:unit'),
    ('兄が温度を三度上げた。', 'QUANTIFIER_TARGET_UNDETERMINED:unit'), ('気温が三度下がった。', 'QUANTIFIER_TARGET_UNDETERMINED:unit'),
    ('兄が本を三冊も読んだ。', 'QUANTIFIER_TARGET_UNDETERMINED:position'), ('兄が本を三冊で読んだ。', NOT_TRIGGERED), ('兄が本を三回目に読んだ。', NOT_TRIGGERED),
    ('兄がりんごを弟に三個あげた。', 'QUANTIFIER_TARGET_UNDETERMINED:particle'), ('りんごを兄が三個食べた。', 'QUANTIFIER_TARGET_UNDETERMINED:scrambled'),
    ('兄が本を三冊読まなかった。', 'QUANTIFIER_SCOPE_UNDETERMINED:neg'), ('兄が本を三冊読んでいない。', 'QUANTIFIER_SCOPE_UNDETERMINED:neg'), ('兄が本を三回読んでいない。', 'QUANTIFIER_SCOPE_UNDETERMINED:neg'),
    ('兄が本を三冊読みたい。', 'REREAD_ABSTAINS'), ('兄が本を三冊読めた。', 'REREAD_ABSTAINS'), ('兄が本を三十冊と五冊読んだ。', NOT_TRIGGERED),
]


@pytest.mark.parametrize('text,reason', QTY_REFUSED, ids=[t for t, _ in QTY_REFUSED])
def test_a_quantity_the_rules_cannot_place_is_refused_with_the_reason_of_the_gate(text, reason):
    out = SR.read(text, 'ja', placement=None)
    rs = reasons(out)
    path = R.w1a5_explain_ja(text)['path']
    if reason == NOT_TRIGGERED:
        assert path == 'not_triggered' and out == BASE.read(text, 'ja', placement=None)
    else:
        assert rs[-1].startswith(reason), rs
        assert path == 'reread_refused'
    assert len(rs) >= 1


def test_a_quantity_with_a_numeral_inside_a_role_is_left_to_the_base_entry():
    for text in ('兄が三度本を読んだ。', '兄が三人の学生に会った。', '兄が三冊の本を読んだ。'):
        assert SR.read(text, 'ja', placement=None) == BASE.read(text, 'ja', placement=None)
        assert R.w1a5_explain_ja(text)['path'] == 'not_triggered'


def test_the_compound_words_that_hold_a_word_of_quantity_are_not_read_as_a_quantity():
    for text in ('兄が三日月を見た。', '兄が一緒に走った。', '兄が一人暮らしを始めた。', '兄が百貨店で買い物した。'):
        out = SR.read(text, 'ja', placement=None)
        assert out == BASE.read(text, 'ja', placement=None), text
        assert not out['readable'] or 'quantifiers' not in out['clauses'][0]


# ------------------------------------------------------------------------------------------------ 10. the mark of an adverb
ADV_MARKS = [
    ('兄が全然本を読んだ。', 'ADVERB_MARK_NOT_READ:neg:全然'), ('兄がもしも本を読んだ。', 'ADVERB_MARK_NOT_READ:cond:もし'), ('兄がよく本を読んだ。', 'ADVERB_MARK_NOT_READ:quant:よく'),
    ('兄がまた本を読んだ。', 'ADVERB_MARK_NOT_READ:conn:また'), ('兄がたぶん本を読んだ。', 'ADVERB_MARK_NOT_READ:modal:たぶん'), ('兄が多分本を読んだ。', 'ADVERB_MARK_NOT_READ:modal:多分'),
    ('兄が恐らく本を読んだ。', 'ADVERB_MARK_NOT_READ:modal:恐らく'), ('兄がきっと本を読んだ。', 'ADVERB_MARK_NOT_READ:modal:きっと'), ('兄がまだ本を読んだ。', 'ADVERB_MARK_NOT_READ:time_aspect:まだ'),
    ('兄がすでに本を読んだ。', 'ADVERB_MARK_NOT_READ:time_aspect:すでに'), ('兄が一番走った。', 'ADVERB_MARK_NOT_READ:convention:一番'), ('兄が最も走った。', 'ADVERB_MARK_NOT_READ:convention:最も'),
    ('兄がちょうど本を読んだ。', 'ADVERB_MARK_NOT_READ:convention:ちょうど'), ('兄がほぼ本を読んだ。', 'ADVERB_MARK_NOT_READ:approx:ほぼ'), ('兄がどうぞ本を読んだ。', 'ADVERB_MARK_NOT_READ:modal:どうぞ'),
    ('兄が少し走った。', 'ADVERB_MARK_NOT_READ:quant:少し'),
    # A2 .. A6
    ('兄がよりゆっくり走った。', 'COMPARISON_NOT_READ'), ('兄がくらいゆっくり走った。', 'COMPARISON_NOT_READ'),
    ('兄がゆっくりそっと窓を開けた。', 'ADVERB_STACKED'), ('兄がゆっくり、しかし本を読んだ。', 'ADVERB_STACKED'),
    ('兄がすぐ近くの店に行った。', 'ADVERB_MAY_MODIFY_NP:すぐ'), ('兄がすぐ隣の部屋に入った。', 'ADVERB_MAY_MODIFY_NP:すぐ'), ('兄がとても古い本を読んだ。', 'ADVERB_MAY_MODIFY_NP:とても'),
    ('兄がゆっくり古い本を読んだ。', 'ADVERB_MAY_MODIFY_NP:ゆっくり'),
    ('兄がゆっくり本を三冊読んだ。', 'ADVERB_WITH_QUANTITY'), ('兄がゆっくり三回読んだ。', 'ADVERB_WITH_QUANTITY'),
    ('兄がゆっくり本を読まなかった。', 'ADVERB_SCOPE_UNDETERMINED:neg'), ('兄がゆっくり本を読んでいない。', 'ADVERB_SCOPE_UNDETERMINED:neg'),
]


@pytest.mark.parametrize('text,reason', ADV_MARKS, ids=[t for t, _ in ADV_MARKS])
def test_an_adverb_the_rules_do_not_mark_is_refused_with_the_reason_of_the_gate(text, reason):
    # round 2 (K218): the mark of an adverb is withdrawn; an adverb that stays uncovered is no trigger, so the entry is the base entry and the reason of the gate is not added
    out = SR.read(text, 'ja', placement=None)
    assert not out['readable'] and R.w1a5_explain_ja(text)['path'] == 'not_triggered'
    assert out == BASE.read(text, 'ja', placement=None)
    assert reason not in out['abstain']['reasons']


ADV_READ = [
    ('兄がゆっくり本を読んだ。', ['ゆっくり']), ('兄が本をそっと置いた。', ['そっと']), ('兄がすぐに帰った。', ['すぐ']), ('兄がじっと空を見た。', ['じっと']),
    ('姉がちゃんと本を読んだ。', ['ちゃんと']), ('母がゆっくり部屋を掃除した。', ['ゆっくり']),
]


@pytest.mark.parametrize('text,flags', ADV_READ, ids=[t for t, _ in ADV_READ])
def test_an_adverb_that_passes_every_gate_is_marked_in_the_last_key_and_is_not_in_a_role(text, flags):
    # round 2 (K218): the mark is withdrawn; the sentence is the base entry's (an abstention) and the diagnosis has no adverb
    out = SR.read(text, 'ja', placement=None)
    assert not out['readable'] and out == BASE.read(text, 'ja', placement=None)
    ex = R.w1a5_explain_ja(text)
    assert ex['path'] == 'not_triggered' and ex['adverbs'] == []


def test_the_registered_words_of_the_small_classes_are_never_marked():
    toks_class = {}
    for cls, words in list(R.W1A5_ADVERB_CLASSES.items()) + [('convention', R.W1A5_CONVENTION_ADVERBS)]:
        for w in words: toks_class[w] = cls
    for w, cls in toks_class.items():
        text = '兄が%s本を読んだ。' % w
        out = SR.read(text, 'ja', placement=None)
        marked = out['readable'] and w in (out['clauses'][0].get('flags') or {}).get('adverbs', [])
        assert not marked, (w, out)
        adverbs = [t[0].surface for t in R._tokens(text) if t[0].feature.pos1 == '副詞']
        if w in adverbs and not out['readable'] and R.w1a5_explain_ja(text)['path'] != 'not_triggered':
            assert out['abstain']['reasons'][-1] == 'ADVERB_MARK_NOT_READ:%s:%s' % (cls, w), (w, out)


def test_an_adverb_the_tagger_does_not_call_an_adverb_is_not_marked():
    for text in ('兄が急に走った。', '兄が静かに走った。'):
        assert SR.read(text, 'ja', placement=None) == BASE.read(text, 'ja', placement=None)
        assert R.w1a5_explain_ja(text)['path'] == 'not_triggered'


# ------------------------------------------------------------------------------------------------ 11. the cross
def test_the_cross_refuses_the_key_flags_today_and_takes_the_key_quantifiers():
    seen = {'flags': 0, 'quantifiers': 0}
    for r in DATA:
        out = SR.read(r['input'], 'ja', placement=None)
        if not out['readable']: continue
        c = out['clauses'][0]
        cr = EC.build_crosses(out)
        if 'flags' in c:
            assert cr.status == 'INPUT_REJECTED' and cr.abstain['reasons'] == ['UNKNOWN_CLAUSE_KEY:flags'], r['id']; seen['flags'] += 1
        elif 'quantifiers' in c:
            assert cr.status == 'CROSSED', r['id']; seen['quantifiers'] += 1
    assert seen['flags'] == 0 and seen['quantifiers'] == 6


# ------------------------------------------------------------------------------------------------ 12. round 2 (K218): what was withdrawn stays withdrawn
MISREAD_BEFORE = [
    '学生が論文を三人書いた。', '客がケーキを五人食べた。', '子供たちが絵を三人描いた。', '学生は論文を三人書いた。', '論文を三人書いた。', '兄が三冊読んだ。', '母が五個買った。', '本は兄が三冊読んだ。',
    '手紙は姉が二通書いた。', '兄がおおかた家に帰った。', '兄がどうやら家に帰った。', '兄がたしか本を読んだ。', '兄がまさか本を読んだ。', '兄がさぞ喜んだ。',
]


def test_the_k218_reasons_table_is_the_constant():
    assert [cells(l)[0] for l in block('w1a5_reasons_k218')] == list(R.W1A5_REASONS_K218) == ['QUANTIFIER_TARGET_UNDETERMINED:noun_phrase']


def test_the_withdrawn_list_is_the_rule_applied_to_the_round_1_output():
    round1 = json.loads((TREE / 'artifacts' / 'w1-a5' / 'data_check_none.json').read_text(encoding='utf-8'))
    construction = {r['id']: r['construction'] for r in DATA}
    made = {}
    for x in round1:
        if x['adverbs']:
            made[x['id']] = ('adverb_mark', 'not_triggered', None, None)
        elif x['path'] == 'reread' and x['quantity'] and x['quantity']['counter'] not in ('回', '度'):
            made[x['id']] = ('noun_phrase_quantity', 'reread_refused', 'QUANTIFIER_TARGET_UNDETERMINED:noun_phrase', x['quantity']['value'])
    assert len(made) == len(WITHDRAWN) == 66 and list(made) == list(WITHDRAWN)
    for i, w in WITHDRAWN.items():
        assert (w['kind'], w['pinned_path'], w['pinned_reason'], w['round1_value']) == made[i], i
        assert w['construction'] == construction[i] and w['input'] == next(r['input'] for r in DATA if r['id'] == i)
    kinds = [w['kind'] for w in WITHDRAWN.values()]
    assert kinds.count('adverb_mark') == 50 and kinds.count('noun_phrase_quantity') == 16
    assert not any(w['input'] in MISREAD_BEFORE for w in WITHDRAWN.values())      # the 14 appended rows are not in the list: round 1 did not output them


def _outputs_of_the_data_and_of_the_entry_inputs():
    texts = [r['input'] for r in DATA] + _entry_inputs()
    for text in texts:
        yield text, SR.read(text, 'ja', placement=None)


def test_no_output_carries_flags_after_the_withdrawal():
    n = 0
    for text, out in _outputs_of_the_data_and_of_the_entry_inputs():
        if out['readable']:
            assert all('flags' not in c for c in out['clauses']), text; n += 1
        assert R.w1a5_explain_ja(text)['adverbs'] == [], text
    assert n > 0


def test_no_quantity_of_a_noun_phrase_is_read():
    n = 0
    for text, out in _outputs_of_the_data_and_of_the_entry_inputs():
        if out['readable']:
            for c in out['clauses']:
                if 'quantifiers' in c:
                    assert list(c['quantifiers']) == ['event'], text; n += 1
    assert n >= 6


def test_the_misread_sentences_of_round_1_and_of_the_plan_are_refused():
    assert len(MISREAD_BEFORE) == len(set(MISREAD_BEFORE)) == 14
    rows = {r['input']: r for r in DATA}
    for text in MISREAD_BEFORE:
        out = SR.read(text, 'ja', placement=None)
        assert not out['readable'], text
        assert rows[text]['behavior'] == 'abstain' and rows[text]['id'].startswith(('W1A5-QTY-A-9', 'W1A5-ADV-A-9')), text
        assert R.w1a5_explain_ja(text)['path'] in ('reread_refused', 'not_triggered')
