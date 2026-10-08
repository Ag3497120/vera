"""Independent proof replay, source licensing, and evidence-universe audit.

This module never imports the producer or its matcher/arithmetic helpers.
The audit also detects applicable opponents and omitted alternative answers.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from decimal import Decimal, Inexact, localcontext
from fractions import Fraction
from typing import Any

from .semantic_coord import chunk, coordination_ok, own_subject_phrase, phrase_bounded, topic_phrase, tag
from .semantic_names import is_past_aux, name_split_in, tokens_covering
from .semantic_ir import (Clause, EventValue, Limit, Meter, Nominal, Pattern,
                          Plan, Proof, ProofNode, Quantity, Request, Variable, View, typed, unit_type)
from .semantic_validate import Invalid, occurrences, request_shape


class Rejected(Invalid):
    pass


class Conflict(Rejected):
    pass


_CONSTRUCTION_PARTICLES = {
    'capacity': ('として',), 'topic': ('について', 'では'),
    'by': ('によって', 'による', 'により'),
    'setting': ('における', 'において'), 'target': ('に対して',),
    'accompaniment': ('と共に', 'ともに'),
}
_TIME_DATE = r'(?:[0-9０-９]+年(?:[0-9０-９]{1,2}月(?:[0-9０-９]{1,2}日)?)?|(?:明治|大正|昭和|平成|令和)[0-9０-９]+年(?:[0-9０-９]{1,2}月(?:[0-9０-９]{1,2}日)?)?)'
_TIME_VALUE = re.compile(r'(?:' + _TIME_DATE + r'|[0-9０-９]+\s*(?:月|日|時|分|秒|曜日)|頃|ごろ|午前|午後|朝|昼|夜)\Z')
_TIME_COMMA_VALUE = re.compile(r'(?:' + _TIME_DATE + r'|[0-9０-９]+(?:月|日|時|分|秒|曜日))\Z')
# ---------------------------------------------------------------------------------------------------------------------
# W1-a: role-type checks. Written independently of semantic_reader (no import of it, none of its constants): this
# module re-tokenizes the clause body and applies its own rules, so a reader that mis-types a role cannot also
# mis-license it. Only the shared tokenizer and frames.read_all (already the baseline of the frame check) are used.
# ---------------------------------------------------------------------------------------------------------------------
_VT_NUM = r'[0-9０-９〇一二三四五六七八九十百千]'
_VT_NOMINAL_ROLES = frozenset(('agent', 'patient', 'recipient', 'causer', 'causee', 'entity', 'attribute', 'standard', 'context', 'result'))
_VT_EVENT_PARTICIPANTS = frozenset(('agent', 'patient', 'recipient', 'causer', 'causee'))
_VT_TIME_ADJUNCT_ROLES = frozenset(('goal', 'location', 'direction', 'place'))
_VT_ADDRESSEE_VERBS = frozenset((
    '渡す', '送る', '贈る', '与える', 'あげる', 'やる', 'くれる', '差し上げる', '配る', '届ける', '返す', '貸す', '預ける', '譲る', '売る',
    '払う', '支払う', '納める', '見せる', '示す', '伝える', '教える', '知らせる', '告げる', '言う', '話す', '語る', '尋ねる', '頼む',
    '勧める', '薦める', '答える', '授ける', '任せる', '委ねる', '申し出る', '打ち明ける', '謝る', '聞かせる', '挨拶する',
    '提出する', '提供する', '供給する', '支給する', '授与する', '寄付する', '寄贈する', '献上する', '配布する', '配達する', '発送する',
    '送付する', '納品する', '譲渡する', '報告する', '連絡する', '通知する', '説明する', '相談する', '質問する', '依頼する', '命令する',
    '申し込む', '問い合わせる', '訴える', '願い出る', '届け出る', '提案する', '提言する', '応募する', '出願する', '返信する', '回答する',
    '紹介する', '要求する', '要請する', '申請する', '約束する', '返事する', '回答する', '忠告する', '警告する', '感謝する', '指示する',
    '伝達する', '教授する', '貸与する', '付与する', '交付する', '通報する', '推薦する', '案内する'))
_VT_RESULT_VERBS = frozenset((
    '変える', '変わる', '変換する', '翻訳する', '訳す', '直す', '分ける', '分割する', 'まとめる', '整理する', '加工する', '変更する',
    '改める', '改造する', '改名する', '転換する', '転用する', '切り替える', '置き換える', '書き換える', '作り変える', '描き直す',
    '分類する', '区分する', '統合する', '統一する', '集約する', '要約する', '圧縮する', '変化する', '変質する', '編集する', '改訂する',
    '編成する', '再編する', '組み替える', '言い換える', '読み替える', '縮小する', '拡大する', '単純化する', '標準化する',
    'なる', '成る', '化す', '発展する', '昇進する', '昇格する', '降格する', '成長する', '進化する', '変貌する', '転じる', '転ずる', '移行する',
    '染める', '塗り替える', '塗りかえる', '塗り直す', '仕立てる', '仕上げる', '改装する', '模様替えする',
    '延期する', '延長する', '短縮する', '繰り上げる', '繰り下げる', '前倒しする', '後ろ倒しする', '先送りする', 'ずらす', '早める', '遅らせる',
    '振り替える', '延ばす', '繰り越す',
    '登用する', '任命する', '任用する', '起用する', '抜擢する', '選任する', '選出する', '認定する', '選ぶ', '指名する'))
_VT_APPOINTMENT_VERBS = frozenset(('登用する', '任命する', '任用する', '起用する', '抜擢する', '選任する', '選出する', '指名する', '認定する',
                                   '昇進する', '昇格する', '降格する'))      # confer a post/status on a person: the に-phrase is that status
_VT_PRODUCT_VERBS = frozenset(('加工する',))      # making a material into a product: the に-phrase is the product, never a person it is done for
_VT_INTRANSITIVE_CHANGE_VERBS = frozenset(('なる', '成る', '変わる', '化す', '変化する', '変質する', '成長する', '発展する', '進化する', '変貌する',
                                           '転じる', '転ずる', '移行する'))      # the subject itself changes; no transitive use (a verb with an object left out is not one of these)
_VT_SHARING_VERBS = frozenset(('分ける', '分割する', '分配する', '配分する'))
_VT_COUNTED_HEAD = re.compile(r'[0-9０-９〇一二三四五六七八九十百千万数]+[つ個組班人名種類グ]?の')
_VT_LOCATIVE_VERBS = frozenset(('住む', '滞在する', '位置する', '存在する'))
_VT_MOTION_VERBS = frozenset(('行く', '来る', '帰る', '戻る', '向かう', '着く', '入る', '出る', '進む', '移る', '渡る',
                              '出かける', '通う', '引っ越す', '到着する', '帰宅する', '出勤する', '出張する', '出発する', '旅立つ', '上陸する')) | _VT_LOCATIVE_VERBS
_VT_GOAL_VERBS = (_VT_MOTION_VERBS - _VT_LOCATIVE_VERBS) | frozenset(('送る', '届ける'))      # verbs of motion / sending whose に・へ-phrase is an end point
# nouns that name a spot or geographic feature and can never act: a から-phrase of a passive naming one is an origin, not a giver
_VT_SPOTS = frozenset(('駅', '公園', '部屋', '庭', '海', '山', '川', '湖', '島', '畑', '森', '谷', '海岸', '教室', '倉庫', '台所', '玄関', '屋上'))
_VT_GATHERINGS = frozenset(('会議', '会合', '集会', '総会', '授業', '講義', '試合', '式典', '面接', '宴会', '結婚式', '葬儀'))      # scheduled gatherings one goes to: an end point of going
_VT_ENCLOSING_VERBS = frozenset(('囲む', '含む', '覆う', '包む', '挟む', '抱く', '満たす', '占める', '隔てる', '区切る', '限る', '閉ざす', '取り巻く', '取り囲む'))
_VT_PLACEMENT_VERBS = frozenset((
    '置く', '入れる', '載せる', '乗せる', '積む', '掛ける', '吊るす', '貼る', '付ける', '立てる', '並べる', '差す', '挿す', '刺す', '埋める', '植える',
    '仕舞う', '収める', '収納する', '配置する', '設置する', '保管する', '運ぶ', '移す', '持つ', '持っていく', '持ってくる', 'しまう', '詰める', '注ぐ',
    '漬ける', '浸す', '飾る', '敷く', '留める', '結ぶ', '繋ぐ', 'つなぐ', '接続する', '投げる', '落とす',
    '置いてくる', '置いていく', '入れてくる', '入れていく'))
_VT_PLACE_ENDINGS = ('学校', '駅', '公園', '会社', '図書館', '病院', '市', '町', '県', '国', '室', '場', '所', '局', '館', '園', '院', '寺', '署', '店',
                     '港', '庫', '村', '区', '島', '城', '堂', '庁', '省', '庭', '部屋', '家', '海', '山')
_VT_PERSON_WORDS = frozenset(('甥', '姪', 'いとこ', '親', '子', '孫', '祖先', '客', '人', '男', '女', '若者', '老人', '幼児', '乳児', '赤ん坊', '赤ちゃん',
                              '友', '友達', '仲間', '隣人', '相手', '他人', '先方', '本人', '当人', '同僚', '家族', '夫婦', '兄弟', '親子',
                              '子ども', '子供', '大人', '住民', '市民', '国民', '村人', '町民', '観客', '聴衆', '乗客', '来場者', '全員', '皆', '誰',
                              '警察', '企業', '当局', '軍隊', '議会', '内閣', '政権', '政府', '軍', '協会', '機関', '組合', '劇団', '財団', '役所', '役場',
                              '国会', '政党', '与党', '野党', '検察', '部隊', '軍団', '教団', '陸軍', '海軍', '空軍', '米軍', '敵軍', '山賊', '海賊', '盗賊', '刑事', 'チーム', '理事会', '取締役会', '評議会', '母親', '父親', '両親', 'おじ', 'おば', '叔母', '伯父', '伯母',
                              '首相', '大統領', '皇帝', '天皇', '神', '泥棒', '敵', '味方', 'クラスメート', '審判',
                              '見習い', '来賓', '来客', '弟子', '師匠', '新人', '常連', '達人', '住職', '僧侶', '神主', '巫女', '王', '女王', '姫', '勇者', '英雄',
                              '犬', '猫', '鳥', '猿', '熊', '鹿', '猪', '馬', '牛', '豚', '羊', '山羊', '兎', '鼠', '狐', '狸', '狼', '虎', '獅子', '象', '蛇', '蛙', '魚',
                              '虫', '蜂', '蚊', '蟻', '烏', '鷲', '鷹', '雀', '鶏', '鳩', '燕', 'イヌ', 'ネコ', 'サル', 'クマ', 'シカ', 'ウマ', 'ウシ', 'ブタ'))
_VT_BENEFACTIVE = frozenset(('あげる', 'やる', 'くれる', '差し上げる', 'もらう', '貰う', 'いただく', '頂く', 'くださる'))
# Round 4 (written separately from the reader's classes; test_gates_round4 checks that the two lists agree). A closed class takes a word
# only when every sense of the word names a person; the ending characters of a word are not evidence.
_VT_PERSON_WORDS = _VT_PERSON_WORDS | frozenset((
    '兵士', '兵隊', '軍人', '役人', '商人', '住人', '町人', '旅人', '恋人', '夫人', '婦人', '青年', '少年', '少女', '武士', '騎士',
    '隊員', '団員', '部員', '局員', '署員', '係員', '駅員', '船員', '乗員', '要員', '党員', '教員',
    '歌手', '作家', '画家', '村長', '町長', '市長', '区長', '知事', '委員', '役員', '議員', '議長', '会長', '幹事', '理事', '取締役', '評議員', '会員',
    '主人', '店主', '社員', '職人', '医者', '学者', '飼い主', '持ち主', '地主', '家主', '船長', '機長', '艦長', '隊長', '団長', '局長', '署長',
    '所長', '館長', '園長', '院長', '組長', '学長'))
# the person-role words of frames.ROLES that name a person in every sense, copied so that the class is closed in this module (written separately from
# the reader's list; test_gates_round5 compares the two); the one frames.ROLES word that also names a building is left out
_VT_ROLE_NOUNS = frozenset(('シェフ','上司','伯母','伯父','住民','作業員','係長','兄','先生','先輩','助手','医師','友人','叔母','叔父','司書','同僚','夫','妹','妻','姉','娘','学生','孫','工員','店員','店長','弟','後輩','息子','患者','技師','担任','指揮者','教師','教授','料理人','校長','検査員','母','消防士','漁師','父','班長','理学療法士','生徒','監督','看護師','社長','祖母','祖父','職員','船長','薬剤師','記者','課長','警察官','運転手','選手','部下','部長'))
_VT_PERSON_WORDS = _VT_PERSON_WORDS | _VT_ROLE_NOUNS
_VT_ROLE_SUFFIXES = frozenset(('士', '生', '主', '医', '者', '人', '手', '員', '民', '師', '長', '係', '官', '家', '将', '婦', '夫'))   # tagged 接尾辞 only inside a compound
_VT_GROUP_SUFFIXES = frozenset(('団', '隊'))
_VT_GROUP_NOUNS = frozenset(('軍', 'チーム', '客'))
_VT_MEMBER_NOUNS = frozenset(('委員', '理事', '役員', '取締役', '評議員', '議員', '幹事', '監事', '会員'))
_VT_POSTS = frozenset(('社長', '部長', '課長', '係長', '班長', '店長', '校長', '議長', '会長', '委員長', '委員', '理事', '幹事', '代表', '主任', '監督',
                       '館長', '院長', '所長', '局長', '署長', '組長', '村長', '町長', '市長', '区長', '知事', '学長', '園長', '艦長', '隊長', '団長',
                       '船長', '機長', '首相', '大統領', '総理', '総裁', 'キャプテン', 'リーダー', '主将', '教授', '役員', '議員', '取締役', '支店長',
                       '工場長'))
_VT_POST_SUFFIXES = frozenset(('長', '係'))
# verbs of making / mending / finishing / editing / dyeing / selecting: their に-phrase is a result only with evidence of a result type
_VT_PROCESSING_VERBS = frozenset(('直す', '仕立てる', '仕上げる', '整理する', 'まとめる', '編集する', '改訂する', '染める', '塗り替える', '塗りかえる',
                                  '塗り直す', '改装する', '模様替えする', '描き直す', '選ぶ', '作り変える', '改造する'))
_VT_SELECTION_VERBS = (_VT_APPOINTMENT_VERBS - frozenset(('昇進する', '昇格する', '降格する'))) | frozenset(('選ぶ',))
_VT_COLOURS = frozenset([c for c in ('赤', '青', '黄', '緑', '白', '黒', '紫', '茶', '灰', '橙', '紺', '藍', '朱', '紅', '桃', '黄緑', '薄緑', '群青')]
                        + [c + '色' for c in ('赤', '青', '黄', '緑', '白', '黒', '紫', '茶', '灰', '橙', '紺', '藍', '朱', '紅', '桃', '金', '銀', '水',
                                              '空', '肌', '黄緑', '薄緑', '群青')]
                        + ['ピンク', 'オレンジ', 'グレー', 'ブラウン', 'ブルー', 'グリーン', 'レッド', 'ホワイト', 'ブラック', 'イエロー', 'パープル', 'ベージュ'])
_VT_FORMATS = frozenset(('図', '表', '図表', '一覧', '要点', '概要', '要約', '目次', 'リスト', '箇条書き', 'グラフ', '年表'))      # nouns naming only a format / digest of content
_VT_FORM_NOUNS = frozenset(('語', '形', '版', '式', '型', '風', '色'))
_VT_LANGUAGES = frozenset(('英語', '仏語', '独語', '露語', '言語', '方言', '敬語', '平仮名', 'ひらがな', 'カタカナ', '漢字'))      # name only a language / variety / script (one token each)
_VT_DEGREE_MARKS = ('ほど', 'くらい', 'ぐらい', '並み')
# A person/organisation is accepted on positive evidence only (see _vt_is_addressee); the ending characters of a word (社 会 部 校 …)
# are shared by organisations, events, places and body/regional parts and decide nothing.
_VT_HONORIFIC_TOKENS = ('さん', '氏', '君', '様', '殿', '達', 'たち', 'ども', 'ちゃん')


def _vt_depths(text):
    """Bracket depth before each character (character scan; the tagger can glue a closing bracket to a neighbour)."""
    depth = 0; out = []
    for ch in text:
        out.append(depth)
        if ch in '（(〈［[【「『《': depth += 1
        elif ch in '）)〉］]】」』》': depth = max(0, depth - 1)
    out.append(depth)
    return out


def _vt_tokens(text):
    """(surface, pos1, pos2, pos3, start, end, lemma) per token."""
    from .typed_edges import _tagger, _base
    out = []; cursor = 0
    for w in _tagger()(text):
        at = text.find(w.surface, cursor)
        if at < 0: at = cursor
        out.append((w.surface, w.feature.pos1, w.feature.pos2, w.feature.pos3, at, at + len(w.surface), _base(w))); cursor = at + len(w.surface)
    return out


# Time-type criteria, written separately from the reader's (no import of it): a counted time (number + counter [+ tail]) or a
# 副詞可能 noun that carries a time morpheme / is a closed deictic time word; X前/X後 only for an event noun, a time word or a
# 後/前 suffix; a relational noun alone is never a time; a の-modified phrase is a time when its head is.
_VT_COUNTERS = ('年代', '年度', '年間', '年', 'か月間', 'か月', 'ヶ月間', 'ヶ月', 'カ月', 'ケ月', '月間', '月', '週間', '週', '日間', '日',
                '時間', '時', '分間', '分', '秒間', '秒', '世紀', '曜日')
_VT_TAILS = ('半', '過ぎ', 'すぎ', '前', '後', '頃', 'ごろ', '以降', '以前', '以後', '以内', '末', '初め', '初頭', '初旬', '上旬', '中旬', '下旬', '目')
_VT_DAYPARTS = ('午前', '午後', '早朝', '朝', '夕方', '夕', '昼', '夜', '晩', '深夜', '未明')
_VT_ERAS = tuple(re.search(r'\(\?:([^()]*)\)\[0-9０-９\]\+年', _TIME_DATE).group(1).split('|')) + ('西暦', '紀元前')   # era names _TIME_DATE already lists
_VT_REL_YEAR = ('同', '当', '翌', '前', '昨', '来', '今', '本', '去', '各', '毎')
_VT_TIME_CHARS = frozenset('朝昼晩夜夕午週月年日曜期代世季春夏秋冬頃旬暮宵刻前後今昔現将初末')
_VT_TIME_WORDS = frozenset(('最近', '近年', '近頃', '以降', '以前', '以後', '現在', '将来', '当時', '当初', '昔', '今後', '今回', '先日',
                            '後日', '目下', '未明', '次', 'きょう', 'あした', 'あす', 'あさ', 'けさ', 'ゆうべ', 'いま', 'のち',
                         '元日', '元旦', '大晦日', '正月', 'お盆', '彼岸', '冬至', '夏至', '春分', '秋分', '夏休み', '冬休み', '春休み', '昼休み', '放課後', '連休', '祝日', '休日', '誕生日', '記念日'))
_VT_NOT_TIME = frozenset(('日常',))
_VT_RELATIONAL = frozenset(('前', '後', '上', '下', '中', '外', '内', '横', '隣', '奥', '側', '辺', '辺り', '先', '間', '際', '手前', 'うち', '途中', 'とき', '時'))


def _vt_is_num(ch):
    return ch in '0123456789０１２３４５６７８９〇一二三四五六七八九十百千万数'


def _vt_counted_prefix(text):
    """Length of the leading counted time expression of `text` (0 when it does not start with one)."""
    i = 0
    for group in (_VT_DAYPARTS, ('約', 'およそ', 'ほぼ'), _VT_ERAS):
        part = next((x for x in group if text.startswith(x, i)), None)
        if part: i += len(part)
    if i < len(text) and text[i] in _VT_REL_YEAR:
        k = i + 1
        if k < len(text) and text[k] in '年月' and k + 1 < len(text) and _vt_is_num(text[k + 1]): k += 1
        if k < len(text) and _vt_is_num(text[k]): i = k
    units = 0
    while i < len(text) and _vt_is_num(text[i]):
        j = i
        while j < len(text) and _vt_is_num(text[j]): j += 1
        unit = next((c for c in _VT_COUNTERS if text.startswith(c, j)), None)
        if unit is None: break
        i = j + len(unit); units += 1
    if not units: return 0
    while True:
        tail = next((t for t in _VT_TAILS if text.startswith(t, i)), None)
        if tail is None: break
        i += len(tail)
    return i


_VT_FINAL_STEMS = ('明け', '末', '初め', '初頭')
_VT_FINAL_WORDS = ('年度', '学期', '世紀', '時代', '時期', '期間')


def _vt_time_final(surface):
    for tail in _VT_FINAL_STEMS:
        if surface.endswith(tail) and len(surface) > len(tail) and any(c in _VT_TIME_CHARS for c in surface[:-len(tail)]): return True
    return surface in _VT_FINAL_WORDS


def _vt_time_token(tok):
    return tok[0] in _VT_TIME_WORDS or (tok[0] not in _VT_NOT_TIME and any(c in _VT_TIME_CHARS for c in tok[0]))


def _vt_lexical_time(toks):
    """toks: particle-free (surface, pos1, pos2, pos3, start, end) tokens."""
    if not toks or len(toks) > 4: return False
    if any(t[1] not in ('名詞', '接頭辞', '接尾辞', '連体詞') or t[2] in ('固有名詞', '数詞') for t in toks): return False
    if ''.join(t[0] for t in toks) in _VT_TIME_WORDS or _vt_time_final(toks[-1][0]): return True
    if toks[-1][0] == '日' and len(toks) >= 2: return True
    if toks[-1][3] != '副詞可能' and toks[-1][0] != '間際': return False
    core = [t for t in toks if t[1] not in ('接頭辞', '連体詞')]
    if not core: return False
    last = core[-1]
    if last[0] == '中' or (last[0] == '間際' and len(core) >= 2):
        return len(core) >= 2 and core[-2][3] == 'サ変可能'
    if last[0] in ('前', '後'):
        if len(core) < 2: return toks[0][1] == '連体詞'
        before = core[-2]
        return True if last[1] == '接尾辞' else (before[3] == 'サ変可能' or _vt_time_token(before))
    if last[0] in _VT_RELATIONAL: return False
    return any(_vt_time_token(t) for t in core)


def _vt_time_unit(text):
    """A particle-free piece of text that is a time (counted, counted + lexical tail, or lexical)."""
    n = _vt_counted_prefix(text)
    if n and n == len(text): return True
    if n: return _vt_lexical_time(_vt_tokens(text[n:]))
    return _vt_lexical_time(_vt_tokens(text))


def _vt_is_time(phrase):
    compact = phrase.replace(' ', '').replace('　', '')
    if not compact: return False
    n = _vt_counted_prefix(compact)
    if n == len(compact): return True
    toks = _vt_tokens(compact)
    if not toks: return False
    pieces = [[]]
    for t in toks:
        if t[1] == '助詞':
            if t[0] != 'の' or not pieces[-1]: return False
            pieces.append([]); continue
        if t[1] in ('動詞', '助動詞', '補助記号', '記号', '副詞'): return False
        pieces[-1].append(t)
    if not pieces[-1]: return False
    head = pieces[-1]
    if len(head) == 1 and head[0][0] in ('前', '後') and len(pieces) >= 2 and pieces[-2] and pieces[-2][-1][3] == 'サ変可能':
        return True                                      # <event noun>の前/後
    return _vt_time_unit(compact[head[0][4]:head[-1][5]])


def _vt_time_fused(phrase):
    compact = phrase.replace(' ', '').replace('　', '')
    segments = [x for x in re.split(r'[、,]', compact) if x]
    if len(segments) > 1: return any(_vt_is_time(x) for x in segments)
    toks = _vt_tokens(compact)
    if len(toks) < 2 or _vt_is_time(compact) or any(t[1] not in ('名詞', '接尾辞', '接頭辞', '連体詞') for t in toks): return False
    for k in range(1, len(toks)):
        if toks[k][1] == '接尾辞': continue
        if _vt_time_unit(compact[:toks[k][4]]): return True
    return False


def _vt_te_auxiliary(words):
    """True when a word list holds <conjunctive て/で/ちゃ/じゃ> [は/も] + the auxiliary なる/いける (the function word of the prohibition / obligation forms). Morphology only."""
    from .typed_edges import _base
    for k, word in enumerate(words):
        if word.feature.pos2 != '非自立可能' or _base(word) not in ('なる', 'いける'): continue
        j = k - 1
        if j >= 0 and words[j].feature.pos1 == '助詞' and words[j].surface in ('は', 'も'): j -= 1
        if j >= 0 and words[j].feature.pos2 == '接続助詞' and words[j].surface in ('て', 'で', 'ちゃ', 'じゃ'): return True
    return False


def _vt_time_suffix_fused(phrase):
    """A time word fused onto a place the tagger splits as <time word> + <suffix token>. `_vt_time_fused` skips every suffix
    boundary (a suffix can continue a time word: next-week + end), so a whole-phrase time is excluded first and only the boundary BEFORE a suffix is read here."""
    compact = phrase.replace(' ', '').replace('　', '')
    if re.search(r'[、,]', compact) or _vt_is_time(compact): return False
    toks = _vt_tokens(compact)
    if len(toks) < 2 or any(t[1] not in ('名詞', '接尾辞', '接頭辞', '連体詞') for t in toks): return False
    return any(toks[k][1] == '接尾辞' and _vt_time_unit(compact[:toks[k][4]]) for k in range(1, len(toks)))


def _vt_is_place(phrase):
    compact = phrase.replace(' ', '').replace('　', '')
    segments = compact.split('の'); head = segments[-1]
    options = [head]
    for tail in ('前', '内', '上', '中', '周辺', '近く', '付近', '隅', '奥', '脇', '横', '隣', '角', '裏', '先', '方面'):
        if head.endswith(tail) and len(head) > len(tail): options.append(head[:-len(tail)])
        if head == tail and len(segments) > 1: options.append(segments[-2])
    if any(o.endswith(_VT_PLACE_ENDINGS) for o in options): return True
    toks = _vt_tokens(compact)
    return bool(toks) and toks[-1][1] == '名詞' and toks[-1][2] == '固有名詞' and toks[-1][3] == '地名'


def _vt_is_origin_spot(phrase):
    """Evidence that a から-phrase of a passive names where something comes from: a closed spot noun that cannot act, or a named place."""
    compact = phrase.replace(' ', '').replace('　', '')
    head = compact.split('の')[-1]
    if head in _VT_SPOTS: return True
    toks = _vt_tokens(head)
    return bool(toks) and toks[-1][1] == '名詞' and toks[-1][2] == '固有名詞' and toks[-1][3] == '地名'


def _vt_is_addressee(phrase):
    """Can the phrase be an addressee / an actor? Positive evidence only, judged from the tagger and closed classes on the HEAD (after
    the last の): a closed person word, a pronoun, a proper person/organisation name, a noun + person-role/honorific/group suffix token,
    a noun + 軍/チーム/客, or <X>会 whose X is a person or ends in a member noun. The ending characters of a word decide nothing, and the
    katakana words of frames._LEARNED (a corpus count of words written before a name: instruments, appliances, cities ...) are not a class of persons."""
    compact = phrase.replace(' ', '').replace('　', '')
    head = compact.split('の')[-1]
    if not head: return False
    if head in _VT_PERSON_WORDS: return True
    toks = _vt_tokens(head)
    if not toks: return False
    final = toks[-1]
    if final[1] == '代名詞': return True
    if final[2] == '固有名詞' and final[3] in ('人名', '組織名', '一般'): return True
    if len(toks) > 1:
        prev = toks[-2]
        chained = prev[1] in ('名詞', '代名詞') or (prev[1] == '接尾辞' and prev[0] in _VT_HONORIFIC_TOKENS + tuple(_VT_ROLE_SUFFIXES))
        if chained:
            # Round 6: a family name + 家 names the people AND the house; that is no evidence of a person (a common noun + 家 is one)
            if (final[1] == '接尾辞' and (final[0] in _VT_HONORIFIC_TOKENS or final[0] in _VT_GROUP_SUFFIXES or final[0] in _VT_ROLE_SUFFIXES)
                    and not (final[0] == '家' and prev[1] == '名詞' and prev[2] == '固有名詞')): return True
            if final[1] == '名詞' and final[0] in _VT_GROUP_NOUNS: return True
        if final[0] == '会' and final[1] == '名詞' and prev[1] in ('名詞', '接尾辞'):
            if prev[0] in _VT_MEMBER_NOUNS or _vt_is_addressee(head[:final[4]]): return True
    return False


def _vt_is_post(phrase):
    """A post / office (what a person is chosen AS): a closed post noun, or <noun> + 長/係 as two tokens."""
    compact = phrase.replace(' ', '').replace('　', '')
    head = compact.split('の')[-1]
    if not head: return False
    if head in _VT_POSTS: return True
    toks = _vt_tokens(head)
    return len(toks) >= 2 and toks[-1][1] == '接尾辞' and toks[-1][0] in _VT_POST_SUFFIXES and toks[-2][1] == '名詞'


def _vt_result_evidence(phrase):
    """Positive evidence that a に-phrase names a result type: a number + counter, an adjectival noun head, a noun + 語/形/版/式/型/風/色, a
    colour name, or a time phrase. A person lexicon is not consulted."""
    compact = phrase.replace(' ', '').replace('　', '')
    if not compact: return False
    if _VT_COUNTED_HEAD.match(compact) or _vt_is_time(compact): return True
    head = compact.split('の')[-1]
    if head in _VT_COLOURS or head in _VT_FORMATS or head in _VT_LANGUAGES: return True
    toks = _vt_tokens(head)
    if not toks: return False
    if toks[-1][1] == '形状詞': return True
    if toks[-1][1] == '名詞' and toks[-1][3] == '助数詞可能': return True                # a noun usable as a counter: a unit things are divided into
    if toks[-1][1] == '名詞' and toks[-1][0] in _VT_FORMATS: return True                 # a compound headed by a format noun
    if len(toks) == 2 and toks[0][2] == '数詞' and toks[1][1] in ('接尾辞', '名詞'): return True      # a numeral + one counter / measure word
    return len(toks) >= 2 and toks[-1][1] == '名詞' and toks[-1][0] in _VT_FORM_NOUNS and toks[-2][1] == '名詞'


def _vt_result_excluded(predicate, phrase, object_person, passive):
    """Why a に-phrase cannot be the result of this verb of change, or None. A person lexicon is not consulted: with a thing acted on, the
    に-phrase is a result only on evidence of a result type (a status-conferring verb, and a clause with no thing acted on whose verb has no
    transitive use, need none; a transitive verb with its object left out is undecided)."""
    compact = phrase.replace(' ', '').replace('　', '')
    if passive and predicate in _VT_SELECTION_VERBS:
        return None if (_vt_is_post(compact) and object_person is not False) else 'the に-phrase of a passive selection is a result only when it names a post'
    if predicate in _VT_APPOINTMENT_VERBS or predicate in _VT_PRODUCT_VERBS: return None
    if _vt_result_evidence(compact): return None
    if object_person is True: return None              # work applied TO a person: the に-phrase is the status the person is brought to
    if predicate in _VT_PROCESSING_VERBS: return 'a result of a verb of making needs evidence of a result type'
    if object_person is None and predicate in _VT_INTRANSITIVE_CHANGE_VERBS: return None   # nothing acted on and the verb takes none (なる, 変わる): the に-phrase is what the subject becomes
    return 'a result of a verb of conversion on a thing needs evidence of a result type'


def _vt_passive_follows(toks, index):
    """toks[index] (tuples with the lemma last) is the predicate token; a サ変 predicate is the noun and the する verb."""
    if index < len(toks) and toks[index][1] == '名詞' and index + 1 < len(toks) and toks[index + 1][6] == 'する': index += 1
    return index + 1 < len(toks) and toks[index + 1][6] in ('れる', 'られる')


def _vt_following(tagged, end):
    """The particle right after a phrase ending at `end` in tag() form; compound particles (によって, について, において,
    に対して) are one unit and are not the plain case particle に."""
    for index, token in enumerate(tagged):
        if token[4] == end:
            if token[1] != '助詞': return ''
            tail = ''.join(t[0] for t in tagged[index:index + 4])
            for compound in ('によって', 'について', 'において', 'に対して', 'による', 'により', 'として', 'における'):
                if tail.startswith(compound) and token[0] == compound[0]: return compound
            return token[0]
        if token[4] > end: break
    return ''


def _vt_recipient_excluded(predicate, value, has_object, benefactive, mark='に'):
    """Why a に-marked phrase cannot be this predicate's recipient, or None. Verbs of transfer/telling and a benefactive address
    the phrase; a person is an addressee; the end point of a motion/placement/location verb is read as recipient (project
    convention); otherwise, with an を-object, the に-phrase is a result/place/state."""
    if predicate in _VT_ADDRESSEE_VERBS or benefactive: return None
    # Round 4: the end point of a MOTION verb is a recipient only when the phrase shows it is a place or an addressee; placement and
    # location verbs keep the project convention (existing tests fix it).
    if predicate in _VT_MOTION_VERBS and predicate not in _VT_LOCATIVE_VERBS:
        return None if (_vt_is_place(value) or _vt_is_addressee(value)) else 'end point without place or person evidence'
    if predicate in _VT_MOTION_VERBS or predicate in _VT_PLACEMENT_VERBS: return None
    if mark != 'に': return None
    person = _vt_is_addressee(value) and not _vt_is_place(value)
    if predicate in _VT_RESULT_VERBS:
        shares = predicate in _VT_SHARING_VERBS and person and not _VT_COUNTED_HEAD.match(value.replace(' ', '').replace('　', ''))
        return None if shares else 'not an addressee'
    if person: return None
    return 'not an addressee' if has_object else None


def _vt_agent_excluded(value, predicate, subject, has_object=False):
    """True when a に-phrase cannot be an agent: neither enclosing, nor a person/organisation that is not also a place, nor (for a
    verb of transfer whose subject is a thing) anything but the recipient."""
    if predicate in _VT_ENCLOSING_VERBS: return False
    if not _vt_is_addressee(value) or _vt_is_place(value): return True
    return predicate in _VT_ADDRESSEE_VERBS and not has_object and (subject is None or not _vt_is_addressee(subject))


def _vt_intransitive(predicate):
    from .frames import transitivity
    return transitivity(predicate) == 'intrans'


def _vt_origin_not_agent(value):
    # a から-phrase is an agent only with positive evidence of a person; a spot noun never is one (a surname-like 森 is tagged a person name)
    return _vt_is_time(value) or value.replace(' ', '').replace('　', '').split('の')[-1] in _VT_SPOTS or not _vt_is_addressee(value)


def _vt_participant_excluded(name, value, tagged, end, predicate, passive, has_patient=True, benefactive=False, subject=None):
    """Re-derive, from the source text alone, whether a Frame participant is of the wrong type for its role.
    Returns the reason or None. A role that is excluded here must NOT be declared by the clause."""
    follow = _vt_following(tagged, end)
    if follow in ('に', 'は') and _vt_is_time(value): return 'time phrase'
    if name == 'agent' and passive and follow == 'に' and _vt_agent_excluded(value, predicate, subject, has_patient): return 'not a person'
    if name == 'agent' and passive and follow == 'に' and predicate in _VT_SELECTION_VERBS: return 'by/as undecided (a passive verb of selection)'
    if name == 'agent' and passive and follow == 'から' and _vt_origin_not_agent(value): return 'an origin, not an agent'
    if name == 'recipient' and follow in ('に', 'へ'): return _vt_recipient_excluded(predicate, value, has_patient, benefactive, follow)
    if name == 'patient' and follow == 'は' and not passive and _vt_intransitive(predicate): return 'topic of an intransitive verb'
    return None


def _vt_check_roles(clause):
    """Type checks every clause must pass, whatever rule produced it."""
    body = clause.body_span or clause.span
    roles = [r for r in clause.roles if r.name in _VT_NOMINAL_ROLES or r.name in _VT_TIME_ADJUNCT_ROLES or r.name in ('time', 'source')]
    if not roles: return
    toks = _vt_tokens(body.text); rdepth = _vt_depths(body.text)
    starts = {t[4] for t in toks}; ends = {t[5] for t in toks}
    spans = {}
    for role in roles:
        a, b = role.span.start - body.start, role.span.end - body.start
        while a < b and body.text[a].isspace(): a += 1
        while b > a and body.text[b - 1].isspace(): b -= 1
        spans[id(role)] = (a, b)
    follow = {k: _vt_following(toks, b) for k, (a, b) in spans.items()}
    has_object = any(r.name == 'patient' and follow[id(r)] == 'を' for r in roles)
    subject = next((r.span.text for r in roles if r.name == 'patient' and follow[id(r)] in ('が', 'は')), None)
    p0 = clause.predicate_span.start - body.start
    after = [t for t in toks if t[4] >= p0]
    benefactive = any(after[k][0] in ('て', 'で') and k + 1 < len(after) and after[k + 1][6] in _VT_BENEFACTIVE
                      for k in range(len(after) - 1))
    clause_passive = _vt_passive_follows(after, 0)
    for role in roles:
        a, b = spans[id(role)]; mark = follow[id(role)]; text = role.span.text
        if role.name in _VT_NOMINAL_ROLES:
            if a not in starts or b not in ends: raise Rejected('ill-typed role: span cuts a token')
            hit = False; has_verb = False; last_content = None
            for t in toks:
                if t[4] < a or t[5] > b: continue
                if rdepth[t[4]] > rdepth[a] or t[0] in '（(〈［[【「『《）)〉］]】」』》': continue
                if t[1] == '助詞' and t[0] in ('が', 'を', 'は', 'より'): hit = True
                if t[1] in ('動詞', '形容詞'): has_verb = True
                if t[1] not in ('助詞', '助動詞', '補助記号', '記号'): last_content = t[0]
            if hit and not (has_verb and last_content in ('こと', 'の', 'もの', 'ところ', 'ため', 'わけ', 'はず', 'よう', 'ほう', '方', '事', '物', 'つもり')):
                raise Rejected('ill-typed role: phrase spans a case particle')
        if role.name in _VT_EVENT_PARTICIPANTS:
            if (_vt_is_time(text) and mark in ('に', 'は')) or _vt_time_fused(text):
                raise Rejected('ill-typed role: time phrase as event participant')
            if role.name == 'agent' and mark in ('に', 'へ') and _vt_agent_excluded(text, clause.predicate, subject, has_object):
                raise Rejected('ill-typed role: a phrase that cannot act as agent')
            if role.name == 'agent' and mark == 'から' and _vt_origin_not_agent(text):
                raise Rejected('ill-typed role: an origin (place/time) as agent')
            if role.name == 'agent' and mark == 'に' and clause_passive and clause.predicate in _VT_SELECTION_VERBS:
                raise Rejected('ill-typed role: the に-phrase of a passive verb of selection is by/as undecided, not an agent')
            if role.name == 'recipient' and mark in ('に', 'へ') and _vt_recipient_excluded(clause.predicate, text, has_object, benefactive, mark):
                raise Rejected('ill-typed role: recipient is not an addressee')
            if role.name == 'patient' and mark == 'は' and not clause_passive and _vt_intransitive(clause.predicate):
                raise Rejected('ill-typed role: a topic as the patient of an intransitive verb')
            if role.name in ('agent', 'patient', 'recipient'):
                stem = re.sub(r'^[おご御]', '', text.replace(' ', '').replace('　', ''))
                if len(stem) >= 2 and clause.predicate.startswith(stem): raise Rejected('ill-typed role: participant repeats the predicate')
        elif role.name in _VT_TIME_ADJUNCT_ROLES and _vt_is_time(text):
            raise Rejected('ill-typed role: time phrase as place/goal/direction/result')
        elif role.name in _VT_TIME_ADJUNCT_ROLES and (_vt_time_fused(text) or _vt_time_suffix_fused(text)):
            raise Rejected('ill-typed role: time phrase fused with place/goal/direction')
        elif role.name == 'source' and mark == 'から' and clause_passive and not _vt_is_origin_spot(text):
            raise Rejected('ill-typed role: the から-phrase of a passive is the agent or the origin, and nothing shows it is a spot')
        elif (role.name in ('goal', 'direction') and mark in ('に', 'へ') and clause.predicate in _VT_GOAL_VERBS
              and not _vt_is_place(text) and text.replace(' ', '').replace('　', '').split('の')[-1] not in _VT_GATHERINGS
              and not _vt_is_addressee(text)):
            raise Rejected('ill-typed role: end point of motion without place evidence')
        elif role.name == 'time' and mark == 'に' and has_object and clause.predicate in _VT_RESULT_VERBS:
            raise Rejected('ill-typed role: time phrase of a verb of change is its new value, not when it happened')
        elif role.name == 'result' and _vt_is_time(text) and clause.predicate not in _VT_RESULT_VERBS:
            raise Rejected('ill-typed role: time phrase as place/goal/direction/result')
        elif (role.name == 'result' and mark == 'に' and clause.predicate in _VT_RESULT_VERBS and not clause_passive
              and any(r.name == 'patient' and follow[id(r)] == 'を' and spans[id(r)][0] >= b for r in roles)):
            raise Rejected('ill-typed role: a に-phrase before the object of a verb of change is not its result')
        elif role.name == 'result' and mark == 'に' and clause.predicate in _VT_RESULT_VERBS and not _vt_is_time(text):
            owners = [r for r in roles if r.name == 'patient' and follow[id(r)] in (('が', 'は') if clause_passive else ('を',))]
            object_person = any(_vt_is_addressee(r.span.text) for r in owners) if owners else None
            why = _vt_result_excluded(clause.predicate, text, object_person, clause_passive)
            if why: raise Rejected('ill-typed role: ' + why)


_COMPOUND_SURFACES = tuple(sorted({surface for choices in _CONSTRUCTION_PARTICLES.values()
                                   for surface in choices}, key=len, reverse=True))


def _compound_predicate_indices(words, positions):
    """Independent token scan for verbs that are parts of closed particles."""
    indices = set()
    for first, start in enumerate(positions):
        for surface in _COMPOUND_SURFACES:
            cursor = start; joined = ''; covered = []
            for index in range(first, len(words)):
                if positions[index] != cursor: break
                joined += words[index].surface
                cursor += len(words[index].surface)
                covered.append(index)
                if joined == surface:
                    indices.update(covered); break
                if not surface.startswith(joined): break
            if any(index in indices for index in covered): break
    return indices


def _filter_compound_predicates(words, positions, predicates, frames=None):
    indices = _compound_predicate_indices(words, positions)
    filtered = [item for item in predicates if item[0] not in indices]
    if frames is not None and len(frames) == len(predicates):
        frames = [frame for frame, item in zip(frames, predicates) if item[0] not in indices]
    return filtered, frames


def _token_suffix(tagged, end, choices):
    """Return a closed particle surface exactly tokenized at a role boundary."""
    starts = [i for i, token in enumerate(tagged) if token[4] == end]
    for first in starts:
        for choice in sorted(choices, key=len, reverse=True):
            cursor = end; pieces = []
            for token in tagged[first:]:
                if token[4] != cursor: break
                pieces.append(token[0]); cursor = token[5]
                joined = ''.join(pieces)
                if joined == choice: return choice
                if not choice.startswith(joined): break
    return None


def _time_role_licensed(role, body, tagged):
    start, end = role.span.start - body.start, role.span.end - body.start
    value = role.span.text
    compact = value.replace(' ', '').replace('　', '')
    simple = compact == '同日付' or _TIME_VALUE.fullmatch(compact) or _vt_is_time(compact)
    if not simple: return False
    if _token_suffix(tagged, end, ('に', 'で') if compact == '同日付' else ('に',)):
        return phrase_bounded(tagged, start, end)
    if role.rule == 'topic' and _vt_is_time(compact) and _token_suffix(tagged, end, ('は',)):
        return phrase_bounded(tagged, start, end)
    left = len(body.text) - len(body.text.lstrip())
    if (start == left and (_TIME_COMMA_VALUE.fullmatch(compact) or _vt_is_time(compact))
            and _token_suffix(tagged, end, ('、', ','))):
        return phrase_bounded(tagged, start, end)
    return False


def _number(q, unit):
    """Independent scaled rational arithmetic; no ambient Decimal context."""
    if not typed(q, "quantity"):
        raise Rejected("non-finite/non-quantity operand")
    d1, f1 = unit_type(q.unit); d2, f2 = unit_type(unit)
    if d1 != d2:
        raise Rejected("incompatible units")
    # Build rational from the integer coefficient and decimal exponent.
    def ratio(d):
        sign, digits, exp = d.as_tuple(); n = int(''.join(map(str, digits)) or '0')
        if sign: n = -n
        if abs(exp) > 256: raise Rejected("quantity exponent outside exact contract")
        return (n * 10 ** exp, 1) if exp >= 0 else (n, 10 ** -exp)
    n, d = ratio(q.amount); fn, fd = ratio(f1); gn, gd = ratio(f2)
    return Fraction(n * fn * gd, d * fd * gn)


def _finite(r):
    # A finite decimal's denominator contains only 2 and 5, independently
    # checked before constructing the exact coefficient.
    denominator = r.denominator; twos = fives = 0
    while denominator % 2 == 0: denominator //= 2; twos += 1
    while denominator % 5 == 0: denominator //= 5; fives += 1
    if denominator != 1: raise Rejected("non-terminating unit conversion")
    places = max(twos, fives)
    coefficient = r.numerator * 2 ** (places - twos) * 5 ** (places - fives)
    digits = tuple(map(int, str(abs(coefficient))))
    if len(digits) > 128 or places > 256: raise Rejected("exact result exceeds precision contract")
    return Decimal((1 if coefficient < 0 else 0, digits, -places))


def _operand(term, env):
    if isinstance(term, Variable):
        if term.name not in env or not typed(env[term.name], term.sort):
            raise Rejected("unbound/ill-typed operand")
        return env[term.name]
    return term


def _test(a, relation, b):
    if isinstance(a, Quantity) or isinstance(b, Quantity):
        if not isinstance(a, Quantity) or not isinstance(b, Quantity): raise Rejected("comparison type")
        a, b = _number(a, a.unit), _number(b, a.unit)
    elif relation not in ('=', '!='):
        raise Rejected("ordered non-quantity comparison")
    return {'=': lambda: a == b, '!=': lambda: a != b, '>': lambda: a > b,
            '<': lambda: a < b, '>=': lambda: a >= b, '<=': lambda: a <= b}[relation]()


def _calc(op, env):
    env = dict(env); answer = ()
    if op.op == 'Filter':
        if not all(_test(_operand(t.left, env), t.relation, _operand(t.right, env)) for t in op.tests):
            return None
    elif op.op in ('Sum', 'Difference'):
        values = [_operand(t, env) for t in op.terms]; unit = op.unit or values[0].unit
        values = [_number(v, unit) for v in values]
        amount = sum(values, Fraction(0)) if op.op == 'Sum' else values[0] - values[1]
        env[op.target.name] = Quantity(_finite(abs(amount) if op.absolute else amount), unit)
    elif op.op == 'Compare':
        a, b = [_operand(t, env) for t in op.terms]
        value = _test(a, op.relation, b)
        if op.choices:
            if _test(a, '=', b): raise Rejected("comparison tie")
            value = _operand(op.choices[0 if value else 1], env)
        env[op.target.name] = value
    elif op.op == 'Project':
        answer = tuple((o.label, Quantity(_finite(_number(_operand(o.term, env), o.unit)), o.unit)
                        if o.unit else _operand(o.term, env)) for o in op.outputs)
    if op.target and not typed(env[op.target.name], op.target.sort): raise Rejected("result sort")
    return env, answer


def _match(pattern, clause, seed=None, opposite=False):
    if pattern.predicate not in ('*', clause.predicate): return None
    if pattern.modality == 'normative':
        if clause.modality not in ('permission', 'prohibition'): return None
    elif pattern.modality != clause.modality: return None
    pol = ('-' if pattern.polarity == '+' else '+') if opposite else pattern.polarity
    if pol != '*' and pol != clause.polarity: return None
    if pattern.time and pattern.time != clause.time: return None
    actual = {r.name: r.term for r in clause.roles}
    if len(actual) != len(clause.roles): raise Rejected("duplicate source role")
    env = dict(seed or {})
    terms = list(pattern.roles)
    if pattern.event is not None:
        terms.append(('$event', pattern.event))
        actual['$event'] = EventValue(clause.sovereign, clause.family, clause.event.name, clause.time)
    for role, wanted in terms:
        if role not in actual: return None
        value = actual[role]
        if isinstance(wanted, Nominal):
            from .typed_edges import _tagger
            nouns = [w.surface for w in _tagger()(value) if w.feature.pos1 in ('名詞', '接尾辞')] if isinstance(value, str) else []
            if not nouns or nouns[-1] != wanted.head: return None
            wanted = wanted.term
        if isinstance(wanted, Variable):
            if not typed(value, wanted.sort): return None
            if wanted.name in env and env[wanted.name] != value: return None
            env[wanted.name] = value
        elif wanted != value: return None
    return env


def _attribute(text):
    from .typed_edges import _tagger, _base
    words = list(_tagger()(text))
    if len(words) == 2 and words[0].feature.pos1 == '形容詞' and words[1].surface == 'さ':
        return 'nominal:' + _base(words[0])
    return text


def _role_split(value, roles, name, raw, body, words, positions):
    """Validated (descriptor, name) split of a Frame role value, using the sentence's own tokens."""
    role = next((r for r in roles if r.name == name), None)
    if role is None: return None
    tagged = [(w.surface, w.feature.pos1, w.feature.pos2, at, at + len(w.surface)) for w, at in zip(words, positions)]
    start = 0
    while True:
        at = raw.find(value, start)
        if at < 0: return None
        split = name_split_in(tokens_covering(tagged, at, at + len(value)), value)
        if split and role.span.text == split[1] and role.span.start - body.start == at + len(split[0]):
            return split
        start = at + 1


