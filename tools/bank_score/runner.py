"""サブプロセス起動・ブートストラップ・出自検査・タイムアウト。

1 問 = 1 プロセス。`python -m verantyx.cli` と同じ経路（runpy で verantyx.cli を __main__ として実行）。
子プロセスの環境は継承せず作り直す。終わったら読み込まれた verantyx* がすべて --tree 配下かを検査する。
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

_SCRIPT = r'''
import importlib.util, json, os, runpy, sys, traceback
TREE = @@TREE@@
MODE = sys.argv[1]
ARGS = sys.argv[2:]

def _locations(m):
    f = getattr(m, "__file__", None)
    if f:
        return [f]
    spec = getattr(m, "__spec__", None)
    o = getattr(spec, "origin", None) if spec is not None else None
    if o and o not in ("namespace", "built-in", "frozen"):
        return [o]
    p = getattr(m, "__path__", None)
    if p is not None:
        try:
            return list(p)
        except Exception:
            return []
    return []

def _inside(path, tree):
    r = os.path.realpath(path)
    return r == tree or r.startswith(tree + os.sep)

def provenance(extra):
    tree = os.path.realpath(TREE)
    mods, outside = [], []
    for name in sorted(list(sys.modules)):
        if not name.split(".")[0].startswith("verantyx"):
            continue
        m = sys.modules.get(name)
        if m is None:
            continue
        locs = _locations(m)
        mods.append(name)
        if not locs or not all(_inside(p, tree) for p in locs):
            outside.append({"module": name, "locations": [os.path.realpath(p) for p in locs] or ["<unknown>"]})
    try:
        spec = importlib.util.find_spec("verantyx.cli")
        origin = getattr(spec, "origin", None)
        if origin is None or not _inside(origin, tree):
            outside.append({"module": "verantyx.cli(find_spec)", "locations": [origin or "<unknown>"]})
    except Exception as e:
        outside.append({"module": "verantyx.cli(find_spec)", "locations": ["<error:%s>" % type(e).__name__]})
    d = {"modules": len(mods), "outside": outside}
    d.update(extra)
    return d

code = 0
extra = {}
if MODE == "precheck":
    try:
        import verantyx
        import verantyx.cli
    except BaseException as e:
        extra["import_error"] = "%s: %s" % (type(e).__name__, e)
else:
    sys.argv = ["verantyx.cli", "--store", "store.json"] + ARGS
    try:
        runpy.run_module("verantyx.cli", run_name="__main__", alter_sys=True)
    except SystemExit as e:
        c = e.code
        code = 0 if c is None else (c if isinstance(c, int) else 1)
        if not isinstance(c, (int, type(None))):
            sys.stderr.write(str(c) + "\n")
    except BaseException:
        traceback.print_exc()
        code = 1
try:
    sys.stdout.flush()
except Exception:
    pass
with open(os.environ["BANK_SCORE_PROVENANCE"], "w", encoding="utf-8") as f:
    json.dump(provenance(extra), f, ensure_ascii=False)
sys.exit(code)
'''


class Session:
    """一時作業場所と、出自検査の通算を持つ。"""

    def __init__(self, python: str, tree: str, corpus_root: str | None, timeout: float):
        self.python = python
        self.tree = os.path.realpath(tree)
        self.timeout = timeout
        self.work = Path(tempfile.mkdtemp(prefix="bank_score_"))
        self.work_real = str(self.work.resolve())
        (self.work / "home").mkdir()
        (self.work / "prov").mkdir()
        self.corpus_root = corpus_root or str(self.work / "empty_corpus")
        if corpus_root is None:
            (self.work / "empty_corpus").mkdir()
        self.script = _SCRIPT.replace("@@TREE@@", repr(self.tree))
        self.processes_checked = 0
        self.processes_unverified = 0
        self.outside: list[dict] = []
        self.redactions = 0
        self.n = 0

    def env(self, prov: Path) -> dict[str, str]:
        return {
            "PATH": os.environ.get("PATH", ""),
            "PYTHONPATH": self.tree,
            "PYTHONDONTWRITEBYTECODE": "1",
            "HOME": str(self.work / "home"),
            "VERA_CORPUS_ROOT": self.corpus_root,
            "BANK_SCORE_PROVENANCE": str(prov),
            "LANG": "C.UTF-8",
            "PYTHONIOENCODING": "utf-8",
        }

    def redact(self, s: str, count: bool = True) -> str:
        """一時パスを <WORK> に置き換える。count=True のときだけ置換件数（生出力・標準エラー用）に数える。"""
        out = s
        for p in sorted({str(self.work), self.work_real}, key=len, reverse=True):
            if p in out:
                if count:
                    self.redactions += out.count(p)
                out = out.replace(p, "<WORK>")
        return out

    def env_for_meta(self) -> dict[str, str]:
        e = self.env(self.work / "prov" / "N.json")
        return {k: self.redact(v, count=False) for k, v in sorted(e.items())}

    def _spawn(self, mode: str, args: list[str], cwd: Path) -> dict:
        self.n += 1
        prov = self.work / "prov" / f"{self.n:05d}.json"
        argv = [self.python, "-c", self.script, mode, *args]
        t0 = time.monotonic()
        status, exit_code, out, err = "ok", None, "", ""
        try:
            cp = subprocess.run(argv, cwd=str(cwd), env=self.env(prov), capture_output=True, timeout=self.timeout)
            exit_code = cp.returncode
            out = cp.stdout.decode("utf-8", "replace")
            err = cp.stderr.decode("utf-8", "replace")
        except subprocess.TimeoutExpired as e:
            status = "TIMEOUT"
            out = (e.stdout or b"").decode("utf-8", "replace") if isinstance(e.stdout, bytes) else ""
            err = (e.stderr or b"").decode("utf-8", "replace") if isinstance(e.stderr, bytes) else ""
        elapsed = round((time.monotonic() - t0) * 1000, 1)
        provenance = None
        if prov.is_file():
            try:
                provenance = json.loads(prov.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                provenance = None
        self.processes_checked += 1
        if provenance is None:
            self.processes_unverified += 1  # 出自を記録できなかった（タイムアウト・異常終了）。数えて報告する
        else:
            for o in provenance.get("outside", []):
                self.outside.append(o)
        return {"status": status, "exit_code": exit_code, "stdout": out, "stderr": err, "provenance": provenance,
                "elapsed_ms": elapsed}

    def precheck(self) -> dict:
        cwd = self.work / "precheck"
        cwd.mkdir(exist_ok=True)
        r = self._spawn("precheck", [], cwd)
        prov = r["provenance"]
        return {"exit_code": r["exit_code"], "status": r["status"],
                "modules": None if prov is None else prov.get("modules"),
                "outside": None if prov is None else prov.get("outside"),
                "import_error": None if prov is None else prov.get("import_error"),
                "stderr_tail": self.redact(r["stderr"][-400:]), "elapsed_ms": r["elapsed_ms"]}

    def run_ask(self, seq: int, argv: list[str], files: list[dict]) -> dict:
        """ask を 1 回走らせる。cwd は問題ごとの一時ディレクトリ（文書ファイルを置く）。"""
        qdir = self.work / f"q{seq:04d}"
        qdir.mkdir()
        for f in files:
            (qdir / f["filename"]).write_text(f["text"], encoding="utf-8")
        r = self._spawn("run", argv, qdir)
        shutil.rmtree(qdir, ignore_errors=True)
        stdout_json = None
        reason = None
        if r["status"] == "TIMEOUT":
            reason = "TIMEOUT"
        elif r["exit_code"] != 0:
            reason = "NONZERO_EXIT"
        else:
            try:
                stdout_json = json.loads(r["stdout"])
            except json.JSONDecodeError:
                stdout_json = None
            if not isinstance(stdout_json, dict):
                stdout_json = None
                reason = "NOT_JSON"
        if reason in ("NONZERO_EXIT", "TIMEOUT"):
            try:
                j = json.loads(r["stdout"])
                stdout_json = j if isinstance(j, dict) else None
            except json.JSONDecodeError:
                pass
        return {"reason": reason, "exit_code": r["exit_code"], "stdout_json": stdout_json,
                "stdout_text": None if stdout_json is not None else self.redact(r["stdout"][:4000]),
                "stderr": self.redact(r["stderr"][-2000:]), "provenance": r["provenance"],
                "elapsed_ms": r["elapsed_ms"]}

    def close(self) -> None:
        shutil.rmtree(self.work, ignore_errors=True)
