#!/usr/bin/env python3
"""W3-b3 step 4: the fixed placement answers for the tests, w3b3_placement_fixture.json.

Inputs: the four new data files, the sentences of w3b3_test_inputs.txt (the sentences the tests use that are not data rows), and the Japanese inputs of the data W3-b1 / W3-b2
froze and of the three B1 samples (the invariants of the control flow are checked on them). The words the new path could ask about are collected as a SUPERSET, as W3-b2 did
(w3b2_placement_fixture.terms_of: the surfaces and base forms of every token, every run of content tokens, the written predicate, the values of the roles, every window
of consecutive tokens (up to 8) made only of content words and の, with the part after each の). A clause of the new path is made of tokens of the sentence (or of the base form
of one), so the words it asks are among these. The answers are `coarse_place.query(word, placement=<dir>)` as they are (the placement path is not written). A word the tests ask
that is not here is answered UNKNOWN by w3b3_fakes.FixtureQuery and recorded in `misses`.
Usage: cd <tree> && PYTHONPATH=<tree> python tests/reading_soundness/w3b3_placement_fixture.py --placement DIR [--out FILE]
"""
import argparse
import importlib.util
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
TREE = HERE.parent.parent
sys.path.insert(0, str(HERE))
import w3b3_common as C

_spec = importlib.util.spec_from_file_location('w3b2_placement_fixture_for_w3b3', HERE / 'w3b2_placement_fixture.py')
B2F = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(B2F)
JA = re.compile('[぀-ヿ㐀-䶿一-鿿]')


def test_inputs():
    return [l.strip() for l in (HERE / 'w3b3_test_inputs.txt').read_text(encoding='utf-8').splitlines() if l.strip() and not l.startswith('#')]


def inputs():
    out = []
    for name in C.DATA_ALL:
        out += [r['input'] for r in C.load_data(name)]
    out += test_inputs()
    out += B2F.inputs()
    return [t for t in dict.fromkeys(out) if JA.search(t)]


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--placement', required=True); ap.add_argument('--out', default=str(HERE / 'w3b3_placement_fixture.json'))
    a = ap.parse_args()
    from verantyx import coarse_place, semantic_reader as R, constructions
    constructions.discover()
    root, _ = C.isolation()
    print('tree=' + root)
    ins = inputs()
    terms = set()
    for text in ins: terms |= B2F.terms_of(text, R)
    answers, sha = {}, None
    for t in sorted(terms):
        ans = coarse_place.query(t, placement=a.placement)
        pl = ans.get('placement') or {}
        sha = sha or pl.get('content_sha256')
        answers[t] = {'term': ans['term'], 'namespace': ans.get('namespace'), 'state': ans['state'], 'origin': ans['origin'],
                      'estimate_basis': ans['estimate_basis'], 'constructed': ans['constructed'], 'top': ans['top'],
                      'decided_by': ans.get('decided_by'), 'generated': ans.get('generated'), 'generated_definition': ans.get('generated_definition'),
                      'frame_status': ans.get('frame_status'), 'frame': ans.get('frame'),
                      'placement': {'content_sha256': pl.get('content_sha256'), 'reason': pl.get('reason')}}
    doc = {'_meta': {'inputs': len(ins), 'terms': len(answers), 'content_sha256': sha,
                     'note': 'coarse_place.query(term, placement=<run1>) の答えの抜粋(frame_status・frame つき)。配置のパスは書かない。テストの偽物 w3b3_fakes.FixtureQuery が使う'},
           'answers': answers}
    Path(a.out).write_text(json.dumps(doc, ensure_ascii=False, sort_keys=True, indent=0) + '\n', encoding='utf-8')
    print('inputs=%d terms=%d out=%s' % (len(ins), len(answers), a.out))


if __name__ == '__main__':
    main()