def _case_order_predicate(clause, raw, body, words, positions, event_index):
    """Re-read an ambiguous verb after putting its source case frame in canonical order."""
    roles = {r.name: r for r in clause.roles}
    agent = roles.get('agent'); recipient = roles.get('recipient')
    if not agent or not recipient: return None
    a0, a1 = agent.span.start - body.start, agent.span.end - body.start
    r0, r1 = recipient.span.start - body.start, recipient.span.end - body.start
    event_start = positions[event_index]
    if not (0 <= r0 < r1 <= a0 < a1 <= event_start): return None

    def case_end(end, allowed):
        following = next((i for i, (word, at) in enumerate(zip(words, positions))
                          if at == end and word.feature.pos1 == '助詞'), None)
        if following is None or words[following].surface not in allowed: return None
        return positions[following] + len(words[following].surface)

    agent_end = case_end(a1, ('は', 'が'))
    recipient_end = case_end(r1, ('に', 'へ'))
    if agent_end is None or recipient_end is None or not (r1 <= recipient_end <= a0): return None
    prefix = raw[:event_start]
    remainder = ''.join(prefix[left:right] for left, right in (
        (0, r0), (recipient_end, a0), (agent_end, event_start)))
    if remainder.strip(): return None
    normalized = prefix[a0:agent_end] + prefix[r0:recipient_end] + remainder + raw[event_start:]

    from .frames import _predicates
    from .typed_edges import _tagger
    reordered = list(_tagger()(normalized)); predicates = _predicates(reordered)
    repositions = []; cursor = 0
    for word in reordered:
        at = normalized.find(word.surface, cursor); repositions.append(at); cursor = at + len(word.surface)
    predicates, _ = _filter_compound_predicates(reordered, repositions, predicates)
    surface = words[event_index].surface
    candidates = [predicate for i, predicate in predicates if reordered[i].surface == surface]
    return candidates[0] if len(candidates) == 1 and len(predicates) == 1 else None


