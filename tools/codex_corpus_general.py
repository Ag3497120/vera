"""General-chatbot corpus families written by Codex agents (luna low, /fast).

Sibling of tools/codex_corpus_families.py. Five new families, each in its own
directory, never mixed:

    general_qa              q_variants[3] -> answer (+why), domain, kind
    code_qa                 question -> answer_text + runnable code + usage
    figurative_commonsense  simile_metaphor / cause_effect / pun / haiku
    narrative               story (per-sentence shape) / poem (theme)
    paraphrase_entail       labelled sentence pairs / who-did-what QA

Safeguards (same as the prose corpus): empty dir + read-only sandbox, any
tool item in the event stream rejects the batch, template-shape gate,
llm_authored source tag. Plus overfitting control:

  * every record whose text shares an 8+ character substring (NFKC,
    whitespace removed) with any evaluation text (--block-dirs) is dropped
    and counted in the ledger as dropped_overlap;
  * every grid cell has split = sha1(cell key) % 10: 0 -> heldout
    (<out>/heldout/records.jsonl), else train (<out>/train/records.jsonl);
  * dedupe by sha of the normalised main text.

Grid cells are walked in order from --start; cells already KEPT in the
ledger are skipped, so several processes on disjoint --start ranges and
reruns never repeat a cell.

    python3.11 tools/codex_corpus_general.py --family general_qa \\
        --out ~/vera-codex-corpus/general_qa --host pro --start 0 \\
        --batches 500 --workers 16 --block-dirs ~/vera-eval-block
"""
from __future__ import annotations

import argparse
import fcntl
import hashlib
import io
import json
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import unicodedata
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

MODEL, EFFORT, TIER = "gpt-6-luna", "low", "priority"
ALLOWED_ITEMS = {"agent_message", "reasoning", "transport_notice"}
#: codex reports a transport downgrade as an "error" item even though the run
#: then completes over HTTPS. It is not a tool call and does not taint output.
BENIGN_ERRORS = ("Falling back from WebSockets to HTTPS transport",)
KANA_ROWS = ("あ", "か", "さ", "た", "な", "は", "ま", "や", "ら", "わ")

COMMON_RULES = """- 本当に正しいことだけを書く。架空の事実・存在しない関数や規則を作らない。
- 各件は独立して意味が通るようにし、同じ文型・同じ言い回しを繰り返さない。
- あなたはコマンドの実行・ファイル操作・検索を一切しない。頭の中の知識だけで書く。テンプレートや機械的な置き換えで件数を水増ししない。
- 出力は指定のJSONだけ。"""


def obj(props: dict) -> dict:
    return {"type": "object", "properties": props,
            "required": list(props), "additionalProperties": False}


S = {"type": "string"}


def arr(x):
    return {"type": "array", "items": x}


def enum(xs):
    return {"type": "string", "enum": list(xs)}


# ============================================================ general_qa
QA_DOMAINS = ("科学（物理・化学）", "生物・人体", "地学・天気・宇宙", "日本の歴史", "世界の歴史",
              "日本の地理", "世界の地理", "社会の仕組み・政治", "法律と暮らし", "経済・お金",
              "健康・病気の予防", "食べ物・料理", "栄養", "スポーツ", "音楽", "美術・工芸",
              "文学・本", "日本語・ことば", "外国語", "コンピュータ・インターネット", "スマホ・家電",
              "乗り物・交通", "暮らし・家事", "マナー・冠婚葬祭", "旅行", "動物", "植物・園芸",
              "季節の行事", "仕事・職場", "学校・勉強", "子育て", "防災・安全")
QA_KINDS = ("fact", "howto", "definition", "comparison", "advice", "social")
QA_LEVELS = ("子どもにもわかるように", "一般の大人向けに", "少し詳しく知りたい人向けに")
QA_KIND_JA = {
    "fact": "事実を問う質問（何・いつ・どこ・なぜ・どれくらい）",
    "howto": "やり方・手順を問う質問",
    "definition": "言葉や物事の意味を問う質問",
    "comparison": "二つのものの違いを問う質問",
    "advice": "困りごと・迷いごとへの助言を求める質問（一般的で安全な助言に限る）",
}
QA_ITEM = obj({"q_variants": arr(S), "answer": S, "why": S,
               "kind": enum(("fact", "howto", "definition", "comparison", "advice",
                             "greeting", "needs_live_data"))})
