#!/usr/bin/env python3
"""W1-f: 残っている失敗テスト 124 件の原因切り分けの再生成スクリプト（直さない）。

製品コード・テストは変更しない。書くのは artifacts/w1-f/** と docs/FAILURE_TRIAGE_W1-f.md だけ。
過去コミット・修正案の複写は必ずツリー外の一時ディレクトリで行う（git archive で展開）。

サブコマンド:
  baseline   全体実行（F5 の作業前/後）。--phase before|after
  isolate    124 件を 1 件ずつ別プロセスで実行
  history    どのコミットで落ち始めたか（二分探索＋両端の実測）
  probe      テスト側だけ機械的に変えた複写で通るか
  fixcheck   束ごとの修正差分を一時複写に当てて通ることを示す（F2）
  qf2        w_question_forms2 の 34 件の切り分け（F3）
  report     decisions.jsonl 等から triage.jsonl・bundles・tickets・文書の生成ブロックを作る
  check      文書の生成ブロックが再生成とバイト一致するか検査（F6）

生成物は決定的（時刻・一時パス・所要秒を入れない）。所要秒は timings.txt に分ける。
Python は /Users/motonisihikoudai/vera-wiring/env/bin/python（3.11）を想定。
"""
from __future__ import annotations

import argparse
import ast
import concurrent.futures as cf
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "artifacts" / "w1-f"
DOC = ROOT / "docs" / "FAILURE_TRIAGE_W1-f.md"
BL_FILE = Path("/Users/motonisihikoudai/Projects/vera-impl/baselines/dev_075d486_failures.txt")
PY = "/Users/motonisihikoudai/vera-wiring/env/bin/python"
DEV = "075d486"
HOME = os.environ.get("HOME", "/Users/motonisihikoudai")
CACHE_ROOT = Path(os.environ.get("W1F_CACHE", str(Path(tempfile.gettempdir()) / "w1f_cache")))

# --------------------------------------------------------------------------
# 選択プラグイン（nodeid の完全一致で項目を選ぶ。非 ASCII の parametrize ID を CLI で選べない問題 P1 の回避）
# --------------------------------------------------------------------------
PLUGIN_SRC = r'''
import json, os, sys

_state = {"outcomes": {}, "collect_errors": [], "not_collected": [], "violations": []}


def _want():
    p = os.environ.get("W1F_SEL")
    if not p:
        return None
    return [l for l in open(p, encoding="utf-8").read().split("\n") if l]


def pytest_collectreport(report):
    if report.failed:
        _state["collect_errors"].append(report.nodeid)


def pytest_collection_modifyitems(config, items):
    want = _want()
    if want is None:
        return
    ws = set(want)
    keep = [i for i in items if i.nodeid in ws]
    drop = [i for i in items if i.nodeid not in ws]
    if drop:
        config.hook.pytest_deselected(items=drop)
    seen = {i.nodeid for i in keep}
    _state["not_collected"] = sorted(ws - seen)
    items[:] = keep


def pytest_runtest_logreport(report):
    nid = report.nodeid
    cur = _state["outcomes"].get(nid)
    if report.when == "call":
        if hasattr(report, "wasxfail"):
            o = "XFAIL" if report.outcome == "skipped" else ("XPASS" if report.outcome == "passed" else "FAIL")
        elif report.outcome == "passed":
            o = "PASS"
        elif report.outcome == "failed":
            o = "FAIL"
        else:
            o = "SKIP"
        _state["outcomes"][nid] = o
    elif report.when in ("setup", "teardown"):
        if report.outcome == "failed":
            _state["outcomes"][nid] = "ERROR"
        elif report.outcome == "skipped" and report.when == "setup":
            if hasattr(report, "wasxfail"):
                _state["outcomes"][nid] = "XFAIL"
            elif cur is None:
                _state["outcomes"][nid] = "SKIP"


def pytest_sessionfinish(session, exitstatus):
    tree = os.path.realpath(os.environ.get("W1F_TREE", os.getcwd()))
    for name, mod in sorted(list(sys.modules.items())):
        if name == "verantyx" or name.startswith("verantyx."):
            f = getattr(mod, "__file__", None)
            if f is None:
                for p in getattr(mod, "__path__", []) or []:
                    f = p
            if f and not os.path.realpath(f).startswith(tree + os.sep):
                _state["violations"].append([name, f])
    out = os.environ.get("W1F_OUT")
    if out:
        with open(out, "w", encoding="utf-8") as fh:
            json.dump(_state, fh, ensure_ascii=False, sort_keys=True)
    tr = session.config.pluginmanager.get_plugin("terminalreporter")
    for name, f in _state["violations"]:
        line = "ISOLATION_VIOLATION %s %s" % (name, f)
        (tr.write_line(line) if tr else print(line))
    for n in _state["not_collected"]:
        line = "NOT_COLLECTED %s" % n
        (tr.write_line(line) if tr else print(line))
    if _state["violations"] and session.exitstatus == 0:
        session.exitstatus = 3
'''

PLUG_DIR = None


def plugin_dir() -> Path:
    """プラグインを置くツリー外ディレクトリ（内容が同じなら再利用）。"""
    d = CACHE_ROOT / "plugin"
    d.mkdir(parents=True, exist_ok=True)
    f = d / "w1fsel.py"
    if not f.exists() or f.read_text(encoding="utf-8") != PLUGIN_SRC:
        f.write_text(PLUGIN_SRC, encoding="utf-8")
    return d


def read_bl() -> list[str]:
    """$BL の 124 件。FAILED を外しただけの文字列（エスケープのまま。デコードしない）。"""
    lines = BL_FILE.read_text(encoding="utf-8").split("\n")
    return [l[len("FAILED "):] for l in lines if l.startswith("FAILED ")]


def base_env(tree: Path, extra: dict | None = None, plug: bool = True) -> dict:
    env = {
        "HOME": HOME,
        "PATH": "/usr/bin:/bin",
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONHASHSEED": "0",  # set/dict の表示順を固定（決定的な出力のため）
        "PYTHONPATH": f"{tree}:{plugin_dir()}" if plug else str(tree),
        "W1F_TREE": str(tree),
        "TMPDIR": str(CACHE_ROOT / "tmp"),
    }
    (CACHE_ROOT / "tmp").mkdir(parents=True, exist_ok=True)
    if extra:
        env.update(extra)
    return env


def extract(sha: str, dest: Path | None = None) -> Path:
    """git archive で複写を展開する（$W には触れない）。"""
    d = dest or Path(tempfile.mkdtemp(prefix=f"w1f_{sha[:7]}_", dir=str(CACHE_ROOT / "tmp")))
    d.mkdir(parents=True, exist_ok=True)
    (CACHE_ROOT / "tmp").mkdir(parents=True, exist_ok=True)
    p = subprocess.run(f"git -C {ROOT} archive {sha} | tar -x -C {d}", shell=True, capture_output=True, text=True)
    if p.returncode != 0:
        raise RuntimeError(f"archive failed {sha}: {p.stderr}")
    return d


def run_selected(tree: Path, nodeids: list[str], files: list[str] | None = None, extra_env: dict | None = None,
                 pytest_args: list[str] | None = None, timeout: int = 3000) -> dict:
    """nodeid の完全一致で選んで 1 プロセスで実行する。
    戻り値: {"outcomes": {nodeid: PASS|FAIL|...}, "not_collected": [...], "collect_errors": [...],
             "violations": [...], "stdout": str, "returncode": int}"""
    (CACHE_ROOT / "tmp").mkdir(parents=True, exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix="w1f_run_", dir=str(CACHE_ROOT / "tmp")))
    try:
        sel = work / "sel.txt"
        sel.write_text("\n".join(nodeids) + "\n", encoding="utf-8")
        outj = work / "out.json"
        if files is None:
            files = sorted({n.split("::", 1)[0] for n in nodeids})
        env = base_env(tree, {"W1F_SEL": str(sel), "W1F_OUT": str(outj), **(extra_env or {})})
        args = [PY, "-m", "pytest", "-p", "no:cacheprovider", "-p", "w1fsel", "-rA", "--tb=short"] + (pytest_args or ["-q"]) + files
        try:
            p = subprocess.run(args, cwd=str(tree), env=env, capture_output=True, text=True, timeout=timeout)
            stdout, rc = p.stdout + (("\n[stderr]\n" + p.stderr) if p.stderr.strip() else ""), p.returncode
        except subprocess.TimeoutExpired as e:
            stdout, rc = "TIMEOUT", -9
        res = {"outcomes": {}, "collect_errors": [], "not_collected": [], "violations": []}
        if outj.exists():
            res.update(json.loads(outj.read_text(encoding="utf-8")))
        res["stdout"] = stdout
        res["returncode"] = rc
        return res
    finally:
        shutil.rmtree(work, ignore_errors=True)


def status_of(res: dict, nodeid: str) -> str:
    """PASS / FAIL / XFAIL / NOT_COLLECTED / COLLECT_ERROR / ISOLATION_VIOLATION / ERROR / SKIP / UNRUN。
    走らなかったものを FAIL にしない。"""
    if res.get("violations"):
        return "ISOLATION_VIOLATION"
    o = res["outcomes"].get(nodeid)
    if o is not None:
        return o
    f = nodeid.split("::", 1)[0]
    if any(e == f or e.startswith(f + "::") for e in res.get("collect_errors", [])):
        return "COLLECT_ERROR"
    if nodeid in res.get("not_collected", []):
        return "NOT_COLLECTED"
    return "UNRUN"


def git(*args: str, check: bool = True) -> str:
    p = subprocess.run(["git", "-C", str(ROOT), *args], capture_output=True, text=True)
    if check and p.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)}: {p.stderr}")
    return p.stdout


def jdump(path: Path, rows: list) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n")


def jload(path: Path) -> list:
    return [json.loads(l) for l in path.read_text(encoding="utf-8").split("\n") if l.strip()]


def timing(label: str, secs: float) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    with open(OUT / "timings.txt", "a", encoding="utf-8") as fh:
        fh.write(f"{label}\t{secs:.1f}s\n")


# --------------------------------------------------------------------------
# baseline（F5 の作業前/後）
# --------------------------------------------------------------------------
def cmd_baseline(a) -> int:
    phase = a.phase
    t0 = time.time()
    OUT.mkdir(parents=True, exist_ok=True)
    env = base_env(ROOT, plug=False)
    junit = OUT / f"suite_{phase}_junit.xml"
    p = subprocess.run([PY, "-m", "pytest", "-q", "-p", "no:cacheprovider", "-rf", "--tb=no",
                        "--continue-on-collection-errors", f"--junitxml={junit}", "tests"],
                       cwd=str(ROOT), env=env, capture_output=True, text=True)
    (OUT / f"suite_{phase}.txt").write_text(p.stdout + p.stderr, encoding="utf-8")
    bl = read_bl()
    lines = [l for l in p.stdout.split("\n") if l.startswith("FAILED ")]
    got = {b for b in bl if any(l == "FAILED " + b or l.startswith("FAILED " + b + " - ") for l in lines)}
    extra = [l for l in lines if not any(l == "FAILED " + b or l.startswith("FAILED " + b + " - ") for b in bl)]
    last = [l for l in p.stdout.split("\n") if l.strip()][-1]
    cmp_lines = []
    if len(lines) == len(bl) == len(got) and not extra:
        cmp_lines.append("SAME")
    else:
        cmp_lines.append("DIFF")
        cmp_lines += ["baseline_not_failed: " + b for b in sorted(set(bl) - got)]
        cmp_lines += ["new_failed: " + l for l in sorted(extra)]
    cmp_lines.append(f"failed_lines={len(lines)} matched_baseline={len(got)} baseline_size={len(bl)}")
    (OUT / f"suite_{phase}_compare.txt").write_text("\n".join(cmp_lines) + "\n", encoding="utf-8")
    if phase == "before":
        c = subprocess.run([PY, "-m", "pytest", "--collect-only", "-q", "-p", "no:cacheprovider",
                            "--continue-on-collection-errors", "tests"], cwd=str(ROOT), env=env, capture_output=True, text=True)
        tail = [l for l in c.stdout.split("\n") if l.strip()]
        tail = [re.sub(r" in [0-9.]+s$", "", l) for l in tail]
        (OUT / "collect.txt").write_text(tail[-1] + "\n", encoding="utf-8")
    timing(f"baseline-{phase}", time.time() - t0)
    print(last)
    print(cmp_lines[0], cmp_lines[-1])
    return 0 if cmp_lines[0] == "SAME" else 1


def cmd_index(a) -> int:
    """CLAUDE.md の指示（実装の前に索引を引く）の結果を記録する。"""
    out = []
    for q in ["失敗 テスト 分類", "bisect 回帰 コミット", "役割 語彙 origin source"]:
        p = subprocess.run([PY, "-B", "-m", "verantyx.cli", "index", "search", f'"{q}"'], cwd=str(ROOT), env=base_env(ROOT, plug=False), capture_output=True, text=True)
        try:
            d = json.loads(p.stdout)
            out.append(f"{q}\tverdict={d.get('verdict')}\tsearched={d.get('searched')}")
        except Exception:
            out.append(f"{q}\t(unparsed) {p.stdout[:80]!r}")
    (OUT / "index_search.txt").write_text("\n".join(out) + "\n", encoding="utf-8")
    print("\n".join(out))
    return 0


def cmd_collect(a) -> int:
    """全 nodeid の収集（F1 の相手テスト実在確認）と収集件数、W1-b merge で増えたテストの記録。"""
    OUT.mkdir(parents=True, exist_ok=True)
    env = base_env(ROOT, plug=False)
    c = subprocess.run([PY, "-m", "pytest", "--collect-only", "-q", "-p", "no:cacheprovider",
                        "--continue-on-collection-errors", "tests"], cwd=str(ROOT), env=env, capture_output=True, text=True)
    lines = [l for l in c.stdout.split("\n") if l.strip()]
    tail = re.sub(r" in [0-9.]+s$", "", lines[-1])
    ids = sorted(l for l in lines if "::" in l and not l.startswith(("ERROR", "FAILED")))
    (OUT / "collect_nodeids.txt").write_text("\n".join(ids) + "\n", encoding="utf-8")
    (OUT / "collect.txt").write_text(tail + "\n", encoding="utf-8")
    c2 = subprocess.run([PY, "-m", "pytest", "--collect-only", "-q", "-p", "no:cacheprovider", "tests/test_build_public.py"],
                        cwd=str(ROOT), env=env, capture_output=True, text=True)
    l2 = re.sub(r" in [0-9.]+s$", "", [l for l in c2.stdout.split("\n") if l.strip()][-1])
    delta = git("diff", "--name-only", "6c0d71e", DEV, "--", "tests").split()
    (OUT / "collect_delta.txt").write_text(
        "tests/test_build_public.py: " + l2 + "\n" + "changed test files 6c0d71e..075d486:\n" + "\n".join(sorted(delta)) + "\n", encoding="utf-8")
    print(tail, "nodeids", len(ids))
    return 0