def _literal(role):
    if isinstance(role.term, Quantity):
        m = re.fullmatch(r'([+-]?[0-9]+(?:\.[0-9]+)?)\s*([^0-9\s]+)', role.span.text)
        return bool(m and Decimal(m[1]) == role.term.amount and m[2] == role.term.unit and typed(role.term, 'quantity'))
    if role.rule == 'nominal': return role.term == _attribute(role.span.text)
    if role.rule == 'frame':
        from .frames import canonical
        return role.term == canonical(role.span.text)
    return role.term == role.span.text


def _symbolic_atom(value):
    """Symbolic records carry atoms, never free-form or compatibility-hidden text."""
    return (isinstance(value, str) and bool(value)
            and value == unicodedata.normalize('NFKC', value)
            and all(char == '_' or char.isalnum() for char in value))


def _ranges(raw):
    """Independent original-sentence boundaries, including quoted punctuation."""
    opened = []; begin = 0; spans = set()
    for match in re.finditer(r'[。！？\n「」『』]', raw):
        mark = match[0]
        if mark in ('「','『'): opened.append(mark)
        elif mark in ('」','』'):
            if not opened or opened.pop() != ('「' if mark == '」' else '『'):
                raise Rejected('unbalanced source quotation')
        elif not opened:
            end = match.end()
            if raw[begin:end].strip(): spans.add((begin,end))
            begin = end
    if opened: raise Rejected('unclosed source quotation')
    if raw[begin:].strip(): spans.add((begin,len(raw)))
    return spans


