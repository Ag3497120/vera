"""W16-t7 K700: 追記専用・ハッシュ連鎖の台帳（`<dir>/events.jsonl` と `<dir>/HEAD`）。

行はちょうど 6 キー {ts, kind, actor, data, prev, sha}。sha = sha256(正準JSON({ts,kind,actor,data,prev}))。
検証の型は閉じた一覧（docs/RECORDER.md）。分からないことと偽であることを混ぜない。
すべてローカル。ネットワークを使わない。
"""
from __future__ import annotations

import base64
import binascii
import fcntl
import hashlib
import json
import os
import re
import unicodedata
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

GENESIS = "0" * 64
KINDS = (
    "owner_utterance", "agent_stop", "tool_call", "process_start", "process_exit",
    "process_interrupted", "process_orphaned", "approval", "commit", "test_run",
)
ACTOR_TYPES = ("owner", "agent", "process")
ROW_KEYS = {"ts", "kind", "actor", "data", "prev", "sha"}
DEFAULT_DIR = ".vera/ledger"

# ---- 秘匿 ------------------------------------------------------------------
# (名前, 正規表現, 伏せる群)。上から順に当てる（sk-ant を sk より先に）。
_B = ""  # 第 4 ラウンドで左境界を外した（監査役の裁定）。鍵は接頭辞・長さ・文字種だけで判定する。過剰な伏せは許し、漏れは許さない
REDACT_PATTERNS = (
    ("private_key", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?(?:-----END [A-Z ]*PRIVATE KEY-----|\Z)"), 0),
    ("sk_ant", re.compile(_B + r"sk-ant-[A-Za-z0-9_\-]{8,}"), 0),
    ("github_pat", re.compile(_B + r"github_pat_[A-Za-z0-9_]{20,}"), 0),
    ("gh_token", re.compile(_B + r"gh[pousr]_[A-Za-z0-9]{20,}"), 0),
    ("aws_akia", re.compile(_B + r"AKIA[0-9A-Z]{16}"), 0),
    ("google_api_key", re.compile(_B + r"AIza[0-9A-Za-z_\-]{35}"), 0),
    ("slack_token", re.compile(_B + r"xox[abprs]-[A-Za-z0-9\-]{10,}"), 0),
    ("sk", re.compile(_B + r"sk-[A-Za-z0-9_\-]{12,}"), 0),
    ("bearer", re.compile(r"(?i:Bearer)\s+((?!\[REDACTED)[A-Za-z0-9._~+/\-]{20,}=*)"), 1),
    ("kv_secret", re.compile(r"(?i:(?:api[_-]?key|token|secret|password))[\"']?\s*[=:]\s*[\"']?((?!\[REDACTED)[^\s\"']{8,})"), 1),
)


_REDACT_MAX_PASSES = 8
_REDACT_RESIDUE = re.compile(r"(\[REDACTED:[a-z_]+\])[A-Za-z0-9_\-]{8,}")

_SECRET_KEY = re.compile(r"(?i)(?:.*[_-])?(?:api[_-]?key|token|secret|password)")


class LedgerError(Exception):
    """型つきの失敗。`code` が型（str(e) の先頭にも入る）。"""

    def __init__(self, code: str, detail: str = ""):
        super().__init__(f"{code}: {detail}" if detail else code)
        self.code = code
        self.detail = detail


def _spans(text):
    """全部の型を元の文字列に独立に当て、重なりを許して一致の区間を集め、重なる区間を併せる。
    前の鍵の本体が後ろの鍵の目印（Bearer・password など）を飲み込んでも、後ろの鍵を見落とさないため。"""
    out = []
    for idx, (name, rx, grp) in enumerate(REDACT_PATTERNS):
        pos = 0
        while pos <= len(text):
            m = rx.search(text, pos)
            if not m:
                break
            s, e = m.span(grp)
            if e > s:
                out.append((s, -e, idx, name))
            pos = m.start() + 1          # 重なりを許す（m.end() から探すと飲み込まれた鍵を見落とす）
    out.sort()                           # 開始位置 → 長い区間 → 一覧で前の型、の順
    merged = []
    for s, ne, _i, name in out:
        e = -ne
        if merged and s < merged[-1][1]:     # 重なり（接するだけは別の区間。隣り合う鍵を 2 件と数える）
            if e > merged[-1][1]:
                merged[-1][1] = e
        else:
            merged.append([s, e, name])
    return merged

# ---- 変形した鍵（W16-t7c K720）。変形は nfkc・pct・b64 の 3 つだけ。名前は短く固定する（長い名前は kv_secret の規則に再び当たり冪等でなくなる）。
_TOKEN_RX = re.compile(r"[^\s\"']+")
_B64_RUN = re.compile(r"[A-Za-z0-9+/_\-]{16,}={0,2}")


def _v_nfkc(w):
    v = unicodedata.normalize("NFKC", w)
    return [v] if v != w else []


def _v_pct(w):
    out = []
    for fn in (urllib.parse.unquote, urllib.parse.unquote_plus):
        cur = w
        for _ in range(4):
            nxt = fn(cur)
            if nxt == cur:
                break
            cur = nxt
            if cur != w and cur not in out:
                out.append(cur)
    return out


def _b64_decode(p):
    """base64 らしい列の復号。UTF-8 strict で読めればそれを、読めなければ置換文字で読んだもの（前後の余分な字の分を許す。過剰に伏せる側）。"""
    p = p.rstrip("=")
    if len(p) < 16 or (("+" in p or "/" in p) and ("-" in p or "_" in p)):
        return None
    p = p.replace("-", "+").replace("_", "/")
    if len(p) % 4 == 1:
        p = p[:-1]                       # 後ろに余分な 1 字（第 3 ラウンド）
    try:
        b = base64.b64decode(p + "=" * (-len(p) % 4), validate=True)
    except (binascii.Error, ValueError):
        return None
    try:
        return b.decode("utf-8")
    except UnicodeDecodeError:
        return b.decode("utf-8", "replace")   # 前後に接した英数字が作る壊れたバイト（第 3 ラウンド）


def _v_b64(w):
    out = []
    cands = [w]
    for r in _B64_RUN.findall(w):
        # 始点の候補: 連続部分の先頭、区切り字（`/ _ - +`）の直後（先頭側 16 個と末尾側 16 個）、
        # `-_` の最後の位置の直後と `+/` の最後の位置の直後（2 つの字集合が混ざる連続部分の後ろ側）。
        seps = [i for i, c in enumerate(r) if c in "/_-+"]
        starts = {0} | {i + 1 for i in seps[:16] + seps[-16:]}
        for alpha in ("-_", "+/"):
            j = max(r.rfind(c) for c in alpha)
            if j >= 0:
                starts.add(j + 1)
        # 各始点を 0〜3 字ずらす（英数字が区切り無しで前に接した形。base64 の 4 字の区切りに合わせる）。
        for s0 in sorted(starts):
            for k in range(4):
                s = s0 + k
                cands.append(r[s:])
                # 終点の候補（第 4 ラウンド）: 後ろにもう一方の字集合の区切り字（`-_` / `+/`）が接した形は、
                # 混在で捨てられるので、s 以後でその字が最初に出る位置の手前までを切り出す。
                for alpha in ("-_", "+/"):
                    es = [e for e in (r.find(c, s) for c in alpha) if e >= 0]
                    if es and min(es) - s >= 16:
                        cands.append(r[s:min(es)])
    for p in cands:
        d = _b64_decode(p)
        if d is not None and d != w and d not in out:
            out.append(d)
    return out


def _variant_hit(w, fns):
    """窓 w の変形のどれかに鍵の形があれば (型, 変形の名前)。無ければ None。順は表示の名前を決めるだけ。"""
    for name, fn in fns:
        for v in fn(w):
            sp = _spans(v)
            if sp:
                return sp[0][2], name
    return None


_FNS_ALL = (("nfkc", _v_nfkc), ("pct", _v_pct), ("b64", _v_b64))
_FNS_MULTI = (("nfkc", _v_nfkc), ("pct", _v_pct))


def _variant_stage(text):
    """K720: 空白・引用符で分けたトークン（連続する 1〜3 個の窓）の変形に鍵の形があれば、窓を丸ごと印にする。(新しい文字列, 個数)。"""
    toks = [m.span() for m in _TOKEN_RX.finditer(text)]
    n = len(toks)
    mark = [None] * n          # 各トークンが属する群 (先頭の添字, 末尾の添字, 型, 変形名)
    for i, (s, e) in enumerate(toks):
        h = _variant_hit(text[s:e], _FNS_ALL)
        if h:
            mark[i] = (i, i, h[0], h[1])
    for size in (2, 3):
        for i in range(n - size + 1):
            if any(mark[k] is not None for k in range(i, i + size)):
                continue
            h = _variant_hit(text[toks[i][0]:toks[i + size - 1][1]], _FNS_MULTI)
            if h:
                g = (i, i + size - 1, h[0], h[1])
                for k in range(i, i + size):
                    mark[k] = g
    groups = sorted({g for g in mark if g is not None})
    if not groups:
        return text, 0
    parts, pos = [], 0   # 断片を左から集めて最後に 1 回だけ連結する（線形）
    for a, b, typ, name in groups:
        parts.append(text[pos:toks[a][0]])
        parts.append(f"[REDACTED:{typ}:{name}]")
        pos = toks[b][1]
    parts.append(text[pos:])
    return "".join(parts), len(groups)


def redact(text) -> tuple:
    """(伏せた後の文字列, 伏せた個数)。秘密の形の部分だけを `[REDACTED:<名前>]` に置き換える。
    K720: 元の文字列に加え、空白・引用符で分けたトークン（1〜3 個の窓）の NFKC・パーセント復号・base64 復号にも当て、
    変形に鍵の形があれば窓を丸ごと `[REDACTED:<型>:<nfkc|pct|b64>]` にする。"""
    if not isinstance(text, str):
        text = str(text)
    total = 0
    # 不動点まで繰り返す（置き換えの結果、新たに鍵の形が現れる場合に備える）。
    for _ in range(_REDACT_MAX_PASSES):
        sp = _spans(text)
        changed = len(sp)
        for s, e, name in reversed(sp):
            text = text[:s] + f"[REDACTED:{name}]" + text[e:]
        # 残り滓の規則: 伏せた印にすき間なく続く英数字の長い連なりは、前の鍵の本体が後ろの鍵の接頭辞を
        # 飲み込んだ残りかもしれない。安全側に倒して落とす（印は残す）。
        text, n = _REDACT_RESIDUE.subn(lambda m: m.group(1), text)
        changed += n
        text, n = _variant_stage(text)
        changed += n
        total += changed
        if changed == 0:
            return text, total
    # 上限に達しても残る場合は安全側に倒す（全体を伏せる）。
    return "[REDACTED:unbounded]", total + 1


def redact_obj(obj) -> tuple:
    """JSON 値の中の全部の文字列を redact する。(新しい値, 個数)。"""
    n = 0

    def walk(x):
        nonlocal n
        if isinstance(x, str):
            y, k = redact(x)
            n += k
            return y
        if isinstance(x, dict):
            out = {}
            for k, v in x.items():
                if isinstance(k, str) and isinstance(v, str) and _SECRET_KEY.fullmatch(k) and len(v) >= 8 and not v.startswith("[REDACTED"):
                    n += 1
                    out[walk(k)] = "[REDACTED:kv_secret]"
                else:
                    out[walk(k) if isinstance(k, str) else k] = walk(v)
            return out
        if isinstance(x, (list, tuple)):
            return [walk(v) for v in x]
        return x
    return walk(obj), n


def canonical(obj) -> str:
    return json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def args_sha256(obj) -> str:
    return hashlib.sha256(canonical(obj).encode("utf-8")).hexdigest()


def sha_of(row: dict) -> str:
    body = {k: row[k] for k in ("ts", "kind", "actor", "data", "prev")}
    return hashlib.sha256(canonical(body).encode("utf-8")).hexdigest()


def now_ts() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def resolve_dir(ledger_dir=None) -> Path:
    """--ledger-dir > 環境変数 VERA_LEDGER_DIR > ./.vera/ledger"""
    if ledger_dir:
        return Path(ledger_dir)
    env = os.environ.get("VERA_LEDGER_DIR")
    return Path(env) if env else Path(DEFAULT_DIR)


def _last_line(path: Path) -> Optional[bytes]:
    """末尾の（空でない）行のバイト列。無ければ None。末尾から読む。"""
    if not path.exists():
        return None
    size = path.stat().st_size
    if size == 0:
        return None
    with open(path, "rb") as f:
        chunk = 8192
        while True:
            start = max(0, size - chunk)
            f.seek(start)
            buf = f.read(size - start)
            body = buf.rstrip(b"\n")
            idx = body.rfind(b"\n")
            if idx >= 0 or start == 0:
                return body[idx + 1:] if body else None
            chunk *= 4


def _last_byte(path: Path) -> bytes:
    with open(path, "rb") as f:
        f.seek(-1, os.SEEK_END)
        return f.read(1)


def _check_actor(actor) -> dict:
    if not isinstance(actor, dict) or actor.get("type") not in ACTOR_TYPES or not isinstance(actor.get("id"), str):
        raise LedgerError("UNKNOWN_ACTOR_TYPE", f"actor.type は {ACTOR_TYPES}、actor.id は文字列")
    out = {"type": actor["type"], "id": actor["id"]}
    if actor.get("model") is not None:
        out["model"] = str(actor["model"])
    return out


def preflight(ledger_dir, kind: str, actor: dict, data: dict) -> None:
    """追記が通る状態かを、書かずに確かめる。だめなら LedgerError（型つき）。vera run が子を起動する前に呼ぶ。"""
    if kind not in KINDS:
        raise LedgerError("UNKNOWN_KIND", str(kind))
    actor = _check_actor(actor)
    if not isinstance(data, dict):
        raise LedgerError("BAD_DATA", "data は辞書")
    if redact_obj(data)[1] or redact_obj(actor)[1]:
        raise LedgerError("UNREDACTED_SECRET_REFUSED", "data/actor に秘密の形が残っている")
    d = Path(ledger_dir)
    try:
        d.mkdir(parents=True, exist_ok=True)
        if not d.is_dir() or not os.access(d, os.W_OK | os.X_OK):
            raise LedgerError("LEDGER_NOT_WRITABLE", str(d))
        ev = d / "events.jsonl"
        if ev.exists():
            if not os.access(ev, os.W_OK):
                raise LedgerError("LEDGER_NOT_WRITABLE", str(ev))
            if ev.stat().st_size and _last_byte(ev) != b"\n":
                raise LedgerError("TORN_TAIL_BLOCKS_APPEND", "最終行が改行で終わっていない。verify を見て人が直す")
        with open(d / ".lock", "a"):
            pass
    except LedgerError:
        raise
    except OSError as e:
        raise LedgerError("LEDGER_NOT_WRITABLE", f"{type(e).__name__}: {e}")


def append(ledger_dir, kind: str, actor: dict, data: dict) -> dict:
    """flock の中で 1 行を追記し HEAD を更新する。書いた行を返す。"""
    if kind not in KINDS:
        raise LedgerError("UNKNOWN_KIND", str(kind))
    actor = _check_actor(actor)
    if not isinstance(data, dict):
        raise LedgerError("BAD_DATA", "data は辞書")
    # 安全網: 呼び出し側が redact し忘れた秘密は台帳に入れない（黙って伏せず、拒否して型で知らせる）
    # 判定は伏せる処理と同じ表現（文字列ごと）で行う。正準 JSON（エスケープ後）には正規表現をかけない。
    if redact_obj(data)[1] or redact_obj(actor)[1]:
        raise LedgerError("UNREDACTED_SECRET_REFUSED", "data/actor に秘密の形が残っている")
    d = Path(ledger_dir)
    d.mkdir(parents=True, exist_ok=True)
    ev = d / "events.jsonl"
    with open(d / ".lock", "a") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        try:
            if ev.exists() and ev.stat().st_size and _last_byte(ev) != b"\n":
                raise LedgerError("TORN_TAIL_BLOCKS_APPEND", "最終行が改行で終わっていない。verify を見て人が直す")
            last = _last_line(ev)
            prev = GENESIS
            if last is not None:
                try:
                    prev = json.loads(last.decode("utf-8"))["sha"]
                except Exception:
                    raise LedgerError("TORN_TAIL_BLOCKS_APPEND", "最終行を読めない。verify を見て人が直す")
            row = {"ts": now_ts(), "kind": kind, "actor": actor, "data": data, "prev": prev}
            row["sha"] = sha_of(row)
            line = (canonical(row) + "\n").encode("utf-8")
            fd = os.open(ev, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o644)
            try:
                os.write(fd, line)
                os.fsync(fd)
            finally:
                os.close(fd)
            tmp = d / f".HEAD.{os.getpid()}.tmp"
            with open(tmp, "w") as f:
                f.write(row["sha"] + "\n")
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, d / "HEAD")
            return row
        finally:
            fcntl.flock(lock.fileno(), fcntl.LOCK_UN)


