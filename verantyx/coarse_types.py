"""Coarse type system for the broad, rough placement of content words (W3-a).

What lives here
---------------
* the type inventory (nouns: 17, predicates: 13) -- ids are ASCII and
  FIXED; the inventory only grows (append, never rename or re-mean);
* the boundary rules that say which type a borderline thing gets
  (written BEFORE the answer keys were written);
* the hand-written seeds: general anchors (人, 道具, 建物, 時間 ...) that a
  definition's hypernym chain can end in.  Seeds are few (<= 30 per
  noun type, <= 400 nouns in all, <= 25 per predicate type);
* the notation rules (digits + unit, dates, URLs, identifiers) -- a
  structural reading of the spelling, not a lexicon;
* the default thresholds (all counts, no weights).

Nothing here consults a trained model, a weight, an external dictionary
or an LLM.  The morphological analyser is used by the *builder* only for
word segmentation and the coarse grammatical class (pos1/pos2/orthBase).
"""
from __future__ import annotations

import re
import unicodedata
from typing import Dict, List, Optional, Sequence, Tuple

TYPES_VERSION = "1"

# --- the inventory ----------------------------------------------------------
# id -> display name.  APPEND ONLY.
NOUN_TYPES: Dict[str, str] = {
    "PERSON": "人",
    "GROUP_ORG": "集団・組織",
    "ANIMAL": "動物",
    "PLANT": "植物・菌類",
    "ARTIFACT": "人工物・道具・乗り物",
    "SUBSTANCE_FOOD": "物質・飲食物",
    "PLACE": "場所・施設・地形・建造物",
    "TIME": "時間・時点・期間",
    "QUANTITY": "数量・単位",
    "EVENT_ACT": "出来事・行為",
    "STATE_PROPERTY": "状態・性質",
    "ABSTRACT": "抽象概念",
    "INFO_LANGUAGE": "情報・文書・言葉・言語・記号",
    "BODY_PART": "身体部位・器官",
    "NATURAL_PHENOMENON": "自然現象",
    "WORK": "作品",
    "IDENTIFIER": "識別子",
}

PRED_TYPES: Dict[str, str] = {
    "P_GIVE": "授受",
    "P_MOVE": "移動",
    "P_CHANGE": "変化",
    "P_CREATE": "作成",
    "P_COMMUNICATE": "伝達",
    "P_PERCEIVE": "知覚",
    "P_EXIST": "存在",
    "P_POSSESS": "所有",
    "P_STATE": "状態",
    "P_COGNITION": "思考・認識",
    "P_EMOTION": "感情",
    "P_CONSUME": "飲食・消費",
    "P_ACT": "その他の行為",
}

#: Everything that may appear in a ``top`` list.
ALL_TYPES: Dict[str, str] = {**NOUN_TYPES, **PRED_TYPES}

#: Particle surfaces a caller may pass as ``context_role``.
ROLE_PARTICLES: Tuple[str, ...] = (
    "が", "を", "に", "で", "へ", "と", "から", "まで", "より", "の", "は", "も")

#: States a query can return.
STATES: Tuple[str, ...] = (
    "DECIDED", "MULTIPLE", "UNPLACED", "UNKNOWN", "NO_PLACEMENT")

#: Origins a result can carry.
ORIGINS: Tuple[str, ...] = ("direct", "estimated")
#: What an ESTIMATE was built on: nearness (shape / family / slot) or a generated definition.
ESTIMATE_BASES: Tuple[str, ...] = ("proximity", "generated")

#: Evidence arms (a count of one kind is never added to another kind).
ARMS: Tuple[str, ...] = (
    "notation", "seed", "definition", "title_qualifier", "alias", "paren_alias",
    "role", "hearst", "sahen", "pos_class", "frame", "morphology",
    # W3-a2 (appended): the definition read by the fallback ("X wa, Y de ari, ...")
    # and the definition sentence a model generated (a different origin: see decide_word)
    "definition_recovered", "gen_definition")


def type_ids(namespace: Optional[str] = None) -> List[str]:
    """Type ids, optionally only one namespace ('N' or 'P')."""
    if namespace == "N":
        return list(NOUN_TYPES)
    if namespace == "P":
        return list(PRED_TYPES)
    return list(ALL_TYPES)


def type_namespace(type_id: str) -> str:
    return "P" if type_id.startswith("P_") else "N"