QA_SCHEMA = obj({"items": arr(QA_ITEM)})
QA_PROMPT = """あなたは物知りで誠実な日本語の書き手です。質問と答えの組を{n}組、あなた自身の言葉で直接書いてください。

分野: {domain}
種類: {kind_ja}
答えの詳しさ: {level}
題材の手がかり: 「{kana}」行の音で始まる語が出てくる題材を多めに選ぶ（こだわりすぎなくてよい）

各組の書き方:
- q_variants: 同じ答えになる質問を、言い方を変えて3つ。1つ目は普通の言い方、2つ目はくだけた話し言葉、3つ目は丁寧な言い方。
- answer: 簡潔で正確な答え（1〜3文）。
- why: 理由や仕組みを1行で。自然でなければ空文字列。
- kind: {kind_field}
{extra}
{rules}"""
QA_SOCIAL_EXTRA = """- この回は、あいさつ・お礼・雑談（「こんにちは」「ありがとう」「元気？」「おやすみ」「疲れた」など、分野に関係する話題の雑談も含む）を kind="greeting" として約6割、
  今この瞬間の情報がないと答えられない質問（今日の天気・今の株価・今何時・試合の結果・電車の運行状況・最新ニュースなど、分野に関係するもの）を kind="needs_live_data" として約4割書く。
- needs_live_data の answer は、リアルタイムの情報は持っていないので答えられないと正直に伝え、どうすれば調べられるか（天気予報サイト、時計、公式サイトなど）を案内する。why は空文字列でよい。
- greeting の answer は自然で温かい返事にする。"""

# ============================================================== code_qa
CQ_LANGS = ("Python", "JavaScript", "TypeScript", "Swift", "Rust", "Go", "SQL",
            "シェル(bash)", "C")
CQ_TASKS = ("write_function", "fix_error", "difference", "refactor", "write_test",
            "query_or_oneliner", "explain_code", "algorithm")
CQ_TASK_JA = {
    "write_function": "「〜する関数を書いて」という依頼",
    "fix_error": "エラーが出たコードと、その直し方を問う質問（エラーメッセージは実在の文面）",
    "difference": "「AとBの違いは？」という質問（違いを示すコード付き）",
    "refactor": "読みにくいコードを読みやすく書き直す依頼",
    "write_test": "既存の関数に単体テストを書く依頼",
    "query_or_oneliner": "SQLのクエリやシェルのワンライナー、短い便利コードの依頼",
    "explain_code": "コードの動きを説明してほしいという質問（改良版コード付き）",
    "algorithm": "並べ替え・探索・集計など、簡単なアルゴリズムを書く依頼",
}
CQ_CONTEXTS = ("文字列処理", "ファイルとディレクトリ", "データの集計", "Webとネットワーク",
               "日付と時刻", "計算と数値", "コマンドラインツール", "データ構造")
CQ_LEVELS = ("初心者", "中級者", "実務者")
CQ_ITEM = obj({"question": S, "answer_text": S, "code": S, "usage": S})
CQ_SCHEMA = obj({"items": arr(CQ_ITEM)})
CQ_PROMPT = """あなたは正確なプログラミングの先生です。プログラミングの質問と答えを{n}組、あなた自身の言葉で直接書いてください。

言語: {lang}
質問の種類: {task_ja}
題材の分野: {context}
質問者: {level}
題材の手がかり: 「{kana}」行の音で始まる語が出てくる題材を多めに選ぶ（こだわりすぎなくてよい）

各組の書き方:
- question: 日本語の自然な質問・依頼文（必要なら元のコードやエラー文を含める）。
- answer_text: 短い日本語の説明（1〜3文）。
- code: そのまま動く完全なコード（必要なimportや定義を含める）。コメントは日本語。マークダウンの```は付けない。
- usage: 使い方の例を1行（実行コマンドや呼び出し例と結果）。
{rules}"""

# ================================================= figurative_commonsense
FC_KINDS = ("simile_metaphor", "cause_effect", "pun", "haiku")
FC_THEMES = ("台所", "天気", "季節", "動物", "植物", "海と川", "山", "乗り物", "学校",
             "仕事", "家族", "友達", "体と健康", "食べ物", "お金", "時間", "音", "光と色",
             "道具", "町", "旅", "スポーツ", "音楽", "夜空", "火と水", "服", "感情",
             "遊び", "年中行事", "機械")
