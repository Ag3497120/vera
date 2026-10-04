"""A bounded, compositional Japanese reader for Round5-A.

Frame/Edge/Stage/Item readings are candidates. Their roles stay clause-local;
unknown constructions remain source-bound Unread records rather than slots.
"""
from __future__ import annotations

import hashlib
import re
import time
from dataclasses import replace
from decimal import Decimal

from .frames import CONVERSE, canonical, read_all, _predicates, transitivity as _transitivity
from .question import Stage
from .semantic_coord import chunk, coordination_ok, own_subject_phrase, phrase_bounded, topic_phrase, tag
from .semantic_names import is_past_aux, name_split_in, tokens_covering
from .semantic_ir import (Limit, Budget, Clause, Nominal, Obligation, Operator, Output,
                          Pattern, Plan, Quantity, Request, Role, Span, Test, Unread, Variable, View)
from .typed_edges import _base, _tagger, extract
from .verdict import COND, _clause_kind, read_records

_NUM = re.compile(r'([+-]?[0-9]+(?:\.[0-9]+)?)\s*([A-Za-z%]+|[一-鿿]+)')
_WH = re.compile(r'誰|だれ|何|どこ|いつ|どちら|いくつ')
# The copula だ is dropped, but not the past auxiliary だ after a 撥音便/イ音便 stem (呼んだ, 泳いだ).
_END = re.compile(r'(?:ですか|ますか|でしょうか|です|(?<![んい])だ|か)?[？?。！!]*$')
_MODAL_UNSUPPORTED = re.compile(r'もし|だったなら|はず|かもしれ|だろう|らしい|そう(?:だ|です|だった|でした)')
_COMPLEX = re.compile(r'すべて|全部|それぞれ|最後|最初|同時|前後|以前|以後|最新|現在|今日|昨日|今年|午前|午後|[0-9]+[年月日時]|ただし|以外|除[くき]|のみ|だけ|必ず')
_ROLE_WORDS = {'受取人': 'recipient', '受領者': 'recipient', '渡した人': 'agent',
               '作成者': 'agent', '起点': 'origin', '終点': 'recipient', '相手': 'recipient'}
_DOUBLE_NEGATION = re.compile(r'(?:ない|なかった|なく|ぬ)(?:わけ|こと|もの)(?:では|じゃ|は|も)|なくはない|ないとは限らない')
_NEGATIVE_ADJECTIVE = re.compile(r'(?:くない|くありません|くなかった|くありませんでした)[。！？?]*$')
_TIME_DATE = r'(?:[0-9０-９]+年(?:[0-9０-９]{1,2}月(?:[0-9０-９]{1,2}日)?)?|(?:明治|大正|昭和|平成|令和)[0-9０-９]+年(?:[0-9０-９]{1,2}月(?:[0-9０-９]{1,2}日)?)?)'
_TIME_NOMINAL = re.compile(r'(?:' + _TIME_DATE + r'|[0-9０-９]+\s*(?:月|日|時|分|秒|曜日)|頃|ごろ|午前|午後|朝|昼|夜)\Z')
_TIME_ADVERBIAL = re.compile(r'(' + _TIME_DATE + r'|[0-9０-９]+(?:月|日|時|分|秒|曜日))\s*[、,]')
_COMPOUND_PARTICLES = (
    ('における', 'setting'), ('において', 'setting'), ('について', 'topic'),
    ('に対して', 'target'), ('では', 'topic'),
    ('として', 'capacity'), ('と共に', 'accompaniment'), ('ともに', 'accompaniment'),
    ('によって', 'by'), ('による', 'by'), ('により', 'by'),
)
_GOAL_PREDICATES = frozenset(('行く','来る','帰る','戻る','向かう','着く','入る','出る','進む','移る','渡る','送る','届ける'))
_LOCATION_PREDICATES = frozenset(('住む','滞在する','位置する','存在する'))
_MEANS_NOMINALS = frozenset(('車','電車','バス','飛行機','船','自転車','徒歩','手','指','箸','包丁','ペン','鉛筆','電話','メール','日本語','英語','道具','方法','手段'))
_PLACE_NOMINALS = frozenset(('学校','家','駅','公園','部屋','店','会社','図書館','病院','工場','東京','大阪','京都','日本','教室','庭','海','山'))
# A noun naming a facility/area/shop ends in one of these (…場, …所, …局, …館). Not 道/橋/線: 鉄道で is a means, not a place.
_PLACE_SUFFIXES = ('学校','駅','公園','会社','図書館','病院','市','町','県','国','室',
                   '場','所','局','館','園','院','寺','署','店','港','庫','村','区','島','城','堂','庁','省')

# ---------------------------------------------------------------------------------------------------------------------
# W1-a: role typing. frames.py (shared, read-only for this work) hands the first に/は/が phrase to the first free slot,
# so a time word can arrive as an "agent" and a goal/result/place as a "recipient". The reader therefore types every
# phrase before it becomes a participant: a phrase of the wrong type is not claimed as that role; it is re-read as the
# adjunct it is (time/place/result/direction) or the clause is returned unsupported with a typed reason.
# semantic_verify.py re-derives the same facts with its own tokenization and its own rules (it does not import this).
# ---------------------------------------------------------------------------------------------------------------------
_ERA_YEAR = _TIME_DATE                       # year / year-month / year-month-day, with or without an era name (defined above)
_ERA_NAMES = re.search(r'\(\?:([^()]*)\)\[0-9０-９\]\+年', _TIME_DATE).group(1)      # the era names _TIME_DATE already lists (a closed class)
# ---- What a time phrase is (positive criteria; a phrase that meets none of them is NOT time, whatever its part of speech) ----
# (1) numeric: [part of day] [approx] [relative-year prefix] (number + time counter)+ [time tail]
#       6時半, 3時過ぎ, 2時間後, 午後3時, 夜9時, 数日後, 10日間, 2020年代, 3月上旬, 5月5日, 3年前
# (2) lexical: a noun carrying a time morpheme (朝昼晩夜夕午週月年日曜期代世季春夏秋冬頃旬暮宵刻前後今昔現将初末) or one of the
#     closed deictic/relative time words, tagged 副詞可能 (a nominal that can also be an adverb); a 副詞可能 noun that names no
#     time (結局 実際 一部 以上 全部 …) is not a time phrase.
# (3) X前 / X後: a time only when X is an event noun (入学前), a time word, or the 後/前 is a suffix (退局後); a place + 前
#     (校舎前) is not. A relational noun alone (前 上 中 時 …) is never a time.
# A の-modified phrase is a time when its head is (先週の金曜日, 式典の翌日, 去年の夏).
_TNUM = r'[0-9０-９〇一二三四五六七八九十百千万数]'
_TCOUNTER = r'(?:年代|年度|年間|年|か月間|か月|ヶ月間|ヶ月|カ月|ケ月|月間|月|週間|週|日間|日|時間|時|分間|分|秒間|秒|世紀|曜日)'
_TTAIL = r'(?:半|過ぎ|すぎ|前|後|頃|ごろ|以降|以前|以後|以内|末|初め|初頭|初旬|上旬|中旬|下旬|目)'
_TIME_NUMERIC_HEAD = re.compile(
    r'(?:午前|午後|早朝|朝|昼|夕方|夕|夜|晩|深夜|未明)?(?:約|およそ|ほぼ)?(?:' + _ERA_NAMES + r'|西暦|紀元前)?'
    r'(?:(?:同|当|翌|前|昨|来|今|本|去|各|毎)(?:年|月)?(?=' + _TNUM + r'))?'
    r'(?:' + _TIME_DATE + r'|' + _TNUM + r'+' + _TCOUNTER + r')+(?:' + _TTAIL + r')*')
_TIME_MORPHEMES = '朝昼晩夜夕午週月年日曜期代世季春夏秋冬頃旬暮宵刻前後今昔現将初末'
_TIME_WORDS = frozenset(('最近', '近年', '近頃', '以降', '以前', '以後', '現在', '将来', '当時', '当初', '昔', '今後', '今回', '先日',
                         '後日', '目下', '未明', '次', 'きょう', 'あした', 'あす', 'あさ', 'けさ', 'ゆうべ', 'いま', 'のち',
                         '元日', '元旦', '大晦日', '正月', 'お盆', '彼岸', '冬至', '夏至', '春分', '秋分', '夏休み', '冬休み', '春休み', '昼休み', '放課後', '連休', '祝日', '休日', '誕生日', '記念日'))
_NOT_TIME = frozenset(('日常',))              # holds a time character, names no time
# Relational / spatial nouns are 副詞可能 too (…の前, 上, 中, 時): a time phrase is never headed by one of them alone.
_SPATIAL_HEADS = frozenset(('前','後','上','下','中','外','内','横','隣','奥','側','辺','辺り','先','手前','間','際','うち','途中','とき','時'))
# W1-a round 3: a person/organisation is recognised by POSITIVE evidence, never by the last characters of a word. A word that merely
# ends like an organisation suffix is not one (神社・教会・茶会・大会 end in 社/会, 外部・胸部・一部 in 部, 高校 in 校, 山間部・出力部 are a
# region / a machine part): the suffix characters are shared by organisations, events, places and body/regional parts, so they decide
# nothing. What counts (see _is_person_phrase): a closed class of person / collective-actor nouns (below), a pronoun, a person-role
# noun, a bare proper name (人名・組織名 as the head), a person/plural suffix TOKEN after a noun (名前＋さん, 子供達), a group suffix
# TOKEN after a noun (消防団, 探検隊: the tagger marks 団/隊 as 接尾辞 only in that use) or 会 after a person-role noun (委員会).
# Anything else is not claimed as an agent (the clause is returned unsupported), whatever its ending.
_PERSON_SUFFIX_TOKENS = frozenset(('さん','氏','君','様','殿','達','たち','ども','ちゃん'))
_GROUP_SUFFIX_TOKENS = frozenset(('団','隊','軍','チーム'))        # 団/隊 are tagged 接尾辞; 軍/チーム are nouns that name a body of persons after another noun (連合軍, 開発チーム)
# Person-denoting common nouns that carry no person suffix: kinship terms, generic person words, collective persons.
_PERSON_NOUNS = frozenset(('甥','姪','いとこ','親','子','孫','祖先','客','人','男','女','若者','老人','幼児','乳児','赤ん坊','赤ちゃん',
                           '友','友達','仲間','隣人','相手','他人','先方','本人','当人','同僚','家族','夫婦','兄弟','親子','子ども','子供',
                           '大人','住民','市民','国民','村人','町民','観客','聴衆','乗客','来場者','全員','皆','誰',
                           # organisations that act, kin and ranks the person suffixes miss
                           '警察','企業','当局','軍隊','議会','内閣','政権','政府','軍','協会','機関','組合','劇団','財団','役所','役場',
                           '国会','政党','与党','野党','検察','部隊','軍団','教団','陸軍','海軍','空軍','米軍','敵軍','山賊','海賊','盗賊','刑事','チーム','理事会','取締役会','評議会','母親','父親','両親','おじ','おば','叔母','伯父','伯母',
                           '首相','大統領','皇帝','天皇','神','泥棒','敵','味方','クラスメート','審判',
                           '見習い','来賓','来客','弟子','師匠','新人','常連','達人','住職','僧侶','神主','巫女','王','女王','姫','勇者','英雄',
                           # animate non-persons: an animal can act (猿に食べられた), so it is a possible agent/addressee
                           '犬','猫','鳥','猿','熊','鹿','猪','馬','牛','豚','羊','山羊','兎','鼠','狐','狸','狼','虎','獅子','象','蛇','蛙','魚',
                           '虫','蜂','蚊','蟻','烏','鷲','鷹','雀','鶏','鳩','燕','イヌ','ネコ','サル','クマ','シカ','ウマ','ウシ','ブタ'))

# W1-a round 4 (N1): the ending characters of a word decide nothing about whether it is a person. What counts is listed here or
# in _is_person_phrase and is POSITIVE evidence only. The closed classes below take a word ONLY when every sense of the word names a
# person (or a body of persons): 歌手 is always a singer; 雨戸 is never a person, and a word that has a person sense and a non-person
# sense (本家, 旧家, 先方の家) is not listed. A word that is not listed is "not shown to be a person", never "shown not to be one".
_PERSON_OCCUPATION_WORDS = frozenset(('兵士','兵隊','軍人','役人','商人','住人','町人','旅人','恋人','夫人','婦人','青年','少年','少女','武士','騎士','隊員','団員','部員','局員','署員','係員','駅員','船員','乗員','要員','党員','教員','歌手','作家','画家','村長','町長','市長','区長','知事','委員','役員','議員','議長','会長','幹事','理事',
                                      '取締役','評議員','会員','主人','店主','社員','職人','医者','学者','飼い主','持ち主','地主','家主',
                                      '船長','機長','艦長','隊長','団長','局長','署長','所長','館長','園長','院長','組長','学長'))
_PERSON_NOUNS = _PERSON_NOUNS | _PERSON_OCCUPATION_WORDS
# The person-role words of frames.ROLES that name a person in EVERY sense, copied here so that the class is closed in this module (frames.ROLES also
# lists a word that names a building as well as a farmer; that one is left out, and frames._LEARNED is not used at all: round 5, M1).
_ROLE_NOUNS = frozenset(('シェフ','上司','伯母','伯父','住民','作業員','係長','兄','先生','先輩','助手','医師','友人','叔母','叔父','司書','同僚','夫','妹','妻','姉','娘','学生','孫','工員','店員','店長','弟','後輩','息子','患者','技師','担任','指揮者','教師','教授','料理人','校長','検査員','母','消防士','漁師','父','班長','理学療法士','生徒','監督','看護師','社長','祖母','祖父','職員','船長','薬剤師','記者','課長','警察官','運転手','選手','部下','部長'))
_PERSON_NOUNS = _PERSON_NOUNS | _ROLE_NOUNS
# person-role suffix TOKENS: the tagger marks these 接尾辞 only when they close a person-role compound (整備士, 研修生, 警察官, 薬剤師, 事務員,
# 保護者). A word the tagger keeps as ONE token (隣家, 欠員, 最長) has no suffix token and is not matched by them.
_HOUSE_SUFFIX_TOKENS = frozenset(('家',))        # a suffix that is a person after a common noun (a trade) but a person AND a building after a family name
_PERSON_ROLE_SUFFIX_TOKENS = frozenset(('士','生','主','医','者','人','手','員','民','師','長','係','官','家','将','婦','夫'))
# a body of persons named after its members: 委員会, 審査委員会, 役員会 (the member noun is a person in every sense)
_MEMBER_NOUNS = frozenset(('委員','理事','役員','取締役','評議員','議員','幹事','監事','会員'))
# A post / office conferred by selection or appointment (the に-phrase of 選ばれた / 任命された is that post, as in "was chosen as ...").
# Closed class: a noun that names an office, never a kinship term or a plain occupation (友人, 先生, 患者, 母 are not posts).
_POST_NOUNS = frozenset(('社長','部長','課長','係長','班長','店長','校長','議長','会長','委員長','委員','理事','幹事','代表','主任','監督','館長',
                         '院長','所長','局長','署長','組長','村長','町長','市長','区長','知事','学長','園長','艦長','隊長','団長','船長',
                         '機長','首相','大統領','総理','総裁','キャプテン','リーダー','主将','教授','役員','議員','取締役','支店長','工場長'))
_POST_SUFFIX_TOKENS = frozenset(('長','係'))           # <noun>+長 / <noun>+係 as two tokens: 学部長, 連絡係


def _word_features(text):
    return [(w.surface, w.feature.pos1, w.feature.pos2, w.feature.pos3) for w in _tagger()(text)]


_TIME_FINAL_STEMS = ('明け', '末', '初め', '初頭')            # 年明け, 週明け, 期末, 月末, 年度末, 学期初め: a time morpheme + one of these
_TIME_FINAL_WORDS = ('年度', '学期', '世紀', '時代', '時期', '期間')


def _time_final(surface):
    """A compound the tagger does not mark 副詞可能 but that ends like a time: <time morpheme> + 明け/末/初め (結末, 文末 do not: no
    time morpheme before the 末), or a period word (年度, 学期, 世紀, 時代)."""
    for tail in _TIME_FINAL_STEMS:
        if surface.endswith(tail) and len(surface) > len(tail) and any(ch in _TIME_MORPHEMES for ch in surface[:-len(tail)]): return True
    return surface in _TIME_FINAL_WORDS


def _time_token(f):
    return f[0] in _TIME_WORDS or (f[0] not in _NOT_TIME and any(ch in _TIME_MORPHEMES for ch in f[0]))


def _time_segment(feats):
    """A particle-free run of tokens that is a lexical time phrase (criteria 2 and 3)."""
    if not feats or len(feats) > 4: return False
    if any(f[1] not in ('名詞', '接頭辞', '接尾辞', '連体詞') or f[2] in ('固有名詞', '数詞') for f in feats): return False
    if ''.join(f[0] for f in feats) in _TIME_WORDS or _time_final(feats[-1][0]): return True   # a calendar word / period compound the tagger does not mark 副詞可能
    if feats[-1][0] == '日' and len(feats) >= 2: return True                                  # <noun>日: 給料日, 定休日, 開業日 (a day named by what happens on it)
    if feats[-1][3] != '副詞可能' and feats[-1][0] != '間際': return False
    core = [f for f in feats if f[1] not in ('接頭辞', '連体詞')]
    if not core: return False
    last = core[-1]
    if last[0] == '中' or (last[0] == '間際' and len(core) >= 2):         # 試合中, 食事中, 閉館間際: <event noun> + during / just before
        return len(core) >= 2 and core[-2][3] == 'サ変可能'
    if last[0] in ('前', '後'):
        if len(core) < 2: return feats[0][1] == '連体詞'                # その後, この前
        prev = core[-2]
        if last[1] == '接尾辞': return True                              # 退局後, 食後: the 後/前 suffix makes a time of its stem
        return prev[3] == 'サ変可能' or _time_token(prev)                # 入学前, 昨年前; 校舎前 is a place
    if last[0] in _SPATIAL_HEADS: return False
    return any(_time_token(f) for f in core)


def _time_text(text, feats):
    if _TIME_NUMERIC_HEAD.fullmatch(text): return True
    m = _TIME_NUMERIC_HEAD.match(text)
    if m and 0 < m.end() < len(text):                                    # 2030年春, 3年前の夏 is handled by の below
        rest = text[m.end():]
        return _time_segment(_word_features(rest))
    return _time_segment(feats)


def _is_time_phrase(phrase):
    """A phrase that names a time (criteria in the block above). Never one that holds a proper noun (…朝 of a dynasty), a
    particle other than の, or whose head is a spatial/relational noun (…の前, 駅前)."""
    compact = phrase.replace(' ', '').replace('　', '')
    if not compact: return False
    if _TIME_NUMERIC_HEAD.fullmatch(compact): return True
    feats = _word_features(compact)
    if not feats: return False
    segments = [[]]
    for f in feats:
        if f[1] == '助詞':
            if f[0] != 'の' or not segments[-1]: return False
            segments.append([]); continue
        if f[1] in ('動詞', '助動詞', '補助記号', '記号', '副詞'): return False
        segments[-1].append(f)
    if not segments[-1]: return False
    head = segments[-1]
    # <event noun>の前 / <event noun>の後 (試合の後, 手術の前): after/before an event; a place + の前 (駅の前) is not a time
    if (len(head) == 1 and head[0][0] in ('前', '後') and len(segments) >= 2 and segments[-2]
            and segments[-2][-1][3] == 'サ変可能'):
        return True
    return _time_text(''.join(f[0] for f in head), head)


def _time_fused(phrase):
    """A time word glued to another participant noun (<time noun><person>, <time noun>、<person>): a role must not swallow
    its own time adjunct."""
    compact = phrase.replace(' ', '').replace('　', '')
    parts = [p for p in re.split(r'[、,]', compact) if p]
    if len(parts) > 1: return any(_is_time_phrase(p) for p in parts)
    feats = _word_features(compact)
    if len(feats) < 2 or _is_time_phrase(compact): return False
    if any(f[1] not in ('名詞', '接尾辞', '接頭辞', '連体詞') for f in feats): return False
    for k in range(1, len(feats)):
        left = feats[:k]
        if feats[k][1] == '接尾辞': continue                                # 来週 + 末 is one word, not a time + noun
        if _time_text(''.join(f[0] for f in left), left): return True
    return False


def _is_place_phrase(phrase):
    compact = phrase.replace(' ', '').replace('　', '')
    segments = compact.split('の'); head = segments[-1]
    # <place>前 / <place>内 / <place>の隅: a spatial tail on a place is still that place
    options = [head]
    for tail in ('前', '内', '上', '中', '周辺', '近く', '付近', '隅', '奥', '脇', '横', '隣', '角', '裏', '先', '方面'):
        if head.endswith(tail) and len(head) > len(tail): options.append(head[:-len(tail)])
        if head == tail and len(segments) > 1: options.append(segments[-2])
    if any(o in _PLACE_NOMINALS or any(o.endswith(x) for x in _PLACE_SUFFIXES) for o in options): return True
    feats = _word_features(compact)
    return bool(feats) and feats[-1][1] == '名詞' and feats[-1][2] == '固有名詞' and feats[-1][3] == '地名'


# Nouns that name a scheduled GATHERING one goes to or takes part in (会議に出る, 試合に行く): every sense is an event held somewhere at a time, so the
# に-phrase of a verb of going / leaving is where one goes (the event), not a purpose. NOT an activity (散歩, 勉強, 旅行, 釣り: one goes IN ORDER
# to do it; that is a purpose, which the convention has no role for).
_GATHERING_NOUNS = frozenset(('会議','会合','集会','総会','授業','講義','試合','式典','面接','宴会','結婚式','葬儀'))


def _is_end_point(phrase):
    """Evidence that the に/へ-phrase of a verb of motion is where one goes: a place (_is_place_phrase), a gathering (_GATHERING_NOUNS) or a person
    (_is_person_phrase: one goes TO somebody; _recipient_claim keeps such a phrase as the recipient, and this keeps the same phrase when the
    shared frame reader split it into a descriptor and a name: 店長 + サキ)."""
    compact = phrase.replace(' ', '').replace('　', '')
    return _is_place_phrase(compact) or compact.split('の')[-1] in _GATHERING_NOUNS or _is_person_phrase(compact)


def _is_person_phrase(phrase):
    """A participant that can receive/address/act: a person name, pronoun, role noun, or an organisation noun. Positive evidence on
    the HEAD of the phrase (the part after the last の) only; the ending characters of a word decide nothing. Evidence:
      (a) the head is a word of a closed class that names persons in every sense (_PERSON_NOUNS, which holds _ROLE_NOUNS). frames._LEARNED (a
          corpus count of katakana words written before a name: it holds names of instruments, appliances, cities ...) is NOT such a class and is not consulted;
      (b) the last token is a pronoun;
      (c) the last token is a proper noun of a person / organisation / unspecified kind;
      (d) two or more tokens whose last token is a person-role / honorific / group SUFFIX token after a noun (整備士, <名前>さん, 子供達);
      (e) two or more tokens whose last token is the noun 軍 / チーム / 客 after a noun (連合軍, 開発チーム, 観光客);
      (f) <X>会 where X is a person or ends in a member noun (委員会, 審査委員会): a body of persons."""
    compact = phrase.replace(' ', '').replace('　', '')
    head = compact.split('の')[-1]
    if not head: return False
    if head in _PERSON_NOUNS: return True
    feats = _word_features(head)
    if not feats: return False
    last = feats[-1]
    if last[1] == '代名詞': return True
    if last[1] == '名詞' and last[2] == '固有名詞' and last[3] in ('人名', '組織名', '一般'): return True    # a bare person / company name
    if len(feats) >= 2:
        before = feats[-2]
        if before[1] in ('名詞', '代名詞') or (before[1] == '接尾辞' and before[0] in _PERSON_ROLE_SUFFIX_TOKENS | _PERSON_SUFFIX_TOKENS):
            if last[1] == '接尾辞' and last[0] in _PERSON_SUFFIX_TOKENS | _GROUP_SUFFIX_TOKENS | _PERSON_ROLE_SUFFIX_TOKENS:
                # Round 6: <family name>+家 is both "the people of that family" and "that family's house": not every sense names persons,
                # so it is no evidence (a common noun + 家, the name of a trade, is a person in every sense and stays).
                if not (last[0] in _HOUSE_SUFFIX_TOKENS and before[1] == '名詞' and before[2] == '固有名詞'): return True
            if last[1] == '名詞' and last[0] in ('軍', 'チーム', '客'): return True
        if last[0] == '会' and last[1] == '名詞' and before[1] in ('名詞', '接尾辞'):
            body = ''.join(f[0] for f in feats[:-1])
            if before[0] in _MEMBER_NOUNS or _is_person_phrase(body): return True
    return False


def _is_post_phrase(phrase):
    """A post / office (the thing a person is chosen AS): the head is a closed-class post noun, or <noun> + 長/係 as two tokens."""
    compact = phrase.replace(' ', '').replace('　', '')
    head = compact.split('の')[-1]
    if not head: return False
    if head in _POST_NOUNS: return True
    feats = _word_features(head)
    return len(feats) >= 2 and feats[-1][1] == '接尾辞' and feats[-1][0] in _POST_SUFFIX_TOKENS and feats[-2][1] == '名詞'


# Verbs whose に/へ argument is an addressee: the thing is handed over, told, asked, shown, reported to someone.
# The class is semantic (transfer of an object or of information), not a list of the words the tests use.
_TRANSFER_PREDICATES = frozenset((
    '渡す','送る','贈る','与える','あげる','やる','くれる','差し上げる','配る','届ける','返す','貸す','預ける','譲る','売る',
    '払う','支払う','納める','見せる','示す','伝える','教える','知らせる','告げる','言う','話す','語る','聞かせる','尋ねる',
    '頼む','勧める','薦める','答える','返す','与える','授ける','任せる','委ねる','申し出る','打ち明ける','謝る','挨拶する',
    '提出する','提供する','供給する','支給する','授与する','寄付する','寄贈する','献上する','配布する','配達する','発送する',
    '送付する','納品する','譲渡する','報告する','連絡する','通知する','説明する','相談する','質問する','依頼する','命令する',
    '紹介する','要求する','要請する','申請する','約束する','返事する','回答する','忠告する','警告する','感謝する','指示する',
    '伝達する','教授する','貸与する','付与する','交付する','通報する','推薦する','案内する',
    '申し込む','申し込む','問い合わせる','訴える','願い出る','届け出る','提案する','提言する','応募する','出願する','返信する','回答する'))
# Verbs of sharing out: …を弟に分ける gives a share to the person (an addressee), unlike the other verbs of change.
_SHARING_PREDICATES = frozenset(('分ける', '分割する', '分配する', '配分する'))
_COUNTED = re.compile(r'[0-9０-９〇一二三四五六七八九十百千万数]+[つ個組班人名種類グ]?の')


def _counted_phrase(value):
    """A phrase headed by a count (二つのグループ, 3組の…): categories made by a partition, not a person who receives."""
    return bool(_COUNTED.match(value.replace(' ', '').replace('　', '')))


def _result_type_evidence(phrase):
    """Positive evidence that a に-phrase names a RESULT TYPE (a form, a state, a category, a language, a colour, a time), judged from tokens
    and closed classes: a number + counter (四つの山, 三段落, 一冊), a head that is an adjectival noun, a noun + 語/形/版/式/型/風/色
    (英語版, 改訂版), a name that names only a colour, or a time phrase. A person word, a lexicon of persons or the ending characters of a
    word are not consulted: no evidence is "undecided", not "not a result"."""
    compact = phrase.replace(' ', '').replace('　', '')
    if not compact: return False
    if _counted_phrase(compact) or _is_time_phrase(compact): return True
    head = compact.split('の')[-1]
    if head in _COLOR_NAMES or head in _FORMAT_NOUNS or head in _LANGUAGE_NAMES: return True
    feats = _word_features(head)
    if not feats: return False
    if feats[-1][1] == '形状詞': return True
    if feats[-1][1] == '名詞' and feats[-1][3] == '助数詞可能': return True            # a noun usable as a counter (袋, 束, 組, 班): a unit things are divided into
    if feats[-1][1] == '名詞' and feats[-1][0] in _FORMAT_NOUNS: return True            # a compound headed by a format noun: 短い要約
    if len(feats) == 2 and feats[0][2] == '数詞' and feats[1][1] in ('接尾辞', '名詞'): return True      # a numeral + one counter / measure word: 一冊, 二つ, 三段落
    return len(feats) >= 2 and feats[-1][1] == '名詞' and feats[-1][0] in _RESULT_FORM_NOUNS and feats[-2][1] == '名詞'


def _result_ill_typed(predicate, phrase, object_person, passive):
    """None when a に-phrase may be the `result` of this verb of change; otherwise the typed reason it may not. One rule for the reader and
    the type gate. object_person: whether the thing the verb acts on (the を-object, or the subject of a passive) is a person; None when
    there is no such thing in the clause.
    Round 5 (M2): a person lexicon is never the ground for `result`. With a thing acted on (X を Y に V) the に-phrase is a result only on
    positive evidence of a result type (_result_type_evidence); with none it is undecided (result|beneficiary), whoever it names. Two cases
    need no evidence: the verb confers a status (an appointment; the object is a person by the verb's own selection) and a clause with NO
    thing acted on AND a verb that has no transitive use (X は Y になる: nothing is done for anybody, so Y can only be what X becomes).
    Round 6: a transitive verb whose object is merely left out (<person>が〜に言い換えた) is NOT such a clause: the に-phrase may be whoever
    the work is done for, so it is a result only on evidence of a result type (the object's absence is not evidence of intransitivity)."""
    compact = phrase.replace(' ', '').replace('　', '')
    if passive and predicate in _SELECTION_PREDICATES:
        return None if (_is_post_phrase(compact) and object_person is not False) else _SELECTION_RESULT_REASON
    if predicate in _APPOINTMENT_PREDICATES or predicate in _PRODUCT_PREDICATES: return None
    if _result_type_evidence(compact): return None
    if object_person is True: return None              # a verb of change applied TO a person (娘を〜に仕立てた): the に-phrase is the status the person is brought to
    if predicate in _PROCESSING_PREDICATES: return _RESULT_EVIDENCE_REASON
    if object_person is None and predicate in _INTRANSITIVE_CHANGE_PREDICATES: return None   # no thing acted on and the verb takes none (なる, 変わる): the に-phrase is what the subject becomes
    return _CHANGE_EVIDENCE_REASON