# --- boundary rules (written before the answer keys) ------------------------
BOUNDARY_RULES: List[str] = [
    "建物・駅・空港・橋・地形・公園・寺社・城など場所として扱う物 -> PLACE",
    "乗り物（車・船・列車・航空機）・道具・機械・衣服・楽器 -> ARTIFACT",
    "会社・学校・政党・球団・軍隊（組織として）-> GROUP_ORG。"
    "建物としての学校・教会などは多義にして PLACE を足す",
    "国・都市・地域は PLACE。組織・政府としての用法がはっきりした語だけ"
    "多義で GROUP_ORG を足す",
    "料理・飲み物・食材・薬・金属・化合物 -> SUBSTANCE_FOOD",
    "病名・症状・性質・感情の名詞・色 -> STATE_PROPERTY",
    "学問分野・制度・主義・方法・理論・宗教・法律 -> ABSTRACT",
    "言語名・文字・記号・文書・単語・規格 -> INFO_LANGUAGE",
    "書籍・映画・楽曲・番組・ゲーム・絵画の題名 -> WORK",
    "「〜年」「〜月」「〜時」・日付 -> TIME。「〜個」「〜キロ」・数 -> QUANTITY",
    "URL・メールアドレス・型番・英数字コード -> IDENTIFIER",
    "天体・天気・地震・津波・波・光など自然に起きる現象 -> NATURAL_PHENOMENON",
    "手・目・臓器・骨・筋肉など身体の部分 -> BODY_PART",
    "戦争・事故・会議・大会・祭り・動作を表すサ変名詞 -> EVENT_ACT",
    "職業名・人を指す役割名 -> PERSON。人が所属する集団そのものは GROUP_ORG",
    "動詞・形容詞・形状詞は述語の型（P_ 接頭）。形容詞・形状詞は P_STATE",
]

# --- seeds (hand-written anchors) -------------------------------------------
# Each seed is a GENERAL hypernym a definition's chain can end in.  The
# words the ticket names as end-of-word traps are deliberately absent.
MAX_SEEDS_PER_NOUN_TYPE = 30
MAX_SEEDS_NOUN_TOTAL = 400
MAX_SEEDS_PER_PRED_TYPE = 25

SEEDS_NOUN: Dict[str, List[str]] = {
    "PERSON": ["人", "人物", "者", "男性", "女性", "人間", "職業", "選手", "俳優", "歌手", "作家", "政治家", "研究者", "学者", "医師", "教師", "兵士", "王", "皇帝", "声優", "芸人", "棋士", "投手"],
    "GROUP_ORG": ["組織", "団体", "企業", "会社", "政党", "軍隊", "機関", "政府", "大学", "協会", "組合", "球団", "劇団", "議会", "法人", "集団", "グループ", "部隊", "チーム", "財団", "放送局", "出版社", "学校"],
    "ANIMAL": ["動物", "哺乳類", "鳥類", "魚類", "昆虫", "爬虫類", "両生類", "甲殻類", "軟体動物", "脊椎動物", "無脊椎動物", "節足動物", "鳥", "魚", "虫", "獣", "家畜", "猛禽類", "霊長類", "貝", "犬", "猫", "馬"],
    "PLANT": ["植物", "樹木", "草", "花", "菌類", "キノコ", "種子植物", "被子植物", "裸子植物", "藻類", "木", "果樹", "多年草", "落葉樹", "常緑樹", "低木", "高木", "シダ植物", "コケ植物", "雑草", "一年草", "つる植物", "観葉植物"],
    "ARTIFACT": ["道具", "機械", "装置", "器具", "乗り物", "車両", "自動車", "船", "航空機", "兵器", "衣服", "家具", "楽器", "機器", "電子機器", "武器", "部品", "鉄道車両", "工具", "容器", "玩具", "食器"],
    "SUBSTANCE_FOOD": ["物質", "食品", "料理", "飲料", "食べ物", "化合物", "元素", "金属", "薬", "薬品", "酒", "菓子", "調味料", "液体", "気体", "鉱物", "岩石", "燃料", "野菜", "果物", "肉", "食材"],
    "PLACE": ["場所", "地域", "都市", "町", "村", "国", "県", "市", "島", "山", "川", "湖", "駅", "施設", "建物", "建築物", "地方", "首都", "道路", "空港", "港", "公園"],
    "TIME": ["時間", "時代", "期間", "日", "年", "月", "時期", "年代", "世紀", "季節", "曜日", "時刻", "時点", "日付", "年号", "元号", "暦", "週", "瞬間", "時", "週間", "祝日", "記念日"],
    "QUANTITY": ["数量", "単位", "数", "割合", "値", "量", "長さ", "重さ", "面積", "体積", "速度", "温度", "密度", "比率", "金額", "価格", "人口", "回数", "件数", "倍", "確率", "通貨", "距離"],
    "EVENT_ACT": ["出来事", "事件", "行為", "活動", "運動", "戦争", "戦い", "会議", "大会", "試合", "祭り", "行事", "儀式", "事故", "災害", "革命", "動作", "競技", "作戦", "儀礼", "戦闘", "反乱", "公演"],
    "STATE_PROPERTY": ["状態", "性質", "病気", "疾患", "症状", "特徴", "性格", "傾向", "症候群", "障害", "感染症", "色", "形", "能力", "感情", "気分", "形状", "状況", "病", "癌", "炎症", "異常", "特性"],
    "ABSTRACT": ["概念", "学問", "分野", "制度", "方法", "理論", "思想", "宗教", "法律", "技術", "原理", "考え方", "哲学", "科学", "政策", "規則", "手法", "主義", "関係", "問題", "学説", "原則", "学派"],
    "INFO_LANGUAGE": ["言語", "文字", "記号", "情報", "文書", "言葉", "単語", "表現", "名称", "用語", "文章", "書類", "データ", "規格", "符号", "方言", "語", "標識", "プロトコル", "略称", "称号", "辞書", "文法"],
    "BODY_PART": ["身体", "部位", "臓器", "骨", "筋肉", "血管", "神経", "腺", "皮膚", "骨格", "内臓", "細胞", "関節", "歯", "血液", "脳", "心臓", "胃", "肺", "指", "足", "顔", "頭"],
    "NATURAL_PHENOMENON": ["現象", "自然現象", "気象", "天体", "惑星", "恒星", "銀河", "地震", "嵐", "台風", "天気", "気象現象", "光", "波", "風", "雨", "雪", "津波", "噴火", "雷", "洪水", "彗星", "衛星"],
    "WORK": ["作品", "小説", "映画", "漫画", "書籍", "楽曲", "曲", "アルバム", "番組", "ゲーム", "テレビドラマ", "アニメ", "絵画", "雑誌", "論文", "詩", "歌", "戯曲", "著作", "シリーズ", "劇", "童話", "ビデオゲーム"],
    "IDENTIFIER": ["識別子", "型番", "コード", "番号", "品番", "略号", "識別番号", "アドレス", "URL", "ID"],
}

