#!/usr/bin/env python3
"""Audited checker for bank6.tsv (held-out bank for the loom evidence gate v3).

Run from this directory:  python3 check6.py > check6.txt
Reads only the corpus and the earlier question banks of this repo; runs no Vera system.
"""
import csv
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
LEADS = HERE.parent / 'data' / 'S300_fulllead.jsonl'
SENTS = HERE.parent / 'bank2' / 'data' / 'fulllead_sents.jsonl'
BANK = HERE / 'bank6.tsv'
PRIOR = {  # banks that Vera systems have read (question surface + gold)
    'bank2': HERE.parent / 'bank2' / 'bank2.tsv',
    'bank3': HERE.parent / 'bank3' / 'bank3.tsv',
    'bank4': HERE.parent / 'bank4' / 'bank4.tsv',
    'questions': HERE.parent / 'questions.tsv',
}
HEADER = ['#id', 'kind', 'shape', 'subject', 'question', 'gold', 'evidence', 'notes', 'audit']
SHAPES = ['S1-alias', 'S2-place', 'S3-person', 'S4-toshite', 'S5-paren', 'S6-naming', 'S7-near']
MIN_A, MIN_U, MIN_SHAPE = 25, 32, 4
NEGATION = re.compile(r'(ない|ではない|以外|除い|除く)')
# answerable items whose fact overlaps an earlier bank's item on the same article, kept knowingly (AUDIT6.md)
KNOWN_OVERLAP = {'B6-A05', 'B6-A08'}
# the asked relation of every kept unanswerable item, searched over all 592 sentences: each term must have 0 hits
ABSENT_TERMS = {
    'B6-U01': ['はっしゅ', 'ハッシュ表（'],
    'B6-U02': ['川原石.*(通称|呼ばれ|愛称)'],
    'B6-U03': ['drama', '海外ドラマ.*英語'],
    'B6-U05': ['フェミニズム.*(別名|呼ばれ|ともいう)', '女性解放', 'ウーマン・?リブ'],
    'B6-U06': ['ゲール', 'Mac ?Fergus', 'Fearghas'],
    'B6-U07': ['海浦.*市', '芦北.*市'],
    'B6-U08': ['安房.*市', '高山市', '中部縦貫.*市'],
    'B6-U09': ['水戸市.{0,3}区'],
    'B6-U10': ['海老津.*市', '岡垣.*市'],
    'B6-U11': ['オックスフォードシャー', 'Oxfordshire', 'カウンティ', 'アフィントン.*州'],
    'B6-U13': ['率い', '開発者', '開発責任', 'Bard.*(人物|氏)'],
    'B6-U14': ['考案', 'BAN BAN.*(作|デザイン)'],
    'B6-U15': ['企画', 'YAMAMORI.*(制作|プロデュー)'],
    'B6-U16': ['HONEY BADGER.*プロデュー', 'バンド.*プロデュース'],
    'B6-U18': ['翻訳', '訳者', '日本語訳', '邦訳'],
    'B6-U19': ['フェミニズム.*[0-9]{4}年', '第一波'],
    'B6-U20': ['ブリティッシュ・エアウェイズ.*設立', 'BOAC', '英国海外航空'],
    'B6-U21': ['開業', '花園町.*[0-9]{4}年'],
    'B6-U22': ['S-37.*(運用|空軍|ロシア|ソ連)', 'ベルクト', 'Berkut', 'Su-'],
    'B6-U23': ['CUBE JUICE.*結成', '長尾.*結成'],
    'B6-U24': ['ニーム', 'デニム.*(生産|国)', 'ジーンズ.*国'],
    'B6-U26': ['ATACS.*略', 'Advanced', 'Train'],
    'B6-U27': ['insulation', '外断熱.*英語'],
    'B6-U28': ['feminis', 'フェミニズム.*英語'],
    'B6-U29': ['Caroline', 'Caroline', 'カロリーヌ.*綴'],
    'B6-U30': ['英虞.*(別名|呼ばれ|称)'],
    'B6-U31': ['国旗.*(呼ばれ|称|愛称)', '三日月旗'],
    'B6-U32': ['S-37.*(愛称|別名|呼ばれ)', 'ベルクト'],
    'B6-U33': ['大使館.*(呼ばれ|愛称|通称)'],
    'B6-U34': ['クラブ世界選手権.*(通称|呼ばれ|略称)', 'クラブワールドカップ'],
    'B6-U35': ['Y16', 'Y18', '隣駅'],
    'B6-U36': ['OR07', 'OR09', '隣駅'],
    'B6-U39': ['[0-9]対[0-9]', '[0-9]-[0-9]で', 'PK戦', 'スーパーカップ.*(勝|優勝|制)'],
    'B6-U40': ['ケニア.*[0-9]+(人|名)', '選手団.*[0-9]+(人|名)の選手'],
}

