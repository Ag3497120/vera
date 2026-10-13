#!/usr/bin/env python3
"""Audited checker for bank8.tsv (held-out bank, written for the next gate revision).

Usage:  python3 check8.py [bank8.tsv] > check8.txt          (reads the corpus and the earlier banks, runs no Vera system)
Checks: corpus identity, header/ids, counts per part and shape, question form, evidence resolution, verbatim golds (not whole titles, not in the question),
the asked-fact absence search per unanswerable item (0 hits; scope 'corpus' = all sentences, 'article' = sentences of the subject article), S8 chains,
S9 kind-word sharing, per-article caps, and ZERO reuse of earlier banks: identical question text, same (article, gold), and for unanswerable items a
same-article question whose asked-fact wording (subject removed) is char-bigram similar.  Article-sharing items are listed as INFO.
"""
import hashlib, json, re, sys
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
BANK = Path(sys.argv[1]) if len(sys.argv) > 1 else HERE / 'bank8.tsv'
LEADS = Path('/Users/motonisihikoudai/Projects/vera-impl/bank8-author/work8/S300_fulllead.jsonl')
L3 = Path('/Users/motonisihikoudai/Projects/vera-impl/wt/line3/experiments/line3')
CORPUS_SHA = 'd987fdee0e19283e9c69e461b2ae695e5f2681f7a64e2c486572fcd6d4f419ea'
PRIOR = ['bank2', 'bank3', 'bank4', 'bank6', 'bank7']
HEADER = ['#id', 'kind', 'shape', 'subject', 'question', 'gold', 'evidence', 'notes', 'audit']
SHAPES = ['S1-alias', 'S2-place', 'S3-person', 'S4-toshite', 'S5-paren', 'S6-naming', 'S7-near', 'S8-chain', 'S9-name']
N_A, N_U, MIN_SHAPE, MIN_S9 = 35, 50, 5, 8
NEGATION = re.compile(r'(ない|ではない|以外|除い|除く)')
SIM_LIMIT = 0.40
# asked relation of every kept unanswerable item: (scope, regex).  scope 'corpus' = all sentences, 'article' = the subject article only.  0 hits required.
ABSENT = {
 'B8b-U01': [('corpus', r'エクスチェンジ|ピーディーエフ|PDF-XChange.*(読み|ヨミ)')],
 'B8b-U02': [('article', r'通称|別名|愛称|とも呼|ともいう|別称')],
 'B8b-U03': [('article', r'別名|ともいう|とも呼|通称|慣用名|別称')],
 'B8b-U04': [('article', r'通称|別名|愛称|とも呼|ともいう'), ('corpus', r'キューバ.*(通称|愛称)')],
 'B8b-U06': [('article', r'愛称|通称|別名|とも呼|ともいう')],
 'B8b-U08': [('article', r'市')],
 'B8b-U10': [('article', r'区'), ('corpus', r'漳州市.*区|芗城|龍文')],
 'B8b-U12': [('article', r'市')],
 'B8-U09': [('article', r'市')],
 'B8-U11': [('article', r'区')],
 'B8b-U13': [('article', r'結成|設立|創設|立ち上げ|旗揚げ')],
 'B8b-U14': [('article', r'最初に定義|初めて|導入|発表|考案')],
 'B8b-U15': [('article', r'考案|命名|名付|付けた|名づけ')],
 'B8b-U16': [('article', r'命名|名付|グループ名|付けた|名づけ')],
 'B8b-U17': [('article', r'設計|氏名|氏が|さんが')],
 'B8b-U19': [('article', r'原理|仕組み|磁|センサ|光|数え|カウント方式|検知方式')],
 'B8b-U20': [('article', r'Windows|macOS|Linux|OS|対応環境|動作環境')],
 'B8b-U21': [('article', r'スープ|出汁|だし|醤油|味噌|塩|豚骨')],
 'B8b-U22': [('article', r'供給|地域|エリア|県内|全域|ガスを')],
 'B8b-U23': [('article', r'定員|人|乗客|旅客|名')],
 'B8b-U25': [('corpus', r'Steyer|シュタイアーベルク.*(Steyer|綴り)')],
 'B8b-U26': [('corpus', r'武宁|Wuning|wǔníng|簡体')],
 'B8b-U27': [('corpus', r'מחנים|Mahanaim|Machanaim')],
 'B8b-U28': [('article', r'[가-힣]|ハングル')],
 'B8b-U29': [('corpus', r'Brunnen|Bundesbrief')],
 'B8b-U31': [('article', r'愛称|通称|呼ばれ|呼称|ニックネーム|とも呼')],
 'B8b-U32': [('article', r'通称|愛称|呼ばれ|称され|とも呼|ともいう|別称')],
 'B8b-U33': [('article', r'通称|愛称|呼ばれ|称され|とも呼|ともいう|別称')],
 'B8b-U34': [('article', r'報道|呼ばれ|と称|通称|別名|とも呼|ともいう')],
 'B8b-U35': [('article', r'現地|呼ばれ|通称|別称|とも呼|ともいう|別名')],
 'B8b-U37': [('article', r'開業|開設|営業を開始|開駅|設置|開通')],
 'B8b-U38': [('article', r'再開')],
 'B8b-U41': [('article', r'結成|設立|デビュー|活動開始|発足')],
 'B8b-U42': [('article', r'利用開始|運用開始|サービス開始|委任|DNSルート|開始日')],
 'B8-U39': [('article', r'優勝|王者|制覇|金メダル')],
 'B8b-U44': [('corpus', r'城站.*(駅番号|隣|次の駅)|Chengzhan')],
 'B8b-U45': [('corpus', r'ヴェーザー左岸.*(本部|所在地|置)')],
 'B8b-U47': [('corpus', r'漳州.*(人口|[0-9]+人)')],
 'B8b-U48': [('corpus', r'郡庁|郡役所|郡衙|東宇和郡.*(中心|所在)')],
 'B8b-U49': [('corpus', r'鳥取ガス.*(本社|所在地|置)')],
 'B8b-U51': [('article', r'地区|区|通り|ミラマール|ベダード|ベダド')],
 'B8b-U52': [('article', r'橋長|全長|[0-9]+(\.[0-9]+)?\s*(m|メートル|ｍ)')],
 'B8b-U54': [('article', r'旧社格|社格|県社|郷社|村社')],
 'B8-U55': [('article', r'旧社格|社格|県社|郷社|村社')],
 'B8b-U56': [('article', r'面積|平方|km|㎞|キロ')],
 'B8b-U59': [('article', r'現在|現・|市|町')],
 'B8b-U60': [('article', r'現在|現・|市|町')],
 'B8b-U62': [('article', r'駅番号|番号|[A-Z]{1,2}-?[0-9]{2}')],
 'B8-U58': [('article', r'駅番号|番号|[A-Z]{1,2}-?[0-9]{2}')],
 'B8-U60': [('article', r'駅番号|番号|[A-Z]{1,2}-?[0-9]{2}')],
}
# S9: the kind word shared by the subject and the entity of the tempting sentence (must occur in both article titles)
KIND = {'B8b-U51': '大使館', 'B8b-U52': '橋', 'B8b-U54': '神社', 'B8-U55': '神社', 'B8b-U56': '県', 'B8b-U59': '村', 'B8b-U60': '村',
        'B8b-U62': '駅', 'B8-U58': '駅', 'B8-U60': '駅'}