SEEDS_PRED: Dict[str, List[str]] = {
    "P_EXIST": ["ある", "いる", "ござる", "残る", "立つ", "座る", "休む", "住む", "おる", "暮らす", "生きる", "泊まる", "止まる", "浮かぶ", "沈む", "余る", "空く", "眠る", "漂う", "待つ", "寝る", "現れる", "隠れる", "浮く"],
    "P_MOVE": ["行く", "来る", "くる", "いく", "入る", "出る", "歩く", "戻る", "進む", "走る", "帰る", "運ぶ", "動く", "通る", "着く", "乗る", "向かう", "渡る", "降りる", "飛ぶ", "上がる", "回る", "移る", "寄る"],
    "P_CHANGE": ["なる", "変わる", "変える", "増える", "減る", "始まる", "終わる", "広がる", "落ちる", "乾く", "冷える", "溶ける", "崩れる", "消える", "増やす", "減らす", "始める", "直す", "決まる", "晴れる", "凍る", "濡れる", "湿る"],
    "P_CREATE": ["作る", "書く", "描く", "焼く", "設ける", "組み立てる", "生む", "築く", "建てる", "編む", "定める", "まとめる", "整える", "起こす", "植える", "育てる", "掘る", "縫う", "煮る", "炒める", "沸かす", "炊く", "揚げる", "蒸す"],
    "P_COMMUNICATE": ["言う", "いう", "教える", "話す", "伝える", "述べる", "呼ぶ", "答える", "尋ねる", "頼む", "願う", "誘う", "呼び出す", "求める", "語る", "告げる", "断る", "勧める", "記す", "表す", "謝る", "褒める", "名乗る", "申し込む"],
    "P_PERCEIVE": ["見る", "聞く", "見える", "聞こえる", "見つける", "探す", "確かめる", "調べる", "眺める", "気づく", "触れる", "感じる", "読み取る", "見つかる", "見直す", "見分ける", "見上げる", "見送る", "響く", "映る", "測る", "触る", "見かける"],
    "P_POSSESS": ["持つ", "含む", "保つ", "得る", "取る", "握る", "含める", "受ける", "受け取る", "失う", "備える", "抱える", "奪う", "拾う", "占める", "つかむ", "持ち帰る", "持ち上げる", "隠す", "担う", "引き継ぐ"],
    "P_GIVE": ["与える", "渡す", "贈る", "送る", "返す", "出す", "貸す", "借りる", "配る", "あげる", "もらう", "くださる", "届ける", "加える", "添える", "譲る", "預ける", "施す", "任せる", "払う", "売る", "買う"],
    "P_STATE": ["できる", "よる", "異なる", "違う", "似る", "当たる", "対する", "関する", "属する", "従う", "過ぎる", "足りる", "限る", "優れる", "基づく", "伴う", "関わる", "沿う", "合う", "超える", "満たす", "至る", "達する", "及ぶ"],
    "P_COGNITION": ["思う", "考える", "知る", "分かる", "わかる", "覚える", "忘れる", "迷う", "決める", "学ぶ", "認める", "疑う", "思い出す", "間違える", "誤る", "困る", "比べる", "悩む", "許す", "慣れる", "数える", "習う", "教わる"],
    "P_EMOTION": ["笑う", "驚く", "楽しむ", "喜ぶ", "怒る", "好む", "泣く", "慌てる", "疲れる", "楽しめる"],
    "P_CONSUME": ["使う", "食べる", "飲む", "用いる", "吸う", "着る", "履く", "使える", "噛む", "味わう", "脱ぐ", "使い分ける", "飲み込む", "吸い込む"],
    "P_ACT": ["する", "行う", "置く", "おく", "つく", "入れる", "付ける", "つける", "開ける", "閉める", "押す", "引く", "切る", "洗う", "拭く", "打つ", "守る", "試す", "働く", "遊ぶ", "戦う", "続ける", "取り除く", "集める", "並べる"],
}