def read_events(ledger_dir) -> list:
    """検証しない生の読み出し。読めない行は飛ばす（verify が型で報告する）。"""
    p = Path(ledger_dir) / "events.jsonl"
    if not p.exists():
        return []
    out = []
    for ln in p.read_text(encoding="utf-8", errors="replace").split("\n"):
        if not ln.strip():
            continue
        try:
            o = json.loads(ln)
        except Exception:
            continue
        if isinstance(o, dict):
            out.append(o)
    return out


def reject(ledger_dir, reason: str, **detail) -> None:
    """連鎖の外の rejects.jsonl に 1 行足す。例外を出さない（hook 経路から呼ばれる）。detail は redact 済みにして書く。"""
    try:
        d = Path(ledger_dir)
        d.mkdir(parents=True, exist_ok=True)
        det, n = redact_obj(detail)
        rec = {"ts": now_ts(), "reason": reason, "detail": det, "redactions": n}
        fd = os.open(d / "rejects.jsonl", os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o644)
        try:
            os.write(fd, (canonical(rec) + "\n").encode("utf-8"))
        finally:
            os.close(fd)
    except Exception:
        pass


def _row_shape_ok(r) -> bool:
    if not isinstance(r, dict) or set(r) != ROW_KEYS:
        return False
    if r["kind"] not in KINDS:
        return False
    a = r["actor"]
    if not isinstance(a, dict) or a.get("type") not in ACTOR_TYPES or not isinstance(a.get("id"), str):
        return False
    return isinstance(r["data"], dict) and isinstance(r["prev"], str) and isinstance(r["sha"], str) and isinstance(r["ts"], str)


