#!/usr/bin/env python3
"""W3-b1 手順 2: 配置の述語の型ごとの成員の一覧(型の表の根拠。登録の前に作る)。

`<配置>/placement.sqlite` を読み取り専用で開き、`headwords` の ns='P'・state='DECIDED' の語を集め、各語を `coarse_place.query(語, placement=<配置>)`
で問い合わせ直して、直接(origin=direct)・決め手に gen_definition が無い・型が 1 つで P_ で始まる語だけを型ごとに残す。
書くもの: <out>/type_members.json(型 -> 語の並び。辞書順)、<out>/type_members.txt(人が読む形。型ごとの件数と語。読解器の 4 つの一覧に入っている語には印 *)。
使い方: cd <木> && PYTHONPATH=<木> python tests/reading_soundness/w3b1_type_members.py --placement DIR --out DIR2
読み込んだ verantyx* が PYTHONPATH の木の配下か検査する(外れたら終了コード 2)。
"""
import argparse
import json
import os
import sqlite3
import sys
from pathlib import Path


def isolation():
    root = os.path.realpath(os.environ.get('PYTHONPATH', '.').split(os.pathsep)[0])
    foreign = [m.__file__ for k, m in list(sys.modules.items()) if (k == 'verantyx' or k.startswith('verantyx.'))
               and getattr(m, '__file__', None) and not os.path.realpath(m.__file__).startswith(root + os.sep)]
    return root, foreign


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--placement', required=True)
    ap.add_argument('--out', required=True)
    a = ap.parse_args()
    from verantyx import coarse_place
    from verantyx import semantic_reader as R
    root, foreign = isolation()
    print('tree=' + root)
    if foreign:
        print('ISOLATION FAILED', foreign); sys.exit(2)
    db = os.path.join(os.path.abspath(a.placement), 'placement.sqlite')
    con = sqlite3.connect('file:%s?mode=ro' % db, uri=True)
    words = [r[0] for r in con.execute("SELECT word FROM headwords WHERE ns='P' AND state='DECIDED' ORDER BY word")]
    con.close()
    reader_lists = {'TRANSFER': R._TRANSFER_PREDICATES, 'GOAL': R._GOAL_PREDICATES, 'PLACEMENT': R._PLACEMENT_PREDICATES,
                    'LOCATION': R._LOCATION_PREDICATES}
    members, dropped = {}, {'not_direct': 0, 'via_generated': 0, 'not_one_P_type': 0}
    for w in words:
        ans = coarse_place.query(w, placement=a.placement)
        if ans.get('state') != 'DECIDED' or ans.get('origin') != 'direct': dropped['not_direct'] += 1; continue
        if 'gen_definition' in (ans.get('decided_by') or []): dropped['via_generated'] += 1; continue
        top = ans.get('top') or []
        if len(top) != 1 or not top[0].startswith('P_'): dropped['not_one_P_type'] += 1; continue
        members.setdefault(top[0], []).append(w)
    members = {t: sorted(ws) for t, ws in sorted(members.items())}
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    (out / 'type_members.json').write_text(json.dumps(members, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    lines = ['# 述語の型ごとの成員(配置 %s の headwords ns=P・DECIDED を問い合わせ直し、direct・gen_definition なし・型 1 つだけ残した)' % os.path.basename(os.path.abspath(a.placement)),
             '# 印: * = 読解器の 4 つの一覧(_TRANSFER/_GOAL/_PLACEMENT/_LOCATION_PREDICATES)に入っている語',
             'headwords(ns=P, DECIDED)=%d 落とした=%s 型の数=%d' % (len(words), json.dumps(dropped), len(members)), '']
    for t, ws in members.items():
        lines.append('## %s  件数=%d' % (t, len(ws)))
        lines.append(' '.join(w + ('*' if any(w in s for s in reader_lists.values()) else '') for w in ws))
        lines.append('')
    (out / 'type_members.txt').write_text('\n'.join(lines), encoding='utf-8')
    print('types=%d words=%d dropped=%s out=%s' % (len(members), sum(len(v) for v in members.values()), dropped, out))


if __name__ == '__main__':
    main()