# Verbs whose に argument names the form/state/category the object ends up in (X を Y に変える). The に phrase is a
# result, not an addressee. Class: change of form, conversion between formats/languages, partition/collection,
# processing into a product, renaming/reclassifying.
_CHANGE_PREDICATES = frozenset((
    '変える','変わる','変換する','翻訳する','訳す','直す','分ける','分割する','まとめる','整理する','加工する','変更する',
    '改める','改造する','改名する','転換する','転用する','切り替える','置き換える','書き換える','作り変える','描き直す',
    '分類する','区分する','統合する','統一する','集約する','要約する','圧縮する','変化する','変質する','編集する','改訂する',
    '編成する','再編する','組み替える','言い換える','読み替える','縮小する','拡大する','単純化する','標準化する',
    # change of state/status (the に-phrase is the state or status that results): become, develop into, be promoted to
    'なる','成る','化す','発展する','昇進する','昇格する','降格する','成長する','進化する','変貌する','転じる','転ずる','移行する',
    # change of colour/appearance (髪を茶色に染めた, 壁を白に塗り替えた): the に-phrase is the result
    '染める','塗り替える','塗りかえる','塗り直す','仕立てる','仕上げる','改装する','模様替えする',
    # rescheduling / re-setting a value (大会を来月に延期した, 期限を3日に延長した): the に-phrase is the new value, not when it happened
    '延期する','延長する','短縮する','繰り上げる','繰り下げる','前倒しする','後ろ倒しする','先送りする','ずらす','早める','遅らせる',
    '振り替える','延ばす','繰り越す',
    # appointment / promotion / selection into a role or status (部下を課長に任命した, 彼を代表に選んだ): the role is the result
    '登用する','任命する','任用する','起用する','抜擢する','選任する','選出する','認定する','選ぶ','指名する'))
# Verbs that confer a post or status on a person (the object is always a person by the verb's own selection: 部下を課長に任命した,
# 候補を議長に選出した). Their に-phrase is the status it is given, even when the object is a person the tagger cannot recognise (候補).
_APPOINTMENT_PREDICATES = frozenset(('登用する','任命する','任用する','起用する','抜擢する','選任する','選出する','指名する','認定する',
                                     '昇進する','昇格する','降格する'))
# W1-a round 4 (N2): the verbs of _CHANGE_PREDICATES fall in three groups for a に-phrase after the object (X を Y に V):
#   (a) conversion verbs (変える, 翻訳する, 分類する, なる, 加工する, ...): the verb itself selects the result; a beneficiary に is rare. Their
#       に-phrase is the `result` unless it is a person and the object is a thing (then it could be whoever the work is done for).
#   (b) _PROCESSING_PREDICATES: verbs of making / mending / finishing / editing / dyeing / selecting. Their に-phrase is as often the person
#       the work is done FOR (妹にセーターを仕上げた) as the form it ends in. It is a `result` ONLY with positive evidence of a result type
#       (_result_type_evidence); with none it stays ambiguous (result|beneficiary), whoever or whatever it names, and a person lexicon is
#       not consulted. Words on the boundary are placed in (b), the safe side (they only lose readings, never gain a wrong one).
#   (c) _APPOINTMENT_PREDICATES keep their treatment: the に-phrase is the status given to the (person) object.
_PROCESSING_PREDICATES = frozenset(('直す','仕立てる','仕上げる','整理する','まとめる','編集する','改訂する','染める','塗り替える','塗りかえる',
                                    '塗り直す','改装する','模様替えする','描き直す','選ぶ','作り変える','改造する'))
# Verbs of change that have NO transitive use (the subject itself changes: 彼は医者になった, 信号が赤に変わった, 水が氷に変化した). Only these
# may take a に-phrase as the result with no evidence of a result type when the clause has no object. The class is closed and decided by the
# verbs' own grammar, not by frames.transitivity (which marks 化す and 発展する transitive): a verb that is transitive or either way (言い換える,
# 訳す, 変える, 縮小する) with its object left out is undecided like any other.
_INTRANSITIVE_CHANGE_PREDICATES = frozenset(('なる','成る','変わる','化す','変化する','変質する','成長する','発展する','進化する','変貌する','転じる','転ずる','移行する'))
# Verbs that name making a MATERIAL into a PRODUCT (加工する): what it is made into is the に-phrase; the verb takes no person it is done for, so it
# needs no evidence of a result type. (A shared test fixes 丸太を角材に加工した -> result; 角材 is a single token with no evidence of its own.)
_PRODUCT_PREDICATES = frozenset(('加工する',))
# Verbs of selection / appointment. In the passive (X が Y に選ばれた) the に-phrase is "by Y" or "as Y": both readings exist, so it is the
# result only when Y is a post (the thing one is chosen as) and is never taken as the agent; otherwise it is undecided.
_SELECTION_PREDICATES = (_APPOINTMENT_PREDICATES - frozenset(('昇進する','昇格する','降格する'))) | frozenset(('選ぶ',))
_SELECTION_AGENT_REASON = 'ill-typed role: the に-phrase of a passive verb of selection is by/as undecided, not an agent'
_SELECTION_RESULT_REASON = 'ill-typed role: the に-phrase of a passive verb of selection is a result only when it names a post'
_RESULT_EVIDENCE_REASON = 'ill-typed role: result of a verb of making without evidence of a result type'
_CHANGE_EVIDENCE_REASON = 'ill-typed role: result of a verb of conversion on a thing without evidence of a result type'
# Names that name only a colour (the position of a result of dyeing / painting). 色 itself ends 茶色, 金色 (one token), so the class is a list.
_COLOR_BASES = ('赤','青','黄','緑','白','黒','紫','茶','灰','橙','紺','藍','朱','紅','桃','金','銀','水','空','肌','黄緑','薄緑','群青')
_COLOR_NAMES = frozenset([c for c in _COLOR_BASES if c not in ('水','空','肌','金','銀')] + [c + '色' for c in _COLOR_BASES]
                         + ['ピンク','オレンジ','グレー','ブラウン','ブルー','グリーン','レッド','ホワイト','ブラック','イエロー','パープル','ベージュ'])
# Nouns that name only a FORMAT or DIGEST of content (what a document is arranged into): 図表, 要点, 一覧. Inanimate in every sense, so
# they can never be the person a piece of work is done for; naming the form the object ends up in, they are evidence of a result type.
_FORMAT_NOUNS = frozenset(('図','表','図表','一覧','要点','概要','要約','目次','リスト','箇条書き','グラフ','年表'))
# Names that name only a language, a language variety or a script (every sense): a form a text is put into (英語に訳す). 英語 is ONE token, so the
# <noun>+語 rule below does not see it; a language name of a country + 語 (two tokens) is seen by that rule.
_LANGUAGE_NAMES = frozenset(('英語','仏語','独語','露語','言語','方言','敬語','平仮名','ひらがな','カタカナ','漢字'))
# Nouns that name a spot or a geographic feature and can never act (so a から-phrase of a passive naming one is an origin, not a giver). A
# closed class of nouns every sense of which is a place that is not a body of people: NOT 学校/会社/局 or a country, which also name bodies that act.
_SPOT_NOUNS = frozenset(('駅','公園','部屋','庭','海','山','川','湖','島','畑','森','谷','海岸','教室','倉庫','台所','玄関','屋上'))
def _is_origin_spot(phrase):
    """Evidence that a から-phrase of a passive names where something comes from rather than who gave it: its head is one of _SPOT_NOUNS or a
    named place (the tagger's 固有名詞/地名; the shared tests fix 九州から運ばれた, 北海道から送られた as source)."""
    compact = phrase.replace(' ', '').replace('　', '')
    head = compact.split('の')[-1]
    if head in _SPOT_NOUNS: return True
    feats = _word_features(head)
    return bool(feats) and feats[-1][1] == '名詞' and feats[-1][2] == '固有名詞' and feats[-1][3] == '地名'


_RESULT_FORM_NOUNS = frozenset(('語','形','版','式','型','風','色'))      # <noun>+語/形/版/式/型/風: 英語版, 改訂版, 浴衣風
# Verbs whose passive agent is the thing that holds/encloses the subject (surrounded by mountains, included in a park): a place-typed
# agent of these is a real (inanimate) agent. For every other verb a place-typed passive に-phrase says where it happened
# (a shop was placed in front of a station) and is not an agent.
_CONTAINMENT_PREDICATES = frozenset(('囲む','含む','覆う','包む','挟む','抱く','満たす','占める','隔てる','区切る','限る','閉ざす','取り巻く','取り囲む'))
# A に-phrase ending in one of these is a purpose/manner/time clause marker (…のために, …ように, …ほうに), not a result noun.
_RELATIONAL_TAILS = ('ため', 'よう', 'ほう', '方', 'とき', '時', '際', '間', 'うち', 'もの', 'こと', 'わけ', 'はず')
_NO_PARTICIPANT_REASON = 'event without participant or content word'
_COORD_REASON = 'coordinated clause is not assertable alone'
_CONTENT_WORDS = ('名詞', '代名詞', '形容詞', '形状詞', '副詞', '接頭辞', '接尾辞', '数詞')
# Verbs that put/move an object to a destination (封筒を青棚に置く). The project reads that に-phrase as `recipient`
# (end point -> recipient, as for motion verbs); the reading is kept, not extended: a destination verb is a closed class
# (placement, attachment, storage, transport), unlike an unlisted verb whose に-phrase could be a result.
_PLACEMENT_PREDICATES = frozenset((
    '置く','入れる','載せる','乗せる','積む','掛ける','吊るす','貼る','付ける','立てる','並べる','差す','挿す','刺す','埋める',
    '植える','仕舞う','収める','収納する','配置する','設置する','保管する','運ぶ','移す','持つ','持っていく','持ってくる','しまう',
    '詰める','注ぐ','漬ける','浸す','飾る','敷く','留める','結ぶ','繋ぐ','つなぐ','接続する','投げる','落とす',
    '置いてくる','置いていく','入れてくる','入れていく'))
# round 5: more verbs of going, so the end-point rule (a place is shown, or the phrase is not an end point) covers them as well
_GOAL_PREDICATES = _GOAL_PREDICATES | frozenset(('出かける','通う','引っ越す','到着する','帰宅する','出勤する','出張する','出発する','旅立つ','上陸する'))
_MOTION_CLASS = _GOAL_PREDICATES | _LOCATION_PREDICATES | _PLACEMENT_PREDICATES
_CAUSATIVE_REASON = 'causative frame: causer/causee unresolved'
_TIME_ROLE_REASON = 'ill-typed role: time phrase as event participant'
_TIME_FUSED_REASON = 'ill-typed role: time phrase fused with participant'
_CASE_SPAN_REASON = 'ill-typed role: phrase spans a case particle'
_TOKEN_SPAN_REASON = 'ill-typed role: span cuts a token'
_NONAGENT_REASON = 'ill-typed role: a phrase that cannot act (not a person/organisation) as agent'
_NOT_ADDRESSEE_REASON = 'ill-typed role: recipient is not an addressee'
_REPEATS_PREDICATE_REASON = 'ill-typed role: participant repeats the predicate itself'
_TIME_ADJUNCT_REASON = 'ill-typed role: time phrase as place/goal/direction/result'
_TIME_ADJUNCT_ROLES = frozenset(('goal', 'location', 'direction', 'place'))
_RESULT_ORDER_REASON = 'ill-typed role: a に-phrase before the object of a verb of change is not its result'
_SOURCE_AGENT_REASON = 'ill-typed role: the から-phrase of a passive is the agent or the origin, and nothing shows it is a spot'
_ENDPOINT_REASON = 'ill-typed role: end point of motion without place evidence'
_TIME_OF_CHANGE_REASON = 'ill-typed role: time phrase of a verb of change is its new value, not when it happened'
_TOPIC_PATIENT_REASON = 'ill-typed role: a は-topic as the patient of an intransitive verb'
_EVENT_PARTICIPANTS = frozenset(('agent', 'patient', 'recipient', 'causer', 'causee'))
_NOMINAL_ROLES = frozenset(('agent', 'patient', 'recipient', 'causer', 'causee', 'entity', 'attribute', 'standard',
                            'context', 'result'))


def _span(source, raw, start=0, end=None):
    end = len(raw) if end is None else end
    return Span(source, start, end, raw[start:end])


def _tokens(text):
    out = []; cursor = 0
    for word in _tagger()(text):
        at = text.find(word.surface, cursor)
        out.append((word, at, at + len(word.surface))); cursor = at + len(word.surface)
    return out


def _uncovered_nominals(tokens, covered):
    """Content omitted by a Frame must remain an explicit unread requirement."""
    for word, start, end in tokens:
        if word.feature.pos1 in ('名詞', '代名詞', '形容詞', '形状詞', '副詞', '接頭辞', '接尾辞'):
            if not any(left <= start and end <= right for left, right in covered):
                return True
    return False


def _predicate_coverage(tokens, ev, predicate):
    spans = [tokens[ev][1:]]
    # サ変 nouns belong to the parsed predicate, not to an omitted argument.
    if ev and _base(tokens[ev][0]) == 'する':
        noun = tokens[ev-1][0]
        if noun.feature.pos1 == '名詞' and _base(noun)+'する' == predicate:
            spans.append(tokens[ev-1][1:])
    return spans


def _event_time(words, predicate_index):
    # The candidate Frame stops at a compound verb's first independent verb.
    # Read the single clause's grammatical auxiliaries, including the compound
    # tail (e.g. 受け/取っ/た), instead of dropping its past tense.
    return 'past' if any(is_past_aux(w)
                         for w in words[predicate_index + 1:]) else 'nonpast'


_PREDICATE_VALUE_REASON = 'copula value is a predicate phrase'
_DEGREE_MARKS = frozenset(('ほど', 'くらい', 'ぐらい', '並み'))
_VALUE_CASE_PARTICLES = frozenset(('より', 'が', 'を', 'に', 'で', 'へ', 'から', 'まで', 'と'))


class _Split:
    """A regex-match-like record of where a copula sentence splits: lhs は/が value."""
    def __init__(self, text, lhs_end, value_start, value_token):
        tail = re.fullmatch(r'(.*?)[。！？?]*\s*', text[value_start:], re.S)
        self._parts = {1: text[:lhs_end], 2: tail[1].lstrip() if tail else text[value_start:]}
        self._starts = {1: 0, 2: value_start + (len(tail[1]) - len(tail[1].lstrip()) if tail else 0)}
        self.value_token = value_token

    def start(self, group): return self._starts[group]
    def __getitem__(self, group): return self._parts[group]


_OPEN_BRACKETS = ('（', '(', '〈', '［', '[', '【', '「', '『', '《')
_CLOSE_BRACKETS = ('）', ')', '〉', '］', ']', '】', '」', '』', '》')


def _bracket_depths(text):
    """depth[i] = how many brackets are open before character i (character scan: the tagger glues '-）' or ']' to its
    neighbours, so a token-surface test would lose the closing bracket)."""
    depth = 0; out = []
    for ch in text:
        out.append(depth)
        if ch in _OPEN_BRACKETS: depth += 1
        elif ch in _CLOSE_BRACKETS: depth = max(0, depth - 1)
    out.append(depth)
    return out
_DANGLING = frozenset(('で', 'に', 'から', 'へ', 'まで', 'より', 'を'))


def _copula_split(text, tokens):
    """Split `lhs は/が value` at the first は/が PARTICLE TOKEN outside any bracket. A か-letter inside a word (a thanks formula) or
    inside a parenthetical reading (a kana reading of a name) is not the topic particle: the old character scan cut those apart."""
    depths = _bracket_depths(text)
    for index, (word, start, end) in enumerate(tokens):
        if depths[start] == 0 and word.feature.pos1 == '助詞' and word.surface in ('は', 'が'):
            lhs_end = start
            if index and tokens[index - 1][0].feature.pos1 == '助詞' and tokens[index - 1][2] == start:
                before = tokens[index - 1]
                # X とは Y (a definition): the と belongs to the topic marker, not to the entity. A case particle right
                # before は (では, には, からは) leaves a phrase with a dangling particle: not a copula sentence.
                if before[0].surface == 'と' and word.surface == 'は': lhs_end = before[1]
                elif before[0].surface in _DANGLING: return None
            if lhs_end == 0 or not text[:lhs_end].strip(): return None
            m = _Split(text, lhs_end, end, index + 1)
            return m if m[2] else None
    return None


def _predicate_phrase_value(tokens, first_value_token, value_end, depths=None, has_copula=True):
    """The right-hand side of は/が is a predicate phrase, not a noun: its last content word is an adjective/adjectival
    noun/verb and it contains a case particle (古い橋より長い, 猫が好き). Reading that as `A is B` mislabels a comparison or
    a double-subject predicate as an identity; it is returned unsupported (the comparison rule can then read it).
    A parenthetical reading/gloss (depth > 0) is not part of the value's own grammar, and a trailing copula (…であった, …で
    あり) is not its predicate: neither decides."""
    value = [t for t in tokens[first_value_token:] if t[1] < value_end and (depths is None or depths[t[1]] == 0)]
    # Round 5 (M9): a value written with NO copula that ENDS in a chain of verbal auxiliaries (れ / られ / せ / た / ない ...) after a verb, an adjective or a
    # verbalising suffix (…がら + れ + た) is a verb the tagger split into pieces, not a noun: 'A が B られた' is no identity of A and B. A value that
    # holds an auxiliary INSIDE a noun phrase (…である魔法使いの名称: a relative clause) or ends in the copula であった is not touched.
    if not has_copula:
        body = [w for w, _, _ in value if w.feature.pos1 not in ('補助記号', '記号')]
        n = len(body)
        while n and body[n - 1].feature.pos1 == '助動詞': n -= 1
        if 0 < n < len(body):
            head = body[n - 1]
            copular_ari = head.feature.pos1 == '動詞' and _base(head) == 'ある' and n >= 2 and body[n - 2].surface == 'で'
            if not copular_ari and (head.feature.pos1 in ('動詞', '形容詞') or (head.feature.pos1 == '接尾辞' and head.feature.pos2 == '動詞的')): return True
    # a comparison inside the value. より is a particle after a noun (駅より) but the tagger calls it an adverb after の (前のより軽い,
    # 君のより重い: 'than the previous one'); an adverb より that opens the value (より安全だ: 'more') is not a comparison standard.
    for k, (w, _, _) in enumerate(value):
        if w.surface != 'より': continue
        if w.feature.pos1 == '助詞': return True
        if k > 0 and (value[k - 1][0].feature.pos1 in ('名詞', '代名詞', '数', '接尾辞')
                      or (value[k - 1][0].feature.pos1 == '助詞' and value[k - 1][0].surface == 'の')): return True
    # Round 4 (N4): ほど / くらい / ぐらい / 並み after a noun, pronoun, number or a nominalising の is a degree comparison (昔ほど…, 君のほど…,
    # 海くらい…): the value is a predicate phrase whatever tag the word gets, exactly as より is.
    for k, (w, _, _) in enumerate(value):
        if w.surface in _DEGREE_MARKS and k > 0 and (value[k - 1][0].feature.pos1 in ('名詞', '代名詞', '数', '接尾辞')
                                                     or (value[k - 1][0].feature.pos1 == '助詞' and value[k - 1][0].surface == 'の')):
            return True
    while value and (value[-1][0].feature.pos1 in ('助動詞', '補助記号', '記号')
                     or (value[-1][0].feature.pos1 == '動詞' and _base(value[-1][0]) == 'ある' and len(value) > 1
                         and value[-2][0].surface == 'で')
                     or (value[-1][0].feature.pos1 == '助詞' and value[-1][0].surface == 'で')):
        value.pop()                                                 # …であった / …であり / …で: the copula, not a predicate of the value
    content = [w for w, _, _ in value if w.feature.pos1 not in ('助詞', '助動詞', '補助記号', '記号')]
    if not content or content[-1].feature.pos1 not in ('形容詞', '形状詞', '動詞'): return False
    return any(w.feature.pos1 == '助詞' and w.surface in _VALUE_CASE_PARTICLES for w, _, _ in value)


def _split_attribute(text, tokens, lhs_end):
    """`entity の attribute` splits at the last の PARTICLE token of the left side (連体詞 この/その/あの contain a の
    character but no particle: an adnominal demonstrative is one entity with its noun, not a one-letter piece + the noun)."""
    last = None; depths = _bracket_depths(text)
    for word, start, end in tokens:
        if end > lhs_end: break
        # a の inside a parenthetical (a name followed by its reading) is part of the gloss, not the entity の attribute
        if depths[start] == 0 and word.feature.pos1 == '助詞' and word.surface == 'の' and 0 < start: last = (start, end)
    if last is None: return text[:lhs_end], ''
    entity, attr = text[:last[0]], text[last[1]:lhs_end]
    return (entity, attr) if entity.strip() and attr.strip() else (text[:lhs_end], '')


def _case_phrase(text, tokens, particle_index, lower=0):
    """Return the source-bounded nominal phrase immediately before a case particle."""
    j = particle_index - 1
    while j >= 0 and tokens[j][2] > lower:
        word = tokens[j][0]
        pos = word.feature.pos1
        if pos in ('名詞','代名詞','形容詞','形状詞','接頭辞','接尾辞','数'):
            j -= 1; continue
        if pos == '助詞' and word.surface == 'の':
            j -= 1; continue
        break
    first = j + 1
    if first >= particle_index: return None
    start, end = tokens[first][1], tokens[particle_index - 1][2]
    phrase = text[start:end]
    return start, end, phrase


def _case_role(particle, phrase, predicate, *, quoted=False, person=False, after_object=None, object_person=None, passive=False):
    """Map only morphologically or syntactically resolved cases; label the rest.

    after_object: for a document clause, whether this phrase stands after the clause's を-object (None: not a clause read, as
    in a question). With a verb of change or rescheduling the time に-phrase after the object is the new value (予定を月曜日に
    変えた: result); before the object it could as well be when it happened -> ambiguous (unsupported), never `time`.
    passive: the verb is followed by れる/られる. The に-phrase of a passive verb of selection is by/as undecided (see _result_ill_typed)."""
    compact = phrase.replace(' ', '').replace('　', '')
    if particle == 'に':
        if (_TIME_NOMINAL.fullmatch(compact) or _is_time_phrase(compact)):
            if after_object is not None and predicate in _CHANGE_PREDICATES:
                return ('result', 'case') if after_object else ('ambiguous', 'case:に:time|result')
            return 'time', 'case'
        if passive and predicate in _SELECTION_PREDICATES and not _is_place_phrase(compact):
            return ('result', 'case') if _result_ill_typed(predicate, compact, object_person, True) is None else ('ambiguous', 'case:に:agent|result')
        if predicate in _CHANGE_PREDICATES and not _is_place_phrase(compact) and not compact.endswith(_RELATIONAL_TAILS):
            # Word order is evidence that needs no lexicon: a result follows its object (AをBに変える); a に-phrase that comes BEFORE the
            # object (BにAを直す) is whoever the work is done for, or the place/target: not decided here (ambiguous -> unsupported).
            if after_object is False: return 'ambiguous', 'case:に:result|beneficiary'
            # Round 4: whether the phrase is a result is decided by _result_ill_typed: a verb of making needs positive evidence of a result
            # type; a conversion verb takes it unless it is a person and the object is a thing; an appointment keeps its status reading.
            if _result_ill_typed(predicate, compact, object_person, False) is not None: return 'ambiguous', 'case:に:result|beneficiary'
            return 'result', 'case'
        # Round 5 (M5): the end point of a verb of motion is a `goal` only when the phrase shows it is a place; a phrase with no such evidence
        # (…しに行く: a purpose of going) is undecided, not a goal.
        if predicate in _GOAL_PREDICATES: return ('goal', 'case') if _is_end_point(compact) else ('ambiguous', 'case:に:goal|purpose|addressee')
        if predicate in _LOCATION_PREDICATES: return 'location', 'case'
        return 'ambiguous', 'case:に:location|goal|time'
    if particle == 'で':
        head = compact.split('の')[-1]
        if compact == '同日付': return 'time', 'case'
        if _is_place_phrase(compact):
            return 'place', 'case'
        if head in _MEANS_NOMINALS or head.endswith('語'):
            return 'means', 'case'
        return 'ambiguous', 'case:で:place|means'
    if particle == 'と':
        if quoted: return 'quotation', 'case'
        if person: return 'companion', 'case'
        return 'ambiguous', 'case:と:companion|quotation'
    if particle == 'から':
        if _TIME_NOMINAL.fullmatch(compact) or _is_time_phrase(compact): return 'ambiguous', 'case:から:source|time-range'
        # Round 5 (M3): the から-phrase of a PASSIVE is the agent (the giver) or the origin. Convention 4.6 makes it the agent; it is the
        # origin only when the phrase names a spot that cannot act (_SPOT_NOUNS). Anything else is undecided, never `source`.
        if passive and not _is_origin_spot(compact): return 'ambiguous', 'case:から:agent|source'
        return 'source', 'case'
    if particle == 'まで': return 'limit', 'case'
    if particle == 'へ':
        if predicate in _GOAL_PREDICATES and not _is_end_point(compact): return 'ambiguous', 'case:へ:direction|purpose|addressee'
        return 'direction', 'case'
    return None, 'case'


def _case_roles(text, tokens, predicate_index, lower=0, existing=(), offset=0, predicate=None, document=False):
    """Read case adjuncts attached before this predicate and preserve ambiguity."""
    predicate = predicate or (_base(tokens[predicate_index][0]) if predicate_index < len(tokens) else '')
    roles = []; issues = []
    existing_spans = set(); existing_terms = set()
    for item in existing:
        if hasattr(item, 'span'):
            existing_spans.add((item.span.start-offset, item.span.end-offset))
            existing_terms.add(str(item.term))
        elif isinstance(item, tuple) and len(item) == 2:
            existing_terms.add(str(item[1]))
    compound_spans = []
    for ti, (word, start, end) in enumerate(tokens):
        if start < lower or ti >= predicate_index: continue
        if any(left < start < right for left, right in compound_spans): continue
        compound = None
        for surface, role_name in _COMPOUND_PARTICLES:
            cursor = start; pieces = []
            for part, part_start, part_end in tokens[ti:predicate_index]:
                if part_start != cursor: break
                pieces.append(part.surface); cursor = part_end
                joined = ''.join(pieces)
                if joined == surface:
                    compound = (surface, role_name, cursor); break
                if not surface.startswith(joined): break
            if compound: break
        if compound:
            surface, role_name, compound_end = compound
            compound_spans.append((start, compound_end))
            located = _case_phrase(text, tokens, ti, lower)
            if located is None: continue
            pstart, pend, phrase = located
            if (pstart, pend) in existing_spans or phrase in existing_terms or _WH.search(phrase): continue
            span = (pstart, pend)
            if span in existing_spans: continue
            roles.append((role_name, phrase, span, 'case'))
            continue
        if (word.feature.pos1 != '助詞' or word.feature.pos2 != '格助詞'
                or word.surface not in ('に','で','と','から','まで','へ')):
            continue
        located = _case_phrase(text, tokens, ti, lower)
        if located is None: continue
        pstart, pend, phrase = located
        # A frame's recipient is already a better typed reading of this に phrase.
        if (pstart, pend) in existing_spans or phrase in existing_terms: continue
        # Wh-bearing phrases are variables in requests, not asserted case adjuncts.
        if _WH.search(phrase): continue
        quoted = word.surface == 'と' and text[:start].rstrip().endswith('」')
        if quoted:
            close = text.rfind('」', 0, start)
            opening = text.rfind('「', 0, close)
            if opening >= 0:
                pstart, pend = opening + 1, close
                phrase = text[pstart:pend]
        person = False
        if word.surface == 'と':
            prior = tokens[ti - 1][0] if ti else None
            person = bool(prior and (prior.feature.pos3 == '人名' or phrase.endswith('さん') or phrase.endswith('氏')))
        after_object = None; object_person = None
        passive_clause = predicate_index + 1 < len(tokens) and _base(tokens[predicate_index + 1][0]) in ('れる', 'られる')
        if document:
            # only a clause with an を-marked object has the 'AをBに' pattern; position relative to it decides result/ambiguous
            ends = [item.span.end - offset for item in existing if getattr(item, 'name', None) == 'patient'
                    and _particle_after(tokens, item.span.end - offset) == 'を']
            if ends: after_object = any(e <= pstart for e in ends)
            # the thing the verb acts on: the を-object, or for a passive its subject (彼が部長に選ばれた: he is given the status)
            marks = ('を',) if not passive_clause else ('が', 'は')
            objects = [item.span.text for item in existing if getattr(item, 'name', None) == 'patient'
                       and _particle_after(tokens, item.span.end - offset) in marks]
            if objects: object_person = any(_is_person_phrase(t) for t in objects)
        role, kind = _case_role(word.surface, phrase, predicate, quoted=quoted, person=person, after_object=after_object,
                                object_person=object_person, passive=passive_clause)
        if role is None: continue
        span = (pstart, pend)
        if span in existing_spans: continue
        roles.append((role, phrase, span, kind))
        if role == 'ambiguous': issues.append('ambiguous case role: '+word.surface)
    return roles, issues


def _compound_token_indices(tokens):
    """Indices inside an exact closed particle sequence, including tokenized し."""
    indices = set()
    surfaces = sorted((surface for surface, _ in _COMPOUND_PARTICLES), key=len, reverse=True)
    for first, (_, start, _) in enumerate(tokens):
        for surface in surfaces:
            cursor = start; joined = ''; covered = []
            for index in range(first, len(tokens)):
                word, at, end = tokens[index]
                if at != cursor: break
                joined += word.surface; cursor = end; covered.append(index)
                if joined == surface:
                    indices.update(covered); break
                if not surface.startswith(joined): break
            if any(index in indices for index in covered): break
    return indices


def _time_adverbial(text, tokens, predicate_index, lower=0, existing=(), offset=0):
    """Recognize one exact, sentence-initial numeric time adverbial before a comma."""
    if lower or predicate_index <= 0 or any(getattr(item, 'name', None) == 'time' for item in existing):
        return None
    match = _TIME_ADVERBIAL.match(text)
    if not match: return _time_word_adverbial(text, tokens)
    start, end = match.span(1); cursor = start; pieces = []
    for word, at, right in tokens:
        if right <= start: continue
        if at != cursor or right > end: return None
        pieces.append(word.surface); cursor = right
        if cursor == end: break
    if cursor != end or ''.join(pieces) != match[1]: return None
    return ('time', match[1], (start, end), 'adverbial')


def _time_word_adverbial(text, tokens):
    """A sentence-initial time noun before the first comma, read as the clause's time."""
    for index, (word, start, end) in enumerate(tokens):
        if word.surface in ('、', ',') and word.feature.pos1 == '補助記号':
            if index == 0: return None
            first = tokens[0][1]; last = tokens[index - 1][2]
            phrase = text[first:last]
            if text[:first].strip() or any(tokens[i][2] != tokens[i + 1][1] for i in range(index - 1)): return None
            if _is_time_phrase(phrase): return ('time', phrase, (first, last), 'adverbial')
            return None
    return None


