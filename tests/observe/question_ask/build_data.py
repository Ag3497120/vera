"""W3-c4 test data: writes the documents (AD01-AD10, docs/dir_ae), the placement and the questions by hand-written content.
Does not import verantyx. The truth of every question is a human judgement of the document, written before any run (docs/OBSERVATION.md, 事前登録 W3-c4).
Sentence ids are `<file>#<line>:<k>` read by a human from `cat -n` of the file (k = the k-th non-empty piece of the line when it is cut after 。 and after '. ')."""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent

DOCS = {
    'AD01.txt': ['看護師が医者に書類を渡した。', '医者が患者に薬を渡した。', '技師が橋を建てた。院長が会議室で資料を配った。', '患者は受付へ行った。',
                 '看護師は薬を渡さなかった。', '係員が患者に番号を渡した。', '院長は朝に手紙を書いた。', '技師は病院から機械を送った。'],
    'AD02.txt': ['# 町の記録', '', '農夫が市場で馬を売った。', '粉屋は農夫に小麦を渡さなかった。', '漁師が港から魚を送った。', '船長は漁師に網を貸した。',
                 '歌手が歌を歌った。', '農夫は市場で牛を売った。'],
    'AD03.txt': ['彼は「先生が地図を渡した。」と言った。', '校長が生徒に本を貸した。', '生徒は図書館で本を読んだ。', '母は「父が車を売った。」と話した。',
                 '父は朝に新聞を買った。', '校長は地図を渡さなかった。', '先生が生徒に本を貸した。'],
    'AD04.txt': ['先生は生徒にＰＣを貸した。', '先生は生徒にPCを貸した。', 'Ａ社が客に車を売った。', 'A社が客に車を売った。', '店員が客にカメラを売った。',
                 '社長は会社から手紙を送った。'],
    'AD05.txt': ['王が民に金貨を配った。大臣が民に穀物を配った。', '兵士は城へ行った。商人は城へ行った。', '王は宮殿で手紙を書いた。', '大臣は王に鍵を渡した。',
                 '画家は寺で絵を描いた。', '商人が兵士に剣を売った。'],
    'AD06.txt': ['教授が学生に資料を渡した。館長が学生に資料を渡した。', '館長は本を読んだ。案内係が客に地図を渡した。', '学生は教室で絵を描いた。', '館長は展示室へ行った。',
                 '警備員が客に鍵を貸した。', '案内係は地図を売らなかった。'],
    'AD07.txt': ['母は台所で料理を作った。父は店で服を買った。', '姉は図書館で本を読んだ。', '兄が妹に鉛筆を貸した。弟は兄に鉛筆を貸した。', '母は弁当を作りました。',
                 '父は新聞を買わなかった。', '姉は夜に手紙を書いた。', '姉が妹に鉛筆を貸した。'],
    'AD08.txt': ['The farmer sold the horse to the miller.', 'The teacher gave the map to the student. The principal gave the map to the student.',
                 'The sailor wrote a letter.', 'The clerk did not give the key to the guest.', 'The baker bought the flour.', 'The doctor read the report.',
                 'The pilot flew the plane.'],
    'AD09.txt': ['The mayor built the bridge.', 'The captain did not sell the ship.', 'The nurse gave the medicine to the child.',
                 'The student sent a letter to the teacher.', 'The chef cooked the soup.', 'The artist painted the wall.'],
    'AD10.txt': ['The gardener planted the roses.', 'The cook bought the flour. The waiter sold the tray to the guest.', 'The pilot flew the plane.',
                 'The sailor did not write the letter.', 'The editor sent a letter to the teacher.', 'The student sent a letter to the teacher.'],
    'dir_ae/AE01.txt': ['船頭が客に荷物を渡した。', '船頭は川から舟を送った。'],
    'dir_ae/AE02.txt': ['漁師が客に荷物を渡した。'],
}