def _native_guard_scope(clause, body):
    """Bind an antecedent to its entire original prefix, not any valid span."""
    raw = clause.span.text
    left = len(raw) - len(raw.lstrip())
    # Independently reject unrepresented prefix scope. A producer cannot
    # turn a hypothesis, correction or rule heading into an asserted fact by
    # moving body_span to the text after a colon.
    colon_positions = [m.start() + clause.span.start for m in re.finditer('[:：]', raw)]
    if colon_positions:
        value = next((r for r in clause.roles if r.name == 'value'), None)
        if (clause.rule not in ('copula', 'identity') or value is None
                or re.fullmatch(r'[0-9]+(?:[:：][0-9]+)+', value.span.text) is None
                or any(not value.span.start <= at < value.span.end for at in colon_positions)):
            raise Rejected('uninterpreted colon scope')
    while left < len(raw) and raw[left] in ' 、,': left += 1
    antecedent = re.match(r'^(.*?)(場合(?:は|には|に)?|ならば|(?<!な)(?<!けれ)なら(?!な)|(?<!なけ)れば|ときは|時は|際は|際には)[、,]?', raw[left:])
    if antecedent and antecedent[1].strip():
        expected_start = clause.span.start + left
        expected_end = expected_start + len(antecedent[1])
        expected_body = expected_start + antecedent.end()
        if len(clause.conditions) != 1 or len(clause.condition_spans) != 1:
            raise Rejected('missing or duplicate source condition')
        guard = clause.condition_spans[0]
        if (guard.start, guard.end, guard.text) != (expected_start, expected_end, antecedent[1]):
            raise Rejected('condition full-prefix scope')
    else:
        expected_body = clause.span.start + left
        if clause.conditions or clause.condition_spans:
            raise Rejected('invented source condition')
    if body.start != expected_body or body.end != clause.span.end:
        raise Rejected('native body boundary')