errors, infos = [], []


def err(m):
    errors.append(m)


def info(m):
    infos.append(m)


# 1. corpus: the sentence file is the 「。」 split of the leads (0-based title#i)
leads = [json.loads(l) for l in open(LEADS, encoding='utf-8')]
split = {r['title']: r['text'].split('。') for r in leads}
by_title = defaultdict(list)
for l in open(SENTS, encoding='utf-8'):
    s = json.loads(l)
    t, i = s['source'].rsplit('#', 1)
    by_title[t].append((int(i), s['sent']))
for r in leads:
    got = sorted(by_title[r['title']])
    if ''.join(x for _, x in got) != r['text']:
        err(f'corpus: sentences of {r["title"]} do not concatenate to its lead')
    for i, x in got:
        if x.rstrip('。') != split[r['title']][i]:
            err(f'corpus: {r["title"]}#{i} differs from the 「。」 split')
SENT = {f'{t}#{i}': s for t, segs in split.items() for i, s in enumerate(segs) if s.strip()}
n_sent = sum(len(v) for v in by_title.values())
print(f'corpus: {len(leads)} leads, {n_sent} sentences, split identity {"ok" if not errors else "FAILED"}')

# 2. bank structure
with open(BANK, encoding='utf-8', newline='') as f:
    rd = csv.reader(f, delimiter='\t', quoting=csv.QUOTE_NONE)
    header = next(rd)
    rows = [dict(zip(header, r)) for r in rd]
if header != HEADER:
    err(f'header {header} != {HEADER}')
ids = [r['#id'] for r in rows]
if len(ids) != len(set(ids)):
    err('duplicate ids')
A = [r for r in rows if r['kind'] == 'ANSWERABLE']
U = [r for r in rows if r['kind'] == 'UNANSWERABLE']
if len(A) + len(U) != len(rows):
    err('kind must be ANSWERABLE or UNANSWERABLE')
shapes = Counter(r['shape'] for r in U)
print(f'rows: {len(rows)} (ANSWERABLE={len(A)}, UNANSWERABLE={len(U)}); shapes: '
      + ', '.join(f'{s}={shapes[s]}' for s in SHAPES))
print('audit: ' + ', '.join(f'{k}={v}' for k, v in sorted(Counter((r["kind"][0] + ":" + r["audit"]) for r in rows).items())))
if len(A) < MIN_A:
    err(f'answerable {len(A)} < {MIN_A}')
if len(U) < MIN_U:
    err(f'unanswerable {len(U)} < {MIN_U}')
for s in SHAPES:
    if shapes[s] < MIN_SHAPE:
        err(f'shape {s}: {shapes[s]} < {MIN_SHAPE}')

