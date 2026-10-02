#!/usr/bin/env python3
"""A3: 受身で動作主が書かれていない文に動作主を問う質問(「誰が会議を開いた？」型)が、時間・場所の句を答えとして返さないこと。

既定の入口ではなく読解 API(mode="semantic")で確かめる。a3.jsonl・a3_r2.jsonl・a3_r3.jsonl の各行 {text, question, forbidden} を
Vera.from_texts({'d': text}, mode='semantic').ask(question) に通し、verdict と values を出力する。
values のどれかが forbidden のいずれかを含んだら失敗(終了コード 1)。隔離検査: 読み込んだ verantyx* が PYTHONPATH の木の配下か。
"""
import json, os, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def main():
    from verantyx.one import Vera
    root = os.path.realpath(os.environ.get('PYTHONPATH', '.').split(os.pathsep)[0])
    foreign = [m.__file__ for k, m in list(sys.modules.items()) if (k == 'verantyx' or k.startswith('verantyx.'))
               and getattr(m, '__file__', None) and not os.path.realpath(m.__file__).startswith(root + os.sep)]
    print('tree=' + root)
    if foreign:
        print('ISOLATION FAILED', foreign); sys.exit(2)
    rows = []
    for name in ('a3.jsonl', 'a3_r2.jsonl', 'a3_r3.jsonl'):
        rows += [json.loads(x) for x in (HERE / name).read_text(encoding='utf-8').splitlines() if x.strip()]
    failed = 0
    for r in rows:
        answer = Vera.from_texts({'d': r['text']}, mode='semantic').ask(r['question'])
        verdict = answer.get('verdict')
        values = [str(v) for v in (answer.get('values') or [])]
        text = answer.get('text', '')
        bad = [f for f in r['forbidden'] if any(f in v for v in values) or f in str(text)]
        failed += bool(bad)
        print(f"{r['id']} verdict={verdict} values={values} text={text!r} forbidden_hit={bad} :: {r['text']} / {r['question']}")
    print(f'rows={len(rows)} failed={failed}')
    sys.exit(1 if failed else 0)


if __name__ == '__main__':
    main()
