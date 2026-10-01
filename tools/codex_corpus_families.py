"""Separate Japanese corpus families written by Codex agents: CODE and CONVERSATION.

Sibling of tools/codex_corpus.py (everyday prose). Same four layers that do
not trust the prompt (empty dir + read-only sandbox, event-stream tool gate,
shape gate, llm_authored source tag), but each family writes to its OWN
directory so the families never mix with the prose corpus or each other:
they become separate sovereigns later.

    code          <out>/items.jsonl       one record per item
                  {"text","family":"code","topic","lang","kind","source","sha"}
    conversation  <out>/utterances.jsonl  one record per utterance
                  {"text","family":"conversation","scene","turn","speaker",
                   "dialogue_id","source","sha","dialogue_sha"}

Each family walks a large topic grid in mixed radix. --shard N/M takes only
cells with index % M == N, so two machines never write the same cell.
Resuming: cells already KEPT in the ledger are skipped; --start sets where
the walk begins. The generation model is fixed: gpt-6-luna, effort low,
service tier priority (/fast).

    python3.11 tools/codex_corpus_families.py --family code \\
        --out ~/Projects/vera-corpus/codex/code --host local \\
        --shard 0/2 --batches 500 --workers 10
"""
from __future__ import annotations

import argparse
import fcntl
import io
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

MODEL, EFFORT, TIER = "gpt-6-luna", "low", "priority"
ALLOWED_ITEMS = {"agent_message", "reasoning"}

# ---------------------------------------------------------------- CODE grid
CODE_LANGS = ("Python", "JavaScript", "TypeScript", "Swift", "Rust", "Go",
              "SQL", "シェル(bash/zsh)", "C")
CODE_TOPICS = (
    "変数と型", "文字列の扱い", "リストと配列", "辞書・マップ", "条件分岐", "ループ",
    "関数と引数", "クロージャ", "クラスと構造体", "継承とインターフェース",
    "エラー処理と例外", "ファイルの読み書き", "JSONの読み書き", "日付と時刻",
    "正規表現", "ソートと検索", "再帰", "イテレータとジェネレータ", "非同期処理",
    "スレッドと並行処理", "メモリ管理", "ポインタと参照", "モジュールとパッケージ",
    "依存関係の管理", "ビルドとコンパイル", "単体テスト", "デバッグの手順",
    "ログの出し方", "性能測定と最適化", "HTTPリクエスト", "Web API設計",
    "データベースの結合(JOIN)", "インデックスとクエリ性能", "トランザクション",
    "gitのブランチ運用", "gitのコンフリクト解消", "gitの履歴操作(rebase/revert)",
    "環境変数と設定ファイル", "パスとディレクトリ操作", "プロセスとシグナル",
    "パーミッション", "文字コードとUnicode", "数値の誤差と丸め", "乱数",
    "コマンドライン引数の解析", "リファクタリング", "命名とコードの読みやすさ",
    "セキュリティ(入力検証・SQLインジェクション)", "キャッシュ", "コードレビューの観点",
)
CODE_KINDS = ("explanation", "snippet", "error_fix", "cli", "review", "qa")
CODE_STYLES = ("初心者向けにやさしく", "実務のメモとして簡潔に",
               "同僚に説明する口調で", "教科書風に丁寧に")
CODE_CONTEXTS = ("業務のWebサービス", "個人の小さなツール", "データ分析",
                 "スマホアプリ", "サーバー運用", "学校の課題", "オープンソースへの貢献",
                 "組込み・低レベル")

CODE_SCHEMA = {
    "type": "object",
    "properties": {"items": {"type": "array", "items": {
        "type": "object",
        "properties": {"kind": {"type": "string", "enum": list(CODE_KINDS)},
                       "text": {"type": "string"}},
        "required": ["kind", "text"], "additionalProperties": False}}},
    "required": ["items"], "additionalProperties": False}

CODE_PROMPT = """あなたはプログラミングに詳しい日本語の書き手です。次のテーマについて、日本語のテキストを{n}件、あなた自身の言葉で直接書いてください。

テーマ: {topic}
言語: {lang}
使われる場面: {context}
文体: {style}

各件には kind を付ける。kind は次のどれか。6種類をおおよそ均等に混ぜる:
- explanation: 概念や仕組みの説明（1〜4文）
- snippet: 短いコード片と、その動作を説明する日本語。コード中のコメントも日本語で書く。コードは本文 text にそのまま含めてよい
- error_fix: 実際に出るエラーメッセージ（原文のまま）と、その原因と直し方の日本語説明
- cli: コマンドの使い方（git・シェル・パッケージマネージャ・ビルドツールなど）とその意味の日本語説明
- review: コードレビューでの指摘やコメント（理由つき）
- qa: 質問と答えの組（「Q: … A: …」の形）

書き方:
- 本当に正しい内容だけを書く。存在しない関数・オプション・エラー文を作らない。
- 各件は独立して意味が通るようにする。同じ文型・同じ言い回しを繰り返さない。
- あなたはコマンドの実行・ファイル操作・検索を一切しない。頭の中の知識だけで書く。テンプレートや機械的な置き換えで件数を水増ししない。
- 出力は指定のJSONだけ。"""

