# writes tests/reading_soundness/ja_r5.jsonl and a3_r5.jsonl  (data only; the reader is not imported)
import json
out = []
def add(id_, typ, text, kind, alts=None, note=''):
    g = {'kind': kind}
    if alts is not None: g['alternatives'] = alts
    out.append({'id': id_, 'type': typ, 'text': text, 'gold': g, 'note': note})
def cl(pred, roles, pol='+'): return {'predicate': [pred] if isinstance(pred, str) else pred, 'polarity': pol, 'roles': roles}

# R1: passive に-phrase is a katakana word naming a thing (a corpus word list is not a class of persons)
r1 = [('ドラムに皮が張られた。', '張る', '皮', 'ドラム'), ('バイオリンに弦が付けられた。', '付ける', '弦', 'バイオリン'),
      ('テレビに保護シートが貼られた。', '貼る', '保護シート', 'テレビ'), ('ラジオに印が付けられた。', '付ける', '印', 'ラジオ'),
      ('コンピュータに装置が取り付けられた。', '取り付ける', '装置', 'コンピュータ'), ('ソファに布が掛けられた。', '掛ける', '布', 'ソファ'),
      ('ベッドにシーツが敷かれた。', '敷く', 'シーツ', 'ベッド'), ('ストーブに薪が入れられた。', '入れる', '薪', 'ストーブ'),
      ('プリンタに用紙が差し込まれた。', '差し込む', '用紙', 'プリンタ'), ('マイクに布が巻かれた。', '巻く', '布', 'マイク'),
      ('フルートに飾りが付けられた。', '付ける', '飾り', 'フルート'), ('エアコンにフィルターが取り付けられた。', '取り付ける', 'フィルター', 'エアコン'),
      ('トランペットに黒い布が掛けられた。', '掛ける', '黒い布', 'トランペット'), ('クラリネットに印が刻まれた。', '刻む', '印', 'クラリネット')]
for i, (t, p, pat, loc) in enumerate(r1, 1):
    add(f'R1-{i:02d}', 'R1', t, 'clauses', [[cl(p, {'patient': pat, 'place': loc})], [cl(p, {'patient': pat, 'location': loc})]],
        '受身の に 句がカタカナ語の物。人ではないので動作主ではない(場所・対象)。読めなければ未対応')
# R1c: controls, a person as the agent of a passive
r1c = [('兄に弟が叱られた。', '叱る', '弟', '兄'), ('教師に生徒が褒められた。', '褒める', '生徒', '教師'), ('警備員に男が呼び止められた。', '呼び止める', '男', '警備員'),
       ('隣人に犬が可愛がられた。', '可愛がる', '犬', '隣人')]
for i, (t, p, pat, ag) in enumerate(r1c, 1):
    add(f'R1c-{i:02d}', 'R1c', t, 'clauses', [[cl(p, {'patient': pat, 'agent': ag})]], '対照: 人が受身の動作主(未対応でも誤読ではない)')
# R2: a verb of conversion on a thing + a に-phrase that shows no result type (a person the work is done for): never `result`
r2 = [('祖母が昔話を孫娘に言い換えた。', '言い換える', '昔話', '孫娘'), ('母が手紙を嫁に書き換えた。', '書き換える', '手紙', '嫁'),
      ('店主が説明書を女将に書き換えた。', '書き換える', '説明書', '女将'), ('叔父が報告を居候に翻訳した。', '翻訳する', '報告', '居候'),
      ('兄が文章を若旦那に訳した。', '訳す', '文章', '若旦那'), ('父が計画を跡取りに読み替えた。', '読み替える', '計画', '跡取り'),
      ('師匠が楽譜を新弟子に書き換えた。', '書き換える', '楽譜', '新弟子'), ('祖父が手順を家来に言い換えた。', '言い換える', '手順', '家来'),
      ('伯母が献立を新妻に変えた。', '変える', '献立', '新妻'), ('先輩が規則を舅に置き換えた。', '置き換える', '規則', '舅'),
      ('姉が案内を姑に訳した。', '訳す', '案内', '姑'), ('職員が通知を孫に切り替えた。', '切り替える', '通知', '孫')]
for i, (t, p, pat, who) in enumerate(r2, 1):
    add(f'R2-{i:02d}', 'R2', t, 'clauses', [[cl(p, {'agent': t[:t.index('が')], 'patient': pat, 'recipient': who})],
                                            [cl(p, {'agent': t[:t.index('が')], 'patient': pat, 'beneficiary': who})]],
        '変換の動詞＋物の目的語＋結果の型の証拠が無い人の に 句。誰かのために行う(受け手)。result ではない。読めなければ未対応')
# R2c: controls, evidence of a result type
r2c = [('兄が文章を英語に訳した。', '訳す', '文章', '英語', '兄'), ('班長が名簿を三つの班に分類した。', '分類する', '名簿', '三つの班', '班長'),
       ('教師が本文を方言に書き換えた。', '書き換える', '本文', '方言', '教師'), ('係員が荷物を箱に分けた。', '分ける', '荷物', '箱', '係員'),
       ('職員が資料を一覧に整理した。', '整理する', '資料', '一覧', '職員')]
