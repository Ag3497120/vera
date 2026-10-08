# writes tests/reading_soundness/ja_r6.jsonl and tests/bank_score/fixtures/B1_v2_r3/items.jsonl (data only; the reader and the entry are not imported)
import json, os
W = '/Users/motonisihikoudai/Projects/vera-impl/wt/W1-a-S'
out = []
def add(id_, typ, text, kind, alts=None, note=''):
    g = {'kind': kind}
    if alts is not None: g['alternatives'] = alts
    out.append({'id': id_, 'type': typ, 'text': text, 'gold': g, 'note': note})
def cl(pred, roles, pol='+'): return {'predicate': [pred] if isinstance(pred, str) else pred, 'polarity': pol, 'roles': roles}

# S1: a verb that can be transitive, its object left out, and a person in the に-phrase: the person is who the work is done for (recipient /
# beneficiary), never what something becomes (result). Unsupported is also right.
s1 = [('通訳が依頼人に訳した。', '訳す', '通訳', '依頼人'), ('講師が初心者に言い換えた。', '言い換える', '講師', '初心者'),
      ('記者が読者に書き換えた。', '書き換える', '記者', '読者'), ('弁護士が被告に翻訳した。', '翻訳する', '弁護士', '被告'),
      ('司会者が観客に言い換えた。', '言い換える', '司会者', '観客'), ('医師が患者に読み替えた。', '読み替える', '医師', '患者'),
      ('兄が妹に翻訳した。', '翻訳する', '兄', '妹'), ('案内人が旅行者に言い換えた。', '言い換える', '案内人', '旅行者'),
      ('秘書が上司に書き換えた。', '書き換える', '秘書', '上司'), ('翻訳者が子どもに訳した。', '訳す', '翻訳者', '子ども'),
      ('先輩が後輩に読み替えた。', '読み替える', '先輩', '後輩'), ('解説者が視聴者に言い換えた。', '言い換える', '解説者', '視聴者'),
      ('司書が利用者に翻訳した。', '翻訳する', '司書', '利用者'), ('祖母が曾孫に訳した。', '訳す', '祖母', '曾孫'),
      ('老人が居候に言い換えた。', '言い換える', '老人', '居候'), ('隠居が嫡男に書き換えた。', '書き換える', '隠居', '嫡男')]
for i, (t, p, ag, who) in enumerate(s1, 1):
    add(f'S1-{i:02d}', 'S1', t, 'clauses', [[cl(p, {'agent': ag, 'recipient': who})], [cl(p, {'agent': ag, 'beneficiary': who})]],
        '他動詞の目的語が省略された文＋人の に 句。誰かのために行う(受け手)。result(何かに変わる先)ではない。読めなければ未対応')
# S1c: controls, a verb with no transitive use (the subject itself becomes something): result needs no further evidence
s1c = [('姉は弁護士になった。', 'なる', '姉', '弁護士'), ('兄は教員に変わった。', '変わる', '兄', '教員'), ('友人は医師になった。', 'なる', '友人', '医師'),
       ('彼は市長になった。', 'なる', '彼', '市長'), ('弟は技術者に成長した。', '成長する', '弟', '技術者')]
for i, (t, p, ag, res) in enumerate(s1c, 1):
    add(f'S1c-{i:02d}', 'S1c', t, 'clauses', [[cl(p, {'agent': ag, 'result': res})]], '対照: 目的語を取らない変化の動詞(なる・変わる 等)。に 句は結果。未対応でも誤読ではない')
# S4: a family name + 家 in the に-phrase of a passive of placing/displaying: the house (or the people) is where it is put, never the agent
s4 = [('絵が伊藤家に飾られた。', '飾る', '絵', '伊藤家'), ('提灯が小林家に吊るされた。', '吊るす', '提灯', '小林家'), ('荷物が加藤家に置かれた。', '置く', '荷物', '加藤家'),
      ('家宝が吉田家に保管された。', '保管する', '家宝', '吉田家'), ('標識が山本家に立てられた。', '立てる', '標識', '山本家'),
      ('皿が松本家に並べられた。', '並べる', '皿', '松本家'), ('掛け軸が井上家に収められた。', '収める', '掛け軸', '井上家'),
      ('若木が木村家に植えられた。', '植える', '若木', '木村家'), ('旗が清水家に掲げられた。', '掲げる', '旗', '清水家'),
      ('壺が斎藤家に据えられた。', '据える', '壺', '斎藤家'), ('衝立が森家に置かれた。', '置く', '衝立', '森家'),
      ('鉢植えが石川家に並べられた。', '並べる', '鉢植え', '石川家'), ('表彰状が橋本家に飾られた。', '飾る', '表彰状', '橋本家')]
for i, (t, p, pat, loc) in enumerate(s4, 1):
    add(f'S4-{i:02d}', 'S4', t, 'clauses', [[cl(p, {'patient': pat, 'place': loc})], [cl(p, {'patient': pat, 'location': loc})]],
        '受身の に 句が 姓+家。「その家の人々」でも「その家(建物)」でもある。動作主ではない(場所または未定)。読めなければ未対応')
# S4c: controls, a common noun + 家 is a person in every sense: the agent of a passive
s4c = [('評論家に感想が求められた。', '求める', '感想', '評論家'), ('小説家に原稿が依頼された。', '依頼する', '原稿', '小説家'),
       ('画家に作品が褒められた。', '褒める', '作品', '画家'), ('建築家に図面が見せられた。', '見せる', '図面', '建築家')]