def _particle_after(tokens, end):
    """The particle token that follows a phrase ending at `end` ('によって' is reported as one unit)."""
    for index, (word, start, right) in enumerate(tokens):
        if start == end:
            if word.surface == 'に' and index + 1 < len(tokens) and _base(tokens[index + 1][0]) == 'よる': return 'によって'
            if word.feature.pos1 == '助詞':
                tail = ''.join(t[0].surface for t in tokens[index:index + 4])
                if any(tail.startswith(c) for c, _ in _COMPOUND_PARTICLES if c.startswith(word.surface) and len(c) > len(word.surface)):
                    return next(c for c, _ in _COMPOUND_PARTICLES if tail.startswith(c))     # について, において, に対して ...
                return word.surface
            return ''
        if start > end: break
    return ''


_BENEFACTIVE_VERBS = frozenset(('あげる', 'やる', 'くれる', '差し上げる', 'もらう', '貰う', 'いただく', '頂く', 'くださる'))


def _benefactive_after(tokens, predicate_index):
    """V-て + あげる/くれる/もらう…: the に-phrase names who benefits or who gets the favour, i.e. an addressee."""
    for k in range(predicate_index + 1, len(tokens) - 1):
        if tokens[k][0].surface in ('て', 'で') and _base(tokens[k + 1][0]) in _BENEFACTIVE_VERBS: return True
    return False


def _object_marked(frame, text, tokens, chunk_start, predicate_start):
    """The clause has an を-marked object. (A は-topic that the frame reader parked in `patient` is not an object.)"""
    if not frame.patient: return False
    at = text.rfind(frame.patient, chunk_start, predicate_start)
    return at >= 0 and _particle_after(tokens, at + len(frame.patient)) in ('を', 'が')


def _recipient_claim(predicate, value, has_object, benefactive, particle='に'):
    """May a に-marked phrase be the recipient of this predicate? 'keep' or 'drop'. One rule for every rule's clauses
    (the frame branch and the type gate share it): a verb of transfer/telling or a benefactive is addressed to the phrase; a
    person is an addressee; a motion/placement/location verb's end point is read as `recipient` (project convention:
    終点 -> recipient, fixed by test_reader_case_roles_are_preserved) and is kept; for any other verb with an を-object
    the に-phrase is a result/place/state, not an addressee, and is not claimed."""
    if predicate in _TRANSFER_PREDICATES or benefactive: return 'keep'
    # Round 4 (J1-17): the end point of a MOTION verb (行く, 移る, 向かう ...) is read as `recipient` (the project convention) ONLY when the
    # phrase shows it is a place (_is_place_phrase) or an addressee (_is_person_phrase). A phrase with neither is not claimed here: it is
    # re-read as the `direction` (へ) / `goal` (に) it is, instead of being typed as somebody who receives. Placement and location verbs
    # (置く, 住む ...) keep their reading: existing tests fix 封筒を青棚に置く -> recipient (see docs H33).
    if predicate in _GOAL_PREDICATES:
        return 'keep' if (_is_place_phrase(value) or _is_person_phrase(value)) else 'drop'
    if predicate in _LOCATION_PREDICATES or predicate in _PLACEMENT_PREDICATES: return 'keep'
    if particle != 'に': return 'keep'                    # へ with any other verb: only the motion rule above applies (nothing else was ever checked for へ)
    person = _is_person_phrase(value) and not _is_place_phrase(value)
    if predicate in _CHANGE_PREDICATES:
        # …を弟に分ける shares with a person; …を二つに分ける makes two (and …を課長に昇進させる / …を二つのグループに分ける name the
        # new status / the categories). Only a verb of sharing out has an addressee, and then only a person who is not a counted
        # group; for every other verb of change the に-phrase is the result.
        return 'keep' if (predicate in _SHARING_PREDICATES and person and not _counted_phrase(value)) else 'drop'
    if person: return 'keep'
    # AをBにV with a non-person B and a verb outside every class above: B may be a result, a place or a person's name
    # nobody tagged. Not claimed as the recipient. A に-complement of a verb with no を-object (九州に集中する) keeps its
    # recorded reading: the gate is only for the ditransitive pattern.
    return 'drop' if has_object else 'keep'


def _can_be_passive_agent(value, predicate, subject, has_object=False):
    """A passive's に-phrase is the agent only when it can act (a person or organisation noun that is not also a place: 学校 and
    会社 are both) or encloses (囲まれる); and, for a verb of transfer, only when the subject is itself a person (弟が兄に教えられた:
    the elder brother taught; 書類が社長に渡された / 警察に通報された: it went TO the president/police, who is its recipient, not its agent;
    but with an を-object, 医師に検査の結果を説明された, the に-phrase is the agent of an indirect passive)."""
    if predicate in _CONTAINMENT_PREDICATES: return True
    if not _is_person_phrase(value) or _is_place_phrase(value): return False
    if predicate in _TRANSFER_PREDICATES and not has_object and (subject is None or not _is_person_phrase(subject)):
        return False                                    # 警察に通報された: to the police. (With an を-object -- 医師に検査の結果を説明された -- the に-phrase is the agent.)
    return True


def _is_origin_not_agent(value):
    """A passive's から-phrase is the giver/sender only when it is shown to be a person or organisation that can act (友人から届けられた,
    役所から通知された, by _is_person_phrase). Anything else (産地から伝えられた, 尺度から割り出された) or a time (来月から導入された) is the
    origin/start: the phrase is not claimed as the agent (round 4: no positive evidence of a person, no agent)."""
    return _is_time_phrase(value) or value.replace(' ', '').replace('　', '').split('の')[-1] in _SPOT_NOUNS or not _is_person_phrase(value)


def _role_claim(role, value, tokens, at, predicate_index, predicate, has_patient=True, subject=None):
    """Decide whether a frame's phrase may be claimed as this participant role.

    'keep'  - the phrase is a participant of this type.
    'time'  - a time phrase marked に/は: it is a time adjunct, never an agent/patient/recipient.
    'drop'  - a recipient/agent marked に/へ whose type is wrong (not an addressee; or a non-person as a passive agent):
              not claimed; _case_roles re-reads the phrase as goal/location/result/direction or leaves it ambiguous.
    'fused' - a time word glued to a participant noun (no particle between them): keep the role, clause not asserted.
    """
    follow = _particle_after(tokens, at + len(value))
    if follow in ('に', 'は') and _is_time_phrase(value): return 'time'
    if _time_fused(value): return 'fused'
    nxt = tokens[predicate_index + 1][0] if predicate_index + 1 < len(tokens) else None
    passive = nxt is not None and _base(nxt) in ('れる', 'られる')
    # A passive's に-phrase is an agent only when it can act: a person, a role/organisation noun, or the thing that
    # encloses (囲まれる). Anything else (a flower bed, a roof, a shelf) is where it happened, or unknown: never an agent.
    if role == 'agent' and passive and follow == 'に' and not _can_be_passive_agent(value, predicate, subject, has_patient): return 'drop'
    if role == 'agent' and passive and follow == 'に' and predicate in _SELECTION_PREDICATES: return 'drop'      # by/as undecided (N3)
    if role == 'agent' and passive and follow == 'から' and _is_origin_not_agent(value): return 'drop'
    # The frame reader parks a は-topic in a free `patient` slot (実は、弟が駅で友人に会った → patient=実). An object slot belongs to a
    # transitive verb: the topic of an intransitive one (会う, 着く, 住む) is not its patient (a passive subject is: 雨に降られた).
    if role == 'patient' and follow == 'は' and not passive and _transitivity(predicate) == 'intrans': return 'drop'
    if role == 'recipient' and follow in ('に', 'へ'):
        return _recipient_claim(predicate, value, has_patient, _benefactive_after(tokens, predicate_index), follow)
    return 'keep'


def _time_topic(text, tokens, predicate_index, lower, taken):
    """A time noun marked は is the clause's time, not a participant."""
    for ti, (word, start, end) in enumerate(tokens):
        if start < lower or ti >= predicate_index: continue
        if word.feature.pos1 == '助詞' and word.surface == 'は':
            located = _case_phrase(text, tokens, ti, lower)
            if located is None: continue
            pstart, pend, phrase = located
            if _is_time_phrase(phrase) and not any(a <= pstart and pend <= b for a, b in taken):
                return ('time', phrase, (pstart, pend), 'topic')
    return None


def _unresolved_complex(text, roles, offset):
    """Keep scope markers ambiguous unless an exact date is already role-bound."""
    found = False
    for match in _COMPLEX.finditer(text):
        found = True
        if not re.fullmatch(r'[0-9]+[年月日時]', match[0]): return True
        before = text[max(0, match.start() - 24):match.start()]
        after = text[match.end():match.end() + 12]
        if re.search(r'[0-9０-９]+(?:年|月|日)?\s*[-‐‑‒–—〜～]\s*$', before): return True
        if re.match(r'(?:以上|以下|前後|ごろ|頃|から|まで|にかけ|にわた|以降|以後|以前|時点)', after): return True
        absolute_start, absolute_end = offset + match.start(), offset + match.end()
        if re.match(r'\s*[-‐‑‒–—〜～]', after):
            tail = re.match(r'\s*[-‐‑‒–—〜～]\s*[)）]', after)
            opening = max(text.rfind('（', 0, match.start()), text.rfind('(', 0, match.start()))
            closing = max(text.rfind('）', 0, match.start()), text.rfind(')', 0, match.start()))
            close_end = offset + match.end() + tail.end() if tail else absolute_end
            open_designator = bool(tail and opening > closing and any(
                role.name == 'entity' and role.span.start <= offset + opening
                and role.span.end >= close_end for role in roles))
            if not open_designator: return True
        if not any(role.span.start <= absolute_start and absolute_end <= role.span.end for role in roles):
            return True
    return not found


def _without_resolved_date_guard(unknown, text, roles, offset, preserve=False):
    reason = 'unsupported source quantifier/exception/time'
    if reason in unknown and not preserve and not _unresolved_complex(text, roles, offset):
        return [item for item in unknown if item != reason]
    return list(unknown)


def attribute(text):
    words = list(_tagger()(text))
    if len(words) == 2 and words[0].feature.pos1 == '形容詞' and words[1].surface == 'さ':
        return 'nominal:' + _base(words[0])
    return text


def quantity(text):
    m = _NUM.fullmatch(text.strip())
    if not m: return None
    value = Decimal(m[1])
    if len(value.as_tuple().digits) > 128: return None
    return Quantity(value, m[2])


def _sentences(raw):
    start = 0; quoted = 0
    for i, ch in enumerate(raw):
        if ch in '「『': quoted += 1
        elif ch in '」』': quoted = max(0, quoted - 1)
        if quoted == 0 and ch in '。！？\n':
            if raw[start:i+1].strip(): yield start, i+1
            start = i+1
    if raw[start:].strip(): yield start, len(raw)


def _piece(source, raw, start, end, sovereign, family):
    full = _span(source, raw, start, end)
    left = start + len(full.text) - len(full.text.lstrip()); right = end
    # A prefix can declare a hypothesis, correction, quotation or normative
    # scope. It is not transparent metadata. Until that scope has a typed
    # interpretation, retain it as unread instead of asserting the suffix.
    colon = raw.find(':', left, right)
    if colon < 0: colon = raw.find('：', left, right)
    if colon >= 0:
        # Keep a complete numeric colon-valued copula (e.g. a displayed
        # clock value) as literal text. A label ending in a digit is not that
        # grammar and receives no exception. Nothing before a colon is cut.
        numeric_value = re.fullmatch(
            r'\s*[^:：。！？\n]+[はが]\s*[0-9]+(?:[:：][0-9]+)+(?:です|である|だ|ではない|でない|じゃない)?[。！？?]*\s*',
            raw[left:right])
        if not numeric_value:
            return [], [Unread(full, 'uninterpreted colon scope')]
    while left < right and raw[left] in ' 、,': left += 1
    condition = []; guard_spans = []; unknown = []; complex_guard = False
    text = raw[left:right]
    if _COMPLEX.search(text): unknown.append('unsupported source quantifier/exception/time')
    cm = COND.match(text)
    if cm and cm.group(1).strip():
        complex_guard = bool(_COMPLEX.search(text[:cm.end()]))
        guard = _span(source, raw, left, left + len(cm.group(1)))
        gc, gu = _piece(source, raw, guard.start, guard.end, sovereign, family)
        if len(gc) == 1 and not gu and not gc[0].conditions and not gc[0].unsupported:
            c = gc[0]
            condition.append(Pattern(c.predicate, tuple((r.name, r.term) for r in c.roles), c.polarity, c.modality, c.time))
            if c.modality != 'assert': unknown.append('unsupported antecedent modality')
        else: unknown.append('unsupported antecedent')
        guard_spans.append(guard); left += cm.end(); text = raw[left:right]
    body = _span(source, raw, left, right)
    tokens = _tokens(text); words = [t[0] for t in tokens]
    if text.rstrip().endswith(('?', '？')) or any(w.feature.pos1 == '助詞' and w.surface in ('か', 'かな', 'かしら', 'かい', 'かね', 'っけ') for w in words):
        return [], [Unread(full, 'interrogative source does not assert a fact')]
    if _DOUBLE_NEGATION.search(text):
        return [], [Unread(full, 'unsupported double negation')]
    # A greeting/interjection (a morning or thanks formula with ございます) is a speech act, not a proposition: nothing after the
    # interjection but auxiliaries / light verbs / particles / punctuation.
    if (tokens and tokens[0][0].feature.pos1 == '感動詞' and all(
            w.feature.pos1 in ('感動詞', '助動詞', '助詞', '補助記号', '記号') or (w.feature.pos1 == '動詞' and w.feature.pos2 == '非自立可能')
            for w, _, _ in tokens)):
        return [], [Unread(full, 'interjection is not a proposition')]
    if _NEGATIVE_ADJECTIVE.search(text):
        return [], [Unread(full, 'unsupported negative adjective')]
    if any('意志推量' in str(w.feature.cForm) for w in words):
        return [], [Unread(full, 'volitional source does not assert a fact')]
    # A duration (1時間) is not a clock-time scope: judge the other complex-scope words on the text without it.
    plain = re.sub(r'[0-9]+(?:\.[0-9]+)?(?:時間|分|秒)', '', text)
    if not condition and not _COMPLEX.search(plain) and all(u == 'unsupported source quantifier/exception/time' for u in unknown):
        from .semantic_measure import read_measure_sentence
        measured = read_measure_sentence(source, raw, start, left, right, sovereign, family)
        if measured is not None: return measured, []
    edges = extract(text); frames = read_all(text); records = read_records(text, 'record')
    predicates = _predicates(words)
    compound_indices = _compound_token_indices(tokens)
    filtered = [item for item in predicates if item[0] not in compound_indices]
    if len(frames) == len(predicates):
        frames = [frame for frame, predicate in zip(frames, predicates)
                  if predicate[0] not in compound_indices]
    predicates = filtered
    result = []
    # Noun copulas (including explicit nominal fragments) are relational facts.
    m = _copula_split(text, tokens)
    if m and not frames and m[2] and not _WH.search(m[2]):
        lhs, raw_value = m[1], m[2]
        suffix = re.search(r'(ではなかった|でなかった|じゃなかった|ではない|でない|じゃない|でした|だった|である|です|だ)$', raw_value)
        copula = suffix[1] if suffix else ''
        value = raw_value[:suffix.start()] if suffix else raw_value
        value = value.rstrip()
        if _predicate_phrase_value(tokens, m.value_token, m.start(2) + len(value), _bracket_depths(text), has_copula=bool(suffix)): unknown.append(_PREDICATE_VALUE_REASON)
        if not value:
            return [], [Unread(full, 'unsupported empty copula value')]
        entity, attr = _split_attribute(text, tokens, len(lhs))
        entity_at = left + text.index(entity); value_at = left + m.start(2)
        roles = [Role('entity', entity, _span(source, raw, entity_at, entity_at+len(entity)))]
        if attr:
            at = left + m.start(1) + len(lhs) - len(attr)
            roles.append(Role('attribute', attribute(attr), _span(source, raw, at, at+len(attr)), 'nominal'))
        q = quantity(value)
        if _NUM.fullmatch(value.strip()) and q is None: unknown.append('quantity outside exact contract')
        if entity in ('彼','彼女','それ','これ','あれ') or value in ('彼','彼女','それ','これ','あれ'):
            unknown.append('unresolved anaphora')
        roles.append(Role('value', q or value, _span(source, raw, value_at, value_at+len(value)), 'quantity' if q else 'literal'))
        pol = '-' if copula in ('ではなかった','でなかった','じゃなかった','ではない','でない','じゃない') else '+'
        before = raw[:value_at]; quoted = before.count('「')>before.count('」')
        mod = 'quote' if quoted else ('hedge' if _MODAL_UNSUPPORTED.search(text) else 'assert')
        ident = hashlib.sha256(f'{source}:{start}:{end}:copula'.encode()).hexdigest()[:24]
        result.append(Clause(ident, Variable('event_'+ident, 'event'), 'property' if attr else 'identity',
            _span(source, raw, value_at, value_at+len(value)), tuple(roles), full, body,
            polarity=pol, modality=mod, time='past' if copula in ('ではなかった','でなかった','じゃなかった','でした','だった') else '', conditions=tuple(condition), condition_spans=tuple(guard_spans),
            rule='copula', sovereign=sovereign, family=family,
            unsupported=tuple(_without_resolved_date_guard(unknown, text, roles, left, complex_guard))))
    elif frames:
        if len(frames) != len(predicates): unknown.append('predicate/frame alignment')
        tagged = tag([w for w, _, _ in tokens], [s0 for _, s0, _ in tokens])
        coordinated = (len(frames) > 1 and len(frames) == len(predicates)
                       and _clause_kind(text, 'record', False) == 'fact'
                       and coordination_ok(tagged, [p0 for p0, _ in predicates]))
        if len(frames) > 1 and not coordinated: unknown.append('multiple predicates need explicit clause scope')
        for index, frame in enumerate(frames):
            if index >= len(predicates): break
            ev, surface_pred = predicates[index]; word, pstart, pend = tokens[ev]
            roles = []; descriptors = []; issues = list(unknown); dropped_recipient = False
            causal = ev + 1 < len(tokens) and _base(tokens[ev + 1][0]) in ('せる', 'させる')
            previous = predicates[index-1][0] if index else -1
            chunk_start = tokens[previous][2] if previous >= 0 else 0
            for role in ('agent','patient','recipient'):
                value = getattr(frame, role)
                if not value: continue
                at = text.rfind(value, chunk_start, pstart)
                if at < 0:
                    at = text.find(value, 0, pstart)
                    if at >= 0 and at < chunk_start:       # the phrase belongs to an earlier clause: a borrowed role
                        pidx = [p0 for p0, _ in predicates]
                        topic = topic_phrase(tagged, pidx) if coordinated else None
                        c_first, c_last = chunk(tagged, pidx, index) if coordinated else (0, 0)
                        if not (coordinated and role == 'agent' and index > 0 and topic == (at, at + len(value))
                                and not own_subject_phrase(tagged, c_first, c_last)):
                            issues.append('unlicensed role borrowing'); continue
                if at < 0:
                    issues.append('unlocated '+role); continue
                claim = _role_claim(role, value, tokens, at, ev, surface_pred if causal else frame.predicate,
                                    _object_marked(frame, text, tokens, chunk_start, pstart), frame.patient or None)
                if claim == 'fused': issues.append(_TIME_FUSED_REASON)
                elif claim in ('time', 'drop'):
                    # a causee typed `recipient` by the shared frame reader (it is what the causative reason below is about) is dropped by the
                    # end-point rule when it shows neither place nor person: the causative frame is still unresolved
                    if role == 'recipient' and claim == 'drop' and (surface_pred if causal else frame.predicate) in _GOAL_PREDICATES: dropped_recipient = True
                    continue      # re-read below as the adjunct it is (time/result/goal/place)
                if value in ('彼','彼女','それ','これ','あれ') or '彼の' in value:
                    issues.append('unresolved anaphora')
                split = name_split_in(tokens_covering([(w.surface, w.feature.pos1, w.feature.pos2, a0, a1) for w, a0, a1 in tokens], at, at+len(value)), value)
                if split:      # an appositive descriptor (技師ユン) names the person; keep it covered, not as the value
                    desc, head = split
                    roles.append(Role(role, canonical(head), _span(source, raw, left+at+len(desc), left+at+len(value)), 'frame'))
                    descriptors.append((at, at+len(desc)))
                else:
                    roles.append(Role(role, canonical(value), _span(source, raw, left+at, left+at+len(value)), 'frame'))
            # Case adjuncts stay attached to this predicate and retain their exact source span.
            case_roles, case_issues = _case_roles(text, tokens, ev, chunk_start, roles, left, predicate=surface_pred if causal else frame.predicate,
                                                  document=True)
            if index == 0:
                adverbial = _time_adverbial(text, tokens, ev, chunk_start, roles, left)
                if adverbial:
                    case_roles.append(adverbial)
            topic_time = _time_topic(text, tokens, ev, chunk_start, [(r.span.start-left, r.span.end-left) for r in roles]
                                     + [span for _, _, span, _ in case_roles])
            if topic_time: case_roles.append(topic_time)
            # The causee of X が Y に Z を V-させる is typed `recipient` by the shared frame reader. That mislabelled recipient is
            # what makes the clause unsupported (diathesis re-reads it as causer/causee/patient). A causative with no
            # recipient (X が Y を V-させる: agent = causer, patient = causee) and a lexicalised -せる verb of transfer
            # (知らせる) carry no mislabelled role and are left as they were.
            if causal and (dropped_recipient or any(r.name == 'recipient' for r in roles)) and frame.predicate not in _TRANSFER_PREDICATES:
                issues.append(_CAUSATIVE_REASON)
            issues.extend(case_issues)
            for role, term, (at, end_at), kind in case_roles:
                roles.append(Role(role, term, _span(source, raw, left+at, left+end_at), kind))
                if term in ('彼','彼女','それ','これ','あれ') or '彼の' in term:
                    issues.append('unresolved anaphora')
            covered = [(r.span.start-left, r.span.end-left) for r in roles] + descriptors + _predicate_coverage(tokens, ev, surface_pred)
            own_tokens = tokens
            if coordinated:        # the other clauses of a coordinated sentence are read as their own clauses
                own_first, own_last = chunk(tagged, [p0 for p0, _ in predicates], index)
                own_tokens = tokens[own_first:own_last + 1]
            if _uncovered_nominals(own_tokens, covered): issues.append('unrepresented source content')
            if not roles and not any(w.feature.pos1 in _CONTENT_WORDS and not any(l <= s0 and e0 <= r for l, r in covered)
                                     for w, s0, e0 in own_tokens):
                issues.append(_NO_PARTICIPANT_REASON)      # an event with no participant and no content word beyond its own predicate
            for r in roles:
                if r.name not in ('agent','patient','recipient','origin','source','location','goal','time','place','means','companion','accompaniment','quotation','limit','direction','ambiguous','setting','topic','target','capacity','by'): continue
                lo_, hi_ = r.span.start - left, r.span.end - left
                for d0, d1 in descriptors:
                    if d1 == lo_: lo_ = d0
                if not phrase_bounded(tagged, lo_, hi_): issues.append('unrepresented source content'); break
            if len({r.name for r in roles}) != len(roles): issues.append('duplicate role in clause')   # two で-phrases: not representable
            if frame.ambiguous: issues.append('ambiguous frame role')
            mod = _clause_kind(text, 'record', frame.negated)
            mod = 'assert' if mod == 'fact' else mod
            clause_edges = [e for e in edges if e.ev == ev]
            if any(e.mod in ('quote','hedge','simile') for e in clause_edges): mod = clause_edges[0].mod
            if _MODAL_UNSUPPORTED.search(text): mod = 'hedge'
            before = raw[:left+pstart]
            if before.count('「')>before.count('」'): mod = 'quote'
            pol = '-' if frame.negated and mod not in ('prohibition','obligation') else '+'
            ident = hashlib.sha256(f'{source}:{start}:{end}:{index}'.encode()).hexdigest()[:24]
            issues = _without_resolved_date_guard(issues, text, roles, left, complex_guard)
            result.append(Clause(ident, Variable('event_'+ident,'event'),frame.predicate,
                _span(source,raw,left+pstart,left+pend),tuple(roles),full,body,polarity=pol,
                modality=mod,time=_event_time(words,ev),conditions=tuple(condition),
                condition_spans=tuple(guard_spans),rule='frame',sovereign=sovereign,family=family,
                unsupported=tuple(issues)))
    if not result:
        return [], [Unread(full,'unsupported clause grammar')]
    if len(result) > 1 and any(_NO_PARTICIPANT_REASON in c.unsupported for c in result[:-1]):
        # A conjunct that says nothing assertable and comes BEFORE the main clause is a manner/adverbial verb (a te-form
        # such as an 'in a hurry' conjunct); asserting the later clauses alone would drop what it contributed. A final
        # conjunct that says nothing (a zero-subject passive) only costs itself: the earlier clauses stand on their own.
        result = [c if _NO_PARTICIPANT_REASON in c.unsupported or _COORD_REASON in c.unsupported
                  else replace(c, unsupported=(*c.unsupported, _COORD_REASON)) for c in result]
    return result, []


def _construction_signature(reading):
    return tuple(sorted((
        clause.rule, clause.predicate,
        (clause.predicate_span.start, clause.predicate_span.end, clause.predicate_span.text),
        tuple((role.name, repr(role.term), role.span.start, role.span.end, role.rule)
              for role in clause.roles),
        clause.polarity, clause.modality, clause.time,
        tuple((pattern.predicate, repr(pattern.roles), pattern.polarity,
               pattern.modality, pattern.time) for pattern in clause.conditions),
    ) for clause in reading.clauses))


def _refines(first, second, registry):
    todo = list(first.refines); seen = set()
    while todo:
        name = todo.pop()
        if name == second.name: return True
        if name in seen: continue
        seen.add(name)
        target = registry.get(name)
        if target: todo.extend(target.refines)
    return False


def _read_constructions(source, raw, start, end, prior_clauses):
    from .constructions import ConstructionContext, Reading, TokenSpan, TypedNote, enabled
    sentence = raw[start:end]
    sentence_span = _span(source, raw, start, end)
    token_spans = tuple(TokenSpan(word, left, right) for word, left, right in _tokens(sentence))
    constructors = enabled()
    if len(token_spans) > 256 or len(constructors) > 64: return [], []
    context = ConstructionContext(sentence, sentence_span, token_spans, source,
                                  tuple(prior_clauses))
    results = []
    for construction in constructors:
        try:
            reading = construction.reads(context)
        except Exception:
            continue
        if reading is None: continue
        if (not isinstance(reading, Reading) or not isinstance(reading.clauses, tuple)
                or not isinstance(reading.consumed_spans, tuple)
                or not isinstance(reading.notes, tuple) or not reading.consumed_spans
                or len(reading.clauses) > context.budget.max_clauses
                or any(not isinstance(note, TypedNote) for note in reading.notes)):
            continue
        valid = True
        for span in reading.consumed_spans:
            if (not isinstance(span, Span) or span.source != source
                    or span.start < start or span.end > end or span.start >= span.end
                    or raw[span.start:span.end] != span.text):
                valid = False; break
        for note in reading.notes:
            span = note.span
            if span is not None and (not isinstance(span, Span) or span.source != source
                    or span.start < start or span.end > end or span.start >= span.end
                    or raw[span.start:span.end] != span.text):
                valid = False; break
        if not valid: continue
        known_ids = {old.id for old in prior_clauses}
        for clause in reading.clauses:
            if not isinstance(clause, Clause):
                valid = False; break
            if (not isinstance(clause.id, str) or not isinstance(clause.span, Span)
                    or clause.rule != construction.name or clause.span.source != source
                    or clause.span.start < start
                    or clause.span.end > end or clause.span.start >= clause.span.end
                    or raw[clause.span.start:clause.span.end] != clause.span.text
                    or clause.id in known_ids):
                valid = False; break
            if (not isinstance(clause.roles, tuple) or any(not isinstance(role, Role) for role in clause.roles)
                    or not isinstance(clause.condition_spans, tuple)
                    or not isinstance(clause.exception_spans, tuple)):
                valid = False; break
            parts = [clause.predicate_span, *(role.span for role in clause.roles),
                     *clause.condition_spans, *clause.exception_spans]
            if clause.body_span is not None: parts.append(clause.body_span)
            if any(not isinstance(part, Span) or part.source != source
                   or part.start < start or part.end > end or part.start >= part.end
                   or raw[part.start:part.end] != part.text for part in parts):
                valid = False; break
            body_span = clause.body_span or clause.span
            if (not (body_span.start <= clause.predicate_span.start
                     and clause.predicate_span.end <= body_span.end)
                    or any(not (body_span.start <= role.span.start < role.span.end <= body_span.end)
                           for role in clause.roles)):
                valid = False; break
            if any(not any(consumed.source == part.source and consumed.start <= part.start
                           and part.end <= consumed.end for consumed in reading.consumed_spans)
                   for part in parts):
                valid = False; break
            known_ids.add(clause.id)
        if valid:
            cost = (len(reading.consumed_spans) + len(reading.notes)
                    + sum(1 + len(clause.roles) + len(clause.conditions) + len(clause.exceptions)
                          for clause in reading.clauses))
            if cost > context.budget.max_steps: valid = False
        if valid and reading.clauses: results.append((construction, reading))

    if not results: return [], []
    registry = {construction.name: construction for construction in constructors}
    suppressed = set(); unresolved = []
    signatures = [_construction_signature(reading) for _, reading in results]
    keys = [set((span.source, span.start, span.end) for span in reading.consumed_spans)
            for _, reading in results]
    for i, (first, _) in enumerate(results):
        for j in range(i + 1, len(results)):
            if not keys[i].intersection(keys[j]) or signatures[i] == signatures[j]: continue
            second = results[j][0]
            first_refines = _refines(first, second, registry)
            second_refines = _refines(second, first, registry)
            if first_refines != second_refines:
                suppressed.add(j if first_refines else i)
            else:
                unresolved.append((i, j))
    ambiguous = set()
    for i, j in unresolved:
        if i not in suppressed and j not in suppressed: ambiguous.update((i, j))
    names = sorted({results[i][0].name for i in ambiguous})
    reason = 'ambiguous construction readings: ' + ', '.join(names)
    clauses = []; consumed = []
    for index, (_, reading) in enumerate(results):
        if index in suppressed: continue
        if index in ambiguous:
            clauses.extend(replace(clause, unsupported=(*clause.unsupported, reason))
                           for clause in reading.clauses)
        else:
            clauses.extend(reading.clauses)
            consumed.append(reading)
    return clauses, consumed