B2DOCS = {
    'BA01.txt': ['森田課長が佐藤さんに報告書を渡した。佐藤さんは会議室で報告書を読んだ。', '田中部長は朝に会議へ行った。', '鈴木さんが顧客に見積書を送った。',
                 '顧客は見積書を読みました。', '森田課長は昼に資料を作った。山田さんが課長に資料を渡した。田中部長は資料を読まなかった。', '佐藤さんは東京から荷物を送った。',
                 '鈴木さんは駅で切符を買った。', '田中部長が山田さんに鍵を貸した。', '顧客は店で地図を買った。'],
    'BA02.txt': ['店長がお客に傘を売った。店員がお客に袋を渡した。', '店長は朝に店を開けた。', '配達員が店へ荷物を運んだ。', 'お客は傘を買いました。',
                 '店員は店でレジを打った。店長はお客に礼を言った。', '配達員は倉庫から荷物を送った。', 'お客が店長に手紙を書いた。', '店員は荷物を受け取らなかった。',
                 '店長は倉庫で傘を作った。'],
    'BA03.txt': ['先生が生徒に宿題を配った。', '生徒は教室で宿題を書いた。校長は職員室で新聞を読んだ。', '先生は放課後に生徒へ手紙を渡した。', '保護者が先生に花を贈った。',
                 '生徒は図書館で本を借りた。', '校長が保護者に案内を送った。', '保護者は案内を読んだ。', '先生は職員室で花を飾った。', '生徒は校庭へ走った。',
                 '先生は宿題を集めなかった。'],
    'BA04.txt': ['The manager sent the report to the director. The director read the report.', 'The assistant booked the room.',
                 'The customer bought the umbrella. The clerk gave the receipt to the customer.', 'The courier did not deliver the parcel.',
                 'The director wrote a memo.', 'The manager sold the license to the customer.', 'The assistant wrote the schedule.',
                 'The clerk sent a letter to the manager.', 'The customer read the receipt.'],
}

PERSON_JA = ('看護師 医者 患者 技師 院長 係員 農夫 粉屋 漁師 船長 歌手 校長 先生 生徒 母 父 社長 店員 客 王 民 大臣 兵士 商人 画家 教授 学生 館長 案内係 警備員 姉 兄 妹 弟 '
             '船頭 森田課長 課長 佐藤さん 田中部長 鈴木さん 顧客 山田さん 店長 お客 配達員 保護者').split()
PLACE_JA = '会議室 受付 病院 市場 港 図書館 城 宮殿 寺 展示室 教室 店 台所 会社 川 東京 駅 倉庫 職員室 校庭'.split()
ARTIFACT_JA = ('書類 薬 橋 資料 機械 手紙 番号 小麦 網 歌 本 地図 車 ＰＣ PC カメラ 金貨 鍵 絵 料理 服 鉛筆 新聞 弁当 荷物 舟 報告書 見積書 切符 傘 袋 レジ 宿題 花 案内').split()
ANIMAL_JA = '馬 牛 魚'.split()
PERSON_EN = ('teacher student principal sailor clerk guest baker doctor pilot miller mayor captain nurse child chef artist gardener cook waiter editor '
             'manager director assistant customer courier').split()
ARTIFACT_EN = 'map letter key flour report plane bridge ship medicine soup wall roses tray umbrella receipt room parcel memo schedule license'.split()
ANIMAL_EN = ['horse']
GROUP_ORG = ['Ａ社', 'A社']
# NOT placed on purpose (nouns that are the answer of a question whose type cannot be checked): 穀物 剣 farmer 会議
def placement():
    lem = {}
    for words, t in ((PERSON_JA + PERSON_EN, 'PERSON'), (PLACE_JA, 'PLACE'), (ARTIFACT_JA + ARTIFACT_EN, 'ARTIFACT'), (ANIMAL_JA + ANIMAL_EN, 'ANIMAL'), (GROUP_ORG, 'GROUP_ORG')):
        for w in words: lem[w] = {'state': 'DECIDED', 'origin': 'direct', 'types': [t]}
    return {'lemmas': dict(sorted(lem.items())), 'neighbors': {}}

