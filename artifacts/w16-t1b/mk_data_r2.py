"""W16-t1b 第 2 ラウンド（K817〜K819）の検査データ tests/reading_soundness/w16t1b_converse.jsonl の生成。期待は表から決め、実行結果から作らない。
使い方: python mk_data_r2.py <出力ディレクトリ> <基点の木> <python> <一時ディレクトリ>。gate は「基点が出来事として読み（節）、かつ最初の問いに ANSWER する文だけ true」（base_gate.py）。"""
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from base_gate import base_readable, base_answers
OUT, BASE, PYTHON, TMP = Path(sys.argv[1]), sys.argv[2], sys.argv[3], sys.argv[4]

def conv(i, key, ja, doc, qs, gate):
    return dict(id=f'cv-{key}-{i:02d}', kind='converse_modal', modality=key, kind_ja=ja, gate=gate, document=doc, questions=qs)

rows = []
# 転換の枠（借りる→貸す、もらう→与える）。主語の役は agent ではなく recipient。
D = [  # (modality, ja, document, questions)
 ('desire','願望','花子は本を借りたかった。',['誰が本を借りた？','花子は本を借りた？']),
 ('desire','願望','次郎は傘を借りたがっていた。',['誰が傘を借りた？','次郎は傘を借りた？']),
 ('desire','願望','美咲は友人から本をもらいたかった。',['誰が本をもらった？','美咲は本をもらった？']),
 ('potential','可能','花子は本を借りられた。',['誰が本を借りた？','花子は本を借りた？']),
 ('potential','可能','次郎が傘を借りられる。',['誰が傘を借りる？','次郎は傘を借りる？']),
 ('potential','可能','美咲も本を借りられた。',['誰が本を借りた？','美咲は本を借りた？']),
 ('potential','可能','花子は友人から本を借りられた。',['誰が本を借りた？','花子は本を借りた？']),
 ('desire','願望（作用域）','花子は本を借り、手紙を書きたかった。',['誰が本を借りた？','花子は本を借りた？']),
 ('desire','願望（作用域）','花子は本を借りて、手紙を書きたかった。',['誰が本を借りた？','花子は本を借りた？']),
 ('desire','願望（作用域）','次郎は友人から傘をもらい、荷物を運びたかった。',['誰が傘をもらった？','次郎は傘をもらった？']),
 ('desire','願望（作用域）','太郎は傘を借りて、窓を開けたがっていた。',['誰が傘を借りた？','太郎は傘を借りた？']),
 ('potential','可能（作用域）','花子は本を借り、箱を開けられた。',['誰が本を借りた？','花子は本を借りた？']),
 ('potential','可能（作用域）','次郎は傘を借りて、窓を開けられた。',['誰が傘を借りた？','次郎は傘を借りた？']),
 ('desire','願望（作用域・agent の先行節）','次郎は本を読み、絵を描きたかった。',['誰が本を読んだ？','次郎は本を読んだ？']),
]
docs = sorted({d[2] for d in D})
readable = base_readable(BASE, PYTHON, docs)
ans = dict(zip(docs, base_answers(BASE, PYTHON, [[d, next(x[3][0] for x in D if x[2] == d)] for d in docs], TMP)))
for i, (k, ja, doc, qs) in enumerate(D):
    # gate: 基点で出来事として読む文だけ true。作用域の行は先行の節が基点で読まれているので、その節に型が付く（同じ規則）。
    rows.append(conv(i, k, ja, doc, qs, bool(readable[doc] and ans[doc])))
P = [  # 受身（正しく読める）。期待は表（受身の動作主）。
 ('次郎は花子に褒められた。','誰が次郎を褒めた？','花子'), ('太郎は先生に叱られた。','誰が太郎を叱った？','先生'),
 ('翔太は直美に叱られた。','誰が翔太を叱った？','直美'), ('健太は先生に助けられた。','誰が健太を助けた？','先生'),
 ('由美は友人に見られた。','誰が由美を見た？','友人'), ('大輔は母に呼ばれた。','誰が大輔を呼んだ？','母'),
]
for i, (d, q, v) in enumerate(P):
    rows.append(dict(id=f'cvp-{i:02d}', kind='passive_control', document=d, questions=[dict(q=q, expect_values=[v])]))
C = [  # 可能動詞でない下一段・転換の枠の普通の文・主語の違う並列
 ('次郎は窓を開けた。','誰が窓を開けた？','次郎'), ('花子は資料を調べた。','誰が資料を調べた？','花子'),
 ('太郎は荷物を届けた。','誰が荷物を届けた？','太郎'), ('美咲は友人に写真を見せた。','誰が写真を見せた？','美咲'),
 ('先生は生徒に英語を教えた。','誰が英語を教えた？','先生'), ('花子は次郎から本を借りた。','誰が本を借りた？','花子'),
 ('花子は友人から本をもらった。','誰が本をもらった？','花子'), ('次郎は傘を借りた。','次郎は傘を借りた？','はい'),
 ('次郎は本を借りて、花子は絵を描きたかった。','誰が本を借りた？','次郎'),
]
for i, (d, q, v) in enumerate(C):
    rows.append(dict(id=f'cvi-{i:02d}', kind='ichidan_control', document=d, questions=[dict(q=q, expect_values=[v])]))
T = [('木村様が書類を運んだ。','誰が書類を運んだ？','木村様'), ('店員が小林さんに本を渡した。','店員は誰に本を渡した？','小林さん')]
for i, (d, q, v) in enumerate(T):
    rows.append(dict(id=f'cvt-{i:02d}', kind='title_control', document=d, questions=[dict(q=q, expect_values=[v])]))
R = [  # 範囲（合否に入れない）
 ('花子は先生に本を届けられた。','誰が本を届けた？'), ('次郎は友人から傘を借りられない。','誰が傘を借りた？'),
 ('花子は本を借りられなかった。','誰が本を借りた？'), ('次郎は小説を読み、窓を開けた。','誰が小説を読んだ？'),
]
for i, (d, q) in enumerate(R):
    rows.append(dict(id=f'cvr-{i:02d}', kind='range', document=d, questions=[q]))
(OUT / 'w16t1b_converse.jsonl').write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
import collections
print(collections.Counter(r['kind'] for r in rows), 'gate true:', sum(r.get('gate', False) for r in rows))