for i, (t, p, pat, ag) in enumerate(s4c, 1):
    add(f'S4c-{i:02d}', 'S4c', t, 'clauses', [[cl(p, {'patient': pat, 'agent': ag})], [cl(p, {'patient': pat, 'recipient': ag})]],
        '対照: 普通名詞+家は人(すべての語義)。受身の に 句の動作主(見せる は受け手)。未対応でも誤読ではない')
with open(f'{W}/tests/reading_soundness/ja_r6.jsonl', 'w', encoding='utf-8') as f:
    for o in out: f.write(json.dumps(o, ensure_ascii=False) + '\n')

# ---- the entry fixture (B1 v2 form)
items = []
def item(id_, text, clauses, must_not, lang='ja', readable=True):
    items.append({'id': id_, 'lang': lang, 'category': 'cat', 'phenomenon': '自作の見本(第3ラウンド。入口の誤読の型)', 'difficulty': 1, 'rationale': '自作',
                  'unit': 'self_made_r3', 'behavior': 'read' if readable else 'abstain', 'input': text, 'traps': [],
                  'expect': {'readable': readable, 'clauses': clauses, 'relations': [], 'must_not': must_not}})
def c(pred, roles, pol='+', tense='past', mod=None, voice='active'):
    return {'predicate': pred, 'roles': roles, 'polarity': pol, 'tense': tense, 'modality': mod, 'voice': voice}
item('FX3-J01', '社長が社員に叱られた。', [c('叱る', {'patient': '社長', 'agent': '社員'}, voice='passive')], [{'clause': 0, 'field': 'voice', 'value': 'active'}])
item('FX3-J02', '少年が教師に褒められた。', [c('褒める', {'patient': '少年', 'agent': '教師'}, voice='passive')], [{'clause': 0, 'role': 'agent', 'value': '少年'}])
item('FX3-J03', '皿が割られた。', [c('割る', {'patient': '皿'}, voice='passive')], [{'clause': 0, 'field': 'voice', 'value': 'active'}])
item('FX3-J04', '通訳が依頼人に訳した。', [c('訳す', {'agent': '通訳', 'recipient': '依頼人'})], [{'clause': 0, 'role': 'result', 'value': '依頼人'}])
item('FX3-J05', '講師が初心者に言い換えた。', [c('言い換える', {'agent': '講師', 'recipient': '初心者'})], [{'clause': 0, 'role': 'result', 'value': '初心者'}])
item('FX3-J06', '兄が妹に翻訳した。', [c('翻訳する', {'agent': '兄', 'recipient': '妹'})], [{'clause': 0, 'role': 'result', 'value': '妹'}])
item('FX3-J07', '姉は弁護士になった。', [c('なる', {'agent': '姉', 'result': '弁護士'})], [{'clause': 0, 'role': 'recipient', 'value': '弁護士'}])
item('FX3-J08', '絵が伊藤家に飾られた。', [c('飾る', {'patient': '絵', 'place': '伊藤家'}, voice='passive')], [{'clause': 0, 'role': 'agent', 'value': '伊藤家'}])
item('FX3-J09', '旗が清水家に掲げられた。', [c('掲げる', {'patient': '旗', 'place': '清水家'}, voice='passive')], [{'clause': 0, 'role': 'agent', 'value': '清水家'}])
item('FX3-J10', '評論家に感想が求められた。', [c('求める', {'patient': '感想', 'agent': '評論家'}, voice='passive')], [{'clause': 0, 'role': 'patient', 'value': '評論家'}])
item('FX3-J11', '店主が客に怒られた。', [c('怒る', {'patient': '店主', 'agent': '客'}, voice='passive')], [{'clause': 0, 'field': 'voice', 'value': 'active'}])
item('FX3-E01', 'Ann sent the package to London.', [c('send', {'agent': 'Ann', 'patient': 'package', 'goal': 'London'})], [{'clause': 0, 'role': 'recipient', 'value': 'London'}], lang='en')
item('FX3-E02', 'The letter was sent to Paris.', [c('send', {'patient': 'letter', 'goal': 'Paris'}, voice='passive')], [{'clause': 0, 'role': 'recipient', 'value': 'Paris'}], lang='en')
item('FX3-E03', 'Lisa sent Paul a message.', [c('send', {'agent': 'Lisa', 'recipient': 'Paul', 'patient': 'message'})], [{'clause': 0, 'role': 'patient', 'value': 'Paul'}], lang='en')
item('FX3-E04', 'Tom shipped the crate to Berlin.', [c('ship', {'agent': 'Tom', 'patient': 'crate', 'goal': 'Berlin'})], [{'clause': 0, 'role': 'recipient', 'value': 'Berlin'}], lang='en')
item('FX3-E05', 'Ben handed the keys to Dana.', [c('hand', {'agent': 'Ben', 'patient': 'keys', 'recipient': 'Dana'})], [{'clause': 0, 'role': 'patient', 'value': 'Dana'}], lang='en')
item('FX3-E06', 'Kate showed the photo to them.', [c('show', {'agent': 'Kate', 'patient': 'photo', 'recipient': 'them'})], [{'clause': 0, 'role': 'patient', 'value': 'them'}], lang='en')
os.makedirs(f'{W}/tests/bank_score/fixtures/B1_v2_r3', exist_ok=True)
with open(f'{W}/tests/bank_score/fixtures/B1_v2_r3/items.jsonl', 'w', encoding='utf-8') as f:
    for o in items: f.write(json.dumps(o, ensure_ascii=False) + '\n')
print(len(out), len(items), {t: sum(1 for o in out if o['type'] == t) for t in ('S1','S1c','S4','S4c')})