# --- notation rules ----------------------------------------------------------
_NUM_CHARS = "0-9０-９〇一二三四五六七八九十百千万億兆"
_NUM = "[" + _NUM_CHARS + "]+(?:[.,，．][0-9０-９]+)*"
#: Time units (a small seed).  Anything else after a number is a counter
#: whose spelling the builder LEARNS from how often it follows a number.
TIME_UNITS: Tuple[str, ...] = (
    "年", "月", "日", "時", "分", "秒", "世紀", "年代", "曜日", "時間",
    "週間", "か月", "ヶ月", "カ月", "ケ月", "週", "時頃", "年度", "学期",
    "年間", "日間")

_RE_NUM_ONLY = re.compile("^" + _NUM + "$")
_RE_NUM_UNIT = re.compile("^(" + _NUM + ")(.{1,6})$")
_RE_ARABIC = re.compile("[0-9０-９]")
_RE_IPV4 = re.compile(r"^\d{1,3}(?:\.\d{1,3}){3}$")
_RE_ISO_DATE = re.compile(r"^\d{4}[-/.]\d{1,2}[-/.]\d{1,2}$")
_RE_CLOCK = re.compile(r"^\d{1,2}:\d{2}(?::\d{2})?$")
_RE_ERA = re.compile("^(令和|平成|昭和|大正|明治|慶応|西暦|紀元前)[" + _NUM_CHARS + "元]+(?:年|世紀)")
_RE_YMD = re.compile("^[" + _NUM_CHARS + "]+年[" + _NUM_CHARS + "]+月(?:[" + _NUM_CHARS + "]+日)?$")
_RE_HM = re.compile("^(?:午前|午後)?[" + _NUM_CHARS + "]+時(?:半|[" + _NUM_CHARS + "]+分)?(?:頃)?$")
_RE_MD = re.compile("^[" + _NUM_CHARS + "]+月[" + _NUM_CHARS + "]+日$")
_RE_URL = re.compile(r"^(?:https?|ftp)://\S+$|^www\.\S+\.\S+$")
_RE_EMAIL = re.compile(r"^[\w.+-]+@[\w-]+(?:\.[\w-]+)+$")
_RE_CODE = re.compile(r"^(?=.*[A-Za-z])(?=.*[0-9])[A-Za-z0-9]+(?:[-_./][A-Za-z0-9]+)*$")
_RE_VERSION = re.compile(r"^(?:[vV]\d+(?:\.\d+)+|\d+(?:\.\d+){2,})$")


def _nfkc(s: str) -> str:
    return unicodedata.normalize("NFKC", s)


