"""Everyday Japanese written by Codex agents — authored, never programmed.

The point of the corpus is that a writer wrote each sentence. A loop over a
template ("{物}は{性質}。" x 10,000) would hand Vera the template's grammar
and the template author's list, not the implicit everyday knowledge the
sentences are supposed to carry — and it would do it at a volume that
drowns everything else. So programmatic generation is not discouraged, it
is made unacceptable, in four layers that do not trust the prompt:

    1  cannot    each agent runs in an EMPTY directory, read-only sandbox,
                 browser/computer/apps disabled, ephemeral; the only output
                 is its final message, shaped by a JSON schema
    2  evidence  the JSONL event stream is read; ANY item other than the
                 agent's message and its reasoning (a command, a file
                 change, a tool or web call) rejects the whole batch
    3  shape     sentences are reduced to skeletons (content runs -> X);
                 a batch whose skeletons repeat like a template is rejected
    4  source    every kept sentence carries llm_authored:codex:<batch>, so
                 the store can always tell it from human-written text

Every batch, kept or rejected, is one line in the ledger with its reason.

The commonsense bank (tools/commonsense_bank_2026-08-14.json) predates this
corpus and is never shown to an agent: topics are everyday SCENES, not the
bank's subjects, so the bank still measures reading and not dictation.

    python3.11 tools/codex_corpus.py --batches 40 --workers 4
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
import tempfile
import threading
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

OUT = Path.home() / "Projects" / "vera-corpus" / "codex"

#: Scenes, not facts. Deliberately not the bank's subjects.
SCENES = (
    "台所", "朝ごはん", "買い物", "市場", "天気の変化", "季節の移り変わり",
    "掃除", "洗濯", "風呂", "寝る前", "通勤・通学", "学校の教室", "子育て",
    "風邪をひいた日", "小さなけが", "庭仕事", "畑", "ペット", "動物園",
    "道具の手入れ", "キャンプ", "海辺", "山歩き", "雪の日", "雨の日",
    "夏祭り", "運動会", "料理の失敗", "引っ越し", "工作", "駅", "病院",
    "公園", "川", "台風", "停電", "古い家", "おばあちゃんの家", "冬の朝",
    "夕立",
)

#: Item types allowed in the event stream. Anything else is a tool.
ALLOWED_ITEMS = {"agent_message", "reasoning"}

SCHEMA = {"type": "object",
          "properties": {"sentences": {"type": "array",
                                       "items": {"type": "string"}}},
          "required": ["sentences"], "additionalProperties": False}

PROMPT = """あなたは日本語の書き手です。次の場面について、自然な日本語の文を{n}文、あなた自身の言葉で直接書いてください。

場面: {scene}（視点: {angle}）

書き方:
- 物の性質（色・味・温度・硬さ・重さ・におい・音）や、行為とその結果、原因と結果が、文の中に自然に含まれるように書く。
- 定義や説明文ではなく、生活の中で実際に書かれるような文にする。
- 1文ずつ独立して意味が通るようにする。同じ文型を繰り返さない。
- コマンド・プログラム・ファイル操作・検索は一切使わない。テンプレートや機械的な置き換えで文を作らない。
- 出力は指定のJSONだけ。"""

#: Demand-driven mode: the store names words whose relations were written
#: only once (candidate seat). A second, independent sentence promotes them;
#: the scene grid mostly re-writes what is already held. The bank's subjects
#: are never targets, so the bank still measures reading, not dictation.
TARGET_PROMPT = """あなたは日本語の書き手です。次の語それぞれについて、その語が実際に出てくる自然な日本語の文を{k}文ずつ、あなた自身の言葉で直接書いてください。

語: {words}

