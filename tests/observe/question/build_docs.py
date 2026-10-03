"""検査データの文書 10 本を書き出す（W3-c2。手で書いた文。読解器・観測器は呼ばない）。出力: docs/QD01.jsonl ... QD10.jsonl"""
import json, os
HERE = os.path.dirname(os.path.abspath(__file__))
DOCS = {
 'QD01': ('ja', ['先生が生徒に地図を渡した。', '校長が生徒に地図を渡した。', '生徒は先生に手紙を送った。', '先生は駅で地図を渡さなかった。',
                 '誰が鍵を持っているか。', '生徒が図書館へ行った。', '先生が本を読む。', '地図は古かった。', '校長が地図を渡さなかった。']),
 'QD02': ('ja', ['駅員が客に切符を渡した。', '駅員が客に切符を渡さなかった。', '運転手が客に切符を渡す。', '社長が客にカメラを売った。',
                 '社長が客に車を売った。', '客が駅へ行った。', '切符が渡された。', '客は急いでいたので駅員は切符を渡した。', '社長は笑顔で客に車を売った。']),
 'QD03': ('ja', ['先生は生徒にＰＣを貸した。', '先生は生徒にPCを貸した。', 'Ａ社が生徒に地図を渡した。', 'A社が生徒に地図を渡した。',
                 'Ｘが生徒に地図を渡した。', '弟が兄に本を貸した。', '兄が弟に本を貸した。', '誰が地図を渡したのか。']),
 'QD04': ('ja', ['画家が絵を描いた。', '画家は寺で絵を描いた。', '漁師が網を作った。', '漁師は港から魚を送った。', '農夫は市場で馬を売った。',
                 '農夫が粉屋に馬を売った。', '歌手が歌を歌った。', '歌手は舞台で歌を歌った。', '大工が家を建てた。']),
 'QD05': ('ja', ['先生は朝に本を読んだ。', '先生は夜に本を読んだ。', '看護師は朝に薬を渡した。', '先生は月曜日に地図を渡した。', '先生は三時に来た。',
                 '母は台所で料理を作った。', '母は弁当を作りました。', '姉は店で服を買った。', '兄は新聞を買う。', '父は昨日手紙を書いた。']),
 'QD06': ('ja', ['犬が公園から走った。', '犬が森から走った。', '社長が会社から手紙を送った。', '医者は病院から薬を送った。', '店員が駅から荷物を送った。',
                 '犬が公園へ走った。', '店員が客に袋を渡さなかった。', '鳥が空を飛んだ。']),
 'QD07': ('ja', ['兄は弟に鉛筆を貸した。', '妹が姉に手紙を送った。', '医者が看護師に薬を渡した。', '医者が患者に薬を渡した。', '弟は図書館で本を読んだ。',
                 '弟は図書館で本を読みました。', '弟は兄に鉛筆を貸した。', '王が民に金貨を配った。', '弟は歩いて図書館へ行った。']),
 'QD08': ('en', ['The farmer bought a horse.', 'The clerk reads the newspaper.', 'The sailor wrote a letter.', 'The teacher gave the map to the student.',
                 'The principal gave the map to the student.', 'The doctor did not give the medicine to the patient.', 'X sold the map to the chef.',
                 'The miller sold the horse to the baker.']),
 'QD09': ('en', ['The chef sold the map to the student.', 'The nurse gave the book to a child.', 'The mayor built the bridge.', 'The pilot flew the plane.',
                 'The painter painted the wall.', 'The captain did not sell the ship.', 'The student sent a letter to the teacher.',
                 'Who gave the map to the student?', 'The engineer built a bridge and the mayor opened it.']),
 'QD10': ('en', ['The teacher gave the student a map.', 'The gardener plants the roses.', 'The student sent a letter to the teacher.',
                 'The principal sent a letter to the teacher.', 'The clerk reads the newspaper.', 'The sailor wrote a letter.',
                 'The farmer bought a horse because the market was open.']),
}
os.makedirs(os.path.join(HERE, 'docs'), exist_ok=True)
for name, (lang, sents) in DOCS.items():
    with open(os.path.join(HERE, 'docs', name + '.jsonl'), 'w', encoding='utf-8') as f:
        for i, t in enumerate(sents, 1):
            f.write(json.dumps({'id': '%s-S%02d' % (name, i), 'text': t, 'lang': lang}, ensure_ascii=False) + '\n')