def notation_type(term: str, counters: Optional[Sequence[str]] = None
                  ) -> Optional[Tuple[str, str]]:
    """Read the SPELLING of ``term``: (type_id, rule_name) or None.

    ``counters`` is the set of counter-unit strings the builder learned
    from the material (a unit that follows a number often enough).
    Digits alone are QUANTITY; digits + a time unit, a date, a clock time
    are TIME; digits + a learned counter are QUANTITY; URL, e-mail,
    letter+digit codes and version strings are IDENTIFIER.
    """
    if not term:
        return None
    t = _nfkc(term).strip()
    if not t:
        return None
    if _RE_URL.match(t) or _RE_EMAIL.match(t):
        return ("IDENTIFIER", "url_or_mail")
    if _RE_ISO_DATE.match(t) or _RE_CLOCK.match(t):
        return ("TIME", "date_or_clock")
    if (_RE_ERA.match(t) or _RE_MD.match(t) or _RE_YMD.match(t)
            or _RE_HM.match(t)):
        return ("TIME", "era_or_date_or_clock")
    if _RE_IPV4.match(t) or _RE_VERSION.match(t):
        return ("IDENTIFIER", "version_or_address")
    if _RE_NUM_ONLY.match(t):
        return ("QUANTITY", "number")
    if counters:
        # a learned unit after Arabic digits is read BEFORE the alphanumeric-code rule
        # (digits + a unit is a quantity); a letters-first code does not start with digits
        m0 = _RE_NUM_UNIT.match(t)
        if (m0 and m0.group(2) in counters and m0.group(2) not in TIME_UNITS
                and _RE_ARABIC.search(m0.group(1)) and m0.group(1)[0] in "0123456789"):
            return ("QUANTITY", "number+counter")
    if _RE_CODE.match(t):
        return ("IDENTIFIER", "alnum_code")
    m = _RE_NUM_UNIT.match(t)
    if m:
        unit = m.group(2)
        if unit in TIME_UNITS:
            return ("TIME", "number+time_unit")
        # a learned counter counts only after an ARABIC number: kanji numeral +
        # a counter-looking unit is as often an ordinary word (a troupe, a region)
        if counters and unit in counters and _RE_ARABIC.search(m.group(1)):
            return ("QUANTITY", "number+counter")
    return None


# --- default thresholds (counts, never weights) ------------------------------
DEFAULT_CONFIG: Dict[str, object] = {
    # builder: segmentation / material
    "min_seen": 3,              # a word seen this often is a "seen in material" word
    "max_word_chars": 12,
    "max_chain_depth": 4,       # hypernym chain rounds
    "min_suffix_chars": 2,      # a hypernym may fall back to a right unit this long
    # definition / alias arm: an arm is "met" at this top-type count
    "def_min": 1,
    "alias_min": 1,
    "paren_alias_min": 1,       # "X (Y, ...)" lead: Y is another spelling of X (an arm of its own)
    "hearst_min": 2,            # hypernym pairs "AやBなどのY": pairs needed for the top type
    "hearst_min_share_pct": 70,
    "role_min_sources": 2,      # role arms decide only when this many sources meet (agreeing)
    "qual_min": 999,              # "X (qualifier)" articles: a type counts from this many
    "ctx_min_lift_pct": 300,    # a context must favour the type this much over its base rate
    "est_ctx_min_lift_pct": 300,
    "est_ctx_min_sources": 2,   # sources that must agree on the slot's type (no pooling)
    # context tables (per source)
    "ctx_min_total": 20,        # leave-one-out total for a context to count
    "ctx_min_share_pct": 70,    # top type's share of the context, in percent
    # role arm (per source)
    "role_min": 5,              # votes for the top type
    "role_min_share_pct": 70,
    # sahen (verbal noun) arm (per source)
    "sahen_min": 3,
    "sahen_min_share_pct": 30,
    # frame arm for predicates (per source)
    "frame_min_total": 30,
    # decision stages: True = a met definition/alias arm outranks role arms
    "definition_outranks_role": False,
    # query-time estimation
    "kin_min_unit_chars": 2,
    "kin_min_count": 3,
    "kin_min_share_pct": 70,
    "head_min_chars": 2,
    "est_ctx_min_total": 20,
    "est_ctx_min_share_pct": 70,
    "conflict_policy": "unknown",   # or "multiple" / "prefer_stage"
    "left_attested": True,       # the left side of a split must be an attested word/atom
    "left_recursive": True,      # ... or itself split into attested words (both parts >= 2 chars)
    # last tier: the term as a LEFT unit of placed words (a cut-off fragment).  OFF by default:
    # on dev it raised the coverage by well under one point and added one estimated error
    # (dev_whatif_kin_left.txt); a coverage rule must not add errors (review r1 M6-4).
    "kin_left": False,
    "kin_left_min_count": 10,    # ... if on: the family must be large ...
    "kin_left_min_share_pct": 90,   # ... and almost uniform (the lax 3 / 70 added 13 wrong for 2 right)
    "pos_min": 3,                # pos_class arm: adjective/adjectival-noun uses
    "kin_store_min": 3,          # unit families stored when they have this many words
    "ctx_store_min": 20,         # contexts stored when they have this many typed uses
    "counter_min": 80,          # a unit following Arabic numerals this often, IN ONE SOURCE, ...
    "counter_min_sources": 2,   # ... in at least this many sources (never pooled) is a counter
    "counter_max_chars": 3,     # a unit made of TWO morphemes ("件取得") may be this long ...
    "counter_max_chars_single": 6,   # ... a one-morpheme unit ("キロメートル", "km") up to this
    # W3-a2 round 2 (M2): a Latin-script unit ("km", "GHz") must be ONE morpheme and, in the
    # source that counts it, (a) follow numerals at least this share (%) as often as the
    # word occurs as a noun there, (b) follow at least this many different numerals.
    # Words like "of", "for", "in" (any share) and "xx" ("4xx": only a few numerals) fail.
    "counter_latin_share_pct": 10,
    "counter_latin_numerals_min": 6,
    # W3-a2 F1: stop one wrong definition from spreading down a hypernym chain
    "donor_stage_b": True,      # chain only through donors that stay DECIDED and uncontradicted
    "donor_contra_min": 5,      # an arm of another kind with a single top type, this many votes
    #                             for a different type, makes the head no donor
    "recovered_decides": True,  # the fallback definition ("definition_recovered") may decide
    # W3-a2: a definition sentence a model generated (arm ``gen_definition``).  It never
    # settles a tie or a split; it places a word nothing else decided, marked as an
    # estimate (generated).  True: when an arm of another kind that reached its own threshold
    # points at the very same single type, the word is placed DIRECT (an agreement).
    "gen_upgrade_on_agreement": True,
}

