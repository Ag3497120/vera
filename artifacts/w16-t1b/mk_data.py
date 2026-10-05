"""W16-t1b 検査データの生成。語の組の表から機械的に作る。期待は表から決め、実行結果から作らない。"""
import json, sys
from pathlib import Path
OUT = Path(sys.argv[1])
# 第 2 ラウンド（K819）: 第 2 引数に基点の木（git archive HEAD の展開先）、第 3 引数に python を渡すと、gate を「基点が出来事として読む文だけ true」に
# 形の規則で決める（行の id を名指しで変えない）。渡さなければ表の gate のまま（第 1 ラウンドの凍結を再生成する場合）。
BASE = sys.argv[2] if len(sys.argv) > 3 else None
PYTHON = sys.argv[3] if len(sys.argv) > 3 else None

def V(plain, past, stem, te, ba, vol, pot, ichi, objs, ptr=None):
    return dict(plain=plain, past=past, stem=stem, te=te, ba=ba, vol=vol, pot=pot, ichi=ichi, objs=objs)

VERBS = [
    V('読む','読んだ','読み','読んで','読め','読もう','読めた',False,['小説','手紙','新聞','地図']),
    V('書く','書いた','書き','書いて','書け','書こう','書けた',False,['手紙','報告書','日記']),
    V('買う','買った','買い','買って','買え','買おう','買えた',False,['切符','新聞','傘']),
    V('洗う','洗った','洗い','洗って','洗え','洗おう','洗えた',False,['皿','車']),
    V('作る','作った','作り','作って','作れ','作ろう','作れた',False,['弁当','資料']),
    V('運ぶ','運んだ','運び','運んで','運べ','運ぼう','運べた',False,['荷物','箱']),
    V('食べる','食べた','食べ','食べて','食べれ','食べよう',None,True,['弁当','みかん','パン']),
    V('見る','見た','見','見て','見れ','見よう',None,True,['写真','地図']),
    V('開ける','開けた','開け','開けて','開けれ','開けよう',None,True,['窓','箱']),
    V('調べる','調べた','調べ','調べて','調べれ','調べよう',None,True,['地図','資料']),
    V('届ける','届けた','届け','届けて','届けれ','届けよう',None,True,['荷物','手紙']),
]
SUBJ = ['次郎','花子','太郎','美咲','健太','由美','大輔']
OTHER = ['和子','誠','真理','隆']

# (template, question tense, gate)
FORMS = {
 ('desire','願望'): [
  ('{s}は{o}を{stem}たかった。','past',True,False),
  ('{s}は{o}を{stem}たい。','plain',True,False),
  ('{s}が{o}を{stem}たいです。','plain',True,False),
  ('{s}は{o}を{stem}たがっていた。','past',True,False),
  ('{s}は{o}を{stem}たかったです。','past',True,False),
  ('{s}は{p}に{o}を{te}もらいたかった。','past',True,False),
  ('{s}は{p}に{o}を{te}ほしかった。','past',False,False),
 ],
 ('potential','可能'): [
  ('{s}は{o}を{stem}られた。','past',True,True),
  ('{s}が{o}を{stem}られる。','plain',True,True),
  ('{s}も{o}を{stem}られた。','past',True,True),
  ('{s}は{o}を{pot}。','past',False,False),
  ('{s}は{o}を{plain}ことができた。','past',False,False),
 ],
 ('conjecture','推量'): [
  ('{s}は{o}を{plain}だろう。','plain',False,False),
  ('{s}は{o}を{past}だろう。','past',False,False),
  ('{s}は{o}を{plain}でしょう。','plain',False,False),
  ('{s}は{o}を{plain}かもしれない。','plain',False,False),
  ('{s}は{o}を{past}かもしれません。','past',False,False),
 ],
 ('appearance','様態'): [
  ('{s}は{o}を{stem}そうだ。','plain',False,False),
  ('{s}は{o}を{plain}ようだ。','plain',False,False),
  ('{s}は{o}を{past}ようだ。','past',False,False),
  ('{s}は{o}を{plain}みたいだ。','plain',False,False),
  ('{s}は{o}を{stem}そうです。','plain',False,False),
 ],
 ('conditional','仮定'): [
  ('{s}が{o}を{ba}ば、','plain',True,False),
  ('{s}が{o}を{past}ら、','past',True,False),
  ('もし{s}が{o}を{past}ら、{p}は喜ぶ。','past',False,False),
  ('{s}が{o}を{plain}なら、{p}は喜ぶ。','plain',False,False),
 ],
 ('volition','意志'): [
  ('{s}は{o}を{vol}。','plain',False,False),
  ('{s}は{o}を{plain}つもりだ。','plain',False,False),
  ('{s}は{o}を{plain}つもりでした。','plain',False,False),
  ('{s}は{o}を{vol}と思った。','plain',False,False),
 ],
 ('hearsay','伝聞'): [
  ('{s}は{o}を{past}らしかった。','past',True,False),
  ('{s}は{o}を{past}らしい。','past',False,False),
  ('{s}は{o}を{plain}そうだ。','plain',False,False),
  ('{s}は{o}を{past}そうだ。','past',False,False),
 ],
}
# 行の並べ方: 形の番号の並び（kind ごと、10 行）
ORDER = {
 'desire': [0,1,2,3,4,5,6,0,1,3],
 'potential': [0,1,2,0,1,2,3,4,3,4],
 'conjecture': [0,1,2,3,4,0,1,2,3,4],
 'appearance': [0,1,2,3,4,0,1,2,3,4],
 'conditional': [0,1,2,3,0,1,0,1,2,3],
 'volition': [0,1,2,3,0,1,2,3,0,1],
 'hearsay': [0,1,2,3,0,1,2,3,0,2],
}
def pick_verb(i, k, need_ichi, need_godan):
    pool = [v for v in VERBS if (not need_ichi or v['ichi']) and (not need_godan or not v['ichi'])]
    return pool[(i*2+k) % len(pool)]