def verify(ledger_dir, expected_head: Optional[str] = None) -> dict:
    """連鎖と HEAD を検査する。行番号は 1 始まり。型は閉じた一覧（docs/RECORDER.md §2）。"""
    d = Path(ledger_dir)
    ev, hp = d / "events.jsonl", d / "HEAD"
    raw = ev.read_bytes().decode("utf-8", errors="replace") if ev.exists() else ""
    lines = raw.split("\n")
    unterminated = bool(raw) and not raw.endswith("\n")
    if lines and lines[-1] == "":
        lines.pop()
    problems = []
    shas = []                     # 構文として読めた行の保存された sha（行番号つき）
    expected_prev = GENESIS
    last_ok_sha = None
    n_rows = 0
    for i, ln in enumerate(lines, 1):
        is_tail = unterminated and i == len(lines)
        try:
            r = json.loads(ln)
            if not isinstance(r, dict):
                raise ValueError("not an object")
        except Exception:
            problems.append({"line": i, "type": "TORN_TAIL" if is_tail else "LINE_UNPARSABLE"})
            expected_prev = None          # 次の行の prev は比べられない（連鎖の誤検出を増やさない）
            continue
        n_rows += 1
        if not _row_shape_ok(r):
            problems.append({"line": i, "type": "BAD_SHAPE"})
        if all(k in r for k in ROW_KEYS):
            try:
                if sha_of(r) != r["sha"]:
                    problems.append({"line": i, "type": "SHA_MISMATCH"})
            except Exception:
                pass
            if expected_prev is not None and r["prev"] != expected_prev:
                problems.append({"line": i, "type": "PREV_MISMATCH"})
            expected_prev = r["sha"] if isinstance(r["sha"], str) else None
            if isinstance(r["sha"], str):
                shas.append((i, r["sha"]))
                last_ok_sha = r["sha"]
        else:
            expected_prev = None
    head = hp.read_text().strip() if hp.exists() else None
    if head is None:
        if n_rows or lines:
            problems.append({"line": None, "type": "HEAD_MISSING"})
    elif head != last_ok_sha:
        p = {"line": None, "type": "HEAD_MISMATCH"}
        at = [i for i, s in shas if s == head]
        if at:
            p["HEAD_POINTS_TO_LINE"] = at[0]          # その後ろが余分（HEAD が先に止まった）
        else:
            p["HEAD_NOT_IN_CHAIN"] = True              # 切り詰め・差し替えの疑い
        problems.append(p)
    if expected_head is not None and expected_head != last_ok_sha:
        problems.append({"line": None, "type": "EXPECTED_HEAD_MISMATCH", "expected": expected_head, "actual": last_ok_sha})
    if not lines and head is None and not problems:
        return {"status": "EMPTY", "n": 0, "problems": [], "head": None}
    row_types = {p["type"] for p in problems if p["type"] in ("LINE_UNPARSABLE", "BAD_SHAPE", "SHA_MISMATCH", "PREV_MISMATCH")}
    if row_types:
        status = "TAMPERED"
    elif any(p["type"] == "TORN_TAIL" for p in problems):
        status = "TORN_TAIL"
    elif problems:
        status = "HEAD_MISMATCH"
    else:
        status = "OK"
    return {"status": status, "n": len(lines), "problems": problems, "head": head}


def find_by_prefix(ledger_dir, prefix: str) -> list:
    return [r for r in read_events(ledger_dir) if isinstance(r.get("sha"), str) and r["sha"].startswith(prefix)]