#: the arm of generated definitions and the origin its source carries
GEN_ARM = "gen_definition"

#: Taxonomic rank words (longest first).  "…イヌ科イヌ亜科の一部" says X belongs to a
#: taxon: the type of the taxon in front of the last rank word is the phrase's.
RANK_WORDS: Tuple[str, ...] = (
    "亜科", "亜属", "亜目", "亜綱", "亜門", "上科", "亜族", "科", "属", "目", "綱", "門", "族")

#: Words a hypernym phrase is NOT (the sentence says "X is one of Y" -- the
#: type is Y's, found before the connecting の).
GENERIC_HEADS: Tuple[str, ...] = (
    "一種", "一つ", "ひとつ", "1つ", "総称", "こと", "種", "類",
    "ほか", "一例", "呼称", "別名", "通称", "称", "もの", "ひとり", "一人", "一部",
    "うち", "なか", "中", "一員", "一族")


# --- predicate frame rules (verbs) -------------------------------------------
# A verb is placed from the COUNTS of which noun type stands in which
# particle slot before it (the first verb after a particle-marked noun).
# Each rule: (predicate type, [(particles, noun types, min share in %), ...]);
# EVERY slot condition of a rule must hold.  The share is over the verb's
# type-known argument occurrences of one source.  A verb may satisfy more
# than one rule: then it keeps all of them (a plurality, not a tie-break).
PRED_FRAME_RULES: List[Tuple[str, List[Tuple[Tuple[str, ...], Tuple[str, ...], int]]]] = [
    ("P_CONSUME", [(("を",), ("SUBSTANCE_FOOD",), 30)]),
    ("P_MOVE", [(("に", "へ", "から", "まで"), ("PLACE",), 30)]),
    ("P_GIVE", [(("に",), ("PERSON", "GROUP_ORG"), 25),
                (("を",), ("ARTIFACT", "SUBSTANCE_FOOD", "QUANTITY",
                           "INFO_LANGUAGE"), 30)]),
    ("P_COMMUNICATE", [(("と", "に"), ("PERSON", "GROUP_ORG"), 20),
                       (("を",), ("INFO_LANGUAGE", "ABSTRACT"), 25)]),
    ("P_CREATE", [(("を",), ("WORK", "ARTIFACT", "INFO_LANGUAGE",
                            "SUBSTANCE_FOOD", "PLACE"), 50)]),
    ("P_COGNITION", [(("を", "と"), ("ABSTRACT", "INFO_LANGUAGE",
                                    "STATE_PROPERTY", "EVENT_ACT"), 50)]),
    ("P_EXIST", [(("に",), ("PLACE",), 20),
                 (("が",), ("PERSON", "ANIMAL", "PLANT", "ARTIFACT", "PLACE",
                            "SUBSTANCE_FOOD", "GROUP_ORG"), 60)]),
    ("P_CHANGE", [(("が",), ("STATE_PROPERTY", "QUANTITY",
                            "NATURAL_PHENOMENON", "ABSTRACT", "TIME"), 50)]),
    ("P_ACT", [(("を",), ("PERSON", "ANIMAL", "BODY_PART", "ARTIFACT"), 50)]),
]

#: Hypernyms that talk about the WORD, not the thing ("X is a term / a name /
#: a word for ..."): the type of what X denotes is not given, so they are skipped
#: when typing a hypernym (the words themselves keep their seed type).
META_HEADS: Tuple[str, ...] = (
    "用語", "言葉", "名称", "呼称", "総称", "略称", "愛称", "通称", "別名",
    "異名", "表現", "語", "単語", "名前", "称号", "俗称", "異称", "略語",
    "表記", "訳語", "訳", "用字", "字")