def _license_measure(clause, body, raw, view):
    """Independent re-reading of a measure sentence (split-based, not the producer's pattern).

    Every list segment must be represented as its own clause, the whole body must be
    consumed, and the role set / answer label / predicate dimension must follow the rules.
    """
    from .semantic_ir import unit_type
    text = re.sub(r'(?:です|だ|である)?[。！？!?]*\s*$', '', raw)
    parts = text.split('、')
    segment = re.compile(r'([^0-9\s：:の]+[0-9]*)(は|が|に|も)([0-9]+(?:\.[0-9]+)?)((?:[A-Za-z]+)|(?:[一-鿿]{1,2}))')
    tail = None; cuts = []; offset = 0
    for index, part in enumerate(parts):
        last = index == len(parts) - 1
        m = re.fullmatch(segment.pattern + r'(?:の([一-鿿ァ-ヶー]+))?', part) if last else segment.fullmatch(part)
        if not m: raise Rejected('measure grammar')
        if last and m.lastindex == 5: tail = m[5]
        cuts.append((offset, m)); offset += len(part) + 1
    count = sum(1 for c in view.clauses if c.rule == 'measure' and c.span == clause.span and c.body_span == clause.body_span)
    if count != len(parts): raise Rejected('measure segment omitted or duplicated')
    mine = [(o, m) for o, m in cuts
            if clause.roles and body.start + o + m.start(1) == next(r for r in clause.roles if r.name == 'entity').span.start]
    if len(mine) != 1: raise Rejected('measure segment alignment')
    o, m = mine[0]
    label, particle, number, unit = m[1], m[2], m[3], m[4]
    roles = {r.name: r for r in clause.roles}
    wanted = {'entity', 'label', 'value'}
    split = re.fullmatch(r'(.+?)([A-Za-z]|[0-9]+)', label) if not re.search(r'[A-Za-z0-9]', label[:1]) else None
    if split and re.search(r'[A-Za-z0-9]', split[1]): split = None
    if split: wanted.add('kind')
    if tail: wanted.add('substance')
    if set(roles) != wanted: raise Rejected('measure role set')
    if roles['entity'].term != label or roles['entity'].span.text != label: raise Rejected('measure entity')
    if clause.predicate_span.text != particle or clause.predicate_span.start != roles['entity'].span.end:
        raise Rejected('measure particle position')
    expected_label = split[2] if split and split[2].isalpha() else label
    if roles['label'].term != expected_label or roles['label'].span.text != expected_label: raise Rejected('measure label')
    if split and (roles['kind'].term != split[1] or roles['kind'].span.text != split[1]): raise Rejected('measure kind')
    value = roles['value']
    if (not isinstance(value.term, Quantity) or value.term.amount != Decimal(number) or value.term.unit != unit
            or value.span.text != number + unit): raise Rejected('measure quantity')
    if tail and roles['substance'].term != tail: raise Rejected('measure substance')
    if clause.predicate != 'measure.' + unit_type(unit)[0]: raise Rejected('measure dimension predicate')
    if (clause.polarity, clause.modality, clause.time) != ('+', 'assert', ''): raise Rejected('measure polarity/modality/time')
    if clause.conditions or clause.exceptions: raise Rejected('measure invented scope')


