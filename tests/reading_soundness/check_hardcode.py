#!/usr/bin/env python3
"""A6: 修正が入力文の決め打ちでないことの機械検査。

全評価文(table7・ja・en・a3)から固有の語を集め、`git diff 075d486 -- verantyx/` の追加行に現れるかを調べる。
  - 失敗(終了コード 1): 日本語の 固有名詞 トークン、数字/英字を含むトークン、英語の文頭以外の大文字語が追加行に現れた。
  - 一覧のみ: 普通名詞(2 文字以上)・動詞の基本形・英語の小文字語が追加行に現れた(判断記録で 1 件ずつ説明する)。
使い方: cd <木> && PYTHONPATH=<木> python tests/reading_soundness/check_hardcode.py [--base 075d486]
"""
import argparse, json, re, subprocess, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def sentences():
    out = []
    for f in ('table7.jsonl', 'ja.jsonl', 'ja_r2.jsonl', 'en.jsonl', 'en_r2.jsonl', 'a3.jsonl', 'a3_r2.jsonl', 'ja_r3.jsonl', 'a3_r3.jsonl', 'ja_r4.jsonl', 'a3_r4.jsonl', 'ja_r5.jsonl', 'a3_r5.jsonl', 'ja_r6.jsonl'):
        for line in (HERE / f).read_text(encoding='utf-8').splitlines():
            if line.strip():
                r = json.loads(line); out.append(r['text'])
                if 'question' in r: out.append(r['question'])
    return out


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--base', default='075d486'); ap.add_argument('--repo', default='.')
    a = ap.parse_args()
    diff = subprocess.run(['git', '-C', a.repo, 'diff', a.base, '--', 'verantyx/'], capture_output=True, text=True, check=True).stdout
    added = [l[1:] for l in diff.splitlines() if l.startswith('+') and not l.startswith('+++')]
    blob = '\n'.join(added)
    from verantyx.typed_edges import _tagger, _base
    proper, common, verbs, english_names, english_words = set(), set(), set(), set(), set()
    for text in sentences():
        if re.search(r'[A-Za-z]{3,}', text) and not re.search(r'[ぁ-んァ-ヶ一-龥]', text):
            words = re.findall(r"[A-Za-z][A-Za-z'\-]*", text)
            for i, w in enumerate(words):
                if i > 0 and w[0].isupper(): english_names.add(w)
                elif len(w) >= 3: english_words.add(w.lower())          # every content word incl. adjectives/adverbs (R8: 'red' is 3 letters)
            continue
        for w in _tagger()(text):
            s = w.surface
            if re.search(r'[0-9０-９A-Za-z]', s): proper.add(s)
            elif w.feature.pos2 == '固有名詞': proper.add(s)
            elif w.feature.pos1 == '名詞' and w.feature.pos2 == '普通名詞' and len(s) >= 2: common.add(s)
            elif w.feature.pos1 == '動詞' and len(_base(w)) >= 2: verbs.add(_base(w))
    hit_proper = sorted(x for x in proper if len(x) >= 2 and x in blob and not x.isdigit())
    hit_names = sorted(x for x in english_names if re.search(r'\b' + re.escape(x) + r'\b', blob))
    hit_common = sorted(x for x in common if x in blob)
    hit_verbs = sorted(x for x in verbs if x in blob)
    hit_english = sorted(x for x in english_words if re.search(r'\b' + re.escape(x) + r'\b', blob))
    print(f'added lines: {len(added)}')
    print('PROPER/NUMERIC (must be empty):', hit_proper)
    print('ENGLISH NAMES (must be empty):', hit_names)
    print('common nouns found in added lines (list only):', hit_common)
    print('verb lemmas found in added lines (list only):', hit_verbs)
    print('english lowercase words found in added lines (list only; each with the added lines that hold it, so a reader can judge):', hit_english)
    for word in hit_english:
        lines = [l.strip() for l in added if re.search(r'\b' + re.escape(word) + r'\b', l)]
        print(f'  [{word}] {len(lines)} added line(s):')
        for l in lines[:3]:
            print('      ' + l[:160])
    sys.exit(1 if (hit_proper or hit_names) else 0)


if __name__ == '__main__':
    main()