FC_REGISTERS = ("日常の話し言葉", "書き言葉", "子ども向け", "大人のユーモア")
FC_SPECS = {
    "simile_metaphor": (
        obj({"items": arr(obj({"expression": S, "type": enum(("simile", "metaphor")),
                               "vehicle": S, "target": S, "property": S,
                               "plain_meaning": S, "example": S}))}),
        """比喩表現（直喩「〜のような」・隠喩）を{n}件書く。
- expression: 比喩表現そのもの。慣用的なものと、新しく作ったわかりやすいものを混ぜる。
- type: simile か metaphor。
- vehicle: たとえに使ったもの。target: たとえられているもの。property: 移された性質。
- plain_meaning: 比喩を使わずに言うと何か。example: その比喩を使った自然な例文。"""),
    "cause_effect": (
        obj({"items": arr(obj({"relation": enum(("cause_effect", "purpose")),
                               "cause": S, "effect": S, "phrasings": arr(S)}))}),
        """常識的な因果関係・目的の関係を{n}件書く（例: 濡れた洗濯物を日なたに干す → 乾く）。
- relation: 原因と結果なら cause_effect、行為と目的なら purpose。
- cause: 原因または行為。effect: 結果または目的。
- phrasings: その関係を表す自然な文を、言い方を変えて2つ。"""),
    "pun": (
        obj({"items": arr(obj({"pun": S, "word_a": S, "word_b": S,
                               "reading": S, "mechanism": S}))}),
        """だじゃれ・言葉遊びを{n}件書く。
- pun: だじゃれの文。word_a / word_b: 掛けている二つの語。reading: 共通する（または似ている）読み（ひらがな）。
- mechanism: なぜ面白いのか、どう音が重なっているのかの説明（1〜2文）。
- 読みが本当に重なっているものだけを書く。"""),
    "haiku": (
        obj({"items": arr(obj({"haiku": S, "lines": arr(S), "kigo": S,
                               "season": enum(("春", "夏", "秋", "冬", "新年")),
                               "note": S}))}),
        """オリジナルの俳句を{n}句書く（既存の有名な句をまねない）。
- haiku: 句全体。lines: 五・七・五の3つの部分。音の数（五・七・五）を守る。
- kigo: 季語。season: その季語の季節。note: 句の情景を1行で。"""),
}
FC_PROMPT = """あなたは日本語の言葉に詳しい書き手です。テーマ「{theme}」に関係するものとして、次を書いてください。口調・文体: {register}。
題材の手がかり: 「{kana}」行の音で始まる語が出てくる題材を多めに選ぶ（こだわりすぎなくてよい）

{task}
{rules}"""

# ============================================================== narrative
NA_KINDS = ("story", "story", "poem")
NA_SETTINGS = ("朝の台所", "通学路", "放課後の教室", "会社の休憩室", "商店街", "病院の待合室",
               "田舎の祖父母の家", "海辺の町", "雪の山小屋", "夏祭り", "夜の駅", "図書館",
               "引っ越しの日", "動物園", "森の中", "宇宙船の中", "魔法の国", "未来の都市",
               "昔話の村", "しゃべる動物たちの町", "小さな島", "雨の日の公園", "キャンプ場",
               "パン屋", "農家の畑", "港", "山頂", "美術館", "工事現場", "誕生日パーティー")
NA_TONES = ("心温まる", "ユーモラス", "少し切ない", "ふしぎ", "わくわくする", "静かで穏やか",
            "ハラハラする", "教訓のある")
NA_SCHEMA_STORY = obj({"items": arr(obj({
    "title": S,
    "sentences": arr(obj({"text": S, "shape": enum(("start", "development", "turn", "ending"))}))}))})
NA_SCHEMA_POEM = obj({"items": arr(obj({"title": S, "theme": S, "lines": arr(S)}))})
NA_STORY_TASK = """短い物語を{n}本書く。1本は3〜6文。
- sentences の各文に shape を付ける: start（始まり・状況）、development（展開）、turn（転換・意外なこと）、ending（結末）。
- 順序は start → development（0〜2文）→ turn → ending を基本とし、start と ending は必ず1文ずつ入れる。
- 出来事の前後関係・原因と結果がはっきりわかるように書く。登場人物や出来事は物語ごとに変える。"""
NA_POEM_TASK = """短い詩を{n}編書く。1編は3〜8行。
- theme: 詩のテーマを短い言葉で。lines: 詩の各行。
- 形式（自由詩・リズムのある詩・子ども向けの詩など）を詩ごとに変える。"""
NA_PROMPT = """あなたは日本語の物語と詩の書き手です。舞台「{setting}」、雰囲気「{tone}」で、次を書いてください。
題材の手がかり: 「{kana}」行の音で始まる語が出てくる題材を多めに選ぶ（こだわりすぎなくてよい）

{task}
{rules}"""

# ===================================================== paraphrase_entail
PE_KINDS = ("pair", "pair", "who_did_what")
PE_PHENOMENA = ("受け身", "使役", "使役受け身", "否定", "二重否定", "比較", "時間の順序（前・後・〜てから）",
                "条件（〜たら・〜ば）", "授受（あげる・もらう・くれる）", "数量", "理由（〜ので・〜から）",
                "可能・不可能", "類義語の言い換え", "語順の入れ替え", "連体修飾（〜した人）", "並列と選択")
PE_TOPICS = ("家族", "学校", "職場", "買い物", "料理", "スポーツ", "旅行", "病院", "天気",
             "動物", "町の出来事", "趣味", "交通", "お祝い", "引っ越し", "図書館", "農業", "工作")
