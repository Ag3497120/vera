#!/usr/bin/env python3
"""Audited checker for bank7.tsv (held-out bank for the output gate v4).

Run from this directory:  python3 check7.py > check7.txt
Reads only the corpus and the earlier question banks of this repo; runs no Vera system.
Checks: corpus identity, header and ids, counts per part and shape, question form, evidence resolution, verbatim golds (not whole titles,
not in the question), the asked-fact absence search per unanswerable item (0 hits), S8 chains, and no repeat of bank2/3/4/6 / questions.tsv
(identical question text, or the same article with the same gold).  Overlaps that share an article but ask another fact are listed as INFO.
"""
import hashlib
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
LEADS = HERE.parent / 'data' / 'S300_fulllead.jsonl'
BANK = HERE / 'bank7.tsv'
PRIOR = {'bank2': (HERE.parent / 'bank2' / 'bank2.tsv', 3, 4, 5, 6), 'bank3': (HERE.parent / 'bank3' / 'bank3.tsv', 3, 4, 5, 6),
         'bank4': (HERE.parent / 'bank4' / 'bank4.tsv', 3, 4, 5, 6), 'bank6': (HERE.parent / 'bank6' / 'bank6.tsv', 3, 4, 5, 6)}
QTSV = HERE.parent / 'questions.tsv'
HEADER = ['#id', 'kind', 'shape', 'subject', 'question', 'gold', 'evidence', 'notes', 'audit']
SHAPES = ['S1-alias', 'S2-place', 'S3-person', 'S4-toshite', 'S5-paren', 'S6-naming', 'S7-near', 'S8-chain']
MIN_A, MIN_U, MIN_SHAPE, MIN_S8 = 30, 40, 4, 6
NEGATION = re.compile(r'(ない|ではない|以外|除い|除く)')
# the asked relation of every kept unanswerable item: (scope, regex).  scope 'corpus' = searched in all 592 sentences, 'article' = in the sentences of the
# subject article only (the relation word occurs in other articles).  Every entry must have 0 hits.
ABSENT = {
    'B7-U01': [('corpus', r'ハナズオウ.*(別名|和名|とも呼|ともいう)')],
    'B7-U02': [('corpus', r'ネノ.*(別名|現地語|通称)')],
    'B7-U03': [('corpus', r'Goncourt')],
    'B7-U04': [('corpus', r'北京語|普通話|ピンイン|Sānshuǐ|Sanshui')],
    'B7-U05': [('corpus', r'オボック.*(通称|別名|愛称)')],
    'B7-U06': [('corpus', r'大津呂.*(通称|別名|愛称)')],
    'B7-U07': [('corpus', r'Udine|ウーディネ県')],
    'B7-U08': [('corpus', r'スコーネ|Skåne|マルメ県')],
    'B7-U09': [('corpus', r'佐渡市')],
    'B7-U10': [('corpus', r'おおい町|大飯町')],
    'B7-U11': [('corpus', r'コマルカ.*(中心|主都|県都)')],
    'B7-U13': [('corpus', r'ロゴ.*Magisk|Magisk.*ロゴ|Magisk.*デザイン')],
    'B7-U14': [('corpus', r'ドレイヤー|Dreyer|NGC.*(カタログ|掲載)')],
    'B7-U15': [('corpus', r'録音')],
    'B7-U16': [('corpus', r'初演|指揮')],
    'B7-U17': [('corpus', r'ユニット名|名義.*(考案|命名)')],
    'B7-U18': [('corpus', r'百福.*(決め|命名|提案)')],
    'B7-U19': [('corpus', r'石炭|重油|燃料|天然ガス|LNG')],
    'B7-U20': [('corpus', r'醸造量|生産量|キロリットル')],
    'B7-U21': [('article', r'優勝|王者|制')],
    'B7-U22': [('article', r'優勝|王者|制')],
    'B7-U23': [('article', r'優勝|勝利|ポール|勝')],
    'B7-U24': [('corpus', r'句集')],
    'B7-U25': [('corpus', r'Prinz|Adalbert')],
    'B7-U26': [('corpus', r'Österreich|Supercup')],
    'B7-U27': [('corpus', r'Algarve|Taça|Torneio')],
    'B7-U28': [('corpus', r'Besenzone')],
    'B7-U29': [('corpus', r'Comarca|A Coruña|Corunha')],
    'B7-U30': [('corpus', r'[฀-๿]')],
    'B7-U32': [('corpus', r'Takakiopsida|タカキア綱|ナンジャモンジャゴケ綱')],
    'B7-U33': [('corpus', r'社内|ペナルティ')],
    'B7-U34': [('article', r'偉業|快挙')],
    'B7-U35': [('corpus', r'Thái|Thai Duc')],
    'B7-U36': [('article', r'総称')],
    'B7-U37': [('article', r'チーム|か国|カ国|参加')],
    'B7-U38': [('article', r'チーム|か国|カ国|参加|出場')],
    'B7-U39': [('article', r'参加国|か国|カ国|[0-9]+チーム|出場')],
    'B7-U40': [('article', r'チーム|か国|カ国|出場')],
    'B7-U41': [('article', r'出走|[0-9]+人|台')],
    'B7-U43': [('corpus', r'ネノ県.*人口|人口.*ネノ県')],
    'B7-U44': [('corpus', r'阿波市.*人口|人口.*阿波市')],
    'B7-U45': [('corpus', r'ブレシア県(の|は|全体).{0,10}人口|ブレシア県の[0-9]')],
    'B7-U46': [('corpus', r'ハノーファー.*(人口|[0-9]+人)')],
    'B7-U47': [('corpus', r'倉吉.*(郵便|〒)')],
    'B7-U48': [('corpus', r'(川原小|萩原町).*(郵便|〒)')],
    'B7-U49': [('corpus', r'安藤百福.*(生ま|生年|没)|(生ま|生年).*安藤百福')],
    'B7-U50': [('corpus', r'ビクター.*(設立|創立|創業)')],
}
errors, infos = [], []