_FORMAL_NOUNS = frozenset(('こと', 'の', 'もの', 'ところ', 'ため', 'わけ', 'はず', 'よう', 'ほう', '方', '事', '物', 'つもり'))


def _spans_case_particle(toks, a, b, depths):
    """The phrase swallows a が/を/は/より particle at bracket depth 0 (<noun>が<noun>, <noun>より…) without being a clause-shaped
    nominal. A parenthetical gloss (頼升（まつだいら よりのり）) and a nominalised clause (問題を…解くこと: it holds a verb and ends in a
    formal noun) legitimately contain such particles."""
    hit = False; has_verb = False; last_content = None
    for w, x, y in toks:
        if x < a or y > b: continue
        if depths[x] > depths[a] or w.surface in _OPEN_BRACKETS or w.surface in _CLOSE_BRACKETS: continue
        if w.feature.pos1 == '助詞' and w.surface in ('が', 'を', 'は', 'より'): hit = True
        if w.feature.pos1 in ('動詞', '形容詞'): has_verb = True
        if w.feature.pos1 not in ('助詞', '助動詞', '補助記号', '記号'): last_content = w.surface
    return hit and not (has_verb and last_content in _FORMAL_NOUNS)


def _repeats_predicate(text, predicate):
    """A participant that is the predicate's own stem (お世話 of the made-up verb 世話る, from お世話になる): it is the predicate
    spelled as a noun, not a participant of it. A stem of one character (歌を歌う, a cognate object) is not matched."""
    stem = re.sub(r'^[おご御]', '', text.replace(' ', '').replace('　', ''))
    return len(stem) >= 2 and predicate.startswith(stem)


def _passive_follows(toks, index):
    """The predicate token at `index` is followed by れる/られる. A サ変 predicate (a noun + する, 指名された) is the noun and the する verb: the
    passive auxiliary follows the verb, whichever of the two the clause's predicate span starts at."""
    if index < len(toks) and toks[index][0].feature.pos1 == '名詞' and index + 1 < len(toks) and _base(toks[index + 1][0]) == 'する': index += 1
    return index + 1 < len(toks) and _base(toks[index + 1][0]) in ('れる', 'られる')


def _type_gate(clause):
    """Typed gate over every clause, whichever rule produced it (native frame/copula or a construction).

    A clause is never deleted: a role of the wrong type leaves it unsupported with a reason that names the type error
    (a time phrase as an agent, a phrase spanning a case particle, a role cutting a token, a non-person as a passive agent,
    a non-addressee as a recipient, a time phrase as a place/goal). Absent/ill-typed is not the same as false, so the
    sentence stays visible as unsupported rather than disappearing."""
    body = clause.body_span or clause.span
    roles = [r for r in clause.roles if r.name in _NOMINAL_ROLES or r.name in _TIME_ADJUNCT_ROLES or r.name in ('result', 'time', 'source')]
    if not clause.roles:
        # An event with no participant at all asserts nothing about anyone: either the sentence has no content word beyond the
        # predicate (すみません → 済む() 否定: nothing is said) or the participants were dropped silently (a clause read as する() out
        # of a sentence that names things). Not supported either way.
        if clause.rule not in ('record', 'measure') and _NO_PARTICIPANT_REASON not in clause.unsupported:
            return replace(clause, unsupported=(*clause.unsupported, _NO_PARTICIPANT_REASON))
        return clause
    if not roles: return clause
    toks = _tokens(body.text); depths = _bracket_depths(body.text)
    starts = {a for _, a, _ in toks}; ends = {b for _, _, b in toks}
    p0 = clause.predicate_span.start - body.start
    pred_index = next((i for i, (_, x, _) in enumerate(toks) if x >= p0), len(toks))
    followers = {}
    for role in roles:
        a, b = role.span.start - body.start, role.span.end - body.start
        while b > a and body.text[b - 1].isspace(): b -= 1
        followers[id(role)] = _particle_after(toks, b)
    has_object = any(r.name == 'patient' and followers[id(r)] == 'を' for r in roles)
    subject = next((r.span.text for r in roles if r.name == 'patient' and followers[id(r)] in ('が', 'は')), None)
    clause_passive = _passive_follows(toks, pred_index)
    objects = [r.span.text for r in roles if r.name == 'patient' and followers[id(r)] in (('が', 'は') if clause_passive else ('を',))]
    object_person = any(_is_person_phrase(t) for t in objects) if objects else None
    benefactive = _benefactive_after(toks, pred_index) if pred_index < len(toks) else False
    found = []
    for role in roles:
        a, b = role.span.start - body.start, role.span.end - body.start
        while a < b and body.text[a].isspace(): a += 1      # a role may carry the blanks around its phrase
        while b > a and body.text[b - 1].isspace(): b -= 1
        if role.name in _NOMINAL_ROLES:
            if a not in starts or b not in ends:
                found.append(_TOKEN_SPAN_REASON); continue
            if _spans_case_particle(toks, a, b, depths):
                found.append(_CASE_SPAN_REASON)
        text = role.span.text; follow = followers[id(role)]
        if role.name in _EVENT_PARTICIPANTS:
            # A time noun is a participant only as an object/subject (日時を伝える, 時期が来る); marked に or は it is the clause's time.
            if _is_time_phrase(text) and follow in ('に', 'は'): found.append(_TIME_ROLE_REASON)
            elif _time_fused(text): found.append(_TIME_FUSED_REASON)
            elif (role.name == 'agent' and follow in ('に', 'へ')
                  and not _can_be_passive_agent(text, clause.predicate, subject, has_object)):
                found.append(_NONAGENT_REASON)
            elif role.name == 'agent' and follow == 'に' and clause_passive and clause.predicate in _SELECTION_PREDICATES:
                found.append(_SELECTION_AGENT_REASON)
            elif role.name == 'agent' and follow == 'から' and _is_origin_not_agent(text):
                found.append(_NONAGENT_REASON)
            elif (role.name == 'recipient' and follow in ('に', 'へ')
                  and _recipient_claim(clause.predicate, text, has_object, benefactive, follow) == 'drop'):
                found.append(_NOT_ADDRESSEE_REASON)
            if role.name in ('agent', 'patient', 'recipient') and _repeats_predicate(text, clause.predicate):
                found.append(_REPEATS_PREDICATE_REASON)
            if (role.name == 'patient' and follow == 'は' and not clause_passive and _transitivity(clause.predicate) == 'intrans'):
                found.append(_TOPIC_PATIENT_REASON)
        elif role.name in _TIME_ADJUNCT_ROLES and _is_time_phrase(text):
            found.append(_TIME_ADJUNCT_REASON)
        elif role.name == 'source' and follow == 'から' and clause_passive and not _is_origin_spot(text):
            found.append(_SOURCE_AGENT_REASON)
        elif (role.name in ('goal', 'direction') and follow in ('に', 'へ') and clause.predicate in _GOAL_PREDICATES
              and not _is_end_point(text)):
            found.append(_ENDPOINT_REASON)
        elif (role.name == 'result' and follow == 'に' and clause.predicate in _CHANGE_PREDICATES and not clause_passive
              and any(r.name == 'patient' and followers[id(r)] == 'を' and r.span.start >= role.span.end for r in roles)):
            found.append(_RESULT_ORDER_REASON)
        elif role.name == 'result' and follow == 'に' and clause.predicate in _CHANGE_PREDICATES and not _is_time_phrase(text):
            reason = _result_ill_typed(clause.predicate, text, object_person, clause_passive)
            if reason: found.append(reason)
        elif role.name == 'time' and follow == 'に' and has_object and clause.predicate in _CHANGE_PREDICATES:
            found.append(_TIME_OF_CHANGE_REASON)        # 予定を月曜日に変えた: the に-time is the new value, not when it happened
        elif role.name == 'result' and _is_time_phrase(text) and clause.predicate not in _CHANGE_PREDICATES:
            found.append(_TIME_ADJUNCT_REASON)
    new = tuple(dict.fromkeys(r for r in found if r not in clause.unsupported))
    return replace(clause, unsupported=(*clause.unsupported, *new)) if new else clause


# W5-e: a coordination (と・や) or a disjunction (か) of noun phrases is neither one value of a role nor a companion: the clause is unsupported with a typed reason
# (docs/READING_SOUNDNESS.md section 10E). UniDic has no coordinating-particle class (と is a case particle, や・か are adverbial particles), so the rule is read off the
# surface of three closed function particles and off adjacency: the particle follows a noun-like token, noun-like tokens and の follow it without a gap, and a particle comes next.
_COORDINATION_REASON = 'COORDINATION_UNDETERMINED'
_DISJUNCTION_REASON = 'DISJUNCTION_UNDETERMINED'
_COORDINATING_PARTICLES = {'と': _COORDINATION_REASON, 'や': _COORDINATION_REASON, 'か': _DISJUNCTION_REASON}
_COORDINATION_BEFORE = ('名詞', '代名詞', '接尾辞', '数')
_COORDINATION_RUN = ('名詞', '代名詞', '接頭辞', '接尾辞', '形状詞', '数')
_COORDINATION_AFTER = ('格助詞', '係助詞', '副助詞')


def _coordination_marks(sentence):
    """(start, end, surface) of each particle token と・や・か of `sentence` that joins noun phrases: the token is a particle outside every compound particle, the token before
    it is noun-like, the tokens after it are noun-like or の (the first one noun-like, without a gap) and the token that ends that run is a case / binding / adverbial particle."""
    if not any(p in sentence for p in _COORDINATING_PARTICLES): return []
    toks = _tokens(sentence); compound = _compound_token_indices(toks); marks = []
    for i, (word, start, end) in enumerate(toks):
        if i == 0 or i in compound or word.feature.pos1 != '助詞' or word.surface not in _COORDINATING_PARTICLES: continue
        if toks[i - 1][0].feature.pos1 not in _COORDINATION_BEFORE: continue
        j = i + 1
        while j < len(toks) and (toks[j][0].feature.pos1 in _COORDINATION_RUN or (toks[j][0].feature.pos1 == '助詞' and toks[j][0].surface == 'の')):
            if j == i + 1 and toks[j][0].feature.pos1 not in _COORDINATION_RUN: break
            j += 1
        if j == i + 1 or j >= len(toks): continue
        after = toks[j][0].feature
        if after.pos1 == '助詞' and after.pos2 in _COORDINATION_AFTER: marks.append((start, end, word.surface))
    return marks


def _coordination_in_value(sentence):
    """W5-f (docs 10H): noun-like と・や・か links whose following token is noun-like, even before a copula."""
    if not any(p in sentence for p in _COORDINATING_PARTICLES): return []
    toks = _tokens(sentence); compound = _compound_token_indices(toks); marks = []
    for i, (word, start, end) in enumerate(toks):
        if i == 0 or i in compound or word.feature.pos1 != '助詞' or word.surface not in _COORDINATING_PARTICLES: continue
        if toks[i - 1][0].feature.pos1 not in _COORDINATION_BEFORE or i + 1 >= len(toks): continue
        if toks[i + 1][0].feature.pos1 not in _COORDINATION_RUN: continue
        marks.append((start, end, word.surface))
    return marks


def _coordination_tomo(sentence):
    """W5-f (docs 10H): positions of adjacent noun-like と+も particles or the とも suffix."""
    if 'とも' not in sentence and 'と' not in sentence: return []
    toks = _tokens(sentence); compound = _compound_token_indices(toks); marks = []
    for i, (word, start, end) in enumerate(toks):
        if i == 0 or i in compound or toks[i - 1][0].feature.pos1 not in _COORDINATION_BEFORE: continue
        if toks[i - 1][2] != start: continue
        if word.feature.pos1 == '接尾辞' and word.surface == 'とも':
            marks.append((start, end)); continue
        if word.feature.pos1 != '助詞' or word.feature.pos2 != '格助詞' or word.surface != 'と' or i + 1 >= len(toks): continue
        next_word, next_start, next_end = toks[i + 1]
        if next_start == end and next_word.feature.pos1 == '助詞' and next_word.feature.pos2 == '係助詞' and next_word.surface == 'も':
            marks.append((start, next_end))
    return marks


def _coordination_gate(clause):
    """W5-e: a clause stays visible as unsupported (never deleted) when it holds a coordination or a disjunction: a role whose syntactic reading marked it
    (`gold_parallel:choice` / `gold_parallel:parallel`, read here, not made), or a joining particle (`_coordination_marks`) inside the clause body.
    A reason already on the clause is not repeated."""
    reasons = []
    for role in clause.roles:
        rule = role.rule or ''
        if rule.endswith(':choice'): reasons.append(_DISJUNCTION_REASON)
        elif rule.endswith(':parallel'): reasons.append(_COORDINATION_REASON)
    body = clause.body_span or clause.span
    for start, _end, surface in _coordination_marks(clause.span.text):
        if body.start <= clause.span.start + start < body.end: reasons.append(_COORDINATING_PARTICLES[surface])
    for start, end, surface in _coordination_in_value(clause.span.text):
        absolute_start, absolute_end = clause.span.start + start, clause.span.start + end
        if any(role.name in ('value', 'entity') and role.span.start <= absolute_start and absolute_end <= role.span.end
               for role in clause.roles):
            reasons.append(_COORDINATING_PARTICLES[surface])
    tomo_count = sum(1 for start, _end in _coordination_tomo(clause.span.text)
                     if body.start <= clause.span.start + start < body.end)
    if tomo_count >= 2: reasons.append(_COORDINATION_REASON)
    new = tuple(dict.fromkeys(r for r in reasons if r not in clause.unsupported))
    return replace(clause, unsupported=(*clause.unsupported, *new)) if new else clause


def document_view(documents, *, sovereigns=None, family='document'):
    started = time.perf_counter(); sources = dict(documents); clauses = []; unread = []
    from .bot import _INJECTED
    for source, raw in sources.items():
        sovereign = (sovereigns or {}).get(source, family)
        for start, end in _sentences(raw):
            if _INJECTED.search(raw[start:end]):
                unread.append(Unread(_span(source,raw,start,end),'document instruction excluded')); continue
            cs, us = _piece(source,raw,start,end,sovereign,family)
            if re.match(r'\s*ただし',raw[start:end]):
                if clauses and clauses[-1].span.source == source:
                    base = clauses[-1]
                    if cs and cs[0].conditions:
                        clauses[-1] = replace(base,exceptions=cs[0].conditions,exception_spans=cs[0].condition_spans)
                        cs = [replace(c,exception_of=base.id) for c in cs]
                    else:
                        clauses[-1] = replace(base,unsupported=(*base.unsupported,'unsupported explicit exception'))
                        cs = [replace(c,unsupported=(*c.unsupported,'unsupported explicit exception'),exception_of=base.id) for c in cs]
                else: us.append(Unread(_span(source,raw,start,end),'exception has no source rule'))
            if us or any(clause.unsupported for clause in cs):
                constructed, readings = _read_constructions(source, raw, start, end, (*clauses, *cs))
                seen = {clause.id for clause in (*clauses, *cs)}
                for clause in constructed:
                    if clause.id not in seen:
                        cs.append(clause); seen.add(clause.id)
                for reading in readings:
                    for consumed in reading.consumed_spans:
                        us = [item for item in us if not (
                            item.span.source == consumed.source
                            and consumed.start <= item.span.start and item.span.end <= consumed.end)]
            cs = [_type_gate(c) for c in cs]
            cs = [_coordination_gate(c) for c in cs]
            clauses.extend(cs); unread.extend(us)
    return View(sources,tuple(clauses),tuple(unread),(time.perf_counter()-started)*1000)


class Builder:
    def __init__(self,text):
        self.text=text; self.nodes=[]; self.obligations=[]; self.outputs=[]; self.roots=[]; self.number=0

    def variable(self,sort='entity'):
        self.number+=1; return Variable('v'+str(self.number),sort)

    def obligation(self,node,kind,span,detail=''):
        ident='o'+str(len(self.obligations))
        self.obligations.append(Obligation(ident,span,kind,node,detail)); return ident

    def bind(self,pattern,span,target=None,relation=''):
        ident='n'+str(len(self.nodes)); ids=[self.obligation(ident,'relation',span,pattern.predicate)]
        for name,term in pattern.roles: ids.append(self.obligation(ident,'role',span,name))
        for kind,detail in (('polarity',pattern.polarity),('modality',pattern.modality)):
            ids.append(self.obligation(ident,kind,span,detail))
        if pattern.time:ids.append(self.obligation(ident,'time',span,pattern.time))
        if pattern.event is not None:ids.append(self.obligation(ident,'event',span))
        self.nodes.append(Operator(ident,'Bind',pattern=pattern,target=target,relation=relation,obligations=tuple(ids),span=span))
        current=ident
        for op in ('ApplyCondition','Except'):
            next_id='n'+str(len(self.nodes)); self.nodes.append(Operator(next_id,op,inputs=(current,))); current=next_id
        self.roots.append(current); return current

    def path(self,phrase,span,sort='value'):
        parts=phrase.split('の')
        if any(not p for p in parts): raise ValueError('empty nominal path')
        subject=parts[0]
        if len(parts)==1:
            value=self.variable(sort); self.bind(Pattern('identity',(('entity',subject),('value',value))),span); return value
        for i,attr in enumerate(parts[1:]):
            value=self.variable(sort if i==len(parts)-2 else 'entity')
            self.bind(Pattern('property',(('entity',subject),('attribute',attribute(attr)),('value',value))),span)
            subject=value
        return subject

    def finish(self):
        if not self.roots or not self.outputs: raise ValueError('no answer obligations')
        current=self.roots[0]
        for root in self.roots[1:]:
            ident='n'+str(len(self.nodes)); self.nodes.append(Operator(ident,'Join',inputs=(current,root))); current=ident
        return current

    def project(self,current):
        ident='n'+str(len(self.nodes)); outputs=[]; ids=[]
        for label,term,span,unit in self.outputs:
            oid=self.obligation(ident,'output',span,label); ids.append(oid); outputs.append(Output(label,term,oid,unit,span))
        self.nodes.append(Operator(ident,'Project',inputs=(current,),outputs=tuple(outputs),obligations=tuple(ids)))
        return Plan(tuple(self.nodes),ident)


def _property_question(fragment,b,span):
    cleaned=_END.sub('',fragment).strip()
    m=re.fullmatch(r'(.+?)(?:は|が)(?:誰|だれ|何|どこ|いつ)([A-Za-z一-鿿]*)',cleaned)
    if m:
        phrase=m[1]; unit=m[2]; value=b.path(phrase,span,'quantity' if unit else 'value')
        b.outputs.append((phrase,value,span,unit)); return True
    if cleaned.endswith('は'):
        phrase=cleaned[:-1]
        if read_all(phrase): return False
        if phrase in _ROLE_WORDS:
            value=b.variable(); b.bind(Pattern('*',((_ROLE_WORDS[phrase],value),)),span)
        elif 'の' in phrase:
            value=b.path(phrase,span)
        else:
            subject=b.variable(); value=b.variable('value')
            b.bind(Pattern('property',(('entity',subject),('attribute',attribute(phrase)),('value',value))),span)
        b.outputs.append((phrase,value,span,'')); return True
    return False


def _event_question(fragment,b,span):
    cleaned=_END.sub('',fragment).strip()
    # A relative head names the missing event role, and becomes a bound variable.
    relative=re.fullmatch(r'(.+?)(人|もの|物|箱|鍵|資料)(?:は)?',cleaned)
    # Cleft question ("Xを呼んだのは？"): the omitted head asks for the role the clause leaves open.
    cleft=None if relative else re.fullmatch(r'(.+?)の(?:は|が)(?:誰|だれ|何)?',cleaned)
    if cleft: relative=re.fullmatch(r'(.+?)(もの)',cleft[1]+'もの')
    core=relative[1] if relative else cleaned
    frames=read_all(core); positioned=_tokens(core); tokens=[w for w,_,_ in positioned]; preds=_predicates(tokens)
    if len(frames)!=1 or len(preds)!=1: return False
    f=frames[0]; original=preds[0][1]
    if any('意志推量' in str(w.feature.cForm) for w in tokens): return False
    if f.ambiguous: return False
    if any(w.feature.pos1 == '副詞' for w in tokens): return False
    roles=[]; outputs=[]; covered=[]
    for role in ('agent','patient','recipient'):
        term=getattr(f,role)
        if term and not _WH.search(term):
            roles.append((role,canonical(term)))
            at = core.rfind(term, 0, positioned[preds[0][0]][1])
            if at >= 0: covered.append((at, at+len(term)))
    case_roles, case_issues = _case_roles(core, positioned, preds[0][0], existing=roles)
    if case_issues: return False
    for role, term, (at, end_at), _kind in case_roles:
        if any(k==role for k,_ in roles):return False
        roles.append((role,term)); covered.append((at,end_at))
    passive=bool(re.search(r'(?:れ|られ)(?:た|る|ます)',core))
    handled_wh=set()
    for m in re.finditer(r'(誰|だれ|何時|いつ|何|どこ)(によって|が|は|を|に|へ|で|から|まで|と)',core):
        handled_wh.add(m.start())
        covered.append((m.start(),m.end()))
        wh, particle = m[1], m[2]
        if particle == 'によって':
            role='agent'
        elif particle in ('が','は'):
            role='patient' if passive else 'agent'
        elif particle == 'を': role='patient'
        elif particle == 'に':
            if wh in ('いつ','何時'): role='time'
            elif wh in ('誰','だれ'): role='agent' if passive else 'recipient'
            elif wh == 'どこ':
                if original in _GOAL_PREDICATES: role='goal'
                elif original in _LOCATION_PREDICATES or original in ('いる','ある'): role='location'
                else: return False
            else: return False
        elif particle == 'へ': role='direction'
        elif particle == 'で':
            if wh == 'どこ': role='place'
            else: return False
        elif particle == 'から': role='time' if wh in ('いつ','何時') else 'source'
        elif particle == 'まで': role='limit'
        elif particle == 'と':
            if wh in ('誰','だれ'): role='companion'
            elif original in ('言う','話す','述べる'): role='quotation'
            else: return False
        if original in CONVERSE and particle != 'によって':
            role={'agent':'recipient','recipient':'agent','origin':'agent','source':'agent'}.get(role,role)
        if any(k==role for k,_ in roles): return False
        value=b.variable(); roles.append((role,value)); outputs.append((role,value))
    if any(m.start() not in handled_wh for m in _WH.finditer(core)):return False
    covered.extend(_predicate_coverage(positioned, preds[0][0], original))
    if _uncovered_nominals(positioned, covered): return False
    if relative:
        head=relative[2]
        if original in CONVERSE: role='recipient'
        elif not f.agent: role='agent'
        elif not f.patient: role='patient'
        else: return False
        if any(k==role for k,_ in roles): return False
        value=b.variable(); roles.append((role,value if head in ('人','もの','物') else Nominal(head,value)))
        outputs.append((role,value))
    # Noun objects in abbreviated relative questions are head restrictions (not for a cleft: the noun is the entity itself).
    if relative and not cleft:
        roles=[(k,Nominal(v,b.variable()) if isinstance(v,str) and k=='patient' else v) for k,v in roles]
    mod='normative' if re.search(r'てよい|てもよい|可能|できる|られる',core) else 'assert'
    if not outputs and re.search(r'(?:の|は|が|を|に)$',cleaned): return False   # a particle-final fragment is not a yes/no question
    if outputs:
        b.bind(Pattern(f.predicate,tuple(roles),'-' if f.negated else '+',mod,_event_time(tokens,preds[0][0])),span)
        b.outputs.extend((label,value,span,'') for label,value in outputs)
    else:
        value=b.variable('value'); b.bind(Pattern(f.predicate,tuple(roles),'*',mod,_event_time(tokens,preds[0][0])),span,value,'whether-negative' if f.negated else 'whether')
        b.outputs.append(('可否',value,span,''))
    return True


def read_request(text,budget=Budget()):
    from .stage_split import split
    raw=text; full=_span('question',raw)
    sr=split(raw); stages=tuple(Stage(s['condition'],s['head'],s['fragment'],tuple(s['span'])) for s in sr.get('stages',()))
    try:
        if not raw.strip(): raise ValueError('empty request')
        from .question import _is_generation, _ACTION
        if _is_generation(raw) or _ACTION.search(raw):
            raise ValueError('generation/action speech act is unsupported in semantic QA')
        if _COMPLEX.search(raw) or _MODAL_UNSUPPORTED.search(raw): raise ValueError('unsupported mandatory scope/quantifier/time')
        if COND.match(raw): raise ValueError('unsupported question antecedent')
        b=Builder(raw)
        cleaned=raw.strip()
        # Explicit arithmetic over named nominal paths. Operands are dependency
        # nodes, never values harvested from nearby sentences.
        am=re.fullmatch(r'(.+?)(?:の合計|の差)(?:は|を)(?:何|いくつ)([A-Za-z一-鿿]*)(?:ですか)?[？?。]*',cleaned)
        cmp=re.fullmatch(r'(.+?)は(.+?)より(大きい|小さい|多い|少ない)(?:ですか|か)[？?。]*',cleaned)
        filt=re.fullmatch(r'(.+?)が([+-]?[0-9]+(?:\.[0-9]+)?\s*[^\s0-9]+?)(以上|以下)の(?:もの|物)は[？?。]*',cleaned)
        from .semantic_measure import read_measure_request
        from .semantic_wh import read_role_list_question
        measure_plan=read_measure_request(raw,b,full) or read_role_list_question(raw,b,full)
        if measure_plan is not None:
            plan=measure_plan
        elif filt:
            q=quantity(filt[2])
            if q is None: raise ValueError('unread filter quantity')
            entity=b.variable(); value=b.variable('quantity')
            current=b.bind(Pattern('property',(('entity',entity),('attribute',attribute(filt[1])),('value',value))),full)
            ident='n'+str(len(b.nodes)); oid=b.obligation(ident,'filter',full,'inclusive quantity threshold')
            b.nodes.append(Operator(ident,'Filter',inputs=(current,),tests=(Test(value,'>=' if filt[3]=='以上' else '<=',q),),obligations=(oid,)))
            b.outputs.append(('対象',entity,full,'')); plan=b.project(ident)
        elif am or cmp:
            phrases=am[1].split('と') if am else [cmp[1],cmp[2]]
            if len(phrases)!=2: raise ValueError('arithmetic requires two explicit operands')
            terms=tuple(b.path(p,full,'quantity') for p in phrases)
            current=b.finish() if b.outputs else b.roots[0]
            for root in b.roots[1:]:
                ident='n'+str(len(b.nodes)); b.nodes.append(Operator(ident,'Join',inputs=(current,root))); current=ident
            ident='n'+str(len(b.nodes)); result=b.variable('quantity' if am else 'value')
            op='Sum' if am and 'の合計' in cleaned else ('Difference' if am else 'Compare')
            oid=b.obligation(ident,'operation',full,op)
            b.nodes.append(Operator(ident,op,inputs=(current,),terms=terms,target=result,unit=am[2] if am else '',
                                   relation=('>' if cmp[3] in ('大きい','多い') else '<') if cmp else '',
                                   absolute=op=='Difference',obligations=(oid,)))
            # absolute is a Difference field, and is false for Sum.
            b.outputs.append(('計算結果' if am else '比較結果',result,full,am[2] if am else '')); plan=b.project(ident)
        else:
            fragments=re.split(r'[、,]|と(?=[^。?？]*?の)',cleaned)
            for fragment in fragments:
                if not fragment.strip(): raise ValueError('empty conjunct')
                at=raw.find(fragment); span=_span('question',raw,at,at+len(fragment))
                if not _property_question(fragment,b,span) and not _event_question(fragment,b,span):
                    raise ValueError('unsupported request grammar')
            plan=b.project(b.finish())
        from .semantic_validate import request_shape
        request=Request(raw,(plan,),tuple(b.obligations),(full,),stages=stages,rules=('frame/edge/stage candidates','nominal-path','role-wh','relational-plan'))
        request_shape(request,plan,budget)
        return request
    except (ValueError, KeyError, IndexError) as exc:
        return Request(raw,(),(),(),(Unread(full,str(exc)),),stages,('typed unread',))
    except Limit as exc:     # a path/plan deeper than the budget is a typed unread request, never an exception out of ask
        return Request(raw,(),(),(),(Unread(full,'request plan exceeds budget: '+str(exc)),),stages,('typed unread',))


# ===================================================================================================================================
# W3-b1: reading with the DIRECT type of a word (the coarse placement). docs/READING_SOUNDNESS.md section 10 (K62-K65).
# Nothing above this line is changed. What is added: a table of types (no word in it), one gate that is the only reader of a placement answer
# (`placement_type`), the two triggers and their plans. The plans return what to read; the entry (semantic_read.py) runs its own rules over it.
# ===================================================================================================================================
# K62. predicate type -> (role, case particles, expected noun types, 'arg' | 'adjunct'). Only these two of the 13 predicate types are read.
TYPED_FRAMES = {
    'P_MOVE': (
        ('agent', ('が',), ('PERSON', 'GROUP_ORG', 'ANIMAL'), 'arg'),
        ('goal', ('へ',), ('PLACE',), 'arg'),
        ('source', ('から',), ('PLACE',), 'arg'),
        ('place', ('で',), ('PLACE',), 'adjunct'),
        ('time', ('に',), ('TIME',), 'adjunct')),
    'P_COMMUNICATE': (
        ('agent', ('が',), ('PERSON', 'GROUP_ORG', 'ANIMAL'), 'arg'),
        # (the row `recipient / に / PERSON GROUP_ORG` was registered here and returned to "not read" on 2026-10-03 15:28:43 +0900: docs K62 table change record 1)
        ('patient', ('を',), ('PERSON', 'GROUP_ORG', 'ANIMAL', 'PLANT', 'ARTIFACT', 'SUBSTANCE_FOOD', 'EVENT_ACT', 'STATE_PROPERTY', 'ABSTRACT',
                              'INFO_LANGUAGE', 'BODY_PART', 'NATURAL_PHENOMENON', 'WORK', 'IDENTIFIER'), 'arg'),
        ('place', ('で',), ('PLACE',), 'adjunct'),
        ('time', ('に',), ('TIME',), 'adjunct')),
}
# the other predicate types: not read (name = a short reason; the sentences are in docs K62)
TYPED_FRAMES_NOT_READ = {
    'P_GIVE': 'NI_ROLE_SPLIT', 'P_CHANGE': 'NI_RESULT_OR_TIME', 'P_CREATE': 'NI_RECIPIENT_OR_BENEFICIARY', 'P_PERCEIVE': 'NI_SOURCE_OR_RECIPIENT',
    'P_EXIST': 'GA_ENTITY_OR_AGENT', 'P_POSSESS': 'PARTICLE_ROLE_UNDECIDED', 'P_ACT': 'PARTICLE_ROLE_UNDECIDED', 'P_STATE': 'ADJECTIVAL_PREDICATE',
    'P_COGNITION': 'TO_QUOTATION_NI_UNDECIDED', 'P_EMOTION': 'NI_DE_CAUSE_OR_PLACE', 'P_CONSUME': 'NI_ROLE_UNDECIDED',
}
# K63: a left-over part of a clause (a noun phrase and a particle, or a comma) that is read as a role: (noun type, particle) -> role. '' is the comma.
PLACEMENT_PART_CONSTRUCTIONS = {('TIME', ''): 'time', ('TIME', 'に'): 'time', ('PLACE', 'で'): 'place'}
# K64: marks of negation, condition, quantification, connection, quotation, modality and aspect (the list of W1-a4, copied; no rule is copied).
# A part is not read when one of its tokens or its particle is one of these (matched on the surface and on the base form of a token).
W3B1_MARKERS_JA = {
    'neg': ('ない', 'ず', 'ぬ', 'ません', 'なかっ', '全然', '決して', 'あまり', '少しも', 'ろくに', 'めったに', '必ずしも', '全く'),
    'cond': ('もし', 'もしも', '万一', '仮に', 'たとえ', 'ば', 'たら', 'なら', '場合'),
    'quant': ('よく', 'いつも', '時々', 'たまに', '少し', 'たくさん', 'ほとんど', 'だけ', 'しか', 'ばかり', 'のみ', 'さえ'),
    'conn': ('また', 'さらに', 'そして', 'しかし', 'だから', 'でも'),
    'quote': ('「', '」', '『', '』', 'という', 'そうだ', 'らしい'),
    'modal': ('たぶん', 'きっと', 'おそらく', 'ぜひ', 'どうか', 'どうやら', 'もしかすると', 'まるで'),
    'time_aspect': ('もう', 'まだ', 'すでに', 'ずっと', '急に', '突然', 'やっと', 'ついに', '再び'),
}
_PLACEMENT_STATES = ('DECIDED', 'MULTIPLE', 'UNPLACED', 'UNKNOWN', 'NO_PLACEMENT')