# --- the decision rules (ONE place: the builder and the query use the same) --
#: Arms whose evidence is kept per source (a count of one source is never added
#: to another source's).
ARMS_BY_SOURCE: Tuple[str, ...] = ("role", "hearst", "sahen", "pos_class", "frame")
#: The definition-like arms (what ``definition_outranks_role`` puts first).
TIER2_ARMS: Tuple[str, ...] = (
    "definition", "definition_recovered", "title_qualifier", "alias", "paren_alias", "hearst")
#: Arms of another kind than a definition whose votes can contradict a chain donor
#: (``donor_contra_min``): each is looked at on its own, never summed.
DONOR_CONTRA_ARMS: Tuple[str, ...] = ("role", "hearst", "alias", "paren_alias", "title_qualifier")
#: Evidence rows that are not a vote for a type (they explain a decision).
NON_VOTE_ARMS: Tuple[str, ...] = ("ns_vote",)


def arm_key(arm: str, src: str) -> str:
    """The name an arm goes by in the output: per-source arms carry the source."""
    if arm in ARMS_BY_SOURCE:
        return "%s@%s" % (arm, src)
    return arm


def arm_top(counts: Dict[str, int], min_n: int, min_share_pct: int = 0) -> List[str]:
    """The types at the top of one arm, or [] when the arm is not met.  Types
    tied at the top stay together (no winner is chosen by order)."""
    if not counts:
        return []
    mx = max(counts.values())
    if mx < min_n:
        return []
    tot = sum(counts.values())
    if min_share_pct and mx * 100 < min_share_pct * tot:
        return []
    return sorted(t for t, c in counts.items() if c == mx)


def combine_arms(arm_tops: Dict[str, List[str]]):
    """Overlay the met arms.  All arms agree on one type -> DECIDED, else
    MULTIPLE (the tops, unioned, in alphabetical order -- a display order).
    None when no arm is met."""
    met = {a: t for a, t in arm_tops.items() if t}
    if not met:
        return None
    sets = {tuple(t) for t in met.values()}
    if len(sets) == 1 and len(next(iter(sets))) == 1:
        return ("DECIDED", list(next(iter(sets))), sorted(met))
    union = sorted({x for t in met.values() for x in t})
    return ("MULTIPLE", union, sorted(met))


def arm_verdict(arm: str, counts: Dict[str, int], cfg: dict,
                base: Optional[int] = None) -> List[str]:
    """The tops of ONE arm (one source) when its own threshold is met, else [].

    ``base`` is the denominator some arms need: for ``sahen`` the number of the
    word's noun uses in that source, for ``pos_class`` its verb uses."""
    if not counts:
        return []
    if arm in ("definition", "definition_recovered"):
        return arm_top(counts, cfg["def_min"])
    if arm == "title_qualifier":
        return arm_top(counts, cfg["qual_min"])
    if arm == "alias":
        return arm_top(counts, cfg["alias_min"])
    if arm == "paren_alias":
        return arm_top(counts, cfg["paren_alias_min"])
    if arm == "hearst":
        return arm_top(counts, cfg["hearst_min"], cfg["hearst_min_share_pct"])
    if arm == "role":
        return arm_top(counts, cfg["role_min"], cfg["role_min_share_pct"])
    if arm == "sahen":
        sc = sum(counts.values())
        if sc >= cfg["sahen_min"] and sc * 100 >= cfg["sahen_min_share_pct"] * max(base or 0, sc):
            return ["EVENT_ACT"]
        return []
    if arm == "pos_class":
        a_s = sum(counts.values())
        if a_s >= cfg["pos_min"] and a_s >= (base or 0):
            return ["P_STATE"]
        return []
    if arm == "frame":
        mx = max(counts.values())
        return sorted(t for t, c in counts.items() if c == mx)
    if arm in ("seed", "notation"):
        return sorted(counts)
    return []


