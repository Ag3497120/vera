"""サブプロセス起動・ブートストラップ・出自検査・タイムアウト。

1 問 = 1 プロセス。`python -m verantyx.cli` と同じ経路（runpy で verantyx.cli を __main__ として実行）。
子プロセスの環境は継承せず作り直す。終わったら読み込まれた verantyx* がすべて --tree 配下かを検査する。
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import sqlite3
import subprocess
import tempfile
import time
from pathlib import Path

# 子プロセスが走らせてよいモジュール（閉じた集合。ここに無い名前は走らせない）。
ALLOWED_MODULES = ("verantyx.cli", "verantyx.semantic_read")
# B7（W6-s）だけが子の環境に足してよい鍵（閉じた集合。これ以外の鍵を足そうとすると ValueError）。
B7_EXTRA_ENV_KEYS = ("VERA_P4_INDEX",)

_SCRIPT = r'''
import importlib.util, json, os, runpy, sys, traceback
TREE = @@TREE@@
ALLOWED = @@ALLOWED@@
MODE = sys.argv[1]
if MODE == "run_module":                 # run_module <module> <args...> : verantyx.cli 以外の入口（--store は付けない）
    MODULE = sys.argv[2]
    ARGS = sys.argv[3:]
elif MODE == "precheck":                 # precheck [<module>]
    MODULE = sys.argv[2] if len(sys.argv) > 2 else "verantyx.cli"
    ARGS = []
else:
    MODULE = "verantyx.cli"
    ARGS = sys.argv[2:]
if MODULE not in ALLOWED:
    sys.stderr.write("module not allowed: %r\n" % (MODULE,))
    sys.exit(97)

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
    for target in sorted({"verantyx.cli", MODULE}):          # 選んだモジュールにも出自の検査を掛ける
        try:
            spec = importlib.util.find_spec(target)
            origin = getattr(spec, "origin", None)
            if origin is None or not _inside(origin, tree):
                outside.append({"module": target + "(find_spec)", "locations": [origin or "<unknown>"]})
        except Exception as e:
            outside.append({"module": target + "(find_spec)", "locations": ["<error:%s>" % type(e).__name__]})
    d = {"modules": len(mods), "outside": outside}
    d.update(extra)
    return d

code = 0
extra = {}
if MODE == "precheck":
    try:
        import verantyx
        import verantyx.cli
        if MODULE != "verantyx.cli":
            importlib.import_module(MODULE)
    except BaseException as e:
        extra["import_error"] = "%s: %s" % (type(e).__name__, e)
else:
    sys.argv = ["verantyx.cli", "--store", "store.json"] + ARGS if MODULE == "verantyx.cli" else [MODULE] + ARGS
    try:
        runpy.run_module(MODULE, run_name="__main__", alter_sys=True)
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
        self.script = _SCRIPT.replace("@@TREE@@", repr(self.tree)).replace("@@ALLOWED@@", repr(ALLOWED_MODULES))
        self.processes_checked = 0
        self.processes_unverified = 0
        self.outside: list[dict] = []
        self.redactions = 0
        self.n = 0

    def env(self, prov: Path, extra: dict[str, str] | None = None) -> dict[str, str]:
        e = {
            "PATH": os.environ.get("PATH", ""),
            "PYTHONPATH": self.tree,
            "PYTHONDONTWRITEBYTECODE": "1",
            "HOME": str(self.work / "home"),
            "VERA_CORPUS_ROOT": self.corpus_root,
            "BANK_SCORE_PROVENANCE": str(prov),
            "LANG": "C.UTF-8",
            "PYTHONIOENCODING": "utf-8",
        }
        if os.environ.get("VERA_PLACEMENT"):      # W3-b1 (auditor): a placement is passed only when the parent names one; recorded in run_meta
            e["VERA_PLACEMENT"] = os.environ["VERA_PLACEMENT"]
        if extra:  # B7: VERA_P4_INDEX だけ（既定 None は今までと同じ 8 鍵）
            bad = sorted(k for k in extra if k not in B7_EXTRA_ENV_KEYS)
            if bad:
                raise ValueError(f"子の環境に足してよい鍵は {list(B7_EXTRA_ENV_KEYS)} だけ（指定: {bad}）")
            e.update(extra)
        return e

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

    def _spawn(self, mode: str, args: list[str], cwd: Path, extra_env: dict[str, str] | None = None) -> dict:
        self.n += 1
        prov = self.work / "prov" / f"{self.n:05d}.json"
        argv = [self.python, "-c", self.script, mode, *args]
        t0 = time.monotonic()
        status, exit_code, out, err = "ok", None, "", ""
        try:
            cp = subprocess.run(argv, cwd=str(cwd), env=self.env(prov, extra_env), capture_output=True, timeout=self.timeout)
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

    def precheck(self, module: str = "verantyx.cli") -> dict:
        if module not in ALLOWED_MODULES:
            raise ValueError(f"許可していないモジュール: {module!r}（許可: {list(ALLOWED_MODULES)}）")
        cwd = self.work / "precheck"
        cwd.mkdir(exist_ok=True)
        r = self._spawn("precheck", [module] if module != "verantyx.cli" else [], cwd)
        prov = r["provenance"]
        return {"exit_code": r["exit_code"], "status": r["status"],
                "modules": None if prov is None else prov.get("modules"),
                "outside": None if prov is None else prov.get("outside"),
                "import_error": None if prov is None else prov.get("import_error"),
                "stderr_tail": self.redact(r["stderr"][-400:]), "elapsed_ms": r["elapsed_ms"]}

    def prepare_b7(self, seq: int, human_sources: list[str], generated_snippets: list[str]) -> dict:
        """B7（W6-s）の 1 問ぶんの子の入力を作る。文書と索引のパスは通し番号（問題の id・unit・lang を含めない: J3）。

        - 文書: human_sources が 1 本以上なら <WORK>/docs/qNNNN.txt（1 行 1 文）。0 本なら作らない（document = None）。
        - 索引: <WORK>/p4/qNNNN/ を作る。生成の文が 1 本以上なら tools.build_p4_corpus_index.build で local.db（origin = "generated"）を
          作る。0 本なら空のディレクトリ（J4: 状態は UNKNOWN_NO_INDEX）。入力の jsonl は索引ディレクトリの外 <WORK>/p4src/ に置く（J5）。
        失敗は例外にせず {"error": "B7_PREPARE_FAILED", "detail": 型名} で返す（cli がその問を runtime_error にする）。
        """
        try:
            index_dir = self.work / "p4" / f"q{seq:04d}"
            index_dir.mkdir(parents=True)
            document, doc_sha = None, None
            if human_sources:
                (self.work / "docs").mkdir(exist_ok=True)
                data = ("\n".join(human_sources) + "\n").encode("utf-8")
                path = self.work / "docs" / f"q{seq:04d}.txt"
                path.write_bytes(data)
                document, doc_sha = str(path), hashlib.sha256(data).hexdigest()
            rows = 0
            if generated_snippets:
                from .. import build_p4_corpus_index as bpi
                (self.work / "p4src").mkdir(exist_ok=True)
                src = self.work / "p4src" / f"q{seq:04d}.jsonl"
                src.write_text("".join(json.dumps({"text": t, "source": "bank_score_b7:generated_snippet"},
                                                  ensure_ascii=False) + "\n" for t in generated_snippets),
                               encoding="utf-8")
                rows = bpi.build(src, index_dir / "local.db", "local")
                if rows != len(generated_snippets):  # 形式の漂流で黙って索引に入らない文を作らない
                    return {"error": "B7_PREPARE_FAILED", "detail": "INDEX_ROWS_MISMATCH"}
            return {"document": document, "document_sha256": doc_sha, "p4_index": str(index_dir), "p4_rows": rows}
        except (OSError, sqlite3.Error) as e:
            return {"error": "B7_PREPARE_FAILED", "detail": type(e).__name__}

    def run_ask(self, seq: int, argv: list[str], files: list[dict], module: str = "verantyx.cli",
                extra_env: dict[str, str] | None = None) -> dict:
        """入口を 1 回走らせる（既定は verantyx.cli の ask）。cwd は問題ごとの一時ディレクトリ（文書ファイルを置く）。
        module は閉じた許可集合（ALLOWED_MODULES）だけ。集合に無ければ例外（何も走らせない）。"""
        if module not in ALLOWED_MODULES:
            raise ValueError(f"許可していないモジュール: {module!r}（許可: {list(ALLOWED_MODULES)}）")
        qdir = self.work / f"q{seq:04d}"
        qdir.mkdir()
        for f in files:
            (qdir / f["filename"]).write_text(f["text"], encoding="utf-8")
        r = (self._spawn("run", argv, qdir, extra_env) if module == "verantyx.cli"
             else self._spawn("run_module", [module, *argv], qdir, extra_env))
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
