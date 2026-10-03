"""W3-b1-5 (integration of W3-b1 with W5-a, base commit 2732274): the cause of each declared row is attributed to the right change (I3, read off the output, not off the generator).

A declared row whose output differs between the merged tree and the W3-b1 tree alone (f410469, the same fixed placement) is caused by W5-a (docs section 10A K62-K64, NOT the
K62-K66 of section 10), so its `why` must say W5-a and the right `section 10A K6x`, and must not name the W3-b1 table change record (the earlier mix-up, review round 4 M1).
A row that does not differ must not name W5-a. The closed table of W5-a's reasons is read from the generator by its path and checked against the docs section 10A.

Placement answers come from fakes (tests/reading_soundness/w3b1_fakes.py); no real placement is opened. Run under a clean environment (env -i).
"""
import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

TREE = Path(__file__).resolve().parent.parent
RS = TREE / 'tests' / 'reading_soundness'
ART = TREE / 'artifacts' / 'w3-b1'


def _load_by_path(name, path):
    """Load a helper module by its path under a unique name (sys.path is restored; see test_semantic_read_w3b1.py)."""
    if name in sys.modules: return sys.modules[name]
    saved = list(sys.path)
    try:
        spec = importlib.util.spec_from_file_location(name, str(path))
        mod = importlib.util.module_from_spec(spec)
        sys.modules[name] = mod
        spec.loader.exec_module(mod)
    finally:
        sys.path[:] = saved
    return mod


F = _load_by_path('w3b1_fakes', RS / 'w3b1_fakes.py')
MK = _load_by_path('w3b1_mk_exceptions_i5', RS / 'w3b1_mk_exceptions.py')

from verantyx import semantic_read as SR    # noqa: E402

DOCS = (TREE / 'docs' / 'READING_SOUNDNESS.md').read_text(encoding='utf-8')
W3B1_COMMIT, PRE_W5A_COMMIT, BASE_COMMIT = 'f410469', '0ff3f35', '2732274'
FORBIDDEN = 'table change record'


def _module_at(commit):
    src = subprocess.run(['git', '-C', str(TREE), 'show', '%s:verantyx/semantic_read.py' % commit], capture_output=True, check=True).stdout
    spec = importlib.util.spec_from_loader('verantyx._semantic_read_at_%s_w3b1_i5t' % commit, loader=None)
    mod = importlib.util.module_from_spec(spec)
    mod.__package__ = 'verantyx'
    sys.modules[spec.name] = mod
    exec(compile(src.decode('utf-8'), 'verantyx/semantic_read.py@%s' % commit, 'exec'), mod.__dict__)
    return mod


W3B1 = _module_at(W3B1_COMMIT)
PRE = _module_at(PRE_W5A_COMMIT)
B27 = _module_at(BASE_COMMIT)

DECLARED = json.loads((RS / 'w3b1_expect_exceptions.json').read_text(encoding='utf-8'))['exceptions']
LANG = {}
for _name in ('ja_r8.jsonl', 'en_r4.jsonl'):
    for _line in (RS / _name).read_text(encoding='utf-8').splitlines():
        _r = json.loads(_line)
        LANG[_r['id']] = _r['lang']


def _rule_k(first_reason):
    """The section 10A K of the generator's closed table that the first reason belongs to (exactly one), or None."""
    hits = [text for k, text in MK.W5A_RULES if first_reason == k or (k.endswith(':') and first_reason.startswith(k))]
    if len(hits) != 1: return None
    m = re.search(r'section 10A (K\d+)', hits[0])
    return m.group(1) if m else None


def _differs(e):
    """(differs, out, alone) for a declared row: the merged tree's output vs the W3-b1 tree alone, both with the fixed placement."""
    lang = LANG[e['id']]
    out = SR.read(e['input'], lang, placement=F.FixtureQuery())
    alone = W3B1.read(e['input'], lang, placement=F.FixtureQuery())
    return out != alone, out, alone