def license_clause(clause, view, ranges=None):
    """Check original text, roles and grammatical scope independently of reader."""
    if clause != view.by_id.get(clause.id): raise Rejected("noncanonical source clause")
    spans = [clause.span, clause.predicate_span, *(r.span for r in clause.roles),
             *clause.condition_spans, *clause.exception_spans]
    if clause.body_span: spans.append(clause.body_span)
    if any(not s.valid(view.sources) for s in spans): raise Rejected("source span mismatch")
    if any(s.source != clause.span.source for s in spans): raise Rejected("cross-source span")
    body = clause.body_span or clause.span
    if not (clause.span.start <= body.start < body.end <= clause.span.end): raise Rejected("body scope")
    if any(not (body.start <= r.span.start < r.span.end <= body.end) for r in clause.roles): raise Rejected("role scope")
    if clause.event.sort != 'event' or clause.unsupported: raise Rejected("unsupported/ill-typed source")
    if len({r.name for r in clause.roles}) != len(clause.roles): raise Rejected("duplicate role")
    # A comparison's dimension/direction are typed values the source does not spell out; they are admitted here only for
    # the comparison rule, whose own licensor re-derives and checks them against the source adjective/cue.
    if any(not (_literal(r) or (clause.rule == 'comparison' and r.rule in ('comparison_dimension', 'comparison_direction')
                                and isinstance(r.term, str) and r.term)) for r in clause.roles):
        raise Rejected("role/value licensing")
    _vt_check_roles(clause)
    if len(clause.conditions) != len(clause.condition_spans) or len(clause.exceptions) != len(clause.exception_spans):
        raise Rejected("guard span count")
    if clause.rule != 'record':
        _native_guard_scope(clause, body)
    raw = body.text
    if clause.rule in ('frame', 'copula', 'identity'):
        from .typed_edges import _tagger
        significant = list(_tagger()(raw))
        if raw.rstrip().endswith(('?', '？')) or any(w.feature.pos1 == '助詞' and w.surface in ('か', 'かな', 'かしら', 'かい', 'かね', 'っけ') for w in significant):
            raise Rejected('interrogative source is not an assertion')
        if any('意志推量' in str(w.feature.cForm) for w in significant):
            raise Rejected('volitional source is not an assertion')
    before = clause.span.text[:clause.predicate_span.start - clause.span.start]
    quoted = before.count('「') > before.count('」') or before.count('『') > before.count('』')
    from .bot import _INJECTED
    if _INJECTED.search(clause.span.text) and clause.modality != 'instruction': raise Rejected("instruction assertion")
    if quoted and clause.modality != 'quote': raise Rejected("quoted assertion")
    if clause.rule == 'record':
        # Explicit symbolic axioms are a kernel-only input format, not a natural
        # language success. Their full formula, polarity and guard must agree.
        roles = {r.name: r.term for r in clause.roles}
        if clause.span.start != 0 or clause.span.end != len(view.sources[clause.span.source]):
            raise Rejected('symbolic full-source scope')
        actor = roles.get('actor'); amount = roles.get('amount')
        if not _symbolic_atom(clause.predicate) or not _symbolic_atom(actor):
            raise Rejected('instruction assertion: non-atomic symbolic value')
        expected = f'{clause.predicate}({actor})'
        expected += '=' + str(amount.amount) + amount.unit if isinstance(amount, Quantity) else ''
        expected += ' is false.' if clause.polarity == '-' else '.'
        if raw != expected: raise Rejected("symbolic source formula")
        if set(roles) != ({'actor', 'amount'} if amount is not None else {'actor'}):
            raise Rejected('symbolic role set')
        if clause.time or clause.modality != 'assert': raise Rejected('symbolic time/modality')
        if (clause.predicate_span.start, clause.predicate_span.end, clause.predicate_span.text) != (
                body.start, body.start + len(clause.predicate), clause.predicate):
            raise Rejected('symbolic predicate position')
        actor_role = next(r for r in clause.roles if r.name == 'actor')
        if (actor_role.span.start, actor_role.span.end) != (
                body.start + len(clause.predicate) + 1, body.start + len(clause.predicate) + 1 + len(str(actor))):
            raise Rejected('symbolic actor position')
        prefix = clause.span.text[:body.start - clause.span.start]
        guards = clause.conditions or clause.exceptions
        if clause.conditions and clause.exceptions or len(guards) > 1:
            raise Rejected('unsupported symbolic guard grammar')
        if guards:
            g = guards[0]
            if (not _symbolic_atom(g.predicate)
                    or any(not _symbolic_atom(value) for _, value in g.roles)):
                raise Rejected('instruction assertion: non-atomic symbolic guard')
            if len(g.roles) != 1 or g.roles[0][0] != 'actor' or g.polarity != '+' or g.modality != 'assert' or g.time or g.event:
                raise Rejected('symbolic guard shape')
            word = 'When ' if clause.conditions else 'Unless '
            guard_text = f'{g.predicate}({g.roles[0][1]})'
            spans_guard = clause.condition_spans or clause.exception_spans
            if prefix != word + guard_text + ', ' or len(spans_guard) != 1 or (
                    spans_guard[0].start, spans_guard[0].end, spans_guard[0].text) != (
                        clause.span.start + len(word), body.start - 2, guard_text):
                raise Rejected('symbolic guard position/content')
        elif prefix:
            raise Rejected('unrepresented symbolic source scope')
    elif clause.rule in ('copula', 'identity'):
        if (clause.span.start, clause.span.end) not in (ranges if ranges is not None else _ranges(view.sources[clause.span.source])):
            raise Rejected('copula full-clause boundary')
        m = re.fullmatch(r'\s*(.*?)\s*(?:と(?=は))?[はが]\s*(.*?)(?:です|である|だ|ではない|でない|じゃない)?[。！？?]*\s*', raw)
        if not m: raise Rejected("copula source grammar")
        roles = {r.name: r for r in clause.roles}; entity = roles.get('entity'); value = roles.get('value')
        if not entity or not value: raise Rejected("copula roles")
        # The sentence splits at its first は/が PARTICLE TOKEN (not at a か/は letter inside a word or a reading such as
        # しながわ): derive the two sides from the verifier's own tokenization.
        ctoks = _vt_tokens(raw)
        cdepth = _vt_depths(raw); cut_index = None
        for i, t in enumerate(ctoks):
            if cdepth[t[4]] == 0 and t[1] == '助詞' and t[0] in ('は', 'が') and raw[:t[4]].strip():
                cut_index = i; break
        if cut_index is None: raise Rejected('copula split is not at a particle token')
        cut = ctoks[cut_index]; left_end = cut[4]
        if cut_index and ctoks[cut_index - 1][1] == '助詞' and ctoks[cut_index - 1][5] == cut[4]:
            if ctoks[cut_index - 1][0] == 'と' and cut[0] == 'は': left_end = ctoks[cut_index - 1][4]     # X とは Y
            elif ctoks[cut_index - 1][0] in ('で', 'に', 'から', 'へ', 'まで', 'より', 'を'): raise Rejected('copula left side ends in a particle')
        side = re.fullmatch(r'\s*(.*?)\s*(?:です|である|だ|ではない|でない|じゃない)?[。！？?]*\s*', raw[cut[5]:])
        if not side: raise Rejected("copula source grammar")
        left_text, right_text = raw[:left_end].strip(), side[1]
        lhs = entity.span.text
        if 'attribute' in roles: lhs += 'の' + roles['attribute'].span.text
        if left_text != lhs.strip() or right_text != value.span.text.strip(): raise Rejected("copula argument assignment")
        if 'attribute' in roles:
            link = entity.span.end - body.start
            ok = False
            for t in ctoks:
                if t[5] > cut[4]: break
                if t[4] == link and t[0] == 'の' and t[1] == '助詞' and cdepth[t[4]] == 0: ok = True
            if not ok: raise Rejected('copula attribute split is not at a particle token')
        vend = value.span.end - body.start
        vtoks = [t for t in ctoks if t[4] >= cut[5] and t[4] < vend and cdepth[t[4]] == 0]      # not inside a parenthetical gloss
        # a value written with no copula that ENDS in a chain of verbal auxiliaries after a verb / an adjective / a verbalising suffix is a verb the tagger
        # split, not a noun (an auxiliary inside a noun phrase, or the copula であった at the end, is not this)
        if not re.search(r'(?:です|である|だ|ではない|でない|じゃない|でした|だった|ではなかった|でなかった|じゃなかった)[。！？?]*\s*$', raw):
            vbody = [t for t in vtoks if t[1] not in ('補助記号', '記号')]
            n = len(vbody)
            while n and vbody[n - 1][1] == '助動詞': n -= 1
            if 0 < n < len(vbody):
                head = vbody[n - 1]
                copular_ari = head[1] == '動詞' and head[6] == 'ある' and n >= 2 and vbody[n - 2][0] == 'で'
                if not copular_ari and (head[1] in ('動詞', '形容詞') or (head[1] == '接尾辞' and head[2] == '動詞的')):
                    raise Rejected('copula value is a predicate phrase')
        while vtoks and (vtoks[-1][1] in ('助動詞', '補助記号', '記号')
                         or (vtoks[-1][1] == '動詞' and vtoks[-1][6] == 'ある' and len(vtoks) > 1 and vtoks[-2][0] == 'で')
                         or (vtoks[-1][1] == '助詞' and vtoks[-1][0] == 'で')):
            vtoks.pop()                                                                          # a trailing copula is not the value's predicate
        vcontent = [t for t in vtoks if t[1] not in ('助詞', '助動詞', '補助記号', '記号')]
        # a comparison standard: より after a noun/pronoun/の is one whatever tag it gets (前のより軽い: the tagger says 副詞)
        if any(t[0] == 'より' and (t[1] == '助詞' or (k > 0 and (vtoks[k - 1][1] in ('名詞', '代名詞', '数', '接尾辞')
                                                              or (vtoks[k - 1][1] == '助詞' and vtoks[k - 1][0] == 'の'))))
               for k, t in enumerate(vtoks)):
            raise Rejected('copula value is a predicate phrase')
        # a degree comparison: ほど / くらい / ぐらい / 並み after a noun, pronoun, number or の (先月ほど静か, 海くらい穏やか, 君のほど重い)
        if any(t[0] in _VT_DEGREE_MARKS and k > 0 and (vtoks[k - 1][1] in ('名詞', '代名詞', '数', '接尾辞')
                                                      or (vtoks[k - 1][1] == '助詞' and vtoks[k - 1][0] == 'の'))
               for k, t in enumerate(vtoks)):
            raise Rejected('copula value is a predicate phrase')
        if (vcontent and vcontent[-1][1] in ('形容詞', '形状詞', '動詞')
                and any(t[1] == '助詞' and t[0] in ('より', 'が', 'を', 'に', 'で', 'へ', 'から', 'まで', 'と') for t in vtoks)):
            raise Rejected('copula value is a predicate phrase')
        negative = bool(re.search(r'(?:ではない|でない|じゃない)[。！？?]*$', raw))
        if (clause.polarity == '-') != negative: raise Rejected("copula polarity")
        if clause.predicate != ('property' if 'attribute' in roles else 'identity'): raise Rejected("copula predicate")
        if clause.predicate_span != value.span: raise Rejected('copula predicate position')
        if clause.time: raise Rejected('unsupported copula time')
    elif clause.rule == 'frame':
        if (clause.span.start, clause.span.end) not in (ranges if ranges is not None else _ranges(view.sources[clause.span.source])):
            raise Rejected('event full-clause boundary')
        from .frames import canonical, read_all
        from .typed_edges import extract
        from .verdict import _clause_kind
        from .frames import _predicates
        from .typed_edges import _tagger, _base
        words = list(_tagger()(raw)); predicates = _predicates(words); all_frames = read_all(raw)
        cursor = 0; positions = []
        for word in words:
            at = raw.find(word.surface, cursor); positions.append(at); cursor = at+len(word.surface)
        predicates, all_frames = _filter_compound_predicates(words, positions, predicates, all_frames)
        tagged = tag(words, positions); pidx = [p0 for p0, _ in predicates]
        multi = len(all_frames) > 1
        if multi:
            # Plain te/renyō coordination only, with every predicate represented as its own clause.
            if (len(all_frames) != len(predicates) or _clause_kind(raw, 'record', False) != 'fact'
                    or not coordination_ok(tagged, pidx)):
                raise Rejected('unsupported multiple-event scope')
            sentence = sum(1 for c in view.clauses if c.rule == 'frame' and c.span == clause.span and c.body_span == clause.body_span)
            if sentence != len(all_frames): raise Rejected('coordinated clause omitted or duplicated')
        elif len(all_frames) != 1: raise Rejected('unsupported multiple-event scope')
        matching = [i for i, f in enumerate(all_frames) if i < len(predicates)
                    and body.start + positions[predicates[i][0]] == clause.predicate_span.start]
        if len(matching) != 1: raise Rejected("event predicate licensing")
        index = matching[0]
        if all_frames[index].predicate != clause.predicate and _case_order_predicate(
                clause, raw, body, words, positions, predicates[index][0]) != clause.predicate:
            raise Rejected("event predicate licensing")
        facts = [all_frames[index]]
        ev = predicates[index][0]
        c_first, c_last = chunk(tagged, pidx, index) if multi else (0, ev)
        lo = tagged[c_first][4] if multi and c_first < len(tagged) else 0
        if clause.predicate_span.end != body.start + positions[ev] + len(words[ev].surface):
            raise Rejected('event predicate end')
        frame = facts[0]; declared = {r.name: r.term for r in clause.roles}
        passive = ev + 1 < len(words) and _base(words[ev + 1]) in ('れる', 'られる')
        if (ev + 1 < len(words) and _base(words[ev + 1]) in ('せる', 'させる') and 'recipient' in declared
                and frame.predicate not in _VT_ADDRESSEE_VERBS):
            raise Rejected('causative frame: causer/causee unresolved')    # the causee is typed recipient by the frame reader
        benefactive = any(words[k].surface in ('て', 'で') and _base(words[k + 1]) in _VT_BENEFACTIVE for k in range(ev + 1, len(words) - 1))
        _po = raw.rfind(frame.patient, lo, positions[ev]) if frame.patient else -1
        has_object = _po >= 0 and _vt_following(tagged, _po + len(frame.patient)) in ('を', 'が')
        for name in ('agent', 'patient', 'recipient'):
            value = getattr(frame, name)
            allowed = {canonical(value)} if value else set()
            split = _role_split(value, clause.roles, name, raw, body, words, positions) if value else None
            if split: allowed.add(canonical(split[1]))
            if value:
                at = raw.rfind(value, lo, positions[ev])
                excluded = (_vt_participant_excluded(name, value, tagged, at + len(value), frame.predicate, passive, has_object, benefactive, frame.patient or None)
                            if at >= 0 else None)
                if excluded:      # the frame handed this phrase to the wrong role: it must not be declared as that role
                    if name in declared: raise Rejected('ill-typed event role: ' + excluded)
                    continue
            if value and declared.get(name) not in allowed: raise Rejected("event role assignment")
            if not value and name in declared: raise Rejected("invented event role")
        for role in clause.roles:
            if role.name in ('agent', 'patient', 'recipient') and multi and role.span.start - body.start < lo:
                # a phrase outside this clause's own tokens: only the topic-scope borrow of the first clause's agent
                topic = topic_phrase(tagged, pidx)
                if (role.name != 'agent' or index == 0 or topic is None
                        or (role.span.start - body.start, role.span.end - body.start) != topic
                        or own_subject_phrase(tagged, c_first, c_last)):
                    raise Rejected('unlicensed role borrowing')
        if _vt_te_auxiliary(words):
            # V-te/de [wa/mo] naranai/ikenai (any politeness; frame.negated is not required: the polite forms read the main verb as an affirmative): the clause is a prohibition / obligation, not an event
            raise Rejected('PROHIBITION_NOT_READ: negated auxiliary naru/ikeru after a conjunctive te/de')
        normalized = _clause_kind(raw, 'record', frame.negated)
        if not quoted and clause.modality not in ('quote', 'hedge', 'instruction'):
            expected = 'assert' if normalized == 'fact' else normalized
            if clause.modality != expected: raise Rejected("normative modality")
        normalized_neg = frame.negated and normalized not in ('prohibition', 'obligation')
        if (clause.polarity == '-') != normalized_neg: raise Rejected("event polarity")
        edges = extract(raw)
        if clause.modality == 'quote' and not quoted and not any(e.mod == 'quote' for e in edges):
            raise Rejected('invented quote modality')
        if clause.modality == 'hedge' and not any(e.mod in ('hedge','simile') for e in edges) and not re.search(r'はず|かもしれ|だろう|らしい|もし', raw):
            raise Rejected('invented hedge modality')
        for role in clause.roles:
            if role.name in ('agent', 'patient', 'recipient'): continue
            case = {'location': 'で', 'place': 'で', 'origin': 'から', 'source': 'から', 'instrument': 'で'}.get(role.name)
            compound = _CONSTRUCTION_PARTICLES.get(role.name)
            if role.name == 'setting':
                end = role.span.end - body.start
                if not _token_suffix(tagged, end, _CONSTRUCTION_PARTICLES['setting']):
                    raise Rejected('extra compound role')
            elif compound:
                end = role.span.end - body.start
                if not _token_suffix(tagged, end, compound): raise Rejected('extra compound role')
            elif role.name == 'location' and frame.predicate in _VT_LOCATIVE_VERBS and _token_suffix(
                    tagged, role.span.end - body.start, ('に',)):
                if not phrase_bounded(tagged, role.span.start - body.start, role.span.end - body.start): raise Rejected('location role')
            elif case and not re.search(re.escape(role.span.text) + case, raw): raise Rejected("extra case role")
            elif role.name == 'quantity' and not isinstance(role.term, Quantity): raise Rejected("quantity role")
            elif role.name == 'time' and not _time_role_licensed(role, body, tagged): raise Rejected("time role")
            elif role.name == 'direction':
                if not (_token_suffix(tagged, role.span.end - body.start, ('へ',)) and
                        phrase_bounded(tagged, role.span.start - body.start, role.span.end - body.start)): raise Rejected('direction role')
            elif role.name == 'goal':
                end = role.span.end - body.start
                if not (_token_suffix(tagged, end, ('に', 'へ')) and frame.predicate in _VT_MOTION_VERBS
                        and frame.predicate not in _VT_LOCATIVE_VERBS
                        and phrase_bounded(tagged, role.span.start - body.start, end)): raise Rejected('goal role')
            elif role.name == 'result':
                end = role.span.end - body.start
                if not (_token_suffix(tagged, end, ('に',)) and frame.predicate in _VT_RESULT_VERBS
                        and (_vt_is_time(role.span.text) or not role.span.text.endswith(('ため', 'よう', 'ほう', '方', 'とき', '時', '際', '間', 'うち', 'もの', 'こと', 'わけ', 'はず')))
                        and phrase_bounded(tagged, role.span.start - body.start, end)): raise Rejected('result role')
            elif not case and role.name not in ('quantity', 'time', 'result', 'direction', 'goal'): raise Rejected("unknown event role")
        # Reconstruct coverage from raw positions and licensed role spans.
        # Do not trust a canonical reader's unsupported flag or Frame's subset.
        licensed = [(r.span.start, r.span.end) for r in clause.roles]
        for name in ('agent', 'patient', 'recipient'):
            value = getattr(frame, name)
            split = _role_split(value, clause.roles, name, raw, body, words, positions) if value else None
            role = next((r for r in clause.roles if r.name == name), None)
            if split and role: licensed.append((role.span.start - len(split[0]), role.span.start))
        for role in clause.roles:
            if role.name not in ('agent', 'patient', 'recipient', 'origin', 'location',
                                 'place', 'time', 'capacity', 'topic', 'by', 'setting', 'target', 'accompaniment'): continue
            lo_, hi_ = role.span.start - body.start, role.span.end - body.start
            if multi and lo_ < lo: continue                       # the borrowed topic agent is checked above
            for a0, b0 in licensed:
                if b0 - body.start == lo_ and a0 < role.span.start: lo_ = a0 - body.start
            if not phrase_bounded(tagged, lo_, hi_): raise Rejected('unlicensed source content')
        licensed.append((clause.predicate_span.start, clause.predicate_span.end))
        if ev and _base(words[ev]) == 'する' and words[ev-1].feature.pos1 == '名詞' and _base(words[ev-1])+'する' == predicates[index][1]:
            licensed.append((body.start+positions[ev-1], body.start+positions[ev-1]+len(words[ev-1].surface)))
        for word, at in zip(words, positions):
            if multi and not (lo <= at < tagged[ev][5]): continue      # other clauses are checked as their own clauses
            if word.feature.pos1 in ('名詞', '代名詞', '形容詞', '形状詞', '副詞', '接頭辞', '接尾辞'):
                start = body.start + at
                if not any(a <= start and start + len(word.surface) <= b for a, b in licensed):
                    raise Rejected('unlicensed source content')
        if any(e.mod in ('quote', 'hedge', 'simile') for e in edges if e.head == clause.predicate) and clause.modality == 'assert':
            raise Rejected("nonasserted modality")
        # Independently inspect raw auxiliaries after the source predicate;
        # Frame.past can omit the tail of a compound verb.
        from .typed_edges import _base
        source_past = any(is_past_aux(w) for w in words[ev+1:])
        if clause.time not in ('past', 'nonpast') or (clause.time == 'past') != source_past: raise Rejected("tense licensing")
    elif clause.rule == 'measure':
        _license_measure(clause, body, raw, view)
    else:
        from .constructions import licensor
        construction = licensor(clause.rule)
        if construction is None: raise Rejected('unrecognized source grammar rule')
        source = view.sources[clause.span.source]
        boundaries = ranges if ranges is not None else _ranges(source)
        if (clause.span.start, clause.span.end) not in boundaries:
            raise Rejected('construction full-clause boundary')
        try:
            licensed = construction.licenses(clause, source)
        except Exception as exc:
            raise Rejected('construction licensor failure') from exc
        if licensed is not True: raise Rejected('construction source licensing')
    # Source metadata cannot erase an antecedent outside the body span.
    prefix = clause.span.text[:body.start - clause.span.start]
    if re.search(r'場合|なら(?!な)|たら|れば|ときは', prefix) and not clause.conditions:
        raise Rejected("missing source condition")
    for pattern, span in zip(clause.conditions, clause.condition_spans):
        if not _license_guard(pattern, span): raise Rejected("condition licensing")
    for pattern, span in zip(clause.exceptions, clause.exception_spans):
        if clause.rule != 'record':
            # A native exception belongs to the immediately following original
            # sentence. It cannot borrow a convenient assertion elsewhere.
            raw_source = view.sources[clause.span.source]
            following = next(((a, b) for a, b in sorted(_ranges(raw_source)) if a == clause.span.end), None)
            if not following or not re.match(r'\s*ただし', raw_source[following[0]:following[1]]):
                raise Rejected('exception source boundary')
            prefix = raw_source[following[0]:following[1]].lstrip()
            cm = re.match(r'^(.*?)(場合(?:は|には|に)?|ならば|(?<!な)(?<!けれ)なら(?!な)|(?<!なけ)れば|ときは|時は|際は|際には)[、,]?', prefix)
            start = following[1] - len(prefix)
            if not cm or (span.start, span.end, span.text) != (start, start+len(cm[1]), cm[1]):
                raise Rejected('exception full-prefix scope')
        if not _license_guard(pattern, span): raise Rejected("exception licensing")


