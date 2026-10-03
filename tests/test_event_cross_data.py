"""W3-b E2: the frozen test sentences (tests/event_cross/data), through `read_events` on the spot.

* a sentence the reader abstains on: status ABSTAINED, no cross, the reader's abstain copied (that is the expectation);
* a sentence the reader reads and that is not in reader_disagreements.json: the number of crosses, the centres, the arms (role -> surface)
  and the relations equal the HAND-WRITTEN expectation;
* a sentence in reader_disagreements.json (the reader read it and the expectation says otherwise): the crosses are a faithful copy of the
  reader's clauses (the cross layer does not repair the reader);
* every sentence: as many event relations as reader relations, arm names inside the closed list.
"""
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
DATA = HERE / 'event_cross' / 'data'
sys.path.insert(0, str(HERE / 'event_cross'))

import classify    # noqa: E402
from verantyx import event_cross as E    # noqa: E402

LANGS = ('ja', 'en')
SENT = {l: classify.load_all('sentences', l) for l in LANGS}
EXP = {e['id']: e for l in LANGS for e in classify.load_all('expected', l)}
ALL = [(l, s) for l in LANGS for s in SENT[l]]
DISAGREE = set(json.loads((DATA / 'reader_disagreements.json').read_text(encoding='utf-8')))
FROZEN = json.loads((DATA / 'FROZEN.json').read_text(encoding='utf-8'))
EIGHT = ('simple', 'complex', 'connective', 'negation', 'comparison', 'giving', 'passive', 'fronted_time_place')


def test_counts_tags_and_topics():
    for l in LANGS:
        rows = SENT[l]
        assert len(rows) >= 60 and len({r['id'] for r in rows}) == len(rows)
        tags = Counter(t for r in rows for t in r['tags'])
        assert all(tags[t] >= 6 for t in EIGHT), (l, tags)
        assert tags['explain'] >= 12 and tags['unreadable'] >= 4, (l, tags)
        assert len({r['topic'] for r in rows}) >= 6
    assert set(EXP) == {s['id'] for _, s in ALL}


def test_no_sentence_is_shared_with_the_existing_test_banks():
    existing = set()

    def strings(x):
        if isinstance(x, str): yield x
        elif isinstance(x, dict):
            for v in x.values(): yield from strings(v)
        elif isinstance(x, list):
            for v in x: yield from strings(v)
    tree = HERE.parent
    paths = list((tree / 'tests' / 'reading_soundness').glob('*.jsonl')) + list((tree / 'tests' / 'bank_score' / 'fixtures').rglob('*.jsonl'))
    for p in paths:
        for line in p.read_text(encoding='utf-8').splitlines():
            if line.strip():
                try: existing.update(s.strip() for s in strings(json.loads(line)))
                except ValueError: pass
    mine = [s['text'] for _, s in ALL]
    assert len(paths) > 10 and [t for t in mine if t in existing] == []
    assert len(set(mine)) == len(mine)


def test_frozen_files_still_have_the_recorded_hashes():
    def sha(name): return hashlib.sha256((DATA / name).read_bytes()).hexdigest()
    for group in ('sentences', 'expected', 'sentences_add1', 'expected_add1'):
        files = {k: v for k, v in FROZEN[group].items() if k != 'frozen_at'}
        assert files, group
        for name, digest in files.items():
            assert sha(name) == digest, (group, name)
    names = {p.name for p in DATA.glob('sentences_*.jsonl')} | {p.name for p in DATA.glob('expected_*.jsonl')}
    recorded = {k for g in ('sentences', 'expected', 'sentences_add1', 'expected_add1') for k in FROZEN[g] if k != 'frozen_at'}
    assert names == recorded           # no data file escapes the freeze list


def test_the_frozen_disagreement_list_is_what_the_classifier_finds():
    found = set()
    for l, s in ALL:
        got = E.read_events(s['text'])
        exp = EXP[s['id']]
        if not got['readable']: continue
        if not exp['readable'] or not classify.agrees(exp, got)[0]: found.add(s['id'])
    assert found == DISAGREE


@pytest.mark.parametrize('lang,sent', ALL, ids=[s['id'] for _, s in ALL])
def test_sentence(lang, sent):
    got = E.read_events(sent['text'])
    ev, exp = got['events'], EXP[sent['id']]
    assert list(got)[-1] == 'events' and ev['schema'] == 'verantyx.event_cross/1'
    assert len(ev['relations']) == len(got['relations'])
    assert ev['relations'] == got['relations']
    for cross in ev['crosses']:
        assert list(cross['arms']) == [r for r in E.ROLE_NAMES if r in cross['arms']]       # inside the closed list, in its order
    if not got['readable']:
        assert ev['status'] == 'ABSTAINED' and ev['crosses'] == [] and ev['relations'] == [] and ev['abstain'] == got['abstain']
        return
    assert ev['status'] == 'CROSSED' and ev['abstain'] is None and len(ev['crosses']) == len(got['clauses'])
    for cross, clause, meta in zip(ev['crosses'], got['clauses'], got['clause_meta']):       # a faithful copy of the reader's clause
        assert cross['center'] == {k: v for k, v in clause.items() if k != 'roles'}
        assert {r: a['fillers'][0]['surface'] for r, a in cross['arms'].items()} == clause['roles']
        assert all(a['kind'] == 'FILLER' and len(a['fillers']) == 1 for a in cross['arms'].values())
        assert cross['provenance']['rule'] == meta['rule'] and cross['provenance']['span'] == meta['span']
    if sent['id'] in DISAGREE:
        return                                   # the reader's reading is copied as it is; it is not compared with the expectation
    assert exp['readable'] is True
    assert len(ev['crosses']) == len(exp['crosses'])
    for cross, want in zip(ev['crosses'], exp['crosses']):
        for k, v in want['center'].items():
            assert cross['center'].get(k) == v, (sent['id'], k)
        assert {r: a['fillers'][0]['surface'] for r, a in cross['arms'].items()} == want['arms']
    key = lambda r: (r['type'], r['from'], r['to'])
    assert sorted(map(key, ev['relations'])) == sorted(map(key, exp['relations']))
