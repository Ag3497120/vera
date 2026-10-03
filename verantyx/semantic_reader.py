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