def _license_guard(pattern, span):
    from .frames import canonical, read_all, _predicates
    from .typed_edges import _tagger, _base
    words = list(_tagger()(span.text)); predicates = _predicates(words)
    positions = []; cursor = 0
    for word in words:
        at = span.text.find(word.surface, cursor); positions.append(at); cursor = at + len(word.surface)
    predicates, _ = _filter_compound_predicates(words, positions, predicates)
    if any(w.feature.pos1 == '助詞' and w.surface in ('か', 'かな', 'かしら', 'かい', 'かね', 'っけ') for w in words):
        return False
    if any('意志推量' in str(w.feature.cForm) for w in words): return False
    if re.search(r'もし|だったなら|はず|かも|だろう|らしい|[「『]', span.text):
        return False
    past = bool(len(predicates) == 1 and any(is_past_aux(w)
                                           for w in words[predicates[0][0]+1:]))
    frames = read_all(span.text)
    if len(frames) == len(_predicates(words)):
        original = _predicates(words)
        indices = _compound_predicate_indices(words, positions)
        frames = [frame for frame, item in zip(frames, original) if item[0] not in indices]
    for frame in frames:
        roles = tuple((k, canonical(getattr(frame, k))) for k in ('agent', 'patient', 'recipient') if getattr(frame, k))
        if pattern.predicate == frame.predicate and pattern.roles == roles and pattern.polarity == ('-' if frame.negated else '+'):
            if len(frames) != 1 or len(predicates) != 1: return False
            from .verdict import _clause_kind
            if _clause_kind(span.text, 'record', frame.negated) != 'fact': return False
            positions = []; cursor = 0
            for word in words:
                at = span.text.find(word.surface, cursor); positions.append(at); cursor = at+len(word.surface)
            ev = predicates[0][0]
            covered = [(positions[ev], positions[ev]+len(words[ev].surface))]
            if ev and _base(words[ev]) == 'する' and words[ev-1].feature.pos1 == '名詞' and _base(words[ev-1])+'する' == predicates[0][1]:
                covered.append((positions[ev-1], positions[ev-1]+len(words[ev-1].surface)))
            for name in ('agent', 'patient', 'recipient'):
                value = getattr(frame, name)
                if value:
                    at = span.text.rfind(value, 0, positions[ev])
                    if at < 0: return False
                    covered.append((at, at+len(value)))
            for word, at in zip(words, positions):
                if word.feature.pos1 in ('名詞', '代名詞', '形容詞', '形状詞', '副詞', '接頭辞', '接尾辞'):
                    if not any(a <= at and at+len(word.surface) <= b for a, b in covered): return False
            return pattern.modality == 'assert' and pattern.time == ('past' if past else 'nonpast')
    m = re.fullmatch(r'(.*?)[はが](.*?)(?:です|だ|である)?[。]*', span.text)
    if m and pattern.predicate == 'identity':
        return dict(pattern.roles) == {'entity': m[1], 'value': m[2]} and pattern.polarity == '+'
    m = re.fullmatch(r'([A-Za-z_]+)\(([^()]+)\)', span.text)
    return bool(m and pattern.predicate == m[1] and pattern.roles == (('actor', m[2]),) and pattern.polarity == '+')


def _repair_prefix(clause):
    """A repair begins with a standalone interjection and comma, before its case frame."""
    from .typed_edges import _tagger
    raw = (clause.body_span or clause.span).text
    words = list(_tagger()(raw)); positions = []; cursor = 0
    for word in words:
        at = raw.find(word.surface, cursor); positions.append(at); cursor = at + len(word.surface)
    tokens = [(word, at) for word, at in zip(words, positions) if not word.surface.isspace()]
    if len(tokens) < 2: return False
    first, second = tokens[:2]
    if (first[0].feature.pos1 != '感動詞' or second[0].surface not in ('、', ',')
            or raw[:first[1]].strip() or raw[first[1] + len(first[0].surface):second[1]].strip()):
        return False
    return True


def _repair_replaces(prior, later, ranges):
    """License a one-slot case-frame repair over adjacent source sentences."""
    if (prior.rule != 'frame' or later.rule != 'frame'
            or prior.span.source != later.span.source
            or prior.sovereign != later.sovereign or prior.family != later.family
            or prior.predicate != later.predicate
            or (prior.polarity, prior.modality, prior.time) != (later.polarity, later.modality, later.time)
            or prior.conditions or prior.exceptions or later.conditions or later.exceptions
            or not _repair_prefix(later)):
        return False
    sentences = sorted(ranges)
    try: following = sentences[sentences.index((prior.span.start, prior.span.end)) + 1]
    except (ValueError, IndexError): return False
    if following != (later.span.start, later.span.end): return False
    old = {role.name: role.term for role in prior.roles}
    new = {role.name: role.term for role in later.roles}
    if old.keys() != new.keys(): return False
    changed = [name for name in old if old[name] != new[name]]
    return len(changed) == 1 and changed[0] in ('agent', 'patient', 'recipient')


def _w16t1b_written(plan, view, basis, op, answer):
    """W16-t1b K801 (written separately from the producer): a string answer is the written form of the source filler, not its canonical key.
    Two different written forms for one answer are rejected."""
    from .frames import canonical
    names = {}
    for node in plan.nodes:
        if node.op == 'Bind' and node.pattern is not None:
            for role_name, term in node.pattern.roles:
                if isinstance(term, Variable): names.setdefault(term.name, set()).add(role_name)
    out = []
    for (label, value), o in zip(answer, op.outputs):
        if isinstance(o.term, Variable) and not o.unit and isinstance(value, str):
            wanted = names.get(o.term.name, set())
            forms = {r.span.text for ident in basis if ident in view.by_id for r in view.by_id[ident].roles
                     if r.name in wanted and r.term == value and canonical(r.span.text) == r.term}
            if len(forms) > 1: raise Rejected('answer written forms differ')
            if len(forms) == 1: value = next(iter(forms))
        out.append((label, value))
    return tuple(out)


@dataclass
class State:
    env: dict
    covers: set
    basis: set
    conditions: set
    exceptions: set
    source: Clause | None = None
    answer: tuple = ()