PE_SCHEMA_PAIR = obj({"items": arr(obj({
    "s1": S, "s2": S, "label": enum(("paraphrase", "entails", "contradicts", "neutral")),
    "reason": S}))})
PE_SCHEMA_WDW = obj({"items": arr(obj({"sentence": S, "question": S, "answer": S}))})
PE_PAIR_TASK = """文のペアを{n}組書き、s1 と s2 の関係に label を付ける。4種類をおおよそ均等に混ぜる:
- paraphrase: 同じ意味の言い換え。entails: s1 が正しければ s2 も必ず正しい（逆は成り立たない）。
- contradicts: 両方が同時には正しくない。neutral: s1 からは s2 が正しいか判断できない。
- reason: なぜその label なのかを1文で。
- 文法現象「{phenomenon}」を必ず使い、その文法の読み違えで label が変わるような、よく考えないと間違えるペアを多く含める。"""
PE_WDW_TASK = """一文と、その文について「誰が・誰に・何を・いつ・どちらが」などを問う質問と答えを{n}組書く。
- 文法現象「{phenomenon}」を必ず使い、主語と目的語を取り違えやすい文にする。
- answer は短く正確に（語句または短い文）。"""
PE_PROMPT = """あなたは日本語の文法と意味に詳しい書き手です。題材「{topic}」で、次を書いてください。
題材の手がかり: 「{kana}」行の音で始まる語が出てくる題材を多めに選ぶ（こだわりすぎなくてよい）

{task}
{rules}"""


def axes(family: str):
    return {
        "general_qa": (("domain", QA_DOMAINS), ("kind", QA_KINDS), ("level", QA_LEVELS),
                       ("kana", KANA_ROWS)),
        "code_qa": (("lang", CQ_LANGS), ("task_kind", CQ_TASKS), ("context", CQ_CONTEXTS),
                    ("level", CQ_LEVELS), ("kana", KANA_ROWS)),
        "figurative_commonsense": (("kind", FC_KINDS), ("theme", FC_THEMES),
                                   ("register", FC_REGISTERS), ("kana", KANA_ROWS)),
        "narrative": (("kind", NA_KINDS), ("setting", NA_SETTINGS), ("tone", NA_TONES),
                      ("kana", KANA_ROWS)),
        "paraphrase_entail": (("kind", PE_KINDS), ("phenomenon", PE_PHENOMENA),
                              ("topic", PE_TOPICS), ("kana", KANA_ROWS)),
    }[family]


def grid_size(family: str) -> int:
    n = 1
    for _, vals in axes(family):
        n *= len(vals)
    return n


