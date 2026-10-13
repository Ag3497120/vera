"""PUB-M5/M6 timing (designer decision L-PUB-40): how long does a write take as a story grows, and does the INCREMENTAL index equal the FULL REBUILD byte for byte?

A synthetic long story (deterministic, seed-free generator: 「X<n> の <attribute> は <value>」 over 12 subjects x 40 numbers x 8 attributes, plus a change clause every 25th sentence and a nest declaration per
session), written into a real mem.v4 store, one session per `--session` writes (default 200).  Reported: the seconds per write in batches of 100 writes (wall clock of the `write` call), the same for a
`recall`, a cProfile of the last 20 writes (cumulative seconds of the functions that matter), and -- on the store at `--equal-at` sentences (default 300; the rebuild builds one corpus per sentence) -- that
`build_index(H, declarations, marks, bridges)` has the same canonical JSON and the same sha as the index the session folded.

  PYTHONPATH=. PYTHONHASHSEED=0 python experiments/line3/pub/m5m6/perf.py [--n 1000] [--session 200] [--equal-at 300]      -> perf.{json,md}
(Single process: it times; --workers is accepted for the common interface and ignored.)
"""
from __future__ import annotations

import argparse
import cProfile
import io
import pstats
import shutil
import tempfile
import time
from typing import Any, Dict, List, Optional, Sequence

import common as K
from common import mem, mask
from verantyx.loom import memcross as mx
from verantyx.loom.state import canonical

SUBJECTS = ["認証モジュール", "決済画面", "検索機能", "通知サービス", "管理画面", "課金基盤", "画像変換", "ログ収集", "配信基盤", "予約画面", "在庫連携", "請求書発行"]
ATTRS = ["担当", "期限", "予算", "開催地", "優先度", "公開日", "試験日", "容量"]
PEOPLE = ["田中", "佐藤", "鈴木", "高橋", "伊藤", "渡辺"]
CITIES = ["大阪", "京都", "東京", "福岡"]


def sentence(i: int) -> str:
    """The i-th sentence: a pure function of i (a linear congruence picks the subject, number and attribute)."""
    a = (i * 7 + 3) % len(ATTRS)
    s = SUBJECTS[(i * 5 + 1) % len(SUBJECTS)] + str((i * 11 + 2) % 40 + 1)
    attr = ATTRS[a]
    if attr == "担当":
        v = PEOPLE[(i * 3) % len(PEOPLE)] + str(i % 9 + 1)
    elif attr in ("期限", "公開日", "試験日"):
        v = "%d月%d日" % ((i * 13) % 12 + 1, (i * 17) % 28 + 1)
    elif attr == "予算":
        v = "%d万円" % ((i * 19) % 500 + 1)
    elif attr == "開催地":
        v = CITIES[(i * 3) % len(CITIES)] + str(i % 9 + 1)
    elif attr == "優先度":
        v = ("高", "中", "低")[i % 3]
    else:
        v = "%dGB" % ((i * 23) % 512 + 1)
    if i % 25 == 24:
        return "%sの%sは%sから%sに変更。" % (s, attr, v, v + "改")
    return "%sの%sは%s。" % (s, attr, v)


def run(n: int, per: int, equal_at: int) -> Dict[str, Any]:
    tmp = tempfile.mkdtemp(prefix="m5m6_perf_")
    try:
        st = mem.MemStore(tmp + "/store", "p")
        batches: List[Dict[str, Any]] = []
        t_batch, k_batch, accepted = 0.0, 0, 0
        written, session = 0, 0
        equal: Optional[Dict[str, Any]] = None
        prof_out = ""
        recall_s: List[float] = []
        s = None
        while written < n:
            if s is not None:
                s.commit()
            s = st.begin("perf", profile=mem.PROFILE_V4)
            session += 1
            s.call("declare_topic", {"text": "基盤整備%d" % session})
            for _ in range(per):
                if written >= n:
                    break
                if written == n - 20:
                    pr = cProfile.Profile()
                    pr.enable()
                t0 = time.perf_counter()
                r = s.call("write", {"text": sentence(written)})
                dt = time.perf_counter() - t0
                accepted += 1 if r.get("ok") else 0
                t_batch += dt
                k_batch += 1
                written += 1
                if k_batch == 100 or written == n:
                    batches.append({"writes_so_far": written, "accepted_so_far": accepted, "seconds_per_write": round(t_batch / k_batch, 4)})
                    t_batch, k_batch = 0.0, 0
                if written % 250 == 0:
                    t0 = time.perf_counter()
                    s.call("recall", {"question": "%sの%sはいつですか" % (SUBJECTS[0] + "1", "期限")})
                    recall_s.append(round(time.perf_counter() - t0, 4))
                if written == equal_at:
                    ix = s.run.builder.index()
                    full = mx.build_index(s.run.rows, s.run.decls, s.run.superseded, bridges=s.run.bridge_log)
                    equal = {"sentences": len(s.run.rows), "same_json": canonical(ix.to_obj()) == canonical(full.to_obj()), "same_sha": ix.index_sha == full.index_sha, "sha": ix.index_sha,
                             "assemble_equals_canonical": s.run.builder._assemble() == canonical(ix.to_obj())}
        pr.disable()
        buf = io.StringIO()
        pstats.Stats(pr, stream=buf).sort_stats("cumulative").print_stats(25)
        prof_out = buf.getvalue()
        s.commit()
        return {"n": n, "per_session": per, "sessions": session, "accepted": accepted, "batches": batches, "recall_seconds_every_250": recall_s, "incremental_equals_rebuild": equal, "profile_last_20_writes": prof_out}
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def md(res: dict) -> str:
    out = ["# PUB-M5/M6 — 書き込みの時間（L-PUB-40）", "", "%d 文（%d セッション、受理 %d）。100 書き込みごとの 1 書き込みあたりの秒:" % (res["n"], res["sessions"], res["accepted"]), "", "| 書き込み済み | 受理済み | 秒/書き込み |", "|---|---|---|"]
    for b in res["batches"]:
        out.append("| %d | %d | %s |" % (b["writes_so_far"], b["accepted_so_far"], b["seconds_per_write"]))
    out += ["", "recall の秒（250 書き込みごと）: %s" % res["recall_seconds_every_250"], "", "増分の索引 = 作り直し: %s" % res["incremental_equals_rebuild"], "", "最後の 20 書き込みの cProfile（累積）:", "", "```", res["profile_last_20_writes"], "```", ""]
    return "\n".join(out)


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--n", type=int, default=1000)
    ap.add_argument("--session", type=int, default=200)
    ap.add_argument("--equal-at", type=int, default=300)
    ap.add_argument("--workers", type=int, default=K.DEFAULT_WORKERS)
    ns = ap.parse_args(argv)
    res = run(ns.n, ns.session, ns.equal_at)
    K.write_json(__import__("os").path.join(K.OUT, "perf.json"), res)
    K.write_text(__import__("os").path.join(K.OUT, "perf.md"), md(res))
    print(md(res))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