# -------------------------------------------------------- CONVERSATION grid
CONV_SETTINGS = (
    "友達同士（学生）", "友達同士（社会人）", "家族（親と子）", "家族（夫婦）",
    "家族（祖父母と孫）", "兄弟姉妹", "職場（上司と部下）", "職場（同僚）",
    "職場（取引先との電話）", "店員と客（コンビニ）", "店員と客（飲食店）",
    "店員と客（服屋）", "店員と客（家電量販店）", "駅員と乗客", "医師と患者",
    "薬剤師と客", "先生と生徒", "先生と保護者", "大学の研究室", "部活の先輩と後輩",
    "近所の人", "役所の窓口", "ホテルのフロント", "タクシー運転手と客",
    "美容師と客", "不動産屋と客", "電話の問い合わせ窓口",
    "ユーザーとAIアシスタント（質問）", "ユーザーとAIアシスタント（依頼）",
    "ユーザーとAIアシスタント（聞き返し・確認）",
    "ユーザーとAIアシスタント（断り・できないことの説明）",
    "ユーザーとAIアシスタント（雑談・冗談・だじゃれ）",
)
CONV_TOPICS = (
    "予定の相談", "道案内", "買い物の相談", "料理", "天気", "体調", "お礼",
    "謝罪", "頼みごと", "断り", "誘い", "トラブルの相談", "勉強", "仕事の進み具合",
    "旅行の計画", "趣味", "お金の話", "引っ越し", "季節の行事", "ちょっとした冗談",
    "忘れ物", "遅刻", "誕生日", "ペット", "ニュースの感想", "機械の使い方",
)
CONV_STYLES = ("くだけた口調", "丁寧な口調", "敬語", "関西弁まじり",
               "テンポの速いやりとり", "ゆっくり落ち着いたやりとり")
CONV_SITUATIONS = ("朝", "昼休み", "夕方", "夜", "週末", "急いでいるとき",
                   "雨の日", "久しぶりに会ったとき")

CONV_SCHEMA = {
    "type": "object",
    "properties": {"dialogues": {"type": "array", "items": {
        "type": "object",
        "properties": {"turns": {"type": "array", "items": {
            "type": "object",
            "properties": {"speaker": {"type": "string"},
                           "text": {"type": "string"}},
            "required": ["speaker", "text"], "additionalProperties": False}}},
        "required": ["turns"], "additionalProperties": False}}},
    "required": ["dialogues"], "additionalProperties": False}

CONV_PROMPT = """あなたは日本語の会話を書く書き手です。次の設定で、自然な日本語の会話を{d}本、あなた自身の言葉で直接書いてください。合計でおよそ{n}発話にする（1本あたり6〜12発話）。

関係・場面: {setting}
話題: {topic}
状況: {situation}
口調: {style}

書き方:
- 実際の人がその場で話すような、自然で具体的な会話にする。相づち・言い直し・聞き返し・感謝・笑いなどを自然に含める。
- speaker には話し手のラベルを付ける（例: 「母」「息子」「店員」「客」「ユーザー」「アシスタント」、または名前）。1本の会話の中でラベルを一貫させる。
- AIアシスタントが出る場合、アシスタントは正確で誠実に答え、できないことはできないと言う。
- 会話ごとに話の流れや言い回しを変える。同じ型を繰り返さない。
- コマンド・プログラム・ファイル操作・検索は一切使わない。テンプレートや機械的な置き換えで会話を作らない。
- 出力は指定のJSONだけ。"""