def err(m):
    errors.append(m)


def info(m):
    infos.append(m)


def norm(q):
    return re.sub(r'[\s？?。、「」『』（）()]', '', q)


def main():
    leads = {}
    for line in LEADS.read_text(encoding='utf-8').splitlines():
        d = json.loads(line)
        leads[d['title']] = d['text'].split('。')
    allsents = [(t, i, s) for t, ss in leads.items() for i, s in enumerate(ss) if s]
    print(f"corpus: {len(leads)} articles, {len(allsents)} sentences; sha256 {hashlib.sha256(LEADS.read_bytes()).hexdigest()[:12]}")
    rows = [l.split('\t') for l in BANK.read_text(encoding='utf-8').splitlines()]
    if rows[0] != HEADER:
        err(f'header {rows[0]}')
    rows = rows[1:]
    ids = [r[0] for r in rows]
    if len(set(ids)) != len(ids):
        err('duplicate ids')
    A = [r for r in rows if r[1] == 'ANSWERABLE']
    U = [r for r in rows if r[1] == 'UNANSWERABLE']
    sh = Counter(r[2] for r in U)
    print(f'rows {len(rows)}: answerable {len(A)}, unanswerable {len(U)}; shapes {dict(sh)}; audit {dict(Counter(r[8] for r in rows))}')
    if len(A) < MIN_A or len(U) < MIN_U:
        err(f'counts A={len(A)} U={len(U)}')
    for s in SHAPES:
        if sh[s] < MIN_SHAPE:
            err(f'shape {s}: {sh[s]} < {MIN_SHAPE}')
    if sh['S8-chain'] < MIN_S8:
        err(f'S8-chain {sh["S8-chain"]} < {MIN_S8}')
    arts = Counter()
    for r in rows:
        if len(r) != 9:
            err(f'{r[0]}: {len(r)} columns')
            continue
        i, kind, shape, subj, q, gold, evid, notes, audit = r
        if not q.endswith('？'):
            err(f'{i}: question does not end in ？')
        if NEGATION.search(q):
            err(f'{i}: negation in question')
        if subj not in q and not any(subj in leads.get(e.rsplit('#', 1)[0], [''])[0] for e in evid.split(';')):
            info(f'{i}: subject {subj!r} not in the question')
        if audit not in ('valid', 'fixed'):
            err(f'{i}: audit {audit}')
        evs = []
        for e in evid.split(';'):
            t, k = e.rsplit('#', 1)
            if t not in leads or not (0 <= int(k) < len(leads[t])) or not leads[t][int(k)]:
                err(f'{i}: evidence {e} does not resolve')
            else:
                evs.append((t, int(k)))
        arts[evs[0][0]] += 1
        if kind == 'ANSWERABLE':
            if shape != '-' or notes:
                err(f'{i}: answerable has shape/notes')
            sent = leads[evs[0][0]][evs[0][1]]
            alts = gold.split('|')
            if not gold or not all(a and a in sent for a in alts):
                err(f'{i}: gold alternative not verbatim in {evid}')
            if any(a == evs[0][0] or a in q for a in alts):
                err(f'{i}: gold is the title or in the question')
            if len(evs) != 1:
                err(f'{i}: answerable has {len(evs)} evidence ids')
        else:
            if gold:
                err(f'{i}: unanswerable has gold')
            if shape not in SHAPES:
                err(f'{i}: shape {shape}')
            if not all(x in notes for x in ('文:', '欠落:', '誤答例:')):
                if not notes:
                    err(f'{i}: no notes')
            if not any(subj in s for _, _, s in allsents):
                err(f'{i}: subject {subj!r} not in the corpus')
            terms = ABSENT.get(i)
            if not terms:
                err(f'{i}: no recorded absence search')
                continue
            for scope, rx in terms:
                pool = [s for t, k, s in allsents if scope == 'corpus' or t == evs[0][0]]
                hit = [s for s in pool if re.search(rx, s)]
                if hit:
                    err(f'{i}: absence term {rx!r} ({scope}) has {len(hit)} hit(s): {hit[0][:50]}')
    for i in ABSENT:
        if i not in ids:
            err(f'ABSENT entry for a missing id {i}')
    if max(arts.values()) > 3:
        info(f'an article is used by {max(arts.values())} items')
    print('absence searches: ' + str(sum(len(v) for k, v in ABSENT.items() if k in ids)) + ' terms over the kept unanswerable items, 0 hits required')

    # no repeat of earlier banks
    prior_q = {}
    prior_art = defaultdict(list)
    for name, (p, ci, cq, cg, ce) in PRIOR.items():
        for l in p.read_text(encoding='utf-8').splitlines()[1:]:
            c = l.split('\t')
            if name == 'bank6':
                c = [c[0], c[1], c[3], c[3], c[4], c[5], c[6]]  # bank6 has the extra shape column
            qq, gg, ee = c[4], c[5], c[6]
            prior_q[norm(qq)] = (name, c[0])
            for e in re.split(r'[;|]', ee):
                if '#' in e:
                    prior_art[e.strip().rsplit('#', 1)[0]].append((name, c[0], qq, gg))
    for l in QTSV.read_text(encoding='utf-8').splitlines()[1:]:
        c = l.split('\t')
        prior_q[norm(c[3])] = ('questions', c[0])
        prior_art[c[2]].append(('questions', c[0], c[3], c[4] if len(c) > 4 else ''))
    shared = 0
    for r in rows:
        i, kind, q, gold, evid = r[0], r[1], r[4], r[5], r[6]
        if norm(q) in prior_q:
            err(f'{i}: question text repeats {prior_q[norm(q)]}')
        a0 = evid.split(';')[0].rsplit('#', 1)[0]
        for name, pid, pq, pg in prior_art.get(a0, []):
            if kind == 'ANSWERABLE' and pg and set(gold.split('|')) & set(pg.split('|')):
                err(f'{i}: same article and gold as {name} {pid} ({pq})')
        if a0 in prior_art:
            shared += 1
            info(f'{i}: article {a0!r} also in ' + ', '.join(sorted({f"{n} {p}" for n, p, _, _ in prior_art[a0]}))[:150])
    print(f'items whose article also appears in an earlier bank: {shared} (different asked fact; listed in AUDIT7.md)')
    print('bank6 questions repeated: ' + str(sum(1 for r in rows if prior_q.get(norm(r[4]), ('',))[0] == 'bank6')))
    for x in infos:
        print('INFO', x)
    if errors:
        print(f'FAIL ({len(errors)} errors)')
        for e in errors:
            print('-', e)
        return 1
    print('PASS (0 errors)')
    return 0


if __name__ == '__main__':
    sys.exit(main())