書き方:
- その物・事の性質（色・味・温度・硬さ・重さ・におい・音・形）や、使い方、原因と結果が、文の中に自然に含まれるように書く。
- 生活の中で実際に書かれるような文にする。定義文を並べない。同じ文型を繰り返さない。
- 本当にそうであることだけを書く。架空の性質を作らない。
- コマンド・プログラム・ファイル操作・検索は一切使わない。テンプレートや機械的な置き換えで文を作らない。
- 出力は指定のJSONだけ。"""

ANGLES = ("子どもの目", "大人の目", "高齢者の目", "失敗談", "手順の途中",
          "感覚の描写", "会話の地の文", "日記")

#: The grid for large runs. Scenes x places x times x voices, walked in
#: mixed radix so thousands of batches never repeat a combination — the
#: same scene asked twice converges on the same sentences.
GRID_SCENES = SCENES + (
    "洗面所", "玄関", "ベランダ", "押し入れ", "車の中", "バス", "電車", "自転車",
    "コンビニ", "パン屋", "八百屋", "魚屋", "肉屋", "薬局", "郵便局", "銀行の窓口",
    "図書館", "美術館", "映画館", "体育館", "プール", "スキー場", "温泉", "旅館",
    "工場", "工事現場", "倉庫", "農家", "漁港", "牧場", "果樹園", "田んぼ",
    "森", "滝", "洞窟", "砂漠の旅", "島", "港町", "雪国", "南の島",
    "火事", "地震", "大雨", "猛暑", "寒波", "霧", "雷", "虹", "満月", "星空",
    "焚き火", "炭火焼き", "パン作り", "漬物", "味噌汁", "お弁当", "おやつ", "果物狩り",
    "氷屋", "製氷", "鍛冶", "陶芸", "木工", "裁縫", "編み物", "染め物",
    "赤ちゃんの世話", "介護", "看病", "歯医者", "床屋", "美容院", "銭湯", "洗車",
    "犬の散歩", "猫の世話", "金魚", "虫取り", "鳥の巣", "田植え", "稲刈り", "雪かき",
    "お正月", "節分", "ひな祭り", "花見", "梅雨", "お盆", "紅葉狩り", "大掃除",
    "試験前夜", "部活", "遠足", "修学旅行", "卒業式", "入学式", "誕生日", "結婚式",
    "楽器の練習", "合唱", "太鼓", "花火", "手紙", "電話", "停電の夜", "断水",
)
GRID_TIMES = ("早朝", "昼", "夕方", "夜", "真冬", "真夏", "雨上がり", "晴天")
GRID_VOICES = ANGLES + ("手紙", "随筆", "説明の途中", "思い出話")

_RUN = re.compile(r"[㐀-䶿一-鿿々〆ァ-ヺーA-Za-z0-9０-９]+")


def skeleton(s: str) -> str:
    return _RUN.sub("X", s)


def shape_gate(sents: list) -> str | None:
    """Reject template-shaped batches. None = pass."""
    if not sents:
        return "EMPTY"
    sk = Counter(skeleton(s) for s in sents)
    if len(sk) / len(sents) < 0.8:
        return "TEMPLATE_SKELETONS_%d_of_%d" % (len(sk), len(sents))
    if sk.most_common(1)[0][1] > 3:
        return "TEMPLATE_REPEAT_%d" % sk.most_common(1)[0][1]
    return None


def run_batch(job: dict, model: str | None, effort: str | None = None,
              tier: str | None = None) -> dict:
    with tempfile.TemporaryDirectory(prefix="codex_corpus_") as tmp:
        tmp = Path(tmp)
        work = tmp / "empty"
        work.mkdir()
        (tmp / "schema.json").write_text(json.dumps(SCHEMA))
        cmd = ["codex", "exec", "--skip-git-repo-check", "--ephemeral",
               "-s", "read-only", "--disable", "browser_use",
               "--disable", "computer_use", "--disable", "apps",
               "-C", str(work), "--output-schema", str(tmp / "schema.json"),
               "--json", "-o", str(tmp / "last.json")]
        if model:
            cmd += ["-m", model]
        if effort:
            cmd += ["-c", "model_reasoning_effort=" + json.dumps(effort)]
        if tier:
            cmd += ["-c", "service_tier=" + json.dumps(tier)]
        if job.get("words"):
            prompt = TARGET_PROMPT.format(k=job["k"], words="、".join(job["words"]))
        else:
            prompt = PROMPT.format(n=job["n"], scene=job["scene"], angle=job["angle"])
        t0 = time.time()
        try:
            p = subprocess.run(cmd + [prompt], cwd=work, capture_output=True,
                               text=True, timeout=600, stdin=subprocess.DEVNULL)
        except subprocess.TimeoutExpired:
            return {**job, "verdict": "REJECTED", "reason": "TIMEOUT"}
        items = Counter()
        for line in p.stdout.splitlines():
            try:
                e = json.loads(line)
            except ValueError:
                continue
            it = (e.get("item") or {}).get("type")
            if it:
                items[it] += 1
        rec = {**job, "seconds": round(time.time() - t0, 1),
               "items": dict(items), "exit": p.returncode}
        tools = {k: v for k, v in items.items() if k not in ALLOWED_ITEMS}
        if tools:
            return {**rec, "verdict": "REJECTED", "reason": "TOOL_USE", "tools": tools}
        try:
            sents = json.loads((tmp / "last.json").read_text())["sentences"]
        except Exception:
            return {**rec, "verdict": "REJECTED", "reason": "NO_SCHEMA_OUTPUT"}
    sents = [s.strip() for s in sents if isinstance(s, str)
             and 6 <= len(s.strip()) <= 120 and re.search(r"[ぁ-ん]", s)]
    bad = shape_gate(sents)
    if bad:
        return {**rec, "verdict": "REJECTED", "reason": bad}
    return {**rec, "verdict": "KEPT", "sentences": sents}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--batches", type=int, default=8)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--per-batch", type=int, default=40)
    ap.add_argument("--model", default=None)
    ap.add_argument("--tier", default=None, help="service tier, e.g. priority (/fast)")
    ap.add_argument("--effort", default=None,
                    help="reasoning effort; low is enough to write sentences")
    ap.add_argument("--out", default=str(OUT))
    ap.add_argument("--targets", default=None,
                    help="JSON list of words to write about (demand-driven)")
    ap.add_argument("--per-word", type=int, default=3)
    ap.add_argument("--grid", action="store_true",
                    help="walk the large scene x time x voice grid")
    ap.add_argument("--host", default="",
                    help="tag written into each source, e.g. pro")
    ap.add_argument("--start", type=int, default=None,
                    help="job index to start from (default: after the ledger)")
    a = ap.parse_args()

    out = Path(a.out).expanduser()
    out.mkdir(parents=True, exist_ok=True)
    ledger, corpus = out / "ledger.jsonl", out / "sentences.jsonl"
    seen = set()
    if corpus.exists():
        for line in corpus.open(encoding="utf-8"):
            seen.add(json.loads(line)["text"])
    start = a.start
    if start is None:
        start = sum(1 for _ in ledger.open()) if ledger.exists() else 0
    jobs = []
    targets = json.loads(Path(a.targets).read_text()) if a.targets else None
    per = max(1, a.per_batch // a.per_word)
    for i in range(start, start + a.batches):
        if targets:
            ws = targets[(i * per) % len(targets):(i * per) % len(targets) + per]
            jobs.append({"job": i, "scene": "target", "angle": "target",
                         "words": ws, "k": a.per_word, "n": a.per_batch})
            continue
        if a.grid:
            sc = GRID_SCENES[i % len(GRID_SCENES)]
            r = i // len(GRID_SCENES)
            tm = GRID_TIMES[r % len(GRID_TIMES)]
            vo = GRID_VOICES[(r // len(GRID_TIMES)) % len(GRID_VOICES)]
            jobs.append({"job": i, "scene": sc + "（" + tm + "）",
                         "angle": vo, "n": a.per_batch})
        else:
            jobs.append({"job": i, "scene": SCENES[i % len(SCENES)],
                         "angle": ANGLES[(i // len(SCENES)) % len(ANGLES)],
                         "n": a.per_batch})
    lock = threading.Lock()
    tally = Counter()

    def one(job):
        r = run_batch(job, a.model, a.effort, a.tier)
        bid = (a.host + "-" if a.host else "") + "b%05d" % job["job"]
        with lock:
            kept = 0
            if r["verdict"] == "KEPT":
                with corpus.open("a", encoding="utf-8") as f:
                    for s in r.pop("sentences"):
                        if s in seen:
                            continue
                        seen.add(s)
                        kept += 1
                        f.write(json.dumps({
                            "text": s, "source": "llm_authored:codex:" + bid,
                            "scene": job["scene"], "angle": job["angle"],
                            "words": job.get("words"),
                            "sha": hashlib.sha1(s.encode()).hexdigest()[:12]},
                            ensure_ascii=False) + "\n")
            r["kept"] = kept
            with ledger.open("a", encoding="utf-8") as f:
                f.write(json.dumps({"batch": bid, **r}, ensure_ascii=False) + "\n")
            tally[r["verdict"] if r["verdict"] == "KEPT" else r["reason"]] += 1
            tally["sentences"] += kept
            print(bid, r["verdict"], r.get("reason", ""), kept, file=sys.stderr, flush=True)

    with ThreadPoolExecutor(a.workers) as ex:
        list(ex.map(one, jobs))
    print(json.dumps(dict(tally), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
