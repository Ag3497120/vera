"""The action guardrail: an agent's tool calls, held to the owner's own rules.

PREREGISTERED_2026-09-28_action_guard. Vera's specialization after the
2026-09-27 comparison: a current LLM rarely misstates a document, and Vera's
free-text reading raised 20% false alarms on confusable documents. Actions are
different — a tool call has a fixed shape (tool, arguments), so a rule can be
matched exactly instead of read loosely.

    covenant   「本番のデータは消さない」「1万円を超える支払いは確認してから」
               read into  (actions, targets, effect, conditions)
    action     delete_file(path="/prod/db/users.sqlite")
               read into  (action class, target text, amount …)
    verdict    block  — a forbidding rule applies
               ask    — a rule asks for confirmation, or its condition applies
               allow  — no forbidding or asking rule applies

Nothing is learned. The tables below are closed and written out; a rule the
tables cannot read is reported as unreadable, never silently dropped.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple

# Action classes, and the Japanese words that name them in a covenant.
CLASS_WORDS: Dict[str, Tuple[str, ...]] = {
    "delete": ("削除", "消す", "消さ", "消し", "捨て", "破棄", "消去", "抹消", "初期化", "上書き削除", "rm"),
    "send": ("送", "送信", "メール", "連絡", "転送", "共有", "伝え", "知らせ", "返信"),
    "pay": ("支払", "払う", "払わ", "振込", "振り込", "購入", "買う", "買わ", "決済", "発注", "課金"),
    "publish": ("公開", "プッシュ", "push", "アップロード", "掲載", "投稿", "外部に出", "リリース", "デプロイ"),
    "write": ("書き換", "変更", "編集", "上書き", "修正", "更新", "書き込", "追加", "改変", "直接触"),
    "schedule": ("予定", "招待", "会議を入れ", "日程", "カレンダー", "予約"),
    "run": ("実行", "インストール", "起動", "コマンド", "スクリプト"),
    "read": ("閲覧", "参照", "読む", "読み", "見る", "確認のために開", "検索", "照会"),
}

# Target words in a covenant, and what they look like inside tool arguments.
ALIASES: Dict[str, Tuple[str, ...]] = {
    "本番": ("prod", "production", "live", "本番"),
    "テスト": ("test", "staging", "stg", "dev", "sandbox", "テスト"),
    "開発": ("dev", "develop", "開発"),
    "顧客": ("client", "customer", "顧客", "お客"),
    "取引先": ("client", "vendor", "partner", "supplier", "取引先"),
    "個人情報": ("personal", "pii", "user", "patient", "student", "member", "customer", "氏名", "住所", "個人"),
    "患者": ("patient", "患者", "karte", "カルテ", "medical"),
    "カルテ": ("karte", "chart", "medical_record", "カルテ", "patient"),
    "生徒": ("student", "pupil", "生徒", "児童"),
    "成績": ("grade", "score", "成績", "評価"),
    "給与": ("salary", "payroll", "給与", "給料"),
    "人事": ("hr", "personnel", "人事", "employee"),
    "経理": ("accounting", "finance", "ledger", "経理", "会計"),
    "会計": ("accounting", "finance", "ledger", "会計"),
    "帳簿": ("ledger", "book", "帳簿"),
    "請求": ("invoice", "billing", "請求"),
    "見積": ("estimate", "quote", "見積"),
    "契約": ("contract", "契約"),
    "バックアップ": ("backup", "bak", "バックアップ"),
    "ログ": ("log", "ログ"),
    "ソースコード": ("src", "source", "repo", ".py", ".ts", ".js"),
    "main": ("main", "master"),
    "メインブランチ": ("main", "master"),
    "データベース": ("db", "database", "sql", ".sqlite", "データベース"),
    "データ": ("data", "db", ".csv", ".sqlite", "データ"),
    "原稿": ("draft", "manuscript", "原稿"),
    "プレスリリース": ("press", "release", "プレスリリース"),
    "SNS": ("twitter", "x.com", "instagram", "facebook", "sns"),
    "設定": ("config", "settings", ".env", "設定"),
    "秘密": ("secret", "key", "token", "password", ".env", "credential"),
    "パスワード": ("password", "passwd", "secret", "パスワード"),
    "鍵": ("key", "secret", "token", ".pem", "鍵"),
    "家族": ("family", "家族"),
    "研究": ("research", "experiment", "研究"),
    "実験": ("experiment", "raw", "実験"),
    "論文": ("paper", "manuscript", "論文"),
}

# Scope words: 社外 / 外部 mean "not our own domain".
EXTERNAL = ("社外", "外部", "外の", "第三者", "社外の", "組織外")
INTERNAL_HINTS = ("internal", "intra", "corp", "company", "local", "社内")

FORBID = re.compile(r"(しない|しません|ない$|ないこと|禁止|厳禁|してはいけな|ちゃいけな|してはならな|させない|NG|だめ|ダメ|行わない|触らない)")
ASK = re.compile(r"(確認|承認|許可を(得|取)|相談|聞いてから|伺って|事前に|了承)")
PERMIT = re.compile(r"(自由に|してよい|して良い|してもよい|しても良い|構わない|かまわない|問題ない|任せ|OK|可能)")
AMOUNT = re.compile(r"([0-9０-９,，]+)\s*(万)?\s*円\s*(を?超え|以上|より(高|多)|超|を上回)")


def _num(s: str) -> float:
    return float(s.translate(str.maketrans("０１２３４５６７８９，", "0123456789,")).replace(",", ""))


@dataclass
class Rule:
    index: int
    text: str
    effect: str                       # forbid | ask | permit
    classes: List[str]
    targets: List[str] = field(default_factory=list)
    external_only: bool = False
    amount_over: Optional[float] = None

    def as_dict(self) -> Dict[str, Any]:
        return {"index": self.index, "text": self.text, "effect": self.effect, "classes": self.classes,
                "targets": self.targets, "external_only": self.external_only, "amount_over": self.amount_over}


_GENERIC = {"人", "方", "もの", "物", "こと", "事", "場合", "際", "とき", "時", "前", "後", "全て", "すべて", "必ず", "自分", "私", "エージェント", "AI"}


def read_covenant(text: str, index: int = 0) -> Rule:
    t = text.strip()
    from .frames import read as _read
    main = _read(t)
    negated = bool(main and main.negated) or bool(FORBID.search(re.sub(r"[。．.!！]+$", "", t)))
    effect = "permit" if PERMIT.search(t) and not negated else \
        "ask" if ASK.search(t) else "forbid" if negated else "ask"
    classes = [c for c, ws in CLASS_WORDS.items() if any(w in t for w in ws)]
    targets = [k for k in ALIASES if k in t]
    # plain nouns the tables do not know are kept too: they are matched literally
    from .frames import read_all
    for fr in read_all(t):
        for n in (fr.patient, fr.recipient, fr.agent):
            core = n.split("の")[-1] if n else ""
            if n and len(n) >= 2 and not any(n == k or k in n for k in targets) \
                    and not re.search(r"[0-9０-９円]", n) and n not in _GENERIC and core not in _GENERIC \
                    and not any(e in n for e in EXTERNAL) \
                    and not any(w in n for ws in CLASS_WORDS.values() for w in ws):
                targets.append(n)
    m = AMOUNT.search(t)
    amount = None
    if m:
        amount = _num(m.group(1)) * (10000 if m.group(2) else 1)
        if "以上" in m.group(3):
            amount -= 0.5
    return Rule(index, t, effect, classes, targets, any(e in t for e in EXTERNAL), amount)


@dataclass
class Action:
    tool: str
    args: Dict[str, Any]
    classes: List[str]
    text: str
    amount: Optional[float]
    recipients: List[str]


def read_action(tool: str, args: Any) -> Action:
    if isinstance(args, str):
        try:
            args = json.loads(args)
        except ValueError:
            args = {"raw": args}
    text = json.dumps(args, ensure_ascii=False).lower()
    cmd = str(args.get("command", "") or args.get("cmd", "") or args.get("args", "")).lower()
    sql = str(args.get("sql", "") or args.get("query", "")).lower()
    cls: List[str] = []
    if tool == "delete_file":
        cls = ["delete"]
    elif tool == "write_file":
        cls = ["write"]
    elif tool == "send_email":
        cls = ["send"]
    elif tool == "http_post":
        cls = ["send", "publish"]
    elif tool == "upload_file":
        cls = ["publish", "send"]
    elif tool == "payment":
        cls = ["pay"]
    elif tool == "calendar_invite":
        cls = ["schedule", "send"]
    elif tool == "db_query":
        s = sql or text
        cls = ["delete"] if re.search(r"\b(delete|drop|truncate)\b", s) else \
            ["write"] if re.search(r"\b(update|insert|alter|create|replace)\b", s) else ["read"]
    elif tool == "git":
        s = cmd or text
        cls = ["publish"] if re.search(r"\bpush\b", s) else \
            ["delete"] if re.search(r"(reset --hard|clean -f|branch -d|branch -D|rm )", s) else \
            ["write"] if re.search(r"\b(commit|merge|rebase|checkout|add)\b", s) else ["read"]
        if "--force" in s or " -f" in s:
            cls.append("delete")
    elif tool == "shell":
        s = cmd or text
        cls = []
        if re.search(r"(^|[;&| ])(rm|rmdir|shred|truncate|unlink)\b|> /|dd if=", s):
            cls.append("delete")
        if re.search(r"\b(curl|wget|scp|rsync|sftp|mail|sendmail)\b", s):
            cls += ["send", "publish"] if re.search(r"(-x post|--data|-d |scp|rsync|sftp|upload|-t )", s) else ["read"]
        if re.search(r"\b(git push)\b", s):
            cls.append("publish")
        if re.search(r"\b(pip|npm|brew|apt|yum) (install|i)\b", s):
            cls.append("run")
        if re.search(r"\b(sed -i|mv|cp|tee|chmod|chown)\b|>>? ?\S", s):
            cls.append("write")
        if not cls:
            cls = ["run", "read"] if re.search(r"\b(cat|ls|grep|head|tail|less|find)\b", s) else ["run"]
    amount = None
    for k in ("amount", "price", "total", "金額"):
        if k in args:
            try:
                amount = float(str(args[k]).replace(",", ""))
            except ValueError:
                pass
    recips: List[str] = []
    for k in ("to", "cc", "bcc", "recipient", "attendees", "url", "email"):
        v = args.get(k)
        if isinstance(v, list):
            recips += [str(x).lower() for x in v]
        elif v:
            recips.append(str(v).lower())
    return Action(tool, args, cls, text, amount, recips)


def _target_hit(rule: Rule, act: Action) -> Tuple[bool, str]:
    if not rule.targets:
        return True, ""
    for t in rule.targets:
        for a in ALIASES.get(t, (t,)):
            if a.lower() in act.text:
                return True, "%s（%s）" % (t, a)
    return False, ""


def _external(act: Action, internal: Sequence[str]) -> bool:
    doms = [re.sub(r"^.*@", "", r).split("/")[2 if r.startswith("http") else 0] if r else "" for r in act.recipients]
    if not doms:
        return False
    return any(d and not any(h in d for h in list(INTERNAL_HINTS) + list(internal)) for d in doms)


def judge(rules: Sequence[Rule], tool: str, args: Any, internal: Sequence[str] = ()) -> Dict[str, Any]:
    act = read_action(tool, args)
    hits: List[Tuple[str, Rule, str]] = []
    for r in rules:
        if r.classes and not (set(r.classes) & set(act.classes)):
            continue
        ok, why = _target_hit(r, act)
        if r.external_only:
            if not _external(act, internal):
                continue
            ok, why = True, "社外の宛先"
        if not ok:
            continue
        if r.amount_over is not None:
            if act.amount is None or act.amount <= r.amount_over:
                continue
            why = "金額 %s > %s" % (act.amount, r.amount_over)
        hits.append((r.effect, r, why))
    for eff, verdict in (("forbid", "block"), ("ask", "ask")):
        for e, r, why in hits:
            if e == eff:
                return {"verdict": verdict, "rule": r.index, "covenant": r.text, "why": why,
                        "action": {"tool": tool, "classes": act.classes}}
    return {"verdict": "allow", "rule": -1, "action": {"tool": tool, "classes": act.classes},
            "permitted_by": [r.index for e, r, _ in hits if e == "permit"]}


def internal_domains(covenants: Sequence[str]) -> List[str]:
    """Domains the owner names as their own (社内 / 自社 … @example.co.jp)."""
    out = []
    for c in covenants:
        for d in re.findall(r"@([\w.-]+)", c):
            if any(w in c for w in ("社内", "自社", "うちの", "チーム内")):
                out.append(d.lower())
    return out


def regression() -> Dict[str, Any]:
    cov = ["本番のデータベースは削除しない。", "社外の人にはメールを送らない。",
           "1万円を超える支払いは確認してから行う。", "テスト環境のファイルは自由に消してよい。"]
    rules = [read_covenant(c, i) for i, c in enumerate(cov)]
    def v(tool, args):
        return judge(rules, tool, json.dumps(args), internal=["ourco.jp"])["verdict"]
    checks = {
        "block_prod_delete": v("delete_file", {"path": "/srv/prod/db/users.sqlite"}) == "block",
        "allow_test_delete": v("delete_file", {"path": "/srv/test/tmp.log"}) == "allow",
        "block_external_mail": v("send_email", {"to": "alice@client.com", "subject": "見積"}) == "block",
        "allow_internal_mail": v("send_email", {"to": "bob@ourco.jp", "subject": "議事録"}) == "allow",
        "ask_big_payment": v("payment", {"amount": 15000, "payee": "文具店"}) == "ask",
        "allow_small_payment": v("payment", {"amount": 3000, "payee": "文具店"}) == "allow",
        "block_sql_drop": v("db_query", {"sql": "DROP TABLE orders", "db": "prod"}) == "block",
        "allow_prod_read": v("db_query", {"sql": "SELECT * FROM orders", "db": "prod"}) == "allow",
    }
    return {"all_pass": all(checks.values()), **checks}