rows = []
for kk, (key, ja) in enumerate(FORMS):
    forms = FORMS[(key, ja)]
    for i, fi in enumerate(ORDER[key]):
        tmpl, qt, gate, need_ichi = forms[fi]
        need_godan = ('{pot}' in tmpl)
        v = pick_verb(i, kk, need_ichi, need_godan)
        o = v['objs'][(i+kk) % len(v['objs'])]
        s = SUBJ[(i+kk) % len(SUBJ)]
        p = OTHER[(i+kk) % len(OTHER)]
        doc = tmpl.format(s=s, o=o, p=p, **{k: v[k] for k in ('plain','past','stem','te','ba','vol','pot') if v[k]})
        qv = v['past'] if qt == 'past' else v['plain']
        rows.append(dict(id=f'mod-{key}-{i:02d}', kind='modal', modality=key, kind_ja=ja, form=tmpl, gate=gate,
                         document=doc, questions=[f'誰が{o}を{qv}？', f'{s}は{o}を{qv}？']))
    # 対照 3 行
    for j in range(3):
        v = VERBS[(kk*3 + j + 1) % len(VERBS)]
        o = v['objs'][(j+kk) % len(v['objs'])]
        s = SUBJ[(kk*2 + j + 2) % len(SUBJ)]
        rows.append(dict(id=f'modc-{key}-{j}', kind='modal_control', modality=key, kind_ja=ja, form='{s}は{o}を{past}。', gate=False,
                         document=f'{s}は{o}を{v["past"]}。',
                         questions=[dict(q=f'誰が{o}を{v["past"]}？', expect_values=[s]), dict(q=f'{s}は{o}を{v["past"]}？', expect_values=['はい'])]))
if BASE:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from base_gate import base_readable
    readable = base_readable(BASE, PYTHON, sorted({r['document'] for r in rows if r['kind'] == 'modal' and r['gate']}))
    for r in rows:
        if r['kind'] == 'modal' and r['gate'] and not readable[r['document']]: r['gate'] = False
# 範囲（合否に入れない）
RANGE = [
 ('べき','次郎は小説を読むべきだ。','誰が小説を読む？'),
 ('べき','花子は手紙を書くべきだった。','誰が手紙を書いた？'),
 ('べき','太郎は荷物を運ぶべきです。','誰が荷物を運ぶ？'),
 ('godan_reru','次郎は先生に小説を読まれた。','誰が小説を読んだ？'),
 ('godan_reru','花子は友人に手紙を書かれた。','誰が手紙を書いた？'),
 ('godan_reru','太郎は社長に荷物を運ばれた。','誰が荷物を運んだ？'),
 ('scope_same','次郎は本を読み、絵を描きたかった。','誰が本を読んだ？'),
 ('scope_same','花子は手紙を書き、荷物を運びたかった。','誰が手紙を書いた？'),
 ('scope_diff','次郎は本を読んで、花子は絵を描きたかった。','誰が本を読んだ？'),
 ('scope_diff','太郎は窓を開けて、美咲は箱を運びたかった。','誰が窓を開けた？'),
 ('potential_verb','次郎は小説が読めた。','誰が小説を読んだ？'),
 ('koto_ga_dekiru','花子は手紙を書くことができる。','誰が手紙を書く？'),
 ('two_sentences','次郎は小説を読みたかった。花子は手紙を書いた。','誰が手紙を書いた？'),
 ('two_sentences','次郎は小説を読みたかった。花子は手紙を書いた。','誰が小説を読んだ？'),
 ('two_sentences','太郎は荷物を運んだ。美咲は箱を開けたかった。','誰が荷物を運んだ？'),
 ('two_sentences','太郎は荷物を運んだ。美咲は箱を開けたかった。','誰が箱を開けた？'),
 ('passive_control','次郎は花子に褒められた。','誰が次郎を褒めた？'),
 ('passive_control','太郎は先生に叱られた。','誰が太郎を叱った？'),
]
for i,(k,d,q) in enumerate(RANGE):
    rows.append(dict(id=f'modr-{i:02d}', kind='range', modality=k, kind_ja=k, form='', gate=False, document=d, questions=[q]))