class CoarseQuery:
    """The placement as the reader asks it: `query(term)` returns the answer of `coarse_place.query(term, placement=<path>)` as it is (the word only: no
    context role, no context predicate, never a None path). `id` is made from the content hash of the first answer."""
    def __init__(self, path):
        self.path = path
        self._id = None

    def query(self, term):
        from . import coarse_place
        answer = coarse_place.query(term, placement=self.path)
        if self._id is None:
            info = (answer.get('placement') if isinstance(answer, dict) else None) or {}
            sha = info.get('content_sha256')
            self._id = 'coarse-placement:' + sha if sha else 'coarse-placement:unavailable:%s' % (info.get('reason'),)
        return answer

    @property
    def id(self):
        if self._id is None:
            self.query('a')
        return self._id


def _placement_answer_problems(answer):
    """The contract of the placement query (docs/COARSE_PLACEMENT.md 11.6): the problems of an answer, empty when it is well formed."""
    if not isinstance(answer, dict): return ['NOT_A_MAPPING']
    for key in ('state', 'top', 'origin', 'estimate_basis', 'constructed'):
        if key not in answer: return ['MISSING_' + key.upper()]
    state, top, origin, basis = answer['state'], answer['top'], answer['origin'], answer['estimate_basis']
    if state not in _PLACEMENT_STATES: return ['STATE_UNKNOWN']
    if not isinstance(top, list) or not all(isinstance(t, str) and t for t in top): return ['TOP_NOT_A_LIST_OF_STRINGS']
    if len(set(top)) != len(top): return ['TOP_DUPLICATED']
    if (state == 'DECIDED') != (len(top) == 1): return ['DECIDED_IFF_ONE_TYPE']
    if (state == 'MULTIPLE') != (len(top) >= 2): return ['MULTIPLE_IFF_TWO_OR_MORE_TYPES']
    if origin not in (None, 'direct', 'estimated'): return ['ORIGIN_UNKNOWN']
    if basis not in (None, 'proximity', 'generated'): return ['ESTIMATE_BASIS_UNKNOWN']
    if (origin == 'estimated') != (basis is not None) or (origin == 'estimated') != bool(answer['constructed']): return ['ESTIMATED_IFF_CONSTRUCTED_IFF_BASIS']
    if top and origin is None: return ['TYPES_WITHOUT_ORIGIN']
    if origin == 'direct':
        by = answer.get('decided_by')
        if not (isinstance(by, list) and by and all(isinstance(x, str) and x for x in by)): return ['DIRECT_WITHOUT_DECIDED_BY']
    return []


def placement_type(answer, *, adjunct=False):
    """THE GATE (K62): the type a placement answer lets the reader use, as (type, None), or (None, reason). The only reader of the fields of an answer
    (state, origin, top, decided_by, estimate_basis). The first rule that applies:
      1 an answer that breaks the contract -> PLACEMENT_INVALID
      2 NO_PLACEMENT / UNKNOWN / UNPLACED / MULTIPLE are four different reasons (nothing here turns one into another)
      3 an estimated answer (near or generated) is a construction, not a testimony: not used
      4 a direct answer that a generated definition decided (`gen_definition` among the arms) is not used
      5 an adjunct (a time or a place) whose arms are ALL role distributions (`role@...`) is not used: they count only that a word stood in that slot
      6 otherwise the one type of a DECIDED direct answer."""
    problems = _placement_answer_problems(answer)
    if problems: return None, 'PLACEMENT_INVALID:' + problems[0]
    state = answer['state']
    if state == 'NO_PLACEMENT':
        return None, 'PLACEMENT_NO_PLACEMENT:%s' % (((answer.get('placement') or {}).get('reason')) or 'UNSPECIFIED')
    if state == 'UNKNOWN': return None, 'PLACEMENT_UNKNOWN'
    if state == 'UNPLACED': return None, 'PLACEMENT_UNPLACED'
    if state == 'MULTIPLE': return None, 'PLACEMENT_MULTIPLE'
    if answer['origin'] == 'estimated':
        return None, 'PLACEMENT_ESTIMATED_NEAR' if answer['estimate_basis'] == 'proximity' else 'PLACEMENT_ESTIMATED_GENERATED'
    arms = answer['decided_by']
    if 'gen_definition' in arms: return None, 'PLACEMENT_DIRECT_VIA_GENERATED'
    if adjunct and all(a.startswith('role@') for a in arms): return None, 'PLACEMENT_SLOT_EVIDENCE_ONLY'
    return answer['top'][0], None


def typed_trigger_ja(text, view):
    """Which of the two typed paths (if any) may look at a refused Japanese input: 'U' (an unlisted predicate whose に / へ phrase the reader named
    `recipient`, or whose に phrase it left ambiguous), 'S4' (the only thing the reader could not represent is a left-over part), or None. One
    sentence, nothing unread, exactly one clause of the frame rule, no condition. A reason of the reader that is not the one of the path (it
    said `ambiguous frame role`, the clause has a quantifier, ...) is the reader saying it cannot split: it is not overridden."""
    if len(list(_sentences(text))) != 1 or view.unread or len(view.clauses) != 1: return None
    clause = view.clauses[0]
    if clause.rule != 'frame' or clause.conditions: return None
    unsupported = set(clause.unsupported)
    if unsupported == {'unrepresented source content'}: return 'S4'
    if any(clause.predicate in four for four in (_TRANSFER_PREDICATES, _GOAL_PREDICATES, _PLACEMENT_PREDICATES, _LOCATION_PREDICATES)): return None
    if not clause.unsupported and any(r.name == 'recipient' for r in clause.roles): return 'U'
    if unsupported == {'ambiguous case role: に'}:
        ambiguous = [r for r in clause.roles if r.name == 'ambiguous']
        if ambiguous and all(r.rule == 'case:に:location|goal|time' for r in ambiguous): return 'U'
    return None


class _Asker:
    """One placement question per word per sentence (the answers are kept for the sentence)."""
    def __init__(self, query):
        self.query, self.answers = query, {}

    def __call__(self, term):
        if term not in self.answers: self.answers[term] = self.query.query(term)
        return self.answers[term]


def typed_plan_u_ja(clause, toks, query, *, voice, written, strip, role_map):
    """Path U: (typed, None) or (None, reason). `voice` is the voice the entry decided, `written` the predicate as written, `strip(role)` the value of a
    role as the entry writes it, `role_map` the entry's table of reader role names -> convention names."""
    if voice != 'active': return None, 'PLACEMENT_VOICE_NOT_ACTIVE'
    if written is None or written != clause.predicate: return None, 'PLACEMENT_PREDICATE_NORMALIZED'
    ask = _Asker(query)
    ptype, why = placement_type(ask(written))
    if why: return None, '%s:predicate:%s' % (why, written)
    if not ptype.startswith('P_'): return None, 'PLACEMENT_NOT_PREDICATE_TYPE'
    if ptype in TYPED_FRAMES_NOT_READ: return None, 'PLACEMENT_FRAME_NOT_READ:' + ptype
    rows = TYPED_FRAMES.get(ptype)
    if rows is None: return None, 'PLACEMENT_FRAME_NOT_READ:' + ptype
    chosen, basis = [], {}
    for role in clause.roles:
        particle = _particle_after(toks, role.span.end)
        value = strip(role)
        if not value: return None, 'PLACEMENT_INVALID:EMPTY_TERM:%s' % (particle,)
        in_frame = [row for row in rows if particle in row[1]]
        if not in_frame: return None, 'PLACEMENT_PARTICLE_NOT_IN_FRAME:%s:%s' % (ptype, particle)
        answer = ask(value)
        noun, why = placement_type(answer)
        if why: return None, '%s:%s:%s' % (why, particle, value)
        candidates = [row for row in in_frame if noun in row[2]]
        if not candidates: return None, 'PLACEMENT_TYPE_MISMATCH:%s:%s:%s' % (ptype, particle, noun)
        if len(candidates) > 1: return None, 'PLACEMENT_ROLE_TIE'
        row = candidates[0]
        if row[3] == 'adjunct':
            noun2, why2 = placement_type(answer, adjunct=True)
            if why2: return None, '%s:%s:%s' % (why2, particle, value)
        # a role name the reader has decided must be the one the table gives (only `recipient` and `ambiguous` are left to the table)
        if role.name not in ('recipient', 'ambiguous'):
            decided = 'agent' if role.name == 'agent' else role_map.get(role.name)
            if decided != row[0]: return None, 'PLACEMENT_READER_DISAGREES:%s:%s' % (decided or role.name, row[0])
        if row[0] in basis: return None, 'PLACEMENT_DUPLICATE_ROLE:' + row[0]
        chosen.append((row[0], role)); basis[row[0]] = 'placement_direct:' + noun
    return {'mode': 'override', 'roles': chosen, 'predicate_basis': 'placement_direct:' + ptype, 'role_basis': basis, 'clause': replace(clause, unsupported=())}, None


def _w3b1_marker(token):
    """The kind of mark (K64) a token is, or None. Matched on the surface and on the base form; a numeral, a connective and a word of the entry's quantity
    list are marks by their own kind."""
    word = token[0]; feature = word.feature
    surface, base = word.surface, _base(word)
    if feature.pos2 == '数詞': return 'quant'
    for kind, words in W3B1_MARKERS_JA.items():
        if surface in words or base in words: return kind
    if feature.pos1 == '接続詞' or feature.pos2 == '接続助詞': return 'conn'
    from .semantic_read import _QUANT_SURFACES
    if surface in _QUANT_SURFACES or base in _QUANT_SURFACES: return 'quant'
    return None


def typed_plan_s4_ja(text, toks, clause, query):
    """Path S4: the left-over parts of the clause (a run of content tokens no role and no predicate covers) read as `time` / `place`, or (None, reason)."""
    pred_i = next((i for i, (w, a, b) in enumerate(toks) if a == clause.predicate_span.start), None)
    if pred_i is None: return None, 'PLACEMENT_PART_NONE'
    covered = [(r.span.start, r.span.end) for r in clause.roles] + list(_predicate_coverage(toks, pred_i, clause.predicate))
    def is_covered(i): return any(l <= toks[i][1] and toks[i][2] <= r for l, r in covered)
    runs, run = [], []
    for i, (w, a, b) in enumerate(toks):
        if w.feature.pos1 in _CONTENT_WORDS and not is_covered(i): run.append(i)
        else:
            if run: runs.append(run)
            run = []
    if run: runs.append(run)
    if not runs: return None, 'PLACEMENT_PART_NONE'
    ask = _Asker(query)
    connective = any(t[0].feature.pos1 == '接続詞' for t in toks)
    new_roles, basis = [], {}
    for run in runs:
        first, last = run[0], run[-1]
        surface = ''.join(toks[i][0].surface for i in run)
        for i in run:
            pos1 = toks[i][0].feature.pos1
            if pos1 not in ('名詞', '接頭辞', '接尾辞'): return None, 'PLACEMENT_PART_NOT_NP:' + pos1
            if toks[i][0].feature.pos2 == '数詞': return None, 'PLACEMENT_PART_MARKER:quant'
        # what stands before the part must be the sentence start, a mark of punctuation, a covered token, or the particle of a covered phrase
        j = first - 1
        isolated = j < 0 or toks[j][0].feature.pos1 == '補助記号' or is_covered(j)
        if not isolated:
            while j >= 0 and toks[j][0].feature.pos1 == '助詞': j -= 1
            isolated = 0 <= j < first - 1 and is_covered(j)
        if not isolated: return None, 'PLACEMENT_PART_NOT_ISOLATED'
        if last + 1 >= len(toks): return None, 'PLACEMENT_PART_NOT_FOLLOWED'
        after = toks[last + 1][0]
        if after.surface == '、' and after.feature.pos1 == '補助記号': particle, particle_token = '', None
        elif after.feature.pos1 == '助詞': particle, particle_token = after.surface, toks[last + 1]
        else: return None, 'PLACEMENT_PART_NOT_FOLLOWED'
        if particle_token is not None and last + 2 < len(toks) and toks[last + 2][0].feature.pos1 == '助詞':
            return None, 'PLACEMENT_PART_PARTICLE:' + particle + toks[last + 2][0].surface
        checked = [toks[i] for i in run] + ([particle_token] if particle_token is not None else [])
        for token in checked:
            kind = _w3b1_marker(token)
            if kind: return None, 'PLACEMENT_PART_MARKER:' + kind
        if connective: return None, 'PLACEMENT_PART_MARKER:conn'
        answer = ask(surface)
        noun, why = placement_type(answer, adjunct=True)
        if why: return None, '%s:part:%s' % (why, surface)
        role_name = PLACEMENT_PART_CONSTRUCTIONS.get((noun, particle))
        if role_name is None: return None, 'PLACEMENT_PART_NO_ROLE:%s:%s' % (noun, particle or '∅')
        if role_name in basis: return None, 'PLACEMENT_DUPLICATE_ROLE:' + role_name
        start, end = toks[first][1], toks[last][2]
        new_roles.append(Role(role_name, surface, Span(clause.predicate_span.source, start, end, text[start:end]), 'placement_direct:' + noun))
        basis[role_name] = 'placement_direct:' + noun
    return {'mode': 'extra', 'roles': new_roles, 'predicate_basis': None, 'role_basis': basis,
            'clause': replace(clause, roles=clause.roles + tuple(new_roles), unsupported=())}, None


def typed_tail_ja(toks, clause):
    """K63, the gate on the ending of the predicate (table change record 2, review round 2 M7): None when the clause that a typed path read has one of the four
    endings that the present rules turn into a polarity and a tense, else the reason (PLACEMENT_PREDICATE_TAIL_UNINTERPRETED:<form of the head>:<part of speech
    of the first token after the head, or なし>). The head is the token the predicate span ends with, the tail the tokens after it (one closing full stop 。 . ． apart;
    ！ and ？ stay in the tail).
    The four shapes are closed structures of a verb form and an auxiliary (no list of words, no list of endings): the head in the final form with nothing after
    it; in the continuative form with the auxiliary た; in the irrealis form with ない in the final form; in the irrealis form with ない in the continuative form
    and た. Everything else is not read, without asking whether the present rules would have used the word (a wide abstention): an ending the rules do not
    interpret (ている + ない, ません, a prohibition, まい, たい, an imperative, てください, ...) is not told apart from one they do."""
    reason = 'PLACEMENT_PREDICATE_TAIL_UNINTERPRETED:%s:%s'
    head_i = next((i for i, (w, a, b) in enumerate(toks) if b == clause.predicate_span.end), None)
    if head_i is None: return reason % ('head', 'なし')
    tail = list(toks[head_i + 1:])
    if tail and tail[-1][0].surface in ('。', '.', '．') and tail[-1][0].feature.pos1 == '補助記号': tail.pop()      # a closing full stop only: ！ and ？ stay in the tail
    first = tail[0][0].feature.pos1 if tail else 'なし'
    head = toks[head_i][0].feature
    if head.pos1 != '動詞': return reason % ('head', first)
    form = head.cForm or ''

    def aux(token, lemma, tail_form):
        f = token[0].feature
        return f.pos1 == '助動詞' and f.lemma == lemma and (f.cForm or '').startswith(tail_form)
    if not tail and form.startswith('終止形'): return None
    if len(tail) == 1 and form.startswith('連用形') and aux(tail[0], 'た', '終止形'): return None
    if len(tail) == 1 and form.startswith('未然形') and aux(tail[0], 'ない', '終止形'): return None
    if len(tail) == 2 and form.startswith('未然形') and aux(tail[0], 'ない', '連用形') and aux(tail[1], 'た', '終止形'): return None
    return reason % (form or 'なし', first)


# K63 (table change record 3, review round 3 M8): the gate on a head that may be a derived verb. The table is docs/READING_SOUNDNESS.md `table:w3b1_derived_gate`
# (a test compares the two). A potential verb (a godan potential, a ra-dropped potential), a spontaneous one and a short causative (〜す) are, in the output of
# the tagger, independent verbs of their own (a shimo-ichidan or a godan verb), so the four endings of typed_tail_ja let them through, and the present rules then
# return the predicate in the derived form with no modality / voice (conventions section 3: a potential is the original verb with modality ability; section 4: a
# causative is the original verb with voice causative). The gate is a closed structure of the conjugation type and the end of the dictionary form, with no list
# of words: (conjugation type, end of the dictionary form), None = not asked.
DERIVED_GATE = (('下一段', None), ('五段-サ行', 'ア段+す'))
_A_ROW_KANA = frozenset('あかさたなはまやらわがざだばぱ')    # the a-column of the gojuon (clear, voiced and semi-voiced); the kana of a conjugation, not words


def typed_head_derived_ja(toks, clause):
    """K63, the gate on a head that may be a derived verb (table change record 3, review round 3 M8): None, or the reason
    (PLACEMENT_PREDICATE_POSSIBLY_DERIVED:<conjugation type of the head>). Applied only after typed_tail_ja has let the clause through (its reasons are unchanged).
    The head is the token the predicate span ends with (as in typed_tail_ja). One of the rows of DERIVED_GATE: the conjugation type (feature.cType) begins with
    下一段, or it is 五段-サ行 and the last two characters of the dictionary form (orthBase, as typed_edges._base) are a kana of the a-column and す.
    The answer fields of the placement are not read here and the placement is not asked."""
    reason = 'PLACEMENT_PREDICATE_POSSIBLY_DERIVED:%s'
    head_i = next((i for i, (w, a, b) in enumerate(toks) if b == clause.predicate_span.end), None)
    if head_i is None: return reason % 'head'
    word = toks[head_i][0]
    ctype = word.feature.cType or ''
    base = _base(word)
    if ctype.startswith(DERIVED_GATE[0][0]): return reason % ctype
    if ctype == DERIVED_GATE[1][0] and len(base) >= 2 and base[-1] == 'す' and base[-2] in _A_ROW_KANA: return reason % ctype
    return None


# ===================================================================================================================================
# W3-b2: the second step of reading by the type of a word. docs/READING_SOUNDNESS.md section 10B (K94-K99).
# Nothing above this line is changed. What is added: a gate for a SET of allowed types (`placement_fit`: a split answer whose every candidate is allowed is read),
# the reader of the frame of a predicate (`predicate_frame`, used only to narrow), the head of `X no Y` (`no_phrase_head`), one more trigger (U3) and the two plans of
# this step. The plans return what to read; the entry (semantic_read.py) runs its own rules over it and decides in which order the plans of W3-b1 and of W3-b2 run.
# No table of K62 / K63 / K64 is widened: the only constants are the two rule names of U3, the three demonstratives of the ticket and the two part-of-speech classes below.
# ===================================================================================================================================
W3B2_AMBIGUOUS_RULES = ('case:で:place|means', 'case:に:location|goal|time')        # K94: the two splits of the reader that U3 looks at
W3B2_DEMONSTRATIVES = ('この', 'その', 'あの')                                       # K97: the ticket's three (the question word of the entry's list is not one)
W3B2_HEAD_RELATIONAL_POS3 = ('副詞可能', '助数詞可能')                                # K96: a head of these classes does not decide the type of its phrase
W3B2_REASON_NAMES = ('PLACEMENT_FRAME_PARTICLE_NOT_CONFIRMED', 'PLACEMENT_FRAME_TYPE_NOT_CONFIRMED', 'PLACEMENT_FRAME_INVALID', 'PLACEMENT_HEAD_RELATIONAL',
                     'PLACEMENT_DETERMINER_ROLE_UNTYPED', 'PLACEMENT_DETERMINER_NOT_BOUNDED', 'PLACEMENT_DETERMINER_NOT_READ', 'PLACEMENT_W3B2_NOT_TRIGGERED')
W3B2_ROLE_BASIS_RE = r'placement_(direct|all_candidates)(_head)?:[A-Z_]+(\+[A-Z_]+)*'    # K99: the values of `role_basis` the new paths write (and W3-b1's)
_CASE_PARTICLES_9 = ('が', 'を', 'に', 'で', 'へ', 'と', 'から', 'まで', 'より')     # the keys a CONFIRMED frame may hold (docs/COARSE_PLACEMENT.md 12.10)


def placement_fit(answer, allowed, *, adjunct=False):
    """K95, the gate for a SET of allowed types: (kind, types) or (None, reason). `placement_type` is the gate of one type; this one adds the one case it refuses
    for being split: every candidate of a direct split answer is in `allowed` (then whichever candidate it is, the reading is the same).
      ('direct', (T,))                T is the one type of a DECIDED direct answer and is in `allowed`
      ('mismatch', (T,))              the same, T is not in `allowed` (the caller names it in its own reason)
      ('all_candidates', (T1, T2..))  a MULTIPLE direct answer, no generated definition, not (an adjunct decided only by role distributions), every type in `allowed`
      (None, reason)                  every other case; for a split answer a candidate of which is outside, the reason is PLACEMENT_MULTIPLE, as in W3-b1; an estimated
                                      split gives the reason of the estimate (it is a construction, whatever its candidates)."""
    allowed = frozenset(allowed)
    noun, why = placement_type(answer, adjunct=adjunct)
    if why is None:
        return ('direct', (noun,)) if noun in allowed else ('mismatch', (noun,))
    if why != 'PLACEMENT_MULTIPLE': return None, why
    # placement_type has checked the contract: the state is MULTIPLE, the origin is direct or estimated
    if answer['origin'] == 'estimated':
        return None, 'PLACEMENT_ESTIMATED_NEAR' if answer['estimate_basis'] == 'proximity' else 'PLACEMENT_ESTIMATED_GENERATED'
    arms = answer['decided_by']
    if 'gen_definition' in arms: return None, 'PLACEMENT_DIRECT_VIA_GENERATED'
    if adjunct and all(a.startswith('role@') for a in arms): return None, 'PLACEMENT_SLOT_EVIDENCE_ONLY'
    types = tuple(sorted(answer['top']))
    if set(types) <= allowed: return 'all_candidates', types
    return None, 'PLACEMENT_MULTIPLE'


def predicate_frame(answer):
    """K95, the frame of a predicate (W3-a3, docs/COARSE_PLACEMENT.md 12.10), read only to NARROW what the table reads: ('table', None) when the answer has no frame
    (no `frame_status`, NOT_CONFIRMED, NO_FRAME_TABLE: the table alone decides, as before), ('confirmed', {particle: frozenset(types)}) for a CONFIRMED frame that keeps the
    invariants of 12.10, else (None, 'PLACEMENT_FRAME_INVALID:<problem>'). The caller has already passed the answer through `placement_type`."""
    if 'frame_status' not in answer: return 'table', None
    status = answer['frame_status']
    if status in ('NOT_CONFIRMED', 'NO_FRAME_TABLE'): return 'table', None
    if status != 'CONFIRMED': return None, 'PLACEMENT_FRAME_INVALID:FRAME_STATUS_UNEXPECTED'

    def bad(problem): return None, 'PLACEMENT_FRAME_INVALID:' + problem
    if answer.get('namespace') != 'P': return bad('NAMESPACE_NOT_P')
    if answer.get('state') != 'DECIDED' or answer.get('origin') != 'direct': return bad('NOT_DECIDED_DIRECT')
    if 'gen_frame' not in (answer.get('decided_by') or []): return bad('GEN_FRAME_NOT_IN_DECIDED_BY')
    frame = answer.get('frame')
    if not isinstance(frame, dict): return bad('FRAME_NOT_A_MAPPING')
    out = {}
    for particle, types in frame.items():
        if particle not in _CASE_PARTICLES_9: return bad('PARTICLE_NOT_CASE:%s' % (particle,))
        if not (isinstance(types, list) and types and all(isinstance(t, str) and t for t in types) and types == sorted(set(types))):
            return bad('TYPES_NOT_A_SORTED_LIST:%s' % (particle,))
        out[particle] = frozenset(types)
    return 'confirmed', out


def _basis_types(basis):
    """The types of a `role_basis` value: `placement_direct_head:PLACE` -> ('PLACE',), `placement_all_candidates:A+B` -> ('A', 'B')."""
    return tuple(basis.split(':', 1)[1].split('+'))


def typed_frame_check_ja(toks, typed, predicate_answer):
    """K95: the frame of the predicate (when CONFIRMED) must hold the particle and every type of every role a path U read; None, or the reason. Applied to what
    W3-b1 read (new questions are not asked) and, inside the plan, to what W3-b2 reads."""
    kind, info = predicate_frame(predicate_answer)
    if kind is None: return info
    if kind == 'table': return None
    ptype = typed['predicate_basis'].split(':', 1)[1]
    for name, role in typed['roles']:
        particle = _particle_after(toks, role.span.end)
        if particle not in info: return 'PLACEMENT_FRAME_PARTICLE_NOT_CONFIRMED:%s:%s' % (ptype, particle)
        types = _basis_types(typed['role_basis'][name])
        if not set(types) <= info[particle]: return 'PLACEMENT_FRAME_TYPE_NOT_CONFIRMED:%s:%s:%s' % (ptype, particle, '+'.join(types))
    return None


def _is_no_token(token):
    f = token[0].feature
    return token[0].surface == 'の' and f.pos1 == '助詞' and f.pos2 == '格助詞'


def no_phrase_head(toks, start, end):
    """K96: the head of `X no Y`, (head, None); (None, None) when the span has not the structure; (None, 'PLACEMENT_HEAD_RELATIONAL:<pos3>') when the head is of a class
    that does not decide the type of the phrase. The structure (no list of words): the tokens of the span are all nouns (not numerals), prefixes, suffixes or the case
    particle の; there is at least one の, none first, none last, none next to another. The head is what stands after the last の."""
    inside = [t for t in toks if t[1] >= start and t[2] <= end]
    if not inside or inside[0][1] != start or inside[-1][2] != end: return None, None

    def nominal(t):
        f = t[0].feature
        return (f.pos1 == '名詞' and f.pos2 != '数詞') or f.pos1 in ('接頭辞', '接尾辞')
    if not all(_is_no_token(t) or nominal(t) for t in inside): return None, None
    at = [i for i, t in enumerate(inside) if _is_no_token(t)]
    if not at or at[0] == 0 or at[-1] == len(inside) - 1 or any(b - a == 1 for a, b in zip(at, at[1:])): return None, None
    head = inside[at[-1] + 1:]
    pos3 = head[-1][0].feature.pos3
    if pos3 in W3B2_HEAD_RELATIONAL_POS3: return None, 'PLACEMENT_HEAD_RELATIONAL:%s' % pos3
    return ''.join(t[0].surface for t in head), None


def _is_demonstrative_token(token):
    """K97: a demonstrative of the ticket's three, by the part of speech (a 連体詞) and the surface. An interjection the tagger cuts is not one."""
    return token[0].feature.pos1 == '連体詞' and token[0].surface in W3B2_DEMONSTRATIVES


def _w3b2_not_demonstrative(toks, role):
    """K97: a role span that begins with a 連体詞 that the entry strips as a demonstrative (its list holds the question word) but that is not one of the three:
    the reason, else None. The question is not read."""
    from .semantic_read import _DEMONSTRATIVES
    inside = [t for t in toks if t[1] >= role.span.start and t[2] <= role.span.end]
    if inside and inside[0][0].feature.pos1 == '連体詞' and inside[0][0].surface in _DEMONSTRATIVES and inside[0][0].surface not in W3B2_DEMONSTRATIVES:
        return 'PLACEMENT_DETERMINER_NOT_READ:%s' % inside[0][0].surface
    return None


def typed_trigger_w3b2_ja(text, view):
    """K94: 'U3' (a clause whose で phrase the reader left ambiguous) or None. Decided before any question to the placement. One sentence, nothing unread, exactly one
    clause of the frame rule, no condition, a predicate in none of the reader's four lists, the unsupported reasons only the ambiguity of で (and, beside it, of に), and
    every `ambiguous` role of one of the two rules of W3B2_AMBIGUOUS_RULES. A split the reader names otherwise (result|beneficiary, goal|purpose|addressee ...) is not
    looked at."""
    if len(list(_sentences(text))) != 1 or view.unread or len(view.clauses) != 1: return None
    clause = view.clauses[0]
    if clause.rule != 'frame' or clause.conditions: return None
    if any(clause.predicate in four for four in (_TRANSFER_PREDICATES, _GOAL_PREDICATES, _PLACEMENT_PREDICATES, _LOCATION_PREDICATES)): return None
    unsupported = set(clause.unsupported)
    if unsupported not in ({'ambiguous case role: で'}, {'ambiguous case role: で', 'ambiguous case role: に'}): return None
    ambiguous = [r for r in clause.roles if r.name == 'ambiguous']
    if not ambiguous or not all(r.rule in W3B2_AMBIGUOUS_RULES for r in ambiguous): return None
    if not any(r.rule == W3B2_AMBIGUOUS_RULES[0] for r in ambiguous): return None
    return 'U3'