# --------------------------------------------------------------------------
# isolate（1 件ずつ別プロセスで実行。F1 の根拠）
# --------------------------------------------------------------------------
def _first_error_line(text: str) -> str:
    cand = [l for l in text.split("\n") if re.match(r"^E\s", l)]
    return cand[0].strip()[:300] if cand else ""


def cmd_isolate(a) -> int:
    bl = read_bl()
    (OUT / "runs").mkdir(parents=True, exist_ok=True)
    full = {}
    sp = OUT / "suite_before.txt"
    # 全体実行（手順 2）と比べるため、全体実行で落ちたかは BL 集合そのもの（suite_before_compare が SAME のとき全部 failed）
    def one(i_nid):
        i, nid = i_nid
        t0 = time.time()
        res = run_selected(ROOT, [nid], pytest_args=["-vv", "--tb=long"])
        # 出力の安定化（実行所要秒の行を落とす）
        out = norm_out(res["stdout"])
        st = status_of(res, nid)
        n = i + 1
        (OUT / "runs" / f"{n:03d}.txt").write_text(out, encoding="utf-8")
        return {"n": n, "nodeid": nid, "outcome": {"FAIL": "failed", "PASS": "passed", "ERROR": "error",
                "NOT_COLLECTED": "not_collected"}.get(st, st.lower()),
                "first_error_line": _first_error_line(out), "violations": res.get("violations", [])}, time.time() - t0
    rows = []
    t0 = time.time()
    with cf.ThreadPoolExecutor(max_workers=a.jobs) as ex:
        for r, dt in ex.map(one, list(enumerate(bl))):
            rows.append(r)
    rows.sort(key=lambda r: r["n"])
    jdump(OUT / "runs_index.jsonl", rows)
    from collections import Counter
    print(dict(Counter(r["outcome"] for r in rows)), "violations:", sum(1 for r in rows if r["violations"]))
    timing("isolate", time.time() - t0)
    return 0



# --------------------------------------------------------------------------
# history（どのコミットで落ち始めたか）
# --------------------------------------------------------------------------
def norm_out(out: str) -> str:
    """出力から所要秒・一時パス・オブジェクトのアドレスを落として決定的にする。"""
    out = re.sub(r"(\d+ \w+(?:, \d+ \w+)*) in [0-9.]+s( \([0-9:]+\))?", r"\1", out)
    out = re.sub(r" in [0-9.]+s( \([0-9:]+\))?(?=\s*$)", "", out, flags=re.M)  # 行末の所要秒（subtests 付きの要約行も）
    out = re.sub(r"\n=+ (.*?) =+", lambda m: "\n=== " + re.sub(r" in [0-9.]+s.*", "", m.group(1)) + " ===", out)
    out = out.replace(str(ROOT), "<TREE>")   # ツリーが /private/tmp の下にあっても <TMP> に化けないよう、一時パスの置換より先に行う
    for cp in sorted({str(CACHE_ROOT), os.path.realpath(str(CACHE_ROOT)), "/private" + str(CACHE_ROOT)}, key=len, reverse=True):
        out = out.replace(cp, "<CACHE>")
    out = re.sub(r"/private/var/folders[^\s'\":]*|/var/folders[^\s'\":]*|/private/tmp/[^\s'\":]*|/tmp/[^\s'\":]*", "<TMP>", out)
    out = re.sub(r"\.memory-frame-[A-Za-z0-9_]+", ".memory-frame-<RND>", out)
    out = re.sub(r"0x[0-9a-f]{6,}", "0x<ADDR>", out)
    out = re.sub(r"(\w*_ms)=[0-9.]+(e-?\d+)?", r"\1=<MS>", out)  # 所要ミリ秒（実行ごとに変わる）
    out = re.sub(r"gap_[0-9a-f]{8}", "gap_<HASH>", out)  # 実行ごとに変わる gap の内容ハッシュ（判断記録に書く）
    out = re.sub(r"pytest-of-[A-Za-z0-9_]+/pytest-\d+", "pytest-of-<USER>/pytest-<N>", out)
    out = re.sub(r"rootdir: \S+", "rootdir: <TREE>", out)
    return out


GOOD = ("PASS", "XFAIL")  # スイートが緑のままの状態（XFAIL は期待された失敗）
_CHAIN = None


def chain() -> list[str]:
    """DEV までの first-parent 履歴（古い順）。"""
    global _CHAIN
    if _CHAIN is None:
        _CHAIN = git("rev-list", "--first-parent", "--reverse", DEV).split()
    return _CHAIN


_EFF = {}


def effective_chain_commit(c: str) -> str:
    """c が first-parent 履歴上に無い（側枝の）コミットなら、それを取り込む最初の first-parent コミットに写す。"""
    ch = chain()
    if c in ch:
        return c
    if c in _EFF:
        return _EFF[c]
    for x in ch:
        if subprocess.run(["git", "-C", str(ROOT), "merge-base", "--is-ancestor", c, x]).returncode == 0:
            _EFF[c] = x
            return x
    raise RuntimeError("not ancestor: " + c)


def func_name(nodeid: str) -> str:
    m = re.match(r"^[^:]+::([^\[]+)", nodeid)
    return m.group(1) if m else ""


def added_in(nodeid: str) -> dict:
    f = nodeid.split("::", 1)[0]
    fn = func_name(nodeid)
    file_add = git("log", "--diff-filter=A", "--format=%H", "--", f).split()
    file_add = file_add[-1] if file_add else None
    fn_add = git("log", "-S", f"def {fn}", "--format=%H", "--", f).split()
    fn_add = fn_add[-1] if fn_add else None
    cands = [effective_chain_commit(c) for c in (file_add, fn_add) if c]
    ch = chain()
    later = max(cands, key=lambda c: ch.index(c))
    return {"file_added": file_add, "func_added": fn_add, "added_in": later}


class HistCache:
    def __init__(self):
        self.path = CACHE_ROOT / "hist_cache.json"
        self.d = json.loads(self.path.read_text(encoding="utf-8")) if self.path.exists() else {}

    def save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.d, ensure_ascii=False, sort_keys=True), encoding="utf-8")


def eval_commit(sha: str, nodeids: list[str]) -> dict:
    """sha の複写で nodeids をまとめて 1 プロセスで走らせ、{nodeid: status} を返す。"""
    tree = extract(sha)
    try:
        files = sorted({n.split("::", 1)[0] for n in nodeids})
        files = [f for f in files if (tree / f).exists()]
        res = run_selected(tree, nodeids, files=files, pytest_args=["-q", "--continue-on-collection-errors"]) if files else \
            {"outcomes": {}, "collect_errors": [], "not_collected": list(nodeids), "violations": []}
        return {n: status_of(res, n) for n in nodeids}
    finally:
        shutil.rmtree(tree, ignore_errors=True)


def ensure_commits(cache: HistCache, commits: list[str], nodeids: list[str], jobs: int) -> None:
    need = sorted({c for c in commits if c not in cache.d or any(n not in cache.d[c] for n in nodeids)})
    if not need:
        return
    with cf.ThreadPoolExecutor(max_workers=jobs) as ex:
        for c, r in zip(need, ex.map(lambda c: eval_commit(c, nodeids), need)):
            cache.d.setdefault(c, {}).update(r)
    cache.save()


def run_one_verbose(tree: Path, nodeid: str, extra_env: dict | None = None) -> tuple[str, str]:
    res = run_selected(tree, [nodeid], pytest_args=["-vv", "--tb=long", "--continue-on-collection-errors"], extra_env=extra_env)
    return status_of(res, nodeid), norm_out(res["stdout"])


def cmd_history(a) -> int:
    t0 = time.time()
    bl = read_bl()
    cache = HistCache()
    jobs = a.jobs
    ch = chain()
    meta = {}
    for i, nid in enumerate(bl):
        m = added_in(nid)
        meta[nid] = m
    # 1. status_at_added
    adds = sorted({m["added_in"] for m in meta.values()}, key=ch.index)
    ensure_commits(cache, adds, bl, jobs)
    state = {}
    for nid in bl:
        L = ch[ch.index(meta[nid]["added_in"]):]
        st = cache.d[L[0]][nid]
        state[nid] = {"L": L, "status_at_added": st, "lo": 0, "hi": len(L) - 1, "skipped": [], "visited": [[L[0], st]]}
        if st not in GOOD:
            state[nid]["done"] = True
    # 2. 二分探索（ラウンド方式。各テストの経路は他のテストに依存しない）
    rnd = 0
    while True:
        want = {}
        for nid, s in state.items():
            if s.get("done"):
                continue
            lo, hi, sk = s["lo"], s["hi"], set(s["skipped"])
            if hi - lo <= 1:
                s["done"] = True
                continue
            cands = [i for i in range(lo + 1, hi) if i not in sk]
            if not cands:
                s["done"] = True
                s["gap_skipped"] = True
                continue
            mid = (lo + hi) // 2
            i = min(cands, key=lambda i: (abs(i - mid), i))
            s["next"] = i
            want.setdefault(s["L"][i], []).append(nid)
        if not want:
            break
        rnd += 1
        ensure_commits(cache, list(want), bl, jobs)
        for c, nids in want.items():
            for nid in nids:
                s = state[nid]
                i = s.pop("next")
                st = cache.d[c][nid]
                s["visited"].append([c, st])
                if st in GOOD:
                    s["lo"] = i
                elif st == "FAIL":
                    s["hi"] = i
                else:
                    s["skipped"].append(i)
        print("round", rnd, "commits", len(want), flush=True)
    # 3. 境界の両端を実測し直す（出力を保存）
    (OUT / "history").mkdir(parents=True, exist_ok=True)
    nmap = {nid: i + 1 for i, nid in enumerate(bl)}
    verify_jobs = []
    for nid, s in state.items():
        if s["status_at_added"] in GOOD:
            verify_jobs.append((nid, s["L"][s["lo"]], "good"))
            verify_jobs.append((nid, s["L"][s["hi"]], "bad"))
    by_commit = {}
    for nid, c, kind in verify_jobs:
        by_commit.setdefault(c, []).append((nid, kind))
    verified = {}

    def verify_commit(c):
        tree = extract(c)
        try:
            out = {}
            for nid, kind in by_commit[c]:
                st, txt = run_one_verbose(tree, nid)
                n = nmap[nid]
                (OUT / "history" / f"{n:03d}_{kind}.txt").write_text(f"# commit {c}\n# status {st}\n" + txt, encoding="utf-8")
                out[(nid, kind)] = st
            return out
        finally:
            shutil.rmtree(tree, ignore_errors=True)
    with cf.ThreadPoolExecutor(max_workers=jobs) as ex:
        for r in ex.map(verify_commit, sorted(by_commit)):
            verified.update(r)
    # 4. 6c0d71e の細分
    B6 = git("rev-parse", "6c0d71e").strip()
    split_targets = [nid for nid, s in state.items() if s["status_at_added"] in GOOD and s["L"][s["hi"]] == B6]
    splits = split_6c0d71e(split_targets, state, jobs) if split_targets else {}
    rows = []
    for nid in bl:
        s, m = state[nid], meta[nid]
        n = nmap[nid]
        row = {"n": n, "nodeid": nid, "added_in": m["added_in"], "file_added": m["file_added"], "func_added": m["func_added"],
               "status_at_added": s["status_at_added"], "born_red": s["status_at_added"] == "FAIL"}
        if s["status_at_added"] in GOOD:
            lo, hi = s["L"][s["lo"]], s["L"][s["hi"]]
            f = nid.split("::", 1)[0]
            row.update({"last_good": lo, "first_bad": hi, "status_at_last_good": cache.d[lo][nid], "skipped_points": sorted({s["L"][i] for i in s["skipped"]}),
                        "gap_skipped": bool(s.get("gap_skipped")),
                        "visited": s["visited"],
                        "verified": verified.get((nid, "good")) in GOOD and verified.get((nid, "bad")) == "FAIL",
                        "good_output": f"artifacts/w1-f/history/{n:03d}_good.txt", "bad_output": f"artifacts/w1-f/history/{n:03d}_bad.txt",
                        "first_bad_subject": git("log", "-1", "--format=%s", hi).strip(),
                        "changed_files": sorted(x for x in git("diff", "--name-only", lo, hi).split("\n") if x),
                        "test_file_changed_between": subprocess.run(["git", "-C", str(ROOT), "diff", "--quiet", lo, hi, "--", f]).returncode != 0})
            if nid in splits:
                row["first_bad_file"] = splits[nid]
        else:
            row["visited"] = s["visited"]
        rows.append(row)
    # 4b. 収集エラーで区間が飛ばされたテスト: テスト先頭に `import pytest` を 1 行足した複写で全コミットを測る（足したことを明記）
    patched = []
    for r in rows:
        if r.get("gap_skipped"):
            patched.append(patched_scan(r, state[r["nodeid"]]["L"], jobs))
    if patched:
        jdump(OUT / "history_patched.jsonl", patched)
    jdump(OUT / "history.jsonl", rows)
    from collections import Counter
    print(dict(Counter(r["status_at_added"] for r in rows)))
    print("boundaries:", dict(Counter(r.get("first_bad", "-")[:7] for r in rows)))
    print("unverified:", [r["n"] for r in rows if r["status_at_added"] in GOOD and not r["verified"]])
    timing("history", time.time() - t0)
    return 0


def patched_scan(row: dict, L: list[str], jobs: int) -> dict:
    """テストファイルに `import pytest` が無いために収集エラーになる区間を、その 1 行を足した複写で測る。
    製品コードは触らない。足した行は出力に明記する。"""
    nid = row["nodeid"]
    f = nid.split("::", 1)[0]

    def one(c):
        tree = extract(c)
        try:
            p = tree / f
            if not p.exists():
                return c, "NOT_COLLECTED", False
            txt = p.read_text(encoding="utf-8")
            added = not re.search(r"^import pytest\b", txt, re.M)
            if added:
                p.write_text("import pytest  # W1-f: 1 line added by the probe\n" + txt, encoding="utf-8")
            res = run_selected(tree, [nid], pytest_args=["-q", "--continue-on-collection-errors"])
            return c, status_of(res, nid), added
        finally:
            shutil.rmtree(tree, ignore_errors=True)
    with cf.ThreadPoolExecutor(max_workers=jobs) as ex:
        res = list(ex.map(one, L))
    seq = [(c, st) for c, st, _ in res]
    first_fail = next((i for i, (c, st) in enumerate(seq) if st == "FAIL"), None)
    all_after_fail = first_fail is not None and all(st == "FAIL" for c, st in seq[first_fail:])
    j = len(seq)
    while j > 0 and seq[j - 1][1] == "FAIL":
        j -= 1
    return {"n": row["n"], "nodeid": nid, "probe": "import_pytest_line_added_to_test_file",
            "statuses": [[c, st, added] for (c, st, added) in res],
            "first_fail_with_patch": seq[first_fail][0] if first_fail is not None else None,
            "monotone_from_first_fail": all_after_fail,
            "final_fail_run_start": seq[j][0] if j < len(seq) else None,
            "last_non_fail_before_final_run": seq[j - 1][0] if j > 0 else None,
            "status_of_last_non_fail": seq[j - 1][1] if j > 0 else None,
            "counts": {k: sum(1 for _, st in seq if st == k) for k in sorted({st for _, st in seq})}}


