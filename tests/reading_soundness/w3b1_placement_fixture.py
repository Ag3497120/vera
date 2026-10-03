#!/usr/bin/env python3
"""W3-b1 手順 5: テスト用の固定の配置の答え w3b1_placement_fixture.json を作る。

入力 = 新データ(ja_r8・en_r4)と B1 見本 3 本の `input`。各入力を基点のままの読解器(document_view。読解器は変えない)に通し、次の語を集める:
  節の述語と書かれた述語、役割の値(`_strip_demonstrative` 後)、覆われていない内容語の連なり(すべての部分連なり)、全トークンの表層と原形、
  英語は全単語の `en.lemma`。各語を `coarse_place.query(語, placement=<配置>)` に聞き、答えの state・origin・estimate_basis・constructed・top・decided_by・
  generated・namespace・content_sha256(配置のパスは消す)だけを鍵で並べ替えて書く。
使い方: cd <木> && PYTHONPATH=<木> python tests/reading_soundness/w3b1_placement_fixture.py --placement DIR [--out FILE]
読み込んだ verantyx* が PYTHONPATH の木の配下か検査する(外れたら終了コード 2)。
"""
import argparse, json, os, re, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
TREE = HERE.parent.parent


def inputs():
    out = []
    for name in ('ja_r8.jsonl', 'en_r4.jsonl'):
        for line in (HERE / name).read_text(encoding='utf-8').splitlines():
            if line.strip(): out.append(json.loads(line)['input'])
    for fx in ('B1_v2', 'B1_v2_r2', 'B1_v2_r3'):
        for line in (TREE / 'tests' / 'bank_score' / 'fixtures' / fx / 'items.jsonl').read_text(encoding='utf-8').splitlines():
            if line.strip(): out.append(json.loads(line)['input'])
    return list(dict.fromkeys(out))


def terms_of(text, R, en_lemma):
    terms = set()
    if not re.search('[぀-ヿ㐀-䶿一-鿿]', text):
        for w in re.findall(r"[A-Za-z][A-Za-z'\-]*", text):
            terms.add(w.lower()); terms.add(en_lemma(w))
        return terms
    from verantyx.semantic_read import _strip_demonstrative, _written_predicate
    toks = R._tokens(text)
    for w, a, b in toks:
        terms.add(w.surface); terms.add(R._base(w))
    run = []
    for t in toks + [None]:
        if t is not None and t[0].feature.pos1 in R._CONTENT_WORDS:
            run.append(t); continue
        for i in range(len(run)):
            for j in range(i + 1, len(run) + 1):
                terms.add(''.join(x[0].surface for x in run[i:j]))
        run = []
    view = R.document_view({'d': text})
    for c in view.clauses:
        terms.add(c.predicate)
        pred_i = next((i for i, (w, a, b) in enumerate(toks) if a == c.predicate_span.start), None)
        written = _written_predicate(toks, pred_i)
        if written: terms.add(written)
        for r in c.roles:
            v = _strip_demonstrative(r, toks)
            if v: terms.add(v)
    return {t for t in terms if isinstance(t, str) and t.strip()}


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--placement', required=True); ap.add_argument('--out', default=str(HERE / 'w3b1_placement_fixture.json'))
    a = ap.parse_args()
    from verantyx import coarse_place, semantic_reader as R, en_frames
    from verantyx import constructions
    constructions.discover()
    root = os.path.realpath(os.environ.get('PYTHONPATH', '.').split(os.pathsep)[0])
    foreign = [m.__file__ for k, m in list(sys.modules.items()) if (k == 'verantyx' or k.startswith('verantyx.'))
               and getattr(m, '__file__', None) and not os.path.realpath(m.__file__).startswith(root + os.sep)]
    print('tree=' + root)
    if foreign: print('ISOLATION FAILED', foreign); sys.exit(2)
    ins = inputs()
    terms = set()
    for text in ins: terms |= terms_of(text, R, en_frames.lemma)
    answers, sha = {}, None
    for t in sorted(terms):
        ans = coarse_place.query(t, placement=a.placement)
        pl = ans.get('placement') or {}
        sha = sha or pl.get('content_sha256')
        answers[t] = {'term': ans['term'], 'namespace': ans.get('namespace'), 'state': ans['state'], 'origin': ans['origin'],
                      'estimate_basis': ans['estimate_basis'], 'constructed': ans['constructed'], 'top': ans['top'],
                      'decided_by': ans.get('decided_by'), 'generated': ans.get('generated'), 'generated_definition': ans.get('generated_definition'),
                      'placement': {'content_sha256': pl.get('content_sha256'), 'reason': pl.get('reason')}}
    doc = {'_meta': {'inputs': len(ins), 'terms': len(answers), 'content_sha256': sha,
                     'note': 'coarse_place.query(term, placement=<run1>) の答えの抜粋。配置のパスは書かない。テストの偽物 FixtureQuery が使う'},
           'answers': answers}
    Path(a.out).write_text(json.dumps(doc, ensure_ascii=False, sort_keys=True, indent=0) + '\n', encoding='utf-8')
    print('inputs=%d terms=%d out=%s' % (len(ins), len(answers), a.out))


if __name__ == '__main__':
    main()
