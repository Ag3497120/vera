"""W8-shadow 影運用の道具の共通部分。

影運用の間、Vera の出力で判断を 1 つも変えない。この道具群の記録・集計は
どの判断の入力にもしない（verantyx/ とほかの道具はこの記録を読まない）。
標準ライブラリだけを使う。ログは追記のみ（既存の行を読まず・書き換えず・削除しない）。
"""
from __future__ import annotations

import fcntl
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HIDDEN = Path("/Users/motonisihikoudai/Projects/vera-impl/hidden")
DEFAULT_PLACEMENT = "/Users/motonisihikoudai/Projects/vera-impl/build/coarse-W3a/full/r8/run2"


class ToolError(Exception):
    """道具が何も書かずに止まる失敗。code は型付きの文字列。"""

    def __init__(self, code, detail=""):
        super().__init__(f"{code}: {detail}" if detail else code)
        self.code = code
        self.detail = detail


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def sha256_file(p) -> str:
    return sha256_bytes(Path(p).read_bytes())


def sha256_text(s: str) -> str:
    return sha256_bytes(s.encode("utf-8"))


def now_ts() -> str:
    import datetime

    return datetime.datetime.now(datetime.timezone.utc).astimezone().isoformat(timespec="seconds")


def refuse_hidden(path):
    """実パスが隠しバンクの下なら REFUSED_HIDDEN_PATH。"""
    real = Path(os.path.realpath(str(path)))
    hid = Path(os.path.realpath(str(HIDDEN)))
    if real == hid or hid in real.parents:
        raise ToolError("REFUSED_HIDDEN_PATH", str(path))


def run_vera(args, *, placement):
    """verantyx.cli を子プロセスで呼ぶ。ソブリンの環境変数は消し、--confirm は渡さない。"""
    if "--confirm" in args:
        raise ToolError("CONFIRM_FORBIDDEN", "shadow tools never pass --confirm")
    env = dict(os.environ)
    env.pop("VERA_SOVEREIGN_ROOT", None)
    env.pop("VERA_SOVEREIGN_STORE", None)
    env["PYTHONPATH"] = str(ROOT)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    if placement is None:
        env.pop("VERA_PLACEMENT", None)
    else:
        env["VERA_PLACEMENT"] = str(placement)
    p = subprocess.run(
        [sys.executable, "-m", "verantyx.cli", *args],
        cwd=str(ROOT), env=env, capture_output=True, text=True,
    )
    return p.returncode, p.stdout, p.stderr


def placement_info(path):
    """配置の manifest.json の content_sha256。読めなければ ToolError(PLACEMENT_UNAVAILABLE)。"""
    mp = Path(path) / "manifest.json"
    try:
        m = json.loads(mp.read_text(encoding="utf-8"))
        return {"path": str(path), "content_sha256": m["content_sha256"]}
    except Exception as e:  # 型付きで止まる。黙って配置なしで流さない
        raise ToolError("PLACEMENT_UNAVAILABLE", f"{path}: {type(e).__name__}")


def append_jsonl(path, obj):
    """1 行を flock の中で 1 回の write で追記する。既存の行は読まない。"""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(obj, ensure_ascii=False, sort_keys=True) + "\n"
    with open(p, "a", encoding="utf-8") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        try:
            f.write(line)
            f.flush()
            os.fsync(f.fileno())
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)


def entry_id(obj) -> str:
    s = json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return sha256_text(s)[:16]


def content_write(directory, text, suffix):
    """内容アドレスで書く。既にあれば同じ中身か確かめ、違えば CONTENT_ADDRESS_COLLISION。"""
    d = Path(directory)
    d.mkdir(parents=True, exist_ok=True)
    h = sha256_text(text)
    p = d / f"{h[:16]}{suffix}"
    if p.exists():
        if p.read_text(encoding="utf-8") != text:
            raise ToolError("CONTENT_ADDRESS_COLLISION", str(p))
    else:
        tmp = d / f".{h[:16]}{suffix}.{os.getpid()}.tmp"
        tmp.write_text(text, encoding="utf-8")
        os.replace(tmp, p)  # 原子的に置く（途中までの読みが衝突と判定されない）
    return {"path": str(p), "sha256": h}


def rec_path(w):
    """content_write の結果を記録用にする（ROOT の下なら相対パス。統合後も辿れる）。"""
    return {"path": rel(w["path"]), "sha256": w["sha256"]}


def tree_info():
    """git_head と verantyx/ が clean か。取れなければ None（推さない）。"""
    def git(*a):
        r = subprocess.run(["git", "-C", str(ROOT), *a], capture_output=True, text=True)
        return r.returncode, r.stdout
    try:
        rc1, head = git("rev-parse", "HEAD")
        rc2, st = git("status", "--porcelain", "--", "verantyx")
    except Exception:
        return {"git_head": None, "verantyx_clean": None}
    return {
        "git_head": head.strip() if rc1 == 0 else None,
        "verantyx_clean": (st.strip() == "") if rc2 == 0 else None,
    }


def rel(p):
    """ROOT 配下なら相対パス、それ以外は実パスで記録する。"""
    rp = Path(os.path.realpath(str(p)))
    try:
        return str(rp.relative_to(Path(os.path.realpath(str(ROOT)))))
    except ValueError:
        return str(rp)


def fail(e: ToolError, rc=2):
    print(json.dumps({"verdict": "ERROR", "code": e.code, "detail": e.detail}, ensure_ascii=False))
    return rc