def typed_plan_u_w3b2_ja(clause, toks, query, *, voice, written, strip, role_map):
    """K94-K96, the plan of paths U and U3 of W3-b2: (typed, None) or (None, reason). The same table (K62) and the same steps as `typed_plan_u_ja`, with three
    differences: a role is read when `placement_fit` gives `direct` or `all_candidates` for the row of its particle; the type of `X no Y` is asked of its head (the whole
    phrase is not asked); the frame of the predicate (K95) narrows each role (the particle must be in it, every type of the role must be in its list)."""
    if voice != 'active': return None, 'PLACEMENT_VOICE_NOT_ACTIVE'
    if written is None or written != clause.predicate: return None, 'PLACEMENT_PREDICATE_NORMALIZED'
    ask = _Asker(query)
    answer_p = ask(written)
    ptype, why = placement_type(answer_p)
    if why: return None, '%s:predicate:%s' % (why, written)
    if not ptype.startswith('P_'): return None, 'PLACEMENT_NOT_PREDICATE_TYPE'
    if ptype in TYPED_FRAMES_NOT_READ: return None, 'PLACEMENT_FRAME_NOT_READ:' + ptype
    rows = TYPED_FRAMES.get(ptype)
    if rows is None: return None, 'PLACEMENT_FRAME_NOT_READ:' + ptype
    fkind, finfo = predicate_frame(answer_p)
    if fkind is None: return None, finfo
    chosen, basis = [], {}
    for role in clause.roles:
        particle = _particle_after(toks, role.span.end)
        value = strip(role)
        if not value: return None, 'PLACEMENT_INVALID:EMPTY_TERM:%s' % (particle,)
        question = _w3b2_not_demonstrative(toks, role)
        if question: return None, question
        in_frame = [row for row in rows if particle in row[1]]
        if not in_frame: return None, 'PLACEMENT_PARTICLE_NOT_IN_FRAME:%s:%s' % (ptype, particle)
        if fkind == 'confirmed' and particle not in finfo: return None, 'PLACEMENT_FRAME_PARTICLE_NOT_CONFIRMED:%s:%s' % (ptype, particle)
        head, relational = no_phrase_head(toks, role.span.end - len(value), role.span.end)      # the value is the end of the role's text (a demonstrative at its start was taken off)
        if relational: return None, relational
        answer = ask(head or value)
        fits, last = [], None
        for row in in_frame:
            kind, payload = placement_fit(answer, row[2], adjunct=row[3] == 'adjunct')
            if kind in ('direct', 'all_candidates'): fits.append((row, kind, payload))
            else: last = (kind, payload)
        if not fits:
            kind, payload = last
            if kind == 'mismatch': return None, 'PLACEMENT_TYPE_MISMATCH:%s:%s:%s' % (ptype, particle, payload[0])
            return None, '%s:%s:%s' % (payload, particle, value)
        if len(fits) > 1: return None, 'PLACEMENT_ROLE_TIE'
        row, kind, types = fits[0]
        if fkind == 'confirmed' and not set(types) <= finfo[particle]:
            return None, 'PLACEMENT_FRAME_TYPE_NOT_CONFIRMED:%s:%s:%s' % (ptype, particle, '+'.join(types))
        if role.name not in ('recipient', 'ambiguous'):
            decided = 'agent' if role.name == 'agent' else role_map.get(role.name)
            if decided != row[0]: return None, 'PLACEMENT_READER_DISAGREES:%s:%s' % (decided or role.name, row[0])
        if row[0] in basis: return None, 'PLACEMENT_DUPLICATE_ROLE:' + row[0]
        chosen.append((row[0], role))
        basis[row[0]] = 'placement_%s%s:%s' % (kind, '_head' if head else '', '+'.join(types))
    return {'mode': 'override', 'roles': chosen, 'predicate_basis': 'placement_direct:' + ptype, 'role_basis': basis, 'clause': replace(clause, unsupported=())}, None


def typed_plan_s4_w3b2_ja(text, toks, clause, query, *, role_map):
    """K96-K97, the plan of path S4 of W3-b2: the parts of W3-b1's plan (a run of content tokens no role and no predicate covers, read as `time` / `place` by K63), with
    (K96) two runs joined by one の made one part whose head is the later run, and (K97) a demonstrative before the part (D1) or before a role the reader typed, when no
    part is left (D2). (typed, None) or (None, reason)."""
    pred_i = next((i for i, (w, a, b) in enumerate(toks) if a == clause.predicate_span.start), None)
    if pred_i is None: return None, 'PLACEMENT_PART_NONE'
    covered = [(r.span.start, r.span.end) for r in clause.roles] + list(_predicate_coverage(toks, pred_i, clause.predicate))

    def is_covered(i): return any(l <= toks[i][1] and toks[i][2] <= r for l, r in covered)
    runs, run = [], []
    for i, (w, a, b) in enumerate(toks):
        if w.feature.pos1 in _CONTENT_WORDS and not is_covered(i): run.append(i)
        else:
            if run: runs.append(run)
            run = []
    if run: runs.append(run)
    if not runs: return _s4_demonstrative_roles(text, toks, clause, query, role_map, covered)
    parts = []
    for r in runs:                   # K96: two runs joined by exactly one の are one part
        if parts and r[0] - parts[-1][-1] == 2 and _is_no_token(toks[parts[-1][-1] + 1]): parts[-1] = parts[-1] + [parts[-1][-1] + 1] + r
        else: parts.append(r)
    ask = _Asker(query)
    connective = any(t[0].feature.pos1 == '接続詞' for t in toks)
    new_roles, basis, flags = [], {}, {}
    for part in parts:
        first, last = part[0], part[-1]
        surface = ''.join(toks[i][0].surface for i in part)
        for i in part:
            if _is_no_token(toks[i]): continue
            pos1 = toks[i][0].feature.pos1
            if pos1 not in ('名詞', '接頭辞', '接尾辞'): return None, 'PLACEMENT_PART_NOT_NP:' + pos1
            if toks[i][0].feature.pos2 == '数詞': return None, 'PLACEMENT_PART_MARKER:quant'
        determiner, lead = None, first                  # K97 D1: a demonstrative just before the part is not part of it; what stands before it decides the isolation
        if first > 0 and _is_demonstrative_token(toks[first - 1]) and toks[first - 1][2] == toks[first][1]:
            determiner, lead = toks[first - 1][0].surface, first - 1
        j = lead - 1
        isolated = j < 0 or toks[j][0].feature.pos1 == '補助記号' or is_covered(j)
        if not isolated:
            while j >= 0 and toks[j][0].feature.pos1 == '助詞': j -= 1
            isolated = 0 <= j < lead - 1 and is_covered(j)
        if not isolated: return None, 'PLACEMENT_PART_NOT_ISOLATED'
        if last + 1 >= len(toks): return None, 'PLACEMENT_PART_NOT_FOLLOWED'
        after = toks[last + 1][0]
        if after.surface == '、' and after.feature.pos1 == '補助記号': particle, particle_token = '', None
        elif after.feature.pos1 == '助詞': particle, particle_token = after.surface, toks[last + 1]
        else: return None, 'PLACEMENT_PART_NOT_FOLLOWED'
        if particle_token is not None and last + 2 < len(toks) and toks[last + 2][0].feature.pos1 == '助詞':
            return None, 'PLACEMENT_PART_PARTICLE:' + particle + toks[last + 2][0].surface
        for token in [toks[i] for i in part] + ([particle_token] if particle_token is not None else []):
            kind = _w3b1_marker(token)
            if kind: return None, 'PLACEMENT_PART_MARKER:' + kind
        if connective: return None, 'PLACEMENT_PART_MARKER:conn'
        start, end = toks[first][1], toks[last][2]
        head, relational = no_phrase_head(toks, start, end)
        if relational: return None, relational
        noun, why = placement_type(ask(head or surface), adjunct=True)
        if why: return None, '%s:part:%s' % (why, surface)
        role_name = PLACEMENT_PART_CONSTRUCTIONS.get((noun, particle))
        if role_name is None: return None, 'PLACEMENT_PART_NO_ROLE:%s:%s' % (noun, particle or '∅')
        if role_name in basis: return None, 'PLACEMENT_DUPLICATE_ROLE:' + role_name
        label = 'placement_direct%s:%s' % ('_head' if head else '', noun)
        new_roles.append(Role(role_name, surface, Span(clause.predicate_span.source, start, end, text[start:end]), label))
        basis[role_name] = label
        if determiner: flags[role_name] = {'determiner': determiner}
    typed = {'mode': 'extra', 'roles': new_roles, 'predicate_basis': None, 'role_basis': basis,
             'clause': replace(clause, roles=clause.roles + tuple(new_roles), unsupported=())}
    if flags: typed['role_flags'] = flags
    return typed, None


def _s4_demonstrative_roles(text, toks, clause, query, role_map, covered):
    """K97 D2: no content run is left, and the reader's `unrepresented source content` is only that a demonstrative stands before a role it typed (the span of the role
    does not hold it). The roles after a demonstrative are marked, when the name the entry writes for them is in the table of types of the event cross and the type of
    their value (the head of `X no Y`) fits it by `placement_fit`; nothing else is added. (typed, None) or (None, reason)."""
    from .event_cross import EXPECTED_TYPES

    def before(role):
        i = next((i for i, t in enumerate(toks) if t[1] == role.span.start), None)
        return i - 1 if i is not None and i > 0 and _is_demonstrative_token(toks[i - 1]) and toks[i - 1][2] == role.span.start else None
    marked = [(role, before(role)) for role in clause.roles if before(role) is not None]
    if not marked: return None, 'PLACEMENT_PART_NONE'
    named = []
    for role, k in marked:
        name = 'agent' if role.name == 'agent' else role_map.get(role.name)
        if name is None: return None, 'PLACEMENT_DETERMINER_ROLE_UNTYPED:%s' % role.name
        if name not in EXPECTED_TYPES: return None, 'PLACEMENT_DETERMINER_ROLE_UNTYPED:%s' % name
        named.append((role, k, name))
    tagged = tag([w for w, _, _ in toks], [a for _, a, _ in toks])
    demonstratives = [(toks[k][1], toks[k][2]) for _, k, _ in named]
    if _uncovered_nominals(toks, covered + demonstratives): return None, 'PLACEMENT_DETERMINER_NOT_BOUNDED'
    for role in clause.roles:
        ds = next((toks[k][1] for r, k, _ in named if r is role), role.span.start)
        if not phrase_bounded(tagged, ds, role.span.end): return None, 'PLACEMENT_DETERMINER_NOT_BOUNDED'
    ask = _Asker(query)
    basis, flags = {}, {}
    for role, k, name in named:
        value = role.span.text
        head, relational = no_phrase_head(toks, role.span.start, role.span.end)
        if relational: return None, relational
        kind, payload = placement_fit(ask(head or value), EXPECTED_TYPES[name], adjunct=name in ('time', 'place'))
        if kind == 'mismatch': return None, 'PLACEMENT_TYPE_MISMATCH:determiner:%s:%s' % (name, payload[0])
        if kind is None: return None, '%s:%s:%s' % (payload, name, value)
        if name in basis: return None, 'PLACEMENT_DUPLICATE_ROLE:' + name
        basis[name] = 'placement_%s%s:%s' % (kind, '_head' if head else '', '+'.join(payload))
        flags[name] = {'determiner': toks[k][0].surface}
    return {'mode': 'extra', 'roles': [], 'predicate_basis': None, 'role_basis': basis, 'role_flags': flags, 'clause': replace(clause, unsupported=())}, None


# ===================================================================================================================================
# W3-b3: embedded crosses. docs/READING_SOUNDNESS.md section 10C (K114-K122).
# Nothing above this line is changed. What is added: the closed list of cuts (a table of parts of speech and forms: no list of words), the pure functions that decide, from a
# SNAPSHOT of the tokens (their features copied at once: the nodes of the tagger are valid only until the next parse), the groups of predicates, the cuts, the gates that need no
# question, the text of each clause and the head noun phrase of a relative clause. The entry (semantic_read.py) reads each clause with its own rules and asks the placement.
# ===================================================================================================================================
from collections import namedtuple as _w3b3_namedtuple

# K115 / K119. kind, the tokens of its connective, 'finite' | 'nonfinite' (how the text of the clause before it is written), the relation of the convention (or the name of the edge the
# diagnosis holds), and whether the clause before it keeps the tense the entry read (False: null, convention section 5).
W3B3_CUTS = (
    ('relative', (), 'finite', 'relative', True),
    ('ので', ('ので',), 'finite', 'cause', True),
    ('から', ('から',), 'finite', 'cause', True),
    ('が', ('が',), 'finite', 'contrast', True),
    ('けれど', ('けれど', 'けれども', 'けど'), 'finite', 'contrast', True),
    ('と', ('と',), 'finite', 'condition', True),
    ('なら', ('なら',), 'finite', 'condition', False),
    ('ば', ('ば',), 'nonfinite', 'condition', False),
    ('たら', ('たら', 'だら'), 'nonfinite', 'condition', False),
    ('ても', ('ても', 'でも'), 'nonfinite', 'concession', False),
    ('ながら', ('ながら',), 'nonfinite', 'simultaneous', False),
    ('て', ('て', 'で'), 'nonfinite', 'TE_UNDETERMINED', False),
    ('並列', ('、',), 'nonfinite', 'PARALLEL_UNDETERMINED', False),
)
W3B3_QUOTE_VERBS = ('言う', '思う', '話す', '伝える', '聞く', '尋ねる', '答える', '考える')          # K119: W1-a4's list of verbs of quotation, copied
W3B3_PERMISSION_WORDS = ('いい', 'よい', 'かまう')                                               # K115: ても + one of these is a permission, not a cut (W1-a4's K42, copied)
W3B3_OUTER_TYPES = ('ABSTRACT', 'EVENT_ACT', 'STATE_PROPERTY')                                    # K118 8: a head of these types may be a content clause / an outer relation
W3B3_QUOTE_TYPES = ('P_COMMUNICATE', 'P_COGNITION', 'P_CREATE', 'P_PERCEIVE')                      # K119: a main predicate of these types makes a quotation と possible
W3B3_REASON_NAMES = ('W3B3_NOT_TRIGGERED', 'CLAUSE_SCOPE_NOT_LISTED', 'CLAUSE_SCOPE_AMBIGUOUS', 'CLAUSE_FORM_NOT_READ', 'CLAUSE_TOKENS_DIFFER', 'CLAUSE_UNREAD',
                     'HEAD_ROLE_UNDETERMINED', 'HEAD_NOT_IN_HOST', 'RELATION_TYPE_UNDETERMINED', 'ELLIPSIS_UNDETERMINED')
W3B3_PRODUCED_WITH_PLACEMENT = {                                                                   # K121: what the entry writes with a placement that it never wrote without one
    'relation:relative': 'with a placement, when K118 holds; the relation holds the key `head`',
    'relation:cause': 'with a placement only (the connectives of the cut table that mean a cause)',
    'relation:contrast': 'with a placement only (the connectives that mean a contrast)',
    'relation:concession': 'with a placement only (the connective that means a concession)',
    'relation:condition': 'with a placement only (the connectives that mean a condition)',
    'relation:simultaneous': 'with a placement only (the connective that means simultaneity)',
    'relation_key:head': 'only in a relation of type relative: from_role, to_role; outside the keys of the convention',
    'tense:null': 'the clause before the connectives whose clause the convention writes with a null tense',
}
W3B3Tok = _w3b3_namedtuple('W3B3Tok', 'surface start end pos1 pos2 pos3 lemma ctype cform base marker is_pred')


def w3b3_snapshot(toks, preds):
    """The tokens of `_tokens` as plain values (copied at once), with the mark of `_w3b1_marker` and whether the entry counts the token as a head of a predicate (`preds`)."""
    out = []
    for (w, a, b), p in zip(toks, preds):
        f = w.feature
        out.append(W3B3Tok(w.surface, a, b, f.pos1, f.pos2, f.pos3, getattr(f, 'lemma', None) or w.surface, f.cType or '', f.cForm or '', _base(w), _w3b1_marker((w, a, b)), bool(p)))
    return tuple(out)


def _w3b3_at(snap, i):
    return snap[i] if 0 <= i < len(snap) else None


def _w3b3_aspect_te(snap, i):
    """A te / de particle between a verb and a verb that is not independent (the progressive, the completive): inside the predicate, not a connective."""
    t, nxt, prev = snap[i], _w3b3_at(snap, i + 1), _w3b3_at(snap, i - 1)
    return (t.pos1 == '助詞' and t.pos2 == '接続助詞' and t.surface in ('て', 'で') and prev is not None and prev.pos1 == '動詞'
            and nxt is not None and nxt.pos1 == '動詞' and nxt.pos2 == '非自立可能')


def w3b3_groups(snap):
    """K115: the groups of predicate tokens (lists of indices): a token that the entry counts as a head of a predicate joins the group of the token before it (a compound verb), or of
    the token two before it when a te / de particle stands between. The copula that follows a nominalising particle is the connective of a cut, not a predicate."""
    groups = []
    for i, t in enumerate(snap):
        if not t.is_pred: continue
        if t.pos1 == '助動詞' and t.lemma == 'だ' and i > 0 and snap[i - 1].pos2 == '準体助詞': continue      # the copula of a nominalised predicate (the で of ので): the connective, not a predicate
        if groups and groups[-1][-1] == i - 1: groups[-1].append(i)
        elif groups and i >= 2 and snap[i - 1].pos1 == '助詞' and snap[i - 1].surface in ('て', 'で') and groups[-1][-1] == i - 2: groups[-1].append(i)
        else: groups.append([i])
    return groups


def _w3b3_comma(snap, i):
    t = _w3b3_at(snap, i)
    return t is not None and t.pos1 == '補助記号' and t.pos2 == '読点'


def _w3b3_cut(kind, snap, tokens, a_end, aux_before=False, comma=None):
    row = next(r for r in W3B3_CUTS if r[0] == kind)
    last = max(list(tokens) + ([comma] if comma is not None else []) + [a_end])
    connective = ''.join(snap[i].surface for i in tokens) if tokens else (snap[comma].surface if comma is not None else '')
    return {'kind': kind, 'connective': connective, 'tokens': tuple(tokens), 'comma': comma, 'a_end': a_end, 'b_start': last + 1, 'aux_before': aux_before,
            'clause_kind': row[2], 'relation': row[3], 'tense_kept': row[4]}


def w3b3_unlisted(snap):
    """K115: the forms outside the list, as the surface of what stands there (nominaliser + ni, te + kara, an auxiliary stem after a verb, a time noun before which a verb stands)."""
    out = []
    for i, t in enumerate(snap):
        nxt, prev = _w3b3_at(snap, i + 1), _w3b3_at(snap, i - 1)
        if t.pos1 == '助詞' and t.pos2 == '準体助詞' and t.surface == 'の' and nxt is not None and nxt.pos1 == '助詞' and nxt.pos2 == '格助詞' and nxt.surface == 'に':
            out.append(t.surface + nxt.surface)
        elif t.pos1 == '助詞' and t.pos2 == '接続助詞' and t.surface in ('て', 'で') and nxt is not None and nxt.pos1 == '助詞' and nxt.pos2 == '格助詞' and nxt.surface == 'から':
            out.append(t.surface + nxt.surface)
        elif t.pos2 == '助動詞語幹' and prev is not None and prev.pos1 in ('動詞', '助動詞'):
            out.append(t.surface)
        elif (t.pos1 in ('名詞', '接尾辞') and t.pos3 in W3B2_HEAD_RELATIONAL_POS3 and prev is not None
              and ((prev.pos1 == '動詞' and prev.cform.startswith(('終止形', '連体形'))) or (prev.pos1 == '助動詞' and prev.lemma == 'た' and prev.cform.startswith('連体形')))):
            out.append(t.surface)
    return out


def w3b3_cuts(snap):
    """K115: every cut of the closed list, found by the part of speech and the form of the token and of its neighbours. A list of dicts (see `_w3b3_cut`)."""
    cuts = []
    n = len(snap)
    for i, t in enumerate(snap):
        prev, nxt = _w3b3_at(snap, i - 1), _w3b3_at(snap, i + 1)
        after = i + 1
        verb_or_ta = prev is not None and (prev.pos1 == '動詞' or (prev.pos1 == '助動詞' and prev.lemma == 'た'))
        verb_or_aux = prev is not None and prev.pos1 in ('動詞', '助動詞')
        aux_before = prev is not None and prev.pos1 == '助動詞'
        conj = t.pos1 == '助詞' and t.pos2 == '接続助詞'
        # relative: a verb (the same form as the final one) or verb + た (attributive), then a noun
        if t.pos1 == '動詞' and t.cform.startswith(('終止形', '連体形')) and nxt is not None and nxt.pos1 in ('名詞', '接頭辞'):
            aspect = prev is not None and prev.pos1 == '助詞' and prev.surface in ('て', 'で') and t.pos2 == '非自立可能'
            if not aspect and nxt.pos3 not in W3B2_HEAD_RELATIONAL_POS3: cuts.append(_w3b3_cut('relative', snap, (), i))
        if (t.pos1 == '助動詞' and t.lemma == 'た' and t.cform.startswith('連体形') and prev is not None and prev.pos1 == '動詞' and prev.cform.startswith('連用形')
                and nxt is not None and nxt.pos1 in ('名詞', '接頭辞') and nxt.pos3 not in W3B2_HEAD_RELATIONAL_POS3):
            before = _w3b3_at(snap, i - 2)
            aspect = before is not None and before.pos1 == '助詞' and before.surface in ('て', 'で') and prev.pos2 == '非自立可能'
            if not aspect: cuts.append(_w3b3_cut('relative', snap, (), i))
        # ので: 準体助詞 の + 助動詞 で
        if (t.pos1 == '助詞' and t.pos2 == '準体助詞' and t.surface == 'の' and nxt is not None and nxt.pos1 == '助動詞' and nxt.lemma == 'だ' and nxt.surface == 'で' and verb_or_ta):
            comma = i + 2 if _w3b3_comma(snap, i + 2) else None
            cuts.append(_w3b3_cut('ので', snap, (i, i + 1), i - 1, comma=comma))
        if conj and t.surface == 'から' and verb_or_ta:
            cuts.append(_w3b3_cut('から', snap, (i,), i - 1, comma=i + 1 if _w3b3_comma(snap, i + 1) else None))
        if conj and t.surface == 'が':
            cuts.append(_w3b3_cut('が', snap, (i,), i - 1, comma=i + 1 if _w3b3_comma(snap, i + 1) else None))
        if conj and t.lemma == 'けれど':
            tokens = (i, i + 1) if nxt is not None and nxt.pos1 == '助詞' and nxt.pos2 == '係助詞' and nxt.surface == 'も' else (i,)
            cuts.append(_w3b3_cut('けれど', snap, tokens, i - 1, comma=tokens[-1] + 1 if _w3b3_comma(snap, tokens[-1] + 1) else None))
        if (conj and t.surface == 'と' and prev is not None
                and ((prev.pos1 == '動詞' and prev.cform.startswith('終止形')) or (prev.pos1 == '助動詞' and prev.lemma in ('た', 'ない') and prev.cform.startswith('終止形')))):
            cuts.append(_w3b3_cut('と', snap, (i,), i - 1, comma=i + 1 if _w3b3_comma(snap, i + 1) else None))
        if (t.pos1 == '助動詞' and t.lemma == 'だ' and t.surface == 'なら' and t.cform.startswith('仮定形') and prev is not None
                and prev.pos1 == '動詞' and prev.cform.startswith('終止形')):
            cuts.append(_w3b3_cut('なら', snap, (i,), i - 1, comma=i + 1 if _w3b3_comma(snap, i + 1) else None))
        if conj and t.surface == 'ば' and verb_or_aux and prev.cform.startswith('仮定形'):
            cuts.append(_w3b3_cut('ば', snap, (i,), i - 1, aux_before=aux_before, comma=i + 1 if _w3b3_comma(snap, i + 1) else None))
        if t.pos1 == '助動詞' and t.lemma == 'た' and t.surface in ('たら', 'だら') and t.cform.startswith('仮定形') and verb_or_aux:
            cuts.append(_w3b3_cut('たら', snap, (i,), i - 1, aux_before=aux_before, comma=i + 1 if _w3b3_comma(snap, i + 1) else None))
        if conj and t.surface in ('て', 'で') and nxt is not None and nxt.pos1 == '助詞' and nxt.pos2 == '係助詞' and nxt.surface == 'も' and verb_or_aux:
            follower = _w3b3_at(snap, i + 2)
            permission = follower is not None and (follower.base in W3B3_PERMISSION_WORDS or follower.surface in W3B3_PERMISSION_WORDS)
            if not permission:
                cuts.append(_w3b3_cut('ても', snap, (i, i + 1), i - 1, aux_before=aux_before, comma=i + 2 if _w3b3_comma(snap, i + 2) else None))
        if conj and t.surface == 'ながら' and verb_or_aux:
            cuts.append(_w3b3_cut('ながら', snap, (i,), i - 1, aux_before=aux_before, comma=i + 1 if _w3b3_comma(snap, i + 1) else None))
        if conj and t.surface in ('て', 'で') and verb_or_aux and not _w3b3_aspect_te(snap, i):
            if nxt is not None and (_w3b3_comma(snap, after) or nxt.pos1 in ('名詞', '代名詞', '副詞', '連体詞', '接頭辞')):
                cuts.append(_w3b3_cut('て', snap, (i,), i - 1, aux_before=aux_before, comma=i + 1 if _w3b3_comma(snap, i + 1) else None))
        if t.pos1 == '動詞' and t.cform.startswith('連用形-一般') and _w3b3_comma(snap, i + 1):
            cuts.append(_w3b3_cut('並列', snap, (), i, comma=i + 1))
    return cuts


def w3b3_scope(snap):
    """K114 2: (cut, None) for a sentence of exactly two groups of predicates and exactly one cut of the list (the cut is a dict with `groups`: the group before and the group after), else
    (None, the reason). Decided by the tokens alone; no question to the placement."""
    groups = w3b3_groups(snap)
    if len(groups) != 2: return None, 'W3B3_NOT_TRIGGERED:groups=%d' % len(groups)
    unlisted = w3b3_unlisted(snap)
    if unlisted: return None, 'CLAUSE_SCOPE_NOT_LISTED:' + unlisted[0]
    cuts = w3b3_cuts(snap)
    if len(cuts) != 1: return None, 'CLAUSE_SCOPE_AMBIGUOUS:cuts=%d' % len(cuts)
    cut = cuts[0]
    before = [g for g in groups if g[-1] <= cut['a_end']]
    after = [g for g in groups if g[0] >= cut['b_start']]
    if len(before) != 1 or len(after) != 1: return None, 'W3B3_NOT_TRIGGERED:groups_not_split'
    return dict(cut, groups=(before[0], after[0])), None


_W3B3_QUOTE_MARKS = ('「', '」', '『', '』', '“', '”', '"')


def w3b3_form_gate(snap, cut):
    """K116 1: the gates of the whole sentence (no position: a mark in either clause stops it): an imperative, a quotation mark, a question, a connective outside the cut. The reason or None.
    `cut` is the cut dict, or None (then no token is set aside)."""
    aside = set()
    if cut is not None:
        aside = set(cut['tokens'])
        if cut['comma'] is not None: aside.add(cut['comma'])
    if any(t.cform.startswith('命令形') for t in snap): return 'CLAUSE_FORM_NOT_READ:imperative'
    if any(ch in t.surface for t in snap for ch in _W3B3_QUOTE_MARKS): return 'CLAUSE_FORM_NOT_READ:quote'
    if any(t.surface in ('？', '?') or (t.pos1 == '助詞' and t.pos2 == '終助詞' and t.surface == 'か') for t in snap): return 'CLAUSE_FORM_NOT_READ:question'
    for i, t in enumerate(snap):
        if i in aside or t.marker != 'conn': continue
        if _w3b3_aspect_te(snap, i): continue
        return 'CLAUSE_FORM_NOT_READ:connective_outside_cut'
    return None


def w3b3_focus_gate(snap, cut):
    """Section 10C, 4th round (review r3, M1-r3): the gate (12) of K122, after the ellipsis (11) and just before "read". The reason or None.
    A particle of the focus or adverbial sub-class (the tagger's pos2 kakari-joshi and fuku-joshi, decided by the part of speech, not by the surface) anywhere in the sentence stops the two-clause path,
    unless it is (a) a token of the connective of the cut (the focus particle that ends a concessive connective) or (b) the topic marker right after a noun or pronoun (the form K120 uses).
    So a focus or adverbial particle stacked on a case particle is never read: the entry reads the single clause and drops it, and the output has no field for it.
    No list of particles: the sub-class decides. The rule is registered in docs/READING_SOUNDNESS.md, change record of the 4th round; the position is in review-impl/W3-b3-2/plan.md section 3.
    (ASCII only: the test of the section of this file scans every non-ASCII literal, docstrings included.)"""
    aside = set(cut['tokens'])
    for i, t in enumerate(snap):
        if i in aside or t.pos1 != '助詞' or t.pos2 not in ('係助詞', '副助詞'): continue
        prev = _w3b3_at(snap, i - 1)
        if t.surface == 'は' and prev is not None and prev.pos1 in ('名詞', '代名詞'): continue
        return 'CLAUSE_FORM_NOT_READ:focus_particle'
    return None

def _w3b3_phrase_particle(t):
    return t.pos1 == '助詞' and t.pos2 not in ('接続助詞', '準体助詞') and not (t.pos2 == '格助詞' and t.surface == 'の')


def w3b3_phrases(snap, lo, hi):
    """K116 2: the tokens [lo, hi) cut after a run of particles (a connecting no does not end a phrase). Each phrase: lo, hi, plo (where its particles begin) and particle (the surface
    of the run, None when the phrase has none)."""
    out, start, i = [], lo, lo
    while i < hi:
        if _w3b3_phrase_particle(snap[i]):
            j = i
            while j < hi and _w3b3_phrase_particle(snap[j]): j += 1
            out.append({'lo': start, 'hi': j, 'plo': i, 'particle': ''.join(snap[k].surface for k in range(i, j))})
            start = i = j
        else:
            i += 1
    if start < hi: out.append({'lo': start, 'hi': hi, 'plo': hi, 'particle': None})
    return out


def _w3b3_topic(p):
    return p['particle'] is not None and p['particle'].endswith('は')


def _w3b3_broken(phrases):
    return sum(1 for p in phrases if p['particle'] == 'が') >= 2 or sum(1 for p in phrases if p['particle'] == 'を') >= 2


def w3b3_sides(snap, cut):
    """The phrases of the part before the predicate of the first clause and of the part before the predicate of the second clause."""
    ga, gb = cut['groups']
    return w3b3_phrases(snap, 0, ga[0]), w3b3_phrases(snap, cut['b_start'], gb[0])