def cell(family: str, i: int) -> dict:
    c, r = {"job": i}, i
    for name, vals in axes(family):
        c[name] = vals[r % len(vals)]
        r //= len(vals)
    key = family + "|" + "|".join(str(c[n]) for n, _ in axes(family)) + "|%d" % (i // grid_size(family))
    c["split"] = "heldout" if int(hashlib.sha1(key.encode()).hexdigest(), 16) % 10 == 0 else "train"
    return c


DEFAULT_N = {"general_qa": 40, "code_qa": 12, "figurative_commonsense": 40,
             "narrative": 15, "paraphrase_entail": 50}


def build(family: str, c: dict, n: int):
    """-> (prompt, schema)"""
    if family == "general_qa":
        if c["kind"] == "social":
            kj, kf, extra = "あいさつ・雑談と、今の情報が必要な質問", "greeting または needs_live_data", QA_SOCIAL_EXTRA
        else:
            kj, kf, extra = QA_KIND_JA[c["kind"]], '"%s"' % c["kind"], ""
        return QA_PROMPT.format(n=n, domain=c["domain"], kind_ja=kj, level=c["level"],
                                kana=c["kana"], kind_field=kf, extra=extra,
                                rules=COMMON_RULES), QA_SCHEMA
    if family == "code_qa":
        return CQ_PROMPT.format(n=n, lang=c["lang"], task_ja=CQ_TASK_JA[c["task_kind"]],
                                context=c["context"], level=c["level"], kana=c["kana"],
                                rules=COMMON_RULES), CQ_SCHEMA
    if family == "figurative_commonsense":
        schema, task = FC_SPECS[c["kind"]]
        return FC_PROMPT.format(theme=c["theme"], register=c["register"], kana=c["kana"],
                                task=task.format(n=n), rules=COMMON_RULES), schema
    if family == "narrative":
        if c["kind"] == "story":
            task, schema = NA_STORY_TASK.format(n=n), NA_SCHEMA_STORY
        else:
            task, schema = NA_POEM_TASK.format(n=n), NA_SCHEMA_POEM
        return NA_PROMPT.format(setting=c["setting"], tone=c["tone"], kana=c["kana"],
                                task=task, rules=COMMON_RULES), schema
    if c["kind"] == "pair":
        task, schema = PE_PAIR_TASK.format(n=n, phenomenon=c["phenomenon"]), PE_SCHEMA_PAIR
    else:
        task, schema = PE_WDW_TASK.format(n=n, phenomenon=c["phenomenon"]), PE_SCHEMA_WDW
    return PE_PROMPT.format(topic=c["topic"], kana=c["kana"], task=task,
                            rules=COMMON_RULES), schema


_HIRA = re.compile(r"[ぁ-ん]")


def _s(x, lo=1, hi=2000):
    return isinstance(x, str) and lo <= len(x.strip()) <= hi


def convert(family: str, c: dict, data: dict):
    """-> list of (record_fields, main_text, overlap_texts)"""
    out = []
    for it in data.get("items", []):
        if family == "general_qa":
            qv = [q.strip() for q in it.get("q_variants", []) if _s(q, 1, 300)]
            ans, why, k = it.get("answer", "").strip(), it.get("why", "").strip(), it.get("kind")
            if len(qv) < 2 or not _s(ans, 1, 600) or not _HIRA.search(ans):
                continue
            if c["kind"] == "social":
                if k not in ("greeting", "needs_live_data"):
                    continue
            else:
                k = c["kind"]
            rec = {"q_variants": qv, "answer": ans, "why": why, "domain": c["domain"],
                   "kind": k, "level": c["level"]}
            out.append((rec, qv[0] + "\n" + ans, qv + [ans, why]))
        elif family == "code_qa":
            q, a, code, use = (it.get(x, "").strip() for x in ("question", "answer_text", "code", "usage"))
            if not (_s(q, 5, 1500) and _s(a, 5, 1000) and _s(code, 5, 6000) and _HIRA.search(a)):
                continue
            code = re.sub(r"^```\w*\n|\n```\s*$", "", code)
            rec = {"question": q, "answer_text": a, "code": code, "usage": use,
                   "lang": c["lang"], "task_kind": c["task_kind"], "context": c["context"]}
            out.append((rec, q + "\n" + code, [q, a, use]))
        elif family == "figurative_commonsense":
            k = c["kind"]
            if k == "simile_metaphor":
                need = ("expression", "vehicle", "target", "property", "plain_meaning", "example")
                if not all(_s(it.get(x), 1, 300) for x in need):
                    continue
                rec = {x: it[x].strip() for x in need}
                rec["type"] = it.get("type")
                main, texts = rec["expression"] + "\n" + rec["example"], [rec[x] for x in need]
            elif k == "cause_effect":
                ph = [p.strip() for p in it.get("phrasings", []) if _s(p, 4, 300)]
                if not (_s(it.get("cause"), 1, 200) and _s(it.get("effect"), 1, 200)) or len(ph) < 2:
                    continue
                rec = {"relation": it.get("relation"), "cause": it["cause"].strip(),
                       "effect": it["effect"].strip(), "phrasings": ph[:2]}
                main, texts = rec["cause"] + "→" + rec["effect"], ph[:2] + [rec["cause"], rec["effect"]]
            elif k == "pun":
                need = ("pun", "word_a", "word_b", "reading", "mechanism")
                if not all(_s(it.get(x), 1, 300) for x in need):
                    continue
                rec = {x: it[x].strip() for x in need}
                main, texts = rec["pun"], [rec["pun"], rec["mechanism"]]
            else:
                lines = [l.strip() for l in it.get("lines", []) if _s(l, 1, 30)]
                if len(lines) != 3 or not _s(it.get("kigo"), 1, 20) or not _s(it.get("haiku"), 5, 60):
                    continue
                rec = {"haiku": it["haiku"].strip(), "lines": lines, "kigo": it["kigo"].strip(),
                       "season": it.get("season"), "note": it.get("note", "").strip()}
                main, texts = rec["haiku"], [rec["haiku"], rec["note"]]
            rec.update({"kind": k, "theme": c["theme"], "register": c["register"]})
            out.append((rec, main, texts))
        elif family == "narrative":
            if c["kind"] == "story":
                ss = [{"text": s.get("text", "").strip(), "shape": s.get("shape")}
                      for s in it.get("sentences", [])]
                ss = [s for s in ss if _s(s["text"], 3, 300)]
                shapes = [s["shape"] for s in ss]
                if not (3 <= len(ss) <= 7) or shapes[0] != "start" or "ending" not in shapes:
                    continue
                rec = {"kind": "story", "title": it.get("title", "").strip(), "sentences": ss}
                main = "".join(s["text"] for s in ss)
                texts = [s["text"] for s in ss]
            else:
                lines = [l.strip() for l in it.get("lines", []) if _s(l, 1, 200)]
                if not (2 <= len(lines) <= 12) or not _s(it.get("theme"), 1, 60):
                    continue
                rec = {"kind": "poem", "title": it.get("title", "").strip(),
                       "theme": it["theme"].strip(), "lines": lines}
                main, texts = "\n".join(lines), lines
            rec.update({"setting": c["setting"], "tone": c["tone"]})
            out.append((rec, main, texts))
        else:
            if c["kind"] == "pair":
                if not (_s(it.get("s1"), 3, 300) and _s(it.get("s2"), 3, 300)):
                    continue
                rec = {"kind": "pair", "s1": it["s1"].strip(), "s2": it["s2"].strip(),
                       "label": it.get("label"), "reason": it.get("reason", "").strip()}
                main, texts = rec["s1"] + "\n" + rec["s2"], [rec["s1"], rec["s2"], rec["reason"]]
            else:
                if not all(_s(it.get(x), 1, 300) for x in ("sentence", "question", "answer")):
                    continue
                rec = {"kind": "who_did_what", "sentence": it["sentence"].strip(),
                       "question": it["question"].strip(), "answer": it["answer"].strip()}
                main, texts = rec["sentence"] + "\n" + rec["question"], [rec["sentence"], rec["question"], rec["answer"]]
            rec.update({"phenomenon": c["phenomenon"], "topic": c["topic"]})
            out.append((rec, main, texts))
    return out


# ------------------------------------------------------------- utilities
_WS = re.compile(r"\s+")
_JA = re.compile(r"[ぁ-ゟ゠-ヿ㐀-䶿一-鿿]")
_RUN = re.compile(r"[㐀-䶿一-鿿々〆ァ-ヺーA-Za-z0-9０-９_]+")


def norm(s: str) -> str:
    return _WS.sub("", unicodedata.normalize("NFKC", s or ""))


def skeleton(s: str) -> str:
    return _RUN.sub("X", s)


def shape_gate(texts: list, min_ratio: float, max_rep: int) -> str | None:
    if not texts:
        return "EMPTY"
    sk = Counter(skeleton(t) for t in texts)
    if len(sk) / len(texts) < min_ratio:
        return "TEMPLATE_SKELETONS_%d_of_%d" % (len(sk), len(texts))
    if sk.most_common(1)[0][1] > max_rep:
        return "TEMPLATE_REPEAT_%d" % sk.most_common(1)[0][1]
    return None


#: content words: kanji runs / katakana runs of 2+ chars, or a number with its unit
_CW = re.compile(r"[一-鿿々〆ヶ]{2,}|[ァ-ヺー]{2,}|\d+(?:\.\d+)?(?:%|[一-鿿ァ-ヺ]|[a-zA-Z]+)")
_SENT_END = re.compile(r"[。！？!?\n]+")
GRAM = 12          # shared substring length that counts as leakage ...
MIN_CW = 2         # ... only when it carries this many content words
MIN_SENT = 10      # whole-sentence rule: eval sentences this long with >=1 content word


class Block:
    """Evaluation texts, indexed for the leakage rule (designer decision 2026-09-30):
    a record is dropped only if it shares a 12+ char substring with the
    evaluation texts that contains >=2 content words, or contains a whole
    evaluation sentence. Stock phrases (pure kana, 「を教えていただけ」) never count."""

    def __init__(self, dirs: list):
        self.grams, self.sent_first, self.short_sents = set(), {}, set()
        self.ntexts = self.nsents = 0
        for t in _eval_texts(dirs):
            t = norm(t)
            if len(t) < 8:
                continue
            self.ntexts += 1
            for i in range(len(t) - GRAM + 1):
                g = t[i:i + GRAM]
                if len(_CW.findall(g)) >= MIN_CW:
                    self.grams.add(g)
            for sn in _SENT_END.split(t):
                if len(sn) >= MIN_SENT and _CW.search(sn):
                    self.nsents += 1
                    if len(sn) >= GRAM:
                        self.sent_first.setdefault(sn[:GRAM], set()).add(sn)
                    else:
                        self.short_sents.add(sn)

    def __len__(self):
        return len(self.grams)

    def hit(self, texts: list) -> str | None:
        """-> the matching evaluation substring/sentence, or None"""
        for t in texts:
            t = norm(t)
            for i in range(len(t) - GRAM + 1):
                g = t[i:i + GRAM]
                if g in self.grams:
                    return g
                for sn in self.sent_first.get(g, ()):
                    if t.startswith(sn, i):
                        return "SENT:" + sn
            for L in range(MIN_SENT, GRAM):
                for i in range(len(t) - L + 1):
                    if t[i:i + L] in self.short_sents:
                        return "SENT:" + t[i:i + L]
        return None


def _eval_texts(dirs: list):
    out = []

    def walk(x):
        if isinstance(x, str):
            out.append(x)
        elif isinstance(x, dict):
            for v in x.values():
                walk(v)
        elif isinstance(x, list):
            for v in x:
                walk(v)

    for d in dirs:
        for p in sorted(Path(d).expanduser().rglob("*")):
            if not p.is_file() or p.name.startswith("schema") or p.suffix in (".py", ".log"):
                continue
            if p.suffix == ".json":
                try:
                    walk(json.loads(p.read_text(encoding="utf-8")))
                except Exception:
                    walk(p.read_text(encoding="utf-8", errors="ignore"))
            elif p.suffix in (".txt", ".jsonl", ".md"):
                for line in p.read_text(encoding="utf-8", errors="ignore").splitlines():
                    walk(line)
    return out


def record_texts(r: dict) -> list:
    """The screened texts of a stored record (same fields convert() screens)."""
    keys = ("q_variants", "answer", "why", "question", "answer_text", "usage", "code",
            "expression", "vehicle", "target", "property", "plain_meaning", "example",
            "cause", "effect", "phrasings", "pun", "mechanism", "haiku", "note",
            "sentences", "lines", "s1", "s2", "reason", "sentence", "text", "title", "theme")
    out = []
    for k in keys:
        v = r.get(k)
        if isinstance(v, str):
            out.append(v)
        elif isinstance(v, list):
            for x in v:
                out.append(x["text"] if isinstance(x, dict) else str(x))
    return out


def free_gb(path: Path) -> float:
    return shutil.disk_usage(path).free / 1e9


def run_codex(prompt: str, schema: dict, codex: str, timeout: int):
    with tempfile.TemporaryDirectory(prefix="codex_general_") as tmp:
        tmp = Path(tmp)
        work = tmp / "empty"
        work.mkdir()
        (tmp / "schema.json").write_text(json.dumps(schema))
        cmd = [codex, "exec", "-m", MODEL,
               "-c", "model_reasoning_effort=" + json.dumps(EFFORT),
               "-c", "service_tier=" + json.dumps(TIER),
               "--skip-git-repo-check", "--ephemeral",
               "-s", "read-only", "--disable", "browser_use",
               "--disable", "computer_use", "--disable", "apps",
               "-C", str(work), "--output-schema", str(tmp / "schema.json"),
               "--json", "-o", str(tmp / "last.json"), prompt]
        t0 = time.time()
        try:
            p = subprocess.run(cmd, cwd=work, capture_output=True, text=True,
                               timeout=timeout, stdin=subprocess.DEVNULL)
        except subprocess.TimeoutExpired:
            return {"verdict": "REJECTED", "reason": "TIMEOUT",
                    "seconds": round(time.time() - t0, 1)}, None
        items, err_msg = Counter(), ""
        for line in p.stdout.splitlines():
            try:
                e = json.loads(line)
            except ValueError:
                continue
            it = (e.get("item") or {}).get("type")
            if it:
                msg = (e.get("item") or {}).get("message") or ""
                if it == "error" and msg.startswith(BENIGN_ERRORS):
                    items["transport_notice"] += 1   # WebSocket -> HTTPS fallback; not a tool
                    continue
                items[it] += 1
                if it == "error" and not err_msg:
                    err_msg = json.dumps(e.get("item"), ensure_ascii=False)[:300]
        rec = {"seconds": round(time.time() - t0, 1), "items": dict(items), "exit": p.returncode}
        tools = {k: v for k, v in items.items() if k not in ALLOWED_ITEMS}
        if tools and set(tools) == {"error"}:
            # an error item is the API/runtime failing, not the agent using a tool;
            # the batch is still rejected (nothing is trusted from it)
            return {**rec, "verdict": "REJECTED", "reason": "API_ERROR", "error": err_msg}, None
        if tools:
            return {**rec, "verdict": "REJECTED", "reason": "TOOL_USE", "tools": tools}, None
        try:
            data = json.loads((tmp / "last.json").read_text())
        except Exception:
            return {**rec, "verdict": "REJECTED", "reason": "NO_SCHEMA_OUTPUT",
                    "stderr_tail": (p.stderr or "")[-300:]}, None
    return rec, data


def locked_append(path: Path, text: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        f.write(text)
        f.flush()
        fcntl.flock(f, fcntl.LOCK_UN)


GATES = {"haiku": (0.5, 10), "cause_effect": (0.6, 6), "pun": (0.6, 6),
         "social": (0.5, 8)}


def main() -> int:
    fams = ("general_qa", "code_qa", "figurative_commonsense", "narrative", "paraphrase_entail")
    ap = argparse.ArgumentParser()
    ap.add_argument("--family", choices=fams, required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--host", required=True)
    ap.add_argument("--batches", type=int, default=100)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--per-batch", type=int, default=None)
    ap.add_argument("--start", type=int, default=0)
    ap.add_argument("--codex", default="codex")
    ap.add_argument("--timeout", type=int, default=900)
    ap.add_argument("--min-free-gb", type=float, default=20.0)
    ap.add_argument("--block-dirs", nargs="+", required=True,
                    help="evaluation directories; records sharing 8+ chars are dropped")
    a = ap.parse_args()

    n = a.per_batch or DEFAULT_N[a.family]
    out = Path(a.out).expanduser()
    out.mkdir(parents=True, exist_ok=True)
    ledger = out / "ledger.jsonl"
    block = Block(a.block_dirs)
    if not len(block):
        print("no evaluation texts loaded; refusing to run", file=sys.stderr)
        return 2
    seen = set()
    for sp in ("train", "heldout"):
        f = out / sp / "records.jsonl"
        if f.exists():
            for line in f.open(encoding="utf-8"):
                try:
                    seen.add(json.loads(line)["sha"])
                except Exception:
                    pass
    done = set()
    if ledger.exists():
        for line in ledger.open(encoding="utf-8"):
            try:
                r = json.loads(line)
            except ValueError:
                continue
            if r.get("verdict") == "KEPT":
                done.add(r["job"])
    jobs, i = [], a.start
    while i < min(a.start + a.batches, grid_size(a.family)):   # strictly this block, never past the grid
        if i not in done:
            jobs.append(cell(a.family, i))
        i += 1
    print(json.dumps({"family": a.family, "grid": grid_size(a.family), "jobs": len(jobs),
                      "first": jobs[0]["job"] if jobs else None,
                      "last": jobs[-1]["job"] if jobs else None, "per_batch": n,
                      "block_texts": block.ntexts, "block_12grams": len(block),
                      "block_sentences": block.nsents,
                      "skipped_done": len(done)}, ensure_ascii=False), file=sys.stderr, flush=True)

    lock, tally, stop = threading.Lock(), Counter(), threading.Event()

    def one(job):
        if stop.is_set():
            return
        if free_gb(out) < a.min_free_gb:
            stop.set()
            print("DISK_GUARD stop: free %.1f GB" % free_gb(out), file=sys.stderr, flush=True)
            return
        bid = "%s-%s-b%06d" % (a.host, a.family, job["job"])
        src = "llm_authored:codex:" + bid
        prompt, schema = build(a.family, job, n)
        rec, data = run_codex(prompt, schema, a.codex, a.timeout)
        got = convert(a.family, job, data) if data is not None else []
        if data is not None:
            mr, rep = GATES.get(job.get("kind"), (0.7, 5))
            bad = shape_gate([m for _, m, _ in got], mr, rep)
            if bad:
                rec = {**rec, "verdict": "REJECTED", "reason": bad}
            else:
                rec = {**rec, "verdict": "KEPT"}
        with lock:
            kept = dropped = dup = 0
            hit_grams = Counter()
            buf, qbuf = io.StringIO(), io.StringIO()
            if rec["verdict"] == "KEPT":
                for fields, main_text, texts in got:
                    h = hashlib.sha1(norm(main_text).encode()).hexdigest()[:16]
                    if h in seen:
                        dup += 1
                        continue
                    hit = block.hit(texts + [main_text])
                    if hit:
                        # dropped from the corpus; kept aside (never train/heldout)
                        # so a later decision about generic phrases can revisit it
                        dropped += 1
                        hit_grams[hit] += 1
                        qbuf.write(json.dumps({**fields, "family": a.family, "split": job["split"],
                                               "cell": job["job"], "source": src, "sha": h,
                                               "overlap_gram": hit}, ensure_ascii=False) + "\n")
                        continue
                    seen.add(h)
                    kept += 1
                    buf.write(json.dumps({**fields, "family": a.family, "split": job["split"],
                                          "cell": job["job"], "source": src, "sha": h},
                                         ensure_ascii=False) + "\n")
                if buf.getvalue():
                    locked_append(out / job["split"] / "records.jsonl", buf.getvalue())
                if qbuf.getvalue():
                    locked_append(out / "overlap_dropped" / "records.jsonl", qbuf.getvalue())
            rec.update({"kept": kept, "dropped_overlap": dropped, "dup": dup,
                        "returned": len(got), "overlap_grams": dict(hit_grams.most_common(5))})
            locked_append(ledger, json.dumps({"batch": bid, **job, **rec}, ensure_ascii=False) + "\n")
            tally[rec["verdict"] if rec["verdict"] == "KEPT" else rec["reason"]] += 1
            tally["records"] += kept
            tally["dropped_overlap"] += dropped
            print(bid, job["split"], rec["verdict"], rec.get("reason", ""), kept,
                  "drop=%d" % dropped, rec.get("seconds"), file=sys.stderr, flush=True)

    with ThreadPoolExecutor(a.workers) as ex:
        list(ex.map(one, jobs))
    print(json.dumps(dict(tally), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