def split_6c0d71e(targets: list[str], state: dict, jobs: int) -> dict:
    """first_bad が 6c0d71e のテストを、verantyx/ のファイル単位で親に重ねて測る。
    戻り値 {nodeid: {"verantyx_files_that_fail": [...], "tests_only": status, "all_verantyx": status, "per_file": {...}}}"""
    B = "6c0d71e"
    parent = git("rev-parse", B + "^1").strip()
    files = sorted(x for x in git("diff", "--name-only", parent, B, "--", "verantyx").split("\n") if x)
    testfiles = sorted({n.split("::", 1)[0] for n in targets})
    results = {nid: {"per_file": {}} for nid in targets}

    def overlay(tree: Path, paths: list[str]):
        for p in paths:
            r = subprocess.run(["git", "-C", str(ROOT), "cat-file", "-e", f"{B}:{p}"], capture_output=True)
            dst = tree / p
            if r.returncode != 0:  # B で削除されたファイル
                if dst.exists():
                    dst.unlink()
                continue
            dst.parent.mkdir(parents=True, exist_ok=True)
            data = subprocess.run(["git", "-C", str(ROOT), "show", f"{B}:{p}"], capture_output=True).stdout
            dst.write_bytes(data)

    def variant(label: str, paths: list[str]):
        tree = extract(parent)
        try:
            overlay(tree, paths)
            res = run_selected(tree, targets, files=[f for f in testfiles if (tree / f).exists()],
                               pytest_args=["-q", "--continue-on-collection-errors"])
            return label, {nid: status_of(res, nid) for nid in targets}
        finally:
            shutil.rmtree(tree, ignore_errors=True)
    variants = [("tests_only", testfiles), ("all_verantyx", files)] + [(f, [f]) for f in files]
    with cf.ThreadPoolExecutor(max_workers=jobs) as ex:
        for label, r in ex.map(lambda v: variant(*v), variants):
            for nid, st in r.items():
                if label in ("tests_only", "all_verantyx"):
                    results[nid][label] = st
                else:
                    results[nid]["per_file"][label] = st
    out = {}
    for nid in targets:
        r = results[nid]
        out[nid] = {"tests_only": r["tests_only"], "all_verantyx": r["all_verantyx"],
                    "verantyx_files_that_fail": sorted(f for f, st in r["per_file"].items() if st == "FAIL"),
                    "verantyx_files_not_decisive": sorted(f for f, st in r["per_file"].items() if st not in ("FAIL", "PASS"))}
    return out



# --------------------------------------------------------------------------
# probe（原因の仮説を一時複写で確かめる。ツリーには書かない）
# --------------------------------------------------------------------------
def suite_failures(tree: Path, extra_env: dict | None = None, files: list[str] | None = None) -> tuple[set, str]:
    """tree で全体（または files）を走らせ、失敗した nodeid の集合を返す。
    nodeid は junit ではなく、プラグインの outcome 記録から取る（-rf の行は長さで切れうるため）。"""
    res = run_selected_all(tree, files or ["tests"], extra_env)
    failed = {n for n, o in res["outcomes"].items() if o in ("FAIL", "ERROR")}
    failed |= {e for e in res.get("collect_errors", [])}
    return failed, res["stdout"]


def run_selected_all(tree: Path, files: list[str], extra_env: dict | None = None) -> dict:
    """選択無しで files を全部走らせる（プラグインは結果記録と隔離検査にだけ使う）。"""
    work = Path(tempfile.mkdtemp(prefix="w1f_all_", dir=str(CACHE_ROOT / "tmp")))
    try:
        outj = work / "out.json"
        env = base_env(tree, {"W1F_OUT": str(outj), **(extra_env or {})})
        args = [PY, "-m", "pytest", "-p", "no:cacheprovider", "-p", "w1fsel", "-q", "--tb=no", "--continue-on-collection-errors"] + files
        p = subprocess.run(args, cwd=str(tree), env=env, capture_output=True, text=True, timeout=3000)
        res = {"outcomes": {}, "collect_errors": [], "not_collected": [], "violations": []}
        if outj.exists():
            res.update(json.loads(outj.read_text(encoding="utf-8")))
        res["stdout"] = p.stdout
        res["returncode"] = p.returncode
        return res
    finally:
        shutil.rmtree(work, ignore_errors=True)