def w3b3_unique(snap, cut):
    """K116 3-5: the reason (CLAUSE_SCOPE_AMBIGUOUS:...) or None. The alternative cuts are counted by structure only (a subject marker or an object marker repeated breaks a clause; no other particle does)."""
    a_phr, b_phr = w3b3_sides(snap, cut)
    if cut['kind'] == 'relative':
        if any(_w3b3_topic(p) for p in a_phr): return 'CLAUSE_SCOPE_AMBIGUOUS:topic_in_relative'
        pa = a_phr
    else:
        if any(_w3b3_topic(p) for p in b_phr) or any(_w3b3_topic(p) for p in a_phr[1:]): return 'CLAUSE_SCOPE_AMBIGUOUS:topic_position'
        pa = a_phr[1:] if a_phr and _w3b3_topic(a_phr[0]) else a_phr
    for k in range(1, len(pa) + 1):
        if not _w3b3_broken(pa[k:]) and not _w3b3_broken(pa[:k] + b_phr): return 'CLAUSE_SCOPE_AMBIGUOUS:alternative_cut=%d' % k
    if _w3b3_broken(pa) or _w3b3_broken(b_phr): return 'CLAUSE_SCOPE_AMBIGUOUS:noncontiguous'
    return None


def _w3b3_body_end(snap):
    last = len(snap) - 1
    while last >= 0 and snap[last].pos1 == '補助記号' and snap[last].pos2 == '句点': last -= 1
    return last


def w3b3_texts(snap, text, cut):
    """K117 1-2: ({'a', 'b', 'a_span', 'b_span', 'last'}, None) or (None, the reason). The clause before the cut is written as it is (finite) or with the dictionary form of its verb as
    written (non-finite); the clause after the cut is written as it is; the tokens of the connective and the comma are in neither."""
    ga, gb = cut['groups']
    last = _w3b3_body_end(snap)
    if cut['clause_kind'] == 'nonfinite':
        if cut['aux_before']: return None, 'CLAUSE_FORM_NOT_READ:aux_in_nonfinite'
        a = text[snap[0].start:snap[cut['a_end']].start] + snap[cut['a_end']].base + '。'
    else:
        a = text[snap[0].start:snap[cut['a_end']].end] + '。'
    b = text[snap[cut['b_start']].start:snap[last].end] + '。'
    return {'a': a, 'b': b, 'a_span': (snap[ga[0]].start, snap[cut['a_end']].end), 'b_span': (snap[gb[0]].start, snap[last].end), 'last': last}, None


def _w3b3_same_token(x, y):
    return (x.surface, x.pos1, x.pos2, x.lemma, x.cform) == (y.surface, y.pos1, y.pos2, y.lemma, y.cform)


def w3b3_tokens_match(snap, clause_snap, cut, which):
    """K117 3: the tokens of the clause text against the tokens of the sentence they come from: None, or CLAUSE_TOKENS_DIFFER:<position>. Only the last token of the clause before the cut
    may differ (a finite clause: attributive -> final; a non-finite clause: the verb is written as its dictionary form: same base, a verb)."""
    last = _w3b3_body_end(snap)
    ref = list(snap[:cut['a_end'] + 1]) if which == 'a' else list(snap[cut['b_start']:last + 1])
    end = clause_snap[-1] if clause_snap else None
    if end is None or not (end.pos1 == '補助記号' and end.pos2 == '句点'): return 'CLAUSE_TOKENS_DIFFER:end'
    body = list(clause_snap[:-1])
    if len(body) != len(ref): return 'CLAUSE_TOKENS_DIFFER:%d' % min(len(body), len(ref))
    for i, (x, y) in enumerate(zip(ref, body)):
        if _w3b3_same_token(x, y): continue
        if which == 'a' and i == len(ref) - 1:
            if cut['clause_kind'] == 'finite' and (x.surface, x.pos1, x.pos2, x.lemma) == (y.surface, y.pos1, y.pos2, y.lemma) and x.cform.startswith('連体形') and y.cform.startswith('終止形'): continue
            if cut['clause_kind'] == 'nonfinite' and x.pos1 == '動詞' and y.pos1 == '動詞' and x.base == y.base: continue
        return 'CLAUSE_TOKENS_DIFFER:%d' % i
    return None


def w3b3_head(snap, cut):
    """K118 1: the head noun phrase of a relative clause: ({'start', 'end', 'surface', 'last_pos3'}, None) or (None, the reason). The tokens from the one after the relative clause up to
    the first particle: all nouns (not numerals), prefixes or suffixes; the particle is not the connecting no; the last token is not of a class that does not decide the type of its phrase."""
    n = len(snap)
    j = cut['b_start']
    k = j
    while k < n and snap[k].pos1 != '助詞': k += 1
    head = snap[j:k]
    if not head or k >= n or k > cut['groups'][1][0] or snap[k].surface == 'の': return None, 'HEAD_ROLE_UNDETERMINED:head_not_simple'
    if any(t.pos1 not in ('名詞', '接頭辞', '接尾辞') or t.pos2 == '数詞' for t in head): return None, 'HEAD_ROLE_UNDETERMINED:head_not_simple'
    if head[-1].pos3 in W3B2_HEAD_RELATIONAL_POS3: return None, 'HEAD_ROLE_UNDETERMINED:head_relational'
    return {'start': head[0].start, 'end': head[-1].end, 'surface': ''.join(t.surface for t in head), 'particle_index': k}, None

# W3-b4: K62 v2, the second table (docs/READING_SOUNDNESS.md section 10D, K160-K165). Nothing above this line is changed: only lines are added.
# The table of W3-b1 (`TYPED_FRAMES`, `TYPED_FRAMES_NOT_READ`) keeps its value; v2 is kept under new names. The rows are (role, particle, expected types) triples that v1 already
# has; of those the new types use agent/が, patient/を, goal/へ and source/から only. No row is added for a role whose type the conventions do not decide (recipient, instrument,
# result, cause), and no row for the adjunct place/で: instrument and cause take words that are PLACE too (examples are in the docs), so the new types are not read through で
# (docs K183, table change record 3). The place/で rows of v1 (P_MOVE, P_COMMUNICATE) are v1's and stay in `TYPED_FRAMES`.
# For a particle that two roles of one predicate type could take, a row is written only when the expected types of the two are disjoint (a test checks it); the rest is not read.
# Two types registered with rows (P_CHANGE, P_CONSUME) were taken out again after the review of round 1 (docs K165, table change records 1 and 2): they are in TYPED_FRAMES_NOT_READ_W3B4.
# After the review of round 2 the place/で row of P_ACT, P_CREATE and P_EMOTION was taken out (table change record 3); the types stay, with their other rows.
# ===================================================================================================================================
TYPED_FRAMES_W3B4 = {
    'P_ACT': (
        ('agent', ('が',), ('PERSON', 'GROUP_ORG', 'ANIMAL'), 'arg'),
        ('patient', ('を',), ('PERSON', 'GROUP_ORG', 'ANIMAL', 'PLANT', 'ARTIFACT', 'SUBSTANCE_FOOD', 'EVENT_ACT', 'STATE_PROPERTY', 'ABSTRACT',
                              'INFO_LANGUAGE', 'BODY_PART', 'NATURAL_PHENOMENON', 'WORK', 'IDENTIFIER'), 'arg'),
        ('goal', ('へ',), ('PLACE',), 'arg'),
        ('source', ('から',), ('PLACE',), 'arg')),
    'P_CREATE': (
        ('agent', ('が',), ('PERSON', 'GROUP_ORG', 'ANIMAL'), 'arg'),
        ('patient', ('を',), ('PERSON', 'GROUP_ORG', 'ANIMAL', 'PLANT', 'ARTIFACT', 'SUBSTANCE_FOOD', 'EVENT_ACT', 'STATE_PROPERTY', 'ABSTRACT',
                              'INFO_LANGUAGE', 'BODY_PART', 'NATURAL_PHENOMENON', 'WORK', 'IDENTIFIER'), 'arg')),
    'P_EMOTION': (
        ('agent', ('が',), ('PERSON', 'GROUP_ORG', 'ANIMAL'), 'arg'),
        ('patient', ('を',), ('PERSON', 'GROUP_ORG', 'ANIMAL', 'PLANT', 'ARTIFACT', 'SUBSTANCE_FOOD', 'EVENT_ACT', 'STATE_PROPERTY', 'ABSTRACT',
                              'INFO_LANGUAGE', 'BODY_PART', 'NATURAL_PHENOMENON', 'WORK', 'IDENTIFIER'), 'arg')),
}


def typed_frames_v2():
    """K161: the table the plans of W3-b4 read with, composed WHEN IT IS ASKED (not copied when the module is loaded): the two types of K62 (v1, in the order of the first
    table), then the types of W3-b4 (three after the narrowing of round 2, and without place/で after the narrowing of round 3). A change of `TYPED_FRAMES` is seen at once (a test of W3-b1 sets an item of it in place)."""
    return {**TYPED_FRAMES, **TYPED_FRAMES_W3B4}


# the types that stay unread (name = a short reason; the sentences are in docs K162, `table:w3b4_not_read`)
TYPED_FRAMES_NOT_READ_W3B4 = {
    'P_GIVE': 'GA_NI_GIVER_OR_RECEIVER', 'P_PERCEIVE': 'GA_PERCEIVER_OR_PERCEIVED', 'P_EXIST': 'GA_ENTITY_OR_AGENT', 'P_POSSESS': 'GA_AGENT_OR_RECIPIENT',
    'P_STATE': 'ADJECTIVAL_PREDICATE', 'P_COGNITION': 'GA_OBJECT_OR_AGENT',
    # narrowed after the review of round 1 (docs K165, table change records 1 and 2): a misread was found for each, so the type goes back to the unread ones (no word, no rule is added)
    'P_CHANGE': 'HE_GOAL_OR_RESULT', 'P_CONSUME': 'NI_TIME_OR_PURPOSE',
}

# ===================================================================================================================================
# W3-b5: the generated frame of a predicate as a REFERENCE for a row that is read only when the frame allows it (docs/READING_SOUNDNESS.md section 10F, K200-K206).
# A row of the kind `frame_required` is a candidate only when the predicate's `frame_generated` holds the row's particle with a type the row expects, and then the row expects
# (row types) intersect (frame types). The frame never decides a type and never breaks a tie; it only allows or does not allow a row. The rows are in their own dictionary:
# `TYPED_FRAMES`, `TYPED_FRAMES_W3B4`, `typed_frames_v2()` and `TYPED_FRAMES_NOT_READ_W3B4` are not changed. No word, no surface rule.
# ===================================================================================================================================
# Narrowed on 2026-10-04 (docs 10F, table change records 1 and 2, K206): the sixteen registered rows went to two (record 1) and then to none (record 2). The frame says which types stand on a
# particle, not which role it is, and a row that read a worst case as a misread was taken out (a type whose rows are all out keeps its key with an empty tuple: the order and the keys of the
# registration stay; the mechanism below, `frame_generated` and the kind `frame_required`, stays and is tested with the registered rows put back).
TYPED_FRAMES_FRAME_REQUIRED_W3B5 = {
    'P_MOVE': (),
    'P_COMMUNICATE': (),
    'P_ACT': (),
    'P_CREATE': (),
    'P_EMOTION': (),
}
W3B5_LICENSES = ('table', 'frame_required')
W3B5_REASON_NAMES = ('FRAME_GENERATED_DOES_NOT_LICENSE', 'PLACEMENT_FRAME_GENERATED_INVALID')


def typed_frames_w3b5_rows():
    """K201: every row of the table with its kind, composed when it is asked: the rows of `typed_frames_v2()` (kind `table`) and then the rows of
    `TYPED_FRAMES_FRAME_REQUIRED_W3B5` (kind `frame_required`), as (type, role, particles, expected types, 'arg' | 'adjunct', kind)."""
    out = [(t, role, parts, exp, kind, 'table') for t, rows in typed_frames_v2().items() for (role, parts, exp, kind) in rows]
    out += [(t, role, parts, exp, kind, 'frame_required') for t, rows in TYPED_FRAMES_FRAME_REQUIRED_W3B5.items() for (role, parts, exp, kind) in rows]
    return out


def predicate_frame_generated(answer):
    """K202, the only reader of `frame_generated` of the answer of a predicate (it reads that key and the two keys inside it, nothing else of the answer):
    ('absent', None) when there is no key or its value is None; ('generated', {particle: frozenset(types)}) for a value that keeps the contract of
    docs/COARSE_PLACEMENT.md (an empty frame is well formed: it allows nothing); else (None, 'PLACEMENT_FRAME_GENERATED_INVALID:<problem>')."""
    value = answer.get('frame_generated') if isinstance(answer, dict) else None
    if value is None: return 'absent', None

    def bad(problem): return None, 'PLACEMENT_FRAME_GENERATED_INVALID:' + problem
    if not isinstance(value, dict): return bad('NOT_A_MAPPING')
    if not {'origin': 'generated'}.items() <= value.items(): return bad('ORIGIN_NOT_GENERATED')         # a field of the VALUE of frame_generated (not of the answer)
    frame = value.get('frame')
    if not isinstance(frame, dict): return bad('FRAME_NOT_A_MAPPING')
    from .coarse_types import NOUN_TYPES
    out = {}
    for particle, types in frame.items():
        if particle not in _CASE_PARTICLES_9: return bad('PARTICLE_NOT_CASE:%s' % (particle,))
        if not (isinstance(types, list) and types and all(isinstance(t, str) and t for t in types)): return bad('TYPES_NOT_A_LIST:%s' % (particle,))
        for t in types:
            if t not in NOUN_TYPES: return bad('TYPE_NOT_NOUN:%s:%s' % (particle, t))
        out[particle] = frozenset(types)
    return 'generated', out


def typed_plan_u_w3b4_ja(clause, toks, query, *, voice, written, strip, role_map):
    """K160, the plan of paths U and U3 with the second table (K62 v2): the plan of W3-b2 (`typed_plan_u_w3b2_v1_ja`), body unchanged, with two references to the table
    replaced: the types that are not read are `TYPED_FRAMES_NOT_READ_W3B4`, and the rows come from `typed_frames_v2()`. The reasons, their order and the form of `role_basis`
    are those of W3-b2 (K99)."""
    if voice != 'active': return None, 'PLACEMENT_VOICE_NOT_ACTIVE'
    if written is None or written != clause.predicate: return None, 'PLACEMENT_PREDICATE_NORMALIZED'
    ask = _Asker(query)
    answer_p = ask(written)
    ptype, why = placement_type(answer_p)
    if why: return None, '%s:predicate:%s' % (why, written)
    if not ptype.startswith('P_'): return None, 'PLACEMENT_NOT_PREDICATE_TYPE'
    if ptype in TYPED_FRAMES_NOT_READ_W3B4: return None, 'PLACEMENT_FRAME_NOT_READ:' + ptype
    rows = typed_frames_v2().get(ptype)
    if rows is None: return None, 'PLACEMENT_FRAME_NOT_READ:' + ptype
    fkind, finfo = predicate_frame(answer_p)
    if fkind is None: return None, finfo
    required_all = TYPED_FRAMES_FRAME_REQUIRED_W3B5.get(ptype, ())        # W3-b5 K200: the rows read only when the generated frame allows them
    gen = None                                                           # predicate_frame_generated(answer_p), asked once and only when a row of that kind is needed
    licensed_roles = {}                                                  # role -> 'frame_generated' for what was read through a row of that kind
    chosen, basis = [], {}
    for role in clause.roles:
        particle = _particle_after(toks, role.span.end)
        value = strip(role)
        if not value: return None, 'PLACEMENT_INVALID:EMPTY_TERM:%s' % (particle,)
        question = _w3b2_not_demonstrative(toks, role)
        if question: return None, question
        in_frame = [row for row in rows if particle in row[1]]
        required = [row for row in required_all if particle in row[1]]
        licensed = []
        if required:
            if gen is None: gen = predicate_frame_generated(answer_p)
            gkind, ginfo = gen
            if gkind is None: return None, ginfo                         # a broken frame is a reason of its own, only when a row of that kind is needed
            if gkind == 'generated':
                allowed = ginfo.get(particle, frozenset())
                licensed = [(r[0], r[1], tuple(t for t in r[2] if t in allowed), r[3]) for r in required if set(r[2]) & allowed]      # row types intersect frame types
                if not in_frame and not licensed: return None, 'FRAME_GENERATED_DOES_NOT_LICENSE:%s' % particle
                in_frame = in_frame + licensed
        if not in_frame: return None, 'PLACEMENT_PARTICLE_NOT_IN_FRAME:%s:%s' % (ptype, particle)
        if fkind == 'confirmed' and particle not in finfo: return None, 'PLACEMENT_FRAME_PARTICLE_NOT_CONFIRMED:%s:%s' % (ptype, particle)
        head, relational = no_phrase_head(toks, role.span.end - len(value), role.span.end)      # the value is the end of the role's text (a demonstrative at its start was taken off)
        if relational: return None, relational
        answer = ask(head or value)
        fits, last = [], None
        for row in in_frame:
            kind, payload = placement_fit(answer, row[2], adjunct=row[3] == 'adjunct')
            if kind in ('direct', 'all_candidates'): fits.append((row, kind, payload))
            else: last = (kind, payload)
        if not fits:
            kind, payload = last
            if kind == 'mismatch' and gen is not None and gen[0] == 'generated' and any(payload[0] in r[2] for r in required) and not any(payload[0] in r[2] for r in in_frame):
                return None, 'FRAME_GENERATED_DOES_NOT_LICENSE:%s' % particle      # a row that expects the type exists, and the frame does not allow it
            if kind == 'mismatch': return None, 'PLACEMENT_TYPE_MISMATCH:%s:%s:%s' % (ptype, particle, payload[0])
            return None, '%s:%s:%s' % (payload, particle, value)
        if len(fits) > 1: return None, 'PLACEMENT_ROLE_TIE'
        row, kind, types = fits[0]
        if any(row is r for r in licensed): licensed_roles[row[0]] = 'frame_generated'
        if fkind == 'confirmed' and not set(types) <= finfo[particle]:
            return None, 'PLACEMENT_FRAME_TYPE_NOT_CONFIRMED:%s:%s:%s' % (ptype, particle, '+'.join(types))
        if role.name not in ('recipient', 'ambiguous'):
            decided = 'agent' if role.name == 'agent' else role_map.get(role.name)
            if decided != row[0]: return None, 'PLACEMENT_READER_DISAGREES:%s:%s' % (decided or role.name, row[0])
        if row[0] in basis: return None, 'PLACEMENT_DUPLICATE_ROLE:' + row[0]
        chosen.append((row[0], role))
        basis[row[0]] = 'placement_%s%s:%s' % (kind, '_head' if head else '', '+'.join(types))
    if licensed_roles:         # the license is told to the caller only: `role_flags` is closed by event_cross (docs 10F H204), so nothing is added to the output
        return {'mode': 'override', 'roles': chosen, 'predicate_basis': 'placement_direct:' + ptype, 'role_basis': basis, 'clause': replace(clause, unsupported=()),
                'role_license': licensed_roles}, None
    return {'mode': 'override', 'roles': chosen, 'predicate_basis': 'placement_direct:' + ptype, 'role_basis': basis, 'clause': replace(clause, unsupported=())}, None


typed_plan_u_w3b2_v1_ja = typed_plan_u_w3b2_ja          # the plan of W3-b2 (rows of v1 only) stays under a name of its own: for the tests and the measurements that compare the two
# semantic_read.py is not changed: the entry looks up `R.typed_plan_u_w3b2_ja` each time it runs, so paths U and U3 read with v2 once the name is this plan
typed_plan_u_w3b2_ja = typed_plan_u_w3b4_ja

# W3-b6 (docs/READING_SOUNDNESS.md section 10I, K270, H270): stage R. The plan of W3-b4/W3-b5 stays, body unchanged, under a name of its own; the name the round-4 gate below wraps
# becomes "that plan, then stage R" (stage R itself is at the end of this file and is looked up when it is called).
import functools as _w3b6_functools
typed_plan_u_w3b4_body_ja = typed_plan_u_w3b4_ja


def _typed_plan_u_w3b6_ja(clause, toks, query, *, voice, written, strip, role_map):
    """K270: the plan of W3-b4 (`typed_plan_u_w3b4_body_ja`), then stage R on what it decided or refused (`typed_plan_u_w3b6_stage_r_ja`)."""
    return typed_plan_u_w3b6_stage_r_ja(typed_plan_u_w3b4_body_ja, clause, toks, query, voice=voice, written=written, strip=strip, role_map=role_map)


typed_plan_u_w3b4_ja = _w3b6_functools.update_wrapper(_typed_plan_u_w3b6_ja, typed_plan_u_w3b4_body_ja)


# ===================================================================================================================================
# W3-b4 round 4 (docs 10D K186, the auditor's decision 2): the gate of a focus particle right after a case particle, on the plans of paths U and U3 (the plan of
# W3-b1 and the plan of W3-b2/W3-b4). A clause whose tokens (marks of punctuation and blanks skipped) have a case particle followed by a binding or adverbial particle
# is refused: the reading would drop that particle (K180). Parts of speech and adjacency only, no list of words. Checked after the plan decided a reading, so every
# reason of a refusal before is unchanged; it can only turn a reading into a refusal. Path S4 is not gated. Nothing above this block is changed.
# ===================================================================================================================================
def typed_focus_after_case_ja(toks, clause):
    """K186: 'PLACEMENT_FOCUS_PARTICLE_AFTER_CASE:<case particle>:<particle>' for the first token of 助詞/係助詞 or 助詞/副助詞 that follows a token of 助詞/格助詞
    inside the clause (tokens of 補助記号 and 空白 between them are skipped), else None."""
    lo, hi = clause.span.start, clause.span.end
    inside = [t for t in toks if t[1] >= lo and t[2] <= hi and t[0].feature.pos1 not in ('補助記号', '空白')]
    for (w, a, b), (w2, a2, b2) in zip(inside, inside[1:]):
        if w.feature.pos1 == '助詞' and w.feature.pos2 == '格助詞' and w2.feature.pos1 == '助詞' and w2.feature.pos2 in ('係助詞', '副助詞'):
            return 'PLACEMENT_FOCUS_PARTICLE_AFTER_CASE:%s:%s' % (w.surface, w2.surface)
    return None


def _quoted_focus_after_case_reason(toks, lo, hi, text, *, separated_only=False):
    """W5-f F-1 r3 (docs 10H.e): after a case particle, skip symbols/blanks; refuse a 1-2 char symbol-bracketed fragment or a focus particle."""
    inside = [t for t in toks if t[1] >= lo and t[2] <= hi]
    for offset, (word, _start, _end) in enumerate(inside):
        if word.feature.pos1 != '助詞' or word.feature.pos2 != '格助詞': continue
        j = offset + 1
        while j < len(inside) and inside[j][0].feature.pos1 in ('補助記号', '空白', '記号'):
            opener = inside[j][0]
            if opener.feature.pos1 == '記号' or (opener.feature.pos1 == '補助記号' and opener.feature.pos2 not in ('読点', '句点', '括弧閉')):
                if opener.feature.pos2 == '括弧開':
                    k = next((k for k in range(j + 1, len(inside)) if inside[k][0].feature.pos1 == '補助記号' and inside[k][0].feature.pos2 == '括弧閉'), None)
                else:
                    k = next((k for k in range(j + 1, len(inside)) if inside[k][0].surface == opener.surface), None)
                if k is not None:
                    fragment = text[inside[j][2] - lo:inside[k][1] - lo].strip()
                    if 1 <= len(fragment) <= 2:
                        return 'PLACEMENT_QUOTED_PARTICLE_AFTER_CASE:%s' % word.surface
            j += 1
        if j >= len(inside): continue
        separated = j > offset + 1 or inside[j][1] > inside[j - 1][2]
        first = inside[j][0]
        if first.feature.pos1 == '助詞' and first.feature.pos2 in ('係助詞', '副助詞') and (separated or not separated_only):
            return 'PLACEMENT_FOCUS_PARTICLE_AFTER_CASE:%s:%s' % (word.surface, first.surface)
    return None


def typed_quoted_focus_after_case_ja(toks, clause):
    """W5-f (docs 10H): refuse a short bracketed fragment after a case particle, or a focus particle past quote symbols."""
    return _quoted_focus_after_case_reason(toks, clause.span.start, clause.span.end, clause.span.text)


def _quoted_focus_public_gate(entry, text, out):
    """W5-f r2: preserve quote-gate refusals on the public path after direct and typed reading."""
    reason = _quoted_focus_after_case_reason(_tokens(text), 0, len(text), text, separated_only=True)
    if reason is None or not out.get('readable'): return out
    unsupported = list(out.get('unsupported') or ())
    clauses, meta = out.get('clauses') or (), out.get('clause_meta') or ()
    predicate = clauses[0].get('predicate') if len(clauses) == 1 else None
    span = meta[0].get('span') if len(meta) == 1 else [0, len(text)]
    record = {'predicate': predicate, 'span': span, 'reasons': [reason]}
    if not any(reason in item.get('reasons', ()) for item in unsupported if isinstance(item, dict)):
        unsupported.append(record)
    return entry._refusal('ja', 'not_supported', [reason], unsupported)


def typed_relational_filler_ja(toks, typed):
    """W5-f r3: retracted by the auditor (2026-10-04 13:30); not called. Kept as the record of K261 (docs 10H.e)."""
    for name, role in (typed.get('roles') or ()):
        if name not in ('place', 'goal', 'source') and _particle_after(toks, role.span.end) != 'で': continue
        head = next((t[0] for t in reversed(toks) if t[1] >= role.span.start and t[2] == role.span.end), None)
        if head is None: continue
        feature = head.feature
        if (feature.pos1, feature.pos2, feature.pos3) == ('名詞', '普通名詞', '副詞可能'):
            return 'RELATIONAL_NOUN_FILLER:%s' % name
    return None


def _typed_plan_focus_gated(plan):
    """K186: the plan `plan` (same arguments), then the gate on what it decided to read. The plan itself is kept as the attribute `ungated`."""
    def gated(clause, toks, query, *, voice, written, strip, role_map):
        typed, why = plan(clause, toks, query, voice=voice, written=written, strip=strip, role_map=role_map)
        if typed is None: return typed, why
        focus = typed_focus_after_case_ja(toks, clause)
        if focus: return None, focus
        focus = typed_quoted_focus_after_case_ja(toks, clause)
        if focus: return None, focus
        return typed, why
    gated.__name__ = plan.__name__ + '_focus_gated'
    gated.ungated = plan
    return gated


typed_plan_u_w3b1_ungated_ja = typed_plan_u_ja           # the plan of W3-b1 (the function of the base commit, unchanged) under a name of its own
typed_plan_u_ja = _typed_plan_focus_gated(typed_plan_u_w3b1_ungated_ja)
typed_plan_u_w3b2_ja = _typed_plan_focus_gated(typed_plan_u_w3b4_ja)


# W1-a5: the slots of the convention that have a field (docs/READING_SOUNDNESS.md section 10G, K210-K218): the auxiliary verbs of aspect (convention 3), the floating
# quantity (convention 6) and the mark of an adverb (`flags.adverbs`). The reading entry `_read_ja` of semantic_read.py is wrapped by `w1a5_wrap` (two lines at the end of that
# file); the function it wraps is not changed. Everything is decided on a copy of the values of the tokens (the nodes of the tagger are valid until the next parse).
# Round 2 (K218, the change record of the docs section 10G): the mark of an adverb and the quantity of a noun phrase were withdrawn; the registered constants stay for the tables and the functions of the adverb gates stay and are not called.
import functools as _w1a5_functools
import sys as _w1a5_sys
import unicodedata as _w1a5_unicodedata
from collections import namedtuple as _w1a5_namedtuple
from types import SimpleNamespace as _w1a5_namespace

# K211: the auxiliary verbs of aspect are a copy of convention 3 (te-iru, te-shimau, te-oku); the table of endings is convention 5 (polarity and tense)
W1A5_ASPECT_AUX = ('居る', '仕舞う', '置く')
W1A5_ASPECT_ENDINGS = (
    ('終止形', (), '+', 'nonpast'),
    ('連用形', ('た',), '+', 'past'),
    ('連用形', ('ます',), '+', 'nonpast'),
    ('連用形', ('ます', 'た'), '+', 'past'),
    ('未然形', ('ない',), '-', 'nonpast'),
    ('未然形', ('ない', 'た'), '-', 'past'),
    ('連用形', ('ます', 'ぬ'), '-', 'nonpast'),
    ('連用形', ('ます', 'ぬ', 'です', 'た'), '-', 'past'),
)
# K212: the counters of a number of times (convention 6); the numerals of a place-value reading
W1A5_EVENT_COUNTERS = ('回', '度')
W1A5_KANJI_DIGITS = ('一', '二', '三', '四', '五', '六', '七', '八', '九')
W1A5_KANJI_UNITS = ('十', '百', '千', '万')
# K213 (withdrawn in round 2, K218: the constants stay as the registered tables, only the gate functions that are not called refer to them): the words that another field of the convention names, and the two small registered classes
W1A5_CONVENTION_ADVERBS = ('一番', '最も', 'ちょうど')
W1A5_ADVERB_CLASSES = {'modal': ('どうぞ', 'ひょっとすると', 'ひょっとしたら', 'もしかしたら'),
                       'approx': ('ほぼ', 'だいたい', '大体', 'あやうく', '危うく')}
W1A5_COMPARISON_PARTICLES = ('より', 'ほど', 'くらい', 'ぐらい')
# K215: the closed list of the reasons this section adds (after the reasons of the base entry)
W1A5_REASONS = (
    'ASPECT_NOT_IN_CONVENTION:<原形>', 'ASPECT_CHAIN_NOT_READ', 'ASPECT_ENDING_NOT_READ', 'ASPECT_CONTRACTED_NEGATION', 'ASPECT_CONTRACTED', 'ASPECT_MULTI_CLAUSE',
    'ASPECT_NOT_ON_PREDICATE', 'QUANTIFIER_TARGET_UNDETERMINED:<two|unit|time|position|particle|no_phrase|scrambled|role>', 'QUANTIFIER_VALUE_UNDETERMINED:<表層>',
    'QUANTIFIER_SCOPE_UNDETERMINED:<neg|modality|voice>', 'COMPETING_READINGS:gold_quantity', 'ADVERB_MARK_NOT_READ:<類>:<表層>', 'COMPARISON_NOT_READ', 'ADVERB_STACKED',
    'ADVERB_MAY_MODIFY_NP:<表層>', 'ADVERB_WITH_QUANTITY', 'ADVERB_SCOPE_UNDETERMINED:<neg|modality>', 'REREAD_ABSTAINS:<理由>')