(OUT/'w16t1b_modality.jsonl').write_text(''.join(json.dumps(r, ensure_ascii=False)+'\n' for r in rows), encoding='utf-8')

# ---- 肩書き ----
TITLES = ['課長','部長','社長','係長','教授','先生','監督','選手','店長','医師','議員','弁護士']
NAMES = ['森田','山本','中村','木村','小林','加藤','吉田','斎藤']
T = {
 'agent': ('{X}が書類を運んだ。','誰が書類を運んだ？'),
 'recipient': ('店員が{X}に本を渡した。','店員は誰に本を渡した？'),
 'patient': ('記者が{X}を取材した。','記者が誰を取材した？'),
}
trows = []
n = 0
for ti, t in enumerate(TITLES):
    for ri, role in enumerate(T):
        name = NAMES[(ti*3+ri) % len(NAMES)]
        X = name + t
        d, q = T[role]
        trows.append(dict(id=f'ttl-{n:02d}', kind='title', role=role, title=t, document=d.format(X=X), question=q, expect_values=[X])); n += 1
# 対照
CT = []
for i,(role,tmpl_x) in enumerate([('agent','{N}'),('recipient','{N}'),('patient','{N}'),('agent','{N}さん'),('recipient','{N}さん'),('patient','{N}さん')]):
    N = NAMES[(i*3+1) % len(NAMES)]
    X = tmpl_x.format(N=N); d,q = T[role]
    CT.append((f'plain-{role}' if 'さん' not in tmpl_x else f'san-{role}', d.format(X=X), q, [X]))
for i,(t,role) in enumerate([('課長','agent'),('医師','agent'),('先生','patient')]):
    N = NAMES[(i*2+4) % len(NAMES)]
    d,q = T[role]
    CT.append((f'noof-{role}', d.format(X=f'{t}の{N}'), q, [f'{t}の{N}']))
for i,(nm,d,q,ev) in enumerate(CT):
    trows.append(dict(id=f'ttlc-{i:02d}-{nm}', kind='title_control', document=d, question=q, expect_values=ev))
# 混在: 同じ人が 森田課長 と 森田 の両方
for i,t in enumerate(['課長','部長','社長','教授','監督','店長']):
    N = NAMES[(i*3+2) % len(NAMES)]
    trows.append(dict(id=f'ttlm-{i:02d}', kind='title_mixed', title=t, document=f'{N}{t}が書類を運んだ。{N}が書類を運んだ。', question='誰が書類を運んだ？', name_only=[N]))
RT = [
 ('技師ユンが書類を運んだ。','誰が書類を運んだ？'),
 ('部長田中が書類を運んだ。','誰が書類を運んだ？'),
 ('新人マキが書類を運んだ。','誰が書類を運んだ？'),
 ('医師の小林が書類を運んだ。','誰が書類を運んだ？'),
 ('課長の森田が書類を運んだ。部長の山本が書類を届けた。','誰が書類を運んだ？'),
 ('森田課長は店員に本を渡した。','森田課長は誰に本を渡した？'),
 ('森田課長は店員に本を渡した。','森田は誰に本を渡した？'),
 ('加藤社長が山本さんに本を渡した。','誰が山本さんに本を渡した？'),
]
for i,(d,q) in enumerate(RT):
    trows.append(dict(id=f'ttlr-{i:02d}', kind='range', document=d, question=q))
(OUT/'w16t1b_title.jsonl').write_text(''.join(json.dumps(r, ensure_ascii=False)+'\n' for r in trows), encoding='utf-8')
import collections
print(collections.Counter((r['kind'],r.get('modality')) for r in rows)); print(collections.Counter(r['kind'] for r in trows))
mod=[r for r in rows if r['kind']=='modal']
print('subjects',len({r['document'][:2] for r in mod}),'verbs',len({r['questions'][0].split('を')[-1] for r in mod}))
