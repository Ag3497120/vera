"""Writes p5/sample60.tsv and p5/direct_judge.tsv: the raw tables (p5_pre.py) + my reading (judgement, reason).
The reading is the implementer's, NOT ground truth.  Run once; then shasum the two files BEFORE counting (p5/judge.sha256)."""
import csv, sys
A = '/Users/motonisihikoudai/Projects/vera-impl/wt/W3-a4-S/artifacts/w3-a4/p5/'
OK, DOUBT, BAD = '正しい', '疑わしい', '明らかな誤り'
# sample60: (judgement, reason) for the words that are not simply right
S60 = {
 '記録する': (DOUBT, '書き留める行為。作成にも当たる'), '発売する': (DOUBT, '売り出す。作成より授受・伝達に近い面もある'),
 '対応する': (DOUBT, '対応（照応）なら状態、対処なら行為。多義'), '失敗する': (DOUBT, '出来事。状態とも変化とも読める'),
 '用意する': (DOUBT, '準備する。作成とも行為とも読める'), '位置する': (DOUBT, '存在のほうが近い。状態でも間違いとは言い切れない'),
 '取得する': (DOUBT, '入手。授受と所有のどちらとも読める'), 'まねする': (DOUBT, '模倣は行為。思考・認識とは言い切れない'),
 '追突する': (DOUBT, '追突は移動とも行為とも読める'), '殉教する': (DOUBT, '死ぬ行為。状態とは言い難いが他の型も決め手に欠ける'),
 '対面する': (DOUBT, '会う。行為とも伝達とも読める'), '剥奪する': (DOUBT, '奪い取る。授受とも所有とも読める'),
 '忌避する': (DOUBT, '避ける。行為か感情か'), '停車する': (DOUBT, '止まる。移動の終わりで移動と言い切れない'),
 '給電する': (DOUBT, '電力を渡す。授受のほうが当てはまる面がある'), 'ディ・ドナテッロする': ('該当なし', '生成が棄権（UNPLACED）。型が付いていない'),
}
DIRECT = {
 'exportする': (DOUBT, '外へ書き出す。伝達とは言い切れない'), '保証する': (DOUBT, '保証の表明は伝達だが約束・状態の面もある'),
 '出土する': (DOUBT, '土から出る。移動とも存在とも読める'), '列挙する': (DOUBT, '並べて述べる。伝達と言い切れない'),
 '奨励する': (DOUBT, '勧める。伝達とも行為とも読める'), '意味する': (BAD, '「〜を意味する」は意味・状態の関係で、相手へ伝える行為ではない'),
 '招待する': (DOUBT, '招く。伝達とも行為とも読める'), '浸透する': (DOUBT, '染み込む。移動とも変化とも読める'),
 '翻訳する': (DOUBT, '言語を変える。伝達・作成・変化のどれとも読める'), '表彰する': (DOUBT, '賞を与える。授受のほうが当てはまる面がある'),
 '請求する': (DOUBT, '求める。伝達と授受の両面'), '輸入する': (DOUBT, '物を国内へ入れる。移動と授受の両面'),
 '配信する': (DOUBT, '送り届ける。伝達と授受の両面'),
}
def fill(raw, out, table):
    rows = list(csv.reader(open(A + raw, encoding='utf-8'), delimiter='\t'))
    head, body = rows[0], rows[1:]
    ji, ri = head.index('judgement'), head.index('reason')
    ti, wi = head.index('top'), head.index('word')
    names = {'P_COMMUNICATE': '伝達', 'P_MOVE': '移動'}
    with open(A + out, 'w', encoding='utf-8') as f:
        f.write('\t'.join(head) + '\n')
        for r in body:
            w = r[wi]
            if w in table:
                r[ji], r[ri] = table[w]
            elif not r[ti]:
                r[ji], r[ri] = '該当なし', '型が付いていない'
            else:
                r[ji], r[ri] = OK, '最も普通の意味が %s の名称に当てはまる（より明らかな型は無い）' % (
                    names.get(r[ti], r[ti]))
            f.write('\t'.join(r) + '\n')
fill('sample60_raw.tsv', 'sample60.tsv', S60)
fill('direct_raw.tsv', 'direct_judge.tsv', DIRECT)