for r in rows:
    i = r['#id']
    if not re.fullmatch(r'B6-[AU]\d\d', i) or (i[3] == 'A') != (r['kind'] == 'ANSWERABLE'):
        err(f'{i}: id/kind mismatch')
    if r['audit'] not in ('valid', 'fixed'):
        err(f'{i}: audit {r["audit"]!r}')
    if (r['kind'] == 'ANSWERABLE') != (r['shape'] == '-') or (r['shape'] != '-' and r['shape'] not in SHAPES):
        err(f'{i}: shape {r["shape"]!r}')
    q = r['question']
    if not q.endswith('？'):
        err(f'{i}: question does not end in ？')
    if NEGATION.search(q):
        err(f'{i}: negation in question: {q}')
    if r['subject'] not in q:
        err(f'{i}: subject {r["subject"]!r} not in the question')
    ev = r['evidence'].split(';')
    if not 1 <= len(ev) <= 2 or len({e.rsplit("#", 1)[0] for e in ev}) != 1:
        err(f'{i}: evidence must be 1-2 ids of one article: {r["evidence"]}')
    if any(e not in SENT for e in ev):
        err(f'{i}: evidence does not resolve: {r["evidence"]}')
        continue
    cited = [SENT[e] for e in ev]
    title = ev[0].rsplit('#', 1)[0]
    if not any(r['subject'] in s for s in cited) and r['subject'] not in title:
        err(f'{i}: subject {r["subject"]!r} not in a cited sentence or the title')
    if r['kind'] == 'ANSWERABLE':
        alts = r['gold'].split('|')
        if not r['gold'] or any(not a for a in alts):
            err(f'{i}: empty gold / alternative')
        for a in alts:
            if not any(a in s for s in cited):
                err(f'{i}: gold {a!r} not verbatim in a cited sentence')
            if a in title or a in q:
                err(f'{i}: gold {a!r} is in the title or the question (answerable from the question alone)')
        others = [k for k, s in SENT.items() if k.rsplit('#', 1)[0] != title and any(a in s for a in alts)]
        if others:
            info(f'{i}: gold also occurs in other articles: {others[:3]}')
    else:
        if r['gold']:
            err(f'{i}: unanswerable with gold')
        if not all(lbl in r['notes'] for lbl in ('文:', '欠落:', '誤答例:')):
            err(f'{i}: notes lack 文:/欠落:/誤答例:')
        terms = ABSENT_TERMS.get(i)
        if not terms:
            err(f'{i}: no absence search recorded')
        for t in terms or []:
            hits = [k for k, s in SENT.items() if re.search(t, s, re.I)]
            if hits:
                err(f'{i}: absence term {t!r} hits {hits[:3]}')
        m = re.search(r'誤答例:\s*(.+?)。?$', r['notes'])
        c = m.group(1) if m else ''
        where = [k for k, s in SENT.items() if c and c in s]
        info(f'{i}: c) {c!r} ' + (f'occurs in {where[:2]}' if where else 'not in the corpus'))

# 3. no repeat of a question that a Vera system has read
prior = []
for name, p in PRIOR.items():
    for l in open(p, encoding='utf-8'):
        if l.startswith('#') or not l.strip():
            continue
        f = l.rstrip('\n').split('\t')
        if name == 'questions':      # id kind subject question gold
            prior.append((name, f[0], f[2], f[3], f[4] if len(f) > 4 else ''))
        else:                        # id kind corpus subject question gold evidence ...
            art = f[6].split(';')[0].rsplit('#', 1)[0] if len(f) > 6 and '#' in f[6] else f[3]
            prior.append((name, f[0], art, f[4], f[5]))


def norm(q):
    return re.sub(r'[\s？?。]', '', q)


pq = {norm(q): (n, i) for n, i, _, q, _ in prior}
for r in rows:
    if norm(r['question']) in pq:
        err(f'{r["#id"]}: question repeats {pq[norm(r["question"])]}')
for r in A:
    title = r['evidence'].split(';')[0].rsplit('#', 1)[0]
    mine = [a.casefold() for a in r['gold'].split('|')]
    for n, pid, art, q, g in prior:
        if art != title or not g:
            continue
        theirs = [x.casefold() for x in g.split('|') if x]
        if any(a == b or (len(b) >= 3 and b in a) or (len(a) >= 3 and a in b) for a in mine for b in theirs):
            msg = f'{r["#id"]}: gold overlaps {n} {pid} ({q} -> {g})'
            (info if r['#id'] in KNOWN_OVERLAP else err)(msg + (' [known, kept]' if r['#id'] in KNOWN_OVERLAP else ''))

for m in infos:
    print('INFO', m)
for m in errors:
    print('ERROR', m)
print(f'RESULT: {"PASS" if not errors else "FAIL"} ({len(errors)} errors, {len(infos)} info)')
sys.exit(1 if errors else 0)
