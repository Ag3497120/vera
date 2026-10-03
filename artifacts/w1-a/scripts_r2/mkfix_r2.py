# writes tests/bank_score/fixtures/B1_v2_r2/items.jsonl (data only; the entry is not imported)
import json
items = []
def item(id_, text, clauses, must_not, lang='ja', relations=None, readable=True, phen='自作の見本(第2ラウンド。入口の誤読の型)'):
    items.append({'id': id_, 'lang': lang, 'category': 'cat', 'phenomenon': phen, 'difficulty': 1, 'rationale': '自作', 'unit': 'self_made_r2',
                  'behavior': 'read' if readable else 'abstain', 'input': text, 'traps': [],
                  'expect': {'readable': readable, 'clauses': clauses, 'relations': relations or [], 'must_not': must_not}})
def c(pred, roles, pol='+', tense='past', mod=None, voice='active'):
    return {'predicate': pred, 'roles': roles, 'polarity': pol, 'tense': tense, 'modality': mod, 'voice': voice}
# --- 授受動詞: a converse verb must not replace the written one (convention 3, 4.6)
item('FX2-J01', '兄は弟から本を借りた。', [c('借りる', {'recipient': '兄', 'agent': '弟', 'patient': '本'})], [{'clause': 0, 'field': 'predicate', 'value': '貸す'}])
item('FX2-J02', '兄は姉から手紙を受け取った。', [c('受け取る', {'recipient': '兄', 'agent': '姉', 'patient': '手紙'})], [{'clause': 0, 'field': 'predicate', 'value': '渡す'}])
item('FX2-J03', '弟は先生に英語を教わった。', [c('教わる', {'recipient': '弟', 'agent': '先生', 'patient': '英語'})], [{'clause': 0, 'field': 'predicate', 'value': '教える'}])
item('FX2-J04', '兄は弟に本をもらった。', [c('もらう', {'recipient': '兄', 'agent': '弟', 'patient': '本'})], [{'clause': 0, 'field': 'predicate', 'value': 'あげる'}])
item('FX2-J05', '叔父が弟に時計をくれた。', [c('くれる', {'agent': '叔父', 'recipient': '弟', 'patient': '時計'})], [{'clause': 0, 'field': 'predicate', 'value': 'もらう'}])
# --- 存在・居住の場所は place (goal ではない)
item('FX2-J06', '兄は東京に住んでいる。', [c('住む', {'agent': '兄', 'place': '東京'}, tense='nonpast')], [{'clause': 0, 'role': 'goal', 'value': '東京'}])
item('FX2-J07', '姉は大阪に滞在した。', [c('滞在する', {'agent': '姉', 'place': '大阪'})], [{'clause': 0, 'role': 'goal', 'value': '大阪'}])
# --- 受身の から 句は agent (規約 4.6)。出どころの場所だけ source
item('FX2-J08', '結果が事務局から通知された。', [c('通知する', {'patient': '結果', 'agent': '事務局'}, voice='passive')], [{'clause': 0, 'role': 'source', 'value': '事務局'}])
item('FX2-J09', '依頼書が本部から配られた。', [c('配る', {'patient': '依頼書', 'agent': '本部'}, voice='passive')], [{'clause': 0, 'role': 'source', 'value': '本部'}])
item('FX2-J10', '荷物が広島から送られた。', [c('送る', {'patient': '荷物', 'source': '広島'}, voice='passive')], [{'clause': 0, 'role': 'agent', 'value': '広島'}])
# --- 物は動作主ではない
item('FX2-J11', 'ドラムに皮が張られた。', [c('張る', {'patient': '皮', 'place': 'ドラム'}, voice='passive')], [{'clause': 0, 'role': 'agent', 'value': 'ドラム'}])
item('FX2-J12', 'ソファに布が掛けられた。', [c('掛ける', {'patient': '布', 'place': 'ソファ'}, voice='passive')], [{'clause': 0, 'role': 'agent', 'value': 'ソファ'}])
# --- 変換の動詞の に 句: 人は result ではない
item('FX2-J13', '祖母が昔話を孫娘に言い換えた。', [c('言い換える', {'agent': '祖母', 'patient': '昔話', 'recipient': '孫娘'})], [{'clause': 0, 'role': 'result', 'value': '孫娘'}])
item('FX2-J14', '兄が文章を英語に訳した。', [c('訳す', {'agent': '兄', 'patient': '文章', 'result': '英語'})], [{'clause': 0, 'role': 'recipient', 'value': '英語'}])
# --- 移動の動詞: 目的は goal ではない / 場所は goal
item('FX2-J15', '母は釣りに行った。', [c('行く', {'agent': '母'})], [{'clause': 0, 'role': 'goal', 'value': '釣り'}])
item('FX2-J16', '妹が図書館へ行った。', [c('行く', {'agent': '妹', 'goal': '図書館'})], [{'clause': 0, 'role': 'goal', 'value': '妹'}])
item('FX2-J17', '兄が友人に手紙を渡した。', [c('渡す', {'agent': '兄', 'recipient': '友人', 'patient': '手紙'})], [{'clause': 0, 'role': 'recipient', 'value': '手紙'}])
item('FX2-J18', '雨が降った。', [c('降る', {'entity': '雨'})], [{'clause': 0, 'role': 'agent', 'value': '雨'}])
item('FX2-J19', '犬が走った。', [c('走る', {'agent': '犬'})], [{'clause': 0, 'role': 'entity', 'value': '犬'}])
item('FX2-J20', '母が窓を開けなかった。', [c('開ける', {'agent': '母', 'patient': '窓'}, pol='-')], [{'clause': 0, 'field': 'polarity', 'value': '+'}])
# --- English
item('FX2-E01', 'Rain stopped.', [c('stop', {'entity': 'Rain'})], [{'clause': 0, 'role': 'agent', 'value': 'Rain'}], lang='en')
item('FX2-E02', 'Snow fell.', [c('fall', {'entity': 'Snow'})], [{'clause': 0, 'role': 'agent', 'value': 'Snow'}], lang='en')
item('FX2-E03', 'Prices dropped.', [c('drop', {'entity': 'Prices'})], [{'clause': 0, 'role': 'agent', 'value': 'Prices'}], lang='en')
item('FX2-E04', 'Ann taught Ben French.', [c('teach', {'agent': 'Ann', 'recipient': 'Ben', 'patient': 'French'})], [{'clause': 0, 'role': 'patient', 'value': 'Ben French'}], lang='en')
item('FX2-E05', 'Ben sent the report to Ann.', [c('send', {'agent': 'Ben', 'patient': 'report', 'recipient': 'Ann'})], [{'clause': 0, 'role': 'recipient', 'value': 'report'}], lang='en')
item('FX2-E06', 'The manager hired a clerk.', [c('hire', {'agent': 'manager', 'patient': 'clerk'})], [{'clause': 0, 'role': 'agent', 'value': 'clerk'}], lang='en')
item('FX2-E07', 'Ann received a letter from Ben.', [c('receive', {'recipient': 'Ann', 'agent': 'Ben', 'patient': 'letter'})], [{'clause': 0, 'role': 'patient', 'value': 'Ben'}], lang='en')
item('FX2-E08', 'The dog chased the cat.', [c('chase', {'agent': 'dog', 'patient': 'cat'})], [{'clause': 0, 'role': 'agent', 'value': 'cat'}], lang='en')
# --- 読めない入力 (規約 7: 1 定型, 2 感動詞, 3 断片, 4 語列, 5 造語の述語, 6 壊れた入力)
for i, (t, lang) in enumerate([('Thank you very much.', 'en'), ('Oh!', 'en'), ('お疲れさまでした。', 'ja'), ('あれ、まあ。', 'ja'),
                               ('駅の近くの古い店。', 'ja'), ('机が静かに走って緑の。', 'ja'), ('兄が窓をうぬぼった。', 'ja'), ('Ann gorped the door.', 'en')], 1):
    item(f'FX2-U{i:02d}', t, [], [{'readable': True}], lang=lang, readable=False)
with open('tests/bank_score/fixtures/B1_v2_r2/items.jsonl', 'w', encoding='utf-8') as f:
    for o in items: f.write(json.dumps(o, ensure_ascii=False) + '\n')
print(len(items))