class Checker:
    def __init__(self, view: View, sovereign: str, meter: Meter):
        self.view, self.sovereign, self.meter = view, sovereign, meter
        if view.invalid: raise Rejected('; '.join(view.invalid))
        self.clauses = []; self.index = {}; self.licensed = set()
        self.plan = None; self.predicates = set()
        self.effective = {}
        self.ranges = {}
        self.superseded_ids = {}
        self.sentence_clauses = {}
        self.fixed_request = None; self.fixed_plan = None; self.operators = None

    def _shape(self, request, plan):
        self.meter.spend()
        # Request/Plan and their relevant children are immutable dataclasses.
        # This avoids revalidating the same fixed plan for every proposal. It
        # conveys no trust to proof nodes, which are all replayed separately.
        if request is self.fixed_request and plan is self.fixed_plan:
            return self.operators
        self.meter.shape(plan, request)
        operators = request_shape(request, plan, self.meter.budget)
        self.fixed_request, self.fixed_plan, self.operators = request, plan, operators
        return operators

    def _source(self, clause):
        if not isinstance(clause,Clause) or not isinstance(clause.id,str): raise Rejected('source type')
        self.meter.spend(1 + len(clause.roles) + len(clause.conditions) + len(clause.exceptions))
        if clause.sovereign != self.sovereign: raise Rejected("sovereign splice")
        if clause != self.view.by_id.get(clause.id): raise Rejected("noncanonical source clause")
        if clause.id not in self.licensed:
            source = clause.span.source
            if source not in self.view.sources: raise Rejected('missing original source')
            if clause.rule != 'record' and source not in self.ranges:
                self.meter.spend(len(self.view.sources[source]))
                self.ranges[source] = _ranges(self.view.sources[source])
            license_clause(clause, self.view, self.ranges.get(source)); self.licensed.add(clause.id)

    def _superseded(self, clause):
        if clause.id in self.superseded_ids: return self.superseded_ids[clause.id]
        if clause.rule != 'frame':
            self.superseded_ids[clause.id] = False; return False
        source = clause.span.source; ranges = self.ranges.get(source)
        if ranges is None:
            self.meter.spend(len(self.view.sources[source]))
            ranges = self.ranges[source] = _ranges(self.view.sources[source])
        sentences = sorted(ranges)
        try: following = sentences[sentences.index((clause.span.start, clause.span.end)) + 1]
        except (ValueError, IndexError):
            self.superseded_ids[clause.id] = False; return False
        candidates = self.sentence_clauses.get((source, *following), ())
        for later in candidates:
            self.meter.spend()
            if (later.rule != 'frame' or later.sovereign != clause.sovereign
                    or later.family != clause.family or later.predicate != clause.predicate):
                continue
            self._source(later)
            if _repair_replaces(clause, later, ranges):
                self.superseded_ids[clause.id] = True; return True
        self.superseded_ids[clause.id] = False
        return False

    def _setup(self, plan):
        self.index = {}; self.predicates = set(); self.effective = {}; self.superseded_ids = {}
        self.sentence_clauses = {}; self.plan = plan
        todo = [n.pattern.predicate for n in plan.nodes if n.pattern]; seen = set(); selected = {}
        while todo:
            self.meter.spend(); pred = todo.pop()
            if pred in seen: continue
            seen.add(pred)
            pool = self.view.by_sovereign.get(self.sovereign, ()) if pred == '*' else self.view.by_predicate.get((self.sovereign, pred), ())
            for c in pool:
                self.meter.spend()
                if c.id in selected: continue
                selected[c.id] = c
                if len(selected) > self.meter.budget.candidates: raise Limit('candidates')
                self.meter.spend(len(c.conditions) + len(c.exceptions))
                todo.extend(p.predicate for p in (*c.conditions, *c.exceptions))
        self.clauses = list(selected.values())
        for c in self.clauses:
            self.sentence_clauses.setdefault((c.span.source, c.span.start, c.span.end), []).append(c)
        if len({c.family for c in self.clauses}) > 1: raise Rejected('family splice')
        for c in self.clauses:
            self.meter.spend(); self.index.setdefault((c.predicate, c.polarity, c.modality), []).append(c)
            self.predicates.add(c.predicate)

    def _pool(self, pattern, opposite=False):
        pol = ('-' if pattern.polarity == '+' else '+') if opposite else pattern.polarity
        polarities = ('+', '-') if pol == '*' else (pol,)
        modalities = ('permission', 'prohibition') if pattern.modality == 'normative' else (pattern.modality,)
        preds = self.predicates if pattern.predicate == '*' else (pattern.predicate,)
        for p in preds:
            for s in polarities:
                for m in modalities:
                    self.meter.spend()
                    yield from self.index.get((p, s, m), ())

    def _guard(self, pattern, env, negative=False, trail=()):
        positive = self._matching(pattern, env, trail)
        opposite = self._matching(pattern, env, trail, True)
        if positive and opposite: raise Conflict('opposing condition/exception evidence')
        return bool(opposite and not positive) if negative else bool(positive)

    def _matching(self, pattern, env, trail=(), opposite=False):
        found = []
        for c in self._pool(pattern, opposite):
            self.meter.spend(1 + len(pattern.roles))
            if _match(pattern, c, env, opposite) == env and self._effective(c, env, trail): found.append(c)
        return found

    def _effective(self, c, env, trail=()):
        self.meter.spend()
        if c.id in trail or c.unsupported: return False
        if len(trail) >= self.meter.budget.depth: return False
        self._source(c)
        key = (c.id, tuple(sorted(env.items())), frozenset(trail))
        if key in self.effective: return self.effective[key]
        if self._superseded(c):
            self.effective[key] = False; return False
        for guard in c.conditions:
            if not self._guard(guard, env, trail=(*trail, c.id)):
                self.effective[key] = False; return False
        for guard in c.exceptions:
            if not self._guard(guard, env, True, (*trail, c.id)):
                self.effective[key] = False; return False
        self.effective[key] = True; return True

    def _scope_support(self, state, op):
        ids = state.conditions if op == 'ApplyCondition' else state.exceptions
        guards = []
        for ident in sorted(ids):
            self.meter.spend(); c = self.view.by_id[ident]
            guards.extend((g, op == 'Except') for g in (c.conditions if op == 'ApplyCondition' else c.exceptions))
        return guards

    def audit(self, plan):
        """Enumerate independently to check omitted outputs and proof-external conflict."""
        self._setup(plan); tables = {}
        for op in plan.nodes:
            self.meter.spend(); ins = [tables[i] for i in op.inputs]; out = []
            if op.op == 'Bind':
                for c in self._pool(op.pattern):
                    self.meter.spend(); env = _match(op.pattern, c)
                    if env is None or c.unsupported: continue
                    self._source(c)
                    if self._superseded(c): continue
                    opposite = Pattern(op.pattern.predicate, op.pattern.roles,
                                       '-' if c.polarity == '+' else '+', op.pattern.modality, op.pattern.time, op.pattern.event)
                    if op.pattern.modality == 'normative':
                        opposite = Pattern(op.pattern.predicate, op.pattern.roles, c.polarity,
                                           'prohibition' if c.modality == 'permission' else 'permission', op.pattern.time, op.pattern.event)
                    for opponent in self._pool(opposite):
                            self.meter.spend()
                            if _match(opposite, opponent, env) is not None and self._effective(c, env) and self._effective(opponent, env):
                                raise Conflict('applicable opponent outside proof')
                    if op.relation in ('whether','whether-negative'): env[op.target.name] = c.modality == 'permission' if op.pattern.modality == 'normative' else c.polarity == ('-' if op.relation == 'whether-negative' else '+')
                    out.append(State(env, set(op.obligations), {c.id}, {c.id} if c.conditions else set(), {c.id} if c.exceptions else set()))
            elif op.op == 'Join':
                for a in ins[0]:
                    for b in ins[1]:
                        self.meter.spend()
                        if any(a.env[k] != b.env[k] for k in a.env.keys() & b.env.keys()): continue
                        out.append(State(a.env | b.env, a.covers | b.covers | set(op.obligations), a.basis | b.basis, a.conditions | b.conditions, a.exceptions | b.exceptions))
            elif op.op in ('ApplyCondition', 'Except'):
                for a in ins[0]:
                    self.meter.spend(); ok = True
                    for guard, negative in self._scope_support(a, op.op):
                        if not self._guard(guard, a.env, negative): ok = False; break
                    if ok: out.append(State(a.env, a.covers | set(op.obligations), a.basis,
                                            set() if op.op == 'ApplyCondition' else a.conditions,
                                            set() if op.op == 'Except' else a.exceptions))
            else:
                for a in ins[0]:
                    self.meter.spend()
                    if op.op == 'Project' and (a.conditions or a.exceptions): continue
                    result = _calc(op, a.env)
                    if result and op.op == 'Project': result = (result[0], _w16t1b_written(plan, self.view, a.basis, op, result[1]))
                    if result: out.append(State(result[0], a.covers | set(op.obligations), a.basis, a.conditions, a.exceptions, answer=result[1]))
            unique = {}
            for a in out:
                self.meter.spend(); unique.setdefault((tuple(sorted(a.env.items())), tuple(sorted(a.basis)), tuple(sorted(a.conditions)), tuple(sorted(a.exceptions))), a)
            self.meter.states(len({tuple(sorted(a.env.items())) for a in unique.values()})); tables[op.id] = list(unique.values())
        return {s.answer for s in tables[plan.root]}

    def proof(self, request: Request, plan: Plan, proof: Proof, allow_superseded=False):
        operators = self._shape(request, plan)
        if self.plan != plan: self._setup(plan)
        if proof.sovereign != self.sovereign: raise Rejected('proof sovereign')
        nodes = {}; states = {}; depths = {}
        for node in proof.nodes:
            if (not isinstance(node,ProofNode) or not isinstance(node.id,str) or not isinstance(node.op,str)
                or not all(isinstance(getattr(node,f),tuple) for f in ('parents','bindings','covers','answer'))
                or any(not isinstance(p,str) for p in node.parents)):
                raise Rejected('proof field types')
            self.meter.spend(1 + len(node.parents) + len(node.bindings) + len(node.covers) + len(node.answer))
            if node.id in nodes or any(p not in nodes for p in node.parents): raise Rejected('duplicate/cyclic/missing proof reference')
            depths[node.id] = 1 + max((depths[p] for p in node.parents), default=0)
            if depths[node.id] > self.meter.budget.depth: raise Limit('depth')
            parents = [states[p] for p in node.parents]
            if node.op == 'Source':
                if node.parents or node.plan_node or node.clause is None: raise Rejected('Source arity')
                c = node.clause
                self._source(c); state = State({}, set(), {c.id}, {c.id} if c.conditions else set(),
                                               {c.id} if c.exceptions else set(), c)
            elif node.op == 'Witness':
                if not parents or parents[0].source is None or node.plan_node or node.clause: raise Rejected('guard witness shape')
                c = parents[0].source; env = dict(node.bindings)
                guards = [(g, False) for g in c.conditions] + [(g, True) for g in c.exceptions]
                if len(parents) != 1 + len(guards): raise Rejected('missing guard witness')
                for (g, negative), p in zip(guards, parents[1:]):
                    if not p.source or p.conditions or p.exceptions or p.env != env or _match(g, p.source, env, negative) != env:
                        raise Rejected('guard witness does not discharge source condition')
                    if not self._guard(g, env, negative, (c.id,)):
                        raise Rejected('guard witness lacks consistent applicable support')
                state = State(env, set(), {c.id}, set(), set(), c)
            else:
                if node.clause or node.plan_node not in operators: raise Rejected('operator/source mismatch')
                op = operators[node.plan_node]
                if op.op != node.op: raise Rejected('operator mismatch')
                head = node.parents[:len(op.inputs)]
                if tuple(nodes[p].plan_node for p in head) != op.inputs: raise Rejected('plan dependency splice')
                if op.op == 'Bind':
                    if len(parents) != 1 or parents[0].source is None: raise Rejected('Bind source')
                    c = parents[0].source; env = _match(op.pattern, c)
                    if env is None: raise Rejected('Bind roles/polarity/time')
                    if self._superseded(c) and not allow_superseded: raise Rejected('superseded source claim')
                    if op.relation in ('whether','whether-negative'): env[op.target.name] = c.modality == 'permission' if op.pattern.modality == 'normative' else c.polarity == ('-' if op.relation == 'whether-negative' else '+')
                    state = State(env, set(op.obligations), {c.id}, {c.id} if c.conditions else set(), {c.id} if c.exceptions else set())
                elif op.op == 'Join':
                    if len(parents) != 2: raise Rejected('Join arity')
                    a, b = parents
                    if any(a.env[k] != b.env[k] for k in a.env.keys() & b.env.keys()): raise Rejected('Join shared variable')
                    state = State(a.env | b.env, a.covers | b.covers | set(op.obligations), a.basis | b.basis, a.conditions | b.conditions, a.exceptions | b.exceptions)
                elif op.op in ('ApplyCondition', 'Except'):
                    if not parents: raise Rejected('scope arity')
                    a = parents[0]; guards = self._scope_support(a, op.op)
                    if len(parents) != len(guards) + 1: raise Rejected('source scope missing')
                    for (guard, negative), p in zip(guards, parents[1:]):
                        if not p.source or p.conditions or p.exceptions or p.env != a.env or _match(guard, p.source, a.env, negative) != a.env:
                            raise Rejected('source scope mismatch')
                        if not self._guard(guard, a.env, negative):
                            raise Rejected('source scope has opposing/missing support')
                    state = State(a.env, a.covers | set(op.obligations), a.basis,
                                  set() if op.op == 'ApplyCondition' else a.conditions,
                                  set() if op.op == 'Except' else a.exceptions)
                else:
                    if len(parents) != 1: raise Rejected('operator proof arity')
                    a = parents[0]
                    if op.op == 'Project' and (a.conditions or a.exceptions): raise Rejected('unresolved ancestor scope')
                    result = _calc(op, a.env)
                    if result is not None and op.op == 'Project': result = (result[0], _w16t1b_written(plan, self.view, a.basis, op, result[1]))
                    if result is None: raise Rejected('false filter')
                    state = State(result[0], a.covers | set(op.obligations), a.basis, a.conditions, a.exceptions, answer=result[1])
            if tuple(sorted(state.env.items())) != node.bindings or tuple(sorted(state.covers)) != node.covers or state.answer != node.answer:
                raise Rejected('producer binding/coverage/answer differs from replay')
            states[node.id] = state; nodes[node.id] = node
        if proof.root not in nodes or nodes[proof.root].plan_node != plan.root: raise Rejected('root mismatch')
        reachable = set(); todo = [proof.root]
        while todo:
            self.meter.spend(); k = todo.pop()
            if k not in reachable: reachable.add(k); todo.extend(nodes[k].parents)
        if reachable != set(nodes): raise Rejected('unreachable proof node')
        state = states[proof.root]
        if state.covers != {o.id for o in request.obligations}: raise Rejected('incomplete obligations')
        return state.answer

    def gate(self, request, plan, proposals):
        self._shape(request, plan)
        expected = self.audit(plan)
        checked = {}
        for answer, proof in proposals:
            self.meter.spend()
            replayed = self.proof(request, plan, proof, allow_superseded=True)
            if replayed != answer: raise Rejected('claimed answer/proof mismatch')
            sources = {node.clause.id for node in proof.nodes if node.op == 'Source'}
            if sources and all(self._superseded(self.view.by_id[ident]) for ident in sources): continue
            if answer not in expected: raise Rejected('producer omitted/invented alternative answers')
            # Validate every submitted proof; duplicates may share only the
            # final rendering, never a cached acceptance of unchecked content.
            checked.setdefault(answer, (replayed, proof))
        if set(checked) != expected: raise Rejected('producer omitted/invented alternative answers')
        if not checked: return {}
        return checked
