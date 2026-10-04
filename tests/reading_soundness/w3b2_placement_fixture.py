#!/usr/bin/env python3
"""W3-b2 step 5: the fixed placement answers for the tests, w3b2_placement_fixture.json.

Inputs: the four new data files, and the Japanese inputs of the data W3-b1 froze (ja_r8, ja_r9, ja_r10) and of the three B1 samples (the invariants of the control
flow are checked on them). Each input goes through the reader as it is (`document_view`; nothing is changed) and the words W3-b2 could ask about are collected as a
SUPERSET: the words of w3b1_placement_fixture.py (the surfaces and base forms of every token, every run of content tokens, the written predicate, the values of
the roles), and every window of consecutive tokens (up to 8) made only of content words and `の` with the part after each `の` (the head of an `X の Y`). The answers
are `coarse_place.query(word, placement=<dir>)` as they are (the placement path is not written; `frame_status` and `frame` are kept). A word the tests ask that is not
here is answered UNKNOWN by w3b2_fakes.FixtureQuery and recorded in `misses`.
Usage: cd <tree> && PYTHONPATH=<tree> python tests/reading_soundness/w3b2_placement_fixture.py --placement DIR [--out FILE]
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
import w3b2_common as C

_spec = importlib.util.spec_from_file_location('w3b1_placement_fixture_round1_for_w3b2', HERE / 'w3b1_placement_fixture.py')
B1F = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(B1F)
JA = re.compile('[぀-ヿ㐀-䶿一-鿿]')


def inputs():
    out = []
    for name in C.DATA:
        out += [r['input'] for r in C.load_data(name)]
    for name in ('ja_r8.jsonl', 'ja_r9.jsonl', 'ja_r10.jsonl'):
        out += [json.loads(l)['input'] for l in (HERE / name).read_text(encoding='utf-8').splitlines() if l.strip()]
    for fx in ('B1_v2', 'B1_v2_r2', 'B1_v2_r3'):
        out += [json.loads(l)['input'] for l in (TREE / 'tests' / 'bank_score' / 'fixtures' / fx / 'items.jsonl').read_text(encoding='utf-8').splitlines() if l.strip()]
    return [t for t in dict.fromkeys(out) if JA.search(t)]


def terms_of(text, R):
    terms = B1F.terms_of(text, R, lambda w: w)
    toks = R._tokens(text)
    ok = [t[0].feature.pos1 in R._CONTENT_WORDS or (t[0].surface == 'の' and t[0].feature.pos1 == '助詞') for t in toks]
    for i in range(len(toks)):
        for j in range(i + 1, min(len(toks), i + 8) + 1):
            if not all(ok[i:j]): break
            parts = [t[0].surface for t in toks[i:j]]
            terms.add(''.join(parts))
            for k, p in enumerate(parts):
                if p == 'の' and k + 1 < len(parts): terms.add(''.join(parts[k + 1:]))
    return {t for t in terms if isinstance(t, str) and t.strip()}


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--placement', required=True); ap.add_argument('--out', default=str(HERE / 'w3b2_placement_fixture.json'))
    a = ap.parse_args()
    from verantyx import coarse_place, semantic_reader as R, constructions
    constructions.discover()
    root, _ = C.isolation()
    print('tree=' + root)
    ins = inputs()
    terms = set()
    for text in ins: terms |= terms_of(text, R)
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
                     'note': 'coarse_place.query(term, placement=<run1>) の答えの抜粋(frame_status・frame つき)。配置のパスは書かない。テストの偽物 w3b2_fakes.FixtureQuery が使う'},
           'answers': answers}
    Path(a.out).write_text(json.dumps(doc, ensure_ascii=False, sort_keys=True, indent=0) + '\n', encoding='utf-8')
    print('inputs=%d terms=%d out=%s' % (len(ins), len(answers), a.out))


if __name__ == '__main__':
    main()