def decide_word(ev, cfg: dict) -> Dict[str, object]:
    """Decide one word from its evidence rows ``(arm, src, type, n, base)``.

    The rows of the generated arm (``gen_definition``) are set apart: the word is first
    decided WITHOUT them (``_decide_base``); a generated arm then (1) never changes a
    DECIDED or MULTIPLE decision (``GENERATED_NOT_DECIDING``), (2) places a word nothing
    else decided only when it names ONE type (a split places nothing:
    ``GENERATED_SPLIT``), as an ESTIMATE (generated) -- or DIRECT when an arm of
    another kind that reached its own threshold names exactly that type (and
    ``gen_upgrade_on_agreement``).  The result carries ``origin`` ("direct", "estimated"
    or None) and ``estimate_basis`` (None or "generated").

    Returns ``{"arms": {key: {counts, top, threshold_met, met, why}}, "state",
    "tops", "by"}``.  ``threshold_met`` is the arm's own threshold; ``met`` is
    True only when the arm also TOOK PART in the decision.  ``why`` names the
    reason an arm that reached its threshold was set aside:
    ``ROLE_SINGLE_SOURCE`` (the weakest arm never decides alone: fewer than
    ``role_min_sources`` role sources reached their thresholds), ``SEEDED`` (a
    hand-written anchor settles the word) or ``OUTRANKED``
    (``definition_outranks_role``).  Counts of different arms and
    different sources are never added."""
    gen_rows = [r for r in ev if r[0] == GEN_ARM]
    base_dec = _decide_base([r for r in ev if r[0] != GEN_ARM], cfg)
    if not gen_rows:
        return base_dec
    arms_ = base_dec["arms"]
    counts: Dict[str, int] = {}
    for _a, _s, typ, n, _b in gen_rows:
        counts[typ] = n
    top = arm_top(counts, 1)
    garm = {"arm": GEN_ARM, "src": gen_rows[0][1], "counts": dict(sorted(counts.items())),
            "top": top, "threshold_met": bool(top), "met": False, "why": None}
    arms_[GEN_ARM] = garm
    if base_dec["state"] in ("DECIDED", "MULTIPLE"):
        garm["why"] = "GENERATED_NOT_DECIDING"
        return base_dec
    if len(top) != 1:
        garm["why"] = "GENERATED_SPLIT"
        return base_dec
    t = top[0]
    garm["met"] = True
    agree = sorted(k for k, a in arms_.items()
                   if k != GEN_ARM and a["threshold_met"] and a["top"] == [t])
    if agree and cfg.get("gen_upgrade_on_agreement", True):
        for k in agree:
            arms_[k]["met"] = True
            arms_[k]["why"] = None
        return {"arms": arms_, "state": "DECIDED", "tops": [t], "by": sorted(agree + [GEN_ARM]),
                "origin": "direct", "estimate_basis": None}
    return {"arms": arms_, "state": "DECIDED", "tops": [t], "by": [GEN_ARM],
            "origin": "estimated", "estimate_basis": "generated"}


def _decide_base(ev, cfg: dict) -> Dict[str, object]:
    """``decide_word`` without the generated arm (see there)."""
    arms: Dict[str, dict] = {}
    for arm, src, typ, n, base in ev:
        if arm in NON_VOTE_ARMS:
            continue
        k = arm_key(arm, src)
        a = arms.setdefault(k, {"arm": arm, "src": src, "counts": {}, "base": None})
        a["counts"][typ] = n
        if base is not None:
            a["base"] = base
    out_arms: Dict[str, dict] = {}
    for k, a in arms.items():
        top = arm_verdict(a["arm"], a["counts"], cfg, a["base"])
        out_arms[k] = {"arm": a["arm"], "src": a["src"],
                       "counts": dict(sorted(a["counts"].items())),
                       "top": top, "threshold_met": bool(top), "met": bool(top),
                       "why": None}
    if not cfg.get("recovered_decides", True):
        for a in out_arms.values():          # the fallback definition is shown, not used
            if a["arm"] == "definition_recovered" and a["threshold_met"]:
                a["met"] = False
                a["why"] = "RECOVERED_NOT_DECIDING"
    role_keys = [k for k, a in out_arms.items() if a["arm"] == "role" and a["threshold_met"]]
    if role_keys and len(role_keys) < cfg["role_min_sources"]:
        for k in role_keys:
            out_arms[k]["met"] = False
            out_arms[k]["why"] = "ROLE_SINGLE_SOURCE"
    seed = out_arms.get("seed")
    if seed is not None and seed["top"]:
        for k, a in out_arms.items():
            if k != "seed" and a["met"]:
                a["met"] = False            # a hand-written anchor settles the word:
                a["why"] = "SEEDED"         # the other arms stay as evidence only
        return {"arms": out_arms, "state": "DECIDED", "tops": list(seed["top"]),
                "by": ["seed"], "origin": "direct", "estimate_basis": None}
    live = {k: a["top"] for k, a in out_arms.items() if a["met"]}
    if cfg.get("definition_outranks_role"):
        t2 = {k: t for k, t in live.items() if out_arms[k]["arm"] in TIER2_ARMS}
        if combine_arms(t2) is not None:
            for k in live:
                if k not in t2:
                    out_arms[k]["met"] = False
                    out_arms[k]["why"] = "OUTRANKED"
            live = t2
    comb = combine_arms(live)
    if comb is None:
        return {"arms": out_arms, "state": "UNPLACED", "tops": [], "by": [],
                "origin": None, "estimate_basis": None}
    return {"arms": out_arms, "state": comb[0], "tops": comb[1], "by": comb[2],
            "origin": "direct", "estimate_basis": None}