errors, infos = [], []
err = errors.append
info = infos.append


def norm(q):
    return re.sub(r'[\s？?。、「」『』（）()!！]', '', q)


def bigrams(s):
    return {s[i:i + 2] for i in range(len(s) - 1)}


def main():
    raw = LEADS.read_bytes()
    if hashlib.sha256(raw).hexdigest() != CORPUS_SHA:
        err('corpus sha mismatch')
    leads = {}
    for line in raw.decode('utf-8').splitlines():
        d = json.loads(line)
        leads[d['title']] = d['text'].split('。')
    allsents = [(t, i, s) for t, ss in leads.items() for i, s in enumerate(ss) if s]
    print(f'corpus: {len(leads)} articles, {len(allsents)} sentences; sha256 {CORPUS_SHA[:12]}')
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
    print(f'rows {len(rows)}: answerable {len(A)}, unanswerable {len(U)}; shapes {dict(sorted(sh.items()))}; audit {dict(Counter(r[8] for r in rows))}')
    if len(A) != N_A or len(U) != N_U:
        err(f'counts A={len(A)} U={len(U)}')
    for s in SHAPES[:8]:
        if sh[s] < MIN_SHAPE:
            err(f'shape {s}: {sh[s]} < {MIN_SHAPE}')
    if sh['S9-name'] < MIN_S9:
        err(f'S9-name {sh["S9-name"]} < {MIN_S9}')
    part_arts = {'ANSWERABLE': Counter(), 'UNANSWERABLE': Counter()}
    allarts = Counter()
    subj_art = {}
    for r in rows:
        if len(r) != 9:
            err(f'{r[0]}: {len(r)} columns')
            continue
        i, kind, shape, subj, q, gold, evid, notes, audit = r
        if not q.endswith('？'):
            err(f'{i}: question does not end in ？')
        if NEGATION.search(q):
            err(f'{i}: negation in question')
        if audit not in ('valid', 'fixed'):
            err(f'{i}: audit {audit}')
        evs = []
        for e in evid.split(';'):
            t, k = e.rsplit('#', 1)
            if t not in leads or not (0 <= int(k) < len(leads[t])) or not leads[t][int(k)]:
                err(f'{i}: evidence {e} does not resolve')
            else:
                evs.append((t, int(k)))
        if not evs:
            continue
        subj_art[i] = evs[0][0]
        part_arts[kind][evs[0][0]] += 1
        allarts[evs[0][0]] += 1
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
            if not notes.startswith('S' + shape[1]):
                err(f'{i}: notes do not start with the shape number')
            if subj not in leads.get(evs[0][0], ['']) [0] and subj != evs[0][0] and subj not in q:
                info(f'{i}: subject {subj!r} not in the first cited sentence')
            if not any(subj in s for _, _, s in allsents):
                err(f'{i}: subject {subj!r} not in the corpus')
            terms = ABSENT.get(i)
            if not terms:
                err(f'{i}: no recorded absence search')
            else:
                for scope, rx in terms:
                    pool = [s for t, k, s in allsents if scope == 'corpus' or t == evs[0][0]]
                    hit = [s for s in pool if re.search(rx, s)]
                    if hit:
                        err(f'{i}: absence term {rx!r} ({scope}) has {len(hit)} hit(s): {hit[0][:50]}')
            if shape == 'S8-chain' and q.count('の') < 2:
                err(f'{i}: S8 question is not a chain of nouns')
            if shape == 'S9-name':
                kw = KIND.get(i)
                tempt = [e for e in evs if e[0] != evs[0][0]]
                if not kw or not tempt:
                    err(f'{i}: S9 needs a kind word and a tempting sentence of another article')
                elif kw not in evs[0][0] and kw not in subj or kw not in tempt[0][0]:
                    err(f'{i}: kind word {kw!r} not shared by {evs[0][0]!r} and {tempt[0][0]!r}')
    for i in ABSENT:
        if i not in ids:
            err(f'ABSENT entry for a missing id {i}')
    for kind, c in part_arts.items():
        if c and max(c.values()) > 2:
            err(f'{kind}: an article is used by {max(c.values())} items of this part')
    if max(allarts.values()) > 3:
        err(f'an article is used by {max(allarts.values())} items')
    print('absence searches: %d terms over the kept unanswerable items, 0 hits required' % sum(len(v) for k, v in ABSENT.items() if k in ids))
    print('S9 kind words:', {i: KIND[i] for i in KIND if i in ids})

    # zero reuse of earlier banks
    prior_q, prior_art = {}, defaultdict(list)
    for name in PRIOR:
        for l in (L3 / name / f'{name}.tsv').read_text(encoding='utf-8').splitlines()[1:]:
            c = l.split('\t')
            qq, gg, ee = c[4], c[5], c[6]   # bank2/3/4: id kind corpus subject question gold evidence ; bank6/7: id kind shape subject question gold evidence
            prior_q[norm(qq)] = (name, c[0])
            for e in re.split(r'[;|]', ee):
                if '#' in e:
                    prior_art[e.strip().rsplit('#', 1)[0]].append((name, c[0], qq, gg, c[3]))
    for l in (L3 / 'questions.tsv').read_text(encoding='utf-8').splitlines()[1:]:
        c = l.split('\t')
        prior_q[norm(c[3])] = ('questions', c[0])
        prior_art[c[2]].append(('questions', c[0], c[3], c[4] if len(c) > 4 else '', c[2]))
    shared, maxsim = [], 0.0
    for r in rows:
        i, kind, subj, q, gold, evid = r[0], r[1], r[3], r[4], r[5], r[6]
        if norm(q) in prior_q:
            err(f'{i}: question text repeats {prior_q[norm(q)]}')
        arts = [e.rsplit('#', 1)[0] for e in evid.split(';')]
        a0 = arts[0]
        qa = bigrams(norm(q).replace(norm(subj), ''))
        for name, pid, pq, pg, _ in prior_art.get(a0, []):
            if kind == 'ANSWERABLE' and pg and set(gold.split('|')) & set(pg.split('|')):
                err(f'{i}: same article and gold as {name} {pid} ({pq})')
            qb = bigrams(norm(pq).replace(norm(subj), ''))
            sim = len(qa & qb) / max(1, len(qa | qb))
            maxsim = max(maxsim, sim)
            if sim >= SIM_LIMIT:
                err(f'{i}: asked-fact wording similar ({sim:.2f}) to {name} {pid}: {pq}')
        if a0 in prior_art:
            shared.append(i)
            info(f'{i}: subject article {a0!r} also in ' + ', '.join(sorted({f"{n} {p}" for n, p, _, _, _ in prior_art[a0]}))[:160])
        for t in arts[1:]:
            if t in prior_art:
                info(f'{i}: tempting article {t!r} also in ' + ', '.join(sorted({f"{n} {p}" for n, p, _, _, _ in prior_art[t]}))[:160])
    print(f'items whose subject article also appears in an earlier bank: {len(shared)} (different asked fact; listed in AUDIT8.md)')
    print(f'question texts repeated: {sum(1 for r in rows if norm(r[4]) in prior_q)}; max same-article asked-fact similarity {maxsim:.2f} (limit {SIM_LIMIT})')
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