def cell(family: str, i: int) -> dict:
    if family == "code":
        la = CODE_LANGS[i % len(CODE_LANGS)]
        r = i // len(CODE_LANGS)
        tp = CODE_TOPICS[r % len(CODE_TOPICS)]
        st = CODE_STYLES[(r // len(CODE_TOPICS)) % len(CODE_STYLES)]
        cx = CODE_CONTEXTS[(r // len(CODE_TOPICS) // len(CODE_STYLES)) % len(CODE_CONTEXTS)]
        return {"job": i, "topic": tp, "lang": la, "style": st, "context": cx}
    se = CONV_SETTINGS[i % len(CONV_SETTINGS)]
    r = i // len(CONV_SETTINGS)
    tp = CONV_TOPICS[r % len(CONV_TOPICS)]
    st = CONV_STYLES[(r // len(CONV_TOPICS)) % len(CONV_STYLES)]
    sx = CONV_SITUATIONS[(r // len(CONV_TOPICS) // len(CONV_STYLES)) % len(CONV_SITUATIONS)]
    return {"job": i, "setting": se, "topic": tp, "style": st, "situation": sx}


def grid_size(family: str) -> int:
    if family == "code":
        return (len(CODE_LANGS) * len(CODE_TOPICS) * len(CODE_STYLES)
                * len(CODE_CONTEXTS))
    return (len(CONV_SETTINGS) * len(CONV_TOPICS) * len(CONV_STYLES)
            * len(CONV_SITUATIONS))


_RUN = re.compile(r"[㐀-䶿一-鿿々〆ァ-ヺーA-Za-z0-9０-９_]+")


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


def free_gb(path: Path) -> float:
    return shutil.disk_usage(path).free / 1e9


def run_codex(prompt: str, schema: dict, codex: str, timeout: int):
    with tempfile.TemporaryDirectory(prefix="codex_family_") as tmp:
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
        items = Counter()
        for line in p.stdout.splitlines():
            try:
                e = json.loads(line)
            except ValueError:
                continue
            it = (e.get("item") or {}).get("type")
            if it:
                items[it] += 1
        rec = {"seconds": round(time.time() - t0, 1), "items": dict(items),
               "exit": p.returncode}
        tools = {k: v for k, v in items.items() if k not in ALLOWED_ITEMS}
        if tools:
            return {**rec, "verdict": "REJECTED", "reason": "TOOL_USE",
                    "tools": tools}, None
        try:
            data = json.loads((tmp / "last.json").read_text())
        except Exception:
            err = (p.stderr or "")[-300:]
            return {**rec, "verdict": "REJECTED", "reason": "NO_SCHEMA_OUTPUT",
                    "stderr_tail": err}, None
    return rec, data


def run_code(job: dict, n: int, codex: str, timeout: int):
    prompt = CODE_PROMPT.format(n=n, topic=job["topic"], lang=job["lang"],
                                style=job["style"], context=job["context"])
    rec, data = run_codex(prompt, CODE_SCHEMA, codex, timeout)
    if data is None:
        return rec, []
    out = []
    for it in data.get("items", []):
        t = (it.get("text") or "").strip()
        k = it.get("kind")
        if k in CODE_KINDS and 10 <= len(t) <= 2000 and re.search(r"[ぁ-ん]", t):
            out.append({"kind": k, "text": t})
    bad = shape_gate([o["text"] for o in out], 0.8, 4)
    if bad:
        return {**rec, "verdict": "REJECTED", "reason": bad}, []
    return {**rec, "verdict": "KEPT"}, out


def run_conv(job: dict, n: int, codex: str, timeout: int):
    d = max(4, round(n / 8))
    prompt = CONV_PROMPT.format(d=d, n=n, setting=job["setting"],
                                topic=job["topic"], style=job["style"],
                                situation=job["situation"])
    rec, data = run_codex(prompt, CONV_SCHEMA, codex, timeout)
    if data is None:
        return rec, []
    dias = []
    for dia in data.get("dialogues", []):
        turns = [{"speaker": (t.get("speaker") or "").strip()[:20],
                  "text": (t.get("text") or "").strip()}
                 for t in dia.get("turns", [])]
        turns = [t for t in turns if t["speaker"] and 1 <= len(t["text"]) <= 400]
        if len(turns) >= 2 and len({t["speaker"] for t in turns}) >= 2:
            dias.append(turns)
    # template check on whole dialogues (utterances like "はい" legitimately repeat)
    bad = shape_gate([" / ".join(t["text"] for t in ts) for ts in dias], 0.9, 1)
    if bad:
        return {**rec, "verdict": "REJECTED", "reason": bad}, []
    return {**rec, "verdict": "KEPT"}, dias


def sha(s: str) -> str:
    return hashlib.sha1(s.encode()).hexdigest()[:12]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--family", choices=("code", "conversation"), required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--host", required=True, help="machine tag, e.g. local / pro")
    ap.add_argument("--batches", type=int, default=100)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--per-batch", type=int, default=100)
    ap.add_argument("--start", type=int, default=0, help="grid index to begin the walk")
    ap.add_argument("--shard", default="0/1", help="N/M: only cells with index %% M == N")
    ap.add_argument("--codex", default="codex", help="path to the codex binary")
    ap.add_argument("--timeout", type=int, default=900)
    ap.add_argument("--min-free-gb", type=float, default=5.0,
                    help="stop launching batches below this free disk space")
    a = ap.parse_args()

    sn, sm = (int(x) for x in a.shard.split("/"))
    out = Path(a.out).expanduser()
    out.mkdir(parents=True, exist_ok=True)
    ledger = out / "ledger.jsonl"
    corpus = out / ("items.jsonl" if a.family == "code" else "utterances.jsonl")
    seen = set()
    if corpus.exists():
        for line in corpus.open(encoding="utf-8"):
            try:
                r = json.loads(line)
            except ValueError:
                continue
            seen.add(r.get("dialogue_sha") or r["sha"])
    done = set()
    if ledger.exists():
        for line in ledger.open(encoding="utf-8"):
            try:
                r = json.loads(line)
            except ValueError:
                continue
            if r.get("verdict") == "KEPT":
                done.add(r["job"])
    size = grid_size(a.family)
    jobs, i = [], a.start
    while len(jobs) < a.batches and i < a.start + 50 * size:
        if i % sm == sn and i not in done:
            jobs.append(cell(a.family, i))
        i += 1
    print(json.dumps({"family": a.family, "grid": size, "jobs": len(jobs),
                      "first": jobs[0]["job"] if jobs else None,
                      "last": jobs[-1]["job"] if jobs else None,
                      "skipped_done": len(done)}, ensure_ascii=False),
          file=sys.stderr, flush=True)

    lock = threading.Lock()
    tally = Counter()
    stop = threading.Event()

    def one(job):
        if stop.is_set():
            return
        if free_gb(out) < a.min_free_gb:
            stop.set()
            print("DISK_GUARD stop: free %.1f GB" % free_gb(out), file=sys.stderr, flush=True)
            return
        bid = "%s-%s-b%05d" % (a.host, a.family[:4], job["job"])
        src = "llm_authored:codex:" + bid
        if a.family == "code":
            rec, got = run_code(job, a.per_batch, a.codex, a.timeout)
        else:
            rec, got = run_conv(job, a.per_batch, a.codex, a.timeout)
        with lock:
            kept = 0
            if rec["verdict"] == "KEPT":
                f = io.StringIO()
                if True:
                    if a.family == "code":
                        for o in got:
                            h = sha(o["text"])
                            if h in seen:
                                continue
                            seen.add(h)
                            kept += 1
                            f.write(json.dumps({
                                "text": o["text"], "family": "code",
                                "topic": job["topic"], "lang": job["lang"],
                                "kind": o["kind"], "style": job["style"],
                                "context": job["context"],
                                "source": src, "sha": h}, ensure_ascii=False) + "\n")
                    else:
                        for di, turns in enumerate(got):
                            dsha = sha("\n".join(t["speaker"] + ":" + t["text"] for t in turns))
                            if dsha in seen:
                                continue
                            seen.add(dsha)
                            did = "%s-d%02d" % (bid, di)
                            for ti, t in enumerate(turns):
                                kept += 1
                                f.write(json.dumps({
                                    "text": t["text"], "family": "conversation",
                                    "scene": job["setting"] + "／" + job["topic"] + "／" + job["situation"],
                                    "style": job["style"], "turn": ti,
                                    "speaker": t["speaker"], "dialogue_id": did,
                                    "source": src, "sha": sha(t["text"]),
                                    "dialogue_sha": dsha}, ensure_ascii=False) + "\n")
                if f.getvalue():
                    with corpus.open("a", encoding="utf-8") as cf:
                        fcntl.flock(cf, fcntl.LOCK_EX)
                        cf.write(f.getvalue())
                        cf.flush()
                        fcntl.flock(cf, fcntl.LOCK_UN)
            rec["kept"] = kept
            with ledger.open("a", encoding="utf-8") as lf:
                fcntl.flock(lf, fcntl.LOCK_EX)
                lf.write(json.dumps({"batch": bid, **job, **rec}, ensure_ascii=False) + "\n")
                lf.flush()
                fcntl.flock(lf, fcntl.LOCK_UN)
            tally[rec["verdict"] if rec["verdict"] == "KEPT" else rec["reason"]] += 1
            tally["records"] += kept
            print(bid, rec["verdict"], rec.get("reason", ""), kept, rec.get("seconds"),
                  file=sys.stderr, flush=True)

    with ThreadPoolExecutor(a.workers) as ex:
        list(ex.map(one, jobs))
    print(json.dumps(dict(tally), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