W1A5_REASONS_K218 = ('QUANTIFIER_TARGET_UNDETERMINED:noun_phrase',)       # round 2: the reason added by the change record (not part of the registered table above)
W1A5_DEPTH = [0]       # > 0 while the base entry runs (also inside a clause of W3-b3): the wrapper does nothing then
W1A5_LAST = {}         # the last decision of the wrapper, for w1a5_explain_ja

_W1A5_TOKEN = _w1a5_namedtuple('_W1A5_TOKEN', 'surface pos1 pos2 pos3 cform base lemma lform start end')
_W1A5_VOICE = ('れる', 'られる', 'せる', 'させる')
_W1A5_CONTRACTED = ('てる', 'ちゃう')
_W1A5_CONTENT = ('名詞', '代名詞', '形容詞', '形状詞', '副詞', '接頭辞', '接尾辞')
_W1A5_UNREPRESENTED = 'unrepresented source content'


def _w1a5_snapshot(tokens):
    """The values of the tokens (read at once: a node of the tagger is valid until the next parse)."""
    out = []
    for word, start, end in tokens:
        f = word.feature
        out.append(_W1A5_TOKEN(word.surface, f.pos1, f.pos2, f.pos3, str(f.cForm), _base(word), getattr(f, 'lemma', None) or word.surface,
                               getattr(f, 'lForm', None) or '', start, end))
    return out


def _w1a5_hira(reading):
    return ''.join(chr(ord(ch) - 0x60) if 0x30A1 <= ord(ch) <= 0x30F6 else ch for ch in reading)


def _w1a5_aux_key(tok):
    """The base form of an auxiliary as the table of endings writes it (the past after a nasal has the base form of another word: its lemma is the one)."""
    words = {w for row in W1A5_ASPECT_ENDINGS for w in row[1]}
    return tok.base if tok.base in words else tok.lemma


# ---- K211: aspect --------------------------------------------------------------------------------------------------------------
def _w1a5_chains(toks):
    """The chains of an auxiliary verb: a verb (or a verb and an auxiliary of voice), a te / de, a verb that is not independent. {'head': index, 'aux': [indices]}."""
    aux = {}
    for i in range(2, len(toks)):
        t, c = toks[i], toks[i - 1]
        if not (t.pos1 == '動詞' and t.pos2 == '非自立可能' and c.pos1 == '助詞' and c.pos2 == '接続助詞' and c.surface in ('て', 'で')): continue
        h = i - 2
        while h >= 0 and toks[h].pos1 == '助動詞' and toks[h].base in _W1A5_VOICE: h -= 1
        if h >= 0 and toks[h].pos1 == '動詞': aux[i] = h
    chains = []
    for i in sorted(aux):
        if aux[i] in aux: continue                       # the second auxiliary of a chain
        seq = [i]
        while True:
            nxt = next((j for j in sorted(aux) if aux[j] == seq[-1]), None)
            if nxt is None: break
            seq.append(nxt)
        chains.append({'head': aux[i], 'aux': seq})
    return chains


def _w1a5_ending(toks, k):
    """(the form of the auxiliary verb at k, the base forms of the auxiliaries behind it, whether the last of them is a final form, the index that follows them)."""
    j, keys, last = k + 1, [], toks[k]
    while j < len(toks) and toks[j].pos1 == '助動詞':
        keys.append(_w1a5_aux_key(toks[j])); last = toks[j]; j += 1
    return toks[k].cform.split('-')[0], tuple(keys), last.cform.startswith('終止形'), j


def _w1a5_row(form, keys, final):
    if not final: return None
    for f, aux, polarity, tense in W1A5_ASPECT_ENDINGS:
        if f == form and aux == keys: return polarity, tense
    return None


def _w1a5_head_is_predicate(toks, h, predicate):
    t = toks[h]
    if (t.base == 'する' or t.lemma == '為る') and h > 0 and toks[h - 1].pos1 == '名詞' and toks[h - 1].surface + 'する' == predicate: return True
    return predicate in (t.base, t.lemma)


def _w1a5_aspect(toks, clauses, reread, head_gate=True):
    """K211. None (nothing to do) | ('refuse', reason) | ('ok', {'aux', 'polarity', 'tense'}). `clauses`: the clauses of the output (a reread has one)."""
    chains = _w1a5_chains(toks)
    many = len(clauses) > 1
    info = []
    for ch in chains:
        k = ch['aux'][0]
        form, keys, final, stop = _w1a5_ending(toks, k)
        reason = found = None
        if toks[k].lemma not in W1A5_ASPECT_AUX: reason = 'ASPECT_NOT_IN_CONVENTION:' + toks[k].base
        elif len(ch['aux']) > 1: reason = 'ASPECT_CHAIN_NOT_READ'
        else:
            found = _w1a5_row(form, keys, final)
            at_end = stop >= len(toks) or toks[stop].pos2 == '句点'
            if found is None or not (at_end or many): reason = 'ASPECT_ENDING_NOT_READ'
        info.append((ch, reason, found, bool(keys) and keys[0] in ('ない', 'ぬ')))
    if not many:
        for ch, reason, found, negated in info:
            if reason: return 'refuse', reason
    for i, t in enumerate(toks):
        if t.pos1 == '助動詞' and t.lemma in _W1A5_CONTRACTED:
            if reread: return 'refuse', 'ASPECT_CONTRACTED'
            nxt = toks[i + 1] if i + 1 < len(toks) else None
            if nxt is not None and nxt.pos1 == '助動詞' and (nxt.base in ('ない', 'ぬ') or nxt.lemma == 'ず' or (nxt.base == 'ます' and nxt.cform.startswith('未然形'))):
                return 'refuse', 'ASPECT_CONTRACTED_NEGATION'
    if many:
        for ch, reason, found, negated in info:
            if reason or negated: return 'refuse', 'ASPECT_MULTI_CLAUSE'
        return None
    if not info: return None
    if head_gate and (len(info) > 1 or not _w1a5_head_is_predicate(toks, info[0][0]['head'], clauses[0]['predicate'])): return 'refuse', 'ASPECT_NOT_ON_PREDICATE'
    ch, reason, found, negated = info[0]
    return 'ok', {'aux': toks[ch['aux'][0]].lemma, 'polarity': found[0], 'tense': found[1]}


def _w1a5_on_output(E, text, toks, out, record):
    """A readable output: only the aspect rule. Nothing to do -> the same object."""
    verdict = _w1a5_aspect(toks, out['clauses'], False)
    if verdict is None: return out
    if verdict[0] == 'refuse':
        record.update(path='aspect_refused', reason=verdict[1])
        return E._refusal('ja', 'not_supported', [verdict[1]], out['unsupported'])
    info = verdict[1]
    record.update(aspect=dict(info))
    clause = out['clauses'][0]
    if (clause['polarity'], clause['tense']) == (info['polarity'], info['tense']):
        record.update(path='aspect_kept')
        return out
    fixed = dict(clause); fixed['polarity'] = info['polarity']; fixed['tense'] = info['tense']
    changed = dict(out); changed['clauses'] = [fixed]
    record.update(path='aspect_corrected')
    return changed


# ---- K212: the floating quantity -----------------------------------------------------------------------------------------------
def _w1a5_is_counter(t):
    return (t.pos1 == '接尾辞' and t.pos2 == '名詞的') or (t.pos1 == '名詞' and t.pos3 == '助数詞可能')


def _w1a5_forms(toks):
    """The quantities: (first numeral index, counter index), a run of numerals and the counter that follows it."""
    forms, i, n = [], 0, len(toks)
    while i < n:
        if toks[i].pos1 == '名詞' and toks[i].pos2 == '数詞':
            j = i
            while j < n and toks[j].pos1 == '名詞' and toks[j].pos2 == '数詞': j += 1
            if j < n and _w1a5_is_counter(toks[j]):
                forms.append((i, j)); i = j + 1
            else:
                i = j
            continue
        i += 1
    return forms


def _w1a5_number(surfaces):
    """The value of the numerals (by the kind of character), or None. Digits of a place-value reading only; a value of 0 is not a quantity."""
    s = _w1a5_unicodedata.normalize('NFKC', ''.join(surfaces))
    if not s: return None
    if s.isascii() and s.isdigit(): return int(s) or None
    digits = {ch: n for n, ch in enumerate(W1A5_KANJI_DIGITS, 1)}
    units = dict(zip(W1A5_KANJI_UNITS, (10, 100, 1000, 10000)))
    if not all(ch in digits or ch in units for ch in s): return None
    total = section = pending = 0
    last = None                              # the last unit of the section (a section runs from a larger unit to a smaller one)
    for ch in s:
        if ch in digits:
            if pending: return None
            pending = digits[ch]
        elif units[ch] == 10000:
            section += pending; pending = 0
            total += (section or 1) * 10000; section = 0; last = None
        else:
            if last is not None and units[ch] >= last: return None
            section += (pending or 1) * units[ch]; pending = 0; last = units[ch]
    value = total + section + pending
    return value or None


# ---- K213 withdrawn (K218, round 2): the mark of an adverb is not made; the functions of its gates stay and are not called ------------------------------
def _w1a5_adverb_class(t):
    names = {t.surface, t.base, t.lemma, _w1a5_hira(t.lform)} - {''}
    for kind, words in W3B1_MARKERS_JA.items():             # K64: referred to, not copied
        if names & set(words): return kind
    from .semantic_read import _QUANT_SURFACES
    if names & set(_QUANT_SURFACES): return 'quant'
    if names & set(W1A5_CONVENTION_ADVERBS): return 'convention'
    for kind, words in W1A5_ADVERB_CLASSES.items():
        if names & set(words): return kind
    return None


def _w1a5_after_adverb(toks, j):
    """The index where the phrase after the adverb (and the particle that belongs to it) starts."""
    k = j + 1
    if k < len(toks) and toks[k].pos1 == '助詞' and toks[k].surface in ('と', 'に'): k += 1
    return k


def _w1a5_np_boundary(toks, role):
    inside = [t for t in toks if t.start >= role.span.start and t.end <= role.span.end]
    if not inside: return False
    first = inside[0]
    head_ok = ((first.pos1 == '名詞' and first.pos2 == '普通名詞' and first.pos3 not in ('副詞可能', '助数詞可能'))
               or (first.pos1 == '名詞' and first.pos2 == '固有名詞') or first.pos1 == '代名詞')
    return head_ok and not any(t.surface == 'の' or t.pos1 in ('連体詞', '形容詞', '形状詞', '動詞', '接頭辞') or t.pos2 == '数詞' for t in inside)


def _w1a5_adverb_gate(toks, j, frame, forms):
    """A1..A5 for the adverb at j: None or the reason."""
    t = toks[j]
    kind = _w1a5_adverb_class(t)
    if kind is not None: return 'ADVERB_MARK_NOT_READ:%s:%s' % (kind, t.surface)
    if any((x.pos1 == '助詞' and x.surface in W1A5_COMPARISON_PARTICLES) or (x.pos1 == '副詞' and x.surface == W1A5_COMPARISON_PARTICLES[0]) for x in toks):
        return 'COMPARISON_NOT_READ'
    nxt = toks[j + 1] if j + 1 < len(toks) else None
    if nxt is not None and (nxt.pos1 in ('副詞', '接続詞') or (nxt.pos2 == '読点' and j + 2 < len(toks) and toks[j + 2].pos1 == '接続詞')):
        return 'ADVERB_STACKED'
    k = _w1a5_after_adverb(toks, j)
    role = next((r for r in frame.roles if k < len(toks) and r.span.start == toks[k].start), None)
    if role is not None and not _w1a5_np_boundary(toks, role): return 'ADVERB_MAY_MODIFY_NP:' + t.surface
    if forms: return 'ADVERB_WITH_QUANTITY'
    return None


# ---- K210, K214: the trigger, the reread and the output --------------------------------------------------------------------------
def _w1a5_reread(E, text, base_out, record):
    def refuse(reason, path='reread_refused'):
        record.update(path=path, reason=reason)
        return E._refusal('ja', base_out['abstain']['kind'], list(base_out['abstain']['reasons']) + [reason], base_out['unsupported'])
    first = _w1a5_snapshot(_tokens(text))
    if not any(t.pos2 == '数詞' for t in first): return base_out
    if len(list(_sentences(text))) != 1 or text[:1].isspace(): return base_out
    view = document_view({'d': text})
    if view.unread: return base_out
    frames = [c for c in view.clauses if c.rule == 'frame']
    others = [c for c in view.clauses if c.rule != 'frame']
    if len(frames) != 1 or any(c.rule != 'gold_quantity' for c in others): return base_out
    frame = frames[0]
    if set(frame.unsupported) != {_W1A5_UNREPRESENTED}: return base_out
    raw = _tokens(text)                                       # a fresh parse after the view: the nodes are read at once
    toks = _w1a5_snapshot(raw)
    tagged = tag([w for w, a, b in raw], [a for w, a, b in raw])
    ev = next((i for i, t in enumerate(toks) if t.start == frame.predicate_span.start), None)
    if ev is None: return base_out
    roles = [(r.span.start, r.span.end) for r in frame.roles]
    if any(t.pos2 == '数詞' and any(x <= t.start and t.end <= y for x, y in roles) for t in toks): return base_out      # a numeral inside a role is the base entry's
    covered = roles + list(_predicate_coverage(raw, ev, frame.predicate))
    forms = _w1a5_forms(toks)
    form_tokens = {i for a, b in forms for i in range(a, b + 1)}
    uncovered = [i for i, t in enumerate(toks) if t.pos1 in _W1A5_CONTENT and not any(x <= t.start and t.end <= y for x, y in covered)]
    if not uncovered or any(i not in form_tokens for i in uncovered): return base_out
    for r in frame.roles:
        if not phrase_bounded(tagged, r.span.start, r.span.end): return base_out
    # ---- the trigger holds: the gates, in the order of K210 ----
    gold = [c for c in others if c.rule == 'gold_quantity']
    mine = sorted((r.name, r.span.start, r.span.end) for r in frame.roles)
    for c in gold:
        quantities = [r for r in c.roles if r.name == 'quantity']
        same = (len(forms) == 1 and len(quantities) == 1 and (c.predicate_span.start, c.predicate_span.end) == (frame.predicate_span.start, frame.predicate_span.end)
                and sorted((r.name, r.span.start, r.span.end) for r in c.roles if r.name != 'quantity') == mine
                and (quantities[0].span.start, quantities[0].span.end) == (toks[forms[0][0]].start, toks[forms[0][1]].end))
        if not same: return refuse('COMPETING_READINGS:gold_quantity')
    early = _w1a5_aspect(toks, [None], True, head_gate=False)
    if early is not None and early[0] == 'refuse': return refuse(early[1])
    key = None
    if forms:
        if len(forms) > 1: return refuse('QUANTIFIER_TARGET_UNDETERMINED:two')
        i, j = forms[0]
        value = _w1a5_number([t.surface for t in toks[i:j]])
        if value is None: return refuse('QUANTIFIER_VALUE_UNDETERMINED:' + ''.join(t.surface for t in toks[i:j]))
        pred_heads = {ev}
        if (toks[ev].base == 'する') and ev > 0 and toks[ev - 1].pos1 == '名詞' and toks[ev - 1].surface + 'する' == frame.predicate: pred_heads.add(ev - 1)
        if j + 1 not in pred_heads: return refuse('QUANTIFIER_TARGET_UNDETERMINED:position')
        if _TIME_NUMERIC_HEAD.fullmatch(''.join(t.surface for t in toks[i:j + 1])): return refuse('QUANTIFIER_TARGET_UNDETERMINED:time')
        counter = toks[j]
        before = toks[i - 1] if i else None
        record.update(quantity={'surface': ''.join(t.surface for t in toks[i:j + 1]), 'value': 'exactly:%d' % value, 'counter': counter.surface, 'key': None})
        if counter.surface in W1A5_EVENT_COUNTERS:
            if counter.surface == W1A5_EVENT_COUNTERS[1] and before is not None and before.pos2 == '格助詞' and before.surface in ('が', 'を'):
                return refuse('QUANTIFIER_TARGET_UNDETERMINED:unit')
            key = 'event'
        elif counter.pos1 == '接尾辞':
            if before is None or before.pos1 != '助詞': return refuse('QUANTIFIER_TARGET_UNDETERMINED:no_phrase')
            if not (before.pos2 == '格助詞' and before.surface in ('が', 'か', 'を')): return refuse('QUANTIFIER_TARGET_UNDETERMINED:particle')
            role = next((r for r in frame.roles if r.span.end == before.start), None)
            if role is None: return refuse('QUANTIFIER_TARGET_UNDETERMINED:no_phrase')
            if before.surface == 'が' and any(r.span.start < role.span.start and any(t.start == r.span.end and t.surface == 'を' and t.pos2 == '格助詞' for t in toks)
                                              for r in frame.roles if r is not role):
                return refuse('QUANTIFIER_TARGET_UNDETERMINED:scrambled')
        else:
            return refuse('QUANTIFIER_TARGET_UNDETERMINED:unit')
    # ---- the reread: the entry's own rules over the clause, without the tokens of the quantity (every gate of the entry is the entry's) ----
    reread_raw = _tokens(text)
    _w1a5_snapshot(reread_raw)
    masked = [t for i, t in enumerate(reread_raw) if i not in form_tokens]
    try:
        clauses, relations, meta = E._map_ja(text, masked, _w1a5_namespace(clauses=(replace(frame, unsupported=()),), unread=()), _w1a5_sys.modules[__name__])
    except E._Abstain as stop:
        return refuse('REREAD_ABSTAINS:' + stop.reason)
    if len(clauses) != 1: return refuse('REREAD_ABSTAINS:CLAUSE_COUNT')
    clause = dict(clauses[0])
    verdict = _w1a5_aspect(toks, [clause], True)
    if verdict is not None:
        if verdict[0] == 'refuse': return refuse(verdict[1])
        record.update(aspect=dict(verdict[1])); clause['polarity'] = verdict[1]['polarity']; clause['tense'] = verdict[1]['tense']
    if forms:
        if clause['polarity'] == '-': return refuse('QUANTIFIER_SCOPE_UNDETERMINED:neg')
        if clause['modality'] is not None: return refuse('QUANTIFIER_SCOPE_UNDETERMINED:modality')
        if clause['voice'] != 'active': return refuse('QUANTIFIER_SCOPE_UNDETERMINED:voice')
        if key is None: return refuse('QUANTIFIER_TARGET_UNDETERMINED:noun_phrase')       # K218 round 2: a quantity of a noun phrase is not read
        record['quantity']['key'] = key
        clause['quantifiers'] = {key: record['quantity']['value']}
    record.update(path='reread')
    return E._answer('ja', [clause], [], meta, base_out['unsupported'])


def w1a5_wrap(base):
    """The reading entry of Japanese with W1-a5 behind it (K210): the base entry runs as it is, then the rules of this section are applied to its output."""
    @_w1a5_functools.wraps(base)
    def wrapped(text, placement=None):
        if W1A5_DEPTH[0] > 0:
            return base(text, placement)
        W1A5_DEPTH[0] = 1
        try:
            out = base(text, placement)
        finally:
            W1A5_DEPTH[0] = 0
        from . import semantic_read as E
        record = {'path': 'not_triggered', 'reason': None, 'aspect': None, 'adverbs': [], 'quantity': None}
        W1A5_DEPTH[0] = 1                     # the reading below is not a reading of an entry: nothing of this section starts again inside it
        try:
            if out['readable']:
                toks = _w1a5_snapshot(_tokens(text))
                result = _w1a5_on_output(E, text, toks, out, record)
            else:
                result = _w1a5_reread(E, text, out, record)
        finally:
            W1A5_DEPTH[0] = 0
        result = _quoted_focus_public_gate(E, text, result)
        W1A5_LAST.clear(); W1A5_LAST.update(record)
        return result
    return wrapped


def w1a5_explain_ja(text, placement=None):
    """The decision of this section for `text` as the entry reads it: {'path', 'reason', 'aspect', 'adverbs', 'quantity'} (a copy)."""
    from . import semantic_read as E
    E.read(text, 'ja', placement=placement)
    return {k: (dict(v) if isinstance(v, dict) else list(v) if isinstance(v, list) else v) for k, v in W1A5_LAST.items()}


# ===================================================================================================================================
# W3-b6: the role frame of a predicate as the way to read what the table of K62 has no opinion about (docs/READING_SOUNDNESS.md section 10I, K270-K277).
# The answer of a predicate may carry `role_frame_status` and `role_frame` ({particle: [{"role", "types"}]}, contract of W3-a6 D8); `role_frame_unconfirmed` is never read.
# Stage R runs after the plan of W3-b4 (the wiring is above, next to `typed_plan_u_w3b2_ja = typed_plan_u_w3b4_ja`) and only on what that plan left to the table: a filler
# the plan decided is checked against the frame (K274), a filler the table has no opinion about is read when exactly one role declared for its particle holds its type (K273).
# No word and no surface rule: the reasons are a closed list, the kinds of the roles a closed table.
# ===================================================================================================================================
W3B6_REASON_NAMES = ('ROLE_FRAME_NOT_CONFIRMED', 'ROLE_FRAME_FILLER_NOT_DIRECT', 'ROLE_FRAME_FILLER_RELATIVE_POSITION', 'ROLE_FRAME_TYPE_NOT_DECLARED', 'ROLE_FRAME_SPLIT',
                     'ROLE_FRAME_PARTICLE_NOT_DECLARED', 'ROLE_FRAME_INVALID', 'ROLE_FRAME_TABLE_CONFLICT', 'ROLE_FRAME_MULTIPLE_FILLERS')
W3B6_ROLE_KINDS = {'agent': 'arg', 'patient': 'arg', 'goal': 'arg', 'source': 'arg', 'place': 'adjunct', 'time': 'adjunct',
                   'recipient': 'arg', 'result': 'arg', 'quotation': 'arg', 'entity': 'arg', 'value': 'arg', 'attribute': 'arg', 'causer': 'arg', 'causee': 'arg', 'experiencer': 'arg',
                   'instrument': 'adjunct', 'companion': 'adjunct', 'cause': 'adjunct', 'standard': 'adjunct', 'beneficiary': 'adjunct'}


def predicate_role_frame(answer):
    """K273, the only reader of the role frame of the answer of a predicate (it reads `role_frame_status` and `role_frame`, nothing else of the answer):
    ('absent', None) when there is no `role_frame_status`; ('not_confirmed', status) for ESTIMATED / NO_ROLE_FRAME with a null frame; ('confirmed', {particle: ((role, frozenset(types)), ...)})
    for a CONFIRMED frame that keeps the contract; else (None, 'ROLE_FRAME_INVALID:<problem>')."""
    if not isinstance(answer, dict) or 'role_frame_status' not in answer: return 'absent', None

    def bad(problem): return None, 'ROLE_FRAME_INVALID:' + problem
    status = answer['role_frame_status']
    if status not in ('CONFIRMED', 'ESTIMATED', 'NO_ROLE_FRAME'): return bad('STATUS_UNKNOWN')
    if 'role_frame' not in answer: return bad('MISSING_ROLE_FRAME')
    frame = answer['role_frame']
    if status != 'CONFIRMED':
        if frame is not None: return bad('FRAME_WITHOUT_CONFIRMED')
        return 'not_confirmed', status
    if not isinstance(frame, dict): return bad('NOT_A_MAPPING')
    from .coarse_types import FRAME_NOUN_TYPES as NOUN_TYPES      # integration of W3-a6 (auditor, 2026-10-05): a role frame may declare only the 17 frame types (D1); RELATIVE_POSITION in a frame stays invalid
    from .event_cross import ROLE_NAMES
    out = {}
    for particle, entries in frame.items():
        if particle not in _CASE_PARTICLES_9: return bad('PARTICLE_NOT_CASE:%s' % (particle,))
        if not (isinstance(entries, list) and entries): return bad('ENTRIES_NOT_A_LIST:%s' % (particle,))
        rows, seen = [], set()
        for entry in entries:
            if not isinstance(entry, dict): return bad('ENTRY_NOT_A_MAPPING:%s' % (particle,))
            if set(entry) != {'role', 'types'}: return bad('ENTRY_KEYS:%s' % (particle,))
            role, types = entry['role'], entry['types']
            if not (isinstance(role, str) and role in ROLE_NAMES): return bad('ROLE_NOT_IN_CONVENTION:%s:%s' % (particle, role))
            if not (isinstance(types, list) and types and all(isinstance(t, str) and t for t in types)): return bad('TYPES_NOT_A_LIST:%s' % (particle,))
            for t in types:
                if t not in NOUN_TYPES: return bad('TYPE_NOT_NOUN:%s:%s' % (particle, t))
            if role in seen: return bad('ROLE_DUPLICATED:%s:%s' % (particle, role))
            seen.add(role)
            rows.append((role, frozenset(types)))
        out[particle] = tuple(rows)
    return 'confirmed', out


def _w3b6_conflict(toks, pairs, basis, frame):
    """K274: the reason of a disagreement between a role the other paths decided (`pairs` of (name, role), `basis` of the plan) and the frame, else None. A disagreement is: for a type
    of the filler the frame of the particle holds in one or more roles and the role of the table is none of them (review r1 M1; the roles are joined with '+', sorted). The frame is looked up for every particle that has one (the particles of the
    subject and the object too: they are not READ by stage R, they are only CHECKED here)."""
    for name, role in pairs:
        particle = _particle_after(toks, role.span.end)
        if particle not in frame or name not in basis or basis[name].startswith('role_frame:'): continue
        for typ in _basis_types(basis[name]):
            holding = [r for r, types in frame[particle] if typ in types]
            if holding and name not in holding: return 'ROLE_FRAME_TABLE_CONFLICT:%s:%s:%s' % (particle, name, '+'.join(sorted(holding)))
    return None


def typed_plan_u_w3b6_stage_r_ja(body, clause, toks, query, *, voice, written, strip, role_map):
    """K270-K277, stage R: (typed, None) or (None, reason), the same as the plan `body` (the plan of W3-b4, called first, unchanged). What `body` refused for a reason that is not "the table has
    no opinion" is returned as it is, with no question asked; with no `role_frame_status` in the answer of the predicate nothing is done (the object `body` returned is returned)."""
    no_opinion = ('PLACEMENT_FRAME_NOT_READ:', 'PLACEMENT_PARTICLE_NOT_IN_FRAME:', 'PLACEMENT_TYPE_MISMATCH:')
    typed, why = body(clause, toks, query, voice=voice, written=written, strip=strip, role_map=role_map)
    if typed is None and not why.startswith(no_opinion): return None, why
    answer_p = query.query(written)
    if 'role_frame_status' not in answer_p: return typed, why
    kind, info = predicate_role_frame(answer_p)
    if kind is None: return None, info
    if kind == 'not_confirmed':
        return (typed, why) if typed is not None else (None, 'ROLE_FRAME_NOT_CONFIRMED:' + info)
    frame = info
    if typed is not None:                                                    # case A: the table read it; stage R only checks (K274)
        conflict = _w3b6_conflict(toks, typed['roles'], typed['role_basis'], frame)
        return (None, conflict) if conflict else (typed, why)
    ptype, _ = placement_type(answer_p)                                       # case B: the table had no opinion about something (the gates of the predicate are passed)
    fkind, finfo = predicate_frame(answer_p)
    if fkind is None: return None, finfo
    read_particles = _CASE_PARTICLES_9[2:]                                    # K271: the particles of the subject and of the object (the first two keys) are not read
    chosen, basis, by_frame = [], {}, 0
    for role in clause.roles:
        particle = _particle_after(toks, role.span.end)
        one, why1 = body(replace(clause, roles=(role,)), toks, query, voice=voice, written=written, strip=strip, role_map=role_map)
        if one is not None:                                                   # the table read this filler: what it decided stays; K274 against the frame
            name = one['roles'][0][0]
            if name in basis: return None, 'PLACEMENT_DUPLICATE_ROLE:' + name
            conflict = _w3b6_conflict(toks, one['roles'], one['role_basis'], frame)
            if conflict: return None, conflict
            chosen.append((name, role)); basis[name] = one['role_basis'][name]
            continue
        if not why1.startswith(no_opinion): return None, why1               # a gate of the filler or of the predicate: not overridden
        named = role.name not in ('recipient', 'ambiguous')
        decided = None
        if named:
            decided = 'agent' if role.name == 'agent' else role_map.get(role.name)
            if decided is None: return None, why
        else:
            if particle not in read_particles: return None, why
            if sum(1 for r in clause.roles if _particle_after(toks, r.span.end) == particle) > 1: return None, 'ROLE_FRAME_MULTIPLE_FILLERS:' + particle
        value = strip(role)
        if not value: return None, 'PLACEMENT_INVALID:EMPTY_TERM:%s' % (particle,)
        question = _w3b2_not_demonstrative(toks, role)
        if question: return None, question
        head, relational = no_phrase_head(toks, role.span.end - len(value), role.span.end)
        if relational: return None, relational
        typ, why2 = placement_type(query.query(head or value))
        if why2: return None, 'ROLE_FRAME_FILLER_NOT_DIRECT:%s:%s' % (particle, why2)
        if typ == 'RELATIVE_POSITION': return None, 'ROLE_FRAME_FILLER_RELATIVE_POSITION:' + particle
        if particle not in frame: return None, 'ROLE_FRAME_PARTICLE_NOT_DECLARED:' + particle
        holding = [r for r, types in frame[particle] if typ in types]
        if not holding: return None, 'ROLE_FRAME_TYPE_NOT_DECLARED:%s:%s' % (particle, typ)
        if len(holding) > 1: return None, 'ROLE_FRAME_SPLIT:%s:%s' % (particle, typ)
        found = holding[0]
        if named and found != decided: return None, 'ROLE_FRAME_TABLE_CONFLICT:%s:%s:%s' % (particle, decided, found)
        if fkind == 'confirmed':
            if particle not in finfo: return None, 'PLACEMENT_FRAME_PARTICLE_NOT_CONFIRMED:%s:%s' % (ptype, particle)
            if typ not in finfo[particle]: return None, 'PLACEMENT_FRAME_TYPE_NOT_CONFIRMED:%s:%s:%s' % (ptype, particle, typ)
        if W3B6_ROLE_KINDS[found] == 'adjunct':
            _, why3 = placement_type(query.query(head or value), adjunct=True)
            if why3: return None, 'ROLE_FRAME_FILLER_NOT_DIRECT:%s:%s' % (particle, why3)
        if found in basis: return None, 'PLACEMENT_DUPLICATE_ROLE:' + found
        chosen.append((found, role)); basis[found] = 'role_frame:%s:%s:%s' % (written, particle, typ)
        by_frame += 1
    if by_frame == 0: return None, why
    return {'mode': 'override', 'roles': chosen, 'predicate_basis': 'placement_direct:' + ptype, 'role_basis': basis, 'clause': replace(clause, unsupported=())}, None