def attribution_problems(e, differs, out):
    """What is wrong with the attribution of one declared row's `why` (an empty list when it is right)."""
    why = e['why']
    bad = []
    if differs:
        k = _rule_k(out['abstain']['reasons'][0]) if not out['readable'] else None
        if k is None: bad.append('the first reason is not in the closed table of W5-a reasons')
        if 'W5-a' not in why: bad.append('does not say W5-a')
        if k is not None and 'section 10A %s' % k not in why: bad.append('does not name section 10A %s' % k)
        if k is not None:
            others = [x for x in re.findall(r'section 10A (K\d+)', why) if x != k]
            if others: bad.append('names another section 10A K: %s' % others)
        if FORBIDDEN in why: bad.append('names a W3-b1 table change record')
    else:
        if 'W5-a' in why or 'section 10A' in why: bad.append('names W5-a although the output does not differ from the W3-b1 tree alone')
    return bad


def test_a_declared_row_names_W5a_and_its_section_10A_K_exactly_when_the_output_differs_from_the_W3b1_tree_alone():
    assert DECLARED
    for e in DECLARED:
        differs, out, _alone = _differs(e)
        assert attribution_problems(e, differs, out) == [], (e['id'], attribution_problems(e, differs, out))


def test_a_row_that_differs_is_the_base_commits_own_output_and_the_W3b1_tree_alone_gave_the_commit_before_W5a():
    rows = []
    for e in DECLARED:
        differs, out, alone = _differs(e)
        if not differs: continue
        rows.append(e['id'])
        lang = LANG[e['id']]
        assert out == SR.read(e['input'], lang, placement=None) == B27.read(e['input'], lang), e['id']
        assert out['readable'] is False and len(out['abstain']['reasons']) == 1, e['id']
        assert alone == PRE.read(e['input'], lang), e['id']
        assert e['observed'] == {'readable': False, 'reasons': out['abstain']['reasons']}, e['id']
    assert rows, 'no declared row differs from the W3-b1 tree alone: the check is empty'


def test_the_check_catches_the_old_attribution_of_the_rows_W5a_changed():
    """The `why` of round 4 (before the merge) of every row that now differs is refused by the check (a check that passes on anything is no check)."""
    old = {e['id']: e for e in json.loads((ART / 'r4_w3b1_expect_exceptions.json').read_text(encoding='utf-8'))['exceptions']}
    caught = 0
    for e in DECLARED:
        differs, out, _alone = _differs(e)
        if not differs: continue
        assert attribution_problems(dict(e, why=old[e['id']]['why']), differs, out), e['id']
        assert attribution_problems(dict(e, why=e['why'].replace('W5-a', 'W3-b1')), differs, out), e['id']
        assert attribution_problems(dict(e, why=e['why'] + ' (table change record 3)'), differs, out), e['id']
        caught += 1
    assert caught >= 1


def test_the_closed_table_of_W5a_reasons_is_registered_in_docs_section_10A():
    head = DOCS.index('\n## 10A.')
    section = DOCS[head:]
    seen = set()
    for key, text in MK.W5A_RULES:
        k = re.search(r'section 10A (K\d+)', text).group(1)
        seen.add(k)
        m = re.search(r'^### %s[（( ]' % k, section, flags=re.M)
        assert m, k
        nxt = re.search(r'^### K', section[m.end():], flags=re.M)
        body = section[m.start(): m.end() + (nxt.start() if nxt else len(section))]
        assert key.rstrip(':') in body, (key, k)
    assert len(seen) == len(MK.W5A_RULES)


def test_the_generators_commits_are_the_ones_this_test_asks_about():
    assert (MK.W3B1_COMMIT, MK.PRE_W5A_COMMIT, MK.BASE_COMMIT) == (W3B1_COMMIT, PRE_W5A_COMMIT, BASE_COMMIT)
