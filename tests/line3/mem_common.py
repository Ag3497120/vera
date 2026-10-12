"""Shared helpers of the memory tests (tests/line3/test_mem_*.py): a store on a temp folder, writes, the probes of docs/LINE3_LOOM_MEMORY_DESIGN.md 2 and the
deterministic filler that grows a memory to a given number of seated units."""
import json
import os

from verantyx.loom import memnotes as mn
from verantyx.loom.memory import MemStore

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
STUB = mn.StubSelfQuestion()

# Pr3 / Pr4 / Pr6 of the design, as sentences
SEEDS = ["認証の前提は決済", "田中の担当は認証", "会議は東京で行う"]                                   # 3 sentences, 9 units: the history the probes need
PROBE_REVERSAL = "決済の前提は認証"
PROBE_SQ = "田中の担当は決済"
PROBE_NEW_RELATION = "東京の天気は晴れ"
PROBE_SHAPE = "東京で会議を開く"
SECOND_TOKYO = "研修は東京で行う"                                                      # the second sentence that gives 東京+で an adhesion of 2

_X = "営業 開発 総務 経理 広報 人事 法務 品質 企画 製造 物流 購買 設計 保守 監査 研究 調達 販売 労務 財務 教育 安全 環境 秘書".split()
_Y = "予算 人数 場所 目標 備品 機材 規模 時期 方式 手順 窓口 分類 範囲 水準".split()
_Z = "白色 赤色 青色 黒色 緑色 黄色 桃色 灰色 銀色 金色".split()


def filler(n_sentences):
    """n distinct 「Xの Y は Z」 sentences, every (X, Y) used once (so no two fillers answer one question), disjoint from the probe vocabulary: 3 units each."""
    out = []
    for k in range(n_sentences):
        x, y = _X[k % len(_X)], _Y[(k // len(_X)) % len(_Y)]
        out.append("%sの%sは%s" % (x, y, _Z[k % len(_Z)]))
    assert len(set(s[:s.index("は")] for s in out)) == len(out), "filler repeats a (X, Y)"
    return out


def new_store(tmp_path, name="mem", store_id="t"):
    return MemStore(str(tmp_path / name), store_id)


def session(tmp_path, name="mem", **kw):
    return new_store(tmp_path, name).begin("test-model", **kw)


def write_all(sess, sentences):
    return [sess.write(s) for s in sentences]


def notes_of(res):
    return [n["type"] for n in res.get("notes", [])]


def ledger_rows(sess_or_dir):
    d = getattr(sess_or_dir, "ledger", None)
    d = d.dir if d is not None else sess_or_dir
    with open(os.path.join(str(d), "ops.jsonl"), encoding="utf-8") as f:
        return [json.loads(ln) for ln in f if ln.strip()]
