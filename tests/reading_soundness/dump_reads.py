#!/usr/bin/env python3
"""W1-a2 X3: 文の集合を読解器(document_view)に通し、supported の節と unsupported の節(理由つき)を 1 行 1 文の JSON Lines に書く。

使い方: cd <木> && PYTHONPATH=<木> python <この木>/tests/reading_soundness/dump_reads.py --banks --extra FILE [FILE ...] --out OUT.jsonl
  --banks : 評価バンク(table7・ja・ja_r2・ja_r3・ja_r4・ja_r5・ja_r6。このファイルの隣から読む)の日本語の文
  --extra : 1 行 1 文のテキストファイル(複数可)
dev(基点)の木と修正後の木の両方で同じコマンドを流し、x3_compare.py で比べる。読み込んだ verantyx* が PYTHONPATH の木の配下か検査する(外れたら終了コード 2)。
"""
import argparse
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
BANKS = ('table7.jsonl', 'ja.jsonl', 'ja_r2.jsonl', 'ja_r3.jsonl', 'ja_r4.jsonl', 'ja_r5.jsonl', 'ja_r6.jsonl')


def sentences(use_banks, extra):
    out, seen = [], set()

    def add(text, source):
        if text and text not in seen:
            seen.add(text); out.append((text, source))
    if use_banks:
        for name in BANKS:
            for line in (HERE / name).read_text(encoding='utf-8').splitlines():
                if line.strip():
                    add(json.loads(line)['text'], name)
    for f in extra:
        for line in Path(f).read_text(encoding='utf-8').splitlines():
            if line.strip():
                add(line.strip(), Path(f).name)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--banks', action='store_true')
    ap.add_argument('--extra', nargs='*', default=[])
    ap.add_argument('--out', required=True)
    a = ap.parse_args()
    from verantyx.semantic_reader import document_view
    from verantyx import constructions
    constructions.discover()
    root = os.path.realpath(os.environ.get('PYTHONPATH', '.').split(os.pathsep)[0])
    foreign = [m.__file__ for k, m in list(sys.modules.items()) if (k == 'verantyx' or k.startswith('verantyx.'))
               and getattr(m, '__file__', None) and not os.path.realpath(m.__file__).startswith(root + os.sep)]
    print('tree=' + root)
    if foreign:
        print('ISOLATION FAILED', foreign); sys.exit(2)
    rows = []
    for text, source in sentences(a.banks, a.extra):
        view = document_view({'d': text})
        sup = [{'rule': c.rule, 'predicate': c.predicate, 'polarity': c.polarity, 'roles': [[r.name, r.span.text] for r in c.roles]}
               for c in view.clauses if not c.unsupported]
        uns = [{'rule': c.rule, 'predicate': c.predicate, 'roles': [[r.name, r.span.text] for r in c.roles], 'reasons': list(c.unsupported)}
               for c in view.clauses if c.unsupported]
        rows.append({'text': text, 'source': source, 'supported': sup, 'unsupported': uns, 'unread': [u.reason for u in view.unread]})
    Path(a.out).write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
    print(f'sentences={len(rows)} supported_sentences={sum(bool(r["supported"]) for r in rows)} out={a.out}')


if __name__ == '__main__':
    main()
