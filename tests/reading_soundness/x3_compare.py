#!/usr/bin/env python3
"""W1-a2 X3: 基点 dev(191db17) と修正後の読みを比べ、「修正後に新しく対応済みになった (役割, 値)」を 1 件ずつ表にする。

使い方: python x3_compare.py --dev DEV.jsonl --after AFTER.jsonl [--gold-harness soundness_after.json] [--classified TSV] --out OUT.tsv
  入力は dump_reads.py の出力。修正後の supported の節の (役割, 値) で、dev の supported の節に同じ組が無いものを 1 行ずつ出す:
    ROLE_CHANGED     : dev の supported でも同じ値があるが別の役割だった(例 recipient -> direction)
    NEWLY_SUPPORTED  : dev では値が supported の節に無かった(未対応だった・別の節だった)
  判定(label):
    正解のある文(--gold-harness の評価バンク)は harness の結果で自動: correct -> CORRECT、misread -> MISREAD、未対応 -> CORRECT(対象節がどれも正解に一致)。
    正解の無い文は --classified(sentence <TAB> role <TAB> value <TAB> label)の手分類。label は IMPROVED(dev より正しい)・CORRECT(正しい)・
    REGRESSED(dev は正しく、いまは誤り)・WRONG(誤り。基点では正しかった組でも、基点に無かった新しい誤りでもない、と判断できないもの)・
    STILL_WRONG(基点でも同じ文が誤って読まれ、いまも誤りが残る。新しい誤読ではない。数えて表に残し、終了コードには数えない。第 2 ラウンドで足した)。
  未分類が 1 行でもあれば終了コード 1。REGRESSED + WRONG + MISREAD が 0 なら 0、そうでなければ 1(未分類が先)。
"""
import argparse
import collections
import json
import sys
from pathlib import Path


def load(path):
    return {r['text']: r for r in (json.loads(l) for l in Path(path).read_text(encoding='utf-8').splitlines() if l.strip())}


def pairs(row):
    return {(name, value) for c in row['supported'] for name, value in c['roles']}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dev', required=True); ap.add_argument('--after', required=True)
    ap.add_argument('--gold-harness'); ap.add_argument('--classified'); ap.add_argument('--out', required=True)
    a = ap.parse_args()
    dev, after = load(a.dev), load(a.after)
    gold = {}
    if a.gold_harness:
        for r in json.load(open(a.gold_harness, encoding='utf-8'))['sentences']:
            gold[r['text']] = r['result']
    manual = {}
    if a.classified:
        for line in Path(a.classified).read_text(encoding='utf-8').splitlines():
            if line.strip() and not line.startswith('#'):
                cols = line.split('\t')
                if len(cols) >= 4: manual[(cols[0], cols[1], cols[2])] = cols[3]
    rows = []
    for text, row in after.items():
        before = pairs(dev[text]) if text in dev else set()
        before_by_value = collections.defaultdict(set)
        for name, value in before: before_by_value[value].add(name)
        for name, value in sorted(pairs(row) - before):
            kind = 'ROLE_CHANGED' if value in before_by_value else 'NEWLY_SUPPORTED'
            if text in gold:
                label = {'correct': 'CORRECT', 'misread': 'MISREAD', 'unsupported': 'CORRECT'}[gold[text]]; how = 'harness'
            else:
                label = manual.get((text, name, value), 'UNCLASSIFIED'); how = 'manual'
            rows.append((text, name, value, kind, '/'.join(sorted(before_by_value.get(value, ()))) or '-', label, how, row['source']))
    out = ['\t'.join(('sentence', 'role', 'value', 'kind', 'dev_role', 'label', 'how', 'source'))] + ['\t'.join(r) for r in rows]
    Path(a.out).write_text('\n'.join(out) + '\n', encoding='utf-8')
    count = collections.Counter(r[5] for r in rows)
    kinds = collections.Counter(r[3] for r in rows)
    bad = count['REGRESSED'] + count['WRONG'] + count['MISREAD']
    print(f"rows={len(rows)} kinds={dict(kinds)} labels={dict(count)}")
    print(f"unclassified={count['UNCLASSIFIED']} regressed={count['REGRESSED']} wrong={count['WRONG']} misread={count['MISREAD']} still_wrong(not new)={count['STILL_WRONG']}")
    sys.exit(1 if (count['UNCLASSIFIED'] or bad) else 0)


if __name__ == '__main__':
    main()