def sh(args: list[str], cwd: Path | None = None, inp: str | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(args, cwd=str(cwd) if cwd else None, capture_output=True, text=True, input=inp)


def make_tree(steps: list) -> tuple[Path | None, list[dict]]:
    """DEV の複写（git clone --shared。$W の .git には書かない）を作り、steps を順に適用する。
    step: ["revert", sha] | ["diff", "artifacts/w1-f/…diff"] | ["overlay", sha, [paths]]
    戻り値 (tree, log)。適用できなかった時点で tree=None（CONFLICT／APPLY_FAILED を FAIL と混ぜない）。"""
    (CACHE_ROOT / "tmp").mkdir(parents=True, exist_ok=True)
    tree = Path(tempfile.mkdtemp(prefix="w1f_tree_", dir=str(CACHE_ROOT / "tmp")))
    sh(["git", "clone", "-q", "--shared", "--no-checkout", str(ROOT), str(tree)])
    sh(["git", "-C", str(tree), "checkout", "-q", DEV])
    log = []
    for st in steps:
        kind = st[0]
        if kind == "revert":
            c = st[1]
            patch = git("diff", "--binary", c + "^1", c, "--", "verantyx")
            if sh(["git", "apply", "-R", "--check", "-"], tree, patch).returncode == 0:
                sh(["git", "apply", "-R", "-"], tree, patch)
                log.append({"step": st, "apply": "OK"})
            else:
                r = sh(["git", "apply", "-R", "-3", "-"], tree, patch)
                if r.returncode == 0:
                    log.append({"step": st, "apply": "OK_3WAY"})
                else:
                    # 3-way でも衝突: 当たる hunk だけを逆適用し（--reject）、当たらなかった hunk は記録する（PARTIAL_REJECT）。
                    # FAIL や PASS と混ぜない: ログの apply が PARTIAL_REJECT の複写で測った結果は「部分逆適用」の証拠として扱う。
                    conflicts = sorted(x for x in sh(["git", "diff", "--name-only", "--diff-filter=U"], tree).stdout.split("\n") if x)
                    sh(["git", "checkout", "-q", "--", "."], tree)
                    sh(["git", "reset", "-q", "--hard", DEV], tree)
                    r2 = sh(["git", "apply", "-R", "--reject", "-"], tree, patch)
                    rej = sorted(str(x.relative_to(tree)) for x in tree.rglob("*.rej"))
                    rej_text = "".join((tree / x).read_text(encoding="utf-8", errors="replace") for x in rej)
                    rej_hunks = rej_text.count("\n@@ ")
                    all_hunks = patch.count("\n@@ ")
                    for x in rej:
                        (tree / x).unlink()
                    log.append({"step": st, "apply": "PARTIAL_REJECT", "three_way_conflict_files": conflicts, "rejected_files": rej,
                                "rejected_hunks": rej_hunks, "total_hunks": all_hunks})
        elif kind == "diff":
            dp = ROOT / st[1]
            r = sh(["git", "apply", "-"], tree, dp.read_text(encoding="utf-8"))
            if r.returncode != 0:
                log.append({"step": st, "apply": "APPLY_FAILED", "stderr": norm_out(r.stderr)[:600]})
                shutil.rmtree(tree, ignore_errors=True)
                return None, log
            log.append({"step": st, "apply": "OK"})
        elif kind == "edit":      # ["edit", path, [[old, new], ...]]（複写の中の文字列置換。old が無ければ失敗として止める）
            fp = tree / st[1]
            txt = fp.read_text(encoding="utf-8")
            for old, new in st[2]:
                if old not in txt:
                    log.append({"step": st, "apply": "APPLY_FAILED", "stderr": "old string not found: " + old[:60]})
                    shutil.rmtree(tree, ignore_errors=True)
                    return None, log
                txt = txt.replace(old, new, 1)
            fp.write_text(txt, encoding="utf-8")
            log.append({"step": st[:2], "apply": "OK"})
        elif kind == "overlay":
            c, paths = st[1], st[2]
            for p in paths:
                data = subprocess.run(["git", "-C", str(ROOT), "show", f"{c}:{p}"], capture_output=True).stdout
                (tree / p).parent.mkdir(parents=True, exist_ok=True)
                (tree / p).write_bytes(data)
            log.append({"step": st, "apply": "OK"})
        else:
            raise ValueError(kind)
    return tree, log


def numstat_paths(diff_text: str) -> list[str]:
    """git apply --numstat で、差分が触れるファイルのパスを取る。"""
    with tempfile.TemporaryDirectory(dir=str(CACHE_ROOT / "tmp")) as d:
        r = sh(["git", "apply", "--numstat", "-"], Path(d), diff_text)
    return sorted(l.split("\t")[-1] for l in r.stdout.split("\n") if l.strip())


def collect_ids_by_file() -> dict:
    d: dict = {}
    for l in (OUT / "collect_nodeids.txt").read_text(encoding="utf-8").split("\n"):
        if l:
            d.setdefault(l.split("::", 1)[0], []).append(l)
    return d


def variant_run(steps: list, base_failed: set | None = None, confirm: bool = True, capture_diff: bool = False) -> dict:
    """steps を適用した複写で全体を走らせ、失敗集合を返す。base_failed があれば newly_passing／newly_failing（単独で確認）も。"""
    key = hashlib.sha256(json.dumps(steps, sort_keys=True).encode()).hexdigest()[:16]
    cache = CACHE_ROOT / "variants" / f"{key}.json"
    tree, log = make_tree(steps)
    if tree is None:
        return {"steps": steps, "log": log, "apply": log[-1]["apply"]}
    try:
        if cache.exists():
            failed = set(json.loads(cache.read_text(encoding="utf-8"))["failed"]); tail = norm_out(json.loads(cache.read_text(encoding="utf-8"))["tail"])
        else:
            failed, out = suite_failures(tree)
            tail = norm_out([l for l in out.split("\n") if l.strip()][-1])
            cache.parent.mkdir(parents=True, exist_ok=True)
            cache.write_text(json.dumps({"failed": sorted(failed), "tail": tail}, ensure_ascii=False), encoding="utf-8")
        res = {"steps": steps, "log": log, "apply": log[-1]["apply"] if log else "OK", "summary_line": tail, "failed": sorted(failed)}
        if capture_diff:
            sh(["git", "add", "-A", "-N", "."], tree)
            res["diff_text"] = sh(["git", "diff", "--binary", DEV], tree).stdout
        if base_failed is not None:
            res["newly_passing"] = sorted(base_failed - failed)
            nf = sorted(failed - base_failed)
            res["newly_failing"] = nf
            res["still_failing_count"] = len(base_failed & failed)
            if confirm:
                by_file = collect_ids_by_file()
                targets = []
                for n in nf:
                    targets += by_file.get(n, [n]) if "::" not in n else [n]   # 収集エラーのファイルは DEV の nodeid に展開
                targets = sorted(set(targets))
                conf = []
                if targets:
                    for i in range(0, len(targets), 1):
                        r = run_selected(tree, [targets[i]], pytest_args=["-q", "--continue-on-collection-errors"])
                        st = status_of(r, targets[i])
                        if st in ("FAIL", "ERROR", "COLLECT_ERROR"):
                            conf.append(targets[i])
                res["newly_failing_confirmed"] = conf
        return res
    finally:
        shutil.rmtree(tree, ignore_errors=True)


def write_probe(name: str, data: dict) -> None:
    (OUT / "probes").mkdir(parents=True, exist_ok=True)
    data = {k: v for k, v in data.items() if k != "failed"}
    (OUT / "probes" / f"{name}.json").write_text(json.dumps(data, ensure_ascii=False, sort_keys=True, indent=1) + "\n", encoding="utf-8")


def cmd_probe(a) -> int:
    mode = a.rest[0] if a.rest else "revert"
    if mode == "revert":
        return probe_revert(a)
    if mode == "adapt":
        return probe_adapt(a)
    if mode == "combo":
        return probe_combo(a)
    if mode == "env":
        return probe_env(a)
    if mode == "e2e":
        return probe_e2e(a)
    print("unknown probe mode", mode)
    return 2


def probe_revert(a) -> int:
    """各 first_bad コミット B の製品側（verantyx/）の変更を DEV の複写から逆適用（そのまま→3-way の順）し、全体を走らせる。
    当たらなかった（CONFLICT）ものは probes/revert_<c>_partial.diff（手で作った最小の部分逆適用）があればそれを当てる。"""
    t0 = time.time()
    hist = jload(OUT / "history.jsonl")
    bl = set(read_bl())
    dev_full = git("rev-parse", DEV).strip()
    commits = sorted({r["first_bad"] for r in hist if r.get("first_bad") and r["first_bad"] != dev_full}, key=chain().index)
    want = a.rest[1:] if len(a.rest) > 1 else None
    (OUT / "probes").mkdir(parents=True, exist_ok=True)

    def one(c):
        subj = git("log", "-1", "--format=%s", c).strip()
        files = sorted(x for x in git("diff", "--name-only", c + "^1", c, "--", "verantyx").split("\n") if x)
        out = {"commit": c, "subject": subj, "files": files}
        r = variant_run([["revert", c]], bl, capture_diff=True)
        out.update({k: v for k, v in r.items() if k not in ("steps", "log", "diff_text")})
        out["log"] = r["log"]
        out["partial_method"] = "git apply -R --reject（当たる hunk だけ）" if r["apply"] == "PARTIAL_REJECT" else None
        return c, out, r.get("diff_text", "")
    sel = [c for c in commits if not want or c[:7] in want]
    with cf.ThreadPoolExecutor(max_workers=a.jobs) as ex:
        results = list(ex.map(one, sel))
    for c, r, dtext in results:
        write_probe(f"revert_{c[:7]}", r)
        (OUT / "probes" / f"revert_{c[:7]}.diff").write_text(dtext, encoding="utf-8")
        print(c[:7], r["subject"], r["apply"], "np", len(r.get("newly_passing", [])), "nfc", len(r.get("newly_failing_confirmed", [])))
    timing("probe-revert", time.time() - t0)
    return 0


def probe_adapt(a) -> int:
    """テスト側だけを機械的に合わせた差分（probes/adapt_<名前>.diff）を DEV に当てて、通るようになる基線の失敗を測る。
    差分が tests/ 以外に触れるものは無効（INVALID）。"""
    t0 = time.time()
    bl = set(read_bl())
    for name in a.rest[1:]:
        dp = OUT / "probes" / f"adapt_{name}.diff"
        text = dp.read_text(encoding="utf-8")
        paths = numstat_paths(text)
        valid = bool(paths) and all(p.startswith("tests/") for p in paths)
        out = {"name": name, "diff": f"artifacts/w1-f/probes/adapt_{name}.diff", "touched": paths, "all_hunks_under_tests": valid}
        if valid:
            r = variant_run([["diff", out["diff"]]], bl)
            out.update({k: v for k, v in r.items() if k not in ("steps", "log", "failed", "newly_passing")})
            out["log"] = r["log"]
            if r["apply"] == "OK":
                out["passes"] = r["newly_passing"]
                out["still_fails"] = sorted(bl - set(r["newly_passing"]))
        else:
            out["apply"] = "INVALID"
        write_probe(f"adapt_{name}", out)
        print("adapt", name, out["apply"], "passes", len(out.get("passes", [])), "newly_failing_confirmed", len(out.get("newly_failing_confirmed", [])))
    timing("probe-adapt", time.time() - t0)
    return 0


def probe_combo(a) -> int:
    """probes/combo_<名前>.spec.json: {"base": [steps...], "variant": [steps...]} の 2 つの複写の失敗集合を比べる（テスト同士の矛盾の証拠）。"""
    t0 = time.time()
    for name in a.rest[1:]:
        spec = json.loads((OUT / "probes" / f"combo_{name}.spec.json").read_text(encoding="utf-8"))
        base = variant_run(spec["base"], None)
        if base["apply"] not in ("OK", "OK_3WAY"):
            write_probe(f"combo_{name}", {"name": name, "apply": base["apply"], "which": "base", "log": base["log"]}); continue
        bfail = set(base["failed"])
        var = variant_run(spec["variant"], bfail)
        out = {"name": name, "spec": spec, "base_summary": base["summary_line"], "base_failed_in_baseline": sorted(bfail & set(read_bl()))}
        out.update({k: v for k, v in var.items() if k not in ("steps", "failed")})
        write_probe(f"combo_{name}", out)
        print("combo", name, var["apply"], "np", len(var.get("newly_passing", [])), "nfc", len(var.get("newly_failing_confirmed", [])))
    timing("probe-combo", time.time() - t0)
    return 0


def probe_env(a) -> int:
    """n=109 の環境依存: 一般コーパス（VERA_GENERAL）が無いと frames.attested が常に False になる。
    最小の sqlite（借りる/を/傘 を 3 つの別 src）を CACHE に作り、VERA_GENERAL を渡して 109 を走らせる。製品・テストは変えない。"""
    bl = read_bl()
    nid = next(n for n in bl if n.startswith("tests/test_p4_abilities.py::test_speech_act_drafts_fill_new_roles_and_reread"))
    import sqlite3
    dbp = CACHE_ROOT / "general_min.db"
    if dbp.exists():
        dbp.unlink()
    con = sqlite3.connect(str(dbp))
    con.execute("create table tedges(head text, rel text, dep text, src text)")
    for i in range(3):
        con.execute("insert into tedges values(?,?,?,?)", ("借りる", "を", "傘", f"s{i}"))
    con.commit(); con.close()
    default = Path(HOME) / "Projects" / "vera-corpus" / "build" / "general.db"
    out = []
    out.append(f"default general store {default}: exists={default.exists()}")
    r0 = run_selected(ROOT, [nid], pytest_args=["-vv", "--tb=short"])
    out.append(f"without VERA_GENERAL: {status_of(r0, nid)}")
    r1 = run_selected(ROOT, [nid], extra_env={"VERA_GENERAL": str(dbp)}, pytest_args=["-vv", "--tb=short"])
    out.append(f"with VERA_GENERAL=<3 rows (借りる,を,傘) in a tiny sqlite>: {status_of(r1, nid)}")
    (OUT / "probes").mkdir(parents=True, exist_ok=True)
    (OUT / "probes" / "env_general_109.txt").write_text("\n".join(out) + "\n", encoding="utf-8")
    print("\n".join(out))
    return 0


def probe_e2e(a) -> int:
    """肩書きに接尾辞が入るときの e2e（dev の複写）: 実タガーの切り方と、Vera.ask の答え。"""
    tree, _ = make_tree([])
    try:
        out = []
        code = ("import fugashi,sys\nt=fugashi.Tagger()\nfor s in ['研究員ユンは青い鍵を運んだ。','技師ユンは青い鍵を運んだ。']:\n"
                "    print('TOKENS', s, [(w.surface,w.feature.pos1,w.feature.pos2) for w in t(s)])\n")
        p = subprocess.run([PY, "-B", "-c", code], cwd=str(tree), env=base_env(tree, plug=False), capture_output=True, text=True)
        out += [l for l in p.stdout.split("\n") if l.strip()]
        for doc in ("研究員ユンは青い鍵を運んだ。", "技師ユンは青い鍵を運んだ。"):
            r = ask_many(tree, doc, ["誰が青い鍵を運んだ？"])[0]
            out.append(f"ASK {doc} 誰が青い鍵を運んだ？ -> {json.dumps(r, ensure_ascii=False)}")
    finally:
        shutil.rmtree(tree, ignore_errors=True)
    (OUT / "probes" / "e2e_names_suffix.txt").write_text("\n".join(out) + "\n", encoding="utf-8")
    print("\n".join(out))
    return 0


def cmd_fixcheck(a) -> int:
    """bundles.jsonl の f2.diff（075d486 基準の製品側だけの最小差分）を DEV の複写に当て、f2.test が直す前 FAIL・直した後 PASS になるか、
    全体での新規失敗（単独で再確認）・新規通過を fixes/<束>.json に書く。"""
    t0 = time.time()
    bl = set(read_bl())
    bundles = jload(OUT / "bundles_input.jsonl")
    for b in bundles:
        f2 = b.get("f2") or {}
        if not f2.get("diff"):
            continue
        if a.rest and b["bundle"] not in a.rest:
            continue
        diff_text = (ROOT / f2["diff"]).read_text(encoding="utf-8")
        paths = numstat_paths(diff_text)
        out = {"bundle": b["bundle"], "test": f2["test"], "diff": f2["diff"], "touched": paths,
               "only_product_files": bool(paths) and all(p.startswith("verantyx/") for p in paths)}
        before = run_selected(ROOT, [f2["test"]], pytest_args=["-q"])
        out["before"] = status_of(before, f2["test"])
        r = variant_run([["diff", f2["diff"]]], bl)
        out["apply"] = r["apply"]
        if r["apply"] == "OK":
            tree, _ = make_tree([["diff", f2["diff"]]])
            try:
                after = run_selected(tree, [f2["test"]], pytest_args=["-q"])
                out["after"] = status_of(after, f2["test"])
            finally:
                shutil.rmtree(tree, ignore_errors=True)
            out["newly_passing"] = r["newly_passing"]
            out["newly_failing"] = r["newly_failing"]
            out["newly_failing_confirmed"] = r.get("newly_failing_confirmed", [])
            out["summary_line"] = r["summary_line"]
            out["bundle_tests_passing_after"] = sorted(set(b["tests"]) & set(r["newly_passing"]))
        write_probe_to(OUT / "fixes" / f"{b['bundle']}.json", out)
        for sp in b.get("split", []):     # 差分を hunk ごとに分け、束のテストごとに「その hunk だけで通るか」を測る（束の切り方の根拠）
            part = {"bundle": b["bundle"], "part": sp["name"], "diff": sp["diff"], "touched": numstat_paths((ROOT / sp["diff"]).read_text(encoding="utf-8")), "tests": {}}
            ptree, plog = make_tree([["diff", sp["diff"]]])
            if ptree is None:
                part["apply"] = plog[-1]["apply"]
            else:
                try:
                    pres = run_selected(ptree, b["tests"], pytest_args=["-q"])
                    part["apply"] = "OK"
                    part["tests"] = {n: status_of(pres, n) for n in b["tests"]}
                finally:
                    shutil.rmtree(ptree, ignore_errors=True)
            write_probe_to(OUT / "fixes" / f"{b['bundle']}_{sp['name']}.json", part)
            print(b["bundle"], sp["name"], part["apply"], sorted(part["tests"].values()))
        lines = [f"bundle {b['bundle']} test {f2['test']}", f"before {out['before']}", f"after {out.get('after')}", f"apply {out['apply']}",
                 f"summary {out.get('summary_line')}", "newly_passing:"] + ["  " + x for x in out.get("newly_passing", [])] + \
                ["newly_failing_confirmed:"] + ["  " + x for x in out.get("newly_failing_confirmed", [])]
        (OUT / "fixes" / f"{b['bundle']}.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(b["bundle"], out["before"], "->", out.get("after"), "np", len(out.get("newly_passing", [])), "nfc", len(out.get("newly_failing_confirmed", [])))
    timing("fixcheck", time.time() - t0)
    return 0


def write_probe_to(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {k: v for k, v in data.items() if k != "failed"}
    path.write_text(json.dumps(data, ensure_ascii=False, sort_keys=True, indent=1) + "\n", encoding="utf-8")


QF2 = "9c89f1e"
QF2_PARENT = "498f3c3"
QF2_FILES = ["verantyx/semantic_wh.py", "tools/demo_question_forms.py"]


def qf2_sub(name: str) -> Path:
    d = OUT / "qf2"
    d.mkdir(parents=True, exist_ok=True)
    return d / name


# 9c89f1e の semantic_wh.py から機能を外す編集（因子）。V=役割の語彙、C=clause 形、P=role-only の問いの wh＋助詞の組の制限。
_ED_C = ["    clause_plan = _clause_wh_question(raw, b, full)\n    if clause_plan is not None:", "    clause_plan = None\n    if clause_plan is not None:"]
_ED_V = [
    ["_ROLE_NOUN = {'物': 'patient', '起点': 'source', '終点': 'limit',", "_ROLE_NOUN = {'物': 'patient', '起点': 'origin', '終点': 'recipient',"],
    ["    elif particle == 'で' and where:\n        role = 'place'", "    elif particle == 'で' and where:\n        role = 'location'"],
    ["    elif particle == 'から' and not when:\n        role = 'source'", "    elif particle == 'から' and not when:\n        role = 'origin'"],
    ["    elif particle == 'へ' and where:\n        role = 'direction'", "    elif particle == 'へ' and where:\n        role = 'recipient'"]]
_P_OLD = "            role = _requested_role(wh, particle, '', '')\n            if role is None:\n                return None\n"
# 親（498f3c3）の _CASE_ROLE と同じ「助詞だけで役割が決まる」表（wh の種類で拒否しない）。9c89f1e で足された助詞は _requested_role の語彙に合わせる。
# 親（498f3c3）の _CASE_ROLE は「助詞だけで役割が決まる」表で、wh の種類で拒否しない。_requested_role が None（組の拒否）または
# means／limit／companion（のちに拒否される）を返す組だけを、親の表の役割に戻す。受理される組の名前は 9c89f1e のまま（名前は V の因子）。
_P_NEW = ("            role = _requested_role(wh, particle, '', '')\n"
          "            if role is None or role in ('means', 'limit', 'companion'):\n"
          "                role = {'が': 'agent', 'は': 'agent', 'を': 'patient', 'に': 'recipient', 'へ': 'recipient', 'で': 'location', 'から': 'origin'}.get(particle)\n"
          "            if role is None:\n"
          "                return None\n")


def _abl_edits(v: bool, c: bool, p: bool) -> list:
    ed = []
    if c: ed.append(_ED_C)
    if v: ed += _ED_V
    if p: ed.append([_P_OLD, _P_NEW])
    return [["verantyx/semantic_wh.py", ed]]


QF2_ABLATIONS = {   # 名前 -> 外した因子の組（V, C, P）。親の受理範囲に戻すのは因子ごと。
    "no_clause_forms": (False, True, False),
    "old_role_vocabulary": (True, False, False),
    "old_role_vocabulary_no_clause_forms": (True, True, False),
    "parent_wh_particle_pairs": (False, False, True),
    "parent_wh_particle_pairs_no_clause_forms": (False, True, True),
    "parent_wh_particle_pairs_old_role_vocabulary": (True, False, True),
    "all_three_restored": (True, True, True),
}
QF2_FACTOR = {"V": "role_vocabulary", "C": "clause_forms", "P": "wh_particle_pairs"}


def qf2_ablation(a) -> int:
    ids = [l for l in qf2_sub("ids.txt").read_text(encoding="utf-8").split("\n") if l]
    out = {}
    for name, (v, c, p) in QF2_ABLATIONS.items():
        edits = _abl_edits(v, c, p)
        steps = [["overlay", QF2, QF2_FILES]] + [["edit", pth, e] for pth, e in edits]
        tree, log = make_tree(steps)
        if tree is None:
            out[name] = {"apply": log[-1]["apply"], "log": log}
            continue
        try:
            files = sorted({n.split("::", 1)[0] for n in ids})
            res = run_selected(tree, ids, files=files, pytest_args=["-q", "--continue-on-collection-errors"])
            out[name] = {"apply": "OK", "restored": [QF2_FACTOR[k] for k, f in zip("VCP", (v, c, p)) if f],
                         "status": {n: status_of(res, n) for n in ids}}
            out[name]["pass_count"] = sum(1 for v_ in out[name]["status"].values() if v_ == "PASS")
        finally:
            shutil.rmtree(tree, ignore_errors=True)
        print("ablation", name, out[name].get("pass_count"))
    write_probe_to(qf2_sub("ablation.json"), out)
    return 0


CAPTURE_SRC = r"""
import json, os, re
_cur = {"id": None}
_log = []

def _norm(x):
    return re.sub(r"0x[0-9a-f]{6,}", "0x<ADDR>", x)

def _deep(x, d=0):
    # repr がアドレスだけの記録用オブジェクト（テストの builder が持つ PatternCall など）は属性まで展開する
    if d > 5:
        return "..."
    if isinstance(x, (list, tuple)):
        inner = ", ".join(_deep(i, d + 1) for i in x)
        return "[" + inner + "]" if isinstance(x, list) else "(" + inner + ("," if len(x) == 1 else "") + ")"
    if isinstance(x, dict):
        return "{" + ", ".join(_deep(k, d + 1) + ": " + _deep(v, d + 1) for k, v in x.items()) + "}"
    r = repr(x)
    if r.startswith("<") and " at 0x" in r and hasattr(x, "__dict__") and vars(x):
        return type(x).__name__ + "(" + ", ".join(k + "=" + _deep(v, d + 1) for k, v in sorted(vars(x).items())) + ")"
    return r

def pytest_runtest_setup(item):
    _cur["id"] = item.nodeid

def pytest_configure(config):
    import verantyx.semantic_wh as wh
    orig = wh.read_role_list_question
    def wrapped(raw, b, full):
        ret = orig(raw, b, full)
        try:
            state = {k: _norm(_deep(v))[:600] for k, v in sorted(vars(b).items())}
        except Exception:
            state = {}
        _log.append({"nodeid": _cur["id"], "kind": "wh", "raw": raw, "ret": _norm(_deep(ret))[:600], "builder": state})
        return ret
    wh.read_role_list_question = wrapped
    orig_role = getattr(wh, "_requested_role", None)   # dev には無い（9c89f1e で足された関数）
    if orig_role is not None:
        import sys
        def role(*a, **k):
            lines = []
            def local(frame, event, arg):
                if event == "line": lines.append(frame.f_lineno)
                elif event == "return": lines.append(-frame.f_lineno)   # 負の数は return 文の行
                return local
            def glob(frame, event, arg):
                return local if frame.f_code is orig_role.__code__ else None
            prev = sys.gettrace()
            sys.settrace(glob)
            try:
                ret = orig_role(*a, **k)
            finally:
                sys.settrace(prev)
            _log.append({"nodeid": _cur["id"], "kind": "role", "wh": a[0] if a else None, "particle": a[1] if len(a) > 1 else None,
                         "ret": ret, "lines": lines, "caller": sys._getframe(1).f_code.co_name})
            return ret
        wh._requested_role = role
    import verantyx.semantic_reader as sr
    import verantyx.semantic_verify as sv
    oreq = sr.read_request
    def req_wrap(text, *a, **k):
        r = oreq(text, *a, **k)
        try:
            plans = [[(n.op, getattr(n.pattern, "predicate", None), [x[0] for x in getattr(n.pattern, "roles", ())]) for n in pl.nodes if n.op == "Bind"] for pl in r.plans]
            unread = len(getattr(r, "unread", ()) or ())
        except Exception:
            plans, unread = None, None
        _log.append({"nodeid": _cur["id"], "kind": "request", "question": text, "plans": _norm(repr(plans)), "unread": unread})
        return r
    sr.read_request = req_wrap
    def wrap_checker(name):
        o = getattr(sv.Checker, name)
        def w(self, *a, **k):
            try:
                doc = "".join(c.span.text for c in self.view.clauses)
            except Exception:
                doc = None
            try:
                r = o(self, *a, **k)
            except BaseException as e:
                _log.append({"nodeid": _cur["id"], "kind": "check", "api": name, "document": doc, "outcome": "raises " + type(e).__name__, "detail": _norm(str(e))[:120]})
                raise
            _log.append({"nodeid": _cur["id"], "kind": "check", "api": name, "document": doc, "outcome": "returns", "detail": _norm(_deep(r))[:200]})
            return r
        setattr(sv.Checker, name, w)
    for nm in ("audit", "proof", "gate"):
        wrap_checker(nm)
    from verantyx.one import Vera
    ofrom = Vera.from_texts.__func__
    def from_texts(cls, texts, *a, **k):
        v = ofrom(cls, texts, *a, **k)
        try: v._w1f_texts = dict(texts)
        except Exception: pass
        return v
    Vera.from_texts = classmethod(from_texts)
    oask = Vera.ask
    def ask(self, q, *a, **k):
        r = oask(self, q, *a, **k)
        _log.append({"nodeid": _cur["id"], "kind": "ask", "question": q, "texts": getattr(self, "_w1f_texts", None),
                     "verdict": r.get("verdict") if isinstance(r, dict) else None, "values": r.get("values") if isinstance(r, dict) else None})
        return r
    Vera.ask = ask

def pytest_sessionfinish(session, exitstatus):
    out = os.environ.get("W1F_CAPTURE")
    if out:
        with open(out, "w", encoding="utf-8") as fh:
            for r in _log: fh.write(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n")
"""


def qf2_capture(tree: Path, ids: list[str]) -> list[dict]:
    d = CACHE_ROOT / "capture_plugin"
    d.mkdir(parents=True, exist_ok=True)
    (d / "w1fcap.py").write_text(CAPTURE_SRC, encoding="utf-8")
    (CACHE_ROOT / "tmp").mkdir(parents=True, exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix="w1f_cap_", dir=str(CACHE_ROOT / "tmp")))
    try:
        outj = work / "cap.jsonl"
        sel = work / "sel.txt"
        sel.write_text("\n".join(ids) + "\n", encoding="utf-8")
        env = base_env(tree, {"W1F_SEL": str(sel), "W1F_CAPTURE": str(outj), "PYTHONPATH": f"{tree}:{plugin_dir()}:{d}"})
        files = sorted({n.split("::", 1)[0] for n in ids})
        subprocess.run([PY, "-m", "pytest", "-p", "no:cacheprovider", "-p", "w1fsel", "-p", "w1fcap", "-q", "--tb=no"] + files,
                       cwd=str(tree), env=env, capture_output=True, text=True, timeout=3000)
        return [json.loads(l) for l in outj.read_text(encoding="utf-8").split("\n") if l.strip()] if outj.exists() else []
    finally:
        shutil.rmtree(work, ignore_errors=True)


def qf2_cap(a) -> int:
    ids = [l for l in qf2_sub("ids.txt").read_text(encoding="utf-8").split("\n") if l]
    # qf2_vc／qf2_pc: 失敗で止まるテストが、先に当たった因子のせいで後ろの問いに進まない。他の因子を親に戻した複写で最後まで走らせ、
    # 残った因子の実行行を取る（vc = V と C を戻す→P が見える、pc = P と C を戻す→V が見える）
    variants = (("dev", []), ("qf2", [["overlay", QF2, QF2_FILES]]),
                ("qf2_vc", [["overlay", QF2, QF2_FILES]] + [["edit", pth, e] for pth, e in _abl_edits(True, True, False)]),
                ("qf2_pc", [["overlay", QF2, QF2_FILES]] + [["edit", pth, e] for pth, e in _abl_edits(False, True, True)]))
    for label, steps in variants:
        tree, _ = make_tree(steps)
        try:
            rows = qf2_capture(tree, ids)
        finally:
            shutil.rmtree(tree, ignore_errors=True)
        jdump(qf2_sub(f"capture_{label}.jsonl"), rows)
        print("capture", label, len(rows))
    return 0


ILLUSTRATIVE_DOC = "ミナは青い鍵を倉庫Cから技師ユンへ運んだ。"


def ask_many(tree: Path, doc: str, questions: list[str]) -> list[dict]:
    code = ("import json,sys\nfrom verantyx.one import Vera\nqs=json.loads(sys.stdin.read())\nout=[]\n"
            "for q in qs['q']:\n    v=Vera.from_texts({'d':qs['doc']},mode='semantic')\n    a=v.ask(q)\n"
            "    out.append({'verdict':a.get('verdict'),'values':a.get('values')})\nprint(json.dumps(out,ensure_ascii=False))\n")
    p = subprocess.run([PY, "-B", "-c", code], cwd=str(tree), env=base_env(tree, plug=False), input=json.dumps({"doc": doc, "q": questions}, ensure_ascii=False),
                       capture_output=True, text=True)
    return json.loads(p.stdout.strip().split("\n")[-1])


QF2_NEW_VOCAB = ("place", "source", "direction")      # 9c89f1e が _requested_role で新しく返す名前（旧: location・origin・recipient）
QF2_ROLE_NAMES = ("agent", "patient", "recipient", "location", "origin", "place", "source", "limit", "goal", "direction", "time", "means", "companion")


def _src_lines(sha: str) -> list[str]:
    return git("show", f"{sha}:verantyx/semantic_wh.py").split("\n")


def _ln(src: list[str], needle: str) -> int:
    return next(i for i, l in enumerate(src, 1) if needle in l)


def _role_noun_dict(sha: str) -> dict:
    m = re.search(r"_ROLE_NOUN = (\{.*?\})\n", git("show", f"{sha}:verantyx/semantic_wh.py"), re.S)
    return ast.literal_eval(m[1])


def qf2_causes(mech: list, seg: list, question: str, called_clause: bool) -> tuple[list, list]:
    """9c89f1e の semantic_wh.py のどの行が、この問いの読みを変えたか。行は推測せず、次の測定から取る:
    clause_forms = 親に無い呼び出し行（ablation が置き換えた行そのもの）、wh_particle_pairs／role_vocabulary = capture が
    sys.settrace で記録した _requested_role の実行行（None を返した return 行、または役割名を決めた代入行）、
    role-noun の問いの role_vocabulary = 親と 9c89f1e の _ROLE_NOUN の差。
    戻り値: (見つかった原因 [{order, line, factor, evidence}]、未特定の因子の理由 [{factor, reason}])。"""
    src = _src_lines(QF2)
    post = _ln(src, "if re.search(r'(?:させ|せられ)', context) and role in ('agent', 'recipient'):")
    found, unknown = [], []
    if "clause_forms" in mech:
        if called_clause:
            found.append({"order": 0, "line": _ln(src, "clause_plan = _clause_wh_question(raw, b, full)"), "factor": "clause_forms",
                          "evidence": "親に無い節単位の問いの呼び出しが role-only より先に実行され、計画を返す"})
        else:
            unknown.append({"factor": "clause_forms", "reason": "ablation では必要だが、捕捉した呼び出しに対応する wh 呼び出しが無い"})
    if "wh_particle_pairs" in mech or "role_vocabulary" in mech:
        hit = {"wh_particle_pairs": False, "role_vocabulary": False}
        for k, e in enumerate(seg, 1):
            if e["caller"] != "read_role_list_question":
                continue
            pair = f"{e['wh']}＋{e['particle']}"
            if e["ret"] is None:
                rl = next((-l for l in e["lines"] if l < 0), None)
                if "wh_particle_pairs" in mech and rl:
                    found.append({"order": k, "line": rl, "factor": "wh_particle_pairs", "evidence": f"_requested_role({pair}) が None を返す（return 行）"}); hit["wh_particle_pairs"] = True
                continue
            assign = max((l for l in e["lines"] if 0 < l < post), default=None)
            if e["ret"] in QF2_NEW_VOCAB and "role_vocabulary" in mech and assign:
                found.append({"order": k, "line": assign, "factor": "role_vocabulary", "evidence": f"_requested_role({pair}) が新しい名前 {e['ret']} を決める（代入行）"}); hit["role_vocabulary"] = True
            elif e["ret"] in ("means", "limit", "companion") and "wh_particle_pairs" in mech and assign:
                found.append({"order": k, "line": assign, "factor": "wh_particle_pairs",
                              "evidence": f"_requested_role({pair}) が {e['ret']} を決め、のちに {_ln(src, 'any(role in (')} 行で拒否される"}); hit["wh_particle_pairs"] = True
        if "role_vocabulary" in mech and not hit["role_vocabulary"]:
            par, new = _role_noun_dict(QF2_PARENT), _role_noun_dict(QF2)
            ch = [n for n in new if par.get(n) != new[n] and n in question]
            if ch:
                found.append({"order": 0.5, "line": _ln(src, "_ROLE_NOUN = {"), "factor": "role_vocabulary",
                              "evidence": "role-noun の問いの " + "・".join(f"{n}（{par.get(n)}→{new[n]}）" for n in ch) + "（_ROLE_NOUN の差）"}); hit["role_vocabulary"] = True
        for f in ("wh_particle_pairs", "role_vocabulary"):
            if f in mech and not hit[f]:
                unknown.append({"factor": f, "reason": "ablation では必要だが、捕捉した実行（_requested_role の実行行・_ROLE_NOUN の差）から原因の行を取れなかった"})
    found.sort(key=lambda x: x["order"])
    return found, unknown


def _summ(e: dict) -> dict:
    """capture の 1 件を、違いが見える要約にする（役割の組と戻り値の種類。verdict と values）。"""
    if e.get("kind") == "ask":
        return {"function": "Vera.ask", "verdict": e["verdict"], "values": e["values"]}
    if e.get("kind") == "check":
        return {"function": "Checker." + e["api"], "outcome": e["outcome"], "detail": e["detail"]}
    if e.get("kind") == "request":
        return {"function": "read_request", "plans": e["plans"], "unread": e["unread"]}
    txt = " ".join(str(x) for x in list((e.get("builder") or {}).values()) + [e.get("ret")])
    roles = list(dict.fromkeys(re.findall(r"\('(" + "|".join(QF2_ROLE_NAMES) + r")', ", txt)))   # 出現順・重複なし
    m = re.match(r"\('(\w+)'", e["ret"])
    kind = m[1] if m else ("None" if e["ret"] == "None" else ("builder の戻り値" if e["ret"].startswith("<object") else re.match(r"\w+", e["ret"])[0]))
    return {"function": "read_role_list_question", "returned": kind, "roles": roles,
            "plan": e["ret"], "builder": e.get("builder")}


def qf2_pick(dc: list, qc: list):
    """テストが公開の入口（Vera.ask）を呼ぶなら、その ask（テスト自身の文書と問い）を優先して選ぶ。次に semantic_verify の Checker
    （audit／proof／gate）、semantic_reader.read_request、最後に read_role_list_question の直接呼び出し。違いが出た最初の組。"""
    da = [e for e in dc if e["kind"] == "ask"]; qa = [e for e in qc if e["kind"] == "ask"]
    for d, q in zip(da, qa):
        if d["question"] == q["question"] and (d["verdict"], d["values"]) != (q["verdict"], q["values"]):
            return "ask", d, q, None
    dk = [e for e in dc if e["kind"] == "check"]; qk = [e for e in qc if e["kind"] == "check"]
    for d, q in zip(dk, qk):
        if d["api"] == q["api"] and (d["outcome"], d["detail"]) != (q["outcome"], q["detail"]):
            return "check", d, q, None
    dr = [e for e in dc if e["kind"] == "request"]; qr = [e for e in qc if e["kind"] == "request"]
    for d, q in zip(dr, qr):
        if d["question"] == q["question"] and (d["plans"], d["unread"]) != (q["plans"], q["unread"]):
            return "request", d, q, None
    dw = [e for e in dc if e["kind"] == "wh"]; qw = [e for e in qc if e["kind"] == "wh"]
    for j, (d, q) in enumerate(zip(dw, qw)):
        if d["raw"] == q["raw"] and (d["ret"], d.get("builder")) != (q["ret"], q.get("builder")):
            return "wh", d, q, j
    return None, None, None, None


def _qf2_groups(dc: list, qc: list) -> list:
    """dev と比べて結果が違った wh 呼び出しごとに (問い, その呼び出し中の _requested_role 記録, 戻り値が None でないか)。"""
    dw = [e for e in dc if e["kind"] == "wh"]
    widx = [i for i, e in enumerate(qc) if e["kind"] == "wh"]
    groups = []
    for jj, (dd, qi) in enumerate(zip(dw, widx)):
        qq = qc[qi]
        if dd["raw"] == qq["raw"] and (dd["ret"], dd.get("builder")) != (qq["ret"], qq.get("builder")):
            start = (widx[jj - 1] + 1) if jj else 0
            groups.append((qq["raw"], [e for e in qc[start:qi] if e["kind"] == "role"], qq["ret"] != "None"))
    return groups


def qf2_repro(a) -> int:
    ids = [l for l in qf2_sub("ids.txt").read_text(encoding="utf-8").split("\n") if l]
    dev = jload(qf2_sub("capture_dev.jsonl")); qf = jload(qf2_sub("capture_qf2.jsonl"))
    qf_vc = jload(qf2_sub("capture_qf2_vc.jsonl")); qf_pc = jload(qf2_sub("capture_qf2_pc.jsonl"))
    abl = json.loads(qf2_sub("ablation.json").read_text(encoding="utf-8"))
    FACT = list(QF2_FACTOR.values())
    sets = {name: frozenset(v["restored"]) for name, v in abl.items() if v.get("apply") == "OK"}
    rows, wh_questions = [], []
    for nid in ids:
        dc = [c for c in dev if c["nodeid"] == nid]; qc = [c for c in qf if c["nodeid"] == nid]
        kind, d, q, j = qf2_pick(dc, qc)
        # 機構: 通った変種のうち、包含で最小のもの（それぞれが「その因子を親に戻せば通る」十分な組）。因子の和を機構とする
        passing = [sets[n] for n in sets if abl[n]["status"].get(nid) == "PASS"]
        minimal = [x for x in passing if not any(y < x for y in passing)]
        minimal = sorted(set(minimal), key=lambda x: (len(x), sorted(x)))
        mech = [f for f in FACT if any(f in x for x in minimal)] or ["unidentified"]
        question = ({"wh": lambda: d["raw"], "ask": lambda: d["question"], "request": lambda: d["question"],
                     "check": lambda: next((e["question"] for e in dc if e["kind"] == "request"), "")}[kind]()) if kind else ""
        # 原因の行は、このテストの中で dev と 9c89f1e の結果が違った wh 呼び出しすべての実行記録から取る（最初の 1 件だけでは、
        # 同じテストが別の問いで別の機構にも当たるのを見落とす）
        found = []
        seen = set()
        def collect(cap_dev, cap_var, factors, label):
            groups = _qf2_groups(cap_dev, cap_var)
            if not groups:
                groups = [(question, [e for e in cap_var if e["kind"] == "role"], any(e["kind"] == "wh" and e["ret"] != "None" for e in cap_var))]
            for raw_q, seg, called in groups:
                f1, _u = qf2_causes(factors, seg, raw_q, called)
                for f in f1:
                    key = (f["factor"], f["line"])
                    if key not in seen:
                        seen.add(key); found.append({**f, "question": raw_q, "captured_in": label})
        collect(dc, qc, mech, "dev+9c89f1e")
        got0 = {f["factor"] for f in found}
        # まだ原因の行が取れていない因子は、他の因子を親に戻した複写の実行記録から取る
        if "wh_particle_pairs" in mech and "wh_particle_pairs" not in got0:
            collect(dc, [c for c in qf_vc if c["nodeid"] == nid], ["wh_particle_pairs"], "V と C を親に戻した複写")
        if "role_vocabulary" in mech and "role_vocabulary" not in got0:
            collect(dc, [c for c in qf_pc if c["nodeid"] == nid], ["role_vocabulary"], "P と C を親に戻した複写")
        found.sort(key=lambda x: (x["captured_in"] != "dev+9c89f1e", x["order"], x["line"]))   # 9c89f1e そのものの実行で最初に当たった行を先頭にする
        got = {f["factor"] for f in found}
        unknown = [{"factor": f, "reason": "ablation ではこの因子を親に戻すと通るが、捕捉した実行（_requested_role の実行行・_ROLE_NOUN の差・clause 呼び出し）から原因の行を取れなかった"}
                   for f in mech if f not in got]
        if kind == "wh":
            wh_questions.append(d["raw"])
        rows.append({"nid": nid, "kind": kind, "d": d, "q": q, "dc": dc, "mech": mech, "minimal": [sorted(x) for x in minimal], "found": found, "unknown": unknown})
    wq = sorted(set(wh_questions))
    tdev, _ = make_tree([]); tqf, _ = make_tree([["overlay", QF2, QF2_FILES]])
    try:
        ask_dev = dict(zip(wq, ask_many(tdev, ILLUSTRATIVE_DOC, wq))) if wq else {}
        ask_qf = dict(zip(wq, ask_many(tqf, ILLUSTRATIVE_DOC, wq))) if wq else {}
    finally:
        shutil.rmtree(tdev, ignore_errors=True); shutil.rmtree(tqf, ignore_errors=True)
    out = []
    for r in rows:
        d, q, kind = r["d"], r["q"], r["kind"]
        if kind == "wh":
            question = d["raw"]; doc = ILLUSTRATIVE_DOC
            src = "illustrative document（テストは semantic_wh.read_role_list_question を直接呼び、文書を持たない）。ask の欄はこの説明用の文書で Vera.ask に同じ問いを与えた結果"
            dev_out = {**_summ(d), "ask_on_illustrative_document": ask_dev.get(question)}
            qf_out = {**_summ(q), "ask_on_illustrative_document": ask_qf.get(question)}
        elif kind == "ask":
            question = d["question"]; doc = "".join((d.get("texts") or {}).values()); src = "テスト自身の文書と問い（Vera.ask を通る）"
            dev_out, qf_out = _summ(d), _summ(q)
        elif kind == "check":
            req = next((e for e in r["dc"] if e["kind"] == "request"), None)
            question = req["question"] if req else ""; doc = d["document"] or ILLUSTRATIVE_DOC
            src = "テスト自身の文書と問い（semantic_verify.Checker を直接呼ぶ）" if d["document"] else "illustrative document"
            dev_out, qf_out = _summ(d), _summ(q)
        elif kind == "request":
            question = d["question"]; doc = ILLUSTRATIVE_DOC
            src = "illustrative document（テストは semantic_reader.read_request に問いだけを与え、文書を持たない）"
            dev_out, qf_out = _summ(d), _summ(q)
        else:
            question = doc = ""; src = "捕捉した呼び出しに違いが無い"; dev_out = qf_out = {}
        if r["found"]:
            cause = f"{QF2}:verantyx/semantic_wh.py:{r['found'][0]['line']}"
        else:
            cause = "UNIDENTIFIED"
        out.append({"nodeid": r["nid"], "hunks": r["mech"], "sufficient_sets": r["minimal"], "question": question, "document": doc, "document_source": src,
                    "dev": dev_out, "qf2": qf_out, "cause": cause,
                    "cause_trace": [{"factor": f["factor"], "line": f"{QF2}:verantyx/semantic_wh.py:{f['line']}", "question": f.get("question"), "captured_in": f["captured_in"], "evidence": f["evidence"]} for f in r["found"]],
                    "cause_unidentified": r["unknown"]})
    jdump(qf2_sub("repro.jsonl"), out)
    from collections import Counter
    print(Counter((tuple(r["hunks"]), r["cause"]) for r in out))
    print("unidentified:", sum(1 for r in out if r["cause_unidentified"] or r["cause"] == "UNIDENTIFIED"))
    return 0


DEMO_ENV = {  # manifest_wave4.json の env（読み取り専用のデータを指す。VERA_CORPUS_ROOT だけは空のディレクトリを CACHE に作る）
    "VERA_LEADS": "/Users/motonisihikoudai/vera-wiring/data/jawiki_leads.full.jsonl",
    "VERA_REAL_QUESTIONS": "/Users/motonisihikoudai/vera-wiring/data/real_agent_questions.jsonl",
    "VERA_CORPUS_DIR": "/Users/motonisihikoudai/vera-codex-corpus",
}


def run_demo(tree: Path, off: str | None = None) -> str:
    empty = CACHE_ROOT / "empty_materials"
    empty.mkdir(parents=True, exist_ok=True)
    env = base_env(tree, {**DEMO_ENV, "VERA_CORPUS_ROOT": str(empty), **({"VERA_CONSTRUCTIONS_OFF": off} if off else {})}, plug=False)
    if not (tree / "tools" / "demo_question_forms.py").exists():
        return "NO_DEMO_FILE"
    p = subprocess.run([PY, "-B", "tools/demo_question_forms.py"], cwd=str(tree), env=env, capture_output=True, text=True, timeout=900)
    lines = [l for l in (p.stdout + "\n" + p.stderr).split("\n") if l.strip()]
    last = lines[-1] if lines else ""
    err = next((l for l in reversed(lines) if l.startswith("AssertionError")), "")
    return norm_out(("DEMO OK" if last.strip() == "DEMO OK" else (err or last)))[:300]


def qf2_demo(a) -> int:
    chain_new = git("log", "--first-parent", "--format=%h", "9c89f1e..57079df").split()
    shas = [QF2_PARENT, QF2] + list(reversed(chain_new))
    lines = []
    def one(sha):
        tree = extract(sha)
        try:
            return sha, run_demo(tree)
        finally:
            shutil.rmtree(tree, ignore_errors=True)
    with cf.ThreadPoolExecutor(max_workers=3) as ex:
        res = dict(ex.map(one, shas))
    for sha in shas:
        lines.append(f"{sha}\t{git('log', '-1', '--format=%s', sha).strip()}\t{res[sha]}")
    qf2_sub("demo_bisect.txt").write_text("env: manifest_wave4.json の env（VERA_CORPUS_ROOT は空ディレクトリ）\n" + "\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    # DEV + qf2 での構文規則 leave-one-out
    tree, _ = make_tree([["overlay", QF2, QF2_FILES]])
    try:
        p = subprocess.run([PY, "-B", "-c", "from verantyx.constructions import discover; print(','.join(sorted(c.name for c in discover())))"],
                           cwd=str(tree), env=base_env(tree, plug=False), capture_output=True, text=True)
        names = p.stdout.strip().split(",")
    finally:
        shutil.rmtree(tree, ignore_errors=True)
    def loo(name):
        t, _ = make_tree([["overlay", QF2, QF2_FILES]])
        try:
            return name, run_demo(t, None if name == "(none off)" else ("ALL" if name == "(all off)" else name) if name != "(all off)" else ",".join(names))
        finally:
            shutil.rmtree(t, ignore_errors=True)
    todo = ["(none off)", "(all off)"] + names
    with cf.ThreadPoolExecutor(max_workers=3) as ex:
        res2 = dict(ex.map(loo, todo))
    out = ["dev + qf2(9c89f1e) の複写。構文規則を 1 つずつ VERA_CONSTRUCTIONS_OFF で外してデモを走らせた結果"] + [f"{n}\t{res2[n]}" for n in todo]
    qf2_sub("demo_leave_one_out.txt").write_text("\n".join(out) + "\n", encoding="utf-8")
    print("\n".join(out))
    return 0


QF2_HARM_RULES = [   # (害の段, 失敗の 1 行目に当てる正規表現, 理由)。上から最初に当たったもの。10 節の害の段の定義を失敗出力に当てはめる規則
    # （規則は 1 回目の失敗出力を見たあとで、定義に沿って書いた。UNCLASSIFIED が出たら report が落ちる）
    ("A", r"'ANSWER' != 'ANSWER'|DID NOT RAISE", "偽の断定: 答えてはいけない入力に ANSWER を返す／対立する主張に Conflict を出さない"),
    ("C", r"assert (None|\[\]) (==|is)|IndexError|Rejected:", "安全側の取りこぼし: 読めるはずの問いが読まれず（計画 None・空）、または完全な答えの提案が拒否され、答えるべきところで棄権する"),
    ("D", r"At index \d+ diff|assert \[.*\] == \[|AssertionError: assert \(\(|assert CapturedPattern|assert \d+ == \d+",
     "書式・API の形: 答えの有無ではなく、計画の形（役割の名前・束縛の数）だけが違う"),
]


def qf2_harm(err: str) -> tuple[str, str]:
    for h, pat, why in QF2_HARM_RULES:
        if re.search(pat, err):
            return h, why
    return "UNCLASSIFIED", "規則に当たらない失敗出力（人が読んで規則を足すこと）"


def qf2_errors(ids: list[str]) -> None:
    """dev + qf2 の複写で 34 件を 1 件ずつ実行し、失敗の 1 行目（E …）を保存する（害の段を失敗出力から決める根拠）。"""
    tree, _ = make_tree([["overlay", QF2, QF2_FILES]])
    try:
        def one(n):
            res = run_selected(tree, [n], pytest_args=["-vv", "--tb=short", "--continue-on-collection-errors"])
            out = norm_out(res["stdout"])
            return {"nodeid": n, "status": status_of(res, n), "self_first_error": _first_error_line(out)}
        with cf.ThreadPoolExecutor(max_workers=4) as ex:
            rows = list(ex.map(one, ids))
    finally:
        shutil.rmtree(tree, ignore_errors=True)
    for r in rows:
        r["harm"], r["harm_reason"] = qf2_harm(r["self_first_error"])
    jdump(qf2_sub("own_commit_errors.jsonl"), rows)
    from collections import Counter
    print("own_commit_errors", Counter(r["harm"] for r in rows), Counter(r["status"] for r in rows))


def cmd_qf2(a) -> int:
    """w_question_forms2（9c89f1e）の 34 件: ids／own_commit／constructions_off／ablation／repro／demo。"""
    t0 = time.time()
    steps = a.rest or ["ids", "own", "off"]
    if steps == ["abl"]:
        return qf2_ablation(a)
    if steps == ["cap"]:
        return qf2_cap(a)
    if steps == ["repro"]:
        return qf2_repro(a)
    if steps == ["demo"]:
        return qf2_demo(a)
    bl = set(read_bl())
    if "ids" in steps:
        r = variant_run([["overlay", QF2, QF2_FILES]], bl)
        newly = sorted(r["newly_failing"]); fixed = sorted(r["newly_passing"])
        qf2_sub("ids.txt").write_text("\n".join(newly) + "\n", encoding="utf-8")
        qf2_sub("fixed_ids.txt").write_text("\n".join(fixed) + "\n", encoding="utf-8")
        qf2_sub("suite_line.txt").write_text(r["summary_line"] + "\n", encoding="utf-8")
        print("ids", len(newly), "fixed", len(fixed))
    ids = [l for l in qf2_sub("ids.txt").read_text(encoding="utf-8").split("\n") if l]
    if "own" in steps:
        status = {n: {} for n in ids}
        for label, sha in (("parent", QF2_PARENT), ("self", QF2)):
            tree = extract(sha)
            try:
                files = sorted({n.split("::", 1)[0] for n in ids})
                res = run_selected(tree, ids, files=files, pytest_args=["-q", "--continue-on-collection-errors"])
                for n in ids:
                    st = status_of(res, n)
                    status[n][label] = {"PASS": "PASS", "FAIL": "FAIL"}.get(st, st)
            finally:
                shutil.rmtree(tree, ignore_errors=True)
        out = {"parent": QF2_PARENT, "self": QF2, "status": status,
               "parent_pass_self_fail": sum(1 for v in status.values() if v == {"parent": "PASS", "self": "FAIL"})}
        write_probe_to(qf2_sub("own_commit.json"), out)
        print("own_commit parent PASS & self FAIL:", out["parent_pass_self_fail"], "of", len(ids))
    if "err" in steps:
        qf2_errors(ids)
    if "off" in steps:
        tree, _ = make_tree([["overlay", QF2, QF2_FILES]])
        try:
            p = subprocess.run([PY, "-B", "-c", "from verantyx.constructions import discover; print(','.join(sorted(c.name for c in discover())))"],
                               cwd=str(tree), env=base_env(tree, plug=False), capture_output=True, text=True)
            allnames = p.stdout.strip()
            files = sorted({n.split("::", 1)[0] for n in ids})
            res_on = run_selected(tree, ids, files=files, pytest_args=["-q"])
            res_off = run_selected(tree, ids, files=files, extra_env={"VERA_CONSTRUCTIONS_OFF": allnames}, pytest_args=["-q"])
        finally:
            shutil.rmtree(tree, ignore_errors=True)
        out = {"constructions": allnames.split(","), "env": "VERA_CONSTRUCTIONS_OFF=<all constructions>",
               "on": {n: status_of(res_on, n) for n in ids}, "off": {n: status_of(res_off, n) for n in ids}}
        out["still_fail_with_all_constructions_off"] = sum(1 for v in out["off"].values() if v == "FAIL")
        write_probe_to(qf2_sub("constructions_off.json"), out)
        print("constructions off: still FAIL", out["still_fail_with_all_constructions_off"], "of", len(ids))
    timing("qf2-" + "-".join(steps), time.time() - t0)
    return 0


# --------------------------------------------------------------------------
# report / check（decisions.jsonl 等の手書き入力と測定を突き合わせ、triage／bundles／tickets／文書の生成ブロックを作る）
# --------------------------------------------------------------------------
CATS = ["製品の不具合", "期待値が古い", "テスト同士の矛盾", "テストの不備", "判断が要る"]
NEED = {"製品の不具合": "bundle", "期待値が古い": "changed_in", "テスト同士の矛盾": "partner", "判断が要る": "decision_needed"}


def _jl(rel: str):
    return json.loads((ROOT / rel).read_text(encoding="utf-8"))


def _line_ok(loc: str) -> bool:
    parts = loc.split(":")
    if len(parts) == 3:
        sha, path, ln = parts
    else:
        (path, ln), sha = parts, DEV
    r = subprocess.run(["git", "-C", str(ROOT), "show", f"{sha}:{path}"], capture_output=True, text=True)
    return r.returncode == 0 and ln.isdigit() and 1 <= int(ln) <= len(r.stdout.splitlines())


def demo_harm() -> str:
    """デモの失敗（qf2/demo_leave_one_out.txt の (none off) 行）から害の段を決める。wrong_other（出典の無い誤答）が増えたら A。"""
    for l in (OUT / "qf2" / "demo_leave_one_out.txt").read_text(encoding="utf-8").split("\n"):
        if l.startswith("(none off)\tAssertionError: "):
            tup = ast.literal_eval(l.split("AssertionError: ", 1)[1])
            return "A" if tup[2].get("wrong_other", 0) > tup[1].get("wrong_other", 0) else "UNCLASSIFIED"
    return "UNCLASSIFIED"


def build_all() -> dict:
    bl = read_bl()
    dec = jload(OUT / "decisions.jsonl")
    runs = {r["nodeid"]: r for r in jload(OUT / "runs_index.jsonl")}
    hist = {r["nodeid"]: r for r in jload(OUT / "history.jsonl")}
    intent = {r["commit"][:7]: r for r in jload(OUT / "intent.jsonl")}
    binp = jload(OUT / "bundles_input.jsonl")
    drafts = jload(OUT / "ticket_drafts.jsonl")
    triage = []
    for d in dec:
        h = hist[d["nodeid"]]; r = runs[d["nodeid"]]
        t = dict(d)
        t["first_bad"] = h.get("first_bad"); t["last_good"] = h.get("last_good"); t["born_red"] = h["born_red"]
        t["added_in"] = h["added_in"]; t["status_at_added"] = h["status_at_added"]
        t["isolated_outcome"] = r["outcome"]; t["first_error_line"] = r["first_error_line"]
        triage.append(t)
    triage.sort(key=lambda t: bl.index(t["nodeid"]))
    bundles = []
    for b in binp:
        fx = _jl(f"artifacts/w1-f/fixes/{b['bundle']}.json") if (OUT / "fixes" / f"{b['bundle']}.json").exists() else None
        f2 = dict(b["f2"])
        if fx and fx.get("apply") == "OK":
            ok = fx["before"] == "FAIL" and fx.get("after") == "PASS" and fx["only_product_files"]
            f2.update({"result": "PASS" if ok else "NOT_SHOWN", "output": f"artifacts/w1-f/fixes/{b['bundle']}.txt", "before": fx["before"], "after": fx.get("after"),
                       "newly_passing": fx["newly_passing"], "newly_failing_confirmed": fx["newly_failing_confirmed"]})
            if not ok:
                f2["reason"] = "before/after/only_product_files のいずれかが満たされない"
        else:
            f2.update({"result": "NOT_SHOWN", "reason": "fixcheck の出力が無い／差分が当たらない"})
        bb = dict(b); bb["f2"] = f2
        bundles.append(bb)
    hmap = {t["nodeid"]: t["harm"] for t in triage}
    for bb in bundles:       # 束の害は、含まれるテストの最も重い害（手で書かない）
        bb["harm"] = min((hmap[x] for x in bb["tests"]), key=lambda x: "ABCD".index(x))
    tickets = []
    for d in drafts:
        tests = [bl[n - 1] for n in d["ns"]]
        if d.get("harm_from") == "qf2_errors":      # w_question_forms2 の 34 件: 失敗出力（qf2/own_commit_errors.jsonl）から機械的に決める
            er = jload(OUT / "qf2" / "own_commit_errors.jsonl")
            harms, tc = [r["harm"] for r in er], len(er)
        elif d.get("harm_from") == "demo":           # デモの失敗: wrong_other が増えるなら偽の断定（A）
            harms, tc = [demo_harm()], 0
        else:
            harms, tc = [hmap[x] for x in tests], len(tests)
        harm = min(harms, key=lambda x: "ABCD".index(x if x in "ABCD" else "Z")) if harms else "UNCLASSIFIED"
        tickets.append({"title": d["title"], "purpose": d["purpose"], "files_to_touch": d["files_to_touch"], "acceptance": d["acceptance"],
                        "harm": harm, "test_count": tc, "bundles": d.get("bundles", []), "ns": d["ns"]})
    key = lambda t: ("ABCD".index(t["harm"]) if t["harm"] in ("A", "B", "C", "D") else 9, -t["test_count"])
    tickets.sort(key=lambda t: (key(t), t["title"]))     # 並べる順だけ（同順位の rank は同じ）。タイトル順は勝者を作らない（rank が同じ）
    for i, t in enumerate(tickets):
        t["rank"] = 1 + sum(1 for u in tickets if key(u) < key(t))
    return {"bl": bl, "dec": dec, "triage": triage, "bundles": bundles, "tickets": tickets, "intent": intent}


def validate(A: dict) -> list[str]:
    bad = []
    bl, triage, intent = A["bl"], A["triage"], A["intent"]
    ids = [t["nodeid"] for t in triage]
    if sorted(ids) != sorted(bl) or len(set(ids)) != 124:
        bad.append("nodeid set != baseline 124")
    allc = set((OUT / "collect_nodeids.txt").read_text(encoding="utf-8").split("\n"))
    for t in triage:
        n, c = t["nodeid"], t.get("category")
        if c not in CATS: bad.append(f"category {c!r}: {n}")
        if not t.get("summary"): bad.append("no summary: " + n)
        if not t.get("cause_locations") or not all(_line_ok(x) for x in t["cause_locations"]): bad.append("cause_locations: " + n)
        if not t.get("evidence"): bad.append("no evidence: " + n)
        for e in t.get("evidence", []):
            f = ROOT / e["file"]
            if not f.exists() or e["excerpt"] not in f.read_text(encoding="utf-8", errors="replace"): bad.append("excerpt not in file: " + n + " " + e["file"])
        if not (ROOT / t.get("isolated_run", "")).is_file(): bad.append("isolated_run: " + n)
        need = NEED.get(c)
        if need and not t.get(need): bad.append(f"{need} missing: {n}")
        if c == "テスト同士の矛盾":
            if t.get("partner") not in allc: bad.append("partner not collected: " + n)
            try:
                pj = _jl(t["partner_probe"])
                if n not in pj.get("newly_passing", []) or t["partner"] not in pj.get("newly_failing_confirmed", []): bad.append("partner_probe does not show the pair: " + n)
            except Exception as ex:
                bad.append(f"partner_probe {ex}: {n}")
        if c == "期待値が古い":
            ci = (t.get("changed_in") or "")[:7]
            if subprocess.run(["git", "-C", str(ROOT), "cat-file", "-e", ci + "^{commit}"]).returncode != 0: bad.append("changed_in not a commit: " + n)
            if ci not in intent: bad.append("no intent row for changed_in: " + n)
            else:
                it = intent[ci]
                if it["quote"] not in Path(it["source"]).read_text(encoding="utf-8", errors="replace"): bad.append("intent quote not in source: " + ci)
            if t.get("adapt_probe") and n not in _jl(t["adapt_probe"]).get("passes", []): bad.append("adapt_probe does not pass: " + n)
        if c == "製品の不具合" and t.get("bundle") not in {b["bundle"] for b in A["bundles"]}: bad.append("bundle unknown: " + n)
        if n.startswith("tests/attack/") and not t.get("principle"): bad.append("principle missing: " + n)
        if t.get("harm") not in ("A", "B", "C", "D"): bad.append("harm: " + n)
        if t.get("isolated_outcome") != "failed": bad.append("isolated outcome is not failed: " + n)
    for b in A["bundles"]:
        if b["f2"]["result"] == "PASS" and b["f2"]["test"] not in b["tests"]: bad.append("f2 test not in bundle: " + b["bundle"])
        if not _line_ok(b["cause"]): bad.append("bundle cause line: " + b["bundle"])
        for t in b["tests"]:
            row = next((x for x in triage if x["nodeid"] == t), None)
            if row is None or row.get("bundle") != b["bundle"]: bad.append(f"bundle member not labelled: {b['bundle']} {t}")
    for b in A["bundles"]:
        if b.get("harm") not in ("A", "B", "C", "D"): bad.append("bundle harm: " + b["bundle"])
        for sp in b.get("split", []):
            if not (OUT / "fixes" / f"{b['bundle']}_{sp['name']}.json").is_file(): bad.append(f"bundle split measurement missing: {b['bundle']} {sp['name']}")
    ids = [l for l in (OUT / "qf2" / "ids.txt").read_text(encoding="utf-8").split("\n") if l]
    er = jload(OUT / "qf2" / "own_commit_errors.jsonl")
    if sorted(r["nodeid"] for r in er) != sorted(ids): bad.append("own_commit_errors ids != ids.txt")
    for r in er:
        if r["status"] != "FAIL" or not r["self_first_error"]: bad.append("own_commit_errors row: " + r["nodeid"])
        if r["harm"] != qf2_harm(r["self_first_error"])[0] or r["harm"] not in ("A", "B", "C", "D"): bad.append("own_commit_errors harm: " + r["nodeid"])
    for r in jload(OUT / "qf2" / "repro.jsonl"):
        if r["cause"] == "UNIDENTIFIED" and not r["cause_unidentified"]: bad.append("qf2 repro: unidentified cause without a typed reason: " + r["nodeid"])
        if r["document_source"].startswith("illustrative") and "read_role_list_question" not in r["document_source"] and "read_request" not in r["document_source"]:
            bad.append("qf2 repro: illustrative document without a stated reason: " + r["nodeid"])
    if demo_harm() not in ("A", "B", "C", "D"): bad.append("demo harm")
    T = A["tickets"]
    for t in T:
        if t["harm"] not in ("A", "B", "C", "D"): bad.append("ticket harm: " + t["title"])
    if bad: return bad
    key = lambda t: ("ABCD".index(t["harm"]), -t["test_count"])
    for a, b in zip(T, T[1:]):
        if key(a) > key(b): bad.append(f"ticket order {a['title']}")
        if key(a) == key(b) and a["rank"] != b["rank"]: bad.append("ticket tie rank")
        if key(a) < key(b) and not a["rank"] < b["rank"]: bad.append("ticket rank not increasing")
    cover = sorted(n for t in T for n in t["ns"])
    if cover != list(range(1, 125)): bad.append("ticket drafts do not cover each failing test exactly once")
    return bad


def _short(nid: str, k: int = 100) -> str:
    return nid if len(nid) <= k else nid[:k] + "…"


def _cell(x) -> str:
    return str(x).replace("|", "\\|").replace("\n", " ")


def render_blocks(A: dict) -> dict:
    from collections import Counter
    triage, bundles, tickets, bl = A["triage"], A["bundles"], A["tickets"], A["bl"]
    B: dict = {}
    # measure
    collect = (OUT / "collect.txt").read_text(encoding="utf-8").strip()
    cmp_b = (OUT / "suite_before_compare.txt").read_text(encoding="utf-8").strip().replace("\n", " / ")
    runs = jload(OUT / "runs_index.jsonl"); hist = jload(OUT / "history.jsonl")
    cd = (OUT / "collect_delta.txt").read_text(encoding="utf-8").strip().replace("\n", " / ")
    oc = Counter(r["outcome"] for r in runs)
    sa = Counter(h["status_at_added"] for h in hist)
    ver = sum(1 for h in hist if h["status_at_added"] in GOOD and h.get("verified"))
    L = [f"- 収集（`collect.txt`）: {collect}", f"- 差分（`collect_delta.txt`）: {cd}",
         f"- 作業前の全体実行と基線の照合（`suite_before_compare.txt`）: {cmp_b}",
         f"- 1 件ずつ別プロセスで実行（`runs_index.jsonl`）: {dict(oc)}、隔離違反 {sum(1 for r in runs if r['violations'])} 件",
         f"- 履歴（`history.jsonl`）: 追加時の状態 {dict(sa)}、境界の両端を実測で確かめた件数 {ver}"]
    B["measure"] = "\n".join(L)
    # counts
    cc = Counter(t["category"] for t in triage)
    hh = Counter((t["category"], t["harm"]) for t in triage)
    rows = ["| 分類 | 件数 | 害 A | 害 B | 害 C | 害 D |", "|---|---:|---:|---:|---:|---:|"]
    for c in CATS:
        rows.append(f"| {c} | {cc[c]} | " + " | ".join(str(hh[(c, x)]) for x in "ABCD") + " |")
    rows.append(f"| 合計 | {sum(cc.values())} | " + " | ".join(str(sum(hh[(c, x)] for c in CATS)) for x in "ABCD") + " |")
    fb = Counter((t["first_bad"] or "-")[:7] if not t["born_red"] else "born_red" for t in triage)
    cm = {t["first_bad"][:7]: None for t in triage if t["first_bad"]}
    rows2 = ["| 落ち始めのコミット | unit（件名） | 件数 | 分類の内訳 |", "|---|---|---:|---|"]
    for c, n in sorted(fb.items(), key=lambda kv: (-kv[1], kv[0])):
        subj = git("log", "-1", "--format=%s", c).strip() if c not in ("-", "born_red") else ("生まれたときから赤（追加コミットで既に FAIL）" if c == "born_red" else "")
        inside = Counter(t["category"] for t in triage if ((t["first_bad"] or "-")[:7] if not t["born_red"] else "born_red") == c)
        rows2.append(f"| {c} | {subj} | {n} | " + "、".join(f"{k} {v}" for k, v in sorted(inside.items())) + " |")
    B["counts"] = "\n".join(rows) + "\n\n" + "\n".join(rows2)
    # per-test table
    T = ["| n | 分類 | 害 | テスト（nodeid） | 理由（1 文目） | 原因の箇所 | 束／落ち始め／相手 | 根拠 |", "|---:|---|---|---|---|---|---|---|"]
    for i, t in enumerate(triage, 1):
        reason = t["summary"].split("。")[0] + "。"
        link = {"製品の不具合": lambda: t["bundle"],
                "テスト同士の矛盾": lambda: "相手: " + _short(t["partner"], 60),
                "期待値が古い": lambda: "changed_in " + t["changed_in"][:7],
                "テストの不備": lambda: ("生まれたときから赤（追加コミット " + t["added_in"][:7] + " で既に FAIL）" if t["born_red"] else "単独と全体で結果が違う／環境依存"),
                "判断が要る": lambda: "決定が要る"}[t["category"]]()
        ev = ", ".join(sorted({e["file"].replace("artifacts/w1-f/", "") for e in t["evidence"]}))
        T.append(f"| {i} | {t['category']} | {t['harm']} | `{_cell(_short(t['nodeid'], 90))}` | {_cell(reason)} | {_cell(', '.join(t['cause_locations']))} | {_cell(link)} | {_cell(ev)} |")
    B["table"] = "\n".join(T)
    # bundles
    X = ["| 束 | 原因の箇所 | 束のテスト | 害 | 原則 | F2（直す前→後） | 全体での新規失敗（単独で確認） | 新規通過 |", "|---|---|---:|---|---|---|---|---:|"]
    for b in bundles:
        f2 = b["f2"]
        X.append(f"| {b['bundle']} | {_cell(b['cause'] + (' ＋ ' + ', '.join(b['cause_also']) if b.get('cause_also') else ''))} | {len(b['tests'])} | {b['harm']} | {_cell(b['principle'])} | {f2['result']}（{f2.get('before')}→{f2.get('after')}、`{f2['diff'].replace('artifacts/w1-f/', '')}`） | {len(f2.get('newly_failing_confirmed', []))} 件 | {len(f2.get('newly_passing', []))} |")
    B["bundles"] = "\n".join(X)
    BP = ["| 束 | 差分の一部 | 触る行 | 束のテストごとの結果（その一部だけを 075d486 に当てた複写） |", "|---|---|---|---|"]
    for b in bundles:
        full = _jl(f"artifacts/w1-f/fixes/{b['bundle']}.json")
        for sp in b.get("split", []):
            m = _jl(f"artifacts/w1-f/fixes/{b['bundle']}_{sp['name']}.json")
            BP.append(f"| {b['bundle']} | {sp['name']}（`{sp['diff'].replace('artifacts/w1-f/', '')}`） | {_cell(', '.join(m['touched']))} | " +
                      "；".join(f"n={A['bl'].index(n) + 1} `{n.split('::')[-1].split('[')[0]}` = {v}" for n, v in m["tests"].items()) + " |")
        if b.get("split"):
            BP.append(f"| {b['bundle']} | 両方（`fixes/{b['bundle']}.diff`） | 全部 | " + "；".join(f"n={A['bl'].index(n) + 1} `{n.split('::')[-1].split('[')[0]}` = {'PASS' if n in full['newly_passing'] else 'FAIL'}" for n in b["tests"]) + " |")
    B["bundle_parts"] = "\n".join(BP)
    # probes
    P = ["| コミット | unit | 逆適用 | 本人が通った基線の失敗 | 新規失敗（単独で確認） |", "|---|---|---|---:|---:|"]
    for f in sorted((OUT / "probes").glob("revert_*.json")):
        d = json.loads(f.read_text(encoding="utf-8"))
        ap = d["apply"] + (f"（{d['log'][0].get('rejected_hunks')}/{d['log'][0].get('total_hunks')} hunk が当たらず）" if d["apply"] == "PARTIAL_REJECT" else "")
        P.append(f"| {d['commit'][:7]} | {d['subject']} | {ap} | {len(d.get('newly_passing', []))} | {len(d.get('newly_failing_confirmed', []))} |")
    P2 = ["| adapter | tests/ 以外に触れない | 通る基線の失敗 | 残る | 新規失敗 |", "|---|---|---:|---:|---:|"]
    for f in sorted((OUT / "probes").glob("adapt_*.json")):
        d = json.loads(f.read_text(encoding="utf-8"))
        P2.append(f"| {d['name']} | {d['all_hunks_under_tests']} | {len(d.get('passes', []))} | {len(d.get('still_fails', []))} | {len(d.get('newly_failing_confirmed', []))} |")
    P3 = ["| 比較 | 通るようになった基線の失敗 | 新規失敗（単独で確認） |", "|---|---:|---:|"]
    for f in sorted(x for x in (OUT / "probes").glob("combo_*.json") if not x.name.endswith(".spec.json")):
        d = json.loads(f.read_text(encoding="utf-8"))
        P3.append(f"| {d['name']} | {len(d.get('newly_passing', []))} | {len(d.get('newly_failing_confirmed', []))} |")
    B["probes"] = "\n".join(P) + "\n\n" + "\n".join(P2) + "\n\n" + "\n".join(P3)
    # qf2
    ids = [l for l in (OUT / "qf2" / "ids.txt").read_text(encoding="utf-8").split("\n") if l]
    fixed = [l for l in (OUT / "qf2" / "fixed_ids.txt").read_text(encoding="utf-8").split("\n") if l]
    own = json.loads((OUT / "qf2" / "own_commit.json").read_text(encoding="utf-8"))
    off = json.loads((OUT / "qf2" / "constructions_off.json").read_text(encoding="utf-8"))
    abl = json.loads((OUT / "qf2" / "ablation.json").read_text(encoding="utf-8"))
    rp = jload(OUT / "qf2" / "repro.jsonl")
    er = {r["nodeid"]: r for r in jload(OUT / "qf2" / "own_commit_errors.jsonl")}
    suite_line = (OUT / "qf2" / "suite_line.txt").read_text(encoding="utf-8").strip()
    Q = [f"- dev（`075d486`）に `9c89f1e` の `semantic_wh.py`・`tools/demo_question_forms.py` を重ねた複写の全体実行: {suite_line}",
         f"- 基線に無い新規失敗: **{len(ids)} 件**（`qf2/ids.txt`）、基線の失敗のうち通るようになるもの: **{len(fixed)} 件**（`qf2/fixed_ids.txt`）",
         f"- 親 `{own['parent']}` で通り自身 `{own['self']}` で落ちる: **{own['parent_pass_self_fail']} / {len(ids)} 件**（`qf2/own_commit.json`）",
         f"- 構文規則 {len(off['constructions'])} 個をすべて外し（`VERA_CONSTRUCTIONS_OFF`）ても落ちる: **{off['still_fail_with_all_constructions_off']} / {len(ids)} 件**（`qf2/constructions_off.json`）",
         "- 機能を親に戻した版（`qf2/ablation.json`。V = 役割の語彙、C = clause 形、P = wh＋助詞の組）で通る件数: " +
         "、".join(f"{k}［{'＋'.join({'role_vocabulary': 'V', 'clause_forms': 'C', 'wh_particle_pairs': 'P'}[x] for x in v['restored'])}］ = {v.get('pass_count')}" for k, v in abl.items()),
         "- 失敗の 1 行目（`qf2/own_commit_errors.jsonl`。dev + 9c89f1e の複写で 1 件ずつ実行）から規則（`QF2_HARM_RULES`）で決めた害の段: " +
         "、".join(f"{h} = {sum(1 for r in er.values() if r['harm'] == h)}" for h in "ABCD")]
    mc = Counter((tuple(r["hunks"]), r["cause"]) for r in rp)
    Q += ["", "| 機構（親に戻すと通る因子の組） | 主な原因の箇所（9c89f1e:verantyx/semantic_wh.py:行） | 件数 |", "|---|---|---:|"]
    for (m, c), n in sorted(mc.items(), key=lambda kv: (-kv[1], kv[0][1])):
        Q.append(f"| {'＋'.join(m)} | {c.split(':', 2)[2] if c.count(':') >= 2 else c} | {n} |")
    fl = Counter((t["factor"], t["line"].split(":")[-1]) for r in rp for t in {(x["factor"], x["line"]): x for x in r["cause_trace"]}.values())
    Q += ["", "実行で確かめた原因の行（`qf2/repro.jsonl` の `cause_trace`。clause_forms = 親に無い呼び出しの行、wh_particle_pairs／role_vocabulary = `_requested_role` の実行行（`sys.settrace` で記録）または `_ROLE_NOUN` の差）:", "",
          "| 因子 | 行 | そこに当たったテスト数 |", "|---|---:|---:|"]
    for (f, ln), n in sorted(fl.items(), key=lambda kv: (kv[0][0], int(kv[0][1]))):
        Q.append(f"| {f} | {ln} | {n} |")
    unid = [r["nodeid"] for r in rp if r["cause_unidentified"]]
    Q += ["", f"原因の行が未特定のテスト: {len(unid)} 件" + ("（`qf2/repro.jsonl` の `cause_unidentified` に理由）" if unid else ""), ""]
    def _out(o):
        if not o: return ""
        f = o.get("function")
        if f == "Vera.ask": return f"ask: {o['verdict']} {o['values']}"
        if f and f.startswith("Checker."): return f"{f}: {o['outcome']} {o['detail'][:50]}"
        if f == "read_request": return f"read_request: {o['plans']}"
        return f"{o.get('returned')} {o.get('roles')}"
    Q += ["| テスト（nodeid） | 機構 | 原因の箇所（実行した行） | 問い | 文書 | dev の出力 | dev+qf2 の出力 | 失敗の 1 行目（dev+qf2）| 害 |", "|---|---|---|---|---|---|---|---|---|"]
    for r in rp:
        lines = "、".join(sorted({t["line"].split(":")[-1] for t in r["cause_trace"]}, key=int)) if r["cause_trace"] else "未特定"
        Q.append(f"| `{_cell(_short(r['nodeid'], 80))}` | {'＋'.join(r['hunks'])} | {lines} | {_cell(r['question'].strip()[:30])} | {_cell(r['document'][:30])} | {_cell(_out(r['dev'])[:90])} | {_cell(_out(r['qf2'])[:90])} | {_cell(er[r['nodeid']]['self_first_error'][:80])} | {er[r['nodeid']]['harm']} |")
    B["qf2"] = "\n".join(Q)
    B["demo"] = "```\n" + (OUT / "qf2" / "demo_bisect.txt").read_text(encoding="utf-8").strip() + "\n```\n\n```\n" + (OUT / "qf2" / "demo_leave_one_out.txt").read_text(encoding="utf-8").strip() + "\n```"
    # tickets
    Tk = ["| 順位 | 害 | テスト数 | 下書き | 束／決定 | 触るファイル |", "|---:|---|---:|---|---|---|"]
    for t in tickets:
        Tk.append(f"| {t['rank']} | {t['harm']} | {t['test_count']} | {_cell(t['title'])} | {_cell(', '.join(t['bundles']) or '—')} | {_cell(', '.join(t['files_to_touch']))} |")
    B["tickets"] = "\n".join(Tk)
    D = []
    for t in tickets:
        D += [f"#### 順位 {t['rank']}（害 {t['harm']}・{t['test_count']} 件）{t['title']}", f"- 目的: {t['purpose']}", f"- 触るファイル: {', '.join(t['files_to_touch'])}", f"- 受入基準の案（測り方）: {t['acceptance']}", ""]
    B["ticket_details"] = "\n".join(D).rstrip()
    return B


def _replace_blocks(doc: str, B: dict) -> str:
    for name, text in B.items():
        pat = re.compile(r"<!-- w1f:begin:" + re.escape(name) + r" -->\n.*?<!-- w1f:end:" + re.escape(name) + r" -->", re.S)
        if not pat.search(doc):
            raise RuntimeError("doc block missing: " + name)
        doc = pat.sub(lambda m: f"<!-- w1f:begin:{name} -->\n{text}\n<!-- w1f:end:{name} -->", doc)
    return doc


def cmd_report(a) -> int:
    A = build_all()
    jdump(OUT / "triage.jsonl", A["triage"])
    jdump(OUT / "bundles.jsonl", A["bundles"])
    jdump(OUT / "tickets.jsonl", A["tickets"])
    bad = validate(A)
    if bad:
        print("\n".join(bad[:60])); print("VALIDATION NG", len(bad)); return 1
    if DOC.exists():
        DOC.write_text(_replace_blocks(DOC.read_text(encoding="utf-8"), render_blocks(A)), encoding="utf-8")
    from collections import Counter
    print(dict(Counter(t["category"] for t in A["triage"])), "tickets", len(A["tickets"]), "VALIDATION OK")
    return 0


def cmd_check(a) -> int:
    A = build_all()
    bad = validate(A)
    B = render_blocks(A)
    doc = DOC.read_text(encoding="utf-8")
    for name, text in B.items():
        m = re.search(r"<!-- w1f:begin:" + re.escape(name) + r" -->\n(.*?)\n<!-- w1f:end:" + re.escape(name) + r" -->", doc, re.S)
        if not m or m.group(1) != text:
            bad.append("doc block differs: " + name)
    for fn, rows in (("triage.jsonl", A["triage"]), ("bundles.jsonl", A["bundles"]), ("tickets.jsonl", A["tickets"])):
        want = "".join(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n" for r in rows)
        if (OUT / fn).read_text(encoding="utf-8") != want:
            bad.append("jsonl differs: " + fn)
    print("\n".join(bad[:40])); print("CHECK OK" if not bad else f"CHECK NG {len(bad)}")
    return 0 if not bad else 1


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("baseline"); s.add_argument("--phase", choices=["before", "after"], default="before")
    s = sub.add_parser("isolate"); s.add_argument("--jobs", type=int, default=6)
    s = sub.add_parser("history"); s.add_argument("--jobs", type=int, default=5)
    s = sub.add_parser("probe"); s.add_argument("rest", nargs="*"); s.add_argument("--jobs", type=int, default=4)
    for name in ["collect", "index", "fixcheck", "qf2", "report", "check"]:
        s = sub.add_parser(name)
        s.add_argument("rest", nargs="*")
    a = ap.parse_args(argv)
    fn = globals().get("cmd_" + a.cmd)
    if fn is None:
        print("not implemented", a.cmd); return 2
    return fn(a)


if __name__ == "__main__":
    sys.exit(main())