Q = []
def q(doc, text, cat, kind, fillers=(), evidence=(), note='', docs=None, ext=()):
    docs = docs if docs is not None else ([doc] if doc else [])
    Q.append({'id': 'AQ%03d' % (len(Q) + 1), 'docs': docs, 'text': text, 'category': cat,
              'truth': {'kind': kind, 'fillers': list(fillers), 'evidence': list(evidence), 'extension_support': list(ext), 'unread_support': []}, 'note': note})
def one(doc, text, filler, ev, cat='one', note=''): q(doc, text, cat, 'ONE', [filler], ev, note)
def none(doc, text, cat='none', note=''): q(doc, text, cat, 'NONE', note=note)
def split(doc, text, fillers, ev, cat='split', note='', docs=None): q(doc, text, cat, 'SPLIT', fillers, ev, note, docs)
def ill(doc, text, kind='ILLFORMED', cat='illformed', note=''): q(doc, text, cat, kind, note=note)

# ---- AD01
d = 'AD01.txt'
one(d, '誰が患者に薬を渡した？', '医者', [d + '#2:1'], 'existing', 'ふつうの 3 腕の文。既存の経路が答えると見込む')
one(d, '看護師は医者に何を渡した？', '書類', [d + '#1:1'])
one(d, '誰が橋を建てた？', '技師', [d + '#3:1'], note='2 文を 1 行に書いた行の前の文')
one(d, '院長は会議室で何を配った？', '資料', [d + '#3:2'], note='2 文を 1 行に書いた行の後の文')
one(d, '患者はどこへ行った？', '受付', [d + '#4:1'])
one(d, '誰が薬を渡さなかった？', '看護師', [d + '#5:1'], note='否定の問いに否定の文')
one(d, '係員は患者に何を渡した？', '番号', [d + '#6:1'])
one(d, '技師は病院から何を送った？', '機械', [d + '#8:1'])
one(d, '院長は朝に何を書いた？', '手紙', [d + '#7:1'])
one(d, '誰が患者に番号を渡した？', '係員', [d + '#6:1'])
none(d, '医者は看護師に何を渡した？', note='役割が逆')
none(d, '誰が書類を送った？', note='書類は渡されただけ')
none(d, '看護師は患者に何を渡した？')
ill(d, '医者は患者に薬を渡したか？', 'YESNO', 'illformed', 'はい／いいえ疑問')
ill(d, '誰が誰に書類を渡した？', note='穴が 2 つ')
ill(d, '医者か看護師が薬を渡した？', note='AかB')
ill(d, '誰かが薬を渡した？', note='不定語')
ill(d, '今日の天気はどうですか？', note='文書と関係の無い読めない形')
ill(d, '医者が患者に薬を渡した。', 'ILLFORMED', 'declarative', '平叙文を質問として渡す')
q(None, '誰が患者に薬を渡した？', 'nodoc', 'NONE', note='文書なし', docs=[])
# ---- AD02
d = 'AD02.txt'
one(d, '誰が市場で馬を売った？', '農夫', [d + '#3:1'], note='見出しと空行のある文書。行番号は見出しを 1 行目と数える')
one(d, '誰が港から魚を送った？', '漁師', [d + '#5:1'])
one(d, '船長は漁師に何を貸した？', '網', [d + '#6:1'])
one(d, '誰が歌を歌った？', '歌手', [d + '#7:1'])
one(d, '誰が農夫に小麦を渡さなかった？', '粉屋', [d + '#4:1'], note='否定の問いに否定の文')
split(d, '農夫は市場で何を売った？', ['馬', '牛'], [d + '#3:1', d + '#8:1'])
none(d, '粉屋は農夫に何を渡した？', 'negonly', '否定の文しか無い命題を肯定で問う')
none(d, '誰が農夫に小麦を渡した？', 'negonly', '否定の文しか無い命題を肯定で問う')
none(d, '漁師は港から何を売った？')
q(None, '農夫は市場で何を売った？', 'nodoc', 'NONE', note='文書なし', docs=[])
# ---- AD03
d = 'AD03.txt'
one(d, '生徒は図書館で何を読んだ？', '本', [d + '#3:1'])
one(d, '父は朝に何を買った？', '新聞', [d + '#5:1'])
one(d, '校長は何を渡さなかった？', '地図', [d + '#6:1'], note='否定の問いに否定の文')
one(d, '先生は生徒に何を貸した？', '本', [d + '#7:1'])
one(d, '校長は生徒に何を貸した？', '本', [d + '#2:1'])
split(d, '誰が生徒に本を貸した？', ['校長', '先生'], [d + '#2:1', d + '#7:1'])
none(d, '誰が地図を渡した？', 'hearsay', '「先生が地図を渡した」は伝聞（文書は事実として述べない）。校長は渡さなかった')
none(d, '誰が車を売った？', 'hearsay', '「父が車を売った」は伝聞')
# ---- AD04
d = 'AD04.txt'
split(d, '先生は生徒に何を貸した？', ['ＰＣ', 'PC'], [d + '#1:1', d + '#2:1'], 'notation', '同じ物の全角／半角の表記違い。計画の写し（SURFACES_DIFFER）では TIE')
split(d, '誰が客に車を売った？', ['Ａ社', 'A社'], [d + '#3:1', d + '#4:1'], 'notation', '同じ会社の全角／半角の表記違い')
one(d, '店員は客に何を売った？', 'カメラ', [d + '#5:1'])
one(d, '誰が客にカメラを売った？', '店員', [d + '#5:1'])
one(d, '社長は会社から何を送った？', '手紙', [d + '#6:1'])
one(d, '誰が会社から手紙を送った？', '社長', [d + '#6:1'])
none(d, '社長は客に何を売った？')
none(d, '店員は生徒に何を貸した？')
# ---- AD05
d = 'AD05.txt'
one(d, '誰が民に金貨を配った？', '王', [d + '#1:1'])
one(d, '王は民に何を配った？', '金貨', [d + '#1:1'])
one(d, '王は宮殿で何を書いた？', '手紙', [d + '#3:1'])
one(d, '誰が王に鍵を渡した？', '大臣', [d + '#4:1'])
one(d, '画家は寺で何を描いた？', '絵', [d + '#5:1'])
split(d, '誰が城へ行った？', ['兵士', '商人'], [d + '#2:1', d + '#2:2'])
one(d, '大臣は民に何を配った？', '穀物', [d + '#1:2'], 'unplaced', '答えの名詞を配置に載せない（型を確かめられない）')
one(d, '商人は兵士に何を売った？', '剣', [d + '#6:1'], 'unplaced', '答えの名詞を配置に載せない')
none(d, '王は兵士に何を渡した？')
none(d, '誰が剣を買った？')
# ---- AD06
d = 'AD06.txt'
one(d, '館長は何を読んだ？', '本', [d + '#2:1'], note='既存の経路が読めない形（計画の F2 と同じ形）')
one(d, '誰が客に地図を渡した？', '案内係', [d + '#2:2'], 'existing', '既存の経路が答えると見込む（F2 の「誰が切符を渡した？」と同じ形）')
one(d, '案内係は客に何を渡した？', '地図', [d + '#2:2'], 'existing', '既存の経路が答えると見込む')
one(d, '館長はどこへ行った？', '展示室', [d + '#4:1'])
one(d, '誰が客に鍵を貸した？', '警備員', [d + '#5:1'])
one(d, '学生は教室で何を描いた？', '絵', [d + '#3:1'])
one(d, '案内係は何を売らなかった？', '地図', [d + '#6:1'], note='否定の問いに否定の文')
one(d, '教授は学生に何を渡した？', '資料', [d + '#1:1'])
split(d, '誰が学生に資料を渡した？', ['教授', '館長'], [d + '#1:1', d + '#1:2'])
none(d, '案内係は何を売った？', 'negonly', '否定の文しか無い命題を肯定で問う')
none(d, '警備員は客に何を渡した？')
# ---- AD07
d = 'AD07.txt'
one(d, '母は台所で何を作った？', '料理', [d + '#1:1'])
one(d, '誰が店で服を買った？', '父', [d + '#1:2'])
one(d, '誰が兄に鉛筆を貸した？', '弟', [d + '#3:2'], 'existing', '既存の経路が答えると見込む')
one(d, '兄は妹に何を貸した？', '鉛筆', [d + '#3:1'])
one(d, '父は何を買わなかった？', '新聞', [d + '#5:1'], note='否定の問いに否定の文')
one(d, '姉は夜に何を書いた？', '手紙', [d + '#6:1'])
one(d, '姉は図書館で何を読んだ？', '本', [d + '#2:1'])
one(d, '母は何を作りました？', '弁当', [d + '#4:1'])
split(d, '誰が妹に鉛筆を貸した？', ['兄', '姉'], [d + '#3:1', d + '#7:1'])
none(d, '妹は兄に何を貸した？')
# ---- AD08 (en)
d = 'AD08.txt'
split(d, 'Who gave the map to the student?', ['teacher', 'principal'], [d + '#2:1', d + '#2:2'])
one(d, 'Who wrote a letter?', 'sailor', [d + '#3:1'])
one(d, 'What did the sailor write?', 'letter', [d + '#3:1'])
one(d, 'Who bought the flour?', 'baker', [d + '#5:1'])
one(d, 'What did the baker buy?', 'flour', [d + '#5:1'])
one(d, 'What did the doctor read?', 'report', [d + '#6:1'])
one(d, 'Who flew the plane?', 'pilot', [d + '#7:1'], 'existing', '既存の経路が答えると見込む')
one(d, 'What did the farmer sell to the miller?', 'horse', [d + '#1:1'])
one(d, 'Who sold the horse to the miller?', 'farmer', [d + '#1:1'], 'unplaced', 'farmer を配置に載せない')
none(d, 'Who gave the key to the guest?', 'negonly', '否定の文しか無い命題を肯定で問う')
none(d, 'What did the clerk give to the guest?', 'negonly', '否定の文しか無い命題を肯定で問う')
ill(d, 'Did the baker buy the flour?', 'YESNO', 'illformed', 'はい／いいえ疑問')
ill(d, 'Who gave what to the student?', note='穴が 2 つ')
ill(d, 'The pilot flew the plane.', 'ILLFORMED', 'declarative', '平叙文を質問として渡す')
# ---- AD09 (en)
d = 'AD09.txt'
one(d, 'Who built the bridge?', 'mayor', [d + '#1:1'], 'existing', '既存の経路が答えると見込む')
one(d, 'What did the mayor build?', 'bridge', [d + '#1:1'])
one(d, 'Who gave the medicine to the child?', 'nurse', [d + '#3:1'])
one(d, 'What did the student send to the teacher?', 'letter', [d + '#4:1'])
one(d, 'Who painted the wall?', 'artist', [d + '#6:1'])
one(d, 'What did the artist paint?', 'wall', [d + '#6:1'])
one(d, 'Who cooked the soup?', 'chef', [d + '#5:1'])
none(d, 'Who sold the ship?', 'negonly', '否定の文しか無い命題を肯定で問う')
none(d, 'What did the captain sell?', 'negonly', '否定の文しか無い命題を肯定で問う')
ill(d, 'Did the mayor build the bridge?', 'YESNO', 'illformed', 'はい／いいえ疑問')
# ---- AD10 (en)
d = 'AD10.txt'
one(d, 'What did the waiter sell to the guest?', 'tray', [d + '#2:2'])
one(d, 'Who sold the tray to the guest?', 'waiter', [d + '#2:2'])
one(d, 'Who planted the roses?', 'gardener', [d + '#1:1'], note='planted は読解器に無い語かもしれない（読めなければ棄権）')
one(d, 'Who bought the flour?', 'cook', [d + '#2:1'])
none(d, 'What did the sailor write?', 'negonly', '否定の文しか無い命題を肯定で問う')
# ---- two documents / the same name twice / a directory
q(None, 'Who bought the flour?', 'twodoc', 'SPLIT', ['baker', 'cook'], ['AD08.txt#5:1', 'AD10.txt#2:1'], '文書 2 本にまたがって割れる', docs=['AD08.txt', 'AD10.txt'])
q(None, 'Who flew the plane?', 'twodoc', 'ONE', ['pilot'], ['AD08.txt#7:1', 'AD10.txt#3:1'], '文書 2 本が同じ答えを述べる', docs=['AD08.txt', 'AD10.txt'])
q(None, 'Who sent a letter to the teacher?', 'twodoc', 'SPLIT', ['student', 'editor'], ['AD09.txt#4:1', 'AD10.txt#5:1', 'AD10.txt#6:1'], '文書 2 本にまたがって割れる', docs=['AD09.txt', 'AD10.txt'])
q(None, 'Who wrote a letter?', 'twodoc', 'ONE', ['sailor'], ['AD08.txt#3:1'], '同じファイル名を 2 回渡す（STRUCTURE_INVALID を見込む）', docs=['AD08.txt', 'AD08.txt'])
q(None, '誰が客に荷物を渡した？', 'twodoc', 'SPLIT', ['船頭', '漁師'], ['AE01.txt#1:1', 'AE02.txt#1:1'], 'ディレクトリを渡す（中に 2 本）', docs=['dir_ae'])