for i, (t, p, pat, res, ag) in enumerate(r2c, 1):
    add(f'R2c-{i:02d}', 'R2c', t, 'clauses', [[cl(p, {'agent': ag, 'patient': pat, 'result': res})]], '対照: 結果の型の証拠がある(言語名・数+助数詞・助数詞可能の名詞・書式名詞)')
# R3: passive から-phrase that names a body (no evidence of a person suffix): the agent (convention 4.6); never the origin
r3 = [('本社から指示が出された。', '出す', '指示', '本社'), ('支店から通達が送られた。', '送る', '通達', '支店'), ('研究所から報告書が公表された。', '公表する', '報告書', '研究所'),
      ('協議会から声明が発表された。', '発表する', '声明', '協議会'), ('出版社から新刊が発売された。', '発売する', '新刊', '出版社'),
      ('本部から命令が伝えられた。', '伝える', '命令', '本部'), ('管理組合から案内が配られた。', '配る', '案内', '管理組合'),
      ('工房から作品が納められた。', '納める', '作品', '工房'), ('市役所から通知が届けられた。', '届ける', '通知', '市役所'),
      ('事業団から資金が提供された。', '提供する', '資金', '事業団'), ('製作所から部品が届けられた。', '届ける', '部品', '製作所'),
      ('運営会社から案内が出された。', '出す', '案内', '運営会社')]
for i, (t, p, pat, ag) in enumerate(r3, 1):
    add(f'R3-{i:02d}', 'R3', t, 'clauses', [[cl(p, {'patient': pat, 'agent': ag})]],
        '受身の から 句が組織名(人の接尾辞トークンで終わらない)。規約 4.6: から の句は agent。source ではない。読めなければ未対応')
r3c = [('畑から芋が掘り出された。', '掘り出す', '芋', '畑'), ('川から砂が運ばれた。', '運ぶ', '砂', '川'), ('庭から古い壺が掘り出された。', '掘り出す', '古い壺', '庭'),
       ('広島から荷物が送られた。', '送る', '荷物', '広島')]
for i, (t, p, pat, src) in enumerate(r3c, 1):
    add(f'R3c-{i:02d}', 'R3c', t, 'clauses', [[cl(p, {'patient': pat, 'source': src})]], '対照: から 句が行為できない場所(出どころ)。未対応でも誤読ではない')
# R4: the end point of a verb of motion is no place and no person (a purpose / an activity): not a goal, not a recipient; the convention has no role
# for it, so a structured reading is wrong and "unsupported" is right
r4 = ['母は釣りに行った。', '弟は見学に来た。', '叔父は荷造りに戻った。', '姉は練習に向かった。', '兄は食事に出た。', '妹は勉強に行った。',
      '父は見回りに出た。', '先生は準備に戻った。', '彼は観光に来た。', '娘は遊びに行った。', '後輩は取材に向かった。', '祖母は昼寝に入った。']
for i, t in enumerate(r4, 1):
    add(f'R4-{i:02d}', 'R4', t, 'unsupported', None, '移動の動詞の に 句が目的・活動(場所でも人でもない)。到達点(goal)でも recipient でもない。規約に目的の役割が無いので未対応が正解')
r4c = [('妹が図書館へ行った。', '行く', '妹', '図書館'), ('兄が病院に着いた。', '着く', '兄', '病院'), ('母が公園に向かった。', '向かう', '母', '公園'),
       ('弟が教室へ戻った。', '戻る', '弟', '教室'), ('叔母が会議に出た。', '出る', '叔母', '会議')]
for i, (t, p, ag, gl) in enumerate(r4c, 1):
    add(f'R4c-{i:02d}', 'R4c', t, 'clauses', [[cl(p, {'agent': ag, 'recipient': gl})], [cl(p, {'agent': ag, 'goal': gl})], [cl(p, {'agent': ag, 'direction': gl})]],
        '対照: 場所(または集まり)が に/へ の終点。recipient / goal / direction のどれでも正(未対応も誤読ではない)')
with open('tests/reading_soundness/ja_r5.jsonl', 'w', encoding='utf-8') as f:
    for o in out: f.write(json.dumps(o, ensure_ascii=False) + '\n')
a3 = [('ドラムに皮が張られた。', '誰が皮を張った？', ['ドラム']), ('バイオリンに弦が付けられた。', '誰が弦を付けた？', ['バイオリン']),
      ('ストーブに薪が入れられた。', '誰が薪を入れた？', ['ストーブ']), ('ソファに布が掛けられた。', '誰が布を掛けた？', ['ソファ']),
      ('ベッドにシーツが敷かれた。', '誰がシーツを敷いた？', ['ベッド'])]
with open('tests/reading_soundness/a3_r5.jsonl', 'w', encoding='utf-8') as f:
    for i, (t, q, forb) in enumerate(a3, 1):
        f.write(json.dumps({'id': f'A3R5-{i:02d}', 'text': t, 'question': q, 'forbidden': forb}, ensure_ascii=False) + '\n')
print(len(out), 'rows')