# ---- B2-like (chat-like phrasing)
B = []
def b(doc, text, kind, fillers=(), evidence=(), note=''):
    B.append({'id': 'BQ%03d' % (len(B) + 1), 'docs': [doc], 'text': text, 'category': 'b2like',
              'truth': {'kind': kind, 'fillers': list(fillers), 'evidence': list(evidence), 'extension_support': [], 'unread_support': []}, 'note': note})
d = 'BA01.txt'
b(d, '佐藤さんに報告書を渡したのは誰ですか？', 'ONE', ['森田課長'], [d + '#1:1'])
b(d, '誰が佐藤さんに報告書を渡しましたか？', 'ONE', ['森田課長'], [d + '#1:1'])
b(d, '森田課長は佐藤さんに何を渡した？', 'ONE', ['報告書'], [d + '#1:1'])
b(d, '佐藤さんは会議室で何を読んだ？', 'ONE', ['報告書'], [d + '#1:2'])
b(d, '田中部長はどこへ行った？', 'ONE', ['会議'], [d + '#2:1'], '会議は配置に載せない')
b(d, '誰が顧客に見積書を送った？', 'ONE', ['鈴木さん'], [d + '#3:1'])
b(d, '顧客は何を読みましたか？', 'ONE', ['見積書'], [d + '#4:1'])
b(d, '誰が課長に資料を渡した？', 'ONE', ['山田さん'], [d + '#5:2'])
b(d, '田中部長は資料を読んだ？', 'YESNO', note='か が無いはい／いいえ疑問')
b(d, '田中部長は何を読まなかった？', 'ONE', ['資料'], [d + '#5:3'])
b(d, '佐藤さんはどこから荷物を送った？', 'ONE', ['東京'], [d + '#6:1'])
b(d, '鈴木さんは駅で何を買った？', 'ONE', ['切符'], [d + '#7:1'])
b(d, '山田さんに鍵を貸したのは誰か教えて。', 'ONE', ['田中部長'], [d + '#8:1'], '依頼の形')
b(d, '顧客は店で何を買った？', 'ONE', ['地図'], [d + '#9:1'])
b(d, '鈴木さんは顧客に何を渡した？', 'NONE')
d = 'BA02.txt'
b(d, '誰がお客に傘を売ったか教えて。', 'ONE', ['店長'], [d + '#1:1'], '依頼の形')
b(d, '誰がお客に傘を売った？', 'ONE', ['店長'], [d + '#1:1'])
b(d, '店員はお客に何を渡した？', 'ONE', ['袋'], [d + '#1:2'])
b(d, 'お客は何を買いましたか？', 'ONE', ['傘'], [d + '#4:1'])
b(d, '配達員はどこから荷物を送った？', 'ONE', ['倉庫'], [d + '#6:1'])
b(d, '誰が店長に手紙を書いた？', 'ONE', ['お客'], [d + '#7:1'])
b(d, 'お客は店長に何を書いた？', 'ONE', ['手紙'], [d + '#7:1'])
b(d, '店員は何を受け取らなかった？', 'ONE', ['荷物'], [d + '#8:1'])
b(d, '店員は何を受け取った？', 'NONE', note='否定の文しか無い命題を肯定で問う')
b(d, '店長は倉庫で何を作った？', 'ONE', ['傘'], [d + '#9:1'])
b(d, '店長はお客に何を売った？', 'ONE', ['傘'], [d + '#1:1'])
d = 'BA03.txt'
b(d, '誰が生徒に宿題を配った？', 'ONE', ['先生'], [d + '#1:1'])
b(d, '生徒は教室で何を書いた？', 'ONE', ['宿題'], [d + '#2:1'])
b(d, '校長は職員室で何を読んだ？', 'ONE', ['新聞'], [d + '#2:2'])
b(d, '誰が先生に花を贈ったか教えて。', 'ONE', ['保護者'], [d + '#4:1'], '依頼の形。贈るは読解器に無い語かもしれない')
b(d, '生徒は図書館で何を借りた？', 'ONE', ['本'], [d + '#5:1'])
b(d, '誰が保護者に案内を送った？', 'ONE', ['校長'], [d + '#6:1'])
b(d, '保護者は何を読んだ？', 'ONE', ['案内'], [d + '#7:1'])
b(d, '先生は何を集めなかった？', 'ONE', ['宿題'], [d + '#10:1'])
b(d, '先生は何を集めた？', 'NONE', note='否定の文しか無い命題を肯定で問う')
b(d, '生徒はどこへ走った？', 'ONE', ['校庭'], [d + '#9:1'])
b(d, '誰が職員室で花を飾った？', 'ONE', ['先生'], [d + '#8:1'])
d = 'BA04.txt'
b(d, 'Who sent the report to the director?', 'ONE', ['manager'], [d + '#1:1'])
b(d, 'Could you tell me who wrote the memo?', 'ONE', ['director'], [d + '#5:1'], '依頼の形')
b(d, 'What did the director read?', 'ONE', ['report'], [d + '#1:2'])
b(d, 'Who bought the umbrella?', 'ONE', ['customer'], [d + '#3:1'])
b(d, 'What did the clerk give to the customer?', 'ONE', ['receipt'], [d + '#3:2'])
b(d, 'Who delivered the parcel?', 'NONE', note='否定の文しか無い命題を肯定で問う（delivered は読めないかもしれない）')
b(d, 'Who sold the license to the customer?', 'ONE', ['manager'], [d + '#6:1'])
b(d, 'Who wrote the schedule?', 'ONE', ['assistant'], [d + '#7:1'])
b(d, 'What did the customer read?', 'ONE', ['receipt'], [d + '#9:1'])
b(d, 'Who sent a letter to the manager?', 'ONE', ['clerk'], [d + '#8:1'])

def write_lines(path, lines):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(''.join(l + '\n' for l in lines), encoding='utf-8')

def main():
    for name, lines in DOCS.items(): write_lines(HERE / 'docs' / name, lines)
    for name, lines in B2DOCS.items(): write_lines(HERE / 'b2like' / 'docs' / name, lines)
    (HERE / 'placement_ask.json').write_text(json.dumps(placement(), ensure_ascii=False, indent=1, sort_keys=True) + '\n', encoding='utf-8')
    (HERE / 'questions.jsonl').write_text(''.join(json.dumps(x, ensure_ascii=False) + '\n' for x in Q), encoding='utf-8')
    (HERE / 'b2like' / 'questions.jsonl').write_text(''.join(json.dumps(x, ensure_ascii=False) + '\n' for x in B), encoding='utf-8')
    print(len(Q), len(B))

if __name__ == '__main__':
    main()
